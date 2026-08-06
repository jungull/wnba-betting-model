#!/usr/bin/env python3
"""compute_model_vs_market.py -- FIRST MODEL-VS-MARKET comparison (legacy points).

Compares, on the STRICT INTERSECTION of matched player-games:

  (1) MODEL OU calls  -- legacy verified pred_point (cbs_v15_player_oof_v5/1,
      target player_scoring_distribution) vs the cross-book consensus line
      -> over/under call -> accuracy vs realized points;
  (2) MARKET OU calls -- de-vigged consensus threshold probability P(over)
      (vig math DELEGATED to experiments/market_program/M11_CONSENSUS_MODEL/
      consensus.py, preregistered multiplicative method, uniform weights)
      -> majority call accuracy AND Brier;
  (3) model OU accuracy vs market OU accuracy, PAIRED per player-game,
      difference with game-date-clustered 95% bootstrap CI (same method,
      seed and draw count as the granular scoreboard);
  (4) model |pred - outcome| vs |line - outcome| paired -- THRESHOLD-DISTANCE
      framing per D036 point 5: |line - outcome| is a distance to a betting
      THRESHOLD, explicitly NOT the market's projection error, and is never
      conflated with projection MAE;
  (5) splits per season + pooled; headline universe A_primary (check-7
      decision of VERIFICATION_REPORT.md), all_tiers published and labelled.

TIMING (T1 / VENDOR_ASSERTED, advisory channel only): the props archive
(master_props_historical.csv) is T1_VENDOR_ASSERTED per D027. Its snapshot
timestamps are vendor-asserted and unwitnessed. Whether the legacy model's
forecast_cutoff precedes the prop snapshot is NOT establishable from
witnessed records: every cutoff-vs-snapshot ordering statement in the
outputs is labelled VENDOR_ASSERTED / asserted-not-witnessed, lives in the
advisory channel (contract section 6.2) and never enters the headline.
No CLV, timing, stale-window, lead-lag or executability claim is made.

D027 bounded use invoked: no-vig calibration against realized outcomes with
unknown-timing caveats (the M00-U2 class extended to this T1 archive by
D027). The M00-U2 caveat text is reproduced verbatim (bytes from
TAXONOMY.json) with its frozen caveat_sha256.

Model-as-probability is NOT available: the legacy artifact is a point
prediction (generation-only); no model Brier exists and none is invented.

Evidence class: PRELIMINARY. No evidence-ladder label (contract section 3)
is claimed or held. This is a scoreboard cell, not a preregistered F8
family endpoint.

No git, no network, no subagents, no SEALED_RESULTS. Deterministic (SEED).
Inputs read-only; all outputs land in this directory.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]                    # .../player-model-program
LIVE_ROOT = WORKTREE.parents[2]               # .../wnba-betting-model (live worktree)

sys.path.insert(0, str(WORKTREE / "experiments" / "market_program" / "M11_CONSENSUS_MODEL"))
import consensus  # noqa: E402  -- vig math is DELEGATED to this module

ATT = WORKTREE / "experiments" / "cbs_v15_player_oof_v5" / "attempt_001"
ENRICHED = WORKTREE / "experiments" / "prediction_contract_v5" / "player_game_enriched.parquet"
PROPS_CSV = LIVE_ROOT / "data" / "props_capture" / "historical" / "master_props_historical.csv"
TAXONOMY = WORKTREE / "experiments" / "market_program" / "M00_MARKET_PROGRAM_CONTRACT" / "TAXONOMY.json"
CONTRACT_MD = WORKTREE / "experiments" / "market_program" / "M00_MARKET_PROGRAM_CONTRACT" / "MARKET_PROGRAM_CONTRACT.md"
ALIAS_TABLE = (WORKTREE / "experiments" / "player_program" / "ops_lane" /
               "O14_OPS_ENTITY_RESOLUTION" / "alias_table.json")

CONTRACT_SHA256_EXPECTED = "1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de"

SEED = 20260806            # same seed + method as the granular scoreboard
N_BOOT = 1000
SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
PROP_SEASONS = [2024, 2025, 2026]
TARGET = "player_scoring_distribution"
HEADLINE_TIER = "A_primary"


# ---------------------------------------------------------------------------
# small utilities (byte-compatible with the granular scoreboard node)
# ---------------------------------------------------------------------------

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


def cluster_bootstrap_ci(values, clusters, n_boot: int = N_BOOT,
                         seed: int = SEED, alpha: float = 0.05) -> dict:
    """Percentile CI on the mean of `values`, cluster-bootstrapped over game
    dates -- identical method to verify_legacy_player_model.py."""
    values = np.asarray(values, dtype=float)
    codes, _ = pd.factorize(np.asarray(clusters), sort=True)
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


# ---------------------------------------------------------------------------
# O14 entity-resolution conventions (ops_lane/O14_OPS_ENTITY_RESOLUTION):
# normalized-EXACT matching + explicit alias table; NO fuzzy fallback;
# unresolvable rows are excluded AND listed, never silently dropped.
# ---------------------------------------------------------------------------

def _norm_name(s: str) -> str:     # O14 fix_entity_resolution._norm_name, verbatim
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_aliases() -> dict:
    if not ALIAS_TABLE.exists():
        return {}
    raw = json.loads(ALIAS_TABLE.read_text(encoding="utf-8"))
    return {_norm_name(k): int(v) for k, v in raw.get("aliases", {}).items()}


def build_identity_index(name_rows: pd.DataFrame) -> dict:
    """normalized name -> player_id, seasons ascending so the latest season's
    binding wins (O14 build_identity_index convention: cross-season index,
    current holder of a name binds last)."""
    idx: dict[str, int] = {}
    for _, sub in name_rows.sort_values("season").groupby("season", sort=True):
        for pid, nm in sub[["player_id", "player_name"]].drop_duplicates().itertuples(index=False):
            idx[_norm_name(nm)] = int(pid)
    idx.update(load_aliases())
    return idx


# ---------------------------------------------------------------------------
# outcomes + identity names (owned gamelogs, assembled exactly as the
# granular scoreboard / verification node did)
# ---------------------------------------------------------------------------

def load_outcomes() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    audit = {"sources": {}}
    frames, names = [], []
    mp_path = WORKTREE / "data" / "masters" / "master_player.parquet"
    date_map = (pd.read_parquet(mp_path, columns=["game_id", "game_date"])
                .drop_duplicates("game_id"))
    date_map["game_id"] = date_map["game_id"].astype(str)
    date_lookup = dict(zip(date_map["game_id"], date_map["game_date"]))
    audit["game_date_source"] = {
        "path": "data/masters/master_player.parquet",
        "sha256": sha256_file(mp_path),
        "use": "game_id -> game_date lookup only (pinned 2021-2024 files carry no date)",
    }

    pinned = {s: WORKTREE / "data" / f"wnba_gamelog_{s}.parquet"
              for s in (2021, 2022, 2023, 2024)}
    refresh = {s: WORKTREE / "data" / "refresh_2026" /
               f"gamelog_player_{s}_regular_season.parquet" for s in (2025, 2026)}

    for season, path in pinned.items():
        g = pd.read_parquet(path)
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
        names.append(pd.DataFrame({"player_id": g["PLAYER_ID"].astype("int64"),
                                   "player_name": g["PLAYER_NAME"].astype(str),
                                   "season": int(season)}))
        audit["sources"][str(season)] = {
            "path": str(path.relative_to(WORKTREE)).replace("\\", "/"),
            "sha256": sha256_file(path), "n_rows": int(len(g)),
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
        names.append(pd.DataFrame({"player_id": g["PLAYER_ID"].astype("int64"),
                                   "player_name": g["PLAYER_NAME"].astype(str),
                                   "season": int(season)}))
        audit["sources"][str(season)] = {
            "path": str(path.relative_to(WORKTREE)).replace("\\", "/"),
            "sha256": sha256_file(path), "n_rows": int(len(g)),
        }
    out = pd.concat(frames, ignore_index=True)
    out["game_date"] = out["game_date"].astype(str)
    before = len(out)
    out = out.drop_duplicates(subset=["game_id", "player_id"], keep="first")
    audit["n_duplicate_player_games_dropped"] = int(before - len(out))
    name_rows = pd.concat(names, ignore_index=True).drop_duplicates()
    return out, name_rows, audit


# ---------------------------------------------------------------------------
# legacy predictions -> scored points frame (generation-consistent rows only)
# ---------------------------------------------------------------------------

def load_scored_points(outcomes: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    pg = pd.read_parquet(ENRICHED, columns=[
        "row_uid", "player_id", "game_id", "team_id", "season",
        "evaluation_tier", "forecast_cutoff", "is_cold_start"])
    pg["game_id"] = pg["game_id"].astype(str)
    pg["forecast_cutoff"] = pd.to_datetime(pg["forecast_cutoff"], utc=True)

    parts, art_hashes = [], {}
    for s in SEASONS:
        name = f"predictions__{TARGET}__{s}.parquet"
        man = json.loads((ATT / f"{name}.manifest.json").read_text(encoding="utf-8"))
        got = sha256_file(ATT / name)
        if got != man["content_sha256"]:
            raise RuntimeError(f"byte drift vs manifest for {name}: {got}")
        art_hashes[str(s)] = got
        p = pd.read_parquet(ATT / name, columns=[
            "row_uid", "pred_point", "forecast_cutoff", "fallback_level",
            "is_cold_start", "exclusion_reason"])
        p["forecast_cutoff"] = pd.to_datetime(p["forecast_cutoff"], utc=True)
        parts.append(p)
    pred = pd.concat(parts, ignore_index=True)

    j = pred.merge(pg.drop(columns=["is_cold_start"]), on="row_uid",
                   how="left", validate="one_to_one",
                   suffixes=("", "_contract"))
    # GENERATION-CONSISTENCY guard: a row is used only if its per-row
    # forecast_cutoff is byte-equal to the contract's cutoff for its row_uid
    # (VERIFICATION_REPORT check 3 found 0 mismatches; re-asserted here, and
    # any mismatch would be EXCLUDED AND COUNTED, never silently dropped).
    incons = (j["forecast_cutoff"] != j["forecast_cutoff_contract"])
    audit = {
        "n_prediction_rows_all_seasons": int(len(j)),
        "n_generation_inconsistent_cutoff_rows_excluded": int(incons.sum()),
        "n_excluded_by_producer_exclusion_reason": int(j["exclusion_reason"].notna().sum()),
        "prediction_artifact_sha256": art_hashes,
    }
    j = j[~incons & j["exclusion_reason"].isna()].copy()

    j = j.merge(outcomes.drop(columns=["season"]),
                on=["game_id", "player_id"], how="left", indicator=True)
    no_outcome = j["_merge"] == "left_only"
    if "outcome_team_id" in j.columns:
        team_known = j["outcome_team_id"].notna()
        team_mismatch = team_known & (j["outcome_team_id"] != j["team_id"]) & ~no_outcome
    else:
        team_mismatch = pd.Series(False, index=j.index)
    zero_min = (~no_outcome) & ~team_mismatch & (j["minutes"] <= 0)
    scored = (~no_outcome) & ~team_mismatch & (j["minutes"] > 0)
    audit.update({
        "n_no_gamelog_outcome_row": int(no_outcome.sum()),
        "n_outcome_team_differs_from_obligation_team": int(team_mismatch.sum()),
        "n_zero_minutes_excluded_conditional_target": int(zero_min.sum()),
        "n_scored_points_rows": int(scored.sum()),
    })
    return j[scored].copy(), audit


# ---------------------------------------------------------------------------
# props archive -> per-player-game consensus (vig math via consensus.py)
# ---------------------------------------------------------------------------

def select_consensus_line(lines_by_book: pd.DataFrame) -> float:
    """Consensus line = the line quoted TWO-SIDED by the most distinct books;
    ties broken by closeness to the median of all two-sided quoted lines,
    then by the LOWER line. Frozen rule; no tuning on results."""
    counts = lines_by_book.groupby("line")["bookmaker_key"].nunique()
    med = float(lines_by_book["line"].median())
    best = sorted(counts.index,
                  key=lambda ln: (-int(counts[ln]), abs(ln - med), ln))
    return float(best[0])


def build_market_frame(id_index: dict) -> tuple[pd.DataFrame, dict, list]:
    raw = pd.read_csv(PROPS_CSV)
    audit = {
        "source": {"path": "data/props_capture/historical/master_props_historical.csv "
                           "(LIVE worktree)",
                   "sha256": sha256_file(PROPS_CSV),
                   "tier": "T1_VENDOR_ASSERTED per D027",
                   "n_rows": int(len(raw)),
                   "n_games": int(raw["game_id"].nunique())},
    }
    assert set(raw["market_key"]) == {"player_points"}, "unexpected market_key"
    raw["game_id"] = raw["game_id"].astype(str)
    raw["commence"] = pd.to_datetime(raw["commence_time"], utc=True)
    raw["snap_ret"] = pd.to_datetime(raw["snapshot_returned_utc"], utc=True)

    # structural in-play exclusion (contract section 4.4)
    inplay = raw["snap_ret"] >= raw["commence"]
    audit["n_inplay_rows_excluded"] = int(inplay.sum())
    df = raw[~inplay].copy()

    one_sided = df["over_price"].isna() | df["under_price"].isna()
    audit["n_one_sided_rows_excluded_cannot_devig"] = int(one_sided.sum())
    audit["one_sided_by_book"] = {k: int(v) for k, v in
                                  df.loc[one_sided, "bookmaker_key"].value_counts().items()}
    df = df[~one_sided].copy()
    audit["n_two_sided_rows"] = int(len(df))

    dup_bl = df.duplicated(["game_id", "player_name", "bookmaker_key", "line"])
    audit["n_same_book_same_line_duplicate_rows_dropped"] = int(dup_bl.sum())
    df = df[~dup_bl].copy()

    # O14 normalized-exact entity resolution; unresolved EXCLUDED and LISTED
    df["norm_name"] = df["player_name"].map(_norm_name)
    df["player_id"] = df["norm_name"].map(id_index)
    unresolved_mask = df["player_id"].isna()
    unresolved = (df[unresolved_mask].groupby("player_name")
                  .agg(n_rows=("game_id", "size"),
                       n_games=("game_id", "nunique")).reset_index()
                  .to_dict(orient="records"))
    known_variants = {
        "Cheyenne Parker": ("owned gamelogs list her as 'Cheyenne "
                            "Parker-Tyus' in 2024-2026; a genuine spelling "
                            "variant. Per O14 conventions resolution is "
                            "normalized-EXACT plus an explicit alias table "
                            "and NEVER fuzzy, so she is excluded here and "
                            "flagged as an alias-table candidate for O14 "
                            "(a human decision, not this node's to make)."),
    }
    for u in unresolved:
        if u["player_name"] in known_variants:
            u["identification_note"] = known_variants[u["player_name"]]
    audit["n_unresolved_player_rows_excluded"] = int(unresolved_mask.sum())
    df = df[~unresolved_mask].copy()
    df["player_id"] = df["player_id"].astype("int64")

    # one vendor-asserted snapshot per game (verified below) -> the prop key
    # is (game_id, player_id)
    snaps_per_game = raw.groupby("game_id")["snapshot_requested_utc"].nunique()
    audit["snapshots_per_game"] = {str(k): int(v) for k, v in
                                   snaps_per_game.value_counts().items()}
    audit["snapshot_class_note"] = (
        "single vendor-asserted snapshot per game; vendor-asserted "
        "snapshot-to-commence gap (hours): "
        f"min {float(((raw['commence'] - raw['snap_ret']).dt.total_seconds() / 3600).min()):.3f}, "
        f"median {float(((raw['commence'] - raw['snap_ret']).dt.total_seconds() / 3600).median()):.3f}, "
        f"max {float(((raw['commence'] - raw['snap_ret']).dt.total_seconds() / 3600).max()):.3f} "
        "-- VENDOR_ASSERTED, unwitnessed (D027); this is the only as-of class "
        "this archive supports (D036 point 3)")

    rows = []
    n_books_other_line_total = 0
    for (gid, pid), grp in df.groupby(["game_id", "player_id"], sort=True):
        cline = select_consensus_line(grp)
        at_line = grp[grp["line"] == cline]
        quotes = []
        for r in at_line.itertuples():
            q = consensus.make_quote(
                bookmaker=r.bookmaker_key, price=float(r.over_price),
                capture_ts=consensus.parse_ts(r.snapshot_returned_utc),
                tier="T1", vendor_ts=str(r.last_update),
                vendor_ts_semantics="unknown_unverified",
                market="player_points", outcome="over", point=float(cline))
            q["opposite_price"] = float(r.under_price)
            quotes.append(q)
        cobj = consensus.consensus_fair_value(
            quotes, allow_t1=True, game_id=str(gid),
            clock_skew=consensus.UNMEASURED)
        n_other = int(grp["bookmaker_key"].nunique() - at_line["bookmaker_key"].nunique())
        n_books_other_line_total += n_other
        rows.append({
            "game_id": str(gid), "player_id": int(pid),
            "player_name": grp["player_name"].iloc[0],
            "consensus_line": cline,
            "p_over_devig": float(cobj["consensus_fair_prob"]),
            "n_books_at_consensus_line": int(cobj["n_books_admitted"]),
            "n_books_excluded_other_lines": n_other,
            "disagreement_score": cobj["disagreement_score"],
            "uncertainty_std": cobj["uncertainty_std"],
            "snap_ret_utc": grp["snap_ret"].iloc[0].isoformat(),
            "commence_utc": grp["commence"].iloc[0].isoformat(),
        })
    mkt = pd.DataFrame(rows)
    audit["n_prop_player_games_resolved_two_sided"] = int(len(mkt))
    audit["n_book_quotes_excluded_non_consensus_line"] = int(n_books_other_line_total)
    audit["consensus_method"] = {
        "module": "experiments/market_program/M11_CONSENSUS_MODEL/consensus.py",
        "module_sha256": sha256_file(WORKTREE / "experiments" / "market_program" /
                                     "M11_CONSENSUS_MODEL" / "consensus.py"),
        "vig_method": consensus.PREREGISTERED_VIG_METHOD,
        "vig_preregistration_hash": consensus.PREREGISTRATION_HASH,
        "weights": "PREREGISTERED_UNIFORM",
        "line_rule": ("consensus line = line quoted two-sided by the most "
                      "distinct books; ties -> closest to the median of all "
                      "two-sided lines for that player-game; ties -> lower "
                      "line. Books not quoting the consensus line are "
                      "EXCLUDED AND COUNTED, never blended across thresholds "
                      "(D036 point 5: thresholds are never conflated)"),
        "epistemic_status_line": consensus.EPISTEMIC_STATUS_LINE,
    }
    return mkt, audit, unresolved


# ---------------------------------------------------------------------------
# matched-universe comparison
# ---------------------------------------------------------------------------

def compare_cell(sub: pd.DataFrame, season_label: str, tier_label: str) -> dict:
    """One scoreboard cell on the matched, evaluable universe `sub`."""
    if len(sub) == 0:
        return {"status": "NO_EVALUABLE_ROWS", "season": season_label,
                "tier": tier_label, "n_player_games": 0}
    y_over = (sub["pts"] > sub["consensus_line"]).to_numpy()
    model_call_over = (sub["pred_point"] > sub["consensus_line"]).to_numpy()
    market_call_over = (sub["p_over_devig"] > 0.5).to_numpy()
    model_ok = (model_call_over == y_over).astype(float)
    market_ok = (market_call_over == y_over).astype(float)
    d_acc = model_ok - market_ok
    ci_acc = cluster_bootstrap_ci(d_acc, sub["game_date"].to_numpy())
    brier = float(np.mean((sub["p_over_devig"].to_numpy() - y_over.astype(float)) ** 2))
    # threshold-distance framing (D036 point 5)
    dist_model = np.abs(sub["pred_point"].to_numpy() - sub["pts"].to_numpy())
    dist_line = np.abs(sub["consensus_line"].to_numpy() - sub["pts"].to_numpy())
    d_dist = dist_model - dist_line
    ci_dist = cluster_bootstrap_ci(d_dist, sub["game_date"].to_numpy())
    return {
        "season": season_label, "tier": tier_label,
        "n_player_games": int(len(sub)),
        "n_games": int(sub["game_id"].nunique()),
        "date_range": [str(sub["game_date"].min()), str(sub["game_date"].max())],
        "model_ou_accuracy": float(model_ok.mean()),
        "market_ou_accuracy": float(market_ok.mean()),
        "paired_accuracy_diff_model_minus_market": float(d_acc.mean()),
        "paired_accuracy_diff_ci95": ci_acc,
        "market_brier_devig_p_over": brier,
        "market_brier_note": ("Brier of the de-vigged consensus P(over) vs the "
                              "realized over indicator. NO model Brier exists: "
                              "the legacy artifact is a point prediction "
                              "(generation-only), not a probability."),
        "over_base_rate": float(y_over.mean()),
        "market_call_over_rate": float(market_call_over.mean()),
        "model_call_over_rate": float(model_call_over.mean()),
        "threshold_distance_block": {
            "framing": ("|consensus_line - outcome| is the distance from a "
                        "betting THRESHOLD to the outcome. The line is not "
                        "the market's point projection; this quantity is NOT "
                        "the market's projection error and is never compared "
                        "to projection MAE as like-for-like (D036 point 5)."),
            "model_mean_abs_pred_minus_outcome": float(dist_model.mean()),
            "line_mean_abs_line_minus_outcome": float(dist_line.mean()),
            "paired_diff_model_minus_line": float(d_dist.mean()),
            "paired_diff_ci95": ci_dist,
            "model_rmse_pred_minus_outcome": float(np.sqrt(np.mean(
                (sub["pred_point"].to_numpy() - sub["pts"].to_numpy()) ** 2))),
            "line_rms_line_minus_outcome": float(np.sqrt(np.mean(
                (sub["consensus_line"].to_numpy() - sub["pts"].to_numpy()) ** 2))),
            "model_bias_pred_minus_outcome": float(np.mean(
                sub["pred_point"].to_numpy() - sub["pts"].to_numpy())),
            "line_bias_line_minus_outcome": float(np.mean(
                sub["consensus_line"].to_numpy() - sub["pts"].to_numpy())),
        },
    }


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

    outcomes, name_rows, outcome_audit = load_outcomes()
    scored, model_audit = load_scored_points(outcomes)
    id_index = build_identity_index(name_rows)
    market, market_audit, unresolved = build_market_frame(id_index)

    # ---- strict intersection ------------------------------------------------
    m = scored.merge(market, on=["game_id", "player_id"], how="inner",
                     validate="one_to_one")
    join_audit = {
        "model_side": model_audit,
        "market_side": market_audit,
        "unresolved_player_names_excluded_and_listed": unresolved,
        "outcome_assembly": outcome_audit,
        "n_scored_model_rows_total": int(len(scored)),
        "n_market_player_games_total": int(len(market)),
        "n_matched_player_games": int(len(m)),
        "n_market_rows_unmatched_no_scored_model_row": int(len(market) - len(m)),
        "n_market_games_total": int(market["game_id"].nunique()),
        "n_matched_games": int(m["game_id"].nunique()),
        "n_market_games_with_no_matched_row": int(
            market["game_id"].nunique() - m["game_id"].nunique()),
        "unmatched_market_note": (
            "market player-games without a matched model row: the game is "
            "outside the owned regular-season outcome universe (e.g. "
            "playoffs/Commissioner's Cup final), the player did not appear "
            "(DNP -- conditional target), the outcome team differs from the "
            "obligation row scored, or the player-game is outside the legacy "
            "contract universe. Nothing is silently dropped; every stage "
            "above carries its own count."),
        "matched_by_tier": {k: int(v) for k, v in
                            m["evaluation_tier"].value_counts().items()},
        "matched_by_season": {str(k): int(v) for k, v in
                              m["season"].value_counts().sort_index().items()},
    }

    # in-cell exclusions (counted; lines are all *.5 so pushes cannot occur,
    # asserted anyway)
    push = (m["pts"] == m["consensus_line"])
    model_nocall = (m["pred_point"] == m["consensus_line"])
    market_nocall = (m["p_over_devig"] == 0.5)
    join_audit["n_push_outcome_equals_line"] = int(push.sum())
    join_audit["n_model_no_call_pred_equals_line"] = int(model_nocall.sum())
    join_audit["n_market_no_call_p_exactly_half"] = int(market_nocall.sum())
    ev = m[~push & ~model_nocall & ~market_nocall].copy()
    join_audit["n_evaluable_matched_player_games"] = int(len(ev))

    # vendor-asserted cutoff-vs-snapshot ordering -- ADVISORY CHANNEL ONLY
    snap = pd.to_datetime(ev["snap_ret_utc"])
    gap_h = (snap - ev["forecast_cutoff"]).dt.total_seconds() / 3600.0
    timing_advisory = {
        "channel": "VENDOR_ASSERTED (contract section 6.2 advisory channel; "
                   "never a headline, gate, endpoint or decision input)",
        "claim": ("cutoff ordering is ASSERTED-NOT-WITNESSED: the legacy "
                  "forecast_cutoff is a verified contract field, but the prop "
                  "snapshot timestamps are vendor-asserted and unwitnessed "
                  "(T1, D027). Whether the model's information cutoff truly "
                  "preceded the market snapshot cannot be established from "
                  "witnessed records."),
        "vendor_asserted_snapshot_minus_cutoff_hours": {
            "min": float(gap_h.min()), "p05": float(gap_h.quantile(0.05)),
            "median": float(gap_h.median()), "p95": float(gap_h.quantile(0.95)),
            "max": float(gap_h.max()),
            "n_negative_snapshot_asserted_before_cutoff": int((gap_h < 0).sum()),
        },
        "reading": (f"in the vendor-asserted timeline the market snapshot "
                    f"post-dates the model cutoff on {int((gap_h >= 0).sum())} "
                    f"of {len(gap_h)} evaluable rows (median gap "
                    f"{float(gap_h.median()):+.2f}h -- ~21 minutes for "
                    f"exact_tip_T-90m cutoff rows vs the ~T-65m snapshot; "
                    f"p95 {float(gap_h.quantile(0.95)):+.1f}h for day-before-"
                    f"18:00-UTC cutoff rows), i.e. the market quote reflects "
                    f"LATER information than the model on those rows IF the "
                    f"vendor stamps are truthful; on the "
                    f"{int((gap_h < 0).sum())} negative rows the asserted "
                    f"ordering is reversed. Asserted, unwitnessed context -- "
                    f"never a timing claim."),
    }

    # ---- cells: headline tier + all_tiers, per season + pooled ---------------
    tiers = {
        HEADLINE_TIER: ev[ev["evaluation_tier"] == HEADLINE_TIER],
        "all_tiers": ev,
    }
    cells = {}
    for tname, tdf in tiers.items():
        block = {}
        for s in PROP_SEASONS:
            block[str(s)] = compare_cell(tdf[tdf["season"] == s], str(s), tname)
        block["pooled_2024_2026"] = compare_cell(tdf, "pooled_2024_2026", tname)
        cells[tname] = block

    head = cells[HEADLINE_TIER]["pooled_2024_2026"]
    ci = head["paired_accuracy_diff_ci95"]
    if ci["lo"] > 0:
        verdict = "YES"
    elif ci["hi"] < 0:
        verdict = "NO"
    else:
        verdict = "INCONCLUSIVE"
    headline = {
        "question": ("does the legacy points model beat the market's own "
                     "over/under calls at the archive's vendor-asserted "
                     "snapshot?"),
        "verdict": verdict,
        "universe": f"{HEADLINE_TIER} matched player-games, pooled 2024-2026",
        "n": head["n_player_games"],
        "model_ou_accuracy": head["model_ou_accuracy"],
        "market_ou_accuracy": head["market_ou_accuracy"],
        "paired_diff": head["paired_accuracy_diff_model_minus_market"],
        "paired_diff_ci95": [ci["lo"], ci["hi"]],
        "market_brier": head["market_brier_devig_p_over"],
    }

    result = {
        "schema": "market_program/MODEL_VS_MARKET/model_vs_market/1",
        "generated_utc": utcnow(),
        "decision_authority": [
            "D023_MARKET_PROGRAM_AUTHORIZED", "D027_PROPS_HISTORICAL_BOUNDED_USES",
            "D034_GRADUATION_STANDARD", "D036_SCOREBOARD_MEASUREMENT_SEMANTICS",
            "D037 (VERIFICATION_REPORT.md, RECEIPTED legacy artifacts)"],
        "evidence_class": "PRELIMINARY",
        "evidence_class_reason": (
            "matched-universe retrospective comparison of a RECEIPTED legacy "
            "generation-only artifact against a T1 vendor-asserted props "
            "archive; not a preregistered family endpoint; no evidence-ladder "
            "label (contract section 3) is claimed or held"),
        "evidence_ladder_labels_held": [],
        "opportunity_class_context": (
            "informs MODEL_VS_MARKET_VALUE (contract section 1.4) but is NOT "
            "an F8 preregistered endpoint and confers no label"),
        "m00_bounded_use": {
            "m00_use_class": "M00-U2",
            "extended_to_this_archive_by": "D027_PROPS_HISTORICAL_BOUNDED_USES "
                                           "(calibration WITH unknown-timing caveats)",
            "object": "data/props_capture/historical/master_props_historical.csv (T1_VENDOR_ASSERTED)",
            "caveat_text_verbatim": u2["caveat_text"],
            "caveat_hash": u2["caveat_sha256"],
            "additional_prohibitions_honored": (
                "no CLV, timing, lead-lag, stale-window or executability "
                "claim is made anywhere in this node (D027)"),
        },
        "contract": {"path": "experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/"
                             "MARKET_PROGRAM_CONTRACT.md",
                     "sha256_verified": got_contract},
        "producer": "compute_model_vs_market.py",
        "commit_sha": ("UNAVAILABLE: no git in this worktree per task "
                       "constraints; the legacy producing run's clean-tree "
                       "receipt asserts commit "
                       "0108ef86e9c085e1d701e40e53c24dcde177ac97 (reproduced, "
                       "not independently verified); manifest content hashes "
                       "are the verified anchors"),
        "seed": SEED, "n_boot": N_BOOT,
        "model": {
            "model_version": "cbs_v15_player_oof_v5/1 (arm cbs_v15_player_oof_v5, rev 8)",
            "target": "points (player_scoring_distribution pred_point)",
            "cutoff": ("per-row forecast_cutoff inherited from "
                       "prediction_contract_v5; every used row re-asserted "
                       "byte-equal to the contract cutoff (generation-"
                       "consistent); verified strictly pre-game by "
                       "VERIFICATION_REPORT.md check 3"),
            "verification": "experiments/market_program/SCOREBOARD/granular/"
                            "VERIFICATION_REPORT.md (7/7 RECEIPTED)",
        },
        "market": {
            "primary_quantity": ("de-vigged consensus threshold probability "
                                 "P(points > consensus_line) -- D036 point 5 "
                                 "primary; implied means are NOT computed"),
            "as_of": ("single vendor-asserted snapshot per game (~T-65m "
                      "median, VENDOR_ASSERTED); the only as-of class this "
                      "archive supports (D036 point 3)"),
        },
        "timing_advisory_vendor_asserted": timing_advisory,
        "headline": headline,
        "cells": cells,
        "join_audit": join_audit,
    }
    result["result_hash"] = hashlib.sha256(json.dumps(
        {k: v for k, v in result.items() if k not in ("generated_utc",)},
        sort_keys=True, default=str).encode()).hexdigest()

    (HERE / "model_vs_market.json").write_text(
        json.dumps(result, indent=1, default=str), encoding="utf-8")
    write_report(result)
    print("verdict:", verdict)
    print("A_primary pooled: n", head["n_player_games"],
          "model", round(head["model_ou_accuracy"], 4),
          "market", round(head["market_ou_accuracy"], 4),
          "diff", round(head["paired_accuracy_diff_model_minus_market"], 4),
          "ci", [round(ci["lo"], 4), round(ci["hi"], 4)])


def write_report(r: dict) -> None:
    h = r["headline"]
    cells = r["cells"]
    ja = r["join_audit"]
    ta = r["timing_advisory_vendor_asserted"]

    def cell_row(c):
        if c.get("status") == "NO_EVALUABLE_ROWS":
            return f"| {c['season']} | 0 | -- | -- | -- | -- | -- |"
        ci = c["paired_accuracy_diff_ci95"]
        return (f"| {c['season']} | {c['n_player_games']} | "
                f"{c['model_ou_accuracy']:.4f} | {c['market_ou_accuracy']:.4f} | "
                f"{c['paired_accuracy_diff_model_minus_market']:+.4f} | "
                f"[{ci['lo']:+.4f}, {ci['hi']:+.4f}] | "
                f"{c['market_brier_devig_p_over']:.4f} |")

    def dist_row(c):
        if c.get("status") == "NO_EVALUABLE_ROWS":
            return f"| {c['season']} | 0 | -- | -- | -- | -- |"
        b = c["threshold_distance_block"]
        ci = b["paired_diff_ci95"]
        return (f"| {c['season']} | {c['n_player_games']} | "
                f"{b['model_mean_abs_pred_minus_outcome']:.4f} | "
                f"{b['line_mean_abs_line_minus_outcome']:.4f} | "
                f"{b['paired_diff_model_minus_line']:+.4f} | "
                f"[{ci['lo']:+.4f}, {ci['hi']:+.4f}] |")

    verdict_sentence = {
        "YES": ("**Yes.** On the matched universe the legacy model's over/under "
                "calls beat the market's own de-vigged majority calls; the "
                "clustered 95% CI on the paired difference excludes zero."),
        "NO": ("**No.** On the matched universe the legacy model's over/under "
               "calls are beaten by the market's own de-vigged majority calls; "
               "the clustered 95% CI on the paired difference excludes zero."),
        "INCONCLUSIVE": ("**Inconclusive.** On the matched universe the paired "
                         "difference between the legacy model's over/under "
                         "calls and the market's de-vigged majority calls has "
                         "a clustered 95% CI that includes zero."),
    }[h["verdict"]]

    lines = [
        "# MODEL_VS_MARKET.md -- legacy points model vs the props market (FIRST comparison)",
        "",
        f"Generated {r['generated_utc']}. Evidence class **PRELIMINARY**. "
        "Authority: D023 / D027 / D034 / D036 / D037. No evidence-ladder label "
        "is claimed or held.",
        "",
        "## Headline (plain language)",
        "",
        "**Does the legacy points model beat the market's over/under calls?** "
        + verdict_sentence,
        "",
        f"- Universe: **{h['universe']}** (strict intersection; matched player-games only)",
        f"- N = {h['n']} player-games; model OU accuracy **{h['model_ou_accuracy']:.4f}** "
        f"vs market OU accuracy **{h['market_ou_accuracy']:.4f}**",
        f"- Paired difference (model - market): **{h['paired_diff']:+.4f}**, "
        f"game-date-clustered 95% CI **[{h['paired_diff_ci95'][0]:+.4f}, "
        f"{h['paired_diff_ci95'][1]:+.4f}]** (seed {r['seed']}, {r['n_boot']} draws)",
        f"- Market de-vigged Brier (P(over) vs outcome): **{h['market_brier']:.4f}**. "
        "The model has NO Brier: it is a point prediction, not a probability.",
        "",
        "**Timing honesty (read before using this number):** every timing "
        "aspect of the market side is **T1 / VENDOR_ASSERTED** (D027). The "
        "prop snapshot timestamps were never witnessed by this program; "
        "whether the legacy model's forecast cutoff truly preceded the "
        "market snapshot is **asserted, not witnessed**. In the "
        "vendor-asserted timeline the market snapshot (~T-65m) post-dates "
        "the model cutoff on all but "
        f"{ta['vendor_asserted_snapshot_minus_cutoff_hours']['n_negative_snapshot_asserted_before_cutoff']} "
        "of the evaluable rows (median gap "
        f"{ta['vendor_asserted_snapshot_minus_cutoff_hours']['median']:+.2f}h, "
        f"p95 {ta['vendor_asserted_snapshot_minus_cutoff_hours']['p95']:+.1f}h), "
        "i.e. the market saw later information than the model on those rows "
        "IF the vendor stamps are truthful. That asymmetry is advisory "
        "context (contract section 6.2 vendor-asserted channel), never a claim.",
        "",
        "**Bounded-use compliance (D027 -> M00-U2, caveat verbatim):**",
        "",
        f"> {r['m00_bounded_use']['caveat_text_verbatim']}",
        "",
        f"(caveat_hash `{r['m00_bounded_use']['caveat_hash']}`; object: "
        "`master_props_historical.csv`, T1_VENDOR_ASSERTED. No CLV, timing, "
        "lead-lag, stale-window or executability claim is made.)",
        "",
        "## 1. What was compared",
        "",
        "| side | quantity | source |",
        "|---|---|---|",
        "| model | `pred_point` of `player_scoring_distribution`, RECEIPTED legacy run "
        "`cbs_v15_player_oof_v5/1` (7/7 verification, VERIFICATION_REPORT.md); "
        "generation-consistent rows only (per-row forecast_cutoff byte-equal to the "
        "contract) | `experiments/cbs_v15_player_oof_v5/attempt_001/` |",
        "| market | de-vigged consensus threshold probability P(points > line) at the "
        "consensus line; vig removal DELEGATED to M11 `consensus.py` (preregistered "
        "multiplicative method, uniform weights) | `master_props_historical.csv` (T1) |",
        "| outcomes | owned regular-season gamelogs (hashes in json) | `data/` |",
        "",
        "Calls: model says OVER iff `pred_point > consensus_line`; the market says "
        "OVER iff de-vigged P(over) > 0.5. Consensus line = the line quoted "
        "two-sided by the most books (ties: nearest the median line, then lower); "
        "books at other lines are excluded and counted -- thresholds are never "
        "blended (D036 point 5). All lines are *.5 so no pushes exist (asserted "
        "in code).",
        "",
        f"## 2. OU-call accuracy, {HEADLINE_TIER} (headline universe)",
        "",
        "| season | N | model OU acc | market OU acc | paired diff | diff 95% CI (clustered) | market Brier |",
        "|---|---|---|---|---|---|---|",
    ]
    for k in ["2024", "2025", "2026", "pooled_2024_2026"]:
        lines.append(cell_row(cells[HEADLINE_TIER][k]))
    lines += [
        "",
        "## 3. OU-call accuracy, all_tiers (labelled aggregate, never the headline)",
        "",
        "| season | N | model OU acc | market OU acc | paired diff | diff 95% CI (clustered) | market Brier |",
        "|---|---|---|---|---|---|---|",
    ]
    for k in ["2024", "2025", "2026", "pooled_2024_2026"]:
        lines.append(cell_row(cells["all_tiers"][k]))
    lines += [
        "",
        "## 4. Threshold-distance comparison (NOT projection error)",
        "",
        "Per D036 point 5 this framing is explicitly distinct from projection "
        "MAE: `|consensus_line - outcome|` measures how far the betting "
        "THRESHOLD sat from the outcome. The line is not the market's point "
        "projection (it is set with vig and flow considerations), so the "
        "column pair below is model-projection-distance vs threshold-distance "
        "-- related, paired on identical rows, but never read as two "
        "projection errors.",
        "",
        f"### {HEADLINE_TIER}",
        "",
        "| season | N | mean \\|pred-outcome\\| | mean \\|line-outcome\\| | paired diff | diff 95% CI (clustered) |",
        "|---|---|---|---|---|---|",
    ]
    for k in ["2024", "2025", "2026", "pooled_2024_2026"]:
        lines.append(dist_row(cells[HEADLINE_TIER][k]))
    lines += [
        "",
        "### all_tiers",
        "",
        "| season | N | mean \\|pred-outcome\\| | mean \\|line-outcome\\| | paired diff | diff 95% CI (clustered) |",
        "|---|---|---|---|---|---|",
    ]
    for k in ["2024", "2025", "2026", "pooled_2024_2026"]:
        lines.append(dist_row(cells["all_tiers"][k]))

    pooled = cells[HEADLINE_TIER]["pooled_2024_2026"]
    lines += [
        "",
        "## 5. Full join audit (no silent drops)",
        "",
        "Market side (props archive -> consensus player-games):",
        "",
        f"- archive rows: {ja['market_side']['source']['n_rows']} over "
        f"{ja['market_side']['source']['n_games']} games (sha256 "
        f"`{ja['market_side']['source']['sha256'][:16]}...`, T1 per D027)",
        f"- in-play rows excluded (structural, contract 4.4): {ja['market_side']['n_inplay_rows_excluded']}",
        f"- one-sided rows excluded (cannot de-vig): "
        f"{ja['market_side']['n_one_sided_rows_excluded_cannot_devig']} "
        f"(by book: {json.dumps(ja['market_side']['one_sided_by_book'])})",
        f"- two-sided rows kept: {ja['market_side']['n_two_sided_rows']}; "
        f"same-book-same-line duplicates dropped: "
        f"{ja['market_side']['n_same_book_same_line_duplicate_rows_dropped']}",
        f"- unresolved player names (O14 normalized-exact + alias table; "
        f"excluded AND listed): {ja['market_side']['n_unresolved_player_rows_excluded']} rows"
        + ("" if not r['join_audit']['unresolved_player_names_excluded_and_listed']
           else " -- " + "; ".join(
               f"{u['player_name']} ({u['n_rows']} rows / {u['n_games']} games)"
               for u in r['join_audit']['unresolved_player_names_excluded_and_listed'])),
        f"- resolved two-sided prop player-games: {ja['market_side']['n_prop_player_games_resolved_two_sided']}; "
        f"book quotes excluded for sitting on a non-consensus line: "
        f"{ja['market_side']['n_book_quotes_excluded_non_consensus_line']}",
        "",
        "Model side (RECEIPTED legacy artifacts -> scored points rows):",
        "",
        f"- prediction rows (all seasons): {ja['model_side']['n_prediction_rows_all_seasons']}; "
        f"generation-inconsistent cutoff rows excluded: "
        f"{ja['model_side']['n_generation_inconsistent_cutoff_rows_excluded']}; "
        f"producer-excluded rows: {ja['model_side']['n_excluded_by_producer_exclusion_reason']}",
        f"- no gamelog outcome row: {ja['model_side']['n_no_gamelog_outcome_row']}; "
        f"outcome-team mismatch (dual obligations): "
        f"{ja['model_side']['n_outcome_team_differs_from_obligation_team']}; "
        f"zero-minute rows (conditional target): "
        f"{ja['model_side']['n_zero_minutes_excluded_conditional_target']}",
        f"- scored model rows: {ja['n_scored_model_rows_total']}",
        "",
        "Intersection:",
        "",
        f"- matched player-games: **{ja['n_matched_player_games']}** across "
        f"{ja['n_matched_games']} games "
        f"(market player-games with no matched model row: "
        f"{ja['n_market_rows_unmatched_no_scored_model_row']}; market games with "
        f"no matched row: {ja['n_market_games_with_no_matched_row']} -- see "
        "`unmatched_market_note` in the json)",
        f"- by tier: {json.dumps(ja['matched_by_tier'])}; by season: "
        f"{json.dumps(ja['matched_by_season'])}",
        f"- pushes (outcome == line): {ja['n_push_outcome_equals_line']}; "
        f"model no-call (pred == line): {ja['n_model_no_call_pred_equals_line']}; "
        f"market no-call (P(over) == 0.5): {ja['n_market_no_call_p_exactly_half']}",
        f"- evaluable matched player-games: **{ja['n_evaluable_matched_player_games']}**"
        f" (headline {HEADLINE_TIER} pooled cell: {pooled['n_player_games']})",
        "",
        "## 6. Provenance",
        "",
        f"- contract sha256 verified: `{r['contract']['sha256_verified']}`",
        f"- vig preregistration hash: `{ja['market_side']['consensus_method']['vig_preregistration_hash']}` "
        f"(method `{ja['market_side']['consensus_method']['vig_method']}`, "
        "frozen in consensus.py before any evaluation)",
        f"- consensus.py sha256: `{ja['market_side']['consensus_method']['module_sha256']}`",
        f"- prediction artifact sha256 (per season) and all input hashes: in "
        "`model_vs_market.json`",
        f"- commit: {r['commit_sha']}",
        f"- seed {r['seed']}, {r['n_boot']} bootstrap draws, clusters = game dates "
        "(same method as the granular scoreboard)",
        "",
        "Epistemic status of the consensus machinery (verbatim, per M11): "
        f"\"{ja['market_side']['consensus_method']['epistemic_status_line']}\"",
        "",
        "This number feeds the leaderboard **Market Advantage** column for the "
        "legacy points row, evidence class PRELIMINARY.",
        "",
    ]
    (HERE / "MODEL_VS_MARKET.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
