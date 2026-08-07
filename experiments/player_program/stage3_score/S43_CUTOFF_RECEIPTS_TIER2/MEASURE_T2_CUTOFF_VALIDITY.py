r"""S43 / TIER-2 POINT-IN-TIME CUTOFF-VALIDITY AUDIT (user decision D065, S37 finding A9).

WHAT THIS MEASURES, AND WHY IT IS NOT THE TIER-1 QUESTION
---------------------------------------------------------
Tier 1 asks "where did this value come from".  Tier 2 asks the harder question the user pinned:

    prove that EVERY UNDERLYING OBSERVATION PREDATES THE FORECAST CUTOFF

For a field whose value is COMPUTED FROM OBSERVATIONS, that decomposes into two separable claims:

  (E) EVENT CLAIM     -- every event whose realisation entered the computation had finished
                         before the row's forecast_cutoff.
  (R) RECORD CLAIM    -- the repository's observation OF those events existed before the cutoff.

(R) is what the D10 ledger demands ("a per-row source observation timestamp <= forecast_cutoff")
and it is why every one of these fields is CUTOFF_UNPROVEN there.  This node does NOT try to
manufacture (R): no capture timestamp exists for any of these artifacts and none can be invented.

(E) has never been measured anywhere in this program, and it is measurable exactly, because every
target's contributing source set is re-derivable from the producers' own code.  (E) is a NECESSARY
condition for cutoff validity.  A field that FAILS (E) is CUTOFF_INVALID -- not merely unproven --
and no future capture receipt can rescue it.  That is what this script is for.

ROOT (stated explicitly; the main working tree's data has drifted because live captures continue
there and is INADMISSIBLE):
  C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program

PROHIBITIONS HONOURED.  No fit.  No performance number of any kind -- no MAE, Brier, accuracy,
log-loss, delta or arm-vs-null comparison.  Counts, censuses, hashes, timestamps and provenance
only.  master_team.observed_time is a LOCAL FILE MTIME IN MID-2026, not an as-of bound; it is
DROPPED at load and never written.  No frozen artifact is modified.  git is not run.  All writes
land in this file's own directory.

Emits RECEIPTS.json and EVIDENCE_DETAIL.json.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from datetime import timedelta

import numpy as np
import pandas as pd

WORKTREE = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ canonicalisation (S32B/canon)
UNIT_SEP = "\x1f"
RECORD_SEP = "\x1e"


def canon_value(v):
    if v is None:
        return "nan"
    if isinstance(v, (bool, np.bool_)):
        return str(bool(v))
    if isinstance(v, (float, np.floating)):
        return repr(float(v))
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if hasattr(v, "isoformat"):
        return v.isoformat()
    try:
        if v is pd.NA or (not isinstance(v, str) and pd.isna(v)):
            return "nan"
    except Exception:
        pass
    return str(v)


def column_digest(values):
    return hashlib.sha256(
        UNIT_SEP.join(canon_value(v) for v in values).encode("utf-8")).hexdigest()


def join_key_digest(rows):
    keys = [RECORD_SEP.join(canon_value(c) for c in row) for row in rows]
    return hashlib.sha256(UNIT_SEP.join(keys).encode("utf-8")).hexdigest()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def P(rel):
    return os.path.join(WORKTREE, rel.replace("/", os.sep))


OUT = {
    "measurement": "S43_TIER2_POINT_IN_TIME_CUTOFF_VALIDITY",
    "commissioned_by": "user decision D065; discharges the tier-2 half of S37 finding A9",
    "root": WORKTREE,
    "standard": {
        "user_ruling_verbatim": (
            "Expected-possessions priors, prior-game box aggregates, recent-form inputs, and "
            "anything computed from historical data need the stronger point-in-time audit proving "
            "that every underlying observation predates the forecast cutoff. So don't turn 12 "
            "fields into 12 research projects. Establish the minimum sufficient proof for each "
            "field, record it, and unblock fitting."),
        "d10_governing_rule_verbatim": (
            "a field is CUTOFF_VALID for a row only if a per-row source observation timestamp "
            "exists and is <= that row's forecast_cutoff. No timestamp means CUTOFF_UNPROVEN. "
            "Structural plausibility is never a substitute."),
        "decomposition": {
            "E_event_claim": "every event whose realisation entered the value had finished before "
                             "the row's forecast_cutoff. NECESSARY. Measured exhaustively here.",
            "R_record_claim": "the repository's observation of those events existed before the "
                              "cutoff. This is D10's timestamp test. NOT measurable: no capture "
                              "timestamp exists on any target artifact. NOT manufactured here.",
            "consequence": "FAIL(E) => CUTOFF_INVALID (no future capture receipt can rescue it). "
                           "PASS(E) and no R => CUTOFF_UNPROVEN, with the gap named exactly.",
        },
    },
    "prohibitions": {
        "no_fit": True, "no_performance_number": True,
        "observed_time_dropped_before_every_write": True,
        "frozen_artifacts_modified": False, "git_run": False,
    },
    "reads": {},
}
READS = OUT["reads"]


def read_hash(rel):
    READS[rel] = sha256(P(rel))
    return P(rel)


# ==================================================================================== 1. CUTOFFS
CV4 = read_hash("experiments/prediction_contract_v4/game.parquet")
cv4 = pd.read_parquet(CV4)
cv4["game_id"] = cv4["game_id"].astype(str)
cv4["gd"] = pd.to_datetime(cv4["game_date"]).dt.strftime("%Y-%m-%d")

cutoff_of = dict(zip(cv4.game_id, cv4.forecast_cutoff))
policy_of = dict(zip(cv4.game_id, cv4.cutoff_policy))

OUT["cutoff_source"] = {
    "artifact": "experiments/prediction_contract_v4/game.parquet",
    "column": "forecast_cutoff",
    "rows": int(len(cv4)),
    "policies": {k: int(v) for k, v in cv4.cutoff_policy.value_counts().items()},
    "policy_definitions": {
        "date_only_prior_day_cutoff": "18:00 UTC on the day BEFORE the game (D10 cutoff_definition)",
        "exact_tip_T-90m": "scheduled tip minus 90 minutes",
    },
    "d10_ledger_field_26_tip_scheduled_contract_v4_screened": "CUTOFF_VALID",
    "note": "this is the same forecast_cutoff column the D10 ledger itself joins to. It is the "
            "only per-row cutoff in the repository.",
}

# ============================================================ 2. UNIVERSE (observed_time DROPPED)
MT = read_hash("data/masters/master_team.parquet")
mt = pd.read_parquet(MT)
assert "observed_time" in mt.columns
mt = mt.drop(columns=["observed_time"])           # LOCAL FILE MTIME IN MID-2026. Never used, never written.
mt["game_id"] = mt["game_id"].astype(str)
mt["game_date"] = mt["game_date"].astype(str)
mt["team_id"] = mt["team_id"].astype("int64")
mt["opp_team_id"] = mt["opp_team_id"].astype("int64")

D010_EXCLUDED_DATE = "2021-05-14"
full_ids = set(mt[mt.is_home == 1].game_id)
uni_ids = set(mt[(mt.is_home == 1) & (mt.game_date != D010_EXCLUDED_DATE)].game_id)

team_rows = mt[mt.game_id.isin(uni_ids)].copy()
team_rows["margin"] = (team_rows.pts - team_rows.opp_pts).astype(float)
team_rows["env"] = (team_rows.pts + team_rows.opp_pts).astype(float)
team_rows = team_rows.sort_values(["game_date", "game_id", "team_id"],
                                  kind="mergesort").reset_index(drop=True)

date_of = dict(zip(mt.game_id, mt.game_date))
season_of = dict(zip(mt.game_id, mt.season))

games = (team_rows[team_rows.is_home == 1][["game_id", "season", "season_type", "game_date"]]
         .sort_values(["game_date", "game_id"], kind="mergesort").reset_index(drop=True))

OUT["universe"] = {
    "full_schedule_clusters": len(full_ids), "full_schedule_rows": int(mt.shape[0]),
    "d010_excluded_date": D010_EXCLUDED_DATE,
    "universe_clusters": len(uni_ids), "universe_rows": int(team_rows.shape[0]),
    "per_season_clusters": {str(k): int(v) for k, v in
                            games.groupby("season").game_id.nunique().items()},
    "pinned_expectation": {"clusters": 1491, "rows": 2982},
    "matches_pin": bool(len(uni_ids) == 1491 and team_rows.shape[0] == 2982),
    "cutoff_join_coverage": {
        "universe_clusters_with_a_forecast_cutoff":
            int(sum(1 for g in uni_ids if g in cutoff_of)),
        "universe_clusters_WITHOUT": sorted(g for g in uni_ids if g not in cutoff_of),
    },
    "policy_over_universe_clusters":
        {k: int(v) for k, v in
         pd.Series([policy_of.get(g) for g in sorted(uni_ids)]).value_counts().items()},
}

# ============================================== 3. OBSERVATION-TIME WITNESSES FOR SOURCE EVENTS
# Witness A: contract_v4 scheduled_tip_time, quality observed_single / observed_revised.
#            D10 ledger field 26 is the ONE tip object it rates CUTOFF_VALID.
# Witness B: data/reference/tip_times.csv (market-archive derived). D10 field 23 = CUTOFF_UNPROVEN.
#            Under the S33R precedent a market archive "may raise a flag, never clear one", so B is
#            used ONLY to establish a violation, never to grant a pass.
TT = read_hash("data/reference/tip_times.csv")
tt = pd.read_csv(TT)
tt["game_id"] = tt.game_id.astype(str)
tt["tip_b"] = pd.to_datetime(tt.tip_utc, utc=True)

wa = cv4[cv4.tip_time_quality.isin(["observed_single", "observed_revised"])]
tipA = dict(zip(wa.game_id, wa.scheduled_tip_time))
tipB = dict(zip(tt.game_id, tt.tip_b))

both = sorted(set(tipA) & set(tipB))
disagree = [g for g in both if abs((tipA[g] - tipB[g]).total_seconds()) > 60]

# unconditional lower bound needing NO tip evidence at all: the earliest instant that can belong to
# calendar date `game_date` under any convention where game_date is a local date at or west of UTC.
def date_lb(gid):
    return pd.Timestamp(date_of[gid] + " 00:00:00", tz="UTC")


def tip_witness(gid):
    """(tip, witness_class) or (None, 'NONE')."""
    if gid in tipA:
        return tipA[gid], "A_contract_v4_observed"
    if gid in tipB:
        return tipB[gid], "B_market_archive_ALARM_ONLY"
    return None, "NONE"


# empirical check that game_date is a LOCAL (ET) date, not a UTC date
offs = []
for gid in sorted(full_ids):
    t, c = tip_witness(gid)
    if t is not None:
        offs.append((t - pd.Timestamp(date_of[gid] + " 00:00:00", tz="UTC")).total_seconds() / 3600.0)
offs = np.array(offs)

OUT["observation_time_witnesses"] = {
    "witness_A": {"artifact": "experiments/prediction_contract_v4/game.parquet",
                  "column": "scheduled_tip_time",
                  "admitted_quality": ["observed_single", "observed_revised"],
                  "games_witnessed": len(tipA),
                  "d10_verdict_on_this_object": "CUTOFF_VALID (ledger #26)"},
    "witness_B": {"artifact": "data/reference/tip_times.csv", "column": "tip_utc",
                  "games_witnessed": len(tipB),
                  "d10_verdict_on_this_object": "CUTOFF_UNPROVEN (ledger #23)",
                  "admissibility": "ALARM ONLY - a market archive may raise a flag, never clear "
                                   "one (S33R precedent / S30 section 8 / P2B). Used here solely "
                                   "to PROVE violations; never to grant a pass.",
                  "covers_2021": bool((tt.season == 2021).any())},
    "cross_check": {"games_witnessed_by_both": len(both),
                    "disagreements_gt_60s": len(disagree), "disagreeing_game_ids": disagree[:50]},
    "coverage_over_full_schedule": {
        "A_only": len(set(tipA) - set(tipB)), "B_only": len(set(tipB) - set(tipA)),
        "both": len(both),
        "witnessed_any": len(set(tipA) | set(tipB)),
        "UNWITNESSED": len(full_ids - (set(tipA) | set(tipB))),
        "unwitnessed_by_season": {str(s): int(sum(1 for g in full_ids -
                                                  (set(tipA) | set(tipB)) if season_of[g] == s))
                                  for s in sorted(set(season_of.values()))},
    },
    "game_date_is_a_LOCAL_date_not_a_UTC_date": {
        "test": "hours from 00:00 UTC of game_date to the witnessed tip",
        "n": int(offs.size), "min": float(offs.min()), "max": float(offs.max()),
        "reading": "max exceeds 24h, so game_date cannot be a UTC date; min exceeds 4h, "
                   "consistent with an EASTERN calendar date. The unconditional lower bound used "
                   "below (00:00 UTC of game_date) is therefore strictly conservative.",
    },
    "event_completion_model": {
        "END_LOWER_BOUND": "tip + 40 minutes of regulation game clock (+5 min per OT period). A "
                           "final score cannot exist earlier under any circumstance. Wall clock is "
                           "strictly longer, so this is a hard floor, never an estimate.",
        "no_END_UPPER_BOUND_is_asserted": (
            "this node declines to assert a wall-clock envelope, because an envelope is a "
            "plausibility argument in the direction of PASS and the ledger's rule forbids exactly "
            "that. Instead the SLACK (cutoff minus source tip) is reported, and a slack of >= 4 "
            "hours is recorded as 'event unambiguously complete' with the threshold stated."),
        "SLACK_SAFE_HOURS": 4.0,
    },
}

# per-game OT periods (for the END lower bound) from the possession stream
POSS = read_hash("experiments/player_program/possessions_v2/possessions_raw_v2.parquet")
poss = pd.read_parquet(POSS, columns=["game_id", "period", "offense_team_id"])
poss["game_id"] = poss.game_id.astype(str)
maxper = poss.groupby("game_id")["period"].max().to_dict()


def end_lower_bound(gid):
    """(timestamp, basis). Hard floor on when this game's final score can exist."""
    t, cls = tip_witness(gid)
    ot = max(0, int(maxper.get(gid, 4)) - 4)
    if t is not None:
        return t + timedelta(minutes=40 + 5 * ot), cls
    return date_lb(gid), "NONE_unconditional_date_floor"


