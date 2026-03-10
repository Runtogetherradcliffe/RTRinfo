#!/bin/bash

# Navigate to the RTR site folder
cd "$(dirname "$0")"

# Add all changes
git add .

# Commit with a timestamp
git commit -m "Weekly roundup update – $(date '+%d %b %Y')"

# Push to GitHub
git push origin main

echo ""
echo "✅ Published! Changes are live at https://runtogetherradcliffe.github.io/RTRinfo/"
echo ""
read -p "Press Enter to close..."
