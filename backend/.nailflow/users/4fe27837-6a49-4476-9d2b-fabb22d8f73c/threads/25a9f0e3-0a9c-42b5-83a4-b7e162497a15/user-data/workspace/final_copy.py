import shutil
import os

os.makedirs('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/outputs', exist_ok=True)
shutil.copy2('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/workspace/data/results/result_15610b95.jpg', '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/outputs/tryon_result.jpg')
print("Copy successful!")
print(f"File exists: {os.path.exists('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/outputs/tryon_result.jpg')}")
print(f"File size: {os.path.getsize('/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/25a9f0e3-0a9c-42b5-83a4-b7e162497a15/user-data/outputs/tryon_result.jpg')}")
