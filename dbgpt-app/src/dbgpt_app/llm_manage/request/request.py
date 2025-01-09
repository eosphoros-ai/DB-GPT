from dataclasses import dataclass


@dataclass
class ModelResponse:
    """ModelRequest"""

    """model_name: model_name"""
    model_name: str = None
    """model_type: model_type"""
    model_type: str = None
    """host: host"""
    host: str = None
    """port: port"""
    port: int = None
    """manager_host: manager_host"""
    manager_host: str = None
    """manager_port: manager_port"""
    manager_port: int = None
    """healthy: healthy"""
    healthy: bool = True

    """check_healthy: check_healthy"""
    check_healthy: bool = True
    prompt_template: str = None
    last_heartbeat: str = None
    stream_api: str = None
    nostream_api: str = None
