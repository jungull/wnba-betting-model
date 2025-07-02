#!/usr/bin/env python3
"""
Runner script for advanced opponent strength normalization.
This script applies sophisticated opponent strength normalization using:
- Multiple defensive metrics (defensive efficiency, steal rate, block rate, etc.)
- 10-game lookback with weighted recent performance (past 5 games weighted 1.5x)
- Historical defensive ratings instead of single-game performance
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from build_advanced_opponent_normalization import main

if __name__ == "__main__":
    print("=== Running Advanced Opponent Strength Normalization ===")
    print("This will:")
    print("1. Load all game data")
    print("2. Calculate defensive metrics for each team-game")
    print("3. Build weighted defensive ratings (10-game lookback, recent 5 weighted 1.5x)")
    print("4. Apply advanced normalization to player stats")
    print("5. Save enhanced player features")
    print()
    
    result = main()
    
    if result is not None:
        print("\n✅ Advanced normalization completed successfully!")
        print(f"Generated {len(result)} normalized player-game records")
    else:
        print("\n❌ Advanced normalization failed!")
        sys.exit(1) 