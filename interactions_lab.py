"""interactions_lab.py — ONE harness pass implementing TWO preregistered
heterogeneity screening protocols (experiments/registry.jsonl):

  * player_feature_interactions_v1  (registered 2026-07-31T13:16:25Z)
  * player_vs_archetype_v1          (registered 2026-07-31T13:33:33Z)

Both inherit the harness, windows, and quarantine of player_feature_screen_v1
(feature_lab.py, reused — not reimplemented): screening window 2021-2024 ONLY,
inner tuning 2021-2023, validation 2024. THE QUARANTINE IS ABSOLUTE: 2025/2026
rows are never loaded; every assembled matrix asserts
max(game_date) < 2025-01-01 (features.common.assert_quarantine) and the audit
trail is written to each experiment directory's quarantine_audit.json.

PROTOCOL 1 (player_feature_interactions_v1)
  Battery (preregistered, closed): (a) every committed survivor of
  player_feature_screen_v1 (experiments/feature_screen/survivor_summary.csv,
  14 rows) on its surviving channel; (b) the resurrection shortlist —
  #6 rest-bucket, #7 back-to-back, #80 minutes-load, #9 travel distance,
  #1 personal home lift, #16 opponent pace profile, #94 blowout-minutes
  elasticity, #14 opponent rim protection, #17 opponent lineup height —
  each crossed with the CLOSED 11-moderator set (features/moderators.py),
  matching the registration's stated multiplicity
  "~(survivors + 8 resurrection) x 11 moderators x relevant channels".
  The registered marquee pairings (#7/#80 x age, #9 x age, #1 x experience,
  #16 x transition share, #94 x starter share, #14 x rim share, #17 x own
  height) are flagged `registered_pairing`.
  Level-2 test per (feature, moderator, channel): ridge [baseline, feature,
  moderator, feature*moderator] vs ridge [baseline, feature, moderator],
  both fit 2021-2023 and scored on walk-forward 2024; the statistic is the
  2024 MAE delta between the two — the interaction term itself must earn it.
  Null: 200 within-season permutations of the MODERATOR ASSIGNMENT across
  players (player-block permutation: which player carries which trait
  profile; feature and target structure untouched). BH at 10% across the
  full battery. Level-3 for BH survivors: empirical-Bayes per-player slopes
  shrunk toward the trait-predicted slope (shrinkage constant tuned on the
  inner 2021-2023 folds); a named-player deviation is reported ONLY if it
  survives shrinkage (posterior |z| >= 2) AND replicates sign in the
  within-player time split (first vs second half of their 2021-2024
  appearances).

PROTOCOL 2 (player_vs_archetype_v1)
  Five opponent-archetype axes + TALL-SHOOTERS / SMALL-PRESSURE composites
  (features/archetypes.py, walk-forward medians). Level-2: own-trait x
  archetype-axis interactions (own height, rim share, 3PA rate, transition
  share) on their mechanism channels; null = 200 within-season permutations
  of the ARCHETYPE ASSIGNMENT across teams (team-block permutation); BH at
  10% as its OWN family. Level-3: EB individual slopes on the two composites
  (all four channels), same shrinkage machinery and time-split replication.

THIS SCRIPT RECORDS NOTHING ON THE LEDGER: it never imports or calls
registry.register / evaluate / record_evaluation / render_leaderboards and
never writes experiments/registry.jsonl. It never runs git. Artifacts go to
experiments/feature_interactions/ and experiments/feature_archetypes/ only.

Run:  python interactions_lab.py                 # both protocols, 200 perms
      python interactions_lab.py --perms 20 --limit1 8 --limit2 4 --skip-l3
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

import feature_lab as FL  # noqa: E402  (the committed harness — reused)
from features import ALL_CANDIDATES, CHANNELS, Ctx  # noqa: E402
from features.common import (QUARANTINE_CUTOFF, TRAIN_SEASONS, VAL_SEASON,  # noqa: E402
                             assert_quarantine, gps)
from features import moderators as MODS  # noqa: E402
from features import archetypes as ARCH  # noqa: E402

OUT1 = REPO / "experiments" / "feature_interactions"
OUT2 = REPO / "experiments" / "feature_archetypes"
SCREEN_DIR = REPO / "experiments" / "feature_screen"

SEED_BASE = 20260731
FDR_Q = 0.10
N_PERM_DEFAULT = 200
MIN_MINUTES_ROBUST = 15.0
EPS = 1e-12

# Level-3 pinned constants (documented in REPORT.md)
K_GRID = [4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0, 512.0, np.inf]
L3_MIN_ROWS = 20          # minimum universe appearances to be evaluated
L3_MIN_HALF = 10          # minimum rows per time-split half
POSTZ_GATE = 2.0          # posterior |z| gate = "survives shrinkage"

# the registration's designated (mechanistic) pairings — flagged, not exclusive
REGISTERED_PAIRINGS = {
    (7, "age"), (80, "age"), (9, "age"), (1, "experience_years"),
    (16, "transition_share"), (94, "starter_share"), (14, "rim_share"),
    (17, "height_inches"),
}

# protocol-2 own-trait -> mechanism channels (pinned before results)
TRAIT_CHANNELS = {
    "height_inches": ["paint"],
    "rim_share": ["paint"],
    "fg3a_rate": ["fg3"],
    "transition_share": ["fg3", "paint"],
}


# ---------------------------------------------------------------------------
# level-2 machinery
# ---------------------------------------------------------------------------

def _mstd(a):
    m, s = float(np.mean(a)), float(np.std(a))
    return m, (s if s > EPS else 1.0), (s <= EPS)


def _fit_pair(zb_tr, zf_tr, zm_tr, y_tr, zb_va, zf_va, zm_va, y_va):
    """(MAE no-interaction, MAE interaction, beta_interaction) — ridge
    lambda=1.0 on standardized inputs, unpenalized intercept (harness)."""
    Zn_tr = np.column_stack([zb_tr, zf_tr, zm_tr])
    Zi_tr = np.column_stack([zb_tr, zf_tr, zm_tr, zf_tr * zm_tr])
    bn = FL.ridge_fit(Zn_tr, y_tr)
    bi = FL.ridge_fit(Zi_tr, y_tr)
    Zn_va = np.column_stack([zb_va, zf_va, zm_va])
    Zi_va = np.column_stack([zb_va, zf_va, zm_va, zf_va * zm_va])
    mae_n = FL.mae(y_va, FL.ridge_predict(Zn_va, bn))
    mae_i = FL.mae(y_va, FL.ridge_predict(Zi_va, bi))
    return mae_n, mae_i, float(bi[4])


def l2_test(b, y, f_raw, m_raw, tr, va, fold_pos, n_perm, perm_side, perm_fn):
    """One preregistered interaction test.

    b, y, f_raw, m_raw: full-length arrays over the universe rows.
    perm_fn(k, fill) -> permuted FILLED full-length array for `perm_side`
    ('m' = moderator/trait assignment, 'f' = archetype assignment).
    """
    out = {"degenerate": False, "note": ""}
    ftr_vals, mtr_vals = f_raw[tr], m_raw[tr]
    fill_f = float(np.nanmean(ftr_vals)) if np.any(~np.isnan(ftr_vals)) else 0.0
    fill_m = float(np.nanmean(mtr_vals)) if np.any(~np.isnan(mtr_vals)) else 0.0
    out["nan_share_feature"] = round(float(np.mean(np.isnan(f_raw))), 4)
    out["nan_share_moderator"] = round(float(np.mean(np.isnan(m_raw))), 4)
    ff = np.where(np.isnan(f_raw), fill_f, f_raw)
    fm = np.where(np.isnan(m_raw), fill_m, m_raw)

    mb, sb, _ = _mstd(b[tr])
    mf, sf, degf = _mstd(ff[tr])
    mm, sm, degm = _mstd(fm[tr])
    if degf or degm:
        out.update({"degenerate": True, "p_value": 1.0, "delta_mae": 0.0,
                    "improvement": 0.0, "beta_interaction": 0.0,
                    "mae_noint_2024": np.nan, "mae_int_2024": np.nan,
                    "fold_deltas": "", "fold_signs": "", "corr_fm": np.nan,
                    "null_q50": 0.0, "null_q95": 0.0,
                    "note": "degenerate (constant feature or moderator)"})
        return out
    zb = (b - mb) / sb
    zf = (ff - mf) / sf
    zm = (fm - mm) / sm
    out["corr_fm"] = round(float(np.corrcoef(zf[tr], zm[tr])[0, 1]), 4)

    mae_n, mae_i, beta = _fit_pair(zb[tr], zf[tr], zm[tr], y[tr],
                                   zb[va], zf[va], zm[va], y[va])
    delta = mae_i - mae_n
    improvement = -delta

    # descriptive inner-fold deltas at the same statistic
    fold_deltas = []
    for (p_tr, p_va) in fold_pos:
        fff = np.where(np.isnan(f_raw), float(np.nanmean(f_raw[p_tr]))
                       if np.any(~np.isnan(f_raw[p_tr])) else 0.0, f_raw)
        fmf = np.where(np.isnan(m_raw), float(np.nanmean(m_raw[p_tr]))
                       if np.any(~np.isnan(m_raw[p_tr])) else 0.0, m_raw)
        kb, ksb, _ = _mstd(b[p_tr])
        kf, ksf, dgf = _mstd(fff[p_tr])
        km, ksm, dgm = _mstd(fmf[p_tr])
        if dgf or dgm:
            fold_deltas.append(np.nan)
            continue
        zbk, zfk, zmk = (b - kb) / ksb, (fff - kf) / ksf, (fmf - km) / ksm
        mn, mi, _b = _fit_pair(zbk[p_tr], zfk[p_tr], zmk[p_tr], y[p_tr],
                               zbk[p_va], zfk[p_va], zmk[p_va], y[p_va])
        fold_deltas.append(mi - mn)

    # permutation null (assignment permutation of one side, refit BOTH models)
    null_imp = np.zeros(n_perm)
    for k in range(n_perm):
        pv = perm_fn(k, fill_m if perm_side == "m" else fill_f)
        pm, ps, dg = _mstd(pv[tr])
        if dg:
            null_imp[k] = 0.0
            continue
        zp = (pv - pm) / ps
        if perm_side == "m":
            mn, mi, _b = _fit_pair(zb[tr], zf[tr], zp[tr], y[tr],
                                   zb[va], zf[va], zp[va], y[va])
        else:
            mn, mi, _b = _fit_pair(zb[tr], zp[tr], zm[tr], y[tr],
                                   zb[va], zp[va], zm[va], y[va])
        null_imp[k] = mn - mi
    p = float((1 + np.sum(null_imp >= improvement)) / (1 + n_perm))

    out.update({
        "mae_noint_2024": round(mae_n, 5), "mae_int_2024": round(mae_i, 5),
        "delta_mae": round(delta, 5), "improvement": round(improvement, 5),
        "beta_interaction": round(beta, 5),
        "fold_deltas": ";".join("" if np.isnan(d) else f"{d:+.5f}" for d in fold_deltas),
        "fold_signs": "".join("x" if np.isnan(d) else ("-" if d < 0 else "+")
                              for d in fold_deltas),
        "p_value": round(p, 5),
        "null_q50": round(float(np.quantile(null_imp, 0.50)), 6),
        "null_q95": round(float(np.quantile(null_imp, 0.95)), 6),
    })
    return out


def build_block_bank(seasons, keys, n_perm, seed):
    """Bank of `n_perm` within-season BLOCK permutations: block = all rows of
    one key (player or team) in one season, kept in row (=date) order; the
    permutation reassigns which key carries which block's value sequence
    (donor sequences cycled when lengths differ). Returns (n_perm, n) int64
    donor-row indices. One preregistered bank is shared across the battery
    (the permuted object is common to many tests); each test's p-value is
    exact under its null — sharing affects only cross-test dependence."""
    n = len(seasons)
    df = pd.DataFrame({"s": np.asarray(seasons), "k": np.asarray(keys)})
    by_season: dict = {}
    for (s, kk), idx in df.groupby(["s", "k"]).indices.items():
        by_season.setdefault(s, []).append(np.sort(np.asarray(idx)))
    rng = np.random.default_rng(seed)
    bank = np.tile(np.arange(n, dtype=np.int64), (n_perm, 1))
    for s, blocks in by_season.items():
        nb = len(blocks)
        for k in range(n_perm):
            perm = rng.permutation(nb)
            for gi, rows in enumerate(blocks):
                donor = blocks[perm[gi]]
                bank[k, rows] = donor[np.arange(len(rows)) % len(donor)]
    return bank


def row_perm_fn(raw_vals, bank):
    state: dict = {}
    def fn(k, fill):
        if "filled" not in state:
            state["filled"] = np.where(np.isnan(raw_vals), fill, raw_vals)
        return state["filled"][bank[k]]
    return fn


def tg_perm_fn(tg_vals, bank_tg, ptr_rows):
    state: dict = {}
    def fn(k, fill):
        if "filled" not in state:
            state["filled"] = np.where(np.isnan(tg_vals), fill, tg_vals)
            state["safe"] = np.clip(ptr_rows, 0, None)
            state["miss"] = ptr_rows < 0
        v = state["filled"][bank_tg[k]]
        out = v[state["safe"]].copy()
        out[state["miss"]] = fill
        return out
    return fn


# ---------------------------------------------------------------------------
# level-3 machinery (EB per-player slopes, shrinkage tuned on inner folds)
# ---------------------------------------------------------------------------

def _slope(x, r):
    xc = x - x.mean()
    sxx = float(np.sum(xc * xc))
    if sxx < 1e-8:
        return np.nan, sxx
    rc = r - r.mean()
    return float(np.sum(xc * rc) / sxx), sxx


def _prep_cols(cols_raw, fit_pos):
    """Fill (fit-window means) + standardize (fit-window stats) each column;
    returns list of full-length z arrays, or None if any column degenerate."""
    zs = []
    for c in cols_raw:
        seg = c[fit_pos]
        fill = float(np.nanmean(seg)) if np.any(~np.isnan(seg)) else 0.0
        fc = np.where(np.isnan(c), fill, c)
        m, s, dg = _mstd(fc[fit_pos])
        if dg:
            return None
        zs.append((fc - m) / s)
    return zs


def _design(zb, zf, zms):
    return np.column_stack([zb, zf] + zms + [zf * zm for zm in zms])


def eb_level3(b, y, f_raw, mods_raw, tr, fold_pos, dates, players, names):
    """EB per-player random slopes on `f_raw`, shrunk toward the slope
    predicted by the trait columns `mods_raw` (list). Returns (rows, meta).

    Pooled interaction model [baseline, f, traits, f x traits] is fit on the
    2021-2023 train rows (frozen); per-player deviation slopes are OLS slopes
    of its residual on z(f) within player over ALL 2021-2024 universe rows
    (the pooled model already removes the trait-predicted component, so the
    within-player slope IS the deviation). Shrinkage constant K (in z-units
    of Sxx, ~= effective games) tuned on the 3 inner walk-forward folds.
    Gates for NAMING a player: n >= 20, posterior |z| >= 2 under the EB prior
    (tau^2 = sigma^2/K), and same-sign deviation in both halves of the
    player's 2021-2024 appearances (>= 10 rows per half)."""
    zs = _prep_cols([b, f_raw] + list(mods_raw), tr)
    if zs is None:
        return [], {"skipped": "degenerate columns"}
    zb, zf, zms = zs[0], zs[1], zs[2:]
    Z = _design(zb, zf, zms)
    beta = FL.ridge_fit(Z[tr], y[tr])
    pred = FL.ridge_predict(Z, beta)
    resid = y - pred
    sigma2 = float(np.var(resid[tr]))
    n_tr_cols = 2 + 2 * len(zms)   # zb zf traits inters
    beta_f = float(beta[2])
    beta_int = np.asarray(beta[3 + len(zms):3 + 2 * len(zms)], dtype=float)

    # ---- K on inner folds ----
    k_curve = {K: [] for K in K_GRID}
    for (p_tr, p_va) in fold_pos:
        zsF = _prep_cols([b, f_raw] + list(mods_raw), p_tr)
        if zsF is None:
            continue
        zbF, zfF, zmsF = zsF[0], zsF[1], zsF[2:]
        ZF = _design(zbF, zfF, zmsF)
        betaF = FL.ridge_fit(ZF[p_tr], y[p_tr])
        predF = FL.ridge_predict(ZF, betaF)
        residF = y - predF
        pl_tr = players[p_tr]
        dev, sxx = {}, {}
        for pid in np.unique(pl_tr):
            rows = p_tr[pl_tr == pid]
            if len(rows) < 5:
                continue
            d, s = _slope(zfF[rows], residF[rows])
            if not np.isnan(d):
                dev[pid], sxx[pid] = d, s
        pl_va = players[p_va]
        d_arr = np.array([dev.get(p, 0.0) for p in pl_va])
        s_arr = np.array([sxx.get(p, 0.0) for p in pl_va])
        for K in K_GRID:
            w = np.zeros_like(s_arr) if np.isinf(K) else s_arr / (s_arr + K)
            adj = w * d_arr * zfF[p_va]
            k_curve[K].append(FL.mae(y[p_va], predF[p_va] + adj))
    k_mean = {K: float(np.mean(v)) for K, v in k_curve.items() if v}
    if not k_mean:
        return [], {"skipped": "no usable folds"}
    K_star = min(k_mean, key=k_mean.get)
    gain_inner = (k_mean.get(np.inf, np.nan) - k_mean[K_star])

    # ---- final per-player estimates over all 2021-2024 universe rows ----
    rows_out = []
    order = np.argsort(players, kind="mergesort")
    bounds = np.flatnonzero(np.r_[True, np.diff(players[order]) != 0, True])
    for i0, i1 in zip(bounds[:-1], bounds[1:]):
        pos = order[i0:i1]
        pos = pos[np.argsort(dates[pos], kind="mergesort")]
        pid = int(players[pos[0]])
        n_i = len(pos)
        if n_i < L3_MIN_ROWS:
            continue
        d_i, sxx_i = _slope(zf[pos], resid[pos])
        if np.isnan(d_i):
            continue
        if np.isinf(K_star):
            w_i, shrunk, post_z = 0.0, 0.0, 0.0
        else:
            w_i = sxx_i / (sxx_i + K_star)
            shrunk = w_i * d_i
            post_sd = float(np.sqrt(sigma2 / (sxx_i + K_star)))
            post_z = shrunk / post_sd if post_sd > 0 else 0.0
        trait_pred = beta_f + float(sum(bi * np.mean(zm[pos])
                                        for bi, zm in zip(beta_int, zms)))
        h = n_i // 2
        s1, sxx1 = _slope(zf[pos[:h]], resid[pos[:h]])
        s2, sxx2 = _slope(zf[pos[h:]], resid[pos[h:]])
        halves_ok = (h >= L3_MIN_HALF and (n_i - h) >= L3_MIN_HALF
                     and not np.isnan(s1) and not np.isnan(s2))
        survives_shrink = bool(abs(post_z) >= POSTZ_GATE)
        replicates = bool(halves_ok and np.sign(s1) == np.sign(s2)
                          and np.sign(s1) == np.sign(shrunk) and shrunk != 0.0)
        rows_out.append({
            "player_id": pid, "player_name": names.get(pid, "?"),
            "n_rows": n_i, "sxx": round(sxx_i, 2),
            "raw_dev_slope": round(d_i, 5),
            "trait_pred_slope": round(trait_pred, 5),
            "shrunken_dev": round(shrunk, 5), "posterior_z": round(post_z, 3),
            "half1_slope": round(s1, 5) if not np.isnan(s1) else np.nan,
            "half2_slope": round(s2, 5) if not np.isnan(s2) else np.nan,
            "half_signs": (("-" if s1 < 0 else "+") if not np.isnan(s1) else "x")
                          + (("-" if s2 < 0 else "+") if not np.isnan(s2) else "x"),
            "survives_shrinkage": survives_shrink, "replicates_sign": replicates,
            "reported": bool(survives_shrink and replicates),
        })
    meta = {"K_star": (None if np.isinf(K_star) else K_star),
            "K_curve": {str(k): round(v, 6) for k, v in k_mean.items()},
            "inner_gain_vs_no_individual": round(float(gain_inner), 6)
            if not np.isnan(gain_inner) else None,
            "sigma2": round(sigma2, 5),
            "beta_feature": round(beta_f, 5),
            "beta_interactions": [round(float(x), 5) for x in beta_int]}
    return rows_out, meta


