"""s01_leadership.py -- who moves when a book disagrees with its peers?

Implements PREREG.md exactly. Nothing here was chosen after seeing a number: the primary
threshold (0.015), the horizon (20-90 min), the statistic (median book_share minus median
cons_share) and the bootstrap (cluster by game, 2000 draws, seed 20260819) were all frozen
first and hashed to 895d004fceaf3c3f64bc0d2f04e581520c284925d2af089672b8e5f2d0371f87.

NO GAME OUTCOME IS READ ANYWHERE IN THIS FILE.
"""
from __future__ import annotations

import json
import random
import statistics as st
from collections import defaultdict
from datetime import datetime

import panel

AS_OF = "2026-08-19T23:05:00Z"   # tape pin; the capture job keeps running
SEED = 20260819
DRAWS = 2000
PRIMARY = 0.015
SENSITIVITY = [0.010, 0.015, 0.020, 0.030]
H_MIN, H_MAX = 20.0, 90.0


def _dt(s):
    if not s:
        return None
    try:
        return datetime.strptime(s.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def observations(rows):
    """One record per (series, book, consecutive capture pair) that clears the gates."""
    obs = []
    for (gid, market, side), by_t in panel.keyed(rows).items():
        times = sorted(by_t)
        for t0, t1 in zip(times, times[1:]):
            d0, d1 = _dt(t0), _dt(t1)
            if d0 is None or d1 is None:
                continue
            mins = (d1 - d0).total_seconds() / 60.0
            if not (H_MIN <= mins <= H_MAX):
                continue
            b0, b1 = by_t[t0], by_t[t1]
            commence = _dt(next(iter(b0.values())).commence)
            if commence is None or d1 >= commence:
                continue                    # pre-game only; in-play is a different process
            for book in set(b0) & set(b1):
                c0 = panel.consensus_excluding(b0, book)
                c1 = panel.consensus_excluding(b1, book)
                if c0 is None or c1 is None:
                    continue
                gap0 = b0[book].p_devig - c0
                if gap0 == 0:
                    continue
                s = 1.0 if gap0 > 0 else -1.0
                d_book = b1[book].p_devig - b0[book].p_devig
                d_cons = c1 - c0
                obs.append({
                    "game": gid, "market": market, "side": side, "book": book,
                    "mins": mins, "gap0": gap0, "abs_gap0": abs(gap0),
                    "gap1": b1[book].p_devig - c1,
                    "book_share": -s * d_book / abs(gap0),
                    "cons_share": s * d_cons / abs(gap0),
                    "book_updated": b1[book].last_update != b0[book].last_update,
                })
    return obs


def cluster_bootstrap(obs, key, seed=SEED, draws=DRAWS):
    """Resample GAMES, not observations -- every quote on a game moves together."""
    by_game = defaultdict(list)
    for o in obs:
        by_game[o["game"]].append(o[key])
    games = list(by_game)
    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        pool = []
        for _ in range(len(games)):
            pool.extend(by_game[rng.choice(games)])
        if pool:
            out.append(st.median(pool))
    out.sort()
    return out[int(0.025 * len(out))], out[int(0.975 * len(out))]


def diff_bootstrap(obs, seed=SEED, draws=DRAWS):
    by_game = defaultdict(list)
    for o in obs:
        by_game[o["game"]].append(o)
    games = list(by_game)
    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        pool = []
        for _ in range(len(games)):
            pool.extend(by_game[rng.choice(games)])
        if pool:
            out.append(st.median([x["book_share"] for x in pool])
                       - st.median([x["cons_share"] for x in pool]))
    out.sort()
    return out[int(0.025 * len(out))], out[int(0.975 * len(out))]


def summarise(obs, label):
    if not obs:
        print("  %-34s NO OBSERVATIONS" % label)
        return None
    bs = [o["book_share"] for o in obs]
    cs = [o["cons_share"] for o in obs]
    closure = [o["book_share"] + o["cons_share"] for o in obs]
    lo, hi = diff_bootstrap(obs)
    r = {
        "label": label, "n": len(obs), "n_games": len({o["game"] for o in obs}),
        "median_book_share": round(st.median(bs), 4),
        "median_cons_share": round(st.median(cs), 4),
        "median_closure": round(st.median(closure), 4),
        "diff_median": round(st.median(bs) - st.median(cs), 4),
        "diff_ci95": [round(lo, 4), round(hi, 4)],
        "excludes_zero": bool(lo > 0 or hi < 0),
        "median_abs_gap0_pp": round(st.median([o["abs_gap0"] for o in obs]) * 100, 3),
        "median_abs_gap1_pp": round(st.median([abs(o["gap1"]) for o in obs]) * 100, 3),
    }
    print("  %-34s n=%6d games=%3d  book %+.3f  cons %+.3f  diff %+.3f [%+.3f,%+.3f]%s"
          % (label, r["n"], r["n_games"], r["median_book_share"], r["median_cons_share"],
             r["diff_median"], lo, hi, "  *" if r["excludes_zero"] else ""))
    return r


def main():
    rows = panel.load_rows("live", as_of=AS_OF)
    obs = observations(rows)
    print("=" * 92)
    print("M29 PRICE LEADERSHIP -- live tape, market prices only, no game outcome read")
    print("=" * 92)
    print("qualifying observations: %d over %d games, %d books"
          % (len(obs), len({o["game"] for o in obs}), len({o["book"] for o in obs})))
    stale = sum(1 for o in obs if not o["book_updated"])
    print("book quote UNCHANGED between the two captures: %d (%.1f%%)"
          "   <-- the staleness confound, measured"
          % (stale, stale / max(len(obs), 1) * 100))
    print()

    out = {"as_of": AS_OF,
           "prereg_sha256": open("PREREG.sha256").read().split()[0],
           "n_raw_observations": len(obs),
           "stale_fraction": round(stale / max(len(obs), 1), 4),
           "primary": None, "sensitivity": [], "updated_only": None,
           "stale_only": None, "by_book": []}

    print("SENSITIVITY LADDER (all thresholds prespecified; 0.015 is the primary)")
    for thr in SENSITIVITY:
        sub = [o for o in obs if o["abs_gap0"] >= thr]
        r = summarise(sub, "|gap| >= %.3f%s" % (thr, "  [PRIMARY]" if thr == PRIMARY else ""))
        if r:
            r["threshold"] = thr
            out["sensitivity"].append(r)
            if thr == PRIMARY:
                out["primary"] = r

    print()
    print("THE STALENESS CONFOUND -- primary threshold, split by whether the book requoted")
    prim = [o for o in obs if o["abs_gap0"] >= PRIMARY]
    out["updated_only"] = summarise([o for o in prim if o["book_updated"]], "book DID requote")
    out["stale_only"] = summarise([o for o in prim if not o["book_updated"]],
                                  "book did NOT requote")

    print()
    print("P4 -- does any book actually LEAD? (higher cons_share = peers move toward it)")
    by_book = defaultdict(list)
    for o in prim:
        by_book[o["book"]].append(o)
    rank = []
    for bk, os_ in sorted(by_book.items()):
        if len(os_) < 30:
            continue
        lo, hi = cluster_bootstrap(os_, "cons_share")
        rank.append({"book": bk, "n": len(os_),
                     "median_cons_share": round(st.median([o["cons_share"] for o in os_]), 4),
                     "median_book_share": round(st.median([o["book_share"] for o in os_]), 4),
                     "cons_ci95": [round(lo, 4), round(hi, 4)]})
    for r in sorted(rank, key=lambda x: -x["median_cons_share"]):
        print("  %-16s n=%5d  cons_share %+.3f [%+.3f,%+.3f]   book_share %+.3f"
              % (r["book"], r["n"], r["median_cons_share"],
                 r["cons_ci95"][0], r["cons_ci95"][1], r["median_book_share"]))
    out["by_book"] = rank

    with open("FINDINGS.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
    print()
    print("wrote FINDINGS.json")
    return out


if __name__ == "__main__":
    main()