SLACK_SAFE_HOURS = 4.0


def classify(target_gid, source_gid):
    """Point-in-time classification of ONE (target row, latest contributing source game) pair."""
    if source_gid is None:
        return "NO_CONTRIBUTING_SOURCE", None, None
    c = cutoff_of.get(target_gid)
    if c is None:
        return "TARGET_HAS_NO_CUTOFF", None, None
    lb, basis = end_lower_bound(source_gid)
    if lb > c:
        return ("PROVEN_AFTER_CUTOFF_no_tip_needed"
                if basis == "NONE_unconditional_date_floor" else
                "PROVEN_AFTER_CUTOFF"), basis, None
    # UNCONDITIONAL PASS, needing no tip evidence at all: a game that can start no earlier than
    # 00:00 UTC of its own calendar date cannot still be in progress 24 hours later. So if the
    # source date's floor plus a full day still precedes the cutoff, the EVENT provably completed.
    if date_lb(source_gid) + timedelta(hours=24) <= c:
        return "EVENT_COMPLETE_BEFORE_CUTOFF_no_tip_needed", "NONE_unconditional_date_ceiling", None
    t, cls = tip_witness(source_gid)
    if t is None:
        return "UNWITNESSED_SOURCE_TIP", basis, None
    slack = (c - t).total_seconds() / 3600.0
    if slack >= SLACK_SAFE_HOURS:
        return "EVENT_COMPLETE_BEFORE_CUTOFF", cls, slack
    return "INDETERMINATE_WITHIN_4H_BAND", cls, slack


