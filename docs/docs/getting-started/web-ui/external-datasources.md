---
sidebar_position: 3
title: External Data Sources
---

# Keep knowledge in sync with external sources

Source bindings connect a knowledge space to an external document platform or feed. Use them when the source changes regularly and uploading a new copy by hand would leave the agent's knowledge out of date.

There are three stages to check: **fetch source content → process documents → generate Wiki pages, if enabled**. A successful source sync does not certify that indexing or Wiki generation has finished.

## Choose a source

Open a [knowledge space](/docs/getting-started/web-ui/knowledge-base), select **Sources**, and click **Bind source**. You can also choose an external source card during space creation and continue into its binding flow.

![Sources tab before a binding is added](/img/data-agent/en/knowledge-sources.png)

The wizard shows the connectors registered in your deployment, alongside local document and text entry points.

![Source types and the four-step binding wizard](/img/data-agent/en/knowledge-binding.png)

The screenshots use the English UI. Some connector descriptions and existing resource names retain their original language. No external account is bound in this example.

| Source | Content and access to prepare |
|---|---|
| **Feishu Wiki** | Wiki resources visible to the app; prepare App ID, App Secret, document permissions, and resource access |
| **Feishu Drive** | Selected drive folders and supported documents; prepare app credentials and access to those folders |
| **Yuque** | Documents from selected personal or team repositories; prepare a token with access to them |
| **RSS / Atom** | Entries from a reachable feed URL |
| **Local documents / Text snippet** | Upload or paste content directly into the space |

Conversion depends on the connector and resource type. A link to a sheet or Base is not evidence that all its table data was imported. Inspect the resulting document content.

## Complete the binding

1. **Choose type.** Select the platform.
2. **Credentials.** Enter the required fields and validate access.
3. **Pick scope.** Select the resources to synchronize. Start with a small folder or repository and verify that the intended documents are visible.
4. **Sync strategy.** Set the schedule, sync mode, conflict handling, and deletion behavior offered by the connector, then finish.

| Setting | Decision to make |
|---|---|
| Schedule | Use manual sync for the first check; choose periodic sync when the scope is verified |
| Incremental / full | Fetch changes where supported, or scan the selected scope |
| Conflict handling | Decide whether existing local content should be updated or skipped |
| Source deletions | Decide whether source removals should propagate locally; check the connector's full-sync behavior |

:::info Finish the scope configuration
The current wizard can save a binding after credential validation, before scope selection is complete. Closing it at that point can leave an incomplete binding. Check **Sources** afterward and finish its configuration or remove the unused binding. With no selected targets, the initial fetch can be skipped.
:::

After finishing, inspect the binding's status and sync logs. Confirm created or updated documents in **File View**, then check their chunks and processing status. If Wiki is enabled, check its generation separately.

## Maintain a binding

| Action | Effect |
|---|---|
| **Sync now** | Run synchronization for the configured scope |
| **Pause / Resume** | Stop or resume scheduled synchronization |
| **Sync logs** | Inspect fetched, created, updated, skipped, failed, or deleted counts and errors |
| **Delete** | Remove the binding while keeping previously synchronized documents |

A binding may be active, paused, running, or in error. Check the last successful sync and errors before assuming the local knowledge is current. Pausing or deleting a binding does not automatically retire the documents it previously imported.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Credential validation fails | App/token validity, required permissions, publication where applicable, and resource access |
| Scope tree is empty | Whether the app or token can see the intended resources |
| Binding exists but no documents arrive | Selected targets, sync mode, logs, and server network access |
| Rate limit (`HTTP 429`) | Provider limits, sync frequency, and concurrent clients |
| TLS verification fails | Configure the trusted corporate CA bundle, for example `DB_GPT_KS_CA_BUNDLE`, and check the server's certificate trust |
| Credential encryption error | Server knowledge-source encryption configuration and persistent key availability; consult server logs |
| Sync succeeds but chat or Wiki fails | Document processing, storage/embedding dependencies, and the language model service |

For a new platform, see the repository's `docs/design/datasource-connector-dev-guide.md`. Connector registration makes a platform discoverable; its permission and synchronization behavior still need validation.
