#!/usr/bin/env python3

import os
import sys
import argparse
import pyperclip
import tiktoken
import re
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern
from fnmatch import fnmatch

DIM = "\033[2m"
RED = "\033[31m"
RESET = "\033[0m"

def load_gitignore_specs(root_dir, extra_excludes=None):
    patterns = []
    gitignore = os.path.join(root_dir, '.gitignore')
    if os.path.isfile(gitignore):
        with open(gitignore, 'r', encoding='utf-8') as f:
            patterns.extend(f.read().splitlines())
    if extra_excludes:
        patterns.extend(extra_excludes)
    return PathSpec.from_lines(GitWildMatchPattern, patterns)

def human_tokens(num):
    if num < 1000:
        return str(num)
    elif num < 10000:
        return f"{num/1000:.1f}k"
    else:
        return f"{num // 1000}k"

def human_size(num_bytes):
    if num_bytes <= 0:
        return "0kb"
    kb = max(1, num_bytes // 1024)
    return f"{kb}kb"

def get_file_tokens(path, enc):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return len(enc.encode(f.read()))
    except:
        return 0

def build_tree_structure(directory, enc, exclude_spec, include, add_hidden, max_file_size):
    name = os.path.basename(directory) or directory
    structure = {"name": name, "path": directory, "files": [], "dirs": [], "tokens": 0, "size": 0}
    try:
        items = sorted(os.listdir(directory))
    except OSError as e:
        print(f"Cannot list directory {directory}: {e}", file=sys.stderr)
        return structure

    for item in items:
        if item.startswith('.') and not add_hidden:
            continue
        full_path = os.path.join(directory, item)
        rel_path = os.path.relpath(full_path, directory)

        if os.path.isdir(full_path):
            if exclude_spec and exclude_spec.match_file(item + "/"):
                continue
            sub = build_tree_structure(full_path, enc, exclude_spec, include, add_hidden, max_file_size)
            structure["dirs"].append(sub)
            structure["tokens"] += sub["tokens"]
            structure["size"] += sub["size"]
        else:
            if exclude_spec and exclude_spec.match_file(rel_path):
                continue
            if include and not any(fnmatch(item, pat) for pat in include):
                continue
            fsize = os.path.getsize(full_path)
            structure["size"] += fsize
            if fsize > max_file_size:
                ftokens = get_file_tokens(full_path, enc) if fsize < 1_000_000 else None
                skipped = True
            else:
                ftokens = get_file_tokens(full_path, enc)
                skipped = False
                structure["tokens"] += ftokens
            structure["files"].append({"name": item, "size": fsize, "tokens": ftokens, "skipped": skipped})
    return structure

def format_tree_for_console(s, prefix="", is_last=True, max_file_size=20480):
    lines = []
    branch = "└──" if is_last else "├──"
    lines.append(f"{prefix}{branch} {s['name']}/"
                 f"{DIM} - {human_size(s['size'])} ~{human_tokens(s['tokens'])} tokens{RESET}")
    next_prefix = prefix + ("    " if is_last else "│   ")
    for i, f in enumerate(s["files"]):
        file_branch = "└──" if (i == len(s["files"]) - 1 and not s["dirs"]) else "├──"
        if f["skipped"]:
            note = f"[skipped because > {human_size(max_file_size)}]"
            line = f"{next_prefix}{file_branch} {RED}{f['name']} - {human_size(f['size'])} {note}"
            if f["tokens"] is not None:
                line += f" ~{human_tokens(f['tokens'])} tokens"
            line += RESET
        else:
            line = (f"{next_prefix}{file_branch} {f['name']}"
                    f"{DIM} - {human_size(f['size'])} ~{human_tokens(f['tokens'])} tokens{RESET}")
        lines.append(line)
    for j, d in enumerate(s["dirs"]):
        sub_last = (j == len(s["dirs"]) - 1)
        lines.extend(format_tree_for_console(d, prefix=next_prefix, is_last=sub_last, max_file_size=max_file_size))
    return lines

def format_tree_for_clipboard(s, prefix="", is_last=True, max_file_size=20480):
    lines = []
    branch = "└──" if is_last else "├──"
    lines.append(f"{prefix}{branch} {s['name']}/ - {human_size(s['size'])}")
    next_prefix = prefix + ("    " if is_last else "│   ")
    for i, f in enumerate(s["files"]):
        file_branch = "└──" if (i == len(s["files"]) - 1 and not s["dirs"]) else "├──"
        if f["skipped"]:
            note = f"[skipped because > {human_size(max_file_size)}]"
            lines.append(f"{next_prefix}{file_branch} {f['name']} - {human_size(f['size'])} {note}")
        else:
            lines.append(f"{next_prefix}{file_branch} {f['name']} - {human_size(f['size'])}")
    for j, d in enumerate(s["dirs"]):
        sub_last = (j == len(s["dirs"]) - 1)
        lines.extend(format_tree_for_clipboard(d, prefix=next_prefix, is_last=sub_last, max_file_size=max_file_size))
    return lines

def gather_files_for_merge(directory, exclude_spec, include, add_hidden, max_file_size):
    valid = []
    for root, dirs, files in os.walk(directory):
        if not add_hidden:
            dirs[:] = [d for d in dirs if not d.startswith('.')]
        for fname in files:
            if not add_hidden and fname.startswith('.'):
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, directory)
            if exclude_spec and exclude_spec.match_file(rel_path):
                continue
            if os.path.getsize(full_path) > max_file_size:
                continue
            if include and not any(fnmatch(fname, pat) for pat in include):
                continue
            valid.append(full_path)
    return valid

