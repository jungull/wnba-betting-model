#!/usr/bin/env python3
"""
w2_integration.py — preregistered experiment w2_zone_channel_integration_v1.

Registered 2026-07-30T21:05:19Z in experiments/registry.jsonl (kind=experiment,
regime A, primary metric margin_mae, incumbent chanreval_structural_calibrated).
This script BUILDS and EVALUATES; it never registers. Every modeling choice below
is the registration's, not this script's:

  Challenger margin = the incumbent's 4-channel structural sum (chanreval
  pipeline, reproduced bit-for-bit by importing experiments/channel_reval/
  run_reval.py's own functions) with the paint and 3pt channels each multiplied
  by a bounded matchup factor from the zone-map machinery:

      factor(off_team, def_team, cutoff) =
          sum_{z in family} xp_contrib_z(matchup_differential @ maps_before(cutoff))
        / sum_{z in family} league_share_z * league_conv_z * pts_value_z
      clipped to [0.85, 1.15]   (fixed a priori in the registration)

  with family = {Restricted Area, In The Paint (Non-RA)} for paint and
  {Corner 3, Above the Break 3, Backcourt} for 3pt. Maps are season-to-date,
  strictly-before-cutoff (matchup_overlay.maps_before(game_date, season=season)),
  with the stored promoted shrinkage priors (data/zone_maps/shrinkage_priors.csv).
  FT and non-paint-2s channels untouched. The challenger is then recalibrated
  with the SAME train-years-only linear protocol as the incumbent (run_reval's
  fit_calibrations, replicated verbatim on the same 2021-2023 eligible games).

Walk-forward guarantees (HANDOFF §3 constitution):
  * maps_before(game_date) excludes the game itself and all same-day/future
    shots; audited here by hard-deleting all shots >= game date and by flipping
    every same-day/future make/miss (factors must be identical).
  * All fitted parameters (chain alphas, both calibrations) come from 2021-2023
    only, via the harness's outer split.
  * Before any comparison the incumbent is REPRODUCED on the identical 673
    chanreval test games: str_margin_cal pooled MAE must match the ledger
    (10.0860; 2024 8.94 / 2025 10.94 / 2026 10.24) within 0.01 — hard assert —
    and per-game predictions must match predictions_v2.csv within 1e-6.

Modes:
  --smoke   copies experiments/registry.jsonl to a scratch path, passes that as
            registry_path to compare_to_incumbent (the real ledger is never
            touched), writes all outputs to a scratch dir (or --outdir).
            Full computation — identical numbers to real mode.
  --real    the ledgered evaluation: default registry, outputs to
            experiments/w2_integration/. Run by the ORCHESTRATOR only, after
            independent verification of the smoke run.

This script never runs git, never calls evalharness.registry.register/evaluate/
record_evaluation directly, and never renders leaderboards. The only registry
write path is compare_to_incumbent's internal ledger append, pointed at the
scratch copy in smoke mode.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import evalharness as eh                              # noqa: E402
from evalharness.baselines import load_frozen_baselines  # noqa: E402
import matchup_overlay as mo                          # noqa: E402

EXPERIMENT_ID = "w2_zone_channel_integration_v1"
RUN_REVAL_PATH = REPO / "experiments" / "channel_reval" / "run_reval.py"
INCUMBENT_PRED_CSV = REPO / "experiments" / "channel_reval" / "predictions_v2.csv"
CHANREVAL_SUMMARY = REPO / "experiments" / "channel_reval" / "run_summary.json"
REGISTRY_PATH = REPO / "experiments" / "registry.jsonl"
OFFICIAL_OUTDIR = REPO / "experiments" / "w2_integration"

CLIP_LO, CLIP_HI = 0.85, 1.15          # preregistered fixed bounds
PAINT_FAMILY = ["Restricted Area", "In The Paint (Non-RA)"]
THREE_FAMILY = ["Corner 3", "Above the Break 3", "Backcourt"]

# Incumbent reproduction targets — the chanreval ledger record (run 1).
REPRO_TOL = 0.01
REPRO_POOLED = 10.0860
REPRO_BY_SEASON = {2024: 8.94, 2025: 10.94, 2026: 10.24}
N_UNIVERSE = 673

AUDIT_SEED = 20260730
AUDIT_PER_SEASON = 4                   # sampled test games per season (+ extremes + train picks)
CHANNEL_BOOT_SEED = 7                  # July convention for channel-level bootstrap
N_BOOT_CHANNEL = 2000

SHOT_COLS = ["GAME_ID", "team_id", "opp_team_id", "team_abbr", "opp_team_abbr",
             "season", "season_type", "zone", "pts_value", "shot_made",
             "pts_scored", "game_date"]


# --------------------------------------------------------------------------- #
# plumbing
# --------------------------------------------------------------------------- #

def load_run_reval():
    """Import the incumbent pipeline (run_reval.py) as a module — its functions
    are reused verbatim so the incumbent chains here ARE the chanreval chains."""
    spec = importlib.util.spec_from_file_location("w2_chanreval_pipeline", str(RUN_REVAL_PATH))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["w2_chanreval_pipeline"] = mod
    spec.loader.exec_module(mod)
    return mod


def mae(err: pd.Series) -> float:
    return float(err.abs().mean())


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp, datetime)):
        return str(o)
    return o


# --------------------------------------------------------------------------- #
# incumbent rebuild (chanreval pipeline, verbatim through rr.*)
# --------------------------------------------------------------------------- #

def rebuild_incumbent(rr):
    D = rr.load_base()
    splits = eh.walk_forward_by_season(
        D, date_col="GAME_DATE", season_col="season",
        min_train_seasons=3, test_seasons=rr.TEST_YEARS,
    )
    by_name = {s.name: s for s in splits}
    outer24 = by_name["season:2024"]
    train_seasons = sorted(D.loc[outer24.train_idx, "season"].unique())
    assert train_seasons == rr.TRAIN_YEARS, train_seasons

    alphas, _ = rr.tune_alphas(D, outer24)
    ref = json.loads(CHANREVAL_SUMMARY.read_text(encoding="utf-8"))
    assert alphas == ref["alphas"], (
        f"alpha tuning did not reproduce the chanreval record: {alphas} vs {ref['alphas']}")

    F = rr.build_features(D, alphas)
    games = rr.make_games(F)

    train_ids = set(D.loc[outer24.train_idx, "GAME_ID"])
    tg = games[games.GAME_ID.isin(train_ids) & games.eligible]
    assert sorted(tg.season_h.unique()) == rr.TRAIN_YEARS
    cal_inc = rr.fit_calibrations(tg)
    # calibration must also reproduce the ledgered incumbent calibration
    for key in ("str_margin", "str_home", "str_away", "raw_margin"):
        got, want = cal_inc[key], ref["calibration"][key]
        assert max(abs(got[0] - want[0]), abs(got[1] - want[1])) < 1e-6, (key, got, want)
    assert cal_inc["n_train_games"] == ref["calibration"]["n_train_games"]

    games = rr.apply_calibrations(games, cal_inc)

    test_ids = {}
    for s in rr.TEST_YEARS:
        split = by_name[f"season:{s}"]
        ids = set(D.loc[split.test_idx, "GAME_ID"])
        sel = games[games.GAME_ID.isin(ids)]
        assert (sel.season_h == s).all()
        test_ids[s] = ids
    n_total_test_games = int(D[D.season.isin(rr.TEST_YEARS)].GAME_ID.nunique())
    return D, alphas, games, train_ids, test_ids, cal_inc, n_total_test_games


def assert_incumbent_reproduced(et: pd.DataFrame, inc_pred: pd.DataFrame) -> dict:
    """Hard assert: the rebuilt incumbent equals the chanreval ledger record on
    the identical 673-game universe, pooled and per season, within 0.01 — and
    per game vs predictions_v2.csv within 1e-6."""
    out = {}
    ids_new, ids_ref = set(et.GAME_ID), set(inc_pred.GAME_ID)
    assert len(et) == N_UNIVERSE, f"eligible test games {len(et)} != {N_UNIVERSE}"
    assert ids_new == ids_ref, (
        f"universe mismatch: {len(ids_new - ids_ref)} only-new, {len(ids_ref - ids_new)} only-ref")

    m = et.merge(inc_pred, on="GAME_ID", suffixes=("", "_ref"), validate="one_to_one")
    for col in ("margin_true", "str_margin_cal", "raw_margin_cal",
                "str_home_cal", "str_away_cal", "str_total_cal"):
        d = float((m[col] - m[f"{col}_ref"]).abs().max())
        out[f"max_abs_diff_{col}"] = d
        assert d < 1e-6, f"per-game reproduction failed on {col}: max abs diff {d}"

    pooled = mae(et.str_margin_cal - et.margin_true)
    out["pooled_mae_str_margin_cal"] = pooled
    assert abs(pooled - REPRO_POOLED) <= REPRO_TOL, (pooled, REPRO_POOLED)
    for s, want in REPRO_BY_SEASON.items():
        sub = et[et.season_h == s]
        got = mae(sub.str_margin_cal - sub.margin_true)
        out[f"mae_{s}"] = got
        assert abs(got - want) <= REPRO_TOL, (s, got, want)
    out["passed"] = True
    return out


# --------------------------------------------------------------------------- #
# zone-map matchup factors
# --------------------------------------------------------------------------- #

def family_ratio(diff: pd.DataFrame, zones: list[str]) -> tuple[float, str | None]:
    """Overlay expected-points ratio vs league-neutral for a zone family.

    numerator   = sum of xp_contrib over the family's league-live zones
    denominator = sum of league_share * league_conv * pts_value over the same
    Zones with no league activity in the pre-cutoff slice contribute to neither
    side (explicitly, never via silent NaN propagation)."""
    sub = diff[diff["zone"].isin(zones)]
    live = sub[sub["league_share"].notna() & (sub["league_share"] > 0)]
    if live.empty:
        return np.nan, "no_league_live_zone_in_family"
    if live["xp_contrib"].isna().any():
        return np.nan, "nan_xp_contrib_in_live_zone"
    num = float(live["xp_contrib"].sum())
    den = float((live["league_share"] * live["league_conv"] * live["pts_value"]).sum())
    if not den > 0:
        return np.nan, "zero_league_neutral_denominator"
    return num / den, None


def factors_for_game_row(maps: dict, team_h: int, team_a: int) -> tuple[dict, list]:
    rec, fails = {}, []
    for side, off_t, def_t in (("h", team_h, team_a), ("a", team_a, team_h)):
        f_paint_raw = f_3pt_raw = np.nan
        reason = None
        try:
            diff = mo.matchup_differential(
                maps["offense"], maps["defense"], maps["league"], int(off_t), int(def_t))
            f_paint_raw, rp = family_ratio(diff, PAINT_FAMILY)
            f_3pt_raw, r3 = family_ratio(diff, THREE_FAMILY)
            reason = rp or r3
        except KeyError as exc:
            reason = f"no_map_for_team: {exc}"
        if reason is not None or not (np.isfinite(f_paint_raw) and np.isfinite(f_3pt_raw)):
            fails.append({"side": side, "off_team": int(off_t), "def_team": int(def_t),
                          "reason": reason or "non_finite_ratio"})
        rec[f"f_paint_raw_{side}"] = f_paint_raw
        rec[f"f_3pt_raw_{side}"] = f_3pt_raw
        rec[f"f_paint_{side}"] = float(np.clip(f_paint_raw, CLIP_LO, CLIP_HI)) if np.isfinite(f_paint_raw) else np.nan
        rec[f"f_3pt_{side}"] = float(np.clip(f_3pt_raw, CLIP_LO, CLIP_HI)) if np.isfinite(f_3pt_raw) else np.nan
    return rec, fails


def compute_factors(needed: pd.DataFrame, shots_slim: pd.DataFrame, k_table) -> tuple[pd.DataFrame, list]:
    """Season-to-date, strictly-pre-cutoff matchup factors for every game in
    `needed` (columns GAME_ID, GAME_DATE_h, season_h, TEAM_ID_h, TEAM_ID_a).
    One maps_before build per unique (season, date). Failures are counted and
    returned, never papered over."""
    rows, failures = [], []
    by_season = {int(s): df for s, df in shots_slim.groupby("season")}
    for (season, date), grp in needed.groupby(["season_h", "GAME_DATE_h"], sort=True):
        season = int(season)
        sshots = by_season.get(season)
        maps = (mo.maps_before(date, shots=sshots, season=season, k_table=k_table)
                if sshots is not None else None)
        if maps is None or maps["offense"] is None:
            for r in grp.itertuples():
                failures.append({"GAME_ID": r.GAME_ID, "season": season, "game_date": str(date),
                                 "side": "both", "reason": "no_prior_shots_in_season"})
            continue
        for r in grp.itertuples():
            rec, fails = factors_for_game_row(maps, r.TEAM_ID_h, r.TEAM_ID_a)
            rec.update({"GAME_ID": r.GAME_ID, "season": season, "game_date": date,
                        "map_n_shots": maps["n_shots"], "map_n_games": maps["n_games"]})
            rows.append(rec)
            for f in fails:
                failures.append({"GAME_ID": r.GAME_ID, "season": season,
                                 "game_date": str(date), **f})
    fac = pd.DataFrame(rows)
    return fac, failures


# --------------------------------------------------------------------------- #
# audits (must pass before any result is reported)
# --------------------------------------------------------------------------- #

def pick_audit_games(games2: pd.DataFrame, tg_mask, et_mask) -> pd.DataFrame:
    rng = np.random.default_rng(AUDIT_SEED)
    et = games2[et_mask]
    tg = games2[tg_mask]
    ids: list = []
    for s in sorted(et.season_h.unique()):
        pool = et.loc[et.season_h == s, "GAME_ID"].to_numpy()
        ids.extend(rng.choice(pool, size=min(AUDIT_PER_SEASON, len(pool)), replace=False).tolist())
    ids.append(et.loc[et.GAME_DATE_h.idxmin(), "GAME_ID"])   # thinnest map
    ids.append(et.loc[et.GAME_DATE_h.idxmax(), "GAME_ID"])   # fullest map
    for s in (2021, 2023):                                   # calibration-feeding train games
        pool = tg.loc[tg.season_h == s, "GAME_ID"].to_numpy()
        if len(pool):
            ids.append(rng.choice(pool))
    ids = list(dict.fromkeys(ids))
    return games2[games2.GAME_ID.isin(ids)][
        ["GAME_ID", "GAME_DATE_h", "season_h", "TEAM_ID_h", "TEAM_ID_a"]]


def audit_factor_walk_forward(sample: pd.DataFrame, shots_slim: pd.DataFrame,
                              k_table, fac: pd.DataFrame) -> dict:
    """Two audits per sampled game, against the production factors:
    (1) censor: hard-DELETE every shot with game_date >= the game's date and
        rebuild -> raw factors must be identical (no same-day/future shot enters);
    (2) perturb: FLIP make/miss on every shot with game_date >= the game's date
        and rebuild -> identical (outcomes on/after the cutoff cannot move the
        factor). Both are load-bearing: the audit also verifies shots existed
        on/after each cutoff, including the game's own shots."""
    fac_idx = fac.set_index("GAME_ID")
    raw_cols = ["f_paint_raw_h", "f_3pt_raw_h", "f_paint_raw_a", "f_3pt_raw_a"]
    per_game, worst = [], 0.0
    n_mismatch = 0
    for r in sample.itertuples():
        date, season = r.GAME_DATE_h, int(r.season_h)
        prod = fac_idx.loc[r.GAME_ID, raw_cols].astype(float).to_numpy()
        onafter = shots_slim.game_date >= date
        own = int(((shots_slim.GAME_ID == r.GAME_ID)).sum())
        n_onafter = int(onafter.sum())

        censored = shots_slim[~onafter]
        maps_c = mo.maps_before(date, shots=censored[censored.season == season],
                                season=season, k_table=k_table)
        rec_c, _ = factors_for_game_row(maps_c, r.TEAM_ID_h, r.TEAM_ID_a)
        got_c = np.array([rec_c[c] for c in raw_cols], dtype=float)

        pert = shots_slim.copy()
        pert.loc[onafter, "shot_made"] = (1 - pert.loc[onafter, "shot_made"]).astype(pert.shot_made.dtype)
        pert.loc[onafter, "pts_scored"] = (
            pert.loc[onafter, "shot_made"] * pert.loc[onafter, "pts_value"]).astype(pert.pts_scored.dtype)
        maps_p = mo.maps_before(date, shots=pert[pert.season == season],
                                season=season, k_table=k_table)
        rec_p, _ = factors_for_game_row(maps_p, r.TEAM_ID_h, r.TEAM_ID_a)
        got_p = np.array([rec_p[c] for c in raw_cols], dtype=float)

        d_c = float(np.nanmax(np.abs(got_c - prod)))
        d_p = float(np.nanmax(np.abs(got_p - prod)))
        ok = (d_c <= 1e-12) and (d_p <= 1e-12) and n_onafter > 0 and own > 0
        n_mismatch += int(not ok)
        worst = max(worst, d_c, d_p)
        per_game.append({"GAME_ID": int(r.GAME_ID), "season": season, "date": str(date.date()),
                         "n_shots_on_or_after_cutoff": n_onafter, "n_own_game_shots": own,
                         "censor_max_abs_diff": d_c, "perturb_max_abs_diff": d_p, "ok": bool(ok)})
    return {"n_games_audited": len(per_game), "n_mismatched_games": n_mismatch,
            "max_abs_diff": worst, "per_game": per_game,
            "passed": n_mismatch == 0 and len(per_game) >= 10}


