# -*- coding: utf-8 -*-
"""M36 s04 -- who is exposed to the depth-shift defect s03 found?

E0-style diagnostic, NON-CLAIMING.

s03 established that the props seam carries no roster change but a real DEPTH
change: median books per quoted player moves 4 -> 5 across it. That matters only
for peer-consensus estimators, because a leave-one-out peer set of a different
size has different variance and different bias. The programme has three such
constructions -- M30, M31 and M32 -- so the obvious next question is whether the
defect has already bitten a receipted result, or is about to bite one.

This asks it two ways, because the two failure modes are different:

  RETROSPECTIVE. Does any existing receipted result span the props seam? A node
  reading only the historical archive cannot, by construction.

  PROSPECTIVE. M31 has not produced its primary statistic yet -- its sample gate
  is still closed and expected to open around 2026-08-27. If ITS peer set drifts
  across ITS OWN window, the same defect bites a number that does not exist yet,
  which is the more dangerous case because there is no published figure to audit
  afterwards. So the peer set is measured directly over every capture time in the
  panel rather than assumed stable.

A stable peer set here is a genuine negative result and is worth recording as one:
it certifies the node that is about to produce a headline number.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
MP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = r"C:\Users\jgallagher\wnba-betting-model"
HIST = os.path.join(ROOT, "data", "props_capture", "historical",
                    "master_props_historical.csv")
SEAM = "2026-07-31"


def main():
    res = {}
    print("=" * 94)
    print("M36 s04 -- exposure to the depth-shift defect (s03)")
    print("=" * 94)

    # ---- retrospective ---------------------------------------------------
    print("\n1. RETROSPECTIVE -- does any receipted result span the props seam?")
    print("   M30_PRICE_LEADERSHIP     reads odds_capture (game-level), not props.")
    print("   M31_DISLOCATION_PERSIST. reads odds_capture via M30's panel, not props.")
    print("   M32_DOES_IT_ACTUALLY_WIN reads master_props_historical.csv EXCLUSIVELY.")

    h = pd.read_csv(HIST, low_memory=False)
    # The seam is defined on ET GAME-DATE (s01/s03 both use ET). Comparing a raw
    # UTC timestamp against a UTC midnight is a unit mismatch: a 02:10 UTC tip on
    # 07-31 is a 22:10 ET game on 07-30 and does NOT cross the seam.
    h_gd = (pd.to_datetime(h["commence_time"], utc=True, errors="coerce")
              .dt.tz_convert("US/Eastern").dt.date)
    h_hi_gd = h_gd.max()
    h_hi_utc = pd.to_datetime(h["commence_time"], utc=True, errors="coerce").max()
    seam_d = pd.Timestamp(SEAM).date()
    spans = bool(h_hi_gd >= seam_d)
    n_after = int((h_gd >= seam_d).sum())
    print("\n   M32 source, last tip        : %s UTC" % h_hi_utc)
    print("   same tip as an ET game-date : %s" % h_hi_gd)
    print("   rows with ET game-date >= %s : %d" % (SEAM, n_after))
    print("   spans the seam? %s" % ("YES" if spans else "NO"))
    res["retrospective"] = {"m32_source_max_utc": str(h_hi_utc),
                            "m32_source_max_et_gamedate": str(h_hi_gd),
                            "rows_at_or_after_seam": n_after,
                            "spans_seam": spans}

    # ---- prospective -----------------------------------------------------
    print("\n2. PROSPECTIVE -- is M31's OWN peer set stable across its own window?")
    sys.path.insert(0, MP)
    sys.path.insert(0, os.path.join(MP, "M30_PRICE_LEADERSHIP"))
    import panel  # noqa: E402

    rows = panel.load_rows("live")
    by_t = defaultdict(set)
    for r in rows:
        by_t[r.t].add(r.book)
    ts = sorted(by_t)
    sizes = sorted(len(by_t[t]) for t in ts)
    presence = Counter()
    for t in ts:
        presence.update(by_t[t])

    print("   rows in panel        : %d" % len(rows))
    print("   capture times        : %d  (%s -> %s)" % (len(ts), ts[0], ts[-1]))
    print("   books per capture    : min %d  median %d  max %d"
          % (sizes[0], sizes[len(sizes) // 2], sizes[-1]))
    print("\n   book presence across capture times:")
    for b, c in presence.most_common():
        print("     %-22s %5.1f%%" % (b, 100.0 * c / len(ts)))

    # stable = every book present essentially always, and the count never collapses
    min_presence = min(100.0 * c / len(ts) for c in presence.values())
    stable = (min_presence >= 99.0) and (sizes[0] >= sizes[-1] - 1)
    res["prospective"] = {"rows": int(len(rows)), "capture_times": len(ts),
                          "first": str(ts[0]), "last": str(ts[-1]),
                          "books_min": sizes[0], "books_max": sizes[-1],
                          "min_book_presence_pct": round(min_presence, 2),
                          "stable": bool(stable)}

    print("\n" + "=" * 94)
    print("VERDICT")
    if spans:
        print("  RETROSPECTIVE: M32 source DOES reach past the seam (%d rows). Its"
              % n_after)
        print("  result may be exposed and must be re-checked before being cited.")
    else:
        print("  RETROSPECTIVE: no receipted result spans the props seam. M30 and M31")
        print("  read a different archive entirely; M32 source stops before it (last ET")
        print("  game-date %s). The depth shift is a forward hazard, not a" % h_hi_gd)
        print("  retroactive contaminant.")
    if stable:
        print("  PROSPECTIVE: M31's peer set is STABLE -- %d books, none below %.1f%% presence,"
              % (sizes[-1], min_presence))
        print("  count never varying by more than one across %d capture times. The statistic"
              % len(ts))
        print("  it produces when its gate opens is not exposed to this defect.")
    else:
        print("  PROSPECTIVE: M31's peer set is NOT stable -- min presence %.1f%%, count %d..%d."
              % (min_presence, sizes[0], sizes[-1]))
        print("  Its primary statistic WOULD be exposed. Fix before the gate opens.")
    print("")
    print("  Scope: this clears the three existing constructions. It says nothing about")
    print("  a FUTURE node that splices the props archives -- that remains blocked on")
    print("  carrying the 4 -> 5 depth difference, per s03.")
    print("=" * 94)
    res["clear"] = bool(not spans and stable)

    with open(os.path.join(HERE, "FINDINGS_s04.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS_s04.json")


if __name__ == "__main__":
    main()
