import pandas as pd
EXPL=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
at=pd.read_csv(EXPL+r"\E1_I0038_within_entity_null_audit\AUDIT_TABLE.csv")
r=at[(at.screen.str.contains("E0_I0024"))&(at.candidate=="R08_player_ra_share")&(at.target=="y_oreb")&(at.n==13784)&(at.base=="B_COMPLETE")]
print("A2 dR2 full precision: %.16f" % r.dr2_reported.iloc[0], " n=",int(r.n.iloc[0]))
print("A2 null_mean       : %.16f" % r.null_mean.iloc[0])
k=at[at.is_kill==True]
print("player_season kills:",(k.candidate_level_recorded=="player_season").sum())
print("player_season kills non-ceiling:",((k.candidate_level_recorded=="player_season")&(~k.is_ceiling.astype(bool))).sum())
print("player_season all non-ceiling:",((at.candidate_level_recorded=="player_season")&(~at.is_ceiling.astype(bool))).sum())
print("opp_team_season kills:",(k.candidate_level_recorded=="opp_team_season").sum())
print("opp_team_season all:",(at.candidate_level_recorded=="opp_team_season").sum())
print("ceiling & player_season:",((at.candidate_level_recorded=="player_season")&(at.is_ceiling.astype(bool))).sum())
