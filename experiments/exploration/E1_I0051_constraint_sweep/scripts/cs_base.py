"""E1_I0051_constraint_sweep -- shared machinery.

THE SHARED SCREEN KIT IS NOT IMPORTED AND NOT MODIFIED (sibling agents hold it open).
This module is a reimplementation.  The frame construction, the simplex projection, the
within-team-game swap, the player-series swap and the Cell class follow
`E1_I0046_allocation/scripts/al_base.py` (read-only) in intent and in detail, deliberately, so
that this screen's numbers can be ANCHORED against that screen's published numbers.  That
authorship is credited here.  Where this module departs from al_base.py it is stated inline.

PARTITION.  Seasons 2021-2024 only.  2025/2026 is never read, joined, merged or described.
Enforced on VALUES.  A column is date-checked only if its dtype is genuinely datetime.

NO NAME-BASED COLUMN SELECTION anywhere.  Every column list is an explicit literal allowlist,
printed when resolved, with its length asserted against a literal.

WHAT IS NEW HERE.  al_base.py modelled the SHARE  s_i = y_i / SUM_j y_j.  This module also
models the LEVEL  y_i  directly, and projects it onto a budget B_g that is FIXED BY THE RULES
(200 team-minutes in regulation, +25 per overtime period) rather than onto the realised total.
That distinction -- a budget fixed at a higher level versus a total that is itself the outcome --
is the whole content of this screen.
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
OUT = os.path.join(EXP, "E1_I0051_constraint_sweep")
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

# ---- programme benchmarks.  0.002057 is quoted ONLY with its audit caveat (see PREREG 9).
FLOOR_SINGLE_CELL = 0.00102          # D103, injection-verified
FLOOR_132_CELL = 0.00235             # D103, injection-verified

# ---- EXPLICIT LITERAL ALLOWLISTS
RESPONSES = ["M_level_min", "S_share_min"]
CANDIDATES = ["A1_pts_share_prior", "A2_fga_share_prior", "A3_starter_rate_prior",
              "A4_vac_x_own", "A5_opp_defrtg", "G01_noise"]
BETWEEN_PLAYER_CANDIDATES = ["A1_pts_share_prior", "A2_fga_share_prior", "A3_starter_rate_prior",
                             "A4_vac_x_own", "G01_noise"]
TG_CONSTANT_CANDIDATES = ["A5_opp_defrtg"]
REAL_CANDIDATES = ["A1_pts_share_prior", "A2_fga_share_prior", "A3_starter_rate_prior",
                   "A4_vac_x_own", "A5_opp_defrtg"]
ARMS_PROJ = ["RAW", "PROJ_BUDGET", "PROJ_ORACLE"]
assert len(RESPONSES) == 2
assert len(CANDIDATES) == 6
assert len(BETWEEN_PLAYER_CANDIDATES) == 5
assert len(TG_CONSTANT_CANDIDATES) == 1
assert len(REAL_CANDIDATES) == 5
assert len(ARMS_PROJ) == 3

H_GRID = [2, 3, 5, 8, 13, 21, 0]      # 0 == EXPANDING
K_GRID = [0.0, 0.5, 1.0, 2.0, 4.0, 8.0]
assert len(H_GRID) * len(K_GRID) == 42

MP_COLS = ["game_id", "season", "season_type", "game_date", "team_id", "opp_team_id", "is_home",
           "player_id", "minutes", "pts", "fga", "fta", "starter_flag", "possessions"]
MT_COLS = ["game_id", "season", "season_type", "team_id", "opp_team_id", "pts", "fga", "fta",
           "oreb", "tov", "minutes", "opp_pts", "is_home"]
assert len(MP_COLS) == 14
assert len(MT_COLS) == 13

# The rules budget.  200 player-minutes in regulation (5 on the floor x 40 minutes), +25 per OT.
REG_BUDGET = 200.0
OT_BUDGET = 25.0


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
    x = sr.shift(1)
    if h == 0:
        return x.expanding(min_periods=1).mean()
    return x.ewm(halflife=h, adjust=True, min_periods=1).mean()


def build_frame(verbose=True):
    """Appeared-roster frame, 2021-2024 regular season, with strictly-prior features.

    Construction follows E1_I0046_allocation/scripts/al_base.py::build_frame so that the counts
    and the closure assertions can be anchored against its published values.
    """
    mp = pd.read_parquet(MP, columns=MP_COLS)
    mt = pd.read_parquet(MT, columns=MT_COLS)
    mp = mp[(mp["season"].isin(sorted(ALLOWED_SEASONS))) &
            (mp["season_type"] == "Regular Season")].copy()
    mt = mt[(mt["season"].isin(sorted(ALLOWED_SEASONS))) &
            (mt["season_type"] == "Regular Season")].copy()
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    mp["minutes"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
    for c in ["pts", "fga", "fta", "starter_flag", "possessions"]:
        mp[c] = pd.to_numeric(mp[c], errors="coerce").fillna(0.0)
    assert_partition(mp, "master_player", verbose)
    assert_partition(mt, "master_team", verbose)

    d = mp[mp["minutes"] > 0].copy()                       # C(g): the realised appeared roster
    d = d.sort_values(["season", "team_id", "game_date", "game_id", "player_id"]
                      ).reset_index(drop=True)

    d["tg"] = d["game_id"].astype(str) + "|" + d["team_id"].astype(str)
    agg = d.groupby("tg", sort=False).agg(T_pts=("pts", "sum"), T_min=("minutes", "sum"),
                                          T_fga=("fga", "sum"), T_poss=("possessions", "sum"),
                                          n_roster=("pts", "size"))
    tgkey = mt["game_id"].astype(str) + "|" + mt["team_id"].astype(str)
    chk = pd.DataFrame({"tg": tgkey, "b_pts": mt["pts"].to_numpy(float),
                        "b_fga": mt["fga"].to_numpy(float),
                        "b_min": mt["minutes"].to_numpy(float)}).merge(
        agg.reset_index(), on="tg", how="inner")
    closure = dict(n_team_games_box=int(len(mt)), n_team_games_matched=int(len(chk)),
                   max_abs_diff_pts=float(np.max(np.abs(chk["T_pts"] - chk["b_pts"]))),
                   max_abs_diff_fga=float(np.max(np.abs(chk["T_fga"] - chk["b_fga"]))),
                   max_abs_diff_min=float(np.max(np.abs(chk["T_min"] - chk["b_min"]))),
                   n_nonzero_pts=int((np.abs(chk["T_pts"] - chk["b_pts"]) > 1e-9).sum()),
                   n_nonzero_fga=int((np.abs(chk["T_fga"] - chk["b_fga"]) > 1e-9).sum()),
                   mean_roster=float(chk["n_roster"].mean()))
    assert closure["n_nonzero_pts"] == 0, "CLOSURE FAILED on points: %s" % closure
    assert closure["n_nonzero_fga"] == 0, "CLOSURE FAILED on attempts: %s" % closure
    assert closure["max_abs_diff_min"] <= 0.07, "CLOSURE FAILED on minutes: %s" % closure
    if verbose:
        print("  CLOSURE  pts max|d|=%.12f (nonzero %d)   fga max|d|=%.12f (nonzero %d)   "
              "min max|d|=%.6f   mean roster %.4f"
              % (closure["max_abs_diff_pts"], closure["n_nonzero_pts"],
                 closure["max_abs_diff_fga"], closure["n_nonzero_fga"],
                 closure["max_abs_diff_min"], closure["mean_roster"]))

    d = d.merge(agg.reset_index(), on="tg", how="left")

    # ---- THE RULES BUDGET.  B_g = 200 + 25*n_OT, inferred from the realised team minutes by
    # rounding to the nearest multiple of 25.  This is NOT an oracle for the level of the budget:
    # 95.27% of team-games are regulation and a live forecaster would use 200.  BOTH are carried:
    #   B_rules  = 25 * round(T_min / 25)     -- the realised budget (needs to know about OT)
    #   B_live   = 200                        -- what a forecaster can actually assert before tip
    d["B_rules"] = 25.0 * np.round(d["T_min"].to_numpy(float) / 25.0)
    d["B_live"] = REG_BUDGET
    resid = d.drop_duplicates("tg")["T_min"] - d.drop_duplicates("tg")["B_rules"]
    assert float(np.max(np.abs(resid))) < 0.5, "MINUTES BUDGET LATTICE FAILED: %.6f" % \
        float(np.max(np.abs(resid)))
    if verbose:
        print("  BUDGET   T_min lands on the 25-lattice on ALL %d team-games; max residual %.6f "
              "min (minute:second rounding).  frac at exactly 200: %.6f"
              % (d["tg"].nunique(), float(np.max(np.abs(resid))),
                 float((d.drop_duplicates("tg")["B_rules"] == 200.0).mean())))

    # ---- THE RESPONSES ---------------------------------------------------------------------
    d["M_level_min"] = d["minutes"].to_numpy(float)                       # LEVEL
    d["S_share_min"] = np.where(d["T_min"] > 0, d["minutes"] / d["T_min"], np.nan)   # SHARE
    ssum = d.groupby("tg", sort=False)["S_share_min"].sum()
    assert float(np.max(np.abs(ssum - 1.0))) < 1e-12, "share does not sum to 1"
    if verbose:
        print("  SIMPLEX  S_share_min sums to 1 within team-game to < 1e-12 (asserted)")

    # ---- strictly-prior player features.  Every one is a .shift(1) inside (season, player_id).
    d = d.sort_values(["season", "player_id", "game_date", "game_id"]).reset_index(drop=True)
    gp = d.groupby(["season", "player_id"], sort=False)
    d["n_prior"] = gp.cumcount().astype(float)
    d["prior5_minutes"] = gp["minutes"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    d["starter_rate_prior"] = gp["starter_flag"].transform(
        lambda s: s.shift(1).expanding(min_periods=1).mean())
    # prior EWMAs of the player's own SHARES (needed for the candidates and for A4)
    d["_s_pts"] = np.where(d["T_pts"] > 0, d["pts"] / d["T_pts"], np.nan)
    d["_s_fga"] = np.where(d["T_fga"] > 0, d["fga"] / d["T_fga"], np.nan)
    for src, tag in ((("_s_pts"), "SPTS"), (("_s_fga"), "SFGA")):
        d["PR__%s__h5" % tag] = gp[src].transform(lambda s: _ewm_prior(s, 5))
    # prior EWMAs of the RESPONSES, over the whole (h, k) grid, for the tuned reference
    for r in RESPONSES:
        for h in H_GRID:
            d["PR__%s__h%d" % (r, h)] = gp[r].transform(lambda s, hh=h: _ewm_prior(s, hh))

    # ---- team-level strictly-prior features -------------------------------------------------
    d = d.sort_values(["season", "team_id", "game_date", "game_id", "player_id"]
                      ).reset_index(drop=True)
    tg = d.drop_duplicates("tg")[["tg", "season", "team_id", "opp_team_id", "game_id", "game_date",
                                  "is_home", "n_roster", "T_min", "B_rules"]].copy()
    tg = tg.sort_values(["season", "team_id", "game_date", "game_id"]).reset_index(drop=True)
    gt = tg.groupby(["season", "team_id"], sort=False)
    tg["tg_index"] = gt.cumcount().astype(int)
    tg["n_hat"] = gt["n_roster"].transform(lambda s: s.shift(1).expanding(min_periods=1).mean())
    tg["n_hat"] = tg["n_hat"].fillna(10.0)

    mt2 = mt.copy()
    mt2["tg"] = mt2["game_id"].astype(str) + "|" + mt2["team_id"].astype(str)
    mt2 = mt2.merge(tg[["tg", "game_date", "tg_index"]], on="tg", how="inner")
    mt2 = mt2.sort_values(["season", "team_id", "game_date", "game_id"]).reset_index(drop=True)
    mt2["def_prior"] = mt2.groupby(["season", "team_id"], sort=False)["opp_pts"].transform(
        lambda s: s.shift(1).expanding(min_periods=1).mean())
    opp = mt2[["season", "game_id", "team_id", "def_prior"]].rename(
        columns={"team_id": "opp_team_id", "def_prior": "A5_opp_defrtg"})
    tg = tg.merge(opp, on=["season", "game_id", "opp_team_id"], how="left")
    tg["A5_opp_defrtg"] = tg["A5_opp_defrtg"].fillna(
        tg.groupby("season")["A5_opp_defrtg"].transform("mean"))

    d = d.merge(tg[["tg", "tg_index", "n_hat", "A5_opp_defrtg"]], on="tg", how="left")
    d = _add_vacated(d, tg, verbose)

    d = d.sort_values(["season", "team_id", "game_date", "game_id", "player_id"]
                      ).reset_index(drop=True)
    d["G01_noise"] = np.random.default_rng(SEED).standard_normal(len(d))

    d["tg_code"] = pd.factorize(d["tg"], sort=True)[0]
    d["ps_code"] = pd.factorize(d["season"].astype(str) + "|" + d["player_id"].astype(str),
                                sort=True)[0]
    d["date_code"] = pd.factorize(d["game_date"], sort=True)[0]
    assert_partition(d, "FRAME", verbose)
    if verbose:
        print("  FRAME %d appeared player-games  team-games=%d  players=%d  seasons=%s"
              % (len(d), d["tg_code"].nunique(), d["player_id"].nunique(),
                 sorted(d["season"].unique())))
    return d, tg, closure


def _add_vacated(d, tg, verbose=True):
    """Prior POINTS share vacated by ESTABLISHED teammates who did not appear.  Strictly prior,
    given the ORACLE ROSTER.  Identical construction to al_base.py::_add_vacated."""
    base = d[["season", "team_id", "player_id", "tg", "tg_index"]].copy()
    prior_share = d["PR__SPTS__h5"].to_numpy(float)
    base["pshare"] = np.where(np.isfinite(prior_share), prior_share, 0.0)
    vac = np.zeros(len(tg), float)
    tgpos = {t: i for i, t in enumerate(tg["tg"].to_numpy())}
    for (ssn, team), grp in base.groupby(["season", "team_id"], sort=False):
        tgs = tg[(tg["season"] == ssn) & (tg["team_id"] == team)].sort_values("tg_index")
        idx_of = {int(r.tg_index): r.tg for r in tgs.itertuples()}
        n_tg = len(tgs)
        appear = {}
        for r in grp.itertuples():
            appear.setdefault(r.player_id, []).append((int(r.tg_index), float(r.pshare)))
        for t in range(n_tg):
            present = set()
            for p, lst in appear.items():
                for (ti, _sh) in lst:
                    if ti == t:
                        present.add(p)
            total = 0.0
            for p, lst in appear.items():
                if p in present:
                    continue
                prev = [(ti, sh) for (ti, sh) in lst if ti < t]
                if len(prev) < 3:
                    continue
                if t - prev[-1][0] > 5:
                    continue
                total += max(prev[-1][1], 0.0)
            vac[tgpos[idx_of[t]]] = total
    tg = tg.copy()
    tg["vacated_prior_share"] = vac
    d = d.merge(tg[["tg", "vacated_prior_share"]], on="tg", how="left")
    own = np.where(np.isfinite(d["PR__SPTS__h5"].to_numpy(float)),
                   d["PR__SPTS__h5"].to_numpy(float), 0.0)
    d["A4_vac_x_own"] = own * d["vacated_prior_share"].to_numpy(float)
    if verbose:
        print("  A4 vacated prior share: mean %.5f  sd %.5f  frac>0 %.4f"
              % (tg["vacated_prior_share"].mean(), tg["vacated_prior_share"].std(ddof=1),
                 float((tg["vacated_prior_share"] > 0).mean())))
    return d


CANDIDATE_PRIOR_HALFLIFE = 5     # fixed, NOT tuned -- no candidate hyperparameter sees an eval row


def add_candidate_columns(d, verbose=True):
    d = d.copy()
    d["A1_pts_share_prior"] = d["PR__SPTS__h5"]
    d["A2_fga_share_prior"] = d["PR__SFGA__h5"]
    d["A3_starter_rate_prior"] = d["starter_rate_prior"]
    for c in CANDIDATES:
        v = pd.to_numeric(d[c], errors="coerce").to_numpy(float)
        mu = float(np.nanmean(v))
        d[c] = np.where(np.isfinite(v), v, mu)
        if verbose:
            print("    candidate %-24s mean %+.6f  sd %.6f  n_imputed_to_mean %d"
                  % (c, float(np.mean(d[c])), float(np.std(d[c], ddof=1)),
                     int((~np.isfinite(v)).sum())))
    assert len([c for c in CANDIDATES if c in d.columns]) == 6
    return d


def decision_mask(d):
    """D081's decision stratum, exactly as E1_I0023/E1_I0043/E1_I0046 defined it."""
    return (pd.to_numeric(d["n_prior"], errors="coerce").to_numpy(float) >= 8.0) & \
           (pd.to_numeric(d["prior5_minutes"], errors="coerce").to_numpy(float) >= 24.0)


