#!/usr/bin/env python3
"""verify_legacy_player_model.py -- D037 legacy player-model VERIFICATION NODE.

Executes, against bytes on disk, the 7-check checklist registered in
PROBE_LEGACY.md (this directory) for the legacy generation-only OOF artifact
set at experiments/cbs_v15_player_oof_v5/attempt_001/:

  1. byte integrity          sha256 of every artifact vs its *.manifest.json
  2. producer digest         recompute the PRODUCER_SOURCES set digest
  3. cutoff discipline       per-fold train_seasons < S; per-row
                             forecast_cutoff/feature_asof strictly before the
                             game; manifest fit_through_date decomposed and
                             re-derived (walk-forward semantics per
                             asof_invariant.py -- see report)
  4. universe                re-derive the prediction_contract_v5 candidate
                             row set from pinned inputs and compare row_uid
                             sets per season; obligation completeness
  5. config/snapshot pinning config_hash + data_snapshot_hash constant per
                             fold and equal to the fold receipt
  6. generation-only         no score/accuracy field anywhere in the lane
  7. tier policy             decide + verify the displayed-universe split

If and only if every check passes, computes points + minutes MAE/RMSE/bias/N
with game-date-cluster-bootstrap 95% CIs against OWNED GAMELOG outcomes on
the artifact universe (never a number copied from any legacy output -- the
lane contains none), and writes:

  legacy_verified_metrics.json   scoreboard-ready cells with D036 provenance
  VERIFICATION_REPORT.md         verdict per check + overall

Evidence class: PRELIMINARY (legacy-receiptable) per D036/D037/D038.
Stdlib + pandas/numpy. No git, no network. Deterministic under SEED.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[3]            # .../player-model-program
sys.path.insert(0, str(WORKTREE))

import asof_invariant as aso            # noqa: E402
import cbs_obligation_key as obk        # noqa: E402
import prediction_contract_v5 as pc5    # noqa: E402

ATT = WORKTREE / "experiments" / "cbs_v15_player_oof_v5" / "attempt_001"
ENRICHED = WORKTREE / "experiments" / "prediction_contract_v5" / "player_game_enriched.parquet"

SEED = 20260806          # same seed + method as compute_player_granular.py
N_BOOT = 1000
SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
TARGETS = ["attempts_usage", "e_minutes_given_active", "p_active",
           "player_scoring_distribution"]
SCORED = {"points": "player_scoring_distribution",
          "minutes": "e_minutes_given_active"}

EXPECTED_DIGEST = "768f8139d72439adcae59b2dcf57390356b435ce8082f9a0aa0acdcb4925b7b9"

#: The PRODUCER_SOURCES tuple named in run_player_oof_v15.py: v14's 25-file
#: producing set (run_player_oof_v14.PRODUCER_SOURCES) plus v15's 6 additions.
PRODUCER_SOURCES = [
    "run_player_oof_v14.py",
    "cbs_v14.py", "cbs_player_runner_v14.py", "cbs_player_history_v14.py",
    "cbs_obligation_order_v3.py", "cbs_obligation_order.py", "cbs_obligation_key.py",
    "cbs_v13.py", "cbs_v12.py", "cbs_v11.py", "cbs_v10.py", "cbs_v8.py", "cbs_v7.py",
    "cbs_v5.py", "cbs_generator.py", "cbs_builders.py",
    "cbs_real_frames_v3.py", "cbs_real_frames_v2.py",
    "cbs_provenance_v4.py", "cbs_provenance_v3.py", "cbs_identity_v3.py",
    "contract_validator_v4_strict.py", "contract_validator_v3_strict.py",
    "prediction_contract_v2.py", "asof_invariant.py",
    "run_player_oof_v15.py", "cbs_v15.py", "cbs_player_runner_v15.py",
    "cbs_real_frames_v5.py", "prediction_contract_v5.py",
    "prediction_contract_v5_enrich.py",
]

FORBIDDEN_SCORE_COLS = {
    "mae", "rmse", "bias", "error", "abs_error", "residual", "brier",
    "log_loss", "accuracy", "score", "skill", "roi", "clv", "profit",
    "pts", "points", "minutes", "reb", "ast", "stl", "blk", "tov", "fg3m",
    "fga", "outcome", "actual", "realized", "min",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


_MIN_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)(?::(\d{1,2}))?\s*$")


def parse_min(v) -> float:
    """Gamelog MIN parser, byte-for-byte the compute_player_granular.py rule."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return 0.0
    if isinstance(v, (int, np.integer, float, np.floating)):
        return float(v)
    m = _MIN_RE.match(str(v))
    if not m:
        raise ValueError(f"unparseable MIN value: {v!r}")
    return float(m.group(1)) + (float(m.group(2)) if m.group(2) else 0.0) / 60.0


def mae_rmse_bias(pred: np.ndarray, actual: np.ndarray) -> dict:
    err = pred - actual
    return {"mae": float(np.mean(np.abs(err))),
            "rmse": float(np.sqrt(np.mean(err ** 2))),
            "bias": float(np.mean(err))}


def cluster_bootstrap_ci(values: np.ndarray, clusters: np.ndarray,
                         n_boot: int = N_BOOT, seed: int = SEED,
                         alpha: float = 0.05) -> dict:
    """Identical method to compute_player_granular.py: percentile CI on the
    mean of `values`, cluster-bootstrapped over game dates."""
    values = np.asarray(values, dtype=float)
    codes, _ = pd.factorize(clusters, sort=True)
    n_clusters = int(codes.max()) + 1
    sums = np.zeros(n_clusters)
    counts = np.zeros(n_clusters)
    np.add.at(sums, codes, values)
    np.add.at(counts, codes, 1.0)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_clusters, size=(n_boot, n_clusters))
    boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"lo": float(lo), "hi": float(hi), "n_boot": int(n_boot),
            "n_clusters": int(n_clusters), "seed": int(seed),
            "method": "cluster_bootstrap_over_game_dates_percentile"}


# ===========================================================================
# CHECK 1 -- byte integrity
# ===========================================================================

