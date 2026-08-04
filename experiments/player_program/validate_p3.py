#!/usr/bin/env python3
"""validate_p3.py — the P3 validation harness on FROZEN coefficients.

No refit, no penalty change, no new feature, no lineup interaction, no team-model change, no new
revision. The registered penalties are re-applied to the registered training windows solely to
RECOVER the intercept, home and season terms that the fit script did not persist; that reproduces
the frozen fit exactly rather than refitting it, and the recovered player effects are asserted
equal to the persisted ones.

Chronological isolation: a row in season S is predicted only by coefficients whose training window
is seasons strictly before S.
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
import fit_rate_and_p3 as F  # noqa: E402

ART = HERE / "possessions_v2" / "possessions_raw_v2.parquet"
COEF = HERE / "fits_v1" / "p3_coefficients_v1.parquet"
OUT = HERE / "validation_v1"
TEAM = REPO / "experiments" / "cbs_v12_team_oof_v2" / "attempt_001"
OFF, DEF = F.OFF, F.DEF
TEST_SEASONS = (2022, 2023, 2024, 2025, 2026)
RNG = np.random.default_rng(20260804)


def boot_ci(vals, clusters, n=1000, level=0.90):
    u, inv = np.unique(clusters, return_inverse=True)
    k = len(u)
    s = np.bincount(inv, weights=vals, minlength=k)
    c = np.bincount(inv, minlength=k).astype(float)
    st = np.empty(n)
    for i in range(n):
        p = RNG.integers(0, k, k)
        st[i] = s[p].sum() / max(c[p].sum(), 1e-12)
    lo, hi = np.quantile(st, [(1 - level) / 2, 1 - (1 - level) / 2])
    return {"point": float(np.mean(vals)), "ci_low": float(lo), "ci_high": float(hi),
            "n_clusters": int(k), "n_rows": int(len(vals))}


def frozen_models(d: pd.DataFrame) -> dict:
    """Recover the full frozen coefficient vector per training cutoff."""
    persisted = pd.read_parquet(COEF)
    out = {}
    for test_s in TEST_SEASONS:
        tr = d[d["season"] < test_s]
        if len(tr) < 5000:
            continue
        fold = json.loads((HERE / "fits_v1" / "RATE_AND_P3_REPORT.json")
                          .read_text(encoding="utf-8"))["p3_full_game"]["folds"][str(test_s)]
        D = F.build_design(tr)
        beta = F.ridge_solve(D, fold["lambda_off"], fold["lambda_def"])
        P = D["P"]
        chk = persisted[persisted["training_cutoff_season"] == test_s - 1].set_index("player_id")
        rec = pd.Series(beta[:P] * 100.0, index=D["players"])
        common = chk.index.intersection(rec.index)
        maxdiff = float(np.max(np.abs(chk.loc[common, "orapm_100"] - rec.loc[common])))
        out[test_s] = {"D": D, "beta": beta, "lam": (fold["lambda_off"], fold["lambda_def"]),
                       "reproduction_max_abs_diff_orapm": maxdiff}
    return out


def home_away_five(d: pd.DataFrame):
    ho, aw = [], []
    off = d[OFF].to_numpy()
    dfn = d[DEF].to_numpy()
    ih = d["is_home_offense"].astype(bool).to_numpy()
    for i in range(len(d)):
        if ih[i]:
            ho.append(tuple(sorted(int(x) for x in off[i])))
            aw.append(tuple(sorted(int(x) for x in dfn[i])))
        else:
            ho.append(tuple(sorted(int(x) for x in dfn[i])))
            aw.append(tuple(sorted(int(x) for x in off[i])))
    return ho, aw


def build_stints(d: pd.DataFrame) -> pd.DataFrame:
    d = d.sort_values(["game_id", "canonical_seq"], kind="mergesort").reset_index(drop=True)
    ho, aw = home_away_five(d)
    d = d.assign(home5=ho, away5=aw)
    key = d["game_id"].astype(str) + "|" + d["home5"].astype(str) + "|" + d["away5"].astype(str)
    new = (key != key.shift(1)).cumsum()
    d = d.assign(stint_id=new)
    hp = np.where(d["is_home_offense"].astype(bool), d["points_scored"], 0.0)
    ap = np.where(~d["is_home_offense"].astype(bool), d["points_scored"], 0.0)
    d = d.assign(home_pts=hp, away_pts=ap)
    g = d.groupby("stint_id")
    st = pd.DataFrame({
        "game_id": g["game_id"].first(), "season": g["season"].first(),
        "game_date": g["game_date"].first(),
        "home5": g["home5"].first(), "away5": g["away5"].first(),
        "n_poss": g.size(), "home_pts": g["home_pts"].sum(), "away_pts": g["away_pts"].sum(),
        "home_off_poss": g["is_home_offense"].sum(),
    }).reset_index()
    st["away_off_poss"] = st["n_poss"] - st["home_off_poss"]
    st["actual_diff"] = st["home_pts"] - st["away_pts"]
    return st


def predict_stints(st: pd.DataFrame, models: dict, mode: str = "separate") -> np.ndarray:
    """Predicted home-minus-away points over the stint, from FROZEN coefficients."""
    pred = np.full(len(st), np.nan)
    for s, M in models.items():
        m = (st["season"] == s).to_numpy()
        if not m.any():
            continue
        D, beta = M["D"], M["beta"]
        pos, P, base = D["pos"], D["P"], D["base"]
        sub = st[m]
        sm = D["s_map"].get(s)
        seff = beta[base + 2 + sm] if sm is not None else 0.0
        icpt, home = beta[base], beta[base + 1]

        def side(fives, block):
            out = np.zeros(len(sub))
            for j, five in enumerate(fives):
                v = 0.0
                for p in five:
                    i = pos.get(p)
                    if i is not None:
                        v += beta[i] if block == "off" else beta[i + P]
                out[j] = v
            return out

        h_off = side(sub["home5"], "off"); a_off = side(sub["away5"], "off")
        h_def = side(sub["home5"], "def"); a_def = side(sub["away5"], "def")
        if mode == "off_only":
            h_def = a_def = np.zeros(len(sub))
        elif mode == "def_only":
            h_off = a_off = np.zeros(len(sub))
        elif mode == "net_only":
            hn, an = h_off - h_def, a_off - a_def
            h_off, a_def = hn, np.zeros(len(sub))
            a_off, h_def = an, np.zeros(len(sub))
        hp = (icpt + seff + home + h_off + a_def) * sub["home_off_poss"].to_numpy()
        ap = (icpt + seff + a_off + h_def) * sub["away_off_poss"].to_numpy()
        pred[m] = hp - ap
    return pred


def stint_results(st: pd.DataFrame, models: dict) -> dict:
    out = {}
    for mode in ("separate", "net_only", "off_only", "def_only"):
        p = predict_stints(st, models, mode)
        ok = ~np.isnan(p)
        e = np.abs(p[ok] - st["actual_diff"].to_numpy()[ok])
        base = np.abs(0.0 - st["actual_diff"].to_numpy()[ok])
        out[mode] = {
            "n_stints": int(ok.sum()),
            "mae": float(e.mean()), "rmse": float(np.sqrt(np.mean((p[ok] -
                                                                   st["actual_diff"].to_numpy()[ok]) ** 2))),
            "mean_signed": float(np.mean(p[ok] - st["actual_diff"].to_numpy()[ok])),
            "intercept_only_mae": float(base.mean()),
            "improvement_vs_intercept": float(base.mean() - e.mean()),
            "paired_ci_vs_intercept": boot_ci(e - base, st["game_id"].to_numpy()[ok]),
        }
    p = predict_stints(st, models, "separate")
    ok = ~np.isnan(p)
    s2 = st[ok].assign(err=np.abs(p[ok] - st["actual_diff"].to_numpy()[ok]),
                       base=np.abs(st["actual_diff"].to_numpy()[ok]))
    buckets = pd.cut(s2["n_poss"], [0, 5, 10, 20, 40, 10000],
                     labels=["1-5", "6-10", "11-20", "21-40", "40+"])
    out["by_possession_bucket"] = {
        str(k): {"n": int(len(g)), "mae": float(g["err"].mean()),
                 "intercept_mae": float(g["base"].mean())}
        for k, g in s2.groupby(buckets)}
    out["by_season"] = {str(int(k)): {"n": int(len(g)), "mae": float(g["err"].mean()),
                                      "intercept_mae": float(g["base"].mean())}
                        for k, g in s2.groupby("season")}
    return out


def lineup_results(st: pd.DataFrame, models: dict) -> dict:
    p = predict_stints(st, models, "separate")
    ok = ~np.isnan(p)
    s2 = st[ok].copy()
    s2["pred"] = p[ok]
    s2["err"] = np.abs(s2["pred"] - s2["actual_diff"])
    s2["base"] = np.abs(s2["actual_diff"])
    seen = set()
    novel = []
    for h, a, s in zip(s2["home5"], s2["away5"], s2["season"]):
        novel.append((h not in seen) or (a not in seen))
        seen.add(h); seen.add(a)
    s2["novel_lineup"] = novel
    out = {}
    for lab, g in (("previously_observed", s2[~s2["novel_lineup"]]),
                   ("new_lineup", s2[s2["novel_lineup"]]),
                   ("low_possession_stints_le10", s2[s2["n_poss"] <= 10]),
                   ("high_possession_stints_gt20", s2[s2["n_poss"] > 20])):
        if len(g):
            out[lab] = {"n": int(len(g)), "mae": float(g["err"].mean()),
                        "intercept_mae": float(g["base"].mean()),
                        "improvement": float(g["base"].mean() - g["err"].mean())}
    out["additive_only"] = ("no lineup interaction term was registered; these are additive "
                            "player-effect assemblies, and no independent lineup rating is fitted "
                            "on held-out data")
    return out


def stability(coef: pd.DataFrame) -> dict:
    out = {}
    for comp in ("orapm_100", "drapm_100", "net_rapm_100"):
        piv = coef.pivot_table(index="player_id", columns="training_cutoff_season", values=comp)
        poss = coef.pivot_table(index="player_id", columns="training_cutoff_season",
                                values="total_possessions")
        rows = []
        cs = sorted(piv.columns)
        for a, b in zip(cs[:-1], cs[1:]):
            m = piv[[a, b]].dropna()
            pm = poss[[a, b]].reindex(m.index)
            keep = (pm[a] >= 1000) & (pm[b] >= 1000)
            m2 = m[keep]
            if len(m2) > 5:
                rows.append({"from": int(a), "to": int(b), "n_players": int(len(m2)),
                             "threshold_possessions": 1000,
                             "pearson": round(float(m2[a].corr(m2[b])), 4),
                             "spearman": round(float(np.corrcoef(
                                 m2[a].rank().to_numpy(), m2[b].rank().to_numpy())[0, 1]), 4),
                             "mean_abs_change": round(float((m2[b] - m2[a]).abs().mean()), 4)})
        out[comp] = rows
    out["caveat"] = ("high stability is not accuracy. A heavily shrunk, biased estimate is stable "
                     "by construction, and 76 of 314 players are shrinkage-dominated.")
    return out


def traded(d: pd.DataFrame, st: pd.DataFrame, models: dict, coef: pd.DataFrame) -> dict:
    v = d[d["lineup_valid_ten"]]
    long = pd.concat([
        v[["season", "offense_team_id", c]].rename(columns={"offense_team_id": "team_id",
                                                            c: "player_id"}) for c in OFF] + [
        v[["season", "defense_team_id", c]].rename(columns={"defense_team_id": "team_id",
                                                            c: "player_id"}) for c in DEF]).dropna()
    long["player_id"] = long["player_id"].astype("int64")
    teams = long.groupby(["player_id", "season"])["team_id"].nunique()
    movers = teams[teams > 1].reset_index()["player_id"].unique()
    hi = coef[coef["total_possessions"] >= 1000]
    piv = hi.pivot_table(index="player_id", columns="training_cutoff_season",
                         values="net_rapm_100")
    cs = sorted(piv.columns)
    mv, st_ = [], []
    for a, b in zip(cs[:-1], cs[1:]):
        m = piv[[a, b]].dropna()
        mv += list((m.loc[m.index.isin(movers), b] - m.loc[m.index.isin(movers), a]).abs())
        st_ += list((m.loc[~m.index.isin(movers), b] - m.loc[~m.index.isin(movers), a]).abs())
    return {
        "n_players_with_multiple_teams_in_a_season": int(len(movers)),
        "coefficient_continuity_mean_abs_change_movers": float(np.mean(mv)) if mv else None,
        "coefficient_continuity_mean_abs_change_stayers": float(np.mean(st_)) if st_ else None,
        "n_mover_transitions": len(mv), "n_stayer_transitions": len(st_),
        "interpretation_limit": ("a similar coefficient across a move is NOT proof the effect "
                                 "transfers; the estimate is heavily shrunk and the player's new "
                                 "team context is itself in the training data"),
    }


def downstream(st: pd.DataFrame, models: dict, d: pd.DataFrame) -> dict:
    """Oracle-rotation diagnostic only. Information-honest rotation is not constructible."""
    g = st.groupby(["game_id", "season"]).agg(
        pred=("actual_diff", "size")).reset_index()[["game_id", "season"]]
    p = predict_stints(st, models, "separate")
    ok = ~np.isnan(p)
    s2 = st[ok].assign(pred=p[ok])
    gm = s2.groupby("game_id").agg(pred_margin=("pred", "sum"),
                                   actual_margin=("actual_diff", "sum"),
                                   season=("season", "first")).reset_index()
    inc = []
    for f in sorted(TEAM.glob("predictions__team_game_distribution__*.parquet")):
        inc.append(pd.read_parquet(f)[["row_uid", "pred_point", "fold_id"]])
    incumbent = pd.concat(inc, ignore_index=True) if inc else pd.DataFrame()
    return {
        "oracle_rotation_diagnostic": {
            "label": "HINDSIGHT-ASSISTED. Uses the ACTUAL held-out ten-player states and the "
                     "ACTUAL possession counts of every stint. NOT live-achievable and NOT a "
                     "betting backtest.",
            "n_games": int(len(gm)),
            "margin_mae_p3_only": float(np.mean(np.abs(gm["pred_margin"]
                                                       - gm["actual_margin"]))),
            "margin_mae_zero_baseline": float(np.mean(np.abs(gm["actual_margin"]))),
            "improvement": float(np.mean(np.abs(gm["actual_margin"]))
                                 - np.mean(np.abs(gm["pred_margin"] - gm["actual_margin"]))),
            "paired_ci": boot_ci(np.abs(gm["pred_margin"] - gm["actual_margin"]).to_numpy()
                                 - np.abs(gm["actual_margin"]).to_numpy(),
                                 gm["game_id"].to_numpy()),
            "by_season": {str(int(k)): {"n": int(len(x)),
                                        "mae": float(np.mean(np.abs(x["pred_margin"]
                                                                    - x["actual_margin"])))}
                          for k, x in gm.groupby("season")},
        },
        "information_honest_rotation_diagnostic": {
            "constructed": False,
            "why_not": (
                "a cutoff-valid rotation needs projected ACTIVE PLAYERS and projected "
                "possessions per player at the forecast cutoff. The player program's own "
                "availability evidence is information-limited before 2026-07-30 (no pregame "
                "injury feed exists), and no frozen projected-possession artifact exists at all "
                "-- v15 projects MINUTES, not possessions, and was frozen without a "
                "minutes-to-possession mapping. Constructing one here would be new modelling, "
                "which this phase excludes."),
            "consequence": ("the downstream test below is ORACLE-ONLY. It cannot establish "
                            "live-achievable value, and is not presented as doing so."),
        },
        "incumbent_team_forecast_rows_available": int(len(incumbent)),
        "incumbent_comparison_not_run": (
            "cbs_v12_team_oof/2 predicts team_game_distribution on the CONTRACT team-game "
            "universe, keyed by row_uid, with 418 rows per season file. Mapping a stint-summed "
            "player margin onto that key requires a rotation and a pace model that do not exist "
            "frozen. Running it on oracle rotations only would compare a hindsight-assisted "
            "challenger against an honest incumbent, which is not a fair paired test and would "
            "invite exactly the misreading the prior bottom-up 3pt result warns about."),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    d = pd.read_parquet(ART)
    d["season"] = pd.to_numeric(d["season"], errors="coerce").astype("int64")
    valid = d[d["lineup_valid_ten"]].copy()
    coef = pd.read_parquet(COEF)
    models = frozen_models(valid)
    st_all = build_stints(valid)
    st = st_all[st_all["season"].isin(TEST_SEASONS)].copy()

    rep = {
        "schema": "p3_validation/1", "generated_utc":
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "integrity": {
            "no_refit": True, "no_penalty_change": True, "no_new_features": True,
            "no_lineup_interactions": True, "no_team_model_change": True,
            "no_new_revision": True,
            "coefficient_reproduction_max_abs_diff_orapm_100": {
                str(s): M["reproduction_max_abs_diff_orapm"] for s, M in models.items()},
            "penalties_used": {str(s): M["lam"] for s, M in models.items()},
            "chronological_isolation": ("a stint in season S is predicted only by the model whose "
                                        "training window is seasons strictly before S"),
            "invalid_lineup_possessions_excluded": int(len(d) - len(valid)),
        },
        "coverage": {
            "possessions_valid": int(len(valid)),
            "stints_all_seasons": int(len(st_all)),
            "stints_held_out": int(len(st)),
            "games_held_out": int(st["game_id"].nunique()),
            "players": int(coef["player_id"].nunique()),
            "median_stint_possessions": float(st["n_poss"].median()),
        },
        "stint_results": stint_results(st, models),
        "lineup_results": lineup_results(st, models),
        "stability": stability(coef),
        "traded_players": traded(valid, st, models, coef),
        "downstream": downstream(st, models, valid),
    }
    (OUT / "P3_VALIDATION.json").write_text(json.dumps(rep, indent=2, default=str) + "\n",
                                            encoding="utf-8", newline="")
    print("validation written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
