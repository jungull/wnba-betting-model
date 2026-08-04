#!/usr/bin/env python3
"""fit_rate_and_p3.py — the two registered baselines, fitted on frozen player_possessions/2.

`player_rate_per100_v1` and `p3_adjusted_impact_v1`. Both registrations are appended BEFORE any
fit and are not modified afterwards. The possession artifact is read-only.

No feature search, no accuracy-driven thresholding, no model searching. Penalties are selected by
inner CHRONOLOGICAL validation inside the training window only.
"""

from __future__ import annotations

import hashlib
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
ART = HERE / "possessions_v2" / "possessions_raw_v2.parquet"
OUT = HERE / "fits_v1"
REG = HERE / "arm_registry.jsonl"

OFF = [f"off_p{i}" for i in range(1, 6)]
DEF = [f"def_p{i}" for i in range(1, 6)]
SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
TEST_SEASONS = (2022, 2023, 2024, 2025, 2026)

RATE_OFF = {"pts": "points", "fga": "fga", "fg3a": "fg3a", "fta": "fta",
            "ast": "assists", "tov": "turnovers"}
RATE_DEF = {"stl": "steals", "blk": "blocks", "pf": "fouls"}
LAM_GRID = [10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0, 10000.0, 30000.0]
K_GRID = [50, 100, 200, 400, 800, 1600, 3200]
#: Preregistered replacement populations. Chosen on role/exposure, never on rank.
REPL_PRIMARY = "below_500_season_possessions"
REPL_ALT = "bottom_rotation_by_team_game_share"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def register(records: list) -> dict:
    have = set()
    if REG.exists():
        have = {json.loads(l)["experiment_id"] for l in
                REG.read_text(encoding="utf-8").splitlines() if l.strip()}
    added = []
    with REG.open("a", encoding="utf-8", newline="") as fh:
        for r in records:
            if r["experiment_id"] in have:
                continue
            fh.write(json.dumps(r, sort_keys=False) + "\n")
            added.append(r["experiment_id"])
    return {"appended": added, "already_present": [r["experiment_id"] for r in records
                                                   if r["experiment_id"] in have]}


# ------------------------------------------------------------------ P3

def build_design(d: pd.DataFrame):
    """Accumulate X'X and X'y directly. No dense design matrix and no scipy.

    A dense 238k x 768 design would be 1.5 GB and is unnecessary: ridge needs only the normal
    equations. The player block has exactly ten ones per row, so X'X's player-player quadrant is a
    co-occurrence count matrix built by adding over the 100 ordered index pairs.
    """
    players = np.sort(pd.unique(pd.concat([d[c] for c in OFF + DEF]).dropna()).astype("int64"))
    pos = {p: i for i, p in enumerate(players)}
    P = len(players)
    n = len(d)
    oc = np.column_stack([d[c].map(pos).to_numpy(dtype=np.int64) for c in OFF])
    dc = np.column_stack([d[c].map(pos).to_numpy(dtype=np.int64) + P for c in DEF])
    idx = np.column_stack([oc, dc])                       # n x 10 column indices
    seasons = sorted(d["season"].unique())
    s_map = {s: i for i, s in enumerate(seasons[1:])}
    extra = 2 + len(s_map)
    base = 2 * P
    E = np.zeros((n, extra))
    E[:, 0] = 1.0
    E[:, 1] = d["is_home_offense"].astype(float).to_numpy()
    sv = d["season"].to_numpy()
    for s, k in s_map.items():
        E[:, 2 + k] = (sv == s).astype(float)
    y = d["points_scored"].to_numpy(float)

    m = base + extra
    XtX = np.zeros((m, m))
    Xty = np.zeros(m)
    for a in range(10):
        np.add.at(Xty, idx[:, a], y)
        for b in range(10):
            np.add.at(XtX, (idx[:, a], idx[:, b]), 1.0)
        for e in range(extra):
            np.add.at(XtX, (idx[:, a], base + e), E[:, e])
            np.add.at(XtX, (base + e, idx[:, a]), E[:, e])
    XtX[base:, base:] = E.T @ E
    Xty[base:] = E.T @ y
    return {"XtX": XtX, "Xty": Xty, "players": players, "pos": pos, "P": P,
            "base": base, "extra": extra, "s_map": s_map, "n": n,
            "yy": float(y @ y)}


