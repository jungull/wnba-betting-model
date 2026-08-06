# M04_COMPETITOR_ARCHIVE_DESIGN — REPORT

> Materialized by the coordinator from the design agent's returned text (harness report-file
> rule). DESIGN.json in this directory is the authoritative machine-readable deliverable.

Both M00 contract hashes verified exactly. The W1 draft
(COMPETITOR_ARCHIVE_DESIGN.md) confirmed byte-identical to the working-tree hash recorded
in TAXONOMY.json at contract freeze (`a1d7dd56…`) — no drift between the ruling and the
draft it rules on.

DESIGN.json validated: parses; the M00-U1 caveat sha256 citation matches
TAXONOMY.json's `permitted_uses[0].caveat_sha256` exactly; **both §5.1 subordination
rulings applied** — CLV-style labels from the T2 archive overruled (realized-outcome labels
only from game results), cross-sectional final-vs-final benchmarking restricted pending
contract amendment.

## The design (finalized from the W1 draft)

Six-rung fixed-cutoff capture ladder (T-24h / T-8h / T-2h / T-30m / final /
post-material-news) with same-rung-same-run comparison discipline; archive schema keyed on
our O14 entity-resolved player_id with provider ids, rung/run identity, provider update
timestamps with confidence, capture timestamps, previous values, change magnitudes, linked
information events, payload hashes, and per-row license_basis; benchmark suite
(per-provider, median, trimmed-mean, market-implied via the live pipeline only, incumbent,
blends) at matched cutoffs only, with amendment-4 fields propagating into every benchmark.

## USER DECISIONS (capture implementation is gated on these — design only until then)

| source | licensing flag | note |
|---|---|---|
| RotoWire | **RED** | explicit anti-crawl ToS clause found; do not capture absent a licensed feed or written permission |
| RotoGrinders | YELLOW | terms not fully retrieved |
| Stokastic | YELLOW | terms not fully retrieved |
| Dimers | UNKNOWN | commercial feed possibility worth a direct inquiry |
| FantasyCruncher | UNKNOWN | — |
| LineStar | UNKNOWN | — |

Open with any of: a licensed-feed inquiry (RotoWire and Dimers both run commercial data
businesses), written permission, or a decision to skip a source. "Personal research use"
was confirmed as a real carve-out for none of them and must not be assumed.
