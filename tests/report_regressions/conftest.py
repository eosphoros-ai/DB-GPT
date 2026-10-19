"""Load the selected source checkout, including for before/after comparisons."""

import os
import sys
from pathlib import Path

SOURCE_ROOT = Path(
    os.environ.get("DBGPT_TEST_SOURCE_ROOT", Path(__file__).resolve().parents[2])
)
for source in sorted((SOURCE_ROOT / "packages").glob("*/src")):
    sys.path.insert(0, str(source))
