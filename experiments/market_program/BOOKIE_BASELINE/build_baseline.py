"""BOOKIE_BASELINE -- measures THE MARKET (not any of our models) against
realized outcomes on the game universe, using the NEW T1 vendor-asserted
odds archive (data/market_snapshots/historical/featured_backfill.jsonl,
LIVE worktree) and owned gamelog-derived game outcomes
(data/masters/master_team.parquet, this worktree).

Governed by MARKET_PROGRAM_CONTRACT.md
(sha256 1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de)
and D034_GRADUATION_STANDARD (player_program DECISION_LEDGER.jsonl):
de-vigged threshold probabilities are the PRIMARY quantity; any
distributional assumption is documented (none used here -- this program
reports moneyline win-probability calibration only, never an implied
scoring-margin distribution).

This program NEVER touches SEALED_RESULTS and NEVER evaluates any of our
own models -- it measures the bookmaker consensus and best-book price
against realized game outcomes only.

INPUT TIER: every row in the input archive is provenance_class
T1_VENDOR_ASSERTED / vendor_ts_semantics=vendor_asserted_unwitnessed (see
first two archive lines, inspected by hand). Per MARKET_PROGRAM_CONTRACT.md
section 4.3 / TAXONOMY.json timestamp_tiers.T1: admissible with an explicit
vendor-latency term and an explicit vendor-asserted-unwitnessed label on
every claim; never the sole basis for an executability claim (this program
makes no executability claim). This is NOT the T2 master_odds.csv object
that MARKET_PROGRAM_CONTRACT.md section 5 bounds -- that section's
enumerated use classes (M00-U1..U6) do not apply to this archive. This
module still carries an explicit unknown-snapshot-time caveat on every
output row and in the report, per the coordinator's instruction, because
the vendor timestamp here is likewise unwitnessed by us.

Stdlib + pandas + pyarrow only. No git, no network, no subagents.
"""
from __future__ import annotations

import json
import sys
import math
import hashlib
import datetime as dt
from collections import defaultdict, Counter

import pandas as pd

# ---------------------------------------------------------------------------
# Delegate vig removal / consensus machinery to M11 -- NEVER reimplemented.
# ---------------------------------------------------------------------------
M11_DIR = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\market_program\M11_CONSENSUS_MODEL"
sys.path.insert(0, M11_DIR)
import consensus as m11  # noqa: E402

CONTRACT_PATH = r"experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/MARKET_PROGRAM_CONTRACT.md"
CONTRACT_SHA256 = "1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de"

ARCHIVE_PATH = r"C:\Users\jgallagher\wnba-betting-model\data\market_snapshots\historical\featured_backfill.jsonl"
MASTER_TEAM_PATH = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\data\masters\master_team.parquet"
OUT_DIR = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\market_program\BOOKIE_BASELINE"

PRIMARY_BOOK = "fanduel"  # measured: most frequently appearing book in the
# archive (4,719 game-appearances across all snapshot lines and both
# classes -- see JOIN_AUDIT.json "primary_book_selection" for the full
# book-frequency table). Used as the BEST_BOOK variant throughout.

# ---------------------------------------------------------------------------
# Unknown-snapshot-time caveat -- FROZEN TEXT, cited verbatim on every
# output row and in the report (D034 / MARKET_PROGRAM_CONTRACT.md section 4.3).
# ---------------------------------------------------------------------------
CAVEAT_TEXT = (
    "This snapshot's timestamp is vendor-asserted and unwitnessed "
    "(tier T1: THIRD_PARTY_CONTEMPORANEOUS, per MARKET_PROGRAM_CONTRACT.md "
    "section 4.3). It is drawn from a third-party historical-odds archive "
    "retrieved on 2026-08-06, labelled EARLY (vendor-asserted ~16:00Z "
    "request) or LATE (vendor-asserted ~23:30Z request) relative to the "
    "archive's own request day, not from our own real-time capture. LATE "
    "is closer to commence than EARLY, but neither is a witnessed closing "
    "line, and the true hours-to-commence at capture is not independently "
    "verified. No timing, latency, reaction, or CLV inference may be drawn "
    "from this snapshot; it supports calibration-against-realized-outcomes "
    "only, at an unknown-but-bounded-pregame instant."
)
CAVEAT_SHA256 = hashlib.sha256(CAVEAT_TEXT.encode("utf-8")).hexdigest()

