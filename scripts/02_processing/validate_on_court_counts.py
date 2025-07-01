import sys
import os
import importlib.util
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import pandas as pd
import numpy as np
import glob

# Dynamically import build_possession_based_features.py as bpf
spec = importlib.util.spec_from_file_location("bpf", os.path.join(os.path.dirname(__file__), "build_possession_based_features.py"))
if spec is None or spec.loader is None:
    raise ImportError("Could not load build_possession_based_features.py")
bpf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bpf)

files = sorted(glob.glob('data/playbyplay/*.parquet'))[:5]
for f in files:
    print(f'\nChecking {f}')
    pbp = pd.read_parquet(f)
    on_court_by_event = bpf.track_on_court(pbp)
    possessions = bpf.track_possessions(pbp, on_court_by_event)
    counts = [len(p['on_court']) for p in possessions]
    print('Possessions:', len(counts), 'Min:', np.min(counts), 'Max:', np.max(counts), 'Mean:', np.mean(counts))
    not5 = [i for i, c in enumerate(counts) if c != 5]
    print('Any not 5:', bool(not5))
    if not5:
        print('First not 5 indices:', not5[:10])
        for idx in not5[:5]:
            print(f'  Possession {idx}: on_court={possessions[idx]["on_court"]}') 