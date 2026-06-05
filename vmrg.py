#!/usr/bin/env python3

import os
import re
import sys
import ast
import json
import time
import mmap
import hashlib
import shutil
from pathlib import Path
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from fnmatch import fnmatch

VERSION = "4.0.0"
MERGED_SUFFIX = "_merged.txt"
FALLBACK_BASE = "vibemerge"
MAX_FILE_SIZE = 1024 * 1024 * 1024
MAX_TOTAL_SIZE = 1024 * 1024 * 1024
CHUNK_SIZE = 256 * 1024
FILE_HEADER_RE = re.compile(r"^(FILE|DELETE|RENAME|PATCH|MKDIR|RMDIR):\s*(.+?)\s*$")
DRIVE_RE = re.compile(r"^[A-Za-z]:")
REPLY_END_MARKER = "END OF REPLY"
NO_CHANGES_MARKER = "NO CHANGES REQUIRED"
GITIGNORE_NAME = ".gitignore"
JUNK_DIR_NAMES = frozenset(
    ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")
)
JUNK_FILE_NAMES = frozenset((".DS_Store", "Thumbs.db", "desktop.ini"))
JUNK_FILE_SUFFIXES = (".pyc", ".pyo", ".swp", ".swo", ".orig", ".rej")
HUNK_SEARCH = "<<<<<<< SEARCH"
HUNK_SEP = "======="
HUNK_REPLACE = ">>>>>>> REPLACE"
PATCH_COVERAGE_LIMIT = 0.6

AI_FORMAT_DIRECTIVE = (
    "\n".join(
        [
            "=" * 80,
            "SYSTEM INSTRUCTION FOR AI",
            "Your reply will be applied back to the project automatically.",
            "When you answer with code changes, you MUST follow this exact format:",
            "1. Start every created file, and every file where you change more than",
            "   about 60 percent of the content, with this 3-line header, with the",
            "   dashes and the FILE: line at the very start of the line, followed by",
            "   the COMPLETE file content. Never write diffs, fragments, placeholders",
            "   or omitted sections inside a FILE body:",
            "   " + "-" * 77,
            "   FILE: relative/path/from/project/root.ext",
            "   " + "-" * 77,
            "2. When you change less than about 60 percent of an existing file, do",
            "   NOT resend the whole file. Use a PATCH header instead and send only",
            "   the changed parts as one or more search and replace hunks:",
            "   " + "-" * 77,
            "   PATCH: relative/path/from/project/root.ext",
            "   " + "-" * 77,
            "   " + HUNK_SEARCH,
            "   the exact existing lines, copied verbatim from the file",
            "   " + HUNK_SEP,
            "   the new lines that replace them",
            "   " + HUNK_REPLACE,
            "   Hunk rules: copy the SEARCH lines exactly as they appear in the file,",
            "   including indentation, spacing and blank lines; include enough",
            "   surrounding lines that the SEARCH block matches exactly one place in",
            "   the file; write multiple hunks in top to bottom file order; hunks",
            "   must never overlap; an empty REPLACE part deletes the SEARCH lines.",
            "   Decide between FILE and PATCH independently for every file: one",
            "   reply may freely mix complete FILE sections for heavily changed",
            "   files with PATCH sections for lightly changed ones.",
            "3. To delete a file, write the same 3-line header with DELETE: instead",
            "   of FILE: and write nothing after the header:",
            "   " + "-" * 77,
            "   DELETE: relative/path/from/project/root.ext",
            "   " + "-" * 77,
            "   When you delete a file, also update every file that imports or",
            "   references it and include those updates in your reply.",
            "4. To rename or move a file or a directory, write the same 3-line",
            "   header with RENAME: and both paths separated by an arrow:",
            "   " + "-" * 77,
            "   RENAME: old/path -> new/path",
            "   " + "-" * 77,
            "   For a file, leave the body empty to move it unchanged, or write the",
            "   complete new content after the header to move and modify it in one",
            "   step. For a directory, the body must stay empty and everything",
            "   inside moves with it. Update every import and reference to the old",
            "   path in the files you output.",
            "5. To create an empty directory, write the same 3-line header with",
            "   MKDIR: and the directory path; write nothing after the header.",
            "   Directories of FILE paths are created automatically, so MKDIR is",
            "   only for directories that must exist while still empty:",
            "   " + "-" * 77,
            "   MKDIR: relative/path/to/dir",
            "   " + "-" * 77,
            "6. To delete a directory AND EVERYTHING INSIDE IT, write the same",
            "   3-line header with RMDIR: and the directory path; write nothing",
            "   after the header. Use it with care and update every file that",
            "   imports or references anything inside that directory:",
            "   " + "-" * 77,
            "   RMDIR: relative/path/to/dir",
            "   " + "-" * 77,
            "7. If several files must receive exactly identical content, write their",
            "   FILE headers stacked directly on top of each other followed by a",
            "   single body; every listed path receives that same content.",
            "8. Use exactly the relative paths that appear in the headers below,",
            "   with forward slashes. Never invent new locations for existing",
            "   files.",
            "9. Output ONLY the files and directories that need to be created,",
            "   modified, renamed or deleted. If something does not need changes,",
            "   leave it out entirely.",
            "10. NEVER compress or minify your reply. Always use normal",
            "    indentation, spacing and line breaks.",
            "11. Do not wrap the reply in markdown code fences and do not add any",
            "    commentary before, between or after the files.",
            "12. Do only what the task asks, nothing more. Do not create markdown",
            "    files, README files, reports, summaries, changelogs, examples or",
            "    any other documentation unless the task explicitly asks for them.",
            "13. If the task requires no changes at all, reply with this single",
            "    line and nothing else:",
            "    NO CHANGES REQUIRED",
            "14. Your reply is applied only if it is complete. Always end it with",
            "    this single line so truncated replies are rejected:",
            "    END OF REPLY",
            "=" * 80,
        ]
    )
    + "\n\n"
)

DUPLICATE_NOTE = (
    "\n".join(
        [
            "=" * 80,
            "SYSTEM INSTRUCTION FOR AI",
            "DUPLICATE FILE NOTE",
            "Some files below share exactly identical content. They are written",
            "once, with several FILE headers stacked directly above a single body;",
            "every path listed in such a stack has exactly that content. You may",
            "use the same stacked header form in your reply.",
            "=" * 80,
        ]
    )
    + "\n\n"
)

REMOVE_COMMENTS_DIRECTIVE = (
    "\n".join(
        [
            "=" * 80,
            "SYSTEM INSTRUCTION FOR AI",
            "COMMENT POLICY: NO COMMENTS",
            "Remove every comment and docstring from the code you output and do",
            "not write any new ones. Deliver clean, self-explanatory code only.",
            "When you patch a file, do not reintroduce comments around the",
            "changed lines.",
            "=" * 80,
        ]
    )
    + "\n\n"
)

ADD_COMMENTS_DIRECTIVE = (
    "\n".join(
        [
            "=" * 80,
            "SYSTEM INSTRUCTION FOR AI",
            "COMMENT POLICY: PROFESSIONAL COMMENTS",
            "Comment the code you output, strictly following these standards:",
            "- Explain WHY: intent, trade-offs, invariants, edge cases and",
            "  non-obvious decisions. Never restate what the code plainly does.",
            "- Document every public module, class and function in the standard",
            "  documentation format of its language (PEP 257 docstrings for",
            "  Python, JSDoc for JavaScript and TypeScript, doc comments for Go,",
            "  Rust and Java), covering purpose, parameters, return value and",
            "  raised errors where applicable.",
            "- Keep comments short, precise and written in clear English as",
            "  complete sentences.",
            "- State units, ranges, formats and external constraints such as",
            "  protocol or business rules where they are not obvious.",
            "- Place comments on their own line directly above the code they",
            "  describe and keep them consistent with the code; a comment that",
            "  contradicts the code is a defect.",
            "- Never leave commented-out code, decorative banners, or TODO and",
            "  FIXME markers without an explanation and a reason.",
            "=" * 80,
        ]
    )
    + "\n\n"
)


