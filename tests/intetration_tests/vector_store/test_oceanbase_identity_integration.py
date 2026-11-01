"""Real OceanBase writes/searches, SQLite metadata and public knowledge tools.

Requires a disposable OceanBase database with vector indexes enabled. Embeddings
are fixed numerical test inputs; neither database, resolver nor tool is mocked.
"""

import json
import os
import uuid
from types import SimpleNamespace

import pytest

if os.environ.get("DBGPT_RUN_LIVE_REGRESSIONS") != "1":
    pytest.skip(
        "Requires the explicitly enabled live OceanBase database",
        allow_module_level=True,
    )

from dbgpt._private.config import Config
from dbgpt.component import SystemApp
from dbgpt.core import Chunk, Embeddings
from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    bind_artifact_sink,
)
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.storage.metadata import _base_dao
from dbgpt.storage.metadata.db_manager import DatabaseManager
from dbgpt.util.executor_utils import DefaultExecutorFactory
from dbgpt_app.openapi.api_v1.tools.report_binding import validate_knowledge_sources
from dbgpt_ext.storage.vector_store.oceanbase_store import (
    OceanBaseConfig,
    OceanBaseStore,
)
from dbgpt_serve.rag.chunk_metadata import chunk_vector_id_map, prepare_document_chunks
from dbgpt_serve.rag.config import ServeConfig
from dbgpt_serve.rag.models.chunk_db import DocumentChunkEntity
from dbgpt_serve.rag.models.document_db import KnowledgeDocumentEntity
from dbgpt_serve.rag.models.models import KnowledgeSpaceEntity
from dbgpt_serve.rag.retriever.knowledge_space import KnowledgeSpaceRetriever
from dbgpt_serve.rag.service.service import Service
from dbgpt_serve.rag.storage_manager import StorageManager
from dbgpt_serve.rag.tools.kb_file_tools import kb_cat
from dbgpt_serve.rag.tools.semantic_search_tool import kb_semantic_search


class NumericalInputs(Embeddings):
    """Small, nonzero distances keep all three test rows above the threshold."""

    def embed_documents(self, texts):
        return [[0.01 * len(text), 0.1, 0.2] for text in texts]

    def embed_query(self, text):
        return [0.1, 0.1, 0.2]


class NumericalInputFactory(EmbeddingFactory):
    def init_app(self, system_app):
        pass

    def create(self, model_name=None, embedding_cls=None):
        return NumericalInputs()


