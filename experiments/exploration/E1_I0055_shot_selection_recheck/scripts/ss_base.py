"""E1_I0055 -- shared machinery.  INDEPENDENT transcription; the parent screen's code
is read-only and is never imported.

PARTITION 2021-2024 ONLY.  2025/2026 is a SEALED confirmation holdout: never read,
joined, filtered against, counted, described or plotted.

R2 / SST CONVENTION (D069): plain UNWEIGHTED OLS, R2 = 1 - SSE/SST, SST about the
UNWEIGHTED mean of the response ON THE SCORED ROWS.  No weighting anywhere.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, ".."))
EXP = os.path.abspath(os.path.join(OUT, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
SRC = os.path.join(EXP, "E1_I0004_shot_selection")
RAW = os.path.join(OUT, "raw")

PARTITION = [2021, 2022, 2023, 2024]
FORBIDDEN_YEARS = (2025, 2026)
CLEAN = [2023, 2024]
RA = "Restricted Area"
ZONES = [RA, "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]
NZ = len(ZONES)

# parent screen's PRESELECTED constants, transcribed (build_frames.py docstring)
MIN_FGA_GAME = 5
MIN_PRE_TOTAL = 200
SHRINK_K = 50.0
ALPHA_EFF = 0.03
ALPHA_EXP = 0.30
MIN_PRIOR = 3

SEED = 20260809

pd.set_option("display.width", 230)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def assert_partition(df, name, col="season"):
    ss = sorted(int(x) for x in pd.unique(df[col]))
    assert set(ss) <= set(PARTITION), f"PARTITION VIOLATION in {name}: {ss}"
    for y in FORBIDDEN_YEARS:
        assert y not in ss, f"HOLDOUT LEAK in {name}: {y}"
    return ss


# ----------------------------------------------------------------- frame rebuild ---
def load_shots(verbose=True):
    dfs = []
    for ssn in PARTITION:
        for t in ("regular", "playoffs"):
            f = os.path.join(ROOT, "data", "shotcharts", f"shots_{ssn}_{t}.parquet")
            d = pd.read_parquet(f)
            d["season"] = ssn
            # FILTER-POINT: per-file partition restriction.
            d = d[d["season"].isin(PARTITION)]
            dfs.append(d)
    shots = pd.concat(dfs, ignore_index=True)
    # FILTER-POINT: re-assert on the concatenated frame.
    shots = shots[shots["season"].isin(PARTITION)].copy()
    shots["game_date"] = pd.to_datetime(shots["GAME_DATE"], format="%Y%m%d")
    assert_partition(shots, "shots")
    assert shots["game_date"].dt.year.max() <= 2024, "PARTITION VIOLATION (date)"
    shots["zone"] = shots["SHOT_ZONE_BASIC"].map(
        lambda z: "Corner 3" if z in ("Left Corner 3", "Right Corner 3") else z)
    gt = shots.groupby("GAME_ID")["TEAM_ID"].unique()
    lut = {}
    for gid, teams in gt.items():
        if len(teams) == 2:
            lut[(gid, teams[0])] = teams[1]
            lut[(gid, teams[1])] = teams[0]
    shots["OPP_TEAM_ID"] = [lut.get((g, t), np.nan)
                            for g, t in zip(shots["GAME_ID"], shots["TEAM_ID"])]
    shots = shots[shots["OPP_TEAM_ID"].notna()].copy()
    shots["OPP_TEAM_ID"] = shots["OPP_TEAM_ID"].astype(shots["TEAM_ID"].dtype)
    n_bc = int((shots["zone"] == "Backcourt").sum())
    shots5 = shots[shots["zone"].isin(ZONES)].copy()
    if verbose:
        print(f"  raw shots (partition, opponent resolved) = {len(shots)}; "
              f"Backcourt dropped = {n_bc}; five-zone shots = {len(shots5)}")
        print(f"  sorted(season.unique()) = {sorted(shots5['season'].unique())}")
    return shots, shots5, n_bc


def _ewm_prior(df, valcol, keys, alpha):
    """EWMA of `valcol` over strictly PRIOR rows within `keys`, adjust=True,
    ignore_na=True -- an independent transcription of the frozen baseline's
    _smooth + _shift_state.  `df` must already be in the baseline's sort order."""
    g = df.groupby(keys, sort=False)[valcol]
    sm = g.transform(lambda x: x.ewm(alpha=alpha, adjust=True, ignore_na=True).mean())
    return sm.groupby([df[k] for k in keys], sort=False).shift(1)


