"""E1_I0026_detection_floor -- shared loader, planting machinery, null helpers.

READ-ONLY on everything outside experiments/exploration/E1_I0026_detection_floor/.
Imports _screen_kit rather than copying it (D077 adoption; 224 assertions).

PARTITION: 2021-2024 only, enforced by screenkit.assert_partition (a VALUE test) after every
load and every filter.  2025/2026 are never read.

R2 CONVENTION (D069): plain unweighted OLS R2, SST about the UNWEIGHTED mean.
The dR2 statistic is tv_base.BaseFit.dr2's algebra, re-derived here and asserted against
screenkit.delta_r2_plain on real data in s03.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
EXPL = os.path.join(ROOT, r"experiments\exploration")
HERE = os.path.join(EXPL, "E1_I0026_detection_floor")
OUT = os.path.join(HERE, "out")
D089_FRAME = os.path.join(EXPL, "E1_I0018_teammate_volume_channel", "screen_frame.parquet")
D085_FRAME = os.path.join(EXPL, "E0_I0016_efficiency_predictors", "screen_frame.parquet")
D089_NPZ = os.path.join(EXPL, "E1_I0018_teammate_volume_channel", "permutation_draws.npz")

if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

os.makedirs(OUT, exist_ok=True)
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 140)

SEED = 20260808
N_DRAWS = 600                 # identical to D085 and D089
SEASONS = (2021, 2022, 2023, 2024)

CARRIER_PLAYER = "P01_c04_prevgame"     # CP -- strictly-prior reconstruction of the best lead
CARRIER_OPP = "A10_opp_defrtg"          # CO -- strictly-prior opponent aggregate

BASES = {
    "B_SINGLE": ["refB_ppm"],
    "B_COMPLETE": ["refB_ppm", "refB_spm", "refB_pps", "refB_mpg"],
}
OUTCOME = "y_ppm"

KEYCOLS = ["season", "player_id", "team_id", "opp_team_id", "game_id", "game_date"]


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


# ---------------------------------------------------------------------------- frame ----------
def load_frame(verbose=True):
    """Join the two frozen screen frames on (player_id, game_id).  1:1 and lossless, asserted."""
    a = pd.read_parquet(D089_FRAME)
    b = pd.read_parquet(D085_FRAME)
    sk.assert_partition(a, verbose=verbose)
    sk.assert_partition(b, verbose=verbose)
    keep_b = ["player_id", "game_id", CARRIER_OPP, "A01_opp_efg_allowed", "A02_opp_ts_allowed"]
    b2 = b[keep_b].copy()
    assert not b2.duplicated(["player_id", "game_id"]).any(), "D085 frame key is not unique"
    assert not a.duplicated(["player_id", "game_id"]).any(), "D089 frame key is not unique"
    n0 = len(a)
    f = a.merge(b2, on=["player_id", "game_id"], how="inner", validate="one_to_one")
    assert len(f) == n0, "join lost rows: %d -> %d" % (n0, len(f))
    f = f.sort_values(["player_id", "season", "game_date", "game_id"],
                      kind="stable").reset_index(drop=True)
    sk.assert_partition(f, verbose=verbose)
    if verbose:
        print("  joined frame %s  (1:1, lossless)" % (f.shape,))
        print("  players=%d teams=%d opp=%d games=%d dates=%d seasons=%s"
              % (f.player_id.nunique(), f.team_id.nunique(), f.opp_team_id.nunique(),
                 f.game_id.nunique(), f.game_date.nunique(), sorted(f.season.unique())))
    return f


def stratum_mask(f, name):
    if name == "POOLED":
        return np.ones(len(f), bool)
    if name == "DECISION":
        return ((f["n_prior"] >= 8).to_numpy()
                & (f["prior5_minutes"] >= 24).to_numpy(dtype=bool))
    raise KeyError(name)


# ------------------------------------------------------------------- dR2 machinery -----------
class BaseFit:
    """Precomputed residualiser for a fixed base design [1, base...].

    Identical algebra to E1_I0018/tv_base.py::BaseFit, which was itself verified against
    screenkit.delta_r2_plain on real data.  D069 convention: SST about the UNWEIGHTED mean.
    """

    def __init__(self, y, base):
        y = np.asarray(y, float)
        base = np.asarray(base, float)
        if base.ndim == 1:
            base = base[:, None]
        self.n = len(y)
        X = np.column_stack([np.ones(self.n), base])
        self.X = X
        self.XtXi = np.linalg.pinv(X.T @ X)
        self.y = y
        self.e = y - X @ (self.XtXi @ (X.T @ y))
        self.sst = float(((y - y.mean()) ** 2).sum())

    def resid_x(self, x):
        x = np.asarray(x, float)
        return x - self.X @ (self.XtXi @ (self.X.T @ x))

    def dr2(self, x):
        xt = self.resid_x(x)
        den = float(xt @ xt)
        if not np.isfinite(den) or den <= 1e-12:
            return 0.0
        num = float(self.e @ xt)
        return (num * num / den) / self.sst


def dr2_fast(e, sst, xt, xtxt):
    """dR2 with the base already residualised out.  e and xt must come from the SAME base."""
    num = float(e @ xt)
    return (num * num / xtxt) / sst


# --------------------------------------------------------------- honest planting --------------
def cyclic_rotate_within(values, codes, rng):
    """Rotate each group's contiguous run by a random offset.

    Preserves each group's LEVEL, its MARGINAL and its SERIAL structure; destroys only the
    alignment to everything else.  `codes` must label contiguous runs in time order -- the
    frame is sorted by (player_id, season, game_date, game_id) before this is called, and
    that is asserted by the caller.
    """
    out = np.empty_like(values)
    order = np.argsort(codes, kind="stable")
    starts = {}
    for pos in order:
        starts.setdefault(codes[pos], []).append(pos)
    for g, idx in starts.items():
        idx = np.asarray(idx)
        m = len(idx)
        if m <= 1:
            out[idx] = values[idx]
            continue
        k = int(rng.integers(1, m)) if m > 1 else 0
        out[idx] = np.roll(values[idx], k)
    return out


class Planter:
    """Builds y(delta) = F + rotate(e) + c*xt on a fixed (stratum, base, carrier) cell.

    THE PLANT IS HONEST: the carrier is a REAL column with its REAL distribution and REAL
    grouping structure.  Nothing is simulated from scratch.  Only the RESPONSE's residual is
    re-aligned, by the same cyclic rotation the programme's own honest null uses on features.
    """

    def __init__(self, y, base, carrier, rot_codes):
        self.bf0 = BaseFit(y, base)
        self.base = np.asarray(base, float)
        if self.base.ndim == 1:
            self.base = self.base[:, None]
        self.F = y - self.bf0.e
        self.e = self.bf0.e
        self.rot_codes = np.asarray(rot_codes)
        self.xt0 = self.bf0.resid_x(carrier)
        self.xtxt0 = float(self.xt0 @ self.xt0)
        self.sst0 = self.bf0.sst
        self.carrier = np.asarray(carrier, float)

    def c_for(self, delta):
        return float(np.sqrt(max(delta, 0.0) * self.sst0 / self.xtxt0))

    def draw_response(self, rng):
        return self.F + cyclic_rotate_within(self.e, self.rot_codes, rng)

    def realised_dr2(self, y_null, delta):
        """dR2 of the carrier on y(delta), with the base REFIT on y(delta) -- the screens' own
        statistic, not an approximation."""
        y = y_null + self.c_for(delta) * self.xt0
        bf = BaseFit(y, self.base)
        return bf.dr2(self.carrier)
