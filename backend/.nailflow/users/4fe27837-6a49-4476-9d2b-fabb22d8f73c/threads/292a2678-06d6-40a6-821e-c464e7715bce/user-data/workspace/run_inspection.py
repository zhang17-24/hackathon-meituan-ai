#!/usr/bin/env python3
"""Run the deep inspection."""
import subprocess
import sys

# Execute the inspection script
result = subprocess.run(
    [sys.executable, '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data/workspace/deep_inspect.py'],
    capture_output=True,
    text=True
)

print("STDOUT:")
print(result.stdout)

if result.stderr:
    print("\nSTDERR:")
    print(result.stderr)

print(f"\nReturn code: {result.returncode}")
