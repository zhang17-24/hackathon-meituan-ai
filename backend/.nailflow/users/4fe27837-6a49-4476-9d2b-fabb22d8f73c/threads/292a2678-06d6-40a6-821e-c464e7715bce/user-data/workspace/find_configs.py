#!/usr/bin/env python3
"""
Comprehensive search for image generation configuration files.
"""

import os
import sys
import json
from pathlib import Path

def find_files_with_keywords(base_path, keywords, extensions):
    """Search for files containing specific keywords."""
    results = []
    
    for root, dirs, files in os.walk(base_path):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for filename in files:
            # Check extension
            if not any(filename.endswith(ext) for ext in extensions):
                continue
                
            filepath = os.path.join(root, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Check for keywords
                    found_keywords = [kw for kw in keywords if kw.lower() in content.lower()]
                    
                    if found_keywords:
                        results.append({
                            'path': filepath,
                            'keywords': found_keywords,
                            'size': len(content)
                        })
            except Exception as e:
                pass
    
    return results

def main():
    print("=" * 80)
    print("IMAGE GENERATION CONFIGURATION SEARCH")
    print("=" * 80)
    
    # Keywords to search for
    keywords = [
        'seedream',
        'doubao', 
        '豆包',
        'model',
        'endpoint',
        'api_key',
        'API_KEY',
        'image_generation',
        'inpaint',
        'nail',
        '美甲'
    ]
    
    # File extensions to check
    extensions = [
        '.py', '.json', '.yaml', '.yml', '.env', '.conf', 
        '.config', '.toml', '.ini', '.txt', '.md'
    ]
    
    # Search paths
    search_paths = [
        '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data/workspace',
        '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data',
    ]
    
    all_results = []
    
    for search_path in search_paths:
        if os.path.exists(search_path):
            print(f"\n🔍 Searching: {search_path}")
            results = find_files_with_keywords(search_path, keywords, extensions)
            all_results.extend(results)
        else:
            print(f"\n⚠️  Path not found: {search_path}")
    
    # Print results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    if all_results:
        # Sort by number of keywords found
        all_results.sort(key=lambda x: len(x['keywords']), reverse=True)
        
        for result in all_results[:20]:  # Show top 20
            print(f"\n📄 {result['path']}")
            print(f"   Size: {result['size']} bytes")
            print(f"   Keywords found: {', '.join(result['keywords'])}")
    else:
        print("\n❌ No files found with relevant keywords")
    
    # Save detailed results
    output_file = '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data/workspace/config_search_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'search_keywords': keywords,
            'total_found': len(all_results),
            'results': all_results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed results saved to: {output_file}")
    
    # Now let's also check environment variables
    print("\n" + "=" * 80)
    print("ENVIRONMENT VARIABLES")
    print("=" * 80)
    
    env_keywords = ['API', 'KEY', 'MODEL', 'ENDPOINT', 'SEEDREAM', 'DOUBAO']
    found_env = []
    
    for key, value in os.environ.items():
        if any(kw in key.upper() for kw in env_keywords):
            found_env.append((key, value))
            print(f"  {key} = {value[:50]}{'...' if len(value) > 50 else ''}")
    
    if not found_env:
        print("  No relevant environment variables found")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
