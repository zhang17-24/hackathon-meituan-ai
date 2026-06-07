import os
import shutil
import sys

# First, copy 007.jpg
src_img = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/uploads/007.jpg'
dst_img = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/007.jpg'
try:
    shutil.copy2(src_img, dst_img)
    print(f"✓ Copied {src_img} to {dst_img}")
except Exception as e:
    print(f"✗ Failed to copy {src_img}: {e}")

# Search for mask files in accessible directories
mask_found = False
search_paths = [
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/data/results',
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/data/results',
    'data/results',
    './data/results',
]

# Try to find the mask file
for base_path in search_paths:
    try:
        if os.path.exists(base_path):
            print(f"Found directory: {base_path}")
            for filename in os.listdir(base_path):
                if filename.endswith('.png') and 'mask' in filename:
                    src_mask = os.path.join(base_path, filename)
                    dst_mask = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png'
                    shutil.copy2(src_mask, dst_mask)
                    print(f"✓ Copied {src_mask} to {dst_mask}")
                    mask_found = True
                    break
        if mask_found:
            break
    except Exception as e:
        print(f"Error checking {base_path}: {e}")

if not mask_found:
    print("✗ Mask file not found in any of the searched locations")
    print("\nNote: The mask was generated at 'data/results/mask_0d023598.png' by the nail_mask_tool,")
    print("but this path may be relative to a working directory that's not accessible.")

# Verify what's in workspace
print("\nFiles in /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/:")
for item in os.listdir('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace'):
    full_path = os.path.join('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace', item)
    if os.path.isfile(full_path):
        print(f"  - {full_path}")
