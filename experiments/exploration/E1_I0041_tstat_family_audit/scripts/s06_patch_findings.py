"""E1_I0041 s06 -- fold the degenerate-null and bar-comparison results into FINDINGS.json."""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = json.load(open(os.path.join(HERE, "FINDINGS.json")))
C = pd.read_csv(os.path.join(HERE, "TSTAT_CELL_FLOORS.csv"))

# s05 wrote the CSV before adding these two columns; recompute and persist them here
C["bar_published_in_sd"] = C["t_crit"] * C["sd_used_by_D103"] / C["sd_signed"]
C["bar_own_in_sd"] = C["bar_own"] / C["sd_signed"]
C.to_csv(os.path.join(HERE, "TSTAT_CELL_FLOORS.csv"), index=False)

zero = C[~np.isfinite(C["degeneracy_ratio"])]
deg = C[C["degeneracy_ratio"] > 5]

F["degenerate_nulls"] = dict(
    criterion="mean(|t|)/sd(|t|) > 5 ; symmetric reference 1.3236",
    degenerate_cells=int(len(deg)),
    degenerate_by_screen={k: int(v) for k, v in deg.groupby("screen").size().items()},
    zero_width_null_cells=int(len(zero)),
    zero_width_published_floor_max=float(zero["mde_published"].max()),
    zero_width_all_recorded_as_powered=bool((zero["mde_published"] <= 0.0023).all()),
    total_unusable=int(len(deg) + len(zero)),
    recorded_by_D103_as_adequately_powered=int((deg["mde_published"] <= 0.0023).sum()
                                               + (zero["mde_published"] <= 0.0023).sum()))

F["bars_in_units_of_each_cells_own_signed_sd"] = {
    k: dict(D103_published=float(g["bar_published_in_sd"].median()),
            screens_own=float(g["bar_own_in_sd"].median()),
            sidak_normal=float(g["z_sidak"].iloc[0]))
    for k, g in C.groupby("screen")}

UN = pd.concat([deg, zero])
n_un = int(len(UN))
n_un_powered = int((UN["mde_published"] <= 0.0023).sum())
# how many of the non-functioning cells does R-A itself count as blind?  Those must come OUT of
# the numerator as well as the denominator, otherwise removing them changes nothing.
n_un_blind_RA = int((UN["mde_RA_fold_only"] > 0.0023).sum())
F["restatement_alternative_denominator"] = dict(
    note=("R-A with the 73 non-functioning nulls removed from BOTH numerator and denominator; "
          "their correct status is UNVERIFIABLE, neither blind nor powered"),
    unusable=n_un, unusable_recorded_powered_as_published=n_un_powered,
    unusable_counted_blind_under_RA=n_un_blind_RA,
    blind=886 - n_un_blind_RA, scoreable=1349 - n_un,
    share=(886 - n_un_blind_RA) / (1349 - n_un))

F["proposed_fix"] = dict(
    location="PROPOSED_FIX/", tests="13/13 pass", recommended=False,
    worse_than_incumbent=[
        "returns nan for 73 real cells the incumbent scores, and D103's own comparison "
        "`mde80_fw > 0.0023` evaluates nan to False, i.e. silently 'not blind'",
        "degeneracy guard has a blind band at mean|t|/sd|t| ~ 2, where E[t]=0 already fails and "
        "the moment recovery overstates sd(t) by 124 percent"],
    adopt_only_with="a caller-side rule that nan == UNVERIFIABLE, never nan == not-blind",
    applied_to_shared_kit=False)

F["files"] = sorted(os.listdir(HERE))
json.dump(F, open(os.path.join(HERE, "FINDINGS.json"), "w"), indent=2, default=str)
print("degenerate=%d  zero_width=%d  unusable=%d  recorded_powered=%d"
      % (len(deg), len(zero), n_un, n_un_powered))
print("of the %d unusable cells, R-A counts %d blind" % (n_un, n_un_blind_RA))
print("alternative denominator: %d / %d = %.4f"
      % (886 - n_un_blind_RA, 1349 - n_un, (886 - n_un_blind_RA) / (1349 - n_un)))
print("FINDINGS.json keys: %s" % list(F.keys()))
