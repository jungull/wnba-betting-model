# -*- coding: utf-8 -*-
"""M08 -- how long does a stale line stay stale, and can this cadence even tell?

PROSPECTIVE MEASUREMENT. A stale window exists only where a fresher cross-book quote was
demonstrably capturable at time T; without that, staleness is an artifact of the observer's
own cadence.

Implements PREREG.md, whose sha256 is verified before anything is computed. The gate is
checked BEFORE the primary statistic exists in memory, not after -- a gate applied to an
already-computed number is not a gate.

Two things are produced:

  1. THE RESOLUTION-FLOOR ANALYSIS, always. It answers the node's own acceptance criterion
     "distinguishes book-is-slow from we-polled-slowly explicitly", and it is a statement
     about the OBSERVER, so it needs no sample gate. If most episodes sit at the floor, this
     cadence cannot measure stale windows at all and that IS the finding.

  2. THE PRIMARY (Kaplan-Meier median lifetime over resolvable episodes), only if the
     preregistered gate is met.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from collections import defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "M30_PRICE_LEADERSHIP")))

import panel  # noqa: E402

FAST_ERA_FROM = "2026-08-19T14:00:00Z"   # the cadence change; identical to M31
THRESH = 0.02                            # frozen in PREREG.md, never tuned here
MAX_GAP_MIN = 12.0                       # an episode straddling a bigger gap is unobservable
SEED = 20260822
DRAWS = 2000

GATE_GAMES = 30
GATE_EPISODES = 150
GATE_RESOLVABLE = 60


def _dt(s):
    return datetime.strptime(s.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")


def verify_prereg():
    p = os.path.join(HERE, "PREREG.md")
    want = open(os.path.join(HERE, "PREREG.sha256"), encoding="utf-8").read().split()[0]
    got = hashlib.sha256(open(p, "rb").read()).hexdigest()
    if got != want:
        raise SystemExit("PREREG.md has been edited since freezing.\n  frozen %s\n  now    %s"
                         % (want, got))
    return got


def episodes():
    """Every stale episode, with the information needed to classify it.

    An episode OPENS when the peer consensus has moved >= THRESH since the book last
    repriced and the book has not repriced. It CLOSES when the book reprices, and is
    CENSORED if the tape ends or the game commences first.
    """
    rows = [r for r in panel.load_rows("live") if r.t >= FAST_ERA_FROM]
    K = panel.keyed(rows)
    out = []
    for (gid, mkt, side), by_t in K.items():
        ts = sorted(by_t)
        if len(ts) < 2:
            continue
        commence = None
        for t in ts:
            for r in by_t[t].values():
                commence = r.commence
                break
            break
        lastprice, lastcons, opened = {}, {}, {}
        for i, t in enumerate(ts):
            books = by_t[t]
            for bk, r in books.items():
                cons = panel.consensus_excluding(books, bk)
                if cons is None:
                    continue
                if bk not in lastprice:
                    lastprice[bk], lastcons[bk] = r.p_devig, cons
                    continue
                if abs(r.p_devig - lastprice[bk]) > 1e-9:          # repriced
                    if bk in opened:
                        j = opened.pop(bk)
                        out.append(_mk(gid, mkt, side, bk, ts, j, i, False, commence))
                    lastprice[bk], lastcons[bk] = r.p_devig, cons
                else:
                    if abs(cons - lastcons[bk]) >= THRESH and bk not in opened:
                        opened[bk] = i
        for bk, j in opened.items():                                # censored at tape end
            out.append(_mk(gid, mkt, side, bk, ts, j, len(ts) - 1, True, commence))
    return out


def _mk(gid, mkt, side, bk, ts, j, i, censored, commence):
    t0, t1 = _dt(ts[j]), _dt(ts[i])
    gaps = [(_dt(ts[k + 1]) - _dt(ts[k])).total_seconds() / 60.0 for k in range(j, i)]
    return {"game": gid, "market": mkt, "side": side, "book": bk,
            "i_open": j, "i_close": i, "polls": i - j,
            "minutes": (t1 - t0).total_seconds() / 60.0,
            "censored": bool(censored),
            "max_gap_min": max(gaps) if gaps else 0.0,
            "commence": commence}


def km_median(dur, cens):
    """Kaplan-Meier median. Returns None when survival never reaches 0.5."""
    pts = sorted(zip(dur, cens))
    n = len(pts)
    s, at_risk = 1.0, n
    for k, (d, c) in enumerate(pts):
        if not c:
            s *= (1.0 - 1.0 / at_risk)
            if s <= 0.5:
                return d
        at_risk -= 1
    return None


def main():
    sha = verify_prereg()
    print("=" * 94)
    print("M08 STALE WINDOW -- how long does a book stay behind its peers?")
    print("=" * 94)
    print("prereg sha256: %s" % sha)

    eps = episodes()
    obs = [e for e in eps if e["max_gap_min"] <= MAX_GAP_MIN]
    unobs = len(eps) - len(obs)
    closed = [e for e in obs if not e["censored"]]
    cens = [e for e in obs if e["censored"]]
    at_floor = [e for e in obs if e["polls"] <= 1]
    resolvable = [e for e in obs if e["polls"] >= 2]
    games = {e["game"] for e in obs}

    print("\nEPISODE COUNTS")
    print("  episodes                       : %d" % len(eps))
    print("  discarded as unobservable      : %d (capture gap > %.0f min)" % (unobs, MAX_GAP_MIN))
    print("  usable                         : %d" % len(obs))
    print("    of which closed              : %d" % len(closed))
    print("    of which right-censored      : %d" % len(cens))
    print("  distinct games                 : %d" % len(games))

    # ---- S1: the resolution floor -- always reported ---------------------
    pct_floor = 100.0 * len(at_floor) / len(obs) if obs else 0.0
    print("\nS1. THE RESOLUTION FLOOR -- a fact about the observer, not the market")
    print("  episodes AT the floor (closed within one poll) : %d (%.1f%%)"
          % (len(at_floor), pct_floor))
    print("  episodes RESOLVABLE (span 2+ poll intervals)   : %d (%.1f%%)"
          % (len(resolvable), 100.0 - pct_floor))
    print("  A floor episode has a true duration somewhere in (0, 2 x cadence) and carries")
    print("  NO duration information. Reporting it as a measured window would be reporting")
    print("  our own polling rate as if it were the market's behaviour.")

    # ---- S2 / S3 ---------------------------------------------------------
    by_book = defaultdict(int)
    for e in obs:
        by_book[e["book"]] += 1
    print("\nS2. EPISODES BY BOOK")
    for b, n in sorted(by_book.items(), key=lambda x: -x[1]):
        print("  %-18s %4d (%.1f%%)" % (b, n, 100.0 * n / len(obs)))
    print("\nS3. UNOBSERVABLE SHARE: %.1f%% of episodes straddle a capture gap > %.0f min"
          % (100.0 * unobs / max(len(eps), 1), MAX_GAP_MIN))

    res = {"prereg_sha256": sha, "threshold": THRESH,
           "counts": {"episodes": len(eps), "unobservable": unobs, "usable": len(obs),
                      "closed": len(closed), "censored": len(cens),
                      "games": len(games), "at_floor": len(at_floor),
                      "resolvable": len(resolvable)},
           "s1_pct_at_floor": round(pct_floor, 1),
           "s2_by_book": dict(sorted(by_book.items(), key=lambda x: -x[1])),
           "s3_pct_unobservable": round(100.0 * unobs / max(len(eps), 1), 1),
           "gate": {"games_required": GATE_GAMES, "episodes_required": GATE_EPISODES,
                    "resolvable_required": GATE_RESOLVABLE, "open": False},
           "primary": None}

    # ---- the gate, checked BEFORE the primary is computed -----------------
    gate_open = (len(games) >= GATE_GAMES and len(obs) >= GATE_EPISODES
                 and len(resolvable) >= GATE_RESOLVABLE)
    res["gate"]["open"] = bool(gate_open)

    print("\nSAMPLE GATE (PREREG.md): %d games, %d episodes, %d resolvable required"
          % (GATE_GAMES, GATE_EPISODES, GATE_RESOLVABLE))
    if not gate_open:
        print("  CLOSED -- need %d more games, %d more episodes, %d more resolvable."
              % (max(0, GATE_GAMES - len(games)), max(0, GATE_EPISODES - len(obs)),
                 max(0, GATE_RESOLVABLE - len(resolvable))))
        print("  The survival curve is NOT computed. Keep capturing and run this again.")
    else:
        dur = [e["minutes"] for e in resolvable]
        cn = [e["censored"] for e in resolvable]
        med = km_median(dur, cn)
        rnd = random.Random(SEED)
        byg = defaultdict(list)
        for e in resolvable:
            byg[e["game"]].append(e)
        keys = list(byg)
        boots = []
        for _ in range(DRAWS):
            samp = [e for k in (rnd.choice(keys) for _ in keys) for e in byg[k]]
            m = km_median([x["minutes"] for x in samp], [x["censored"] for x in samp])
            if m is not None:
                boots.append(m)
        boots.sort()
        lo = boots[int(0.025 * len(boots))] if boots else None
        hi = boots[int(0.975 * len(boots))] if boots else None
        print("  OPEN.")
        print("\nPRIMARY -- KM median stale-window, RESOLVABLE episodes only")
        print("  median %.1f min  [95%% CI %.1f, %.1f]  (n=%d, %d clusters)"
              % (med, lo, hi, len(resolvable), len(keys)))
        print("  Stated as a BOUND under a %.0f-minute cadence, carrying the D023"
              % 5.0)
        print("  amendment-4 timestamp-uncertainty and vendor-latency terms.")
        res["primary"] = {"km_median_min": med, "ci95": [lo, hi],
                          "n_resolvable": len(resolvable), "n_clusters": len(keys)}

    print("\n" + "=" * 94)
    if pct_floor >= 50.0:
        print("PREMISE WARNING: %.1f%% of episodes sit at the resolution floor. Over half of" % pct_floor)
        print("what looks like a stale window is indistinguishable from our own polling rate.")
        print("This is the falsification condition named in PREREG.md and it is ACTIVE.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS.json")


if __name__ == "__main__":
    main()
