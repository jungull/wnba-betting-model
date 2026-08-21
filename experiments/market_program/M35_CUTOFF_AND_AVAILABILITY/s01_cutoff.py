"""s01_cutoff.py -- can the cutoff move, and does that make the injury tape legible?

E0-STYLE DIAGNOSTIC, NON-CLAIMING.

M34 reported that at the contract cutoff the injury tape is visible on 0.0% of rows. That was
computed against the DATE-ONLY policy applied to every row, because M34 could not reach the
contract (its outcome snapshot ends 2026-07-31, before the injury capture begins) and used the
documented fallback for all of them.

The contract does not apply one policy to every row. It applies two:

    date_only_prior_day_cutoff   32,243 rows (71.9%)   18:00 UTC the day before
    exact_tip_T-90m              12,608 rows (28.1%)   90 minutes before tip, ON GAME DAY

So M34's 0.0% is right for the 72% and wrong as a blanket statement, and this file says so.

WHAT DECIDES WHICH POLICY A GAME GETS. `resolve_tip_times` (prediction_contract_v2) admits a
tip time only from an observation recorded strictly before that observation's OWN reported tip
minus 90 minutes -- point-in-time, fail-closed. Its only sources today are `odds_extension`
(12,550 rows) and `props_historical` (58). Every other game falls back to date-only NOT because
a later cutoff is disallowed, but because no qualifying tip observation exists.

THE OBSERVATION THIS FILE TESTS. The injury capture records `game_time_et` alongside
`retrieval_ts_utc`. That is exactly the shape `resolve_tip_times` wants: a reported tip and the
instant we held it. If those captures qualify, the injury tape does not merely become readable
-- it is itself the evidence that makes a later cutoff legal.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

INJ = (r"C:\Users\jgallagher\wnba-betting-model\data\injury_official_live"
       r"\injury_snapshots.csv")
MASTER = r"C:\Users\jgallagher\wnba-betting-model\data\masters\master_player.parquet"
T90 = pd.Timedelta(minutes=90)


def load():
    inj = pd.read_csv(INJ)
    inj = inj[inj["player_id"].notna()].copy()
    inj["player_id"] = inj["player_id"].astype("int64")
    inj["gd"] = pd.to_datetime(inj["game_date"], errors="coerce").dt.date
    inj["ret"] = pd.to_datetime(inj["retrieval_ts_utc"], utc=True, errors="coerce")
    hh = inj["game_time_et"].astype(str).str.extract(r"(\d{2}):(\d{2})")
    # ET evening game -> UTC. August is EDT (UTC-4); the archive is one August window.
    inj["tip"] = (pd.to_datetime(inj["gd"].astype(str), utc=True)
                  + pd.to_timedelta(hh[0].astype(float) + 12, unit="h")
                  + pd.to_timedelta(hh[1].astype(float), unit="m")
                  + pd.Timedelta(hours=4))
    inj = inj[inj["ret"].notna() & inj["tip"].notna() & inj["gd"].notna()].copy()
    mp = pd.read_parquet(MASTER)
    dc = [c for c in mp.columns if c.lower() == "game_date"][0]
    mp["gd"] = pd.to_datetime(mp[dc]).dt.date
    mp["appeared"] = (mp["minutes"].fillna(0) > 0).astype(int)
    return inj, mp[["game_id", "player_id", "team_id", "minutes", "gd", "appeared"]]


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    inj, mp = load()
    out = {}

    print("=" * 94)
    print("M35 s01 -- can the cutoff move, and does the injury tape then become legible?")
    print("=" * 94)

    # ---- 1. would injury captures QUALIFY as tip-time observations? ------------------
    inj["qualifies"] = inj["ret"] < (inj["tip"] - T90)
    per_match = inj.groupby(["gd", "matchup"]).agg(
        any_qual=("qualifies", "any"), first_ret=("ret", "min"), tip=("tip", "first"))
    per_match["lead_h"] = (per_match["tip"] - per_match["first_ret"]).dt.total_seconds() / 3600
    print("\n1. DO INJURY CAPTURES QUALIFY AS POINT-IN-TIME TIP OBSERVATIONS?")
    print("   (rule: an observation counts only if retrieved before its own reported tip - 90m)")
    print("   matchup-dates in the tape        : %d" % len(per_match))
    print("   with a QUALIFYING observation    : %d (%.1f%%)"
          % (per_match["any_qual"].sum(), 100 * per_match["any_qual"].mean()))
    print("   median lead of first capture     : %.2f hours before tip"
          % per_match["lead_h"].median())
    out["tip_observation"] = {"n_matchup_dates": int(len(per_match)),
                              "n_qualifying": int(per_match["any_qual"].sum()),
                              "median_lead_hours": float(per_match["lead_h"].median())}

    # ---- 2. under a T-90m cutoff, how much status is legally visible? -----------------
    dates = sorted(set(mp["gd"]) & set(inj["gd"]))
    d = mp[mp["gd"].isin(dates)].copy()
    tip_of = inj.groupby(["player_id", "gd"])["tip"].min()
    d["tip"] = list(tip_of.reindex(list(zip(d["player_id"], d["gd"]))).to_numpy())
    d["tip"] = pd.to_datetime(d["tip"], utc=True)

    print("\n2. STATUS VISIBLE UNDER EACH CUTOFF POLICY, on %d player-game rows" % len(d))
    cov = {}
    for tag, cut in (("date_only (18:00 UTC day before)",
                      pd.to_datetime(d["gd"].astype(str), utc=True) - pd.Timedelta(hours=6)),
                     ("exact_tip_T-90m", d["tip"] - T90)):
        c = pd.Series(cut).reset_index(drop=True)
        vis = []
        j = inj.set_index(["player_id", "gd"]).sort_values("ret")
        for pid, gd, cu in zip(d["player_id"], d["gd"], c):
            if pd.isna(cu):
                vis.append(None)
                continue
            try:
                g = j.loc[(pid, gd)]
            except KeyError:
                vis.append(None)
                continue
            g = g.to_frame().T if isinstance(g, pd.Series) else g
            ok = g[g["ret"] < cu]
            vis.append(ok["status"].iloc[-1] if len(ok) else None)
        d["st_" + tag[:9]] = vis
        frac = float(pd.Series(vis).notna().mean())
        cov[tag] = frac
        print("   %-34s status on %5.1f%% of rows" % (tag, frac * 100))
    out["coverage"] = cov

    # ---- 3. what that status is worth for AVAILABILITY at the later cutoff ------------
    col = [c for c in d.columns if c.startswith("st_exact")][0]
    print("\n3. AVAILABILITY under the T-90m cutoff (the legible one)")
    print("   %-16s %6s %10s" % ("status", "n", "appeared"))
    ap = {}
    for s, g in d.groupby(d[col].fillna("(not listed)")):
        ap[s] = {"n": int(len(g)), "rate": float(g["appeared"].mean())}
        print("   %-16s %6d %9.1f%%" % (s, len(g), 100 * g["appeared"].mean()))
    out["availability_at_T90"] = ap

    base = float(d["appeared"].mean())
    known = d[col].notna()
    print("\n   base appearance rate, all rows      : %.4f" % base)
    print("   rows with a status at T-90m         : %d (%.1f%%)" % (known.sum(),
                                                                    100 * known.mean()))
    if known.any():
        pred = np.where(d[col].eq("Out"), 0.0, np.where(known, 0.95, base))
        brier_base = float(np.mean((base - d["appeared"]) ** 2))
        brier_inj = float(np.mean((pred - d["appeared"]) ** 2))
        out["brier"] = {"base_rate_only": brier_base, "with_injury_status": brier_inj,
                        "improvement_pct": (brier_base - brier_inj) / brier_base * 100}
        print("   Brier, base rate only               : %.5f" % brier_base)
        print("   Brier, using status at T-90m        : %.5f  (%+.1f%%)"
              % (brier_inj, (brier_base - brier_inj) / brier_base * 100))

    json.dump(out, open("FINDINGS_cutoff.json", "w", encoding="utf-8", newline="\n"),
              indent=1, default=str)
    print("\nwrote FINDINGS_cutoff.json")


if __name__ == "__main__":
    main()
