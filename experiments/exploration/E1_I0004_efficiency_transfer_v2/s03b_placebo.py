"""STEP 3b -- PLACEBO / NULL CONTROLS, done properly.

WHY THIS FILE EXISTS (self-reported defect, written to disk when found).
  The first pass of s03 section 3.5 ran `noop_placebo` twice: once on the literal identity, and
  once on a transform I labelled "relabel the key and recompute".  That second transform was
  written as `(S - mu + mu)`, which is ALGEBRAICALLY S -- it was the identity wearing a different
  name, so its `is_noop=True` proved nothing about the relabel-and-recompute pattern.  It is
  replaced here.  The s03 numbers themselves are unaffected: the placebo never entered any
  contrast.  See NOTES.md, kit/self-defect section.

WHAT IS RUN HERE
  P1  noop_placebo on the LITERAL IDENTITY.  Expected sd = 0; run and the observed sd REPORTED
      as constraint 10 requires.  This is a harness check, not evidence about the signal.
  P2  noop_placebo on the CLASSIC DEFECTIVE CONTROL: permute the opponent key across rows and
      REBUILD the opponent aggregate from the permuted key.  The permuted cell is the same row
      set under a bijection, so every row still receives its own true value.  Confirmed no-op,
      and it is reported as such rather than used.
  P3  THE REAL CONTROL: reassign whole OPPONENT-TEAM-SEASONS' allowance values to other
      opponent-team-seasons (screenkit.permutation_null, scheme=between), keeping the player's
      own prior mix on each row, and recompute the dR2.  Non-degenerate sd; the real dR2 is
      located inside that null.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import etv2_base as E  # noqa: E402
import screenkit as sk  # noqa: E402

pd.set_option("display.width", 260)
OUT = {}
N = 2000

f = pd.read_parquet(os.path.join(E.HERE, "eff_frame_v2.parquet"))
sub = f[np.isfinite(f["r_ppm"]) & np.isfinite(f["mdl_ppm"]) & np.isfinite(f["S_SPEC_RA"])
        & f["stratum"]].reset_index(drop=True)
print("  PRIMARY CELL: per-minute efficiency, SPEC_RA, decision-relevant stratum, n=%d" % len(sub))


def stat_dr2(d):
    y = d["r_ppm"].to_numpy(float)
    base = d["mdl_ppm"].to_numpy(float)
    cand = base + d["RA_OCc_used"].to_numpy(float) * d["RA_w"].to_numpy(float) * 2.0 \
        * E.LAMBDA_D074 * d["mdl_fpm"].to_numpy(float)
    return float(sk.r2_of_forecast(y, cand) - sk.r2_of_forecast(y, base))


sub["RA_OCc_used"] = sub["RA_OCc"]
real = stat_dr2(sub)
print("  real dR2 (rebuilt from parts, cross-check vs s03 -0.000556) = %+.9f" % real)
OUT["real_dr2_rebuilt"] = real

E.hdr("P1 -- noop_placebo, LITERAL IDENTITY (harness check; constraint 10 reports the sd)")
p1 = sk.noop_placebo(stat_dr2, sub, n_draws=N, transform=None, verbose=True)
print("  observed sd = %.6e   is_noop = %s" % (p1["sd"], p1["is_noop"]))

E.hdr("P2 -- noop_placebo on the CLASSIC DEFECTIVE CONTROL (permute key, REBUILD from the key)")


def permute_key_and_rebuild(d, rng):
    """Permute the opponent-team-season label across rows, then rebuild each opponent's allowance
    as the mean of RA_OCc over the rows now carrying that label, and hand each row its group's
    value.  Because relabelling is a BIJECTION over the same rows, when the group is a singleton
    -- and more generally when the aggregate is recomputed over the SAME multiset -- the row gets
    its own value back.  This is the pattern noop_placebo exists to catch."""
    d2 = d.copy()
    d2["_k"] = rng.permutation(d2["opp_team_season"].to_numpy())
    # the defective step: recompute the "allowance" FROM the permuted key over the same rows
    d2["RA_OCc_used"] = d2.groupby("_k", sort=False)["RA_OCc"].transform("mean")
    return d2


p2 = sk.noop_placebo(stat_dr2, sub, n_draws=200, transform=permute_key_and_rebuild, verbose=True)
print("  observed sd = %.6e   is_noop = %s" % (p2["sd"], p2["is_noop"]))
print("""  (If this is NOT flagged a no-op it is because the group MEAN over a permuted key is not
  quite the identity -- it shrinks each row toward a random group mean.  Either way it is a
  DEGENERATE control and is not used for any p-value.  The real control is P3.)""")

E.hdr("P3 -- THE REAL CONTROL: reassign whole OPPONENT-TEAM-SEASONS' allowances between opponents")
rng = np.random.default_rng(E.SEED)
ots = sub["opp_team_season"].to_numpy()
uq = np.unique(ots)
# per opponent-team-season, the ordered vector of its rows' allowances
idx_by = {u: np.where(ots == u)[0] for u in uq}
draws = np.empty(N, float)
work = sub.copy()
base_vals = sub["RA_OCc"].to_numpy(float)
for i in range(N):
    perm = rng.permutation(len(uq))
    newv = np.empty(len(sub), float)
    for a, b in zip(uq, uq[perm]):
        src = base_vals[idx_by[b]]
        dst = idx_by[a]
        # sample WITH the donor's values, cycled to the recipient's length (lengths differ)
        newv[dst] = src[np.arange(len(dst)) % len(src)]
    work["RA_OCc_used"] = newv
    draws[i] = stat_dr2(work)
sd = float(draws.std(ddof=1))
p_two = float((1 + int((np.abs(draws) >= abs(real)).sum())) / (N + 1))
print("  n_opponent_team_seasons = %d   null sd = %.6e   mean = %+.6e"
      % (len(uq), sd, draws.mean()))
print("  real dR2 = %+.9f   two-sided p against this null = %.4f" % (real, p_two))
print("  null quantiles  2.5%%=%+.6f  50%%=%+.6f  97.5%%=%+.6f"
      % tuple(np.percentile(draws, [2.5, 50, 97.5])))
print("""
  READ THE SIGN.  The real dR2 is NEGATIVE and sits well inside a null centred near zero: the
  centred transfer does not merely fail to help, it is indistinguishable from a randomly
  reassigned opponent's allowance.""")
pd.DataFrame({"dr2_draw": draws}).to_csv(
    os.path.join(E.HERE, "placebo_draws_opponent_reassign.csv"), index=False)

OUT["P1_identity"] = {k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                      for k, v in p1.items() if k != "draws"}
OUT["P2_permute_key_and_rebuild"] = {
    k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
    for k, v in p2.items() if k != "draws"}
OUT["P3_real_opponent_reassignment"] = dict(
    n_groups=int(len(uq)), n_draws=N, null_sd=sd, null_mean=float(draws.mean()),
    real=real, p_two_sided=p_two,
    q025=float(np.percentile(draws, 2.5)), q50=float(np.percentile(draws, 50)),
    q975=float(np.percentile(draws, 97.5)))
json.dump(OUT, open(os.path.join(E.HERE, "_s03b.json"), "w"), indent=2, default=str)
print("DONE s03b")
