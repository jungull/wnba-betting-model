"""S08 -- THE DECLARED SECONDARY WINDOW, THE STRATIFICATIONS, AND THE DESCRIPTIVE ACCOUNTING.

Nothing here is a new preregistered cell.  Three kinds of thing:
  1  W1 (2022-2024) reruns of the five cells that do not touch the champion, with the DIRECTION
     each one moves stated explicitly.
  2  STRATIFICATIONS of preregistered cells -- the same statistic on a subset of its own row set.
     Reported with their own n, never substituted for the headline.
  3  DESCRIPTIVE accounting: where the freed minutes actually go.  No null, no verdict.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redist_base as rb
import s04_prereg
import s06_cells as s6

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
W2 = (2023, 2024)
W1 = (2022, 2023, 2024)
NDRAW = 20000
NDRAW_N1 = 2000
CHAMP_COL = {"minutes": "min_hat", "fga": "fga_hat", "pts": "pts_hat"}


def main():
    rb.hdr("S08 SECONDARY WINDOW, STRATIFICATIONS, ACCOUNTING")
    pre = s04_prereg.assert_unchanged()
    print("  prereg hash verified: %s" % pre["prereg_sha256"])
    S = {"prereg_sha256": pre["prereg_sha256"]}
    S6 = json.load(open(os.path.join(rb.OUT, "_s06.json"), encoding="utf-8"))

    R = pd.read_parquet(os.path.join(rb.OUT, "_rem_frame.parquet")).sort_values(
        ["season", "game_id", "team_id", "player_id"], kind="stable").reset_index(drop=True)
    G = pd.read_parquet(os.path.join(rb.OUT, "_tg_frame.parquet")).sort_values(
        ["season", "game_id", "team_id"], kind="stable").reset_index(drop=True)
    rs = R["season"].to_numpy(); gs = G["season"].to_numpy()
    tgc = pd.factorize(R["tg"])[0]
    ord_t, b_t, sz_t = s6.block_bounds(tgc)
    ord_s, b_s, sz_s = s6.block_bounds(gs)

    # ---------------------------------------------------------------- 1. W1 rerun
    rb.hdr("1. DECLARED SECONDARY WINDOW W1 = 2022-2024")
    rows = []
    for ch in rb.CHANNELS:
        y = G["unest_" + ch].to_numpy(float); x = G["freed_" + ch].to_numpy(float)
        real, _ = s6.wf_coef([x], y, gs, W1, 2021, 1)
        rng = np.random.default_rng(rb.SEED + 1401)
        dr = np.array([s6.wf_coef([x[s6.perm_index(ord_s, b_s, sz_s, rng)]], y, gs, W1,
                                  2021, 1)[0] for _ in range(4000)])
        nm, sd = float(dr.mean()), float(dr.std(ddof=1))
        p = float((1 + int((np.abs(dr - nm) >= abs(real - nm)).sum())) / 4001.0)
        w2 = S6["cells"]["P01_LEAKAGE_" + ch]
        rows.append(dict(cell="P01_LEAKAGE_" + ch, W2_effect=w2["effect"], W1_effect=real,
                         W1_p=p, W1_null_sd=sd, W1_MDE80=rb.mde80(sd),
                         direction=("W1 makes it LARGER in magnitude" if abs(real) > abs(w2["effect"])
                                    else "W1 makes it SMALLER in magnitude")))
    for ch in rb.CHANNELS:
        y = R["d_" + ch].to_numpy(float)
        b5 = R["base5_" + ch].to_numpy(float); z = R["z_" + ch].to_numpy(float)
        u = R["u_" + ch].to_numpy(float)
        real, _ = s6.wf_coef([b5, z, u, u * z], y, rs, W1, 2021, 4)
        rng = np.random.default_rng(rb.SEED + 1402)
        dr = np.empty(1000)
        for i in range(1000):
            inv = s6.perm_index(ord_t, b_t, sz_t, rng)
            dr[i] = s6.wf_coef([b5[inv], z[inv], u, u * z[inv]], y, rs, W1, 2021, 4)[0]
        nm, sd = float(dr.mean()), float(dr.std(ddof=1))
        p = float((1 + int((np.abs(dr - nm) >= abs(real - nm)).sum())) / 1001.0)
        w2 = S6["cells"]["P02_TILT_" + ch]
        rows.append(dict(cell="P02_TILT_" + ch, W2_effect=w2["effect"], W1_effect=real,
                         W1_p=p, W1_null_sd=sd, W1_MDE80=rb.mde80(sd),
                         direction=("W1 makes it LARGER in magnitude" if abs(real) > abs(w2["effect"])
                                    else "W1 makes it SMALLER in magnitude")))
    for ch in rb.CHANNELS:
        y = R[ch].to_numpy(float)
        b5 = R["base5_" + ch].to_numpy(float); z = R["z_" + ch].to_numpy(float)
        u = R["u_" + ch].to_numpy(float)
        yh0, _ = s6.wf_predict([b5, z], y, rs, W1, 2021)
        yh1, _ = s6.wf_predict([b5, z, u, u * z], y, rs, W1, 2021)
        m = np.isin(rs, W1)
        l0 = np.abs(y[m] - yh0[m]); l1 = np.abs(y[m] - yh1[m])
        n2 = rb.paired_signflip_block(l1, l0, R["tg"].to_numpy()[m], NDRAW, rb.SEED + 1403)
        w2 = S6["cells"]["P03_GAIN_vs_BASE5_ORACLEABS_" + ch]
        rows.append(dict(cell="P03_" + ch, W2_effect=w2["effect"], W1_effect=n2["real"],
                         W1_p=n2["p"], W1_null_sd=n2["null_sd"],
                         W1_MDE80=rb.mde80(n2["null_sd"]),
                         direction=("W1 makes it LARGER" if n2["real"] > w2["effect"]
                                    else "W1 makes it SMALLER")))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    S["secondary_W1"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "secondary_window_W1.csv"), index=False)

    # ---------------------------------------------------------------- 2. stratifications
    rb.hdr("2. STRATIFICATION OF P03/P04 -- the gain where the treatment is actually ON")
    rows = []
    for ch in rb.CHANNELS:
        y = R[ch].to_numpy(float)
        b5 = R["base5_" + ch].to_numpy(float); z = R["z_" + ch].to_numpy(float)
        u = R["u_" + ch].to_numpy(float)
        cf = R[CHAMP_COL[ch]].to_numpy(float)
        m = np.isin(rs, W2)
        for lab, X0, X1, off, mint in [
                ("P03_vs_base5", [b5, z], [b5, z, u, u * z], None, 2021),
                ("P04_vs_champion", [], [u, u * z], cf, 2022)]:
            ofs = np.zeros(len(y)) if off is None else off
            yh0, _ = s6.wf_predict(X0, y - ofs, rs, W2, mint)
            yh1, _ = s6.wf_predict(X1, y - ofs, rs, W2, mint)
            f0 = yh0 + ofs; f1 = yh1 + ofs
            for sname, smask in [("ALL", m), ("FREED>0", m & (u > 0)),
                                 ("FREED>=25min-equivalent", m & (R["freed_minutes"].to_numpy() >= 25.0)),
                                 ("FREED=0", m & (u == 0))]:
                if smask.sum() < 50:
                    continue
                l0 = np.abs(y[smask] - f0[smask]); l1 = np.abs(y[smask] - f1[smask])
                n2 = rb.paired_signflip_block(l1, l0, R["tg"].to_numpy()[smask], NDRAW,
                                              rb.SEED + 1500)
                rows.append(dict(cell=lab + "_" + ch, stratum=sname, n=int(smask.sum()),
                                 n_blocks=n2["n_blocks"], MAE_M0=float(l0.mean()),
                                 MAE_M1=float(l1.mean()), dMAE=n2["real"], p=n2["p"],
                                 null_sd=n2["null_sd"], MDE80=rb.mde80(n2["null_sd"]),
                                 pct_of_MAE=100.0 * n2["real"] / float(l0.mean())))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    S["stratification"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "stratification_by_freed.csv"), index=False)

    # ---------------------------------------------------------------- 3. accounting
    rb.hdr("3. DESCRIPTIVE ACCOUNTING -- where the freed minutes go")
    A = G[G["season"].isin(W2)].copy()
    rem = R[R["season"].isin(W2)]
    gain = (rem.assign(_d=rem["minutes"] - rem["base5_minutes"])
            .groupby(["game_id", "team_id"])["_d"].sum().rename("gain_established").reset_index())
    A = A.merge(gain, on=["game_id", "team_id"], how="left")
    A["gain_established"] = A["gain_established"].fillna(0.0)
    A["freed_bucket"] = pd.cut(A["freed_minutes"], [-0.01, 0.01, 15, 30, 45, 1e9],
                               labels=["0", "0-15", "15-30", "30-45", "45+"])
    acc = A.groupby("freed_bucket", observed=True).agg(
        n_teamgames=("freed_minutes", "size"),
        mean_freed=("freed_minutes", "mean"),
        mean_gain_established=("gain_established", "mean"),
        mean_unest_minutes=("unest_minutes", "mean"),
        mean_n_absent=("n_absent", "mean"),
        mean_n_rem=("n_rem", "mean")).reset_index()
    acc["gain_per_freed_minute"] = acc["mean_gain_established"] / acc["mean_freed"].replace(0, np.nan)
    acc["gain_per_remaining_player"] = acc["mean_gain_established"] / acc["mean_n_rem"]
    print(acc.to_string(index=False))
    S["accounting"] = acc.to_dict("records")
    acc.to_csv(os.path.join(rb.OUT, "accounting_where_minutes_go.csv"), index=False)

    # concentration, measured honestly: how much of the WITHIN-team-game spread in the realised
    # gain is explained by anything pre-game?
    rb.hdr("4. CONCENTRATION, MEASURED AS PREDICTABLE CONCENTRATION")
    rows = []
    for ch in rb.CHANNELS:
        sub = rem[rem["u_" + ch].to_numpy() > 0].copy()
        gm = sub.groupby("tg")
        d = sub["d_" + ch] - gm["d_" + ch].transform("mean")
        for pname, pv in [("uniform (constant within team-game)", np.zeros(len(sub))),
                          ("base5 level", sub["base5_" + ch].to_numpy()),
                          ("within-team-game z of base5", sub["z_" + ch].to_numpy()),
                          ("u * z", sub["uz_" + ch].to_numpy()),
                          ("position match with the absentee",
                           sub["posmatch"].fillna(0.0).to_numpy())]:
            pw = pv - sub.groupby("tg")[sub.columns[0]].transform(lambda s: 0.0).to_numpy() \
                if False else pv - pd.Series(pv, index=sub.index).groupby(sub["tg"]).transform("mean").to_numpy()
            c = (0.0 if np.std(pw) == 0 else float(np.corrcoef(d, pw)[0, 1]))
            rows.append(dict(channel=ch, predictor=pname, n=int(len(sub)),
                             within_teamgame_corr=c, within_R2=c * c))
        # the ex-post spread, for contrast
        rows.append(dict(channel=ch, predictor="[EX-POST spread of the realised gain, sd]",
                         n=int(len(sub)), within_teamgame_corr=float(d.std()), within_R2=np.nan))
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    S["concentration"] = t.to_dict("records")
    t.to_csv(os.path.join(rb.OUT, "concentration_predictable.csv"), index=False)

    with open(os.path.join(rb.OUT, "_s08.json"), "w", encoding="utf-8") as fh:
        json.dump(rb.jsonable(S), fh, indent=1)
    print("\n  wrote _s08.json and four CSVs")


if __name__ == "__main__":
    main()
