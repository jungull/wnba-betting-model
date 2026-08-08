"""S05 -- BUILD THE CELL FRAME EXACTLY AS PREREG.md SECTION 3 DEFINES IT.

The preregistration hash is re-asserted first.  Nothing is measured here; this file only
materialises ESTABLISHED / ABSENT / REM, FREED, u, z, and the champion columns, and asserts the
coverage counts that D087 requires.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redist_base as rb
import s04_prereg
import screenkit as sk

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)

MINPRIOR = 3
CHAMP_COL = {"minutes": "min_hat", "fga": "fga_hat", "pts": "pts_hat"}
CHAMP_N = 3


def main():
    rb.hdr("S05 CELL FRAME")
    pre = s04_prereg.assert_unchanged()
    print("  prereg hash verified: %s" % pre["prereg_sha256"])
    F = {"prereg_sha256": pre["prereg_sha256"]}

    assert len(CHAMP_COL) == CHAMP_N, "champion column map length"
    print("  ALLOWLIST CHAMP_COL resolved %d/%d: %s" % (len(CHAMP_COL), CHAMP_N, CHAMP_COL))

    tg = pd.read_parquet(os.path.join(rb.OUT, "_team_frame.parquet"))
    pf = pd.read_parquet(os.path.join(rb.OUT, "_player_frame.parquet"))

    # RS_ALL: every REGULAR-SEASON team-game in the partition with champion rows present.
    # 2021 and 2022 exist here ONLY as training data for walk-forward coefficients.
    rsall = tg[(tg["season_type"] == "Regular Season") & (tg["n_champion_rows"] > 0)
               & tg["has_team_arm"]][["game_id", "team_id", "season", "game_date"]].copy()
    print("  RS_ALL team-games (2021-2024): %d" % len(rsall))
    print(rsall.groupby("season").size().to_string())
    F["RS_ALL_by_season"] = {str(k): int(v) for k, v in rsall.groupby("season").size().items()}

    p = pf.merge(rsall[["game_id", "team_id"]], on=["game_id", "team_id"], how="inner")
    for c in ["min_hat", "fga_hat", "pts_hat"]:
        assert c in p.columns, c

    # ---------------- ESTABLISHED / ABSENT / REM
    p["established"] = ((p["nprior_minutes"] >= MINPRIOR)
                        & p["base5_minutes"].notna()).astype(int)
    e = p[p["established"] == 1].copy()
    e["is_absent"] = (e["appeared"] == 0).astype(int)
    e["is_rem"] = (e["appeared"] == 1).astype(int)
    assert ((e["is_absent"] + e["is_rem"]) == 1).all(), "ABSENT and REM do not partition ESTABLISHED"
    print("  ESTABLISHED rows %d; ABSENT %d; REM %d  (partition asserted)"
          % (len(e), int(e["is_absent"].sum()), int(e["is_rem"].sum())))

    for ch in rb.CHANNELS:
        e["_f_" + ch] = np.where(e["is_absent"] == 1, e["base5_" + ch], 0.0)
    G = e.groupby(["game_id", "team_id"]).agg(
        n_absent=("is_absent", "sum"), n_elig=("is_absent", "size"), n_rem=("is_rem", "sum"),
        **{("freed_" + ch): ("_f_" + ch, "sum") for ch in rb.CHANNELS}).reset_index()
    # z is computed over ESTABLISHED (absence-blind), per PREREG section 3
    for ch in rb.CHANNELS:
        gm = e.groupby(["game_id", "team_id"])["base5_" + ch]
        e["z_" + ch] = ((e["base5_" + ch] - gm.transform("mean"))
                        / gm.transform("std").replace(0.0, np.nan)).fillna(0.0)

    # ---------------- unestablished volume (P01's response)
    un = p[(p["established"] == 0) & (p["appeared"] == 1)].groupby(["game_id", "team_id"]).agg(
        **{("unest_" + ch): (ch, "sum") for ch in rb.CHANNELS}).reset_index()
    G = G.merge(un, on=["game_id", "team_id"], how="left")
    for ch in rb.CHANNELS:
        G["unest_" + ch] = G["unest_" + ch].fillna(0.0)
    G = G.merge(rsall, on=["game_id", "team_id"], how="left")
    assert G["season"].notna().all()

    # ---------------- REM frame
    R = e[e["is_rem"] == 1].merge(
        G[["game_id", "team_id", "season", "n_absent", "n_elig", "n_rem"]
          + ["freed_" + c for c in rb.CHANNELS]],
        on=["game_id", "team_id"], how="left", suffixes=("", "_g"))
    assert R["n_rem"].notna().all()
    for ch in rb.CHANNELS:
        R["u_" + ch] = R["freed_" + ch] / R["n_rem"]
        R["uz_" + ch] = R["u_" + ch] * R["z_" + ch]
        R["d_" + ch] = R[ch] - R["base5_" + ch]
    R["tg"] = R["game_id"].astype(str) + "_" + R["team_id"].astype(str)

    # ---------------- position group for P05
    def posgroup(s):
        return (s.split("-")[0] if isinstance(s, str) and s else None)
    e["pg"] = e["position_raw"].map(posgroup)
    R["pg"] = R["position_raw"].map(posgroup)
    big = (e[e["is_absent"] == 1].sort_values("base5_minutes", ascending=False)
           .groupby(["game_id", "team_id"]).head(1)[["game_id", "team_id", "pg"]]
           .rename(columns={"pg": "pg_absentee"}))
    R = R.merge(big, on=["game_id", "team_id"], how="left")
    R["posmatch"] = ((R["pg"].notna()) & (R["pg_absentee"].notna())
                     & (R["pg"] == R["pg_absentee"])).astype(float)
    R.loc[R["pg"].isna() | R["pg_absentee"].isna(), "posmatch"] = np.nan

    # ---------------- coverage assertions (D087)
    rb.hdr("COVERAGE ASSERTIONS ON THE CELL ROW SET (D087)")
    for w, lab in [((2023, 2024), "RSP-W2 (PRIMARY)"), ((2022, 2023, 2024), "RSP-W1 (secondary)")]:
        S = R[R["season"].isin(w)]
        print("  %-22s rows %5d  team-games %4d  seasons %s"
              % (lab, len(S), S["tg"].nunique(), sorted(S["season"].unique())))
        cov = {}
        for c in (["base5_" + x for x in rb.CHANNELS] + ["min_hat", "fga_hat", "pts_hat"]
                  + [x for x in rb.CHANNELS] + ["z_minutes", "u_minutes"]):
            cov[c] = float(S[c].notna().mean())
            assert cov[c] == 1.0, "INCOMPLETE COVERAGE on %s: %.6f" % (c, cov[c])
        pm_cov = float(S["posmatch"].notna().mean())
        absg = S[S["freed_minutes"] > 0]
        pm_cov_abs = float(absg["posmatch"].notna().mean())
        print("     every analysis column has coverage 1.000000 (asserted)")
        print("     posmatch defined on %.4f of all rows, %.4f of FREED>0 rows"
              % (pm_cov, pm_cov_abs))
        F["coverage_" + lab.split()[0]] = {
            "n_rows": int(len(S)), "n_teamgames": int(S["tg"].nunique()),
            "analysis_columns_coverage": cov, "posmatch_coverage_all": pm_cov,
            "posmatch_coverage_absence_rows": pm_cov_abs,
            "n_absence_rows": int(len(absg)),
            "n_absence_teamgames": int(absg["tg"].nunique())}

    rb.hdr("PARTITION ASSERT AND WRITE")
    F["partition_R"] = {k: v for k, v in sk.assert_partition(
        R[["season"]], verbose=True).items() if k != "draws"}
    F["partition_G"] = {k: v for k, v in sk.assert_partition(
        G[["season"]], verbose=True).items() if k != "draws"}
    R.to_parquet(os.path.join(rb.OUT, "_rem_frame.parquet"), index=False)
    G.to_parquet(os.path.join(rb.OUT, "_tg_frame.parquet"), index=False)
    with open(os.path.join(rb.OUT, "_s05.json"), "w", encoding="utf-8") as fh:
        json.dump(rb.jsonable(F), fh, indent=1)
    print("  wrote _rem_frame %s and _tg_frame %s" % (R.shape, G.shape))


if __name__ == "__main__":
    main()
