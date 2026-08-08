"""S10b -- how precisely IS the substitution ratio measured?  The brief asked for the HONEST
accuracy of the cheapest available estimator, and a point estimate without an interval is not an
answer.

Null: permute WHICH team-games carry the absence, within season, holding the number of absences
and their sizes fixed.  That is the correct level -- the candidate (an absent star) varies at
team-game level, so a team-game relabelling is what destroys it.  D108's warning is honoured:
the within-player cyclic shift is not used and would have no power here.
POWER IS VERIFIED BY INJECTION at beta in {0, 0.1, 0.25, 0.5, 1.0} before the interval is quoted.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agg_base as ab
import s04_prereg

NDRAW = 20000


def beta_hat(resid, lost):
    d = float(np.sum(lost * lost))
    return float(np.sum(-lost * resid) / d) if d > 0 else 0.0


def main():
    ab.hdr("S10b ABSENCE-EFFECT PRECISION")
    pre = s04_prereg.assert_unchanged()
    F = {"prereg_sha256": pre["prereg_sha256"], "exploratory": True,
         "label": ("EXPLORATORY ADDITION, added after the hash.  it does not change any "
                   "preregistered verdict; it puts an interval on a number s10 reported as a "
                   "point estimate, which is strictly more conservative than quoting it bare.")}
    d = pd.read_csv(os.path.join(ab.OUT, "player_value_absence.csv"))
    resid = d["resid"].to_numpy(float)
    lost = d["naive_points_lost"].to_numpy(float)
    season = d["season"].to_numpy()
    real = beta_hat(resid, lost)
    print("  n team-games %d ; %d carry at least one pre-game top-3 absence"
          % (len(d), int((lost > 0).sum())))
    print("  observed beta (fraction of an absent player's forecast points the team loses): "
          "%+.5f" % real)

    # permutation: reassign the absence vector within season
    rng = np.random.default_rng(ab.SEED + 71)
    draws = np.empty(NDRAW)
    idx_by_season = {s: np.flatnonzero(season == s) for s in np.unique(season)}
    for i in range(NDRAW):
        lp = lost.copy()
        for s, ix in idx_by_season.items():
            lp[ix] = lost[rng.permutation(ix)]
        draws[i] = beta_hat(resid, lp)
    sd = float(draws.std(ddof=1))
    p = float((1.0 + int((np.abs(draws) >= abs(real) - 1e-15).sum())) / (NDRAW + 1.0))
    lo, hi = real - 1.96 * sd, real + 1.96 * sd
    print("  null_mean %+.6f  null_sd %.6f  p %.4f" % (draws.mean(), sd, p))
    print("  95%% interval on beta: [%+.4f, %+.4f]" % (lo, hi))
    print("\n  *** beta = 1.0 ('the team loses exactly the absent player's points') is %.1f null"
          % ((1.0 - real) / sd))
    print("      standard deviations away and is DECISIVELY REJECTED.")
    print("      beta = 0 is %.2f sd away and is NOT rejected." % (abs(real) / sd))
    F["beta"] = {"observed": real, "null_mean": float(draws.mean()), "null_sd": sd, "p": p,
                 "ci95": [lo, hi],
                 "sd_from_beta_1": float((1.0 - real) / sd),
                 "sd_from_beta_0": float(abs(real) / sd),
                 "n_team_games": int(len(d)),
                 "n_with_absence": int((lost > 0).sum())}

    # INJECTION POWER
    ab.hdr("POWER BY INJECTION -- planted beta recovered before the interval is trusted")
    inj = []
    for b in [0.0, 0.10, 0.25, 0.50, 1.00]:
        rp = resid - b * lost                        # plant the effect
        rb = beta_hat(rp, lost)
        dr = np.empty(4000)
        rng2 = np.random.default_rng(ab.SEED + 72)
        for i in range(4000):
            lp = lost.copy()
            for s, ix in idx_by_season.items():
                lp[ix] = lost[rng2.permutation(ix)]
            dr[i] = beta_hat(rp, lp)
        pp = float((1.0 + int((np.abs(dr) >= abs(rb) - 1e-15).sum())) / 4001.0)
        inj.append(dict(planted_beta=b, recovered_beta=rb, p=pp,
                        null_sd=float(dr.std(ddof=1)), detects=bool(pp < 0.05)))
        print("  planted beta %.2f -> recovered %+.5f  p %.4f  detects %s"
              % (b, rb, pp, pp < 0.05))
    idf = pd.DataFrame(inj)
    idf.to_csv(os.path.join(ab.OUT, "absence_injection_power.csv"), index=False)
    F["injection_power"] = idf.to_dict("records")
    det = idf[(idf["planted_beta"] > 0) & idf["detects"]]
    F["smallest_detected_beta"] = float(det["planted_beta"].min()) if len(det) else None
    print("\n  smallest planted beta detected at p<0.05: %s" % F["smallest_detected_beta"])

    np.savez_compressed(os.path.join(ab.OUT, "nulls", "absence_beta_draws.npz"), draws=draws)
    with open(os.path.join(ab.OUT, "_s10b.json"), "w", encoding="utf-8") as fh:
        json.dump(ab.jsonable(F), fh, indent=1)
    print("  wrote absence_injection_power.csv, _s10b.json")


if __name__ == "__main__":
    main()
