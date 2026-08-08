"""E1 I0013 -- shared machinery.

Imports E0_I0013_possession_volume/pv_base.py and E0_I0012_layer3_noncollinear/base.py READ-ONLY,
then IMMEDIATELY re-points every OUT constant into THIS directory so no reused helper can write
outside our write scope.  Bytecode writing is disabled BEFORE those imports so not even a .pyc
lands in someone else's directory.

PARTITION: 2021-2024 only, enforced by base.load_player / base.load_team and re-asserted here.
R2 CONVENTION (D069): plain unweighted OLS R2 = 1 - SSE/SST with SST about the UNWEIGHTED mean.
  Declared in FINDINGS.json.  No weighted regression anywhere in this E1.
"""
import os
import sys

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

import numpy as np   # noqa: E402
import pandas as pd  # noqa: E402

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E1_I0013_tempo_redundancy")
E0 = os.path.join(ROOT, r"experiments\exploration\E0_I0013_possession_volume")
E0_12 = os.path.join(ROOT, r"experiments\exploration\E0_I0012_layer3_noncollinear")

for p in (E0, E0_12):
    if p not in sys.path:
        sys.path.insert(0, p)

import base as B       # noqa: E402  READ-ONLY
import pv_base as P    # noqa: E402  READ-ONLY

# >>> write-scope lockdown: every reused helper now points at OUR directory <<<
B.OUT = OUT
P.OUT = OUT

PARTITION = [2021, 2022, 2023, 2024]
HOLDOUT = {2025, 2026}
SEED = 20260810
NDRAW = 400

pd.set_option("display.width", 250)
np.seterr(divide="ignore", invalid="ignore")


def hdr(s):
    print("\n" + "=" * 92)
    print(s)
    print("=" * 92)


def guard(df, where):
    ss = sorted(int(x) for x in pd.unique(df["season"]))
    print("  [PARTITION] %-52s seasons=%s n=%d" % (where, ss, len(df)))
    assert set(ss) <= set(PARTITION), "PARTITION VIOLATION at %s: %s" % (where, ss)
    assert not (set(ss) & HOLDOUT), "HOLDOUT TOUCHED at %s: %s" % (where, ss)
    return df


def write(df, name):
    p = os.path.join(OUT, name)
    assert os.path.abspath(p).startswith(os.path.abspath(OUT)), "WRITE SCOPE VIOLATION %s" % p
    d = df.drop(columns=[c for c in B.BANNED_COLS if c in df.columns])
    if "season" in d.columns:
        guard(d, "pre-write " + name)
    d.to_csv(p, index=False)
    print("  wrote %s shape=%s" % (name, d.shape))


# ------------------------------------------------------------------ R2 / OLS (D069)
def r2(y, cols):
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in cols])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    sse = float(r @ r)
    sst = float(((y - y.mean()) ** 2).sum())      # UNWEIGHTED mean -- D069
    return 1.0 - sse / sst


def ols_last(y, cols):
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in cols])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(b[-1])


def prep_fast(y, basecols):
    """QR of a baseline design once; incremental R2 of any single added column is then O(np).
    Identical to E0_I0013/run_screen.py::prep_fast so reproduction is exact."""
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in basecols])
    Q, _ = np.linalg.qr(X)
    ry = y - Q @ (Q.T @ y)
    sst = float(((y - y.mean()) ** 2).sum())
    return Q, ry, sst


def incr(Q, ry, sst, m):
    m = np.asarray(m, float)
    if not np.all(np.isfinite(m)):
        m = np.where(np.isfinite(m), m, np.nanmean(m[np.isfinite(m)]))
    rm = m - Q @ (Q.T @ m)
    den = float(rm @ rm)
    if den <= 1e-12:
        return 0.0
    return float((ry @ rm) ** 2 / den) / sst


def beta_from_qr(Q, ry, m):
    """OLS coefficient on m in [baseline, m], via the FWL projection."""
    m = np.asarray(m, float)
    rm = m - Q @ (Q.T @ m)
    den = float(rm @ rm)
    return float((ry @ rm) / den) if den > 1e-12 else np.nan


def center_within(v, seas):
    """Season-demean, matching E0_I0013/run_screen.py::center_within exactly."""
    v = np.asarray(v, float)
    out = np.empty_like(v)
    for s in np.unique(seas):
        m = seas == s
        mu = np.nanmean(v[m])
        out[m] = np.where(np.isfinite(v[m]), v[m] - mu, 0.0)
    return out


def dummies(keys, drop_first=True):
    """Dense 0/1 columns for a categorical key, first level dropped (intercept is in the design)."""
    k = pd.Series(np.asarray(keys)).astype(str)
    lv = sorted(k.unique())
    if drop_first:
        lv = lv[1:]
    return [(k == v).to_numpy(float) for v in lv]


