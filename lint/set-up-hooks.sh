#!/bin/bash

# Script to set up Git hooks

REPO_ROOT=$(git rev-parse --show-toplevel)
HOOK_DIR="$REPO_ROOT/.git/hooks"
SCRIPT_DIR="$REPO_ROOT/lint"

echo "Setting up Git hooks..."

# Create hooks directory if it doesn't exist
mkdir -p "$HOOK_DIR"

# Create symlink for pre-commit hook
ln -sf ../../lint/pre-commit.sh "$HOOK_DIR/pre-commit"
chmod +x "$SCRIPT_DIR/pre-commit.sh"

echo "Git hooks setup complete!"
echo "Pre-commit hook will run formatter, type checker, and tests before each commit."