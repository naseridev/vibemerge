#!/usr/bin/env python3

import os
import sys
import time
import mmap
from pathlib import Path
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from fnmatch import fnmatch
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from functools import lru_cache
import re


VERSION = "2.1.0"
DEFAULT_OUTPUT = "vibemerged.txt"
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_TOTAL_SIZE = 1024 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
CPU_THRESHOLD = 4


LANG_PATTERNS = {
    '.py': (rb'"""', rb"'''", rb'"', rb"'", rb'#'),
    '.js': (rb'`', rb'"', rb"'", rb'//', rb'/*'),
    '.ts': (rb'`', rb'"', rb"'", rb'//', rb'/*'),
    '.jsx': (rb'`', rb'"', rb"'", rb'//', rb'/*'),
    '.tsx': (rb'`', rb'"', rb"'", rb'//', rb'/*'),
    '.java': (rb'"', rb"'", rb'//', rb'/*'),
    '.c': (rb'"', rb"'", rb'//', rb'/*'),
    '.cpp': (rb'"', rb"'", rb'//', rb'/*'),
    '.go': (rb'`', rb'"', rb"'", rb'//'),
    '.rs': (rb'"', rb"'", rb'r"', rb'//'),
    '.php': (rb'"', rb"'", rb'//'),
    '.rb': (rb'"', rb"'", rb'#'),
}


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
        print(f"{prefix}{percent}%", flush=True)
        last_percent[0] = percent


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


def is_text_mmap(filepath):
    try:
        stat = filepath.stat()
        if stat.st_size == 0 or stat.st_size > MAX_FILE_SIZE:
            return False
        
        with open(filepath, 'rb') as f:
            if stat.st_size < 1024:
                chunk = f.read()
            else:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    chunk = mm[:1024]
            return b'\x00' not in chunk
    except:
        return False


def compress_code_optimized(content, ext):
    content_bytes = content.encode('utf-8') if isinstance(content, str) else content
    result = bytearray()
    i = 0
    n = len(content_bytes)
    
    whitespace = {ord(' '), ord('\n'), ord('\t'), ord('\r')}
    
    while i < n:
        ch = content_bytes[i]
        
        if ch == ord('\\') and i + 1 < n:
            result.append(ch)
            result.append(content_bytes[i + 1])
            i += 2
            continue
        
        if ch == ord('"'):
            result.append(ch)
            i += 1
            while i < n:
                ch = content_bytes[i]
                result.append(ch)
                if ch == ord('\\') and i + 1 < n:
                    result.append(content_bytes[i + 1])
                    i += 2
                    continue
                if ch == ord('"'):
                    i += 1
                    break
                i += 1
            continue
        
        if ch == ord("'"):
            result.append(ch)
            i += 1
            while i < n:
                ch = content_bytes[i]
                result.append(ch)
                if ch == ord('\\') and i + 1 < n:
                    result.append(content_bytes[i + 1])
                    i += 2
                    continue
                if ch == ord("'"):
                    i += 1
                    break
                i += 1
            continue
        
        if ch == ord('`'):
            result.append(ch)
            i += 1
            while i < n:
                ch = content_bytes[i]
                result.append(ch)
                if ch == ord('\\') and i + 1 < n:
                    result.append(content_bytes[i + 1])
                    i += 2
                    continue
                if ch == ord('`'):
                    i += 1
                    break
                i += 1
            continue
        
        if ext == '.py' and i + 2 < n:
            if content_bytes[i:i+3] == b'"""' or content_bytes[i:i+3] == b"'''":
                delim = content_bytes[i:i+3]
                result.extend(delim)
                i += 3
                while i + 2 < n:
                    if content_bytes[i:i+3] == delim:
                        result.extend(delim)
                        i += 3
                        break
                    result.append(content_bytes[i])
                    i += 1
                continue
        
        if ch in whitespace:
            i += 1
            continue
        
        result.append(ch)
        i += 1
    
    return result.decode('utf-8', errors='replace')


def process_file_parallel(args):
    fpath, directory, compress = args
    try:
        stat = fpath.stat()
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read().rstrip()
    except UnicodeDecodeError:
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read().rstrip()
    except:
        return None
    
    ext = fpath.suffix.lower()
    lines = content.count('\n') + 1
    
    if compress:
        compressed = compress_code_optimized(content, ext)
        compressed_size = len(compressed.encode('utf-8'))
    else:
        compressed = content
        compressed_size = 0
    
    rel = fpath.relative_to(directory.parent)
    header = f"{'-' * 80}\nFILE: {rel}\n{'-' * 80}\n\n"
    
    return {
        'path': fpath,
        'content': compressed,
        'header': header,
        'lines': lines,
        'size': stat.st_size,
        'compressed_size': compressed_size
    }


