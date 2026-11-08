"""Warning helpers for models loaded with remote code execution enabled."""

import logging
import threading

logger = logging.getLogger(__name__)

_TRUST_REMOTE_CODE_WARNING_EMITTED = False
_TRUST_REMOTE_CODE_WARNING_LOCK = threading.Lock()

TRUST_REMOTE_CODE_WARNING = (
    "Loading a Hugging Face model with trust_remote_code=True: Python code "
    "shipped in the model repository may be executed. Only load models from "
    "sources you trust. To disable remote code execution, set "
    "trust_remote_code=False in the model parameters; for vLLM deployments, "
    "also set it to False in extras when extras is used, because extras takes "
    "precedence."
)


def warn_trust_remote_code() -> None:
    """Warn once per process when a model is loaded with remote code enabled.

    The warning is emitted at most once per process so that loading several
    models does not flood the logs. When ``WARNING`` logging is disabled the
    flag is intentionally not consumed, so the warning is still emitted if
    logging is enabled later. The flag is set after the warning has been
    logged, so a logging failure does not swallow the warning for later loads.
    """
    global _TRUST_REMOTE_CODE_WARNING_EMITTED

    if _TRUST_REMOTE_CODE_WARNING_EMITTED or not logger.isEnabledFor(logging.WARNING):
        return

    with _TRUST_REMOTE_CODE_WARNING_LOCK:
        if _TRUST_REMOTE_CODE_WARNING_EMITTED:
            return
        logger.warning(TRUST_REMOTE_CODE_WARNING)
        _TRUST_REMOTE_CODE_WARNING_EMITTED = True
