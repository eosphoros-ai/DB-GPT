# Dashboard browser regression inputs

These JSON files are maintained test inputs, not fresh execution evidence. Seven
browser specs load them through `../fixtures.ts`, relative to the test directory.
A clean checkout does not need the author's historical `docs/dashboard/evidence`
directory to load these tests.

| Directory | Purpose |
|---|---|
| walmart | Temporal rendering, saved layout and query snapshots |
| apple | Editor overflow and published financial data |
| retail | Filter and editing feedback |
| northwind | Template workspace and source preview |
| tools | Three tool failure event shapes |
| questions | Original case 04 and 07 question arrays |

[manifest.json](manifest.json) records each input's original archive path, source
SHA-256, current SHA-256 and extraction/sanitization step. Archive paths are
provenance, not files needed at runtime. Owner, conversation, turn and host metadata
use fixture placeholders. Dashboard IDs, Schema, queries and business values are
preserved. Question fixtures contain only the question arrays used by the specs;
the Northwind snapshot has its transport envelope removed.

Case 07 replaces a personal absolute snapshot path with a portable display-only
path in the question text. No test opens that path; it exercises a free-text
question. Its question payload matches the backend contract fixture.

The real Walmart aggregates are historical regression values. The separate
repository demo generator produces synthetic retail data and is not their source.
Apple financial facts come from the repository's
[SEC source index](../../../../examples/dashboard/sources/apple-sec-sources.json).

To update an input, explain the behavior being exercised, inspect its values and
remove credentials or personal metadata, then update the manifest hash and run the
affected specs. Do not regenerate all fixtures solely to make assertions pass.
Run `python scripts/dashboard/verify_pr_materials.py` from the repository root to
check hashes, data relationships and maintained documentation links.

From `web`, `npm run test:e2e:dashboard -- --list` verifies test collection without
starting a server. Actual browser execution needs the environment described in the
[developer guide](../../../../docs/dashboard/DEVELOPER_GUIDE.md).
