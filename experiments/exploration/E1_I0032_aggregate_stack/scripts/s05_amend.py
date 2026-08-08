"""E1_I0032 s05 -- AMENDMENT 1 to the preregistration.

TRIGGER: a ROW COUNT, and nothing else.  s04 printed ZERO fallback_level == 2 rows inside the
preregistered common row set.  No outcome statistic had been computed at that moment and none is
computed in this file.  The failed s04 log is kept on disk as run_log_s04_FAILED_zero_routed_rows.txt
and the coverage accounting that diagnosed it is attrition_by_feature.csv.

WHAT WENT WRONG, precisely:
  The preregistered common row set required every component's feature to be finite.  C1's target
  population -- the rows where the champion emits its constant -- is BY CONSTRUCTION the population
  with almost no prior history, which is exactly where the prior-history features (own usage,
  teammate volume) and the E1_I0018 screen frame's own row universe do not reach.  Of the champion's
  947 fallback_level == 2 rows, only 62 survive into the E1_I0018 universe and ZERO have a finite
  prior5_minutes.  The preregistered definition deleted the largest component's entire population.

ZERO COMPONENTS ARE ADDED AND ZERO ARE DROPPED.  What changes is the row universe and the rule for
what a feature component does where its feature does not exist.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack_base import OUT, prereg

spec = prereg()

AMEND = {
    "amendment": 1,
    "parent_sha256": spec["sha256"],
    "trigger": ("A ROW COUNT ONLY: s04 reported 0 fallback_level == 2 rows inside the preregistered "
                "common row set (62 in the joined frame, 0 after the prior5_minutes requirement). "
                "No outcome statistic existed when this amendment was written."),
    "components_added": 0,
    "components_dropped": 0,
    "changes": [
        {"what": "BASE UNIVERSE",
         "from": ("rows present in ALL of E1_I0018 (features), E0_I0016 (defence) and E1_I0020 "
                  "(champion)"),
         "to": ("E0_I0024_reb_ast_characterisation/screen_frame.parquet, 18,212 rows, seasons "
                "2021-2024.  It STRICTLY CONTAINS the champion's universe (tier & rebast = 13,879, "
                "tier-only = 0) and is the most complete player-game history in the repository. "
                "2021 rows are HISTORY ONLY and are never scored."),
         "why": ("the champion's own universe is 13,879 rows for 2022-2024 against E1_I0018's "
                 "11,706; using the narrower frame as the base deletes 885 of the 947 rows the "
                 "largest component acts on.")},
        {"what": "MISSING-FEATURE RULE",
         "from": "a component's feature had to be finite on every common row",
         "to": ("a feature component applies its walk-forward correction where its feature is "
                "finite and applies EXACTLY ZERO where it is not.  This is what a production stack "
                "does, it keeps ONE row set and ONE denominator, and it is applied IDENTICALLY in "
                "the real stack, in every ablation and in every placebo."),
         "consequence_stated_in_advance": ("C5 (teammate volume) reaches 11,706 of 13,879 scored "
                                           "rows and only 62 of the 947 routed rows.  C6 (defence) "
                                           "reaches ~12,030.  Their measured contribution is "
                                           "therefore bounded by their coverage and that bound is "
                                           "published beside their ablation delta.")},
        {"what": "DEFENCE COVERAGE",
         "from": "A10_opp_defrtg joined on (season, player_id, game_id)",
         "to": ("A10_opp_defrtg joined on (season, game_id, opp_team_id).  It is a TEAM-GAME "
                "property, not a player property, so the team-game join is the correct one and it "
                "is exact where both are present -- verified and published."),
         "why": "the player-row join carried the E1_I0016 universe's gaps for no reason."},
        {"what": "DECISION STRATUM COLUMNS",
         "from": "n_prior >= 8 AND prior5_minutes >= 24 (E1_I0018 columns)",
         "to": ("pl_games_prior >= 8 AND pl_min_mean5 >= 24 (the champion frame's own columns). "
                "VERIFIED IDENTICAL on the 11,706-row overlap: 4,513 rows either way, agreement "
                "1.0000, corr 1.000000 on both ingredients.  The stratum DEFINITION is unchanged; "
                "only the columns carrying it are."),
         "why": "prior5_minutes is finite on 9,496 of 11,706 rows and on ZERO routed rows."},
        {"what": "PLACEBO TEAMMATE FEATURE",
         "from": "E1_I0018's G01_noise",
         "to": ("E0_I0024's own G01_noise, which covers the whole base universe.  It is the same "
                "kind of object -- a pre-existing negative-control noise column written by an "
                "earlier screen, not one manufactured here."),
         "why": "the E1_I0018 column does not exist outside the E1_I0018 universe."},
    ],
    "what_this_amendment_could_have_bought_the_agent_and_did_not": (
        "Widening the row set widens C1's population from 62 to 947 rows, which can only help the "
        "component with the largest published claim.  The agent had NOT computed any dR2 when it "
        "made the change, so it could not have known the sign -- but a reader should treat C1's "
        "measured gain as the figure this amendment most affects, and the ablation and the placebo "
        "route are the checks on it.  Both were hashed before the amendment."),
}

txt = json.dumps(AMEND, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
AMEND["sha256"] = hashlib.sha256(txt.encode("utf-8")).hexdigest()
json.dump(AMEND, open(os.path.join(OUT, "_prereg_amendment.json"), "w", encoding="utf-8"), indent=1)
print("AMENDMENT 1 SHA-256: %s" % AMEND["sha256"])
print("parent prereg sha256: %s" % spec["sha256"])
print("components added: 0    components dropped: 0")
print("trigger: a row count (0 routed rows), no outcome statistic seen")
