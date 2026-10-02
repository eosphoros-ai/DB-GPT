"""Knowledge source framework glue (bindings, sync engine, ingest adapter).

Contract layer (connectors) lives in dbgpt_ext; this package owns the
knowledge-space integration: storage, credentials encryption, the ingest
seam into ``Service._sync_knowledge_document`` and the due-binding scheduler.
"""
