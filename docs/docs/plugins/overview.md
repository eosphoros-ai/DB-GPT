---
title: Plugins
---

# Plugins

A plugin packages a reusable way to solve a class of tasks. It combines scenario instructions, skills, supporting resources, and DB-GPT configuration so users can start from a focused method instead of writing a long prompt each time.

![Official plugin directory](/img/data-agent/en/plugins.png)

## Plugin, Skill, Tool, and Flow

| Building block | What it describes |
| --- | --- |
| Plugin | A scenario capability package, such as SQL Optimization Expert |
| Skill | A focused method with instructions and optional scripts/resources |
| Tool | An executable operation exposed to an agent |
| Flow | A graph of agent responsibilities, dependencies, and control nodes |

A plugin can contain several skills. A skill can describe how to use tools. A Flow can assign skills and resources to its agent nodes. None of these names alone grants access to a database or authorizes a change.

## Where to start

Use [official plugins](./official-plugins.md) for the five homepage scenarios. [Using plugins](./using-plugins.md) explains selection, enablement, import, and removal. [Package reference](./package-reference.md) explains how to build an importable package.

The **Market** tab is currently a placeholder. **Installed** currently lists enabled plugins. Do not interpret either view as a guarantee of a hosted marketplace or completed dependency installation.