def evaluate(pairs, label):
    """pairs: iterable of (target_game_id, latest_source_game_id, target_team_id or None)."""
    cnt = Counter()
    by_policy = defaultdict(Counter)
    by_season = defaultdict(Counter)
    fail_witness = Counter()
    fail_lateness_h = []
    examples = []
    slacks = []
    for tgid, sgid, tid in pairs:
        v, basis, slack = classify(tgid, sgid)
        cnt[v] += 1
        by_policy[policy_of.get(tgid, "NONE")][v] += 1
        by_season[str(season_of.get(tgid))][v] += 1
        if v.startswith("PROVEN_AFTER_CUTOFF"):
            fail_witness[basis] += 1
            fail_lateness_h.append(
                (end_lower_bound(sgid)[0] - cutoff_of[tgid]).total_seconds() / 3600.0)
        if slack is not None:
            slacks.append(slack)
        if v.startswith("PROVEN_AFTER_CUTOFF") and len(examples) < 25:
            examples.append({
                "target_game_id": tgid, "target_team_id": (int(tid) if tid is not None else None),
                "target_game_date": date_of.get(tgid),
                "target_forecast_cutoff": str(cutoff_of.get(tgid)),
                "target_cutoff_policy": policy_of.get(tgid),
                "latest_contributing_source_game_id": sgid,
                "source_game_date": date_of.get(sgid),
                "source_end_lower_bound_utc": str(end_lower_bound(sgid)[0]),
                "source_witness": end_lower_bound(sgid)[1]})
    n = sum(cnt.values())
    bad = sum(v for k, v in cnt.items() if k.startswith("PROVEN_AFTER_CUTOFF"))
    good = sum(v for k, v in cnt.items() if k.startswith("EVENT_COMPLETE_BEFORE_CUTOFF"))
    return {
        "event_claim_PASSES_on_rows": good,
        "event_claim_FAILS_on_rows": bad,
        "event_claim_NOT_ESTABLISHED_on_rows": n - good - bad
        - cnt.get("NO_CONTRIBUTING_SOURCE", 0),
        "construction": label,
        "rows_evaluated": n,
        "verdict_counts": dict(sorted(cnt.items())),
        "rows_with_an_observation_provably_after_their_own_cutoff": bad,
        "share_of_rows_failing_the_event_claim": round(bad / n, 6) if n else None,
        "failures_by_witness_class": dict(sorted(fail_witness.items())),
        "failures_resting_only_on_the_ALARM_ONLY_market_archive":
            fail_witness.get("B_market_archive_ALARM_ONLY", 0),
        "failures_provable_from_CUTOFF_VALID_evidence_alone":
            fail_witness.get("A_contract_v4_observed", 0)
            + fail_witness.get("NONE_unconditional_date_floor", 0),
        "lateness_hours_of_failures": ({
            "min": float(np.min(fail_lateness_h)), "p50": float(np.median(fail_lateness_h)),
            "max": float(np.max(fail_lateness_h))} if fail_lateness_h else None),
        "by_cutoff_policy": {k: dict(sorted(v.items())) for k, v in sorted(by_policy.items())},
        "by_season": {k: dict(sorted(v.items())) for k, v in sorted(by_season.items())},
        "slack_hours_when_measurable": ({
            "n": len(slacks), "min": float(np.min(slacks)), "p05": float(np.percentile(slacks, 5)),
            "p50": float(np.percentile(slacks, 50)), "max": float(np.max(slacks))} if slacks
            else None),
        "examples_of_failures": examples,
    }


# =================================================== 4. LATEST CONTRIBUTOR UNDER EACH SEQUENCING
# Regimes actually used by this slate's code (re-read from the producers, not assumed):
#   ROW-strict  : ordered by (game_date, game_id), up to but NOT including the current row.
#                 features_common.STRICTLY_PRIOR_STATEMENT. An earlier SAME-DAY game_id counts.
#   DATE-strict : game_date strictly earlier than the current row's game_date.
#                 build_projected_exposure.build_pace (`d < r.game_date`); SC01's ratings;
#                 build_score_baselines.build_eff_ewmas / build_league_average.
tr_sorted = team_rows.sort_values(["team_id", "game_date", "game_id"],
                                  kind="mergesort").reset_index(drop=True)

prev_row_career, prev_row_season, prev_date_team, prev_date_team_season = {}, {}, {}, {}
for tid, sub in tr_sorted.groupby("team_id", sort=True):
    gids = sub.game_id.tolist()
    dts = sub.game_date.tolist()
    sns = sub.season.tolist()
    for i in range(len(gids)):
        key = (gids[i], int(tid))
        prev_row_career[key] = gids[i - 1] if i > 0 else None
        j = i - 1
        while j >= 0 and sns[j] != sns[i]:
            j -= 1
        prev_row_season[key] = gids[j] if j >= 0 else None
        k = i - 1
        while k >= 0 and dts[k] >= dts[i]:
            k -= 1
        prev_date_team[key] = gids[k] if k >= 0 else None
        k2 = k
        while k2 >= 0 and sns[k2] != sns[i]:
            k2 -= 1
        prev_date_team_season[key] = gids[k2] if k2 >= 0 else None

g_ids = games.game_id.tolist()
g_dts = games.game_date.tolist()
prev_row_league, prev_date_league = {}, {}
for i in range(len(g_ids)):
    prev_row_league[g_ids[i]] = g_ids[i - 1] if i > 0 else None
    k = i - 1
    while k >= 0 and g_dts[k] >= g_dts[i]:
        k -= 1
    prev_date_league[g_ids[i]] = g_ids[k] if k >= 0 else None

team_keys = list(zip(team_rows.game_id, team_rows.team_id))

# ============================================ 5. TARGET 1 -- the possession prior, re-derived
# The producer (build_projected_exposure.build_pace) is re-implemented here EXACTLY, so the
# contributing source set of every row is not argued but recomputed, and the recomputation is
# checked against the frozen artifact's own values.
PP = read_hash("experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet")
pp = pd.read_parquet(PP)
pp["game_id"] = pp.game_id.astype(str)
pp["team_id"] = pp.team_id.astype("int64")
pp["gd"] = pd.to_datetime(pp.game_date).dt.strftime("%Y-%m-%d")

REGULATION_MIN, WINDOW_K, MIN_HISTORY_M = 40.0, 10, 3
n_off = (poss.groupby(["game_id", "offense_team_id"]).size().rename("n_off_poss").reset_index()
         .rename(columns={"offense_team_id": "team_id"}))
n_off["team_id"] = n_off.team_id.astype("int64")
gmin = {g: REGULATION_MIN + 5.0 * max(0, int(m) - 4) for g, m in maxper.items()}
n_off["reg_equiv"] = n_off.n_off_poss * REGULATION_MIN / n_off.game_id.map(gmin)
game_pace = n_off.groupby("game_id")["reg_equiv"].mean().to_dict()

sched = pp[["game_id", "team_id", "gd", "season"]].drop_duplicates(["game_id", "team_id"])
sched = sched.sort_values(["team_id", "gd", "game_id"], kind="mergesort").reset_index(drop=True)

G = (sched[["game_id", "gd", "season"]].drop_duplicates("game_id")
     .sort_values(["gd", "game_id"], kind="mergesort").reset_index(drop=True))
G["game_pace"] = G.game_id.map(game_pace)
by_date = G.groupby("gd")["game_pace"].agg(["sum", "count"]).sort_index()
league_prior_mean = (by_date["sum"].cumsum().shift(1) / by_date["count"].cumsum().shift(1)).to_dict()
league_prior_n = by_date["count"].cumsum().shift(1).to_dict()
sorted_dates = sorted(by_date.index)
prev_date_of_date = {d: (sorted_dates[i - 1] if i > 0 else None) for i, d in enumerate(sorted_dates)}
last_game_on_date = G.groupby("gd")["game_id"].max().to_dict()

hist = {}
for t, sub in sched.groupby("team_id", sort=True):
    hist[t] = list(zip(sub.gd, sub.season, sub.game_id))

