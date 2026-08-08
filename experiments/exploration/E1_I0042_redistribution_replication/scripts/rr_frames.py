"""E1_I0042 -- frame loading, built ONCE and imported by every later step so they cannot drift.

Both frames are READ-ONLY inputs produced by earlier screens.  Nothing here writes to them.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import rr_base as R  # noqa: E402

# ---- EXPLICIT allowlists, PREREG s2.  Length-asserted.  No substring matching.
U39_KEEP = ("row_uid", "season", "game_id", "team_id", "player_id", "game_date", "appeared",
            "minutes", "pts", "min_hat", "pts_hat", "is_fallback", "fallback_level",
            "n_prior_games", "base5_minutes", "base5_pts", "nprior_minutes", "tg",
            "z_minutes", "z_pts", "established", "freed_minutes", "n_rem", "DECISION")
U39_C = ("u_minutes", "uz_minutes", "u_pts", "uz_pts")
U39_AB = ("depth_bucket", "draft_bucket", "e_full_minutes", "e_full_pts")

REM_KEEP = ("row_uid", "season", "game_id", "team_id", "player_id", "minutes", "pts",
            "min_hat", "pts_hat", "n_prior_games", "base5_minutes", "established",
            "freed_minutes", "n_rem", "u_minutes", "uz_minutes", "z_minutes", "tg")
# ADDED AFTER THE HASH (declared, DEFECTS DEF-1): PREREG s2's REM_KEEP omitted the two POINTS
# redistribution regressors, so anchor A8 (the points channel on REM) could not be built at all.
# This is a column-list omission in the preregistration, not a change of cell or specification.
# It adds no cell and changes no headline; it makes a preregistered anchor runnable.
REM_PTS = ("u_pts", "uz_pts")

RESP = {"minutes": "min_hat", "pts": "pts_hat"}          # explicit dict, 2 entries
assert len(RESP) == 2


def load_u39():
    f = pd.read_parquet(os.path.join(R.SRC_STACK39, "_fit.parquet"))
    R.assert_partition(f, "U39_raw")
    R.assert_allowlist(f, U39_KEEP, 24, "U39_KEEP")
    R.assert_allowlist(f, U39_C, 4, "U39_C")
    R.assert_allowlist(f, U39_AB, 4, "U39_AB")
    f = f[list(U39_KEEP) + list(U39_C) + list(U39_AB)].copy()
    f["season"] = pd.to_numeric(f["season"]).astype(int)
    R.assert_partition(f, "U39")
    return f


def load_rem():
    r = pd.read_parquet(os.path.join(R.SRC_REDIST, "_rem_frame.parquet"))
    R.assert_partition(r, "REM_raw")
    r = r.copy()
    if "tg" not in r.columns:
        r["tg"] = r["game_id"].astype(str) + "_" + r["team_id"].astype(str)
    R.assert_allowlist(r, REM_KEEP, 18, "REM_KEEP")
    R.assert_allowlist(r, REM_PTS, 2, "REM_PTS_added_after_hash")
    r = r[list(REM_KEEP) + list(REM_PTS)].copy()
    r["season"] = pd.to_numeric(r["season"]).astype(int)
    R.assert_partition(r, "REM")
    return r


def vectors(f, treat_min=25.0):
    """Everything the arms need, as explicit named arrays.  `TC` is the published gate."""
    v = {}
    v["season"] = f["season"].to_numpy(int)
    v["tg"] = f["tg"].to_numpy()
    v["freed"] = pd.to_numeric(f["freed_minutes"], errors="coerce").to_numpy(float)
    v["established"] = pd.to_numeric(f["established"], errors="coerce").to_numpy(float) == 1
    v["SCORED"] = np.isin(v["season"], np.array(R.ADMISSIBLE_SCORED))
    if "DECISION" in f.columns:
        v["DECISION"] = f["DECISION"].to_numpy(bool)
    else:
        v["DECISION"] = ((pd.to_numeric(f["n_prior_games"], errors="coerce").to_numpy(float) >= 8)
                         & (pd.to_numeric(f["base5_minutes"], errors="coerce").to_numpy(float) >= 24))
    v["TC"] = (v["freed"] >= treat_min) & v["established"]
    for t, hcol in RESP.items():
        if t not in f.columns or hcol not in f.columns:
            continue
        v["y_" + t] = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
        v["ch_" + t] = pd.to_numeric(f[hcol], errors="coerce").to_numpy(float)
        v["u_" + t] = np.nan_to_num(pd.to_numeric(f["u_" + t], errors="coerce").to_numpy(float))
        v["uz_" + t] = np.nan_to_num(pd.to_numeric(f["uz_" + t], errors="coerce").to_numpy(float))
    return v
