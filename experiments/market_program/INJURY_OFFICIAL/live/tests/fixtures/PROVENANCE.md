# Fixture provenance

These four PDFs are **not captures made by this track**. They are real
production bytes, copied read-only (never modified) from the live main
worktree's own production injury-capture archive
(`C:\Users\jgallagher\wnba-betting-model\data\injury_capture\raw\`,
written by `injury_capture_daily.py`, a script this track does not own and
did not modify), so the parser and pipeline tests have real report bytes
to run against regardless of this session's live network conditions to
`ak-static.cms.nba.com` (see `../ACCESS_VERIFICATION.md`).

| fixture file | source path (live main worktree, read-only) | SHA-256 |
|---|---|---|
| `reference_prod_wnba_official_20260806T190009Z.pdf` | `data/injury_capture/raw/wnba_official_20260806T190009Z.pdf` | `256990a464ef262de93f72ed98fb0bfdbf971179b91bc4934dc5699f3dda13c2` |
| `reference_prod_wnba_official_20260731T205354Z.pdf` | `data/injury_capture/raw/wnba_official_20260731T205354Z.pdf` | `0d29268680477a8f89fd431fbe506f8f169c557acf3ccb8fd08a63379fa5edb5` |
| `reference_prod_wnba_official_20260731T215354Z.pdf` | `data/injury_capture/raw/wnba_official_20260731T215354Z.pdf` | `097f7ceb2055c02c4a7b52bffe7fb1ec47e7ee01ad1d5d0dc56f154c44a6609a0` |
| `reference_prod_wnba_official_20260805T230003Z.pdf` | `data/injury_capture/raw/wnba_official_20260805T230003Z.pdf` | `46b8cadfadfcb1b1cc0075aa9251077aeba00e8f42af23e4f9083a7587138756` |

Copied and hashed 2026-08-06 by the D033 INJURY-LIVE track (this node).
Selection rationale: the first is the most recent capture at copy time and
was independently verified structurally correct (13 rows, 0 rejects, clean
embedded-publication-timestamp parse); the second pair are two
production-captured PDFs ~1 hour apart with matching row content but
different byte hashes, useful for hash-dedup / parser-stability testing;
the third exposes a real reason-cell y-baseline layout edge case, kept
deliberately (not cherry-picked out) because it is the fixture that proves
the parser's reject path actually fires on real bytes, not only on
synthetic ones -- see `parser.py`'s module docstring "KNOWN LIMITATION"
section and `tests/test_parser.py::test_dense_report_known_reason_wrap_limitation_is_rejected_not_silent`.
