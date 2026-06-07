#!/usr/bin/env python3
"""Deep environment and module inspection."""
import os
import sys
import importlib
import inspect
import json

results = {}

# 1. All environment variables
results['all_env_vars'] = dict(os.environ)

# 2. Python path
results['python_path'] = sys.path

# 3. Try to import and inspect tool modules
tool_module_names = [
    'nailflow', 'nail_flow', 'tools', 'app', 'agent',
    'image_generation', 'seedream', 'doubao',
    'nail_tools', 'nail_config', 'config',
    'hand_detect', 'nail_mask', 'style_understanding',
    'prompt_builder', 'quality_check',
]

results['importable_modules'] = {}
results['failed_imports'] = {}

for mod_name in tool_module_names:
    try:
        mod = importlib.import_module(mod_name)
        mod_file = getattr(mod, '__file__', 'N/A')
        members = [m for m in dir(mod) if not m.startswith('_')]
        results['importable_modules'][mod_name] = {
            'file': mod_file,
            'members': members[:30]
        }
    except Exception as e:
        results['failed_imports'][mod_name] = str(e)

# 4. Check for loaded modules that might be related
results['loaded_modules'] = [
    name for name in sorted(sys.modules.keys())
    if any(kw in name.lower() for kw in ['nail', 'seed', 'doubao', 'image_gen', 'tool', 'ark', 'volc'])
]

# 5. Check cwd and its contents recursively
cwd = os.getcwd()
results['cwd'] = cwd

# 6. Try to find any .env files
import glob
for base in ['/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data/workspace', '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data', '/app', '/src', cwd]:
    try:
        env_files = glob.glob(os.path.join(base, '**', '.env*'), recursive=True)
        if env_files:
            results[f'env_files_in_{base}'] = env_files
    except:
        pass

# Output
output_path = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data/workspace/inspection_results.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False, default=str)

print(f"Results saved to {output_path}")
print(f"\nKey findings:")
print(f"  CWD: {cwd}")
print(f"  Python path entries: {len(sys.path)}")
print(f"  Importable modules: {list(results['importable_modules'].keys())}")
print(f"  Loaded related modules: {results['loaded_modules']}")
print(f"  Failed imports: {len(results['failed_imports'])}")
