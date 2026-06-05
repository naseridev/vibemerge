# VibeMerge

A high-performance code merging utility for consolidating source files into a single output file, shipping them to an AI, and applying the AI's answer back onto the project. Built for efficiency and reliability.

## Overview

VibeMerge is designed to aggregate codebases efficiently. It merges every text file in a project regardless of language, and offers a full AI round-trip workflow: merge, ask, and apply. The apply step can create new files, replace or patch existing ones, rename or move files, and delete files the AI marks for removal, and it is atomic: an incomplete reply applies nothing.

## Features

- Merges every text file type, with binary files detected and skipped automatically
- AI round-trip workflow: merge with a format directive, apply the AI reply back automatically
- Full apply support: creates new files, replaces changed files, applies partial `PATCH:` hunks, renames files and directories with `RENAME:`, deletes files with `DELETE:`, and gives directories their own CRUD with `MKDIR:` and `RMDIR:`
- Partial patches: files with small changes arrive as exact search and replace hunks instead of full copies; the 60 percent rule is applied per file, so one reply freely mixes complete files and patches
- Atomic apply: every reply is parsed, validated and fully staged in memory first; a missing `END OF REPLY` marker or any failing patch hunk means nothing is written
- Duplicate elimination in merged output: identical files are written once under stacked headers, and a duplicate note is added to the AI directive whenever that happens
- Interactive task entry with `-p`, typed directly in the terminal
- Junk cleanup with `-x`: cache directories, compiled leftovers and OS or editor droppings are deleted from the project before merging, with `.git` always protected
- Gitignore handling that works like git: `.gitignore` files are discovered at every level of the tree by default, each scoped to its own subtree with last-match-wins semantics, and `-i` swaps in any other ignore file name or path
- Project structure tree embedded in `-a` output so the AI understands the layout
- Task embedding with `-m` (inline) or `-p` (interactive or piped stdin): the request travels inside the merged file
- Output splitting with `--split` for projects larger than the model context window
- Truncated reply rejection via a mandatory `END OF REPLY` marker, written at the end of every merged part as well
- Post-apply syntax validation for Python and JSON files (warn-only)
- Version control warning when applying onto a directory that is not under git
- Token count estimate for every merged output
- Custom system prompt injection: `-s` prepends any prompt file you provide, nothing is hardcoded; prompt files that live inside the merged tree are excluded from the merge automatically
- Automatic project root detection when applying replies, from any working directory
- Terminal output with a semantic color system: green only for completed additions, cyan for content changes, yellow for destructive or cautionary results, red strictly for errors, dim for structure and no-ops, and zero counts always dimmed
- Comment policy control: by default the AI is instructed to remove all comments, `-c` switches to professional standards-based commenting, and `-k` says nothing about comments at all
- Scope discipline baked into the directive: the AI is told to do only the task and never produce unrequested markdown files, reports or other documentation
- Intelligent text file detection and duplicate elimination
- Automatic exclusion of the output file and of the script itself from scans
- Memory-mapped I/O for large files
- Safe apply mode with path traversal protection
- Hardened error handling: every failure produces a clear one-line message, never a crash or traceback
- Progress tracking and detailed statistics

## Installation

Clone the repository and ensure Python 3.7+ is installed:

```bash
git clone https://github.com/naseridev/vibemerge.git
```

```bash
cd vibemerge
```

```bash
chmod +x vmrg.py
```

## Usage

### Basic Syntax

```bash
./vmrg.py [OPTIONS] PATH [PATH ...]
```

### Examples

Merge all files in a directory (output: project_merged.txt):

```bash
./vmrg.py /path/to/project
```

Merge specific files:

```bash
./vmrg.py file1.py file2.py file3.py
```

Merge with custom output:

```bash
./vmrg.py /path/to/project -o output.txt
```

Use a custom ignore file instead of the default .gitignore:

```bash
./vmrg.py /path/to/project -i .vmignore -o output.txt
```

Merge for an AI round trip with a custom system prompt file:

```bash
./vmrg.py /path/to/project -a -s system_prompt.txt
```

Apply an AI response back onto the project, letting VibeMerge detect the project root automatically:

```bash
./vmrg.py ai_response.txt -u
```

Apply an AI response onto an explicit directory:

```bash
./vmrg.py ai_response.txt -u -o /path/to/project
```

Embed the task inside the merged file:

