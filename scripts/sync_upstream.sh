#!/bin/bash
# sync_upstream.sh - Repeatable script to sync fork branch with upstream main

set -e

REPO_DIR="/Users/ghchinoy/projects/vertex-ai-creative-studio"
UPSTREAM_REMOTE="upstream"
UPSTREAM_BRANCH="main"

echo "Checking current branch status..."
CURRENT_BRANCH=$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD)
echo "Current branch: $CURRENT_BRANCH"

echo "Fetching latest changes from $UPSTREAM_REMOTE..."
git -C "$REPO_DIR" fetch "$UPSTREAM_REMOTE"

echo "Attempting to merge $UPSTREAM_REMOTE/$UPSTREAM_BRANCH into $CURRENT_BRANCH..."
# We use --no-commit to allow review and mandatory ruff pass before finalizing
if git -C "$REPO_DIR" merge "$UPSTREAM_REMOTE/$UPSTREAM_BRANCH" --no-commit --no-ff; then
    echo "Merge successful (staged, not committed)."
else
    echo "CONFLICTS detected. Please resolve them manually in $REPO_DIR."
    echo "After resolving conflicts, run: uv run ruff format . && uv run ruff check --fix ."
    echo "Then commit the changes."
    exit 1
fi

echo "Running mandatory v2.0 baseline linting and formatting..."
cd "$REPO_DIR"
uv run ruff format .
uv run ruff check --fix .

echo "Sync complete. Please review the changes and commit them."