pace_rows, pace_sources = [], {}
for r in sched.itertuples(index=False):
    h = hist[r.team_id]
    same = [(d, gid) for (d, s, gid) in h if d < r.gd and s == r.season]
    prev = [(d, gid) for (d, s, gid) in h if d < r.gd and s == r.season - 1]
    if len(same) >= MIN_HISTORY_M:
        level, src, vals = 1, "team_window_same_season", same[-WINDOW_K:]
        est, n_hist = float(np.mean([game_pace[g] for _, g in vals])), len(vals)
        srcs = [g for _, g in vals]
    elif len(prev) >= MIN_HISTORY_M:
        level, src, vals = 2, "team_window_prior_season", prev[-WINDOW_K:]
        est, n_hist = float(np.mean([game_pace[g] for _, g in vals])), len(vals)
        srcs = [g for _, g in vals]
    else:
        lm, ln = league_prior_mean.get(r.gd, np.nan), league_prior_n.get(r.gd, np.nan)
        if pd.notna(lm):
            level, src, est, n_hist = 3, "league_prior_all", float(lm), int(ln)
            pd_ = prev_date_of_date.get(r.gd)
            srcs = [last_game_on_date[pd_]] if pd_ else []
        else:
            level, src, est, n_hist, srcs = 4, "unresolved_no_prior_games", np.nan, 0, []
    pace_rows.append((r.game_id, r.team_id, level, src, n_hist, est))
    pace_sources[(r.game_id, int(r.team_id))] = srcs

RP = pd.DataFrame(pace_rows, columns=["game_id", "team_id", "pace_level", "pace_source",
                                      "n_history_games", "team_pace_estimate"])
agg = RP.groupby("game_id")["team_pace_estimate"].agg(
    m="mean", n="size", u=lambda s: s.isna().sum())
proj = {g: (np.nan if u > 0 else m) for g, m, u in zip(agg.index, agg["m"], agg["u"])}

frozen = pp.set_index(["game_id", "team_id"])
rep = {"rows": int(len(RP)), "level_mismatch": 0, "source_mismatch": 0,
       "n_history_mismatch": 0, "estimate_max_abs_diff": 0.0, "projected_max_abs_diff": 0.0}
for r in RP.itertuples(index=False):
    f = frozen.loc[(r.game_id, int(r.team_id))]
    rep["level_mismatch"] += int(f["pace_level"] != r.pace_level)
    rep["source_mismatch"] += int(f["pace_source"] != r.pace_source)
    rep["n_history_mismatch"] += int(int(f["n_history_games"]) != int(r.n_history_games))
    a, b = f["team_pace_estimate"], r.team_pace_estimate
    if not (pd.isna(a) and pd.isna(b)):
        rep["estimate_max_abs_diff"] = max(rep["estimate_max_abs_diff"], abs(float(a) - float(b)))
    a2, b2 = f["projected_team_off_possessions"], proj[r.game_id]
    if not (pd.isna(a2) and pd.isna(b2)):
        rep["projected_max_abs_diff"] = max(rep["projected_max_abs_diff"], abs(float(a2) - float(b2)))
rep["reproduces_frozen_artifact_exactly"] = bool(
    rep["level_mismatch"] == 0 and rep["source_mismatch"] == 0 and rep["n_history_mismatch"] == 0
    and rep["estimate_max_abs_diff"] < 1e-9 and rep["projected_max_abs_diff"] < 1e-9)

# the frozen byte pin, recomputed under the S36 canonicalisation
pp_sorted = pp.sort_values(by=["game_id", "team_id"],
                           key=lambda s: s.astype(str)).reset_index(drop=True)
rep["frozen_column_pin_projected_team_off_possessions"] = {
    "recomputed_column_sha256": column_digest(pp_sorted.projected_team_off_possessions.tolist()),
    "pinned": "9078790427e0c3357dd8fe6a337fcc96852bfbfedaac48d963f5686894ac71bd",
    "recomputed_join_key_sha256": join_key_digest(
        list(zip(pp_sorted.game_id.tolist(), pp_sorted.team_id.tolist()))),
    "pinned_join_key": "6b8b2709af3890c40a2fbc14eec36f02a5eae048aece1480ce7f3929126dd59b",
}
rep["frozen_column_pin_projected_team_off_possessions"]["column_matches"] = bool(
    rep["frozen_column_pin_projected_team_off_possessions"]["recomputed_column_sha256"] ==
    rep["frozen_column_pin_projected_team_off_possessions"]["pinned"])
rep["frozen_column_pin_projected_team_off_possessions"]["join_key_matches"] = bool(
    rep["frozen_column_pin_projected_team_off_possessions"]["recomputed_join_key_sha256"] ==
    rep["frozen_column_pin_projected_team_off_possessions"]["pinned_join_key"])

# EXHAUSTIVE point-in-time evaluation over the universe rows SC08 actually consumes.
# SC08 consumes the GAME-level sum of the two sides, so a game fails if EITHER side fails.
pace_pairs_team, pace_pairs_game = [], []
worst_by_game = {}
for (gid, tid), srcs in pace_sources.items():
    if gid not in uni_ids:
        continue
    latest = max(srcs, key=lambda g: (date_of[g], g)) if srcs else None
    pace_pairs_team.append((gid, latest, tid))
    cur = worst_by_game.get(gid)
    if latest is not None and (cur is None or (date_of[latest], latest) > (date_of[cur], cur)):
        worst_by_game[gid] = latest
for gid in sorted(uni_ids):
    pace_pairs_game.append((gid, worst_by_game.get(gid), None))

n_src = [len(s) for (g, t), s in pace_sources.items() if g in uni_ids]
T1 = {
    "target": "opponent.opp_pace_estimate class -- team_possession_prior_v1.parquet "
              "(projected_team_off_possessions), D10 ledger #50 (and #49)",
    "consumed_by": ["SC08_SIGMA_MARGIN_MAP z1 = z(projected_team_off_possessions)",
                    "experiments/market_program/SCORE_BASELINES/build_score_baselines.py "
                    "(the composite baseline's pace factor -> pred_home/away/total/margin/p_home)"],
    "d10_ledger_words_engaged_with": (
        "those receipts attest construction order, not observation time... This is the sharpest "
        "case in the ledger of the difference between 'validated' and 'timestamped'."),
    "artifact_contamination_check_graph_policy_13_2_2": {
        "manifest_sibling_expected":
            "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet"
            ".manifest.json",
        "manifest_sibling_present": os.path.exists(
            P("experiments/player_program/projected_exposure_v1/"
              "team_possession_prior_v1.parquet.manifest.json")),
        "asof_granularity_declared": None,
        "granularity_established_by_re_derivation_instead": "row",
        "evidence": "the producer's own selection predicate is `d < r.game_date` (same season, "
                    "then prior season, then a league mean over strictly earlier dates). Every "
                    "row's value therefore depends only on games on dates strictly before that "
                    "row's own date, and this node reproduced all 2,990 rows exactly under that "
                    "predicate. The artifact is ROW-granular AT DATE RESOLUTION. That is a "
                    "stronger statement than the missing manifest carries, and a weaker one than "
                    "cutoff validity requires.",
    },
    "exact_re_derivation": rep,
    "contributing_source_set_size": {
        "n_rows": len(n_src), "min": int(min(n_src)) if n_src else None,
        "max": int(max(n_src)) if n_src else None,
        "mean": round(float(np.mean(n_src)), 4) if n_src else None,
        "definition": "the explicit list of prior GAMES whose realised possession counts enter "
                      "this row's value (last <= WINDOW_K=10 qualifying games, or the previous "
                      "date's league mean at level 3)",
    },
    "coverage": "EXHAUSTIVE -- every one of the 2,982 universe team-game rows and all 1,491 "
                "clusters; no sampling",
    "point_in_time_per_team_row": evaluate(pace_pairs_team, "pace prior, per team-game row"),
    "point_in_time_per_game_cluster_worst_side": evaluate(
        pace_pairs_game, "pace prior, per game cluster (worst of the two sides) -- this is the "
                         "grain SC08 consumes"),
}

