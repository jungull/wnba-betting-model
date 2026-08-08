"""E0_I0028 DEGENERACY SWEEP -- local machinery.

WHY LOCAL, NOT `_screen_kit`.  Three other agents are running concurrently in adjacent screen
directories and the kit has been edited by concurrent agents before (E1_I0022 recorded exactly that
reason).  The brief permits importing `_screen_kit`; this screen instead reimplements the four
things it needs (partition assertion on VALUES, r2/skill of a given forecast, block sign-flip null,
cyclic-shift control) so it has no cross-directory code dependency that could change under it
mid-run.  The IDEAS are credited:
  * value-based partition assertion        <- _screen_kit/screenkit.py :: assert_partition (K0/K4:
                                              a name match may only NOMINATE a column for a VALUE
                                              test; direction matters, PAST is not a holdout leak)
  * r2_of_forecast / skill semantics       <- E0_I0015_points_skill_decomposition/psd_base.py (D081)
  * block sign-flip paired null            <- E0_I0015/psd_base.py :: block_signflip_test (D081)
  * cyclic shift within groups             <- E1_I0021_heterogeneity_diagnostic/hd_base.py (D093)

TIME WINDOW TABLE -- what every constructed quantity reads.  (Trap 2: names lie. "prior",
"baseline" and "expected" have all appeared in this program on quantities that read the future.)

  quantity                       reads                                            strictly prior?
  -----------------------------  -----------------------------------------------  ---------------
  n_prior_appearances            champion's own provenance sidecar, as-of cutoff   YES (model's own)
  prior_games_admitted           contract frame, as-of cutoff                      YES (contract's)
  player_season_game_index       POSITION in the (season,player_id) date-sorted    YES (a count of
                                 series; a count of rows, no outcome touched       rows, not values)
  ref_<t> (B0)                   mean of the player's APPEARANCES at strictly      YES
                                 EARLIER dates in the same season; shift(1) BEFORE
                                 expanding
  lg_<t>                         mean over ALL rows at strictly EARLIER dates in   YES
                                 the same season (expanding, shift by date block)
  prev_<t>                       the player's mean over the PREVIOUS season        YES (seasons are
                                                                                   calendar-disjoint
                                                                                   -- ASSERTED)
  B1 / B2                        k*m + sum_prior over k + n_prior, from the above  YES
  k (the shrinkage constant)     selected on STRICTLY EARLIER SEASONS only; 2022   YES, with one
                                 uses the untuned prereg default k=5               declared exception

  *** EVERY quantity above is on the INPUT side.  minutes / pts / fga / appeared OF THE ROW BEING
  SCORED appear ONLY on the outcome side, and never in a region definition. ***
"""
import hashlib
import json
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.dirname(os.path.abspath(__file__))

V15 = os.path.join(ROOT, r"experiments\cbs_v15_player_oof_v5\attempt_001")
V14 = os.path.join(ROOT, r"experiments\cbs_v14_player_oof\attempt_001")

# *** PER-ARM CONTRACTS (prereg amendment f110da75...).  The two arms are NOT on the same contract:
# v15 emits 21617 rows for 2022-2024 and contract v5 has exactly 21617; v14 emits 17809 and contract
# v4 has exactly 17809.  Binding both arms to v4 would inner-join away 3808 v15 rows (17.6% of its
# output) -- precisely the obligations v5 added, which is the last population a degeneracy sweep
# can afford to lose. ***
CONTRACT_V4 = os.path.join(ROOT, r"experiments\prediction_contract_v4\player_game.parquet")
CONTRACT_V5 = os.path.join(ROOT,
                           r"experiments\prediction_contract_v5\player_game_enriched.parquet")

ARMS = {"cbs_v15_player_oof_v5": V15, "cbs_v14_player_oof": V14}
ARM_CONTRACT = {"cbs_v15_player_oof_v5": CONTRACT_V5, "cbs_v14_player_oof": CONTRACT_V4}

#: Pre-game observables the v5 contract carries and the v4 contract does not (added partitions
#: P15-P20).  Absent on the v14 arm, where they are recorded NOT_AVAILABLE, never silently skipped.
V5_ONLY_COLS = ["universe_tier", "evaluation_tier", "fit_eligible", "candidate_source",
                "team_assignment_confidence", "roster_evidence_regime"]
TARGETS = ["player_scoring_distribution", "e_minutes_given_active", "attempts_usage", "p_active"]
TRUTH = {"player_scoring_distribution": "pts", "e_minutes_given_active": "minutes",
         "attempts_usage": "fga", "p_active": "appeared"}
