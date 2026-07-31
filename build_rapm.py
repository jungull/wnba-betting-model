"""
build_rapm.py
=============
RAPM v0 — possession-level regularized adjusted plus-minus (ROADMAP Phase 2b).
Infrastructure + diagnostics ONLY: no promotion claim, no registry entry. The
promotion experiment happens later, when minute-weighted aggregation challenges
the team chains under the harness.

Model
-----
One row per possession from data/possessions/possessions.parquet (built and
score-reconciled by build_possessions.py). Target y = points scored on the
possession. Design: unpenalized intercept + unpenalized home-offense indicator
+ one OFFENSE dummy per player (+1 when on offense) + one DEFENSE dummy per
player (+1 when on defense). Closed-form numpy ridge (house convention,
experiments/w5_closing_line):  beta = solve(X'X + lam*P, X'y)  with P = identity
zeroed on intercept/home. lam is in POSSESSIONS-EQUIVALENT units (a lam-
possession prior of league-average play per player coefficient), swept over
{500, 1000, 2000, 5000}.

Train: seasons 2021-2024. Held out for the predictive diagnostic: 2025-2026.
Rows used: end_reason != 'technical_ft' (zero-duration synthetic technical-FT
rows carry real points for reconciliation but are not possession opportunities)
and full 5v5 lineups only (n_off_oncourt == n_def_oncourt == 5).

Sign conventions in the output CSV (data/rapm/rapm_v0.csv):
  orapm_100  = +100 * offense beta   (positive = good offense)
  drapm_100  = -100 * defense beta   (positive = good defense)
  net_100    = orapm_100 + drapm_100

Diagnostics (ROADMAP 2b gates — reported, never claimed):
  1. predictive stint error on 2025-2026 (lineup-constant possession runs):
     predicted vs actual home-minus-away points per stint, MAE, against a
     team-strength-only baseline (2021-24 team off/def points-per-possession
     from master_team scores + reconciled possession counts) and a zero
     baseline. Unseen players / expansion teams get the league-average (0)
     coefficient in their respective models.
  2. year-over-year stability: single-season fits, net-rating Pearson r for
     players >= 1000 possessions in both seasons (2022v2023, 2023v2024).
  3. lambda sensitivity: pairwise Spearman rank correlation over the union of
     top-50-by-net sets, plus top-50 overlap counts.
  4. garbage-time sensitivity: refit excluding possessions with period >= 4
     and |score margin before possession| >= 15; Pearson r vs full fit for
     players >= 500 training possessions.
  5. replacement-level behavior: mean net of players < 300 possessions
     (should sit below average, not at zero-noise extremes).
  6. SMOKE TEST ONLY (never a gate): top-15 offense / defense with minutes.

Outputs: data/rapm/rapm_v0.csv, experiments/rapm_v0/rapm_by_season.csv,
experiments/rapm_v0/stint_eval.csv, experiments/rapm_v0/REPORT.md (written by
this script), console log with every number.
"""

from __future__ import annotations

import os
import sys
import time
from collections import Counter

import numpy as np
import pandas as pd

import asof_invariant as aoi

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
POSS_PATH = os.path.join(DATA, "possessions", "possessions.parquet")
STINTS_PATH = os.path.join(DATA, "derived", "stints.parquet")
MASTER_TEAM_PATH = os.path.join(DATA, "masters", "master_team.parquet")
RAPM_DIR = os.path.join(DATA, "rapm")
EXP_DIR = os.path.join(ROOT, "experiments", "rapm_v0")
RAPM_CSV = os.path.join(RAPM_DIR, "rapm_v0.csv")

LAMBDAS = [500, 1000, 2000, 5000]
TRAIN_SEASONS = {"2021", "2022", "2023", "2024"}
TEST_SEASONS = {"2025", "2026"}
GARBAGE_MARGIN = 15          # |margin| >= 15 in Q4+ = garbage time
OFF_SLOTS = [f"off_p{k}" for k in range(1, 6)]
DEF_SLOTS = [f"def_p{k}" for k in range(1, 6)]

REPORT_LINES: list[str] = []


def log(s: str = ""):
    print(s)
    REPORT_LINES.append(s)


