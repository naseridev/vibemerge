# VibeMerge

A command-line file concatenation tool designed for preparing code repositories for AI agent interactions during manual vibe coding sessions.

## Overview

VibeMerge is a utility that merges multiple text files from a project directory into a single concatenated file, formatted for use as prompts with AI coding agents. When working without integrated tools like Cursor, this script streamlines the process of preparing your codebase for manual submission to AI agents.

## Features

- **Selective File Processing**: Only processes text files while skipping binary files and hidden files
- **Size Management**: Built-in file size limits (1GB total, 10MB per file) to prevent memory issues
- **Ignore Pattern Support**: Custom ignore patterns via external file (similar to .gitignore)
- **Clean Output Format**: Each file is clearly delimited with its relative path
- **Error Handling**: Graceful handling of encoding issues and file access problems

## Usage

### Basic Usage
```bash
./vmrg.py /path/to/your/project
```

### With Custom Output File
```bash
./vmrg.py /path/to/your/project -o custom_output.txt
```

### With Ignore Patterns
```bash
./vmrg.py /path/to/your/project -i .vibeignore
```

## Command Line Options

- `directory`: Target directory to process (required)
- `-o, --output`: Custom output file path (default: `vibemerged.txt` in script directory)
- `-i, --ignore`: Path to ignore patterns file

## Ignore Patterns File

Create a text file with patterns to exclude files/directories:

```
*.log
*.tmp
node_modules/
dist/
build/
__pycache__/
*.pyc
```

## Output Format

The merged file contains each processed file with its relative path as a header:

```
project/src/main.py

#!/usr/bin/env python3
import os
...

project/src/utils.py

def helper_function():
    pass
...
```

## File Processing Rules

- Processes only text files (detects binary files and skips them)
- Skips hidden files and directories (those starting with '.')
- Respects ignore patterns if provided
- Sorts files alphabetically for consistent output
- Handles encoding issues with replacement characters

## Use Cases

- Preparing code for manual AI agent prompting
- Creating consolidated code reviews
- Generating documentation inputs
- Code analysis preparation

## Technical Specifications

- Maximum total size: 1GB
- Maximum individual file size: 10MB
- Text detection: Binary null-byte checking
- Encoding: UTF-8 with error replacement fallback

## Requirements

- Python 3.6+
- Standard library only (no external dependencies)