SEASONS = [2022, 2023, 2024]
SEED = 20260808
PREREG_SHA = "895bac8bc2255c9d660ac956873884eefbc95ddab6128fd80cbf90b8cbc6dac0"
K_GRID = [0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0]
K_DEFAULT_2022 = 5.0

QCOLS = ["pred_q05", "pred_q25", "pred_q50", "pred_q75", "pred_q95"]


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def assert_prereg():
    p = os.path.join(OUT, "_prereg.json")
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)
    got = d.pop("_prereg_sha256")
    blob = json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h = hashlib.sha256(blob).hexdigest()
    assert h == got == PREREG_SHA, "PREREG HASH MISMATCH: recomputed=%s stored=%s pinned=%s" % (
        h, got, PREREG_SHA)
    return h


# ------------------------------------------------------------------ partition guard (VALUE-based)
def assert_partition(f, allowed=(2022, 2023, 2024), verbose=True, label=""):
    """Value-based partition check.  Credit: screenkit.assert_partition (K0/K4).

    THE INVARIANT (K0): a substring match on a column NAME may only ever NOMINATE a column for a
    VALUE test.  It may never, by itself, cause a violation.
    THE DIRECTION RULE (K4): a value ABOVE the partition is the holdout direction and is ALWAYS
    fatal.  A value BELOW it is historical and cannot be a holdout leak, so it is recorded rather
    than fatal -- but only when the frame carries an in-partition ANCHOR proving the observation
    window really is inside the partition.
    """
    lo, hi = min(allowed), max(allowed)
    fatal, historical, checked_s, checked_d, anchors = [], [], [], [], []
    for c in f.columns:
        s = f[c]
        if pd.api.types.is_datetime64_any_dtype(s):
            checked_d.append(c)
            yr = s.dropna()
            if len(yr) == 0:
                continue
            yr = yr.dt.year
            if yr.max() > hi:
                fatal.append((c, "date", "FUTURE", int(yr.min()), int(yr.max())))
            elif yr.min() < lo:
                historical.append((c, "date", "PAST", int(yr.min()), int(yr.max())))
            else:
                anchors.append(c)
            continue
        if pd.api.types.is_bool_dtype(s) or not pd.api.types.is_numeric_dtype(s):
            continue
        v = pd.to_numeric(s, errors="coerce").dropna()
        if len(v) == 0:
            continue
        u = np.unique(v.to_numpy(dtype=float))
        # VALUE gate: only a column whose EVERY value is a plausible whole year is a season column.
        if not (u.min() >= 1990 and u.max() <= 2100 and np.allclose(u, np.round(u))):
            continue
        checked_s.append(c)
        if u.max() > hi:
            fatal.append((c, "season", "FUTURE", float(u.min()), float(u.max())))
        elif u.min() < lo:
            historical.append((c, "season", "PAST", float(u.min()), float(u.max())))
        else:
            anchors.append(c)
    if not anchors and historical:
        fatal += [tuple(list(h[:2]) + ["PAST_WITH_NO_ANCHOR"] + list(h[3:])) for h in historical]
    ok = len(fatal) == 0
    if verbose:
        print("  partition[%s]: season-valued=%s  date=%s  anchors=%s" %
              (label, checked_s, checked_d, anchors))
        if historical:
            print("    historical (PAST, non-fatal, anchored): %s" % (historical,))
        if fatal:
            print("    *** FATAL: %s" % (fatal,))
    assert ok, "PARTITION VIOLATION [%s]: %s" % (label, fatal)
    return {"ok": ok, "season_cols": checked_s, "date_cols": checked_d,
            "anchor_cols": anchors, "historical": historical}


