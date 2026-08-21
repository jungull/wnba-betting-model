"""build_quotes.py -- one row per BOOK QUOTE, with its leave-one-out peer consensus and the
realised outcome.

WHY THIS EXISTS. Every profitability number this programme holds is measured against CONSENSUS,
not against truth. M30/D157 established that a quote beating its peers' de-vigged consensus by
3 percentage points is worth +1.44% -- but "worth" there means *relative to where the market
settled*, not *relative to what happened*. Nobody has checked whether those quotes actually WIN.

That is the only question that decides whether anything here is a strategy, and the props archive
plus owned gamelog outcomes can answer it.

MACHINERY IS REUSED, NOT REIMPLEMENTED. The props load, in-play exclusion, entity resolution,
consensus-line matching and per-book de-vig are M14's recipe, which is MODEL_VS_MARKET's, which
delegates the vig math to M11's `consensus.no_vig` under the preregistered method. Outcomes come
from `mvm.load_outcomes()`. This file adds exactly two things: a LEAVE-ONE-OUT peer consensus, and
the realised return of actually taking the quote.

LEAVE-ONE-OUT MATTERS AND IS THE WHOLE POINT. M13 and M14 use `p_over_market_devig`, the consensus
over ALL books including the one being judged. For measuring how far a book sits from its peers
that inflates the apparent edge -- a generous book drags the benchmark toward itself, so the gap
looks smaller and the edge looks larger. M30 used leave-one-out for exactly this reason and the
threshold being tested here is M30's, so the benchmark must be built the same way.

NO MODEL IS INVOLVED. This measures the market against itself and against outcomes. No fitted
scoring model appears anywhere, so nothing here touches S42.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MP = HERE.parent
sys.path.insert(0, str(MP / "M11_CONSENSUS_MODEL"))
sys.path.insert(0, str(MP / "MODEL_VS_MARKET"))

import compute_model_vs_market as mvm   # noqa: E402
import consensus                        # noqa: E402

PROPS = Path(r"C:\Users\jgallagher\wnba-betting-model\data\props_capture\historical"
             r"\master_props_historical.csv")
MIN_PEERS = 3          # same as M30: two peers cannot outvote a disagreement


def implied(american: float) -> float:
    a = float(american)
    return (-a) / (-a + 100.0) if a < 0 else 100.0 / (a + 100.0)


def decimal(american: float) -> float:
    a = float(american)
    return 1.0 + (100.0 / -a if a < 0 else a / 100.0)


def build() -> tuple[pd.DataFrame, dict]:
    _, name_rows, _ = mvm.load_outcomes()
    id_index = mvm.build_identity_index(name_rows)
    ev = pd.read_parquet(MP / "M13_PLAYER_VALUE_TRANSLATION" / "translation_rows.parquet")

    raw = pd.read_csv(PROPS)
    raw["game_id"] = raw["game_id"].astype(str)
    raw["commence"] = pd.to_datetime(raw["commence_time"], utc=True)
    raw["snap_ret"] = pd.to_datetime(raw["snapshot_returned_utc"], utc=True)
    audit = {"n_raw": int(len(raw))}

    df = raw[~(raw["snap_ret"] >= raw["commence"])].copy()      # in-play, contract 4.4
    audit["n_inplay_excluded"] = audit["n_raw"] - len(df)
    n0 = len(df)
    df = df[~(df["over_price"].isna() | df["under_price"].isna())].copy()
    audit["n_one_sided_excluded"] = n0 - len(df)
    n0 = len(df)
    df = df[~df.duplicated(["game_id", "player_name", "bookmaker_key", "line"])].copy()
    audit["n_duplicate_dropped"] = n0 - len(df)

    df["player_id"] = df["player_name"].map(mvm._norm_name).map(id_index)
    audit["n_unresolved_excluded"] = int(df["player_id"].isna().sum())
    df = df[df["player_id"].notna()].copy()
    df["player_id"] = df["player_id"].astype("int64")

    keys = set(zip(ev["game_id"], ev["player_id"]))
    line_of = dict(zip(zip(ev["game_id"], ev["player_id"]), ev["consensus_line"]))
    df["key"] = list(zip(df["game_id"], df["player_id"]))
    n0 = len(df)
    df = df[df["key"].isin(keys)].copy()
    audit["n_outside_matched_universe"] = n0 - len(df)
    df["match_line"] = df["key"].map(line_of)
    n0 = len(df)
    df = df[df["line"] == df["match_line"]].copy()
    audit["n_off_consensus_line_excluded"] = n0 - len(df)

    # per-book de-vig, DELEGATED to M11 under the preregistered method
    p_over_book = []
    for op, up in zip(df["over_price"], df["under_price"]):
        probs, _, _, _ = consensus.no_vig([float(op), float(up)],
                                          method=consensus.PREREGISTERED_VIG_METHOD)
        p_over_book.append(probs[0])
    df["p_over_book"] = p_over_book

    # LEAVE-ONE-OUT peer consensus: median of every OTHER book's de-vigged over probability
    loo = np.full(len(df), np.nan)
    npeer = np.zeros(len(df), dtype=int)
    pos = {k: i for i, k in enumerate(df.index)}
    for _, grp in df.groupby("key", sort=False):
        v = grp["p_over_book"].to_numpy(float)
        for j, ix in enumerate(grp.index):
            others = np.delete(v, j)
            npeer[pos[ix]] = len(others)
            if len(others) >= MIN_PEERS:
                loo[pos[ix]] = float(np.median(others))
    df["cons_loo"] = loo
    df["n_peers"] = npeer
    audit["n_quotes_before_peer_gate"] = int(len(df))
    df = df[df["cons_loo"].notna()].copy()
    audit["n_quotes_with_enough_peers"] = int(len(df))

    out = df.join(ev.set_index(["game_id", "player_id"])[
        ["y_over", "pts", "consensus_line", "season", "game_date", "evaluation_tier",
         "p_over_market_devig"]], on=["game_id", "player_id"])
    out = out[out["y_over"].notna()].copy()
    audit["n_quotes_with_outcome"] = int(len(out))

    # the two sides of the quote, priced and benchmarked
    out["p_raw_over"] = out["over_price"].map(implied)
    out["p_raw_under"] = out["under_price"].map(implied)
    out["edge_over"] = out["cons_loo"] / out["p_raw_over"] - 1.0
    out["edge_under"] = (1.0 - out["cons_loo"]) / out["p_raw_under"] - 1.0
    out["gap_over"] = out["cons_loo"] - out["p_over_book"]        # peers minus this book
    out["gap_under"] = -out["gap_over"]

    take_over = out["edge_over"] >= out["edge_under"]
    out["side"] = np.where(take_over, "over", "under")
    out["edge"] = np.where(take_over, out["edge_over"], out["edge_under"])
    out["gap"] = np.where(take_over, out["gap_over"], out["gap_under"])
    out["price"] = np.where(take_over, out["over_price"], out["under_price"])
    won = np.where(take_over, out["y_over"] == 1, out["y_over"] == 0)
    out["won"] = won.astype(float)
    out["ret"] = np.where(won, out["price"].map(decimal) - 1.0, -1.0)
    return out, audit


if __name__ == "__main__":
    q, audit = build()
    print("=" * 84)
    print("SHAPE ONLY -- no return, no ROI, nothing to preregister against")
    print("=" * 84)
    for k, v in audit.items():
        print("  %-34s %d" % (k, v))
    print()
    print("  quotes           : %d" % len(q))
    print("  games            : %d" % q["game_id"].nunique())
    print("  game dates       : %d" % q["game_date"].nunique())
    print("  books            : %d  %s" % (q["bookmaker_key"].nunique(),
                                           sorted(q["bookmaker_key"].unique())))
    print("  seasons          : %s" % sorted(q["season"].unique()))
    print("  peers per quote  : median %d" % int(np.median(q["n_peers"])))
    print()
    print("  quotes by |gap| band (peers minus this book, in probability points):")
    for lo, hi in ((0.0, 0.01), (0.01, 0.02), (0.02, 0.03), (0.03, 1.0)):
        m = (q["gap"].abs() >= lo) & (q["gap"].abs() < hi)
        print("     %4.0f-%4.0fpp : %6d" % (lo * 100, hi * 100, int(m.sum())))
    q.drop(columns=["key"]).to_parquet(HERE / "quotes.parquet", index=False)
    print("\nwrote quotes.parquet")
