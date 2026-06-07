#!/usr/bin/env python3
import os
import shutil
import glob

print("=== Starting file copy operation ===\n")

# 1. Copy 007.jpg
src_img = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/uploads/007.jpg'
dst_img = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/007.jpg'

try:
    shutil.copy2(src_img, dst_img)
    print(f"✓ Copied image: {dst_img}")
except Exception as e:
    print(f"✗ Failed to copy image: {e}")

# 2. Search for mask file using glob patterns
print("\n=== Searching for mask files ===")
mask_patterns = [
    '**/mask*.png',
    '**/*mask*.png',
    'data/results/mask_*.png',
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/**/mask*.png'
]

mask_found = False
for pattern in mask_patterns:
    matches = glob.glob(pattern, recursive=True)
    if matches:
        print(f"Pattern '{pattern}' found: {matches}")
        # Try to copy the first match
        for mask_src in matches:
            try:
                dst_mask = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png'
                shutil.copy2(mask_src, dst_mask)
                print(f"✓ Copied mask: {mask_src} → {dst_mask}")
                mask_found = True
                break
            except Exception as e:
                print(f"✗ Failed to copy {mask_src}: {e}")
        if mask_found:
            break

if not mask_found:
    print("✗ Could not find or copy any mask file")

# 3. List final workspace contents
print("\n=== Files in /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace ===")
workspace_files = []
for item in sorted(os.listdir('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace')):
    full_path = os.path.join('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace', item)
    if os.path.isfile(full_path) and (item.endswith('.jpg') or item.endswith('.png')):
        size = os.path.getsize(full_path)
        workspace_files.append(f"{full_path} ({size:,} bytes)")
        print(f"  {full_path} ({size:,} bytes)")

print("\n=== Summary ===")
print(f"Target files in workspace: {len(workspace_files)}")
for f in workspace_files:
    print(f"  - {f}")