# ------------------------------------------------------------------ metrics
def mae(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    return float(np.mean(np.abs(y[m] - yhat[m]))) if m.any() else float("nan")


def mse(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    return float(np.mean((y[m] - yhat[m]) ** 2)) if m.any() else float("nan")


def r2_of_forecast(y, yhat):
    """1 - SSE/SST on a GIVEN forecast.  NOTHING is fitted (D069 denominator; D081's form)."""
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    y, yhat = y[m], yhat[m]
    sst = float(((y - y.mean()) ** 2).sum())
    return 1.0 - float(((y - yhat) ** 2).sum()) / sst if sst > 0 else float("nan")


def loss_vec(y, yhat, target):
    """Per-row loss.  ABSOLUTE error for the three continuous targets; SQUARED error (Brier) for
    p_active, whose outcome is 0/1.  Declared in the prereg; restated here so no caller can pick."""
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    return (y - yhat) ** 2 if target == "p_active" else np.abs(y - yhat)


def skill_of(y, yhat, yref, target):
    """1 - LOSS_model/LOSS_ref on THE SAME rows (rows finite for BOTH forecasts)."""
    y = np.asarray(y, float)
    a = np.asarray(yhat, float)
    b = np.asarray(yref, float)
    m = np.isfinite(y) & np.isfinite(a) & np.isfinite(b)
    if not m.any():
        return float("nan"), float("nan"), float("nan"), 0
    la = float(np.mean(loss_vec(y[m], a[m], target)))
    lb = float(np.mean(loss_vec(y[m], b[m], target)))
    return (1.0 - la / lb if lb > 0 else float("nan")), la, lb, int(m.sum())


# ------------------------------------------------------------------ paired inference
def block_signflip(diff, block_codes, n_draws=4000, seed=SEED):
    """Paired permutation for mean(diff), sign flipped for a WHOLE block at a time.

    Credit: E0_I0015/psd_base.py :: block_signflip_test (D081).  Row-level sign flipping is the
    anticonservative null this program has been burned by four times and is NOT offered here.
    """
    d = np.asarray(diff, float)
    ok = np.isfinite(d)
    if not ok.any():
        return {"mean_diff": float("nan"), "p_two_sided_blockflip": float("nan"),
                "n_blocks": 0, "n_rows": 0, "null_sd": float("nan"), "n_draws": int(n_draws)}
    d = np.where(ok, d, 0.0)
    uq, inv = np.unique(np.asarray(block_codes), return_inverse=True)
    nb = len(uq)
    bsum = np.bincount(inv, weights=d, minlength=nb)
    n_ok = int(ok.sum())
    real = float(bsum.sum() / n_ok)
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_draws, nb))
    draws = (signs * bsum[None, :]).sum(axis=1) / n_ok
    p = (1.0 + int((np.abs(draws) >= abs(real)).sum())) / (n_draws + 1.0)
    return {"mean_diff": real, "p_two_sided_blockflip": float(p), "n_blocks": int(nb),
            "n_rows": n_ok, "null_sd": float(draws.std(ddof=1)), "n_draws": int(n_draws)}


# ------------------------------------------------------------------ loading
#: columns every arm's contract must supply, whatever its version
_CORE = ["row_uid", "game_id", "team_id", "player_id", "game_date", "season",
         "exact_cutoff_ok", "tip_time_quality", "minutes", "pts", "fga", "appeared",
         "in_target_box", "fold_id"]
_PER_TARGET = ["prediction_required__%s", "outcome_scoreable__%s"]
#: pre-game observables that exist only on ONE of the two contracts.  Taken when present.
_OPTIONAL = ["prior_games_admitted", "lookback_games_used", "candidate_at_cutoff",
             "n_prior_candidate_obligations", "n_prior_team_games", "is_cold_start",
             "universe_tier", "evaluation_tier", "fit_eligible", "candidate_source",
             "team_assignment_confidence", "roster_evidence_regime", "team_assignment_ambiguous",
             "n_prior_appearances"]


def load_contract(arm, verbose=True):
    """The truth + row universe FOR ONE ARM, from ITS OWN contract version.

    *** FILTERED TO 2022-2024 BEFORE ANYTHING ELSE TOUCHES IT. ***  The holdout is never in memory.
    """
    path = ARM_CONTRACT[arm]
    have = set(pd.read_parquet(path, columns=None).columns) if False else None
    import pyarrow.parquet as pq
    have = set(pq.ParquetFile(path).schema.names)
    cols = list(_CORE)
    for t in TARGETS:
        cols += [p % t for p in _PER_TARGET]
    cols += [x for x in _OPTIONAL if x in have]
    cols = [x for x in dict.fromkeys(cols) if x in have]
    c = pd.read_parquet(path, columns=cols)
    for x in _OPTIONAL:                       # NOT_AVAILABLE, never silently skipped
        if x not in c.columns:
            c[x] = pd.NA
    n0 = len(c)
    c = c[c["season"].isin(SEASONS)].copy()
    for col in ("pts", "fga"):
        c[col] = pd.to_numeric(c[col], errors="coerce").astype(float)
    c["minutes"] = c["minutes"].astype(float)
    c["appeared"] = c["appeared"].astype(bool)
    c = c.sort_values(["season", "player_id", "game_date", "game_id"],
                      kind="stable").reset_index(drop=True)
    # position inside the player's season series -- a COUNT OF ROWS, no outcome value touched
    c["player_season_game_index"] = c.groupby(["season", "player_id"]).cumcount()
    if verbose:
        print("  contract[%s] <- %s" % (arm, os.path.basename(path)))
        print("  %d rows total -> %d rows in 2022-2024 (%d dropped: 2021 + holdout)"
              % (n0, len(c), n0 - len(c)))
        print("  seasons present: %s   date span: %s .. %s"
              % (sorted(c["season"].unique()), c["game_date"].min().date(),
                 c["game_date"].max().date()))
    assert_partition(c[["season", "game_date"]], verbose=verbose, label="contract")
    assert c["game_date"].max() < pd.Timestamp("2025-01-01")
    return c


