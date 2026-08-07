"""
E0 I0012 -- FORMULATION 1: OPPONENT-SPECIFIC RESIDUAL HISTORY (familiarity / scheme fit).

Question: does a player systematically over/under-perform against a SPECIFIC opponent,
beyond (a) his own quality and (b) that opponent's overall defensive strength?

Construction (all pregame, strict shift):
  surprise   e_it = y_it - own_pre_it * (def_pre_it / lg_rate_it)
             -- an unfitted multiplicative expectation: own pregame rate scaled by how much
                harder/easier this opponent's overall defence has been than the league.
                No regression is fit to produce it, so it carries no in-sample leakage.
  pair value M_it = mean of e over all games this player has played against this opponent
                    STRICTLY BEFORE this game's date, pooled across the partition seasons
                    (familiarity is a cross-season claim), shrunk toward 0 by SHRINK_PAIR.

Then: incremental R2 of M (residualized on D and O*D) over the base model y ~ O + D + O*D.

This formulation is structurally unlikely to be overall defence in disguise, because the
opponent's overall level has already been divided out of e. The real threat is that M is a
PLAYER main effect (a persistent miss in own_pre) wearing an opponent costume -- so the
variance decomposition is over PLAYER, and the honest test is run within player as well.

PARTITION: 2021-2024 only. Enforced in base.load_player() and re-asserted before write.
"""
import os
import numpy as np
import pandas as pd

import base as B

SHRINK_PAIR = 2.0     # pseudo-games of shrinkage toward 0 surprise
MIN_PAIR_GAMES = 1.0  # require at least this many prior meetings
N_PERM = 200


