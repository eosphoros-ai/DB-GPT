"""Bundled snapshot of the models.dev catalog.

The snapshot provides fresher / richer model metadata (context length, output
length, function-calling support) than the hardcoded ``ModelMetadata`` entries
registered with each proxy client. It is consumed by
:func:`dbgpt.model.adapter.base.get_supported_models` as a first-class source,
with the hardcoded registry kept as a fallback.

See ``dbgpt/model/proxy/models_dev_catalog.json`` for the raw data.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent / "proxy" / "models_dev_catalog.json"
)


@lru_cache(maxsize=1)
def _load_catalog() -> Dict[str, Any]:
    try:
        with open(_CATALOG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_models_dev_models(provider: str) -> Optional[List[Dict[str, Any]]]:
    """Return the models.dev model list for a provider, if a snapshot exists."""
    entry = _load_catalog().get(provider)
    if not entry:
        return None
    models = entry.get("models")
    return models if isinstance(models, list) else None