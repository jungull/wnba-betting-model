"""s01_persistence.py -- how long does a dislocated price stay on the screen?

Implements PREREG.md, frozen at
51fc14ff79821bdbfe3569145dd517d5433f1defbef515380bb6b37653fbcb76 before the data needed to
answer the question existed.

THE SAMPLE GATE IS ENFORCED HERE, IN CODE. Until 30 games / 150 episodes / 40 strong
episodes have accumulated, this script reports sample counts and REFUSES to compute the
survival curve. That is not a formality: without it, the curve could be recomputed daily and
published on whichever day it looked best, which is choosing the answer. Run it as often as
you like -- it will keep saying "not yet" until the tape has caught up.

NO GAME OUTCOME IS READ ANYWHERE IN THIS FILE.
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "M30_PRICE_LEADERSHIP"))
import panel                      # noqa: E402

FAST_ERA_FROM = "2026-08-19T14:00:00Z"   # first capture after the cadence change
MAX_GAP_MIN = 12.0                       # a wider gap makes an episode unobservable
STRONG_PP = 0.030
SEED = 20260820
DRAWS = 2000

GATE_GAMES = 30
GATE_EPISODES = 150
GATE_STRONG = 40


def _dt(s):
    try:
        return datetime.strptime(s.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
    except (ValueError, AttributeError):
        return None


def price_observations(rows):
    """Every pre-game quote with its capture time and the leave-one-out peer consensus.

    M30 has an equivalent function, but it does not carry the capture instant -- it never
    needed to, because it pooled across time. This node is entirely about WHEN, so it builds
    its own rather than editing a node that has already passed. The consensus arithmetic is
    imported from M30's panel.py unchanged, so a dislocation means the same thing here as it
    does there.
    """
    out = []
    for (gid, market, side), by_t in panel.keyed(rows).items():
        for t, books in by_t.items():
            dt = _dt(t)
            commence = _dt(next(iter(books.values())).commence)
            if dt is None or commence is None or dt >= commence:
                continue                       # pre-game only (D151)
            for bk, r in books.items():
                cons = panel.consensus_excluding(books, bk)
                if cons is None or r.p_raw <= 0:
                    continue
                out.append({"t": t, "game": gid, "market": market, "side": side, "book": bk,
                            "commence": r.commence,
                            "gap_devig": r.p_devig - cons,
                            "edge": cons / r.p_raw - 1.0})
    return out


def build_episodes(as_of: str | None = None):
    """Open/close every dislocation episode. Returns (episodes, diagnostics)."""
    rows = [r for r in panel.load_rows("live", as_of=as_of) if r.t >= FAST_ERA_FROM]
    obs = price_observations(rows)

    by_series = defaultdict(dict)          # series -> {t -> obs}
    for o in obs:
        by_series[(o["game"], o["market"], o["side"], o["book"])][o["t"]] = o

    all_caps = sorted({r.t for r in rows})
    last_cap = _dt(all_caps[-1]) if all_caps else None

    episodes, discarded = [], 0
    for series, by_t in by_series.items():
        times = sorted(by_t)
        open_at = None
        peak_gap = 0.0
        broken = False
        for i, t in enumerate(times):
            o = by_t[t]
            hot = o["edge"] > 0
            if hot and open_at is None:
                open_at, peak_gap, broken = t, -o["gap_devig"], False
            elif hot and open_at is not None:
                peak_gap = max(peak_gap, -o["gap_devig"])
                prev = _dt(times[i - 1])
                if prev and (_dt(t) - prev).total_seconds() / 60.0 > MAX_GAP_MIN:
                    broken = True          # unknown lifetime; must not be fabricated
            elif not hot and open_at is not None:
                if broken:
                    discarded += 1
                else:
                    episodes.append(_episode(series, open_at, t, peak_gap, False))
                open_at = None
        if open_at is not None:            # still open when the tape ran out
            if broken:
                discarded += 1
            else:
                end = min([x for x in (_dt(by_t[times[-1]]["commence"]) if
                                       by_t[times[-1]].get("commence") else None, last_cap)
                           if x is not None], default=last_cap)
                episodes.append(_episode(series, open_at, None, peak_gap, True, end))
    return episodes, {"discarded_unobservable": discarded,
                      "captures": len(all_caps),
                      "era_from": all_caps[0] if all_caps else None,
                      "era_to": all_caps[-1] if all_caps else None}


def _episode(series, open_at, close_at, peak_gap, censored, censor_end=None):
    t0 = _dt(open_at)
    t1 = _dt(close_at) if close_at else censor_end
    mins = (t1 - t0).total_seconds() / 60.0 if (t0 and t1) else 0.0
    return {"game": series[0], "market": series[1], "side": series[2], "book": series[3],
            "opened": open_at, "closed": close_at, "minutes": round(max(mins, 0.0), 2),
            "censored": censored, "peak_gap": round(peak_gap, 5),
            "strong": peak_gap >= STRONG_PP}


def kaplan_meier(eps):
    """Survival function over episode lifetimes, honouring right-censoring."""
    if not eps:
        return [], None
    times = sorted({e["minutes"] for e in eps if not e["censored"]})
    surv, curve = 1.0, []
    for t in times:
        d = sum(1 for e in eps if not e["censored"] and e["minutes"] == t)
        n = sum(1 for e in eps if e["minutes"] >= t)
        if n <= 0:
            continue
        surv *= (1.0 - d / n)
        curve.append((t, round(surv, 5), n, d))
    median = next((t for t, s, _, _ in curve if s <= 0.5), None)
    return curve, median


def survival_at(curve, minutes):
    s = 1.0
    for t, v, _, _ in curve:
        if t <= minutes:
            s = v
        else:
            break
    return s


def boot_median(eps, seed=SEED, draws=DRAWS):
    by_game = defaultdict(list)
    for e in eps:
        by_game[e["game"]].append(e)
    games = list(by_game)
    rng = random.Random(seed)
    meds = []
    for _ in range(draws):
        pool = []
        for _ in range(len(games)):
            pool.extend(by_game[rng.choice(games)])
        _, m = kaplan_meier(pool)
        if m is not None:
            meds.append(m)
    if not meds:
        return None, None
    meds.sort()
    return meds[int(0.025 * len(meds))], meds[int(0.975 * len(meds))]


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    as_of = sys.argv[1] if len(sys.argv) > 1 else None
    eps, diag = build_episodes(as_of)
    games = len({e["game"] for e in eps})
    strong = [e for e in eps if e["strong"]]

    print("=" * 88)
    print("M31 DISLOCATION PERSISTENCE -- how long does a dislocated price stay up?")
    print("=" * 88)
    print("five-minute era: %s -> %s (%d captures)"
          % (diag["era_from"], diag["era_to"], diag["captures"]))
    print("episodes            : %d" % len(eps))
    print("  of which STRONG   : %d  (opinion gap reached %.0fpp)" % (len(strong), STRONG_PP * 100))
    print("  of which censored : %d  (still open when the game started or the tape ended)"
          % sum(1 for e in eps if e["censored"]))
    print("distinct games      : %d" % games)
    print("discarded as unobservable (capture gap > %.0f min): %d"
          % (MAX_GAP_MIN, diag["discarded_unobservable"]))

    out = {"prereg_sha256": open("PREREG.sha256").read().split()[0],
           "as_of": as_of or diag["era_to"], "counts": {
               "episodes": len(eps), "strong": len(strong), "games": games,
               "censored": sum(1 for e in eps if e["censored"]),
               "discarded_unobservable": diag["discarded_unobservable"]},
           "gate": {"games_required": GATE_GAMES, "episodes_required": GATE_EPISODES,
                    "strong_required": GATE_STRONG}}

    gate_open = (games >= GATE_GAMES and len(eps) >= GATE_EPISODES
                 and len(strong) >= GATE_STRONG)
    out["gate"]["open"] = gate_open

    print()
    print("SAMPLE GATE (PREREG.md): %d games, %d episodes, %d strong required"
          % (GATE_GAMES, GATE_EPISODES, GATE_STRONG))
    if not gate_open:
        need = []
        if games < GATE_GAMES:
            need.append("%d more games" % (GATE_GAMES - games))
        if len(eps) < GATE_EPISODES:
            need.append("%d more episodes" % (GATE_EPISODES - len(eps)))
        if len(strong) < GATE_STRONG:
            need.append("%d more strong episodes" % (GATE_STRONG - len(strong)))
        print("  CLOSED -- need " + ", ".join(need) + ".")
        print("  The survival curve is NOT computed. This is deliberate: recomputing it every")
        print("  day and publishing when it looks best is choosing the answer, not measuring")
        print("  it. Keep capturing and run this again.")
        out["primary"] = None
    else:
        print("  OPEN -- computing the preregistered primary.")
        out["primary"] = {}
        for label, sub in (("STRONG", strong), ("WEAK", [e for e in eps if not e["strong"]])):
            curve, med = kaplan_meier(sub)
            lo, hi = boot_median(sub)
            out["primary"][label] = {
                "n": len(sub), "median_minutes": med, "median_ci95": [lo, hi],
                "survival_5min": round(survival_at(curve, 5), 4),
                "survival_10min": round(survival_at(curve, 10), 4),
                "survival_30min": round(survival_at(curve, 30), 4),
                "survival_60min": round(survival_at(curve, 60), 4)}
            r = out["primary"][label]
            print("  %-7s n=%3d  median %s min [%s,%s]  alive at 5/10/30/60 min: "
                  "%.0f%% / %.0f%% / %.0f%% / %.0f%%"
                  % (label, r["n"], r["median_minutes"], lo, hi,
                     r["survival_5min"] * 100, r["survival_10min"] * 100,
                     r["survival_30min"] * 100, r["survival_60min"] * 100))

    with open("FINDINGS.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
    print()
    print("wrote FINDINGS.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
