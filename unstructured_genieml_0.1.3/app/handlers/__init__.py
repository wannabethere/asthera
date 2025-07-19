"""
Handlers for various API operations.
"""
import sys
import os
from pathlib import Path

# Add agents_test to Python path if it's not already there
root_dir = Path(__file__).parent.parent.parent
agents_test_path = os.path.join(root_dir, "agents_test")
if agents_test_path not in sys.path:
    sys.path.append(str(root_dir))

# Add app/agentic to Python path if it's not already there
agents_path = os.path.join(root_dir, "app", "agentic")
if agents_path not in sys.path:
    sys.path.append(agents_path) 