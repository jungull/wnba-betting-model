"""
E0 I0012 -- layer 3 (matchup interaction) at PLAYER level, NON-COLLINEAR formulations.

Shared base. Loads the masters, applies the exploration partition, and builds the
"base model" every formulation in this sweep is tested ON TOP OF:

    y ~ O (own pregame rate) + D (opponent OVERALL pregame defensive allowance) + O*D

The design rule for this sweep (from the I0010 post-mortem): any candidate matchup
variable M must be RESIDUALIZED against D before being tested. A matchup variable that
carries nothing after residualization is overall opponent defence wearing a costume.

PARTITION (GRAPH_POLICY 13.2): seasons 2021-2024 ONLY.
  # FILTER-POINT applied immediately after each load, asserted, and re-asserted before write.
  The 2025/2026 confirmation holdout is never read, joined, counted, or described.

MANIFEST CHECK (13.2.2), performed programmatically in check_manifest():
  data/masters/master_player.parquet.manifest.json -> "asof_granularity": "row"
  data/masters/master_team.parquet.manifest.json   -> "asof_granularity": "row"
  Row granularity => filtering to 2021-2024 is SUFFICIENT. Both artifacts are usable at E0.

KNOWN HAZARDS HONORED HERE:
  * master_player.position is a starting-LINEUP-SLOT label, not a position. NOT used as a
    position field anywhere in this sweep. Position, where needed, comes from
    data/reference/player_bios.csv (position_raw / height_inches / weight_lbs).
  * master_player.pace is corrupt on this partition. NOT read. Possessions come from the
    `possessions` column, whose sanity is printed by poss_sanity().
  * observed_time is a local file mtime in mid-2026. DROPPED at load; safe_write() re-checks.
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0012_layer3_noncollinear")
PARTITION = [2021, 2022, 2023, 2024]
TARGETS = ["pts", "reb", "ast"]
MIN_MIN_ANALYSIS = 10.0
SHRINK_K = 5.0
MIN_PRIOR_UNITS = 3.0
SEED = 20260807

# Columns that must never reach an output file written by this sweep.
BANNED_COLS = ["observed_time"]

pd.set_option("display.width", 240)
np.seterr(divide="ignore", invalid="ignore")


def hdr(s):
    print("\n" + "=" * 78)
    print(s)
    print("=" * 78)


# ------------------------------------------------------------------ manifest gate
def check_manifest(rel):
    """13.2.2 artifact contamination gate. Returns the manifest dict; raises if unusable."""
    p = os.path.join(ROOT, rel + ".manifest.json")
    with open(p, "r", encoding="utf-8") as f:
        m = json.load(f)
    g = m.get("asof_granularity")
    print("  manifest %-42s asof_granularity=%r  fit_seasons=%s"
          % (os.path.basename(rel), g, m.get("fit_seasons")))
    if g != "row":
        raise RuntimeError("UNUSABLE AT E0: %s has asof_granularity=%r (not 'row'); "
                           "filtering to 2021-2024 does not bound it." % (rel, g))
    return m


# ------------------------------------------------------------------ loads
def load_player():
    check_manifest(r"data\masters\master_player.parquet")
    mp = pd.read_parquet(os.path.join(ROOT, r"data\masters\master_player.parquet"))
    n0 = len(mp)
    # FILTER-POINT <<< exploration partition
    mp = mp[mp["season"].isin(PARTITION)].copy()
    assert set(mp["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION (player)"
    mp = mp.drop(columns=[c for c in BANNED_COLS if c in mp.columns])
    mp = mp[mp["season_type"] == "Regular Season"].copy()
    for c in ["pts", "reb", "ast", "oreb", "dreb", "fga", "fg3a", "fta", "ftm",
              "fgm", "fg3m", "tov", "stl", "blk", "points_paint", "minutes", "possessions"]:
        if c in mp.columns:
            mp[c] = pd.to_numeric(mp[c], errors="coerce").astype("float64")
    for c in ["team_id", "opp_team_id", "player_id", "game_id"]:
        mp[c] = mp[c].astype("int64")
    mp["gdate"] = pd.to_datetime(mp["game_date"])
    print("  master_player: raw %d -> partition+RS %d rows | seasons %s | max date %s"
          % (n0, len(mp), sorted(mp["season"].unique()), str(mp["gdate"].max().date())))
    return mp.sort_values(["gdate", "game_id", "team_id", "player_id"]).reset_index(drop=True)


def load_team():
    check_manifest(r"data\masters\master_team.parquet")
    mt = pd.read_parquet(os.path.join(ROOT, r"data\masters\master_team.parquet"))
    n0 = len(mt)
    # FILTER-POINT
    mt = mt[mt["season"].isin(PARTITION)].copy()
    assert set(mt["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION (team)"
    mt = mt.drop(columns=[c for c in BANNED_COLS if c in mt.columns])
    mt = mt[mt["season_type"] == "Regular Season"].copy()
    mt["gdate"] = pd.to_datetime(mt["game_date"])
    for c in ["team_id", "opp_team_id", "game_id"]:
        mt[c] = mt[c].astype("int64")
    print("  master_team:   raw %d -> partition+RS %d rows | seasons %s"
          % (n0, len(mt), sorted(mt["season"].unique())))
    return mt.sort_values(["gdate", "game_id", "team_id"]).reset_index(drop=True)


def team_possessions(mt):
    """Possessions derived from master_team (master_player.pace is corrupt; not used).
    Standard estimator, averaged with the opponent's mirror-image estimate."""
    p = (mt["fga"] - mt["oreb"] + mt["tov"] + 0.44 * mt["fta"]).astype(float)
    q = (mt["opp_fga"] - mt["opp_oreb"] + mt["opp_tov"] + 0.44 * mt["opp_fta"]).astype(float)
    out = mt[["game_id", "season", "gdate", "team_id", "opp_team_id", "is_home"]].copy()
    out["team_poss"] = 0.5 * (p + q)
    return out