def format_bytes(size):
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    while size >= 1024.0 and idx < len(units) - 1:
        size /= 1024.0
        idx += 1
    return f"{int(size)} {units[idx]}" if idx == 0 else f"{size:.2f} {units[idx]}"


def format_time(seconds):
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.0f}s"


class Theme:
    SUCCESS = "32"
    WARNING = "33"
    ERROR = "31"
    INFO = "36"
    MUTED = "2"
    ACCENT = "1;38;5;208"
    PROGRESS = "38;5;208"
    RESET = "\033[0m"

    ROLES = {
        "ok": SUCCESS,
        "warn": WARNING,
        "err": ERROR,
        "info": INFO,
        "dim": MUTED,
        "accent": ACCENT,
        "progress": PROGRESS,
    }

    TAG_ROLES = {
        "+": "ok",
        "~": "info",
        "-": "warn",
        "=": "dim",
        "!": "err",
        "*": "info",
    }

    def __init__(self, stream=None):
        stream = stream if stream is not None else sys.stdout
        env = os.environ
        try:
            is_tty = stream.isatty()
        except (AttributeError, ValueError):
            is_tty = False
        self.enabled = (
            is_tty and "NO_COLOR" not in env and env.get("TERM", "") != "dumb"
        )

    def code_for(self, role):
        return self.ROLES.get(role, "")

    def paint(self, text, role):
        code = self.code_for(role)
        if not self.enabled or not code:
            return str(text)
        return f"\033[{code}m{text}{self.RESET}"

    def paint_count(self, value, role):
        if value <= 0:
            return self.paint(f"{value:,}", "dim")
        return self.paint(f"{value:,}", role)


class TUI:
    def __init__(self, quiet=False):
        self.quiet = quiet
        self.is_tty = sys.stdout.isatty()
        self.term_width = shutil.get_terminal_size((80, 24))[0]
        self.theme = Theme(sys.stdout)
        self.color = self.theme.enabled

    def paint(self, text, role):
        return self.theme.paint(text, role)

    def print_header(self, text):
        if self.quiet:
            return
        width = min(self.term_width, 80)
        print()
        print(self.paint("-" * width, "dim"))
        print(self.paint(text + ":", "accent"))
        print(self.paint("-" * width, "dim"))
        print()

    def print_section(self, text):
        if self.quiet:
            return
        width = min(self.term_width, 80)
        print()
        print(self.paint("-" * width, "dim"))
        print(self.paint(text, "accent"))
        print(self.paint("-" * width, "dim"))
        print()

    def print_info(self, label, value, kind=None):
        if self.quiet:
            return
        lab = f"{label:.<20}"
        val = str(value)
        if kind:
            val = self.paint(val, kind)
        print(self.paint(lab, "dim") + " " + val)

    def print_count(self, label, value, role):
        if self.quiet:
            return
        lab = f"{label:.<20}"
        print(self.paint(lab, "dim") + " " + self.theme.paint_count(value, role))

    def print_item(self, tag, text, kind=None):
        if self.quiet:
            return
        role = kind if kind else Theme.TAG_ROLES.get(tag, "dim")
        print("  " + self.paint(tag, role) + " " + text)

    def blank_line(self):
        if not self.quiet:
            print()

    def progress_bar(self, current, total, prefix="", width=40):
        if self.quiet or not self.is_tty or total == 0:
            return
        percent = current / total
        filled = int(width * percent)
        if self.color:
            bar = self.paint("#" * filled, "progress") + self.paint(
                "-" * (width - filled), "dim"
            )
            display = f"\r{prefix} [{bar}] {int(percent * 100)}% ({current}/{total})"
            sys.stdout.write(display)
        else:
            bar = "#" * filled + "-" * (width - filled)
            display = f"\r{prefix} [{bar}] {int(percent * 100)}% ({current}/{total})"
            sys.stdout.write(display[: self.term_width])
        sys.stdout.flush()
        if current >= total:
            print()


class ProgressTracker:
    def __init__(self, total, prefix="", tui=None):
        self.total = total
        self.prefix = prefix
        self.tui = tui
        self.current = 0
        self.start_time = time.time()

    def update(self, increment=1):
        if not self.tui:
            return
        self.current += increment
        self.tui.progress_bar(self.current, self.total, self.prefix)

    def finish(self):
        if self.tui and not self.tui.quiet:
            elapsed = time.time() - self.start_time
            self.tui.print_info("Time elapsed", format_time(elapsed))


def self_paths():
    result = set()
    try:
        result.add(Path(__file__).resolve())
    except (OSError, ValueError, NameError):
        pass
    try:
        if sys.argv and sys.argv[0]:
            result.add(Path(sys.argv[0]).resolve())
    except (OSError, ValueError, IndexError):
        pass
    return result


def load_patterns(path):
    p = Path(path)
    if not p.exists():
        return tuple()
    patterns = []
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            negated = False
            if line.startswith("!"):
                negated = True
                line = line[1:].strip()
            elif line.startswith("\\"):
                line = line[1:]
            line = line.strip("/")
            if line:
                patterns.append((line, negated))
    return tuple(patterns)


def matches_pattern(name, rel, p):
    if fnmatch(name, p) or fnmatch(rel, p):
        return True
    if fnmatch(rel, p + "/*") or fnmatch(rel, "*/" + p + "/*"):
        return True
    return False


class IgnoreRules:
    def __init__(self, ignore_value=None):
        value = ignore_value or GITIGNORE_NAME
        self.name = Path(value).name
        self.rules = []
        self.loaded_files = set()
        if ignore_value:
            try:
                explicit = Path(ignore_value).resolve()
            except (OSError, ValueError):
                explicit = None
            if explicit is not None and explicit.is_file():
                self.global_patterns = load_patterns(explicit)
                self.loaded_files.add(explicit)
            else:
                self.global_patterns = tuple()
        else:
            self.global_patterns = tuple()

    def register_root(self, directory):
        if self.global_patterns:
            self.rules.append((directory, self.global_patterns))
        self.load_dir(directory)

    def load_dir(self, directory):
        candidate = directory / self.name
        try:
            resolved = candidate.resolve()
        except (OSError, ValueError):
            return
        if resolved in self.loaded_files:
            return
        patterns = load_patterns(candidate)
        if patterns:
            self.loaded_files.add(resolved)
            self.rules.append((directory, patterns))

    def ignored(self, path):
        verdict = False
        decided = False
        name = path.name
        for scope, patterns in self.rules:
            if scope != path.parent and scope not in path.parents:
                continue
            try:
                rel = path.relative_to(scope).as_posix()
            except (ValueError, TypeError):
                continue
            for p, negated in patterns:
                if matches_pattern(name, rel, p):
                    verdict = not negated
                    decided = True
        return verdict if decided else False


def is_text(filepath):
    try:
        stat = filepath.stat()
        if stat.st_size == 0 or stat.st_size > MAX_FILE_SIZE:
            return False
        with open(filepath, "rb") as f:
            return b"\x00" not in f.read(8192)
    except OSError:
        return False


def read_file(filepath):
    try:
        with open(filepath, "rb") as f:
            size = os.fstat(f.fileno()).st_size
            if size < CHUNK_SIZE:
                return f.read()
            try:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    return bytes(mm)
            except (OSError, ValueError):
                f.seek(0)
                return f.read()
    except OSError:
        return None


