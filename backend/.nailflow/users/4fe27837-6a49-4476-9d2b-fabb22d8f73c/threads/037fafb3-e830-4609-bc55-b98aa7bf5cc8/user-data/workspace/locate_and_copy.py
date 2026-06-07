#!/usr/bin/env python3
import os
import shutil
import glob

print("=" * 70)
print("LOCATING AND COPYING FILES")
print("=" * 70)

# 1. Copy 007.jpg
print("\n[1/3] Copying 007.jpg...")
src_img = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/uploads/007.jpg'
dst_img = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/007.jpg'
try:
    shutil.copy2(src_img, dst_img)
    size = os.path.getsize(dst_img)
    print(f"✓ Copied to: {dst_img}")
    print(f"  Size: {size:,} bytes")
except Exception as e:
    print(f"✗ Error: {e}")

# 2. Search for mask file
print("\n[2/3] Searching for mask file...")
mask_patterns = [
    'data/results/mask_*.png',
    '**/mask_*.png',
    '**/*mask*.png',
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/**/mask_*.png',
]

mask_found = False
for pattern in mask_patterns:
    print(f"  Trying pattern: {pattern}")
    matches = glob.glob(pattern, recursive=True)
    if matches:
        print(f"  ✓ Found: {matches[0]}")
        src_mask = matches[0]
        dst_mask = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png'
        try:
            shutil.copy2(src_mask, dst_mask)
            size = os.path.getsize(dst_mask)
            print(f"✓ Copied to: {dst_mask}")
            print(f"  Size: {size:,} bytes")
            print(f"  Source: {os.path.abspath(src_mask)}")
            mask_found = True
            break
        except Exception as e:
            print(f"✗ Error copying: {e}")

if not mask_found:
    print("✗ Mask file not found with any pattern")
    print("\nAttempting to search common directories...")
    common_dirs = [
        '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data',
        '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace',
        '.',
        os.getcwd(),
    ]
    for base_dir in common_dirs:
        if os.path.exists(base_dir):
            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    if 'mask' in file and file.endswith('.png'):
                        full_path = os.path.join(root, file)
                        print(f"  Found: {full_path}")

# 3. Final report
print("\n[3/3] Final workspace contents:")
print("-" * 70)
workspace_files = []
for filename in sorted(os.listdir('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace')):
    if filename.endswith(('.jpg', '.png')):
        full_path = os.path.join('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace', filename)
        if os.path.isfile(full_path):
            workspace_files.append(full_path)
            size = os.path.getsize(full_path)
            print(f"  {full_path}")
            print(f"    Size: {size:,} bytes")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total files in workspace: {len(workspace_files)}")
for f in workspace_files:
    print(f"  - {f}")
