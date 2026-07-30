"""oracle_bracket.py — Regime-C availability oracle bracket (four runs).

Preregistered experiment: ``oracle_availability_bracket_v2``
(experiments/registry.jsonl, registered 2026-07-30T20:45:57Z, regime C,
primary metric margin_mae, incumbent ``chanreval_structural_calibrated``).
Supersedes ``oracle_availability_bracket_v1``, whose registered mechanics
contained a ~40x dimensional error (caught in smoke; never evaluated).

Four minutes-weight vectors over the SAME dressed universe (minutes-model M2
test rows), same games, same RAPM values:

  v1  no availability      w = min_ewma (as-of trend minutes)   -> adjustment == 0
  v2  reconstructed        w = p_plays * pred_min_played        (deployable, GATED)
  v3  pregame oracle       w = played_flag * StageB(started_last := actual starter)
  v4  omniscient minutes   w = actual minutes                   (DIAGNOSTIC ONLY)

margin_v = str_margin_cal + LINEUP_SCALE * [(m_v - m_1)_home - (m_v - m_1)_away]
with m_v(team) = sum_p w_v val_p / sum_p w_v (minutes-weighted MEAN RAPM),
val = rapm_v0 net_100 (missing players -> 25th percentile), and
LINEUP_SCALE = 4.0 = 5 on-floor slots x (80 team possessions / 100), fixed.

Because every variant runs over the identical dressed-row universe, roster-
composition information is common-mode and cancels in (s_v - s_1): v2 measures
REWEIGHTING within the roster, not who-is-dressed news. v1's margin equals the
unadjusted structural forecast exactly (audited). v4 embeds in-game information
(foul trouble, in-game injury, OT, blowout scripts) nobody had at tip — per
ROADMAP regime C it is a diagnostic ceiling, never "what news could achieve".

Run:  python oracle_bracket.py            # real run (records on ledger)
      python oracle_bracket.py --smoke    # scratch registry + outdir
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from evalharness import compare_to_incumbent, walk_forward_by_season  # noqa: E402
from evalharness import registry as ereg  # noqa: E402
import minutes_twostage as mts  # noqa: E402

CHAN = REPO / "experiments" / "channel_reval" / "predictions_v2.csv"
M2_PRED = REPO / "experiments" / "minutes_twostage" / "test_predictions_m1.csv"
M2_DRESSED = REPO / "experiments" / "minutes_twostage" / "test_predictions_m2.csv"
RAPM = REPO / "data" / "rapm" / "rapm_v0.csv"
ODDS_OLD = REPO / "data" / "drive_masters" / "master_odds.csv"
ODDS_EXT = REPO / "data" / "odds_capture" / "master_odds_extension.csv"
DEFAULT_OUTDIR = REPO / "experiments" / "oracle_bracket"
EXPERIMENT_ID = "oracle_availability_bracket_v2"

LINEUP_SCALE = 4.0        # 5 on-floor slots x (80 team possessions per game / 100)
LAMBDA_B = 0.01           # recorded in minutes_twostage secondary results
REPRO_TOL = 1e-6
TEST_SEASONS = [2024, 2025, 2026]
VARIANTS = ["v1_none", "v2_reconstructed", "v3_pregame_oracle", "v4_omniscient"]


# ---------------------------------------------------------------------------
# rebuild the minutes feature frame EXACTLY as minutes_twostage.main steps 1-3
# ---------------------------------------------------------------------------

def rebuild_minutes_frame() -> tuple[pd.DataFrame, pd.DataFrame, "mts.Standardizer", np.ndarray]:
    dressed_raw, mt = mts.load_frames()
    P = mts.build_post_features(dressed_raw[dressed_raw["played_flag"] == 1])
    D = mts.asof_merge(dressed_raw, P)
    tf = mts.build_team_features(mt, P)
    D = D.merge(tf, on=["game_id", "team_id", "season"], how="left", validate="m:1")
    D["home_flag"] = D["is_home"].astype(float)
    trait_const = {
        c: float(tf.loc[tf["season"].isin(mts.TRAIN_SEASONS), c].dropna().mean())
        for c in ("team_bench_share_ewma", "team_n_rotation_ewma")
    }
    for c, v in trait_const.items():
        D[c] = D[c].fillna(v)
    ti = mts.build_team_index_features(D, P, tf)
    D = D.merge(ti, on=["team_id", "season", "game_id", "player_id"],
                how="left", validate="1:1")
    D["returning_flag"] = ((D["played_last_team_game"] == 0)
                           & D["prev_dnp_class"].isin(["INJ", "NWT"])).astype(float)
    ev, _ = mts.load_injury_events(D)
    D = mts.add_injury_features(D, ev)
    D["row_id"] = D["game_id"].astype(str) + ":" + D["player_id"].astype(str)

    # refit Stage B at the recorded lambda on the identical protocol
    m1 = (D["played_flag"] == 1) & (D["player_gp_season"] >= 1)
    U1 = D[m1].reset_index(drop=True)
    o1 = {o.name: o for o in walk_forward_by_season(
        U1, date_col="game_date", season_col="season", test_seasons=TEST_SEASONS)}
    tr1 = U1.loc[o1["season:2024"].train_idx]
    assert sorted(tr1["season"].unique()) == mts.TRAIN_SEASONS
    std_b = mts.Standardizer(tr1[mts.STAGE_B_FEATURES])
    beta_b = mts.ridge_fit(std_b.transform(tr1[mts.STAGE_B_FEATURES]),
                           tr1["minutes"].to_numpy(float), LAMBDA_B)
    D["pred_min_played_repro"] = mts.ridge_predict(
        std_b.transform(D[mts.STAGE_B_FEATURES]), beta_b)
    return D, mt, std_b, beta_b


# ---------------------------------------------------------------------------
# bookie lines: latest pre-tip snapshot per (game, book), home-row margin
# ---------------------------------------------------------------------------

def build_bookie_margins() -> pd.DataFrame:
    frames = []
    for path in (ODDS_OLD, ODDS_EXT):
        o = pd.read_csv(path, low_memory=False)
        o = o[o["game_id"].notna()].copy()
        o["game_id"] = o["game_id"].astype(np.int64).astype(str)
        o["snap"] = pd.to_datetime(o["odds_snapshot_timestamp"], utc=True, format="mixed")
        o["tip"] = pd.to_datetime(o["odds_commence_time"], utc=True, format="mixed")
        o = o[(o["team"] == o["home_team"]) & (o["snap"] <= o["tip"])
              & o["odds_spread"].notna()]
        frames.append(o[["game_id", "bookmaker_key", "snap", "odds_spread"]])
    allo = pd.concat(frames, ignore_index=True)
    allo = allo.sort_values("snap").groupby(["game_id", "bookmaker_key"]).tail(1)
    per_game = allo.groupby("game_id").agg(
        bookie_margin=("odds_spread", lambda s: float(-s.mean())),
        n_books=("odds_spread", "size")).reset_index()
    return per_game


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def fmt_table(df: pd.DataFrame, floatfmt: str = "{:.4f}") -> str:
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: floatfmt.format(v) if pd.notna(v) else "")
    header = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    body = "\n".join("| " + " | ".join(map(str, row)) + " |"
                     for row in d.itertuples(index=False))
    return "\n".join([header, sep, body])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args(argv)

    registry_path = None
    outdir = args.outdir or DEFAULT_OUTDIR
    if args.smoke:
        import tempfile
        scratch = Path(tempfile.mkdtemp(prefix="oracle_bracket_smoke_"))
        registry_path = scratch / "registry_scratch.jsonl"
        shutil.copyfile(REPO / "experiments" / "registry.jsonl", registry_path)
        outdir = args.outdir or (scratch / "out")
    outdir.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[oracle] {'SMOKE ' if args.smoke else ''}run at {run_time} -> {outdir}")

    # 1. base forecasts ------------------------------------------------------
    chan = pd.read_csv(CHAN)
    chan["GAME_ID"] = chan["GAME_ID"].astype(str)
    chan["game_date"] = pd.to_datetime(chan["GAME_DATE_h"])
    n_all = len(chan)
    n_playoffs = int((chan["season_type_h"] != "Regular Season").sum())
    chan = chan[chan["season_type_h"] == "Regular Season"].copy()
    print(f"[base] {len(chan)} regular-season channel test games scored "
          f"({chan['season_h'].value_counts().sort_index().to_dict()}); "
          f"{n_playoffs} playoff games excluded (minutes system is "
          f"regular-season-only per MINUTES_MODEL_SPEC 2.1)")

    # 2. minutes frame + Stage-B reproduction gate ---------------------------
    D, mt, std_b, beta_b = rebuild_minutes_frame()
    committed = pd.read_csv(M2_PRED)
    j = committed.merge(D[["row_id", "pred_min_played_repro"]], on="row_id",
                        validate="1:1")
    repro_dev = float((j["pred_min_played"] - j["pred_min_played_repro"]).abs().max())
    assert repro_dev <= REPRO_TOL, f"Stage-B reproduction FAILED: {repro_dev}"
    print(f"[repro] Stage-B reproduced: max |dev| = {repro_dev:.2e} over {len(j):,} rows")

    # 3. weights on the dressed M2 test universe -----------------------------
    m2c = pd.read_csv(M2_DRESSED)
    m2c["game_id"] = m2c["game_id"].astype(str)
    dd = m2c.merge(
        D[["row_id", "starter_flag", "team_id"] + mts.STAGE_B_FEATURES],
        on="row_id", validate="1:1", how="left", suffixes=("_csv", ""))
    assert dd["team_id"].notna().all()
    # the committed CSV's min_ewma and the rebuilt frame's must be identical
    assert float((dd["min_ewma_csv"] - dd["min_ewma"]).abs().max()) < 1e-9
    # w3: inject actual starters into Stage B, zeroed by actual played_flag
    X3 = dd[mts.STAGE_B_FEATURES].copy()
    X3["started_last"] = dd["starter_flag"].fillna(0).astype(float)
    pred3 = mts.ridge_predict(std_b.transform(X3), beta_b)
    dd["w1"] = dd["min_ewma"].clip(lower=0)
    dd["w2"] = (dd["p_plays"] * dd["pred_min_played"]).clip(lower=0)
    dd["w3"] = (dd["played_flag"] * pred3).clip(lower=0)
    dd["w4"] = dd["minutes"].fillna(0.0).clip(lower=0)
    # w2 provenance audit: identical to the committed file's product
    prov_dev = float((dd["w2"] - (m2c["p_plays"] * m2c["pred_min_played"]).clip(lower=0))
                     .abs().max())
    assert prov_dev < 1e-9, prov_dev

    # 4. RAPM values ---------------------------------------------------------
    rapm = pd.read_csv(RAPM)
    replacement = float(rapm["net_100"].quantile(0.25))
    val_map = dict(zip(rapm["player_id"].astype(np.int64), rapm["net_100"]))
    dd["val"] = dd["player_id"].astype(np.int64).map(val_map)
    n_repl = int(dd["val"].isna().sum())
    dd["val"] = dd["val"].fillna(replacement)
    print(f"[rapm] replacement (p25 net_100) = {replacement:.3f}; "
          f"rows on replacement {n_repl:,}/{len(dd):,}")

    # 5. team strengths per variant -----------------------------------------
    def strength(g, w):
        tot = g[w].sum()
        return float((g[w] * g["val"]).sum()) / tot if tot > 0 else np.nan
    rows = []
    for (gid, tid), g in dd.groupby(["game_id", "team_id"]):
        rows.append({"game_id": gid, "team_id": tid,
                     "team": g["team_abbreviation"].iloc[0],
                     "n_rows": len(g)}
                    | {f"s_{v}": strength(g, w)
                       for v, w in zip(VARIANTS, ["w1", "w2", "w3", "w4"])})
    S = pd.DataFrame(rows)

    # 6. per-game margins per variant ---------------------------------------
    tid_map = mt[["game_id", "team_abbreviation", "team_id"]].copy()
    tid_map["game_id"] = tid_map["game_id"].astype(str)
    tid_lookup = {(g, a): t for g, a, t in
                  tid_map.itertuples(index=False, name=None)}
    cg = chan.copy()
    cg["tid_h"] = [tid_lookup.get((g, a)) for g, a in
                   zip(cg["GAME_ID"], cg["TEAM_ABBREVIATION_h"])]
    cg["tid_a"] = [tid_lookup.get((g, a)) for g, a in
                   zip(cg["GAME_ID"], cg["TEAM_ABBREVIATION_a"])]
    assert cg["tid_h"].notna().all() and cg["tid_a"].notna().all()
    s_lookup = {(r["game_id"], r["team_id"]): r for _, r in S.iterrows()}
    for side, tid in (("h", "tid_h"), ("a", "tid_a")):
        recs = [s_lookup.get((g, t)) for g, t in zip(cg["GAME_ID"], cg[tid])]
        for v in VARIANTS:
            cg[f"s_{v}_{side}"] = [r[f"s_{v}"] if r is not None else np.nan
                                   for r in recs]
        cg[f"n_rows_{side}"] = [r["n_rows"] if r is not None else 0 for r in recs]
    covered = cg[[f"s_{v}_h" for v in VARIANTS] + [f"s_{v}_a" for v in VARIANTS]].notna().all(axis=1)
    dropped = cg[~covered]
    cg = cg[covered].copy()
    print(f"[cover] {len(cg)} games scored; {len(dropped)} dropped "
          f"(missing strength on a side)")

    for v in VARIANTS:
        adj_h = cg[f"s_{v}_h"] - cg["s_v1_none_h"]
        adj_a = cg[f"s_{v}_a"] - cg["s_v1_none_a"]
        cg[f"margin_{v}"] = cg["str_margin_cal"] + LINEUP_SCALE * (adj_h - adj_a)
    ident_dev = float((cg["margin_v1_none"] - cg["str_margin_cal"]).abs().max())
    assert ident_dev == 0.0, f"v1 identity violated: {ident_dev}"

    # 7. MAE table + registered comparison ----------------------------------
    mae_rows = []
    for v in VARIANTS:
        err = (cg[f"margin_{v}"] - cg["margin_true"]).abs()
        row = {"variant": v, "pooled_mae": float(err.mean()), "n": len(cg)}
        for season in TEST_SEASONS:
            row[f"mae_{season}"] = float(err[cg["season_h"] == season].mean())
        mae_rows.append(row)
    mae_tbl = pd.DataFrame(mae_rows)
    print(fmt_table(mae_tbl))

    def frame(v):
        return pd.DataFrame({
            "game_id": cg["GAME_ID"], "game_date": cg["game_date"],
            "season": cg["season_h"], "y_true": cg["margin_true"].astype(float),
            "y_pred": cg[f"margin_{v}"].astype(float),
            "team": cg["TEAM_ABBREVIATION_h"],
        })
    inc_frame = frame("v1_none")[["game_id", "y_true", "y_pred"]]
    result = compare_to_incumbent(
        frame("v2_reconstructed"), inc_frame, experiment_id=EXPERIMENT_ID,
        registry_path=registry_path, loss="absolute", cluster="date",
        team_col="team", coverage=(1.0, 1.0),
    )
    print(f"[gate v2-v1] {result.verdict} pooled {result.metric_challenger:.4f} vs "
          f"{result.metric_incumbent:.4f} delta {result.pooled_improvement:+.4f} "
          f"CI [{result.ci_low:+.4f}, {result.ci_high:+.4f}] failed={result.failed_gates}")
    res3 = compare_to_incumbent(
        frame("v3_pregame_oracle"), inc_frame, experiment_id=EXPERIMENT_ID,
        registry_path=registry_path, loss="absolute", cluster="date",
        team_col="team", coverage=(1.0, 1.0), record=False,
    )
    res4 = compare_to_incumbent(
        frame("v4_omniscient"), inc_frame, experiment_id=EXPERIMENT_ID,
        registry_path=registry_path, loss="absolute", cluster="date",
        team_col="team", coverage=(1.0, 1.0), record=False,
    )
    print(f"[v3-v1] delta {res3.pooled_improvement:+.4f} CI [{res3.ci_low:+.4f}, {res3.ci_high:+.4f}]")
    print(f"[v4-v1] delta {res4.pooled_improvement:+.4f} CI [{res4.ci_low:+.4f}, {res4.ci_high:+.4f}] (DIAGNOSTIC ONLY)")

    # 8. bookie gap table (context, ungated) ---------------------------------
    bk = build_bookie_margins()
    cb = cg.merge(bk, left_on="GAME_ID", right_on="game_id", how="inner",
                  suffixes=("", "_bk"))
    gap_rows = []
    for season in TEST_SEASONS + ["pooled"]:
        sub = cb if season == "pooled" else cb[cb["season_h"] == season]
        if not len(sub):
            continue
        bmae = float((sub["bookie_margin"] - sub["margin_true"]).abs().mean())
        row = {"season": season, "n_odds_covered": len(sub), "bookie_mae": bmae}
        for v in VARIANTS:
            vmae = float((sub[f"margin_{v}"] - sub["margin_true"]).abs().mean())
            row[f"{v}_mae"] = vmae
            row[f"{v}_gap"] = vmae - bmae
        gap_rows.append(row)
    gap_tbl = pd.DataFrame(gap_rows)
    print(fmt_table(gap_tbl[["season", "n_odds_covered", "bookie_mae"]
                            + [f"{v}_gap" for v in VARIANTS]]))

    # 9. secondary record ----------------------------------------------------
    def slim(r):
        d = r.to_dict()
        return {k: d[k] for k in
                ("metric_challenger", "metric_incumbent", "pooled_improvement",
                 "ci_low", "ci_high", "ci_level", "n_games", "n_clusters", "per_season")}
    secondary = {
        "record_type": "oracle_bracket_sensitivity",
        "labels": {"v1": "no availability info", "v2": "reconstructed (regime-B)",
                   "v3": "pregame oracle (active + confirmed starters)",
                   "v4": "omniscient minutes (DIAGNOSTIC CEILING ONLY - contaminated "
                         "by in-game information; never what news extraction could achieve)"},
        "mae_table": mae_tbl.to_dict("records"),
        "v3_vs_v1": slim(res3),
        "v4_vs_v1": slim(res4),
        "bookie_gap_table": gap_tbl.to_dict("records"),
        "coverage": {"games_scored": int(len(cg)), "games_dropped": int(len(dropped)),
                     "playoff_games_excluded": n_playoffs,
                     "playoff_exclusion_reason": "minutes system is regular-season-"
                                                 "only (MINUTES_MODEL_SPEC 2.1); "
                                                 "identical exclusion for all four "
                                                 "variants",
                     "rapm_replacement_rows": n_repl,
                     "rapm_replacement_value": replacement},
        "audits": {"v1_identity_max_dev": ident_dev,
                   "stage_b_reproduction_max_dev": repro_dev,
                   "w2_provenance_max_dev": prov_dev,
                   "game_set_identity": "single frame, all variants same rows"},
        "constants": {"lineup_scale": LINEUP_SCALE, "lambda_b": LAMBDA_B},
    }
    ereg.evaluate(EXPERIMENT_ID, secondary, registry_path=registry_path)

    # 10. artifacts ----------------------------------------------------------
    mae_tbl.to_csv(outdir / "bracket_results.csv", index=False)
    gap_tbl.to_csv(outdir / "bookie_gap.csv", index=False)
    keep = (["GAME_ID", "game_date", "season_h", "TEAM_ABBREVIATION_h",
             "TEAM_ABBREVIATION_a", "margin_true", "str_margin_cal"]
            + [f"margin_{v}" for v in VARIANTS]
            + [f"s_{v}_h" for v in VARIANTS] + [f"s_{v}_a" for v in VARIANTS]
            + ["n_rows_h", "n_rows_a"])
    cg[keep].to_csv(outdir / "game_level_margins.csv", index=False)
    with open(outdir / "gate_verdict.json", "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, indent=2, default=str)
    with open(outdir / "secondary_results.json", "w", encoding="utf-8") as fh:
        json.dump(secondary, fh, indent=2, default=str)

    md = f"""# Regime-C availability oracle bracket (`{EXPERIMENT_ID}`)

