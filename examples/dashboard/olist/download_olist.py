"""Download and verify the public Olist CSV archive from Kaggle.

Raw files are intentionally ignored by Git.  The source manifest pins the
dataset URL, version, license, archive digest, and expected file names.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "source-manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if destination not in target.parents and target != destination:
            raise ValueError(f"Archive member escapes destination: {member.filename}")
    archive.extractall(destination)


def download_and_extract(output: Path, force: bool = False) -> Path:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / "brazilian-ecommerce.zip"

    if force or not archive_path.exists():
        partial_path = archive_path.with_suffix(".zip.part")
        request = urllib.request.Request(
            manifest["download_api"],
            headers={"User-Agent": "DB-GPT-Dashboard-Lab/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                with partial_path.open("wb") as target:
                    shutil.copyfileobj(response, target)
            partial_path.replace(archive_path)
        finally:
            partial_path.unlink(missing_ok=True)

    actual_digest = _sha256(archive_path)
    expected_digest = manifest["archive_sha256"].lower()
    if actual_digest != expected_digest:
        raise ValueError(
            "Olist archive checksum mismatch: "
            f"expected {expected_digest}, got {actual_digest}"
        )

    extract_dir = output / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        actual_files = sorted(
            item.filename for item in archive.infolist() if not item.is_dir()
        )
        expected_files = sorted(manifest["files"])
        if actual_files != expected_files:
            raise ValueError(
                "Olist archive file list differs from the pinned manifest: "
                f"expected {expected_files}, got {actual_files}"
            )
        _safe_extract(archive, extract_dir)
    return extract_dir


def _verified_core_directory(output: Path) -> Path:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    mirror = manifest["fallback_mirror"]
    extract_dir = output / "extracted"
    for filename, expected in mirror["files"].items():
        path = extract_dir / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        if (
            path.stat().st_size != expected["size"]
            or _sha256(path) != expected["sha256"]
        ):
            raise ValueError(f"Olist core file checksum mismatch: {filename}")
    return extract_dir


def download_core_mirror(output: Path, force: bool = False) -> Path:
    """Download the eight required tables from a commit-pinned mirror."""

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    mirror = manifest["fallback_mirror"]
    extract_dir = output / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    for filename, expected in mirror["files"].items():
        target = extract_dir / filename
        if not force and target.is_file():
            if (
                target.stat().st_size == expected["size"]
                and _sha256(target) == expected["sha256"]
            ):
                continue
        partial = target.with_suffix(target.suffix + ".part")
        request = urllib.request.Request(
            f"{mirror['base_url']}/{filename}",
            headers={"User-Agent": "DB-GPT-Dashboard-Lab/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                with partial.open("wb") as stream:
                    shutil.copyfileobj(response, stream)
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        if (
            target.stat().st_size != expected["size"]
            or _sha256(target) != expected["sha256"]
        ):
            raise ValueError(f"Olist mirror file checksum mismatch: {filename}")
    return _verified_core_directory(output)


def resolve_source_files(output: Path, force: bool = False) -> Path:
    """Prefer verified local/Kaggle data and fall back only on network failure."""

    if not force:
        try:
            return _verified_core_directory(output)
        except (FileNotFoundError, ValueError):
            pass
    try:
        return download_and_extract(output, force=force)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Kaggle download unavailable ({exc}); using pinned core mirror.")
        return download_core_mirror(output, force=force)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "raw",
        help="Ignored directory used for the downloaded archive and CSV files.",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    extracted = resolve_source_files(args.output, force=args.force)
    print(f"Verified Olist CSV files at {extracted.resolve()}")


if __name__ == "__main__":
    main()
