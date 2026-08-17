#!/usr/bin/env python3
"""E1_I0045 s02 -- RECONSTRUCT the universe's construction from the registered rules.

`prediction_contract_v5.py` is the generator.  Its rules are read from source, not inferred, and
re-executed here over the manifest-verified `master_player` so that the attribution of each
champion row to the source that admitted it is itself checkable.

  S1  tier A : box membership (DNP rows INCLUDED) in the team's latest <=5 ADMITTED prior
               same-season games.                                        [master_player: VERIFIED]
  S3  tier A : captured pregame availability report.  REPORT_ERA_START = 2026-07-30, so S3 can
               admit NOTHING in this partition.  Asserted, not assumed.
  S_TX tier B: transaction-wire acquisition within S_TX_HORIZON=3 team games, suppressed by a
               later release.                     [injury_history.csv: NO MANIFEST -> UNVERIFIABLE]
  S2  tier B: prior-season franchise affiliation, admitted while team_game_index < S2_HORIZON=5.
                                                                          [master_player: VERIFIED]

S1 and S2 are rebuilt here from a manifest-verified artifact and BACK NUMBERS.  S_TX is rebuilt
only as COLOUR and is labelled UNVERIFIABLE in every table it touches; no conclusion rests on it.
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rc_base as rb  # noqa: E402

pd.set_option("display.width", 240)
F = {}

PF = pd.read_parquet(os.path.join(rb.OUT, "_PF.parquet"))
pm = rb.load_player_master()
rb.assert_partition(PF, "PF")

# =========================================================================================
rb.hdr("1. THE REGISTERED CONSTANTS, READ OUT OF prediction_contract_v5.py BY AST")
import ast  # noqa: E402
src = open(os.path.join(rb.ROOT, "prediction_contract_v5.py"), encoding="utf-8").read()
tree = ast.parse(src)
CONST = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0],
                                                                             ast.Name):
        nm = node.targets[0].id
        if nm in ("ROSTER_LOOKBACK", "S_TX_HORIZON", "S2_HORIZON"):
            CONST[nm] = ast.literal_eval(node.value)
        if nm == "REPORT_ERA_START":
            CONST[nm] = "pd.Timestamp('2026-07-30T00:00:00Z')  (literal in source)"
for k, v in CONST.items():
    print("    %-18s = %s" % (k, v))
assert CONST["ROSTER_LOOKBACK"] == 5 and CONST["S2_HORIZON"] == 5 and CONST["S_TX_HORIZON"] == 3
F["registered_constants"] = CONST
F["contract_v5_sha256"] = rb.sha256_file(os.path.join(rb.ROOT, "prediction_contract_v5.py"))

# S3 cannot admit anything in this partition -- assert it
maxcut = pd.to_datetime(PF["forecast_cutoff"], utc=True).max()
era = pd.Timestamp("2026-07-30T00:00:00Z")
print("\n    latest forecast_cutoff in this partition = %s" % maxcut)
print("    REPORT_ERA_START                          = %s" % era)
assert maxcut < era, "S3 could admit inside this partition; the reconstruction must handle it"
print("    => S3 (the only Tier-A source that does not require a prior box row) admits ZERO rows")
print("       in 2021-2024.  Tier A here is S1 and nothing else.")
F["S3_admits_in_partition"] = 0

# =========================================================================================
rb.hdr("2. RE-EXECUTE S1 AND S2 OVER master_player")
tg = (pm[["game_id", "team_id", "season", "game_date"]].drop_duplicates()
      .sort_values(["team_id", "season", "game_date", "game_id"], kind="mergesort")
      .reset_index(drop=True))
tg["team_game_index"] = tg.groupby(["team_id", "season"]).cumcount()
tg["avail"] = (pd.to_datetime(tg["game_date"]).dt.tz_localize("UTC")
               + pd.Timedelta(hours=rb.AVAIL_LAG_HOURS))
print("  team-games in the partition = %d" % len(tg))

# box membership INCLUDING DNP rows -- v5's s1_index
s1 = {}
for t, g, p in zip(pm["team_id"], pm["game_id"], pm["player_id"]):
    s1.setdefault((int(t), str(g)), set()).add(int(p))

# prior-season franchise affiliation -- v5's s2_seasons
s2 = {}
for t, p, s in zip(pm["team_id"], pm["player_id"], pm["season"]):
    s2.setdefault((int(t), int(p)), set()).add(int(s))

by_ts = {}
for t, s, g, i, a in zip(tg["team_id"], tg["season"], tg["game_id"], tg["team_game_index"],
                         tg["avail"]):
    by_ts.setdefault((int(t), int(s)), []).append((str(g), int(i), a))
for k in by_ts:
    by_ts[k].sort(key=lambda x: x[1])

cut = pd.to_datetime(PF["forecast_cutoff"], utc=True).to_numpy()
gids = PF["game_id"].astype(str).to_numpy()
tids = PF["team_id"].to_numpy()
pids = PF["player_id"].to_numpy()
seas = PF["season"].to_numpy()

gidx_map = {(str(g), int(t)): int(i) for g, t, i
            in zip(tg["game_id"], tg["team_id"], tg["team_game_index"])}

n = len(PF)
by_s1 = np.zeros(n, bool)
by_s2 = np.zeros(n, bool)
gidx = np.full(n, -1, np.int64)
for i in range(n):
    t = int(tids[i]); s = int(seas[i]); g = gids[i]; p = int(pids[i]); c = cut[i]
    gi = gidx_map.get((g, t), -1)
    gidx[i] = gi
    games = by_ts.get((t, s), [])
    prior = [x for x in games if x[1] < gi]
    admitted = [x for x in prior if x[2] < c]
    window = admitted[-CONST["ROSTER_LOOKBACK"]:]
    for g2, _i2, _a2 in window:
        if p in s1.get((t, g2), ()):
            by_s1[i] = True
            break
    if gi < CONST["S2_HORIZON"]:
        seen = s2.get((t, p), set())
        if any(x < s for x in seen):
            by_s2[i] = True

PF["team_game_index"] = gidx
PF["rec_S1"] = by_s1
PF["rec_S2"] = by_s2
print("  rows admitted by S1 (reconstructed) = %d" % int(by_s1.sum()))
print("  rows admitted by S2 (reconstructed) = %d" % int(by_s2.sum()))

# --- the cross-check that matters: S1 must equal the manifest-verified tier-A membership -------
agree = int((PF["rec_S1"] == PF["tier_A"]).sum())
print("\n  CROSS-CHECK: reconstructed S1 vs contract-v4 membership (the tier-A definition)")
print("    agree on %d of %d rows (%.4f%%)" % (agree, n, 100.0 * agree / n))
dis = PF[PF["rec_S1"] != PF["tier_A"]]
print("    disagreements: %d   (S1 but not v4: %d ; v4 but not S1: %d)"
      % (len(dis), int((dis["rec_S1"] & ~dis["tier_A"]).sum()),
         int((~dis["rec_S1"] & dis["tier_A"]).sum())))
F["S1_vs_v4"] = {"n": n, "agree": agree, "share": agree / n,
                 "S1_not_v4": int((dis["rec_S1"] & ~dis["tier_A"]).sum()),
                 "v4_not_S1": int((~dis["rec_S1"] & dis["tier_A"]).sum())}

# =========================================================================================
rb.hdr("3. WHAT ADMITS THE TIER-B ROWS?")
B = PF[~PF["tier_A"]].copy()
B["src"] = np.where(B["rec_S2"], "S2 prior-season affiliation",
                    np.where(B["rec_S1"], "S1 (v4/S1 boundary)", "NEITHER S1 NOR S2 -> S_TX"))
t = (B.groupby("src").agg(n=("p_active_hat", "size"),
                          mean_p_active=("p_active_hat", "mean"),
                          appeared_rate=("appeared", "mean"),
                          sum_p=("p_active_hat", "sum"),
                          sum_appeared=("appeared", "sum")).reset_index())
t["share_of_tier_B"] = t["n"] / len(B)
t["excess_players_per_team_game"] = (t["sum_p"] - t["sum_appeared"]) / 1392.0
print(t.to_string(index=False))
t.to_csv(os.path.join(rb.OUT, "tier_b_by_admitting_source.csv"), index=False)
F["tier_b_by_source"] = t.to_dict("records")

print("\n  team_game_index of tier-B rows (S2 may only admit while index < %d):"
      % CONST["S2_HORIZON"])
print("    %s" % B["team_game_index"].value_counts().sort_index().head(12).to_dict())
print("    tier-B rows at team_game_index >= %d : %d (%.1f%%)"
      % (CONST["S2_HORIZON"], int((B["team_game_index"] >= CONST["S2_HORIZON"]).sum()),
         100.0 * float((B["team_game_index"] >= CONST["S2_HORIZON"]).mean())))

# =========================================================================================
rb.hdr("4. WHY A PAIRING PERSISTS -- THE S2 RULE HAS NO RECENCY, NO DEPARTURE, NO RELEASE")
s2b = B[B["rec_S2"]]
print("  S2-admitted tier-B rows: %d" % len(s2b))
z = (s2b.groupby("seasons_since_club")
     .agg(n=("p_active_hat", "size"), mean_p=("p_active_hat", "mean"),
          appeared=("appeared", "mean")).reset_index())
print("\n  by how many seasons ago she last played for THIS club:")
print(z.to_string(index=False))
z.to_csv(os.path.join(rb.OUT, "S2_rows_by_seasons_since_club.csv"), index=False)
F["S2_by_seasons_since_club"] = z.to_dict("records")

d = (s2b.groupby("departed").agg(n=("p_active_hat", "size"), mean_p=("p_active_hat", "mean"),
                                 appeared=("appeared", "mean")).reset_index())
print("\n  by the DEPARTURE signal (has she played for somebody else since):")
print(d.to_string(index=False))
F["S2_by_departed"] = d.to_dict("records")

# the whole tier-B population by departure, to sit beside E1_I0035's 0.0068
dd = (B.groupby("departed").agg(n=("p_active_hat", "size"), mean_p=("p_active_hat", "mean"),
                                appeared=("appeared", "mean"),
                                sum_p=("p_active_hat", "sum"),
                                sum_app=("appeared", "sum")).reset_index())
print("\n  ALL tier-B rows by the departure signal:")
print(dd.to_string(index=False))
F["tier_b_by_departed"] = dd.to_dict("records")

A = PF[PF["tier_A"]]
da = (A.groupby("departed").agg(n=("p_active_hat", "size"), mean_p=("p_active_hat", "mean"),
                                appeared=("appeared", "mean")).reset_index())
print("\n  ALL tier-A rows by the departure signal (a mid-season trade can make one):")
print(da.to_string(index=False))
F["tier_a_by_departed"] = da.to_dict("records")

# =========================================================================================
rb.hdr("5. UNVERIFIABLE COLOUR -- contract v5's own labels, and the transaction wire")
v5p = os.path.join(rb.CV5, "player_game.parquet")
mani = v5p + ".manifest.json"
print("  %s exists=%s   sibling manifest exists=%s"
      % (os.path.basename(v5p), os.path.exists(v5p), os.path.exists(mani)))
print("  => NO MANIFEST => UNVERIFIABLE => may not back a number.  Used below as COLOUR ONLY.")
F["v5_manifest_present"] = os.path.exists(mani)
if os.path.exists(v5p):
    v5 = pd.read_parquet(v5p)
    v5 = v5[v5["season"].isin(rb.EXPLORATION_SEASONS)]
    v5 = rb.pick(v5, ("row_uid", "universe_tier", "candidate_source", "team_assignment_source"),
                 "cv5 UNVERIFIABLE")
    m = PF.merge(v5, on="row_uid", how="left")
    print("\n  [UNVERIFIABLE] champion rows matched to a v5 row: %d of %d"
          % (int(m["universe_tier"].notna().sum()), len(m)))
    ct = pd.crosstab(m["tier_A"], m["team_assignment_source"].fillna("<no v5 row>"))
    print("  [UNVERIFIABLE] tier_A (v4 membership) x v5 team_assignment_source:")
    print(ct.to_string())
    cc = pd.crosstab(m.loc[~m["tier_A"], "team_assignment_source"].fillna("<none>"),
                     m.loc[~m["tier_A"], "rec_S2"])
    print("\n  [UNVERIFIABLE] tier-B: v5's own source label x my reconstructed S2:")
    print(cc.to_string())
    F["UNVERIFIABLE_v5_crosstab"] = json.loads(ct.to_json())

txp = rb.TRANSACTIONS
print("\n  %s exists=%s   sibling manifest exists=%s"
      % (os.path.basename(txp), os.path.exists(txp),
         os.path.exists(txp + ".manifest.json")))
print("  => NO MANIFEST => UNVERIFIABLE.  Its observation time is ALSO a single retrospective")
print("     scrape (S_TX_OBSERVED_TIME = 2026-07-30T17:42Z), so it is not provably pre-cutoff")
print("     for ANY 2021-2024 row.  It is therefore NOT used to build any rule measured here.")
F["transactions_manifest_present"] = os.path.exists(txp + ".manifest.json")

# =========================================================================================
rb.hdr("6. PERSIST")
PF.to_parquet(os.path.join(rb.OUT, "_PF.parquet"), index=False)
rb.dump(F, "_s02.json")
print("  written.")
print("\nDONE s02")