def poss_sanity(mp):
    s = mp["possessions"]
    print("  possessions sanity: n=%d min=%.1f p1=%.1f med=%.1f mean=%.1f p99=%.1f max=%.1f"
          % (len(s), s.min(), s.quantile(.01), s.median(), s.mean(), s.quantile(.99), s.max()))


# ------------------------------------------------------------------ shift discipline
def prior_expanding(df, keys, valcols, prefix, datecol="gdate"):
    """Cumulative sum of valcols over rows STRICTLY BEFORE the row's date, within `keys`.
    Aggregated to date level first so same-day games cannot see each other."""
    daily = (df.groupby(keys + [datecol], as_index=False)[valcols].sum()
               .sort_values(keys + [datecol]).reset_index(drop=True))
    prior = daily.groupby(keys, sort=False)[valcols].cumsum().to_numpy() - daily[valcols].to_numpy()
    out = daily[keys + [datecol]].copy()
    for i, c in enumerate(valcols):
        out[prefix + c] = prior[:, i]
    return df.merge(out, on=keys + [datecol], how="left")


# ------------------------------------------------------------------ regression helpers
def r2(y, X):
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    return 1.0 - float(r @ r) / float(((y - y.mean()) ** 2).sum())


def fit_beta(y, X):
    Xm = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in X])
    b, *_ = np.linalg.lstsq(Xm, y, rcond=None)
    return b


def resid_on(y, X):
    """Residual of y after regressing on X (list of arrays), with intercept."""
    Xm = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in X])
    b, *_ = np.linalg.lstsq(Xm, np.asarray(y, float), rcond=None)
    return np.asarray(y, float) - Xm @ b


def zwithin(df, col, keys=("season",)):
    """Within-group centered then unit-scaled."""
    v = df[col] - df.groupby(list(keys))[col].transform("mean")
    sd = v.std()
    return v / sd if sd > 0 else v


def var_decomp(df, col, group):
    """Between- vs within-group variance decomposition of `col` over `group`.
    Returns (between_frac, within_frac, n_groups, median_group_n).
    If between_frac is large the raw test is testing the GROUP, not the matchup."""
    d = df[[col, group]].dropna()
    gm = d.groupby(group)[col].transform("mean")
    grand = d[col].mean()
    ss_b = float(((gm - grand) ** 2).sum())
    ss_w = float(((d[col] - gm) ** 2).sum())
    tot = ss_b + ss_w
    if tot <= 0:
        return (np.nan, np.nan, d[group].nunique(), np.nan)
    return (ss_b / tot, ss_w / tot, int(d[group].nunique()),
            float(d.groupby(group).size().median()))


