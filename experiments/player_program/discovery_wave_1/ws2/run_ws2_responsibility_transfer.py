#!/usr/bin/env python3
"""run_ws2_responsibility_transfer.py -- discovery wave 1, ws2_responsibility_transfer.

Tests whether turnovers rise specifically for players positioned to ABSORB missing teammates'
offensive responsibility, using three constructions frozen in FROZEN_CONSTRUCTIONS.json BEFORE
this fit was run.

The prior arm H applied the SAME team-level displaced_involvement to every player on the roster
(verified constant within team-game) and was null. That is a team-level intercept shift, not the
responsibility-transfer mechanism.

DISCOVERY LANE. Development evidence only. Does not modify Arm D or any canonical artifact and
does not append to arm_registry.jsonl.
"""
from __future__ import annotations
import hashlib, json, sys                                                       # noqa: E401
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent            # .../discovery_wave_1/ws2
PP = HERE.parents[1]                              # .../experiments/player_program
ROOT = PP.parents[1]                              # repo root
sys.path.insert(0, str(PP)); sys.path.insert(0, str(ROOT))

from evalharness.compare import cluster_bootstrap_ci                            # noqa: E402
import feature_gate                                                             # noqa: E402
from register_turnover_p2 import RIDGE_LAMBDA, MIN_TRAIN_ROWS                   # noqa: E402
from run_turnover_p2 import poisson_ridge, _pois_dev                            # noqa: E402

OUT = HERE
TGT = PP / "turnover_targets_v1"

