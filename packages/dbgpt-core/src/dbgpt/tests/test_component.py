import asyncio
from unittest.mock import patch

import pytest
from fastapi import FastAPI

from dbgpt.component import BaseComponent, SystemApp


class _SlowStartComponent(BaseComponent):
    name = "test_slow_start_component"

    def __init__(self, system_app=None):
        self.started = asyncio.Event()
        self.cancelled = False
        super().__init__(system_app)

    def init_app(self, system_app):
        pass

    async def async_after_start(self):
        self.started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            self.cancelled = True
            raise


def _build_system_app():
    handlers = {}

    def _register(app, event, handler):
        handlers[event] = handler

    with patch("dbgpt.util.fastapi.register_event_handler", _register):
        system_app = SystemApp(FastAPI())
    return system_app, handlers


@pytest.mark.asyncio
async def test_startup_task_is_kept_and_cancelled_on_shutdown():
    system_app, handlers = _build_system_app()
    component = system_app.register(_SlowStartComponent)

    await handlers["startup"]()
    await asyncio.wait_for(component.started.wait(), timeout=1)

    await handlers["shutdown"]()

    # The startup hooks still running at shutdown are cancelled and awaited
    assert component.cancelled
    assert system_app._startup_task.cancelled()
