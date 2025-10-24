# VibeMerge

A high-performance code merging utility for consolidating source files from multiple languages into a single output file. Built for efficiency and scalability.

## Overview

VibeMerge is designed to aggregate codebases efficiently. It supports over 40 programming languages, provides optional compression, and scales with parallel processing capabilities.

## Features

- Multi-language support for 40+ file types
- Parallel processing with multi-core utilization
- Optional whitespace compression
- Intelligent text file detection
- Pattern-based file filtering
- Memory-mapped I/O for large files
- Progress tracking and detailed statistics

## Installation

Clone the repository and ensure Python 3.7+ is installed:

```bash
git clone https://github.com/naseridev/vibemerge.git
```

```bash
cd vmrg
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

Merge all files in a directory:
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

Enable compression and parallel processing:
```bash
./vmrg.py /path/to/project -cp -o output.txt
```

Use ignore patterns:
```bash
./vmrg.py /path/to/project -i .gitignore -o output.txt
```

Combine multiple options:
```bash
./vmrg.py /path/to/project -cdpo output.txt -i .gitignore
```

## Options

| Option | Description |
|--------|-------------|
| `-o, --output` | Specify output file path (default: vibemerged.txt) |
| `-i, --ignore` | Path to ignore patterns file |
| `-c, --compress` | Enable whitespace compression |
| `-d, --dont-comment` | Add AI directive to prevent code commenting |
| `-p, --parallel` | Enable parallel processing for faster merging |
| `-q, --quiet` | Suppress progress output |
| `-v, --version` | Display version information |

## Supported Languages

Python, JavaScript, TypeScript, Java, C, C++, C#, Go, Rust, PHP, Ruby, Swift, Kotlin, Scala, Lua, Perl, R, Objective-C, SQL, Shell, Bash, Vim, Dart, Elixir, Erlang, Clojure, Lisp, Haskell, OCaml, F#, Nim, Crystal, V, Zig

## Ignore Patterns

Create a file with patterns to exclude specific files or directories:

```
node_modules
*.log
build/
dist/
.git
__pycache__
```

## Performance Considerations

- Parallel processing activates automatically for 4+ files on multi-core systems
- Maximum file size: 10 MB per file
- Maximum total size: 1 GB
- Memory-mapped I/O used for files larger than 256 KB

## Output Format

Each merged file includes a header with the relative path:

```
--------------------------------------------------------------------------------
FILE: src/main.py
--------------------------------------------------------------------------------

[file content]
```

## Compression Mode

When compression is enabled, the output includes a directive for AI systems:

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

## Exit Codes

- 0: Success
- 1: Fatal error
- 130: User interruption

## Requirements

- Python 3.7 or higher
- No external dependencies required

## Contributing

Contributions are welcome. Submit pull requests with clear descriptions and test coverage.

## Support

For issues or questions, open an issue on the GitHub repository.