# ---------------------------------------------------------------------------
# battery construction (protocol 1)
# ---------------------------------------------------------------------------

def travel_distance(ctx):
    """#9 — haversine km from the previous game's venue (schedule fact;
    first game of a player-season = 0)."""
    P = ctx.P
    tc = pd.read_csv(REPO / "data" / "reference" / "team_cities.csv")
    tc = tc[tc["first_season"] <= 2024].drop_duplicates("team_id")
    lat_m = dict(zip(tc["team_id"], tc["lat"]))
    lon_m = dict(zip(tc["team_id"], tc["lon"]))
    venue = np.where(P["is_home"].to_numpy(float) == 1.0,
                     P["team_id"].to_numpy(), P["opp_team_id"].to_numpy())
    lat = pd.Series(venue, index=P.index).map(lat_m).astype(float)
    lon = pd.Series(venue, index=P.index).map(lon_m).astype(float)
    plat = lat.groupby(gps(P)).shift(1)
    plon = lon.groupby(gps(P)).shift(1)
    r1, r2 = np.radians(plat), np.radians(lat)
    dlat = r2 - r1
    dlon = np.radians(lon - plon)
    a = np.sin(dlat / 2) ** 2 + np.cos(r1) * np.cos(r2) * np.sin(dlon / 2) ** 2
    km = 2 * 6371.0 * np.arcsin(np.sqrt(a))
    return km.fillna(0.0)


