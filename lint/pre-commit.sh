#!/bin/bash

echo "Running pre-commit hooks..."

# Save current staged changes temporarily
echo "Stashing unstaged changes..."
git stash -q --keep-index

# Get the directory of the repository
REPO_DIR=$(git rev-parse --show-toplevel)
cd "$REPO_DIR" || exit 1

# Execute linting and tests
echo "Running formatter..."
pdm run format

FORMATTING=$?

echo "Running mypy..."
pdm run mypy

MYPY=$?

echo "Running pytest..."
pdm run pytest

PYTEST=$?

# Restore unstaged changes
echo "Restoring unstaged changes..."
git stash pop -q

# If any command failed, abort the commit
if [ $FORMATTING -ne 0 ] || [ $MYPY -ne 0 ] || [ $PYTEST -ne 0 ]; then
    echo "Pre-commit hooks failed!"
    if [ $FORMATTING -ne 0 ]; then
        echo "Formatting failed!"
    fi
    if [ $MYPY -ne 0 ]; then
        echo "Type checking failed!"
    fi
    if [ $PYTEST -ne 0 ]; then
        echo "Tests failed!"
    fi
    exit 1
fi

# If any files were changed by formatting, add them to the commit
if git diff --name-only | grep -q '.'; then
    echo "Formatting changed files. Adding them to the commit..."
    git add -u
fi

echo "Pre-commit hooks passed!"
exit 0