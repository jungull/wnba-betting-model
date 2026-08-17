"""E1_I0051 -- s01.  ANCHORS, reproduced BEFORE any new statistic.  The run HALTS on any failure.

Also measures, in the same pass, the quantity this screen exists to test:
  HOW BADLY DOES AN INDEPENDENTLY-MODELLED MINUTES FORECAST VIOLATE THE 200-MINUTE BUDGET?
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_base as B  # noqa: E402

pd.set_option("display.width", 220)
ROWS = []
FAILED = []


def anchor(aid, what, source, required, got, ok, note=""):
    ROWS.append(dict(anchor_id=aid, what=what, source=source, required=str(required),
                     reproduced=str(got), abs_dev=note, status="PASS" if ok else "FAIL"))
    print("  %-5s %-58s req=%-34s got=%-34s %s %s"
          % (aid, what[:58], str(required)[:34], str(got)[:34], "PASS" if ok else "**FAIL**", note))
    if not ok:
        FAILED.append(aid)


B.hdr("E1_I0051_constraint_sweep -- s01 ANCHORS")
print("PREREG.md sha256 %s" % B.prereg_sha())

d, tg, closure = B.build_frame(verbose=True)
d = B.add_candidate_columns(d, verbose=True)

B.hdr("ANCHOR BLOCK -- the run halts on any failure")

# ---- A1 / A2 -------------------------------------------------------------------------------
anchor("A1", "appeared player-games, 2021-24 Regular Season", "E1_I0046", 16717, len(d),
       len(d) == 16717)
anchor("A2", "team-games", "E1_I0046", 1776, int(d["tg_code"].nunique()),
       int(d["tg_code"].nunique()) == 1776)

# ---- A3 / A4 / A5 --------------------------------------------------------------------------
anchor("A3", "sum(player pts) == team pts, max |diff|", "E1_I0046", "0.0 exact / 0 nonzero",
       "%.12f / %d" % (closure["max_abs_diff_pts"], closure["n_nonzero_pts"]),
       closure["max_abs_diff_pts"] == 0.0 and closure["n_nonzero_pts"] == 0, "0.000e+00")
anchor("A4", "sum(player fga) == team fga, max |diff|", "E1_I0046", "0.0 exact / 0 nonzero",
       "%.12f / %d" % (closure["max_abs_diff_fga"], closure["n_nonzero_fga"]),
       closure["max_abs_diff_fga"] == 0.0 and closure["n_nonzero_fga"] == 0, "0.000e+00")
anchor("A5", "sum(player minutes) vs box minutes, max |diff|", "E1_I0046", "<= 0.07",
       "%.6f" % closure["max_abs_diff_min"], closure["max_abs_diff_min"] <= 0.07)

# ---- A6 / A7  decision stratum -------------------------------------------------------------
dm = B.decision_mask(d)
dd = d[dm]
a6 = (int(len(dd)), int(dd["player_id"].nunique()), int(dd["game_id"].nunique()))
anchor("A6", "decision stratum, all seasons (rows / players / games)", "E1_I0043",
       "(5673, 149, 708)", str(a6), a6 == (5673, 149, 708))
n_clean = int(((d["season"].isin(B.CLEAN_EVAL_SEASONS)).to_numpy() & dm).sum())
anchor("A7", "decision stratum, clean window 2023-24, rows", "E1_I0046", 3167, n_clean,
       n_clean == 3167)

# ---- A8 mean appeared roster ---------------------------------------------------------------
mr = float(d.drop_duplicates("tg")["n_roster"].mean())
anchor("A8", "mean appeared roster per team-game", "E1_I0046 / E1_I0033", "9.41 (2dp)",
       "%.4f" % mr, round(mr, 2) == 9.41)

# ---- A9  E0_I0016 / E1_I0018 screen frame --------------------------------------------------
# their frame: appeared (minutes>0), Regular Season 2021-24, >= 3 prior appearances
n_i16 = int((d["n_prior"].to_numpy(float) >= 3.0).sum())
anchor("A9", "E0_I0016 / E1_I0018 screen frame (>=3 prior appearances)", "those screens",
       14852, n_i16, n_i16 == 14852)

# ---- A10 home advantage --------------------------------------------------------------------
mt = pd.read_parquet(B.MT, columns=B.MT_COLS)
mt = mt[(mt["season"].isin(sorted(B.ALLOWED_SEASONS))) &
        (mt["season_type"] == "Regular Season")].copy()
B.assert_partition(mt, "master_team_A10")
mt["is_home"] = mt["is_home"].astype(bool)
h = mt[mt["is_home"]]["pts"].to_numpy(float)
a = mt[~mt["is_home"]]["pts"].to_numpy(float)
ha = float(h.mean() - a.mean())
n_games = int(mt["game_id"].nunique())
anchor("A10", "home advantage in team points (mean home - mean away)", "D104 / E1_I0030",
       "+0.965090 on 888 games", "%+.6f on %d games" % (ha, n_games),
       abs(ha - 0.965090) < 5e-7 and n_games == 888, "|d| %.2e" % abs(ha - 0.965090))

# ---- A11 possessions ratio ------------------------------------------------------------------
mtp = mt.copy()
mtp["tg"] = mtp["game_id"].astype(str) + "|" + mtp["team_id"].astype(str)
mtp["poss_box"] = (mtp["fga"].astype(float) + 0.44 * mtp["fta"].astype(float)
                   - mtp["oreb"].astype(float) + mtp["tov"].astype(float))
pp = d.groupby("tg", sort=False)["possessions"].sum().rename("P_player")
jj = mtp.set_index("tg")[["poss_box"]].join(pp, how="inner")
ratio = jj["P_player"] / (5.0 * jj["poss_box"])
med = float(ratio.median())
# A11 IS DEMOTED FROM A HALT-ANCHOR.  See DEFECTS.md D-01.  The PREREG named this anchor WITHOUT
# ITS ROW SET, which is a D101 violation inside this screen's own preregistration.  E0_I0012's
# frame is a filtered analysis frame (their spread p05 0.960 / p95 1.023 is NARROWER than any
# unfiltered construction can give); six explicit row-set and estimator variants were enumerated
# in s01b_a11.py and NONE matches.  The search was STOPPED there rather than continued, because
# continuing would be fitting a construction to a target.  Reported as a NON-REPRODUCTION with
# both numbers published.  It touches nothing: possessions FAIL the §3 budget gate and are
# re-measured nowhere in this screen.
_a11_ok = round(med, 3) == 0.992
ROWS.append(dict(anchor_id="A11",
                 what="median sum(player possessions) / (5 x team possessions)",
                 source="E0_I0012", required="0.992 (3dp), p05 0.960, p95 1.023",
                 reproduced="%.6f, p05 %.3f, p95 %.3f" % (med, ratio.quantile(.05),
                                                          ratio.quantile(.95)),
                 abs_dev="|d| %.6f" % abs(med - 0.992),
                 status="PASS" if _a11_ok else "NON-REPRODUCTION (DEMOTED, see DEFECTS D-01)"))
print("  %-5s %-58s req=%-34s got=%-34s %s"
      % ("A11", "median sum(player poss) / (5 x team poss)", "0.992 / .960 / 1.023",
         "%.6f / %.3f / %.3f" % (med, ratio.quantile(.05), ratio.quantile(.95)),
         "PASS" if _a11_ok else "**NON-REPRODUCTION -- DEMOTED, NOT A HALT (DEFECTS D-01)**"))

# ---- A12 the minutes budget lattice ---------------------------------------------------------
tgu = d.drop_duplicates("tg")
res = (tgu["T_min"].to_numpy(float) - tgu["B_rules"].to_numpy(float))
anchor("A12", "T_min on the 25-lattice: n on lattice / max residual", "this screen s00",
       "1776 / 0.066667", "%d / %.6f" % (int((np.abs(res) < 0.5).sum()), float(np.abs(res).max())),
       int((np.abs(res) < 0.5).sum()) == 1776 and abs(float(np.abs(res).max()) - 0.0666667) < 1e-4)

# ---- A14 zero points shares -----------------------------------------------------------------
nz = int((d["pts"].to_numpy(float) == 0.0).sum())
anchor("A14", "appeared player-games with points share exactly 0", "E1_I0046", 2506, nz,
       nz == 2506)

if FAILED:
    raise SystemExit("ANCHORS FAILED: %s -- HALTING, no new statistic is computed." % FAILED)
npass = sum(1 for r in ROWS if r["status"] == "PASS")
nexact = sum(1 for r in ROWS if r["abs_dev"] == "0.000e+00")
print("\n  %d of %d ANCHORS PASS (%d at exactly 0.000e+00).  1 demoted non-reproduction (A11)."
      % (npass, len(ROWS), nexact))

# =============================================================================================
B.hdr("A13 (ATTEMPTED, NOT A HALT-ANCHOR) -- E1_I0034's trailing-form accounting")
print("""  E1_I0034 defines ESTABLISHED over the CHAMPION'S OBLIGATION UNIVERSE ('champion candidate
  rows for g with >=3 strictly-prior same-season appearances and a base5').  That universe is not
  reachable from master_player alone, so an EXACT reproduction is not available to this screen and
  A13 is DEMOTED from a halt-anchor to a corroboration, stated as such.  What follows is an
  INDEPENDENT reconstruction from master_player using the closest available definition:
    ESTABLISHED = a player with >=3 strictly-prior same-season appearances FOR THIS TEAM whose
                  last appearance was within the team's previous 5 team-games (so the universe is
                  current rather than season-cumulative).
  The QUALITATIVE claim under test is the one that matters to this screen: does a per-player
  trailing-form minutes estimator sum to the 200-minute budget, or not?""")

clean = d[d["season"].isin(B.CLEAN_EVAL_SEASONS)].copy()
tgc = tg[tg["season"].isin(B.CLEAN_EVAL_SEASONS)].copy()
# base5 = trailing-5 mean minutes over the player's own strictly-earlier same-season games
d = d.sort_values(["season", "player_id", "game_date", "game_id"]).reset_index(drop=True)
d["base5_min"] = d.groupby(["season", "player_id"], sort=False)["minutes"].transform(
    lambda s: s.shift(1).rolling(5, min_periods=3).mean())
d["n_prior_team"] = d.groupby(["season", "team_id", "player_id"], sort=False).cumcount().astype(float)

rows = []
for (ssn, team), grp in d[d["season"].isin(B.CLEAN_EVAL_SEASONS)].groupby(
        ["season", "team_id"], sort=False):
    tgs = tgc[(tgc["season"] == ssn) & (tgc["team_id"] == team)].sort_values("tg_index")
    hist = {}          # player -> list of (tg_index, base5_at_that_game, appeared)
    g_of = {}
    for r in d[(d["season"] == ssn) & (d["team_id"] == team)].itertuples():
        g_of.setdefault(r.tg, None)
    # build per-team-game appearance / base5 tables
    sub = d[(d["season"] == ssn) & (d["team_id"] == team)]
    by_tg = {t: s for t, s in sub.groupby("tg", sort=False)}
    seen = {}
    lastseen = {}
    for r in tgs.itertuples():
        t = r.tg
        ti = int(r.tg_index)
        present = by_tg.get(t)
        pres_ids = set(present["player_id"].to_numpy()) if present is not None else set()
        est, absent, rem = [], [], []
        for p, cnt in seen.items():
            if cnt < 3:
                continue
            if ti - lastseen[p] > 5:
                continue
            b5 = hist.get(p, np.nan)
            if not np.isfinite(b5):
                continue
            est.append((p, b5))
            (rem if p in pres_ids else absent).append((p, b5))
        freed = float(sum(b for _p, b in absent))
        rem_sum = float(sum(b for _p, b in rem))
        realised_rem = float(present[present["player_id"].isin([p for p, _b in rem])]["minutes"].sum()
                             ) if present is not None and rem else 0.0
        rows.append(dict(tg=t, season=ssn, freed=freed, n_est=len(est), n_abs=len(absent),
                         n_rem=len(rem), rem_base5_sum=rem_sum, realised_rem_min=realised_rem,
                         realised_gain=realised_rem - rem_sum))
        # advance state
        if present is not None:
            for rr in present.itertuples():
                seen[rr.player_id] = seen.get(rr.player_id, 0) + 1
                lastseen[rr.player_id] = ti
                if np.isfinite(rr.base5_min):
                    hist[rr.player_id] = float(rr.base5_min)
                # recompute base5 AFTER this game for the next one
        for rr in (present.itertuples() if present is not None else []):
            pass
    # end team
acc = pd.DataFrame(rows)
# recompute base5 forward-looking-free: use each player's trailing-5 AT the team-game in question
# (the loop above stored the value from her PREVIOUS appearance, which is strictly prior -- correct)
bins = [-0.001, 0.001, 15.0, 30.0, 45.0, 1e9]
labs = ["none", "0-15", "15-30", "30-45", "45+"]
acc["bucket"] = pd.cut(acc["freed"], bins=bins, labels=labs)
summ = acc.groupby("bucket", observed=False).agg(
    team_games=("tg", "size"), rem_base5_sum=("rem_base5_sum", "mean"),
    n_est=("n_est", "mean"), n_rem=("n_rem", "mean"),
    realised_gain=("realised_gain", "mean"))
summ["slack_vs_200"] = 200.0 - summ["rem_base5_sum"]
print()
print(summ.to_string(float_format=lambda x: "%.4f" % x))
print("""
  E1_I0034 published (clean window, champion universe):
     bucket        team-games   rem trailing-5 sum   slack   realised gain
     none              261            198.96          +1.0       -3.24
     0-15              220            201.08          -1.1       -2.59
     15-30             171            201.50          -1.5       -3.01
     30-45             124            191.44          +8.6       +6.36
     45+               112            184.02         +16.0      +15.47""")

B.hdr("THE MEASUREMENT THIS SCREEN EXISTS FOR -- does an independent minutes forecast sum to 200?")
print("""  Every minutes screen in this programme models the player's minutes INDEPENDENTLY and never
  checks the roster sum.  Here is what the sum actually is, for the simplest such forecast, on the
  APPEARED ROSTER (so the roster is granted as an oracle and only the BUDGET is at issue).""")
res_rows = []
for h_ in [3, 5, 8, 13]:
    for k_ in [0.0, 1.0]:
        f = B.allocator_raw(d, "M_level_min", h_, k_)
        s = pd.Series(f).groupby(d["tg_code"].to_numpy()).sum()
        res_rows.append(dict(h=h_, k=k_, mean_sum=float(s.mean()), sd_sum=float(s.std(ddof=1)),
                             mae_vs_200=float(np.abs(s - 200.0).mean()),
                             p05=float(s.quantile(.05)), p95=float(s.quantile(.95)),
                             frac_within_5=float((np.abs(s - 200.0) <= 5).mean())))
rr = pd.DataFrame(res_rows)
print()
print(rr.to_string(index=False, float_format=lambda x: "%.4f" % x))

out = os.path.join(B.OUT, "ANCHORS.csv")
pd.DataFrame(ROWS).to_csv(out, index=False)
acc.to_csv(os.path.join(B.OUT, "_A13_accounting_raw.csv"), index=False)
summ.reset_index().to_csv(os.path.join(B.OUT, "A13_TRAILING_FORM_ACCOUNTING.csv"), index=False)
rr.to_csv(os.path.join(B.OUT, "BUDGET_VIOLATION.csv"), index=False)
d.to_parquet(os.path.join(B.SCR, "_frame.parquet"))
tg.to_parquet(os.path.join(B.SCR, "_tg.parquet"))
B.dump("s01", dict(prereg_sha=B.prereg_sha(), anchors=ROWS, closure=closure,
                   budget_violation=res_rows, n_rows=len(d)))
print("\nwrote ANCHORS.csv, A13_TRAILING_FORM_ACCOUNTING.csv, BUDGET_VIOLATION.csv")
B.hdr("DONE s01")