```bash
./vmrg.py /path/to/project -a -m "fix the login bug"
```

Type the task interactively in the terminal:

```bash
./vmrg.py /path/to/project -ap
```

Split a large project into parts of about 100k tokens:

```bash
./vmrg.py /path/to/project -a --split 100000
```

Combine multiple options:

```bash
./vmrg.py /path/to/project -ko output.txt -i .vmignore
```

## Options

| Option | Description |
|--------|-------------|
| `-o, --output` | Output file path for merging (default: `<src>_merged.txt`), or target directory for `-u` |
| `-i, --ignore NAME_OR_PATH` | Ignore file name or path (gitignore style, supports `!` negation), discovered at every level of the project tree; default: `.gitignore` |
| `-c, --comment` | Instruct the AI to add professional, standards-based comments: explain why rather than what, document public APIs in the language's standard format, no commented-out code or noise |
| `-k, --keep-comments` | Send no comment instructions to the AI at all, leaving its comment behavior untouched |
| `-x, --clean` | Delete useless junk from the given directories before merging: `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache` directories and `.DS_Store`, `Thumbs.db`, `desktop.ini`, `*.pyc`, `*.pyo`, `*.swp`, `*.swo`, `*.orig`, `*.rej` and `*~` files; `.git` is never touched |
| `-a, --ai-format` | Add the AI round-trip directive requesting a reply in mergeable VibeMerge format, containing only the files that need to be created, modified, patched, renamed or deleted |
| `-s, --system-file FILE` | Prepend a system prompt read from the given file to the merged output, before all other directives |
| `-p, --prompt` | Type the task interactively in the terminal (finish with an empty line), or pipe it in via stdin; the text is appended as a `TASK` block and combines with `-m` |
| `-m, --message` | Append a `TASK` block with the given text at the end of the merged output |
| `--split TOKENS` | Split the merged output into multiple part files of about `TOKENS` tokens each |
| `-u, --unmerge` | Apply a merged or AI response file back onto a directory, creating, updating and deleting files, auto-detecting the project root when `-o` is omitted |
| `-q, --quiet` | Suppress progress output |
| `-v, --version` | Display version information |

The default output file is named after the first input path: merging `/path/to/project` produces `project_merged.txt` and merging `main.py` produces `main_merged.txt`, created in the current working directory. With `--split`, the parts are named `<base>_merged_part1.txt`, `<base>_merged_part2.txt` and so on; part 1 carries the directives and the project tree, later parts carry a short continuation directive, and the `TASK` block is written at the end of the last part. By default every merged output carries a comment policy instructing the AI to strip all comments; `-c` replaces it with the professional commenting policy and `-k` omits it entirely. `-c` and `-k` cannot be combined, and the mode `-u` cannot be combined with `-c`, `-k`, `-x`, `-a`, `-s`, `-p`, `-i`, `-m` or `--split`. The file given to `-s` is never included in the merge, even when it lives inside the scanned directories, and previously generated split parts are skipped as well.

## AI Round-Trip Workflow

1. Merge the project with the `-a` flag. The output starts with a directive instructing the AI to answer in the exact VibeMerge format, never minified, with no markdown fences or commentary, sending complete files for large changes and exact search and replace patches for small ones, to include only the files that actually need to be created, modified, renamed or deleted, to mark deletions with `DELETE:` and renames with `RENAME:`, to keep all related imports and references consistent, to answer `NO CHANGES REQUIRED` when nothing needs to change, to do only what the task asks without producing unrequested documentation, reports or markdown files, and to always finish with an `END OF REPLY` line. A project structure tree is embedded after the directives. Combine with `-s` to prepend your own system prompt from a file, and with `-m` or `-p` to embed the task itself so the whole request is a single paste.

```bash
./vmrg.py /path/to/project -a -s system_prompt.txt -m "fix the login bug"
```

2. Paste `project_merged.txt` into the AI and save the reply to a file, for example `ai_response.txt`. If the project does not fit in the model context window, use `--split` and paste the parts in order.

3. Apply the reply. With no `-o`, VibeMerge inspects the relative paths inside the reply and locates the matching project root on its own, searching the current directory, its ancestors, the directories around the response file, and their immediate subdirectories. If no directory on disk matches the files in the reply, it stops with a clear error instead of writing to the wrong place.

```bash
./vmrg.py ai_response.txt -u
```

Apply mode changes files in place, so keep the project under version control or make your own copy before applying a reply.

