import shutil
import os
from utils.config import Config
from datetime import datetime

def backup_database():
    src = Config.DATABASE_URL.replace('sqlite:///', '')
    if not os.path.exists(src):
        print('Database file not found.')
        return
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(backup_dir, f'wnba_odds_{timestamp}.db')
    shutil.copy2(src, dst)
    print(f'Backup created: {dst}') 