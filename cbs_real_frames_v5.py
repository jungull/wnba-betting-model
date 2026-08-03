#!/usr/bin/env python3
"""cbs_real_frames_v5.py — `cbs_real_frames/5`: the v5 causal player fold.

**IT DOES NOT FIT, PREDICT OR SCORE.** No model, no coefficient, no accuracy figure, no error
figure, no comparison of any forecast to any outcome.

HOW THE FORK IS GUARANTEED MINIMAL
-----------------------------------
`build_player_frame_v5` is **generated at import time from
`inspect.getsource(cbs_real_frames_v3.build_player_frame)`** and five textual substitutions, each
asserted to match exactly once. The copy is therefore exact by construction and **cannot drift**:
if `/3` changes, either the substitution still applies to the new source or import fails loudly.
Nothing is transcribed by hand.

The five seams, and the authorised reason for each:

  1. INPUT          — read the enriched v5 contract instead of v4            (v5 schema)
  2. CARRIED COLS   — keep the tier, fit-eligibility and evidence columns    (tier policy)
  3. TRAIN FILTER   — the training frame is Tier A rows only                 (tier policy)
  4. UNIVERSE COLS  — the universe carries the tier columns                  (contract identity)
  5. SCOREABILITY   — p_active is scoreable on Tier A OR on an appearance    (v5 schema)

Every estimator, mask, tuning rule, calibration, availability gate, conditional history and
grouping rule is `/3`'s, untouched, because none of them is inside the diff.

THE HISTORY POLICY, STATED AT ITS ACTUAL WIDTH
-----------------------------------------------
`tier_a_target_fit_with_observed_history/1`. The causal history walk runs over **every tier**,
because a Tier B row that appeared is a real game the player played and, once it has occurred, it
is historically knowable and belongs in her later form estimates. Only the **training frame** is
restricted to Tier A.

That restriction is on TARGET LOSS, not on influence, and the difference is not cosmetic. An
observed Tier B game changes the EWMA features of later Tier A training rows, and those changed
features can change selected hyperparameters, fitted coefficients, calibration and every later
prediction. **That is indirect fitting influence and it is permitted and measured**, not denied —
see `experiments/player_program/register_tier_policy_erratum.py`.

`build_player_frame_v5(..., tier_b_history=False)` builds the attribution sensitivity in which
Tier B observations are withheld from the history walk. Its purpose is attribution, never
selection.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd

import cbs_provenance as _prov_v2
import cbs_real_frames_v2 as rf2
import cbs_real_frames_v3 as rf3

ADAPTER_ID = "cbs_real_frames/5"
SUPERSEDES = rf3.ADAPTER_ID
FOLD_RECEIPT_SCHEMA = "cbs_real_fold_receipt/5"

REPO_ROOT = Path(__file__).resolve().parent
V5_CONTRACT = "experiments/prediction_contract_v5/player_game_enriched.parquet"

RealFrameError = rf3.RealFrameError

#: v5 columns carried through the frame so the runner and the receipts can see the tier policy.
V5_CARRY = ("universe_tier", "evaluation_tier", "fit_eligible", "is_fallback",
            "candidate_source", "team_assignment_source", "team_assignment_confidence",
            "roster_evidence_regime", "candidate_evidence_time", "cutoff_source",
            "team_assignment_ambiguous", "history_admissible_from",
            "history_eligible_after_event", "n_prior_candidate_obligations",
            "n_prior_appearances", "n_prior_team_games", "era")

#: universe columns beyond `/3`'s identity set.
V5_UNIVERSE_CARRY = ("universe_tier", "evaluation_tier", "fit_eligible", "is_fallback")


def load_inputs_v5(root: Path | str = REPO_ROOT, *, require_attested: bool = True):
    """Read the ENRICHED v5 contract and the masters, in `/3`'s return shape.

    `require_attested` is honoured by hashing the v5 artifacts rather than by consulting the v4
    attestation set, which does not know about them. A missing artifact is a refusal.
    """
    root = Path(root)
    p = root / V5_CONTRACT
    if not p.exists():
        raise RealFrameError(
            f"the enriched v5 contract is absent at {p}; run prediction_contract_v5.py then "
            f"prediction_contract_v5_enrich.py first")
    pg = pd.read_parquet(p)
    tg = pd.read_parquet(root / "experiments" / "prediction_contract_v4" / "team_game.parquet")
    mp = pd.read_parquet(root / _prov_v2.MASTER_PLAYER)
    mt = pd.read_parquet(root / _prov_v2.MASTER_TEAM)
    for f in (pg, tg, mp, mt):
        f["game_date"] = pd.to_datetime(f["game_date"])
    if "pts" not in pg.columns and "points" in pg.columns:
        pg = pg.rename(columns={"points": "pts"})
    return pg, tg, mp, mt


# --------------------------------------------------------------------------
# the generated fork
# --------------------------------------------------------------------------

_SUBS: tuple[tuple[str, str, str], ...] = (
    (
        "input",
        "    pg, tg, mp, mt = load_inputs(root, require_attested=require_attested)",
        "    pg, tg, mp, mt = load_inputs_v5(root, require_attested=require_attested)",
    ),
    (
        "carried_columns",
        '        [c for c in ("contract_src_asof_roster", "contract_n_roster_games_consumed")\n'
        "         if c in pg.columns]",
        '        [c for c in ("contract_src_asof_roster", "contract_n_roster_games_consumed")\n'
        "         if c in pg.columns] + \\\n"
        "        [c for c in V5_CARRY if c in pg.columns]",
    ),
    (
        "train_filter",
        '    train = frame[frame["season"] < season].reset_index(drop=True)',
        '    train = frame[(frame["season"] < season)\n'
        '                  & frame["fit_eligible"].astype(bool)].reset_index(drop=True)',
    ),
    (
        "universe_columns",
        '    universe = src[list(PLAYER_UNIVERSE_IDENTITY) + ["appeared"]].copy()',
        "    universe = src[list(PLAYER_UNIVERSE_IDENTITY) + [\"appeared\"]\n"
        "                   + [c for c in V5_UNIVERSE_CARRY if c in src.columns]].copy()",
    ),
    (
        "scoreability",
        '        derived_sc = (universe["appeared"].astype(bool) if t != "p_active"\n'
        "                      else pd.Series(True, index=universe.index))",
        '        derived_sc = (universe["appeared"].astype(bool) if t != "p_active"\n'
        '                      else ((universe["universe_tier"] == "A")\n'
        '                            | universe["appeared"].astype(bool)))',
    ),
)


def _forked_source() -> tuple[str, dict]:
    """`/3`'s source with exactly the five seams applied, each asserted to match once."""
    src = inspect.getsource(rf3.build_player_frame)
    applied = {}
    for name, old, new in _SUBS:
        n = src.count(old)
        if n != 1:
            raise RealFrameError(
                f"the {name!r} seam matched {n} times in cbs_real_frames_v3.build_player_frame; "
                f"it must match exactly once. `/3` has changed and this fork must be re-derived "
                f"rather than silently re-applied.")
        src = src.replace(old, new)
        applied[name] = {"removed_lines": old.count("\n") + 1,
                         "added_lines": new.count("\n") + 1}
    src = src.replace("def build_player_frame(", "def build_player_frame_v5(", 1)
    return src, applied


