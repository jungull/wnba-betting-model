"""S04 -- STEP 4.  THE MAIN-EFFECT TEST THAT HAS NEVER BEEN RUN, AND THE ABSORPTION TEST.

D076 screened home/away as a predictor of |residual| -- WHERE THE MODEL ERRS.  That is a different
question.  This asks whether adding a home/away MAIN EFFECT to a strictly-prior-games-only forecast
IMPROVES it.

REFERENCES.  Four, all strictly prior-games-only, all COMPLETE in the required sense (they consume
every available prior measurement of the target in the base, not a truncated window):
    REF_EXPANDING_COMPLETE      expanding mean of every prior same-season game
    REF_EWMA8_COMPLETE          EWMA half-life 8 over the same prior set (E1_I0022's winning form)
    REF_VENUE_SPLIT_EXPANDING   the same, restricted to prior games AT THE SAME VENUE TYPE
    REF_VENUE_SPLIT_EWMA8       ditto with the EWMA
The venue-split pair IS the absorption test: if a real home increment is being hidden inside a
blended reference, splitting the reference by venue must recover it.

THE INCREMENT.  yhat = ref + a + b*(is_home - 0.5), with a and b fitted by OLS on the residual
(y - ref) over STRICTLY EARLIER SEASONS ONLY.  The base arm carries `a` too, so `b` is isolated and
the comparison is not contaminated by the intercept correction.

DENOMINATOR RULE (D099).  Every dR2 is reported on the SST of the FULL pooled evaluation stratum.
The decision-stratum numbers are additionally reported on the decision stratum's OWN SST, and both
are labelled; the two are never mixed.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

import ha_base as hb
import s00_prereg
import screenkit as sk

EVAL_SEASONS = [2022, 2023, 2024]
N_DRAWS = 4000


# ------------------------------------------------------------------ strictly-prior reference cores
def _prefix_expanding(v, starts, ns):
    """est[p] = mean of v[0..p-1] within the block; NaN at p == 0."""
    out = np.full(len(v), np.nan)
    for a, n in zip(starts, ns):
        c = np.r_[0.0, np.cumsum(v[a:a + n])]
        k = np.arange(n, dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[a:a + n] = np.where(k > 0, c[:n] / np.where(k > 0, k, 1.0), np.nan)
    return out


def _prefix_ewma(v, starts, ns, half_life):
    """est[p] = EWMA of v[0..p-1]; NaN at p == 0.  Decayed toward the most recent prior game."""
    lam = 0.5 ** (1.0 / half_life)
    out = np.full(len(v), np.nan)
    for a, n in zip(starts, ns):
        e = w = 0.0
        for j in range(n):
            out[a + j] = (e / w) if w > 0 else np.nan
            e = lam * e + v[a + j]
            w = lam * w + 1.0
    return out


def _prefix_by_venue(v, home, starts, ns, kind, half_life=8.0):
    """Same as above but each row sees ONLY prior rows with the SAME venue type."""
    out = np.full(len(v), np.nan)
    lam = 0.5 ** (1.0 / half_life)
    for a, n in zip(starts, ns):
        acc = {0: [0.0, 0.0], 1: [0.0, 0.0]}     # [sum-or-ewma, count-or-weight]
        for j in range(n):
            k = int(home[a + j])
            s, c = acc[k]
            out[a + j] = (s / c) if c > 0 else np.nan
            if kind == "expanding":
                acc[k] = [s + v[a + j], c + 1.0]
            else:
                acc[k] = [lam * s + v[a + j], lam * c + 1.0]
    return out


def _prev_season_player(f, col):
    g = f.groupby(["season", "player_id"])[col].mean()
    lut = {(int(s) + 1, int(p)): float(v) for (s, p), v in g.items()}
    return np.array([lut.get((int(s), int(p)), np.nan)
                     for s, p in zip(f["season"], f["player_id"])])


def _league_prior(f, col):
    """same-season league mean over games on STRICTLY EARLIER DATES (date-blocked, not row-shifted:
    a plain shift would let a row see other games played the SAME day, which are not pre-game)."""
    out = np.full(len(f), np.nan)
    s = f["season"].to_numpy()
    d = f["game_date"].to_numpy()
    v = f[col].to_numpy(float)
    for ss in np.unique(s):
        m = np.flatnonzero(s == ss)
        order = m[np.argsort(d[m], kind="stable")]
        dd = d[order]
        c = np.r_[0.0, np.cumsum(v[order])]
        first = np.searchsorted(dd, dd, side="left")
        with np.errstate(invalid="ignore", divide="ignore"):
            out[order] = np.where(first > 0, c[first] / np.where(first > 0, first, 1.0), np.nan)
    return out


def build_refs(f, col):
    """The four references plus the fallback chain, all strictly prior."""
    codes, starts, ns = hb.group_bounds(f, ["season", "player_id"])
    v = f[col].to_numpy(float)
    home = f["is_home"].to_numpy(int)
    prevpl = _prev_season_player(f, col)
    league = _league_prior(f, col)
    grand = float(np.nanmean(v))          # ONLY fires on rows with no prior of ANY kind; counted.

    def chain(x):
        y = np.where(np.isfinite(x), x, prevpl)
        y = np.where(np.isfinite(y), y, league)
        n_grand = int((~np.isfinite(y)).sum())
        return np.where(np.isfinite(y), y, grand), n_grand

    out, counts = {}, {}
    out["REF_EXPANDING_COMPLETE"], counts["REF_EXPANDING_COMPLETE"] = chain(
        _prefix_expanding(v, starts, ns))
    out["REF_EWMA8_COMPLETE"], counts["REF_EWMA8_COMPLETE"] = chain(
        _prefix_ewma(v, starts, ns, 8.0))
    # the venue-split refs fall back FIRST to the all-games ref of the same form (documented in the
    # prereg), then down the same chain -- otherwise "venue split" would be silently testing
    # "smaller sample" instead of "venue".
    vs_e = _prefix_by_venue(v, home, starts, ns, "expanding")
    vs_w = _prefix_by_venue(v, home, starts, ns, "ewma", 8.0)
    out["REF_VENUE_SPLIT_EXPANDING"], counts["REF_VENUE_SPLIT_EXPANDING"] = chain(
        np.where(np.isfinite(vs_e), vs_e, _prefix_expanding(v, starts, ns)))
    out["REF_VENUE_SPLIT_EWMA8"], counts["REF_VENUE_SPLIT_EWMA8"] = chain(
        np.where(np.isfinite(vs_w), vs_w, _prefix_ewma(v, starts, ns, 8.0)))
    counts["_n_rows_using_venue_split_prefix"] = int(np.isfinite(vs_e).sum())
    return out, counts, grand


def mae(y, yh):
    m = np.isfinite(y) & np.isfinite(yh)
    return float(np.mean(np.abs(y[m] - yh[m])))


def r2f(y, yh, sst=None):
    m = np.isfinite(y) & np.isfinite(yh)
    yy, hh = y[m], yh[m]
    sse = float(((yy - hh) ** 2).sum())
    if sst is None:
        sst = float(((yy - yy.mean()) ** 2).sum())
    return 1.0 - sse / sst


def main():
    hb.hdr("S04 MAIN-EFFECT TEST AND REFERENCE ABSORPTION")
    prereg = s00_prereg.assert_prereg_unchanged()
    FIND = {"prereg_sha256": prereg["prereg_sha256"]}

    p = pd.read_parquet(os.path.join(hb.OUT, "_player_frame.parquet"))
    sk.assert_partition(p[["season", "game_date"]], verbose=False)
    f = p[(p["season_type"] == "Regular Season") & (p["appeared"] == 1)].copy()
    f = f.sort_values(["season", "player_id", "game_date", "game_id"],
                      kind="stable").reset_index(drop=True)
    f["ppm"] = f["pts"] / f["minutes"]
    print("  frame: %s   seasons %s" % (f.shape, sorted(f["season"].unique())))

    # ---------- decision stratum (D081): >=8 prior appearances AND trailing-5 mean minutes >= 24
    codes, starts, ns = hb.group_bounds(f, ["season", "player_id"])
    nprior = np.empty(len(f))
    tr5 = np.full(len(f), np.nan)
    mv = f["minutes"].to_numpy(float)
    for a, n in zip(starts, ns):
        nprior[a:a + n] = np.arange(n, dtype=float)
        c = np.r_[0.0, np.cumsum(mv[a:a + n])]
        for j in range(n):
            lo = max(0, j - 5)
            k = j - lo
            tr5[a + j] = (c[j] - c[lo]) / k if k > 0 else np.nan
    f["n_prior_app"] = nprior
    f["trail5_min"] = tr5
    f["decision_stratum"] = ((f["n_prior_app"] >= 8) & (f["trail5_min"] >= 24)).astype(int)
    print("  decision stratum (>=8 prior apps, trailing-5 mean minutes >=24): %d of %d rows "
          "(%.1f%%)" % (int(f["decision_stratum"].sum()), len(f),
                        100.0 * f["decision_stratum"].mean()))

    # ---------- THE DETECTION-FLOOR ARITHMETIC: how big IS the per-player home increment?
    hb.hdr("A. THE SIZE OF THE THING BEING LOOKED FOR (before any test)")
    floor = {}
    for tgt in ["pts", "minutes", "ppm", "fga", "fta"]:
        dh = float(f.loc[f.is_home == 1, tgt].mean() - f.loc[f.is_home == 0, tgt].mean())
        sd = float(f[tgt].std(ddof=1))
        # what an expanding reference built from a ~50/50 blend of venues misses: the reference sits
        # at the blend, so the venue-conditional increment relative to it is HALF the home-away gap
        inc = dh / 2.0
        # the best achievable dR2 from a perfectly known constant shift of size `inc`
        best_dr2 = (inc / sd) ** 2
        floor[tgt] = {"home_minus_away_per_appearance": dh, "sd_of_target": sd,
                      "increment_vs_blended_reference": inc,
                      "increment_as_frac_of_sd": inc / sd,
                      "max_attainable_dR2": best_dr2,
                      "n_rows_for_dR2_of_2sd_detection": (2.0 / (inc / sd)) ** 2}
        print("  %-8s home-away per appearance = %+.5f   sd = %.4f   increment vs a blended "
              "reference = %+.5f" % (tgt, dh, sd, inc))
        print("           => %.4f%% of one sd; the LARGEST dR2 a perfect home term could add is "
              "%.3e" % (100 * inc / sd, best_dr2))
    FIND["detection_floor_arithmetic"] = floor
    print("  This is computed BEFORE any model is fitted and it is the whole explanation of the")
    print("  programme's player-level nulls: the quantity is real and it is roughly 1% of a")
    print("  player's own game-to-game spread.")

    # ---------- build references and run the walk-forward main-effect test
    hb.hdr("B. WALK-FORWARD MAIN-EFFECT TEST")
    rows, pair_rows = [], []
    refcounts = {}
    yhat_store = {}
    for tgt in ["pts", "minutes", "ppm", "fga"]:
        refs, counts, grand = build_refs(f, tgt)
        refcounts[tgt] = counts
        y = f[tgt].to_numpy(float)
        hcent = f["is_home"].to_numpy(float) - 0.5
        season = f["season"].to_numpy()
        ev = np.isin(season, EVAL_SEASONS)
        for rname, ref in refs.items():
            base = np.full(len(f), np.nan)
            full = np.full(len(f), np.nan)
            betas = {}
            for s in EVAL_SEASONS:
                tr = season < s
                te = season == s
                r = y[tr] - ref[tr]
                X = np.column_stack([np.ones(tr.sum()), hcent[tr]])
                coef, *_ = np.linalg.lstsq(X, r, rcond=None)
                a0, b1 = float(coef[0]), float(coef[1])
                base[te] = ref[te] + a0
                full[te] = ref[te] + a0 + b1 * hcent[te]
                betas[str(s)] = {"intercept": a0, "beta_home": b1, "n_train": int(tr.sum())}
            yhat_store[(tgt, rname, "base")] = base
            yhat_store[(tgt, rname, "full")] = full
            for sname, mask in [("POOLED", ev),
                                ("DECISION_STRATUM", ev & (f["decision_stratum"] == 1).to_numpy())]:
                yy, bb, ff = y[mask], base[mask], full[mask]
                sst_full = float(((y[ev] - y[ev].mean()) ** 2).sum())      # COMMON denominator
                sst_sub = float(((yy - yy.mean()) ** 2).sum())
                rows.append(dict(
                    target=tgt, reference=rname, stratum=sname, n=int(mask.sum()),
                    mae_base=mae(yy, bb), mae_full=mae(yy, ff),
                    mae_improvement_pct=100.0 * (1.0 - mae(yy, ff) / mae(yy, bb)),
                    r2_base_commonSST=r2f(yy, bb, sst_full),
                    r2_full_commonSST=r2f(yy, ff, sst_full),
                    dR2_commonSST=r2f(yy, ff, sst_full) - r2f(yy, bb, sst_full),
                    dR2_ownSST_LABELLED=r2f(yy, ff, sst_sub) - r2f(yy, bb, sst_sub),
                    beta_home_2022=betas["2022"]["beta_home"],
                    beta_home_2023=betas["2023"]["beta_home"],
                    beta_home_2024=betas["2024"]["beta_home"]))
                cl = (f.loc[mask, "season"].astype(str) + "_"
                      + f.loc[mask, "player_id"].astype(str)).to_numpy()
                pc = sk.paired_forecast_comparison(yy, ff, bb, cl, n_draws=N_DRAWS,
                                                   seed=hb.SEED, name_a="with_home_term",
                                                   name_b="reference_only",
                                                   alternative="two_sided")
                pair_rows.append(dict(target=tgt, reference=rname, stratum=sname,
                                      dr2_a_minus_b=pc["dr2_a_minus_b"],
                                      p_cluster=pc["p"],
                                      p_row_level_NAIVE=pc["p_row_level_NAIVE"],
                                      inflation=pc.get("inflation"),
                                      n_clusters=pc.get("n_clusters")))
    me = pd.DataFrame(rows)
    pcmp = pd.DataFrame(pair_rows)
    me = me.merge(pcmp, on=["target", "reference", "stratum"], how="left")
    me.to_csv(os.path.join(hb.OUT, "main_effect_test.csv"), index=False)
    FIND["reference_fallback_counts"] = refcounts

    for sname in ["POOLED", "DECISION_STRATUM"]:
        print("\n  --- %s ---" % sname)
        sh = me[me.stratum == sname][["target", "reference", "n", "mae_base", "mae_full",
                                      "mae_improvement_pct", "dR2_commonSST", "p_cluster",
                                      "beta_home_2024"]]
        print(sh.to_string(index=False, float_format=lambda x: "%.6f" % x))

    # ---------- C. REFERENCE ABSORPTION, TESTED DIRECTLY
    hb.hdr("C. REFERENCE ABSORPTION -- venue-split reference vs all-games reference")
    abs_rows = []
    y_all = f[["pts", "minutes", "ppm", "fga"]]
    ev = np.isin(f["season"].to_numpy(), EVAL_SEASONS)
    for tgt in ["pts", "minutes", "ppm", "fga"]:
        y = y_all[tgt].to_numpy(float)
        for form, a_name, b_name in [
                ("expanding", "REF_VENUE_SPLIT_EXPANDING", "REF_EXPANDING_COMPLETE"),
                ("ewma8", "REF_VENUE_SPLIT_EWMA8", "REF_EWMA8_COMPLETE")]:
            A = yhat_store[(tgt, a_name, "base")]
            B = yhat_store[(tgt, b_name, "base")]
            m = ev & np.isfinite(A) & np.isfinite(B)
            cl = (f.loc[m, "season"].astype(str) + "_" + f.loc[m, "player_id"].astype(str)).to_numpy()
            pc = sk.paired_forecast_comparison(y[m], A[m], B[m], cl, n_draws=N_DRAWS,
                                               seed=hb.SEED, name_a="venue_split",
                                               name_b="all_games", alternative="two_sided")
            abs_rows.append(dict(target=tgt, form=form, n=int(m.sum()),
                                 mae_venue_split=mae(y[m], A[m]), mae_all_games=mae(y[m], B[m]),
                                 mae_improvement_pct=100.0 * (1 - mae(y[m], A[m]) / mae(y[m], B[m])),
                                 dr2_venue_minus_all=pc["dr2_a_minus_b"], p_cluster=pc["p"],
                                 p_row_level_NAIVE=pc["p_row_level_NAIVE"]))
            print("  %-8s %-10s  MAE venue-split=%.5f  all-games=%.5f  improvement=%+.3f%%  "
                  "dR2=%+.3e  p=%.4f"
                  % (tgt, form, mae(y[m], A[m]), mae(y[m], B[m]),
                     100.0 * (1 - mae(y[m], A[m]) / mae(y[m], B[m])), pc["dr2_a_minus_b"], pc["p"]))
    ab = pd.DataFrame(abs_rows)
    ab.to_csv(os.path.join(hb.OUT, "reference_absorption.csv"), index=False)

    # ---------- D. negative control: a FAKE home label, same pipeline
    hb.hdr("D. NEGATIVE CONTROL -- a fake venue label through the identical pipeline")
    rng = np.random.default_rng(hb.SEED + 7)
    gids = f["game_id"].to_numpy()
    uq, inv = np.unique(gids, return_inverse=True)
    flip = rng.integers(0, 2, size=len(uq)).astype(float)[inv]
    fake = np.where(flip > 0, 1.0 - f["is_home"].to_numpy(float), f["is_home"].to_numpy(float))
    nc = []
    for tgt in ["pts", "ppm"]:
        refs, _, _ = build_refs(f, tgt)
        ref = refs["REF_EWMA8_COMPLETE"]
        y = f[tgt].to_numpy(float)
        for label, hv in [("REAL_is_home", f["is_home"].to_numpy(float)), ("FAKE_label", fake)]:
            hc = hv - 0.5
            base = np.full(len(f), np.nan)
            full = np.full(len(f), np.nan)
            season = f["season"].to_numpy()
            for s in EVAL_SEASONS:
                tr, te = season < s, season == s
                X = np.column_stack([np.ones(tr.sum()), hc[tr]])
                coef, *_ = np.linalg.lstsq(X, y[tr] - ref[tr], rcond=None)
                base[te] = ref[te] + coef[0]
                full[te] = ref[te] + coef[0] + coef[1] * hc[te]
            m = np.isin(season, EVAL_SEASONS)
            cl = (f.loc[m, "season"].astype(str) + "_" + f.loc[m, "player_id"].astype(str)).to_numpy()
            pc = sk.paired_forecast_comparison(y[m], full[m], base[m], cl, n_draws=N_DRAWS,
                                               seed=hb.SEED, alternative="two_sided")
            nc.append(dict(target=tgt, label=label, dr2=pc["dr2_a_minus_b"], p=pc["p"],
                           mae_improvement_pct=100 * (1 - mae(y[m], full[m]) / mae(y[m], base[m]))))
            print("  %-5s %-14s  dR2=%+.3e  p=%.4f  MAE improvement=%+.4f%%"
                  % (tgt, label, pc["dr2_a_minus_b"], pc["p"], nc[-1]["mae_improvement_pct"]))
    FIND["negative_control_fake_label"] = nc

    FIND["main_effect"] = me.to_dict("records")
    FIND["absorption"] = ab.to_dict("records")
    with open(os.path.join(hb.OUT, "_s04.json"), "w", encoding="utf-8") as fh:
        json.dump(hb.jsonable(FIND), fh, indent=2)
    print("\n  wrote main_effect_test.csv, reference_absorption.csv, _s04.json")


if __name__ == "__main__":
    main()
