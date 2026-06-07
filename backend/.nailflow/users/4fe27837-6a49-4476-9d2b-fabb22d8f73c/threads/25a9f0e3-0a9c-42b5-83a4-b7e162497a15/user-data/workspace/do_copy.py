#!/usr/bin/env python3
import os
import shutil

source = "/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/workspace/data/results/result_15610b95.jpg"
dest_dir = "/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/outputs"
dest_file = os.path.join(dest_dir, "tryon_result.jpg")

# Ensure output directory exists
os.makedirs(dest_dir, exist_ok=True)

# Copy the file
shutil.copy2(source, dest_file)

# Verify
if os.path.exists(dest_file):
    size = os.path.getsize(dest_file)
    print(f"SUCCESS: Copied to {dest_file}")
    print(f"Size: {size} bytes ({size/1024:.1f} KB)")
else:
    print("FAILED: Copy did not succeed")