def process_file_worker(args):
    fpath, basedir = args
    try:
        content_bytes = read_file(fpath)
        if content_bytes is None:
            return None

        lines = content_bytes.count(b"\n") + 1

        try:
            content_str = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content_str = content_bytes.decode("utf-8", errors="replace")

        content_str = content_str.rstrip()

        rel = relative_label(fpath, basedir)
        header = f"{'-' * 80}\nFILE: {rel}\n{'-' * 80}\n\n"

        return {
            "content": content_str,
            "header": header,
            "lines": lines,
            "size": len(content_bytes),
        }
    except Exception:
        return None


def resolve_paths(paths):
    resolved_files = []
    resolved_dirs = []
    seen = set()

    for path_str in paths:
        try:
            path = Path(path_str).resolve()
        except (OSError, ValueError):
            raise ValueError(f"Invalid path: {path_str}")

        if path in seen:
            continue
        seen.add(path)

        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")

        if path.is_file():
            resolved_files.append(path)
        elif path.is_dir():
            resolved_dirs.append(path)
        else:
            raise ValueError(f"Invalid path type: {path}")

    return resolved_files, resolved_dirs


def default_output_path(paths):
    first = Path(paths[0]).resolve()
    base = first.stem if first.is_file() else first.name
    base = "".join(c if (c.isalnum() or c in "-_") else "_" for c in base).strip("_")
    if not base:
        base = FALLBACK_BASE
    return (Path.cwd() / f"{base}{MERGED_SUFFIX}").resolve()


def collect_files_from_dirs(directories, rules, tui, outpath, seen):
    all_paths = []

    for directory in directories:
        rules.register_root(directory)
        for root, dirs, filenames in os.walk(directory):
            root_path = Path(root)
            if root_path != directory:
                rules.load_dir(root_path)
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and not rules.ignored(root_path / d)
            ]
            for filename in filenames:
                if not filename.startswith("."):
                    all_paths.append((root_path / filename, directory))

    tui.print_header("SCANNING FILES")
    tui.print_info("Directories", f"{len(directories)}")
    tui.print_info("Total files found", f"{len(all_paths):,}")

    tracker = ProgressTracker(len(all_paths), "Scanning", tui)

    valid_files = []
    total = 0
    limit_hit = False

    for fpath, basedir in all_paths:
        tracker.update()

        if limit_hit:
            continue
        if fpath == outpath or fpath in seen:
            continue
        if rules.ignored(fpath):
            continue
        if not fpath.is_file():
            continue
        if not is_text(fpath):
            continue

        try:
            fsize = fpath.stat().st_size
        except OSError:
            continue

        if total + fsize > MAX_TOTAL_SIZE:
            limit_hit = True
            continue

        total += fsize
        seen.add(fpath)
        valid_files.append((fpath, basedir))

    tracker.finish()

    if limit_hit:
        tui.print_info("Warning", "Size limit reached, some files skipped")

    return valid_files, total


def collect_files(input_files, directories, rules, tui, outpath, excluded=None):
    files = []
    total = 0
    seen = set(self_paths())
    if excluded:
        seen.update(excluded)
    part_prefix = f"{outpath.stem}_part"

    def is_output_part(fpath):
        return (
            fpath.parent == outpath.parent
            and fpath.suffix == outpath.suffix
            and fpath.stem.startswith(part_prefix)
        )

    if input_files:
        tui.print_header("VALIDATING FILES")
        tui.print_info("Input files", f"{len(input_files):,}")

        tracker = ProgressTracker(len(input_files), "Validating", tui)
        limit_hit = False

        for fpath in input_files:
            tracker.update()

            if limit_hit:
                continue
            if fpath == outpath or fpath in seen or is_output_part(fpath):
                continue
            if not fpath.is_file():
                continue
            if not is_text(fpath):
                continue

            try:
                fsize = fpath.stat().st_size
            except OSError:
                continue

            if total + fsize > MAX_TOTAL_SIZE:
                limit_hit = True
                continue

            total += fsize
            seen.add(fpath)
            files.append((fpath, fpath.parent))

        tracker.finish()

        if limit_hit:
            tui.print_info("Warning", "Size limit reached, some files skipped")

    if directories:
        dir_files, dir_size = collect_files_from_dirs(
            directories, rules, tui, outpath, seen
        )
        dir_files = [
            (fpath, basedir)
            for fpath, basedir in dir_files
            if not is_output_part(fpath)
        ]
        dir_size = sum(
            fpath.stat().st_size for fpath, _basedir in dir_files if fpath.is_file()
        )

        if total + dir_size > MAX_TOTAL_SIZE:
            remaining = MAX_TOTAL_SIZE - total
            accumulated = 0
            for fpath, basedir in dir_files:
                try:
                    fsize = fpath.stat().st_size
                except OSError:
                    continue
                if accumulated + fsize > remaining:
                    continue
                files.append((fpath, basedir))
                accumulated += fsize
            total += accumulated
        else:
            files.extend(dir_files)
            total += dir_size

    return sorted(files, key=lambda x: x[0]), total


def estimate_tokens(chars):
    return max(1, chars // 4) if chars > 0 else 0


def render_tree(rels):
    tree = {}
    for rel in sorted(rels):
        node = tree
        parts = rel.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part + "/", {})
        node[parts[-1]] = None

    lines = []

    def walk(node, depth):
        dirs = sorted(k for k, v in node.items() if v is not None)
        files = sorted(k for k, v in node.items() if v is None)
        for name in dirs:
            lines.append("  " * depth + name)
            walk(node[name], depth + 1)
        for name in files:
            lines.append("  " * depth + name)

    walk(tree, 0)
    return (
        "=" * 80 + "\nPROJECT STRUCTURE\n" + "\n".join(lines) + "\n" + "=" * 80 + "\n\n"
    )


def prompt_interactively():
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        return data.strip()
    print("Enter task (finish with an empty line):")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines).strip()


def build_system_block(system_file):
    if not system_file:
        return ""
    try:
        p = Path(system_file).resolve()
        text = p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as e:
        raise ValueError(f"Cannot read system prompt file {system_file}: {e}")
    if not text:
        return ""
    return text + "\n\n"


def build_task_block(message, interactive_text=None):
    pieces = []
    if interactive_text:
        pieces.append(interactive_text.strip())
    if message:
        pieces.append(message.strip())
    if not pieces:
        return ""
    return "=" * 80 + "\nTASK\n" + "\n\n".join(pieces) + "\n" + "=" * 80 + "\n"


def continuation_directive(part):
    return (
        "\n".join(
            [
                "=" * 80,
                "SYSTEM INSTRUCTION FOR AI",
                f"VIBEMERGE CONTINUATION - PART {part}",
                "This file continues the same project from the previous part.",
                "All instructions from part 1 apply to the complete set of parts.",
                "=" * 80,
            ]
        )
        + "\n\n"
    )


class PatchError(ValueError):
    pass


