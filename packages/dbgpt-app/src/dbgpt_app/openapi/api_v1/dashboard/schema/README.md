# Dashboard Schema v1

`dashboard.schema.json` is the checked-in JSON Schema generated from
`DashboardSchemaV1`. The REST endpoint `GET /api/v1/dashboards/schema` exposes the
same contract to the web editor, where Ajv performs a fast client-side check.

The server always re-validates the Pydantic model, cross-field rules, and SQL. A
successful browser-side check is never treated as authorization to execute SQL.
