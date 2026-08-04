#!/usr/bin/env python3
"""build_ws5_features.py — the six frozen ws5 opportunity proxies, strictly prior games only.

Mirrors the chronological forward pass in run_turnover_p2.py: all EWMA state is SNAPSHOT at the
start of each game DATE and only consumed afterwards, so same-day games cannot see each other and
no row can ever see itself.

Because TURNOVERS sit inside five of the six proxies and turnovers are also the regression target,
this module ships an INDEPENDENT recomputation probe (`--probe N`) that rebuilds sampled rows from
a plain `game_date < target_date` filter and asserts equality.

Reads only; writes `ws5_opportunity_proxy_features_v1.parquet` and `WS5_FEATURE_VALIDATION.json`.
"""
from __future__ import annotations
import argparse, hashlib, json, sys                                            # noqa: E401
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]                      # experiments/player_program
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from freeze_ws5 import (ALPHA_LONG, ALPHA_SHORT, FT_TRIP_WEIGHT, PER36_SHRINK_K_MIN,  # noqa: E402
                        SHRINK_K, SHRINK_TARGET_SHARE)

PROXIES = ["x1_fga_share", "x2_pe_per36", "x3_pe_share", "x4_pe_share_delta",
           "x5_involvement_rank", "x6_responsibility_share"]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_box() -> pd.DataFrame:
    """Played rows only, with the frozen play-ending quantity attached."""
    box = pd.read_parquet(ROOT / "data/masters/master_player.parquet",
                          columns=["game_id", "team_id", "player_id", "game_date", "minutes",
                                   "fga", "fta", "tov"])
    box["game_id"] = box["game_id"].astype(str)
    box["game_date"] = pd.to_datetime(box["game_date"])      # master stores it as a string
    box = box[box["minutes"].notna()].copy()
    for c in ("fga", "fta", "tov", "minutes"):
        box[c] = box[c].astype(float).fillna(0.0)
    box["pe"] = box["fga"] + FT_TRIP_WEIGHT * box["fta"] + box["tov"]
    return box.sort_values(["game_date", "game_id"]).reset_index(drop=True)


