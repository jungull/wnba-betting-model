"""verify.py -- re-derive EVERY headline number of E1_I0058 from the artifacts on disk.

Exits non-zero on the first discrepancy. Nothing here reads a conclusion and agrees with it:
the deterministic statistics are recomputed from `out/analysis_frame.csv` and compared against
what `s02_score.py` wrote, and the prose in NOTES.md is checked to contain the numbers it quotes.

  python scripts/verify.py           # hashes, partition, all deterministic statistics, prose
  python scripts/verify.py --full    # additionally re-runs the seeded bootstrap + permutation null

`--full` re-runs 5,000-draw resampling and takes a few minutes.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mb_base as mb  # noqa: E402

FULL = "--full" in sys.argv
TOL = 1e-9
FAILURES: list[str] = []
CHECKS = [0]


def check(label, ok, detail=""):
    CHECKS[0] += 1
    if ok:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}   {detail}")
        FAILURES.append(f"{label}   {detail}")


def close(label, got, want, tol=TOL):
    check(label, abs(float(got) - float(want)) <= tol,
          f"got {got!r} want {want!r} (tol {tol})")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


P = lambda *a: os.path.join(mb.EXP_DIR, *a)  # noqa: E731

R = json.load(open(P("out", "s02_results.json")))
LP = json.load(open(P("out", "leak_proof.json")))
FD = json.load(open(P("FINDINGS.json")))
NOTES = open(P("NOTES.md"), encoding="utf-8").read()

print("=" * 88)
print("E1_I0058_market_benchmark -- VERIFICATION")
print("=" * 88)

# ------------------------------------------------------------------ 1. THE FREEZE
print("\n[1] FREEZE AND PROVENANCE")
recorded_pre = open(P("PREREG.sha256")).read().split()[0]
actual_pre = sha256_file(P("PREREG.md"))
check("PREREG.md sha256 re-derives to its recorded freeze value",
      actual_pre == recorded_pre, f"disk {actual_pre} vs recorded {recorded_pre}")
check("PREREG.md byte count matches the freeze record",
      os.path.getsize(P("PREREG.md")) == int(
          re.search(r"bytes=(\d+)", open(P("PREREG.sha256")).read()).group(1)))
check("s02 results were produced under that same PREREG hash",
      R["prereg_sha256"] == actual_pre)
check("leak_proof was produced under that same PREREG hash",
      LP["prereg_sha256"] == actual_pre)
check("FINDINGS.json carries that same PREREG hash", FD["prereg_sha256"] == actual_pre)

actual_frame = sha256_file(P("out", "analysis_frame.csv"))
check("analysis_frame.csv sha256 re-derives to the value s01 recorded at build time",
      actual_frame == LP["analysis_frame_sha256"],
      f"disk {actual_frame} vs recorded {LP['analysis_frame_sha256']}")
check("FINDINGS.json carries that same frame hash",
      FD["analysis_frame_sha256"] == actual_frame)

# ------------------------------------------------------------------ 2. THE PARTITION
print("\n[2] PARTITION -- THE HOLDOUT MUST BE UNTOUCHED")
A = pd.read_csv(P("out", "analysis_frame.csv"))
A["game_date"] = pd.to_datetime(A.game_date)
check("frame contains season 2024 and nothing else", set(A.season.unique()) == {2024},
      str(sorted(A.season.unique())))
check("zero rows from holdout seasons (recorded)", LP["rows_from_holdout_seasons"] == 0)
check("zero rows dated after the partition (recorded)", LP["rows_dated_after_partition"] == 0)
check("no row in the frame is dated after 2024-12-31",
      bool((A.game_date <= pd.Timestamp("2024-12-31")).all()),
      str(A.game_date.max()))
check("no row in the frame is dated before the 2024 season opener",
      bool((A.game_date >= pd.Timestamp("2024-01-01")).all()), str(A.game_date.min()))
check("sigma(.) was calibrated on 2021-2023 only",
      LP["sigma_calibration_seasons"] == [2021, 2022, 2023])
check("holdout rows excluded = total - admitted",
      LP["props_rows_excluded_as_holdout_or_later"]
      == LP["props_rows_total"] - LP["props_rows_admitted"])
check("row count 1972", len(A) == 1972 == LP["analysis_rows"] == R["n"])
check("78 players", A.player_id.nunique() == 78 == LP["n_players"])
check("262 games", A.gid.nunique() == 262 == LP["n_games"])
check("date span 2024-05-14 .. 2024-10-20",
      str(A.game_date.min().date()) == LP["analysis_game_date_min"] == "2024-05-14"
      and str(A.game_date.max().date()) == LP["analysis_game_date_max"] == "2024-10-20")
check("row_uid is unique -- one row per player-game obligation", A.row_uid.is_unique)
check("pts is present for every row (it is the response)", int(A.pts.isna().sum()) == 0)

# ------------------------------------------------------------------ 3. ACCURACY
print("\n[3] STANDALONE ACCURACY -- RECOMPUTED FROM THE FRAME, NOT READ BACK")
y = A.pts.values.astype(float)
for arm in ["M1", "M2", "M3", "F1", "F2"]:
    v = A[arm].values.astype(float)
    ok = np.isfinite(v)
    e = v[ok] - y[ok]
    close(f"{arm} MAE", np.abs(e).mean(), R["accuracy"][arm]["mae"])
    close(f"{arm} RMSE", np.sqrt((e ** 2).mean()), R["accuracy"][arm]["rmse"])
    close(f"{arm} bias", e.mean(), R["accuracy"][arm]["bias"])
    close(f"{arm} corr", np.corrcoef(v[ok], y[ok])[0, 1], R["accuracy"][arm]["corr"])
    check(f"{arm} n", int(ok.sum()) == R["accuracy"][arm]["n"])

print("\n[3b] R-SQUARED LADDER -- EVERY CELL")
psm = A.groupby("player_id").pts.transform("mean").values
refs = {"R0_grand_mean": np.full(len(A), y.mean()),
        "R1_player_season_mean__RETROSPECTIVE": psm,
        "R2_market_raw": A.M1.values.astype(float)}
for arm in ["M1", "M2", "M3", "F1", "F2"]:
    v = A[arm].values.astype(float)
    ok = np.isfinite(v)
    for rn, rv in refs.items():
        got = 1 - ((v[ok] - y[ok]) ** 2).sum() / ((rv[ok] - y[ok]) ** 2).sum()
        close(f"R2 {arm} vs {rn}", got, R["r2_ladder"][arm][rn])
check("the declared honest reference is R0_grand_mean",
      FD["declared_honest_reference"] == "R0_grand_mean")
check("R1 is labelled RETROSPECTIVE in the ladder key",
      "RETROSPECTIVE" in "".join(R["r2_ladder"]["F1"].keys()))

# ------------------------------------------------------------------ 4. REGRESSIONS
print("\n[4] REGRESSIONS -- COEFFICIENTS REFITTED FROM THE FRAME")
MODELS = {"UNI_M1": ["M1"], "UNI_M2": ["M2"], "UNI_F1": ["F1"],
          "ENC_M2_F1": ["M2", "F1"], "ENC_M1_F1": ["M1", "F1"], "ENC_M2_F2": ["M2", "F2"]}


def ols(X, yy):
    return np.linalg.lstsq(X, yy, rcond=None)[0]


def fit(cols):
    idx = A[["pts"] + cols].dropna().index
    X = np.column_stack([np.ones(len(idx))]
                        + [A.loc[idx, c].values.astype(float) for c in cols])
    yy = A.loc[idx, "pts"].values.astype(float)
    b = ols(X, yy)
    res = yy - X @ b
    return idx, b, res, yy


for name, cols in MODELS.items():
    idx, b, res, yy = fit(cols)
    check(f"{name} n", len(idx) == R["fits"][name]["n"])
    close(f"{name} const", b[0], R["fits"][name]["coef"]["const"])
    for i, c in enumerate(cols):
        close(f"{name} {c}", b[i + 1], R["fits"][name]["coef"][c])
    close(f"{name} R2(R0)", 1 - (res ** 2).sum() / ((yy - yy.mean()) ** 2).sum(),
          R["fits"][name]["r2_R0"])
    close(f"{name} in-sample MAE", np.abs(res).mean(), R["fits"][name]["mae"])

close("corr(M2,F1)", A[["M2", "F1"]].corr().iloc[0, 1], R["corr_M2_F1"])

# ------------------------------------------------------------------ 5. THE VERDICTS
print("\n[5] THE FIVE PREREGISTERED PREDICTIONS -- VERDICTS RE-DERIVED FROM FIRST PRINCIPLES")
MAT = 0.10
bF = R["ci"]["ENC_M2_F1|F1"]
bM = R["ci"]["ENC_M2_F1|M2"]
pF = R["perm"]["ENC_M2_F1|F1"]
pM = R["perm"]["ENC_M2_F1|M2"]

# PREREG section 5: BOTH criteria required.
dist_F = bF["excludes_zero"] and pF["p_two_sided"] < 0.05
dist_M = bM["excludes_zero"] and pM["p_two_sided"] < 0.05

check("CI 'excludes_zero' flag for bF agrees with its own interval",
      bF["excludes_zero"] == (not (bF["ci_headline"][0] <= 0 <= bF["ci_headline"][1])))
check("CI 'excludes_zero' flag for bM agrees with its own interval",
      bM["excludes_zero"] == (not (bM["ci_headline"][0] <= 0 <= bM["ci_headline"][1])))
check("the headline CI is the WIDER of GAME and PLAYER, as preregistered, for bF",
      abs(bF["ci_headline"][1] - bF["ci_headline"][0])
      >= max(abs(bF["ci_game"][1] - bF["ci_game"][0]),
             abs(bF["ci_player"][1] - bF["ci_player"][0])) - TOL)
check("the headline CI is the WIDER of GAME and PLAYER, as preregistered, for bM",
      abs(bM["ci_headline"][1] - bM["ci_headline"][0])
      >= max(abs(bM["ci_game"][1] - bM["ci_game"][0]),
             abs(bM["ci_player"][1] - bM["ci_player"][0])) - TOL)

mae_gap = R["accuracy"]["F1"]["mae"] - R["accuracy"]["M2"]["mae"]
check("P1 PASS -- market beats model by more than the 0.10 floor",
      (mae_gap > MAT) and FD["predictions"]["P1"]["verdict"] == "PASS", f"gap {mae_gap:.4f}")
check("P2 PASS -- bF NOT distinguishable under section 5 (both criteria required)",
      (not dist_F) and FD["predictions"]["P2"]["verdict"] == "PASS")
check("P2 records the section-7 wording conflict rather than hiding it",
      "CONFLICT" in FD["predictions"]["P2"]
      and FD["predictions"]["P2"]["verdict_under_literal_section_7_wording"] == "FAIL")
check("P2's two criteria are recorded individually",
      FD["predictions"]["P2"]["criterion_i_ci_excludes_zero"] is True
      and FD["predictions"]["P2"]["criterion_ii_perm_p_lt_05"] is False)
check("P3 PASS -- bM IS distinguishable (both criteria hold)",
      dist_M and FD["predictions"]["P3"]["verdict"] == "PASS")
check("P4 FAIL -- de-vig gain below the 0.05 threshold",
      (R["p4"]["mae_M1_minus_M2"] < 0.05) and FD["predictions"]["P4"]["verdict"] == "FAIL",
      f"gain {R['p4']['mae_M1_minus_M2']:.4f}")
check("P5 FAIL -- the raw-line bias CI includes zero",
      (R["p5"]["ci"][0] <= 0 <= R["p5"]["ci"][1])
      and FD["predictions"]["P5"]["verdict"] == "FAIL", str(R["p5"]["ci"]))
check("summary block agrees with the per-prediction verdicts",
      FD["predictions_summary"] == {"P1": "PASS", "P2": "PASS", "P3": "PASS",
                                    "P4": "FAIL", "P5": "FAIL"})

print("\n[5b] THE GATE ON SUBGROUPS")
check("section 8 was NOT run", FD["subgroups_section_8"]["run"] is False)
check("section 8 was gated on bF being distinguishable, which it is not", not dist_F)
check("no subgroup key leaked into FINDINGS.json",
      not any(k.startswith(("S1", "S2", "S3", "S4")) for k in FD))

# ------------------------------------------------------------------ 6. MATERIALITY / POWER
print("\n[6] MATERIALITY AND POWER")
close("MDE(bF) = 2.802 * SD_boot(bF)", 2.802 * R["mde"]["sd_bF"], R["mde"]["MDE_bF"], 1e-6)
check("MDE(bF) in MAE points is BELOW the 0.10 materiality floor -> null is informative",
      abs(R["mde"]["mae_gain_at_mde"]) < MAT and FD["power_MDE"]["null_is_informative"] is True,
      f"{abs(R['mde']['mae_gain_at_mde']):.4f}")
comb = R["combination"]
gain_in = comb["mae_blend_insample"] - comb["mae_market_fit_insample"]
gain_cv = comb["mae_blend_logocv__POSTHOC"] - comb["mae_market_fit_logocv__POSTHOC"]
check("in-sample blend gain is below the materiality floor", abs(gain_in) < MAT,
      f"{gain_in:.4f}")
check("leave-one-game-out blend gain is below the materiality floor", abs(gain_cv) < MAT,
      f"{gain_cv:.4f}")
check("the LOGO-CV figure is labelled POST-HOC in FINDINGS.json",
      "POSTHOC" in "".join(FD["combination_value"].keys()))
close("FINDINGS in-sample gain matches the results file", FD["combination_value"]["gain_insample"],
      gain_in)
close("FINDINGS LOGO-CV gain matches the results file",
      FD["combination_value"]["gain_logocv__POSTHOC"], gain_cv)

# ------------------------------------------------------------------ 7. HONESTY OF THE PROSE
print("\n[7] THE PROSE QUOTES THE ARTIFACTS -- NUMBERS CHECKED AS STRINGS IN NOTES.md")
QUOTED = {
    "M2 MAE 4.9043": "4.9043", "F1 MAE 5.3232": "5.3232", "MAE gap 0.4189": "0.4189",
    "bM +1.0978": "1.0978", "bF -0.1604": "0.1604", "bM CI lo 0.9556": "0.9556",
    "bM CI hi 1.2450": "1.2450", "bF CI lo -0.3012": "0.3012", "bF CI hi -0.0248": "0.0248",
    "perm p bF 0.7111": "0.7111", "perm p bM 0.0002": "0.0002",
    "null mean +0.1882": "0.1882", "MDE 0.1987": "0.1987", "MDE in MAE 0.0351": "0.0351",
    "blend gain in-sample 0.0079": "0.0079", "blend gain LOGO-CV 0.0051": "0.0051",
    "P4 gain 0.0188": "0.0188", "P5 bias 0.1691": "0.1691",
    "corr(M2,F1) 0.8643": "0.8643", "n=1972": "1,972", "78 players": "78",
    "262 games": "262", "40.2% selection": "40.2%",
}
for label, s in QUOTED.items():
    check(f"NOTES.md quotes {label}", s in NOTES)

check("NOTES.md states the conditional population up front", "40.2%" in NOTES
      and "Books price the players they choose to price" in NOTES)
check("NOTES.md labels R1 as retrospective", "RETROSPECTIVE" in NOTES)
check("NOTES.md carries the D2 caveat with the permutation p-value",
      "DEFECTS.md` D2" in NOTES or "DEFECTS.md D2" in NOTES)
check("NOTES.md does not claim an edge",
      not re.search(r"\b(we beat the market|our edge|profitable|the model wins)\b",
                    NOTES, re.I))
check("FINDINGS headline states the market encompasses the model",
      "MARKET ENCOMPASSES THE MODEL" in FD["HEADLINE"].upper())
check("FINDINGS carries the conditional-population statement",
      "40.2%" in FD["POPULATION_SELECTION_STATEMENT"])
check("the decision-id conflict is recorded", FD["decision_id"] == "D141"
      and FD["decision_id_printed_inside_frozen_PREREG"] == "D138")
check("evidence level is E1 and no higher", FD["evidence_level"] == "E1")

for f in ["PREREG.md", "PREREG.sha256", "NOTES.md", "DEFECTS.md", "PARTITION_PROOF.md",
          "FINDINGS.json", "ENCOMPASSING.csv", "run_log_s00.txt", "run_log_s01.txt",
          "run_log_s02.txt", "out/analysis_frame.csv", "out/leak_proof.json",
          "out/s00_shape.json", "out/s02_results.json"]:
    check(f"artifact present and non-empty: {f}",
          os.path.exists(P(*f.split("/"))) and os.path.getsize(P(*f.split("/"))) > 0)

E = pd.read_csv(P("ENCOMPASSING.csv"))
check("ENCOMPASSING.csv covers all six fitted models", set(E.model.unique()) == set(MODELS))
row = E[(E.model == "ENC_M2_F1") & (E.term == "F1")].iloc[0]
close("ENCOMPASSING.csv bF matches the results file", row.coef, bF["coef"])
close("ENCOMPASSING.csv bF permutation p matches", row.perm_p_two_sided, pF["p_two_sided"])

# ------------------------------------------------------------------ 8. FULL RESAMPLING
if FULL:
    print("\n[8] --full: RE-RUNNING THE SEEDED BOOTSTRAP AND PERMUTATION NULL")
    SEED_BOOT, SEED_PERM, N = 20240817, 20240818, 5000

    def cluster_boot(cols, cluster_col, seed, ndraw):
        idx = A[["pts"] + cols].dropna().index
        D = A.loc[idx]
        yy = D.pts.values.astype(float)
        X = np.column_stack([np.ones(len(D))] + [D[c].values.astype(float) for c in cols])
        codes, uniq = pd.factorize(D[cluster_col])
        order = np.argsort(codes, kind="stable")
        Xs, ys, cs = X[order], yy[order], codes[order]
        starts = np.searchsorted(cs, np.arange(len(uniq)))
        ends = np.searchsorted(cs, np.arange(len(uniq)), side="right")
        members = [np.arange(s, e) for s, e in zip(starts, ends)]
        rng = np.random.default_rng(seed)
        out = np.empty((ndraw, X.shape[1]))
        G = len(uniq)
        for d in range(ndraw):
            sel = np.concatenate([members[i] for i in rng.integers(0, G, G)])
            out[d] = ols(Xs[sel], ys[sel])
        return out

    for tag, cl in (("GAME", "gid"), ("PLAYER", "player_id")):
        b = cluster_boot(["M2", "F1"], cl, SEED_BOOT, N)
        lo, hi = np.nanpercentile(b[:, 2], 2.5), np.nanpercentile(b[:, 2], 97.5)
        close(f"bF BOOT_{tag} CI lo re-derives", lo, bF[f"ci_{tag.lower()}"][0], 1e-9)
        close(f"bF BOOT_{tag} CI hi re-derives", hi, bF[f"ci_{tag.lower()}"][1], 1e-9)

    def cyclic_perm_null(cols, shift_col, seed, ndraw):
        idx = A[["pts"] + cols].dropna().index
        D = A.loc[idx].sort_values(["player_id", "game_date"]).copy()
        yy = D.pts.values.astype(float)
        base = {c: D[c].values.astype(float) for c in cols}
        codes, uniq = pd.factorize(D.player_id)
        members = [np.where(codes == i)[0] for i in range(len(uniq))]
        rng = np.random.default_rng(seed)
        j = cols.index(shift_col)
        src = base[shift_col]
        Xcols = [np.ones(len(D))] + [base[c].copy() for c in cols]
        out = np.empty(ndraw)
        for d in range(ndraw):
            v = src.copy()
            for mm in members:
                if len(mm) < 2:
                    continue
                v[mm] = np.roll(src[mm], int(rng.integers(1, len(mm))))
            Xcols[1 + j] = v
            out[d] = ols(np.column_stack(Xcols), yy)[1 + j]
        return out

    nulls = cyclic_perm_null(["M2", "F1"], "F1", SEED_PERM, N)
    p = (1 + (np.abs(nulls) >= abs(bF["coef"])).sum()) / (1 + N)
    close("bF permutation p re-derives exactly", p, pF["p_two_sided"], 1e-12)
    close("bF null mean re-derives", nulls.mean(), pF["null_mean"], 1e-9)
    check("the null is NOT centred at zero -- DEFECTS.md D2 is factually correct",
          nulls.mean() > 0.10 and np.percentile(nulls, 2.5) > 0,
          f"null mean {nulls.mean():.4f}, 2.5th pct {np.percentile(nulls, 2.5):.4f}")
    check("the observed bF lies BELOW the entire null 95% interval (POST-HOC observation)",
          bF["coef"] < np.percentile(nulls, 2.5))
else:
    print("\n[8] SKIPPED -- pass --full to re-run the seeded bootstrap and permutation null")

print("\n" + "=" * 88)
if FAILURES:
    print(f"VERIFICATION FAILED -- {len(FAILURES)} of {CHECKS[0]} checks failed")
    for f in FAILURES:
        print("   *", f)
    sys.exit(1)
print(f"VERIFICATION PASSED -- {CHECKS[0]}/{CHECKS[0]} checks")
print("Every headline number re-derives from the artifacts on disk.")
print("=" * 88)