def split_half_reliability(df, unit_cols, value_col, weight_col=None, order_col="gdate"):
    """Odd/even split-half reliability of a constructed measure.

    Splits the ROWS that feed the measure into odd/even by within-unit chronological
    rank, recomputes the (weighted) mean on each half, and correlates across units.
    Spearman-Brown corrected. Returns (r_half, r_sb, n_units)."""
    d = df[list(unit_cols) + [value_col] + ([weight_col] if weight_col else []) + [order_col]].dropna().copy()
    d = d.sort_values(list(unit_cols) + [order_col])
    d["_rk"] = d.groupby(list(unit_cols), sort=False).cumcount()
    d["_h"] = d["_rk"] % 2
    if weight_col:
        d["_num"] = d[value_col] * d[weight_col]
        agg = d.groupby(list(unit_cols) + ["_h"]).agg(num=("_num", "sum"), den=(weight_col, "sum")).reset_index()
        agg["m"] = agg["num"] / agg["den"]
    else:
        agg = d.groupby(list(unit_cols) + ["_h"])[value_col].mean().reset_index().rename(columns={value_col: "m"})
    w = agg.pivot_table(index=list(unit_cols), columns="_h", values="m").dropna()
    if len(w) < 8 or w.shape[1] < 2:
        return (np.nan, np.nan, len(w))
    r = float(np.corrcoef(w[0].values, w[1].values)[0, 1])
    sb = 2 * r / (1 + r) if (1 + r) != 0 else np.nan
    return (r, sb, len(w))


# ------------------------------------------------------------------ base model frame
def build_base(mp, T):
    """Pregame own rate (O), pregame OVERALL opponent defensive allowance (D), outcome y.

    Both O and D use strict shift discipline: only rows strictly before the target game's
    date contribute. D excludes this player's own prior contribution to that opponent, so a
    player cannot be part of the defence he is being matched against.
    """
    d = mp.copy()
    d["s"] = d[T].astype(float)
    d["u"] = d["possessions"].astype(float) / 100.0
    d = d[d["u"] > 0].copy()

    d = prior_expanding(d, ["season", "player_id"], ["s", "u"], "own_")
    d = prior_expanding(d, ["season", "opp_team_id"], ["s", "u"], "def_")
    d = prior_expanding(d, ["season", "opp_team_id", "player_id"], ["s", "u"], "dpl_")
    la = prior_expanding(d[["season", "gdate", "s", "u"]].copy(), ["season"], ["s", "u"], "all_")
    d["lg_rate"] = np.where(la["all_u"].values > 1.0, la["all_s"].values / la["all_u"].values, np.nan)

    prev = d.groupby("season")[["s", "u"]].sum().reset_index()
    prev["prev_lg"] = prev["s"] / prev["u"]
    prev["season"] += 1
    d = d.merge(prev[["season", "prev_lg"]], on="season", how="left")
    d["lg_rate"] = d["lg_rate"].fillna(d["prev_lg"]).fillna(d["s"].sum() / d["u"].sum())

    on = d["def_s"] - d["dpl_s"]
    ou = d["def_u"] - d["dpl_u"]
    d["def_pre"] = (on + SHRINK_K * d["lg_rate"]) / (ou + SHRINK_K)
    d.loc[ou < MIN_PRIOR_UNITS, "def_pre"] = np.nan

    po = d.groupby(["season", "player_id"])[["s", "u"]].sum().reset_index()
    po["prev_own"] = po["s"] / po["u"]
    po["season"] += 1
    d = d.merge(po[["season", "player_id", "prev_own"]], on=["season", "player_id"], how="left")
    d["own_pre"] = (d["own_s"] + SHRINK_K * d["prev_own"].fillna(d["lg_rate"])) / (d["own_u"] + SHRINK_K)
    d.loc[d["own_u"] < MIN_PRIOR_UNITS, "own_pre"] = np.nan

    d["y"] = d["s"] / d["u"]
    d["is_analysis"] = d["minutes"] >= MIN_MIN_ANALYSIS
    return d


def prep_frame(d, extra_required=()):
    """Analysis rows with O/D standardized within season and the O*D base interaction."""
    need = ["own_pre", "def_pre", "y"] + list(extra_required)
    w = d[d["is_analysis"]].dropna(subset=need).copy()
    w["O"] = zwithin(w, "own_pre")
    w["D"] = zwithin(w, "def_pre")
    w["OD"] = w["O"] * w["D"]
    return w


def base_terms(g):
    return [g["O"].values, g["D"].values, g["OD"].values]


