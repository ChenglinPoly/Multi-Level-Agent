
# Default pytest configuration
import sys
from pathlib import Path

# Add the project root to sys.path so we can import modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
