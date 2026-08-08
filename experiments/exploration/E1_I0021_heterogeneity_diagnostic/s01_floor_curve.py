"""
s01 -- STEP 1: REPRODUCE D081 AT FLOOR 0, THEN THE MINUTES-FLOOR SENSITIVITY CURVE.

REPRODUCTION FIRST.  D081's published per-component skills are recomputed from its frozen
decomp_frame.parquet and compared cell by cell to its own component_skill.csv.  If they do not
reproduce, this script STOPS and says so; nothing downstream is meaningful otherwise.

THEN, for each realised-minutes floor in the preregistered grid, every one of D081's nine cells is
recomputed on the retained rows against TWO references:

  FROZEN reference -- D081's published prior-only reference, simply subset to the retained rows.
      Model and reference face the SAME rows.  The reference was built over all prior games, so it
      does NOT get the denoising benefit.
  REFIT reference  -- the identical construction rebuilt so its expanding prior windows see only
      the player's prior games that THEMSELVES cleared the floor.  The reference now enjoys exactly
      the same denoising the response enjoys.

THE HONEST NUMBER IS THE REFIT ONE.  A rising skill curve against the frozen reference is partly
MECHANICAL -- noisy rows are being deleted from the response, which shrinks the denominator of the
rate for everyone.  Only the refit column answers "is the model better than a like-for-like
reference facing the same filtered rows".  Both are reported side by side at every floor.

The response variance decomposition is also reported at every floor: total variance of
points-per-minute, and its split into BETWEEN-player and WITHIN-player parts, so it is visible how
much of the per-minute variance the floor is actually removing and from where.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import hd_base as hb  # noqa: E402
import s00_prereg as pr  # noqa: E402

REPRO_TOL = 5e-6   # absolute tolerance on skill; D081 published to far more digits than this


def check_prereg():
    with open(os.path.join(hb.OUT, "_prereg.json"), encoding="utf-8") as fh:
        on_disk = json.load(fh)
    h = on_disk.pop("prereg_sha256")
    live = hb.sha({k: v for k, v in pr.PREREG.items() if k != "prereg_sha256"})
    assert h == live, "PREREG HASH MISMATCH: on-disk %s vs live %s" % (h, live)
    ids_disk = [c["component"] + "|" + c["ref_frozen"] for c in on_disk["step1_components"]]
    ids_live = [c["component"] + "|" + c["ref_frozen"] for c in pr.STEP1_COMPONENTS]
    added = [i for i in ids_live if i not in ids_disk]
    dropped = [i for i in ids_disk if i not in ids_live]
    print("  PREREG hash %s VERIFIED. step1 cells added=%d dropped=%d"
          % (h, len(added), len(dropped)))
    return h


def var_decomp(df, col, pcol="player_id"):
    """Total / between-player / within-player variance of `col`.

    between = variance of the player means (weighted by player n); within = mean of the player
    variances.  Reported so the floor's effect on the RESPONSE is visible separately from its
    effect on skill.
    """
    v = pd.to_numeric(df[col], errors="coerce")
    d = pd.DataFrame({"v": v, "p": df[pcol].to_numpy()}).dropna()
    if len(d) < 3:
        return dict(total=np.nan, between=np.nan, within=np.nan, icc=np.nan, n=len(d))
    g = d.groupby("p")["v"]
    n = g.size()
    mu = g.mean()
    grand = float(d["v"].mean())
    total = float(d["v"].var(ddof=1))
    between = float((n * (mu - grand) ** 2).sum() / max(len(d) - 1, 1))
    within = float(((n - 1) * g.var(ddof=1).fillna(0.0)).sum() / max(len(d) - 1, 1))
    return dict(total=total, between=between, within=within,
                icc=(between / total if total > 0 else np.nan), n=int(len(d)),
                n_players=int(len(mu)))


def main():
    log = []

    def P(s=""):
        print(s)
        log.append(str(s))

    hb.hdr("E1_I0021 s01 -- MINUTES-FLOOR SENSITIVITY CURVE")
    h = check_prereg()
    log.append("PREREG hash %s VERIFIED" % h)

    f = hb.load_decomp(verbose=True)
    P("  D081 decomp_frame loaded: %d rows, seasons %s, max date %s"
      % (len(f), sorted(f["season"].unique()), f["gdate"].max().date()))
    P("  partition assert_partition: PASS (values, not names)")

    # ------------------------------------------------------------------ minutes distribution
    m = f["y_minutes"]
    P("")
    P("  REALISED MINUTES distribution (the thing never previously filtered on):")
    P("    min=%.2f  p05=%.2f  p25=%.2f  median=%.2f  p75=%.2f  max=%.2f  mean=%.2f"
      % (m.min(), m.quantile(.05), m.quantile(.25), m.median(), m.quantile(.75), m.max(), m.mean()))
    for fl in pr.MINUTES_FLOOR_GRID:
        P("    rows with realised minutes >= %2d : %5d (%.1f%%)"
          % (fl, int((m >= fl).sum()), 100.0 * (m >= fl).mean()))

    # ------------------------------------------------------------------ REPRODUCTION at floor 0
    hb.hdr("REPRODUCTION -- D081 published component skills at floor 0")
    pub = pd.read_csv(os.path.join(hb.D081, "component_skill.csv"))
    pub_key = {(r["component"], r["reference"]): r for _, r in pub.iterrows()}

    repro_rows = []
    worst = 0.0
    for c in pr.STEP1_COMPONENTS:
        y = f[c["y"]] if c["y"] in f.columns else None
        if y is None:
            raise KeyError("missing y column %s" % c["y"])
        s, mm, mr, n = hb.skill(f[c["y"]], f[c["model"]], f[c["ref_frozen"]])
        pk = pub_key.get((c["component"], c["ref_frozen"]))
        d_skill = s - float(pk["skill"])
        d_n = n - int(pk["n"])
        worst = max(worst, abs(d_skill))
        repro_rows.append(dict(component=c["component"], reference=c["ref_frozen"],
                               n_repro=n, n_published=int(pk["n"]), n_delta=d_n,
                               skill_repro=s, skill_published=float(pk["skill"]),
                               skill_delta=d_skill,
                               model_mae_repro=mm, model_mae_published=float(pk["model_mae"]),
                               ref_mae_repro=mr, ref_mae_published=float(pk["ref_mae"])))
        P("  %-12s %-12s n=%5d (pub %5d, d=%+d)  skill=%+.6f%%  published=%+.6f%%  DELTA=%+.2e"
          % (c["component"], c["ref_frozen"], n, int(pk["n"]), d_n,
             100 * s, 100 * float(pk["skill"]), d_skill))
    repro = pd.DataFrame(repro_rows)
    repro.to_csv(os.path.join(hb.OUT, "reproduction_floor0.csv"), index=False)
    P("")
    P("  worst absolute skill delta across all 9 cells: %.3e  (tolerance %.0e)" % (worst, REPRO_TOL))
    if worst > REPRO_TOL:
        P("  *** REPRODUCTION FAILED -- STOPPING. Nothing downstream would be meaningful. ***")
        with open(os.path.join(hb.OUT, "run_log_s01.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(log))
        raise SystemExit(2)
    P("  REPRODUCTION OK. D081's published figures are reproduced exactly from its frozen frame.")

    # ------------------------------------------------------------------ THE FLOOR CURVE
    hb.hdr("THE MINUTES-FLOOR CURVE  (CONDITIONS ON A REALISED OUTCOME -- NOT A FORECAST GAIN)")
    rows = []
    vrows = []
    for fl in pr.MINUTES_FLOOR_GRID:
        sub = hb.build_floor_references(f, fl, datecol="gdate", mincol="y_minutes", verbose=False)
        n_ret = len(sub)
        vd_ppm = var_decomp(sub, "r_ppm")
        vd_pts = var_decomp(sub, "y_pts")
        vrows.append(dict(floor=fl, n=n_ret, n_players=vd_ppm["n_players"],
                          ppm_sd=float(np.sqrt(vd_ppm["total"])),
                          ppm_var_total=vd_ppm["total"], ppm_var_between=vd_ppm["between"],
                          ppm_var_within=vd_ppm["within"], ppm_icc=vd_ppm["icc"],
                          pts_sd=float(np.sqrt(vd_pts["total"])),
                          pts_var_total=vd_pts["total"], pts_var_between=vd_pts["between"],
                          pts_var_within=vd_pts["within"], pts_icc=vd_pts["icc"],
                          minutes_sd=float(sub["y_minutes"].std(ddof=1)),
                          minutes_mean=float(sub["y_minutes"].mean())))
        P("")
        P("  FLOOR %2d min : n=%5d (%.1f%% of 13879)  players=%3d  ppm sd=%.4f  "
          "ppm var total=%.5f between=%.5f within=%.5f  ICC=%.3f"
          % (fl, n_ret, 100.0 * n_ret / len(f), vd_ppm["n_players"],
             np.sqrt(vd_ppm["total"]), vd_ppm["total"], vd_ppm["between"], vd_ppm["within"],
             vd_ppm["icc"]))
        for c in pr.STEP1_COMPONENTS:
            ycol = c["y"]
            resp = sub[ycol]
            s_fr, mm_fr, mr_fr, n_fr = hb.skill(resp, sub[c["model"]], sub[c["ref_frozen"]])
            s_rf, mm_rf, mr_rf, n_rf = hb.skill(resp, sub[c["model"]], sub[c["ref_refit"]])
            rows.append(dict(
                floor=fl, component=c["component"], kind=c["kind"],
                reference_frozen=c["ref_frozen"], reference_refit=c["ref_refit"],
                n=n_fr, n_players=vd_ppm["n_players"],
                response_sd=float(pd.to_numeric(resp, errors="coerce").std(ddof=1)),
                model_mae=mm_fr,
                ref_mae_frozen=mr_fr, skill_vs_frozen_ref=s_fr,
                ref_mae_refit=mr_rf, skill_vs_refit_ref=s_rf,
                mechanical_part=s_fr - s_rf))
            P("      %-12s %-11s  skill vs FROZEN ref = %+7.3f%%   vs REFIT ref = %+7.3f%%   "
              "(mechanical part %+7.3f%%)  n=%d"
              % (c["component"], c["ref_frozen"], 100 * s_fr, 100 * s_rf,
                 100 * (s_fr - s_rf), n_fr))

    curve = pd.DataFrame(rows)

    # ------------------------------------------------------------------ STRONGEST AVAILABLE REF
    # NEITHER of the two columns above is clean on its own, and saying so is the whole point:
    #   * the FROZEN reference sees MORE prior games (all of them) but none of them denoised;
    #   * the REFIT reference sees DENOISED prior games but FEWER of them, so it pays a sample-size
    #     penalty that flatters the model.
    # The only comparison that cannot be gamed either way is against the BEST reference available
    # at that floor -- the minimum MAE over every prior-only reference in play, frozen or refit,
    # scored on the same rows.  That is the hardest like-for-like reference and it is the number
    # this screen leads with.
    hb.hdr("SKILL AGAINST THE STRONGEST AVAILABLE PRIOR-ONLY REFERENCE AT EACH FLOOR")
    best_rows = []
    by_comp = {}
    for c in pr.STEP1_COMPONENTS:
        by_comp.setdefault((c["component"], c["y"], c["model"]), []).extend(
            [c["ref_frozen"], c["ref_refit"]])
    for fl in pr.MINUTES_FLOOR_GRID:
        sub = hb.build_floor_references(f, fl, datecol="gdate", mincol="y_minutes")
        for (comp, ycol, mcol), refs in by_comp.items():
            refs = sorted(set(refs))
            cand = []
            for rc in refs:
                s_, mm_, mr_, n_ = hb.skill(sub[ycol], sub[mcol], sub[rc])
                cand.append((mr_, rc, s_, mm_, n_))
            cand.sort()
            mr_best, rc_best, s_best, mm_best, n_best = cand[0]
            best_rows.append(dict(floor=fl, component=comp, n=n_best,
                                  best_reference=rc_best, best_ref_mae=mr_best,
                                  model_mae=mm_best, skill_vs_best_ref=s_best,
                                  refs_considered="|".join(refs)))
            P("  floor %2d  %-12s  strongest ref = %-11s  ref_mae=%.6f  model_mae=%.6f  "
              "skill=%+7.3f%%  n=%d"
              % (fl, comp, rc_best, mr_best, mm_best, 100 * s_best, n_best))
    best = pd.DataFrame(best_rows)
    best.to_csv(os.path.join(hb.OUT, "minutes_floor_curve_best_ref.csv"), index=False)
    curve = curve.merge(best[["floor", "component", "best_reference", "best_ref_mae",
                              "skill_vs_best_ref"]], on=["floor", "component"], how="left")
    curve.to_csv(os.path.join(hb.OUT, "minutes_floor_curve.csv"), index=False)
    vdf = pd.DataFrame(vrows)
    vdf.to_csv(os.path.join(hb.OUT, "response_variance_by_floor.csv"), index=False)

    # ------------------------------------------------------------------ summary
    hb.hdr("SUMMARY -- points-per-minute, the response the program failed on")
    ppm = curve[(curve["component"] == "pts_per_min")]
    for _, r in ppm.iterrows():
        P("  floor %2d  ref %-9s  n=%5d  resp_sd=%.4f  skill(frozen)=%+7.3f%%  "
          "skill(refit)=%+7.3f%%" % (r["floor"], r["reference_frozen"], r["n"], r["response_sd"],
                                     100 * r["skill_vs_frozen_ref"], 100 * r["skill_vs_refit_ref"]))
    base = vdf.iloc[0]
    top = vdf.iloc[-1]
    P("")
    P("  ppm variance removed by the floor: total %.5f -> %.5f (%.1f%% gone); within-player "
      "%.5f -> %.5f (%.1f%% gone); between-player %.5f -> %.5f (%.1f%% gone)"
      % (base["ppm_var_total"], top["ppm_var_total"],
         100 * (1 - top["ppm_var_total"] / base["ppm_var_total"]),
         base["ppm_var_within"], top["ppm_var_within"],
         100 * (1 - top["ppm_var_within"] / base["ppm_var_within"]),
         base["ppm_var_between"], top["ppm_var_between"],
         100 * (1 - top["ppm_var_between"] / base["ppm_var_between"])))

    out = {
        "prereg_sha256": h,
        "reproduction": {"ok": True, "worst_abs_skill_delta": worst, "tolerance": REPRO_TOL,
                         "cells": len(repro)},
        "floor_grid": pr.MINUTES_FLOOR_GRID,
        "n_rows_floor0": int(len(f)),
        "curve_rows": int(len(curve)),
        "conditioning_label": "Every floor > 0 conditions on a REALISED outcome. Measurement "
                              "question only; NOT a live forecasting increment.",
    }
    with open(os.path.join(hb.OUT, "_s01.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=float)
    with open(os.path.join(hb.OUT, "run_log_s01.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("")
    P("  wrote minutes_floor_curve.csv, response_variance_by_floor.csv, reproduction_floor0.csv")


if __name__ == "__main__":
    main()
