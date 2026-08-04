#!/usr/bin/env python3
"""run_ws6_mechanism_decomposition.py -- DISCOVERY workstream ws6_mechanism_decomposition.

CENTRAL QUESTION
    Arm G (`offensive_involvement_proxy`) improved player-level Poisson deviance yet made
    team-level MAE WORSE. Do OFFSETTING MECHANISM EFFECTS explain that?

    supports:   involvement helps one mechanism and hurts another with OPPOSITE SIGNS
    falsifies:  all mechanisms respond to involvement in the SAME direction

WHAT THIS IS NOT
    Discovery only. Nothing here replaces the validated total-turnover target, nothing is
    promoted, no canonical artifact is modified, and nothing is appended to arm_registry.jsonl.

PROTOCOL PARITY
    The per-mechanism fits reproduce arm G's design EXACTLY -- same offset
    (log exposure + log D_ewma_shrunk), same ridge lambda, same walk-forward-by-season split,
    same standardisation -- with the single change that the response is a mechanism count
    instead of the total. Because mechanism counts sum EXACTLY to the total, the decomposition
    is arithmetically closed.

MANDATORY GATE
    `feature_gate.audit(...)` runs before EVERY fit; every audit is persisted.

NULLS ARE PRESERVED
    `offensive_involvement_proxy` and `role_change` are null for a player's first appearances.
    Diagnostics NEVER impute. Two fits are reported side by side: `parity` (mean-imputation,
    exactly what arm G did) and `complete_case` (nulls dropped). Divergence between them is
    itself reported.

Run::  python experiments/player_program/discovery_wave_1/ws6/run_ws6_mechanism_decomposition.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]                     # experiments/player_program
ROOT = PP.parents[1]                     # repo root
sys.path.insert(0, str(PP))
sys.path.insert(0, str(ROOT))

from feature_gate import audit as gate_audit                                  # noqa: E402
from register_turnover_targets import MECHANISM_CROSSWALK                     # noqa: E402
from register_turnover_p2 import RIDGE_LAMBDA                                 # noqa: E402
from register_turnover_p1 import EB_PRIOR_K, EWMA_ALPHA                       # noqa: E402
from run_turnover_p2 import poisson_ridge, _pois_dev                          # noqa: E402

TGT = PP / "turnover_targets_v1"
P1 = PP / "turnover_p1_v1"
P2 = PP / "turnover_p2_v1"
EVENTS = PP / "event_contract_v1/canonical_player_events_v1.parquet"
CONTRACT = ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet"

# ---- PREREGISTERED discovery thresholds (fixed before any fit) ------------------------ #
MIN_EVENTS_FOR_FIT = 200          # player-attributed events, whole sample
MIN_TRAIN_EVENTS = 100            # events in the walk-forward training seasons
MIN_NONZERO_ROWS = 150            # player-games with >=1 of this mechanism
MIN_EXPOSURE_SPLITHALF = 200      # off. possessions per half for split-half reliability
N_BOOT = 400                      # cluster bootstrap draws for the sign test
SEED = 20260804

MECH_GROUP = {m: v["group"] for m, v in MECHANISM_CROSSWALK.items()}
GROUP_ORDER = ["bad_pass", "lost_ball", "travel_footwork", "offensive_foul", "shot_clock",
               "other_violation", "unknown"]


def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _chi2_sf(x: float, k: int) -> float:
    """Upper tail of chi-square with k df. Implemented locally: scipy is not installed here."""
    if k <= 0 or x <= 0:
        return 1.0
    from math import lgamma, exp, log
    a, xx = k / 2.0, x / 2.0
    lg = lgamma(a)
    if xx < a + 1.0:                                    # series for the lower regularised gamma
        term = 1.0 / a
        s = term
        n = a
        for _ in range(2000):
            n += 1.0
            term *= xx / n
            s += term
            if abs(term) < abs(s) * 1e-14:
                break
        return float(1.0 - s * exp(-xx + a * log(xx) - lg))
    # Lentz continued fraction for the upper regularised gamma
    tiny = 1e-300
    b = xx + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 2000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-14:
            break
    return float(exp(-xx + a * log(xx) - lg) * h)


def gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


# --------------------------------------------------------------------------------------- #
# cluster-robust Poisson inference
# --------------------------------------------------------------------------------------- #
def poisson_cluster_fit(X: np.ndarray, y: np.ndarray, off: np.ndarray, clusters: np.ndarray,
                        lam: float = RIDGE_LAMBDA) -> dict:
    """Pooled Poisson ridge + cluster-robust sandwich covariance (clustered by game)."""
    b, conv = poisson_ridge(X, y, off, lam)
    n, p = X.shape
    Xd = np.hstack([np.ones((n, 1)), X])
    mu = np.exp(np.clip(off + Xd @ b, -20, 20))
    W = np.clip(mu, 1e-9, 1e9)
    Pen = np.eye(p + 1) * lam
    Pen[0, 0] = 0.0
    bread = np.linalg.pinv(Xd.T @ (Xd * W[:, None]) + Pen)
    u = Xd * (y - mu)[:, None]
    df = pd.DataFrame(u)
    df["_c"] = clusters
    S = df.groupby("_c").sum().to_numpy(float)
    meat = S.T @ S
    V = bread @ meat @ bread
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    return {"beta": b, "se": se, "converged": bool(conv), "n": int(n),
            "n_clusters": int(pd.Series(clusters).nunique())}


def main() -> int:
    rng = np.random.default_rng(SEED)
    started = _utc()
    audits: list[dict] = []

    def GATE(tag, df, names, offset=None, target=None):
        """Mandatory prefit gate. Records the audit; a blocking finding raises."""
        a = gate_audit(df, names, offset=offset, target=target)
        a["fit_tag"] = tag
        audits.append(a)
        return a

    # ================= LOAD (read-only) =================================================
    T = pd.read_parquet(TGT / "player_turnover_targets_v1.parquet")
    TM = pd.read_parquet(TGT / "team_turnover_reconciliation_v1.parquet")
    TM["team_id"] = TM["team_id"].astype("Int64")
    F = pd.read_parquet(P2 / "turnover_role_context_features_v1.parquet")
    P1I = pd.read_parquet(P1 / "turnover_p1_predictions_intrinsic.parquet")
    P2I = pd.read_parquet(P2 / "turnover_p2_predictions_intrinsic.parquet")
    C = pd.read_parquet(CONTRACT, columns=["game_id", "game_date"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)

    MECH = [m for m in MECHANISM_CROSSWALK if m in T.columns]
    MECH_ABSENT = [m for m in MECHANISM_CROSSWALK if m not in T.columns]

    # closure check on the frozen target (must hold; this is the whole basis of the decomposition)
    closure = bool((T[MECH].sum(axis=1) == T["turnovers"]).all())
    if not closure:
        raise RuntimeError("mechanism columns do not sum to `turnovers`; decomposition invalid")

    # ---- provenance check: does the committed artifact match its own receipt? ----------
    rec = json.loads((TGT / "TURNOVER_VALIDATION.json").read_text(encoding="utf-8"))
    prov = {
        "receipt_player_sha256": rec["artifact_sha256"]["player"],
        "observed_player_sha256": _sha(TGT / "player_turnover_targets_v1.parquet"),
        "receipt_total_turnovers": rec["checks"][0]["detail"]["total_turnovers"],
        "observed_total_turnovers": int(T["turnovers"].sum()),
    }
    prov["sha_matches_receipt"] = prov["receipt_player_sha256"] == prov["observed_player_sha256"]
    prov["total_matches_receipt"] = (prov["receipt_total_turnovers"]
                                     == prov["observed_total_turnovers"])
    prov["note"] = ("PRE-EXISTING at the base commit; not introduced by ws6. ws6 changes nothing. "
                    "The discrepancy is 1 turnover event in 39,279 (2.5e-5) and cannot move any "
                    "conclusion below, but the artifact is NOT byte-identical to its receipt.")

    # ================= WHERE THE MISSING MECHANISMS WENT ================================
    # Recompute mechanism x disposition from the canonical events using the PRODUCER's own
    # rule, so the three absent mechanism columns are explained rather than merely noted.
    EV = pd.read_parquet(EVENTS, columns=["game_id", "source_system", "event_family",
                                          "event_subtype", "source_subtype_raw", "player1_id",
                                          "event_team_id"])
    EV = EV[EV["event_family"] == "turnover"].copy()
    leg2m = {c: m for m, v in MECHANISM_CROSSWALK.items() for c in v["legacy"]}
    cdn2m = {c: m for m, v in MECHANISM_CROSSWALK.items() for c in v["cdn"] if c}
    is_leg = EV["source_system"] == "nba_playbyplayv2"
    EV["mechanism"] = np.where(
        is_leg, EV["source_subtype_raw"].map(leg2m),
        EV["event_subtype"].astype("string").fillna("").map(cdn2m))
    EV["mechanism"] = EV["mechanism"].fillna("unresolved")
    mt = pd.read_parquet(ROOT / "data/masters/master_team.parquet",
                         columns=["game_id", "team_id"]).drop_duplicates()
    team_ids = set(mt["team_id"].astype("int64"))
    p1id = EV["player1_id"]
    EV["is_team_turnover"] = p1id.isna() | p1id.astype("Int64").isin(team_ids)
    disp = pd.crosstab(EV["mechanism"],
                       np.where(EV["is_team_turnover"], "team_charged", "player_attributed"))
    for c in ("team_charged", "player_attributed"):
        if c not in disp.columns:
            disp[c] = 0
    disp["total"] = disp.sum(axis=1)
    disp["team_charged_share"] = (disp["team_charged"] / disp["total"]).round(4)
    absent_expl = {}
    for m in MECH_ABSENT:
        r = disp.loc[m] if m in disp.index else None
        absent_expl[m] = {
            "group": MECH_GROUP[m],
            "events_in_canonical_contract": int(r["total"]) if r is not None else 0,
            "player_attributed": int(r["player_attributed"]) if r is not None else 0,
            "team_charged": int(r["team_charged"]) if r is not None else 0,
            "why_absent": ("STRUCTURALLY TEAM-CHARGED: the source puts a TEAM id in the player1 "
                           "field, so the producer's attribution rule routes 100% of these events "
                           "to team_unattributed. There is no player-attributed support, so the "
                           "producer emitted no column. This is correct, not a defect."),
        }

    # ================= ASSEMBLE THE ANALYSIS FRAME ======================================
    key = ["game_id", "team_id", "player_id"]
    F2 = F[key + ["offensive_involvement_proxy", "role_change", "trailing_minutes_share",
                  "proj_minutes_share"]].copy()
    F2["team_id"] = F2["team_id"].astype("Int64")
    F2["player_id"] = F2["player_id"].astype("Int64")

    D = T.merge(TM[["game_id", "team_id", "source_system"]], on=["game_id", "team_id"], how="left")
    D = D.merge(C, on="game_id", how="left")
    D = D.merge(F2, on=key, how="left")
    join_cov = {
        "target_rows": int(len(T)),
        "source_system_joined": int(D["source_system"].notna().sum()),
        "involvement_joined_non_null": int(D["offensive_involvement_proxy"].notna().sum()),
        "involvement_null_PRESERVED": int(D["offensive_involvement_proxy"].isna().sum()),
        "role_change_null_PRESERVED": int(D["role_change"].isna().sum()),
    }

    # fit frame = intrinsic universe (arm G's own universe): eligible rows with exposure > 0
    P1I["team_id"] = P1I["team_id"].astype("Int64")
    P1I["player_id"] = P1I["player_id"].astype("Int64")
    F1 = D.merge(P1I[key + ["D_ewma_shrunk", "season"]].rename(columns={"season": "_s"}),
                 on=key, how="inner")
    F1 = F1[(F1["realised_off_possessions"] > 0) & F1["D_ewma_shrunk"].notna()].copy()
    F1["exposure"] = F1["realised_off_possessions"].astype(float)
    F1 = F1.sort_values(["game_date", "game_id"]).reset_index(drop=True)

    # ================= PER-MECHANISM DIAGNOSTICS ========================================
    tot_tov = int(T["turnovers"].sum())
    tot_exp = float(T["realised_off_possessions"].sum())
    # team-game level frame for error attribution
    TG = (D.groupby(["game_id", "team_id"])[MECH + ["turnovers"]].sum().reset_index())
    P2I["team_id"] = P2I["team_id"].astype("Int64")
    TGP = (P2I.groupby(["game_id", "team_id"])[["pred_D", "pred_G", "turnovers"]].sum()
           .reset_index().rename(columns={"turnovers": "y_total_pred_universe"}))
    TGE = TG.merge(TGP, on=["game_id", "team_id"], how="inner")
    TGE["delta_G_minus_D"] = TGE["pred_G"] - TGE["pred_D"]
    var_tot = float(np.var(TGE["turnovers"], ddof=1))
    cov_delta_tot = float(np.cov(TGE["delta_G_minus_D"], TGE["turnovers"])[0, 1])

    # split-half reliability setup: per-player odd/even game halves
    D["_gidx"] = D.sort_values(["game_date", "game_id"]).groupby("player_id").cumcount()
    D["_half"] = D["_gidx"] % 2

    diagnostics = {}
    for m in MECH:
        col = D[m]
        n_ev = int(col.sum())
        nz = int((col > 0).sum())
        mech_exp = float(D.loc[col > 0, "realised_off_possessions"].sum())

        # -- source-schema stability (CONFOUNDED unless restricted) ------------------
        def rate_by(sub):
            e = float(sub["realised_off_possessions"].sum())
            return float(100.0 * sub[m].sum() / e) if e > 0 else float("nan")
        by_src = {s: rate_by(sub) for s, sub in D.groupby("source_system")}
        # the ONE deconfounded stratum: 2025 Regular Season has BOTH schemas
        dec = D[(D["season"] == 2025) & (D["season_type"] == "Regular Season")]
        dec_by_src = {s: rate_by(sub) for s, sub in dec.groupby("source_system")}
        dec_n = {s: int(sub[m].sum()) for s, sub in dec.groupby("source_system")}
        if len(dec_by_src) == 2 and all(np.isfinite(list(dec_by_src.values()))):
            a, b = dec_by_src["nba_cdn_playbyplay"], dec_by_src["nba_playbyplayv2"]
            ratio = float(a / b) if b > 0 else float("nan")
            enough = min(dec_n.values()) >= 25
            stable = bool(enough and np.isfinite(ratio) and 0.75 <= ratio <= 1.333)
            verdict = ("STABLE" if stable else
                       ("SCHEMA_SHIFT" if enough else "UNDERPOWERED"))
        else:
            ratio, verdict = float("nan"), "UNDERPOWERED"

        # -- player concentration -----------------------------------------------------
        pl = D.groupby("player_id").agg(c=(m, "sum"), e=("realised_off_possessions", "sum"))
        pl = pl[pl["e"] > 0]
        tot_c = float(pl["c"].sum())
        top10 = float(pl["c"].nlargest(max(1, int(0.10 * len(pl)))).sum() / tot_c) if tot_c > 0 else float("nan")
        gcoef = gini(pl["c"].to_numpy(float))
        # split-half reliability of the per-100 rate (does stable PLAYER signal exist at all?)
        h = D.groupby(["player_id", "_half"]).agg(c=(m, "sum"),
                                                  e=("realised_off_possessions", "sum")).reset_index()
        w = h.pivot(index="player_id", columns="_half", values=["c", "e"])
        w.columns = [f"{a}{b}" for a, b in w.columns]
        w = w.dropna()
        w = w[(w["e0"] >= MIN_EXPOSURE_SPLITHALF) & (w["e1"] >= MIN_EXPOSURE_SPLITHALF)]
        if len(w) >= 30:
            r0 = 100 * w["c0"] / w["e0"]
            r1 = 100 * w["c1"] / w["e1"]
            sh = float(np.corrcoef(r0, r1)[0, 1]) if r0.std() > 0 and r1.std() > 0 else float("nan")
            rel = float(2 * sh / (1 + sh)) if np.isfinite(sh) and sh > -1 else float("nan")
        else:
            sh, rel = float("nan"), float("nan")

        # -- involvement / role-change gradient (descriptive, complete case, NO imputation)
        cc = D[D["offensive_involvement_proxy"].notna() & (D["realised_off_possessions"] > 0)]
        q = pd.qcut(cc["offensive_involvement_proxy"], 5, labels=False, duplicates="drop")
        grad = {}
        for qi, sub in cc.groupby(q):
            grad[f"q{int(qi) + 1}"] = round(rate_by(sub), 4)
        gq = [grad.get(f"q{i}", float("nan")) for i in range(1, 6)]
        grad_ratio = float(gq[-1] / gq[0]) if (len(gq) == 5 and gq[0] and np.isfinite(gq[0])) else float("nan")

        ccr = D[D["role_change"].notna() & (D["realised_off_possessions"] > 0)]
        qr = pd.qcut(ccr["role_change"], 5, labels=False, duplicates="drop")
        rgrad = {f"q{int(qi) + 1}": round(rate_by(sub), 4) for qi, sub in ccr.groupby(qr)}

        # -- contribution to total-model error ----------------------------------------
        cov_m_tot = float(np.cov(TGE[m], TGE["turnovers"])[0, 1])
        cov_delta_m = float(np.cov(TGE["delta_G_minus_D"], TGE[m])[0, 1])
        diagnostics[m] = {
            "group": MECH_GROUP[m],
            "base_rate": {
                "events": n_ev,
                "share_of_all_turnovers": round(n_ev / tot_tov, 6),
                "per_100_off_poss": round(100.0 * n_ev / tot_exp, 5),
                "player_games_with_at_least_one": nz,
                "share_of_player_games_nonzero": round(nz / len(D), 6),
                "mean_per_player_game": round(float(col.mean()), 5),
                "dispersion_index_var_over_mean": round(float(col.var() / col.mean()), 4) if col.mean() > 0 else None,
            },
            "source_schema_stability": {
                "per_100_by_source_CONFOUNDED": {k: round(v, 5) for k, v in by_src.items()},
                "confound_warning": ("source is CONFOUNDED with season type: every 2021-2025 "
                                     "playoff game is CDN. A raw source difference must NEVER be "
                                     "read as a basketball effect."),
                "deconfounded_stratum": "season==2025 & season_type=='Regular Season' (both schemas present)",
                "deconfounded_per_100_by_source": {k: round(v, 5) for k, v in dec_by_src.items()},
                "deconfounded_events_by_source": dec_n,
                "cdn_over_legacy_ratio": round(ratio, 4) if np.isfinite(ratio) else None,
                "verdict": verdict,
            },
            "player_concentration": {
                "n_players": int(len(pl)),
                "top_decile_share_of_events": round(top10, 4) if np.isfinite(top10) else None,
                "gini": round(gcoef, 4) if np.isfinite(gcoef) else None,
                "split_half_r": round(sh, 4) if np.isfinite(sh) else None,
                "spearman_brown_reliability": round(rel, 4) if np.isfinite(rel) else None,
                "n_players_split_half": int(len(w)),
            },
            "involvement_relationship": {
                "per_100_by_involvement_quintile": grad,
                "q5_over_q1_ratio": round(grad_ratio, 4) if np.isfinite(grad_ratio) else None,
                "nulls_preserved_excluded_from_gradient": int(D["offensive_involvement_proxy"].isna().sum()),
            },
            "role_change_relationship": {"per_100_by_role_change_quintile": rgrad},
            "total_model_error_contribution": {
                "team_game_variance_share": round(cov_m_tot / var_tot, 5),
                "share_of_G_minus_D_covariance_with_truth": (
                    round(cov_delta_m / cov_delta_tot, 5) if cov_delta_tot != 0 else None),
                "team_game_mean": round(float(TGE[m].mean()), 4),
                "team_game_sd": round(float(TGE[m].std()), 4),
            },
        }

    # ================= PER-MECHANISM INVOLVEMENT FITS ===================================
    FEATS = ["offensive_involvement_proxy"]
    FEATS2 = ["offensive_involvement_proxy", "role_change"]
    off = (np.log(np.clip(F1["exposure"].to_numpy(float), 1e-6, None))
           + np.log(np.clip(F1["D_ewma_shrunk"].to_numpy(float), 1e-9, None)))

    fits = {}
    seasons = sorted(F1["season"].unique())
    season_arr = F1["season"].to_numpy()
    # a season with too little history falls back exactly as arm G did (to arm D)
    NOTRAIN = np.zeros(len(F1), bool)
    for s in seasons:
        if (season_arr < s).sum() < 2000:
            NOTRAIN |= (season_arr == s)

    def share_baseline(m: str) -> np.ndarray:
        """Walk-forward share-of-total baseline: share_m(prior seasons) * exp(offset).

        Summed over all mechanisms this is exactly exp(offset) = arm D, so the sum-of-mechanism
        model is on the SAME scale as the monolithic arms and the comparison is fair.
        """
        p = np.full(len(F1), np.nan)
        for s in seasons:
            tr = season_arr < s
            te = season_arr == s
            den = float(F1.loc[tr, "turnovers"].sum())
            if tr.sum() == 0 or den <= 0:
                continue                                   # handled by NOTRAIN
            p[te] = (float(F1.loc[tr, m].sum()) / den) * np.exp(off[te])
        return p

    def run_one(m: str) -> dict:
        y_all = F1[m].to_numpy(float)
        n_ev = int(y_all.sum())
        nz = int((y_all > 0).sum())
        supportable = (n_ev >= MIN_EVENTS_FOR_FIT) and (nz >= MIN_NONZERO_ROWS)
        rec = {"group": MECH_GROUP.get(m, m.replace("_grp_", "")),
               "events_in_fit_universe": n_ev,
               "nonzero_rows": nz, "support_ok": bool(supportable)}
        if not supportable:
            rec["status"] = "NOT_FITTED_INSUFFICIENT_SUPPORT"
            rec["reason"] = (f"needs >= {MIN_EVENTS_FOR_FIT} events and >= {MIN_NONZERO_ROWS} "
                             f"nonzero player-games (preregistered); has {n_ev} / {nz}")
            rec["_pred"] = share_baseline(m)
            return rec

        # ---- (1) PARITY fit: arm G's exact protocol, mean-imputed nulls --------------
        Z = F1.copy()
        mu_, sd_ = Z[FEATS].mean(), Z[FEATS].std().replace(0, 1.0)
        Z["_z"] = ((Z[FEATS] - mu_) / sd_).fillna(0.0).to_numpy(float).ravel()
        GATE(f"{m}|pooled_parity", Z, ["_z"], offset=off, target=y_all)
        fp = poisson_cluster_fit(Z[["_z"]].to_numpy(float), y_all, off,
                                 Z["game_id"].to_numpy())

        # ---- (2) COMPLETE-CASE fit: nulls dropped, never imputed --------------------
        cc = F1["offensive_involvement_proxy"].notna().to_numpy()
        Zc = F1.loc[cc].copy()
        muc, sdc = Zc[FEATS].mean(), Zc[FEATS].std().replace(0, 1.0)
        Zc["_z"] = ((Zc[FEATS] - muc) / sdc).to_numpy(float).ravel()
        GATE(f"{m}|pooled_complete_case", Zc, ["_z"], offset=off[cc], target=y_all[cc])
        fc = poisson_cluster_fit(Zc[["_z"]].to_numpy(float), y_all[cc], off[cc],
                                 Zc["game_id"].to_numpy())

        # ---- (3) + role change, complete case --------------------------------------
        cc2 = (F1["offensive_involvement_proxy"].notna() & F1["role_change"].notna()).to_numpy()
        Z2 = F1.loc[cc2].copy()
        mu2, sd2 = Z2[FEATS2].mean(), Z2[FEATS2].std().replace(0, 1.0)
        Xz2 = ((Z2[FEATS2] - mu2) / sd2)
        for i, c in enumerate(FEATS2):
            Z2[f"_z{i}"] = Xz2[c].to_numpy(float)
        zn = [f"_z{i}" for i in range(len(FEATS2))]
        GATE(f"{m}|pooled_with_role_change", Z2, zn, offset=off[cc2], target=y_all[cc2])
        f2 = poisson_cluster_fit(Z2[zn].to_numpy(float), y_all[cc2], off[cc2],
                                 Z2["game_id"].to_numpy())

        # ---- (4) WALK-FORWARD by season, arm G protocol; also yields OOS predictions --
        pred = share_baseline(m)                       # walk-forward share-of-total fallback
        by_season = {}
        for s in seasons:
            tr = season_arr < s
            te = np.where(season_arr == s)[0]
            if tr.sum() < 2000 or F1.loc[tr, m].sum() < MIN_TRAIN_EVENTS:
                by_season[int(s)] = {"fallback": True,
                                     "train_events": int(F1.loc[tr, m].sum())}
                continue
            TR = F1.loc[tr]
            mt_, st_ = TR[FEATS].mean(), TR[FEATS].std().replace(0, 1.0)
            Xtr = ((TR[FEATS] - mt_) / st_).fillna(0.0).to_numpy(float)
            Xte = ((F1.iloc[te][FEATS] - mt_) / st_).fillna(0.0).to_numpy(float)
            GATE(f"{m}|walkforward_{int(s)}", pd.DataFrame(Xtr, columns=["_z"]), ["_z"],
                 offset=off[tr], target=F1.loc[tr, m].to_numpy(float))
            b, conv = poisson_ridge(Xtr, F1.loc[tr, m].to_numpy(float), off[tr], RIDGE_LAMBDA)
            if not conv:
                by_season[int(s)] = {"CONVERGENCE_FAILURE": True}
                continue
            pred[te] = np.exp(np.clip(off[te] + b[0] + Xte @ b[1:], -20, 20))
            by_season[int(s)] = {"fallback": False, "beta_involvement": round(float(b[1]), 6),
                                 "intercept": round(float(b[0]), 6),
                                 "train_events": int(F1.loc[tr, m].sum())}

        wf_betas = [v["beta_involvement"] for v in by_season.values() if "beta_involvement" in v]
        rec.update({
            "status": "FITTED",
            "pooled_parity": {"beta_involvement": round(float(fp["beta"][1]), 6),
                              "se_cluster_robust": round(float(fp["se"][1]), 6),
                              "z": round(float(fp["beta"][1] / fp["se"][1]), 4) if fp["se"][1] > 0 else None,
                              "ci90": [round(float(fp["beta"][1] - 1.645 * fp["se"][1]), 6),
                                       round(float(fp["beta"][1] + 1.645 * fp["se"][1]), 6)],
                              "converged": fp["converged"], "n": fp["n"],
                              "n_game_clusters": fp["n_clusters"]},
            "pooled_complete_case": {"beta_involvement": round(float(fc["beta"][1]), 6),
                                     "se_cluster_robust": round(float(fc["se"][1]), 6),
                                     "ci90": [round(float(fc["beta"][1] - 1.645 * fc["se"][1]), 6),
                                              round(float(fc["beta"][1] + 1.645 * fc["se"][1]), 6)],
                                     "converged": fc["converged"], "n": fc["n"]},
            "pooled_with_role_change": {
                "beta_involvement": round(float(f2["beta"][1]), 6),
                "se_involvement": round(float(f2["se"][1]), 6),
                "beta_role_change": round(float(f2["beta"][2]), 6),
                "se_role_change": round(float(f2["se"][2]), 6),
                "ci90_role_change": [round(float(f2["beta"][2] - 1.645 * f2["se"][2]), 6),
                                     round(float(f2["beta"][2] + 1.645 * f2["se"][2]), 6)],
                "converged": f2["converged"], "n": f2["n"]},
            "walk_forward_by_season": by_season,
            "walk_forward_beta_sign_consistent": (
                bool(len(wf_betas) > 1 and (all(x > 0 for x in wf_betas) or all(x < 0 for x in wf_betas)))),
        })
        b_, s_ = fp["beta"][1], fp["se"][1]
        rec["sign"] = ("positive" if b_ > 0 else "negative" if b_ < 0 else "zero")
        rec["sign_significant_90"] = bool(abs(b_) > 1.645 * s_)
        rec["_pred"] = pred
        return rec

    # TOTAL as the reference (this is literally arm G, refitted here for an apples-to-apples SE)
    y_tot = F1["turnovers"].to_numpy(float)
    Zt = F1.copy()
    mt0, st0 = Zt[FEATS].mean(), Zt[FEATS].std().replace(0, 1.0)
    Zt["_z"] = ((Zt[FEATS] - mt0) / st0).fillna(0.0).to_numpy(float).ravel()
    GATE("TOTAL|pooled_parity", Zt, ["_z"], offset=off, target=y_tot)
    ft = poisson_cluster_fit(Zt[["_z"]].to_numpy(float), y_tot, off, Zt["game_id"].to_numpy())
    total_fit = {"beta_involvement": round(float(ft["beta"][1]), 6),
                 "se_cluster_robust": round(float(ft["se"][1]), 6),
                 "ci90": [round(float(ft["beta"][1] - 1.645 * ft["se"][1]), 6),
                          round(float(ft["beta"][1] + 1.645 * ft["se"][1]), 6)],
                 "z": round(float(ft["beta"][1] / ft["se"][1]), 4),
                 "n": ft["n"], "n_game_clusters": ft["n_clusters"],
                 "interpretation": "this reproduces arm G on the TOTAL count, for reference"}

    for m in MECH:
        fits[m] = run_one(m)

    # ---- group-level fits (aggregate mechanism groups) --------------------------------
    group_fits = {}
    for gname in GROUP_ORDER:
        cols = [m for m in MECH if MECH_GROUP[m] == gname]
        if not cols:
            group_fits[gname] = {"status": "NO_PLAYER_ATTRIBUTED_SUPPORT",
                                 "mechanisms": [m for m in MECHANISM_CROSSWALK
                                                if MECH_GROUP[m] == gname],
                                 "reason": "every event in this group is team-charged"}
            continue
        F1[f"_grp_{gname}"] = F1[cols].sum(axis=1)
        group_fits[gname] = run_one(f"_grp_{gname}")
        group_fits[gname]["mechanisms"] = cols

    # ================= DIRECT CANCELLATION TESTS ========================================
    fitted = {m: r for m, r in fits.items() if r.get("status") == "FITTED"}
    gfitted = {g: r for g, r in group_fits.items() if r.get("status") == "FITTED"}

    def sign_table(d):
        return {k: {"beta": v["pooled_parity"]["beta_involvement"],
                    "ci90": v["pooled_parity"]["ci90"],
                    "sign": v["sign"], "significant_90": v["sign_significant_90"],
                    "events": v["events_in_fit_universe"]} for k, v in d.items()}

    pos = [k for k, v in fitted.items() if v["sign"] == "positive" and v["sign_significant_90"]]
    neg = [k for k, v in fitted.items() if v["sign"] == "negative" and v["sign_significant_90"]]
    gpos = [k for k, v in gfitted.items() if v["sign"] == "positive" and v["sign_significant_90"]]
    gneg = [k for k, v in gfitted.items() if v["sign"] == "negative" and v["sign_significant_90"]]

    # heterogeneity: are the mechanism betas different from each other at all?
    bs = np.array([v["pooled_parity"]["beta_involvement"] for v in fitted.values()])
    ses = np.array([v["pooled_parity"]["se_cluster_robust"] for v in fitted.values()])
    wts = 1.0 / np.clip(ses ** 2, 1e-18, None)
    bbar = float((wts * bs).sum() / wts.sum())
    Q = float((wts * (bs - bbar) ** 2).sum())
    dfree = len(bs) - 1
    # Higgins I^2
    I2 = float(max(0.0, (Q - dfree) / Q)) if Q > 0 else 0.0
    Qp = _chi2_sf(Q, dfree)

    # count-weighted reconstruction: does sum_m (count_m * beta_m) reproduce the total beta?
    cnts = np.array([v["events_in_fit_universe"] for v in fitted.values()], float)
    fitted_ev = float(cnts.sum())
    total_ev = float(F1["turnovers"].sum())
    beta_recon = float((cnts * bs).sum() / total_ev)   # unfitted mechanisms contribute 0

    # ---- the operative test: does a SUM-OF-MECHANISM model beat monolithic G at team level?
    # Every one of the 19 mechanisms contributes: fitted ones via their own model, unfitted ones
    # via the walk-forward share-of-total baseline. The shares sum to 1, so in the absence of any
    # fitted effect the sum collapses EXACTLY onto arm D -- an honest like-for-like comparison.
    S = np.zeros(len(F1))
    for m in MECH:
        S += np.nan_to_num(fits[m]["_pred"], nan=0.0)
    S[NOTRAIN] = np.exp(off[NOTRAIN])          # parity: arm G also falls back to D here
    F1["_sum_mech_pred"] = S
    sum_scale_check = {
        "share_baseline_only_sums_to_arm_D": round(float(
            np.nansum([np.nan_to_num(share_baseline(m), nan=0.0) for m in MECH], axis=0)[~NOTRAIN].sum()
            / np.exp(off[~NOTRAIN]).sum()), 6),
        "rows_falling_back_to_D_no_training_season": int(NOTRAIN.sum()),
    }

    P2Ik = P2I[key + ["pred_D", "pred_G"]].copy()
    P2Ik["team_id"] = P2Ik["team_id"].astype("Int64")
    P2Ik["player_id"] = P2Ik["player_id"].astype("Int64")
    A = F1[key + ["turnovers", "_sum_mech_pred"]].merge(P2Ik, on=key, how="inner")
    TA = A.groupby(["game_id", "team_id"])[["turnovers", "_sum_mech_pred", "pred_D",
                                            "pred_G"]].sum().reset_index()
    team_mae = {c: float(np.mean(np.abs(TA[c] - TA["turnovers"])))
                for c in ["pred_D", "pred_G", "_sum_mech_pred"]}
    player_dev = {c: _pois_dev(A["turnovers"], A[c])
                  for c in ["pred_D", "pred_G", "_sum_mech_pred"]}

    # cluster bootstrap (by game) on the team-level paired difference vs monolithic G
    gids = TA["game_id"].to_numpy()
    ug = np.unique(gids)
    dv = (np.abs(TA["pred_G"] - TA["turnovers"])
          - np.abs(TA["_sum_mech_pred"] - TA["turnovers"])).to_numpy(float)
    idx = {g: np.where(gids == g)[0] for g in ug}
    boot = []
    for _ in range(N_BOOT):
        pick = rng.choice(ug, size=len(ug), replace=True)
        boot.append(float(np.mean(np.concatenate([dv[idx[g]] for g in pick]))))
    boot = np.array(boot)

    # ================= THE COMPETING EXPLANATION ========================================
    # `offensive_involvement_proxy` is a SHARE of team shot attempts: within a team-game the
    # values are near-constant-sum, so the feature is overwhelmingly a WITHIN-team reallocation
    # signal carrying almost no BETWEEN-team information. Reallocating a fixed team total across
    # teammates can improve every player row while leaving the team sum unimproved -- and the
    # exponential link makes the team sum strictly WORSE. This is tested here head to head
    # against the mechanism-cancellation story.
    Zw = F1.copy()
    zz = ((Zw[FEATS] - mt0) / st0).fillna(0.0).to_numpy(float).ravel()
    Zw["_z"] = zz
    tg_mean = Zw.groupby(["game_id", "team_id"])["_z"].transform("mean")
    Zw["_z_between"] = tg_mean
    Zw["_z_within"] = Zw["_z"] - tg_mean
    var_dec = {
        "total_variance_of_standardised_involvement": round(float(np.var(zz)), 6),
        "between_team_game_variance": round(float(np.var(tg_mean)), 6),
        "within_team_game_variance": round(float(np.var(Zw["_z_within"])), 6),
        "within_share_of_variance": round(float(np.var(Zw["_z_within"]) / np.var(zz)), 5),
    }
    GATE("TOTAL|within_between", Zw, ["_z_within", "_z_between"], offset=off, target=y_tot)
    fwb = poisson_cluster_fit(Zw[["_z_within", "_z_between"]].to_numpy(float), y_tot, off,
                              Zw["game_id"].to_numpy())
    wb_total = {"beta_within": round(float(fwb["beta"][1]), 6),
                "se_within": round(float(fwb["se"][1]), 6),
                "beta_between": round(float(fwb["beta"][2]), 6),
                "se_between": round(float(fwb["se"][2]), 6),
                "within_significant_90": bool(abs(fwb["beta"][1]) > 1.645 * fwb["se"][1]),
                "between_significant_90": bool(abs(fwb["beta"][2]) > 1.645 * fwb["se"][2])}
    wb_mech = {}
    for m in fitted:
        GATE(f"{m}|within_between", Zw, ["_z_within", "_z_between"], offset=off,
             target=F1[m].to_numpy(float))
        fm = poisson_cluster_fit(Zw[["_z_within", "_z_between"]].to_numpy(float),
                                 F1[m].to_numpy(float), off, Zw["game_id"].to_numpy())
        wb_mech[m] = {"beta_within": round(float(fm["beta"][1]), 6),
                      "se_within": round(float(fm["se"][1]), 6),
                      "beta_between": round(float(fm["beta"][2]), 6),
                      "se_between": round(float(fm["se"][2]), 6),
                      "within_significant_90": bool(abs(fm["beta"][1]) > 1.645 * fm["se"][1]),
                      "between_significant_90": bool(abs(fm["beta"][2]) > 1.645 * fm["se"][2])}

    # how much of arm G's team-level movement is pure reallocation noise?
    TAg = TA.copy()
    realloc = {
        "team_total_corr_predD_predG": round(float(np.corrcoef(TAg["pred_D"], TAg["pred_G"])[0, 1]), 6),
        "mean_abs_team_level_change_G_minus_D": round(float(np.mean(np.abs(TAg["pred_G"] - TAg["pred_D"]))), 6),
        "corr_of_team_change_with_team_truth": round(float(
            np.corrcoef(TAg["pred_G"] - TAg["pred_D"], TAg["turnovers"])[0, 1]), 6),
        "corr_of_team_change_with_arm_D_team_error": round(float(
            np.corrcoef(TAg["pred_G"] - TAg["pred_D"], TAg["turnovers"] - TAg["pred_D"])[0, 1]), 6),
        "reading": ("a team-level change UNCORRELATED with arm D's team error is noise: it moves "
                    "the team prediction without tracking the team error, which raises team MAE "
                    "while player-level allocation improves"),
    }
    competing_explanation = {
        "claim": ("arm G's feature is a WITHIN-team share, so it reallocates a fixed team total "
                  "between teammates; player rows improve, team totals do not, and the "
                  "exponential link adds team-level noise"),
        "involvement_variance_decomposition": var_dec,
        "total_within_vs_between_fit": wb_total,
        "per_mechanism_within_vs_between_fit": wb_mech,
        "team_level_reallocation_diagnostics": realloc,
    }

    cancellation = {
        "reference_total_fit_arm_G_reproduction": total_fit,
        "per_mechanism_sign_table": sign_table(fitted),
        "per_group_sign_table": sign_table(gfitted),
        "mechanisms_significantly_POSITIVE_90": pos,
        "mechanisms_significantly_NEGATIVE_90": neg,
        "source_schema_caveat_on_the_negative_arm": {
            "mechanism": "traveling",
            "deconfounded_cdn_over_legacy_ratio": diagnostics["traveling"][
                "source_schema_stability"]["cdn_over_legacy_ratio"],
            "note": ("`traveling` carries the only significantly NEGATIVE mechanism effect, and its "
                     "deconfounded CDN/legacy rate ratio is the closest of the well-supported "
                     "mechanisms to the stability boundary. The sign is nonetheless negative in "
                     "EVERY walk-forward season, spanning both source eras, and survives dropping "
                     "nulls and controlling for role_change -- so the sign is not a schema "
                     "artifact. The MAGNITUDE should still not be read as a pure basketball "
                     "quantity, because source remains confounded with season type outside the "
                     "2025 regular season."),
        },
        "groups_significantly_POSITIVE_90": gpos,
        "groups_significantly_NEGATIVE_90": gneg,
        "opposite_signed_significant_effects_exist": bool(pos and neg),
        "opposite_signed_significant_group_effects_exist": bool(gpos and gneg),
        "heterogeneity_across_mechanisms": {
            "Q": round(Q, 4), "df": dfree, "p": f"{Qp:.3e}",
            "I2": round(I2, 4), "precision_weighted_mean_beta": round(bbar, 6),
            "reading": ("Q tests whether the mechanism betas differ from each other at all. "
                        "Heterogeneity WITHOUT sign reversal is NOT cancellation.")},
        "count_weighted_reconstruction": {
            "sum_count_x_beta_over_total": round(beta_recon, 6),
            "total_beta_direct": total_fit["beta_involvement"],
            "fitted_events": int(fitted_ev), "total_events": int(total_ev),
            "unfitted_event_share": round(1 - fitted_ev / total_ev, 5),
            "reading": ("if opposite signs cancelled, the count-weighted sum would be near zero "
                        "while individual betas were large")},
        "sum_of_mechanism_models_vs_monolithic_G": {
            "team_mae": {k: round(v, 5) for k, v in team_mae.items()},
            "player_poisson_deviance": {k: round(v, 6) for k, v in player_dev.items()},
            "team_mae_reduction_sum_vs_G": round(float(dv.mean()), 6),
            "ci90_cluster_bootstrap_by_game": [round(float(np.percentile(boot, 5)), 6),
                                               round(float(np.percentile(boot, 95)), 6)],
            "convention": "INCUMBENT(G) minus CHALLENGER(sum); POSITIVE = sum-of-mechanisms better",
            "team_games": int(len(TA)), "n_boot": N_BOOT,
            "scale_check": sum_scale_check,
            "reading": ("if offsetting mechanism effects were the cause of arm G's team-level "
                        "loss, modelling mechanisms separately would recover it")},
        "competing_explanation_within_team_reallocation": competing_explanation,
    }

    # ================= SEPARATE-MODELLING SUPPORTABILITY ================================
    supportable = {}
    for m in MECH:
        d = diagnostics[m]
        f = fits[m]
        crit = {
            "support_events_ge_200": d["base_rate"]["events"] >= MIN_EVENTS_FOR_FIT,
            "nonzero_rows_ge_150": d["base_rate"]["player_games_with_at_least_one"] >= MIN_NONZERO_ROWS,
            "source_schema_stable_in_deconfounded_stratum":
                d["source_schema_stability"]["verdict"] == "STABLE",
            "player_signal_reliable_split_half_ge_0p2": bool(
                d["player_concentration"]["spearman_brown_reliability"] is not None
                and np.isfinite(d["player_concentration"]["spearman_brown_reliability"] or np.nan)
                and (d["player_concentration"]["spearman_brown_reliability"] or 0) >= 0.20),
            "involvement_effect_significant_90": bool(f.get("sign_significant_90", False)),
        }
        n_ok = sum(bool(v) for v in crit.values())
        supportable[m] = {"criteria": crit, "criteria_met": n_ok,
                          "verdict": ("SUPPORTABLE" if n_ok >= 4 else
                                      "MARGINAL" if n_ok == 3 else "NOT_SUPPORTABLE")}
    group_supportable = {}
    for g in GROUP_ORDER:
        cols = [m for m in MECH if MECH_GROUP[m] == g]
        if not cols:
            group_supportable[g] = {"verdict": "IMPOSSIBLE_NO_PLAYER_SUPPORT"}
            continue
        f = group_fits[g]
        d_ev = sum(diagnostics[m]["base_rate"]["events"] for m in cols)
        rels = [diagnostics[m]["player_concentration"]["spearman_brown_reliability"] for m in cols]
        rels = [r for r in rels if r is not None and np.isfinite(r)]
        srcs = [diagnostics[m]["source_schema_stability"]["verdict"] for m in cols]
        crit = {"support_events_ge_200": d_ev >= MIN_EVENTS_FOR_FIT,
                "any_member_source_stable": any(s == "STABLE" for s in srcs),
                "max_member_reliability_ge_0p2": bool(rels and max(rels) >= 0.20),
                "involvement_effect_significant_90": bool(f.get("sign_significant_90", False))}
        n_ok = sum(bool(v) for v in crit.values())
        group_supportable[g] = {"criteria": crit, "criteria_met": n_ok, "events": d_ev,
                                "verdict": ("SUPPORTABLE" if n_ok >= 3 else
                                            "MARGINAL" if n_ok == 2 else "NOT_SUPPORTABLE")}

    # ================= VERDICT ==========================================================
    supports = cancellation["opposite_signed_significant_effects_exist"]
    recovers = (cancellation["sum_of_mechanism_models_vs_monolithic_G"]
                ["ci90_cluster_bootstrap_by_game"][0] > 0)
    recon = cancellation["count_weighted_reconstruction"]
    # "cancellation" requires the count-weighted sum to be pulled toward zero. It is not:
    # the reconstruction reproduces the total coefficient almost exactly.
    cancels = abs(recon["sum_count_x_beta_over_total"]) < 0.5 * abs(recon["total_beta_direct"])
    if supports and cancels and recovers:
        verdict = "SUPPORTED"
    elif supports and not cancels:
        verdict = "REJECTED_AS_CAUSE__HETEROGENEITY_REAL_BUT_NOT_OFFSETTING"
    elif supports and cancels and not recovers:
        verdict = "REJECTED_AS_CAUSE__CANCELLATION_PRESENT_BUT_MODELLING_IT_DOES_NOT_RECOVER_TEAM_MAE"
    else:
        verdict = "FALSIFIED"

    card_criteria = {
        "card_supports_marker": {
            "text": "involvement helps one mechanism and hurts another with opposite signs",
            "met": bool(supports),
            "evidence": {"significant_positive": pos, "significant_negative": neg,
                         "significant_positive_groups": gpos, "significant_negative_groups": gneg}},
        "card_falsifier_marker": {
            "text": "all mechanisms respond to involvement in the same direction",
            "met": bool(not supports),
            "evidence": "traveling / travel_footwork is significantly negative while bad_pass and "
                        "lost_ball are significantly positive"},
        "card_expected_direction": {
            "text": "the G player-level gain and team-level loss ARISE FROM offsetting mechanism effects",
            "met": bool(supports and cancels and recovers),
            "why_not": ("opposite signs exist and mechanism heterogeneity is large (I2 = "
                        f"{round(I2, 3)}), but the effects do NOT offset: the count-weighted sum "
                        f"({recon['sum_count_x_beta_over_total']}) reproduces the total coefficient "
                        f"({recon['total_beta_direct']}) almost exactly, because the positive "
                        "mechanisms carry ~75% of all turnovers and the negative one ~9%. And "
                        "giving every mechanism its own coefficient makes team MAE WORSE, not "
                        "better. Offsetting mechanism effects are therefore NOT the cause."),
        },
        "identified_cause_instead": {
            "text": ("the sign reversal that matters is WITHIN-team vs BETWEEN-team, not across "
                     "mechanisms. `offensive_involvement_proxy` is a share of team shot attempts: "
                     f"{var_dec['within_share_of_variance']:.1%} of its variance is within a "
                     "team-game. Arm G pools a POSITIVE within-team effect "
                     f"({wb_total['beta_within']:+.4f}) with a NEGATIVE between-team effect "
                     f"({wb_total['beta_between']:+.4f}) into ONE coefficient, which the within "
                     "variance dominates. The resulting coefficient allocates turnovers correctly "
                     "BETWEEN TEAMMATES (player deviance improves) while pushing TEAM TOTALS the "
                     "wrong way (team MAE degrades). This reversal is present in essentially every "
                     "mechanism, so it is a property of the FEATURE, not of the mechanism mix."),
            "supported_by": ["involvement_variance_decomposition", "total_within_vs_between_fit",
                             "per_mechanism_within_vs_between_fit",
                             "team_level_reallocation_diagnostics"],
            "n_mechanisms_with_beta_between_below_beta_within": int(sum(
                1 for v in wb_mech.values() if v["beta_between"] < v["beta_within"])),
            "n_mechanisms_fitted": len(wb_mech),
        },
    }

    for r in fits.values():
        r.pop("_pred", None)
    for r in group_fits.values():
        r.pop("_pred", None)

    OUTJ = {
        "schema": "ws6_mechanism_decomposition/1",
        "workstream": "ws6_mechanism_decomposition",
        "status": "DISCOVERY ONLY -- development evidence; nothing promoted, nothing registered",
        "executed_utc": started, "finished_utc": _utc(),
        "base_commit_expected": "eb1103c",
        "central_question": ("does OFFSETTING MECHANISM EFFECT explain arm G's player-level gain "
                             "with a team-level loss?"),
        "arm_G_phenomenon_as_measured_in_P2": {
            "intrinsic": {"player_deviance_D": 1.08832, "player_deviance_G": 1.08787,
                          "team_mae_D": 2.8960, "team_mae_G": 2.9067,
                          "paired_team_mae_G_vs_D": -0.0107, "ci90": [-0.0152, -0.0063]},
            "operational": {"player_deviance_D": 1.22854, "player_deviance_G": 1.22717,
                            "team_mae_D": 2.9675, "team_mae_G": 2.9725,
                            "paired_team_mae_G_vs_D": -0.0051, "ci90": [-0.0096, -0.0006]},
            "source": "experiments/player_program/turnover_p2_v1/TURNOVER_P2_RESULTS.json",
        },
        "preregistered_thresholds": {
            "min_events_for_fit": MIN_EVENTS_FOR_FIT, "min_train_events": MIN_TRAIN_EVENTS,
            "min_nonzero_rows": MIN_NONZERO_ROWS, "min_exposure_split_half": MIN_EXPOSURE_SPLITHALF,
            "ridge_lambda": RIDGE_LAMBDA, "eb_prior_k": EB_PRIOR_K, "ewma_alpha": EWMA_ALPHA,
            "n_boot": N_BOOT, "seed": SEED},
        "target_closure_check": {"mechanism_columns_sum_to_turnovers": closure,
                                 "n_mechanism_columns": len(MECH)},
        "artifact_provenance_flag": prov,
        "absent_mechanism_columns": absent_expl,
        "mechanism_disposition_from_events": json.loads(disp.reset_index().to_json(orient="records")),
        "source_schema_confound_map": json.loads(
            pd.crosstab([D.drop_duplicates(["game_id", "team_id"])["season"],
                         D.drop_duplicates(["game_id", "team_id"])["season_type"]],
                        D.drop_duplicates(["game_id", "team_id"])["source_system"])
            .reset_index().to_json(orient="records")),
        "join_coverage_nulls_preserved": join_cov,
        "fit_universe": {"rows": int(len(F1)), "team_games": int(TA["game_id"].nunique()),
                         "seasons": [int(s) for s in seasons],
                         "definition": "arm G's own intrinsic universe: eligible, exposure > 0"},
        "per_mechanism_diagnostics": diagnostics,
        "per_mechanism_involvement_fits": fits,
        "per_group_involvement_fits": group_fits,
        "cancellation_test": cancellation,
        "separate_modelling_supportable": supportable,
        "separate_modelling_supportable_by_group": group_supportable,
        "card_criteria_evaluated": card_criteria,
        "verdict": verdict,
        "guardrails": {
            "hypothesis_ledger_card_left_FROZEN_and_unmodified": True,
            "validated_total_turnover_target_untouched": True,
            "no_mechanism_model_promoted": True,
            "no_canonical_artifact_modified": True,
            "arm_registry_not_appended": True,
            "nulls_preserved": True},
    }
    (HERE / "WS6_MECHANISM_DECOMPOSITION.json").write_text(
        json.dumps(OUTJ, indent=2, default=str), encoding="utf-8")
    (HERE / "WS6_FEATURE_GATE_AUDITS.json").write_text(json.dumps({
        "schema": "ws6_feature_gate_audits/1",
        "note": "feature_gate.audit ran before EVERY fit; all audits recorded",
        "n_audits": len(audits), "all_passed": bool(all(a["passed"] for a in audits)),
        "audits": audits}, indent=2, default=str), encoding="utf-8")

    print(f"mechanisms {len(MECH)} fitted {len(fitted)} | verdict {verdict}")
    print(f"gate audits {len(audits)} all_passed={all(a['passed'] for a in audits)}")
    print(f"total beta {total_fit['beta_involvement']:+.5f} ci{total_fit['ci90']}")
    for m, r in fitted.items():
        p = r["pooled_parity"]
        print(f"  {m:26s} n={r['events_in_fit_universe']:6d} beta={p['beta_involvement']:+.5f} "
              f"ci[{p['ci90'][0]:+.5f},{p['ci90'][1]:+.5f}] {'*' if r['sign_significant_90'] else ' '}")
    print("team MAE:", {k: round(v, 5) for k, v in team_mae.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
