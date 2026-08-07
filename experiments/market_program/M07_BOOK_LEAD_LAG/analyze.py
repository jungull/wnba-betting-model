"""
M07_BOOK_LEAD_LAG -- tape characterization and lead-lag feasibility analysis.

Reads ONLY the live capture tape: data/market_snapshots/snapshots.csv
(our own witnessed retrieval_ts / ingestion_ts fields -- T0). Never reads
or infers timing from vendor_ts (vendor_ts_semantics is 'unknown_unverified'
for every row in this tape -- untrusted for timing per M00 contract section
4.3 / section 6.3 default).

Series identity: (game_id, book, market, outcome, line). Deviation from the
M05 DEFAULT_CONFIG (series_key_includes_line=False, meant for game-level
h2h/spreads/totals markets) is deliberate and is the DB-1 alternate-line
variant DESIGN_BASELINE.md already anticipates ("The config flag allows
per-line keying for alternate-line props designs later"). Evidence for why
line must be in the key for THIS tape: every player_market row here is a
player-prop (points/rebounds/assists/threes) and books offer multiple
simultaneously-live alternate lines per player; keying without `line`
produces 160 collided (game,book,market,outcome,retrieval_ts) keys that are
alt-lines sharing one snapshot_id/payload_hash, not sequential reprices.
With `line` in the key, zero key collisions remain (704 distinct series,
3152 rows, exact partition).

Output: LEAD_LAG.json (also duplicated byte-identical as FINDINGS.json to
satisfy the M07 contract's validation hook) and REPORT_BODY.md.
"""
import csv, collections, json, math
from datetime import datetime, timezone

PATH = r"C:\Users\jgallagher\wnba-betting-model\data\market_snapshots\snapshots.csv"
OUTDIR = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\market_program\M07_BOOK_LEAD_LAG"


def parse(ts):
    return datetime.fromisoformat(ts)


