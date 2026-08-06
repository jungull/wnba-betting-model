# M01_MARKET_DATA_INVENTORY — REPORT

> Materialized by the coordinator from the inventory agent's returned text (the harness
> refused the agent's own REPORT.md write — third occurrence of this rule; the agent's full
> findings are in the run journal). INVENTORY.json in this directory is the authoritative
> machine-readable deliverable and validates as JSON.

Both M00 contract hashes verified exactly before any classification
(MARKET_PROGRAM_CONTRACT.md `1152dcd3…`, TAXONOMY.json `c83e25e7…`).

## Formal ruling — earliest valid point-in-time tape date

**2026-07-30** for the odds (15:01:32Z), injury (15:49:50Z), news (16:25:50Z) and referee
(17:08:06Z) capture streams; **2026-07-31T14:23:41Z for props only**. This corrects
MARKET_PROGRAM_RESPONSE_2026-08-06.md, which stated 2026-07-31 for everything.

## Coverage and classification

Every market-relevant source classified into the contract's T0/T1/T2 classes with a
coverage matrix (source × season × market × book × cadence) in INVENTORY.json. The T2
final-state archive (master_odds.csv) reconciles exactly: 20,004 rows, 22 books, 814 raw
game_id groups = 813 valid games + one blank-id group of 94 rows. It is inventoried only
under M00-U1/M00-U3 with the frozen caveat texts cited by sha256 — never as point-in-time
evidence; D016/P2B is not relitigated.

## Contradictions found (reported, not resolved by this node)

1. **Tape start date** — response document said 07-31; bytes say 07-30 (ruled above).
2. **Forecast log schema** — the response document's "upgraded to SCHEMA/2 today" reads as
   if rows exist; every row read (8 in this worktree's copy, 40 live) is schema/1.
   Coordinator clarification recorded in the ledger: the WRITER was upgraded (code merged on
   the data branch, migration shipped-not-run); no schema/2 rows exist until the next
   forecast run or a deliberate migration. The claim's wording was loose; the code state is
   as described.
3. **Odds API historical endpoint status** — ODDS_API_VERIFICATION.md self-describes as
   unconfirmed against a live key, yet an actual executed historical pull exists at
   `data/props_capture/historical/master_props_historical.csv`. Unreconciled at inventory
   time; superseded in part by the later live verification (ODDS_API_LIVE_VERIFICATION.md,
   57-credit probe run), but the pre-existing pull remains unexplained by either document.

## New object flagged — UNGOVERNED

`data/props_capture/historical/master_props_historical.csv`: a real, previously executed
Odds API `/historical` pull — **36,946 rows, 784 games, player_points only, 2024-05-14 →
2026-07-30, all status=ok**. Classified T1 (vendor-asserted timestamps) per the taxonomy's
general rule, but **no M00-class bounded-use ruling covers this object** (the contract's
archive ruling names master_odds.csv and its extensions). Flagged for a coordinator ruling
before any market-lane node cites it for anything beyond bare existence. Materially: this
is ~2.2 seasons of owned player-prop history bearing directly on D023 amendment (1).

## Environment note

The program worktree lacks data/drive_masters/, data/odds_capture/ and
migrate_forecast_log_schema2.py entirely (they are data-branch artifacts); all such bytes
were read from the live main worktree under the headers/samples-only constraint.
