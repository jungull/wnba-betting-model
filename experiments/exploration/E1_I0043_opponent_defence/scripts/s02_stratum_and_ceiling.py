"""
s02 -- THE DECISION-STRATUM INTERSECTION, THEN THE ARITHMETIC CEILING.  NO EFFECT SIZE HERE.

Order is preregistered and is not an accident:
  1. the intersection, because a gain on rows nobody bets on is not a gain (D119);
  2. the ceiling, because if 1 sd of the candidate cannot move the response past the detection
     floor then no fit is worth running and the channel closes on arithmetic (D084's route).

A matched PURE-NOISE control runs the identical path and its ceiling is printed beside every real
ceiling, because the ceiling statistic has a noise floor and E1_I0023 disclosed a value for it that
its own artifact contradicts (see DEFECTS.md D-01).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import od_base as ob  # noqa: E402

LOG = []
FLOOR_SINGLE = 0.00102          # D103, injection-verified, single preregistered cell
FLOOR_132 = 0.00235             # D103, injection-verified, 132-cell family
LARGEST_LIVE = 0.002057         # D089, the largest live effect the programme has measured


def P(x=""):
    print(x)
    LOG.append(str(x))


def main():
    ob.hdr("E1_I0043 s02 -- STEP 1 OF 2: THE DECISION-STRATUM INTERSECTION (before any effect size)")
    P("  PREREG.md sha256 %s" % ob.prereg_sha())
    m = ob.build_merged(verbose=True)
    m["_m_hat"] = m["prior5_minutes"].fillna(m["refB_mpg"])
    P("  _m_hat = prior5_minutes with refB_mpg fallback (D089's construction). "
      "NO realised minutes anywhere.")

    dec = ob.decision_mask(m)
    ssn = m["season"].to_numpy()
    need = list(dict.fromkeys(ob.BASE_B2_FAMILY + ob.CANDIDATE + ["y_ppm", "y_pts", "_m_hat"]))
    P("  RESOLVED column list for complete-casing (explicit allowlist, printed): %s" % need)
    assert len(need) == 13, "resolved list length %d != 13" % len(need)
    fin = ob.finite_mask(m, need)

    rows = []
    for lbl, msk in [("ALL_ROWS", np.ones(len(m), bool)),
                     ("DECISION", dec),
                     ("DECISION_COMPLETE_CASE", dec & fin),
                     ("DECISION_CC_EVAL_2023_24", dec & fin & np.isin(ssn, ob.CLEAN_EVAL_SEASONS)),
                     ("DECISION_CC_EVAL_2022_disclosed", dec & fin & (ssn == 2022)),
                     ("DECISION_CC_TRAIN_le2022", dec & fin & (ssn <= 2022))]:
        d = dict(population=lbl, n_rows=int(msk.sum()),
                 n_players=int(m.loc[msk, "player_id"].nunique()),
                 n_games=int(m.loc[msk, "game_id"].nunique()),
                 n_dates=int(m.loc[msk, "game_date"].nunique()),
                 n_opp_team_seasons=int(m.loc[msk, "opp_team_season"].nunique()),
                 n_seasons=int(m.loc[msk, "season"].nunique()),
                 pct_of_frame=100.0 * msk.sum() / len(m))
        rows.append(d)
        P("    %-32s n=%6d (%5.1f%% of frame)  players=%3d  opp_team_seasons=%2d  games=%3d  "
          "dates=%3d" % (lbl, d["n_rows"], d["pct_of_frame"], d["n_players"],
                         d["n_opp_team_seasons"], d["n_games"], d["n_dates"]))
    pd.DataFrame(rows).to_csv(os.path.join(ob.OUT, "DECISION_STRATUM.csv"), index=False)

    eval_mask = dec & fin & np.isin(ssn, ob.CLEAN_EVAL_SEASONS)
    nb = int(m.loc[eval_mask, "opp_team_season"].nunique())
    P("\n  BLOCK COUNT on the headline cell: %d opponent-team-seasons." % nb)
    P("    A two-sided SIGN-FLIP at %d blocks has p_min = 2^(1-nb) = %.3e -- not the binding "
      "constraint here, and this screen does not use a sign-flip for its verdict." % (nb, 2.0 ** (1 - nb)))
    P("    t_crit vs sqrt(nb): sqrt(%d) = %.3f. Any |t| above that on %d blocks would be "
      "arithmetically impossible for a block statistic, and none is quoted." % (nb, np.sqrt(nb), nb))
    P("    The verdict nulls are PERMUTATION nulls at %d exchangeable units, so p_min = "
      "1/(N_DRAWS+1) = %.3e." % (nb, 1.0 / (ob.N_DRAWS + 1)))
    assert nb >= 6, "below six blocks -- a two-sided test is arithmetically incapable"

    P("\n  INTERSECTION WITH EACH SIGHTING'S ROW SET (the D119 clause):")
    P("    S4 D117 measured on ALL 14,852 rows.  The decision stratum is %d of them (%.1f%%); "
      "%.1f%% of the rows behind sighting 4 are rows nobody would bet on."
      % (int(dec.sum()), 100.0 * dec.sum() / len(m), 100.0 * (1 - dec.sum() / len(m))))
    P("    S3 D103 / S2 D099 / S1 D098 are all INSIDE the decision stratum already.")
    P("    The clean-window eval set is %d rows -- %.1f%% of the decision stratum and %.1f%% of "
      "the frame." % (int(eval_mask.sum()), 100.0 * eval_mask.sum() / max(dec.sum(), 1),
                      100.0 * eval_mask.sum() / len(m)))

    # ---------------------------------------------------------------- CEILING
    ob.hdr("E1_I0043 s02 -- STEP 2 OF 2: THE ARITHMETIC CEILING (computed BEFORE any fit)")
    P("  BENCHMARKS frozen in PREREG before this number existed:")
    P("    largest live effect (D089)                     %.6f" % LARGEST_LIVE)
    P("    single-cell detection floor (D103, INJECTION-VERIFIED)   %.5f" % FLOOR_SINGLE)
    P("    132-cell floor (D103, INJECTION-VERIFIED)                %.5f" % FLOOR_132)

    v = {c: pd.to_numeric(m[c], errors="coerce").to_numpy(float)
         for c in dict.fromkeys(need + ob.NEG_CONTROL)}
    crows = []
    for dname, is_nc in [("A10_opp_defrtg", False), ("G01_noise", True)]:
        for bkey in ["B0_COMPLETE", "B1_HONEST", "B2_FAMILY"]:
            basecols = ob.BASES[bkey]
            for ev_lbl, ev in [("CLEAN_2023_24", ob.CLEAN_EVAL_SEASONS),
                               ("DISCLOSED_2022", ob.DISCLOSED_CONTRAST_EVAL_SEASONS)]:
                mask = dec & fin & np.isfinite(v[dname])
                # forecast shift in POINTS: (rate shift) x minutes estimate
                betas, dd, ee, yy, xi, mh = [], [], [], [], [], []
                for s in ev:
                    tr, te = mask & (ssn < s), mask & (ssn == s)
                    if tr.sum() < 300 or te.sum() < 80:
                        continue
                    Xb_tr, Xb_te = ob.design(v, basecols, tr), ob.design(v, basecols, te)
                    dbar = float(v[dname][tr].mean())
                    d_tr, d_te = v[dname][tr] - dbar, v[dname][te] - dbar
                    y_tr = v["y_ppm"][tr]
                    bb = ob.ols(Xb_tr, y_tr)
                    ba = ob.ols(np.column_stack([Xb_tr, d_tr]), y_tr)
                    mhat = v["_m_hat"][te]
                    shift_rate = (np.column_stack([Xb_te, d_te]) @ ba) - (Xb_te @ bb)
                    dd.append(shift_rate * mhat)
                    ee.append(v["y_pts"][te] - (Xb_te @ bb) * mhat)
                    yy.append(v["y_pts"][te])
                    xi.append(d_te)
                    mh.append(mhat)
                    betas.append(float(ba[-1]))
                if not yy:
                    continue
                d = np.concatenate(dd)
                e = np.concatenate(ee)
                y = np.concatenate(yy)
                x = np.concatenate(xi)
                mhat = np.concatenate(mh)
                sst = float(((y - y.mean()) ** 2).sum())
                sdd, sde = float(d @ d), float(d @ e)
                beta = float(np.mean(betas))
                sd_x = float(np.std(x, ddof=1))
                sd_y = float(np.std(y, ddof=1))
                pts1 = abs(beta) * sd_x * float(np.mean(mhat))
                r = dict(candidate=dname, is_negative_control=is_nc, base=bkey, window=ev_lbl,
                         n=int(len(y)), sd_y_points=sd_y, beta_on_ppm=beta,
                         sd_defence_centred=sd_x, mean_minutes_estimate=float(np.mean(mhat)),
                         points_moved_by_1sd=pts1,
                         pct_of_response_sd=100.0 * pts1 / sd_y,
                         ceiling_1sd_form=(pts1 / sd_y) ** 2,
                         ceiling_D084_form=sdd / sst,
                         DIAGNOSTIC_oracle=(sde * sde) / (sdd * sst) if sdd > 0 else np.nan,
                         realised_signed_dr2_points=(2 * sde - sdd) / sst,
                         vs_floor_single=(sdd / sst) / FLOOR_SINGLE,
                         vs_floor_132=(sdd / sst) / FLOOR_132,
                         vs_largest_live=(sdd / sst) / LARGEST_LIVE)
                crows.append(r)
                P("    %-15s %-12s %-14s n=%5d  1sd moves %.5f pts (%.2f%% of sd %.4f)  -> "
                  "ceiling %.8f (1sd-form %.8f)%s"
                  % (dname, bkey, ev_lbl, r["n"], pts1, r["pct_of_response_sd"], sd_y,
                     r["ceiling_D084_form"], r["ceiling_1sd_form"],
                     "   <-- NEGATIVE CONTROL" if is_nc else ""))
    cf = pd.DataFrame(crows)
    cf.to_csv(os.path.join(ob.OUT, "CEILING.csv"), index=False)

    hl = cf[(cf.candidate == "A10_opp_defrtg") & (cf.base == "B1_HONEST")
            & (cf.window == "CLEAN_2023_24")].iloc[0]
    nc = cf[(cf.candidate == "G01_noise") & (cf.base == "B1_HONEST")
            & (cf.window == "CLEAN_2023_24")].iloc[0]
    ob.hdr("THE CEILING, IN ONE LINE, AND THE GATE")
    P("  1 sd of centred opponent defensive rating = %.5f rating points" % hl["sd_defence_centred"])
    P("    x beta %.6e points-per-minute per rating point = %.8f ppm"
      % (hl["beta_on_ppm"], hl["sd_defence_centred"] * hl["beta_on_ppm"]))
    P("    x %.2f estimated minutes = %.5f POINTS PER GAME" % (hl["mean_minutes_estimate"],
                                                               hl["points_moved_by_1sd"]))
    P("    against a response sd of %.4f points = %.3f%% of one response sd."
      % (hl["sd_y_points"], hl["pct_of_response_sd"]))
    P("  CEILING (D084 variance-share form) = %.8f" % hl["ceiling_D084_form"])
    P("    = %.2fx the single-cell floor %.5f  (INJECTION-VERIFIED, D103)"
      % (hl["vs_floor_single"], FLOOR_SINGLE))
    P("    = %.2fx the 132-cell floor %.5f     (INJECTION-VERIFIED, D103)"
      % (hl["vs_floor_132"], FLOOR_132))
    P("    = %.2fx the largest live effect %.6f (D089)" % (hl["vs_largest_live"], LARGEST_LIVE))
    P("  MATCHED PURE-NOISE CONTROL on the identical path: ceiling %.8f, i.e. the real ceiling is "
      "%.2fx its own noise floor." % (nc["ceiling_D084_form"],
                                      hl["ceiling_D084_form"] / nc["ceiling_D084_form"]))
    gate = "PROCEED" if hl["ceiling_D084_form"] > FLOOR_SINGLE else "DO NOT FIT"
    P("  PREREGISTERED GATE (PREREG 4): ceiling %s single-cell floor -> %s"
      % (">" if gate == "PROCEED" else "<=", gate))

    with open(os.path.join(HERE, "_s02.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha=ob.prereg_sha(), strata=rows, n_blocks=nb,
                       ceiling=json.loads(cf.to_json(orient="records")), gate=gate), fh, indent=2,
                  default=float)
    with open(os.path.join(HERE, "run_log_s02.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))


if __name__ == "__main__":
    main()
