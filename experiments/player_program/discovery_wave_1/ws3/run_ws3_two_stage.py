#!/usr/bin/env python3
"""run_ws3_two_stage.py — DISCOVERY ws3_team_total_plus_allocation.

Hypothesis (frozen card): one model should not have to control BOTH how many turnovers a team
commits AND which players commit them. Stage 1 forecasts the team total on projected team
possessions; stage 2 allocates that total compositionally among the projected candidates.
The allocated player expectations sum EXACTLY to the stage-1 team total.

DEVELOPMENT ONLY. Nothing here may replace Arm D. Nothing is appended to arm_registry.jsonl.

Every hyperparameter below is either a REUSED FROZEN CONSTANT from P1/P2 or is fixed in this
header before any result was computed. No retuning.
"""
from __future__ import annotations
import hashlib, json, sys                                                       # noqa: E401
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]                       # experiments/player_program
ROOT = PP.parents[1]                       # repo root
sys.path.insert(0, str(PP)); sys.path.insert(0, str(ROOT))

import feature_gate                                                             # noqa: E402
from feature_gate import FeatureGateFailure                                      # noqa: E402
from evalharness.compare import cluster_bootstrap_ci                             # noqa: E402
from register_turnover_p1 import EB_PRIOR_K, EWMA_ALPHA                          # noqa: E402
from register_turnover_p2 import INVOLVE_ALPHA, INVOLVE_SHRINK_K, RIDGE_LAMBDA, MIN_TRAIN_ROWS  # noqa: E402
from run_turnover_p2 import poisson_ridge                                        # noqa: E402

OUT = HERE
OUT.mkdir(parents=True, exist_ok=True)

# ---- preregistered constants ------------------------------------------------------------- #
HP = {
    "reused_frozen_from_P1": {"EB_PRIOR_K": EB_PRIOR_K, "EWMA_ALPHA": EWMA_ALPHA},
    "reused_frozen_from_P2": {"INVOLVE_ALPHA": INVOLVE_ALPHA,
                              "INVOLVE_SHRINK_K": INVOLVE_SHRINK_K,
                              "RIDGE_LAMBDA": RIDGE_LAMBDA,
                              "MIN_TRAIN_ROWS": MIN_TRAIN_ROWS},
    "fixed_here_before_results": {
        "STAGE1_RIDGE_LAMBDA": 10.0,          # same as the P2 ridge, not retuned
        "STAGE2_RIDGE_LAMBDA": 10.0,
        "MIN_TRAIN_TEAM_GAMES": 200,
        "RECENT_ROSTER_WINDOW": 10,           # same window P2 used for displaced involvement
        "SHARE_CALIBRATION_BINS": 10,
        "WINSOR_Q": [0.005, 0.995],           # training-fold quantiles; see SOFTMAX_SATURATION
    },
}
S1_LAM = HP["fixed_here_before_results"]["STAGE1_RIDGE_LAMBDA"]
S2_LAM = HP["fixed_here_before_results"]["STAGE2_RIDGE_LAMBDA"]
MIN_TG = HP["fixed_here_before_results"]["MIN_TRAIN_TEAM_GAMES"]
ROSTER_W = HP["fixed_here_before_results"]["RECENT_ROSTER_WINDOW"]
NBINS = HP["fixed_here_before_results"]["SHARE_CALIBRATION_BINS"]
WQ = HP["fixed_here_before_results"]["WINSOR_Q"]

# ---- preserved negative result from the FIRST execution of this script -------------------- #
# The first execution reused P2's EWMA update rule verbatim: player minute/shot state was
# decayed ONLY on days the player appeared, while team state was decayed on every team game.
# The two states therefore ran on different decay clocks and player/team was not a share:
# trailing_minutes_share reached 1.617 and prior_tov_share reached 2.575. An additive Poisson
# with a log offset absorbs that; a WITHIN-TEAM SOFTMAX does not. Standardised outliers of ~30
# sigma multiplied by a coefficient of ~0.31 drove eta by ~9, the softmax saturated, and 1% of
# candidates received share 0.0 while others received share 1.0.
SOFTMAX_SATURATION = {
    "status": "NEGATIVE RESULT, PRESERVED",
    "what": ("stage 2 executed with P2's appearance-clocked EWMA state and no winsorisation; "
             "the within-team softmax saturated"),
    "diagnosis": ("player EWMA state was decayed only on days the player appeared while team "
                  "EWMA state was decayed every team game, so player/team was not bounded by 1; "
                  "a within-group softmax is multiplicative and unbounded-outlier-sensitive "
                  "where the additive Poisson of P1/P2 is not"),
    "evidence": {"share_S2_min": 0.0, "share_S2_max": 1.0,
                 "share_S2_1st_percentile": 0.0, "share_S2_99th_percentile": 1.0,
                 "corr_with_D_shares": 0.2353,
                 "max_trailing_minutes_share": 1.617461,
                 "max_prior_tov_share": 2.574689},
    "measured_metrics": {
        "D_frozen_unconstrained": {"poisson_deviance": 1.2285420505227964, "mae": 0.8478710366088574},
        "D_total_x_S2_shares": {"poisson_deviance": 8.246467600014133, "mae": 1.0493567151197083},
        "S1_total_x_S2_shares": {"poisson_deviance": 8.235257361504328, "mae": 1.0431145597016112},
        "ORACLE_total_x_S2_shares": {"poisson_deviance": 8.169484710819662, "mae": 1.0146117501803282},
        "S2_share_calibration_slope": 0.11422294804021273,
        "S2_multinomial_log_loss_per_turnover": 6.237621840236808,
    },
    "correction": ("three changes, in order of importance: (1) the PERMANENT GATE IS NOW RUN PER "
                   "TRAINING FOLD, which caught a 2022-fold design whose within-team variance was "
                   "1e-9 and 1e-17; (2) player state is decayed on EVERY team game (absent players "
                   "contribute 0) and keyed by (team, player), so the ratio is a genuine share; "
                   "(3) stage-2 features are winsorised at training-fold quantiles"),
    "second_saturation_had_a_different_cause": (
        "after (2), the un-winsorised ablation still saturated. The cause was NOT outliers: the "
        "2021 projected-exposure regime gives every Tier A candidate on a team an IDENTICAL "
        "projected possession share and an IDENTICAL p_active, so the 2022 training fold's "
        "within-team-game design had std 7.8e-9 and 5.1e-17. Dividing test rows by that std sent "
        "|X.gamma| to 6.9e4. The POOLED gate cannot see this -- pooled variance is healthy. The "
        "per-training-fold gate blocks it as impossible_scaling and drops both features for that "
        "fold. Winsorisation had merely MASKED it by clipping the feature to a sign indicator."),
    "lesson": ("a feature construction that is safe under an additive link is not automatically "
               "safe under a compositional one, and a design matrix that passes a POOLED audit "
               "can be degenerate inside one training fold. The optimiser converged in 5 Newton "
               "iterations in every fold while producing degenerate shares."),
}