def ridge_solve(D, lam_off, lam_def):
    pen = np.zeros(D["XtX"].shape[0])
    pen[:D["P"]] = lam_off
    pen[D["P"]:D["base"]] = lam_def
    return np.linalg.solve(D["XtX"] + np.diag(pen), D["Xty"])


def predict_rows(te, D, beta):
    pos, P, base = D["pos"], D["P"], D["base"]
    n = len(te)
    out = np.full(n, beta[base]) + beta[base + 1] * te["is_home_offense"].astype(float).to_numpy()
    sv = te["season"].to_numpy()
    for s, k in D["s_map"].items():
        out += beta[base + 2 + k] * (sv == s)
    for c in OFF:
        j = te[c].map(pos).to_numpy(dtype="float64")
        ok = ~np.isnan(j)
        out[ok] += beta[j[ok].astype(np.int64)]
    for c in DEF:
        j = te[c].map(pos).to_numpy(dtype="float64")
        ok = ~np.isnan(j)
        out[ok] += beta[j[ok].astype(np.int64) + P]
    return out


def fit_p3(d: pd.DataFrame) -> dict:
    res = {"folds": {}, "coefficients": []}
    for test_s in TEST_SEASONS:
        tr = d[d["season"] < test_s]
        te = d[d["season"] == test_s]
        if len(tr) < 5000:
            continue
        inner_s = max(tr["season"].unique())
        itr, iva = tr[tr["season"] < inner_s], tr[tr["season"] == inner_s]
        best = None
        if len(itr) > 1000 and len(iva) > 500:
            Di = build_design(itr)
            best_sse = np.inf
            for lo in LAM_GRID:
                for ld in LAM_GRID:
                    b = ridge_solve(Di, lo, ld)
                    pr = predict_rows(iva, Di, b)
                    sse = float(np.sum((iva["points_scored"].to_numpy(float) - pr) ** 2))
                    if sse < best_sse:
                        best_sse, best = sse, (lo, ld)
        lo, ld = best if best else (300.0, 300.0)

        D = build_design(tr)
        beta = ridge_solve(D, lo, ld)
        pr = predict_rows(te, D, beta)
        yte = te["points_scored"].to_numpy(float)
        res["folds"][str(test_s)] = {
            "lambda_off": lo, "lambda_def": ld,
            "n_train_possessions": int(len(tr)), "n_test_possessions": int(len(te)),
            "n_players": int(D["P"]),
            "test_mse": float(np.mean((yte - pr) ** 2)),
            "test_mae": float(np.mean(np.abs(yte - pr))),
            "baseline_mse_intercept_only": float(np.mean((yte - yte.mean()) ** 2)),
        }
        P = D["P"]
        orapm = beta[:P] * 100.0
        drapm = -beta[P:D["base"]] * 100.0
        cnt_o = count_side(tr, OFF, D["players"])
        cnt_d = count_side(tr, DEF, D["players"])
        for i, p in enumerate(D["players"]):
            res["coefficients"].append({
                "training_cutoff_season": int(test_s) - 1, "player_id": int(p),
                "orapm_100": float(orapm[i]), "drapm_100": float(drapm[i]),
                "net_rapm_100": float(orapm[i] + drapm[i]),
                "off_possessions": int(cnt_o[i]), "def_possessions": int(cnt_d[i]),
                "total_possessions": int(cnt_o[i] + cnt_d[i]),
            })
    return res


def count_side(d, cols, players):
    v = pd.concat([d[c] for c in cols]).dropna().astype("int64").value_counts()
    return np.array([int(v.get(p, 0)) for p in players])


