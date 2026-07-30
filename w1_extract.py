#!/usr/bin/env python3
"""
W1 news -> availability EXTRACTION layer (ROADMAP Phase 2a).

The LLM is an auditable extraction layer ONLY (per ROADMAP + the evaluation
constitution): it pulls structured availability signals out of captured news
text with exact quoted evidence. It never invents probabilities or minutes -
those belong to the downstream statistical models (regime rules apply).

Input:  data/news_capture/news_items.csv   (from news_capture_daily.py)
Output: data/w1_extractions/extractions.jsonl   (append-only, one record per item)
        data/w1_extractions/extractions.csv     (flat per-player view, regenerated)
        data/w1_extractions/raw/<runstamp>.jsonl (raw API responses, auditability)

Modes:
  python w1_extract.py                # incremental: extract new items (direct calls)
  python w1_extract.py --backlog      # all unextracted items via the Batches API (50% cost)
  python w1_extract.py --limit N      # cap items this run (testing)

Key: ANTHROPIC_API_KEY env var, else ANTHROPIC_API_KEY= line in repo-root .env
(git-ignored). Model: claude-opus-5 (change with --model; cost note in ROADMAP).
Idempotent: items are keyed by sha1(source|url); already-extracted items skip.
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
NEWS_CSV = ROOT / "data" / "news_capture" / "news_items.csv"
OUTDIR = ROOT / "data" / "w1_extractions"
RAWDIR = OUTDIR / "raw"
JSONL = OUTDIR / "extractions.jsonl"
FLAT_CSV = OUTDIR / "extractions.csv"

TEAMS = ["Atlanta Dream", "Chicago Sky", "Connecticut Sun", "Dallas Wings",
         "Golden State Valkyries", "Indiana Fever", "Las Vegas Aces",
         "Los Angeles Sparks", "Minnesota Lynx", "New York Liberty",
         "Phoenix Mercury", "Portland Fire", "Seattle Storm", "Toronto Tempo",
         "Washington Mystics"]

SYSTEM_PROMPT = """You extract player-availability information from WNBA news items for a \
sports modeling pipeline. You are an extraction layer, not a forecaster: report only what \
the text states or directly attributes, with exact quotes as evidence. Never estimate \
probabilities, minutes, or outcomes. Never infer a status the text does not support; use \
"unknown" and mark speculation instead.

WNBA teams (use these exact names): """ + "; ".join(TEAMS) + """.

For each news item you receive, identify every player about whom the item carries \
availability-relevant information: injury or illness, game status designations \
(out/doubtful/questionable/probable/available), returns, absences, rest, suspensions, \
roster moves affecting availability, minutes restrictions, or coach comments about a \
player's readiness. General performance news (points scored, trade rumors without \
availability impact) is NOT availability-relevant. An item may have zero relevant players."""

# Prompt version = hash of the extraction-shaping text; recorded per record so
# regime-B/D consumers can filter by extraction methodology.
PROMPT_VERSION = hashlib.sha1(SYSTEM_PROMPT.encode()).hexdigest()[:12]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant": {"type": "boolean",
                     "description": "true if the item carries availability info for any player"},
        "players": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "player_name": {"type": "string"},
                    "team": {"type": "string",
                             "description": "one of the 15 exact team names, or 'unknown'"},
                    "status_signal": {"type": "string",
                                      "enum": ["out", "doubtful", "questionable", "probable",
                                               "available", "returning", "day_to_day",
                                               "season_ending", "unknown"]},
                    "body_part": {"type": "string",
                                  "description": "injured body part or condition, or 'none stated'"},
                    "reported_limitation": {"type": "string",
                                            "description": "any stated restriction (e.g. minutes limit), or 'none stated'"},
                    "quoted_evidence": {"type": "string",
                                        "description": "EXACT text from the item supporting this extraction"},
                    "source_tier": {"type": "string",
                                    "enum": ["player", "coach", "team_official",
                                             "league_official", "beat_reporter",
                                             "aggregator", "unknown"]},
                    "game_date_referenced": {"type": "string",
                                             "description": "YYYY-MM-DD if a specific game is referenced, else 'none'"},
                    "is_speculation": {"type": "boolean",
                                       "description": "true if the signal is speculative/secondhand rather than an official or directly-attributed statement"}
                },
                "required": ["player_name", "team", "status_signal", "body_part",
                             "reported_limitation", "quoted_evidence", "source_tier",
                             "game_date_referenced", "is_speculation"],
                "additionalProperties": False
            }
        }
    },
    "required": ["relevant", "players"],
    "additionalProperties": False
}


def api_key():
    import os
    k = os.getenv("ANTHROPIC_API_KEY")
    if k:
        return k
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("No ANTHROPIC_API_KEY in environment or .env - add it to the "
             "git-ignored .env at the repo root.")


def item_key(row) -> str:
    return hashlib.sha1(f"{row.source}|{row.url}".encode()).hexdigest()


def load_done() -> set:
    if not JSONL.exists():
        return set()
    done = set()
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                done.add(json.loads(line)["item_key"])
            except Exception:
                continue
    return done


def item_prompt(row) -> str:
    return (f"News item (source: {row.source}; published: {row.published_utc}; "
            f"captured: {row.capture_utc}):\n"
            f"TITLE: {row.title}\n"
            f"TEXT: {str(row.summary_text)[:4000]}")


