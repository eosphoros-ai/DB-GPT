import logging
import threading
import time

import schedule

from dbgpt.component import BaseComponent, SystemApp

logger = logging.getLogger(__name__)


class DefaultScheduler(BaseComponent):
    """The default scheduler"""

    name = "dbgpt_default_scheduler"

    def __init__(
        self,
        system_app: SystemApp,
        scheduler_delay_ms: int = 5000,
        scheduler_interval_ms: int = 1000,
    ):
        super().__init__(system_app)
        self.system_app = system_app
        self._scheduler_interval_ms = scheduler_interval_ms
        self._scheduler_delay_ms = scheduler_delay_ms
        self._stop_event = threading.Event()

    def init_app(self, system_app: SystemApp):
        self.system_app = system_app

    def after_start(self):
        thread = threading.Thread(target=self._scheduler)
        thread.start()
        self._stop_event.clear()

    def before_stop(self):
        self._stop_event.set()

    def _scheduler(self):
        time.sleep(self._scheduler_delay_ms / 1000)
        while not self._stop_event.is_set():
            try:
                schedule.run_pending()
            except Exception as e:
                logger.debug(f"Scheduler error: {e}")
            finally:
                time.sleep(self._scheduler_interval_ms / 1000)
