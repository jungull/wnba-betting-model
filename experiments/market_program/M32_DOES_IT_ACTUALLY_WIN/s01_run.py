"""s01_run.py -- implements PREREG.md 22edafa5d230a817e4c468b9d8ff5920b002481e259c7b4651376529c17412e1

Response is MONEY: realised return per unit staked. Nothing here is a probability score.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

SEED, DRAWS = 20260821, 2000


def _decimal(american: float) -> float:
    a = float(american)
    return 1.0 + (100.0 / -a if a < 0 else a / 100.0)
ACT = 0.03


def boot(sub: pd.DataFrame, rng) -> tuple[float, float, float]:
    """Cluster bootstrap of the mean return, resampling GAME DATES."""
    g = sub.groupby("game_date")["ret"]
    sums, cnts = g.sum().to_numpy(), g.count().to_numpy()
    k = len(sums)
    if k < 2:
        return float(sub["ret"].mean()), float("nan"), float("nan")
    acc = np.empty(DRAWS)
    for b in range(DRAWS):
        i = rng.integers(0, k, k)
        acc[b] = sums[i].sum() / cnts[i].sum()
    acc.sort()
    return float(sub["ret"].mean()), float(acc[int(0.025 * DRAWS)]), float(acc[int(0.975 * DRAWS)])


def cell(name: str, sub: pd.DataFrame, rng) -> dict:
    if not len(sub):
        print("  %-34s EMPTY" % name)
        return {}
    m, lo, hi = boot(sub, rng)
    star = "  *" if (np.isfinite(lo) and (lo > 0 or hi < 0)) else ""
    print("  %-34s n=%6d  ROI %+7.3f%% [%+7.3f, %+7.3f]  win %5.1f%%  price %+7.1f%s"
          % (name, len(sub), m * 100, lo * 100, hi * 100,
             sub["won"].mean() * 100, sub["price"].mean(), star))
    return {"n": int(len(sub)), "roi": m, "ci95": [lo, hi],
            "win_rate": float(sub["won"].mean()), "mean_price": float(sub["price"].mean()),
            "n_dates": int(sub["game_date"].nunique()),
            "excludes_zero": bool(np.isfinite(lo) and (lo > 0 or hi < 0))}


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    rng = np.random.default_rng(SEED)
    q = pd.read_parquet("quotes.parquet")
    out = {"prereg_sha256": open("PREREG.sha256").read().split()[0],
           "n_quotes": int(len(q)), "n_games": int(q["game_id"].nunique()),
           "n_dates": int(q["game_date"].nunique()),
           "seasons": sorted(int(x) for x in q["season"].unique())}

    print("=" * 100)
    print("M32 -- do the quotes that beat consensus actually WIN? Response is realised money.")
    print("=" * 100)
    print("%d quotes | %d games | %d game dates | 9 books | seasons %s\n"
          % (len(q), q["game_id"].nunique(), q["game_date"].nunique(), out["seasons"]))

    print("THE BASELINE, AND THE CLAIM")
    out["all"] = cell("every quote, indiscriminately", q, rng)
    out["edge_pos"] = cell("edge > 0 (beats peer consensus)", q[q["edge"] > 0], rng)

    print("\nBY HOW FAR THE BOOK IS MORE GENEROUS THAN ITS PEERS")
    bands = [(0.00, 0.01), (0.01, 0.02), (0.02, 0.03), (0.03, 1.00)]
    out["bands"] = {}
    rois = []
    for lo, hi in bands:
        sub = q[(q["gap"] >= lo) & (q["gap"] < hi)]
        r = cell("gap %2.0f-%3.0fpp" % (lo * 100, hi * 100), sub, rng)
        out["bands"]["%.2f_%.2f" % (lo, hi)] = r
        if r:
            rois.append(r["roi"])

    print("\nPRIMARY -- M30's ACT threshold")
    out["primary"] = cell("gap >= 3pp  [PRIMARY]", q[q["gap"] >= ACT], rng)

    # THE PREREGISTERED CONTROL WAS UNBUILDABLE AND THIS IS RECORDED, NOT PAPERED OVER.
    # `gap` is defined on the side TAKEN, and the side taken is whichever has the larger
    # edge -- always the side the book is generous on. So `gap <= -3pp` is empty BY
    # CONSTRUCTION and the control as written could never have fired. The control that
    # answers the same question is the OPPOSITE SIDE of the very same quotes: bet the side
    # the peers call overpriced. If the mechanism were real that must lose, and by more.
    print("\nNEGATIVE CONTROL -- the OPPOSITE side of the same quotes (see DEFECTS.md)")
    prim_q = q[q["gap"] >= ACT].copy()
    opp = prim_q.copy()
    opp["price"] = np.where(prim_q["side"] == "over",
                            prim_q["under_price"], prim_q["over_price"])
    opp_won = np.where(prim_q["side"] == "over", prim_q["y_over"] == 0, prim_q["y_over"] == 1)
    opp["won"] = opp_won.astype(float)
    opp["ret"] = np.where(opp_won, opp["price"].map(_decimal) - 1.0, -1.0)
    out["control"] = cell("opposite side of the 3pp quotes", opp, rng)

    print("\nBY SEASON, at the primary threshold")
    out["by_season"] = {}
    for s in out["seasons"]:
        sub = q[(q["gap"] >= ACT) & (q["season"] == s)]
        out["by_season"][str(s)] = cell("  %d" % s, sub, rng)

    print("\nBY BOOK, at the primary threshold (P5: no book supplies >50%% of the total return)")
    prim = q[q["gap"] >= ACT]
    tot = float(prim["ret"].sum())
    shares = {}
    for bk, sub in prim.groupby("bookmaker_key"):
        contrib = float(sub["ret"].sum())
        shares[bk] = contrib / tot if tot != 0 else float("nan")
        print("  %-20s n=%5d  ROI %+7.3f%%  contributes %+8.3f of %+8.3f total"
              % (bk, len(sub), sub["ret"].mean() * 100, contrib, tot))
    out["book_share_of_total_return"] = shares

    print("\n" + "=" * 100)
    print("PREDICTIONS")
    p1 = -0.08 <= out["all"]["roi"] <= -0.02
    p2 = out["primary"]["roi"] > 0
    p3 = all(rois[i] <= rois[i + 1] + 1e-12 for i in range(len(rois) - 1))
    p4 = not out["primary"]["excludes_zero"]
    mx = max((abs(v) for v in shares.values() if np.isfinite(v)), default=float("nan"))
    p5 = bool(np.isfinite(mx) and mx <= 0.5)
    p6 = bool(out["control"].get("roi", 0.0) < out["all"]["roi"])
    for nm, ok, txt in (("P1", p1, "betting everything loses roughly the vig"),
                        ("P2", p2, "the 3pp bucket has POSITIVE realised return"),
                        ("P3", p3, "ROI rises monotonically across the gap bands"),
                        ("P4", p4, "...but its 95% interval still includes zero"),
                        ("P5", p5, "no single book supplies >50% of the total return"),
                        ("P6", p6, "the stingy control loses, and by more than the baseline")):
        print("  %s %-4s %s" % (nm, "PASS" if ok else "FAIL", txt))
    out["predictions"] = {"P1": bool(p1), "P2": bool(p2), "P3": bool(p3),
                          "P4": bool(p4), "P5": bool(p5), "P6": bool(p6)}
    out["max_book_share"] = float(mx)

    json.dump(out, open("FINDINGS.json", "w", encoding="utf-8", newline="\n"),
              indent=1, default=float)
    print("\nwrote FINDINGS.json")


if __name__ == "__main__":
    main()
