# Data resources documentation validation

Date: 2026-11-15

## Scope

- Rewrote the datasource guide and the knowledge base, knowledge chat, external source, and LLM-Wiki guides in English and simplified Chinese.
- Added 11 product screenshots per language: three datasource views and eight knowledge views.
- Added a knowledge base link to the documentation homepage and placed the knowledge usage manual before its technical principles.

## Evidence and limits

Screenshots were captured from the running product through its normal controls. English pages use the English UI; Chinese pages use the Chinese UI. Stored names/descriptions and some connector-provided descriptions retain their original language.

The existing `Olist_Analytics_Governance` space contains a document in `TODO` state with zero chunks. Its Wiki contains zero pages and the captured chat has no answer. The guides explicitly identify these as entry/state screenshots. No successful document ingestion, external synchronization, Wiki generation, or model-grounded answer is claimed.

The PostgreSQL form contains illustrative values, with no connection test or save performed. Datasource availability is described as deployment-dependent rather than a fixed global Yes/No support matrix.

Implementation/UI review informed the guide's boundaries:

- The creation form offers index methods and chunking options rather than an embedding-model selector.
- The UI's Structural Index corresponds to `FullText` and requires a configured backend.
- Upload acceptance, document processing, source synchronization, and Wiki generation are separate stages.
- A source binding can be saved after credential validation before its scope is complete.
- Removing a binding retains already synchronized documents.
- Wiki and code graph views serve different purposes.

## Checks

- All ten guides' local document links and screenshot paths were checked; screenshot directory languages match document languages.
- Paired screenshots were visually inspected for readable controls, complete creation forms, and hidden conversation history.
- English and Chinese production builds completed. Changed guide bodies introduce no broken links; the build still reports existing global `/versions` links and unrelated documentation warnings.
- Browser review of all ten final pages passed; every referenced screenshot resource returned HTTP 200.
- The English and Chinese homepage knowledge links point to their corresponding locale routes. The knowledge sidebar shows the usage manual before principles.
