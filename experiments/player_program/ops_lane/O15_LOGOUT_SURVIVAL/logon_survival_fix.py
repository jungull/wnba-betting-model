"""
O15_LOGOUT_SURVIVAL -- the fix, expressed as a pure function over task XML.

Why XML and not PowerShell object surgery
-----------------------------------------
`setup_scripts\\verify_scheduled_tasks.ps1:129-135` records the hazard the hard
way: constructing a fresh settings object with `New-ScheduledTaskSettingsSet`
"would silently reset every other setting on the task ... to its default, which
is a far larger change than the one being asked for."  The same trap exists for
`New-ScheduledTaskPrincipal`: a principal built from scratch drops whatever of
`UserId` / `GroupId` / `RunLevel` / `Id` / `DisplayName` the caller forgot.

So the remediation is defined here as a *minimal textual rewrite of the task's
own exported XML*: exactly one element, `<LogonType>`, changes value.  Every
other byte of the definition -- triggers, actions, settings, registration info,
the principal's UserId and RunLevel -- is required to survive unchanged, and
`TESTS.py` asserts that against the real exported definition of a live task.

That property is the whole point.  A logon-mode change must not become a
silent re-registration that resets StartWhenAvailable, which is the mitigation
`verify_scheduled_tasks.ps1` exists to protect.

Nothing in this module touches the machine.  It transforms text.  Applying the
result is the caller's decision and requires the user's own approval.

Target logon modes
------------------
InteractiveToken  the defect.  Task Scheduler refuses to launch and logs
                  event 332, "did not launch ... because user ... was not
                  logged on".  Observed 23 times on this machine.

S4U               "Run whether user is logged on or not / Do not store
                  password".  Survives logoff.  The process receives a local
                  token with NO outbound network credentials -- fine for these
                  jobs (public HTTPS + local disk, verified: no UNC path and no
                  browser automation in any capture script), fatal for anything
                  that reaches a file share or an authenticated intranet host.

Password          "Run whether user is logged on or not" with the account
                  password stored by the scheduler.  Full network credentials.
                  Requires the "Log on as a batch job" right and a password the
                  scheduler must be told, and it breaks at every password
                  rotation.  This is the "batch-logon with IT" option demoted in
                  PROJECT_UPDATE_2026-08-04.md:267.

S4U is the recommendation for the capture family.  It is NOT proposed for
WNBA_ReplyDeliveryWatchdog: that task's script lives under a OneDrive-synced
path, and a cloud-only placeholder cannot be hydrated from a session with no
interactive OneDrive client.  See REPORT.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFECTIVE_LOGON_TYPES = ("InteractiveToken", "InteractiveTokenOrPassword")
SURVIVING_LOGON_TYPES = ("S4U", "Password")

_LOGON_RE = re.compile(r"<LogonType>\s*([^<\s]+)\s*</LogonType>")
_PRINCIPALS_RE = re.compile(r"<Principals>.*?</Principals>", re.S)


class RemediationError(ValueError):
    """The XML is not a shape this remediation is willing to touch."""


@dataclass
class Remediation:
    task_name: str
    before_logon_type: str
    after_logon_type: str
    changed: bool
    xml_before: str = field(repr=False, default="")
    xml_after: str = field(repr=False, default="")

    @property
    def chars_changed(self) -> int:
        return sum(1 for a, b in zip(self.xml_before, self.xml_after) if a != b) + abs(
            len(self.xml_before) - len(self.xml_after)
        )


def read_logon_type(xml: str) -> str:
    """Return the task's declared LogonType, or '' when the element is absent.

    An absent <LogonType> is not benign: Task Scheduler then defaults the
    principal to InteractiveToken, so the task is defective in exactly the same
    way while looking clean to a naive grep.
    """
    m = _LOGON_RE.search(xml)
    return m.group(1) if m else ""


def survives_logoff(logon_type: str) -> bool:
    """Will a task with this LogonType launch while no one is logged on?

    Absent/blank is treated as NOT surviving -- see read_logon_type.
    """
    return logon_type in SURVIVING_LOGON_TYPES


def remediate_task_xml(xml: str, task_name: str, target: str = "S4U") -> Remediation:
    """Rewrite exactly the <LogonType> element. Everything else is preserved.

    Raises RemediationError rather than guessing when the definition has no
    <Principals> block, has more than one principal, or when `target` is not a
    logon mode that actually survives logoff.
    """
    if target not in SURVIVING_LOGON_TYPES:
        raise RemediationError(
            f"{target!r} does not survive logoff; expected one of {SURVIVING_LOGON_TYPES}"
        )

    principals = _PRINCIPALS_RE.findall(xml)
    if len(principals) != 1:
        raise RemediationError(
            f"expected exactly one <Principals> block, found {len(principals)}"
        )

    n_logon = len(_LOGON_RE.findall(xml))
    if n_logon > 1:
        raise RemediationError(f"expected at most one <LogonType>, found {n_logon}")

    before = read_logon_type(xml)

    if n_logon == 0:
        # Defective-by-omission. Inserting an element is a larger edit than this
        # function is allowed to make silently, so refuse and let a human look.
        raise RemediationError(
            "no <LogonType> element; the principal defaults to InteractiveToken. "
            "This needs an explicit principal, not a text substitution."
        )

    if survives_logoff(before):
        return Remediation(task_name, before, before, False, xml, xml)

    after_xml = _LOGON_RE.sub(f"<LogonType>{target}</LogonType>", xml, count=1)
    return Remediation(task_name, before, target, True, xml, after_xml)


def diff_lines(a: str, b: str) -> list[tuple[int, str, str]]:
    """Line-level differences as (1-indexed line no, before, after)."""
    la, lb = a.splitlines(), b.splitlines()
    out: list[tuple[int, str, str]] = []
    for i in range(max(len(la), len(lb))):
        x = la[i] if i < len(la) else "<missing>"
        y = lb[i] if i < len(lb) else "<missing>"
        if x != y:
            out.append((i + 1, x, y))
    return out


def classify_tasks(principals: list[dict]) -> dict:
    """Split live task records (as emitted by measure_logon_survival.ps1) into
    those that survive logoff and those that do not.

    Accepts the PowerShell spelling 'Interactive' (what Get-ScheduledTask
    reports) as well as the XML spelling 'InteractiveToken'.
    """
    ps_defective = set(DEFECTIVE_LOGON_TYPES) | {"Interactive"}
    defective, surviving, unknown = [], [], []
    for p in principals:
        lt = (p.get("logon_type") or "").strip()
        if lt in ps_defective or lt == "":
            defective.append(p.get("task"))
        elif lt in SURVIVING_LOGON_TYPES:
            surviving.append(p.get("task"))
        else:
            unknown.append(p.get("task"))
    return {"defective": defective, "surviving": surviving, "unknown": unknown}
