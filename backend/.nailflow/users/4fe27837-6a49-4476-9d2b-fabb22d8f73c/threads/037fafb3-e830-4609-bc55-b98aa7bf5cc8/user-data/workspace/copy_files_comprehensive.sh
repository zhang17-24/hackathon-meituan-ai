#!/bin/bash
# Script to locate and copy mask files to workspace

echo "========================================================================"
echo "FILE LOCATION AND COPY SCRIPT"
echo "========================================================================"

# Define paths
WORKSPACE="/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace"
UPLOADS="/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/uploads"
IMAGE_SRC="$UPLOADS/007.jpg"
IMAGE_DST="$WORKSPACE/007.jpg"
MASK_DST="$WORKSPACE/mask.png"
ORIGINAL_MASK="data/results/mask_6510c2d5.png"

# 1. Copy 007.jpg
echo ""
echo "[1/4] Copying 007.jpg from uploads to workspace..."
if [ -f "$IMAGE_SRC" ]; then
    cp "$IMAGE_SRC" "$IMAGE_DST"
    if [ -f "$IMAGE_DST" ]; then
        SIZE=$(stat -c%s "$IMAGE_DST" 2>/dev/null || stat -f%z "$IMAGE_DST" 2>/dev/null)
        echo "✓ Copied: $IMAGE_DST"
        echo "  Size: $SIZE bytes"
    else
        echo "✗ Failed to copy image"
        exit 1
    fi
else
    echo "✗ Source image not found: $IMAGE_SRC"
    exit 1
fi

# 2. Search for original mask file
echo ""
echo "[2/4] Searching for original mask file: $ORIGINAL_MASK"
MASK_SRC=""

# Try different possible locations
for path in \
    "$ORIGINAL_MASK" \
    "$WORKSPACE/$ORIGINAL_MASK" \
    "/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.deer-flow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/$ORIGINAL_MASK" \
    "./$ORIGINAL_MASK"; do
    if [ -f "$path" ]; then
        MASK_SRC="$path"
        echo "✓ Found: $MASK_SRC"
        break
    fi
done

# If not found, search for any mask file
if [ -z "$MASK_SRC" ]; then
    echo "  Original mask not found, searching for any mask file..."
    MASK_SRC=$(find . -name "mask_*.png" -type f 2>/dev/null | head -1)
    if [ -n "$MASK_SRC" ]; then
        echo "✓ Found alternative: $MASK_SRC"
    fi
fi

# 3. Copy mask file
echo ""
echo "[3/4] Copying mask file to workspace..."
if [ -n "$MASK_SRC" ] && [ -f "$MASK_SRC" ]; then
    cp "$MASK_SRC" "$MASK_DST"
    if [ -f "$MASK_DST" ]; then
        SIZE=$(stat -c%s "$MASK_DST" 2>/dev/null || stat -f%z "$MASK_DST" 2>/dev/null)
        echo "✓ Copied: $MASK_DST"
        echo "  Size: $SIZE bytes"
        echo "  Source: $(realpath "$MASK_SRC" 2>/dev/null || echo "$MASK_SRC")"
    else
        echo "✗ Failed to copy mask"
        exit 1
    fi
else
    echo "✗ No mask file found"
    exit 1
fi

# 4. Final report
echo ""
echo "[4/4] Final workspace contents:"
echo "------------------------------------------------------------------------"
for file in "$IMAGE_DST" "$MASK_DST"; do
    if [ -f "$file" ]; then
        SIZE=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null)
        echo "  $file"
        echo "    Size: $SIZE bytes"
    fi
done

echo ""
echo "========================================================================"
echo "SUMMARY"
echo "========================================================================"
echo ""
echo "Absolute paths of files in workspace:"
echo "  1. $IMAGE_DST"
echo "  2. $MASK_DST"
echo ""
echo "✓ All files successfully copied!"
echo ""
