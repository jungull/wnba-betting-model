"""coherence_study — joint-coherence design study (READ-ONLY reconnaissance).

NOT a registered experiment. Fits no promoted models, makes no promotion claims,
never touches the registry, leaderboards, or any existing file. All inputs are
committed artifacts of registered experiments:

  experiments/channel_reval/predictions_v2.csv          (incumbent heads, 673 games)
  experiments/channel_reval/channel_base_v2.csv         (walk-forward observables)
  experiments/w2_integration/game_level_predictions.csv (incumbent per-channel preds, both sides)
  experiments/w2_integration/calibration_params.json    (reproduced incumbent calibrations)
  experiments/bottomup_3pt/teamgame_level_predictions.csv (challenger 3pt per team-game)
  experiments/w4_refs/crew_factors.csv                  (walk-forward crew FTA prior; actual-crew proxy)

Outputs (this folder only):
  decomposition_per_game.csv      per-game c/u decomposition + observables
  decomposition_summary.csv       variance tables by model x scope
  channel_shock_decomposition.csv channel-level covariance split of c and u
  shock_correlates.csv            correlations of c (and |c|) with observables
  recombination_results.csv       margin/total MAE under counterfactual recombinations
  analysis_log.txt                full numeric log (stdout tee)

Error convention throughout: e = prediction - truth.
Decomposition per game: c = (e_h + e_a)/2 (common shock), u = (e_h - e_a)/2
(idiosyncratic). Identities: e_margin_sidediff = e_h - e_a = 2u;
e_total = e_h + e_a = 2c. Rows labeled ORACLE use realized outcomes and can
never be features; rows labeled ANALYTIC-NORMAL assume Gaussian errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\jgallagher\wnba-betting-model")
CR = ROOT / "experiments" / "channel_reval"
W2 = ROOT / "experiments" / "w2_integration"
BU = ROOT / "experiments" / "bottomup_3pt"
W4 = ROOT / "experiments" / "w4_refs"
OUT = ROOT / "experiments" / "coherence_study"

LOG_LINES: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    LOG_LINES.append(str(msg))


def mae(x) -> float:
    return float(np.mean(np.abs(np.asarray(x, dtype=float))))


def var(x) -> float:
    return float(np.var(np.asarray(x, dtype=float), ddof=1))


def cov(x, y) -> float:
    return float(np.cov(np.asarray(x, float), np.asarray(y, float), ddof=1)[0, 1])


def corr(x, y) -> float:
    return float(np.corrcoef(np.asarray(x, float), np.asarray(y, float))[0, 1])


def spearman(x, y) -> float:
    xr = pd.Series(x).rank().to_numpy()
    yr = pd.Series(y).rank().to_numpy()
    return corr(xr, yr)


def check(name: str, got: float, want: float, tol: float) -> None:
    ok = abs(got - want) <= tol
    log(f"  ASSERT {name}: got {got:.6f} want {want:.6f} tol {tol} -> {'OK' if ok else 'FAIL'}")
    if not ok:
        raise AssertionError(f"{name}: {got} vs {want} (tol {tol})")


# ===========================================================================
# 0. Load committed artifacts, reproduce ledgered numbers (trust gate)
# ===========================================================================
log("=" * 78)
log("0. LOAD + REPRODUCE LEDGERED NUMBERS (hard gate before analysis)")
log("=" * 78)

P = pd.read_csv(CR / "predictions_v2.csv")
P["GAME_DATE_h"] = pd.to_datetime(P["GAME_DATE_h"])
assert len(P) == 673, f"predictions_v2 rows {len(P)}"

W = pd.read_csv(W2 / "game_level_predictions.csv")
W["date"] = pd.to_datetime(W["date"])
assert len(W) == 673

B = pd.read_csv(BU / "teamgame_level_predictions.csv")
B["date"] = pd.to_datetime(B["date"])

CB = pd.read_csv(CR / "channel_base_v2.csv")
CB["GAME_DATE"] = pd.to_datetime(CB["GAME_DATE"])

CF = pd.read_csv(W4 / "crew_factors.csv")

with open(W2 / "calibration_params.json", "r", encoding="utf-8") as f:
    CAL = json.load(f)["incumbent_reproduced"]
a_m, b_m = CAL["str_margin"]
a_h, b_h = CAL["str_home"]
a_a, b_a = CAL["str_away"]

# ledger reproduction: incumbent heads on the 673 chanreval test games
e_margin_head = P.str_margin_cal - P.margin_true
check("incumbent margin MAE (chanreval ledger 10.0860)", mae(e_margin_head), 10.0860, 5e-4)
check("incumbent home MAE (gate-4 8.7928)", mae(P.str_home_cal - P.team_pts_h), 8.7928, 5e-4)
check("incumbent away MAE (gate-4 8.6163)", mae(P.str_away_cal - P.team_pts_a), 8.6163, 5e-4)
check("incumbent total MAE (gate-4 14.2236)", mae(P.str_total_cal - P.total_true), 14.2236, 5e-4)

# w2 file must contain the same games with the same incumbent channel preds
M = P.merge(
    W[["game_id", "TEAM_ID_h", "TEAM_ID_a",
       "str_ft_h", "str_3pt_h", "str_paint_h", "str_np2_h",
       "str_ft_a", "str_3pt_a", "str_paint_a", "str_np2_a",
       "ch_ft_h", "ch_3pt_h", "ch_paint_h", "ch_np2_h",
       "ch_ft_a", "ch_3pt_a", "ch_paint_a", "ch_np2_a"]],
    left_on="GAME_ID", right_on="game_id", how="inner", validate="1:1",
)
assert len(M) == 673, "w2 game set != predictions_v2 game set"
S_h = M.str_ft_h + M.str_3pt_h + M.str_paint_h + M.str_np2_h
S_a = M.str_ft_a + M.str_3pt_a + M.str_paint_a + M.str_np2_a
check("rebuild str_home_cal from channels (max|diff|)",
      float((a_h + b_h * S_h - M.str_home_cal).abs().max()), 0.0, 1e-8)
check("rebuild str_away_cal from channels (max|diff|)",
      float((a_a + b_a * S_a - M.str_away_cal).abs().max()), 0.0, 1e-8)
check("rebuild str_margin_cal from channels (max|diff|)",
      float((a_m + b_m * (S_h - S_a) - M.str_margin_cal).abs().max()), 0.0, 1e-8)
M["S_h"], M["S_a"] = S_h, S_a
# actual channel identity: side truth = sum of actual channels
check("channel identity home (max|diff|)",
      float((M.ch_ft_h + M.ch_3pt_h + M.ch_paint_h + M.ch_np2_h - M.team_pts_h).abs().max()),
      0.0, 1e-9)

# bottom-up challenger: home/away wide, incumbent 3pt must match w2's chains
bh = B[B.is_home == 1][["game_id", "actual_3pt_points", "incumbent_pred", "challenger_pred"]]
ba = B[B.is_home == 0][["game_id", "actual_3pt_points", "incumbent_pred", "challenger_pred"]]
BW = bh.merge(ba, on="game_id", suffixes=("_h", "_a"), validate="1:1")
log(f"  bottom-up rows: {len(B)} team-games -> {len(BW)} games with BOTH sides covered "
    f"({len(B) - 2 * len(BW)} single-side rows dropped, registered gate-4 protocol)")
SUB = M.merge(BW, left_on="GAME_ID", right_on="game_id", how="inner", validate="1:1")
check("BU incumbent 3pt == w2 str_3pt, home (max|diff|)",
      float((SUB.incumbent_pred_h - SUB.str_3pt_h).abs().max()), 0.0, 1e-6)
check("BU incumbent 3pt == w2 str_3pt, away (max|diff|)",
      float((SUB.incumbent_pred_a - SUB.str_3pt_a).abs().max()), 0.0, 1e-6)
check("BU actual 3pt == channel actual, home (max|diff|)",
      float((SUB.actual_3pt_points_h - SUB.ch_3pt_h).abs().max()), 0.0, 1e-6)

# substituted variant, exactly the bottomup gate-4 protocol
SUB["sub_S_h"] = SUB.S_h - SUB.str_3pt_h + SUB.challenger_pred_h
SUB["sub_S_a"] = SUB.S_a - SUB.str_3pt_a + SUB.challenger_pred_a
SUB["sub_margin_cal"] = a_m + b_m * (SUB.sub_S_h - SUB.sub_S_a)
SUB["sub_home_cal"] = a_h + b_h * SUB.sub_S_h
SUB["sub_away_cal"] = a_a + b_a * SUB.sub_S_a
log(f"  substitution universe: {len(SUB)} RS games (bottomup REPORT gate-4 used 627)")
check("substituted margin MAE (bottomup gate-4 10.3569)",
      mae(SUB.sub_margin_cal - SUB.margin_true), 10.3569, 5e-4)
check("incumbent margin MAE on same 627 (bottomup gate-4 10.1753)",
      mae(SUB.str_margin_cal - SUB.margin_true), 10.1753, 5e-4)

# ===========================================================================
# 1. Shared-shock decomposition
# ===========================================================================
log("")
log("=" * 78)
log("1. SHARED-SHOCK DECOMPOSITION  (e = pred - truth; c=(e_h+e_a)/2, u=(e_h-e_a)/2)")
log("=" * 78)

M["e_h"] = M.str_home_cal - M.team_pts_h
M["e_a"] = M.str_away_cal - M.team_pts_a
M["c"] = (M.e_h + M.e_a) / 2.0
M["u"] = (M.e_h - M.e_a) / 2.0
M["e_h_unc"] = M.S_h - M.team_pts_h
M["e_a_unc"] = M.S_a - M.team_pts_a
M["c_unc"] = (M.e_h_unc + M.e_a_unc) / 2.0
M["u_unc"] = (M.e_h_unc - M.e_a_unc) / 2.0
# raw-trend model (for design question iv: value of shared structural scaling)
M["e_h_raw"] = M.raw_home_cal - M.team_pts_h
M["e_a_raw"] = M.raw_away_cal - M.team_pts_a

SUB["e_h_sub"] = SUB.sub_home_cal - SUB.team_pts_h
SUB["e_a_sub"] = SUB.sub_away_cal - SUB.team_pts_a
SUB["c_sub"] = (SUB.e_h_sub + SUB.e_a_sub) / 2.0
SUB["u_sub"] = (SUB.e_h_sub - SUB.e_a_sub) / 2.0
SUB["e_h_sub_unc"] = SUB.sub_S_h - SUB.team_pts_h
SUB["e_a_sub_unc"] = SUB.sub_S_a - SUB.team_pts_a
# incumbent restricted to same 627 games
SUB["e_h_inc"] = SUB.str_home_cal - SUB.team_pts_h
SUB["e_a_inc"] = SUB.str_away_cal - SUB.team_pts_a
SUB["c_inc"] = (SUB.e_h_inc + SUB.e_a_inc) / 2.0
SUB["u_inc"] = (SUB.e_h_inc - SUB.e_a_inc) / 2.0


def decomp_row(tag, scope, eh, ea, n=None):
    eh = np.asarray(eh, float)
    ea = np.asarray(ea, float)
    n = len(eh) if n is None else n
    vh, va, cv = var(eh), var(ea), cov(eh, ea)
    r = cv / np.sqrt(vh * va)
    c_ = (eh + ea) / 2.0
    u_ = (eh - ea) / 2.0
    vc, vu = var(c_), var(u_)
    return {
        "model": tag, "scope": scope, "n_games": n,
        "mean_e_h": float(eh.mean()), "mean_e_a": float(ea.mean()),
        "var_e_h": vh, "var_e_a": va, "cov_h_a": cv, "corr_h_a": r,
        "var_c": vc, "var_u": vu,
        "mean_c": float(c_.mean()), "mean_u": float(u_.mean()),
        "common_share": vc / (vc + vu),
        "var_margin_err_2u": 4 * vu, "var_total_err_2c": 4 * vc,
        "side_mae_h": mae(eh), "side_mae_a": mae(ea),
        "margin_mae_sidediff": mae(eh - ea), "total_mae": mae(eh + ea),
    }


rows = []
rows.append(decomp_row("incumbent_cal", "pooled_673", M.e_h, M.e_a))
for s in sorted(M.season_h.unique()):
    m = M.season_h == s
    rows.append(decomp_row("incumbent_cal", f"season_{s}", M.e_h[m], M.e_a[m]))
# half-season stability
for s in sorted(M.season_h.unique()):
    m = M[M.season_h == s].sort_values("GAME_DATE_h")
    half = len(m) // 2
    rows.append(decomp_row("incumbent_cal", f"season_{s}_H1", m.e_h.iloc[:half], m.e_a.iloc[:half]))
    rows.append(decomp_row("incumbent_cal", f"season_{s}_H2", m.e_h.iloc[half:], m.e_a.iloc[half:]))
rows.append(decomp_row("incumbent_uncal", "pooled_673", M.e_h_unc, M.e_a_unc))
rows.append(decomp_row("rawtrend_cal", "pooled_673", M.e_h_raw, M.e_a_raw))
rows.append(decomp_row("incumbent_cal", "rs627", SUB.e_h_inc, SUB.e_a_inc))
rows.append(decomp_row("substituted_cal", "rs627", SUB.e_h_sub, SUB.e_a_sub))
rows.append(decomp_row("incumbent_uncal", "rs627",
                       SUB.S_h - SUB.team_pts_h, SUB.S_a - SUB.team_pts_a))
rows.append(decomp_row("substituted_uncal", "rs627", SUB.e_h_sub_unc, SUB.e_a_sub_unc))
for s in sorted(SUB.season_h.unique()):
    m = SUB.season_h == s
    rows.append(decomp_row("incumbent_cal", f"rs627_season_{s}", SUB.e_h_inc[m], SUB.e_a_inc[m]))
    rows.append(decomp_row("substituted_cal", f"rs627_season_{s}", SUB.e_h_sub[m], SUB.e_a_sub[m]))
D = pd.DataFrame(rows)
D.to_csv(OUT / "decomposition_summary.csv", index=False)

hh = D[(D.model == "incumbent_cal") & (D.scope == "pooled_673")].iloc[0]
log(f"\nINCUMBENT calibrated, 673 games:")
log(f"  var(e_h)={hh.var_e_h:.2f}  var(e_a)={hh.var_e_a:.2f}  cov={hh.cov_h_a:.2f}  corr={hh.corr_h_a:+.4f}")
log(f"  var(c)={hh.var_c:.2f}  var(u)={hh.var_u:.2f}  COMMON SHARE var(c)/(var(c)+var(u)) = {hh.common_share:.4f}")
log(f"  margin err var 4var(u)={hh.var_margin_err_2u:.2f}; total err var 4var(c)={hh.var_total_err_2c:.2f}")
log(f"  (common error mass cancels in margins, DOUBLES in totals: 4var(c)/4var(u) = "
    f"{hh.var_total_err_2c / hh.var_margin_err_2u:.2f}x)")
i627 = D[(D.model == "incumbent_cal") & (D.scope == "rs627")].iloc[0]
s627 = D[(D.model == "substituted_cal") & (D.scope == "rs627")].iloc[0]
log(f"\nSUBSTITUTED (challenger 3pt) vs incumbent on identical {int(s627.n_games)} RS games (calibrated):")
log(f"  corr(e_h,e_a): inc {i627.corr_h_a:+.4f} -> sub {s627.corr_h_a:+.4f}")
log(f"  var(c): {i627.var_c:.2f} -> {s627.var_c:.2f} ({s627.var_c - i627.var_c:+.2f})")
log(f"  var(u): {i627.var_u:.2f} -> {s627.var_u:.2f} ({s627.var_u - i627.var_u:+.2f})")
log(f"  common share: {i627.common_share:.4f} -> {s627.common_share:.4f} "
    f"({s627.common_share - i627.common_share:+.4f})")
log(f"  per-side error variance (avg): {0.5 * (i627.var_e_h + i627.var_e_a):.2f} -> "
    f"{0.5 * (s627.var_e_h + s627.var_e_a):.2f}")

# ===========================================================================
# 1b. Channel-level decomposition of the common shock (which channel drives c?)
# ===========================================================================
log("")
log("=" * 78)
log("1b. CHANNEL DECOMPOSITION OF c AND u (incumbent uncal chains, 673 games)")
log("=" * 78)
ch_names = ["ft", "3pt", "paint", "np2"]
c_parts, u_parts = {}, {}
for ch in ch_names:
    e_ch_h = M[f"str_{ch}_h"] - M[f"ch_{ch}_h"]
    e_ch_a = M[f"str_{ch}_a"] - M[f"ch_{ch}_a"]
    c_parts[ch] = ((e_ch_h + e_ch_a) / 2.0).to_numpy()
    u_parts[ch] = ((e_ch_h - e_ch_a) / 2.0).to_numpy()
c_sum = sum(c_parts.values())
u_sum = sum(u_parts.values())
check("channel c-parts sum to c_unc (max|diff|)",
      float(np.max(np.abs(c_sum - M.c_unc.to_numpy()))), 0.0, 1e-9)
crec = []
for tgt, parts, tot in (("c", c_parts, M.c_unc), ("u", u_parts, M.u_unc)):
    vt = var(tot)
    for ch in ch_names:
        row = {"component": tgt, "channel": ch, "var": var(parts[ch]),
               "var_share_of_total": var(parts[ch]) / vt,
               "cov_with_total": cov(parts[ch], tot),
               "beta_share": cov(parts[ch], tot) / vt}  # variance attribution incl. cross-cov
        for ch2 in ch_names:
            row[f"cov_{ch2}"] = cov(parts[ch], parts[ch2])
        crec.append(row)
    log(f"  {tgt}: total var {vt:.2f}; beta-shares (cov(part,total)/var(total)): " +
        "  ".join(f"{ch} {cov(parts[ch], tot) / vt:+.3f}" for ch in ch_names))
CD = pd.DataFrame(crec)
CD.to_csv(OUT / "channel_shock_decomposition.csv", index=False)
log("  (beta-shares sum to 1; own-variance and cross-channel covariances in "
    "channel_shock_decomposition.csv)")

# ===========================================================================
# 2. What drives the common shock? Walk-forward observables + labeled oracles
# ===========================================================================
log("")
log("=" * 78)
log("2. DRIVERS OF c  (walk-forward observables vs ORACLE context)")
log("=" * 78)

# --- build strictly-prior features from channel_base_v2 --------------------
cb = CB.sort_values(["TEAM_ID", "GAME_DATE"]).copy()
cb["poss_proxy"] = cb.team_fga + 0.44 * cb.team_fta
grp = cb.groupby(["TEAM_ID", "year"], sort=False)
cb["rest_days"] = grp["GAME_DATE"].diff().dt.days.clip(upper=10)
cb["pace_prior"] = grp["poss_proxy"].transform(lambda s: s.shift(1).expanding().mean())
cb["fg3a_prior"] = grp["team_fg3a"].transform(lambda s: s.shift(1).expanding().mean())
cb["prior_games"] = grp.cumcount()

# league scoring environment strictly before each date (game totals)
home_rows = CB[CB.is_home == 1][["GAME_ID", "GAME_DATE", "year", "team_pts", "opp_pts"]].copy()
home_rows["game_total"] = home_rows.team_pts + home_rows.opp_pts
gt = home_rows.sort_values("GAME_DATE").reset_index(drop=True)
gdates = gt.GAME_DATE.to_numpy()
gtotals = gt.game_total.to_numpy()
gyears = gt.year.to_numpy()


def league_env(date, year, days):
    m = (gdates < date) & (gdates >= date - np.timedelta64(days, "D"))
    if m.sum() >= 8:
        return float(gtotals[m].mean())
    m2 = (gdates < date) & (gyears == year)
    return float(gtotals[m2].mean()) if m2.sum() else np.nan


season_start = {int(y): d for y, d in CB.groupby("year")["GAME_DATE"].min().items()}

F = M[["GAME_ID", "GAME_DATE_h", "season_h", "season_type_h", "TEAM_ID_h", "TEAM_ID_a",
       "margin_true", "total_true", "str_margin_cal", "str_total_cal",
       "e_h", "e_a", "c", "u", "c_unc", "u_unc"]].copy()
F["env_total_30d"] = [league_env(d, y, 30) for d, y in zip(F.GAME_DATE_h, F.season_h)]
F["env_total_14d"] = [league_env(d, y, 14) for d, y in zip(F.GAME_DATE_h, F.season_h)]
env_std = []
for d, y in zip(F.GAME_DATE_h, F.season_h):
    m2 = (gdates < d) & (gyears == y)
    env_std.append(float(gtotals[m2].mean()) if m2.sum() else np.nan)
F["env_total_season"] = env_std
F["days_into_season"] = [(d - season_start[int(y)]).days for d, y in zip(F.GAME_DATE_h, F.season_h)]
F["month"] = F.GAME_DATE_h.dt.month

side_feats = cb[["GAME_ID", "TEAM_ID", "rest_days", "pace_prior", "fg3a_prior", "poss_proxy",
                 "prior_games"]]
F = F.merge(side_feats.add_suffix("_hh"), left_on=["GAME_ID", "TEAM_ID_h"],
            right_on=["GAME_ID_hh", "TEAM_ID_hh"], how="left")
F = F.merge(side_feats.add_suffix("_aa"), left_on=["GAME_ID", "TEAM_ID_a"],
            right_on=["GAME_ID_aa", "TEAM_ID_aa"], how="left")
F["rest_h"] = F.rest_days_hh
F["rest_a"] = F.rest_days_aa
F["rest_min"] = F[["rest_h", "rest_a"]].min(axis=1)
F["rest_sum"] = F.rest_h + F.rest_a
F["pace_prior_sum"] = F.pace_prior_hh + F.pace_prior_aa
F["fg3a_prior_sum"] = F.fg3a_prior_hh + F.fg3a_prior_aa
F["season"] = F.season_h.astype(int)

F = F.merge(CF[["GAME_ID", "crew_factor", "crew_prior_mean", "min_ref_n_prior"]],
            on="GAME_ID", how="left")
log(f"  crew factors merged for {F.crew_factor.notna().sum()}/673 games "
    "(w4 caveat: ACTUAL crew as proxy for pregame announcement)")

# ORACLE context columns (never features)
F["ORACLE_pace_realized_sum"] = F.poss_proxy_hh + F.poss_proxy_aa
F["ORACLE_pace_shock"] = F.ORACLE_pace_realized_sum - F.pace_prior_sum
F["ORACLE_hot_cold_vs_env"] = F.total_true - F.env_total_season
F["ORACLE_total_vs_pred"] = F.total_true - F.str_total_cal  # == -2c by identity
check("identity total_true - str_total_cal == -2c (max|diff|)",
      float((F.ORACLE_total_vs_pred + 2 * F.c).abs().max()), 0.0, 1e-9)

wf_feats = ["env_total_30d", "env_total_14d", "env_total_season", "days_into_season", "month",
            "rest_h", "rest_a", "rest_min", "rest_sum",
            "pace_prior_sum", "fg3a_prior_sum", "season",
            "crew_factor", "crew_prior_mean"]
oracle_ctx = ["ORACLE_pace_shock", "ORACLE_pace_realized_sum", "ORACLE_hot_cold_vs_env"]
oracle_chan = {f"ORACLE_c_{ch}": c_parts[ch] for ch in ch_names}
for k, v in oracle_chan.items():
    F[k] = v

corr_rows = []
for cls, feats in (("walkforward", wf_feats), ("ORACLE_context", oracle_ctx + list(oracle_chan))):
    for f_ in feats:
        m = F[f_].notna() & F.c.notna()
        n = int(m.sum())
        if n < 20:
            continue
        corr_rows.append({
            "feature": f_, "class": cls, "n": n,
            "pearson_r_c": corr(F.loc[m, f_], F.loc[m, "c"]),
            "spearman_r_c": spearman(F.loc[m, f_], F.loc[m, "c"]),
            "pearson_r_absc": corr(F.loc[m, f_], F.loc[m, "c"].abs()),
            "pearson_r_u": corr(F.loc[m, f_], F.loc[m, "u"]),
        })
CT = pd.DataFrame(corr_rows).sort_values(["class", "pearson_r_c"],
                                         key=lambda s: s.abs() if s.name == "pearson_r_c" else s,
                                         ascending=[True, False])
CT.to_csv(OUT / "shock_correlates.csv", index=False)
log("\n  correlations with c (walk-forward observables):")
for _, r in CT[CT["class"] == "walkforward"].iterrows():
    log(f"    {r.feature:<20} r={r.pearson_r_c:+.4f}  spearman={r.spearman_r_c:+.4f}  "
        f"r(|c|)={r.pearson_r_absc:+.4f}  r(u)={r.pearson_r_u:+.4f}  n={r.n}")
log("  ORACLE context (uses realized outcomes; decomposition context ONLY, never features):")
for _, r in CT[CT["class"] == "ORACLE_context"].iterrows():
    log(f"    {r.feature:<26} r={r.pearson_r_c:+.4f}  n={r.n}")

# --- multivariate: is c predictable at all? --------------------------------
# In-sample OLS on all walk-forward features (diagnostic ceiling), then honest
# fit-on-2024+2025 / evaluate-on-2026 out-of-sample R^2.
feat_cols = [f_ for f_ in wf_feats if f_ not in ("month", "season")]
sub_f = F.dropna(subset=feat_cols + ["c"]).copy()
X = sub_f[feat_cols].to_numpy(float)
for s in (2025, 2026):
    X = np.column_stack([X, (sub_f.season == s).to_numpy(float)])
X = np.column_stack([np.ones(len(X)), X])
y = sub_f.c.to_numpy(float)
beta, *_ = np.linalg.lstsq(X, y, rcond=None)
r2_in = 1 - np.sum((y - X @ beta) ** 2) / np.sum((y - y.mean()) ** 2)
tr = sub_f.season.isin([2024, 2025]).to_numpy()
Xtr, ytr = X[tr], y[tr]
Xte, yte = X[~tr], y[~tr]
bta, *_ = np.linalg.lstsq(Xtr, ytr, rcond=None)
sse = np.sum((yte - Xte @ bta) ** 2)
sst = np.sum((yte - ytr.mean()) ** 2)
r2_oos = 1 - sse / sst
log(f"\n  c predictability: in-sample OLS R^2 = {r2_in:.4f} "
    f"({len(feat_cols)} walk-forward features + season dummies, n={len(sub_f)})")
log(f"  honest split (fit 2024+2025 -> predict 2026): out-of-sample R^2 = {r2_oos:.4f} "
    f"(n_test={int((~tr).sum())})")
log(f"  sd(c) = {np.std(y, ddof=1):.3f} points; mean(c) = {y.mean():+.3f}")
# same for u
yu = sub_f.u.to_numpy(float)
bu_, *_ = np.linalg.lstsq(X, yu, rcond=None)
r2u_in = 1 - np.sum((yu - X @ bu_) ** 2) / np.sum((yu - yu.mean()) ** 2)
log(f"  u predictability (same features): in-sample R^2 = {r2u_in:.4f}")
PRED_SUMMARY = {"r2_c_insample": float(r2_in), "r2_c_oos_2026": float(r2_oos),
                "r2_u_insample": float(r2u_in), "n": int(len(sub_f))}

# ===========================================================================
# 3. Recombination simulation (existing predictions only; oracles labeled)
# ===========================================================================
log("")
log("=" * 78)
log("3. RECOMBINATION SIMULATION (margin MAE on identical games)")
log("=" * 78)
rec = []


def add(universe, variant, kind, margin_err, total_err=None, note=""):
    row = {"universe": universe, "variant": variant, "kind": kind,
           "margin_mae": mae(margin_err),
           "margin_err_var": var(margin_err),
           "total_mae": mae(total_err) if total_err is not None else np.nan,
           "note": note}
    rec.append(row)
    t = f"  total MAE {row['total_mae']:.4f}" if total_err is not None else ""
    log(f"  [{universe}] {variant:<44} margin MAE {row['margin_mae']:.4f}{t}  ({kind})")


# ---- universe A: all 673 test games (incumbent-only recombinations) -------
tot_err = M.str_total_cal - M.total_true
add("673", "(a) calibrated margin head (incumbent)", "observable",
    M.str_margin_cal - M.margin_true, tot_err, "deployed head")
add("673", "(b) score-head difference home_cal - away_cal", "observable",
    (M.str_home_cal - M.str_away_cal) - M.margin_true, tot_err,
    "= a_h-a_a + b_h*S_h - b_a*S_a; e = e_h - e_a = 2u")
# (c) ORACLE: remove realized common shock c from both sides, then difference
oc_h = M.str_home_cal - M.c
oc_a = M.str_away_cal - M.c
add("673", "(c) ORACLE sides minus common shock, then diff", "ORACLE",
    (oc_h - oc_a) - M.margin_true, (oc_h + oc_a) - M.total_true,
    "margin unchanged vs (b) BY IDENTITY; totals collapse to 0 error")
check("(c) == (b) margin (max|diff|)",
      float(((oc_h - oc_a) - (M.str_home_cal - M.str_away_cal)).abs().max()), 0.0, 1e-9)
side_or = mae(oc_h - M.team_pts_h)
log(f"      ORACLE side MAE after removing c: home {side_or:.4f} vs actual "
    f"{mae(M.e_h):.4f} (side error becomes pure u)")
# ORACLE: remove idiosyncratic u instead (margin collapses, totals unchanged)
add("673", "(c') ORACLE sides minus idiosyncratic u, then diff", "ORACLE",
    (M.str_home_cal - M.u) - (M.str_away_cal + M.u) - M.margin_true,
    (M.str_home_cal - M.u + M.str_away_cal + M.u) - M.total_true,
    "margin error -> 0; totals untouched: u is the ONLY margin-relevant mass")
# ANALYTIC-NORMAL: side errors independent at unchanged side accuracy
vh, va, cv_ = var(M.e_h), var(M.e_a), cov(M.e_h, M.e_a)
mu_h, mu_a = float(M.e_h.mean()), float(M.e_a.mean())


def normal_mae(mu, sd):
    from math import erf, exp, pi, sqrt
    return sd * sqrt(2 / pi) * exp(-mu ** 2 / (2 * sd ** 2)) + mu * erf(mu / (sd * sqrt(2)))


m_ind = normal_mae(mu_h - mu_a, np.sqrt(vh + va))
t_ind = normal_mae(mu_h + mu_a, np.sqrt(vh + va))
log(f"  [673] ANALYTIC-NORMAL if corr(e_h,e_a)=0 at unchanged side accuracy: "
    f"margin MAE ~{m_ind:.3f} (vs {mae(M.e_h - M.e_a):.3f} actual sidediff), "
    f"total MAE ~{t_ind:.3f} (vs {mae(tot_err):.3f})")
log(f"        -> the +{cv_ / np.sqrt(vh * va):.3f} correlation is worth "
    f"~{m_ind - mae(M.e_h - M.e_a):+.2f} margin MAE and costs "
    f"~{t_ind - mae(tot_err):+.2f} total MAE vs independence (pure transfer)")
rec.append({"universe": "673", "variant": "ANALYTIC-NORMAL corr=0 counterfactual",
            "kind": "ANALYTIC-NORMAL", "margin_mae": m_ind, "margin_err_var": vh + va,
            "total_mae": t_ind, "note": "side accuracy fixed, co-movement removed"})

# correlation trade curve (ANALYTIC-NORMAL, fixed side variances)
log("\n  co-movement trade curve (ANALYTIC-NORMAL, side accuracy fixed at incumbent):")
log("    corr      margin_MAE   total_MAE")
for rho in (0.0, 0.10, 0.20, cv_ / np.sqrt(vh * va), 0.40, 0.50):
    sd_m = np.sqrt(vh + va - 2 * rho * np.sqrt(vh * va))
    sd_t = np.sqrt(vh + va + 2 * rho * np.sqrt(vh * va))
    log(f"    {rho:+.3f}    {normal_mae(mu_h - mu_a, sd_m):8.3f}    "
        f"{normal_mae(mu_h + mu_a, sd_t):8.3f}")

# ---- universe B: 627 RS games (substitution recombinations) ---------------
log("")
inc_tot_627 = (SUB.str_home_cal + SUB.str_away_cal) - SUB.total_true
sub_tot_627 = (SUB.sub_home_cal + SUB.sub_away_cal) - SUB.total_true
add("rs627", "(a) incumbent margin head", "observable",
    SUB.str_margin_cal - SUB.margin_true, inc_tot_627)
add("rs627", "(b) incumbent side-head difference", "observable",
    (SUB.str_home_cal - SUB.str_away_cal) - SUB.margin_true, inc_tot_627)
add("rs627", "full substitution (challenger 3pt both sides)", "observable",
    SUB.sub_margin_cal - SUB.margin_true, sub_tot_627, "bottomup gate-4 protocol")

# (d) cancellation-preserving blends at PREDICTION level (observable, no truth used)
inc3_com = (SUB.str_3pt_h + SUB.str_3pt_a) / 2.0
inc3_dif = (SUB.str_3pt_h - SUB.str_3pt_a) / 2.0
ch3_com = (SUB.challenger_pred_h + SUB.challenger_pred_a) / 2.0
ch3_dif = (SUB.challenger_pred_h - SUB.challenger_pred_a) / 2.0
# d2: incumbent common component + challenger differential
d2_S_h = SUB.S_h - SUB.str_3pt_h + (inc3_com + ch3_dif)
d2_S_a = SUB.S_a - SUB.str_3pt_a + (inc3_com - ch3_dif)
d2_margin = a_m + b_m * (d2_S_h - d2_S_a)
d2_total = (a_h + b_h * d2_S_h) + (a_a + b_a * d2_S_a)
add("rs627", "(d2) blend: inc 3pt COMMON + chal 3pt DIFF", "observable",
    d2_margin - SUB.margin_true, d2_total - SUB.total_true,
    "margin IDENTICAL to full substitution (theorem: margins see only differentials)")
check("(d2) margin == full substitution margin (max|diff|)",
      float((d2_margin - SUB.sub_margin_cal).abs().max()), 0.0, 1e-9)
# d3: challenger common component + incumbent differential  <- the actual rescue
d3_S_h = SUB.S_h - SUB.str_3pt_h + (ch3_com + inc3_dif)
d3_S_a = SUB.S_a - SUB.str_3pt_a + (ch3_com - inc3_dif)
d3_margin = a_m + b_m * (d3_S_h - d3_S_a)
d3_total = (a_h + b_h * d3_S_h) + (a_a + b_a * d3_S_a)
add("rs627", "(d3) blend: chal 3pt COMMON + inc 3pt DIFF", "observable",
    d3_margin - SUB.margin_true, d3_total - SUB.total_true,
    "margin IDENTICAL to incumbent; totals move to challenger's — the safe substitution")
check("(d3) margin == incumbent margin head (max|diff|)",
      float((d3_margin - SUB.str_margin_cal).abs().max()), 0.0, 1e-9)
# d4: ORACLE error-space blend c_inc + u_sub
d4_margin_err = 2 * SUB.u_sub
log(f"  [rs627] (d4) ORACLE error blend c_inc+u_sub: margin err = 2*u_sub -> "
    f"MAE {mae(d4_margin_err):.4f} == full-substitution side-diff MAE "
    f"{mae(SUB.e_h_sub - SUB.e_a_sub):.4f} BY IDENTITY (margin never sees c)")
rec.append({"universe": "rs627", "variant": "(d4) ORACLE error blend c_inc + u_sub",
            "kind": "ORACLE", "margin_mae": mae(d4_margin_err),
            "margin_err_var": var(d4_margin_err), "total_mae": np.nan,
            "note": "identical to full substitution side-diff — rescue impossible via c"})

# the direct channel-level test: differential vs common accuracy of the 3pt channel
tru3_dif = (SUB.ch_3pt_h - SUB.ch_3pt_a) / 2.0
tru3_com = (SUB.ch_3pt_h + SUB.ch_3pt_a) / 2.0
log("\n  DIRECT CHANNEL TEST (3pt, per-game, rs627; halves so units = side points):")
log(f"    3pt DIFFERENTIAL MAE: incumbent {mae(inc3_dif - tru3_dif):.4f}  "
    f"challenger {mae(ch3_dif - tru3_dif):.4f}  "
    f"(delta {mae(inc3_dif - tru3_dif) - mae(ch3_dif - tru3_dif):+.4f}, + = chal better)")
log(f"    3pt COMMON/SUM  MAE: incumbent {mae(inc3_com - tru3_com):.4f}  "
    f"challenger {mae(ch3_com - tru3_com):.4f}  "
    f"(delta {mae(inc3_com - tru3_com) - mae(ch3_com - tru3_com):+.4f})")
log(f"    3pt per-side MAE (context, matches bottomup primary): incumbent "
    f"{0.5 * (mae(SUB.str_3pt_h - SUB.ch_3pt_h) + mae(SUB.str_3pt_a - SUB.ch_3pt_a)):.4f}  "
    f"challenger "
    f"{0.5 * (mae(SUB.challenger_pred_h - SUB.ch_3pt_h) + mae(SUB.challenger_pred_a - SUB.ch_3pt_a)):.4f}")
CH3 = {
    "diff_mae_inc": mae(inc3_dif - tru3_dif), "diff_mae_chal": mae(ch3_dif - tru3_dif),
    "com_mae_inc": mae(inc3_com - tru3_com), "com_mae_chal": mae(ch3_com - tru3_com),
}

# ---- ORACLE lambda-shrink of per-channel DIFFERENTIAL error (gain ceilings) ----
log("\n  ORACLE gain ceilings: margin MAE after shrinking one channel's differential "
    "error by lambda (673 games, incumbent chains + margin head):")
lam_rows = []
Sdiff = M.S_h - M.S_a
for ch in ch_names:
    e_dif_ch = (M[f"str_{ch}_h"] - M[f"ch_{ch}_h"]) - (M[f"str_{ch}_a"] - M[f"ch_{ch}_a"])
    for lam in (0.25, 0.5, 1.0):
        mm = a_m + b_m * (Sdiff - lam * e_dif_ch)
        lam_rows.append({"universe": "673", "variant": f"ORACLE shrink {ch} diff err lam={lam}",
                         "kind": "ORACLE", "margin_mae": mae(mm - M.margin_true),
                         "margin_err_var": var(mm - M.margin_true), "total_mae": np.nan,
                         "note": "ceiling for a channel-differential head"})
    got = [r["margin_mae"] for r in lam_rows[-3:]]
    log(f"    {ch:<6} lam 0.25 -> {got[0]:.4f}   lam 0.5 -> {got[1]:.4f}   "
        f"lam 1.0 (full oracle) -> {got[2]:.4f}   (baseline {mae(M.str_margin_cal - M.margin_true):.4f})")
rec.extend(lam_rows)

# ---- 3b. attribution: WHERE does the substitution's margin damage come from? ----
log("")
log("=" * 78)
log("3b. VARIANCE ATTRIBUTION OF THE SUBSTITUTION DAMAGE (uncal, rs627)")
log("=" * 78)
# e_margin_unc = e3_dif + e_rest_dif; rest identical in both models
e3d_inc = (SUB.str_3pt_h - SUB.ch_3pt_h) - (SUB.str_3pt_a - SUB.ch_3pt_a)
e3d_sub = (SUB.challenger_pred_h - SUB.ch_3pt_h) - (SUB.challenger_pred_a - SUB.ch_3pt_a)
erest_d = ((SUB.str_ft_h + SUB.str_paint_h + SUB.str_np2_h)
           - (SUB.ch_ft_h + SUB.ch_paint_h + SUB.ch_np2_h)) \
        - ((SUB.str_ft_a + SUB.str_paint_a + SUB.str_np2_a)
           - (SUB.ch_ft_a + SUB.ch_paint_a + SUB.ch_np2_a))
for tag, e3 in (("incumbent", e3d_inc), ("challenger", e3d_sub)):
    log(f"  {tag:<10} var(e3_dif)={var(e3):8.3f}  cov(e3_dif, e_rest_dif)={cov(e3, erest_d):+8.3f}  "
        f"corr={corr(e3, erest_d):+.4f}  var(margin_unc_err)={var(e3 + erest_d):8.3f}")
d_var = var(e3d_sub) - var(e3d_inc)
d_cov = 2 * (cov(e3d_sub, erest_d) - cov(e3d_inc, erest_d))
log(f"  DELTA var(margin err) = {var(e3d_sub + erest_d) - var(e3d_inc + erest_d):+.3f}  "
    f"= own-variance term {d_var:+.3f} + cross-channel covariance term {d_cov:+.3f}")
log("  -> the challenger's 3pt differential is MORE accurate alone but LESS anti-correlated "
    "with the paint/ft/np2 differential errors; the lost cross-channel cancellation, "
    "not the channel itself, is what degrades the margin.")
# same attribution for the game-total direction (sums)
e3s_inc = (SUB.str_3pt_h - SUB.ch_3pt_h) + (SUB.str_3pt_a - SUB.ch_3pt_a)
e3s_sub = (SUB.challenger_pred_h - SUB.ch_3pt_h) + (SUB.challenger_pred_a - SUB.ch_3pt_a)
erest_s = ((SUB.str_ft_h + SUB.str_paint_h + SUB.str_np2_h)
           - (SUB.ch_ft_h + SUB.ch_paint_h + SUB.ch_np2_h)) \
        + ((SUB.str_ft_a + SUB.str_paint_a + SUB.str_np2_a)
           - (SUB.ch_ft_a + SUB.ch_paint_a + SUB.ch_np2_a))
log(f"  totals direction: var(e3_sum) inc {var(e3s_inc):.3f} -> chal {var(e3s_sub):.3f}; "
    f"cov with rest_sum {cov(e3s_inc, erest_s):+.3f} -> {cov(e3s_sub, erest_s):+.3f}; "
    f"var(total_unc_err) {var(e3s_inc + erest_s):.3f} -> {var(e3s_sub + erest_s):.3f}")
ATTR = {"d_var_margin": float(var(e3d_sub + erest_d) - var(e3d_inc + erest_d)),
        "own_var_term": float(d_var), "cross_cov_term": float(d_cov),
        "corr_e3dif_rest_inc": float(corr(e3d_inc, erest_d)),
        "corr_e3dif_rest_sub": float(corr(e3d_sub, erest_d))}

# ---- 3d. walk-forward common-shock LEVEL tracker (observable; margin-neutral) ----
log("")
log("=" * 78)
log("3d. WALK-FORWARD c LEVEL TRACKER (e) — trailing league-wide mean of realized c,")
log("    strictly prior games; subtracting c_hat from BOTH sides is margin-neutral")
log("    by construction and moves only totals. Grid reported honestly; a registered")
log("    run must preregister (or train-year-tune) the window.")
log("=" * 78)
Msort = M.sort_values("GAME_DATE_h").reset_index(drop=True)
cdates = Msort.GAME_DATE_h.to_numpy()
cvals = Msort.c.to_numpy()
for W_days in (14, 30, 60):
    chat = np.zeros(len(Msort))
    n_used = 0
    for i in range(len(Msort)):
        m = (cdates < cdates[i]) & (cdates >= cdates[i] - np.timedelta64(W_days, "D"))
        if m.sum() >= 8:
            chat[i] = cvals[m].mean()
            n_used += 1
    tot_corrected = Msort.str_total_cal.to_numpy() - 2 * chat
    e_before = Msort.str_total_cal.to_numpy() - Msort.total_true.to_numpy()
    e_after = tot_corrected - Msort.total_true.to_numpy()
    msk26 = (Msort.season_h == 2026).to_numpy()
    r_ = corr(chat[chat != 0], cvals[chat != 0]) if (chat != 0).sum() > 20 else np.nan
    log(f"  W={W_days:>2}d: corrected games {n_used}/673, corr(c_hat,c)={r_:+.4f}; "
        f"total MAE {mae(e_before):.4f} -> {mae(e_after):.4f} "
        f"(delta {mae(e_before) - mae(e_after):+.4f}); "
        f"2026 total bias {e_before[msk26].mean():+.3f} -> {e_after[msk26].mean():+.3f}; "
        f"margin unchanged BY CONSTRUCTION")
    rec.append({"universe": "673", "variant": f"(e) walk-forward c tracker W={W_days}d, totals",
                "kind": "observable", "margin_mae": mae(Msort.str_margin_cal - Msort.margin_true),
                "margin_err_var": var(Msort.str_margin_cal - Msort.margin_true),
                "total_mae": mae(e_after),
                "note": "c_hat subtracted from both sides; margin-neutral by construction"})
    if W_days == 14:
        for lam_t in (0.25, 0.5):
            e_l = (Msort.str_total_cal.to_numpy() - 2 * lam_t * chat) - Msort.total_true.to_numpy()
            log(f"         damped x{lam_t}: total MAE {mae(e_l):.4f} (delta "
                f"{mae(e_before) - mae(e_l):+.4f}); 2026 bias {e_l[msk26].mean():+.3f}  "
                f"[grid line, damping must be preregistered]")
            rec.append({"universe": "673",
                        "variant": f"(e) c tracker W=14d damped x{lam_t}, totals",
                        "kind": "observable",
                        "margin_mae": mae(Msort.str_margin_cal - Msort.margin_true),
                        "margin_err_var": var(Msort.str_margin_cal - Msort.margin_true),
                        "total_mae": mae(e_l), "note": "damped tracker grid line"})

# ---- design-memo power estimate: date-clustered bootstrap CI on the (d3) totals gain ----
log("")
log("=" * 78)
log("3c. (d3) TOTALS GAIN — date-clustered bootstrap CI (DESIGN-MEMO POWER ESTIMATE,")
log("    computed with evalharness bootstrap math but NOT a registered evaluation)")
log("=" * 78)
delta_tot = np.abs(SUB.str_home_cal + SUB.str_away_cal - SUB.total_true).to_numpy() \
          - np.abs(d3_total - SUB.total_true).to_numpy()   # + = d3 better
dates_627 = SUB.GAME_DATE_h.dt.normalize().to_numpy()
rng = np.random.default_rng(20260730)
uniq, inv = np.unique(dates_627, return_inverse=True)
members = [np.flatnonzero(inv == k) for k in range(len(uniq))]
sums = np.array([delta_tot[m].sum() for m in members])
sizes = np.array([len(m) for m in members], float)
draws = rng.integers(0, len(uniq), size=(2000, len(uniq)))
stats = np.array([sums[d].sum() / sizes[d].sum() for d in draws])
lo, hi = np.quantile(stats, [0.05, 0.95])
log(f"  pooled totals improvement (d3 - incumbent): {delta_tot.mean():+.4f} "
    f"(inc {mae(SUB.str_home_cal + SUB.str_away_cal - SUB.total_true):.4f} -> d3 "
    f"{mae(d3_total - SUB.total_true):.4f})")
log(f"  90% date-clustered bootstrap CI: [{lo:+.4f}, {hi:+.4f}]  ({len(uniq)} date clusters, "
    f"n_boot=2000, seed 20260730)")
per_season_d3 = []
for s in sorted(SUB.season_h.unique()):
    m = (SUB.season_h == s).to_numpy()
    per_season_d3.append((int(s), float(delta_tot[m].mean()), int(m.sum())))
    log(f"    season {s}: delta {delta_tot[m].mean():+.4f} (n={m.sum()})")
D3CI = {"pooled_delta": float(delta_tot.mean()), "ci90": [float(lo), float(hi)],
        "per_season": per_season_d3}

# ---- 3e. gate-4 dress rehearsal for (d3) + per-channel differential-weight ceiling ----
log("")
log("=" * 78)
log("3e. (d3) FULL GATE-4 COMPONENTS + per-channel diff-weight margin-head ceiling")
log("=" * 78)
for nm, ph, pa in (("incumbent", SUB.str_home_cal, SUB.str_away_cal),
                   ("d3_blend ", a_h + b_h * d3_S_h, a_a + b_a * d3_S_a)):
    log(f"  {nm}: home {mae(ph - SUB.team_pts_h):.4f}  away {mae(pa - SUB.team_pts_a):.4f}  "
        f"margin(head) {mae((SUB.str_margin_cal if nm.startswith('inc') else d3_margin) - SUB.margin_true):.4f}  "
        f"total {mae(ph + pa - SUB.total_true):.4f}")

# ceiling for family (i)-lite: margin = a + sum_ch w_ch * (str_ch_h - str_ch_a)
# fitted ON THE 673 TEST GAMES -> IN-SAMPLE UPPER BOUND, not an achievable claim.
diffs = np.column_stack([(M[f"str_{ch}_h"] - M[f"str_{ch}_a"]).to_numpy() for ch in ch_names])
Xw = np.column_stack([np.ones(len(M)), diffs])
yw = M.margin_true.to_numpy(float)
bw, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
fit = Xw @ bw
log(f"\n  per-channel differential weights, fit on 673 TEST games (IN-SAMPLE BOUND):")
log(f"    weights: intercept {bw[0]:+.3f}; " +
    "  ".join(f"{ch} {bw[1 + i]:+.4f}" for i, ch in enumerate(ch_names)) +
    f"   (incumbent constrains all four to b_m={b_m:.4f})")
log(f"    margin MAE: {mae(fit - yw):.4f} vs incumbent 10.0860 -> in-sample ceiling "
    f"{mae(M.str_margin_cal - M.margin_true) - mae(fit - yw):+.4f}")
# honest walk-forward flavor: fit weights on 2024+2025 test games, apply to 2026
tr_m = M.season_h.isin([2024, 2025]).to_numpy()
bw2, *_ = np.linalg.lstsq(Xw[tr_m], yw[tr_m], rcond=None)
oos = Xw[~tr_m] @ bw2
inc26 = mae(M.str_margin_cal.to_numpy()[~tr_m] - yw[~tr_m])
log(f"    fit 2024+2025 -> 2026: weighted {mae(oos - yw[~tr_m]):.4f} vs incumbent-2026 "
    f"{inc26:.4f} (delta {inc26 - mae(oos - yw[~tr_m]):+.4f}) "
    f"[diagnostic split, NOT the registered protocol (weights would fit on 2021-23)]")
WCEIL = {"weights_full": [float(x) for x in bw],
         "mae_insample": float(mae(fit - yw)),
         "ceiling_vs_incumbent": float(mae(M.str_margin_cal - M.margin_true) - mae(fit - yw)),
         "oos_2026_delta": float(inc26 - mae(oos - yw[~tr_m]))}

R = pd.DataFrame(rec)
R.to_csv(OUT / "recombination_results.csv", index=False)

# ===========================================================================
# 4. per-game evidence table
# ===========================================================================
per_game = F[["GAME_ID", "GAME_DATE_h", "season_h", "season_type_h",
              "margin_true", "total_true", "str_margin_cal", "str_total_cal",
              "e_h", "e_a", "c", "u", "c_unc", "u_unc"] + wf_feats
             + ["ORACLE_pace_shock", "ORACLE_hot_cold_vs_env"]
             + list(oracle_chan)].copy()
sub_cols = SUB[["GAME_ID", "sub_margin_cal", "e_h_sub", "e_a_sub", "c_sub", "u_sub",
                "c_inc", "u_inc"]]
per_game = per_game.merge(sub_cols, on="GAME_ID", how="left")
per_game.to_csv(OUT / "decomposition_per_game.csv", index=False)

with open(OUT / "analysis_summary.json", "w", encoding="utf-8") as f:
    json.dump({
        "incumbent_673": {k: (float(hh[k]) if isinstance(hh[k], (int, float, np.floating)) else hh[k])
                          for k in ("var_e_h", "var_e_a", "cov_h_a", "corr_h_a", "var_c", "var_u",
                                    "common_share", "side_mae_h", "side_mae_a",
                                    "margin_mae_sidediff", "total_mae")},
        "rs627_incumbent_common_share": float(i627.common_share),
        "rs627_substituted_common_share": float(s627.common_share),
        "predictability": PRED_SUMMARY,
        "channel3pt_diff_common": CH3,
        "substitution_damage_attribution": ATTR,
        "d3_totals_gain_ci": D3CI,
        "diffweight_ceiling": WCEIL,
    }, f, indent=2)

(OUT / "analysis_log.txt").write_text("\n".join(LOG_LINES), encoding="utf-8")
log("\nDONE. Outputs written to experiments/coherence_study/")
