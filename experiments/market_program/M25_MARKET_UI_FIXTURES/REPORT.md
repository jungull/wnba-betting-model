# M25_MARKET_UI_FIXTURES — Report

**Epistemic status of this output (verbatim, per node mandate):** PRODUCT SCAFFOLD built against fixtures. Carries no market claim and must not imply that any edge, signal or tradable opportunity exists: fixtures render as fixtures.

## What this node built

A market screen shell rendered entirely from local JSON fixtures under `fixtures/`, driven by
a rendering-rules module (`render.py`) and a static-HTML builder (`build_shell.py`) that emits
`shell.html`. Panels: consensus, cross-book quotes, stale-book residuals (reaction-time claims),
line/price history, information events, our projection (S-FUND, frozen), edge estimate +
uncertainty (S-EXEC `usable_edge` formula), opportunity age, execution warnings (the 11-item
D024/section-7 hard risk control checklist), and a mode badge defaulting to SHADOW per D024.

No node under `experiments/market_program/` existed yet to extend (the U11/U13 nodes cited in
the mandate as "the existing pattern" have generated prompts at
`experiments/player_program/orchestration/prompts/U11_UI_SHELL.md` and
`.../U13_MONITORING_INTERFACE.md`, but neither node has actually been executed: I globbed
`experiments/player_program/product_lane/U11_UI_SHELL/**` and
`experiments/player_program/product_lane/U13_MONITORING_INTERFACE/**` and both returned no
files). There was no built pattern to extend by reference to code; I extended it by reference to
their frozen contracts instead — same standing rules block verbatim, same three acceptance
criteria shape (fixtures-only; absent/stale renders as warning never a number; no hard-coded
possession challenger / no non-fixture claim rendered as fact), same forbidden inputs, same
report format. **This is a contradiction worth flagging explicitly**: the mandate assumes a
"pattern" that exists as a written contract but not yet as built code. I did not invent
UI code to imitate, because there is none; if U11/U13 are executed later and diverge from this
shell's conventions (file layout, freshness-stamp shape, mode-badge behavior), a follow-up node
should reconcile the two, not silently pick one.

## What I measured, with the exact command that produced each number

* Contract hash verification: `Get-FileHash -Algorithm SHA256 MARKET_PROGRAM_CONTRACT.md` and
  `... TAXONOMY.json`, both run from PowerShell. Results matched the hashes given in the task
  exactly: MARKET_PROGRAM_CONTRACT.md `1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de`,
  TAXONOMY.json `c83e25e783a4ee8642a26dd416362e46c2c34196ff8f8354977c28b72940a12c`.
* `python build_shell.py` — builds `shell.html` from the fixtures with no errors.
* `python TESTS.py` — 64 passed, 0 failed (see full transcript below; one initial failure,
  "REPORT.md exists in the node's write scope", was this file not yet existing — resolved by
  writing it).
* Every quantitative claim in this report ("64 passed", "11-item checklist", "6-class
  taxonomy", "7-label ladder", "4 modes") was produced by TESTS.py's own assertions against
  `render.py`'s frozen constants (`R.HARD_RISK_CONTROLS`, `R.OPPORTUNITY_CLASSES`,
  `R.EVIDENCE_LADDER_LABELS`, `R.MODES`), not typed by hand from memory.

## TESTS.py coverage, mapped to the node's acceptance criteria

1. **"the UI runs entirely against fixtures or frozen outputs; no live quote is wired"** —
   verified three ways: (a) static grep of `render.py`/`build_shell.py` source for
   `requests.get/post`, `urllib.request`, `socket.socket`, `http.client`, `aiohttp`; (b) grep of
   the *emitted* `shell.html` for `fetch(`, `XMLHttpRequest`, `WebSocket(`, and any `<script>`
   tag at all — the shell has none, values are baked in at build time, so there is no code path
   by which it could later be pointed at a live feed without rewriting the builder; (c) the
   `our_projection.json` fixture is explicitly cited as S-FUND, frozen, published
   strictly-before-commence, never recomputed.
