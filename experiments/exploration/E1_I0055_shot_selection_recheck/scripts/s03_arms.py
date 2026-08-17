"""S03 -- DECISION STRATUM FIRST, then the projected re-measurement, both arms.

Order is fixed by PREREG sec 6: the row-set intersection is reported BEFORE any
effect size.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ss_base import (CLEAN, HERE, OUT, PARTITION, RA, SEED, ZONES,  # noqa
                     assert_partition, hdr)
from ss_arms import (ARMS, OppGameIndex, arm_stats, blind_player_map,  # noqa
                     common_slope, cov_cols, project_slopes)

N_DRAWS = 5000
R = {}
PGKEY = ["player_id", "season", "game_id"]

COMP = pd.read_parquet(os.path.join(HERE, "_complete.parquet"))
DEC = pd.read_parquet(os.path.join(HERE, "_dec.parquet"))
assert_partition(COMP, "_complete")
assert_partition(DEC, "_dec")

# ======================================================== 1. THE ROW-SET LADDER ===
hdr("1. ROW SETS -- REPORTED BEFORE ANY EFFECT SIZE (PREREG sec 6)")
print("  The projection is only defined on player-games carrying all five zones, so")
print("  every arm -- RAW included -- runs on the COMPLETE subset.  The 62 incomplete")
print("  player-games are excluded from BOTH arms so the comparison is like-for-like.\n")

dk = DEC[["season", "player_id", "game_id", "DECISION", "n_prior_min",
          "prior5_minutes", "season_type"]].copy()
dk["player_id"] = dk["player_id"].astype(np.int64)
dk["game_id"] = dk["game_id"].astype(str)
COMP["game_id"] = COMP["game_id"].astype(str)
PG = (COMP[PGKEY + ["OPP_TEAM_ID", "TEAM_ID", "game_date", "fga", "role_prior_fga",
                    "n_prior"]].drop_duplicates(PGKEY).reset_index(drop=True))
PG = PG.merge(dk, on=["season", "player_id", "game_id"], how="left")
n_match = int(PG["DECISION"].notna().sum())
print(f"  complete player-games in the shot frame            : {len(PG)}")
print(f"  matched into master_player (minutes available)     : {n_match} "
      f"({100 * n_match / len(PG):.2f}%)")
print(f"  UNMATCHED (no minutes row -> cannot be stratified) : {len(PG) - n_match}")
PG["DECISION"] = PG["DECISION"].fillna(False).astype(bool)
PG["CLEAN"] = PG["season"].isin(CLEAN)
print(f"\n  {'row set':<28}{'player-games':>14}{'rows':>10}{'opp-games':>12}"
      f"{'seasons':>22}")
ROWSETS = {}
for nm, mask in [("ALL_x_PUBLISHED", np.ones(len(PG), bool)),
                 ("ALL_x_CLEAN", PG["CLEAN"].to_numpy()),
                 ("DECISION_x_PUBLISHED", PG["DECISION"].to_numpy()),
                 ("DECISION_x_CLEAN", (PG["DECISION"] & PG["CLEAN"]).to_numpy())]:
    sub = PG[mask]
    nog = sub[["season", "OPP_TEAM_ID", "game_id"]].drop_duplicates().shape[0]
    ROWSETS[nm] = sub.index.to_numpy()
    print(f"  {nm:<28}{len(sub):>14}{len(sub) * 5:>10}{nog:>12}"
          f"{str(sorted(sub['season'].unique())):>22}")
    R.setdefault("rowsets", {})[nm] = dict(
        player_games=int(len(sub)), rows=int(len(sub) * 5), opponent_games=int(nog),
        seasons=[int(s) for s in sorted(sub["season"].unique())])
print("\n  PRIMARY ROW SET = DECISION_x_CLEAN  (n_prior>=8 AND prior5_minutes>=24,")
print("  seasons 2023-2024 -- the one clean window).")
R["decision_match_rate"] = float(n_match / len(PG))

# ---------------------------------------------------------------- design matrices
W = {}
for col in ("OS", "resid_S1", "S1", "share"):
    W[col] = (COMP.pivot_table(index=PGKEY, columns="zone", values=col)[ZONES]
              .reindex(pd.MultiIndex.from_frame(PG[PGKEY])).to_numpy(float))
assert not np.isnan(W["OS"]).any()

OGI_ALL = OppGameIndex(PG["season"].to_numpy(), PG["OPP_TEAM_ID"].to_numpy(),
                       PG["game_date"].to_numpy(), PG["game_id"].to_numpy())


def build(idx):
    X = W["OS"][idx]
    Yf = W["resid_S1"][idx]
    SH = W["share"][idx]
    S1 = W["S1"][idx]
    Q, Yres = [], np.empty_like(SH)
    for z in range(5):
        B = np.column_stack([np.ones(len(idx)), S1[:, z]])
        q, _ = np.linalg.qr(B)
        Q.append(q)
        Yres[:, z] = SH[:, z] - q @ (q.T @ SH[:, z])
    ogi = OppGameIndex(PG["season"].to_numpy()[idx], PG["OPP_TEAM_ID"].to_numpy()[idx],
                       PG["game_date"].to_numpy()[idx], PG["game_id"].to_numpy()[idx])
    return dict(X=X, Yf=Yf, Yres=Yres, Q=Q, ogi=ogi, pid=PG["player_id"].to_numpy()[idx],
                n=len(idx))


DES = {nm: build(idx) for nm, idx in ROWSETS.items()}

# ==================================================== 2. REAL EFFECT SIZES ========
hdr("2. REAL EFFECT SIZES -- SIGN AND MAGNITUDE, BEFORE AND AFTER PROJECTION")
real = {}
for nm, d in DES.items():
    real[nm] = arm_stats(d["X"], d["Yf"], d["Yres"], d["Q"])
    print(f"\n  --- {nm}   player-games={d['n']}  rows={d['n'] * 5} ---")
    print(f"  {'zone':<24}{'RAW frozen':>12}{'PROJ frozen':>13}{'flip':>6}"
          f"{'RAW unfroz':>12}{'PROJ unfroz':>13}{'flip':>6}")
    for j, z in enumerate(ZONES):
        rf, pf = real[nm]["RAW_FROZEN"][j], real[nm]["PROJ_FROZEN"][j]
        ru, pu = real[nm]["RAW_UNFROZEN"][j], real[nm]["PROJ_UNFROZEN"][j]
        print(f"  {z:<24}{rf:>+12.4f}{pf:>+13.4f}"
              f"{('YES' if np.sign(rf) != np.sign(pf) else 'no'):>6}"
              f"{ru:>+12.4f}{pu:>+13.4f}"
              f"{('YES' if np.sign(ru) != np.sign(pu) else 'no'):>6}")
    print(f"  {'PROJ_COMMON (one slope)':<24}{real[nm]['COMMON_FROZEN'][0]:>+12.4f}"
          f"{'':>13}{'':>6}{real[nm]['COMMON_UNFROZEN'][0]:>+12.4f}")

# =============================================================== 3. NULLS =========
hdr("3. NULLS -- matched to the level the candidate varies at")
print("""  N_TSTRAJ  (PRIMARY, matched): whole opponent-team-season TRAJECTORIES of the
            five-zone allowance are swapped within season.  Row-level variation of
            the candidate survives; the defence<->offence match is broken at the
            level the candidate is shared at (48 opponent-team-seasons).
  N_OPPGAME (KNOWN TOO NARROW, reported for contrast): opponent-game vectors
            permuted within season, which destroys the team-season clustering --
            the parent screen measured this family's naive-null inflation at
            1.80x-3.80x, so this null is reported and used for NO verdict.
  N_BLIND   (deliberately blind): the candidate cyclically shifted WITHIN player.