def build_battery(ctx, mods_frame, rot_height_rows):
    """The closed protocol-1 battery: list of dicts
    {num, feature, channel, series, survivor, resurrection}."""
    cand_by_num = {c.num: c for c in ALL_CANDIDATES}
    cache: dict = {}

    def get_series(num, ch, alpha):
        akey = None
        if alpha is not None and not (isinstance(alpha, float) and np.isnan(alpha)):
            akey = round(float(alpha), 3)
        key = (num, akey)
        if key not in cache:
            cache[key] = cand_by_num[num].build(ctx, akey)
        return FL.series_for_channel(cache[key], ch)

    surv = pd.read_csv(SCREEN_DIR / "survivor_summary.csv")
    scr = pd.read_csv(SCREEN_DIR / "screen_results.csv")
    frozen_alpha = {(int(r["catalog_number"]), r["channel"]): r["alpha_chosen"]
                    for _, r in scr.iterrows()}

    entries: dict = {}   # (num, channel) -> entry

    def add(num, name, ch, series, survivor=False, resurrection=False):
        key = (num, ch)
        if key in entries:
            entries[key]["survivor"] |= survivor
            entries[key]["resurrection"] |= resurrection
            return
        entries[key] = {"num": num, "feature": name, "channel": ch,
                        "series": series, "survivor": survivor,
                        "resurrection": resurrection}

    # (a) committed survivors on their surviving channels, frozen alphas
    for _, r in surv.iterrows():
        num, ch = int(r["catalog_number"]), r["channel"]
        add(num, r["name"], ch, get_series(num, ch, r["alpha_chosen"]),
            survivor=True)

    # (b) the resurrection shortlist, exactly as registered
    for ch in CHANNELS:
        add(6, "rest_bucket_profile", ch, get_series(6, ch, None), resurrection=True)
        add(7, "b2b_flag", ch,
            (ctx.P["days_rest_player"] <= 1).astype(float).fillna(0.0),
            resurrection=True)
        add(80, "min7d_load", ch, mods_frame["min7d_load"], resurrection=True)
        add(9, "travel_distance", ch, travel_distance(ctx), resurrection=True)
        add(1, "home_lift_shrunk", ch,
            get_series(1, ch, frozen_alpha.get((1, ch))), resurrection=True)
        add(16, "opp_pace_tercile_profile", ch, get_series(16, ch, None),
            resurrection=True)
        add(94, "blowout_x_min_elasticity", ch, get_series(94, ch, None),
            resurrection=True)
    add(14, "paintrel_vs_rimprot", "paint",
        get_series(14, "paint", frozen_alpha.get((14, "paint"))), resurrection=True)
    add(17, "opp_rotation_height", "paint", rot_height_rows, resurrection=True)

    return list(entries.values())


