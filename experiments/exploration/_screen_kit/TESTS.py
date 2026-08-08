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
import warnings

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

    # A genuinely row-level feature must NOT be pushed to a coarse level -- and, since the P2 fix,
    # must NOT be "recommended" as `row` either.  THIS ASSERTION WAS REWRITTEN BY THE P2 FIX: it
    # previously required `recommended_permutation_level == sk.ROW_LEVEL`, i.e. it asserted the
    # defective contract.  The intent (do not push a row-varying feature to a coarse level) is
    # preserved; the contract it is checked against is the new one.  See TEST 10.
    rep2 = sk.detect_grouping_level(df, "player_minutes")
    check("a genuinely row-varying feature is not pushed to a coarse level (P2 contract)",
          rep2["recommended_permutation_level"] is None
          and rep2["status"] == sk.STATUS_NO_COARSER_LEVEL,
          "recommended = %r  status = %s" % (rep2["recommended_permutation_level"],
                                             rep2["status"]))

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
# REGRESSION TESTS FOR THE FOUR ISSUES FOUND BY THE KIT'S FIRST REAL USER (E0_I0015).
#
# Each of TEST 9-13 FAILS against the pre-fix screenkit.py.  That is the point: the 49-assertion
# suite passed while `detect_grouping_level` crashed on every boolean feature, because the suite
# only ever exercised floats.  The remedy for a blind spot is to close the blind spot, not just
# the bug.
# ===========================================================================================

