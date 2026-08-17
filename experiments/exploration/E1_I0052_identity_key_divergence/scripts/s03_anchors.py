"""E1_I0052 s03 -- ANCHOR REPRODUCTION, before any new statistic.

Reproduces the load-bearing constants of E1_I0048 (the screen that created this one)
and of the partition itself. Anything that does not reproduce is reported, not hidden.
"""
import os, sys, json
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B

RECENCY_GAMES = 3   # daily_forecast.py:120, pre-repair (735b63bc)

B.banner("s03  ANCHORS")

anchors = []


def anchor(aid, what, expect, got, tol=0.0):
    ok = (abs(float(got) - float(expect)) <= tol) if isinstance(expect, (int, float)) \
        else (got == expect)
    err = (float(got) - float(expect)) if isinstance(expect, (int, float)) else None
    anchors.append({"anchor": aid, "quantity": what, "expected": expect,
                    "reproduced": got, "abs_err": err,
                    "status": "EXACT" if (err == 0 or (err is None and ok))
                              else ("PASS" if ok else "MISMATCH")})
    print("  %-5s %-58s expect=%-10s got=%-10s %s" %
          (aid, what[:58], expect, got, anchors[-1]["status"]))


# ---------------- manifests -----------------------------------------------------
B.banner("manifest status of every artifact this screen reads")
for lbl, path in [("master_player RESEARCH", B.MP_RESEARCH),
                  ("master_player PRODUCTION", B.MP_PROD),
                  ("master_team RESEARCH", B.MT_RESEARCH)]:
    m = B.manifest_status(path)
    print("  %-26s %-22s %s" % (lbl, m["status"], m.get("path") or ""))
    if m["status"] == "PRESENT":
        print("     %-23s asof_granularity=%s  fit_through_date=%s"
              % ("", m.get("asof_granularity"), m.get("fit_through_date")))

p_all, mp_path = B.load_master_player("research")
print("\n  read: %s" % mp_path)
print("  sha256: %s" % B.sha256(mp_path))
print("  rows(all seasons)=%d  cols=%d" % (len(p_all), p_all.shape[1]))

# ---------------- A1: player_id nulls -------------------------------------------
B.banner("A1-A3  the stable key exists and is complete")
anchor("A1", "master_player rows, all seasons", 34199, len(p_all))
anchor("A2", "null player_id rows, all seasons", 0, int(p_all.player_id.isna().sum()))
anchor("A3", "player_id dtype is Int64", "Int64", str(p_all.player_id.dtype))

p, guard = B.partition_guard(p_all, "season", "master_player")
print("\n  PARTITION GUARD: %s" % json.dumps(guard))

# ---------------- A4-A6: identity ambiguity -------------------------------------
B.banner("A4-A8  identity ambiguity, exact equality only")
ids_all, names_all = B.identity_table(p_all)
anchor("A4", "distinct player_id with >1 player_name, ALL seasons", 13, len(ids_all))
anchor("A5", "distinct player_name with >1 player_id, ALL seasons", 0, len(names_all))

ids_p, names_p = B.identity_table(p)
anchor("A6", "distinct player_id with >1 player_name, 2021-2024", 12, len(ids_p))
anchor("A7", "distinct player_name with >1 player_id, 2021-2024", 0, len(names_p))
anchor("A8", "ambiguous ids 2021-2024 == declared allowlist", True,
       sorted(ids_p.player_id.tolist()) == sorted(B.AMBIGUOUS_IDS_2021_2024))
print("\n  RESOLVED AMBIGUOUS ID LIST (printed, per the no-name-selection rule):")
for _, r in ids_p.iterrows():
    print("     %-9d  %-46s  seasons=%-20s teams=%s"
          % (r.player_id, r.names, r.seasons, r.teams))

# ---------------- A9: roster-window divergence (E1_I0048 headline) --------------
B.banner("A9-A12  roster-window divergence under the two keys (E1_I0048 s05 rule)")


def window_diffs(frame):
    rows = []
    for (s, ab), g in frame.groupby(["season", "team_abbreviation"]):
        gids = sorted(g.game_id.unique(),
                      key=lambda gid: g[g.game_id == gid].game_date.iloc[0])
        for i in range(1, len(gids) + 1):
            recent = set(gids[max(0, i - RECENCY_GAMES):i])
            rr = g[g.game_id.isin(recent)]
            n_name = rr.player_name.nunique()
            n_id = rr.player_id.nunique()
            rows.append({"season": int(s), "team": ab, "slate_index": i,
                         "n_name": int(n_name), "n_id": int(n_id),
                         "delta": int(n_name - n_id)})
    return pd.DataFrame(rows)


wd = window_diffs(p)
wd.to_csv(os.path.join(B.OUT, "_s03_windows_2021_2024.csv"), index=False)
anchor("A9", "roster windows simulated, 2021-2024", 1940, len(wd))
anchor("A10", "windows where the two keys differ, 2021-2024", 196, int((wd.delta != 0).sum()))
anchor("A11", "divergence rate 2021-2024 (%)", 10.10,
       round(100.0 * (wd.delta != 0).mean(), 2), tol=0.005)
anchor("A12", "windows with NEGATIVE delta (drop mode), 2021-2024", 0,
       int((wd.delta < 0).sum()))
print("\n  delta distribution: %s" % wd.delta.value_counts().sort_index().to_dict())

ap = pd.DataFrame(anchors)
ap.to_csv(os.path.join(B.OUT, "ANCHOR_REPRODUCTION.csv"), index=False)
print("\n  anchors: %d  EXACT=%d  PASS=%d  MISMATCH=%d"
      % (len(ap), (ap.status == "EXACT").sum(), (ap.status == "PASS").sum(),
         (ap.status == "MISMATCH").sum()))

ids_p.to_csv(os.path.join(B.OUT, "_s03_ambiguous_identities_2021_2024.csv"), index=False)
json.dump({"guard": guard, "mp_sha256": B.sha256(mp_path), "mp_path": mp_path,
           "n_anchors": len(ap),
           "n_exact": int((ap.status == "EXACT").sum()),
           "n_mismatch": int((ap.status == "MISMATCH").sum())},
          open(os.path.join(B.OUT, "_s03.json"), "w"), indent=2)