# ---------------------------------------------------------------------------
# mechanism hypotheses for the ranked trend ledger (charter amendment 4)
# ---------------------------------------------------------------------------

FATIGUE_FEATS = {6, 7, 80, 9}

def mechanism(num, feature, moderator, channel):
    """One-line mechanism hypothesis + anomaly flag. Honest default: pairs
    with no story on file are FLAGGED (and kept — never dropped for taste)."""
    designated = {
        (7, "age"): "older legs pay a larger back-to-back tax",
        (80, "age"): "veterans degrade more under heavy recent minutes load",
        (9, "age"): "travel costs scale with age",
        (1, "experience_years"): "vets' routines dampen venue swings; young players ride them",
        (16, "transition_share"): "open-floor scorers harvest fast-paced opponents",
        (94, "starter_share"): "expected blowouts move starters' and bench minutes in opposite directions",
        (14, "rim_share"): "paint-reliant scorers lose their diet to shot-blocking front lines",
        (17, "height_inches"): "height mismatch prices rim finishing",
    }
    if (num, moderator) in designated:
        return designated[(num, moderator)], False
    if num in FATIGUE_FEATS and moderator in ("career_minutes", "min7d_load"):
        return "fatigue effects compound with accumulated wear", False
    if num in FATIGUE_FEATS and moderator == "bench_depth":
        return "thin rotations cannot shelter tired players", False
    if num in (14, 17) and moderator in ("height_inches", "rim_share") and channel == "paint":
        return "interior matchup effect concentrated in interior-reliant players", False
    if num in (16, 94) and moderator == "usage_ewma":
        return "high-usage players absorb more of any game-environment shift", False
    if num == 1 and moderator == "age":
        return "venue sensitivity may fade with age/experience", False
    if moderator == "starter_share" and num in (94, 16):
        return "role (starter vs bench) gates exposure to game-script effects", False
    return "no mechanism on file - ANOMALY (kept per charter amendment 4)", True


def arch_mechanism(trait, axis, channel):
    m = {
        ("height_inches", "rot_height"): "size-vs-size: rim finishing priced by opposing length",
        ("rim_share", "rot_height"): "paint-reliant scorers meet tall rotations at the rim",
        ("rim_share", "rim_protect"): "rim pressure lands hardest on rim-dependent diets",
        ("height_inches", "rim_protect"): "shot-blockers tax small finishers most",
        ("fg3a_rate", "opp_3pa"): "3pt-volume teams trade threes: high-3PA players see more open looks in those games",
        ("fg3a_rate", "pace"): "fast games create more 3pt volume for volume shooters",
        ("transition_share", "pace"): "transition scorers harvest possessions in fast games",
        ("transition_share", "pressure"): "pressure defenses create open-floor chaos transition players exploit",
        ("rim_share", "pace"): "fast games generate rim runs for interior finishers",
        ("height_inches", "pressure"): "small pressure lineups concede interior position to size",
    }
    if (trait, axis) in m:
        return m[(trait, axis)], False
    return "no mechanism on file - ANOMALY (kept per charter amendment 4)", True


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def finalize_family(rows):
    res = pd.DataFrame(rows)
    res["q_value"] = FL.bh_adjust(res["p_value"].to_numpy(float))
    res["bh_pass"] = res["q_value"] <= FDR_Q
    res["survives"] = res["bh_pass"]
    res = res.sort_values(["survives", "q_value", "delta_mae"],
                          ascending=[False, True, True]).reset_index(drop=True)
    return res


def named_df(all_rows):
    cols = ["pattern", "channel", "player_id", "player_name", "n_rows", "sxx",
            "raw_dev_slope", "trait_pred_slope", "shrunken_dev", "posterior_z",
            "half1_slope", "half2_slope", "half_signs", "survives_shrinkage",
            "replicates_sign", "reported", "K_star"]
    if not all_rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(all_rows)[cols]


def write_quarantine(outdir, ctx, extra=None):
    audit = list(ctx.audit) + (extra or [])
    with open(outdir / "quarantine_audit.json", "w") as f:
        json.dump({"cutoff": str(QUARANTINE_CUTOFF.date()),
                   "all_pass": all(a["pass"] for a in audit),
                   "matrices": audit}, f, indent=2)


