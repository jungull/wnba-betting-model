"""S03c -- PROBE 3.  EXPLORATORY, DECLARED, STILL PRE-PREREGISTRATION.

Probe 2 produced three facts that force a redesign, and this file works out what the design has
to be.  All of it is descriptive; nothing here is a test.

  (a) Ranking the roster by the CHAMPION's p_active_hat*min_hat contaminates the rotation with
      tier-B fallback rows -- declared-constant p_active 0.80 times a prefix-mean min_hat 21.7
      gives a phantom an expected 17.4 minutes, which ranks 5th-8th on many teams.  57% of K=8
      absence games have an "absentee" who has never played a game this season.  D111 ruling 3
      is exactly this defect, seen from a different direction.
      -> RANK BY THE PLAYER'S OWN STRICTLY-PRIOR TRAILING-5 MINUTES INSTEAD.  Pre-game knowable,
         phantom-free, and every member has a baseline by construction.

  (b) At K=8 the freed minutes are 27.3 per absence team-game but the remaining top-8 gain only
      ~0.98 each (~6.7 total).  Roughly three quarters of the freed volume leaves the top-8
      entirely.  -> THE REMAINING SET MUST BE THE WHOLE ESTABLISHED ROSTER, and the leakage to
      players with no established baseline has to be measured, not assumed away.

  (c) The within-team-game correlation of the realised delta with a proportional-to-baseline
      allocation is -0.2577: the BIGGEST players absorb the LEAST.  That is either a real
      ceiling effect or pure mean reversion in a noisy trailing-5.  -> the same correlation MUST
      be computed on NO-ABSENCE team-games as a control before it means anything, and the
      mean-reversion main effect must sit in the BASE before any allocation term is tested.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redist_base as rb

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
MINPRIOR = 3


def build(p, thresh):
    """ELIGIBLE = has >=3 strictly-prior same-season appearances.
       ABSENT   = ELIGIBLE, base5_minutes >= thresh, appeared == 0.
       REMAINING= ELIGIBLE, appeared == 1."""
    e = p[(p["nprior_minutes"] >= MINPRIOR) & p["base5_minutes"].notna()].copy()
    e["is_absent"] = ((e["appeared"] == 0) & (e["base5_minutes"] >= thresh)).astype(int)
    e["is_rem"] = (e["appeared"] == 1).astype(int)
    for ch in rb.CHANNELS:
        e["_f_" + ch] = np.where(e["is_absent"] == 1, e["base5_" + ch], 0.0)
    G = e.groupby(["game_id", "team_id"]).agg(
        n_absent=("is_absent", "sum"), n_rem=("is_rem", "sum"), n_elig=("is_absent", "size"),
        **{("freed_" + ch): ("_f_" + ch, "sum") for ch in rb.CHANNELS}).reset_index()
    return e, G


def main():
    rb.hdr("S03c PROBE 3 (EXPLORATORY, DECLARED)")
    P = {}
    tg = pd.read_parquet(os.path.join(rb.OUT, "_team_frame.parquet"))
    pf = pd.read_parquet(os.path.join(rb.OUT, "_player_frame.parquet"))
    rs1 = tg[tg["RS1"]][["game_id", "team_id", "season"]]
    p = pf.merge(rs1, on=["game_id", "team_id"], how="inner", suffixes=("", "_t"))

    rb.hdr("1. THE PHANTOM DIAGNOSIS -- how the champion ranking gets contaminated")
    p["exp_minutes"] = p["p_active_hat"] * p["min_hat"]
    p["rank_champ"] = p.groupby(["game_id", "team_id"])["exp_minutes"].rank(ascending=False,
                                                                           method="first")
    top8 = p[p["rank_champ"] <= 8]
    noprior = top8["nprior_minutes"] < MINPRIOR
    print("  pre-game top-8 by champion expected minutes: %d rows" % len(top8))
    print("  of those, %d (%.4f) have FEWER THAN %d prior same-season appearances"
          % (int(noprior.sum()), float(noprior.mean()), MINPRIOR))
    print("  their appearance rate: %.4f  (vs %.4f for the rest)"
          % (top8.loc[noprior, "appeared"].mean(), top8.loc[~noprior, "appeared"].mean()))
    print("  their mean p_active_hat: %.4f  mean min_hat: %.4f"
          % (top8.loc[noprior, "p_active_hat"].mean(), top8.loc[noprior, "min_hat"].mean()))
    P["phantom_diagnosis"] = {
        "n_top8_rows": int(len(top8)), "n_no_prior": int(noprior.sum()),
        "frac_no_prior": float(noprior.mean()),
        "appearance_rate_no_prior": float(top8.loc[noprior, "appeared"].mean()),
        "appearance_rate_rest": float(top8.loc[~noprior, "appeared"].mean()),
        "mean_p_active_hat_no_prior": float(top8.loc[noprior, "p_active_hat"].mean()),
        "mean_min_hat_no_prior": float(top8.loc[noprior, "min_hat"].mean())}

    rb.hdr("2. THRESHOLD SWEEP ON THE NEW, PHANTOM-FREE DEFINITION")
    rows = []
    for th in [10, 12, 15, 18, 20, 24]:
        e, G = build(p, th)
        hit = G["n_absent"] >= 1
        rows.append(dict(thresh=th, absence_games=int(hit.sum()),
                         noabs_games=int((~hit).sum()),
                         mean_n_absent=float(G.loc[hit, "n_absent"].mean()),
                         mean_freed_min=float(G.loc[hit, "freed_minutes"].mean()),
                         mean_freed_fga=float(G.loc[hit, "freed_fga"].mean()),
                         mean_freed_pts=float(G.loc[hit, "freed_pts"].mean()),
                         mean_n_rem=float(G.loc[hit, "n_rem"].mean()),
                         remaining_rows=int(G.loc[hit, "n_rem"].sum())))
    sw = pd.DataFrame(rows)
    print(sw.to_string(index=False))
    P["threshold_sweep"] = sw.to_dict("records")

    rb.hdr("3. THE ACCOUNTING -- where do the freed minutes actually go?  (thresh=15)")
    TH = 15
    e, G = build(p, TH)
    e = e.merge(G, on=["game_id", "team_id"])
    # every appeared player in the team-game, including those with NO established baseline
    allp = p.merge(G[["game_id", "team_id", "n_absent", "n_rem"]
                     + ["freed_" + c for c in rb.CHANNELS]], on=["game_id", "team_id"])
    allp["established"] = ((allp["nprior_minutes"] >= MINPRIOR)
                           & allp["base5_minutes"].notna()).astype(int)
    ap = allp[allp["appeared"] == 1].copy()
    ap["_d"] = np.where(ap["established"] == 1, ap["minutes"] - ap["base5_minutes"],
                        ap["minutes"])
    acc = ap.groupby(["game_id", "team_id"]).apply(
        lambda d: pd.Series({
            "gain_established": float(d.loc[d["established"] == 1, "_d"].sum()),
            "minutes_unestablished": float(d.loc[d["established"] == 0, "minutes"].sum()),
            "n_unestablished_played": int((d["established"] == 0).sum())}),
        include_groups=False).reset_index()
    acc = acc.merge(G, on=["game_id", "team_id"])
    hit = acc["n_absent"] >= 1
    print("  absence team-games %d, no-absence %d" % (int(hit.sum()), int((~hit).sum())))
    print("\n                                   absence      no-absence     contrast")
    for c, lab in [("freed_minutes", "freed minutes (by construction)"),
                   ("gain_established", "gain of ESTABLISHED players who played"),
                   ("minutes_unestablished", "minutes of UNESTABLISHED players"),
                   ("n_unestablished_played", "count of unestablished who played")]:
        a = float(acc.loc[hit, c].mean()); b = float(acc.loc[~hit, c].mean())
        print("  %-34s %8.4f    %8.4f    %+8.4f" % (lab, a, b, a - b))
    P["accounting_minutes"] = {
        c: {"absence": float(acc.loc[hit, c].mean()), "no_absence": float(acc.loc[~hit, c].mean())}
        for c in ["freed_minutes", "gain_established", "minutes_unestablished",
                  "n_unestablished_played"]}

    rb.hdr("4. THE MEAN-REVERSION CONTROL -- the same correlation on NO-ABSENCE games")
    rem = e[(e["is_rem"] == 1)].copy()
    rem["nrem"] = rem.groupby(["game_id", "team_id"])["minutes"].transform("size")
    for ch in rb.CHANNELS:
        rem["_d_" + ch] = rem[ch] - rem["base5_" + ch]
    rem["_absg"] = (rem["n_absent"] >= 1).astype(int)
    out = []
    for ch in rb.CHANNELS:
        for lab, sub in [("ABSENCE", rem[rem["_absg"] == 1]), ("NO-ABSENCE", rem[rem["_absg"] == 0])]:
            gm = sub.groupby(["game_id", "team_id"])
            dw = sub["_d_" + ch] - gm["_d_" + ch].transform("mean")
            bw = sub["base5_" + ch] - gm["base5_" + ch].transform("mean")
            out.append(dict(channel=ch, stratum=lab, n=len(sub),
                            within_corr_delta_vs_base5=float(np.corrcoef(dw, bw)[0, 1]),
                            mean_delta=float(sub["_d_" + ch].mean())))
    mr = pd.DataFrame(out)
    print(mr.to_string(index=False))
    print("\n  READ: if the within-team-game correlation is EQUALLY negative in the no-absence")
    print("  stratum, the 'big players absorb least' pattern of probe 2 is MEAN REVERSION in a")
    print("  noisy trailing-5 and carries no absence information at all.")
    P["mean_reversion_control"] = mr.to_dict("records")

    rb.hdr("5. RAW TREATMENT CONTRAST PER CHANNEL, established remaining players only")
    out = []
    for ch in rb.CHANNELS:
        a = rem.loc[rem["_absg"] == 1, "_d_" + ch]
        b = rem.loc[rem["_absg"] == 0, "_d_" + ch]
        out.append(dict(channel=ch, n_absence=len(a), n_noabs=len(b),
                        mean_delta_absence=float(a.mean()), mean_delta_noabs=float(b.mean()),
                        contrast=float(a.mean() - b.mean()), sd=float(rem["_d_" + ch].std()),
                        mae_zero=float(np.abs(rem["_d_" + ch]).mean())))
    rc = pd.DataFrame(out)
    print(rc.to_string(index=False))
    P["raw_contrast"] = rc.to_dict("records")

    with open(os.path.join(rb.OUT, "_s03c_probe.json"), "w", encoding="utf-8") as fh:
        json.dump(rb.jsonable(P), fh, indent=1)
    print("\n  wrote _s03c_probe.json")


if __name__ == "__main__":
    main()
