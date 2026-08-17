"""E1_I0052 s06b -- locate the real decision-stratum columns and E1_I0045's removal flags."""
import os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B

for lbl, rel in [
    ("screen_frame (E0_I0029)", "exploration/E0_I0029_freethrow_hurdle/screen_frame.parquet"),
    ("frame (E1_I0011)", "exploration/E1_I0011_split_alpha/frame.parquet"),
    ("_PF (E1_I0045)", "exploration/E1_I0045_roster_currency/_PF.parquet"),
    ("_player_frame (E1_I0035)", "exploration/E1_I0035_availability_sum/_player_frame.parquet"),
    ("_master_player_partition (E1_I0033)",
     "exploration/E1_I0033_aggregation_level/_master_player_partition.parquet"),
    ("m13 translation_rows", "exploration/MEASURE_F1_m13_fitpool/repro_out/translation_rows.parquet"),
]:
    fp = os.path.join(B.EXP, rel.replace("/", os.sep))
    import pyarrow.parquet as pq
    cols = list(pq.read_schema(fp).names)
    B.banner("%s  (%d cols)" % (lbl, len(cols)))
    print("  " + ", ".join(cols))
