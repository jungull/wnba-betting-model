"""E1_I0051 -- s06.  SIGN_FLIPS.csv and FINDINGS.json."""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_base as B  # noqa: E402

pd.set_option("display.width", 250)

pc = pd.read_csv(os.path.join(B.OUT, "PRIMARY_CELLS.csv"))
nl = pd.read_csv(os.path.join(B.OUT, "NULLS.csv"))
fw = pd.read_csv(os.path.join(B.OUT, "FAMILYWISE.csv"))
bs = pd.read_csv(os.path.join(B.OUT, "BOOTSTRAP_VARIANCE.csv"))
ss = pd.read_csv(os.path.join(B.OUT, "SEASON_STABILITY.csv"))
cen = pd.read_csv(os.path.join(B.OUT, "CONSTRAINT_CENSUS.csv"))

RESP = "M_level_min"
B.hdr("SIGN_FLIPS -- every re-measured candidate, before and after projection")

prim = pc[(pc["response"] == RESP) & (pc["window"] == "CLEAN_2023_24") &
          (pc["population"] == "DECISION")]
rows = []
for cand in B.CANDIDATES:
    for arm in ("FROZEN", "UNFROZEN"):
        g = prim[(prim["candidate"] == cand) & (prim["arm"] == arm)]
        get = lambda p: float(g[g["projection"] == p]["dr2"].iloc[0])  # noqa: E731
        raw, pb, po = get("RAW"), get("PROJ_BUDGET"), get("PROJ_ORACLE")

        def nn(proj, null):
            q = nl[(nl["candidate"] == cand) & (nl["arm"] == arm) &
                   (nl["projection"] == proj) & (nl["null"] == null)]
            return q.iloc[0] if len(q) else None

        primary_null = "N_TGBLOCK" if cand in B.TG_CONSTANT_CANDIDATES else "N_TGSWAP"
        r_raw, r_pb = nn("RAW", primary_null), nn("PROJ_BUDGET", primary_null)
        s_raw = nn("RAW", "N_PSWAP")
        s_pb = nn("PROJ_BUDGET", "N_PSWAP")

        def fwp(proj):
            q = fw[(fw["candidate"] == cand) & (fw["arm"] == arm) & (fw["projection"] == proj)]
            return float(q["p_familywise"].iloc[0]) if len(q) else np.nan

        def boot(proj):
            q = bs[(bs["candidate"] == cand) & (bs["arm"] == arm) & (bs["projection"] == proj)]
            return (float(q["boot_sd"].iloc[0]), float(q["mde80_bootstrap"].iloc[0])) \
                if len(q) else (np.nan, np.nan)

        sr = ss[(ss["candidate"] == cand) & (ss["arm"] == arm)]
        bsd_raw, mde_raw = boot("RAW")
        bsd_pb, mde_pb = boot("PROJ_BUDGET")
        flip = (np.sign(raw) != np.sign(pb)) and raw != 0 and pb != 0
        rows.append(dict(
            screen="E1_I0051_constraint_sweep", response=RESP,
            row_set="DECISION (n_prior>=8 & prior5_minutes>=24) x CLEAN_2023_24",
            n=int(g["n"].iloc[0]), n_blocks=764, sst_basis="scored rows, unweighted",
            base="B_TUNED prior-minutes EWMA, (h,k) walk-forward on strictly earlier seasons",
            weighting="none", candidate=cand, arm=arm, primary_null=primary_null,
            dr2_RAW=raw, sign_RAW=("+" if raw > 0 else "-"),
            dr2_PROJ_BUDGET=pb, sign_PROJ_BUDGET=("+" if pb > 0 else "-"),
            dr2_PROJ_ORACLE=po, sign_PROJ_ORACLE=("+" if po > 0 else "-"),
            SIGN_FLIPS_RAW_to_PROJ_BUDGET=("YES" if flip else "no"),
            z_RAW=(float(r_raw["z"]) if r_raw is not None else np.nan),
            p_RAW=(float(r_raw["p"]) if r_raw is not None else np.nan),
            null_mean_RAW=(float(r_raw["null_mean"]) if r_raw is not None else np.nan),
            z_PROJ_BUDGET=(float(r_pb["z"]) if r_pb is not None else np.nan),
            p_PROJ_BUDGET=(float(r_pb["p"]) if r_pb is not None else np.nan),
            null_mean_PROJ_BUDGET=(float(r_pb["null_mean"]) if r_pb is not None else np.nan),
            p_PSWAP_RAW=(float(s_raw["p"]) if s_raw is not None else np.nan),
            p_PSWAP_PROJ_BUDGET=(float(s_pb["p"]) if s_pb is not None else np.nan),
            p_familywise_RAW=fwp("RAW"), p_familywise_PROJ_BUDGET=fwp("PROJ_BUDGET"),
            boot_sd_RAW=bsd_raw, mde80_boot_RAW=mde_raw,
            boot_sd_PROJ_BUDGET=bsd_pb, mde80_boot_PROJ_BUDGET=mde_pb,
            obs_over_bootfloor_PROJ_BUDGET=(abs(pb) / mde_pb if mde_pb == mde_pb and mde_pb > 0
                                            else np.nan),
            eval_2023_PROJ_BUDGET=float(sr[sr["projection"] == "PROJ_BUDGET"]["eval_2023"].iloc[0]),
            eval_2024_PROJ_BUDGET=float(sr[sr["projection"] == "PROJ_BUDGET"]["eval_2024"].iloc[0]),
            disclosed_2022_PROJ_BUDGET=float(
                sr[sr["projection"] == "PROJ_BUDGET"]["disclosed_2022"].iloc[0]),
            eval_2023_RAW=float(sr[sr["projection"] == "RAW"]["eval_2023"].iloc[0]),
            eval_2024_RAW=float(sr[sr["projection"] == "RAW"]["eval_2024"].iloc[0]),
            disclosed_2022_RAW=float(sr[sr["projection"] == "RAW"]["disclosed_2022"].iloc[0]),
        ))
