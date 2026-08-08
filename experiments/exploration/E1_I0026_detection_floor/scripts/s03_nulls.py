"""s03_nulls.py -- STAGE 1 of the detection-floor study.

Builds the joined frame, records `detect_grouping_level` for both carriers BEFORE any null is
chosen, verifies the fast dR2 against screenkit.delta_r2_plain on real data, and computes the
null draw set for every (stratum, base, null) cell using THE PROGRAMME'S OWN NULLS from
_screen_kit.  Written to disk incrementally.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from df_base import (BASES, CARRIER_OPP, CARRIER_PLAYER, HERE, N_DRAWS, OUT, OUTCOME, SEED,
                     BaseFit, hdr, load_frame, sk, stratum_mask)

t_start = time.time()
hdr("A. FRAME")
f = load_frame(verbose=True)

hdr("B. detect_grouping_level ON BOTH CARRIERS -- recorded BEFORE any null is chosen")
CANDIDATE_KEYS = {
    "row": None,
    "player_game": ["player_id", "game_id"],
    "team_game": ["team_id", "game_id"],
    "opp_team_game": ["opp_team_id", "game_id"],
    "game": ["game_id"],
    "game_date": ["game_date"],
    "player_season": ["player_id", "season"],
    "team_season": ["team_id", "season"],
    "opp_team_season": ["opp_team_id", "season"],
    "season": ["season"],
}
GL = {}
for c in (CARRIER_PLAYER, CARRIER_OPP):
    g = sk.detect_grouping_level(f, c, candidate_keys=CANDIDATE_KEYS, verbose=True)
    GL[c] = dict(g)
    acf = sk.within_group_acf1(f, c, ["player_id", "season"], order_col="game_date")
    GL[c]["acf1_within_player_season"] = acf
    print("  %s: within-player-season acf1 = %s" % (c, acf))

with open(os.path.join(OUT, "s03_grouping_levels.json"), "w", encoding="utf-8") as fh:
    json.dump(GL, fh, indent=2, default=str)

hdr("C. FAST dR2 vs screenkit.delta_r2_plain ON REAL DATA (must agree to ~1e-12)")
_m = stratum_mask(f, "POOLED")
_cols = [OUTCOME] + BASES["B_COMPLETE"] + [CARRIER_PLAYER]
_ok = np.ones(len(f), bool)
for c in _cols:
    _ok &= np.isfinite(pd.to_numeric(f[c], errors="coerce").to_numpy(float))
_y = f.loc[_ok, OUTCOME].to_numpy(float)
_B = f.loc[_ok, BASES["B_COMPLETE"]].to_numpy(float)
_x = f.loc[_ok, CARRIER_PLAYER].to_numpy(float)
_fast = BaseFit(_y, _B).dr2(_x)
_kit = sk.delta_r2_plain(_y, _B, np.column_stack([_B, _x]))
print("  fast=%.12e  kit=%.12e  |diff|=%.3e" % (_fast, _kit, abs(_fast - _kit)))
assert abs(_fast - _kit) < 1e-10, "fast dR2 does not reproduce screenkit.delta_r2_plain"

# ---------------------------------------------------------------------------------------------
hdr("D. NULL DRAW SETS -- the programme's real nulls, %d draws each, seed %d" % (N_DRAWS, SEED))
# ---------------------------------------------------------------------------------------------
NULLS = [
    ("N_A_within_player_cyclic", CARRIER_PLAYER, "perm_cyclic", ["player_id", "season"], None),
    ("N_B_entity_swap_team_season", CARRIER_PLAYER, "entity_swap", ["team_id", "season"], None),
    ("N_C_entity_swap_opp_team_season", CARRIER_OPP, "entity_swap", ["opp_team_id", "season"], None),
    ("N_D_within_date_opp_swap", CARRIER_OPP, "perm_between", ["opp_team_id", "game_id"],
     "game_date"),
    ("N_R_row_level_CONTRAST_ONLY", CARRIER_PLAYER, "perm_row", sk.ROW_LEVEL, None),
    ("N_R_row_level_CONTRAST_ONLY_OPP", CARRIER_OPP, "perm_row", sk.ROW_LEVEL, None),
]
DESIGNS = [(s, b) for s in ("POOLED", "DECISION") for b in ("B_SINGLE", "B_COMPLETE")]

store = {}
meta = []
for sname, bname in DESIGNS:
    basecols = BASES[bname]
    for nname, carrier, kind, level, block in NULLS:
        cols = [OUTCOME] + basecols + [carrier]
        m = stratum_mask(f, sname).copy()
        for c in cols:
            m &= np.isfinite(pd.to_numeric(f[c], errors="coerce").to_numpy(float))
        sub = f.loc[m].reset_index(drop=True)
        sk.assert_partition(sub, verbose=False)
        y = sub[OUTCOME].to_numpy(float)
        B = sub[basecols].to_numpy(float)
        x = sub[carrier].to_numpy(float)
        bf = BaseFit(y, B)
        d = sub[["season", "player_id", "team_id", "opp_team_id", "game_id", "game_date"]].copy()
        d["feat"] = x

        def stat_fn(dfr, _bf=bf):
            return _bf.dr2(pd.to_numeric(dfr["feat"], errors="coerce").to_numpy(float))

        t0 = time.time()
        if kind == "perm_cyclic":
            r = sk.permutation_null(stat_fn, d, level, N_DRAWS, SEED, feature_col="feat",
                                    scheme=sk.SCHEME_WITHIN_CYCLIC, order_col="game_date",
                                    alternative="greater")
        elif kind == "entity_swap":
            r = sk.entity_swap_null(stat_fn, d, level, N_DRAWS, SEED, feature_col="feat",
                                    date_col="game_date", season_col="season",
                                    tiebreak_col="game_id", alternative="greater")
        elif kind == "perm_between":
            r = sk.permutation_null(stat_fn, d, level, N_DRAWS, SEED, feature_col="feat",
                                    scheme=sk.SCHEME_BETWEEN, block_col=block,
                                    alternative="greater")
        elif kind == "perm_row":
            r = sk.permutation_null(stat_fn, d, sk.ROW_LEVEL, N_DRAWS, SEED, feature_col="feat",
                                    alternative="greater")
        else:
            raise KeyError(kind)
        dt = time.time() - t0
        key = "%s|%s|%s" % (sname, bname, nname)
        store[key] = np.asarray(r["draws"], float)
        rec = dict(stratum=sname, base=bname, null=nname, carrier=carrier, kind=kind,
                   level=str(level), block=str(block), n=int(len(sub)),
                   n_groups=int(r.get("n_groups", -1)),
                   real_dr2=float(r["real"]), null_mean=float(r["mean"]),
                   null_sd=float(r["sd"]), p=float(r["p"]),
                   q95_dr2=float(np.nanquantile(store[key], 0.95)),
                   secs=round(dt, 1))
        rec["t_crit_percell"] = ((rec["q95_dr2"] - rec["null_mean"]) / rec["null_sd"]
                                 if rec["null_sd"] > 0 else float("nan"))
        meta.append(rec)
        print("  %-9s %-11s %-32s n=%-6d grp=%-5s real=%.3e mu=%.3e sd=%.3e p=%.4f  %5.1fs"
              % (sname, bname, nname, rec["n"], rec["n_groups"], rec["real_dr2"],
                 rec["null_mean"], rec["null_sd"], rec["p"], dt))

md = pd.DataFrame(meta)
md.to_csv(os.path.join(OUT, "s03_null_meta.csv"), index=False)
np.savez_compressed(os.path.join(OUT, "s03_null_draws.npz"),
                    keys=np.array(list(store.keys())),
                    draws=np.vstack([store[k] for k in store]))
print("\n  wrote s03_null_meta.csv and s03_null_draws.npz   total %.1fs"
      % (time.time() - t_start))
print(md[["stratum", "base", "null", "n", "n_groups", "null_sd", "t_crit_percell"]]
      .to_string(index=False))