def build_frame(verbose=True):
    """Independent rebuild of E1_I0004_shot_selection/selection_frame.parquet."""
    shots, shots5, n_bc = load_shots(verbose)

    pgt = (shots5.groupby(["PLAYER_ID", "season", "GAME_ID", "game_date", "TEAM_ID",
                           "OPP_TEAM_ID"]).size().rename("fga").reset_index())
    pzt = (shots5.groupby(["PLAYER_ID", "season", "GAME_ID", "zone"]).size()
           .rename("z_att").reset_index())
    panel = (pgt.assign(_k=1).merge(pd.DataFrame({"zone": ZONES, "_k": 1}), on="_k")
             .drop(columns="_k"))
    panel = panel.merge(pzt, on=["PLAYER_ID", "season", "GAME_ID", "zone"], how="left")
    panel["z_att"] = panel["z_att"].fillna(0.0)
    panel["share"] = panel["z_att"] / panel["fga"]
    panel = panel.rename(columns={"PLAYER_ID": "player_id", "GAME_ID": "game_id"})

    # ---- S1 = EWMA_0.03(share)[strictly prior], per zone x player-season.
    panel = panel.sort_values(["zone", "player_id", "season", "game_date", "game_id"],
                              kind="stable").reset_index(drop=True)
    parts = []
    for z in ZONES:
        q = panel[panel["zone"] == z].copy()
        q["S1"] = _ewm_prior(q, "share", ["player_id", "season"], ALPHA_EFF)
        q["n_prior"] = (q.groupby(["player_id", "season"], sort=False).cumcount()
                        .astype(float))
        q["role_prior_fga"] = _ewm_prior(q, "fga", ["player_id", "season"], ALPHA_EXP)
        parts.append(q)
    panel = pd.concat(parts, ignore_index=True)
    panel.loc[panel["n_prior"] < MIN_PRIOR, ["S1", "role_prior_fga"]] = np.nan

    # ---- league prior share, strictly BEFORE this calendar date, same season.
    lgd = (shots5.groupby(["season", "game_date", "zone"]).size().rename("a")
           .reset_index().sort_values(["season", "zone", "game_date"], kind="stable"))
    lgd["cum"] = lgd.groupby(["season", "zone"], sort=False)["a"].cumsum() - lgd["a"]
    lgt = (shots5.groupby(["season", "game_date"]).size().rename("t").reset_index()
           .sort_values(["season", "game_date"], kind="stable"))
    lgt["cumt"] = lgt.groupby("season", sort=False)["t"].cumsum() - lgt["t"]
    lgd = lgd.merge(lgt[["season", "game_date", "cumt"]], on=["season", "game_date"])
    lgd["lg_share_prior"] = lgd["cum"] / lgd["cumt"]

    panel = panel.merge(lgd[["season", "game_date", "zone", "lg_share_prior"]],
                        on=["season", "game_date", "zone"], how="left")
    panel["lg_panel"] = panel.groupby(["season", "zone"])["lg_share_prior"].transform(
        lambda x: x.bfill().ffill())

    # ---- S2 = shrunk expanding prior-games share.
    panel = panel.sort_values(["zone", "player_id", "season", "game_date", "game_id"],
                              kind="stable").reset_index(drop=True)
    gk = [panel["zone"], panel["player_id"], panel["season"]]
    panel["pre_zatt"] = panel.groupby(gk, sort=False)["z_att"].cumsum() - panel["z_att"]
    panel["pre_fga"] = panel.groupby(gk, sort=False)["fga"].cumsum() - panel["fga"]
    panel["S2"] = ((panel["pre_zatt"] + SHRINK_K * panel["lg_panel"])
                   / (panel["pre_fga"] + SHRINK_K))
    panel.loc[panel["n_prior"] < MIN_PRIOR, "S2"] = np.nan

    # ---- opponent allowance OS (opponent-team x season x GAME level).
    tg = (shots5.groupby(["OPP_TEAM_ID", "season", "GAME_ID", "game_date", "zone"])
          .size().rename("a").reset_index())
    tgw = tg.pivot_table(index=["OPP_TEAM_ID", "season", "GAME_ID", "game_date"],
                         columns="zone", values="a", fill_value=0).reset_index()
    for z in ZONES:
        if z not in tgw.columns:
            tgw[z] = 0
    tgw = tgw.sort_values(["OPP_TEAM_ID", "season", "game_date", "GAME_ID"],
                          kind="stable").reset_index(drop=True)
    tk = [tgw["OPP_TEAM_ID"], tgw["season"]]
    tgw["tot"] = tgw[ZONES].sum(axis=1)
    tgw["pre_tot"] = tgw.groupby(tk, sort=False)["tot"].cumsum() - tgw["tot"]
    for z in ZONES:
        tgw["pre_" + z] = tgw.groupby(tk, sort=False)[z].cumsum() - tgw[z]
        tgw["oppshare_" + z] = tgw["pre_" + z] / tgw["pre_tot"]
    tgw["OS_ok"] = tgw["pre_tot"] >= MIN_PRE_TOTAL

    osl = tgw.melt(id_vars=["OPP_TEAM_ID", "season", "GAME_ID", "game_date", "OS_ok",
                            "pre_tot"],
                   value_vars=["oppshare_" + z for z in ZONES],
                   var_name="zone", value_name="opp_share_prior")
    osl["zone"] = osl["zone"].str.replace("oppshare_", "", regex=False)
    osl = osl.merge(lgd[["season", "game_date", "zone", "lg_share_prior"]],
                    on=["season", "game_date", "zone"], how="left")
    osl["OS"] = osl["opp_share_prior"] - osl["lg_share_prior"]
    osl.loc[~osl["OS_ok"], ["OS", "opp_share_prior"]] = np.nan

    panel = panel.drop(columns=["lg_share_prior"]).rename(
        columns={"lg_panel": "lg_share_prior"})
    panel = panel.merge(
        osl[["OPP_TEAM_ID", "season", "GAME_ID", "zone", "OS", "opp_share_prior"]]
        .rename(columns={"GAME_ID": "game_id"}),
        on=["OPP_TEAM_ID", "season", "game_id", "zone"], how="left")

    # FILTER-POINT: partition re-assert before gating.
    panel = panel[panel["season"].isin(PARTITION)].copy()
    assert_partition(panel, "panel")

    SEL = panel[(panel["fga"] >= MIN_FGA_GAME)
                & panel[["share", "S1", "S2", "OS", "role_prior_fga"]]
                .notna().all(axis=1)].copy()
    SEL["resid_S1"] = SEL["share"] - SEL["S1"]
    SEL["resid_S2"] = SEL["share"] - SEL["S2"]
    assert_partition(SEL, "SEL")
    cols = ["zone", "player_id", "season", "game_id", "TEAM_ID", "OPP_TEAM_ID",
            "game_date", "fga", "z_att", "share", "S1", "S2", "resid_S1", "resid_S2",
            "OS", "opp_share_prior", "lg_share_prior", "role_prior_fga", "n_prior"]
    return SEL[cols].reset_index(drop=True), panel, shots5, tgw


