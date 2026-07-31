"""
build_rapm_v1.py
================
RAPM v1 — extended lambda sweep + multi-season priors (ROADMAP Phase 2b follow-up).

Infrastructure + honest held-out measurement ONLY: no promotion claim, no registry
entry, no leaderboard touch. Adoption into the game model is the orchestrator's
decision under a separate registered experiment.

What this resolves / builds
---------------------------
1. v0's lambda=5000 sat at the top of its sweep {500,1000,2000,5000} (flagged in
   experiments/rapm_v0/build_log.md). Extend the sweep to 100,000 (log-spaced)
   under v0's EXACT held-out protocol (train 2021-24, predict 2025-26 stint
   margins) and report whether the boundary censored a better lambda.
2. Two multi-season RAPM variants:
   a. PRIOR-ANCHORED: season-s coefficients fit on season-s possessions only,
      ridge-shrunk BOTH toward zero (lambda_within) and toward the player's
      season-(s-1) anchored estimate (lambda_prior):
         min ||y - Xb||^2 + lw*||b||^2 + lp*||b - b_prev||^2
         => b = (X'X + (lw+lp) P)^-1 (X'y + lp * b_prev),  P = I zeroed on
            intercept/home (both stay unpenalized, per v0 house convention).
      New players (never seen in an earlier season) anchor to an EMPIRICAL
      REPLACEMENT-LEVEL prior, not zero: the possession-weighted mean single-
      season (lam=2000) offense/defense coefficient of league entrants in
      strictly earlier seasons (walk-forward safe; 2021/2022 fall back to 0
      because no entrant history exists yet). Players absent a season carry
      their last anchored estimate forward unchanged (documented limitation).
   b. DECAY-POOLED: one weighted ridge on all seasons <= s with possession
      weight 0.5^((s - season)/half_life); half_life and lambda swept jointly.
      half_life=inf reproduces v0's equal-pooled fit exactly.
3. Evaluation (held-out, walk-forward in spirit), the ROADMAP 2b gate menu:
   - predictive stint error: train through season s -> predict season s+1
     stints, folds ->2023, ->2024, ->2025, ->2026 (MAE primary for v0
     continuity; RMSE secondary). Hyperparameters selected ONCE on the ->2025
     fold; the ->2026 fold is evaluated blind at those frozen settings.
     The v0 selection fold (train 21-24 -> 25+26 pooled) is also reported for
     apples-to-apples with v0's published numbers, and the lambda-boundary
     question is answered on that exact protocol.
   - deployed year-over-year stability: r between the ratings each method
     would ship after season s vs after s+1 (pairs 2022-23, 2023-24, 2024-25),
     players >= 1000 possessions in both seasons. NOTE: multi-season methods
     share training data across the pair, so this is partially mechanical —
     reported as the operational number it is, alongside v0's single-season
     "signal" YoY for reference.
   - rank stability of tails: top-25 / bottom-25 overlap (and Spearman) across
     successive deployed ratings, same eligibility.
   - garbage-time sensitivity: refit train<=2024 excluding period>=4 &
     |margin before| >= 15 possessions (flags exist in the data), r vs full.
   - replacement-level behavior: mean net of low-possession players and of
     current-season entrants (should sit below average, shrunk).
   - smoke test ONLY (never a criterion): top-12 by net.
4. Candidate CSVs in data/rapm/rapm_v0.csv's EXACT schema (column names and
   order) so downstream joins keep working, written to
   experiments/rapm_multiseason/ (NOT data/rapm/ — adoption is not this
   script's call):
     - rapm_v1_singleseason_extlambda_train2021_24.csv (v0 method, extended-
       sweep winner on v0's selection protocol)
     - rapm_v1_prior_anchored_train2021_24.csv / ..._train2021_26.csv
     - rapm_v1_decay_pooled_train2021_24.csv   / ..._train2021_26.csv
   Schema-compat notes: `minutes_2021_24` holds TRAINING-WINDOW minutes (name
   kept for join compatibility; for *_train2021_26 files it is 2021-26
   minutes). `lambda_chosen` = lambda_within for the anchored files and the
   pooled lambda for decay files (half_life / lambda_prior documented in
   REPORT.md). `net_100_lam{500,1000,2000,5000}` = the same method refit with
   its within-lambda at those values (other hyperparameters held fixed).

Protocol identity: imports build_rapm (v0) UNMODIFIED and reuses its design
matrix, stint construction, team baseline, and solver conventions. Before any
new number is trusted, this script must reproduce v0's published selection-fold
MAEs {500: 2.1044, 1000: 2.0999, 2000: 2.0963, 5000: 2.0934} and hard-fails if
it cannot.

Outputs: experiments/rapm_multiseason/{REPORT.md, fold_results.csv,
sweep_lambda_extended.csv, sweep_prior_anchored.csv, sweep_decay_pooled.csv,
5 candidate CSVs}. No matplotlib in this environment (and no network to get
it), so sweep curves ship as CSVs plus ASCII curves inside REPORT.md.
"""

from __future__ import annotations

import os
import sys
import time
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import build_rapm as v0  # v0 protocol functions — file NOT modified

ROOT = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(ROOT, "experiments", "rapm_multiseason")
RAPM_V0_CSV = os.path.join(ROOT, "data", "rapm", "rapm_v0.csv")

SEASONS = ["2021", "2022", "2023", "2024", "2025", "2026"]
LAMBDAS_EXT = [500, 1000, 2000, 3500, 5000, 7500, 11000, 16000, 23000,
               33000, 47000, 68000, 100000]
V0_LAMBDAS = [500, 1000, 2000, 5000]
V0_SELFOLD_MAE = {500: 2.1044, 1000: 2.0999, 2000: 2.0963, 5000: 2.0934}
LW_GRID = [0, 500, 1000, 2000, 5000, 10000, 20000, 50000]
LP_GRID = [0, 500, 1000, 2000, 5000, 10000, 20000, 50000]
H_GRID = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0, float("inf")]
LAM_REP = 2000          # fixed a priori: single-season lambda for entrant (replacement) estimation
ELIG_POSS = 1000        # YoY / tails eligibility (v0 diagnostic-2 convention)
TAIL_N = 25

R: list[str] = []       # report lines


def log(s: str = ""):
    print(s)
    R.append(s)


