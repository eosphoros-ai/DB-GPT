---
title: Plugin package reference
---

# Plugin package reference

The current loader supports `.dbgpt-plugin/plugin.json`, the compatible `.qwenwork-plugin/plugin.json`, and legacy `suite.yaml` packages. Prefer the native manifest for new work.

## Native package layout

```text
my-data-plugin/
  .dbgpt-plugin/
    plugin.json
  skills/
    scoped-query/
      SKILL.md
  prompts/
    playbook.md
```

A small starting manifest:

```json
{
  "name": "my-data-plugin",
  "version": "1.0.0",
  "displayName": "Scoped Data Query",
  "displayNameCn": "限定范围取数",
  "descriptionEn": "Answer bounded questions from a selected database.",
  "descriptionZh": "基于选定数据库回答限定范围的数据问题。",
  "skills": ["skills/scoped-query"],
  "dbgpt": {
    "scenario_id": "query",
    "execution": "react",
    "sop": "prompts/playbook.md",
    "required_resources": ["database"]
  }
}
```

This illustrates a layout; it is not a ready-to-run complete scenario. Supply the referenced instructions and test the package in the target DB-GPT version.

## Fields and runtime support

`name` identifies the package; use a stable unique value. Supply version and localized display/description fields for a usable directory card. `skills` and `dbgpt.sop` reference package resources. `dbgpt` holds DB-GPT-specific scenario, execution, resource, recommendation, and tool declarations.

Existing official manifests include semantic policies, approval overrides, and output contracts. Treat them as declarations whose individual runtime support must be verified. In particular, declaring a semantic pin, estimated scan threshold, or row-level rule does not make the current semantic read tools enforce it.

## Package and verify

ZIP the package with its manifest and referenced resources. Keep paths within the package; do not include credentials, local environment files, or generated private reports. Import through **Plugins → + Add**, inspect the card and loaded skills, then run a small checkable task.

Use the current loader and its tests as the detailed compatibility reference: `packages/dbgpt-serve/src/dbgpt_serve/plugins/loader.py` and the adjacent `tests/` directory. Validate every capability you document with a real tool result.
