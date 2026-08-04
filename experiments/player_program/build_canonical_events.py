#!/usr/bin/env python3
"""build_canonical_events.py — the only sanctioned producer of `canonical_player_events/1`.

Normalises the legacy PlayByPlayV2 store and the modern CDN store into one event contract over
the 1,495-game universe. Registered before execution as `canonical_player_events_v1`.

**Nothing is fitted and nothing is scored.** No possession is linked, no denominator is chosen,
no model is trained. The producer FAILS CLOSED: a missing source column, an unmappable required
field, a store collision or a failed reconciliation writes no artifact.

Source fidelity is preserved. Where one schema carries less information than the other, the
canonical value is NULL with an explicit flag — never an inferred value presented as observed.

Run::

    python experiments/player_program/build_canonical_events.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "event_contract_v1"
LEGACY = ROOT / "data/playbyplay"
CDN = ROOT / "data/refresh_2026/pbp"
CONTRACT = ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet"

PARSER_VERSION = "canonical_player_events/1"
CONTRACT_VERSION = "player_event_contract/1"

REG_PERIOD_SEC = 600.0
OT_PERIOD_SEC = 300.0

#: frozen family crosswalk — legacy EVENTMSGTYPE
LEGACY_FAMILY = {
    1: "made_field_goal", 2: "missed_field_goal", 3: "free_throw", 4: "rebound",
    5: "turnover", 6: "foul", 7: "violation", 8: "substitution", 9: "timeout",
    10: "jump_ball", 11: "ejection", 12: "period_start", 13: "period_end",
    18: "replay_or_administrative",
}
#: frozen family crosswalk — CDN actionType
CDN_FAMILY = {
    "Made Shot": "made_field_goal", "Missed Shot": "missed_field_goal",
    "Free Throw": "free_throw", "Rebound": "rebound", "Turnover": "turnover",
    "Foul": "foul", "Violation": "violation", "Substitution": "substitution",
    "Timeout": "timeout", "Jump Ball": "jump_ball", "Ejection": "ejection",
    "Instant Replay": "replay_or_administrative",
}


class ProducerFailure(RuntimeError):
    """Any contract violation. Nothing is written."""


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _uid(game_id: str, system: str, sid) -> str:
    return hashlib.sha1(f"{game_id}|{system}|{sid}".encode()).hexdigest()[:16]


def _elapsed(period, remaining):
    period = np.asarray(period, dtype=float)
    remaining = np.asarray(remaining, dtype=float)
    before = np.where(period <= 4, REG_PERIOD_SEC * (period - 1),
                      4 * REG_PERIOD_SEC + OT_PERIOD_SEC * (period - 5))
    length = np.where(period <= 4, REG_PERIOD_SEC, OT_PERIOD_SEC)
    return before + (length - remaining)


_MMSS = re.compile(r"^\s*(\d+):(\d+(?:\.\d+)?)\s*$")
_ISO = re.compile(r"^PT(\d+)M(\d+(?:\.\d+)?)S$")


def _clock_legacy(s: pd.Series) -> np.ndarray:
    out = np.full(len(s), np.nan)
    for i, v in enumerate(s.astype("string").fillna("")):
        m = _MMSS.match(v)
        if m:
            out[i] = int(m.group(1)) * 60 + float(m.group(2))
    return out


def _clock_cdn(s: pd.Series) -> np.ndarray:
    out = np.full(len(s), np.nan)
    for i, v in enumerate(s.astype("string").fillna("")):
        m = _ISO.match(v)
        if m:
            out[i] = int(m.group(1)) * 60 + float(m.group(2))
    return out


def _pid(s: pd.Series) -> pd.Series:
    v = pd.to_numeric(s, errors="coerce")
    return v.where(v > 0).astype("Int64")


CANON_COLS = [
    "event_uid", "game_id", "canonical_event_seq", "source_system", "source_file",
    "source_file_sha256", "source_event_id", "source_row_index",
    "period", "clock_seconds_remaining", "elapsed_seconds",
    "event_team_id", "player1_id", "player2_id", "player3_id",
    "event_family", "event_subtype", "source_subtype_raw",
    "shot_made", "shot_value", "shot_distance", "shot_x", "shot_y",
    "rebound_type", "turnover_type", "foul_type",
    "steal_player_id", "assist_player_id", "block_player_id",
    "free_throw_seq_raw", "sub_player_in_id", "sub_player_out_id",
    "score_home", "score_away", "description",
    "mapping_rule_id", "parser_version", "contract_version",
    "quality", "key_fallback_used", "duplicate_source_key", "taxonomy_unmapped",
    "taxonomy_from_text", "clock_unparsed", "coordinates_supported",
    "substitution_in_supported", "assist_supported", "steal_block_form",
    "free_throw_result_supported", "score_out_of_sequence",
]


def normalise_legacy(game_id: str, path: Path) -> pd.DataFrame:
    d = pd.read_parquet(path)
    need = ["EVENTNUM", "PERIOD", "PCTIMESTRING", "EVENTMSGTYPE", "EVENTMSGACTIONTYPE"]
    miss = [c for c in need if c not in d.columns]
    if miss:
        raise ProducerFailure(f"{path.name}: missing legacy columns {miss}")
    n = len(d)
    fam = d["EVENTMSGTYPE"].map(LEGACY_FAMILY)
    unmapped = fam.isna()
    fam = fam.fillna("unknown")
    rem = _clock_legacy(d["PCTIMESTRING"])
    p1, p2, p3 = _pid(d["PLAYER1_ID"]), _pid(d["PLAYER2_ID"]), _pid(d["PLAYER3_ID"])
    desc = (d.get("HOMEDESCRIPTION").astype("string")
            .fillna(d.get("VISITORDESCRIPTION").astype("string"))
            .fillna(d.get("NEUTRALDESCRIPTION").astype("string")))
    sid = d["EVENTNUM"]
    dup = sid.duplicated(keep=False)

    out = pd.DataFrame({
        "game_id": game_id,
        "source_system": "nba_playbyplayv2",
        "source_file": path.name,
        "source_event_id": sid.astype(str),
        "source_row_index": np.arange(n),
        "period": pd.to_numeric(d["PERIOD"], errors="coerce").astype("Int64"),
        "clock_seconds_remaining": rem,
        "event_team_id": _pid(d.get("PLAYER1_TEAM_ID", pd.Series([pd.NA] * n))),
        "player1_id": p1, "player2_id": p2, "player3_id": p3,
        "event_family": fam,
        "event_subtype": "action_" + d["EVENTMSGACTIONTYPE"].astype("Int64").astype(str),
        "source_subtype_raw": (d["EVENTMSGTYPE"].astype("Int64").astype(str) + "/"
                               + d["EVENTMSGACTIONTYPE"].astype("Int64").astype(str)),
        "shot_made": np.where(fam == "made_field_goal", True,
                              np.where(fam == "missed_field_goal", False, None)),
        "shot_value": pd.NA, "shot_distance": np.nan, "shot_x": np.nan, "shot_y": np.nan,
        "turnover_type": pd.NA, "foul_type": pd.NA, "free_throw_seq_raw": pd.NA,
        "score_home": pd.NA, "score_away": pd.NA,
        "description": desc,
        "mapping_rule_id": "legacy_eventmsgtype/1",
        "quality": np.where(unmapped | dup | np.isnan(rem), "degraded", "ok"),
        "key_fallback_used": False,
        "duplicate_source_key": dup.to_numpy(),
        "taxonomy_unmapped": unmapped.to_numpy(),
        "taxonomy_from_text": False,
        "clock_unparsed": np.isnan(rem),
        "coordinates_supported": False,
        "substitution_in_supported": True,
        "assist_supported": True,
        "steal_block_form": "attribution",
        "free_throw_result_supported": False,
        "score_out_of_sequence": False,
    })
    # legacy attributions
    out["steal_player_id"] = p2.where(fam == "turnover")
    out["assist_player_id"] = p2.where(fam == "made_field_goal")
    out["block_player_id"] = p3.where(fam == "missed_field_goal")
    out["sub_player_out_id"] = p1.where(fam == "substitution")
    out["sub_player_in_id"] = p2.where(fam == "substitution")
    # team rebound: no player identity on a rebound row
    out["rebound_type"] = np.where(fam == "rebound",
                                   np.where(p1.isna(), "team", "unresolved"), None)
    return out


def normalise_cdn(game_id: str, path: Path) -> pd.DataFrame:
    d = pd.read_parquet(path)
    need = ["actionId", "period", "clock", "actionType", "subType", "personId"]
    miss = [c for c in need if c not in d.columns]
    if miss:
        raise ProducerFailure(f"{path.name}: missing CDN columns {miss}")
    n = len(d)
    at = d["actionType"].astype("string").fillna("")
    st = d["subType"].astype("string").fillna("")
    desc = d["description"].astype("string")
    fam = at.map(CDN_FAMILY)
    from_text = pd.Series(False, index=d.index)

    # period start / end
    is_period = at.str.lower() == "period"
    fam = fam.where(~is_period, st.str.lower().map({"start": "period_start", "end": "period_end"}))
    # empty actionType: the source carries standalone STEAL / BLOCK rows, identified only in text
    empty = at == ""
    txt = desc.fillna("").str.upper()
    fam = fam.where(~(empty & txt.str.contains("STEAL")), "steal")
    fam = fam.where(~(empty & txt.str.contains("BLOCK")), "block")
    from_text |= empty & (txt.str.contains("STEAL") | txt.str.contains("BLOCK"))
    unmapped = fam.isna()
    fam = fam.fillna("unknown")

    rem = _clock_cdn(d["clock"])
    pid = _pid(d["personId"])
    sid = d["actionId"]
    dup = sid.duplicated(keep=False)

    is_fg = pd.to_numeric(d.get("isFieldGoal", 0), errors="coerce").fillna(0) == 1
    x = pd.to_numeric(d.get("xLegacy"), errors="coerce").where(is_fg)
    y = pd.to_numeric(d.get("yLegacy"), errors="coerce").where(is_fg)
    dist = pd.to_numeric(d.get("shotDistance"), errors="coerce").where(is_fg)
    sres = d.get("shotResult", pd.Series([pd.NA] * n)).astype("string")

    out = pd.DataFrame({
        "game_id": game_id,
        "source_system": "nba_cdn_playbyplay",
        "source_file": path.name,
        "source_event_id": sid.astype(str),
        "source_row_index": np.arange(n),
        "period": pd.to_numeric(d["period"], errors="coerce").astype("Int64"),
        "clock_seconds_remaining": rem,
        "event_team_id": _pid(d.get("teamId", pd.Series([pd.NA] * n))),
        "player1_id": pid, "player2_id": pd.NA, "player3_id": pd.NA,
        "event_family": fam,
        "event_subtype": st.replace("", pd.NA),
        "source_subtype_raw": at + "/" + st,
        "shot_made": np.where(sres == "Made", True, np.where(sres == "Missed", False, None)),
        "shot_value": pd.to_numeric(d.get("shotValue"), errors="coerce").where(is_fg).astype("Int64"),
        "shot_distance": dist, "shot_x": x, "shot_y": y,
        "turnover_type": st.where(fam == "turnover"),
        "foul_type": st.where(fam == "foul"),
        "free_throw_seq_raw": st.where(fam == "free_throw"),
        "steal_player_id": pd.NA, "assist_player_id": pd.NA, "block_player_id": pd.NA,
        "sub_player_out_id": pid.where(fam == "substitution"),
        "sub_player_in_id": pd.NA,
        "score_home": pd.to_numeric(d.get("scoreHome"), errors="coerce").astype("Int64"),
        "score_away": pd.to_numeric(d.get("scoreAway"), errors="coerce").astype("Int64"),
        "description": desc,
        "mapping_rule_id": "cdn_actiontype/1",
        "quality": np.where(unmapped | dup | np.isnan(rem), "degraded", "ok"),
        "key_fallback_used": False,
        "duplicate_source_key": dup.to_numpy(),
        "taxonomy_unmapped": unmapped.to_numpy(),
        "taxonomy_from_text": from_text.to_numpy(),
        "clock_unparsed": np.isnan(rem),
        "coordinates_supported": True,
        "substitution_in_supported": False,
        "assist_supported": False,
        "steal_block_form": "standalone_row",
        "free_throw_result_supported": False,
        "score_out_of_sequence": False,
    })
    out["rebound_type"] = np.where(fam == "rebound",
                                   np.where(pid.isna(), "team", "unresolved"), None)
    return out


def build_game(game_id: str, path: Path, source: str) -> pd.DataFrame:
    """Normalise ONE game and apply keying, ordering and provenance.

    The single code path used by both the producer and the validator, so a determinism check
    cannot pass merely because two copies of the logic happen to agree.
    """
    df = normalise_legacy(game_id, path) if source == "legacy" else normalise_cdn(game_id, path)
    df["source_file_sha256"] = _sha(path)
    df["elapsed_seconds"] = _elapsed(df["period"].astype(float), df["clock_seconds_remaining"])
    # tie-break on the source event id NUMERICALLY. A string sort would order '10' before '9'
    # and scramble simultaneous events.
    df["_sid_num"] = pd.to_numeric(df["source_event_id"], errors="coerce")
    df = df.sort_values(["period", "elapsed_seconds", "_sid_num", "source_event_id"],
                        kind="mergesort").reset_index(drop=True)
    df = df.drop(columns="_sid_num")
    df["canonical_event_seq"] = np.arange(len(df))
    # registered fallback: a non-unique source event id keys on
    # (period, clock_seconds_remaining, file_row_index) instead, degraded and flagged
    dup_mask = df["source_event_id"].duplicated(keep=False)
    key = df["source_event_id"].astype(str)
    if dup_mask.any():
        fb = ("fb:" + df["period"].astype(str) + ":"
              + df["clock_seconds_remaining"].round(2).astype(str) + ":"
              + df["source_row_index"].astype(str))
        key = key.where(~dup_mask, fb)
        df.loc[dup_mask, "key_fallback_used"] = True
        df.loc[dup_mask, "quality"] = "degraded"
    df["event_uid"] = [_uid(game_id, s, k) for s, k in zip(df["source_system"], key)]
    # Source anomaly, preserved and LABELLED rather than reordered: some scores regress in
    # source order -- replay rows carry a post-correction snapshot, and technical free throws at a
    # period boundary are emitted before the period_start row that carries the pre-technical score.
    have = df["score_home"].notna() & df["score_away"].notna()
    if have.any():
        sh = df.loc[have, "score_home"].astype(float)
        sa = df.loc[have, "score_away"].astype(float)
        dec = (sh.diff() < 0) | (sa.diff() < 0)
        idx = dec[dec].index
        if len(idx):
            df.loc[idx, "score_out_of_sequence"] = True
            df.loc[idx, "quality"] = "degraded"
    df["parser_version"] = PARSER_VERSION
    df["contract_version"] = CONTRACT_VERSION
    return df.reindex(columns=CANON_COLS)


def main() -> int:
    started = _utc()
    producer_sha_before = _sha(Path(__file__))
    OUT.mkdir(parents=True, exist_ok=True)

    c = pd.read_parquet(CONTRACT, columns=["game_id", "game_date", "season"]).drop_duplicates("game_id")
    c["game_id"] = c["game_id"].astype(str)
    universe = sorted(c["game_id"])

    legacy_files = {re.search(r"pbp_(\d+)", p.name).group(1): p
                    for p in LEGACY.glob("pbp_*.parquet")}
    cdn_files = {re.search(r"pbp_(\d+)", p.name).group(1): p for p in CDN.glob("pbp_*.parquet")}
    both = set(legacy_files) & set(cdn_files)
    if both:
        raise ProducerFailure(f"{len(both)} games appear in BOTH stores; precedence must not be "
                              f"exercised silently: {sorted(both)[:5]}")

    frames, per_game, missing = [], [], []
    shas: dict[str, str] = {}
    for g in universe:
        if g in legacy_files:
            p, src = legacy_files[g], "legacy"
        elif g in cdn_files:
            p, src = cdn_files[g], "cdn"
        else:
            missing.append(g)
            continue
        raw_n = len(pd.read_parquet(p, columns=None))
        df = build_game(g, p, src)
        shas[p.name] = df["source_file_sha256"].iloc[0]
        frames.append(df)
        per_game.append({"game_id": g, "source_system": df["source_system"].iloc[0],
                         "raw_rows": raw_n, "canonical_rows": len(df)})

    if missing:
        raise ProducerFailure(f"{len(missing)} universe games have no event file")

    events = pd.concat(frames, ignore_index=True)
    if events["event_uid"].duplicated().any():
        raise ProducerFailure("canonical event_uid is not unique")

    pg = pd.DataFrame(per_game)
    if int(pg["raw_rows"].sum()) != int(pg["canonical_rows"].sum()):
        raise ProducerFailure("row counts do not reconcile to the raw sources")

    producer_sha_after = _sha(Path(__file__))
    if producer_sha_before != producer_sha_after:
        raise ProducerFailure("the producer changed while it was running")

    events.to_parquet(OUT / "canonical_player_events_v1.parquet", index=False)

    fam = events.groupby(["source_system", "event_family"]).size().unstack(fill_value=0)
    unmapped_vals = (events[events["taxonomy_unmapped"]]
                     .groupby(["source_system", "source_subtype_raw"]).size())
    receipt = {
        "schema": "canonical_event_receipt/1",
        "artifact_id": "canonical_player_events/1",
        "experiment_id": "canonical_player_events_v1",
        "generated_utc": started, "finished_utc": _utc(),
        "nothing_fitted": True, "nothing_scored": True, "no_possession_linking": True,
        "producer": {"path": "experiments/player_program/build_canonical_events.py",
                     "sha256_before": producer_sha_before, "sha256_after": producer_sha_after},
        "parser_version": PARSER_VERSION, "contract_version": CONTRACT_VERSION,
        "universe_games": len(universe),
        "games_by_source": pg.groupby("source_system").size().to_dict(),
        "raw_rows_by_source": pg.groupby("source_system")["raw_rows"].sum().to_dict(),
        "canonical_rows": int(len(events)),
        "row_reconciliation": {"raw_total": int(pg["raw_rows"].sum()),
                               "canonical_total": int(pg["canonical_rows"].sum()),
                               "closes": True},
        "family_counts_by_source": fam.to_dict(),
        "unmapped_raw_values": {f"{k[0]}|{k[1]}": int(v) for k, v in unmapped_vals.items()},
        "unmapped_row_total": int(events["taxonomy_unmapped"].sum()),
        "taxonomy_from_text_rows": int(events["taxonomy_from_text"].sum()),
        "quality_counts": events["quality"].value_counts().to_dict(),
        "flag_counts": {c: int(events[c].sum()) for c in
                        ["key_fallback_used", "duplicate_source_key", "taxonomy_unmapped",
                         "taxonomy_from_text", "clock_unparsed", "score_out_of_sequence"]},
        "coverage": {
            "coordinates_supported_rows": int(events["coordinates_supported"].sum()),
            "rows_with_shot_coordinates": int(events["shot_x"].notna().sum()),
            "substitution_in_supported_rows": int(events["substitution_in_supported"].sum()),
            "assist_supported_rows": int(events["assist_supported"].sum()),
            "rebound_type_counts": events["rebound_type"].value_counts(dropna=False).to_dict(),
        },
        "artifact_sha256": _sha(OUT / "canonical_player_events_v1.parquet"),
        "source_file_sha256_count": len(shas),
    }
    (OUT / "EVENT_NORMALISATION_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, default=str), encoding="utf-8")
    (OUT / "event_crosswalk.json").write_text(json.dumps(
        {"legacy_EVENTMSGTYPE": LEGACY_FAMILY, "cdn_actionType": CDN_FAMILY,
         "cdn_period_subtype": {"start": "period_start", "end": "period_end"},
         "cdn_empty_actiontype": {"STEAL in description": "steal",
                                  "BLOCK in description": "block",
                                  "field_origin": "parsed"}},
        indent=2), encoding="utf-8")

    print(f"canonical events: {len(events):,} rows over {len(universe)} games")
    print(f"  by source: {receipt['games_by_source']}")
    print(f"  unmapped rows: {receipt['unmapped_row_total']:,}  "
          f"from-text: {receipt['taxonomy_from_text_rows']:,}")
    print(f"  quality: {receipt['quality_counts']}")
    print(f"  shot coordinates on {receipt['coverage']['rows_with_shot_coordinates']:,} rows")
    print(f"  artifact: {OUT / 'canonical_player_events_v1.parquet'}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ProducerFailure as exc:
        print(f"PRODUCER FAILED CLOSED: {exc}", file=sys.stderr)
        sys.exit(2)
