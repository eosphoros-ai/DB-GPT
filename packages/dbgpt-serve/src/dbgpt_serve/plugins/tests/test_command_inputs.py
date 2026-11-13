"""Command metadata describes uploads without changing command identity."""

import json

import pytest
import yaml

from dbgpt_serve.plugins.loader import load_suite_dir


def write_command(root, **metadata):
    manifest = root / ".dbgpt-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"name": "reports", "version": "1", "skills": ["skills/report"]}),
        encoding="utf-8",
    )
    skill = root / "skills" / "report" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\n"
        + yaml.safe_dump(
            {"name": "report", "command": "/读年报", **metadata},
            allow_unicode=True,
        )
        + "---\n# Report\n",
        encoding="utf-8",
    )
    return root


def test_upload_requirements_and_english_command_share_the_canonical_binding(tmp_path):
    root = write_command(
        tmp_path / "reports",
        **{
            "command-en": "/annual-report",
            "input_files": {
                "min": 1,
                "max": 1,
                "types": ["application/pdf", "APPLICATION/PDF"],
            },
        },
    )
    package = load_suite_dir(root)
    assert package is not None
    command = package.snapshot["commands"][0]
    assert command["name"] == "/读年报"
    assert command["display_en"] == "/annual-report"
    assert "/annual-report" in command["aliases"]
    assert command["input_files"] == {
        "min": 1,
        "max": 1,
        "types": ["application/pdf"],
    }


@pytest.mark.parametrize(
    "requirements",
    [
        None,
        [],
        {"min": True, "max": 1, "types": ["application/pdf"]},
        {"min": 1, "max": False, "types": ["application/pdf"]},
        {"min": -1, "max": 2, "types": ["application/pdf"]},
        {"min": 2, "max": 1, "types": ["application/pdf"]},
        {"min": 0, "max": 0, "types": ["application/pdf"]},
        {"min": 1, "max": 1, "types": []},
        {"min": 1, "max": 1, "types": "application/pdf"},
        {"min": 1, "max": 1, "types": ["PDF"]},
        {"min": 1, "max": 1, "types": [None]},
    ],
)
def test_invalid_input_requirements_do_not_publish_an_unusable_command(
    tmp_path, requirements
):
    root = write_command(tmp_path / "reports", input_files=requirements)
    assert load_suite_dir(root) is None


@pytest.mark.parametrize("label", ["annual-report", 12, ["/annual-report"]])
def test_english_command_must_be_a_slash_alias(tmp_path, label):
    root = write_command(tmp_path / "reports", **{"command-en": label})
    assert load_suite_dir(root) is None