# --------------------------------------------------------------------------- allocator machinery
def project_to(raw, tg_code, n_tg, counts, budget_per_row):
    """Project a forecast so the team-game roster sums EXACTLY to `budget_per_row`.

    budget_per_row is a per-ROW array carrying that row's team-game budget (so 200, or 25*n_OT,
    or the realised total).  With budget == 1 this is exactly al_base.py::project.
    Fallback to an equal split of the budget if a team-game's raw sum is 0.
    """
    r = np.maximum(raw, 0.0)
    s = np.bincount(tg_code, weights=r, minlength=n_tg)
    den = s[tg_code]
    equal = budget_per_row / counts[tg_code]
    return np.where(den > 0, budget_per_row * r / np.where(den > 0, den, 1.0), equal)


def allocator_raw(d, resp, h, k):
    """Shrunken prior EWMA of the player's OWN earlier response.  No team information at all --
    this is the 'model the components independently' construction, which is the point."""
    pr = d["PR__%s__h%d" % (resp, h)].to_numpy(float)
    npri = d["n_prior"].to_numpy(float)
    if resp == "S_share_min":
        tgt = 1.0 / d["n_hat"].to_numpy(float)
    else:
        tgt = REG_BUDGET / d["n_hat"].to_numpy(float)
    w = np.zeros(len(d)) if k == 0.0 else k / (k + npri)
    pr = np.where(np.isfinite(pr), pr, tgt)
    return (1.0 - w) * pr + w * tgt


