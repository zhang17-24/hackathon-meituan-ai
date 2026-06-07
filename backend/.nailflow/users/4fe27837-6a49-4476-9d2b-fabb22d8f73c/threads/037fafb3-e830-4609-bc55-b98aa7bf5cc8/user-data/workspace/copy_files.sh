#!/bin/bash
# Copy 007.jpg to workspace
cp /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/uploads/007.jpg /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/007.jpg
echo "Copied 007.jpg to workspace"

# Try to find and copy the mask file
if [ -f "data/results/mask_0d023598.png" ]; then
    cp data/results/mask_0d023598.png /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png
    echo "Copied mask from relative path"
elif [ -f "/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/data/results/mask_0d023598.png" ]; then
    cp /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/data/results/mask_0d023598.png /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png
    echo "Copied mask from workspace/data"
else
    echo "Mask file not found at expected locations"
fi

# List workspace contents
ls -la /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace
