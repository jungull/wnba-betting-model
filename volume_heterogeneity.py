"""volume_heterogeneity.py — the CORRECTED heterogeneity screen
(experiments/registry.jsonl, experiment_id=player_volume_heterogeneity_v1,
registered 2026-07-31T15:35:33Z).

WHY THIS SCREEN EXISTS
  player_feature_interactions_v1 (473 tests) and player_vs_archetype_v1
  (25 tests) both returned ZERO level-2 survivors. An orchestrator power
  diagnostic (experiments/power_diagnostic.py, power_diagnostic2.py) proved
  those nulls VACUOUS rather than informative:
    * points per 36 is the noisiest available target — only 29.8% of its
      variance is stable between-player signal; ~70% is make/miss luck;
    * the smallest individual split difference detectable in pts/36 for a
      median player is 3.89 per 36 — about TEN TIMES the only condition
      effect ever measured at league level (home advantage, +0.38/36);
    * some tested conditions barely occur (back-to-backs ~2.6% of rows), so
      their "nulls" were arithmetic, not evidence.
  The registered correction: keep the harness, change the TARGET to VOLUME
  quantities (minutes 52.5% signal, fg3a36 55.4%, fga36 40.8%, fta36 22.6%),
  gate rare conditions out UP FRONT, and report a minimum detectable effect
  beside every observed effect so no null is ever again reported without
  stating what it could have seen.

WHAT THIS SCRIPT IS
  A WRAPPER. It reuses the committed machinery and modifies nothing:
    feature_lab.py        universe, ridge, BH, alpha grid, MAE
    interactions_lab.py   l2_test, block-permutation banks, eb_level3,
                          finalize/report helpers  (imported, never edited)
    features/*            Ctx, candidate catalog, moderators, archetypes
  Its own contributions are exactly the four registered corrections:
  volume targets + their tuned baselines, the condition-frequency gate,
  the power (MDE) columns, and the chance-expectation comparison at level 3.

PROTOCOL (as registered)
  * Window 2021-2024 ONLY. QUARANTINE ABSOLUTE: 2025/2026 never loaded; every
    assembled matrix asserts max(game_date) < 2025-01-01; audit written to
    experiments/volume_heterogeneity/quarantine_audit.json.
  * TARGETS: minutes played, fga/36, fg3a/36, fta/36 (NOT points).
    Baseline per target = shifted per-player EWMA of that target, alpha tuned
    on the 3 inner walk-forward folds of 2021-2023 (frozen before 2024).
  * BATTERY: the 14 committed pooled-screen survivors (on their surviving
    channels, frozen alphas) + the registered resurrection shortlist
    (#6, #7, #80, #9, #1, #16, #94, #14, #17), each crossed with the closed
    18-condition moderator set = the 11 registered player traits
    (features/moderators.py) + the 5 archetype axes + 2 composites
    (features/archetypes.py), on all four targets.
  * CONDITION-FREQUENCY GATE (mandatory, before testing): any condition
    occurring on fewer than 8% of eligible rows is EXCLUDED UP FRONT and
    listed in excluded_for_rarity.csv with its observed frequency. Rarity
    exclusions are NOT reported as nulls.
  * POWER REPORTING (mandatory): every test row carries its minimum
    detectable effect beside its observed effect.
        MDE = 2.8 * sd_within_player * sqrt(2 / (n_eligible_per_player / 2))
    for the median eligible player of that test (registered formula), plus a
    pooled counterpart at the test's total eligible n. Nulls whose MDE far
    exceeds a plausible effect are labelled `underpowered`, distinct from
    `null_with_power`.
  * LEVEL 3: EB per-player slopes with within-player time-split replication
    (interactions_lab.eb_level3, unmodified), reported ALONGSIDE the
    chance-expectation count under the naming gates.
  * NULL: 200 within-season block permutations of the moderator/archetype
    ASSIGNMENT (player blocks for player traits, team blocks for archetype
    axes); BH at 10% across this screen's battery; sign-consistency across
    the inner folds additionally required for survival.

THIS SCRIPT RECORDS NOTHING ON THE LEDGER. It never imports or calls
registry.register / evaluate / record_evaluation / render_leaderboards, never
writes experiments/registry.jsonl, and never runs git. It writes only inside
experiments/volume_heterogeneity/.

Run:  python volume_heterogeneity.py
      python volume_heterogeneity.py --perms 20 --limit 12 --skip-l3   # dev
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import feature_lab as FL            # noqa: E402  committed harness — reused
import interactions_lab as IL       # noqa: E402  committed heterogeneity harness — reused
from features import ALL_CANDIDATES, Ctx  # noqa: E402
from features.common import (QUARANTINE_CUTOFF, TRAIN_SEASONS, VAL_SEASON,  # noqa: E402
                             assert_quarantine, sew, sratio_ew)
from features import moderators as MODS    # noqa: E402
from features import archetypes as ARCH    # noqa: E402

OUT = REPO / "experiments" / "volume_heterogeneity"
SCREEN_DIR = REPO / "experiments" / "feature_screen"

FDR_Q = 0.10
N_PERM_DEFAULT = 200
SEED_BASE = 20260731
MIN_MINUTES_ROBUST = 15.0

# ---- registered corrections: pinned constants -----------------------------
TARGETS = ["minutes", "fga36", "fg3a36", "fta36"]
TARGET_NUMER = {"fga36": "fga", "fg3a36": "fg3a", "fta36": "fta"}
TARGET_LABEL = {"minutes": "minutes played", "fga36": "shot attempts / 36",
                "fg3a36": "3pt attempts / 36", "fta36": "FT attempts / 36"}

RARITY_GATE = 0.08          # registered: conditions under 8% are excluded up front
MDE_Z = 2.8                 # diagnostic's constant (80% power, alpha .05, two-sided)
MDE_MIN_PLAYER_ROWS = 20    # "eligible player" == level-3 naming gate (n >= 20)
UNDERPOWER_RATIO = 3.0      # MDE > 3 x plausible effect  ==  "MDE >> plausible effect"
PLAUSIBLE_FLOOR_FRAC = 0.05  # a-priori practical-significance floor: 5% of target mean

# chance expectation for the level-3 naming gates (see REPORT.md derivation):
P_POSTZ = 0.0455            # P(|z| >= 2) under the null
REPL_LOW, REPL_HIGH = 0.25, 0.50   # P(sign replication) bracket under the null

# resurrection features that are channel-specific: the channel is fixed by the
# COMMITTED pooled screen (lowest p, then most negative delta) — a rule derived
# from prior artifacts, fixed before this screen's results exist.
RESURRECTION_NUMS = [6, 7, 80, 9, 1, 16, 94, 14, 17]


# ---------------------------------------------------------------------------
# targets and their baselines
# ---------------------------------------------------------------------------

def build_targets(ctx) -> dict[str, pd.Series]:
    """The four registered VOLUME targets on the played frame."""
    P = ctx.P
    m = P["minutes"].astype(float)
    out = {"minutes": m}
    for tgt, num in TARGET_NUMER.items():
        out[tgt] = P[num].astype(float) / m * 36.0
    return out


def tune_volume_baselines(ctx, U, folds, targets):
    """Per-target baseline = shifted per-player EWMA of that target, alpha
    tuned on the inner 2021-2023 folds ONLY (frozen before 2024 is touched).

    The registered phrase admits two harness-canonical encodings for a per-36
    rate target: (a) `ewma_target` — the shifted EWMA of the rate itself
    (equal weight per game); (b) `ratio_ewma` — the shifted ratio of EWMAs of
    (numerator, minutes), i.e. the minutes-weighted rate trend, which is the
    form the committed pooled screen used for its per-36 channel targets. Both
    are swept on the inner folds and the STRONGER is kept: choosing the
    harder-to-beat baseline is the conservative direction (it can only make
    features look worse, never better). `minutes` is a level, not a rate, so
    only form (a) exists for it.
    """
    P = ctx.P
    curves, chosen, base_series = [], {}, {}
    for tgt in TARGETS:
        forms = ["ewma_target"] + (["ratio_ewma"] if tgt in TARGET_NUMER else [])
        best = (None, None, np.inf)
        for form in forms:
            for a in FL.ALPHA_GRID:
                base = _baseline_series(P, targets, tgt, form, a)
                bu = base.loc[U.index]
                losses = []
                for f in folds:
                    pred = bu.loc[f.val_idx].to_numpy(float)
                    yv = U.loc[f.val_idx, f"y_{tgt}"].to_numpy(float)
                    ok = ~np.isnan(pred)
                    losses.append(FL.mae(yv[ok], pred[ok]))
                loss = float(np.mean(losses))
                curves.append({"target": tgt, "form": form, "alpha": a,
                               "inner_mae": round(loss, 6)})
                if loss < best[2]:
                    best = (form, a, loss)
        chosen[tgt] = {"form": best[0], "alpha": best[1],
                       "inner_mae": round(best[2], 6)}
        base_series[tgt] = _baseline_series(P, targets, tgt, best[0], best[1])
    return chosen, pd.DataFrame(curves), base_series


def _baseline_series(P, targets, tgt, form, alpha):
    if form == "ewma_target":
        return sew(P, targets[tgt], alpha)
    return sratio_ew(P, P[TARGET_NUMER[tgt]].astype(float),
                     P["minutes"].astype(float), alpha) * 36.0


# ---------------------------------------------------------------------------
# the registered battery (feature columns)
# ---------------------------------------------------------------------------

def _akey(alpha):
    if alpha is None:
        return None
    try:
        if isinstance(alpha, float) and np.isnan(alpha):
            return None
    except TypeError:
        return None
    return round(float(alpha), 3)


def build_feature_columns(ctx, mods_frame, rot_height_rows):
    """One column per registered battery entry.

    (a) the 14 committed pooled-screen survivors, each on its SURVIVING
        channel at its FROZEN alpha (experiments/feature_screen/
        survivor_summary.csv — nothing re-tuned here);
    (b) the registered resurrection shortlist. For the channel-specific ones
        the channel is fixed by the committed pooled screen's own ranking
        (lowest p, then most negative delta) — the target is no longer a
        points channel, so each resurrection feature contributes exactly one
        column rather than four.

    Columns with identical values are collapsed (several catalog builders
    return the same series for every channel); the collapse is recorded so the
    battery's multiplicity is honest rather than inflated.
    """
    cand_by_num = {c.num: c for c in ALL_CANDIDATES}
    cache: dict = {}

    def get_series(num, ch, alpha):
        key = (num, _akey(alpha))
        if key not in cache:
            cache[key] = cand_by_num[num].build(ctx, key[1])
        return FL.series_for_channel(cache[key], ch)

    surv = pd.read_csv(SCREEN_DIR / "survivor_summary.csv")
    scr = pd.read_csv(SCREEN_DIR / "screen_results.csv")

    entries = []
    for _, r in surv.iterrows():
        entries.append({"num": int(r["catalog_number"]), "feature": r["name"],
                        "src_channel": r["channel"], "alpha": _akey(r["alpha_chosen"]),
                        "role": "survivor",
                        "series": get_series(int(r["catalog_number"]), r["channel"],
                                             r["alpha_chosen"])})

    # committed-screen best channel per resurrection catalog number
    def best_channel(num):
        sub = scr[scr["catalog_number"] == num]
        if not len(sub):
            return None, None
        sub = sub.sort_values(["p_value", "delta_mae"])
        return sub["channel"].iloc[0], _akey(sub["alpha_chosen"].iloc[0])

    P = ctx.P
    for num in RESURRECTION_NUMS:
        if num == 7:
            s = (P["days_rest_player"] <= 1).astype(float).fillna(0.0)
            entries.append({"num": 7, "feature": "b2b_flag", "src_channel": "-",
                            "alpha": None, "role": "resurrection", "series": s})
        elif num == 80:
            entries.append({"num": 80, "feature": "min7d_load", "src_channel": "-",
                            "alpha": MODS.MOD_ALPHA, "role": "resurrection",
                            "series": mods_frame["min7d_load"]})
        elif num == 9:
            entries.append({"num": 9, "feature": "travel_distance", "src_channel": "-",
                            "alpha": None, "role": "resurrection",
                            "series": IL.travel_distance(ctx)})
        elif num == 17:
            entries.append({"num": 17, "feature": "opp_rotation_height",
                            "src_channel": "-", "alpha": ARCH.AX_ALPHA,
                            "role": "resurrection", "series": rot_height_rows})
        else:
            ch, alpha = best_channel(num)
            entries.append({"num": num, "feature": cand_by_num[num].name,
                            "src_channel": ch, "alpha": alpha,
                            "role": "resurrection",
                            "series": get_series(num, ch, alpha)})

    # ---- collapse identical columns -------------------------------------
    kept, seen, collapsed = [], {}, []
    for e in entries:
        v = e["series"].to_numpy(float)
        sig = hash(np.nan_to_num(np.round(v, 9), nan=-9.87654321e17).tobytes())
        if sig in seen:
            owner = seen[sig]
            owner["role"] = ("survivor+resurrection"
                             if owner["role"] != e["role"] else owner["role"])
            collapsed.append({"dropped": f"#{e['num']} {e['feature']} "
                                         f"[{e['src_channel']}]",
                              "identical_to": f"#{owner['num']} {owner['feature']} "
                                              f"[{owner['src_channel']}]"})
            continue
        seen[sig] = e
        kept.append(e)
    return kept, pd.DataFrame(collapsed)


# ---------------------------------------------------------------------------
# the condition-frequency gate (registered correction 3)
# ---------------------------------------------------------------------------

def occurrence(v: np.ndarray):
    """Occurrence rate of a condition among eligible rows, with its kind.

    * binary (<= 2 distinct non-NaN values): share of rows at the positive
      (higher) level — this is what catches back-to-backs;
    * sparse-continuous (a single modal value on > 50% of rows, e.g. a
      shrunk deviation that is exactly 0 whenever the condition never
      occurred): share of rows that are non-NaN and off the modal value;
    * continuous: 1.0 — the condition varies on essentially every row, so
      there is no rarity question to ask.
    A column with a single distinct value is degenerate and excluded.
    """
    n = len(v)
    ok = ~np.isnan(v)
    x = v[ok]
    if n == 0 or len(x) == 0:
        return 0.0, "all_missing"
    uniq = np.unique(x)
    if len(uniq) == 1:
        return 0.0, "constant"
    if len(uniq) == 2:
        return float(np.mean(v == uniq.max())), "binary"
    vals, counts = np.unique(x, return_counts=True)
    modal = vals[int(np.argmax(counts))]
    if counts.max() / n > 0.5:
        return float(np.mean(ok & (v != modal))), "sparse_continuous"
    return 1.0, "continuous"


# ---------------------------------------------------------------------------
# power reporting (registered correction 4)
# ---------------------------------------------------------------------------

def mde_stats(y: np.ndarray, players: np.ndarray, eligible: np.ndarray):
    """Minimum detectable effect for a test restricted to `eligible` rows.

    Registered formula, for the MEDIAN ELIGIBLE PLAYER of the test:
        MDE = 2.8 * sd_within_player * sqrt(2 / (n_eligible_per_player / 2))
    'eligible player' == a player with >= 20 eligible rows (the level-3
    naming gate, i.e. exactly the players an individual effect could ever be
    named for). The pooled counterpart substitutes the test's TOTAL eligible
    n for the per-player n: it is what the LEVEL-2 pooled ridge can resolve,
    since level 2 aggregates the split across all players at once.
    """
    idx = np.flatnonzero(eligible)
    out = {"n_eligible": int(len(idx)), "n_players_eligible": 0,
           "median_player_rows": np.nan, "sd_within_player": np.nan,
           "mde_player": np.nan, "mde_pooled": np.nan}
    if len(idx) < 10:
        return out
    d = pd.DataFrame({"p": players[idx], "y": y[idx]})
    g = d.groupby("p")["y"]
    n_i, sd_i = g.size(), g.std(ddof=1)
    keep = (n_i >= MDE_MIN_PLAYER_ROWS) & sd_i.notna()
    if not bool(keep.any()):
        keep = sd_i.notna()
    n_i, sd_i = n_i[keep], sd_i[keep]
    if not len(n_i):
        return out
    med_n, med_sd = float(n_i.median()), float(sd_i.median())
    out.update({
        "n_players_eligible": int(len(n_i)),
        "median_player_rows": round(med_n, 1),
        "sd_within_player": round(med_sd, 4),
        "mde_player": round(MDE_Z * med_sd * np.sqrt(2.0 / (med_n / 2.0)), 4),
        "mde_pooled": round(MDE_Z * med_sd * np.sqrt(2.0 / (len(idx) / 2.0)), 5),
    })
    return out


def plausible_effects(ctx, U, targets_U):
    """A measured, per-target anchor for 'a plausible condition effect'.

    The diagnostic's anchor for points was the league home lift (+0.38/36) —
    the only condition effect the project has ever measured. Same construction
    here, per target: the larger of the league home-vs-away mean difference
    and the league rested (>= 3 days) vs short-rest mean difference, floored
    at 5% of the target's mean so a target whose venue split happens to be
    ~0 does not get an absurdly small anchor. Both components are reported.
    """
    P = ctx.P.loc[U.index]
    home = P["is_home"].to_numpy(float) == 1.0
    rest = P["days_rest_player"].to_numpy(float)
    rested = rest >= 3.0
    short = (rest <= 2.0) & ~np.isnan(rest)
    out = {}
    for tgt in TARGETS:
        y = targets_U[tgt]
        d_home = abs(float(np.nanmean(y[home]) - np.nanmean(y[~home])))
        d_rest = abs(float(np.nanmean(y[rested]) - np.nanmean(y[short])))
        floor = PLAUSIBLE_FLOOR_FRAC * float(np.nanmean(y))
        out[tgt] = {"home_split": round(d_home, 4), "rest_split": round(d_rest, 4),
                    "floor_5pct_of_mean": round(floor, 4),
                    "plausible_effect": round(max(d_home, d_rest, floor), 4)}
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="corrected volume heterogeneity screen")
    ap.add_argument("--perms", type=int, default=N_PERM_DEFAULT)
    ap.add_argument("--limit", type=int, default=None, help="DEV: first N tests")
    ap.add_argument("--targets", type=str, default=None, help="DEV: comma list")
    ap.add_argument("--skip-l3", action="store_true", help="DEV only")
    args = ap.parse_args(argv)
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    targets_run = ([t for t in args.targets.split(",")] if args.targets else TARGETS)

    # ---- context, universe, committed point-channel baselines ------------
    print("[load] building context (quarantine-filtered at source) ...")
    ctx = Ctx()
    U, outer, folds = FL.build_universe(ctx)
    print(f"[universe] {len(U)} rows; train={len(outer.train_idx)} "
          f"val2024={len(outer.test_idx)}")
    # the committed pooled-screen baselines are an INPUT to several candidate
    # builders (fam_a/b/e/j read ctx.baselines), so they must be re-derived
    # exactly as the prior screens did or the feature columns would differ.
    print("[baseline] re-deriving the committed per-channel point baselines "
          "(inputs to the feature builders) ...")
    pt_alphas, _ = FL.tune_baselines(ctx, U, outer, folds)
    print(f"[baseline] committed point-channel alphas: {pt_alphas}")

    # ---- the four registered VOLUME targets ------------------------------
    tgt_P = build_targets(ctx)
    for tgt in TARGETS:
        U[f"y_{tgt}"] = tgt_P[tgt].loc[U.index]
    assert_quarantine(U["game_date"], f"volume_target_universe(n={len(U)})", ctx.audit)
    bad = {t: int(U[f"y_{t}"].isna().sum()) for t in TARGETS}
    if any(bad.values()):
        raise RuntimeError(f"NaN volume targets on the universe: {bad}")

    print("[baseline] tuning volume-target baselines on the inner folds ...")
    vol_chosen, vol_curves, vol_base = tune_volume_baselines(ctx, U, folds, tgt_P)
    for tgt in TARGETS:
        c = vol_chosen[tgt]
        print(f"  {tgt:8s} form={c['form']:12s} alpha={c['alpha']} "
              f"inner_mae={c['inner_mae']}")
    vol_curves.to_csv(OUT / "baseline_alpha_curves.csv", index=False)

    tr = U.index.get_indexer(outer.train_idx)
    va = U.index.get_indexer(outer.test_idx)
    fold_pos = [(U.index.get_indexer(f.train_idx), U.index.get_indexer(f.val_idx))
                for f in folds]
    upos = U.index.to_numpy()

    arr = {}
    for tgt in TARGETS:
        b = vol_base[tgt].loc[U.index].to_numpy(float)
        if np.isnan(b).any():
            raise RuntimeError(f"NaN baseline on target {tgt}")
        arr[tgt] = {"y": U[f"y_{tgt}"].to_numpy(float), "b": b}

    U15 = U[U["minutes"] >= MIN_MINUTES_ROBUST].copy()
    assert_quarantine(U15["game_date"], f"volume_design_min15(n={len(U15)})", ctx.audit)
    u15pos = U15.index.to_numpy()
    arr15 = {t: {"y": U15[f"y_{t}"].to_numpy(float),
                 "b": vol_base[t].loc[U15.index].to_numpy(float)} for t in TARGETS}
    tr15 = np.flatnonzero(np.isin(U15["season"].to_numpy(int), TRAIN_SEASONS))
    va15 = np.flatnonzero(U15["season"].to_numpy(int) == VAL_SEASON)

    # ---- the closed 18-condition moderator set ---------------------------
    print("[traits] 11 player moderators + 5 archetype axes + 2 composites ...")
    bios = MODS.load_bios(ctx.audit)
    mods_P = MODS.build_moderators(ctx, bios)
    heights = MODS.heights_by_player(bios)
    TG = ARCH.build_archetype_table(ctx, heights, ctx.audit)
    ptr_P = ARCH.opponent_pointer(ctx, TG)
    rot_height_rows = ARCH.axis_on_rows(ctx, TG, ptr_P, "rot_height")

    ARCH_CONDS = list(ARCH.AXES) + list(ARCH.COMPOSITES)
    cond_U, cond_kind = {}, {}
    for m in MODS.MODERATORS:
        cond_U[m] = mods_P[m].to_numpy(float)[upos]
        cond_kind[m] = "player_trait"
    for a in ARCH_CONDS:
        cond_U[a] = ARCH.axis_on_rows(ctx, TG, ptr_P, a).to_numpy(float)[upos]
        cond_kind[a] = "archetype"
    mods_U15 = {m: mods_P[m].to_numpy(float)[u15pos] for m in MODS.MODERATORS}
    ptr_U, ptr_U15 = ptr_P[upos], ptr_P[u15pos]

    players_U = U["player_id"].to_numpy(np.int64)
    dates_U = U["game_date"].to_numpy()
    seasons_U = U["season"].to_numpy(int)
    names = dict(zip(ctx.P["player_id"].to_numpy(), ctx.P["player_name"]))
    targets_U = {t: arr[t]["y"] for t in TARGETS}

    # ---- battery columns --------------------------------------------------
    print("[battery] building the registered feature columns ...")
    feats, collapsed = build_feature_columns(ctx, mods_P, rot_height_rows)
    feat_U = {}
    for e in feats:
        e["vals"] = e["series"].to_numpy(float)[upos]
        feat_U[(e["num"], e["src_channel"])] = e["vals"]
    print(f"[battery] {len(feats)} distinct feature columns "
          f"({len(collapsed)} identical columns collapsed)")

    # ---- CONDITION-FREQUENCY GATE (before any test is run) ---------------
    freq_rows, excluded = [], []
    for e in feats:
        rate, kind = occurrence(e["vals"])
        row = {"role": "feature", "name": f"#{e['num']} {e['feature']}",
               "detail": f"channel={e['src_channel']} alpha={e['alpha']}",
               "kind": kind, "occurrence_rate": round(rate, 5),
               "n_eligible_rows": len(e["vals"]),
               "n_occurrences": int(round(rate * len(e["vals"])))}
        freq_rows.append(row)
        if kind == "constant" or rate < RARITY_GATE:
            e["excluded"] = True
            excluded.append({**row, "gate": RARITY_GATE,
                             "reason": ("degenerate constant column" if kind == "constant"
                                        else f"occurs on {rate:.2%} of eligible rows "
                                             f"(< {RARITY_GATE:.0%} gate)")})
        else:
            e["excluded"] = False
    conds_kept = []
    for c, v in cond_U.items():
        rate, kind = occurrence(v)
        row = {"role": "moderator", "name": c, "detail": cond_kind[c], "kind": kind,
               "occurrence_rate": round(rate, 5), "n_eligible_rows": len(v),
               "n_occurrences": int(round(rate * len(v)))}
        freq_rows.append(row)
        if kind == "constant" or rate < RARITY_GATE:
            excluded.append({**row, "gate": RARITY_GATE,
                             "reason": ("degenerate constant column" if kind == "constant"
                                        else f"occurs on {rate:.2%} of eligible rows "
                                             f"(< {RARITY_GATE:.0%} gate)")})
        else:
            conds_kept.append(c)
    feats_kept = [e for e in feats if not e["excluded"]]
    n_removed = (len(feats) * len(cond_U) - len(feats_kept) * len(conds_kept)) * len(targets_run)
    for x in excluded:
        x["tests_removed_from_battery"] = None
    exc_df = pd.DataFrame(excluded)
    if len(exc_df):
        exc_df["tests_removed_from_battery"] = n_removed
    exc_df.to_csv(OUT / "excluded_for_rarity.csv", index=False)
    pd.DataFrame(freq_rows).sort_values("occurrence_rate").to_csv(
        OUT / "condition_frequencies.csv", index=False)
    print(f"[gate] {len(feats_kept)}/{len(feats)} features and "
          f"{len(conds_kept)}/{len(cond_U)} conditions pass the {RARITY_GATE:.0%} "
          f"frequency gate; {len(excluded)} excluded up front "
          f"({n_removed} tests never run, never reported as nulls)")
    for x in excluded:
        print(f"   EXCLUDED [{x['role']}] {x['name']}: {x['reason']}")

    # ---- power anchors ----------------------------------------------------
    anchors = plausible_effects(ctx, U, targets_U)
    for t in TARGETS:
        print(f"[power] {t:8s} plausible effect anchor = "
              f"{anchors[t]['plausible_effect']} (home {anchors[t]['home_split']}, "
              f"rest {anchors[t]['rest_split']}, 5% floor "
              f"{anchors[t]['floor_5pct_of_mean']})")

    # ---- permutation banks (registered nulls) ----------------------------
    print("[banks] within-season block-permutation banks ...")
    bank_rows = IL.build_block_bank(seasons_U, players_U, args.perms, SEED_BASE + 11)
    bank_rows15 = IL.build_block_bank(U15["season"].to_numpy(int),
                                      U15["player_id"].to_numpy(np.int64),
                                      args.perms, SEED_BASE + 12)
    bank_tg = IL.build_block_bank(TG["season"].to_numpy(int),
                                  TG["team_id"].to_numpy(np.int64),
                                  args.perms, SEED_BASE + 13)

    # ---- the battery ------------------------------------------------------
    tests = [{"e": e, "cond": c, "target": t}
             for t in targets_run for e in feats_kept for c in conds_kept]
    if args.limit:
        tests = tests[: args.limit]
    print(f"[screen] {len(tests)} tests = {len(feats_kept)} features x "
          f"{len(conds_kept)} conditions x {len(targets_run)} targets, "
          f"{args.perms} permutations each")

    mde_cache: dict = {}
    rows, t_run = [], time.time()
    for i, t in enumerate(tests, 1):
        e, c, tgt = t["e"], t["cond"], t["target"]
        f_all, m_all, A = e["vals"], cond_U[c], arr[tgt]
        if cond_kind[c] == "player_trait":
            pfn = IL.row_perm_fn(m_all, bank_rows)
        else:
            pfn = IL.tg_perm_fn(TG[c].to_numpy(float), bank_tg, ptr_U)
        try:
            r = IL.l2_test(A["b"], A["y"], f_all, m_all, tr, va, fold_pos,
                           args.perms, "m", pfn)
        except Exception as ex:      # one test must never sink the battery
            r = {"degenerate": True, "p_value": 1.0, "delta_mae": np.nan,
                 "improvement": np.nan, "beta_interaction": np.nan,
                 "mae_noint_2024": np.nan, "mae_int_2024": np.nan,
                 "fold_deltas": "", "fold_signs": "", "corr_fm": np.nan,
                 "nan_share_feature": np.nan, "nan_share_moderator": np.nan,
                 "null_q50": np.nan, "null_q95": np.nan,
                 "note": f"TEST FAILED: {type(ex).__name__}: {ex}"}
        key = (e["num"], e["src_channel"], c, tgt)
        if key not in mde_cache:
            elig = ~np.isnan(f_all) & ~np.isnan(m_all)
            mde_cache[key] = mde_stats(A["y"], players_U, elig)
        pw = mde_cache[key]
        an = anchors[tgt]
        beta = r.get("beta_interaction")
        rows.append({
            "protocol": "player_volume_heterogeneity_v1",
            "target": tgt, "target_label": TARGET_LABEL[tgt],
            "catalog_number": e["num"], "feature": e["feature"],
            "feature_channel": e["src_channel"], "feature_alpha": e["alpha"],
            "battery": e["role"], "condition": c, "condition_kind": cond_kind[c],
            "registered_pairing": (e["num"], c) in IL.REGISTERED_PAIRINGS,
            "n_train": len(tr), "n_val": len(va),
            "observed_effect": (abs(float(beta)) if beta is not None
                                and not pd.isna(beta) else np.nan),
            **pw,
            "plausible_effect": an["plausible_effect"],
            "mde_ratio_player": (round(pw["mde_player"] / an["plausible_effect"], 2)
                                 if not np.isnan(pw["mde_player"]) else np.nan),
            "mde_ratio_pooled": (round(pw["mde_pooled"] / an["plausible_effect"], 3)
                                 if not np.isnan(pw["mde_pooled"]) else np.nan),
            **r})
        if i % 50 == 0 or i == len(tests):
            el = time.time() - t_run
            print(f"  [{i}/{len(tests)}] {el:.0f}s "
                  f"(eta {el / i * (len(tests) - i):.0f}s)")

    res = pd.DataFrame(rows)

    # ---- BH + sign consistency (registered survival rule) ----------------
    res["q_value"] = FL.bh_adjust(res["p_value"].to_numpy(float))
    res["bh_pass"] = res["q_value"] <= FDR_Q
    res["sign_consistent"] = [
        bool(fs != "" and set(str(fs)) == {"-"} and (d < 0))
        for fs, d in zip(res["fold_signs"], res["delta_mae"].fillna(0.0))]
    res["survives"] = res["bh_pass"] & res["sign_consistent"]

    def _label(r, which):
        if r["survives"]:
            return "survivor"
        ratio = r["mde_ratio_player"] if which == "player" else r["mde_ratio_pooled"]
        if pd.isna(ratio):
            return "indeterminate"
        return "underpowered" if ratio > UNDERPOWER_RATIO else "null_with_power"

    res["power_label"] = [_label(r, "player") for _, r in res.iterrows()]
    res["power_label_pooled"] = [_label(r, "pooled") for _, r in res.iterrows()]
    res = res.sort_values(["survives", "q_value", "delta_mae"],
                          ascending=[False, True, True]).reset_index(drop=True)
    res.to_csv(OUT / "screen_results.csv", index=False)

    # secondary (clearly non-binding) per-target BH view
    per_t = {}
    for tgt in targets_run:
        sub = res[res["target"] == tgt]
        q = FL.bh_adjust(sub["p_value"].to_numpy(float))
        per_t[tgt] = {"n": len(sub), "bh_pass_within_target": int((q <= FDR_Q).sum()),
                      "min_p": float(sub["p_value"].min()),
                      "n_at_p_floor": int((sub["p_value"] <= 1.0 / (args.perms + 1) + 1e-9).sum()),
                      "n_p05": int((sub["p_value"] <= 0.05).sum())}

    surv = res[res["survives"]].copy()

    # ---- min15 robustness for survivors ----------------------------------
    rob_rows = []
    for _, r in surv.iterrows():
        f15 = None
        for e in feats_kept:
            if e["num"] == r["catalog_number"] and e["src_channel"] == r["feature_channel"]:
                f15 = e["series"].to_numpy(float)[u15pos]
                break
        if f15 is None:
            continue
        c = r["condition"]
        if cond_kind[c] == "player_trait":
            m15 = mods_U15[c]
            pfn = IL.row_perm_fn(m15, bank_rows15)
        else:
            m15 = ARCH.axis_on_rows(ctx, TG, ptr_P, c).to_numpy(float)[u15pos]
            pfn = IL.tg_perm_fn(TG[c].to_numpy(float), bank_tg, ptr_U15)
        A15 = arr15[r["target"]]
        rr = IL.l2_test(A15["b"], A15["y"], f15, m15, tr15, va15, [],
                        args.perms, "m", pfn)
        rob_rows.append({"target": r["target"], "catalog_number": r["catalog_number"],
                         "feature": r["feature"], "feature_channel": r["feature_channel"],
                         "condition": c, "delta_mae_min15": rr.get("delta_mae"),
                         "p_value_min15": rr.get("p_value"),
                         "agrees_with_primary": bool(
                             (rr.get("delta_mae") or 0) < 0) == bool(r["delta_mae"] < 0)})
    rob = pd.DataFrame(rob_rows)
    if len(surv) and len(rob):
        surv = surv.merge(rob, on=["target", "catalog_number", "feature",
                                   "feature_channel", "condition"], how="left")
    surv.to_csv(OUT / "survivor_summary.csv", index=False)

    # ---- LEVEL 3 ---------------------------------------------------------
    named_rows, l3_meta = [], {}
    if not args.skip_l3:
        l3_jobs = []
        for _, r in surv.iterrows():
            l3_jobs.append({
                "pattern": f"#{r['catalog_number']} {r['feature']} x {r['condition']}",
                "target": r["target"], "kind": "level2_survivor",
                "f": feat_U[(r["catalog_number"], r["feature_channel"])],
                "mods": [cond_U[r["condition"]]]})
        traits4 = [cond_U[t] for t in MODS.OWN_TRAITS]
        for comp in ARCH.COMPOSITES:
            for tgt in targets_run:
                l3_jobs.append({"pattern": comp, "target": tgt,
                                "kind": "registered_composite",
                                "f": cond_U[comp], "mods": traits4})
        print(f"[L3] EB per-player slope pass on {len(l3_jobs)} patterns ...")
        for j in l3_jobs:
            A = arr[j["target"]]
            rows_i, meta = IL.eb_level3(A["b"], A["y"], j["f"], j["mods"], tr,
                                        fold_pos, dates_U, players_U, names)
            n_eval = len(rows_i)
            lo = n_eval * P_POSTZ * REPL_LOW
            hi = n_eval * P_POSTZ * REPL_HIGH
            tag = f"{j['pattern']} [{j['target']}]"
            for x in rows_i:
                x.update({"pattern": j["pattern"], "target": j["target"],
                          "pattern_kind": j["kind"], "K_star": meta.get("K_star"),
                          "n_evaluated_in_pattern": n_eval,
                          "chance_expected_named_low": round(lo, 2),
                          "chance_expected_named_high": round(hi, 2)})
            named_rows += rows_i
            l3_meta[tag] = {**meta, "n_evaluated": n_eval,
                            "chance_expected_named": [round(lo, 2), round(hi, 2)],
                            "reported": int(sum(x["reported"] for x in rows_i))}
            print(f"  [L3] {tag}: {n_eval} players evaluated, "
                  f"{l3_meta[tag]['reported']} named, chance expects "
                  f"{lo:.1f}-{hi:.1f}")

    cols = ["pattern", "target", "pattern_kind", "player_id", "player_name",
            "n_rows", "sxx", "raw_dev_slope", "trait_pred_slope", "shrunken_dev",
            "posterior_z", "half1_slope", "half2_slope", "half_signs",
            "survives_shrinkage", "replicates_sign", "reported", "K_star",
            "n_evaluated_in_pattern", "chance_expected_named_low",
            "chance_expected_named_high"]
    nd = pd.DataFrame(named_rows)[cols] if named_rows else pd.DataFrame(columns=cols)
    nd.to_csv(OUT / "named_player_deviations.csv", index=False)

    IL.write_quarantine(OUT, ctx)

    runtime = time.time() - t0
    write_report(res, surv, rob, nd, l3_meta, vol_chosen, pt_alphas, anchors,
                 per_t, exc_df, pd.DataFrame(freq_rows), collapsed, feats_kept,
                 conds_kept, args, ctx, runtime, targets_run)

    n_bh = int(res["bh_pass"].sum())
    n_surv = int(res["survives"].sum())
    n_up = int((res["power_label_pooled"] == "underpowered").sum())
    n_np = int((res["power_label_pooled"] == "null_with_power").sum())
    print(f"\n[done] {len(res)} tests | BH-pass {n_bh} | survivors {n_surv} "
          f"(expected false ~{FDR_Q * n_bh:.1f}) | pooled-power: "
          f"{n_np} null_with_power, {n_up} underpowered | "
          f"named {int(nd['reported'].sum()) if len(nd) else 0} | "
          f"runtime {runtime:.0f}s")
    return 0


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def write_report(res, surv, rob, nd, l3_meta, vol_chosen, pt_alphas, anchors,
                 per_t, exc, freq, collapsed, feats_kept, conds_kept, args, ctx,
                 runtime, targets_run):
    n = len(res)
    n_bh = int(res["bh_pass"].sum())
    n_surv = int(res["survives"].sum())
    n_p05 = int((res["p_value"] <= 0.05).sum())
    p_floor = 1.0 / (args.perms + 1)
    n_floor = int((res["p_value"] <= p_floor + 1e-9).sum())
    bh_floor_need = int(np.ceil(p_floor * n / FDR_Q))
    L, A = [], None
    A = L.append
    A("# player_volume_heterogeneity_v1 — corrected heterogeneity screen")
    A("")
    A(f"*Generated by `volume_heterogeneity.py`; runtime {runtime:.0f}s; "
      f"{args.perms} permutations per test; ridge lambda={FL.RIDGE_LAMBDA} on "
      f"standardized inputs. Reuses `feature_lab.py` and `interactions_lab.py` "
      f"unmodified (imported, never edited).*")
    A("")
    A("## Why this screen exists")
    A("")
    A("`player_feature_interactions_v1` (473 tests) and `player_vs_archetype_v1` "
      "(25 tests) each returned **zero** level-2 survivors. The orchestrator "
      "power diagnostic (`experiments/power_diagnostic.py`, `power_diagnostic2.py`) "
      "showed those nulls were **vacuous, not informative**: points/36 carries "
      "only 29.8% between-player signal, the smallest individual split "
      "difference detectable in points/36 for a median player is **3.89 per 36** "
      "against a measured league condition effect of **+0.38** (home), and some "
      "tested conditions barely occur. This screen keeps the harness and changes "
      "the target to VOLUME, gates rare conditions out up front, and reports a "
      "minimum detectable effect beside every observed effect.")
    A("")
    A("## Protocol (as registered)")
    A("")
    A(f"- Window 2021-2024 ONLY. Quarantine asserted on every matrix "
      f"(`quarantine_audit.json`: all_pass="
      f"{all(a['pass'] for a in ctx.audit)}, {len(ctx.audit)} matrices; "
      f"cutoff {QUARANTINE_CUTOFF.date()}). 2025/2026 are never loaded.")
    A("- Targets (the core change): " + "; ".join(
        f"**{TARGET_LABEL[t]}**" for t in TARGETS) + " — NOT points.")
    A(f"- Battery: {len(feats_kept)} feature columns x {len(conds_kept)} "
      f"conditions x {len(targets_run)} targets = **{n} tests**. Statistic: "
      "2024 MAE(ridge[b,f,m,f x m]) - MAE(ridge[b,f,m]) — the interaction "
      "column must earn it on walk-forward 2024.")
    A(f"- Null: {args.perms} within-season BLOCK permutations of the "
      "moderator/archetype ASSIGNMENT (player blocks for the 11 player traits, "
      "team blocks for the 7 archetype conditions). BH at "
      f"{FDR_Q:.0%} across this screen's battery; **sign-consistency across the "
      "3 inner folds additionally required for survival** (this registration "
      "names the clause; the previous screens did not).")
    A("")
    A("## Pinned decisions (fixed before results were seen)")
    A("")
    A("- **Baseline per target**: shifted per-player EWMA of that target, alpha "
      "tuned on the 3 inner 2021-2023 folds only. The registered phrase admits "
      "two harness-canonical encodings for a per-36 rate (`ewma_target` = EWMA "
      "of the rate; `ratio_ewma` = the minutes-weighted ratio-of-EWMAs the "
      "committed pooled screen used); both were swept on inner folds and the "
      "**stronger** kept — the conservative direction, since a harder baseline "
      "can only make features look worse.")
    A("- **Universe reused verbatim** from `feature_lab.build_universe`: played "
      "regular-season rows, minutes >= 8, >= 5 prior same-season appearances. "
      "Identical rows to the two prior screens, so this is a like-for-like "
      "re-test with the target swapped.")
    A("- **Feature columns**: the 14 committed pooled-screen survivors on their "
      "surviving channels at their FROZEN alphas, plus the registered "
      "resurrection shortlist. Because the target is no longer a points "
      "channel, each channel-specific resurrection feature contributes ONE "
      "column, at the channel the committed pooled screen itself ranked best "
      "(lowest p, then most negative delta) — a rule read off prior artifacts, "
      "fixed before this screen's results existed. Identical columns are "
      f"collapsed ({len(collapsed)} collapsed) so multiplicity is not inflated.")
    A("- **The committed point-channel baselines are still re-derived** "
      f"({pt_alphas}) because several catalog builders read `ctx.baselines`; "
      "without them the feature columns would not be the ones the previous "
      "screens tested.")
    A("- **Moderator/axis EWMAs pinned at alpha 0.10**; bios/archetype "
      "definitions untouched (`features/moderators.py`, `features/archetypes.py` "
      "are read-only here).")
    A("- **NaN features/conditions** mean-filled with FIT-window means at fit "
      "time (fold fills from fold-train) — feature encoding, not imputation.")
    A("")
    A("## Baselines chosen (inner folds only)")
    A("")
    A("| target | baseline form | alpha | inner-fold MAE |")
    A("|---|---|---|---|")
    for t in TARGETS:
        c = vol_chosen[t]
        A(f"| {TARGET_LABEL[t]} | `{c['form']}` | {c['alpha']} | {c['inner_mae']} |")
    A("")
    A("## Correction 3 — the condition-frequency gate")
    A("")
    n_elig_rows = int(freq["n_eligible_rows"].max()) if len(freq) else 0
    A(f"Every condition's occurrence rate among the {n_elig_rows:,} eligible "
      f"universe rows was computed BEFORE any test was run. Anything "
      f"under **{RARITY_GATE:.0%}** was excluded up front and is NOT reported as "
      "a null. Occurrence is defined as: binary columns -> share at the positive "
      "level; columns with a single modal value on >50% of rows -> share off the "
      "modal value; otherwise 1.0 (the condition varies on essentially every "
      "row, so there is no rarity question).")
    A("")
    if len(exc):
        A("| excluded | role | kind | occurrence | reason |")
        A("|---|---|---|---|---|")
        for _, r in exc.iterrows():
            A(f"| {r['name']} | {r['role']} | {r['kind']} | "
              f"{r['occurrence_rate']:.2%} | {r['reason']} |")
        A("")
        A(f"**{int(exc['tests_removed_from_battery'].iloc[0])} tests were never "
          "run because of this gate** — in the previous screens they would have "
          "been counted as nulls.")
    else:
        A("No condition fell below the gate.")
    A("")
    A("Full table: `condition_frequencies.csv`. Ten rarest conditions:")
    A("")
    A("| condition | role | kind | occurrence |")
    A("|---|---|---|---|")
    for _, r in freq.sort_values("occurrence_rate").head(10).iterrows():
        A(f"| {r['name']} | {r['role']} | {r['kind']} | {r['occurrence_rate']:.2%} |")
    A("")
    A("## Correction 4 — power reporting")
    A("")
    A("Every row of `screen_results.csv` carries, beside its observed effect:")
    A("")
    A("- `observed_effect` — |beta_interaction|, the fitted interaction "
      "coefficient in TARGET UNITS per (1 sd feature x 1 sd condition). "
      "Directly comparable to the MDE columns.")
    A("- `mde_player` — the registered formula "
      "`2.8 * sd_within_player * sqrt(2 / (n_per_player/2))` for the **median "
      "eligible player** of that test (eligible player = >= 20 eligible rows, "
      "the level-3 naming gate). This is the INDIVIDUAL-level resolution: what "
      "a single player's conditional split would have to be for us to see it.")
    A("- `mde_pooled` — the same formula at the test's TOTAL eligible n. This "
      "is the LEVEL-2 resolution, because the pooled ridge aggregates the split "
      "across all players at once.")
    A("- `plausible_effect` — the measured per-target anchor (max of the league "
      "home split, the league rest split, and a 5%-of-mean floor), the same "
      "anchor class the diagnostic used for points (+0.38/36 home).")
    A("- `power_label` (registered, per-player MDE) and `power_label_pooled` "
      f"(pooled MDE): a non-survivor is `underpowered` when MDE > "
      f"{UNDERPOWER_RATIO:g} x plausible effect, else `null_with_power`.")
    A("")
    A("**Which label to read for which claim**: the per-player MDE governs "
      "whether an INDIVIDUAL effect (level 3) could ever have been seen; the "
      "pooled MDE governs whether the LEVEL-2 pooled test could have seen a "
      "plausible effect. Both are reported so no null is stated without saying "
      "what it could have seen.")
    A("")
    A("| target | plausible effect | home split | rest split | 5% floor | "
      "median within-player sd | median MDE (player) | median MDE (pooled) |")
    A("|---|---|---|---|---|---|---|---|")
    for t in targets_run:
        sub = res[res["target"] == t]
        a = anchors[t]
        A(f"| {TARGET_LABEL[t]} | {a['plausible_effect']} | {a['home_split']} | "
          f"{a['rest_split']} | {a['floor_5pct_of_mean']} | "
          f"{sub['sd_within_player'].median():.3f} | "
          f"{sub['mde_player'].median():.3f} | {sub['mde_pooled'].median():.4f} |")
    A("")
    A("## Headline")
    A("")
    A(f"- **{n} tests**; p <= 0.05 before correction: **{n_p05}** "
      f"(global-null expectation ~{0.05 * n:.1f}).")
    A(f"- **BH({FDR_Q:.0%}) passes: {n_bh}**; with the registered "
      f"sign-consistency clause, **survivors: {n_surv}**; expected false among "
      f"the BH passes: ~{FDR_Q * n_bh:.1f}.")
    A(f"- Tests at the permutation p-floor ({p_floor:.5f}): **{n_floor}**. "
      f"With {n} tests, BH at {FDR_Q:.0%} cannot reject anything unless at "
      f"least **{bh_floor_need}** tests sit at that floor — a hard multiplicity "
      f"fact of a {args.perms}-permutation null over a battery this size, and "
      "itself a power statement about the screen (see 'Screen-level power').")
    A("")
    A("Power split over all tests (pooled MDE, the level-2-appropriate one):")
    A("")
    A("| label | count |")
    A("|---|---|")
    for lab, cnt in res["power_label_pooled"].value_counts().items():
        A(f"| {lab} | {cnt} |")
    A("")
    A("Power split using the registered per-player MDE (the level-3-appropriate one):")
    A("")
    A("| label | count |")
    A("|---|---|")
    for lab, cnt in res["power_label"].value_counts().items():
        A(f"| {lab} | {cnt} |")
    A("")
    A("p-value histogram (bin 0.05):")
    A("")
    A("```")
    A(IL._histogram_line(res["p_value"]))
    A("```")
    A("")
    A("## Per-target results")
    A("")
    A("| target | tests | p<=0.05 | at p-floor | min p | survivors | "
      "BH within target (secondary) | median pooled MDE | plausible effect |")
    A("|---|---|---|---|---|---|---|---|---|")
    for t in targets_run:
        sub = res[res["target"] == t]
        pt = per_t[t]
        A(f"| {TARGET_LABEL[t]} | {pt['n']} | {pt['n_p05']} | {pt['n_at_p_floor']} | "
          f"{pt['min_p']:.5f} | {int(sub['survives'].sum())} | "
          f"{pt['bh_pass_within_target']} | {sub['mde_pooled'].median():.4f} | "
          f"{anchors[t]['plausible_effect']} |")
    A("")
    A("*The per-target BH column is a SECONDARY diagnostic (4 families of "
      f"{per_t[targets_run[0]]['n']}); the binding rule is BH across the whole "
      "battery, as registered.*")
    A("")
    A("## Survivors")
    A("")
    if len(surv):
        A("| target | # | feature | condition | delta MAE | observed effect | "
          "MDE pooled | p | q | folds | min15 |")
        A("|---|---|---|---|---|---|---|---|---|---|---|")
        for _, r in surv.iterrows():
            A(f"| {r['target']} | {r['catalog_number']} | {r['feature']} | "
              f"{r['condition']} | {r['delta_mae']:+.5f} | "
              f"{r['observed_effect']:.4f} | {r['mde_pooled']:.4f} | "
              f"{r['p_value']:.5f} | {r['q_value']:.4f} | {r['fold_signs']} | "
              f"{r.get('delta_mae_min15', '')} |")
    else:
        A("**None.** No feature x condition interaction beat the "
          "no-interaction model plus multiplicity control and inner-fold "
          "sign-consistency on any volume target.")
    A("")
    A("## Strongest 15 tests regardless of survival")
    A("")
    A("| target | feature | condition | delta MAE | observed effect | "
      "MDE pooled | p | q | folds | power |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for _, r in res.sort_values(["p_value", "delta_mae"]).head(15).iterrows():
        oe = "" if pd.isna(r["observed_effect"]) else f"{r['observed_effect']:.4f}"
        A(f"| {r['target']} | #{r['catalog_number']} {r['feature']} | "
          f"{r['condition']} | {r['delta_mae']:+.5f} | {oe} | "
          f"{r['mde_pooled']:.4f} | {r['p_value']:.5f} | {r['q_value']:.4f} | "
          f"{r['fold_signs']} | {r['power_label_pooled']} |")
    A("")
    A("## Screen-level power — what this null can and cannot say")
    A("")
    A("Three distinct power questions, all answered here rather than left "
      "implicit as in the previous screens:")
    A("")
    A(f"1. **Individual resolution (level 3)**: median per-player MDE by target "
      "is in the power table above. Compare to the plausible-effect column: a "
      "ratio far above 1 means an individual conditional effect of realistic "
      "size is invisible at this sample size, whatever the p-value says.")
    A(f"2. **Pooled resolution (level 2)**: median pooled MDE by target. This "
      "is the number that decides whether a level-2 null is informative.")
    A(f"3. **Multiplicity resolution (the screen itself)**: with {n} tests, a "
      f"{args.perms}-permutation null (p-floor {p_floor:.5f}) and BH at "
      f"{FDR_Q:.0%}, at least {bh_floor_need} tests must sit at the p-floor "
      f"before ANY test can be rejected. Observed at the floor: {n_floor}. "
      "This is a property of the registered design, and it is the reason the "
      "per-target secondary BH column is reported alongside.")
    A("")
    A("## Level 3 — named-player deviations vs chance")
    A("")
    A("Naming gates (unchanged machinery, `interactions_lab.eb_level3`): "
      "n >= 20 rows, posterior |z| >= 2 after EB shrinkage (K tuned on the "
      "inner folds), and same-sign deviation in both halves of the player's "
      "2021-2024 appearances (>= 10 rows per half).")
    A("")
    A("**Chance expectation** (the comparison the previous screen omitted): "
      f"under a pure null, P(|z| >= 2) = {P_POSTZ}, and the two-half "
      f"sign-replication gate passes with probability between {REPL_LOW} "
      f"(halves independent) and {REPL_HIGH} (halves tracking the overall "
      "sign), so chance predicts between "
      f"`n_evaluated x {P_POSTZ} x {REPL_LOW}` and "
      f"`n_evaluated x {P_POSTZ} x {REPL_HIGH}` named players. "
      "*(By this same arithmetic the previous archetype screen's 1,352 "
      "player-pattern evaluations predicted 15-31 named players by chance; it "
      "reported 2 — i.e. it found fewer than chance, which is why the "
      "comparison has to appear.)*")
    A("")
    if len(nd):
        rep = nd[nd["reported"]]
        tot_lo = sum(m["chance_expected_named"][0] for m in l3_meta.values())
        tot_hi = sum(m["chance_expected_named"][1] for m in l3_meta.values())
        A(f"- Player-pattern evaluations: **{len(nd)}**; "
          f"**named: {len(rep)}**; **chance expects {tot_lo:.0f}-{tot_hi:.0f}**.")
        verdict = ("BELOW chance" if len(rep) < tot_lo else
                   "within the chance band" if len(rep) <= tot_hi else "ABOVE chance")
        A(f"- Verdict: the named count is **{verdict}** — "
          + ("no evidence of credible individual heterogeneity beyond noise."
             if len(rep) <= tot_hi else
             "more named players than chance predicts; see the table."))
        A("")
        A("| pattern | target | evaluated | named | chance low | chance high | K* |")
        A("|---|---|---|---|---|---|---|")
        for tag, m in l3_meta.items():
            A(f"| {tag.rsplit(' [', 1)[0]} | {tag.rsplit(' [', 1)[1][:-1]} | "
              f"{m['n_evaluated']} | {m['reported']} | "
              f"{m['chance_expected_named'][0]} | {m['chance_expected_named'][1]} | "
              f"{m.get('K_star')} |")
        if len(rep):
            A("")
            A("| pattern | target | player | n | raw dev | shrunk dev | post z | halves |")
            A("|---|---|---|---|---|---|---|---|")
            for _, r in rep.sort_values("posterior_z", key=abs,
                                        ascending=False).head(40).iterrows():
                A(f"| {r['pattern']} | {r['target']} | {r['player_name']} | "
                  f"{r['n_rows']} | {r['raw_dev_slope']:+.4f} | "
                  f"{r['shrunken_dev']:+.4f} | {r['posterior_z']:+.2f} | "
                  f"{r['half_signs']} |")
    else:
        A("Level 3 not run (dev mode) or no pattern reached it.")
    A("")
    A("## Files")
    A("")
    A("- `screen_results.csv` — every test: observed effect, MDE (player and "
      "pooled), plausible effect, power label, p, q, survives")
    A("- `survivor_summary.csv` — survivors (+ >=15-minute robustness)")
    A("- `excluded_for_rarity.csv` — conditions excluded UP FRONT with their "
      "observed frequency (never reported as nulls)")
    A("- `condition_frequencies.csv` — the full frequency table")
    A("- `named_player_deviations.csv` — level-3 evidence per evaluated player, "
      "carrying the chance-expectation columns")
    A("- `baseline_alpha_curves.csv` — inner-fold baseline sweep, both forms")
    A("- `quarantine_audit.json` — per-matrix date audit")
    (OUT / "REPORT.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
