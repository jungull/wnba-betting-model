"""Measure the observable footprint of D-c in the two hash chains.

READ-ONLY. Reads ONLY chain metadata fields (record_idx, game_id,
forecast_cutoff, decision_time_label, logged_at_utc, model_version_hash) and
the two prediction fields needed to tell a served forecast from a NO_FORECAST
record. It never reads a prediction value, an outcome, or anything comparative,
so it cannot constitute performance peeking.

Run:  python experiments/player_program/ops_lane/O12_PER_GAME_EXECUTION_SCOPE/measure_chain_scope.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHAINS = {
    "official": REPO / "forecasts" / "forecast_log.jsonl",
    "scratch": REPO / "experiments" / "forecast_dryrun" / "scratch_chain.jsonl",
}


def load(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def summarise(name: str, recs: list[dict]) -> dict:
    cutoffs = sorted({r["forecast_cutoff"] for r in recs})
    games = sorted({r["game_id"] for r in recs})
    by_game_label = Counter((r["game_id"], r["decision_time_label"]) for r in recs)
    by_cutoff = defaultdict(set)
    for r in recs:
        by_cutoff[r["forecast_cutoff"]].add(r["game_id"])
    # cutoff second-of-minute distribution: a scheduler firing "at now" lands on
    # arbitrary sub-minute instants; a cutoff supplied by an obligation is round.
    round_minute = sum(1 for c in cutoffs if c[17:19] == "00" and "." not in c)
    statuses = Counter(
        (r.get("core_only_prediction") or {}).get("status", "FORECAST") for r in recs
    )
    labels = Counter(r["decision_time_label"] for r in recs)
    dup_key = Counter(
        (r["game_id"], r["forecast_cutoff"], r["model_version_hash"]) for r in recs
    )
    # the proposed obligation key: forecast_cutoff (a wall-clock instant) is
    # replaced by decision_time_label (the contract obligation the run served).
    obl_key = Counter(
        (r["game_id"], r["decision_time_label"], r["model_version_hash"]) for r in recs
    )
    return {
        "n_repeat_servings_under_shipped_key": sum(v - 1 for v in dup_key.values()),
        "n_repeat_servings_under_obligation_key": sum(v - 1 for v in obl_key.values()),
        "repeat_obligations": sorted(
            [list(k) for k, v in obl_key.items() if v > 1]
        ),
        "n_model_version_hashes": len({r["model_version_hash"] for r in recs}),
        "chain": name,
        "n_records": len(recs),
        "n_distinct_games": len(games),
        "n_distinct_cutoffs": len(cutoffs),
        "n_cutoffs_on_a_round_second": round_minute,
        "records_per_cutoff_min": min((len(v) for v in by_cutoff.values()), default=0),
        "records_per_cutoff_max": max((len(v) for v in by_cutoff.values()), default=0),
        "max_records_for_one_game_label_pair": max(by_game_label.values(), default=0),
        "n_game_label_pairs_with_more_than_one_record": sum(
            1 for v in by_game_label.values() if v > 1
        ),
        "n_duplicate_key_collisions": sum(1 for v in dup_key.values() if v > 1),
        "label_counts": dict(labels),
        "status_counts": dict(statuses),
        "first_cutoff": cutoffs[0] if cutoffs else None,
        "last_cutoff": cutoffs[-1] if cutoffs else None,
    }


def main() -> int:
    out = {}
    for name, path in CHAINS.items():
        recs = load(path)
        s = summarise(name, recs)
        s["path"] = str(path)
        s["exists"] = path.exists()
        out[name] = s
    print(json.dumps(out, indent=2, sort_keys=True))
    dest = Path(__file__).with_name("chain_scope_measurements.json")
    dest.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
