"""Playoff-shift groundwork — descriptive quantification of how the WNBA game
changes from regular season (RS) to playoffs (PO), 2021-2025.

READ-ONLY reconnaissance for the playoff-mode spec (MINUTES_MODEL_SPEC.md 2.1
excludes playoffs from the minutes model; the channel model blends playoff rows
into the same within-season trends). No registration, no model fitting — every
"prediction" below is a frozen, previously-published recipe (minutes B1/B3 with
alpha=0.30 from minutes_baselines run 1; raw-trend channel EWMAs with the
chanreval run-1 alphas) or a bookie line, applied descriptively.

Questions (see REPORT.md):
  Q1 rotation tightening         -> rotation_teamgame.csv, rotation_paired.csv,
                                    rotation_summary.csv
  Q2 minutes predictability      -> minutes_playoff_rows.csv, minutes_mae_summary.csv
  Q3 channel structure shift     -> channel_teamgame.csv, channel_paired.csv,
                                    channel_summary.csv
  Q4 margin predictability       -> margin_test_split.csv (from chanreval
                                    predictions_v2.csv, 46 PO test games)
  Q5 the market                  -> bookie_game_rows.csv, market_summary.csv
  Q6 series carryover            -> series_game_rows.csv, series_summary.csv,
                                    series_paired.csv
  everything                     -> run_summary.json

Conventions reused verbatim from the repo:
  - minutes EWMA: ewm(alpha=0.30, adjust=True).mean().shift(1) within
    (player_id, season), played rows, >=1 prior same-season played appearance
    (minutes_baselines.py; pooled test anchors B1 5.3913 / B3 4.6428).
  - channel EWMA: ewm(alpha, adjust=True).mean().shift(1) within
    (TEAM_ID, season); alphas ft=0.10, 3pt/paint/np2=0.05 (chanreval run 1).
  - bookie margin: home-team rows, latest pre-tip snapshot per (game, book),
    consensus = -mean(spread) (oracle_bracket.build_bookie_margins).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model"
OUT = os.path.join(ROOT, "experiments", "playoff_shift")
MASTER_PLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")
MASTER_TEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")
POSSESSIONS = os.path.join(ROOT, "data", "possessions", "possessions.parquet")
PRED_V2 = os.path.join(ROOT, "experiments", "channel_reval", "predictions_v2.csv")
ODDS_OLD = os.path.join(ROOT, "data", "drive_masters", "master_odds.csv")
ODDS_EXT = os.path.join(ROOT, "data", "odds_capture", "master_odds_extension.csv")

PO_SEASONS = [2021, 2022, 2023, 2024, 2025]
MIN_ALPHA = 0.30                      # minutes_baselines run 1, frozen
CH_ALPHAS = {"ch_ft": 0.10, "ch_3pt": 0.05, "ch_paint": 0.05, "ch_np2": 0.05}

RS, PO = "Regular Season", "Playoffs"
summary: dict = {"generated": pd.Timestamp.now(tz="UTC").isoformat()}


def mae(err: pd.Series | np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(err, dtype=float))))


def paired_stats(diff: pd.Series) -> dict:
    """Descriptive paired stats: mean diff, sd, t = mean/(sd/sqrt(n))."""
    d = diff.dropna().to_numpy(float)
    n = len(d)
    sd = float(np.std(d, ddof=1)) if n > 1 else np.nan
    t = float(np.mean(d) / (sd / np.sqrt(n))) if n > 1 and sd > 0 else np.nan
    return {"n_pairs": n, "mean_diff": float(np.mean(d)) if n else np.nan,
            "sd_diff": sd, "t_stat": t}


def boot_mae_diff(err_a: np.ndarray, err_b: np.ndarray, n_boot: int = 4000,
                  seed: int = 20260731) -> tuple[float, float]:
    """90% bootstrap CI on MAE(a) - MAE(b), independent resamples (descriptive)."""
    rng = np.random.default_rng(seed)
    a = np.abs(np.asarray(err_a, float))
    b = np.abs(np.asarray(err_b, float))
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        diffs[i] = (a[rng.integers(0, len(a), len(a))].mean()
                    - b[rng.integers(0, len(b), len(b))].mean())
    return float(np.quantile(diffs, 0.05)), float(np.quantile(diffs, 0.95))


print("Loading masters ...")
pp = pd.read_parquet(MASTER_PLAYER)
mt = pd.read_parquet(MASTER_TEAM)
poss = pd.read_parquet(POSSESSIONS,
                       columns=["game_id", "season", "season_type",
                                "offense_team_id", "possession_idx"])

# ---------------------------------------------------------------------------
# Q1 — rotation tightening (paired same-team-same-season)
# ---------------------------------------------------------------------------
print("Q1 rotation ...")
played = pp[pp["minutes"].notna() & (pp["minutes"] > 0)].copy()
played["minutes"] = played["minutes"].astype(float)

rows = []
for (gid, tid), g in played.groupby(["game_id", "team_id"], sort=False):
    m = g["minutes"].sort_values(ascending=False).to_numpy()
    tot = m.sum()
    norm = 200.0 / tot                      # OT-normalization to a 40-min game
    starters = g[g["starter_flag"] == 1]["minutes"]
    dressed = pp[(pp["game_id"] == gid) & (pp["team_id"] == tid)]
    rows.append({
        "game_id": gid, "team_id": tid,
        "season": int(g["season"].iloc[0]), "season_type": g["season_type"].iloc[0],
        "game_date": g["game_date"].iloc[0],
        "team_abbreviation": g["team_abbreviation"].iloc[0],
        "n_played": len(m),
        "team_total_min": float(tot),
        "ot_game": int(tot > 205),
        "top5_share": float(m[:5].sum() / tot),
        "top7_share": float(m[:7].sum() / tot),
        "starter_min_avg_raw": float(starters.mean()),
        "starter_min_avg_n40": float(starters.mean() * norm),
        "starter_share": float(starters.sum() / tot),
        "bench_share": float(1.0 - starters.sum() / tot),
        "max_min_n40": float(m.max() * norm),
        "n_35plus_n40": int((m * norm >= 35).sum()),
        "n_30plus_n40": int((m * norm >= 30).sum()),
        "dressed_n": int(len(dressed)),
        "n_dnp": int(dressed["dnp_reason"].notna().sum()),
        "n_dnp_cd": int(dressed["dnp_reason"].astype(str)
                        .str.contains("Coach", na=False).sum()),
    })
rot = pd.DataFrame(rows)
rot.to_csv(os.path.join(OUT, "rotation_teamgame.csv"), index=False)

ROT_METRICS = ["n_played", "top5_share", "top7_share", "starter_min_avg_n40",
               "starter_min_avg_raw", "starter_share", "bench_share",
               "max_min_n40", "n_35plus_n40", "n_30plus_n40",
               "dressed_n", "n_dnp", "n_dnp_cd"]

per_ts = (rot[rot["season"].isin(PO_SEASONS)]
          .groupby(["team_id", "team_abbreviation", "season", "season_type"])
          [ROT_METRICS].mean().reset_index())
wide = per_ts.pivot_table(index=["team_id", "team_abbreviation", "season"],
                          columns="season_type", values=ROT_METRICS)
wide.columns = [f"{m}_{'PO' if st == PO else 'RS'}" for m, st in wide.columns]
wide = wide.reset_index()
paired = wide.dropna(subset=[f"{m}_PO" for m in ROT_METRICS]
                     + [f"{m}_RS" for m in ROT_METRICS])
for m in ROT_METRICS:
    paired = paired.copy()
    paired[f"{m}_diff"] = paired[f"{m}_PO"] - paired[f"{m}_RS"]
paired.to_csv(os.path.join(OUT, "rotation_paired.csv"), index=False)

rot_sum = []
for m in ROT_METRICS:
    for season, sub in list(paired.groupby("season")) + [("pooled", paired)]:
        st = paired_stats(sub[f"{m}_diff"])
        rot_sum.append({"metric": m, "season": season,
                        "rs_mean": float(sub[f"{m}_RS"].mean()),
                        "po_mean": float(sub[f"{m}_PO"].mean()),
                        **st})
rot_sum = pd.DataFrame(rot_sum)
rot_sum.to_csv(os.path.join(OUT, "rotation_summary.csv"), index=False)
summary["q1_rotation_pooled"] = (
    rot_sum[rot_sum["season"] == "pooled"]
    .set_index("metric")[["rs_mean", "po_mean", "mean_diff", "t_stat", "n_pairs"]]
    .round(4).to_dict("index"))

# starter-minutes distribution context (row-level, not paired)
rs_g = rot[(rot["season_type"] == RS) & rot["season"].isin(PO_SEASONS)]
po_g = rot[rot["season_type"] == PO]
summary["q1_context"] = {
    "rs_teamgames": int(len(rs_g)), "po_teamgames": int(len(po_g)),
    "po_ot_rate": float(po_g["ot_game"].mean()),
    "rs_ot_rate": float(rs_g["ot_game"].mean()),
    "starter40_rate_po": float((po_g["max_min_n40"] >= 38).mean()),
    "starter40_rate_rs": float((rs_g["max_min_n40"] >= 38).mean()),
}

# ---------------------------------------------------------------------------
# Q2 — minutes predictability: frozen B3 EWMA carry vs RS-frozen, B1 context
# ---------------------------------------------------------------------------
print("Q2 minutes ...")
P = played.sort_values(["player_id", "season", "game_date", "game_id"],
                       kind="mergesort").reset_index(drop=True)
g = P.groupby(["player_id", "season"], sort=False)
P["prior_apps"] = g.cumcount()
P["pred_b1_carry"] = g["minutes"].shift(1)
P["pred_b3_carry"] = g["minutes"].transform(
    lambda s: s.ewm(alpha=MIN_ALPHA, adjust=True).mean().shift(1))
P["started_last"] = g["starter_flag"].shift(1)

# RS-frozen variants: state at end of the player's regular season, held fixed
# through the playoffs (no playoff-game updates).
is_rs = P["season_type"] == RS
P["rs_minutes"] = P["minutes"].where(is_rs)
grs = P.groupby(["player_id", "season"], sort=False)
P["rs_prior_apps"] = grs["rs_minutes"].transform(
    lambda s: s.notna().cumsum().shift(1).fillna(0))
# shifted EWMA over RS rows only, forward-filled across playoff rows
P["pred_b3_rsfrozen"] = grs["rs_minutes"].transform(
    lambda s: s.dropna().ewm(alpha=MIN_ALPHA, adjust=True).mean()
    .reindex(s.index).ffill().shift(1) if s.notna().any() else s)
# NOTE: the construction above shifts AFTER ffill, which would leak the last
# RS game's own minutes into its own prediction only if ffill crossed rows —
# rebuild explicitly to be safe:
def _rs_frozen(s: pd.Series) -> pd.Series:
    """Shifted EWMA that updates on RS rows only; PO rows get end-of-RS state."""
    vals = s.to_numpy(float)          # NaN on PO rows (rs_minutes)
    out = np.full(len(vals), np.nan)
    state, weight_seen = np.nan, False
    alpha = MIN_ALPHA
    wsum, vsum = 0.0, 0.0             # adjust=True accumulation
    for i, v in enumerate(vals):
        out[i] = state if weight_seen else np.nan
        if not np.isnan(v):           # RS played row -> update state after
            wsum = 1.0 + (1.0 - alpha) * wsum
            vsum = v + (1.0 - alpha) * vsum
            state = vsum / wsum
            weight_seen = True
    return pd.Series(out, index=s.index)

P["pred_b3_rsfrozen"] = grs["rs_minutes"].transform(_rs_frozen)
P["pred_b1_rsfrozen"] = grs["rs_minutes"].transform(
    lambda s: s.ffill().shift(1))     # last RS game's minutes (carried into PO)
# for RS rows pred_b1_rsfrozen == pred_b1_carry by construction; verified below.

P["err_b1_carry"] = P["pred_b1_carry"] - P["minutes"]
P["err_b3_carry"] = P["pred_b3_carry"] - P["minutes"]
P["err_b3_rsfrozen"] = P["pred_b3_rsfrozen"] - P["minutes"]
P["err_b1_rsfrozen"] = P["pred_b1_rsfrozen"] - P["minutes"]

# sanity: on RS rows the carry and rsfrozen variants must agree
rs_rows = P[is_rs & P["pred_b3_carry"].notna() & P["pred_b3_rsfrozen"].notna()]
agree = float((rs_rows["pred_b3_carry"] - rs_rows["pred_b3_rsfrozen"]).abs().max())
assert agree < 1e-9, f"RS-row variant mismatch: {agree}"

po_rows = P[(P["season_type"] == PO) & (P["prior_apps"] >= 1)].copy()
# head-to-head universe: both variants defined (player has >=1 prior played
# game this season AND >=1 RS played game this season)
h2h = po_rows[po_rows["pred_b3_carry"].notna()
              & po_rows["pred_b3_rsfrozen"].notna()].copy()
h2h_out = h2h[["game_id", "season", "game_date", "team_abbreviation",
               "player_id", "player_name", "starter_flag", "started_last",
               "minutes", "prior_apps", "rs_prior_apps",
               "pred_b1_carry", "pred_b3_carry", "pred_b3_rsfrozen",
               "pred_b1_rsfrozen",
               "err_b1_carry", "err_b3_carry", "err_b3_rsfrozen"]]
h2h_out.to_csv(os.path.join(OUT, "minutes_playoff_rows.csv"), index=False)

rs_eval = P[is_rs & (P["prior_apps"] >= 1) & P["season"].isin(PO_SEASONS)]
mrows = []
for label, sub in [("PO 2021-2025", h2h), ("RS 2021-2025 (same seasons)", rs_eval)]:
    mrows.append({
        "universe": label, "n_rows": len(sub),
        "mae_b1_carry": mae(sub["err_b1_carry"]),
        "mae_b3_carry": mae(sub["err_b3_carry"]),
        "mae_b3_rsfrozen": mae(sub["err_b3_rsfrozen"]),
        "bias_b3_carry": float(sub["err_b3_carry"].mean()),
        "bias_b3_rsfrozen": float(sub["err_b3_rsfrozen"].mean()),
        "actual_min_mean": float(sub["minutes"].mean()),
        "actual_min_sd": float(sub["minutes"].std()),
    })
for season in PO_SEASONS:
    sub = h2h[h2h["season"] == season]
    mrows.append({"universe": f"PO {season}", "n_rows": len(sub),
                  "mae_b1_carry": mae(sub["err_b1_carry"]),
                  "mae_b3_carry": mae(sub["err_b3_carry"]),
                  "mae_b3_rsfrozen": mae(sub["err_b3_rsfrozen"]),
                  "bias_b3_carry": float(sub["err_b3_carry"].mean()),
                  "bias_b3_rsfrozen": float(sub["err_b3_rsfrozen"].mean()),
                  "actual_min_mean": float(sub["minutes"].mean()),
                  "actual_min_sd": float(sub["minutes"].std())})
    sub_rs = rs_eval[rs_eval["season"] == season]
    mrows.append({"universe": f"RS {season}", "n_rows": len(sub_rs),
                  "mae_b1_carry": mae(sub_rs["err_b1_carry"]),
                  "mae_b3_carry": mae(sub_rs["err_b3_carry"]),
                  "mae_b3_rsfrozen": mae(sub_rs["err_b3_rsfrozen"]),
                  "bias_b3_carry": float(sub_rs["err_b3_carry"].mean()),
                  "bias_b3_rsfrozen": float(sub_rs["err_b3_rsfrozen"].mean()),
                  "actual_min_mean": float(sub_rs["minutes"].mean()),
                  "actual_min_sd": float(sub_rs["minutes"].std())})
# starter/bench split on playoffs (prior-game starter, spec M1 convention)
for grp, sub in h2h.groupby(h2h["started_last"].fillna(-1)):
    name = {1.0: "PO started_last=1", 0.0: "PO started_last=0",
            -1.0: "PO started_last=NA"}[float(grp)]
    mrows.append({"universe": name, "n_rows": len(sub),
                  "mae_b1_carry": mae(sub["err_b1_carry"]),
                  "mae_b3_carry": mae(sub["err_b3_carry"]),
                  "mae_b3_rsfrozen": mae(sub["err_b3_rsfrozen"]),
                  "bias_b3_carry": float(sub["err_b3_carry"].mean()),
                  "bias_b3_rsfrozen": float(sub["err_b3_rsfrozen"].mean()),
                  "actual_min_mean": float(sub["minutes"].mean()),
                  "actual_min_sd": float(sub["minutes"].std())})
# same split on RS for comparison
for grp, sub in rs_eval.groupby(rs_eval["started_last"].fillna(-1)):
    if float(grp) < 0:
        continue
    name = {1.0: "RS started_last=1", 0.0: "RS started_last=0"}[float(grp)]
    mrows.append({"universe": name, "n_rows": len(sub),
                  "mae_b1_carry": mae(sub["err_b1_carry"]),
                  "mae_b3_carry": mae(sub["err_b3_carry"]),
                  "mae_b3_rsfrozen": mae(sub["err_b3_rsfrozen"]),
                  "bias_b3_carry": float(sub["err_b3_carry"].mean()),
                  "bias_b3_rsfrozen": float(sub["err_b3_rsfrozen"].mean()),
                  "actual_min_mean": float(sub["minutes"].mean()),
                  "actual_min_sd": float(sub["minutes"].std())})
minutes_sum = pd.DataFrame(mrows).round(4)
minutes_sum.to_csv(os.path.join(OUT, "minutes_mae_summary.csv"), index=False)

ci_lo, ci_hi = boot_mae_diff(h2h["err_b3_carry"], h2h["err_b3_rsfrozen"])
summary["q2_minutes"] = {
    "po_n": int(len(h2h)),
    "po_mae_b3_carry": mae(h2h["err_b3_carry"]),
    "po_mae_b3_rsfrozen": mae(h2h["err_b3_rsfrozen"]),
    "carry_minus_rsfrozen_ci90": [ci_lo, ci_hi],
    "rs_mae_b3_same_seasons": mae(rs_eval["err_b3_carry"]),
    "po_mae_b1_carry": mae(h2h["err_b1_carry"]),
    "rs_mae_b1_same_seasons": mae(rs_eval["err_b1_carry"]),
    "anchors_note": "published pooled test anchors (2024-2026 RS): B1 5.3913, B3 4.6428",
    "po_bias_b3_carry_starters": float(
        h2h.loc[h2h["started_last"] == 1, "err_b3_carry"].mean()),
    "po_bias_b3_carry_bench": float(
        h2h.loc[h2h["started_last"] == 0, "err_b3_carry"].mean()),
}

# ---------------------------------------------------------------------------
# Q3 — channel structure shift (paired same-team-same-season)
# ---------------------------------------------------------------------------
print("Q3 channels ...")
T = mt.copy()
for c in ["fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "tov", "pts",
          "pf", "points_paint", "opp_pts"]:
    T[c] = T[c].astype(float)
T["ch_ft"] = T["ftm"]
T["ch_3pt"] = 3.0 * T["fg3m"]
T["pts_2s"] = 2.0 * (T["fgm"] - T["fg3m"])
T["ch_paint"] = T["points_paint"]
T["ch_np2"] = T["pts_2s"] - T["points_paint"]
viol = int((T["ch_ft"] + T["ch_3pt"] + T["pts_2s"] - T["pts"]).abs().gt(0).sum())
assert viol == 0, f"box identity violations: {viol}"
T["box_poss"] = T["fga"] - T["oreb"] + T["tov"] + 0.44 * T["fta"]

pbp_tm = (poss.groupby(["game_id", "offense_team_id"])
          .size().rename("pbp_poss").reset_index()
          .rename(columns={"offense_team_id": "team_id"}))
T = T.merge(pbp_tm, on=["game_id", "team_id"], how="left")

T["ft_rate"] = T["fta"] / T["fga"]
T["fg3a_share"] = T["fg3a"] / T["fga"]
T["paint_share"] = T["ch_paint"] / T["pts"]
T["reg_factor"] = 200.0 / T["minutes"].astype(float)   # OT normalization
for c in ["pts", "ch_ft", "ch_3pt", "ch_paint", "ch_np2", "fta", "fg3a", "pf"]:
    T[f"{c}_per100"] = 100.0 * T[c] / T["box_poss"]
T["box_poss_reg"] = T["box_poss"] * T["reg_factor"]    # possessions per 40 min

CH_METRICS = ["pts", "ch_ft", "ch_3pt", "ch_paint", "ch_np2",
              "box_poss", "box_poss_reg", "pbp_poss",
              "pts_per100", "ch_ft_per100", "ch_3pt_per100",
              "ch_paint_per100", "ch_np2_per100",
              "fta", "fta_per100", "fg3a", "fg3a_per100", "pf", "pf_per100",
              "ft_rate", "fg3a_share", "paint_share"]

ch_cols = ["game_id", "season", "season_type", "game_date", "team_id",
           "team_abbreviation", "is_home", "minutes"] + CH_METRICS
T[ch_cols].to_csv(os.path.join(OUT, "channel_teamgame.csv"), index=False)

per_ts_c = (T[T["season"].isin(PO_SEASONS)]
            .groupby(["team_id", "team_abbreviation", "season", "season_type"])
            [CH_METRICS].mean().reset_index())
wide_c = per_ts_c.pivot_table(index=["team_id", "team_abbreviation", "season"],
                              columns="season_type", values=CH_METRICS)
wide_c.columns = [f"{m}_{'PO' if st == PO else 'RS'}" for m, st in wide_c.columns]
wide_c = wide_c.reset_index().dropna(
    subset=[f"{m}_PO" for m in CH_METRICS if m != "pbp_poss"])
for m in CH_METRICS:
    wide_c[f"{m}_diff"] = wide_c[f"{m}_PO"] - wide_c[f"{m}_RS"]
wide_c.to_csv(os.path.join(OUT, "channel_paired.csv"), index=False)

ch_sum = []
for m in CH_METRICS:
    for season, sub in list(wide_c.groupby("season")) + [("pooled", wide_c)]:
        st = paired_stats(sub[f"{m}_diff"])
        rs_mean = float(sub[f"{m}_RS"].mean())
        ch_sum.append({"metric": m, "season": season, "rs_mean": rs_mean,
                       "po_mean": float(sub[f"{m}_PO"].mean()),
                       "pct_change": (100.0 * st["mean_diff"] / rs_mean
                                      if rs_mean else np.nan), **st})
ch_sum = pd.DataFrame(ch_sum)
ch_sum.to_csv(os.path.join(OUT, "channel_summary.csv"), index=False)
summary["q3_channels_pooled"] = (
    ch_sum[ch_sum["season"] == "pooled"]
    .set_index("metric")[["rs_mean", "po_mean", "mean_diff", "pct_change",
                          "t_stat", "n_pairs"]].round(4).to_dict("index"))

# ---------------------------------------------------------------------------
# Q4 — margin predictability on the chanreval test set
# ---------------------------------------------------------------------------
print("Q4 margin ...")
pred = pd.read_csv(PRED_V2, dtype={"GAME_ID": str})
pred["err_str"] = pred["str_margin_cal"] - pred["margin_true"]
pred["err_raw"] = pred["raw_margin_cal"] - pred["margin_true"]
pred["err_naive"] = pred["naive_margin_pred"] - pred["margin_true"]

# playoff-team lists per season (control: RS games between playoff teams)
po_teams = (mt[mt["season_type"] == PO].groupby("season")["team_abbreviation"]
            .apply(lambda s: set(s.unique())).to_dict())
# abbreviation drift: PHO (<=2024) vs PHX (2025+) already consistent within season.
def both_po_teams(r) -> bool:
    teams = po_teams.get(r["season_h"], set())
    return r["TEAM_ABBREVIATION_h"] in teams and r["TEAM_ABBREVIATION_a"] in teams

pred["both_playoff_teams"] = pred.apply(both_po_teams, axis=1)

def margin_block(name: str, sub: pd.DataFrame) -> dict:
    return {"split": name, "n": len(sub),
            "str_mae": mae(sub["err_str"]), "raw_mae": mae(sub["err_raw"]),
            "naive_mae": mae(sub["err_naive"]),
            "str_edge_vs_naive": mae(sub["err_naive"]) - mae(sub["err_str"]),
            "mean_abs_margin": float(sub["margin_true"].abs().mean()),
            "mean_total": float(sub["total_true"].mean()),
            "str_bias": float(sub["err_str"].mean())}

is_po_t = pred["season_type_h"] == "Playoffs"
in_seasons = pred["season_h"].isin([2024, 2025])
blocks = [
    margin_block("PO 2024-2025 (46 test games)", pred[is_po_t]),
    margin_block("RS 2024-2025 (same seasons)", pred[~is_po_t & in_seasons]),
    margin_block("RS 2024-2025 both-playoff-teams", pred[~is_po_t & in_seasons
                                                         & pred["both_playoff_teams"]]),
    margin_block("RS all test (2024-2026)", pred[~is_po_t]),
    margin_block("PO 2024", pred[is_po_t & (pred["season_h"] == 2024)]),
    margin_block("PO 2025", pred[is_po_t & (pred["season_h"] == 2025)]),
    margin_block("RS 2024", pred[~is_po_t & (pred["season_h"] == 2024)]),
    margin_block("RS 2025", pred[~is_po_t & (pred["season_h"] == 2025)]),
]
margin_df = pd.DataFrame(blocks).round(4)
margin_df.to_csv(os.path.join(OUT, "margin_test_split.csv"), index=False)

po_sub = pred[is_po_t]
rs_sub = pred[~is_po_t & in_seasons]
rs_ctl = pred[~is_po_t & in_seasons & pred["both_playoff_teams"]]
ci_po_rs = boot_mae_diff(po_sub["err_str"], rs_sub["err_str"])
ci_po_ctl = boot_mae_diff(po_sub["err_str"], rs_ctl["err_str"])
summary["q4_margin"] = {
    "po_str_mae": mae(po_sub["err_str"]), "po_n": int(len(po_sub)),
    "rs_same_seasons_str_mae": mae(rs_sub["err_str"]), "rs_n": int(len(rs_sub)),
    "rs_both_po_teams_str_mae": mae(rs_ctl["err_str"]), "rs_ctl_n": int(len(rs_ctl)),
    "po_minus_rs_ci90": ci_po_rs, "po_minus_rs_ctl_ci90": ci_po_ctl,
    "po_naive_mae": mae(po_sub["err_naive"]),
    "rs_naive_mae": mae(rs_sub["err_naive"]),
    "po_edge_vs_naive": mae(po_sub["err_naive"]) - mae(po_sub["err_str"]),
    "rs_edge_vs_naive": mae(rs_sub["err_naive"]) - mae(rs_sub["err_str"]),
}

# ---------------------------------------------------------------------------
# Q5 — the market: bookie margin MAE RS vs PO, and our gap
# ---------------------------------------------------------------------------
print("Q5 market ...")
frames = []
for path in (ODDS_OLD, ODDS_EXT):
    o = pd.read_csv(path, low_memory=False)
    o = o[o["game_id"].notna()].copy()
    o["game_id"] = o["game_id"].astype(np.int64).astype(str)
    o["snap"] = pd.to_datetime(o["odds_snapshot_timestamp"], utc=True, format="mixed")
    o["tip"] = pd.to_datetime(o["odds_commence_time"], utc=True, format="mixed")
    o = o[(o["team"] == o["home_team"]) & (o["snap"] <= o["tip"])
          & o["odds_spread"].notna()]
    o["era_file"] = os.path.basename(path)
    frames.append(o[["game_id", "bookmaker_key", "snap", "tip", "odds_spread",
                     "era_file"]])
allo = pd.concat(frames, ignore_index=True)
last = allo.sort_values("snap").groupby(["game_id", "bookmaker_key"]).tail(1)
bookie = (last.groupby("game_id")
          .agg(bookie_margin=("odds_spread", lambda s: float(-s.mean())),
               n_books=("odds_spread", "size"),
               era_file=("era_file", "first")).reset_index())

# T-65 matched sensitivity (old master is a single ~T-64/65-min snapshot; take
# the extension snapshot nearest 65 min before tip per game-book)
allo["mins_before_tip"] = (allo["tip"] - allo["snap"]).dt.total_seconds() / 60.0
near65 = allo.copy()
near65["dist65"] = (near65["mins_before_tip"] - 65.0).abs()
near65 = near65.sort_values("dist65").groupby(["game_id", "bookmaker_key"]).head(1)
bookie65 = (near65.groupby("game_id")
            .agg(bookie_margin_t65=("odds_spread", lambda s: float(-s.mean())))
            .reset_index())
bookie = bookie.merge(bookie65, on="game_id", how="left")

home = mt[mt["is_home"] == 1][["game_id", "season", "season_type", "game_date",
                               "team_abbreviation", "opp_team_abbreviation",
                               "pts", "opp_pts"]].copy()
home["margin_true"] = home["pts"].astype(float) - home["opp_pts"].astype(float)
bg = home.merge(bookie, on="game_id", how="inner")
bg["bookie_err"] = bg["bookie_margin"] - bg["margin_true"]
bg["bookie_err_t65"] = bg["bookie_margin_t65"] - bg["margin_true"]
# playoff-teams control flag
bg["both_playoff_teams"] = bg.apply(
    lambda r: (r["team_abbreviation"] in po_teams.get(r["season"], set())
               and r["opp_team_abbreviation"] in po_teams.get(r["season"], set())),
    axis=1)
bg = bg.merge(pred[["GAME_ID", "err_str", "str_margin_cal"]]
              .rename(columns={"GAME_ID": "game_id"}), on="game_id", how="left")
bg.to_csv(os.path.join(OUT, "bookie_game_rows.csv"), index=False)

mk_rows = []
def market_block(name, sub, model=False):
    row = {"split": name, "n_games": len(sub),
           "bookie_mae": mae(sub["bookie_err"]),
           "bookie_mae_t65": (mae(sub.loc[sub["bookie_err_t65"].notna(),
                                          "bookie_err_t65"])
                              if sub["bookie_err_t65"].notna().any() else np.nan),
           "mean_n_books": float(sub["n_books"].mean()),
           "mean_abs_margin": float(sub["margin_true"].abs().mean())}
    if model:
        both = sub[sub["err_str"].notna()]
        row.update({"n_model_games": len(both),
                    "model_str_mae": mae(both["err_str"]),
                    "bookie_mae_same_games": mae(both["bookie_err"]),
                    "model_minus_bookie_gap": mae(both["err_str"])
                    - mae(both["bookie_err"])})
    return row

for season in [2022, 2023, 2024, 2025, 2026]:
    for st_name, st_flag in [("RS", RS), ("PO", PO)]:
        sub = bg[(bg["season"] == season) & (bg["season_type"] == st_flag)]
        if len(sub):
            mk_rows.append(market_block(f"{st_name} {season}", sub,
                                        model=season in (2024, 2025)))
mk_rows.append(market_block("PO pooled 2023-2025",
                            bg[bg["season_type"] == PO]))
mk_rows.append(market_block(
    "RS pooled 2023-2025 (same seasons w/ PO odds)",
    bg[(bg["season_type"] == RS) & bg["season"].isin([2023, 2024, 2025])]))
mk_rows.append(market_block(
    "RS pooled 2023-2025 both-playoff-teams",
    bg[(bg["season_type"] == RS) & bg["season"].isin([2023, 2024, 2025])
       & bg["both_playoff_teams"]]))
mk_rows.append(market_block("PO 2024-2025 (chanreval overlap)",
                            bg[(bg["season_type"] == PO)
                               & bg["season"].isin([2024, 2025])], model=True))
mk_rows.append(market_block("RS 2024-2025 (chanreval overlap)",
                            bg[(bg["season_type"] == RS)
                               & bg["season"].isin([2024, 2025])], model=True))
market_df = pd.DataFrame(mk_rows).round(4)
market_df.to_csv(os.path.join(OUT, "market_summary.csv"), index=False)

po_bg = bg[bg["season_type"] == PO]
rs_bg = bg[(bg["season_type"] == RS) & bg["season"].isin([2023, 2024, 2025])]
rs_bg_ctl = rs_bg[rs_bg["both_playoff_teams"]]
ci_bk = boot_mae_diff(po_bg["bookie_err"], rs_bg["bookie_err"])
ci_bk_ctl = boot_mae_diff(po_bg["bookie_err"], rs_bg_ctl["bookie_err"])
po_ov = bg[(bg["season_type"] == PO) & bg["err_str"].notna()]
rs_ov = bg[(bg["season_type"] == RS) & bg["season"].isin([2024, 2025])
           & bg["err_str"].notna()]
summary["q5_market"] = {
    "po_bookie_mae": mae(po_bg["bookie_err"]), "po_n": int(len(po_bg)),
    "rs_bookie_mae_2023_2025": mae(rs_bg["bookie_err"]), "rs_n": int(len(rs_bg)),
    "rs_bookie_mae_both_po_teams": mae(rs_bg_ctl["bookie_err"]),
    "rs_ctl_n": int(len(rs_bg_ctl)),
    "po_minus_rs_bookie_ci90": ci_bk,
    "po_minus_rs_ctl_bookie_ci90": ci_bk_ctl,
    "gap_po_2024_2025": {"n": int(len(po_ov)),
                         "model_mae": mae(po_ov["err_str"]),
                         "bookie_mae": mae(po_ov["bookie_err"]),
                         "gap": mae(po_ov["err_str"]) - mae(po_ov["bookie_err"])},
    "gap_rs_2024_2025": {"n": int(len(rs_ov)),
                         "model_mae": mae(rs_ov["err_str"]),
                         "bookie_mae": mae(rs_ov["bookie_err"]),
                         "gap": mae(rs_ov["err_str"]) - mae(rs_ov["bookie_err"])},
}

# ---------------------------------------------------------------------------
# Q6 — series context: do errors shrink by game 3+ of a series?
# ---------------------------------------------------------------------------
print("Q6 series ...")
# frozen raw-trend channel EWMA (chanreval run-1 alphas), within (team, season),
# RS+PO blended chronologically — exactly how the current model treats playoffs
Tc = T.sort_values(["team_id", "season", "game_date", "game_id"],
                   kind="mergesort").reset_index(drop=True)
gt = Tc.groupby(["team_id", "season"], sort=False)
Tc["prior_games"] = gt.cumcount()
for ch, a in CH_ALPHAS.items():
    Tc[f"pred_{ch}"] = gt[ch].transform(
        lambda s, a=a: s.ewm(alpha=a, adjust=True).mean().shift(1))
    Tc[f"abserr_{ch}"] = (Tc[f"pred_{ch}"] - Tc[ch]).abs()
Tc["pred_pts_sum"] = sum(Tc[f"pred_{ch}"] for ch in CH_ALPHAS)
Tc["abserr_pts_sum"] = (Tc["pred_pts_sum"] - Tc["pts"]).abs()

po_t = Tc[(Tc["season_type"] == PO) & (Tc["prior_games"] >= 5)].copy()
pair_key = po_t.apply(
    lambda r: "-".join(sorted([str(int(r["team_id"])),
                               str(int(mt.loc[(mt["game_id"] == r["game_id"])
                                              & (mt["team_id"] != r["team_id"]),
                                              "team_id"].iloc[0]))])), axis=1)
po_t["series_id"] = po_t["season"].astype(str) + "_" + pair_key
# game number within series must be ranked over unique GAMES, not team-rows
game_order = (po_t[["series_id", "game_id", "game_date"]].drop_duplicates()
              .sort_values(["series_id", "game_date", "game_id"]))
game_order["series_game_num"] = game_order.groupby("series_id").cumcount() + 1
po_t = po_t.merge(game_order[["series_id", "game_id", "series_game_num"]],
                  on=["series_id", "game_id"], how="left")

# margin errors by series game (chanreval predictions, 2024-25 only)
pm = pred[pred["season_type_h"] == "Playoffs"][["GAME_ID", "err_str"]]
po_games = (po_t[po_t["is_home"] == 1]
            [["game_id", "season", "series_id", "series_game_num", "game_date"]]
            .merge(pm.rename(columns={"GAME_ID": "game_id"}),
                   on="game_id", how="left"))
po_t.to_csv(os.path.join(OUT, "series_game_rows.csv"), index=False)

ser_rows = []
for gn, sub in po_t.groupby(po_t["series_game_num"].clip(upper=4)):
    label = f"game {int(gn)}" if gn < 4 else "game 4+"
    row = {"series_game": label, "n_teamgames": len(sub),
           "n_games": int(sub["game_id"].nunique())}
    for ch in CH_ALPHAS:
        row[f"mae_{ch}"] = float(sub[f"abserr_{ch}"].mean())
    row["mae_pts_sum"] = float(sub["abserr_pts_sum"].mean())
    gsub = po_games[po_games["series_game_num"].clip(upper=4) == gn]
    row["margin_mae_str_2024_25"] = (mae(gsub.loc[gsub["err_str"].notna(),
                                                  "err_str"])
                                     if gsub["err_str"].notna().any() else np.nan)
    row["n_margin_games"] = int(gsub["err_str"].notna().sum())
    ser_rows.append(row)
# bucket comparison rows: games 1-2 vs 3+
b12 = po_t[po_t["series_game_num"] <= 2]
b3p = po_t[po_t["series_game_num"] >= 3]
for label, sub in [("games 1-2", b12), ("games 3+", b3p)]:
    row = {"series_game": label, "n_teamgames": len(sub),
           "n_games": int(sub["game_id"].nunique())}
    for ch in CH_ALPHAS:
        row[f"mae_{ch}"] = float(sub[f"abserr_{ch}"].mean())
    row["mae_pts_sum"] = float(sub["abserr_pts_sum"].mean())
    gid = set(sub["game_id"])
    gsub = po_games[po_games["game_id"].isin(gid) & po_games["err_str"].notna()]
    row["margin_mae_str_2024_25"] = mae(gsub["err_str"]) if len(gsub) else np.nan
    row["n_margin_games"] = int(len(gsub))
    ser_rows.append(row)
series_sum = pd.DataFrame(ser_rows).round(4)
series_sum.to_csv(os.path.join(OUT, "series_summary.csv"), index=False)

# series-paired: within series reaching game 3, per-team mean abs err g1-2 vs g3+
pair_rows = []
for (sid, tid), sub in po_t.groupby(["series_id", "team_id"]):
    if sub["series_game_num"].max() < 3:
        continue
    early = sub[sub["series_game_num"] <= 2]
    late = sub[sub["series_game_num"] >= 3]
    row = {"series_id": sid, "team_id": tid,
           "season": int(sub["season"].iloc[0]),
           "team_abbreviation": sub["team_abbreviation"].iloc[0],
           "n_early": len(early), "n_late": len(late)}
    for ch in list(CH_ALPHAS) + ["pts_sum"]:
        row[f"early_{ch}"] = float(early[f"abserr_{ch}"].mean())
        row[f"late_{ch}"] = float(late[f"abserr_{ch}"].mean())
        row[f"diff_{ch}"] = row[f"late_{ch}"] - row[f"early_{ch}"]
    pair_rows.append(row)
series_paired = pd.DataFrame(pair_rows)
series_paired.to_csv(os.path.join(OUT, "series_paired.csv"), index=False)

summary["q6_series"] = {
    "n_series_team_pairs_reaching_g3": int(len(series_paired)),
    "late_minus_early_abserr": {
        ch: paired_stats(series_paired[f"diff_{ch}"])
        for ch in list(CH_ALPHAS) + ["pts_sum"]},
    "by_game_table": series_sum.to_dict("records"),
}

with open(os.path.join(OUT, "run_summary.json"), "w") as f:
    json.dump(summary, f, indent=2, default=str)
print("DONE — outputs in", OUT)
