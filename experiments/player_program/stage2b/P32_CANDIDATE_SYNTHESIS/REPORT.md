# P32_CANDIDATE_SYNTHESIS — REPORT

SYNTHESIS. Reduces sources to families. Rejection here is a design decision, not an empirical result: nothing has been fitted.

Node: `P32_CANDIDATE_SYNTHESIS` (replacement dispatch for a wave lost at session logout; nothing from that wave existed on disk when this node started). Deliverables: this file and `SPEC.json` in the same directory. Nothing else was written anywhere.

---

## 1. What was measured, and with what

Every number below was produced by a command run in this session against the actual bytes. No figure is quoted from memory.

**Input hash verification (all eight MATCH).** Rederived with PowerShell over raw file bytes:

```powershell
Get-FileHash -Algorithm SHA256 <file>   # compared case-insensitively to the frozen value, per file
```

| file | frozen sha256 | result |
|---|---|---|
| P31_FINAL_V3_IDEATION/GENERATION_ORDER_V3.json | 898f4b80... | MATCH |
| HYPOTHESES_adversarial_identifiability.md | bf589616... | MATCH |
| HYPOTHESES_calibration_control.md | 1085da13... | MATCH |
| HYPOTHESES_coldstart_fallback.md | 8d145ce1... | MATCH |
| HYPOTHESES_cutoff_leakage.md | 3d8c096b... | MATCH |
| HYPOTHESES_opponent_mechanism.md | 88cda948... | MATCH |
| HYPOTHESES_timeseries_shrinkage.md | ea2cbd42... | MATCH |
| P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json | 95d2412c... | MATCH |

**Byte sizes vs GENERATION_ORDER_V3's recorded `bytes` field.** `(Get-Item <file>).Length` per file: 15,703 / 22,461 / 26,511 / 17,940 / 22,235 / 14,083 — all six MATCH the frozen record. `EVIDENCE_PACKET_V3.json` is 74,025 bytes, matching the size every source attests for the packet it consumed.

**Hypothesis counts vs GENERATION_ORDER_V3's `n_hypotheses_reported`.** Counted by heading pattern:

```powershell
Select-String -Path <file> -Pattern '^##+ +(TS\d|AI-H\d|CALIBRATION_CONTROL_H\d|COLDSTART_FALLBACK_H\d|CUTOFF_LEAKAGE_H\d|OPPONENT_MECHANISM_H\d)'
```

adversarial 5, calibration 6, coldstart 6, cutoff 5, opponent 5, timeseries 4 — all six MATCH the frozen record. **Candidate union = 31.**

**Output validation.** The required command was run and passes:

```
python -c "import json;json.load(open('experiments/player_program/stage2b/P32_CANDIDATE_SYNTHESIS/SPEC.json'))"
```

**Reconciliation arithmetic**, computed by a python one-liner over the written SPEC (not asserted): 20 families, 26 arms, 5 rejections; 26 + 5 = 31 = the candidate union. Provenance citations inside arms total 30 = 26 arms + the 4 duplicate-rejected candidates cited inside their canonical merged arms. Per-source provenance coverage: calibration 6/6, coldstart 6/6, cutoff 5/5, opponent 5/5, timeseries 4/4, adversarial 4/5 (AI-H4 rejected, cited only in the rejection ledger).

**Universe numbers carried, both, per the packet rule:** 2,982 team-game rows over 1,491 game clusters (resolved); 2,990 rows over 1,495 clusters (full schedule). Games are never split across folds or cluster-bootstrap draws. Folds are the FIVE D006 expanding-window folds.

---

## 2. What this node did

Deduplicated the 31-candidate union into **20 mechanistically distinct families carrying 26 complete arm definitions**, and rejected 5 candidates each with one named reason. Complete definitions — feature lists with lineage and cutoff-validity citations back to EVIDENCE_PACKET_V3, estimator/formula specifications, hyperparameter grids separated from hypotheses, per-arm K0_MATCHED implications, and provenance to source file and section — are in `SPEC.json`. They are not repeated here; this report gives the audit trail for the decisions.

**Family semantics, stated to prevent a later misreading:** a family in `SPEC.json` is a mechanistic equivalence class (one falsifiable mechanism sentence per family). It is deliberately NOT the multiplicity-accounting family: the sources' declared multiplicity families are preserved verbatim per arm, they conflict in places (disagreements D2/D5 below), and fixing the multiplicity partition belongs to the preregistration chain P33-P37, not to this node.

