"""S11 -- THE LEVEL RE-RUNS.  The top-4 triage pairs, re-measured at TEAM-GAME level.

PREREG 4.4 selected (candidate, target) pairs by the frozen EV formula.  Each was killed at
PLAYER level.  Each is an OPPONENT-team-season quantity: the same number for all ~9.4
teammates in a team-game.  That is the exact and only configuration in which a player-level
response dilutes a real effect, so it is the exact configuration the level-artefact hypothesis
predicts should come back to life at team level.

D101 IS IN FORCE: nothing here is compared to a player-level number.  Each level carries its
own response, row set, SST, reference and null.  The only claim made is a SURVIVAL claim.

Also runs the R08 "level-up" control demanded by PREREG 6.6.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import (BaseFit, EXP, FLOOR_1CELL, FLOOR_132, OUT, R_DRAWS, SEED, assert_partition,
                 hdr, injection_power, mde80, null_draws, perm_p, resolve, var_share_between)

HEADLINE_SEASONS = (2022, 2023, 2024)

# ===================================================================== build team-game frame
hdr("1. BUILD THE TEAM-GAME FRAME (aggregated from D108's own player frame)")
P = pd.read_parquet(os.path.join(EXP, "E0_I0029_freethrow_hurdle", "screen_frame.parquet"))
P["game_date"] = pd.to_datetime(P["game_date"])
assert_partition(P, "E0_I0029 screen_frame")
P = P[P["season"].isin(HEADLINE_SEASONS)].reset_index(drop=True)
print(f"  player rows {P.shape}")

MCOLS = resolve(P, ["M01_opp_pf_pg", "M04_opp_allowed_ft_rate", "M06_opp_pace"], 3,
                "OPPONENT CANDIDATES")
SUMCOLS = resolve(P, ["fta", "ftm", "pts", "oreb", "reb"], 5, "SUMMABLE RESPONSES")

# A_CONSTANT: every M column must be constant within a team-game (it is an opponent quantity)
key = ["season", "game_id", "team_id"]
for c in MCOLS:
    nun = P.groupby(key, sort=False)[c].nunique(dropna=False)
    assert int((nun > 1).sum()) == 0, f"A_CONSTANT FAILED: {c} varies within a team-game"
print(f"  A_CONSTANT ok: all {len(MCOLS)} opponent candidates are team-game constants")

agg = {c: "sum" for c in SUMCOLS}
agg.update({c: "first" for c in MCOLS})
agg.update({"opp_team_id": "first", "is_home": "first", "game_date": "first",
            "minutes": "sum", "player_id": "size"})
T = P.groupby(key, as_index=False).agg(agg).rename(columns={"player_id": "n_players"})
T = T.rename(columns={c: "T_" + c for c in SUMCOLS})
print(f"  team-games {T.shape}")

# A_ROSTER_COMPLETE (PREREG 3.2)
ot = np.round((T["minutes"] - 200.0) / 25.0)
resid = T["minutes"] - (200.0 + 25.0 * ot.clip(lower=0))
ok = int((np.abs(resid) < 1.0).sum())
print(f"  A_ROSTER_COMPLETE: {ok}/{len(T)} team-games have minutes == 200 + 25*OT (+-1.0)")
assert ok == len(T), "A_ROSTER_COMPLETE FAILED"

# A_TEAM_JOIN + A_SUM_IDENTITY against the independent team box (PREREG 3.2)
TB = pd.read_parquet(os.path.join(EXP, "E1_I0033_aggregation_level", "_team_frame.parquet"))
TB["game_id"] = TB["game_id"].astype(str)
T["game_id"] = T["game_id"].astype(str)
TB = TB[TB["season"].isin(HEADLINE_SEASONS)]
m = T.merge(TB[["season", "game_id", "team_id", "fta", "ftm", "pts", "oreb", "reb"]],
            on=key, how="inner", suffixes=("", "_box"))
print(f"  A_TEAM_JOIN: aggregate keys {len(T)}  box keys {len(TB)}  matched {len(m)}")
assert len(m) == len(T) == len(TB), "A_TEAM_JOIN FAILED -- key sets differ"
for c in ["fta", "ftm", "pts", "oreb", "reb"]:
    rate = float((np.abs(m["T_" + c] - m[c]) < 1e-9).mean())
    print(f"  A_SUM_IDENTITY {c:5s}: exact match on {rate:.4%} of team-games")
    assert rate > 0.99, f"A_SUM_IDENTITY FAILED for {c}"

# ===================================================================== team reference
hdr("2. TEAM-LEVEL REFERENCE -- STRICTLY PRIOR, BUILT HERE, NO RETROSPECTIVE BASELINE")
T = T.sort_values(["season", "team_id", "game_date", "game_id"],
                  kind="stable").reset_index(drop=True)


def prior_mean(df, keycols, val):
    return df.groupby(keycols, sort=False)[val].transform(
        lambda s: s.shift(1).expanding().mean())


def prior_count(df, keycols, val):
    return df.groupby(keycols, sort=False)[val].transform(
        lambda s: s.shift(1).expanding().count())


TK = ["season", "team_id"]
for q in ["T_fta", "T_ftm", "T_pts", "T_oreb"]:
    T["REF_" + q] = prior_mean(T, TK, q)
T["team_n_prior"] = prior_count(T, TK, "T_pts")

# A_NO_RETRO_2 -- empirical: rebuild on a truncated frame; prior refs must be bit-identical
hdr("3. A_NO_RETRO_2 -- delete the last 20% of each season and rebuild")
cut = T.groupby("season")["game_date"].transform(lambda s: s.quantile(0.80))
Ttr = T[T["game_date"] <= cut].copy().sort_values(
    ["season", "team_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
for q in ["T_fta", "T_ftm", "T_pts", "T_oreb"]:
    Ttr["REF2_" + q] = prior_mean(Ttr, TK, q)
chk = T.merge(Ttr[key + ["REF2_" + q for q in ["T_fta", "T_ftm", "T_pts", "T_oreb"]]],
              on=key, how="inner")
bad_total = 0
for q in ["T_fta", "T_ftm", "T_pts", "T_oreb"]:
    a, b = chk["REF_" + q].to_numpy(), chk["REF2_" + q].to_numpy()
    bad = int((~(np.isclose(a, b, rtol=0, atol=1e-12) | (np.isnan(a) & np.isnan(b)))).sum())
    bad_total += bad
    print(f"  REF_{q:7s}: {bad} mismatches over {len(chk)} surviving rows")
assert bad_total == 0, "A_NO_RETRO_2 FAILED -- a reference changed when the future was deleted"
print("  A_NO_RETRO_2 ok: every team reference is strictly prior")

# ===================================================================== cells
hdr("4. THE FOUR PREREGISTERED LEVEL RE-RUNS (top of TRIAGE_RANKING.csv)")
CELLS = [
    dict(cell="L1", cand="M06_opp_pace", resp="T_fta"),
    dict(cell="L2", cand="M06_opp_pace", resp="T_ftm"),
    dict(cell="L3", cand="M04_opp_allowed_ft_rate", resp="T_pts"),
    dict(cell="L4", cand="M01_opp_pf_pg", resp="T_pts"),
]
BASE_OF = {"T_fta": ["REF_T_fta", "is_home", "team_n_prior"],
           "T_ftm": ["REF_T_ftm", "is_home", "team_n_prior"],
           "T_pts": ["REF_T_pts", "is_home", "team_n_prior"],
           "T_oreb": ["REF_T_oreb", "is_home", "team_n_prior"]}

rows, injrows = [], []
for spec in CELLS + [dict(cell="C1_LEVELUP", cand="ROSTER_RA_SHARE", resp="T_oreb")]:
    hdr(f"CELL {spec['cell']}:  {spec['cand']}  ->  {spec['resp']}   (TEAM-GAME LEVEL)")
    W = T.copy()
    if spec["cand"] == "ROSTER_RA_SHARE":
        # PREREG 6.6 control: level R08 UP to the team by taking the roster's attempt-weighted
        # prior restricted-area share.  Built from D097's frame on the same team-games.
        F97 = pd.read_parquet(os.path.join(
            EXP, "E0_I0024_reb_ast_characterisation", "screen_frame.parquet"))
        F97 = F97[F97["season"].isin(HEADLINE_SEASONS)]
        F97["game_id"] = F97["game_id"].astype(str)
        rs = F97.dropna(subset=["R08_player_ra_share"]).groupby(key, as_index=False).agg(
            ROSTER_RA_SHARE=("R08_player_ra_share", "mean"),
            n_with_r08=("R08_player_ra_share", "size"))
        W = W.merge(rs, on=key, how="left")
        print(f"  roster RA-share coverage: {int(W['ROSTER_RA_SHARE'].notna().sum())}/{len(W)}"
              f" team-games")

    BASE = resolve(W, BASE_OF[spec["resp"]], 3, f"TEAM BASE({spec['resp']})")
    d = W.dropna(subset=[spec["resp"], spec["cand"]] + BASE).reset_index(drop=True)
    for c in BASE:
        assert int(d[c].notna().sum()) == len(d), f"A_REF_COVERAGE FAILED {c}"
    print(f"  n = {len(d)} team-games   A_REF_COVERAGE ok on {len(BASE)} base columns")

    y = d[spec["resp"]].to_numpy(float)
    X = d[BASE].to_numpy(float)
    x = d[spec["cand"]].to_numpy(float)
    bf = BaseFit(y, X)
    obs = bf.dr2(x)

    # PREREG 5.5 -- CEILING BEFORE FITTING
    ex = bf.resid_x(x)
    ceil = (bf.beta(x) * float(np.std(ex, ddof=1)) / float(np.std(y, ddof=1))) ** 2
    print(f"  r2_base = {bf.r2_base:.6f}   observed dR2 = {obs:.6e}")
    print(f"  CEILING = {ceil:.6e}   ({ceil / FLOOR_1CELL:.2f}x single-cell floor)")
    if ceil < FLOOR_1CELL:
        print("  >>> CEILING BELOW FLOOR -- recorded, NOT FIT further.")

    ent = pd.Series(d["opp_team_id"].astype(str) + "_" + d["season"].astype(str)).to_numpy()
    if spec["cand"] == "ROSTER_RA_SHARE":
        ent = pd.Series(d["team_id"].astype(str) + "_" + d["season"].astype(str)).to_numpy()
    seas = d["season"].to_numpy()
    gdate = d["game_date"].to_numpy()
    vsb = var_share_between(x, ent)
    xb = pd.Series(x).groupby(pd.Series(ent)).transform("mean").to_numpy()
    xw = x - xb
    print(f"  var share BETWEEN entity-seasons = {vsb:.4f}")
    print(f"  dR2 between-only = {bf.dr2(xb):.6e}   within-only = {bf.dr2(xw):.6e}")

    NULLS = {"N_ROW": ("N_ROW", None, None), "N_ESWAP": ("N_SWAP", ent, seas)}
    for name, (kind, grp, blk) in NULLS.items():
        rr = np.random.default_rng(SEED + abs(hash(name + spec["cell"])) % 100000)
        Xp = null_draws(kind, x, rr, groups=grp, order_key=gdate, blocks=blk, R=R_DRAWS)
        EX = bf.resid_X(Xp)
        den = np.einsum("ij,ij->j", EX, EX)
        draws = ((bf.e @ EX) ** 2 / den) / bf.sst
        p = perm_p(obs, draws)
        pw = injection_power(bf, x, EX, np.random.default_rng(SEED + 13),
                             deltas=[0.0, 0.000500, 0.001127, 0.002057, 0.005, 0.010],
                             nrep=60)
        pwb = injection_power(bf, xb, EX, np.random.default_rng(SEED + 17),
                              deltas=[0.0, 0.002057, 0.010], nrep=60)
        m80 = mde80(pw)
        t1 = float(pw.loc[pw["delta"] == 0.0, "power"].iloc[0])
        pb = float(pwb.loc[pwb["delta"] == 0.002057, "power"].iloc[0])
        pbig = float(pw.loc[pw["delta"] == 0.002057, "power"].iloc[0])
        status = ("DEGENERATE" if pbig < 0.80 else
                  "ANTICONSERVATIVE" if t1 > 0.10 else "USABLE")
        print(f"\n  {name:8s} p={p:.6f}  null_mean={draws.mean():.4e} "
              f"null_sd={draws.std(ddof=1):.4e}")
        print(f"    MDE80={m80:.4e}  power@0.002057(FULL)={pbig:.2f} "
              f"(BETWEEN)={pb:.2f}  typeI={t1:.2f}  STATUS={status}")
        for _, r in pw.iterrows():
            injrows.append(dict(cell=spec["cell"], null=name, planted_along="FULL",
                                delta=r["delta"], power=r["power"], nrep=r["nrep"]))
        for _, r in pwb.iterrows():
            injrows.append(dict(cell=spec["cell"], null=name, planted_along="BETWEEN",
                                delta=r["delta"], power=r["power"], nrep=r["nrep"]))
        rows.append(dict(cell=spec["cell"], level="team_game", candidate=spec["cand"],
                         response=spec["resp"], n=len(d), r2_base=bf.r2_base, dr2=obs,
                         ceiling=ceil, ceiling_over_1cell_floor=ceil / FLOOR_1CELL,
                         null=name, p=p, null_mean=float(draws.mean()),
                         null_sd=float(draws.std(ddof=1)), R=R_DRAWS, mde80=m80,
                         power_full_at_best=pbig, power_between_at_best=pb, typeI=t1,
                         null_status=status,
                         UNINFORMATIVE=bool(m80 > max(ceil, 0.002057)),
                         var_share_between_entity=vsb))
        np.savez_compressed(os.path.join(OUT, "nulls",
                                         f"level_{spec['cell']}_{name}.npz"),
                            draws=draws, observed=np.array([obs]))

R = pd.DataFrame(rows)
hdr("5. LEVEL RE-RUN RESULTS")
print(R.to_string(index=False))
R.to_csv(os.path.join(OUT, "LEVEL_RERUN_CELLS.csv"), index=False)
pd.DataFrame(injrows).to_csv(os.path.join(OUT, "LEVEL_RERUN_INJECTION.csv"), index=False)
T.to_parquet(os.path.join(OUT, "_team_game_frame.parquet"), index=False)
print("\nwrote LEVEL_RERUN_CELLS.csv, LEVEL_RERUN_INJECTION.csv, _team_game_frame.parquet")
