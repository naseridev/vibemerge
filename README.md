# VibeMerge

A powerful command-line file concatenation tool designed for preparing code repositories for AI agent interactions during manual vibe coding sessions.

## Overview

VibeMerge is a utility that merges multiple text files from a project directory into a single concatenated file, formatted for use as prompts with AI coding agents. When working without integrated tools like Cursor, this script streamlines the process of preparing your codebase for manual submission to AI agents.

## Features

- **Smart File Processing**: Automatically detects and processes only text files while skipping binary files
- **Progress Tracking**: Real-time progress indicators during scanning and merging operations
- **Size Management**: Built-in safety limits (1GB total, 10MB per file) to prevent memory issues
- **Ignore Pattern Support**: Flexible ignore patterns via external file (similar to .gitignore)
- **Code Compression**: Optional whitespace compression to reduce token usage
- **AI Directive Mode**: Optional header to instruct AI agents to provide clean, comment-free code
- **Clean Output Format**: Each file is clearly delimited with its relative path
- **Hidden File Filtering**: Automatically skips hidden files and directories (starting with '.')
- **Error Handling**: Graceful handling of encoding issues and file access problems
- **Detailed Statistics**: Comprehensive summary of merged files, lines, and sizes

## Installation

No installation required! VibeMerge uses only Python standard library.

```bash
# Make the script executable
chmod +x vmrg.py
```

## Usage

### Basic Usage

```bash
./vmrg.py /path/to/your/project
```

This will create `vibemerged.txt` in the same directory as the script.

### With Custom Output File

```bash
./vmrg.py /path/to/your/project -o custom_output.txt
```

### With Ignore Patterns

```bash
./vmrg.py /path/to/your/project -i .vibeignore
```

### With Code Compression

```bash
./vmrg.py /path/to/your/project -c
```

Removes unnecessary whitespace to reduce file size and token count.

### With AI No-Comment Directive

```bash
./vmrg.py /path/to/your/project -d
```

Adds a header instructing AI agents to generate clean code without comments or docstrings.

### Combined Options

```bash
./vmrg.py /path/to/your/project -cdo output.txt -i .gitignore
```

## Command Line Options

| Option | Long Form | Description |
|--------|-----------|-------------|
| `directory` | - | Target directory to process (required) |
| `-o` | `--output` | Custom output file path |
| `-i` | `--ignore` | Path to ignore patterns file |
| `-c` | `--compress` | Enable whitespace compression |
| `-d` | `--dont-comment` | Add AI no-comment directive |
| `-q` | `--quiet` | Quiet mode (suppress progress output) |
| `-v` | `--version` | Show version information |

## Ignore Patterns File

Create a text file with patterns to exclude files and directories. Supports wildcards and path matching:

```
# Comments start with #
*.log
*.tmp
*.pyc
node_modules/
dist/
build/
__pycache__/
.git/
*.min.js
package-lock.json
```

Pattern matching supports:
- Wildcards (`*`, `?`)
- Filename matching (`*.log`)
- Path matching (`node_modules/`)

## Output Format

The merged file contains each processed file with a clear delimiter and relative path:

```
--------------------------------------------------------------------------------
FILE: project/src/main.py
--------------------------------------------------------------------------------

#!/usr/bin/env python3
import os
...


--------------------------------------------------------------------------------
FILE: project/src/utils.py
--------------------------------------------------------------------------------

def helper_function():
    pass
...
```

### With AI Directive Mode (-d)

When using the `-d` flag, the output file starts with:

```
IMPORTANT: This code is merged for AI processing.
When generating output, DO NOT add comments or docstrings.
Provide clean, production-ready code only.
```

## File Processing Rules

- **Text Detection**: Uses binary null-byte checking to identify text files
- **Hidden Files**: Skips files and directories starting with '.'
- **Sorting**: Files are processed in alphabetical order for consistent output
- **Encoding**: UTF-8 with automatic fallback to replacement characters
- **Size Limits**: 
  - Maximum individual file: 10MB
  - Maximum total size: 1GB
  - Empty files are skipped

## Code Compression

When using the `-c` flag, VibeMerge removes:
- Spaces
- Newlines
- Tabs
- Carriage returns

**Note**: The compression algorithm preserves string literals to maintain code integrity.

## Example Output

After running VibeMerge, you'll see a summary:

```
Scanning directory...
Scan 100%
Loaded 5 ignore pattern(s)
Merging 42 file(s)...
merge 100%
Completed in 0.87s

Files:       42
Lines:       3,457
Size:        234.56 KB
Output:      /path/to/vibemerged.txt
Compressed:  No
AI directive: No
```

With compression enabled:

```
Files:       42
Lines:       3,457
Size before: 234.56 KB
Size after:  156.89 KB
Reduction:   33.1%
Output:      /path/to/vibemerged.txt
Compressed:  Yes
AI directive: Yes
```

## Use Cases

- **AI Agent Prompting**: Prepare entire codebases for submission to AI coding assistants
- **Code Reviews**: Create consolidated files for manual or automated review
- **Documentation**: Generate input files for documentation tools
- **Code Analysis**: Prepare code for static analysis or security scanning
- **Context Sharing**: Share complete project context in a single file
- **Backup**: Create readable backups of text-based projects

## Technical Specifications

- **Language**: Python 3.6+
- **Dependencies**: None (uses only standard library)
- **Maximum total size**: 1GB
- **Maximum individual file size**: 10MB
- **Text detection**: Binary null-byte checking (first 1KB)
- **Encoding**: UTF-8 with error replacement fallback
- **Progress updates**: Every 10% increment

## Error Handling

VibeMerge handles common issues gracefully:

- **Invalid directory**: Clear error message
- **Permission errors**: Skips inaccessible files
- **Encoding issues**: Falls back to replacement characters
- **Size limit reached**: Warning message and graceful stop
- **Keyboard interrupt**: Clean cancellation (exit code 130)

## Requirements

- Python 3.6 or higher
- No external dependencies

## Version

Current version: **2.0.0**

## License

This tool is provided as-is for use in AI-assisted development workflows.

## Tips

1. **Create project-specific ignore files**: Each project can have its own `.vibeignore` file
2. **Use compression for large projects**: The `-c` flag can significantly reduce token usage
3. **Combine with AI directive**: Use `-cd` together for optimal AI agent interaction
4. **Test ignore patterns**: Run once to see what gets included, then refine your patterns
5. **Check output before using**: Always review the merged file to ensure expected content

## Troubleshooting

**Problem**: Too many files included  
**Solution**: Create or update your ignore patterns file

**Problem**: Binary files processed as text  
**Solution**: VibeMerge should auto-detect these, but you can add patterns to ignore them

**Problem**: Output file too large  
**Solution**: Use the `-c` flag for compression or add more ignore patterns

**Problem**: Encoding errors  
**Solution**: VibeMerge automatically handles these with replacement characters

---

**Happy Vibe Coding! 🚀**
