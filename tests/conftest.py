import os
import sys

# Add the project root to the sys.path so tests can find core modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
