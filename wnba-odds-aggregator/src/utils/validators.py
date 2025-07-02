import re
from datetime import datetime

def validate_team_name(name):
    return isinstance(name, str) and len(name) > 0

def validate_odds_value(value):
    try:
        return value is None or (isinstance(value, (int, float)) and -10000 < value < 10000)
    except Exception:
        return False

def validate_datetime(dt):
    if isinstance(dt, datetime):
        return True
    try:
        datetime.fromisoformat(dt)
        return True
    except Exception:
        return False 