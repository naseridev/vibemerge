#!/usr/bin/env python3

import os
import sys
import time
import mmap
import shutil
from pathlib import Path
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from fnmatch import fnmatch
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from functools import lru_cache
from collections import deque
import threading


VERSION = "4.0.0"
DEFAULT_OUTPUT = "vibemerged.txt"
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_TOTAL_SIZE = 1024 * 1024 * 1024
CHUNK_SIZE = 256 * 1024
MIN_PARALLEL_FILES = 4


LANGUAGE_CONFIGS = {
    '.py': {'strings': [(b'"""', b'"""'), (b"'''", b"'''"), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'#', b'\n')]},
    '.js': {'strings': [(b'`', b'`'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.ts': {'strings': [(b'`', b'`'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.jsx': {'strings': [(b'`', b'`'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.tsx': {'strings': [(b'`', b'`'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.java': {'strings': [(b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.c': {'strings': [(b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.cpp': {'strings': [(b'"', b'"'), (b"'", b"'"), (b'R"(', b')"')], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.cc': {'strings': [(b'"', b'"'), (b"'", b"'"), (b'R"(', b')"')], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.h': {'strings': [(b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.hpp': {'strings': [(b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.cs': {'strings': [(b'@"', b'"'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.go': {'strings': [(b'`', b'`'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.rs': {'strings': [(b'r#"', b'"#'), (b'r"', b'"'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.php': {'strings': [(b'<<<', b''), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/'), (b'#', b'\n')]},
    '.rb': {'strings': [(b'%Q{', b'}'), (b'%q{', b'}'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'#', b'\n'), (b'=begin', b'=end')]},
    '.swift': {'strings': [(b'"""', b'"""'), (b'"', b'"')], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.kt': {'strings': [(b'"""', b'"""'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.scala': {'strings': [(b'"""', b'"""'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.lua': {'strings': [(b'[[', b']]'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'--', b'\n')]},
    '.pl': {'strings': [(b'q{', b'}'), (b'qq{', b'}'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'#', b'\n')]},
    '.r': {'strings': [(b'"', b'"'), (b"'", b"'")], 'comments': [(b'#', b'\n')]},
    '.m': {'strings': [(b'@"', b'"'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.sql': {'strings': [(b'"', b'"'), (b"'", b"'")], 'comments': [(b'--', b'\n'), (b'/*', b'*/')]},
    '.sh': {'strings': [(b'"', b'"'), (b"'", b"'")], 'comments': [(b'#', b'\n')]},
    '.bash': {'strings': [(b'"', b'"'), (b"'", b"'")], 'comments': [(b'#', b'\n')]},
    '.vim': {'strings': [(b'"', b'"'), (b"'", b"'")], 'comments': [(b'"', b'\n')]},
    '.dart': {'strings': [(b'"""', b'"""'), (b"'''", b"'''"), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.ex': {'strings': [(b'"""', b'"""'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'#', b'\n')]},
    '.exs': {'strings': [(b'"""', b'"""'), (b'"', b'"'), (b"'", b"'")], 'comments': [(b'#', b'\n')]},
    '.erl': {'strings': [(b'"', b'"')], 'comments': [(b'%', b'\n')]},
    '.clj': {'strings': [(b'"', b'"')], 'comments': [(b';', b'\n')]},
    '.lisp': {'strings': [(b'"', b'"')], 'comments': [(b';', b'\n')]},
    '.hs': {'strings': [(b'"', b'"')], 'comments': [(b'--', b'\n'), (b'{-', b'-}')]},
    '.ml': {'strings': [(b'"', b'"')], 'comments': [(b'(*', b'*)')]},
    '.fs': {'strings': [(b'"""', b'"""'), (b'"', b'"')], 'comments': [(b'//', b'\n'), (b'(*', b'*)')]},
    '.nim': {'strings': [(b'"""', b'"""'), (b'"', b'"')], 'comments': [(b'#', b'\n')]},
    '.cr': {'strings': [(b'"', b'"'), (b"'", b"'")], 'comments': [(b'#', b'\n')]},
    '.v': {'strings': [(b'"', b'"'), (b"'", b"'")], 'comments': [(b'//', b'\n'), (b'/*', b'*/')]},
    '.zig': {'strings': [(b'"', b'"')], 'comments': [(b'//', b'\n')]},
}


def format_bytes(size):
    units = ['B', 'KB', 'MB', 'GB', 'TB']
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


class TUI:
    def __init__(self, quiet=False):
        self.quiet = quiet
        self.term_width = shutil.get_terminal_size((80, 24))[0]
        self.lock = threading.Lock()

    def clear_line(self):
        if not self.quiet:
            sys.stdout.write('\r' + ' ' * self.term_width + '\r')
            sys.stdout.flush()

    def print_header(self, text):
        if self.quiet:
            return
        width = min(self.term_width, 80)
        print('=' * width)
        print(text.center(width))
        print('=' * width)

    def print_section(self, text):
        if self.quiet:
            return
        width = min(self.term_width, 80)
        print()
        print('-' * width)
        print(text)
        print('-' * width)
        print()

    def print_info(self, label, value):
        if not self.quiet:
            print(f"{label:.<20} {value}")

    def progress_bar(self, current, total, prefix='', width=40):
        if self.quiet or total == 0:
            return

        with self.lock:
            percent = current / total
            filled = int(width * percent)
            bar = '#' * filled + '-' * (width - filled)
            percent_str = f"{int(percent * 100)}%"

            display = f"\r{prefix} [{bar}] {percent_str} ({current}/{total})"

            sys.stdout.write(display[:self.term_width])
            sys.stdout.flush()

            if current >= total:
                print()


class ProgressTracker:
    def __init__(self, total, prefix="", tui=None):
        self.total = total
        self.prefix = prefix
        self.tui = tui
        self.current = 0
        self.lock = threading.Lock()
        self.start_time = time.time()

    def update(self, increment=1):
        if not self.tui or self.tui.quiet:
            return

        with self.lock:
            self.current += increment
            self.tui.progress_bar(self.current, self.total, self.prefix)

    def finish(self):
        if self.tui and not self.tui.quiet:
            elapsed = time.time() - self.start_time
            self.tui.print_info("Time elapsed", format_time(elapsed))


@lru_cache(maxsize=128)
def load_patterns(path):
    if not Path(path).exists():
        return tuple()
    patterns = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
    return tuple(patterns)


def should_ignore(filepath, basedir, patterns):
    if not patterns:
        return False
    rel = str(filepath.relative_to(basedir))
    name = filepath.name
    for p in patterns:
        if fnmatch(name, p) or fnmatch(rel, p):
            return True
    return False


def is_text(filepath):
    try:
        stat = filepath.stat()
        if stat.st_size == 0 or stat.st_size > MAX_FILE_SIZE:
            return False

        with open(filepath, 'rb') as f:
            if stat.st_size < 1024:
                return b'\x00' not in f.read()
            else:
                try:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        sample = mm[:min(8192, len(mm))]
                        return b'\x00' not in sample
                except:
                    return b'\x00' not in f.read(8192)
    except:
        return False


def compress_code(content_bytes, ext):
    config = LANGUAGE_CONFIGS.get(ext, {'strings': [(b'"', b'"'), (b"'", b"'")], 'comments': []})

    result = bytearray()
    i = 0
    n = len(content_bytes)
    whitespace = frozenset([32, 9, 10, 13])

    while i < n:
        ch = content_bytes[i]

        if ch == 92 and i + 1 < n:
            result.append(ch)
            result.append(content_bytes[i + 1])
            i += 2
            continue

        found_string = False
        for start_delim, end_delim in config['strings']:
            delim_len = len(start_delim)
            if i + delim_len <= n and content_bytes[i:i+delim_len] == start_delim:
                result.extend(start_delim)
                i += delim_len

                end_len = len(end_delim) if end_delim else 0

                if not end_delim:
                    while i < n and content_bytes[i] not in (10, 13):
                        result.append(content_bytes[i])
                        i += 1
                else:
                    while i + end_len <= n:
                        if content_bytes[i:i+end_len] == end_delim:
                            result.extend(end_delim)
                            i += end_len
                            break

                        if content_bytes[i] == 92 and i + 1 < n:
                            result.append(content_bytes[i])
                            result.append(content_bytes[i + 1])
                            i += 2
                            continue

                        result.append(content_bytes[i])
                        i += 1

                found_string = True
                break

        if found_string:
            continue

        if ch in whitespace:
            i += 1
            continue

        result.append(ch)
        i += 1

    return bytes(result)


def read_file(filepath):
    try:
        stat = filepath.stat()
        size = stat.st_size

        if size == 0:
            return b''

        with open(filepath, 'rb') as f:
            if size < CHUNK_SIZE:
                return f.read()
            else:
                try:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        return bytes(mm)
                except:
                    return f.read()
    except:
        return None


def process_file_worker(args):
    fpath, basedir, compress = args

    try:
        content_bytes = read_file(fpath)
        if content_bytes is None:
            return None

        ext = fpath.suffix.lower()

        if compress:
            processed = compress_code(content_bytes, ext)
            compressed_size = len(processed)
        else:
            processed = content_bytes
            compressed_size = 0

        try:
            content_str = processed.decode('utf-8')
        except UnicodeDecodeError:
            content_str = processed.decode('utf-8', errors='replace')

        lines = content_str.count('\n') + 1

        try:
            rel = fpath.relative_to(basedir)
        except (ValueError, TypeError):
            rel = fpath.name

        header = f"{'-' * 80}\nFILE: {rel}\n{'-' * 80}\n\n"

        return {
            'content': content_str,
            'header': header,
            'lines': lines,
            'size': len(content_bytes),
            'compressed_size': compressed_size
        }
    except Exception as e:
        return None


def resolve_paths(paths):
    resolved_files = []
    resolved_dirs = []

    for path_str in paths:
        path = Path(path_str).resolve()

        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")

        if path.is_file():
            resolved_files.append(path)
        elif path.is_dir():
            resolved_dirs.append(path)
        else:
            raise ValueError(f"Invalid path type: {path}")

    return resolved_files, resolved_dirs


def collect_files_from_dirs(directories, patterns, tui):
    all_paths = deque()

    for directory in directories:
        for root, dirs, filenames in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in filenames:
                if not filename.startswith('.'):
                    all_paths.append((Path(root) / filename, directory))

    if not tui.quiet:
        tui.print_info("Scanning directories", f"{len(directories)}")

    tui.print_section("SCANNING FILES")
    tui.print_info("Total files found", f"{len(all_paths):,}")

    tracker = ProgressTracker(len(all_paths), "Scanning", tui)

    valid_files = []
    total = 0

    for fpath, basedir in all_paths:
        tracker.update()

        if not fpath.is_file():
            continue
        if should_ignore(fpath, basedir, patterns):
            continue
        if not is_text(fpath):
            continue

        try:
            fsize = fpath.stat().st_size
        except:
            continue

        if total + fsize > MAX_TOTAL_SIZE:
            tui.print_info("Warning", "Size limit reached")
            break

        total += fsize
        valid_files.append((fpath, Path(basedir)))

    tracker.finish()
    return valid_files, total

def collect_files(input_files, directories, patterns, tui):
    files = []
    total = 0

    if input_files:
        tui.print_section("VALIDATING FILES")
        tui.print_info("Input files", f"{len(input_files):,}")

        tracker = ProgressTracker(len(input_files), "Validating", tui)

        for fpath in input_files:
            tracker.update()

            if not fpath.is_file():
                continue
            if not is_text(fpath):
                continue

            try:
                fsize = fpath.stat().st_size
            except:
                continue

            if total + fsize > MAX_TOTAL_SIZE:
                tui.print_info("Warning", "Size limit reached")
                break

            total += fsize
            files.append((fpath, fpath.parent))

        tracker.finish()

    if directories:
        dir_files, dir_size = collect_files_from_dirs(directories, patterns, tui)

        if total + dir_size > MAX_TOTAL_SIZE:
            remaining = MAX_TOTAL_SIZE - total
            accumulated = 0
            for fpath, basedir in dir_files:
                fsize = fpath.stat().st_size
                if accumulated + fsize > remaining:
                    break
                files.append((fpath, basedir))
                accumulated += fsize
            total += accumulated
        else:
            files.extend(dir_files)
            total += dir_size

    return sorted(files, key=lambda x: x[0]), total


def merge_files(paths, output, ignore, compress, no_comment, quiet, parallel):
    tui = TUI(quiet)

    input_files, directories = resolve_paths(paths)

    if not input_files and not directories:
        raise ValueError("No valid files or directories provided")

    patterns = load_patterns(ignore) if ignore else tuple()

    operation_start = time.time()

    files, total_size = collect_files(input_files, directories, patterns, tui)

    if not files:
        raise ValueError("No valid files found")

    if output:
        outpath = Path(output).resolve()
    else:
        outpath = Path.cwd() / DEFAULT_OUTPUT

    outpath.parent.mkdir(parents=True, exist_ok=True)

    num_cpus = cpu_count()
    use_parallel = parallel and len(files) >= MIN_PARALLEL_FILES and num_cpus > 1

    tui.print_section("PROCESSING FILES")
    tui.print_info("Valid files", f"{len(files):,}")
    tui.print_info("Total size", format_bytes(total_size))
    tui.print_info("Processing mode", f"Parallel ({num_cpus} CPUs)" if use_parallel else "Sequential")
    if compress:
        tui.print_info("Compression", "Enabled")
    if no_comment:
        tui.print_info("No comments", "Enabled")

    print()

    merge_start = time.time()
    compressed_size = 0
    total_lines = 0

    with open(outpath, 'w', encoding='utf-8', buffering=CHUNK_SIZE) as out:
        if compress:
            out.write("=" * 80 + "\n")
            out.write("SYSTEM INSTRUCTION FOR AI\n")
            out.write("This code has been compressed to reduce token usage.\n")
            out.write("When generating responses or code:\n")
            out.write("- Write code in normal, readable format with proper spacing\n")
            out.write("- Use standard indentation and line breaks\n")
            out.write("- Follow conventional formatting practices\n")
            out.write("- DO NOT compress or minify your output\n")
            out.write("=" * 80 + "\n\n")

        if no_comment:
            out.write("=" * 80 + "\n")
            out.write("SYSTEM INSTRUCTION FOR AI\n")
            out.write("When generating code:\n")
            out.write("- DO NOT add comments or docstrings\n")
            out.write("- Provide clean, production-ready code only\n")
            out.write("- Focus on functionality, not documentation\n")
            out.write("=" * 80 + "\n\n")

        if use_parallel:
            results = [None] * len(files)
            tracker = ProgressTracker(len(files), "Processing", tui)

            with ProcessPoolExecutor(max_workers=num_cpus) as executor:
                futures = {
                    executor.submit(process_file_worker, (fpath, basedir, compress)): i
                    for i, (fpath, basedir) in enumerate(files)
                }

                for future in as_completed(futures):
                    idx = futures[future]
                    result = future.result()
                    if result:
                        results[idx] = result
                    tracker.update()

            tracker.finish()

            write_start = time.time()
            write_tracker = ProgressTracker(len(results), "Writing", tui)

            for i, result in enumerate(results):
                write_tracker.update()

                if result is None:
                    continue

                if i > 0:
                    out.write('\n\n')

                out.write(result['header'])
                out.write(result['content'])

                total_lines += result['lines']
                if compress:
                    compressed_size += result['compressed_size']

            write_tracker.finish()

        else:
            tracker = ProgressTracker(len(files), "Merging", tui)

            for i, (fpath, basedir) in enumerate(files):
                tracker.update()

                if i > 0:
                    out.write('\n\n')

                try:
                    rel = fpath.relative_to(basedir)
                except (ValueError, TypeError):
                    rel = fpath.name

                out.write(f"FILE: {rel}\n")
                out.write(f"{'-' * 80}\n\n")

                content_bytes = read_file(fpath)
                if content_bytes is None:
                    continue

                if compress:
                    ext = fpath.suffix.lower()
                    processed = compress_code(content_bytes, ext)
                    compressed_size += len(processed)
                    try:
                        content = processed.decode('utf-8')
                    except UnicodeDecodeError:
                        content = processed.decode('utf-8', errors='replace')
                else:
                    try:
                        content = content_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        content = content_bytes.decode('utf-8', errors='replace')

                total_lines += content.count('\n') + 1
                out.write(content.rstrip())

            tracker.finish()

    merge_elapsed = time.time() - merge_start
    total_elapsed = time.time() - operation_start

    tui.print_section("OPERATION COMPLETE")
    tui.print_info("Total files", f"{len(files):,}")
    tui.print_info("Total lines", f"{total_lines:,}")

    if compress:
        tui.print_info("Original size", format_bytes(total_size))
        tui.print_info("Compressed size", format_bytes(compressed_size))
        reduction = ((total_size - compressed_size) / total_size * 100) if total_size > 0 else 0
        tui.print_info("Reduction", f"{reduction:.1f}%")
    else:
        tui.print_info("Total size", format_bytes(total_size))

    tui.print_info("Merge time", format_time(merge_elapsed))
    tui.print_info("Total time", format_time(total_elapsed))
    tui.print_info("Output file", str(outpath))

    if use_parallel:
        throughput = total_size / merge_elapsed if merge_elapsed > 0 else 0
        tui.print_info("Throughput", f"{format_bytes(throughput)}/s")

    return outpath, len(files), total_size, compressed_size if compress else 0, total_lines


def main():
    desc = f"""VibeMerge v{VERSION} - A Sensible Approach to Code Merging

This is not rocket science. It merges source files intelligently.
No corporate buzzwords, no unnecessary abstraction layers.
Supports 40+ languages because that's what the job requires.

Examples:
  %(prog)s /path/to/project
  %(prog)s file1.py file2.py file3.py
  %(prog)s /path/to/dir file1.py file2.py
  %(prog)s /path/to/project -o out.txt -p
  %(prog)s file.py -cd
  %(prog)s /path/to/project -cdpo out.txt -i .gitignore
    """

    parser = ArgumentParser(
        description=desc,
        formatter_class=RawDescriptionHelpFormatter
    )

    parser.add_argument('paths', nargs='+', help='Files or directories to merge')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('-i', '--ignore', help='Ignore patterns file')
    parser.add_argument('-c', '--compress', action='store_true',
                       help='Compress whitespace')
    parser.add_argument('-d', '--dont-comment', action='store_true',
                       help='Add AI no-comment directive')
    parser.add_argument('-p', '--parallel', action='store_true',
                       help='Enable parallel processing')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='Quiet mode')
    parser.add_argument('-v', '--version', action='version',
                       version=f'%(prog)s {VERSION}')

    args = parser.parse_args()

    try:
        merge_files(
            args.paths,
            args.output,
            args.ignore,
            args.compress,
            args.dont_comment,
            args.quiet,
            args.parallel
        )
        return 0

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user", file=sys.stderr)
        return 130

    except Exception as e:
        print(f"\nFatal error: {e}", file=sys.stderr)
        if not args.quiet:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
