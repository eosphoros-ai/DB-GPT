# Dashboard identity and authorization integration

## Identity source

Dashboard APIs do not create a second login or session system. Every protected
route receives DB-GPT's existing `UserRequest` through
`Depends(get_user_from_headers)`, then persists only that upstream `user_id` (or
the upstream-compatible `user_name`) as the dashboard actor ID.

The current upstream `get_user_from_headers` implementation is a development
header adapter and falls back to user `001`. A production deployment must put
DB-GPT behind its real authentication middleware or a trusted gateway that removes
client-supplied identity headers and injects the verified principal. Dashboard
RBAC must not be presented as login authentication.

## Two authorization layers

1. `DashboardAuthorizationService` controls actions on a dashboard object. The
   deny-by-default roles are viewer, editor, and owner.
2. `data_source_authorizer(actor_id, source_id)` is the adapter point for DB-GPT's
   deployment-specific data-source policy. Every source in a federated widget is
   passed to this adapter before query execution.

Dashboard membership never grants extra database privileges. Connectors still use
the deployment's existing database account, which should be read-only and limited
to the required schemas.

## Strict data-source authorization mode

Set `DBGPT_DASHBOARD_REQUIRE_DATA_SOURCE_AUTHORIZATION=1` (or construct
`DashboardAuthorizationService(require_data_source_authorizer=True)`) to fail closed
for query actions when no platform data-source policy adapter is configured. This
mode is intended for deployments that require user-to-data-source authorization.
The local demo keeps the default disabled because upstream DB-GPT does not currently
expose one universal table/column policy API across all connector deployments.

This is deliberately named a **strict data-source authorization mode**, not a blanket
"production mode". It closes one specific authorization boundary; production readiness
also requires verified authentication, read-only connector credentials, supported
frontend dependencies, TLS, secret management, monitoring, and deployment hardening.

### Verifiable implementation and tests

- Implementation:
  [`access.py`](../../packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/access.py)
  reads `DBGPT_DASHBOARD_REQUIRE_DATA_SOURCE_AUTHORIZATION` and rejects query actions
  when strict mode is enabled but no platform policy adapter is configured.
- API identity boundary:
  [`api.py`](../../packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/api.py)
  consumes DB-GPT's `UserRequest` and returns HTTP 401 when it contains no identity.
- Deterministic tests:
  [`test_access.py`](../../packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/tests/test_access.py)
  contains `test_strict_query_mode_fails_closed_without_platform_policy` and
  `test_strict_query_mode_can_be_enabled_from_environment`;
  [`test_api.py`](../../packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/tests/test_api.py)
  contains `test_dashboard_identity_comes_from_upstream_user_request`.

## Trust boundaries

- The public snapshot endpoint does not execute SQL.
- Share tokens do not identify a DB-GPT user and grant access only to one immutable
  published snapshot.
- Dashboard roles are scoped to one dashboard and cannot alter connector accounts.
- Audit details redact SQL, parameters, tokens, passwords, and credentials.
- Table/column authorization remains an upstream platform responsibility; it is not
  silently simulated by dashboard membership.
