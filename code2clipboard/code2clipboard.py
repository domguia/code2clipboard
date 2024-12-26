#!/usr/bin/env python3

import os
import sys
import argparse
import pyperclip
import tiktoken
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern
from fnmatch import fnmatch

DIM = "\033[2m"
RESET = "\033[0m"

def load_gitignore_specs(root_dir, extra_excludes=None):
    """
    Returns a pathspec that combines .gitignore patterns plus any extra excludes.
    """
    patterns = []
    gitignore_path = os.path.join(root_dir, '.gitignore')
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            gitignore_lines = f.read().splitlines()
        patterns.extend(gitignore_lines)

    if extra_excludes:
        patterns.extend(extra_excludes)

    return PathSpec.from_lines(GitWildMatchPattern, patterns)

def human_tokens(num: int) -> str:
    """
    Convert integer token counts to a human-readable format:
      <1000 => "123"
      1000..9999 => "6.1k"
      >=10000 => "23k"
    """
    if num < 1000:
        return str(num)
    elif num < 10000:
        return f"{num/1000:.1f}k"
    else:
        return f"{num // 1000}k"

def human_size(num_bytes: int) -> str:
    """
    Return a rough integer "kb" for file size.
      - if 0 < size < 1024 => "1kb"
      - else => e.g. 23456 => "22kb"
    """
    if num_bytes <= 0:
        return "0kb"
    kb = max(1, num_bytes // 1024)  # at least 1kb if nonempty
    return f"{kb}kb"

def get_file_tokens(path, enc):
    """
    Return the number of tokens in file `path` or 0 on error.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return len(enc.encode(text))
    except Exception as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)
        return 0

def build_tree_structure(
    directory, enc, exclude_spec, include, add_hidden, max_file_size
):
    """
    Recursively gather info about `directory`: 
    - total tokens, total size
    - list of files (name, tokens, size, skipped?)
    - list of dirs (same structure)

    Returns a dict:
    {
      "name": <basename>,
      "path": <abs path>,
      "files": [ {"name":..., "tokens":..., "size":..., "skipped":...}, ... ],
      "dirs": [...sub-structures...],
      "tokens": <cumulative tokens in this dir>,
      "size": <cumulative file size in this dir>
    }
    """
    name = os.path.basename(directory) or directory
    structure = {
        "name": name,
        "path": directory,
        "files": [],
        "dirs": [],
        "tokens": 0,
        "size": 0,
    }

    try:
        items = sorted(os.listdir(directory))
    except OSError as e:
        print(f"Cannot list directory {directory}: {e}", file=sys.stderr)
        return structure

    for item in items:
        # skip hidden if not asked to include them
        if item.startswith('.') and not add_hidden:
            continue

        full_path = os.path.join(directory, item)
        rel_path = os.path.relpath(full_path, directory)

        if os.path.isdir(full_path):
            # skip entire directory if excluded
            if exclude_spec and exclude_spec.match_file(item + "/"):
                continue

            sub_structure = build_tree_structure(
                full_path, enc, exclude_spec, include, add_hidden, max_file_size
            )
            structure["dirs"].append(sub_structure)
            structure["tokens"] += sub_structure["tokens"]
            structure["size"] += sub_structure["size"]

        else:
            fsize = os.path.getsize(full_path)

            # If file is larger than max_file_size, mark it as skipped
            if fsize > max_file_size:
                structure["files"].append({
                    "name": item,
                    "size": fsize,
                    "tokens": 0,
                    "skipped": True
                })
                # Do NOT add to total tokens/size
                continue

            # skip if excluded
            if exclude_spec and exclude_spec.match_file(rel_path):
                continue

            # skip if doesn't match any --include pattern
            if include:
                if not any(fnmatch(item, pat) for pat in include):
                    continue

            ftokens = get_file_tokens(full_path, enc)

            structure["files"].append({
                "name": item,
                "size": fsize,
                "tokens": ftokens,
                "skipped": False
            })
            structure["tokens"] += ftokens
            structure["size"] += fsize

    return structure

def format_tree(structure, prefix="", is_last=True, max_file_size=None):
    """
    Pretty ASCII tree for directories and files, with:
      "dir/        - 12kb ~3k tokens"
      "file.py     - 4kb ~1.2k tokens"
    in dim text.

    If a file is "skipped" (too large, etc.), show a notice instead of size/token info.
    """
    lines = []
    branch = "└──" if is_last else "├──"

    dir_line = (
        f"{prefix}{branch} {structure['name']}/"
        f"{DIM} - {human_size(structure['size'])} ~{human_tokens(structure['tokens'])} tokens{RESET}"
    )
    lines.append(dir_line)

    # next-level prefix
    next_prefix = prefix + ("    " if is_last else "│   ")

    # show files
    file_count = len(structure["files"])
    for i, f in enumerate(structure["files"]):
        file_branch = "└──" if (i == file_count - 1 and not structure["dirs"]) else "├──"
        if f.get("skipped"):
            # e.g. "skipped because > 20kb"
            reason_line = (
                f"{next_prefix}{file_branch} {f['name']}"
                f"{DIM} - skipped because > {human_size(max_file_size)}{RESET}"
                if max_file_size
                else f"{next_prefix}{file_branch} {f['name']}{DIM} - skipped{RESET}"
            )
            lines.append(reason_line)
        else:
            line = (
                f"{next_prefix}{file_branch} {f['name']}"
                f"{DIM} - {human_size(f['size'])} ~{human_tokens(f['tokens'])} tokens{RESET}"
            )
            lines.append(line)

    # subdirs
    dir_count = len(structure["dirs"])
    for j, d in enumerate(structure["dirs"]):
        sub_is_last = (j == dir_count - 1)
        lines.extend(format_tree(
            d, prefix=next_prefix, is_last=sub_is_last, max_file_size=max_file_size
        ))

    return lines

def gather_files_for_merge(directory, exclude_spec, include, add_hidden, max_file_size):
    """
    Returns a list of valid files for merging (same logic as in build_tree_structure).
    Skips any file larger than max_file_size.
    """
    valid_files = []
    for root, dirs, files in os.walk(directory):
        if not add_hidden:
            dirs[:] = [d for d in dirs if not d.startswith('.')]

        for fname in files:
            if not add_hidden and fname.startswith('.'):
                continue

            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, directory)

            if os.path.getsize(full_path) > max_file_size:
                continue

            if exclude_spec and exclude_spec.match_file(rel_path):
                continue

            if include:
                if not any(fnmatch(fname, pat) for pat in include):
                    continue

            valid_files.append(full_path)
    return valid_files

def do_tree(directory, enc, exclude_spec, include, add_hidden, max_file_size):
    """
    Build and print the tree, copy to clipboard.
    """
    structure = build_tree_structure(
        directory, enc, exclude_spec, include, add_hidden, max_file_size
    )
    # create a "fake root" so the top line is consistent
    top_struct = {
        "name": os.path.basename(directory.rstrip("/")) or directory,
        "size": structure["size"],
        "tokens": structure["tokens"],
        "files": structure["files"],
        "dirs": structure["dirs"]
    }
    lines = format_tree(top_struct, prefix="", is_last=True, max_file_size=max_file_size)
    tree_text = "\n".join(lines)

    print(tree_text)
    try:
        pyperclip.copy(tree_text)
        print("\n(Tree copied to clipboard.)")
    except Exception as e:
        print(f"Could not copy to clipboard: {e}")

def do_tokens(directory, enc, exclude_spec, include, add_hidden, max_file_size):
    """
    Calculate and print the total tokens in the directory (human-readable).
    """
    structure = build_tree_structure(
        directory, enc, exclude_spec, include, add_hidden, max_file_size
    )
    print(f"Estimated total tokens: {human_tokens(structure['tokens'])}")

def do_merge(directory, enc, exclude_spec, include, add_hidden, max_file_size):
    """
    Merge content of all valid files into clipboard.
    Files larger than max_file_size are skipped.
    """
    valid_files = gather_files_for_merge(
        directory, exclude_spec, include, add_hidden, max_file_size
    )
    merged_content = []
    for path in valid_files:
        rel_path = os.path.relpath(path, directory)
        header = (
            f"==============================\n"
            f"File: {rel_path}\n"
            f"==============================\n"
        )
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            merged_content.append(header + content + "\n\n")
        except Exception as e:
            print(f"Error reading {path}: {e}", file=sys.stderr)

    final_text = "".join(merged_content)
    try:
        pyperclip.copy(final_text)
        print("(All file contents merged and copied to clipboard.)")
    except Exception as e:
        print(f"Could not copy to clipboard: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="By default: merges all files (copies to clipboard) + displays tree.\n"
                    "Use --tree for only tree, --tokens for only tokens."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to process (default: current)."
    )
    parser.add_argument(
        "--tree",
        action="store_true",
        help="Display only the ASCII tree (no merge)."
    )
    parser.add_argument(
        "--tokens",
        action="store_true",
        help="Display only the total token count (no merge, no tree)."
    )
    parser.add_argument(
        "--include",
        nargs="*",
        help="Wildcard patterns to include, e.g. --include '*.py' '*.md'."
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        help="Extra exclude patterns (in addition to .gitignore)."
    )
    parser.add_argument(
        "--add-hidden",
        action="store_true",
        help="Include hidden files and directories."
    )
    parser.add_argument(
        "--max-file-size",
        type=int,
        default=20480,
        help="Max file size in bytes (default 20KB)."
    )

    args = parser.parse_args()
    directory = os.path.abspath(args.directory)

    # Build a pathspec for ignoring from .gitignore plus extra excludes
    exclude_spec = load_gitignore_specs(directory, args.exclude)

    # Prepare tokenizer (gpt-4o, fallback to o200k_base)
    try:
        enc = tiktoken.encoding_for_model("gpt-4o")
    except Exception as e:
        print("Could not load tokenizer 'gpt-4o'. Falling back to 'o200k_base'. Error:", e)
        enc = tiktoken.get_encoding("o200k_base")

    # Decide what to do based on flags
    if args.tree and not args.tokens:
        # only tree
        do_tree(directory, enc, exclude_spec, args.include, args.add_hidden, args.max_file_size)
    elif args.tokens and not args.tree:
        # only tokens
        do_tokens(directory, enc, exclude_spec, args.include, args.add_hidden, args.max_file_size)
    else:
        # default => merge + tree
        # or if both --tree and --tokens are given => do both
        if args.tokens:
            do_tokens(directory, enc, exclude_spec, args.include, args.add_hidden, args.max_file_size)
        do_merge(directory, enc, exclude_spec, args.include, args.add_hidden, args.max_file_size)
        do_tree(directory, enc, exclude_spec, args.include, args.add_hidden, args.max_file_size)

if __name__ == "__main__":
    main()
