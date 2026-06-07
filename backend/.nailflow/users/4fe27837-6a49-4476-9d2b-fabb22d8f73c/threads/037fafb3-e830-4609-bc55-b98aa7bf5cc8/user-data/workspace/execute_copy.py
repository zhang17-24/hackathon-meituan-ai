#!/usr/bin/env python3
"""Execute file copy operations and report results"""
import os
import shutil
import glob
import sys

def copy_with_verification(src, dst):
    """Copy file and verify it exists"""
    try:
        shutil.copy2(src, dst)
        if os.path.exists(dst):
            size = os.path.getsize(dst)
            print(f"✓ SUCCESS: {dst} ({size:,} bytes)")
            return True
        else:
            print(f"✗ FAILED: {dst} not found after copy")
            return False
    except Exception as e:
        print(f"✗ ERROR copying {src} → {dst}: {e}")
        return False

print("=" * 60)
print("COPYING FILES TO WORKSPACE")
print("=" * 60)

# Copy 007.jpg
print("\n1. Copying 007.jpg...")
img_copied = copy_with_verification(
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/uploads/007.jpg',
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/007.jpg'
)

# Search and copy mask file
print("\n2. Searching for mask file...")
mask_copied = False

# Try different possible locations for the mask
mask_search_paths = [
    'data/results/mask_0d023598.png',
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/data/results/mask_0d023598.png',
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/data/results/mask_0d023598.png',
]

for mask_path in mask_search_paths:
    if os.path.exists(mask_path):
        print(f"Found mask at: {mask_path}")
        mask_copied = copy_with_verification(
            mask_path,
            '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png'
        )
        break

if not mask_copied:
    # Try glob search
    for pattern in ['**/mask*.png', 'data/results/*.png']:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            print(f"Found mask via pattern '{pattern}': {matches[0]}")
            mask_copied = copy_with_verification(
                matches[0],
                '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png'
            )
            break

if not mask_copied:
    print("✗ Could not find mask file")

# Final report
print("\n" + "=" * 60)
print("FINAL WORKSPACE CONTENTS")
print("=" * 60)

workspace_files = []
for item in sorted(os.listdir('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace')):
    full_path = os.path.join('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace', item)
    if os.path.isfile(full_path) and (item.endswith('.jpg') or item.endswith('.png')):
        size = os.path.getsize(full_path)
        workspace_files.append(full_path)
        print(f"  {full_path} ({size:,} bytes)")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Image file (007.jpg): {'✓ Present' if img_copied else '✗ Missing'}")
print(f"Mask file (mask.png): {'✓ Present' if mask_copied else '✗ Missing'}")
print(f"\nAbsolute paths in workspace:")
for f in workspace_files:
    print(f"  {f}")

sys.exit(0 if (img_copied and mask_copied) else 1)