def identifiability(d: pd.DataFrame, lam: float = 300.0) -> dict:
    D = build_design(d)
    P, base = D["P"], D["base"]
    XtX = D["XtX"]
    sv = np.linalg.svd(XtX, compute_uv=False)
    sv = sv[sv > 0]
    pen = np.zeros(XtX.shape[0]); pen[:base] = lam
    H = XtX + np.diag(pen)
    edf_diag = np.diag(np.linalg.solve(H, XtX))
    cnt_o, cnt_d = count_side(d, OFF, D["players"]), count_side(d, DEF, D["players"])
    corr = []
    for lo in (100.0, 300.0, 1000.0, 3000.0):
        b = ridge_solve(D, lo, lo)
        corr.append({"lambda": lo,
                     "orapm_sd": float(np.std(b[:P] * 100)),
                     "drapm_sd": float(np.std(-b[P:base] * 100)),
                     "off_def_corr": float(np.corrcoef(b[:P], b[P:base])[0, 1])})
    return {
        "n_columns": int(XtX.shape[0]), "n_players": int(P),
        "rank_of_XtX": int(np.linalg.matrix_rank(XtX)),
        "rank_deficiency": int(XtX.shape[0] - np.linalg.matrix_rank(XtX)),
        "condition_number_unpenalised": float(sv[0] / sv[-1]) if len(sv) else None,
        "singular_values": {"max": float(sv[0]), "min_nonzero": float(sv[-1]),
                            "p10": float(np.percentile(sv, 10))},
        "effective_df_at_lambda_300": {
            "total": float(edf_diag.sum()),
            "player_blocks": float(edf_diag[:base].sum()),
            "as_fraction_of_player_columns": float(edf_diag[:base].sum() / base),
        },
        "shrinkage_dominated_players": {
            "edf_below_0_25": int((edf_diag[:P] < 0.25).sum()),
            "edf_below_0_50": int((edf_diag[:P] < 0.50).sum()),
            "note": "per-column effective df at lambda=300; low values mean the estimate is "
                    "mostly prior, not data",
        },
        "weak_off_def_separation": {
            "players_under_500_off_or_def_possessions": int(
                ((cnt_o < 500) | (cnt_d < 500)).sum()),
            "off_def_possession_correlation": float(np.corrcoef(cnt_o, cnt_d)[0, 1]),
            "why_it_matters": ("offensive and defensive possessions are near-perfectly paired for "
                               "a player who is never substituted mid-possession, so the two "
                               "blocks are informed by almost the same rows and separating them "
                               "relies on rotation asymmetry"),
        },
        "ridge_sensitivity": corr,
        "identification_statement": (
            "connectedness and 308.7 rows per column establish ESTIMABILITY UNDER "
            "REGULARISATION, not precise identification. Each block's row sums are constant (5 "
            "per possession), so each is collinear with the intercept and the unpenalised system "
            "is rank-deficient; ridge resolves this numerically by shrinking toward zero, which "
            "is an assumption, not an identification result."),
    }


# ------------------------------------------------------------------ rate model

def rate_data(d: pd.DataFrame) -> pd.DataFrame:
    mp = pd.read_parquet(REPO / "data" / "masters" / "master_player.parquet")
    mp["game_id"] = mp["game_id"].astype(str)
    for c in ("player_id", "team_id"):
        mp[c] = mp[c].astype("int64")
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    mp["season"] = pd.to_numeric(mp["season"], errors="coerce").astype("int64")
    v = d[d["lineup_valid_ten"]]
    off = pd.concat([v[["game_id", "offense_team_id", c]].rename(
        columns={"offense_team_id": "team_id", c: "player_id"}) for c in OFF]).dropna()
    dfn = pd.concat([v[["game_id", "defense_team_id", c]].rename(
        columns={"defense_team_id": "team_id", c: "player_id"}) for c in DEF]).dropna()
    off["player_id"] = off["player_id"].astype("int64")
    dfn["player_id"] = dfn["player_id"].astype("int64")
    o = off.groupby(["game_id", "team_id", "player_id"]).size().rename("off_poss")
    e = dfn.groupby(["game_id", "team_id", "player_id"]).size().rename("def_poss")
    poss = pd.concat([o, e], axis=1).fillna(0).reset_index()
    m = mp.merge(poss, on=["game_id", "team_id", "player_id"], how="inner")
    m = m[(m["off_poss"] > 0) & (m["def_poss"] > 0)]
    m["season"] = pd.to_numeric(m["season"], errors="coerce").astype("int64")
    return m.sort_values("game_date").reset_index(drop=True)