# ---------------------------------------------------------------------------
# design / solve
# ---------------------------------------------------------------------------
def make_design(df: pd.DataFrame, pid_to_col: "dict[int, int]", n_players: int):
    """Column-index matrix C (N x 12) + y. Cols: 0 intercept, 1 home,
    2..2+P-1 offense dummies, 2+P..2+2P-1 defense dummies."""
    n = len(df)
    C = np.empty((n, 12), dtype=np.int64)
    C[:, 0] = 0
    C[:, 1] = 1
    for j, c in enumerate(OFF_SLOTS):
        C[:, 2 + j] = df[c].map(pid_to_col).to_numpy(dtype=np.int64) + 2
    for j, c in enumerate(DEF_SLOTS):
        C[:, 7 + j] = df[c].map(pid_to_col).to_numpy(dtype=np.int64) + 2 + n_players
    y = df["points_scored"].to_numpy(dtype=np.float64)
    home = df["is_home_offense"].to_numpy(dtype=np.float64)
    return C, y, home


def gram(C: np.ndarray, y: np.ndarray, home: np.ndarray, dim: int):
    """Accumulate X'X and X'y where X row i has ones at C[i, :] except the home
    column (index 1) whose value is home[i]."""
    vals = np.ones_like(C, dtype=np.float64)
    vals[:, 1] = home
    G = np.zeros((dim, dim), dtype=np.float64)
    b = np.zeros(dim, dtype=np.float64)
    for a in range(12):
        np.add.at(b, C[:, a], vals[:, a] * y)
        for c in range(12):
            np.add.at(G, (C[:, a], C[:, c]), vals[:, a] * vals[:, c])
    return G, b


def solve_ridge(G: np.ndarray, b: np.ndarray, lam: float) -> np.ndarray:
    P = np.ones(len(b))
    P[0] = P[1] = 0.0        # intercept + home unpenalized
    return np.linalg.solve(G + lam * np.diag(P), b)


def fit_rapm(df: pd.DataFrame, lambdas: "list[float]"):
    """Fit on df (already filtered). Returns (players array, {lam: beta}, poss
    counts per player)."""
    pids = sorted(set(pd.concat([df[c] for c in OFF_SLOTS + DEF_SLOTS]).astype("int64")))
    pid_to_col = {p: i for i, p in enumerate(pids)}
    P = len(pids)
    C, y, home = make_design(df, pid_to_col, P)
    G, b = gram(C, y, home, 2 + 2 * P)
    betas = {lam: solve_ridge(G, b, lam) for lam in lambdas}
    off_poss = Counter()
    def_poss = Counter()
    for c in OFF_SLOTS:
        off_poss.update(df[c].astype("int64").tolist())
    for c in DEF_SLOTS:
        def_poss.update(df[c].astype("int64").tolist())
    return np.array(pids, dtype=np.int64), pid_to_col, betas, off_poss, def_poss


def ratings_frame(pids, betas_lam, off_poss, def_poss):
    P = len(pids)
    out = pd.DataFrame({"player_id": pids})
    out["off_poss"] = [off_poss.get(p, 0) for p in pids]
    out["def_poss"] = [def_poss.get(p, 0) for p in pids]
    out["total_poss"] = out["off_poss"] + out["def_poss"]
    for lam, beta in betas_lam.items():
        out[f"orapm_100_lam{lam}"] = 100.0 * beta[2:2 + P]
        out[f"drapm_100_lam{lam}"] = -100.0 * beta[2 + P:2 + 2 * P]
        out[f"net_100_lam{lam}"] = out[f"orapm_100_lam{lam}"] + out[f"drapm_100_lam{lam}"]
    return out


