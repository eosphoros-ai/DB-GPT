# Tools Overview

DB-GPT ships with a small set of built-in tools that power the **Agentic Data API**. These tools are the default execution surface for data analysis, skill-driven workflows, SQL exploration, shell access, and HTML report delivery.

The current source of truth lives in:

- `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py`

## Built-in tools

The core built-in tools are:

- `load_skill`
- `code_interpreter`
- `shell_interpreter`
- `sql_query`
- `html_interpreter`

They are exposed as agent tools and used by the Agentic Data workflow to move from reasoning → execution → presentation.

## Tool selection guide

| Tool | Use it for | Do not use it for |
|------|------------|-------------------|
| `load_skill` | Load a skill's instructions and workflow | Running code or shell commands |
| `code_interpreter` | Python analysis, charts, dataframe logic, calculations | Shell commands or final HTML rendering |
| `shell_interpreter` | Bash / CLI commands such as `ls`, `grep`, `curl`, `git`, `pip` | Python analysis or skill-specific script execution when a skill says otherwise |
| `sql_query` | Read-only SQL against the selected datasource | Any write/update/delete schema changes |
| `html_interpreter` | Final HTML page / report rendering | General Python computation or shell execution |

## Typical execution flow

For most agentic data tasks, the pattern is:

1. Use `load_skill` when the task matches a reusable skill.
2. Use `sql_query` to inspect structured data.
3. Use `code_interpreter` for Python analysis, chart generation, and data shaping.
4. Use `shell_interpreter` only for true shell / CLI work.
5. Use `html_interpreter` as the final presentation step for reports or web pages.

## Important rules

### 1. `html_interpreter` is the final presentation tool

When a user asks for:

- an HTML report
- a web page
- an interactive report
- a rendered analysis deliverable

the final rendering step should go through `html_interpreter`.

### 2. `sql_query` is read-only

`sql_query` only supports safe query access. It is designed for `SELECT`-style exploration, not data mutation.

### 3. `code_interpreter` calls are independent

Each `code_interpreter` call runs independently. Variables do **not** persist between calls, so every snippet must include its own imports, loading logic, and output statements.

### 4. `shell_interpreter` is for shell tasks only

Use `shell_interpreter` for CLI workflows. If a skill specifically requires another execution path, follow the skill instructions.

## Next step

See [Tool Resource](../modules/resource/tools.md) for the detailed meaning, parameters, examples, and usage patterns of each built-in tool.