_SRC, SEAMS_APPLIED = _forked_source()

#: The fork executes in `/3`'s own module namespace plus this module's overrides, so every name it
#: does not redefine resolves to the SAME OBJECT `/3` uses. Nothing is re-implemented.
_NS = dict(rf3.__dict__)
_NS.update({"load_inputs_v5": load_inputs_v5, "V5_CARRY": V5_CARRY,
            "V5_UNIVERSE_CARRY": V5_UNIVERSE_CARRY})
exec(compile(_SRC, f"<{ADAPTER_ID} generated from {rf3.ADAPTER_ID}>", "exec"), _NS)
_build_player_frame_v5 = _NS["build_player_frame_v5"]


def source_diff() -> dict:
    """The exact, checkable diff of this fork against the LIVE `/3` source."""
    import difflib
    a = inspect.getsource(rf3.build_player_frame).splitlines()
    b = _SRC.splitlines()
    diff = [ln for ln in difflib.unified_diff(a, b, "cbs_real_frames_v3.build_player_frame",
                                              "cbs_real_frames_v5.build_player_frame_v5",
                                              lineterm="", n=0)]
    changed = [ln for ln in diff if ln.startswith(("+", "-"))
               and not ln.startswith(("+++", "---"))]
    return {
        "adapter": ADAPTER_ID, "forked_from": f"{rf3.ADAPTER_ID}.build_player_frame",
        "generated_at_import_from_inspect_getsource": True,
        "n_seams": len(_SUBS),
        "seams": {name: {"reason": reason} for name, reason in (
            ("input", "v5 schema: read the enriched v5 contract"),
            ("carried_columns", "tier policy: carry tier and evidence columns"),
            ("train_filter", "tier policy: the training frame is Tier A only"),
            ("universe_columns", "contract identity: the universe carries tier columns"),
            ("scoreability", "v5 schema: p_active scoreable on Tier A or on an appearance"),
        )},
        "seams_applied": SEAMS_APPLIED,
        "n_changed_lines": len(changed),
        "changed_lines": changed,
        "unchanged": ("every estimator, mask, tuning rule, calibration, availability gate, "
                      "conditional history and grouping rule; none is inside the diff"),
        "name_resolution": ("the fork executes in cbs_real_frames_v3's own namespace, so every "
                            "name it does not redefine is the SAME OBJECT /3 uses"),
    }


