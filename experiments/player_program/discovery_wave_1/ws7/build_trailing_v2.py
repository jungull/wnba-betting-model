#!/usr/bin/env python3
"""build_trailing_v2.py -- leakage-free rebuild of the trailing role signal for ws7.

DEFECT BEING REPAIRED (coordinator amendment 2)
-----------------------------------------------
`turnover_p2_v1/turnover_role_context_features_v1.parquet` builds its prior-role columns by
iterating the REALISED box score (master_player filtered to minutes.notna()) and left-merging the
result onto the Tier A candidate universe. A candidate who never appeared has no box-score row,
so it receives NULL. The null pattern is therefore an EXACT did_appear indicator:
non-null = 27,351 = the appearers, null = 8,278 = the non-appearers, zero off-diagonal.

Standardise-then-fillna turns that null pattern into a constant column value for exactly the
non-appearers, which encodes a POST-CUTOFF OUTCOME into the design matrix.

THE REPAIR: the same EWMA machine (alpha 0.10, discounted cumulative sums, strictly prior games)
but state is READ for every Tier A candidate on every candidate date, not only for players who
turned out to appear. State is still UPDATED only from realised box scores, which is legitimate
-- those are prior games by the time they are read.

A player with no prior history now takes a DEFINED value (zero prior minutes, zero prior
attempts) rather than NULL. "No prior usage" is a legitimate pregame statement. "Did not appear"
is not.

The canonical artifact is NOT modified. This writes its own copy under the ws7 directory.
"""
from __future__ import annotations
import json, sys                                                                # noqa: E401
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import register_ws7 as R                                                        # noqa: E402

ALPHA = 0.10                 # matches INVOLVE_ALPHA in register_turnover_p2
SHRINK_K = R.INVOLVE_SHRINK_K
NOMINAL_ROTATION = 9.0       # frozen fallback for a team's very first game (no prior state)
OUT = HERE / "ws7_trailing_role_features_v2.parquet"


