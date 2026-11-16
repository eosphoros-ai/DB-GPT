# Skills Overview

> The skill definition on this page is adapted from the [Agent Skills](https://agentskills.io/what-are-skills) description, which frames skills as lightweight, self-contained capability packages that agents can discover, load, and apply on demand.

## What is a skill?

In DB-GPT, a skill is a reusable capability package that gives an agent a structured way to solve a task.

Instead of relying only on free-form reasoning, a skill provides a stable execution pattern for a specific kind of work.

<img
  src="/img/skill/skill_list.png"
  alt="DB-GPT skills overview"
  className="showcase-hero-image"
/>


## Skill definition

Adapted from the Agent Skills description, a skill can be understood as:

- a **lightweight extension format** for giving agents specialized knowledge and workflows
- a **package of know-how**, not just facts, APIs, or prompts
- a **progressive-disclosure unit** that can be discovered first and fully loaded only when needed
- a **self-contained bundle** of instructions, scripts, templates, and reference files
- a way to make agent behavior more **consistent, repeatable, and domain-aware**

In DB-GPT terms, a skill is not just “something the model knows.” It is a packaged workflow that helps the agent decide:

- what problem it is solving
- what tools it should use
- what order the steps should follow
- what outputs should be produced
- what constraints it should obey

## What a skill usually contains

A DB-GPT skill package often includes:

- a name
- instructions in `SKILL.md`
- optional scripts
- optional templates
- optional static resources or examples

At its core, a skill is a folder containing a `SKILL.md` file. This file includes metadata and instructions that tell an agent how to perform a specific task. Skills can also bundle scripts, templates, and reference materials.

```text
my-skill/
├── SKILL.md          # Required: instructions + metadata
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation loaded as needed
└── assets/           # Optional: templates, output resources, static files
```

## Skill anatomy

Following the structure used by DB-GPT's own skill-creator guidance, a skill is organized as a small self-contained package:

| Part | Required | Purpose |
|------|----------|---------|
| `SKILL.md` | Yes | Defines the skill's identity and instructions |
| `scripts/` | No | Stores executable code such as Python or shell helpers |
| `references/` | No | Stores documents that can be loaded into context only when needed |
| `assets/` | No | Stores templates, fonts, icons, boilerplate files, or other output resources |

### `SKILL.md`

`SKILL.md` is the entry point of the skill. It usually contains:

- metadata such as `name` and `description`
- the workflow instructions the agent should follow
- guidance on when to read additional references or use bundled resources

### `scripts/`

Use `scripts/` for executable helpers, such as:

- Python data-processing utilities
- shell scripts
- report-generation helpers
- automation code used by the skill

### `references/`

Use `references/` for supporting knowledge that should not always live inside `SKILL.md`, such as:

- API documentation
- business logic references
- schemas
- workflow guides
- policy or domain documents

This keeps `SKILL.md` smaller while still making deeper context available when the task requires it.

### `assets/`

Use `assets/` for files that support the output rather than the reasoning process, such as:

- HTML templates
- icons and logos
- fonts
- boilerplate frontend files
- report resources

## Why skills matter

Skills are useful when:

- a workflow should be standardized
- the task requires domain-specific reasoning
- reporting or analysis should follow a known pattern
- the agent should use curated instructions instead of improvising everything

## How skills work

The common execution pattern is:

1. The agent identifies that a task matches a skill.
2. The skill instructions are loaded.
3. The agent follows the skill-defined workflow.
4. The required tools are executed.
5. The final answer, report, or page is returned.

## Skills and built-in tools

Skills often orchestrate the built-in execution tools together:

- `load_skill` → load the skill instructions
- `sql_query` → retrieve structured data if needed
- `code_interpreter` → compute metrics, transform data, and generate charts
- `shell_interpreter` → run shell commands when required
- `html_interpreter` → render the final report or webpage

## Practical examples

### Financial report analysis

A financial-report skill can define:

- how to inspect uploaded reports
- how to compute indicators and compare periods
- how to generate charts and summaries
- how to render the final HTML report

### CSV / Excel analysis

A data-analysis skill can define:

- how to inspect a dataset
- how to calculate core metrics
- how to visualize outputs
- how to turn the result into a reusable report

## Good practices

- use skills when the workflow should be repeatable
- follow the skill instructions strictly
- prefer the tools required by the skill over ad-hoc alternatives
- use `html_interpreter` for final report rendering when the skill produces a webpage or report

## Next step

See [How to Use Skill](./how-to-use-skill.md) for the practical workflow.