def run():
    B.hdr("F1 -- OPPONENT-SPECIFIC RESIDUAL HISTORY")
    mp = B.load_player()
    B.poss_sanity(mp)
    mp = mp[(mp["minutes"] >= 1.0) & (mp["possessions"] > 0)].copy()

    rng = np.random.default_rng(B.SEED)
    results = {}

    for T in B.TARGETS:
        B.hdr("F1 / target = %s" % T)
        d = B.build_base(mp, T)
        d = d.dropna(subset=["own_pre", "def_pre", "lg_rate"]).copy()

        # ---- pregame surprise (no fitting) ----
        d["exp"] = d["own_pre"] * (d["def_pre"] / d["lg_rate"])
        d["e"] = d["y"] - d["exp"]
        print("  surprise e: mean=%+.4f sd=%.4f  (expectation is unfitted, so mean need not be 0)"
              % (d["e"].mean(), d["e"].std()))

        # ---- pair history, strictly prior, pooled across partition seasons ----
        d = d.sort_values(["gdate", "game_id", "player_id"]).reset_index(drop=True)
        d["_one"] = 1.0
        pr = B.prior_expanding(d, ["player_id", "opp_team_id"], ["e", "_one"], "pair_")
        d["pair_e"] = pr["pair_e"].values
        d["pair_n"] = pr["pair__one"].values
        d["M_pair"] = d["pair_e"] / (d["pair_n"] + SHRINK_PAIR)
        d.loc[d["pair_n"] < MIN_PAIR_GAMES, "M_pair"] = np.nan

        w = B.prep_frame(d, extra_required=["M_pair"])
        print("  analysis rows with a pair history: %d" % len(w))
        print("  prior-meeting counts (pair_n) on analysis rows: "
              "mean=%.2f med=%.0f p25=%.0f p75=%.0f max=%.0f | frac with n>=3: %.3f | n>=6: %.3f"
              % (w["pair_n"].mean(), w["pair_n"].median(), w["pair_n"].quantile(.25),
                 w["pair_n"].quantile(.75), w["pair_n"].max(),
                 (w["pair_n"] >= 3).mean(), (w["pair_n"] >= 6).mean()))

        # ---- (a) collinearity with OVERALL opponent defence ----
        r_all, per = B.collinearity(w, "M_pair")
        print("  (a) COLLINEARITY corr(M_pair, def_pre) within season = %+.4f | per season %s"
              % (r_all, {k: round(v, 3) for k, v in per.items()}))

        # ---- (b) between/within variance decomposition ----
        bp, wp, ng, mg = B.var_decomp(w, "M_pair", "player_id")
        bo, wo, ngo, mgo = B.var_decomp(w, "M_pair", "opp_team_id")
        print("  (b) VAR DECOMP of M_pair: between-PLAYER %.3f / within %.3f (%d players, med n=%.0f)"
              % (bp, wp, ng, mg))
        print("      VAR DECOMP of M_pair: between-OPPONENT %.3f / within %.3f (%d opponents)"
              % (bo, wo, ngo))

        # ---- (c) split-half reliability of the pair measure ----
        # units = (player, opponent) pairs; value = per-game surprise; odd/even meetings.
        pool = d.dropna(subset=["e"])[["player_id", "opp_team_id", "e", "gdate"]].copy()
        cnt = pool.groupby(["player_id", "opp_team_id"]).size()
        keep = cnt[cnt >= 4].index
        pool = pool.set_index(["player_id", "opp_team_id"]).loc[keep].reset_index()
        rh, sb, nu = B.split_half_reliability(pool, ["player_id", "opp_team_id"], "e")
        print("  (c) SPLIT-HALF RELIABILITY of pair surprise (pairs with >=4 meetings): "
              "r_half=%.4f  spearman-brown=%.4f  n_pairs=%d" % (rh, sb, nu))
        # reference: the same statistic at PLAYER level (how reliable is "this player surprises")
        rh_p, sb_p, nu_p = B.split_half_reliability(
            d.dropna(subset=["e"])[["player_id", "e", "gdate"]], ["player_id"], "e")
        print("      reference: player-level surprise reliability r_half=%.4f sb=%.4f n=%d"
              % (rh_p, sb_p, nu_p))

        # ---- (d) effect: raw, then WITHIN-PLAYER (the honest version) ----
        print("  (d) EFFECT -- M centered within SEASON (raw):")
        raw = B.screen_increment(w, "M_pair", "F1_raw")
        print("  (d) EFFECT -- M centered within (SEASON, PLAYER) (removes the player main effect):")
        wp_ = B.screen_increment(w, "M_pair", "F1_within_player",
                                 center_keys=("season", "player_id"))
        print("  (d) EFFECT -- restricted to pairs with >=3 prior meetings, within player:")
        w3 = w[w["pair_n"] >= 3].copy()
        thick = B.screen_increment(w3, "M_pair", "F1_thick",
                                   center_keys=("season", "player_id")) if len(w3) > 500 else None

        # ---- (e) PLACEBO: permute the ASSIGNMENT of already-computed M values to rows ----
        # NOT a key permutation. M_pair is computed once from true pairs; the permutation
        # reshuffles which ROW receives which already-computed value, within season.
        # A no-op placebo would have sd exactly 0; this one must not.
        pool_w = w.copy()
        real_pool = None
        vals = []
        for it in range(N_PERM):
            p = pool_w.copy()
            perm = np.empty(len(p))
            for s in sorted(p["season"].unique()):
                k = (p["season"] == s).values
                v = p.loc[k, "M_pair"].values.copy()
                rng.shuffle(v)
                perm[k] = v
            p["M_perm"] = perm
            res = B.screen_increment_quiet(p, "M_perm", center_keys=("season", "player_id"))
            vals.append(res)
        V = pd.DataFrame(vals)
        real = B.screen_increment_quiet(pool_w, "M_pair", center_keys=("season", "player_id"))
        print("  (e) PLACEBO (%d perms, value-assignment permutation within season):" % N_PERM)
        print("      %-10s %11s %11s %11s %11s" % ("stat", "REAL", "plc_mean", "plc_SD", "frac>=real"))
        plc = {}
        for stat in ["dR2_M", "dR2_OxM"]:
            v = V[stat].values
            print("      %-10s %11.7f %11.7f %11.7f %11.3f"
                  % (stat, real[stat], v.mean(), v.std(), float((v >= real[stat]).mean())))
            plc[stat] = {"real": float(real[stat]), "mean": float(v.mean()),
                         "sd": float(v.std()), "frac_ge": float((v >= real[stat]).mean())}
            if v.std() == 0.0:
                print("      *** DEGENERATE PLACEBO (sd exactly 0) -- this is the no-op signature. ***")
        V.assign(target=T).to_csv(os.path.join(B.OUT, "f1_placebo_draws_%s.csv" % T), index=False)

        results[T] = {
            "collinearity_vs_overall_def": r_all, "collinearity_per_season": per,
            "var_between_player": bp, "var_within_player": wp,
            "var_between_opponent": bo,
            "reliability_pair_half": rh, "reliability_pair_sb": sb, "n_pairs": nu,
            "reliability_player_half": rh_p, "reliability_player_sb": sb_p,
            "pair_n_mean": float(w["pair_n"].mean()),
            "pair_n_median": float(w["pair_n"].median()),
            "frac_pair_n_ge3": float((w["pair_n"] >= 3).mean()),
            "n_rows": int(len(w)),
            "effect_raw": raw["rows"], "effect_within_player": wp_["rows"],
            "effect_thick_n3": thick["rows"] if thick else None,
            "placebo": plc,
        }
        B.safe_write(w[["game_id", "season", "game_date", "team_id", "opp_team_id", "player_id",
                        "minutes", "possessions", "y", "own_pre", "def_pre", "e",
                        "pair_n", "M_pair"]], "f1_features_%s.csv" % T)

    return results


if __name__ == "__main__":
    import json
    r = run()
    with open(os.path.join(B.OUT, "f1_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2, default=float)
    print("\nF1 done.")
