"""
c06 -- ASSEMBLE FINDINGS.json FROM THE ARTEFACTS ON DISK AND APPLY THE PREREGISTERED DECISION RULE.

The rule is applied MECHANICALLY first and its verdict is recorded verbatim, INCLUDING where it
disagrees with the direct measurements.  A confirmation that quietly swaps its criterion after seeing
the numbers confirms nothing, so the disagreement is published as a defect in this screen's own
preregistration, with the exact clause, why it is a wrong proxy, and which measurement settles the
question the clause was trying to ask.
"""
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np       # noqa: E402
import pandas as pd      # noqa: E402
import cbase as cb       # noqa: E402
import c00_prereg as c0  # noqa: E402


def J(name):
    with open(os.path.join(cb.OUT, name), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    P = cb.Tee()
    cb.hdr("E1_I0025 c06 -- FINDINGS AND THE PREREGISTERED DECISION RULE")
    h, added, dropped = c0.check()
    P("  PREREG hash %s VERIFIED.  specs added=%d dropped=%d" % (h, len(added), len(dropped)))

    c01, c02, c03, c04, c05 = J("_c01.json"), J("_c02.json"), J("_c03.json"), J("_c04.json"), J("_c05.json")
    lad = pd.DataFrame(c02["ladder"])
    dec = pd.DataFrame(c03["decomposition"])
    rnd = pd.DataFrame(c04["random_tier_null"])
    swp = pd.DataFrame(c02["swap_null"])

    def L(rid, rung, evalrows="T3_high", stratum="DECISION"):
        s = lad[(lad.stratum == stratum) & (lad.eval_rows == evalrows) & (lad.response == rid)
                & (lad.rung.str.startswith(rung))]
        return float(s.iloc[0]["dr2_defence_family"])

    verdicts = {}
    for rid in ("ppm", "points"):
        G_refit = L(rid, "L4")
        G_step = L(rid, "L3")
        G_lin = L(rid, "L2")
        G_main = L(rid, "L1")
        F = G_step / G_refit
        d = dec[(dec.stratum == "DECISION") & (dec.tier == "T3_high") & (dec.response == rid)].iloc[0]
        R_nodef = float(d["R_nodef_refit_only"])
        tp_pooled = float(d["transplant_pooled_frozen_dr2"])
        tp_tier = float(d["transplant_tier_frozen_dr2"])
        q95 = float(rnd[(rnd.response == rid) & (rnd.statistic == "defence")]["null_p95"].max())
        p_rand = float(rnd[(rnd.response == rid) & (rnd.statistic == "defence")]["p_onesided"].max())
        p_swap_step = float(swp[(swp.response == rid) & (swp.rung.str.startswith("L3"))].iloc[0]["p_swap"])
        t1 = float(dec[(dec.stratum == "DECISION") & (dec.tier == "T1_low")
                       & (dec.response == rid)].iloc[0]["G_refit_L4"])
        t2 = float(dec[(dec.stratum == "DECISION") & (dec.tier == "T2_mid")
                       & (dec.response == rid)].iloc[0]["G_refit_L4"])
        nc = pd.DataFrame(c04["negative_control"])
        nc_max = float(nc["noise_dr2"].max())

        thr = {
            "F >= 0.60": F >= 0.60,
            "G_step > 0 at swap p < 0.05": (G_step > 0 and p_swap_step < 0.05),
            "R_nodef < 0.50 * G_refit": R_nodef < 0.50 * G_refit,
            "Q95_rand < 0.50 * G_refit": q95 < 0.50 * G_refit,
            "negative control clean": nc_max < 0.50 * G_refit,
            "max(|T1|, T2) < 0.50 * G_refit": max(abs(t1), t2) < 0.50 * G_refit,
        }
        art = {
            "R_nodef >= G_refit": R_nodef >= G_refit,
            "Q95_rand >= 0.60 * G_refit": q95 >= 0.60 * G_refit,
            "random-tier one-sided p >= 0.05": p_rand >= 0.05,
            "F <= 0.15 AND Q95_rand >= 0.30 * G_refit": (F <= 0.15 and q95 >= 0.30 * G_refit),
            "negative control >= 0.50 * G_refit": nc_max >= 0.50 * G_refit,
        }
        mech = ("REFIT_ARTEFACT" if any(art.values())
                else ("THRESHOLD" if all(thr.values()) else "UNRESOLVED"))
        verdicts[rid] = dict(
            G_refit_L4=G_refit, G_step_L3=G_step, G_linear_family_L2=G_lin,
            G_pooled_main_L1=G_main, F_recovery=F,
            R_nodef_refit_without_defence=R_nodef,
            transplant_pooled_frozen=tp_pooled, transplant_pooled_frozen_share=tp_pooled / G_refit,
            transplant_tier_frozen=tp_tier, transplant_tier_frozen_share=tp_tier / G_refit,
            Q95_random_tier=q95, p_random_tier=p_rand, p_swap_step=p_swap_step,
            placebo_tier_T1=t1, placebo_tier_T2=t2, negative_control_max=nc_max,
            THRESHOLD_criteria=thr, REFIT_ARTEFACT_criteria=art,
            MECHANICAL_VERDICT=mech,
            share_of_G_refit=dict(
                pooled_one_coefficient=G_main / G_refit,
                added_by_linear_interaction=(G_lin - G_main) / G_refit,
                added_by_making_it_a_step=(G_step - G_lin) / G_refit,
                added_by_the_full_tier_refit=(G_refit - G_step) / G_refit))
        P("")
        P("  ---- %s ----" % rid.upper())
        P("  G_refit(L4)=%+.6f  G_step(L3)=%+.6f  F=%.3f  |  L2=%+.6f  L1=%+.6f"
          % (G_refit, G_step, F, G_lin, G_main))
        P("  decomposition of G_refit: pooled one coefficient %.0f%% | linear interaction +%.0f%% | "
          "step instead of linear +%.0f%% | full tier refit +%.0f%%"
          % (100 * G_main / G_refit, 100 * (G_lin - G_main) / G_refit,
             100 * (G_step - G_lin) / G_refit, 100 * (G_refit - G_step) / G_refit))
        P("  R_nodef=%+.6f (%.0f%% of G_refit)   transplant pooled-frozen=%+.6f (%.0f%%)"
          % (R_nodef, 100 * R_nodef / G_refit, tp_pooled, 100 * tp_pooled / G_refit))
        P("  THRESHOLD criteria: %s" % {k: bool(x) for k, x in thr.items()})
        P("  ARTEFACT  criteria: %s" % {k: bool(x) for k, x in art.items()})
        P("  MECHANICAL VERDICT (preregistered rule, applied without adjustment): %s" % mech)

    # ------------------------------------------------------------------ the adjudication
    cb.hdr("ADJUDICATION -- WHERE THE PREREGISTERED RULE AND THE DIRECT MEASUREMENTS DISAGREE")
    adj = dict(
        mechanical_verdict=verdicts["ppm"]["MECHANICAL_VERDICT"],
        clauses_that_fired=[k for k, x in verdicts["ppm"]["REFIT_ARTEFACT_criteria"].items() if x],
        defect_1=dict(
            clause="R_nodef >= G_refit",
            intended_to_test="whether the defence term is 'along for the ride' on the refit",
            why_it_is_a_wrong_proxy="D098's statistic already carries the tier-restricted refit in "
                                    "BOTH arms, so the refit's contribution is ADDITIVE and "
                                    "ORTHOGONAL to the defence increment -- it cannot flow through "
                                    "the defence column by construction. R_nodef measures 'the top "
                                    "tercile has different baseline relationships', which is TRUE "
                                    "and separately worth +0.0333, and says nothing about whether "
                                    "the defence term is a passenger.",
            measurement_that_settles_it="TRANSPLANT with the POOLED non-defence coefficients frozen "
                                        "and only a defence coefficient added -- no refit anywhere "
                                        "-- recovers %.6f, %.0f%% of G_refit. And the pooled "
                                        "tier-step model, which has NO tier-specific baseline "
                                        "coefficients, recovers %.0f%%."
                                        % (verdicts["ppm"]["transplant_pooled_frozen"],
                                           100 * verdicts["ppm"]["transplant_pooled_frozen_share"],
                                           100 * verdicts["ppm"]["F_recovery"]),
            corroboration="adding defence to a model that ALREADY has tier-specific baselines (L4, "
                          "+0.023863) buys MORE than adding it to one that does not (L3, "
                          "+0.021986). If defence were proxying for the missing tier baseline "
                          "structure the ordering would be reversed. And the refit gain is generic "
                          "across tiers (T3 +0.0333, T2 +0.0338) while the defence gain is not "
                          "(T3 +0.0239, T2 +0.0052, T1 -0.0041)."),
        defect_2=dict(
            clause="Q95_rand >= 0.60 * G_refit",
            intended_to_test="whether refitting any equally sized subset reproduces the gain",
            why_it_is_a_wrong_proxy="the random-tier null is centred on the GENUINE pooled defence "
                                    "effect (null mean +0.0053, against the pooled all-tiers dR2 of "
                                    "+0.0050), not on zero, because a random subset of the decision "
                                    "stratum still contains the real pooled effect. Comparing a "
                                    "percentile of a correctly-centred null against a FRACTION OF "
                                    "THE OBSERVED is not a test of anything. The calibrated "
                                    "statistic is the p-value.",
            measurement_that_settles_it="the random-tier one-sided p is %.4f (row shuffle) and "
                                        "%.4f (player-season blocks). Both clear 0.05, but only "
                                        "just, and that thinness is the real residual uncertainty "
                                        "in this result -- it is reported as such rather than "
                                        "hidden behind the z of +12.80 against the opponent-swap "
                                        "null, which holds the subset fixed and therefore cannot "
                                        "speak to whether the subset is special."
                                        % (float(rnd[(rnd.response == "ppm") & (rnd.statistic == "defence")
                                                     & (rnd.variant == "ROWSHUFFLE")].iloc[0]["p_onesided"]),
                                           float(rnd[(rnd.response == "ppm") & (rnd.statistic == "defence")
                                                     & (rnd.variant == "PLAYERBLOCK")].iloc[0]["p_onesided"]))))
    for k in ("defect_1", "defect_2"):
        P("  %s -- clause `%s` FIRED." % (k.upper(), adj[k]["clause"]))
        P("     intended to test: %s" % adj[k]["intended_to_test"])
        P("     why it is a wrong proxy: %s" % adj[k]["why_it_is_a_wrong_proxy"])
        P("     what settles it: %s" % adj[k]["measurement_that_settles_it"])

    acc = pd.DataFrame(c03["accounting"])
    concl = pd.DataFrame(c05["concentration_null"])
    axis = pd.DataFrame(c05["axis"])

    findings = dict(
        screen="E1_I0025_threshold_vs_refit",
        confirms="E1_I0023 / D098, raised and not accepted",
        prereg_sha256=h, specs_added=len(added), specs_dropped=len(dropped),
        VERDICT="UNRESOLVED",
        VERDICT_ONE_LINE=(
            "The lead does NOT die -- REFIT ARTEFACT is refuted directly: a pooled model with no "
            "tier-specific baseline coefficients recovers 92% of the gain and freezing every "
            "non-defence coefficient at its pooled value recovers 99%. But THRESHOLD as framed is "
            "not supported either: 70% of the +0.023863 is a SINGLE POOLED DEFENCE COEFFICIENT with "
            "no volume heterogeneity at all, scored on high-volume rows; making the slope a step "
            "rather than linear is worth only 3%; and the 'largest the programme has measured' "
            "status rests on a dR2 and a ceiling computed on a 1,687-row subset whose SST is 36% of "
            "the stratum's, while the identical model scores +0.005028 over the whole stratum."),
        reproduction=c01["headline"], reproduction_gate_pass=c01["gate_pass"],
        headline=verdicts,
        adjudication=adj,
        ladder=c02["ladder"], ladder_increments=c02["increments"], swap_null=c02["swap_null"],
        noop_placebo=c02["noop_placebo"], placebo_perturbs=c02["placebo_perturbs"],
        l4_null_reproduction=c02["l4_null_reproduction"],
        refit_decomposition=c03["decomposition"], absolute_accounting=c03["accounting"],
        placebo_tiers=c04["placebo_tiers"], random_tier_null=c04["random_tier_null"],
        negative_control=c04["negative_control"], negative_control_clean=c04["control_clean"],
        axis_resolution=c05["axis"], concentration_increment_null=c05["concentration_null"],
        what_is_settled=[
            "REFIT ARTEFACT IS REFUTED. Transplanting the POOLED non-defence coefficients and "
            "adding only a defence term recovers 99% of D098's +0.023863; the pooled tier-step "
            "model recovers 92%; the refit's own contribution is generic across terciles (T3 "
            "+0.0333, T2 +0.0338) while the defence gain is specific to the top one.",
            "THE +0.024 vs +0.0002 TENSION IS AN ARTEFACT OF TWO DIFFERENT CONTRASTS ON TWO "
            "DIFFERENT ROW SETS. +0.0002 is a linear interaction's increment OVER a model that "
            "already carries defence, scored on all 4,514 decision rows; +0.024 is the whole "
            "defence family's increment over a NO-defence model, scored on 1,687 top-tercile rows. "
            "Put on the same footing the linear interaction is +0.004466 on those rows, not "
            "+0.0002.",
            "A STEP DOES BEAT A LINE, AND THAT PART OF THE THRESHOLD READING IS CORRECT. On the "
            "full decision stratum the tier step adds +0.003317 over one pooled coefficient where "
            "the linear interaction adds +0.000203 -- a factor of 16. The step's own increment "
            "clears the within-date opponent-swap null at z=+3.55, p=0.0020.",
            "THE CONCENTRATION IS REAL IN ABSOLUTE TERMS AND IS NOT A DENOMINATOR EFFECT. The "
            "identical pooled coefficient reduces SSE by +1.3506 on the top tercile while reducing "
            "it by only +1.1378 over the whole stratum -- it HURTS the bottom two terciles "
            "(-0.0472 and -0.1656). sd(T3)/sd(all) = 0.976, so the subset is not simply a "
            "lower-variance target.",
            "THE AXIS IS 'THIS PLAYER SCORES A LOT', NOT MINUTES PLAYED, AND USAGE CANNOT BE "
            "SEPARATED FROM PRIOR SCORING RATE."],
        what_is_not_settled=[
            "WHETHER THE TOP TERCILE IS SPECIAL RELATIVE TO ANY EQUALLY SIZED SUBSET. Against a "
            "size-matched random-tier null the observed gain clears at one-sided p 0.0180 (row "
            "shuffle) and 0.0459 (player-season blocks). That is significant but thin, and it is a "
            "far weaker statement than the z of +12.80 against the opponent-swap null, which holds "
            "the subset fixed and cannot address it.",
            "WHETHER THE ARITHMETIC CEILING OF 0.01280821 IS COMPARABLE TO D079/D084/D089. IT WAS "
            "NOT RECOMPUTED HERE. It was measured on the same 1,687-row subset, and the dR2 on that "
            "subset is inflated roughly 2.8x relative to a common-denominator reading (+0.016772 "
            "with the subset's own SST against +0.005968 with the stratum's). The '6.2x the largest "
            "the programme has measured' claim should be treated as unverified until the ceiling is "
            "recomputed on a common denominator."],
        what_would_resolve_it=[
            "Recompute the arithmetic ceiling and the headline dR2 on the FULL decision stratum's "
            "SST so the number is comparable to D079 (0.001127), D084 (0.000129) and D089 "
            "(0.002057). `absolute_accounting.csv` already supplies the common-denominator dR2s: "
            "+0.005968 (ppm) and +0.004909 (points).",
            "Re-run the random-tier null with degenerate draws screened out (the player-block "
            "variant's null has sd 0.0516 and a max of 0.6485, driven by draws whose training folds "
            "are near-collinear; a variance-stabilised or trimmed null would give the concentration "
            "claim a fair test) and with more than 500 draws.",
            "Score the pooled tier-step model -- L3, which needs no refit and is a single deployable "
            "model -- as the candidate, rather than the tier-restricted refit. It is 92% of the "
            "gain, it is one model rather than three, and it is the specification that would "
            "actually ship.",
            "An out-of-partition or market confirmation. Neither exists inside 2021-2024 and this "
            "screen may not read 2025/2026."],
        scope=dict(
            wrote_only_in=cb.OUT,
            d098_directory="READ ONLY; its modules were imported under python -B and "
                           "sys.dont_write_bytecode, so no __pycache__ was created there",
            ledgers="registry.jsonl / DECISION_LEDGER.jsonl / GRAPH_EVENTS.jsonl / idea_log.jsonl "
                    "were NEVER read or written by this screen",
            screen_kit="not imported; D098's machinery was used instead so the numbers are "
                       "comparable",
            partition="2021-2024 only, enforced on values; 2025/2026 never read, joined, plotted or "
                      "described",
            champion="never loaded, scored, retrained or modified"))

    with open(os.path.join(cb.OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
        json.dump(findings, fh, indent=2, default=float)

    cb.hdr("VERDICT: %s" % findings["VERDICT"])
    P(findings["VERDICT_ONE_LINE"])
    P.write(os.path.join(cb.OUT, "run_log_c06.txt"))

    # one combined log
    parts = []
    for f in ("run_log_c00.txt", "run_log_c01.txt", "run_log_c02.txt", "run_log_c03.txt",
              "run_log_c04.txt", "run_log_c05.txt", "run_log_c06.txt"):
        p = os.path.join(cb.OUT, f)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                parts.append("\n\n########## %s ##########\n" % f + fh.read())
    with open(os.path.join(cb.OUT, "run_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    print("wrote FINDINGS.json and run_log.txt")


if __name__ == "__main__":
    main()
