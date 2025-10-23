#!/usr/bin/env python3

import os
import sys
import time
from pathlib import Path
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from fnmatch import fnmatch


VERSION = "2.0.0"
DEFAULT_OUTPUT = "vibemerged.txt"
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_TOTAL_SIZE = 1024 * 1024 * 1024


def format_bytes(size):
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    idx = 0
    while size >= 1024.0 and idx < len(units) - 1:
        size /= 1024.0
        idx += 1
    return f"{int(size)} {units[idx]}" if idx == 0 else f"{size:.2f} {units[idx]}"


def show_progress(current, total, prefix="", last_percent=[0]):
    if total == 0:
        return

    percent = int(100 * current / total)

    if percent >= last_percent[0] + 10 or current >= total:
        print(f"{prefix}{percent}%")
        last_percent[0] = percent


def load_patterns(path):
    if not Path(path).exists():
        return []
    patterns = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
    return patterns


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
            chunk = f.read(min(stat.st_size, 1024))
            return b'\x00' not in chunk
    except:
        return False


def compress_code(content):
    result = []
    in_string = False
    string_char = None
    escaped = False
    
    for char in content:
        if escaped:
            result.append(char)
            escaped = False
            continue
            
        if char == string_char and in_string:
            in_string = False
            string_char = None
            result.append(char)
            continue
            
        if in_string:
            result.append(char)
            continue
            
        if char in (' ', '\n', '\t', '\r'):
            continue
            
        result.append(char)
    
    return ''.join(result)


def collect_files(directory, patterns, quiet):
    files = []
    total = 0

    if not quiet:
        print("Scanning directory...\n")
        file_count = sum(1 for _ in directory.rglob('*') if _.is_file())
        processed = 0

    for root, dirs, filenames in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        for filename in sorted(filenames):
            if not quiet:
                processed += 1
                show_progress(processed, file_count, "Scan ")

            if filename.startswith('.'):
                continue

            fpath = Path(root) / filename

            if not fpath.is_file():
                continue

            if should_ignore(fpath, directory, patterns):
                continue

            if not is_text(fpath):
                continue

            fsize = fpath.stat().st_size
            if total + fsize > MAX_TOTAL_SIZE:
                if not quiet:
                    print("Warning: size limit reached")
                break

            total += fsize
            files.append(fpath)

    return sorted(files), total


def merge_files(directory, output, ignore, compress, no_comment, quiet):
    directory = Path(directory).resolve()

    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Invalid directory: {directory}")

    patterns = load_patterns(ignore) if ignore else []

    if not quiet and patterns:
        print(f"Loaded {len(patterns)} ignore pattern(s)")

    files, total_size = collect_files(directory, patterns, quiet)

    if not files:
        raise ValueError("No files found")

    if output:
        outpath = Path(output).resolve()
    else:
        outpath = Path(__file__).parent.resolve() / DEFAULT_OUTPUT

    outpath.parent.mkdir(parents=True, exist_ok=True)

    if not quiet:
        print(f"Merging {len(files)} file(s)...")

    start = time.time()
    compressed_size = 0
    total_lines = 0

    with open(outpath, 'w', encoding='utf-8') as out:
        if no_comment:
            out.write("IMPORTANT: This code is merged for AI processing.\n")
            out.write("When generating output, DO NOT add comments or docstrings.\n")
            out.write("Provide clean, production-ready code only.\n\n")

        for i, fpath in enumerate(files):
            if not quiet:
                show_progress(i + 1, len(files), "merge ")

            if i > 0:
                out.write('\n\n')

            rel = fpath.relative_to(directory.parent)
            out.write(f"{'-' * 80}\n")
            out.write(f"FILE: {rel}\n")
            out.write(f"{'-' * 80}\n\n")

            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read().rstrip()
            except UnicodeDecodeError:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read().rstrip()

            total_lines += content.count('\n') + 1

            if compress:
                content = compress_code(content)
                compressed_size += len(content.encode('utf-8'))

            out.write(content)

    elapsed = time.time() - start

    if not quiet:
        print(f"Completed in {elapsed:.2f}s\n")

    return outpath, len(files), total_size, compressed_size if compress else 0, total_lines


def main():
    desc = f"""VibeMerge v{VERSION} - File Merger

Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project -o out.txt
  %(prog)s /path/to/project -cd
  %(prog)s /path/to/project -cdo out.txt -i .gitignore
    """

    parser = ArgumentParser(
        description=desc,
        formatter_class=RawDescriptionHelpFormatter
    )

    parser.add_argument('directory')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('-i', '--ignore', help='Ignore patterns file')
    parser.add_argument('-c', '--compress', action='store_true',
                       help='Compress whitespace')
    parser.add_argument('-d', '--dont-comment', action='store_true',
                       help='Add AI no-comment directive')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='Quiet mode')
    parser.add_argument('-v', '--version', action='version',
                       version=f'%(prog)s {VERSION}')

    args = parser.parse_args()

    try:
        outpath, count, size, compressed_size, total_lines = merge_files(
            args.directory,
            args.output,
            args.ignore,
            args.compress,
            args.dont_comment,
            args.quiet
        )

        if not args.quiet:
            print(f"Files:       {count:,}")
            print(f"Lines:       {total_lines:,}")
            if args.compress:
                print(f"Size before: {format_bytes(size)}")
                print(f"Size after:  {format_bytes(compressed_size)}")
                reduction = ((size - compressed_size) / size * 100) if size > 0 else 0
                print(f"Reduction:   {reduction:.1f}%")
            else:
                print(f"Size:        {format_bytes(size)}")
            print(f"Output:      {outpath}")
            print(f"Compressed:  {'Yes' if args.compress else 'No'}")
            print(f"AI directive: {'Yes' if args.dont_comment else 'No'}")
        return 0

    except KeyboardInterrupt:
        print("\n\nCancelled", file=sys.stderr)
        return 130

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
