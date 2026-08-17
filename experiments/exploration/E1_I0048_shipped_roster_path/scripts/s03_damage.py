#!/usr/bin/env python3
"""s03 â€” damage in shipped output, restricted to the DEFECTIVE ERA and to
team-slots that passed the s02 fidelity gate.

The repair landed in commit 55d84f1e (2026-08-06 19:47Z). Shipped records
0..39 were produced by the naive name-keyed roster; 40..63 by the
identity-resolved roster. Damage is quantified on the pre-repair era only.

SEALED PARTITION (2026): descriptive counts of rows and names emitted by the
code. NO skill statistic, NO outcome column. Enforced by the allowlist.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent.parent
LIVE = Path(r"C:\Users\jgallagher\wnba-betting-model")
ET = ZoneInfo("America/New_York")
RECENCY_GAMES = 3
MINUTES_ALPHA = 0.30
REPAIR_COMMITS = {"55d84f1edd11e9412cc993f0a64e7d9a260cb32b",
                  "9cfe22e61d77b1478f45e68676b8a73afc294933",
                  "5943846f4d01acf3341ef26f798f045a92655c44"}

TEAMS = {"Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
         "Dallas Wings": "DAL", "Golden State Valkyries": "GSV",
         "Indiana Fever": "IND", "Las Vegas Aces": "LVA",
         "Los Angeles Sparks": "LAS", "Minnesota Lynx": "MIN",
         "New York Liberty": "NYL", "Phoenix Mercury": "PHX",
         "Portland Fire": "PDX", "Seattle Storm": "SEA",
         "Toronto Tempo": "TOR", "Washington Mystics": "WAS"}

ALLOW = ["game_id", "season", "game_date", "team_id", "team_abbreviation",
         "player_id", "player_name", "minutes"]
BANNED = ["pts", "fgm", "fga", "reb", "ast", "plus_minus", "appeared"]


def _norm_name(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


print("=" * 78)
print("s03 â€” SHIPPED DAMAGE, pre-repair era, fidelity-gated slots only")
print("=" * 78)

p = pd.read_parquet(LIVE / "data" / "masters" / "master_player.parquet")
missing = [c for c in ALLOW if c not in p.columns]
assert not missing, f"allowlist unresolved: {missing}"
p = p[ALLOW].copy()
assert not [c for c in p.columns if c in BANNED], "OUTCOME COLUMN LEAKED"
p["game_date"] = pd.to_datetime(p.game_date)
print(f"resolved columns by explicit allowlist: {ALLOW}")
print(f"master rows {len(p)}; outcome columns asserted absent: {BANNED}")

inj_all = pd.read_csv(LIVE / "data" / "injury_capture" / "injury_log.csv")
inj_all["cap_dt"] = pd.to_datetime(inj_all.capture_utc,
                                   format="%Y%m%dT%H%M%SZ", utc=True)

recs = [json.loads(l) for l in
        (LIVE / "forecasts" / "forecast_log.jsonl").read_text(encoding="utf-8")
        .splitlines() if l.strip()]
FID = pd.read_csv(HERE / "FIDELITY.csv")
FID = FID[FID.log == "LIVE_main_worktree"]
repro = {(int(r.record_idx), r.side): bool(r.reproduced) for r in FID.itertuples()}

abbr_to_name = {v: k for k, v in TEAMS.items()}
rows, cases = [], []
n_pre_slots = n_pre_repro = 0

for r in recs:
    core = r["core_only_prediction"]
    sha = core["provenance"]["source_version"].replace("git:", "")
    era = "post_repair" if sha in REPAIR_COMMITS else "PRE_REPAIR"
    if "player_layer_informational" not in core:
        continue
    if era != "PRE_REPAIR":
        continue
    cutoff = datetime.fromisoformat(r["forecast_cutoff"])
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    slate_date = cutoff.astimezone(ET).date()
    season = slate_date.year
    ps = p[(p.season == season) & (p.game_date.dt.date < slate_date)]

    for side in ("home", "away"):
        ab = core[f"{side}_team"]
        n_pre_slots += 1
        if not repro.get((int(r["record_idx"]), side), False):
            continue
        n_pre_repro += 1
        tp = ps[ps.team_abbreviation == ab]
        tgames = sorted(tp.game_id.unique(),
                        key=lambda gid: tp[tp.game_id == gid].game_date.iloc[0])
        recent = set(tgames[-RECENCY_GAMES:])
        rec_rows = tp[tp.game_id.isin(recent)]

        # ---- the two keys, on the SAME frame (controlled: no master drift) --
        name_roster = set(rec_rows.player_name.unique())     # shipped key
        id_roster = set(rec_rows.player_id.unique())         # stable key

        # name -> distinct player_id  (collision: two people, one emitted row)
        n2i = rec_rows.groupby("player_name").player_id.nunique()
        collisions = n2i[n2i > 1]
        # player_id -> distinct player_name (variant: one person, two rows)
        i2n = rec_rows.groupby("player_id").player_name.nunique()
        variants = i2n[i2n > 1]

        # ---- departure, strictly pre-cutoff, no outcome data ---------------
        # E1_I0045 s01:277-278 exactly:
        #   departed = last_any_date.notna & last_any_team != team_id
        #              & (last_club_date.isna | last_any_date > last_club_date)
        # On the SHIPPED roster that predicate pools two opposite meanings,
        # because the shipped roster already requires current box-score
        # membership (DNP rows included). Split, and report both:
        #   STALE   â€” has appeared for this club, has since appeared elsewhere
        #             => a genuinely phantom pairing (the defect being hunted)
        #   ARRIVAL â€” has never appeared for this club, last appeared elsewhere
        #             => a correct, current entry for a player who has not
        #                debuted. NOT damage.
        app = ps[(ps.minutes.notna()) & (ps.minutes > 0)]
        team_id = rec_rows.team_id.iloc[0]
        n_departed = n_stale = n_arrival = 0
        for pid in id_roster:
            a = app[app.player_id == pid].sort_values(["game_date", "game_id"])
            if not len(a):
                continue                      # never appeared anywhere
            last_any_team = a.team_id.iloc[-1]
            ac = a[a.team_id == team_id]
            last_club_date = ac.game_date.iloc[-1] if len(ac) else pd.NaT
            last_any_date = a.game_date.iloc[-1]
            departed = (last_any_team != team_id
                        and (pd.isna(last_club_date)
                             or last_any_date > last_club_date))
            if not departed:
                continue
            n_departed += 1
            kind = "STALE_PHANTOM_PAIRING" if len(ac) else "ARRIVAL_NOT_YET_DEBUTED"
            if len(ac):
                n_stale += 1
            else:
                n_arrival += 1
            nm = sorted(rec_rows[rec_rows.player_id == pid].player_name.unique())
            k = len(a)
            t5 = float(a.minutes.iloc[-5:].mean())
            cases.append({"case": kind, "record_idx": r["record_idx"],
                          "slate_date": str(slate_date), "team": ab,
                          "player_id": int(pid), "player_name": "|".join(nm),
                          "last_appearance_for": a.team_abbreviation.iloc[-1],
                          "appeared_for_this_club": int(len(ac)),
                          "n_prior_app_season": k, "trail5_min": round(t5, 3),
                          "in_decision_stratum": bool(k >= 8 and t5 >= 24)})

        for nm, k in collisions.items():
            pids = sorted(rec_rows[rec_rows.player_name == nm].player_id.unique())
            cases.append({"case": "NAME_COLLISION_MERGED", "record_idx":
                          r["record_idx"], "slate_date": str(slate_date),
                          "team": ab, "player_id": ";".join(map(str, pids)),
                          "player_name": nm, "n_prior_app_season": None,
                          "trail5_min": None, "in_decision_stratum": None})
        for pid, k in variants.items():
            nms = sorted(rec_rows[rec_rows.player_id == pid].player_name.unique())
            a = app[app.player_id == pid]
            kk = len(a)
            t5 = float(a.minutes.iloc[-5:].mean()) if kk else float("nan")
            cases.append({"case": "NAME_VARIANT_DUPLICATED", "record_idx":
                          r["record_idx"], "slate_date": str(slate_date),
                          "team": ab, "player_id": int(pid),
                          "player_name": "|".join(nms),
                          "n_prior_app_season": kk,
                          "trail5_min": (round(t5, 3) if kk else None),
                          "in_decision_stratum": bool(kk >= 8 and t5 >= 24)})

        rows.append({"record_idx": r["record_idx"], "slate_date": str(slate_date),
                     "team": ab, "side": side, "sha": sha[:12],
                     "n_roster_name_key": len(name_roster),
                     "n_roster_id_key": len(id_roster),
                     "keys_differ": len(name_roster) != len(id_roster),
                     "n_name_collisions": int(len(collisions)),
                     "n_name_variants": int(len(variants)),
                     "n_departed_E1_I0045_rule": n_departed,
                     "n_stale_phantom": n_stale,
                     "n_arrival_not_debuted": n_arrival})

D = pd.DataFrame(rows)
C = pd.DataFrame(cases)
D.to_csv(HERE / "SHIPPED_DAMAGE_by_slot.csv", index=False)

print(f"\npre-repair team-slots in shipped log : {n_pre_slots}")
print(f"  passed the fidelity gate (usable)  : {n_pre_repro}")
print(f"  fidelity rate                      : {n_pre_repro}/{n_pre_slots}")

print("\n--- H1  phantom (departed) player-club pairings ---")
print(f"  E1_I0045 'departed' predicate, ported verbatim : "
      f"{int(D.n_departed_E1_I0045_rule.sum())} emissions on "
      f"{int((D.n_departed_E1_I0045_rule>0).sum())} of {len(D)} slots")
print(f"    of which STALE  (appeared here, since appeared elsewhere) : "
      f"{int(D.n_stale_phantom.sum())}   <-- THE DEFECT")
print(f"    of which ARRIVAL (never appeared here, not yet debuted)   : "
      f"{int(D.n_arrival_not_debuted.sum())}   <-- correct rostering, NOT damage")

print("\n--- H2/H4  name key vs player_id key, SAME frame (no drift) ---")
print(f"  team-slots where the two keys give different roster sizes : "
      f"{int(D.keys_differ.sum())} of {len(D)}")
print(f"  total name->multi-id collisions (a player DROPPED)        : {int(D.n_name_collisions.sum())}")
print(f"  total id->multi-name variants  (a player DUPLICATED)      : {int(D.n_name_variants.sum())}")

if len(C):
    print("\n--- named cases ---")
    print(C.to_string(index=False))
    print("\n--- DECISION STRATUM (n_prior_app_season>=8 AND trail5_min>=24) ---")
    ds = C[C.in_decision_stratum == True]  # noqa: E712
    print(f"  affected emissions reaching the decision stratum: {len(ds)} of {len(C)}")
    if len(ds):
        print(ds.to_string(index=False))
else:
    print("\n  NO affected emissions of any kind on the pre-repair era.")
    print("  DECISION STRATUM: 0 affected emissions, therefore 0 reach it.")

cols = ["case", "record_idx", "slate_date", "team", "player_id", "player_name",
        "n_prior_app_season", "trail5_min", "in_decision_stratum"]
(C if len(C) else pd.DataFrame(columns=cols)).to_csv(
    HERE / "SHIPPED_DAMAGE.csv", index=False)

json.dump({"pre_repair_slots": n_pre_slots, "fidelity_passed": n_pre_repro,
           "departed_emissions_E1_I0045_rule": int(D.n_departed_E1_I0045_rule.sum()), "stale_phantom_emissions": int(D.n_stale_phantom.sum()), "arrival_not_debuted_emissions": int(D.n_arrival_not_debuted.sum()),
           "name_collisions": int(D.n_name_collisions.sum()),
           "name_variants": int(D.n_name_variants.sum()),
           "slots_keys_differ": int(D.keys_differ.sum()),
           "n_cases": int(len(C)),
           "n_cases_decision_stratum": (int((C.in_decision_stratum == True).sum())  # noqa: E712
                                        if len(C) else 0)},
          open(HERE / "_s03.json", "w"), indent=2)
print("\nwrote SHIPPED_DAMAGE.csv, SHIPPED_DAMAGE_by_slot.csv")
