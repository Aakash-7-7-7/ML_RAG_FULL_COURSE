#!/usr/bin/env python3
"""

python create_struct.py structure.txt 


create_structure.py
--------------------
Reads an ASCII "tree" diagram (like the one `tree` command prints, or the
kind you draw by hand with │ ├── └──) and creates the matching folders and
files on disk.

USAGE
    python create_structure.py structure.txt [target_dir]

    structure.txt  -> path to a text file containing the tree diagram
    target_dir     -> (optional) where to create everything, default = "."

CONVENTION
    - Any entry whose name ends with "/" is treated as a FOLDER.
    - Any entry WITHOUT a trailing "/" is treated as a FILE (created empty).
    - Comments after the entry name (anything starting with "  #") are ignored.
    - Blank lines are ignored.
    - Indentation is read from the tree-drawing characters (│, ├──, └──,
      spaces) - it does NOT need to be perfectly aligned, but each
      indentation "level" must be 4 characters wide, same as the sample
      you gave me (this is how `tree` and most hand-drawn trees format).

This means if you paste a *different* project structure into a text file
using the same drawing style, this same script will build it for you.
"""

import os
import re
import sys

INDENT_UNIT = 4  # width of one nesting level, e.g. "│   ", "    ", "├── ", "└── "
INDENT_TOKENS = {"│   ", "    ", "├── ", "└── "}


def parse_line(raw_line: str):
    """Return (depth, name) for a tree line, or None if the line has no entry."""
    line = raw_line.rstrip("\n").rstrip()
    if not line.strip():
        return None

    # Strip a trailing comment like "   # Electron Desktop App"
    comment_match = re.search(r"\s{2,}#.*$", line)
    if comment_match:
        line = line[: comment_match.start()]

    if not line.strip():
        return None

    content = line
    depth = 0
    while True:
        chunk = content[:INDENT_UNIT]
        if chunk in INDENT_TOKENS:
            depth += 1
            content = content[INDENT_UNIT:]
        else:
            break

    name = content.strip()
    if not name:
        return None
    # A line that's just leftover tree-drawing characters (e.g. a lone "│")
    # is a spacer, not a real entry.
    if re.fullmatch(r"[│─├└\s]+", name):
        return None
    return depth, name


def build_structure(lines, base_dir):
    """Walk the parsed lines and create folders/files under base_dir."""
    # stack[depth] = absolute path of the folder living at that depth
    stack = {}
    created_dirs = 0
    created_files = 0

    for raw_line in lines:
        parsed = parse_line(raw_line)
        if parsed is None:
            continue
        depth, name = parsed

        is_dir = name.endswith("/")
        clean_name = name.rstrip("/")

        parent = stack.get(depth - 1, base_dir) if depth > 0 else base_dir
        full_path = os.path.join(parent, clean_name)

        if is_dir:
            os.makedirs(full_path, exist_ok=True)
            stack[depth] = full_path
            created_dirs += 1
            print(f"[dir ] {full_path}{os.sep}")
        else:
            os.makedirs(parent, exist_ok=True)
            if not os.path.exists(full_path):
                with open(full_path, "w", encoding="utf-8"):
                    pass
            created_files += 1
            print(f"[file] {full_path}")

    return created_dirs, created_files


def main():
    if len(sys.argv) < 2:
        print("Usage: python create_structure.py <structure.txt> [target_dir]")
        sys.exit(1)

    structure_file = sys.argv[1]
    target_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    if not os.path.isfile(structure_file):
        print(f"Error: structure file not found: {structure_file}")
        sys.exit(1)

    os.makedirs(target_dir, exist_ok=True)

    with open(structure_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    dirs, files = build_structure(lines, target_dir)
    print(f"\nDone. Created {dirs} folder(s) and {files} file(s) under '{os.path.abspath(target_dir)}'.")


if __name__ == "__main__":
    main()