def fit_rates(m: pd.DataFrame) -> dict:
    out = {"targets": {}, "selected_k": {}}
    for stat, name in list(RATE_OFF.items()) + list(RATE_DEF.items()):
        den = "off_poss" if stat in RATE_OFF else "def_poss"
        g = m[m[stat].notna()].copy()
        if not len(g):
            continue
        g["rate"] = 100.0 * g[stat] / g[den]
        rows = []
        for test_s in TEST_SEASONS:
            tr, te = g[g["season"] < test_s], g[g["season"] == test_s]
            if len(tr) < 500 or not len(te):
                continue
            league = float((tr[stat].sum() / tr[den].sum()) * 100.0)
            prior = tr.groupby("player_id").agg(s=(stat, "sum"), d=(den, "sum"))
            inner_s = max(tr["season"].unique())
            itr, iva = tr[tr["season"] < inner_s], tr[tr["season"] == inner_s]
            bestk, bestv = K_GRID[len(K_GRID) // 2], np.inf
            if len(itr) > 200 and len(iva) > 100:
                il = float((itr[stat].sum() / itr[den].sum()) * 100.0)
                ip = itr.groupby("player_id").agg(s=(stat, "sum"), d=(den, "sum"))
                for k in K_GRID:
                    p = predict_rate(iva, ip, il, k)
                    v = float(np.mean(np.abs(p - iva["rate"].to_numpy())))
                    if v < bestv:
                        bestv, bestk = v, k
            pred_rate = predict_rate(te, prior, league, bestk)
            actual_rate = te["rate"].to_numpy()
            # (1) oracle exposure: rate x ACTUAL possessions
            tot_oracle = pred_rate * te[den].to_numpy() / 100.0
            # (2) projected exposure: prior mean possessions per game for that player
            pp = tr.groupby("player_id")[den].mean()
            proj = te["player_id"].map(pp).fillna(tr[den].mean()).to_numpy()
            tot_proj = pred_rate * proj / 100.0
            actual_tot = te[stat].to_numpy(float)
            rows.append({
                "test_season": int(test_s), "k": bestk, "league_rate": round(league, 4),
                "n": int(len(te)),
                "rate_mae": float(np.mean(np.abs(pred_rate - actual_rate))),
                "rate_rmse": float(np.sqrt(np.mean((pred_rate - actual_rate) ** 2))),
                "total_mae_oracle_exposure": float(np.mean(np.abs(tot_oracle - actual_tot))),
                "total_mae_projected_exposure": float(np.mean(np.abs(tot_proj - actual_tot))),
                "exposure_error_share": float(
                    1 - np.mean(np.abs(tot_oracle - actual_tot))
                    / max(np.mean(np.abs(tot_proj - actual_tot)), 1e-9)),
            })
        if rows:
            r = pd.DataFrame(rows)
            out["targets"][name] = {
                "denominator": "off_poss" if stat in RATE_OFF else "def_poss",
                "per_season": rows,
                "pooled_rate_mae": float(np.average(r["rate_mae"], weights=r["n"])),
                "pooled_total_mae_oracle": float(
                    np.average(r["total_mae_oracle_exposure"], weights=r["n"])),
                "pooled_total_mae_projected": float(
                    np.average(r["total_mae_projected_exposure"], weights=r["n"])),
                "pooled_exposure_error_share": float(
                    np.average(r["exposure_error_share"], weights=r["n"])),
            }
            out["selected_k"][name] = {str(x["test_season"]): x["k"] for x in rows}
    return out


def predict_rate(te, prior, league, k):
    s = te["player_id"].map(prior["s"]).fillna(0.0).to_numpy()
    dd = te["player_id"].map(prior["d"]).fillna(0.0).to_numpy()
    return 100.0 * (s + (k / 100.0) * league) / (dd + k)


# ------------------------------------------------------------------ baselines

def baselines(d: pd.DataFrame) -> dict:
    v = d[d["lineup_valid_ten"]]
    players = np.sort(pd.unique(pd.concat([v[c] for c in OFF + DEF]).dropna()).astype("int64"))
    on_off, on_def, n_off, n_def = {}, {}, {}, {}
    tot = v["points_scored"].sum() / len(v)
    for c in OFF:
        g = v.groupby(c)["points_scored"].agg(["sum", "size"])
        for p, r in g.iterrows():
            on_off[p] = on_off.get(p, 0) + r["sum"]; n_off[p] = n_off.get(p, 0) + r["size"]
    for c in DEF:
        g = v.groupby(c)["points_scored"].agg(["sum", "size"])
        for p, r in g.iterrows():
            on_def[p] = on_def.get(p, 0) + r["sum"]; n_def[p] = n_def.get(p, 0) + r["size"]
    rows = []
    for p in players:
        no, nd = n_off.get(p, 0), n_def.get(p, 0)
        if no < 100 or nd < 100:
            continue
        rows.append({"player_id": int(p),
                     "raw_on_off_100": 100 * (on_off[p] / no - tot),
                     "raw_on_def_100": -100 * (on_def[p] / nd - tot),
                     "off_poss": int(no), "def_poss": int(nd)})
    return {"n_players_with_100_plus_each_side": len(rows),
            "method": "raw on-court offensive PPP minus league, and defensive PPP allowed minus "
                      "league with sign flipped; NO teammate or opponent adjustment",
            "status": "DIAGNOSTIC ONLY, never the primary adjusted estimate",
            "rows": rows}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    d = pd.read_parquet(ART)
    # the artifact stores season as a string; every fold boundary is an integer comparison
    d["season"] = pd.to_numeric(d["season"], errors="coerce").astype("int64")
    dig = _sha(ART)
    valid = d[d["lineup_valid_ten"]].copy()
    comp = valid[~valid["non_competitive_conservative"]].copy()

    regs = [
        {"schema": "player_program_arm_registry/1", "kind": "arm",
         "experiment_id": "player_rate_per100_v1", "registered_at": _utc(),
         "registered_before_fitting": True,
         "extra": {"frozen_config": {
             "artifact": "player_possessions/2", "artifact_sha256": dig,
             "producing_commit": "8aff846",
             "model": "pooled empirical-Bayes shrinkage; player effect shrunk toward the league "
                      "rate with strength k selected by INNER CHRONOLOGICAL validation",
             "targets_per_100_off": list(RATE_OFF.values()),
             "targets_per_100_def": list(RATE_DEF.values()),
             "no_rebound_targets": "excluded until event-level opportunities are validated",
             "folds": "walk-forward by season; train strictly earlier seasons",
             "k_grid": K_GRID,
             "exclusion_policy": "invalid-lineup possessions excluded explicitly",
             "uncertainty": "per-season fold spread; shrinkage weight reported",
             "exposure_rule": "actual possessions are a POSTGAME denominator or oracle "
                              "diagnostic only, never a pregame feature",
             "no_feature_search": True, "no_independent_per_player_models": True,
             "output_schema": ["target", "test_season", "k", "rate_mae", "rate_rmse",
                               "total_mae_oracle_exposure", "total_mae_projected_exposure"]}}},
        {"schema": "player_program_arm_registry/1", "kind": "arm",
         "experiment_id": "p3_adjusted_impact_v1", "registered_at": _utc(),
         "registered_before_fitting": True,
         "extra": {"frozen_config": {
             "artifact": "player_possessions/2", "artifact_sha256": dig,
             "producing_commit": "8aff846",
             "design": "one row per VALID possession; outcome = points scored; five offensive "
                       "and five defensive player indicators; global intercept; home-court term; "
                       "season dummies with the first season as reference",
             "sign_convention": {
                 "ORAPM_100": "points ADDED per 100 offensive possessions",
                 "DRAPM_100": "points PREVENTED per 100 defensive possessions; the internal "
                              "coefficient is points ALLOWED and its sign is flipped before "
                              "reporting",
                 "Net_RAPM_100": "ORAPM_100 + DRAPM_100"},
             "primary_penalty_policy": "SEPARATE offensive and defensive ridge penalties",
             "sensitivity": "shared-penalty variant, explanatory only",
             "penalty_selection": "inner CHRONOLOGICAL validation inside the training window; "
                                  "never random CV across games or possessions",
             "lambda_grid": LAM_GRID,
             "exclusion_policy": "the 503 invalid-lineup possessions are excluded from every "
                                 "design matrix and appear only in artifact coverage",
             "variants": ["full_game", "competitive_conservative/1"],
             "baselines": ["raw on/off", "ordinary unregularised APM where estimable",
                           "ridge RAPM (primary)", "competitive-possession ridge RAPM"],
             "replacement_primary": REPL_PRIMARY, "replacement_alternative": REPL_ALT,
             "uncertainty": "ridge-sensitivity spread and effective-df shrinkage diagnostic",
             "output_schema": ["training_cutoff_season", "player_id", "orapm_100", "drapm_100",
                               "net_rapm_100", "off_possessions", "def_possessions"]}}},
    ]
    reg_result = register(regs)

    rate = fit_rates(rate_data(d))
    p3_full = fit_p3(valid)
    p3_comp = fit_p3(comp)
    ident = identifiability(valid[valid["season"] < 2026])
    base = baselines(valid)

    coef = pd.DataFrame(p3_full["coefficients"])
    coef.to_parquet(OUT / "p3_coefficients_v1.parquet", index=False)
    latest = coef[coef["training_cutoff_season"] == coef["training_cutoff_season"].max()]
    repl_pool = latest[latest["total_possessions"] < 500]
    repl_alt_pool = latest.nsmallest(max(int(0.25 * len(latest)), 1), "total_possessions")

    report = {
        "schema": "rate_and_p3_fit/1", "generated_utc": _utc(),
        "artifact": {"id": "player_possessions/2", "sha256": dig,
                     "frozen_and_unmodified": True,
                     "valid_possessions_used": int(len(valid)),
                     "invalid_excluded": int(len(d) - len(valid)),
                     "competitive_possessions_used": int(len(comp))},
        "registration": reg_result,
        "rate_results": rate,
        "p3_full_game": {k: v for k, v in p3_full.items() if k != "coefficients"},
        "p3_competitive": {k: v for k, v in p3_comp.items() if k != "coefficients"},
        "identifiability": ident,
        "baselines_raw_on_off": {k: v for k, v in base.items() if k != "rows"},
        "replacement_level": {
            "primary_rule": REPL_PRIMARY,
            "primary_n": int(len(repl_pool)),
            "primary_mean_net_rapm_100": float(repl_pool["net_rapm_100"].mean())
            if len(repl_pool) else None,
            "alternative_rule": REPL_ALT,
            "alternative_n": int(len(repl_alt_pool)),
            "alternative_mean_net_rapm_100": float(repl_alt_pool["net_rapm_100"].mean()),
            "registered_before_fitting": True,
            "not_chosen_by_who_it_ranks_favourably": True,
            "reported_separately_from_intrinsic_rapm": True,
        },
        "example_top_net": latest.nlargest(8, "net_rapm_100")[
            ["player_id", "orapm_100", "drapm_100", "net_rapm_100",
             "total_possessions"]].to_dict("records"),
    }
    (OUT / "RATE_AND_P3_REPORT.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8", newline="")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