def assert_seasons_disjoint(c, verbose=True):
    """A previous-season aggregate is strictly prior ONLY IF the seasons do not overlap in calendar
    time.  Asserted, never assumed.  (D081 made the same assertion for the same reason.)"""
    g = c.groupby("season")["game_date"].agg(["min", "max"]).sort_index()
    prev = None
    for s, r in g.iterrows():
        if prev is not None:
            assert r["min"] > prev, "seasons overlap in calendar time"
        prev = r["max"]
    if verbose:
        for s, r in g.iterrows():
            print("    season %d: %s .. %s" % (s, r["min"].date(), r["max"].date()))
    return {str(int(s)): [str(r["min"].date()), str(r["max"].date())] for s, r in g.iterrows()}


def load_predictions(arm, target, verbose=False):
    """Champion output for one (arm, target) across 2022-2024, joined to its provenance sidecar."""
    base = ARMS[arm]
    frames, prov = [], []
    for s in SEASONS:
        p = os.path.join(base, "predictions__%s__%d.parquet" % (target, s))
        d = pd.read_parquet(p)
        d["season"] = s
        frames.append(d)
        q = os.path.join(base, "provenance_sidecar__%d.parquet" % s)
        pv = pd.read_parquet(q, columns=["row_uid", "target_key", "n_prior_candidate_games",
                                         "n_prior_appearances", "n_prior_available_obligations",
                                         "team_prior_games", "residual_pool_n", "selected_alpha",
                                         "selected_lambda"])
        prov.append(pv[pv["target_key"] == target])
    d = pd.concat(frames, ignore_index=True)
    pv = pd.concat(prov, ignore_index=True).drop(columns=["target_key"])
    n_before = len(d)
    d = d.merge(pv, on="row_uid", how="left", validate="one_to_one")
    assert len(d) == n_before
    d["arm_id_file"] = arm
    if verbose:
        print("    %-24s %-30s %6d rows  sidecar matched %6d"
              % (arm, target, len(d), int(d["n_prior_appearances"].notna().sum())))
    return d


