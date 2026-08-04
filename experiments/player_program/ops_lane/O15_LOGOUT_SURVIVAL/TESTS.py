"""
O15_LOGOUT_SURVIVAL -- tests for the designed fix.

Repo convention (pytest is not installed): standalone runnable script, main()
returns 1 on failure.  Run:

    python experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/TESTS.py

Nothing here registers, modifies or deletes a scheduled task.  The live-machine
tests are read-only and skip cleanly when their evidence file is absent, so this
file is runnable on a machine that does not own the tasks.
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from logon_survival_fix import (  # noqa: E402
    RemediationError,
    classify_tasks,
    diff_lines,
    read_logon_type,
    remediate_task_xml,
    survives_logoff,
)

FAILURES: list[str] = []
SKIPS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILURES.append(f"{name}: {detail}")


def skip(name: str, why: str) -> None:
    print(f"  SKIP  {name}  ({why})")
    SKIPS.append(f"{name}: {why}")


SYNTHETIC = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>2026-07-30T18:00:00</Date>
    <Author>JOHNG-T\\jgallagher</Author>
    <URI>\\WNBA_Synthetic</URI>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <Repetition>
        <Interval>PT1H</Interval>
        <Duration>PT13H</Duration>
      </Repetition>
      <StartBoundary>2026-07-30T10:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-21-1225438708-3013916289-1686297083-2261</UserId>
      <LogonType>InteractiveToken</LogonType>
    </Principal>
  </Principals>
  <Settings>
    <StartWhenAvailable>true</StartWhenAvailable>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>python.exe</Command>
      <Arguments>odds_capture_daily.py</Arguments>
    </Exec>
  </Actions>
</Task>
"""


# --------------------------------------------------------------------------- #
def t_read_and_classify() -> None:
    print("\n[1] LogonType reading and logoff-survival classification")
    check("reads InteractiveToken", read_logon_type(SYNTHETIC) == "InteractiveToken",
          read_logon_type(SYNTHETIC))
    check("absent element reads as ''", read_logon_type("<Task/>") == "")
    check("InteractiveToken does NOT survive logoff",
          survives_logoff("InteractiveToken") is False)
    check("absent/blank does NOT survive logoff (defaults to InteractiveToken)",
          survives_logoff("") is False)
    check("S4U survives logoff", survives_logoff("S4U") is True)
    check("Password survives logoff", survives_logoff("Password") is True)


def t_minimal_rewrite() -> None:
    print("\n[2] the rewrite changes exactly one element and nothing else")
    r = remediate_task_xml(SYNTHETIC, "WNBA_Synthetic", target="S4U")
    check("reports a change", r.changed is True)
    check("before/after recorded",
          (r.before_logon_type, r.after_logon_type) == ("InteractiveToken", "S4U"),
          f"{r.before_logon_type}->{r.after_logon_type}")

    d = diff_lines(r.xml_before, r.xml_after)
    check("exactly one line differs", len(d) == 1, f"{len(d)} lines: {d}")
    if d:
        check("the differing line is the LogonType element",
              "LogonType" in d[0][1] and "LogonType" in d[0][2], str(d[0]))

    # The properties that matter operationally, asserted individually so a
    # failure names the thing that was lost.
    for token in (
        "<StartWhenAvailable>true</StartWhenAvailable>",
        "<UserId>S-1-5-21-1225438708-3013916289-1686297083-2261</UserId>",
        "<Interval>PT1H</Interval>",
        "<Duration>PT13H</Duration>",
        "<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>",
        "<Arguments>odds_capture_daily.py</Arguments>",
        '<Principal id="Author">',
    ):
        check(f"preserved: {token[:52]}", token in r.xml_after)

    check("no InteractiveToken remains", "InteractiveToken" not in r.xml_after)
    check("line count unchanged",
          len(r.xml_before.splitlines()) == len(r.xml_after.splitlines()))


