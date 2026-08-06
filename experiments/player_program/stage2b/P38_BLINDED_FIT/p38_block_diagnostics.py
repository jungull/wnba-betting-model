#!/usr/bin/env python3
"""p38_block_diagnostics.py -- sealed diagnostics for the P25-blocked instances.

For every instance the frozen P25 offset-dependency guard blocked, re-invoke the guard
PER FOLD exactly as the frozen runner does (same wrapper, same argument pins), capture the
guard's complete machine-readable record for each fold, and record the structural facts
that explain the firing pattern:

  * whether the projection/offset is game-shared (both team-rows of a game carry one
    projection value), which makes the exact-determination tie groups game pairs;
  * which design columns are game-level (constant within every game cluster) -- any such
    column is constant within every projection tie group by construction;
  * which columns are fold-constant (structurally zero variance) inside card-deactivated /
    rule-collapsed folds that the runner's bundle loop still audits.

Output: SEALED_RESULTS/P38/<element>/BLOCK_DIAGNOSTICS.json (sealed; the full guard
records contain dependency diagnostics and are never printed). stdout carries finding
KINDS, FEATURE NAMES, FOLD IDS and structural counts only.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

import p38_driver as D
from p38_wrappers import FoldGovernor

os.environ["P38_UNSEALED"] = "1"
sys.path.insert(0, str(D.RUNNER_DIR))
import guard_harness as gh                     # noqa: E402
from runner_constants import INTERCEPT_COL     # noqa: E402

import p38_run_fleet as RF                     # noqa: E402

BLOCKED = ("A05", "A12", "A13", "A14", "A15", "A17", "A22")


def main():
    F, u, checks = D.build_universe()
    folds, _ = D.build_folds(F)
    archive, poss, lineup, prior, openers = D.build_archive_and_sources()

    # structural fact: the projection (and hence the offset) is game-shared or not
    proj_per_game = F.groupby("game_id")["projected_team_off_possessions"].nunique()
    game_shared = bool((proj_per_game == 1).all())
    n_distinct_proj = int(F["projected_team_off_possessions"].nunique())
    tie_struct = {"projection_game_shared_all_games": game_shared,
                  "n_games": int(F["game_id"].nunique()),
                  "n_distinct_projection_values": n_distinct_proj}
    print(json.dumps({"structural": tie_struct}))

    inv = [e for e in RF.build_inventory(F, folds, archive, poss, lineup, prior)
           if e["arm_code"] in BLOCKED]

    for entry in inv:
        key = entry["key"]
        governor = FoldGovernor(entry["module"], {}, entry.get("override"))
        final_fold = {"fold_id": "FINAL_ASSEMBLED_DESIGN",
                      "train_idx": np.arange(len(F)), "test_idx": np.empty(0, int)}
        per_fold = {}
        col_facts = {}
        for fold in list(folds) + [final_fold]:
            fid = str(fold["fold_id"])
            bundle = governor.build_design(fold, F)
            W = F.copy()
            for name, v in bundle["columns"].items():
                W[name] = np.asarray(v, float)
            tr = np.asarray(fold["train_idx"], int)
            W_tr = W.iloc[tr].reset_index(drop=True)
            cand = [c for c in bundle["treatment_cols"] if c != INTERCEPT_COL]
            nuis = [c for c in bundle["nuisance_cols"] if c != INTERCEPT_COL]
            # structural column facts on this fold's training rows
            for c in cand + nuis:
                v = W_tr[c].to_numpy(float)
                per_gid = pd.Series(v).groupby(W_tr["game_id"].to_numpy()).nunique()
                col_facts.setdefault(c, {})[fid] = {
                    "fold_constant": bool(np.nanstd(v) == 0.0),
                    "game_level_constant_within_every_cluster": bool((per_gid <= 1).all()),
                }
            try:
                rec = gh.p25_check(
                    W_tr, candidate_features=cand, nuisance_features=nuis,
                    preregistered_contrasts=governor.preregistered_contrasts(),
                    prereg_digest_expected=governor.prereg_digest_expected())
                per_fold[fid] = {"verdict": "PASS", "record": rec}
            except Exception as e:
                rec = getattr(e, "record", None)
                fired = []
                if isinstance(rec, dict):
                    fired = [{"kind": f.get("kind"), "feature": f.get("feature")}
                             for f in rec.get("blocking", [])]
                per_fold[fid] = {"verdict": "BLOCK", "fired": fired, "record": rec}
        out = {
            "schema": "p38_block_diagnostics/1",
            "element": key,
            "structural": tie_struct,
            "column_structural_facts": col_facts,
            "p25_per_fold": per_fold,
            "note": ("re-invocation of the frozen P25 wrapper with the runner's own "
                     "argument pins, per fold, for diagnosis of the sealed block; the "
                     "block verdict of record remains the runner's own (sidecar)"),
        }
        sha = RF.write_json(D.SEALED_P38 / key / "BLOCK_DIAGNOSTICS.json", out)
        summary = {fid: (v["verdict"] if v["verdict"] == "PASS"
                         else [(f["kind"], f["feature"]) for f in v["fired"]])
                   for fid, v in per_fold.items()}
        print(json.dumps({"element": key, "p25_per_fold_summary": summary,
                          "diagnostics_sha256": sha}, default=str))


if __name__ == "__main__":
    main()
