#!/usr/bin/env python3
"""run_ws5.py — ws5_opportunity_proxies: gate, fit, evaluate the six frozen proxies in three roles.

Mirrors experiments/player_program/run_turnover_p2.py: Poisson ridge (lambda=10), offset =
log(exposure) + log(frozen Arm D rate) so beta = 0 reproduces Arm D exactly, walk-forward by season,
training-fold standardisation only.

`feature_gate.audit` runs on the EXACT standardised design matrix of every (arm, season) fold
BEFORE that fold is fitted, and fails closed. All audits are written to WS5_FEATURE_GATE.json.

CONTROL ARM K0 (coordinator amendment, added before results were read): every Poisson-ridge arm
carries an UNPENALISED INTERCEPT that unfitted Arm D does not have, so free recalibration alone
supplies a gain of the same order as the effects being hunted. K0 is that recalibration and nothing
else -- zero features, identical pipeline, folds, offset and standardisation path. Every proxy arm
is therefore reported against BOTH baselines: vs Arm D (as registered) and vs K0 (the honest test of
whether the PROXY adds anything beyond recalibration).

Development-only. Modifies no canonical artifact, no Arm D, and never touches arm_registry.jsonl.
"""
from __future__ import annotations
import hashlib, json, sys                                                      # noqa: E401
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(PP)); sys.path.insert(0, str(ROOT))
from evalharness.compare import cluster_bootstrap_ci                           # noqa: E402
from feature_gate import audit as gate_audit, FeatureGateFailure               # noqa: E402
from freeze_ws5 import BOOT_SEED, MIN_TRAIN_ROWS, RIDGE_LAMBDA                 # noqa: E402
from run_turnover_p2 import poisson_ridge, _pois_dev                          # noqa: E402

PROXIES = ["x1_fga_share", "x2_pe_per36", "x3_pe_share", "x4_pe_share_delta",
           "x5_involvement_rank", "x6_responsibility_share"]

# K0: the recalibration-only control. Zero features, unpenalised intercept, same everything else.
CONTROL = {"K0": []}
DFREE = {"Dfree": ["logD"]}                       # free Arm-D coefficient, nested reference
RATE_ARMS = {f"R{i+1}": [p] for i, p in enumerate(PROXIES)}          # role (a)
INTER_ARMS = {f"X{i+1}": {"base": [p, "logD"], "inter": [(p, "logD")]}
              for i, p in enumerate(PROXIES)}                        # role (b)
# role (c2): pure unfitted allocation weights. The frozen spec labels these P1..P6; rendered PW_k
# here purely to avoid collision with the P1 program phase. No semantic change.
PURE_W = {"PW1": ("x1_fga_share", "identity"), "PW2": ("x2_pe_per36", "identity"),
          "PW3": ("x3_pe_share", "identity"), "PW5": ("x5_involvement_rank", "inverse_rank"),
          "PW6": ("x6_responsibility_share", "identity")}
# PW4 is NOT constructible: x4 can be negative. Declared in the freeze, not decided here.
BASELINES = ["D", "K0"]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def standardise(tr: pd.DataFrame, te: pd.DataFrame, cols: list[str], inter: list[tuple]):
    """Training-fold means/sds only. Products are formed AFTER standardisation."""
    if not cols:
        return (pd.DataFrame(index=tr.index), pd.DataFrame(index=te.index), [])
    mu, sd = tr[cols].mean(), tr[cols].std().replace(0, 1.0)
    Ztr = ((tr[cols] - mu) / sd).fillna(0.0)
    Zte = ((te[cols] - mu) / sd).fillna(0.0)
    names = list(cols)
    for a, b in inter:
        n = f"{a}__X__{b}"
        Ztr[n], Zte[n] = Ztr[a] * Ztr[b], Zte[a] * Zte[b]
        names.append(n)
    return Ztr[names], Zte[names], names


