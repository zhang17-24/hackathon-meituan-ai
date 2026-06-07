#!/bin/bash
# Search for configuration and image generation files

echo "Searching for relevant files..."
echo "=============================="

# Find Python files in common locations
echo -e "\n1. Python files in /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data/workspace:"
find /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data/workspace -name "*.py" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" 2>/dev/null | head -20

# Search for seedream/doubao references
echo -e "\n2. Files containing 'seedream', 'doubao', or 'model':"
grep -r "seedream\|doubao\|model" /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data/workspace --include="*.py" --include="*.json" --include="*.yaml" -l 2>/dev/null | head -10

# Check for any config files
echo -e "\n3. Configuration files:"
find /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data -name ".env" -o -name "config.*" -o -name "settings.*" 2>/dev/null | head -10

echo -e "\nSearch complete."
