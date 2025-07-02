import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from monitors.quality_monitor import QualityMonitor

if __name__ == '__main__':
    # TODO: Load odds data from DB
    records = []
    monitor = QualityMonitor()
    monitor.check_completeness(records, ['game_id', 'home_team', 'away_team', 'price_home', 'price_away'])
    monitor.check_outliers(records, 'price_home', -10000, 10000)
    print(monitor.report()) 