def input_defect_receipt(F: pd.DataFrame, O: pd.DataFrame, key: list[str]) -> dict:
    """Coordinator amendment: `turnover_p2_v1/turnover_role_context_features_v1.parquet` was built
    by iterating REALISED box rows and left-merging onto the candidate universe, so its columns are
    NULL exactly on non-appearing candidates -- an exact did_appear indicator on the operational
    track. ws5 does not consume that artifact; every ws5 proxy is rebuilt so state is READ for every
    Tier A candidate. This receipt proves both halves: the defect is real, and ws5 is clean."""
    P2 = pd.read_parquet(PP / "turnover_p2_v1/turnover_role_context_features_v1.parquet",
                         columns=key + ["offensive_involvement_proxy", "trailing_minutes_share",
                                        "role_change"])
    j = O[key + ["did_appear"]].merge(P2, on=key, how="left").merge(
        F[key + PROXIES], on=key, how="left")
    rec = {"canonical_artifact": "turnover_p2_v1/turnover_role_context_features_v1.parquet",
           "operational_rows": int(len(j)), "appearers": int(j["did_appear"].sum()),
           "non_appearers": int((~j["did_appear"]).sum()), "canonical_columns": {}}
    for c in ("offensive_involvement_proxy", "trailing_minutes_share", "role_change"):
        nn = j[c].notna()
        rec["canonical_columns"][c] = {
            "non_null": int(nn.sum()), "null": int((~nn).sum()),
            "null_and_appearing": int(((~nn) & j["did_appear"]).sum()),
            "non_null_and_non_appearing": int((nn & ~j["did_appear"]).sum()),
            "is_exact_did_appear_indicator": bool(((~nn) & j["did_appear"]).sum() == 0
                                                  and (nn & ~j["did_appear"]).sum() == 0)}
    rec["ws5_rebuilt_columns"] = {
        p: {"non_null": int(j[p].notna().sum()), "null": int(j[p].isna().sum())} for p in PROXIES}
    m = j["offensive_involvement_proxy"].notna()
    rec["ws5_x1_vs_canonical"] = {
        "max_abs_diff_where_canonical_defined": float(
            (j.loc[m, "x1_fga_share"] - j.loc[m, "offensive_involvement_proxy"]).abs().max()),
        "rows_canonical_null_but_ws5_present": int((~m & j["x1_fga_share"].notna()).sum()),
        "of_those_non_appearing": int((~m & j["x1_fga_share"].notna() & ~j["did_appear"]).sum()),
        "reading": ("ws5 x1 reproduces the canonical FGA-share formula EXACTLY wherever the "
                    "canonical is defined, and supplies genuine strictly-prior values on the "
                    "non-appearing candidates where the canonical is null. ws5 R1 is therefore the "
                    "clean re-measurement of P2 arm G.")}
    rec["columns_ws5_never_consumed"] = ["trailing_minutes_share", "role_change",
                                         "offensive_involvement_proxy"]
    rec["canonical_artifact_not_modified"] = True
    return rec


