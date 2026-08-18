"""mb_base.py -- shared loading / identity / partition machinery for E1_I0058_market_benchmark.

READ THE CONSTRUCTION, NOT THE LABEL (D086).  Every column this module hands onward is
documented here with what it ACTUALLY is, not what its name suggests.

  props.line          -- a BETTING LINE for the `player_points` market at ONE captured
                         snapshot, per (event, bookmaker, player).  It is NOT a mean
                         forecast: it is set to balance two-sided action and the two
                         prices around it carry vig.
  props.over_price /
  props.under_price   -- AMERICAN odds.  Their implied probabilities sum to > 1.
  master_player.pts   -- realised points, the outcome.
  prediction.pred_point (target `player_scoring_distribution`)
                      -- E[points | player is ACTIVE], constructed in
                         `cbs_v7.conditional_center` as
                             ewma(points per 36 min) * ewma(minutes) / 36
                         both legs walk-forward over history KNOWABLE AT THE CUTOFF.
                         It is a CONDITIONAL-ON-PLAYING centre, which is why every
                         analysis here is restricted to rows the player actually played.

PARTITION.  The boundary is taken from the repository's own definition,
`experiments/exploration/_screen_kit/screenkit.py :: EXPLORATION_SEASONS`, NOT assumed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
EXP_DIR = os.path.dirname(_HERE)
OUT = os.path.join(EXP_DIR, "out")
REPO = os.path.abspath(os.path.join(EXP_DIR, "..", "..", ".."))
KIT = os.path.join(REPO, "experiments", "exploration", "_screen_kit")
if KIT not in sys.path:
    sys.path.insert(0, KIT)

import screenkit as sk  # noqa: E402

# ---- the partition, from the repository's own definition -----------------------------------
EXPLORATION_SEASONS = tuple(sk.EXPLORATION_SEASONS)   # (2021, 2022, 2023, 2024)
HOLDOUT_SEASONS = tuple(sk.HOLDOUT_SEASONS)           # (2025, 2026)
#: The props instrument exists only from 2024 onward, so the only exploration season this
#: screen can use is the LATEST exploration season.  Stated, not assumed.
PROPS_EXPLORATION_SEASON = max(EXPLORATION_SEASONS)

PROPS_CSV = os.path.join(REPO, "data", "props_capture", "historical",
                         "master_props_historical.csv")
MASTER = os.path.join(REPO, "data", "masters", "master_player.parquet")

#: PRIMARY model anchor: the v5-contract player OOF run, same estimator as v14.
ANCHOR_PRIMARY = os.path.join(REPO, "experiments", "cbs_v15_player_oof_v5", "attempt_001")
ANCHOR_PRIMARY_ID = "cbs_v15_player_oof_v5/1"
#: SECONDARY anchor for a construction-robustness check only.
ANCHOR_SECONDARY = os.path.join(REPO, "experiments", "cbs_v14_player_oof", "attempt_001")
ANCHOR_SECONDARY_ID = "cbs_v14_player_oof/1"

TARGET = "player_scoring_distribution"


# ============================================================================================
# identity
# ============================================================================================
def stable_hash(*parts) -> str:
    """Byte-identical to `cbs_obligation_key.stable_hash`; reproduced, then ASSERTED equal."""
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()[:16]


def row_uid(player_id, game_id, team_id) -> str:
    return "ob_" + stable_hash(int(player_id), str(game_id), int(team_id))


def assert_row_uid_matches_repo():
    """Prove our reimplementation equals the repository's, rather than assuming it."""
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    import cbs_obligation_key as ok
    probes = [(202664, "1022400001", 1611661313), (1641653, "1022300169", 1611661319),
              (203824, "1022400175", 1611661328)]
    for p in probes:
        assert row_uid(*p) == ok.row_uid(*p), f"row_uid drift at {p}"
    return ok.OBLIGATION_KEY_ID


_NONALPHA = re.compile(r"[^a-z]")


def norm_name(s) -> str:
    """ASCII-fold, lowercase, drop every non-letter.  EXACT match on this key only.

    NO substring matching anywhere in this screen (a name substring alone must never
    establish anything).  Residual collisions are counted and reported, not swallowed.
    """
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return _NONALPHA.sub("", s.lower())


# ============================================================================================
# artifact reproduction from bytes
# ============================================================================================
def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(parquet_path: str) -> dict:
    """Re-hash a prediction artifact and compare to its own committed manifest sidecar."""
    man_path = parquet_path + ".manifest.json"
    got = sha256_file(parquet_path)
    rec = {"artifact": os.path.relpath(parquet_path, REPO).replace("\\", "/"),
           "sha256_recomputed": got, "manifest_present": os.path.exists(man_path)}
    if rec["manifest_present"]:
        man = json.load(open(man_path))
        claimed = None
        for k in ("sha256", "artifact_sha256", "digest", "content_sha256"):
            if k in man:
                claimed = man[k]
                break
        if claimed is None:
            for v in man.values():
                if isinstance(v, str) and len(v) == 64 and re.fullmatch(r"[0-9a-f]{64}", v):
                    claimed = v
                    break
        rec["sha256_manifest"] = claimed
        rec["match"] = (claimed == got)
        rec["n_rows_claimed"] = man.get("n_rows", man.get("rows"))
    return rec


