"""
E0 I0004 -- shot-location tendency/conversion x opponent location allowance.

HARD RULE: exploration partition = seasons 2021-2024 ONLY. This script reads
ONLY the eight shots_{2021,2022,2023,2024}_{regular,playoffs}.parquet files
under data/shotcharts/. It never opens shots_2025_*, shots_2026_*, or the
pre-built data/zone_maps/*.csv artifacts -- those were confirmed (via their
.manifest.json) to be BUILT ACROSS ALL SEASONS 2021-2026 (shrinkage priors
pooled across the full 6-season sample), so even reading their raw/season-
specific columns would indirectly rest on a K constant informed by the
confirmation holdout. Rebuilding directly from raw per-season shot files
sidesteps that contamination entirely.

Also deliberately avoids any on-court lineup join (I0003 found clock-time
lineup attribution only ~72% accurate). Opponent identity here comes from
the two TEAM_IDs present in each GAME_ID in the shot-event file itself --
shot-event-level, no lineup needed.
"""
import pandas as pd
import numpy as np

SEASONS = [2021, 2022, 2023, 2024]
TYPES = ["regular", "playoffs"]
FILES = [f"data/shotcharts/shots_{s}_{t}.parquet" for s in SEASONS for t in TYPES]

print("=== Loading exploration-partition files only ===")
for f in FILES:
    print(" ", f)

dfs = []
for f in FILES:
    d = pd.read_parquet(f)
    season = int(f.split("shots_")[1][:4])
    d["season"] = season
    dfs.append(d)
shots = pd.concat(dfs, ignore_index=True)

print(f"\nTotal shots loaded: {len(shots)}")
print(f"Season range in loaded data: {shots['season'].min()}-{shots['season'].max()}")
print(f"GAME_DATE range: {shots['GAME_DATE'].min()} - {shots['GAME_DATE'].max()}")
assert shots["season"].max() <= 2024, "LEAKAGE: a season > 2024 was loaded"
assert shots["GAME_DATE"].astype(str).str.slice(0, 4).astype(int).max() <= 2024, \
    "LEAKAGE: a game_date in 2025/2026 was loaded"
print("PARTITION CHECK PASSED: no 2025/2026 data loaded.\n")

# ---------------------------------------------------------------------------
# 1. Zone granularity the data actually supports
# ---------------------------------------------------------------------------
print("=== 1. Zone granularity (SHOT_ZONE_BASIC, raw, 2021-2024) ===")
print(shots["SHOT_ZONE_BASIC"].value_counts())
print()


def merge_zone(z):
    if z in ("Left Corner 3", "Right Corner 3"):
        return "Corner 3"
    return z


shots["zone"] = shots["SHOT_ZONE_BASIC"].map(merge_zone)
print("=== Collapsed 6-zone scheme (merge L/R corner) ===")
print(shots["zone"].value_counts())
print()

# sanity: zone implies point value?
shots["is3"] = (shots["SHOT_TYPE"] == "3PT Field Goal").astype(int)
zone_val = shots.groupby("zone")["is3"].agg(["mean", "size"])
print("Zone vs 3PT-flag agreement (mean should be 0 or 1):")
print(zone_val)
print()

# ---------------------------------------------------------------------------
# 2. Opponent identity from shot-event data (no lineup join)
# ---------------------------------------------------------------------------
print("=== 2. Deriving opponent team per shot from GAME_ID team pairs ===")
game_teams = shots.groupby("GAME_ID")["TEAM_ID"].unique()
n_not_two = (game_teams.apply(len) != 2).sum()
print(f"Games with != 2 distinct TEAM_IDs in shot data: {n_not_two} / {len(game_teams)}")

opp_lookup = {}
for gid, teams in game_teams.items():
    if len(teams) == 2:
        opp_lookup[(gid, teams[0])] = teams[1]
        opp_lookup[(gid, teams[1])] = teams[0]

shots["OPP_TEAM_ID"] = [
    opp_lookup.get((gid, tid), np.nan)
    for gid, tid in zip(shots["GAME_ID"], shots["TEAM_ID"])
]
n_missing_opp = shots["OPP_TEAM_ID"].isna().sum()
print(f"Shots with no resolvable opponent (dropped): {n_missing_opp} / {len(shots)}")
shots = shots[shots["OPP_TEAM_ID"].notna()].copy()
shots["OPP_TEAM_ID"] = shots["OPP_TEAM_ID"].astype(shots["TEAM_ID"].dtype)
shots["made"] = shots["SHOT_MADE_FLAG"].astype(int)
print(f"Shots remaining after opponent resolution: {len(shots)}\n")

