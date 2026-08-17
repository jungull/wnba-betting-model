"""E1_I0053_minutes -- shared machinery for the dedicated MINUTES screen.

THE SHARED SCREEN KIT IS NOT IMPORTED AND NOT MODIFIED.  Nothing outside this screen's own
directory is written.  Everything needed is reimplemented here.  The within-team-game swap, the
player-series swap and the date-blocked swap follow `_screen_kit/screenkit.py` and
`E1_I0046_allocation/scripts/al_base.py` (both read-only) in intent; the anchor block in s01 is the
check that the reimplementation is faithful, and it includes EXACT reproductions of
E1_I0046's published tuned/naive minutes-share reference R2.

PARTITION.  Seasons 2021-2024 only.  2025/2026 is never read, joined, merged or described.
Enforced on VALUES.  A column is date-checked only if its dtype is genuinely datetime (K0: the word
'candi-DATE' contains 'date', and pd.to_datetime on a float silently returns 1970).

NO NAME-BASED COLUMN SELECTION anywhere.  Every column list is an explicit literal allowlist, is
printed when resolved, and has its length asserted against a literal.

RESPONSE.  Primary R1_min is the LEVEL, y_i = minutes_i, and the 200-minute team-game constraint is
therefore UNENFORCED in the RAW arm.  R2_smin is the SHARE, y_i = minutes_i / T_min(g), and is
projected inside the team-game.  Both arms are reported for every cell.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")
OUT = os.path.join(EXP, "E1_I0053_minutes")
NULLS = os.path.join(OUT, "nulls")
SCR = os.path.join(OUT, "scripts")
MP = os.path.join(ROOT, r"data\masters\master_player.parquet")
MT = os.path.join(ROOT, r"data\masters\master_team.parquet")

SEED = 20260808
N_DRAWS = 2000
ALLOWED_SEASONS = {2021, 2022, 2023, 2024}
FORBIDDEN_YEARS = (2025, 2026)
CLEAN_EVAL_SEASONS = [2023, 2024]
DISCLOSED_EVAL_SEASONS = [2022]

# ---------------------------------------------------------------- EXPLICIT LITERAL ALLOWLISTS
RESPONSES = ["R1_min", "R2_smin"]

# candidates that vary WITHIN the team-game  -> nulls N_TGSWAP (primary) and N_PSWAP (secondary)
WITHIN_TG_CANDIDATES = ["C1_player_rest", "C2_foul_rate", "C3_blowout_adj", "C4_min_volatility",
                        "C5_starter_delta"]
# candidates CONSTANT within the team-game  -> null N_TGBLOCK (same-date team-game permutation)
TG_CONSTANT_CANDIDATES = ["C6_team_rest", "C7_sched_density", "C8_opp_pace_prior"]
CONTROLS = ["G01_noise", "G02_tg_noise"]
REAL_CANDIDATES = WITHIN_TG_CANDIDATES + TG_CONSTANT_CANDIDATES
CANDIDATES = REAL_CANDIDATES + CONTROLS

assert len(RESPONSES) == 2
assert len(WITHIN_TG_CANDIDATES) == 5
assert len(TG_CONSTANT_CANDIDATES) == 3
assert len(CONTROLS) == 2
assert len(REAL_CANDIDATES) == 8
assert len(CANDIDATES) == 10

H_GRID = [2, 3, 5, 8, 13, 21, 0]      # 0 == EXPANDING
K_GRID = [0.0, 0.5, 1.0, 2.0, 4.0, 8.0]
assert len(H_GRID) * len(K_GRID) == 42

MP_COLS = ["game_id", "season", "season_type", "game_date", "team_id", "opp_team_id", "is_home",
           "player_id", "minutes", "pts", "fga", "starter_flag", "pf"]
MT_COLS = ["game_id", "season", "season_type", "game_date", "team_id", "opp_team_id", "pts", "fga",
           "minutes", "opp_pts", "fta", "oreb", "tov"]
assert len(MP_COLS) == 13
assert len(MT_COLS) == 13

BLOWOUT_MARGIN = 15.0                 # |final margin| >= 15 == blowout, PRIOR games only
REST_CLIP = 21.0                      # days, both rest candidates
CANDIDATE_PRIOR_HALFLIFE = 5          # fixed, NOT tuned -- no candidate hyperparameter sees eval


def hdr(s):
    print("\n" + "=" * 108)
    print(s)
    print("=" * 108)


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")
                                     ).encode("utf-8")).hexdigest()


def prereg_sha():
    with open(os.path.join(OUT, "PREREG.md"), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def dump(name, obj):
    with open(os.path.join(SCR, "_%s.json" % name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=str)


# --------------------------------------------------------------------------- partition gate
def assert_partition(f, label="", verbose=False):
    """VALUE-level gate.  Only genuinely datetime-dtyped columns are checked; nothing is coerced."""
    if "season" in f.columns:
        bad = sorted(set(int(s) for s in pd.unique(f["season"])) - ALLOWED_SEASONS)
        assert not bad, "PARTITION VIOLATION %s: seasons %s" % (label, bad)
    checked = []
    for c in f.columns:
        s = f[c]
        if not pd.api.types.is_datetime64_any_dtype(s):
            continue
        mx = s.max()
        if pd.notna(mx):
            assert mx.year not in FORBIDDEN_YEARS and mx < pd.Timestamp("2025-01-01"), \
                "PARTITION VIOLATION %s: column %s reaches %s" % (label, c, mx)
        checked.append(c)
    if verbose:
        print("  assert_partition PASS %-18s seasons=%s datetime-gated=%s"
              % (label, sorted(set(int(s) for s in pd.unique(f["season"]))), checked))
    return True


# --------------------------------------------------------------------------- frame construction
def _ewm_prior(sr, h):
    """Strictly-prior EWMA inside an already-grouped series.  h == 0 means expanding mean."""
    x = sr.shift(1)
    if h == 0:
        return x.expanding(min_periods=1).mean()
    return x.ewm(halflife=h, adjust=True, min_periods=1).mean()


def build_frame(verbose=True):
    """Appeared-roster frame, 2021-2024 regular season, with strictly-prior features."""
    mp = pd.read_parquet(MP, columns=MP_COLS)
    mt = pd.read_parquet(MT, columns=MT_COLS)
    mp = mp[(mp["season"].isin(sorted(ALLOWED_SEASONS))) &
            (mp["season_type"] == "Regular Season")].copy()
    mt = mt[(mt["season"].isin(sorted(ALLOWED_SEASONS))) &
            (mt["season_type"] == "Regular Season")].copy()
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    mt["game_date"] = pd.to_datetime(mt["game_date"])
    for c in ["minutes", "pts", "fga", "starter_flag", "pf"]:
        mp[c] = pd.to_numeric(mp[c], errors="coerce").fillna(0.0)
    for c in ["pts", "fga", "minutes", "opp_pts", "fta", "oreb", "tov"]:
        mt[c] = pd.to_numeric(mt[c], errors="coerce").fillna(0.0)
    assert_partition(mp, "master_player", verbose)
    assert_partition(mt, "master_team", verbose)

    d = mp[mp["minutes"] > 0].copy()                       # C(g): the realised appeared roster
    d = d.sort_values(["season", "team_id", "game_date", "game_id",
                       "player_id"]).reset_index(drop=True)
    d["tg"] = d["game_id"].astype(str) + "|" + d["team_id"].astype(str)

    agg = d.groupby("tg", sort=False).agg(T_pts=("pts", "sum"), T_min=("minutes", "sum"),
                                          T_fga=("fga", "sum"), n_roster=("pts", "size"))
    mt["tg"] = mt["game_id"].astype(str) + "|" + mt["team_id"].astype(str)
    chk = pd.DataFrame({"tg": mt["tg"], "b_pts": mt["pts"].to_numpy(float),
                        "b_fga": mt["fga"].to_numpy(float),
                        "b_min": mt["minutes"].to_numpy(float)}).merge(
        agg.reset_index(), on="tg", how="inner")
    closure = dict(n_team_games_box=int(len(mt)), n_team_games_matched=int(len(chk)),
                   max_abs_diff_pts=float(np.max(np.abs(chk["T_pts"] - chk["b_pts"]))),
                   max_abs_diff_fga=float(np.max(np.abs(chk["T_fga"] - chk["b_fga"]))),
                   max_abs_diff_min=float(np.max(np.abs(chk["T_min"] - chk["b_min"]))),
                   n_nonzero_pts=int((np.abs(chk["T_pts"] - chk["b_pts"]) > 1e-9).sum()),
                   n_nonzero_fga=int((np.abs(chk["T_fga"] - chk["b_fga"]) > 1e-9).sum()),
                   mean_roster=float(chk["n_roster"].mean()),
                   mean_T_min=float(chk["T_min"].mean()))
    assert closure["n_nonzero_pts"] == 0, "CLOSURE FAILED on points: %s" % closure
    assert closure["n_nonzero_fga"] == 0, "CLOSURE FAILED on attempts: %s" % closure
    assert closure["max_abs_diff_min"] <= 0.07, "CLOSURE FAILED on minutes: %s" % closure
    if verbose:
        print("  CLOSURE  pts nonzero %d   fga nonzero %d   min max|d|=%.6f   mean roster %.4f   "
              "mean team minutes %.4f"
              % (closure["n_nonzero_pts"], closure["n_nonzero_fga"], closure["max_abs_diff_min"],
                 closure["mean_roster"], closure["mean_T_min"]))

    d = d.merge(agg.reset_index(), on="tg", how="left")

    # ---- THE RESPONSES ---------------------------------------------------------------------
    d["R1_min"] = d["minutes"].to_numpy(float)                       # LEVEL, constraint unenforced
    d["R2_smin"] = np.where(d["T_min"] > 0, d["minutes"] / d["T_min"], np.nan)   # SHARE
    ssum = d.groupby("tg", sort=False)["R2_smin"].sum()
    assert float(np.max(np.abs(ssum - 1.0))) < 1e-12, "R2_smin does not sum to 1"
    if verbose:
        print("  SIMPLEX  R2_smin sums to 1 within team-game to < 1e-12  (asserted)")

    # ---- strictly-prior PLAYER features.  Every one is a .shift(1) inside (season, player_id).
    d = d.sort_values(["season", "player_id", "game_date", "game_id"]).reset_index(drop=True)
    gp = d.groupby(["season", "player_id"], sort=False)
    d["n_prior"] = gp.cumcount().astype(float)
    d["prior5_minutes"] = gp["minutes"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    d["prior5_smin"] = gp["R2_smin"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    d["prior5_sd_minutes"] = gp["minutes"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=2).std(ddof=1))
    d["starter_rate_prior"] = gp["starter_flag"].transform(
        lambda s: s.shift(1).expanding(min_periods=1).mean())
    d["starter_rate_recent3"] = gp["starter_flag"].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    d["foul_p36_raw"] = 36.0 * d["pf"].to_numpy(float) / np.maximum(d["minutes"].to_numpy(float), 1.0)
    d["foul_rate_prior"] = gp["foul_p36_raw"].transform(
        lambda s: _ewm_prior(s, CANDIDATE_PRIOR_HALFLIFE))
    for r in RESPONSES:
        for h in H_GRID:
            d["PR__%s__h%d" % (r, h)] = gp[r].transform(lambda s, hh=h: _ewm_prior(s, hh))
    # player's own previous APPEARANCE date -> personal rest
    d["prev_appear_date"] = gp["game_date"].shift(1)
    d["C1_player_rest"] = (d["game_date"] - d["prev_appear_date"]).dt.days.astype(float)
    d["C1_player_rest"] = d["C1_player_rest"].clip(upper=REST_CLIP)

    # ---- blowout-adjusted trailing minutes -------------------------------------------------
    mt_marg = mt[["tg", "pts", "opp_pts"]].copy()
    mt_marg["blowout"] = (np.abs(mt_marg["pts"] - mt_marg["opp_pts"]) >= BLOWOUT_MARGIN).astype(float)
    d = d.merge(mt_marg[["tg", "blowout"]], on="tg", how="left")
    d["blowout"] = d["blowout"].fillna(0.0)
    d = d.sort_values(["season", "player_id", "game_date", "game_id"]).reset_index(drop=True)
    gp = d.groupby(["season", "player_id"], sort=False)
    nb_min = d["minutes"].to_numpy(float) * (1.0 - d["blowout"].to_numpy(float))
    d["_nb_min"] = nb_min
    d["_nb_flag"] = 1.0 - d["blowout"].to_numpy(float)
    cum_nb_min = gp["_nb_min"].transform(lambda s: s.shift(1).expanding(min_periods=1).sum())
    cum_nb_n = gp["_nb_flag"].transform(lambda s: s.shift(1).expanding(min_periods=1).sum())
    cum_all = gp["minutes"].transform(lambda s: s.shift(1).expanding(min_periods=1).mean())
    nb_mean = np.where(cum_nb_n.to_numpy(float) > 0,
                       cum_nb_min.to_numpy(float) / np.maximum(cum_nb_n.to_numpy(float), 1.0), np.nan)
    d["C3_blowout_adj"] = nb_mean - cum_all.to_numpy(float)

    # ---- TEAM-GAME-level strictly-prior features -------------------------------------------
    d = d.sort_values(["season", "team_id", "game_date", "game_id",
                       "player_id"]).reset_index(drop=True)
    tg = d.drop_duplicates("tg")[["tg", "season", "team_id", "opp_team_id", "game_id", "game_date",
                                  "is_home", "n_roster", "T_min"]].copy()
    tg = tg.sort_values(["season", "team_id", "game_date", "game_id"]).reset_index(drop=True)
    gt = tg.groupby(["season", "team_id"], sort=False)
    tg["tg_index"] = gt.cumcount().astype(int)
    tg["n_hat"] = gt["n_roster"].transform(lambda s: s.shift(1).expanding(min_periods=1).mean())
    tg["n_hat"] = tg["n_hat"].fillna(10.0)
    tg["C6_team_rest"] = gt["game_date"].transform(lambda s: (s - s.shift(1)).dt.days).astype(float)
    tg["C6_team_rest"] = tg["C6_team_rest"].clip(upper=REST_CLIP)
    # games the team played in the STRICTLY PRIOR 7 calendar days
    dens = np.zeros(len(tg), float)
    for _, gidx in tg.groupby(["season", "team_id"], sort=False).indices.items():
        gi = np.asarray(sorted(gidx))
        dts = tg["game_date"].to_numpy()[gi].astype("datetime64[D]").astype(int)
        for a in range(len(gi)):
            dens[gi[a]] = float(np.sum((dts[:a] >= dts[a] - 7) & (dts[:a] < dts[a])))
    tg["C7_sched_density"] = dens

    # opponent prior pace proxy: opponent's own strictly-prior mean estimated possessions per game
    mt2 = mt.copy()
    mt2["poss_est"] = (mt2["fga"].to_numpy(float) + 0.44 * mt2["fta"].to_numpy(float)
                       - mt2["oreb"].to_numpy(float) + mt2["tov"].to_numpy(float))
    mt2 = mt2.sort_values(["season", "team_id", "game_date", "game_id"]).reset_index(drop=True)
    mt2["pace_prior"] = mt2.groupby(["season", "team_id"], sort=False)["poss_est"].transform(
        lambda s: s.shift(1).expanding(min_periods=1).mean())
    opp = mt2[["season", "game_id", "team_id", "pace_prior"]].rename(
        columns={"team_id": "opp_team_id", "pace_prior": "C8_opp_pace_prior"})
    tg = tg.merge(opp, on=["season", "game_id", "opp_team_id"], how="left")

    d = d.merge(tg[["tg", "tg_index", "n_hat", "C6_team_rest", "C7_sched_density",
                    "C8_opp_pace_prior"]], on="tg", how="left")

    # ---- controls, seeded ------------------------------------------------------------------
    d = d.sort_values(["season", "team_id", "game_date", "game_id",
                       "player_id"]).reset_index(drop=True)
    d["tg_code"] = pd.factorize(d["tg"], sort=True)[0]
    d["ps_code"] = pd.factorize(d["season"].astype(str) + "|" + d["player_id"].astype(str),
                                sort=True)[0]
    d["date_code"] = pd.factorize(d["game_date"], sort=True)[0]
    rng = np.random.default_rng(SEED)
    d["G01_noise"] = rng.standard_normal(len(d))
    tgn = rng.standard_normal(int(d["tg_code"].max()) + 1)
    d["G02_tg_noise"] = tgn[d["tg_code"].to_numpy()]

    d["C2_foul_rate"] = d["foul_rate_prior"]
    d["C4_min_volatility"] = d["prior5_sd_minutes"]
    d["C5_starter_delta"] = (d["starter_rate_recent3"].to_numpy(float)
                             - d["starter_rate_prior"].to_numpy(float))

    assert_partition(d, "FRAME", verbose)
    if verbose:
        print("  FRAME %d appeared player-games  team-games=%d  players=%d  seasons=%s"
              % (len(d), d["tg_code"].nunique(), d["player_id"].nunique(),
                 sorted(d["season"].unique())))
    return d, tg, closure


def add_candidate_columns(d, verbose=True):
    """Materialise the ten preregistered candidates.  EXPLICIT LITERAL list, no name matching.

    Non-finite values are imputed to the column mean (computed over the whole 2021-2024 frame --
    a constant, carrying no row-specific information, and identical in every arm and every draw).
    """
    d = d.copy()
    rep = []
    for c in CANDIDATES:
        v = pd.to_numeric(d[c], errors="coerce").to_numpy(float)
        mu = float(np.nanmean(v))
        d[c] = np.where(np.isfinite(v), v, mu)
        rep.append(dict(candidate=c, mean=float(np.mean(d[c])), sd=float(np.std(d[c], ddof=1)),
                        n_imputed=int((~np.isfinite(v)).sum())))
        if verbose:
            print("    candidate %-20s mean %+12.6f  sd %10.6f  n_imputed %5d"
                  % (c, rep[-1]["mean"], rep[-1]["sd"], rep[-1]["n_imputed"]))
    assert len([c for c in CANDIDATES if c in d.columns]) == 10, "candidate allowlist changed"
    return d, rep


def decision_mask(d):
    """D081's decision stratum, exactly as E1_I0023/s00_prereg.py defined it."""
    return (pd.to_numeric(d["n_prior"], errors="coerce").to_numpy(float) >= 8.0) & \
           (pd.to_numeric(d["prior5_minutes"], errors="coerce").to_numpy(float) >= 24.0)