def ols(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def r2_of_forecast(y, yhat):
    sst = float(((y - y.mean()) ** 2).sum())
    return 1.0 - float(((y - yhat) ** 2).sum()) / sst


class Cell:
    """A frozen cell.  Identical response, row set, SST basis, weighting and base across every
    draw -- D101 implemented rather than asserted.  The ONLY thing a null draw may change is the
    candidate column's VALUES.

    `proj` is one of RAW / PROJ_BUDGET / PROJ_ORACLE.  Follows al_base.py::Cell, extended so the
    projection target can be a rules budget rather than the realised total.
    """

    def __init__(self, d, y, base, cand_name, cand_vals, fit_mask, score_mask, eval_seasons,
                 arm, proj, budget_rules, budget_live, total_realised):
        self.season = d["season"].to_numpy()
        self.tg_code = d["tg_code"].to_numpy()
        self.n_tg = int(self.tg_code.max()) + 1
        self.counts = np.bincount(self.tg_code, minlength=self.n_tg)
        self.y = y
        self.base = base
        self.cand_name = cand_name
        self.cand = cand_vals
        self.fit_mask = fit_mask
        self.score_mask = score_mask
        self.eval_seasons = eval_seasons
        self.arm = arm
        assert proj in ARMS_PROJ, proj
        self.proj = proj
        self.budget_rules = budget_rules
        self.budget_live = budget_live
        self.total_realised = total_realised

    def _target(self, te):
        if self.proj == "PROJ_BUDGET":
            return self.budget_live[te]
        if self.proj == "PROJ_ORACLE":
            return self.total_realised[te]
        return None

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
            tgt = self._target(te)
            if tgt is None:
                yb_te, ya_te = yb_raw_te, ya_raw_te
            else:
                tgc = self.tg_code[te]
                yb_te = project_to(yb_raw_te, tgc, self.n_tg, self.counts, tgt)
                ya_te = project_to(ya_raw_te, tgc, self.n_tg, self.counts, tgt)
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
    Valid for every between-player candidate; it is the IDENTITY for a team-game-constant one."""

    def __init__(self, d):
        self.codes = d["tg_code"].to_numpy()
        self.order = np.argsort(self.codes, kind="stable")
        self.n = len(self.codes)
        self.n_groups = int(self.codes.max()) + 1
        self.n_blocks = self.n_groups

    def draw(self, x, rng):
        keys = rng.random(self.n)
        perm = np.lexsort((keys, self.codes))
        out = np.empty_like(x)
        out[self.order] = x[perm]
        return out


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

    def draw(self, x, rng):
        out = x.copy()
        for units in self.blocks:
            perm = rng.permutation(len(units))
            for a, b in enumerate(perm):
                out[units[a]] = float(x[units[b]][0])
        return out


class PlayerSeriesSwap:
    """N_PSWAP -- reassign a player's WHOLE candidate series to another player in the same
    team-season, at proportional positions.  Preserves serial structure; destroys only WHICH
    PLAYER IN THE COMPOSITION owns it.  Follows al_base.py::PlayerSeriesSwap, which credits
    E0_I0016/ep_base.py::EntitySwap."""

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

    def draw(self, x, rng):
        out = x.copy()
        for _, gis in self.by_team.items():
            perm = rng.permutation(len(gis))
            for a, b in enumerate(perm):
                ia, ib = self.groups[gis[a]], self.groups[gis[b]]
                na, nb = len(ia), len(ib)
                pos = (np.round(np.arange(na) / max(na - 1, 1) * max(nb - 1, 0)).astype(int)
                       if na > 1 else np.zeros(na, int))
                out[ia] = x[ib][pos]
        return out


class WithinPlayerCyclic:
    """N_WITHIN_PLAYER -- cyclic shift inside each player-season.  CONTRAST ONLY, never a verdict."""

    def __init__(self, d):
        codes = d["ps_code"].to_numpy()
        order = np.lexsort((d["game_id"].to_numpy(), d["game_date"].to_numpy(), codes))
        oc = codes[order]
        starts = np.flatnonzero(np.r_[True, oc[1:] != oc[:-1]])
        ends = np.r_[starts[1:], len(oc)]
        self.groups = [order[s:e] for s, e in zip(starts, ends)]
        self.n_groups = len(self.groups)
        self.n_blocks = self.n_groups

    def draw(self, x, rng):
        out = np.empty_like(x)
        for idx in self.groups:
            kk = int(rng.integers(0, len(idx))) if len(idx) > 1 else 0
            out[idx] = np.roll(x[idx], kk)
        return out


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


def save_null(name, res, extra=None):
    """RAW, UNSTANDARDISED, SIGNED draws.  Standardising erases the null mean irrecoverably."""
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
    """Paired forecast contrast, null by sign-flipping WHOLE TEAM-GAMES."""
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
