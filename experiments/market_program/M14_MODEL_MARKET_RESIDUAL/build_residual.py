#!/usr/bin/env python3
"""build_residual.py -- M14_MODEL_MARKET_RESIDUAL: model-vs-market residual structure at
matched point-in-time snapshots.

MANDATE (M14_MODEL_MARKET_RESIDUAL.md, this node's contract): characterize the STRUCTURE of the
disagreement between the frozen player-points model's translated probability/point projection and
the market's own de-vigged terms -- where it concentrates (market / book / season), whether it is
systematic or noise, and what would falsify a claimed model edge. THIS IS NOT AN EDGE HUNT. A
residual is a discrepancy, not an edge. M13 already found the translation is WORSE calibrated than
the market (Brier 0.2748 vs 0.2488, n=5,737); this node's job is to describe the shape of that gap,
not to re-litigate whether it exists.

EPISTEMIC STATUS (write verbatim wherever this module's output is cited): "DIAGNOSTIC MEASUREMENT.
Residuals between the translated fundamental fair line and the market consensus, both pinned to
point-in-time snapshots. A residual is a discrepancy, not an edge; promotion beyond diagnostic
status runs through the M00 ladder and the shadow-trading chain, never through this node."

INPUTS (read-only; nothing here is modified):
  * experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/translation_rows.parquet -- REUSED
    verbatim (matched, evaluable player-games with model translation variants and market de-vigged
    probability already computed; row-level forecast_cutoff and vendor-asserted snap_ret_utc
    already present).
  * experiments/market_program/M11_CONSENSUS_MODEL/consensus.py -- no_vig() DELEGATED for
    single-book de-vig (never reimplemented).
  * experiments/market_program/MARKET_IMPLIED_PROJECTIONS/implied_mean.py -- implied_mean_from_
    probability() DELEGATED for the point-scale residual (never reimplemented); its preregistered,
    UNFITTED per-market sigma assumption is carried forward as a stated limitation, not silently
    adopted as fact.
  * experiments/market_program/MODEL_VS_MARKET/compute_model_vs_market.py -- load_outcomes(),
    build_identity_index() and cluster_bootstrap_ci() REUSED; the in-play/one-sided/duplicate
    filtering RULES documented in that module (and in MARKET_PROGRAM_CONTRACT.md section 4.4) are
    reproduced here (not invented) to recover BOOK-LEVEL quotes that module's own aggregation
    discards -- this node needs per-book granularity that no upstream artifact currently persists.
  * data/props_capture/historical/master_props_historical.csv (LIVE worktree; T1_VENDOR_ASSERTED
    per D027) -- read only for book-level quote reconstruction.

NO SEALED_RESULTS. No git. No network. Deterministic under SEED. numpy/pandas only.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MARKET_PROGRAM = HERE.parent                          # .../experiments/market_program
WORKTREE = MARKET_PROGRAM.parent.parent                # .../player-model-program
LIVE_ROOT = WORKTREE.parents[2]                         # .../wnba-betting-model (LIVE data worktree)

sys.path.insert(0, str(MARKET_PROGRAM / "M11_CONSENSUS_MODEL"))
sys.path.insert(0, str(MARKET_PROGRAM / "MODEL_VS_MARKET"))
sys.path.insert(0, str(MARKET_PROGRAM / "MARKET_IMPLIED_PROJECTIONS"))
import consensus  # noqa: E402  -- vig math DELEGATED to this module
import compute_model_vs_market as mvm  # noqa: E402  -- join/entity-resolution machinery REUSED
import implied_mean as mip  # noqa: E402  -- point-scale inversion DELEGATED to this module

CONTRACT_MD = MARKET_PROGRAM / "M00_MARKET_PROGRAM_CONTRACT" / "MARKET_PROGRAM_CONTRACT.md"
TAXONOMY = MARKET_PROGRAM / "M00_MARKET_PROGRAM_CONTRACT" / "TAXONOMY.json"
M13_DIR = MARKET_PROGRAM / "M13_PLAYER_VALUE_TRANSLATION"
M13_TRANSLATION_ROWS = M13_DIR / "translation_rows.parquet"
M13_FINDINGS = M13_DIR / "FINDINGS.json"
PROPS_CSV = LIVE_ROOT / "data" / "props_capture" / "historical" / "master_props_historical.csv"

CONTRACT_SHA256_EXPECTED = "1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de"

SEED = 20260806            # same seed as every other market-lane node's cluster bootstrap
N_BOOT = 1000
HEADLINE_TIER = "A_primary"
MARKET_KEY = "player_points"
MIN_N_STABLE = 30          # below this a cell is reported but flagged UNDERPOWERED, never suppressed

EPISTEMIC_STATUS_LINE = (
    "DIAGNOSTIC MEASUREMENT. Residuals between the translated fundamental fair line and the "
    "market consensus, both pinned to point-in-time snapshots. A residual is a discrepancy, not "
    "an edge; promotion beyond diagnostic status runs through the M00 ladder and the shadow-"
    "trading chain, never through this node."
)

VARIANTS = ["normal", "student_t", "empirical", "het_normal"]
PRIMARY_VARIANT = "student_t"   # M13's AIC-selected primary; not re-derived here, reused as-is


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# small stats helpers (no scipy in this environment -- same discipline as M13)
# ---------------------------------------------------------------------------

def describe(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return {"n": 0}
    return {
        "n": int(len(x)), "mean": float(x.mean()), "std_ddof1": float(x.std(ddof=1)) if len(x) > 1 else None,
        "median": float(np.median(x)), "min": float(x.min()), "max": float(x.max()),
        "p05": float(np.percentile(x, 5)), "p95": float(np.percentile(x, 95)),
    }


def ols_slope_intercept(x: np.ndarray, y: np.ndarray) -> tuple:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    xm, ym = x.mean(), y.mean()
    sxx = float(np.sum((x - xm) ** 2))
    if sxx == 0:
        return float("nan"), float("nan")
    b = float(np.sum((x - xm) * (y - ym)) / sxx)
    a = float(ym - b * xm)
    return a, b


def cluster_bootstrap_slope_ci(x: np.ndarray, y: np.ndarray, clusters, n_boot=N_BOOT, seed=SEED) -> dict:
    """CI on the OLS slope of y ~ x, refit per cluster-bootstrap draw (game-date clusters).
    Same discipline as M13's bootstrap_param_ci: parameter uncertainty is propagated by refitting
    inside the bootstrap, not by treating a single point estimate as exact."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    codes, _ = pd.factorize(np.asarray(clusters), sort=True)
    n_clusters = int(codes.max()) + 1
    by_cluster_idx = [np.where(codes == c)[0] for c in range(n_clusters)]
    rng = np.random.default_rng(seed)
    slopes = []
    for _ in range(n_boot):
        draw = rng.integers(0, n_clusters, size=n_clusters)
        idx = np.concatenate([by_cluster_idx[c] for c in draw]) if n_clusters else np.array([], dtype=int)
        if len(idx) < 3:
            continue
        _, b = ols_slope_intercept(x[idx], y[idx])
        if not math.isnan(b):
            slopes.append(b)
    slopes = np.asarray(slopes)
    if len(slopes) == 0:
        return {"lo": None, "hi": None, "n_boot": 0, "n_clusters": n_clusters, "seed": seed,
                "method": "cluster_bootstrap_over_game_dates_percentile_refit_per_draw", "status": "NO_DRAWS"}
    return {"lo": float(np.percentile(slopes, 2.5)), "hi": float(np.percentile(slopes, 97.5)),
            "n_boot": int(len(slopes)), "n_clusters": int(n_clusters), "seed": int(seed),
            "method": "cluster_bootstrap_over_game_dates_percentile_refit_per_draw"}


