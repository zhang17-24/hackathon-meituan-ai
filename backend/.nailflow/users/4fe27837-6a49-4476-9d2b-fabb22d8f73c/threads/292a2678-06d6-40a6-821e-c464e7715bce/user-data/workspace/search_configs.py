#!/usr/bin/env python3
"""Search for configuration files and image generation related files."""

import os
import glob
from pathlib import Path

def search_files():
    """Search for relevant configuration and code files."""
    
    search_paths = [
        '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data/workspace',
        '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data',
        '/app',
        '/src',
        '/opt',
        '/usr/local/lib/python3.11/site-packages',
    ]
    
    # File patterns to search for
    config_patterns = [
        '*.env',
        '*.yaml',
        '*.yml',
        '*.json',
        '*.py',
        '*.conf',
        '*.config',
        '*.toml',
        '*.ini'
    ]
    
    # Keywords to search for in file contents
    keywords = [
        'seedream',
        'doubao',
        'model',
        'endpoint',
        'api_key',
        'image_generation',
        'nail',
        'inpaint'
    ]
    
    found_files = []
    keyword_matches = {}
    
    print("=" * 80)
    print("SEARCHING FOR CONFIGURATION AND IMAGE GENERATION FILES")
    print("=" * 80)
    
    for base_path in search_paths:
        if not os.path.exists(base_path):
            print(f"\n⚠️  Path not found: {base_path}")
            continue
            
        print(f"\n📁 Searching in: {base_path}")
        
        for pattern in config_patterns:
            search_pattern = os.path.join(base_path, '**', pattern)
            matches = glob.glob(search_pattern, recursive=True)
            
            for filepath in matches:
                found_files.append(filepath)
                
                # Check file contents for keywords
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        
                        for keyword in keywords:
                            if keyword.lower() in content:
                                if filepath not in keyword_matches:
                                    keyword_matches[filepath] = []
                                if keyword not in keyword_matches[filepath]:
                                    keyword_matches[filepath].append(keyword)
                except Exception as e:
                    pass
    
    print("\n" + "=" * 80)
    print("FOUND FILES")
    print("=" * 80)
    
    if found_files:
        for f in sorted(set(found_files))[:50]:  # Limit output
            print(f"  {f}")
    else:
        print("  No files found")
    
    print("\n" + "=" * 80)
    print("KEYWORD MATCHES")
    print("=" * 80)
    
    if keyword_matches:
        for filepath, keywords_found in sorted(keyword_matches.items()):
            print(f"\n  📄 {filepath}")
            print(f"     Keywords: {', '.join(keywords_found)}")
    else:
        print("  No keyword matches found")
    
    return found_files, keyword_matches

if __name__ == '__main__':
    search_files()