def main() -> int:
    audits: list[dict] = []
    F = pd.read_parquet(HERE / "ws5_opportunity_proxy_features_v1.parquet")
    key = ["game_id", "team_id", "player_id"]

    P1O = pd.read_parquet(PP / "turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet")
    P1I = pd.read_parquet(PP / "turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet")
    if "exposure" not in P1I.columns:
        P1I = P1I.rename(columns={"realised_off_possessions": "exposure"})
    TM = pd.read_parquet(PP / "turnover_targets_v1/team_turnover_reconciliation_v1.parquet")
    C = pd.read_parquet(ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet",
                        columns=["game_id", "season"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)

    O = P1O.merge(F[key + PROXIES], on=key, how="left")
    I = P1I.merge(F[key + PROXIES], on=key, how="left")
    for d in (O, I):
        d["logD"] = np.log(np.clip(d["D_ewma_shrunk"].to_numpy(float), 1e-9, None))

    defect = input_defect_receipt(F, P1O, key)
    (HERE / "WS5_INPUT_DEFECT_RECEIPT.json").write_text(json.dumps(defect, indent=2, default=str),
                                                        encoding="utf-8")
    print("canonical P2 involvement proxy is an exact did_appear indicator: "
          f"{defect['canonical_columns']['offensive_involvement_proxy']['is_exact_did_appear_indicator']}"
          f" | ws5 rebuilt x1 nulls on operational: "
          f"{defect['ws5_rebuilt_columns']['x1_fga_share']['null']}")

    # ---------------- REDUNDANCY vs the frozen P1 EWMA turnover rate --------------------- #
    redundancy = {}
    for trk, d in (("intrinsic", I), ("operational", O)):
        blk = {}
        for p in PROXIES:
            m = d[p].notna()
            r_lin = float(np.corrcoef(d.loc[m, p], d.loc[m, "D_ewma_shrunk"])[0, 1])
            r_log = float(np.corrcoef(d.loc[m, p], d.loc[m, "logD"])[0, 1])
            blk[p] = {"corr_with_D_rate": round(r_lin, 4), "corr_with_logD": round(r_log, 4),
                      "r2_on_logD": round(r_log ** 2, 4),
                      "variance_left_after_logD": round(1 - r_log ** 2, 4), "n": int(m.sum())}
        redundancy[trk] = blk

    # ---------------- POOLED GATE on the six-proxy matrix (combined-arm admissibility) ---- #
    train_src = I[I["exposure"] > 0].reset_index(drop=True).copy()
    off_pool = np.log(np.clip(train_src["exposure"].to_numpy(float), 1e-6, None)) + \
        train_src["logD"].to_numpy(float)
    try:
        a = gate_audit(train_src, PROXIES, offset=off_pool,
                       target=train_src["turnovers"].to_numpy(float))
        combined_ok, combined_block = True, []
    except FeatureGateFailure as e:
        a = {"passed": False, "raised": str(e)}
        combined_ok, combined_block = False, json.loads(str(e))
    a["scope"] = "pooled six-proxy matrix (combined-arm admissibility + redundancy diagnostic)"
    audits.append(a)

    ARMS: dict[str, list[str]] = {**CONTROL, **DFREE, **RATE_ARMS}
    if combined_ok:
        ARMS["ALL"] = list(PROXIES)
    print(f"combined ALL arm admissible: {combined_ok}")

    # ---------------- FIT ---------------------------------------------------------------- #
    def fit_predict(df: pd.DataFrame, track: str):
        specs = {n: {"base": c, "inter": []} for n, c in ARMS.items()}
        specs.update(INTER_ARMS)
        out = {n: np.full(len(df), np.nan) for n in specs}
        coefs: dict[int, dict] = {}
        for s in sorted(df["season"].unique()):
            tr = train_src[train_src["season"] < s]
            idx = np.where(df["season"].to_numpy() == s)[0]
            te = df.iloc[idx]
            base = te["D_ewma_shrunk"].to_numpy(float) * te["exposure"].to_numpy(float)
            if len(tr) < MIN_TRAIN_ROWS:
                for n in specs:
                    out[n][idx] = base
                coefs[int(s)] = {"fallback_to_D": True, "train_rows": int(len(tr))}
                continue
            coefs[int(s)] = {"fallback_to_D": False, "train_rows": int(len(tr))}
            otr = np.log(np.clip(tr["exposure"].to_numpy(float), 1e-6, None)) + \
                tr["logD"].to_numpy(float)
            ote = np.log(np.clip(te["exposure"].to_numpy(float), 1e-6, None)) + \
                te["logD"].to_numpy(float)
            ytr = tr["turnovers"].to_numpy(float)
            for n, sp in specs.items():
                Ztr, Zte, names = standardise(tr, te, sp["base"], sp["inter"])
                # ---- MANDATORY PREFIT GATE on the exact design matrix, fails closed ------ #
                au = gate_audit(Ztr, names, offset=otr, target=ytr, test_df=Zte)
                au["scope"] = f"prefit design matrix {n} season {int(s)} track {track}"
                audits.append(au)
                b, conv = poisson_ridge(Ztr.to_numpy(float).reshape(len(Ztr), -1), ytr, otr,
                                        RIDGE_LAMBDA)
                if not conv:
                    out[n][idx] = base
                    coefs[int(s)][n] = {"CONVERGENCE_FAILURE": True, "fell_back_to_D": True}
                    continue
                lin = ote + b[0]
                if names:
                    lin = lin + Zte.to_numpy(float) @ b[1:]
                out[n][idx] = np.exp(np.clip(lin, -20, 20))
                coefs[int(s)][n] = dict(zip(["intercept"] + names, np.round(b, 5).tolist()))
        return out, coefs

    results = {}
    for track, df in (("intrinsic", I), ("operational", O)):
        d = df.reset_index(drop=True).copy()
        preds, coefs = fit_predict(d, track)
        d["pred_A"] = d["A_league_constant"] * d["exposure"]
        d["pred_D"] = d["D_ewma_shrunk"] * d["exposure"]
        for n, v in preds.items():
            d[f"pred_{n}"] = v
        gk = [d["game_id"], d["team_id"]]
        tot = {b: d.groupby(["game_id", "team_id"])[f"pred_{b}"].transform("sum") for b in BASELINES}

        # ---- role (c1): fitted rate arm renormalised to a baseline's team total ---------- #
        # `Wfree`/`WKfree` renormalise the NO-PROXY Dfree arm the same way. They are the control
        # for "is the reallocation gain the proxy's, or just a relaxed Arm-D coefficient?"
        alloc_arms: list[str] = []
        for i in list(range(1, 7)) + ["free"]:
            src = f"pred_R{i}" if i != "free" else "pred_Dfree"
            tR = d.groupby(["game_id", "team_id"])[src].transform("sum")
            for b, tag in (("D", ""), ("K0", "K")):
                nm = f"W{tag}{i}"
                d[f"pred_{nm}"] = np.where(tR > 0, d[src] * tot[b] / tR, d[f"pred_{b}"])
                alloc_arms.append(nm)

        # ---- role (c2): pure unfitted allocation weight ---------------------------------- #
        pw_impute = {}
        for arm, (p, gmap) in PURE_W.items():
            v = d[p].to_numpy(float)
            gv = np.where(np.isfinite(v),
                          (1.0 / np.clip(v, 1e-9, None)) if gmap == "inverse_rank" else v, np.nan)
            s = pd.Series(gv, index=d.index)
            n_imp = int(s.isna().sum())
            s = s.fillna(s.groupby(gk).transform("mean"))
            w = pd.Series(d["exposure"].to_numpy(float) * s.fillna(0.0).to_numpy(float), index=d.index)
            tw = w.groupby(gk).transform("sum")
            for b, tag in (("D", ""), ("K0", "K")):
                nm = arm.replace("PW", f"PW{tag}")
                d[f"pred_{nm}"] = np.where(tw > 0, tot[b] * w / tw, d[f"pred_{b}"])
                alloc_arms.append(nm)
            pw_impute[arm] = {"rows_with_null_weight": n_imp,
                              "rule": "team-game mean of the available weights; if the whole "
                                      "team-game is null the arm equals its normalisation baseline"}

        arms_all = ["D", "A"] + list(ARMS) + list(INTER_ARMS) + alloc_arms
        g = d.groupby(["game_id", "team_id"]).agg(
            **{a: (f"pred_{a}", "sum") for a in arms_all}).reset_index()
        g = g.merge(TM[["game_id", "team_id", "player_attributed"]],
                    on=["game_id", "team_id"], how="left")
        g["y"] = g["player_attributed"].fillna(0)

        blk = {
            "rows": int(len(d)), "team_games": int(len(g)),
            "player": {a: {"deviance": _pois_dev(d["turnovers"], d[f"pred_{a}"]),
                           "mae": float(np.mean(np.abs(d["turnovers"] - d[f"pred_{a}"]))),
                           "bias": float(np.mean(d[f"pred_{a}"] - d["turnovers"]))} for a in arms_all},
            "team": {a: {"mae": float(np.mean(np.abs(g[a] - g["y"]))),
                         "rmse": float(np.sqrt(np.mean((g[a] - g["y"]) ** 2))),
                         "bias": float(np.mean(g[a] - g["y"]))} for a in arms_all},
            "by_season_team_mae": {}, "coefficients_by_season": coefs,
            "pure_weight_null_imputation": pw_impute,
        }
        CONV = "INCUMBENT abs error MINUS CHALLENGER abs error; POSITIVE = challenger beats incumbent"
        for b in BASELINES:
            tblk, pblk = {}, {}
            for a in arms_all:
                if a == b:
                    continue
                dv = np.abs(g[b] - g["y"]) - np.abs(g[a] - g["y"])
                ci = cluster_bootstrap_ci(dv.to_numpy(float), g["game_id"].to_numpy(), seed=BOOT_SEED)
                tblk[a] = {"convention": CONV, "mean_mae_reduction": float(dv.mean()),
                           "ci90": [ci["low"], ci["high"]], "improved": int((dv > 0).sum()),
                           "worsened": int((dv < 0).sum()),
                           "significant": bool(ci["low"] > 0 or ci["high"] < 0)}
                pv = np.abs(d["turnovers"] - d[f"pred_{b}"]) - np.abs(d["turnovers"] - d[f"pred_{a}"])
                pci = cluster_bootstrap_ci(pv.to_numpy(float), d["game_id"].to_numpy(), seed=BOOT_SEED)
                pblk[a] = {"convention": CONV, "mean_mae_reduction": float(pv.mean()),
                           "ci90": [pci["low"], pci["high"]],
                           "significant": bool(pci["low"] > 0 or pci["high"] < 0)}
            blk[f"paired_vs_{b}_team"], blk[f"paired_vs_{b}_player"] = tblk, pblk
        gs = g.merge(C, on="game_id", how="left")
        for s, sub in gs.groupby("season"):
            blk["by_season_team_mae"][int(s)] = {a: float(np.mean(np.abs(sub[a] - sub["y"])))
                                                 for a in arms_all}
        # per-season PLAYER-level stability. Allocation arms are team-total-pinned, so the player
        # level is the only level they can be judged at and the only level stability can be read at.
        blk["by_season_player_mae"] = {}
        blk["by_season_player_vs_K0"] = {}
        for s, sub in d.groupby("season"):
            blk["by_season_player_mae"][int(s)] = {
                a: float(np.mean(np.abs(sub["turnovers"] - sub[f"pred_{a}"]))) for a in arms_all}
            e0 = np.abs(sub["turnovers"] - sub["pred_K0"])
            blk["by_season_player_vs_K0"][int(s)] = {
                a: float(np.mean(e0 - np.abs(sub["turnovers"] - sub[f"pred_{a}"])))
                for a in arms_all}
        blk["allocation_team_total_invariance"] = {
            a: {"normalised_to": ("K0" if ("WK" in a or "PWK" in a) else "D"),
                "max_abs_team_total_deviation": float(np.max(np.abs(
                    g[a] - g["K0" if ("WK" in a or "PWK" in a) else "D"])))}
            for a in alloc_arms}
        results[track] = blk
        d.to_parquet(HERE / f"ws5_predictions_{track}.parquet", index=False)

    (HERE / "WS5_FEATURE_GATE.json").write_text(json.dumps({
        "schema": "ws5_feature_gate/1",
        "mandatory": ("feature_gate.audit ran on the exact standardised design matrix of every "
                      "(arm, season, track) fold BEFORE that fold was fitted, and fails closed"),
        "n_audits": len(audits), "all_passed": all(x.get("passed") for x in audits),
        "blocking_any": [x for x in audits if not x.get("passed")],
        "target_derived_check": ("every audit carried target=turnovers. Turnovers enter proxies "
                                 "x2..x6 through STRICTLY PRIOR games only; the independent "
                                 "recomputation probe in WS5_FEATURE_VALIDATION.json re-derives "
                                 "sampled rows from a plain `game_date < target_date` filter."),
        "audits": audits}, indent=2, default=str), encoding="utf-8")

    out = {
        "schema": "ws5_results/2", "workstream": "ws5_opportunity_proxies", "wave": "discovery_wave_1",
        "executed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "DISCOVERY, historical development evidence only; nothing here is promotable",
        "sign_convention": "INCUMBENT minus CHALLENGER absolute error; POSITIVE = challenger better",
        "baselines": {"D": "frozen P1 EWMA-shrunk incumbent, UNFITTED (no intercept)",
                      "K0": ("recalibration-only control: zero features, unpenalised intercept, "
                             "identical pipeline/folds/offset. Coordinator amendment. Any arm that "
                             "beats D but not K0 is redundant with free recalibration.")},
        "hyperparameters": {"ridge_lambda": RIDGE_LAMBDA, "min_train_rows": MIN_TRAIN_ROWS,
                            "boot_seed": BOOT_SEED, "preregistered": True, "no_search": True},
        "arm_naming": {"R_k": "role (a) rate predictor", "X_k": "role (b) interaction with logD",
                       "W_k / WK_k": "role (c) fitted allocation, renormalised to the D / K0 team total",
                       "PW_k / PWK_k": "role (c) pure unfitted allocation weight, D / K0 team total",
                       "Dfree": "free Arm-D coefficient, nested reference",
                       "note": "the frozen spec labels the pure-weight arms P1..P6; PW_k avoids "
                               "collision with the P1 program phase. No semantic change."},
        "combined_arm_admissible": combined_ok, "combined_arm_block": combined_block,
        "redundancy_vs_P1_EWMA": redundancy,
        "shared_input_defect": defect,
        "p2_arm_G_reconciliation": {
            "what": ("P2 arm G used the canonical involvement proxy, whose null pattern IS an exact "
                     "did_appear indicator on the operational track; P2 mean-imputed those nulls in "
                     "the fold, so arm G's operational feature encoded appearance. ws5 R1 is the "
                     "same formula with genuine strictly-prior values on all 35,629 candidates."),
            "p2_arm_G_operational": {"deviance": 1.22717, "player_mae": 0.8454, "team_mae": 2.9725,
                                     "team_vs_D": -0.0051},
            "ws5_R1_operational": "see results.operational for the clean re-measurement",
            "note": "training rows are identical between the two (both train on the intrinsic "
                    "appearer frame), so the difference isolates the operational test-row defect"},
        "artifact_sha256": {"features": _sha(HERE / "ws5_opportunity_proxy_features_v1.parquet")},
        "results": results,
    }
    (HERE / "WS5_RESULTS.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    for track in ("intrinsic", "operational"):
        r = results[track]
        print(f"\n=== {track} === rows {r['rows']:,} team-games {r['team_games']:,}")
        hdr = f"{'arm':7s} {'dev':>9s} {'plMAE':>7s} {'tmMAE':>7s} " \
              f"{'tm vs D':>9s} {'tm vs K0':>9s} {'K0ci90':>21s} {'pl vs K0':>9s}"
        print(hdr)
        for a in ["D", "A"] + list(ARMS) + list(INTER_ARMS) + \
                [x for x in r["team"] if x.startswith(("W", "PW"))]:
            if a not in r["team"]:
                continue
            td = r["paired_vs_D_team"].get(a); tk = r["paired_vs_K0_team"].get(a)
            pk = r["paired_vs_K0_player"].get(a)
            fmt = lambda z: f"{z['mean_mae_reduction']:+.4f}" if z else ""      # noqa: E731
            ci = f"[{tk['ci90'][0]:+.4f},{tk['ci90'][1]:+.4f}]" if tk else ""
            print(f"{a:7s} {r['player'][a]['deviance']:9.5f} {r['player'][a]['mae']:7.4f} "
                  f"{r['team'][a]['mae']:7.4f} {fmt(td):>9s} {fmt(tk):>9s} {ci:>21s} "
                  f"{fmt(pk):>9s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
