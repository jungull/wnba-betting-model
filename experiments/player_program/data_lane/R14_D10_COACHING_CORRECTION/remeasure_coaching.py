#!/usr/bin/env python3
"""remeasure_coaching.py — R14_D10_COACHING_CORRECTION.

Re-measures the coaching field family that D10_FIELD_AVAILABILITY_LEDGER reported ABSENT with
coverage 0 in every season and every fold.

READ-ONLY except for this node's own directory. Nothing is fitted, predicted or scored. No
comparative historical performance of any challenger is read. D10's artifact is never opened for
write and never rewritten; it is read only to reproduce the search that produced its negative.

WHAT THIS FILE REFUSES TO COLLAPSE
----------------------------------
  presence         a source for the field exists in the repository and resolves for some share of
                   the row universe.
  cutoff validity  the value was PROVABLY observable at the row's own declared pregame cutoff.

Presence is re-measured here and comes back positive. Cutoff validity is re-measured here and
comes back ZERO, for the same reason it is zero for every other field drawn from
data/injury_history/injury_history.csv: that archive has exactly one observation time and it is
after every cutoff in the universe. Correcting a false ABSENT does not admit anything.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]                      # experiments/player_program
ROOT = PROGRAM.parents[1]                      # repo worktree root
sys.path.insert(0, str(PROGRAM))

import possession_features as pf               # noqa: E402

DATA = ROOT / "data"
INJURY_HISTORY = DATA / "injury_history" / "injury_history.csv"
MASTER_TEAM = DATA / "masters" / "master_team.parquet"
CONTRACT_V4_GAME = ROOT / "experiments" / "prediction_contract_v4" / "game.parquet"
RECEIPT = PROGRAM / "ROSTER_SOURCE_AUDIT_RECEIPT.json"
D10_BUILD = PROGRAM / "data_lane" / "D10_FIELD_AVAILABILITY_LEDGER" / "build_ledger.py"
D10_FINDINGS = PROGRAM / "data_lane" / "D10_FIELD_AVAILABILITY_LEDGER" / "FINDINGS.json"

#: The single retrospective observation moment of the whole transaction archive, as recorded by
#: ROSTER_SOURCE_AUDIT_RECEIPT.json. Read from the receipt at runtime, not hardcoded as a belief.
ARCHIVE_OBS_FALLBACK = pd.Timestamp("2026-07-30", tz="UTC")

#: injury_history uses Basketball-Reference franchise labels. master_team carries both sides of
#: the Phoenix rename and the Portland label; POR -> PDX is the only reach the map has to make.
IH_ABBR_TO_MASTER = {"POR": "PDX"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def src(p: Path) -> dict:
    if not p.exists():
        return {"path": str(p.relative_to(ROOT)).replace("\\", "/"), "present": False}
    return {"path": str(p.relative_to(ROOT)).replace("\\", "/"), "present": True,
            "bytes": p.stat().st_size, "sha256": sha256(p)}


# --------------------------------------------------------------------------- #
# 1. the row universe, the cutoffs and the folds — rebuilt, not inherited
# --------------------------------------------------------------------------- #

def build_spine():
    u = pf.load_universe()
    f = u.frame.copy()
    f["game_id"] = f["game_id"].astype(str)
    f["game_date"] = pd.to_datetime(f["game_date"])
    g = pd.read_parquet(CONTRACT_V4_GAME)
    g["game_id"] = g["game_id"].astype(str)
    f = f.merge(g[["game_id", "forecast_cutoff", "cutoff_policy"]], on="game_id", how="left")
    f.index = pd.Index([f"{a}:{b}" for a, b in zip(f.game_id, f.team_id)], name="team_game_uid")

    folds = pf.chronological_folds(u)
    fold_masks = {}
    for fo in folds:
        def uids(ix):
            d = u.frame.loc[ix]
            return set(f"{a}:{b}" for a, b in zip(d.game_id.astype(str), d.team_id))
        fold_masks[fo.fold_id] = {"cutoff_date": str(fo.cutoff_date), "test_season": int(fo.season),
                                  "train_uids": uids(fo.train_index), "test_uids": uids(fo.test_index)}
    return u, f, fold_masks


def coverage_block(spine: pd.DataFrame, fold_masks: dict, covered: pd.Series,
                   valid: pd.Series | None = None) -> dict:
    """Coverage by season and by fold. ``valid`` is covered AND provably pre-cutoff-observed."""
    covered = covered.reindex(spine.index).fillna(False).astype(bool)
    if valid is None:
        valid = pd.Series(False, index=spine.index)
    valid = valid.reindex(spine.index).fillna(False).astype(bool) & covered

    def cell(mask):
        mask = pd.Series(mask, index=spine.index) if not isinstance(mask, pd.Series) else mask
        n = int(mask.sum())
        if n == 0:
            return {"rows": 0, "covered": 0, "coverage": None,
                    "cutoff_valid": 0, "cutoff_valid_rate": None}
        c = int((covered & mask).sum())
        v = int((valid & mask).sum())
        return {"rows": n, "covered": c, "coverage": round(c / n, 6),
                "cutoff_valid": v, "cutoff_valid_rate": round(v / n, 6)}

    out = {"overall": cell(pd.Series(True, index=spine.index)), "by_season": {},
           "by_season_type": {}, "by_fold": {}}
    for s, grp in spine.groupby("season"):
        out["by_season"][str(int(s))] = cell(pd.Series(spine.index.isin(grp.index), index=spine.index))
    for st, grp in spine.groupby("season_type"):
        out["by_season_type"][str(st)] = cell(pd.Series(spine.index.isin(grp.index), index=spine.index))
    for fid, fm in fold_masks.items():
        out["by_fold"][fid] = {
            "test_season": fm["test_season"], "cutoff_date": fm["cutoff_date"],
            "train": cell(pd.Series(spine.index.isin(list(fm["train_uids"])), index=spine.index)),
            "test": cell(pd.Series(spine.index.isin(list(fm["test_uids"])), index=spine.index))}
    gid = spine["game_id"]
    out["overall"]["game_clusters"] = int(gid.nunique())
    out["overall"]["game_clusters_covered"] = int(gid[covered].nunique())
    return out


# --------------------------------------------------------------------------- #
# 2. enumerate and classify the front_office rows
# --------------------------------------------------------------------------- #

HIRE_RE = re.compile(r"^The (?P<team>.+?) hired (?P<person>.+?) as (?P<role>.+?)\.$")
LEAVE_RE = re.compile(r"^(?P<person>.+?) resigns as (?P<role>.+?) for (?P<team>.+?)\.$")
FIRE_RE = re.compile(r"^The (?P<team>.+?) fired (?P<person>.+?) as (?P<role>.+?)\.$")


def classify_front_office(notes: str) -> dict:
    """Parse one front_office note into (action, person, role_raw, role_class, team_fullname).

    role_class is one of: head_coach, interim_head_coach, general_manager, other.
    A row whose role does not mention 'coach' is NOT coaching identity and is flagged as such.
    """
    for action, rx in (("hire", HIRE_RE), ("resign", LEAVE_RE), ("fire", FIRE_RE)):
        m = rx.match(notes.strip())
        if not m:
            continue
        role_raw = m.group("role").strip()
        low = role_raw.lower()
        if "coach" not in low:
            role_class = "general_manager" if "gm" in low or "general manager" in low else "other"
        elif "interim" in low:
            role_class = "interim_head_coach"
        else:
            role_class = "head_coach"
        return {"action": action, "person": m.group("person").strip(), "role_raw": role_raw,
                "role_class": role_class, "team_fullname": m.group("team").strip(),
                "parsed": True}
    return {"action": None, "person": None, "role_raw": None, "role_class": "unparsed",
            "team_fullname": None, "parsed": False}


# --------------------------------------------------------------------------- #
# 3. how the false negative was produced — reproduced, not asserted
# --------------------------------------------------------------------------- #

def diagnose_false_negative(ih: pd.DataFrame) -> dict:
    """Three candidate mechanisms, each tested against the actual bytes. Only what reproduces
    is reported as a cause."""
    out = {}

    # (a) the search D10 says it ran. Re-run it verbatim and count what it actually returns.
    try:
        r = subprocess.run(["grep", "-rn", "-i", "coach", "data/injury_history/"],
                           cwd=str(ROOT), capture_output=True, text=True, errors="replace")
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        fo_hits = [l for l in lines if ",front_office," in l]
        out["a_grep_reproduction"] = {
            "command": "grep -rn -i coach data/injury_history/  (cwd = worktree root)",
            "returncode": r.returncode,
            "total_matching_lines": len(lines),
            "lines_in_front_office_rows": len(fo_hits),
            "first_two_matches": [l[:180] for l in lines[:2]],
            "reproduces_d10_negative": len(fo_hits) == 0,
        }
    except Exception as exc:                                        # pragma: no cover
        out["a_grep_reproduction"] = {"error": repr(exc)}

    # (b) the pandas-3 string-dtype trap: the idiomatic pandas-2 way of finding text columns
    #     returns an EMPTY list on this file, because every text column is StringDtype, not object.
    obj_cols = [c for c in ih.columns if ih[c].dtype == object]
    is_obj_cols = [c for c in ih.columns if pd.api.types.is_object_dtype(ih[c])]
    is_str_cols = [c for c in ih.columns if pd.api.types.is_string_dtype(ih[c])]
    out["b_string_dtype_trap"] = {
        "pandas_version": pd.__version__,
        "notes_dtype": str(ih["notes"].dtype),
        "columns_where_dtype_equals_object": obj_cols,
        "columns_where_is_object_dtype": is_obj_cols,
        "columns_where_is_string_dtype": is_str_cols,
        "an_object_dtype_column_scanner_finds_nothing_to_search": len(obj_cols) == 0,
        "but_str_contains_works_when_the_column_is_named_directly":
            int(ih["notes"].str.contains("Coach", case=True, na=False).sum()),
        "verdict": ("a scanner written as [c for c in df.columns if df[c].dtype == object] "
                    "silently sees ZERO text columns in this file and reports no text to search. "
                    "This is a live, reproducible silent-false-negative mechanism on these exact "
                    "bytes under pandas " + pd.__version__ + ". It is NOT, however, the mechanism "
                    "D10 used: D10's build_ledger.py contains no dtype-based column scan."),
    }

    # (c) the mechanism that DOES reproduce D10's negative: a hardcoded category whitelist that
    #     omits exactly one category, and that category is the coaching one.
    d10_src = D10_BUILD.read_text(encoding="utf-8", errors="replace")
    d10_cats = set(re.findall(r'"(missed_game_injury|missed_game_other|signing|trade|draft|'
                              r'waiver_claim|contract_conversion|waiver|retirement|'
                              r'contract_suspension|front_office|activation)"', d10_src))
    all_cats = set(ih["category"].dropna().unique())
    omitted = sorted(all_cats - d10_cats)
    rows_reached = int(ih["category"].isin(sorted(d10_cats & all_cats)).sum())
    out["c_category_whitelist_omission"] = {
        "categories_present_in_the_file": sorted(all_cats),
        "categories_named_anywhere_in_D10_build_ledger_py": sorted(d10_cats),
        "categories_in_the_file_that_D10_never_names": omitted,
        "file_rows": int(len(ih)),
        "rows_reached_by_D10s_whitelist": rows_reached,
        "rows_never_reached": int(len(ih)) - rows_reached,
        "reproduces_d10_negative": omitted == ["front_office"],
        "verdict": ("D10 read injury_history.csv (build_ledger.py line 572) and then subsetted it "
                    "three times by hardcoded category sets: {missed_game_injury, "
                    "missed_game_other}, ACQ={signing,trade,draft,waiver_claim,"
                    "contract_conversion}, REL={waiver,retirement,contract_suspension}. Ten of the "
                    "eleven categories present in the file are in that union. The eleventh is "
                    "front_office, and front_office is exactly where head-coach identity lives. "
                    "D10 never enumerated category.value_counts(); it enumerated a list it "
                    "brought with it."),
    }

    # (d) where D10's whitelist came from: the upstream receipt's prose enumerates the same ten.
    rec_txt = RECEIPT.read_text(encoding="utf-8", errors="replace")
    rec = json.loads(rec_txt)
    # find the what_it_is prose that sits beside source == the injury_history path
    what_it_is = None
    def walk(o):
        nonlocal what_it_is
        if isinstance(o, dict):
            if (str(o.get("source", "")).endswith("injury_history/injury_history.csv")
                    and isinstance(o.get("what_it_is"), str) and what_it_is is None):
                what_it_is = o["what_it_is"]
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(rec)
    out["d_upstream_prose_omits_it_too"] = {
        "receipt": "experiments/player_program/ROSTER_SOURCE_AUDIT_RECEIPT.json",
        "receipt_what_it_is_prose": what_it_is,
        "prose_mentions_front_office_or_coach": bool(
            re.search(r"front_office|coach", what_it_is or "", re.I)),
        "receipt_category_counts_include_front_office": '"front_office": 49' in rec_txt,
        "verdict": ("the receipt's own machine-readable category counts record front_office: 49, "
                    "while its human-readable what_it_is prose lists only the other ten "
                    "categories. D10 inherited the prose and not the counts. This is a "
                    "document-vs-bytes contradiction inside a single file."),
    }
    return out


# --------------------------------------------------------------------------- #
def main() -> int:
    ih_raw = pd.read_csv(INJURY_HISTORY)

    # --- the noise class, counted exactly and excluded on purpose ---------------------------- #
    notes = ih_raw["notes"]
    coach_ci = notes.str.lower().str.contains("coach", na=False)
    cd_exact = notes.str.strip().str.upper().eq("COACH'S DECISION")
    cd_sub = notes.str.upper().str.contains("COACH'S DECISION", na=False, regex=False)
    noise = {
        "rows_whose_notes_contain_coach_case_insensitive": int(coach_ci.sum()),
        "rows_whose_notes_are_exactly_COACHS_DECISION": int(cd_exact.sum()),
        "rows_whose_notes_contain_COACHS_DECISION_anywhere": int(cd_sub.sum()),
        "category_breakdown_of_COACHS_DECISION_rows":
            {str(k): int(v) for k, v in ih_raw.loc[cd_sub, "category"].value_counts().items()},
        "surface_forms_and_their_counts": {
            str(k): int(v) for k, v in
            ih_raw.loc[cd_sub, "notes"].str.strip().value_counts().items()},
        "names_a_coach": False,
        "excluded_because": (
            "COACH'S DECISION is an ESPN did-not-play REASON string on a player row. It names no "
            "coach, carries no coach identity, no tenure and no change event. It is a player "
            "availability datum already measured by D10 as injury.missed_game_other_wire. "
            "Counting these as coaching identity would inflate the coaching family to 2,882 rows "
            "of noise and hide the 49 rows that actually carry identity. They are EXCLUDED."),
        "arithmetic_check": (
            "coach-case-insensitive rows = COACH'S-DECISION rows + front_office rows whose note "
            "contains 'Coach'"),
    }
    fo = ih_raw[ih_raw["category"] == "front_office"].copy()
    noise["arithmetic_check_holds"] = bool(
        int(coach_ci.sum()) == int(cd_sub.sum())
        + int(fo["notes"].str.lower().str.contains("coach", na=False).sum()))

    # --- enumerate and classify the 49 signal rows -------------------------------------------- #
    parsed = fo["notes"].apply(classify_front_office).apply(pd.Series)
    fo = pd.concat([fo.reset_index(drop=True), parsed.reset_index(drop=True)], axis=1)
    fo["date_ts"] = pd.to_datetime(fo["date"], errors="coerce")
    fo["master_abbr"] = fo["team"].replace(IH_ABBR_TO_MASTER)

    mt = pd.read_parquet(MASTER_TEAM, columns=["team_id", "team_abbreviation"]).drop_duplicates()
    abbr_to_id = dict(zip(mt["team_abbreviation"], mt["team_id"]))
    fo["team_id"] = fo["master_abbr"].map(abbr_to_id)

    enumerated = []
    for _, r in fo.sort_values(["date_ts", "team"]).iterrows():
        enumerated.append({
            "date": str(r["date"]), "team_abbr_in_file": str(r["team"]),
            "master_abbr": str(r["master_abbr"]),
            "team_id": (None if pd.isna(r["team_id"]) else int(r["team_id"])),
            "notes": str(r["notes"]), "action": r["action"], "person": r["person"],
            "role_raw": r["role_raw"], "role_class": r["role_class"],
            "is_coaching_identity": bool(r["role_class"] in ("head_coach", "interim_head_coach")),
        })

    fo_summary = {
        "front_office_rows": int(len(fo)),
        "parsed": int(fo["parsed"].sum()),
        "unparsed": int((~fo["parsed"]).sum()),
        "by_action": {str(k): int(v) for k, v in fo["action"].value_counts(dropna=False).items()},
        "by_role_class": {str(k): int(v) for k, v in fo["role_class"].value_counts().items()},
        "coaching_identity_rows": int(fo["role_class"].isin(["head_coach", "interim_head_coach"]).sum()),
        "non_coaching_rows": enumerated and [e for e in enumerated if not e["is_coaching_identity"]],
        "distinct_named_people": int(fo.loc[fo["role_class"].isin(
            ["head_coach", "interim_head_coach"]), "person"].nunique()),
        "date_range": [str(fo["date_ts"].min().date()), str(fo["date_ts"].max().date())],
        "teams_with_at_least_one_event": sorted(fo["master_abbr"].unique().tolist()),
        "teams_unmapped_to_master_team": sorted(fo.loc[fo["team_id"].isna(), "team"].unique().tolist()),
    }

    # --- build the head-coach tenure timeline from the 49 events ------------------------------ #
    ev = fo[fo["role_class"].isin(["head_coach", "interim_head_coach"])].copy()
    ev = ev.dropna(subset=["date_ts", "team_id"]).sort_values("date_ts")
    timeline: dict[int, list] = {}
    for tid, g in ev.groupby("team_id"):
        seq = []
        for _, r in g.iterrows():
            seq.append({"date": r["date_ts"], "action": r["action"], "person": r["person"],
                        "role_class": r["role_class"]})
        timeline[int(tid)] = seq

    def coach_asof(tid, when: pd.Timestamp):
        """Who the archive says is head coach STRICTLY BEFORE ``when``, and since when.

        Returns (person, since_date, n_prior_events) or (None, None, n_prior_events).
        A hire sets the incumbent. A fire/resign of the CURRENT incumbent vacates the seat; the
        archive then names nobody until the next hire, and we report NOT COVERED rather than
        carrying a stale name forward. A departure naming somebody who is not the incumbent (the
        archive's window opens mid-tenure) also vacates, because it proves the incumbent we do
        not know has left.
        """
        seq = timeline.get(int(tid), [])
        cur, since, k = None, None, 0
        for e in seq:
            if e["date"] >= when:
                break
            k += 1
            if e["action"] == "hire":
                cur, since = e["person"], e["date"]
            else:                                   # fire / resign
                cur, since = None, None
        return cur, since, k

    u, spine, fold_masks = build_spine()
    idx = spine.index
    cutoff = pd.to_datetime(spine["forecast_cutoff"], utc=True)
    FALSE = pd.Series(False, index=idx)

    named, since_v, prior_k = [], [], []
    for tid, gd in zip(spine["team_id"], spine["game_date"]):
        c, s, k = coach_asof(tid, pd.Timestamp(gd))
        named.append(c is not None)
        since_v.append(s)
        prior_k.append(k)
    named = pd.Series(named, index=idx)
    prior_k = pd.Series(prior_k, index=idx)
    since_v = pd.Series(since_v, index=idx)

    # any_event: the weak presence measure — this team has >=1 head-coach event ever earlier.
    any_event = prior_k > 0
    # in-season change: >=1 head-coach event with effective date inside this row's season year and
    # strictly before the game.
    ev_by_team_year: dict = {}
    for _, r in ev.iterrows():
        ev_by_team_year.setdefault((int(r["team_id"]), int(r["date_ts"].year)), []).append(r["date_ts"])
    change_k = []
    for tid, gd, ssn in zip(spine["team_id"], spine["game_date"], spine["season"]):
        arr = ev_by_team_year.get((int(tid), int(ssn)), [])
        change_k.append(sum(1 for d in arr if d < pd.Timestamp(gd)))
    change_k = pd.Series(change_k, index=idx)
    change_determinable = change_k > 0

    # tenure in games: computable only where a name AND its appointment date are both known.
    tenure_games = {}
    for uid, tid, gd, s in zip(idx, spine["team_id"], spine["game_date"], since_v):
        # since_v round-trips through a pandas Series, so a missing appointment date arrives as
        # NaT, not None. `s is None` alone silently marks every row as known — the same shape of
        # error this node exists to correct. pd.isna covers None, NaT and NaN.
        if s is None or pd.isna(s):
            tenure_games[uid] = None
            continue
        m = (spine["team_id"] == tid) & (spine["game_date"] >= s) & (spine["game_date"] < gd)
        tenure_games[uid] = int(m.sum())
    tenure_known = pd.Series({k: v is not None for k, v in tenure_games.items()})

    # --- cutoff validity: measured, and it is zero ------------------------------------------- #
    rec = json.loads(RECEIPT.read_text(encoding="utf-8", errors="replace"))
    obs_txt = json.dumps(rec)
    m = re.search(r"committed (\d{4}-\d{2}-\d{2})", obs_txt)
    archive_obs = pd.Timestamp(m.group(1), tz="UTC") if m else ARCHIVE_OBS_FALLBACK
    rows_with_cutoff_after_obs = int((cutoff >= archive_obs).sum())

    # The one boundary that could be argued the other way, measured rather than waved past.
    m2 = re.search(r"committed (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) ([+-]\d{4})", obs_txt)
    commit_ts = (pd.Timestamp(f"{m2.group(1)} {m2.group(2)}{m2.group(3)}").tz_convert("UTC")
                 if m2 else archive_obs)
    late = cutoff >= archive_obs
    late_named = late & named
    late_after_commit = cutoff >= commit_ts
    boundary = {
        "rows_whose_cutoff_is_on_or_after_the_archive_DATE": int(late.sum()),
        "of_those_with_a_named_head_coach": int(late_named.sum()),
        "commit_timestamp_recovered_from_the_receipt": str(commit_ts),
        "rows_whose_cutoff_is_on_or_after_the_commit_TIMESTAMP": int(late_after_commit.sum()),
        "game_dates_involved": sorted(spine.loc[late, "game_date"].astype(str).unique().tolist()),
        "latest_front_office_event_in_the_archive": str(ev["date_ts"].max().date()),
        "why_these_are_still_recorded_cutoff_valid_0": (
            "a weaker rule — 'the archive file existed before this row's cutoff' — would score "
            f"{int(late_after_commit.sum())} of the 2,982 rows valid. This node does NOT apply "
            "that rule and records 0, for three measured reasons. (1) The observation moment is "
            "not in the bytes: injury_history.csv has no capture, publication or observation "
            "column, so no gate that reads the artifact can verify the ordering; the 2026-07-30 "
            "13:42 -0400 figure comes from git history via ROSTER_SOURCE_AUDIT_RECEIPT.json. "
            "(2) Only one snapshot was ever taken and Basketball-Reference edits transaction "
            "pages in place, so the bytes on disk today cannot be shown to be the bytes that "
            "stood at that moment. (3) Cutoff validity in the D10 ledger is a PER-ROW property "
            "backed by a per-row timestamp; a single file-level commit time is not one. This is "
            "recorded so a later reader can see the boundary was measured and rejected on stated "
            "grounds, not overlooked."),
    }

    cutoff_validity = {
        "boundary_case_examined": boundary,
        "archive_observation_time": str(archive_obs.date()),
        "observation_time_is_per_row": False,
        "source_has_a_publication_time_column": bool("publication_time" in ih_raw.columns),
        "rows_whose_own_forecast_cutoff_is_at_or_after_the_archive_observation_time":
            rows_with_cutoff_after_obs,
        "cutoff_valid_rows": 0,
        "why_zero": (
            "the front_office rows carry an EFFECTIVE date and nothing else. The archive has one "
            "observation time for all 8,340 rows and it is 2026-07-30, later than every cutoff in "
            "the universe. A coaching change effective 2022-05-25 is a true fact about "
            "2022-05-25, and such moves are in practice reported same day — but this artifact "
            "cannot PROVE any row was public before 2026-07-30, and plausibility is not a "
            "timestamp. Correcting ABSENT to PRESENT changes the presence column and NOTHING in "
            "the cutoff-valid column."),
    }

    # --- the four fields, re-measured -------------------------------------------------------- #
    fields = []

    def emit(name, verdict, structural_class, covered, evidence, extra=None):
        rec = {"family": "coaching", "field": name, "verdict": verdict,
               "structural_class": structural_class,
               "source": ("injury_history_wire" if covered is not None else None),
               "source_timestamp_column": ("date (EFFECTIVE date only)" if covered is not None else None),
               "source_timestamp_granularity": (
                   "per-row effective date; observation time is ONE constant for all rows"
                   if covered is not None else None),
               "d10_verdict": "ABSENT", "d10_coverage": 0.0,
               "evidence": evidence,
               "coverage": coverage_block(spine, fold_masks,
                                          covered if covered is not None else FALSE, valid=FALSE)}
        if extra:
            rec.update(extra)
        fields.append(rec)
        return rec

    emit("coaching.head_coach_identity", "PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN",
         "retrospective_archive_single_observation_time", named,
         ("COVERED means: the 49-row front_office event archive names a specific head coach for "
          "this team as of a moment strictly before this row's game_date, with no intervening "
          "departure. A team whose head coach was appointed before the archive window opens "
          "(2021-05-03) has no hire event and is NOT covered — the archive cannot name a coach it "
          "never saw hired. Vacancies after a fire/resign with no subsequent hire are NOT covered; "
          "no stale name is carried forward. This is a strictly weaker measure than 'the team has "
          "some coaching event somewhere', which is reported separately as "
          "coaching.head_coach_event_present."),
         {"named_coach_rows": int(named.sum()),
          "distinct_named_coaches_used": int(pd.Series(
              [coach_asof(t, pd.Timestamp(d))[0] for t, d in
               zip(spine['team_id'], spine['game_date'])]).dropna().nunique())})

    emit("coaching.head_coach_event_present", "PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN",
         "retrospective_archive_single_observation_time", any_event,
         ("the weak presence measure: this team has at least one head-coach event in the archive "
          "with an effective date strictly earlier than this row's game_date. It does NOT imply a "
          "coach can be named for the row — a row whose only prior event is a firing is covered "
          "here and not covered by head_coach_identity. Reported so the gap between 'the family "
          "exists for this team' and 'the field resolves for this row' is visible and not "
          "collapsed."))

    emit("coaching.coach_change_flag", "PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN",
         "retrospective_archive_single_observation_time", change_determinable,
         ("COVERED means: at least one head-coach event with an effective date inside this row's "
          "own season year and strictly earlier than its game_date, i.e. an in-season coaching "
          "change the archive can date. Rows not covered are rows where the archive records no "
          "in-season change before the game; that is an unobserved-negative, not a measured "
          "'no change', because the archive's completeness for a season it did not scrape "
          "cannot be established from the bytes."),
         {"rows_with_at_least_one_in_season_prior_event": int(change_determinable.sum()),
          "max_in_season_prior_events": int(change_k.max())})

    emit("coaching.coach_tenure_games", "PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN",
         "retrospective_archive_single_observation_time", tenure_known,
         ("COVERED means: a named head coach AND that coach's appointment date are both known "
          "from the archive, so games-since-appointment is countable against the possession "
          "universe. Identical to head_coach_identity by construction — every named coach in this "
          "archive is named BY a hire event that carries its own date — and reported separately "
          "so that identity and tenure are not assumed to coincide in some future source where "
          "they would not."),
         {"tenure_games_min": (None if not tenure_known.any() else
                               int(min(v for v in tenure_games.values() if v is not None))),
          "tenure_games_max": (None if not tenure_known.any() else
                               int(max(v for v in tenure_games.values() if v is not None)))})

    emit("coaching.rotation_policy", "ABSENT", "no_source", None,
         ("re-searched and STILL ABSENT. No artifact in the repository records a rotation policy, "
          "a minutes-allocation rule, a substitution pattern or any coach-level strategy "
          "descriptor. The front_office rows carry WHO coaches, never HOW. D10's ABSENT verdict "
          "for this one field survives correction and is preserved as a negative result."))

    diag = diagnose_false_negative(ih_raw)

    # --- D10's own recorded claim, quoted from its bytes -------------------------------------- #
    d10 = json.loads(D10_FINDINGS.read_text(encoding="utf-8", errors="replace"))
    d10_coaching = [f for f in d10.get("fields", []) if f.get("family") == "coaching"]
    d10_claim = [{"field": f["field"], "verdict": f["verdict"],
                  "overall_coverage": f.get("coverage", {}).get("overall", {}).get("coverage"),
                  "overall_covered": f.get("coverage", {}).get("overall", {}).get("covered"),
                  "cutoff_valid": f.get("coverage", {}).get("overall", {}).get("cutoff_valid")}
                 for f in d10_coaching]

    out = {
        "schema": "r14_d10_coaching_correction/1",
        "node_id": "R14_D10_COACHING_CORRECTION",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "epistemic_status": (
            "REMEDIATION of a confirmed FALSE NEGATIVE. D10 reported the coaching family ABSENT "
            "with 0 coverage on an assertion contradicted by the bytes of a file it had itself "
            "loaded. This node RE-MEASURES; it may not simply restate D12's numbers, because "
            "relaying an unverified figure is the failure mode that produced the defect."),
        "parent_artifact": "experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER",
        "parent_artifact_modified": False,
        "sources": {"injury_history": src(INJURY_HISTORY), "master_team": src(MASTER_TEAM),
                    "contract_v4_game": src(CONTRACT_V4_GAME),
                    "roster_source_audit_receipt": src(RECEIPT),
                    "d10_findings": src(D10_FINDINGS), "d10_build_ledger": src(D10_BUILD)},
        "row_universe": {"artifact": "team_possession_universe/1",
                         "row_universe_digest": u.row_universe_digest,
                         "team_game_rows": int(len(spine)),
                         "game_clusters": int(spine["game_id"].nunique())},
        "d10_original_claim_as_recorded_in_its_findings": d10_claim,
        "corrected_verdict": "PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN",
        "cutoff_valid_count": 0,
        "presence_is_not_cutoff_validity": (
            "the family is PRESENT. It is not admissible. Those are different columns and this "
            "correction moves only the first."),
        "coachs_decision_noise_class": noise,
        "front_office_enumeration": fo_summary,
        "front_office_rows": enumerated,
        "cutoff_validity": cutoff_validity,
        "fields": fields,
        "how_the_false_negative_was_produced": diag,
        "measured_independently_of_D12": (
            "the coverage numbers in this file are produced by remeasure_coaching.py from "
            "data/injury_history/injury_history.csv, possession_features.load_universe() and "
            "possession_features.chronological_folds(). No file under data_lane/D12_COACHING_"
            "HISTORY was read by this script. The comparison in cross_check_vs_D12 below is "
            "computed AFTER the fact by a separate script and is a check, not a source."),
    }

    (HERE / "CORRECTION.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    # a flat CSV of the 49 rows, for a human to read without parsing JSON
    pd.DataFrame(enumerated).to_csv(HERE / "front_office_rows_v1.csv", index=False)

    # a flat CSV of the per-row coverage, so the coverage claim is auditable row by row
    pd.DataFrame({
        "team_game_uid": idx, "game_id": spine["game_id"].values,
        "team_id": spine["team_id"].values, "game_date": spine["game_date"].values,
        "season": spine["season"].values, "season_type": spine["season_type"].values,
        "head_coach_named": named.values, "head_coach_event_present": any_event.values,
        "in_season_change_determinable": change_determinable.values,
        "prior_head_coach_events": prior_k.values,
        "coach_tenure_games": [tenure_games[u_] for u_ in idx],
        "cutoff_valid": False,
    }).to_csv(HERE / "coverage_by_row_v1.csv", index=False)

    print(f"front_office rows           : {fo_summary['front_office_rows']}")
    print(f"  coaching identity rows    : {fo_summary['coaching_identity_rows']}")
    print(f"  non-coaching (GM etc)     : {len(fo_summary['non_coaching_rows'])}")
    print(f"COACH'S DECISION noise rows : {noise['rows_whose_notes_contain_COACHS_DECISION_anywhere']}")
    print(f"universe                    : {len(spine)} team-games / {spine['game_id'].nunique()} clusters")
    for f in fields:
        c = f["coverage"]["overall"]
        print(f"  {f['field']:42s} {f['verdict']:44s} cov={c['coverage']} "
              f"covered={c['covered']} cutoff_valid={c['cutoff_valid']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
