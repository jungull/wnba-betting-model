"""E0_I0028 -- STEP 01: build the working frame and establish the positive control.

Loads all 8 (arm x target) prediction sets for 2022-2024, joins EACH ARM TO ITS OWN CONTRACT
(prereg amendment f110da75...), attaches the provenance sidecar, builds the strictly-prior
baselines, and writes `work_frame.parquet`.

Also runs the POSITIVE CONTROL the prereg requires: the sweep must rediscover D092/D094's
cold-start fallback region.  A sweep that cannot find the ONE KNOWN INSTANCE is broken, and no
other result from it would be believable.
"""
import json
import os

import numpy as np
import pandas as pd

import dg_base as B

pd.set_option("display.width", 250)


def main():
    B.hdr("STEP 01 -- LOAD, JOIN, BUILD PRIORS")
    print("  prereg sha256 verified : %s" % B.assert_prereg())
    am = json.load(open(os.path.join(B.OUT, "_prereg_amendment.json"), encoding="utf-8"))
    print("  amendment sha256       : %s  (added=%d dropped=%d corrected=%d)"
          % (am["_amendment_sha256"], am["counts"]["added"], am["counts"]["dropped"],
             am["counts"]["corrected"]))

    B.hdr("1a. the 2021 fold -- CONFIRM the known non-finding, then never use it")
    for arm, base in B.ARMS.items():
        r = json.load(open(os.path.join(base, "fold_receipt__2021.json"), encoding="utf-8"))
        print("    %-24s %s" % (arm, {k: r[k] for k in r if k in
                                      ("fold_id", "n_train_rows", "model_was_fitted",
                                       "degenerate")}))
    print("  -> degenerate BY DESIGN. Excluded from every discovery claim (prereg C1).")

    contracts, spans = {}, {}
    for arm in B.ARMS:
        B.hdr("1b. contract / truth frame -- %s" % arm)
        c = B.load_contract(arm)
        print("\n  season calendar ranges (must be disjoint for prev-season aggregates to be prior):")
        spans[arm] = B.assert_seasons_disjoint(c)
        c = B.build_priors(c, verbose=(arm == "cbs_v15_player_oof_v5"))
        B.assert_partition(c[["season", "game_date"]], label=arm + "/post-priors")
        contracts[arm] = c

    B.hdr("1c. champion output inventory")
    preds, rows = {}, []
    for arm in B.ARMS:
        for t in B.TARGETS:
            d = B.load_predictions(arm, t)
            preds[(arm, t)] = d
            rows.append(dict(arm=arm, target=t, n_rows=len(d),
                             contract_rows=len(contracts[arm]),
                             pred_point_null=int(d["pred_point"].isna().sum()),
                             pred_sd_null=int(d["pred_sd"].isna().sum()),
                             q50_null=int(d["pred_q50"].isna().sum()),
                             n_components=d["component_id"].nunique(),
                             components=" | ".join(sorted(d["component_id"].unique())),
                             fallback_share=round(float(d["is_fallback"].mean()), 4)))
    inv = pd.DataFrame(rows)
    print(inv.drop(columns=["components"]).to_string(index=False))
    print("\n  component_id inventory:")
    for r in rows:
        print("    %-24s %-30s %s" % (r["arm"], r["target"], r["components"]))
    inv.to_csv(os.path.join(B.OUT, "output_inventory.csv"), index=False)

    B.hdr("1d. assemble the long working frame  (one row per arm x target x row_uid)")
    keep = ["row_uid", "game_id", "team_id", "player_id", "game_date", "season",
            "prior_games_admitted", "lookback_games_used", "candidate_at_cutoff",
            "exact_cutoff_ok", "tip_time_quality", "player_season_game_index",
            "n_prior_candidate_obligations", "n_prior_team_games", "team_assignment_ambiguous",
            "universe_tier", "evaluation_tier", "fit_eligible", "candidate_source",
            "team_assignment_confidence", "roster_evidence_regime",
            "minutes", "pts", "fga", "appeared", "n_app_prior", "n_row_prior", "prev_n",
            "ref_pts", "ref_minutes", "ref_fga", "ref_appeared",
            "lg_pts", "lg_minutes", "lg_fga", "lg_appeared",
            "prev_pts", "prev_minutes", "prev_fga", "prev_appeared",
            "sum_pts_prior", "sum_minutes_prior", "sum_fga_prior", "sum_appeared_prior"]
    out, joinlog = [], []
    for (arm, t), d in preds.items():
        c = contracts[arm]
        sc, rq = "outcome_scoreable__%s" % t, "prediction_required__%s" % t
        cc = c[keep + [sc, rq]].copy()
        d2 = d.drop(columns=["season"]).merge(cc, on="row_uid", how="inner", validate="one_to_one")
        d2["arm"], d2["target"] = arm, t
        d2["y"] = d2[B.TRUTH[t]].astype(float)
        d2["ref"] = d2["ref_" + B.TRUTH[t]].astype(float)
        d2["scoreable"] = d2[sc].astype(bool)
        d2["required"] = d2[rq].astype(bool)
        joinlog.append(dict(arm=arm, target=t, pred_rows=len(d), joined=len(d2),
                            unmatched=len(d) - len(d2), scoreable=int(d2["scoreable"].sum()),
                            required=int(d2["required"].sum())))
        print("    %-24s %-30s pred=%6d joined=%6d unmatched=%3d required=%6d scoreable=%6d"
              % (arm, t, len(d), len(d2), len(d) - len(d2), int(d2["required"].sum()),
                 int(d2["scoreable"].sum())))
        out.append(d2.drop(columns=[sc, rq]))
    w = pd.concat(out, ignore_index=True)
    assert all(j["unmatched"] == 0 for j in joinlog), "UNMATCHED PREDICTION ROWS REMAIN"
    print("\n  working frame: %s   (zero unmatched rows on either arm)" % (w.shape,))

    B.assert_partition(w[["season", "game_date"]], label="work_frame")
    assert set(w["season"].unique()) == {2022, 2023, 2024}
    assert w["game_date"].max() < pd.Timestamp("2025-01-01")

    B.hdr("1e. POSITIVE CONTROL -- rediscover D092 / D094")
    print("  D092: champion emits a CONSTANT for players with < 3 prior appearances --")
    print("        8.704 pts at sd 0.013 and 21.62 minutes at sd 0.09, all three seasons,")
    print("        against a truth sd of 7.2.")
    print("  D094: on 698 fallback rows the champion prints EXACTLY TWO distinct point values.\n")
    ctrl = []
    for t in ("player_scoring_distribution", "e_minutes_given_active", "attempts_usage"):
        for arm in B.ARMS:
            d = w[(w["arm"] == arm) & (w["target"] == t)]
            for cond, name in ((d["n_prior_appearances"] < 3, "n_prior_appearances < 3"),
                               (d["is_fallback"].astype(bool), "is_fallback"),
                               (d["is_cold_start"].astype(bool), "is_cold_start")):
                s = d[cond.fillna(False).to_numpy()]
                if len(s) < 10:
                    continue
                sy = s.loc[s["scoreable"], "y"]
                ctrl.append(dict(arm=arm, target=t, condition=name, n_rows=len(s),
                                 n_distinct_pred=int(s["pred_point"].round(9).nunique()),
                                 mean_pred=round(float(s["pred_point"].mean()), 4),
                                 sd_pred=round(float(s["pred_point"].std(ddof=1)), 4),
                                 sd_truth=round(float(sy.std(ddof=1)), 4) if len(sy) > 1 else None))
    cf = pd.DataFrame(ctrl)
    print(cf.to_string(index=False))
    cf.to_csv(os.path.join(B.OUT, "positive_control.csv"), index=False)
    print()
    for t, lbl, exp in (("player_scoring_distribution", "pts", "8.704 / 0.013"),
                        ("e_minutes_given_active", "minutes", "21.62 / 0.09")):
        h = cf[(cf["arm"] == "cbs_v15_player_oof_v5") & (cf["target"] == t)
               & (cf["condition"] == "n_prior_appearances < 3")]
        if len(h):
            r = h.iloc[0]
            print("  D092 CHECK %-8s n_prior_appearances<3 : mean=%8.3f sd=%7.4f  n=%5d "
                  "n_distinct=%d   (D092 published %s)"
                  % (lbl, r["mean_pred"], r["sd_pred"], r["n_rows"], r["n_distinct_pred"], exp))

    B.hdr("1f. pooled skill of the champion against the strictly-prior reference (the anchor)")
    anch = []
    for arm in B.ARMS:
        for t in B.TARGETS:
            d = w[(w["arm"] == arm) & (w["target"] == t) & w["scoreable"]]
            s, lm, lr, n = B.skill_of(d["y"], d["pred_point"], d["ref"], t)
            anch.append(dict(arm=arm, target=t, n_scoreable=n,
                             pooled_skill_pct=round(100 * s, 4),
                             loss_champion=round(lm, 5), loss_reference=round(lr, 5),
                             metric=("Brier" if t == "p_active" else "MAE")))
            print("    %-24s %-30s skill=%+8.4f%%  %s champ=%.4f ref=%.4f  n=%d"
                  % (arm, t, 100 * s, "Brier" if t == "p_active" else "MAE ", lm, lr, n))
    pd.DataFrame(anch).to_csv(os.path.join(B.OUT, "pooled_anchor.csv"), index=False)
    print("\n  D081 published pooled POINTS skill = -0.22%% for the champion vs its reference.")
    print("  The reference here is INDEPENDENTLY REBUILT (D076's construction, not its stored")
    print("  column), so an exact match is not expected -- SIGN and ORDER OF MAGNITUDE anchor it.")

    w.to_parquet(os.path.join(B.OUT, "work_frame.parquet"), index=False)
    print("\n  wrote work_frame.parquet %s" % (w.shape,))
    B.jwrite("_s01.json", {"prereg_sha256": B.PREREG_SHA,
                           "amendment_sha256": am["_amendment_sha256"],
                           "season_spans": spans, "work_frame_shape": list(w.shape),
                           "join_log": joinlog, "inventory": rows,
                           "positive_control": cf.to_dict("records"),
                           "pooled_anchor": anch})


if __name__ == "__main__":
    main()
