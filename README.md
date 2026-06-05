# VibeMerge

A high-performance code merging utility for consolidating source files from multiple languages into a single output file, shipping them to an AI, and applying the AI's answer back onto the project. Built for efficiency and scalability.

## Overview

VibeMerge is designed to aggregate codebases efficiently. It supports over 70 file types across systems and web languages, provides optional semantics-preserving compression with comment stripping, and offers a full AI round-trip workflow: merge, ask, and apply. The apply step can create new files, replace or patch existing ones, rename or move files, and delete files the AI marks for removal, and it is atomic: an incomplete reply applies nothing.

## Features

- Multi-language support for 70+ file types, including the complete web stack
- AI round-trip workflow: merge with a format directive, apply the AI reply back automatically
- Full apply support: creates new files, replaces changed files, applies partial `PATCH:` hunks, renames files marked with `RENAME:`, and deletes files marked with `DELETE:`
- Partial patches: files with small changes arrive as exact search and replace hunks instead of full copies, with a 60 percent rule for when the AI must send the whole file
- Atomic apply: every reply is parsed, validated and fully staged in memory first; a missing `END OF REPLY` marker or any failing patch hunk means nothing is written
- Duplicate elimination in merged output: identical files are written once under stacked headers, and a duplicate note is added to the AI directive whenever that happens
- Interactive task entry with `-p`, typed directly in the terminal
- Automatic `.gitignore` loading from the root of every scanned directory, no flag required
- Project structure tree embedded in `-a` output so the AI understands the layout
- Task embedding with `-m`/`--prompt-file`: the request travels inside the merged file
- Output splitting with `--split` for projects larger than the model context window
- Truncated reply rejection via a mandatory `END OF REPLY` marker, written at the end of every merged part as well
- Post-apply syntax validation for Python and JSON files (warn-only)
- Version control warning when applying onto a directory that is not under git
- Token count estimate for every merged output
- Custom system prompt injection: `-s` prepends any prompt file you provide, nothing is hardcoded; prompt files that live inside the merged tree are excluded from the merge automatically
- Automatic project root detection when applying replies, from any working directory
- Semantics-preserving compression: collapses whitespace, preserves indentation and line structure, strips comments
- Language-aware lexing for JavaScript regex literals, nested template literals, and PHP heredoc/nowdoc
- Gitignore-style filtering with negation patterns and directory pruning
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

Enable compression:

```bash
./vmrg.py /path/to/project -c -o output.txt
```

Use ignore patterns:

```bash
./vmrg.py /path/to/project -i .gitignore -o output.txt
```

Merge for an AI round trip with a custom system prompt file (compressed input, format directive included):

```bash
./vmrg.py /path/to/project -ca -s system_prompt.txt
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
./vmrg.py /path/to/project -ca -m "fix the login bug"
```

Type the task interactively in the terminal:

```bash
./vmrg.py /path/to/project -cap
```

Split a large project into parts of about 100k tokens:

```bash
./vmrg.py /path/to/project -ca --split 100000
```

Combine multiple options:

```bash
./vmrg.py /path/to/project -cdo output.txt -i .gitignore
```

## Options

| Option | Description |
|--------|-------------|
| `-o, --output` | Output file path for merging (default: `<src>_merged.txt`), or target directory for `-u` |
| `-i, --ignore` | Path to ignore patterns file (gitignore style, supports `!` negation) |
| `-c, --compress` | Enable whitespace compression and comment stripping |
| `-d, --dont-comment` | Add AI directive to prevent code commenting |
| `-a, --ai-format` | Add AI directive requesting an uncompressed reply, in mergeable VibeMerge format, containing only the files that need to be created, modified or deleted |
| `-s, --system-file FILE` | Prepend a system prompt read from the given file to the merged output, before all other directives |
| `-p, --prompt` | Type the task interactively in the terminal (finish with an empty line); the text is appended as a `TASK` block |
| `-m, --message` | Append a `TASK` block with the given text at the end of the merged output |
| `--prompt-file` | Append a `TASK` block read from a file at the end of the merged output (combines with `-m`) |
| `--split TOKENS` | Split the merged output into multiple part files of about `TOKENS` tokens each |
| `-u, --unmerge` | Apply a merged or AI response file back onto a directory, creating, updating and deleting files, auto-detecting the project root when `-o` is omitted |
| `-q, --quiet` | Suppress progress output |
| `-v, --version` | Display version information |

