"""E1_I0052 s04 -- THE MEASUREMENT at the one live research-lane site that is name-keyed.

E0_I0006_usage_redistribution/analyze_clean.py is the authoritative ("clean") arm of a screen
that produced a LIVE VERDICT (kill). Three of its keyed operations carry player_name in the key:

  L20  baseline    = played.groupby(["player_id","player_name","team_id","season"]).agg(...)
  L87  tm_baseline = control.groupby(["player_id","player_name"]).agg(...)
  L92  merged      = game_rows.merge(tm_baseline, on=["player_id","player_name"], how="inner")

All three are COMPOSITE (id AND name). A composite key diverges from the id-only key exactly when
one player_id carries two player_name spellings inside the group -- the duplication mode -- and
the duplication then propagates into two thresholds (games_played >= 15 ; n_control_games >= 5)
and one INNER JOIN, either of which can turn a duplication into a DROP.

This script re-executes the screen's own rule under both keys on the SAME frame. One line changed
at a time. No fitting, no champion, nothing enacted.

D101: a row-set change under a different key IS a denominator change. Stated at every occurrence.
"""
import os, sys, json
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B

SRC = os.path.join(B.EXP, "exploration", "E0_I0006_usage_redistribution")
PLAYED = os.path.join(SRC, "clean_played_panel.parquet")
ROSTER = os.path.join(SRC, "clean_roster_panel.parquet")

B.banner("s04  E0_I0006_usage_redistribution -- both keys on the same frame")

for lbl, path in [("clean_played_panel", PLAYED), ("clean_roster_panel", ROSTER)]:
    m = B.manifest_status(path)
    print("  %-20s manifest=%-22s sha256=%s" % (lbl, m["status"], B.sha256(path)[:16]))
print("  (E0_I0006/NOTES.md: these are rebuilt from raw per-season gamelogs precisely because")
print("   master_player's manifest declares fit_through_season 2026. Provenance is that screen's.)")

played = pd.read_parquet(PLAYED)
roster = pd.read_parquet(ROSTER)
played, g1 = B.partition_guard(played, "season", "clean_played_panel")
roster, g2 = B.partition_guard(roster, "season", "clean_roster_panel")
print("\n  PARTITION GUARD played : %s" % json.dumps(g1))
print("  PARTITION GUARD roster : %s" % json.dumps(g2))

# ---------------------------------------------------------------- identity table
B.banner("1. identity ambiguity IN THIS SCREEN'S OWN SOURCE (not master_player)")
gg = played[["player_id", "player_name"]].dropna().drop_duplicates()
i2n = gg.groupby("player_id").player_name.nunique()
n2i = gg.groupby("player_name").player_id.nunique()
amb_ids = sorted(int(x) for x in i2n[i2n > 1].index)
amb_names = sorted(n2i[n2i > 1].index)
print("  played-panel rows              : %d" % len(played))
print("  distinct player_id             : %d" % played.player_id.nunique())
print("  distinct player_name           : %d" % played.player_name.nunique())
print("  ids with >1 name (DUPLICATION) : %d  -> %s" % (len(amb_ids), amb_ids))
print("  names with >1 id (DROP)        : %d  -> %s" % (len(amb_names), list(amb_names)))
for pid in amb_ids:
    sub = played[played.player_id == pid]
    print("     %-9d %-46s seasons=%s teams=%s"
          % (pid, " | ".join(sorted(sub.player_name.unique())),
             sorted(int(s) for s in sub.season.unique()),
             sorted(int(t) for t in sub.team_id.unique())))
print("\n  cross-check vs master_player 2021-2024 allowlist: %s"
      % ("SUBSET" if set(amb_ids) <= set(B.AMBIGUOUS_IDS_2021_2024) else "NOT A SUBSET"))
print("  ids in master allowlist but absent from this panel: %s"
      % sorted(set(B.AMBIGUOUS_IDS_2021_2024) - set(amb_ids)))

results = {"site_rows": []}

