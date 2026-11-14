"""Shared package-tree transaction for uploads and generated artifacts."""

import contextlib
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Iterator

_LOCK = threading.RLock()


@contextlib.contextmanager
def installation_lock(root: Path) -> Iterator[None]:
    import fcntl

    lock_path = root.parent / f".{root.name}-installation.lock"
    with _LOCK, lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def commit_package(
    root: Path,
    source: Path,
    name: str,
    register: Callable[[Path], Any],
    *,
    replace_existing: bool = True,
) -> Any:
    """Publish a complete tree and recover it if registry registration fails.

    Generated installs never replace a different tree. Their registry callback
    must commit the registration and audit in one database transaction.
    """
    from .loader import package_digest

    with installation_lock(root):
        target = root / name
        if not target.resolve().is_relative_to(root.resolve()) or target.is_symlink():
            raise ValueError("unsafe installation target")
        if target.exists() and not replace_existing:
            if package_digest(source) != package_digest(target):
                raise ValueError("same-name package exists: rename and rebuild")
            return register(target)
        with tempfile.TemporaryDirectory(dir=root, prefix=".suite-install-") as temp:
            backup = Path(temp) / "previous"
            stage = Path(temp) / "package"
            shutil.copytree(source, stage)
            if target.exists():
                target.rename(backup)
            try:
                stage.rename(target)
                return register(target)
            except Exception:
                if target.exists():
                    shutil.rmtree(target)
                if backup.exists():
                    backup.rename(target)
                raise
