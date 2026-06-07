import glob
import os

search_roots = [
    '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data',
    '/home/',
    '/tmp/',
    '/var/',
    '/opt/',
    '/app/',
    '.',
    os.path.expanduser('~'),
]

for root in search_roots:
    if not os.path.isdir(root):
        print(f"SKIP (not a dir): {root}")
        continue
    for pattern in ['**/*mask*.png', '**/mask_*.png']:
        results = glob.glob(os.path.join(root, pattern), recursive=True)
        if results:
            print(f"FOUND via {root}/{pattern}:")
            for r in results:
                print(f"  {r}")

# Also try the exact path
exact = 'data/results/mask_6510c2d5.png'
if os.path.exists(exact):
    print(f"FOUND exact: {os.path.abspath(exact)}")
else:
    print(f"NOT FOUND exact: {exact}")

# Try relative from workspace
ws_exact = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/037fafb3-e830-4609-bc55-b98aa7bf5cc8/user-data/workspace/data/results/mask_6510c2d5.png'
if os.path.exists(ws_exact):
    print(f"FOUND: {ws_exact}")
else:
    print(f"NOT FOUND: {ws_exact}")
