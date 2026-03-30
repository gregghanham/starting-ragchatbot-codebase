#!/bin/bash
# Frontend quality check script
# Runs Prettier (format check) and ESLint (lint) on all frontend files.
# Usage: ./scripts/quality-check.sh [--fix]
set -e

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$FRONTEND_DIR"

FIX=false
if [[ "${1}" == "--fix" ]]; then
    FIX=true
fi

if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

if $FIX; then
    echo "Auto-formatting with Prettier..."
    npx prettier --write .
    echo "Done. Files have been formatted."
else
    echo "Checking formatting with Prettier..."
    npx prettier --check .

    echo "Linting JavaScript with ESLint..."
    npx eslint script.js

    echo "All checks passed!"
fi
