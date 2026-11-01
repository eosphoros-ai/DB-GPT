"""Failure boundaries for optional, reproducible reference data generation."""

import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "reference_sources",
    Path(__file__).resolve().parents[1] / "install_reference_sources.py",
)
reference_sources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference_sources)


class ReferenceSourcesTest(unittest.TestCase):
    def test_offline_missing_archive_never_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(reference_sources.requests, "get") as download:
                with self.assertRaisesRegex(
                    FileNotFoundError, "Offline source archive"
                ):
                    reference_sources.generate_sources(
                        root / "out",
                        root / "cache",
                        offline=True,
                        source_keys=["energy"],
                    )
                download.assert_not_called()
            self.assertFalse((root / "out/energy.sqlite").exists())

    def test_changed_archive_is_rejected_before_creating_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "energy.zip").write_bytes(b"unexpected replacement download")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                reference_sources.generate_sources(
                    root / "out", root, offline=True, source_keys=["energy"]
                )
            self.assertFalse((root / "out/energy.sqlite").exists())

    def test_existing_database_is_validated_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "example.sqlite"
            rows = [{"entity": "original", "value": 3.0}]
            metadata = ("url", "citation", "license", "notes")
            reference_sources.write_database(database, rows, metadata)
            original = database.read_bytes()
            reference_sources.write_database(database, rows, metadata)
            self.assertEqual(database.read_bytes(), original)
            with self.assertRaisesRegex(ValueError, "preserved without changes"):
                reference_sources.write_database(
                    database, [{"entity": "replacement", "value": 9.0}], metadata
                )
            self.assertEqual(database.read_bytes(), original)
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(
                    connection.execute("SELECT * FROM facts").fetchall(),
                    [("original", 3.0)],
                )

    def test_default_command_does_not_register_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                sys, "argv", ["install_reference_sources.py", "--output", directory]
            ):
                with patch.object(
                    reference_sources, "generate_sources", return_value=[]
                ):
                    with patch.object(
                        reference_sources, "register_sources"
                    ) as register:
                        reference_sources.main()
                        register.assert_not_called()


if __name__ == "__main__":
    unittest.main()
