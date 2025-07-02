import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from utils.backup import backup_database
 
if __name__ == '__main__':
    backup_database() 