"""
build_rapm_walkforward.py
=========================
RAPM walk-forward — season-by-season refit of the v0 model so player values can
enter downstream experiments without look-ahead contamination.

Preregistered experiment: ``build_rapm_walkforward_v1`` (experiments/registry.jsonl,
registered 2026-07-31T15:58:28Z, regime A, primary metric ``stint_mae_walkforward``,
incumbent ``rapm_v0_static_2021_2024``). INFRASTRUCTURE PREREQUISITE — no promotion
claim. The registration is BLOCKING: "no experiment may consume fitted player values
on a scored season inside the fit window until this lands." Acceptance is governed by
``asof_invariant_audit_v1`` (C). This script does not touch the registry, the
leaderboards, `data/rapm/rapm_v0.csv`, or `build_rapm.py`.

The defect this remediates
--------------------------
`data/rapm/rapm_v0.csv` is a SINGLE STATIC table fit on TRAIN_SEASONS =
{2021, 2022, 2023, 2024} (build_rapm.py:74), and every consumer joins it by
player_id with no season key. Both registered consumers scored 2024 as a test
season using values fit on those same 2024 possessions. The leakage is
established by DATA LINEAGE, not by any correlation pattern.

Committed consequences already on the ledger (see the errata under
oracle_availability_bracket_v2, runs 3 and 4):
  joint_differential_v1  pooled +0.2439 contaminated vs +0.0219 clean — the
                         apparent gain was 2024 leakage; recorded FAIL.
  oracle_..._bracket_v2  deployable v2 REVERSES (+5.3% -> -4.2% of market gap);
                         achievable pregame ceiling FALLS (15.6% -> 12.6%);
                         omniscient v4 rose (18.2% -> 36.3%) but is regime-C
                         diagnostic and must NOT be cited as achievable. The
                         first erratum's "worth twice what we credited" reading
                         was RETRACTED. Verdict FAIL either way.

Run 4 also withdrew the "roster turnover does not decay like that" phrasing and
queued "a direct contaminated-vs-walk-forward comparison on identical
observations" under THIS experiment as the decisive test. Section 3 delivers it.

What this builds
----------------
One RAPM fit per EMIT SEASON s, trained on possessions from seasons STRICTLY
BEFORE s (expanding window), emitted as a per-(season, player) long table.
A consumer joins on (season, player_id) instead of player_id alone.

  emit s   train window   fit_through_season   inner lambda-validation season
  2022     2021           2021                 (none — thin-history caveat)
  2023     2021-2022      2022                 2022
  2024     2021-2023      2023                 2023
  2025     2021-2024      2024                 2024
  2026     2021-2025      2025                 2025

2021 has no prior data and is excluded from the table entirely, per the
registration.

Protocol identity
-----------------
Imports build_rapm (v0) UNMODIFIED and reuses its design matrix, gram, ridge
solver, stint construction, and team baseline. Only the training window, the
lambda-selection protocol, and the output schema change. Two hard gates:

  gate 1  the emit-2025 block (train window 2021-2024 == v0's TRAIN_SEASONS)
          must reproduce rapm_v0.csv's net_100_lam{500..5000} to < 0.005.
  gate 2  the global-player-space gram must equal v0's per-window gram on the
          shared columns. Fits use one global player index (all players
          2021-2026) so per-season grams are ADDITIVE and every expanding
          window is a cheap sum; players with zero possessions in a window
          decouple and solve to exactly 0 (v0's unseen-player convention) and
          are not emitted.

Lambda selection
----------------
v0 picks lambda on 2025-2026 stint MAE — future data relative to every emit
season here, so inheriting it would re-import the look-ahead through the
hyperparameter. Instead lambda is chosen per season on an INNER walk-forward
split strictly inside the training window (fit seasons < s-1, score stint MAE
on s-1), using v0's argmin rule verbatim (ties to the larger lambda). Emit 2022
has a one-season window and no inner split; it falls back to the largest grid
value — an a-priori "most shrinkage when there is least data and no way to
validate" rule — and is flagged `lambda_source=fallback_max_grid`.

The registration specifies the EXTENDED sweep ("interior optimum near 68,000 on
the v0 protocol") re-selected per season, so that is the shipped default and it
drives `net_100`. Measured caveat, reported rather than acted on unilaterally:

  - the inner-validation curve is FLAT above ~5,000. The 2023 fold reads 2.1742
    at every lambda from 5,000 to 47,000; folds separate only in the 4th
    decimal. v0's tie-break rounds at 6 decimals, so it never fires, and the
    argmin lands at 33,000 / 47,000 / 68,000 by noise rather than at a real
    optimum.
  - that shrinkage costs the thing the table exists for. Held-out stint MAE
    improves 0.0008-0.0024, while the resulting feature's margin correlation
    FALLS (2025 +0.400 -> +0.310, 2026 +0.308 -> +0.227) and the p25
    replacement value collapses toward zero (-0.890 -> -0.189) — the values
    stop separating players.

Both protocols therefore ship in the same table and both are equally
uncontaminated (the choice is shrinkage/utility, never leakage):
  `net_100`         registered protocol — extended sweep, per-season selection
  `net_100_v0grid`  same fits, selection restricted to v0's {500..5000} grid
  `net_100_lam*`    same fits at fixed lambdas (rapm_v0 schema identity)
RECOMMENDATION to the orchestrator: amend the registration to the v0 grid, or
adopt `net_100_v0grid`. Not done unilaterally — the registration is binding and
acceptance belongs to asof_invariant_audit_v1.

Outputs
-------
  data/rapm/rapm_walkforward.csv          one row per (season, player); carries
                                          rapm_v0.csv's exact column set plus
                                          `season` / `fit_through_season`
  data/rapm/rapm_walkforward_seasons.csv  per-season manifest: fit window, the
                                          p25 replacement a consumer needs for
                                          players with no prior history, and
                                          the primary metric
  experiments/rapm_walkforward/{REPORT.md, consumer_audit.csv,
                                margin_corr_diagnostic.csv,
                                stint_eval_by_season.csv}

Run:  python build_rapm_walkforward.py
      python build_rapm_walkforward.py --lambdas 500,1000,2000,5000
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections import Counter

import numpy as np
import pandas as pd

import build_rapm as v0  # v0 protocol functions - file NOT modified

ROOT = os.path.dirname(os.path.abspath(__file__))
RAPM_DIR = os.path.join(ROOT, "data", "rapm")
EXP_DIR = os.path.join(ROOT, "experiments", "rapm_walkforward")
OUT_CSV = os.path.join(RAPM_DIR, "rapm_walkforward.csv")
OUT_SEASONS_CSV = os.path.join(RAPM_DIR, "rapm_walkforward_seasons.csv")
RAPM_V0_CSV = os.path.join(RAPM_DIR, "rapm_v0.csv")

EXPERIMENT_ID = "build_rapm_walkforward_v1"
SEASONS = ["2021", "2022", "2023", "2024", "2025", "2026"]
EMIT_SEASONS = ["2022", "2023", "2024", "2025", "2026"]  # 2021 has no prior data
V0_LAMBDAS = [500, 1000, 2000, 5000]                     # rapm_v0 schema columns
LAMBDAS_REGISTERED = [500, 1000, 2000, 3500, 5000, 7500, 11000, 16000, 23000,
                      33000, 47000, 68000, 100000]       # registration: extended sweep
V0_TRAIN_WINDOW = ["2021", "2022", "2023", "2024"]       # build_rapm.TRAIN_SEASONS
GATE_TOL = 0.005

# rapm_v0.csv's exact column set (schema-identity requirement in features_desc).
# `minutes_2021_24` keeps its v0 name for join compatibility but holds this
# row's TRAINING-WINDOW minutes — the build_rapm_v1.py precedent, documented.
V0_SCHEMA = ["player_id", "player_name", "off_poss", "def_poss", "total_poss",
             "minutes_2021_24", "orapm_100", "drapm_100", "net_100",
             "lambda_chosen"] + [f"net_100_lam{l}" for l in V0_LAMBDAS]

# ---------------------------------------------------------------------------
# consumer audit (features_desc: "Mandatory")
# Every reader of a fitted player-value table, its fit window, the seasons it
# scored, and whether they intersect. The scan is programmatic so a NEW consumer
# cannot slip in unnoticed; the verdicts are curated from committed artifacts.
# ---------------------------------------------------------------------------
CONSUMER_META = {
    "oracle_bracket.py": dict(
        experiment_id="oracle_availability_bracket_v2", regime="C",
        scored_seasons="2024,2025,2026",
        verdict="CONTAMINATED — ERRATUM + RETRACTION ON LEDGER",
        detail="2024 scored inside the fit window (207 of 627 games). Registered "
               "verdict was FAIL on gate1_pooled_improvement either way, so no "
               "promotion rests on it. Clean-season corrections (registry run 4): "
               "deployable v2 REVERSES +5.3%->-4.2% of market gap; achievable "
               "pregame ceiling FALLS 15.6%->12.6%; omniscient v4 rose "
               "18.2%->36.3% but is regime-C diagnostic and must not headline."),
    "joint_differential.py": dict(
        experiment_id="joint_differential_v1", regime="A",
        scored_seasons="2024,2025,2026",
        verdict="CONTAMINATED — RECORDED FAIL",
        detail="d_rapm built from rapm_v0 net_100. Pooled +0.2439 contaminated "
               "vs +0.0219 on clean seasons — the apparent gain was 2024 leakage. "
               "Ablation: the differential reframing carries +0.004 clean."),
    "build_rapm_v1.py": dict(
        experiment_id="(none)", regime="n/a", scored_seasons="(none scored)",
        verdict="CLEAN — no registry entry, no promotion claim",
        detail="Reads rapm_v0.csv only as a join-compatibility cross-check. "
               "Writes candidates to experiments/rapm_multiseason/, not data/rapm/."),
    "build_rapm.py": dict(
        experiment_id="(none)", regime="n/a", scored_seasons="(none scored)",
        verdict="PRODUCER of the contaminated table",
        detail="Fits TRAIN_SEASONS={2021,2022,2023,2024} and emits one static "
               "row per player. Left untouched by this experiment."),
    "build_rapm_walkforward.py": dict(
        experiment_id=EXPERIMENT_ID, regime="A", scored_seasons="(none scored)",
        verdict="CLEAN — this script",
        detail="Reads rapm_v0.csv only for gate 1 (reproduction check)."),
}
# Scored on 2024 but verified NOT to read any player-value rating table.
NON_CONSUMERS_NOTE = (
    "feature_lab.py, interactions_lab.py, crossseason_screen.py, "
    "volume_heterogeneity.py (player_feature_screen_v1, "
    "player_feature_interactions_v1, player_vs_archetype_v1, "
    "player_feature_crossseason_v1, player_volume_heterogeneity_v1 — all "
    "regime A, all with *_delta_2024 primary metrics) validate on 2024 but read "
    "data/player_possession_features.parquet, NOT any RAPM table. Verified by "
    "repo-wide scan below: they do not appear. Clean with respect to THIS defect."
)

R: list[str] = []


def log(s: str = ""):
    print(s)
    R.append(s)


def scan_consumers() -> list:
    """Repo-root *.py files that read a rapm table. Programmatic so a new
    consumer cannot be added without this audit noticing."""
    pat = re.compile(r"rapm[_/]?v0\.csv|rapm[\"'/\\]+rapm")
    found = []
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".py"):
            continue
        try:
            with open(os.path.join(ROOT, fn), encoding="utf-8") as fh:
                if pat.search(fh.read()):
                    found.append(fn)
        except OSError:
            continue
    return found


# ---------------------------------------------------------------------------
# global-player-space fits (per-season grams are additive across windows)
# ---------------------------------------------------------------------------
def season_gram(df: pd.DataFrame, gmap: dict, U: int):
    C, y, home = v0.make_design(df, gmap, U)
    return v0.gram(C, y, home, 2 + 2 * U)


def window_gram(grams: dict, seasons: list):
    return (sum(grams[s][0] for s in seasons), sum(grams[s][1] for s in seasons))


def net100(beta: np.ndarray, U: int) -> np.ndarray:
    return 100.0 * beta[2:2 + U] - 100.0 * beta[2 + U:2 + 2 * U]


# ---------------------------------------------------------------------------
# stint evaluation (v0.build_stints, global-space prediction)
# ---------------------------------------------------------------------------
class Bundle:
    """Pre-indexed stint structure for one season; reused across lambdas."""

    def __init__(self, df: pd.DataFrame, gmap: dict):
        sdf = v0.build_stints(df)
        _, self.codes = np.unique(sdf["stint_id"].to_numpy(), return_inverse=True)
        self.n = int(self.codes.max()) + 1
        self.sign = np.where(sdf["is_home_offense"].to_numpy() == 1, 1.0, -1.0)
        self.is_home = sdf["is_home_offense"].to_numpy(dtype=float)
        self.actual = np.zeros(self.n)
        np.add.at(self.actual, self.codes,
                  self.sign * sdf["points_scored"].to_numpy(dtype=float))
        self.off_idx = np.stack([sdf[c].astype("int64").map(gmap).to_numpy(np.int64)
                                 for c in v0.OFF_SLOTS])
        self.def_idx = np.stack([sdf[c].astype("int64").map(gmap).to_numpy(np.int64)
                                 for c in v0.DEF_SLOTS])
        self.df = sdf

    def stint_mae(self, beta: np.ndarray, U: int) -> float:
        pred = (beta[0] + beta[1] * self.is_home
                + beta[2:2 + U][self.off_idx].sum(axis=0)
                + beta[2 + U:2 + 2 * U][self.def_idx].sum(axis=0))
        marg = np.zeros(self.n)
        np.add.at(marg, self.codes, self.sign * pred)
        return float(np.abs(marg - self.actual).mean())

    def team_mae(self, tb: dict) -> float:
        pp = v0.predict_possessions_team(self.df, tb)
        marg = np.zeros(self.n)
        np.add.at(marg, self.codes, self.sign * pp)
        return float(np.abs(marg - self.actual).mean())

    def zero_mae(self) -> float:
        return float(np.abs(self.actual).mean())


# ---------------------------------------------------------------------------
# margin diagnostic (the comparison run 4 queued under this experiment)
# ---------------------------------------------------------------------------
def game_team_weights(usable: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for cols, team_col in ((v0.OFF_SLOTS, "offense_team_id"),
                           (v0.DEF_SLOTS, "defense_team_id")):
        for c in cols:
            parts.append(usable[["game_id", team_col, c]]
                         .rename(columns={team_col: "team_id", c: "player_id"}))
    allp = pd.concat(parts, ignore_index=True)
    allp["player_id"] = allp["player_id"].astype("int64")
    return (allp.groupby(["game_id", "team_id", "player_id"], as_index=False)
            .size().rename(columns={"size": "w"}))


def margin_corr(gw: pd.DataFrame, games: pd.DataFrame, val_map: dict,
                replacement: float) -> "tuple[float, int]":
    v = gw.copy()
    v["val"] = v["player_id"].map(val_map).fillna(replacement)
    v["wv"] = v["w"] * v["val"]
    agg = v.groupby(["game_id", "team_id"], as_index=False).agg(
        wv=("wv", "sum"), w=("w", "sum"))
    agg["team_val"] = agg["wv"] / agg["w"]
    tv = agg[["game_id", "team_id", "team_val"]]
    m = (games.merge(tv, left_on=["game_id", "home_team_id"],
                     right_on=["game_id", "team_id"], how="inner")
         .rename(columns={"team_val": "home_val"}).drop(columns=["team_id"])
         .merge(tv, left_on=["game_id", "away_team_id"],
                right_on=["game_id", "team_id"], how="inner")
         .rename(columns={"team_val": "away_val"}).drop(columns=["team_id"]))
    if len(m) < 3:
        return float("nan"), len(m)
    return float(np.corrcoef(m["home_val"] - m["away_val"], m["margin"])[0, 1]), len(m)


def build_games(usable: pd.DataFrame) -> pd.DataFrame:
    home = (usable.loc[usable["is_home_offense"] == 1, ["game_id", "offense_team_id"]]
            .drop_duplicates("game_id")
            .rename(columns={"offense_team_id": "home_team_id"}))
    away = (usable.loc[usable["is_home_offense"] == 0, ["game_id", "offense_team_id"]]
            .drop_duplicates("game_id")
            .rename(columns={"offense_team_id": "away_team_id"}))
    seas = usable[["game_id", "season"]].drop_duplicates("game_id")
    g = home.merge(away, on="game_id").merge(seas, on="game_id")
    mt = pd.read_parquet(v0.MASTER_TEAM_PATH, columns=["game_id", "team_id", "pts"])
    mt["game_id"] = mt["game_id"].astype(str).str.zfill(10)
    g = (g.merge(mt.rename(columns={"team_id": "home_team_id", "pts": "home_pts"}),
                 on=["game_id", "home_team_id"], how="inner")
         .merge(mt.rename(columns={"team_id": "away_team_id", "pts": "away_pts"}),
                on=["game_id", "away_team_id"], how="inner"))
    g["margin"] = g["home_pts"] - g["away_pts"]
    return g


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lambdas", default=",".join(str(x) for x in LAMBDAS_REGISTERED),
                    help="ridge grid (possession-equivalent units). Default is the "
                         "registered extended sweep.")
    args = ap.parse_args()
    lambdas = sorted({int(x) for x in args.lambdas.split(",") if x.strip()}
                     | set(V0_LAMBDAS))   # v0 lambdas always present (gate 1 + schema)
    v0grid = [l for l in lambdas if l in set(V0_LAMBDAS)]

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    t0 = time.time()
    os.makedirs(RAPM_DIR, exist_ok=True)
    os.makedirs(EXP_DIR, exist_ok=True)

    log(f"# RAPM walk-forward (`{EXPERIMENT_ID}`) — build log "
        + time.strftime("%Y-%m-%d %H:%M"))
    log("")
    log("*Regime A, INFRASTRUCTURE PREREQUISITE — no promotion claim. Registration is*")
    log("*BLOCKING; acceptance is governed by `asof_invariant_audit_v1` (C). This script*")
    log("*does not touch the registry, the leaderboards, `data/rapm/rapm_v0.csv`, or*")
    log("*`build_rapm.py`.*")
    log("")

    # ---------------- data (v0-identical filter) ---------------------------
    poss = pd.read_parquet(v0.POSS_PATH)
    usable = poss[(poss["end_reason"] != "technical_ft")
                  & (poss["n_off_oncourt"] == 5)
                  & (poss["n_def_oncourt"] == 5)].copy()
    log("## 0. Data (v0 filter: non-technical, full 5v5)")
    log(f"- possessions {len(poss):,} -> usable {len(usable):,} "
        f"({len(usable)/len(poss)*100:.2f}%)")
    seas_df = {s: usable[usable["season"] == s].copy() for s in SEASONS}
    for s in SEASONS:
        log(f"  - {s}: {len(seas_df[s]):,} possessions, "
            f"{seas_df[s]['game_id'].nunique():,} games")

    all_pids = sorted(set(pd.concat([usable[c] for c in v0.OFF_SLOTS + v0.DEF_SLOTS])
                          .astype("int64")))
    gmap = {p: i for i, p in enumerate(all_pids)}
    U = len(all_pids)
    log(f"- global player space 2021-2026: {U} players (design dim {2 + 2 * U})")
    log(f"- lambda grid (registered extended sweep): {lambdas}")

    seas_off, seas_def = {}, {}
    for s in SEASONS:
        oc, dc = Counter(), Counter()
        for c in v0.OFF_SLOTS:
            oc.update(seas_df[s][c].astype("int64").tolist())
        for c in v0.DEF_SLOTS:
            dc.update(seas_df[s][c].astype("int64").tolist())
        seas_off[s], seas_def[s] = oc, dc

    # ---------------- per-season grams (additive across windows) ------------
    tg = time.time()
    grams = {s: season_gram(seas_df[s], gmap, U) for s in SEASONS}
    log(f"- per-season grams built in {time.time() - tg:.0f}s "
        f"(every window is a sum of these)")

    sub = seas_df["2021"]
    loc_pids = sorted(set(pd.concat([sub[c] for c in v0.OFF_SLOTS + v0.DEF_SLOTS])
                          .astype("int64")))
    loc_map = {p: i for i, p in enumerate(loc_pids)}
    Pl = len(loc_pids)
    Cl, yl, hl = v0.make_design(sub, loc_map, Pl)
    Gl, bl = v0.gram(Cl, yl, hl, 2 + 2 * Pl)
    sel = np.array([0, 1] + [2 + gmap[p] for p in loc_pids]
                   + [2 + U + gmap[p] for p in loc_pids])
    Gg, bg = grams["2021"]
    ok_g = np.allclose(Gl, Gg[np.ix_(sel, sel)]) and np.allclose(bl, bg[sel])
    log(f"- GATE 2 global-space gram identity (season 2021): "
        f"{'PASS' if ok_g else 'FAIL'}")
    if not ok_g:
        raise RuntimeError("global-space gram != v0 per-window gram")

    bundles = {s: Bundle(seas_df[s], gmap) for s in SEASONS[1:]}

    # ---------------- walk-forward loop ------------------------------------
    log("")
    log("## 1. Walk-forward fits — emit season s trained on seasons < s")
    log("")
    log("Lambda is chosen per season on an INNER split strictly inside the training")
    log("window (fit seasons < s-1, score stint MAE on s-1), never on s or later, using")
    log("v0's argmin rule verbatim. Emit 2022 has a one-season window and no inner")
    log("split; it falls back to the largest grid value (thin-history caveat, flagged).")
    log("")
    log("`net_100` follows the REGISTERED extended sweep. `net_100_v0grid` is the same")
    log("fit with selection restricted to v0's {500..5000}. Both are equally")
    log("uncontaminated — see section 5 for why the default is contested.")
    log("")

    rows, season_meta, stint_rows = [], [], []

    for s in EMIT_SEASONS:
        train_ss = [x for x in SEASONS if x < s]
        fit_through = train_ss[-1]
        G, b = window_gram(grams, train_ss)
        betas = {lam: v0.solve_ridge(G, b, lam) for lam in lambdas}

        inner_val = train_ss[-1] if len(train_ss) >= 2 else None
        if inner_val is not None:
            Gi, bi = window_gram(grams, train_ss[:-1])
            bu = bundles[inner_val]
            inner_mae = {lam: bu.stint_mae(v0.solve_ridge(Gi, bi, lam), U)
                         for lam in lambdas}
            pick = lambda grid: min(grid, key=lambda l: (round(inner_mae[l], 6), -l))
            lam_star, lam_v0 = pick(lambdas), pick(v0grid)
            lam_src = "inner_validation"
            inner_star = inner_mae[lam_star]
        else:
            inner_mae = {}
            lam_star, lam_v0 = max(lambdas), max(v0grid)
            lam_src = "fallback_max_grid"
            inner_star = float("nan")

        beta = betas[lam_star]
        off_c, def_c = Counter(), Counter()
        for t in train_ss:
            off_c.update(seas_off[t])
            def_c.update(seas_def[t])
        seen = np.array([p for p in all_pids
                         if (off_c.get(p, 0) + def_c.get(p, 0)) > 0], dtype=np.int64)
        gidx = np.array([gmap[p] for p in seen])

        blk = pd.DataFrame({"season": s, "fit_through_season": fit_through,
                            "player_id": seen})
        blk["train_seasons"] = (f"{train_ss[0]}-{train_ss[-1]}"
                                if len(train_ss) > 1 else train_ss[0])
        blk["n_train_seasons"] = len(train_ss)
        blk["off_poss"] = [off_c.get(p, 0) for p in seen]
        blk["def_poss"] = [def_c.get(p, 0) for p in seen]
        blk["total_poss"] = blk["off_poss"] + blk["def_poss"]
        blk["orapm_100"] = np.round(100.0 * beta[2:2 + U][gidx], 3)
        blk["drapm_100"] = np.round(-100.0 * beta[2 + U:2 + 2 * U][gidx], 3)
        blk["net_100"] = np.round(blk["orapm_100"] + blk["drapm_100"], 3)
        blk["lambda_chosen"] = lam_star
        blk["lambda_source"] = lam_src
        blk["net_100_v0grid"] = np.round(net100(betas[lam_v0], U)[gidx], 3)
        blk["lambda_chosen_v0grid"] = lam_v0
        for lam in V0_LAMBDAS:
            blk[f"net_100_lam{lam}"] = np.round(net100(betas[lam], U)[gidx], 3)
        rows.append(blk)

        # primary metric: held-out stint MAE on season s, never trained on
        bu_s = bundles[s]
        tb = v0.team_baseline_tables(pd.concat([seas_df[t] for t in train_ss],
                                               ignore_index=True))
        mae_rapm = bu_s.stint_mae(beta, U)
        mae_v0g = bu_s.stint_mae(betas[lam_v0], U)
        mae_team, mae_zero = bu_s.team_mae(tb), bu_s.zero_mae()
        slots = pd.concat([seas_df[s][c] for c in v0.OFF_SLOTS + v0.DEF_SLOTS]
                          ).astype("int64")
        unseen = float((~slots.isin(set(seen.tolist()))).mean() * 100)
        stint_rows.append({"emit_season": s, "fit_through_season": fit_through,
                           "n_stints": bu_s.n, "lambda_chosen": lam_star,
                           "stint_mae_walkforward": mae_rapm,
                           "stint_mae_v0grid": mae_v0g,
                           "mae_team_baseline": mae_team, "mae_zero_baseline": mae_zero,
                           "unseen_slot_pct": unseen})

        p25 = float(blk["net_100"].quantile(0.25))
        season_meta.append({
            "season": s, "fit_through_season": fit_through,
            "train_seasons": blk["train_seasons"].iat[0], "n_train_seasons": len(train_ss),
            "n_train_possessions": int(sum(len(seas_df[t]) for t in train_ss)),
            "n_train_games": int(pd.concat([seas_df[t] for t in train_ss])
                                 ["game_id"].nunique()),
            "n_players": len(seen), "lambda_chosen": lam_star, "lambda_source": lam_src,
            "lambda_chosen_v0grid": lam_v0, "inner_val_season": inner_val or "none",
            "inner_val_stint_mae": round(inner_star, 6) if inner_star == inner_star else "",
            "replacement_net_100_p25": round(p25, 3),
            "replacement_net_100_v0grid_p25": round(
                float(blk["net_100_v0grid"].quantile(0.25)), 3),
            "sd_net_100": round(float(blk["net_100"].std()), 3),
            "sd_net_100_v0grid": round(float(blk["net_100_v0grid"].std()), 3),
            "stint_mae_walkforward": round(mae_rapm, 4),
            "unseen_slot_pct": round(unseen, 2),
            "thin_history_caveat": len(train_ss) < 2})

        log(f"- emit {s}: train {blk['train_seasons'].iat[0]} "
            f"({season_meta[-1]['n_train_possessions']:,} poss, {len(seen)} players), "
            f"fit_through {fit_through} | inner val {inner_val or '-'} -> "
            f"lambda {lam_star} ({lam_src}); v0-grid pick {lam_v0}")
        log(f"    stint_mae_walkforward on {s}: {mae_rapm:.4f} "
            f"(v0-grid {mae_v0g:.4f}) vs team baseline {mae_team:.4f} vs zero "
            f"{mae_zero:.4f}; {unseen:.1f}% of {s} slots have no prior history "
            f"(p25 replacement {p25:+.3f})")

    wf = pd.concat(rows, ignore_index=True).sort_values(
        ["season", "net_100"], ascending=[True, False])
    meta = pd.DataFrame(season_meta)

    # ---------------- gate 1: reproduce v0 on the identical window ----------
    log("")
    log("## 2. GATE 1 — emit-2025 block reproduces rapm_v0.csv")
    log("Emit season 2025 trains on 2021-2024, exactly build_rapm.py's TRAIN_SEASONS.")
    log("Same window + same lambdas + same estimator must give the same coefficients.")
    v0csv = pd.read_csv(RAPM_V0_CSV)
    blk25 = wf[wf["season"] == "2025"]
    mrg = blk25.merge(v0csv, on="player_id", suffixes=("_wf", "_v0"))
    max_diff = max(float((mrg[f"net_100_lam{l}_wf"]
                          - mrg[f"net_100_lam{l}_v0"]).abs().max()) for l in V0_LAMBDAS)
    ok1 = max_diff < GATE_TOL
    log(f"- joined {len(mrg)} players; max |diff| on net_100_lam{V0_LAMBDAS} = "
        f"{max_diff:.6f} -> {'PASS' if ok1 else 'FAIL'}")
    if not ok1:
        raise RuntimeError(f"emit-2025 block disagrees with rapm_v0.csv ({max_diff})")

    # ---------------- the comparison run 4 queued ---------------------------
    log("")
    log("## 3. Contaminated vs walk-forward on identical observations")
    log("")
    log("Registry run 4 withdrew the phrase *roster turnover does not decay like that*")
    log("and queued **a direct contaminated-vs-walk-forward comparison on identical")
    log("observations** under this experiment as the decisive test. This is it.")
    log("")
    log("Per season: corr(possession-weighted team player-value differential, realized")
    log("margin). Same games, same weights, same replacement convention (each table's")
    log("own p25) — the ONLY thing that differs is which value table is joined.")
    log("")
    log("*Read as a CONTAMINATION diagnostic, not a forecast. Weights come from")
    log("realized on-court possessions, so neither arm is a pregame feature and no")
    log("number here is a skill estimate. Per registry run 4 the leakage is already")
    log("established by DATA LINEAGE; this quantifies its size on matched data.*")
    log("")
    gw = game_team_weights(usable)
    games = build_games(usable)
    v0_map = dict(zip(v0csv["player_id"].astype("int64"), v0csv["net_100"]))
    v0_repl = float(v0csv["net_100"].quantile(0.25))

    diag_rows = []
    for s in EMIT_SEASONS:
        gs = games[games["season"] == s]
        gws = gw[gw["game_id"].isin(set(gs["game_id"]))]
        blk = wf[wf["season"] == s]
        wf_map = dict(zip(blk["player_id"].astype("int64"), blk["net_100"]))
        wf_repl = float(meta.loc[meta["season"] == s, "replacement_net_100_p25"].iat[0])
        g_map = dict(zip(blk["player_id"].astype("int64"), blk["net_100_v0grid"]))
        g_repl = float(blk["net_100_v0grid"].quantile(0.25))
        f_map = dict(zip(blk["player_id"].astype("int64"), blk["net_100_lam5000"]))
        f_repl = float(blk["net_100_lam5000"].quantile(0.25))
        r_v0, _ = margin_corr(gws, gs, v0_map, v0_repl)
        r_wf, n_g = margin_corr(gws, gs, wf_map, wf_repl)
        r_g, _ = margin_corr(gws, gs, g_map, g_repl)
        r_f, _ = margin_corr(gws, gs, f_map, f_repl)
        diag_rows.append({"season": s, "n_games": n_g,
                          "season_inside_v0_fit_window": s in set(V0_TRAIN_WINDOW),
                          "corr_static_rapm_v0": round(r_v0, 4),
                          "corr_walkforward_lam5000_fixed": round(r_f, 4),
                          "corr_walkforward_registered": round(r_wf, 4),
                          "corr_walkforward_v0grid": round(r_g, 4),
                          "v0_rated_share_pct": round(
                              float(gws["player_id"].isin(v0_map).mean() * 100), 1),
                          "wf_rated_share_pct": round(
                              float(gws["player_id"].isin(wf_map).mean() * 100), 1)})
    diag = pd.DataFrame(diag_rows)

    log("The primary contrast is the FIXED-lambda column, because both arms then hold")
    log("lambda at 5,000 and the only difference left is the fit window. The two")
    log("selection arms vary lambda by season, so their cross-season shape mixes")
    log("shrinkage changes with the window change and is shown for completeness only.")
    log("")
    log("| season | in v0 fit window | static rapm_v0 | **wf lam5000 (fixed)** | "
        "wf `net_100` (registered) | wf `net_100_v0grid` | rated share v0 | "
        "rated share wf |")
    log("|---|---|---|---|---|---|---|---|")
    for _, r_ in diag.iterrows():
        log(f"| {r_['season']} | {'YES' if r_['season_inside_v0_fit_window'] else 'no'} "
            f"| {r_['corr_static_rapm_v0']:+.3f} "
            f"| **{r_['corr_walkforward_lam5000_fixed']:+.3f}** "
            f"| {r_['corr_walkforward_registered']:+.3f} "
            f"| {r_['corr_walkforward_v0grid']:+.3f} "
            f"| {r_['v0_rated_share_pct']:.1f}% | {r_['wf_rated_share_pct']:.1f}% |")
    log("")
    d = diag.set_index("season")
    log(f"- On the fixed-lambda contrast the static arm breaks at its fit-window edge: "
        f"{d.loc['2024', 'corr_static_rapm_v0']:+.3f} (2024, in-window) -> "
        f"{d.loc['2025', 'corr_static_rapm_v0']:+.3f} -> "
        f"{d.loc['2026', 'corr_static_rapm_v0']:+.3f}, while the walk-forward arm runs "
        f"{d.loc['2024', 'corr_walkforward_lam5000_fixed']:+.3f} -> "
        f"{d.loc['2025', 'corr_walkforward_lam5000_fixed']:+.3f} -> "
        f"{d.loc['2026', 'corr_walkforward_lam5000_fixed']:+.3f} with no break at the "
        f"boundary.")
    log("- CONTROLLED READ, 2025: the walk-forward window for 2025 IS 2021-2024, so at")
    log("  fixed lambda the two arms are the SAME table on the SAME player set — equal")
    log("  coverage, equal correlation, as the row shows. That row is a harness check,")
    log("  not evidence. 2026 is the clean comparison, and there walk-forward is higher")
    log("  on both correlation and coverage.")
    log("- CONFOUND, stated plainly: on 2022-2024 the arms do not have equal coverage.")
    log("  rapm_v0 rates ~100% of those slots precisely BECAUSE it was fit on them,")
    log("  while a walk-forward table has no value for a player with no prior history")
    log("  and falls back to p25. Lower coverage attenuates correlation on its own, so")
    log("  part of the 2022-2024 gap is coverage, not look-ahead.")
    log("- The registered arm declines across seasons partly because its selected")
    log("  lambda climbs (2,000 -> 47,000 -> 68,000). That is the shrinkage effect of")
    log("  section 5, NOT contamination — which is exactly why the fixed-lambda column")
    log("  is the one to read here.")
    log("- This diagnostic sizes the defect; it does not re-run any affected")
    log("  experiment. Re-running joint_differential_v1 and oracle_..._bracket_v2 on")
    log("  clean values is their own registered work, not this build's to claim.")

    # ---------------- lambda protocol evidence ------------------------------
    log("")
    log("## 4. Stability of consecutive emit seasons")
    log("Consecutive tables share all but one season of training data, so this r is")
    log("largely mechanical persistence — the operational number for a rating")
    log("re-shipped each season, NOT an independent-signal YoY.")
    for a, b_ in zip(EMIT_SEASONS[:-1], EMIT_SEASONS[1:]):
        fa = wf[wf["season"] == a][["player_id", "net_100", "total_poss"]]
        fb = wf[wf["season"] == b_][["player_id", "net_100", "total_poss"]]
        m = fa.merge(fb, on="player_id", suffixes=("_a", "_b"))
        m = m[(m["total_poss_a"] >= 1000) & (m["total_poss_b"] >= 1000)]
        if len(m) >= 3:
            r_ = float(np.corrcoef(m["net_100_a"], m["net_100_b"])[0, 1])
            log(f"- r({a} vs {b_}) = {r_:.3f}  (n={len(m)} players >= 1000 poss both)")

    log("")
    log("## 5. Lambda protocol — registered default vs measured recommendation")
    log("")
    log("The registration specifies the extended sweep re-selected per season, so it")
    log("drives `net_100`. Reporting the measurement rather than acting on it")
    log("unilaterally, because the registration is binding and acceptance belongs to")
    log("`asof_invariant_audit_v1`:")
    log("")
    log("| season | registered lambda | v0-grid lambda | sd net_100 | sd v0grid | "
        "p25 repl | p25 repl v0grid |")
    log("|---|---|---|---|---|---|---|")
    for _, r_ in meta.iterrows():
        log(f"| {r_['season']} | {r_['lambda_chosen']:,} | {r_['lambda_chosen_v0grid']:,} "
            f"| {r_['sd_net_100']:.2f} | {r_['sd_net_100_v0grid']:.2f} "
            f"| {r_['replacement_net_100_p25']:+.3f} "
            f"| {r_['replacement_net_100_v0grid_p25']:+.3f} |")
    log("")
    log("- The inner-validation curve is FLAT above ~5,000 (the 2023 fold reads 2.1742")
    log("  at every lambda from 5,000 to 47,000; folds separate in the 4th decimal).")
    log("  v0's tie-break rounds at 6 decimals so it never fires, and the argmin lands")
    log("  high by noise rather than at a real optimum.")
    log("- The extra shrinkage buys 0.0008-0.0024 stint MAE and costs the separation")
    log("  the table exists to provide: margin correlation falls and the p25")
    log("  replacement collapses toward zero (see the table above and section 3).")
    log("- RECOMMENDATION: amend the registration to v0's grid, or have consumers read")
    log("  `net_100_v0grid`. Both columns are equally uncontaminated — this is a")
    log("  shrinkage/utility question, never a leakage one.")

    # ---------------- mandatory consumer audit ------------------------------
    log("")
    log("## 6. Consumer audit (mandatory per the registration)")
    log("")
    log("Every repo-root module that reads a fitted player-value table, its fit window,")
    log("the seasons it scored, and whether they intersect. The scan is programmatic so")
    log("a new consumer cannot be added without this audit noticing; verdicts are")
    log("curated from committed artifacts.")
    log("")
    scanned = scan_consumers()
    unknown = [f for f in scanned if f not in CONSUMER_META]
    if unknown:
        raise RuntimeError(
            f"consumer audit: unregistered reader(s) of a rapm table: {unknown}. "
            f"Add them to CONSUMER_META with a verdict before shipping.")
    audit_rows = []
    for fn in scanned:
        m_ = CONSUMER_META[fn]
        scored = m_["scored_seasons"]
        inter = sorted(set(scored.split(",")) & set(V0_TRAIN_WINDOW))
        audit_rows.append({
            "consumer": fn, "experiment_id": m_["experiment_id"], "regime": m_["regime"],
            "table_read": "data/rapm/rapm_v0.csv", "table_fit_window": "2021-2024",
            "scored_seasons": scored,
            "intersection_with_fit_window": ",".join(inter) or "(none)",
            "intersects": bool(inter), "verdict": m_["verdict"], "detail": m_["detail"]})
    audit = pd.DataFrame(audit_rows)
    audit.to_csv(os.path.join(EXP_DIR, "consumer_audit.csv"), index=False,
                 encoding="utf-8")
    log("| consumer | experiment | regime | scored | in fit window | verdict |")
    log("|---|---|---|---|---|---|")
    for _, r_ in audit.iterrows():
        log(f"| `{r_['consumer']}` | {r_['experiment_id']} | {r_['regime']} "
            f"| {r_['scored_seasons']} | {r_['intersection_with_fit_window']} "
            f"| {r_['verdict']} |")
    log("")
    for _, r_ in audit[audit["intersects"]].iterrows():
        log(f"- **{r_['consumer']}** — {r_['detail']}")
    log("")
    log(f"- NOT consumers: {NON_CONSUMERS_NOTE}")
    log("")
    log("- Scope limit, stated: this scan covers repo-root `*.py` reading a RAPM table.")
    log("  The full multi-artifact blast radius (zone maps, calibration params, frozen")
    log("  baselines, EB shrinkage constants) is deliverable (A) of")
    log("  `asof_invariant_audit_v1`, not this build.")

    # ---------------- names, schema, write ----------------------------------
    st = pd.read_parquet(v0.STINTS_PATH,
                         columns=["GAME_ID", "PLAYER_ID", "PLAYER_NAME", "stint_sec"])
    st["season"] = "20" + st["GAME_ID"].str[3:5]
    names = (st.groupby("PLAYER_ID")["PLAYER_NAME"]
             .agg(lambda x: x.mode().iat[0] if len(x.mode()) else ""))
    mins = st.groupby(["season", "PLAYER_ID"])["stint_sec"].sum() / 60.0
    cum = {s: mins[mins.index.get_level_values("season")
                   .isin([t for t in SEASONS if t < s])]
           .groupby(level="PLAYER_ID").sum() for s in EMIT_SEASONS}
    wf["player_name"] = wf["player_id"].map(names).fillna("")
    wf["minutes_2021_24"] = [round(float(cum[s].get(p, 0.0)), 1)
                             for s, p in zip(wf["season"], wf["player_id"])]

    wf = wf[["season", "fit_through_season"] + V0_SCHEMA
            + ["train_seasons", "n_train_seasons", "lambda_source",
               "net_100_v0grid", "lambda_chosen_v0grid"]]
    assert not wf.duplicated(["season", "player_id"]).any(), "duplicate (season, player)"
    assert set(V0_SCHEMA).issubset(wf.columns), "rapm_v0 schema identity broken"
    wf.to_csv(OUT_CSV, index=False, encoding="utf-8")
    meta.to_csv(OUT_SEASONS_CSV, index=False, encoding="utf-8")
    diag.to_csv(os.path.join(EXP_DIR, "margin_corr_diagnostic.csv"), index=False,
                encoding="utf-8")
    pd.DataFrame(stint_rows).round(4).to_csv(
        os.path.join(EXP_DIR, "stint_eval_by_season.csv"), index=False, encoding="utf-8")

    # ---------------- consumer note ----------------------------------------
    log("")
    log("## 7. How to consume")
    log("")
    log("```python")
    log("wf = pd.read_csv('data/rapm/rapm_walkforward.csv', dtype={'season': str})")
    log("meta = pd.read_csv('data/rapm/rapm_walkforward_seasons.csv', dtype={'season': str})")
    log("# join on BOTH keys - joining on player_id alone re-creates the defect")
    log("df = df.merge(wf[['season','player_id','net_100']], on=['season','player_id'],")
    log("              how='left')")
    log("# players with no prior history take that season's own p25, not a global one")
    log("repl = dict(zip(meta['season'], meta['replacement_net_100_p25']))")
    log("df['net_100'] = df['net_100'].fillna(df['season'].map(repl))")
    log("# cleanliness assertion the registration asks every consumer to make")
    log("assert (df['fit_through_season'] < df['season']).all()")
    log("```")
    log("")
    log("- seasons 2022-2026 are emitted; 2021 has no prior data and is excluded.")
    log("- a game in season s only ever sees values fit on seasons <= s-1.")
    log("- 2022 carries the thin-history caveat (one training season, no inner split);")
    log("  `thin_history_caveat` is flagged in the season manifest.")
    log("- `minutes_2021_24` keeps its rapm_v0 name for join compatibility but holds")
    log("  THIS ROW's training-window minutes (the build_rapm_v1.py precedent).")
    log("- SCALE WARNING: `lambda_chosen` varies by season (that is what makes it")
    log("  walk-forward), and lambda sets shrinkage, so `net_100` is not on one scale")
    log("  across seasons. For pooled cross-season fits use a fixed-lambda column")
    log("  (`net_100_lam5000` is the closest analogue to rapm_v0's `net_100`) or")
    log("  standardize within season.")

    log("")
    log("## Files")
    log(f"- data/rapm/rapm_walkforward.csv ({len(wf):,} rows, "
        f"{wf['season'].nunique()} seasons, {wf['player_id'].nunique()} players)")
    log(f"- data/rapm/rapm_walkforward_seasons.csv ({len(meta)} rows)")
    log("- experiments/rapm_walkforward/{consumer_audit,margin_corr_diagnostic,"
        "stint_eval_by_season}.csv")
    log("- NOT modified: data/rapm/rapm_v0.csv, build_rapm.py, experiments/registry.jsonl,"
        " leaderboards/")
    log("")
    log(f"runtime {time.time() - t0:.0f}s")

    with open(os.path.join(EXP_DIR, "REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(R) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
