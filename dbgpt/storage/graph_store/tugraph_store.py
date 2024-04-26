"""TuGraph vector store."""
import logging
from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.datasource.conn_tugraph import TuGraphConnector
from typing import Any,Optional
logger = logging.getLogger(__name__)



class TuGraphStore(GraphStoreBase):
    """TuGraph vector store."""

    def __init__(self, host: str, port: int, user: str, pwd: str, db_name: str, node_label: str = 'entity', edge_label: str = 'rel', **kwargs: Any) -> None:
        """Initialize the TuGraphStore with connection details."""
        self.conn = TuGraphConnector.from_uri_db(host=host, port=port, user=user, pwd=pwd, db_name=db_name)
        self._node_label = node_label
        self._edge_label = edge_label
        self._create_schema()

    def _create_schema(self):
        create_vertex_gql = f"CALL db.createLabel('vertex', '{self._node_label}', 'id', ['id',string,false])"
        create_edge_gql = f"CALL db.createLabel('edge', '{self._edge_label}', '[[\"{self._node_label}\",\"{self._node_label}\"]]', ['id',string,false]);"
        self.conn.run(create_vertex_gql)
        self.conn.run(create_edge_gql)

    
        

