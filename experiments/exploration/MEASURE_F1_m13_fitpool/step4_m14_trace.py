#!/usr/bin/env python3
"""STEP 4 -- trace the defect FORWARD into M14.

Run 1 (CONTROL): the patched M14 copy against the REAL, PUBLISHED M13 output.
                 If this does not reproduce M14's published result_hash and
                 falsification slope exactly, the trace is attributable to the
                 harness and is reported as such rather than to the defect.
Run 2..n       : the same M14 copy against each counterfactual
                 cf_<variant>/translation_rows.parquet produced by step3.

M14 and M13 are NEVER written to; M14's output dir is redirected by env var.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
M14_PUB = json.loads((WORKTREE / "experiments" / "market_program" / "M14_MODEL_MARKET_RESIDUAL"
                      / "FINDINGS.json").read_text(encoding="utf-8"))

RUNNER = HERE / "_m14_runner.py"
RUNNER.write_text(
    "import sys, pathlib\n"
    f"sys.path.insert(0, r'{HERE}')\n"
    "import m14_lib\n"
    "m14_lib.main()\n", encoding="utf-8")

RUNS = [
    ("CONTROL_PUBLISHED_M13",
     WORKTREE / "experiments" / "market_program" / "M13_PLAYER_VALUE_TRANSLATION"),
    ("A_POOLED_PUBLISHED", HERE / "cf_A_POOLED_PUBLISHED"),
    ("B_POOLED_2022_2024", HERE / "cf_B_POOLED_2022_2024"),
    ("C_TIME_ORDERED", HERE / "cf_C_TIME_ORDERED"),
    ("D_TIME_ORDERED_2022_2024", HERE / "cf_D_TIME_ORDERED_2022_2024"),
]


def summarize(f: dict) -> dict:
    fa = f["falsification"]
    p = fa["pooled_headline"]
    return {
        "result_hash": f["result_hash"],
        "verdict": fa["verdict"],
        "pooled_n": p["n"],
        "pooled_slope": p["slope"],
        "pooled_intercept": p["intercept"],
        "slope_ci95_lo": p["slope_ci95"]["lo"],
        "slope_ci95_hi": p["slope_ci95"]["hi"],
        "slope_ci95_width": p["slope_ci95"]["hi"] - p["slope_ci95"]["lo"],
        "slope_distinguishable_from_zero": p["slope_distinguishable_from_zero"],
        "slope_by_variant": {v: fa["by_translation_variant_headline"][v]["slope"]
                             for v in fa["by_translation_variant_headline"]},
        "slope_by_season": {s: fa["by_season_headline"][s]["slope"]
                            for s in fa["by_season_headline"]},
        "slope_by_season_sig": {s: fa["by_season_headline"][s]["slope_distinguishable_from_zero"]
                                for s in fa["by_season_headline"]},
        "influence": {k: v["slope"] for k, v in fa["influence_leave_out_top_n"].items()},
    }


def main():
    results = {}
    for tag, m13dir in RUNS:
        outdir = HERE / "m14_out" / tag
        env = dict(os.environ, M14_M13_DIR=str(m13dir), M14_OUT_DIR=str(outdir))
        print("=" * 70)
        print("M14 run:", tag, "<-", m13dir)
        if "--summarize-only" in sys.argv and (outdir / "FINDINGS.json").exists():
            print("  (reusing existing M14 output; no re-run)")
            r = subprocess.CompletedProcess([], 0, "", "")
        else:
            r = subprocess.run([sys.executable, str(RUNNER)], env=env,
                               capture_output=True, text=True)
            print("\n".join((r.stdout or "").strip().splitlines()[-6:]))
        if r.returncode != 0:
            print("STDERR:", (r.stderr or "")[-3000:])
            results[tag] = {"error": "M14 run failed", "stderr": (r.stderr or "")[-3000:]}
            continue
        f = json.loads((outdir / "FINDINGS.json").read_text(encoding="utf-8"))
        results[tag] = summarize(f)
        print("  slope:", results[tag]["pooled_slope"], " verdict:", results[tag]["verdict"])

    pub = summarize(M14_PUB)
    ctrl = results.get("CONTROL_PUBLISHED_M13", {})
    control_ok = {
        "result_hash_identical": ctrl.get("result_hash") == pub["result_hash"],
        "verdict_identical": ctrl.get("verdict") == pub["verdict"],
        "pooled_slope_abs_delta": (abs(ctrl["pooled_slope"] - pub["pooled_slope"])
                                   if "pooled_slope" in ctrl else None),
        "slope_ci_lo_abs_delta": (abs(ctrl["slope_ci95_lo"] - pub["slope_ci95_lo"])
                                  if "slope_ci95_lo" in ctrl else None),
        "slope_ci_hi_abs_delta": (abs(ctrl["slope_ci95_hi"] - pub["slope_ci95_hi"])
                                  if "slope_ci95_hi" in ctrl else None),
    }
    _d = [control_ok["pooled_slope_abs_delta"], control_ok["slope_ci_lo_abs_delta"],
          control_ok["slope_ci_hi_abs_delta"]]
    control_ok["max_abs_numeric_delta"] = max(_d) if all(x is not None for x in _d) else None
    control_ok["M14_HARNESS_REPRODUCES_PUBLISHED"] = bool(
        control_ok["verdict_identical"] and control_ok["result_hash_identical"]
        and control_ok["max_abs_numeric_delta"] == 0.0)

    deltas = {}
    base = results.get("A_POOLED_PUBLISHED", {})
    for tag in ("B_POOLED_2022_2024", "C_TIME_ORDERED", "D_TIME_ORDERED_2022_2024"):
        v = results.get(tag, {})
        if "pooled_slope" not in v or "pooled_slope" not in base:
            continue
        deltas[f"{tag}_vs_A"] = {
            "slope_published_A": base["pooled_slope"], "slope_variant": v["pooled_slope"],
            "slope_abs_delta": abs(v["pooled_slope"] - base["pooled_slope"]),
            "slope_delta_as_fraction_of_A_CI_width":
                abs(v["pooled_slope"] - base["pooled_slope"]) / base["slope_ci95_width"],
            "ci_width_A": base["slope_ci95_width"], "ci_width_variant": v["slope_ci95_width"],
            "ci_width_ratio_variant_over_A": v["slope_ci95_width"] / base["slope_ci95_width"],
            "verdict_A": base["verdict"], "verdict_variant": v["verdict"],
            "verdict_flips": bool(v["verdict"] != base["verdict"]),
            "still_sig_at_zero": v["slope_distinguishable_from_zero"],
        }

    out = {"m14_published": pub, "runs": results,
           "control_check_vs_published_M14": control_ok,
           "m14_deltas_vs_published_pooled_fit": deltas}
    (HERE / "step4_m14_trace.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print()
    print(json.dumps(control_ok, indent=1))
    print(json.dumps(deltas, indent=1))


if __name__ == "__main__":
    main()