**Deduplication standard.** Two candidates were merged only when the mechanism AND the design column they produce are the same object up to affine recoding or a hyperparameter/basis choice — never merely because their prose is similar. Conversely, candidates that share raw material but make different falsifiable predictions were kept as separate arms in one family (e.g., symmetric vs antisymmetric combinations of rest, which are orthogonal projections of (rest_own, rest_opp) testing "game-level depression" vs "equilibrium drag").

### Rejections (design decisions, one named reason each)

| id | candidate | reason | canonical retention |
|---|---|---|---|
| R1 | OM-H3 home +/-1 term | duplicate formulation | A25 (affine recoding of AI-H3's column; identical span beside offset) |
| R2 | OM-H4 rest differential, cap 4 | duplicate formulation | A23 (cap and opener rule become preserved choice sets) |
| R3 | CF-H2 depth-indexed slope kernel | duplicate formulation | A04 (kernel preserved as basis option; stricter CC-H4 null adopted) |
| R4 | AI-H5 schedule-index drift | duplicate formulation | A06 (monotone basis preserved as option; its truncated-2026 binding carried) |
| R5 | AI-H4 lagged OT-exposure arm | downstream-mismatch-exploitation-only | none (audit content preserved as a recommendation, below) |

On R5, stated plainly: as a promotion candidate AI-H4's primary-target signal is zero by its own hypothesis — the source says a nonzero coefficient is a pipeline defect, not a pace discovery, and preregisters non-promotion. V2_STOP_CONDITION's E5 note records that trailing OT rate's only downstream benefit channel is arbitraging the OT bias (~132 rows), improving turnover MAE while worsening the primary target — the named exclusion. The rejection is therefore consistent with the source's own intent. The audit idea is genuinely valuable and is **preserved as a recommendation**: run the identical construction in a diagnostic lane, never as a challenger and never inside the promotion multiplicity accounting. This node does not create that diagnostic; it records that rejecting the arm did not discard the insight.

### Rejection-category scan (required categories with zero members, stated rather than left implicit)

- **Offset reconstruction: zero.** No source proposed the own/opp pair, the current projection as a substantive feature, or an offset-affine term outside the declared calibration family. Elevated-P25-risk arms (A08, A09, A10, A16, A26) carry withdrawal-on-audit-failure declarations; that adjudication belongs to the guard at preregistration, not to design-time rejection.
- **Postgame surrogate: zero.** Every realized-column use in all 31 candidates is a strictly-lagged aggregate under P22 discipline with same-game joins failing closed.
- **Cutoff-unproven injury field: zero proposed.** All six sources honoured P24 (0 cutoff-valid injury rows in every fold). A22 is the mandated lagged-lineup twin, not an injury field.
- **Unsafe fan-out feature: zero.** No candidate touches team_cities or the venue/travel/elevation/timezone set. The PHO/PHX duplicate (team_id 1611661317) precondition binds A14 by source declaration and was **extended by this synthesis** to every cross-season franchise-history construction (A11, A12, A13): P23 receipts required.
- **Fold-degenerate: zero rejected.** The two support-risk arms are retained WITH the remedies the packet's own S7 clause prescribes: A05 (playoff intercept; test-side 2026 degeneracy; section-4 fallback declared; four effective folds) and A14 (expansion stratum; support unmeasurable from this node's read scope; preregistered retirement rule). A candidate with a known blocking training-fold degeneracy and no declared remedy would have been rejected; none exists in the union.

---

## 3. What could NOT be established, and why

1. **A14's fold support** (>= 10 expansion clusters in any training fold): the schedule/data artifacts are outside this node's read scope (`experiments/player_program/` only). The P27 guard measures it at preregistration; the source's retirement rule covers the negative case.
2. **Which carryover null matches the frozen incumbent** (disagreement D1, TS3's rho=1 pooling null vs CF-H1's no-carryover null): resolving it requires reading the incumbent's receipted construction. That is legitimate non-performance information, but it is P33-P37's decision to make with the arms in front of it; making it here would have silently resolved a source disagreement this node is required to preserve.
3. **Whether A16's lagged incumbent projections are retrievable as frozen receipted rows** of `team_possession_prior_v1.parquet` without recomputation: plausible from PROGRAM_STATE's frozen-artifact listing; not verified against artifact bytes.
4. **The cause of the D4 admissibility split** (opponent_mechanism holding the lagged-lineup family empty while two sources built it): the ROLE_PROMPT files are not among this node's frozen inputs, and GENERATION_ORDER records that two never existed on disk at all.
5. **Whether `end_reason` level dictionaries can actually distinguish live-ball turnover terminators** (A19/A20): a data question outside read scope; both arms carry withdrawal-as-design-failure if the dictionary fails.

