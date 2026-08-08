"""
s06 -- IS `A10_opp_defrtg` ACTUALLY STRICTLY PRIOR?  VERIFIED ON BYTES, NOT INHERITED.

WHY.  s04/s05 returned an opponent-defence main effect inside the top usage tier of walk-forward
dR2 = +0.024 (points-per-minute, decision stratum), roughly 12 sd beyond a within-date opponent-swap
null, in a programme where D085 screened twelve constructions of exactly this quantity across 36
cells and found a best dR2 of 0.00144.  An effect that large, that is stronger for exactly the
players who contribute the largest share of their team's points, is the SIGNATURE OF A
CONTEMPORANEOUS LEAK: if the opponent's "defensive rating" included the game being scored, the
player's own points would be inside their own regressor, and the contamination would scale with the
player's usage.

That hypothesis is stated BEFORE the probe.  Four checks:
    C1 COLD-START STRUCTURE.  A strictly-prior expanding mean must be undefined when the opponent
       has zero prior games.  A contemporaneous one is defined there.
    C2 INDEPENDENT REBUILD.  Rebuild the column from `data/masters/master_team.parquet` with an
       explicit shift(1) before the expanding sums, and compare to the frozen column bit for bit.
    C3 POSITIVE CONTROL.  Build the DELIBERATELY LEAKY twin (the same rating INCLUDING the current
       game) and confirm the probes separate it from the clean one.  A probe that only ever says
       "clean" proves nothing; this one has to detect a planted leak.
    C4 LEAD-LAG PROFILE (D090's strongest probe shape).  For a strictly-prior expanding mean, the
       INCREMENT from game k to game k+1 must be driven by what happened in game k, and the
       increment INTO game k must be independent of game k.  A contemporaneous series has the
       opposite profile.

Then the decisive one: RE-RUN THE TOP-TIER MAIN EFFECT with the clean rebuild and with the leaky
twin.  If the frozen column behaves like the clean rebuild and NOT like the leaky twin, the result
is not a leak and must be explained some other way.
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
import uid_base as ub  # noqa: E402
import s00_prereg as pr  # noqa: E402
import s02_interaction_forecast as s02  # noqa: E402
import s05_placebos as s05  # noqa: E402

MT_PATH = os.path.join(ub.ROOT, r"data\masters\master_team.parquet")
DEFENCE = "A10_opp_defrtg"
UCOL = pr.USAGE_MAIN


def main():
    log = []

    def P(x=""):
        print(x)
        log.append(str(x))

    ub.hdr("E1_I0023 s06 -- LEAKAGE PROBE ON THE OPPONENT DEFENCE COLUMN")
    h, _, _ = pr.check_prereg()
    P("  PREREG hash %s VERIFIED" % h)
    P("  HYPOTHESIS UNDER TEST, STATED FIRST: the top-tier effect is a contemporaneous leak, and it "
      "scales with usage because a high-usage player contributes more of the points inside their "
      "own opponent-defence regressor.")
    m, ncl = s02.build_frame(P)

    # ------------------------------------------------------------------ C1 cold-start structure
    ub.hdr("C1 -- COLD-START STRUCTURE")
    g = m.groupby("opp_prior_games")[DEFENCE].agg(n="size", n_nan=lambda x: int(x.isna().sum()))
    for k in sorted(g.index)[:6]:
        P("  opp_prior_games=%-3s n=%5d  A10 missing=%5d  (%.1f%%)"
          % (k, g.loc[k, "n"], g.loc[k, "n_nan"], 100.0 * g.loc[k, "n_nan"] / g.loc[k, "n"]))
    if 0 in g.index:
        c1 = bool(g.loc[0, "n_nan"] == g.loc[0, "n"])
        P("  A10 is entirely MISSING where the opponent has zero prior games: %s   -> %s"
          % (c1, "consistent with a STRICTLY PRIOR series" if c1
             else "CONSISTENT WITH A CONTEMPORANEOUS LEAK"))
    else:
        c1 = None
        P("  C1 IS INCONCLUSIVE AND IS REPORTED AS SUCH: the frame contains NO rows with zero "
          "opponent prior games (the minimum present is %s), because D085's frame already requires "
          "prior appearances. This check therefore cannot discriminate either way, and C2/C3/C4 "
          "carry the whole verdict." % sorted(g.index)[0])

    # ------------------------------------------------------------------ C2/C3 rebuild + leaky twin
    ub.hdr("C2/C3 -- INDEPENDENT REBUILD FROM master_team, PLUS A DELIBERATELY LEAKY TWIN")
    mt = pd.read_parquet(MT_PATH)
    mt["game_date"] = pd.to_datetime(mt["game_date"], errors="coerce")
    mt = mt[mt["season"].isin(sorted(ub.ALLOWED_SEASONS))].copy()
    ub.assert_partition(mt)
    for c in ["opp_pts", "opp_fga", "opp_oreb", "opp_tov", "opp_fta"]:
        mt[c] = pd.to_numeric(mt[c], errors="coerce").astype(float)
    mt["opp_poss"] = mt["opp_fga"] - mt["opp_oreb"] + mt["opp_tov"] + 0.44 * mt["opp_fta"]
    mt = mt.sort_values(["season", "team_id", "game_date", "game_id"],
                        kind="stable").reset_index(drop=True)
    gb = mt.groupby(["season", "team_id"], sort=False)
    # CLEAN: shift(1) BEFORE expanding -- strictly prior
    ppts = gb["opp_pts"].transform(lambda x: x.shift(1).expanding().sum())
    ppos = gb["opp_poss"].transform(lambda x: x.shift(1).expanding().sum())
    mt["CLEAN_defrtg"] = 100.0 * ppts / ppos.replace(0.0, np.nan)
    # LEAKY POSITIVE CONTROL: no shift -- includes the game being scored
    lpts = gb["opp_pts"].transform(lambda x: x.expanding().sum())
    lpos = gb["opp_poss"].transform(lambda x: x.expanding().sum())
    mt["LEAKY_defrtg"] = 100.0 * lpts / lpos.replace(0.0, np.nan)

    opp = mt[["season", "team_id", "game_id", "CLEAN_defrtg", "LEAKY_defrtg"]].rename(
        columns={"team_id": "opp_team_id"})
    m = m.merge(opp, on=["season", "opp_team_id", "game_id"], how="left")
    ok = np.isfinite(m[DEFENCE]) & np.isfinite(m["CLEAN_defrtg"])
    d_clean = float(np.max(np.abs(m.loc[ok, DEFENCE] - m.loc[ok, "CLEAN_defrtg"])))
    okl = np.isfinite(m[DEFENCE]) & np.isfinite(m["LEAKY_defrtg"])
    d_leaky = float(np.max(np.abs(m.loc[okl, DEFENCE] - m.loc[okl, "LEAKY_defrtg"])))
    P("  frozen A10 vs INDEPENDENT CLEAN rebuild: max|diff| = %.3e on %d rows" % (d_clean, int(ok.sum())))
    P("  frozen A10 vs LEAKY twin              : max|diff| = %.3e on %d rows  (must be LARGE)"
      % (d_leaky, int(okl.sum())))
    P("  corr(CLEAN, LEAKY) = %.4f"
      % float(np.corrcoef(m.loc[ok & okl, "CLEAN_defrtg"], m.loc[ok & okl, "LEAKY_defrtg"])[0, 1]))

    # ------------------------------------------------------------------ C4 lead-lag profile
    ub.hdr("C4 -- LEAD-LAG PROFILE against the opponent's OWN allowed points, game by game")
    u = mt[["season", "team_id", "game_id", "game_date", "opp_pts", "opp_poss",
            "CLEAN_defrtg", "LEAKY_defrtg"]].copy()
    u["allowed_rtg_this_game"] = 100.0 * u["opp_pts"] / u["opp_poss"].replace(0.0, np.nan)
    # the FROZEN column's own team-game series, lifted straight out of the player frame
    fz = (m.groupby(["season", "opp_team_id", "game_id"], sort=False)[DEFENCE]
          .first().reset_index().rename(columns={"opp_team_id": "team_id", DEFENCE: "FROZEN_A10"}))
    u = u.merge(fz, on=["season", "team_id", "game_id"], how="left")
    u = u.sort_values(["season", "team_id", "game_date", "game_id"],
                      kind="stable").reset_index(drop=True)
    key = [u["season"], u["team_id"]]
    allowed = u["allowed_rtg_this_game"].to_numpy(float)

    def cr(a, b):
        mm = np.isfinite(a) & np.isfinite(b)
        return float(np.corrcoef(a[mm], b[mm])[0, 1]) if mm.sum() > 50 else np.nan

    prof = []
    for col in ["CLEAN_defrtg", "LEAKY_defrtg", "FROZEN_A10"]:
        series = u[col]
        s_prev = series.groupby(key, sort=False).shift(1)
        s_next = series.groupby(key, sort=False).shift(-1)
        d_into = (series - s_prev).to_numpy(float)     # increment INTO game k
        d_out = (s_next - series).to_numpy(float)      # increment from game k to game k+1
        prof.append(dict(column=col,
                         corr_increment_INTO_game_k_with_game_k=cr(d_into, allowed),
                         corr_increment_OUT_OF_game_k_with_game_k=cr(d_out, allowed),
                         corr_level_with_game_k=cr(series.to_numpy(float), allowed)))
        r = prof[-1]
        P("  %-24s corr(increment INTO game k , game k) = %+.4f   "
          "corr(increment OUT OF game k , game k) = %+.4f   corr(level , game k) = %+.4f"
          % (col, r["corr_increment_INTO_game_k_with_game_k"],
             r["corr_increment_OUT_OF_game_k_with_game_k"], r["corr_level_with_game_k"]))
    P("  STRICTLY PRIOR signature: INTO ~ 0, OUT strongly POSITIVE.  "
      "LEAK signature: INTO strongly POSITIVE.")

    # ------------------------------------------------------------------ the decisive re-run
    ub.hdr("THE DECISIVE RE-RUN -- top usage tier, frozen vs CLEAN rebuild vs LEAKY twin")
    m, unit = s05.build_placebos(m, P)
    basecols = pr.BASE_COMPLETE
    need = list(dict.fromkeys(basecols + [UCOL, DEFENCE, "CLEAN_defrtg", "LEAKY_defrtg",
                                          "y_ppm", "y_pts", "_m_hat"]))
    v = {c: pd.to_numeric(m[c], errors="coerce").to_numpy(float) for c in need}
    rows = []
    for resp_id in ["ppm", "points"]:
        resp = s02.RESP[resp_id]
        for sid in ["POOLED", "DECISION"]:
            base_mask = s02.stratum_mask(m, sid)
            for c in need:
                base_mask &= np.isfinite(v[c])
            first_tr = base_mask & (m["season"].to_numpy()
                                    < pr.PREREG["partition"]["scored_seasons"][0])
            tier_all, _ = ub.usage_terciles(v[UCOL][first_tr], v[UCOL])
            for tier, tname in ((-1, "ALL_TIERS"), (2, "T3_high_usage")):
                mask = base_mask if tier == -1 else (base_mask & (tier_all == tier))
                for col, lbl in ((DEFENCE, "FROZEN_A10"), ("CLEAN_defrtg", "CLEAN_rebuild"),
                                 ("LEAKY_defrtg", "LEAKY_positive_control")):
                    r = s05.score(m, v, basecols, mask, v[col], UCOL, False, resp)
                    if r is None:
                        continue
                    dr2, y, A, B, C = r
                    ct = ub.paired_cluster_test(y, A, B, C, ncl, n_draws=pr.N_DRAWS, seed=ub.SEED)
                    ct.pop("draws_cluster")
                    rows.append(dict(response=resp_id, stratum=sid, tier=tname, column=lbl,
                                     n_scored=int(len(y)), dr2=dr2, p_cluster=ct["p_cluster"]))
                    q = rows[-1]
                    P("  %-6s %-9s %-14s %-22s n=%5d  main-effect dR2=%+.6f  cluster p=%.4f"
                      % (resp_id, sid, tname, lbl, q["n_scored"], q["dr2"], q["p_cluster"]))

    ldf = pd.DataFrame(rows)
    ldf.to_csv(os.path.join(ub.OUT, "leakage_probes.csv"), index=False)
    pd.DataFrame(prof).to_csv(os.path.join(ub.OUT, "leadlag_profile.csv"), index=False)

    ub.hdr("LEAKAGE VERDICT")
    fz = ldf[(ldf.column == "FROZEN_A10")].set_index(["response", "stratum", "tier"])["dr2"]
    cl = ldf[(ldf.column == "CLEAN_rebuild")].set_index(["response", "stratum", "tier"])["dr2"]
    lk = ldf[(ldf.column == "LEAKY_positive_control")].set_index(["response", "stratum", "tier"])["dr2"]
    P("  frozen-vs-clean max |dR2 difference| = %.3e  (must be ~0 if the frozen column is clean)"
      % float((fz - cl).abs().max()))
    P("  leaky twin / frozen dR2 ratio, by cell: %s"
      % ", ".join("%s=%.1fx" % ("|".join(map(str, k)), lk[k] / fz[k]) for k in fz.index))

    out = dict(prereg_sha256=h, cold_start_all_missing=c1,
               frozen_vs_clean_max_abs_diff=d_clean, frozen_vs_leaky_max_abs_diff=d_leaky,
               leadlag=prof, rerun=json.loads(ldf.to_json(orient="records")))
    with open(os.path.join(ub.OUT, "_s06.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=float)
    with open(os.path.join(ub.OUT, "run_log_s06.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("  wrote leakage_probes.csv, leadlag_profile.csv, _s06.json")


if __name__ == "__main__":
    main()
