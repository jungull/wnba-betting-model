"""
E0 I0010 / F_POSITIONAL_MATCHUP -- the screen.

Self-contained: reloads master_player, re-applies the partition filter, rebuilds the
allowance features (same logic as build_features.py), then runs steps 4/5/6.

PARTITION (GRAPH_POLICY 13.2): seasons 2021-2024 ONLY. # FILTER-POINT immediately after load.
Manifest: master_player.parquet.manifest.json -> "asof_granularity": "row" -> filtering suffices.

Deterministic: numpy seed 20260807 for the permutation placebo.
"""
import numpy as np
import pandas as pd
import os

np.seterr(divide="ignore", invalid="ignore")

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0010_positional_matchup")
PARTITION = [2021, 2022, 2023, 2024]
TARGETS = ["pts", "reb", "ast"]
MIN_MIN_ANALYSIS = 10.0
SHRINK_K = 5.0
MIN_PRIOR_UNITS = 3.0
N_PERM = 200
SEED = 20260807

pd.set_option("display.width", 220)


def hdr(s):
    print("\n" + "=" * 78); print(s); print("=" * 78)


# ------------------------------------------------------------------ load/filter
mp = pd.read_parquet(os.path.join(ROOT, r"data\masters\master_player.parquet"))
# FILTER-POINT
mp = mp[mp["season"].isin(PARTITION)].copy()
assert set(mp["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
mp = mp[mp["season_type"] == "Regular Season"].copy()
for c in ["pts", "reb", "ast"]:
    mp[c] = mp[c].astype("float64")
mp["minutes"] = mp["minutes"].astype("float64")
mp["possessions"] = mp["possessions"].astype("float64")
for c in ["team_id", "opp_team_id", "player_id"]:
    mp[c] = mp[c].astype("int64")
mp = mp[(mp["minutes"] >= 1.0) & (mp["possessions"] > 0)].copy()
mp["gdate"] = pd.to_datetime(mp["game_date"])
mp = mp.sort_values(["gdate", "game_id", "team_id", "player_id"]).reset_index(drop=True)
# normalisation: per-100-possessions (default) or per-36-minutes (robustness run)
UNITCOL = os.environ.get("I0010_UNIT", "unit100")
mp["unit"] = (mp["possessions"] / 100.0) if UNITCOL == "unit100" else (mp["minutes"] / 36.0)
print("NORMALISATION UNIT:", UNITCOL)

# position group: expanding modal STARTING-SLOT label from strictly prior games
rp = mp["position"].fillna("").astype(str).str.strip()
mp["_G"] = (rp == "G").astype(float); mp["_F"] = (rp == "F").astype(float); mp["_C"] = (rp == "C").astype(float)
pc = (mp.groupby("player_id", sort=False)[["_G", "_F", "_C"]].cumsum() - mp[["_G", "_F", "_C"]].values).to_numpy()
mp["pos_group"] = np.where(pc.sum(1) > 0, np.array(["G", "F", "C"])[pc.argmax(1)], "U")
POOL = mp[mp["pos_group"] != "U"].copy().reset_index(drop=True)
assert set(POOL["season"].unique()) <= set(PARTITION)
print("pooled rows (known position group, RS, 2021-2024):", len(POOL),
      "| seasons:", sorted(POOL["season"].unique()))


def prior_expanding(df, keys, valcols, prefix):
    daily = df.groupby(keys + ["gdate"], as_index=False)[valcols].sum().sort_values(keys + ["gdate"]).reset_index(drop=True)
    prior = daily.groupby(keys, sort=False)[valcols].cumsum().to_numpy() - daily[valcols].to_numpy()
    out = daily[keys + ["gdate"]].copy()
    for i, c in enumerate(valcols):
        out[prefix + c] = prior[:, i]
    return df.merge(out, on=keys + ["gdate"], how="left")


def r2(y, X):
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    return 1.0 - float(r @ r) / float(((y - y.mean()) ** 2).sum())


def dummies(s):
    lv = sorted(pd.unique(s))[1:]
    return [(s == v).astype(float).values for v in lv]


# ------------------------------------------------------------------ build features
def build(T, oppcol="opp_team_id", src=None):
    d = (POOL if src is None else src).copy()
    d["s"] = d[T]; d["u"] = d["unit"]; d["opp"] = d[oppcol]
    cell = ["season", "opp", "pos_group"]

    # STEP 1+2: within-season strict LOO (drop the whole game AND all of this player's rows)
    Tt = d.groupby(cell)[["s", "u"]].transform("sum")
    Gg = d.groupby(cell + ["game_id"])[["s", "u"]].transform("sum")
    Pp = d.groupby(cell + ["player_id"])[["s", "u"]].transform("sum")
    num = Tt["s"] - Gg["s"] - Pp["s"] + d["s"]; den = Tt["u"] - Gg["u"] - Pp["u"] + d["u"]
    d["allow_loo"] = np.where(den > 1e-9, num / den, np.nan)
    d["allow_naive"] = Tt["s"] / Tt["u"]

    # STEP 3: pregame-observable
    d = prior_expanding(d, cell, ["s", "u"], "cel_")
    d = prior_expanding(d, cell + ["player_id"], ["s", "u"], "cpl_")
    d = prior_expanding(d, ["season", "pos_group"], ["s", "u"], "lg_")
    d = prior_expanding(d, ["season", "player_id"], ["s", "u"], "own_")
    d = prior_expanding(d, ["season", "opp"], ["s", "u"], "def_")
    d = prior_expanding(d, ["season", "opp", "player_id"], ["s", "u"], "dpl_")

    ps = d.groupby(["season", "pos_group"])[["s", "u"]].sum().reset_index()
    ps["prev_rate"] = ps["s"] / ps["u"]; ps["season"] += 1
    d = d.merge(ps[["season", "pos_group", "prev_rate"]], on=["season", "pos_group"], how="left")
    d["lg_rate"] = pd.Series(np.where(d["lg_u"] > 1.0, d["lg_s"] / d["lg_u"], np.nan)).fillna(d["prev_rate"])

    pn = d["cel_s"] - d["cpl_s"]; pu = d["cel_u"] - d["cpl_u"]
    d["allow_pre"] = (pn + SHRINK_K * d["lg_rate"]) / (pu + SHRINK_K)
    d.loc[pu < MIN_PRIOR_UNITS, "allow_pre"] = np.nan

    on = d["def_s"] - d["dpl_s"]; ou = d["def_u"] - d["dpl_u"]
    la = prior_expanding(d[["season", "gdate", "s", "u"]].copy(), ["season"], ["s", "u"], "all_")
    d["lg_all_rate"] = pd.Series(np.where(la["all_u"].values > 1.0, la["all_s"].values / la["all_u"].values, np.nan)).fillna(d["lg_rate"])
    d["def_pre"] = (on + SHRINK_K * d["lg_all_rate"]) / (ou + SHRINK_K)
    d.loc[ou < MIN_PRIOR_UNITS, "def_pre"] = np.nan

    OwnT = d.groupby(["season", "player_id"])[["s", "u"]].transform("sum")
    d["own_loo"] = np.where((OwnT["u"] - d["u"]) > 1e-9, (OwnT["s"] - d["s"]) / (OwnT["u"] - d["u"]), np.nan)
    po = d.groupby(["season", "player_id"])[["s", "u"]].sum().reset_index()
    po["prev_own"] = po["s"] / po["u"]; po["season"] += 1
    d = d.merge(po[["season", "player_id", "prev_own"]], on=["season", "player_id"], how="left")
    d["own_pre"] = (d["own_s"] + SHRINK_K * d["prev_own"].fillna(d["lg_rate"])) / (d["own_u"] + SHRINK_K)
    d.loc[d["own_u"] < MIN_PRIOR_UNITS, "own_pre"] = np.nan

    d["y"] = d["s"] / d["u"]
    return d[d["minutes"] >= MIN_MIN_ANALYSIS].copy()


def demean(df, col, keys=("season", "pos_group")):
    """Within-(season,position) centering -- isolates the OPPONENT-specific component of the
    allowance from the (large) between-position level differences."""
    return df[col] - df.groupby(list(keys))[col].transform("mean")


# ================================================================== run
RES = {}
for T in TARGETS:
    hdr("TARGET = %s" % T)
    d = build(T)

    # --- STEP 2 diagnostic: what LOO actually buys, WITHIN position group
    hdr_diag = d.dropna(subset=["own_loo", "allow_loo", "allow_naive"]).copy()
    for c in ["own_loo", "allow_loo", "allow_naive"]:
        hdr_diag[c + "_c"] = demean(hdr_diag, c)
    print("STEP 2 -- leave-one-out effect (correlation of player's own tendency with the")
    print("          aggregate he is part of), WITHIN (season, position group):")
    print("  naive (no LOO):  r = %+.4f" % hdr_diag[["own_loo_c", "allow_naive_c"]].corr().iloc[0, 1])
    print("  strict LOO    :  r = %+.4f" % hdr_diag[["own_loo_c", "allow_loo_c"]].corr().iloc[0, 1])
    print("  RAW (not demeaned) naive r=%+.4f  LOO r=%+.4f   <- dominated by position level"
          % (hdr_diag[["own_loo", "allow_naive"]].corr().iloc[0, 1],
             hdr_diag[["own_loo", "allow_loo"]].corr().iloc[0, 1]))
    print("  allowance sd: RAW %.3f  vs WITHIN-(season,pos) %.3f  <- how much is really opponent"
          % (hdr_diag["allow_loo"].std(), hdr_diag["allow_loo_c"].std()))

    # --- STEP 4: incremental R2 of the interaction over both additive main effects
    for tag, ocol, acol in [("WITHIN-SEASON LOO (uses future games)", "own_loo", "allow_loo"),
                            ("PREGAME-OBSERVABLE (decides the verdict)", "own_pre", "allow_pre")]:
        w = d.dropna(subset=[ocol, acol, "def_pre", "y"]).copy()
        w["O"] = demean(w, ocol); w["A"] = demean(w, acol); w["D"] = demean(w, "def_pre")
        # scale to unit sd within the frame so the product term is well conditioned
        for c in ["O", "A", "D"]:
            w[c] = w[c] / w[c].std()
        w["OA"] = w["O"] * w["A"]; w["OD"] = w["O"] * w["D"]
        print("\nSTEP 4 -- %s   [n=%d]" % (tag, len(w)))
        print("  %-8s %7s %9s %9s %11s %11s" % ("season", "n", "R2_add", "R2_full", "dR2_inter", "beta_inter"))
        rows = []
        for seas in PARTITION + ["POOLED"]:
            g = w if seas == "POOLED" else w[w["season"] == seas]
            if len(g) < 200:
                continue
            pg = dummies(g["pos_group"])
            base = [g["O"].values, g["A"].values] + pg
            full = base + [g["OA"].values]
            y = g["y"].values
            ra, rf = r2(y, base), r2(y, full)
            X = np.column_stack([np.ones(len(g))] + [np.asarray(c, float) for c in full])
            b = np.linalg.lstsq(X, y, rcond=None)[0]
            print("  %-8s %7d %9.5f %9.5f %11.5f %11.4f" % (seas, len(g), ra, rf, rf - ra, b[-1]))
            rows.append((seas, len(g), ra, rf, rf - ra, b[-1]))
        if "PREGAME" in tag:
            RES[T] = {"step4": rows, "frame": w}

    # --- STEP 5: overall-defence confound
    w = RES[T]["frame"]
    print("\nSTEP 5 -- overall-opponent-defence confound (pregame frame)")
    print("  corr(positional allowance, overall opp defence) within (season,pos) = %+.4f"
          % w[["A", "D"]].corr().iloc[0, 1])
    # residualise the positional allowance on overall defence -> pure positional component
    Xd = np.column_stack([np.ones(len(w)), w["D"].values])
    w = w.copy()
    w["Ares"] = w["A"].values - Xd @ np.linalg.lstsq(Xd, w["A"].values, rcond=None)[0]
    w["Ares"] = w["Ares"] / w["Ares"].std()
    w["OAres"] = w["O"] * w["Ares"]
    print("  %-8s %7s %11s %11s %11s" % ("season", "n", "dR2_A|D", "dR2_OxA|D", "dR2_OxAres"))
    st5 = []
    for seas in PARTITION + ["POOLED"]:
        g = w if seas == "POOLED" else w[w["season"] == seas]
        if len(g) < 200:
            continue
        pg = dummies(g["pos_group"])
        y = g["y"].values
        b_OD = [g["O"].values, g["D"].values] + pg + [g["OD"].values]      # own + overall D + own*D
        b_ODA = b_OD + [g["A"].values]                                     # + positional allowance
        b_ODAI = b_ODA + [g["OA"].values]                                  # + positional interaction
        b_res = b_OD + [g["Ares"].values]
        b_resI = b_res + [g["OAres"].values]
        d1 = r2(y, b_ODA) - r2(y, b_OD)
        d2 = r2(y, b_ODAI) - r2(y, b_ODA)
        d3 = r2(y, b_resI) - r2(y, b_res)
        print("  %-8s %7d %11.5f %11.5f %11.5f" % (seas, len(g), d1, d2, d3))
        st5.append((seas, len(g), d1, d2, d3))
    RES[T]["step5"] = st5
    RES[T]["frame5"] = w
    # Drop carried-through source metadata before writing. `observed_time` in master_player is a
    # LOCAL FILE MTIME (a mid-2026 build timestamp; the manifest says so explicitly and that it
    # is NOT an as-of bound) -- not season data, but it must not reach this experiment's bytes.
    keep = ["game_id", "season", "game_date", "team_id", "opp_team_id", "player_id", "player_name",
            "pos_group", "minutes", "possessions", "unit", "s", "y", "allow_loo", "allow_naive",
            "allow_pre", "def_pre", "own_loo", "own_pre", "lg_rate"]
    d[[c for c in keep if c in d.columns]].to_csv(os.path.join(OUT, "features_%s.csv" % T), index=False)

# ================================================================== STEP 6 placebo
hdr("STEP 6 -- PLACEBO: permute opponent identity within season (%d perms, seed %d)" % (N_PERM, SEED))
rng = np.random.default_rng(SEED)
teams_by_season = {s: np.array(sorted(POOL.loc[POOL.season == s, "opp_team_id"].unique())) for s in PARTITION}
print("teams per season:", {s: len(v) for s, v in teams_by_season.items()})

# NOTE ON PLACEBO CONSTRUCTION (a bug found and fixed in this script):
# Simply relabelling opponent ids and rebuilding is a NO-OP -- the cell (season, pi(opp), pos)
# is the same set of rows as (season, opp, pos), just renamed, so every row still receives its
# own true allowance and the "placebo" reproduces the real number exactly (sd = 0). The correct
# placebo keeps the allowance panel keyed on TRUE opponents and makes each row look up a
# DIFFERENT team's allowance as of the same date. That is what is implemented below.

def team_panel(T):
    """Per (season, pos_group, team) cumulative allowance-through-date panel, true opponents."""
    p = (POOL.assign(s=POOL[T], u=POOL["unit"])
         .groupby(["season", "pos_group", "opp_team_id", "gdate"], as_index=False)[["s", "u"]].sum()
         .sort_values(["season", "pos_group", "opp_team_id", "gdate"]).reset_index(drop=True))
    p[["cs", "cu"]] = p.groupby(["season", "pos_group", "opp_team_id"], sort=False)[["s", "u"]].cumsum()
    return p[["season", "pos_group", "opp_team_id", "gdate", "cs", "cu"]].sort_values("gdate").reset_index(drop=True)


def lookup_allow(rows, panel, team_col):
    """Allowance of `team_col` as of each row's date (cumulative STRICTLY before that date)."""
    L = rows[["season", "pos_group", team_col, "gdate", "lg_rate"]].copy()
    L = L.rename(columns={team_col: "opp_team_id"}).sort_values("gdate").reset_index()
    m = pd.merge_asof(L, panel, on="gdate", by=["season", "pos_group", "opp_team_id"],
                      direction="backward", allow_exact_matches=False)
    a = (m["cs"] + SHRINK_K * m["lg_rate"]) / (m["cu"] + SHRINK_K)
    a = a.where(m["cu"] >= MIN_PRIOR_UNITS)
    return pd.Series(a.values, index=m["index"].values).reindex(rows.index)


def inc_r2(w):
    """incremental R2 of the own x allowance interaction over both additive main effects
    (+ position dummies), pooled and per season."""
    w = w.copy()
    w["O"] = demean(w, "own_pre"); w["A"] = demean(w, "allow_pre")
    w["O"] /= w["O"].std(); w["A"] /= w["A"].std(); w["OA"] = w["O"] * w["A"]
    out = {}
    for seas in ["POOLED"] + PARTITION:
        g = w if seas == "POOLED" else w[w["season"] == seas]
        if len(g) < 200:
            out[seas] = np.nan; continue
        pg = dummies(g["pos_group"]); y = g["y"].values
        base = [g["O"].values, g["A"].values] + pg
        out[seas] = r2(y, base + [g["OA"].values]) - r2(y, base)
    return out


placebo = {}
for T in TARGETS:
    panel = team_panel(T)
    base = build(T).dropna(subset=["own_pre", "y", "lg_rate"]).copy()

    # REAL, computed through the identical team-panel machinery (identity map) so that the real
    # number and the placebo floor differ ONLY in which team's allowance a row receives.
    base["allow_pre"] = lookup_allow(base, panel, "opp_team_id")
    real = inc_r2(base.dropna(subset=["allow_pre"]))

    vals = []
    for it in range(N_PERM):
        pmap = {}
        for s, tm in teams_by_season.items():
            while True:
                pr = rng.permutation(tm)
                if not np.any(pr == tm):        # derangement: nobody keeps their own defence
                    break
            pmap.update({(int(s), int(a)): int(b) for a, b in zip(tm, pr)})
        b2 = base.copy()
        b2["opp_fake"] = [pmap[(int(s), int(o))] for s, o in
                          zip(b2["season"].values, b2["opp_team_id"].values)]
        b2["allow_pre"] = lookup_allow(b2, panel, "opp_fake")
        vals.append(inc_r2(b2.dropna(subset=["allow_pre"])))
    V = pd.DataFrame(vals)
    placebo[T] = V
    print("\n---- %s ----" % T)
    print("  %-8s %10s %10s %10s %10s %10s %10s" %
          ("season", "REAL", "plc_mean", "plc_sd", "plc_med", "plc_p95", "frac>=real"))
    for seas in ["POOLED"] + PARTITION:
        v = V[seas].dropna().values
        r_ = real[seas]
        print("  %-8s %10.6f %10.6f %10.6f %10.6f %10.6f %10.3f" %
              (seas, r_, v.mean(), v.std(), np.median(v), np.quantile(v, 0.95), float((v >= r_).mean())))
    p_pool = float((V["POOLED"].values >= real["POOLED"]).mean())
    print("  VERDICT SIGNAL: pooled real sits at placebo percentile %.3f -> %s"
          % (1 - p_pool, "INSIDE THE NOISE FLOOR" if p_pool > 0.05 else "outside the floor"))
    V.assign(target=T).to_csv(os.path.join(OUT, "placebo_draws_%s.csv" % T), index=False)

hdr("DONE")