def stream_history(box: pd.DataFrame, keys: pd.DataFrame) -> pd.DataFrame:
    """Single forward pass. `keys` carries every (game_id, team_id, player_id, game_date) that needs
    a snapshot -- the union of Tier A candidates and realised participants."""
    # long-run (alpha=0.10) player state
    pL_pe, pL_min, pL_fga = {}, {}, {}
    tL_pe, tL_fga = {}, {}
    pS_pe, tS_pe = {}, {}                      # short-run (alpha=0.35)
    lg_pe, lg_min = 0.0, 0.0                   # league-to-date, alpha=0.10

    need = keys.groupby("game_date", sort=True)
    play = {d: g for d, g in box.groupby("game_date", sort=True)}
    all_dates = sorted(set(keys["game_date"].unique()) | set(play.keys()))

    rows: list[dict] = []
    for d in all_dates:
        # ---- SNAPSHOT: state here reflects games strictly BEFORE date d -------------- #
        if d in need.groups:
            day = need.get_group(d)
            r_lg = (lg_pe / lg_min) if lg_min > 0 else np.nan
            for r in day.itertuples(index=False):
                tf = tL_fga.get(r.team_id, 0.0)
                tp = tL_pe.get(r.team_id, 0.0)
                tps = tS_pe.get(r.team_id, 0.0)
                pf = pL_fga.get(r.player_id, 0.0)
                pp = pL_pe.get(r.player_id, 0.0)
                pps = pS_pe.get(r.player_id, 0.0)
                pm = pL_min.get(r.player_id, 0.0)
                x1 = ((pf + SHRINK_K * SHRINK_TARGET_SHARE) / (tf + SHRINK_K)) if tf > 0 else np.nan
                x3 = ((pp + SHRINK_K * SHRINK_TARGET_SHARE) / (tp + SHRINK_K)) if tp > 0 else np.nan
                x3s = ((pps + SHRINK_K * SHRINK_TARGET_SHARE) / (tps + SHRINK_K)) if tps > 0 else np.nan
                x2 = (36.0 * (pp + PER36_SHRINK_K_MIN * r_lg) / (pm + PER36_SHRINK_K_MIN)) \
                    if (lg_min > 0) else np.nan
                rows.append({"game_id": r.game_id, "team_id": r.team_id, "player_id": r.player_id,
                             "x1_fga_share": x1, "x2_pe_per36": x2, "x3_pe_share": x3,
                             "x4_pe_share_delta": (x3s - x3) if np.isfinite(x3s) and np.isfinite(x3)
                             else np.nan,
                             "_team_prior_pe": tp, "_team_prior_fga": tf,
                             "_player_prior_min": pm})
        # ---- CONSUME date d ---------------------------------------------------------- #
        if d in play:
            day = play[d]
            for r in day.itertuples(index=False):
                pL_pe[r.player_id] = (1 - ALPHA_LONG) * pL_pe.get(r.player_id, 0.0) + r.pe
                pL_min[r.player_id] = (1 - ALPHA_LONG) * pL_min.get(r.player_id, 0.0) + r.minutes
                pL_fga[r.player_id] = (1 - ALPHA_LONG) * pL_fga.get(r.player_id, 0.0) + r.fga
                pS_pe[r.player_id] = (1 - ALPHA_SHORT) * pS_pe.get(r.player_id, 0.0) + r.pe
            for t, sub in day.groupby("team_id"):
                tL_pe[t] = (1 - ALPHA_LONG) * tL_pe.get(t, 0.0) + float(sub["pe"].sum())
                tL_fga[t] = (1 - ALPHA_LONG) * tL_fga.get(t, 0.0) + float(sub["fga"].sum())
                tS_pe[t] = (1 - ALPHA_SHORT) * tS_pe.get(t, 0.0) + float(sub["pe"].sum())
            lg_pe = (1 - ALPHA_LONG) * lg_pe + float(day["pe"].sum())
            lg_min = (1 - ALPHA_LONG) * lg_min + float(day["minutes"].sum())
    return pd.DataFrame(rows)


