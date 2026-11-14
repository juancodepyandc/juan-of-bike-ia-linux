#!/bin/bash
set -e

echo "🔄 Fetching latest changes from origin..."
git fetch origin

echo "🔀 Merging latest changes..."
# Adjust 'main' to your default branch if it's different (e.g., 'master')
git merge origin/main

echo "📦 Installing dependencies..."
cd application && npm install

echo "✅ Running typecheck..."
npm run typecheck

echo "🚀 Update and merge completed successfully!"
