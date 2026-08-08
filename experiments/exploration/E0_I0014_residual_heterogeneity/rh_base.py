"""
E0_I0014 RESIDUAL HETEROGENEITY -- shared loader / feature builder / null machinery.

PARTITION (GRAPH_POLICY 13.2): seasons 2021-2024 ONLY.  Enforced by VALUE TEST on the season
    column and on max(game_date) at every load and before every write.  No regex/byte scan of
    file contents is used as a partition check anywhere (that check has produced false positives
    twice in this program).

RESIDUAL SOURCE (Step 1): experiments/cbs_v15_player_oof_v5/attempt_001/predictions__*__<S>.parquet
    Season-chronological walk-forward: the fold for season S is fitted on Tier-A rows of seasons
    < S only (fold_receipt__<S>.json: train_seasons, model_was_fitted, fold_boundary receipt ok,
    own_outcome_never_informed_its_forecast=true).  Each per-season artifact is asof_granularity
    "artifact" but its OWN fit_through_season is S, so the 2021..2024 files are wholly inside the
    exploration partition -- no filtering is relied on, the artifacts themselves are bounded.
    The 2021 fold is DEGENERATE (n_train_rows=0, model_was_fitted=false, declared-constant only)
    and is EXCLUDED from the screen.  Screen seasons = 2022, 2023, 2024.

RETROSPECTIVE-BASELINE RULE (trap 3): every constructed candidate is a STRICTLY-PRIOR expanding or
    trailing window inside the same season, built by sort-by-date then .shift(1) before any cumsum
    or rolling.  No full-season aggregate, no leave-one-out, no leave-one-season-out anywhere.
    See the TIME-WINDOW TABLE in NOTES.md.

PERMUTATION (trap 4/5): block permutation of ALREADY-COMPUTED values.  PLAYER scheme reassigns
    whole (season, player_id) blocks; TEAM scheme reassigns whole (season, team_id) blocks; both
    stay inside season.  The naive ROW scheme is reported alongside only to expose the inflation
    factor.  Nothing is recomputed inside a draw.  The DEFECTIVE NO-OP placebo (permute a key that
    the value lookup does not consult) is run on purpose in the diagnostic.

R2 CONVENTION (D069): plain unweighted OLS R2 = 1 - SSE/SST about the UNWEIGHTED mean.  No
    weighting anywhere in this screen.

HAZARDS honoured: master_player.pace / pace_per40 / estimated_pace are corrupt (verified upstream
    in E0_I0013) and are NOT read.  master_player.possessions is clean and is used.
    data/w1_truth/player_game_availability.csv is asof_granularity "artifact" with
    fit_through_season 2026 -> UNUSABLE, NOT OPENED.  data/zone_maps/* not touched.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0014_residual_heterogeneity")
OOF = os.path.join(ROOT, r"experiments\cbs_v15_player_oof_v5\attempt_001")
CONTRACT = os.path.join(ROOT, r"experiments\prediction_contract_v4\player_game.parquet")
MASTER = os.path.join(ROOT, r"data\masters\master_player.parquet")

PARTITION = [2021, 2022, 2023, 2024]
SCREEN_SEASONS = [2022, 2023, 2024]          # 2021 fold is degenerate (no model fitted)
HOLDOUT = {2025, 2026}

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def check_manifest(rel, require_row=True):
    """Read the sibling manifest and inspect asof_granularity.  VALUE inspection, not text scan."""
    p = os.path.join(ROOT, rel.replace("/", os.sep)) if not os.path.isabs(rel) else rel
    mp = p + ".manifest.json"
    if not os.path.exists(mp):
        print("  MANIFEST MISSING for %s -> NOT USABLE" % rel)
        return None
    m = json.load(open(mp))
    g = m.get("asof_granularity")
    print("  manifest %-70s asof_granularity=%-9s fit_through_season=%s" %
          (os.path.basename(p), g, m.get("fit_through_season")))
    if require_row and g != "row":
        raise SystemExit("REFUSED: %s is asof_granularity=%s, filtering does not help" % (rel, g))
    return m


def guard(df, where, col="season"):
    s = set(pd.unique(df[col]))
    bad = s & HOLDOUT
    if bad:
        raise SystemExit("PARTITION VIOLATION at %s: %s" % (where, sorted(bad)))
    print("  guard ok  %-46s n=%-7d seasons=%s" % (where, len(df), sorted(s)))


def safe_write(df, name):
    if "season" in df.columns:
        guard(df, "write:" + name)
    df.to_csv(os.path.join(OUT, name), index=False)
    print("  wrote %s (%d rows)" % (name, len(df)))


# ----------------------------------------------------------------------------- loaders
def load_master():
    check_manifest("data/masters/master_player.parquet", require_row=True)
    mp = pd.read_parquet(MASTER)
    mp = mp[mp["season"].isin(PARTITION)].copy()                       # FILTER-POINT
    mp["gdate"] = pd.to_datetime(mp["game_date"])
    assert mp["gdate"].max() < pd.Timestamp("2025-01-01"), "date bound violated"
    mp["minutes"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
    mp["appeared"] = mp["minutes"] > 0
    mp = mp.drop(columns=[c for c in ["observed_time"] if c in mp.columns])
    guard(mp, "master_player after load")
    return mp


def load_contract():
    check_manifest("experiments/prediction_contract_v4/player_game.parquet", require_row=True)
    c = pd.read_parquet(CONTRACT)
    c = c[c["season"].isin(PARTITION)].copy()                          # FILTER-POINT
    c["gdate"] = pd.to_datetime(c["game_date"])
    assert c["gdate"].max() < pd.Timestamp("2025-01-01"), "date bound violated"
    guard(c, "contract_v4 player_game after load")
    return c


TARGET_MAP = {
    "pts": "player_scoring_distribution",
    "minutes": "e_minutes_given_active",
    "fga": "attempts_usage",
}


def load_oof(seasons=SCREEN_SEASONS):
    """Load the per-season OOF prediction artifacts.  Each file's OWN manifest is inspected and its
    fit_through_season must be <= 2024 (i.e. the whole artifact sits inside the partition)."""
    frames = []
    for tgt, key in TARGET_MAP.items():
        for s in seasons:
            rel = "experiments/cbs_v15_player_oof_v5/attempt_001/predictions__%s__%d.parquet" % (key, s)
            m = json.load(open(os.path.join(ROOT, rel.replace("/", os.sep)) + ".manifest.json"))
            fts = m.get("fit_through_season")
            print("  oof %-34s season=%d asof_granularity=%-9s fit_through_season=%s fit_seasons=%s"
                  % (key, s, m.get("asof_granularity"), fts, m.get("fit_seasons")))
            if fts is None or int(fts) > 2024:
                raise SystemExit("REFUSED: %s bound at season %s" % (rel, fts))
            d = pd.read_parquet(os.path.join(ROOT, rel.replace("/", os.sep)))
            d = d[["row_uid", "pred_point", "pred_sd", "is_fallback", "fallback_level",
                   "is_cold_start", "n_prior_games", "pred_q05", "pred_q25", "pred_q75",
                   "pred_q95"]].copy()
            d.columns = ["row_uid"] + ["%s__%s" % (tgt, c) for c in d.columns[1:]]
            d["__season"] = s
            frames.append((tgt, s, d))
    out = {}
    for tgt in TARGET_MAP:
        out[tgt] = pd.concat([f for t, s, f in frames if t == tgt], ignore_index=True)
    return out


# ----------------------------------------------------------------------------- features
def _shift_expanding(g, col):
    """strictly-prior cumulative sum of col within an already-date-sorted group"""
    return g[col].shift(1).cumsum()


def build_player_pregame(mp):
    """Player-level PRE-GAME state.  Every column is built from rows STRICTLY BEFORE the target
    game's date, inside the same season (career columns cross seasons but never forward in time).
    Index key: (game_id, team_id, player_id)."""
    d = mp.sort_values(["player_id", "gdate", "game_id"]).copy()
    g = d.groupby(["season", "player_id"], sort=False)
    ga = d.groupby(["player_id"], sort=False)

    ap = d["appeared"].astype(float)
    d["_ap"] = ap
    d["_apmin"] = ap * d["minutes"]

    # --- sample depth (strictly prior, same season) ---
    d["pl_games_prior"] = d.groupby(["season", "player_id"], sort=False)["_ap"].transform(
        lambda x: x.shift(1).cumsum()).fillna(0.0)
    d["pl_minutes_prior"] = d.groupby(["season", "player_id"], sort=False)["_apmin"].transform(
        lambda x: x.shift(1).cumsum()).fillna(0.0)
    # --- sample depth (strictly prior, career within 2021-2024 window) ---
    d["pl_career_games_prior"] = d.groupby(["player_id"], sort=False)["_ap"].transform(
        lambda x: x.shift(1).cumsum()).fillna(0.0)
    d["pl_prior_season_games"] = d["pl_career_games_prior"] - d["pl_games_prior"]
    d["pl_is_rookie_window"] = (d["pl_prior_season_games"] <= 0).astype(float)

    # --- trailing-5 role volatility over PRIOR APPEARANCES only ---
    app = d[d["appeared"]].copy()
    ag = app.groupby(["season", "player_id"], sort=False)
    for src, tag in [("minutes", "min"), ("fga", "fga"), ("pts", "pts"),
                     ("usage_percentage", "usg")]:
        v = pd.to_numeric(app[src], errors="coerce")
        app["_v"] = v
        gg = app.groupby(["season", "player_id"], sort=False)["_v"]
        app["pl_%s_sd5" % tag] = gg.transform(lambda x: x.shift(1).rolling(5, min_periods=3).std())
        app["pl_%s_mean5" % tag] = gg.transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
    app["pl_min_cv5"] = app["pl_min_sd5"] / app["pl_min_mean5"].replace(0, np.nan)
    app["_mn"] = pd.to_numeric(app["minutes"], errors="coerce")
    gmn = app.groupby(["season", "player_id"], sort=False)["_mn"]
    app["pl_min_rng5"] = (gmn.transform(lambda x: x.shift(1).rolling(5, min_periods=3).max()) -
                          gmn.transform(lambda x: x.shift(1).rolling(5, min_periods=3).min()))
    app["pl_min_trend5"] = (gmn.transform(lambda x: x.shift(1).rolling(2, min_periods=2).mean()) -
                            gmn.transform(lambda x: x.shift(3).rolling(3, min_periods=3).mean()))
    app["pl_abs_min_trend5"] = app["pl_min_trend5"].abs()
    sf = pd.to_numeric(app["starter_flag"], errors="coerce").fillna(0.0)
    app["_sf"] = sf
    gsf = app.groupby(["season", "player_id"], sort=False)["_sf"]
    app["pl_start_frac5"] = gsf.transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
    app["_sfchg"] = gsf.transform(lambda x: (x.diff().abs() > 0).astype(float))
    app["pl_start_switch5"] = app.groupby(["season", "player_id"], sort=False)["_sfchg"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=3).sum())
    # rest days since the player's own last APPEARANCE (as-played dates)
    app["pl_rest_days"] = app.groupby(["season", "player_id"], sort=False)["gdate"].transform(
        lambda x: (x - x.shift(1)).dt.days)

    volcols = [c for c in app.columns if c.startswith("pl_") and c not in
               ("pl_games_prior", "pl_minutes_prior", "pl_career_games_prior",
                "pl_prior_season_games", "pl_is_rookie_window")]
    d = d.merge(app[["game_id", "team_id", "player_id"] + volcols],
                on=["game_id", "team_id", "player_id"], how="left")

    keep = ["game_id", "team_id", "player_id", "season", "gdate",
            "pl_games_prior", "pl_minutes_prior", "pl_career_games_prior",
            "pl_prior_season_games", "pl_is_rookie_window"] + volcols
    return d[keep].copy()


def build_team_pregame(mp):
    """Team-level PRE-GAME state.  Roster / churn / schedule columns read ONLY the team's games
    strictly before the target date, in the same season.  Key: (game_id, team_id)."""
    tg = (mp.groupby(["season", "team_id", "game_id", "gdate", "opp_team_id", "is_home"],
                     as_index=False)
            .agg(poss=("possessions", "sum"), n_box=("player_id", "size")))
    tg = tg.sort_values(["season", "team_id", "gdate"]).reset_index(drop=True)

    # rosters / starting fives per (team, game)
    rost = (mp[mp["appeared"]].groupby(["season", "team_id", "game_id"])["player_id"]
            .apply(lambda s: frozenset(s)).rename("roster").reset_index())
    st = mp[(mp["starter_flag"].astype(float) == 1.0)]
    five = (st.groupby(["season", "team_id", "game_id"])["player_id"]
            .apply(lambda s: frozenset(s)).rename("five").reset_index())
    tg = tg.merge(rost, on=["season", "team_id", "game_id"], how="left")
    tg = tg.merge(five, on=["season", "team_id", "game_id"], how="left")

    rows = []
    for (s, t), g in tg.groupby(["season", "team_id"], sort=False):
        g = g.sort_values("gdate").reset_index(drop=True)
        dates = g["gdate"].to_numpy()
        poss = g["poss"].to_numpy(float)
        rosters = list(g["roster"])
        fives = list(g["five"])
        seen = set()             # union of rosters[0..i-1] at the top of iteration i
        seen_lag = set()         # union of rosters[0..i-2] at the top of iteration i
        five_run = 0
        prev_five = None
        for i in range(len(g)):
            # ---- everything below reads indices < i only ----
            tm_game_idx = float(i)
            tm_rest = float((dates[i] - dates[i - 1]) / np.timedelta64(1, "D")) if i >= 1 else np.nan
            if i >= 1:
                w = dates[i] - dates[:i]
                d3 = int((w <= np.timedelta64(3, "D")).sum())
                d7 = int((w <= np.timedelta64(7, "D")).sum())
            else:
                d3, d7 = 0, 0
            tm_poss_mean = float(poss[:i].mean()) if i >= 1 else np.nan
            if i >= 2 and rosters[i - 1] is not None and rosters[i - 2] is not None:
                a, b = rosters[i - 1], rosters[i - 2]
                jac = len(a & b) / max(len(a | b), 1)
                churn = 1.0 - jac
            else:
                churn = np.nan
            # players who debuted for this club in the LAST PRIOR game (never appeared in any
            # game before that one).  Reads rosters[0..i-1] only.
            if i >= 1 and rosters[i - 1] is not None:
                newf = float(len([p for p in rosters[i - 1] if p not in seen_lag]))
            else:
                newf = np.nan
            five_tenure = float(five_run) if i >= 1 else np.nan
            five_new = (1.0 if (i >= 2 and fives[i - 1] is not None and fives[i - 2] is not None
                                and fives[i - 1] != fives[i - 2]) else
                        (0.0 if i >= 2 else np.nan))
            rows.append((s, t, g["game_id"].iloc[i], tm_game_idx, tm_rest,
                         1.0 if tm_rest == 1 else 0.0,
                         1.0 if d3 >= 2 else 0.0, float(d7), tm_poss_mean, churn, newf,
                         five_tenure, five_new))
            # ---- advance state to include game i (used only by i+1 onward) ----
            seen_lag = set(seen)
            if rosters[i] is not None:
                seen |= rosters[i]
            if fives[i] is not None:
                if prev_five is not None and fives[i] == prev_five:
                    five_run += 1
                else:
                    five_run = 1
                prev_five = fives[i]
    T = pd.DataFrame(rows, columns=["season", "team_id", "game_id", "tm_game_idx", "tm_rest_days",
                                    "tm_b2b", "tm_3in4", "tm_games_prior7d", "tm_poss_mean_prior",
                                    "tm_roster_churn_prior", "tm_newfaces_prior",
                                    "tm_five_tenure_prior", "tm_five_changed_prior"])
    T["tm_season_progress"] = T["tm_game_idx"] / 40.0

    # opponent unfamiliarity: prior same-season meetings, strictly before this game
    mm = tg[["season", "team_id", "opp_team_id", "game_id", "gdate", "is_home"]].sort_values(
        ["season", "team_id", "opp_team_id", "gdate"])
    mm["tm_prior_meetings"] = mm.groupby(["season", "team_id", "opp_team_id"]).cumcount().astype(float)
    mm["tm_first_meeting"] = (mm["tm_prior_meetings"] == 0).astype(float)
    T = T.merge(mm[["season", "team_id", "game_id", "tm_prior_meetings", "tm_first_meeting",
                    "is_home", "opp_team_id"]], on=["season", "team_id", "game_id"], how="left")
    T["tm_is_home"] = T["is_home"].astype(float)

    # opponent's own as-of pace proxy, joined by (game_id, opponent)
    opp = T[["season", "game_id", "team_id", "tm_poss_mean_prior", "tm_rest_days",
             "tm_game_idx"]].rename(
        columns={"team_id": "opp_team_id", "tm_poss_mean_prior": "opp_poss_mean_prior",
                 "tm_rest_days": "opp_rest_days", "tm_game_idx": "opp_game_idx"})
    T = T.merge(opp, on=["season", "game_id", "opp_team_id"], how="left")
    T["tm_rest_diff"] = T["tm_rest_days"] - T["opp_rest_days"]
    return T.drop(columns=["is_home"])


def build_player_team_state(mp, T):
    """Player-vs-team-schedule state: how many team games the player has missed / games since the
    player last appeared, expressed in TEAM GAMES.  Strictly prior."""
    idx = T[["season", "team_id", "game_id", "tm_game_idx"]]
    d = mp.merge(idx, on=["season", "team_id", "game_id"], how="left")
    d = d.sort_values(["season", "player_id", "team_id", "tm_game_idx"])
    g = d.groupby(["season", "player_id", "team_id"], sort=False)
    last_ap_idx = g.apply(
        lambda x: x["tm_game_idx"].where(x["appeared"]).shift(1).ffill(), include_groups=False)
    d["_last_ap_idx"] = last_ap_idx.reset_index(level=[0, 1, 2], drop=True)
    d["pl_teamgames_since_appear"] = d["tm_game_idx"] - d["_last_ap_idx"] - 1.0
    d["_apf"] = d["appeared"].astype(float)
    d["pl_dnp_frac5"] = 1.0 - g["_apf"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=3).mean())
    return d[["game_id", "team_id", "player_id", "pl_teamgames_since_appear", "pl_dnp_frac5"]]


# ----------------------------------------------------------------------------- stats
def zwithin(v, seas):
    v = np.asarray(v, float)
    out = np.full(len(v), np.nan)
    for s in np.unique(seas):
        m = seas == s
        x = v[m]
        f = np.isfinite(x)
        if f.sum() < 5:
            continue
        mu, sd = x[f].mean(), x[f].std(ddof=1)
        out[m] = (x - mu) / (sd if sd > 0 else 1.0)
    return out


def demean_within(v, seas):
    v = np.asarray(v, float)
    out = v.copy()
    for s in np.unique(seas):
        m = seas == s
        out[m] = v[m] - v[m].mean()
    return out


def tstat(ytil, x, seas, k_extra):
    """FWL: y already demeaned within season.  x demeaned within season here.  Returns
    (beta, t, dR2) for the simple slope after season fixed effects."""
    xt = demean_within(x, seas)
    sxx = float(xt @ xt)
    if sxx <= 0:
        return np.nan, np.nan, np.nan
    sxy = float(xt @ ytil)
    beta = sxy / sxx
    sse = float(ytil @ ytil) - beta * sxy
    n = len(ytil)
    df = n - k_extra - 1
    se = np.sqrt(max(sse, 0.0) / df / sxx)
    t = beta / se if se > 0 else np.nan
    sst = float(ytil @ ytil)
    dr2 = (sst - sse) / sst if sst > 0 else np.nan
    return beta, t, dr2


def r2_plain(y, yhat):
    """D069: plain unweighted OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean."""
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    sse = float(((y - yhat) ** 2).sum())
    sst = float(((y - y.mean()) ** 2).sum())
    return 1.0 - sse / sst if sst > 0 else np.nan


# ----------------------------------------------------------------------------- permutation
def make_blocks(frame, keycols):
    """Ordered row-index blocks, one per (season, key), grouped by season."""
    df = pd.DataFrame({"i": np.arange(len(frame)),
                       "s": frame["season"].to_numpy()})
    df["k"] = list(map(tuple, frame[keycols].to_numpy()))
    df = df.sort_values(["s", "k"])
    groups = {}
    for (s, k), g in df.groupby(["s", "k"], sort=False):
        groups.setdefault(s, []).append(g["i"].to_numpy())
    return groups


def block_index(groups, n, rng):
    """Build a row->donor-row gather index.  Whole blocks of ALREADY-COMPUTED values are
    reassigned to other blocks within the same season, cycling when block lengths differ.
    Nothing is recomputed.  The same index serves every candidate in the draw, which is what
    makes the max-t family-wise correction valid."""
    idx = np.arange(n)
    for s, blocks in groups.items():
        order = rng.permutation(len(blocks))
        for i, b in enumerate(blocks):
            don = blocks[order[i]]
            idx[b] = don[np.arange(len(b)) % len(don)]
    return idx


def within_block_index(groups, n, rng):
    """WITHIN-block permutation index: values are shuffled INSIDE each (season,key) block, so the
    block's LEVEL survives and only the within-block (game-to-game) alignment is destroyed.  This
    is the correct null for a candidate whose variance is mostly WITHIN its block -- for such a
    candidate the between-block reassignment above leaves the effect almost intact and is not a
    null at all.  A candidate is only credited if it beats BOTH."""
    idx = np.arange(n)
    for s, blocks in groups.items():
        for b in blocks:
            idx[b] = b[rng.permutation(len(b))]
    return idx


def var_share_between(v, groups, n):
    """fraction of the candidate's variance that lives BETWEEN blocks (vs within)."""
    v = np.asarray(v, float)
    tot = np.nanvar(v)
    if not np.isfinite(tot) or tot <= 0:
        return np.nan
    num = 0.0
    cnt = 0
    gm = np.nanmean(v)
    for s, blocks in groups.items():
        for b in blocks:
            x = v[b]
            x = x[np.isfinite(x)]
            if len(x) == 0:
                continue
            num += len(x) * (x.mean() - gm) ** 2
            cnt += len(x)
    return float(num / cnt / tot) if cnt else np.nan


def row_index(seas, rng):
    """The NAIVE row-level permutation index.  Reported ONLY to expose the inflation factor."""
    idx = np.arange(len(seas))
    for s in np.unique(seas):
        m = np.where(seas == s)[0]
        idx[m] = m[rng.permutation(len(m))]
    return idx