# ---- FROZEN ARMS (see FROZEN_CONSTRUCTIONS.json) --------------------------------------- #
ARMS = {
    "H":    ["displaced_involvement"],
    "T1":   ["transfer_direct"],
    "T2":   ["transfer_allocated"],
    "T3":   ["transfer_role_sensitive"],
    "T123": ["transfer_direct", "transfer_allocated", "transfer_role_sensitive"],
    "HT2":  ["displaced_involvement", "transfer_allocated"],
    "HT3":  ["displaced_involvement", "transfer_role_sensitive"],
}
DERIVED = ["transfer_direct", "transfer_allocated", "transfer_role_sensitive"]
ALLFEAT = ["displaced_involvement"] + DERIVED


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_constructions(F: pd.DataFrame) -> pd.DataFrame:
    """The three frozen constructions. Formulas are fixed in FROZEN_CONSTRUCTIONS.json."""
    F = F.copy()
    # nulls imputed on the RAW inputs so the zero keeps its mechanistic meaning
    F["prior_involvement"] = F["offensive_involvement_proxy"].fillna(0.0)
    F["team_prior_involvement_sum"] = (
        F.groupby(["game_id", "team_id"])["prior_involvement"].transform("sum"))
    F["role_expansion"] = (
        (F["proj_minutes_share"] - F["trailing_minutes_share"]).fillna(0.0).clip(lower=0.0))

    D = F["displaced_involvement"].to_numpy(float)
    pi = F["prior_involvement"].to_numpy(float)
    S = F["team_prior_involvement_sum"].to_numpy(float)

    # C1 direct interaction
    F["transfer_direct"] = D * pi
    # C2 allocated displaced load (proportional to prior creation share)
    share = np.divide(pi, S, out=np.zeros_like(pi), where=S > 0)
    F["transfer_allocated"] = D * share
    # C3 role-sensitive transfer
    F["transfer_role_sensitive"] = F["transfer_allocated"].to_numpy(float) * \
        F["role_expansion"].to_numpy(float)
    return F


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    gate_log: list[dict] = []

    # ---------- INPUTS (read-only) ------------------------------------------------------ #
    FEATP = PP / "turnover_p2_v1/turnover_role_context_features_v1.parquet"
    P1OP = PP / "turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet"
    P1IP = PP / "turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet"
    PXP = PP / "projected_exposure_v1/projected_player_possessions_v1.parquet"

    F = pd.read_parquet(FEATP)
    P1O = pd.read_parquet(P1OP)
    P1I = pd.read_parquet(P1IP)
    if "exposure" not in P1I.columns:
        P1I = P1I.rename(columns={"realised_off_possessions": "exposure"})
    TM = pd.read_parquet(TGT / "team_turnover_reconciliation_v1.parquet")
    C = pd.read_parquet(ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet",
                        columns=["game_id", "game_date", "season", "forecast_cutoff"]
                        ).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)

    # tier_a_only universe assertion -- no Tier B, no S2
    PX = pd.read_parquet(PXP, columns=["game_id", "team_id", "player_id", "regime"])
    PXA = PX[PX["regime"] == "tier_a_only"]
    key = ["game_id", "team_id", "player_id"]
    universe = {
        "tier_a_only_rows": int(len(PXA)),
        "regimes_present_in_source": sorted(PX["regime"].unique().tolist()),
        "regime_used": "tier_a_only",
        "feature_rows": int(len(F)),
        "operational_rows": int(len(P1O)),
        "feature_universe_equals_tier_a": bool(
            len(F) == len(PXA) and len(F.merge(PXA[key], on=key, how="inner")) == len(F)),
        "operational_universe_equals_tier_a": bool(
            len(P1O) == len(PXA) and len(P1O.merge(PXA[key], on=key, how="inner")) == len(P1O)),
    }
    if not (universe["feature_universe_equals_tier_a"]
            and universe["operational_universe_equals_tier_a"]):
        raise RuntimeError(f"universe is not exactly tier_a_only: {universe}")

    # ---------- FROZEN CONSTRUCTIONS ---------------------------------------------------- #
    F = build_constructions(F)
    F.to_parquet(OUT / "ws2_transfer_features_v1.parquet", index=False)

    cov = {c: {"non_null": int(F[c].notna().sum()), "null": int(F[c].isna().sum()),
               "zero_frac": float((F[c] == 0).mean()), "mean": float(F[c].mean()),
               "std": float(F[c].std()), "min": float(F[c].min()), "max": float(F[c].max())}
           for c in ALLFEAT + ["prior_involvement", "role_expansion",
                               "team_prior_involvement_sum"]}
    corr = F[ALLFEAT].corr().round(4).to_dict()

    # allocation identity: T2 must sum back to D within each team-game
    chk = F.groupby(["game_id", "team_id"]).agg(
        t2=("transfer_allocated", "sum"), d=("displaced_involvement", "first")).reset_index()
    alloc_identity = {
        "claim": "sum_i transfer_allocated_i == displaced_involvement within each team-game",
        "max_abs_deviation": float(np.max(np.abs(chk["t2"] - chk["d"]))),
        "holds": bool(np.allclose(chk["t2"], chk["d"], atol=1e-9)),
        "team_games": int(len(chk))}
    displaced_constant = {
        "claim": "displaced_involvement is constant within a team-game, so arm H assigns every "
                 "candidate the identical value",
        "holds": bool((F.groupby(["game_id", "team_id"])["displaced_involvement"].nunique() == 1).all()),
        "distinct_values_per_team_game_max": int(
            F.groupby(["game_id", "team_id"])["displaced_involvement"].nunique().max())}

    # ---------- ASSEMBLE TRACKS --------------------------------------------------------- #
    O = P1O.merge(F[key + ALLFEAT], on=key, how="left")
    I = P1I.merge(F[key + ALLFEAT], on=key, how="left")
    I = I.merge(C[["game_id", "season"]].rename(columns={"season": "_s"}), on="game_id", how="left")
    I["season"] = I["_s"]; I = I.drop(columns="_s")
    TM = TM.merge(C[["game_id", "game_date"]], on="game_id", how="left")

    def fit_predict(df: pd.DataFrame, train_src: pd.DataFrame, track: str):
        """Walk-forward by season. beta=0 (exactly Arm D) when training support is short."""
        out = {a: np.full(len(df), np.nan) for a in ARMS}
        coefs: dict = {}
        for s in sorted(df["season"].unique()):
            tr = train_src[train_src["season"] < s]
            te_idx = np.where(df["season"].to_numpy() == s)[0]
            te = df.iloc[te_idx]
            base = te["D_ewma_shrunk"].to_numpy(float) * te["exposure"].to_numpy(float)
            if len(tr) < MIN_TRAIN_ROWS:
                for a in ARMS:
                    out[a][te_idx] = base
                coefs[int(s)] = {"fallback_to_D": True, "train_rows": int(len(tr))}
                continue
            coefs[int(s)] = {"fallback_to_D": False, "train_rows": int(len(tr))}

            otr = np.log(np.clip(tr["exposure"].to_numpy(float), 1e-6, None)) + \
                np.log(np.clip(tr["D_ewma_shrunk"].to_numpy(float), 1e-9, None))
            ote = np.log(np.clip(te["exposure"].to_numpy(float), 1e-6, None)) + \
                np.log(np.clip(te["D_ewma_shrunk"].to_numpy(float), 1e-9, None))
            ytr = tr["turnovers"].to_numpy(float)

            for a, feats in ARMS.items():
                mu_tr, sd_tr = tr[feats].mean(), tr[feats].std().replace(0, 1.0)
                Xtr = ((tr[feats] - mu_tr) / sd_tr).fillna(0.0)
                Xte = ((te[feats] - mu_tr) / sd_tr).fillna(0.0)

                # ---- MANDATORY PREFIT GATE on the exact design matrix that enters the fit
                g = feature_gate.audit(Xtr, feats, offset=otr, target=ytr, test_df=Xte)
                gate_log.append({"track": track, "season": int(s), "arm": a,
                                 "features": feats, "n_rows": g["n_rows"],
                                 "findings": g["findings"], "blocking": g["blocking"],
                                 "passed": g["passed"]})

                b, conv = poisson_ridge(Xtr.to_numpy(float), ytr, otr, RIDGE_LAMBDA)
                if not conv:
                    out[a][te_idx] = base
                    coefs[int(s)][a] = {"CONVERGENCE_FAILURE": True, "fell_back_to_D": True}
                    continue
                out[a][te_idx] = np.exp(np.clip(ote + b[0] + Xte.to_numpy(float) @ b[1:], -20, 20))
                coefs[int(s)][a] = dict(zip(["intercept"] + feats, np.round(b, 6).tolist()))
        return out, coefs

    train_src = I[I["exposure"] > 0].copy()
    res: dict = {}
    for name, df in (("intrinsic", I), ("operational", O)):
        preds, coefs = fit_predict(df.reset_index(drop=True), train_src, name)
        d = df.reset_index(drop=True).copy()
        d["pred_D"] = d["D_ewma_shrunk"] * d["exposure"]
        for a in ARMS:
            d[f"pred_{a}"] = preds[a]
        allarms = ["D"] + list(ARMS)

        g = d.groupby(["game_id", "team_id"]).agg(
            **{a: (f"pred_{a}", "sum") for a in allarms}).reset_index()
        g = g.merge(TM[["game_id", "team_id", "player_attributed", "team_unattributed",
                        "team_off_possessions"]], on=["game_id", "team_id"], how="left")
        g["y"] = g["player_attributed"].fillna(0)

        blk = {
            "rows": int(len(d)), "team_games": int(len(g)),
            "player": {a: {"deviance": _pois_dev(d["turnovers"], d[f"pred_{a}"]),
                           "mae": float(np.mean(np.abs(d["turnovers"] - d[f"pred_{a}"]))),
                           "bias": float(np.mean(d[f"pred_{a}"] - d["turnovers"]))}
                       for a in allarms},
            "team": {a: {"mae": float(np.mean(np.abs(g[a] - g["y"]))),
                         "rmse": float(np.sqrt(np.mean((g[a] - g["y"]) ** 2))),
                         "bias": float(np.mean(g[a] - g["y"]))} for a in allarms},
            "paired_vs_D": {}, "paired_vs_H": {}, "by_season_team_mae": {},
            "coefficients_by_season": coefs}

        CONV = ("INCUMBENT abs error MINUS CHALLENGER abs error; POSITIVE = challenger beats "
                "the incumbent")
        for ref in ("D", "H"):
            slot = blk[f"paired_vs_{ref}"]
            for a in allarms:
                if a == ref:
                    continue
                dv = (np.abs(g[ref] - g["y"]) - np.abs(g[a] - g["y"])).to_numpy(float)
                ci = cluster_bootstrap_ci(dv, g["game_id"].to_numpy())
                slot[a] = {"convention": CONV, "incumbent": ref,
                           "mean_mae_reduction": float(dv.mean()),
                           "ci90": [ci["low"], ci["high"]],
                           "ci_excludes_zero": bool(ci["low"] > 0 or ci["high"] < 0),
                           "improved": int((dv > 0).sum()), "worsened": int((dv < 0).sum()),
                           "n_clusters": int(ci["n_clusters"])}

        gs = g.merge(C[["game_id", "season"]], on="game_id", how="left")
        for s, sub in gs.groupby("season"):
            blk["by_season_team_mae"][int(s)] = {a: float(np.mean(np.abs(sub[a] - sub["y"])))
                                                 for a in allarms}
        if "did_appear" in d:
            for lab, sub in (("appearing", d[d["did_appear"]]),
                             ("non_appearing", d[~d["did_appear"]])):
                blk[f"player_{lab}"] = {
                    a: {"n": int(len(sub)),
                        "mae": float(np.mean(np.abs(sub["turnovers"] - sub[f"pred_{a}"])))}
                    for a in allarms}
        res[name] = blk
        d.to_parquet(OUT / f"ws2_predictions_{name}.parquet", index=False)

    # ---------- GATE SUMMARY ------------------------------------------------------------ #
    gate_summary = {
        "schema": "ws2_feature_gate_log/1",
        "gate_module": "experiments/player_program/feature_gate.py",
        "requirement": "audit() called on the standardised training design matrix of every "
                       "(track, season, arm) before its fit",
        "audits_run": len(gate_log),
        "all_passed": bool(all(a["passed"] for a in gate_log)),
        "total_blocking_findings": int(sum(len(a["blocking"]) for a in gate_log)),
        "non_blocking_findings": [a for a in gate_log if a["findings"]],
        "adjudications_used": "NONE -- no finding was adjudicated away",
        "audits": gate_log}
    (OUT / "FEATURE_GATE_LOG.json").write_text(
        json.dumps(gate_summary, indent=2, default=str), encoding="utf-8")

    out = {
        "schema": "discovery_ws2_results/1",
        "workstream": "ws2_responsibility_transfer",
        "wave": "discovery_wave_1",
        "lane": "DISCOVERY -- historical development evidence only; no promotion, no registry write",
        "executed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "frozen_spec": "FROZEN_CONSTRUCTIONS.json",
        "sign_convention": "INCUMBENT minus CHALLENGER absolute error; POSITIVE = challenger better",
        "hyperparameters": {"ridge_lambda": RIDGE_LAMBDA, "min_train_rows": MIN_TRAIN_ROWS,
                            "offset": "log(exposure) + log(D_ewma_shrunk)",
                            "preregistered": True},
        "arms": ARMS,
        "universe": universe,
        "track_semantics": {
            "intrinsic": "ORACLE DIAGNOSTIC -- realised exposure, conditions on appearance",
            "operational": "decision-relevant -- projected exposure over all tier_a candidates "
                           "including non-appearers"},
        "feature_coverage": cov, "feature_correlations": corr,
        "allocation_identity_check": alloc_identity,
        "arm_H_degeneracy_check": displaced_constant,
        "gate_summary": {k: v for k, v in gate_summary.items() if k != "audits"},
        "input_sha256": {"features_p2": _sha(FEATP), "p1_operational": _sha(P1OP),
                         "p1_intrinsic": _sha(P1IP)},
        "artifact_sha256": {"ws2_features": _sha(OUT / "ws2_transfer_features_v1.parquet")},
        "results": res}
    (OUT / "WS2_RESULTS.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    # ---------- CONSOLE ----------------------------------------------------------------- #
    print(f"\ngate: {gate_summary['audits_run']} audits, all_passed="
          f"{gate_summary['all_passed']}, blocking={gate_summary['total_blocking_findings']}")
    print(f"allocation identity holds: {alloc_identity['holds']} "
          f"(max dev {alloc_identity['max_abs_deviation']:.2e})")
    for name in ("intrinsic", "operational"):
        r = res[name]
        print(f"\n=== {name} === rows {r['rows']:,} team-games {r['team_games']:,}")
        print(f"{'arm':5s} {'plDev':>9s} {'plMAE':>8s} {'teamMAE':>8s} "
              f"{'vsD':>9s} {'ci90(D)':>20s} {'vsH':>9s} {'ci90(H)':>20s}")
        for a in ["D"] + list(ARMS):
            pD = r["paired_vs_D"].get(a); pH = r["paired_vs_H"].get(a)
            f1 = f"{pD['mean_mae_reduction']:+.4f}" if pD else ""
            c1 = f"[{pD['ci90'][0]:+.4f},{pD['ci90'][1]:+.4f}]" if pD else ""
            f2 = f"{pH['mean_mae_reduction']:+.4f}" if pH else ""
            c2 = f"[{pH['ci90'][0]:+.4f},{pH['ci90'][1]:+.4f}]" if pH else ""
            print(f"{a:5s} {r['player'][a]['deviance']:9.5f} {r['player'][a]['mae']:8.4f} "
                  f"{r['team'][a]['mae']:8.4f} {f1:>9s} {c1:>20s} {f2:>9s} {c2:>20s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
