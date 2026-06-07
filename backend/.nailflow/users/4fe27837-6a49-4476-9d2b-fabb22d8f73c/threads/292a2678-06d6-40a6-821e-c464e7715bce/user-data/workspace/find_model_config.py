#!/usr/bin/env python3
"""
Search for model configuration files containing seedream or doubao references.
"""

import os
import sys
import glob
from pathlib import Path

def search_for_model_config():
    """Search for files containing model configuration."""
    
    print("=" * 80)
    print("SEARCHING FOR MODEL CONFIGURATION")
    print("=" * 80)
    
    # Search patterns
    search_locations = [
        '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data/workspace',
        '/Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend/.nailflow/users/4fe27837-6a49-4476-9d2b-fabb22d8f73c/threads/292a2678-06d6-40a6-821e-c464e7715bce/user-data',
        '/app',
        '/usr/local/lib/python3.11/site-packages',
        '/usr/local/lib/python3.11/dist-packages',
        '/opt',
        '/etc',
        '/root',
        os.path.expanduser('~'),
        os.getcwd(),
    ]
    
    # File patterns to search
    file_patterns = [
        '*.py', '*.json', '*.yaml', '*.yml', '*.env', 
        '*.conf', '*.config', '*.toml', '*.ini'
    ]
    
    # Keywords to find
    keywords = [
        'seedream',
        'doubao',
        'doubao-seedream',
        'SEEDREAM',
        'DOUBAO',
        'model_name',
        'endpoint',
        'API_KEY',
        'api_key',
        'ARK_API_KEY',
        'VOLC_ACCESSKEY',
    ]
    
    found_files = []
    
    for location in search_locations:
        if not os.path.exists(location):
            continue
            
        print(f"\n🔍 Searching: {location}")
        
        for pattern in file_patterns:
            search_path = os.path.join(location, '**', pattern)
            try:
                for filepath in glob.glob(search_path, recursive=True):
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            found_keywords = [kw for kw in keywords if kw.lower() in content.lower()]
                            
                            if found_keywords:
                                found_files.append({
                                    'path': filepath,
                                    'keywords': found_keywords,
                                    'size': os.path.getsize(filepath)
                                })
                                print(f"  ✓ Found: {filepath}")
                                print(f"    Keywords: {', '.join(found_keywords)}")
                    except Exception as e:
                        pass
            except Exception as e:
                pass
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if found_files:
        print(f"\n✓ Found {len(found_files)} files with model configuration:")
        for f in found_files[:10]:
            print(f"\n  📄 {f['path']}")
            print(f"     Keywords: {', '.join(f['keywords'])}")
            
            # Try to read and show relevant sections
            try:
                with open(f['path'], 'r', encoding='utf-8') as file:
                    lines = file.readlines()
                    print(f"     Lines: {len(lines)}")
                    
                    # Show lines with keywords
                    for i, line in enumerate(lines):
                        if any(kw.lower() in line.lower() for kw in keywords):
                            print(f"     Line {i+1}: {line.strip()[:100]}")
            except:
                pass
    else:
        print("\n❌ No configuration files found with model keywords")
    
    # Also check environment variables
    print("\n" + "=" * 80)
    print("ENVIRONMENT VARIABLES")
    print("=" * 80)
    
    env_keywords = ['API', 'KEY', 'MODEL', 'ENDPOINT', 'SEEDREAM', 'DOUBAO', 'ARK', 'VOLC']
    found_env = []
    
    for key, value in os.environ.items():
        if any(kw in key.upper() for kw in env_keywords):
            found_env.append((key, value))
            # Mask sensitive values
            if 'KEY' in key.upper() or 'SECRET' in key.upper() or 'TOKEN' in key.upper():
                display_value = value[:8] + '...' if len(value) > 8 else value
            else:
                display_value = value
            print(f"  {key} = {display_value}")
    
    if not found_env:
        print("  No relevant environment variables found")
    
    print("\n" + "=" * 80)
    
    return found_files

if __name__ == '__main__':
    search_for_model_config()