""")
NULLS = ["N_TSTRAJ", "N_OPPGAME", "N_BLIND"]
draws = {}
for nm, d in DES.items():
    draws[nm] = {}
    # one representative five-zone allowance vector per opponent-game (they are equal
    # across the rows of an opponent-game by construction; the mean is an identity).
    ogi = d["ogi"]
    rep = np.zeros((ogi.M, 5))
    cnt = np.zeros(ogi.M)
    np.add.at(rep, ogi.unit, d["X"])
    np.add.at(cnt, ogi.unit, 1.0)
    rep = rep / cnt[:, None]
    iddev = float(np.abs(rep[ogi.unit] - d["X"]).max())
    assert iddev < 1e-12, f"opponent-game vector is not constant within unit: {iddev}"
    for nl in NULLS:
        rng = np.random.default_rng(SEED + 101 + NULLS.index(nl))
        acc = {a: np.empty((N_DRAWS, 5)) for a in ARMS}
        for i in range(N_DRAWS):
            if nl == "N_TSTRAJ":
                Xp = rep[ogi.draw_tstraj(rng)][ogi.unit]
            elif nl == "N_OPPGAME":
                Xp = rep[ogi.draw_oppgame(rng)][ogi.unit]
            else:
                Xp = d["X"][blind_player_map(d["pid"], rng)]
            st = arm_stats(Xp, d["Yf"], d["Yres"], d["Q"])
            for a in ARMS:
                acc[a][i] = st[a]
        draws[nm][nl] = acc
        print(f"  {nm:<24} {nl:<12} {N_DRAWS} draws done")

# ============================================ 4. p-VALUES AND FAMILY-WISE BAR =====
hdr("4. SIGN AND SIGNIFICANCE, BEFORE AND AFTER PROJECTION")


def pack(nm, nl, arm):
    D = draws[nm][nl][arm]
    mu, sd = D.mean(axis=0), D.std(axis=0, ddof=1)
    obs = real[nm][arm]
    zr = (obs - mu) / sd
    zm = (D - mu) / sd
    maxz = zm.max(axis=1)
    argmax = zm.argmax(axis=1)
    out = []
    for j, z in enumerate(ZONES):
        p_un = float(((D[:, j] >= obs[j]).sum() + 1) / (N_DRAWS + 1))
        p_fw = float(((maxz >= zr[j]).sum() + 1) / (N_DRAWS + 1))
        out.append(dict(zone=z, rowset=nm, null=nl, arm=arm, obs=float(obs[j]),
                        sign="+" if obs[j] > 0 else "-",
                        null_mean=float(mu[j]), null_sd=float(sd[j]), z=float(zr[j]),
                        p_unadjusted_one_sided=p_un, p_familywise_one_sided=p_fw,
                        n_draws=N_DRAWS))
    dom = {ZONES[k]: float((argmax == k).mean()) for k in range(5)}
    return out, dom


cells = []
dominance = {}
for nm in DES:
    for nl in NULLS:
        for arm in ARMS:
            o, dm = pack(nm, nl, arm)
            cells += o
            dominance[f"{nm}|{nl}|{arm}"] = dm
CELLS = pd.DataFrame(cells)
CELLS.to_csv(os.path.join(OUT, "PRIMARY_CELLS.csv"), index=False)

for nm in ["DECISION_x_CLEAN", "ALL_x_PUBLISHED"]:
    for nl in ["N_TSTRAJ"]:
        print(f"\n  === {nm} / {nl} ===")
        print(f"  {'zone':<24}{'arm':<16}{'obs':>11}{'sign':>6}{'z':>8}"
              f"{'p_unadj':>10}{'p_FWE':>10}")
        for arm in ["RAW_FROZEN", "PROJ_FROZEN", "RAW_UNFROZEN", "PROJ_UNFROZEN"]:
            sub = CELLS[(CELLS.rowset == nm) & (CELLS.null == nl) & (CELLS.arm == arm)]
            for _, r in sub.iterrows():
                print(f"  {r['zone']:<24}{arm:<16}{r['obs']:>+11.4f}{r['sign']:>6}"
                      f"{r['z']:>+8.2f}{r['p_unadjusted_one_sided']:>10.4f}"
                      f"{r['p_familywise_one_sided']:>10.4f}")

hdr("5. FAMILY-WISE SINGLE-CELL DOMINANCE (PREREG sec 7.5)")
print(f"  {'cell':<58}{'top zone':<24}{'share of draws':>15}")
for k in [f"{nm}|N_TSTRAJ|{a}" for nm in DES for a in
          ["RAW_FROZEN", "PROJ_FROZEN", "RAW_UNFROZEN", "PROJ_UNFROZEN"]]:
    dm = dominance[k]
    top = max(dm.items(), key=lambda kv: kv[1])
    print(f"  {k:<58}{top[0]:<24}{100 * top[1]:>14.2f}%")
R["familywise_dominance"] = dominance

hdr("6. NULL-CENTRE CHECK (PREREG sec 7.1) -- mean signed t over draws must be ~0")
print(f"  {'rowset':<24}{'null':<12}{'arm':<16}{'mean signed t':>15}{'verdict':>12}")
centre = {}
for nm in DES:
    for nl in NULLS:
        for arm in ["RAW_FROZEN", "PROJ_FROZEN", "RAW_UNFROZEN", "PROJ_UNFROZEN"]:
            D = draws[nm][nl][arm]
            mu, sd = D.mean(axis=0), D.std(axis=0, ddof=1)
            t = ((D - mu) / sd).mean()
            centre[f"{nm}|{nl}|{arm}"] = float(t)
            if nm == "DECISION_x_CLEAN" or nl == "N_BLIND":
                print(f"  {nm:<24}{nl:<12}{arm:<16}{t:>+15.6f}"
                      f"{('CENTRED' if abs(t) < 0.02 else 'DISPLACED'):>12}")
R["null_centre_mean_signed_t"] = centre
print("\n  NOTE: this is the SELF-centre of each null (it is centred by construction).")
print("  The check that separates valid from blind arms is in s04 (injection +")
print("  Type-I on synthetic data), where the centre is NOT free.")

# ================================================================= 7. WRITE =======
hdr("7. WRITE")
np.savez_compressed(
    os.path.join(OUT, "raw", "S03_null_draws_signed_raw.npz"),
    zones=np.array(ZONES, dtype=object), arms=np.array(ARMS, dtype=object),
    rowsets=np.array(list(DES.keys()), dtype=object),
    nulls=np.array(NULLS, dtype=object), seed=SEED, n_draws=N_DRAWS,
    response="share_z (FROZEN: offset share-S1; UNFROZEN: share on [1,S1])",
    sst_basis="unweighted, about the unweighted mean on the scored rows",
    weighting="none", statistic="per-zone OLS slope on OS_z (RAW) / on the projected "
                                "fitted increment (PROJ)",
    **{f"{nm}__{nl}__{a}": draws[nm][nl][a]
       for nm in DES for nl in NULLS for a in ARMS})
for nm in DES:
    R.setdefault("real", {})[nm] = {a: [float(v) for v in real[nm][a]] for a in ARMS}
json.dump(R, open(os.path.join(HERE, "_s03.json"), "w", encoding="utf-8"), indent=2,
          default=float)
np.savez_compressed(os.path.join(HERE, "_designs.npz"),
                    **{f"{nm}__{k}": DES[nm][k] for nm in DES for k in ("X", "Yf", "Yres")},
                    **{f"{nm}__idx": ROWSETS[nm] for nm in DES})
PG.to_parquet(os.path.join(HERE, "_pg.parquet"), index=False)
print("  wrote PRIMARY_CELLS.csv, raw/S03_null_draws_signed_raw.npz, _s03.json, "
      "_designs.npz, _pg.parquet")
print(f"  PARTITION RE-ASSERT: {sorted(PG['season'].unique())}")
print("\nDone.")
