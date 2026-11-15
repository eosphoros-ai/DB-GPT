---
title: Semantic Center troubleshooting
---

# Semantic Center troubleshooting

| Symptom | Check and action |
| --- | --- |
| Connection missing from the spaces list | Verify it in Datasources, run registration, and inspect per-connection failures. |
| Space not activated | Review activation options. Metadata can be read before activation, but that does not publish drafts. |
| Metric search is empty | Confirm the matching database, published version, spelling, and saved synonyms. Search a short business term. |
| Business definition is missing | Confirm it is published and still targets an existing table/column. |
| Requested version is absent | Read the version list and resolve the required version; retrieval does not fall back. |
| Fields no longer match the database | Synchronize metadata after schema changes and review affected definitions. |
| No semantic tools appear | Verify the database connection loaded and that the chosen agent path mounts the tools. |
| Guardrails appear but SQL ignores them | UI records are not universal execution enforcement. Inspect effective tool and database permissions. |

## Report a useful issue

Include the plugin, database connection name without credentials, metric name/ID and version, space/publication state, search term, error message, and the relevant tool result. Remove credentials and sensitive rows.

Do not “fix” empty search by publishing unreviewed drafts. Missing definitions are actionable information: clarify the business scope before calculating.
