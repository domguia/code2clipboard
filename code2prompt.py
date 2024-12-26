#!/usr/bin/env python3

import os
import sys
import argparse
import pyperclip
import tiktoken
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

def load_gitignore_specs(root_dir, extra_excludes=None):
    """
    Returns a pathspec that combines .gitignore patterns plus any extra exclude patterns.
    Uses pathspec to match files we want to skip.
    """
    patterns = []
    gitignore_path = os.path.join(root_dir, '.gitignore')
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            gitignore_lines = f.read().splitlines()
        patterns.extend(gitignore_lines)

    # Extra excludes from CLI
    if extra_excludes:
        patterns.extend(extra_excludes)

    # Construct a pathspec matching Git wildmatch rules
    return PathSpec.from_lines(GitWildMatchPattern, patterns)

def gather_files(
    directory, 
    include=None, 
    exclude_spec=None, 
    add_hidden=False, 
    max_file_size=20480
):
    """
    Yields valid file paths from `directory` based on:
      - `include`: list of wildcard patterns (e.g. ["*.py", "*.md"])
      - `exclude_spec`: a PathSpec object (combining .gitignore + extra excludes)
      - `add_hidden`: if False, skip hidden files/dirs
      - `max_file_size`: skip files bigger than this.
    """
    # Make absolute to ensure pathspec matching works from root_dir
    directory = os.path.abspath(directory)
    for root, dirs, files in os.walk(directory):
        # Remove hidden dirs if not asked to include them
        if not add_hidden:
            dirs[:] = [d for d in dirs if not d.startswith('.')]

        for fname in files:
            # Skip hidden files if not allowed
            if not add_hidden and fname.startswith('.'):
                continue

            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, directory)

            # Skip big files
            if os.path.getsize(full_path) > max_file_size:
                continue

            # Check .gitignore + extra excludes
            # If the pathspec "matches_file", we skip it
            if exclude_spec and exclude_spec.match_file(rel_path):
                continue

            # If user passed --include, only accept if it matches
            if include:
                # If none of the patterns match, skip
                if not any(fnmatch(fname, pat) for pat in include):
                    continue

            yield full_path

def build_directory_tree(directory, add_hidden=False):
    """
    Returns a simple text-based directory tree for display.
    """
    directory = os.path.abspath(directory)
    lines = []

    for root, dirs, files in os.walk(directory):
        if not add_hidden:
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]

        level = root.replace(directory, '').count(os.sep)
        indent = '    ' * level
        folder_name = os.path.basename(root) or os.path.basename(directory)
        lines.append(f"{indent}{folder_name}/")

        sub_indent = '    ' * (level + 1)
        for f in files:
            lines.append(f"{sub_indent}{f}")

    return "\n".join(lines)

# We need fnmatch for simple wildcard matching in gather_files
from fnmatch import fnmatch

def main():
    parser = argparse.ArgumentParser(description="Simple CLI for tokens, tree, merge.")
    parser.add_argument(
        "action",
        choices=["tokens", "tree", "merge"],
        help="Action: tokens (show total tokens), tree (print/copy directory tree), merge (copy all files)."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to process (default: current)."
    )
    parser.add_argument(
        "--include",
        nargs="*",
        help="List of wildcard patterns to include, e.g. --include '*.py' '*.md'."
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

    # Prepare encoder (replace "gpt-4o" with your favorite if you want)
    enc = tiktoken.encoding_for_model("gpt-4o")

    # 1) Gather valid files
    valid_files = list(
        gather_files(
            directory,
            include=args.include,
            exclude_spec=exclude_spec,
            add_hidden=args.add_hidden,
            max_file_size=args.max_file_size
        )
    )

    if args.action == "tokens":
        total_tokens = 0
        for path in valid_files:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
                total_tokens += len(enc.encode(text))
            except Exception as e:
                print(f"Error reading {path}: {e}", file=sys.stderr)

        print(f"Estimated total tokens: {total_tokens}")

    elif args.action == "tree":
        tree_text = build_directory_tree(directory, args.add_hidden)
        print(tree_text)
        try:
            pyperclip.copy(tree_text)
            print("\n(Tree copied to clipboard.)")
        except Exception as e:
            print(f"Could not copy to clipboard: {e}")

    elif args.action == "merge":
        merged_content = []
        for path in valid_files:
            rel_path = os.path.relpath(path, directory)
            header = f"==============================\nFile: {rel_path}\n==============================\n"
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

if __name__ == "__main__":
    main()
