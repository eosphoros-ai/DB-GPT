# How to Use Skill

## Basic usage flow

In practice, using a skill usually follows this pattern:

1. Identify the right skill for the task.
2. Load the skill instructions.
3. Follow the skill-defined workflow.
4. Use the required built-in tools.
5. Return the final result or render the final report.

## Common tool flow

Depending on the skill, the execution path often looks like this:

- `load_skill` → load the skill instructions
- `sql_query` → retrieve structured data if needed
- `code_interpreter` → compute metrics, transform data, generate charts
- `shell_interpreter` → run shell commands when required
- `html_interpreter` → render the final HTML report or page

## Example scenarios

### Financial report analysis

The agent can:

1. load the financial-report skill
2. execute the required data extraction and analysis steps
3. generate charts and metrics
4. use `html_interpreter` to render the final report

![Financial Report Analysis Skill Example](/img/skill/use_financial_report_analysis_skill.png)

### CSV / Excel analysis

The agent can:

1. load a data analysis skill
2. inspect the uploaded file
3. use Python analysis to calculate metrics and visualize results
4. render the output as a report if needed

![CSV Data Analysis Skill Example](/img/skill/use_csv_data_skill.png)

## Good practices

- use skills when the workflow should be repeatable
- follow the skill instructions strictly
- prefer the tools required by the skill over ad-hoc alternatives
- use `html_interpreter` for final report rendering when the skill produces a webpage or report

## Related reading

- [dbgpts Introduction](./introduction.md)
- [Tools Overview](../agents/introduction/tools.md)
- [Built-in tools](../agents/modules/resource/tools.md)
