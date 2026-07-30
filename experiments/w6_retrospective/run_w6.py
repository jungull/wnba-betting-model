"""W6 "playing-through-it" retrospective study — preregistered as
``w6_microsignal_retrospective_v1`` (QUARANTINED, regime B, primary metric
``absence_auc``; thresholds min_improvement 0.02 / harm_ci_bound 0.01 /
per_season_tolerance 0.05; incumbent ``rest_schedule_minutes_baseline``).

Retrospective correlation study ONLY (ROADMAP W6: "a retrospective
correlation is a leaderboard footnote, not a feature"). Result posts win or
lose; a null result is the cheap kill this quarantine slot exists to buy.

Design (walk-forward safe; every rolling quantity is shifted — the signal at
game t uses games strictly before t; features reset per season):

  Unit / target: for each player-game actually PLAYED (master_player row with
  non-null minutes), label 1 if the player has a ``missed_game_injury``
  ground-truth record (data/injury_history/injury_history.csv, ESPN game-day
  DNP reasons, keyword-classified) within her TEAM's next 3 games of the same
  season, else 0. Rows whose ground truth is structurally missing are
  excluded and counted:
    * fewer than 3 remaining team games in-season (season-boundary truncation
      — applied to positives and negatives alike so the base rate is not
      biased by asymmetric censoring),
    * a window game where the player neither played nor has any ESPN
      missed_game_* row: roster departure (waiver/trade/suspension — she
      cannot generate the ground-truth event) or an ESPN coverage gap
      (master shows a DNP but ESPN carries no row). A row with an observed
      positive in the window is kept regardless (the positive record itself
      is the observation; label-0 requires a FULLY observed window).
    * fewer than 5 prior played games in the season (constitution: >= 5
      prior same-season games for any prediction row; short window needs 5).

  Challenger (micro-signal anomaly score, v1 — no fitting beyond z-scoring
  on train years 2021-2023): four deltas, each = short-window (last 5 played
  games before t) minus season baseline (expanding over all played games
  before t):
      d_ft    FT% (made/att aggregate; needs >=5 window FTA & >=10 baseline)
      d_stint mean stint length (data/derived/stints.parquet; per-game mean)
      d_rim   rim-attempt share (Restricted Area / total FGA, shotcharts;
              needs >=10 window & >=20 baseline attempts)
      d_min   minutes
  Each delta is z-scored with train-year (2021-2023) means/stds; a missing
  component contributes 0 (neutral) and availability is reported.
      microsignal_score = -(z_ft + z_stint + z_rim + z_min)
  (declines in FT%, stint length, rim share, minutes all push the score UP).

  Incumbent (rest/schedule/minutes-trend only, fixed a-priori orientation,
  same z-scoring convention):
      rest_schedule_minutes_baseline = z(games_last7) - z(days_rest) - z(d_min)
  (dense recent schedule, short rest, declining minutes -> higher risk).

  Evaluation: 2024 / 2025 / 2026 separately + pooled. absence_auc for both
  scores (tie-aware Mann-Whitney). 90% CIs from a seeded game-date-clustered
  percentile bootstrap (numpy, n_boot=2000, seed=20260730 — the harness's
  conventions), recomputing AUC per replicate; the paired delta
  (challenger - incumbent, higher-better) is bootstrapped on the same
  replicates. Team-clustered sensitivity CI for the pooled delta, mirroring
  compare.py. Threshold metrics at the alert threshold giving 1 alert per
  100 player-games on train years (99th percentile of each score on the
  train labeled universe, per score): row-level precision, event-level
  recall, false alerts per 100 player-games, median lead time in days from
  first alert to the absence.

  Ledger: the registered primary metric absence_auc is a set-level rank
  statistic — per-game paired residuals do not exist for it, so
  compare_to_incumbent()'s per-game loss contract cannot host it. The
  harness's documented path for evaluations produced outside compare.py is
  registry.evaluate()/record_evaluation() (registry.py docstring); with
  --record this script appends ONE evaluation record carrying the full gate
  verdict computed against the preregistered thresholds in compare.py's
  orientation (delta = challenger - incumbent AUC, positive = improvement),
  per-season AUCs, all CIs, thresholds, sample accounting and coverage.

Run:   python experiments/w6_retrospective/run_w6.py            (dry run)
       python experiments/w6_retrospective/run_w6.py --record   (ledger row)
Local data only. Outputs: CSVs next to this file + printed summary.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

EXPERIMENT_ID = "w6_microsignal_retrospective_v1"
CHALLENGER_ID = "microsignal_anomaly_v1"
INCUMBENT_ID = "rest_schedule_minutes_baseline"
TRAIN_SEASONS = (2021, 2022, 2023)
TEST_SEASONS = (2024, 2025, 2026)
WINDOW = 5                  # short window: last 5 played games
LABEL_HORIZON = 3           # absence within team's next 3 games
MIN_PRIOR_PLAYED = 5        # constitution: >=5 prior same-season games
FT_MIN_W, FT_MIN_B = 5, 10  # min FTA for the FT% component
RIM_MIN_W, RIM_MIN_B = 10, 20
REST_CAP = 15.0             # days-rest cap (avoid return-from-absence outliers)
ALERTS_PER_100 = 1.0        # threshold: 1 alert per 100 player-games on train
N_BOOT = 2000
SEED = 20260730
CI_LEVEL = 0.90

TEAM_CANON = {"PHX": "PHO", "PDX": "POR"}   # master -> injury-history style


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


# ---------------------------------------------------------------------------
# AUC + clustered bootstrap (numpy, deterministic)
# ---------------------------------------------------------------------------

def _avg_ranks(x: np.ndarray) -> np.ndarray:
    """Tie-aware average ranks (1-based), pure numpy."""
    uniq, inv, counts = np.unique(x, return_inverse=True, return_counts=True)
    csum = np.cumsum(counts)
    start = csum - counts + 1
    return ((start + csum) / 2.0)[inv]


def auc(y: np.ndarray, s: np.ndarray) -> float:
    """Mann-Whitney AUC with tie correction. NaN if one class absent."""
    y = np.asarray(y)
    s = np.asarray(s, dtype=float)
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = _avg_ranks(s)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def date_cluster_bootstrap(
    y: np.ndarray, s_ch: np.ndarray, s_inc: np.ndarray, cluster_ids: np.ndarray,
    *, n_boot: int = N_BOOT, seed: int = SEED, ci_level: float = CI_LEVEL,
) -> dict:
    """Cluster (game-date) percentile bootstrap of AUC_ch, AUC_inc and the
    paired delta, recomputing AUC on every replicate. Deterministic."""
    uniq, inv = np.unique(cluster_ids, return_inverse=True)
    n_cl = len(uniq)
    members = [np.flatnonzero(inv == k) for k in range(n_cl)]
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, n_cl, size=(n_boot, n_cl))
    a_ch = np.full(n_boot, np.nan)
    a_inc = np.full(n_boot, np.nan)
    for b in range(n_boot):
        idx = np.concatenate([members[k] for k in draws[b]])
        yb = y[idx]
        if yb.sum() == 0 or yb.sum() == len(yb):
            continue                              # degenerate replicate
        a_ch[b] = auc(yb, s_ch[idx])
        a_inc[b] = auc(yb, s_inc[idx])
    ok = ~np.isnan(a_ch)
    alpha = (1 - ci_level) / 2.0
    q = [alpha, 1 - alpha]

    def ci(v):
        lo, hi = np.quantile(v[ok], q)
        return float(lo), float(hi)

    d = a_ch - a_inc
    return {
        "n_clusters": int(n_cl),
        "n_boot": int(n_boot),
        "n_degenerate": int((~ok).sum()),
        "seed": int(seed),
        "ci_level": ci_level,
        "auc_ch_ci": ci(a_ch),
        "auc_inc_ci": ci(a_inc),
        "delta_ci": ci(d),
    }


# ---------------------------------------------------------------------------
# data assembly
# ---------------------------------------------------------------------------

def load_master() -> pd.DataFrame:
    mp = pd.read_parquet(REPO / "data/masters/master_player.parquet")
    mp["team_i"] = mp["team_abbreviation"].replace(TEAM_CANON)
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    mp["nname"] = mp["player_name"].map(norm_name)
    mp["played"] = mp["minutes"].notna()
    dup = mp.duplicated(["game_id", "player_id"]).sum()
    if dup:
        raise RuntimeError(f"master_player has {dup} duplicate (game, player) rows")
    return mp


def load_injury(mp: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """ESPN missed_game_* rows resolved to (game_id, team_i, player_id).

    Returns (resolved rows, accounting dict). Name resolution: exact
    normalized full name within (season, team) roster, then a unique
    first+last-token containment fallback (handles 'AD Durr' ->
    'Asia (AD) Durr', 'Cyesha Damian Goree' -> 'Cyesha Goree')."""
    ih = pd.read_csv(REPO / "data/injury_history/injury_history.csv")
    mg = ih[ih["category"].str.startswith("missed_game")].copy()
    mg["nname"] = mg["player_relinquished"].map(norm_name)

    sched = mp[["game_id", "season", "game_date", "team_i"]].drop_duplicates()
    sched["date"] = sched["game_date"].dt.strftime("%Y-%m-%d")
    m = mg.merge(sched, left_on=["team", "date"], right_on=["team_i", "date"],
                 how="left")
    unmatched = m[m["game_id"].isna()]
    cup = unmatched["notes"].str.contains("commissioners-cup-final")
    acc = {
        "espn_missed_game_rows": int(len(mg)),
        "rows_matched_to_master_game": int(m["game_id"].notna().sum()),
        "rows_unmatched_game_cup_final": int(cup.sum()),
        "rows_unmatched_game_other": int((~cup).sum()),
    }
    m = m[m["game_id"].notna()].copy()

    roster = (mp[["season", "team_i", "nname", "player_id"]]
              .drop_duplicates(["season", "team_i", "nname"]))
    m = m.merge(roster, on=["season", "team_i", "nname"], how="left")

    # fallback: unique roster candidate containing both first & last token
    un = m["player_id"].isna()
    acc["names_resolved_exact"] = int((~un).sum())
    acc["names_resolved_fallback"] = 0
    if un.any():
        ros = mp[["season", "team_i", "nname", "player_id"]].drop_duplicates()
        fixed = 0
        for i in m.index[un]:
            raw = str(m.at[i, "player_relinquished"]).split()
            first, last = norm_name(raw[0]), norm_name(raw[-1])
            cand = ros[(ros["season"] == m.at[i, "season"])
                       & (ros["team_i"] == m.at[i, "team_i"])]
            hit = cand[cand["nname"].str.contains(first, regex=False)
                       & cand["nname"].str.contains(last, regex=False)]
            if len(hit) == 1:
                m.at[i, "player_id"] = hit["player_id"].iloc[0]
                fixed += 1
        acc["names_resolved_fallback"] = fixed
    acc["names_unresolved"] = int(m["player_id"].isna().sum())
    m = m[m["player_id"].notna()].copy()
    m["player_id"] = m["player_id"].astype("int64")
    acc["rows_resolved_total"] = int(len(m))
    return m[["game_id", "season", "team_i", "player_id", "category",
              "notes", "date", "game_date"]], acc


def per_game_micro(mp: pd.DataFrame) -> pd.DataFrame:
    """Attach per-played-game stint mean and rim counts to master rows."""
    st = pd.read_parquet(REPO / "data/derived/stints.parquet",
                         columns=["GAME_ID", "PLAYER_ID", "stint_sec"])
    stint = (st.groupby(["GAME_ID", "PLAYER_ID"], as_index=False)["stint_sec"]
             .mean().rename(columns={"GAME_ID": "game_id",
                                     "PLAYER_ID": "player_id",
                                     "stint_sec": "stint_mean"}))
    shots = []
    for f in sorted((REPO / "data/shotcharts").glob("shots_*.parquet")):
        d = pd.read_parquet(f, columns=["GAME_ID", "PLAYER_ID", "SHOT_ZONE_BASIC"])
        shots.append(d)
    sh = pd.concat(shots, ignore_index=True)
    sh["is_ra"] = (sh["SHOT_ZONE_BASIC"] == "Restricted Area").astype(int)
    rim = (sh.groupby(["GAME_ID", "PLAYER_ID"])
           .agg(fga_chart=("is_ra", "size"), ra=("is_ra", "sum"))
           .reset_index()
           .rename(columns={"GAME_ID": "game_id", "PLAYER_ID": "player_id"}))
    rim["game_id"] = rim["game_id"].astype(str)
    stint["player_id"] = stint["player_id"].astype("int64")
    rim["player_id"] = rim["player_id"].astype("int64")
    out = mp.merge(stint, on=["game_id", "player_id"], how="left")
    out = out.merge(rim, on=["game_id", "player_id"], how="left")
    played = out["played"]
    # a played game with no shot rows is a real 0-attempt game, not missing
    out.loc[played & out["fga_chart"].isna(), ["fga_chart", "ra"]] = 0.0
    return out


# ---------------------------------------------------------------------------
# features (walk-forward: shifted rolling / expanding, per player-season)
# ---------------------------------------------------------------------------

def build_features(mp: pd.DataFrame) -> pd.DataFrame:
    """Per played row: shifted short-window vs expanding-baseline deltas +
    incumbent schedule features. Sorted per (player, season) by date."""
    pl = mp[mp["played"]].copy()
    pl = pl.sort_values(["player_id", "season", "game_date", "game_id"])
    g = pl.groupby(["player_id", "season"], sort=False)

    def sh_roll(col, fn="mean", w=WINDOW):
        s = g[col].apply(lambda x: getattr(
            x.shift(1).rolling(w, min_periods=w), fn)())
        return s.reset_index(level=[0, 1], drop=True)

    def sh_exp(col, fn="mean"):
        s = g[col].apply(lambda x: getattr(
            x.shift(1).expanding(min_periods=1), fn)())
        return s.reset_index(level=[0, 1], drop=True)

    pl["n_prior_played"] = g.cumcount()

    pl["min_w"] = sh_roll("minutes")
    pl["min_b"] = sh_exp("minutes")
    pl["d_min"] = pl["min_w"] - pl["min_b"]

    pl["stint_w"] = sh_roll("stint_mean")          # NaN-skipping mean
    pl["stint_b"] = sh_exp("stint_mean")
    pl["d_stint"] = pl["stint_w"] - pl["stint_b"]

    for num, den, pref in (("ftm", "fta", "ft"), ("ra", "fga_chart", "rim")):
        pl[f"{pref}_num_w"] = sh_roll(num, "sum")
        pl[f"{pref}_den_w"] = sh_roll(den, "sum")
        pl[f"{pref}_num_b"] = sh_exp(num, "sum")
        pl[f"{pref}_den_b"] = sh_exp(den, "sum")
    for pref, (mw, mb) in (("ft", (FT_MIN_W, FT_MIN_B)),
                           ("rim", (RIM_MIN_W, RIM_MIN_B))):
        w_ok = pl[f"{pref}_den_w"] >= mw
        b_ok = pl[f"{pref}_den_b"] >= mb
        rate_w = pl[f"{pref}_num_w"] / pl[f"{pref}_den_w"].where(w_ok)
        rate_b = pl[f"{pref}_num_b"] / pl[f"{pref}_den_b"].where(b_ok)
        pl[f"d_{pref}"] = rate_w - rate_b

    # incumbent schedule features (player-level, within season)
    pl["days_rest"] = (g["game_date"].diff().dt.days.astype(float)
                       .clip(upper=REST_CAP))
    dates_i = pl["game_date"].values.astype("datetime64[D]").astype("int64")
    key = pl["player_id"].astype(str) + "|" + pl["season"].astype(str)
    games7 = np.zeros(len(pl))
    start = 0
    for _, idx in pl.groupby(key, sort=False).indices.items():
        di = dates_i[idx]
        for j in range(len(idx)):
            games7[idx[j]] = np.searchsorted(di, di[j]) - np.searchsorted(
                di, di[j] - 7)
    pl["games_last7"] = games7          # played games in (t-7d, t), excl. today
    return pl


def zscore_train(pl: pd.DataFrame, cols: list[str]) -> tuple[pd.DataFrame, dict]:
    """z-params from train-season ELIGIBLE rows; NaN -> 0 after z."""
    train = pl[pl["season"].isin(TRAIN_SEASONS) & pl["eligible"]]
    params = {}
    for c in cols:
        mu = float(train[c].mean())
        sd = float(train[c].std(ddof=0))
        if not np.isfinite(sd) or sd == 0:
            raise RuntimeError(f"degenerate train std for {c}")
        params[c] = {"mean": mu, "std": sd,
                     "train_n_nonnull": int(train[c].notna().sum())}
        pl[f"z_{c}"] = ((pl[c] - mu) / sd).fillna(0.0)
    return pl, params


# ---------------------------------------------------------------------------
# labels
# ---------------------------------------------------------------------------

def build_labels(pl: pd.DataFrame, mp: pd.DataFrame, inj: pd.DataFrame
                 ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Label + exclusion accounting on played rows (see module docstring)."""
    sched = (mp[["season", "team_i", "game_id", "game_date"]]
             .drop_duplicates().sort_values(["season", "team_i", "game_date",
                                             "game_id"]))
    sched["t_idx"] = sched.groupby(["season", "team_i"]).cumcount()
    n_games = sched.groupby(["season", "team_i"])["t_idx"].max().rename("t_max")
    sched = sched.merge(n_games, on=["season", "team_i"])
    idx_of = {(r.season, r.team_i, r.game_id): (r.t_idx, r.t_max)
              for r in sched.itertuples()}
    game_at = {(r.season, r.team_i, r.t_idx): (r.game_id, r.game_date)
               for r in sched.itertuples()}

    # observation lookups
    played_set = set(zip(mp.loc[mp["played"], "game_id"],
                         mp.loc[mp["played"], "player_id"]))
    roster_set = set(zip(mp["game_id"], mp["player_id"]))   # any master row
    inj_rows = inj[inj["category"] == "missed_game_injury"]
    inj_set = set(zip(inj_rows["game_id"], inj_rows["player_id"]))
    espn_any = set(zip(inj["game_id"], inj["player_id"]))   # any missed_game_*
    inj_date = dict(zip(zip(inj_rows["game_id"], inj_rows["player_id"]),
                        inj_rows["game_date"]))

    lab = np.full(len(pl), -1, dtype=int)          # -1 = excluded
    reason = np.array([""] * len(pl), dtype=object)
    abs_game = np.array([None] * len(pl), dtype=object)
    abs_date = np.array([None] * len(pl), dtype=object)

    seasons = pl["season"].to_numpy()
    teams = pl["team_i"].to_numpy()
    gids = pl["game_id"].to_numpy()
    pids = pl["player_id"].to_numpy()
    nprior = pl["n_prior_played"].to_numpy()

    for i in range(len(pl)):
        if nprior[i] < MIN_PRIOR_PLAYED:
            reason[i] = "insufficient_history"
            continue
        t_idx, t_max = idx_of[(seasons[i], teams[i], gids[i])]
        if t_idx + LABEL_HORIZON > t_max:
            reason[i] = "season_end_truncation"
            continue
        pos_hit = None
        unobserved = None
        for k in range(1, LABEL_HORIZON + 1):
            wgid, wdate = game_at[(seasons[i], teams[i], t_idx + k)]
            keyp = (wgid, pids[i])
            if keyp in inj_set:
                pos_hit = (wgid, wdate)
                break
            if keyp in played_set or keyp in espn_any:
                continue                            # observed non-injury
            if unobserved is None:
                unobserved = ("window_roster_departure"
                              if keyp not in roster_set
                              else "window_espn_coverage_gap")
        if pos_hit is not None:
            lab[i] = 1
            abs_game[i], abs_date[i] = pos_hit
        elif unobserved is not None:
            reason[i] = unobserved
        else:
            lab[i] = 0
    pl = pl.copy()
    pl["label"] = lab
    pl["excl_reason"] = reason
    pl["absence_game_id"] = abs_game
    pl["absence_date"] = abs_date
    pl["eligible"] = lab >= 0

    funnel = (pl.groupby(["season"])
              .apply(lambda d: pd.Series({
                  "played_rows": len(d),
                  "eligible_rows": int(d["eligible"].sum()),
                  "positives": int((d["label"] == 1).sum()),
                  "positive_rate": float((d["label"] == 1).sum()
                                         / max(d["eligible"].sum(), 1)),
                  "excl_insufficient_history":
                      int((d["excl_reason"] == "insufficient_history").sum()),
                  "excl_season_end_truncation":
                      int((d["excl_reason"] == "season_end_truncation").sum()),
                  "excl_window_roster_departure":
                      int((d["excl_reason"] == "window_roster_departure").sum()),
                  "excl_window_espn_coverage_gap":
                      int((d["excl_reason"] == "window_espn_coverage_gap").sum()),
              }), include_groups=False)
              .reset_index())
    return pl, funnel