---

## 4. Contradictions found (every one, preserved rather than resolved)

Between documents, and between documents and bytes. D-ids match `SPEC.json.preserved_disagreements`.

- **D1 — TS3 vs CF-H1:** opposite null presumptions about the incumbent's prior-season pooling (rho=1 vs no carryover). Both nulls cannot be correct. Both arms carried (A11, A12) with the disagreement stamped on each; resolution assigned to preregistration, from receipts, never from performance.
- **D1a — CC-H4 vs CF-H2:** null structure for the depth-indexed slope (tier main + global slope in the null, vs slope-1 only). The stricter null was adopted for the canonical arm per RESEARCH_CONTRACT_V1 precedence and S4; the weaker formulation is recorded, not silently discarded.
- **D2 — CC-H5 vs AI-H5 vs CF-H3:** three different multiplicity-family assignments for the within-season drift mechanism. Affects alpha budgeting only; preserved.
- **D3 — CC-H6 vs coldstart standing constraint 4:** one source excludes any new `is_playoff_game` term as fold-degenerate; another proposes it with the declared section-4 fallback — the remedy the packet's S7 clause itself names. A05 retained with the objection attached.
- **D4 — opponent_mechanism vs cutoff_leakage/coldstart_fallback:** lagged-lineup admissibility (family declared empty vs two arms built under the S8 LAGGED_USE_ONLY licence). The packet's licence to propose governs this synthesis; the narrower reading travels with A13/A22 verbatim.
- **D5 — TS3 in `timeseries_shrinkage` vs CF-H1/H4 in `COLDSTART_FALLBACK`:** mechanistically one family, two declared multiplicity homes. Preserved.
- **D6 — four incompatible frozen trailing-window conventions** (cross-season decay h=10/lambda=0.5; same-season flat with E=3; last-k; all-prior flat/EWMA-grid), each declared non-tunable by its source. Preserved per-arm; the preregistration node must not harmonize them into a pooled grid without charging the relevant family's multiplicity budget.
- **D7 — three season-opener rest rules and three frozen caps (4/7/10)** for the rest family. Preserved as explicit choice sets in A23/A24; never averaged.
- **D8 — document vs frozen record:** the timeseries source attests the staging packet copy was "the only copy in existence," while GENERATION_ORDER_V3 records byte-identical isolation copies existed for four sources. A provenance-narrative overstatement by a thin-briefed source; immaterial to content (its computed packet hash matches the frozen value); recorded, not repaired.

No contradiction was found between any document and the verified bytes of the eight frozen inputs themselves (hashes, sizes and counts all reconcile, section 1).

---

## 5. Stop-condition assessment

**Not tripped.** Nothing in the union or in this synthesis changes the primary target (`REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`), the K0 structure (the per-arm K0_MATCHED map of D007 stands; every arm states its matched null), the inference structure (five D006 folds, game-clustered, games never split), the candidate universe (2,982 / 1,491, with 2,990 / 1,495 reported alongside), the cutoff-valid feature set as adjudicated by the packet, or the leakage status. The preserved disagreements above are formulation- and accounting-level; each is assigned to the preregistration chain, which is where the packet already places such decisions. The closest calls, stated so a reviewer can disagree: D1 (carryover nulls) touches what a *particular arm's* K0 contains, not the K0 *structure*; D2/D5 touch multiplicity budgeting, which is not one of the six frozen dimensions.

## 6. Prohibitions honoured

No fit was performed and no performance number appears in this node's outputs. Nothing under `SEALED_RESULTS` was read, listed or globbed. No frozen artifact was modified. Git was not run. All writes are inside `experiments/player_program/stage2b/P32_CANDIDATE_SYNTHESIS/`. This node does not mark its own work accepted; two independent adversarial reviewers examine these outputs after freezing.