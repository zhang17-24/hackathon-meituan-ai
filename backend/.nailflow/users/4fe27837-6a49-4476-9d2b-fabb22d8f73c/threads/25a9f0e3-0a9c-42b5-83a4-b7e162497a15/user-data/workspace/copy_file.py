#!/usr/bin/env python3
import os
import shutil

# Source and destination paths
source = "/data/results/result_15610b95.jpg"
dest_dir = "/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/outputs"
dest_file = os.path.join(dest_dir, "tryon_result.jpg")

# Step 1: Check if source file exists
print(f"=== Step 1: Checking source file ===")
if os.path.exists(source):
    print(f"✓ Source file found: {source}")
    print(f"  Size: {os.path.getsize(source)} bytes")
else:
    print(f"✗ Source file NOT found at: {source}")
    # Try relative path
    rel_source = "data/results/result_15610b95.jpg"
    if os.path.exists(rel_source):
        source = rel_source
        print(f"✓ Found at relative path: {source}")
    else:
        print("Searching for the file...")
        for root, dirs, files in os.walk("/"):
            if "result_15610b95.jpg" in files:
                source = os.path.join(root, "result_15610b95.jpg")
                print(f"✓ Found at: {source}")
                break
        else:
            print("✗ File not found anywhere. Exiting.")
            exit(1)

# Step 2: Ensure output directory exists
print(f"\n=== Step 2: Ensuring output directory exists ===")
if not os.path.exists(dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    print(f"✓ Created directory: {dest_dir}")
else:
    print(f"✓ Directory already exists: {dest_dir}")

# Step 3: Copy the file
print(f"\n=== Step 3: Copying file ===")
shutil.copy2(source, dest_file)

if os.path.exists(dest_file):
    print(f"✓ Successfully copied to: {dest_file}")
    print(f"  Size: {os.path.getsize(dest_file)} bytes")
else:
    print("✗ Copy failed!")
    exit(1)

print("\n=== Done! ===")
