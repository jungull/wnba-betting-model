"""
E0 I0010 -- is the null a REAL null or a null through a noisy construction? (discipline #4)

(a) split-half reliability of the positional allowance, benchmarked against the overall
    team-defence allowance (known-real signal) and the player's own tendency (known-real).
(b) is the positional-allowance MAIN effect alive at all (per-season betas / t-stats)?
(c) robustness of the headline to per-36-minutes instead of per-100-possessions.

PARTITION: 2021-2024 only. # FILTER-POINT right after load. Deterministic (parity split, no RNG).
"""
import numpy as np
import pandas as pd
import os

np.seterr(divide="ignore", invalid="ignore")
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0010_positional_matchup")
PARTITION = [2021, 2022, 2023, 2024]
TARGETS = ["pts", "reb", "ast"]
pd.set_option("display.width", 220)


def hdr(s):
    print("\n" + "=" * 78); print(s); print("=" * 78)


mp = pd.read_parquet(os.path.join(ROOT, r"data\masters\master_player.parquet"))
# FILTER-POINT
mp = mp[mp["season"].isin(PARTITION)].copy()
assert set(mp["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
mp = mp[mp["season_type"] == "Regular Season"].copy()
for c in ["pts", "reb", "ast"]:
    mp[c] = mp[c].astype("float64")
mp["minutes"] = mp["minutes"].astype("float64")
mp["possessions"] = mp["possessions"].astype("float64")
for c in ["team_id", "opp_team_id", "player_id"]:
    mp[c] = mp[c].astype("int64")
mp = mp[(mp["minutes"] >= 1.0) & (mp["possessions"] > 0)].copy()
mp["gdate"] = pd.to_datetime(mp["game_date"])
mp = mp.sort_values(["gdate", "game_id", "team_id", "player_id"]).reset_index(drop=True)
mp["unit"] = mp["possessions"] / 100.0
mp["unit36"] = mp["minutes"] / 36.0
rp = mp["position"].fillna("").astype(str).str.strip()
mp["_G"] = (rp == "G").astype(float); mp["_F"] = (rp == "F").astype(float); mp["_C"] = (rp == "C").astype(float)
pc = (mp.groupby("player_id", sort=False)[["_G", "_F", "_C"]].cumsum() - mp[["_G", "_F", "_C"]].values).to_numpy()
mp["pos_group"] = np.where(pc.sum(1) > 0, np.array(["G", "F", "C"])[pc.argmax(1)], "U")
POOL = mp[mp["pos_group"] != "U"].copy().reset_index(drop=True)
print("pooled rows:", len(POOL), "seasons:", sorted(POOL["season"].unique()))

# deterministic odd/even split of each defence's games, by date order
gm = POOL[["season", "opp_team_id", "game_id", "gdate"]].drop_duplicates().sort_values(["season", "opp_team_id", "gdate"])
gm["half"] = gm.groupby(["season", "opp_team_id"], sort=False).cumcount() % 2
POOL = POOL.merge(gm[["season", "opp_team_id", "game_id", "half"]], on=["season", "opp_team_id", "game_id"], how="left")


def splithalf(keys, T, unit="unit"):
    d = POOL.assign(s=POOL[T], u=POOL[unit])
    a = d.groupby(keys + ["half"], as_index=False)[["s", "u"]].sum()
    a["rate"] = a["s"] / a["u"]
    w = a.pivot_table(index=keys, columns="half", values="rate").dropna()
    n_ = a.pivot_table(index=keys, columns="half", values="u").dropna()
    w = w[(n_[0] > 5) & (n_[1] > 5)]                       # >=500 possessions per half
    # remove level differences across (season, position) so we measure OPPONENT variation only
    g = w.reset_index()
    lvl = [k for k in keys if k != "opp_team_id"]
    g["h0"] = g[0] - g.groupby(lvl)[0].transform("mean")
    g["h1"] = g[1] - g.groupby(lvl)[1].transform("mean")
    r = np.corrcoef(g["h0"], g["h1"])[0, 1]
    sb = 2 * r / (1 + r) if r > -1 else np.nan             # Spearman-Brown -> full-season reliability
    return r, sb, len(g)


hdr("(a) SPLIT-HALF RELIABILITY of the pregame allowance measure")
print("Within (season, position-group) level differences removed, so this is purely")
print("'do the same opponents look alike in independent halves of their own season?'")
print("\n%-6s | %-34s | %-30s | %s" % ("", "POSITIONAL allowance (this idea)", "OVERALL team defence (benchmark)", "player OWN tendency"))
print("%-6s | %8s %8s %6s | %8s %8s %6s | %8s %8s %6s" %
      ("target", "r_half", "r_full", "n", "r_half", "r_full", "n", "r_half", "r_full", "n"))
rel = {}
for T in TARGETS:
    p = splithalf(["season", "pos_group", "opp_team_id"], T)
    o = splithalf(["season", "opp_team_id"], T)
    pl = splithalf(["season", "player_id"], T)
    rel[T] = p
    print("%-6s | %8.3f %8.3f %6d | %8.3f %8.3f %6d | %8.3f %8.3f %6d"
          % (T, p[0], p[1], p[2], o[0], o[1], o[2], pl[0], pl[1], pl[2]))
print("\nr_half = correlation between the two halves; r_full = Spearman-Brown full-season reliability.")
print("A near-zero r_full for the POSITIONAL column would mean the allowance is mostly sampling")
print("noise and the interaction null is AMBIGUOUS rather than negative.")

hdr("(a2) variance decomposition of the positional allowance")
for T in TARGETS:
    d = POOL.assign(s=POOL[T], u=POOL["unit"])
    a = d.groupby(["season", "pos_group", "opp_team_id"], as_index=False)[["s", "u"]].sum()
    a["rate"] = a["s"] / a["u"]
    tot = a["rate"].std()
    a["c"] = a["rate"] - a.groupby(["season", "pos_group"])["rate"].transform("mean")
    print("  %-4s full-season allowance: sd across all cells %.3f ; sd WITHIN (season,pos) %.3f"
          " ; share of variance that is between-position %.2f"
          % (T, tot, a["c"].std(), 1 - (a["c"].std() ** 2) / (tot ** 2)))

hdr("(b) is the positional-allowance MAIN effect alive? (pregame, per season)")
feat = {T: pd.read_csv(os.path.join(OUT, "features_%s.csv" % T)) for T in TARGETS}


def r2(y, X):
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    return 1.0 - float(r @ r) / float(((y - y.mean()) ** 2).sum()), b, r


def dummies(s):
    return [(s == v).astype(float).values for v in sorted(pd.unique(s))[1:]]


print("  partial correlation of the PREGAME positional allowance with the outcome, after")
print("  own tendency + position dummies (per season). Persistence check on the MAIN effect.")
print("  %-6s %-8s %8s %10s %10s" % ("target", "season", "n", "beta", "partial_r"))
for T in TARGETS:
    w = feat[T].dropna(subset=["own_pre", "allow_pre", "y"]).copy()
    assert set(w["season"].unique()) <= set(PARTITION)
    for c in ["own_pre", "allow_pre"]:
        w[c + "_c"] = w[c] - w.groupby(["season", "pos_group"])[c].transform("mean")
        w[c + "_c"] /= w[c + "_c"].std()
    for seas in PARTITION + ["POOLED"]:
        g = w if seas == "POOLED" else w[w["season"] == seas]
        pg = dummies(g["pos_group"])
        _, b, _ = r2(g["y"].values, [g["own_pre_c"].values, g["allow_pre_c"].values] + pg)
        _, _, ry = r2(g["y"].values, [g["own_pre_c"].values] + pg)
        _, _, ra = r2(g["allow_pre_c"].values, [g["own_pre_c"].values] + pg)
        pr = np.corrcoef(ry, ra)[0, 1]
        print("  %-6s %-8s %8d %10.4f %10.4f" % (T, seas, len(g), b[2], pr))

hdr("(c) robustness: per-36-MINUTES normalisation instead of per-100-possessions")
print("  run:  set I0010_UNIT=unit36  &&  python analyze.py    -> run_log_per36.txt")