# ---------------------------------------------------------------------------
# weighted gram (w == 1 reproduces v0.gram bit-for-bit; verified at runtime)
# ---------------------------------------------------------------------------
def gram_w(C: np.ndarray, y: np.ndarray, home: np.ndarray, dim: int,
           w: np.ndarray):
    vals = np.ones_like(C, dtype=np.float64)
    vals[:, 1] = home
    G = np.zeros((dim, dim), dtype=np.float64)
    b = np.zeros(dim, dtype=np.float64)
    wy = w * y
    for a in range(12):
        np.add.at(b, C[:, a], vals[:, a] * wy)
        for c in range(12):
            np.add.at(G, (C[:, a], C[:, c]), vals[:, a] * vals[:, c] * w)
    return G, b


@dataclass
class Fit:
    """Design + gram for one training window (optionally possession-weighted)."""
    pids: np.ndarray
    pid_to_col: dict
    P: int
    G: np.ndarray
    b: np.ndarray


def build_fit(df: pd.DataFrame, w: np.ndarray | None = None) -> Fit:
    pids = sorted(set(pd.concat([df[c] for c in v0.OFF_SLOTS + v0.DEF_SLOTS])
                      .astype("int64")))
    p2c = {p: i for i, p in enumerate(pids)}
    P = len(pids)
    C, y, home = v0.make_design(df, p2c, P)
    if w is None:
        w = np.ones(len(df))
    G, b = gram_w(C, y, home, 2 + 2 * P, w)
    return Fit(np.array(pids, dtype=np.int64), p2c, P, G, b)


def solve(fit: Fit, lam: float) -> np.ndarray:
    return v0.solve_ridge(fit.G, fit.b, lam)


def solve_anchored(fit: Fit, lw: float, lp: float, prior: np.ndarray) -> np.ndarray:
    Pd = np.ones(len(fit.b))
    Pd[0] = Pd[1] = 0.0
    return np.linalg.solve(fit.G + (lw + lp) * np.diag(Pd), fit.b + lp * prior)


# ---------------------------------------------------------------------------
# global player space + vector-form models
# ---------------------------------------------------------------------------
@dataclass
class Model:
    """Player coefficients scattered into the GLOBAL pid space.
    NaN = player unseen by this model (prediction fills with fill_off/fill_def)."""
    off: np.ndarray
    def_: np.ndarray
    mu: float
    home: float

    def net100(self, gidx: np.ndarray) -> np.ndarray:
        return 100.0 * self.off[gidx] - 100.0 * self.def_[gidx]


def beta_to_model(fit: Fit, beta: np.ndarray, gmap: dict, U: int) -> Model:
    off = np.full(U, np.nan)
    de = np.full(U, np.nan)
    for i, p in enumerate(fit.pids):
        off[gmap[p]] = beta[2 + i]
        de[gmap[p]] = beta[2 + fit.P + i]
    return Model(off, de, float(beta[0]), float(beta[1]))


# ---------------------------------------------------------------------------
# stint evaluation bundles (v0.build_stints, one prediction path for all models)
# ---------------------------------------------------------------------------
@dataclass
class Bundle:
    season: str
    n_stints: int
    codes: np.ndarray
    sign: np.ndarray
    is_home: np.ndarray
    actual: np.ndarray          # per-stint actual signed margin
    off_idx: np.ndarray         # (5, N) global player indices
    def_idx: np.ndarray
    df: pd.DataFrame            # sorted possession frame (for team baseline)
    slot_pids: np.ndarray = field(default=None)  # (10, N) raw pids for unseen shares


def make_bundle(test_df: pd.DataFrame, gmap: dict) -> Bundle:
    df = v0.build_stints(test_df)
    ids, codes = np.unique(df["stint_id"].to_numpy(), return_inverse=True)
    sign = np.where(df["is_home_offense"].to_numpy() == 1, 1.0, -1.0)
    actual = np.zeros(len(ids))
    np.add.at(actual, codes, sign * df["points_scored"].to_numpy(dtype=float))
    off_idx = np.stack([df[c].astype("int64").map(gmap).to_numpy(dtype=np.int64)
                        for c in v0.OFF_SLOTS])
    def_idx = np.stack([df[c].astype("int64").map(gmap).to_numpy(dtype=np.int64)
                        for c in v0.DEF_SLOTS])
    slot_pids = np.vstack([off_idx, def_idx])
    return Bundle(str(df["season"].iloc[0]), len(ids), codes, sign,
                  df["is_home_offense"].to_numpy(dtype=float), actual,
                  off_idx, def_idx, df, slot_pids)


def stint_errors(bu: Bundle, m: Model, fill_off: float = 0.0,
                 fill_def: float = 0.0) -> np.ndarray:
    ov = m.off[bu.off_idx]
    dv = m.def_[bu.def_idx]
    ov = np.where(np.isnan(ov), fill_off, ov)
    dv = np.where(np.isnan(dv), fill_def, dv)
    pred = m.mu + m.home * bu.is_home + ov.sum(axis=0) + dv.sum(axis=0)
    marg = np.zeros(bu.n_stints)
    np.add.at(marg, bu.codes, bu.sign * pred)
    return marg - bu.actual


def team_errors(bu: Bundle, tb: dict) -> np.ndarray:
    pp = v0.predict_possessions_team(bu.df, tb)
    marg = np.zeros(bu.n_stints)
    np.add.at(marg, bu.codes, bu.sign * pp)
    return marg - bu.actual


def mae(e: np.ndarray) -> float:
    return float(np.abs(e).mean())


def rmse(e: np.ndarray) -> float:
    return float(np.sqrt((e ** 2).mean()))


def unseen_share(bu: Bundle, seen_gidx: set) -> float:
    flat = bu.slot_pids.ravel()
    seen = np.isin(flat, np.fromiter(seen_gidx, dtype=np.int64))
    return float((~seen).mean() * 100)