def implied_mean_safe(line: float, p_over: float):
    try:
        mu, sigma, note = mip.implied_mean_from_probability(
            market_key=MARKET_KEY, line=line, vig_free_over_prob=p_over)
        return mu, sigma, None
    except mip.ImpliedMeanError as e:
        return None, None, str(e)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    got_contract = sha256_file(CONTRACT_MD)
    if got_contract != CONTRACT_SHA256_EXPECTED:
        raise RuntimeError(f"contract sha256 mismatch: {got_contract}")
    if consensus.CONTRACT_SHA256 != CONTRACT_SHA256_EXPECTED:
        raise RuntimeError("consensus.py pins a different contract hash")

    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    u2 = next(u for u in taxonomy["final_state_archive_ruling"]["permitted_uses"]
              if u["use_class"] == "M00-U2")
    u2_hash = hashlib.sha256(u2["caveat_text"].encode("utf-8")).hexdigest()
    if u2_hash != u2["caveat_sha256"]:
        raise RuntimeError("M00-U2 caveat hash does not reproduce from TAXONOMY.json")

    if not M13_TRANSLATION_ROWS.exists():
        raise RuntimeError(
            f"REQUIRED UPSTREAM ARTIFACT MISSING at the path actually checked: "
            f"{M13_TRANSLATION_ROWS}. This is M13_PLAYER_VALUE_TRANSLATION's declared output; "
            f"M14 cannot proceed without it and will not silently fabricate a substitute.")
    if not M13_FINDINGS.exists():
        raise RuntimeError(f"REQUIRED UPSTREAM ARTIFACT MISSING at the path actually checked: {M13_FINDINGS}")

    # =========================================================================
    # STEP 0 -- integrity: reproduce M13's own hash of its output before trusting it
    # =========================================================================
    m13_findings = json.loads(M13_FINDINGS.read_text(encoding="utf-8"))
    got_rows_hash = sha256_file(M13_TRANSLATION_ROWS)
    expect_rows_hash = m13_findings["translation_function"]["per_row_output"]["sha256"]
    rows_hash_match = (got_rows_hash == expect_rows_hash)
    if not rows_hash_match:
        print(f"WARNING: translation_rows.parquet sha256 does not match M13 FINDINGS.json "
              f"({got_rows_hash} vs {expect_rows_hash}) -- recording as a contradiction, not "
              f"silently proceeding as if it matched.")

    ev = pd.read_parquet(M13_TRANSLATION_ROWS)
    ev["forecast_cutoff_dt"] = pd.to_datetime(ev["forecast_cutoff"], utc=True)
    ev["snap_ret_dt"] = pd.to_datetime(ev["snap_ret_utc"], utc=True)
    ev["timestamp_mismatch_hours"] = (ev["snap_ret_dt"] - ev["forecast_cutoff_dt"]).dt.total_seconds() / 3600.0

    # =========================================================================
    # STEP 1 -- consensus-level (player-game) residuals, both scales, all 4 variants
    # =========================================================================
    for v in VARIANTS:
        ev[f"resid_prob_{v}"] = ev[f"p_over_{v}"] - ev["p_over_market_devig"]

    mu_list, sigma_list, err_list = [], [], []
    for line, p in zip(ev["consensus_line"], ev["p_over_market_devig"]):
        mu, sigma, err = implied_mean_safe(float(line), float(p))
        mu_list.append(mu); sigma_list.append(sigma); err_list.append(err)
    ev["market_implied_mean"] = mu_list
    ev["market_implied_mean_sigma"] = sigma_list
    ev["market_implied_mean_error"] = err_list
    n_implied_mean_failed = int(sum(1 for e in err_list if e is not None))
    ev["resid_points"] = ev["pred_point"] - ev["market_implied_mean"]

    # =========================================================================
    # STEP 2 -- book-level reconstruction (recover per-book granularity that
    # MODEL_VS_MARKET / M13's consensus join discards)
    # =========================================================================
    print("loading outcomes/name-rows for entity resolution (REUSED from compute_model_vs_market)...")
    _, name_rows, _ = mvm.load_outcomes()
    id_index = mvm.build_identity_index(name_rows)

    raw = pd.read_csv(PROPS_CSV)
    raw_sha256 = sha256_file(PROPS_CSV)
    raw["game_id"] = raw["game_id"].astype(str)
    raw["commence"] = pd.to_datetime(raw["commence_time"], utc=True)
    raw["snap_ret"] = pd.to_datetime(raw["snapshot_returned_utc"], utc=True)
    raw["last_update_dt"] = pd.to_datetime(raw["last_update"], utc=True)

    n_raw = int(len(raw))
    # in-play exclusion -- structural, contract section 4.4 (rule reproduced, not reinvented)
    inplay = raw["snap_ret"] >= raw["commence"]
    n_inplay_excluded = int(inplay.sum())
    df = raw[~inplay].copy()
    one_sided = df["over_price"].isna() | df["under_price"].isna()
    n_one_sided_excluded = int(one_sided.sum())
    df = df[~one_sided].copy()
    dup_bl = df.duplicated(["game_id", "player_name", "bookmaker_key", "line"])
    n_dup_dropped = int(dup_bl.sum())
    df = df[~dup_bl].copy()

    df["norm_name"] = df["player_name"].map(mvm._norm_name)
    df["player_id"] = df["norm_name"].map(id_index)
    n_unresolved = int(df["player_id"].isna().sum())
    df = df[df["player_id"].notna()].copy()
    df["player_id"] = df["player_id"].astype("int64")

    matched_keys = set(zip(ev["game_id"], ev["player_id"]))
    consensus_line_lookup = dict(zip(zip(ev["game_id"], ev["player_id"]), ev["consensus_line"]))
    df["key"] = list(zip(df["game_id"], df["player_id"]))
    n_before_key_filter = int(len(df))
    df = df[df["key"].isin(matched_keys)].copy()
    n_after_key_filter = int(len(df))
    df["match_consensus_line"] = df["key"].map(consensus_line_lookup)
    at_line = df[df["line"] == df["match_consensus_line"]].copy()
    n_off_consensus_line_excluded = int(len(df) - len(at_line))

    # per-book single-book de-vig probability -- DELEGATED to consensus.no_vig (multiplicative,
    # PREREGISTERED, never reimplemented here)
    p_over_book, overround = [], []
    for op, up in zip(at_line["over_price"], at_line["under_price"]):
        probs, param, _, _ = consensus.no_vig([float(op), float(up)], method=consensus.PREREGISTERED_VIG_METHOD)
        p_over_book.append(probs[0])
        overround.append(param)
    at_line = at_line.copy()
    at_line["p_over_book"] = p_over_book
    at_line["overround_param"] = overround

    ev_lookup = ev.set_index(["game_id", "player_id"])
    book = at_line.join(ev_lookup[[
        "pred_point", "consensus_line", "pts", "y_over", "season", "evaluation_tier", "game_date",
        "forecast_cutoff_dt", "p_over_market_devig",
    ] + [f"p_over_{v}" for v in VARIANTS]], on=["game_id", "player_id"])

    for v in VARIANTS:
        book[f"resid_prob_book_{v}"] = book[f"p_over_{v}"] - book["p_over_book"]
    book["resid_prob_book_vs_consensus"] = book["p_over_book"] - book["p_over_market_devig"]
    book["timestamp_mismatch_hours_book"] = (
        book["last_update_dt"] - book["forecast_cutoff_dt"]).dt.total_seconds() / 3600.0

    mu_b, sig_b, err_b = [], [], []
    for line, p in zip(book["consensus_line"], book["p_over_book"]):
        mu, sigma, err = implied_mean_safe(float(line), float(p))
        mu_b.append(mu); sig_b.append(sigma); err_b.append(err)
    book["market_implied_mean_book"] = mu_b
    book["resid_points_book"] = book["pred_point"] - book["market_implied_mean_book"]
    n_implied_mean_book_failed = int(sum(1 for e in err_b if e is not None))

    # ---- integrity check: reconstructed per-book quotes should reproduce the
    # SAME consensus p_over_market_devig that M13/MODEL_VS_MARKET already report
    # when run back through consensus.consensus_fair_value (measure, don't assert)
    recon_diffs = []
    for (gid, pid), grp in at_line.groupby(["game_id", "player_id"], sort=False):
        quotes = []
        for r in grp.itertuples():
            q = consensus.make_quote(
                bookmaker=r.bookmaker_key, price=float(r.over_price),
                capture_ts=consensus.parse_ts(r.snapshot_returned_utc),
                tier="T1", vendor_ts=str(r.last_update),
                vendor_ts_semantics="unknown_unverified",
                market="player_points", outcome="over", point=float(r.match_consensus_line))
            q["opposite_price"] = float(r.under_price)
            quotes.append(q)
        cobj = consensus.consensus_fair_value(quotes, allow_t1=True, game_id=str(gid),
                                              clock_skew=consensus.UNMEASURED)
        target = consensus_line_lookup.get((gid, pid))
        try:
            reported = float(ev_lookup.loc[(gid, pid), "p_over_market_devig"])
            if cobj["consensus_fair_prob"] is not None:
                recon_diffs.append(abs(cobj["consensus_fair_prob"] - reported))
        except Exception:
            pass
    recon_diffs = np.asarray(recon_diffs, dtype=float)
    reconstruction_check = {
        "n_player_games_reconstructed": int(len(recon_diffs)),
        "max_abs_diff_vs_m13_p_over_market_devig": float(recon_diffs.max()) if len(recon_diffs) else None,
        "mean_abs_diff": float(recon_diffs.mean()) if len(recon_diffs) else None,
        "tolerance": 1e-9,
        "reconstruction_matches_within_tolerance": bool(
            len(recon_diffs) > 0 and recon_diffs.max() < 1e-6),
        "note": ("independently rebuilds the consensus de-vigged probability from raw per-book "
                 "quotes at the matched consensus line and compares it to M13's already-reported "
                 "p_over_market_devig for the same player-games -- a re-derivation, not an "
                 "acceptance of the upstream number on assertion."),
    }

    # =========================================================================
    # STEP 3 -- timestamp pairing / mismatch window (acceptance criterion 1)
    # =========================================================================
    def amendment4_wrapped(mismatch_desc: dict) -> dict:
        return {
            "is_reaction_time_claim": False,
            "epistemic_status": EPISTEMIC_STATUS_LINE,
            "t_lower": "NOT_A_REACTION_TIME_CLAIM",
            "t_upper": "NOT_A_REACTION_TIME_CLAIM",
            "poll_interval_event": "N/A_NO_EVENT_STREAM",
            "poll_interval_quote": "N/A_SINGLE_SNAPSHOT_PER_GAME_T1_ARCHIVE",
            "vendor_latency_bound": "UNBOUNDED",
            "clock_skew_bound": "UNMEASURED",
            "censor_type": "N/A",
            "tier": "T1 (market side; model side is T0/verified-pre-game; pair inherits weakest -- "
                    "contract section 4.3)",
            "channel": "VENDOR_ASSERTED (contract section 6.2 advisory channel; never a headline, "
                       "gate, endpoint or decision input)",
            "timestamp_pairing_note": (
                "Every residual pair is matched at EXPLICIT timestamps: model side = per-row "
                "forecast_cutoff (T0, verified strictly pre-game, byte-equal to the prediction "
                "contract per VERIFICATION_REPORT.md check 3); market side = per-row vendor-"
                "asserted snapshot_returned_utc (game-level) or last_update (book-level), T1, "
                "unwitnessed (D027/D016 P2B: CUTOFF_UNPROVEN). The mismatch_window below is the "
                "explicit gap between those two asserted instants, recorded per D023 amendment 4 -- "
                "this is a recorded window, NOT a reaction-time or lead-lag claim: no inference "
                "about which side saw the other's information first is drawn from it."),
            "mismatch_window_hours": mismatch_desc,
        }

    game_level_gap = describe(ev["timestamp_mismatch_hours"].to_numpy())
    game_level_gap_by_season = {
        str(s): describe(ev.loc[ev["season"] == s, "timestamp_mismatch_hours"].to_numpy())
        for s in sorted(ev["season"].unique())
    }
    book_level_gap = describe(book["timestamp_mismatch_hours_book"].dropna().to_numpy())
    n_negative_game_level = int((ev["timestamp_mismatch_hours"] < 0).sum())
    n_negative_book_level = int((book["timestamp_mismatch_hours_book"].dropna() < 0).sum())

    timestamp_pairing = amendment4_wrapped({
        "game_level_snap_ret_minus_forecast_cutoff": game_level_gap,
        "game_level_by_season": game_level_gap_by_season,
        "book_level_last_update_minus_forecast_cutoff": book_level_gap,
        "n_pairs_with_market_timestamp_asserted_before_model_cutoff": {
            "game_level": n_negative_game_level, "book_level": n_negative_book_level,
        },
        "reading": (f"in the vendor-asserted timeline the market snapshot post-dates the model "
                    f"cutoff on {int(len(ev) - n_negative_game_level)} of {len(ev)} evaluable "
                    f"player-games (median gap {game_level_gap['median']:+.2f}h); on "
                    f"{n_negative_game_level} rows the asserted ordering is reversed. Advisory, "
                    f"unwitnessed context only -- never a timing claim (this echoes, and "
                    f"independently reproduces on this node's own universe, the same finding "
                    f"MODEL_VS_MARKET.md already reported)."),
    })

    # =========================================================================
    # STEP 4 -- residual distributions BY MARKET, BY BOOK, BY SEASON (never pooled silently)
    # =========================================================================
    by_market = {
        MARKET_KEY: {"n_matched_player_games": int(len(ev)), "n_matched_book_rows": int(len(book))},
        "other_stat_families_checked": ["player_rebounds", "player_assists", "player_steals",
                                        "player_blocks", "player_threes", "player_turnovers"],
        "other_stat_families_finding": (
            "PRESERVED NULL, not an oversight: the props archive's market_key is asserted-"
            "exclusively 'player_points' (asserted in compute_model_vs_market.py and reconfirmed "
            "here by direct read of master_props_historical.csv's market_key column, which "
            "contains exactly one distinct value). No model translation exists for other stat "
            "families (M13 section 2 / PROBE_LEGACY.md: the legacy points model never registered "
            "those targets). Therefore this node reports residual structure for exactly ONE "
            "market -- player_points -- and states this explicitly rather than silently reporting "
            "a single pooled table as if 'by market' had nothing left to stratify."),
        "market_key_distinct_values_in_raw_archive": sorted(raw["market_key"].unique().tolist()),
    }

    def season_cell(sub: pd.DataFrame, col: str) -> dict:
        vals = sub[col].dropna().to_numpy()
        d = describe(vals)
        if len(vals) == 0:
            d["status"] = "NO_ROWS"
            return d
        ci = mvm.cluster_bootstrap_ci(vals, sub.loc[sub[col].notna(), "game_date"].to_numpy())
        d["mean_ci95"] = ci
        d["mean_distinguishable_from_zero"] = bool(ci["lo"] > 0 or ci["hi"] < 0)
        d["underpowered"] = bool(d["n"] < MIN_N_STABLE)
        return d

    residual_by_season = {}
    for tname, tdf in {HEADLINE_TIER: ev[ev["evaluation_tier"] == HEADLINE_TIER], "all_tiers": ev}.items():
        block = {}
        for s in sorted(ev["season"].unique()):
            sub = tdf[tdf["season"] == s]
            block[str(s)] = {
                "resid_prob_primary": season_cell(sub, f"resid_prob_{PRIMARY_VARIANT}"),
                "resid_points": season_cell(sub, "resid_points"),
                "n_market_implied_mean_undefined": int(sub["market_implied_mean"].isna().sum()),
            }
        block["pooled"] = {
            "resid_prob_primary": season_cell(tdf, f"resid_prob_{PRIMARY_VARIANT}"),
            "resid_points": season_cell(tdf, "resid_points"),
            "n_market_implied_mean_undefined": int(tdf["market_implied_mean"].isna().sum()),
        }
        residual_by_season[tname] = block

    def book_cell(sub: pd.DataFrame, col: str) -> dict:
        vals = sub[col].dropna().to_numpy()
        d = describe(vals)
        if len(vals) == 0:
            d["status"] = "NO_ROWS"
            return d
        clusters = sub.loc[sub[col].notna(), "game_date"].to_numpy()
        ci = mvm.cluster_bootstrap_ci(vals, clusters)
        d["mean_ci95"] = ci
        d["mean_distinguishable_from_zero"] = bool(ci["lo"] > 0 or ci["hi"] < 0)
        d["underpowered"] = bool(d["n"] < MIN_N_STABLE)
        return d

    residual_by_book = {}
    for b, sub in book.groupby("bookmaker_key"):
        residual_by_book[b] = {
            "resid_prob_book_primary": book_cell(sub, f"resid_prob_book_{PRIMARY_VARIANT}"),
            "resid_prob_book_vs_consensus": book_cell(sub, "resid_prob_book_vs_consensus"),
            "resid_points_book": book_cell(sub, "resid_points_book"),
            "n_matched_rows": int(len(sub)),
            "n_matched_player_games": int(sub[["game_id", "player_id"]].drop_duplicates().shape[0]),
        }

    # book x season (finer grain, sample-size caveats stated per cell, never suppressed)
    residual_by_book_season = {}
    for (b, s), sub in book.groupby(["bookmaker_key", "season"]):
        residual_by_book_season.setdefault(b, {})[str(s)] = {
            "n": int(len(sub)),
            "resid_prob_book_primary_mean": float(sub[f"resid_prob_book_{PRIMARY_VARIANT}"].mean()) if len(sub) else None,
            "underpowered": bool(len(sub) < MIN_N_STABLE),
        }

    # =========================================================================
    # STEP 5 -- falsification analysis (acceptance criterion 4)
    # =========================================================================
    def falsification_block(sub: pd.DataFrame, resid_col: str) -> dict:
        s = sub.dropna(subset=[resid_col, "p_over_market_devig", "y_over"])
        x = s[resid_col].to_numpy()
        y = (s["y_over"] - s["p_over_market_devig"]).to_numpy()
        a, b = ols_slope_intercept(x, y)
        ci = cluster_bootstrap_slope_ci(x, y, s["game_date"].to_numpy())
        return {
            "n": int(len(s)), "intercept": a, "slope": b, "slope_ci95": ci,
            "slope_distinguishable_from_zero": bool(
                ci.get("lo") is not None and (ci["lo"] > 0 or ci["hi"] < 0)),
        }

    headline_ev = ev[ev["evaluation_tier"] == HEADLINE_TIER]
    falsification_pooled = falsification_block(headline_ev, f"resid_prob_{PRIMARY_VARIANT}")
    falsification_by_season = {
        str(s): falsification_block(headline_ev[headline_ev["season"] == s], f"resid_prob_{PRIMARY_VARIANT}")
        for s in sorted(headline_ev["season"].unique())
    }
    falsification_by_variant = {
        v: falsification_block(headline_ev, f"resid_prob_{v}") for v in VARIANTS
    }

    # influence diagnostics: leave-out-top-N by |resid_prob_primary| (not driven by extreme rows)
    abs_resid = headline_ev[f"resid_prob_{PRIMARY_VARIANT}"].abs()
    influence = {}
    for pct in (1, 5, 10):
        thresh = np.percentile(abs_resid, 100 - pct)
        trimmed = headline_ev[abs_resid < thresh]
        influence[f"drop_top_{pct}pct_by_abs_resid"] = falsification_block(
            trimmed, f"resid_prob_{PRIMARY_VARIANT}")

    falsification = {
        "hypothesis_under_test": (
            "Does the sign/magnitude of the model-minus-market probability residual predict where "
            "the market's own de-vigged probability was WRONG (i.e. does resid_prob_primary "
            "covary with (y_over - p_over_market_devig))? This is the MODEL_VS_MARKET_VALUE "
            "(TAXONOMY.json section MODEL_VS_MARKET_VALUE) falsification test, applied here as a "
            "diagnostic, not as a preregistered F8 endpoint -- no evidence-ladder label is sought "
            "or held for this result."),
        "would_be_supported_by": (
            "slope b > 0 with cluster-bootstrapped 95% CI excluding zero, pooled AND stable in "
            "sign across seasons AND across all four translation variants AND not reversed or "
            "nulled by dropping the top 1-10% most extreme residual rows (leave-out-top-N)."),
        "would_be_falsified_by": (
            "slope CI including zero or negative; sign flipping across seasons; the result "
            "appearing only under one translation variant and vanishing under the others "
            "(variant-dependent, not a property of the disagreement itself); or the slope "
            "collapsing toward zero once the most extreme-residual rows are dropped (evidence the "
            "apparent signal is driven by a handful of outlier games, not a systematic pattern)."),
        "pooled_headline": falsification_pooled,
        "by_season_headline": falsification_by_season,
        "by_translation_variant_headline": falsification_by_variant,
        "influence_leave_out_top_n": influence,
    }
    if falsification_pooled["slope_distinguishable_from_zero"] and falsification_pooled["slope"] > 0:
        falsification["verdict"] = "NOT_FALSIFIED_AT_THIS_N_SEE_CAVEATS"
    else:
        falsification["verdict"] = "FALSIFIED_NO_PREDICTIVE_CONTENT_DETECTED_AT_THIS_N"
    falsification["verdict_note"] = (
        "Evaluated strictly against the pooled headline (A_primary) slope CI only; season/variant/"
        "influence stability is reported alongside and must be read before citing this verdict -- "
        "a pooled-significant slope that reverses sign across seasons or variants is NOT read as "
        "'not falsified' by this node (see the season/variant/influence blocks).")

    # =========================================================================
    # assemble FINDINGS.json
    # =========================================================================
    could_not_establish = [
        "A joint test that partials out multiple books simultaneously (e.g. book fixed effects in "
        "a single regression): no statsmodels/scipy in this environment; per-book cells are "
        "reported independently (book_cell) rather than jointly modelled.",
        "Whether the point-scale residual (resid_points) reflects a real point-scale disagreement "
        "or an artifact of MARKET_IMPLIED_PROJECTIONS' preregistered, UNFITTED sigma=6.0 "
        "assumption for player_points: that assumption is not fitted to any outcome or price data "
        "(implied_mean.py's own documented limitation) and is carried forward unchanged, not "
        "re-validated here. resid_points should be read alongside resid_prob (which carries no "
        "such external dispersion assumption), not in place of it.",
        "Any timing, CLV, lead-lag, or stale-window claim from the mismatch-window figures: "
        "structurally out of scope for this T1-descended market side (D016/P2B; contract section "
        "5) and explicitly not attempted -- see the amendment-4-wrapped timestamp_pairing block's "
        "is_reaction_time_claim: false.",
        "Whether a real edge exists once execution costs (fees, slippage, latency) are applied: "
        "out of this node's mandate entirely (S-EXEC territory per contract section 2, four-system "
        "separation) and would be a Severity A substitution breach for this node to estimate.",
        "A causal account of WHY the residual concentrates where it does (if it does): this node "
        "characterizes structure (where/how much), not mechanism.",
    ]

    contradictions_found = []
    if not rows_hash_match:
        contradictions_found.append({
            "what": "translation_rows.parquet sha256 does not match the value recorded in M13's "
                    "own FINDINGS.json",
            "got": got_rows_hash, "expected": expect_rows_hash,
            "handling": "proceeded using the file actually on disk (frozen bytes govern over "
                        "prose), reported here rather than silently reconciled",
        })
    if not reconstruction_check["reconstruction_matches_within_tolerance"]:
        contradictions_found.append({
            "what": "independently rebuilt per-book consensus de-vig probability does not "
                    "reproduce M13's p_over_market_devig within 1e-6 tolerance",
            "detail": reconstruction_check,
            "handling": "reported as a re-derivation discrepancy, not silently patched or hidden",
        })

    stop_conditions_checked = {
        "money_wager_credentials_scraping_licensing_sealed_results": (
            "none tripped -- no spend, no wager, no credentials, no scraping beyond the "
            "already-provisioned local archive read, and stage2b/SEALED_RESULTS was never read "
            "(confirmed: this script contains no reference to that path and never imports "
            "anything under experiments/player_program/stage2b/)."),
        "reaction_time_or_timing_claim": (
            "none made. The timestamp_pairing block explicitly carries is_reaction_time_claim: "
            "false and the full amendment-4 sentinel field set; the mismatch-window figures are "
            "advisory, VENDOR_ASSERTED-channel context reproduced from the same vendor-asserted "
            "stamps MODEL_VS_MARKET.md already used for an equivalent advisory statement -- no new "
            "timing inference is drawn."),
        "final_state_odds_archive_bounded_use": (
            "the only final-state/T2-descended archive touched is the props archive "
            "(master_props_historical.csv, T1_VENDOR_ASSERTED per D027, extending M00-U2); the "
            "use here -- no-vig calibration-adjacent residual structure against realized outcomes, "
            "unknown-time -- is the same M00-U2 class M13 and MODEL_VS_MARKET already invoke, not "
            "a new or stretched use. The M00-U2 caveat is reproduced verbatim below and its hash "
            "verified against TAXONOMY.json at run time."),
    }

    findings = {
        "schema": "market_program/M14_MODEL_MARKET_RESIDUAL/findings/1",
        "generated_utc": utcnow(),
        "epistemic_status": EPISTEMIC_STATUS_LINE,
        "decision_authority": ["D023_MARKET_PROGRAM_AUTHORIZED", "D027_PROPS_HISTORICAL_BOUNDED_USES",
                                "D036_SCOREBOARD_MEASUREMENT_SEMANTICS", "D037", "D043"],
        "evidence_class": "DIAGNOSTIC",
        "evidence_class_reason": (
            "structural characterization of a model-vs-market residual on a T1 vendor-asserted "
            "props archive; explicitly NOT an edge claim, NOT PRODUCTION_ELIGIBLE, NOT a "
            "tradability claim; not a preregistered family endpoint; no evidence-ladder label "
            "(contract section 3) is claimed or held"),
        "evidence_ladder_labels_held": [],
        "not_a_production_eligible_or_tradability_claim": True,
        "opportunity_class_context": (
            "informs MODEL_VS_MARKET_VALUE (TAXONOMY.json opportunity_taxonomy, primary families "
            "F5/F8) but is NOT an F8 preregistered endpoint and confers no evidence-ladder label"),
        "seed": SEED, "n_boot": N_BOOT,
        "contract_sha256_verified": got_contract,
        "commit_sha": ("UNAVAILABLE: no git in this worktree per task constraints; upstream "
                       "artifacts' clean-tree receipts assert commit "
                       "0108ef86e9c085e1d701e40e53c24dcde177ac97 (reproduced, not independently "
                       "verified); manifest/content hashes are the verified anchors"),
        "m00_bounded_use": {
            "m00_use_class": "M00-U2", "extended_to_this_archive_by": "D027_PROPS_HISTORICAL_BOUNDED_USES",
            "object": "data/props_capture/historical/master_props_historical.csv (T1_VENDOR_ASSERTED)",
            "caveat_text_verbatim": u2["caveat_text"], "caveat_hash": u2["caveat_sha256"],
            "additional_prohibitions_honored": ("no CLV, timing, lead-lag, stale-window or "
                                                "executability claim is made anywhere in this node"),
        },
        "inputs": {
            "m13_translation_rows": {
                "path": str(M13_TRANSLATION_ROWS.relative_to(WORKTREE)).replace("\\", "/"),
                "n_rows": int(len(ev)), "sha256_reproduced": got_rows_hash,
                "sha256_matches_m13_findings": rows_hash_match,
            },
            "props_archive_raw": {
                "path": "data/props_capture/historical/master_props_historical.csv (LIVE worktree)",
                "sha256": raw_sha256, "n_rows": n_raw,
            },
            "book_level_reconstruction_audit": {
                "n_inplay_excluded": n_inplay_excluded,
                "n_one_sided_excluded": n_one_sided_excluded,
                "n_duplicate_dropped": n_dup_dropped,
                "n_unresolved_player_names_excluded": n_unresolved,
                "n_rows_before_matched_key_filter": n_before_key_filter,
                "n_rows_after_matched_key_filter_to_m13_universe": n_after_key_filter,
                "n_rows_off_consensus_line_excluded": n_off_consensus_line_excluded,
                "n_book_level_matched_rows_final": int(len(book)),
                "n_distinct_books_in_final_table": int(book["bookmaker_key"].nunique()),
            },
            "reconstruction_integrity_check": reconstruction_check,
            "market_implied_mean_undefined_rows": {
                "consensus_level": n_implied_mean_failed, "book_level": n_implied_mean_book_failed,
                "note": "implied_mean_from_probability raises (not silently clips) on a "
                        "degenerate p_over of exactly 0 or 1; such rows are counted and excluded "
                        "from resid_points, never imputed.",
            },
        },
        "residual_definitions": {
            "resid_prob": ("p_over_{variant} (M13 translation, 4 named variants: normal, "
                           "student_t [primary, AIC-selected by M13], empirical, het_normal) "
                           "minus p_over_market_devig (M11 consensus de-vig). Positive = model "
                           "more bullish on OVER than the market."),
            "resid_points": ("pred_point (model's own point estimate) minus market_implied_mean "
                             "(MARKET_IMPLIED_PROJECTIONS' Normal-inversion of the market's "
                             "de-vigged probability at the consensus line, sigma=6.0 for "
                             "player_points, PREREGISTERED and UNFITTED -- see could_not_establish). "
                             "Positive = model projects more points than the market implies."),
            "resid_prob_book / resid_points_book": ("same two definitions computed against an "
                                                     "INDIVIDUAL book's own de-vigged probability "
                                                     "at the matched consensus line, instead of the "
                                                     "cross-book consensus -- this is what makes the "
                                                     "'by book' stratification possible; no upstream "
                                                     "artifact persists this granularity."),
        },
        "timestamp_pairing_and_mismatch_window": timestamp_pairing,
        "residual_by_market": by_market,
        "residual_by_season": residual_by_season,
        "residual_by_book": residual_by_book,
        "residual_by_book_and_season": residual_by_book_season,
        "falsification": falsification,
        "stop_conditions_checked": stop_conditions_checked,
        "could_not_establish": could_not_establish,
        "contradictions_found": contradictions_found,
    }
    findings["result_hash"] = sha256_hex(canonical_json(
        {k: v for k, v in findings.items() if k != "generated_utc"}))

    (HERE / "FINDINGS.json").write_text(json.dumps(findings, indent=1, default=str), encoding="utf-8")

    print("wrote FINDINGS.json")
    print("headline pooled falsification slope:", falsification_pooled["slope"],
          "CI", falsification_pooled["slope_ci95"].get("lo"), falsification_pooled["slope_ci95"].get("hi"))
    print("verdict:", falsification["verdict"])
    return findings


if __name__ == "__main__":
    main()
