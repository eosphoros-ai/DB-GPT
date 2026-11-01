"""Checked-in release boundary, shared with the browser; not a user setting."""

import json
from pathlib import Path

LAYOUT_TEMPLATES_ENABLED = json.loads(
    (Path(__file__).parent / "schema/dashboard-release-features.json").read_text(
        encoding="utf-8"
    )
)["layout_templates"]


def layout_templates_enabled() -> bool:
    return LAYOUT_TEMPLATES_ENABLED
