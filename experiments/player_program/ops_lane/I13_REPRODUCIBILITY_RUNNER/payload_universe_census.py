#!/usr/bin/env python3
"""payload_universe_census.py — the REAL recorded run this node reproduces.

A reproducibility runner demonstrated only on a toy payload proves that the runner can compare two
short strings. This payload is the real thing: it loads the frozen team-game possession universe
through the program's own loader, read-only, and emits two files.

    universe_census.json    structural facts: team-game rows, game clusters, cluster sizes, the
                            universe contract digests, and the exact bytes each artifact it read.
    cluster_bootstrap.csv   a SEEDED cluster bootstrap over game clusters.

WHY A BOOTSTRAP IS IN HERE AT ALL
---------------------------------
Without it the seed binding would be decorative: a payload with no stochastic step reproduces
whether or not the seed is honoured, so a runner that silently dropped the seed would still show
green. The bootstrap makes the seed LOAD-BEARING — change the recorded seed and the output bytes
must move, which is exactly what this node's tests assert.

WHAT THE BOOTSTRAP IS AND IS NOT
--------------------------------
It resamples GAME CLUSTERS, never rows, so a game is never split across a draw. The statistic is
the mean of the realised regulation-equivalent offensive possession column, read as a column of
numbers to size a sampling distribution. No model is fitted. No arm is scored. No prediction is
contrasted with an outcome. Nothing here is a performance claim about the incumbent or about any
challenger, and nothing here is read from any sealed result.

DETERMINISM RULES OBSERVED HERE
-------------------------------
* no wall-clock, no hostname, no pid, no absolute path in any output;
* JSON with sorted keys and a fixed float format; CSV with an explicit format string and "\\n";
* floats rounded to a fixed number of decimals BEFORE formatting, so the emitted text cannot
  depend on the last bit of an accumulation order.

Run (normally through ``repro_runner``, which binds the seed):
    python payload_universe_census.py --out <dir>
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse                                                               # noqa: E402
import hashlib                                                                # noqa: E402
import json                                                                   # noqa: E402
import os                                                                     # noqa: E402
from pathlib import Path                                                      # noqa: E402

import numpy as np                                                            # noqa: E402
import pandas as pd                                                           # noqa: E402

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]                       # experiments/player_program
ROOT = HERE.parents[3]                          # repository worktree root
sys.path.insert(0, str(PROGRAM))

N_DRAWS = 500
FLOAT_DECIMALS = 8


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _r(x: float) -> float:
    return float(np.round(float(x), FLOAT_DECIMALS))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    seed_raw = os.environ.get("REPRO_SEED")
    if seed_raw is None:
        sys.stderr.write("payload: REPRO_SEED is not set; this payload refuses to run unseeded, "
                         "because an unseeded run cannot be reproduced from a manifest\n")
        return 2
    seed = int(seed_raw)

    import possession_features as pf             # READ-ONLY loader; writes nothing

    prior = PROGRAM / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
    poss = PROGRAM / "possessions_v2" / "possessions_raw_v2.parquet"

    u = pf.load_universe(prior_path=prior, possessions_path=poss)
    F = u.frame
    target = F[pf.TARGET_COLUMN].to_numpy(dtype=float)

    games = F["game_id"].astype(str).to_numpy()
    order = np.argsort(games, kind="stable")     # stable: the draw cannot depend on input order
    uniq, first = np.unique(games[order], return_index=True)
    counts = pd.Series(games).value_counts()

    census = {
        "schema": "i13_universe_census/1",
        "universe_contract_id": u.contract.get("universe_contract_id"),
        "row_universe_digest": u.contract.get("row_universe_digest"),
        "team_game_rows": int(len(F)),
        "game_clusters": int(len(uniq)),
        "cluster_size_distribution": {str(k): int(v) for k, v in
                                      sorted(counts.value_counts().items())},
        "columns": sorted(map(str, F.columns)),
        "target_column": pf.TARGET_COLUMN,
        "offset_column": pf.OFFSET_COLUMN,
        "target_summary": {
            "n": int(np.isfinite(target).sum()),
            "mean": _r(target.mean()),
            "std_ddof1": _r(target.std(ddof=1)),
            "min": _r(target.min()),
            "max": _r(target.max()),
        },
        "seasons": sorted(map(str, pd.unique(F["season"]))),
        "artifacts_read": {
            "team_possession_prior_v1.parquet": _sha256(prior),
            "possessions_raw_v2.parquet": _sha256(poss),
        },
        "note": ("structural facts about the row universe plus a summary of the target column "
                 "read as numbers. No model, no arm, no scoring, no comparison."),
    }
    with (out / "universe_census.json").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(census, sort_keys=True, ensure_ascii=True, indent=2,
                            allow_nan=False) + "\n")

    # ---- seeded CLUSTER bootstrap; a game is never split across a draw --------------- #
    rng = np.random.default_rng(seed)
    idx_by_cluster = np.split(order, first[1:])
    n_clusters = len(idx_by_cluster)
    lines = ["draw,seed,n_clusters_drawn,n_rows_drawn,mean_target"]
    for d in range(N_DRAWS):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        rows = np.concatenate([idx_by_cluster[i] for i in pick])
        lines.append(f"{d},{seed},{n_clusters},{len(rows)},"
                     f"{_r(target[rows].mean()):.{FLOAT_DECIMALS}f}")
    with (out / "cluster_bootstrap.csv").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"rows={len(F)} clusters={n_clusters} seed={seed} draws={N_DRAWS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