def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_patch_hunks(content, rel):
    lines = normalize_newlines(content).split("\n")
    hunks = []
    i = 0
    n = len(lines)
    while i < n:
        if not lines[i].strip():
            i += 1
            continue
        if lines[i] != HUNK_SEARCH:
            raise PatchError(
                f"PATCH {rel} contains text outside of search and replace hunks"
            )
        i += 1
        search_lines = []
        while i < n and lines[i] != HUNK_SEP:
            search_lines.append(lines[i])
            i += 1
        if i >= n:
            raise PatchError(f"PATCH {rel} has a hunk without a {HUNK_SEP} separator")
        i += 1
        replace_lines = []
        while i < n and lines[i] != HUNK_REPLACE:
            replace_lines.append(lines[i])
            i += 1
        if i >= n:
            raise PatchError(
                f"PATCH {rel} has a hunk without a {HUNK_REPLACE} terminator"
            )
        i += 1
        search = "\n".join(search_lines)
        if not search.strip():
            raise PatchError(f"PATCH {rel} has a hunk with an empty SEARCH block")
        hunks.append((search, "\n".join(replace_lines)))
    if not hunks:
        raise PatchError(f"PATCH {rel} contains no hunks")
    return hunks


def find_anchored(text, search):
    positions = []
    start = 0
    slen = len(search)
    while True:
        idx = text.find(search, start)
        if idx == -1:
            break
        end = idx + slen
        head_ok = idx == 0 or text[idx - 1] == "\n"
        tail_ok = end == len(text) or text[end] == "\n"
        if head_ok and tail_ok:
            positions.append((idx, end))
        start = idx + 1
    return positions


def apply_hunks(original, hunks, rel):
    text = normalize_newlines(original)
    base_len = max(1, len(text))
    for index, (search, replace) in enumerate(hunks, 1):
        positions = find_anchored(text, search)
        if not positions:
            raise PatchError(
                f"hunk {index} of PATCH {rel} does not match the current file content"
            )
        if len(positions) > 1:
            raise PatchError(
                f"hunk {index} of PATCH {rel} matches {len(positions)} places, "
                "it must match exactly one"
            )
        s, e = positions[0]
        if replace == "":
            if e < len(text) and text[e] == "\n":
                e += 1
            elif s > 0 and text[s - 1] == "\n":
                s -= 1
            text = text[:s] + text[e:]
        else:
            text = text[:s] + replace + text[e:]
    coverage = sum(len(search) for search, _replace in hunks) / base_len
    if text and not text.endswith("\n"):
        text += "\n"
    return text, coverage


def parse_rename(raw):
    if "->" not in raw:
        return None
    old, _sep, new = raw.partition("->")
    old = old.strip()
    new = new.strip()
    if not old or not new:
        return None
    return old, new


def validate_content(rel, content):
    if not content.strip():
        return None
    ext = rel.suffix.lower()
    if ext == ".py":
        try:
            ast.parse(content)
        except SyntaxError as e:
            return f"python syntax error at line {e.lineno}"
        except (ValueError, RecursionError):
            return "python parse failure"
    elif ext == ".json":
        try:
            json.loads(content)
        except ValueError:
            return "invalid json"
    return None


def under_version_control(path):
    try:
        cur = Path(path).resolve()
    except (OSError, ValueError):
        return False
    for p in [cur, *cur.parents]:
        try:
            if (p / ".git").exists():
                return True
        except OSError:
            continue
    return False


def is_junk_file(name):
    if name in JUNK_FILE_NAMES:
        return True
    if name.endswith("~"):
        return True
    return any(name.endswith(suffix) for suffix in JUNK_FILE_SUFFIXES)


def tree_size(path):
    total = 0
    for root, _dirs, filenames in os.walk(path):
        root_path = Path(root)
        for filename in filenames:
            try:
                total += (root_path / filename).stat().st_size
            except OSError:
                continue
    return total