# ---------------------------------------------------------------------------
# ASCII sweep curve (matplotlib unavailable in this env; no network to add it)
# ---------------------------------------------------------------------------
def ascii_curve(pairs, label_fmt="{:>7}", width=48):
    vals = [v for _, v in pairs]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    out = []
    for k, v in pairs:
        n = int(round((v - lo) / span * width))
        star = " <-- min" if v == lo else ""
        out.append(f"  {label_fmt.format(k)}  {v:.4f}  |" + "#" * n + star)
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    t0 = time.time()
    os.makedirs(EXP, exist_ok=True)

    log("# RAPM v1 — multi-season priors + extended lambda sweep — "
        + time.strftime("%Y-%m-%d %H:%M"))
    log("")
    log("*Model-infrastructure measurement only. No promotion claim; no registry entry;*")
    log("*adoption of any candidate is the orchestrator's decision under a separate*")
    log("*registered experiment. Candidate CSVs live in experiments/rapm_multiseason/,*")
    log("*NOT data/rapm/.*")
    log("")

    # ---------------- data (v0-identical filter) ---------------------------
    poss = pd.read_parquet(v0.POSS_PATH)
    usable = poss[(poss["end_reason"] != "technical_ft")
                  & (poss["n_off_oncourt"] == 5)
                  & (poss["n_def_oncourt"] == 5)].copy()
    log("## 0. Data")
    log(f"- possessions: {len(poss):,} rows; usable (v0 filter: non-technical, "
        f"full 5v5): {len(usable):,} ({len(usable)/len(poss)*100:.2f}%)")
    seas_df = {s: usable[usable["season"] == s].copy() for s in SEASONS}
    for s in SEASONS:
        log(f"  - {s}: {len(seas_df[s]):,} possessions, "
            f"{seas_df[s]['game_id'].nunique():,} games, "
            f"ppp {seas_df[s]['points_scored'].mean():.4f}")

    # global player space
    all_pids = sorted(set(pd.concat([usable[c] for c in v0.OFF_SLOTS + v0.DEF_SLOTS])
                          .astype("int64")))
    gmap = {p: i for i, p in enumerate(all_pids)}
    U = len(all_pids)
    garr = np.array(all_pids, dtype=np.int64)
    log(f"- players across 2021-2026: {U}")

    # per-season possession counts (on-court appearances)
    seas_poss = {}
    for s in SEASONS:
        c = Counter()
        for col in v0.OFF_SLOTS + v0.DEF_SLOTS:
            c.update(seas_df[s][col].astype("int64").tolist())
        seas_poss[s] = c

    # ---------------- fits: per-season and per-window grams ----------------
    tg = time.time()
    seas_fit = {s: build_fit(seas_df[s]) for s in SEASONS}
    windows = {"2022": ["2021", "2022"], "2023": ["2021", "2022", "2023"],
               "2024": ["2021", "2022", "2023", "2024"],
               "2025": ["2021", "2022", "2023", "2024", "2025"],
               "2026": SEASONS}
    win_df = {e: pd.concat([seas_df[s] for s in ss], ignore_index=True)
              for e, ss in windows.items()}
    pooled_fit = {e: build_fit(win_df[e]) for e in ["2022", "2023", "2024", "2025"]}
    print(f"[timing] season+pooled grams {time.time()-tg:.0f}s")

    # verify weighted gram == v0 gram when w == 1 (protocol identity, part 1)
    f21 = seas_fit["2021"]
    C, y, home = v0.make_design(seas_df["2021"], f21.pid_to_col, f21.P)
    G0, b0 = v0.gram(C, y, home, 2 + 2 * f21.P)
    assert np.allclose(G0, f21.G) and np.allclose(b0, f21.b), \
        "gram_w(w=1) != v0.gram — protocol drift"
    log("- gram identity check: gram_w(w=1) == v0.gram on season 2021: PASS")

    # ---------------- bundles + baselines per fold -------------------------
    bundles = {s: make_bundle(seas_df[s], gmap) for s in ["2023", "2024", "2025", "2026"]}
    folds = [("2023", "2022"), ("2024", "2023"), ("2025", "2024"), ("2026", "2025")]
    team_tb = {tr: v0.team_baseline_tables(win_df[tr]) for _, tr in folds}

    seen_by_window = {e: {gmap[p] for s in ss for p in seas_fit[s].pids}
                      for e, ss in windows.items()}

    # ---------------- 1. protocol identity: reproduce v0 -------------------
    log("")
    log("## 1. Protocol identity — reproduce v0's selection fold")
    log("v0 protocol: train 2021-24 pooled ridge, predict 2025+2026 stint margins,")
    log("unseen players -> league average (0).")
    pf24 = pooled_fit["2024"]
    sel_err = {}
    for lam in V0_LAMBDAS:
        beta = solve(pf24, lam)
        m = beta_to_model(pf24, beta, gmap, U)
        e = np.concatenate([stint_errors(bundles["2025"], m),
                            stint_errors(bundles["2026"], m)])
        sel_err[lam] = e
        got, want = round(mae(e), 4), V0_SELFOLD_MAE[lam]
        status = "PASS" if abs(got - want) < 5e-5 else "FAIL"
        log(f"- lam={lam}: sel-fold MAE {got:.4f} (v0 build log {want:.4f}) {status}")
        if status == "FAIL":
            raise RuntimeError(f"v0 reproduction failed at lam={lam}: {got} vs {want}")
    b5000 = solve(pf24, 5000)
    log(f"- lam=5000 intercept {b5000[0]:.4f} home {b5000[1]:+.4f} "
        f"(v0: 0.9962 / +0.0147)")

    # ---------------- 2. extended lambda sweep -----------------------------
    log("")
    log("## 2. Extended lambda sweep — was 5000 censored by the boundary?")
    t1 = time.time()
    ext_rows = []
    e25_by_lam, e26sel_by_lam = {}, {}
    for lam in LAMBDAS_EXT:
        beta = solve(pf24, lam)
        m = beta_to_model(pf24, beta, gmap, U)
        e25 = stint_errors(bundles["2025"], m)
        e26 = stint_errors(bundles["2026"], m)   # trained <=2024, v0 sel-fold half
        e25_by_lam[lam], e26sel_by_lam[lam] = e25, e26
        pooled = np.concatenate([e25, e26])
        ext_rows.append({"lambda": lam,
                         "mae_selfold_2025_26": mae(pooled),
                         "mae_2025": mae(e25), "mae_2026_train_thru2024": mae(e26),
                         "rmse_selfold_2025_26": rmse(pooled),
                         "intercept": float(beta[0]), "home": float(beta[1])})
    ext_df = pd.DataFrame(ext_rows)
    ext_df.round(6).to_csv(os.path.join(EXP, "sweep_lambda_extended.csv"), index=False)
    lam_sel = int(min(LAMBDAS_EXT,
                      key=lambda l: (round(float(ext_df.loc[ext_df["lambda"] == l,
                                    "mae_selfold_2025_26"].iloc[0]), 6), -l)))
    lam_f25 = int(min(LAMBDAS_EXT,
                      key=lambda l: (round(float(ext_df.loc[ext_df["lambda"] == l,
                                    "mae_2025"].iloc[0]), 6), -l)))
    log("Selection-fold curve (v0's exact protocol, train 21-24 -> 25+26 stints):")
    for line in ascii_curve([(r["lambda"], r["mae_selfold_2025_26"]) for r in ext_rows]):
        log(line)
    log(f"- winner on v0's protocol (ties to larger): lambda = {lam_sel:,}")
    log(f"- winner on the ->2025 fold only (used for the walk-forward table): "
        f"lambda = {lam_f25:,}")
    gain = V0_SELFOLD_MAE[5000] - float(ext_df.loc[ext_df['lambda'] == lam_sel,
                                                   'mae_selfold_2025_26'].iloc[0])
    if lam_sel > 5000:
        log(f"- VERDICT: yes — the v0 sweep boundary censored the optimum. "
            f"lam={lam_sel:,} beats lam=5000 by {gain:.4f} stint-MAE points "
            f"on the identical protocol.")
    else:
        log("- VERDICT: no — 5000 stands as the interior optimum on the extended grid.")
    print(f"[timing] extended sweep {time.time()-t1:.0f}s")

    # ---------------- 3. replacement-level priors --------------------------
    log("")
    log("## 3. Replacement-level prior (for new players in the anchored model)")
    log(f"Entrant = player first appearing in season u (absent from every earlier")
    log(f"season's design). Their single-season lam={LAM_REP} coefficients are")
    log("possession-weight averaged over entrant seasons STRICTLY BEFORE t to give")
    log("the season-t anchor for new players (walk-forward safe; already shrunk")
    log("toward 0 by the single-season ridge, so conservative). 2021/2022 have no")
    log("entrant history -> anchor 0 (documented fallback, not a rookie model).")
    ss_beta = {s: solve(seas_fit[s], LAM_REP) for s in SEASONS}
    seen_prior: set = set()
    entrant_rows = []
    for u in SEASONS:
        f = seas_fit[u]
        ent = [p for p in f.pids if p not in seen_prior] if u != "2021" else []
        for p in ent:
            i = f.pid_to_col[p]
            entrant_rows.append({"season": int(u), "player_id": p,
                                 "off": ss_beta[u][2 + i],
                                 "def": ss_beta[u][2 + f.P + i],
                                 "poss": seas_poss[u].get(p, 0)})
        seen_prior |= set(f.pids.tolist())
    ent_df = pd.DataFrame(entrant_rows)
    rep_at = {}
    for t in SEASONS:
        hist = ent_df[ent_df["season"] < int(t)] if len(ent_df) else ent_df
        if len(hist) == 0:
            rep_at[t] = (0.0, 0.0, 0)
        else:
            w = hist["poss"].to_numpy(dtype=float)
            rep_at[t] = (float(np.average(hist["off"], weights=w)),
                         float(np.average(hist["def"], weights=w)), len(hist))
    for t in SEASONS:
        ro, rd, n = rep_at[t]
        log(f"- rep_at[{t}]: off {ro*100:+.3f}/100, def(allowed) {rd*100:+.3f}/100 "
            f"-> net {100*(ro-rd):+.3f}/100  (from {n} prior entrants)")

    # ---------------- 4. prior-anchored grid (select on ->2025) ------------
    log("")
    log("## 4. Prior-anchored two-level sweep (lambda_within x lambda_prior)")
    log("Fit chain 2021->2024 per config; deployed rating = post-2024 snapshot;")
    log("selected on the ->2025 fold (train<=2024 -> 2025 stints, unseen->0).")
    t2 = time.time()

    def anchored_chain(seasons_list, lw, lp, snapshots_at=None):
        off = np.full(U, np.nan)
        de = np.full(U, np.nan)
        snaps = {}
        for s in seasons_list:
            f = seas_fit[s]
            prior = np.zeros(2 + 2 * f.P)
            ro, rd, _ = rep_at[s]
            for i, p in enumerate(f.pids):
                g = gmap[p]
                po, pdv = off[g], de[g]
                prior[2 + i] = po if np.isfinite(po) else ro
                prior[2 + f.P + i] = pdv if np.isfinite(pdv) else rd
            beta = solve_anchored(f, lw, lp, prior)
            for i, p in enumerate(f.pids):
                g = gmap[p]
                off[g] = beta[2 + i]
                de[g] = beta[2 + f.P + i]
            if snapshots_at is None or s in snapshots_at:
                snaps[s] = Model(off.copy(), de.copy(), float(beta[0]), float(beta[1]))
        return snaps

    anc_rows = []
    for lw in LW_GRID:
        for lp in LP_GRID:
            if lw == 0 and lp == 0:
                continue
            snaps = anchored_chain(windows["2024"], lw, lp, snapshots_at={"2024"})
            m = snaps["2024"]
            e25 = stint_errors(bundles["2025"], m)
            e26 = stint_errors(bundles["2026"], m)
            anc_rows.append({"lambda_within": lw, "lambda_prior": lp,
                             "mae_2025": mae(e25),
                             "mae_selfold_2025_26": mae(np.concatenate([e25, e26])),
                             "rmse_2025": rmse(e25)})
    anc_df = pd.DataFrame(anc_rows)
    anc_df.round(6).to_csv(os.path.join(EXP, "sweep_prior_anchored.csv"), index=False)
    best = anc_df.loc[anc_df.sort_values(
        ["mae_2025", "lambda_within", "lambda_prior"],
        ascending=[True, False, False]).index[0]]
    LW_STAR, LP_STAR = int(best["lambda_within"]), int(best["lambda_prior"])
    log(f"- grid: lw in {LW_GRID}, lp in {LP_GRID} ({len(anc_df)} configs)")
    log(f"- chosen on ->2025 fold: lambda_within={LW_STAR:,}, lambda_prior={LP_STAR:,} "
        f"(MAE {best['mae_2025']:.4f})")
    piv = anc_df.pivot(index="lambda_within", columns="lambda_prior", values="mae_2025")
    log("- ->2025 MAE grid (rows lw, cols lp):")
    log("```")
    log(piv.round(4).to_string())
    log("```")
    print(f"[timing] anchored grid {time.time()-t2:.0f}s")

    # ---------------- 5. decay-pooled grid (select on ->2025) --------------
    log("")
    log("## 5. Decay-pooled sweep (half_life x lambda)")
    log("One weighted ridge on 2021-2024, weight 0.5^((2024-season)/half_life);")
    log("half_life=inf == v0's equal pooling. Selected on the ->2025 fold.")
    t3 = time.time()

    def decay_weights(ss, end_year, h):
        yr = np.concatenate([np.full(len(seas_df[s]), int(s)) for s in ss]).astype(float)
        return 0.5 ** ((end_year - yr) / h) if np.isfinite(h) else np.ones(len(yr))

    decay_fit_cache = {}

    def decay_fit(end: str, h: float) -> Fit:
        key = (end, h)
        if key not in decay_fit_cache:
            if not np.isfinite(h):
                decay_fit_cache[key] = pooled_fit[end]
            else:
                ss = windows[end]
                decay_fit_cache[key] = build_fit(win_df[end],
                                                 decay_weights(ss, int(end), h))
        return decay_fit_cache[key]

    dec_rows = []
    for h in H_GRID:
        fh = decay_fit("2024", h)
        for lam in LAMBDAS_EXT:
            m = beta_to_model(fh, solve(fh, lam), gmap, U)
            e25 = stint_errors(bundles["2025"], m)
            e26 = stint_errors(bundles["2026"], m)
            dec_rows.append({"half_life": h, "lambda": lam,
                             "mae_2025": mae(e25),
                             "mae_selfold_2025_26": mae(np.concatenate([e25, e26])),
                             "rmse_2025": rmse(e25)})
    dec_df = pd.DataFrame(dec_rows)
    dec_df.round(6).to_csv(os.path.join(EXP, "sweep_decay_pooled.csv"), index=False)
    bestd = dec_df.loc[dec_df.sort_values(["mae_2025", "half_life", "lambda"],
                                          ascending=[True, False, False]).index[0]]
    H_STAR, LAMD_STAR = float(bestd["half_life"]), int(bestd["lambda"])
    log(f"- grid: half_life in {H_GRID}, lambda = extended grid ({len(dec_df)} configs)")
    log(f"- chosen on ->2025 fold: half_life={H_STAR}, lambda={LAMD_STAR:,} "
        f"(MAE {bestd['mae_2025']:.4f})")
    pivd = dec_df.pivot(index="half_life", columns="lambda", values="mae_2025")
    log("- ->2025 MAE grid (rows half_life, cols lambda):")
    log("```")
    log(pivd.round(4).to_string())
    log("```")
    print(f"[timing] decay grid {time.time()-t3:.0f}s")

    # ---------------- 6. walk-forward fold table ---------------------------
    log("")
    log("## 6. Walk-forward comparison — train <= s, predict s+1 stints")
    log("Hyperparameters frozen from the ->2025 selection above; the ->2026 fold is")
    log("therefore BLIND for all three v1 methods. ->2023/->2024 are supplementary")
    log("folds evaluated at those same (future-selected) settings — labeled as such.")
    log("v0-method rows are refit per window at their fixed lambdas. Unseen players")
    log("predict at league average (0), v0 convention.")
    t4 = time.time()

    anc_snaps_star = anchored_chain(SEASONS, LW_STAR, LP_STAR)  # snapshots every season
    fold_err: dict[str, dict[str, np.ndarray]] = {}
    fold_meta = {}
    model_store: dict[tuple, Model] = {}
    for test_s, tr_end in folds:
        bu = bundles[test_s]
        pf = pooled_fit[tr_end]
        models = {
            "v0 pooled lam=5000": beta_to_model(pf, solve(pf, 5000), gmap, U),
            f"single ext lam={lam_f25}": beta_to_model(pf, solve(pf, lam_f25), gmap, U),
            f"prior-anchored (lw={LW_STAR}, lp={LP_STAR})": anc_snaps_star[tr_end],
            f"decay-pooled (h={H_STAR}, lam={LAMD_STAR})": beta_to_model(
                decay_fit(tr_end, H_STAR), solve(decay_fit(tr_end, H_STAR), LAMD_STAR),
                gmap, U),
        }
        for k, m in models.items():
            model_store[(k, tr_end)] = m
        errs = {"zero baseline": -bu.actual.copy(),
                "team baseline": team_errors(bu, team_tb[tr_end])}
        for name, m in models.items():
            errs[name] = stint_errors(bu, m)
            ro, rd, _ = rep_at[test_s]
            errs[name + " [unseen->repl]"] = stint_errors(bu, m, fill_off=ro,
                                                          fill_def=rd)
        fold_err[test_s] = errs
        fold_meta[test_s] = {
            "n_stints": bu.n_stints,
            "unseen_pct": unseen_share(bu, seen_by_window[tr_end])}

    model_names = list(fold_err["2023"].keys())
    rows = []
    for name in model_names:
        row = {"model": name}
        pooled_e = []
        for test_s, _ in folds:
            e = fold_err[test_s][name]
            row[f"mae_{test_s}"] = mae(e)
            row[f"rmse_{test_s}"] = rmse(e)
            pooled_e.append(e)
        pe = np.concatenate(pooled_e)
        row["mae_pooled"] = mae(pe)
        row["rmse_pooled"] = rmse(pe)
        rows.append(row)
    fold_df = pd.DataFrame(rows)
    fold_df.round(6).to_csv(os.path.join(EXP, "fold_results.csv"), index=False)

    log("")
    log(f"Folds: " + "; ".join(
        f"->{s} ({fold_meta[s]['n_stints']:,} stints, {fold_meta[s]['unseen_pct']:.1f}% "
        f"unseen slots)" for s, _ in folds))
    log("")
    hdr = ("| model | ->2023 | ->2024 | ->2025* | ->2026 (blind) | pooled | RMSE pooled |")
    log(hdr)
    log("|---|---|---|---|---|---|---|")
    for r_ in rows:
        log(f"| {r_['model']} | {r_['mae_2023']:.4f} | {r_['mae_2024']:.4f} | "
            f"{r_['mae_2025']:.4f} | {r_['mae_2026']:.4f} | {r_['mae_pooled']:.4f} | "
            f"{r_['rmse_pooled']:.4f} |")
    log("")
    log("*->2025 is the selection fold for the three v1 methods (their hyperparameters")
    log("minimize this column — read it as in-selection, not held out). v0 lam=5000 was")
    log("itself chosen on 2025-26 data in the v0 build, so its ->2025/->2026 cells carry")
    log("the same caveat. ->2023/->2024 use hyperparameters selected on later seasons")
    log("(reverse-time selection): fair for method comparison, not a prospective sim.")
    log("[unseen->repl] rows: identical fit, but players unseen in training predict at")
    log("the walk-forward replacement prior instead of league average.")
    print(f"[timing] fold table {time.time()-t4:.0f}s")

    # ---------------- 7. deployed YoY stability + tails --------------------
    log("")
    log("## 7. Stability of deployed ratings (as-of season s vs s+1)")
    log(f"Eligibility: >= {ELIG_POSS} on-court possessions in BOTH seasons of the pair")
    log("(v0 diagnostic-2 convention). Deployed rating after season s uses data <= s")
    log("only. NOTE: multi-season methods share training data across a pair, so their")
    log("r is partly mechanical persistence — that is the operationally relevant number")
    log("for a rating you re-ship each season, but it is NOT comparable to v0's")
    log("independent single-season 'signal' YoY, shown last.")
    t5 = time.time()
    pairs = [("2022", "2023"), ("2023", "2024"), ("2024", "2025")]
    # deployed models as of each season end
    deployed = {}
    for e in ["2022", "2023", "2024", "2025"]:
        pf = pooled_fit[e]
        deployed.setdefault("v0 pooled lam=5000", {})[e] = \
            model_store.get(("v0 pooled lam=5000", e)) or beta_to_model(
                pf, solve(pf, 5000), gmap, U)
        deployed.setdefault(f"single ext lam={lam_f25}", {})[e] = \
            model_store.get((f"single ext lam={lam_f25}", e)) or beta_to_model(
                pf, solve(pf, lam_f25), gmap, U)
        deployed.setdefault(f"prior-anchored (lw={LW_STAR}, lp={LP_STAR})", {})[e] = \
            anc_snaps_star[e]
        dk = f"decay-pooled (h={H_STAR}, lam={LAMD_STAR})"
        deployed.setdefault(dk, {})[e] = \
            model_store.get((dk, e)) or beta_to_model(
                decay_fit(e, H_STAR), solve(decay_fit(e, H_STAR), LAMD_STAR), gmap, U)

    stab_summary = {}
    log("")
    log("| method | YoY r (22-23, 23-24, 24-25) | mean r | top-25 overlap | "
        "bottom-25 overlap | Spearman (mean) |")
    log("|---|---|---|---|---|---|")
    for name, per_season in deployed.items():
        rs, tops, bots, rhos = [], [], [], []
        for a, b in pairs:
            elig = np.array([gmap[p] for p in all_pids
                             if seas_poss[a].get(p, 0) >= ELIG_POSS
                             and seas_poss[b].get(p, 0) >= ELIG_POSS])
            na = per_season[a].net100(elig)
            nb = per_season[b].net100(elig)
            ok = np.isfinite(na) & np.isfinite(nb)
            na, nb, el = na[ok], nb[ok], elig[ok]
            rs.append(float(np.corrcoef(na, nb)[0, 1]))
            rhos.append(float(np.corrcoef(pd.Series(na).rank(),
                                          pd.Series(nb).rank())[0, 1]))
            ta = set(el[np.argsort(-na)[:TAIL_N]])
            tb_ = set(el[np.argsort(-nb)[:TAIL_N]])
            ba = set(el[np.argsort(na)[:TAIL_N]])
            bb = set(el[np.argsort(nb)[:TAIL_N]])
            tops.append(len(ta & tb_))
            bots.append(len(ba & bb))
        stab_summary[name] = {"yoy_mean": float(np.mean(rs)),
                              "top": float(np.mean(tops)), "bot": float(np.mean(bots)),
                              "rho": float(np.mean(rhos))}
        log(f"| {name} | {', '.join(f'{x:.3f}' for x in rs)} | {np.mean(rs):.3f} | "
            f"{np.mean(tops):.1f}/{TAIL_N} | {np.mean(bots):.1f}/{TAIL_N} | "
            f"{np.mean(rhos):.3f} |")

    # v0 signal YoY (independent single-season fits, lam=5000) — reference + repro
    sig = []
    for a, b in pairs:
        fa, fb = seas_fit[a], seas_fit[b]
        ba_, bb_ = solve(fa, 5000), solve(fb, 5000)
        ma = beta_to_model(fa, ba_, gmap, U)
        mb = beta_to_model(fb, bb_, gmap, U)
        elig = np.array([gmap[p] for p in all_pids
                         if seas_poss[a].get(p, 0) >= ELIG_POSS
                         and seas_poss[b].get(p, 0) >= ELIG_POSS])
        na, nb = ma.net100(elig), mb.net100(elig)
        ok = np.isfinite(na) & np.isfinite(nb)
        sig.append((a, b, float(np.corrcoef(na[ok], nb[ok])[0, 1]), int(ok.sum())))
    log("")
    log("Reference — v0 'signal' YoY (independent single-season fits, lam=5000):")
    for a, b, r_, n_ in sig:
        note = ""
        if (a, b) == ("2022", "2023"):
            note = "  (v0 build log: 0.515)"
        if (a, b) == ("2023", "2024"):
            note = "  (v0 build log: 0.353)"
        log(f"- r({a} vs {b}) = {r_:.3f}  (n={n_}){note}")
    print(f"[timing] stability {time.time()-t5:.0f}s")

    # ---------------- 8. garbage-time sensitivity --------------------------
    log("")
    log("## 8. Garbage-time sensitivity (train<=2024 window)")
    t6 = time.time()
    tr24 = win_df["2024"]
    margin = (tr24["home_pts_before"] - tr24["away_pts_before"]).abs()
    garb = (tr24["period"] >= 4) & (margin >= v0.GARBAGE_MARGIN)
    ng_df = tr24[~garb].reset_index(drop=True)
    log(f"- garbage possessions (period>=4, |margin|>= {v0.GARBAGE_MARGIN}): "
        f"{int(garb.sum()):,} of {len(tr24):,} ({garb.mean()*100:.2f}%)")
    poss24 = Counter()
    for s in windows["2024"]:
        poss24.update(seas_poss[s])
    elig500 = np.array([gmap[p] for p in all_pids if poss24.get(p, 0) >= 500])

    ng_pooled = build_fit(ng_df)
    # anchored: per-season non-garbage grams
    ng_seas_fit = {}
    for s in windows["2024"]:
        sd = seas_df[s]
        mg = (sd["home_pts_before"] - sd["away_pts_before"]).abs()
        gb = (sd["period"] >= 4) & (mg >= v0.GARBAGE_MARGIN)
        ng_seas_fit[s] = build_fit(sd[~gb].reset_index(drop=True))

    def anchored_chain_alt(fits, lw, lp):
        off = np.full(U, np.nan)
        de = np.full(U, np.nan)
        last = None
        for s in windows["2024"]:
            f = fits[s]
            prior = np.zeros(2 + 2 * f.P)
            ro, rd, _ = rep_at[s]
            for i, p in enumerate(f.pids):
                g = gmap[p]
                prior[2 + i] = off[g] if np.isfinite(off[g]) else ro
                prior[2 + f.P + i] = de[g] if np.isfinite(de[g]) else rd
            beta = solve_anchored(f, lw, lp, prior)
            for i, p in enumerate(f.pids):
                g = gmap[p]
                off[g] = beta[2 + i]
                de[g] = beta[2 + f.P + i]
            last = Model(off.copy(), de.copy(), float(beta[0]), float(beta[1]))
        return last

    ng_yr = np.concatenate([np.full(len(seas_df[s]), int(s)) for s in windows["2024"]]
                           ).astype(float)[~garb.to_numpy()]
    ng_w = 0.5 ** ((2024.0 - ng_yr) / H_STAR) if np.isfinite(H_STAR) else None
    ng_decay_fit = build_fit(ng_df, ng_w)
    gcheck = {
        "v0 pooled lam=5000": (deployed["v0 pooled lam=5000"]["2024"],
                               beta_to_model(ng_pooled, solve(ng_pooled, 5000), gmap, U)),
        f"single ext lam={lam_f25}": (deployed[f"single ext lam={lam_f25}"]["2024"],
                                      beta_to_model(ng_pooled, solve(ng_pooled, lam_f25),
                                                    gmap, U)),
        f"prior-anchored (lw={LW_STAR}, lp={LP_STAR})": (
            anc_snaps_star["2024"], anchored_chain_alt(ng_seas_fit, LW_STAR, LP_STAR)),
        f"decay-pooled (h={H_STAR}, lam={LAMD_STAR})": (
            deployed[f"decay-pooled (h={H_STAR}, lam={LAMD_STAR})"]["2024"],
            beta_to_model(ng_decay_fit, solve(ng_decay_fit, LAMD_STAR), gmap, U)),
    }
    garb_summary = {}
    for name, (full_m, ng_m) in gcheck.items():
        nf = full_m.net100(elig500)
        ng = ng_m.net100(elig500)
        ok = np.isfinite(nf) & np.isfinite(ng)
        r_ = float(np.corrcoef(nf[ok], ng[ok])[0, 1])
        garb_summary[name] = r_
        note = "  (v0 build log: 0.9770)" if name == "v0 pooled lam=5000" else ""
        log(f"- {name}: r(full vs garbage-excluded) = {r_:.4f} "
            f"(n={int(ok.sum())}, >=500 poss){note}")
    print(f"[timing] garbage {time.time()-t6:.0f}s")

    # ---------------- 9. candidates in the exact v0 schema ------------------
    log("")
    log("## 9. Candidate CSVs (exact rapm_v0.csv schema, written to "
        "experiments/rapm_multiseason/)")
    t7 = time.time()
    st = pd.read_parquet(v0.STINTS_PATH,
                         columns=["GAME_ID", "PLAYER_ID", "PLAYER_NAME", "stint_sec"])
    st["season"] = "20" + st["GAME_ID"].str[3:5]
    names = (st.groupby("PLAYER_ID")["PLAYER_NAME"]
             .agg(lambda s: s.mode().iat[0] if len(s.mode()) else ""))

    def window_minutes(ss):
        sub = st[st["season"].isin(set(ss))]
        return sub.groupby("PLAYER_ID")["stint_sec"].sum() / 60.0

    def window_poss(ss):
        off_c, def_c = Counter(), Counter()
        for s in ss:
            for col in v0.OFF_SLOTS:
                off_c.update(seas_df[s][col].astype("int64").tolist())
            for col in v0.DEF_SLOTS:
                def_c.update(seas_df[s][col].astype("int64").tolist())
        return off_c, def_c

    def write_candidate(fname, model_by_lam: dict, chosen_key, lam_chosen_val,
                        window_ss, note):
        """model_by_lam: {500:..,1000:..,2000:..,5000:.., 'chosen': Model}"""
        m = model_by_lam[chosen_key]
        seen = np.isfinite(m.off) | np.isfinite(m.def_)
        pids = garr[seen]
        gidx = np.array([gmap[p] for p in pids])
        off_c, def_c = window_poss(window_ss)
        mins = window_minutes(window_ss)
        out = pd.DataFrame({"player_id": pids})
        out["player_name"] = out["player_id"].map(names).fillna("")
        out["off_poss"] = [off_c.get(p, 0) for p in pids]
        out["def_poss"] = [def_c.get(p, 0) for p in pids]
        out["total_poss"] = out["off_poss"] + out["def_poss"]
        out["minutes_2021_24"] = out["player_id"].map(mins).fillna(0.0).round(1)
        out["orapm_100"] = np.round(100.0 * np.nan_to_num(m.off[gidx]), 3)
        out["drapm_100"] = np.round(-100.0 * np.nan_to_num(m.def_[gidx]), 3)
        out["net_100"] = np.round(out["orapm_100"] + out["drapm_100"], 3)
        out["lambda_chosen"] = lam_chosen_val
        for lam in V0_LAMBDAS:
            ml = model_by_lam[lam]
            out[f"net_100_lam{lam}"] = np.round(
                100.0 * np.nan_to_num(ml.off[gidx])
                - 100.0 * np.nan_to_num(ml.def_[gidx]), 3)
        out = out.sort_values("net_100", ascending=False)
        path = os.path.join(EXP, fname)
        out.to_csv(path, index=False, encoding="utf-8")
        log(f"- {fname}: {len(out)} players. {note}")
        return out

    # (a) single-season-method, extended-lambda winner, v0 window
    cand_ext = {lam: beta_to_model(pf24, solve(pf24, lam), gmap, U)
                for lam in set(V0_LAMBDAS + [lam_sel])}
    cand_ext["chosen"] = cand_ext[lam_sel]
    out_ext = write_candidate(
        "rapm_v1_singleseason_extlambda_train2021_24.csv", cand_ext, "chosen",
        lam_sel, windows["2024"],
        f"v0 method, lambda={lam_sel:,} (extended-sweep winner on v0's own "
        f"selection protocol). Drop-in replacement shape for rapm_v0.csv.")

    # cross-check the lamX columns against rapm_v0.csv (join-compat proof)
    v0csv = pd.read_csv(RAPM_V0_CSV)
    mrg = out_ext.merge(v0csv, on="player_id", suffixes=("_v1", "_v0"))
    max_diff = max(float((mrg[f"net_100_lam{l}_v1"]
                          - mrg[f"net_100_lam{l}_v0"]).abs().max())
                   for l in V0_LAMBDAS)
    log(f"- cross-check vs data/rapm/rapm_v0.csv on net_100_lam{{500..5000}}: "
        f"max |diff| = {max_diff:.4f} over {len(mrg)} joined players "
        f"({'PASS' if max_diff < 0.005 else 'FAIL'})")
    if max_diff >= 0.005:
        raise RuntimeError("candidate lamX columns disagree with rapm_v0.csv")

    # (b) prior-anchored, thru 2024 and thru 2026
    def anchored_candidate(upto: str):
        d = {lw: anchored_chain(windows[upto], lw, LP_STAR,
                                snapshots_at={upto})[upto]
             for lw in V0_LAMBDAS}
        d["chosen"] = anc_snaps_star[upto]
        return d

    write_candidate("rapm_v1_prior_anchored_train2021_24.csv",
                    anchored_candidate("2024"), "chosen", LW_STAR, windows["2024"],
                    f"anchored chain 2021->2024, lw={LW_STAR:,}, lp={LP_STAR:,} "
                    f"(lp fixed in the lamX columns). lambda_chosen = lambda_within.")
    write_candidate("rapm_v1_prior_anchored_train2021_26.csv",
                    anchored_candidate("2026"), "chosen", LW_STAR, windows["2026"],
                    f"anchored chain 2021->2026 (deployment-shaped), lw={LW_STAR:,}, "
                    f"lp={LP_STAR:,}. minutes_2021_24 column holds 2021-26 minutes "
                    f"(schema-name kept for joins).")

    # (c) decay-pooled, thru 2024 and thru 2026
    def decay_candidate(upto: str):
        if upto == "2026":
            ss = windows["2026"]
            fu = build_fit(win_df["2026"], decay_weights(ss, 2026, H_STAR))
        else:
            fu = decay_fit(upto, H_STAR)
        d = {lam: beta_to_model(fu, solve(fu, lam), gmap, U) for lam in V0_LAMBDAS}
        d["chosen"] = beta_to_model(fu, solve(fu, LAMD_STAR), gmap, U)
        return d

    write_candidate("rapm_v1_decay_pooled_train2021_24.csv",
                    decay_candidate("2024"), "chosen", LAMD_STAR, windows["2024"],
                    f"decay-pooled 2021-2024, half_life={H_STAR}, lam={LAMD_STAR:,}.")
    write_candidate("rapm_v1_decay_pooled_train2021_26.csv",
                    decay_candidate("2026"), "chosen", LAMD_STAR, windows["2026"],
                    f"decay-pooled 2021-2026 (deployment-shaped), half_life={H_STAR}, "
                    f"lam={LAMD_STAR:,}. minutes_2021_24 column holds 2021-26 minutes.")
    print(f"[timing] candidates {time.time()-t7:.0f}s")

    # ---------------- 10. replacement-level behavior ------------------------
    log("")
    log("## 10. Replacement-level behavior (train<=2024 candidates)")
    anc24 = anc_snaps_star["2024"]
    dec24 = deployed[f"decay-pooled (h={H_STAR}, lam={LAMD_STAR})"]["2024"]
    ent24 = ent_df[ent_df["season"] == 2024]["player_id"].tolist()
    for name, m in [("v0 pooled lam=5000", deployed["v0 pooled lam=5000"]["2024"]),
                    (f"single ext lam={lam_f25}",
                     deployed[f"single ext lam={lam_f25}"]["2024"]),
                    (f"prior-anchored (lw={LW_STAR}, lp={LP_STAR})", anc24),
                    (f"decay-pooled (h={H_STAR}, lam={LAMD_STAR})", dec24)]:
        seen = np.isfinite(m.off)
        net = 100.0 * m.off - 100.0 * m.def_
        tp = np.array([poss24.get(p, 0) for p in all_pids])
        low = seen & (tp < 300)
        hi = seen & (tp >= 1000)
        ent_idx = np.array([gmap[p] for p in ent24 if np.isfinite(m.off[gmap[p]])])
        ent_net = net[ent_idx] if len(ent_idx) else np.array([np.nan])
        log(f"- {name}: net mean <300 poss {np.nanmean(net[low]):+.3f} "
            f"(n={int(low.sum())}, min {np.nanmin(net[low]):+.3f}, "
            f"max {np.nanmax(net[low]):+.3f}); >=1000 poss {np.nanmean(net[hi]):+.3f} "
            f"(n={int(hi.sum())}); 2024 entrants {np.nanmean(ent_net):+.3f} "
            f"(n={len(ent_idx)})")
    log("  (want: low-poss and entrant means below the established-player mean,")
    log("   and shrunk toward the prior rather than at noisy extremes)")

    # ---------------- 11. smoke test (never a criterion) --------------------
    log("")
    log("## 11. Smoke test ONLY (broken-data check, never a promotion criterion)")
    anc26 = anc_snaps_star["2026"]
    poss_all = Counter()
    for s in SEASONS:
        poss_all.update(seas_poss[s])
    net26 = 100.0 * anc26.off - 100.0 * anc26.def_
    okm = np.isfinite(net26) & (np.array([poss_all.get(p, 0) for p in all_pids]) >= 1500)
    order = np.argsort(-np.where(okm, net26, -np.inf))[:12]
    log(f"top-12 net, prior-anchored thru-2026 candidate (>=1500 poss 2021-26):")
    for g in order:
        pid = int(garr[g])
        log(f"  {str(names.get(pid, '')):<28} net {net26[g]:+6.2f}  "
            f"(o {100*anc26.off[g]:+5.2f} / d {-100*anc26.def_[g]:+5.2f}, "
            f"poss {poss_all.get(pid, 0):>6,})")

    # ---------------- 12. recommendation + files ----------------------------
    log("")
    log("## 12. Honest recommendation (measurement, not promotion)")
    best_pool = min(
        (r_ for r_ in rows if "unseen" not in r_["model"]
         and r_["model"] not in ("zero baseline",)),
        key=lambda r_: r_["mae_pooled"])
    v0row = next(r_ for r_ in rows if r_["model"] == "v0 pooled lam=5000")
    teamrow = next(r_ for r_ in rows if r_["model"] == "team baseline")
    log(f"- Boundary flag: " + (
        f"RESOLVED — censored. On v0's exact protocol the extended sweep prefers "
        f"lambda={lam_sel:,} (sel-fold MAE "
        f"{float(ext_df.loc[ext_df['lambda'] == lam_sel, 'mae_selfold_2025_26'].iloc[0]):.4f} "
        f"vs 2.0934 at 5000)." if lam_sel > 5000 else
        "RESOLVED — not censored; 5000 is an interior optimum on the extended grid."))
    log(f"- Best pooled walk-forward MAE: {best_pool['model']} "
        f"({best_pool['mae_pooled']:.4f} vs v0-method {v0row['mae_pooled']:.4f}, "
        f"team baseline {teamrow['mae_pooled']:.4f}).")
    log("- Margins between RAPM variants are small on stint MAE (stints are ~5")
    log("  possessions of near-coin-flip noise); the stability table is where the")
    log("  multi-season structure shows its value for a rating re-shipped seasonally.")
    log("- No promotion claim is made here. The promotion question (does any of this")
    log("  move the GAME model?) belongs to the orchestrator's registered experiment")
    log("  (minute-weighted aggregation vs team chains), per ROADMAP 2b.")
    log("")
    log("## Files")
    for f in sorted(os.listdir(EXP)):
        log(f"- experiments/rapm_multiseason/{f}")
    log("")
    log(f"runtime {time.time()-t0:.0f}s")

    with open(os.path.join(EXP, "REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(R) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
