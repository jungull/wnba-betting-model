"""E1_I0018 s06 -- STEP 3(a): what information does the feature need, and when is it knowable?

The feature's only non-prior input is the set of players with MINUTES > 0 in TODAY's box.  Three
facts about that set are established here on values rather than asserted:

  (a) IT IS A POST-GAME OBSERVATION, NOT A PRE-GAME ONE.  "Appeared in the box with minutes > 0" is
      strictly stronger than "was on the active list": a healthy, active, dressed player who is a
      coach's-decision DNP, or who is held out of a blowout, or who is injured in warm-ups or
      ejected, is ABSENT from this set.  So even a PERFECT pre-game injury report reconstructs at
      best a SUPERSET of PRESENT(g), never PRESENT(g) itself.  data/w1_truth/roster_asof.csv is
      the file that would let this be separated, and it is FORBIDDEN (artifact-granular,
      fit_through_season 2026), so THE SEPARATION CANNOT BE MADE HERE.  That is a stated limit.

  (b) HOW MUCH CHURN THERE IS relative to the team's previous game, in rows and in usage mass.

  (c) HOW MUCH OF THE CHURN IS PERSISTENT.  An absence that continues into the team's NEXT game is
      consistent with an injury/unavailability that a pre-game report would carry; a one-game
      absence is more consistent with rotation noise that no pre-game report can supply.
      *** THE "NEXT GAME" LOOK-AHEAD IS A DESCRIPTIVE DIAGNOSTIC ONLY.  It reads a later game and
      is therefore NEVER used as a feature, never enters a base, and never enters any dR2.  It is
      loudly labelled in the TIME-WINDOW TABLE, exactly as D084 labelled its oracle. ***

Also computed here: the tip-time LOSS LADDER (Step 3c) -- how much of the effect is lost between
the tip-time variant and the strictly-prior-only variant, on every measure this screen produced.
"""
import json
import os
import sys
from collections import deque

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tv_base import MP_PATH, OUT, SEASONS, hdr, sk

f = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
sk.assert_partition(f, verbose=True)

# =====================================================================================
hdr("1. WHAT THE FEATURE NEEDS -- the churn between TODAY's box and the PREVIOUS game's box")
# =====================================================================================
d = f[np.isfinite(f["T01_c04_tiptime"]) & np.isfinite(f["P01_c04_prevgame"])]
news = d["T01_c04_tiptime"] - d["P01_c04_prevgame"]
r2_p01_on_t01 = float(np.corrcoef(d["T01_c04_tiptime"], d["P01_c04_prevgame"])[0, 1] ** 2)
churn = {
    "n_rows": int(len(d)),
    "sd_T01_tiptime": float(d["T01_c04_tiptime"].std()),
    "sd_P01_prior_only": float(d["P01_c04_prevgame"].std()),
    "sd_news_T01_minus_P01": float(news.std()),
    "mean_abs_news": float(news.abs().mean()),
    "share_rows_news_exactly_zero": float((news.abs() < 1e-12).mean()),
    "share_rows_abs_news_gt_2_usg": float((news.abs() > 2.0).mean()),
    "share_rows_abs_news_gt_5_usg": float((news.abs() > 5.0).mean()),
    "r2_of_prevgame_roster_predicting_todays": r2_p01_on_t01,
    "share_of_T01_variance_NOT_predictable_from_prev_game": float(1 - r2_p01_on_t01),
}
print(json.dumps(churn, indent=2))
print("\n  READ THIS AS: the previous game's box membership reproduces %.1f%% of the variance of"
      % (100 * r2_p01_on_t01))
print("  today's, leaving %.1f%% that is SAME-DAY NEWS.  On %.1f%% of rows the two rosters are"
      % (100 * (1 - r2_p01_on_t01), 100 * churn["share_rows_news_exactly_zero"]))
print("  IDENTICAL, so on those rows the tip-time and the prior-only variants agree exactly.")

# =====================================================================================
hdr("2. HOW PERSISTENT IS AN ABSENCE?  *** DESCRIPTIVE DIAGNOSTIC -- READS THE NEXT GAME ***")
# =====================================================================================
print("  This block reads the team's NEXT game to characterise KNOWABILITY.  It produces no")
print("  feature, enters no base and enters no dR2.  It is here because 'is this absence the kind")
print("  a pre-game injury report would carry' cannot be answered without looking at persistence,")
print("  and the file that would answer it directly (roster_asof.csv) is FORBIDDEN.")
mp = pd.read_parquet(MP_PATH)
mp["game_date"] = pd.to_datetime(mp["game_date"], errors="coerce")
mp = mp[mp["season"].isin(SEASONS)].copy()
mp["minutes"] = pd.to_numeric(mp["minutes"], errors="coerce").astype(float)
mp["player_id"] = pd.to_numeric(mp["player_id"], errors="coerce").astype("int64")
mp["team_id"] = pd.to_numeric(mp["team_id"], errors="coerce").astype("int64")
pl = mp[(mp["minutes"] > 0) & (mp["season_type"] == "Regular Season")].copy()
sk.assert_partition(pl, verbose=False)

tg = (pl[["season", "team_id", "game_id", "game_date"]].drop_duplicates()
      .sort_values(["season", "team_id", "game_date", "game_id"], kind="stable"))
byg = pl.groupby(["season", "team_id", "game_id"], sort=False)["player_id"].apply(
    lambda s: set(int(v) for v in s)).to_dict()