def independent_recompute(box: pd.DataFrame, gid: str, tid, pid, gdate) -> dict:
    """Rebuild x1/x2/x3/x4 for ONE row from a plain strictly-prior filter. No streaming state.

    The decay CADENCE must match the streamer exactly, and the streamer inherits P2's convention:
      * player state decays once per prior ROW for that player,
      * team state decays once per prior (date, team) group,
      * league state decays once per prior date on which any game was played.
    A probe that assumed a single global cadence is what flagged this on the first run.
    """
    prior = box[box["game_date"] < gdate]
    if prior.empty:
        return {k: np.nan for k in ("x1_fga_share", "x2_pe_per36", "x3_pe_share", "x4_pe_share_delta")}

    def ew_rows(sub: pd.DataFrame, col: str, alpha: float) -> float:
        """one decay step per row, in the streamer's (game_date, game_id) order"""
        acc = 0.0
        for v in sub.sort_values(["game_date", "game_id"])[col].to_numpy(float):
            acc = (1 - alpha) * acc + v
        return acc

    def ew_days(sub: pd.DataFrame, col: str, alpha: float) -> float:
        """one decay step per distinct date present in `sub`, value = that date's sum"""
        acc = 0.0
        for _, v in sub.groupby("game_date")[col].sum().sort_index().items():
            acc = (1 - alpha) * acc + float(v)
        return acc

    pl = prior[prior["player_id"] == pid]
    tm = prior[prior["team_id"] == tid]
    pf, pp, pm = ew_rows(pl, "fga", ALPHA_LONG), ew_rows(pl, "pe", ALPHA_LONG), \
        ew_rows(pl, "minutes", ALPHA_LONG)
    pps = ew_rows(pl, "pe", ALPHA_SHORT)
    tf, tp = ew_days(tm, "fga", ALPHA_LONG), ew_days(tm, "pe", ALPHA_LONG)
    tps = ew_days(tm, "pe", ALPHA_SHORT)
    lgp, lgm = ew_days(prior, "pe", ALPHA_LONG), ew_days(prior, "minutes", ALPHA_LONG)
    r_lg = (lgp / lgm) if lgm > 0 else np.nan
    x1 = ((pf + SHRINK_K * SHRINK_TARGET_SHARE) / (tf + SHRINK_K)) if tf > 0 else np.nan
    x3 = ((pp + SHRINK_K * SHRINK_TARGET_SHARE) / (tp + SHRINK_K)) if tp > 0 else np.nan
    x3s = ((pps + SHRINK_K * SHRINK_TARGET_SHARE) / (tps + SHRINK_K)) if tps > 0 else np.nan
    x2 = (36.0 * (pp + PER36_SHRINK_K_MIN * r_lg) / (pm + PER36_SHRINK_K_MIN)) if lgm > 0 else np.nan
    return {"x1_fga_share": x1, "x2_pe_per36": x2, "x3_pe_share": x3,
            "x4_pe_share_delta": (x3s - x3) if np.isfinite(x3s) and np.isfinite(x3) else np.nan}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", type=int, default=250, help="rows for the independent leakage probe")
    a = ap.parse_args()
    OUT = HERE
    box = load_box()

    PX = pd.read_parquet(PP / "projected_exposure_v1/projected_player_possessions_v1.parquet",
                         columns=["game_id", "team_id", "player_id", "game_date", "season",
                                  "forecast_cutoff", "regime"])
    PX = PX[PX["regime"] == "tier_a_only"].drop(columns="regime").copy()
    PX["game_id"] = PX["game_id"].astype(str)
    PX["is_tier_a_candidate"] = True

    # realised participants that are NOT Tier A candidates still need x1..x4 for the intrinsic track
    I = pd.read_parquet(PP / "turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet",
                        columns=["game_id", "team_id", "player_id", "game_date", "season"])
    I["game_id"] = I["game_id"].astype(str)
    key = ["game_id", "team_id", "player_id"]
    extra = I.merge(PX[key + ["is_tier_a_candidate"]], on=key, how="left")
    extra = extra[extra["is_tier_a_candidate"].isna()].drop(columns="is_tier_a_candidate")
    extra["forecast_cutoff"] = pd.NaT
    extra["is_tier_a_candidate"] = False
    keys = pd.concat([PX, extra], ignore_index=True).drop_duplicates(key)

    H = stream_history(box, keys[key + ["game_date"]])
    F = keys.merge(H, on=key, how="left")

    # x5 / x6 are defined ONLY over the Tier A projected candidate set for the team-game
    cand = F["is_tier_a_candidate"].to_numpy(bool)
    Fc = F[cand].copy()
    Fc["x5_involvement_rank"] = Fc.groupby(["game_id", "team_id"])["x3_pe_share"].rank(
        ascending=False, method="first")
    den = Fc.groupby(["game_id", "team_id"])["x3_pe_share"].transform("sum")
    Fc["x6_responsibility_share"] = np.where(den > 0, Fc["x3_pe_share"] / den, np.nan)
    F = F.merge(Fc[key + ["x5_involvement_rank", "x6_responsibility_share"]], on=key, how="left")
    F["decision_time_label"] = "pregame_cutoff"

    # ---------------- leakage probe: independent strictly-prior recomputation ------------- #
    rng = np.random.default_rng(20260730)
    samp = F[F["x3_pe_share"].notna()].sample(min(a.probe, int(F["x3_pe_share"].notna().sum())),
                                              random_state=20260730)
    mism, checked = [], 0
    for r in samp.itertuples(index=False):
        exp = independent_recompute(box, r.game_id, r.team_id, r.player_id, r.game_date)
        for k, v in exp.items():
            got = getattr(r, k)
            checked += 1
            if not (np.isnan(v) and np.isnan(got)) and abs(float(v) - float(got)) > 1e-9:
                mism.append({"game_id": r.game_id, "player_id": int(r.player_id), "feature": k,
                             "streamed": float(got), "independent": float(v)})
    probe = {"rows_sampled": int(len(samp)), "values_checked": checked,
             "mismatches": len(mism), "examples": mism[:5],
             "method": ("each sampled row rebuilt from a plain `game_date < target_date` filter "
                        "with no streaming state; exact equality required"),
             "passed": len(mism) == 0}

    # ---------------- shift detector: proxy vs the SAME-GAME quantity --------------------- #
    same = box[key + ["pe", "fga", "tov"]].rename(
        columns={"pe": "_same_game_pe", "fga": "_same_game_fga", "tov": "_same_game_tov"})
    S = F.merge(same, on=key, how="left")
    shift = {}
    for p in PROXIES:
        row = {}
        for c in ("_same_game_pe", "_same_game_fga", "_same_game_tov"):
            m = S[p].notna() & S[c].notna()
            row[c.replace("_same_game_", "corr_same_game_")] = (
                round(float(np.corrcoef(S.loc[m, p], S.loc[m, c])[0, 1]), 4) if m.sum() > 10 else None)
        shift[p] = row

    F.to_parquet(OUT / "ws5_opportunity_proxy_features_v1.parquet", index=False)
    cov = {p: {"non_null": int(F[p].notna().sum()), "null": int(F[p].isna().sum()),
               "mean": float(F[p].mean()), "std": float(F[p].std()),
               "min": float(F[p].min()), "max": float(F[p].max())} for p in PROXIES}
    val = {
        "artifact": "ws5_opportunity_proxy_features_v1",
        "grain": ["game_id", "team_id", "player_id", "decision_time_label"],
        "rows": int(len(F)),
        "unique_grain": bool(not F.duplicated(key + ["decision_time_label"]).any()),
        "tier_a_candidate_rows": int(F["is_tier_a_candidate"].sum()),
        "realised_non_candidate_rows": int((~F["is_tier_a_candidate"]).sum()),
        "coverage": cov,
        "correlations": F[PROXIES].corr().round(4).to_dict(),
        "chronological_isolation": (
            "one forward pass; EWMA state is snapshot at the START of each game DATE and the date's "
            "games are consumed only afterwards, so no row sees itself and same-day games cannot "
            "see each other"),
        "independent_recomputation_probe": probe,
        "same_game_shift_detector": shift,
        "null_policy": "PRESERVE NULLS; no back-fill in the artifact",
        "null_reasons": {
            "x1/x3/x4": "team has zero prior EWMA support (no prior games at all)",
            "x2": "league has zero prior minutes (first game date only)",
            "x5/x6": "row is a realised participant that was NOT a Tier A projected candidate",
        },
        "no_target_game_quantities": True,
        "does_not_observe": ["touches", "passes", "drives", "time of possession",
                             "potential assists"],
        "artifact_sha256": None,
        "built_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    val["artifact_sha256"] = _sha(OUT / "ws5_opportunity_proxy_features_v1.parquet")
    (OUT / "WS5_FEATURE_VALIDATION.json").write_text(json.dumps(val, indent=2, default=str),
                                                     encoding="utf-8")
    print(f"rows {len(F):,}  tierA {int(F['is_tier_a_candidate'].sum()):,}")
    print(f"probe: {probe['values_checked']} values checked, {probe['mismatches']} mismatches -> "
          f"{'PASS' if probe['passed'] else 'FAIL'}")
    for p in PROXIES:
        print(f"  {p:24s} null={cov[p]['null']:6d} mean={cov[p]['mean']:.4f} "
              f"sd={cov[p]['std']:.4f}")
    return 0 if probe["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
