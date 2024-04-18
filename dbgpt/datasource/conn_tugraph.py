from typing import Any, Optional, cast,List,Dict
from urllib.parse import quote, quote_plus as urlquote
from neo4j import GraphDatabase
from .base import BaseConnector

class TuGraphConnector(BaseConnector):
    """TuGraph connector."""

    db_type: str = "tugraph"
    driver: str = "bolt"
    dialect: str = "tugraph"
    def __init__(self, session):
        """Initialize the connector with a Neo4j driver."""
        self._session = session
    @classmethod
    def from_uri_db(cls, host: str, port: int, user: str, pwd: str, db_name: str, **kwargs: Any) -> "TuGraphConnector":
        """Create a new TuGraphConnector from host, port, user, pwd, db_name."""
        db_url = f"{cls.driver}://{host}:{str(port)}"
        client = GraphDatabase.driver(db_url, auth=(user, pwd))
        client.verify_connectivity()
        session = client.session(database=db_name)
        return cast(TuGraphConnector,cls(session=session))

    def get_table_names(self):
        """Get users from the TuGraph database using the Neo4j driver."""
        """Get all table names from the TuGraph database using the Neo4j driver."""
        # Run the query to get vertex labels
        v_result = self._session.run("CALL db.vertexLabels()")
        v_data = [tabel_name['label'] for tabel_name in v_result]
        
        # Run the query to get edge labels
        e_result = self._session.run("CALL db.edgeLabels()")
        e_data = [tabel_name['label'] for tabel_name in e_result]
        return {'vertex_tables':v_data,'edge_tables':e_data}

    def get_grants(self):
        """Get grants."""
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        """Get character_set of current database."""
        return "UTF-8"

    def table_simple_info(self):
        """Get table simple info."""
        return []

    def close(self):
        """Close the Neo4j driver."""
        self.driver.close()
    def run(self):
        return []
    def get_columns(self, table_name: str) -> List[Dict]:
        """Get fileds about specified graph.
        Args:
            table_name (str): table name (graph name)

        Returns:
            columns: List[Dict], which contains name: str, type: str,
                default_expression: str, is_in_primary_key: bool, comment: str
                eg:[{'name': 'id', 'type': 'int', 'default_expression': '',
                'is_in_primary_key': True, 'comment': 'id'}, ...]
        """
        print(f"CALL db.getVertexSchema('{table_name}')")
        # data = [{'name':'id','type':str,'is_in_primary_key':True,'default_expression':''}]
        # result = self._session.run(f"CALL db.getVertexSchema('{table_name}')")
        return []
    
    def get_indexes(self, table_name: str) -> List[Dict]:
        """Get table indexes about specified table.

        Args:
            table_name:(str) table name

        Returns:
            List[Dict]:eg:[{'name': 'idx_key', 'column_names': ['id']}]
        """
        # {'name':'id','column_names':['id']}
        return []
