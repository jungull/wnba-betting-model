"""E0_I0019 -- s00: inspect the p_active artifacts and the frames we may join to.
Read-only. Writes _s00.json into this directory only."""
import json, os, sys
import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0019_availability_forecast")
sys.path.insert(0, os.path.join(ROOT, r"experiments\exploration\_screen_kit"))
import screenkit as sk

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 100)

ARMS = {
    "v15": os.path.join(ROOT, r"experiments\cbs_v15_player_oof_v5\attempt_001"),
    "v14": os.path.join(ROOT, r"experiments\cbs_v14_player_oof\attempt_001"),
}
rep = {}

print("=" * 100)
print("s00a  FOLD RECEIPTS for p_active, both arms, seasons 2021-2024")
print("=" * 100)
for arm, d in ARMS.items():
    rep[arm] = {}
    for s in [2021, 2022, 2023, 2024]:
        fr = json.load(open(os.path.join(d, "fold_receipt__%d.json" % s)))
        row = dict(
            train_seasons=fr["train_seasons"], n_train_rows=fr["n_train_rows"],
            n_test_rows=fr["n_test_rows"], model_was_fitted=fr["model_was_fitted"],
            degenerate=fr["degenerate"],
            cold_start_declared_constant_only=fr["cold_start_declared_constant_only"],
            targets=fr.get("targets"),
            components=[c for c in fr.get("components", []) if c.startswith("p_active")],
            all_receipt_keys=sorted(fr.get("receipts", {}).keys()),
            fold_boundary_ok=fr.get("receipts", {}).get("fold_boundary", {}).get("ok"),
            provenance_history_ok=fr.get("receipts", {}).get("provenance_history", {}).get("ok"),
            own_outcome_never_informed_its_forecast=fr.get("own_outcome_never_informed_its_forecast"),
            forecast_scored_against_outcome=fr.get("forecast_scored_against_outcome"),
            evaluation_metric_calculated=fr.get("evaluation_metric_calculated"),
            failed_receipts=fr.get("failed_receipts"),
            fit_through_date=fr.get("fit_through_date"),
            p_active_completeness=fr.get("obligation_completeness", {}).get("p_active"),
            top_level_keys=sorted(fr.keys()),
        )
        rep[arm][s] = row
        print("  %s season %d train=%-14s n_train=%-6d n_test=%-5d fitted=%-5s degen=%-5s "
              "own_outcome_never_informed=%s" % (arm, s, fr["train_seasons"], fr["n_train_rows"],
              fr["n_test_rows"], fr["model_was_fitted"], fr["degenerate"],
              fr["own_outcome_never_informed_its_forecast"]))
        print("        p_active components: %s" % row["components"])

print("=" * 100)
print("s00b  MANIFESTS via screenkit.check_manifest (verdict field is `status`)")
print("=" * 100)
man = {}
for arm, d in ARMS.items():
    for s in [2021, 2022, 2023, 2024]:
        p = os.path.join(d, "predictions__p_active__%d.parquet" % s)
        r = sk.check_manifest(p)
        raw = json.load(open(p + ".manifest.json"))
        man["%s_%d" % (arm, s)] = dict(
            status=r.get("status"), asof_granularity=raw.get("asof_granularity"),
            fit_seasons=raw.get("fit_seasons"), fit_through_season=raw.get("fit_through_season"),
            fit_through_date=raw.get("fit_through_date"),
            scores_computed=raw.get("scores_computed"), generation_only=raw.get("generation_only"),
            content_sha256=raw.get("content_sha256"))
        print("  %-9s %d  status=%-38s asof=%-9s fit_seasons=%-8s fit_through_season=%s"
              % (arm, s, r.get("status"), raw.get("asof_granularity"), raw.get("fit_seasons"),
                 raw.get("fit_through_season")))

print("=" * 100)
print("s00c  p_active PARQUET SCHEMA (v15, 2022)")
print("=" * 100)
pa = pd.read_parquet(os.path.join(ARMS["v15"], "predictions__p_active__2022.parquet"))
print("  shape", pa.shape)
print(pa.dtypes.to_string())
print(pa.head(6).to_string())
schema = {c: str(t) for c, t in pa.dtypes.items()}

print("=" * 100)
print("s00d  PREDICTION CONTRACT v4 player_game columns")
print("=" * 100)
cm = sk.check_manifest(os.path.join(ROOT, r"experiments\prediction_contract_v4\player_game.parquet"))
print("  contract manifest status:", cm.get("status"))
con = pd.read_parquet(os.path.join(ROOT, r"experiments\prediction_contract_v4\player_game.parquet"))
print("  shape", con.shape)
print("  columns:", list(con.columns))
print(con.head(3).to_string())

print("=" * 100)
print("s00e  MASTER_PLAYER columns")
print("=" * 100)
mm = sk.check_manifest(os.path.join(ROOT, r"data\masters\master_player.parquet"))
print("  master manifest status:", mm.get("status"))
mp = pd.read_parquet(os.path.join(ROOT, r"data\masters\master_player.parquet"), columns=None)
print("  shape", mp.shape)
print("  columns:", list(mp.columns))

print("=" * 100)
print("s00f  FORBIDDEN ARTIFACT MANIFESTS -- read the MANIFEST ONLY, never the data")
print("=" * 100)
forb = {}
for rel in ["data/w1_truth/player_game_availability.csv", "data/w1_truth/roster_asof.csv"]:
    mp_path = os.path.join(ROOT, rel.replace("/", os.sep))
    r = sk.check_manifest(mp_path)
    raw = json.load(open(mp_path + ".manifest.json"))
    forb[rel] = dict(status=r.get("status"), asof_granularity=raw.get("asof_granularity"),
                     fit_through_season=raw.get("fit_through_season"))
    print("  %-46s status=%-38s asof=%-9s fit_through_season=%s  -> NOT OPENED"
          % (rel, r.get("status"), raw.get("asof_granularity"), raw.get("fit_through_season")))

json.dump(dict(fold_receipts=rep, manifests=man, p_active_schema=schema,
               contract_columns=list(con.columns), master_columns=list(mp.columns),
               forbidden=forb),
          open(os.path.join(OUT, "_s00.json"), "w"), indent=2, default=str)
print("\nwrote _s00.json")