def pinned_decisions_lines():
    return [
        "- **Reused harness**: universe, per-channel baselines (frozen alphas from "
        "the committed pooled screen, re-derived deterministically by "
        "`feature_lab.tune_baselines`), ridge (lambda=1.0, standardized, "
        "unpenalized intercept), splits, and quarantine audit all come from "
        "`feature_lab.py` / `features.common` — not reimplemented.",
        "- **Statistic**: 2024 MAE of ridge[baseline, feature, moderator, "
        "feature x moderator] minus ridge[baseline, feature, moderator] — the "
        "interaction column must earn the delta on walk-forward 2024.",
        "- **Null**: within-season BLOCK permutation of the trait/archetype "
        "ASSIGNMENT (a player's — or team's — whole within-season value sequence "
        "is reassigned to another player/team, cycled when lengths differ). This "
        "preserves feature and target structure AND the within-carrier "
        "autocorrelation of the trait, destroying only who-carries-which-trait. "
        "One preregistered 200-permutation bank is shared across the battery "
        "(the permuted object is common to many tests); each p-value is exact "
        "under its null.",
        "- **Moderator/axis EWMAs fixed at alpha 0.10** (constitution rule 3 "
        "constant): the registered sweep clause covers candidate features; the "
        "moderator set is a closed trait battery. Survivor features keep the "
        "alphas FROZEN by the committed pooled screen (survivor_summary.csv / "
        "screen_results.csv); nothing is re-tuned on 2024.",
        "- **Battery**: full cross of the closed feature battery x the closed "
        "11-moderator set (the registration's stated multiplicity). The "
        "registered mechanistic pairings are flagged `registered_pairing`, not "
        "privileged: BH runs across the whole family.",
        "- **Survival = BH(10%)** on the battery (the registration names no "
        "sign-consistency clause for level 2); inner-fold deltas are reported "
        "as descriptive evidence. Robustness: survivors re-tested on the "
        ">=15-minute universe (same frozen configs).",
        "- **Level 3** (BH survivors / registered composites): pooled interaction "
        "model frozen on 2021-2023; per-player deviation slopes = OLS of its "
        "residual on z(feature) within player over 2021-2024 universe rows; EB "
        "shrinkage weight Sxx/(Sxx+K), K tuned on the 3 inner folds "
        "(grid 4..512 + no-individual); naming gates: n>=20, posterior |z|>=2 "
        "(tau^2=sigma^2/K), same-sign deviation in both halves (>=10 rows each) "
        "of the player's 2021-2024 appearances. If K*=no-individual, the named "
        "list is empty by construction — an honest result.",
        "- **Bios**: 2025/2026 season rows filtered at load; age from birthdate "
        "at July 1; undrafted experience = age-22 (a-priori proxy); career "
        "odometer counts 2021+ minutes only (data horizon).",
        "- **NaN moderators/features** mean-filled with FIT-window means at fit "
        "time (fold fills from fold-train) — feature encoding, not imputation.",
    ]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="two-protocol interaction screen")
    ap.add_argument("--perms", type=int, default=N_PERM_DEFAULT)
    ap.add_argument("--limit1", type=int, default=None, help="DEV: first N battery tests")
    ap.add_argument("--limit2", type=int, default=None, help="DEV: first N archetype tests")
    ap.add_argument("--skip-l3", action="store_true", help="DEV only")
    args = ap.parse_args(argv)
    t0 = time.time()
    OUT1.mkdir(parents=True, exist_ok=True)
    OUT2.mkdir(parents=True, exist_ok=True)

    print("[load] building context (quarantine-filtered at source) ...")
    ctx = Ctx()
    U, outer, folds = FL.build_universe(ctx)
    print(f"[universe] {len(U)} rows; train={len(outer.train_idx)} val2024={len(outer.test_idx)}")
    print("[baseline] re-deriving frozen per-channel baseline alphas on inner folds ...")
    chosen, _curves = FL.tune_baselines(ctx, U, outer, folds)
    print(f"[baseline] frozen alphas: {chosen}")

    tr = U.index.get_indexer(outer.train_idx)
    va = U.index.get_indexer(outer.test_idx)
    fold_pos = [(U.index.get_indexer(f.train_idx), U.index.get_indexer(f.val_idx))
                for f in folds]

    def arrays_for(Ux, label):
        assert_quarantine(Ux["game_date"], label, ctx.audit)
        out = {}
        for ch in CHANNELS:
            bvals = ctx.baselines[ch].loc[Ux.index].to_numpy(float)
            if np.isnan(bvals).any():
                raise RuntimeError(f"NaN baseline on {ch}")
            out[ch] = {"y": Ux[f"y_{ch}"].to_numpy(float), "b": bvals}
        return out

    arr = arrays_for(U, f"interactions_design(n={len(U)})")
    U15 = U[U["minutes"] >= MIN_MINUTES_ROBUST].copy()
    arr15 = arrays_for(U15, f"interactions_design_min15(n={len(U15)})")
    tr15 = np.flatnonzero(np.isin(U15["season"].to_numpy(int), TRAIN_SEASONS))
    va15 = np.flatnonzero(U15["season"].to_numpy(int) == VAL_SEASON)

    # ---- moderators + archetypes -----------------------------------------
    print("[traits] building the closed 11-moderator set + archetype axes ...")
    bios = MODS.load_bios(ctx.audit)
    mods_P = MODS.build_moderators(ctx, bios)
    heights = MODS.heights_by_player(bios)
    TG = ARCH.build_archetype_table(ctx, heights, ctx.audit)
    ptr_P = ARCH.opponent_pointer(ctx, TG)
    rot_height_rows = ARCH.axis_on_rows(ctx, TG, ptr_P, "rot_height")

    upos = U.index.to_numpy()
    u15pos = U15.index.to_numpy()
    mods_U = {m: mods_P[m].to_numpy(float)[upos] for m in MODS.MODERATORS}
    mods_U15 = {m: mods_P[m].to_numpy(float)[u15pos] for m in MODS.MODERATORS}
    ptr_U, ptr_U15 = ptr_P[upos], ptr_P[u15pos]

    players_U = U["player_id"].to_numpy(np.int64)
    dates_U = U["game_date"].to_numpy()
    seasons_U = U["season"].to_numpy(int)
    names = dict(zip(ctx.P["player_id"].to_numpy(), ctx.P["player_name"]))

    print("[banks] preregistered assignment-permutation banks ...")
    bank_rows = build_block_bank(seasons_U, players_U, args.perms, SEED_BASE + 1)
    bank_rows15 = build_block_bank(U15["season"].to_numpy(int),
                                   U15["player_id"].to_numpy(np.int64),
                                   args.perms, SEED_BASE + 2)
    bank_tg = build_block_bank(TG["season"].to_numpy(int),
                               TG["team_id"].to_numpy(np.int64),
                               args.perms, SEED_BASE + 3)

    # ======================================================================
    # PROTOCOL 1 — player_feature_interactions_v1
    # ======================================================================
    print("[battery] assembling the closed battery ...")
    battery = build_battery(ctx, mods_P, rot_height_rows)
    tests = []
    for e in battery:
        for m in MODS.MODERATORS:
            tests.append({**{k: e[k] for k in ("num", "feature", "channel",
                                               "survivor", "resurrection")},
                          "moderator": m, "series": e["series"]})
    if args.limit1:
        tests = tests[: args.limit1]
    print(f"[P1] {len(tests)} interaction tests "
          f"({len(battery)} feature-channel entries x {len(MODS.MODERATORS)} moderators)"
          f", {args.perms} permutations each")

    rows1 = []
    feat_vals_cache: dict = {}
    t_p1 = time.time()
    for i, t in enumerate(tests, 1):
        key = (t["num"], t["channel"])
        if key not in feat_vals_cache:
            feat_vals_cache[key] = t["series"].to_numpy(float)[upos]
        f_all = feat_vals_cache[key]
        m_all = mods_U[t["moderator"]]
        A = arr[t["channel"]]
        try:
            r = l2_test(A["b"], A["y"], f_all, m_all, tr, va, fold_pos,
                        args.perms, "m", row_perm_fn(m_all, bank_rows))
        except Exception as ex:  # a test must never sink the battery
            r = {"degenerate": True, "p_value": 1.0, "delta_mae": np.nan,
                 "improvement": np.nan, "beta_interaction": np.nan,
                 "mae_noint_2024": np.nan, "mae_int_2024": np.nan,
                 "fold_deltas": "", "fold_signs": "", "corr_fm": np.nan,
                 "nan_share_feature": np.nan, "nan_share_moderator": np.nan,
                 "null_q50": np.nan, "null_q95": np.nan,
                 "note": f"TEST FAILED: {type(ex).__name__}: {ex}"}
        rows1.append({
            "protocol": "player_feature_interactions_v1",
            "catalog_number": t["num"], "feature": t["feature"],
            "channel": t["channel"], "moderator": t["moderator"],
            "battery": ("survivor+resurrection" if t["survivor"] and t["resurrection"]
                        else "survivor" if t["survivor"] else "resurrection"),
            "registered_pairing": (t["num"], t["moderator"]) in REGISTERED_PAIRINGS,
            "n_train": len(tr), "n_val": len(va), **r})
        if i % 50 == 0 or i == len(tests):
            print(f"  [P1 {i}/{len(tests)}] {time.time()-t_p1:.0f}s")

    res1 = finalize_family(rows1)
    res1.to_csv(OUT1 / "interaction_results.csv", index=False)
    surv1 = res1[res1["survives"]].copy()

    # min15 robustness for survivors (same frozen configs)
    rob_rows = []
    for _, r in surv1.iterrows():
        f15 = None
        for e in battery:
            if e["num"] == r["catalog_number"] and e["channel"] == r["channel"]:
                f15 = e["series"].to_numpy(float)[u15pos]
                break
        m15 = mods_U15[r["moderator"]]
        A15 = arr15[r["channel"]]
        rr = l2_test(A15["b"], A15["y"], f15, m15, tr15, va15, [],
                     args.perms, "m", row_perm_fn(m15, bank_rows15))
        rob_rows.append({"catalog_number": r["catalog_number"],
                         "feature": r["feature"], "channel": r["channel"],
                         "moderator": r["moderator"],
                         "delta_mae_min15": rr.get("delta_mae"),
                         "p_value_min15": rr.get("p_value"),
                         "agrees_with_primary": bool(
                             (rr.get("delta_mae") or 0) < 0) == bool(r["delta_mae"] < 0)})
    rob1 = pd.DataFrame(rob_rows)
    if len(surv1):
        surv1 = surv1.merge(rob1, on=["catalog_number", "feature", "channel",
                                      "moderator"], how="left")
    surv1.to_csv(OUT1 / "survivor_summary.csv", index=False)

    # ---- level 3 for BH survivors ----------------------------------------
    named1_rows, l3_meta1 = [], {}
    if not args.skip_l3:
        print(f"[P1-L3] EB named-player pass on {len(surv1)} survivors ...")
        for _, r in surv1.iterrows():
            f_all = feat_vals_cache[(r["catalog_number"], r["channel"])]
            m_all = mods_U[r["moderator"]]
            A = arr[r["channel"]]
            pat = f"#{r['catalog_number']} {r['feature']} x {r['moderator']} [{r['channel']}]"
            rows_i, meta = eb_level3(A["b"], A["y"], f_all, [m_all], tr,
                                     fold_pos, dates_U, players_U, names)
            for x in rows_i:
                x.update({"pattern": pat, "channel": r["channel"],
                          "K_star": meta.get("K_star")})
            named1_rows += rows_i
            l3_meta1[pat] = meta
    nd1 = named_df(named1_rows)
    nd1.to_csv(OUT1 / "named_player_deviations.csv", index=False)
    write_quarantine(OUT1, ctx)

    # ======================================================================
    # PROTOCOL 2 — player_vs_archetype_v1
    # ======================================================================
    axis_rows_cache = {ax: ARCH.axis_on_rows(ctx, TG, ptr_P, ax).to_numpy(float)[upos]
                       for ax in ARCH.AXES}
    tests2 = []
    for trait in MODS.OWN_TRAITS:
        for ax in ARCH.AXES:
            for ch in TRAIT_CHANNELS[trait]:
                tests2.append({"trait": trait, "axis": ax, "channel": ch})
    if args.limit2:
        tests2 = tests2[: args.limit2]
    print(f"[P2] {len(tests2)} own-trait x archetype tests, {args.perms} perms each")

    rows2 = []
    for i, t in enumerate(tests2, 1):
        f_all = axis_rows_cache[t["axis"]]
        m_all = mods_U[t["trait"]]
        A = arr[t["channel"]]
        tg_vals = TG[t["axis"]].to_numpy(float)
        try:
            r = l2_test(A["b"], A["y"], f_all, m_all, tr, va, fold_pos,
                        args.perms, "f", tg_perm_fn(tg_vals, bank_tg, ptr_U))
        except Exception as ex:
            r = {"degenerate": True, "p_value": 1.0, "delta_mae": np.nan,
                 "improvement": np.nan, "beta_interaction": np.nan,
                 "mae_noint_2024": np.nan, "mae_int_2024": np.nan,
                 "fold_deltas": "", "fold_signs": "", "corr_fm": np.nan,
                 "nan_share_feature": np.nan, "nan_share_moderator": np.nan,
                 "null_q50": np.nan, "null_q95": np.nan,
                 "note": f"TEST FAILED: {type(ex).__name__}: {ex}"}
        rows2.append({"protocol": "player_vs_archetype_v1",
                      "axis": t["axis"], "own_trait": t["trait"],
                      "channel": t["channel"], "n_train": len(tr),
                      "n_val": len(va), **r})
        print(f"  [P2 {i}/{len(tests2)}] {t['trait']} x {t['axis']} [{t['channel']}] "
              f"p={r.get('p_value')}")

    res2 = finalize_family(rows2)
    res2.to_csv(OUT2 / "archetype_results.csv", index=False)
    surv2 = res2[res2["survives"]].copy()

    rob_rows2 = []
    for _, r in surv2.iterrows():
        f15 = ARCH.axis_on_rows(ctx, TG, ptr_P, r["axis"]).to_numpy(float)[u15pos]
        m15 = mods_U15[r["own_trait"]]
        A15 = arr15[r["channel"]]
        rr = l2_test(A15["b"], A15["y"], f15, m15, tr15, va15, [],
                     args.perms, "f",
                     tg_perm_fn(TG[r["axis"]].to_numpy(float), bank_tg, ptr_U15))
        rob_rows2.append({"axis": r["axis"], "own_trait": r["own_trait"],
                          "channel": r["channel"],
                          "delta_mae_min15": rr.get("delta_mae"),
                          "p_value_min15": rr.get("p_value")})
    if len(surv2):
        surv2 = surv2.merge(pd.DataFrame(rob_rows2),
                            on=["axis", "own_trait", "channel"], how="left")
    surv2.to_csv(OUT2 / "survivor_summary.csv", index=False)

    # ---- level 3: EB individual slopes on the two composites -------------
    named2_rows, l3_meta2 = [], {}
    if not args.skip_l3:
        print("[P2-L3] EB named-player pass on the two composites x 4 channels ...")
        traits4 = [mods_U[t] for t in MODS.OWN_TRAITS]
        for comp in ARCH.COMPOSITES:
            comp_rows = ARCH.axis_on_rows(ctx, TG, ptr_P, comp).to_numpy(float)[upos]
            for ch in CHANNELS:
                A = arr[ch]
                pat = f"{comp} [{ch}]"
                rows_i, meta = eb_level3(A["b"], A["y"], comp_rows, traits4, tr,
                                         fold_pos, dates_U, players_U, names)
                for x in rows_i:
                    x.update({"pattern": pat, "channel": ch,
                              "K_star": meta.get("K_star")})
                named2_rows += rows_i
                l3_meta2[pat] = meta
    nd2 = named_df(named2_rows)
    nd2.to_csv(OUT2 / "named_player_deviations.csv", index=False)
    write_quarantine(OUT2, ctx)

    runtime = time.time() - t0
    write_report1(res1, surv1, rob1, nd1, l3_meta1, chosen, args, ctx, runtime,
                  n_entries=len(battery))
    write_report2(res2, surv2, nd2, l3_meta2, args, ctx, runtime, TG)
    write_ledger(res1, res2, nd1, nd2)

    n_bh1 = int(res1["bh_pass"].sum())
    n_bh2 = int(res2["bh_pass"].sum())
    print(f"\n[done] P1: {len(res1)} tests, {n_bh1} BH-survivors "
          f"(expected false ~{FDR_Q * n_bh1:.1f}); "
          f"P2: {len(res2)} tests, {n_bh2} BH-survivors; "
          f"named P1={int(nd1['reported'].sum()) if len(nd1) else 0} "
          f"P2={int(nd2['reported'].sum()) if len(nd2) else 0}; "
          f"runtime {runtime:.0f}s")
    return 0


