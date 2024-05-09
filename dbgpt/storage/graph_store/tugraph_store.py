"""TuGraph vector store."""
import logging
from typing import Any, List, Tuple,Optional,Dict

from dbgpt.datasource.conn_tugraph import TuGraphConnector
from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.graph import Direction, MemoryGraph

logger = logging.getLogger(__name__)

def format_paths(paths):
    formatted_paths = []
    for path in paths:
        formatted_path = []
        nodes = list(path.nodes)
        for i in range(len(nodes)):
            formatted_path.append(nodes[i]._properties['id'])
            if i < len(path.relationships):
                formatted_path.append(path.relationships[i]._properties['id'])
            formatted_paths.append(formatted_path)
    return formatted_paths        

def remove_duplicates(lst):
    seen = set()
    result = []
    for sub_lst in lst:
        sub_tuple = tuple(sub_lst)
        if sub_tuple not in seen:
            result.append(sub_lst)
            seen.add(sub_tuple)
    return result

class TuGraphStore(GraphStoreBase):
    """TuGraph vector store."""

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
        

    def get_triplets(self, subj: str) -> List[List[str]]:
        """Get triplets."""
        query = f"""MATCH (n1:{self._node_label})-[r]->(n2:{self._node_label}) WHERE n1.id = "{subj}" RETURN r.id as rel, n2.id as obj;"""
        data = self.conn.run(query)
        result = [[item['rel'],item['obj']] for item in data.data()]
        return result
       

    def insert_triplet(self, subj: str, rel: str, obj: str) -> None:
        """Add triplet."""
        subj_query = f'''MERGE (n1:{self._node_label} {{id:'{subj}'}})'''
        obj_query = f"MERGE (n1:{self._node_label} {{id:'{obj}'}})"
        rel_query = f"MERGE (n1:{self._node_label} {{id:'{subj}'}})-[r:{self._edge_label} {{id:'{rel}'}}]->(n2:{self._node_label} {{id:'{obj}'}})"
        self.conn.run(query=subj_query)
        self.conn.run(query=obj_query)
        self.conn.run(query=rel_query)

    def get_rel_map(
        self, subjs: Optional[List[str]] = None, depth: int = 2, limit: int = 30
    ) -> List[List[str]]:
        """Get flat rel map."""
        # *1..{depth}
        query = f'''MATCH p=(n:{self._node_label})-[r:{self._edge_label}*1..{depth}]->() WHERE n.id IN {subjs} RETURN p LIMIT {limit}'''
        data = self.conn.run(query=query)
        result = []
        formatted_paths = format_paths(data.value())
        for path in formatted_paths:
            result.append(path)
        result = remove_duplicates(result)
        return result
        

    def delete_triplets(self, subj: str, obj: str) -> None:
        """Delete triplet."""
        del_subj_query = f"MATCH (n:{self._node_label}) WHERE n.id = '{subj}' DELETE n"
        del_obj_query = f"MATCH (n:{self._node_label}) WHERE n.id = '{obj}' DELETE n"
        self.conn.run(query=del_subj_query)
        self.conn.close_session()
        self.conn.run(query=del_obj_query)
        self.conn.close_session()

    def get_schema(self, refresh: bool = False) -> str:
        """Get the schema of the graph store."""
        query = "CALL dbms.graph.getGraphSchema()"
        data = self.conn.run(query=query)
        return data.data()[0]["schema"]

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



