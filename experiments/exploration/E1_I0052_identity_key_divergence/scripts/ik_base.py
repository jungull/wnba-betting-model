"""E1_I0052 shared base: paths, partition guard, manifest checks, identity table.

PARTITION: 2021-2024 ONLY. 2025/26 is a SEALED confirmation holdout and is never
read for measurement. Every loader here filters to EXPL_SEASONS before returning.
"""
import os, sys, json, hashlib
import pandas as pd
import numpy as np

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
PROD = r"C:\Users\jgallagher\wnba-betting-model"
EXP = os.path.join(ROOT, "experiments")
KIT = os.path.join(EXP, "exploration", "_screen_kit")
HERE = os.path.join(EXP, "exploration", "E1_I0052_identity_key_divergence")
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, KIT)

EXPL_SEASONS = (2021, 2022, 2023, 2024)
SEALED_SEASONS = (2025, 2026)

MP_RESEARCH = os.path.join(ROOT, "data", "masters", "master_player.parquet")
MP_PROD = os.path.join(PROD, "data", "masters", "master_player.parquet")
MT_RESEARCH = os.path.join(ROOT, "data", "masters", "master_team.parquet")


def sha256(path, cap=None):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def manifest_status(path):
    """Sibling-manifest check. MISSING = UNVERIFIABLE."""
    for cand in (path + ".manifest.json",
                 os.path.splitext(path)[0] + ".manifest.json",
                 os.path.join(os.path.dirname(path), "_manifest.json")):
        if os.path.exists(cand):
            try:
                m = json.load(open(cand, "r", encoding="utf-8"))
            except Exception as e:
                return {"status": "UNPARSEABLE", "path": cand, "err": repr(e)}
            return {"status": "PRESENT", "path": cand,
                    "asof_granularity": m.get("asof_granularity"),
                    "fit_through_date": m.get("fit_through_date")}
    return {"status": "MISSING_UNVERIFIABLE", "path": None}


def load_master_player(which="research"):
    p = MP_RESEARCH if which == "research" else MP_PROD
    df = pd.read_parquet(p)
    return df, p


def partition_guard(df, seasoncol="season", label=""):
    """Assert no sealed season survives. Returns the filtered frame."""
    before = len(df)
    seen = sorted(pd.Series(df[seasoncol]).dropna().unique().tolist())
    keep = df[df[seasoncol].isin(EXPL_SEASONS)].copy()
    sealed_dropped = before - len(keep)
    assert not set(keep[seasoncol].unique()) & set(SEALED_SEASONS), \
        "SEALED SEASON LEAKED into %s" % label
    return keep, {"label": label, "rows_in": before, "rows_kept": len(keep),
                  "sealed_rows_dropped": sealed_dropped,
                  "seasons_seen": [int(s) for s in seen]}


def identity_table(p):
    """Exact-equality identity ambiguity. No fuzzy matching, no substring selection.

    Returns (ids_with_multiple_names, names_with_multiple_ids) as DataFrames.
    """
    g = p[["player_id", "player_name"]].dropna().drop_duplicates()
    i2n = g.groupby("player_id").player_name.nunique()
    n2i = g.groupby("player_name").player_id.nunique()
    amb_ids = sorted(i2n[i2n > 1].index.tolist())
    amb_names = sorted(n2i[n2i > 1].index.tolist())
    rows_i = []
    for pid in amb_ids:
        nms = sorted(g[g.player_id == pid].player_name.tolist())
        seasons = sorted(p[p.player_id == pid].season.unique().tolist())
        teams = sorted(p[p.player_id == pid].team_abbreviation.dropna().unique().tolist())
        rows_i.append({"player_id": int(pid), "n_names": len(nms),
                       "names": " | ".join(nms),
                       "seasons": " ".join(str(int(s)) for s in seasons),
                       "teams": " ".join(teams)})
    rows_n = []
    for nm in amb_names:
        ids = sorted(g[g.player_name == nm].player_id.tolist())
        rows_n.append({"player_name": nm, "n_ids": len(ids),
                       "player_ids": " | ".join(str(int(i)) for i in ids)})
    return (pd.DataFrame(rows_i), pd.DataFrame(rows_n))


# ---- EXPLICIT ALLOWLIST of ambiguous identities in the exploration partition ----
# Populated by s03 and asserted there; declared here so downstream scripts select
# by player_id, never by name substring.
AMBIGUOUS_IDS_2021_2024 = [
    203400, 1628922, 1629484, 1629546, 1629566, 1630043,
    1630151, 1631021, 1631263, 1641657, 1641661, 1642299,
]


def banner(t):
    print()
    print("=" * 92)
    print(t)
    print("=" * 92)
