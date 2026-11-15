---
title: Datasources
---

# Connect a database

A datasource gives DB-GPT a connection to the database you want to query, analyze, or inspect. Connect it once, then select it when starting a data task. A successful connection establishes access; business definitions such as “net receipts” belong in the [Semantic Layer](/docs/semantic-center/overview).

For documents, policies, or runbooks, use a [knowledge base](/docs/getting-started/web-ui/knowledge-base).

## Before you connect

Prepare the database address, port, database name, and credentials. Use an account with the permissions your task needs; for analysis, start with read access to the relevant tables. The **DB-GPT server** must be able to reach the database.

For SQLite and DuckDB, prepare the database file on the server. A path on your laptop is usable only if DB-GPT runs there. In a container, mount the file and enter its path **inside the container**.

## 1. Choose a database type

Open **Datasources** in the sidebar. The page has two views:

| View | Use it to |
|---|---|
| **Connections** | Find existing connections, edit their settings, or refresh metadata |
| **Database catalog** | Explore database types and add a connection |

![Existing database connections](/img/data-agent/en/datasource-list.png)

In **Database catalog**, search by name or filter by category. Choose an available card, or click **Add data source** and select a database type.

![Database catalog with categories and availability](/img/data-agent/en/datasource-catalog.png)

:::info Availability depends on your deployment
The server's registered connectors determine which database types you can select. **Unavailable in this environment** means the connector is unavailable in this deployment. Check its driver, dependencies, and server configuration rather than treating a disabled card as a universal support statement.
:::

## 2. Fill in the connection

The form changes with the selected connector. For PostgreSQL, enter the host, port, username, password if required, database name, and schema. Expand **Advanced settings** when your deployment requires additional connector options.

![PostgreSQL connection form with example values](/img/data-agent/en/datasource-create.png)

The values shown above illustrate the form; they are not a tested connection. Replace them with your own settings.

| Field | What to enter |
|---|---|
| Host and port | The address reachable from the DB-GPT server |
| Username and password | Credentials for the intended access scope |
| Database name / schema | The database and, where supported, schema to inspect |
| File path | For file databases, a path accessible to the server process |
| Description | A short explanation of what this connection is for |

Click **Test connection** and resolve any error before saving. Then click **Add data source**. Saving also checks the connection; an earlier successful test does not guarantee that changed settings will work.

## 3. Start a data task

Return to **Connections** and confirm that the connection appears. Start a new task from the homepage, select that datasource, and ask a small, verifiable question—for example, “List the tables available in this database.”

For business analysis, continue with the [Semantic Layer](/docs/semantic-center/overview) to define metrics and relationships, then choose a [scenario plugin](/docs/plugins/overview). Inspect the SQL and results returned by the task before using them in a decision.

## Maintain a connection

Use the actions on a connection card to edit settings, refresh metadata, or delete the connection. Refresh metadata after schema changes so DB-GPT can obtain updated database information. This is separate from synchronizing and publishing definitions in the Semantic Layer.

Deleting a connection removes its DB-GPT connection configuration. It does not delete tables or records in the source database. Tasks that depend on that connection may need a replacement.

## If something goes wrong

| Symptom | What to check |
|---|---|
| Timeout or connection refused | Server-to-database routing, firewall, host, port, and whether the database is listening |
| Authentication or permission error | Credentials and grants on the selected database/schema |
| File not found | Server path, container mount, and file permissions |
| Database type unavailable | Connector registration, required drivers, and installation extras |
| Connection works but tables are missing | Selected schema, account visibility, and refreshed metadata |
| Queries run but business totals are wrong | Metric definitions, date attribution, and join cardinality in the Semantic Layer |
