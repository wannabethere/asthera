"""
Script to help migrate LLM calls to traced pattern

This script analyzes files and suggests migration patterns for LLM calls.
Use as a guide - manual review is recommended for each change.
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple


def find_llm_calls(file_path: Path) -> List[Tuple[int, str, str]]:
    """
    Find LLM call patterns in a file
    
    Returns:
        List of (line_number, pattern_type, context)
    """
    patterns = [
        (r'chain\.ainvoke\(', 'async_chain_invoke'),
        (r'chain\.invoke\(', 'sync_chain_invoke'),
        (r'self\.llm\.ainvoke\(', 'direct_async_invoke'),
        (r'self\.llm\.invoke\(', 'direct_sync_invoke'),
        (r'llm\.ainvoke\(', 'llm_async_invoke'),
        (r'llm\.invoke\(', 'llm_sync_invoke'),
    ]
    
    matches = []
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        for line_num, line in enumerate(lines, 1):
            for pattern, pattern_type in patterns:
                if re.search(pattern, line):
                    # Get context (5 lines before and after)
                    start = max(0, line_num - 6)
                    end = min(len(lines), line_num + 5)
                    context = ''.join(lines[start:end])
                    matches.append((line_num, pattern_type, context))
                    
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return matches


def suggest_migration(pattern_type: str, context: str) -> str:
    """Suggest migration pattern based on context"""
    
    # Check if JsonOutputParser is used
    uses_json = 'JsonOutputParser' in context or 'json_parser' in context
    
    # Check if timeout is used
    has_timeout = 'wait_for' in context or 'timeout' in context
    
    suggestion = f"""
Migration Suggestion:
---------------------
Pattern Type: {pattern_type}

1. Add import:
   from app.utils import traced_llm_call

2. Replace with:
   result = await traced_llm_call(
       llm=self.llm,
       prompt=prompt,
       inputs={{...}},
       operation_name="describe_this_operation",
       parse_json={str(uses_json)},"""
    
    if has_timeout:
        suggestion += """
       timeout=30.0,"""
    
    suggestion += """
       metadata={{
           # Add relevant context
           "key": "value"
       }}
   )

3. Remove:
   - chain = prompt | self.llm | parser
   - chain.ainvoke(...)
   - response.content extraction (for string results)
   - Manual logging
   - Timeout handling
"""
    
    return suggestion


def analyze_file(file_path: Path):
    """Analyze a file and print migration suggestions"""
    matches = find_llm_calls(file_path)
    
    if not matches:
        return
    
    print(f"\n{'='*80}")
    print(f"File: {file_path}")
    print(f"Found {len(matches)} LLM call(s)")
    print(f"{'='*80}\n")
    
    for line_num, pattern_type, context in matches:
        print(f"Line {line_num}: {pattern_type}")
        print(f"\nContext:")
        print(context)
        print(suggest_migration(pattern_type, context))
        print(f"\n{'-'*80}\n")


def analyze_directory(directory: Path, pattern: str = "**/*.py"):
    """Analyze all Python files in a directory"""
    files = list(directory.glob(pattern))
    
    print(f"Analyzing {len(files)} files in {directory}")
    print(f"{'='*80}\n")
    
    total_matches = 0
    files_with_matches = []
    
    for file_path in files:
        matches = find_llm_calls(file_path)
        if matches:
            total_matches += len(matches)
            files_with_matches.append((file_path, len(matches)))
    
    print(f"\nSummary:")
    print(f"  Files analyzed: {len(files)}")
    print(f"  Files with LLM calls: {len(files_with_matches)}")
    print(f"  Total LLM calls found: {total_matches}")
    print(f"\nFiles to migrate:\n")
    
    for file_path, count in sorted(files_with_matches, key=lambda x: x[1], reverse=True):
        rel_path = file_path.relative_to(directory)
        print(f"  [{count:3d}] {rel_path}")
    
    return files_with_matches


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python migrate_llm_calls.py <file_path>         # Analyze single file")
        print("  python migrate_llm_calls.py <directory> --all   # Analyze directory")
        sys.exit(1)
    
    target = Path(sys.argv[1])
    
    if not target.exists():
        print(f"Error: {target} does not exist")
        sys.exit(1)
    
    if target.is_file():
        analyze_file(target)
    elif target.is_dir():
        if "--all" in sys.argv:
            analyze_directory(target)
        else:
            print("For directories, use --all flag:")
            print(f"  python migrate_llm_calls.py {target} --all")
    else:
        print(f"Error: {target} is neither a file nor directory")
        sys.exit(1)


if __name__ == "__main__":
    main()
