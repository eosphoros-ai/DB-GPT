---
title: Using plugins
---

# Using plugins

## Find and inspect

Open **Plugins**. Browse **Official**, **Enterprise**, **Installed**, or **Market**. Use the capability filters or search by plugin, capability, or scenario.

![Plugin directory with scenario icons and capability filters](/img/data-agent/en/plugins.png)

Click a plugin name to open its detail drawer. **Overview** shows expected deliverables, an example question, and the package README. **Skills** lists commands and skills. **Configuration** shows declared execution settings, allowed/excluded tools, and default context; these declarations do not prove that a tool is available or a permission is enforced.

![Plugin detail drawer and expected deliverables](/img/data-agent/en/plugins-detail.png)

Click **Manage** to reveal enable switches in the directory, or use the switch in the detail drawer. **Installed** includes enabled, disabled, and installed-but-not-enabled plugins. Enabled official homepage plugins appear as scenario buttons.

![Manage mode with plugin enable switches](/img/data-agent/en/plugins-manage.png)

## Start a task

Click **Use** in the directory. A plugin with several commands opens the **Skills** tab so you can choose a command; a plugin with one command opens the homepage directly. The homepage displays the selected plugin and, when applicable, the command beside the input.

You can also choose a homepage scenario or open **+ → Expert suite** in the composer. The same plugin icons and names identify the selection in each location.

![Choose an enabled plugin from the composer context menu](/img/data-agent/en/plugin-picker.png)

Attach the required database or files, then choose a recommended question or enter your own request. Expert questions often need your SQL or table list added before sending.

Quick commands such as `/sql-diagnose` and `/data-dictionary` help select a task method. They do not substitute for required resources, tool permissions, or a working model.

## Import a team package

Click **Add → Import plugin ZIP** and select a ZIP containing a supported plugin manifest or legacy suite definition. **Add → Create with AI** opens the plugin creation task on the homepage. Import only packages whose instructions and scripts you trust. Confirm the imported card, inspect its resources, and enable it when ready.

Use **Enterprise** to find team imports. Disabling prevents selection for new tasks without deleting the package. To uninstall, open the detail drawer, choose **… → Uninstall**, and review the confirmation. Package files remain on disk; follow the server's response for whether removal is allowed.

## Check dependencies

Before a real task, verify the model, database, required files, tool environment, and any MCP services. An imported or enabled plugin does not mean these dependencies have been provisioned.

Next: [Official plugins](./official-plugins.md) · [Package reference](./package-reference.md).