# ------------------------------------------------------------------ permutation machinery
class TeamPanel:
    """Dense (date x team) forward-filled panel of an ALREADY-COMPUTED pregame team field.

    Copied from E0_I0013/run_screen.py so the E1 reproduces the E0's cluster-level null exactly
    rather than inventing a different one.  This is NOT the no-op form: no grouping key is
    permuted and no aggregate is recomputed; only the ASSIGNMENT of a computed value to a row
    changes.
    """

    def __init__(self, teampre, field):
        self.field = field
        self.teams, self.dates, self.vals = {}, {}, {}
        for s, g in teampre.groupby("season"):
            piv = (g.pivot_table(index="gdate", columns="team_id", values=field, aggfunc="first")
                     .sort_index().ffill())
            assert piv.shape[1] == 12, "expected 12 teams in season %s, got %d" % (s, piv.shape[1])
            self.teams[s] = piv.columns.to_numpy()
            self.dates[s] = piv.index.to_numpy()
            self.vals[s] = piv.to_numpy(dtype=float)

    def bind(self, frame, keycol):
        n = len(frame)
        A = np.full((n, 12), np.nan)
        col0 = np.zeros(n, dtype=int)
        seas = frame["season"].to_numpy()
        gd = frame["gdate"].to_numpy()
        key = frame[keycol].to_numpy()
        for s in np.unique(seas):
            m = seas == s
            pos = np.searchsorted(self.dates[s], gd[m], side="right") - 1
            A[m, :] = self.vals[s][pos, :]
            tmap = {t: i for i, t in enumerate(self.teams[s])}
            col0[m] = [tmap[k] for k in key[m]]
        return A, col0, seas


def perm_team(A, col0, seas, rng):
    out = np.empty(len(col0))
    for s in np.unique(seas):
        idx = np.where(seas == s)[0]
        pm = rng.permutation(12)
        out[idx] = A[idx, pm[col0[idx]]]
    return out


def perm_rows(v, seas, rng):
    """The NAIVE row-level permutation.  Reported ONLY to expose how much too narrow the wrong
    null is.  Never used for a verdict."""
    out = np.empty(len(v))
    for s in np.unique(seas):
        idx = np.where(seas == s)[0]
        out[idx] = rng.permutation(v[idx])
    return out


class GamePerm:
    """GAME-LEVEL permutation.  exp_gposs is symmetric in the two teams, so it takes ONE value per
    game_id: the honest unit of variation is the GAME, not the row and not the team-game.  Within a
    season we permute WHICH GAME's already-computed value each game receives, then broadcast back
    to rows.  Nothing is recomputed."""

    def __init__(self, frame, valcol):
        self.seas = frame["season"].to_numpy()
        gid = frame["game_id"].to_numpy()
        self.blocks, self.gvals = {}, {}
        for s in np.unique(self.seas):
            m = self.seas == s
            gi = gid[m]
            uq, inv = np.unique(gi, return_inverse=True)
            v = pd.Series(frame[valcol].to_numpy()[m]).groupby(inv).first().to_numpy()
            self.blocks[s] = (np.where(m)[0], inv)
            self.gvals[s] = v

    def draw(self, rng):
        out = np.empty(len(self.seas))
        for s, (idx, inv) in self.blocks.items():
            v = self.gvals[s]
            out[idx] = v[rng.permutation(len(v))][inv]
        return out


def summarize(draws, real, label):
    a = np.asarray(draws, float)
    a = a[np.isfinite(a)]
    return dict(label=label, n_draws=int(len(a)), mean=float(a.mean()),
                sd=float(a.std(ddof=1)), p95=float(np.percentile(a, 95)),
                max=float(a.max()), frac_ge_real=float((a >= real).mean()))


# ------------------------------------------------------------------ frame construction
TEAM_FIELDS = P.TEAM_FIELDS


def build_frame(target="ast"):
    """Rebuild EXACTLY the analysis frame E0_I0013/run_screen.py analysed for `target`.

    Every construction is inherited unchanged from the E0 screen so that any later difference is
    attributable to an E1 change and not to the harness.
    """
    from run_screen_defs import CANDS
    mp = B.load_player()
    guard(mp, "master_player after load")
    mt = B.load_team()
    guard(mt, "master_team after load")
    TEAM = P.build_team_pre(mt)

    d = B.build_base(mp, target)
    d = P.add_player_pregame(d)
    guard(d, "player frame target=%s" % target)

    opp_ren = {f: "opp_" + f for f in TEAM_FIELDS}
    own_ren = {f: "own_" + f for f in TEAM_FIELDS}
    d = d.merge(TEAM[["season", "game_id", "team_id"] + TEAM_FIELDS]
                .rename(columns={"team_id": "opp_team_id", **opp_ren}),
                on=["season", "game_id", "opp_team_id"], how="left")
    d = d.merge(TEAM[["season", "game_id", "team_id"] + TEAM_FIELDS].rename(columns=own_ren),
                on=["season", "game_id", "team_id"], how="left")
    d["exp_gposs"] = 0.5 * (d["opp_pace48"] + d["own_pace48"])

    need = ["own_pre", "def_pre", "Mexp", "ppm", "usg_pre", "exp_gposs"] + \
           [c["name"] for c in CANDS if c["side"] in ("opp", "own")]
    W = d[d["is_analysis"]].dropna(subset=need + ["s"]).copy().reset_index(drop=True)
    guard(W, "analysis frame target=%s" % target)

    W["O"] = B.zwithin(W, "own_pre")
    W["D"] = B.zwithin(W, "def_pre")
    W["OD"] = W["O"] * W["D"]
    W["ME"] = B.zwithin(W, "Mexp")
    W["OME"] = W["O"] * W["ME"]
    return W, TEAM, mp, mt


def e0_basecols(W):
    """The published E0 base model: y_count ~ O + D + O*D + Mexp + O*Mexp."""
    return [W["O"].values, W["D"].values, W["OD"].values, W["ME"].values, W["OME"].values]
