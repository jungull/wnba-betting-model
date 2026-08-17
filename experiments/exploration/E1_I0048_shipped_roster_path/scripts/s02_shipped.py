#!/usr/bin/env python3
"""s02 — re-execute daily_forecast.py:647-693 against the shipped log.

Fidelity gate first: a team-slot whose shipped aggregates do not reproduce
EXACTLY may back no damage number.

READ-ONLY on every production path. Writes only inside
E1_I0048_shipped_roster_path/.

SEALED PARTITION: every shipped record is 2026. This script computes COUNTS OF
ROWS AND NAMES EMITTED BY THE CODE only. No skill statistic, no outcome column,
no realised-vs-predicted comparison. Enforced by the column allowlist below.
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
WT = HERE.parent.parent.parent                       # worktree root
LIVE = Path(r"C:\Users\jgallagher\wnba-betting-model")

ET = ZoneInfo("America/New_York")
RECENCY_GAMES = 3          # daily_forecast.py:120
MINUTES_ALPHA = 0.30       # daily_forecast.py:112

TEAMS = {                  # daily_forecast.py:130-138 (transcribed, asserted below)
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV",
    "Indiana Fever": "IND", "Las Vegas Aces": "LVA",
    "Los Angeles Sparks": "LAS", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Phoenix Mercury": "PHX",
    "Portland Fire": "PDX", "Seattle Storm": "SEA",
    "Toronto Tempo": "TOR", "Washington Mystics": "WAS",
}

# ---- column allowlist. NO OUTCOME FIELD APPEARS HERE. -----------------------
ALLOW = ["game_id", "season", "game_date", "team_id", "team_abbreviation",
         "player_id", "player_name", "minutes"]
BANNED = ["pts", "fgm", "fga", "reb", "ast", "plus_minus", "appeared",
          "home_score", "away_score", "margin", "total"]


def _norm_name(s: str) -> str:                        # daily_forecast.py:606-609
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_master(root: Path) -> pd.DataFrame:
    p = pd.read_parquet(root / "data" / "masters" / "master_player.parquet")
    missing = [c for c in ALLOW if c not in p.columns]
    assert not missing, f"master_player missing allowlisted columns: {missing}"
    p = p[ALLOW].copy()
    leaked = [c for c in p.columns if c in BANNED]
    assert not leaked, f"OUTCOME COLUMN LEAKED INTO FRAME: {leaked}"
    p["game_date"] = pd.to_datetime(p.game_date)
    return p


def load_inj(root: Path) -> pd.DataFrame:
    inj = pd.read_csv(root / "data" / "injury_capture" / "injury_log.csv")
    inj["cap_dt"] = pd.to_datetime(inj.capture_utc, format="%Y%m%dT%H%M%SZ",
                                   utc=True)
    return inj


def reconstruct(p: pd.DataFrame, inj_all: pd.DataFrame, season: int,
                slate_date, cutoff, team_ab: str) -> dict | None:
    """Line-for-line re-execution of daily_forecast.py:645-759 for one team."""
    inj = inj_all[inj_all.cap_dt <= cutoff]
    if len(inj):
        inj = (inj.sort_values("cap_dt")
                  .drop_duplicates(subset=["team", "player"], keep="last"))
    abbr_to_name = {v: k for k, v in TEAMS.items()}

    ps = p[(p.season == season) & (p.game_date.dt.date < slate_date)]
    tp = ps[ps.team_abbreviation == team_ab]
    if not len(tp):
        return None
    tgames = sorted(tp.game_id.unique(),
                    key=lambda gid: tp[tp.game_id == gid].game_date.iloc[0])
    recent = set(tgames[-RECENCY_GAMES:])
    roster = tp[tp.game_id.isin(recent)].player_name.unique()

    team_inj = (inj[inj.team == abbr_to_name.get(team_ab, "?")]
                if len(inj) else pd.DataFrame())
    inj_by_norm = ({_norm_name(r.player): r for r in team_inj.itertuples()}
                   if len(team_inj) else {})
    matched = set()
    avail, outs = [], []
    for name in sorted(roster):
        hist = (tp[(tp.player_name == name) & (tp.minutes.notna())
                   & (tp.minutes > 0)].sort_values(["game_date", "game_id"]))
        rec = {"player": name, "games_played": int(len(hist)),
               "min_ewma": (float(hist.minutes.ewm(alpha=MINUTES_ALPHA,
                                                   adjust=True).mean().iloc[-1])
                            if len(hist) else None),
               "cold_start": len(hist) == 0, "designation": None}
        hit = inj_by_norm.get(_norm_name(name))
        if hit is not None:
            matched.add(_norm_name(name))
            rec["designation"] = hit.status
        (outs if rec["designation"] == "Out" else avail).append(rec)

    ew = [a["min_ewma"] for a in avail if a["min_ewma"] is not None]
    unmatched = [inj_by_norm[n].player for n in inj_by_norm if n not in matched]
    return {"roster": list(roster), "avail": avail, "out": outs,
            "n_roster": len(roster), "n_out": len(outs),
            "n_cold_start": sum(1 for a in avail if a["cold_start"]),
            "sum_min_ewma_available": float(np.nansum(ew)) if ew else None,
            "vacated_min_ewma": float(np.nansum(
                [o["min_ewma"] for o in outs if o["min_ewma"] is not None])),
            "unmatched_injury_players": unmatched,
            "tp": tp, "recent": recent, "ps": ps}


def run(root: Path, label: str) -> tuple[pd.DataFrame, dict]:
    log = root / "forecasts" / "forecast_log.jsonl"
    recs = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    p = load_master(root)
    inj_all = load_inj(root)
    print(f"\n### {label}: {len(recs)} shipped records | master rows {len(p)} "
          f"| injury rows {len(inj_all)}")

    slots, dmg = [], []
    n_no_player_layer = 0
    for r in recs:
        core = r["core_only_prediction"]
        if "player_layer_informational" not in core:
            # skipped-game records (no_forecast_reason) carry no player layer
            n_no_player_layer += 1
            continue
        pl = core["player_layer_informational"]
        cutoff = datetime.fromisoformat(r["forecast_cutoff"])
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        slate_date = cutoff.astimezone(ET).date()      # daily_forecast.py:902-903
        season = slate_date.year                       # :904
        for side in ("home", "away"):
            ab = core[f"{side}_team"]
            shipped = pl[side]
            got = reconstruct(p, inj_all, season, slate_date, cutoff, ab)
            row = {"log": label, "record_idx": r["record_idx"],
                   "game_id": r["game_id"], "label": r["decision_time_label"],
                   "slate_date": str(slate_date), "side": side, "team": ab,
                   "shipped_n_roster": shipped["n_roster"],
                   "shipped_n_out": shipped["n_out"],
                   "shipped_sum_ewma": shipped["sum_min_ewma_available"],
                   "shipped_vacated": shipped["vacated_min_ewma"],
                   "shipped_out_names": "|".join(sorted(pl[f"out_{side}"]))}
            if got is None:
                row.update({"reproduced": False, "why": "no season rows"})
                slots.append(row); continue
            ok_r = got["n_roster"] == shipped["n_roster"]
            ok_o = got["n_out"] == shipped["n_out"]
            ok_n = (sorted(o["player"] for o in got["out"])
                    == sorted(pl[f"out_{side}"]))
            se, ss = got["sum_min_ewma_available"], shipped["sum_min_ewma_available"]
            ok_e = (se is None and ss is None) or (
                se is not None and ss is not None and abs(se - ss) <= 1e-9)
            ok_v = abs(got["vacated_min_ewma"] - shipped["vacated_min_ewma"]) <= 1e-9
            repro = all([ok_r, ok_o, ok_n, ok_e, ok_v])
            row.update({"reproduced": repro, "mine_n_roster": got["n_roster"],
                        "mine_n_out": got["n_out"],
                        "mine_sum_ewma": se, "mine_vacated": got["vacated_min_ewma"],
                        "ok_n_roster": ok_r, "ok_n_out": ok_o, "ok_out_names": ok_n,
                        "ok_sum_ewma": ok_e, "ok_vacated": ok_v,
                        "mine_out_names": "|".join(sorted(o["player"] for o in got["out"])),
                        "mine_roster": "|".join(sorted(got["roster"])),
                        "unmatched_injury": "|".join(sorted(got["unmatched_injury_players"])),
                        "why": "" if repro else "aggregate mismatch"})
            slots.append(row)
            if repro:
                dmg.append((row, got, p, season, slate_date))
    print(f"  records carrying a player layer: {len(recs) - n_no_player_layer}"
          f" / {len(recs)}  (skipped-game records without one: {n_no_player_layer})")
    S = pd.DataFrame(slots)
    return S, {"records": recs, "dmg": dmg, "master": p,
               "n_no_player_layer": n_no_player_layer}


# --------------------------------------------------------------- fidelity
print("=" * 78)
print("s02 — FIDELITY GATE then damage. SEALED PARTITION: descriptive counts only.")
print("=" * 78)
print(f"column allowlist resolved: {ALLOW}")
print(f"banned (outcome) columns asserted absent: {BANNED}")

S_live, ctx_live = run(LIVE, "LIVE_main_worktree")
S_wt, ctx_wt = run(WT, "worktree_copy")

S = pd.concat([S_live, S_wt], ignore_index=True)
S.to_csv(HERE / "FIDELITY.csv", index=False)
for lab, sub in S.groupby("log"):
    print(f"\n  {lab}: reproduced {int(sub.reproduced.sum())} / {len(sub)} team-slots")
    bad = sub[~sub.reproduced]
    if len(bad):
        print(bad[["record_idx", "team", "slate_date", "shipped_n_roster",
                   "mine_n_roster", "shipped_n_out", "mine_n_out", "why"]]
              .to_string(index=False))

json.dump({"fidelity": {k: {"n": int(len(v)), "reproduced": int(v.reproduced.sum())}
                        for k, v in S.groupby("log")}},
          open(HERE / "_s02_fidelity.json", "w"), indent=2)
print("\nwrote FIDELITY.csv")
