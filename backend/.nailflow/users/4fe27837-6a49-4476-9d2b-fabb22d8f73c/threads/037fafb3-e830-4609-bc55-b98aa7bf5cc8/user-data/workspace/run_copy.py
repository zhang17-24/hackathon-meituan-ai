import shutil
import os
import glob

print("=" * 70)
print("FILE COPY OPERATIONS")
print("=" * 70)

# 1. Copy 007.jpg
print("\n1. Copying 007.jpg from uploads to workspace...")
try:
    shutil.copy2('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/uploads/007.jpg', '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/007.jpg')
    print("✓ Copied: /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/007.jpg")
    img_size = os.path.getsize('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/007.jpg')
    print(f"  Size: {img_size:,} bytes")
except Exception as e:
    print(f"✗ Failed: {e}")

# 2. Search for and copy mask file
print("\n2. Searching for mask file...")
mask_copied = False

# Try the original path first
search_paths = [
    'data/results/mask_6510c2d5.png',
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/data/results/mask_6510c2d5.png',
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/data/results/mask_6510c2d5.png',
]

for mask_path in search_paths:
    if os.path.exists(mask_path):
        print(f"Found at: {mask_path}")
        try:
            shutil.copy2(mask_path, '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png')
            mask_size = os.path.getsize('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png')
            print(f"✓ Copied: /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png")
            print(f"  Size: {mask_size:,} bytes")
            mask_copied = True
            break
        except Exception as e:
            print(f"✗ Failed to copy: {e}")

# If not found, search with glob
if not mask_copied:
    print("Searching with glob patterns...")
    for pattern in ['**/mask*.png', 'data/**/*.png']:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            print(f"Found via '{pattern}': {matches[0]}")
            try:
                shutil.copy2(matches[0], '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png')
                mask_size = os.path.getsize('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png')
                print(f"✓ Copied: /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/mask.png")
                print(f"  Size: {mask_size:,} bytes")
                mask_copied = True
                break
            except Exception as e:
                print(f"✗ Failed to copy: {e}")

if not mask_copied:
    print("✗ Mask file not found anywhere")

# 3. Final report
print("\n" + "=" * 70)
print("FINAL REPORT")
print("=" * 70)
print("\nAbsolute paths in /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/:")

workspace_files = []
for filename in sorted(os.listdir('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace')):
    if filename.endswith('.jpg') or filename.endswith('.png'):
        full_path = os.path.join('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace', filename)
        if os.path.isfile(full_path):
            workspace_files.append(full_path)
            size = os.path.getsize(full_path)
            print(f"  {full_path} ({size:,} bytes)")

print(f"\nTotal image files: {len(workspace_files)}")