def screen_increment(w, mcol, label, interact_with_own=True, seasons=PARTITION,
                     center_keys=("season",)):
    """Core E0 test. M is residualized on D (and on O when it is an interaction candidate),
    then we ask for the incremental R2 of M (and of O x M_res) over the base model.

    center_keys controls what M is centered within BEFORE residualization. Use
    ("season","player_id") when the honest question is within-player (i.e. when the
    variance decomposition says most of M's variance is between-player).

    Returns dict with pooled/per-season dR2 and betas.
    """
    w = w.copy()
    w["M"] = zwithin(w, mcol, keys=center_keys)
    # residualize the candidate against overall opponent defence AND the base interaction
    w["Mres"] = resid_on(w["M"].values, [w["D"].values, w["OD"].values])
    sd = w["Mres"].std()
    w["Mres"] = w["Mres"] / sd if sd > 0 else w["Mres"]
    w["OM"] = w["O"] * w["Mres"]

    rows = []
    for seas in list(seasons) + ["POOLED"]:
        g = w if seas == "POOLED" else w[w["season"] == seas]
        if len(g) < 200:
            continue
        y = g["y"].values
        B = base_terms(g)
        r_b = r2(y, B)
        r_m = r2(y, B + [g["Mres"].values])
        rec = {"scope": str(seas), "n": int(len(g)), "R2_base": r_b,
               "dR2_M": r_m - r_b, "beta_M": float(fit_beta(y, B + [g["Mres"].values])[-1])}
        if interact_with_own:
            r_i = r2(y, B + [g["Mres"].values, g["OM"].values])
            rec["dR2_OxM"] = r_i - r_m
            rec["beta_OxM"] = float(fit_beta(y, B + [g["Mres"].values, g["OM"].values])[-1])
        rows.append(rec)
    print("  %-8s %8s %9s %10s %9s %11s %10s" %
          ("scope", "n", "R2_base", "dR2_M", "beta_M", "dR2_OxM", "beta_OxM"))
    for r_ in rows:
        print("  %-8s %8d %9.5f %10.6f %9.4f %11.6f %10.4f" %
              (r_["scope"], r_["n"], r_["R2_base"], r_["dR2_M"], r_["beta_M"],
               r_.get("dR2_OxM", np.nan), r_.get("beta_OxM", np.nan)))
    return {"label": label, "rows": rows, "frame": w}


def screen_increment_quiet(w, mcol, center_keys=("season",)):
    """Pooled-only version of screen_increment, for placebo loops. Returns dR2_M / dR2_OxM.

    IMPORTANT (placebo discipline): callers must permute the ASSIGNMENT of an
    already-computed value to rows and pass the permuted COLUMN here. Permuting a grouping
    key and recomputing the aggregate is a no-op and reproduces the real number with sd 0.
    """
    M = zwithin(w, mcol, keys=center_keys).values
    D = w["D"].values
    OD = w["OD"].values
    O = w["O"].values
    y = w["y"].values
    ok = np.isfinite(M) & np.isfinite(y) & np.isfinite(D) & np.isfinite(O)
    M, D, OD, O, y = M[ok], D[ok], OD[ok], O[ok], y[ok]
    Mr = resid_on(M, [D, OD])
    sd = Mr.std()
    if sd > 0:
        Mr = Mr / sd
    Bs = [O, D, OD]
    r_b = r2(y, Bs)
    r_m = r2(y, Bs + [Mr])
    r_i = r2(y, Bs + [Mr, O * Mr])
    return {"dR2_M": r_m - r_b, "dR2_OxM": r_i - r_m}


def collinearity(w, mcol, dcol="def_pre"):
    """Raw correlation of the candidate with OVERALL opponent defensive strength, WITHIN season.
    This is the I0010 costume test: |r| near 0.5+ means the candidate is mostly overall defence."""
    a = zwithin(w, mcol)
    b = zwithin(w, dcol)
    m = a.notna() & b.notna()
    r_all = float(np.corrcoef(a[m], b[m])[0, 1])
    per = {}
    for s in sorted(w["season"].unique()):
        k = m & (w["season"] == s)
        if k.sum() > 50:
            per[int(s)] = float(np.corrcoef(a[k], b[k])[0, 1])
    return r_all, per


def safe_write(df, name):
    """Drop banned columns, re-assert the partition, then write."""
    d = df.drop(columns=[c for c in BANNED_COLS if c in df.columns]).copy()
    if "season" in d.columns:
        assert set(pd.unique(d["season"])) <= set(PARTITION), "PARTITION VIOLATION before write: %s" % name
    for c in d.columns:
        assert c not in BANNED_COLS, "banned column %s reached write" % c
    p = os.path.join(OUT, name)
    d.to_csv(p, index=False)
    print("  wrote %s  shape=%s" % (name, d.shape))
    return p