*Generated by `oracle_bracket.py` on {run_time}. Regime C — sensitivity analysis; only the
v2-vs-v1 comparison is gated (deployable system); v3/v4 are preregistered oracle outputs,
never promotable; v4 is a DIAGNOSTIC CEILING contaminated by in-game information.*

## The bracket (margin MAE, {len(cg)} channel test games)

{fmt_table(mae_tbl)}

- **Gated v2 vs v1: {result.verdict}** (delta {result.pooled_improvement:+.4f},
  CI [{result.ci_low:+.4f}, {result.ci_high:+.4f}]; failed: {result.failed_gates or 'none'})
- v3 pregame-oracle vs v1: delta {res3.pooled_improvement:+.4f}, CI [{res3.ci_low:+.4f}, {res3.ci_high:+.4f}]
- v4 omniscient vs v1: delta {res4.pooled_improvement:+.4f}, CI [{res4.ci_low:+.4f}, {res4.ci_high:+.4f}]
  (diagnostic ceiling only)

## Bookie gap (odds-covered subset; gap = variant MAE - avg bookie MAE)

{fmt_table(gap_tbl[["season", "n_odds_covered", "bookie_mae"] + [f"{v}_gap" for v in VARIANTS]])}

## Design notes

- All four variants run over the identical dressed universe (minutes-model M2 test rows),
  so roster-composition information is common-mode and cancels in the strength differences:
  v2 measures REWEIGHTING within the dressed roster (P(plays) x conditional minutes vs trend
  minutes), not who-is-dressed news. v1's margin equals `str_margin_cal` exactly (audited,
  max dev {ident_dev}).
- m_v(team) = sum(w_v * val)/sum(w_v) (minutes-weighted MEAN RAPM); val = rapm_v0 `net_100`;
  missing -> p25 = {replacement:.3f} ({n_repl:,} rows); LINEUP_SCALE = {LINEUP_SCALE} fixed a
  priori (5 on-floor slots x 80 team possessions / 100). Supersedes v1's dimensionally wrong
  200x-mean + 0.80 formulation (caught in smoke, never evaluated on the ledger).
- v3 injects actual active/DNP status and actual starters (started_last := target-game
  starter flag — documented approximation; the model was trained on started_last semantics).
- Stage-B reproduction gate: refit at recorded lambda {LAMBDA_B} reproduced the committed
  predictions to {repro_dev:.2e}. w2 provenance dev {prov_dev:.2e}.
- Games dropped for coverage: {len(dropped)}. Playoff games excluded up front: {n_playoffs}
  (minutes system is regular-season-only per spec 2.1; identical for all variants).

## Files

`bracket_results.csv`, `bookie_gap.csv`, `game_level_margins.csv`, `gate_verdict.json`,
`secondary_results.json`.
"""
    (outdir / "REPORT.md").write_text(md, encoding="utf-8")
    print(f"[done] artifacts in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
