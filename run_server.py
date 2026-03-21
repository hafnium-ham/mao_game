#!/usr/bin/env python3
"""Simple wrapper script to run the Mao game server."""

import sys
from pathlib import Path

# Add the mao_game parent directory to the path
# This allows the mao_game package to be imported properly
parent_dir = Path(__file__).parent
sys.path.insert(0, str(parent_dir))

# Now import and run
if __name__ == "__main__":
    from mao_game.main import main
    main()