# ------------------------------------------------------------------ strictly-prior baselines
def build_priors(c, verbose=True):
    """Attach the strictly-prior-games-only quantities every baseline is built from.

    CONSTRUCTION, stated so it can be checked rather than trusted:
      inside (season, player_id) sorted by game_date, for the APPEARANCE series only,
        n_app_prior[i]   = number of the player's appearances at STRICTLY EARLIER dates
        sum_<t>_prior[i] = sum of <t> over those appearances
      both are `.shift(1)` BEFORE any cumulative sum, so row i can never see row i.
      lg_<t>[i]   = mean of <t> over ALL appearances in the season at STRICTLY EARLIER DATES.
                    Built by aggregating per DATE and shifting the date series, so two rows on the
                    SAME date see the same value and neither sees the other.  (A plain expanding
                    mean over a row order would leak same-date rows into each other.)
      prev_<t>    = the player's mean over the PREVIOUS season (calendar-disjoint, asserted).
    """
    c = c.sort_values(["season", "player_id", "game_date", "game_id"],
                      kind="stable").reset_index(drop=True)
    app = c["appeared"].to_numpy()
    for t, col in (("pts", "pts"), ("minutes", "minutes"), ("fga", "fga"),
                   ("appeared", "appeared")):
        v = c[col].to_numpy(float)
        contrib = np.where(app, np.nan_to_num(v, nan=0.0), 0.0)
        if t == "appeared":                       # p_active is defined on ALL rows, not appearances
            contrib = np.nan_to_num(c["appeared"].to_numpy(float), nan=0.0)
        g = c.groupby(["season", "player_id"], sort=False)
        c["_c_" + t] = contrib
        c["sum_%s_prior" % t] = g["_c_" + t].transform(lambda s: s.shift(1).cumsum()).fillna(0.0)
        c.drop(columns=["_c_" + t], inplace=True)
    g = c.groupby(["season", "player_id"], sort=False)
    c["_app_f"] = c["appeared"].astype(float)
    c["n_app_prior"] = g["_app_f"].transform(lambda s: s.shift(1).cumsum()).fillna(0.0)
    c["n_row_prior"] = c["player_season_game_index"].astype(float)
    c.drop(columns=["_app_f"], inplace=True)

    # ---- league expanding means, shifted BY DATE so same-date rows never see each other ----
    for t, col in (("pts", "pts"), ("minutes", "minutes"), ("fga", "fga")):
        d = c[c["appeared"]].groupby(["season", "game_date"])[col].agg(["sum", "count"])
        d = d.sort_index()
        cs = d.groupby(level=0)[["sum", "count"]].apply(lambda x: x.shift(1).cumsum())
        cs.index = d.index
        lg = (cs["sum"] / cs["count"]).rename("lg_" + t)
        c = c.merge(lg.reset_index(), on=["season", "game_date"], how="left")
    d = c.groupby(["season", "game_date"])["appeared"].agg(["sum", "count"]).sort_index()
    cs = d.groupby(level=0)[["sum", "count"]].apply(lambda x: x.shift(1).cumsum())
    cs.index = d.index
    c = c.merge((cs["sum"] / cs["count"]).rename("lg_appeared").reset_index(),
                on=["season", "game_date"], how="left")

    # ---- previous-season player means (seasons are calendar-disjoint: asserted separately) ----
    prev = (c[c["appeared"]].groupby(["season", "player_id"])
            .agg(prev_pts=("pts", "mean"), prev_minutes=("minutes", "mean"),
                 prev_fga=("fga", "mean"), prev_n=("pts", "size")).reset_index())
    pa = (c.groupby(["season", "player_id"])["appeared"].mean()
          .rename("prev_appeared").reset_index())
    prev = prev.merge(pa, on=["season", "player_id"], how="outer")
    prev["season"] = prev["season"] + 1                       # attach to the FOLLOWING season
    c = c.merge(prev, on=["season", "player_id"], how="left")
    c["prev_n"] = c["prev_n"].fillna(0.0)

    # ---- B0: THE REFERENCE.  expanding mean of the player's prior APPEARANCES this season. ----
    for t in ("pts", "minutes", "fga", "appeared"):
        n = c["n_app_prior"] if t != "appeared" else c["n_row_prior"]
        with np.errstate(invalid="ignore", divide="ignore"):
            r = c["sum_%s_prior" % t] / n.replace(0, np.nan)
        lgc = c["lg_" + t]
        glob = float(c.loc[c["appeared"], t if t != "appeared" else "appeared"].astype(float).mean()) \
            if t != "appeared" else float(c["appeared"].mean())
        c["ref_" + t] = r.fillna(lgc).fillna(c["prev_" + t]).fillna(glob)
    if verbose:
        print("  priors built: shift(1) BEFORE cumsum; league means shifted BY DATE")
        print("  ref_ columns: %s" % [x for x in c.columns if x.startswith("ref_")])
    return c


def baseline_B(c, t, k, form):
    """B1 / B2: shrunk prior mean.  (k*m + sum_prior) / (k + n_prior).

    form='B1' -> m is the expanding LEAGUE mean over strictly-earlier games in the season.
    form='B2' -> m is the player's OWN previous-season mean when it rests on >= 5 prior-season
                 appearances, else the league mean.  Both are strictly prior.
    """
    n = (c["n_app_prior"] if t != "appeared" else c["n_row_prior"]).to_numpy(float)
    s = c["sum_%s_prior" % t].to_numpy(float)
    m = c["lg_" + t].to_numpy(float)
    if form == "B2":
        pv = c["prev_" + t].to_numpy(float)
        use = np.isfinite(pv) & (c["prev_n"].to_numpy(float) >= 5)
        m = np.where(use, pv, m)
    glob = float(np.nanmean(m))
    m = np.where(np.isfinite(m), m, glob)
    return (k * m + s) / (k + n)


def cyclic_shift_within_groups(x, codes, rng):
    """Rotate each group's series by a random offset.  Rows MUST already be in (group, date) order.
    Credit: E1_I0021_heterogeneity_diagnostic/hd_base.py (D093).  A within-group SHUFFLE is
    anticonservative for the autocorrelated prior-history series this program is made of."""
    out = np.array(x, dtype=float, copy=True)
    order = np.argsort(codes, kind="stable")
    sc = np.asarray(codes)[order]
    starts = np.flatnonzero(np.r_[True, sc[1:] != sc[:-1]])
    ends = np.r_[starts[1:], len(sc)]
    for a, b in zip(starts, ends):
        idx = order[a:b]
        n = b - a
        if n < 2:
            continue
        out[idx] = np.roll(np.asarray(x, float)[idx], int(rng.integers(0, n)))
    return out


def jwrite(name, obj):
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True, default=str)
    print("  wrote %s" % p)
    return p