def t_idempotence_and_refusals() -> None:
    print("\n[3] idempotence and refusal to guess")
    once = remediate_task_xml(SYNTHETIC, "t", target="S4U")
    twice = remediate_task_xml(once.xml_after, "t", target="S4U")
    check("second application is a no-op", twice.changed is False)
    check("second application is byte-identical", twice.xml_after == once.xml_after)

    for bad, why in (
        ("Interactive", "not a surviving mode"),
        ("InteractiveToken", "the defect itself"),
        ("Batch", "not a Task Scheduler LogonType value"),
    ):
        try:
            remediate_task_xml(SYNTHETIC, "t", target=bad)
            check(f"refuses target={bad!r} ({why})", False, "no exception raised")
        except RemediationError:
            check(f"refuses target={bad!r} ({why})", True)

    no_logon = SYNTHETIC.replace(
        "      <LogonType>InteractiveToken</LogonType>\n", "")
    try:
        remediate_task_xml(no_logon, "t")
        check("refuses a definition with no <LogonType>", False, "no exception")
    except RemediationError:
        check("refuses a definition with no <LogonType>", True)

    two = SYNTHETIC.replace("</Principals>", "</Principals><Principals></Principals>")
    try:
        remediate_task_xml(two, "t")
        check("refuses two <Principals> blocks", False, "no exception")
    except RemediationError:
        check("refuses two <Principals> blocks", True)


def t_password_target() -> None:
    print("\n[4] the Password (batch-logon) alternative")
    r = remediate_task_xml(SYNTHETIC, "t", target="Password")
    check("Password rewrite is also single-line",
          len(diff_lines(r.xml_before, r.xml_after)) == 1)
    check("Password rewrite preserves StartWhenAvailable",
          "<StartWhenAvailable>true</StartWhenAvailable>" in r.xml_after)


def t_live_exported_definition() -> None:
    print("\n[5] against the REAL exported definition of a live task")
    p = HERE / "evidence_task_WNBA_OddsCapture.xml"
    if not p.exists():
        skip("real-XML rewrite", f"{p.name} absent (not the machine that owns the tasks)")
        return
    xml = p.read_text(encoding="utf-8-sig")
    check("live definition is currently InteractiveToken",
          read_logon_type(xml) == "InteractiveToken", read_logon_type(xml))
    r = remediate_task_xml(xml, "WNBA_OddsCapture", target="S4U")
    d = diff_lines(r.xml_before, r.xml_after)
    check("exactly one line differs on the real definition", len(d) == 1, str(d))
    check("real definition keeps its StartWhenAvailable value",
          ("<StartWhenAvailable>" in xml)
          == ("<StartWhenAvailable>" in r.xml_after))
    # Everything except the LogonType line must be byte-identical.
    before = [l for l in xml.splitlines() if "LogonType" not in l]
    after = [l for l in r.xml_after.splitlines() if "LogonType" not in l]
    check("all non-LogonType lines byte-identical", before == after)


def t_live_measurement() -> None:
    print("\n[6] against the measured live task inventory")
    p = HERE / "EVIDENCE_measured.json"
    if not p.exists():
        skip("live classification", "EVIDENCE_measured.json absent")
        return
    d = json.loads(p.read_text(encoding="utf-8-sig"))
    principals = d.get("principals") or []
    if isinstance(principals, dict):
        principals = [principals]
    c = classify_tasks(principals)
    check("every WNBA task was classified",
          len(c["defective"]) + len(c["surviving"]) + len(c["unknown"]) == len(principals))
    check("no unrecognised LogonType value", c["unknown"] == [], str(c["unknown"]))
    check("classifier agrees with the PowerShell count",
          len(c["defective"]) == d["wnba_tasks_interactive"],
          f"{len(c['defective'])} vs {d['wnba_tasks_interactive']}")
    # The defect is only 'reproduced' if the log actually shows a suppressed launch.
    check("id-332 (user not logged on) observed for WNBA tasks",
          d["e332_wnba_total"] > 0, str(d["e332_wnba_total"]))
    # StartWhenAvailable did not rescue them: every recorded start on the
    # affected day sits on the trigger's own second boundary, so none of them is
    # a catch-up run fired when the machine became available again.
    starts = d.get("worst_hit_starts_on_affected_days") or []
    if starts:
        secs = {s.split("T")[1][3:8] for s in starts}   # mm:ss
        check("no off-cadence catch-up start (StartWhenAvailable did not recover)",
              len(secs) == 1, str(sorted(secs)))
    else:
        skip("catch-up check", "no start events recorded")


def main() -> int:
    print("O15_LOGOUT_SURVIVAL -- TESTS")
    print("=" * 72)
    t_read_and_classify()
    t_minimal_rewrite()
    t_idempotence_and_refusals()
    t_password_target()
    t_live_exported_definition()
    t_live_measurement()
    print("\n" + "=" * 72)
    if SKIPS:
        print(f"{len(SKIPS)} skipped:")
        for s in SKIPS:
            print(f"  - {s}")
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