# ================================ 6. TARGET 2/3 -- lagged and recent-form constructions in the slate
# Enumerated by reading the eleven arm modules and features_common, not taken from the A9 table.
CONSTRUCTIONS = [
    ("SC01_OPP_ADJ_INTERACTING", "ridge rating fit on strictly-prior two-season-window rows "
     "(pts of prior games)", "DATE_strict_team", "opponent.prior_box_aggregates"),
    ("SC02_A07_SCORE_TRANSIENT", "prior_count(same_season=True): count of same-season strictly-"
     "prior COMPLETED games", "ROW_strict_team_same_season", "opponent.prior_box_aggregates"),
    ("SC03_SEASON_CARRYOVER_PRIOR", "prior_season_aggregates: whole-PRIOR-SEASON settled margin/"
     "env means", "PRIOR_SEASON_team", "opponent.prior_box_aggregates"),
    ("SC03_SEASON_CARRYOVER_PRIOR", "prior_count(same_season=True) fade clock",
     "ROW_strict_team_same_season", "opponent.prior_box_aggregates"),
    ("SC04_HCA_LEAGUE_DRIFT", "league_prior_ewma(home_minus_away, halflife 60 league games)",
     "ROW_strict_league", "opponent.prior_box_aggregates"),
    ("SC05_HCA_TEAM_OFFSETS", "prior_home_away_split(margin): strictly-prior own home/away means",
     "ROW_strict_team_career", "opponent.prior_box_aggregates"),
    ("SC08_SIGMA_MARGIN_MAP", "prior_rolling_sd(margin, window 20): rolling sd of last <= 20 "
     "strictly-prior own settled margins", "ROW_strict_team_career",
     "opponent.prior_box_aggregates"),
    ("SC08_SIGMA_MARGIN_MAP", "pace_prior(): the byte-pinned possession artifact",
     "DATE_strict_team", "opponent.opp_pace_estimate"),
    ("SC10_FORM_TREND", "prior_ewma(halflife 4, same_season) -- L_short RECENT FORM",
     "ROW_strict_team_same_season", "opponent.prior_box_aggregates"),
    ("SC10_FORM_TREND", "prior_ewma(halflife 12, same_season) -- L_med RECENT FORM",
     "ROW_strict_team_same_season", "opponent.prior_box_aggregates"),
    ("SC10_FORM_TREND", "prior_expanding_mean(same_season) -- L_long season-to-date anchor",
     "ROW_strict_team_same_season", "opponent.prior_box_aggregates"),
    ("SC10_FORM_TREND", "orthogonalisation covariate: shift(1).rolling(window).mean() and "
     "shift(1).expanding().mean() on margin", "ROW_strict_team_same_season",
     "opponent.prior_box_aggregates"),
    ("SC11_LEAGUE_TOTAL_DRIFT", "league_prior_ewma(total, halflife 60 league games)",
     "ROW_strict_league", "opponent.prior_box_aggregates"),
    ("SC12_ROBUST_INPUT_WINSOR", "prior_ewma(span 10, career) on margin AND clip(margin,+/-15)",
     "ROW_strict_team_career", "opponent.prior_box_aggregates"),
    ("SC12_ROBUST_INPUT_WINSOR", "prior_count(same_season=False) support floor",
     "ROW_strict_team_career", "opponent.prior_box_aggregates"),
]

REGIME_LATEST = {
    "ROW_strict_team_career": lambda gid, tid: prev_row_career.get((gid, int(tid))),
    "ROW_strict_team_same_season": lambda gid, tid: prev_row_season.get((gid, int(tid))),
    "DATE_strict_team": lambda gid, tid: prev_date_team.get((gid, int(tid))),
    "DATE_strict_team_same_season": lambda gid, tid: prev_date_team_season.get((gid, int(tid))),
    "ROW_strict_league": lambda gid, tid: prev_row_league.get(gid),
    "DATE_strict_league": lambda gid, tid: prev_date_league.get(gid),
}

regime_results = {}
for regime, fn in REGIME_LATEST.items():
    if regime.endswith("league"):
        pairs = [(gid, fn(gid, None), None) for gid in games.game_id]
    else:
        pairs = [(gid, fn(gid, tid), tid) for gid, tid in team_keys]
    regime_results[regime] = evaluate(pairs, regime)

# SC03's prior-season regime, handled separately: the latest contributing observation is the
# team's LAST game of the previous season (and the league mean over that whole season).
prev_season_last = {}
for tid, sub in tr_sorted.groupby("team_id", sort=True):
    last_of = sub.groupby("season")["game_id"].max().to_dict()
    for gid, sn in zip(sub.game_id, sub.season):
        prev_season_last[(gid, int(tid))] = last_of.get(sn - 1)
league_season_last = team_rows.groupby("season")["game_id"].max().to_dict()
ps_pairs = []
for gid, tid in team_keys:
    a = prev_season_last.get((gid, int(tid)))
    b = league_season_last.get(int(season_of[gid]) - 1)   # league_mean_env spans the whole season
    cand = [x for x in (a, b) if x is not None]
    latest = max(cand, key=lambda g: (date_of[g], g)) if cand else None
    ps_pairs.append((gid, latest, tid))
regime_results["PRIOR_SEASON_team"] = evaluate(ps_pairs, "PRIOR_SEASON_team")

T23 = {
    "target": "opponent.prior_box_aggregates (D10 ledger #51) AND every lagged-outcome / "
              "recent-form construction in the slate",
    "enumeration_method": "read from the eleven arm modules and runner/features_common.py in this "
                          "worktree, not taken from the A9 table",
    "constructions": [{"arm": a, "construction": c, "sequencing_regime": r, "ledger_field": f}
                      for a, c, r, f in CONSTRUCTIONS],
    "sequencing_regimes_found": {
        "ROW_strict": "ordered by (game_date, game_id), up to but NOT including the current row; "
                      "an earlier SAME-DAY game_id DOES count as prior "
                      "(features_common.STRICTLY_PRIOR_STATEMENT, verbatim)",
        "DATE_strict": "game_date strictly earlier than the current row's game_date "
                       "(SC01's card wording; the pace producer's `d < r.game_date`)",
        "PRIOR_SEASON": "whole previous season aggregates, carried across the season boundary",
    },
    "coverage": "EXHAUSTIVE -- all 2,982 team-game rows (team regimes) / all 1,491 clusters "
                "(league regimes); no sampling. Only the LATEST contributing source per row is "
                "classified, which is sufficient and exact: the latest source binds, so if it "
                "clears the cutoff every earlier source does too.",
    "point_in_time_by_regime": regime_results,
}

# ========================== 7. TARGET 4 -- the five score_baseline_rows prediction columns
SB = read_hash("experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet")
BUILDER = read_hash("experiments/market_program/SCORE_BASELINES/build_score_baselines.py")
sb = pd.read_parquet(SB)
sb["game_id"] = sb.game_id.astype(str)

EFF_SPAN, EFF_ALPHA, EFF_MIN_HISTORY, BLEND = 10, 2.0 / 11.0, 3, 0.5


def lagged_ewma(vals):
    e = None
    for v in vals:
        e = v if e is None else EFF_ALPHA * v + (1.0 - EFF_ALPHA) * e
    return e


# --- re-derive the builder's own inputs, exactly as build_score_baselines.py does them ---------
mt_h = mt[mt.is_home == 1][["game_id", "game_date", "season", "team_id", "opp_team_id",
                            "pts", "opp_pts"]].copy()
mt_h = mt_h.rename(columns={"team_id": "home_team_id", "opp_team_id": "away_team_id",
                            "pts": "home_pts", "opp_pts": "away_pts"})
mt_h["actual_total"] = mt_h.home_pts + mt_h.away_pts
mt_h["actual_margin"] = mt_h.home_pts - mt_h.away_pts
mt_h["y_home_win"] = (mt_h.home_pts > mt_h.away_pts).astype(float)
mt_h = mt_h.sort_values(["game_date", "game_id"], kind="mergesort").reset_index(drop=True)

tg = mt[["game_id", "team_id", "game_date", "pts", "opp_pts"]].merge(
    n_off, on=["game_id", "team_id"], how="left", validate="1:1")
tg = tg[tg.n_off_poss.notna()].copy()
opp = tg[["game_id", "team_id", "n_off_poss"]].rename(
    columns={"team_id": "otid", "n_off_poss": "n_def_poss"})
tg = tg.merge(opp, on="game_id", how="left")
tg = tg[tg.team_id != tg.otid].drop(columns=["otid"])
tg["ppp_off"] = tg.pts / tg.n_off_poss
tg["ppp_def"] = tg.opp_pts / tg.n_def_poss
tg = tg.sort_values(["team_id", "game_date", "game_id"], kind="mergesort").reset_index(drop=True)