sf = pd.DataFrame(rows)
sf.to_csv(os.path.join(B.OUT, "SIGN_FLIPS.csv"), index=False)
print(sf[["candidate", "arm", "dr2_RAW", "dr2_PROJ_BUDGET", "dr2_PROJ_ORACLE",
          "SIGN_FLIPS_RAW_to_PROJ_BUDGET", "p_familywise_RAW", "p_familywise_PROJ_BUDGET"]
         ].to_string(index=False, float_format=lambda x: "%+.6f" % x))

nfl_unf = int((sf[(sf["arm"] == "UNFROZEN") &
                  (sf["candidate"].isin(B.BETWEEN_PLAYER_CANDIDATES))]
               ["SIGN_FLIPS_RAW_to_PROJ_BUDGET"] == "YES").sum())
nfl_fr = int((sf[(sf["arm"] == "FROZEN") &
                 (sf["candidate"].isin(B.BETWEEN_PLAYER_CANDIDATES))]
              ["SIGN_FLIPS_RAW_to_PROJ_BUDGET"] == "YES").sum())
print("\n  UNFROZEN: %d of %d between-player candidates FLIP SIGN"
      % (nfl_unf, len(B.BETWEEN_PLAYER_CANDIDATES)))
print("  FROZEN:   %d of %d between-player candidates FLIP SIGN"
      % (nfl_fr, len(B.BETWEEN_PLAYER_CANDIDATES)))

# ---------------------------------------------------------------------------------------------
B.hdr("FINDINGS.json")
by_screen = cen.drop_duplicates("screen").set_index("screen")["screen_level_classification"]
counts = by_screen.value_counts().to_dict()

