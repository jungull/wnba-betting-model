"""E0_I0024 s03 -- STEP 2 (baseline accuracy) and STEP 3 (THE ORACLE LADDER).

THE CENTRAL QUESTION.  How much of a rebound / assist forecast is predictable AT ALL?  D081
established for POINTS that 51.3% of variance on the decision stratum is irreducible even to an
oracle that knows the player's whole season and their REALISED minutes.  Nobody has the equivalent
number for rebounds or assists, because D088 established the champion forecasts neither.

LADDER RUNGS.  D081's shape, with the champion rungs OMITTED because no champion rebound or assist
forecast exists anywhere (D088).  Points is carried through the IDENTICAL machinery purely as a
CALIBRATION ANCHOR, so the comparison is made on THIS frame rather than across frames.

    HONEST (strictly prior-games-only, pre-game attainable)
      REF  expanding prior mean of the target
      H1   EWMA of the prior target (halflife 5)
      H2   trailing-5 prior mean
      H3   (FLOORED prior per-minute rate) x (prior mean minutes)     <- the decomposition
      H4   OLS on the full B_COMPLETE base, WALK-FORWARD by season    <- best reachable here

    ORACLE (LABELLED; conditions on outcomes; NEVER pre-game attainable -- see DEFECTS.md D-03)
      O1   the player's SEASON-MEAN target            (knows the whole season)
      O2   ACTUAL minutes x SEASON-MEAN per-minute rate
      O3   within-player-season OLS of the target on ACTUAL minutes
      O4   ACTUAL minutes x FLOORED PRIOR rate        (semi-oracle: realised minutes only)
      O5   prior mean minutes x SEASON-MEAN rate      (semi-oracle: season rate only)

THE HEADLINE NUMBER is 1 - R2(O2): the share of the target's variance that is irreducible even to
an estimator handed the player's season-long rate AND the realised minutes.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rb_base import (BASE_COLS, HEADLINE_SEASONS, OUT, SEED, TARGETS, assert_partition, hdr,
                     mae, r2_plain, rmse, sha)

rep = {}
F = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F)
F = F.sort_values(["season", "player_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
print("  frame %s   headline seasons %s" % (F.shape, list(HEADLINE_SEASONS)))

# =====================================================================================
hdr("0. SUPPLEMENTARY LEAKAGE PROBES P4b / P4c -- fixing DEFECT D-01")
# =====================================================================================
print("  DEFECT D-01: s02's probe P4 was VACUOUS (hard-coded True).  It is superseded here by a")
print("  brute-force recomputation (P4b) and a discrimination check against the FORBIDDEN")
print("  tip-time membership (P4c).  See DEFECTS.md.")
MPP = os.path.join(os.path.dirname(OUT), "..", "..", "data", "masters", "master_player.parquet")
MPP = os.path.normpath(os.path.join(
    r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program",
    r"data\masters\master_player.parquet"))
mp = pd.read_parquet(MPP)
mp["game_date"] = pd.to_datetime(mp["game_date"], errors="coerce")
mp = mp[mp["season"].isin([2021, 2022, 2023, 2024])]
for c in ["fga", "fta", "tov", "minutes"]:
    mp[c] = pd.to_numeric(mp[c], errors="coerce").astype(float)
mp = mp[mp["minutes"] > 0].copy()
mp["player_id"] = pd.to_numeric(mp["player_id"], errors="coerce").astype("int64")
mp["team_id"] = pd.to_numeric(mp["team_id"], errors="coerce").astype("int64")
mp["game_id"] = mp["game_id"].astype(str)
mp["used"] = mp["fga"] + 0.44 * mp["fta"] + mp["tov"]

rng = np.random.default_rng(SEED + 7)
newprobes = []
cand = F.index[F["A01_c04_prevgame"].notna()].to_numpy()
samp = rng.choice(cand, size=250, replace=False)
bad_prev = 0; bad_today = 0; n_ok = 0; n_diff_membership = 0
for i in samp:
    r = F.loc[i]
    tm = mp[(mp["season"] == r["season"]) & (mp["team_id"] == r["team_id"])]
    gl = (tm[["game_id", "game_date"]].drop_duplicates()
          .sort_values(["game_date", "game_id"], kind="stable").reset_index(drop=True))
    k = gl.index[gl["game_id"] == r["game_id"]]
    if len(k) == 0 or k[0] == 0:
        continue
    prev_gid = gl.loc[k[0] - 1, "game_id"]
    prev_ids = set(tm[tm["game_id"] == prev_gid]["player_id"].tolist())
    today_ids = set(tm[tm["game_id"] == r["game_id"]]["player_id"].tolist())
    if prev_ids != today_ids:
        n_diff_membership += 1
    # usage accumulated over games STRICTLY EARLIER than the CURRENT game
    earlier = tm[(tm["game_date"] < r["game_date"]) |
                 ((tm["game_date"] == r["game_date"]) & (tm["game_id"] < r["game_id"]))]
    if len(earlier) == 0:
        continue
    agg = earlier.groupby("player_id")["used"].agg(["sum", "count"])
    usg = (agg["sum"] / agg["count"]).to_dict()
    me = int(r["player_id"])
    rec_prev = float(sum(usg.get(q, 0.0) for q in prev_ids if q != me))
    rec_today = float(sum(usg.get(q, 0.0) for q in today_ids if q != me))
    n_ok += 1
    if abs(rec_prev - float(r["A01_c04_prevgame"])) > 1e-9:
        bad_prev += 1
    if abs(rec_today - float(r["A01_c04_prevgame"])) > 1e-9:
        bad_today += 1

print("  [P4b] A01 == recomputation from the PREVIOUS game's box : mismatches=%d of %d"
      % (bad_prev, n_ok))
print("  [P4c] A01 vs recomputation from TODAY's box (FORBIDDEN)  : mismatches=%d of %d"
      % (bad_today, n_ok))
print("        membership differed between prev and today on %d of %d sampled rows"
      % (n_diff_membership, n_ok))
ok4b = (bad_prev == 0)
ok4c = (bad_today > 0) and (n_diff_membership > 0)
print("  [%s] P4b  [%s] P4c -- A01 matches the PREVIOUS box and DOES NOT match today's box"
      % ("PASS" if ok4b else "FAIL", "PASS" if ok4c else "FAIL"))
assert ok4b, "A01 does not reproduce from the previous game's box"
assert ok4c, "A01 is indistinguishable from a today's-box quantity -- CANNOT RULE OUT TIP-TIME LEAK"
newprobes = [dict(probe="P4b A01 == recomputed from PREVIOUS game box", passed=True,
                  n_checked=n_ok, detail="mismatches=0"),
             dict(probe="P4c A01 != recomputed from TODAY's box (tip-time discrimination)",
                  passed=True, n_checked=n_ok,
                  detail="mismatches vs today's box=%d; membership differed on %d rows"
                         % (bad_today, n_diff_membership))]
old = pd.read_csv(os.path.join(OUT, "leakage_probes.csv"))
old.loc[old["probe"].str.startswith("A01 uses PREVIOUS"), "probe"] = \
    "P4_VACUOUS_SUPERSEDED (see DEFECTS.md D-01) -- original probe asserted nothing"
old.loc[old["probe"].str.startswith("P4_VACUOUS"), "passed"] = False
pd.concat([old, pd.DataFrame(newprobes)], ignore_index=True).to_csv(
    os.path.join(OUT, "leakage_probes.csv"), index=False)
rep["probes_added"] = newprobes

# =====================================================================================
hdr("1. WALK-FORWARD H4: OLS on B_COMPLETE, fitted on STRICTLY EARLIER SEASONS ONLY")
# =====================================================================================
print("  Season s is scored by a model fitted on seasons < s.  2021 has no earlier season and is")
print("  therefore unscorable for H4; the headline is 2022-2024 in any case.  This is the only")
print("  fitting anywhere in this screen and it never touches the champion.")


def wf_ols(F, target, basecols):
    yhat = np.full(len(F), np.nan)
    cols = [c if not c.startswith("ref_") or "__" in c else c for c in basecols]
    X = F[cols].to_numpy(float)
    y = F[target].to_numpy(float)
    seasons = F["season"].to_numpy()
    for s in sorted(set(seasons.tolist())):
        tr = seasons < s
        te = seasons == s
        if tr.sum() < 200:
            continue
        Xtr = np.column_stack([np.ones(tr.sum()), X[tr]])
        ok = np.isfinite(Xtr).all(axis=1) & np.isfinite(y[tr])
        beta, *_ = np.linalg.lstsq(Xtr[ok], y[tr][ok], rcond=None)
        Xte = np.column_stack([np.ones(te.sum()), X[te]])
        yhat[te] = Xte @ beta
    return yhat


def basecols_for(target):
    out = []
    for c in BASE_COLS["B_COMPLETE"]:
        out.append(c + "__" + target if c in ("ref_mean", "ref_ewma", "ref_trail5",
                                              "ref_rate_x_min", "ref_pct") else c)
    return out


# =====================================================================================
hdr("2. THE LADDER")
# =====================================================================================
rows = []
for label, mask in [("ALL (2022-2024)", F["season"].isin(HEADLINE_SEASONS).to_numpy()),
                    ("DECISION (>=8 prior, >=24 trail-5 min)",
                     (F["season"].isin(HEADLINE_SEASONS) & (F["DECISION"] == 1)).to_numpy()),
                    ("ALL incl 2021 (power sensitivity)", np.ones(len(F), bool))]:
    for t in TARGETS:
        d = F.loc[mask].copy()
        y = d[t].to_numpy(float)
        m_act = d["minutes"].to_numpy(float)
        preds = {
            ("REF  expanding prior mean", "honest"): d["ref_mean__" + t].to_numpy(float),
            ("H1   EWMA prior (hl=5)", "honest"): d["ref_ewma__" + t].to_numpy(float),
            ("H2   trailing-5 prior mean", "honest"): d["ref_trail5__" + t].to_numpy(float),
            ("H3   prior rate(floored) x prior minutes", "honest"):
                d["ref_rate_x_min__" + t].to_numpy(float),
            ("H4   walk-forward OLS on B_COMPLETE", "honest"):
                wf_ols(d, t, basecols_for(t)),
            ("O1   SEASON-MEAN target", "ORACLE"): d["ORACLE_seasonmean__" + t].to_numpy(float),
            ("O2   ACTUAL minutes x SEASON-MEAN rate", "ORACLE"):
                m_act * d["ORACLE_seasonrate__" + t].to_numpy(float),
            ("O4   ACTUAL minutes x prior rate(floored)", "ORACLE"):
                m_act * d["ref_rate_floored__" + t].to_numpy(float),
            ("O5   prior minutes x SEASON-MEAN rate", "ORACLE"):
                d["ref_mean_minutes"].to_numpy(float) * d["ORACLE_seasonrate__" + t].to_numpy(float),
        }
        # O3: within-player-season OLS of the target on ACTUAL minutes (in-sample, ORACLE)
        o3 = np.full(len(d), np.nan)
        for (_, _), g in d.groupby(["season", "player_id"], sort=False):
            ii = g.index
            xx = g["minutes"].to_numpy(float)
            yy = g[t].to_numpy(float)
            if len(g) < 3 or np.std(xx) == 0:
                o3[d.index.get_indexer(ii)] = yy.mean()
                continue
            A = np.column_stack([np.ones(len(g)), xx])
            b, *_ = np.linalg.lstsq(A, yy, rcond=None)
            o3[d.index.get_indexer(ii)] = A @ b
        preds[("O3   within-player-season OLS on ACTUAL min", "ORACLE")] = o3

        for (nm, kind), p in preds.items():
            ok = np.isfinite(y) & np.isfinite(p)
            rows.append(dict(subset=label, target=t, n=int(ok.sum()), rung=nm, kind=kind,
                             mae=mae(y[ok], p[ok]), rmse=rmse(y[ok], p[ok]),
                             r2=r2_plain(y[ok], p[ok]),
                             sd_y=float(np.std(y[ok], ddof=1))))

L = pd.DataFrame(rows)
L.to_csv(os.path.join(OUT, "oracle_ladder.csv"), index=False)

for label in L["subset"].unique():
    print("\n" + "-" * 100)
    print("  SUBSET: %s" % label)
    print("-" * 100)
    for t in TARGETS:
        sub = L[(L["subset"] == label) & (L["target"] == t)].sort_values("rung")
        n = sub["n"].max()
        sdy = sub["sd_y"].iloc[0]
        print("\n   %-8s  n=%-6d sd_y=%.4f" % (t, n, sdy))
        print("     %-46s %-7s %8s %8s %9s" % ("rung", "kind", "MAE", "RMSE", "R2"))
        for _, r in sub.iterrows():
            print("     %-46s %-7s %8.4f %8.4f %9.5f"
                  % (r["rung"], r["kind"], r["mae"], r["rmse"], r["r2"]))

# =====================================================================================
hdr("3. THE HEADLINE NUMBERS -- IRREDUCIBLE SHARE AND REACHABLE HEADROOM")
# =====================================================================================
summ = []
for label in L["subset"].unique():
    for t in TARGETS:
        sub = L[(L["subset"] == label) & (L["target"] == t)].set_index("rung")
        best_honest = sub[sub["kind"] == "honest"]["r2"].max()
        best_honest_rung = sub[sub["kind"] == "honest"]["r2"].idxmax()
        r2_ref = float(sub.loc[[i for i in sub.index if i.startswith("REF")][0], "r2"])
        r2_o2 = float(sub.loc[[i for i in sub.index if i.startswith("O2")][0], "r2"])
        r2_o1 = float(sub.loc[[i for i in sub.index if i.startswith("O1")][0], "r2"])
        r2_o3 = float(sub.loc[[i for i in sub.index if i.startswith("O3")][0], "r2"])
        r2_o5 = float(sub.loc[[i for i in sub.index if i.startswith("O5")][0], "r2"])
        summ.append(dict(subset=label, target=t, n=int(sub["n"].max()),
                         sd_y=float(sub["sd_y"].iloc[0]),
                         r2_REF_honest=r2_ref, best_honest_rung=best_honest_rung,
                         r2_best_honest=float(best_honest),
                         r2_O1_seasonmean=r2_o1, r2_O2_oracle=r2_o2, r2_O3_oracle=r2_o3,
                         r2_O5_semioracle=r2_o5,
                         IRREDUCIBLE_share_even_to_O2=1.0 - r2_o2,
                         IRREDUCIBLE_share_even_to_O3=1.0 - r2_o3,
                         headroom_O2_minus_best_honest=r2_o2 - float(best_honest),
                         headroom_O5_minus_best_honest=r2_o5 - float(best_honest),
                         headroom_O1_minus_REF=r2_o1 - r2_ref))
S = pd.DataFrame(summ)
S.to_csv(os.path.join(OUT, "ladder_summary.csv"), index=False)

for label in S["subset"].unique():
    print("\n  SUBSET: %s" % label)
    print("   %-8s %6s %8s %9s %9s %9s %12s %11s" %
          ("target", "n", "sd_y", "R2 REF", "R2 best", "R2 O2", "IRREDUCIBLE", "headroom"))
    print("   %-8s %6s %8s %9s %9s %9s %12s %11s" %
          ("", "", "", "honest", "honest", "ORACLE", "even to O2", "O2-besthon"))
    for _, r in S[S["subset"] == label].iterrows():
        print("   %-8s %6d %8.4f %9.5f %9.5f %9.5f %11.2f%% %11.5f"
              % (r["target"], r["n"], r["sd_y"], r["r2_REF_honest"], r["r2_best_honest"],
                 r["r2_O2_oracle"], 100 * r["IRREDUCIBLE_share_even_to_O2"],
                 r["headroom_O2_minus_best_honest"]))

# =====================================================================================
hdr("4. BASELINE ACCURACY TABLE (STEP 2 deliverable)")
# =====================================================================================
B = L[L["kind"] == "honest"].copy()
B.to_csv(os.path.join(OUT, "baseline_accuracy.csv"), index=False)
print("  WROTE baseline_accuracy.csv (%d rows -- honest rungs only)" % len(B))

rep["ladder_summary"] = summ
json.dump(rep, open(os.path.join(OUT, "_s03.json"), "w"), indent=2, default=str)
print("\n  WROTE oracle_ladder.csv, ladder_summary.csv, baseline_accuracy.csv, _s03.json")
