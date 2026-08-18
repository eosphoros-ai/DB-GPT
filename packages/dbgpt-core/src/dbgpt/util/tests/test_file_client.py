import asyncio
from pathlib import Path

import pytest

from dbgpt.util import file_client
from dbgpt.util.file_client import FileClient


def test_read_file_rejects_absolute_path_outside_upload_root(monkeypatch, tmp_path):
    upload_root = tmp_path / "uploads"
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    monkeypatch.setattr(file_client, "KNOWLEDGE_UPLOAD_ROOT_PATH", str(upload_root))

    with pytest.raises(ValueError):
        FileClient().read_file("conv_a", str(outside))


def test_read_file_rejects_relative_traversal(monkeypatch, tmp_path):
    upload_root = tmp_path / "uploads"
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    monkeypatch.setattr(file_client, "KNOWLEDGE_UPLOAD_ROOT_PATH", str(upload_root))

    with pytest.raises(ValueError):
        FileClient().read_file("conv_a", "../outside.txt")


def test_read_file_allows_conversation_file(monkeypatch, tmp_path):
    upload_root = tmp_path / "uploads"
    conv_dir = upload_root / "conv_a"
    conv_dir.mkdir(parents=True)
    target = conv_dir / "allowed.txt"
    target.write_text("allowed", encoding="utf-8")
    monkeypatch.setattr(file_client, "KNOWLEDGE_UPLOAD_ROOT_PATH", str(upload_root))

    assert FileClient().read_file("conv_a", "allowed.txt") == b"allowed"


def test_delete_file_rejects_absolute_path_outside_upload_root(monkeypatch, tmp_path):
    upload_root = tmp_path / "uploads"
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    monkeypatch.setattr(file_client, "KNOWLEDGE_UPLOAD_ROOT_PATH", str(upload_root))

    with pytest.raises(ValueError):
        asyncio.run(FileClient().delete_file("conv_a", str(outside)))

    assert outside.exists()


def test_delete_file_allows_conversation_file(monkeypatch, tmp_path):
    upload_root = tmp_path / "uploads"
    conv_dir = upload_root / "conv_a"
    conv_dir.mkdir(parents=True)
    target = conv_dir / "allowed.txt"
    target.write_text("allowed", encoding="utf-8")
    monkeypatch.setattr(file_client, "KNOWLEDGE_UPLOAD_ROOT_PATH", str(upload_root))

    asyncio.run(FileClient().delete_file("conv_a", str(target)))

    assert not target.exists()
