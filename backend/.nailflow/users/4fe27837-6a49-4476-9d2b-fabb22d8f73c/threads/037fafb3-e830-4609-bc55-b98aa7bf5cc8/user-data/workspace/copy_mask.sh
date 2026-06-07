#!/bin/bash
# Copy the mask file to workspace
if [ -f "data/results/mask_0d023598.png" ]; then
    cp data/results/mask_0d023598.png /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png
    echo "✓ Copied data/results/mask_0d023598.png to /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png"
else
    echo "✗ Mask file not found at data/results/mask_0d023598.png"
    echo "Trying to find it..."
    find . -name "mask_*.png" -type f 2>/dev/null | head -5
fi

# List workspace contents
echo ""
echo "Files in /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/:"
ls -la /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/*.jpg /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/*.png 2>/dev/null | grep -E '\.(jpg|png)$'