eff, eff_sources = {}, {}
for tid, sub in tg.groupby("team_id", sort=True):
    sub = sub.sort_values(["game_date", "game_id"], kind="mergesort")
    dts, offs_, defs_, gids = (sub.game_date.tolist(), sub.ppp_off.tolist(),
                               sub.ppp_def.tolist(), sub.game_id.tolist())
    for i in range(len(sub)):
        pri = [j for j in range(len(sub)) if dts[j] < dts[i]]
        if len(pri) >= EFF_MIN_HISTORY:
            eff[(gids[i], int(tid))] = (lagged_ewma([offs_[j] for j in pri]),
                                        lagged_ewma([defs_[j] for j in pri]), len(pri))
        else:
            eff[(gids[i], int(tid))] = (None, None, len(pri))
        eff_sources[(gids[i], int(tid))] = [gids[j] for j in pri]

pace_by_game = {r.game_id: (r.projected_team_off_possessions if r.pace_resolved else None)
                for r in pp.drop_duplicates("game_id").itertuples(index=False)}

comp_rows, comp_sources = [], {}
for g in mt_h.itertuples(index=False):
    p = pace_by_game.get(g.game_id)
    if p is None or (isinstance(p, float) and math.isnan(p)):
        continue
    h = eff.get((g.game_id, int(g.home_team_id)))
    a = eff.get((g.game_id, int(g.away_team_id)))
    if h is None or a is None or h[0] is None or a[0] is None:
        continue
    hs = p * (BLEND * h[0] + (1 - BLEND) * a[1])
    as_ = p * (BLEND * a[0] + (1 - BLEND) * h[1])
    comp_rows.append({"game_id": g.game_id, "season": int(g.season), "pred_home": hs,
                      "pred_away": as_, "pred_total": hs + as_, "pred_margin": hs - as_,
                      "y_home_win": float(g.y_home_win)})
    srcs = set(eff_sources[(g.game_id, int(g.home_team_id))]) | \
        set(eff_sources[(g.game_id, int(g.away_team_id))]) | \
        set(pace_sources.get((g.game_id, int(g.home_team_id)), [])) | \
        set(pace_sources.get((g.game_id, int(g.away_team_id)), []))
    comp_sources[g.game_id] = srcs
comp = pd.DataFrame(comp_rows)


def fit_logistic_1d(x, y, max_iter=200, tol=1e-10, ridge=1e-9):
    X = np.column_stack([np.ones(len(x)), np.asarray(x, float)])
    b = np.zeros(2)
    for _ in range(max_iter):
        eta = X @ b
        p = 1.0 / (1.0 + np.exp(-eta))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + ridge * np.eye(2)
        gvec = X.T @ (np.asarray(y, float) - p) - ridge * b
        step = np.linalg.solve(H, gvec)
        b = b + step
        if np.max(np.abs(step)) < tol:
            break
    return b


ph = pd.Series(np.nan, index=comp.index)
wf_fits = {}
for s in sorted(comp.season.unique()):
    trn = comp[comp.season < s]
    if len(trn) == 0:
        wf_fits[int(s)] = None
        continue
    beta = fit_logistic_1d(trn.pred_margin.to_numpy(), trn.y_home_win.to_numpy())
    wf_fits[int(s)] = {"n_train": int(len(trn)),
                       "train_seasons": sorted(int(x) for x in trn.season.unique())}
    m = comp.season == s
    ph[m] = 1.0 / (1.0 + np.exp(-(beta[0] + beta[1] * comp.loc[m, "pred_margin"].to_numpy())))
comp["p_home"] = ph

frozen_comp = sb[sb.method == "composite_pace_x_eff_v1"].sort_values(
    "game_id", key=lambda s: s.astype(str)).reset_index(drop=True)
mine = comp.sort_values("game_id", key=lambda s: s.astype(str)).reset_index(drop=True)

PINS = {"pred_margin": "1d79ff3adeda3d66e26f3bda1702d36301da447d87828c474d488d793de44ff4",
        "pred_total": "16c312aba2f964682f4d20a694b09890f4488f0e5bcdf31f827946158e145f3d",
        "p_home": "8a92c017e4f8606c3a7405116a455dc746493581454dc4dcbe1aab6d00b41989"}
rederiv = {"frozen_rows": int(len(frozen_comp)), "re_derived_rows": int(len(mine)),
           "game_id_sets_identical": bool(set(frozen_comp.game_id) == set(mine.game_id)),
           "columns": {}}
for c in ("pred_home", "pred_away", "pred_total", "pred_margin", "p_home"):
    a = frozen_comp[c].to_numpy(float)
    b = mine[c].to_numpy(float)
    both_nan = np.isnan(a) & np.isnan(b)
    d = np.abs(np.where(both_nan, 0.0, a - b))
    entry = {"max_abs_diff": float(np.nanmax(d)) if len(d) else None,
             "n_nan_frozen": int(np.isnan(a).sum()), "n_nan_re_derived": int(np.isnan(b).sum()),
             "nan_positions_identical": bool((np.isnan(a) == np.isnan(b)).all())}
    if c in PINS:
        got = column_digest(frozen_comp[c].tolist())
        entry["frozen_column_sha256_recomputed"] = got
        entry["pinned"] = PINS[c]
        entry["byte_pin_reproduces"] = bool(got == PINS[c])
        entry["re_derived_column_sha256"] = column_digest(mine[c].tolist())
        entry["re_derivation_is_byte_identical_to_the_pin"] = bool(
            entry["re_derived_column_sha256"] == PINS[c])
    rederiv["columns"][c] = entry

# fallback method rows (league_average_v1) -- the 26 composite-uncovered clusters use these
lg_by_date = mt_h.groupby("game_date").agg(n=("game_id", "size")).sort_index()
lg_dates = lg_by_date.index.tolist()
prev_lg_date = {d: (lg_dates[i - 1] if i > 0 else None) for i, d in enumerate(lg_dates)}
last_gid_on_date = mt_h.groupby("game_date")["game_id"].max().to_dict()

sb_pairs, la_pairs = [], []
for gid in sorted(uni_ids):
    if gid in comp_sources and comp_sources[gid]:
        latest = max(comp_sources[gid], key=lambda g: (date_of[g], g))
    else:
        latest = None
    sb_pairs.append((gid, latest, None))
    pdt = prev_lg_date.get(date_of[gid])
    la_pairs.append((gid, last_gid_on_date.get(pdt) if pdt else None, None))

comp_uncovered = sorted(uni_ids - set(frozen_comp.game_id))
T4 = {
    "target": "the five score_baseline_rows prediction columns pred_home / pred_away / "
              "pred_total / pred_margin / p_home",
    "status_before_this_node": "byte pins + an S34-adjudicated registration + a line-numbered "
                               "provenance argument, but NO cutoff-validity measurement. S37 "
                               "section 8: their 'provenance argument was not re-derived from the "
                               "builder's own inputs'.",
    "artifact_contamination_check_graph_policy_13_2_2": {
        "manifest_sibling_present": os.path.exists(
            P("experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet"
              ".manifest.json")),
        "asof_granularity_declared": None,
        "granularity_established_by_re_derivation_instead": "row (at DATE resolution) for "
            "pred_home/pred_away/pred_total/pred_margin; SEASON for the p_home calibration layer",
    },
    "builder": {"path": "experiments/market_program/SCORE_BASELINES/build_score_baselines.py",
                "sha256": READS["experiments/market_program/SCORE_BASELINES/"
                                "build_score_baselines.py"],
                "own_inputs_named_in_the_builder": [
                    "data/masters/master_team.parquet",
                    "experiments/player_program/projected_exposure_v1/"
                    "team_possession_prior_v1.parquet",
                    "experiments/player_program/possessions_v2/possessions_raw_v2.parquet"]},
    "re_derivation_from_the_builders_own_inputs": rederiv,
    "walk_forward_calibration_layer": {
        "rule": "logistic(pred_margin) fitted ONLY on seasons strictly earlier than the target's "
                "season, applied to that season; never pooled, never same-season",
        "fits_by_season": wf_fits,
        "granularity": "SEASON, not row. Every training observation for season S belongs to a "
                       "season that ended before season S began, so the SEASON bound implies the "
                       "row bound for this layer; the binding constraint on p_home is therefore "
                       "pred_margin's own date-strict source set, not the calibration fit.",
    },
    "composite_method_coverage": {
        "universe_clusters": len(uni_ids),
        "clusters_carrying_composite_pace_x_eff_v1": len(set(frozen_comp.game_id) & uni_ids),
        "clusters_falling_back_to_league_average_v1": len(comp_uncovered),
        "fallback_clusters_by_season": {str(s): int(sum(1 for g in comp_uncovered
                                                        if season_of[g] == s))
                                        for s in sorted(set(season_of.values()))},
    },
    "coverage": "EXHAUSTIVE -- all 1,491 universe clusters under both methods; no sampling",
    "point_in_time_composite_pace_x_eff_v1": evaluate(
        sb_pairs, "composite baseline: union of both teams' date-strict efficiency history and "
                  "the pace prior's own source games"),
    "point_in_time_league_average_v1_fallback": evaluate(
        la_pairs, "league_average_v1: expanding league means over all games on strictly earlier "
                  "dates -- evaluated on all 1,491 clusters"),
    "point_in_time_league_average_v1_ON_THE_26_CLUSTERS_THAT_ACTUALLY_USE_IT": evaluate(
        [p for p in la_pairs if p[0] in set(comp_uncovered)],
        "league_average_v1 restricted to the composite-uncovered clusters the universe actually "
        "falls back to"),
    "point_in_time_AS_CONSUMED_BY_THE_UNIVERSE": evaluate(
        [(p[0], p[1], None) for p in sb_pairs if p[0] not in set(comp_uncovered)]
        + [p for p in la_pairs if p[0] in set(comp_uncovered)],
        "the C_margin / C_total / C_p_home columns as build_universe actually assembles them: "
        "composite where covered, league_average_v1 on the 26 uncovered clusters"),
}

