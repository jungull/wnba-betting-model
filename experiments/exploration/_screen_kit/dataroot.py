"""dataroot.py -- make the research lane able to SEE the data production already reads.

THE DEFECT THIS CLOSES (D138). A git worktree does not carry gitignored paths. Every screen
this programme has run executed inside `.claude/worktrees/player-model-program`, where six
data directories present in the main checkout simply do not exist. Screens probed for them,
found nothing, and recorded the absence as a fact about the repository. It was a fact about
the worktree.

**Measured 2026-08-19, not asserted:** six directories, 1,130 files, ~761 MB.

    drive_masters            3 files    11.2 MB
    entity_resolution        1 file      0.0 MB
    injury_official_live   642 files    64.6 MB   <- official quarter-hour injury reports
    market_snapshots        10 files    40.0 MB
    odds_capture           468 files    51.2 MB   <- the live odds tape
    sxbet_capture            6 files   594.2 MB

D138's ruling was that repointing the research lane at these is "the highest-leverage action
available to this programme". This module is that repoint.

HOW TO USE IT, and the rule that matters:

    from dataroot import require, resolve, inventory

    odds = require("odds_capture")      # a Path, or a loud failure naming every path tried
    inj  = require("injury_official_live")

**NEVER conclude that a source does not exist because a path did not resolve.** `require`
raises with the full search order precisely so that an environmental absence can never again
be written down as a repository fact. If you need to branch on availability, call
`available(name)` and say in your report that you branched.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
# .../experiments/exploration/_screen_kit -> repo root is three levels up
REPO = HERE.parent.parent.parent
MAIN_CHECKOUT = Path(r"C:\Users\jgallagher\wnba-betting-model")

#: Sources that exist in the main checkout but NOT in the worktree, measured 2026-08-19.
#: Kept as data rather than prose so a screen can assert against it.
WORKTREE_INVISIBLE = {
    "drive_masters": "master odds/reference exports",
    "entity_resolution": "alias and identity resolution artifacts",
    "injury_official_live": "official league quarter-hour injury reports, live capture",
    "market_snapshots": "market ladder snapshots, poll log, vendor timing",
    "odds_capture": "live multi-book odds tape",
    "sxbet_capture": "sxbet exchange tape (provenance unverified -- see D138 ruling 6)",
}


@dataclass(frozen=True)
class Root:
    path: Path
    how: str

    def __truediv__(self, name: str) -> Path:
        return self.path / name


def _candidates(explicit=None) -> list[tuple[Path, str]]:
    """Search order. An EXPLICIT root is authoritative and is the ONLY candidate.

    Falling through from an explicit root to a different one would silently substitute the
    provenance a caller pinned -- a screen would record "I read root X" while having read
    root Y. That is the same class of defect as D138 itself, so an explicit root that lacks
    the requested source raises instead of quietly succeeding elsewhere.
    """
    if explicit:
        return [(Path(explicit), "explicit argument (authoritative -- no fallback)")]
    out: list[tuple[Path, str]] = []
    env = os.environ.get("WNBA_DATA_ROOT")
    if env:
        out.append((Path(env), "$WNBA_DATA_ROOT"))
    out.append((REPO / "data", "repo-relative <repo>/data"))
    # climb out of .claude/worktrees/<name>/ to the checkout that owns the ignored paths
    out.append((REPO.parent.parent.parent / "data", "worktree parent climb"))
    out.append((MAIN_CHECKOUT / "data", "hard-coded main checkout (D138 fallback)"))
    return out


def resolve(explicit=None, must_contain: str | None = None) -> Root:
    """Resolve the data root, preferring one that actually contains `must_contain`.

    `must_contain` matters: the worktree HAS a `data/` directory, so a naive
    first-hit-wins resolver finds it and then reports the six ignored sources as absent.
    That is precisely the D138 failure, reproduced by the fix meant to prevent it.
    """
    tried = []
    first_existing: Root | None = None
    for path, how in _candidates(explicit):
        tried.append(f"{how}: {path}")
        if not path.is_dir():
            continue
        if first_existing is None:
            first_existing = Root(path.resolve(), how)
        if must_contain is None or (path / must_contain).exists():
            return Root(path.resolve(), how)

    if must_contain is not None and first_existing is not None:
        raise FileNotFoundError(
            f"Found a data root at {first_existing.path} (via {first_existing.how}) but it does "
            f"NOT contain {must_contain!r}.\n"
            + (f"{must_contain!r} is one of the six sources a git worktree cannot see (D138): "
               f"{WORKTREE_INVISIBLE[must_contain]}.\n" if must_contain in WORKTREE_INVISIBLE else "")
            + "This is an ENVIRONMENTAL absence, NOT evidence that the source does not exist.\n"
            + "Tried, in order:\n  " + "\n  ".join(tried)
            + "\nSet WNBA_DATA_ROOT to the checkout that owns the gitignored data paths."
        )
    if first_existing is not None:
        return first_existing
    raise FileNotFoundError(
        "No data root found at all. Tried:\n  " + "\n  ".join(tried))


def require(name: str, explicit=None) -> Path:
    """Return the directory for one named source, or fail loudly."""
    root = resolve(explicit, must_contain=name)
    p = root / name
    if not p.exists():
        raise FileNotFoundError(f"{name!r} not present under {root.path}")
    return p


def available(name: str, explicit=None) -> bool:
    """Non-raising probe. If you branch on this, SAY SO in your report."""
    try:
        require(name, explicit)
        return True
    except FileNotFoundError:
        return False


def inventory(explicit=None) -> dict:
    """What this process can actually REACH, and whether the naive root would have lied.

    Two different questions, reported separately, because conflating them is the whole D138
    defect:

      * `naive_root` -- what a screen gets if it just joins "data" onto the repo path. Inside
        a worktree this directory EXISTS but is missing the ignored sources, which is why the
        failure was silent rather than loud.
      * `reachable` -- what `require()` can actually find by climbing to the checkout that
        owns the ignored paths. This is what a screen using this module will get.
    """
    naive = resolve(explicit)
    naive_missing = [n for n in WORKTREE_INVISIBLE if not (naive.path / n).exists()]

    reachable, unreachable, where = [], [], {}
    for name in WORKTREE_INVISIBLE:
        try:
            path = require(name, explicit)
            reachable.append(name)
            where[name] = str(path.parent)
        except FileNotFoundError:
            unreachable.append(name)

    return {
        "naive_root": str(naive.path),
        "naive_root_resolved_via": naive.how,
        "naive_root_would_be_blind_to": naive_missing,
        "naive_root_is_blind": bool(naive_missing),
        "reachable_via_require": reachable,
        "unreachable": unreachable,
        "reachable_from": where,
        "blind": bool(unreachable),
        "warning": (
            "THIS PROCESS CANNOT REACH SOURCES PRODUCTION READS (D138). Any screen run here "
            "measures a poorer information set than the shipped pipeline uses, and must say so."
            if unreachable else
            "All six previously-invisible sources ARE reachable through require(). Note that "
            "the naive <repo>/data root is still blind to " + str(len(naive_missing)) +
            " of them -- which is exactly why screens must use require() rather than joining "
            "paths by hand."
        ),
    }


if __name__ == "__main__":
    import json
    inv = inventory()
    print(json.dumps(inv, indent=1))
    print()
    for name, desc in WORKTREE_INVISIBLE.items():
        try:
            p = require(name)
            n = sum(len(f) for _, _, f in os.walk(p))
            mb = sum(os.path.getsize(os.path.join(r, f))
                     for r, _, fs in os.walk(p) for f in fs) / 1e6
            print(f"  OK      {name:22s} {n:5d} files {mb:9.1f} MB  {desc}")
        except FileNotFoundError:
            print(f"  MISSING {name:22s}                            {desc}")