def build_params(row, model):
    return {
        "model": model,
        "max_tokens": 2000,
        "system": [{"type": "text", "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"}}],
        "output_config": {"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        "messages": [{"role": "user", "content": item_prompt(row)}],
    }


def record_from(row, key, payload, model, raw_text):
    return {
        "item_key": key,
        "source": row.source,
        "url": row.url,
        "title": row.title,
        "published_utc": row.published_utc,
        "capture_utc": row.capture_utc,
        "extracted_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "relevant": payload.get("relevant"),
        "players": payload.get("players", []),
        "raw_len": len(raw_text),
    }


def write_records(records, raw_rows, runstamp):
    RAWDIR.mkdir(parents=True, exist_ok=True)
    with open(RAWDIR / f"run_{runstamp}.jsonl", "a", encoding="utf-8") as f:
        for r in raw_rows:
            f.write(json.dumps(r) + "\n")
    with open(JSONL, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def rebuild_flat():
    rows = []
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            for p in rec.get("players") or []:
                rows.append({
                    "extracted_utc": rec["extracted_utc"],
                    "published_utc": rec["published_utc"],
                    "capture_utc": rec["capture_utc"],
                    "source": rec["source"],
                    "player_name": p.get("player_name"),
                    "team": p.get("team"),
                    "status_signal": p.get("status_signal"),
                    "body_part": p.get("body_part"),
                    "reported_limitation": p.get("reported_limitation"),
                    "source_tier": p.get("source_tier"),
                    "game_date_referenced": p.get("game_date_referenced"),
                    "is_speculation": p.get("is_speculation"),
                    "quoted_evidence": p.get("quoted_evidence"),
                    "url": rec["url"],
                    "model": rec["model"],
                    "prompt_version": rec["prompt_version"],
                })
    pd.DataFrame(rows).to_csv(FLAT_CSV, index=False)
    return len(rows)


def parse_payload(text):
    return json.loads(text)


def run_incremental(todo, model, client):
    runstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    records, raws, failures = [], [], 0
    for i, (key, row) in enumerate(todo, 1):
        try:
            resp = client.messages.create(**build_params(row, model))
            if resp.stop_reason == "refusal":
                failures += 1
                raws.append({"item_key": key, "stop_reason": "refusal"})
                continue
            text = next(b.text for b in resp.content if b.type == "text")
            payload = parse_payload(text)
            records.append(record_from(row, key, payload, model, text))
            raws.append({"item_key": key, "response": text,
                         "usage": resp.usage.to_dict() if hasattr(resp.usage, "to_dict") else str(resp.usage)})
        except Exception as e:
            failures += 1
            raws.append({"item_key": key, "error": str(e)[:300]})
        if i % 25 == 0:
            print(f"  ...{i}/{len(todo)}")
            time.sleep(1)
    write_records(records, raws, runstamp)
    return records, failures


def run_backlog(todo, model, client):
    """Batches API: 50% price, fine for the non-urgent backlog."""
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    runstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    keymap = {key: row for key, row in todo}
    requests = [Request(custom_id=key,
                        params=MessageCreateParamsNonStreaming(**build_params(row, model)))
                for key, row in todo]
    batch = client.messages.batches.create(requests=requests)
    print(f"batch {batch.id} submitted with {len(requests)} items; polling...")
    while True:
        b = client.messages.batches.retrieve(batch.id)
        if b.processing_status == "ended":
            break
        print(f"  status={b.processing_status} processing={b.request_counts.processing} "
              f"succeeded={b.request_counts.succeeded} errored={b.request_counts.errored}")
        time.sleep(30)
    records, raws, failures = [], [], 0
    for result in client.messages.batches.results(batch.id):
        key = result.custom_id
        row = keymap.get(key)
        if row is None:
            continue
        if result.result.type != "succeeded":
            failures += 1
            raws.append({"item_key": key, "batch_result": result.result.type})
            continue
        msg = result.result.message
        if msg.stop_reason == "refusal":
            failures += 1
            raws.append({"item_key": key, "stop_reason": "refusal"})
            continue
        try:
            text = next(b.text for b in msg.content if b.type == "text")
            payload = parse_payload(text)
            records.append(record_from(row, key, payload, model, text))
            raws.append({"item_key": key, "response": text})
        except Exception as e:
            failures += 1
            raws.append({"item_key": key, "error": str(e)[:300]})
    write_records(records, raws, runstamp)
    return records, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backlog", action="store_true", help="use the Batches API for all unextracted items")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--model", default="claude-opus-5")
    args = ap.parse_args()

    if not NEWS_CSV.exists():
        sys.exit(f"{NEWS_CSV} not found - run news_capture_daily.py first")
    news = pd.read_csv(NEWS_CSV)
    done = load_done()
    todo = []
    for row in news.itertuples(index=False):
        key = item_key(row)
        if key not in done:
            todo.append((key, row))
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(news)} items in log; {len(done)} already extracted; {len(todo)} to do "
          f"(model {args.model}, prompt {PROMPT_VERSION})")
    if not todo:
        return

    import anthropic
    client = anthropic.Anthropic(api_key=api_key())

    if args.backlog:
        records, failures = run_backlog(todo, args.model, client)
    else:
        records, failures = run_incremental(todo, args.model, client)

    n_flat = rebuild_flat()
    n_rel = sum(1 for r in records if r.get("relevant"))
    print(f"done: {len(records)} items extracted ({n_rel} availability-relevant), "
          f"{failures} failures, flat view {n_flat} player-signal rows -> {FLAT_CSV}")


if __name__ == "__main__":
    main()
