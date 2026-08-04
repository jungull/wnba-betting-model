"""Measure which read surfaces the seal guard actually traps.

Shared by TESTS.py (which asserts) and demo_seal.py (which records the table in MEASUREMENTS.json)
so that the claim and the measurement can never drift apart.

Call with a SealGuard already armed on `payload_dir`.

Each probe returns one of:
    TRAPPED            SealViolation was raised -- layer L1 caught it
    NOT_TRAPPED_NO_PLAINTEXT   the call got through the trap but recovered no plaintext (L2)
    LEAKED             the call returned plaintext -- a real hole
"""
from __future__ import annotations

import io
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sealed_package import SealViolation  # noqa: E402

TRAPPED = "TRAPPED"
NOT_TRAPPED_NO_PLAINTEXT = "NOT_TRAPPED_NO_PLAINTEXT"
LEAKED = "LEAKED"

# Surfaces that MUST be trapped by layer L1. TESTS.py asserts exactly this set.
MUST_TRAP = (
    "builtins.open(rb)", "builtins.open(w)", "io.open(rb)", "os.open(O_RDONLY)",
    "os.listdir(payload_dir)", "os.scandir(payload_dir)",
    "pathlib.Path.read_bytes", "pathlib.Path.read_text", "pathlib.Path.iterdir",
    "shutil.copy",
)


def _probe(fn, marker: bytes) -> dict:
    try:
        got = fn()
    except SealViolation as e:
        return {"outcome": TRAPPED, "detail": type(e).__name__}
    except Exception as e:  # got past the trap, but failed for another reason
        return {"outcome": NOT_TRAPPED_NO_PLAINTEXT,
                "detail": f"{type(e).__name__}: {str(e)[:120]}"}
    blob = got if isinstance(got, (bytes, bytearray)) else str(got).encode("utf-8", "replace")
    if marker in blob:
        return {"outcome": LEAKED, "detail": "plaintext marker recovered"}
    return {"outcome": NOT_TRAPPED_NO_PLAINTEXT, "detail": "returned no plaintext marker"}


def probe_surfaces(stored_file: str | os.PathLike, payload_dir: str | os.PathLike,
                   scratch: str | os.PathLike, marker: bytes) -> dict:
    """Run every probe. `marker` is a byte string known to be in the payload PLAINTEXT."""
    sf, pdir, scr = str(stored_file), str(payload_dir), str(scratch)
    out: dict[str, dict] = {}

    out["builtins.open(rb)"] = _probe(lambda: open(sf, "rb").read(), marker)
    # a WRITE probe: writes must also be API-mediated. Targets a new name, never an existing
    # payload, so that a hole in the trap leaves a stray file rather than a destroyed result.
    out["builtins.open(w)"] = _probe(
        lambda: open(os.path.join(pdir, "probe_write.tmp"), "w").close(), marker)
    out["io.open(rb)"] = _probe(lambda: io.open(sf, "rb").read(), marker)
    out["os.open(O_RDONLY)"] = _probe(lambda: os.read(os.open(sf, os.O_RDONLY), 4096), marker)
    out["os.listdir(payload_dir)"] = _probe(lambda: os.listdir(pdir), marker)
    out["os.scandir(payload_dir)"] = _probe(lambda: [e.name for e in os.scandir(pdir)], marker)
    out["pathlib.Path.read_bytes"] = _probe(lambda: Path(sf).read_bytes(), marker)
    out["pathlib.Path.read_text"] = _probe(lambda: Path(sf).read_text(errors="replace"), marker)
    out["pathlib.Path.iterdir"] = _probe(lambda: [p.name for p in Path(pdir).iterdir()], marker)
    out["shutil.copy"] = _probe(lambda: shutil.copy(sf, os.path.join(scr, "copy.bin")), marker)

    # native readers -- these open the file in C and do NOT route through the Python surface.
    # they are expected to get past L1; L2 is what stops them returning plaintext.
    def _pandas_parquet():
        import pandas as pd
        return pd.read_parquet(sf).to_csv(index=False)

    def _pyarrow_raw():
        import pyarrow as pa
        with pa.OSFile(sf, "rb") as f:
            return f.read()

    def _out_of_process():
        import subprocess
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys;sys.stdout.buffer.write(open(sys.argv[1],'rb').read())", sf],
            capture_output=True)
        return r.stdout

    out["pandas.read_parquet"] = _probe(_pandas_parquet, marker)
    out["pyarrow.OSFile"] = _probe(_pyarrow_raw, marker)
    # an entirely separate process. L1 cannot possibly see this; only L2 stands between it and
    # the plaintext. Probed so that the limit of the mechanism is a measured number, not a claim.
    out["separate python process"] = _probe(_out_of_process, marker)
    return out
