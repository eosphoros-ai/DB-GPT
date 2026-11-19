"""Acceptance commands must not silently replace real work with synthetic output."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "options",
    [
        ["--resume-database", "saved.db"],
        ["--resume-database", ""],
        ["--resume-run-id", "saved-run"],
        ["--review-only"],
        ["--model-config", "model.toml"],
    ],
)
def test_real_run_options_require_real_pdfs_before_writing_output(tmp_path, options):
    root = Path(__file__).resolve().parents[6]
    output = tmp_path / "acceptance"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/verify_financial_comparison.py"),
            "--output-dir",
            str(output),
            *options,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "require --real-pdfs" in result.stderr
    assert not output.exists()
