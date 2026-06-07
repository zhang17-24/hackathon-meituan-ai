#!/usr/bin/env python3
"""
Execute file operations: locate mask file, copy 007.jpg and mask to workspace
"""
import os
import shutil
import glob
from pathlib import Path

def print_header(text):
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)

def print_section(text):
    print("\n" + "-" * 70)
    print(text)
    print("-" * 70)

# Paths
WORKSPACE = Path('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace')
UPLOADS = Path('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/uploads')
IMAGE_SRC = UPLOADS / '007.jpg'
IMAGE_DST = WORKSPACE / '007.jpg'
MASK_DST = WORKSPACE / 'mask.png'
ORIGINAL_MASK = 'data/results/mask_6510c2d5.png'

print_header("FILE LOCATION AND COPY OPERATIONS")

# Step 1: Copy 007.jpg
print_section("Step 1: Copying 007.jpg")
if IMAGE_SRC.exists():
    try:
        shutil.copy2(IMAGE_SRC, IMAGE_DST)
        size = IMAGE_DST.stat().st_size
        print(f"✓ SUCCESS: Copied to {IMAGE_DST}")
        print(f"  Size: {size:,} bytes")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        exit(1)
else:
    print(f"✗ FAILED: Source not found: {IMAGE_SRC}")
    exit(1)

# Step 2: Search for mask file
print_section("Step 2: Searching for mask file")
mask_found = False
mask_src = None

# Try the original path first
search_paths = [
    ORIGINAL_MASK,
    WORKSPACE / ORIGINAL_MASK,
    Path('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data') / ORIGINAL_MASK,
]

print(f"Looking for original: {ORIGINAL_MASK}")
for path in search_paths:
    path = Path(path)
    if path.exists():
        mask_src = path
        print(f"✓ Found at: {path}")
        mask_found = True
        break

# If not found, search with glob
if not mask_found:
    print("\nSearching with glob patterns...")
    patterns = [
        'data/results/mask_*.png',
        '**/mask_*.png',
        '**/*mask*.png',
    ]
    
    for pattern in patterns:
        print(f"  Pattern: {pattern}")
        matches = glob.glob(pattern, recursive=True)
        if matches:
            mask_src = Path(matches[0])
            print(f"  ✓ Found: {mask_src}")
            mask_found = True
            break

if not mask_found:
    print("✗ FAILED: No mask file found anywhere")
    print("\nAttempting deep search...")
    for base in [Path('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data'), Path('.')]:
        if base.exists():
            for png in base.rglob('mask*.png'):
                print(f"  Found: {png}")
                mask_src = png
                mask_found = True
                break
        if mask_found:
            break

# Step 3: Copy mask file
print_section("Step 3: Copying mask file")
if mask_found and mask_src:
    try:
        shutil.copy2(mask_src, MASK_DST)
        size = MASK_DST.stat().st_size
        print(f"✓ SUCCESS: Copied to {MASK_DST}")
        print(f"  Size: {size:,} bytes")
        print(f"  Source: {mask_src.absolute()}")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        exit(1)
else:
    print("✗ FAILED: No mask file to copy")
    exit(1)

# Step 4: Final report
print_section("Step 4: Final Report")
print("\nFiles in workspace:")
workspace_files = []
for item in sorted(WORKSPACE.iterdir()):
    if item.is_file() and item.suffix in ['.jpg', '.png']:
        size = item.stat().st_size
        workspace_files.append((item, size))
        print(f"  {item}")
        print(f"    Size: {size:,} bytes")

print_header("SUMMARY")
print("\n✓ All operations completed successfully!")
print(f"\nAbsolute paths of files in {WORKSPACE}:")
for file_path, size in workspace_files:
    print(f"  {file_path}")
print(f"\nTotal files: {len(workspace_files)}")
print("\n" + "=" * 70 + "\n")
