# Metadata and Architecture Expert

An official built-in DB-GPT suite for physical data dictionaries, ER diagrams, schema documentation and modeling reviews.

Select the suite from the home page or composer, choose an authorized database and specify schemas or tables.

| Command | Output |
| --- | --- |
| /data-dictionary | Physical metadata CSV, preview and business-definition questions |
| /physical-er | Declared relationship table and copyable Mermaid ER source |
| /schema-doc | HTML schema documentation, with dictionary and relationship evidence |
| /model-review | Modeling proposals, candidate DDL and migration validation |

CSV files come from executed, untruncated catalog-query artifacts. Complete report tasks use the existing report tool. Physical constraints, published business definitions and inferred relationships are distinguished; physical ER is not cross-system lineage.

Semantic Center is optional. No DDL, shell, automatic publishing or business-data scans are enabled. See the [workflow](prompts/workflow.md) and [metadata boundaries](references/metadata-boundaries.md).
