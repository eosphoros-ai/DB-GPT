# Customizing Operators

Customization comes in three levels. Start at the lowest level that can express your requirement —
most "new operator" requests are actually configuration.

## Level 0 — Compose an agent node (zero code)

A new analysis capability is usually a goal + tool boundary:

```json
{
  "id": "n4",
  "kind": "agent",
  "label": "Cohort Retention",
  "config": {
    "agent_profile": "react_data",
    "goal": "Compute weekly cohort retention from the upstream semantic card; verify denominators with an independent SQL path. Output: retention table + three findings.",
    "tools": ["sql_query", "code_interpreter"],
    "datasources": ["Walmart_Sales"],
    "max_turns": 8
  }
}
```

Add it to a flow in the editor, connect it, deploy. Done — no Python, no restart.

## Level 1 — Mount skills, tools and MCP

- **Skills**: drop a skill package into the skills directory; it appears in the node property
  panel. Selecting it mounts `load_skill` / `execute_skill_script_file` and lists the skill in the
  node prompt. Skills carry templates (e.g. HTML report skeletons) that `html_interpreter` can
  fill via `template_path` + `data`.
- **MCP**: add `sse:<url>` / `http:<url>` entries to a node's MCP list to expose an external tool
  server to that node only.
- **Datasources / knowledge**: binding a connector or knowledge space is what makes `sql_query`
  or the `kb_*` family exist inside the node.

## Level 2 — Write a Python operator

When behavior must be deterministic (file loading, chart rendering, gating) or must talk to
infrastructure directly, write an operator. The pattern used by all built-in product nodes:

```python
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.util.i18n_utils import _


class HOMyOperator(MapOperator[str, str]):
    """One-line description shown in the editor palette."""

    metadata = ViewMetadata(
        label=_("My Operator"),
        name="taskflow_my_operator",
        description=_("Deterministic step that transforms upstream text."),
        category=OperatorCategory.COMMON,
        parameters=[
            Parameter.build_from(_("Limit"), "limit", int, optional=True,
                                 default=100, description=_("Row cap.")),
        ],
        inputs=[IOField.build_from(_("Upstream"), "content", str,
                                   description=_("Upstream node output."))],
        outputs=[IOField.build_from(_("Result"), "result", str,
                                    description=_("Transformed output."))],
    )

    def __init__(self, limit: int = 100, **kwargs):
        super().__init__(**kwargs)
        self._limit = limit

    async def map(self, content: str) -> str:
        return content[: self._limit]
```

Checklist for a well-behaved product operator:

1. **`ViewMetadata` is the UI.** Label/description/parameters render in the editor palette and
   property panel; keep them i18n-wrapped with `_()`.
2. **Emit a step marker.** Wrap your output with `build_step_marker(...)` (see
   `dbgpt_app/operators/taskflow.py`) so the run card shows your node like every other node, with
   duration and status.
3. **Strip protocol from content.** Apply `strip_step_markers` / `strip_artifact_fences` to
   upstream text before feeding it to an LLM or returning it.
4. **Register artifacts, don't inline them.** Large payloads (HTML, tables) go to disk under the
   pilot artifact root and travel as `vis-flow-artifact` metadata fences; the chat UI renders
   chips and serves files through the scoped artifact endpoint.
5. **Fail loudly.** Raise on infrastructure errors; return text only for *content*-level results.
   A node that "succeeds" with an error string poisons every downstream contract.

Operators are discovered by the flow runtime through package metadata scanning — place the module
inside a loaded `dbgpt` package (e.g. `dbgpt_app/operators/`) and restart the server; the kind
then appears in the editor palette and can be referenced from the TaskFlow DSL compiler.

## Extending the TaskFlow DSL itself

Adding a brand-new `kind` (palette entry + compile rule + config validation) means extending the
compiler's `NODE_KINDS` manifest and its builder in
`dbgpt_serve/flow/taskflow/compiler.py`, plus the web kind manifest and i18n labels. That is a
product change, not a user extension — propose it with a mockup first.

Next: [runs & artifacts](./runs-and-artifacts.md) · [editor](./editor.md)