# ---------------------------------------------------------------------------
# 3. Do opponents differ systematically in what they concede by zone?
# ---------------------------------------------------------------------------
print("=== 3a. Team-season defensive conversion allowed, by zone ===")
def_zone = (
    shots.groupby(["OPP_TEAM_ID", "season", "zone"])
    .agg(att=("made", "size"), mk=("made", "sum"))
    .reset_index()
)
def_zone["rate"] = def_zone["mk"] / def_zone["att"]

def_pool = (
    shots.groupby(["OPP_TEAM_ID", "season"])
    .agg(att=("made", "size"), mk=("made", "sum"))
    .reset_index()
)
def_pool["pool_rate"] = def_pool["mk"] / def_pool["att"]

def_zone = def_zone.merge(def_pool[["OPP_TEAM_ID", "season", "pool_rate"]], on=["OPP_TEAM_ID", "season"])
def_zone["zone_conv_residual"] = def_zone["rate"] - def_zone["pool_rate"]


def dispersion_test(group, rate_col, att_col):
    """Simple DerSimonian-Laird-style test: is between-team variance in
    rate_col bigger than pure binomial sampling noise would predict?
    Returns (mu, Q, df, between_var, K_pseudo_attempts)."""
    n = group[att_col].values.astype(float)
    r = group[rate_col].values.astype(float)
    mu = np.sum(n * r) / np.sum(n)
    if mu <= 0 or mu >= 1:
        return mu, np.nan, len(n) - 1, np.nan, np.nan
    Q = np.sum(n * (r - mu) ** 2) / (mu * (1 - mu))
    dfree = len(n) - 1
    c = np.sum(n) - np.sum(n ** 2) / np.sum(n)
    between_var = mu * (1 - mu) * max(Q - dfree, 0) / c if c > 0 else np.nan
    K = (mu * (1 - mu) / between_var - 1) if (between_var and between_var > 0) else np.inf
    return mu, Q, dfree, between_var, K


print(f"{'zone':<24}{'teams':>6}{'mu':>8}{'Q':>10}{'df':>5}{'K(pseudo-att)':>16}   verdict")
zone_disp_results = {}
for zone, g in def_zone.groupby("zone"):
    # pool across seasons at team-season grain (treat each team-season as one cell)
    mu, Q, dfree, bvar, K = dispersion_test(g, "rate", "att")
    zone_disp_results[zone] = (mu, Q, dfree, bvar, K)
    verdict = "REAL DISPERSION" if (Q > dfree * 1.5 and K < 300) else "~noise-dominated"
    print(f"{zone:<24}{g['OPP_TEAM_ID'].nunique():>6}{mu:>8.3f}{Q:>10.1f}{dfree:>5}{K:>16.1f}   {verdict}")
print()

print("=== 3b. Team-season defensive SHOT-MIX SHARE allowed, by zone (tendency side) ===")
def_zone["share"] = def_zone["att"] / def_zone.groupby(["OPP_TEAM_ID", "season"])["att"].transform("sum")
league_share = (
    shots.groupby(["season", "zone"]).size().rename("n").reset_index()
)
league_tot = shots.groupby("season").size().rename("tot").reset_index()
league_share = league_share.merge(league_tot, on="season")
league_share["league_share"] = league_share["n"] / league_share["tot"]
def_zone = def_zone.merge(league_share[["season", "zone", "league_share"]], on=["season", "zone"])
def_zone["share_residual"] = def_zone["share"] - def_zone["league_share"]

print(f"{'zone':<24}{'teams':>6}{'mu(share)':>10}{'Q':>10}{'df':>5}{'K(pseudo-att)':>16}   verdict")
share_disp_results = {}
for zone, g in def_zone.groupby("zone"):
    mu, Q, dfree, bvar, K = dispersion_test(g, "share", "att")
    share_disp_results[zone] = (mu, Q, dfree, bvar, K)
    verdict = "REAL DISPERSION" if (Q > dfree * 1.5 and K < 300) else "~noise-dominated"
    print(f"{zone:<24}{g['OPP_TEAM_ID'].nunique():>6}{mu:>10.3f}{Q:>10.1f}{dfree:>5}{K:>16.1f}   {verdict}")
print()

