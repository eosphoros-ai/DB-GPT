"""Semantic center: six-layer semantic stack for DB-GPT data agents.

Storage split (see ``docs/design/semantic-center-impl-plan.md``):

- The tables in :mod:`dbgpt_serve.semantic.models` (structured meta DB) are the
  **source of truth** for L1 metadata / L2 annotations / L3 metrics+calibers /
  L4 join graph / L5 examples / L6 guardrail rules.
- Vector chunks live in the KB managed space ``semantic::<conn_id>`` (derived
  index, read-only) and are (re)built from these tables by the publisher.

Field naming follows the repo convention (``gmt_created`` / ``gmt_modified``),
which maps to ``created_at`` / ``updated_at`` in the design doc.
"""

__version__ = "0.1.0"