# ---------------------------------------------------------------- SITE 1 : L20
B.banner("2. SITE L20 -- the high-usage pool (the screen's fit population)")
NAMEKEY = ["player_id", "player_name", "team_id", "season"]
IDKEY = ["player_id", "team_id", "season"]


def build_baseline(keys):
    b = played.groupby(keys).agg(
        baseline_usage=("usage_percentage", "mean"),
        games_played=("game_id", "count"),
        start_rate=("start_position", lambda s: (s.fillna("") != "").mean()),
    ).reset_index()
    return b


b_name = build_baseline(NAMEKEY)
b_id = build_baseline(IDKEY)
hi_name = b_name[(b_name.baseline_usage >= 0.20) & (b_name.games_played >= 15)].copy()
hi_id = b_id[(b_id.baseline_usage >= 0.20) & (b_id.games_played >= 15)].copy()

print("  baseline rows  name-key=%d   id-key=%d   delta=%+d"
      % (len(b_name), len(b_id), len(b_name) - len(b_id)))
print("  ANCHOR: published high-usage player-team-seasons (NOTES.md) = 200")
print("  high-usage pool  name-key=%d   id-key=%d   delta=%+d"
      % (len(hi_name), len(hi_id), len(hi_name) - len(hi_id)))

set_name = set(map(tuple, hi_name[["player_id", "team_id", "season"]].values.tolist()))
set_id = set(map(tuple, hi_id[["player_id", "team_id", "season"]].values.tolist()))
only_name = sorted(set_name - set_id)
only_id = sorted(set_id - set_name)
dup_in_name = hi_name.groupby(["player_id", "team_id", "season"]).size()
dup_in_name = dup_in_name[dup_in_name > 1]
print("  identities present under ID key but MISSING under NAME key (DROP): %d  %s"
      % (len(only_id), only_id))
print("  identities present under NAME key but not ID key                : %d  %s"
      % (len(only_name), only_name))
print("  identities appearing TWICE under the NAME key (DUPLICATION)     : %d  %s"
      % (len(dup_in_name), dup_in_name.to_dict()))
results["site_rows"].append({
    "screen": "E0_I0006_usage_redistribution", "file": "analyze_clean.py", "line": 20,
    "op": "GROUPBY", "keys_used": "|".join(NAMEKEY), "stable_id_available": "YES",
    "id_only_keys": "|".join(IDKEY),
    "rows_name_key": len(b_name), "rows_id_key": len(b_id),
    "rows_diverging": abs(len(b_name) - len(b_id)),
    "direction": ("DUPLICATION" if len(b_name) > len(b_id) else
                  ("DROP" if len(b_name) < len(b_id) else "NONE")),
    "downstream_pool_name": len(hi_name), "downstream_pool_id": len(hi_id),
    "pool_dropped_by_name_key": len(only_id), "pool_duplicated_by_name_key": len(dup_in_name),
})

# per-identity forensics for every ambiguous id
B.banner("2b. named cases -- what the split does to each ambiguous identity's pool row")
rows_fx = []
for pid in amb_ids:
    for (tid, ssn), sub in played[played.player_id == pid].groupby(["team_id", "season"]):
        n_by_name = sub.groupby("player_name").size().to_dict()
        tot = int(sub.shape[0])
        u_all = float(sub.usage_percentage.mean())
        parts = []
        for nm, cnt in sorted(n_by_name.items()):
            uu = float(sub[sub.player_name == nm].usage_percentage.mean())
            parts.append("%s: gp=%d usage=%.4f%s" % (nm, cnt, uu,
                         "  QUALIFIES" if (cnt >= 15 and uu >= 0.20) else ""))
        q_id = (tot >= 15 and u_all >= 0.20)
        q_name_any = any(c >= 15 and float(sub[sub.player_name == n].usage_percentage.mean()) >= 0.20
                         for n, c in n_by_name.items())
        n_qual_name = sum(1 for n, c in n_by_name.items()
                          if c >= 15 and float(sub[sub.player_name == n].usage_percentage.mean()) >= 0.20)
        verdict = ("SAME" if (q_id == q_name_any and n_qual_name <= 1) else
                   ("DROPPED_BY_NAME_KEY" if q_id and not q_name_any else
                    ("DUPLICATED_BY_NAME_KEY" if n_qual_name > 1 else "ADDED_BY_NAME_KEY")))
        print("  pid=%-9d team=%-5d season=%d  gp_total=%-3d usage_total=%.4f  id_qualifies=%s"
              % (pid, tid, ssn, tot, u_all, q_id))
        for pp in parts:
            print("        %s" % pp)
        print("        -> %s" % verdict)
        rows_fx.append({"player_id": pid, "team_id": int(tid), "season": int(ssn),
                        "names": " | ".join(sorted(n_by_name)),
                        "gp_total": tot, "usage_total": round(u_all, 6),
                        "id_qualifies_high_usage": bool(q_id),
                        "n_name_rows_qualifying": n_qual_name,
                        "split_detail": " ; ".join(parts), "verdict": verdict})