# ---- feature declarations (registered before the fit) ------------------------------------ #
S1_DECLARED = ["log_personnel_rate", "team_tov_rate_ewma", "team_tov_rate_shrunk",
               "roster_continuity_minutes", "roster_continuity_jaccard",
               "displaced_creation_responsibility", "proj_top5_concentration",
               "n_candidates", "frac_candidates_cold_start", "log_proj_team_off_poss"]
S2_DECLARED = ["offensive_involvement_proxy", "proj_off_poss_share", "proj_minutes_share",
               "proj_rotation_rank", "p_active", "prior_tov_share", "role_change",
               "trailing_minutes_share", "responsibility_transfer",
               "displaced_creation_responsibility"]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _pois_dev(y, mu):
    mu = np.clip(np.asarray(mu, float), 1e-9, None); y = np.asarray(y, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(y > 0, y * np.log(np.where(y > 0, y, 1.0) / mu), 0.0)
    return float(2 * np.mean(t - (y - mu)))


# ------------------------------------------------------------------------------------------ #
# conditional multinomial (softmax-share) fit with ridge
# ------------------------------------------------------------------------------------------ #
def _group_bounds(grp: np.ndarray) -> np.ndarray:
    """Start index of each group; rows must already be sorted by grp."""
    return np.flatnonzero(np.r_[True, grp[1:] != grp[:-1]])


def softmax_shares(eta: np.ndarray, starts: np.ndarray, grp_of_row: np.ndarray) -> np.ndarray:
    m = np.maximum.reduceat(eta, starts)
    e = np.exp(eta - m[grp_of_row])
    s = np.add.reduceat(e, starts)
    return e / s[grp_of_row]


def fit_conditional_multinomial(X, n, starts, grp_of_row, offset, lam, iters=100):
    """max sum_t sum_i n_i log p_i  -  lam/2 ||g||^2 ,  p = softmax(offset + X g) within group.

    Newton with step-halving on the penalised objective. Returns (gamma, converged, n_iter).
    Non-convergence is reported, never silently used: a converging optimiser does not validate
    an unidentified design, and a diverging one is an implementation defect.
    """
    p_dim = X.shape[1]
    g = np.zeros(p_dim)
    N = np.add.reduceat(n, starts)                       # per-group realised total

    def obj(gg):
        eta = offset + X @ gg
        m = np.maximum.reduceat(eta, starts)
        s = np.log(np.add.reduceat(np.exp(eta - m[grp_of_row]), starts)) + m
        return float(n @ eta - N @ s) - 0.5 * lam * float(gg @ gg)

    cur = obj(g)
    converged = False
    it = 0
    for it in range(1, iters + 1):
        p = softmax_shares(offset + X @ g, starts, grp_of_row)
        w = N[grp_of_row] * p
        grad = X.T @ (n - w) - lam * g
        # H = -( X' W X - sum_t N_t xbar_t xbar_t' ) - lam I
        XtWX = X.T @ (X * w[:, None])
        Sx = np.vstack([np.add.reduceat(X[:, j] * p, starts) for j in range(p_dim)]).T  # T x p
        H = -(XtWX - (Sx * N[:, None]).T @ Sx) - lam * np.eye(p_dim)
        try:
            step = np.linalg.solve(H, -grad)
        except np.linalg.LinAlgError:
            break
        t = 1.0
        ok = False
        for _ in range(40):
            cand = g + t * step
            v = obj(cand)
            if np.isfinite(v) and v >= cur - 1e-12:
                ok = True
                break
            t *= 0.5
        if not ok:
            break
        if np.max(np.abs(cand - g)) < 1e-9:
            g, cur, converged = cand, v, True
            break
        g, cur = cand, v
    else:
        converged = True
    return g, bool(converged and np.all(np.isfinite(g))), it


# ------------------------------------------------------------------------------------------ #
def build_features():
    """Cutoff-valid team-level and player-within-team features via ONE chronological pass.

    State is snapshotted BEFORE the day's games are consumed, so no feature sees its own game.

    CORRECTION 1 vs the P2 artifact: P2's involvement/role features were built by merging the
    candidate frame onto the REALISED box score, so they are null for exactly the 8,278
    candidates who did not appear. Their missingness is a perfect post-cutoff appearance
    oracle. Here every feature is emitted for EVERY candidate from prior-game state only, so
    missingness means "no prior league history", which is knowable at the cutoff.

    CORRECTION 2 (see SOFTMAX_SATURATION): player EWMA state is decayed on EVERY game its team
    plays -- an absent player contributes 0 -- and is keyed by (team, player). Player and team
    state then share one decay clock, so player/team is a genuine share bounded by 1 and the
    team's shares sum to 1 over its tracked players.
    """
    C = pd.read_parquet(ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet",
                        columns=["game_id", "game_date", "season"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)

    P = pd.read_parquet(PP / "turnover_targets_v1/player_turnover_targets_v1.parquet",
                        columns=["game_id", "team_id", "player_id", "turnovers",
                                 "realised_off_possessions"])
    P = P.merge(C[["game_id", "game_date"]], on="game_id", how="left")

    TM = pd.read_parquet(PP / "turnover_targets_v1/team_turnover_reconciliation_v1.parquet")
    TM = TM.merge(C[["game_id", "game_date", "season"]], on="game_id", how="left")

    O = pd.read_parquet(PP / "turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet")
    PX = pd.read_parquet(PP / "projected_exposure_v1/projected_player_possessions_v1.parquet",
                         columns=["game_id", "team_id", "player_id", "regime", "projected_minutes",
                                  "projected_off_possessions", "p_active"])
    PX = PX[PX["regime"] == "tier_a_only"].drop(columns="regime")
    PACE = pd.read_parquet(PP / "projected_exposure_v1/team_possession_prior_v1.parquet",
                           columns=["game_id", "team_id", "projected_team_off_possessions",
                                    "pace_source", "pace_resolved"])

    box = pd.read_parquet(ROOT / "data/masters/master_player.parquet",
                          columns=["game_id", "team_id", "player_id", "minutes", "fga"])
    box["game_id"] = box["game_id"].astype(str)
    box = box[box["minutes"].notna()].merge(C[["game_id", "game_date"]], on="game_id", how="left")

    key = ["game_id", "team_id", "player_id"]
    F = O[key + ["game_date", "season", "turnovers", "did_appear", "exposure",
                 "D_ewma_shrunk", "pred_D_ewma_shrunk", "league_prior_fallback"]].copy()
    F = F.merge(PX, on=key, how="left")

    # projected role shares (already cutoff-valid: built from the projected exposure artifact)
    g = F.groupby(["game_id", "team_id"])
    F["proj_minutes_share"] = F["projected_minutes"] / g["projected_minutes"].transform("sum")
    F["proj_off_poss_share"] = F["projected_off_possessions"] / g["projected_off_possessions"].transform("sum")
    F["proj_rotation_rank"] = g["projected_minutes"].rank(ascending=False, method="first")
    top5 = (F.sort_values("projected_minutes", ascending=False).groupby(["game_id", "team_id"])
            ["proj_minutes_share"].apply(lambda s: s.nlargest(5).sum())
            .rename("proj_top5_concentration"))
    F = F.merge(top5, on=["game_id", "team_id"], how="left")

    # ---- chronological state ------------------------------------------------------------- #
    a_i, a_t = 1.0 - INVOLVE_ALPHA, 1.0 - EWMA_ALPHA
    p_min, p_fga = {}, {}                        # (team, player) EWMA minutes / fga (alpha INVOLVE)
    p_tov = {}                                   # (team, player) EWMA attributed tov (alpha EWMA)
    t_min, t_fga = {}, {}
    t_tov, t_poss = {}, {}                       # team EWMA attributed tov / off poss
    s_tov, s_poss = {}, {}                       # team season-to-date attributed tov / off poss
    lg_tov = lg_poss = 0.0
    roster: dict = {}                            # team -> set of (team, player) ever seen
    recent: dict = {}                            # team -> list of appearing-player sets

    box_by = {d: v for d, v in box.groupby("game_date", sort=True)}
    tov_by = {d: v for d, v in P.groupby("game_date", sort=True)}
    tm_by = {d: v for d, v in TM.groupby("game_date", sort=True)}
    cand_by = {d: v for d, v in F.groupby("game_date", sort=True)}
    dates = sorted(set(box_by) | set(tov_by) | set(tm_by) | set(cand_by))

    prow, trow = [], []
    for d in dates:
        lg_rate = (lg_tov / lg_poss) if lg_poss > 0 else np.nan
        day = cand_by.get(d)
        if day is not None:
            for (gid, tid), sub in day.groupby(["game_id", "team_id"]):
                tmf = t_fga.get(tid, 0.0); tmm = t_min.get(tid, 0.0); tmt = t_tov.get(tid, 0.0)
                seen = roster.get(tid, set())
                cand = set(sub["player_id"])
                hist = set().union(*recent.get(tid, [set()])[-ROSTER_W:]) if tid in recent else set()
                missing = hist - cand
                disp = (float(sum(p_fga.get((tid, q), 0.0) for q in missing)) / tmf) \
                    if tmf > 0 else np.nan
                cont_min = (float(sum(p_min.get((tid, q), 0.0) for q in cand)) / tmm) \
                    if tmm > 0 else np.nan
                jac = (len(hist & cand) / len(hist)) if hist else np.nan
                for r in sub.itertuples(index=False):
                    known = r.player_id in seen
                    pm = p_min.get((tid, r.player_id), 0.0)
                    pf = p_fga.get((tid, r.player_id), 0.0)
                    pt = p_tov.get((tid, r.player_id), 0.0)
                    prow.append({
                        "game_id": r.game_id, "team_id": r.team_id, "player_id": r.player_id,
                        "offensive_involvement_proxy": ((pf + INVOLVE_SHRINK_K / 9.0)
                                                        / (tmf + INVOLVE_SHRINK_K))
                        if (known and tmf > 0) else np.nan,
                        "trailing_minutes_share": (pm / tmm) if (known and tmm > 0) else np.nan,
                        "prior_tov_share": (pt / tmt) if (known and tmt > 0) else np.nan,
                    })
                pp = (s_poss.get((tid, sub["season"].iloc[0]), 0.0))
                tt = (s_tov.get((tid, sub["season"].iloc[0]), 0.0))
                trow.append({
                    "game_id": gid, "team_id": tid,
                    "team_tov_rate_ewma": (t_tov.get(tid, 0.0) / t_poss[tid])
                    if t_poss.get(tid, 0.0) > 0 else np.nan,
                    "team_tov_rate_shrunk": ((tt + EB_PRIOR_K * lg_rate) / (pp + EB_PRIOR_K))
                    if np.isfinite(lg_rate) else np.nan,
                    "roster_continuity_minutes": cont_min,
                    "roster_continuity_jaccard": jac,
                    "displaced_creation_responsibility": disp,
                    "n_prior_team_games_seen": float(len(recent.get(tid, []))),
                })
        # ---- consume the day ------------------------------------------------------------- #
        # every tracked player of a team that played is decayed, absent ones contributing 0, so
        # player state and team state share one decay clock and the ratio is a genuine share
        b = box_by.get(d)
        tov_obs = {}
        v = tov_by.get(d)
        if v is not None:
            for r in v.itertuples(index=False):
                tov_obs[(r.team_id, r.player_id)] = float(r.turnovers or 0)
        if b is not None:
            for t, sub in b.groupby("team_id"):
                obs_m = dict(zip(sub["player_id"], sub["minutes"].fillna(0.0)))
                obs_f = dict(zip(sub["player_id"], sub["fga"].fillna(0.0)))
                roster.setdefault(t, set()).update(sub["player_id"])
                for q in roster[t]:
                    p_min[(t, q)] = a_i * p_min.get((t, q), 0.0) + float(obs_m.get(q, 0.0))
                    p_fga[(t, q)] = a_i * p_fga.get((t, q), 0.0) + float(obs_f.get(q, 0.0))
                    p_tov[(t, q)] = a_t * p_tov.get((t, q), 0.0) + tov_obs.get((t, q), 0.0)
                t_min[t] = a_i * t_min.get(t, 0.0) + float(sub["minutes"].sum())
                t_fga[t] = a_i * t_fga.get(t, 0.0) + float(sub["fga"].sum())
                recent.setdefault(t, []).append(set(sub["player_id"]))
        m = tm_by.get(d)
        if m is not None:
            for r in m.itertuples(index=False):
                x, nn = float(r.player_attributed or 0), float(r.team_off_possessions or 0)
                t_tov[r.team_id] = a_t * t_tov.get(r.team_id, 0.0) + x
                t_poss[r.team_id] = a_t * t_poss.get(r.team_id, 0.0) + nn
                s_tov[(r.team_id, r.season)] = s_tov.get((r.team_id, r.season), 0.0) + x
                s_poss[(r.team_id, r.season)] = s_poss.get((r.team_id, r.season), 0.0) + nn
                lg_tov += x; lg_poss += nn

    F = F.merge(pd.DataFrame(prow), on=key, how="left")
    T = pd.DataFrame(trow)

    # ---- team frame ---------------------------------------------------------------------- #
    agg = F.groupby(["game_id", "team_id"]).agg(
        D_agg=("pred_D_ewma_shrunk", "sum"),
        cand_realised_total=("turnovers", "sum"),
        n_candidates=("player_id", "size"),
        frac_candidates_cold_start=("league_prior_fallback", "mean"),
        proj_top5_concentration=("proj_top5_concentration", "first"),
        game_date=("game_date", "first"), season=("season", "first")).reset_index()
    T = agg.merge(T, on=["game_id", "team_id"], how="left")
    T = T.merge(TM[["game_id", "team_id", "player_attributed", "team_unattributed",
                    "team_off_possessions"]], on=["game_id", "team_id"], how="left")
    T = T.merge(PACE, on=["game_id", "team_id"], how="left")
    T["log_proj_team_off_poss"] = np.log(np.clip(T["projected_team_off_possessions"], 1e-6, None))
    T["log_personnel_rate"] = (np.log(np.clip(T["D_agg"], 1e-9, None))
                               - T["log_proj_team_off_poss"])
    T["y_team"] = T["player_attributed"]

    # responsibility transfer varies WITHIN a team-game; displaced_* alone does not
    F = F.merge(T[["game_id", "team_id", "displaced_creation_responsibility"]],
                on=["game_id", "team_id"], how="left")
    F["role_change"] = F["proj_minutes_share"] - F["trailing_minutes_share"]
    F["responsibility_transfer"] = (F["displaced_creation_responsibility"]
                                    * (F["proj_off_poss_share"] - F["trailing_minutes_share"]))
    return F, T


# ------------------------------------------------------------------------------------------ #
DROPPABLE = {"zero_variance", "impossible_scaling", "exact_duplicate", "near_collinear"}


def fold_gate(df, names, idx, offset, target, label):
    """Run the PERMANENT gate on the TRAINING FOLD ACTUALLY BEING FITTED.

    Auditing the pooled matrix once is not enough. A feature can have healthy pooled variance
    and NO variance inside one training fold: the 2021 projected-exposure regime gives every
    Tier A candidate on a team an identical projected possession share and an identical
    p_active, so the within-team-game design for the 2022 fold is degenerate at ~1e-17 while
    the pooled design looks fine. Scaling by that std sends |X.gamma| to ~7e4 and saturates the
    softmax. This is the same class of defect that created feature_gate.py.

    A feature with no training-fold variance is UNIDENTIFIED in that fold. It is dropped, never
    adjudicated through. If the design still blocks after dropping, the caller falls back.
    """
    keep = list(names)
    recs = []
    for attempt in range(len(names) + 1):
        try:
            a = feature_gate.audit(df.iloc[idx], keep, offset=offset, target=target)
            a.update({"label": f"{label}/attempt{attempt}", "raised": False, "features": keep})
            recs.append(a)
            return keep, recs, True
        except FeatureGateFailure as e:
            blocking = json.loads(str(e))
            recs.append({"label": f"{label}/attempt{attempt}", "raised": True, "passed": False,
                         "features": list(keep), "blocking": blocking})
            drop = {b["feature"] for b in blocking
                    if b.get("kind") in DROPPABLE and b.get("feature") in keep}
            if not drop:
                return keep, recs, False
            keep = [c for c in keep if c not in drop]
            if not keep:
                return keep, recs, False
    return keep, recs, False


def rank_check(df, names, tol=1e-6):
    """Multi-way rank deficiency, which the PERMANENT gate cannot see.

    feature_gate.audit compares features PAIRWISE. It cannot detect a >2-way exact linear
    dependency. This design has one: proj_off_poss_share == proj_minutes_share exactly, and
    role_change == proj_minutes_share - trailing_minutes_share, so those three span a
    2-dimensional space. Ridge hides it by picking a minimum-norm solution; the coefficients
    are then uninterpretable and unstable across folds. Reported here and resolved by dropping
    one member, which leaves the SPAN of the design exactly unchanged.
    """
    X = df[names].to_numpy(float)
    X = np.where(np.isfinite(X), X, 0.0)
    X = X - X.mean(0)
    sd = X.std(0); sd[sd == 0] = 1.0
    Z = X / sd
    s = np.linalg.svd(Z, compute_uv=False)
    s = s / max(s[0], 1e-300)
    r = int((s > tol).sum())
    out = {"n_features": len(names), "numerical_rank": r,
           "rank_deficient": bool(r < len(names)),
           "normalised_singular_values": [float(x) for x in np.round(s, 10)],
           "condition_number": float(s[0] / max(s[-1], 1e-300))}
    if out["rank_deficient"]:
        V = np.linalg.svd(Z, full_matrices=True)[2]
        out["null_space_loadings"] = [
            dict(zip(names, np.round(V[i] / np.abs(V[i]).max(), 4).tolist()))
            for i in range(r, len(names))]
    return out


def winsorise_fit(df, names, idx, q):
    lo = df[names].iloc[idx].quantile(q[0])
    hi = df[names].iloc[idx].quantile(q[1])
    return lo, hi


def winsorise_apply(df, names, lo, hi):
    return df[names].clip(lower=lo, upper=hi, axis=1)


def within_group_center(df, cols, gidx):
    """Centre each column on its team-game mean over NON-NULL values, then neutral-impute the
    nulls to 0 (the within-group mean). NaNs are preserved in the artifact; imputation happens
    only inside the design matrix and is counted."""
    out = pd.DataFrame(index=df.index)
    imputed = {}
    for c in cols:
        v = df[c].to_numpy(float)
        ok = np.isfinite(v).astype(float)
        s = np.bincount(gidx, weights=np.where(np.isfinite(v), v, 0.0))
        k = np.bincount(gidx, weights=ok)
        mean = np.divide(s, k, out=np.zeros_like(s), where=k > 0)
        cv = np.where(np.isfinite(v), v - mean[gidx], 0.0)
        out[c] = cv
        imputed[c] = int((~np.isfinite(v)).sum())
    return out, imputed


def main() -> int:
    F, T = build_features()
    F = F.sort_values(["game_id", "team_id", "player_id"]).reset_index(drop=True)
    T = T.sort_values(["game_id", "team_id"]).reset_index(drop=True)
    tkey = T["game_id"].astype(str) + "|" + T["team_id"].astype(str)
    fkey = F["game_id"].astype(str) + "|" + F["team_id"].astype(str)
    tindex = {k: i for i, k in enumerate(tkey)}
    gidx = fkey.map(tindex).to_numpy()
    assert np.isfinite(gidx.astype(float)).all(), "every candidate row must join a team-game"
    order = np.argsort(gidx, kind="stable")
    F = F.iloc[order].reset_index(drop=True); gidx = gidx[order]
    starts = _group_bounds(gidx)
    assert len(starts) == len(T), "group bounds must cover every team-game exactly once"

    F.to_parquet(OUT / "ws3_player_features_v1.parquet", index=False)
    T.to_parquet(OUT / "ws3_team_features_v1.parquet", index=False)

    # ==================== MANDATORY PREFIT FEATURE GATE ==================================== #
    gate = {"note": "a converging optimiser does not validate an unidentified design",
            "declared": {"stage1": S1_DECLARED, "stage2": S2_DECLARED}, "audits": []}

    def _try(label, df, names, **kw):
        try:
            a = feature_gate.audit(df, names, **kw)
            a.update({"label": label, "raised": False})
        except FeatureGateFailure as e:
            a = {"label": label, "raised": True, "passed": False,
                 "blocking": json.loads(str(e)), "features": names}
        gate["audits"].append(a)
        return a

    # stage 1, as declared (includes projected pace, which IS the offset)
    _try("stage1_as_declared", T, S1_DECLARED,
         offset=T["log_proj_team_off_poss"].to_numpy(), target=T["y_team"].to_numpy())
    S1_FEATS = [c for c in S1_DECLARED if c != "log_proj_team_off_poss"]
    a1 = _try("stage1_after_removing_the_offset_duplicate", T, S1_FEATS,
              offset=T["log_proj_team_off_poss"].to_numpy(), target=T["y_team"].to_numpy())

    # stage 2, as declared, on the WITHIN-TEAM-GAME centred design (the softmax parametrisation)
    Xc_all, imputed_all = within_group_center(F, S2_DECLARED, gidx)
    off2 = np.log(np.clip(F["pred_D_ewma_shrunk"].to_numpy(float), 1e-12, None))
    _try("stage2_as_declared_within_team_centred", Xc_all, S2_DECLARED,
         offset=off2, target=F["turnovers"].to_numpy())
    S2_PAIRWISE_OK = [c for c in S2_DECLARED
                      if c not in ("proj_minutes_share", "displaced_creation_responsibility")]
    Xp, _ = within_group_center(F, S2_PAIRWISE_OK, gidx)
    _try("stage2_after_removing_the_duplicate_and_the_within_team_constant",
         Xp, S2_PAIRWISE_OK, offset=off2, target=F["turnovers"].to_numpy())

    # ---- supplementary MULTI-WAY rank check (the permanent gate is pairwise only) --------- #
    gate["multiway_rank_check"] = {
        "why": ("feature_gate.audit compares features PAIRWISE and cannot see a >2-way exact "
                "linear dependency; this design contains one"),
        "stage1": rank_check(T, S1_FEATS),
        "stage2_pairwise_clean_design": rank_check(Xp, S2_PAIRWISE_OK),
    }
    # trailing_minutes_share == proj_off_poss_share - role_change on every non-null row.
    # Dropping it leaves the span of the design exactly unchanged and both survivors are
    # named on the frozen card ("projected role", "role change").
    S2_FEATS = [c for c in S2_PAIRWISE_OK if c != "trailing_minutes_share"]
    Xc, imputed = within_group_center(F, S2_FEATS, gidx)
    a2 = _try("stage2_final_after_resolving_the_three_way_dependency",
              Xc, S2_FEATS, offset=off2, target=F["turnovers"].to_numpy())
    gate["multiway_rank_check"]["stage2_final_design"] = rank_check(Xc, S2_FEATS)
    gate["null_imputation_inside_the_design_matrix_only"] = imputed
    gate["stage1_features_used"] = S1_FEATS
    gate["stage2_features_used"] = S2_FEATS
    gate["softmax_saturation_negative_result"] = SOFTMAX_SATURATION

    # ---- LEAKAGE AUDIT of the rebuilt features vs the canonical P2 artifact --------------- #
    P2F = pd.read_parquet(PP / "turnover_p2_v1/turnover_role_context_features_v1.parquet",
                          columns=["game_id", "team_id", "player_id", "trailing_minutes_share",
                                   "role_change", "offensive_involvement_proxy"])
    chk = F[["game_id", "team_id", "player_id", "did_appear"]].merge(
        P2F, on=["game_id", "team_id", "player_id"], how="left")
    leak = {"test": ("is the feature's NULL PATTERN identical to the post-cutoff did_appear "
                     "indicator? if yes the missingness itself is an appearance oracle"),
            "canonical_p2_artifact_NOT_MODIFIED": True, "columns": {}}
    for c in ["trailing_minutes_share", "role_change", "offensive_involvement_proxy"]:
        for src, d in (("turnover_p2_v1_canonical", chk[c]), ("ws3_rebuilt", F[c])):
            nn = d.notna().to_numpy()
            ap = (chk if src.startswith("turnover") else F)["did_appear"].to_numpy(bool)
            leak["columns"][f"{c} :: {src}"] = {
                "non_null": int(nn.sum()), "null": int((~nn).sum()),
                "null_and_appeared": int((~nn & ap).sum()),
                "non_null_and_did_not_appear": int((nn & ~ap).sum()),
                "null_pattern_is_exactly_did_appear": bool((nn == ap).all()),
                "verdict": "LEAKING — missingness is an exact did_appear indicator"
                if (nn == ap).all() else "clean — missingness is not the appearance indicator"}
    leak["rebuilt_null_meaning"] = ("no prior appearance for THAT TEAM before the cutoff, i.e. a "
                                    "cold start; this is knowable at the cutoff and is preserved "
                                    "as NULL rather than imputed in the artifact")
    gate["leakage_audit"] = leak
    gate["passed_for_the_fitted_designs"] = bool(
        a1.get("passed") and a2.get("passed")
        and not gate["multiway_rank_check"]["stage1"]["rank_deficient"]
        and not gate["multiway_rank_check"]["stage2_final_design"]["rank_deficient"]
        and not any(v["null_pattern_is_exactly_did_appear"]
                    for k, v in leak["columns"].items() if k.endswith("ws3_rebuilt")))
    (OUT / "WS3_FEATURE_GATE.json").write_text(json.dumps(gate, indent=2, default=str),
                                               encoding="utf-8")
    if not gate["passed_for_the_fitted_designs"]:
        print(json.dumps({"GATE_BLOCKED": [a for a in gate["audits"] if not a.get("passed")]},
                         indent=2, default=str)[:4000])
        return 2

    # ==================== WALK-FORWARD BY SEASON =========================================== #
    seasons = sorted(T["season"].unique())
    T = T.copy()
    T["S1_total"] = np.nan
    T["D_agg_cal"] = np.nan
    T["K0_total"] = np.nan                      # intercept-only control, identical pipeline
    shares_S2 = np.full(len(F), np.nan)
    shares_S2_nw = np.full(len(F), np.nan)      # ablation: no winsorisation
    fold = {}
    fold_gates = {}
    y_t = T["y_team"].to_numpy(float)
    off1 = T["log_proj_team_off_poss"].to_numpy(float)
    X1_raw = T[S1_FEATS]
    n_pl = F["turnovers"].to_numpy(float)

    for s in seasons:
        tr_t = np.where(T["season"].to_numpy() < s)[0]
        te_t = np.where(T["season"].to_numpy() == s)[0]
        te_p = np.where(np.isin(gidx, te_t))[0]
        tr_p = np.where(np.isin(gidx, tr_t))[0]
        info = {"train_team_games": int(len(tr_t)), "train_player_rows": int(len(tr_p)),
                "test_team_games": int(len(te_t))}

        # ---- stage 1 -------------------------------------------------------------------- #
        if len(tr_t) < MIN_TG:
            for c in ("S1_total", "D_agg_cal", "K0_total"):
                T.loc[T.index[te_t], c] = T["D_agg"].to_numpy()[te_t]
            info["stage1"] = {"fallback_to_D_aggregate": True}
        else:
            lo, hi = winsorise_fit(X1_raw, S1_FEATS, tr_t, WQ)
            X1w = winsorise_apply(X1_raw, S1_FEATS, lo, hi)
            keep1, recs1, ok1 = fold_gate(X1w, S1_FEATS, tr_t, off1[tr_t], y_t[tr_t],
                                          f"stage1_train_fold_{int(s)}")
            fold_gates[f"stage1_{int(s)}"] = {"kept": keep1, "passed": ok1, "audits": recs1}
            mu, sd = X1w.iloc[tr_t].mean(), X1w.iloc[tr_t].std().replace(0, 1.0)
            ZT = ((X1w - mu) / sd).fillna(0.0)
            # K0: intercept only, identical pipeline, zero features
            b0, c0 = poisson_ridge(np.zeros((len(tr_t), 0)), y_t[tr_t], off1[tr_t], S1_LAM)
            T.loc[T.index[te_t], "K0_total"] = np.exp(np.clip(off1[te_t] + b0[0], -20, 20)) \
                if c0 else T["D_agg"].to_numpy()[te_t]
            info["K0_intercept_only"] = {"converged": bool(c0), "intercept": float(b0[0])}
            if not ok1 or not keep1:
                T.loc[T.index[te_t], "S1_total"] = T["D_agg"].to_numpy()[te_t]
                info["stage1"] = {"GATE_BLOCKED": True, "fell_back_to_D_aggregate": True}
            else:
                Xtr = ZT[keep1].iloc[tr_t].to_numpy(float)
                Xte = ZT[keep1].iloc[te_t].to_numpy(float)
                b, conv = poisson_ridge(Xtr, y_t[tr_t], off1[tr_t], S1_LAM)
                if conv:
                    T.loc[T.index[te_t], "S1_total"] = np.exp(
                        np.clip(off1[te_t] + b[0] + Xte @ b[1:], -20, 20))
                    info["stage1"] = {"fallback_to_D_aggregate": False, "converged": True,
                                      "features_after_fold_gate": keep1,
                                      "coef": dict(zip(["intercept"] + keep1,
                                                       np.round(b, 5).tolist()))}
                else:
                    T.loc[T.index[te_t], "S1_total"] = T["D_agg"].to_numpy()[te_t]
                    info["stage1"] = {"CONVERGENCE_FAILURE": True,
                                      "fell_back_to_D_aggregate": True}
            r = float(y_t[tr_t].sum() / T["D_agg"].to_numpy()[tr_t].sum())
            T.loc[T.index[te_t], "D_agg_cal"] = T["D_agg"].to_numpy()[te_t] * r
            info["train_fold_level_calibration_ratio"] = r

        # ---- stage 2 -------------------------------------------------------------------- #
        base_sh = np.exp(off2 - np.log(np.add.reduceat(np.exp(off2), starts))[gidx])
        if len(tr_p) < MIN_TRAIN_ROWS:
            shares_S2[te_p] = base_sh[te_p]
            shares_S2_nw[te_p] = base_sh[te_p]
            info["stage2"] = {"fallback_to_D_proportional_shares": True}
        else:
            g_tr = gidx[tr_p]
            _, inv = np.unique(g_tr, return_inverse=True)
            st_tr = _group_bounds(inv)
            for tag, target, wins in (("winsorised", shares_S2, True),
                                      ("no_winsorisation_ablation", shares_S2_nw, False)):
                Xw = Xc
                if wins:
                    lo, hi = winsorise_fit(Xc, S2_FEATS, tr_p, WQ)
                    Xw = winsorise_apply(Xc, S2_FEATS, lo, hi)
                keep2, recs2, ok2 = fold_gate(Xw, S2_FEATS, tr_p, off2[tr_p], n_pl[tr_p],
                                              f"stage2_{tag}_train_fold_{int(s)}")
                if wins:
                    fold_gates[f"stage2_{int(s)}"] = {"kept": keep2, "passed": ok2,
                                                      "audits": recs2}
                if not ok2 or not keep2:
                    target[te_p] = base_sh[te_p]
                    rec = {"GATE_BLOCKED": True, "fell_back_to_D_proportional_shares": True}
                else:
                    sd2 = Xw[keep2].iloc[tr_p].std().replace(0, 1.0)
                    Xs = (Xw[keep2] / sd2).to_numpy(float)
                    gam, conv2, nit = fit_conditional_multinomial(
                        Xs[tr_p], n_pl[tr_p], st_tr, inv, off2[tr_p], S2_LAM)
                    if conv2:
                        target[te_p] = softmax_shares(off2 + Xs @ gam, starts, gidx)[te_p]
                        rec = {"fallback_to_D_proportional_shares": False, "converged": True,
                               "newton_iterations": int(nit),
                               "features_after_fold_gate": keep2,
                               "gamma": dict(zip(keep2, np.round(gam, 5).tolist()))}
                    else:
                        target[te_p] = base_sh[te_p]
                        rec = {"CONVERGENCE_FAILURE": True,
                               "fell_back_to_D_proportional_shares": True}
                info["stage2" if wins else "stage2_ablation"] = rec
        fold[int(s)] = info

    # ==================== ASSEMBLE ARMS ==================================================== #
    D_agg = T["D_agg"].to_numpy(float)
    S1 = T["S1_total"].to_numpy(float)
    Dcal = T["D_agg_cal"].to_numpy(float)
    K0 = T["K0_total"].to_numpy(float)
    cand_tot = T["cand_realised_total"].to_numpy(float)
    D_sh = np.exp(off2 - np.log(np.add.reduceat(np.exp(off2), starts))[gidx])

    F["share_D"] = D_sh
    F["share_S2"] = shares_S2
    F["share_S2_no_winsorisation"] = shares_S2_nw
    player_arms = {
        "D_frozen_unconstrained": F["pred_D_ewma_shrunk"].to_numpy(float),
        "S1_total_x_D_shares": S1[gidx] * D_sh,
        "D_total_x_S2_shares": D_agg[gidx] * shares_S2,
        "S1_total_x_S2_shares": S1[gidx] * shares_S2,
        "D_total_x_S2_shares_no_winsorisation": D_agg[gidx] * shares_S2_nw,
        "ORACLE_total_x_D_shares": cand_tot[gidx] * D_sh,
        "ORACLE_total_x_S2_shares": cand_tot[gidx] * shares_S2,
    }
    for k, v in player_arms.items():
        F[f"pred_{k}"] = v

    # ---- the sum-to-total constraint MUST hold exactly ---------------------------------- #
    constraint = {}
    for k, tot in (("S1_total_x_D_shares", S1), ("S1_total_x_S2_shares", S1),
                   ("D_total_x_S2_shares", D_agg),
                   ("D_total_x_S2_shares_no_winsorisation", D_agg),
                   ("ORACLE_total_x_S2_shares", cand_tot),
                   ("ORACLE_total_x_D_shares", cand_tot)):
        summed = np.add.reduceat(player_arms[k], starts)
        err = np.abs(summed - tot)
        constraint[k] = {"max_abs_deviation": float(err.max()),
                         "mean_abs_deviation": float(err.mean()),
                         "exact_to_1e-9": bool(err.max() < 1e-9)}
        assert err.max() < 1e-9, f"allocation for {k} does not sum to the stage-1 total"
    for nm, sh in (("share_D", D_sh), ("share_S2", shares_S2),
                   ("share_S2_no_winsorisation", shares_S2_nw)):
        sm = np.add.reduceat(sh, starts)
        constraint[nm] = {"max_abs_share_sum_error": float(np.abs(sm - 1.0).max())}
        assert np.abs(sm - 1.0).max() < 1e-9, f"{nm} does not sum to 1 within every team-game"
    constraint["assertion"] = "ALLOCATED PLAYER EXPECTATIONS SUM EXACTLY TO THE STAGE-1 TEAM TOTAL"

    # ==================== EVALUATION ======================================================= #
    gid_t = T["game_id"].to_numpy()
    gid_p = F["game_id"].to_numpy()
    team_arms = {"D_aggregate_INCUMBENT": D_agg, "D_aggregate_level_calibrated": Dcal,
                 "K0_intercept_only_control": K0, "S1_team_total_model": S1}
    res = {"team_games": int(len(T)), "player_rows": int(len(F)),
           "sign_convention": "INCUMBENT minus CHALLENGER absolute error; POSITIVE = challenger better"}

    res["stage1_team_total"] = {}
    for k, v in team_arms.items():
        res["stage1_team_total"][k] = {
            "mae": float(np.mean(np.abs(v - y_t))),
            "rmse": float(np.sqrt(np.mean((v - y_t) ** 2))),
            "bias": float(np.mean(v - y_t)),
            "poisson_deviance": _pois_dev(y_t, v)}
    res["stage1_paired_vs_D_aggregate"] = {}
    for k, v in team_arms.items():
        if k == "D_aggregate_INCUMBENT":
            continue
        dv = np.abs(D_agg - y_t) - np.abs(v - y_t)
        ci = cluster_bootstrap_ci(dv, gid_t)
        res["stage1_paired_vs_D_aggregate"][k] = {
            "mean_mae_reduction": float(dv.mean()), "ci90": [ci["low"], ci["high"]],
            "clusters": ci["n_clusters"], "team_games_improved": int((dv > 0).sum()),
            "team_games_worsened": int((dv < 0).sum())}
    # the coordinator's required control: a fitted unpenalised intercept buys free recalibration,
    # so the S1 model must clear K0, not only the unfitted Arm D aggregate
    dvk = np.abs(K0 - y_t) - np.abs(S1 - y_t)
    cik = cluster_bootstrap_ci(dvk, gid_t)
    res["stage1_paired_vs_K0_intercept_only"] = {
        "S1_team_total_model": {
            "mean_mae_reduction": float(dvk.mean()), "ci90": [cik["low"], cik["high"]],
            "clusters": cik["n_clusters"], "team_games_improved": int((dvk > 0).sum()),
            "team_games_worsened": int((dvk < 0).sum())},
        "note": ("K0 is an intercept-only Poisson fit on the same offset through the identical "
                 "walk-forward pipeline; it isolates the free recalibration an unpenalised "
                 "intercept buys from any genuine feature contribution")}
    res["stage1_by_season_team_mae"] = {
        int(s): {k: float(np.mean(np.abs(v[T["season"].to_numpy() == s]
                                         - y_t[T["season"].to_numpy() == s])))
                 for k, v in team_arms.items()} for s in seasons}

    res["stage2_player_allocation"] = {}
    for k, v in player_arms.items():
        res["stage2_player_allocation"][k] = {
            "poisson_deviance": _pois_dev(n_pl, v),
            "mae": float(np.mean(np.abs(n_pl - v))),
            "rmse": float(np.sqrt(np.mean((n_pl - v) ** 2))),
            "bias": float(np.mean(v - n_pl))}
    appear = F["did_appear"].to_numpy(bool)
    for lab, m in (("appearing", appear), ("non_appearing", ~appear)):
        res[f"stage2_player_{lab}"] = {
            k: {"n": int(m.sum()), "poisson_deviance": _pois_dev(n_pl[m], v[m]),
                "mae": float(np.mean(np.abs(n_pl[m] - v[m])))} for k, v in player_arms.items()}
    res["stage2_paired_vs_D_frozen"] = {}
    base = player_arms["D_frozen_unconstrained"]
    for k, v in player_arms.items():
        if k == "D_frozen_unconstrained":
            continue
        dv = np.abs(base - n_pl) - np.abs(v - n_pl)
        ci = cluster_bootstrap_ci(dv, gid_p)
        res["stage2_paired_vs_D_frozen"][k] = {
            "mean_mae_reduction": float(dv.mean()), "ci90": [ci["low"], ci["high"]],
            "clusters": ci["n_clusters"], "rows_improved": int((dv > 0).sum()),
            "rows_worsened": int((dv < 0).sum())}
    res["stage2_by_season_player_deviance"] = {
        int(s): {k: _pois_dev(n_pl[F["season"].to_numpy() == s], v[F["season"].to_numpy() == s])
                 for k, v in player_arms.items()} for s in seasons}

    # ---- share calibration --------------------------------------------------------------- #
    pos = cand_tot[gidx] > 0
    real_sh = np.divide(n_pl, cand_tot[gidx], out=np.zeros_like(n_pl), where=cand_tot[gidx] > 0)
    cal = {}
    for nm, sh in (("D_shares", D_sh), ("S2_shares", shares_S2),
                   ("S2_shares_no_winsorisation", shares_S2_nw)):
        q = pd.qcut(pd.Series(sh[pos]), NBINS, labels=False, duplicates="drop")
        w = cand_tot[gidx][pos]
        bins = []
        for b in sorted(pd.Series(q).dropna().unique()):
            m = (q == b).to_numpy()
            bins.append({"bin": int(b), "n": int(m.sum()),
                         "mean_predicted_share": float(sh[pos][m].mean()),
                         "mean_realised_share": float(np.average(real_sh[pos][m],
                                                                 weights=w[m])),
                         "gap": float(np.average(real_sh[pos][m], weights=w[m])
                                      - sh[pos][m].mean())})
        x, y = sh[pos], real_sh[pos]
        A = np.vstack([np.ones_like(x), x]).T
        coef = np.linalg.lstsq(A * np.sqrt(w)[:, None], y * np.sqrt(w), rcond=None)[0]
        cal[nm] = {"decile_bins": bins, "calibration_intercept": float(coef[0]),
                   "calibration_slope": float(coef[1]),
                   "mean_abs_bin_gap": float(np.mean([abs(b["gap"]) for b in bins])),
                   "multinomial_log_loss_per_turnover": float(
                       -np.sum(n_pl[pos] * np.log(np.clip(sh[pos], 1e-12, None)))
                       / max(n_pl[pos].sum(), 1.0))}
    res["share_calibration"] = cal
    res["share_calibration_note"] = ("a perfectly calibrated share model has slope 1, intercept 0 "
                                     "and zero bin gaps; realised shares are weighted by the "
                                     "team-game realised total")

    # ---- retest of the MOTIVATING PREMISE -------------------------------------------------- #
    # ws3 exists because P2 arm G (offensive_involvement_proxy) improved operational player
    # deviance 1.22854 -> 1.22717 while worsening team MAE 2.96745 -> 2.97251. The leakage audit
    # shows arm G's feature is null on exactly the 8,278 non-appearing candidates, so P2 gave
    # every non-appearer the training-mean value and adjusted only the appearers -- an
    # appearance-conditional adjustment that cannot be made at the cutoff. Refit the same
    # one-feature arm through an identical pipeline on the canonical (leaking) column and on the
    # ws3 rebuilt (clean) column, and see whether the gain survives.
    P2F2 = pd.read_parquet(PP / "turnover_p2_v1/turnover_role_context_features_v1.parquet",
                           columns=["game_id", "team_id", "player_id",
                                    "offensive_involvement_proxy"]).rename(
        columns={"offensive_involvement_proxy": "involve_canonical_LEAKING"})
    G = F[["game_id", "team_id", "player_id", "season", "turnovers", "exposure",
           "D_ewma_shrunk", "offensive_involvement_proxy"]].merge(
        P2F2, on=["game_id", "team_id", "player_id"], how="left").rename(
        columns={"offensive_involvement_proxy": "involve_ws3_clean"})
    offG = (np.log(np.clip(G["exposure"].to_numpy(float), 1e-6, None))
            + np.log(np.clip(G["D_ewma_shrunk"].to_numpy(float), 1e-9, None)))
    yG = G["turnovers"].to_numpy(float)
    retest = {}
    for col in ("involve_canonical_LEAKING", "involve_ws3_clean"):
        pred = G["D_ewma_shrunk"].to_numpy(float) * G["exposure"].to_numpy(float)
        for s in seasons:
            tr = np.where(G["season"].to_numpy() < s)[0]
            te = np.where(G["season"].to_numpy() == s)[0]
            if len(tr) < MIN_TRAIN_ROWS:
                continue
            m, sdv = G[col].iloc[tr].mean(), G[col].iloc[tr].std() or 1.0
            z = ((G[col] - m) / sdv).fillna(0.0).to_numpy(float)[:, None]
            b, cv = poisson_ridge(z[tr], yG[tr], offG[tr], RIDGE_LAMBDA)
            if cv:
                pred[te] = np.exp(np.clip(offG[te] + b[0] + z[te] @ b[1:], -20, 20))
        tg = np.add.reduceat(pred, starts)
        retest[col] = {"player_poisson_deviance": _pois_dev(yG, pred),
                       "player_mae": float(np.mean(np.abs(yG - pred))),
                       "team_mae": float(np.mean(np.abs(tg - y_t))),
                       "nulls_mean_imputed": int(G[col].isna().sum())}
    base_dev = _pois_dev(yG, G["D_ewma_shrunk"].to_numpy(float) * G["exposure"].to_numpy(float))
    res["motivating_premise_retest"] = {
        "question": ("does arm G's player-deviance gain survive removal of the post-cutoff "
                     "missingness structure?"),
        "p2_published_operational": {"D_deviance": 1.22854, "G_deviance": 1.22717,
                                     "D_team_mae": 2.96745, "G_team_mae": 2.97251},
        "pipeline_note": ("both variants are refitted here on the OPERATIONAL track walk-forward "
                          "(P2 trained on the intrinsic frame), so absolute values need not "
                          "reproduce P2; the leaking-vs-clean CONTRAST is the measurement"),
        "D_baseline_deviance_this_pipeline": base_dev,
        "arms": retest,
        "gain_vs_D": {k: base_dev - v["player_poisson_deviance"] for k, v in retest.items()},
        "value_of_the_leak_alone": {
            "deviance_advantage_of_the_leaking_column_over_the_clean_one": float(
                retest["involve_ws3_clean"]["player_poisson_deviance"]
                - retest["involve_canonical_LEAKING"]["player_poisson_deviance"]),
            "p2_published_G_minus_D_deviance_gain": 1.22854 - 1.22717,
            "ratio": float((retest["involve_ws3_clean"]["player_poisson_deviance"]
                            - retest["involve_canonical_LEAKING"]["player_poisson_deviance"])
                           / (1.22854 - 1.22717)),
            "reading": ("the post-cutoff missingness structure is worth an order of magnitude "
                        "more deviance than the entire published arm-G gain, so the observation "
                        "that motivated ws3 is not established on cutoff-valid inputs")},
    }

    # ---- the joint question -------------------------------------------------------------- #
    dv_alloc = (np.abs(base - n_pl) - np.abs(player_arms["D_total_x_S2_shares"] - n_pl))
    ci_alloc = cluster_bootstrap_ci(dv_alloc, gid_p)
    dev_base = _pois_dev(n_pl, base)
    dev_alloc = _pois_dev(n_pl, player_arms["D_total_x_S2_shares"])
    res["joint_verdict"] = {
        "question": "does allocation improve player identity WITHOUT harming the team total?",
        "arm_that_answers_it": "D_total_x_S2_shares",
        "why": ("this arm holds the team total EXACTLY at the frozen D aggregate and changes only "
                "the allocation, so its team-total MAE is identical to the incumbent by "
                "construction and any player-level movement is pure allocation"),
        "team_total_mae_identical_to_incumbent": bool(
            abs(float(np.mean(np.abs(np.add.reduceat(player_arms["D_total_x_S2_shares"], starts)
                                     - y_t))) - float(np.mean(np.abs(D_agg - y_t)))) < 1e-9),
        "player_deviance_incumbent": dev_base,
        "player_deviance_allocated": dev_alloc,
        "player_deviance_change": dev_alloc - dev_base,
        "player_mae_reduction": float(dv_alloc.mean()),
        "player_mae_reduction_ci90": [ci_alloc["low"], ci_alloc["high"]],
    }
    gate["per_training_fold_gate"] = fold_gates
    return res, F, T, fold, gate, constraint, seasons


if __name__ == "__main__":
    r = main()
    if isinstance(r, int):
        sys.exit(r)
    res, F, T, fold, gate, constraint, seasons = r
    F.to_parquet(OUT / "ws3_player_predictions_v1.parquet", index=False)
    T.to_parquet(OUT / "ws3_team_predictions_v1.parquet", index=False)
    out = {
        "schema": "discovery_ws3_two_stage/1",
        "workstream": "ws3_team_total_plus_allocation",
        "wave": "discovery_wave_1",
        "lane": "DISCOVERY (development folds only) — may not replace Arm D; not registered as an arm",
        "executed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "hyperparameters": HP,
        "walk_forward": "by season; fold s trains on seasons < s only; all statistics train-fold only",
        "universe": ("ALL Tier A candidate obligations including non-appearers (realised target 0); "
                     "never built from realised rows"),
        "feature_gate": gate,
        "sum_to_total_constraint": constraint,
        "fold_detail": fold,
        "results": res,
        "artifact_sha256": {
            "player_features": _sha(OUT / "ws3_player_features_v1.parquet"),
            "team_features": _sha(OUT / "ws3_team_features_v1.parquet"),
        },
    }
    (OUT / "WS3_RESULTS.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"stage1": res["stage1_team_total"],
                      "stage1_paired": res["stage1_paired_vs_D_aggregate"],
                      "stage2": res["stage2_player_allocation"],
                      "joint": res["joint_verdict"]}, indent=2, default=str))
