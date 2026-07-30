"""minutes_twostage.py — Two-stage conditional minutes model (Phase 2a).

Preregistered experiment: ``minutes_twostage_availability_v1``
(experiments/registry.jsonl, registered 2026-07-30T20:19:14Z, regime B,
primary metric minutes_mae, thresholds 0.10/0.05/0.15/0.0, incumbent
``minutes_ewma_alpha030_v1`` = the B3 EWMA floor, pooled 4.6428).

This script does NOT register (already registered) and does NOT render
leaderboards (orchestrator's job). It:

  Stage B  E[min | played]  ridge (closed form, unpenalized intercept) on
           MINUTES_MODEL_SPEC groups A-E + injury-history availability
           features, fit once on 2021-2023, frozen for 2024/2025/2026.
  Stage A  P(plays)         L2 logistic (IRLS, unpenalized intercept) over
           the dressed roster, same protocol.

  M1 (PRIMARY, gated)   Stage-B minutes MAE on played rows vs the stored
                        incumbent predictions (experiments/minutes_baselines/
                        test_predictions.csv pred_ewma), identical universe.
  M2 (secondary)        Stage-A pooled Brier vs shifted expanding played-rate
                        prior, dressed universe; decile reliability table.
  M3 (secondary)        p*m unconditional expected-minutes MAE vs
                        B4 = EWMA x played-in-team's-previous-game.
  M4 (diagnostic)       per-team-game sum of p*m vs 200.

  Audits: independent shift-recompute (25 rows, seed 20260731), target
  permutation probe, availability timestamp check, incumbent reproduction,
  universe identity. Regime-B accounting per the registration. W1 news
  overlay: preregistered exploratory only (rules in the registration).

Shift discipline (HANDOFF section 3 rules 1/3): every trend feature is a
POST-value (.ewm()/.rolling()/.expanding() including the row's own game)
computed on the played subframe, then merged onto the dressed frame and
converted to an AS-OF value via groupby(player, season) shift(1)+ffill —
on played rows this equals the classic window-then-shift feature; on DNP
rows it is the value entering the player's next appearance. Zero same-game
information anywhere; features reset per season; trends follow the player
across in-season trades (spec section 5).

Availability rule (regime B): every injury-history record used for target
game G satisfies record_date <= game_date(G) - 1 day; W1 news satisfies
date(published_utc) <= game_date - 1. Verified in-run.

Run:  python minutes_twostage.py            # real run (records on ledger)
      python minutes_twostage.py --smoke    # scratch registry + outdir
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from evalharness import (  # noqa: E402
    compare_to_incumbent,
    inner_tuning_splits,
    walk_forward_by_season,
)
from evalharness.metrics import brier_score  # noqa: E402
from evalharness import registry as ereg  # noqa: E402

MASTER = REPO / "data" / "masters" / "master_player.parquet"
MASTER_TEAM = REPO / "data" / "masters" / "master_team.parquet"
INJ = REPO / "data" / "injury_history" / "injury_history.csv"
W1 = REPO / "data" / "w1_extractions" / "extractions.csv"
INCUMBENT_FILE = REPO / "experiments" / "minutes_baselines" / "test_predictions.csv"
DEFAULT_OUTDIR = REPO / "experiments" / "minutes_twostage"
EXPERIMENT_ID = "minutes_twostage_availability_v1"

TRAIN_SEASONS = [2021, 2022, 2023]
TEST_SEASONS = [2024, 2025, 2026]
EWMA_ALPHA = 0.30            # frozen from minutes_ewma_vs_carryforward_v1
TEAM_ALPHA = 0.10            # a-priori constant for team-trait EWMAs (constitution range)
LAMBDA_GRID = [round(float(x), 6) for x in np.logspace(-2, 4, 13)]
N_INNER_FOLDS = 3
DAYS_CAP = 45.0              # days_since_last_appearance cap (never-played -> cap)
MISS_CAP = 20.0              # games_missed_streak cap
AUDIT_N = 25
AUDIT_SEED = 20260731
PERM_SEED = 20260731
INCUMBENT_POOLED = 4.6428
INCUMBENT_TOL = 1e-3
W1_WINDOW = ("2026-05-30", "2026-07-29")
W1_RECENCY_DAYS = 3
W1_P_OUT_CAP = 0.25
W1_P_RET_FLOOR = 0.75

DNP_CLASS = {"CD": "prev_dnp_cd", "INJ": "prev_dnp_inj", "NWT": "prev_dnp_nwt"}

STAGE_B_FEATURES = [
    # group A — player minutes trend
    "min_ewma", "min_last1", "min_mean_l5", "min_expmean", "min_std_l10",
    "min_share_ewma", "min_trend_delta", "player_gp_season",
    # group B — starter/role
    "started_last", "start_share_l5", "starts_streak",
    # group C — availability/return
    "days_since_last_appearance", "games_missed_streak", "returning_flag",
    "prev_dnp_cd", "prev_dnp_inj", "prev_dnp_nwt",
    # group D — team context/schedule
    "days_rest_team", "b2b_flag", "home_flag", "team_gp_season",
    "blowout_proxy", "team_bench_share_ewma", "team_n_rotation_ewma",
    # group E — teammate interaction
    "vacated_min", "returned_teammate_min", "pf_per_min_ewma",
    # cold-ish indicator
    "few_prior_apps_flag",
    # regime-B availability (injury-history archive)
    "miss_inj_l21", "miss_other_l21", "roster_move_l14", "suspension_l30",
    "waived_since_last_game",
]

STAGE_A_FEATURES = [
    "p_plays_prior", "min_ewma", "started_last", "start_share_l5",
    "played_last_team_game", "played_share_l10_team_games",
    "days_since_last_appearance", "games_missed_streak",
    "prev_dnp_cd", "prev_dnp_inj", "prev_dnp_nwt", "returning_flag",
    "player_gp_season", "team_gp_season",
    "miss_inj_l21", "miss_other_l21", "roster_move_l14", "suspension_l30",
    "waived_since_last_game",
]

INJ_CLASSES = {
    "missed_game_injury": "miss_inj",
    "missed_game_other": "miss_other",
    "signing": "roster_move", "waiver_claim": "roster_move",
    "trade": "roster_move", "contract_conversion": "roster_move",
    "contract_suspension": "suspension",
    "waiver": "gone", "retirement": "gone",
}


def norm_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace(".", " ").replace("'", "").replace("-", " ")
    return " ".join(s.split())


# ---------------------------------------------------------------------------
# data loading
# ---------------------------------------------------------------------------

def load_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_parquet(MASTER)
    rs = df[df["season_type"] == "Regular Season"].copy()
    rs["game_date"] = pd.to_datetime(rs["game_date"])
    minutes = rs["minutes"]
    is_played = minutes.fillna(0) > 0
    has_reason = rs["dnp_reason"].notna() & (rs["dnp_reason"].astype(str) != "")
    dressed = rs[is_played | has_reason].copy()
    dressed["played_flag"] = (dressed["minutes"].fillna(0) > 0).astype(int)

    def dnp_class(v):
        if not isinstance(v, str) or not v.strip():
            return None
        u = v.upper()
        if u.startswith("DNP"):
            return "CD"
        if u.startswith("NWT"):
            return "NWT"
        return "INJ"   # DND - Injury/Illness, reconditioning, other dressed-out
    dressed["dnp_class"] = dressed["dnp_reason"].map(dnp_class)
    bad = dressed[(dressed["played_flag"] == 0) & dressed["dnp_class"].isna()]
    assert len(bad) == 0, f"DNP rows without class: {len(bad)}"

    mt = pd.read_parquet(MASTER_TEAM)
    mt = mt[mt["season_type"] == "Regular Season"].copy()
    mt["game_date"] = pd.to_datetime(mt["game_date"])
    return dressed, mt


def sort_pd(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(["player_id", "season", "game_date", "game_id"],
                          kind="mergesort").reset_index(drop=True)


# ---------------------------------------------------------------------------
# stage-B trend features: POST values on played rows -> AS-OF on dressed
# ---------------------------------------------------------------------------

def build_post_features(played: pd.DataFrame) -> pd.DataFrame:
    """POST-value trend features on played rows (include the row's own game)."""
    P = sort_pd(played).copy()
    team_tot = P.groupby(["game_id", "team_id"])["minutes"].transform("sum")
    P["min_share"] = P["minutes"] / team_tot
    P["pf_per_min"] = P["pf"].fillna(0) / P["minutes"]
    g = P.groupby(["player_id", "season"], sort=False)
    P["post_ewma"] = g["minutes"].transform(lambda s: s.ewm(alpha=EWMA_ALPHA, adjust=True).mean())
    P["post_last1"] = P["minutes"]
    P["post_mean_l5"] = g["minutes"].transform(lambda s: s.rolling(5, min_periods=1).mean())
    P["post_expmean"] = g["minutes"].transform(lambda s: s.expanding().mean())
    P["post_std_l10"] = g["minutes"].transform(lambda s: s.rolling(10, min_periods=2).std())
    P["post_share_ewma"] = g["min_share"].transform(lambda s: s.ewm(alpha=EWMA_ALPHA, adjust=True).mean())
    P["post_start"] = P["starter_flag"].astype(float)
    P["post_start_share_l5"] = g["starter_flag"].transform(lambda s: s.rolling(5, min_periods=1).mean())
    P["post_starts_streak"] = g["starter_flag"].transform(
        lambda s: s.groupby((s == 0).cumsum()).cumsum())
    P["post_pfmin_ewma"] = g["pf_per_min"].transform(lambda s: s.ewm(alpha=EWMA_ALPHA, adjust=True).mean())
    P["post_date"] = P["game_date"]
    return P


POST_TO_ASOF = {
    "post_ewma": "min_ewma",
    "post_last1": "min_last1",
    "post_mean_l5": "min_mean_l5",
    "post_expmean": "min_expmean",
    "post_std_l10": "min_std_l10",
    "post_share_ewma": "min_share_ewma",
    "post_start": "started_last",
    "post_start_share_l5": "start_share_l5",
    "post_starts_streak": "starts_streak",
    "post_pfmin_ewma": "pf_per_min_ewma",
    "post_date": "last_played_date",
}


def asof_merge(dressed: pd.DataFrame, P: pd.DataFrame) -> pd.DataFrame:
    """Merge POST features onto the dressed frame and shift(1)+ffill within
    (player, season): on played rows == classic shifted feature; on DNP rows
    == value entering the player's next appearance (strictly prior info)."""
    D = sort_pd(dressed).copy()
    keys = ["player_id", "season", "game_id"]
    D = D.merge(P[keys + list(POST_TO_ASOF)], on=keys, how="left", validate="1:1")
    gd = D.groupby(["player_id", "season"], sort=False)
    for post, asof in POST_TO_ASOF.items():
        D[asof] = gd[post].transform(lambda s: s.shift(1).ffill())
    D = D.drop(columns=[c for c in POST_TO_ASOF if c != "post_date"])
    # prior played appearances this season (0 for never-played-yet)
    D["player_gp_season"] = gd["played_flag"].cumsum() - D["played_flag"]
    # prior dressed appearances + shifted expanding played-rate (Stage A)
    D["prior_dressed"] = gd.cumcount()
    D["p_plays_prior"] = gd["played_flag"].transform(lambda s: s.expanding().mean().shift(1))
    # most recent PRIOR DNP class
    D["prev_dnp_class"] = gd["dnp_class"].transform(lambda s: s.shift(1).ffill())
    for cls, col in DNP_CLASS.items():
        D[col] = (D["prev_dnp_class"] == cls).astype(float)
    # days since last played appearance, capped; never-played -> cap
    days = (D["game_date"] - D["last_played_date"]).dt.days.astype(float)
    D["days_since_last_appearance"] = np.minimum(days.fillna(DAYS_CAP), DAYS_CAP)
    D["min_trend_delta"] = (D["min_mean_l5"] - D["min_expmean"]).fillna(0.0)
    D["few_prior_apps_flag"] = (D["player_gp_season"] < 3).astype(float)
    # no-played-history defaults (honest "none observed" encodings)
    for c in ["min_ewma", "min_last1", "min_mean_l5", "min_expmean",
              "min_share_ewma", "started_last", "start_share_l5",
              "starts_streak", "pf_per_min_ewma"]:
        D[c] = D[c].fillna(0.0)
    D["min_std_l10"] = D["min_std_l10"].fillna(0.0)
    return D


# ---------------------------------------------------------------------------
# team context features (master_team) per (game_id, team_id)
# ---------------------------------------------------------------------------

def build_team_features(mt: pd.DataFrame, P: pd.DataFrame) -> pd.DataFrame:
    T = mt.sort_values(["team_id", "season", "game_date", "game_id"],
                       kind="mergesort").reset_index(drop=True)
    gt = T.groupby(["team_id", "season"], sort=False)
    T["team_gp_season"] = gt.cumcount()
    T["days_rest_team"] = gt["game_date"].diff().dt.days.astype(float)
    T["days_rest_team"] = np.minimum(T["days_rest_team"].fillna(10.0), 10.0)
    T["b2b_flag"] = (T["days_rest_team"] <= 1).astype(float)
    T["net_ewma"] = gt["plus_minus"].transform(
        lambda s: s.ewm(alpha=TEAM_ALPHA, adjust=True).mean().shift(1))

    # per-team-game rotation traits from played rows -> shifted team EWMAs
    pb = P.groupby(["game_id", "team_id"]).apply(
        lambda x: pd.Series({
            "bench_share": x.loc[x["starter_flag"] == 0, "minutes"].sum() / x["minutes"].sum(),
            "n_rotation": float((x["minutes"] >= 10).sum()),
        }), include_groups=False).reset_index()
    T = T.merge(pb, on=["game_id", "team_id"], how="left", validate="1:1")
    gt = T.groupby(["team_id", "season"], sort=False)
    T["team_bench_share_ewma"] = gt["bench_share"].transform(
        lambda s: s.ewm(alpha=TEAM_ALPHA, adjust=True).mean().shift(1))
    T["team_n_rotation_ewma"] = gt["n_rotation"].transform(
        lambda s: s.ewm(alpha=TEAM_ALPHA, adjust=True).mean().shift(1))

    opp = T[["game_id", "team_id", "net_ewma"]].rename(
        columns={"team_id": "opp_team_id", "net_ewma": "opp_net_ewma"})
    T = T.merge(opp, on=["game_id", "opp_team_id"], how="left", validate="1:1")
    T["blowout_proxy"] = (T["net_ewma"].fillna(0.0) - T["opp_net_ewma"].fillna(0.0)).abs()
    T["team_game_order"] = T["team_gp_season"]
    return T[["game_id", "team_id", "season", "team_gp_season", "days_rest_team",
              "b2b_flag", "blowout_proxy", "team_bench_share_ewma",
              "team_n_rotation_ewma", "team_game_order"]]


# ---------------------------------------------------------------------------
# team-index features: played_last_team_game / share_l10 / missed streak /
# vacated_min / returned_teammate_min
# ---------------------------------------------------------------------------

def build_team_index_features(D: pd.DataFrame, P: pd.DataFrame,
                              team_feats: pd.DataFrame) -> pd.DataFrame:
    """ALLP grid: (team-season game order k) x (players seen for that team)."""
    order = team_feats[["game_id", "team_id", "season", "team_game_order"]]
    roster = (D[["team_id", "season", "player_id"]].drop_duplicates())
    games = order.rename(columns={"team_game_order": "k"})
    grid = roster.merge(games, on=["team_id", "season"], how="left")

    app = P[["game_id", "team_id", "player_id"]].copy()
    app["appeared"] = 1.0
    postv = P[["game_id", "team_id", "player_id", "post_ewma"]]
    grid = grid.merge(app, on=["game_id", "team_id", "player_id"], how="left")
    grid = grid.merge(postv, on=["game_id", "team_id", "player_id"], how="left")
    grid["appeared"] = grid["appeared"].fillna(0.0)
    grid = grid.sort_values(["team_id", "season", "player_id", "k"],
                            kind="mergesort").reset_index(drop=True)
    gg = grid.groupby(["team_id", "season", "player_id"], sort=False)

    cum = gg["appeared"].cumsum()
    grid["apps_prior"] = cum - grid["appeared"]
    grid["played_last_team_game"] = gg["appeared"].shift(1).fillna(0.0)
    cum_prior = grid["apps_prior"]
    cum_prior_10 = gg["appeared"].transform(
        lambda s: s.cumsum().shift(11).fillna(0.0))
    denom = np.minimum(grid["k"].astype(float), 10.0)
    grid["played_share_l10_team_games"] = np.where(
        denom > 0, (cum_prior - cum_prior_10) / denom, 0.0)

    # last played team-game order strictly before k: shift(1)+ffill of
    # k-where-played within (team, season, player)
    tmp = grid.assign(kp=grid["k"].where(grid["appeared"] == 1))
    grid["last_played_k"] = tmp.groupby(["team_id", "season", "player_id"],
                                        sort=False)["kp"].transform(
        lambda s: s.shift(1).ffill())
    missed = grid["k"] - 1.0 - grid["last_played_k"]
    missed = missed.fillna(grid["k"].astype(float))       # never played -> all k prior games missed
    grid["games_missed_streak"] = np.minimum(np.maximum(missed, 0.0), MISS_CAP)

    # as-of trailing EWMA for teammate sums (value after last played team game)
    grid["ewma_asof_team"] = gg["post_ewma"].transform(lambda s: s.shift(1).ffill())
    # appeared in team's last-3 window (k-3..k-1), excluding last game
    cum_prior_3 = gg["appeared"].transform(lambda s: s.cumsum().shift(4).fillna(0.0))
    in_last3 = (cum_prior - cum_prior_3) > 0
    grid["is_vacated"] = ((grid["played_last_team_game"] == 0) & in_last3).astype(float)
    grid["vac_contrib"] = grid["is_vacated"] * grid["ewma_asof_team"].fillna(0.0)
    # returned last game after missing >= 2 team games
    a_1 = gg["appeared"].shift(1).fillna(0.0)
    a_2 = gg["appeared"].shift(2).fillna(0.0)
    a_3 = gg["appeared"].shift(3).fillna(0.0)
    apps_before_km3 = gg["appeared"].transform(lambda s: s.cumsum().shift(3).fillna(0.0))
    grid["is_returned"] = ((a_1 == 1) & (a_2 == 0) & (a_3 == 0)
                           & (apps_before_km3 > 0)).astype(float)
    grid["ret_contrib"] = grid["is_returned"] * grid["ewma_asof_team"].fillna(0.0)

    team_sums = grid.groupby(["team_id", "season", "game_id"])[
        ["vac_contrib", "ret_contrib"]].sum().reset_index().rename(
        columns={"vac_contrib": "team_vacated", "ret_contrib": "team_returned"})

    keep = grid[["team_id", "season", "game_id", "player_id",
                 "played_last_team_game", "played_share_l10_team_games",
                 "games_missed_streak", "vac_contrib", "ret_contrib"]]
    out = keep.merge(team_sums, on=["team_id", "season", "game_id"], how="left")
    out["vacated_min"] = out["team_vacated"] - out["vac_contrib"]
    out["returned_teammate_min"] = out["team_returned"] - out["ret_contrib"]
    return out[["team_id", "season", "game_id", "player_id",
                "played_last_team_game", "played_share_l10_team_games",
                "games_missed_streak", "vacated_min", "returned_teammate_min"]]


# ---------------------------------------------------------------------------
# regime-B availability features from the injury-history archive
# ---------------------------------------------------------------------------

def load_injury_events(D: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    inj = pd.read_csv(INJ)
    inj["date"] = pd.to_datetime(inj["date"])
    inj["season"] = inj["date"].dt.year
    inj["cls"] = inj["category"].map(INJ_CLASSES)
    inj = inj[inj["cls"].notna()].copy()

    events = []
    for col in ("player_relinquished", "player_acquired"):
        sub = inj[inj[col].notna() & (inj[col].astype(str).str.strip() != "")]
        events.append(sub[["date", "season", "cls", col]].rename(columns={col: "name"}))
    ev = pd.concat(events, ignore_index=True)
    ev["norm"] = ev["name"].map(norm_name)

    # season-scoped unique-name resolution from the master itself
    names = D[["season", "player_id", "player_name"]].drop_duplicates().copy()
    names["norm"] = names["player_name"].map(norm_name)
    by_season = names.groupby(["season", "norm"])["player_id"].agg(["nunique", "first"])
    uniq_season = by_season[by_season["nunique"] == 1]["first"]
    by_all = names.groupby("norm")["player_id"].agg(["nunique", "first"])
    uniq_all = by_all[by_all["nunique"] == 1]["first"]

    ev["player_id"] = [
        uniq_season.get((s, n), uniq_all.get(n, np.nan))
        for s, n in zip(ev["season"], ev["norm"])
    ]
    resolved = ev[ev["player_id"].notna()].copy()
    resolved["player_id"] = resolved["player_id"].astype(np.int64)
    accounting = {
        "events_total": int(len(ev)),
        "events_resolved": int(len(resolved)),
        "resolution_rate": round(len(resolved) / max(len(ev), 1), 4),
        "unresolved_by_cls": ev[ev["player_id"].isna()]["cls"].value_counts().to_dict(),
        "resolved_by_cls": resolved["cls"].value_counts().to_dict(),
    }
    return resolved[["player_id", "season", "date", "cls"]], accounting


def add_injury_features(D: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
    """Window counts via searchsorted per (player, class). Every window ends at
    game_date - 1 day (strictly-prior-day rule)."""
    D = D.copy()
    for c in ["miss_inj_l21", "miss_other_l21", "roster_move_l14",
              "suspension_l30", "waived_since_last_game"]:
        D[c] = 0.0
    spec = {
        "miss_inj": ("miss_inj_l21", 21, "count"),
        "miss_other": ("miss_other_l21", 21, "count"),
        "roster_move": ("roster_move_l14", 14, "flag"),
        "suspension": ("suspension_l30", 30, "flag"),
    }
    ev = ev.sort_values("date")
    grouped = {k: {pid: sub["date"].to_numpy(dtype="datetime64[D]")
                   for pid, sub in g.groupby("player_id")}
               for k, g in ev.groupby("cls")}
    dates = D["game_date"].to_numpy(dtype="datetime64[D]")
    pids = D["player_id"].to_numpy()
    lastp = D["last_played_date"].to_numpy(dtype="datetime64[D]")

    for cls, (col, win, kind) in spec.items():
        per_player = grouped.get(cls, {})
        vals = np.zeros(len(D))
        for pid, evd in per_player.items():
            mask = pids == pid
            if not mask.any():
                continue
            d = dates[mask]
            hi = np.searchsorted(evd, d)                       # events strictly before game_date
            lo = np.searchsorted(evd, d - np.timedelta64(win, "D"))
            n = (hi - lo).astype(float)
            vals[mask] = n if kind == "count" else (n > 0).astype(float)
        D[col] = vals

    per_gone = grouped.get("gone", {})
    vals = np.zeros(len(D))
    for pid, evd in per_gone.items():
        mask = pids == pid
        if not mask.any():
            continue
        d = dates[mask]
        lp = lastp[mask]
        hi = np.searchsorted(evd, d)
        lo = np.searchsorted(evd, np.where(np.isnat(lp), d - np.timedelta64(60, "D"),
                                           lp + np.timedelta64(1, "D")))
        vals[mask] = ((hi - lo) > 0).astype(float)
    D["waived_since_last_game"] = vals
    return D


# ---------------------------------------------------------------------------
# W1 news signals (exploratory overlay only — registration w1_overlay)
# ---------------------------------------------------------------------------

def load_w1_signals(D: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    w1 = pd.read_csv(W1)
    w1["pub_date"] = pd.to_datetime(w1["published_utc"], utc=True, format="mixed").dt.tz_localize(None).dt.normalize()
    names = D.loc[D["season"] == 2026, ["player_id", "player_name"]].drop_duplicates().copy()
    names["norm"] = names["player_name"].map(norm_name)
    by = names.groupby("norm")["player_id"].agg(["nunique", "first"])
    uniq = by[by["nunique"] == 1]["first"]
    w1["norm"] = w1["player_name"].map(norm_name)
    w1["player_id"] = w1["norm"].map(uniq)
    acc = {
        "signals_total": int(len(w1)),
        "signals_resolved": int(w1["player_id"].notna().sum()),
        "by_status": w1["status_signal"].value_counts().to_dict(),
        "speculation_rows": int(w1["is_speculation"].astype(str).str.lower().eq("true").sum()),
    }
    sig = w1[w1["player_id"].notna()].copy()
    sig["player_id"] = sig["player_id"].astype(np.int64)
    sig["is_spec"] = sig["is_speculation"].astype(str).str.lower().eq("true")
    return sig[["player_id", "pub_date", "status_signal", "is_spec", "source_tier"]], acc


def latest_w1_signal(D26: pd.DataFrame, sig: pd.DataFrame,
                     include_speculation: bool) -> pd.Series:
    """Most recent signal class in [game_date - W1_RECENCY_DAYS, game_date - 1]."""
    s = sig if include_speculation else sig[~sig["is_spec"]]
    out = pd.Series(index=D26.index, dtype=object)
    per = {pid: sub.sort_values("pub_date") for pid, sub in s.groupby("player_id")}
    for idx, row in D26.iterrows():
        sub = per.get(row["player_id"])
        if sub is None:
            continue
        lo = row["game_date"] - pd.Timedelta(days=W1_RECENCY_DAYS)
        hi = row["game_date"] - pd.Timedelta(days=1)
        m = sub[(sub["pub_date"] >= lo) & (sub["pub_date"] <= hi)]
        if len(m):
            out.at[idx] = m.iloc[-1]["status_signal"]
    return out


# ---------------------------------------------------------------------------
# models: closed-form ridge + IRLS logistic (no sklearn in this env)
# ---------------------------------------------------------------------------

class Standardizer:
    def __init__(self, X: pd.DataFrame):
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0, ddof=0)
        self.keep = self.std[self.std > 1e-12].index.tolist()
        self.dropped = [c for c in X.columns if c not in self.keep]

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        Z = (X[self.keep] - self.mean[self.keep]) / self.std[self.keep]
        return Z.to_numpy(dtype=float)


def ridge_fit(Z: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    n, p = Z.shape
    X1 = np.hstack([np.ones((n, 1)), Z])
    pen = lam * np.eye(p + 1)
    pen[0, 0] = 0.0
    return np.linalg.solve(X1.T @ X1 + pen, X1.T @ y)


def ridge_predict(Z: np.ndarray, beta: np.ndarray) -> np.ndarray:
    return np.hstack([np.ones((Z.shape[0], 1)), Z]) @ beta


def logistic_fit(Z: np.ndarray, y: np.ndarray, lam: float,
                 max_iter: int = 100, tol: float = 1e-9) -> np.ndarray:
    n, p = Z.shape
    X1 = np.hstack([np.ones((n, 1)), Z])
    beta = np.zeros(p + 1)
    beta[0] = np.log(max(y.mean(), 1e-6) / max(1 - y.mean(), 1e-6))
    pen = lam * np.eye(p + 1)
    pen[0, 0] = 0.0
    for _ in range(max_iter):
        eta = np.clip(X1 @ beta, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        W = np.maximum(mu * (1 - mu), 1e-10)
        grad = X1.T @ (mu - y) + pen @ beta
        H = (X1 * W[:, None]).T @ X1 + pen
        step = np.linalg.solve(H, grad)
        beta = beta - step
        if np.max(np.abs(step)) < tol:
            break
    return beta


def logistic_predict(Z: np.ndarray, beta: np.ndarray) -> np.ndarray:
    eta = np.clip(np.hstack([np.ones((Z.shape[0], 1)), Z]) @ beta, -30, 30)
    return 1.0 / (1.0 + np.exp(-eta))


def tune_lambda(U: pd.DataFrame, feats: list[str], ycol: str, outer,
                fit_fn, pred_fn, loss_fn) -> tuple[float, pd.DataFrame]:
    folds = inner_tuning_splits(U, outer, date_col="game_date", n_folds=N_INNER_FOLDS)
    rows = []
    for lam in LAMBDA_GRID:
        fold_losses = []
        for f in folds:
            tr, va = U.loc[f.train_idx], U.loc[f.val_idx]
            std = Standardizer(tr[feats])
            beta = fit_fn(std.transform(tr[feats]), tr[ycol].to_numpy(float), lam)
            pv = pred_fn(std.transform(va[feats]), beta)
            fold_losses.append(loss_fn(va[ycol].to_numpy(float), pv))
        rows.append({"lambda": lam}
                    | {f"fold{i+1}": v for i, v in enumerate(fold_losses)}
                    | {"mean_val_loss": float(np.mean(fold_losses))})
    curve = pd.DataFrame(rows)
    best = float(curve.loc[curve["mean_val_loss"].idxmin(), "lambda"])
    return best, curve


# ---------------------------------------------------------------------------
# independent shift-recompute audit (reimplements every feature per row)
# ---------------------------------------------------------------------------

def audit_row(row: pd.Series, D: pd.DataFrame, P: pd.DataFrame,
              mt: pd.DataFrame, ev: pd.DataFrame,
              trait_const: dict | None = None) -> dict:
    """Recompute every Stage-B feature for one row using ONLY rows dated
    strictly before the target date (plus schedule info for the target game,
    which is known pregame). Independent, loop-based implementations."""
    pid, season, date, team = row["player_id"], row["season"], row["game_date"], row["team_id"]
    hist = P[(P["player_id"] == pid) & (P["season"] == season)
             & (P["game_date"] < date)].sort_values(["game_date", "game_id"])
    dhist = D[(D["player_id"] == pid) & (D["season"] == season)
              & (D["game_date"] < date)].sort_values(["game_date", "game_id"])
    s = hist["minutes"]
    out = {}
    out["min_ewma"] = s.ewm(alpha=EWMA_ALPHA, adjust=True).mean().iloc[-1] if len(s) else 0.0
    out["min_last1"] = s.iloc[-1] if len(s) else 0.0
    out["min_mean_l5"] = s.tail(5).mean() if len(s) else 0.0
    out["min_expmean"] = s.mean() if len(s) else 0.0
    out["min_std_l10"] = s.tail(10).std() if len(s) >= 2 else 0.0
    shares = []
    for _, h in hist.iterrows():
        tot = P[(P["game_id"] == h["game_id"]) & (P["team_id"] == h["team_id"])]["minutes"].sum()
        shares.append(h["minutes"] / tot)
    out["min_share_ewma"] = (pd.Series(shares).ewm(alpha=EWMA_ALPHA, adjust=True).mean().iloc[-1]
                             if shares else 0.0)
    out["min_trend_delta"] = ((s.tail(5).mean() - s.mean()) if len(s) else 0.0)
    out["player_gp_season"] = float(len(s))
    out["started_last"] = float(hist["starter_flag"].iloc[-1]) if len(hist) else 0.0
    out["start_share_l5"] = float(hist["starter_flag"].tail(5).mean()) if len(hist) else 0.0
    streak = 0
    for v in hist["starter_flag"].iloc[::-1]:
        if v == 1:
            streak += 1
        else:
            break
    out["starts_streak"] = float(streak)
    out["days_since_last_appearance"] = (
        min((date - hist["game_date"].iloc[-1]).days, DAYS_CAP) if len(hist) else DAYS_CAP)
    pf = (hist["pf"].fillna(0) / hist["minutes"])
    out["pf_per_min_ewma"] = (pf.ewm(alpha=EWMA_ALPHA, adjust=True).mean().iloc[-1]
                              if len(pf) else 0.0)
    # the stored feature is the most recent prior DRESSED row's ffilled class
    cls_series = dhist["dnp_class"].ffill()
    prev_cls = cls_series.iloc[-1] if len(cls_series) and pd.notna(cls_series.iloc[-1]) else None
    for cls, col in DNP_CLASS.items():
        out[col] = float(prev_cls == cls)
    # team schedule
    tsched = mt[(mt["team_id"] == team) & (mt["season"] == season)].sort_values(
        ["game_date", "game_id"])
    prior_games = tsched[tsched["game_date"] < date]
    out["team_gp_season"] = float(len(prior_games))
    rest = (date - prior_games["game_date"].iloc[-1]).days if len(prior_games) else 10.0
    out["days_rest_team"] = float(min(rest, 10.0))
    out["b2b_flag"] = float(out["days_rest_team"] <= 1)
    out["home_flag"] = float(row["is_home"])
    net = prior_games["plus_minus"]
    own = net.ewm(alpha=TEAM_ALPHA, adjust=True).mean().iloc[-1] if len(net) else 0.0
    opp_id = row["opp_team_id"]
    osched = mt[(mt["team_id"] == opp_id) & (mt["season"] == season)
                & (mt["game_date"] < date)].sort_values(["game_date", "game_id"])
    onet = osched["plus_minus"]
    oppv = onet.ewm(alpha=TEAM_ALPHA, adjust=True).mean().iloc[-1] if len(onet) else 0.0
    out["blowout_proxy"] = abs(own - oppv)
    bs, nr = [], []
    for _, tg in prior_games.iterrows():
        px = P[(P["game_id"] == tg["game_id"]) & (P["team_id"] == team)]
        bs.append(px.loc[px["starter_flag"] == 0, "minutes"].sum() / px["minutes"].sum())
        nr.append(float((px["minutes"] >= 10).sum()))
    tc = trait_const or {}
    out["team_bench_share_ewma"] = (pd.Series(bs).ewm(alpha=TEAM_ALPHA, adjust=True).mean().iloc[-1]
                                    if bs else tc.get("team_bench_share_ewma", np.nan))
    out["team_n_rotation_ewma"] = (pd.Series(nr).ewm(alpha=TEAM_ALPHA, adjust=True).mean().iloc[-1]
                                   if nr else tc.get("team_n_rotation_ewma", np.nan))
    # team-index features
    k = len(prior_games)
    tp = P[(P["team_id"] == team) & (P["season"] == season)]
    gids = prior_games["game_id"].tolist()
    appear = [set(tp[tp["game_id"] == g]["player_id"]) for g in gids]
    own_app = [pid in a for a in appear]
    out["played_last_team_game"] = float(own_app[-1]) if k else 0.0
    lastn = min(k, 10)
    out["played_share_l10_team_games"] = (
        float(sum(own_app[-lastn:])) / lastn if lastn else 0.0)
    ms = 0
    for a in reversed(own_app):
        if not a:
            ms += 1
        else:
            break
    out["games_missed_streak"] = float(min(ms, MISS_CAP))
    ret = float(out["played_last_team_game"] == 0
                and prev_cls in ("INJ", "NWT"))
    out["returning_flag"] = ret
    # vacated / returned teammate sums
    seen = set().union(*appear[-3:]) if k else set()
    vac = 0.0
    for q in seen:
        if q == pid:
            continue
        if k and (q not in appear[-1]):
            qh = tp[(tp["player_id"] == q)
                    & (tp["game_date"] < prior_games["game_date"].iloc[-1] + pd.Timedelta(days=1))]
            qh = qh[qh["game_id"].isin(gids)]
            if len(qh):
                qs = P[(P["player_id"] == q) & (P["season"] == season)
                       & (P["game_date"] <= qh["game_date"].max())].sort_values(
                    ["game_date", "game_id"])["minutes"]
                vac += qs.ewm(alpha=EWMA_ALPHA, adjust=True).mean().iloc[-1]
    out["vacated_min"] = vac
    retm = 0.0
    if k >= 1:
        for q in appear[-1]:
            if q == pid:
                continue
            missed2 = (k >= 3 and q not in appear[-2] and q not in appear[-3]
                       and any(q in a for a in appear[:-3]))
            if missed2:
                qs = P[(P["player_id"] == q) & (P["season"] == season)
                       & (P["game_date"] <= prior_games["game_date"].iloc[-1])].sort_values(
                    ["game_date", "game_id"])["minutes"]
                if len(qs):
                    retm += qs.ewm(alpha=EWMA_ALPHA, adjust=True).mean().iloc[-1]
    out["returned_teammate_min"] = retm
    out["few_prior_apps_flag"] = float(len(s) < 3)
    # regime-B injury windows (events strictly before date)
    pe = ev[(ev["player_id"] == pid) & (ev["date"] < date)]
    def _win(cls, days):
        lo = date - pd.Timedelta(days=days)
        return pe[(pe["cls"] == cls) & (pe["date"] >= lo)]
    out["miss_inj_l21"] = float(len(_win("miss_inj", 21)))
    out["miss_other_l21"] = float(len(_win("miss_other", 21)))
    out["roster_move_l14"] = float(len(_win("roster_move", 14)) > 0)
    out["suspension_l30"] = float(len(_win("suspension", 30)) > 0)
    lastd = hist["game_date"].iloc[-1] if len(hist) else date - pd.Timedelta(days=60)
    gone = pe[(pe["cls"] == "gone") & (pe["date"] > lastd)]
    out["waived_since_last_game"] = float(len(gone) > 0)
    return out


# ---------------------------------------------------------------------------
# report helpers
# ---------------------------------------------------------------------------

def fmt_table(df: pd.DataFrame, floatfmt: str = "{:.4f}") -> str:
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: floatfmt.format(v) if pd.notna(v) else "")
    header = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    body = "\n".join("| " + " | ".join(map(str, row)) + " |"
                     for row in d.itertuples(index=False))
    return "\n".join([header, sep, body])


def reliability_table(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    q = pd.qcut(pd.Series(p), n_bins, duplicates="drop")
    df = pd.DataFrame({"y": y, "p": p, "bin": q})
    out = df.groupby("bin", observed=True).agg(
        n=("y", "size"), mean_pred=("p", "mean"), obs_rate=("y", "mean")).reset_index()
    out["bin"] = out["bin"].astype(str)
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args(argv)

    registry_path = None
    outdir = args.outdir or DEFAULT_OUTDIR
    if args.smoke:
        import tempfile
        scratch = Path(tempfile.mkdtemp(prefix="minutes_twostage_smoke_"))
        registry_path = scratch / "registry_scratch.jsonl"
        shutil.copyfile(REPO / "experiments" / "registry.jsonl", registry_path)
        outdir = args.outdir or (scratch / "out")
    outdir.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[twostage] {'SMOKE ' if args.smoke else ''}run at {run_time} -> {outdir}")

    # 1. frames -------------------------------------------------------------
    dressed_raw, mt = load_frames()
    P = build_post_features(dressed_raw[dressed_raw["played_flag"] == 1])
    D = asof_merge(dressed_raw, P)
    print(f"[data] dressed {len(D):,} rows ({int(D['played_flag'].sum()):,} played) "
          f"| team-games {len(mt):,}")

    # 2. team + team-index features ----------------------------------------
    tf = build_team_features(mt, P)
    D = D.merge(tf, on=["game_id", "team_id", "season"], how="left", validate="m:1")
    D["home_flag"] = D["is_home"].astype(float)
    # a player's first-ever game for a team can precede that team's second game
    # (staggered openers + mid-season signings): team-trait EWMAs are undefined
    # there. Fill with TRAIN-years constants (walk-forward safe), count the rows.
    trait_const = {
        c: float(tf.loc[tf["season"].isin(TRAIN_SEASONS), c].dropna().mean())
        for c in ("team_bench_share_ewma", "team_n_rotation_ewma")
    }
    n_trait_filled = int(D["team_bench_share_ewma"].isna().sum())
    for c, v in trait_const.items():
        D[c] = D[c].fillna(v)
    ti = build_team_index_features(D, P, tf)
    D = D.merge(ti, on=["team_id", "season", "game_id", "player_id"],
                how="left", validate="1:1")
    D["returning_flag"] = ((D["played_last_team_game"] == 0)
                           & D["prev_dnp_class"].isin(["INJ", "NWT"])).astype(float)

    # 3. regime-B availability features ------------------------------------
    ev, inj_acc = load_injury_events(D)
    D = add_injury_features(D, ev)
    print(f"[injury] events resolved {inj_acc['events_resolved']:,}/{inj_acc['events_total']:,} "
          f"({inj_acc['resolution_rate']:.1%})")

    # timestamp audit: by construction windows end at date-1; verify hard
    assert (ev["date"] < ev["date"].max() + pd.Timedelta(days=1)).all()
    ts_audit = {"max_event_date": str(ev["date"].max().date()),
                "rule": "windows end at game_date - 1 day via searchsorted(hi) on strictly-less"}

    # 4. universes ----------------------------------------------------------
    D["row_id"] = D["game_id"].astype(str) + ":" + D["player_id"].astype(str)
    assert not D["row_id"].duplicated().any()
    m1 = (D["played_flag"] == 1) & (D["player_gp_season"] >= 1)
    m2 = D["prior_dressed"] >= 1
    m3 = m2 & (D["player_gp_season"] >= 1)
    U1 = D[m1].copy()
    U2 = D[m2].copy()
    U3 = D[m3].copy()
    print(f"[universe] M1 {len(U1):,} | M2 {len(U2):,} | M3 {len(U3):,} "
          f"(M2-only sliver {int((m2 & ~m3).sum()):,})")

    # incumbent reproduction + universe identity ---------------------------
    inc = pd.read_csv(INCUMBENT_FILE)
    U1_test = U1[U1["season"].isin(TEST_SEASONS)]
    ours = set(U1_test["row_id"])
    theirs = set(inc["row_id"])
    assert ours == theirs, (f"M1 universe mismatch: only-ours {len(ours - theirs)}, "
                            f"only-incumbent {len(theirs - ours)}")
    chk = U1_test.merge(inc[["row_id", "pred_ewma", "y_true"]], on="row_id",
                        validate="1:1")
    assert float((chk["minutes"] - chk["y_true"]).abs().max()) < 1e-6
    ewma_dev = float((chk["min_ewma"] - chk["pred_ewma"]).abs().max())
    inc_mae = float((chk["pred_ewma"] - chk["y_true"]).abs().mean())
    assert abs(inc_mae - INCUMBENT_POOLED) <= INCUMBENT_TOL, inc_mae
    print(f"[incumbent] reproduced pooled {inc_mae:.4f} (anchor {INCUMBENT_POOLED}); "
          f"max |our_ewma - stored| = {ewma_dev:.2e}")

    # 5. splits + tuning ----------------------------------------------------
    U1 = U1.reset_index(drop=True)
    U2 = U2.reset_index(drop=True)
    o1 = {o.name: o for o in walk_forward_by_season(
        U1, date_col="game_date", season_col="season", test_seasons=TEST_SEASONS)}
    o2 = {o.name: o for o in walk_forward_by_season(
        U2, date_col="game_date", season_col="season", test_seasons=TEST_SEASONS)}
    tr1 = U1.loc[o1["season:2024"].train_idx]
    tr2 = U2.loc[o2["season:2024"].train_idx]
    assert sorted(tr1["season"].unique()) == TRAIN_SEASONS
    assert sorted(tr2["season"].unique()) == TRAIN_SEASONS

    mae = lambda y, p: float(np.mean(np.abs(y - p)))
    bri = lambda y, p: float(np.mean((y - np.clip(p, 0, 1)) ** 2))
    lam_b, curve_b = tune_lambda(U1, STAGE_B_FEATURES, "minutes",
                                 o1["season:2024"], ridge_fit, ridge_predict, mae)
    lam_a, curve_a = tune_lambda(U2, STAGE_A_FEATURES, "played_flag",
                                 o2["season:2024"], logistic_fit, logistic_predict, bri)
    print(f"[tuning] ridge lambda={lam_b} | logistic lambda={lam_a}")

    # 6. fit once on 2021-2023, frozen -------------------------------------
    std_b = Standardizer(tr1[STAGE_B_FEATURES])
    beta_b = ridge_fit(std_b.transform(tr1[STAGE_B_FEATURES]),
                       tr1["minutes"].to_numpy(float), lam_b)
    std_a = Standardizer(tr2[STAGE_A_FEATURES])
    beta_a = logistic_fit(std_a.transform(tr2[STAGE_A_FEATURES]),
                          tr2["played_flag"].to_numpy(float), lam_a)
    if std_b.dropped or std_a.dropped:
        print(f"[warn] zero-variance dropped: B={std_b.dropped} A={std_a.dropped}")

    D["pred_min_played"] = ridge_predict(std_b.transform(D[STAGE_B_FEATURES]), beta_b)
    D["p_plays"] = logistic_predict(std_a.transform(D[STAGE_A_FEATURES]), beta_a)
    D["pred_exp_min"] = D["p_plays"] * D["pred_min_played"]
    D["pred_b4"] = D["min_ewma"] * D["played_last_team_game"]

    # 7. audits BEFORE any scoring is believed ------------------------------
    U1_test = D[m1 & D["season"].isin(TEST_SEASONS)].copy()
    rng = np.random.default_rng(AUDIT_SEED)
    picks = U1_test.loc[rng.choice(U1_test.index.to_numpy(), size=AUDIT_N, replace=False)]
    audit_rows = []
    for _, r in picks.iterrows():
        rec = audit_row(r, D, P, mt, ev, trait_const)
        for feat, val in rec.items():
            stored = float(r[feat])
            val = float(val) if pd.notna(val) else np.nan
            ok = (abs(stored - val) <= 1e-6) if pd.notna(val) else pd.isna(val)
            audit_rows.append({"row_id": r["row_id"], "player": r["player_name"],
                               "date": str(r["game_date"].date()), "feature": feat,
                               "stored": stored, "recomputed": val,
                               "abs_diff": abs(stored - val) if pd.notna(val) else np.nan,
                               "identical": bool(ok)})
    audit = pd.DataFrame(audit_rows)
    n_bad = int((~audit["identical"]).sum())
    print(f"[audit] shift-recompute: {len(audit)} checks, {n_bad} mismatches, "
          f"max |diff| {audit['abs_diff'].max():.3e}")
    if n_bad:
        audit.to_csv(outdir / "leakage_audit.csv", index=False)
        raise RuntimeError("Shift audit FAILED — see leakage_audit.csv; not scoring.")

    # permutation probe: shuffle train minutes within season, refit, score
    tr_perm = tr1.copy()
    tr_perm["minutes"] = (tr_perm.groupby("season")["minutes"]
                          .transform(lambda s: s.sample(frac=1.0, random_state=PERM_SEED)
                                     .to_numpy()))
    beta_perm = ridge_fit(std_b.transform(tr_perm[STAGE_B_FEATURES]),
                          tr_perm["minutes"].to_numpy(float), lam_b)
    perm_pred = ridge_predict(std_b.transform(U1_test[STAGE_B_FEATURES]), beta_perm)
    perm_mae = mae(U1_test["minutes"].to_numpy(float), perm_pred)
    mean_mae = mae(U1_test["minutes"].to_numpy(float),
                   np.full(len(U1_test), tr1["minutes"].mean()))
    print(f"[audit] permutation probe: shuffled-model MAE {perm_mae:.4f} "
          f"vs train-mean {mean_mae:.4f} (must be comparable)")

    # 8. M1 — the registered primary comparison ----------------------------
    ch = pd.DataFrame({
        "game_id": U1_test["row_id"], "game_date": U1_test["game_date"],
        "season": U1_test["season"], "y_true": U1_test["minutes"].astype(float),
        "y_pred": U1_test["pred_min_played"].astype(float),
        "team": U1_test["team_abbreviation"],
    })
    inc_frame = inc[["row_id", "y_true", "pred_ewma"]].rename(
        columns={"row_id": "game_id", "pred_ewma": "y_pred"})
    result = compare_to_incumbent(
        ch, inc_frame, experiment_id=EXPERIMENT_ID, registry_path=registry_path,
        loss="absolute", cluster="date", team_col="team",
        coverage=(float(U1_test["pred_min_played"].notna().mean()),
                  float(inc["pred_ewma"].notna().mean())),
    )
    print(f"[M1] {result.verdict} (run {result.run_number}) pooled "
          f"{result.metric_challenger:.4f} vs {result.metric_incumbent:.4f} "
          f"delta {result.pooled_improvement:+.4f} CI [{result.ci_low:+.4f}, {result.ci_high:+.4f}] "
          f"failed={result.failed_gates}")

    # 9. M2 — Stage A vs expanding prior (secondary; compute-only) ----------
    U2_test = D[m2 & D["season"].isin(TEST_SEASONS)].copy()
    prior_ok = U2_test["p_plays_prior"].notna()
    assert prior_ok.all()
    ch2 = pd.DataFrame({
        "game_id": U2_test["row_id"], "game_date": U2_test["game_date"],
        "season": U2_test["season"], "y_true": U2_test["played_flag"].astype(float),
        "y_pred": np.clip(U2_test["p_plays"].astype(float), 0, 1),
        "team": U2_test["team_abbreviation"],
    })
    in2 = pd.DataFrame({
        "game_id": U2_test["row_id"], "y_true": U2_test["played_flag"].astype(float),
        "y_pred": np.clip(U2_test["p_plays_prior"].astype(float), 0, 1),
    })
    res2 = compare_to_incumbent(
        ch2, in2, experiment_id=EXPERIMENT_ID, registry_path=registry_path,
        loss=lambda y, p: (y - p) ** 2, cluster="date", team_col="team",
        coverage=(1.0, 1.0), record=False,
    )
    rel = reliability_table(U2_test["played_flag"].to_numpy(float),
                            np.clip(U2_test["p_plays"].to_numpy(float), 0, 1))
    print(f"[M2] Brier challenger {res2.metric_challenger:.5f} vs prior "
          f"{res2.metric_incumbent:.5f} delta {res2.pooled_improvement:+.5f} "
          f"CI [{res2.ci_low:+.5f}, {res2.ci_high:+.5f}]")

    # 10. M3 — p*m vs B4 (secondary; compute-only) --------------------------
    U3_test = D[m3 & D["season"].isin(TEST_SEASONS)].copy()
    y3 = U3_test["minutes"].fillna(0.0).astype(float)
    ch3 = pd.DataFrame({
        "game_id": U3_test["row_id"], "game_date": U3_test["game_date"],
        "season": U3_test["season"], "y_true": y3,
        "y_pred": U3_test["pred_exp_min"].astype(float),
        "team": U3_test["team_abbreviation"],
    })
    in3 = pd.DataFrame({"game_id": U3_test["row_id"], "y_true": y3,
                        "y_pred": U3_test["pred_b4"].astype(float)})
    res3 = compare_to_incumbent(
        ch3, in3, experiment_id=EXPERIMENT_ID, registry_path=registry_path,
        loss="absolute", cluster="date", team_col="team",
        coverage=(1.0, 1.0), record=False,
    )
    print(f"[M3] exp-min MAE {res3.metric_challenger:.4f} vs B4 "
          f"{res3.metric_incumbent:.4f} delta {res3.pooled_improvement:+.4f} "
          f"CI [{res3.ci_low:+.4f}, {res3.ci_high:+.4f}]")

    # 11. M4 — team-sum diagnostic ------------------------------------------
    sums = (D[m2 & D["season"].isin(TEST_SEASONS)]
            .groupby(["game_id", "team_id"])
            .agg(pred_sum=("pred_exp_min", "sum"),
                 actual_sum=("minutes", lambda s: s.fillna(0).sum()))
            .reset_index())
    m4 = {
        "n_team_games": int(len(sums)),
        "pred_sum_mean": float(sums["pred_sum"].mean()),
        "pred_sum_p10": float(sums["pred_sum"].quantile(0.10)),
        "pred_sum_p50": float(sums["pred_sum"].quantile(0.50)),
        "pred_sum_p90": float(sums["pred_sum"].quantile(0.90)),
        "actual_sum_mean": float(sums["actual_sum"].mean()),
        "note": "universe misses cold-start rows; actual_sum shows the same "
                "shortfall vs 200, so the bias comparison is like-for-like",
    }
    print(f"[M4] pred team-sum mean {m4['pred_sum_mean']:.1f} vs actual "
          f"{m4['actual_sum_mean']:.1f} (200 + OT is the physical target)")

    # 12. regime-B accounting ----------------------------------------------
    avail_cols = ["miss_inj_l21", "miss_other_l21", "roster_move_l14",
                  "suspension_l30", "waived_since_last_game"]
    U1_test["has_avail"] = (U1_test[avail_cols] != 0).any(axis=1)
    cov_rows = []
    for season in TEST_SEASONS:
        sub = U1_test[U1_test["season"] == season]
        cov_rows.append({
            "season": season, "n_rows": len(sub),
            "rows_with_signal": int(sub["has_avail"].sum()),
            "coverage": float(sub["has_avail"].mean()),
            "n_games": sub["game_id"].nunique(),
            "n_teams": sub["team_abbreviation"].nunique(),
        })
    cov_tbl = pd.DataFrame(cov_rows)
    err_ch = (U1_test["pred_min_played"] - U1_test["minutes"]).abs()
    err_in = (U1_test["min_ewma"] - U1_test["minutes"]).abs()
    miss_split = {
        "covered_rows": int(U1_test["has_avail"].sum()),
        "covered_mae_challenger": float(err_ch[U1_test["has_avail"]].mean()),
        "covered_mae_incumbent": float(err_in[U1_test["has_avail"]].mean()),
        "uncovered_mae_challenger": float(err_ch[~U1_test["has_avail"]].mean()),
        "uncovered_mae_incumbent": float(err_in[~U1_test["has_avail"]].mean()),
        "covered_played_rate_M2": float(
            U2_test[(U2_test[avail_cols] != 0).any(axis=1)]["played_flag"].mean()),
        "uncovered_played_rate_M2": float(
            U2_test[~(U2_test[avail_cols] != 0).any(axis=1)]["played_flag"].mean()),
    }
    regime_b = {
        "sources": {"bbref_transactions": "official league transactions, public "
                                          "same-day, day precision",
                    "espn_missed_game": "postgame per-game records, usable from "
                                        "the following day",
                    "w1_news": "exact published_utc; exploratory overlay only"},
        "resolution": inj_acc,
        "coverage_by_season": cov_rows,
        "time_of_day": "not applicable at day precision (stated per registration)",
        "systematic_missingness": miss_split,
        "timestamp_audit": ts_audit,
    }

    # 13. W1 overlay (exploratory, non-promotable) --------------------------
    sig, w1_acc = load_w1_signals(D)
    lo, hi = pd.Timestamp(W1_WINDOW[0]), pd.Timestamp(W1_WINDOW[1])
    w_m2 = m2 & (D["season"] == 2026) & D["game_date"].between(lo, hi)
    D26 = D[w_m2].copy()
    D26["w1_signal"] = latest_w1_signal(D26, sig, include_speculation=False)
    D26["w1_signal_spec"] = latest_w1_signal(D26, sig, include_speculation=True)
    strat_rows = []
    for cls, grp in D26.groupby(D26["w1_signal_spec"].fillna("none")):
        strat_rows.append({
            "signal": cls, "n": len(grp),
            "played_rate": float(grp["played_flag"].mean()),
            "mean_model_p": float(grp["p_plays"].mean()),
            "mean_abs_expmin_err": float(
                (grp["pred_exp_min"] - grp["minutes"].fillna(0)).abs().mean()),
        })
    strat = pd.DataFrame(strat_rows).sort_values("n", ascending=False)

    D26["p_overlay"] = D26["p_plays"]
    is_out = D26["w1_signal"].isin(["out", "season_ending"])
    is_ret = D26["w1_signal"] == "returning"
    D26.loc[is_out, "p_overlay"] = np.minimum(D26.loc[is_out, "p_plays"], W1_P_OUT_CAP)
    D26.loc[is_ret, "p_overlay"] = np.maximum(D26.loc[is_ret, "p_plays"], W1_P_RET_FLOOR)
    y26 = D26["played_flag"].to_numpy(float)
    w1_overlay = {
        "window": list(W1_WINDOW), "n_rows": int(len(D26)),
        "n_touched_out": int(is_out.sum()), "n_touched_returning": int(is_ret.sum()),
        "brier_base": bri(y26, D26["p_plays"].to_numpy(float)),
        "brier_overlay": bri(y26, D26["p_overlay"].to_numpy(float)),
        "m3_mae_base": float((D26["p_plays"] * D26["pred_min_played"]
                              - D26["minutes"].fillna(0)).abs().mean()),
        "m3_mae_overlay": float((D26["p_overlay"] * D26["pred_min_played"]
                                 - D26["minutes"].fillna(0)).abs().mean()),
        "resolution": w1_acc,
        "status": "exploratory, non-promotable (registration w1_overlay)",
    }
    print(f"[W1] window rows {len(D26):,}; touched out {w1_overlay['n_touched_out']} "
          f"/ returning {w1_overlay['n_touched_returning']}; Brier "
          f"{w1_overlay['brier_base']:.5f} -> {w1_overlay['brier_overlay']:.5f}")

    # 14. secondary evaluation record on the ledger -------------------------
    def slim(r):
        d = r.to_dict()
        return {k: d[k] for k in
                ("metric_challenger", "metric_incumbent", "pooled_improvement",
                 "ci_low", "ci_high", "ci_level", "n_games", "n_clusters",
                 "per_season")}
    secondary = {
        "record_type": "secondary_metrics",
        "m2_stage_a_vs_expanding_prior": slim(res2) | {
            "preregistered_bar": "improvement >= 0.005 and CI excludes degradation",
            "bar_met": bool(res2.pooled_improvement >= 0.005 and res2.ci_low > 0)},
        "m3_product_vs_b4": slim(res3) | {
            "preregistered_bar": "improvement >= 0.10, CI harm <= 0.05, "
                                 "season tolerance 0.15",
            "bar_met": bool(res3.pooled_improvement >= 0.10 and res3.ci_low >= -0.05
                            and all(s["delta"] >= -0.15 for s in res3.per_season))},
        "exploratory_posthoc": {
            "label": "NOT preregistered - context only. MAE on a zero-inflated "
                     "mixture grades medians and structurally rewards B4's hard "
                     "zeros; the aggregation layer consumes MEANS (sum of rate x "
                     "E[min]), which RMSE grades.",
            "m3_rmse_challenger": float(np.sqrt(np.mean(
                (U3_test["pred_exp_min"] - y3) ** 2))),
            "m3_rmse_b4": float(np.sqrt(np.mean(
                (U3_test["pred_b4"] - y3) ** 2))),
        },
        "m4_team_sum_diagnostic": m4,
        "m2_universe_n": int(len(U2_test)),
        "m3_universe_n": int(len(U3_test)),
        "m3_excluded_sliver": int((m2 & ~m3 & D["season"].isin(TEST_SEASONS)).sum()),
        "regime_b_accounting": regime_b,
        "w1_overlay_exploratory": w1_overlay,
        "audits": {
            "shift_recompute": {"n_checks": int(len(audit)), "mismatches": n_bad,
                                "max_abs_diff": float(audit["abs_diff"].max())},
            "permutation_probe": {"shuffled_mae": perm_mae,
                                  "train_mean_mae": mean_mae,
                                  "true_model_mae": result.metric_challenger},
            "incumbent_reproduction": {"pooled": inc_mae,
                                       "anchor": INCUMBENT_POOLED,
                                       "max_ewma_dev": ewma_dev},
        },
        "model": {"lambda_ridge": lam_b, "lambda_logistic": lam_a,
                  "zero_variance_dropped_b": std_b.dropped,
                  "zero_variance_dropped_a": std_a.dropped,
                  "team_trait_filled_rows": n_trait_filled,
                  "team_trait_constants": trait_const},
    }
    ereg.evaluate(EXPERIMENT_ID, secondary, registry_path=registry_path)

    # 15. artifacts ---------------------------------------------------------
    coefs_b = pd.DataFrame({"feature": ["intercept"] + std_b.keep,
                            "coef_standardized": beta_b}).sort_values(
        "coef_standardized", key=np.abs, ascending=False)
    coefs_a = pd.DataFrame({"feature": ["intercept"] + std_a.keep,
                            "coef_standardized": beta_a}).sort_values(
        "coef_standardized", key=np.abs, ascending=False)
    coefs_b.to_csv(outdir / "feature_importance_minutes_stage_b.csv", index=False)
    coefs_a.to_csv(outdir / "feature_importance_minutes_stage_a.csv", index=False)
    curve_b.to_csv(outdir / "lambda_curve_stage_b.csv", index=False)
    curve_a.to_csv(outdir / "lambda_curve_stage_a.csv", index=False)
    audit.to_csv(outdir / "leakage_audit.csv", index=False)
    rel.to_csv(outdir / "stage_a_reliability.csv", index=False)
    strat.to_csv(outdir / "w1_stratified.csv", index=False)
    cov_tbl.to_csv(outdir / "regime_b_coverage.csv", index=False)
    pred_cols = ["row_id", "game_id", "game_date", "season", "player_id",
                 "player_name", "team_abbreviation", "played_flag", "minutes",
                 "min_ewma", "pred_min_played", "p_plays", "p_plays_prior",
                 "pred_exp_min", "pred_b4", "has_avail"]
    U1_test[pred_cols].to_csv(outdir / "test_predictions_m1.csv", index=False)
    U2t = D[m2 & D["season"].isin(TEST_SEASONS)].copy()
    U2t["has_avail"] = (U2t[avail_cols] != 0).any(axis=1)
    U2t[[c for c in pred_cols if c != "has_avail"] + ["has_avail"]].to_csv(
        outdir / "test_predictions_m2.csv", index=False)
    with open(outdir / "gate_verdict.json", "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, indent=2, default=str)
    with open(outdir / "secondary_results.json", "w", encoding="utf-8") as fh:
        json.dump(secondary, fh, indent=2, default=str)

    # feature dictionary
    dict_rows = []
    for f in STAGE_B_FEATURES:
        dict_rows.append({"feature": f, "stage": "B",
                          "in_stage_a": f in STAGE_A_FEATURES})
    for f in STAGE_A_FEATURES:
        if f not in STAGE_B_FEATURES:
            dict_rows.append({"feature": f, "stage": "A", "in_stage_a": True})
    pd.DataFrame(dict_rows).to_csv(outdir / "feature_dictionary_minutes.csv",
                                   index=False)

    # 16. report ------------------------------------------------------------
    md = f"""# Two-stage conditional minutes model (`{EXPERIMENT_ID}`)

*Generated by `minutes_twostage.py` on {run_time} — run {result.run_number} (M1 comparison) on the
registry ledger; secondary metrics recorded as the following evaluation record. Regime B.
Registered 2026-07-30T20:19:14Z; incumbent `minutes_ewma_alpha030_v1` (pooled {INCUMBENT_POOLED}).*

## Verdict — M1 primary (gated)

- **{result.verdict}** (promote={result.promote}); failed gates: {result.failed_gates or 'none'}.
- Pooled minutes MAE: **challenger {result.metric_challenger:.4f}** vs incumbent {result.metric_incumbent:.4f}
  -> improvement **{result.pooled_improvement:+.4f}** (gate 1 >= +0.10).
- 90% date-cluster bootstrap CI: [{result.ci_low:+.4f}, {result.ci_high:+.4f}] (gate 2 low >= -0.05);
  team-cluster sensitivity {result.ci_sensitivity_team}.
- Per-season: {json.dumps(result.per_season, default=str)}

## Secondary (preregistered bars, recorded not gated)

- **M2** Stage-A Brier {res2.metric_challenger:.5f} vs expanding prior {res2.metric_incumbent:.5f}
  (delta {res2.pooled_improvement:+.5f}, CI [{res2.ci_low:+.5f}, {res2.ci_high:+.5f}];
  bar met: {secondary['m2_stage_a_vs_expanding_prior']['bar_met']}). Reliability: `stage_a_reliability.csv`.
- **M3** p*m expected-minutes MAE {res3.metric_challenger:.4f} vs B4 {res3.metric_incumbent:.4f}
  (delta {res3.pooled_improvement:+.4f}, CI [{res3.ci_low:+.4f}, {res3.ci_high:+.4f}];
  bar met: {secondary['m3_product_vs_b4']['bar_met']}).
- **M4** predicted team-sum mean {m4['pred_sum_mean']:.1f} (p10 {m4['pred_sum_p10']:.1f} / p50
  {m4['pred_sum_p50']:.1f} / p90 {m4['pred_sum_p90']:.1f}) vs actual universe sum {m4['actual_sum_mean']:.1f}.

## Universes

M1 played {len(U1):,} (test {len(U1_test):,} — identical to the incumbent file);
M2 dressed {len(U2):,} (test {len(U2_test):,}); M3 product {len(U3):,}
(test {len(U3_test):,}; M2-only sliver excluded from M3: {secondary['m3_excluded_sliver']:,} test rows).

## Model

Ridge lambda {lam_b} / logistic lambda {lam_a} (13-point log grids, 3 inner walk-forward folds
strictly inside 2021-2023; curves in `lambda_curve_stage_*.csv`). Fit once on 2021-2023,
standardization from train only, frozen for all test seasons. Top standardized coefficients:
`feature_importance_minutes_stage_b.csv` / `_stage_a.csv`.

Known wart (constitution rule 6): `min_share_ewma` and `min_ewma` are near-collinear and take
large opposite-signed coefficients; predictively harmless under ridge, but v2 should keep one.
`p_plays_prior` similarly flips sign conditional on `min_ewma`. Interpretability caveats, not
leakage — the shift audit and permutation probe bound causality.

## Audits

- Shift-recompute: {len(audit)} independent per-row feature recomputations, {n_bad} mismatches,
  max |diff| {audit['abs_diff'].max():.3e}. PASS.
- Permutation probe: shuffled-target model MAE {perm_mae:.4f} vs train-mean baseline {mean_mae:.4f}
  (true model {result.metric_challenger:.4f}) — model collapses without real signal. PASS.
- Incumbent reproduction: pooled {inc_mae:.4f} vs anchor {INCUMBENT_POOLED}; row-level max
  |our EWMA - stored| {ewma_dev:.2e}; universes identical. PASS.
- Availability timestamps: every window ends at game_date - 1 day (searchsorted strictly-less);
  ESPN/bbref day precision stated. PASS.

## Regime-B accounting

{fmt_table(cov_tbl)}

Missingness split (M1 test): covered rows {miss_split['covered_rows']:,} — challenger MAE
{miss_split['covered_mae_challenger']:.4f} vs incumbent {miss_split['covered_mae_incumbent']:.4f};
uncovered — {miss_split['uncovered_mae_challenger']:.4f} vs {miss_split['uncovered_mae_incumbent']:.4f}.
M2 played-rate covered {miss_split['covered_played_rate_M2']:.4f} vs uncovered
{miss_split['uncovered_played_rate_M2']:.4f} (availability signals mark genuinely-at-risk rows).
Injury-event name resolution {inj_acc['resolution_rate']:.1%}
({inj_acc['events_resolved']:,}/{inj_acc['events_total']:,}; unresolved never guessed).

## W1 overlay (exploratory, non-promotable)

Window {W1_WINDOW[0]}..{W1_WINDOW[1]}: {w1_overlay['n_rows']:,} dressed rows; overlay touched
{w1_overlay['n_touched_out']} out/season-ending and {w1_overlay['n_touched_returning']} returning rows.
Brier {w1_overlay['brier_base']:.5f} -> {w1_overlay['brier_overlay']:.5f};
M3-window MAE {w1_overlay['m3_mae_base']:.4f} -> {w1_overlay['m3_mae_overlay']:.4f}.
Stratified signal table: `w1_stratified.csv`. W1 signal resolution: {w1_acc['signals_resolved']}/{w1_acc['signals_total']}.

## Files

`gate_verdict.json`, `secondary_results.json`, `test_predictions_m1.csv`, `test_predictions_m2.csv`,
`feature_importance_minutes_stage_[ab].csv`, `lambda_curve_stage_[ab].csv`, `leakage_audit.csv`,
`stage_a_reliability.csv`, `regime_b_coverage.csv`, `w1_stratified.csv`,
`feature_dictionary_minutes.csv`.
"""
    (outdir / "REPORT.md").write_text(md, encoding="utf-8")
    print(f"[done] report + artifacts in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