def build_player_frame_v5(season: int, root: Path | str = REPO_ROOT, *,
                          require_attested: bool = True,
                          tier_b_history: bool = True) -> dict:
    """The v5 causal player fold.

    `tier_b_history=True` (the registered policy) runs the causal history walk over EVERY tier, so
    an observed Tier B game informs later form estimates. `tier_b_history=False` builds the
    ATTRIBUTION SENSITIVITY in which Tier B observations are withheld from the history walk. The
    sensitivity exists to attribute a difference, never to select a better result.
    """
    root = Path(root)
    if tier_b_history:
        out = _build_player_frame_v5(season, root, require_attested=require_attested)
        out["tier_b_history"] = True
    else:
        out = _build_sensitivity(season, root, require_attested=require_attested)
        out["tier_b_history"] = False
    out["adapter"] = ADAPTER_ID
    out["receipts"]["adapter"] = ADAPTER_ID
    out["receipts"]["supersedes"] = SUPERSEDES
    out["receipts"]["history_policy"] = (
        "tier_a_target_fit_with_observed_history/1 — only Tier A rows contribute TARGET LOSS; "
        "all cutoff-valid previously observed performances may contribute to later HISTORY "
        "features; indirect influence on later Tier A features is permitted and measured"
        if tier_b_history else
        "ATTRIBUTION SENSITIVITY — Tier B observations withheld from the history walk")
    return out


def _build_sensitivity(season: int, root: Path, *, require_attested: bool) -> dict:
    """Withhold Tier B rows from the history walk by withholding them from the source frame.

    Implemented by filtering the CONTRACT before the walk rather than by touching the walk, so the
    causal derivation is byte-identical to the primary build. The test frame is then re-widened to
    all tiers, because every obligation must still receive a forecast slot.
    """
    import cbs_obligation_key as obk

    full = _build_player_frame_v5(season, root, require_attested=require_attested)
    pg = pd.read_parquet(root / V5_CONTRACT)
    keep = set(pg.loc[pg["universe_tier"] == "A", "row_uid"])

    orig = load_inputs_v5
    try:
        def _tier_a_only(r, *, require_attested=True):
            p, t, m, mt_ = orig(r, require_attested=require_attested)
            return p[p["row_uid"].isin(keep)].copy(), t, m, mt_
        _NS["load_inputs_v5"] = _tier_a_only
        sens = _NS["build_player_frame_v5"](season, root, require_attested=require_attested)
    finally:
        _NS["load_inputs_v5"] = orig

    obk.assert_unique_canonical_keys(sens["train"], f"sensitivity train (season:{season})")
    sens["universe"] = full["universe"]
    sens["test_tier_a_only"] = True
    return sens


def main() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="cbs_real_frames/5")
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--diff", action="store_true")
    args = ap.parse_args()
    if args.diff:
        print(json.dumps(source_diff(), indent=2))
        return 0
    f = build_player_frame_v5(args.season, args.root)
    print(json.dumps({"season": args.season, "n_train": len(f["train"]),
                      "n_test": len(f["test"]), "n_universe": len(f["universe"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