# ============================================================================================
# loaders -- every one of them PARTITION-FILTERED BEFORE ANYTHING ELSE HAPPENS
# ============================================================================================
def load_master(season: int = PROPS_EXPLORATION_SEASON) -> pd.DataFrame:
    cols = ["game_id", "season", "season_type", "game_date", "team_id", "opp_team_id",
            "is_home", "player_id", "player_name", "minutes", "pts", "starter_flag"]
    m = pd.read_parquet(MASTER, columns=cols)
    m = m[m.season == season].copy()          # <<< PARTITION FILTER, FIRST
    m["gid"] = m.game_id.astype(str)
    m["pn"] = m.player_name.map(norm_name)
    m["row_uid"] = [row_uid(p, g, t) for p, g, t in
                    zip(m.player_id, m.gid, m.team_id)]
    return m


def load_props_raw() -> pd.DataFrame:
    h = pd.read_csv(PROPS_CSV, low_memory=False)
    h["commence_ts"] = pd.to_datetime(h.commence_time, utc=True)
    h["snap_ts"] = pd.to_datetime(h.snapshot_returned_utc, utc=True, errors="coerce")
    h["gid"] = h.game_id.astype(str).str.replace(r"\.0$", "", regex=True)
    h["pn"] = h.player_name.map(norm_name)
    h["lead_h"] = (h.commence_ts - h.snap_ts).dt.total_seconds() / 3600.0
    return h


def load_anchor(anchor_dir: str, season: int = PROPS_EXPLORATION_SEASON) -> pd.DataFrame:
    p = os.path.join(anchor_dir, f"predictions__{TARGET}__{season}.parquet")
    d = pd.read_parquet(p)
    return d, p


# ============================================================================================
# vig removal
# ============================================================================================
def american_to_prob(a):
    a = np.asarray(a, dtype=float)
    neg = a < 0
    den_neg = np.where(neg, -a + 100.0, 1.0)
    den_pos = np.where(neg, 1.0, a + 100.0)
    return np.where(neg, (-a) / den_neg, 100.0 / den_pos)


#: Wichura AS241 / Acklam inverse normal CDF.  scipy is NOT installed in this environment, so
#: the quantile function is implemented here and REGRESSION-TESTED against known values in
#: `verify.py` rather than trusted.  Absolute error < 1.15e-9 over (0,1).
_A = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
      1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
_B = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
      6.680131188771972e+01, -1.328068155288572e+01)
_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
      -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
      3.754408661907416e+00)


def norm_ppf(p):
    """Inverse standard normal CDF, vectorised."""
    p = np.asarray(p, dtype=float)
    out = np.empty_like(p)
    lo, hi = 0.02425, 1 - 0.02425
    m_lo, m_hi = p < lo, p > hi
    m_mid = ~(m_lo | m_hi)
    q = np.sqrt(-2 * np.log(np.where(m_lo, np.clip(p, 1e-300, None), 0.5)))
    out = np.where(m_lo,
                   (((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) /
                   ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1), 0.0)
    q2 = np.sqrt(-2 * np.log(np.where(m_hi, np.clip(1 - p, 1e-300, None), 0.5)))
    out = np.where(m_hi,
                   -(((((_C[0] * q2 + _C[1]) * q2 + _C[2]) * q2 + _C[3]) * q2 + _C[4]) * q2 + _C[5]) /
                   ((((_D[0] * q2 + _D[1]) * q2 + _D[2]) * q2 + _D[3]) * q2 + 1), out)
    r = np.where(m_mid, p, 0.5) - 0.5
    r2 = r * r
    out = np.where(m_mid,
                   (((((_A[0] * r2 + _A[1]) * r2 + _A[2]) * r2 + _A[3]) * r2 + _A[4]) * r2 + _A[5]) * r /
                   (((((_B[0] * r2 + _B[1]) * r2 + _B[2]) * r2 + _B[3]) * r2 + _B[4]) * r2 + 1), out)
    return out


def devig_proportional(p_over_raw, p_under_raw):
    """Multiplicative / proportional de-vig.

    ASSUMPTION: the book's margin is applied as a common multiplicative factor to both
    sides, so fair probabilities are the raw implied probabilities rescaled to sum to 1.
    This is the standard and the most conservative of the common methods in the sense
    that it moves the two sides by the SAME RATIO, i.e. it introduces no favourite-
    longshot correction of its own.  It is exact only if the book prices that way.
    """
    s = p_over_raw + p_under_raw
    return p_over_raw / s, p_under_raw / s


def devig_additive(p_over_raw, p_under_raw):
    """Additive-margin de-vig: subtract half the overround from each side.

    ASSUMPTION: the margin is a constant probability increment on each side.  Reported
    as a SENSITIVITY only, never as the headline.
    """
    s = p_over_raw + p_under_raw
    m = (s - 1.0) / 2.0
    return p_over_raw - m, p_under_raw - m


def write_log(name: str, lines) -> str:
    path = os.path.join(EXP_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(str(x) for x in lines) + "\n")
    return path


class Tee:
    """Capture everything printed into a run log AND stdout."""

    def __init__(self, path):
        self.buf = []
        self.path = path

    def __call__(self, *a):
        s = " ".join(str(x) for x in a)
        self.buf.append(s)
        print(s)

    def close(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.buf) + "\n")
