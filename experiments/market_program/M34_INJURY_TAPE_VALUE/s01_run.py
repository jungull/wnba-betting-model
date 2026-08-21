"""s01_run.py -- implements PREREG.md 0fcdb68a2db87707a2ed6b36fca8fd4e22adf929a2a7410419fee1fe5804c3db

Ten game dates. This is a feasibility measurement, not evidence, and says so throughout.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

MASTER = r"C:\Users\jgallagher\wnba-betting-model\data\masters\master_player.parquet"
INJ = (r"C:\Users\jgallagher\wnba-betting-model\data\injury_official_live"
       r"\injury_snapshots.csv")
SEED, DRAWS = 20260821, 2000
STATUSES = ["Out", "Doubtful", "Questionable", "Probable", "Available"]


def load():
    mp = pd.read_parquet(MASTER)
    dc = [c for c in mp.columns if c.lower() == "game_date"][0]
    mp["gd_ts"] = pd.to_datetime(mp[dc])
    mp["gd"] = mp["gd_ts"].dt.date
    mp = mp[["game_id", "player_id", "team_id", "season", "minutes", "gd", "gd_ts"]].copy()
    mp["appeared"] = (mp["minutes"].fillna(0) > 0).astype(int)

    inj = pd.read_csv(INJ)
    inj = inj[inj["player_id"].notna()].copy()
    inj["player_id"] = inj["player_id"].astype("int64")
    inj["gd"] = pd.to_datetime(inj["game_date"], errors="coerce").dt.date
    inj["ret"] = pd.to_datetime(inj["retrieval_ts_utc"], utc=True, errors="coerce")
    # scheduled tip, ET -> UTC (ET is UTC-4 in August; the archive is a single August window)
    hhmm = inj["game_time_et"].astype(str).str.extract(r"(\d{2}):(\d{2})")
    inj["tip_utc"] = (pd.to_datetime(inj["gd"].astype(str), utc=True)
                      + pd.to_timedelta(hhmm[0].astype(float) + 12, unit="h")
                      + pd.to_timedelta(hhmm[1].astype(float), unit="m")
                      + pd.Timedelta(hours=4))
    inj = inj[inj["ret"].notna() & inj["gd"].notna()].copy()
    return mp, inj


def pit_status(inj: pd.DataFrame, cutoff_col: str) -> pd.DataFrame:
    """Last status strictly BEFORE the cutoff. Nothing at or after it may be read."""
    ok = inj[inj["ret"] < inj[cutoff_col]].copy()
    ok = ok.sort_values("ret").drop_duplicates(["player_id", "gd"], keep="last")
    return ok[["player_id", "gd", "status"]].rename(columns={"status": "st"})


def build():
    mp, inj = load()
    dates = sorted(set(mp["gd"]) & set(inj["gd"]))
    d = mp[mp["gd"].isin(dates)].copy()

    # CUTOFF_A: 18:00 UTC the day before the game -- the contract's own convention
    inj["cut_a"] = pd.to_datetime(inj["gd"].astype(str), utc=True) - pd.Timedelta(hours=6)
    inj["cut_b"] = inj["tip_utc"]

    for tag, col in (("A", "cut_a"), ("B", "cut_b")):
        d = d.merge(pit_status(inj, col).rename(columns={"st": "st_" + tag}),
                    on=["player_id", "gd"], how="left")

    # BASE: EWMA(half-life 2) of the player's own prior PLAYED minutes, strictly prior
    full = mp.sort_values(["player_id", "gd_ts"]).copy()
    full["_m"] = full["minutes"].where(full["appeared"] == 1)
    full["base"] = full.groupby("player_id", sort=False)["_m"].transform(
        lambda s: s.ewm(halflife=2.0, adjust=True, ignore_na=True).mean().shift(1))
    d = d.merge(full[["game_id", "player_id", "base"]], on=["game_id", "player_id"], how="left")
    return d, dates


def boot(err, clusters, rng):
    g = pd.DataFrame({"e": np.abs(err), "c": clusters}).groupby("c")["e"]
    s, n = g.sum().to_numpy(), g.count().to_numpy()
    k = len(s)
    acc = np.empty(DRAWS)
    for b in range(DRAWS):
        i = rng.integers(0, k, k)
        acc[b] = s[i].sum() / n[i].sum()
    acc.sort()
    return float(np.mean(np.abs(err))), float(acc[int(.025 * DRAWS)]), float(acc[int(.975 * DRAWS)])


def walk_forward_offsets(sub: pd.DataFrame, col: str) -> np.ndarray:
    """Per-status additive offset fitted on STRICTLY EARLIER game dates only."""
    out = np.zeros(len(sub))
    dates = sorted(sub["gd"].unique())
    idx = {d: i for i, d in enumerate(dates)}
    resid = sub["minutes"].to_numpy(float) - sub["base"].to_numpy(float)
    st = sub[col].fillna("(none)").to_numpy()
    gd = sub["gd"].to_numpy()
    for i in range(len(sub)):
        prior = np.array([idx[g] < idx[gd[i]] for g in gd])
        m = prior & (st == st[i])
        out[i] = float(np.mean(resid[m])) if m.sum() >= 5 else np.nan
    return out


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    rng = np.random.default_rng(SEED)
    d, dates = build()
    out = {"prereg_sha256": open("PREREG.sha256").read().split()[0],
           "n_rows": int(len(d)), "n_dates": len(dates),
           "n_players": int(d["player_id"].nunique()), "n_games": int(d["game_id"].nunique())}

    print("=" * 92)
    print("M34 -- what is the injury tape worth? TEN GAME DATES. Feasibility, not evidence.")
    print("=" * 92)
    print("%d player-game rows | %d dates | %d games | %d players\n"
          % (len(d), len(dates), d["game_id"].nunique(), d["player_id"].nunique()))

    print("POINT-IN-TIME COVERAGE -- how much of the tape each cutoff can legally see")
    for tag in ("A", "B"):
        c = d["st_" + tag].notna().mean()
        print("  CUTOFF_%s  status available on %5.1f%% of rows" % (tag, c * 100))
        out["coverage_" + tag] = float(c)

    print("\nP1 -- does the status predict APPEARANCE at all? (a different question; E1_I0062)")
    ap = {}
    for tag in ("A", "B"):
        print("  CUTOFF_%s" % tag)
        for s in STATUSES + ["(none)"]:
            m = d["st_" + tag].fillna("(none)") == s
            if m.sum() == 0:
                continue
            r = float(d.loc[m, "appeared"].mean())
            ap["%s_%s" % (tag, s)] = {"n": int(m.sum()), "appearance_rate": r}
            print("    %-14s n=%4d  appeared %5.1f%%" % (s, int(m.sum()), r * 100))
    out["appearance_by_status"] = ap

    print("\nMINUTES, on rows where the player APPEARED")
    played = d[(d["appeared"] == 1) & d["base"].notna() & d["minutes"].notna()].copy()
    print("  scored rows: %d over %d dates" % (len(played), played["gd"].nunique()))
    res = {}
    b, lo, hi = boot(played["base"] - played["minutes"], played["gd"], rng)
    res["BASE"] = {"n": int(len(played)), "mae": b, "ci95": [lo, hi]}
    print("  %-28s MAE %7.4f  [%7.4f, %7.4f]" % ("BASE  EWMA(hl=2)", b, lo, hi))

    for tag in ("A", "B"):
        off = walk_forward_offsets(played, "st_" + tag)
        use = ~np.isnan(off)
        adj = played["base"].to_numpy(float) + np.where(use, np.nan_to_num(off), 0.0)
        m, l2, h2 = boot(adj - played["minutes"].to_numpy(float), played["gd"], rng)
        res["BASE+" + tag] = {"mae": m, "ci95": [l2, h2],
                              "n_rows_with_offset": int(use.sum()),
                              "delta_vs_base": b - m}
        print("  %-28s MAE %7.4f  [%7.4f, %7.4f]   delta %+7.4f   (offset on %d rows)"
              % ("BASE+" + tag + ("  contract-legal" if tag == "A" else "  latest pre-tip"),
                 m, l2, h2, b - m, int(use.sum())))
    out["minutes"] = res

    print("\nPREDICTIONS")
    out_rate = ap.get("B_Out", ap.get("A_Out", {})).get("appearance_rate", float("nan"))
    p1 = bool(np.isfinite(out_rate) and out_rate < 0.10)
    dB = res["BASE+B"]["delta_vs_base"]
    dA = res["BASE+A"]["delta_vs_base"]
    p2 = bool(dB > 0)
    p3 = bool(dA < 0.5 * dB) if dB > 0 else None
    p4 = not any(r.get("ci95") and (r["ci95"][0] > res["BASE"]["mae"]
                                    or r["ci95"][1] < res["BASE"]["mae"])
                 for k, r in res.items() if k != "BASE")
    for nm, ok, txt in (("P1", p1, "Out is near-deterministic for non-appearance (<10%)"),
                        ("P2", p2, "latest-pre-tip status improves the minutes forecast"),
                        ("P3", p3, "the contract-legal version gets less than half of that"),
                        ("P4", p4, "no interval separates from base -- 10 dates cannot settle it")):
        print("  %s %-5s %s" % (nm, "n/a" if ok is None else ("PASS" if ok else "FAIL"), txt))
    out["predictions"] = {"P1": p1, "P2": p2, "P3": p3, "P4": bool(p4)}
    out["out_appearance_rate"] = float(out_rate)

    json.dump(out, open("FINDINGS.json", "w", encoding="utf-8", newline="\n"),
              indent=1, default=float)
    print("\nwrote FINDINGS.json")


if __name__ == "__main__":
    main()
