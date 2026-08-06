"""Idempotent operational runner for the W2-C1 challenger arm.

DESIGN: THIS RUNNER MIRRORS THE BASE LOG. It never invents its own obligations.
For each base forecast record in the official chain it asks: does a paired W2-C1
record exist? If not, and the record's cutoff has not passed, it writes one from the
same slate-date data snapshot.

That single choice buys four of the required properties structurally rather than by
checking for them:
    pairing        a challenger record cannot exist without its base record
    no orphans     nothing to mirror means nothing is written
    idempotency    an existing pair is skipped; re-running changes nothing
    identical rows structural and W2-C1 are scored on the same games and cutoffs

It NEVER writes the official chain. daily_forecast.py owns that. If the base job did
not run, this runner writes nothing and the coverage auditor reports the miss --
which is correct: a challenger record for a cutoff the incumbent never served would
give one model an easier subset.

Usage:
    python prospective_pair/run_prospective.py            # act
    python prospective_pair/run_prospective.py --dry-run  # decide, write nothing
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import alt_model_log as alog                                    # noqa: E402
from alt_model_log import (                                     # noqa: E402
    AltLogError, DuplicateArmForecastError, LateForecastError,
    OrphanForecastError, append_arm_forecast, base_record_hash, read_official,
)
from coverage_audit import CONTRACT_LABELS, TEAMS, _slate_date, _utc  # noqa: E402
from w2c1_forecast import (                                     # noqa: E402
    MODEL_ID, forecast_slate, model_version_hash,
)

TEAM_MASTER = REPO / "data" / "masters" / "master_team.parquet"
RUN_LOG = REPO / "forecasts" / "prospective_pair_runs.jsonl"
LABEL_HOURS = dict(CONTRACT_LABELS)


def git_head() -> str:
    """Read .git/HEAD by file, never by running git."""
    try:
        h = (REPO / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if h.startswith("ref: "):
            ref = REPO / ".git" / h[5:]
            if ref.exists():
                return "git:" + ref.read_text(encoding="utf-8").strip()
            for ln in (REPO / ".git" / "packed-refs").read_text(encoding="utf-8").splitlines():
                if ln.endswith(" " + h[5:]):
                    return "git:" + ln.split()[0]
            return "git:unresolved"
        return "git:" + h
    except OSError:
        return "git:unavailable"


def latest_tips() -> dict:
    """(slate_date, home, away) -> (tip_utc, market fields) from the newest capture."""
    out = {}
    for f in sorted(glob.glob(str(REPO / "data" / "odds_capture" / "live_*.json"))):
        try:
            games = json.load(open(f, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        cap = _utc(datetime.strptime(Path(f).stem.replace("live_", ""), "%Y%m%dT%H%M%SZ"))
        for g in games:
            h, a = TEAMS.get(g.get("home_team")), TEAMS.get(g.get("away_team"))
            if not h or not a:
                continue
            tip = _utc(g["commence_time"])
            line = price = book = None
            for bm in g.get("bookmakers", []):
                for mk in bm.get("markets", []):
                    if mk.get("key") != "spreads":
                        continue
                    for o in mk.get("outcomes", []):
                        if TEAMS.get(o.get("name")) == h and o.get("point") is not None:
                            line, price, book = -float(o["point"]), o.get("price"), bm.get("key")
            out[(_slate_date(tip), h, a)] = {
                "tip": tip, "market_line": line, "market_price": price,
                "market_book": book, "market_captured_at": cap,
                "market_source": Path(f).name,
            }
    return out


def snapshot_hash(slate_date: str) -> str:
    """Hash of the exact training frame W2-C1 will see for this slate date."""
    tm = pd.read_parquet(TEAM_MASTER)
    tm["game_date"] = pd.to_datetime(tm.game_date)
    d = pd.Timestamp(slate_date)
    prior = tm[(tm.season_type == "Regular Season") & (tm.game_date < d)]
    key = "|".join(f"{r.game_id}:{r.team_id}:{r.pts}" for r in
                   prior.sort_values(["game_date", "game_id", "team_id"]).itertuples())
    return hashlib.sha256(key.encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="decide and report; write nothing")
    ap.add_argument("--base-log", default=None,
                    help="base chain to mirror (default: the official log). Used to "
                         "exercise the pipeline end-to-end against the dry-run chain.")
    ap.add_argument("--arm-log", default=None, help="arm chain to write (default: the companion log)")
    args = ap.parse_args()
    if args.arm_log:
        alog.DEFAULT_ALT_LOG = Path(args.arm_log)

    now = datetime.now(timezone.utc)
    started = now.isoformat()
    official = read_official(args.base_log)
    tips = latest_tips()
    actions, failures = [], []

    print("=" * 96)
    print("PROSPECTIVE PAIR RUNNER  %s  model=%s hash=%s%s"
          % (started, MODEL_ID, model_version_hash()[:16], "  [DRY RUN]" if args.dry_run else ""))
    print("=" * 96)
    print("base records in official chain: %d" % len(official))

    snap_cache: dict[str, str] = {}
    for idx, rec in enumerate(official):
        c = rec.get("core_only_prediction") or {}
        gid, label = str(rec["game_id"]), rec["decision_time_label"]
        h, a = c.get("home_team"), c.get("away_team")
        tag = f"#{idx} {h} v {a} @ {label}"

        if c.get("status", "forecast") != "forecast":
            actions.append({"base_idx": idx, "tag": tag, "action": "skip",
                            "why": "base record is an explicit no-forecast; nothing to pair"})
            continue
        if alog.already_logged(gid, label, MODEL_ID, alog.DEFAULT_ALT_LOG):
            actions.append({"base_idx": idx, "tag": tag, "action": "already_logged",
                            "why": "idempotent: pair exists"})
            continue
        if label not in LABEL_HOURS:
            actions.append({"base_idx": idx, "tag": tag, "action": "declined",
                            "why": f"unregistered decision time {label!r}"})
            continue

        ev = (c.get("provenance") or {}).get("event_time")
        slate = None
        meta = None
        if ev:
            tip = _utc(ev)
            slate = _slate_date(tip)
            meta = tips.get((slate, h, a))
        if meta is None:
            for (sd, hh, aa), m in tips.items():
                if hh == h and aa == a and (slate is None or sd == slate):
                    slate, meta = sd, m
                    break
        if meta is None:
            actions.append({"base_idx": idx, "tag": tag, "action": "declined",
                            "why": "no tip time available for this game; cannot place a cutoff"})
            continue

        tip = meta["tip"]
        cutoff = tip - timedelta(hours=LABEL_HOURS[label])
        if now > cutoff:
            actions.append({"base_idx": idx, "tag": tag, "action": "late_prevented",
                            "why": (f"cutoff {cutoff.isoformat()} already passed at "
                                    f"{now.isoformat()}; a forecast made after its own cutoff "
                                    "would carry information the cutoff excludes"),
                            "cutoff": cutoff.isoformat()})
            continue

        try:
            if slate not in snap_cache:
                snap_cache[slate] = snapshot_hash(slate)

            row = None
            tm = pd.read_parquet(TEAM_MASTER)
            ab2id = tm[["team_id", "team_abbreviation"]].drop_duplicates() \
                .set_index("team_abbreviation").team_id.to_dict()
            hid, aid = ab2id.get(h), ab2id.get(a)
            if hid is None or aid is None:
                actions.append({"base_idx": idx, "tag": tag, "action": "declined",
                                "why": f"unknown team abbreviation(s) {h}/{a}"})
                continue
            # The matchup MUST be supplied explicitly. Tonight's games are not in the
            # master yet -- it holds completed games -- so deriving the slate from it
            # would silently emit a no-forecast for every future game, which is the
            # one thing this arm exists to produce.
            preds = forecast_slate(slate, str(TEAM_MASTER), matchups=[(hid, aid)])
            row = preds.iloc[0] if len(preds) else None
            common = dict(
                game_id=gid, decision_time_label=label, cutoff_utc=cutoff, tip_utc=tip,
                base_record_idx=idx, base_record_sha256=base_record_hash(rec),
                model_id=MODEL_ID, model_hash=model_version_hash(),
                data_snapshot_hash=snap_cache[slate],
                producer=f"prospective_pair/run_prospective.py {git_head()}",
                market_line=meta["market_line"], market_price=meta["market_price"],
                market_book=meta["market_book"], market_source=meta["market_source"],
                market_captured_at=meta["market_captured_at"], created_at_utc=now)
            if row is None or not bool(row.eligible):
                why = ("no prediction row produced" if row is None
                       else str(row.ineligible_reason))
                plan = {"base_idx": idx, "tag": tag, "action": "no_forecast", "why": why}
                if not args.dry_run:
                    append_arm_forecast(status="no_forecast", no_forecast_reason=why, **common)
            else:
                plan = {"base_idx": idx, "tag": tag, "action": "forecast",
                        "cutoff": cutoff.isoformat(),
                        "home": round(row.home_score, 3), "away": round(row.away_score, 3),
                        "margin": round(row.margin, 3), "total": round(row.total, 3)}
                if not args.dry_run:
                    r2 = append_arm_forecast(
                        status="forecast", home_score=row.home_score, away_score=row.away_score,
                        margin=row.margin, total=row.total, **common)
                    plan["arm_record_idx"] = r2["record_idx"]
                    plan["arm_record_sha256"] = r2["record_sha256"]
            actions.append(plan)
        except (OrphanForecastError, LateForecastError, DuplicateArmForecastError) as exc:
            actions.append({"base_idx": idx, "tag": tag, "action": "refused",
                            "why": f"{type(exc).__name__}: {exc}"})
        except (AltLogError, OSError, ValueError, KeyError) as exc:
            failures.append({"base_idx": idx, "tag": tag, "error": repr(exc),
                             "traceback": traceback.format_exc()[-800:]})
            actions.append({"base_idx": idx, "tag": tag, "action": "FAILED", "why": repr(exc)})

    for p in actions:
        extra = ""
        if p["action"] == "forecast":
            extra = "  home %.1f away %.1f margin %+.2f total %.1f" % (
                p["home"], p["away"], p["margin"], p["total"])
        print("  %-14s %-34s %s%s" % (p["action"], p["tag"], p.get("why", "")[:60], extra))

    rep = alog.verify_chain(alog.DEFAULT_ALT_LOG, check_pairing=not args.base_log)
    counts: dict = {}
    for p in actions:
        counts[p["action"]] = counts.get(p["action"], 0) + 1
    receipt = {
        "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
        "dry_run": bool(args.dry_run), "model_id": MODEL_ID,
        "model_hash": model_version_hash(), "producer": git_head(),
        "base_records_seen": len(official), "actions": counts,
        "failures": failures, "arm_chain_ok": rep.ok, "arm_chain_n": rep.n_records,
        "arm_chain_tip": rep.tip_sha256, "detail": actions,
    }
    print("\n  %s" % ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print("  arm chain: ok=%s n=%d tip=%s" % (rep.ok, rep.n_records, str(rep.tip_sha256)[:16]))
    if failures:
        print("  FAILURES: %d (recorded in the run receipt)" % len(failures))
    if not args.dry_run:
        RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(RUN_LOG, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(receipt, sort_keys=True, default=str) + "\n")
        print("  receipt appended to %s" % RUN_LOG.name)
    return 1 if failures or not rep.ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
