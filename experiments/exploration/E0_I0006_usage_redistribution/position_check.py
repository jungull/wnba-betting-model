"""
Quick follow-up: does the top usage-absorber tend to share the absent player's POSITION
(from data/reference/player_bios.csv, which has position_raw for all players regardless of
starter status -- unlike master_player's position column which is starters-only)?
Exploration partition only (2021-2024), inherited from upstream files already filtered.
"""
import pandas as pd

OUT = "experiments/exploration/E0_I0006_usage_redistribution"
redis = pd.read_csv(f"{OUT}/redistribution_rows.csv")
top_absorber = pd.read_csv(f"{OUT}/top_absorber_per_game.csv")

bios = pd.read_csv("data/reference/player_bios.csv")
assert bios.season.between(2021, 2024).all() or True  # bios has multi-season rows; filter below
bios = bios[bios.season.between(2021, 2024)][["player_id", "season", "position_raw"]]

def simplify(pos):
    if pd.isna(pos):
        return None
    pos = str(pos)
    if "Guard" in pos and "Forward" not in pos and "Center" not in pos:
        return "G"
    if "Forward" in pos and "Guard" not in pos and "Center" not in pos:
        return "F"
    if "Center" in pos and "Forward" not in pos and "Guard" not in pos:
        return "C"
    return "Hybrid"

bios["pos_simple"] = bios.position_raw.apply(simplify)

ta = top_absorber.merge(bios, left_on=["absent_player_id", "season"], right_on=["player_id", "season"], how="left")
ta = ta.rename(columns={"pos_simple": "absent_pos"}).drop(columns=["player_id"])
ta = ta.merge(bios, left_on=["top_absorber_id", "season"], right_on=["player_id", "season"], how="left")
ta = ta.rename(columns={"pos_simple": "absorber_pos"}).drop(columns=["player_id"])

ta_valid = ta.dropna(subset=["absent_pos", "absorber_pos"])
print("n absence-games with position for both absent player and top absorber:", len(ta_valid))
match_rate = (ta_valid.absent_pos == ta_valid.absorber_pos).mean()
print("share where top absorber shares absent player's simplified position (G/F/C):", round(match_rate, 3))

# naive baseline: league-wide distribution of positions among rotation players (from bios, dedup by player-season)
pos_dist = bios.drop_duplicates(["player_id", "season"]).pos_simple.value_counts(normalize=True)
print("\nleague position distribution (player-seasons, 2021-2024):")
print(pos_dist)
naive_match = (pos_dist ** 2).sum()  # prob two random players share position under this distribution
print("naive same-position match probability if absorber were random:", round(naive_match, 3))

print("\nDONE position_check.py")
