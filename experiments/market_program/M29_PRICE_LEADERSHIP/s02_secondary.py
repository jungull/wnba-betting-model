"""s02_secondary.py -- SECONDARY analysis. NOT confirmatory. Read DEFECTS.md first.

The preregistered primary statistic in s01 came back degenerate: a median of zero everywhere,
because 66% of dislocated books do not move at all over the horizon and 33% of observations
have neither side moving. A median over a distribution with a point mass that large at zero
measures the point mass, not the movement.

That is a defect in the PREREGISTRATION, not in the data, and per programme discipline it is
recorded rather than quietly repaired. s01 stands exactly as frozen. Everything in this file
is POST-HOC and is labelled as such: it may motivate a preregistered follow-up, and it may
not be quoted as a confirmed result.

The second defect: the prereg defined "did the book requote?" via `last_update`, which the
feed re-stamps on every poll -- 99.6% of consecutive captures show a fresh `last_update`
while 82.6% of prices are unchanged. The intent of that gate is unambiguous, so it is
reimplemented on PRICE IDENTITY and the substitution is disclosed here and in DEFECTS.md.

NO GAME OUTCOME IS READ ANYWHERE IN THIS FILE.
"""
from __future__ import annotations

import json
import random
import statistics as st
from collections import defaultdict

import panel
import s01_leadership as s01

SEED = s01.SEED
DRAWS = s01.DRAWS
PRIMARY = s01.PRIMARY


def boot_mean(obs, fn, seed=SEED, draws=DRAWS):
    """Cluster bootstrap of a MEAN, resampling games."""
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
            out.append(st.mean(fn(x) for x in pool))
    out.sort()
    return st.mean(fn(x) for x in obs), out[int(0.025 * len(out))], out[int(0.975 * len(out))]


def line(label, obs, fn, unit=""):
    if not obs:
        print("  %-40s NO OBSERVATIONS" % label)
        return None
    m, lo, hi = boot_mean(obs, fn)
    star = "  *" if (lo > 0 or hi < 0) else ""
    print("  %-40s n=%6d  %+7.3f%s [%+.3f,%+.3f]%s" % (label, len(obs), m, unit, lo, hi, star))
    return {"label": label, "n": len(obs), "mean": round(m, 5),
            "ci95": [round(lo, 5), round(hi, 5)], "excludes_zero": bool(lo > 0 or hi < 0)}


def main():
    rows = panel.load_rows("live", as_of=s01.AS_OF)
    obs = s01.observations(rows)
    for o in obs:                      # DEFECT 2 repair: requote means the PRICE changed
        o["requoted"] = o["book_share"] != 0.0
    prim = [o for o in obs if o["abs_gap0"] >= PRIMARY]

    out = {"_status": "SECONDARY / POST-HOC. Not confirmatory. See DEFECTS.md.",
           "as_of": s01.AS_OF,
           "prereg_sha256": open("PREREG.sha256").read().split()[0]}

    print("=" * 92)
    print("M29 s02 -- SECONDARY analysis (post-hoc). The preregistered median was degenerate.")
    print("=" * 92)

    zb = sum(1 for o in prim if o["book_share"] == 0.0)
    zc = sum(1 for o in prim if o["cons_share"] == 0.0)
    zboth = sum(1 for o in prim if o["book_share"] == 0.0 and o["cons_share"] == 0.0)
    print("WHY THE MEDIAN WAS DEGENERATE (primary threshold, n=%d)" % len(prim))
    print("  dislocated book did not move at all : %5d (%.1f%%)" % (zb, 100 * zb / len(prim)))
    print("  consensus did not move at all       : %5d (%.1f%%)" % (zc, 100 * zc / len(prim)))
    print("  neither moved                       : %5d (%.1f%%)" % (zboth, 100 * zboth / len(prim)))
    out["point_mass_at_zero"] = {"book_still": zb, "cons_still": zc, "both_still": zboth,
                                 "n": len(prim)}

    print()
    print("SHARE OF THE GAP CLOSED, by mover (mean; the prereg asked for a median)")
    out["shares"] = {
        "book": line("book moved toward consensus", prim, lambda o: o["book_share"]),
        "cons": line("consensus moved toward book", prim, lambda o: o["cons_share"]),
        "diff": line("difference (book - consensus)", prim,
                     lambda o: o["book_share"] - o["cons_share"]),
    }

    print()
    print("THE SAME THING IN PROBABILITY POINTS, which has no ratio pathology")
    print("  (positive = movement in the gap-closing direction)")
    def sgn(o):
        return 1.0 if o["gap0"] > 0 else -1.0
    out["pp"] = {
        "gap0": line("initial gap |g0|", prim, lambda o: o["abs_gap0"] * 100, "pp"),
        "gap1": line("gap one horizon later |g1|", prim, lambda o: abs(o["gap1"]) * 100, "pp"),
        "shrink": line("gap shrinkage |g0| - |g1|", prim,
                       lambda o: (o["abs_gap0"] - abs(o["gap1"])) * 100, "pp"),
        "by_book": line("...contributed by the book moving", prim,
                        lambda o: o["book_share"] * o["abs_gap0"] * 100, "pp"),
        "by_cons": line("...contributed by consensus moving", prim,
                        lambda o: o["cons_share"] * o["abs_gap0"] * 100, "pp"),
    }

    print()
    print("STALENESS, redefined on PRICE identity because last_update is re-stamped every poll")
    rq = [o for o in prim if o["requoted"]]
    nq = [o for o in prim if not o["requoted"]]
    out["requoted"] = {
        "frac_requoted": round(len(rq) / max(len(prim), 1), 4),
        "requoted_diff": line("book requoted: book - cons share", rq,
                              lambda o: o["book_share"] - o["cons_share"]),
        "not_requoted_cons": line("book did NOT requote: cons share", nq,
                                  lambda o: o["cons_share"]),
    }

    print()
    print("P4 -- per book. cons_share high = its peers come to IT. (mean, cluster CI)")
    by_book = defaultdict(list)
    for o in prim:
        by_book[o["book"]].append(o)
    rank = []
    for bk, os_ in by_book.items():
        if len(os_) < 30:
            continue
        cm, clo, chi = boot_mean(os_, lambda o: o["cons_share"])
        bm, blo, bhi = boot_mean(os_, lambda o: o["book_share"])
        rank.append({"book": bk, "n": len(os_), "cons_mean": round(cm, 4),
                     "cons_ci95": [round(clo, 4), round(chi, 4)],
                     "book_mean": round(bm, 4), "book_ci95": [round(blo, 4), round(bhi, 4)],
                     "requote_rate": round(sum(1 for o in os_ if o["requoted"]) / len(os_), 3)})
    for r in sorted(rank, key=lambda x: -x["cons_mean"]):
        print("  %-16s n=%5d  cons %+.3f [%+.3f,%+.3f]  book %+.3f [%+.3f,%+.3f]  requote %.0f%%"
              % (r["book"], r["n"], r["cons_mean"], r["cons_ci95"][0], r["cons_ci95"][1],
                 r["book_mean"], r["book_ci95"][0], r["book_ci95"][1], r["requote_rate"] * 100))
    out["by_book"] = rank

    with open("FINDINGS_s02.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
    print()
    print("wrote FINDINGS_s02.json")


if __name__ == "__main__":
    main()