# ============================================================== 8. NEW FINDINGS (measured, not asserted)
# N1: fold-train moments applied to training rows.
zscore_rows = {}
FOLDS = {"train_lt_2022": [2021], "train_lt_2023": [2021, 2022],
         "train_lt_2024": [2021, 2022, 2023], "train_lt_2025": [2021, 2022, 2023, 2024],
         "train_lt_2026": [2021, 2022, 2023, 2024, 2025]}
for f, trs in FOLDS.items():
    sub = games[games.season.isin(trs)]
    if len(sub) == 0:
        continue
    last = sub.sort_values(["game_date", "game_id"]).iloc[-1]
    n_after = 0
    for gid in sub.game_id:
        c = cutoff_of.get(gid)
        lb, _ = end_lower_bound(last.game_id)
        if c is not None and lb > c:
            n_after += 1
    zscore_rows[f] = {
        "train_clusters": int(len(sub)),
        "latest_observation_entering_the_fold_train_moment": {
            "game_id": last.game_id, "game_date": last.game_date,
            "end_lower_bound_utc": str(end_lower_bound(last.game_id)[0])},
        "train_clusters_whose_own_cutoff_PRECEDES_that_observation": n_after,
        "share": round(n_after / len(sub), 6),
    }

# N2: same-day contribution census under the ROW-strict convention.
same_day_team = sum(1 for gid, tid in team_keys
                    if prev_row_career.get((gid, int(tid))) is not None
                    and date_of[prev_row_career[(gid, int(tid))]] == date_of[gid])
same_day_league = sum(1 for gid in games.game_id
                      if prev_row_league.get(gid) is not None
                      and date_of[prev_row_league[gid]] == date_of[gid])

OUT["new_findings_measured"] = {
    "N1_fold_train_moments_are_not_row_level_as_of": {
        "what": "zscore_train() / center_on_train() / SC08's pooled_sd fallback / the lambda "
                "selection tail compute a FOLD-TRAIN constant over the whole training window and "
                "apply it to every training row, including rows whose own forecast_cutoff long "
                "precedes the last training observation.",
        "consumers": ["SC08 sigma_z_pace_prior and sigma_z_lagged_margin_sd (zscore_train)",
                      "SC08 pooled train margin sd fallback (36 clusters per the card)",
                      "SC04 and SC11 centred league drift (center_on_train)",
                      "SC01 and SC10 lambda selection on the train tail"],
        "not_in_the_A9_table": True,
        "measured": zscore_rows,
        "scope_note": "TEST rows are unaffected: every fold's training seasons end before its "
                      "test season begins. The defect, if the tier-2 standard binds training "
                      "rows, is confined to training rows. This is the standard walk-forward "
                      "convention, so the coordinator must decide whether D065's 'every "
                      "underlying observation predates the forecast cutoff' binds per-row on "
                      "training rows or only on evaluation rows. This node does not decide it.",
    },
    "N2_same_day_prior_games_are_admitted_by_the_ROW_strict_convention": {
        "what": "features_common.STRICTLY_PRIOR_STATEMENT admits an earlier SAME-DAY game_id as "
                "prior. Under the date_only_prior_day_cutoff policy the row's cutoff is 18:00 UTC "
                "on the day BEFORE, so a same-day source game is provably after the cutoff with "
                "no tip evidence required at all.",
        "team_rows_whose_immediately_prior_own_game_is_SAME_DAY": same_day_team,
        "game_clusters_whose_immediately_prior_league_game_is_SAME_DAY": same_day_league,
        "note": "SC01's card and the pace producer both use the DATE-strict reading instead, so "
                "the slate contains two different meanings of 'strictly prior' with different "
                "point-in-time consequences. features_common's own docstring asserts the "
                "opposite rationale -- that the primitives exist so the phrase cannot mean "
                "eleven different things.",
    },
    "N3_no_asof_granularity_manifest_on_either_consumed_artifact": {
        "team_possession_prior_v1.parquet": "no sibling .manifest.json; asof_granularity "
                                            "UNDECLARED",
        "score_baseline_rows.parquet": "no sibling .manifest.json; asof_granularity UNDECLARED",
        "why_it_matters": "GRAPH_POLICY 13.2.2 makes the manifest the gate for relying on a "
                          "pre-built artifact. Both artifacts were consumed by the frozen cards "
                          "without one. This node established row granularity by re-derivation "
                          "instead, which is stronger evidence than the manifest would have "
                          "carried -- but the process control was absent.",
    },
}

