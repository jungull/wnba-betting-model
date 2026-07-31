"""Q1: is the day-before advantage a timing effect or a sample effect?
   Q2: could our model be exploiting knowledge of who actually played?
"""
import pandas as pd
import numpy as np

R = r"C:\Users\jgallagher\wnba-betting-model"

# ---------------------------------------------------------------- Q1
print("=" * 74)
print("Q1  SAME-GAMES timing test (isolates timing from sample composition)")
print("=" * 74)
b = pd.read_csv(R + r"\experiments\clv_transfer\bet_log.csv")
ext = b[b.era == "extension"].copy()
# one row per (game, cutoff): model_margin and market_margin
per = (ext.groupby(["game_id", "cutoff", "season"])
       .agg(model=("model_margin", "first"), market=("market_margin", "first"),
            truth=("margin_true", "first")).reset_index())
piv = per.pivot_table(index=["game_id", "season", "truth"], columns="cutoff",
                      values=["model", "market"]).dropna()
piv.columns = [f"{a}_{c}" for a, c in piv.columns]
piv = piv.reset_index()
cuts = sorted({c.split("_", 1)[1] for c in piv.columns if c.startswith("model_")})
print(f"games with BOTH cutoffs present: {len(piv)} | cutoffs {cuts}")
if len(piv) and len(cuts) >= 2:
    for season in ["all"] + sorted(piv.season.unique().tolist()):
        d = piv if season == "all" else piv[piv.season == season]
        row = [f"{'pooled' if season=='all' else season:>7} n={len(d):3d}"]
        for c in cuts:
            mo = (d[f"model_{c}"] - d.truth).abs().mean()
            mk = (d[f"market_{c}"] - d.truth).abs().mean()
            row.append(f"{c}: model {mo:6.3f} market {mk:6.3f} gap {mo-mk:+.3f}")
        print("  " + " | ".join(row))
    print("\n  READ: if our gap is genuinely smaller at the earlier cutoff on the")
    print("  SAME games, the day-before effect is real. If the gaps match, the")
    print("  earlier 'advantage' was sample composition.")

# ---------------------------------------------------------------- Q2
print()
print("=" * 74)
print("Q2  Could we be exploiting knowledge of who actually played?")
print("=" * 74)
print("Structural check: the margin model's inputs are team-level shifted trends")
print("from PRIOR games (channel_base_v2). It consumes no lineup, injury or")
print("availability field at all. Testing the behavioural signature instead:")
print("if we secretly knew tonight's absences, our edge over the market should")
print("GROW on games with more absences (we'd know, the market wouldn't).")

mp = pd.read_parquet(R + r"\data\masters\master_player.parquet")
mp = mp[mp.season_type == "Regular Season"]
# players dressed but did not play = absences visible only after tipoff
dnp = (mp[mp.dnp_reason.notna() & (mp.dnp_reason.astype(str) != "")]
       .groupby(["game_id", "team_id"]).size().rename("n_dnp").reset_index())
tot = dnp.groupby("game_id").n_dnp.sum().rename("game_dnp").reset_index()
tot["game_id"] = tot.game_id.astype(str)

pv = pd.read_csv(R + r"\experiments\channel_reval\predictions_v2.csv")
pv["GAME_ID"] = pv.GAME_ID.astype(str)
bk = pd.read_csv(R + r"\experiments\oracle_bracket\bookie_gap.csv")
ob = pd.read_csv(R + r"\experiments\oracle_bracket\game_level_margins.csv")
ob["GAME_ID"] = ob.GAME_ID.astype(str)

# join model error, market error, and absence count per game
bl = b[b.era.isin(["extension", "old"])].groupby("game_id").agg(
    market=("market_margin", "first"), truth=("margin_true", "first")).reset_index()
bl["game_id"] = bl.game_id.astype(str)
m = pv[["GAME_ID", "str_margin_cal", "margin_true"]].merge(
    bl[["game_id", "market"]], left_on="GAME_ID", right_on="game_id")
m = m.merge(tot, left_on="GAME_ID", right_on="game_id", how="left")
m["game_dnp"] = m.game_dnp.fillna(0)
m["err_model"] = (m.str_margin_cal - m.margin_true).abs()
m["err_market"] = (m.market - m.margin_true).abs()
m["edge"] = m.err_market - m.err_model          # positive = we beat the market
print(f"\n  games joined: {len(m)}")
q = m.game_dnp.quantile([0.33, 0.67]).tolist()
m["absence_tier"] = np.where(m.game_dnp <= q[0], "few",
                     np.where(m.game_dnp <= q[1], "some", "many"))
print(m.groupby("absence_tier").agg(
    n=("edge", "size"), mean_absences=("game_dnp", "mean"),
    model_mae=("err_model", "mean"), market_mae=("err_market", "mean"),
    our_edge=("edge", "mean")).to_string())
r = m.edge.corr(m.game_dnp)
print(f"\n  corr(our edge over market, number of absences) = {r:+.3f}")
print("  READ: a POSITIVE correlation would be the signature of secretly")
print("  knowing absences. Near zero or negative = no such advantage.")