def get_merged_content(directory, enc, exclude_spec, include, add_hidden, max_file_size):
    valid_files = gather_files_for_merge(directory, exclude_spec, include, add_hidden, max_file_size)
    merged = []
    for path in valid_files:
        rel_path = os.path.relpath(path, directory)
        header = f"==============================\nFile: {rel_path}\n==============================\n"
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                merged.append(header + f.read() + "\n\n")
        except Exception as e:
            print(f"Error reading {path}: {e}", file=sys.stderr)
    return "".join(merged)

def parse_merged_text(merged_text):
    pattern = r"==============================\nFile: (.*?)\n==============================\n"
    matches = list(re.finditer(pattern, merged_text))
    files = []
    for i in range(len(matches)):
        rel_path = matches[i].group(1)
        start = matches[i].end()
        end = matches[i+1].start() if i+1 < len(matches) else len(merged_text)
        content = merged_text[start:end].strip()
        files.append((rel_path, content))
    return files

def partial_display_merged(merged_text, max_files=3, max_lines=10):
    if not merged_text.strip():
        print("(No merged content to display.)\n")
        return

    files = parse_merged_text(merged_text)
    for i, (rel_path, content) in enumerate(files[:max_files], 1):
        header = f"==============================\nFile: {rel_path}\n==============================\n"
        print(header)
        lines = content.splitlines()
        for line in lines[:max_lines]:
            print(line)
        if len(lines) > max_lines:
            print("... (truncated)\n")
        else:
            print()
    
    total = len(files)
    if total > max_files:
        print(f"Showing {max_files} of {total} files. The full content is in the clipboard.")
    else:
        print(f"All {total} files shown (partially). The full content is in the clipboard.")

def get_tree_texts(directory, enc, exclude_spec, include, add_hidden, max_file_size):
    structure = build_tree_structure(directory, enc, exclude_spec, include, add_hidden, max_file_size)
    top = {
        "name": os.path.basename(directory.rstrip("/")) or directory,
        "size": structure["size"],
        "tokens": structure["tokens"],
        "files": structure["files"],
        "dirs": structure["dirs"]
    }
    console = "\n".join(format_tree_for_console(top, max_file_size=max_file_size))
    cb = "\n".join(format_tree_for_clipboard(top, max_file_size=max_file_size))
    return console, cb

def do_tree(directory, enc, exclude_spec, include, add_hidden, max_file_size):
    console, cb = get_tree_texts(directory, enc, exclude_spec, include, add_hidden, max_file_size)
    print(console)
    try:
        pyperclip.copy(cb)
        print("\n(Tree copied to clipboard.)")
    except Exception as e:
        print(f"Could not copy to clipboard: {e}")

def do_tokens(directory, enc, exclude_spec, include, add_hidden, max_file_size):
    structure = build_tree_structure(directory, enc, exclude_spec, include, add_hidden, max_file_size)
    print(f"Estimated total tokens: {human_tokens(structure['tokens'])}")

def do_merge_and_tree(directory, enc, exclude_spec, include, add_hidden, max_file_size):
    merged_text = get_merged_content(directory, enc, exclude_spec, include, add_hidden, max_file_size)
    console_tree, cb_tree = get_tree_texts(directory, enc, exclude_spec, include, add_hidden, max_file_size)
    final_clipboard = cb_tree + "\n\n" + merged_text
    try:
        pyperclip.copy(final_clipboard)
        print("(Tree + All file contents copied to clipboard.)\n")
    except Exception as e:
        print(f"Could not copy to clipboard: {e}\n")
    print(console_tree)
    print("\nHere is a **partial preview**. The **entire** content is already in your clipboard.\n")
    partial_display_merged(merged_text, max_files=3, max_lines=10)

def main():
    parser = argparse.ArgumentParser(
        description="Code2Clipboard: Scan codebase, tokenize content, generate LLM-ready prompts."
    )
    parser.add_argument('--version', action='version', version=f"Code2Clipboard {__version__}")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to process.")
    parser.add_argument("--tree", action="store_true", help="Only display the ASCII tree.")
    parser.add_argument("--tokens", action="store_true", help="Only display total token count.")
    parser.add_argument("--include", nargs="*", help="Include patterns, e.g., --include '*.py' '*.md'.")
    parser.add_argument("--exclude", nargs="*", help="Extra exclude patterns.")
    parser.add_argument("--add-hidden", action="store_true", help="Include hidden files/folders.")
    parser.add_argument("--max-file-size", type=int, default=20480, help="Max file size in bytes (default 20KB).")
    args = parser.parse_args()

    directory = os.path.abspath(args.directory)
    exclude_spec = load_gitignore_specs(directory, args.exclude)
    try:
        enc = tiktoken.encoding_for_model("gpt-4o")
    except:
        enc = tiktoken.get_encoding("o200k_base")

    if args.tree and not args.tokens:
        do_tree(directory, enc, exclude_spec, args.include, args.add_hidden, args.max_file_size)
    elif args.tokens and not args.tree:
        do_tokens(directory, enc, exclude_spec, args.include, args.add_hidden, args.max_file_size)
    else:
        if args.tokens:
            do_tokens(directory, enc, exclude_spec, args.include, args.add_hidden, args.max_file_size)
        do_merge_and_tree(directory, enc, exclude_spec, args.include, args.add_hidden, args.max_file_size)

if __name__ == "__main__":
    main()
