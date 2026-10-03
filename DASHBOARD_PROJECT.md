# Agent Dashboard

This integration adds schema-driven dashboard planning, editing, revision-aware saves,
query execution, templates, and fixed or live publication to the DB-GPT Data Assistant.

Start with the [maintained documentation](docs/dashboard/README.md),
[design](docs/dashboard/DESIGN.md), [retail example](docs/dashboard/demos/walmart.md),
and [financial example](docs/dashboard/demos/apple.md).

The [review scope](docs/dashboard/PR_SCOPE.md) separates the toolchain dependency from the Dashboard module and its required
chat, attachment and scheduled-task interfaces. Global theme/home, model and sandbox
changes are outside this candidate.
See [validation](docs/dashboard/VALIDATION.md) for dated results and outstanding checks.

Historical process reports and personal closeout materials are described in
[the archive policy](docs/dashboard/HISTORY.md); they are not runtime dependencies.
