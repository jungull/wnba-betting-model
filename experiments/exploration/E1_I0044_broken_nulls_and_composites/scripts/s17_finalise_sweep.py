"""S17 -- fold the MEASURED resolutions (s16) into COMPOSITE_SWEEP.csv and produce the counts.

E0_I0016: NOT EXPOSED, by design.  The screen splits every feature into an entity-season MEAN
component and a mean-free WITHIN component and screens each under a null that is valid for it
(`ep_base.py:279-291`).  Its own docstring makes the composite argument verbatim:
"scheme='between' applied to a feature that varies WITHIN its groups annihilates 100% of the
within-group variation and yields a p that is 'manufactured rather than measured', while
scheme='within' is the literal identity for a feature that is constant within groups."
That is a fourth screen immune by design, after E0_I0014's level selection, E0_I0015's measured
share and E1_I0021's within-entity estimand.

E0_I0017: uses `entity_swap_null` at ONE declared entity per candidate, with no decomposition
(`s02_screen.py:12-13`, `s05_finalise.py:179`).  A candidate is EXPOSED when the measurement
shows its components STRADDLE -- one component with between-opp-team-season share > 0.5 and
another with between-player-season share > 0.5 -- because no single entity swap can be a valid
null for both.  The threshold 0.50 is E1_I0038's, unchanged and not retuned.
"""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = pd.read_csv(os.path.join(HERE, "COMPOSITE_SWEEP.csv"))
M = pd.read_csv(os.path.join(HERE, "MEASURED_COMPONENT_SHARES.csv"))

def straddles(js):
    try:
        d = json.loads(js)
    except Exception:
        return None
    if len(d) < 2:
        return None
    opp = any(v["between_opp_team_season"] > 0.5 for v in d.values()
              if np.isfinite(v.get("between_opp_team_season", np.nan)))
    pl = any(v["between_player_season"] > 0.5 for v in d.values()
             if np.isfinite(v.get("between_player_season", np.nan)))
    return bool(opp and pl)

idx = F.set_index(["screen", "candidate"])
n16 = n17e = n17c = n_still = 0
for _, r in M.iterrows():
    k = (r["screen"], r["candidate"])
    if r["screen"] == "E0_I0016_efficiency_predictors":
        idx.loc[k, "composite_verdict"] = "NOT_EXPOSED"
        idx.loc[k, "verdict_reason"] = (
            "IMMUNE BY DESIGN: the screen decomposes every feature into an entity-season MEAN "
            "and a mean-free WITHIN component and screens each under a null valid for it, so "
            "no component is left without a valid null")
        idx.loc[k, "evidence"] = "ep_base.py:279-291 (decompose); measured shares in "\
                                 "MEASURED_COMPONENT_SHARES.csv"
        idx.loc[k, "component_levels"] = r["component_shares"]
        n16 += 1
        continue
    st = straddles(r["component_shares"])
    idx.loc[k, "component_levels"] = r["component_shares"]
    idx.loc[k, "evidence"] = ("MEASURED on the screen's own screen_frame.parquet; null from "
                              "s02_screen.py:12-13, s05_finalise.py:179")
    if st is None:
        n_still += 1
        idx.loc[k, "composite_verdict"] = "UNDETERMINABLE"
        idx.loc[k, "verdict_reason"] = (
            "fewer than two components could be measured on the screen's own frame (a component "
            "is a raw box column not carried into screen_frame.parquet); the share the invariant "
            "needs is not on disk at any entity and was not invented here")
    elif st:
        n17e += 1
        idx.loc[k, "composite_verdict"] = "EXPOSED"
        idx.loc[k, "verdict_reason"] = (
            "MEASURED STRADDLE: one component is opponent-dominant (between-opp-team-season "
            "share > 0.5) and another is player-dominant (between-player-season share > 0.5). "
            "The screen uses ONE entity swap at ONE declared entity and does not decompose, so "
            "whichever entity it picks, the other component's variation lives inside the "
            "permuting block and the null is not valid for it.")
    else:
        n17c += 1
        idx.loc[k, "composite_verdict"] = "NOT_EXPOSED"
        idx.loc[k, "verdict_reason"] = (
            "MEASURED: every component is dominant at the SAME level, so a single entity swap "
            "at that level is valid for all of them")
F = idx.reset_index()
F.to_csv(os.path.join(HERE, "COMPOSITE_SWEEP.csv"), index=False)
print("E0_I0016 resolved to NOT_EXPOSED (immune by design): %d" % n16)
print("E0_I0017 measured EXPOSED: %d   NOT_EXPOSED: %d   still UNDETERMINABLE: %d"
      % (n17e, n17c, n_still))

IS_COMP = F["candidate_class"].astype(str).str.startswith(("COMPOSITE", "BUNDLE"))
print("\n================ FINAL COMPOSITE SWEEP ================")
print("(screen, candidate) pairs swept                     : %d" % len(F))
print("  screens contributing candidates                   : %d" % F["screen"].nunique())
print("COMPOSITE (ratio/difference/product/sum/bundle/spec) : %d" % int(IS_COMP.sum()))
print("ATOMIC or single-quantity aggregate                  : %d"
      % int(F["candidate_class"].astype(str).str.startswith("ATOMIC").sum()))
print("NOT A FEATURE (stratum / arm / harvest artefact)     : %d"
      % int(F["candidate_class"].astype(str).str.startswith("NOT_A_FEATURE").sum()))
print("construction UNDETERMINABLE                          : %d"
      % int(F["candidate_class"].astype(str).str.startswith("UNDETERMINABLE").sum()))
print("\n--- verdicts among the %d composites ---" % int(IS_COMP.sum()))
print(F.loc[IS_COMP, "composite_verdict"].value_counts().to_string())
print("\n--- EXPOSED, full resolved list (asserted count) ---")
E = F[F["composite_verdict"] == "EXPOSED"]
print(E[["screen", "candidate", "candidate_class"]].to_string(index=False))
print("EXPOSED COUNT = %d" % len(E))
print("\n--- UNDETERMINABLE composites, full resolved list ---")
U = F[IS_COMP & (F["composite_verdict"] == "UNDETERMINABLE")]
print(U[["screen", "candidate", "candidate_class"]].to_string(index=False))
print("UNDETERMINABLE COMPOSITE COUNT = %d" % len(U))
print("\n--- by screen ---")
print(pd.crosstab(F.loc[IS_COMP, "screen"], F.loc[IS_COMP, "composite_verdict"]).to_string())
print("\nDONE s17")