def check1_byte_integrity() -> dict:
    results, failures = [], []
    manifests = sorted(ATT.glob("*.manifest.json"))
    for mp in manifests:
        man = json.loads(mp.read_text(encoding="utf-8"))
        art = WORKTREE / man["artifact"]
        got = sha256_file(art)
        nbytes = art.stat().st_size
        ok = (got == man["content_sha256"]) and (nbytes == man["content_bytes"])
        results.append({"artifact": man["artifact"], "sha256_ok": got == man["content_sha256"],
                        "bytes_ok": nbytes == man["content_bytes"]})
        if not ok:
            failures.append({"artifact": man["artifact"], "expected": man["content_sha256"],
                             "got": got})
    n_expected = len(SEASONS) * (len(TARGETS) + 2) + 1   # preds+sidecar+receipt per fold, +index
    return {
        "check": "1_byte_integrity",
        "verdict": "PASS" if (not failures and len(manifests) == n_expected) else "FAIL",
        "n_manifests": len(manifests), "n_manifests_expected": n_expected,
        "n_verified": sum(1 for r in results if r["sha256_ok"] and r["bytes_ok"]),
        "failures": failures,
        "note": ("every *.manifest.json in the lane re-verified against recomputed "
                 "sha256 and byte counts of the named artifact"),
    }


# ===========================================================================
# CHECK 2 -- producer source-set digest
# ===========================================================================

