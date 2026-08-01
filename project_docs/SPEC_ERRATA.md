# Errata for frozen specification documents

A registered specification is **frozen**: once its `config_hash` is in the append-only registry,
the document is not edited, even to fix something that is plainly wrong. Editing it would break
the hash's meaning and make "retained unchanged" a false claim — which has already happened once
in this project and had to be undone by restoring
`CONTRACT_BASELINE_SUITE_V1.md` byte-for-byte.

So corrections to frozen documents live **here**, outside them. This file is not itself frozen and
carries no hash.

Each entry names the document, the exact stale claim, what is true, and whether the error is
material to the registration.

---

## `CONTRACT_BASELINE_SUITE_V3.md` — 2026-08-01

### E-V3-1 · builder assertion count

| | |
|---|---|
| **Stale claim** | "`tests/test_cbs_builders.py` (54 assertions)" — §0, *Executable core* |
| **True at registration and since** | the suite runs and passes **66/66** |
| **Material to the registration?** | **No.** |

The document was written when the suite had 54 assertions. Twelve more were added in the same
working session — before the v3 record was appended — to enforce that the document's `p_active`
feature order, the α and λ grids, the calibration-tail fraction, the minimum residual counts and
the `1e-6` team-points floor are all **equal** across the document, the registry record and
`cbs_builders.py`. The count in the prose was not updated to match.

No frozen *rule* is affected: every constant, grid, threshold and ordering in the v3 document is
unchanged, and the `config_hash`
`b8d22ec8c3d4584a3bba97f9cc47ba64d369e0f91f29f0e38560b33da595733e` still recomputes. The error is
a stale description of the test suite that checks the specification, not of the specification.

**Do not edit `CONTRACT_BASELINE_SUITE_V3.md` to fix this.** The live authority for the assertion
count is the suite's own output in the repository gate.

### E-V3-2 · superseded by v4

`contract_baseline_suite_v3` is **superseded by `contract_baseline_suite_v4`**
(`project_docs/CONTRACT_BASELINE_SUITE_V4.md`). v3's registry record and document are unchanged.

v3 froze the right *ideas* but its helpers proved useful primitives rather than the registered
end-to-end pipeline, and five points needed tightening before any real generation:

1. the team T1/T2/T3 split was defined on **team-game rows**, so the two rows of one game — and
   two games on one date — could land in different segments;
2. selection functions took bare frames, so returning disjoint arrays did not make contaminated
   selection *unrepresentable*; nothing stopped a caller passing calibration or test rows;
3. candidate-obligation ordering was not pinned, leaving tie-breaking to input order;
4. a **constant** residual pool yields `sd = 0`, which passed the "finite" test but violates the
   contract's `pred_sd > 0`;
5. base rates and fallback means were not explicitly restricted to the fitting/tuning prefix.

All five are frozen in v4.


---

## `CONTRACT_BASELINE_SUITE_V4.md` — 2026-08-01

### E-V4-1 · superseded by v5

`contract_baseline_suite_v4` is **superseded by `contract_baseline_suite_v5`**
(`project_docs/CONTRACT_BASELINE_SUITE_V5.md`). v4's registry record and document are unchanged,
and its implementation files (`cbs_generator.py`, `cbs_pipeline.py`) are left exactly as
registered.

v4's **specification** was sound. Its **implementation differed materially from it** in eight
ways, each confirmed by direct reproduction: λ tuning cut by player rather than chronologically;
team rows were never ordered, so input order could make a later game history for an earlier one;
the calibration map was pooled rather than per side; the residual sign was inverted against
additive offsets; missing channels were silently dropped; fitted hashes covered only the
coefficients; cold-start ignored the target; and Stage-A features were silently zero-filled while
`feature_asof` was trusted.

### E-V4-2 · assertion count in the document

The v4 document records "**123 assertions**" for `tests/test_cbs_generator.py`, which was correct
at registration and remains correct. No correction needed; noted here so the two suites are not
confused — `tests/test_cbs_v5.py` is a separate 75-assertion suite for v5.
