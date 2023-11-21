from abc import ABC, abstractmethod
from typing import List
import os
import hashlib
import sys
import logging
import traceback

from .base import DAG

logger = logging.getLogger(__name__)


class DAGLoader(ABC):
    @abstractmethod
    def load_dags(self) -> List[DAG]:
        """Load dags"""


class LocalFileDAGLoader(DAGLoader):
    def __init__(self, filepath: str) -> None:
        super().__init__()
        self._filepath = filepath

    def load_dags(self) -> List[DAG]:
        if not os.path.exists(self._filepath):
            return []
        if os.path.isdir(self._filepath):
            return _process_directory(self._filepath)
        else:
            return _process_file(self._filepath)


def _process_directory(directory: str) -> List[DAG]:
    dags = []
    for file in os.listdir(directory):
        if file.endswith(".py"):
            filepath = os.path.join(directory, file)
            dags += _process_file(filepath)
    return dags


def _process_file(filepath) -> List[DAG]:
    mods = _load_modules_from_file(filepath)
    results = _process_modules(mods)
    return results


def _load_modules_from_file(filepath: str):
    import importlib
    import importlib.machinery
    import importlib.util

    logger.info(f"Importing {filepath}")

    org_mod_name, _ = os.path.splitext(os.path.split(filepath)[-1])
    path_hash = hashlib.sha1(filepath.encode("utf-8")).hexdigest()
    mod_name = f"unusual_prefix_{path_hash}_{org_mod_name}"

    if mod_name in sys.modules:
        del sys.modules[mod_name]

    def parse(mod_name, filepath):
        try:
            loader = importlib.machinery.SourceFileLoader(mod_name, filepath)
            spec = importlib.util.spec_from_loader(mod_name, loader)
            new_module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = new_module
            loader.exec_module(new_module)
            return [new_module]
        except Exception as e:
            msg = traceback.format_exc()
            logger.error(f"Failed to import: {filepath}, error message: {msg}")
            # TODO save error message
            return []

    return parse(mod_name, filepath)


def _process_modules(mods) -> List[DAG]:
    top_level_dags = (
        (o, m) for m in mods for o in m.__dict__.values() if isinstance(o, DAG)
    )
    found_dags = []
    for dag, mod in top_level_dags:
        try:
            # TODO validate dag params
            logger.info(f"Found dag {dag} from mod {mod} and model file {mod.__file__}")
            found_dags.append(dag)
        except Exception:
            msg = traceback.format_exc()
            logger.error(f"Failed to dag file, error message: {msg}")
    return found_dags