### Reply Format

A created file, or an existing file where more than about 60 percent of the content changes, is written as a complete file under a `FILE:` header:

```
--------------------------------------------------------------------------------
FILE: src/main.py
--------------------------------------------------------------------------------
[complete file content]
```

An existing file with smaller changes is patched in place with a `PATCH:` header carrying one or more search and replace hunks. The SEARCH lines must be copied verbatim from the file, must match exactly one place, and hunks are written in top to bottom order; an empty REPLACE part deletes the SEARCH lines:

```
--------------------------------------------------------------------------------
PATCH: src/main.py
--------------------------------------------------------------------------------
<<<<<<< SEARCH
def greet(name):
    return f"hello {name}"
=======
def greet(name):
    return f"hi {name}"
>>>>>>> REPLACE
```

Directories have their own operations. `MKDIR:` creates an empty directory (directories of `FILE:` paths are created automatically, so it exists only for directories that must exist while still empty), `RMDIR:` removes a directory and everything inside it, and `RENAME:` moves a directory with all of its contents when given a directory path; a directory rename must have an empty body:

```
--------------------------------------------------------------------------------
MKDIR: assets/images
--------------------------------------------------------------------------------
--------------------------------------------------------------------------------
RMDIR: src/legacy
--------------------------------------------------------------------------------
--------------------------------------------------------------------------------
RENAME: src/old_module -> src/core
--------------------------------------------------------------------------------
```

Several files that must receive exactly identical content are written once, as stacked `FILE:` headers directly above a single body; the merge side uses the same form for duplicate files and adds a duplicate note to the directive whenever it does:

```
--------------------------------------------------------------------------------
FILE: conf/a.py
--------------------------------------------------------------------------------
--------------------------------------------------------------------------------
FILE: conf/b.py
--------------------------------------------------------------------------------
[shared content]
```

A file to be removed is marked with a `DELETE:` header with nothing after it:

```
--------------------------------------------------------------------------------
DELETE: src/old_module.py
--------------------------------------------------------------------------------
```

A file to be renamed or moved uses a `RENAME:` header with both paths. An empty body moves the file unchanged; a non-empty body moves it and replaces its content in one step:

```
--------------------------------------------------------------------------------
RENAME: src/helper.py -> src/utils/helper.py
--------------------------------------------------------------------------------
```

A reply that changes nothing is the single line `NO CHANGES REQUIRED`, and every reply ends with the single line `END OF REPLY`. The marker is mandatory: a reply without it is rejected as incomplete and nothing at all is applied.

### Apply Mode Behavior

- Detects the real project root automatically when `-o` is omitted, and errors out if it cannot be detected
- Parses `FILE:`, `PATCH:`, `DELETE:`, `RENAME:`, `MKDIR:` and `RMDIR:` sections delimited by dash lines; falls back to bare header lines if the AI omitted the dashes
- Applies atomically in two phases: every section is parsed, checked and staged against an in-memory view of the project first, and files are only written once the whole reply has staged cleanly, so sections may build on each other (create then patch, rename a directory then patch a file under its new path, remove a directory then recreate files inside it) within one reply, executed strictly in the order they appear
- Rejects a reply that is missing its `END OF REPLY` marker before writing anything, since that means the AI output was cut off
- Aborts the entire apply, writing nothing, when any patch hunk does not match, matches more than one place, targets a missing file, or is malformed
- Warns when a patch covers more than 60 percent of a file, since the directive requires a full FILE section in that case
- Treats a `NO CHANGES REQUIRED` reply as a successful no-op instead of an error
- Headers and `END OF REPLY` lines inside markdown code fences are treated as content, not as instructions
- Warns when the target directory is not under version control, since apply mode changes files in place
- Strips a surrounding markdown code fence around the whole reply and around individual file bodies
- Ignores any commentary before the first file header
- Streams a live, colored per-item log while applying: `+` created (files and dirs), `~` updated, patched or renamed, `-` deleted files and removed dirs, `=` unchanged, already absent or already renamed, `!` skipped or warning
- Writes complete files with UTF-8 encoding and LF line endings, creating directories as needed
- Skips files whose content is identical to what is already on disk
- Deletes only regular files; a `DELETE:` for a path that does not exist is reported as already absent, and a `DELETE:` for a directory is skipped
- Renames preserve file bytes exactly when the body is empty; a `RENAME:` whose source is missing but whose destination exists is reported as already renamed
- Directory operations are guarded: `MKDIR` on an existing directory and `RMDIR` on a missing one are no-ops, a path conflict with a file is skipped, a directory rename refuses to carry content or to overwrite an existing destination, and `RMDIR` is the only recursive operation
- Validates applied Python files with `ast.parse` and JSON files with `json.loads`, reporting syntax warnings without blocking the apply
- Rejects absolute paths, drive letters, `..` components and anything that would resolve outside the target directory, for every section type including `MKDIR:`, `RMDIR:` and both sides of `RENAME:`
- Warns when an applied file looks minified, since AI replies must always use normal formatting

