"""E0_I0029 s04 -- WHICH STAGE CARRIES THE PREDICTABILITY, ON A SINGLE COMMON DENOMINATOR.

D099 DENOMINATOR RULE.  s03's stage R2s are on DIFFERENT denominators -- stage A on the full
stratum's SST, stages B and C on the fta>0 subset's SST.  Comparing them directly is exactly the
error D099 forbids, and stage C's R2(O2)=0.887 would otherwise look like the answer when it is an
ARTEFACT: stage C's oracle exposure is the REALISED ATTEMPT COUNT, and ftm is nearly determined by
fta.  D097 caught the same shape in total rebounds ("an artefact of aggregation").

THIS FILE ANSWERS THE QUESTION ON ONE DENOMINATOR: SST(ftm) over the FULL stratum.

    ftm = A * G * C        A = 1{fta>0}    G = fta | A=1    C = ftm/fta | A=1

A composed forecast ftm_hat = Ahat * Ghat * Chat is scored against SST(ftm) on the FULL stratum.
Each stage is then switched between three information levels, one at a time:

    LEAGUE  the strictly-prior expanding LEAGUE mean of that stage quantity (no player information)
    HONEST  the player's MATCHED strictly-prior reference for that stage
    ORACLE  the REALISED value of that stage quantity

Two readings, both on SST(ftm):
    (i)  WHICH STAGE CARRIES THE HONEST PREDICTABILITY -- upgrade ONE stage LEAGUE -> HONEST and
         measure the R2 gain.  This is what a forecaster could actually buy.
    (ii) WHICH STAGE CARRIES THE IRREDUCIBLE VARIANCE -- from the all-HONEST composition, upgrade
         ONE stage HONEST -> ORACLE and measure the R2 gain.  This is the ceiling of perfecting
         that stage alone.  Reported in BOTH orderings (add-one-oracle and leave-one-honest),
         because a single ordering of a non-additive decomposition is a choice, not a fact.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ft_base import (HEADLINE_SEASONS, OUT, assert_partition, hdr, jsonable, r2_plain, safe_div)

rep = {}
F = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F)
F = F.sort_values(["season", "game_date", "game_id"], kind="stable").reset_index(drop=True)

# =====================================================================================
hdr("1. STAGE QUANTITIES AND THEIR THREE INFORMATION LEVELS")
# =====================================================================================
# --- LEAGUE level: expanding mean over rows strictly EARLIER IN THE SAME SEASON.  Prior-only.
def league_prior(col, mask=None):
    v = F[col].astype(float).copy()
    if mask is not None:
        v = v.where(mask)
    out = v.groupby(F["season"], sort=False).transform(lambda x: x.shift(1).expanding().mean())
    # cold start at the very first rows of a season: fall back to the season's first available
    return out.groupby(F["season"], sort=False).transform(lambda x: x.ffill().bfill())


cond = F["COND"] == 1
F["LG_A"] = league_prior("y_any_fta")
F["LG_G"] = league_prior("fta", mask=cond)
F["ft_pct_given"] = safe_div(F["ftm"], F["fta"])
F["LG_C"] = league_prior("ft_pct_given", mask=cond)

# --- HONEST level: the player's MATCHED strictly-prior reference, league value where unavailable
F["HON_A"] = F["ref_mean__y_any_fta"].fillna(F["LG_A"])
F["HON_G"] = F["ref_mean__y_fta_given"].fillna(F["LG_G"])
F["HON_C"] = F["F03_prior_ft_pct"].fillna(F["LG_C"])

# --- ORACLE level: the REALISED stage quantity.  LABELLED; used only here and in s03's rungs.
F["ORA_A"] = F["y_any_fta"].astype(float)
F["ORA_G"] = np.where(cond, F["fta"].astype(float), F["HON_G"])
F["ORA_C"] = np.where(cond, F["ft_pct_given"].astype(float), F["HON_C"])

for lv in ["LG", "HON", "ORA"]:
    print("  %-4s A mean %.4f | G mean %.4f | C mean %.4f"
          % (lv, F[lv + "_A"].mean(), F[lv + "_G"].mean(), F[lv + "_C"].mean()))

# =====================================================================================
hdr("2. COMPOSED FORECASTS ON THE COMMON DENOMINATOR  SST(ftm), FULL STRATUM")
# =====================================================================================
STRATA = {
    "POOLED (2022-2024)": F["season"].isin(HEADLINE_SEASONS).to_numpy(),
    "DECISION (2022-2024)": (F["season"].isin(HEADLINE_SEASONS) & (F["DECISION"] == 1)).to_numpy(),
}
LEVELS = ["LG", "HON", "ORA"]
rows = []


def compose(d, la, lg, lc):
    return (d[la + "_A"].to_numpy(float) * d[lg + "_G"].to_numpy(float)
            * d[lc + "_C"].to_numpy(float))


for sname, smask in STRATA.items():
    d = F.loc[smask]
    y = d["y_ftm"].to_numpy(float)
    sst = float(((y - y.mean()) ** 2).sum())
    combos = [
        ("all LEAGUE (no player information)", "LG", "LG", "LG"),
        ("HONEST stage A only", "HON", "LG", "LG"),
        ("HONEST stage B only", "LG", "HON", "LG"),
        ("HONEST stage C only", "LG", "LG", "HON"),
        ("all HONEST", "HON", "HON", "HON"),
        ("all HONEST + ORACLE A", "ORA", "HON", "HON"),
        ("all HONEST + ORACLE B", "HON", "ORA", "HON"),
        ("all HONEST + ORACLE C", "HON", "HON", "ORA"),
        ("all ORACLE except A honest", "HON", "ORA", "ORA"),
        ("all ORACLE except B honest", "ORA", "HON", "ORA"),
        ("all ORACLE except C honest", "ORA", "ORA", "HON"),
        ("all ORACLE (identity check, must be 1.0)", "ORA", "ORA", "ORA"),
    ]
    res = {}
    for label, a, g, c in combos:
        p = compose(d, a, g, c)
        r2 = r2_plain(y, p)
        res[label] = r2
        rows.append(dict(stratum=sname, denominator="SST(ftm) FULL STRATUM", n=int(len(d)),
                         sd_y_ftm=float(np.std(y, ddof=1)), composition=label,
                         level_A=a, level_B=g, level_C=c, r2=r2))
    base = res["all LEAGUE (no player information)"]
    hon = res["all HONEST"]
    print("\n  STRATUM %s   n=%d  sd(ftm)=%.4f  SST=%.1f"
          % (sname, len(d), float(np.std(y, ddof=1)), sst))
    print("   %-44s %10s %12s" % ("composition", "R2(ftm)", "gain"))
    for label, *_ in combos:
        ref = base if label.startswith("HONEST stage") or label == "all HONEST" else (
            hon if "ORACLE" in label and "except" not in label and label != "all ORACLE (identity check, must be 1.0)" else np.nan)
        gain = res[label] - ref if np.isfinite(ref) else np.nan
        print("   %-44s %10.5f %12s"
              % (label, res[label], ("%+.5f" % gain) if np.isfinite(gain) else ""))

    # --- reading (i): honest predictability per stage, common denominator
    hi = {s: res["HONEST stage %s only" % s] - base for s in ["A", "B", "C"]}
    tot_hon = hon - base
    # --- reading (ii): oracle headroom per stage, two orderings
    add1 = {s: res["all HONEST + ORACLE %s" % s] - hon for s in ["A", "B", "C"]}
    leave1 = {s: 1.0 - res["all ORACLE except %s honest" % s] for s in ["A", "B", "C"]}
    print("\n   (i)  HONEST PREDICTABILITY BOUGHT BY EACH STAGE  (LEAGUE -> HONEST, dR2 on SST(ftm))")
    for s in "ABC":
        print("        stage %s : %+.5f   (%.1f%% of the all-honest total %.5f)"
              % (s, hi[s], 100 * hi[s] / tot_hon if tot_hon else np.nan, tot_hon))
    print("   (ii) ORACLE HEADROOM PER STAGE ON THE SAME DENOMINATOR")
    print("        %-6s %14s %16s" % ("stage", "add-one-oracle", "leave-one-honest"))
    for s in "ABC":
        print("        %-6s %+14.5f %+16.5f" % (s, add1[s], leave1[s]))
    rep[sname] = dict(n=int(len(d)), r2=res, honest_gain_by_stage=hi,
                      honest_total=tot_hon, oracle_add1=add1, oracle_leave1=leave1)

D = pd.DataFrame(rows)

# =====================================================================================
hdr("3. PER-STAGE HONEST vs MATCHED-REFERENCE SKILL, ON EACH STAGE'S OWN DENOMINATOR")
# =====================================================================================
print("  Reported ALONGSIDE, never compared across stages (D099).  The matched reference for a")
print("  CONDITIONAL stage is built on the player's PRIOR fta>0 GAMES ONLY.")
extra = []
for sname, smask in STRATA.items():
    for stage, tgt, refcol, rowmask in [
            ("A  P(any FTA)", "y_any_fta", "ref_mean__y_any_fta", np.ones(len(F), bool)),
            ("B  FTA | any", "y_fta_given", "ref_mean__y_fta_given", cond.to_numpy()),
            ("C  FTM | FTA", "y_ftm_given", "F03_prior_ft_pct", cond.to_numpy()),
            ("C' FT% | FTA", "ft_pct_given", "F03_prior_ft_pct", cond.to_numpy())]:
        m = smask & rowmask
        d = F.loc[m]
        y = d[tgt].to_numpy(float)
        r = d[refcol].to_numpy(float)
        if stage.startswith("C "):
            r = r * d["fta"].to_numpy(float)      # ftm|fta needs the realised exposure -> ORACLE
        ok = np.isfinite(y) & np.isfinite(r)
        lg = d["LG_C"].to_numpy(float) if stage.startswith("C") else None
        row = dict(stratum=sname, stage=stage, target=tgt, n=int(ok.sum()),
                   denominator=("FULL_STRATUM" if stage.startswith("A") else
                                "CONDITIONAL_SUBSET(fta>0)"),
                   sd_y=float(np.std(y[ok], ddof=1)),
                   r2_matched_prior_reference=r2_plain(y[ok], r[ok]),
                   note=("uses REALISED fta as exposure -> ORACLE-EXPOSURE, not a pregame forecast"
                         if stage.startswith("C ") else ""))
        extra.append(row)
        print("   %-22s %-22s n=%-6d sd=%7.4f  R2(matched prior ref)=%8.5f  %s"
              % (sname, stage, row["n"], row["sd_y"], row["r2_matched_prior_reference"],
                 row["note"]))
E = pd.DataFrame(extra)

# =====================================================================================
hdr("4. WRITE hurdle_stages.csv")
# =====================================================================================
out = os.path.join(OUT, "hurdle_stages.csv")
with open(out, "w", encoding="utf-8", newline="") as fh:
    fh.write("# SECTION 1: composed ftm forecasts, COMMON DENOMINATOR = SST(ftm) on the FULL "
             "stratum (D099)\n")
D.to_csv(out, index=False, mode="a")
with open(out, "a", encoding="utf-8", newline="") as fh:
    fh.write("\n# SECTION 2: per-stage skill on EACH STAGE'S OWN denominator -- NOT comparable "
             "across stages\n")
E.to_csv(out, index=False, mode="a")
print("  wrote %s" % out)

rep["per_stage_own_denominator"] = extra
json.dump(jsonable(rep), open(os.path.join(OUT, "_s04.json"), "w"), indent=2)
print("  WROTE _s04.json")
