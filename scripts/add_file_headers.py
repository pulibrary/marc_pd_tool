# lint/add_file_headers.py

# Standard library imports
from os import getcwd
from pathlib import Path
from sys import exit
from typing import List

SEARCH_DIRS = ["tests", "marc_pd_tool", "lint"]


def find_python_files(root_dir: str) -> List[Path]:
    """Find all Python files in specified project directories."""
    files = []
    root = Path(root_dir)
    for dir_name in SEARCH_DIRS:
        if (root / dir_name).exists():
            files.extend(Path(root / dir_name).rglob("*.py"))
    return files


def add_file_header(file_path: Path, project_root: Path) -> bool:
    """Add or update the file path header comment. Returns True if file was modified."""
    relative_path = file_path.relative_to(project_root)
    desired_header = f"# {relative_path}"

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # If header is already correct, no change needed
    if lines and lines[0].strip() == desired_header:
        return False

    # If first line is a path comment, update it
    if lines and lines[0].startswith("# ") and "/" in lines[0]:
        lines[0] = desired_header + "\n"
        if len(lines) == 1 or lines[1].strip():
            lines.insert(1, "\n")
    else:
        # Otherwise prepend the header with a blank line after
        lines.insert(0, desired_header + "\n\n")

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return True


def main():
    """Main script function."""
    project_root = Path(getcwd())
    python_files = find_python_files(project_root)
    updated = 0
    for file_path in python_files:
        if add_file_header(file_path, project_root):
            updated = 1
    exit(updated)


if __name__ == "__main__":
    main()