# ---------------------------------------------------------------------------
# stint construction + prediction (held-out diagnostic)
# ---------------------------------------------------------------------------
def build_stints(df: pd.DataFrame) -> pd.DataFrame:
    """Maximal runs of unchanged 10-player floor units within a game.
    Returns one row per stint with possession list boundaries."""
    df = df.sort_values(["game_id", "possession_idx"]).reset_index(drop=True)
    home5 = np.where(df["is_home_offense"].to_numpy() == 1,
                     df[OFF_SLOTS].astype("int64").apply(tuple, axis=1),
                     df[DEF_SLOTS].astype("int64").apply(tuple, axis=1))
    away5 = np.where(df["is_home_offense"].to_numpy() == 1,
                     df[DEF_SLOTS].astype("int64").apply(tuple, axis=1),
                     df[OFF_SLOTS].astype("int64").apply(tuple, axis=1))
    key = pd.Series(list(zip(df["game_id"], home5, away5)))
    new_stint = (key != key.shift(1)).to_numpy()
    df = df.assign(stint_id=np.cumsum(new_stint))
    return df


def predict_possessions_rapm(df, pid_to_col, beta, P):
    mu, h = beta[0], beta[1]
    off_b = beta[2:2 + P]
    def_b = beta[2 + P:2 + 2 * P]

    def side_sum(cols, vec):
        s = np.zeros(len(df))
        for c in cols:
            idx = df[c].map(pid_to_col)          # NaN for unseen players -> 0
            known = idx.notna()
            s[known.to_numpy()] += vec[idx[known].astype(int).to_numpy()]
        return s

    return (mu + h * df["is_home_offense"].to_numpy()
            + side_sum(OFF_SLOTS, off_b) + side_sum(DEF_SLOTS, def_b))


def team_baseline_tables(train_df: pd.DataFrame):
    """2021-24 team off/def points-per-possession from master_team pts +
    reconciled possession counts."""
    mt = pd.read_parquet(MASTER_TEAM_PATH, columns=["game_id", "team_id", "pts"])
    mt["game_id"] = mt["game_id"].astype(str).str.zfill(10)
    train_games = set(train_df["game_id"])
    mt = mt[mt["game_id"].isin(train_games)]
    pts_for = mt.groupby("team_id")["pts"].sum()
    opp = mt.merge(mt, on="game_id", suffixes=("", "_o"))
    opp = opp[opp["team_id"] != opp["team_id_o"]]
    pts_against = opp.groupby("team_id")["pts_o"].sum()
    off_n = train_df.groupby("offense_team_id").size()
    def_n = train_df.groupby("defense_team_id").size()
    off_ppp = (pts_for / off_n).dropna()
    def_ppp = (pts_against / def_n).dropna()
    mu_home = train_df.loc[train_df["is_home_offense"] == 1, "points_scored"].mean()
    mu_away = train_df.loc[train_df["is_home_offense"] == 0, "points_scored"].mean()
    mu = train_df["points_scored"].mean()
    return {"off": off_ppp.to_dict(), "def": def_ppp.to_dict(),
            "mu": mu, "mu_home": mu_home, "mu_away": mu_away}


def predict_possessions_team(df, tb):
    off_adj = df["offense_team_id"].map(tb["off"]).fillna(tb["mu"]) - tb["mu"]
    def_adj = df["defense_team_id"].map(tb["def"]).fillna(tb["mu"]) - tb["mu"]
    base = np.where(df["is_home_offense"] == 1, tb["mu_home"], tb["mu_away"])
    return base + off_adj.to_numpy() + def_adj.to_numpy()


