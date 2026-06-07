#!/bin/bash
set -e

echo "=== Step 1: Searching for source file ==="
SOURCE_FILE=$(find / -name "result_15610b95.jpg" 2>/dev/null | head -1)

if [ -z "$SOURCE_FILE" ]; then
    echo "ERROR: File 'result_15610b95.jpg' not found anywhere on the system."
    echo "Searched in: /data, /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data, /home, /tmp, /var, /opt"
    
    # Also check the exact path mentioned
    if [ -f "data/results/result_15610b95.jpg" ]; then
        SOURCE_FILE="data/results/result_15610b95.jpg"
        echo "Found at relative path: $SOURCE_FILE"
    else
        exit 1
    fi
fi

echo "Found source file at: $SOURCE_FILE"

echo ""
echo "=== Step 2: Ensure outputs directory exists ==="
OUTPUT_DIR="/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/outputs"
if [ ! -d "$OUTPUT_DIR" ]; then
    mkdir -p "$OUTPUT_DIR"
    echo "Created directory: $OUTPUT_DIR"
else
    echo "Directory already exists: $OUTPUT_DIR"
fi

echo ""
echo "=== Step 3: Copying file ==="
cp "$SOURCE_FILE" "$OUTPUT_DIR/tryon_result.jpg"

if [ -f "$OUTPUT_DIR/tryon_result.jpg" ]; then
    echo "SUCCESS: File copied to $OUTPUT_DIR/tryon_result.jpg"
    ls -lh "$OUTPUT_DIR/tryon_result.jpg"
else
    echo "ERROR: Copy failed."
    exit 1
fi