def_zone.to_csv("experiments/exploration/E0_I0004_shot_location_allowance/team_zone_defense_2021_2024.csv", index=False)

# ---------------------------------------------------------------------------
# 4. Player zone tendency/conversion x opponent zone allowance -- beyond pooled
# ---------------------------------------------------------------------------
print("=== 4. Player-level interaction test (conversion channel) ===")
# Player-season-zone conversion, and a leave-current-season-out player-zone baseline
pz = (
    shots.groupby(["PLAYER_ID", "season", "zone"])
    .agg(att=("made", "size"), mk=("made", "sum"))
    .reset_index()
)
pz["rate"] = pz["mk"] / pz["att"]

# leave-one-season-out player-zone baseline (avg of OTHER seasons, attempt-weighted)
records = []
for (pid, zone), g in pz.groupby(["PLAYER_ID", "zone"]):
    for _, row in g.iterrows():
        other = g[g["season"] != row["season"]]
        if other["att"].sum() >= 10:  # require some other-season support
            base_rate = other["mk"].sum() / other["att"].sum()
            records.append((pid, row["season"], zone, base_rate, other["att"].sum()))
baseline = pd.DataFrame(records, columns=["PLAYER_ID", "season", "zone", "player_zone_baseline", "baseline_att"])
print(f"Player-season-zone cells with a usable other-season baseline (>=10 att): {len(baseline)}")

shots_b = shots.merge(baseline, on=["PLAYER_ID", "season", "zone"], how="inner")
print(f"Shots joined to a player-zone baseline: {len(shots_b)} / {len(shots)}")

# opponent zone_conv_residual, leave-current-season alone is fine since it's
# a season-level aggregate (one game is ~1/30-40th of the team-season sample)
opp_res = def_zone[["OPP_TEAM_ID", "season", "zone", "zone_conv_residual", "share_residual"]]
shots_b = shots_b.merge(opp_res, on=["OPP_TEAM_ID", "season", "zone"], how="left")

shots_b["shooting_residual"] = shots_b["made"] - shots_b["player_zone_baseline"]

print("\n--- Conversion interaction: corr(shooting_residual, opp zone_conv_residual), by zone ---")
for zone, g in shots_b.groupby("zone"):
    if len(g) < 200:
        continue
    corr = g["shooting_residual"].corr(g["zone_conv_residual"])
    med = g["zone_conv_residual"].median()
    hi = g[g["zone_conv_residual"] > med]["shooting_residual"].mean()
    lo = g[g["zone_conv_residual"] <= med]["shooting_residual"].mean()
    print(f"{zone:<24} n={len(g):>6}  corr={corr:+.4f}  hi_opp_resid_mean={hi:+.4f}  lo_opp_resid_mean={lo:+.4f}  diff={hi-lo:+.4f}")

print("\n--- Placebo: corr(shooting_residual, opp POOLED rate) [should be ~0 since residual already player-zone-demeaned & this is season-pool not zone] ---")
opp_pool_only = def_pool[["OPP_TEAM_ID", "season", "pool_rate"]]
shots_c = shots_b.merge(opp_pool_only, on=["OPP_TEAM_ID", "season"], how="left")
corr_placebo = shots_c["shooting_residual"].corr(shots_c["pool_rate"])
print(f"corr(shooting_residual, opp pooled FG% allowed) overall = {corr_placebo:+.4f}  n={len(shots_c)}")

shots_b.to_csv("experiments/exploration/E0_I0004_shot_location_allowance/shot_level_residuals_2021_2024.csv", index=False)

# ---------------------------------------------------------------------------
# 5. Season-split persistence check (within exploration partition only)
# ---------------------------------------------------------------------------
print("\n=== 5. Persistence: split 2021-2022 vs 2023-2024 (both inside partition) ===")
shots_b["half"] = np.where(shots_b["season"] <= 2022, "2021_2022", "2023_2024")
for zone, g in shots_b.groupby("zone"):
    if len(g) < 200:
        continue
    row = []
    for half, gg in g.groupby("half"):
        if len(gg) < 100:
            row.append((half, np.nan, len(gg)))
            continue
        corr = gg["shooting_residual"].corr(gg["zone_conv_residual"])
        row.append((half, corr, len(gg)))
    print(f"{zone:<24}" + "  ".join(f"{h}: corr={c:+.4f} (n={n})" if not np.isnan(c) else f"{h}: n={n} too small" for h, c, n in row))

print("\nDone.")
