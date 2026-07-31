"""features/common.py — shared data context + helpers for player_feature_screen_v1.

QUARANTINE IS ABSOLUTE: every loader in this module filters to season <= 2024
BEFORE the frame enters memory-resident state, and asserts
max(game_date) < 2025-01-01. The 2025 and 2026 seasons are never loaded by
any code path in this package.

Shift discipline (HANDOFF §3 rules 1/3, registration features_desc):
  * every performance TREND is a post-value computed on played rows, then
    converted to an as-of value via groupby(player_id, season).shift(1)
    (played-frame rows: shift(1) == value entering this game);
  * SCHEDULE FACTS (venue, date, rest, tip hour, opponent identity, ref crew,
    meeting number, trip position) are known before tip-off and attach
    unshifted — they are not trends;
  * within-season trend features reset per season; the cross-season identity
    family (I) and career features (#19, #78) use strictly-prior information
    across seasons by construction (shift within player over the full
    career ordering) — the honest reading of "reset per season" for a family
    whose entire point is cross-season memory (documented in REPORT.md);
  * trades follow the player: all player groupings are (player_id, season)
    or (player_id,), never (player_id, team_id).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
CACHE = REPO / "experiments" / "feature_screen" / "cache"

QUARANTINE_CUTOFF = pd.Timestamp("2025-01-01")
SCREEN_SEASONS = [2021, 2022, 2023, 2024]
TRAIN_SEASONS = [2021, 2022, 2023]
VAL_SEASON = 2024

CHANNELS = ["fg3", "paint", "ft", "np2"]
TEAM_ALPHA = 0.10          # a-priori constant for team/opponent/ref context EWMAs
                           # (constitution rule 3 range; fixed, not swept — the
                           # sweep clause is applied to the candidate's own core
                           # player-trend EWMA, documented in REPORT.md)
FAST_ALPHA = 0.40          # fixed fast/slow pair for gap features (#36 family)
SLOW_ALPHA = 0.05

# venue timezone offsets vs ET during the WNBA season (summer, DST):
# PHO is MST year-round = PDT in summer = -3.
TZ_OFFSET = {
    "ATL": 0, "CON": 0, "IND": 0, "NYL": 0, "WAS": 0,
    "CHI": -1, "DAL": -1, "MIN": -1,
    "LAS": -3, "LVA": -3, "PHO": -3, "SEA": -3,
    # post-2024 franchises never appear in the screening window; mapped for safety
    "GSV": -3, "TOR": 0, "POR": -3,
}


class QuarantineError(RuntimeError):
    pass


class Candidate:
    """One catalogued candidate feature.

    build(ctx, alpha) -> pd.Series aligned to ctx.P.index (same value used for
    every screened channel) OR dict {channel: Series} for channel-specific
    values. `alpha` is honored only when alpha_swept (sweep on inner folds
    only; frozen before 2024 is touched). `sweep_grid` overrides the default
    alpha grid (used by #92, whose swept parameter is a blend weight).
    interaction_with_baseline: adds a baseline*feature column per the
    registration's interaction clause — the catalog defines no baseline
    interactions, so it is False for every candidate (documented).
    """

    def __init__(self, num, name, family, build, alpha_swept=False,
                 channels=None, interaction_with_baseline=False,
                 sweep_grid=None, note=""):
        self.num = num
        self.name = name
        self.family = family
        self.build = build
        self.alpha_swept = alpha_swept
        self.channels = channels or list(CHANNELS)
        self.interaction_with_baseline = interaction_with_baseline
        self.sweep_grid = sweep_grid
        self.note = note

    @property
    def meta(self):
        return {"name": self.name, "family": self.family,
                "catalog_number": self.num, "alpha_swept": self.alpha_swept,
                "interaction_with_baseline": self.interaction_with_baseline}


def assert_quarantine(dates, label: str, audit: list | None = None):
    """Assert max(game_date) < 2025-01-01 for any assembled matrix / source."""
    d = pd.to_datetime(pd.Series(dates).dropna())
    if len(d) == 0:
        raise QuarantineError(f"{label}: empty date vector — cannot certify quarantine")
    mx, mn = d.max(), d.min()
    ok = mx < QUARANTINE_CUTOFF
    if audit is not None:
        audit.append({"matrix": label, "n": int(len(d)),
                      "min_date": str(mn.date()), "max_date": str(mx.date()),
                      "cutoff": str(QUARANTINE_CUTOFF.date()), "pass": bool(ok)})
    if not ok:
        raise QuarantineError(
            f"QUARANTINE VIOLATION in {label}: max(game_date)={mx.date()} >= "
            f"{QUARANTINE_CUTOFF.date()}. The screening path refuses to continue.")
    return True


# ---------------------------------------------------------------------------
# grouped trend helpers (all on the played frame P, aligned to P.index)
# ---------------------------------------------------------------------------

def read_parquet_screen_seasons(path, columns=None) -> pd.DataFrame:
    """Read a parquet with a season<=2024 pushdown filter regardless of the
    stored dtype of `season` (int or string) — quarantine rows never load."""
    import pyarrow.parquet as pq
    schema = pq.read_schema(path)
    t = schema.field("season").type
    if "string" in str(t):
        flt = [("season", "in", [str(s) for s in SCREEN_SEASONS])]
    else:
        flt = [("season", "<=", 2024)]
    df = pd.read_parquet(path, columns=columns, filters=flt)
    df["season"] = df["season"].astype(int)
    return df


def gps(P: pd.DataFrame):
    return [P["player_id"], P["season"]]


def post_ewm(P, s: pd.Series, alpha: float) -> pd.Series:
    return s.groupby(gps(P)).transform(lambda x: x.ewm(alpha=alpha, adjust=True).mean())


def shift_ps(P, s: pd.Series) -> pd.Series:
    return s.groupby(gps(P)).shift(1)


def sew(P, s: pd.Series, alpha: float) -> pd.Series:
    """Shifted within-(player, season) EWMA — the canonical as-of trend."""
    return shift_ps(P, post_ewm(P, s, alpha))


def sratio_ew(P, num: pd.Series, den: pd.Series, alpha: float) -> pd.Series:
    """Shifted ratio-of-EWMAs (minutes/attempt-weighted rate trend)."""
    n = post_ewm(P, num, alpha)
    d = post_ewm(P, den, alpha)
    return shift_ps(P, n / d.replace(0.0, np.nan))


def sexp_mean(P, s: pd.Series) -> pd.Series:
    return s.groupby(gps(P)).transform(lambda x: x.expanding().mean().shift(1))


def scum_ratio(P, num: pd.Series, den: pd.Series) -> pd.Series:
    cn = num.groupby(gps(P)).transform(lambda x: x.cumsum().shift(1))
    cd = den.groupby(gps(P)).transform(lambda x: x.cumsum().shift(1))
    return cn / cd.replace(0.0, np.nan)


def sroll(P, s: pd.Series, window: int, fn: str, min_periods: int = 2) -> pd.Series:
    def f(x):
        r = x.rolling(window, min_periods=min_periods)
        return getattr(r, fn)().shift(1)
    return s.groupby(gps(P)).transform(f)


def shrink(value: pd.Series, n: pd.Series, k: float, prior=0.0) -> pd.Series:
    """Empirical-Bayes style shrinkage toward `prior` with prior strength k."""
    w = n / (n + k)
    return (w * value + (1.0 - w) * prior).where(value.notna(), np.nan)


def venue_split_asof(P, s: pd.Series, alpha: float, k: float,
                     prior: float = 0.0) -> pd.Series:
    """Shrunken as-of (home EWMA − away EWMA) of a per-game stat.

    Venue-conditional post EWMAs are computed within (player, season, venue);
    the as-of value at game g is the last SAME-VENUE post value strictly before
    g (shift within venue group, then ffill along the player-season timeline).
    Shrunk toward `prior` by min(n_home, n_away)/(min+k).
    """
    out = {}
    counts = {}
    for name, home in (("h", 1), ("a", 0)):
        m = P["is_home"].astype(float).eq(home)
        v = s.where(m)
        grp = [P["player_id"], P["season"], m]
        post = v.groupby(grp).transform(
            lambda x: x.ewm(alpha=alpha, adjust=True, ignore_na=True).mean())
        post = post.where(m)  # defined on own-venue rows only
        asof = post.groupby(grp).shift(1)          # previous same-venue value
        asof = asof.groupby(gps(P)).ffill()        # carried to all later rows
        out[name] = asof
        cnt = m.astype(float).groupby(gps(P)).cumsum() - m.astype(float)
        counts[name] = cnt
    lift = out["h"] - out["a"]
    n_eff = pd.concat([counts["h"], counts["a"]], axis=1).min(axis=1)
    return shrink(lift, n_eff, k, prior)


def bucket_dev(P, bucket: pd.Series, value: pd.Series, k: float) -> pd.Series:
    """Shrunken prior-mean of `value` within (player, season, bucket) — the
    'pooled then personalized' machinery, personalized-only (shrunk to 0) so
    no fit-window pooled constant can leak across inner folds."""
    grp = [P["player_id"], P["season"], bucket]
    prior_mean = value.groupby(grp).transform(lambda x: x.expanding().mean().shift(1))
    n = pd.Series(0.0, index=P.index).groupby(grp).cumcount().astype(float)
    return shrink(prior_mean, n, k).fillna(0.0)


def bucket_ratio_dev(P, bucket: pd.Series, num: pd.Series, den: pd.Series,
                     k: float) -> pd.Series:
    """Shrunken (in-bucket cum ratio − overall cum ratio), all strictly prior."""
    grp = [P["player_id"], P["season"], bucket]
    cn = num.groupby(grp).transform(lambda x: x.cumsum().shift(1))
    cd = den.groupby(grp).transform(lambda x: x.cumsum().shift(1))
    rate_b = cn / cd.replace(0.0, np.nan)
    overall = scum_ratio(P, num, den)
    dev = rate_b - overall
    return shrink(dev, cd.fillna(0.0), k).fillna(0.0)


def league_asof_by_date(T: pd.DataFrame, col: str) -> pd.Series:
    """League expanding mean of a per-team-game stat, strictly before each
    row's date, within season. Same-date games share the same value."""
    out = pd.Series(np.nan, index=T.index)
    for season, sub in T.groupby("season"):
        day = sub.groupby("game_date")[col].agg(["sum", "count"]).sort_index()
        cs = day["sum"].cumsum().shift(1)
        cc = day["count"].cumsum().shift(1)
        lm = (cs / cc)
        out.loc[sub.index] = sub["game_date"].map(lm)
    return out


def league_asof_std_by_date(T: pd.DataFrame, col: str) -> pd.Series:
    """League expanding std of a per-team-game stat, strictly before each
    row's date, within season (NaN-ignoring)."""
    out = pd.Series(np.nan, index=T.index)
    for season, sub in T.groupby("season"):
        v = sub[col]
        day = (pd.DataFrame({"d": sub["game_date"], "s": v, "s2": v ** 2,
                             "n": v.notna().astype(float)})
               .groupby("d").sum(min_count=1).sort_index())
        cn = day["n"].cumsum().shift(1)
        cs = day["s"].cumsum().shift(1)
        cs2 = day["s2"].cumsum().shift(1)
        var = cs2 / cn - (cs / cn) ** 2
        sd = np.sqrt(var.clip(lower=0.0))
        out.loc[sub.index] = sub["game_date"].map(sd)
    return out


def center_by_date(P: pd.DataFrame, s: pd.Series) -> pd.Series:
    """Center an as-of series by the league mean of that series over rows
    STRICTLY BEFORE each row's date, within season — never over same-day or
    future rows (a same-frame expanding mean over a player-sorted frame would
    average values 'as of' later dates, leaking forward information into the
    centering constant). Early-season rows with no prior day fall back to 0
    (uncentered), which is honest 'no information yet'."""
    tmp = pd.DataFrame({"season": P["season"].values, "game_date": P["game_date"].values,
                        "v": s.values}, index=P.index)
    out = pd.Series(np.nan, index=P.index)
    for season, sub in tmp.groupby("season"):
        v = sub["v"]
        day = (pd.DataFrame({"d": sub["game_date"], "s": v,
                             "n": v.notna().astype(float)})
               .groupby("d").sum(min_count=1).sort_index())
        cs = day["s"].cumsum().shift(1)
        cn = day["n"].cumsum().shift(1)
        m = cs / cn
        out.loc[sub.index] = sub["game_date"].map(m)
    return (s - out).where(out.notna(), s - 0.0)


# ---------------------------------------------------------------------------
# the data context
# ---------------------------------------------------------------------------

class Ctx:
    """Lazily builds and caches every source table the candidates need.

    Everything is quarantine-filtered at load; every derived table's dates are
    re-asserted. `self.audit` accumulates the matrix-quarantine audit rows.
    """

    def __init__(self):
        CACHE.mkdir(parents=True, exist_ok=True)
        self.audit: list[dict] = []
        self._cache: dict[str, object] = {}
        self.P = self._build_played()
        self.baselines: dict[str, pd.Series] = {}   # frozen per-channel as-of baselines (set by harness)
        self.baseline_alphas: dict[str, float] = {}

    # -- core played frame ---------------------------------------------------
    def _build_played(self) -> pd.DataFrame:
        df = read_parquet_screen_seasons(
            DATA / "masters" / "master_player.parquet")   # 2025/2026 rows never read
        df = df[df["season_type"] == "Regular Season"].copy()
        df["game_date"] = pd.to_datetime(df["game_date"])
        assert_quarantine(df["game_date"], "master_player[RS<=2024]", self.audit)
        P = df[df["minutes"].fillna(0) > 0].copy()
        for c in ["fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb",
                  "ast", "stl", "blk", "tov", "pf", "pts", "plus_minus",
                  "points_paint", "points_fast_break", "points_second_chance",
                  "starter_flag", "is_home", "team_id", "opp_team_id",
                  "player_id", "fouls_drawn"]:
            P[c] = P[c].astype(float) if c not in ("team_id", "opp_team_id", "player_id") else P[c].astype(np.int64)
        P = P.sort_values(["player_id", "season", "game_date", "game_id"],
                          kind="mergesort").reset_index(drop=True)
        # channel points (box identity verified: np2 >= 0 and even on all rows)
        P["cp_fg3"] = 3.0 * P["fg3m"]
        P["cp_paint"] = P["points_paint"]
        P["cp_ft"] = P["ftm"]
        P["cp_np2"] = P["pts"] - P["cp_fg3"] - P["cp_ft"] - P["cp_paint"]
        bad = int((P["cp_np2"] < 0).sum())
        if bad:
            raise RuntimeError(f"channel identity violated on {bad} rows")
        for ch in CHANNELS:
            P[f"r_{ch}"] = P[f"cp_{ch}"] / P["minutes"] * 36.0
        # usage proxy (box; usage_percentage column not used — proxy is
        # always defined and identically derived across seasons)
        P["usage_raw"] = P["fga"] + 0.44 * P["fta"] + P["tov"]
        P["usage36"] = P["usage_raw"] / P["minutes"] * 36.0
        P["ts_denom"] = 2.0 * (P["fga"] + 0.44 * P["fta"])
        P["prior_apps"] = P.groupby(["player_id", "season"]).cumcount()
        # player days rest (vs own previous played game)
        P["days_rest_player"] = (
            P.groupby(["player_id", "season"])["game_date"].diff().dt.days
            .astype(float).clip(upper=10))
        P["rest_bucket"] = pd.cut(P["days_rest_player"],
                                  [-1, 1, 2, 100], labels=["le1", "2", "ge3"])
        P["rest_bucket"] = P["rest_bucket"].astype(object).fillna("first")
        return P

    # -- generic cache -------------------------------------------------------
    def _memo(self, key: str, builder):
        if key not in self._cache:
            self._cache[key] = builder()
        return self._cache[key]

    @property
    def games(self) -> set:
        return self._memo("games", lambda: set(self.P["game_id"].unique()))

    def game_dates(self) -> pd.DataFrame:
        def b():
            g = self.P.groupby("game_id").agg(
                game_date=("game_date", "first"), season=("season", "first")).reset_index()
            return g
        return self._memo("game_dates", b)

    # -- team frame + traits -------------------------------------------------
    def team(self) -> pd.DataFrame:
        def build():
            mt = read_parquet_screen_seasons(DATA / "masters" / "master_team.parquet")
            mt = mt[mt["season_type"] == "Regular Season"].copy()
            mt["game_date"] = pd.to_datetime(mt["game_date"])
            assert_quarantine(mt["game_date"], "master_team[RS<=2024]", self.audit)
            for c in mt.columns:
                if mt[c].dtype.name == "Int64":
                    mt[c] = mt[c].astype(float)
            mt["team_id"] = mt["team_id"].astype(np.int64)
            mt["opp_team_id"] = mt["opp_team_id"].astype(np.int64)
            T = mt.sort_values(["team_id", "season", "game_date", "game_id"],
                               kind="mergesort").reset_index(drop=True)
            gt = lambda s: s.groupby([T["team_id"], T["season"]])  # noqa: E731

            def tsew(col, alpha=TEAM_ALPHA):
                return gt(T[col]).transform(
                    lambda x: x.ewm(alpha=alpha, adjust=True).mean().shift(1))

            T["team_gp"] = gt(T["game_id"]).cumcount().astype(float)
            T["rest"] = gt(T["game_date"]).transform(lambda s: s.diff().dt.days).astype(float).clip(upper=10)
            T["b2b"] = (T["rest"] <= 1).astype(float)
            # games in prior 14 / 5 days (count strictly-before games)
            for win, name in ((14, "g14"), (5, "g5")):
                vals = np.zeros(len(T))
                for _, idx in T.groupby(["team_id", "season"]).groups.items():
                    d = T.loc[idx, "game_date"].to_numpy(dtype="datetime64[D]")
                    lo = np.searchsorted(d, d - np.timedelta64(win, "D"))
                    hi = np.arange(len(d))
                    vals[T.index.get_indexer(idx)] = hi - lo
                T[name] = vals
            T["dense3in5"] = (T["g5"] >= 2).astype(float)   # 3rd+ game in 5 days
            # venue-run position (schedule fact): nth consecutive same-venue game
            run = (T["is_home"] != gt(T["is_home"]).shift(1)).astype(int)
            runid = run.groupby([T["team_id"], T["season"]]).cumsum()
            T["venue_run_pos"] = T.groupby([T["team_id"], T["season"], runid]).cumcount().astype(float) + 1.0
            # meeting number vs this opponent this season
            T["meeting_no"] = T.groupby([T["team_id"], T["season"], T["opp_team_id"]]).cumcount().astype(float) + 1.0
            # post-break flag: first 3 team games after the season's longest league gap
            T["post_break"] = 0.0
            for season, sub in T.groupby("season"):
                days = np.sort(sub["game_date"].unique())
                gaps = np.diff(days).astype("timedelta64[D]").astype(int)
                if len(gaps) == 0 or gaps.max() < 6:
                    continue
                break_end = days[int(np.argmax(gaps)) + 1]
                m = sub["game_date"] >= break_end
                order_after = sub[m].groupby("team_id").cumcount()
                idx = sub[m].index[order_after < 3]
                T.loc[idx, "post_break"] = 1.0
            T["wins"] = (T["wl"] == "W").astype(float)
            cw = gt(T["wins"]).transform(lambda s: s.cumsum().shift(1))
            cg = gt(T["wins"]).cumcount().astype(float)
            T["winpct_asof"] = (cw / cg.replace(0, np.nan)).fillna(0.5)
            T["season_frac"] = cg / gt(T["game_id"]).transform("size").astype(float)
            # trait EWMAs (shifted within team-season, alpha 0.10)
            T["net_sew"] = tsew("plus_minus")
            T["ptsallow_sew"] = tsew("opp_pts")
            T["fg3a_allow_sew"] = tsew("opp_fg3a")
            T["blk_sew"] = tsew("blk")
            T["pf_sew"] = tsew("pf")
            T["opp_tov_sew"] = tsew("opp_tov")          # turnovers forced
            T["fballow_sew"] = tsew("opp_points_fast_break")
            T["fg3a_fast"] = gt(T["fg3a"]).transform(lambda x: x.ewm(alpha=FAST_ALPHA, adjust=True).mean().shift(1))
            T["fg3a_slow"] = gt(T["fg3a"]).transform(lambda x: x.ewm(alpha=SLOW_ALPHA, adjust=True).mean().shift(1))
            T["astrate_sew"] = gt(T["ast"] / T["fgm"].replace(0, np.nan)).transform(
                lambda x: x.ewm(alpha=TEAM_ALPHA, adjust=True).mean().shift(1))
            # opponent DREB% (their dreb vs our oreb): per game from own row
            T["opp_drebpct"] = T["opp_dreb"] / (T["opp_dreb"] + T["oreb"]).replace(0, np.nan)
            T["opp_drebpct_sew"] = gt(T["opp_drebpct"]).transform(
                lambda x: x.ewm(alpha=TEAM_ALPHA, adjust=True).mean().shift(1))
            # 3P% allowed volatility (rolling std, shifted)
            T["fg3pct_allow_std"] = gt(T["opp_fg3_pct"]).transform(
                lambda x: x.rolling(10, min_periods=4).std().shift(1))
            # allowed channel shares (drift, fast − slow)
            T["al_fg3"] = 3.0 * T["opp_fg3m"]
            T["al_ft"] = T["opp_ftm"]
            T["al_paint"] = T["opp_points_paint"]
            T["al_np2"] = T["opp_pts"] - T["al_fg3"] - T["al_ft"] - T["al_paint"]
            for ch in CHANNELS:
                share = T[f"al_{ch}"] / T["opp_pts"].replace(0, np.nan)
                fast = share.groupby([T["team_id"], T["season"]]).transform(
                    lambda x: x.ewm(alpha=FAST_ALPHA, adjust=True).mean().shift(1))
                slow = share.groupby([T["team_id"], T["season"]]).transform(
                    lambda x: x.ewm(alpha=SLOW_ALPHA, adjust=True).mean().shift(1))
                T[f"al_drift_{ch}"] = fast - slow
            # rotation traits from played box rows
            pb = self.P.groupby(["game_id", "team_id"]).apply(
                lambda x: pd.Series({
                    "bench_share": x.loc[x["starter_flag"] == 0, "minutes"].sum() / x["minutes"].sum(),
                    "n_rotation": float((x["minutes"] >= 10).sum())}),
                include_groups=False).reset_index()
            T = T.merge(pb, on=["game_id", "team_id"], how="left", validate="1:1")
            gt2 = lambda s: s.groupby([T["team_id"], T["season"]])  # noqa: E731
            T["bench_share_sew"] = gt2(T["bench_share"]).transform(
                lambda x: x.ewm(alpha=TEAM_ALPHA, adjust=True).mean().shift(1))
            T["n_rotation_sew"] = gt2(T["n_rotation"]).transform(
                lambda x: x.ewm(alpha=TEAM_ALPHA, adjust=True).mean().shift(1))
            # pace from possessions counts
            poss = self.poss()
            pc = poss.groupby(["game_id", "offense_team_id"]).size().rename("n_off_poss").reset_index()
            pc = pc.rename(columns={"offense_team_id": "team_id"})
            T = T.merge(pc, on=["game_id", "team_id"], how="left", validate="1:1")
            T["pace_sew"] = gt2(T["n_off_poss"]).transform(
                lambda x: x.ewm(alpha=TEAM_ALPHA, adjust=True).mean().shift(1))
            # league-centered versions of product ingredients: subtract the
            # strictly-prior league mean of the underlying per-game stat
            center_base = {"ptsallow_sew": "opp_pts", "fg3a_allow_sew": "opp_fg3a",
                           "blk_sew": "blk", "pf_sew": "pf", "opp_tov_sew": "opp_tov",
                           "fballow_sew": "opp_points_fast_break",
                           "opp_drebpct_sew": "opp_drebpct", "pace_sew": "n_off_poss",
                           "bench_share_sew": "bench_share",
                           "n_rotation_sew": "n_rotation"}
            T["_astrate_g"] = T["ast"] / T["fgm"].replace(0, np.nan)
            center_base["astrate_sew"] = "_astrate_g"
            for col, base_col in center_base.items():
                T[f"{col}_c"] = T[col] - league_asof_by_date(T, base_col)
            # volatility trait: center by strictly-prior-by-date league mean
            # of the as-of std values themselves
            T["fg3pct_allow_std_c"] = (T["fg3pct_allow_std"]
                                       - league_asof_by_date(T, "fg3pct_allow_std"))
            # terciles of opponent-relevant traits via strictly-prior-date z
            for col in ["ptsallow_sew", "pace_sew"]:
                lg_mean = league_asof_by_date(T, {"ptsallow_sew": "opp_pts",
                                                  "pace_sew": "n_off_poss"}[col])
                dev = T[col] - lg_mean
                sd = league_asof_std_by_date(T, col)
                z = dev / sd.replace(0, np.nan)
                T[f"{col}_bucket"] = pd.cut(z, [-np.inf, -0.43, 0.43, np.inf],
                                            labels=["lo", "mid", "hi"]).astype(object)
                T[f"{col}_bucket"] = T[f"{col}_bucket"].fillna("mid")
            return T
        return self._memo("team", build)

    def team_cols_on_P(self, cols: list[str], opp: bool = False) -> pd.DataFrame:
        """Merge team-trait columns onto P rows (own team or opponent)."""
        T = self.team()
        key_team = "opp_team_id" if opp else "team_id"
        sub = T[["game_id", "team_id"] + cols].rename(
            columns={"team_id": key_team, **{c: (f"o_{c}" if opp else f"t_{c}") for c in cols}})
        out = self.P[["game_id", key_team]].merge(
            sub, on=["game_id", key_team], how="left", validate="m:1")
        out.index = self.P.index
        return out[[(f"o_{c}" if opp else f"t_{c}") for c in cols]]

    # -- possessions ---------------------------------------------------------
    def poss(self) -> pd.DataFrame:
        def build():
            p = read_parquet_screen_seasons(DATA / "possessions" / "possessions.parquet")
            p = p[p["season_type"] == "Regular Season"].copy()
            p = p[p["game_id"].isin(self.games)].reset_index(drop=True)
            gd = self.game_dates()
            assert_quarantine(gd.loc[gd["game_id"].isin(p["game_id"].unique()), "game_date"],
                              "possessions[RS<=2024]", self.audit)
            p["uid"] = np.arange(len(p))
            p["margin"] = (p["home_pts_before"] - p["away_pts_before"]).abs()
            p["garbage"] = (p["margin"] >= 15).astype(float)
            # start_sec/end_sec are CUMULATIVE game seconds (P1 0-600, P4
            # 1800-2400, OT beyond) — closing = last 5 min of P4 (>=2100) or OT
            p["closing"] = ((((p["period"] == 4) & (p["start_sec"] >= 2100.0)) |
                             (p["period"] >= 5)) & (p["margin"] <= 5)).astype(float)
            return p
        return self._memo("poss", build)

    def presence(self) -> pd.DataFrame:
        """Long (uid x on-court player) frame with side and possession flags."""
        def build():
            p = self.poss()
            frames = []
            for side, tcol, pcols in (("off", "offense_team_id", [f"off_p{i}" for i in range(1, 6)]),
                                      ("def", "defense_team_id", [f"def_p{i}" for i in range(1, 6)])):
                sub = p[["game_id", "uid", tcol, "points_scored", "duration_sec",
                         "garbage", "closing", "period"] + pcols].copy()
                sub = sub.melt(id_vars=["game_id", "uid", tcol, "points_scored",
                                        "duration_sec", "garbage", "closing", "period"],
                               value_vars=pcols, value_name="player_id").drop(columns="variable")
                sub = sub.rename(columns={tcol: "team_id"})
                sub["side"] = side
                frames.append(sub)
            L = pd.concat(frames, ignore_index=True)
            L = L[L["player_id"].notna()]
            L["player_id"] = L["player_id"].astype(np.int64)
            # per-possession-side starter counts
            st = pd.read_csv(DATA / "derived" / "starters.csv")
            st = st[st["GAME_ID"].astype(str).isin(self.games)]
            st = st.rename(columns={"GAME_ID": "game_id", "TEAM_ID": "team_id",
                                    "PLAYER_ID": "player_id"})
            st["game_id"] = st["game_id"].astype(str)
            L = L.merge(st[["game_id", "team_id", "player_id", "period1_starter"]],
                        on=["game_id", "team_id", "player_id"], how="left")
            L["period1_starter"] = L["period1_starter"].fillna(0).astype(float)
            L["n_starters_side"] = L.groupby(["uid", "side"])["period1_starter"].transform("sum")
            return L
        return self._memo("presence", build)

    def pgposs(self) -> pd.DataFrame:
        """Per (game_id, player_id) possession aggregates."""
        def build():
            f = CACHE / "pgposs.parquet"
            if f.exists():
                out = pd.read_parquet(f)
            else:
                L = self.presence()
                own_start_excl_self = L["n_starters_side"] - L["period1_starter"]
                # opponent side's starter count for each row
                per_uid = L.groupby(["uid", "side"])["period1_starter"].sum().unstack(fill_value=0.0)
                opp_map = pd.DataFrame({
                    "off": per_uid.get("def", 0.0), "def": per_uid.get("off", 0.0)})
                opp_long = opp_map.stack().rename("opp_starters").reset_index()
                opp_long.columns = ["uid", "side", "opp_starters"]
                L = L.merge(opp_long, on=["uid", "side"], how="left")
                L["with3own"] = (own_start_excl_self >= 3).astype(float)
                L["vs3opp"] = (L["opp_starters"] >= 3).astype(float)
                L["is_off"] = (L["side"] == "off").astype(float)
                L["off_pts"] = L["points_scored"] * L["is_off"]
                L["def_pts"] = L["points_scored"] * (1.0 - L["is_off"])
                out = L.groupby(["game_id", "team_id", "player_id"]).agg(
                    n_on=("uid", "size"), dur_on=("duration_sec", "sum"),
                    n_off_on=("is_off", "sum"), off_pts_on=("off_pts", "sum"),
                    def_pts_on=("def_pts", "sum"),
                    n_garb_on=("garbage", "sum"),
                    dur_garb_on=("duration_sec", lambda s: 0.0),  # placeholder, set below
                    n_with3own=("with3own", "sum"), n_vs3opp=("vs3opp", "sum"),
                    n_closing_on=("closing", "sum")).reset_index()
                dg = (L.assign(dg=L["duration_sec"] * L["garbage"])
                      .groupby(["game_id", "team_id", "player_id"])["dg"].sum().reset_index())
                out = out.drop(columns=["dur_garb_on"]).merge(
                    dg.rename(columns={"dg": "dur_garb_on"}),
                    on=["game_id", "team_id", "player_id"], how="left")
                p = self.poss()
                gtot = p.groupby("game_id").agg(
                    n_game_poss=("uid", "size"), game_dur=("duration_sec", "sum"),
                    n_game_closing=("closing", "sum"),
                    game_garb_dur=("duration_sec", lambda s: 0.0)).reset_index()
                gg = (p.assign(x=p["duration_sec"] * p["garbage"])
                      .groupby("game_id")["x"].sum().reset_index().rename(columns={"x": "game_garb_dur"}))
                gtot = gtot.drop(columns=["game_garb_dur"]).merge(gg, on="game_id")
                out = out.merge(gtot, on="game_id", how="left")
                out.to_parquet(f, index=False)
            gd = self.game_dates()
            assert_quarantine(gd.loc[gd["game_id"].isin(out["game_id"].unique()), "game_date"],
                              "pgposs", self.audit)
            return out
        return self._memo("pgposs", build)

    def pgposs_on_P(self, cols: list[str]) -> pd.DataFrame:
        pg = self.pgposs()
        out = self.P[["game_id", "player_id"]].merge(
            pg[["game_id", "player_id"] + cols], on=["game_id", "player_id"],
            how="left", validate="1:1")
        out.index = self.P.index
        return out[cols]

    def pairs(self) -> pd.DataFrame:
        """Per (game_id, team_id, p1, p2) same-team shared-possession counts."""
        def build():
            f = CACHE / "pairs_game.parquet"
            if f.exists():
                pr = pd.read_parquet(f)
            else:
                L = self.presence()[["game_id", "uid", "team_id", "player_id",
                                     "side", "points_scored"]].copy()
                a = L.rename(columns={"player_id": "p1"})
                b = L[["uid", "team_id", "player_id"]].rename(columns={"player_id": "p2"})
                m = a.merge(b, on=["uid", "team_id"])
                m = m[m["p1"] != m["p2"]]
                m["is_off"] = (m["side"] == "off").astype(np.float32)
                m["off_pts"] = m["points_scored"].astype(np.float32) * m["is_off"]
                pr = m.groupby(["game_id", "team_id", "p1", "p2"]).agg(
                    n_shared=("uid", "size"), n_off_shared=("is_off", "sum"),
                    off_pts_shared=("off_pts", "sum")).reset_index()
                pr.to_parquet(f, index=False)
            return pr
        return self._memo("pairs", build)

    # -- shots ---------------------------------------------------------------
    def shots(self) -> pd.DataFrame:
        def build():
            f = CACHE / "shots_joined.parquet"
            if f.exists():
                s = pd.read_parquet(f)
            else:
                frames = []
                for yr in SCREEN_SEASONS:
                    d = pd.read_parquet(DATA / "shotcharts" / f"shots_{yr}_regular.parquet")
                    d["season"] = yr
                    frames.append(d)
                s = pd.concat(frames, ignore_index=True)
                s = s[s["GAME_ID"].astype(str).isin(self.games)].copy()
                s["game_id"] = s["GAME_ID"].astype(str)
                s["player_id"] = s["PLAYER_ID"].astype(np.int64)
                s["game_date"] = pd.to_datetime(s["GAME_DATE"], format="%Y%m%d")
                # CUMULATIVE game seconds, matching the possessions clock
                clock = s["MINUTES_REMAINING"] * 60.0 + s["SECONDS_REMAINING"]
                s["elapsed"] = np.where(
                    s["PERIOD"] <= 4,
                    (s["PERIOD"] - 1) * 600.0 + (600.0 - clock),
                    2400.0 + (s["PERIOD"] - 5) * 300.0 + (300.0 - clock))
                s["made"] = s["SHOT_MADE_FLAG"].astype(float)
                s["is3"] = (s["SHOT_TYPE"] == "3PT Field Goal").astype(float)
                zb = s["SHOT_ZONE_BASIC"]
                s["zone"] = np.select(
                    [zb == "Restricted Area", zb == "In The Paint (Non-RA)",
                     zb == "Mid-Range", zb.isin(["Left Corner 3", "Right Corner 3"]),
                     zb == "Above the Break 3"],
                    ["RA", "ITP", "MID", "C3", "AB3"], default="OTHER")
                s["pps_zone"] = np.where(s["is3"] == 1, 3.0, 2.0)
                # join possessions for possession age + margin at shot time
                # (merge_asof needs the on-key sorted GLOBALLY)
                p = self.poss()[["game_id", "period", "start_sec", "end_sec",
                                 "margin", "garbage", "uid"]].sort_values(
                    "start_sec", kind="mergesort")
                s = s.sort_values("elapsed", kind="mergesort")
                s = pd.merge_asof(
                    s, p.rename(columns={"period": "PERIOD"}),
                    left_on="elapsed", right_on="start_sec",
                    by=["game_id", "PERIOD"], direction="backward")
                s["poss_age"] = s["elapsed"] - s["start_sec"]
                s.loc[s["elapsed"] > s["end_sec"] + 1.0, ["poss_age", "garbage", "margin"]] = np.nan
                keep = ["game_id", "player_id", "season", "game_date", "PERIOD",
                        "elapsed", "made", "is3", "zone", "pps_zone", "poss_age",
                        "garbage", "margin", "SHOT_DISTANCE", "LOC_X"]
                s = s[keep].reset_index(drop=True)
                s.to_parquet(f, index=False)
            assert_quarantine(s["game_date"], "shots[RS 2021-24]", self.audit)
            return s
        return self._memo("shots", build)

    def shot_pg(self) -> pd.DataFrame:
        """Per (player, game) shot aggregates used by many F/D candidates."""
        def build():
            s = self.shots().copy()
            s["early"] = (s["poss_age"] <= 6.0).astype(float)
            s["late"] = (s["poss_age"] >= 20.0).astype(float)
            s["xsign"] = np.sign(s["LOC_X"]).astype(float)
            s["ra"] = (s["zone"] == "RA").astype(float)
            s["itp"] = (s["zone"] == "ITP").astype(float)
            s["mid"] = (s["zone"] == "MID").astype(float)
            s["c3"] = (s["zone"] == "C3").astype(float)
            s["ab3"] = (s["zone"] == "AB3").astype(float)
            s["garb"] = s["garbage"].fillna(0.0)
            # garbage channel points from shots
            s["g_fg3"] = 3.0 * s["made"] * s["is3"] * s["garb"]
            s["g_paint"] = 2.0 * s["made"] * (s["ra"] + s["itp"]) * s["garb"]
            s["g_np2"] = 2.0 * s["made"] * s["mid"] * s["garb"]
            # league as-of expected points by (season, zone): cum by date, shifted
            day = (s.groupby(["season", "zone", "game_date"])
                   .agg(att=("made", "size"), mk=("made", "sum"),
                        pps=("pps_zone", "first")).reset_index()
                   .sort_values(["season", "zone", "game_date"], kind="mergesort"))
            day["c_att"] = day.groupby(["season", "zone"])["att"].transform(lambda x: x.cumsum().shift(1))
            day["c_mk"] = day.groupby(["season", "zone"])["mk"].transform(lambda x: x.cumsum().shift(1))
            day["lg_xpts"] = day["pps"] * day["c_mk"] / day["c_att"]
            s = s.merge(day[["season", "zone", "game_date", "lg_xpts"]],
                        on=["season", "zone", "game_date"], how="left")
            agg = s.groupby(["player_id", "game_id"]).agg(
                fga=("made", "size"), fg3a_s=("is3", "sum"),
                ra_a=("ra", "sum"), itp_a=("itp", "sum"), mid_a=("mid", "sum"),
                c3_a=("c3", "sum"), ab3_a=("ab3", "sum"),
                ra_m=("ra", lambda x: 0.0),
                dist_sum=("SHOT_DISTANCE", "sum"), xsign_sum=("xsign", "sum"),
                early_a=("early", "sum"), late_a=("late", "sum"),
                xpts_sum=("lg_xpts", "sum"),
                g_fg3=("g_fg3", "sum"), g_paint=("g_paint", "sum"),
                g_np2=("g_np2", "sum")).reset_index()
            ram = (s.assign(x=s["ra"] * s["made"]).groupby(["player_id", "game_id"])["x"]
                   .sum().reset_index().rename(columns={"x": "ra_m"}))
            agg = agg.drop(columns=["ra_m"]).merge(ram, on=["player_id", "game_id"])
            return agg
        return self._memo("shot_pg", build)

    def shot_pg_on_P(self, cols: list[str]) -> pd.DataFrame:
        sp = self.shot_pg()
        out = self.P[["game_id", "player_id"]].merge(
            sp[["game_id", "player_id"] + cols], on=["game_id", "player_id"],
            how="left", validate="1:1")
        out.index = self.P.index
        return out[cols]

    # -- play-by-play extracts ----------------------------------------------
    def pbp(self) -> dict:
        """Per-game PBP extracts: tip hour, per-(player, game) FT/assist/foul
        aggregates, per-game crew technicals. Cached."""
        def build():
            fpg = CACHE / "pbp_player_game.parquet"
            fg = CACHE / "pbp_game.parquet"
            if fpg.exists() and fg.exists():
                return {"pg": pd.read_parquet(fpg), "game": pd.read_parquet(fg)}
            rows_pg, rows_g = [], []
            for gid in sorted(self.games):
                d = pd.read_parquet(DATA / "playbyplay" / f"pbp_{gid}.parquet",
                                    columns=["EVENTNUM", "EVENTMSGTYPE", "PERIOD",
                                             "WCTIMESTRING", "PCTIMESTRING",
                                             "SCOREMARGIN", "PLAYER1_ID", "PLAYER2_ID",
                                             "HOMEDESCRIPTION", "VISITORDESCRIPTION"])
                d = d.sort_values("EVENTNUM", kind="mergesort")
                # tip hour (ET) from first wall clock
                tip = np.nan
                wc = d["WCTIMESTRING"].dropna()
                if len(wc):
                    m = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", str(wc.iloc[0]).strip())
                    if m:
                        h = int(m.group(1)) % 12 + (12 if m.group(3) == "PM" else 0)
                        tip = h + int(m.group(2)) / 60.0
                marg = d["SCOREMARGIN"].replace("TIE", "0")
                marg = pd.to_numeric(marg, errors="coerce").ffill().fillna(0.0).abs()
                mmss = d["PCTIMESTRING"].astype(str).str.extract(r"(\d+):(\d+)")
                remain = pd.to_numeric(mmss[0], errors="coerce") * 60 + pd.to_numeric(mmss[1], errors="coerce")
                desc = d["HOMEDESCRIPTION"].fillna("") + " " + d["VISITORDESCRIPTION"].fillna("")
                per = d["PERIOD"].astype(int)
                # FT events
                ft = d[d["EVENTMSGTYPE"] == 3].copy()
                if len(ft):
                    ft_desc = desc.loc[ft.index]
                    ft["made"] = (~ft_desc.str.contains("MISS")).astype(float)
                    ft["clutch"] = ((per.loc[ft.index] >= 4) & (remain.loc[ft.index] <= 300)
                                    & (marg.loc[ft.index] <= 5)).astype(float)
                    ft["garb"] = (marg.loc[ft.index] >= 15).astype(float)
                    a = ft.groupby("PLAYER1_ID").agg(
                        fta_pbp=("made", "size"), ftm_pbp=("made", "sum"),
                        fta_cl=("clutch", "sum"),
                        ftm_cl=("made", lambda s: 0.0), g_ftm=("garb", lambda s: 0.0)).reset_index()
                    mc = (ft.assign(x=ft["made"] * ft["clutch"]).groupby("PLAYER1_ID")["x"].sum())
                    gm = (ft.assign(x=ft["made"] * ft["garb"]).groupby("PLAYER1_ID")["x"].sum())
                    a["ftm_cl"] = a["PLAYER1_ID"].map(mc).fillna(0.0)
                    a["g_ftm"] = a["PLAYER1_ID"].map(gm).fillna(0.0)
                else:
                    a = pd.DataFrame(columns=["PLAYER1_ID", "fta_pbp", "ftm_pbp",
                                              "fta_cl", "ftm_cl", "g_ftm"])
                # made FG assist tags
                mk = d[d["EVENTMSGTYPE"] == 1]
                if len(mk):
                    una = (mk["PLAYER2_ID"].fillna(0) == 0).astype(float)
                    b = pd.DataFrame({"PLAYER1_ID": mk["PLAYER1_ID"], "una": una})
                    b = b.groupby("PLAYER1_ID").agg(makes_pbp=("una", "size"),
                                                    unassisted=("una", "sum")).reset_index()
                else:
                    b = pd.DataFrame(columns=["PLAYER1_ID", "makes_pbp", "unassisted"])
                # fouls
                fo = d[d["EVENTMSGTYPE"] == 6]
                if len(fo):
                    fo_desc = desc.loc[fo.index]
                    tech = fo_desc.str.contains("T.FOUL|Technical", regex=True).astype(float)
                    c = pd.DataFrame({"PLAYER1_ID": fo["PLAYER1_ID"],
                                      "p1foul": (per.loc[fo.index] == 1).astype(float),
                                      "tech": tech})
                    c = c.groupby("PLAYER1_ID").agg(p1_fouls=("p1foul", "sum"),
                                                    tech_fouls=("tech", "sum"),
                                                    fouls_pbp=("p1foul", "size")).reset_index()
                    n_tech_game = float(tech.sum())
                else:
                    c = pd.DataFrame(columns=["PLAYER1_ID", "p1_fouls", "tech_fouls", "fouls_pbp"])
                    n_tech_game = 0.0
                m = a.merge(b, on="PLAYER1_ID", how="outer").merge(c, on="PLAYER1_ID", how="outer")
                m["game_id"] = gid
                rows_pg.append(m)
                rows_g.append({"game_id": gid, "tip_hour_et": tip, "n_tech": n_tech_game})
            pg = pd.concat(rows_pg, ignore_index=True).rename(columns={"PLAYER1_ID": "player_id"})
            pg = pg[pg["player_id"].notna() & (pg["player_id"] != 0)]
            pg["player_id"] = pg["player_id"].astype(np.int64)
            num_cols = [c for c in pg.columns if c not in ("player_id", "game_id")]
            pg[num_cols] = pg[num_cols].fillna(0.0)
            game = pd.DataFrame(rows_g)
            pg.to_parquet(fpg, index=False)
            game.to_parquet(fg, index=False)
            return {"pg": pg, "game": game}
        return self._memo("pbp", build)

    def pbp_on_P(self, cols: list[str]) -> pd.DataFrame:
        pg = self.pbp()["pg"]
        out = self.P[["game_id", "player_id"]].merge(
            pg[["game_id", "player_id"] + cols], on=["game_id", "player_id"],
            how="left", validate="1:1")
        out.index = self.P.index
        return out[cols].fillna(0.0)

    # -- officials -----------------------------------------------------------
    def crew(self) -> pd.DataFrame:
        """Per game_id: as-of crew traits (mean over the 3 refs of their
        strictly-prior expanding game-total tendencies, league-centered).
        Ref tendencies persist across seasons (refs are not players; the
        per-season reset rule applies to player trends — documented)."""
        def build():
            off = pd.read_csv(DATA / "officials_master.csv")
            off["game_id"] = off["GAME_ID"].astype(str)
            off = off[off["game_id"].isin(self.games)].copy()
            T = self.team()
            gtot = T.groupby("game_id").agg(
                tot_fta=("fta", "sum"), tot_pf=("pf", "sum"),
                game_date=("game_date", "first")).reset_index()
            poss = self.poss().groupby("game_id").size().rename("tot_poss").reset_index()
            gtot = gtot.merge(poss, on="game_id", how="left")
            gtot = gtot.merge(self.pbp()["game"][["game_id", "n_tech"]], on="game_id", how="left")
            R = off.merge(gtot, on="game_id", how="left").sort_values(
                ["OFFICIAL_ID", "game_date", "game_id"], kind="mergesort")
            for col in ["tot_fta", "tot_pf", "tot_poss", "n_tech"]:
                R[f"ref_{col}"] = R.groupby("OFFICIAL_ID")[col].transform(
                    lambda s: s.expanding().mean().shift(1))
            crew = R.groupby("game_id").agg(
                crew_fta=("ref_tot_fta", "mean"), crew_pf=("ref_tot_pf", "mean"),
                crew_pace=("ref_tot_poss", "mean"), crew_tech=("ref_n_tech", "mean"),
                game_date=("game_date", "first")).reset_index()
            # league-center by strictly-prior league mean of the game totals
            gt = gtot.sort_values("game_date", kind="mergesort").reset_index(drop=True)
            for col, name in (("tot_fta", "crew_fta"), ("tot_pf", "crew_pf"),
                              ("tot_poss", "crew_pace"), ("n_tech", "crew_tech")):
                day = gt.groupby("game_date")[col].agg(["sum", "count"]).sort_index()
                lm = (day["sum"].cumsum().shift(1) / day["count"].cumsum().shift(1))
                crew[f"{name}_c"] = crew[name] - crew["game_date"].map(lm)
            return crew
        return self._memo("crew", build)

    def crew_on_P(self, cols: list[str]) -> pd.DataFrame:
        cr = self.crew()
        out = self.P[["game_id"]].merge(cr[["game_id"] + cols], on="game_id",
                                        how="left", validate="m:1")
        out.index = self.P.index
        return out[cols]

    def officials_long(self) -> pd.DataFrame:
        def build():
            off = pd.read_csv(DATA / "officials_master.csv")
            off["game_id"] = off["GAME_ID"].astype(str)
            off = off[off["game_id"].isin(self.games)].copy()
            return off[["game_id", "OFFICIAL_ID"]]
        return self._memo("officials_long", build)

    # -- season aggregates for cross-season identity -------------------------
    def season_rates(self) -> pd.DataFrame:
        """Per (player, season): season per-36 channel rates (>=150 minutes)."""
        def build():
            g = self.P.groupby(["player_id", "season"]).agg(
                mins=("minutes", "sum"),
                **{f"s_{ch}": (f"cp_{ch}", "sum") for ch in CHANNELS}).reset_index()
            for ch in CHANNELS:
                g[f"rate_{ch}"] = np.where(g["mins"] >= 150.0,
                                           g[f"s_{ch}"] / g["mins"] * 36.0, np.nan)
            return g
        return self._memo("season_rates", build)