@pytest.mark.asyncio
@pytest.mark.parametrize("duplicate", [True, False])
async def test_real_oceanbase_public_search_readback_and_binding(
    tmp_path, monkeypatch, duplicate
):
    config = OceanBaseConfig(
        ob_host=os.environ.get("DBGPT_OB_HOST", "127.0.0.1"),
        ob_port=int(os.environ.get("DBGPT_OB_PORT", "12881")),
        ob_user=os.environ.get("DBGPT_OB_USER", "root@test"),
        ob_password=os.environ.get("DBGPT_OB_PASSWORD", ""),
        ob_database=os.environ.get("DBGPT_OB_DATABASE", "dbgpt_f16_regression"),
    )
    name = "f16_" + uuid.uuid4().hex
    store = OceanBaseStore(config, name=name, embedding_fn=NumericalInputs())
    manager = DatabaseManager()
    manager.init_db(
        "sqlite:///" + (tmp_path / "knowledge.sqlite").as_posix(),
        engine_args={"connect_args": {"check_same_thread": False}},
    )
    # Route every real DAO to the isolated on-disk database, including those
    # instantiated internally by public tools and the retriever.
    monkeypatch.setattr(_base_dao, "db", manager)
    for entity in (KnowledgeSpaceEntity, KnowledgeDocumentEntity, DocumentChunkEntity):
        entity.__table__.create(manager.engine, checkfirst=True)
    app = SystemApp()
    app.config.set(
        "app_config",
        SimpleNamespace(
            rag=SimpleNamespace(
                similarity_top_k=3, storage=SimpleNamespace(vector=config)
            ),
            models=SimpleNamespace(default_embedding="numerical-test-inputs"),
        ),
    )
    app.register(NumericalInputFactory)
    executor = app.register(DefaultExecutorFactory, max_workers=2)
    storage = app.register(StorageManager)
    storage._store_cache[name] = store
    app.register(Service, ServeConfig(rerank_model=None))
    monkeypatch.setattr(Config(), "SYSTEM_APP", app)
    texts = ["shared body", "middle", "shared body" if duplicate else "unique end"]
    chunks = [Chunk(chunk_id=key, content=body) for key, body in zip("ABC", texts)]
    document = SimpleNamespace(
        id=1, doc_name="source.txt", summary='{"file_path":"source.txt"}'
    )
    try:
        prepare_document_chunks(chunks, document)
        vector_ids = store.load_document(chunks)
        assert len(vector_ids) == 3 and len(set(vector_ids)) == 3
        assert not set(vector_ids).intersection("ABC")
        prepare_document_chunks(chunks, document, vector_ids)
        with manager.session() as session:
            session.add(KnowledgeSpaceEntity(id=1, name=name, vector_type="oceanbase"))
            session.add(
                KnowledgeDocumentEntity(
                    id=1,
                    doc_name="source.txt",
                    doc_type="TEXT",
                    space=name,
                    summary=document.summary,
                    vector_ids=",".join(vector_ids),
                )
            )
            for chunk in chunks:
                session.add(
                    DocumentChunkEntity(
                        document_id=1,
                        doc_name="source.txt",
                        doc_type="TEXT",
                        content=chunk.content,
                        meta_info=json.dumps(chunk.metadata),
                    )
                )
        raw = store.similar_search_with_scores("source", 3, 0.0)
        assert {c.chunk_id for c in raw} == set(vector_ids)
        assert {c.metadata["chunk_id"] for c in raw} == set("ABC")
        retriever = KnowledgeSpaceRetriever(space_id=1, top_k=3, system_app=app)
        resolved = retriever._resolve_source_chunks(raw)
        assert {c.chunk_id for c in resolved} == set(vector_ids)
        for chunk in resolved:
            body = await kb_cat(name, "source.txt", chunk_id=chunk.chunk_id)
            assert "not found" not in body.lower(), body
            assert chunk.content in body
        sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid=name))
        with bind_artifact_sink(sink):
            result = await kb_semantic_search(name, "source", top_k=3)
        references = {a.artifact_id: a for a in sink.snapshot()}
        # DefaultRanker intentionally merges equal bodies. Both duplicate
        # backend rows above must resolve; every retained public reference must
        # also point to its correct persisted UUID.
        assert len(references) == (2 if duplicate else 3), result
        assert {a.source_id for a in references.values()} <= set(vector_ids), result
        for artifact_id, reference in references.items():
            assert reference.source_id in result
            body = await kb_cat(name, "source.txt", chunk_id=reference.source_id)
            assert "not found" not in body.lower(), body
            assert reference.excerpt in body
            assert not validate_knowledge_sources(
                f'<p data-dbgpt-artifacts="{artifact_id}">evidence</p>', references
            )
        print(
            json.dumps(
                {
                    "table": name,
                    "duplicate": duplicate,
                    "vector_ids": vector_ids,
                    "public_output": result,
                }
            )
        )
    finally:
        store.vector_store_client.drop_table_if_exist(name)
        store.vector_store_client.engine.dispose()
        executor.create().shutdown(wait=True)
        manager.engine.dispose()


def test_partial_vector_ids_are_not_assigned_to_neighbors():
    chunks = [Chunk(chunk_id=key, content="same") for key in "ABC"]
    assert chunk_vector_id_map(chunks, ["new-uuid"]) == {}
    assert chunk_vector_id_map(chunks, ["A", "C"]) == {"A": "A", "C": "C"}