The default output file is named after the first input path: merging `/path/to/project` produces `project_merged.txt` and merging `main.py` produces `main_merged.txt`, created in the current working directory. With `--split`, the parts are named `<base>_merged_part1.txt`, `<base>_merged_part2.txt` and so on; part 1 carries the directives and the project tree, later parts carry a short continuation directive, and the `TASK` block is written at the end of the last part. The mode `-u` cannot be combined with `-c`, `-d`, `-a`, `-s`, `-p`, `-i`, `-m`, `--prompt-file` or `--split`. Files given to `-s` or `--prompt-file` are never included in the merge, even when they live inside the scanned directories, and previously generated split parts are skipped as well.

## AI Round-Trip Workflow

1. Merge the project with the `-a` flag. The output starts with a directive instructing the AI to answer with complete files in the exact VibeMerge format, never compressed or minified, with no diffs, fragments, markdown fences or commentary, to include only the files that actually need to be created, modified, renamed or deleted, to mark deletions with `DELETE:` and renames with `RENAME:`, to keep all related imports and references consistent, to answer `NO CHANGES REQUIRED` when nothing needs to change, and to always finish with an `END OF REPLY` line. The directive also tells the AI that the input may be compressed. A project structure tree is embedded after the directives. Combine with `-c` to shrink the input while keeping the reply readable, with `-s` to prepend your own system prompt from a file, and with `-m` or `--prompt-file` to embed the task itself so the whole request is a single paste.

```bash
./vmrg.py /path/to/project -ca -s system_prompt.txt -m "fix the login bug"
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
- Parses `FILE:`, `PATCH:`, `DELETE:` and `RENAME:` sections delimited by dash lines; falls back to bare header lines if the AI omitted the dashes
- Applies atomically in two phases: every section is parsed, checked and staged against an in-memory view of the project first, and files are only written once the whole reply has staged cleanly, so sections may build on each other (create then patch, rename then patch) within one reply
- Rejects a reply that is missing its `END OF REPLY` marker before writing anything, since that means the AI output was cut off
- Aborts the entire apply, writing nothing, when any patch hunk does not match, matches more than one place, targets a missing file, or is malformed
- Warns when a patch covers more than 60 percent of a file, since the directive requires a full FILE section in that case
- Treats a `NO CHANGES REQUIRED` reply as a successful no-op instead of an error
- Headers and `END OF REPLY` lines inside markdown code fences are treated as content, not as instructions
- Warns when the target directory is not under version control, since apply mode changes files in place
- Strips a surrounding markdown code fence around the whole reply and around individual file bodies
- Ignores any commentary before the first file header
- Streams a live, colored per-file log while applying: `+` created, `~` updated, patched or renamed, `-` deleted, `=` unchanged, already absent or already renamed, `!` skipped or warning
- Writes complete files with UTF-8 encoding and LF line endings, creating directories as needed
- Skips files whose content is identical to what is already on disk
- Deletes only regular files; a `DELETE:` for a path that does not exist is reported as already absent, and a `DELETE:` for a directory is skipped
- Renames preserve file bytes exactly when the body is empty; a `RENAME:` whose source is missing but whose destination exists is reported as already renamed
- Validates applied Python files with `ast.parse` and JSON files with `json.loads`, reporting syntax warnings without blocking the apply
- Rejects absolute paths, drive letters, `..` components and anything that would resolve outside the target directory, for `FILE:`, `DELETE:` and both sides of `RENAME:` sections
- Warns when an applied file looks compressed, since AI replies must never be compressed

## Supported Languages

Python, JavaScript, TypeScript (including `.mts`/`.cts`), JSX, TSX, Java, C, C++, C#, Go, Rust, PHP, Ruby, Swift, Kotlin, Scala, Lua, Perl, R, Objective-C, SQL, Shell, Bash, Vim, Dart, Elixir, Erlang, Clojure, Lisp, Haskell, OCaml, F#, Nim, Crystal, V, Zig

Web stack: HTML, HTM, XHTML, CSS, SCSS, Sass, LESS, Stylus, Vue, Svelte, Astro, JSON, JSONC, JSON5, Web App Manifest, XML, SVG, YAML, TOML, GraphQL, CoffeeScript, EJS, Handlebars, Mustache, Pug, Jade, Twig, Liquid, Markdown

Files in any other text format are still merged as-is; the language list above determines which files can be compressed with full comment and string awareness.

## Ignore Patterns

A `.gitignore` file found at the root of each scanned directory is loaded automatically; no flag is needed. Patterns passed with `-i` are applied after the automatic ones, so the last matching pattern wins and an explicit `-i` file can re-include paths with `!` negation. Nested `.gitignore` files in subdirectories are not read.

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
- Maximum file size: 10 MB per file
- Maximum total size: 1 GB
- Memory-mapped I/O used for files larger than 256 KB
- Progress bars render only on interactive terminals and stay silent in pipes and CI logs

## Terminal Output

Every operation opens with a version banner, shows a colored phase header with the run details, streams the work live line by line, and closes with a framed summary block:

```
* VibeMerge v4.0.0  apply

