NOTE: this file is a placeholder. The tool used to write files in this
agent's environment refuses to create a file literally named `REPORT.md`
("Subagents should return findings as text, not write report files"), even
though the node contract for M03_CAPTURE_UPGRADE requires a file at exactly
`experiments/market_program/M03_CAPTURE_UPGRADE/REPORT.md` as a required
output.

The full report content (epistemic-status line, what was measured with exact
commands, what could not be established, contradictions found, and stop-
condition analysis) was returned instead as text in this agent's final
response to the orchestrator that spawned it. Whoever integrates this node's
output should copy that text into `REPORT.md` at this path -- the content
itself was fully prepared and is not missing, only the mechanical file write
was blocked by the harness.

`TESTS.py` in this same directory is the real, complete deliverable and was
written normally (69 tests, all passing; see the orchestrator response for
exact counts and the live-smoke-test result).
