#!/usr/bin/env python3
"""
Fix relative imports to absolute imports in app/ directory
"""
import re
import sys
from pathlib import Path


def fix_imports_in_file(file_path: Path) -> int:
    """
    Fix relative imports to absolute imports in a file
    
    Returns:
        Number of imports fixed
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        fixes = 0
        
        # Get the module path from file path
        # e.g., app/assistants/nodes.py -> app.assistants
        parts = file_path.parts
        app_index = parts.index('app')
        module_parts = parts[app_index:-1]  # Exclude filename
        
        # Pattern: from .module import ...
        # Replace with: from app.parent.module import ...
        
        # Single dot imports: from .module import
        pattern = r'^from \.([a-zA-Z_][a-zA-Z0-9_]*) import'
        
        def replacer(match):
            nonlocal fixes
            module_name = match.group(1)
            parent_module = '.'.join(module_parts)
            new_import = f'from {parent_module}.{module_name} import'
            fixes += 1
            return new_import
        
        content = re.sub(pattern, replacer, content, flags=re.MULTILINE)
        
        # Write back if changed
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            return fixes
        
        return 0
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return 0


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python fix_imports.py <directory|file>")
        sys.exit(1)
    
    target = Path(sys.argv[1])
    
    if not target.exists():
        print(f"Error: {target} does not exist")
        sys.exit(1)
    
    # Collect files
    if target.is_file():
        files = [target]
    else:
        files = list(target.rglob("*.py"))
    
    print(f"Processing {len(files)} Python files...")
    
    total_fixes = 0
    files_fixed = 0
    
    for file_path in files:
        fixes = fix_imports_in_file(file_path)
        if fixes > 0:
            total_fixes += fixes
            files_fixed += 1
            print(f"  ✓ {file_path.relative_to(target.parent if target.is_file() else target)}: {fixes} imports fixed")
    
    print(f"\nSummary:")
    print(f"  Files processed: {len(files)}")
    print(f"  Files fixed: {files_fixed}")
    print(f"  Total imports fixed: {total_fixes}")


if __name__ == "__main__":
    main()
