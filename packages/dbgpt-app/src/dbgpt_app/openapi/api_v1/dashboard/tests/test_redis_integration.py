"""Opt-in cross-process collaboration ticket coverage against real Redis."""

import os

import pytest

from dbgpt_app.openapi.api_v1.dashboard.collaboration import (
    DashboardPatchError,
    RedisDashboardTicketStore,
)

pytestmark = pytest.mark.redis_integration


def _redis_url() -> str:
    value = os.getenv("DASHBOARD_TEST_REDIS_URL")
    if not value:
        pytest.skip("Set DASHBOARD_TEST_REDIS_URL to run Redis integration tests.")
    return value


def test_ticket_crosses_workers_and_is_consumed_exactly_once():
    issuer = RedisDashboardTicketStore(_redis_url(), ttl_seconds=30)
    consumer = RedisDashboardTicketStore(_redis_url(), ttl_seconds=30)
    try:
        issued = issuer.issue("dashboard-redis", "alice", "browser-a")
        claim = consumer.consume(issued.ticket, "dashboard-redis")

        assert (claim.actor_id, claim.client_id) == ("alice", "browser-a")
        with pytest.raises(DashboardPatchError, match="already used"):
            issuer.consume(issued.ticket, "dashboard-redis")
    finally:
        issuer.close()
        consumer.close()
