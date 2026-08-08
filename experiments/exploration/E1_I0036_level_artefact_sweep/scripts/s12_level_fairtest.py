"""S12 -- THE FAIR TEAM-LEVEL TEST + FAMILY-WISE CORRECTION.

s11 used a 3-column team reference against player screens that used a 10-column B_COMPLETE.
That is D087 reference incompleteness working in the CANDIDATE's favour: a thin reference
leaves room that the candidate then appears to fill.  A survival measured that way is not
evidence.

So every s11 cell is re-measured against two stronger, level-matched, strictly-prior bases:

  B_TEAM_COMPLETE   the team's own expanding / EWMA / trailing-5 history of the response,
                    plus its own prior pace and prior shot volume, plus cold-start and venue
  B_TEAM_PLUS_OPP   the above PLUS the closest prior OPPONENT measurement of the same target
                    (the team-level analogue of D097's B_COMPLETE_PLUS_R10)

and the family-wise multiplicity over the 4 preregistered cells is applied by max-statistic.

D101 remains in force: no number here is compared to a player-level number.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import (BaseFit, EXP, FLOOR_1CELL, OUT, R_DRAWS, SEED, assert_partition, hdr,
                 injection_power, mde80, null_draws, perm_p, resolve, var_share_between)

HEADLINE_SEASONS = (2022, 2023, 2024)
key = ["season", "game_id", "team_id"]

# ============================================================ build
hdr("1. TEAM-GAME FRAME WITH PACE, VOLUME AND OPPONENT-ALLOWED HISTORY")
P = pd.read_parquet(os.path.join(EXP, "E0_I0029_freethrow_hurdle", "screen_frame.parquet"))
P["game_date"] = pd.to_datetime(P["game_date"])
assert_partition(P, "E0_I0029 screen_frame")
P = P[P["season"].isin(HEADLINE_SEASONS)].reset_index(drop=True)

MCOLS = resolve(P, ["M01_opp_pf_pg", "M04_opp_allowed_ft_rate", "M06_opp_pace",
                    "M02_opp_allowed_fta_pg", "M03_opp_allowed_ftm_pg"], 5, "OPP COLUMNS")
SUMC = resolve(P, ["fta", "ftm", "pts", "oreb", "fga", "pf"], 6, "SUMMABLE")
a = {c: "sum" for c in SUMC}
a.update({c: "first" for c in MCOLS})
a.update({"opp_team_id": "first", "is_home": "first", "game_date": "first",
          "pace": "first", "minutes": "sum", "player_id": "size"})
T = P.groupby(key, as_index=False).agg(a).rename(columns={"player_id": "n_players",
                                                          "pace": "T_pace"})
T = T.rename(columns={c: "T_" + c for c in SUMC})
print(f"  team-games {T.shape}")

# opponent's SCORED points in this same game -> the team's ALLOWED points (for prior history)
oth = T[["season", "game_id", "team_id", "T_pts", "T_fta", "T_ftm"]].rename(
    columns={"team_id": "opp_team_id", "T_pts": "a_pts", "T_fta": "a_fta", "T_ftm": "a_ftm"})
T = T.merge(oth, on=["season", "game_id", "opp_team_id"], how="left")
print(f"  allowed-quantity join coverage: a_pts {T['a_pts'].notna().mean():.4f}")
assert float(T["a_pts"].notna().mean()) == 1.0, "A_TEAM_JOIN FAILED on the opponent row"

T = T.sort_values(["season", "team_id", "game_date", "game_id"],
                  kind="stable").reset_index(drop=True)
TK = ["season", "team_id"]


def prior_mean(df, k, v):
    return df.groupby(k, sort=False)[v].transform(lambda s: s.shift(1).expanding().mean())


def prior_ewma(df, k, v, hl=5.0):
    return df.groupby(k, sort=False)[v].transform(
        lambda s: s.shift(1).ewm(halflife=hl, adjust=True).mean())


def prior_trail(df, k, v, w=5):
    return df.groupby(k, sort=False)[v].transform(
        lambda s: s.shift(1).rolling(w, min_periods=1).mean())


for q in ["T_fta", "T_ftm", "T_pts", "T_oreb"]:
    T["REFm_" + q] = prior_mean(T, TK, q)
    T["REFe_" + q] = prior_ewma(T, TK, q)
    T["REFt_" + q] = prior_trail(T, TK, q)
T["REF_pace"] = prior_mean(T, TK, "T_pace")
T["REF_fga"] = prior_mean(T, TK, "T_fga")
T["team_n_prior"] = T.groupby(TK, sort=False)["T_pts"].transform(
    lambda s: s.shift(1).expanding().count())

# opponent's prior ALLOWED points per game, attached by opponent identity
OT = T.sort_values(["season", "team_id", "game_date", "game_id"],
                   kind="stable").reset_index(drop=True)
OT["OPP_allowed_pts_pg"] = prior_mean(OT, TK, "a_pts")
T = T.merge(OT[key + ["OPP_allowed_pts_pg"]].rename(
    columns={"team_id": "opp_team_id", "OPP_allowed_pts_pg": "M07_opp_allowed_pts_pg"}),
    on=["season", "game_id", "opp_team_id"], how="left")
print(f"  M07_opp_allowed_pts_pg coverage {T['M07_opp_allowed_pts_pg'].notna().mean():.4f}")

# A_NO_RETRO_2 on the new references
hdr("2. A_NO_RETRO_2 -- rebuild after deleting the last 20% of each season")
cut = T.groupby("season")["game_date"].transform(lambda s: s.quantile(0.80))
Tt = T[T["game_date"] <= cut].sort_values(["season", "team_id", "game_date", "game_id"],
                                          kind="stable").reset_index(drop=True)
bad = 0
for q in ["T_fta", "T_ftm", "T_pts", "T_oreb"]:
    Tt["X"] = prior_mean(Tt, TK, q)
    Tt["Y"] = prior_ewma(Tt, TK, q)
    Tt["Z"] = prior_trail(Tt, TK, q)
    c = T.merge(Tt[key + ["X", "Y", "Z"]], on=key, how="inner")
    for src, dst in [("REFm_" + q, "X"), ("REFe_" + q, "Y"), ("REFt_" + q, "Z")]:
        A, B = c[src].to_numpy(), c[dst].to_numpy()
        b = int((~(np.isclose(A, B, rtol=0, atol=1e-10) | (np.isnan(A) & np.isnan(B)))).sum())
        bad += b
        print(f"  {src:14s} mismatches={b} / {len(c)}")
assert bad == 0, "A_NO_RETRO_2 FAILED"
print("  A_NO_RETRO_2 ok")

# ============================================================ cells
hdr("3. THE FOUR CELLS UNDER TWO LEVEL-MATCHED BASES")
CELLS = [
    dict(cell="L1", cand="M06_opp_pace", resp="T_fta", oppref="M02_opp_allowed_fta_pg"),
    dict(cell="L2", cand="M06_opp_pace", resp="T_ftm", oppref="M03_opp_allowed_ftm_pg"),
    dict(cell="L3", cand="M04_opp_allowed_ft_rate", resp="T_pts",
         oppref="M07_opp_allowed_pts_pg"),
    dict(cell="L4", cand="M01_opp_pf_pg", resp="T_pts", oppref="M07_opp_allowed_pts_pg"),
]

rows, drawstore = [], {}
for spec in CELLS:
    for basename in ["B_TEAM_COMPLETE", "B_TEAM_PLUS_OPP"]:
        q = spec["resp"]
        cols = ["REFm_" + q, "REFe_" + q, "REFt_" + q, "REF_pace", "REF_fga",
                "team_n_prior", "is_home"]
        nexp = 7
        if basename == "B_TEAM_PLUS_OPP":
            cols = cols + [spec["oppref"]]
            nexp = 8
        hdr(f"CELL {spec['cell']} / {basename}:  {spec['cand']} -> {q}")
        BASE = resolve(T, cols, nexp, f"{basename}({q})")
        d = T.dropna(subset=[q, spec["cand"]] + BASE).reset_index(drop=True)
        for c in BASE:
            assert int(d[c].notna().sum()) == len(d), f"A_REF_COVERAGE FAILED {c}"
        print(f"  n = {len(d)}  A_REF_COVERAGE ok on {len(BASE)} columns")

        y = d[q].to_numpy(float)
        X = d[BASE].to_numpy(float)
        x = d[spec["cand"]].to_numpy(float)
        bf = BaseFit(y, X)
        obs = bf.dr2(x)
        ex = bf.resid_x(x)
        ceil = (bf.beta(x) * float(np.std(ex, ddof=1)) / float(np.std(y, ddof=1))) ** 2
        print(f"  r2_base={bf.r2_base:.6f}  dR2={obs:.6e}  CEILING={ceil:.6e} "
              f"({ceil / FLOOR_1CELL:.2f}x single-cell floor)")

        ent = pd.Series(d["opp_team_id"].astype(str) + "_"
                        + d["season"].astype(str)).to_numpy()
        rr = np.random.default_rng(SEED + abs(hash(spec["cell"] + basename)) % 100000)
        Xp = null_draws("N_SWAP", x, rr, groups=ent, order_key=d["game_date"].to_numpy(),
                        blocks=d["season"].to_numpy(), R=R_DRAWS)
        EX = bf.resid_X(Xp)
        den = np.einsum("ij,ij->j", EX, EX)
        draws = ((bf.e @ EX) ** 2 / den) / bf.sst
        p = perm_p(obs, draws)
        z = (obs - draws.mean()) / draws.std(ddof=1)
        zn = (draws - draws.mean()) / draws.std(ddof=1)
        drawstore[(spec["cell"], basename)] = (z, zn)

        pw = injection_power(bf, x, EX, np.random.default_rng(SEED + 23),
                             deltas=[0.0, 0.002057, 0.004, 0.006, 0.010, 0.020], nrep=60)
        m80 = mde80(pw)
        t1 = float(pw.loc[pw["delta"] == 0.0, "power"].iloc[0])
        pbest = float(pw.loc[pw["delta"] == 0.002057, "power"].iloc[0])
        pbig = float(pw.loc[pw["delta"] == 0.020, "power"].iloc[0])
        # a null with power at LARGE deltas is UNDERPOWERED, not degenerate
        status = ("DEGENERATE" if pbig < 0.80 else
                  "ANTICONSERVATIVE" if t1 > 0.10 else
                  "USABLE_BUT_UNDERPOWERED_AT_0.002057" if pbest < 0.80 else "USABLE")
        print(f"  N_ESWAP p={p:.6f}  null_mean={draws.mean():.4e} "
              f"null_sd={draws.std(ddof=1):.4e}  z={z:.3f}")
        print(f"  MDE80={m80:.4e}  power@0.002057={pbest:.2f}  power@0.020={pbig:.2f} "
              f"typeI={t1:.2f}  STATUS={status}")
        print(f"  observed dR2 {'ABOVE' if obs > m80 else 'BELOW'} this cell's MDE80")
        rows.append(dict(cell=spec["cell"], base=basename, candidate=spec["cand"],
                         response=q, level="team_game", n=len(d), r2_base=bf.r2_base,
                         dr2=obs, ceiling=ceil, null="N_ESWAP", p_percell=p,
                         null_mean=float(draws.mean()), null_sd=float(draws.std(ddof=1)),
                         z=float(z), R=R_DRAWS, mde80=m80, typeI=t1,
                         power_at_0p002057=pbest, power_at_0p020=pbig, null_status=status,
                         above_own_mde=bool(obs > m80),
                         var_share_between_opp=var_share_between(x, ent)))
        np.savez_compressed(
            os.path.join(OUT, "nulls", f"fair_{spec['cell']}_{basename}.npz"),
            draws=draws, observed=np.array([obs]), z_null=zn, z_obs=np.array([z]))

R = pd.DataFrame(rows)

# ============================================================ family-wise
hdr("4. FAMILY-WISE CORRECTION OVER THE 4 PREREGISTERED CELLS (max-z)")
for basename in ["B_TEAM_COMPLETE", "B_TEAM_PLUS_OPP"]:
    zs = {c["cell"]: drawstore[(c["cell"], basename)] for c in CELLS}
    maxnull = np.max(np.vstack([zn for (_, zn) in zs.values()]), axis=0)
    print(f"\n  {basename}: K = {len(zs)} cells, max-z null over {R_DRAWS} draws")
    for cell, (zo, _) in zs.items():
        pfw = (1.0 + float((maxnull >= zo).sum())) / (1.0 + len(maxnull))
        R.loc[(R["cell"] == cell) & (R["base"] == basename), "p_familywise_maxz"] = pfw
        print(f"    {cell}: z_obs={zo:7.3f}   p_familywise = {pfw:.6f}   "
              f"{'SURVIVES' if pfw < 0.05 else 'killed'}")

hdr("5. FAIR-TEST RESULT TABLE")
print(R[["cell", "base", "candidate", "response", "n", "r2_base", "dr2", "mde80",
         "p_percell", "p_familywise_maxz", "null_status", "above_own_mde"]].to_string(
    index=False))
R.to_csv(os.path.join(OUT, "LEVEL_FAIRTEST_CELLS.csv"), index=False)
T.to_parquet(os.path.join(OUT, "_team_game_frame_v2.parquet"), index=False)
print("\nwrote LEVEL_FAIRTEST_CELLS.csv, _team_game_frame_v2.parquet")