fin = dict(
    screen="E1_I0051_constraint_sweep",
    prereg_sha256=B.prereg_sha(),
    partition="Regular Season 2021-2024 ONLY; 2025/2026 never read, joined, merged or described",
    clean_window="2023-2024 (eval); training strictly earlier; 2022 disclosed contrast only",
    decision_stratum="n_prior>=8 AND prior5_minutes>=24 (D081/E1_I0023); n=3167 in 764 team-games",
    census=dict(
        n_screen_directories=int(by_screen.size),
        n_response_rows=int(len(cen)),
        counts_by_screen=counts,
        violated_screens=sorted(by_screen[by_screen == "VIOLATED"].index.tolist()),
        honoured_screens=sorted(by_screen[by_screen == "HONOURED"].index.tolist()),
        not_determinable_screens=sorted(by_screen[by_screen == "NOT-DETERMINABLE"].index.tolist()),
        excluded="E1_I0004_efficiency_transfer (its own ABANDONED.md voids every number)",
    ),
    budget_gate=dict(
        rule="team-game total lands on a rules lattice on >=99% of team-games to within 0.5 units "
             "AND the best pre-tip assertion has MAE <= 2% of the total",
        minutes=dict(passes=True, lattice="1776/1776 within 0.066667 of a multiple of 25",
                     frac_at_200=0.952703, mae_pretip=1.26984, pct_of_total=0.63091, cv=0.029100),
        points=dict(passes=False, cv=0.134400, mae_pretip=8.75004, pct_of_total=10.686),
        attempts=dict(passes=False, cv=0.092410, mae_pretip=4.95242, pct_of_total=7.256),
        possessions=dict(passes=False, cv=0.054620),
        usage_percentage=dict(passes=False, cv=0.137590, team_game_sum_mean=1.7016),
    ),
    budget_violation_measured=dict(
        what="team-game sum of an INDEPENDENTLY modelled minutes forecast, appeared roster",
        base="prior-minutes EWMA h=3 k=0", mean_sum=201.5603, sd_sum=17.2478,
        mae_vs_200=13.0942, frac_within_5_minutes=0.2849,
        comment="the errors cancel in the MEAN, which is why nobody checked the dispersion; the "
                "violation is 10.3x the budget's own pre-tip uncertainty of 1.26984",
    ),
    projection_is_an_improvement=dict(
        response=RESP, row_set="DECISION x CLEAN_2023_24", n=3167, n_blocks=764,
        null="paired sign-flip over whole team-games",
        PROJ_BUDGET_vs_RAW=dict(dr2=0.031318, z=2.17, p=0.0350),
        PROJ_ORACLE_vs_RAW=dict(dr2=0.057525, z=3.47, p=0.0010),
        pooled_all_appeared=dict(n=9056, n_blocks=960,
                                 PROJ_BUDGET_vs_RAW=dict(dr2=0.020020, z=10.89, p=0.0005),
                                 PROJ_ORACLE_vs_RAW=dict(dr2=0.024576, z=11.97, p=0.0005)),
        live_availability="the 200 budget is knowable before tip-off (MAE 0.63091% of the total); "
                          "the DENOMINATOR SET C(g) is still an oracle -- see DEFECTS D-05",
    ),
    sign_flips=dict(
        arm_UNFROZEN=dict(n_flips=nfl_unf, n_between_player=5,
                          flipped=["A1_pts_share_prior", "A2_fga_share_prior", "A4_vac_x_own"]),
        arm_FROZEN=dict(n_flips=nfl_fr, n_between_player=5, flipped=[]),
        familywise_survivors_RAW_UNFROZEN=["A1_pts_share_prior", "A2_fga_share_prior"],
        familywise_survivors_PROJ_BUDGET_UNFROZEN=[],
        counterweight="only A4's flip clears its own block-bootstrap floor (2.94x); A1's clears by "
                      "1.05x and A2's is 0.94x -- BELOW its floor and NOT ESTABLISHED under that "
                      "variance estimate.  See DEFECTS D-09.",
    ),
    arithmetic_control=dict(
        candidate="A5_opp_defrtg (team-game constant)",
        correct_null="N_TGBLOCK", dr2_RAW=-0.001812, dr2_PROJ_BUDGET=-0.000870,
        p_RAW=0.9620, p_PROJ_BUDGET=0.9460,
        vacuous_control="N_TGSWAP is the LITERAL IDENTITY for a team-game-constant column; "
                        "measured null sd 6.513e-19 / 2.171e-19 / and EXACTLY 0.000e+00 in one "
                        "cell.  Run deliberately as a control that cannot fail.",
    ),
    availability_as_constraint=dict(
        P1_roster_sum_is_not_a_budget=dict(
            confirmed=True, roster_cv=0.10706, minutes_cv=0.02910,
            looseness_ratio=14.17,
            conclusion="a roster sum is an OUTCOME, not a budget; projection is not the right "
                       "operation and D112's calibration framing was correct"),
        P2_uniform_rescale_cancels=dict(
            confirmed=True, max_abs_deviation=2.132e-14,
            derived_before_measuring=True,
            corroborates="E1_I0035's measured Xb downstream misallocation 8.912455 min, identical "
                         "to the unrepaired champion to the last digit"),
        new_repair_suggested=False,
        conclusion="NO. The constraint framing derives what E1_I0035 measured and sharpens why Xa "
                   "wins; it suggests no repair the calibration framing missed and adds no fourth "
                   "option.  D112's recommendation stands exactly as recorded.",
    ),
    controls=dict(
        no_op_placebo="deviation EXACTLY 0.000e+00 on all 36 cells, identity asserted first",
        response_placebo="A4/PROJ_BUDGET observed -0.018404 against a placebo range "
                         "[-0.008512, +0.003315] over 200 within-team-game response permutations",
        blind_null_demo="re-run on this screen's own cells; the blind within-player null DESTROYS "
                        "a real survivor here (A1 FROZEN: correct p 0.0025 z +30.48, blind "
                        "p 1.0000 z -3.19 with its null mean +0.030311 sitting ABOVE the observed "
                        "+0.021110) -- the OPPOSITE direction of failure to E1_I0046's demo, "
                        "which is the stronger form of the point",
        season_split="A1/A2/A4 are negative under PROJ_BUDGET in ALL THREE evaluation seasons",
    ),
    anchors=dict(n_required=13, n_reproduced=12, n_at_exactly_zero=2,
                 non_reproduction="A11 (E0_I0012 possessions ratio) -- see DEFECTS D-01",
                 d104_home_advantage="+0.965090 on 888 games, |d| 9.01e-08"),
    concurrency=dict(
        collision="E1_I0053_minutes, a DEDICATED minutes screen by a sibling agent, was created "
                  "while this screen's s03 was running and carries the same response, the same "
                  "RAW/PROJ axis, the same clean window and the same 3,167-row stratum",
        caught_by="s04_census.py enumerates the directory rather than trusting a typed list",
        ruling="where the two disagree, prefer E1_I0053; this screen's distinctive axis is the "
               "separation of PROJ_BUDGET (live) from PROJ_ORACLE",
    ),
    no_production_change_proposed=True,
    no_champion_fitted=True,
    no_repair_enacted=True,
    processes_launched=["s03 PID recorded in scripts/_s03_pid.txt",
                        "s05 PID recorded in scripts/_s05_pid.txt"],
    blanket_kills_issued="NONE",
)

# sha256 of every .md and .csv in the directory
files = {}
for fn in sorted(os.listdir(B.OUT)):
    p = os.path.join(B.OUT, fn)
    if os.path.isfile(p) and (fn.endswith(".md") or fn.endswith(".csv")):
        with open(p, "rb") as fh:
            files[fn] = hashlib.sha256(fh.read()).hexdigest()
fin["file_sha256"] = files

with open(os.path.join(B.OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
    json.dump(fin, fh, indent=1, default=str)
print("  wrote FINDINGS.json with sha256 of %d .md/.csv files" % len(files))
print("  census by screen: %s" % counts)
B.hdr("DONE s06")