def _bool_frame(n_games=12, rows_per_game=4, seed=17):
    """Frame whose feature is a BOOLEAN constant within game.  Mirrors the reporter's repro in
    E0_I0015/KIT_BUG_REPRO.py, enlarged so a permutation null is meaningful."""
    rng = np.random.default_rng(seed)
    rows = []
    for gi in range(n_games):
        # flag varies WITHIN each season (2 False / 4 True per season) so `season` is not itself a
        # constant level, and the coarsest constant level is genuinely `game`.
        flag = bool(gi % 3 != 0)
        for k in range(rows_per_game):
            rows.append({
                "season": 2021 + (gi // (n_games // 2)),
                "game_id": 500 + gi,
                "team_id": 1 if k < rows_per_game // 2 else 2,
                "player_id": 10 * (1 + k),
                "flag_bool": flag,
                "y": float(rng.normal()),
            })
    df = pd.DataFrame(rows)
    df["flag_float"] = df["flag_bool"].astype(float)
    return df


def test_boolean_feature_p1():
    """P1 REGRESSION.  Pre-fix, every assertion here is unreachable: `detect_grouping_level`
    raises `TypeError: numpy boolean subtract ...` on the first call, because `bool` passes
    `pd.api.types.is_numeric_dtype` and `groupby.transform('max') - groupby.transform('min')` is
    not defined for numpy booleans.  `permutation_null` inherits it through the same helper.
    """
    section("TEST 9 -- P1 REGRESSION: BOOLEAN features (pre-fix: TypeError, 0 of these ran)")
    df = _bool_frame()
    print("      feature dtype = %s ; is_numeric_dtype says %s (which is why bool took the "
          "numeric branch)" % (df["flag_bool"].dtype, pd.api.types.is_numeric_dtype(df["flag_bool"])))

    rep_b = sk.detect_grouping_level(df, "flag_bool", verbose=True)
    rep_f = sk.detect_grouping_level(df, "flag_float")
    check("detect_grouping_level does not raise on a BOOLEAN feature",
          rep_b["recommended_permutation_level"] == "game",
          "recommended = %r" % rep_b["recommended_permutation_level"])
    check("bool and its float twin give the IDENTICAL levels table",
          rep_b["levels"] == rep_f["levels"],
          "bool game spread = %r, float game spread = %r"
          % (rep_b["levels"]["game"]["max_within_group_spread"],
             rep_f["levels"]["game"]["max_within_group_spread"]))
    check("the bool went through the NUMERIC spread path, not the nunique fallback",
          rep_b["levels"]["game"]["max_within_group_spread"] == 0.0
          and rep_b["levels"]["season"]["max_within_group_spread"] == 1.0,
          "game spread = %r, season spread = %r"
          % (rep_b["levels"]["game"]["max_within_group_spread"],
             rep_b["levels"]["season"]["max_within_group_spread"]))
    check("the report says the feature is boolean", rep_b["feature_is_boolean"] is True,
          "feature_dtype = %s" % rep_b["feature_dtype"])

    # permutation_null inherited the crash through the same helper.
    seen_dtypes, true_counts = [], []

    def stat_bool(d):
        seen_dtypes.append(str(d["flag_bool"].dtype))
        true_counts.append(int(d["flag_bool"].sum()))
        # BOOLEAN MASKING -- this is what silently breaks if the kit hands stat_fn floats back
        return float(d.loc[d["flag_bool"], "y"].mean() - d.loc[~d["flag_bool"], "y"].mean())

    res = sk.permutation_null(stat_bool, df, ["game_id"], 40, 1,
                              feature_col="flag_bool", block_col="season",
                              alternative="two_sided")
    check("permutation_null runs on a BOOLEAN feature", np.isfinite(res["real"]),
          "real = %.6f  p = %.4f  n_groups = %d" % (res["real"], res["p"], res["n_groups"]))
    check("stat_fn sees dtype bool on EVERY permuted frame, not float",
          set(seen_dtypes) == {"bool"}, "dtypes seen = %s" % sorted(set(seen_dtypes)))
    check("every draw is a genuine permutation: the True count never changes",
          set(true_counts) == {int(df["flag_bool"].sum())} and res["sd"] > 0,
          "True counts seen = %s (real = %d), sd = %.6g"
          % (sorted(set(true_counts)), int(df["flag_bool"].sum()), res["sd"]))
    check("permutation_null reports the feature as boolean",
          res["feature_is_boolean"] is True)

    # A nullable pandas `boolean` column (pd.NA present) must also be handled, not crash.
    dfn = df.copy()
    vals = df["flag_bool"].to_numpy().copy()
    arr = pd.array(vals, dtype="boolean")
    arr[0] = pd.NA
    dfn["flag_nullable"] = arr
    rep_n = sk.detect_grouping_level(dfn, "flag_nullable")
    check("a nullable `boolean` column with pd.NA is handled, not crashed on",
          rep_n["feature_is_boolean"] is True
          and np.isfinite(rep_n["levels"]["season"]["max_within_group_spread"]),
          "dtype = %s, season spread = %r"
          % (rep_n["feature_dtype"], rep_n["levels"]["season"]["max_within_group_spread"]))

    # Negative control: a non-numeric, non-boolean feature still takes the distinct-count path.
    dfs = df.copy()
    dfs["label"] = np.where(df["flag_bool"], "hot", "cold")
    rep_s = sk.detect_grouping_level(dfs, "label")
    check("a STRING feature still uses the distinct-count path (spread nan, no coercion)",
          rep_s["recommended_permutation_level"] == "game"
          and np.isnan(rep_s["levels"]["game"]["max_within_group_spread"]),
          "recommended = %r" % rep_s["recommended_permutation_level"])


# ===========================================================================================
def test_row_recommendation_is_not_an_endorsement_p2():
    """P2 REGRESSION -- THE SERIOUS ONE, AND THE SILENT ONE.

    Pre-fix, `detect_grouping_level` returned `recommended_permutation_level: "row"` for a
    genuinely row-varying feature -- 34 of 55 candidates in the screen that reported it.  The
    docstring carried the caveat; the FIELD NAME undid it.  `"row"` is also the exact sentinel
    `permutation_null` accepts for the naive null, so a caller who trusted the field name got the
    anticonservative null WITH THE KIT'S AUTHORITY BEHIND IT, and no signal at all.
    """
    section("TEST 10 -- P2 REGRESSION: `row` must never be returned as a RECOMMENDATION")
    df = _game_frame()
    rep = sk.detect_grouping_level(df, "player_minutes", verbose=True)

    check("recommended_permutation_level is None, NOT the string 'row'",
          rep["recommended_permutation_level"] is None
          and rep["recommended_permutation_level"] != sk.ROW_LEVEL,
          "recommended = %r" % rep["recommended_permutation_level"])
    check("status names the situation and says ANTICONSERVATIVE out loud",
          rep["status"] == sk.STATUS_NO_COARSER_LEVEL
          and "ANTICONSERVATIVE" in rep["status"],
          "status = %s" % rep["status"])
    check("row_null_is_anticonservative is True and a warning is carried",
          rep["row_null_is_anticonservative"] is True
          and isinstance(rep["warning"], str) and "ANTICONSERVATIVE" in rep["warning"].upper(),
          "warning is %d chars" % len(rep["warning"] or ""))
    check("the naive null is still reachable, but ONLY via the opt-in field",
          rep["level_if_you_accept_the_anticonservative_row_null"] == sk.ROW_LEVEL)

    # THE CONTRACT THAT MATTERS: a caller who reads ONLY the recommendation field and pipes it
    # straight into permutation_null must be REFUSED, not silently given the wrong null.
    refused = False
    try:
        sk.permutation_null(lambda d: 0.0, df, rep["recommended_permutation_level"], 10, 1,
                            feature_col="player_minutes")
    except ValueError as exc:
        refused = "REFUSES" in str(exc)
    check("piping the recommendation into permutation_null REFUSES (cannot be misled)", refused)

    refused_k = False
    try:
        sk.permutation_null(lambda d: 0.0, df, rep["recommended_key_cols"], 10, 1,
                            feature_col="player_minutes")
    except ValueError as exc:
        refused_k = "REFUSES" in str(exc)
    check("piping recommended_key_cols into permutation_null also REFUSES", refused_k)

    # Generic guard against reintroducing the defect under a different field name.
    endorsing = sorted(k for k, v in rep.items()
                       if isinstance(v, str) and v == sk.ROW_LEVEL
                       and ("recommend" in k.lower() or "correct" in k.lower()
                            or "level" == k.lower()))
    check("NO field whose name reads as a recommendation carries the value 'row'",
          endorsing == [], "offending fields = %s" % endorsing)

    # A key that identifies rows uniquely is a row-level null wearing key columns.
    check("`player_game` uniquely identifies rows here and is flagged is_row_equivalent",
          rep["levels"]["player_game"]["is_row_equivalent"] is True
          and rep["levels"]["player_game"]["constant_within"] is True,
          "n_groups = %d vs n_rows = %d"
          % (rep["levels"]["player_game"]["n_groups"], rep["n_rows"]))
    check("a constant-but-row-equivalent key is NOT recommended",
          rep["recommended_permutation_level"] != "player_game")

    # POSITIVE CONTROL: when a genuinely coarser level exists the good path is unchanged.
    rep_ok = sk.detect_grouping_level(df, "game_pace")
    check("the good path is unchanged: a real coarser level is still recommended",
          rep_ok["status"] == sk.STATUS_COARSER_LEVEL_FOUND
          and rep_ok["recommended_permutation_level"] == "game"
          and rep_ok["recommended_key_cols"] == ["game_id"]
          and rep_ok["row_null_is_anticonservative"] is False,
          "recommended = %r" % rep_ok["recommended_permutation_level"])

    # And an explicit row-level null still carries its own warning in the result.
    naive = sk.permutation_null(lambda d: float(d["player_minutes"].mean()), df,
                                sk.ROW_LEVEL, 5, 1, feature_col="player_minutes")
    check("an explicitly-requested ROW_LEVEL null returns a warning field",
          naive["is_row_level_naive"] is True
          and isinstance(naive["warning"], str) and "anticonservative" in naive["warning"],
          "warning is %d chars" % len(naive["warning"] or ""))


# ===========================================================================================
def test_r2_of_forecast_p3():
    """P3 REGRESSION.  `screenkit.r2_plain(y, X)` REFITS; the screens' own
    `rh_base.r2_plain(y, yhat)` SCORES A GIVEN FORECAST.  Same name, different semantics.  The
    reporter got 0.4747 against a published 0.4694 and briefly believed its reproduction had
    failed.  Pre-fix, `sk.r2_of_forecast` does not exist and this whole test raises.
    """
    section("TEST 11 -- P3 REGRESSION: r2_of_forecast (scores) vs r2_plain (refits)")
    y = np.array([1.0, 2.0, 3.0, 4.0])
    yhat = np.array([1.1, 1.9, 3.2, 3.9])
    # SSE = 0.01 + 0.01 + 0.04 + 0.01 = 0.07 ; SST = 2.25+0.25+0.25+2.25 = 5.0
    # R2  = 1 - 0.07/5.0 = 0.986   -- arithmetic done on paper, independent of the implementation
    expected = 0.986
    got = sk.r2_of_forecast(y, yhat)
    print("      hand-derived 1 - 0.07/5.0 = %.16f" % expected)
    print("      screenkit                 = %.16f" % got)
    check("r2_of_forecast matches hand arithmetic (1 - 0.07/5.0 = 0.986)",
          abs(got - expected) < 1e-12, "|diff| = %.3e" % abs(got - expected))

    refit = sk.r2_plain(y, yhat)
    print("      r2_plain(y, yhat) REFITS y ~ a + b*yhat and returns %.16f" % refit)
    check("THE COLLISION: r2_plain(y, yhat) != r2_of_forecast(y, yhat)",
          abs(refit - got) > 1e-6, "refit %.6f vs scored %.6f (gap %.6f)"
          % (refit, got, refit - got))

    # The sharpest statement of the difference: an ANTI-correlated forecast.  Refitting flips the
    # sign and scores a perfect 1.0; scoring it as given gives 1 - 4*sum(y^2)/SST = 1 - 120/5 = -23.
    check("r2_plain(y, -y) == 1.0 exactly (it refits, so the sign is free)",
          abs(sk.r2_plain(y, -y) - 1.0) < 1e-12, "r2_plain = %.15f" % sk.r2_plain(y, -y))
    check("r2_of_forecast(y, -y) == -23.0 exactly (hand-derived; it does NOT refit)",
          abs(sk.r2_of_forecast(y, -y) - (-23.0)) < 1e-12,
          "r2_of_forecast = %.15f" % sk.r2_of_forecast(y, -y))

    # Refitting can never do worse than scoring as given: r2_plain >= r2_of_forecast, always.
    worse = 0
    for s in range(25):
        rg = np.random.default_rng(400 + s)
        yy = rg.normal(size=120)
        ff = 0.6 * yy + rg.normal(size=120) * 0.5 + rg.normal() * 2.0
        if sk.r2_plain(yy, ff) < sk.r2_of_forecast(yy, ff) - 1e-12:
            worse += 1
    check("r2_plain(y, f) >= r2_of_forecast(y, f) on 25 random forecasts", worse == 0,
          "%d/25 violations" % worse)

    # The identity that pins the semantics: for an ALREADY OLS-CALIBRATED forecast (the fitted
    # values of y on X) the two coincide exactly, and both equal r2_plain(y, X).
    rg = np.random.default_rng(77)
    n = 300
    X = rg.normal(size=(n, 2))
    yy = X @ np.array([0.8, -0.3]) + rg.normal(size=n)
    Xd = np.column_stack([np.ones(n), X])
    beta, *_ = np.linalg.lstsq(Xd, yy, rcond=None)
    fitted = Xd @ beta
    check("on OLS-FITTED values the two agree exactly, and both equal r2_plain(y, X)",
          abs(sk.r2_of_forecast(yy, fitted) - sk.r2_plain(yy, X)) < 1e-12
          and abs(sk.r2_plain(yy, fitted) - sk.r2_plain(yy, X)) < 1e-12,
          "scored %.12f vs fitted-model %.12f" % (sk.r2_of_forecast(yy, fitted),
                                                  sk.r2_plain(yy, X)))

    # Matches the frozen rh_base(y, yhat) form, recomputed inline here from its definition.
    rg2 = np.random.default_rng(88)
    ya = rg2.normal(size=500) * 3.0 + 10.0
    fa = ya * 0.85 + rg2.normal(size=500)
    sse = float(((ya - fa) ** 2).sum())
    sst = float(((ya - ya.mean()) ** 2).sum())
    check("equals the frozen rh_base 1 - SSE/SST form recomputed inline",
          abs(sk.r2_of_forecast(ya, fa) - (1.0 - sse / sst)) < 1e-14,
          "|diff| = %.3e" % abs(sk.r2_of_forecast(ya, fa) - (1.0 - sse / sst)))
    check("a perfect forecast scores exactly 1.0",
          sk.r2_of_forecast(ya, ya) == 1.0, "R2 = %r" % sk.r2_of_forecast(ya, ya))

    # It must refuse a design matrix rather than silently doing something.
    raised = False
    try:
        sk.r2_of_forecast(yy, X)
    except ValueError as exc:
        raised = "r2_plain" in str(exc)
    check("passing a design matrix raises and points at r2_plain", raised)


# ===========================================================================================
def test_within_scheme_and_var_share_p4():
    """P4 REGRESSION (a).  The kit shipped only a BETWEEN-group permutation scheme and no variance
    decomposition, so E0_I0014 had to write `within_block_index` and `var_share_between` itself.
    Pre-fix, `scheme=` is not a parameter and `sk.var_share_between` does not exist.
    """
    section("TEST 12 -- P4 REGRESSION: within-group scheme + var_share_between")

    # ---- var_share_between against three exact constructions -----------------------------
    g = np.repeat(np.arange(20), 10)
    pure_between = pd.DataFrame({"g": g, "x": g.astype(float)})            # constant within group
    check("var_share_between == 1.0 for a feature constant within groups",
          abs(sk.var_share_between(pure_between, "x", "g") - 1.0) < 1e-12,
          "share = %.15f" % sk.var_share_between(pure_between, "x", "g"))

    alt = np.tile(np.array([-1.0, 1.0]), 100)
    pure_within = pd.DataFrame({"g": g, "x": alt})                          # every group mean = 0
    check("var_share_between == 0.0 exactly when all group means are equal",
          sk.var_share_between(pure_within, "x", "g") == 0.0,
          "share = %r" % sk.var_share_between(pure_within, "x", "g"))

    # group mean = +-1 (balanced), within-group deviation = +-1 (balanced) -> share exactly 1/2
    mu = np.where((g % 2) == 0, 1.0, -1.0)
    half = pd.DataFrame({"g": g, "x": mu + alt})
    check("var_share_between == 0.5 on a balanced half-and-half construction",
          abs(sk.var_share_between(half, "x", "g") - 0.5) < 1e-12,
          "share = %.15f" % sk.var_share_between(half, "x", "g"))
    check("var_share_between handles a BOOLEAN feature too (P1 path shared)",
          abs(sk.var_share_between(_bool_frame(), "flag_bool", "game_id") - 1.0) < 1e-12,
          "share = %.15f" % sk.var_share_between(_bool_frame(), "flag_bool", "game_id"))

    # ---- structural guarantees of the two schemes ----------------------------------------
    rng = np.random.default_rng(31)
    n_g, m = 40, 15
    codes = np.repeat(np.arange(n_g), m)
    n = n_g * m
    x = np.repeat(rng.normal(size=n_g), m) + rng.normal(size=n)   # varies BOTH between and within
    df = pd.DataFrame({"season": 2021 + (codes % 4) * 0, "grp": codes, "x": x})
    cnt = np.bincount(codes)
    gm0 = np.bincount(codes, weights=x) / cnt

    def group_mean_dev(d):
        v = d["x"].to_numpy(float)
        return float(np.max(np.abs(np.bincount(codes, weights=v) / cnt - gm0)))

    def within_ss(d):
        v = d["x"].to_numpy(float)
        return float(((v - (np.bincount(codes, weights=v) / cnt)[codes]) ** 2).sum())

    w_means = sk.permutation_null(group_mean_dev, df, "grp", 30, 5,
                                  feature_col="x", scheme=sk.SCHEME_WITHIN)
    check("WITHIN scheme preserves every group mean EXACTLY on every draw",
          float(np.max(w_means["draws"])) < 1e-12,
          "max |group-mean drift| over 30 draws = %.3e" % float(np.max(w_means["draws"])))

    w_ss = sk.permutation_null(within_ss, df, "grp", 30, 5,
                               feature_col="x", scheme=sk.SCHEME_WITHIN)
    check("WITHIN scheme preserves each group's multiset (within-group SS unchanged)",
          float(np.max(np.abs(w_ss["draws"] - w_ss["real"]))) < 1e-9,
          "max |draw - real| = %.3e" % float(np.max(np.abs(w_ss["draws"] - w_ss["real"]))))

    # WHY THE WITHIN SCHEME HAD TO EXIST: forcing the BETWEEN scheme onto a within-varying feature
    # (allow_nonconstant=True) broadcasts one representative value per group, annihilating 100% of
    # the within-group variation the statistic depends on.  Every draw is ~0 against a real value
    # of ~n; any p taken there is manufactured, not measured.
    b_ss = sk.permutation_null(within_ss, df, "grp", 30, 5, feature_col="x",
                               scheme=sk.SCHEME_BETWEEN, allow_nonconstant=True)
    print("      within-group SS: real = %.4f ; BETWEEN-scheme draws max = %.3e ; "
          "WITHIN-scheme draws min = %.4f"
          % (b_ss["real"], float(np.max(b_ss["draws"])), float(np.min(w_ss["draws"]))))
    check("BETWEEN scheme on a within-varying feature destroys ALL within-group variation",
          b_ss["real"] > 100.0 and float(np.max(b_ss["draws"])) < 1e-12,
          "real = %.4f, max draw = %.3e" % (b_ss["real"], float(np.max(b_ss["draws"]))))

    # ---- refusal contracts ---------------------------------------------------------------
    const_df = pd.DataFrame({"grp": codes, "x": np.repeat(rng.normal(size=n_g), m)})
    raised = False
    try:
        sk.permutation_null(lambda d: 0.0, const_df, "grp", 5, 1,
                            feature_col="x", scheme=sk.SCHEME_WITHIN)
    except ValueError as exc:
        raised = "IDENTITY" in str(exc)
    check("WITHIN scheme is REFUSED on a feature constant within groups (it is the identity)",
          raised)

    raised2 = False
    try:
        sk.permutation_null(lambda d: 0.0, df, sk.ROW_LEVEL, 5, 1,
                            feature_col="x", scheme=sk.SCHEME_WITHIN)
    except ValueError as exc:
        raised2 = "meaningless at ROW_LEVEL" in str(exc)
    check("WITHIN scheme is REFUSED at ROW_LEVEL", raised2)

    raised3 = False
    try:
        sk.permutation_null(lambda d: 0.0, df, "grp", 5, 1, feature_col="x", scheme="sideways")
    except ValueError as exc:
        raised3 = "scheme must be" in str(exc)
    check("an unrecognised scheme raises rather than falling back to a default", raised3)

    # ---- calibration: the WITHIN null is EXACT for a group-demeaned statistic -------------
    # Group level is a confounder present in BOTH x and y; the true WITHIN effect is exactly zero.
    n_rep, n_dr, alpha = 80, 200, 0.05
    p_within = []
    for r in range(n_rep):
        rg = np.random.default_rng(5000 + r)
        u = rg.normal(0.0, 2.0, n_g)
        y = u[codes] + rg.normal(0.0, 1.0, n)
        xv = u[codes] * 1.5 + rg.normal(0.0, 1.0, n)      # shares the group level, no within link
        ym = y - (np.bincount(codes, weights=y) / cnt)[codes]
        d_ = pd.DataFrame({"grp": codes, "x": xv})

        def fwl(dd, _ym=ym):
            v = dd["x"].to_numpy(float)
            xm = v - (np.bincount(codes, weights=v) / cnt)[codes]
            sxx = float(xm @ xm)
            return abs(float(xm @ _ym) / sxx) if sxx > 1e-12 else 0.0

        p_within.append(sk.permutation_null(fwl, d_, "grp", n_dr, 700 + r,
                                            feature_col="x", scheme=sk.SCHEME_WITHIN,
                                            alternative="greater")["p"])
    p_within = np.array(p_within)
    rej = float((p_within <= alpha).mean())
    print("      %d replicates, %d within-group draws each, TRUE WITHIN-GROUP EFFECT = 0" % (n_rep, n_dr))
    print("      WITHIN-scheme rejection rate at alpha=0.05 : %.3f   mean p = %.3f (uniform => 0.5)"
          % (rej, p_within.mean()))
    check("WITHIN-scheme null is calibrated with a group-level confounder (rej <= 0.15)",
          rej <= 0.15, "rejection rate = %.3f" % rej)
    check("WITHIN-scheme p-values are ~uniform (mean p in [0.30, 0.70])",
          0.30 <= float(p_within.mean()) <= 0.70, "mean p = %.3f" % p_within.mean())


# ===========================================================================================
def test_paired_forecast_comparison_p4():
    """P4 REGRESSION (b).  Forecast-vs-forecast on the same rows is the shape EVERY skill
    comparison in this program has, and the kit shipped nothing for it.  Pre-fix,
    `sk.paired_forecast_comparison` does not exist and this whole test raises.
    """
    section("TEST 13 -- P4 REGRESSION: paired forecast-vs-forecast comparison")
    rng = np.random.default_rng(101)
    n_g, m = 25, 40
    codes = np.repeat(np.arange(n_g), m)
    n = n_g * m
    y = np.repeat(rng.normal(0.0, 1.0, n_g), m) + rng.normal(0.0, 1.0, n)
    a = 0.5 * y + rng.normal(0.0, 0.5, n)
    b = 0.5 * y + rng.normal(0.0, 1.2, n)                 # B is genuinely worse

    refused = False
    try:
        sk.paired_forecast_comparison(y, a, b, None, 50, 1)
    except ValueError as exc:
        refused = "REFUSES" in str(exc)
    check("paired_forecast_comparison REFUSES a None clustering level", refused)

    res = sk.paired_forecast_comparison(y, a, b, codes, 2000, 3,
                                        name_a="A", name_b="B", verbose=True)
    check("dR2 == r2_of_forecast(A) - r2_of_forecast(B) exactly",
          abs(res["dr2_a_minus_b"] - (sk.r2_of_forecast(y, a) - sk.r2_of_forecast(y, b))) < 1e-12,
          "|diff| = %.3e"
          % abs(res["dr2_a_minus_b"] - (sk.r2_of_forecast(y, a) - sk.r2_of_forecast(y, b))))
    check("the genuinely better forecast wins with a small clustered p",
          res["dr2_a_minus_b"] > 0 and res["p"] < 0.01,
          "dR2 = %+.6f, p = %.5f" % (res["dr2_a_minus_b"], res["p"]))

    # Comparing a forecast with ITSELF can never look significant: d == 0 for every row.
    same = sk.paired_forecast_comparison(y, a, a, codes, 500, 3)
    check("identical forecasts -> dR2 == 0.0 and p == 1.0 EXACTLY",
          same["dr2_a_minus_b"] == 0.0 and same["p"] == 1.0,
          "dR2 = %r, p = %r" % (same["dr2_a_minus_b"], same["p"]))

    # Antisymmetry: swapping the two forecasts negates dR2 exactly and leaves two-sided p alone.
    rev = sk.paired_forecast_comparison(y, b, a, codes, 2000, 3)
    check("swapping A and B negates dR2 exactly and preserves the two-sided p",
          abs(rev["dr2_a_minus_b"] + res["dr2_a_minus_b"]) < 1e-15 and rev["p"] == res["p"],
          "dR2 %+.8f vs %+.8f, p %.5f vs %.5f"
          % (rev["dr2_a_minus_b"], res["dr2_a_minus_b"], rev["p"], res["p"]))

    # THE TRAP-1 ANALOGUE FOR PAIRED TESTS.  Two EXCHANGEABLE forecasts (true difference zero),
    # clustered errors.  Flipping signs cluster-wise is exact; flipping them row-wise is the
    # paired twin of the naive row-level permutation null and over-rejects for the same reason.
    n_rep, n_dr, alpha = 200, 300, 0.05
    pc, pr, infl = [], [], []
    for r in range(n_rep):
        rg = np.random.default_rng(9100 + r)
        u = rg.normal(0.0, 1.0, n_g)
        yy = u[codes] + rg.normal(0.0, 1.0, n)
        fa = np.repeat(rg.normal(0.0, 1.0, n_g), m)       # cluster-constant, independent of y
        fb = np.repeat(rg.normal(0.0, 1.0, n_g), m)       # ... and exchangeable with fa
        rr = sk.paired_forecast_comparison(yy, fa, fb, codes, n_dr, 4200 + r)
        pc.append(rr["p"])
        pr.append(rr["p_row_level_NAIVE"])
        infl.append(rr["inflation"])
    pc, pr, infl = np.array(pc), np.array(pr), np.array(infl)
    rej_c, rej_r = float((pc <= alpha).mean()), float((pr <= alpha).mean())
    print("      %d replicates, %d sign-flip draws each, TWO EXCHANGEABLE FORECASTS (true dR2 = 0)"
          % (n_rep, n_dr))
    print("      rejection rate at alpha=0.05 -- CLUSTER sign-flip : %.3f   (nominal %.2f)"
          % (rej_c, alpha))
    print("      rejection rate at alpha=0.05 -- NAIVE ROW flip    : %.3f   [CONTRAST ONLY]" % rej_r)
    print("      cluster p-values: mean %.3f  median %.3f   null-width inflation median %.2fx"
          % (pc.mean(), np.median(pc), np.median(infl)))
    check("CLUSTER sign-flip null is calibrated (rejection rate <= 0.12)", rej_c <= 0.12,
          "cluster rejection rate = %.3f" % rej_c)
    check("NAIVE row-wise sign flip OVER-REJECTS (rate >= 0.20 with true dR2 = 0)", rej_r >= 0.20,
          "row-level rejection rate = %.3f" % rej_r)
    check("cluster p-values are ~uniform (mean p in [0.30, 0.70])",
          0.30 <= float(pc.mean()) <= 0.70, "mean p = %.3f" % pc.mean())
    check("the row-wise null is measurably TOO NARROW (median inflation > 2x)",
          float(np.median(infl)) > 2.0, "median sd_cluster/sd_row = %.2fx" % np.median(infl))


# ===========================================================================================
# REGRESSION TESTS FOR THE THREE DEFECTS + ONE USAGE NIT FOUND BY THE KIT'S SECOND AND THIRD
# REAL USERS (E0_I0016_efficiency_predictors and the screen alongside it).
#
# Each of TEST 14-17 FAILS against the pre-fix screenkit.py (git 56dc793).  The 100-assertion
# suite passed while `assert_partition` RAISED ON CLEAN DATA for any frame with a column named
# `candidate`, because no fixture ever contained one.  Same lesson as P1: close the blind spot.
# ===========================================================================================

def test_date_branch_value_gate_k0():
    """K0 REGRESSION -- THE PRIORITY, AND THE FOURTH NAME-BASED FALSE HIT IN THIS PROGRAM.

    Pre-fix, `assert_partition` auto-detected date columns by `"date" in name.lower()`, and THE
    WORD "candi-DATE" CONTAINS "date".  `pd.to_datetime` on a float column does not raise -- it
    reads the values as epoch nanoseconds and returns 1970-01-01 -- and 1970 is outside every real
    partition, so a frame whose every value sat inside 2021-2024 raised `PartitionViolation`.

    The defect is an ASYMMETRY: the SEASON branch already had `_is_season_valued` (with the
    `_team_season_2025` regression test in TEST 6); the DATE branch had no equivalent.  These
    assertions pin the symmetry, and they pin that the obvious workaround (`date_cols=[]`) did not
    become the fix.
    """
    section("TEST 14 -- K0 REGRESSION: assert_partition raised on CLEAN data ('candi-DATE')")

    # ---- the reporter's frame, verbatim in shape.  Every value is inside 2021-2024. ----------
    clean = pd.DataFrame({
        "season": [2021, 2022, 2023, 2024],
        "game_date": pd.to_datetime(["2021-06-01", "2022-06-01", "2023-06-01", "2024-06-01"]),
        "candidate": ["A01_opp_efg_allowed", "B05_matchup_fouldraw",
                      "C07_pl_usage_rank", "G01_noise"],
        "mae_with_candidate": [0.1234, 0.2345, 0.3456, 0.4567],
        "n_candidates": [44, 44, 44, 44],
        "update_flag": [0, 1, 0, 1],
        "validated": [True, True, False, True],
    })
    print("      columns whose NAME contains the substring 'date':")
    for c in clean.columns:
        if "date" in str(c).lower():
            print("        %-22s dtype=%-16s <- 'date' in name" % (c, clean[c].dtype))

    err = None
    rep = None
    try:
        rep = sk.assert_partition(clean, verbose=True)
    except Exception as exc:                                # noqa: BLE001
        err = exc
    check("PASSES on a clean 2021-2024 frame containing a column named `candidate`",
          err is None and rep is not None and rep["ok"] is True,
          "raised %s" % type(err).__name__ if err is not None
          else "violations = %s" % rep["violations"])

    if rep is not None:
        for col in ("candidate", "mae_with_candidate", "n_candidates", "update_flag", "validated"):
            check("name-only 'date' match %-20s is SKIPPED, not checked" % ("`%s`" % col),
                  col in rep["skipped_name_only"] and col not in rep["checked_date_cols"],
                  "skipped=%s checked=%s" % (col in rep["skipped_name_only"],
                                             col in rep["checked_date_cols"]))
        check("the REAL date column is still checked and its years reported",
              rep["checked_date_cols"].get("game_date") == [2021, 2022, 2023, 2024],
              "checked_date_cols = %s" % rep["checked_date_cols"])
        check("the epoch-nanosecond reading is refused BY NAME in the skip reason",
              "NUMERIC" in rep["skipped_name_only"].get("mae_with_candidate", "")
              and "epoch" in rep["skipped_name_only"].get("mae_with_candidate", "").lower(),
              "reason = %s" % rep["skipped_name_only"].get("mae_with_candidate", "")[:70])

    # ---- THE ASYMMETRY, stated side by side (the reporter's REPRO 3) -------------------------
    asym = pd.DataFrame({
        "season": [2021, 2022],
        "_team_season_2025": [1.2e-4, 3.4e-4],      # name season-like, values are dR2 draws
        "candidate_mae": [0.11, 0.22],              # name date-like (candi-DATE), values are MAEs
    })
    rep_a = sk.assert_partition(asym, raise_on_violation=False, verbose=True)
    check("SYMMETRY: the season branch AND the date branch both skip a name-only match",
          "_team_season_2025" in rep_a["skipped_name_only"]
          and "candidate_mae" in rep_a["skipped_name_only"]
          and rep_a["ok"] is True,
          "skipped = %s, violations = %s" % (sorted(rep_a["skipped_name_only"]),
                                             rep_a["violations"]))
    check("the two branches give the SAME 'name is X-like but VALUES are not' wording",
          "VALUES are" in rep_a["skipped_name_only"].get("_team_season_2025", "")
          and "VALUES are" in rep_a["skipped_name_only"].get("candidate_mae", ""))

    # ---- REQUIREMENT: THE TRUE CHECK MUST STAY LIVE -----------------------------------------
    real_violation = pd.DataFrame({
        "season": [2021, 2022],
        "game_date": pd.to_datetime(["2021-06-01", "2026-06-01"]),   # a GENUINE 2026 violation
        "candidate": ["A01", "B05"],
        "mae_with_candidate": [0.11, 0.22],
    })
    caught = False
    try:
        sk.assert_partition(real_violation)
    except sk.PartitionViolation as exc:
        caught = "2026" in str(exc)
    check("a GENUINE 2026 date is still caught (the fix did not disable the check)", caught)

    # ...AND THE WORKAROUND MUST NOT BE THE FIX.  `date_cols=[]` used to silence the true alarm
    # too; datetime-dtype columns are now checked regardless of `date_cols` (declared break B2).
    caught_off = False
    try:
        sk.assert_partition(real_violation, date_cols=[])
    except sk.PartitionViolation as exc:
        caught_off = "2026" in str(exc)
    check("date_cols=[] NO LONGER opens a false-pass door on a datetime column (B2)", caught_off)
    rep_optout = sk.assert_partition(real_violation, date_cols=[], raise_on_violation=False,
                                     include_datetime_dtype_cols=False)
    check("the pre-K0 behaviour is still reachable, but only by naming it explicitly",
          rep_optout["ok"] is True and rep_optout["checked_date_cols"] == {},
          "checked = %s" % rep_optout["checked_date_cols"])

    # A date column stored as STRINGS must still be parsed and checked.
    str_dates = pd.DataFrame({
        "season": [2021, 2026],
        "game_date": ["2021-06-01", "2026-06-01"],
        "candidate": ["A01", "B05"],
    })
    caught_str = False
    try:
        sk.assert_partition(str_dates)
    except sk.PartitionViolation as exc:
        caught_str = "2026" in str(exc)
    check("a STRING date column holding 2026 is still parsed and flagged", caught_str)

    # An EXPLICIT date_cols entry that is not date-valued must be LOUD, never silently skipped.
    err2 = None
    try:
        sk.assert_partition(clean, date_cols=["mae_with_candidate"])
    except Exception as exc:                                # noqa: BLE001
        err2 = exc
    check("explicitly naming a NON-date column in date_cols raises an actionable ValueError",
          isinstance(err2, ValueError) and not isinstance(err2, sk.PartitionViolation)
          and "pd.to_datetime" in str(err2),
          "%s: %s" % (type(err2).__name__, str(err2)[:60]))

    # ---- THE REPORTED NOISE: no UserWarning on a frame with an object column ------------------
    with warnings.catch_warnings(record=True) as caught_w:
        warnings.simplefilter("always")
        sk.assert_partition(clean)
        sk.assert_partition(asym, raise_on_violation=False)
    msgs = [str(x.message) for x in caught_w]
    check("assert_partition emits NO warnings at all (the 'Could not infer format' noise is gone)",
          msgs == [], "warnings = %s" % [m[:60] for m in msgs])

    # ---- the unit-level guard itself ---------------------------------------------------------
    ok_dt, yrs_dt, _ = sk._is_date_valued(pd.to_datetime(pd.Series(["2026-01-01"])))
    ok_f, _, why_f = sk._is_date_valued(pd.Series([0.1234, 0.2345]))
    ok_i, _, _ = sk._is_date_valued(pd.Series([1, 2, 3]))
    ok_s, yrs_s, _ = sk._is_date_valued(pd.Series(["2021-06-01", "2022-07-04"]))
    ok_j, _, _ = sk._is_date_valued(pd.Series(["A01_opp_efg", "B05_matchup"]))
    check("_is_date_valued: datetime64 accepted with NO year-range gate (2026 still checkable)",
          ok_dt is True and yrs_dt == {2026})
    check("_is_date_valued: a FLOAT column is refused outright (no epoch-nanosecond reading)",
          ok_f is False and "1970" in why_f)
    check("_is_date_valued: an INT column is refused outright too", ok_i is False)
    check("_is_date_valued: a string column of real dates is accepted",
          ok_s is True and yrs_s == {2021, 2022})
    check("_is_date_valued: a string column of feature ids is refused", ok_j is False)


# ===========================================================================================
def _persistence_frame(n_entities=80, n_games=40, seed=13):
    """Entities with a PERSISTENT true level, observed with noise.  Two baselines, BOTH strictly
    prior-games-only: a rolling-3 mean (noisy) and an expanding mean (better).  NEITHER reads the
    future -- both are built from `shift(1)` alone."""
    rng = np.random.default_rng(seed)
    rows = []
    for e in range(n_entities):
        mu = rng.normal(0.0, 1.0)
        for gi in range(n_games):
            rows.append({"entity_id": e, "season": 2023,
                         "game_date": pd.Timestamp("2023-05-01") + pd.Timedelta(days=2 * gi),
                         "game_id": gi, "y": mu + rng.normal(0.0, 1.0)})
    df = pd.DataFrame(rows)
    g = df.groupby(["entity_id", "season"], sort=False)["y"]
    df["refA_ppm"] = g.transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    df["refB_ppm"] = g.transform(lambda s: s.shift(1).expanding().mean())
    return df


def test_leakage_probe_states_only_what_it_licenses_k1():
    """K1 REGRESSION.  The probe used to assert, in its own verdict string, "That is only possible
    because it CONTAINS the future."  IT FIRED ON TWO STRICTLY PRIOR-GAMES-ONLY BASELINES that
    differ only as ESTIMATORS.  A caller trusting that wording would discard a clean baseline.

    Pre-fix this test fails on both halves: the false sentence is present, and the neutral fields
    (`screening_flag`, `status`, `alternative_explanation`) do not exist.
    """
    section("TEST 15 -- K1 REGRESSION: the leakage probe is a SCREEN, not a VERDICT")
    df = _persistence_frame()

    # Both baselines use shift(1) only.  Proof by construction: neither can see row i or later.
    g = df.groupby(["entity_id", "season"], sort=False)
    lag_ok = bool((g["game_id"].transform("max") >= df["game_id"]).all())
    check("fixture sanity: both baselines are built from shift(1) -- strictly prior games only",
          lag_ok and df["refA_ppm"].isna().sum() == df["refB_ppm"].isna().sum(),
          "both start NaN at each entity's first game")

    res = sk.future_leakage_probe(df, "refB_ppm", "refA_ppm",
                                  ["entity_id", "season"], "game_date", "y", verbose=True)

    # THE EMPIRICAL POINT: the probe FIRES on a pair where NOTHING reads the future.
    check("the probe FIRES on refB vs refA even though NEITHER reads the future",
          res["screening_flag"] is True,
          "corr %.4f vs %.4f, dR2 %.4f" % (res["corr_suspect_with_future"],
                                           res["corr_clean_with_future"],
                                           res["dr2_suspect_over_clean_predicting_future"]))
    check("the numbers are NOT weakened: both correlations and the dR2 are still reported",
          np.isfinite(res["corr_suspect_with_future"])
          and np.isfinite(res["corr_clean_with_future"])
          and res["dr2_suspect_over_clean_predicting_future"] > 0.01)

    # THE CLAIM ATTACHED TO THEM.
    check("the verdict NO LONGER says 'only possible because it CONTAINS the future'",
          "only possible because it" not in res["verdict"]
          and "CONTAINS the future" not in res["verdict"],
          "verdict starts: %s..." % res["verdict"][:52])
    check("the verdict names itself a SCREENING FLAG and denies being a verdict",
          "SCREENING FLAG" in res["verdict"] and "NOT A VERDICT" in res["verdict"])
    check("the verdict offers the BETTER-ESTIMATOR explanation as an equal alternative",
          "BETTER ESTIMATOR" in res["verdict"] and "persist" in res["verdict"].lower()
          and "CANNOT TELL THEM APART" in res["verdict"])
    check("the verdict tells the caller NOT to discard a baseline on this alone",
          "not" in res["verdict"].lower() and "discard a baseline" in res["verdict"])
    check("status is the ambiguity-naming constant, not a leakage finding",
          res["status"] == sk.SCREEN_FLAG_AMBIGUOUS
          and "ALSO_CONSISTENT_WITH_A_BETTER_ESTIMATOR" in res["status"],
          "status = %s" % res["status"])
    check("alternative_explanation is carried as its own field",
          isinstance(res["alternative_explanation"], str)
          and "PERSISTS" in res["alternative_explanation"].upper())
    check("the legacy `reads_future` field is preserved with its value unchanged",
          res["reads_future"] == res["screening_flag"])

    # THE TRUE POSITIVE MUST STILL FIRE, and its verdict must still be strong about what to check.
    rng = np.random.default_rng(19)
    rows = []
    for p in range(60):
        mu = rng.normal(0.0, 1.0)
        for gi in range(30):
            rows.append({"player_id": p, "season": 2023,
                         "game_date": pd.Timestamp("2023-05-01") + pd.Timedelta(days=2 * gi),
                         "y": mu + rng.normal(0.0, 1.0)})
    leaky = pd.DataFrame(rows)
    gl = leaky.groupby(["player_id", "season"], sort=False)["y"]
    tot, cnt = gl.transform("sum"), gl.transform("count")
    leaky["baseline_loo"] = (tot - leaky["y"]) / (cnt - 1)        # READS THE FUTURE
    leaky["baseline_pregame"] = gl.transform(lambda s: s.shift(1).expanding().mean())
    res_leak = sk.future_leakage_probe(leaky, "baseline_loo", "baseline_pregame",
                                       ["player_id", "season"], "game_date", "y")
    check("the genuine leave-one-out leak is STILL flagged (no loss of sensitivity)",
          res_leak["screening_flag"] is True and res_leak["status"] == sk.SCREEN_FLAG_AMBIGUOUS)
    check("a NOT-flagged result names itself not-a-certificate",
          sk.future_leakage_probe(leaky, "baseline_pregame", "baseline_loo",
                                  ["player_id", "season"], "game_date", "y")["status"]
          == sk.SCREEN_NOT_FLAGGED)


# ===========================================================================================
def _entity_series_frame(n_entities=24, seed=29, n_seasons=2):
    """Entity-seasons of UNEQUAL length whose feature is an EXPANDING PRIOR -- so it varies WITHIN
    the entity-season AND carries its signal at the entity level.  This is the shape for which the
    kit had no valid scheme (K2)."""
    rng = np.random.default_rng(seed)
    rows = []
    for e in range(n_entities):
        season = 2021 + (e % n_seasons)
        n_g = int(rng.integers(12, 30))                  # UNEQUAL series lengths
        level = rng.normal(0.0, 1.0)
        for gi in range(n_g):
            rows.append({"entity_id": e, "season": season,
                         "game_id": gi,
                         "game_date": pd.Timestamp("2021-05-01") + pd.Timedelta(days=3 * gi),
                         "obs": level + rng.normal(0.0, 1.0)})
    df = pd.DataFrame(rows)
    g = df.groupby(["entity_id", "season"], sort=False)["obs"]
    df["prior"] = g.transform(lambda s: s.shift(1).expanding().mean()).fillna(0.0)
    return df


def test_entity_swap_null_k2():
    """K2 REGRESSION.  Pre-fix, `sk.EntitySwap` and `sk.entity_swap_null` do not exist and this
    whole test raises `AttributeError`.  The gap was real, not misuse: for a within-varying feature
    `SCHEME_BETWEEN` requires constancy and `SCHEME_WITHIN` answers a different question, so the
    between-entity question had NO valid scheme.
    """
    section("TEST 16 -- K2 REGRESSION: entity_swap_null (the missing between-entity scheme)")
    df = _entity_series_frame()

    # ---- the gap, reproduced: NO candidate key is constant-within (the reporter's 132 cells) --
    lvl = sk.detect_grouping_level(
        df, "prior",
        candidate_keys={"entity_season": ["entity_id", "season"], "game": ["game_id"],
                        "season": ["season"]})
    check("the K2 shape: the feature is constant within NO candidate key",
          lvl["constant_levels"] == [] and lvl["status"] == sk.STATUS_NO_COARSER_LEVEL,
          "constant levels = %s" % lvl["constant_levels"])

    swapper = sk.EntitySwap(df, ["entity_id", "season"], date_col="game_date",
                            season_col="season", tiebreak_col="game_id")
    check("EntitySwap groups the frame into one series per entity-season",
          swapper.n_groups == df.groupby(["entity_id", "season"], sort=False).ngroups
          and swapper.n_seasons == df["season"].nunique(),
          "%d groups over %d seasons" % (swapper.n_groups, swapper.n_seasons))
    check("the fixture really has UNEQUAL series lengths (the proportional map is exercised)",
          len(set(swapper.group_sizes.tolist())) > 1,
          "sizes %d..%d" % (swapper.group_sizes.min(), swapper.group_sizes.max()))

    # ---- STRUCTURAL GUARANTEES, checked with a value that ENCODES its own provenance ----------
    # Each row carries `entity_code * 1000 + position_in_series`, so a draw can be decoded exactly.
    # `_group_codes` is the same helper EntitySwap uses, and EntitySwap orders its groups by code,
    # so the code IS the group index.  (Asserted immediately below rather than assumed.)
    ecodes = sk._group_codes(df, ["entity_id", "season"])
    check("EntitySwap group i holds exactly the rows of entity-season code i",
          all(set(np.flatnonzero(ecodes == gi)) == set(idx.tolist())
              for gi, idx in enumerate(swapper.groups)))
    pos = np.empty(len(df), dtype=float)
    for gi, idx in enumerate(swapper.groups):
        pos[idx] = np.arange(len(idx))
    tag = ecodes * 1000.0 + pos
    season_of_code = {int(c): int(s) for c, s in zip(ecodes, df["season"].to_numpy())}

    rng = np.random.default_rng(4)
    n_bad_season, n_first, n_last, n_moved = 0, 0, 0, 0
    for _ in range(20):
        d = swapper.draw(tag, rng)
        src_code = (d // 1000).astype(int)
        src_pos = (d % 1000).astype(int)
        # (a) never crosses a season
        for i in range(len(d)):
            if season_of_code[src_code[i]] != int(df["season"].iloc[i]):
                n_bad_season += 1
        # (b) endpoints map to endpoints
        for gi, idx in enumerate(swapper.groups):
            partner = src_code[idx[0]]
            n_first += int(src_pos[idx[0]] != 0)
            n_last += int(src_pos[idx[-1]] != swapper.group_sizes[partner] - 1)
        n_moved += int((src_code != ecodes).sum())
    check("EntitySwap NEVER swaps across a season block", n_bad_season == 0,
          "%d cross-season assignments in 20 draws" % n_bad_season)
    check("position 0 always receives the partner's position 0", n_first == 0)
    check("the last position always receives the partner's LAST position", n_last == 0)
    check("draws really move values between entities (not a silent identity)", n_moved > 0,
          "%d rows reassigned across 20 draws" % n_moved)

    # a single-entity season block returns that entity's own values back, exactly
    solo = df[(df["entity_id"] == df["entity_id"].iloc[0]) & (df["season"] == 2021)].copy()
    solo_swap = sk.EntitySwap(solo, ["entity_id", "season"], date_col="game_date",
                              season_col="season", tiebreak_col="game_id")
    solo_vals = solo["prior"].to_numpy(float)
    check("a season block with ONE entity yields that entity's own series back, exactly",
          np.array_equal(solo_swap.draw(solo_vals, np.random.default_rng(0)), solo_vals))

    # an entity that spans seasons is refused rather than silently assigned to one
    spanning = pd.DataFrame({
        "entity_id": [1, 1, 2, 2],
        "season": [2021, 2022, 2021, 2022],           # entity 1 appears in BOTH seasons
        "game_date": pd.to_datetime(["2021-06-01", "2022-06-01", "2021-06-02", "2022-06-02"]),
        "v": [0.1, 0.2, 0.3, 0.4],
    })
    refused = False
    try:
        sk.EntitySwap(spanning, ["entity_id"], date_col="game_date", season_col="season")
    except ValueError as exc:
        refused = "spans more than one" in str(exc)
    check("an entity spanning more than one season RAISES rather than being silently assigned",
          refused)
    ok_spanning = sk.EntitySwap(spanning, ["entity_id", "season"], date_col="game_date",
                                season_col="season")
    check("...and putting the season INTO entity_cols is accepted, as the message advises",
          ok_spanning.n_groups == 4 and ok_spanning.n_seasons == 2)

    # ---- the driver: calibration under a TRUE BETWEEN-ENTITY EFFECT OF ZERO ------------------
    n_rep, n_dr, alpha = 60, 200, 0.05
    ps = []
    for r in range(n_rep):
        rg = np.random.default_rng(6100 + r)
        d = df.copy()
        # outcome carries an entity level, but one INDEPENDENT of the candidate -> true effect 0
        ent_u = rg.normal(0.0, 1.5, swapper.n_groups)
        yv = np.empty(len(d))
        for gi, idx in enumerate(swapper.groups):
            yv[idx] = ent_u[gi]
        d["y"] = yv + rg.normal(0.0, 1.0, len(d))

        def stat(dd):
            return sk.r2_plain(dd["y"].to_numpy(float), dd["prior"].to_numpy(float))

        ps.append(sk.entity_swap_null(stat, d, ["entity_id", "season"], n_dr, 800 + r,
                                      feature_col="prior", date_col="game_date",
                                      season_col="season", tiebreak_col="game_id",
                                      swapper=swapper, alternative="greater")["p"])
    ps = np.array(ps)
    rej = float((ps <= alpha).mean())
    print("      %d replicates, %d entity-swap draws each, TRUE BETWEEN-ENTITY EFFECT = 0"
          % (n_rep, n_dr))
    print("      entity-swap rejection rate at alpha=0.05 : %.3f   mean p = %.3f (uniform => 0.5)"
          % (rej, ps.mean()))
    check("entity_swap_null is calibrated with an entity-level outcome (rejection <= 0.15)",
          rej <= 0.15, "rejection rate = %.3f" % rej)
    check("entity-swap p-values are ~uniform (mean p in [0.30, 0.70])",
          0.30 <= float(ps.mean()) <= 0.70, "mean p = %.3f" % ps.mean())

    # ---- power: a REAL between-entity effect is detected -------------------------------------
    rg = np.random.default_rng(77)
    d2 = df.copy()
    lvl_by_group = np.empty(len(d2))
    for gi, idx in enumerate(swapper.groups):
        lvl_by_group[idx] = d2["prior"].to_numpy(float)[idx].mean()
    d2["y"] = 1.2 * lvl_by_group + rg.normal(0.0, 1.0, len(d2))

    def stat2(dd):
        return sk.r2_plain(dd["y"].to_numpy(float), dd["prior"].to_numpy(float))

    hit = sk.entity_swap_null(stat2, d2, ["entity_id", "season"], 400, 9,
                              feature_col="prior", date_col="game_date", season_col="season",
                              tiebreak_col="game_id", swapper=swapper, verbose=True)
    check("a REAL between-entity effect is detected (p < 0.01)", hit["p"] < 0.01,
          "real = %.4f, null mean = %.4f, p = %.5f" % (hit["real"], hit["mean"], hit["p"]))
    check("the null is NOT degenerate: the draws have real spread",
          hit["sd"] > 1e-6 and hit["n_finite_draws"] == 400,
          "sd = %.6g over %d finite draws" % (hit["sd"], hit["n_finite_draws"]))
    check("the result labels its scheme and carries the between-only warning",
          hit["scheme"] == sk.SCHEME_ENTITY_SWAP and hit["is_row_level_naive"] is False
          and "BETWEEN-ENTITY question only" in hit["warning"])
    check("p is the add-one estimator and can never be 0", hit["p"] >= 1.0 / (400 + 1.0))

    # ---- refusal + reuse contracts -----------------------------------------------------------
    ref = False
    try:
        sk.entity_swap_null(stat2, d2, None, 5, 1, feature_col="prior", date_col="game_date")
    except ValueError as exc:
        ref = "REFUSES" in str(exc)
    check("entity_swap_null REFUSES a None entity level, mirroring permutation_null", ref)

    ref2 = False
    try:
        sk.entity_swap_null(stat2, d2.iloc[:50], ["entity_id", "season"], 5, 1,
                            feature_col="prior", date_col="game_date", swapper=swapper)
    except ValueError as exc:
        ref2 = "cannot be reused" in str(exc)
    check("a swapper built on a differently-shaped frame is REFUSED, not silently misapplied", ref2)

    # ---- a BOOLEAN feature is handed back as bool, matching permutation_null -----------------
    d3 = df.copy()
    d3["flag"] = d3["prior"] > 0
    seen = []

    def stat_bool(dd):
        seen.append(str(dd["flag"].dtype))
        return float(dd.loc[dd["flag"], "prior"].mean() - dd.loc[~dd["flag"], "prior"].mean())

    rb = sk.entity_swap_null(stat_bool, d3, ["entity_id", "season"], 15, 2,
                             feature_col="flag", date_col="game_date", season_col="season",
                             tiebreak_col="game_id")
    check("a BOOLEAN feature is permuted and handed back to stat_fn AS BOOL",
          set(seen) == {"bool"} and rb["feature_is_boolean"] is True and np.isfinite(rb["real"]),
          "dtypes seen = %s" % sorted(set(seen)))


# ===========================================================================================
def test_candidate_keys_must_be_a_mapping_k3():
    """K3 REGRESSION (the reported usage nit).  Pre-fix, a list reached `.items()` and died with
    `AttributeError: 'list' object has no attribute 'items'` -- which names neither the parameter
    nor the required shape.  An AttributeError is not a TypeError, so this check fails pre-fix.
    """
    section("TEST 17 -- K3 REGRESSION: candidate_keys must be a mapping, with a clear error")
    df = _game_frame()

    err = None
    try:
        sk.detect_grouping_level(df, "game_pace", candidate_keys=["game_id"])
    except Exception as exc:                                # noqa: BLE001
        err = exc
    print("      raised: %s: %s" % (type(err).__name__, str(err)[:88]))
    check("a LIST raises TypeError, not a bare AttributeError",
          isinstance(err, TypeError), "got %s" % type(err).__name__)
    check("the message names the parameter, the type received, and the required shape",
          err is not None and "candidate_keys" in str(err) and "list" in str(err)
          and "MAPPING" in str(err).upper() and "{" in str(err),
          "message is %d chars" % len(str(err) if err else ""))
    check("the message shows the caller how to fix it with their own column name",
          err is not None and "'game_id'" in str(err).replace('"', "'"))

    err2 = None
    try:
        sk.detect_grouping_level(df, "game_pace", candidate_keys=("game_id", "team_id"))
    except Exception as exc:                                # noqa: BLE001
        err2 = exc
    check("a TUPLE is rejected the same way", isinstance(err2, TypeError))

    # POSITIVE CONTROLS: a proper mapping still works, and the default still works.
    ok = sk.detect_grouping_level(df, "game_pace", candidate_keys={"game": ["game_id"]})
    check("a proper mapping still works unchanged",
          ok["recommended_permutation_level"] == "game"
          and ok["levels"]["game"]["constant_within"] is True)
    check("omitting candidate_keys still uses DEFAULT_CANDIDATE_KEYS",
          set(sk.detect_grouping_level(df, "game_pace")["levels"])
          | set(sk.detect_grouping_level(df, "game_pace")["skipped"])
          == set(sk.DEFAULT_CANDIDATE_KEYS))


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
        # regression tests for the four issues found by the kit's first user (E0_I0015)
        test_boolean_feature_p1,
        test_row_recommendation_is_not_an_endorsement_p2,
        test_r2_of_forecast_p3,
        test_within_scheme_and_var_share_p4,
        test_paired_forecast_comparison_p4,
        # regression tests for the three defects + one usage nit found by the kit's SECOND and
        # THIRD users (E0_I0016_efficiency_predictors and the screen alongside it)
        test_date_branch_value_gate_k0,
        test_leakage_probe_states_only_what_it_licenses_k1,
        test_entity_swap_null_k2,
        test_candidate_keys_must_be_a_mapping_k3,
    ]

    # Optional name filter, e.g. `python TESTS.py p1 p2` -- used to demonstrate that each new
    # regression test FAILS against the pre-fix screenkit.py without waiting for the full suite.
    sel = [a for a in sys.argv[1:] if not a.startswith("-")]
    if sel:
        tests = [t for t in tests if any(s in t.__name__ for s in sel)]
        print("  RUNNING A SUBSET: %s" % ", ".join(t.__name__ for t in tests))

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