def hash_file(fpath):
    digest = hashlib.md5()
    try:
        with open(fpath, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def detect_duplicates(files):
    by_size = {}
    for fpath, basedir in files:
        try:
            size = fpath.stat().st_size
        except OSError:
            continue
        by_size.setdefault(size, []).append((fpath, basedir))

    groups = {}
    aliases = set()
    for entries in by_size.values():
        if len(entries) < 2:
            continue
        by_hash = {}
        for fpath, basedir in entries:
            digest = hash_file(fpath)
            if digest is None:
                continue
            by_hash.setdefault(digest, []).append((fpath, basedir))
        for members in by_hash.values():
            if len(members) < 2:
                continue
            rep = members[0][0]
            groups[rep] = members
            for fpath, _basedir in members[1:]:
                aliases.add(fpath)
    return groups, aliases


def relative_label(fpath, basedir):
    try:
        return fpath.relative_to(basedir).as_posix()
    except (ValueError, TypeError):
        return fpath.name


def stacked_header(members):
    blocks = []
    for fpath, basedir in members:
        rel = relative_label(fpath, basedir)
        blocks.append(f"{'-' * 80}\nFILE: {rel}\n{'-' * 80}\n")
    return "".join(blocks) + "\n"


class MergeEngine:
    def __init__(
        self,
        paths,
        output,
        ignore,
        add_comments,
        keep_comments,
        ai_format,
        quiet,
        system_file=None,
        message=None,
        split=None,
        interactive=False,
        clean=False,
    ):
        self.paths = paths
        self.output = output
        self.ignore = ignore
        self.add_comments = add_comments
        self.keep_comments = keep_comments
        self.ai_format = ai_format
        self.clean = clean
        self.system_file = system_file
        self.message = message
        self.split = split
        self.interactive = interactive
        self.tui = TUI(quiet)
        self.stats = {"written": 0, "failed": 0, "lines": 0, "chars": 0}
        self.parts = []
        self.state = {"out": None, "part": 0, "part_chars": 0, "part_written": 0}

    def run(self):
        tui = self.tui

        input_files, directories = resolve_paths(self.paths)
        if not input_files and not directories:
            raise ValueError("No valid files or directories provided")

        interactive_text = prompt_interactively() if self.interactive else None

        if self.clean:
            self._clean_junk(directories)

        rules = IgnoreRules(self.ignore)

        if self.output:
            try:
                outpath = Path(self.output).resolve()
            except (OSError, ValueError):
                raise ValueError(f"Invalid output path: {self.output}")
        else:
            outpath = default_output_path(self.paths)
        self.outpath = outpath

        excluded = self._excluded_inputs()

        operation_start = time.time()

        files, total_size = collect_files(
            input_files, directories, rules, tui, outpath, excluded
        )
        if not files:
            raise ValueError("No valid files found")

        try:
            outpath.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ValueError(f"Cannot create output directory: {e}")

        groups, aliases = detect_duplicates(files)
        group_sizes = {rep: len(members) for rep, members in groups.items()}

        self._print_plan(files, total_size, groups)

        task_block = build_task_block(self.message, interactive_text)
        system_block = build_system_block(self.system_file)
        self.preamble = self._build_preamble(system_block, bool(groups))
        self.tree_block = (
            render_tree([relative_label(f, b) for f, b in files])
            if self.ai_format
            else ""
        )
        self.split_chars = self.split * 4 if self.split else None

        merge_start = time.time()

        self._open_part()
        try:
            tracker = ProgressTracker(len(files), "Processing", tui)
            for fpath, basedir in files:
                if fpath in aliases:
                    tracker.update()
                    continue
                try:
                    result = process_file_worker((fpath, basedir))
                except Exception:
                    result = None
                if result is not None and fpath in groups:
                    result["header"] = stacked_header(groups[fpath])
                self._write_section(result, group_sizes.get(fpath, 1))
                tracker.update()

            if task_block:
                self._emit("\n\n" + task_block)
            self._close_part()
            tracker.finish()
        finally:
            if self.state["out"] is not None:
                self.state["out"].close()

        self._print_summary(
            total_size,
            time.time() - merge_start,
            time.time() - operation_start,
            groups,
        )
        return self.parts, self.stats["written"], total_size

    def _clean_junk(self, directories):
        tui = self.tui
        tui.print_header("CLEANING JUNK")
        removed = 0
        freed = 0
        failed = 0
        protected = set(self_paths())
        if not directories:
            tui.print_info("Junk removed", "0 (no directories given)")
            return
        for directory in directories:
            for root, dirs, filenames in os.walk(directory):
                root_path = Path(root)
                if ".git" in dirs:
                    dirs.remove(".git")
                junk_dirs = [d for d in dirs if d in JUNK_DIR_NAMES]
                dirs[:] = [d for d in dirs if d not in JUNK_DIR_NAMES]
                for name in junk_dirs:
                    junk_path = root_path / name
                    rel = relative_label(junk_path, directory)
                    size = tree_size(junk_path)
                    try:
                        shutil.rmtree(junk_path)
                        removed += 1
                        freed += size
                        tui.print_item("-", f"removed junk dir {rel}/", "warn")
                    except OSError as e:
                        failed += 1
                        tui.print_item("!", f"could not remove {rel}/: {e}", "err")
                for filename in filenames:
                    if not is_junk_file(filename):
                        continue
                    junk_path = root_path / filename
                    if junk_path.resolve() in protected:
                        continue
                    rel = relative_label(junk_path, directory)
                    try:
                        size = junk_path.stat().st_size
                    except OSError:
                        size = 0
                    try:
                        junk_path.unlink()
                        removed += 1
                        freed += size
                        tui.print_item("-", f"removed junk file {rel}", "warn")
                    except OSError as e:
                        failed += 1
                        tui.print_item("!", f"could not remove {rel}: {e}", "err")
        tui.print_count("Junk removed", removed, "warn")
        if failed > 0:
            tui.print_count("Junk failed", failed, "err")
        tui.print_info("Space freed", format_bytes(freed))

    def _excluded_inputs(self):
        excluded = set()
        if self.system_file:
            try:
                excluded.add(Path(self.system_file).resolve())
            except (OSError, ValueError):
                pass
        return excluded

    def _build_preamble(self, system_block, has_duplicates):
        pieces = []
        if system_block:
            pieces.append(system_block)
        if self.ai_format:
            pieces.append(AI_FORMAT_DIRECTIVE)
        if has_duplicates:
            pieces.append(DUPLICATE_NOTE)
        if not self.keep_comments:
            pieces.append(
                ADD_COMMENTS_DIRECTIVE
                if self.add_comments
                else REMOVE_COMMENTS_DIRECTIVE
            )
        return "".join(pieces)

    def _print_plan(self, files, total_size, groups):
        tui = self.tui
        tui.print_header("PROCESSING FILES")
        tui.print_info("Valid files", f"{len(files):,}")
        tui.print_info("Total size", format_bytes(total_size))
        tui.print_info("Ignore file", self.ignore if self.ignore else GITIGNORE_NAME)
        if groups:
            duplicate_paths = sum(len(m) for m in groups.values())
            tui.print_info(
                "Duplicates",
                f"{duplicate_paths:,} path(s) in {len(groups):,} identical group(s)",
                "info",
            )
        if not self.keep_comments:
            tui.print_info(
                "Comment policy",
                "Add professional comments" if self.add_comments else "Remove comments",
            )
        if self.ai_format:
            tui.print_info("AI round-trip", "Enabled")
        if self.system_file:
            tui.print_info("System prompt", str(self.system_file))
        if self.split:
            tui.print_info("Split limit", f"~{self.split:,} tokens per part")
        tui.blank_line()

    def _part_path(self, index):
        if not self.split:
            return self.outpath
        return self.outpath.with_name(
            f"{self.outpath.stem}_part{index}{self.outpath.suffix}"
        )

    def _emit(self, text):
        self.state["out"].write(text)
        self.stats["chars"] += len(text)
        self.state["part_chars"] += len(text)

    def _close_part(self):
        if self.state["out"] is None:
            return
        self._emit("\n" + REPLY_END_MARKER + "\n")
        self.state["out"].close()
        self.state["out"] = None

    def _open_part(self):
        self._close_part()
        self.state["part"] += 1
        p = self._part_path(self.state["part"])
        try:
            self.state["out"] = open(p, "w", encoding="utf-8", buffering=CHUNK_SIZE)
        except OSError as e:
            raise ValueError(f"Cannot write output file {p}: {e}")
        self.parts.append(p)
        self.state["part_chars"] = 0
        self.state["part_written"] = 0
        if self.state["part"] == 1:
            if self.preamble:
                self._emit(self.preamble)
            if self.tree_block:
                self._emit(self.tree_block)
        else:
            self._emit(continuation_directive(self.state["part"]))

    def _write_section(self, result, path_count):
        if result is None:
            self.stats["failed"] += 1
            return
        section = result["header"] + result["content"] + "\n"
        if (
            self.split_chars
            and self.state["part_written"] > 0
            and self.state["part_chars"] + len(section) > self.split_chars
        ):
            self._open_part()
        if self.state["part_written"] > 0:
            self._emit("\n\n")
        self._emit(section)
        self.state["part_written"] += 1
        self.stats["written"] += path_count
        self.stats["lines"] += result["lines"]

    def _print_summary(self, total_size, merge_elapsed, total_elapsed, groups):
        tui = self.tui
        stats = self.stats
        tui.print_section("OPERATION COMPLETE")
        tui.print_count("Files merged", stats["written"], "ok")
        if stats["failed"] > 0:
            tui.print_count("Files failed", stats["failed"], "err")
        if groups:
            deduplicated = sum(len(m) - 1 for m in groups.values())
            tui.print_count("Bodies deduplicated", deduplicated, "info")
        tui.print_info("Total lines", f"{stats['lines']:,}")
        tui.print_info("Total size", format_bytes(total_size))
        tui.print_info("Estimated tokens", f"{estimate_tokens(stats['chars']):,}")
        tui.print_info("Merge time", format_time(merge_elapsed))
        tui.print_info("Total time", format_time(total_elapsed))
        if self.split and len(self.parts) > 1:
            tui.print_info("Output parts", f"{len(self.parts)}", "info")
            for p in self.parts:
                tui.print_item("*", str(p))
        else:
            tui.print_info("Output file", str(self.parts[0]), "info")


def is_dash_line(line):
    s = line.strip()
    return len(s) >= 3 and set(s) == {"-"}


def strip_fences(lines):
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    if (
        end - start >= 2
        and lines[start].lstrip().startswith("```")
        and lines[end - 1].strip().startswith("```")
    ):
        return lines[start + 1 : end - 1]
    return lines[start:end]


def parse_merged(text):
    raw_lines = text.split("\n")

    has_end = False
    while raw_lines and not raw_lines[-1].strip():
        raw_lines.pop()
    while raw_lines and raw_lines[-1].strip() == REPLY_END_MARKER:
        has_end = True
        raw_lines.pop()
        while raw_lines and not raw_lines[-1].strip():
            raw_lines.pop()

    if raw_lines and raw_lines[0].lstrip().startswith("```"):
        raw_lines = raw_lines[1:]
        k = len(raw_lines) - 1
        while k >= 0 and not raw_lines[k].strip():
            k -= 1
        if k >= 0 and raw_lines[k].strip().startswith("```"):
            raw_lines = raw_lines[:k]

    lines = []
    fence_open = False
    for line in raw_lines:
        if not fence_open and line.strip() == REPLY_END_MARKER:
            has_end = True
            continue
        lines.append(line)
        if line.lstrip().startswith("```"):
            fence_open = not fence_open

    in_fence = []
    fence_open = False
    for line in lines:
        in_fence.append(fence_open)
        if line.lstrip().startswith("```"):
            fence_open = not fence_open

    headers = []
    for idx, line in enumerate(lines):
        if in_fence[idx]:
            continue
        m = FILE_HEADER_RE.match(line)
        if m and idx > 0 and is_dash_line(lines[idx - 1]):
            headers.append((idx, m.group(1), m.group(2)))

    strict = bool(headers)
    if not headers:
        for idx, line in enumerate(lines):
            if in_fence[idx]:
                continue
            m = FILE_HEADER_RE.match(line)
            if m:
                headers.append((idx, m.group(1), m.group(2)))

    sections = []
    for h, (idx, action, raw_path) in enumerate(headers):
        start = idx + 1
        if start < len(lines) and is_dash_line(lines[start]):
            start += 1
        if h + 1 < len(headers):
            stop = headers[h + 1][0]
            if strict and stop > start and is_dash_line(lines[stop - 1]):
                stop -= 1
        else:
            stop = len(lines)
        body = strip_fences(lines[start:stop])
        content = "\n".join(body).rstrip()
        sections.append((action, raw_path, content + "\n" if content else ""))

    for i in range(len(sections) - 2, -1, -1):
        action, raw_path, content = sections[i]
        if action == "FILE" and content == "" and sections[i + 1][0] == "FILE":
            sections[i] = (action, raw_path, sections[i + 1][2])

    return sections, has_end


def sanitize_rel_path(raw):
    p = raw.strip().strip("\"'`").replace("\\", "/")
    p = DRIVE_RE.sub("", p)
    while p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    parts = [seg.strip() for seg in p.split("/")]
    parts = [seg for seg in parts if seg and seg != "."]
    if not parts:
        return None
    for seg in parts:
        if seg == ".." or "\x00" in seg:
            return None
    return Path(*parts)


def looks_compressed(content):
    stripped = content.strip()
    if len(stripped) < 240:
        return False
    return (stripped.count("\n") + 1) < len(stripped) / 240


def gather_rel_paths(merged_inputs):
    rels = []
    for merged in merged_inputs:
        try:
            text = merged.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            sections, _has_end = parse_merged(text)
        except Exception:
            sections = []
        for action, raw_path, _content in sections:
            if action == "RENAME":
                pair = parse_rename(raw_path)
                if pair is None:
                    continue
                rel = sanitize_rel_path(pair[0])
            else:
                rel = sanitize_rel_path(raw_path)
            if rel is not None:
                rels.append(rel)
    return rels


def candidate_roots(merged_inputs):
    roots = []
    seen = set()

    def add(path):
        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError):
            return
        if resolved not in seen:
            seen.add(resolved)
            roots.append(resolved)

    try:
        add(Path.cwd())
    except (OSError, ValueError):
        pass

    for merged in merged_inputs:
        start = merged.parent
        add(start)
        for ancestor in start.parents:
            add(ancestor)

    base_roots = list(roots)
    for base in base_roots:
        try:
            for child in base.iterdir():
                if child.is_dir() and not child.name.startswith("."):
                    add(child)
        except OSError:
            continue

    return roots


