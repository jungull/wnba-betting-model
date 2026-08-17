import pandas as pd
R=r"C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program/"
Q=pd.read_parquet(R+'data/masters/master_player.parquet',columns=['game_id','season','game_date','minutes','dnp_reason'])
Q['game_date']=pd.to_datetime(Q['game_date'])
print('master_player game_date span:',Q.game_date.min().date(),'->',Q.game_date.max().date())
print('2026 span:',Q[Q.season==2026].game_date.min().date(),'->',Q[Q.season==2026].game_date.max().date())
# main-repo master (may be fresher)
import os
M=r"C:/Users/jgallagher/wnba-betting-model/data/masters/master_player.parquet"
if os.path.exists(M):
    Z=pd.read_parquet(M,columns=['game_id','season','game_date'])
    Z['game_date']=pd.to_datetime(Z['game_date'])
    print('MAIN-REPO master_player rows',len(Z),'span',Z.game_date.min().date(),'->',Z.game_date.max().date())
    print('  mtime',pd.Timestamp(os.path.getmtime(M),unit='s'))