# ---------------------------------------------------------------------------
# threshold metrics
# ---------------------------------------------------------------------------

def threshold_metrics(ev: pd.DataFrame, score_col: str, thr: float) -> dict:
    """Row-level precision / false alerts per 100; event-level recall +
    median lead time (days, first alerting game -> absence date)."""
    alerts = ev[score_col] >= thr
    n = len(ev)
    tp_rows = int((alerts & (ev["label"] == 1)).sum())
    fp_rows = int((alerts & (ev["label"] == 0)).sum())
    events = ev[ev["label"] == 1].copy()
    ev_groups = events.groupby(["player_id", "absence_game_id"])
    n_events = ev_groups.ngroups
    detected, leads = 0, []
    for (_, _), d in ev_groups:
        hit = d[d[score_col] >= thr]
        if len(hit):
            detected += 1
            first_alert = hit["game_date"].min()
            a_date = pd.to_datetime(d["absence_date"].iloc[0])
            leads.append(float((a_date - first_alert).days))
    return {
        "n_rows": int(n),
        "n_alerts": int(alerts.sum()),
        "alerts_per_100": float(100.0 * alerts.sum() / n) if n else np.nan,
        "false_alerts_per_100": float(100.0 * fp_rows / n) if n else np.nan,
        "precision_rows": float(tp_rows / alerts.sum()) if alerts.sum() else np.nan,
        "n_events": int(n_events),
        "events_detected": int(detected),
        "recall_events": float(detected / n_events) if n_events else np.nan,
        "median_lead_days": float(np.median(leads)) if leads else np.nan,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(record: bool) -> None:
    print("== W6 retrospective:", EXPERIMENT_ID, "| record =", record)
    mp = load_master()
    inj, inj_acc = load_injury(mp)
    mp = per_game_micro(mp)
    pl = build_features(mp)
    pl, funnel = build_labels(pl, mp, inj)

    delta_cols = ["d_ft", "d_stint", "d_rim", "d_min"]
    pl, zparams = zscore_train(pl, delta_cols + ["days_rest", "games_last7"])
    pl["score_micro"] = -(pl["z_d_ft"] + pl["z_d_stint"]
                          + pl["z_d_rim"] + pl["z_d_min"])
    pl["score_incumbent"] = (pl["z_games_last7"] - pl["z_days_rest"]
                             - pl["z_d_min"])

    ev_all = pl[pl["eligible"]].copy()
    train = ev_all[ev_all["season"].isin(TRAIN_SEASONS)]
    thr_micro = float(np.quantile(train["score_micro"],
                                  1 - ALERTS_PER_100 / 100.0))
    thr_inc = float(np.quantile(train["score_incumbent"],
                                1 - ALERTS_PER_100 / 100.0))
    print(f"train rows {len(train)}, thresholds: micro {thr_micro:.4f} "
          f"incumbent {thr_inc:.4f}")

    # component availability (before neutral fill), eligible rows
    avail = (ev_all.groupby("season")[delta_cols]
             .apply(lambda d: d.notna().mean()).round(4).reset_index())

    # ---- AUC + bootstrap per season and pooled over test seasons ----------
    auc_rows, thr_rows = [], []
    per_season_delta = {}
    for scope in list(TEST_SEASONS) + ["pooled_test", "train_2021_2023"]:
        if scope == "pooled_test":
            d = ev_all[ev_all["season"].isin(TEST_SEASONS)]
        elif scope == "train_2021_2023":
            d = train
        else:
            d = ev_all[ev_all["season"] == scope]
        y = d["label"].to_numpy()
        sc, si = d["score_micro"].to_numpy(), d["score_incumbent"].to_numpy()
        dates = d["game_date"].dt.normalize().to_numpy()
        a_ch, a_inc = auc(y, sc), auc(y, si)
        bs = date_cluster_bootstrap(y, sc, si, dates)
        auc_rows.append({
            "scope": scope, "n_rows": len(d), "n_pos": int(y.sum()),
            "n_dates": bs["n_clusters"],
            "auc_microsignal": a_ch,
            "auc_micro_ci_low": bs["auc_ch_ci"][0],
            "auc_micro_ci_high": bs["auc_ch_ci"][1],
            "auc_incumbent": a_inc,
            "auc_inc_ci_low": bs["auc_inc_ci"][0],
            "auc_inc_ci_high": bs["auc_inc_ci"][1],
            "delta_auc": a_ch - a_inc,
            "delta_ci_low": bs["delta_ci"][0],
            "delta_ci_high": bs["delta_ci"][1],
            "n_boot": bs["n_boot"], "n_degenerate_reps": bs["n_degenerate"],
            "seed": bs["seed"],
        })
        if scope in TEST_SEASONS:
            per_season_delta[scope] = a_ch - a_inc
        for name, col, thr in (("microsignal", "score_micro", thr_micro),
                               ("incumbent", "score_incumbent", thr_inc)):
            tm = threshold_metrics(d, col, thr)
            thr_rows.append({"scope": scope, "score": name,
                             "threshold": thr, **tm})

    auc_df = pd.DataFrame(auc_rows)
    thr_df = pd.DataFrame(thr_rows)
    pooled = auc_df[auc_df["scope"] == "pooled_test"].iloc[0]

    # team-clustered sensitivity CI on the pooled delta (compare.py mirror)
    dte = ev_all[ev_all["season"].isin(TEST_SEASONS)]
    bs_team = date_cluster_bootstrap(
        dte["label"].to_numpy(), dte["score_micro"].to_numpy(),
        dte["score_incumbent"].to_numpy(), dte["team_i"].to_numpy())

    # ---- gates against the preregistered thresholds ------------------------
    from evalharness.registry import get_registration
    reg = get_registration(EXPERIMENT_ID)
    th = reg["thresholds"]
    pooled_delta = float(pooled["delta_auc"])
    gates = {
        "gate1_pooled_improvement": bool(pooled_delta >= th["min_improvement"]),
        "gate2_ci_excludes_harm": bool(pooled["delta_ci_low"]
                                       >= -th["harm_ci_bound"]),
        "gate3_per_season_non_inferiority": bool(
            min(per_season_delta.values()) >= -th["per_season_tolerance"]),
        "gate4_joint_forecast": None,       # no game forecast produced here
        "gate5_coverage": True,             # identical row set for both scores
    }
    failed = [g for g, ok in gates.items() if ok is False]
    verdict = "PASS" if not failed else "FAIL"
    worst_season = min(per_season_delta, key=per_season_delta.get)

    # ---- event addressability (regime-B systematic missingness) ------------
    sched = (mp[["season", "team_i", "game_id", "game_date"]]
             .drop_duplicates().sort_values(["season", "team_i", "game_date",
                                             "game_id"]))
    sched["t_idx"] = sched.groupby(["season", "team_i"]).cumcount()
    gid2idx = dict(zip(zip(sched["season"], sched["team_i"], sched["game_id"]),
                       sched["t_idx"]))
    idx2gid = dict(zip(zip(sched["season"], sched["team_i"], sched["t_idx"]),
                       sched["game_id"]))
    anyset = set(zip(inj["game_id"], inj["player_id"]))
    injr = inj[inj["category"] == "missed_game_injury"].copy()
    injr["t_idx"] = [gid2idx[(s, t, g)] for s, t, g in
                     zip(injr["season"], injr["team_i"], injr["game_id"])]
    injr["ep_start"] = [
        r.t_idx == 0
        or (idx2gid[(r.season, r.team_i, r.t_idx - 1)], r.player_id) not in anyset
        for r in injr.itertuples()]
    starts = injr[injr["ep_start"]]
    event_keys = set(zip(ev_all.loc[ev_all["label"] == 1, "player_id"],
                         ev_all.loc[ev_all["label"] == 1, "absence_game_id"]))
    addr_mask = [(p, g) in event_keys
                 for p, g in zip(starts["player_id"], starts["game_id"])]
    addr = (starts.groupby("season").size().rename("episode_starts").to_frame()
            .join(starts[addr_mask].groupby("season").size()
                  .rename("addressable_events"))
            .reset_index())
    addr["addressable_share"] = (addr["addressable_events"]
                                 / addr["episode_starts"]).round(3)

    # ---- exploratory footnotes (post-hoc, NOT gate inputs) -----------------
    dte_ = ev_all[ev_all["season"].isin(TEST_SEASONS)].copy()
    dte_["t_idx"] = [gid2idx[(s, t, g)] for s, t, g in
                     zip(dte_["season"], dte_["team_i"], dte_["game_id"])]
    s2d = sched.set_index(["season", "team_i", "t_idx"])["game_date"]
    nxt = [s2d.get((s, t, i + 1), pd.NaT) for s, t, i in
           zip(dte_["season"], dte_["team_i"], dte_["t_idx"])]
    h1 = dte_[(dte_["label"] == 0)
              | (pd.to_datetime(dte_["absence_date"]) == pd.to_datetime(nxt))]
    ft_rows = dte_[dte_["d_ft"].notna()]
    exploratory = {
        "note": "post-hoc diagnostics, clearly exploratory — not gate inputs",
        "horizon1_only": {
            "n": int(len(h1)), "n_pos": int(h1["label"].sum()),
            "auc_microsignal": auc(h1["label"].to_numpy(),
                                   h1["score_micro"].to_numpy()),
            "auc_incumbent": auc(h1["label"].to_numpy(),
                                 h1["score_incumbent"].to_numpy())},
        "ft_component_only": {
            "auc_all_rows_neutral_filled": auc(dte_["label"].to_numpy(),
                                               -dte_["z_d_ft"].to_numpy()),
            "auc_rows_with_ft_available": auc(ft_rows["label"].to_numpy(),
                                              -ft_rows["z_d_ft"].to_numpy()),
            "n_rows_with_ft": int(len(ft_rows)),
            "n_pos_with_ft": int(ft_rows["label"].sum())},
        "per_component_auc_test_pooled_component_available_rows_only": {
            f"-{c}": auc(dte_.loc[dte_[c].notna(), "label"].to_numpy(),
                         -dte_.loc[dte_[c].notna(), c].to_numpy())
            for c in ["d_ft", "d_stint", "d_rim", "d_min"]},
    }

    # ---- regime-B coverage tables ------------------------------------------
    inj_g = inj[inj["category"] == "missed_game_injury"]
    cov_team = (inj_g.groupby(["season", "team_i"]).size()
                .rename("missed_game_injury_rows").reset_index())
    # per-season source coverage: master games with >=1 ESPN missed_game row
    games_master = mp[["season", "game_id"]].drop_duplicates()
    games_espn = inj[["season", "game_id"]].drop_duplicates()
    cov_src = (games_master.groupby("season").size().rename("master_games")
               .to_frame()
               .join(games_espn.groupby("season").size()
                     .rename("games_with_espn_dnp_rows"))
               .reset_index())
    # cross-check: master boxscore DNPs with injury-ish reason vs ESPN injury rows
    inj_pat = re.compile(r"injur|ill|health|protocol|concuss", re.I)
    mdnp = mp[mp["dnp_reason"].notna()].copy()
    mdnp["injury_ish"] = mdnp["dnp_reason"].str.contains(inj_pat)
    espn_inj_set = set(zip(inj_g["game_id"], inj_g["player_id"]))
    mdnp["in_espn_injury"] = [
        (g, p) in espn_inj_set for g, p in zip(mdnp["game_id"], mdnp["player_id"])]
    cross = (mdnp[mdnp["injury_ish"]].groupby("season")
             .agg(master_injury_dnps=("game_id", "size"),
                  also_in_espn_ground_truth=("in_espn_injury", "sum"))
             .reset_index())
    cross["espn_capture_rate"] = (cross["also_in_espn_ground_truth"]
                                  / cross["master_injury_dnps"]).round(4)

    # ---- write CSVs --------------------------------------------------------
    auc_df.to_csv(OUT / "auc_results.csv", index=False)
    thr_df.to_csv(OUT / "threshold_metrics.csv", index=False)
    funnel.to_csv(OUT / "label_funnel.csv", index=False)
    avail.to_csv(OUT / "component_availability.csv", index=False)
    cov_team.to_csv(OUT / "coverage_absences_by_season_team.csv", index=False)
    cov_src.to_csv(OUT / "coverage_source_by_season.csv", index=False)
    cross.to_csv(OUT / "coverage_master_dnp_crosscheck.csv", index=False)
    addr.to_csv(OUT / "coverage_event_addressability.csv", index=False)
    slim = ev_all[["game_id", "game_date", "season", "team_i", "player_id",
                   "player_name", "label", "absence_game_id", "absence_date",
                   "d_ft", "d_stint", "d_rim", "d_min", "days_rest",
                   "games_last7", "score_micro", "score_incumbent"]]
    slim.to_csv(OUT / "labeled_universe.csv", index=False)
    with open(OUT / "zscore_params.json", "w", encoding="utf-8") as fh:
        json.dump({"train_seasons": TRAIN_SEASONS, "params": zparams,
                   "thr_micro": thr_micro, "thr_incumbent": thr_inc}, fh,
                  indent=2)

    print("\n== AUC ==\n", auc_df.round(4).to_string(index=False))
    print("\n== thresholds ==\n", thr_df.round(4).to_string(index=False))
    print("\n== funnel ==\n", funnel.to_string(index=False))
    print("\n== gates ==", gates, "verdict:", verdict)
    print("team-clustered sensitivity delta CI:", bs_team["delta_ci"],
          "n_teams:", bs_team["n_clusters"])
    print("injury-row accounting:", inj_acc)

    # ---- ledger ------------------------------------------------------------
    results = {
        "method": (
            "absence_auc is a set-level rank statistic; per-game paired "
            "residuals do not exist for it, so compare_to_incumbent()'s "
            "per-game loss contract cannot host the primary metric. Recorded "
            "via registry.evaluate() — the harness's documented path for "
            "evaluations produced outside compare.py (registry.py "
            "docstring). Gates computed here against the preregistered "
            "thresholds in compare.py's orientation: delta = "
            "challenger_auc - incumbent_auc (higher-better, positive = "
            "improvement); CIs from a seeded game-date-clustered percentile "
            "bootstrap recomputing AUC per replicate (n_boot=2000, "
            "seed=20260730, level 0.90), matching compare.py's primary "
            "clustering; team-clustered sensitivity CI alongside."),
        "study_kind": "retrospective_correlation_only",
        "challenger_id": CHALLENGER_ID,
        "incumbent_id": INCUMBENT_ID,
        "regime_note": (
            "Regime B: ground truth = ESPN game-day-final DNP reasons "
            "(keyword-classified). No pregame Q/D/P designations, no "
            "played-hurt labels, no intraday timestamps (post-game "
            "artifacts: time-of-day coverage is nil by construction). "
            "Season-long absences (suspension/overseas/pregnancy) are "
            "structurally invisible; COACH'S DECISION/REST can mask "
            "injuries. Results apply to the covered subset only."),
        "n_rows_pooled_test": int(pooled["n_rows"]),
        "n_pos_pooled_test": int(pooled["n_pos"]),
        "pooled_auc_challenger": float(pooled["auc_microsignal"]),
        "pooled_auc_incumbent": float(pooled["auc_incumbent"]),
        "pooled_improvement": pooled_delta,
        "ci_level": CI_LEVEL,
        "ci_low": float(pooled["delta_ci_low"]),
        "ci_high": float(pooled["delta_ci_high"]),
        "ci_method": "cluster",
        "cluster": "date",
        "n_boot": N_BOOT,
        "seed": SEED,
        "ci_sensitivity_team": [bs_team["delta_ci"][0], bs_team["delta_ci"][1],
                                bs_team["n_clusters"]],
        "per_season": [
            {"season": str(s),
             "n": int(auc_df.loc[auc_df["scope"] == s, "n_rows"].iloc[0]),
             "n_pos": int(auc_df.loc[auc_df["scope"] == s, "n_pos"].iloc[0]),
             "delta": float(per_season_delta[s]),
             "metric_challenger": float(
                 auc_df.loc[auc_df["scope"] == s, "auc_microsignal"].iloc[0]),
             "metric_incumbent": float(
                 auc_df.loc[auc_df["scope"] == s, "auc_incumbent"].iloc[0]),
             "delta_ci90": [
                 float(auc_df.loc[auc_df["scope"] == s, "delta_ci_low"].iloc[0]),
                 float(auc_df.loc[auc_df["scope"] == s, "delta_ci_high"].iloc[0])],
             } for s in TEST_SEASONS],
        "thresholds": th,
        "gates": gates,
        "gate_details": {
            "gate1": {"pooled_improvement": pooled_delta,
                      "min_improvement": th["min_improvement"]},
            "gate2": {"ci_low": float(pooled["delta_ci_low"]),
                      "harm_ci_bound": th["harm_ci_bound"]},
            "gate3": {"worst_season": str(worst_season),
                      "worst_delta": float(per_season_delta[worst_season]),
                      "per_season_tolerance": th["per_season_tolerance"]},
            "gate4": {"status": "not_provided",
                      "note": "no game forecast produced by this study"},
            "gate5": {"coverage_challenger": 1.0, "coverage_incumbent": 1.0,
                      "note": "identical eligible row set for both scores; "
                              "missing micro components neutral-filled and "
                              "reported in component_availability.csv"},
        },
        "alert_threshold_rule": "1 alert per 100 player-games on train "
                                "2021-2023 (99th pct per score)",
        "threshold_metrics_pooled_test": {
            r["score"]: {k: (None if pd.isna(v) else v)
                         for k, v in r.items() if k not in ("scope", "score")}
            for _, r in thr_df[thr_df["scope"] == "pooled_test"].iterrows()},
        "promote": False,       # quarantined retrospective study, never a feature
        "verdict": verdict,
        "failed_gates": failed,
        "interpretation": (
            "NULL RESULT in substance despite the incumbent-relative gates "
            "passing mechanically. The challenger's own absence_auc is "
            f"statistically indistinguishable from chance (pooled "
            f"{float(pooled['auc_microsignal']):.4f}, 90% CI "
            f"[{float(pooled['auc_micro_ci_low']):.4f}, "
            f"{float(pooled['auc_micro_ci_high']):.4f}] — includes 0.5); the "
            f"positive delta (+{pooled_delta:.4f}) exists only because the "
            "incumbent rest/schedule/minutes-trend baseline scores BELOW "
            f"chance ({float(pooled['auc_incumbent']):.4f}) at its "
            "preregistered fixed orientation. The registered hypothesis's "
            "'better than chance' clause is REFUTED. At the 1-per-100 alert "
            "threshold the challenger detects 4 of 200 absence events "
            "(2.0% event recall) with 5.2% row precision against a 4.5% "
            "base rate. Promotion was never on the table: quarantined, and "
            "ROADMAP W6 requires prospective performance — there is no "
            "retrospective correlation here to footnote. This kills the W6 "
            "micro-signal v1 cheaply, which is what the quarantine queue "
            "is for."),
        "exclusions_pooled": {
            r: int((pl.loc[~pl["eligible"], "excl_reason"] == r).sum())
            for r in ["insufficient_history", "season_end_truncation",
                      "window_roster_departure", "window_espn_coverage_gap"]},
        "ground_truth_accounting": inj_acc,
        "event_addressability_by_season": addr.to_dict("records"),
        "exploratory_posthoc": exploratory,
        "artifacts": "experiments/w6_retrospective/ (REPORT.md + CSVs)",
    }
    if record:
        from evalharness.registry import evaluate
        rec = evaluate(EXPERIMENT_ID, results)
        print("\nLEDGER: recorded evaluation run", rec["run_number"],
              "at", rec["eval_time"])
    else:
        print("\nDRY RUN — nothing recorded on the ledger.")
    with open(OUT / "ledger_payload.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=str)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true",
                    help="append the evaluation to experiments/registry.jsonl")
    main(record=ap.parse_args().record)
