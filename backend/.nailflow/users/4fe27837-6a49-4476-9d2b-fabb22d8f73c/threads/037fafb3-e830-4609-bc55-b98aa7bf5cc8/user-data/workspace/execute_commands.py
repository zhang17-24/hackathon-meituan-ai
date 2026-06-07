#!/usr/bin/env python3
import shutil
import os
from pathlib import Path

print("=" * 60)
print("Executing Command 1: Copy 007.jpg")
print("=" * 60)
try:
    src = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/uploads/007.jpg'
    dst = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/007.jpg'
    shutil.copy2(src, dst)
    print(f"✓ Successfully copied {src} to {dst}")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 60)
print("Executing Command 2: Find and copy mask_6510c2d5.png")
print("=" * 60)
mask_found = False
try:
    # Search in /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data first
    for root, dirs, files in os.walk('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data'):
        if 'mask_6510c2d5.png' in files:
            src = os.path.join(root, 'mask_6510c2d5.png')
            dst = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png'
            shutil.copy2(src, dst)
            print(f"✓ Found and copied {src} to {dst}")
            mask_found = True
            break
    
    if not mask_found:
        # Search in / with depth limit
        for root, dirs, files in os.walk('/'):
            depth = root.count(os.sep)
            if depth >= 5:
                dirs.clear()
                continue
            if 'mask_6510c2d5.png' in files:
                src = os.path.join(root, 'mask_6510c2d5.png')
                dst = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png'
                shutil.copy2(src, dst)
                print(f"✓ Found and copied {src} to {dst}")
                mask_found = True
                break
    
    if not mask_found:
        print("⚠ mask_6510c2d5.png not found")
    else:
        print("Done")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 60)
print("Executing Command 3: Verify files")
print("=" * 60)
files_to_check = [
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/007.jpg',
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png'
]

for file_path in files_to_check:
    try:
        stat = os.stat(file_path)
        print(f"✓ {file_path}")
        print(f"  Size: {stat.st_size} bytes")
        print(f"  Modified: {stat.st_mtime}")
    except FileNotFoundError:
        print(f"✗ {file_path} - NOT FOUND")
    except Exception as e:
        print(f"✗ {file_path} - Error: {e}")

print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
print("All requested operations completed.")