APPLYING FILES:

Detected root....... /home/edward/Desktop/solutik-backend/source/app (85 matched)
Target directory.... /home/edward/Desktop/solutik-backend/source/app
Sections found...... 85 in app_merged_persian.txt

  ~ updated app/api/routes.py
  ~ patched app/api/auth.py (2 hunk(s))
  + created app/api/health.py
  ~ renamed app/api/legacy.py -> app/api/v1/legacy.py
  - deleted app/api/deprecated.py
  = app/core/config.py unchanged

--------------------------------------------------------------------------------
OPERATION COMPLETE
--------------------------------------------------------------------------------

Files created....... 1
Files updated....... 1
Files patched....... 1
Files renamed....... 1
Files deleted....... 1
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

## Compression Mode

Compression collapses runs of spaces and tabs, removes blank lines and trailing whitespace, and strips comments, while preserving newlines, leading indentation, string literals, JavaScript regex and template literals, and PHP heredoc/nowdoc bodies byte for byte, so the compressed code remains syntactically valid. Shebang lines and PHP 8 attributes are preserved. Web formats are compressed with the same guarantees: HTML and template comments, CSS block comments, and YAML, TOML, and GraphQL comments are stripped while quoted values, URLs, and attribute strings stay untouched.

When compression is enabled without `-a`, the output includes a directive for AI systems:

```
================================================================================
SYSTEM INSTRUCTION FOR AI
This code has been compressed to reduce token usage.
When generating responses or code:
- Write code in normal, readable format with proper spacing
- Use standard indentation and line breaks
- Follow conventional formatting practices
- DO NOT compress or minify your output
================================================================================
```

With `-a`, a single round-trip directive is written instead. It notes that the input may be compressed, forbids compressed replies, requires the reply to contain only the files that need to be created, modified, renamed or deleted, documents the `PATCH:`, `DELETE:`, `RENAME:` and stacked header forms, states the 60 percent rule for choosing between PATCH and FILE, requires consistency of imports and references across the reply, defines the `NO CHANGES REQUIRED` reply, and requires the closing `END OF REPLY` marker without which `-u` refuses to apply anything. When identical files are merged, a duplicate note explaining the stacked header form is appended to the directive automatically.

With `-s FILE`, the merged output is prefixed with the exact content of the given file, before every other directive. No system prompt is hardcoded into the tool; the file is inserted as-is, so it can carry any framing, persona or rules you want. A ready-to-use example prompt for high quality engineering replies ships as `senior_prompt.txt`.

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