"""S03d -- PROBE 4.  EXPLORATORY, DECLARED, THE LAST ONE BEFORE PREREGISTRATION.

Probe 3 left an accounting hole: freed 35.2 minutes but only +9.3 of contrast reached the
established remaining players and the unestablished players' minutes went DOWN.  The hole is the
>=15-minute threshold -- an established player with a base5 of 11 minutes who sits is neither an
"absentee" nor a "remaining player", so their freed minutes vanish from the accounting.

This probe drops the threshold entirely (FREED = every established player who did not appear),
checks that the minute accounting then CLOSES, and computes the per-cell arithmetic ceiling that
PREREG.md has to quote.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redist_base as rb

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
MINPRIOR = 3


def main():
    rb.hdr("S03d PROBE 4 (EXPLORATORY, DECLARED)")
    P = {}
    tg = pd.read_parquet(os.path.join(rb.OUT, "_team_frame.parquet"))
    pf = pd.read_parquet(os.path.join(rb.OUT, "_player_frame.parquet"))
    rs1 = tg[tg["RS1"]][["game_id", "team_id", "season"]]
    p = pf.merge(rs1, on=["game_id", "team_id"], how="inner", suffixes=("", "_t"))

    p["established"] = ((p["nprior_minutes"] >= MINPRIOR) & p["base5_minutes"].notna()).astype(int)
    e = p[p["established"] == 1].copy()
    e["is_absent"] = (e["appeared"] == 0).astype(int)
    for ch in rb.CHANNELS:
        e["_f_" + ch] = np.where(e["is_absent"] == 1, e["base5_" + ch], 0.0)
    G = e.groupby(["game_id", "team_id"]).agg(
        n_absent=("is_absent", "sum"), n_elig=("is_absent", "size"),
        n_rem=("appeared", "sum"),
        **{("freed_" + ch): ("_f_" + ch, "sum") for ch in rb.CHANNELS},
        **{("B_" + ch): ("base5_" + ch, "sum") for ch in rb.CHANNELS}).reset_index()
    G = G.merge(rs1, on=["game_id", "team_id"])
    print("  team-games %d   mean established %.3f   mean absent %.3f   mean remaining %.3f"
          % (len(G), G["n_elig"].mean(), G["n_absent"].mean(), G["n_rem"].mean()))
    print("  FREED distribution (minutes): mean %.4f  median %.4f  frac>0 %.4f  p90 %.4f"
          % (G["freed_minutes"].mean(), G["freed_minutes"].median(),
             (G["freed_minutes"] > 0).mean(), G["freed_minutes"].quantile(0.9)))
    print("  n_absent value counts:")
    print(G["n_absent"].value_counts().sort_index().head(10).to_string())
    P["team_frame"] = {"n_teamgames": int(len(G)),
                       "mean_established": float(G["n_elig"].mean()),
                       "mean_absent": float(G["n_absent"].mean()),
                       "mean_remaining": float(G["n_rem"].mean()),
                       "mean_freed_minutes": float(G["freed_minutes"].mean()),
                       "frac_freed_gt0": float((G["freed_minutes"] > 0).mean())}

    rb.hdr("1. DOES THE MINUTE ACCOUNTING CLOSE?")
    rem = e[e["appeared"] == 1].merge(G, on=["game_id", "team_id"], suffixes=("", "_g"))
    gain = (rem.assign(_d=rem["minutes"] - rem["base5_minutes"])
            .groupby(["game_id", "team_id"])["_d"].sum().rename("gain_est").reset_index())
    unest = (p[(p["established"] == 0) & (p["appeared"] == 1)]
             .groupby(["game_id", "team_id"])["minutes"].sum().rename("unest_min").reset_index())
    A = G.merge(gain, on=["game_id", "team_id"], how="left").merge(
        unest, on=["game_id", "team_id"], how="left")
    A["gain_est"] = A["gain_est"].fillna(0.0); A["unest_min"] = A["unest_min"].fillna(0.0)
    A["resid"] = A["gain_est"] - A["freed_minutes"]
    A["predicted_resid"] = 200.0 - A["unest_min"] - A["B_minutes"]
    print("  identity check   gain_est - freed  ==  200 - unest_min - B_minutes  + OT slack")
    print("    mean gain_est - freed        %+.4f" % A["resid"].mean())
    print("    mean 200 - unest - B         %+.4f" % A["predicted_resid"].mean())
    print("    mean discrepancy (OT etc.)   %+.4f  sd %.4f"
          % ((A["resid"] - A["predicted_resid"]).mean(),
             (A["resid"] - A["predicted_resid"]).std()))
    q = A["freed_minutes"] > 0
    print("\n  by absence stratum:")
    print("    freed>0  n=%4d  gain_est %+.4f  freed %+.4f  ratio %.4f"
          % (int(q.sum()), A.loc[q, "gain_est"].mean(), A.loc[q, "freed_minutes"].mean(),
             A.loc[q, "gain_est"].mean() / A.loc[q, "freed_minutes"].mean()))
    print("    freed=0  n=%4d  gain_est %+.4f" % (int((~q).sum()), A.loc[~q, "gain_est"].mean()))
    print("    CONTRAST gain_est %+.4f   per unit freed %.4f"
          % (A.loc[q, "gain_est"].mean() - A.loc[~q, "gain_est"].mean(),
             (A.loc[q, "gain_est"].mean() - A.loc[~q, "gain_est"].mean())
             / A.loc[q, "freed_minutes"].mean()))
    b = np.polyfit(A["freed_minutes"], A["gain_est"], 1)
    print("  POOLED OLS slope of gain_est on freed_minutes: %.4f (intercept %+.4f)" % (b[0], b[1]))
    P["accounting"] = {"mean_resid": float(A["resid"].mean()),
                       "mean_predicted_resid": float(A["predicted_resid"].mean()),
                       "mean_discrepancy": float((A["resid"] - A["predicted_resid"]).mean()),
                       "pooled_slope": float(b[0]), "pooled_intercept": float(b[1])}

    rb.hdr("2. THE SAME SLOPE FOR FGA AND POINTS (not budget-constrained a priori)")
    for ch in ["fga", "pts"]:
        gn = (rem.assign(_d=rem[ch] - rem["base5_" + ch])
              .groupby(["game_id", "team_id"])["_d"].sum().rename("gain").reset_index())
        Ax = G.merge(gn, on=["game_id", "team_id"], how="left")
        Ax["gain"] = Ax["gain"].fillna(0.0)
        bb = np.polyfit(Ax["freed_" + ch], Ax["gain"], 1)
        print("  %-4s pooled slope %.4f  intercept %+.4f   mean freed %.4f"
              % (ch, bb[0], bb[1], Ax["freed_" + ch].mean()))
        P.setdefault("pooled_slopes", {})[ch] = {"slope": float(bb[0]),
                                                 "intercept": float(bb[1])}

    rb.hdr("3. ANALYSIS ROW SET RSP AND THE ARITHMETIC CEILING PER CELL")
    R = rem.copy()
    R["nrem"] = R.groupby(["game_id", "team_id"])["minutes"].transform("size")
    rows = []
    for ch in rb.CHANNELS:
        R["_d"] = R[ch] - R["base5_" + ch]
        R["_u"] = R["freed_" + ch] / R["nrem"]
        gm = R.groupby(["game_id", "team_id"])
        R["_z"] = ((R["base5_" + ch] - gm["base5_" + ch].transform("mean"))
                   / gm["base5_" + ch].transform("std").replace(0, np.nan)).fillna(0.0)
        mae0 = float(np.abs(R["_d"] - R["_d"].mean()).mean())
        rows.append(dict(
            channel=ch, n_rows=int(len(R)), n_blocks=int(gm.ngroups),
            sd_delta=float(R["_d"].std()),
            mean_uniform_term=float(R["_u"].mean()), sd_uniform_term=float(R["_u"].std()),
            mae_centred_base=mae0,
            ceiling_frac_of_mae=float(R["_u"].std() / mae0),
            corr_delta_uniform=float(np.corrcoef(R["_d"], R["_u"])[0, 1]),
            corr_delta_tilt=float(np.corrcoef(R["_d"], R["_u"] * R["_z"])[0, 1]),
            champ_mae=float(np.abs(R[ch] - R[{"minutes": "min_hat", "fga": "fga_hat",
                                              "pts": "pts_hat"}[ch]]).mean()),
            base5_mae=float(np.abs(R[ch] - R["base5_" + ch]).mean())))
    ce = pd.DataFrame(rows)
    print(ce.to_string(index=False))
    P["ceiling"] = ce.to_dict("records")

    rb.hdr("4. POSITION MATCH AVAILABILITY")
    def posgroup(s):
        s = ("" if not isinstance(s, str) else s)
        return s.split("-")[0] if s else None
    e2 = e.copy(); e2["pg"] = e2["position_raw"].map(posgroup)
    absn = e2[e2["is_absent"] == 1]
    print("  absentee rows %d, position group known for %d (%.4f)"
          % (len(absn), int(absn["pg"].notna().sum()), float(absn["pg"].notna().mean())))
    print("  remaining rows %d, position group known for %.4f"
          % (int((e2["appeared"] == 1).sum()),
             float(e2.loc[e2["appeared"] == 1, "pg"].notna().mean())))
    P["position_coverage"] = {
        "absentee_rows": int(len(absn)),
        "absentee_pos_known": float(absn["pg"].notna().mean()),
        "remaining_pos_known": float(e2.loc[e2["appeared"] == 1, "pg"].notna().mean())}

    with open(os.path.join(rb.OUT, "_s03d_probe.json"), "w", encoding="utf-8") as fh:
        json.dump(rb.jsonable(P), fh, indent=1)
    print("\n  wrote _s03d_probe.json")


if __name__ == "__main__":
    main()
