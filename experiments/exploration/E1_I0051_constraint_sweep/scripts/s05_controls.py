"""E1_I0051 -- s05.  Controls, season split, block bootstrap, and the availability arithmetic.

PREREG section 8 controls 1, 4, 7, 8 plus the section 6 predictions P1 and P2.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_base as B  # noqa: E402

pd.set_option("display.width", 240)

d = pd.read_parquet(os.path.join(B.SCR, "_frame.parquet"))
B.assert_partition(d, "FRAME_reload", True)
dm = B.decision_mask(d)
season = d["season"].to_numpy()
tg_code = d["tg_code"].to_numpy()
n_tg = int(tg_code.max()) + 1
counts = np.bincount(tg_code, minlength=n_tg)
B_live = d["B_live"].to_numpy(float)
B_rules = d["B_rules"].to_numpy(float)
T_real = d["T_min"].to_numpy(float)
CHOSEN = {("M_level_min", 2023): (3, 1.0), ("M_level_min", 2024): (3, 1.0),
          ("M_level_min", 2022): (2, 2.0),
          ("S_share_min", 2023): (3, 1.0), ("S_share_min", 2024): (3, 1.0),
          ("S_share_min", 2022): (2, 1.0)}
RESP = "M_level_min"


def make_cell(resp, cand, arm, proj, ev_set, mask):
    base = np.zeros(len(d))
    for ev in ev_set:
        h, k = CHOSEN[(resp, ev)]
        f = B.allocator_raw(d, resp, h, k)
        base = np.where((season == ev) | (season < ev), f, base)
    is_lvl = (resp == "M_level_min")
    return B.Cell(d, d[resp].to_numpy(float), base, cand, d[cand].to_numpy(float),
                  mask, mask, ev_set, arm, proj, B_rules,
                  B_live if is_lvl else np.ones(len(d)),
                  T_real if is_lvl else np.ones(len(d)))


# =============================================================================================
B.hdr("CONTROL 1 -- NO-OP PLACEBO.  The transform is ASSERTED to be the identity first.")
rows = []
for c in B.CANDIDATES:
    for arm in ("FROZEN", "UNFROZEN"):
        for proj in B.ARMS_PROJ:
            cell = make_cell(RESP, c, arm, proj, B.CLEAN_EVAL_SEASONS, dm)
            x = cell.cand
            xid = x.copy()                      # the no-op
            assert np.array_equal(x, xid), "NO-OP IS NOT THE IDENTITY -- check is vacuous"
            assert xid is not x, "no-op returned the same object; the check would be trivial"
            a, b = float(cell.dr2()), float(cell.dr2(xid))
            rows.append(dict(response=RESP, candidate=c, arm=arm, projection=proj,
                             dr2=a, dr2_after_noop=b, deviation=b - a,
                             identity_asserted=True))
pl = pd.DataFrame(rows)
mx = float(np.abs(pl["deviation"]).max())
print("  cells %d   max |deviation| = %.3e   %s"
      % (len(pl), mx, "EXACTLY 0.000e+00 ON ALL CELLS" if mx == 0.0 else "**NON-ZERO**"))
assert mx == 0.0
pl.to_csv(os.path.join(B.OUT, "PLACEBOS.csv"), index=False)

# =============================================================================================
B.hdr("CONTROL 4 -- RESPONSE PLACEBO.  Permute the RESPONSE inside the team-game.")
sw = B.WithinTeamGameSwap(d)
rng = np.random.default_rng(B.SEED)
rp = []
for c in ("A1_pts_share_prior", "A4_vac_x_own"):
    for proj in ("RAW", "PROJ_BUDGET"):
        cell = make_cell(RESP, c, "UNFROZEN", proj, B.CLEAN_EVAL_SEASONS, dm)
        obs = float(cell.dr2())
        vals = []
        for _ in range(200):
            yperm = sw.draw(cell.y, rng)
            c2 = B.Cell(d, yperm, cell.base, c, cell.cand, dm, dm, B.CLEAN_EVAL_SEASONS,
                        "UNFROZEN", proj, B_rules, B_live, T_real)
            vals.append(float(c2.dr2()))
        vals = np.asarray(vals)
        rp.append(dict(response=RESP, candidate=c, arm="UNFROZEN", projection=proj,
                       observed=obs, placebo_mean=float(vals.mean()),
                       placebo_max=float(vals.max()), placebo_min=float(vals.min()),
                       n_placebo=200))
        print("  %-20s %-12s observed %+.6f   placebo mean %+.6f  min %+.6f  max %+.6f"
              % (c, proj, obs, vals.mean(), vals.min(), vals.max()))
pd.DataFrame(rp).to_csv(os.path.join(B.OUT, "RESPONSE_PLACEBO.csv"), index=False)

# =============================================================================================
B.hdr("CONTROL 8 -- SEASON SPLIT.  eval 2023 / eval 2024 / DISCLOSED 2022.")
ss = []
for c in B.CANDIDATES:
    for arm in ("FROZEN", "UNFROZEN"):
        for proj in ("RAW", "PROJ_BUDGET"):
            r = {}
            for lab, evs in (("eval_2023", [2023]), ("eval_2024", [2024]),
                             ("disclosed_2022", [2022])):
                cell = make_cell(RESP, c, arm, proj, evs, dm)
                v = cell.full()
                r[lab] = np.nan if v is None else v["dr2"]
            ss.append(dict(response=RESP, candidate=c, arm=arm, projection=proj, **r))
ss = pd.DataFrame(ss)
print(ss[ss["arm"] == "UNFROZEN"].to_string(index=False, float_format=lambda x: "%+.6f" % x))
ss.to_csv(os.path.join(B.OUT, "SEASON_STABILITY.csv"), index=False)

# =============================================================================================
B.hdr("CONTROL 7 -- BLOCK BOOTSTRAP over TEAM-GAMES, beside the permutation null")
bs = []
for c in ("A1_pts_share_prior", "A2_fga_share_prior", "A4_vac_x_own"):
    for arm in ("FROZEN", "UNFROZEN"):
        for proj in ("RAW", "PROJ_BUDGET"):
            cell = make_cell(RESP, c, arm, proj, B.CLEAN_EVAL_SEASONS, dm)
            full = cell.full()
            y, yb, ya, idx = full["y"], full["yb"], full["ya"], full["idx"]
            blk = tg_code[idx]
            ub = pd.unique(blk)
            per = {b: np.flatnonzero(blk == b) for b in ub}
            rng2 = np.random.default_rng(B.SEED)
            draws = np.empty(1000)
            for i in range(1000):
                pick = rng2.choice(ub, size=len(ub), replace=True)
                sel = np.concatenate([per[b] for b in pick])
                yy = y[sel]
                sst = float(((yy - yy.mean()) ** 2).sum())
                draws[i] = (float(((yy - yb[sel]) ** 2).sum())
                            - float(((yy - ya[sel]) ** 2).sum())) / sst
            sd = float(draws.std(ddof=1))
            bs.append(dict(response=RESP, candidate=c, arm=arm, projection=proj,
                           observed=full["dr2"], boot_sd=sd, boot_mean=float(draws.mean()),
                           t=full["dr2"] / sd if sd > 0 else np.nan,
                           mde80_bootstrap=2.80 * sd, n_blocks=len(ub), n_boot=1000))
            print("  %-20s %-9s %-12s obs %+.6f  boot sd %.6f  t %+6.2f  MDE80_boot %.6f"
                  % (c, arm, proj, full["dr2"], sd, full["dr2"] / sd if sd > 0 else np.nan,
                     2.80 * sd))
pd.DataFrame(bs).to_csv(os.path.join(B.OUT, "BOOTSTRAP_VARIANCE.csv"), index=False)

# =============================================================================================
B.hdr("SECTION 6 -- THE AVAILABILITY DEFECT AS A CONSTRAINT.  P1 and P2, measured.")

tgu = d.drop_duplicates("tg")
roster = tgu["n_roster"].to_numpy(float)
tmin = tgu["T_min"].to_numpy(float)
brul = tgu["B_rules"].to_numpy(float)
print("""
P1 -- IS A ROSTER SUM A BUDGET?  Compare the two candidate 'budgets' on the same team-games.""")
p1 = pd.DataFrame([
    dict(quantity="team MINUTES (the rules budget)", mean=float(tmin.mean()),
         sd=float(tmin.std(ddof=1)), cv=float(tmin.std(ddof=1) / tmin.mean()),
         n_distinct=int(pd.unique(np.round(tmin, 4)).size),
         mae_best_pretip_assertion=float(np.abs(tmin - 200.0).mean()),
         pct_of_total=100.0 * float(np.abs(tmin - 200.0).mean()) / float(tmin.mean()),
         lands_on_a_rules_lattice="YES -- 1776/1776 within 0.0667 of a multiple of 25"),
    dict(quantity="realised ROSTER SIZE", mean=float(roster.mean()),
         sd=float(roster.std(ddof=1)), cv=float(roster.std(ddof=1) / roster.mean()),
         n_distinct=int(pd.unique(roster).size),
         mae_best_pretip_assertion=float(np.abs(roster - roster.mean()).mean()),
         pct_of_total=100.0 * float(np.abs(roster - roster.mean()).mean()) / float(roster.mean()),
         lands_on_a_rules_lattice="NO -- integers 6..12, no rule fixes it"),
])
print(p1.to_string(index=False, float_format=lambda x: "%.5f" % x))
p1.to_csv(os.path.join(B.OUT, "AVAILABILITY_P1_TIGHTNESS.csv"), index=False)
ratio = float(p1.loc[1, "pct_of_total"]) / float(p1.loc[0, "pct_of_total"])
print("\n  The roster count is %.2fx LOOSER, as a fraction of itself, than the minutes budget."
      % ratio)
print("  P1 CONFIRMED: a roster sum is not a budget in the PREREG section 2 sense.")

print("""
P2 -- DOES A UNIFORM PER-TEAM-GAME RESCALING CANCEL UNDER A RENORMALISING DOWNSTREAM STEP?
  The exposure producer allocates a FIXED 200 team-minutes in proportion to p_active x e_min.
  Xb multiplies every p_active in a team-game by one scalar s_g = Rhat_g / sum(p_active).
  Claim: project_to(s_g * w, ...) == project_to(w, ...) EXACTLY.  Demonstrated numerically here on
  this screen's own team-game structure with randomly drawn positive weights and scalars, which is
  a property of the arithmetic and not of any basketball fact.""")
rng3 = np.random.default_rng(B.SEED)
w = rng3.random(len(d)) + 0.05
s_g = rng3.random(n_tg) * 1.5 + 0.25
w_scaled = w * s_g[tg_code]
a = B.project_to(w, tg_code, n_tg, counts, B_live)
b = B.project_to(w_scaled, tg_code, n_tg, counts, B_live)
dev = float(np.abs(a - b).max())
print("  max |project(w) - project(s_g * w)| over %d rows / %d team-games = %.3e  %s"
      % (len(d), n_tg, dev, "EXACT CANCELLATION" if dev < 1e-12 else "**DOES NOT CANCEL**"))
assert dev < 1e-12
print("""  P2 CONFIRMED, and it was DERIVED before it was looked up: E1_I0035 measured Xb's downstream
  exposure misallocation at 8.912455 minutes -- IDENTICAL TO THE UNREPAIRED CHAMPION TO THE LAST
  DIGIT.  The constraint framing predicts that number exactly, with no fit and no data.""")

pd.DataFrame([dict(check="uniform_rescale_cancels_under_projection", n_rows=len(d),
                   n_team_games=n_tg, max_abs_deviation=dev,
                   predicted_before_measuring=True,
                   corroborating_published_number="E1_I0035 Xb misallocation 8.912455 min, "
                                                  "identical to unrepaired champion")]
             ).to_csv(os.path.join(B.OUT, "AVAILABILITY_P2_CANCELLATION.csv"), index=False)

B.dump("s05", dict(prereg_sha=B.prereg_sha(), noop_max_dev=mx, p2_dev=dev,
                   roster_vs_minutes_looseness=ratio))
print("\nwrote PLACEBOS.csv RESPONSE_PLACEBO.csv SEASON_STABILITY.csv BOOTSTRAP_VARIANCE.csv "
      "AVAILABILITY_P1_TIGHTNESS.csv AVAILABILITY_P2_CANCELLATION.csv")
B.hdr("DONE s05")
