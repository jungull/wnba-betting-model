import os
import pandas as pd
import numpy as np

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "IDEATION_QUEUE", "_data_feasibility7.txt")
L = []
def say(s):
    L.append(str(s))

mp = pd.read_parquet(os.path.join(ROOT, "data", "masters", "master_player.parquet"))
mp["gd"] = pd.to_datetime(mp.game_date)

say("### A. `era` (measurement regime) vs season  -- is there a source discontinuity mid-panel?")
say(pd.crosstab(mp.season, mp.era).to_string())
say("minutes_source vs era:")
say(pd.crosstab(mp.era, mp.minutes_source).to_string())

say("")
say("### B. OVERTIME exposure inflation (structural: minutes denominator is not constant)")
po = pd.read_parquet(os.path.join(ROOT, "data", "possessions", "possessions.parquet"),
                     columns=["game_id", "period", "season"])
po["gid"] = po.game_id.astype(str)
ot = po.groupby("gid").period.max()
otg = set(ot[ot >= 5].index)
mp["gid"] = mp.game_id.astype(str)
mp["is_ot"] = mp.gid.isin(otg)
pl = mp[mp.minutes.notna()]
say("OT games: %d of %d (%.4f). Player-rows in OT games: %d (%.4f of played rows)"
    % (len(otg), po.gid.nunique(), len(otg) / po.gid.nunique(), pl.is_ot.sum(), pl.is_ot.mean()))
say("mean minutes  non-OT %.3f  vs OT %.3f  (+%.1f%%)"
    % (pl[~pl.is_ot].minutes.mean(), pl[pl.is_ot].minutes.mean(),
       100 * (pl[pl.is_ot].minutes.mean() / pl[~pl.is_ot].minutes.mean() - 1)))
say("mean pts      non-OT %.3f  vs OT %.3f  (+%.1f%%)"
    % (pl[~pl.is_ot].pts.mean(), pl[pl.is_ot].pts.mean(),
       100 * (pl[pl.is_ot].pts.mean() / pl[~pl.is_ot].pts.mean() - 1)))
say("=> OT is UNFORECASTABLE at tip-off but inflates the target on %.2f%% of rows." % (100 * pl.is_ot.mean()))

say("")
say("### C. POSITION availability: master_player.position vs player_bios.position_raw")
bios = pd.read_csv(os.path.join(ROOT, "data", "reference", "player_bios.csv"), low_memory=False)
say("bios rows=%d players=%d seasons=%s" % (len(bios), bios.player_id.nunique(), sorted(bios.season.unique())))
say("bios position_raw values: %s" % bios.position_raw.value_counts(dropna=False).to_dict())
key = set(zip(bios.player_id, bios.season))
mp["k"] = list(zip(mp.player_id, mp.season))
say("master_player rows joinable to a bios (player_id,season) row: %.4f" % mp.k.isin(key).mean())
say("master_player.position blank fraction: %.4f (blank exactly on non-starters, confirmed earlier)"
    % (mp.position.astype(str).str.strip() == "").mean())
say("=> ANY position feature read from master_player.position is defined on STARTERS ONLY (44.3%% of rows).")
say("   player_bios.position_raw is the correct source: %.2f%% coverage of player-seasons."
    % (100 * bios.position_raw.notna().mean()))

say("")
say("### D. TEAMMATE-ABSENCE state constructible strictly-prior? (extends the D089 volume lead)")
# for each team-game, how many roster players were listed DNP (row exists, minutes null)
tg = mp.groupby(["gid", "team_id"]).agg(n_rows=("player_id", "size"),
                                        n_dnp=("minutes", lambda s: s.isna().sum()),
                                        n_played=("minutes", "count")).reset_index()
say("team-games: %d ; mean roster rows %.2f ; mean DNP %.2f ; mean played %.2f"
    % (len(tg), tg.n_rows.mean(), tg.n_dnp.mean(), tg.n_played.mean()))
say("team-games with >=1 DNP: %.4f ; >=2: %.4f ; >=3: %.4f"
    % ((tg.n_dnp >= 1).mean(), (tg.n_dnp >= 2).mean(), (tg.n_dnp >= 3).mean()))
say("=> the DNP ROW EXISTS in the box score, so 'who was out' is observable AFTER the game.")
say("   Strictly-prior use: a player's OWN prior absence spell state, and a TEAMMATE's prior absence spell,")
say("   are both computable from games already played. Today's inactives are NOT (that is the 49.2% news gap).")

say("")
say("### E. ZERO-INFLATION of the ungenerated targets (scale/link question)")
pl2 = pl[pl.season <= 2024]
for c in ["reb", "oreb", "dreb", "ast", "stl", "blk", "fg3m", "ftm", "tov", "pts"]:
    v = pl2[c]
    say("  %-5s mean=%6.3f var=%7.3f var/mean=%5.2f frac_zero=%.4f  (Poisson would give var/mean=1)"
        % (c, v.mean(), v.var(), v.var() / max(v.mean(), 1e-9), (v == 0).mean()))

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("\n".join(L))
