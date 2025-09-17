#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from argparse import ArgumentParser
from fnmatch import fnmatch


def load_ignore_patterns(file_path):
    if not Path(file_path).exists():
        return []

    patterns = []

    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
    return patterns


def should_ignore(file_path, base_dir, patterns):
    if not patterns:
        return False

    rel_path = str(file_path.relative_to(base_dir))
    filename = file_path.name

    for pattern in patterns:
        if fnmatch(filename, pattern) or fnmatch(rel_path, pattern):
            return True
    return False


def is_text_file(file_path):
    try:
        size = file_path.stat().st_size
        if size == 0 or size > 10485760:
            return False

        with open(file_path, 'rb') as f:
            chunk = f.read(min(size, 1024))
            return b'\x00' not in chunk
    except:
        return False


def collect_files(directory, ignore_patterns):
    files = []
    total_size = 0
    max_size = 1073741824

    for root, dirs, filenames in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        for filename in sorted(filenames):
            if filename.startswith('.'):
                continue

            file_path = Path(root) / filename

            if not file_path.is_file():
                continue

            if should_ignore(file_path, directory, ignore_patterns):
                continue

            if not is_text_file(file_path):
                continue

            file_size = file_path.stat().st_size
            if total_size + file_size > max_size:
                break

            total_size += file_size
            files.append(file_path)

    return sorted(files), total_size


def merge_files(directory_path, output_file=None, ignore_file=None):
    directory = Path(directory_path).resolve()

    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Directory not found: {directory_path}")

    ignore_patterns = []
    if ignore_file:
        ignore_patterns = load_ignore_patterns(ignore_file)

    files, total_size = collect_files(directory, ignore_patterns)

    if not files:
        raise ValueError("No files found")

    if output_file:
        output_path = Path(output_file)
    else:
        script_dir = Path(__file__).parent.resolve()
        output_path = script_dir / "vibemerged.txt"

    with open(output_path, 'w', encoding='utf-8') as out_file:
        for i, file_path in enumerate(files):
            if i > 0:
                out_file.write('\n\n')

            rel_path = file_path.relative_to(directory.parent)
            out_file.write(f"{rel_path}\n\n")

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().rstrip()
                    out_file.write(content)
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read().rstrip()
                    out_file.write(content)

    return output_path, len(files), total_size


def main():
    parser = ArgumentParser(description="VibeMerge - File concatenation tool")
    parser.add_argument("directory")
    parser.add_argument("-o", "--output")
    parser.add_argument("-i", "--ignore")

    args = parser.parse_args()

    try:
        output_file, file_count, total_size = merge_files(
            args.directory, args.output, args.ignore
        )

        print(f"Merged {file_count} files ({total_size // 1048576} MB)")
        print(f"Output: {output_file}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
