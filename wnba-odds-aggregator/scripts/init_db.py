import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from utils.database import init_db

if __name__ == '__main__':
    init_db() 