# ======================= 8b. TIMESTAMP PROVENANCE TRACE (coordinator relay #04, acted on)
# A passing `observed_after_cutoff == 0` proves nothing if the timestamp compared is synthetic.
# So: state what every timestamp this node relies on IS, and name every neighbouring validation
# this node deliberately did NOT credit.
wa_full = cv4[cv4.tip_time_quality.isin(["observed_single", "observed_revised"])]
OUT["timestamp_provenance_trace"] = {
    "why_this_section_exists": (
        "a concurrent integrity audit found a cutoff-availability check that passes BY "
        "CONSTRUCTION: prediction_contract_v5.py:459 sets the S2 source's candidate_observed_time "
        "to pd.Timestamp(f'{season}-01-01T00:00:00Z'), a SYNTHETIC SEASON-START MARKER, and "
        "validate_projected_exposure.py:565 then asserts observed_after_cutoff == 0 for "
        "B_s2_weak_fallback, which cannot fail. It is disclosed at build_projected_exposure.py:"
        "128-135, so it is not concealed. This node treats it as the failure shape to test itself "
        "against."),
    "timestamps_this_node_RELIES_ON": {
        "forecast_cutoff": {
            "artifact": "experiments/prediction_contract_v4/game.parquet",
            "what_it_is": "the per-row decision boundary itself, not an observation timestamp",
            "synthetic": "PARTLY, AND DECLARED: 1,088 of 1,495 rows use "
                         "date_only_prior_day_cutoff = 18:00 UTC on the day before, which is a "
                         "POLICY constant, not a measurement. It is the repository's own declared "
                         "cutoff and the D10 ledger joins to the same column, so it is used here "
                         "as given. Note the direction: a policy cutoff that sits EARLIER than a "
                         "real one makes this audit STRICTER, never laxer.",
        },
        "witness_A_scheduled_tip_time": {
            "artifact": "experiments/prediction_contract_v4/game.parquet",
            "capture_timestamp_column": "tip_time_observed_at",
            "d10_verdict": "CUTOFF_VALID (ledger #26)",
            "GENUINE_OR_SYNTHETIC": "GENUINE",
            "trace": {
                "rows": int(len(wa_full)),
                "n_null_capture_timestamps": int(wa_full.tip_time_observed_at.isna().sum()),
                "n_distinct_capture_timestamps": int(wa_full.tip_time_observed_at.nunique()),
                "capture_timestamp_range": [str(wa_full.tip_time_observed_at.min()),
                                            str(wa_full.tip_time_observed_at.max())],
                "rows_whose_capture_precedes_their_own_scheduled_tip":
                    int((wa_full.tip_time_observed_at < wa_full.scheduled_tip_time).sum()),
                "rows_whose_capture_precedes_their_own_forecast_cutoff":
                    int((wa_full.tip_time_observed_at <= wa_full.forecast_cutoff).sum()),
                "is_a_constant_marker": bool(wa_full.tip_time_observed_at.nunique() <= 1),
                "underlying_feed": {k: int(v) for k, v in
                                    wa_full.tip_time_source.value_counts().items()},
            },
            "verdict": "199 distinct capture instants spanning 2025-07-05..2026-07-30, none null, "
                       "every one preceding both its own tip and its own cutoff. This is a real "
                       "capture series, not a marker. LIMITATION, stated: live capture only began "
                       "in July 2025, so witness A exists for 2025/2026 games only and cannot "
                       "witness 2021-2024 at all.",
            "market_lineage_disclosed": "the underlying feed is odds_extension / "
                                        "props_historical, i.e. an odds feed. What makes it "
                                        "admissible under the D10 ledger is not its lineage but "
                                        "its screened per-row capture timestamp, which is exactly "
                                        "what witness B lacks.",
        },
        "witness_B_tip_times_csv": {
            "artifact": "data/reference/tip_times.csv",
            "capture_timestamp_column": None,
            "d10_verdict": "CUTOFF_UNPROVEN (ledger #23)",
            "GENUINE_OR_SYNTHETIC": "GENUINE VALUES, NO CAPTURE TIMESTAMP",
            "how_it_is_used_here": "ALARM ONLY. It is permitted to PROVE a violation and is never "
                                   "permitted to grant a pass, per the S33R precedent that a "
                                   "market archive 'may raise a flag, never clear one'. Every "
                                   "verdict in this receipt reports separately how many failures "
                                   "rest on witness B alone.",
        },
        "REFUSED__master_team_observed_time": {
            "what_it_is": "a LOCAL FILE MTIME IN MID-2026 (10 distinct values, all 2026-07-31 / "
                          "2026-08-01), which the manifest itself says is not an as-of bound",
            "used_by_this_node": False,
            "dropped_at_load": True,
            "why": "treating it as the observation timestamp would manufacture exactly the false "
                   "pass the coordinator relay describes -- except in the opposite direction, "
                   "since it postdates every cutoff and would manufacture a universal FAIL. "
                   "Either way it is not an observation time and this node never reads it.",
        },
    },
    "validations_TRACED_AND_NOT_CREDITED": [
        {"validation": "validate_projected_exposure.py::_r2 (line 546) observed_after_cutoff",
         "what_timestamp_it_compares": "CONTRACT.candidate_observed_time vs forecast_cutoff",
         "applies_to": "the PLAYER-candidate frame (evaluation_tier A_primary / "
                       "B_transaction_sensitivity / B_s2_weak_fallback)",
         "genuine": "MIXED. A_primary compares captured as-of roster times. "
                    "B_s2_weak_fallback compares the SYNTHETIC season-start marker set at "
                    "prediction_contract_v5.py:459 and therefore passes by construction.",
         "credited_by_this_node": False,
         "why_not": "it is not a check on any tier-2 target. It bounds the player-candidate "
                    "roster path. team_possession_prior_v1 is built by build_pace(), which reads "
                    "only possessions_raw_v2 plus the schedule identities (game_id, team_id, "
                    "game_date, season) and never reads candidate_source, "
                    "roster_evidence_regime or candidate_observed_time."},
        {"validation": "validate_projected_exposure.py::pace_matches_independent_rederivation "
                       "(line 674)",
         "what_timestamp_it_compares": "NONE. It re-derives pace values without producer code.",
         "genuine": "yes, but it is a CONSTRUCTION-ORDER check, not an observation-time check",
         "credited_by_this_node": False,
         "why_not": "this node re-derived the artifact independently rather than inheriting the "
                    "claim; see targets.T1.exact_re_derivation. The independent re-derivation "
                    "AGREES, which is why this node can speak about the source set at all -- but "
                    "agreement about construction order is precisely what the D10 ledger already "
                    "said is not observation time."},
        {"validation": "PROJECTED_EXPOSURE_VALIDATION.json '35/35', cited by D10 field #49/#50",
         "what_timestamp_it_compares": "no per-observation timestamp for the pace artifact",
         "credited_by_this_node": False,
         "why_not": "the D10 ledger had already discounted it in the same words this node was "
                    "asked to engage with. This node neither credits nor re-litigates it."},
        {"validation": "score_baseline_rows byte pins in S35/S36 runner_constants.INPUT_PINS",
         "what_timestamp_it_compares": "NONE. Byte identity of a column, not observation time.",
         "credited_by_this_node": "only as byte identity",
         "why_not": "a byte pin proves the file has not changed. It says nothing about when the "
                    "observations inside it existed. This node re-derived the columns from the "
                    "builder's own inputs instead."},
    ],
    "pace_artifact_isolation_from_the_S2_marker": {
        "claim": "the synthetic S2 season-start marker cannot reach team_possession_prior_v1",
        "code_evidence": "build_projected_exposure.build_pace(base) consumes only "
                         "base[['game_id','team_id','game_date','season']] plus "
                         "possessions_raw_v2; candidate_observed_time is not in load_inputs()'s "
                         "`keep` list at all",
        "measured_evidence": "this node re-derived all 2,990 rows of the artifact from "
                             "master_team's schedule identities and the possession stream ALONE "
                             "-- no contract v5 frame, no roster regime, no candidate timestamps "
                             "-- and reproduced pace_level, pace_source, n_history_games, "
                             "team_pace_estimate and projected_team_off_possessions exactly, "
                             "including the frozen column byte pin.",
        "reproduced_exactly": rep["reproduces_frozen_artifact_exactly"],
        "byte_pin_reproduced":
            rep["frozen_column_pin_projected_team_off_possessions"]["column_matches"],
        "conclusion": "isolation established by reproduction, not by reading the code. The S2 "
                      "defect is real and is out of scope for these four targets.",
    },
    "self_check": {
        "did_this_node_credit_any_untraced_cutoff_availability_pass": False,
        "every_verdict_rests_on": "either (a) a re-derivation of the producer's own source set "
                                  "plus a tip witness whose provenance is traced above, or (b) an "
                                  "unconditional calendar-date floor requiring no timestamp at "
                                  "all. No verdict in this receipt inherits another node's pass.",
    },
}

# ================================================================================ 9. ASSEMBLE
OUT["targets"] = {"T1_opp_pace_estimate": T1, "T2_T3_prior_box_and_recent_form": T23,
                  "T4_score_baseline_prediction_columns": T4}

with open(os.path.join(HERE, "EVIDENCE_DETAIL.json"), "w", encoding="utf-8") as f:
    json.dump(OUT, f, indent=1, default=str)

print(json.dumps({
    "universe": OUT["universe"]["matches_pin"],
    "pace_re_derivation": rep["reproduces_frozen_artifact_exactly"],
    "pace_pin": rep["frozen_column_pin_projected_team_off_possessions"]["column_matches"],
    "score_baseline_pins": {c: rederiv["columns"][c].get("byte_pin_reproduces")
                            for c in PINS},
    "score_baseline_re_derivation_matches_pin": {
        c: rederiv["columns"][c].get("re_derivation_is_byte_identical_to_the_pin") for c in PINS},
    "T1_game_grain_verdicts":
        T1["point_in_time_per_game_cluster_worst_side"]["verdict_counts"],
    "T2_regimes": {k: v["verdict_counts"] for k, v in regime_results.items()},
    "T4_composite": T4["point_in_time_composite_pace_x_eff_v1"]["verdict_counts"],
    "T4_fallback": T4["point_in_time_league_average_v1_fallback"]["verdict_counts"],
    "same_day": {"team": same_day_team, "league": same_day_league},
}, indent=1, default=str))