n_new_abs = n_persist = n_oneoff = 0
n_new_ret = 0
for (ssn, tid), sub in tg.groupby(["season", "team_id"], sort=False):
    gids = list(sub["game_id"])
    sets = [byg[(ssn, tid, g)] for g in gids]
    for i in range(1, len(sets) - 1):
        prev, cur, nxt = sets[i - 1], sets[i], sets[i + 1]
        newly_absent = prev - cur          # played last game, not this one
        newly_present = cur - prev
        n_new_abs += len(newly_absent)
        n_new_ret += len(newly_present)
        n_persist += len(newly_absent - nxt)     # still absent next game
        n_oneoff += len(newly_absent & nxt)      # back next game
persist = {
    "n_newly_absent_transitions": int(n_new_abs),
    "n_newly_present_transitions": int(n_new_ret),
    "share_absences_persisting_into_the_next_game": float(n_persist / max(n_new_abs, 1)),
    "share_absences_lasting_exactly_one_game": float(n_oneoff / max(n_new_abs, 1)),
}
print("\n" + json.dumps(persist, indent=2))
print("\n  READ THIS AS: %.1f%% of newly-absent teammate-games persist into the team's NEXT game,"
      % (100 * persist["share_absences_persisting_into_the_next_game"]))
print("  which is the profile of a multi-game unavailability -- the kind a pre-game injury report")
print("  plausibly carries.  The other %.1f%% last exactly one game."
      % (100 * persist["share_absences_lasting_exactly_one_game"]))
print("  THIS IS AN UPPER BOUND ON WHAT A PERFECT PRE-GAME REPORT COULD RECOVER, NOT AN ESTIMATE")
print("  OF WHAT ONE WOULD RECOVER: persistence is necessary for pre-game knowability, not")
print("  sufficient, and this screen cannot observe the active list at all.")

# =====================================================================================
hdr("3. STEP 3(c) -- THE TIP-TIME LOSS LADDER")
# =====================================================================================
res = pd.read_csv(os.path.join(OUT, "screen_results.csv"))
pts = pd.read_csv(os.path.join(OUT, "points_propagation.csv"))
wf = pd.read_csv(os.path.join(OUT, "walkforward_points.csv"))
cl = pd.read_csv(os.path.join(OUT, "ceiling_reconciliation.csv"))

TT, PO = "T01_c04_tiptime", "P01_c04_prevgame"
ladder = []


def pick(df, **kw):
    q = df.copy()
    for k, v in kw.items():
        q = q[q[k] == v]
    return q


for stratum in ["POOLED", "DECISION"]:
    for base in ["B_SINGLE", "B_COMPLETE"]:
        for oc in ["ppm", "spm"]:
            a = pick(res, candidate=TT, outcome=oc, base=base, stratum=stratum)
            b = pick(res, candidate=PO, outcome=oc, base=base, stratum=stratum)
            if len(a) and len(b):
                ladder.append(dict(measure="dR2 on y_" + oc, stratum=stratum, base=base,
                                   tip_time=float(a["dr2"].iloc[0]),
                                   prior_only=float(b["dr2"].iloc[0]),
                                   tip_time_fw_p=float(a["p_familywise_maxt"].iloc[0]),
                                   prior_only_fw_p=float(b["p_familywise_maxt"].iloc[0])))
        a = pick(pts, candidate=TT, base=base, stratum=stratum)
        b = pick(pts, candidate=PO, base=base, stratum=stratum)
        if len(a) and len(b):
            ladder.append(dict(measure="paired dR2 on POINTS (in-sample coef)", stratum=stratum,
                               base=base, tip_time=float(a["paired_dr2_points"].iloc[0]),
                               prior_only=float(b["paired_dr2_points"].iloc[0]),
                               tip_time_fw_p=float(a["paired_p_cluster"].iloc[0]),
                               prior_only_fw_p=float(b["paired_p_cluster"].iloc[0])))
        a = pick(wf, candidate=TT, base=base, stratum=stratum)
        b = pick(wf, candidate=PO, base=base, stratum=stratum)
        if len(a) and len(b):
            ladder.append(dict(measure="paired dR2 on POINTS (WALK-FORWARD coef)",
                               stratum=stratum, base=base,
                               tip_time=float(a["walkforward_paired_dr2_points"].iloc[0]),
                               prior_only=float(b["walkforward_paired_dr2_points"].iloc[0]),
                               tip_time_fw_p=float(a["paired_p_cluster"].iloc[0]),
                               prior_only_fw_p=float(b["paired_p_cluster"].iloc[0])))
        a = pick(cl, candidate=TT, base=base, stratum=stratum)
        b = pick(cl, candidate=PO, base=base, stratum=stratum)
        if len(a) and len(b):
            ladder.append(dict(measure="ARITHMETIC CEILING (D084 form)", stratum=stratum,
                               base=base,
                               tip_time=float(a["D084_form_ceiling_var_share"].iloc[0]),
                               prior_only=float(b["D084_form_ceiling_var_share"].iloc[0]),
                               tip_time_fw_p=np.nan, prior_only_fw_p=np.nan))
lad = pd.DataFrame(ladder)
lad["prior_only_retains_pct"] = 100 * lad["prior_only"] / lad["tip_time"]
lad["lost_to_tip_time_pct"] = 100 - lad["prior_only_retains_pct"]
lad.to_csv(os.path.join(OUT, "tiptime_loss_ladder.csv"), index=False)
print(lad.to_string(index=False))
print("\n  MEDIAN of prior_only_retains_pct across the ladder = %.1f%%"
      % float(lad["prior_only_retains_pct"].median()))

with open(os.path.join(OUT, "_s06.json"), "w", encoding="utf-8") as fh:
    json.dump({"roster_churn": churn, "absence_persistence_DIAGNOSTIC_reads_next_game": persist,
               "tiptime_loss_ladder": json.loads(lad.to_json(orient="records")),
               "median_prior_only_retains_pct": float(lad["prior_only_retains_pct"].median())},
              fh, indent=2, default=str)
print("\n  wrote tiptime_loss_ladder.csv, _s06.json")
