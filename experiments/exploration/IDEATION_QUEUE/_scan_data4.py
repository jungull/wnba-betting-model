import os, glob
import pandas as pd
import numpy as np

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "IDEATION_QUEUE", "_data_feasibility4.txt")
L = []
def say(s):
    L.append(str(s))

mp = pd.read_parquet(os.path.join(ROOT, "data", "masters", "master_player.parquet"))
mp["gd"] = pd.to_datetime(mp["game_date"])
expl = mp[mp.season <= 2024]

say("### 1. SHOT <-> POSSESSION TIME JOIN VIABILITY (no raw pbp needed)")
sc = pd.read_parquet(os.path.join(ROOT, "data", "shotcharts", "shots_2023_regular.parquet"))
sc["gid"] = sc.GAME_ID.astype(str)
# game clock seconds elapsed: 10-min quarters in WNBA
sc["sec"] = (sc.PERIOD.clip(upper=4) - 1) * 600 + np.where(sc.PERIOD <= 4, 600, 300) \
            - (sc.MINUTES_REMAINING * 60 + sc.SECONDS_REMAINING)
po = pd.read_parquet(os.path.join(ROOT, "data", "possessions", "possessions.parquet"))
po["gid"] = po.game_id.astype(str)
po23 = po[po.season == 2023]
say("shots_2023_regular games=%d ; possessions 2023 games=%d" % (sc.gid.nunique(), po23.gid.nunique()))
say("shot GAME_IDs found in possessions: %d / %d" % (sc.gid.isin(set(po23.gid)).sum(), len(sc)))
say("possessions start_sec/end_sec range: %.0f .. %.0f" % (po.start_sec.min(), po.end_sec.max()))
say("=> time-join is constructible: possessions carry period+start_sec+end_sec and full on-court 10;")
say("   shotcharts carry PERIOD + MIN/SEC remaining. No raw pbp file required.")

say("")
say("### 2. RAW PBP vs POSSESSIONS coverage divergence (provenance question, NOT asserted)")
gids_pbp = set(os.path.basename(p)[4:-8] for p in glob.glob(os.path.join(ROOT, "data", "playbyplay", "pbp_*.parquet")))
say("raw pbp files: %d ; possessions games: %d ; master games: %d"
    % (len(gids_pbp), po.gid.nunique(), mp.game_id.nunique()))
for s in sorted(po.season.unique()):
    g = set(po[po.season == s].gid)
    say("  season %s: possessions games=%3d ; of which have a raw pbp file=%3d" % (s, len(g), len(g & gids_pbp)))
say("possessions has NO sibling manifest: %s" % (not os.path.exists(os.path.join(ROOT, "data", "possessions", "possessions.parquet.manifest.json"))))

say("")
say("### 3. GARBAGE TIME / BLOWOUT definability from possessions")
po["margin"] = (po.home_pts_before - po.away_pts_before).abs()
po["t"] = (po.period.clip(upper=4) - 1) * 600 + po.start_sec.where(po.period <= 4, 0)
late = po[po.period >= 4]
say("possessions in period>=4: %d ; of those |margin|>=20: %d (%.4f)"
    % (len(late), (late.margin >= 20).sum(), (late.margin >= 20).mean()))
say("possessions overall |margin|>=20: %.4f ; >=15: %.4f" % ((po.margin >= 20).mean(), (po.margin >= 15).mean()))
say("games with any period>=5 (OT): %d of %d" % (po[po.period >= 5].gid.nunique(), po.gid.nunique()))