# ---------------------------------------------------------------------------
# report writers
# ---------------------------------------------------------------------------

def _histogram_line(pvals):
    hist, _ = np.histogram(pd.Series(pvals).dropna(), bins=np.arange(0, 1.05, 0.05))
    return " ".join(f"{int(h):>4}" for h in hist)


def write_report1(res, surv, rob, nd, l3_meta, chosen, args, ctx, runtime, n_entries):
    n = len(res)
    n_bh = int(res["bh_pass"].sum())
    n_p05 = int((res["p_value"] <= 0.05).sum())
    marq = res[res["registered_pairing"]]
    L = []
    A = L.append
    A("# player_feature_interactions_v1 — heterogeneity screening report")
    A("")
    A(f"*Generated by interactions_lab.py; runtime {runtime:.0f}s (shared pass "
      f"with player_vs_archetype_v1); {args.perms} permutations per test; "
      f"ridge lambda={FL.RIDGE_LAMBDA} on standardized inputs; baseline alphas "
      f"frozen {chosen}.*")
    A("")
    A("## Protocol (as registered; pinned decisions below)")
    A("")
    A("- Screening window 2021-2024 ONLY; quarantine asserted on every matrix "
      f"(`quarantine_audit.json`, all_pass={all(a['pass'] for a in ctx.audit)}, "
      f"{len(ctx.audit)} matrices).")
    A(f"- Battery: {n_entries} feature-channel entries (14 committed pooled-screen "
      "survivors + the 9-feature resurrection shortlist) x the closed 11-moderator "
      f"set = {n} tests. Statistic: 2024 MAE(ridge[b,f,m,fxm]) - MAE(ridge[b,f,m]).")
    A(f"- Null: {args.perms} within-season player-block permutations of the "
      "moderator assignment; BH at 10% across the full battery; level-3 EB "
      "named-player pass on BH survivors.")
    A("")
    A("## Pinned decisions (fixed before results were seen)")
    A("")
    for line in pinned_decisions_lines():
        A(line)
    A("")
    A("## Headline")
    A("")
    A(f"- **{n} tests**; p<=0.05 before correction: **{n_p05}** (global-null "
      f"expectation ~{0.05 * n:.1f}).")
    A(f"- **BH(10%) survivors: {n_bh}**; expected false among them: "
      f"~{FDR_Q * n_bh:.1f}.")
    A(f"- Registered mechanistic pairings tested: {len(marq)}; their best p: "
      f"{marq['p_value'].min() if len(marq) else float('nan')}.")
    A("")
    A("p-value histogram (bin 0.05):")
    A("")
    A("```")
    A(_histogram_line(res["p_value"]))
    A("```")
    A("")
    A("## Survivors")
    A("")
    if len(surv):
        A("| # | feature | moderator | ch | delta | p | q | beta_int | folds | min15 | battery |")
        A("|---|---|---|---|---|---|---|---|---|---|---|")
        for _, r in surv.iterrows():
            A(f"| {r['catalog_number']} | {r['feature']} | {r['moderator']} | "
              f"{r['channel']} | {r['delta_mae']:+.4f} | {r['p_value']:.4f} | "
              f"{r['q_value']:.4f} | {r['beta_interaction']:+.4f} | "
              f"{r['fold_signs']} | {r.get('delta_mae_min15', '')} | {r['battery']} |")
    else:
        A("**None.** No feature x trait interaction beat the no-interaction "
          "model plus multiplicity control on this window.")
    A("")
    A("## The resurrection shortlist verdict (marquee: B2B x age)")
    A("")
    A("| # | feature | moderator | ch | delta | p | q | survives |")
    A("|---|---|---|---|---|---|---|---|")
    rr = res[res["registered_pairing"]].sort_values("p_value")
    for _, r in rr.iterrows():
        A(f"| {r['catalog_number']} | {r['feature']} | {r['moderator']} | "
          f"{r['channel']} | {r['delta_mae']} | {r['p_value']} | "
          f"{r['q_value']:.4f} | {r['survives']} |")
    A("")
    A("## Level 3 — named-player deviations")
    A("")
    if len(nd):
        rep = nd[nd["reported"]]
        A(f"- Players evaluated: {len(nd)}; **reported (survive shrinkage AND "
          f"time-split replication): {len(rep)}**.")
        if len(rep):
            A("")
            A("| pattern | player | n | raw dev | shrunk dev | post z | halves |")
            A("|---|---|---|---|---|---|---|")
            for _, r in rep.iterrows():
                A(f"| {r['pattern']} | {r['player_name']} | {r['n_rows']} | "
                  f"{r['raw_dev_slope']:+.4f} | {r['shrunken_dev']:+.4f} | "
                  f"{r['posterior_z']:+.2f} | {r['half_signs']} |")
        for pat, meta in l3_meta.items():
            A(f"- `{pat}`: K*={meta.get('K_star')}, inner gain vs no-individual "
              f"= {meta.get('inner_gain_vs_no_individual')}")
    else:
        A("No BH survivors reached level 3 (or level 3 skipped in dev mode) — "
          "an empty named list is a legitimate result.")
    A("")
    A("## Files")
    A("")
    A("- `interaction_results.csv` — every test (statistic, p, q, survives)")
    A("- `survivor_summary.csv` — BH survivors + min15 robustness")
    A("- `named_player_deviations.csv` — full level-3 evidence per evaluated player")
    A("- `quarantine_audit.json` — per-matrix date audit")
    A("- `RANKED_TREND_LEDGER.md` — combined ranked ledger (charter amendment 4)")
    (OUT1 / "REPORT.md").write_text("\n".join(L), encoding="utf-8")


