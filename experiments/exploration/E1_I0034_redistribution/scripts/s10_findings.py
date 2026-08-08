"""S10 -- ASSEMBLE FINDINGS.json AND EVERY CSV THAT BACKS A QUOTED NUMBER.

Verdicts are applied by the PREREGISTERED decision rules DR1-DR5, mechanically, from the stored
statistics.  Nothing is decided by hand here.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redist_base as rb
import s04_prereg

pd.set_option("display.width", 260); pd.set_option("display.max_columns", 60)
W2 = (2023, 2024)


def load(n):
    p = os.path.join(rb.OUT, n)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def verdict_forecast(eff, p, mde):
    if p < 0.05 and eff > 0 and eff > mde:
        return "DECIDED_POSITIVE"
    if p < 0.05 and eff < 0 and abs(eff) > mde:
        return "DECIDED_NEGATIVE"
    if p < 0.05:
        return "SIGNIFICANT_BUT_UNDERPOWERED__NOT_ESTABLISHED"
    return "NOT_ESTABLISHED"


def main():
    rb.hdr("S10 FINDINGS")
    pre = s04_prereg.assert_unchanged()
    S2, S5, S6 = load("_s02.json"), load("_s05.json"), load("_s06.json")
    S7, S8, S9 = load("_s07.json"), load("_s08.json"), load("_s09.json")
    print("  loaded: s02 %s s05 %s s06 %s s07 %s s08 %s s09 %s"
          % tuple("ok" if x else "MISSING" for x in [S2, S5, S6, S7, S8, S9]))

    F = {
        "screen_id": "E1_I0034_redistribution",
        "question": ("when a player is absent, where do their minutes, shot attempts and points "
                     "go, and is that redistribution forecastable from pre-game information?"),
        "prereg_sha256": pre["prereg_sha256"],
        "prereg_bytes": pre["n_bytes"],
        "seed": rb.SEED,
        "partition": {"exploration_seasons": list(rb.EXPLORATION_SEASONS),
                      "holdout_never_opened": [2025, 2026],
                      "primary_scoring_window_W2": list(W2),
                      "secondary_scoring_window_W1": [2022, 2023, 2024],
                      "seasons_used_as_TRAINING_ONLY": [2021, 2022]},
        "level_declaration": S2["level_declaration"],
        "conditioning": ("ABSENCE IS REALISED -- ORACLE. both pre-game injury sources return "
                         "manifest_present:false / UNVERIFIABLE and are refused, so every "
                         "forecast cell is a CEILING, not an achievable increment."),
        "anchors": {"A1_D104_home_advantage": S2["anchor_A1_D104"],
                    "A2_D076_appeared_player_games": S2["anchor_A2_D076"],
                    "A3_D111_absence_construction": S2["anchor_A3_D111_absence"]},
        "manifest_checks": {k: {"status": v.get("status"),
                                "asof_granularity": v.get("asof_granularity"),
                                "screen_decision": v.get("screen_decision")}
                            for k, v in S2["manifest_checks"].items()},
        "retrospective_baseline_check": S2["retrospective_baseline_check"],
        "reference_coverage_D087": {"bios": S2["bios_coverage_D087"],
                                    "cell_row_set": {k: v for k, v in S5.items()
                                                     if k.startswith("coverage_")}},
        "arithmetic_ceiling_computed_before_fitting": {
            "note": ("largest linear association available, on RSP-W2, before any model existed. "
                     "D103 single-cell floor 0.00102; programme's largest live effect 0.002057."),
            "minutes": {"dR2_on_level": 0.00470, "ceiling_dMAE": 0.0329,
                        "verdict": "ABOVE both benchmarks -- fitted"},
            "fga": {"dR2_on_level": 0.00258, "ceiling_dMAE": 0.0087,
                    "verdict": "ABOVE both benchmarks -- fitted"},
            "pts": {"dR2_on_level": 0.00146, "ceiling_dMAE": 0.0059,
                    "verdict": ("above the D103 floor but BELOW the programme's largest live "
                                "effect -- fitted, verdict quoted with the ceiling attached")}},
        "cells": {},
        "power": {},
        "null_audit_ADDED_AFTER_HASH": {},
        "secondary_and_stratification": {},
        "cells_added_after_hash": [
            {"id": "s09_NULL_AUDIT",
             "what": ("a whole verification step: absorption tell on all 14 cells, measured "
                      "candidate-level audit, a blindness demonstration of the within-player "
                      "cyclic null on this screen's own candidate, component-wise vs "
                      "shuffled-residual injection side by side, block-bootstrap variance, and a "
                      "simulated 80%-power curve."),
             "why": ("coordinator correction mid-screen: E1_I0036 severity A (shuffled-residual "
                     "injection can certify a blind null) and D113 (analytic MDE80 possibly "
                     "anti-conservative)."),
             "direction_it_moved_the_result": (
                 "AGAINST this screen's headline, twice. (a) it downgraded P03_minutes from "
                 "DECIDED to AT-THE-BOUNDARY (empirical power 0.783 at the observed effect, "
                 "injection-verified MDE80 0.0308 > observed 0.0295). (b) rescaled to the "
                 "injection-verified floor it also WITHDREW the points-negative verdicts "
                 "(-4.01 and -3.28 null sds against a points threshold of 9.50). It moved "
                 "nothing in this screen's favour.")}],
        "cells_dropped_after_hash": [],
        "note_on_strata": ("the FREED>0 and FREED>=25 rows in "
                           "secondary_and_stratification.stratification_by_freed are "
                           "STRATIFICATIONS of preregistered cells -- the same statistic on a "
                           "subset of its own row set -- not new cells. Each carries its own n."),
    }

    # ---------------------------------------------------------------- cells + verdicts
    for name, c in S6["cells"].items():
        rec = {k: v for k, v in c.items() if k not in ("per_season", "per_season_M0",
                                                       "per_season_M1")}
        rec["per_season"] = c.get("per_season") or {"M0": c.get("per_season_M0"),
                                                    "M1": c.get("per_season_M1")}
        eff, p, mde = float(c["effect"]), float(c["p"]), float(c["MDE80"])
        if name.startswith("P03") or name.startswith("P04") or name.startswith("P05"):
            rec["verdict"] = verdict_forecast(eff, p, mde)
        elif name.startswith("P01"):
            rec["distance_of_zero_in_null_sds"] = abs(eff - 0.0) / float(c["null_sd"])
            rec["distance_of_one_in_null_sds"] = abs(1.0 - eff) / float(c["null_sd"])
            rec["verdict"] = ("FULL_LEAKAGE_REJECTED__NO_LEAKAGE_ESTABLISHED"
                              if abs(eff) < mde else "LEAKAGE_DETECTED")
        elif name.startswith("P02"):
            rec["verdict"] = ("DIFFUSE__TILT_NOT_ESTABLISHED" if abs(eff) < mde
                              else ("CONCENTRATED_ON_LARGE_BASELINES" if eff > 0
                                    else "CONCENTRATED_ON_SMALL_BASELINES"))
        elif name.startswith("P06"):
            rec["verdict"] = ("NEGATIVE_CONTROL_PASSES__NULL" if abs(eff) < mde
                              else "NEGATIVE_CONTROL_FAILS__WITHDRAW_P03_P04")
        # the coordinator's absorption tell, on every cell
        nm, nsd = float(c["null_mean"]), float(c["null_sd"])
        rec["null_absorption_tell"] = {
            "null_mean": nm, "observed": eff, "null_mean_in_null_sds": nm / nsd,
            "same_sign_as_observed": bool(np.sign(nm) == np.sign(eff) and eff != 0),
            "abs_ratio": (abs(nm) / abs(eff)) if eff != 0 else None,
            "ABSORBED": bool(np.sign(nm) == np.sign(eff) and eff != 0 and abs(nm) >= abs(eff))}
        F["cells"][name] = rec

    # ---- injection-verified floors, from the simulated power curve (s09 E2), attached per cell
    cp = os.path.join(rb.OUT, "power_simulated_curve.csv")
    if os.path.exists(cp):
        curve = pd.read_csv(cp)
        for cell, g in curve.groupby("cell"):
            g = g.sort_values("dMAE_total")
            x = g["dMAE_total"].to_numpy(); yy = g["empirical_power"].to_numpy()
            extrap = bool(yy.max() < 0.80)
            if not extrap:
                inj = float(np.interp(0.80, yy, x))
            else:
                sl = (yy[-1] - yy[-2]) / (x[-1] - x[-2])
                inj = float(x[-1] + (0.80 - yy[-1]) / sl)
            rec = F["cells"][cell]
            ana = float(rec["MDE80"]); nsd = float(rec["null_sd"])
            rec["MDE80_analytic"] = ana
            rec["MDE80_injection_verified"] = inj
            rec["MDE80_injection_verified_is_EXTRAPOLATED"] = extrap
            rec["MDE80_injection_over_analytic"] = inj / ana
            rec["injection_verified_threshold_in_null_sds"] = inj / nsd
            rec["empirical_power_at_observed_effect"] = float(
                np.interp(float(rec["effect"]), x, yy))
            rec["verdict_under_injection_verified_floor"] = verdict_forecast(
                float(rec["effect"]), float(rec["p"]), inj)
            rec["MDE80_which_floor_backs_the_verdict"] = (
                "the headline verdict uses the PREREGISTERED analytic floor; the "
                "injection-verified floor is reported beside it and is the one to prefer "
                "(coordinator note on D113).")

    print("\n  VERDICTS")
    for n, c in F["cells"].items():
        print("    %-42s effect %+9.5f  p %.4f  MDE80 %.5f  -> %s"
              % (n, c["effect"], c["p"], c["MDE80"], c["verdict"]))

    # ---------------------------------------------------------------- power
    if S7:
        F["power"] = {
            "injection_construction": ("COMPONENT-WISE: `plant * candidate` is added to the REAL "
                                       "response and the ENTIRE path is rerun. The response "
                                       "structure of the carrier is never destroyed. The "
                                       "shuffled-residual construction that E1_I0036 found "
                                       "defective is run only as a labelled comparison in s09."),
            "injection_P01": S7.get("injection_P01"),
            "injection_P02_P05": S7.get("injection_P02_P05"),
            "injection_P03_fullpath": S7.get("injection_P03_fullpath"),
            "injection_P03_percell": S7.get("injection_P03_percell"),
            "type_I": S7.get("type_I"),
            "noop_placebo": S7.get("noop_placebo"),
            "declared_trap": ("a two-sided permutation p at an observed statistic of exactly zero "
                              "is 1.0000 by construction. no `plant = 0` row is reported as a "
                              "type-I pass; the type-I pass comes only from the synthetic "
                              "no-effect datasets.")}
    if S9:
        F["null_audit_ADDED_AFTER_HASH"] = {
            "status": S9["status"],
            "absorption_tell": S9.get("absorption_tell"),
            "level_audit": S9.get("level_audit"),
            "blindness_demo": S9.get("blindness_demo"),
            "injection_style_comparison": S9.get("injection_style_comparison"),
            "bootstrap_floors": S9.get("bootstrap_floors"),
            "simulated_power_curve": S9.get("simulated_power_curve")}
    if S8:
        F["secondary_and_stratification"] = {
            "secondary_W1": S8.get("secondary_W1"),
            "stratification_by_freed": S8.get("stratification"),
            "accounting_where_minutes_go": S8.get("accounting"),
            "concentration_predictable": S8.get("concentration")}

    # ---------------------------------------------------------------- the baseline-sum diagnostic
    rb.hdr("BASELINE-SUM DIAGNOSTIC -- why FREED overstates the minutes actually available")
    R = pd.read_parquet(os.path.join(rb.OUT, "_rem_frame.parquet"))
    G = pd.read_parquet(os.path.join(rb.OUT, "_tg_frame.parquet"))
    pf = pd.read_parquet(os.path.join(rb.OUT, "_player_frame.parquet"))
    est = pf[(pf["nprior_minutes"] >= 3) & pf["base5_minutes"].notna()]
    B = est.groupby(["game_id", "team_id"])["base5_minutes"].sum().rename("B_minutes").reset_index()
    A = G.merge(B, on=["game_id", "team_id"], how="left")
    A = A[A["season"].isin(W2)]
    A["bucket"] = pd.cut(A["freed_minutes"], [-0.01, 0.01, 15, 30, 45, 1e9],
                         labels=["0", "0-15", "15-30", "30-45", "45+"])
    d = A.groupby("bucket", observed=True).agg(
        n=("B_minutes", "size"), mean_B_minutes=("B_minutes", "mean"),
        mean_freed=("freed_minutes", "mean"), mean_n_elig=("n_elig", "mean"),
        mean_n_rem=("n_rem", "mean")).reset_index()
    d["B_minus_200"] = d["mean_B_minutes"] - 200.0
    d["B_of_remaining"] = d["mean_B_minutes"] - d["mean_freed"]
    d["minutes_actually_available_to_remaining"] = 200.0 - d["B_of_remaining"]
    print(d.to_string(index=False))
    print("\n  READ: the trailing-5 baselines of a team's ESTABLISHED players sum to more than the")
    print("  200-minute budget, and by MORE when the team has absences -- because a trailing-5 is")
    print("  computed over games the player PLAYED, which are systematically his higher-minute")
    print("  games. FREED therefore OVERSTATES what is available to redistribute.")
    d.to_csv(os.path.join(rb.OUT, "baseline_sum_diagnostic.csv"), index=False)
    F["baseline_sum_diagnostic"] = d.to_dict("records")

    # ---------------------------------------------------------------- primary cell CSV
    rows = []
    for n, c in F["cells"].items():
        rows.append(dict(cell=n, row_set=c.get("row_set"), n=c.get("n"),
                         n_blocks=c.get("n_blocks"), response=c.get("response"),
                         base=c.get("base") or c.get("base_M0"),
                         candidate=c.get("candidate"),
                         effect=c["effect"], p=c["p"], null_scheme=c["null_scheme"],
                         null_mean=c["null_mean"], null_sd=c["null_sd"], MDE80=c["MDE80"],
                         MAE_M0=c.get("MAE_M0"), MAE_M1=c.get("MAE_M1"),
                         null_absorbed=c["null_absorption_tell"]["ABSORBED"],
                         null_mean_over_observed=c["null_absorption_tell"]["abs_ratio"],
                         MDE80_injection_verified=c.get("MDE80_injection_verified"),
                         empirical_power_at_observed=c.get(
                             "empirical_power_at_observed_effect"),
                         verdict_under_injection_floor=c.get(
                             "verdict_under_injection_verified_floor"),
                         verdict=c["verdict"]))
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(rb.OUT, "primary_cells.csv"), index=False)
    print("\n  wrote primary_cells.csv")

    with open(os.path.join(rb.OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
        json.dump(rb.jsonable(F), fh, indent=1)
    print("  wrote FINDINGS.json")


if __name__ == "__main__":
    main()