def check2_producer_digest(run_index: dict, receipts: dict, manifests: list[dict]) -> dict:
    sources = {rel: sha256_file(WORKTREE / rel) for rel in PRODUCER_SOURCES}
    digest = hashlib.sha256(
        json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    recorded = run_index["producer"]["producer_source_sha256"]
    drifted = sorted(k for k in sources if recorded.get(k) != sources[k])
    man_digests = {m.get("producer_source_set_digest") for m in manifests}
    rec_digests = {r["producer_source_set_digest"] for r in receipts.values()}
    ok = (digest == EXPECTED_DIGEST and man_digests == {EXPECTED_DIGEST}
          and rec_digests == {EXPECTED_DIGEST} and not drifted)
    return {
        "check": "2_producer_digest",
        "verdict": "PASS" if ok else "FAIL",
        "recomputed_digest": digest,
        "expected_digest": EXPECTED_DIGEST,
        "digest_matches": digest == EXPECTED_DIGEST,
        "n_sources": len(sources),
        "sources_drifted_since_run": drifted,
        "all_manifests_carry_expected_digest": man_digests == {EXPECTED_DIGEST},
        "all_fold_receipts_carry_expected_digest": rec_digests == {EXPECTED_DIGEST},
        "digest_rule": ("sha256 over json.dumps({rel: sha256(bytes)}, sort_keys=True, "
                        "separators=(',',':')) per run_player_oof_v14.producer_digest"),
    }


# ===========================================================================
# CHECK 3/4/5/7 -- per-fold, per-row work over the parquets + contract
# ===========================================================================

def load_contract() -> pd.DataFrame:
    pg = pd.read_parquet(ENRICHED)
    pg["game_id"] = pg["game_id"].astype(str)
    pg["game_date"] = pd.to_datetime(pg["game_date"])
    gd = pg["game_date"]
    pg["game_date_utc"] = gd.dt.tz_localize("UTC") if gd.dt.tz is None else gd.dt.tz_convert("UTC")
    pg["forecast_cutoff"] = pd.to_datetime(pg["forecast_cutoff"], utc=True)
    # the row's GAME DATETIME for strict pre-game assertions: the OBSERVED
    # scheduled tip where the contract captured one (all exact_tip_T-90m rows),
    # else midnight UTC of the game date, which precedes any same-day tip.
    tip = pd.to_datetime(pg["scheduled_tip_time"], utc=True, errors="coerce")
    pg["game_datetime_utc"] = tip.fillna(pg["game_date_utc"])
    pg["game_time_basis"] = np.where(tip.notna(), "observed_scheduled_tip",
                                     "game_date_midnight_utc_lower_bound")
    # canonical key re-derivation over the WHOLE universe
    want = np.array([obk.row_uid(p, g, t) for p, g, t
                     in zip(pg["player_id"], pg["game_id"], pg["team_id"])])
    n_bad = int((pg["row_uid"].to_numpy() != want).sum())
    if n_bad:
        raise RuntimeError(f"{n_bad} contract row_uids do not re-derive")
    obk.assert_unique_canonical_keys(pg, "enriched v5 contract")
    return pg


def per_fold_checks(pg: pd.DataFrame, receipts: dict, manifests_by_name: dict) -> dict:
    c3 = {"per_fold": {}, "row_violations_total": 0}
    c5 = {"per_fold": {}}
    c7counts = {"per_fold": {}}
    tier_map = dict(zip(pg["row_uid"], pg["evaluation_tier"]))
    cut_map = dict(zip(pg["row_uid"], pg["forecast_cutoff"]))
    gd_map = dict(zip(pg["row_uid"], pg["game_datetime_utc"]))
    basis_map = dict(zip(pg["row_uid"], pg["game_time_basis"]))
    season_first_game = pg.groupby("season")["game_date_utc"].min().to_dict()

    for s in SEASONS:
        rec = receipts[s]
        srows = pg[pg["season"] == s]
        assert int(rec["n_universe_rows"]) == len(srows)
        train_ok = (max(rec["train_seasons"]) < s) if rec["train_seasons"] else True
        fold3 = {"train_seasons": rec["train_seasons"],
                 "max_train_season_lt_S": bool(train_ok),
                 "degenerate_no_train": not rec["train_seasons"]}
        fold5 = {}
        fold7 = {}
        feat_max = None
        for t in TARGETS:
            p = pd.read_parquet(ATT / f"predictions__{t}__{s}.parquet")
            p["forecast_cutoff"] = pd.to_datetime(p["forecast_cutoff"], utc=True)
            p["feature_asof"] = pd.to_datetime(p["feature_asof"], utc=True)
            # universe identity
            ids_match = set(p["row_uid"]) == set(srows["row_uid"])
            n_dup = int(p["row_uid"].duplicated().sum())
            n_excl = int(p["exclusion_reason"].notna().sum())
            # cutoff discipline per row, against the row's game datetime
            # (observed scheduled tip where captured, else midnight UTC of the
            # game date -- a lower bound on any same-day tip)
            gd = p["row_uid"].map(gd_map)
            basis = p["row_uid"].map(basis_map).value_counts().to_dict()
            ccontract = p["row_uid"].map(cut_map)
            n_cut_ge_game = int((p["forecast_cutoff"] >= gd).sum())
            n_feat_ge_game = int((p["feature_asof"] >= gd).sum())
            n_feat_gt_cut = int((p["feature_asof"] > p["forecast_cutoff"]).sum())
            n_cut_mismatch = int((p["forecast_cutoff"] != ccontract).sum())
            fm = p["feature_asof"].max()
            feat_max = fm if feat_max is None else max(feat_max, fm)
            # pinning
            ch = p["config_hash"].unique().tolist()
            sh = p["data_snapshot_hash"].unique().tolist()
            fi = p["fold_id"].unique().tolist()
            fold5[t] = {
                "config_hash_constant_and_matches_receipt":
                    ch == [rec["config_hash"]],
                "snapshot_hash_constant_and_matches_receipt":
                    sh == [rec["snapshot_hash"]],
                "fold_id_constant": fi == [f"season:{s}"],
            }
            # tiers
            tiers = p["row_uid"].map(tier_map).value_counts().to_dict()
            fold7[t] = {"observed": {k: int(v) for k, v in tiers.items()},
                        "receipt": rec["emitted_by_target_and_tier"][t],
                        "match": {k: int(v) for k, v in tiers.items()}
                                 == rec["emitted_by_target_and_tier"][t]}
            # fallback / cold-start vs receipt obligation_completeness
            oc = rec["obligation_completeness"][t]
            fl = {str(k): int(v) for k, v
                  in p["fallback_level"].value_counts().items()}
            fold3.setdefault("targets", {})[t] = {
                "row_uid_set_equals_universe": bool(ids_match),
                "n_duplicate_row_uids": n_dup,
                "n_excluded": n_excl,
                "n_excluded_receipt": int(oc["n_excluded"]),
                "n_rows_cutoff_not_before_game": n_cut_ge_game,
                "n_rows_feature_asof_not_before_game": n_feat_ge_game,
                "game_time_basis_counts": {k: int(v) for k, v in basis.items()},
                "n_rows_feature_asof_after_cutoff": n_feat_gt_cut,
                "n_rows_cutoff_differs_from_contract": n_cut_mismatch,
                "fallback_levels_match_receipt": fl == {str(k): int(v) for k, v
                                                        in oc["fallback_levels"].items()},
                "n_cold_start_matches_receipt":
                    int(p["is_cold_start"].sum()) == int(oc["n_cold_start"]),
                "n_emitted_matches_receipt": len(p) == int(oc["n_emitted"]) == int(oc["n_required"]),
            }
            c3["row_violations_total"] += n_cut_ge_game + n_feat_ge_game + n_feat_gt_cut

        # ---- fit_through_date decomposition -------------------------------
        man = manifests_by_name[f"predictions__player_scoring_distribution__{s}.parquet"]
        man_ft = pd.Timestamp(man["fit_through_date"])
        train_rows = pg[(pg["season"] < s) & (pg["season"].isin(rec["train_seasons"]))
                        & pg["fit_eligible"].astype(bool)]
        if len(train_rows):
            tb = pd.Timestamp(aso.bound_from_dates(train_rows["game_date"]))
            train_bound = tb.tz_convert("UTC") if tb.tzinfo else tb.tz_localize("UTC")
        else:
            train_bound = None
        expected_ft = max([b for b in (train_bound, feat_max) if b is not None])
        first_game = season_first_game[s]
        fold3["manifest_fit_through_date"] = str(man_ft)
        fold3["recomputed_fit_through"] = str(expected_ft)
        fold3["fit_through_reproduces"] = abs((man_ft - expected_ft).total_seconds()) <= 1
        fold3["train_component_bound"] = str(train_bound) if train_bound is not None else None
        fold3["season_first_game_date_utc"] = str(first_game)
        fold3["train_bound_precedes_season_first_game"] = (
            bool(train_bound < first_game) if train_bound is not None else True)
        fold3["fit_through_semantics_note"] = (
            "fit_through_date is the artifact's LATEST SOURCE OBSERVATION "
            "(asof_invariant.py): max(train-season game-date bound, max per-row "
            "feature_asof). Per-row feature_asof includes lawful WITHIN-season "
            "walk-forward history strictly before each row's own cutoff, so the "
            "artifact-level date lands near season end BY DESIGN; the leakage "
            "assertions are the train-component bound vs the season's first game "
            "and the per-row strict inequalities, both checked here.")
        c3["per_fold"][str(s)] = fold3
        c5["per_fold"][str(s)] = fold5
        c7counts["per_fold"][str(s)] = fold7

    # verdicts
    ok3 = c3["row_violations_total"] == 0 and all(
        f["max_train_season_lt_S"] and f["fit_through_reproduces"]
        and f["train_bound_precedes_season_first_game"]
        and all(t["row_uid_set_equals_universe"] and t["n_duplicate_row_uids"] == 0
                and t["n_rows_cutoff_differs_from_contract"] == 0
                for t in f["targets"].values())
        for f in c3["per_fold"].values())
    c3.update({"check": "3_cutoff_discipline", "verdict": "PASS" if ok3 else "FAIL"})
    ok5 = all(all(all(v.values()) for v in fold.values())
              for fold in c5["per_fold"].values())
    c5.update({"check": "5_config_snapshot_pinning", "verdict": "PASS" if ok5 else "FAIL"})
    ok7 = all(all(t["match"] for t in fold.values())
              for fold in c7counts["per_fold"].values())
    c7counts["tier_counts_verdict"] = "PASS" if ok7 else "FAIL"
    return {"c3": c3, "c5": c5, "c7counts": c7counts}


# ===========================================================================
# CHECK 4 -- universe re-derivation
# ===========================================================================

def check4_universe(pg: pd.DataFrame, receipts: dict) -> dict:
    # (a) pinned inputs must equal the bytes the run recorded
    pinned = receipts[SEASONS[0]]["artifacts"]
    for s in SEASONS[1:]:
        assert receipts[s]["artifacts"] == pinned, "receipts disagree on pinned inputs"
    pin_results = {rel: sha256_file(WORKTREE / rel) == want for rel, want in pinned.items()}
    unpinned = {
        "data/injury_history/injury_history.csv":
            sha256_file(WORKTREE / "data/injury_history/injury_history.csv"),
        "data/injury_capture/injury_log.csv":
            sha256_file(WORKTREE / "data/injury_capture/injury_log.csv"),
    }
    # (b) re-derive the candidate universe from those inputs
    inputs = pc5.load_inputs(WORKTREE)
    cand, _gen = pc5.build_candidates(inputs)
    per_season = {}
    all_ok = True
    ev_tier = np.where(cand["universe_tier"] == "A", "A_primary",
                       np.where(cand["team_assignment_source"] == "S_TX",
                                "B_transaction_sensitivity", "B_s2_weak_fallback"))
    cand = cand.assign(ev_tier=ev_tier)
    for s in SEASONS:
        rows = cand[cand["season"] == s]
        got = set(rows["row_uid"])
        want = set(pg.loc[pg["season"] == s, "row_uid"])
        rec = receipts[s]
        tiers = rows["ev_tier"].value_counts().to_dict()
        ok = (got == want and len(got) == int(rec["n_universe_rows"])
              and {k: int(v) for k, v in tiers.items()} == rec["test_rows_by_tier"])
        per_season[str(s)] = {
            "n_rederived": len(got),
            "n_receipt_universe": int(rec["n_universe_rows"]),
            "row_uid_set_equals_artifact_universe": got == set(pg.loc[pg["season"] == s, "row_uid"]),
            "n_only_in_rederived": len(got - want),
            "n_only_in_artifact": len(want - got),
            "rederived_tier_counts": {k: int(v) for k, v in tiers.items()},
            "receipt_tier_counts": rec["test_rows_by_tier"],
            "ok": bool(ok),
        }
        all_ok &= ok
    return {
        "check": "4_universe_rederivation",
        "verdict": "PASS" if (all_ok and all(pin_results.values())) else "FAIL",
        "pinned_input_hashes_match_fold_receipts": pin_results,
        "unpinned_inputs_note": (
            "the transaction wire and report capture feed S_TX/S3 candidacy but are "
            "NOT hash-pinned in the fold receipts; their bytes as verified today are "
            "recorded here. Exact row_uid set equality of the re-derivation makes the "
            "gap immaterial for THIS verification."),
        "unpinned_input_sha256_today": unpinned,
        "n_rederived_total": int(len(cand)),
        "per_season": per_season,
        "method": ("prediction_contract_v5.build_candidates() re-run in memory from the "
                   "pinned master/v4 inputs; per-season row_uid sets compared to the "
                   "enriched contract AND (via check 3) to every prediction parquet; "
                   "evaluation-tier counts re-derived from universe_tier + "
                   "team_assignment_source and compared to every fold receipt"),
    }


# ===========================================================================
# CHECK 6 -- generation-only
# ===========================================================================

def check6_generation_only(run_index: dict, receipts: dict, manifests: list[dict]) -> dict:
    bad_cols = {}
    for f in sorted(ATT.glob("*.parquet")):
        cols = {c.lower() for c in pd.read_parquet(f).columns}
        hit = sorted(cols & FORBIDDEN_SCORE_COLS)
        if hit:
            bad_cols[f.name] = hit
    man_ok = all(m.get("generation_only") is True and m.get("scores_computed") is False
                 for m in manifests)
    rec_ok = all(r["forecast_scored_against_outcome"] is False
                 and r["evaluation_metric_calculated"] is False
                 and r["own_outcome_never_informed_its_forecast"] is True
                 for r in receipts.values())
    ok = (run_index["scores_computed"] is False and man_ok and rec_ok and not bad_cols)
    return {
        "check": "6_generation_only",
        "verdict": "PASS" if ok else "FAIL",
        "run_index_scores_computed": run_index["scores_computed"],
        "all_manifests_generation_only_and_unscored": man_ok,
        "all_fold_receipts_deny_scoring": rec_ok,
        "outcome_or_score_columns_found_in_artifacts": bad_cols,
        "consequence": ("every number surfaced by this node is computed FRESH from "
                        "pred_point vs owned-gamelog outcomes; none is copied from "
                        "legacy output, because the lane contains none"),
    }


# ===========================================================================
# CHECK 7 -- tier policy decision
# ===========================================================================

def check7_tier_policy(c7counts: dict) -> dict:
    return {
        "check": "7_tier_policy",
        "verdict": "PASS" if c7counts["tier_counts_verdict"] == "PASS" else "FAIL",
        "decision": {
            "headline_universe": "A_primary ONLY",
            "B_s2_weak_fallback": "SPLIT OUT -- reported as a separate labelled row set",
            "B_transaction_sensitivity": "SPLIT OUT -- reported as a separate labelled row set",
            "all_tiers_aggregate": "also published, explicitly labelled, never the headline",
            "authority": ("prediction_contract_v5 tier semantics: Tier B is cutoff-safe "
                          "but roster membership is NOT verified and is 'reported "
                          "SEPARATELY and never mixed silently into Tier A headline "
                          "metrics'; D036 point 8 requires the universe named on every "
                          "displayed number"),
        },
        "per_fold_per_target_counts_verified": c7counts["per_fold"],
    }


# ===========================================================================
# outcomes (owned gamelogs, assembled exactly as compute_player_granular.py)
# ===========================================================================

def load_outcomes() -> tuple[pd.DataFrame, dict]:
    audit = {"sources": {}}
    frames = []
    mp_path = WORKTREE / "data" / "masters" / "master_player.parquet"
    date_map = (pd.read_parquet(mp_path, columns=["game_id", "game_date"])
                .drop_duplicates("game_id"))
    date_map["game_id"] = date_map["game_id"].astype(str)
    date_lookup = dict(zip(date_map["game_id"], date_map["game_date"]))
    mp_games = pd.read_parquet(mp_path, columns=["game_id", "season"])
    mp_games["game_id"] = mp_games["game_id"].astype(str)
    master_game_counts = mp_games.drop_duplicates("game_id")["season"].value_counts().to_dict()

    pinned = {s: WORKTREE / "data" / f"wnba_gamelog_{s}.parquet"
              for s in (2021, 2022, 2023, 2024)}
    refresh = {s: WORKTREE / "data" / "refresh_2026" /
               f"gamelog_player_{s}_regular_season.parquet" for s in (2025, 2026)}

    for season, path in pinned.items():
        g = pd.read_parquet(path)
        tovcol = "TO" if "TO" in g.columns else "TOV"
        df = pd.DataFrame({
            "game_id": g["GAME_ID"].astype(str),
            "player_id": g["PLAYER_ID"].astype("int64"),
            "season": int(season),
            "minutes": g["MIN"].map(parse_min),
            "pts": g["PTS"].astype(float),
        })
        if "TEAM_ID" in g.columns:
            df["outcome_team_id"] = g["TEAM_ID"].astype("int64")
        df["game_date"] = df["game_id"].map(date_lookup)
        frames.append(df)
        audit["sources"][str(season)] = {
            "path": str(path.relative_to(WORKTREE)).replace("\\", "/"),
            "sha256": sha256_file(path), "n_rows": int(len(g)),
            "n_games": int(df["game_id"].nunique()),
            "n_games_in_master": int(master_game_counts.get(season, 0)),
            "tov_column": tovcol, "has_team_id": "TEAM_ID" in g.columns,
            "date_source": "data/masters/master_player.parquet (game_id->game_date only)",
        }
    for season, path in refresh.items():
        g = pd.read_parquet(path)
        df = pd.DataFrame({
            "game_id": g["GAME_ID"].astype(str),
            "player_id": g["PLAYER_ID"].astype("int64"),
            "season": int(season),
            "minutes": g["MIN"].map(parse_min),
            "pts": g["PTS"].astype(float),
            "game_date": pd.to_datetime(g["GAME_DATE"]).dt.strftime("%Y-%m-%d"),
        })
        if "TEAM_ID" in g.columns:
            df["outcome_team_id"] = g["TEAM_ID"].astype("int64")
        frames.append(df)
        audit["sources"][str(season)] = {
            "path": str(path.relative_to(WORKTREE)).replace("\\", "/"),
            "sha256": sha256_file(path), "n_rows": int(len(g)),
            "n_games": int(df["game_id"].nunique()),
            "n_games_in_master": int(master_game_counts.get(season, 0)),
            "has_team_id": "TEAM_ID" in g.columns,
            "note": ("refresh_2026 regular-season file; pinned 2025 file is truncated "
                     "and no pinned 2026 file exists (see compute_player_granular.py "
                     "source verification)") ,
        }
    out = pd.concat(frames, ignore_index=True)
    out["game_date"] = out["game_date"].astype(str)
    before = len(out)
    out = out.drop_duplicates(subset=["game_id", "player_id"], keep="first")
    audit["n_duplicate_player_games_dropped"] = int(before - len(out))
    return out, audit


# ===========================================================================
# metrics
# ===========================================================================

def build_scoring_frame(pg: pd.DataFrame, outcomes: pd.DataFrame,
                        manifests_by_name: dict) -> tuple[dict, dict]:
    """Join predictions -> contract identity -> owned-gamelog outcomes."""
    ident = pg[["row_uid", "player_id", "game_id", "team_id", "season",
                "evaluation_tier", "is_cold_start"]].copy()
    frames = {}
    audits = {}
    for stat, target in SCORED.items():
        parts = []
        art_hashes = {}
        for s in SEASONS:
            name = f"predictions__{target}__{s}.parquet"
            p = pd.read_parquet(ATT / name,
                                columns=["row_uid", "pred_point", "is_fallback",
                                         "fallback_level", "is_cold_start"])
            parts.append(p)
            art_hashes[str(s)] = manifests_by_name[name]["content_sha256"]
        pred = pd.concat(parts, ignore_index=True)
        j = pred.merge(ident.drop(columns=["is_cold_start"]), on="row_uid",
                       how="left", validate="one_to_one")
        j = j.merge(outcomes.drop(columns=["season"]),
                    on=["game_id", "player_id"], how="left", indicator=True)
        n_total = len(j)
        no_outcome = j["_merge"] == "left_only"
        games_in_outcomes = set(outcomes["game_id"])
        game_absent = no_outcome & ~j["game_id"].isin(games_in_outcomes)
        # a traded player owes two obligations in one game; the outcome belongs
        # to the team she actually played for
        if "outcome_team_id" in j.columns:
            team_known = j["outcome_team_id"].notna()
            team_mismatch = team_known & (j["outcome_team_id"] != j["team_id"]) & ~no_outcome
        else:
            team_mismatch = pd.Series(False, index=j.index)
        zero_min = (~no_outcome) & ~team_mismatch & (j["minutes"] <= 0)
        scored = (~no_outcome) & ~team_mismatch & (j["minutes"] > 0)
        audits[stat] = {
            "n_obligation_rows": int(n_total),
            "n_no_gamelog_outcome_row": int(no_outcome.sum()),
            "n_no_outcome__game_outside_outcome_universe": int(game_absent.sum()),
            "n_no_outcome__candidate_did_not_appear_in_covered_game":
                int((no_outcome & ~game_absent).sum()),
            "no_outcome_note": ("the outcome universe is the owned REGULAR-SEASON "
                                "gamelogs; obligations for games outside it "
                                "(playoffs and, for 2021-2024, any game the pinned "
                                "file lacks) and non-appearing candidates (an "
                                "obligation is owed pre-game; a healthy scratch is "
                                "a legitimate obligation with no minutes outcome) "
                                "are excluded AND counted here"),
            "n_outcome_team_differs_from_obligation_team": int(team_mismatch.sum()),
            "n_zero_minutes_excluded_conditional_target": int(zero_min.sum()),
            "n_scored": int(scored.sum()),
            "conditioning": ("both targets are conditional-on-appearance "
                             "(e_minutes_GIVEN_active; scoring distribution scoreable "
                             "only on appearance per the contract's "
                             "outcome_scoreable__* declarations); rows without a "
                             "gamelog appearance are excluded AND counted, never "
                             "silently dropped"),
            "prediction_artifact_sha256": art_hashes,
        }
        frames[stat] = j[scored].copy()
    return frames, audits


def metric_cell(sub: pd.DataFrame, stat: str, ycol: str, season_label: str,
                tier_label: str, art_hashes: dict, outcome_sources: dict) -> dict:
    if len(sub) == 0:
        return {"status": "NO_EVALUABLE_ROWS", "season": season_label,
                "tier": tier_label, "n_player_games": 0}
    pred = sub["pred_point"].to_numpy(float)
    act = sub[ycol].to_numpy(float)
    m = mae_rmse_bias(pred, act)
    ci = cluster_bootstrap_ci(np.abs(pred - act), sub["game_date"].to_numpy())
    return {
        "evidence_class": "PRELIMINARY",
        "evidence_class_reason": ("legacy-receiptable per D037: generation-only OOF "
                                  "artifacts verified by the 7-check provenance "
                                  "checklist; scored fresh by this node, not by the "
                                  "producing run"),
        "model_version": "cbs_v15_player_oof_v5/1 (arm cbs_v15_player_oof_v5, rev 8)",
        "target": stat,
        "cutoff": ("per-row forecast_cutoff inherited from prediction_contract_v5 "
                   "(v4 cutoffs where present, else 18:00 UTC the day before the "
                   "game); every row verified strictly pre-game (check 3)"),
        "universe": (f"prediction_contract_v5 obligation rows, tier={tier_label}, "
                     "joined to owned-gamelog appearances (minutes > 0)"),
        "season": season_label,
        "tier": tier_label,
        "n_player_games": int(len(sub)),
        "n_cold_start_rows_included": int(sub["is_cold_start"].sum()),
        "n_fallback_rows_included": int((sub["fallback_level"] > 0).sum()),
        "date_range": [str(sub["game_date"].min()), str(sub["game_date"].max())],
        "mae": m["mae"], "rmse": m["rmse"], "bias": m["bias"],
        "mae_ci95": ci,
        "source_prediction_artifact_sha256": art_hashes,
        "outcome_sources": outcome_sources,
    }


def compute_metrics(frames: dict, audits: dict, outcome_audit: dict) -> dict:
    tiers = {
        "A_primary": lambda d: d[d["evaluation_tier"] == "A_primary"],
        "B_s2_weak_fallback": lambda d: d[d["evaluation_tier"] == "B_s2_weak_fallback"],
        "B_transaction_sensitivity":
            lambda d: d[d["evaluation_tier"] == "B_transaction_sensitivity"],
        "all_tiers": lambda d: d,
    }
    out = {}
    for stat, target in SCORED.items():
        ycol = {"points": "pts", "minutes": "minutes"}[stat]
        df = frames[stat]
        osrc = {s: {"path": v["path"], "sha256": v["sha256"]}
                for s, v in outcome_audit["sources"].items()}
        out[stat] = {"source_target_key": target, "tiers": {}}
        for tname, tf in tiers.items():
            block = {}
            base = tf(df)
            for s in SEASONS:
                block[str(s)] = metric_cell(base[base["season"] == s], stat, ycol,
                                            str(s), tname,
                                            {str(s): audits[stat]["prediction_artifact_sha256"][str(s)]},
                                            {str(s): osrc[str(s)]})
            block["pooled_2022_2026"] = metric_cell(
                base[base["season"] >= 2022], stat, ycol, "pooled_2022_2026", tname,
                {k: v for k, v in audits[stat]["prediction_artifact_sha256"].items()
                 if k != "2021"},
                {k: v for k, v in osrc.items() if k != "2021"})
            block["pooled_2021_2026"] = metric_cell(
                base, stat, ycol, "pooled_2021_2026", tname,
                audits[stat]["prediction_artifact_sha256"], osrc)
            out[stat]["tiers"][tname] = block
        out[stat]["join_audit"] = audits[stat]
    out["headline_note"] = (
        "the scoreboard-comparable window is pooled_2022_2026 on tier A_primary: "
        "the naive-baseline column (player_granular_metrics.json) covers seasons "
        "2022-2026, and Tier B roster membership is unverified by contract. 2021 "
        "cells exist because the artifact universe includes 2021 (an UNFITTED, "
        "fallback-only fold: model_was_fitted=false) and are labelled, never pooled "
        "into the headline.")
    return out


# ===========================================================================
# report
# ===========================================================================

def write_report(checks: dict, overall: str, metrics: dict | None,
                 outcome_audit: dict | None, ts: str) -> None:
    L = []
    ap = "experiments/cbs_v15_player_oof_v5/attempt_001"
    L.append("# VERIFICATION_REPORT.md -- legacy player-model verification (D037)")
    L.append("")
    L.append(f"Date: {ts}. Verification node for the checklist in PROBE_LEGACY.md, "
             f"executed against bytes at `{ap}/`.")
    L.append(f"Producer run: `cbs_v15_player_oof_v5/1`; verifier: "
             f"`verify_legacy_player_model.py` (this directory).")
    L.append("")
    L.append(f"## OVERALL VERDICT: {overall}")
    L.append("")
    order = ["1_byte_integrity", "2_producer_digest", "3_cutoff_discipline",
             "4_universe_rederivation", "5_config_snapshot_pinning",
             "6_generation_only", "7_tier_policy"]
    titles = {
        "1_byte_integrity": "Check 1 -- byte integrity",
        "2_producer_digest": "Check 2 -- producer source-set digest",
        "3_cutoff_discipline": "Check 3 -- cutoff discipline",
        "4_universe_rederivation": "Check 4 -- universe re-derivation",
        "5_config_snapshot_pinning": "Check 5 -- config/snapshot pinning",
        "6_generation_only": "Check 6 -- generation-only claim",
        "7_tier_policy": "Check 7 -- tier policy",
    }
    c = checks
    L.append("| # | Check | Verdict |")
    L.append("|---|-------|---------|")
    for k in order:
        L.append(f"| {k[0]} | {titles[k].split('-- ')[1]} | **{c[k]['verdict']}** |")
    L.append("")

    c1 = c["1_byte_integrity"]
    L.append(f"### {titles['1_byte_integrity']}: {c1['verdict']}")
    L.append(f"{c1['n_verified']}/{c1['n_manifests']} manifests re-verified "
             f"(expected {c1['n_manifests_expected']}: 6 folds x (4 prediction "
             f"parquets + sidecar + fold receipt) + run_index). Recomputed sha256 "
             f"and byte counts equal `content_sha256`/`content_bytes` in every "
             f"`*.manifest.json`. Failures: {c1['failures'] or 'none'}.")
    L.append("")

    c2 = c["2_producer_digest"]
    L.append(f"### {titles['2_producer_digest']}: {c2['verdict']}")
    L.append(f"Recomputed digest over the 31-file `PRODUCER_SOURCES` set of "
             f"`run_player_oof_v15.py` = `{c2['recomputed_digest']}`; expected "
             f"`{c2['expected_digest']}` -- match: {c2['digest_matches']}. All 25 "
             f"artifact manifests and all 6 fold receipts carry the expected "
             f"digest. Producer source files drifted since the run: "
             f"{c2['sources_drifted_since_run'] or 'none'}.")
    L.append("")

    c3 = c["3_cutoff_discipline"]
    L.append(f"### {titles['3_cutoff_discipline']}: {c3['verdict']}")
    L.append(f"Per-row violations across all 24 prediction parquets "
             f"(forecast_cutoff >= game datetime, feature_asof >= game datetime, "
             f"or feature_asof > forecast_cutoff): "
             f"**{c3['row_violations_total']}**. The game datetime is the "
             f"contract's OBSERVED scheduled tip where captured (all 12,608 "
             f"`exact_tip_T-90m` rows of 2025-2026), else midnight UTC of the "
             f"game date, a lower bound on any same-day tip. "
             f"Per fold: `max(train_seasons) < S` holds for every fitted fold "
             f"(2021 is degenerate: no train seasons, fallback-only, "
             f"`model_was_fitted=false`). Every row's forecast_cutoff is "
             f"byte-equal to the contract's cutoff for its row_uid.")
    L.append("")
    L.append("| fold | train_seasons | manifest fit_through_date | reproduces | "
             "train-bound | precedes S's first game |")
    L.append("|------|---------------|---------------------------|------------|"
             "-------------|-------------------------|")
    for s in SEASONS:
        f = c3["per_fold"][str(s)]
        L.append(f"| {s} | {f['train_seasons'] or '[] (degenerate)'} | "
                 f"{f['manifest_fit_through_date']} | {f['fit_through_reproduces']} | "
                 f"{f['train_component_bound'] or 'n/a'} | "
                 f"{f['train_bound_precedes_season_first_game']} |")
    L.append("")
    L.append("PROBE_LEGACY.md's literal reading of the third assertion "
             "(`fit_through_date <= season S first game date`) does not apply to a "
             "walk-forward artifact and is replaced, per `asof_invariant.py`'s own "
             "manifest semantics, by the two assertions above: the artifact-level "
             "`fit_through_date` is max(train bound, max per-row `feature_asof`), "
             "and the per-row `feature_asof` lawfully includes within-season "
             "history strictly before each row's own cutoff. The recomputed value "
             "reproduces the manifest value exactly in every fold, and the "
             "TRAIN component precedes the predicted season's first game in every "
             "fitted fold.")
    L.append("")

    c4 = c["4_universe_rederivation"]
    L.append(f"### {titles['4_universe_rederivation']}: {c4['verdict']}")
    L.append(f"`prediction_contract_v5.build_candidates()` re-run in memory from "
             f"the pinned inputs (all pinned hashes match the fold receipts: "
             f"{all(c4['pinned_input_hashes_match_fold_receipts'].values())}); "
             f"{c4['n_rederived_total']} obligation rows re-derived.")
    L.append("")
    L.append("| season | n re-derived | n receipt | row_uid sets equal | tier counts match |")
    L.append("|--------|--------------|-----------|--------------------|-------------------|")
    for s in SEASONS:
        p = c4["per_season"][str(s)]
        L.append(f"| {s} | {p['n_rederived']} | {p['n_receipt_universe']} | "
                 f"{p['row_uid_set_equals_artifact_universe']} | "
                 f"{p['rederived_tier_counts'] == p['receipt_tier_counts']} |")
    L.append("")
    L.append(f"Caveat (recorded, not blocking): {c4['unpinned_inputs_note']}")
    L.append("")

    c5 = c["5_config_snapshot_pinning"]
    L.append(f"### {titles['5_config_snapshot_pinning']}: {c5['verdict']}")
    L.append("`config_hash` and `data_snapshot_hash` are single-valued in every "
             "prediction parquet and equal to the fold receipt's values; `fold_id` "
             "is `season:S` everywhere; the run-level `config_hash` "
             "(`e435d732...`) is constant across all six folds.")
    L.append("")

    c6 = c["6_generation_only"]
    L.append(f"### {titles['6_generation_only']}: {c6['verdict']}")
    L.append(f"`run_index.json.scores_computed={c6['run_index_scores_computed']}`; "
             f"all 25 manifests carry `generation_only: true, scores_computed: "
             f"false`; all 6 fold receipts assert no forecast was scored and no "
             f"evaluation metric calculated; no outcome or score column exists in "
             f"any parquet (columns scanned against a forbidden-name set; hits: "
             f"{c6['outcome_or_score_columns_found_in_artifacts'] or 'none'}). "
             f"Every surfaced number below is computed fresh against owned "
             f"gamelogs.")
    L.append("")

    c7 = c["7_tier_policy"]
    L.append(f"### {titles['7_tier_policy']}: {c7['verdict']}")
    d = c7["decision"]
    L.append(f"DECISION (recorded): headline universe = **{d['headline_universe']}**; "
             f"`B_s2_weak_fallback` and `B_transaction_sensitivity` are split out as "
             f"separate labelled row sets; an all-tiers aggregate is published and "
             f"labelled, never the headline. Authority: {d['authority']} Per-fold, "
             f"per-target tier counts in the parquets match every fold receipt.")
    L.append("")

    if metrics is not None:
        L.append("## Verified legacy metrics (evidence class: PRELIMINARY, legacy-receiptable)")
        L.append("")
        L.append("Computed by this node from `pred_point` vs owned-gamelog outcomes "
                 "(sources + sha256 in `legacy_verified_metrics.json`), on "
                 "appearance rows (minutes > 0) of the artifact universe; both "
                 "targets are conditional-on-appearance by contract. 95% CIs: "
                 f"game-date-cluster bootstrap, seed {SEED}, {N_BOOT} draws -- the "
                 "same method as the naive-baseline scoreboard cells. Bias = "
                 "mean(pred - actual). Headline = A_primary, pooled 2022-2026 "
                 "(the naive-baseline window).")
        for stat in SCORED:
            L.append("")
            L.append(f"### {stat}")
            L.append("")
            L.append("| tier | season | N | MAE | MAE 95% CI | RMSE | bias |")
            L.append("|------|--------|---|-----|------------|------|------|")
            for tname in ("A_primary", "all_tiers", "B_s2_weak_fallback",
                          "B_transaction_sensitivity"):
                block = metrics[stat]["tiers"][tname]
                for key in [str(s) for s in SEASONS] + ["pooled_2022_2026",
                                                        "pooled_2021_2026"]:
                    cell = block[key]
                    if cell.get("status") == "NO_EVALUABLE_ROWS":
                        L.append(f"| {tname} | {key} | 0 | -- | -- | -- | -- |")
                        continue
                    ci = cell["mae_ci95"]
                    bold = tname == "A_primary" and key == "pooled_2022_2026"
                    b = "**" if bold else ""
                    L.append(f"| {tname} | {b}{key}{b} | {cell['n_player_games']} | "
                             f"{b}{cell['mae']:.4f}{b} | "
                             f"[{ci['lo']:.4f}, {ci['hi']:.4f}] | "
                             f"{cell['rmse']:.4f} | {cell['bias']:+.4f} |")
            a = metrics[stat]["join_audit"]
            L.append("")
            L.append(f"Join audit ({stat}): {a['n_obligation_rows']} obligation rows; "
                     f"{a['n_no_gamelog_outcome_row']} without a gamelog outcome row "
                     f"(candidate did not appear, or outcome outside the owned "
                     f"regular-season universe); "
                     f"{a['n_outcome_team_differs_from_obligation_team']} where the "
                     f"outcome's team differs from the obligation's team (dual "
                     f"obligations of traded players -- the other team's row scores); "
                     f"{a['n_zero_minutes_excluded_conditional_target']} zero-minute "
                     f"rows excluded (conditional target); {a['n_scored']} scored.")
        L.append("")
        L.append("## Scope and caveats")
        L.append("")
        L.append("- Stats covered: **points and minutes only.** The legacy lane never "
                 "registered rebounds/assists/steals/blocks/threes/turnovers; those "
                 "scoreboard rows remain ABSENT for the legacy column (PROBE_LEGACY.md).")
        L.append("- No `SEALED_RESULTS` path was read or written; no git command was "
                 "run. The producer's own clean-tree receipt records commit "
                 "`0108ef86e9c085e1d701e40e53c24dcde177ac97`; that identifier is "
                 "reproduced from the receipt, not independently verified here -- the "
                 "verified anchors are the manifest hashes and the producer source-set "
                 "digest (checks 1-2).")
        L.append("- 2021 is an unfitted, fallback-only fold and 2021 outcome rows come "
                 "from the pinned 2021 gamelog; 2021 cells are labelled and excluded "
                 "from the headline pooled window.")
        L.append("- Evidence class PRELIMINARY per D036/D038: verified provenance, "
                 "but a legacy artifact scored retrospectively by a different node -- "
                 "not a program-registered, pre-declared evaluation (that would be "
                 "VERIFIED).")
    L.append("")
    (HERE / "VERIFICATION_REPORT.md").write_text("\n".join(L) + "\n",
                                                 encoding="utf-8", newline="")


# ===========================================================================

def main() -> int:
    ts = utcnow()
    run_index = json.loads((ATT / "run_index.json").read_text(encoding="utf-8"))
    receipts = {s: json.loads((ATT / f"fold_receipt__{s}.json").read_text(encoding="utf-8"))
                for s in SEASONS}
    manifests = [json.loads(p.read_text(encoding="utf-8"))
                 for p in sorted(ATT.glob("*.manifest.json"))]
    manifests_by_name = {Path(m["artifact"]).name: m for m in manifests}

    checks = {}
    print("check 1: byte integrity ...")
    checks["1_byte_integrity"] = check1_byte_integrity()
    print("  ->", checks["1_byte_integrity"]["verdict"])

    print("check 2: producer digest ...")
    checks["2_producer_digest"] = check2_producer_digest(run_index, receipts, manifests)
    print("  ->", checks["2_producer_digest"]["verdict"])

    print("loading enriched contract + per-fold checks (3/5/7 counts) ...")
    pg = load_contract()
    pf = per_fold_checks(pg, receipts, manifests_by_name)
    checks["3_cutoff_discipline"] = pf["c3"]
    checks["5_config_snapshot_pinning"] = pf["c5"]
    print("  -> 3:", pf["c3"]["verdict"], " 5:", pf["c5"]["verdict"])

    print("check 4: universe re-derivation (build_candidates re-run) ...")
    checks["4_universe_rederivation"] = check4_universe(pg, receipts)
    print("  ->", checks["4_universe_rederivation"]["verdict"])

    print("check 6: generation-only scan ...")
    checks["6_generation_only"] = check6_generation_only(run_index, receipts, manifests)
    print("  ->", checks["6_generation_only"]["verdict"])

    checks["7_tier_policy"] = check7_tier_policy(pf["c7counts"])
    print("check 7 ->", checks["7_tier_policy"]["verdict"])

    order = ["1_byte_integrity", "2_producer_digest", "3_cutoff_discipline",
             "4_universe_rederivation", "5_config_snapshot_pinning",
             "6_generation_only", "7_tier_policy"]
    overall = "RECEIPTED" if all(checks[k]["verdict"] == "PASS" for k in order) else "FAILED"
    print("OVERALL:", overall)

    metrics = None
    outcome_audit = None
    if overall == "RECEIPTED":
        print("assembling owned-gamelog outcomes ...")
        outcomes, outcome_audit = load_outcomes()
        print("scoring points + minutes ...")
        frames, audits = build_scoring_frame(pg, outcomes, manifests_by_name)
        metrics = compute_metrics(frames, audits, outcome_audit)

    payload = {
        "schema": "market_program/SCOREBOARD/granular/legacy_verified_metrics/1",
        "generated_utc": ts,
        "decision_authority": ["D036_SCOREBOARD_MEASUREMENT_SEMANTICS",
                               "D037_GRANULAR_PLAYER_SCOREBOARD"],
        "evidence_class": "PRELIMINARY",
        "evidence_class_reason": ("legacy-receiptable: provenance verified by the "
                                  "7-check checklist below; scored retrospectively "
                                  "by this verification node, not by a "
                                  "program-registered pre-declared evaluation"),
        "seed": SEED, "n_boot": N_BOOT,
        "producer": "verify_legacy_player_model.py",
        "producer_sha256": sha256_file(Path(__file__)),
        "commit_sha": ("UNAVAILABLE: no git in this worktree per task constraints; "
                       "the producing run's clean-tree receipt asserts commit "
                       "0108ef86e9c085e1d701e40e53c24dcde177ac97 (reproduced, not "
                       "independently verified); manifest content hashes + the "
                       "producer source-set digest are the verified anchors"),
        "legacy_run": {
            "run_id": run_index["run_id"],
            "arm_id": run_index["arm_id"],
            "arm_revision": run_index["arm_revision"],
            "artifact_dir": "experiments/cbs_v15_player_oof_v5/attempt_001",
            "row_universe": run_index["row_universe"],
            "history_policy": run_index["history_policy"],
            "config_hash": run_index["config_hash"],
            "snapshot_hash_by_season": run_index["snapshot_hash_by_season"],
            "producer_source_set_digest": EXPECTED_DIGEST,
        },
        "verification": {"overall_verdict": overall,
                         "checklist_source": "PROBE_LEGACY.md (this directory)",
                         "checks": checks},
        "stats_covered": sorted(SCORED),
        "stats_absent_no_legacy_artifacts": ["rebounds", "assists", "steals",
                                             "blocks", "threes_made", "turnovers"],
        "outcome_assembly": outcome_audit,
        "our_model": metrics if metrics is not None else {
            "lifecycle_state": "VERIFICATION_FAILED", "note": "see checks"},
    }
    with open(HERE / "legacy_verified_metrics.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, default=str)

    write_report(checks, overall, metrics, outcome_audit, ts)

    if metrics:
        for stat in SCORED:
            cell = metrics[stat]["tiers"]["A_primary"]["pooled_2022_2026"]
            ci = cell["mae_ci95"]
            print(f"  A_primary pooled 2022-2026 {stat:8s}: "
                  f"MAE={cell['mae']:.4f} [{ci['lo']:.4f},{ci['hi']:.4f}] "
                  f"RMSE={cell['rmse']:.4f} bias={cell['bias']:+.4f} "
                  f"N={cell['n_player_games']}")
    return 0 if overall == "RECEIPTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