## Ignore Patterns

Ignoring is always on and searches the whole project tree. By default every `.gitignore` file found at any level of the scanned directories is loaded, and each one's patterns apply only to its own subtree, exactly like git: rules from deeper ignore files are evaluated after rules from outer ones, so the last matching pattern wins and a nested `!` negation can re-include something an outer file excluded.

Passing `-i` changes which ignore file is used instead of `.gitignore`. A bare name such as `-i .vmignore` is discovered at every level of the tree just like the default; a path to an existing file such as `-i ../shared.ignore` is loaded once and applied globally from the root of every scanned directory, while files with the same name inside the tree are still discovered and scoped to their own directories.

Ignore files use gitignore-style patterns to exclude specific files or directories. Lines starting with `#` are comments, a trailing `/` marks a directory, and `!` re-includes a previously excluded path. The last matching pattern wins. Matching directories are pruned during the scan, so excluded trees are never walked. As in git, a file cannot be re-included if one of its parent directories is excluded.

```
node_modules
*.log
build/*
!build/keep.txt
dist/
__pycache__
```

## Performance Considerations

- Files are processed sequentially and streamed to disk as they are read
- Maximum file size: 1 GB per file
- Maximum total size: 1 GB per merge
- Memory-mapped I/O used for files larger than 256 KB
- Progress bars render only on interactive terminals and stay silent in pipes and CI logs

## Terminal Output

VibeMerge ships a clean, scrollable terminal interface. Every operation opens with a framed phase header carrying the run details, streams the work live line by line, and closes with a framed summary block:

```
--------------------------------------------------------------------------------
APPLYING FILES:
--------------------------------------------------------------------------------

Detected root....... /home/edward/Desktop/solutik-backend/source/app (85 matched)
Target directory.... /home/edward/Desktop/solutik-backend/source/app
Sections found...... 85 in app_merged_persian.txt

  ~ updated app/api/routes.py
  ~ patched app/api/auth.py (2 hunk(s))
  + created app/api/health.py
  ~ renamed app/api/legacy.py -> app/api/v1/legacy.py
  ~ renamed dir app/v1/ -> app/api/v1/
  - deleted app/api/deprecated.py
  = app/core/config.py unchanged

--------------------------------------------------------------------------------
OPERATION COMPLETE
--------------------------------------------------------------------------------

Files created....... 1
Files patched....... 1
Files renamed....... 1
Files deleted....... 1
Dirs renamed........ 1
Files unchanged..... 1
Total time.......... 0.04s
```

The terminal is never cleared, so the full history of every run stays scrollable. Colors come from a single semantic theme with fixed meanings: green marks successful additions, cyan marks informational content changes and detected values, yellow marks destructive results and warnings, red is reserved for errors and skips, and dim gray carries structure, labels and no-ops. Counters in the summary are colored only when they are non-zero, so a quiet run stays visually quiet. Colors are enabled only on interactive terminals and are disabled automatically in pipes, in CI, when `NO_COLOR` is set, or when `TERM` is `dumb`. Errors are reported as a single friendly red line; VibeMerge never prints a stack trace.

## Output Format

Each merged file includes a header with the relative path, identical files share one body under stacked headers, and every merged file or part ends with the `END OF REPLY` line so it passes the same completeness check as an AI reply:

```
--------------------------------------------------------------------------------
FILE: src/main.py
--------------------------------------------------------------------------------
[file content]
```

## Exit Codes

- 0: Success
- 1: Fatal error
- 2: Invalid command line usage
- 130: User interruption

## Requirements

- Python 3.7 or higher
- No external dependencies required

## Contributing

Contributions are welcome. Submit pull requests with clear descriptions and test coverage.

## Support

For issues or questions, open an issue on the GitHub repository.