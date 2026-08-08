"""TESTS.py -- known-answer tests for screenkit.

A shared library that is subtly wrong is WORSE than copy-paste, because it propagates one error
into every future screen with the authority of a shared helper.  Every assertion below is against
a value derived INDEPENDENTLY of the implementation -- by hand arithmetic, by closed-form algebra,
or by a construction whose answer is fixed before the code runs.

SYNTHETIC DATA ONLY.  Nothing here loads real season data.  Nothing here touches 2025/2026 except
the deliberate partition-violation fixture, which is a 4-row in-memory frame.

Run:  python TESTS.py       (exit code 0 = all pass, 1 = at least one failure)
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import traceback

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import screenkit as sk  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

RESULTS = []


def check(name, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((name, ok, detail))
    print("    [%s] %-58s %s" % ("PASS" if ok else "FAIL", name, detail))
    return ok


def section(title):
    print("\n" + "=" * 96)
    print(title)
    print("=" * 96)


# ===========================================================================================
def test_r2_plain_hand_computed():
    """R2 against arithmetic done on paper.

    y = [1,2,3,4], x = [1,2,3,5].
      mean x = 2.75, mean y = 2.5
      Sxy = (-1.75)(-1.5)+(-0.75)(-0.5)+(0.25)(0.5)+(2.25)(1.5) = 2.625+0.375+0.125+3.375 = 6.5
      Sxx = 3.0625+0.5625+0.0625+5.0625 = 8.75
      Syy = 2.25+0.25+0.25+2.25 = 5.0
      R2  = Sxy^2/(Sxx*Syy) = 42.25/43.75 = 169/175 = 0.9657142857142857...
    """
    section("TEST 1 -- r2_plain / delta_r2_plain against hand-computed arithmetic")
    y = np.array([1.0, 2.0, 3.0, 4.0])
    x = np.array([1.0, 2.0, 3.0, 5.0])
    expected = 169.0 / 175.0
    got = sk.r2_plain(y, x)
    print("      hand-derived R2 = 169/175 = %.16f" % expected)
    print("      screenkit       =           %.16f" % got)
    check("r2_plain matches hand arithmetic (169/175)", abs(got - expected) < 1e-12,
          "|diff| = %.3e" % abs(got - expected))

    # An exactly-fitting model must give R2 == 1 to machine precision.
    y2 = 3.0 + 2.0 * x
    check("r2_plain == 1 on an exact linear fit", abs(sk.r2_plain(y2, x) - 1.0) < 1e-12,
          "R2 = %.15f" % sk.r2_plain(y2, x))

    # SST must be about the UNWEIGHTED mean: adding a constant to y must not change R2.
    check("r2_plain is invariant to shifting y by a constant",
          abs(sk.r2_plain(y + 1000.0, x) - got) < 1e-10,
          "R2(y+1000) = %.12f" % sk.r2_plain(y + 1000.0, x))

    # delta_r2_plain is exactly the difference of the two R2s, and shares one SST.
    rng = np.random.default_rng(3)
    n = 200
    z = rng.normal(size=n)
    xx = rng.normal(size=n)
    yy = 0.7 * z + 0.4 * xx + rng.normal(size=n)
    d = sk.delta_r2_plain(yy, z[:, None], np.column_stack([z, xx]))
    d_manual = sk.r2_plain(yy, np.column_stack([z, xx])) - sk.r2_plain(yy, z[:, None])
    check("delta_r2_plain == r2_plain(full) - r2_plain(base)", abs(d - d_manual) < 1e-12,
          "dR2 = %.10f, |diff| = %.3e" % (d, abs(d - d_manual)))


# ===========================================================================================
def test_defective_vs_standard_weighted_r2():
    """The three analytic predictions about the trap-4 defect."""
    section("TEST 2 -- wls_r2_DEFECTIVE vs r2_weighted_standard (trap 4)")
    rng = np.random.default_rng(7)

    # ---- 2a. UNIFORM WEIGHTS -> ratio EXACTLY 1.0000000000 -------------------------------
    # Analytic: with w = c constant, mu_w = ybar and sum(w(y-ybar)^2) = c*sum((y-ybar)^2)
    # = sum((sqrt(c)y - mean(sqrt(c)y))^2).  Numerator identical.  The R2s coincide exactly.
    n = 300
    x = rng.normal(size=n)
    y = 2.0 + 1.3 * x + rng.normal(size=n)
    for c in (1.0, 3.7, 250.0):
        w = np.full(n, c)
        rd = sk.wls_r2_DEFECTIVE(y, x, w)
        rs = sk.r2_weighted_standard(y, x, w)
        ratio = rd / rs
        print("      uniform w = %-7.1f  defective = %.15f  standard = %.15f  ratio = %.12f"
              % (c, rd, rs, ratio))
        check("uniform weights w=%g -> ratio EXACTLY 1.0000000000" % c,
              round(ratio, 10) == 1.0, "ratio = %.12f  (|ratio-1| = %.3e)" % (ratio, abs(ratio - 1)))

    # ---- 2b. CENTERED RESPONSE -> ratio ~0.99931 and NOT exactly 1 ------------------------
    # Construction (exact, no fitting/search).  Let a = sqrt(w), z = a*y.  Then
    #   sum(w*y)      = <a, z>            -> force z PERPENDICULAR to a  =>  mu_w = 0 exactly
    #   sst_standard  = |z|^2                                        =: S
    #   sst_defective = |z|^2 - <1,z>^2/n = S - T                    (SST of z about its OWN mean)
    # With R := standard weighted R2 = 1 - sse/S and t := T/S,
    #   R2_defective = 1 - sse/(S-T) = 1 - (1-R)/(1-t)
    #   ratio        = [1 - (1-R)/(1-t)] / R
    # We INVERT that for the target ratio, build data with exactly that (R, t), and require the
    # implementation to return the target.
    n = 400
    R_target = 0.5
    ratio_target = 0.99931
    t_target = 1.0 - (1.0 - R_target) / (1.0 - ratio_target * R_target)

    rg = np.random.default_rng(11)
    w = np.exp(rg.normal(0.0, 0.6, n))
    a = np.sqrt(w)
    ahat = a / np.linalg.norm(a)
    one = np.ones(n)
    u = one - (one @ ahat) * ahat                 # component of 1 orthogonal to a
    nu2 = float(u @ u)
    uhat = u / np.sqrt(nu2)

    beta2 = nu2 / (n * t_target) - 1.0            # alpha = 1; solves t = nu2 / (n(1+beta^2))
    assert beta2 > 0, "construction infeasible for this weight dispersion"
    beta = np.sqrt(beta2)

    v = rg.normal(size=n)
    v -= (v @ ahat) * ahat
    v -= (v @ uhat) * uhat
    vhat = v / np.linalg.norm(v)

    z = uhat + beta * vhat                        # <a,z> = 0 ; <1,z> = |u| ; |z|^2 = 1 + beta^2
    zhat = z / np.linalg.norm(z)

    g = rg.normal(size=n)
    g -= (g @ ahat) * ahat
    g -= (g @ zhat) * zhat
    ghat = g / np.linalg.norm(g)

    wdir = np.sqrt(R_target) * zhat + np.sqrt(1.0 - R_target) * ghat   # unit, perpendicular to a
    xc = 50.0 * wdir / a                          # span{a, a*xc} = span{a, wdir}; scale is free
    yc = z / a

    S = float(np.sum(w * yc ** 2))
    T = float(np.sum(a * yc) ** 2 / n)
    print("      construction check: sum(w*y) = %.3e (target 0)   t = T/S = %.9f (target %.9f)"
          % (float(np.sum(w * yc)), T / S, t_target))

    rd = sk.wls_r2_DEFECTIVE(yc, xc, w)
    rs = sk.r2_weighted_standard(yc, xc, w)
    ratio = rd / rs
    print("      centered response:  standard R2 = %.12f (target %.2f)" % (rs, R_target))
    print("                          defective R2 = %.12f" % rd)
    print("                          ratio        = %.12f (target %.5f)" % (ratio, ratio_target))
    check("centered response: standard weighted R2 hits the constructed 0.5",
          abs(rs - R_target) < 1e-9, "R2_std = %.12f" % rs)
    check("centered response: ratio == 0.99931 (analytic target)",
          abs(ratio - ratio_target) < 1e-8, "ratio = %.12f" % ratio)
    check("centered response: ratio is NOT exactly 1",
          ratio != 1.0 and round(ratio, 10) != 1.0, "ratio = %.12f, 1-ratio = %.3e"
          % (ratio, 1.0 - ratio))
    # Independent closed-form re-derivation of the defective value from S, T and SSE.
    sse = (1.0 - rs) * S
    rd_pred = 1.0 - sse / (S - T)
    check("defective R2 == closed form 1 - SSE/(S-T)", abs(rd - rd_pred) < 1e-12,
          "|diff| = %.3e" % abs(rd - rd_pred))

    # ---- 2c. DISPERSED WEIGHTS, NON-CENTERED RESPONSE -> dR2 shortfall inside the 0-25% band
    # Analytic: SSE is identical under both conventions, so
    #   shortfall = 1 - dR2_defective/dR2_standard = 1 - SST_standard/SST_defective
    # and for a non-centered y with dispersed w, SST_defective > SST_standard, so the defect
    # ALWAYS understates.  Measured band across the frozen screens: 0% to 25.3%.
    n = 800
    rg2 = np.random.default_rng(23)
    w2 = np.exp(rg2.normal(0.0, 0.9, n))
    x1 = rg2.normal(size=n)
    x2 = rg2.normal(size=n)
    y2 = 1.0 + 0.30 * x1 + 0.10 * x2 + rg2.normal(size=n)      # mean ~1.0 -> NOT centered

    dr2_std = sk.delta_r2_weighted(y2, x1[:, None], np.column_stack([x1, x2]), w2)
    dr2_def = (sk.wls_r2_DEFECTIVE(y2, np.column_stack([x1, x2]), w2)
               - sk.wls_r2_DEFECTIVE(y2, x1[:, None], w2))
    shortfall = 1.0 - dr2_def / dr2_std

    a2 = np.sqrt(w2)
    sst_std = float(np.sum(w2 * (y2 - np.average(y2, weights=w2)) ** 2))
    yw = a2 * y2
    sst_def = float(np.sum((yw - yw.mean()) ** 2))
    shortfall_pred = 1.0 - sst_std / sst_def

    print("      dispersed w, non-centered y:  dR2 standard  = %.8f" % dr2_std)
    print("                                    dR2 defective = %.8f" % dr2_def)
    print("                                    shortfall     = %.4f%%  (predicted %.4f%%)"
          % (100 * shortfall, 100 * shortfall_pred))
    check("dR2 shortfall == closed form 1 - SST_std/SST_def",
          abs(shortfall - shortfall_pred) < 1e-12, "|diff| = %.3e" % abs(shortfall - shortfall_pred))
    check("defect UNDERSTATES dR2 (defective <= standard)", dr2_def <= dr2_std,
          "def %.8f <= std %.8f" % (dr2_def, dr2_std))
    check("dR2 shortfall lands inside the measured 0-25.3%% band",
          0.0 < shortfall <= 0.253, "shortfall = %.2f%%" % (100 * shortfall))


# ===========================================================================================
def _game_frame(n_games=30, rows_per_game=10, seed=5):
    """Synthetic frame where the feature is deliberately CONSTANT WITHIN GAME."""
    rng = np.random.default_rng(seed)
    rows = []
    for gi in range(n_games):
        gval = rng.normal()
        home, away = gi % 12, (gi + 5) % 12
        for k in range(rows_per_game):
            rows.append({
                "season": 2021 + gi % 4,
                "game_id": 1000 + gi,
                "team_id": home if k < rows_per_game // 2 else away,
                "player_id": 100 * (1 + (k % (rows_per_game // 2))) + (k >= rows_per_game // 2),
                "game_pace": gval,                       # ONE VALUE PER GAME
                "player_minutes": float(rng.integers(8, 38)),
            })
    return pd.DataFrame(rows)


def test_detect_grouping_level():
    section("TEST 3 -- detect_grouping_level must report `game`, not `row` (trap 1)")
    df = _game_frame()
    rep = sk.detect_grouping_level(df, "game_pace", verbose=True)
    check("recommends the GAME level for a per-game feature",
          rep["recommended_permutation_level"] == "game",
          "recommended = %r" % rep["recommended_permutation_level"])
    check("recommendation is NOT `row`", rep["recommended_permutation_level"] != sk.ROW_LEVEL)
    check("game level is flagged constant", rep["levels"]["game"]["constant_within"] is True)
    check("team_season level is NOT constant (feature varies across a team's games)",
          rep["levels"]["team_season"]["constant_within"] is False,
          "max distinct within a team-season = %d"
          % rep["levels"]["team_season"]["max_distinct_within_group"])
    check("reports 30 distinct feature values across 300 rows",
          rep["n_distinct_values_global"] == 30 and rep["n_rows"] == 300,
          "%d distinct / %d rows" % (rep["n_distinct_values_global"], rep["n_rows"]))

    # A genuinely row-level feature must NOT be pushed to a coarse level.
    rep2 = sk.detect_grouping_level(df, "player_minutes")
    check("a genuinely row-varying feature falls back to `row`",
          rep2["recommended_permutation_level"] == sk.ROW_LEVEL,
          "recommended = %r" % rep2["recommended_permutation_level"])

    # The refusal contract.
    raised = False
    try:
        sk.permutation_null(lambda d: 0.0, df, None, 10, 1, feature_col="game_pace")
    except ValueError as exc:
        raised = "REFUSES" in str(exc)
    check("permutation_null REFUSES a None grouping level", raised)

    raised2 = False
    try:
        sk.permutation_null(lambda d: 0.0, df, "team_id", 10, 1, feature_col="game_pace")
    except ValueError as exc:
        raised2 = "not constant within groups" in str(exc).lower() or "NOT constant" in str(exc)
    check("permutation_null refuses a level where the feature is not constant", raised2)


# ===========================================================================================
def test_critical_row_level_null_over_rejects():
    """THE CRITICAL TEST.  No real effect, a group-level feature.

    The row-level null must OVER-REJECT (frequently p < 0.05).  The correct-level null must not.
    This is the executable statement of trap 1: it demonstrates the over-rejection empirically
    rather than asserting an inequality.

    Design (design effect is the whole point):
      30 games x 50 rows = 1500 rows.  y carries a GAME random effect (sd 2.0) plus row noise
      (sd 1.0) -> ICC = 4/5 = 0.8.  The feature x is drawn per GAME, independently of y, so the
      TRUE effect is exactly zero.

      ANALYTIC PREDICTION.  Design effect DE = 1 + (m-1)*ICC = 1 + 49*0.8 = 40.2.  On the
      CORRELATION scale the correct null is sqrt(DE) = 6.34x wider than the row-level null; but the
      statistic here is dR2, which is r^2, so on the REPORTED scale the sd inflation is DE itself,
      ~40x.  Both the rejection rates and that factor are checked below.
    """
    section("TEST 4 -- CRITICAL: row-level null over-rejects, correct-level null does not")
    n_games, m = 30, 50
    n_reps, n_draws = 120, 200
    alpha = 0.05
    icc = 4.0 / 5.0
    design_effect = 1.0 + (m - 1) * icc

    game_ids = np.repeat(np.arange(n_games), m)
    n = n_games * m

    def stat_fn(d):
        yv = d["y"].to_numpy(float)
        return sk.delta_r2_plain(yv, d[["z"]].to_numpy(float),
                                 d[["z", "x"]].to_numpy(float))

    p_row, p_grp, infl = [], [], []
    for rep in range(n_reps):
        rng = np.random.default_rng(90000 + rep)
        game_effect = rng.normal(0.0, 2.0, n_games)
        y = game_effect[game_ids] + rng.normal(0.0, 1.0, n)
        x = rng.normal(size=n_games)[game_ids]           # per-GAME, independent of y -> NO EFFECT
        z = rng.normal(size=n)                           # a genuine row-level nuisance covariate
        df = pd.DataFrame({"game_id": game_ids, "y": y, "x": x, "z": z})

        cmp = sk.null_width_comparison(stat_fn, df, "game_id", n_draws, 1234 + rep,
                                       feature_col="x")
        p_row.append(cmp["p_row_level_NAIVE"])
        p_grp.append(cmp["p_correct"])
        infl.append(cmp["inflation"])

    p_row, p_grp, infl = np.array(p_row), np.array(p_grp), np.array(infl)
    rej_row = float((p_row <= alpha).mean())
    rej_grp = float((p_grp <= alpha).mean())

    print("      %d replicate datasets, %d permutation draws each, TRUE EFFECT = 0" % (n_reps, n_draws))
    print("      rejection rate at alpha=%.2f  --  NAIVE ROW-LEVEL null  : %.3f   (nominal %.2f)"
          % (alpha, rej_row, alpha))
    print("      rejection rate at alpha=%.2f  --  CORRECT GAME-LEVEL null: %.3f   (nominal %.2f)"
          % (alpha, rej_grp, alpha))
    print("      correct-level p-values: mean %.3f  median %.3f  min %.3f   (uniform => mean 0.5)"
          % (p_grp.mean(), np.median(p_grp), p_grp.min()))
    print("      null sd inflation (correct/row): median %.2fx  min %.2fx  max %.2fx"
          % (np.median(infl), infl.min(), infl.max()))
    print("      analytic design effect DE = 1 + (%d-1)*%.1f = %.1f ; the statistic is dR2 = r^2,"
          % (m, icc, design_effect))
    print("      so the expected sd inflation on the REPORTED scale is DE itself (~%.1fx), and"
          % design_effect)
    print("      sqrt(DE) = %.2fx on the correlation scale." % np.sqrt(design_effect))

    check("row-level null OVER-REJECTS (rate >= 0.50 with zero true effect)", rej_row >= 0.50,
          "row-level rejection rate = %.3f" % rej_row)
    check("correct-level null is calibrated (rejection rate <= 0.20)", rej_grp <= 0.20,
          "correct-level rejection rate = %.3f" % rej_grp)
    check("correct-level p-values are ~uniform (mean p in [0.30, 0.70])",
          0.30 <= float(p_grp.mean()) <= 0.70, "mean p = %.3f" % p_grp.mean())
    check("row-level rejection rate strictly exceeds correct-level", rej_row > rej_grp,
          "%.3f > %.3f" % (rej_row, rej_grp))
    check("measured null-sd inflation brackets the analytic design effect %.1f" % design_effect,
          0.5 * design_effect < float(np.median(infl)) < 2.0 * design_effect,
          "median inflation = %.2fx vs DE = %.1f" % (np.median(infl), design_effect))


# ===========================================================================================
def test_noop_placebo():
    section("TEST 5 -- noop_placebo: sd < 1e-15 on a genuine no-op, nonzero on a real shuffle")
    rng = np.random.default_rng(41)
    n_teams, n = 12, 900
    df = pd.DataFrame({
        "season": rng.integers(2021, 2025, n),
        "team_id": rng.integers(0, n_teams, n),
        "opp_team_id": rng.integers(0, n_teams, n),
        "val": rng.normal(size=n),
        "z": rng.normal(size=n),
    })
    df = df[df["team_id"] != df["opp_team_id"]].reset_index(drop=True)

    def opp_profile(d, tcol, ocol):
        prof = d.groupby(["season", tcol])["val"].mean().rename("prof").reset_index()
        merged = d.merge(prof.rename(columns={tcol: ocol}), on=["season", ocol], how="left")
        return merged["prof"].to_numpy(float)

    df["feat"] = opp_profile(df, "team_id", "opp_team_id")
    df["y"] = 0.5 * df["z"] + rng.normal(size=len(df))

    def stat_fn(d):
        return sk.delta_r2_plain(d["y"].to_numpy(float), d[["z"]].to_numpy(float),
                                 d[["z", "feat"]].to_numpy(float))

    # (a) literal identity -- the purest no-op
    res_id = sk.noop_placebo(stat_fn, df, 25, verbose=True)
    check("identity transform -> sd < 1e-15 and is_noop True",
          res_id["sd"] < 1e-15 and res_id["is_noop"], "sd = %.3e" % res_id["sd"])

    # (b) THE REAL DEFECTIVE PATTERN: permute the grouping KEY consistently, then RECOMPUTE the
    #     aggregate from the permuted key.  The permuted cell is the same row set under a
    #     bijection, so every row still receives its own true value.
    def relabel_and_recompute(d, rgen):
        w = d.copy()
        newt = np.empty(len(w), dtype=np.int64)
        newo = np.empty(len(w), dtype=np.int64)
        for s in np.unique(w["season"].to_numpy()):
            mask = w["season"].to_numpy() == s
            teams = np.arange(n_teams)
            sigma = dict(zip(teams, rgen.permutation(teams)))
            newt[mask] = [sigma[t] for t in w.loc[mask, "team_id"]]
            newo[mask] = [sigma[t] for t in w.loc[mask, "opp_team_id"]]
        w["team_id_p"] = newt
        w["opp_team_id_p"] = newo
        w["feat"] = opp_profile(w, "team_id_p", "opp_team_id_p")
        return w

    res_key = sk.noop_placebo(stat_fn, df, 15, transform=relabel_and_recompute, verbose=True)
    check("permute-the-key-and-recompute is CONFIRMED a no-op (sd < 1e-15)",
          res_key["sd"] < 1e-15 and res_key["is_noop"],
          "sd = %.3e, max|draw-real| = %.3e" % (res_key["sd"], res_key["max_abs_dev_from_real"]))
    check("noop_placebo RETURNS the observed sd rather than rounding it to zero",
          isinstance(res_key["sd"], float), "sd = %.3e (reported, not asserted bitwise-zero)"
          % res_key["sd"])

    # (c) a REAL shuffle must NOT look like a no-op
    def real_shuffle(d, rgen):
        w = d.copy()
        w["feat"] = rgen.permutation(w["feat"].to_numpy(float))
        return w

    res_real = sk.noop_placebo(stat_fn, df, 25, transform=real_shuffle, verbose=True)
    check("a real shuffle FAILS the no-op signature (sd > 0, is_noop False)",
          res_real["sd"] > 1e-12 and not res_real["is_noop"], "sd = %.3e" % res_real["sd"])


# ===========================================================================================
def test_assert_partition():
    section("TEST 6 -- assert_partition is VALUE-based, never textual (trap 3)")
    clean = pd.DataFrame({
        "season": [2021, 2022, 2023, 2024],
        "game_date": pd.to_datetime(["2021-06-01", "2022-07-04", "2023-08-11", "2024-05-20"]),
        "value": [0.1, 0.2, 0.3, 0.4],
    })
    rep = sk.assert_partition(clean, verbose=True)
    check("PASSES on clean 2021-2024 data", rep["ok"] is True)

    dirty = clean.copy()
    dirty.loc[1, "season"] = 2025
    raised = False
    try:
        sk.assert_partition(dirty)
    except sk.PartitionViolation as exc:
        raised = "2025" in str(exc)
    check("RAISES PartitionViolation on a 2025 season VALUE", raised)

    dirty_date = clean.copy()
    dirty_date.loc[2, "game_date"] = pd.Timestamp("2025-03-01")
    raised_d = False
    try:
        sk.assert_partition(dirty_date)
    except sk.PartitionViolation as exc:
        raised_d = "2025" in str(exc)
    check("RAISES on a 2025 YEAR VALUE inside a date column", raised_d)

    # THE REGRESSION TEST FOR TRAP 3.  A column literally NAMED `_team_season_2025` whose VALUES
    # are dR2 permutation draws (~1e-4).  A byte/regex/name scan flags this; a VALUE check must not.
    rng = np.random.default_rng(2)
    trap3 = pd.DataFrame({
        "season": np.repeat([2021, 2022, 2023, 2024], 25),
        "game_date": pd.to_datetime(np.repeat(["2021-06-01", "2022-06-01",
                                               "2023-06-01", "2024-06-01"], 25)),
        "_team_season_2025": rng.normal(1e-4, 3e-5, 100),        # dR2 draws, NOT seasons
        "dr2_draw_season_2026": rng.normal(1e-4, 3e-5, 100),     # same trap, different name
        "note_about_the_2025_holdout": ["seasons 2025 and 2026 are the holdout"] * 100,
    })
    rep3 = sk.assert_partition(trap3, verbose=True)
    check("PASSES on a column NAMED `_team_season_2025` holding dR2 draws (trap-3 regression)",
          rep3["ok"] is True, "violations = %s" % rep3["violations"])
    check("the name-only column is recorded as SKIPPED, not checked",
          "_team_season_2025" in rep3["skipped_name_only"],
          "skipped = %s" % sorted(rep3["skipped_name_only"]))
    check("prose containing '2025' in a text column does not trigger a violation",
          "note_about_the_2025_holdout" not in str(rep3["violations"]))

    # A year-VALUED column with an innocuous name must still be caught.
    sneaky = pd.DataFrame({"season": [2021, 2022], "fit_through": [2024, 2026]})
    raised_s = False
    try:
        sk.assert_partition(sneaky)
    except sk.PartitionViolation as exc:
        raised_s = "2026" in str(exc)
    check("catches year-VALUED data in an innocuously named column", raised_s)


# ===========================================================================================
def test_check_manifest():
    section("TEST 7 -- check_manifest: missing manifest is UNVERIFIABLE, never a pass")
    tmp = os.path.join(HERE, "_tmp_manifest_test")
    os.makedirs(tmp, exist_ok=True)
    try:
        a_none = os.path.join(tmp, "no_manifest.parquet")
        open(a_none, "wb").close()
        r0 = sk.check_manifest(a_none, verbose=True)
        check("MISSING manifest -> status UNVERIFIABLE", r0["status"] == "UNVERIFIABLE",
              "status = %s" % r0["status"])
        check("MISSING manifest -> usable_at_e0_e1 is False (not a pass)",
              r0["usable_at_e0_e1"] is False)

        a_row = os.path.join(tmp, "row_gran.parquet")
        open(a_row, "wb").close()
        with open(a_row + ".manifest.json", "w", encoding="utf-8") as fh:
            json.dump({"asof_granularity": "row", "fit_seasons": [2021, 2022, 2023, 2024],
                       "content_sha256": "deadbeef"}, fh)
        r1 = sk.check_manifest(a_row, verbose=True)
        check("asof_granularity 'row' -> USABLE_IF_FILTERED",
              r1["status"] == "USABLE_IF_FILTERED" and r1["usable_at_e0_e1"] is True,
              "status = %s" % r1["status"])
        check("'row' granularity says filtering helps", r1["filtering_helps"] is True)

        a_art = os.path.join(tmp, "artifact_gran.parquet")
        open(a_art, "wb").close()
        with open(a_art + ".manifest.json", "w", encoding="utf-8") as fh:
            json.dump({"asof_granularity": "artifact", "fit_through_season": 2026}, fh)
        r2 = sk.check_manifest(a_art, verbose=True)
        check("asof_granularity 'artifact' -> UNUSABLE at E0/E1",
              r2["status"] == "UNUSABLE" and r2["usable_at_e0_e1"] is False,
              "status = %s" % r2["status"])
        check("'artifact' granularity says filtering does NOT help",
              r2["filtering_helps"] is False)

        a_odd = os.path.join(tmp, "odd_gran.parquet")
        open(a_odd, "wb").close()
        with open(a_odd + ".manifest.json", "w", encoding="utf-8") as fh:
            json.dump({"note": "no granularity field here"}, fh)
        r3 = sk.check_manifest(a_odd, verbose=True)
        check("manifest present but granularity absent -> UNVERIFIABLE",
              r3["status"] == "UNVERIFIABLE" and r3["usable_at_e0_e1"] is False,
              "status = %s" % r3["status"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================================
def test_future_leakage_probe():
    section("TEST 8 -- future_leakage_probe detects a full-season leave-one-out baseline (trap 2)")
    rng = np.random.default_rng(19)
    n_players, n_games = 60, 30
    rows = []
    for p in range(n_players):
        mu = rng.normal(0.0, 1.0)
        for gi in range(n_games):
            rows.append({"player_id": p, "season": 2023,
                         "game_date": pd.Timestamp("2023-05-01") + pd.Timedelta(days=2 * gi),
                         "y": mu + rng.normal(0.0, 1.0)})
    df = pd.DataFrame(rows)

    g = df.groupby(["player_id", "season"], sort=False)["y"]
    tot, cnt = g.transform("sum"), g.transform("count")
    # RETROSPECTIVE: full-season leave-one-out -- reads every other game in the season, future ones
    # included.  This is exactly the `player_tendency_loo` pattern.
    df["baseline_loo"] = (tot - df["y"]) / (cnt - 1)
    # CLEAN: expanding mean over the player's games STRICTLY BEFORE this one.
    df["baseline_pregame"] = g.transform(lambda s: s.shift(1).expanding().mean())

    res = sk.future_leakage_probe(df, "baseline_loo", "baseline_pregame",
                                  ["player_id", "season"], "game_date", "y", verbose=True)
    check("flags the leave-one-out baseline as reading the future",
          res["reads_future"] is True)
    check("LOO correlates with the unplayed future more strongly than the pregame baseline",
          abs(res["corr_suspect_with_future"]) > abs(res["corr_clean_with_future"]),
          "%.4f vs %.4f" % (res["corr_suspect_with_future"], res["corr_clean_with_future"]))
    check("LOO adds substantial dR2 over the pregame baseline in PREDICTING the future",
          res["dr2_suspect_over_clean_predicting_future"] > 0.01,
          "dR2 = %.4f" % res["dr2_suspect_over_clean_predicting_future"])

    # Directional negative control: the clean baseline must not be flagged against the LOO one.
    res_rev = sk.future_leakage_probe(df, "baseline_pregame", "baseline_loo",
                                      ["player_id", "season"], "game_date", "y")
    check("does NOT flag the pregame baseline when contrasted against the LOO one",
          res_rev["reads_future"] is False,
          "corr %.4f vs %.4f, dR2 %.4f" % (res_rev["corr_suspect_with_future"],
                                           res_rev["corr_clean_with_future"],
                                           res_rev["dr2_suspect_over_clean_predicting_future"]))


# ===========================================================================================
def main():
    print("=" * 96)
    print("screenkit TESTS -- known-answer tests, SYNTHETIC DATA ONLY, no 2025/2026 real data")
    print("=" * 96)
    print("numpy %s   pandas %s   python %s" % (np.__version__, pd.__version__,
                                                sys.version.split()[0]))

    tests = [
        test_r2_plain_hand_computed,
        test_defective_vs_standard_weighted_r2,
        test_detect_grouping_level,
        test_critical_row_level_null_over_rejects,
        test_noop_placebo,
        test_assert_partition,
        test_check_manifest,
        test_future_leakage_probe,
    ]
    for t in tests:
        try:
            t()
        except Exception:                                   # noqa: BLE001
            print("    [FAIL] %s raised:" % t.__name__)
            traceback.print_exc()
            RESULTS.append((t.__name__ + " (raised)", False, "uncaught exception"))

    section("SUMMARY")
    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    for name, ok, detail in RESULTS:
        if not ok:
            print("  FAILED: %-58s %s" % (name, detail))
    print("  %d assertions: %d PASSED, %d FAILED" % (len(RESULTS), n_pass, n_fail))
    print("  RESULT: %s" % ("ALL TESTS PASS" if n_fail == 0 else "%d TEST(S) FAILED" % n_fail))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