# --------------------------------------------------------- published-null machinery
class ZoneSuff:
    """Sufficient statistics for OLS of y on a cluster-CONSTANT x.  Transcribed from
    the parent screen so its permutation p-values can be reproduced exactly."""

    def __init__(self, df, zone, canonical_keys):
        d = df[df["zone"] == zone][["y", "x", "opp", "season"]].dropna()
        self.zone = zone
        self.N = len(d)
        self.y_row = d["y"].to_numpy(float)
        self.x_row = d["x"].to_numpy(float)
        pos = {k: i for i, k in enumerate(canonical_keys)}
        inv = np.array([pos[f"{a}_{b}"] for a, b in zip(d["season"], d["opp"])], int)
        K = len(canonical_keys)
        self.nc = np.bincount(inv, minlength=K).astype(float)
        self.Syc = np.bincount(inv, weights=self.y_row, minlength=K)
        self.present = self.nc > 0
        self.xc = np.divide(np.bincount(inv, weights=self.x_row, minlength=K), self.nc,
                            out=np.zeros(K), where=self.present)
        self.Sy = float(self.y_row.sum())
        self.ybar = self.Sy / self.N
        self.SSTy = float(((self.y_row - self.ybar) ** 2).sum())
        self.inv = inv

    def stat(self, xc):
        p = self.present
        nc, Syc = self.nc[p], self.Syc[p]
        xv = xc[p]
        xbar = float((nc * xv).sum() / self.N)
        dx = xv - xbar
        Sxx = float((nc * dx * dx).sum())
        Sxy = float((dx * (Syc - nc * self.ybar)).sum())
        return Sxy / Sxx


def season_groups(keys):
    seasons = np.array([k.split("_")[0] for k in keys])
    return [np.where(seasons == s)[0] for s in np.unique(seasons)]


def perm_maps(groups, rng):
    n = sum(len(g) for g in groups)
    out = np.arange(n)
    for m in groups:
        out[m] = rng.permutation(m)
    return out


def row_beta(y, x):
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    xm = x.mean()
    dx = x - xm
    return float((dx * (y - y.mean())).sum() / (dx * dx).sum())


def ols(y, X):
    """Plain unweighted OLS.  Returns (coef, r2 about the unweighted mean, resid)."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    sse = float(e @ e)
    sst = float(((y - y.mean()) ** 2).sum())
    return b, float(1.0 - sse / sst), e


# ------------------------------------------------------------- decision stratum ----
MP_COLS = ["game_id", "season", "season_type", "game_date", "team_id", "opp_team_id",
           "player_id", "minutes", "starter_flag"]


def decision_frame(verbose=True):
    """D081's decision stratum, built from master_player (asof_granularity == 'row',
    manifest read as a COLUMN VALUE), restricted to the partition."""
    mp = pd.read_parquet(os.path.join(ROOT, "data", "masters", "master_player.parquet"),
                         columns=MP_COLS)
    # FILTER-POINT: partition restriction, immediately after load.
    mp = mp[mp["season"].isin(PARTITION)].copy()
    assert_partition(mp, "master_player")
    mp["minutes"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
    d = mp[mp["minutes"] > 0].copy()
    d = d.sort_values(["season", "player_id", "game_date", "game_id"],
                      kind="stable").reset_index(drop=True)
    gp = d.groupby(["season", "player_id"], sort=False)
    d["n_prior_min"] = gp.cumcount().astype(float)
    d["prior5_minutes"] = gp["minutes"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    d["DECISION"] = (d["n_prior_min"] >= 8.0) & (d["prior5_minutes"] >= 24.0)
    if verbose:
        print(f"  master_player appeared rows (partition) = {len(d)}; "
              f"DECISION = {int(d['DECISION'].sum())}")
    return d
