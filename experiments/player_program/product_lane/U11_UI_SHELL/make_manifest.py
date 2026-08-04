#!/usr/bin/env python3
"""make_manifest.py — emit MANIFEST.json: the machine-readable record of this node.

For each fixture it records the payload digest, the rendered-page digest, and the counts
that the acceptance criteria are argued from: how many numbers the page shows and how
many warnings it shows. Regenerate with::

    python experiments/player_program/product_lane/U11_UI_SHELL/make_manifest.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ui_shell  # noqa: E402

WARN_MARKER = "<span class='badge'>WARNING</span>"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build() -> dict:
    fixtures = []
    for p in sorted((HERE / "fixtures").glob("*.json")):
        raw = p.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        html = ui_shell.render_payload(payload)
        fixtures.append({
            "fixture": p.name,
            "payload_id": (payload.get("audit") or {}).get("payload_id"),
            "payload_sha256": sha256(raw),
            "rendered": f"rendered/{p.stem}.html",
            "rendered_sha256": sha256(html.encode("utf-8")),
            "numbers_rendered": html.count(ui_shell.NUMBER_MARKER),
            "warnings_rendered": html.count(WARN_MARKER),
        })
    return {
        "schema": "u11_ui_shell_manifest/1",
        "node": "U11_UI_SHELL",
        "epistemic_status": ("PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim "
                             "and must not imply a model has been promoted."),
        "view_payload_schema": ui_shell.VIEW_SCHEMA,
        "renderer": "ui_shell.py",
        "renderer_sha256": sha256((HERE / "ui_shell.py").read_bytes()),
        "reason_codes": ui_shell.REASONS,
        "fixtures": fixtures,
        "model_identifiers_embedded_in_code": [],
        "inputs_read_outside_this_directory": [],
    }


def main() -> int:
    m = build()
    (HERE / "MANIFEST.json").write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    for f in m["fixtures"]:
        print(f"  {f['fixture']:<26} numbers={f['numbers_rendered']:<3} warnings={f['warnings_rendered']}")
    print("MANIFEST.json written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