# --------------------------------------------------------------------------- allocator machinery
def project_to_total(raw, tg_code, n_tg, counts, totals):
    """Rescale inside the team-game so the forecast sums to the team's realised total.

    ORACLE: it uses the realised team total and the realised roster.  Declared in DEFECTS.md.
    """
    r = np.maximum(raw, 0.0)
    s = np.bincount(tg_code, weights=r, minlength=n_tg)
    den = s[tg_code]
    fallback = totals[tg_code] / counts[tg_code]
    return np.where(den > 0, r * totals[tg_code] / np.where(den > 0, den, 1.0), fallback)


REGULATION_TEAM_MINUTES = 200.0     # 5 players x 40 minutes.  NOT the realised total: not oracle.


def shrink_target(d, resp):
    """The value a player with no history is shrunk toward.  STRICTLY PRE-GAME on both responses:
    `n_hat` is the team's own strictly-prior mean roster size and 200 is the rulebook."""
    if resp == "R1_min":
        return REGULATION_TEAM_MINUTES / d["n_hat"].to_numpy(float)
    return 1.0 / d["n_hat"].to_numpy(float)


def allocator_raw(d, resp, h, k):
    """Shrunken EWMA of the player's own earlier response values toward the shrink target."""
    pr = d["PR__%s__h%d" % (resp, h)].to_numpy(float)
    npri = d["n_prior"].to_numpy(float)
    tgt = shrink_target(d, resp)
    w = np.zeros(len(d)) if k == 0.0 else k / (k + npri)
    pr = np.where(np.isfinite(pr), pr, tgt)
    return (1.0 - w) * pr + w * tgt


