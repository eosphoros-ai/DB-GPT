"""Code graph persistence models.

Three tables:
  - code_graph_vertex: AST-extracted code nodes (classes, functions, modules, etc.)
  - code_graph_edge: Structural relationships (contains, calls, imports, etc.)
  - code_graph_meta: Per-knowledge-space graph metadata (counts, build info)
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from dbgpt.storage.metadata import BaseDao, Model

logger = logging.getLogger(__name__)


# Props that are extracted to dedicated columns (not stored in JSON props)
_VERTEX_PROPS_COLUMNS = {"node_type", "source_file", "language", "community"}


# ---------------------------------------------------------------------------
# Vertex
# ---------------------------------------------------------------------------


class CodeGraphVertexEntity(Model):
    """Code graph vertex (node) entity."""

    __tablename__ = "code_graph_vertex"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_id = Column(String(100), nullable=False)
    vid = Column(String(500), nullable=False)
    name = Column(String(500), nullable=False)
    node_type = Column(String(50), nullable=False, default="")
    source_file = Column(String(500), default="")
    language = Column(String(30), default="")
    community = Column(String(50), default="")
    props = Column(Text, default=None)
    gmt_create = Column(DateTime, default=datetime.now)
    gmt_modified = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return (
            f"CodeGraphVertexEntity(id={self.id}, vid='{self.vid}', "
            f"name='{self.name}', node_type='{self.node_type}')"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "knowledge_id": self.knowledge_id,
            "vid": self.vid,
            "name": self.name,
            "node_type": self.node_type,
            "source_file": self.source_file,
            "language": self.language,
            "community": self.community,
            "props": self.props,
        }


class CodeGraphVertexDao(BaseDao):
    """DAO for code_graph_vertex table."""

    def batch_insert(self, knowledge_id: str, vertices: list) -> int:
        """Bulk insert vertices for a knowledge space."""
        if not vertices:
            return 0
        session = self.get_raw_session()
        try:
            current_time = datetime.now()
            batch_size = 200
            for i in range(0, len(vertices), batch_size):
                batch = vertices[i : i + batch_size]
                mappings = [
                    {
                        "knowledge_id": knowledge_id,
                        "vid": v["vid"],
                        "name": v["name"],
                        "node_type": v.get("node_type", ""),
                        "source_file": v.get("source_file", ""),
                        "language": v.get("language", ""),
                        "community": v.get("community", ""),
                        "props": v.get("props"),
                        "gmt_create": current_time,
                        "gmt_modified": current_time,
                    }
                    for v in batch
                ]
                session.bulk_insert_mappings(CodeGraphVertexEntity, mappings)
            session.commit()
            return len(vertices)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_by_knowledge_id(self, knowledge_id: str) -> List[CodeGraphVertexEntity]:
        """Get all vertices for a knowledge space."""
        session = self.get_raw_session()
        try:
            return (
                session.query(CodeGraphVertexEntity)
                .filter(CodeGraphVertexEntity.knowledge_id == knowledge_id)
                .all()
            )
        finally:
            session.close()

    def search_by_name(
        self,
        knowledge_id: str,
        name_prefix: str,
        node_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[CodeGraphVertexEntity]:
        """Search vertices by name prefix (uses index)."""
        session = self.get_raw_session()
        try:
            query = session.query(CodeGraphVertexEntity).filter(
                CodeGraphVertexEntity.knowledge_id == knowledge_id,
                CodeGraphVertexEntity.name.like(f"{name_prefix}%"),
            )
            if node_type:
                query = query.filter(CodeGraphVertexEntity.node_type == node_type)
            return query.limit(limit).all()
        finally:
            session.close()

    def get_by_source_file(
        self, knowledge_id: str, source_file: str
    ) -> List[CodeGraphVertexEntity]:
        """Get all vertices in a specific source file."""
        session = self.get_raw_session()
        try:
            return (
                session.query(CodeGraphVertexEntity)
                .filter(
                    CodeGraphVertexEntity.knowledge_id == knowledge_id,
                    CodeGraphVertexEntity.source_file == source_file,
                )
                .all()
            )
        finally:
            session.close()

    def get_by_vid(
        self, knowledge_id: str, vid: str
    ) -> Optional[CodeGraphVertexEntity]:
        """Get a single vertex by its vid."""
        session = self.get_raw_session()
        try:
            return (
                session.query(CodeGraphVertexEntity)
                .filter(
                    CodeGraphVertexEntity.knowledge_id == knowledge_id,
                    CodeGraphVertexEntity.vid == vid,
                )
                .first()
            )
        finally:
            session.close()

    def delete_by_knowledge_id(self, knowledge_id: str) -> int:
        """Delete all vertices for a knowledge space. Returns count deleted."""
        session = self.get_raw_session()
        try:
            count = (
                session.query(CodeGraphVertexEntity)
                .filter(CodeGraphVertexEntity.knowledge_id == knowledge_id)
                .delete()
            )
            session.commit()
            return count
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def count_by_knowledge_id(self, knowledge_id: str) -> int:
        """Count vertices for a knowledge space."""
        session = self.get_raw_session()
        try:
            result = (
                session.query(func.count(CodeGraphVertexEntity.id))
                .filter(CodeGraphVertexEntity.knowledge_id == knowledge_id)
                .scalar()
            )
            return result or 0
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------


class CodeGraphEdgeEntity(Model):
    """Code graph edge (relationship) entity."""

    __tablename__ = "code_graph_edge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_id = Column(String(100), nullable=False)
    sid = Column(String(500), nullable=False)
    tid = Column(String(500), nullable=False)
    edge_type = Column(String(50), nullable=False, default="references")
    confidence = Column(String(20), default="EXTRACTED")
    source_file = Column(String(500), default="")
    source_location = Column(String(30), default="")
    props = Column(Text, default=None)
    gmt_create = Column(DateTime, default=datetime.now)
    gmt_modified = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return (
            f"CodeGraphEdgeEntity(id={self.id}, sid='{self.sid}', "
            f"tid='{self.tid}', edge_type='{self.edge_type}')"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "knowledge_id": self.knowledge_id,
            "sid": self.sid,
            "tid": self.tid,
            "edge_type": self.edge_type,
            "confidence": self.confidence,
            "source_file": self.source_file,
            "source_location": self.source_location,
            "props": self.props,
        }


class CodeGraphEdgeDao(BaseDao):
    """DAO for code_graph_edge table."""

    def batch_insert(self, knowledge_id: str, edges: list) -> int:
        """Bulk insert edges for a knowledge space."""
        if not edges:
            return 0
        session = self.get_raw_session()
        try:
            current_time = datetime.now()
            batch_size = 200
            for i in range(0, len(edges), batch_size):
                batch = edges[i : i + batch_size]
                mappings = [
                    {
                        "knowledge_id": knowledge_id,
                        "sid": e["sid"],
                        "tid": e["tid"],
                        "edge_type": e["edge_type"],
                        "confidence": e.get("confidence", "EXTRACTED"),
                        "source_file": e.get("source_file", ""),
                        "source_location": e.get("source_location", ""),
                        "props": e.get("props"),
                        "gmt_create": current_time,
                        "gmt_modified": current_time,
                    }
                    for e in batch
                ]
                session.bulk_insert_mappings(CodeGraphEdgeEntity, mappings)
            session.commit()
            return len(edges)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_by_knowledge_id(self, knowledge_id: str) -> List[CodeGraphEdgeEntity]:
        """Get all edges for a knowledge space."""
        session = self.get_raw_session()
        try:
            return (
                session.query(CodeGraphEdgeEntity)
                .filter(CodeGraphEdgeEntity.knowledge_id == knowledge_id)
                .all()
            )
        finally:
            session.close()

    def get_out_edges(
        self, knowledge_id: str, sid: str, edge_type: Optional[str] = None
    ) -> List[CodeGraphEdgeEntity]:
        """Get outgoing edges from a vertex (sid matches)."""
        session = self.get_raw_session()
        try:
            query = session.query(CodeGraphEdgeEntity).filter(
                CodeGraphEdgeEntity.knowledge_id == knowledge_id,
                CodeGraphEdgeEntity.sid == sid,
            )
            if edge_type:
                query = query.filter(CodeGraphEdgeEntity.edge_type == edge_type)
            return query.all()
        finally:
            session.close()

    def get_in_edges(
        self, knowledge_id: str, tid: str, edge_type: Optional[str] = None
    ) -> List[CodeGraphEdgeEntity]:
        """Get incoming edges to a vertex (tid matches)."""
        session = self.get_raw_session()
        try:
            query = session.query(CodeGraphEdgeEntity).filter(
                CodeGraphEdgeEntity.knowledge_id == knowledge_id,
                CodeGraphEdgeEntity.tid == tid,
            )
            if edge_type:
                query = query.filter(CodeGraphEdgeEntity.edge_type == edge_type)
            return query.all()
        finally:
            session.close()

    def delete_by_knowledge_id(self, knowledge_id: str) -> int:
        """Delete all edges for a knowledge space. Returns count deleted."""
        session = self.get_raw_session()
        try:
            count = (
                session.query(CodeGraphEdgeEntity)
                .filter(CodeGraphEdgeEntity.knowledge_id == knowledge_id)
                .delete()
            )
            session.commit()
            return count
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def count_by_knowledge_id(self, knowledge_id: str) -> int:
        """Count edges for a knowledge space."""
        session = self.get_raw_session()
        try:
            result = (
                session.query(func.count(CodeGraphEdgeEntity.id))
                .filter(CodeGraphEdgeEntity.knowledge_id == knowledge_id)
                .scalar()
            )
            return result or 0
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


class CodeGraphMetaEntity(Model):
    """Code graph metadata entity — one row per knowledge space."""

    __tablename__ = "code_graph_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_id = Column(String(100), nullable=False, unique=True)
    vertex_count = Column(Integer, default=0)
    edge_count = Column(Integer, default=0)
    community_count = Column(Integer, default=0)
    build_source = Column(String(20), default="")
    repo_url = Column(String(500), default="")
    branch = Column(String(100), default="")
    build_status = Column(String(20), default="completed")
    graph_version = Column(Integer, default=1)
    gmt_create = Column(DateTime, default=datetime.now)
    gmt_modified = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return (
            f"CodeGraphMetaEntity(id={self.id}, knowledge_id='{self.knowledge_id}', "
            f"vertices={self.vertex_count}, edges={self.edge_count})"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "knowledge_id": self.knowledge_id,
            "vertex_count": self.vertex_count,
            "edge_count": self.edge_count,
            "community_count": self.community_count,
            "build_source": self.build_source,
            "repo_url": self.repo_url,
            "branch": self.branch,
            "build_status": self.build_status,
            "graph_version": self.graph_version,
            "gmt_create": self.gmt_create.isoformat() if self.gmt_create else None,
            "gmt_modified": (
                self.gmt_modified.isoformat() if self.gmt_modified else None
            ),
        }


class CodeGraphMetaDao(BaseDao):
    """DAO for code_graph_meta table."""

    def get_by_knowledge_id(self, knowledge_id: str) -> Optional[CodeGraphMetaEntity]:
        """Get meta for a knowledge space."""
        session = self.get_raw_session()
        try:
            return (
                session.query(CodeGraphMetaEntity)
                .filter(CodeGraphMetaEntity.knowledge_id == knowledge_id)
                .first()
            )
        finally:
            session.close()

    def upsert(self, meta: CodeGraphMetaEntity) -> int:
        """Insert or update meta for a knowledge space.

        Returns the row ID.
        """
        session = self.get_raw_session()
        try:
            existing = (
                session.query(CodeGraphMetaEntity)
                .filter(CodeGraphMetaEntity.knowledge_id == meta.knowledge_id)
                .first()
            )
            if existing:
                existing.vertex_count = meta.vertex_count
                existing.edge_count = meta.edge_count
                existing.community_count = meta.community_count
                existing.build_source = meta.build_source
                existing.repo_url = meta.repo_url
                existing.branch = meta.branch
                existing.build_status = meta.build_status
                existing.graph_version = meta.graph_version
                existing.gmt_modified = datetime.now()
                session.commit()
                return existing.id
            else:
                meta.gmt_create = datetime.now()
                meta.gmt_modified = datetime.now()
                session.add(meta)
                session.commit()
                return meta.id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_by_knowledge_id(self, knowledge_id: str) -> bool:
        """Delete meta for a knowledge space."""
        session = self.get_raw_session()
        try:
            count = (
                session.query(CodeGraphMetaEntity)
                .filter(CodeGraphMetaEntity.knowledge_id == knowledge_id)
                .delete()
            )
            session.commit()
            return count > 0
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
