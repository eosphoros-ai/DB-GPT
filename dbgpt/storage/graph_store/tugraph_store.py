"""TuGraph vector store."""
import logging
from typing import Any, List, Tuple

from dbgpt.datasource.conn_tugraph import TuGraphConnector
from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.graph import Direction, MemoryGraph

logger = logging.getLogger(__name__)


class TuGraphStore(GraphStoreBase):
    """TuGraph graph store."""

    def __init__(self, host: str, port: int, user: str, pwd: str, db_name: str, node_label: str = 'entity', edge_label: str = 'rel', **kwargs: Any) -> None:
        """Initialize the TuGraphStore with connection details."""
        self.conn = TuGraphConnector.from_uri_db(host=host, port=port, user=user, pwd=pwd, db_name=db_name)
        self._node_label = node_label
        self._edge_label = edge_label
        self._create_schema()

    def _check_label(self,type:str):
        result = self.conn.get_table_names()
        if type == 'vertex':
            return self._node_label in result['vertex_tables']

        if type == 'edge':
            return self._edge_label in result['edge_tables']

    def _create_schema(self):
        if not self._check_label('vertex'):
            create_vertex_gql = f"CALL db.createLabel('vertex', '{self._node_label}', 'id', ['id',string,false])"
            self.conn.run(create_vertex_gql)
        if not self._check_label('edge'):
            create_edge_gql = f'''CALL db.createLabel('edge', '{self._edge_label}', '[["{self._node_label}","{self._node_label}"]]',["id",STRING,false])'''
            self.conn.run(create_edge_gql)

    def insert_triplet(self, subj: str, rel: str, obj: str) -> None:
        subj_query = f'''MERGE (n1:{self._node_label} {{id:'{subj}'}})'''
        obj_query = f"MERGE (n1:{self._node_label} {{id:'{obj}'}})"
        rel_query = f"MERGE (n1:{self._node_label} {{id:'{subj}'}})-[r:{self._edge_label} {{id:'{rel}'}}]->(n2:{self._node_label} {{id:'{obj}'}})"
        self.conn.run(query=subj_query)
        self.conn.run(query=obj_query)
        self.conn.run(query=rel_query)

    def get_triplets(self, sub: str) -> List[Tuple[str, str]]:
        query = f"""
            MATCH (n1:{self._node_label})-[r]->(n2:{self._node_label}) WHERE n1.id = "{sub}" RETURN r.id as rel, n2.id as obj;
        """
        data = self.conn.run(query)
        result = [(item['rel'],item['obj']) for item in data]
        return result

    def delete_triplet(self, sub: str, rel: str, obj: str):
        del_subj_query = f"MATCH (n:{self._node_label}) WHERE n.id = '{sub}' DELETE n"
        del_obj_query = f"MATCH (n:{self._node_label}) WHERE n.id = '{obj}' DELETE n"
        self.conn.run(query=del_subj_query)
        self.conn.run(query=del_obj_query)

    def get_schema(self, refresh: bool = False) -> str:
        # todo: get schema on tugraph
        query = "CALL dbms.graph.getGraphSchema()"
        data = self.conn.run(query=query)
        return data[0]["schema"]

    def explore(
        self,
        subs: List[str],
        direction: Direction = Direction.BOTH,
        depth_limit: int = None,
        fan_limit: int = None,
        result_limit: int = None
    ) -> MemoryGraph:
        # todo: bfs on tugraph
        query = f'''MATCH p=(n:{self._node_label})-[r:{self._edge_label}]->() WHERE n.id IN {subs} RETURN p,r.id as rel LIMIT {result_limit}'''
        self.conn.run(query=query)
        return MemoryGraph()

    def query(self, query: str, **args) -> MemoryGraph:
        self.conn.run(query=query)
        # todo: construct MemoryGraph
        return MemoryGraph()



