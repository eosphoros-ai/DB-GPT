---
title: Using plugins
---

# Using plugins

## Find and inspect

Open **Plugins**. Browse **Official**, **Enterprise**, or **Installed**, or search by name. Open a card to inspect its description, skills, scenario, and execution configuration before using it.

![Plugin directory and enable switches](/img/data-agent/en/plugins.png)

The enable switch controls whether the plugin is active. Installed is an enabled-plugin view; a disabled package may still exist in the registry. Official enabled homepage plugins appear as scenario buttons in the current homepage order.

## Start a task

Return to the homepage, choose a scenario, attach the required database or files, and choose a recommended question. Expert questions often need your SQL or table list added before sending.

Quick commands such as `/sql-diagnose` and `/data-dictionary` help select a task method. They do not substitute for required resources, tool permissions, or a working model.

## Import a team package

Click **+ Add** and select a ZIP containing a supported plugin manifest or legacy suite definition. Import only packages whose instructions and scripts you trust. Confirm the imported card, inspect its resources, and enable it when ready.

Use **Enterprise** to find team imports. Disabling stops active use without implying deletion; uninstall removes an eligible imported package. Follow the UI's available actions—built-in packages may not offer the same removal controls.

## Check dependencies

Before a real task, verify the model, database, required files, tool environment, and any MCP services. An imported or enabled plugin does not mean these dependencies have been provisioned.

Next: [Official plugins](./official-plugins.md) · [Package reference](./package-reference.md).