say("")
say("### 4. INJURY-TYPE ABSENCE HISTORY feasibility")
ih = pd.read_csv(os.path.join(ROOT, "data", "injury_history", "injury_history.csv"), low_memory=False)
ih["d"] = pd.to_datetime(ih["date"], errors="coerce")
miss = ih[ih.category.isin(["missed_game_injury", "missed_game_other"])]
say("missed_game_* rows total: %d ; in 2021-2024: %d" % (len(miss), (miss.d.dt.year <= 2024).sum()))
say("distinct players (relinquished) in missed_game_*: %d" % miss.player_relinquished.nunique())
mi = ih[ih.category == "missed_game_injury"]
say("missed_game_injury distinct note values: %d" % mi.notes.nunique())
say("top 25 injury note values:")
for k, v in mi.notes.value_counts().head(25).items():
    say("   %-46s %d" % (str(k)[:46], v))
say("master_player DNP rows total: %d (injury-ish: %d)"
    % (mp.minutes.isna().sum(),
       mp.dnp_reason.fillna("").str.contains("Injury|Illness|Concussion|Protocol|Reconditioning", case=False, regex=True).sum()))

say("")
say("### 5. ARITHMETIC CEILING INPUTS on the exploration partition (played rows)")
pl = expl[expl.minutes.notna()].copy()
pl["ppm"] = pl.pts / pl.minutes.replace(0, np.nan)
say("var(pts)=%.4f" % pl.pts.var())
for c in ["ftm", "fg3m", "fgm", "fga", "fta", "fouls_drawn", "oreb", "dreb", "reb", "ast", "tov", "minutes"]:
    v = pl[c]
    say("  %-12s var=%9.4f  cov_with_pts=%9.4f  var_share_if_perfect=%.4f  corr=%.4f"
        % (c, v.var(), v.cov(pl.pts), (v.cov(pl.pts) ** 2) / (v.var() * pl.pts.var()), v.corr(pl.pts)))

say("")
say("### 6. FT CHANNEL: how much of points variance is the FT component?")
ftpts = pl.ftm
fieldpts = pl.pts - pl.ftm
say("var(pts)=%.4f = var(FTpts)=%.4f + var(fieldpts)=%.4f + 2cov=%.4f"
    % (pl.pts.var(), ftpts.var(), fieldpts.var(), 2 * ftpts.cov(fieldpts)))
say("FT component share of points variance (var only): %.4f" % (ftpts.var() / pl.pts.var()))
say("R2 of a PERFECT ftm forecast holding field pts at its mean: %.4f"
    % ((ftpts.cov(pl.pts) ** 2) / (ftpts.var() * pl.pts.var())))
say("fta==0 share of played rows: %.4f ; fouls_drawn==0 share: %.4f"
    % ((pl.fta == 0).mean(), (pl.fouls_drawn == 0).mean()))

say("")
say("### 7. REBOUND / ASSIST target scale (the ungenerated-forecast frontier)")
for c in ["reb", "oreb", "dreb", "ast", "stl", "blk", "tov", "fg3m"]:
    say("  %-6s mean=%7.4f var=%8.4f  frac_zero=%.4f" % (c, pl[c].mean(), pl[c].var(), (pl[c] == 0).mean()))

say("")
say("### 8. OBSERVED_TIME / provenance columns in master_player")
say("observed_time dtype=%s nunique=%d sample=%s"
    % (mp.observed_time.dtype, mp.observed_time.nunique(), mp.observed_time.dropna().unique()[:3]))
say("source values: %s" % mp.source.value_counts().to_dict())
say("era values: %s" % mp.era.value_counts().to_dict())
say("minutes_source values: %s" % mp.minutes_source.value_counts(dropna=False).to_dict())

say("")
say("### 9. HOW MANY PLAYER-GAMES ARE 'THIN SAMPLE' (cold-start tier population)")
pl2 = mp[mp.minutes.notna()].sort_values(["player_id", "gd"]).copy()
pl2["n_prior"] = pl2.groupby("player_id").cumcount()
for k in [0, 1, 2, 3, 5, 10]:
    sub = pl2[pl2.n_prior <= k]
    say("  rows with <=%2d prior appearances: %6d (%.4f of played rows)" % (k, len(sub), len(sub) / len(pl2)))

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("WROTE", OUT, len(L))