def collect_files_parallel(directory, patterns, quiet):
    files = []
    total = 0
    
    all_files = []
    for root, dirs, filenames in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for filename in filenames:
            if not filename.startswith('.'):
                all_files.append(Path(root) / filename)
    
    if not quiet:
        print(f"Scanning {len(all_files)} files...\n", flush=True)
    
    valid_files = []
    for fpath in all_files:
        if not fpath.is_file():
            continue
        if should_ignore(fpath, directory, patterns):
            continue
        if not is_text_mmap(fpath):
            continue
        
        fsize = fpath.stat().st_size
        if total + fsize > MAX_TOTAL_SIZE:
            if not quiet:
                print("Warning: size limit reached")
            break
        
        total += fsize
        valid_files.append(fpath)
    
    return sorted(valid_files), total


def merge_files(directory, output, ignore, compress, no_comment, quiet, parallel):
    directory = Path(directory).resolve()
    
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Invalid directory: {directory}")
    
    patterns = load_patterns(ignore) if ignore else tuple()
    
    if not quiet and patterns:
        print(f"Loaded {len(patterns)} ignore pattern(s)")
    
    files, total_size = collect_files_parallel(directory, patterns, quiet)
    
    if not files:
        raise ValueError("No files found")
    
    if output:
        outpath = Path(output).resolve()
    else:
        outpath = Path(__file__).parent.resolve() / DEFAULT_OUTPUT
    
    outpath.parent.mkdir(parents=True, exist_ok=True)
    
    if not quiet:
        print(f"Merging {len(files)} file(s)...")
        if parallel:
            print(f"Using {min(cpu_count(), len(files))} workers")
    
    start = time.time()
    compressed_size = 0
    total_lines = 0
    
    use_parallel = parallel and len(files) >= CPU_THRESHOLD and cpu_count() > 1
    
    if use_parallel:
        results = []
        with ProcessPoolExecutor(max_workers=cpu_count()) as executor:
            futures = {
                executor.submit(process_file_parallel, (f, directory, compress)): i 
                for i, f in enumerate(files)
            }
            
            for future in as_completed(futures):
                idx = futures[future]
                result = future.result()
                if result:
                    results.append((idx, result))
                
                if not quiet:
                    show_progress(len(results), len(files), "Process ")
        
        results.sort(key=lambda x: x[0])
        
        with open(outpath, 'w', encoding='utf-8') as out:
            if compress:
                out.write("=" * 80 + "\n")
                out.write("SYSTEM INSTRUCTION FOR AI\n")
                out.write("=" * 80 + "\n")
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
                out.write("=" * 80 + "\n")
                out.write("When generating code:\n")
                out.write("- DO NOT add comments or docstrings\n")
                out.write("- Provide clean, production-ready code only\n")
                out.write("- Focus on functionality, not documentation\n")
                out.write("=" * 80 + "\n\n")
            
            for i, (_, result) in enumerate(results):
                if i > 0:
                    out.write('\n\n')
                out.write(result['header'])
                out.write(result['content'])
                
                total_lines += result['lines']
                if compress:
                    compressed_size += result['compressed_size']
    
    else:
        with open(outpath, 'w', encoding='utf-8') as out:
            if compress:
                out.write("=" * 80 + "\n")
                out.write("SYSTEM INSTRUCTION FOR AI\n")
                out.write("=" * 80 + "\n")
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
                out.write("=" * 80 + "\n")
                out.write("When generating code:\n")
                out.write("- DO NOT add comments or docstrings\n")
                out.write("- Provide clean, production-ready code only\n")
                out.write("- Focus on functionality, not documentation\n")
                out.write("=" * 80 + "\n\n")
            
            for i, fpath in enumerate(files):
                if not quiet:
                    show_progress(i + 1, len(files), "Merge ")
                
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
                    ext = fpath.suffix.lower()
                    content = compress_code_optimized(content, ext)
                    compressed_size += len(content.encode('utf-8'))
                
                out.write(content)
    
    elapsed = time.time() - start
    
    if not quiet:
        print(f"\nCompleted in {elapsed:.2f}s")
    
    return outpath, len(files), total_size, compressed_size if compress else 0, total_lines


def main():
    desc = f"""VibeMerge v{VERSION} - File Merger

Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project -o out.txt -p
  %(prog)s /path/to/project -cd
  %(prog)s /path/to/project -cdpo out.txt -i .gitignore
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
    parser.add_argument('-p', '--parallel', action='store_true',
                       help='Enable parallel processing')
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
            args.quiet,
            args.parallel
        )
        
        if not args.quiet:
            print(f"\nFiles:       {count:,}")
            print(f"Lines:       {total_lines:,}")
            if args.compress:
                print(f"Size before: {format_bytes(size)}")
                print(f"Size after:  {format_bytes(compressed_size)}")
                reduction = ((size - compressed_size) / size * 100) if size > 0 else 0
                print(f"Reduction:   {reduction:.1f}%")
            else:
                print(f"Size:        {format_bytes(size)}")
            print(f"Output:      {outpath}")
            if args.compress:
                print(f"Compressed:  Yes")
            if args.dont_comment:
                print(f"No Comments: Yes")
            if args.parallel:
                print(f"Parallel:    Yes ({cpu_count()} CPUs)")
        return 0
    
    except KeyboardInterrupt:
        print("\n\nCancelled", file=sys.stderr)
        return 130
    
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
