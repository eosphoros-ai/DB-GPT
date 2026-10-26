import os
import subprocess
import sys


def test_production_import_without_redis_only_disables_collaboration():
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    env["DBGPT_DASHBOARD_PRODUCTION_MODE"] = "true"
    env.pop("DBGPT_DASHBOARD_COLLAB_REDIS_URL", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from dbgpt_app.openapi.api_v1.dashboard import collaboration, api
try:
    collaboration.ticket_store.issue('dashboard', 'alice', 'client')
except collaboration.DashboardCollaborationUnavailable:
    pass
else:
    raise AssertionError('Production collaboration must still fail closed')
""",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