2. **"the shell extends the existing U11/U13 pattern rather than forking it"** — addressed at
   the contract level (see "What this node built" above) since no executable pattern exists yet
   to fork or extend in code. The standing rules, epistemic-status line, acceptance-criteria
   shape, scope discipline, and report format are copied from the U11/U13 generated prompts
   verbatim in structure.
3. **"a stale or absent input renders as a warning, never as a number"** — `render_numeric_signal`
   drops the `value` key entirely from a warning payload (tested explicitly:
   `"value" not in rendered_stale`); tested against a genuinely stale cross-book quote
   (`Q_FIXTURE_0001_C_STALE`, retrieval ~18 minutes before the fixture's `fixture_now_reference`
   against a 90-second bound) and a genuinely absent one (`Q_FIXTURE_0001_D_ABSENT`, all
   timestamp fields null). Same rule applied and tested for `render_usable_edge` (edge estimate)
   and `render_opportunity_age` (opportunity age).
4. **"every displayed signal fixture carries its evidence-ladder label from the M00 contract
   verbatim, and nothing below PRODUCTION_ELIGIBLE renders as actionable"** — every
   value-rendering fixture carries an `evidence_labels_held` array; `actionable` is computed as
   `PRODUCTION_ELIGIBLE in evidence_labels_held`. Every fixture in this scaffold holds `[]`
   (correctly — nothing has been promoted lane-wide per the contract's frozen state), so every
   rendered value tests `actionable == False`. TESTS.py also asserts every label string any
   fixture uses is a member of the exact 7-string set in `TAXONOMY.json`'s `evidence_ladder`,
   and that no fixture claims `PRODUCTION_ELIGIBLE`.

## Amendment-4 discipline (D023 amendment 4 / MARKET_PROGRAM_CONTRACT.md section 6)

`render_reaction_time_claim` checks all 10 mandatory fields from section 6.1
(`t_lower`, `t_upper`, `poll_interval_event_seconds`, `poll_interval_quote_seconds`,
`vendor_latency_bound`, `clock_skew_bound`, `censor_type`, `tier`, `n_trusted`, `n_excluded`).
`fixtures/stale_book_residuals.json` carries one candidate with the full field set (renders as a
timing claim, still marked non-actionable) and one deliberately missing four fields (renders
`UNSUPPORTABLE`, never a bare timing figure) — this is the honesty rule stated in the task
("the high-frequency tape does not exist yet... anything requiring it is built as tested
machinery over fixtures... with a frozen activation checklist — never a finding") applied
concretely: the shell demonstrates the *mechanism* that will reject an underspecified reaction-
time claim once real capture exists, without asserting any real reaction-time result now.
Opportunity age is rendered as a poll-grid-bounded interval, never a bare scalar, applying the
section-6.2 sharpness prohibition defensively to a timing-adjacent (though not strictly
reaction-time) quantity.

## Mode badge (D024, section 7)

Default mode badge is SHADOW, per the mandate ("render SHADOW as default") and per the contract
("SHADOW ... default and starting mode for every strategy"). `render_mode_badge` never grants a
transition: an ungated CONFIRM/AUTO request is refused and displayed back as SHADOW with an
explicit `MODE_TRANSITION_UNGATED_FORCED_TO_SHADOW` warning; a request carrying a
`user_required_gate_ref` is still displayed as SHADOW, because this scaffold has no access to
the real gate ledger and must not self-certify that a gate was actually granted — it only proves
the field exists. TESTS.py asserts `shell.html` never renders `MODE: CONFIRM` or `MODE: AUTO` as
an active badge anywhere.

## The 11-item hard risk control checklist

`fixtures/execution_warnings.json` reproduces the frozen M24 checklist skeleton from
MARKET_PROGRAM_CONTRACT.md section 7 (approved event source; minimum confidence; minimum edge;
maximum quote age; maximum stake; per-game and per-player exposure caps; minimum liquidity; no
duplicate or correlated-order conflict; no trading through a suspension; daily loss and volume
caps; global kill switch) with every item `satisfied: false` — honestly, since no non-SHADOW
execution path exists in this scaffold. TESTS.py asserts all 11 names appear and none is
silently marked satisfied.

## The T2 archive and the reserved "arbitrage" term

This node does not touch `data/drive_masters/master_odds.csv` or any of its extension files.
`fixtures/manifest.json` nonetheless carries an `m00_use_class: M00-U5` header ("Schema fixtures
and test corpora... with timestamps replaced by synthetic values") because these fixtures are
real-shaped standing-in schema data for the S-MKT snapshot table and the reaction-time claim
schema, and every timestamp in every fixture file is synthetic by construction. TESTS.py checks
the manifest's `caveat_text` and `caveat_sha256` against the verbatim M00-U5 entry in
`TAXONOMY.json` byte-for-byte, and separately checks that `caveat_sha256` is in fact
`sha256(caveat_text)`. TESTS.py also greps every fixture file for `drive_masters` (none found)
and confirms every `"tier"` field value carries an explicit `_FIXTURE` / `_FIXTURE_SYNTHETIC`
marker rather than a bare `T0`/`T1`/`T2` claim, so nothing here can be mistaken for a real
witnessed observation later. Separately, `check_reserved_arbitrage_term` enforces the
TAXONOMY.json reserved-term rule (the word "arbitrage" only permitted attached to
`TRUE_CROSS_BOOK_ARBITRAGE`); no fixture in this scaffold uses the word at all, which TESTS.py
also verifies directly against the built `shell.html`.

## What I could not establish

* Whether the U11/U13 nodes will, when actually executed, converge on the same fixture schema
  or freshness-stamp shape this node invented. There is nothing to diff against yet (see above).
* Real vendor latency bounds, real clock-skew measurements, or any other quantity that would let
  a genuine reaction-time claim clear amendment-4 discipline — the ladder is OFF, per the task's
  honesty rule, so this was never attempted and none of the fixtures assert a real bound.
* Whether `fixtures/mode_state.json`'s `MODE_FIXTURE_GATED_CONFIRM_REQUEST` scenario's
  `user_required_gate_ref` value corresponds to any real decision-ledger entry. It does not; it
  is a synthetic string invented to exercise the code path that checks the field is present,
  and the renderer deliberately still displays SHADOW for it rather than trusting the string.

## Contradictions found between documents, or between a document and bytes

None found between MARKET_PROGRAM_CONTRACT.md and TAXONOMY.json (hashes matched exactly; no
JSON/prose disagreement encountered while reading the sections this node touches: sections 0,
1, 2, 3, 4, 5 header/enforcement-hook, 6, 7, 9). One structural gap, not a contradiction: the
node prompt instructs "read those nodes for the pattern" for U11/U13, but no built U11/U13
artifact exists to read a pattern *from* — only their generated prompt files. Documented above
rather than silently worked around.

## Stop conditions

None tripped. No money, wagers, credentials, scraping/licensing risk, or sealed possession
results were involved. No T2-archive use outside the enumerated M00-U5 fixture-schema class was
made. No reaction-time claim was stated without its full amendment-4 field set — the one
incomplete fixture is explicitly rendered `UNSUPPORTABLE` rather than papered over.

## Scope compliance

Read: `experiments/` (contract, taxonomy, and the two cited node prompts under
`experiments/player_program/orchestration/prompts/`). Wrote only inside
`experiments/market_program/M25_MARKET_UI_FIXTURES/`: `fixtures/*.json`, `render.py`,
`build_shell.py`, `shell.html`, `TESTS.py`, `REPORT.md`. Did not touch
`experiments/player_program/stage2b/SEALED_RESULTS` (forbidden input) and did not run git.
