"""s03_beats_consensus.py -- does a dislocated price actually beat the hold?

POST-HOC / EXPLORATORY, like s02. Not confirmatory. See DEFECTS.md.

s02 established that when a book disagrees with its peers, the BOOK is what moves: the gap
shrinks 0.49pp of an initial 1.95pp per horizon, essentially all of it contributed by the
outlier, with no detectable movement of consensus toward it. That makes the peer consensus
the right anchor. It does NOT make the dislocation profitable, because reverting to
consensus and beating the price you had to pay are different questions.

This asks the second one, in the only form that means anything:

    You bet side S at book b, paying its VIGGED implied probability p_raw.
    The other books' de-vigged median says S is worth cons.
    Expected return per unit staked = cons / p_raw - 1, positive only if cons > p_raw.

That is the standard beat-the-no-vig-consensus test, and it is deliberately harsh on us: it
charges the full vig of the book actually being bet, and it credits no forecasting skill of
our own -- the edge, if any, comes entirely from one book being out of line with the others.

Also runs the replication on the 2025 `hist_` family, which PREREG.md reserved and which has
not been consulted until now.

NO GAME OUTCOME IS READ ANYWHERE IN THIS FILE.
"""
from __future__ import annotations

import json
import random
import statistics as st
from collections import defaultdict
import panel
import s01_leadership as s01


def price_observations(rows):
    """Every pre-game quote, with the leave-one-out consensus for its own side."""
    out = []
    for (gid, market, side), by_t in panel.keyed(rows).items():
        for t, books in by_t.items():
            dt = s01._dt(t)
            commence = s01._dt(next(iter(books.values())).commence)
            if dt is None or commence is None or dt >= commence:
                continue
            for bk, r in books.items():
                cons = panel.consensus_excluding(books, bk)
                if cons is None or r.p_raw <= 0:
                    continue
                out.append({
                    "game": gid, "market": market, "side": side, "book": bk,
                    "p_raw": r.p_raw, "p_devig": r.p_devig, "cons": cons,
                    "overround": r.p_raw / r.p_devig,
                    "gap_devig": r.p_devig - cons,          # opinion gap, vig removed
                    "edge": cons / r.p_raw - 1.0,           # what you would actually earn
                })
    return out


def boot(obs, fn, seed=s01.SEED, draws=s01.DRAWS):
    """Cluster bootstrap of a mean, resampling GAMES.

    Identical in distribution to pooling the resampled observations and taking their mean,
    but it collapses each game to (sum, count) first, so a draw costs O(games) instead of
    O(quotes). At 60k quotes the naive form takes about half an hour per statistic; this
    takes milliseconds and is the same estimator.
    """
    sums = defaultdict(float)
    cnts = defaultdict(int)
    total = 0.0
    for o in obs:
        v = fn(o)
        sums[o["game"]] += v
        cnts[o["game"]] += 1
        total += v
    games = list(sums)
    gs = [sums[g] for g in games]
    gc = [cnts[g] for g in games]
    k = len(games)
    rng = random.Random(seed)
    vals = []
    for _ in range(draws):
        s = 0.0
        n = 0
        for _ in range(k):
            i = rng.randrange(k)
            s += gs[i]
            n += gc[i]
        if n:
            vals.append(s / n)
    vals.sort()
    return total / len(obs), vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))]


def report(label, obs, fn=lambda o: o["edge"], pct=True):
    if not obs:
        print("  %-44s NO OBSERVATIONS" % label)
        return None
    m, lo, hi = boot(obs, fn)
    k = 100.0 if pct else 1.0
    star = "  *" if (lo > 0 or hi < 0) else ""
    print("  %-44s n=%7d  %+7.3f%s [%+.3f,%+.3f]%s"
          % (label, len(obs), m * k, "%" if pct else "", lo * k, hi * k, star))
    return {"label": label, "n": len(obs), "mean": round(m, 6),
            "ci95": [round(lo, 6), round(hi, 6)], "excludes_zero": bool(lo > 0 or hi < 0)}


def run(family, out):
    rows = panel.load_rows(family, as_of=s01.AS_OF)
    obs = price_observations(rows)
    if not obs:
        print("  no observations for family=%s" % family)
        return
    n_pos = sum(1 for o in obs if o["edge"] > 0)
    print("  quotes: %d over %d games, %d books"
          % (len(obs), len({o["game"] for o in obs}), len({o["book"] for o in obs})))
    print("  mean overround per book/market: %.3f%%"
          % ((st.mean(o["overround"] for o in obs) - 1) * 100))
    print("  quotes that BEAT the de-vigged consensus of their peers: %d (%.2f%%)"
          % (n_pos, 100 * n_pos / len(obs)))
    print()
    res = {"n": len(obs), "frac_beating_consensus": round(n_pos / len(obs), 5),
           "mean_overround": round(st.mean(o["overround"] for o in obs) - 1, 5)}
    print("  EXPECTED RETURN PER UNIT STAKED (cons / vigged price - 1)")
    res["all"] = report("every pre-game quote", obs)
    res["positive_only"] = report("only quotes that beat consensus", [o for o in obs if o["edge"] > 0])
    for thr in (0.010, 0.015, 0.020, 0.030):
        sub = [o for o in obs if o["gap_devig"] <= -thr]   # book is GENEROUS on this side
        res["gap_%.3f" % thr] = report(
            "book is generous by >= %.1fpp of opinion" % (thr * 100), sub)
    print()
    print("  BY MARKET (all quotes)")
    for mk in ("h2h", "spreads", "totals"):
        res["market_" + mk] = report("  " + mk, [o for o in obs if o["market"] == mk])
    print()
    print("  BEST-OF-BOOK: for each side, only the single most generous quote available")
    best = {}
    for o in obs:
        k = (o["game"], o["market"], o["side"])
        if k not in best or o["edge"] > best[k]["edge"]:
            best[k] = o
    res["best_of_book"] = report("best price on each side", list(best.values()))
    out[family] = res


def main():
    out = {"_status": "POST-HOC / EXPLORATORY. Not confirmatory. See DEFECTS.md.",
           "as_of": s01.AS_OF,
           "prereg_sha256": open("PREREG.sha256").read().split()[0]}
    print("=" * 96)
    print("M29 s03 -- does beating the peer consensus survive the vig you pay to do it?")
    print("=" * 96)
    print()
    print("LIVE FAMILY (2026 tape)")
    print("-" * 96)
    run("live", out)
    print()
    print("REPLICATION -- hist FAMILY (2025 tape), reserved by PREREG.md and untouched until now")
    print("-" * 96)
    run("hist", out)
    with open("FINDINGS_s03.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
    print()
    print("wrote FINDINGS_s03.json")


if __name__ == "__main__":
    main()
