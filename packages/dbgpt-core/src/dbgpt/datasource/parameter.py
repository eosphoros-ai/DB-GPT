from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional, Type

from dbgpt.util.configure import RegisterParameters
from dbgpt.util.parameter_utils import BaseParameters

if TYPE_CHECKING:
    from dbgpt.datasource.base import BaseConnector


@dataclass
class BaseDatasourceParameters(BaseParameters, RegisterParameters):
    """Base class for datasource parameters."""

    def engine_args(self) -> Optional[Dict[str, Any]]:
        """Return engine arguments."""
        return None

    def create_connector(self) -> "BaseConnector":
        """Create a connector."""
        raise NotImplementedError("Current connector does not support create_connector")

    @classmethod
    def from_persisted_state(
        cls: Type["BaseDatasourceParameters"], state: Dict[str, Any]
    ) -> "BaseDatasourceParameters":
        """Create a new instance from the persisted state."""
        mapping = cls._persisted_state_mapping()
        unmapping = {v: k for k, v in mapping.items()}
        new_state = {}
        for k, v in state.items():
            if k in unmapping:
                new_state[unmapping[k]] = v
            elif k == "ext_config" and isinstance(v, dict) and v:
                new_state.update(v)
        return cls(**new_state)

    def persisted_state(self) -> Dict[str, Any]:
        """Return the persisted state."""
        db_type = getattr(self, "__type__", "unknown")
        state = asdict(self)
        new_state = {"db_type": db_type}
        mapping = self._persisted_state_mapping()
        ext_config = {}
        for k, v in state.items():
            if k in mapping:
                new_state[mapping[k]] = v
            else:
                ext_config[k] = v
        new_state["ext_config"] = ext_config
        return new_state

    @classmethod
    def _persisted_state_mapping(cls) -> Dict[str, str]:
        """Return the mapping of persisted state.

        Tell how to save the persisted state to the database(DB-GPT datasource serve
        module).
        """
        return {
            "host": "db_host",
            "port": "db_port",
            "user": "db_user",
            "password": "db_pwd",
            "database": "db_name",
            "path": "db_path",
        }
