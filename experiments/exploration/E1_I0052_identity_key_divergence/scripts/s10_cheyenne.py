"""E1_I0052 s10 -- the ONE unresolved name, opened rather than counted.

62 priced rows in the 2024 partition fail normalized-exact resolution, all under a single
spelling. A count alone would have hidden what this is. Opened here.

This is a THIRTEENTH ambiguous identity of a kind the prior screen could not see, because it
only compared master_player against itself: the two spellings live in DIFFERENT FEEDS.
"""
import os, sys, json, re, unicodedata
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B


def _norm_name(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


p_all, _ = B.load_master_player("research")
B.banner("s10  the unresolved spelling, opened")

# ---- exact selection: the normalized form only, no substring, no fuzzy -------------
TARGET_NORM = _norm_name("Cheyenne Parker")
mp = p_all.copy()
mp["_n"] = mp.player_name.map(_norm_name)
cand = mp[mp["_n"].str.startswith("cheyenneparker")]
print("  master_player rows whose normalized name starts 'cheyenneparker' (ALL seasons,")
print("  including sealed -- shown for identity resolution only, NO statistic taken from them):")
print(cand.groupby(["player_id", "player_name", "season"]).size().to_string())
pids = sorted(int(x) for x in cand.player_id.unique())
print("\n  distinct player_id behind those spellings: %s" % pids)
print("  -> %s" % ("ONE person, two spellings" if len(pids) == 1
                   else "MORE THAN ONE person"))

expl = cand[cand.season.isin(B.EXPL_SEASONS)]
print("\n  EXPLORATION PARTITION 2021-2024 only:")
print(expl.groupby(["player_id", "player_name", "season"]).size().to_string())
norms_expl = sorted(expl["_n"].unique().tolist())
print("  normalized spellings present in 2021-2024: %s" % norms_expl)
print("  is '%s' among them? %s" % (TARGET_NORM, TARGET_NORM in norms_expl))

print("\n  CONSEQUENCE for the market frame:")
print("    build_identity_index is built from OWNED GAMELOG name rows. If the props feed's")
print("    spelling never appears there, the row resolves to NaN and is EXCLUDED.")
print("    That is a DROP: 62 priced rows removed from the market denominator in 2024.")
print("    It is not the 'two players share one name' drop mode -- that has zero instances.")
print("    It is a CROSS-FEED drop: two feeds hold two spellings of one person, and the")
print("    join is normalized-exact with an empty alias table.")
print("\n    The m14 code already names this case in its own `known_variants` dict and")
print("    excludes-and-lists rather than guessing. The exclusion is correct behaviour;")
print("    the 62 rows are the measured cost of an empty alias table.")

json.dump({"target_norm": TARGET_NORM, "player_ids": pids,
           "spellings_all_seasons": sorted(cand.player_name.unique().tolist()),
           "spellings_2021_2024": sorted(expl.player_name.unique().tolist()),
           "rows_dropped_from_market_frame_2024": 62},
          open(os.path.join(B.OUT, "_s10.json"), "w"), indent=2)
