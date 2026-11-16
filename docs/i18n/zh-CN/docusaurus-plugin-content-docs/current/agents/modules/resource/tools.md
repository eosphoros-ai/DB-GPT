# Built-in tools

DB-GPT provides a small set of built-in tools in the **Agentic Data API**.

These tools are the core execution layer for:

- loading reusable skills
- running Python analysis
- executing shell commands
- querying structured data
- rendering HTML reports

Source of truth:

- `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py`

## Built-in tools

- [load_skill](./tools/load-skill.md)
- [code_interpreter](./tools/code-interpreter.md)
- [shell_interpreter](./tools/shell-interpreter.md)
- [sql_query](./tools/sql-query.md)
- [html_interpreter](./tools/html-interpreter.md)

## Recommended execution order

### Skill-driven workflow

1. `load_skill`
2. `sql_query` or `code_interpreter`
3. `html_interpreter` for final delivery

### Structured data workflow

1. `sql_query`
2. `code_interpreter`
3. `html_interpreter`

### Shell-assisted workflow

1. `shell_interpreter`
2. `code_interpreter`
3. `html_interpreter` if the result must be rendered

## Tool selection guide

| Tool | Use it for | Avoid using it for |
|------|------------|--------------------|
| `load_skill` | Loading skill instructions and workflow definitions | Running code or shell commands |
| `code_interpreter` | Python analysis, calculations, charts, dataframe work | Shell commands or final HTML rendering |
| `shell_interpreter` | CLI commands and environment inspection | Python analysis or final report rendering |
| `sql_query` | Read-only SQL exploration | Writes, schema changes, destructive SQL |
| `html_interpreter` | Final HTML page / report rendering | Computation or shell execution |
