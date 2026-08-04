"""
D12_COACHING_HISTORY -- build a retrospectively auditable head-coaching table.

Epistemic status of every artifact this script writes:
    REFERENCE DATA. Auditable history only. Explicitly NOT admitted to any experiment
    before a cutoff review.

Design rules this script obeys (they are the node's acceptance criteria):
  1. Every emitted coaching record carries a source (dataset file, source page, source row
     index, verbatim note text) and an effective date.
  2. No record is invented. Every coach name, date and franchise is parsed by an explicit,
     named regex rule from a byte in the source file. Rows that no rule parses are emitted
     as UNPARSED, not dropped and not hand-filled.
  3. Ambiguous tenure boundaries are MARKED, never smoothed. Left-censored starts, ends
     inferred only by succession, open ends, and the appointment-date-vs-first-game gap are
     each carried as an explicit flag, not resolved by assumption.
  4. Nothing here is a feature. The table is emitted with admission_status = NOT_ADMITTED.

Run:  python build_coaching_history.py
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# --- paths -------------------------------------------------------------------------------
NODE_DIR = Path(__file__).resolve().parent
REPO_ROOT = NODE_DIR.parents[3]  # .../player-model-program

# The only source in this repository that contains dated head-coaching events.
# NOTE: this file lives OUTSIDE the node's declared read scope
# (experiments/player_program/). That deviation is disclosed in REPORT.md.
SRC_COACH_EVENTS = REPO_ROOT / "data" / "injury_history" / "injury_history.csv"

# In-scope sibling-node artifact used ONLY as a franchise-name -> team_id dictionary.
SRC_TEAM_DIM = (
    REPO_ROOT
    / "experiments/player_program/data_lane/D13_ARENA_TRAVEL_DIMENSION/arena_dimension_v1.csv"
)

# In-scope canonical universe, used ONLY to enumerate team-seasons and their first game date.
# Universe definition is the one EVIDENCE_PACKET_V2 / D13 use:
#   team_possession_prior_v1.parquet where pace_resolved == True  -> 2982 rows / 1491 clusters.
SRC_UNIVERSE = (
    REPO_ROOT / "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet"
)
UNIVERSE_DEFINITION = "team_possession_prior_v1.parquet where pace_resolved == True"

OUT_EVENTS = NODE_DIR / "coaching_events_v1.csv"
OUT_TENURE = NODE_DIR / "coaching_tenure_v1.csv"
OUT_COVERAGE = NODE_DIR / "team_season_coverage_v1.csv"
OUT_MEAS = NODE_DIR / "MEASUREMENTS.json"

EPISTEMIC_STATUS = (
    "REFERENCE DATA. Auditable history only. Explicitly NOT admitted to any experiment "
    "before a cutoff review."
)

# --- parse rules -------------------------------------------------------------------------
# Each rule is (rule_id, compiled_pattern, event_type). Rules are tried in order.
RULES = [
    (
        "R1_HIRE",
        re.compile(r"^The (?P<franchise>.+?) hired (?P<coach>.+?) as (?P<role>.*?Head Coach.*?)\.$"),
        "HIRE",
    ),
    (
        "R2_DEPART_RESIGN",
        re.compile(r"^(?P<coach>.+?) resigns as (?P<role>.*?Head Coach.*?) for (?P<franchise>.+?)\.$"),
        "DEPART",
    ),
    (
        "R3_DEPART_FIRE",
        re.compile(r"^The (?P<franchise>.+?) fired (?P<coach>.+?) as (?P<role>.*?Head Coach.*?)\.$"),
        "DEPART",
    ),
]

DNP_MARKER = "COACH'S DECISION"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    meas: dict = {
        "node_id": "D12_COACHING_HISTORY",
        "epistemic_status": EPISTEMIC_STATUS,
        "built_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {},
        "measurements": {},
    }

    # ---------------------------------------------------------------- load source
    raw = pd.read_csv(SRC_COACH_EVENTS)
    meas["inputs"]["coach_event_source"] = {
        "path": str(SRC_COACH_EVENTS.relative_to(REPO_ROOT)).replace("\\", "/"),
        "sha256": sha256(SRC_COACH_EVENTS),
        "rows": int(len(raw)),
        "columns": list(raw.columns),
        "has_capture_timestamp_column": False,
        "in_declared_node_read_scope": False,
    }

    dim = pd.read_csv(SRC_TEAM_DIM)
    meas["inputs"]["team_dimension"] = {
        "path": str(SRC_TEAM_DIM.relative_to(REPO_ROOT)).replace("\\", "/"),
        "sha256": sha256(SRC_TEAM_DIM),
        "rows": int(len(dim)),
        "in_declared_node_read_scope": True,
    }

    # franchise name -> team_id (one id per franchise in D13)
    fran_map = (
        dim.groupby("franchise")["team_id"].agg(lambda s: sorted(set(s))).to_dict()
    )
    fran_to_id = {k: v[0] for k, v in fran_map.items() if len(v) == 1}
    meas["measurements"]["team_dimension_franchises"] = len(fran_to_id)
    meas["measurements"]["team_dimension_franchises_ambiguous"] = int(
        sum(1 for v in fran_map.values() if len(v) != 1)
    )

    # ---------------------------------------------------------------- candidate rows
    notes = raw["notes"].astype(str)
    mentions_coach = notes.str.contains("coach", case=False, regex=False)
    dnp = notes.str.upper().str.contains(DNP_MARKER, regex=False)
    head_coach = notes.str.contains("Head Coach", regex=False)

    meas["measurements"]["source_rows_mentioning_coach_any_case"] = int(mentions_coach.sum())
    meas["measurements"]["source_rows_dnp_coaches_decision"] = int(dnp.sum())
    meas["measurements"]["source_rows_mentioning_head_coach"] = int(head_coach.sum())
    meas["measurements"]["source_rows_category_front_office"] = int(
        (raw["category"] == "front_office").sum()
    )
    meas["measurements"]["source_rows_front_office_without_head_coach"] = int(
        ((raw["category"] == "front_office") & ~head_coach).sum()
    )

    # Per-source-page provenance: does every season page contribute front-office rows at all?
    # A page with zero front_office rows is a CAPTURE GAP, not evidence that no change occurred.
    pages = raw[raw["source_page"].astype(str).str.startswith("bbref_transactions_")]
    meas["measurements"]["front_office_rows_by_source_page"] = {
        str(k): int((v["category"] == "front_office").sum())
        for k, v in pages.groupby("source_page")
    }
    meas["measurements"]["head_coach_rows_by_source_page"] = {
        str(k): int(v["notes"].astype(str).str.contains("Head Coach", regex=False).sum())
        for k, v in pages.groupby("source_page")
    }
    meas["measurements"]["all_rows_by_source_page_bbref"] = {
        str(k): int(len(v)) for k, v in pages.groupby("source_page")
    }
    meas["measurements"]["raw_source_pages_resident_in_worktree"] = sorted(
        p.name for p in (SRC_COACH_EVENTS.parent / "raw").glob("*")
    ) if (SRC_COACH_EVENTS.parent / "raw").exists() else []

    cand = raw[head_coach].copy()
    cand["source_row_index"] = cand.index.astype(int)

    # ---------------------------------------------------------------- parse
    records = []
    for _, r in cand.iterrows():
        note = str(r["notes"]).strip()
        parsed = None
        for rule_id, pat, etype in RULES:
            m = pat.match(note)
            if m:
                parsed = (rule_id, etype, m.groupdict())
                break
        if parsed is None:
            records.append(
                dict(
                    event_date=r["date"],
                    source_team_code=r["team"],
                    franchise="UNRESOLVED",
                    team_id=None,
                    coach_name="UNPARSED",
                    event_type="UNPARSED",
                    departure_mode="",
                    role_text="",
                    is_interim=None,
                    role_is_compound=None,
                    parse_rule_id="NONE",
                    source_dataset="data/injury_history/injury_history.csv",
                    source_page=r["source_page"],
                    source_row_index=int(r["source_row_index"]),
                    source_note_verbatim=note,
                    source_category=r["category"],
                )
            )
            continue

        rule_id, etype, g = parsed
        role = g["role"].strip()
        franchise = g["franchise"].strip()
        dep_mode = ""
        if etype == "DEPART":
            dep_mode = "RESIGN" if rule_id == "R2_DEPART_RESIGN" else "FIRED"
        records.append(
            dict(
                event_date=r["date"],
                source_team_code=r["team"],
                franchise=franchise,
                team_id=fran_to_id.get(franchise),
                coach_name=g["coach"].strip(),
                event_type=etype,
                departure_mode=dep_mode,
                role_text=role,
                is_interim=role.lower().startswith("interim"),
                role_is_compound=("&" in role) or (" and " in role.lower()),
                parse_rule_id=rule_id,
                source_dataset="data/injury_history/injury_history.csv",
                source_page=r["source_page"],
                source_row_index=int(r["source_row_index"]),
                source_note_verbatim=note,
                source_category=r["category"],
            )
        )

    ev = pd.DataFrame.from_records(records)
    ev["event_date"] = pd.to_datetime(ev["event_date"]).dt.date.astype(str)
    ev = ev.sort_values(["event_date", "source_row_index"]).reset_index(drop=True)
    ev.insert(0, "event_id", ["CE%03d" % (i + 1) for i in range(len(ev))])
    ev["effective_date_basis"] = "SOURCE_TRANSACTION_DATE"
    ev["cutoff_status"] = "CUTOFF_UNPROVEN"
    ev["admission_status"] = "NOT_ADMITTED"

    meas["measurements"]["events_emitted"] = int(len(ev))
    meas["measurements"]["events_unparsed"] = int((ev["event_type"] == "UNPARSED").sum())
    meas["measurements"]["events_by_rule"] = (
        ev["parse_rule_id"].value_counts().sort_index().to_dict()
    )
    meas["measurements"]["events_by_type"] = ev["event_type"].value_counts().to_dict()
    meas["measurements"]["events_unresolved_franchise"] = int(ev["team_id"].isna().sum())
    meas["measurements"]["events_date_min"] = ev["event_date"].min()
    meas["measurements"]["events_date_max"] = ev["event_date"].max()
    meas["measurements"]["distinct_coach_names"] = int(
        ev.loc[ev["event_type"] != "UNPARSED", "coach_name"].nunique()
    )
    meas["measurements"]["events_interim"] = int(ev["is_interim"].fillna(False).sum())
    meas["measurements"]["events_role_compound"] = int(
        ev["role_is_compound"].fillna(False).sum()
    )

    # season-page attribution vs calendar year of the event date
    ev["source_page_year"] = ev["source_page"].astype(str).str.extract(r"(\d{4})")[0]
    ev["event_year"] = ev["event_date"].str[:4]
    ymm = ev[ev["source_page_year"] != ev["event_year"]]
    meas["measurements"]["events_with_page_year_ne_event_year"] = int(len(ymm))
    meas["measurements"]["page_year_ne_event_year_detail"] = ymm[
        ["event_id", "event_date", "source_page", "franchise", "coach_name"]
    ].to_dict("records")

    # source-code vs parsed-franchise disagreement (entity-resolution hazard)
    dim_codes = (
        dim.groupby("franchise")["abbreviation"].agg(lambda s: sorted(set(s))).to_dict()
    )
    mism = []
    for _, r in ev[ev["event_type"] != "UNPARSED"].iterrows():
        codes = dim_codes.get(r["franchise"], [])
        if r["source_team_code"] not in codes:
            mism.append(
                {
                    "event_id": r["event_id"],
                    "franchise": r["franchise"],
                    "source_team_code": r["source_team_code"],
                    "team_dimension_codes": codes,
                }
            )
    meas["measurements"]["events_with_team_code_disagreement"] = len(mism)
    meas["measurements"]["team_code_disagreements"] = mism

    ev.to_csv(OUT_EVENTS, index=False)

    # ---------------------------------------------------------------- universe
    uni = pd.read_parquet(
        SRC_UNIVERSE, columns=["game_id", "season", "team_id", "game_date", "pace_resolved"]
    )
    meas["inputs"]["universe"] = {
        "path": str(SRC_UNIVERSE.relative_to(REPO_ROOT)).replace("\\", "/"),
        "sha256": sha256(SRC_UNIVERSE),
        "definition": UNIVERSE_DEFINITION,
        "all_rows_in_file": int(len(uni)),
        "all_games_in_file": int(uni["game_id"].nunique()),
        "in_declared_node_read_scope": True,
    }
    tg = uni[uni["pace_resolved"] == True][["game_id", "season", "team_id", "game_date"]].copy()
    tg = tg.drop_duplicates()
    tg["game_date"] = pd.to_datetime(tg["game_date"])
    tg = tg.rename(columns={"team_id": "offense_team_id"})
    meas["measurements"]["universe_team_game_rows"] = int(len(tg))
    meas["measurements"]["universe_game_clusters"] = int(tg["game_id"].nunique())

    ts = (
        tg.groupby(["season", "offense_team_id"])
        .agg(first_game_date=("game_date", "min"), last_game_date=("game_date", "max"),
             team_games=("game_id", "nunique"))
        .reset_index()
        .rename(columns={"offense_team_id": "team_id"})
    )
    meas["measurements"]["universe_team_seasons"] = int(len(ts))

    # ---------------------------------------------------------------- tenure spells
    ok = ev[ev["event_type"].isin(["HIRE", "DEPART"]) & ev["team_id"].notna()].copy()
    ok["team_id"] = ok["team_id"].astype("int64")
    ok["event_dt"] = pd.to_datetime(ok["event_date"])

    id_to_fran = {v: k for k, v in fran_to_id.items()}
    spells = []
    sid = 0
    for team_id, grp in ok.groupby("team_id"):
        grp = grp.sort_values(["event_dt", "source_row_index"])
        open_spell = None  # dict
        for _, e in grp.iterrows():
            if e["event_type"] == "DEPART":
                if open_spell is not None and open_spell["coach_name"] == e["coach_name"]:
                    open_spell["end_date"] = e["event_date"]
                    open_spell["end_basis"] = "EVENT_DATED_%s" % e["departure_mode"]
                    open_spell["end_event_id"] = e["event_id"]
                    spells.append(open_spell)
                    open_spell = None
                else:
                    if open_spell is not None:
                        # someone left who was not the coach we were tracking
                        open_spell["end_date"] = e["event_date"]
                        open_spell["end_basis"] = "INFERRED_BY_OTHER_DEPARTURE"
                        open_spell["end_event_id"] = e["event_id"]
                        open_spell["flags"].append("END_INFERRED_DEPARTURE_NAME_MISMATCH")
                        spells.append(open_spell)
                        open_spell = None
                    sid += 1
                    spells.append(
                        dict(
                            tenure_id="CT%03d" % sid,
                            team_id=int(team_id),
                            franchise=id_to_fran.get(int(team_id), "UNKNOWN"),
                            coach_name=e["coach_name"],
                            is_interim=bool(e["is_interim"]),
                            role_text=e["role_text"],
                            start_date="",
                            start_basis="LEFT_CENSORED_UNKNOWN",
                            start_event_id="",
                            end_date=e["event_date"],
                            end_basis="EVENT_DATED_%s" % e["departure_mode"],
                            end_event_id=e["event_id"],
                            flags=["START_LEFT_CENSORED_NO_HIRE_EVENT_IN_SOURCE"],
                        )
                    )
                continue

            # HIRE
            if open_spell is not None:
                open_spell["end_date"] = e["event_date"]
                open_spell["end_basis"] = "INFERRED_BY_SUCCESSION"
                open_spell["end_event_id"] = e["event_id"]
                open_spell["flags"].append("END_INFERRED_BY_SUCCESSION_NOT_DATED_IN_SOURCE")
                spells.append(open_spell)
                open_spell = None
            sid += 1
            open_spell = dict(
                tenure_id="CT%03d" % sid,
                team_id=int(team_id),
                franchise=id_to_fran.get(int(team_id), "UNKNOWN"),
                coach_name=e["coach_name"],
                is_interim=bool(e["is_interim"]),
                role_text=e["role_text"],
                start_date=e["event_date"],
                start_basis="EVENT_DATED_APPOINTMENT",
                start_event_id=e["event_id"],
                end_date="",
                end_basis="OPEN",
                end_event_id="",
                flags=[],
            )
        if open_spell is not None:
            open_spell["flags"].append("END_OPEN_NO_DEPARTURE_EVENT_IN_SOURCE")
            spells.append(open_spell)

    # franchises in the universe with no coaching events at all
    universe_team_ids = set(int(t) for t in ts["team_id"].unique())
    covered_ids = set(int(t) for t in ok["team_id"].unique())
    for tid in sorted(universe_team_ids - covered_ids):
        sid += 1
        spells.append(
            dict(
                tenure_id="CT%03d" % sid,
                team_id=int(tid),
                franchise=id_to_fran.get(int(tid), "UNKNOWN"),
                coach_name="UNKNOWN",
                is_interim=None,
                role_text="",
                start_date="",
                start_basis="LEFT_CENSORED_UNKNOWN",
                start_event_id="",
                end_date="",
                end_basis="OPEN",
                end_event_id="",
                flags=["NO_COACHING_EVENT_FOR_FRANCHISE_IN_SOURCE"],
            )
        )

    tn = pd.DataFrame.from_records(spells)
    tn = tn.sort_values(["franchise", "end_date", "start_date"]).reset_index(drop=True)

    # appointment-date vs first-game-coached ambiguity, measured against the universe
    lag_rows = []
    for i, s in tn.iterrows():
        if s["start_basis"] != "EVENT_DATED_APPOINTMENT":
            continue
        sd = pd.Timestamp(s["start_date"])
        nxt = tg[(tg["offense_team_id"] == s["team_id"]) & (tg["game_date"] >= sd)]
        if len(nxt) == 0:
            tn.at[i, "flags"] = list(s["flags"]) + ["NO_SUBSEQUENT_GAME_IN_UNIVERSE"]
            continue
        d = int((nxt["game_date"].min() - sd).days)
        lag_rows.append({"tenure_id": s["tenure_id"], "days": d})
        f = list(s["flags"])
        f.append("APPOINTMENT_DATE_IS_NOT_FIRST_GAME_COACHED")
        if d > 30:
            f.append("APPOINTMENT_TO_FIRST_GAME_GAP_GT_30D")
        tn.at[i, "flags"] = f

    tn["n_flags"] = tn["flags"].apply(len)
    tn["boundary_ambiguous"] = tn["n_flags"] > 0
    tn["flags"] = tn["flags"].apply(lambda x: "|".join(x))
    tn["cutoff_status"] = "CUTOFF_UNPROVEN"
    tn["admission_status"] = "NOT_ADMITTED"
    tn["source_dataset"] = "data/injury_history/injury_history.csv"
    tn.to_csv(OUT_TENURE, index=False)

    meas["measurements"]["tenure_spells"] = int(len(tn))
    meas["measurements"]["tenure_spells_boundary_ambiguous"] = int(tn["boundary_ambiguous"].sum())
    meas["measurements"]["tenure_spells_fully_dated_both_ends"] = int(
        ((tn["start_basis"] == "EVENT_DATED_APPOINTMENT") & tn["end_basis"].str.startswith("EVENT_DATED")).sum()
    )
    meas["measurements"]["tenure_spells_left_censored"] = int(
        (tn["start_basis"] == "LEFT_CENSORED_UNKNOWN").sum()
    )
    meas["measurements"]["tenure_spells_end_inferred_by_succession"] = int(
        (tn["end_basis"] == "INFERRED_BY_SUCCESSION").sum()
    )
    meas["measurements"]["tenure_spells_open_end"] = int((tn["end_basis"] == "OPEN").sum())
    if lag_rows:
        ld = pd.DataFrame(lag_rows)
        meas["measurements"]["appointment_to_first_game_days"] = {
            "n": int(len(ld)),
            "min": int(ld["days"].min()),
            "median": float(ld["days"].median()),
            "max": int(ld["days"].max()),
            "n_gt_30d": int((ld["days"] > 30).sum()),
        }

    # ---------------------------------------------------------------- coverage
    # Season windows, so that "carried forward" can be counted in seasons rather than assumed.
    season_open = ts.groupby("season")["first_game_date"].min().to_dict()

    def season_of(dt: pd.Timestamp) -> int:
        """League season a date belongs to: the latest season whose opener it precedes or equals
        is NOT used; we use the season whose window contains it, else the next season to open."""
        later = [s for s, o in season_open.items() if o >= dt]
        return int(min(later)) if later else int(max(season_open))

    cov = []
    for _, row in ts.iterrows():
        tid, season = int(row["team_id"]), int(row["season"])
        fg = row["first_game_date"]
        cands = []
        for _, s in tn.iterrows():
            if s["team_id"] != tid or s["coach_name"] == "UNKNOWN":
                continue
            st = pd.Timestamp(s["start_date"]) if s["start_date"] else None
            en = pd.Timestamp(s["end_date"]) if s["end_date"] else None
            if st is not None and st > fg:
                continue
            if en is not None and en < fg:
                continue
            cands.append(s)

        carried = None
        if len(cands) == 1:
            s = cands[0]
            name, tids = s["coach_name"], s["tenure_id"]
            st = pd.Timestamp(s["start_date"]) if s["start_date"] else None
            start_season = season_of(st) if st is not None else None
            carried = (season - start_season) if start_season is not None else None
            open_end = s["end_basis"] == "OPEN"

            if s["start_basis"] == "LEFT_CENSORED_UNKNOWN":
                status = "NAMED_START_LEFT_CENSORED"
            elif bool(s["is_interim"]) and carried and carried >= 1:
                # An interim appointment is NOT evidence of tenure in a later season.
                # Mark it; do not smooth it into coverage.
                status = "UNKNOWN_ONLY_INTERIM_SPELL_CARRIED_ACROSS_SEASON"
                name, tids = "", s["tenure_id"]
            elif open_end and carried and carried >= 1:
                status = "NAMED_OPEN_END_CARRIED_FORWARD_UNVERIFIED"
            else:
                status = "NAMED_EVENT_ANCHORED"
        elif len(cands) == 0:
            status, name, tids = "UNKNOWN_NO_SPELL_COVERS_OPENER", "", ""
        else:
            status = "AMBIGUOUS_MULTIPLE_SPELLS"
            name = " | ".join(c["coach_name"] for c in cands)
            tids = " | ".join(c["tenure_id"] for c in cands)

        cov.append(
            dict(
                season=season,
                team_id=tid,
                franchise=id_to_fran.get(tid, "UNKNOWN"),
                first_game_date=str(fg.date()),
                team_games=int(row["team_games"]),
                opening_head_coach=name,
                coverage_status=status,
                seasons_carried_forward=carried if carried is not None else "",
                tenure_ids=tids,
                cutoff_status="CUTOFF_UNPROVEN",
                admission_status="NOT_ADMITTED",
            )
        )
    cv = pd.DataFrame.from_records(cov).sort_values(["season", "franchise"])
    cv.to_csv(OUT_COVERAGE, index=False)

    vc = cv["coverage_status"].value_counts().to_dict()
    meas["measurements"]["coverage_team_seasons"] = int(len(cv))
    meas["measurements"]["coverage_by_status"] = vc
    named = int(cv["coverage_status"].str.startswith("NAMED").sum())
    anchored = int((cv["coverage_status"] == "NAMED_EVENT_ANCHORED").sum())
    meas["measurements"]["coverage_team_seasons_with_any_named_opening_coach"] = named
    meas["measurements"]["coverage_fraction_any_named"] = round(named / len(cv), 4)
    meas["measurements"]["coverage_team_seasons_event_anchored"] = anchored
    meas["measurements"]["coverage_fraction_event_anchored"] = round(anchored / len(cv), 4)
    meas["measurements"]["coverage_by_season"] = {
        str(k): v["coverage_status"].value_counts().to_dict()
        for k, v in cv.groupby("season")
    }
    meas["measurements"]["coverage_team_games_by_status"] = (
        cv.groupby("coverage_status")["team_games"].sum().to_dict()
    )

    # in-season coaching changes intersecting an actual played season window
    inseason = []
    for _, e in ok.iterrows():
        hit = ts[
            (ts["team_id"] == e["team_id"])
            & (ts["first_game_date"] <= e["event_dt"])
            & (ts["last_game_date"] >= e["event_dt"])
        ]
        if len(hit):
            inseason.append(
                {
                    "event_id": e["event_id"],
                    "season": int(hit.iloc[0]["season"]),
                    "franchise": e["franchise"],
                    "event_date": e["event_date"],
                    "event_type": e["event_type"],
                    "coach_name": e["coach_name"],
                }
            )
    meas["measurements"]["in_season_coaching_events"] = len(inseason)
    meas["measurements"]["in_season_coaching_events_detail"] = inseason

    # output integrity
    meas["outputs"] = {}
    for p in (OUT_EVENTS, OUT_TENURE, OUT_COVERAGE):
        meas["outputs"][p.name] = {"sha256": sha256(p), "bytes": p.stat().st_size}

    OUT_MEAS.write_text(json.dumps(meas, indent=2, default=str), encoding="utf-8")
    print(json.dumps(meas["measurements"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