def write_report2(res, surv, nd, l3_meta, args, ctx, runtime, TG):
    n = len(res)
    n_bh = int(res["bh_pass"].sum())
    L = []
    A = L.append
    A("# player_vs_archetype_v1 — opponent-archetype screening report")
    A("")
    A(f"*Generated by interactions_lab.py (shared pass); {args.perms} "
      f"permutations per test; runtime {runtime:.0f}s total.*")
    A("")
    A("## Protocol (as registered)")
    A("")
    A("- Five opponent-archetype axes (rotation height last-10, own-3PA EWMA, "
      "blocks-per-paint-attempt-faced EWMA, steals-per-def-possession EWMA, "
      "pace EWMA — all shifted, alpha 0.10) + walk-forward-median composites "
      "TALL_SHOOTERS and SMALL_PRESSURE (features/archetypes.py).")
    A(f"- Level-2: own-trait x axis on mechanism channels ({n} tests); null = "
      f"{args.perms} within-season TEAM-block permutations of the archetype "
      "assignment; BH at 10% as its OWN family (separate from protocol 1).")
    A("- Level-3: EB individual slopes on the two composites x 4 channels, "
      "trait-predicted slope from [own height, rim share, 3PA rate, transition "
      "share]; same shrinkage machinery and time-split naming gates as "
      "protocol 1 (see its REPORT.md pinned decisions — shared).")
    A("")
    comp_rate = {c: float(TG[c].mean()) for c in ARCH.COMPOSITES}
    A(f"- Composite base rates over team-games (as-of, NaN excluded): "
      f"{ {k: round(v, 3) for k, v in comp_rate.items()} }.")
    A("")
    A("## Headline")
    A("")
    A(f"- **{n} tests**; BH(10%) survivors: **{n_bh}** (expected false "
      f"~{FDR_Q * n_bh:.1f}).")
    A("")
    A("p-value histogram (bin 0.05):")
    A("")
    A("```")
    A(_histogram_line(res["p_value"]))
    A("```")
    A("")
    A("## All level-2 tests")
    A("")
    A("| own trait | axis | ch | delta | p | q | beta_int | survives |")
    A("|---|---|---|---|---|---|---|---|")
    for _, r in res.iterrows():
        A(f"| {r['own_trait']} | {r['axis']} | {r['channel']} | "
          f"{r['delta_mae']} | {r['p_value']} | {r['q_value']:.4f} | "
          f"{r['beta_interaction']} | {r['survives']} |")
    A("")
    A("## Level 3 — individual responses to the composites (the John deliverable)")
    A("")
    if len(nd):
        rep = nd[nd["reported"]]
        A(f"- Players evaluated: {len(nd)}; **reported: {len(rep)}**.")
        if len(rep):
            A("")
            A("| composite [ch] | player | n | raw dev | shrunk dev | post z | halves |")
            A("|---|---|---|---|---|---|---|")
            for _, r in rep.iterrows():
                A(f"| {r['pattern']} | {r['player_name']} | {r['n_rows']} | "
                  f"{r['raw_dev_slope']:+.4f} | {r['shrunken_dev']:+.4f} | "
                  f"{r['posterior_z']:+.2f} | {r['half_signs']} |")
        else:
            A("- **No player passed both naming gates** — after honest "
              "shrinkage and replication, no credible individual archetype "
              "responder exists on this window. A legitimate result.")
        for pat, meta in l3_meta.items():
            A(f"- `{pat}`: K*={meta.get('K_star')}, inner gain vs no-individual "
              f"= {meta.get('inner_gain_vs_no_individual')}")
    else:
        A("Level 3 skipped (dev mode).")
    A("")
    A("## Files")
    A("")
    A("- `archetype_results.csv`, `survivor_summary.csv`, "
      "`named_player_deviations.csv`, `quarantine_audit.json`")
    (OUT2 / "REPORT.md").write_text("\n".join(L), encoding="utf-8")


