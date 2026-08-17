#!/usr/bin/env python3
"""s01 — reproduce prior-screen anchors EXACTLY before any new statistic.

Recomputed from stored frames, never transcribed from prose.
Read-only. Writes only inside E1_I0048_shipped_roster_path/.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent.parent.parent            # worktree root
I0045 = HERE.parent / "E1_I0045_roster_currency"
OUT = HERE

rows = []


def anchor(aid, what, mine, published, tol=0.0):
    d = abs(float(mine) - float(published))
    ok = d <= tol
    rows.append({"anchor_id": aid, "quantity": what, "mine": mine,
                 "published": published, "abs_diff": d, "tolerance": tol,
                 "confirmed": bool(ok)})
    print(f"  [{'OK ' if ok else 'FAIL'}] {aid} {what}: mine={mine} "
          f"published={published} diff={d:.6g}")
    return ok


print("=" * 78)
print("s01 — ANCHOR REPRODUCTION (no new statistic until these pass)")
print("=" * 78)

# ---------------------------------------------------------------- A1..A6
PF = pd.read_parquet(I0045 / "_PF.parquet")

# explicit allowlist column resolution — no substring matching anywhere
NEED = ["row_uid", "player_id", "team_id", "tier_A", "rec_S1", "rec_S2",
        "departed", "seasons_since_club", "n_prior_app_season", "trail5_min"]
missing = [c for c in NEED if c not in PF.columns]
assert not missing, f"E1_I0045 _PF.parquet missing allowlisted columns: {missing}"
print(f"\nresolved columns from _PF.parquet by explicit allowlist: {NEED}")
print(f"_PF.parquet rows = {len(PF)}")

print("\n-- A1 RS1P champion rows --")
anchor("A1", "RS1P champion rows", len(PF), 20084)

print("\n-- A2/A3 tier-B rows by admitting source --")
tierB = ~PF["tier_A"].to_numpy(bool)
s2 = PF["rec_S2"].to_numpy(bool)
s1 = PF["rec_S1"].to_numpy(bool)
n_s2 = int((tierB & s2).sum())
n_stx = int((tierB & ~s1 & ~s2).sum())
anchor("A2", "tier-B admitted by S2", n_s2, 3266)
anchor("A3", "tier-B admitted by S_TX only", n_stx, 506)

print("\n-- A4 S2 rows by seasons-since-club --")
s2b = PF[tierB & s2]
vc = s2b["seasons_since_club"].value_counts().to_dict()
for k, pub in ((1, 1765), (2, 991), (3, 432), (99, 78)):
    anchor(f"A4_{k}", f"S2 rows seasons_since_club={k}", int(vc.get(k, 0)), pub)

print("\n-- A5 S2 departed / not departed --")
anchor("A5_dep", "S2 rows departed", int(s2b["departed"].sum()), 1489)
anchor("A5_not", "S2 rows not departed", int((~s2b["departed"].astype(bool)).sum()), 1777)

print("\n-- A6 decision stratum (n_prior_app_season>=8 AND trail5_min>=24) --")
dec = ((PF["n_prior_app_season"] >= 8)
       & (PF["trail5_min"].fillna(-1) >= 24))
anchor("A6", "RS1P rows in the decision stratum", int(dec.sum()), 4964)

# ---------------------------------------------------------------- A7
print("\n-- A7 p_active references in production files (recounted) --")
PROD_FILES = ["daily_forecast.py", "props_edge.py", "conditional_edge.py",
              "calibrated_prob_edge.py", "daily_certify.py", "daily_refresh.py",
              "props_capture_daily.py", "odds_capture_daily.py",
              "injury_capture_daily.py"]
PROD_DIRS = ["wnba-prediction-engine", "wnba_odds_system",
             "wnba-odds-aggregator", "forecasts", "leaderboards"]
pat = re.compile(r"p_active")


def count_in(p: Path) -> int:
    try:
        return len(pat.findall(p.read_text(encoding="utf-8", errors="ignore")))
    except Exception:
        return 0


for f in PROD_FILES:
    p = REPO / f
    assert p.exists(), f"production file not found: {p}"
    anchor(f"A7_{f}", f"p_active refs in {f}", count_in(p), 0)

for dname in PROD_DIRS:
    d = REPO / dname
    assert d.exists(), f"production dir not found: {d}"
    tot = sum(count_in(p) for p in d.rglob("*") if p.is_file())
    anchor(f"A7_{dname}", f"p_active refs in {dname}/ (recursive)", tot, 0)

# ---------------------------------------------------------------- verdict
A = pd.DataFrame(rows)
A.to_csv(OUT / "ANCHOR_REPRODUCTION.csv", index=False)
n_ok = int(A.confirmed.sum())
print("\n" + "=" * 78)
print(f"ANCHORS CONFIRMED: {n_ok} / {len(A)}")
print(f"exact (diff == 0.000e+00): {int((A.abs_diff == 0).sum())} / {len(A)}")
if n_ok != len(A):
    print("FAILURES:")
    print(A[~A.confirmed].to_string(index=False))
print("=" * 78)

(OUT / "_s01.json").write_text(json.dumps(
    {"anchors": rows, "n_confirmed": n_ok, "n_total": len(A),
     "n_exact_zero": int((A.abs_diff == 0).sum())}, indent=2), encoding="utf-8")