def clip_activation(fac: pd.DataFrame, tg_ids: set, et_ids: set) -> pd.DataFrame:
    """Long table of clip-activation rates by subset x channel (+ per test season)."""
    f = fac.copy()
    f["subset"] = np.where(f.GAME_ID.isin(tg_ids), "train_2021_2023",
                           np.where(f.GAME_ID.isin(et_ids), "test_2024_2026", "other"))
    rows = []
    for ch in ("paint", "3pt"):
        raw = pd.concat([f[f"f_{ch}_raw_h"], f[f"f_{ch}_raw_a"]], ignore_index=True)
        meta = pd.concat([f[["subset", "season"]]] * 2, ignore_index=True)
        t = meta.assign(raw=raw).dropna(subset=["raw"])
        scopes = [("all", t)] + [(s, t[t.subset == s]) for s in ("train_2021_2023", "test_2024_2026")]
        scopes += [(f"test {s}", t[(t.subset == "test_2024_2026") & (t.season == s)])
                   for s in sorted(t.loc[t.subset == "test_2024_2026", "season"].unique())]
        for scope, sub in scopes:
            if not len(sub):
                continue
            rows.append({
                "channel": ch, "scope": scope, "n_team_games": int(len(sub)),
                "clip_low_rate": float((sub.raw < CLIP_LO).mean()),
                "clip_high_rate": float((sub.raw > CLIP_HI).mean()),
                "clip_total_rate": float(((sub.raw < CLIP_LO) | (sub.raw > CLIP_HI)).mean()),
                "raw_min": float(sub.raw.min()), "raw_p25": float(sub.raw.quantile(0.25)),
                "raw_median": float(sub.raw.median()), "raw_p75": float(sub.raw.quantile(0.75)),
                "raw_max": float(sub.raw.max()),
            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# challenger assembly, calibration, secondaries
# --------------------------------------------------------------------------- #

def add_challenger(games2: pd.DataFrame) -> pd.DataFrame:
    g = games2.copy()
    for side in ("h", "a"):
        g[f"w2_paint_{side}"] = g[f"f_paint_{side}"] * g[f"str_paint_{side}"]
        g[f"w2_3pt_{side}"] = g[f"f_3pt_{side}"] * g[f"str_3pt_{side}"]
        g[f"w2_sum_{side}"] = (g[f"str_ft_{side}"] + g[f"str_np2_{side}"]
                               + g[f"w2_paint_{side}"] + g[f"w2_3pt_{side}"])
    g["w2_margin_uncal"] = g["w2_sum_h"] - g["w2_sum_a"]
    return g


def fit_w2_calibration(rr, tg2: pd.DataFrame) -> dict:
    """The incumbent's exact train-years-only linear protocol (run_reval
    fit_calibrations), applied to the challenger sums: margin, home, away."""
    cal = {"n_train_games": int(len(tg2))}
    a, b = rr.linfit(tg2.w2_margin_uncal, tg2.margin_true)
    cal["w2_margin"] = (a, b)
    a, b = rr.linfit(tg2.w2_sum_h, tg2.team_pts_h)
    cal["w2_home"] = (a, b)
    a, b = rr.linfit(tg2.w2_sum_a, tg2.team_pts_a)
    cal["w2_away"] = (a, b)
    return cal


def apply_w2_calibration(g: pd.DataFrame, cal: dict) -> pd.DataFrame:
    g = g.copy()
    a, b = cal["w2_margin"]
    g["w2_margin_cal"] = a + b * g["w2_margin_uncal"]
    ah, bh = cal["w2_home"]
    g["w2_home_cal"] = ah + bh * g["w2_sum_h"]
    aa, ba = cal["w2_away"]
    g["w2_away_cal"] = aa + ba * g["w2_sum_a"]
    g["w2_total_cal"] = g["w2_home_cal"] + g["w2_away_cal"]
    return g


def channel_secondaries(rr, et2: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Per-team-game channel MAEs (paint, 3pt) challenger vs incumbent chain,
    with the July-convention per-row paired bootstrap; plus the 4x4 channel
    residual covariance matrices for both models."""
    rows = []
    for ch, inc_col, w2_col in (("paint", "str_paint", "w2_paint"), ("3pt", "str_3pt", "w2_3pt")):
        act = rr.CH_ACTUAL[ch]
        err_i = pd.concat([(et2[f"{inc_col}_h"] - et2[f"{act}_h"]).abs(),
                           (et2[f"{inc_col}_a"] - et2[f"{act}_a"]).abs()], ignore_index=True)
        err_c = pd.concat([(et2[f"{w2_col}_h"] - et2[f"{act}_h"]).abs(),
                           (et2[f"{w2_col}_a"] - et2[f"{act}_a"]).abs()], ignore_index=True)
        diffs = (err_c - err_i).to_numpy()
        rng = np.random.default_rng(CHANNEL_BOOT_SEED)
        boots = np.array([diffs[rng.integers(0, len(diffs), len(diffs))].mean()
                          for _ in range(N_BOOT_CHANNEL)])
        rows.append({"channel": ch, "n_team_games": int(len(diffs)),
                     "mae_incumbent_chain": float(err_i.mean()),
                     "mae_challenger_chain": float(err_c.mean()),
                     "delta_improvement": float(err_i.mean() - err_c.mean()),
                     "prob_challenger_better": float((boots < 0).mean())})
    ch_table = pd.DataFrame(rows)

    cov = {}
    for label, cols in (
        ("incumbent", {"ft": "str_ft", "3pt": "str_3pt", "paint": "str_paint", "np2": "str_np2"}),
        ("challenger", {"ft": "str_ft", "3pt": "w2_3pt", "paint": "w2_paint", "np2": "str_np2"}),
    ):
        errs = pd.DataFrame({
            c: pd.concat([et2[f"{col}_h"] - et2[f"{rr.CH_ACTUAL[c]}_h"],
                          et2[f"{col}_a"] - et2[f"{rr.CH_ACTUAL[c]}_a"]], ignore_index=True)
            for c, col in cols.items()})
        cov[label] = errs.cov().round(3)
    return ch_table, cov


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #

def fmt_cov(m: pd.DataFrame) -> list[str]:
    lines = ["| | " + " | ".join(m.columns) + " |",
             "|---|" + "---|" * len(m.columns)]
    for idx, row in m.iterrows():
        lines.append(f"| **{idx}** | " + " | ".join(f"{v:.3f}" for v in row) + " |")
    return lines


def write_report(path: Path, ctx: dict) -> None:
    reg = ctx["registration"]
    repro = ctx["repro"]
    res = ctx["result"]
    S = []
    A = S.append
    A("# w2_zone_channel_integration_v1 — zone-map matchup factors on the structural channel sum")
    A("")
    A(f"*Generated by `w2_integration.py` ({ctx['mode'].upper()} mode) at {ctx['generated_at']}.*")
    if ctx["mode"] == "smoke":
        A("*Smoke run: full computation, but the gate verdict was recorded to a SCRATCH copy of the")
        A("registry — the ledgered evaluation is the orchestrator's real-mode run. Numbers are")
        A("deterministic and identical between modes.*")
    A("")
    A("## Registration (binding)")
    A("")
    A(f"- id `{reg['experiment_id']}`, registered {reg['registered_at']}, regime {reg['regime']},")
    A(f"  primary metric {reg['primary_metric']}, incumbent `{reg['incumbent_id']}`, decision time {reg['decision_time']}.")
    th = reg["thresholds"]
    A(f"- Gate thresholds: min_improvement {th['min_improvement']}, harm_ci_bound {th['harm_ci_bound']},")
    A(f"  per_season_tolerance {th['per_season_tolerance']}, coverage_tolerance {th['coverage_tolerance']}.")
    A(f"- Factor: overlay expected-points ratio vs league-neutral per channel family, clipped to")
    A(f"  [{CLIP_LO}, {CLIP_HI}] (fixed a priori). Paint family = {{RA, Paint non-RA}}; 3pt family =")
    A("  {Corner 3, Above the Break 3, Backcourt}. FT and non-paint-2s channels untouched.")
    A("- Maps: `matchup_overlay.maps_before(game_date, season=season)` — season-to-date, strictly")
    A("  pre-cutoff, stored promoted shrinkage priors (`data/zone_maps/shrinkage_priors.csv`).")
    A("")
    A("## Incumbent reproduction (hard gate, ran before anything else)")
    A("")
    A(f"- Universe: the identical {N_UNIVERSE} chanreval test games (predictions_v2.csv) — game-set equality asserted.")
    A(f"- Rebuilt `str_margin_cal` vs predictions_v2.csv per game: max |diff| = {repro['max_abs_diff_str_margin_cal']:.2e}.")
    A(f"- Pooled MAE {repro['pooled_mae_str_margin_cal']:.4f} (ledger 10.0860); "
      f"2024 {repro['mae_2024']:.4f} / 2025 {repro['mae_2025']:.4f} / 2026 {repro['mae_2026']:.4f}")
    A("  (ledger 8.94 / 10.94 / 10.24) — all within the 0.01 tolerance. Chain alphas and the")
    A("  incumbent calibration also reproduced the ledgered values exactly (asserted at 1e-6).")
    A("")
    A("## Factor coverage")
    A("")
    fc = ctx["factor_coverage"]
    A(f"- Games needing factors: {fc['n_needed']} ({fc['n_train']} eligible train 2021-2023 for the")
    A(f"  calibration fit + {fc['n_test']} test). Factors produced for all sides of {fc['n_complete']} games;")
    A(f"  **{fc['n_failures']} factor failures**{' — see run_summary.json' if fc['n_failures'] else ''}.")
    A(f"- Calibration fit on {ctx['cal_w2']['n_train_games']} train games (incumbent used {ctx['cal_inc_n']}; "
      f"{'IDENTICAL' if ctx['cal_w2']['n_train_games'] == ctx['cal_inc_n'] else 'MISMATCH — protocol deviation, see concerns'}).")
    A("")
    A("## Audits (all ran before results were read)")
    A("")
    aud = ctx["audit_wf"]
    A(f"- **Walk-forward factor audit** on {aud['n_games_audited']} sampled games (test games from every")
    A("  season + earliest/fullest-map extremes + train-year games): (1) hard-delete every shot on/after")
    A("  the game date and rebuild; (2) flip every make/miss on/after the game date and rebuild.")
    A(f"  Factors identical in both variants for every game (max |diff| {aud['max_abs_diff']:.1e}, "
      f"mismatches {aud['n_mismatched_games']}) -> **{'PASS' if aud['passed'] else 'FAIL'}**.")
    A("  The factors are this experiment's only new derived features, so this is also the shift audit:")
    A("  nothing about the target game (or any later shot) can enter its own factor.")
    A("- **Clip activation** (raw ratio outside [0.85, 1.15]):")
    A("")
    A("| channel | scope | n team-games | below 0.85 | above 1.15 | total clipped | raw median | raw min..max |")
    A("|---|---|---|---|---|---|---|---|")
    for _, r in ctx["clip_table"].iterrows():
        A(f"| {r.channel} | {r.scope} | {r.n_team_games} | {r.clip_low_rate:.1%} | {r.clip_high_rate:.1%} | "
          f"**{r.clip_total_rate:.1%}** | {r.raw_median:.3f} | {r.raw_min:.3f}..{r.raw_max:.3f} |")
    A("")
    A("## Headline result (primary: margin MAE, paired, 90% date-clustered bootstrap)")
    A("")
    A(f"**VERDICT: {res['verdict']}** (promote={res['promote']}); failed gates: {res['failed_gates'] or 'none'}.")
    A("")
    A("| scope | n | challenger MAE | incumbent MAE | delta (＋=better) |")
    A("|---|---|---|---|---|")
    A(f"| pooled | {res['n_games']} | **{res['metric_challenger']:.4f}** | {res['metric_incumbent']:.4f} | "
      f"{res['pooled_improvement']:+.4f} |")
    for s in res["per_season"]:
        A(f"| {s['season']} | {s['n']} | {s['metric_challenger']:.4f} | {s['metric_incumbent']:.4f} | "
          f"{s['delta']:+.4f} |")
    A("")
    A(f"- 90% date-clustered bootstrap CI on the pooled delta: [{res['ci_low']:+.4f}, {res['ci_high']:+.4f}] "
      f"({res['n_clusters']} date clusters); team-clustered sensitivity "
      f"[{res['ci_sensitivity_team'][0]:+.4f}, {res['ci_sensitivity_team'][1]:+.4f}] "
      f"({res['ci_sensitivity_team'][2]} franchises).")
    g = res["gates"]
    A(f"- Gates: pooled>=+{th['min_improvement']} -> {g['gate1_pooled_improvement']}; "
      f"CI excludes harm -> {g['gate2_ci_excludes_harm']}; per-season non-inferiority -> "
      f"{g['gate3_per_season_non_inferiority']}; joint forecast -> {g['gate4_joint_forecast']}; "
      f"coverage -> {g['gate5_coverage']}.")
    jc = ctx["joint_detail"]["components"]
    A("- Joint forecast (gate 4): " + "; ".join(
        f"{k} {v['challenger_mae']:.3f} vs {v['incumbent_mae']:.3f} ({v['delta_improvement']:+.3f})"
        for k, v in jc.items()) + ".")
    A(f"- Uncalibrated margin MAE (diagnostic): challenger {ctx['uncal']['w2']:.4f} vs incumbent "
      f"{ctx['uncal']['str']:.4f}.")
    A("")
    A("## Preregistered secondaries (recorded, not gated)")
    A("")
    A("| channel | n team-games | incumbent chain MAE | challenger chain MAE | delta (＋=better) | P(challenger better) |")
    A("|---|---|---|---|---|---|")
    for _, r in ctx["ch_table"].iterrows():
        A(f"| {r.channel} | {r.n_team_games} | {r.mae_incumbent_chain:.4f} | {r.mae_challenger_chain:.4f} | "
          f"{r.delta_improvement:+.4f} | {r.prob_challenger_better:.3f} |")
    A("")
    A(f"(The registration's reporting bar for a meaningful per-channel gain is >= 0.10 points.)")
    A("")
    tot = ctx["totals"]
    A(f"- Game **total** MAE: challenger {tot['w2_total_mae']:.4f} vs incumbent {tot['str_total_mae']:.4f} "
      f"({tot['str_total_mae'] - tot['w2_total_mae']:+.4f}).")
    A("")
    A("### 4x4 channel residual covariance (error-cancellation structure, ROADMAP Phase 1.3)")
    A("")
    A("Incumbent (matches the chanreval ledger matrix within "
      f"{ctx['cov_check_max_diff']:.3g}):")
    A("")
    S.extend(fmt_cov(ctx["cov"]["incumbent"]))
    A("")
    A("Challenger:")
    A("")
    S.extend(fmt_cov(ctx["cov"]["challenger"]))
    A("")
    d_inc = ctx["cov"]["incumbent"]
    d_ch = ctx["cov"]["challenger"]
    A(f"- Variance diagonal (ft/3pt/paint/np2): incumbent "
      f"{'/'.join(f'{d_inc.loc[c, c]:.1f}' for c in d_inc.columns)} vs challenger "
      f"{'/'.join(f'{d_ch.loc[c, c]:.1f}' for c in d_ch.columns)}.")
    A(f"- Sum of off-diagonal covariances (negative = error cancellation): incumbent "
      f"{float(d_inc.to_numpy().sum() - np.diag(d_inc).sum()):.2f} vs challenger "
      f"{float(d_ch.to_numpy().sum() - np.diag(d_ch).sum()):.2f}.")
    A("")
    A("## Calibration (train 2021-2023 only, incumbent protocol replicated verbatim)")
    A("")
    cw, ci = ctx["cal_w2"], ctx["cal_inc"]
    A(f"- Challenger: margin a={cw['w2_margin'][0]:.4f} b={cw['w2_margin'][1]:.4f}; "
      f"home a={cw['w2_home'][0]:.4f} b={cw['w2_home'][1]:.4f}; "
      f"away a={cw['w2_away'][0]:.4f} b={cw['w2_away'][1]:.4f}.")
    A(f"- Incumbent (reproduced): margin a={ci['str_margin'][0]:.4f} b={ci['str_margin'][1]:.4f}; "
      f"home a={ci['str_home'][0]:.4f} b={ci['str_home'][1]:.4f}; "
      f"away a={ci['str_away'][0]:.4f} b={ci['str_away'][1]:.4f}.")
    A("")
    A("## Things that smell wrong / design caveats (read before believing anything)")
    A("")
    for note in ctx["concerns"]:
        A(f"- {note}")
    A("")
    A("## Files")
    A("")
    for name, desc in ctx["files"]:
        A(f"- `{name}` — {desc}")
    A("")
    path.write_text("\n".join(S) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true",
                      help="scratch registry copy + scratch output dir (the only mode the build agent runs)")
    mode.add_argument("--real", action="store_true",
                      help="ledgered evaluation: real registry, outputs to experiments/w2_integration/ (orchestrator only)")
    ap.add_argument("--outdir", type=Path, default=None,
                    help="output dir override (smoke default: a fresh temp dir; real default: experiments/w2_integration)")
    args = ap.parse_args()

    t_start = datetime.now(timezone.utc)
    if args.smoke:
        outdir = args.outdir or Path(tempfile.mkdtemp(prefix="w2_integration_smoke_"))
        outdir.mkdir(parents=True, exist_ok=True)
        registry_path = outdir / "registry_scratch.jsonl"
        shutil.copy2(REGISTRY_PATH, registry_path)
        print(f"SMOKE mode: outputs -> {outdir}\n  scratch registry -> {registry_path}")
    else:
        outdir = args.outdir or OFFICIAL_OUTDIR
        outdir.mkdir(parents=True, exist_ok=True)
        registry_path = None
        print(f"REAL mode: outputs -> {outdir}; the gate verdict WILL be appended to {REGISTRY_PATH}")

    frozen = load_frozen_baselines()      # tamper check; raises on drift
    reg = eh.get_registration(EXPERIMENT_ID, registry_path=registry_path)
    print(f"registration OK: {EXPERIMENT_ID} (registered {reg['registered_at']}, "
          f"incumbent {reg['incumbent_id']}, regime {reg['regime']})")

    # ---- incumbent, reproduced through the chanreval pipeline itself --------
    rr = load_run_reval()
    D, alphas, games, train_ids, test_ids, cal_inc, n_total_test_games = rebuild_incumbent(rr)
    print(f"incumbent rebuilt: alphas {alphas}, {n_total_test_games} total test games")

    inc_pred = pd.read_csv(INCUMBENT_PRED_CSV)
    all_test_ids = set().union(*test_ids.values())
    et0 = games[games.GAME_ID.isin(all_test_ids) & games.eligible]
    repro = assert_incumbent_reproduced(
        et0, inc_pred[["GAME_ID", "margin_true", "str_margin_cal", "raw_margin_cal",
                       "str_home_cal", "str_away_cal", "str_total_cal"]])
    print(f"incumbent reproduction PASS: pooled {repro['pooled_mae_str_margin_cal']:.4f}, "
          f"per-game max|diff| {repro['max_abs_diff_str_margin_cal']:.2e}")

    # ---- zone-map matchup factors ------------------------------------------
    shots = mo.load_enriched()[SHOT_COLS]
    # shots_enriched stores GAME_ID as str; channel_base uses int64. Factors never
    # join the two on GAME_ID (teams by int team_id, cutoffs by date) — this cast
    # only makes the audit's own-game-shots presence check comparable.
    shots = shots.assign(GAME_ID=shots.GAME_ID.astype("int64"))
    k_table = mo.load_k_table()
    assert k_table is not None, "stored shrinkage_priors.csv missing"

    tg_ids = set(games.loc[games.GAME_ID.isin(train_ids) & games.eligible, "GAME_ID"])
    needed = games.loc[games.GAME_ID.isin(tg_ids | all_test_ids) & games.eligible,
                       ["GAME_ID", "GAME_DATE_h", "season_h", "TEAM_ID_h", "TEAM_ID_a",
                        "TEAM_ABBREVIATION_h", "TEAM_ABBREVIATION_a"]]
    print(f"computing factors for {len(needed)} games "
          f"({len(tg_ids)} train + {len(et0)} test) ...")
    fac, failures = compute_factors(needed, shots, k_table)
    n_complete = int(fac[["f_paint_h", "f_3pt_h", "f_paint_a", "f_3pt_a"]].notna().all(axis=1).sum())
    print(f"factors: {n_complete}/{len(needed)} games complete, {len(failures)} side-failures")

    games2 = add_challenger(games.merge(fac.drop(columns=["season", "game_date"]),
                                        on="GAME_ID", how="left", validate="one_to_one"))

    tg2 = games2[games2.GAME_ID.isin(tg_ids) & games2.eligible]
    et2 = games2[games2.GAME_ID.isin(all_test_ids) & games2.eligible].copy()
    assert len(tg2) == len(tg_ids) and len(et2) == N_UNIVERSE

    miss_test = et2[et2.w2_margin_uncal.isna()]
    if len(miss_test):
        (outdir / "factor_failures.json").write_text(
            json.dumps(jsonable(failures), indent=2), encoding="utf-8")
        raise SystemExit(
            f"{len(miss_test)} of the {N_UNIVERSE} preregistered test games have no factors "
            f"({sorted(miss_test.GAME_ID)[:10]} ...). The identical-universe comparison cannot "
            "run; see factor_failures.json. Refusing to shrink the universe silently.")
    miss_train = tg2[tg2.w2_margin_uncal.isna()]
    tg_fit = tg2.dropna(subset=["w2_margin_uncal", "w2_sum_h", "w2_sum_a"])

    # ---- challenger calibration (train years only, incumbent protocol) ------
    cal_w2 = fit_w2_calibration(rr, tg_fit)
    games2 = apply_w2_calibration(games2, cal_w2)
    tg2 = games2[games2.GAME_ID.isin(tg_ids) & games2.eligible]
    et2 = games2[games2.GAME_ID.isin(all_test_ids) & games2.eligible].copy()
    print(f"challenger calibration (n={cal_w2['n_train_games']}): "
          f"margin a={cal_w2['w2_margin'][0]:.3f} b={cal_w2['w2_margin'][1]:.3f}")

    # ---- audits BEFORE reading any result ----------------------------------
    sample = pick_audit_games(games2, games2.GAME_ID.isin(tg_ids) & games2.eligible,
                              games2.GAME_ID.isin(all_test_ids) & games2.eligible)
    audit_wf = audit_factor_walk_forward(sample, shots, k_table, fac)
    print(f"walk-forward factor audit: {audit_wf['n_games_audited']} games, "
          f"max|diff| {audit_wf['max_abs_diff']:.1e} -> "
          f"{'PASS' if audit_wf['passed'] else 'FAIL'}")
    if not audit_wf["passed"]:
        (outdir / "audits.json").write_text(json.dumps(jsonable(audit_wf), indent=2), encoding="utf-8")
        raise SystemExit("walk-forward factor audit FAILED — results are not evidence; stopping")

    clip_table = clip_activation(fac, tg_ids, all_test_ids)

    # ---- secondaries --------------------------------------------------------
    ch_table, cov = channel_secondaries(rr, et2)
    ref_cov = pd.DataFrame(json.loads(CHANREVAL_SUMMARY.read_text(encoding="utf-8"))
                           ["residual_covariance_structural"])
    cov_check = float((cov["incumbent"] - ref_cov.loc[cov["incumbent"].index,
                                                      cov["incumbent"].columns]).abs().max().max())
    totals = {"w2_total_mae": mae(et2.w2_total_cal - et2.total_true),
              "str_total_mae": mae(et2.str_total_cal - et2.total_true),
              "w2_home_mae": mae(et2.w2_home_cal - et2.team_pts_h),
              "str_home_mae": mae(et2.str_home_cal - et2.team_pts_h),
              "w2_away_mae": mae(et2.w2_away_cal - et2.team_pts_a),
              "str_away_mae": mae(et2.str_away_cal - et2.team_pts_a)}
    uncal = {"w2": mae(et2.w2_margin_uncal - et2.margin_true),
             "str": mae(et2.str_margin_uncal - et2.margin_true)}

    # ---- gate-4 joint check hook -------------------------------------------
    joint_tol = float(reg["thresholds"]["harm_ci_bound"])

    def joint_check():
        comps = {}
        for name, t_col, c_col, i_col in [
            ("home_score", "team_pts_h", "w2_home_cal", "str_home_cal"),
            ("away_score", "team_pts_a", "w2_away_cal", "str_away_cal"),
            ("margin", "margin_true", "w2_margin_cal", "str_margin_cal"),
            ("total", "total_true", "w2_total_cal", "str_total_cal"),
        ]:
            m_ch = mae(et2[c_col] - et2[t_col])
            m_inc = mae(et2[i_col] - et2[t_col])
            comps[name] = {"challenger_mae": round(m_ch, 4), "incumbent_mae": round(m_inc, 4),
                           "delta_improvement": round(m_inc - m_ch, 4)}
        ok = all(c["challenger_mae"] <= c["incumbent_mae"] + joint_tol for c in comps.values())
        return ok, {"tolerance": joint_tol, "components": comps}

    # ---- the registered comparison -----------------------------------------
    cov_frac = len(et2) / n_total_test_games
    ch_frame = et2[["GAME_ID", "GAME_DATE_h", "season_h", "margin_true", "w2_margin_cal",
                    "TEAM_ID_h"]].rename(columns={
        "GAME_ID": "game_id", "GAME_DATE_h": "game_date", "season_h": "season",
        "margin_true": "y_true", "w2_margin_cal": "y_pred", "TEAM_ID_h": "home_team"})
    inc_frame = inc_pred[["GAME_ID", "margin_true", "str_margin_cal"]].rename(columns={
        "GAME_ID": "game_id", "margin_true": "y_true", "str_margin_cal": "y_pred"})
    result = eh.compare_to_incumbent(
        ch_frame, inc_frame,
        experiment_id=EXPERIMENT_ID,
        registry_path=registry_path,
        joint_check=joint_check,
        coverage=(cov_frac, cov_frac),
    )
    print(f"VERDICT: {result.verdict} (promote={result.promote}); "
          f"pooled improvement {result.pooled_improvement:+.4f} "
          f"[90% CI {result.ci_low:+.4f}, {result.ci_high:+.4f}]; failed: {result.failed_gates}")

    # ---- outputs ------------------------------------------------------------
    et_out = et2.copy()          # map_n_shots / map_n_games already merged in
    for side in ("h", "a"):
        for ch in ("paint", "3pt"):
            raw = et_out[f"f_{ch}_raw_{side}"]
            et_out[f"clip_{ch}_{side}"] = np.where(raw < CLIP_LO, "lo",
                                                   np.where(raw > CLIP_HI, "hi", ""))
    pred_cols = (["GAME_ID", "GAME_DATE_h", "season_h", "season_type_h",
                  "TEAM_ABBREVIATION_h", "TEAM_ABBREVIATION_a", "TEAM_ID_h", "TEAM_ID_a",
                  "margin_true", "total_true", "team_pts_h", "team_pts_a",
                  "str_margin_uncal", "str_margin_cal", "str_home_cal", "str_away_cal", "str_total_cal",
                  "w2_margin_uncal", "w2_margin_cal", "w2_home_cal", "w2_away_cal", "w2_total_cal",
                  "naive_margin_pred"]
                 + [f"str_{c}_{s}" for s in ("h", "a") for c in rr.CHANNELS]
                 + [f"w2_paint_{s}" for s in ("h", "a")] + [f"w2_3pt_{s}" for s in ("h", "a")]
                 + [f"{rr.CH_ACTUAL[c]}_{s}" for s in ("h", "a") for c in rr.CHANNELS]
                 + [f"f_{ch}_raw_{s}" for s in ("h", "a") for ch in ("paint", "3pt")]
                 + [f"f_{ch}_{s}" for s in ("h", "a") for ch in ("paint", "3pt")]
                 + [f"clip_{ch}_{s}" for s in ("h", "a") for ch in ("paint", "3pt")]
                 + ["map_n_shots", "map_n_games"])
    et_out = et_out.rename(columns={"GAME_ID": "game_id", "GAME_DATE_h": "date",
                                    "season_h": "season", "season_type_h": "season_type"})
    pred_cols = [c.replace("GAME_ID", "game_id").replace("GAME_DATE_h", "date")
                 .replace("season_h", "season").replace("season_type_h", "season_type")
                 if c in ("GAME_ID", "GAME_DATE_h", "season_h", "season_type_h") else c
                 for c in pred_cols]
    et_out[pred_cols].to_csv(outdir / "game_level_predictions.csv", index=False)

    fac_out = needed.merge(fac, on="GAME_ID", how="left", validate="one_to_one")
    fac_out["subset"] = np.where(fac_out.GAME_ID.isin(tg_ids), "train", "test")
    fac_out.drop(columns=["season", "game_date"]).to_csv(outdir / "factors_all_games.csv", index=False)
    clip_table.to_csv(outdir / "clip_activation.csv", index=False)

    audits_payload = {
        "incumbent_reproduction": repro,
        "walk_forward_factor_audit": audit_wf,
        "factor_failures": failures,
        "n_train_games_missing_factors": int(len(miss_train)),
        "clip_activation": clip_table.to_dict(orient="records"),
    }
    (outdir / "audits.json").write_text(json.dumps(jsonable(audits_payload), indent=2),
                                        encoding="utf-8")
    (outdir / "calibration_params.json").write_text(json.dumps(jsonable({
        "alphas": alphas,
        "challenger": cal_w2, "incumbent_reproduced": cal_inc,
        "clip_bounds": [CLIP_LO, CLIP_HI],
        "k_table_used": k_table.to_dict(orient="records"),
    }), indent=2), encoding="utf-8")

    concerns = []
    hi_rate = clip_table.loc[(clip_table.channel == "3pt") & (clip_table.scope == "all"),
                             "clip_total_rate"]
    concerns.append(
        "Structural overlap / partial double-counting: the incumbent's paint and 3pt chains already "
        "contain an opponent-allowed ratio (opp_paint_allow/lg_paint; opp_fg3a_allow/lg_fg3a) and the "
        "team's own volume trend. The overlay factor multiplies in the SAME opponent-allowed and "
        "own-tendency information again from shot-location data (exp_share starts from off_share). "
        "The train-years calibration slope can shrink the global overconfidence this creates, but not "
        "the per-game double count.")
    if len(hi_rate) and float(hi_rate.iloc[0]) > 0.25:
        concerns.append(
            f"High clip activation: {float(hi_rate.iloc[0]):.0%} of 3pt factors hit the [0.85, 1.15] "
            "bounds (see table). At that rate the factor behaves closer to a three-level switch than a "
            "continuous multiplier — the preregistered bounds are doing a lot of work.")
    concerns.append(
        "The family expected-points ratio conflates matchup-tilted attempt share with conversion: a "
        "high-3pt-volume team gets a 3pt factor well above 1 even against a neutral defense (its "
        "own share tendency is in the numerator, and share renormalization pushes the paint factor "
        "down mechanically). This is the registered formula (\"shot-location tendency x location "
        "conversion\"), reported as such.")
    concerns.append(
        "Shrinkage-prior K table is estimated on the FULL 2021-2026 sample (variance-ratio "
        "hyperparameters, per matchup_overlay's documented contract and the registration's "
        "\"as promoted in the zone-map build\"). Rates inside maps_before are strictly pre-cutoff; "
        "the K constants themselves are not walk-forward.")
    concerns.append(
        "team_def conversion priors are near-total shrinkage (K 344-5000): opponent conversion-allowed "
        "is effectively neutralized, so the defensive side of the factor is carried almost entirely by "
        "allowed-location SHARE, not conversion.")
    if len(miss_train):
        concerns.append(
            f"{len(miss_train)} train games missing factors — calibration fit on "
            f"{cal_w2['n_train_games']} games instead of the incumbent's {cal_inc['n_train_games']} "
            "(protocol deviation).")
    if cov_check > 0.01:
        concerns.append(
            f"Reproduced incumbent residual covariance differs from the chanreval ledger by up to "
            f"{cov_check:.3f} (expected < 0.01) — investigate before trusting the covariance table.")

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "mode": "smoke" if args.smoke else "real",
        "generated_at": t_start.isoformat(timespec="seconds"),
        "run_number": result.run_number,
        "eval_time": result.eval_time,
        "registration": reg,
        "incumbent_reproduction": repro,
        "alphas": alphas,
        "clip_bounds": [CLIP_LO, CLIP_HI],
        "factor_coverage": {"n_needed": int(len(needed)), "n_train": int(len(tg_ids)),
                            "n_test": int(len(et2)), "n_complete": n_complete,
                            "n_failures": len(failures),
                            "n_train_games_missing_factors": int(len(miss_train))},
        "calibration_challenger": cal_w2,
        "calibration_incumbent": cal_inc,
        "audit_walk_forward": audit_wf,
        "clip_activation": clip_table.to_dict(orient="records"),
        "primary_result": result.to_dict(),
        "joint_check": joint_check()[1],
        "uncalibrated_margin_mae": uncal,
        "secondaries": {
            "channel_table": ch_table.to_dict(orient="records"),
            "totals_and_scores": totals,
            "residual_covariance_incumbent": cov["incumbent"].to_dict(),
            "residual_covariance_challenger": cov["challenger"].to_dict(),
            "incumbent_cov_vs_chanreval_ledger_max_abs_diff": cov_check,
        },
        "coverage": cov_frac,
        "n_total_test_games": n_total_test_games,
        "concerns": concerns,
        "n_frozen_baseline_rows_verified": int(len(frozen)),
    }
    (outdir / "run_summary.json").write_text(json.dumps(jsonable(summary), indent=2),
                                             encoding="utf-8")

    write_report(outdir / "REPORT.md", {
        "mode": "smoke" if args.smoke else "real",
        "generated_at": t_start.isoformat(timespec="seconds"),
        "registration": reg, "repro": repro,
        "factor_coverage": summary["factor_coverage"],
        "cal_w2": cal_w2, "cal_inc": cal_inc, "cal_inc_n": cal_inc["n_train_games"],
        "audit_wf": audit_wf, "clip_table": clip_table,
        "result": result.to_dict(), "joint_detail": joint_check()[1],
        "uncal": uncal, "ch_table": ch_table, "totals": totals,
        "cov": cov, "cov_check_max_diff": cov_check,
        "concerns": concerns,
        "files": [
            ("game_level_predictions.csv", "row-level: truth, incumbent + challenger margins/scores/totals, all per-channel predictions both sides, raw+clipped factors, clip flags, map sizes"),
            ("factors_all_games.csv", "factors for every train+test game used (calibration inputs included)"),
            ("clip_activation.csv", "clip-activation rates by channel x scope"),
            ("audits.json", "incumbent reproduction + walk-forward factor audit + factor failures"),
            ("calibration_params.json", "challenger + reproduced incumbent calibrations, alphas, clip bounds, K table"),
            ("run_summary.json", "everything above plus the full gate verdict"),
        ],
    })

    dt = (datetime.now(timezone.utc) - t_start).total_seconds()
    print(f"wrote REPORT.md, game_level_predictions.csv, factors_all_games.csv, "
          f"clip_activation.csv, audits.json, calibration_params.json, run_summary.json -> {outdir}")
    print(f"done in {dt:.1f}s")


if __name__ == "__main__":
    main()
