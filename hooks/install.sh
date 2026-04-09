#!/bin/bash
# Install git hooks for test quality enforcement

echo "📦 Installing git hooks..."

# Get the repository root
REPO_ROOT="$(git rev-parse --show-toplevel)"

if [ ! -d "$REPO_ROOT/.git/hooks" ]; then
    echo "❌ Error: .git/hooks directory not found"
    exit 1
fi

# Copy pre-commit hook
cp "$REPO_ROOT/hooks/pre-commit" "$REPO_ROOT/.git/hooks/pre-commit"
chmod +x "$REPO_ROOT/.git/hooks/pre-commit"

echo "✅ Pre-commit hook installed successfully"
echo ""
echo "This hook will check for test anti-patterns before each commit."
echo "See TESTING_STANDARDS.md for details on what is checked."
echo ""
echo "To bypass the hook (not recommended): git commit --no-verify"
