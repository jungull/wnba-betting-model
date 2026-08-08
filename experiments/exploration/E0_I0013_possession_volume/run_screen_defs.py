"""E0 I0013 -- the candidate registry, in one place so run_screen.py and run_maxt_robust.py
cannot drift apart.

side:  'opp'  value read from the OPPONENT team's pregame table
       'own'  value read from the player's OWN team's pregame table
       'both' derived from both sides
       'plyr' player-level

EVERY construction below is strictly-prior, same-season, date-aggregated (base.prior_expanding).
None of them reads the target game, any later game, or any other season -- i.e. none of them is a
retrospective baseline (trap 2). `cluster` names the grouping level at which the permutation null
and the cluster-robust SE are taken (trap 3).
"""

CANDS = [
    dict(name="opp_pace48", side="opp", field="pace48", cluster="opp_team_id", direction=1,
         construction="Opponent's pregame expanding possessions per 48 min, built from master_team "
                      "via base.team_possessions (symmetrised FGA-OREB+TOV+0.44*FTA), strictly "
                      "prior in-season games only, >=300 prior possessions required. "
                      "master_player.pace is corrupt and is NOT read."),
    dict(name="own_pace48", side="own", field="pace48", cluster="team_id", direction=1,
         construction="Player's OWN team's pregame expanding possessions per 48 min, identical "
                      "construction, strictly prior in-season games only."),
    dict(name="exp_gposs", side="both", field="pace48", cluster="opp_team_id", direction=2,
         construction="Expected game possessions = mean of the two teams' pregame expanding "
                      "possessions-per-48. Both components strictly prior in-season."),
    dict(name="ppm", side="plyr", field="ppm", cluster="player_id", direction=3,
         construction="Player's pregame expanding POSSESSIONS PER MINUTE = prior possessions / "
                      "prior minutes, shrunk by 30 minutes toward the strictly-prior expanding "
                      "league mean (previous-season fallback). The second exposure component, "
                      "distinct from minutes, which is already in the base model as Mexp."),
    dict(name="opp_orebA100", side="opp", field="orebA100", cluster="opp_team_id", direction=4,
         construction="OREB the opponent ALLOWS per 100 possessions, pregame expanding, strictly "
                      "prior in-season. The layer-2 offensive-rebound main effect I0012 flagged "
                      "as a possession-generating channel worth a layer-2 look."),
    dict(name="own_orebR100", side="own", field="orebR100", cluster="team_id", direction=4,
         construction="Player's OWN team's OREB per 100 possessions, pregame expanding, strictly "
                      "prior in-season. Own-side second-chance possession generation."),
    dict(name="opp_fgaA48", side="opp", field="fgaA48", cluster="opp_team_id", direction=1,
         construction="FGA the opponent ALLOWS per 48 min, pregame expanding, strictly prior "
                      "in-season. Supply-side pace instrument (shot supply) -- the cleaner "
                      "instrument I0012's NOTES asked for instead of the tempo proxy."),
    dict(name="opp_missA48", side="opp", field="missA48", cluster="opp_team_id", direction=1,
         construction="Missed FG the opponent ALLOWS per 48 min (opp_fga - opp_fgm in the "
                      "opponent's own master_team row), pregame expanding, strictly prior "
                      "in-season. The OREB supply the player's side generates against them."),
    dict(name="opp_missO48", side="opp", field="missO48", cluster="opp_team_id", direction=1,
         construction="The opponent's OWN missed FG per 48 min, pregame expanding, strictly prior "
                      "in-season. The DREB supply available to the player."),
]

DIRECTION_LABEL = {
    1: "D1 opponent / own-team pace as MAIN effects (incl. supply-side instruments)",
    2: "D2 expected game possessions",
    3: "D3 possessions-per-minute as an exposure channel distinct from minutes",
    4: "D4 layer-2 OREB main effect (possession generation)",
}
