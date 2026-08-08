"""E1_I0027 s04 -- BUILD AND SCORE THE LADDER on the canonical frame.  Six targets, five rungs.

Re-hashes the frozen spec and asserts equality with s03 before computing anything.
Writes ladder_table.csv and ladder_pairwise.csv.

INFERENCE.  Paired comparisons use the shared screen kit's `paired_forecast_comparison`, which
sign-flips WHOLE CLUSTERS at (season, player_id).  The kit is imported rather than reimplemented
because D096 closed five false-assurance defects in exactly this machinery and the repaired suite
carries 224 assertions; reimplementing it here would forfeit that.  The row-level p is reported
beside every clustered p FOR CONTRAST ONLY.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")
KIT = os.path.join(EXP, "_screen_kit")
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
for p in (HERE, KIT):
    if p not in sys.path:
        sys.path.insert(0, p)
import refladder as RL          # noqa: E402
import screenkit as SK          # noqa: E402

OUT = HERE
CANON_FRAME = os.path.join(EXP, r"E0_I0024_reb_ast_characterisation\screen_frame.parquet")
EVAL_SEASONS = [2023, 2024]
SEED = 20260808
N_DRAWS = 4000


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


hdr("0. re-hash the frozen preregistration")
pre = json.load(open(os.path.join(OUT, "_prereg.json"), encoding="utf-8"))
for t, c in pre["canon"].items():
    RL.CANON[t].update({k: c[k] for k in ("mode", "half_life", "shrink", "k", "floor", "source")})
h = RL.ladder_hash()
print("  frozen sha256 = %s" % pre["sha256"])
print("  re-hashed     = %s" % h)
assert h == pre["sha256"], "LADDER SPEC HAS CHANGED SINCE PREREGISTRATION"
print("  MATCH -- the ladder used below is the one that was frozen.")
print("  kit version marker: %s" % getattr(SK, "__version__", "n/a"))

hdr("1. build every rung for every target")
raw = pd.read_parquet(CANON_FRAME)
rows, pairs = [], []
store = {}
for t in RL.TARGETS:
    rungs, meta = RL.ladder(raw, t, scored_seasons=[2022, 2023, 2024])
    f = meta["frame"]
    y = RL.target_series(f, t)
    ev = f["season"].isin(EVAL_SEASONS).to_numpy()
    store[t] = (rungs, meta, f, y, ev)
    print("\n  target=%-8s grand_fallback_rows=%d  r3_degenerate=%s  r4_scored=%s"
          % (t, meta["grand_fallback_rows"], meta["r3_degenerate_for_this_target"],
             [(d["season"], d.get("n_scored", 0)) for d in meta["r4"]["per_season"]]))
    # ONE denominator for the whole target: SST of y on the eval rows where EVERY rung is finite.
    ok = ev & np.isfinite(y)
    for r in RL.RUNGS:
        v = rungs[r].to_numpy(float)
        if not np.all(np.isnan(v)):
            ok &= np.isfinite(v)
    sst = float(((y[ok] - y[ok].mean()) ** 2).sum())
    print("    common scored rows = %d ; SST = %.6f (this is the ONLY denominator for target %s)"
          % (int(ok.sum()), sst, t))
    for r in RL.RUNGS:
        v = rungs[r].to_numpy(float)
        if np.all(np.isnan(v)):
            rows.append(dict(target=t, rung=r, n_scored=0, mae=np.nan, r2_common_sst=np.nan,
                             skill_vs_R1=np.nan, status="DEGENERATE_FOR_THIS_TARGET"))
            continue
        mae = float(np.mean(np.abs(y[ok] - v[ok])))
        r2 = RL.r2_of_forecast(y[ok], v[ok], sst=sst)
        rows.append(dict(target=t, rung=r, n_scored=int(ok.sum()), mae=mae, r2_common_sst=r2,
                         sst_common=sst, status="ok"))
        print("      %-20s MAE %10.6f   R2(common SST) %+9.6f" % (r, mae, r2))
    base = rungs["R1_PLAYER_EXPAND"].to_numpy(float)
    bmae = float(np.mean(np.abs(y[ok] - base[ok])))
    for d in rows:
        if d["target"] == t and d["status"] == "ok":
            d["skill_vs_R1"] = 1.0 - d["mae"] / bmae

hdr("2. is the ladder actually ordered?  Paired cluster sign-flip, adjacent rungs")
for t in RL.TARGETS:
    rungs, meta, f, y, ev = store[t]
    ok = ev & np.isfinite(y)
    live = [r for r in RL.RUNGS if not np.all(np.isnan(rungs[r].to_numpy(float)))]
    for r in live:
        ok &= np.isfinite(rungs[r].to_numpy(float))
    groups = (f["season"].astype(str) + "_" + f["player_id"].astype(str)).to_numpy()[ok]
    print("\n  target=%s  n=%d  live rungs=%s" % (t, int(ok.sum()), live))
    for a, b in zip(live[1:], live[:-1]):
        res = SK.paired_forecast_comparison(
            y[ok], rungs[a].to_numpy(float)[ok], rungs[b].to_numpy(float)[ok],
            groups=groups, n_draws=N_DRAWS, seed=SEED, name_a=a, name_b=b,
            alternative="two_sided")
        d = dict(res) if isinstance(res, dict) else {"raw": res}
        rec = dict(target=t, rung_a=a, rung_b=b, n=int(ok.sum()))
        for k in ("dr2_a_minus_b", "p_cluster_signflip", "p_two_sided", "p", "p_row_level_NAIVE",
                  "inflation_factor", "n_clusters", "mae_a", "mae_b"):
            if k in d:
                rec[k] = d[k]
        pairs.append(rec)
        print("    %-20s vs %-20s  dR2 %+ .6f   p_cluster %s   p_row_NAIVE %s"
              % (a, b, rec.get("dr2_a_minus_b", float("nan")),
                 rec.get("p_cluster_signflip", rec.get("p", "?")),
                 rec.get("p_row_level_NAIVE", "?")))

hdr("3. write")
lt = pd.DataFrame(rows)
lt.to_csv(os.path.join(OUT, "ladder_table.csv"), index=False)
pd.DataFrame(pairs).to_csv(os.path.join(OUT, "ladder_pairwise.csv"), index=False)
print(lt.to_string())
print("\n  ladder_table.csv, ladder_pairwise.csv written")

hdr("4. the headline of step 1: how much does the reference alone move a skill number?")
sw = []
for t in RL.TARGETS:
    s = lt.loc[(lt.target == t) & (lt.status == "ok")]
    if len(s) < 2:
        continue
    best = s.loc[s.mae.idxmin()]
    worst = s.loc[s.mae.idxmax()]
    sw.append(dict(target=t, weakest_rung=worst.rung, weakest_mae=worst.mae,
                   strongest_rung=best.rung, strongest_mae=best.mae,
                   mae_spread_pct=100.0 * (worst.mae - best.mae) / worst.mae,
                   incumbent_R1_mae=float(s.loc[s.rung == "R1_PLAYER_EXPAND", "mae"].iloc[0]),
                   pct_R1_is_beaten_by_best=100.0 * (
                       float(s.loc[s.rung == "R1_PLAYER_EXPAND", "mae"].iloc[0]) - best.mae)
                       / float(s.loc[s.rung == "R1_PLAYER_EXPAND", "mae"].iloc[0])))
sw = pd.DataFrame(sw)
sw.to_csv(os.path.join(OUT, "reference_spread.csv"), index=False)
print(sw.to_string())
print("\n  reference_spread.csv written")