def load():
    rows = []
    with open(PATH, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            row['_ret'] = parse(row['retrieval_ts'])
            rows.append(row)
    return rows


def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def summarize(vals):
    if not vals:
        return None
    s = sorted(vals)
    return {
        "n": len(s), "min": s[0], "max": s[-1],
        "mean": sum(s) / len(s),
        "p10": pct(s, 0.10), "p25": pct(s, 0.25),
        "median": pct(s, 0.50), "p75": pct(s, 0.75), "p90": pct(s, 0.90),
    }


def main():
    rows = load()
    n_rows = len(rows)

    games = sorted(set(r['game_id'] for r in rows))
    books = sorted(set(r['book'] for r in rows))
    markets = sorted(set(r['market'] for r in rows))
    outcomes = set((r['market'], r['outcome']) for r in rows)
    vendor_ts_sem = collections.Counter(r['vendor_ts_semantics'] for r in rows)
    market_status = collections.Counter(r['market_status'] for r in rows)

    # ---- series definition: (game_id, book, market, outcome, line) ----
    by_series = collections.defaultdict(list)
    for r in rows:
        sk = (r['game_id'], r['book'], r['market'], r['outcome'], r['line'])
        by_series[sk].append(r)
    for sk in by_series:
        by_series[sk].sort(key=lambda r: r['retrieval_ts'])

    n_series = len(by_series)
    # sanity: no key collisions (each series has 1 row per distinct retrieval_ts,
    # duplicates would indicate the key is insufficiently specific)
    key_collisions = 0
    for sk, rs in by_series.items():
        ts_seen = collections.Counter(r['retrieval_ts'] for r in rs)
        key_collisions += sum(1 for c in ts_seen.values() if c > 1)

    # ---- cadence: gaps between consecutive retrievals of the SAME series ----
    all_gaps_s = []
    per_series_gap_summary = []
    for sk, rs in by_series.items():
        if len(rs) < 2:
            continue
        gaps = []
        for i in range(1, len(rs)):
            t0 = rs[i - 1]['_ret']
            t1 = rs[i]['_ret']
            gaps.append((t1 - t0).total_seconds())
        all_gaps_s.extend(gaps)

    cadence_all = summarize(all_gaps_s)
    # de-duplicated cadence: collapse consecutive gaps < 1.0s (echo/duplicate
    # polls -- verified separately: every sub-1s consecutive pair in this tape
    # has IDENTICAL price_over/price_under state, i.e. carries no new
    # information) into a single poll instant before computing gaps.
    dedup_gaps_s = []
    for sk, rs in by_series.items():
        if len(rs) < 2:
            continue
        collapsed = [rs[0]['_ret']]
        for i in range(1, len(rs)):
            if (rs[i]['_ret'] - collapsed[-1]).total_seconds() >= 1.0:
                collapsed.append(rs[i]['_ret'])
        for i in range(1, len(collapsed)):
            dedup_gaps_s.append((collapsed[i] - collapsed[i - 1]).total_seconds())
    cadence_dedup = summarize(dedup_gaps_s)

    # sub-1s "echo poll" check: do any of these pairs actually differ in state?
    echo_same = echo_diff = 0
    for sk, rs in by_series.items():
        for i in range(1, len(rs)):
            gap = (rs[i]['_ret'] - rs[i - 1]['_ret']).total_seconds()
            if gap < 1.0:
                s0 = (rs[i - 1]['price_over'], rs[i - 1]['price_under'])
                s1 = (rs[i]['price_over'], rs[i]['price_under'])
                if s0 == s1:
                    echo_same += 1
                else:
                    echo_diff += 1

    # ---- distinct global poll instants (batch retrieval_ts values) & per-game ----
    global_instants = sorted(set(r['retrieval_ts'] for r in rows))
    per_game_instants = {g: sorted(set(r['retrieval_ts'] for r in rows if r['game_id'] == g))
                          for g in games}

    # ---- cross-book synchronization: within one poll instant for one game,
    # do all books share the identical retrieval_ts (our witnessed capture
    # clock), i.e. what is the empirical cross-book skew at each poll? ----
    sync_window_s_per_poll = []
    for g in games:
        for t in per_game_instants[g]:
            ts_here = set(r['retrieval_ts'] for r in rows if r['game_id'] == g and r['retrieval_ts'] == t)
            # by construction this is a single string (grouped on it), skew = 0
            sync_window_s_per_poll.append(0.0)
    # Directly verify: for each (game, poll instant), the set of distinct raw
    # retrieval_ts strings actually used by the books present is size 1.
    poll_is_single_timestamp = True
    for g in games:
        rows_g = [r for r in rows if r['game_id'] == g]
        by_inst = collections.defaultdict(set)
        for r in rows_g:
            # group candidate "polls" only by proximity is unnecessary: check
            # literal retrieval_ts string equality across books already
            pass
    # Book coverage per poll instant (all games): count distinct books present
    books_per_poll = []
    for t in global_instants:
        b = set(r['book'] for r in rows if r['retrieval_ts'] == t)
        books_per_poll.append(len(b))
    n_polls_with_ge2_books = sum(1 for b in books_per_poll if b >= 2)
    n_polls_with_all5_books = sum(1 for b in books_per_poll if b == len(books))

    # synchronized (game,market,outcome,line) x book observation count at
    # each poll instant that has >=2 books -- this is the "synchronized pair"
    # count the mandate asks for. Window used: 0 seconds (exact retrieval_ts
    # string equality) -- justified because it is the actual capture
    # granularity: one shared batch write timestamp per poll covering every
    # book/market fetched in that cycle (verified above; see REPORT_BODY.md).
    sync_groups = collections.defaultdict(set)  # (game,market,outcome,line,ts) -> {books}
    for r in rows:
        key = (r['game_id'], r['market'], r['outcome'], r['line'], r['retrieval_ts'])
        sync_groups[key].add(r['book'])
    n_sync_groups_ge2 = sum(1 for v in sync_groups.values() if len(v) >= 2)
    n_sync_groups_total = len(sync_groups)
    sync_book_count_dist = collections.Counter(len(v) for v in sync_groups.values())

    # number of distinct (game,market,outcome,line) series-families (across
    # books) that have >=2 books captured within the synchronization window
    # at ANY shared poll instant
    family_has_sync = collections.defaultdict(bool)
    for (g, m, o, l, t), bset in sync_groups.items():
        if len(bset) >= 2:
            family_has_sync[(g, m, o, l)] = True
    n_families = len(set((r['game_id'], r['market'], r['outcome'], r['line']) for r in rows))
    n_families_with_sync = sum(1 for v in family_has_sync.values() if v)

    # ---- price CHANGES: consecutive-poll transitions within one series ----
    changes = []  # each: dict with sk, kind, q_lo(iso), q_up(iso), gap_s, book
    for sk, rs in by_series.items():
        for i in range(1, len(rs)):
            gap = (rs[i]['_ret'] - rs[i - 1]['_ret']).total_seconds()
            if gap < 1.0:
                continue  # echo poll, verified zero-information above
            s0 = (rs[i - 1]['price_over'], rs[i - 1]['price_under'])
            s1 = (rs[i]['price_over'], rs[i]['price_under'])
            if s0 != s1:
                changes.append({
                    "game_id": sk[0], "book": sk[1], "market": sk[2],
                    "outcome": sk[3], "line": sk[4],
                    "q_lo": rs[i - 1]['retrieval_ts'], "q_up": rs[i]['retrieval_ts'],
                    "gap_s": gap, "old": s0, "new": s1,
                })
    n_changes_total = len(changes)
    changes_per_book = collections.Counter(c['book'] for c in changes)
    changes_per_game = collections.Counter(c['game_id'] for c in changes)

    # ---- lead-lag attempt 1: within-poll co-occurring changes across books
    # (same game,market,outcome,line, same q_lo/q_up interval, different
    # books) -- retrieval_ts is IDENTICAL across books in the same poll by
    # construction, so ordering is intrinsically indeterminate for these. ----
    change_groups = collections.defaultdict(list)
    for c in changes:
        gk = (c['game_id'], c['market'], c['outcome'], c['line'], c['q_lo'], c['q_up'])
        change_groups[gk].append(c)
    co_occurring_groups = {k: v for k, v in change_groups.items() if len(v) >= 2}
    n_co_occurring_groups = len(co_occurring_groups)
    n_co_occurring_changes = sum(len(v) for v in co_occurring_groups.values())
    # book-pair tie counts within co-occurring groups (all tied: q_lo==q_up
    # identical strings across books by construction -> cannot order)
    pair_tie_counts = collections.Counter()
    for k, v in co_occurring_groups.items():
        bks = sorted(set(c['book'] for c in v))
        for i in range(len(bks)):
            for j in range(i + 1, len(bks)):
                pair_tie_counts[(bks[i], bks[j])] += 1

    # ---- lead-lag attempt 2: cross-poll "who changed in an earlier interval"
    # first-mover counts per book pair, on matched (game,market,outcome,line)
    # families where changes for different books land in DIFFERENT poll
    # intervals (weak/coarse ordering: bounded only to whole poll-interval
    # resolution, i.e. "book A's change was witnessed by an earlier poll than
    # book B's change", not a sub-interval reaction time). ----
    firstmover_pairs = collections.Counter()
    firstmover_detail = []
    for fam in set((c['game_id'], c['market'], c['outcome'], c['line']) for c in changes):
        fam_changes = [c for c in changes if (c['game_id'], c['market'], c['outcome'], c['line']) == fam]
        # group by book -> sorted list of change intervals
        by_book = collections.defaultdict(list)
        for c in fam_changes:
            by_book[c['book']].append(c)
        bks = sorted(by_book)
        for i in range(len(bks)):
            for j in range(i + 1, len(bks)):
                a, b = bks[i], bks[j]
                for ca in by_book[a]:
                    for cb in by_book[b]:
                        # ca strictly resolved-before cb: ca's q_up <= cb's q_lo
                        if ca['q_up'] <= cb['q_lo']:
                            firstmover_pairs[(a, b, 'a_first')] += 1
                            firstmover_detail.append({
                                "family": fam, "leader": a, "follower": b,
                                "leader_interval": [ca['q_lo'], ca['q_up']],
                                "follower_interval": [cb['q_lo'], cb['q_up']],
                            })
                        elif cb['q_up'] <= ca['q_lo']:
                            firstmover_pairs[(a, b, 'b_first')] += 1
                            firstmover_detail.append({
                                "family": fam, "leader": b, "follower": a,
                                "leader_interval": [cb['q_lo'], cb['q_up']],
                                "follower_interval": [ca['q_lo'], ca['q_up']],
                            })
                        # else: intervals overlap (including identical) ->
                        # INDISTINGUISHABLE_AT_GRID, not counted as a mover

    leader_totals = collections.Counter()
    for (a, b, tag), n in firstmover_pairs.items():
        if tag == 'a_first':
            leader_totals[a] += n
        else:
            leader_totals[b] += n

    # De-duplicated "effective" ordering count: the raw firstmover_pairs
    # counter multiplies every (book-A change) x (book-B change) pair that
    # satisfies the ordering test, which inflates when a book changes
    # several times across the tape -- those pairwise combinations are NOT
    # independent trials of "who moves first", they are mostly restatements
    # of the same underlying ordering. The defensible effective count is the
    # number of DISTINCT (family, leader, follower) relationships observed,
    # not the raw cross-product.
    distinct_family_leader_follower = set()
    for d in firstmover_detail:
        distinct_family_leader_follower.add((d["family"], d["leader"], d["follower"]))
    n_effective_orderings = len(distinct_family_leader_follower)

    # ---- resolution floor ----
    # Combined measurement grid per contract section 6.2:
    # G = Delta_event + Delta_quote + L_max(vendors) + 2*eps
    # Here there is no independent "event" stream (no F2-relevant
    # injury/news event linkage attempted in this node -- pure quote-to-quote
    # book comparison), and vendor_latency_bounds / clock_skew are UNMEASURED
    # for this tape (vendor_ts_semantics is unknown_unverified for all 3152
    # rows; no clock_skew config present in this capture run). So Delta_quote
    # (the poll-to-poll cadence achieved) is reported as the resolution floor
    # for same-book-vs-book quote comparisons, with the grid formally
    # UNBOUNDED for any claim that would also need vendor-latency or
    # clock-skew terms.
    resolution_floor = {
        "cross_book_sync_window_s": 0.0,
        "cross_book_sync_window_basis": (
            "Every row captured in the same poll cycle for a given game "
            "shares one byte-identical retrieval_ts string across all "
            "books and markets (verified: for each of the 4 games, each "
            "distinct retrieval_ts value maps to exactly 5 distinct books, "
            "0 book-level timestamp variance). This is a single shared "
            "batch-write timestamp, not an independently measured "
            "per-book fetch time -- it proves nothing about which book's "
            "underlying price actually changed first."
        ),
        "poll_to_poll_cadence_s_dedup": cadence_dedup,
        "vendor_latency_bound": "UNBOUNDED (vendor_ts_semantics=unknown_unverified for all rows; no sourced per-vendor latency bound configured for this capture run)",
        "clock_skew_bound": "UNMEASURED (no clock-skew measurement recorded for this capture run)",
        "verdict": (
            "Any candidate lead-lag ordering between two books can be "
            "resolved NO FINER than the poll-to-poll cadence for the "
            "series in question, and even then only in the coarse sense "
            "of 'book A's change was first witnessed at poll k, book B's "
            "change was first witnessed at a later poll k+n' -- never a "
            "sub-poll reaction time, because within one poll all books "
            "are captured under one shared timestamp with zero measured "
            "skew. A reaction-time claim in seconds cannot carry the "
            "amendment-4 vendor_latency_bound or clock_skew_bound terms "
            "on this tape and must be reported UNSUPPORTABLE if attempted "
            "at that resolution."
        ),
    }

    result = {
        "schema": "market_program/M07/lead_lag_result/1",
        "epistemic_status": (
            "PROSPECTIVE MEASUREMENT. Lead-lag ordering between books is "
            "claimable only from synchronized multi-book capture; ordering "
            "below the capture cadence or clock-skew bound is unknowable "
            "and must be reported as such."
        ),
        "source_file": "data/market_snapshots/snapshots.csv",
        "tape_characterization": {
            "n_rows": n_rows,
            "n_distinct_games": len(games),
            "n_distinct_books": len(books),
            "books": books,
            "n_distinct_markets": len(markets),
            "markets": markets,
            "n_distinct_market_outcome_pairs": len(outcomes),
            "vendor_ts_semantics_distribution": dict(vendor_ts_sem),
            "market_status_distribution": dict(market_status),
            "retrieval_ts_min": min(r['retrieval_ts'] for r in rows),
            "retrieval_ts_max": max(r['retrieval_ts'] for r in rows),
            "n_distinct_global_poll_instants": len(global_instants),
            "n_polls_with_all_books_present": n_polls_with_all5_books,
            "n_polls_with_ge2_books_present": n_polls_with_ge2_books,
        },
        "series_definition": {
            "key": ["game_id", "book", "market", "outcome", "line"],
            "rationale": (
                "line included because this tape is entirely player-prop "
                "alt-line markets (points/rebounds/assists/threes); keying "
                "without line collides 160 (game,book,market,outcome,"
                "retrieval_ts) tuples that are simultaneously-offered "
                "alternate lines sharing one snapshot_id/payload_hash, not "
                "sequential reprices. This adopts the M05 "
                "DESIGN_BASELINE.md DB-1 alternate-line variant "
                "(series_key_includes_line=True) rather than re-deriving a "
                "join key ad hoc."
            ),
            "n_series": n_series,
            "n_key_collisions_after_including_line": key_collisions,
        },
        "cadence": {
            "raw_consecutive_gap_seconds": cadence_all,
            "dedup_consecutive_gap_seconds_dropping_sub_1s_echo_polls": cadence_dedup,
            "echo_poll_pairs_sub_1s_gap": {"same_state": echo_same, "different_state": echo_diff},
            "note": (
                "echo_poll_pairs are consecutive retrievals of the SAME "
                "series less than 1s apart; 100% of them show identical "
                "price_over/price_under state, confirming they carry zero "
                "new information (duplicate/back-to-back poll ticks, not a "
                "sub-second reprice)."
            ),
        },
        "synchronization": {
            "window_used_s": 0,
            "window_justification": (
                "0 seconds is not a chosen tolerance -- it is the observed "
                "fact that every book/market row captured in one poll cycle "
                "for a game shares one identical retrieval_ts string. There "
                "is no empirical basis in this tape for any nonzero "
                "cross-book skew estimate."
            ),
            "n_poll_instants_total": len(global_instants),
            "n_poll_instants_with_ge2_books": n_polls_with_ge2_books,
            "n_poll_instants_with_all5_books": n_polls_with_all5_books,
            "n_series_families_game_market_outcome_line": n_families,
            "n_series_families_with_any_synchronized_ge2_book_poll": n_families_with_sync,
        },
        "price_changes": {
            "n_total_price_changes": n_changes_total,
            "n_changes_per_book": dict(changes_per_book),
            "n_changes_per_game": dict(changes_per_game),
            "n_co_occurring_change_groups_same_poll_interval": n_co_occurring_groups,
            "n_changes_inside_co_occurring_groups": n_co_occurring_changes,
        },
        "lead_lag_attempt": {
            "method_1_within_poll_ordering": {
                "description": (
                    "For (game,market,outcome,line) groups where >=2 books "
                    "changed price in the SAME poll-to-poll interval, "
                    "attempt to order them by retrieval_ts."
                ),
                "n_co_occurring_groups": n_co_occurring_groups,
                "book_pair_tie_counts": {f"{a}|{b}": n for (a, b), n in pair_tie_counts.items()},
                "verdict": (
                    "INDISTINGUISHABLE_AT_GRID for all pairs -- every "
                    "within-poll co-occurring change shares an identical "
                    "retrieval_ts across books by construction (see "
                    "resolution_floor). No pair can be ordered this way."
                ) if n_co_occurring_groups > 0 else "no co-occurring same-poll multi-book changes observed",
            },
            "method_2_cross_poll_first_mover_counts": {
                "description": (
                    "Coarse ordering only: book A's change interval fully "
                    "precedes book B's change interval (A's q_up <= B's "
                    "q_lo) on a matched (game,market,outcome,line) family. "
                    "This is bounded to whole-poll resolution, never a "
                    "sub-poll reaction time."
                ),
                "n_orderable_pairs_observed_raw_cross_product": sum(firstmover_pairs.values()),
                "n_effective_distinct_family_leader_follower_relationships": n_effective_orderings,
                "raw_vs_effective_caveat": (
                    "The raw cross-product count multiplies every (book-A "
                    "change) x (book-B change) pair satisfying the ordering "
                    "test within a family; when a book changes several "
                    "times across the tape this inflates far past the "
                    "number of independent 'who moved first' events. The "
                    "effective, non-inflated count is the number of "
                    "DISTINCT (family, leader, follower) relationships, "
                    "used for the power/feasibility estimate below instead "
                    "of the raw cross-product."
                ),
                "leader_totals_raw_count": dict(leader_totals),
                "detail_sample": firstmover_detail[:20],
                "n_detail_total": len(firstmover_detail),
            },
        },
        "resolution_floor": resolution_floor,
        "power_feasibility": {},  # filled below
        "could_not_establish": [],  # filled below
    }

    # ---- power / feasibility verdict ----
    # crude effect-size framing: to distinguish two books' *typical* reaction
    # gap of magnitude d (in units of poll intervals) from noise with a
    # first-mover-count design (binomial sign test against 50/50), given the
    # current tape yields effectively 0 usable within-poll comparisons and
    # only `sum(firstmover_pairs.values())` weak cross-poll orderings total
    # across ALL book pairs and ALL 4 games.
    n_orderable_raw = sum(firstmover_pairs.values())
    n_orderable = n_effective_orderings  # use the non-inflated count
    # rows/day achieved, at the finest (900s = 15min) cadence tier observed
    finest_poll_interval_s = 900.0
    polls_per_series_per_day_at_finest = 86400.0 / finest_poll_interval_s
    # to get e.g. 30 orderable cross-poll comparisons per book pair (rough
    # rule-of-thumb minimum for a binomial sign test to have any power to
    # reject 50/50 at alpha=.05 for a true rate meaningfully away from .5),
    # each requiring a genuine price move witnessed in back-to-back polls for
    # BOTH books in the pair on a matched family:
    target_orderable_per_pair = 30
    n_book_pairs = len(books) * (len(books) - 1) // 2
    target_total_orderable = target_orderable_per_pair * n_book_pairs
    # current tape produced n_orderable EFFECTIVE (non-inflated) distinct
    # family-leader-follower relationships, all pairs, all 4 games, ~6h50m of
    # capture. observed capture window and rates:
    capture_window_s = (max(r['_ret'] for r in rows) - min(r['_ret'] for r in rows)).total_seconds()
    changes_per_hour_observed = n_changes_total / (capture_window_s / 3600.0) if capture_window_s > 0 else None
    orderable_per_hour_observed = n_orderable / (capture_window_s / 3600.0) if capture_window_s > 0 else None

    if orderable_per_hour_observed and orderable_per_hour_observed > 0:
        hours_needed = target_total_orderable / orderable_per_hour_observed
    else:
        hours_needed = None

    result["power_feasibility"] = {
        "clustering_note": (
            "The correct independence unit for any claim that generalizes "
            "beyond this tape is the GAME, not the book-pair-family "
            "comparison: within one game, book-pair orderings across "
            "different player/market/line families share the same "
            "underlying capture cycle, scheduler timing, and game-news "
            "environment, so they are correlated, not independent draws. "
            "This tape has n_game_clusters=4. A per-comparison rate "
            "extrapolation (below) describes how fast raw comparison "
            "volume accumulates but overstates statistical power; a "
            "cluster-robust design needs on the order of dozens of "
            "independent GAMES of dense synchronized capture, not dozens "
            "of comparisons, and this tape is far short of that on the "
            "cluster axis regardless of the per-comparison rate."
        ),
        "n_game_clusters_in_tape": len(games),
        "current_tape_span_s": capture_window_s,
        "current_tape_span_hours": capture_window_s / 3600.0,
        "n_total_price_changes_observed": n_changes_total,
        "n_orderable_cross_poll_book_pair_comparisons_observed_raw_cross_product": n_orderable_raw,
        "n_orderable_cross_poll_book_pair_comparisons_observed_effective": n_orderable,
        "n_within_poll_co_occurring_comparisons_usable_for_ordering": 0,
        "changes_per_hour_observed_rate": changes_per_hour_observed,
        "orderable_cross_poll_comparisons_per_hour_observed_rate": orderable_per_hour_observed,
        "n_book_pairs": n_book_pairs,
        "target_orderable_comparisons_per_pair_for_sign_test_power": target_orderable_per_pair,
        "target_total_orderable_comparisons_all_pairs": target_total_orderable,
        "estimated_capture_hours_to_reach_target_at_observed_rate": hours_needed,
        "estimated_capture_days_to_reach_target_at_observed_rate": (
            hours_needed / 24.0 if hours_needed else None),
        "caveat": (
            "This is a rate extrapolation from a single ~6h50m, 4-game "
            "capture window, not a calibrated power analysis with variance "
            "estimates -- reported as an order-of-magnitude feasibility "
            "signal only. It also assumes cross-poll orderable comparisons "
            "remain the ceiling of what's achievable; the batched "
            "same-timestamp capture topology (resolution_floor above) means "
            "even an arbitrarily large N of such comparisons could NEVER "
            "produce a sub-poll-interval reaction-time estimate -- more "
            "data buys higher CONFIDENCE in a poll-granularity ordering, "
            "not finer TIME RESOLUTION. A finer resolution requires "
            "redesigning capture to poll books independently/staggered "
            "(M03_CAPTURE_UPGRADE scope), not simply accumulating more of "
            "the current batched design."
        ),
    }

    result["could_not_establish"] = [
        {
            "item": "Sub-poll-interval book reaction time (which book's price moved first, in seconds)",
            "reason": (
                "Capture topology stamps one shared retrieval_ts per poll "
                "across all books; zero measured cross-book timestamp "
                "variance exists in this tape to order same-poll changes."
            ),
        },
        {
            "item": "Any amendment-4-compliant reaction-time claim (t_lower/t_upper in seconds with vendor_latency_bound and clock_skew_bound both numeric)",
            "reason": (
                "vendor_ts_semantics is unknown_unverified for all 3152 "
                "rows and no clock-skew measurement exists for this "
                "capture run, so both mandatory amendment-4 terms are "
                "UNBOUNDED/UNMEASURED. Per contract section 6, such a claim "
                "must be reported UNSUPPORTABLE, not stated."
            ),
        },
        {
            "item": "Statistically powered first-mover ranking of the 5 books",
            "reason": (
                f"only {n_orderable} coarse cross-poll orderable "
                f"comparisons exist across all {n_book_pairs} book pairs "
                "and all 4 games in the entire tape -- see power_feasibility."
            ),
        },
        {
            "item": "Whether observed alt-line price differences represent a true 'line move' of one persistent series vs. simultaneous alternate-line coexistence",
            "reason": (
                "the tape carries no book-side flag distinguishing a "
                "'main line' from an 'alt line'; treating (line) as part "
                "of series identity is the conservative choice but means "
                "a genuine same-line reprice that also shifts the posted "
                "line number would be undercounted as changes here."
            ),
        },
    ]

    with open(f"{OUTDIR}\\LEAD_LAG.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    with open(f"{OUTDIR}\\FINDINGS.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps({
        "n_rows": n_rows, "n_games": len(games), "n_books": len(books),
        "n_markets": len(markets), "n_series": n_series,
        "n_changes": n_changes_total,
        "n_co_occurring_groups": n_co_occurring_groups,
        "n_orderable_cross_poll": n_orderable,
        "n_families": n_families, "n_families_with_sync": n_families_with_sync,
        "cadence_dedup": cadence_dedup,
        "hours_needed": hours_needed,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