def trailing5_mean_ref(d, resp):
    """The literal untuned trailing-5 ARITHMETIC mean -- the weakest honest benchmark, and on
    R1_min it is exactly `prior5_minutes`, the decision stratum's own gate variable."""
    tgt = shrink_target(d, resp)
    if resp == "R1_min":
        v = d["prior5_minutes"].to_numpy(float)
    else:
        v = d["prior5_smin"].to_numpy(float)
    return np.where(np.isfinite(v), v, tgt)


def ols(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def r2_of_forecast(y, yhat):
    sst = float(((y - y.mean()) ** 2).sum())
    return 1.0 - float(((y - yhat) ** 2).sum()) / sst


class Cell:
    """A frozen cell: identical response, row set, SST basis, weighting and base across every draw.

    The ONLY thing a null draw may change is the candidate column's VALUES.  Rows, folds, base,
    response and SST are fixed at construction.
    """

    def __init__(self, d, y, base, cand_name, cand_vals, fit_mask, score_mask, eval_seasons,
                 arm, projected, proj_totals=None):
        self.season = d["season"].to_numpy()
        self.tg_code = d["tg_code"].to_numpy()
        self.n_tg = int(self.tg_code.max()) + 1
        self.counts = np.bincount(self.tg_code, minlength=self.n_tg).astype(float)
        self.y = y
        self.base = base
        self.cand_name = cand_name
        self.cand = cand_vals
        self.fit_mask = fit_mask
        self.score_mask = score_mask
        self.eval_seasons = eval_seasons
        self.arm = arm
        self.projected = projected       # "RAW" or "PROJ"
        # per-team-game total the PROJ arm forces the forecast to sum to.  ORACLE (DEFECTS D-01).
        self.proj_totals = proj_totals

    def _fit(self, cand):
        y, b = self.y, self.base
        ys, ybs, yas, idxs, betas = [], [], [], [], []
        for s in self.eval_seasons:
            tr = self.fit_mask & (self.season < s)
            te = (self.season == s)                       # ALL roster rows: projection needs them
            sc = self.score_mask & te
            if tr.sum() < 300 or sc.sum() < 50:
                continue
            Xb_tr = np.column_stack([np.ones(int(tr.sum())), b[tr]])
            Xb_te = np.column_stack([np.ones(int(te.sum())), b[te]])
            bb = ols(Xb_tr, y[tr])
            yb_raw_te = Xb_te @ bb
            dbar = float(cand[tr].mean())
            d_tr = cand[tr] - dbar
            d_te = cand[te] - dbar
            if self.arm == "FROZEN":
                r_tr = y[tr] - Xb_tr @ bb
                dd = float(d_tr @ d_tr)
                g = float(d_tr @ r_tr) / dd if dd > 0 else 0.0
                ya_raw_te = yb_raw_te + g * d_te
                betas.append(g)
            elif self.arm == "UNFROZEN":
                Xa_tr = np.column_stack([Xb_tr, d_tr])
                Xa_te = np.column_stack([Xb_te, d_te])
                ba = ols(Xa_tr, y[tr])
                ya_raw_te = Xa_te @ ba
                betas.append(float(ba[-1]))
            else:
                raise ValueError(self.arm)
            if self.projected == "PROJ":
                tgc = self.tg_code[te]
                tot = self.proj_totals
                yb_te = project_to_total(yb_raw_te, tgc, self.n_tg, self.counts, tot)
                ya_te = project_to_total(ya_raw_te, tgc, self.n_tg, self.counts, tot)
            else:
                yb_te, ya_te = yb_raw_te, ya_raw_te
            keep = sc[te]
            ys.append(y[te][keep])
            ybs.append(yb_te[keep])
            yas.append(ya_te[keep])
            idxs.append(np.flatnonzero(sc))
        if not ys:
            return None
        yy = np.concatenate(ys)
        yb = np.concatenate(ybs)
        ya = np.concatenate(yas)
        sst = float(((yy - yy.mean()) ** 2).sum())
        sse_b = float(((yy - yb) ** 2).sum())
        sse_a = float(((yy - ya) ** 2).sum())
        return dict(dr2=(sse_b - sse_a) / sst, sst=sst, sse_base=sse_b, sse_aug=sse_a,
                    n=len(yy), beta=float(np.mean(betas)), n_folds=len(ys),
                    r2_base=1.0 - sse_b / sst, r2_aug=1.0 - sse_a / sst,
                    y=yy, yb=yb, ya=ya, idx=np.concatenate(idxs))

    def dr2(self, cand=None):
        r = self._fit(self.cand if cand is None else cand)
        return np.nan if r is None else r["dr2"]

    def full(self):
        return self._fit(self.cand)


# --------------------------------------------------------------------------- nulls
def _group_codes(df, cols):
    key = df[cols[0]].astype(str)
    for c in cols[1:]:
        key = key + "|" + df[c].astype(str)
    return pd.factorize(key, sort=True)[0]


class WithinTeamGameSwap:
    """N_TGSWAP -- permute the candidate AMONG THE PLAYERS INSIDE THE SAME TEAM-GAME.

    Tests: WHICH PLAYER IN THIS TEAM-GAME holds which candidate value.
    DOES NOT TEST the team-game LEVEL of the candidate -- that is preserved exactly.  It is the
    IDENTITY for a team-game-constant candidate and must never be used to judge one.
    """

    def __init__(self, d):
        self.codes = d["tg_code"].to_numpy()
        self.order = np.argsort(self.codes, kind="stable")
        self.n = len(self.codes)
        self.n_groups = int(self.codes.max()) + 1
        self.n_blocks = self.n_groups

    def draw_index(self, rng):
        keys = rng.random(self.n)
        perm = np.lexsort((keys, self.codes))
        pi = np.empty(self.n, np.int64)
        pi[self.order] = perm
        return pi

    def draw(self, x, rng):
        return x[self.draw_index(rng)]


class WithinDateTeamGameSwap:
    """N_TGBLOCK -- permute a TEAM-GAME-CONSTANT candidate among the team-games on the same date."""

    def __init__(self, d):
        self.tg_code = d["tg_code"].to_numpy()
        dt = d["date_code"].to_numpy()
        tg_date, tg_rows = {}, {}
        for i, t in enumerate(self.tg_code):
            tg_rows.setdefault(t, []).append(i)
            tg_date[t] = dt[i]
        by_date = {}
        for t, dd in tg_date.items():
            by_date.setdefault(dd, []).append(t)
        self.blocks = [[np.asarray(tg_rows[t]) for t in ts] for ts in by_date.values() if len(ts) > 1]
        self.n_blocks = len(self.blocks)
        self.n_groups = sum(len(b) for b in self.blocks)

    def draw_index(self, rng):
        pi = np.arange(len(self.tg_code), dtype=np.int64)
        for units in self.blocks:
            perm = rng.permutation(len(units))
            for a, b in enumerate(perm):
                pi[units[a]] = units[b][0]
        return pi

    def draw(self, x, rng):
        return x[self.draw_index(rng)]


class PlayerSeriesSwap:
    """N_PSWAP -- reassign a player's WHOLE candidate series to another player in the same
    TEAM-season, at proportional positions.  Preserves each series' serial shape exactly (the K6
    hazard one level over) and destroys only WHICH PLAYER owns it."""

    def __init__(self, df):
        codes = _group_codes(df, ["season", "player_id"])
        order = np.lexsort((df["game_id"].to_numpy(), df["game_date"].to_numpy(), codes))
        oc = codes[order]
        starts = np.flatnonzero(np.r_[True, oc[1:] != oc[:-1]])
        ends = np.r_[starts[1:], len(oc)]
        team = _group_codes(df, ["season", "team_id"])
        self.groups = [order[s:e] for s, e in zip(starts, ends)]
        self.by_team = {}
        for gi, idx in enumerate(self.groups):
            self.by_team.setdefault(int(team[idx[0]]), []).append(gi)
        self.n_groups = len(self.groups)
        self.n_blocks = len(self.by_team)
        self.n_rows = len(df)

    def draw_index(self, rng):
        pi = np.arange(self.n_rows, dtype=np.int64)
        for _, gis in self.by_team.items():
            perm = rng.permutation(len(gis))
            for a, b in enumerate(perm):
                ia, ib = self.groups[gis[a]], self.groups[gis[b]]
                na, nb = len(ia), len(ib)
                pos = (np.round(np.arange(na) / max(na - 1, 1) * max(nb - 1, 0)).astype(int)
                       if na > 1 else np.zeros(na, int))
                pi[ia] = ib[pos]
        return pi

    def draw(self, x, rng):
        return x[self.draw_index(rng)]


class WithinPlayerCyclic:
    """N_WITHIN_PLAYER -- cyclic shift inside each player-season.  CONTRAST ONLY, never a verdict.
    Present so this screen DEMONSTRATES a blind null's behaviour on its own data."""

    def __init__(self, d):
        codes = d["ps_code"].to_numpy()
        order = np.lexsort((d["game_id"].to_numpy(), d["game_date"].to_numpy(), codes))
        oc = codes[order]
        starts = np.flatnonzero(np.r_[True, oc[1:] != oc[:-1]])
        ends = np.r_[starts[1:], len(oc)]
        self.groups = [order[s:e] for s, e in zip(starts, ends)]
        self.n_groups = len(self.groups)
        self.n_blocks = self.n_groups
        self.n_rows = len(d)

    def draw_index(self, rng):
        pi = np.arange(self.n_rows, dtype=np.int64)
        for idx in self.groups:
            n = len(idx)
            kk = int(rng.integers(0, n)) if n > 1 else 0
            pi[idx] = idx[(np.arange(n) - kk) % n]
        return pi

    def draw(self, x, rng):
        return x[self.draw_index(rng)]


def run_null(cell, swapper, n_draws=N_DRAWS, seed=SEED, label=""):
    """Signed statistics only.  Absolute values are never stored.  p is the add-one estimator."""
    rng = np.random.default_rng(seed)
    x = cell.cand
    real = float(cell.dr2())
    draws = np.empty(n_draws, float)
    for i in range(n_draws):
        draws[i] = cell.dr2(swapper.draw(x, rng))
    ok = np.isfinite(draws)
    dd = draws[ok]
    mean, sd = float(dd.mean()), float(dd.std(ddof=1))
    return dict(label=label, real=real, draws=draws, n_draws=int(n_draws), n_finite=int(ok.sum()),
                null_mean=mean, null_sd=sd,
                z=(real - mean) / sd if sd > 0 else np.nan,
                p=float((1.0 + int((dd >= real).sum())) / (len(dd) + 1.0)),
                n_groups=int(getattr(swapper, "n_groups", -1)),
                n_blocks=int(getattr(swapper, "n_blocks", -1)))


def run_null_family(cells, swapper, n_draws=N_DRAWS, seed=SEED, label=""):
    """One SHARED draw stream across every cell in `cells` (D120).

    Draw i uses `default_rng(seed + i)`, so every cell sees the SAME permutation on draw i and the
    family-wise maximum is COUPLED rather than a stack of independent maxima.  Signed statistics
    only; absolute values are never stored.
    """
    names = list(cells.keys())
    real = {k: float(c.dr2()) for k, c in cells.items()}
    draws = {k: np.empty(n_draws, float) for k in names}
    for i in range(n_draws):
        pi = swapper.draw_index(np.random.default_rng(seed + i))
        for k in names:
            draws[k][i] = cells[k].dr2(cells[k].cand[pi])
    out = {}
    for k in names:
        dd = draws[k][np.isfinite(draws[k])]
        mean, sd = float(dd.mean()), float(dd.std(ddof=1))
        out[k] = dict(label="%s|%s" % (label, k), real=real[k], draws=draws[k],
                      n_draws=int(n_draws), n_finite=int(len(dd)), null_mean=mean, null_sd=sd,
                      z=(real[k] - mean) / sd if sd > 0 else np.nan,
                      p=float((1.0 + int((dd >= real[k]).sum())) / (len(dd) + 1.0)),
                      n_groups=int(getattr(swapper, "n_groups", -1)),
                      n_blocks=int(getattr(swapper, "n_blocks", -1)))
    return out


def familywise_from_stream(res, family):
    """Coupled max-z family-wise p over `family`, using the SHARED draw stream in `res`."""
    fam = [k for k in family if k in res]
    if not fam:
        return {}
    Zd = np.column_stack([(res[k]["draws"] - res[k]["null_mean"]) /
                          (res[k]["null_sd"] if res[k]["null_sd"] > 0 else np.inf) for k in fam])
    maxz = np.nanmax(Zd, axis=1)
    ok = np.isfinite(maxz)
    return {k: float((1.0 + int((maxz[ok] >= res[k]["z"]).sum())) / (int(ok.sum()) + 1.0))
            for k in fam}


def save_null(name, res, extra=None):
    """RAW, UNSTANDARDISED, SIGNED draws with full stratum keys in the filename and payload."""
    payload = dict(draws_raw_unstandardised=res["draws"],
                   observed_signed=np.array([res["real"]]),
                   null_mean=np.array([res["null_mean"]]),
                   null_sd=np.array([res["null_sd"]]),
                   n_groups=np.array([res["n_groups"]]),
                   n_blocks=np.array([res["n_blocks"]]),
                   n_draws=np.array([res["n_draws"]]),
                   label=np.array([res["label"]]))
    for k, val in (extra or {}).items():
        payload[k] = np.asarray(val)
    p = os.path.join(NULLS, name + ".npz")
    np.savez(p, **payload)
    return p


def paired_signflip(y, ya, yb, blocks, n_draws=N_DRAWS, seed=SEED):
    """Paired forecast contrast, null by sign-flipping WHOLE BLOCKS.  Exact under within-block
    exchangeability.  dR2 aggregates exactly to r2_of_forecast(y,a) - r2_of_forecast(y,b)."""
    sst = float(((y - y.mean()) ** 2).sum())
    dloss = (y - yb) ** 2 - (y - ya) ** 2          # >0 when a is better
    codes = pd.factorize(blocks, sort=True)[0]
    nb = int(codes.max()) + 1
    sums = np.bincount(codes, weights=dloss, minlength=nb)
    real = float(sums.sum()) / sst
    rng = np.random.default_rng(seed)
    draws = np.empty(n_draws, float)
    for i in range(n_draws):
        sgn = rng.integers(0, 2, nb) * 2 - 1
        draws[i] = float((sums * sgn).sum()) / sst
    mean, sd = float(draws.mean()), float(draws.std(ddof=1))
    return dict(real=real, draws=draws, null_mean=mean, null_sd=sd, n_blocks=int(nb),
                z=(real - mean) / sd if sd > 0 else np.nan,
                p=float((1.0 + int((np.abs(draws) >= abs(real)).sum())) / (len(draws) + 1.0)),
                p_min_attainable=2.0 ** (1 - nb))