pd.DataFrame(rows_fx).to_csv(os.path.join(B.OUT, "_s04_identity_split_forensics.csv"), index=False)

# ---------------------------------------------------------------- SITE 2/3 : L87/L92
B.banner("3. SITES L87 + L92 -- teammate baseline and the INNER JOIN")
print("  Re-executing build_redistribution() under both keys on the identical event list.")

hi_pub = hi_name.copy()  # the screen's own pool, as published


def _absence_events(hi_pool):
    ridx = roster.set_index(["player_id", "team_id", "season"])
    rows = []
    for _, row in hi_pool.iterrows():
        key = (row.player_id, row.team_id, row.season)
        if key not in ridx.index:
            continue
        sub = ridx.loc[[key]]
        for _, ar in sub[sub.is_dnp].iterrows():
            rows.append({"player_id": row.player_id, "team_id": row.team_id,
                         "season": row.season, "game_id": ar.game_id})
    return pd.DataFrame(rows).drop_duplicates(
        subset=["player_id", "team_id", "season", "game_id"])


ev = _absence_events(hi_pub)
print("  ANCHOR: published absence-game rows (NOTES.md) = 622   reproduced = %d" % len(ev))


def build_redis(event_rows, keys, leave_one_out=False):
    out, n_drop_join, n_dup_join = [], 0, 0
    for r in event_rows:
        pid, tid, season, gid = r["player_id"], r["team_id"], r["season"], r["game_id"]
        pres = played[(played.team_id == tid) & (played.season == season) &
                      (played.player_id == pid)].game_id.unique()
        control_games = [g for g in pres if not (leave_one_out and g == gid)]
        if len(control_games) < 6:
            continue
        control = played[(played.team_id == tid) & (played.season == season) &
                         (played.game_id.isin(control_games)) & (played.player_id != pid)]
        tmb = control.groupby(keys).agg(
            tm_baseline_usage=("usage_percentage", "mean"),
            n_control_games=("game_id", "count")).reset_index()
        tmb = tmb[tmb.n_control_games >= 5]
        gr = played[(played.game_id == gid) & (played.team_id == tid) &
                    (played.player_id != pid)]
        merged = gr.merge(tmb, on=keys, how="inner", suffixes=("", "_b"))
        if merged.empty:
            continue
        merged["delta_usage"] = merged.usage_percentage - merged.tm_baseline_usage
        merged["event_key"] = "%s_%s_%s_%s" % (pid, tid, season, gid)
        out.append(merged[["event_key", "player_id", "delta_usage"]])
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


ev_rec = ev.to_dict("records")
r_name = build_redis(ev_rec, ["player_id", "player_name"], False)
r_id = build_redis(ev_rec, ["player_id"], False)
print("  ANCHOR: published teammate-level redistribution rows (NOTES.md) = 4,983")
print("  reproduced  name-key=%d   id-key=%d   delta=%+d"
      % (len(r_name), len(r_id), len(r_name) - len(r_id)))


def top1(df):
    def f(g):
        pos = g[g.delta_usage > 0].sort_values("delta_usage", ascending=False)
        if len(pos) == 0 or pos.delta_usage.sum() <= 0:
            return np.nan
        return float(pos.delta_usage.iloc[0] / pos.delta_usage.sum())
    return df.groupby("event_key").apply(f, include_groups=False)