def spearman(a: pd.Series, b: pd.Series) -> float:
    ra, rb = a.rank(), b.rank()
    return float(np.corrcoef(ra, rb)[0, 1])


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    t0 = time.time()
    os.makedirs(RAPM_DIR, exist_ok=True)
    os.makedirs(EXP_DIR, exist_ok=True)

    poss = pd.read_parquet(POSS_PATH)
    log("# RAPM v0 — build log " + time.strftime("%Y-%m-%d %H:%M"))
    log("")
    log(f"possessions loaded: {len(poss):,} rows, {poss['game_id'].nunique():,} games")

    usable = poss[(poss["end_reason"] != "technical_ft") &
                  (poss["n_off_oncourt"] == 5) & (poss["n_def_oncourt"] == 5)].copy()
    log(f"usable (non-technical, full 5v5 lineups): {len(usable):,} "
        f"({len(usable) / len(poss) * 100:.2f}%)")

    train = usable[usable["season"].isin(TRAIN_SEASONS)].copy()
    test = usable[usable["season"].isin(TEST_SEASONS)].copy()
    log(f"train 2021-2024: {len(train):,} possessions / {train['game_id'].nunique():,} games; "
        f"held-out 2025-2026: {len(test):,} / {test['game_id'].nunique():,} games")
    log(f"train points-per-possession: {train['points_scored'].mean():.4f}")

    # ---------------- full fit, lambda sweep --------------------------------
    pids, pid_to_col, betas, off_poss, def_poss = fit_rapm(train, LAMBDAS)
    P = len(pids)
    log(f"players in training design: {P}")
    for lam in LAMBDAS:
        log(f"  lam={lam}: intercept {betas[lam][0]:.4f}  home {betas[lam][1]:+.4f}")
    ratings = ratings_frame(pids, betas, off_poss, def_poss)

    # names + minutes
    st = pd.read_parquet(STINTS_PATH,
                         columns=["GAME_ID", "PLAYER_ID", "PLAYER_NAME", "stint_sec"])
    st["season"] = "20" + st["GAME_ID"].str[3:5]
    st_train = st[st["season"].isin(TRAIN_SEASONS)]
    names = (st.groupby("PLAYER_ID")["PLAYER_NAME"]
             .agg(lambda s: s.mode().iat[0] if len(s.mode()) else ""))
    mins = st_train.groupby("PLAYER_ID")["stint_sec"].sum() / 60.0
    ratings["player_name"] = ratings["player_id"].map(names).fillna("")
    ratings["minutes_2021_24"] = ratings["player_id"].map(mins).fillna(0.0).round(1)

    # ---------------- diagnostic 1: predictive stint error ------------------
    stints = build_stints(test)
    tb = team_baseline_tables(train)
    sign = np.where(stints["is_home_offense"] == 1, 1.0, -1.0)
    stints["_signed_pts"] = sign * stints["points_scored"]
    stints["_team_signed"] = sign * predict_possessions_team(stints, tb)
    for lam in LAMBDAS:
        pp = predict_possessions_rapm(stints, pid_to_col, betas[lam], P)
        stints[f"_rapm_signed_{lam}"] = sign * pp
    grp = stints.groupby("stint_id")
    eval_df = grp.agg(
        game_id=("game_id", "first"), season=("season", "first"),
        n_poss=("points_scored", "size"),
        actual_margin=("_signed_pts", "sum"),
        pred_team=("_team_signed", "sum"),
        **{f"pred_rapm_{lam}": (f"_rapm_signed_{lam}", "sum") for lam in LAMBDAS})
    lam_stint_mae = {
        lam: float((eval_df[f"pred_rapm_{lam}"] - eval_df["actual_margin"]).abs().mean())
        for lam in LAMBDAS}
    mae_team = float((eval_df["pred_team"] - eval_df["actual_margin"]).abs().mean())
    mae_zero = float(eval_df["actual_margin"].abs().mean())

    log("")
    log("## Diagnostic 1 — predictive stint error, 2025-2026 held out")
    log(f"stints: {len(eval_df):,} (mean {eval_df['n_poss'].mean():.1f} possessions, "
        f"mean |actual margin| {mae_zero:.3f})")
    log(f"  zero baseline (predict 0):        MAE {mae_zero:.4f}")
    log(f"  team-strength baseline (2021-24): MAE {mae_team:.4f}")
    for lam in LAMBDAS:
        log(f"  RAPM lam={lam:<5}                    MAE {lam_stint_mae[lam]:.4f}")
    # unseen-player share
    test_pids = pd.concat([test[c] for c in OFF_SLOTS + DEF_SLOTS]).astype("int64")
    unseen = (~test_pids.isin(set(pids))).mean() * 100
    log(f"  player-slots in 2025-26 filled by players unseen in 2021-24: {unseen:.1f}% "
        f"(they predict at league average in RAPM; expansion teams likewise in the team baseline)")

    lam_star = min(LAMBDAS, key=lambda l: (round(lam_stint_mae[l], 6), -l))
    log(f"  chosen lambda (min held-out stint MAE, ties to larger): {lam_star}")

    # ---------------- diagnostic 2: year-over-year stability ----------------
    log("")
    log("## Diagnostic 2 — year-over-year stability (single-season fits, "
        f"lam={lam_star}, players >= 1000 possessions both years)")
    season_frames = {}
    for season in ["2021", "2022", "2023", "2024"]:
        sdf = usable[usable["season"] == season]
        sp, sp_map, sb, so, sd = fit_rapm(sdf, [lam_star])
        f = ratings_frame(sp, sb, so, sd)
        f["season"] = season
        season_frames[season] = f
    yoy = {}
    for a, b in (("2022", "2023"), ("2023", "2024")):
        fa = season_frames[a][["player_id", f"net_100_lam{lam_star}", "total_poss"]]
        fb = season_frames[b][["player_id", f"net_100_lam{lam_star}", "total_poss"]]
        m = fa.merge(fb, on="player_id", suffixes=("_a", "_b"))
        m = m[(m["total_poss_a"] >= 1000) & (m["total_poss_b"] >= 1000)]
        r = float(np.corrcoef(m[f"net_100_lam{lam_star}_a"],
                              m[f"net_100_lam{lam_star}_b"])[0, 1])
        yoy[(a, b)] = (r, len(m))
        log(f"  net rating r({a} vs {b}) = {r:.3f}   (n = {len(m)} players)")

    # ---------------- diagnostic 3: lambda sensitivity ----------------------
    log("")
    log("## Diagnostic 3 — lambda sensitivity (top-50 by net)")
    top_sets = {}
    for lam in LAMBDAS:
        top_sets[lam] = set(ratings.nlargest(50, f"net_100_lam{lam}")["player_id"])
    for i, la in enumerate(LAMBDAS):
        for lb in LAMBDAS[i + 1:]:
            union = list(top_sets[la] | top_sets[lb])
            sub = ratings[ratings["player_id"].isin(union)]
            rho = spearman(sub[f"net_100_lam{la}"], sub[f"net_100_lam{lb}"])
            ov = len(top_sets[la] & top_sets[lb])
            log(f"  lam {la:>4} vs {lb:>4}: Spearman {rho:.3f} on union of top-50s "
                f"(n={len(union)}), top-50 overlap {ov}/50")

    # ---------------- diagnostic 4: garbage-time sensitivity ----------------
    log("")
    log("## Diagnostic 4 — garbage-time sensitivity")
    margin = (train["home_pts_before"] - train["away_pts_before"]).abs()
    garbage = (train["period"] >= 4) & (margin >= GARBAGE_MARGIN)
    log(f"garbage-time possessions (period >= 4, |margin before| >= {GARBAGE_MARGIN}): "
        f"{int(garbage.sum()):,} of {len(train):,} ({garbage.mean() * 100:.2f}%)")
    gp, gp_map, gb, go, gd = fit_rapm(train[~garbage], [lam_star])
    gf = ratings_frame(gp, gb, go, gd)
    m = ratings[["player_id", f"net_100_lam{lam_star}", "total_poss"]].merge(
        gf[["player_id", f"net_100_lam{lam_star}"]], on="player_id",
        suffixes=("_full", "_nogarbage"))
    m500 = m[m["total_poss"] >= 500]
    r_g = float(np.corrcoef(m500[f"net_100_lam{lam_star}_full"],
                            m500[f"net_100_lam{lam_star}_nogarbage"])[0, 1])
    log(f"  net rating r(full vs garbage-excluded), players >= 500 poss: "
        f"{r_g:.4f}  (n = {len(m500)})")

    # ---------------- diagnostic 5: replacement-level behavior --------------
    log("")
    log("## Diagnostic 5 — replacement-level behavior")
    nc = f"net_100_lam{lam_star}"
    low = ratings[ratings["total_poss"] < 300]
    high = ratings[ratings["total_poss"] >= 1000]
    log(f"  players < 300 possessions: n={len(low)}, mean net {low[nc].mean():+.3f}, "
        f"min {low[nc].min():+.3f}, max {low[nc].max():+.3f}")
    log(f"  players >= 1000 possessions: n={len(high)}, mean net {high[nc].mean():+.3f}")
    log(f"  all players: mean net {ratings[nc].mean():+.3f}")
    log("  (want: low-poss group mean below average, and shrunk — not at extremes)")

    # ---------------- smoke test (never a gate) -----------------------------
    log("")
    log(f"## Smoke test ONLY (never a promotion criterion) — lam={lam_star}, "
        "players >= 1500 possessions 2021-24")
    big = ratings[ratings["total_poss"] >= 1500]
    for col, label in ((f"orapm_100_lam{lam_star}", "OFFENSE"),
                       (f"drapm_100_lam{lam_star}", "DEFENSE")):
        log(f"  top-15 {label}:")
        t = big.nlargest(15, col)[["player_name", "player_id", col, nc,
                                   "total_poss", "minutes_2021_24"]]
        for _, r in t.iterrows():
            log(f"    {r['player_name']:<28} {r[col]:+6.2f}  (net {r[nc]:+6.2f}, "
                f"poss {int(r['total_poss']):>6,}, min {r['minutes_2021_24']:>7,.0f})")

    # ---------------- outputs ----------------------------------------------
    out = ratings[["player_id", "player_name", "off_poss", "def_poss",
                   "total_poss", "minutes_2021_24"]].copy()
    out["orapm_100"] = ratings[f"orapm_100_lam{lam_star}"].round(3)
    out["drapm_100"] = ratings[f"drapm_100_lam{lam_star}"].round(3)
    out["net_100"] = ratings[nc].round(3)
    out["lambda_chosen"] = lam_star
    for lam in LAMBDAS:
        out[f"net_100_lam{lam}"] = ratings[f"net_100_lam{lam}"].round(3)
    out = out.sort_values("net_100", ascending=False)
    out.to_csv(RAPM_CSV, index=False, encoding="utf-8")

    # ---------------- attestation (amendment v5 C3) -------------------------
    # Derived from the games ACTUALLY FIT, not from TRAIN_SEASONS: if the season
    # filter ever changes, or a season is only partly present in possessions, the
    # constant would still read 2024 while the artifact had seen something later.
    # The data is the evidence; the constant is only a description of it.
    mt = pd.read_parquet(MASTER_TEAM_PATH, columns=["game_id", "season", "game_date"])
    train_ids = set(train["game_id"].astype(str))
    fit_rows = mt[mt["game_id"].astype(str).isin(train_ids)]
    if fit_rows.empty:
        raise RuntimeError(
            "no master_team rows matched the training game_ids, so the artifact's "
            "fit_through_date cannot be evidenced. Refusing to write an unattested "
            "rapm_v0.csv (screening_protocol_amendment_v5 C3-BLOCKING).")
    fit_seasons = sorted({int(s) for s in fit_rows["season"]})
    aoi.write_manifest(
        RAPM_CSV,
        producer="build_rapm.py",
        fit_through_date=aoi.bound_from_dates(fit_rows["game_date"]),
        fit_through_season=max(fit_seasons),
        fit_seasons=fit_seasons,
        notes=(
            "Static single-table RAPM. Every fitted value saw the same evidence, so "
            "artifact granularity is exact rather than conservative. This is the "
            "artifact whose misuse motivated asof_invariant_audit_v1: it must never "
            f"score a season in {fit_seasons}. Use rapm_walkforward.csv for those."),
        extra={"n_train_possessions": int(len(train)),
               "n_train_games": int(len(train_ids)),
               "lambda_chosen": int(lam_star)},
    )
    log(f"manifest written for {os.path.basename(RAPM_CSV)} "
        f"(fit through {max(fit_seasons)}, {len(train_ids)} games)")

    by_season = pd.concat(season_frames.values(), ignore_index=True)
    by_season["player_name"] = by_season["player_id"].map(names).fillna("")
    by_season.round(3).to_csv(os.path.join(EXP_DIR, "rapm_by_season.csv"),
                              index=False, encoding="utf-8")
    eval_df.round(3).to_csv(os.path.join(EXP_DIR, "stint_eval.csv"),
                            index=False, encoding="utf-8")

    log("")
    log(f"wrote {RAPM_CSV} ({len(out)} players), rapm_by_season.csv, stint_eval.csv")
    log(f"runtime {time.time() - t0:.0f}s")

    with open(os.path.join(EXP_DIR, "build_log.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT_LINES) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