def write_ledger(res1, res2, nd1, nd2):
    surv1 = res1[res1["survives"]].copy()
    surv2 = res2[res2["survives"]].copy()
    rows = []
    for _, r in surv1.iterrows():
        mech, anom = mechanism(r["catalog_number"], r["feature"],
                               r["moderator"], r["channel"])
        rows.append({"protocol": "interactions",
                     "pattern": f"#{r['catalog_number']} {r['feature']} x {r['moderator']}",
                     "channel": r["channel"], "delta": r["delta_mae"],
                     "q": r["q_value"], "mech": mech, "anom": anom})
    for _, r in surv2.iterrows():
        mech, anom = arch_mechanism(r["own_trait"], r["axis"], r["channel"])
        rows.append({"protocol": "archetypes",
                     "pattern": f"{r['own_trait']} x {r['axis']}",
                     "channel": r["channel"], "delta": r["delta_mae"],
                     "q": r["q_value"], "mech": mech, "anom": anom})
    rows.sort(key=lambda x: x["delta"])
    L = []
    A = L.append
    A("# RANKED TREND LEDGER — heterogeneity screens (DRAFT)")
    A("")
    A("*Charter amendment 4 deliverable: every surviving pattern ranked by "
      "effect, with a mechanism hypothesis and an anomaly flag where none "
      "exists. FLAGGED PATTERNS ARE KEPT — dropped only by blind-year or live "
      "failure, never for sounding strange. 'Makes sense' is commentary, not "
      "a gate. Blind-year value is PENDING for every row: the sealed "
      "2025-2026 walk-forward (player_feature_confirm_v1, the supreme court "
      "per amendment 1) has not been touched.*")
    A("")
    if rows:
        A("| rank | family | pattern | ch | 2024 MAE delta | q | mechanism hypothesis | anomaly | blind-year |")
        A("|---|---|---|---|---|---|---|---|---|")
        for i, r in enumerate(rows, 1):
            A(f"| {i} | {r['protocol']} | {r['pattern']} | {r['channel']} | "
              f"{r['delta']:+.4f} | {r['q']:.3f} | {r['mech']} | "
              f"{'**FLAGGED**' if r['anom'] else ''} | PENDING |")
    else:
        A("**No level-2 survivors in either family on this window.** The "
          "ledger is empty pending the next battery — an honest empty result, "
          "not a failure of the protocol.")
    A("")
    A("## Named-player deviations (level 3, gated)")
    A("")
    any_named = False
    for nd, fam in ((nd1, "interactions"), (nd2, "archetypes")):
        if len(nd):
            rep = nd[nd["reported"]]
            if len(rep):
                any_named = True
                for _, r in rep.iterrows():
                    A(f"- [{fam}] **{r['player_name']}** on {r['pattern']}: "
                      f"shrunk dev {r['shrunken_dev']:+.4f} (raw "
                      f"{r['raw_dev_slope']:+.4f}, n={r['n_rows']}, post z "
                      f"{r['posterior_z']:+.2f}, halves {r['half_signs']}) — "
                      f"blind-year PENDING")
    if not any_named:
        A("None passed both naming gates (shrinkage + time-split replication). "
          "Individual heterogeneity beyond the type level is not credibly "
          "estimable on this window — the honest reading, per the Clark case "
          "study.")
    A("")
    A("*Encoding bake-off note (charter amendment 2): every pattern above "
      "enters confirmation in three encodings — raw individual, shrunken "
      "individual (per-player dial), type-level only — head-to-head on the "
      "blind years; best blind performance ships.*")
    (OUT1 / "RANKED_TREND_LEDGER.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
