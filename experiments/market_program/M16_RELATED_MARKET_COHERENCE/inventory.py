"""
M16_RELATED_MARKET_COHERENCE - Step 1: inventory.

Reads (read-only, from the DATA worktree):
  data/market_snapshots/snapshots.csv                          (live ladder)
  data/market_snapshots/historical/featured_backfill.jsonl      (game-market archive: h2h/spreads/totals)
  data/market_snapshots/historical/props_discovery.jsonl        (player-prop archive)

Writes: inventory.json into this node's own directory.
No third-party libraries used (stdlib only) because scipy/pandas/numpy are not
installed in this environment (verified: `python -c "import pandas"` -> ModuleNotFoundError).
"""
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

DATA_ROOT = Path(r"C:\Users\jgallagher\wnba-betting-model\data\market_snapshots")
OUT_DIR = Path(__file__).parent

SNAPSHOTS_CSV = DATA_ROOT / "snapshots.csv"
FEATURED_JSONL = DATA_ROOT / "historical" / "featured_backfill.jsonl"
PROPS_JSONL = DATA_ROOT / "historical" / "props_discovery.jsonl"

result = {}

# ---------------------------------------------------------------------------
# 1. snapshots.csv (live ladder)
# ---------------------------------------------------------------------------
with open(SNAPSHOTS_CSV, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

n_rows = len(rows)
books = Counter(r["book"] for r in rows)
markets = Counter(r["market"] for r in rows)
market_status = Counter(r["market_status"] for r in rows)
vendor_ts_semantics = Counter(r["vendor_ts_semantics"] for r in rows)
game_ids = set(r["game_id"] for r in rows)
vendor_ts_all = sorted(r["vendor_ts"] for r in rows if r["vendor_ts"])
retrieval_ts_all = sorted(r["retrieval_ts"] for r in rows if r["retrieval_ts"])

# classify market family
def market_family(m):
    if m == "h2h":
        return "moneyline"
    if m == "spreads":
        return "spread"
    if m == "totals":
        return "total"
    if m.startswith("player_"):
        return "player_prop"
    return "other"

fam_counter = Counter(market_family(r["market"]) for r in rows)

result["snapshots_csv"] = {
    "path": str(SNAPSHOTS_CSV),
    "n_rows": n_rows,
    "n_distinct_games": len(game_ids),
    "n_distinct_books": len(books),
    "books": dict(books),
    "n_distinct_markets_raw": len(markets),
    "markets_raw": dict(markets),
    "market_family_counts": dict(fam_counter),
    "market_status_counts": dict(market_status),
    "vendor_ts_semantics_counts": dict(vendor_ts_semantics),
    "vendor_ts_min": vendor_ts_all[0] if vendor_ts_all else None,
    "vendor_ts_max": vendor_ts_all[-1] if vendor_ts_all else None,
    "retrieval_ts_min": retrieval_ts_all[0] if retrieval_ts_all else None,
    "retrieval_ts_max": retrieval_ts_all[-1] if retrieval_ts_all else None,
}

# ---------------------------------------------------------------------------
# Working-universe check on snapshots.csv: for each (game_id, book, retrieval batch
# instant), do we have h2h AND spreads AND totals simultaneously?
# We use snapshot_id's shared retrieval_ts (to the second) as the "same snapshot
# instant" key, since retrieval_ts is when OUR system captured the batch, which is
# the only instant we actually control/witnessed (T0-ish), separate from vendor_ts
# (T1, vendor-asserted).
# ---------------------------------------------------------------------------
by_instant = defaultdict(dict)  # (game_id, book, retrieval_ts) -> {family: True}
for r in rows:
    fam = market_family(r["market"])
    if fam in ("moneyline", "spread", "total"):
        key = (r["game_id"], r["book"], r["retrieval_ts"])
        by_instant[key][fam] = True

triples = [k for k, v in by_instant.items() if len(v) == 3]
pairs_only = [k for k, v in by_instant.items() if len(v) == 2]
singles_only = [k for k, v in by_instant.items() if len(v) == 1]

result["snapshots_csv"]["game_level_market_instants"] = {
    "definition": "keyed on (game_id, book, retrieval_ts-to-the-second)",
    "n_instants_with_all_3_families": len(triples),
    "n_instants_with_exactly_2_families": len(pairs_only),
    "n_instants_with_exactly_1_family": len(singles_only),
    "n_distinct_games_in_triples": len(set(k[0] for k in triples)),
    "n_distinct_books_in_triples": len(set(k[1] for k in triples)),
    "sample_triple_keys": [list(k) for k in triples[:10]],
}

# ---------------------------------------------------------------------------
# 2. featured_backfill.jsonl (historical game-market archive)
# ---------------------------------------------------------------------------
n_batches = 0
n_events_total = 0
distinct_event_ids = set()
distinct_books_hist = Counter()
distinct_markets_hist = Counter()
requested_ts_list = []
vendor_snapshot_ts_list = []
provenance_classes = Counter()
vendor_ts_semantics_hist = Counter()
commence_times = []

# working-universe accumulator: for each (event_id, book, batch requested_ts) track which
# of h2h/spreads/totals markets are present
hist_by_instant = defaultdict(dict)

with open(FEATURED_JSONL, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        n_batches += 1
        rec = json.loads(line)
        requested_ts_list.append(rec.get("requested_ts"))
        vendor_snapshot_ts_list.append(rec.get("vendor_snapshot_ts"))
        provenance_classes[rec.get("provenance_class")] += 1
        vendor_ts_semantics_hist[rec.get("vendor_ts_semantics")] += 1
        payload = rec.get("payload") or []
        n_events_total += len(payload)
        for ev in payload:
            eid = ev.get("id")
            distinct_event_ids.add(eid)
            commence_times.append(ev.get("commence_time"))
            for bm in ev.get("bookmakers", []):
                bkey = bm.get("key")
                distinct_books_hist[bkey] += 1
                fams_present = set()
                for mkt in bm.get("markets", []):
                    mkey = mkt.get("key")
                    distinct_markets_hist[mkey] += 1
                    fams_present.add(mkey)
                instant_key = (eid, bkey, rec.get("requested_ts"))
                for fam in fams_present:
                    hist_by_instant[instant_key][fam] = True

hist_triples = [k for k, v in hist_by_instant.items() if {"h2h", "spreads", "totals"} <= set(v.keys())]

result["featured_backfill_jsonl"] = {
    "path": str(FEATURED_JSONL),
    "n_batch_records": n_batches,
    "n_event_rows_total_incl_duplicates_across_batches": n_events_total,
    "n_distinct_event_ids": len(distinct_event_ids),
    "requested_ts_min": min(t for t in requested_ts_list if t) if requested_ts_list else None,
    "requested_ts_max": max(t for t in requested_ts_list if t) if requested_ts_list else None,
    "commence_time_min": min(t for t in commence_times if t) if commence_times else None,
    "commence_time_max": max(t for t in commence_times if t) if commence_times else None,
    "provenance_class_counts": dict(provenance_classes),
    "vendor_ts_semantics_counts": dict(vendor_ts_semantics_hist),
    "n_distinct_books": len(distinct_books_hist),
    "books_by_bookmaker_appearance_count": dict(distinct_books_hist.most_common()),
    "markets_by_appearance_count": dict(distinct_markets_hist),
    "game_level_market_instants": {
        "definition": "keyed on (event_id, book, batch requested_ts) -- ALL markets returned in the SAME API poll for that event+book share one requested_ts, so this is the 'same snapshot instant' key for the archive",
        "n_distinct_event_book_instant_keys": len(hist_by_instant),
        "n_instants_with_all_3_families_h2h_spreads_totals": len(hist_triples),
        "n_distinct_events_in_triples": len(set(k[0] for k in hist_triples)),
        "n_distinct_books_in_triples": len(set(k[1] for k in hist_triples)),
    },
}

# ---------------------------------------------------------------------------
# 3. props_discovery.jsonl (historical player-prop archive)
# ---------------------------------------------------------------------------
n_batches_p = 0
n_bookmakers_total = 0
n_nonempty_payload = 0
n_null_payload = 0
distinct_event_ids_p = set()
provenance_classes_p = Counter()

with open(PROPS_JSONL, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        n_batches_p += 1
        rec = json.loads(line)
        provenance_classes_p[rec.get("provenance_class")] += 1
        distinct_event_ids_p.add(rec.get("event_id"))
        nb = rec.get("n_bookmakers", 0)
        n_bookmakers_total += nb or 0
        if rec.get("payload") is None:
            n_null_payload += 1
        else:
            n_nonempty_payload += 1

result["props_discovery_jsonl"] = {
    "path": str(PROPS_JSONL),
    "n_batch_records": n_batches_p,
    "n_distinct_event_ids": len(distinct_event_ids_p),
    "n_records_with_null_payload": n_null_payload,
    "n_records_with_nonempty_payload": n_nonempty_payload,
    "sum_n_bookmakers_field": n_bookmakers_total,
    "provenance_class_counts": dict(provenance_classes_p),
    "note": "This archive targets player props (n_bookmakers mostly 0/empty in sampled rows), not moneyline/spread/total; kept separate from the game-market coherence universe.",
}

out_path = OUT_DIR / "inventory.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, default=str)

print(json.dumps(result, indent=2, default=str)[:3000])
print("...")
print("WROTE", out_path)