# ---------------------------------------------------------------------------
# Team-name -> gamelog abbreviation map (measured from the archive's 16
# distinct team names against master_team.parquet's team_abbreviation set;
# franchise-rename years carry both abbreviations as candidates).
# ---------------------------------------------------------------------------
NAME_TO_ABBR = {
    "Atlanta Dream": ["ATL"],
    "Chicago Sky": ["CHI"],
    "Connecticut Sun": ["CON"],
    "Dallas Wings": ["DAL"],
    "Golden State Valkyries": ["GSV"],
    "Indiana Fever": ["IND"],
    "Las Vegas Aces": ["LVA"],
    "Los Angeles Sparks": ["LAS"],
    "Minnesota Lynx": ["MIN"],
    "New York Liberty": ["NYL"],
    "Phoenix Mercury": ["PHO", "PHX"],
    "Portland Fire": ["PDX"],
    "Seattle Storm": ["SEA"],
    "Toronto Tempo": ["TOR"],
    "Washington Mystics": ["WAS"],
    "Nigeria": None,  # national team exhibition; not in the gamelog universe
}

ET_OFFSET_HOURS = 4  # WNBA regular/playoff season runs May-Oct, EDT (UTC-4)
                      # throughout; approximation documented in BASELINE.md.


def parse_dt(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# 1. Load owned game outcomes
# ---------------------------------------------------------------------------

def load_outcomes():
    mt = pd.read_parquet(MASTER_TEAM_PATH)
    mt = mt[mt["is_home"] == 1][
        ["game_id", "game_date", "season", "season_type",
         "team_abbreviation", "opp_team_abbreviation", "pts", "opp_pts"]
    ].copy()
    mt["game_date"] = pd.to_datetime(mt["game_date"]).dt.date
    # index for exact-date lookup and a fallback list per (home,away) pair
    by_pair = defaultdict(list)
    for row in mt.itertuples(index=False):
        by_pair[(row.team_abbreviation, row.opp_team_abbreviation)].append(row)
    return mt, by_pair


def match_outcome(home_abbrs, away_abbrs, et_date, by_pair):
    """Returns (row_or_None, reason). Exact-date match preferred; falls back
    to a +/-1 day window ONLY if it resolves to exactly one candidate (a
    back-to-back series on consecutive dates must never be silently
    collapsed -- an ambiguous window is reported, not guessed)."""
    candidates = []
    for h in home_abbrs:
        for a in away_abbrs:
            candidates.extend(by_pair.get((h, a), []))
    if not candidates:
        return None, "NO_MASTER_ROW_FOR_TEAM_PAIR"
    exact = [r for r in candidates if r.game_date == et_date]
    if len(exact) == 1:
        return exact[0], "MATCHED_EXACT_DATE"
    if len(exact) > 1:
        return None, f"AMBIGUOUS_EXACT_DATE_{len(exact)}_ROWS"
    window = [r for r in candidates
              if abs((r.game_date - et_date).days) <= 1]
    if len(window) == 1:
        return window[0], "MATCHED_WITHIN_1_DAY"
    if len(window) == 0:
        return None, f"NO_MASTER_ROW_WITHIN_1_DAY_et_date={et_date}"
    return None, f"AMBIGUOUS_WITHIN_1_DAY_{len(window)}_ROWS"


# ---------------------------------------------------------------------------
# 2. Load archive, build per-game/per-class "closest-to-commence" snapshot
# ---------------------------------------------------------------------------

def load_archive():
    """Returns dict: game_id -> {"EARLY": snap, "LATE": snap, "meta": {...}}
    where each snap is the archive line whose requested_ts is the LATEST one
    <= commence_time among lines of that class in which the game appears
    (closest-to-commence "the day's snapshot" for that class), and every
    contributing vendor_snapshot_ts is structurally required to be strictly
    before commence_time (in-play exclusion, contract section 4.4)."""
    game_meta = {}
    # per game_id, per class -> list of (requested_ts, snap_record)
    candidates = defaultdict(lambda: defaultdict(list))
    n_lines = 0
    n_payload_games = 0
    n_inplay_excluded = 0
    with open(ARCHIVE_PATH, encoding="utf-8") as f:
        for line in f:
            n_lines += 1
            d = json.loads(line)
            hour = d["requested_ts"][11:13]
            cls = "EARLY" if hour == "16" else ("LATE" if hour == "23" else None)
            if cls is None:
                continue  # unexpected request hour; never silently bucketed
            vendor_snapshot_ts = d["vendor_snapshot_ts"]
            retrieval_ts = d["retrieval_ts"]
            vendor_ts_semantics = d["vendor_ts_semantics"]
            provenance_class = d["provenance_class"]
            req_ts = d["requested_ts"]
            for g in d["payload"]:
                n_payload_games += 1
                commence = g["commence_time"]
                if vendor_snapshot_ts >= commence:
                    n_inplay_excluded += 1
                    continue
                gid = g["id"]
                game_meta[gid] = {
                    "home_team": g["home_team"],
                    "away_team": g["away_team"],
                    "commence_time": commence,
                }
                candidates[gid][cls].append((req_ts, {
                    "requested_ts": req_ts,
                    "vendor_snapshot_ts": vendor_snapshot_ts,
                    "retrieval_ts": retrieval_ts,
                    "vendor_ts_semantics": vendor_ts_semantics,
                    "provenance_class": provenance_class,
                    "bookmakers": g.get("bookmakers", []),
                }))

    per_game = {}
    for gid, meta in game_meta.items():
        picked = {}
        for cls in ("EARLY", "LATE"):
            lst = candidates[gid].get(cls, [])
            if not lst:
                continue
            lst.sort(key=lambda t: t[0])
            picked[cls] = lst[-1][1]  # latest requested_ts <= commence
        per_game[gid] = {"meta": meta, "snaps": picked}

    audit = {
        "n_archive_lines": n_lines,
        "n_payload_game_appearances": n_payload_games,
        "n_inplay_rows_excluded_structural": n_inplay_excluded,
        "n_distinct_games": len(per_game),
    }
    return per_game, audit


# ---------------------------------------------------------------------------
# 3. Per-book quote extraction
# ---------------------------------------------------------------------------

def extract_market(snap, market_key, home_team, away_team):
    """Returns dict book -> {outcomes...} for the given market at this
    snapshot. h2h/spreads: {'home_price','away_price','home_point','away_point'}
    totals: {'over_price','under_price','point'}"""
    out = {}
    for bm in snap["bookmakers"]:
        book = bm["key"]
        for mk in bm.get("markets", []):
            if mk["key"] != market_key:
                continue
            outcomes = {o["name"]: o for o in mk["outcomes"]}
            if market_key in ("h2h", "spreads"):
                ho = outcomes.get(home_team)
                ao = outcomes.get(away_team)
                if ho is None or ao is None:
                    continue
                rec = {
                    "home_price": ho["price"], "away_price": ao["price"],
                }
                if market_key == "spreads":
                    rec["home_point"] = ho.get("point")
                    rec["away_point"] = ao.get("point")
                out[book] = rec
            elif market_key == "totals":
                ov = outcomes.get("Over")
                un = outcomes.get("Under")
                if ov is None or un is None:
                    continue
                out[book] = {
                    "over_price": ov["price"], "under_price": un["price"],
                    "point": ov.get("point"),
                }
    return out


# ---------------------------------------------------------------------------
# 4. Metric accumulators
# ---------------------------------------------------------------------------

class Series:
    """One (season_bucket, snapshot_class, variant) accumulator per metric
    family. variant in {"cross_book", "best_book"}."""

    def __init__(self):
        self.spread_errs = []       # predicted_home_margin - actual_home_margin
        self.total_errs = []        # predicted_total - actual_total
        self.ml_probs = []          # (p_home, y_home_won)
        self.book_counts_h2h = []
        self.book_counts_spreads = []
        self.book_counts_totals = []
        self.n_games_with_h2h = 0
        self.n_games_with_spread = 0
        self.n_games_with_total = 0

    def add_spread(self, pred_home_margin, actual_home_margin):
        self.spread_errs.append(pred_home_margin - actual_home_margin)

    def add_total(self, pred_total, actual_total):
        self.total_errs.append(pred_total - actual_total)

    def add_ml(self, p_home, y_home_won):
        self.ml_probs.append((p_home, y_home_won))


def mae_bias(errs):
    if not errs:
        return None, None, 0
    n = len(errs)
    mae = sum(abs(e) for e in errs) / n
    bias = sum(errs) / n
    return mae, bias, n


def brier_logloss(pairs):
    if not pairs:
        return None, None, 0
    n = len(pairs)
    brier = sum((p - y) ** 2 for p, y in pairs) / n
    eps = 1e-12
    ll = -sum(
        y * math.log(min(max(p, eps), 1 - eps)) +
        (1 - y) * math.log(min(max(1 - p, eps), 1 - eps))
        for p, y in pairs
    ) / n
    return brier, ll, n


def calibration_table(pairs, n_bins=10):
    bins = [[] for _ in range(n_bins)]
    for p, y in pairs:
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, y))
    table = []
    for i, b in enumerate(bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        if b:
            mean_p = sum(p for p, _ in b) / len(b)
            emp_rate = sum(y for _, y in b) / len(b)
        else:
            mean_p = None
            emp_rate = None
        table.append({
            "bin": f"[{lo:.1f},{hi:.1f})", "n": len(b),
            "mean_predicted_p_home": mean_p,
            "empirical_home_win_rate": emp_rate,
        })
    return table


# ---------------------------------------------------------------------------
# 5. Main measurement pass
# ---------------------------------------------------------------------------

def main():
    mt, by_pair = load_outcomes()
    per_game, load_audit = load_archive()

    matched = {}
    unmatched_rows = []
    for gid, rec in per_game.items():
        meta = rec["meta"]
        home, away = meta["home_team"], meta["away_team"]
        home_abbrs = NAME_TO_ABBR.get(home)
        away_abbrs = NAME_TO_ABBR.get(away)
        if not home_abbrs or not away_abbrs:
            unmatched_rows.append({
                "game_id": gid, "home_team": home, "away_team": away,
                "commence_time": meta["commence_time"],
                "reason": "NO_ABBR_MAPPING",
            })
            continue
        ct = parse_dt(meta["commence_time"])
        et_date = (ct - dt.timedelta(hours=ET_OFFSET_HOURS)).date()
        row, reason = match_outcome(home_abbrs, away_abbrs, et_date, by_pair)
        if row is None:
            unmatched_rows.append({
                "game_id": gid, "home_team": home, "away_team": away,
                "commence_time": meta["commence_time"],
                "et_date_estimate": str(et_date), "reason": reason,
            })
            continue
        matched[gid] = {
            "master_game_id": row.game_id,
            "game_date": str(row.game_date),
            "season": int(row.season),
            "season_type": row.season_type,
            "home_pts": float(row.pts),
            "away_pts": float(row.opp_pts),
            "match_reason": reason,
        }

    # accumulators keyed (season_bucket, class, variant)
    def newkey():
        return Series()
    acc = defaultdict(newkey)
    outcome_rows = []  # per-row measured detail, for JSON export

    for gid, rec in per_game.items():
        if gid not in matched:
            continue
        out = matched[gid]
        meta = rec["meta"]
        home, away = meta["home_team"], meta["away_team"]
        actual_margin = out["home_pts"] - out["away_pts"]
        actual_total = out["home_pts"] + out["away_pts"]
        y_home_won = 1.0 if out["home_pts"] > out["away_pts"] else 0.0
        season = out["season"]

        for cls, snap in rec["snaps"].items():
            # ---- h2h ----
            h2h = extract_market(snap, "h2h", home, away)
            n_books_h2h = len(h2h)
            per_book_probs = []
            for book, q in h2h.items():
                try:
                    quote = m11.make_quote(
                        bookmaker=book, price=q["home_price"],
                        capture_ts=snap["retrieval_ts"], tier="T1",
                        vendor_ts=snap["vendor_snapshot_ts"],
                        vendor_ts_semantics=snap["vendor_ts_semantics"],
                        market="h2h", outcome="HOME",
                    )
                    quote["opposite_price"] = q["away_price"]
                    per_book_probs.append(quote)
                except Exception:
                    continue
            consensus_obj = None
            if per_book_probs:
                consensus_obj = m11.consensus_fair_value(
                    per_book_probs, allow_t1=True, game_id=gid)
            for variant, p_home in (
                ("cross_book", consensus_obj["consensus_fair_prob"]
                 if consensus_obj else None),
                ("best_book", None),
            ):
                if variant == "best_book":
                    if PRIMARY_BOOK in h2h:
                        try:
                            probs, _, _, _ = m11.no_vig(
                                [h2h[PRIMARY_BOOK]["home_price"],
                                 h2h[PRIMARY_BOOK]["away_price"]])
                            p_home = probs[0]
                        except Exception:
                            p_home = None
                    else:
                        p_home = None
                if p_home is None:
                    continue
                s = acc[(season, cls, variant)]
                s.add_ml(p_home, y_home_won)
                s.n_games_with_h2h += 1
                s.book_counts_h2h.append(n_books_h2h)

            # ---- spreads ----
            sp = extract_market(snap, "spreads", home, away)
            n_books_sp = len(sp)
            home_points = [q["home_point"] for q in sp.values()
                           if q.get("home_point") is not None]
            cross_pred = -(sum(home_points) / len(home_points)) if home_points else None
            best_pred = None
            if PRIMARY_BOOK in sp and sp[PRIMARY_BOOK].get("home_point") is not None:
                best_pred = -sp[PRIMARY_BOOK]["home_point"]
            for variant, pred in (("cross_book", cross_pred), ("best_book", best_pred)):
                if pred is None:
                    continue
                s = acc[(season, cls, variant)]
                s.add_spread(pred, actual_margin)
                s.n_games_with_spread += 1
                s.book_counts_spreads.append(n_books_sp)

            # ---- totals ----
            tt = extract_market(snap, "totals", home, away)
            n_books_tt = len(tt)
            pts = [q["point"] for q in tt.values() if q.get("point") is not None]
            cross_tot = sum(pts) / len(pts) if pts else None
            best_tot = None
            if PRIMARY_BOOK in tt and tt[PRIMARY_BOOK].get("point") is not None:
                best_tot = tt[PRIMARY_BOOK]["point"]
            for variant, pred in (("cross_book", cross_tot), ("best_book", best_tot)):
                if pred is None:
                    continue
                s = acc[(season, cls, variant)]
                s.add_total(pred, actual_total)
                s.n_games_with_total += 1
                s.book_counts_totals.append(n_books_tt)

            outcome_rows.append({
                "game_id": gid, "class": cls, "season": season,
                "home_team": home, "away_team": away,
                "n_books_h2h": n_books_h2h, "n_books_spreads": n_books_sp,
                "n_books_totals": n_books_tt,
                "cross_book_p_home": consensus_obj["consensus_fair_prob"]
                    if consensus_obj else None,
                "actual_home_won": y_home_won,
            })

    # ---- build pooled buckets by summing raw lists across seasons ----
    seasons_present = sorted({k[0] for k in acc if k[0] != "POOLED"})
    for cls in ("EARLY", "LATE"):
        for variant in ("cross_book", "best_book"):
            pooled = Series()
            for season in seasons_present:
                s = acc.get((season, cls, variant))
                if not s:
                    continue
                pooled.spread_errs.extend(s.spread_errs)
                pooled.total_errs.extend(s.total_errs)
                pooled.ml_probs.extend(s.ml_probs)
                pooled.book_counts_h2h.extend(s.book_counts_h2h)
                pooled.book_counts_spreads.extend(s.book_counts_spreads)
                pooled.book_counts_totals.extend(s.book_counts_totals)
                pooled.n_games_with_h2h += s.n_games_with_h2h
                pooled.n_games_with_spread += s.n_games_with_spread
                pooled.n_games_with_total += s.n_games_with_total
            acc[("POOLED", cls, variant)] = pooled

    # ---- serialize metrics ----
    def avg(lst):
        return (sum(lst) / len(lst)) if lst else None

    metrics = {
        "schema": "market_program/BOOKIE_BASELINE/metrics/1",
        "caveat_text": CAVEAT_TEXT,
        "caveat_sha256": CAVEAT_SHA256,
        "vig_method": m11.PREREGISTERED_VIG_METHOD,
        "vig_preregistration_hash": m11.PREREGISTRATION_HASH,
        "primary_book_best_book_variant": PRIMARY_BOOK,
        "rows": [],
    }
    for (season, cls, variant), s in sorted(
        acc.items(), key=lambda kv: (str(kv[0][0]), kv[0][1], kv[0][2])
    ):
        spread_mae, spread_bias, n_spread = mae_bias(s.spread_errs)
        total_mae, total_bias, n_total = mae_bias(s.total_errs)
        brier, logloss, n_ml = brier_logloss(s.ml_probs)
        row = {
            "season": season, "snapshot_class": cls, "variant": variant,
            "spread": {"mae": spread_mae, "bias": spread_bias, "n": n_spread},
            "total": {"mae": total_mae, "bias": total_bias, "n": n_total},
            "moneyline": {
                "brier": brier, "log_loss": logloss, "n": n_ml,
                "calibration_10bin": calibration_table(s.ml_probs),
            },
            "coverage": {
                "avg_books_h2h": avg(s.book_counts_h2h),
                "avg_books_spreads": avg(s.book_counts_spreads),
                "avg_books_totals": avg(s.book_counts_totals),
                "n_games_with_h2h": s.n_games_with_h2h,
                "n_games_with_spread": s.n_games_with_spread,
                "n_games_with_total": s.n_games_with_total,
            },
        }
        metrics["rows"].append(row)

    join_audit = {
        "schema": "market_program/BOOKIE_BASELINE/join_audit/1",
        "archive_load": load_audit,
        "n_games_matched": len(matched),
        "n_games_unmatched": len(unmatched_rows),
        "unmatched_games": unmatched_rows,
        "match_reason_counts": dict(Counter(
            m["match_reason"] for m in matched.values())),
        "unmatched_reason_counts": dict(Counter(
            u["reason"].split("_et_date=")[0] for u in unmatched_rows)),
    }

    with open(f"{OUT_DIR}/baseline_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    with open(f"{OUT_DIR}/join_audit.json", "w", encoding="utf-8") as f:
        json.dump(join_audit, f, indent=2, default=str)
    with open(f"{OUT_DIR}/outcome_rows.json", "w", encoding="utf-8") as f:
        json.dump(outcome_rows, f, indent=2, default=str)

    print("games total in archive:", len(per_game))
    print("matched:", len(matched), "unmatched:", len(unmatched_rows))
    print("rows written:", len(metrics["rows"]))
    return metrics, join_audit


if __name__ == "__main__":
    main()
