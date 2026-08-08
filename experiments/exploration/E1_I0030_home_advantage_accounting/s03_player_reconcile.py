"""S03 -- STEP 3.  PUSH THE TEAM EFFECT TO PLAYER LEVEL AND RECONCILE THE ACCOUNTING.

THE EXACT IDENTITY THIS STAGE RESTS ON.  Let H be the set of home team-games and A the set of away
team-games, |H| = |A| = N.  Then

    mean_H(team points) = (1/N) sum_{g in H} sum_i pts_{i,g}
                        = sum_i (m_i^H / N) * pbar_i^H
                        = sum_i f_i^H * pbar_i^H

where m_i^H is the number of home team-games in which player i appeared, f_i^H = m_i^H / N is that
player's APPEARANCE RATE per home team-game, and pbar_i^H is their mean points in those games.  So

    G = mean_H - mean_A = sum_i [ f_i^H * pbar_i^H  -  f_i^A * pbar_i^A ]
      = sum_i fbar_i * (pbar_i^H - pbar_i^A)      <-- WITHIN-PLAYER effect (rate)
      + sum_i pbar_i_bar * (f_i^H - f_i^A)        <-- COMPOSITION effect (who is on the floor)

with fbar_i = (f_i^H + f_i^A)/2 and pbar_i_bar = (pbar_i^H + pbar_i^A)/2.  Expanding shows the two
terms sum to G with NO residual.  THIS IS THE RECONCILIATION.  It cannot come back "nothing": both
sides are arithmetic, so the only question is which term holds the effect.

The within-player term is then split again, exactly, into MINUTES and POINTS-PER-MINUTE, because
pbar_i = mbar_i * ppm_i where ppm_i = (sum of points)/(sum of minutes) over that player's games in
that venue type.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

import ha_base as hb
import s00_prereg
import screenkit as sk

N_DRAWS = 20000


def two_way(Xh, Xa, Yh, Ya):
    """d(X*Y) = Ybar*dX + Xbar*dY, exactly.  Returns (total, dX_part, dY_part, residual)."""
    Xh, Xa, Yh, Ya = [np.asarray(v, float) for v in (Xh, Xa, Yh, Ya)]
    tot = Xh * Yh - Xa * Ya
    px = ((Yh + Ya) / 2.0) * (Xh - Xa)
    py = ((Xh + Xa) / 2.0) * (Yh - Ya)
    return tot, px, py, tot - px - py


def main():
    hb.hdr("S03 PLAYER-LEVEL RECONCILIATION")
    prereg = s00_prereg.assert_prereg_unchanged()
    FIND = {"prereg_sha256": prereg["prereg_sha256"], "n_draws": N_DRAWS}

    p = pd.read_parquet(os.path.join(hb.OUT, "_player_frame.parquet"))
    t = pd.read_parquet(os.path.join(hb.OUT, "_team_frame.parquet"))
    sk.assert_partition(p[["season", "game_date"]], verbose=False)
    sk.assert_partition(t[["season", "game_date"]], verbose=False)

    # ---- headline stratum: REGULAR SEASON.  DISCLOSED REASON:
    # in the playoffs home court is AWARDED to the better seed, so the home team is systematically
    # the stronger team and the paired contrast is a strength contrast, not a venue contrast.  s02
    # measured that stratum at +5.68 points -- 5.9x the regular-season figure -- which is the
    # signature of exactly that confound.  The playoff number is reported and labelled, never
    # pooled into the headline.
    REG = "Regular Season"
    p = p[p["season_type"] == REG].copy()
    t = t[t["season_type"] == REG].copy()
    games = sorted(t["game_id"].unique())
    print("  regular-season partition: %d games, %d team-games, %d player-rows"
          % (len(games), len(t), len(p)))

    # ================================================================== A. the exact reconciliation
    hb.hdr("A. THE RECONCILIATION -- both sides and the residual")
    N_H = int((t["is_home"] == 1).sum())
    N_A = int((t["is_home"] == 0).sum())
    print("  N_home team-games = %d   N_away team-games = %d" % (N_H, N_A))

    team_mean_h = float(t.loc[t.is_home == 1, "pts"].mean())
    team_mean_a = float(t.loc[t.is_home == 0, "pts"].mean())
    G = team_mean_h - team_mean_a
    print("  TEAM SIDE:  mean home pts = %.5f   mean away pts = %.5f   G = %+.6f"
          % (team_mean_h, team_mean_a, G))

    app = p[p["appeared"] == 1].copy()
    agg = (app.groupby(["player_id", "is_home"])
              .agg(m=("pts", "size"), pts_sum=("pts", "sum"), min_sum=("minutes", "sum"),
                   fga_sum=("fga", "sum"), fta_sum=("fta", "sum"), fg3a_sum=("fg3a", "sum"),
                   fgm_sum=("fgm", "sum"), fg3m_sum=("fg3m", "sum"), ftm_sum=("ftm", "sum"))
              .reset_index())
    wide = agg.pivot(index="player_id", columns="is_home").fillna(0.0)
    wide.columns = ["%s_%s" % (a, "h" if b == 1 else "a") for a, b in wide.columns]
    W = wide.reset_index()

    W["f_h"] = W["m_h"] / N_H
    W["f_a"] = W["m_a"] / N_A
    W["pbar_h"] = np.where(W["m_h"] > 0, W["pts_sum_h"] / W["m_h"].replace(0, np.nan), 0.0)
    W["pbar_a"] = np.where(W["m_a"] > 0, W["pts_sum_a"] / W["m_a"].replace(0, np.nan), 0.0)
    W["mbar_h"] = np.where(W["m_h"] > 0, W["min_sum_h"] / W["m_h"].replace(0, np.nan), 0.0)
    W["mbar_a"] = np.where(W["m_a"] > 0, W["min_sum_a"] / W["m_a"].replace(0, np.nan), 0.0)
    W["ppm_h"] = np.where(W["min_sum_h"] > 0, W["pts_sum_h"] / W["min_sum_h"].replace(0, np.nan), 0.0)
    W["ppm_a"] = np.where(W["min_sum_a"] > 0, W["pts_sum_a"] / W["min_sum_a"].replace(0, np.nan), 0.0)

    lhs_h = float((W["f_h"] * W["pbar_h"]).sum())
    lhs_a = float((W["f_a"] * W["pbar_a"]).sum())
    print("  PLAYER SIDE: sum_i f_i^H*pbar_i^H = %.5f   sum_i f_i^A*pbar_i^A = %.5f"
          % (lhs_h, lhs_a))
    print("  RECONSTRUCTION ERROR vs the team means: home %.3e  away %.3e"
          % (lhs_h - team_mean_h, lhs_a - team_mean_a))

    tot, part_f, part_p, resid = two_way(W["f_h"], W["f_a"], W["pbar_h"], W["pbar_a"])
    WITHIN = float(part_p.sum())
    COMPOSITION = float(part_f.sum())
    RESID = float(resid.sum())
    print("\n  *** THE RECONCILIATION ***")
    print("    team-level home effect G                     = %+.6f pts / game" % G)
    print("    (1) WITHIN-PLAYER  sum fbar_i*(pbar^H-pbar^A) = %+.6f   (%.1f%% of G)"
          % (WITHIN, 100 * WITHIN / G))
    print("    (2) COMPOSITION    sum pbar_bar*(f^H-f^A)     = %+.6f   (%.1f%% of G)"
          % (COMPOSITION, 100 * COMPOSITION / G))
    print("    (1)+(2)                                      = %+.6f" % (WITHIN + COMPOSITION))
    print("    RESIDUAL (must be ~0 by construction)        = %+.3e" % RESID)
    print("    |(1)+(2) - G|                                = %.3e"
          % abs(WITHIN + COMPOSITION - G))
    FIND["reconciliation_points"] = {
        "n_players": int(len(W)), "N_home_team_games": N_H, "N_away_team_games": N_A,
        "team_mean_home_pts": team_mean_h, "team_mean_away_pts": team_mean_a,
        "G_team_home_effect_pts": G,
        "player_side_home": lhs_h, "player_side_away": lhs_a,
        "reconstruction_error_home": lhs_h - team_mean_h,
        "reconstruction_error_away": lhs_a - team_mean_a,
        "within_player_rate_part": WITHIN,
        "composition_availability_part": COMPOSITION,
        "sum_of_parts": WITHIN + COMPOSITION,
        "residual": RESID,
        "abs_gap_to_G": abs(WITHIN + COMPOSITION - G),
        "share_within_player": WITHIN / G, "share_composition": COMPOSITION / G,
    }

    # ---- split the within-player term into minutes and points-per-minute, exactly
    hb.hdr("B. SPLITTING THE WITHIN-PLAYER TERM: minutes vs points-per-minute")
    fbar = (W["f_h"] + W["f_a"]) / 2.0
    tot2, part_m, part_r, resid2 = two_way(W["mbar_h"], W["mbar_a"], W["ppm_h"], W["ppm_a"])
    MIN_PART = float((fbar * part_m).sum())
    RATE_PART = float((fbar * part_r).sum())
    print("    WITHIN-PLAYER total                     = %+.6f" % WITHIN)
    print("      via MINUTES PER APPEARANCE            = %+.6f  (%.1f%% of the within term)"
          % (MIN_PART, 100 * MIN_PART / WITHIN))
    print("      via POINTS PER MINUTE                 = %+.6f  (%.1f%% of the within term)"
          % (RATE_PART, 100 * RATE_PART / WITHIN))
    print("      residual                              = %+.3e"
          % (WITHIN - MIN_PART - RATE_PART))
    FIND["within_player_split"] = {
        "within_total": WITHIN, "minutes_per_appearance_part": MIN_PART,
        "points_per_minute_part": RATE_PART,
        "residual": WITHIN - MIN_PART - RATE_PART,
        "share_minutes": MIN_PART / WITHIN, "share_ppm": RATE_PART / WITHIN}

    # ---- and the same identity applied to FREE THROWS MADE, the channel s02 identified
    hb.hdr("C. THE SAME RECONCILIATION ON FREE THROWS MADE (the channel s02 located)")
    W["fbar_h"] = np.where(W["m_h"] > 0, W["ftm_sum_h"] / W["m_h"].replace(0, np.nan), 0.0)
    W["fbar_a"] = np.where(W["m_a"] > 0, W["ftm_sum_a"] / W["m_a"].replace(0, np.nan), 0.0)
    W["fta_bar_h"] = np.where(W["m_h"] > 0, W["fta_sum_h"] / W["m_h"].replace(0, np.nan), 0.0)
    W["fta_bar_a"] = np.where(W["m_a"] > 0, W["fta_sum_a"] / W["m_a"].replace(0, np.nan), 0.0)
    G_ftm = float(t.loc[t.is_home == 1, "ftm"].mean() - t.loc[t.is_home == 0, "ftm"].mean())
    _, pf_f, pf_p, _ = two_way(W["f_h"], W["f_a"], W["fbar_h"], W["fbar_a"])
    print("    team-level FT-makes home effect          = %+.6f" % G_ftm)
    print("      within-player                          = %+.6f  (%.1f%%)"
          % (pf_p.sum(), 100 * pf_p.sum() / G_ftm))
    print("      composition                            = %+.6f  (%.1f%%)"
          % (pf_f.sum(), 100 * pf_f.sum() / G_ftm))
    G_fta = float(t.loc[t.is_home == 1, "fta"].mean() - t.loc[t.is_home == 0, "fta"].mean())
    _, pa_f, pa_p, _ = two_way(W["f_h"], W["f_a"], W["fta_bar_h"], W["fta_bar_a"])
    print("    team-level FT-ATTEMPTS home effect       = %+.6f" % G_fta)
    print("      within-player                          = %+.6f  (%.1f%%)"
          % (pa_p.sum(), 100 * pa_p.sum() / G_fta))
    print("      composition                            = %+.6f  (%.1f%%)"
          % (pa_f.sum(), 100 * pa_f.sum() / G_fta))
    FIND["reconciliation_ftm"] = {"G": G_ftm, "within": float(pf_p.sum()),
                                  "composition": float(pf_f.sum())}
    FIND["reconciliation_fta"] = {"G": G_fta, "within": float(pa_p.sum()),
                                  "composition": float(pa_f.sum())}

    # ---- IS THE COMPOSITION TERM REAL?  The same per-game sign flip, but the WHOLE decomposition
    # is recomputed on every draw.  Flipping which team is home preserves N_H = N_A = 888 exactly,
    # so f_i^H and f_i^A stay comparable draw to draw.  Without this the -0.349 is uninterpretable:
    # a term that is 36% of G in the wrong direction is either a real availability asymmetry or
    # pure roster noise, and the arithmetic alone cannot say which.
    hb.hdr("A2. NULL FOR THE DECOMPOSITION TERMS (whole decomposition recomputed per draw)")
    NC_DRAWS = 4000
    pid_codes, pid_uq = pd.factorize(app["player_id"])
    gid_codes, gid_uq = pd.factorize(app["game_id"])
    npl = len(pid_uq)
    ih = app["is_home"].to_numpy(float)
    ptsv = app["pts"].to_numpy(float)
    minv = app["minutes"].to_numpy(float)

    def decompose_from_labels(lab):
        w_h, w_a = lab, 1.0 - lab
        m_h = np.bincount(pid_codes, weights=w_h, minlength=npl)
        m_a = np.bincount(pid_codes, weights=w_a, minlength=npl)
        s_h = np.bincount(pid_codes, weights=w_h * ptsv, minlength=npl)
        s_a = np.bincount(pid_codes, weights=w_a * ptsv, minlength=npl)
        fh, fa = m_h / N_H, m_a / N_A
        with np.errstate(invalid="ignore", divide="ignore"):
            ph = np.where(m_h > 0, s_h / np.where(m_h > 0, m_h, 1.0), 0.0)
            pa = np.where(m_a > 0, s_a / np.where(m_a > 0, m_a, 1.0), 0.0)
        w = float((fh * ph - fa * pa).sum())
        within = float((((fh + fa) / 2.0) * (ph - pa)).sum())
        comp = float((((ph + pa) / 2.0) * (fh - fa)).sum())
        return w, within, comp

    g_real, w_real, c_real = decompose_from_labels(ih)
    assert abs(g_real - G) < 1e-9 and abs(w_real - WITHIN) < 1e-9
    rng = np.random.default_rng(hb.SEED)
    dg = np.empty(NC_DRAWS)
    dw = np.empty(NC_DRAWS)
    dc = np.empty(NC_DRAWS)
    for i in range(NC_DRAWS):
        flip = rng.integers(0, 2, size=len(gid_uq)).astype(float)[gid_codes]
        lab = np.where(flip > 0, 1.0 - ih, ih)
        dg[i], dw[i], dc[i] = decompose_from_labels(lab)
    nulls = {}
    for nm, real, dr in [("G", G, dg), ("within_player", WITHIN, dw),
                         ("composition", COMPOSITION, dc)]:
        p = (1.0 + int((np.abs(dr) >= abs(real) - 1e-12).sum())) / (NC_DRAWS + 1.0)
        nulls[nm] = {"real": float(real), "null_sd": float(dr.std(ddof=1)),
                     "null_mean": float(dr.mean()), "p_pergame_signflip": float(p),
                     "n_draws": NC_DRAWS}
        print("  %-16s real=%+.5f  null sd=%.5f  t=%+.2f  p=%.4f"
              % (nm, real, dr.std(ddof=1), real / dr.std(ddof=1), p))
    print("  -> the sign-flip preserves N_H=N_A=%d exactly, so the composition term is being"
          % N_H)
    print("     tested against its own honest null and not against zero.")
    FIND["decomposition_term_nulls"] = nulls
    pd.DataFrame({"G": dg, "within_player": dw, "composition": dc}).to_csv(
        os.path.join(hb.OUT, "permutation_draws_reconciliation.csv"), index=False)

    # ================================================================== D. per-player candidates
    hb.hdr("D. PLAYER-LEVEL HOME/AWAY CONTRASTS, per-game paired, correct-level null")
    # Build, per GAME, the home team's aggregate minus the away team's aggregate for each
    # player-level candidate.  The paired unit is still the GAME, so the null is still the per-game
    # sign flip.  Two aggregation weights are reported because they answer different questions:
    #   EQUAL   -- unweighted mean over the players who appeared (what "the average player" did)
    #   MINUTE  -- minute-weighted (what the team's minutes actually produced)
    rows = []
    tg = (app.groupby(["game_id", "team_id", "is_home"])
             .agg(n_used=("pts", "size"), pts=("pts", "sum"), minutes=("minutes", "sum"),
                  fga=("fga", "sum"), fta=("fta", "sum"), fg3a=("fg3a", "sum"),
                  fgm=("fgm", "sum"), fg3m=("fg3m", "sum"), ftm=("ftm", "sum"),
                  pts_eq=("pts", "mean"), min_eq=("minutes", "mean"),
                  fga_eq=("fga", "mean"), fta_eq=("fta", "mean"), fg3a_eq=("fg3a", "mean"),
                  ppm_eq=("ppm", "mean"), fgapm_eq=("fga_per_min", "mean"),
                  ftapm_eq=("fta_per_min", "mean"))
             .reset_index())
    tg["ppm_mw"] = tg["pts"] / tg["minutes"]
    tg["fga_per_min_mw"] = tg["fga"] / tg["minutes"]
    tg["fta_per_min_mw"] = tg["fta"] / tg["minutes"]
    tg["efg_pct"] = (tg["fgm"] + 0.5 * tg["fg3m"]) / tg["fga"].replace(0, np.nan)
    tg["ts_pct"] = tg["pts"] / (2.0 * (tg["fga"] + 0.44 * tg["fta"]))
    # minutes concentration and starter share
    hhi = (app.assign(share=lambda d: d["minutes"] /
                      d.groupby(["game_id", "team_id"])["minutes"].transform("sum"))
              .assign(sq=lambda d: d["share"] ** 2)
              .groupby(["game_id", "team_id"])["sq"].sum().rename("hhi_minutes"))
    st = (app.groupby(["game_id", "team_id"])
             .apply(lambda d: (d.loc[d["starter_flag"] == 1, "minutes"].sum()
                               / d["minutes"].sum()), include_groups=False)
             .rename("starter_minute_share"))
    tg = tg.merge(hhi, on=["game_id", "team_id"]).merge(st, on=["game_id", "team_id"])

    PLAYER_CELLS = [
        ("pts_eq", "mean player points (equal weight over players who appeared)"),
        ("min_eq", "mean player minutes"),
        ("ppm_eq", "mean player points-per-minute (equal weight)"),
        ("ppm_mw", "team points per team minute (minute-weighted ppm)"),
        ("fga_eq", "mean player FGA"),
        ("fga_per_min_mw", "FGA per minute, minute-weighted"),
        ("fgapm_eq", "mean player FGA-per-minute (equal weight)"),
        ("fta_eq", "mean player FTA"),
        ("fta_per_min_mw", "FTA per minute, minute-weighted"),
        ("ftapm_eq", "mean player FTA-per-minute (equal weight)"),
        ("fg3a_eq", "mean player 3PA"),
        ("efg_pct", "team effective FG%"),
        ("ts_pct", "team true shooting %"),
        ("n_used", "number of players who appeared"),
        ("hhi_minutes", "Herfindahl concentration of the minutes distribution"),
        ("starter_minute_share", "share of minutes taken by starters"),
    ]
    h = tg[tg.is_home == 1].set_index("game_id")
    a = tg[tg.is_home == 0].set_index("game_id")
    idx = h.index.intersection(a.index)
    for c, desc in PLAYER_CELLS:
        d = (pd.to_numeric(h.loc[idx, c], errors="coerce")
             - pd.to_numeric(a.loc[idx, c], errors="coerce")).to_numpy(float)
        r = hb.paired_game_signflip(d, N_DRAWS, hb.SEED)
        rows.append(dict(candidate=c, description=desc, n_games=r["n_games"],
                         home_mean=float(h.loc[idx, c].mean()),
                         away_mean=float(a.loc[idx, c].mean()),
                         diff=r["real"], null_sd=r["null_sd"],
                         t=r["real"] / r["null_sd"] if r["null_sd"] else np.nan,
                         p_pergame_signflip=r["p"]))
    pr = pd.DataFrame(rows)
    print(pr[["candidate", "n_games", "home_mean", "away_mean", "diff", "null_sd", "t",
              "p_pergame_signflip"]].to_string(index=False,
                                               float_format=lambda x: "%.5f" % x))

    # ---- the reconciliation rows, appended to the same CSV so both sides live together
    recon_rows = [
        dict(candidate="__RECON_G_team_pts", description="team-level home effect, points",
             diff=G, n_games=len(idx)),
        dict(candidate="__RECON_within_player", description="sum fbar*(pbar^H-pbar^A)",
             diff=WITHIN, n_games=len(idx)),
        dict(candidate="__RECON_composition", description="sum pbar_bar*(f^H-f^A)",
             diff=COMPOSITION, n_games=len(idx)),
        dict(candidate="__RECON_sum_of_parts", description="within + composition",
             diff=WITHIN + COMPOSITION, n_games=len(idx)),
        dict(candidate="__RECON_residual", description="sum_of_parts - G",
             diff=WITHIN + COMPOSITION - G, n_games=len(idx)),
        dict(candidate="__RECON_within_via_minutes", description="within term, minutes channel",
             diff=MIN_PART, n_games=len(idx)),
        dict(candidate="__RECON_within_via_ppm", description="within term, points-per-minute "
                                                             "channel", diff=RATE_PART,
             n_games=len(idx)),
    ]
    pr = pd.concat([pr, pd.DataFrame(recon_rows)], ignore_index=True)
    pr.to_csv(os.path.join(hb.OUT, "player_reconciliation.csv"), index=False)

    # ================================================================== E. hunting the leak
    hb.hdr("E. WHERE INSIDE THE PLAYER LEVEL DOES IT SIT?  (the leak hunt)")
    # per-player contribution to the WITHIN term, sorted
    W["contrib_within"] = fbar * (W["pbar_h"] - W["pbar_a"])
    W["contrib_comp"] = ((W["pbar_h"] + W["pbar_a"]) / 2.0) * (W["f_h"] - W["f_a"])
    W["games"] = W["m_h"] + W["m_a"]
    top = W.sort_values("contrib_within", ascending=False)
    print("  concentration of the within-player term:")
    cw = W["contrib_within"].to_numpy(float)
    order = np.argsort(-cw)
    cum = np.cumsum(cw[order])
    for k in [1, 5, 10, 25, 50, 100]:
        if k <= len(cw):
            print("    top %3d players of %d contribute %+.4f of %+.4f (%.0f%%)"
                  % (k, len(cw), cum[k - 1], WITHIN, 100 * cum[k - 1] / WITHIN))
    n_pos = int((cw > 0).sum())
    print("    players with a POSITIVE home contribution: %d of %d (%.1f%%)"
          % (n_pos, len(cw), 100.0 * n_pos / len(cw)))
    FIND["within_term_concentration"] = {
        "n_players": int(len(cw)), "n_positive": n_pos,
        "frac_positive": float(n_pos / len(cw)),
        "top10_share_of_within": float(cum[9] / WITHIN) if len(cw) > 10 else None,
        "top50_share_of_within": float(cum[49] / WITHIN) if len(cw) > 50 else None,
    }

    # by minutes tier (a role split, computed from realised minutes -- a DESCRIPTION, not a feature)
    app2 = app.copy()
    med = app2.groupby("player_id")["minutes"].mean().rename("mpg")
    app2 = app2.merge(med, on="player_id")
    app2["tier"] = pd.cut(app2["mpg"], [-0.01, 10, 20, 28, 100],
                          labels=["bench <10", "rotation 10-20", "starter 20-28", "star >28"])
    tier = (app2.groupby(["tier", "is_home"], observed=True)
                .agg(n=("pts", "size"), pts=("pts", "mean"), minutes=("minutes", "mean"),
                     fta=("fta", "mean"), ftm=("ftm", "mean"), fga=("fga", "mean"))
                .reset_index())
    tw = tier.pivot(index="tier", columns="is_home")
    print("\n  BY MINUTES TIER (home minus away, per appearance):")
    for c in ["pts", "minutes", "fta", "ftm", "fga"]:
        print("    %-8s %s" % (c, {str(i): round(float(tw[(c, 1)][i] - tw[(c, 0)][i]), 4)
                                   for i in tw.index}))
    FIND["by_minutes_tier"] = {
        str(i): {c: float(tw[(c, 1)][i] - tw[(c, 0)][i])
                 for c in ["pts", "minutes", "fta", "ftm", "fga"]} for i in tw.index}
    tw.to_csv(os.path.join(hb.OUT, "by_minutes_tier.csv"))

    # blowout / garbage time check: does the minutes distribution differ?
    hb.hdr("F. BLOWOUT AND ROTATION CHECKS -- the leaks the brief named")
    marg = (t[t.is_home == 1].set_index("game_id")["pts"]
            - t[t.is_home == 0].set_index("game_id")["pts"]).rename("margin")
    tg2 = tg.merge(marg, on="game_id")
    tg2["abs_margin"] = tg2["margin"].abs()
    hw = float((marg > 0).mean())
    print("  home team wins %.2f%% of regular-season games (n=%d)" % (100 * hw, len(marg)))
    print("  mean |margin| = %.2f" % float(marg.abs().mean()))
    for c in ["n_used", "hhi_minutes", "starter_minute_share"]:
        dd = (tg2[tg2.is_home == 1].set_index("game_id")[c]
              - tg2[tg2.is_home == 0].set_index("game_id")[c])
        r = hb.paired_game_signflip(dd.to_numpy(float), N_DRAWS, hb.SEED)
        print("  %-22s home-minus-away = %+.5f   p=%.4f" % (c, r["real"], r["p"]))
    # close games only -- if the effect is garbage time it should vanish here
    close_ids = marg.index[marg.abs() <= 8]
    print("\n  CLOSE GAMES ONLY (|margin| <= 8, n=%d):" % len(close_ids))
    tc = t[t["game_id"].isin(close_ids)]
    for c in ["pts", "ftm", "fta", "pf", "fg3m"]:
        dd = (tc[tc.is_home == 1].set_index("game_id")[c]
              - tc[tc.is_home == 0].set_index("game_id")[c])
        r = hb.paired_game_signflip(dd.to_numpy(float), N_DRAWS, hb.SEED)
        print("    %-6s = %+.4f  p=%.4f" % (c, r["real"], r["p"]))
        FIND.setdefault("close_games", {})[c] = {"diff": r["real"], "p": r["p"],
                                                 "n_games": r["n_games"]}
    FIND["home_win_rate_regular"] = hw
    FIND["mean_abs_margin"] = float(marg.abs().mean())

    W.to_csv(os.path.join(hb.OUT, "per_player_contributions.csv"), index=False)
    with open(os.path.join(hb.OUT, "_s03.json"), "w", encoding="utf-8") as fh:
        json.dump(hb.jsonable(FIND), fh, indent=2)
    print("\n  wrote player_reconciliation.csv, per_player_contributions.csv, "
          "by_minutes_tier.csv, _s03.json")


if __name__ == "__main__":
    main()
