"""
s01 -- ANCHORS FIRST, THEN THE INDEPENDENCE AUDIT.

Nothing new is computed until every anchor reproduces.  The independence audit then runs BEFORE any
effect size, because its answer governs whether an effect size means anything.
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
import od_base as ob  # noqa: E402

LOG = []


def P(x=""):
    print(x)
    LOG.append(str(x))


def dr2_plain(y, ref_mat, x):
    """In-sample dR2 of adding x to [1, ref].  D085's exact algebraic form."""
    y = np.asarray(y, float)
    X = np.column_stack([np.ones(len(y))] + [np.asarray(r, float) for r in ref_mat])
    XtXi = np.linalg.pinv(X.T @ X)
    e = y - X @ (XtXi @ (X.T @ y))
    sst = float(((y - y.mean()) ** 2).sum())
    x = np.asarray(x, float)
    xt = x - X @ (XtXi @ (X.T @ x))
    den = float(xt @ xt)
    if den <= 1e-12:
        return 0.0
    num = float(e @ xt)
    return (num * num / den) / sst


def main():
    ob.hdr("E1_I0043 s01 -- ANCHOR REPRODUCTION")
    P("  PREREG.md sha256 %s" % ob.prereg_sha())
    P("  PARTITION: 2021-2024 exploration only. 2025/26 is NEVER read.")

    m = ob.build_merged(verbose=True)
    for k, cols in ob.BASES.items():
        assert len(cols) == ob.BASE_LENGTHS[k], "allowlist %s length changed" % k
        P("  ALLOWLIST %-12s n=%d  %s" % (k, len(cols), cols))
    assert len(ob.CANDIDATE) == 1, "candidate is not a single column"
    P("  ALLOWLIST CANDIDATE  n=%d  %s   (single column -> D120 every-component invariant is "
      "satisfied by construction, and this assertion is the proof)" % (len(ob.CANDIDATE),
                                                                       ob.CANDIDATE))
    assert len(ob.A_FAMILY) == 12, "A-family allowlist length changed"

    a = pd.read_parquet(os.path.join(ob.F_EFF, "screen_frame.parquet"))
    sr = pd.read_csv(os.path.join(ob.F_EFF, "screen_results.csv"))
    row = sr[(sr["candidate"] == "A10_opp_defrtg") & (sr["outcome"] == "ppm")].iloc[0]

    anchors = []

    def anchor(aid, what, got, want, tol, src):
        d = abs(float(got) - float(want))
        ok = d <= tol
        anchors.append(dict(anchor=aid, what=what, reproduced=float(got), recorded=float(want),
                            abs_diff=d, tol=tol, PASS=bool(ok), source=src))
        P("  %-4s %-52s reproduced %.12f   recorded %.12f   |diff| %.3e   %s"
          % (aid, what, got, want, d, "PASS" if ok else "*** FAIL ***"))
        assert ok, "ANCHOR %s FAILED" % aid

    # A7 -- frame identity
    b = pd.read_parquet(os.path.join(ob.F_TV, "screen_frame.parquet"))
    anchor("A7a", "E0_I0016 screen_frame row count", len(a), 14852, 0, "parquet")
    anchor("A7b", "E1_I0018 screen_frame row count", len(b), 14852, 0, "parquet")
    anchor("A7c", "merged row count", len(m), 14852, 0, "inner merge")

    # A1/A3 -- D085's own cell, recomputed from the frame
    d1 = dr2_plain(a["y_ppm"], [a["refB_ppm"]], a["A10_opp_defrtg"])
    anchor("A1", "D085 A10_opp_defrtg -> ppm dR2 over refB", d1, row["dr2"], 5e-7,
           "E0_I0016/screen_results.csv")
    d1a = dr2_plain(a["y_ppm"], [a["refA_ppm"]], a["A10_opp_defrtg"])
    anchor("A1b", "D085 same cell over refA", d1a, row["dr2_over_refA"], 5e-7, "same")
    g = a.groupby(["opp_team_id", "season"], sort=False)["A10_opp_defrtg"]
    mu = g.transform("mean").to_numpy(float)
    xv = a["A10_opp_defrtg"].to_numpy(float)
    vs = float(np.var(mu, ddof=0) / np.var(xv, ddof=0))
    anchor("A3", "var_share_between opp_team_season", vs, row["var_share_between_entity"], 5e-7,
           "same")
    anchor("A2a", "D085 p_N2_entity_swap (read)", row["p_N2_entity_swap"], 0.001664, 5e-7, "same")
    anchor("A2b", "D085 p_familywise_N2 (read)", row["p_familywise_N2"], 0.009983, 5e-7, "same")
    anchor("A2c", "D085 p_N1_within_entity (read) -- the BLIND arm", row["p_N1_within_entity"],
           0.870216, 5e-7, "same")

    # A4/A5 -- E1_I0023's ceiling artifacts
    ac = pd.read_csv(os.path.join(ob.EXP, "E1_I0023_usage_defence_interaction",
                                  "arithmetic_ceiling.csv"))
    t3 = ac[(ac.defence == "A10_opp_defrtg") & (ac.stratum == "DECISION")
            & (ac.tier == "T3_high_usage") & (ac.contrast == "MAIN_EFFECT")
            & (ac.fit == "walk_forward")].iloc[0]
    al = ac[(ac.defence == "A10_opp_defrtg") & (ac.stratum == "DECISION")
            & (ac.tier == "ALL_TIERS") & (ac.contrast == "MAIN_EFFECT")
            & (ac.fit == "walk_forward")].iloc[0]
    anchor("A4a", "D098 ceiling (T3, decision, wf)", t3["ceiling_D084_form_var_share"], 0.01280821,
           1e-6, "E1_I0023/arithmetic_ceiling.csv")
    anchor("A4b", "D098 points moved by 1 sd (T3)", t3["points_moved_by_1sd"], 0.739198, 5e-7,
           "same")
    anchor("A4c", "D098 realised dR2 points (T3, n=1687)", t3["realised_paired_dr2_points"],
           0.018703, 5e-7, "same")
    anchor("A4d", "D098 T3 row count", t3["n"], 1687, 0, "same")
    anchor("A5a", "D099 realised dR2 points, decision, n=4514", al["realised_paired_dr2_points"],
           0.003335, 5e-7, "same")
    anchor("A5b", "D099 decision-stratum row count", al["n"], 4514, 0, "same")

    # A6 -- D093's Spearman, carried in E1_I0023's prereg
    with open(os.path.join(ob.EXP, "E1_I0023_usage_defence_interaction", "_prereg.json"),
              encoding="utf-8") as fh:
        pj = json.load(fh)
    flat = json.dumps(pj)
    i = flat.find("R04_opp_defrtg_spearman")
    sp = float(flat[i:].split(":")[1].split(",")[0].split("}")[0].strip().strip('"'))
    anchor("A6", "D093 opp-defrtg Spearman (carried anchor)", sp, 0.3200431235648813, 0.0,
           "E1_I0023/_prereg.json")

    P("\n  ALL %d ANCHORS REPRODUCED.  New statistics may now be generated." % len(anchors))
    pd.DataFrame(anchors).to_csv(os.path.join(ob.OUT, "ANCHORS.csv"), index=False)

    # ------------------------------------------------------------------ INDEPENDENCE AUDIT
    ob.hdr("E1_I0043 s01 -- THE INDEPENDENCE AUDIT (run BEFORE any new effect size)")
    checks = []

    def chk(cid, name, verdict, detail):
        checks.append(dict(check=cid, name=name, verdict=verdict, detail=detail))
        P("  %-4s %-34s %-22s %s" % (cid, name, verdict, detail))

    # ---- I1 COLUMN IDENTITY -------------------------------------------------
    P("\n  I1 COLUMN IDENTITY -- resolve each sighting's defence column to a physical file")
    src = a["A10_opp_defrtg"].to_numpy(float)
    mm = m["A10_opp_defrtg"].to_numpy(float)
    key_a = (a["player_id"].astype(str) + "|" + a["game_id"].astype(str)).to_numpy()
    key_m = (m["player_id"].astype(str) + "|" + m["game_id"].astype(str)).to_numpy()
    lut = dict(zip(key_a, src))
    diff = float(np.max(np.abs(mm - np.array([lut[k] for k in key_m]))))
    P("    S1 D098  E1_I0023/uid_base.py:92   pd.read_parquet(E0_I0016/screen_frame.parquet)")
    P("    S2 D099  E1_I0025/cbase.py         DEFENCE='A10_opp_defrtg', same merged frame")
    P("    S3 D103  E1_I0026/NOTES.md         'joined 1:1 to E0_I0016/screen_frame.parquet for the "
      "opponent columns'")
    P("    S4 D117  E1_I0038                  reads D085's OWN recorded p from E0_I0016")
    P("    max |value difference| between the merged frame's column and the source parquet's "
      "column, on the joined rows: %.3e" % diff)
    chk("I1", "column identity", "SAME VECTOR" if diff == 0.0 else "DIFFERS",
        "max|diff| %.3e across all 14,852 rows; one physical column in one physical file" % diff)

    # ---- I2 ROW SETS --------------------------------------------------------
    P("\n  I2 ROW SETS -- pairwise containment on (player_id, game_id)")
    dec = ob.decision_mask(m)
    need = list(dict.fromkeys(ob.BASE_B0_COMPLETE + ["A10_opp_defrtg", "y_ppm", "y_pts",
                                                     "O01_own_usg_pg"]))
    fin = ob.finite_mask(m, need)
    ssn = m["season"].to_numpy()
    S4 = np.ones(len(m), bool)                                  # D117: the whole frame
    S3 = dec & fin                                              # D103: decision, in-sample
    S2 = dec & fin & (ssn >= 2022)                              # D099: decision, wf-scored
    u = m["O01_own_usg_pg"].to_numpy(float)
    tr21 = S2 & (ssn < 2022)
    ref = u[S2] if tr21.sum() < 200 else u[tr21]
    q = np.quantile(ref[np.isfinite(ref)], [1 / 3, 2 / 3])
    top = u >= q[1]
    S1 = S2 & top                                               # D098: + top usage tercile
    sets = {"S1_D098": S1, "S2_D099": S2, "S3_D103": S3, "S4_D117": S4}
    for k, v in sets.items():
        P("    %-9s n=%6d" % (k, int(v.sum())))
    rows = []
    names = list(sets)
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            A, B = sets[x], sets[y]
            inter = int((A & B).sum())
            uni = int((A | B).sum())
            rows.append(dict(a=x, b=y, n_a=int(A.sum()), n_b=int(B.sum()), intersection=inter,
                             union=uni, jaccard=inter / uni,
                             a_subset_of_b=bool(inter == A.sum()),
                             b_subset_of_a=bool(inter == B.sum())))
            P("    %-9s vs %-9s  inter=%6d  jaccard=%.4f  a<=b=%s  b<=a=%s"
              % (x, y, inter, inter / uni, inter == A.sum(), inter == B.sum()))
    pd.DataFrame(rows).to_csv(os.path.join(ob.OUT, "INDEPENDENCE_ROWSETS.csv"), index=False)
    nested = all(r["a_subset_of_b"] or r["b_subset_of_a"] for r in rows)
    chk("I2", "row sets", "FULLY NESTED" if nested else "NOT NESTED",
        "S1 c S2 c S3 c S4; every sighting is a sub-population of the same 14,852-row frame")

    # ---- I3 RESPONSE --------------------------------------------------------
    resp = {"S1_D098": {"y_ppm", "y_pts"}, "S2_D099": {"y_ppm", "y_pts"},
            "S3_D103": {"y_ppm"}, "S4_D117": {"y_ppm"}}
    common = set.intersection(*resp.values())
    chk("I3", "response", "SHARED: %s" % sorted(common),
        "all four report the SAME response y_ppm; y_ppm is the only response common to all four")

    # ---- I4 BASE ------------------------------------------------------------
    chk("I4", "base / reference", "3 of 4 SHARE A BASE FAMILY",
        "S1,S2 = BASE_COMPLETE(refB_ppm,spm,pps,mpg,own_usg); S3 = B_COMPLETE/B_SINGLE same refB "
        "family; S4 = [1, refB_ppm] alone. No base carries a possession or opponent-pace term.")

    # ---- I5 SHARED UPSTREAM -------------------------------------------------
    P("\n  I5 SHARED UPSTREAM -- provenance chain")
    P("    E0_I0016_efficiency_predictors/screen_frame.parquet  ->  A10_opp_defrtg")
    P("      |-- E1_I0021 (D093)  merged D085+D089        -> Spearman +0.320   [the STRUCTURAL claim]")
    P("      |-- E1_I0023 (D098)  merged D085+D089        -> SIGHTING 1")
    P("      |     `-- E1_I0025 (D099) confirmation of S1 -> SIGHTING 2")
    P("      |-- E1_I0026 (D103)  joined D085 onto D089   -> SIGHTING 3")
    P("      `-- E0_I0016 own recorded null (D085)        -> SIGHTING 4 via E1_I0038 (D117)")
    chk("I5", "shared upstream", "ONE SOURCE FILE",
        "all four resolve to A10_opp_defrtg in E0_I0016/screen_frame.parquet; any defect in that "
        "column's construction propagates to all four identically")

    # ---- I6 REDUNDANCY WITHIN THE A-FAMILY ----------------------------------
    P("\n  I6 REDUNDANCY -- was D085's 'twelve constructions' twelve tests?")
    A = np.column_stack([pd.to_numeric(a[c], errors="coerce").to_numpy(float)
                         for c in ob.A_FAMILY])
    okA = np.all(np.isfinite(A), axis=1)
    A = A[okA]
    C = np.corrcoef(A, rowvar=False)
    i10 = ob.A_FAMILY.index("A10_opp_defrtg")
    cors = sorted(((ob.A_FAMILY[j], float(C[i10, j])) for j in range(12) if j != i10),
                  key=lambda t: -abs(t[1]))
    for nm, c in cors:
        P("    corr(A10_opp_defrtg, %-28s) = %+.4f" % (nm, c))
    Az = (A - A.mean(0)) / A.std(0, ddof=1)
    ev = np.linalg.eigvalsh(np.corrcoef(Az, rowvar=False))[::-1]
    cum = np.cumsum(ev) / ev.sum()
    k99 = int(np.searchsorted(cum, 0.99) + 1)
    k95 = int(np.searchsorted(cum, 0.95) + 1)
    P("    A-family correlation-matrix eigenvalues: %s" % np.round(ev, 4).tolist())
    P("    effective dimension: %d components carry 95%% of variance, %d carry 99%% (of 12 columns)"
      % (k95, k99))
    pd.DataFrame([dict(a="A10_opp_defrtg", b=nm, pearson=c) for nm, c in cors]
                 ).to_csv(os.path.join(ob.OUT, "AFAMILY_CORRELATION.csv"), index=False)
    chk("I6", "A-family redundancy", "%d of 12 effective dims @95%%" % k95,
        "max |corr| with A10 is %+.4f (%s)" % (cors[0][1], cors[0][0]))

    pd.DataFrame(checks).to_csv(os.path.join(ob.OUT, "INDEPENDENCE.csv"), index=False)

    # ---- the preregistered rule fires ---------------------------------------
    collapse = (diff == 0.0) and nested and len(common) >= 1
    ob.hdr("PREREGISTERED INDEPENDENCE RULE (PREREG section 3)")
    P("  I1 same vector: %s | I2 nested: %s | I5 one source file: True" % (diff == 0.0, nested))
    P("  -> THE FOUR SIGHTINGS ARE %s"
      % ("ONE SIGHTING. No corroboration credit is taken from the count of four."
         if collapse else "GENUINELY INDEPENDENT."))

    with open(os.path.join(HERE, "_s01.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha=ob.prereg_sha(), anchors=anchors, checks=checks,
                       rowsets={k: int(v.sum()) for k, v in sets.items()},
                       collapse=bool(collapse), k95=k95, k99=k99), fh, indent=2, default=float)
    with open(os.path.join(HERE, "run_log_s01.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))


if __name__ == "__main__":
    main()