t_name, t_id = top1(r_name), top1(r_id)
print("\n  ANCHOR: published real top1_share mean=0.470 median=0.454 n=578")
print("  name-key  mean=%.4f median=%.4f n=%d" % (t_name.mean(), t_name.median(), t_name.notna().sum()))
print("  id-key    mean=%.4f median=%.4f n=%d" % (t_id.mean(), t_id.median(), t_id.notna().sum()))
print("  D101 denominator: n changes by %+d events; top1_share mean changes by %+.6f"
      % (t_id.notna().sum() - t_name.notna().sum(), t_id.mean() - t_name.mean()))

# which events actually differ
common = sorted(set(t_name.index) & set(t_id.index))
dd = pd.DataFrame({"name": t_name.reindex(common), "id": t_id.reindex(common)})
dd["absdiff"] = (dd["name"] - dd["id"]).abs()
n_ev_diff = int((dd.absdiff > 1e-12).sum())
print("  events present in both: %d ; events whose top1_share DIFFERS: %d"
      % (len(common), n_ev_diff))
print("  events only under name-key: %d ; only under id-key: %d"
      % (len(set(t_name.index) - set(t_id.index)), len(set(t_id.index) - set(t_name.index))))
if n_ev_diff:
    print(dd[dd.absdiff > 1e-12].sort_values("absdiff", ascending=False).head(20).to_string())

results["site_rows"].append({
    "screen": "E0_I0006_usage_redistribution", "file": "analyze_clean.py", "line": 87,
    "op": "GROUPBY", "keys_used": "player_id|player_name", "stable_id_available": "YES",
    "id_only_keys": "player_id",
    "rows_name_key": len(r_name), "rows_id_key": len(r_id),
    "rows_diverging": abs(len(r_name) - len(r_id)),
    "direction": ("DUPLICATION" if len(r_name) > len(r_id) else
                  ("DROP" if len(r_name) < len(r_id) else "NONE")),
    "downstream_pool_name": int(t_name.notna().sum()),
    "downstream_pool_id": int(t_id.notna().sum()),
    "pool_dropped_by_name_key": len(set(t_id.index) - set(t_name.index)),
    "pool_duplicated_by_name_key": 0,
})
results["site_rows"].append({
    "screen": "E0_I0006_usage_redistribution", "file": "analyze_clean.py", "line": 92,
    "op": "JOIN(inner)", "keys_used": "player_id|player_name", "stable_id_available": "YES",
    "id_only_keys": "player_id",
    "rows_name_key": len(r_name), "rows_id_key": len(r_id),
    "rows_diverging": abs(len(r_name) - len(r_id)),
    "direction": ("DUPLICATION" if len(r_name) > len(r_id) else
                  ("DROP" if len(r_name) < len(r_id) else "NONE")),
    "downstream_pool_name": int(t_name.notna().sum()),
    "downstream_pool_id": int(t_id.notna().sum()),
    "pool_dropped_by_name_key": len(set(t_id.index) - set(t_name.index)),
    "pool_duplicated_by_name_key": 0,
})

results["published_stat"] = {
    "top1_share_mean_name_key": float(t_name.mean()),
    "top1_share_mean_id_key": float(t_id.mean()),
    "top1_share_median_name_key": float(t_name.median()),
    "top1_share_median_id_key": float(t_id.median()),
    "n_name_key": int(t_name.notna().sum()), "n_id_key": int(t_id.notna().sum()),
    "published_mean": 0.470, "published_median": 0.454, "published_n": 578,
    "placebo_noise_floor_published": 0.539,
    "verdict_published": "kill",
}
results["ambiguous_ids_in_panel"] = amb_ids
results["names_with_multiple_ids_in_panel"] = list(amb_names)
json.dump(results, open(os.path.join(B.OUT, "_s04.json"), "w"), indent=2, default=str)
dd.to_csv(os.path.join(B.OUT, "_s04_event_top1_both_keys.csv"))
print("\nDONE s04")
