# shell_interpreter

## Overview

`shell_interpreter` executes shell / bash commands in a sandboxed environment.

It is intended for command-line workflows rather than data analysis logic.

## Parameters

```json
{
  "code": "shell command(s)"
}
```

## What it does

- runs bash / shell commands
- enforces sandbox isolation
- applies security checks for dangerous patterns
- limits memory and execution time

## Runtime characteristics

- memory limit: **256MB**
- timeout: **30s**
- no persistent shell state between calls

## When to use it

- inspect files and directories
- run CLI utilities such as `ls`, `grep`, `curl`, `git`, `pip`
- perform shell-level environment tasks

## Example

```json
{
  "code": "ls -la"
}
```

## Notes

- use `code_interpreter` for Python analysis instead
- use `html_interpreter` for final rendered output
- if a skill explicitly requires another execution path, follow the skill instructions
