import asyncio
import logging
from enum import Enum, auto
from typing import Dict, Optional, cast

from lyric import CodeResult, DefaultLyricDriver, PyTaskResourceConfig

from dbgpt.component import BaseComponent, SystemApp

logger = logging.getLogger(__name__)


class ServerState(Enum):
    INIT = auto()
    STARTING = auto()
    READY = auto()
    STOPPING = auto()
    STOPPED = auto()


class CodeServer(BaseComponent):
    def __init__(self, system_app: Optional[SystemApp] = None):
        self.sys_app = system_app
        super().__init__(system_app)
        self._lcd = DefaultLyricDriver()
        self._init_lock = asyncio.Lock()
        self._state = ServerState.INIT
        self._ready_event = asyncio.Event()

    def init_app(self, system_app: SystemApp):
        self.sys_app = system_app

    def before_start(self):
        if self._state == ServerState.INIT:
            self._state = ServerState.STARTING
            self._lcd.start()

    def before_stop(self):
        self._state = ServerState.STOPPING
        self._lcd.stop()
        self._state = ServerState.STOPPED
        self._ready_event.clear()

    async def async_after_start(self):
        await self._ensure_initialized()

    async def _ensure_initialized(self):
        """Ensure the server is initialized and workers are loaded."""
        if self._state == ServerState.READY:
            return

        async with self._init_lock:
            # Double check after acquiring lock
            if self._state == ServerState.READY:
                return

            if self._state == ServerState.INIT:
                logger.info("Starting code server...")
                self._state = ServerState.STARTING
                self._lcd.start()
            if self._state == ServerState.STARTING:
                await self._lcd.lyric.load_default_workers()
                self._state = ServerState.READY
                self._ready_event.set()
                logger.info("Code server is ready")

    async def wait_ready(self, timeout: Optional[float] = None) -> bool:
        """Wait until server is ready.

        Args:
            timeout: Maximum time to wait in seconds. None means wait forever.

        Returns:
            bool: True if server is ready, False if timeout occurred
        """
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def exec(
        self, code: str, lang: str, resources: Optional[PyTaskResourceConfig] = None
    ) -> CodeResult:
        await self._ensure_initialized()
        return await self._lcd.exec(code, lang, resources=resources)

    async def exec1(
        self,
        code: str,
        input_bytes: bytes,
        call_name: str,
        lang: str = "python",
        resources: Optional[PyTaskResourceConfig] = None,
    ) -> CodeResult:
        await self._ensure_initialized()
        return await self._lcd.exec1(
            code, input_bytes, call_name, lang=lang, resources=resources
        )

    async def parse_awel(self, code: str) -> Optional[Dict]:
        """Parse the AWEL code.

        Return the flow metadata.
        """
        raise NotImplementedError

    async def run_awel_operator(self, code: str):
        """Run an AWEL operator in remote mode."""
        raise NotImplementedError


_SYSTEM_APP: Optional[SystemApp] = None


def initialize_code_server(system_app: SystemApp):
    """Initialize the code server."""
    global _SYSTEM_APP
    _SYSTEM_APP = system_app
    code_server = CodeServer(system_app)
    system_app.register_instance(code_server)


async def get_code_server(
    system_app: Optional[SystemApp] = None,
    wait_ready: bool = True,
    timeout: Optional[float] = None,
) -> CodeServer:
    """Return the code server.

    Args:
        system_app (Optional[SystemApp]): The system app. Defaults to None.
        wait_ready (bool): Whether to wait for server to be ready. Defaults to True.
        timeout (Optional[float]): Maximum time to wait in seconds. None means wait forever.

    Returns:
        CodeServer: The code server.
    """
    if not _SYSTEM_APP:
        if not system_app:
            system_app = SystemApp()
        initialize_code_server(system_app)

    app = system_app or _SYSTEM_APP
    server = CodeServer.get_instance(cast(SystemApp, app))

    if wait_ready:
        await server._ensure_initialized()
        if not await server.wait_ready(timeout):
            raise TimeoutError("Timeout waiting for code server to be ready")

    return server