def score_root(root, rels):
    if not rels:
        return 0
    hits = 0
    for rel in rels:
        candidate = root / rel
        try:
            if candidate.is_file():
                hits += 1
        except OSError:
            continue
    return hits


def detect_project_root(merged_inputs, rels):
    best_root = None
    best_score = 0
    for root in candidate_roots(merged_inputs):
        score = score_root(root, rels)
        if score > best_score:
            best_score = score
            best_root = root
    return best_root, best_score


def write_file_atomic(dest, content):
    tmp = dest.with_name(dest.name + ".vibemerge_tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp, dest)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


class ApplyEngine:
    def __init__(self, paths, output, quiet):
        self.paths = paths
        self.output = output
        self.tui = TUI(quiet)
        self.stats = {
            "created": 0,
            "updated": 0,
            "patched": 0,
            "renamed": 0,
            "deleted": 0,
            "dirs_created": 0,
            "dirs_renamed": 0,
            "dirs_deleted": 0,
            "unchanged": 0,
            "skipped": 0,
            "suspicious": 0,
            "invalid": 0,
        }
        self.ops = []
        self.virtual = {}
        self.deleted_sentinel = object()
        self.dir_journal = []

    def run(self):
        tui = self.tui

        merged_inputs = self._resolve_inputs()
        target = self._resolve_target(merged_inputs)
        self.target = target

        tui.print_header("APPLYING FILES")
        if self.detected_note:
            tui.print_info("Detected root", self.detected_note, "info")
        tui.print_info("Target directory", str(target))
        if not under_version_control(target):
            tui.print_info("Warning", "Target is not under version control", "warn")

        start = time.time()

        sections = self._load_sections(merged_inputs)
        self._stage(sections)
        self._execute()
        self._print_summary(time.time() - start)
        return self.stats

    def _resolve_inputs(self):
        merged_inputs = []
        for path_str in self.paths:
            try:
                p = Path(path_str).resolve()
            except (OSError, ValueError):
                raise ValueError(f"Invalid merged file path: {path_str}")
            if not p.is_file():
                raise ValueError(f"Merged file not found: {p}")
            merged_inputs.append(p)
        return merged_inputs

    def _resolve_target(self, merged_inputs):
        self.detected_note = None
        if self.output:
            try:
                target = Path(self.output).resolve()
            except (OSError, ValueError):
                raise ValueError(f"Invalid target directory: {self.output}")
        else:
            rels = gather_rel_paths(merged_inputs)
            detected, score = detect_project_root(merged_inputs, rels)
            if detected is None or score == 0:
                raise ValueError(
                    "Could not detect the project root for these files. "
                    "Run again from inside the project, or pass the target "
                    "directory explicitly with -o."
                )
            target = detected
            self.detected_note = f"{target} ({score} matched)"

        if target.exists() and not target.is_dir():
            raise ValueError(f"Target must be a directory: {target}")
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ValueError(f"Cannot create target directory {target}: {e}")
        return target

    def _load_sections(self, merged_inputs):
        tui = self.tui
        all_sections = []
        for merged in merged_inputs:
            try:
                text = merged.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                raise ValueError(f"Cannot read merged file {merged}: {e}")
            try:
                sections, has_end = parse_merged(text)
            except Exception as e:
                raise ValueError(f"Could not parse merged file {merged}: {e}")

            if not sections:
                if NO_CHANGES_MARKER in text:
                    tui.print_info(
                        "Result",
                        f"AI reported no changes required in {merged.name}",
                        "ok",
                    )
                    continue
                raise ValueError(f"No FILE sections found in {merged}")

            if not has_end:
                raise ValueError(
                    f"{merged.name} has no {REPLY_END_MARKER} line. The reply "
                    "looks incomplete, so nothing was applied. Get the full "
                    "reply ending with that line and run again."
                )

            tui.print_info("Sections found", f"{len(sections)} in {merged.name}")
            all_sections.extend(sections)
        tui.blank_line()
        return all_sections

    def _inside_target(self, path):
        try:
            path.parent.resolve().relative_to(self.target)
            return True
        except (ValueError, OSError):
            return False

    def _resolve_disk(self, path):
        current = path
        for event in reversed(self.dir_journal):
            kind = event[0]
            if kind == "mv":
                _kind, old, new = event
                if current == new or new in current.parents:
                    current = old / current.relative_to(new)
                elif current == old or old in current.parents:
                    return None
            elif kind == "rm":
                _kind, removed = event
                if current == removed or removed in current.parents:
                    return None
        return current

    def _vexists(self, dest):
        if dest in self.virtual:
            return self.virtual[dest] is not self.deleted_sentinel
        disk = self._resolve_disk(dest)
        if disk is None:
            return False
        try:
            return disk.is_file()
        except OSError:
            return False

    def _vexists_any(self, dest):
        if dest in self.virtual:
            return self.virtual[dest] is not self.deleted_sentinel
        disk = self._resolve_disk(dest)
        if disk is None:
            return False
        try:
            return disk.exists()
        except OSError:
            return False

    def _vread(self, dest):
        if dest in self.virtual:
            value = self.virtual[dest]
            return None if value is self.deleted_sentinel else value
        disk = self._resolve_disk(dest)
        if disk is None:
            return None
        try:
            if disk.is_file():
                return disk.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        return None

    def _dir_exists(self, dest):
        for key, value in self.virtual.items():
            if value is not self.deleted_sentinel and dest in key.parents:
                return True
        for event in reversed(self.dir_journal):
            kind = event[0]
            if kind == "mk":
                _kind, made = event
                if dest == made or dest in made.parents:
                    return True
            elif kind == "rm":
                _kind, removed = event
                if dest == removed or removed in dest.parents:
                    return False
            elif kind == "mv":
                _kind, old, new = event
                if dest == new or new in dest.parents:
                    dest = old / dest.relative_to(new)
                elif dest == old or old in dest.parents:
                    return False
        try:
            return dest.is_dir()
        except OSError:
            return False

    def _log(self, tag, text, kind=None):
        self.ops.append({"do": "log", "tag": tag, "text": text, "kind": kind})

    def _quality_warnings(self, rel, content):
        if looks_compressed(content):
            self._log("!", f"{rel} looks compressed", "warn")
            self.stats["suspicious"] += 1
        err = validate_content(rel, content)
        if err:
            self._log("!", f"{rel} {err}", "warn")
            self.stats["invalid"] += 1

    def _stage(self, sections):
        for action, raw_path, content in sections:
            if action == "RENAME":
                self._stage_rename(raw_path, content)
                continue

            rel = sanitize_rel_path(raw_path)
            if rel is None:
                self._log("!", f"skipped unsafe path {raw_path!r}", "err")
                self.stats["skipped"] += 1
                continue
            dest = self.target / rel
            if not self._inside_target(dest):
                self._log("!", f"skipped, escapes target {raw_path!r}", "err")
                self.stats["skipped"] += 1
                continue

            if action == "DELETE":
                self._stage_delete(rel, dest)
            elif action == "PATCH":
                self._stage_patch(rel, dest, content)
            elif action == "MKDIR":
                self._stage_mkdir(rel, dest)
            elif action == "RMDIR":
                self._stage_rmdir(rel, dest)
            else:
                self._stage_file(rel, dest, content)

    def _stage_file(self, rel, dest, content):
        self._quality_warnings(rel, content)
        existed_before = self._vexists_any(dest)
        if existed_before:
            if self._vread(dest) == content:
                self._log("=", f"{rel} unchanged")
                self.stats["unchanged"] += 1
                return
            self.ops.append(
                {
                    "do": "write",
                    "dest": dest,
                    "content": content,
                    "tag": "~",
                    "text": f"updated {rel}",
                    "stat": "updated",
                }
            )
        else:
            self.ops.append(
                {
                    "do": "write",
                    "dest": dest,
                    "content": content,
                    "tag": "+",
                    "text": f"created {rel}",
                    "stat": "created",
                }
            )
        self.virtual[dest] = content

    def _stage_patch(self, rel, dest, content):
        current = self._vread(dest)
        if current is None:
            raise PatchError(
                f"PATCH target {rel} does not exist in the project, "
                "so nothing was applied"
            )
        hunks = parse_patch_hunks(content, rel)
        new_text, coverage = apply_hunks(current, hunks, rel)
        if coverage > PATCH_COVERAGE_LIMIT:
            self._log(
                "!",
                f"{rel} patch covers {int(coverage * 100)}% of the file, "
                "a full FILE section would be safer",
                "warn",
            )
        if new_text == normalize_newlines(current):
            self._log("=", f"{rel} unchanged")
            self.stats["unchanged"] += 1
            return
        self._quality_warnings(rel, new_text)
        self.ops.append(
            {
                "do": "write",
                "dest": dest,
                "content": new_text,
                "tag": "~",
                "text": f"patched {rel} ({len(hunks)} hunk(s))",
                "stat": "patched",
            }
        )
        self.virtual[dest] = new_text

    def _stage_delete(self, rel, dest):
        if self._vexists(dest):
            self.ops.append(
                {
                    "do": "delete",
                    "dest": dest,
                    "tag": "-",
                    "text": f"deleted {rel}",
                    "stat": "deleted",
                }
            )
            self.virtual[dest] = self.deleted_sentinel
        elif self._vexists_any(dest):
            self._log("!", f"skipped {rel}: not a regular file", "err")
            self.stats["skipped"] += 1
        else:
            self._log("=", f"{rel} already absent")
            self.stats["unchanged"] += 1

    def _stage_mkdir(self, rel, dest):
        if self._vexists_any(dest) and not self._dir_exists(dest):
            self._log("!", f"skipped mkdir {rel}: a file exists at that path", "err")
            self.stats["skipped"] += 1
            return
        if self._dir_exists(dest):
            self._log("=", f"{rel}/ already exists")
            self.stats["unchanged"] += 1
            return
        self.ops.append(
            {
                "do": "mkdir",
                "dest": dest,
                "tag": "+",
                "text": f"created dir {rel}/",
                "stat": "dirs_created",
            }
        )
        self.dir_journal.append(("mk", dest))

    def _stage_rmdir(self, rel, dest):
        if self._vexists(dest):
            self._log("!", f"skipped rmdir {rel}: that path is a file", "err")
            self.stats["skipped"] += 1
            return
        if not self._dir_exists(dest):
            self._log("=", f"{rel}/ already absent")
            self.stats["unchanged"] += 1
            return
        self.ops.append(
            {
                "do": "rmdir",
                "dest": dest,
                "tag": "-",
                "text": f"removed dir {rel}/ and its contents",
                "stat": "dirs_deleted",
            }
        )
        for key in list(self.virtual):
            if dest in key.parents:
                self.virtual[key] = self.deleted_sentinel
        self.dir_journal.append(("rm", dest))

    def _stage_rename(self, raw_path, content):
        pair = parse_rename(raw_path)
        old_rel = sanitize_rel_path(pair[0]) if pair else None
        new_rel = sanitize_rel_path(pair[1]) if pair else None
        if old_rel is None or new_rel is None:
            self._log("!", f"skipped unsafe rename {raw_path!r}", "err")
            self.stats["skipped"] += 1
            return
        src_path = self.target / old_rel
        dst_path = self.target / new_rel
        if not self._inside_target(src_path) or not self._inside_target(dst_path):
            self._log("!", f"skipped, escapes target {raw_path!r}", "err")
            self.stats["skipped"] += 1
            return

        if not self._vexists(src_path) and self._dir_exists(src_path):
            if content:
                self._log(
                    "!",
                    f"skipped rename {old_rel}: a directory rename cannot carry content",
                    "err",
                )
                self.stats["skipped"] += 1
                return
            if self._vexists_any(dst_path) or self._dir_exists(dst_path):
                self._log(
                    "!",
                    f"skipped rename {old_rel}: destination {new_rel} already exists",
                    "err",
                )
                self.stats["skipped"] += 1
                return
            self.ops.append(
                {
                    "do": "rename_dir",
                    "src": src_path,
                    "dest": dst_path,
                    "tag": "~",
                    "text": f"renamed dir {old_rel}/ -> {new_rel}/",
                    "stat": "dirs_renamed",
                }
            )
            for key in list(self.virtual):
                if src_path in key.parents:
                    value = self.virtual.pop(key)
                    self.virtual[dst_path / key.relative_to(src_path)] = value
            self.dir_journal.append(("mv", src_path, dst_path))
            return

        if self._vexists(src_path):
            if content:
                self._quality_warnings(new_rel, content)
                self.ops.append(
                    {
                        "do": "rename_write",
                        "src": src_path,
                        "dest": dst_path,
                        "content": content,
                        "tag": "~",
                        "text": f"renamed {old_rel} -> {new_rel}",
                        "stat": "renamed",
                    }
                )
                self.virtual[dst_path] = content
            else:
                moved = self._vread(src_path)
                self.ops.append(
                    {
                        "do": "rename_move",
                        "src": src_path,
                        "dest": dst_path,
                        "tag": "~",
                        "text": f"renamed {old_rel} -> {new_rel}",
                        "stat": "renamed",
                    }
                )
                self.virtual[dst_path] = moved
            self.virtual[src_path] = self.deleted_sentinel
        elif self._vexists(dst_path) and not self._vexists_any(src_path):
            self._log("=", f"{old_rel} already renamed to {new_rel}")
            self.stats["unchanged"] += 1
        else:
            self._log("!", f"skipped rename, missing source {old_rel}", "err")
            self.stats["skipped"] += 1

    def _execute(self):
        for op in self.ops:
            kind = op["do"]
            if kind == "log":
                self.tui.print_item(op["tag"], op["text"], op["kind"])
                continue
            try:
                if kind == "write":
                    op["dest"].parent.mkdir(parents=True, exist_ok=True)
                    write_file_atomic(op["dest"], op["content"])
                elif kind == "delete":
                    op["dest"].unlink()
                elif kind == "rename_move":
                    op["dest"].parent.mkdir(parents=True, exist_ok=True)
                    os.replace(op["src"], op["dest"])
                elif kind == "rename_write":
                    op["dest"].parent.mkdir(parents=True, exist_ok=True)
                    write_file_atomic(op["dest"], op["content"])
                    op["src"].unlink()
                elif kind == "mkdir":
                    op["dest"].mkdir(parents=True, exist_ok=True)
                elif kind == "rmdir":
                    shutil.rmtree(op["dest"])
                elif kind == "rename_dir":
                    op["dest"].parent.mkdir(parents=True, exist_ok=True)
                    os.replace(op["src"], op["dest"])
                self.tui.print_item(op["tag"], op["text"])
                self.stats[op["stat"]] += 1
            except OSError as e:
                self.tui.print_item("!", f"skipped {op['text']}: {e}", "err")
                self.stats["skipped"] += 1

    def _print_summary(self, elapsed):
        tui = self.tui
        stats = self.stats
        tui.print_section("OPERATION COMPLETE")
        tui.print_count("Files created", stats["created"], "ok")
        tui.print_count("Files updated", stats["updated"], "info")
        tui.print_count("Files patched", stats["patched"], "info")
        tui.print_count("Files renamed", stats["renamed"], "info")
        tui.print_count("Files deleted", stats["deleted"], "warn")
        tui.print_count("Dirs created", stats["dirs_created"], "ok")
        tui.print_count("Dirs renamed", stats["dirs_renamed"], "info")
        tui.print_count("Dirs deleted", stats["dirs_deleted"], "warn")
        tui.print_count("Files unchanged", stats["unchanged"], "dim")
        if stats["skipped"] > 0:
            tui.print_count("Files skipped", stats["skipped"], "warn")
        if stats["suspicious"] > 0:
            tui.print_info(
                "Warnings", f"{stats['suspicious']:,} file(s) look compressed", "warn"
            )
        if stats["invalid"] > 0:
            tui.print_info(
                "Syntax warnings",
                f"{stats['invalid']:,} file(s) failed validation",
                "warn",
            )
        tui.print_info("Total time", format_time(elapsed))


def main():
    desc = f"""VibeMerge v{VERSION} - A Sensible Approach to Code Merging

This is not rocket science. It merges source files intelligently,
ships them to an AI, and applies the answer back to your project.
Supports 40+ languages because that's what the job requires.

Examples:
  %(prog)s /path/to/project
  %(prog)s file1.py file2.py file3.py
  %(prog)s /path/to/project -o out.txt
  %(prog)s /path/to/project -a -s system_prompt.txt -m "fix the login bug"
  %(prog)s /path/to/project -ap
  %(prog)s /path/to/project -a --split 100000
  %(prog)s ai_response.txt -u
  %(prog)s ai_response.txt -u -o /path/to/project
    """

    parser = ArgumentParser(
        description=desc, formatter_class=RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "paths",
        nargs="+",
        help="Files or directories to merge, or merged files with -u",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file, or target directory with -u (default: <src>_merged.txt)",
    )
    parser.add_argument(
        "-i",
        "--ignore",
        metavar="NAME_OR_PATH",
        help="Ignore file name or path (gitignore style, supports ! negation), "
        "discovered at every level of the project tree (default: .gitignore)",
    )
    parser.add_argument(
        "-c",
        "--comment",
        action="store_true",
        help="Instruct the AI to add professional, standards-based comments "
        "(default: the AI is instructed to remove all comments)",
    )
    parser.add_argument(
        "-k",
        "--keep-comments",
        action="store_true",
        help="Leave comments alone: no comment instructions are sent to the AI at all",
    )
    parser.add_argument(
        "-x",
        "--clean",
        action="store_true",
        help="Delete useless junk (cache directories, compiled leftovers, OS and "
        "editor droppings) from the given directories before merging",
    )
    parser.add_argument(
        "-a",
        "--ai-format",
        action="store_true",
        help="Add the AI round-trip directive requesting a reply in mergeable VibeMerge format",
    )
    parser.add_argument(
        "-u",
        "--unmerge",
        action="store_true",
        help="Apply a merged or AI response file back onto a directory, creating, updating and deleting files",
    )
    parser.add_argument(
        "-s",
        "--system-file",
        metavar="FILE",
        help="Prepend a system prompt read from this file to the merged output",
    )
    parser.add_argument(
        "-p",
        "--prompt",
        action="store_true",
        help="Type the task interactively in the terminal, appended as a TASK block",
    )
    parser.add_argument(
        "-m",
        "--message",
        help="Append a TASK block with this text at the end of the merged output",
    )
    parser.add_argument(
        "--split",
        type=int,
        metavar="TOKENS",
        help="Split the merged output into multiple parts of about TOKENS tokens each",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {VERSION}"
    )

    args = parser.parse_args()

    if args.comment and args.keep_comments:
        parser.error("-c/--comment and -k/--keep-comments cannot be combined")

    merge_only = (
        args.comment
        or args.keep_comments
        or args.clean
        or args.ai_format
        or args.ignore
        or args.system_file
        or args.prompt
        or args.message
        or args.split
    )
    if args.unmerge and merge_only:
        parser.error(
            "-u/--unmerge cannot be combined with "
            "-c, -k, -x, -a, -s, -p, -i, -m or --split"
        )

    if args.split is not None and args.split <= 0:
        parser.error("--split must be a positive number of tokens")

    try:
        if args.unmerge:
            ApplyEngine(args.paths, args.output, args.quiet).run()
        else:
            MergeEngine(
                args.paths,
                args.output,
                args.ignore,
                args.comment,
                args.keep_comments,
                args.ai_format,
                args.quiet,
                args.system_file,
                args.message,
                args.split,
                args.prompt,
                args.clean,
            ).run()
        return 0

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user", file=sys.stderr)
        return 130

    except Exception as e:
        theme = Theme(sys.stderr)
        print("\n" + theme.paint(f"Error: {e}", "err"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
