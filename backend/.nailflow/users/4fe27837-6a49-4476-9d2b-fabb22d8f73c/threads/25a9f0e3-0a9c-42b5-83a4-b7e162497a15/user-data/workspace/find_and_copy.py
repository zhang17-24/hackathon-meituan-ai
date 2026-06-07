#!/usr/bin/env python3
import os
import shutil
import subprocess

print("=" * 60)
print("Searching for result_15610b95.jpg")
print("=" * 60)

# Method 1: Use find command
print("\n1. Using find command to search entire filesystem...")
try:
    result = subprocess.run(
        ['find', '/', '-name', 'result_15610b95.jpg', '-type', 'f'],
        capture_output=True,
        text=True,
        timeout=30
    )
    found_paths = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
    print(f"   Found {len(found_paths)} matches:")
    for p in found_paths:
        print(f"   - {p}")
        if os.path.exists(p):
            size = os.path.getsize(p)
            print(f"     Size: {size} bytes")
except Exception as e:
    print(f"   Error: {e}")
    found_paths = []

# Method 2: Check common locations
print("\n2. Checking common locations...")
common_paths = [
    "/data/results/result_15610b95.jpg",
    "/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/data/results/result_15610b95.jpg",
    "/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/workspace/data/results/result_15610b95.jpg",
    "/tmp/data/results/result_15610b95.jpg",
    "/home/data/results/result_15610b95.jpg",
    "./data/results/result_15610b95.jpg",
]

for path in common_paths:
    if os.path.exists(path):
        print(f"   ✓ Found: {path}")
        if path not in found_paths:
            found_paths.append(path)
    else:
        print(f"   ✗ Not found: {path}")

# Method 3: Check if data directory exists anywhere
print("\n3. Searching for 'data/results' directories...")
try:
    result = subprocess.run(
        ['find', '/', '-type', 'd', '-path', '*/data/results'],
        capture_output=True,
        text=True,
        timeout=30
    )
    data_dirs = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
    print(f"   Found {len(data_dirs)} data/results directories:")
    for d in data_dirs:
        print(f"   - {d}")
        # List contents
        try:
            files = os.listdir(d)
            print(f"     Contents: {files[:10]}")
        except:
            pass
except Exception as e:
    print(f"   Error: {e}")

# Copy the file if found
print("\n" + "=" * 60)
print("Copying to /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/outputs/tryon_result.jpg")
print("=" * 60)

dest_dir = "/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/outputs"
dest_file = os.path.join(dest_dir, "tryon_result.jpg")

# Ensure output directory exists
if not os.path.exists(dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    print(f"Created output directory: {dest_dir}")

if found_paths:
    source = found_paths[0]
    print(f"\nCopying from: {source}")
    try:
        shutil.copy2(source, dest_file)
        if os.path.exists(dest_file):
            size = os.path.getsize(dest_file)
            print(f"✓ Successfully copied to: {dest_file}")
            print(f"  Size: {size} bytes")
        else:
            print("✗ Copy failed - destination file not created")
    except Exception as e:
        print(f"✗ Copy error: {e}")
else:
    print("\n✗ File not found anywhere on the system")
    print("\nPossible reasons:")
    print("  1. The tryon tool hasn't been run yet")
    print("  2. The file was generated in a different session/container")
    print("  3. The path 'data/results/result_15610b95.jpg' is relative to a different working directory")