def main() -> int:
    C = pd.read_parquet(ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet",
                        columns=["game_id", "game_date", "season"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)

    box = pd.read_parquet(ROOT / "data/masters/master_player.parquet",
                          columns=["game_id", "team_id", "player_id", "minutes", "fga"])
    box["game_id"] = box["game_id"].astype(str)
    box = box[box["minutes"].notna()].merge(C[["game_id", "game_date"]], on="game_id", how="left")

    V1 = pd.read_parquet(PP / "turnover_p2_v1/turnover_role_context_features_v1.parquet")
    cand = V1[["game_id", "team_id", "player_id", "game_date",
               "proj_minutes_share", "projected_minutes"]].copy()

    # ---- one chronological pass over the UNION of box dates and candidate dates -------- #
    ewm_min, ewm_fga, ewm_tm_min, ewm_tm_fga = {}, {}, {}, {}
    recent_roster: dict = {}
    box_by_date = {d: sub for d, sub in box.groupby("game_date", sort=False)}
    cand_by_date = {d: sub for d, sub in cand.groupby("game_date", sort=False)}
    all_dates = sorted(set(box_by_date) | set(cand_by_date))

    rows = []
    for d in all_dates:
        # 1. READ state for every candidate on this date, BEFORE consuming the date's games
        cd = cand_by_date.get(d)
        if cd is not None:
            for r in cd.itertuples(index=False):
                tm_m = ewm_tm_min.get(r.team_id, 0.0)
                tm_f = ewm_tm_fga.get(r.team_id, 0.0)
                pm = ewm_min.get(r.player_id, 0.0)
                pf = ewm_fga.get(r.player_id, 0.0)
                rows.append({
                    "game_id": r.game_id, "team_id": r.team_id, "player_id": r.player_id,
                    "trailing_minutes_share_v2": (pm / tm_m) if tm_m > 0 else 1.0 / NOMINAL_ROTATION,
                    "offensive_involvement_proxy_v2": (pf + SHRINK_K / NOMINAL_ROTATION) / (tm_f + SHRINK_K),
                    "prior_support_v2": tm_f,
                    "player_prior_fga_v2": pf,
                    "player_prior_minutes_v2": pm,
                    "has_prior_history_v2": int(pm > 0 or pf > 0),
                })
        # 2. UPDATE state from this date's realised box scores
        bd = box_by_date.get(d)
        if bd is not None:
            for r in bd.itertuples(index=False):
                ewm_min[r.player_id] = (1 - ALPHA) * ewm_min.get(r.player_id, 0.0) + float(r.minutes or 0)
                ewm_fga[r.player_id] = (1 - ALPHA) * ewm_fga.get(r.player_id, 0.0) + float(r.fga or 0)
            for t, sub in bd.groupby("team_id"):
                ewm_tm_min[t] = (1 - ALPHA) * ewm_tm_min.get(t, 0.0) + float(sub["minutes"].sum())
                ewm_tm_fga[t] = (1 - ALPHA) * ewm_tm_fga.get(t, 0.0) + float(sub["fga"].sum())
                recent_roster.setdefault(t, []).append(set(sub["player_id"]))

    H = pd.DataFrame(rows)
    F = cand.merge(H, on=["game_id", "team_id", "player_id"], how="left")
    F["trailing_rotation_rank_v2"] = F.groupby(["game_id", "team_id"])[
        "trailing_minutes_share_v2"].rank(ascending=False, method="first")
    F["role_change_v2"] = F["proj_minutes_share"] - F["trailing_minutes_share_v2"]
    F["log1p_player_support_v2"] = np.log1p(np.clip(F["player_prior_fga_v2"], 0.0, None))

    # team-level displaced involvement, recomputed from the rebuilt involvement values
    inv_by_player = (H.sort_values("game_id").drop_duplicates("player_id")
                     .set_index("player_id")["offensive_involvement_proxy_v2"].to_dict())
    disp = {}
    for (gid, tid), sub in F.groupby(["game_id", "team_id"]):
        hist = set().union(*recent_roster.get(tid, [set()])[-10:]) if tid in recent_roster else set()
        missing = hist - set(sub["player_id"])
        disp[(gid, tid)] = float(sum(inv_by_player.get(p, 0.0) for p in missing)) if missing else 0.0
    F["displaced_involvement_v2"] = [disp.get((g, t), 0.0)
                                     for g, t in zip(F["game_id"], F["team_id"])]

    NEW = [c for c in F.columns if c.endswith("_v2")]
    nulls = {c: int(F[c].isna().sum()) for c in NEW}
    F.to_parquet(OUT, index=False)

    # ---- leakage receipt: prove the null pattern no longer tracks did_appear ---- #
    P1O = pd.read_parquet(PP / "turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet")
    chk = P1O[["game_id", "team_id", "player_id", "did_appear"]].merge(
        F[["game_id", "team_id", "player_id"] + NEW], on=["game_id", "team_id", "player_id"], how="left")
    v1chk = P1O[["game_id", "team_id", "player_id", "did_appear"]].merge(
        V1[["game_id", "team_id", "player_id", "trailing_minutes_share", "role_change",
            "offensive_involvement_proxy"]], on=["game_id", "team_id", "player_id"], how="left")

    def crosstab(df, col):
        n = df[col].isna()
        return {"null_and_did_appear": int((n & df["did_appear"]).sum()),
                "null_and_not_appear": int((n & ~df["did_appear"]).sum()),
                "nonnull_and_did_appear": int((~n & df["did_appear"]).sum()),
                "nonnull_and_not_appear": int((~n & ~df["did_appear"]).sum())}

    rec = {
        "schema": "ws7_trailing_rebuild_receipt/1",
        "defect": ("v1 prior-role columns were built by iterating the realised box score and "
                   "left-merging onto the candidate universe, so their null pattern is an exact "
                   "did_appear indicator -- post-cutoff outcome information"),
        "v1_crosstabs_null_vs_did_appear": {c: crosstab(v1chk, c) for c in
                                            ["trailing_minutes_share", "role_change",
                                             "offensive_involvement_proxy"]},
        "v2_crosstabs_null_vs_did_appear": {c: crosstab(chk, c) for c in NEW},
        "v2_null_counts": nulls,
        "rows": int(len(F)),
        "expected_rows": 35629,
        "alpha": ALPHA, "shrink_K": SHRINK_K,
        "first_game_fallback": (f"trailing_minutes_share = 1/{NOMINAL_ROTATION:.0f} when a team has "
                                "no prior state at all; the involvement proxy is already defined "
                                "at 1/9 in that case by its own shrinkage"),
        "state_update_rule": ("EWMA state is UPDATED only from realised box scores, which are "
                              "prior games by the time they are read; state is READ for every "
                              "Tier A candidate, appearer or not"),
        "n_candidates_without_prior_history": int((F["has_prior_history_v2"] == 0).sum()),
        "of_which_did_appear": int(chk.loc[chk["has_prior_history_v2"] == 0, "did_appear"].sum()),
    }
    (HERE / "TRAILING_REBUILD_RECEIPT.json").write_text(json.dumps(rec, indent=2, default=str),
                                                        encoding="utf-8")
    print(json.dumps(rec, indent=2, default=str)[:2600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
