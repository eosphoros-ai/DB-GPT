"""TuGraph Connector."""

import json
from typing import Dict, List, cast

from .base import BaseConnector


class TuGraphConnector(BaseConnector):
    """TuGraph connector."""

    db_type: str = "tugraph"
    driver: str = "bolt"
    dialect: str = "tugraph"

    def __init__(self, driver, graph):
        """Initialize the connector with a Neo4j driver."""
        self._driver = driver
        self._schema = None
        self._graph = graph
        self._session = None

    def create_graph(self, graph_name: str) -> None:
        """Create a new graph."""
        # run the query to get vertex labels
        with self._driver.session(database="default") as session:
            graph_list = session.run("CALL dbms.graph.listGraphs()").data()
            exists = any(item["graph_name"] == graph_name for item in graph_list)
            if not exists:
                session.run(f"CALL dbms.graph.createGraph('{graph_name}', '', 2048)")

    def delete_graph(self, graph_name: str) -> None:
        """Delete a graph."""
        with self._driver.session(database="default") as session:
            graph_list = session.run("CALL dbms.graph.listGraphs()").data()
            exists = any(item["graph_name"] == graph_name for item in graph_list)
            if exists:
                session.run(f"Call dbms.graph.deleteGraph('{graph_name}')")

    @classmethod
    def from_uri_db(
        cls, host: str, port: int, user: str, pwd: str, db_name: str
    ) -> "TuGraphConnector":
        """Create a new TuGraphConnector from host, port, user, pwd, db_name."""
        try:
            from neo4j import GraphDatabase

            db_url = f"{cls.driver}://{host}:{str(port)}"
            driver = GraphDatabase.driver(db_url, auth=(user, pwd))
            driver.verify_connectivity()
            return cast(TuGraphConnector, cls(driver=driver, graph=db_name))

        except ImportError as err:
            raise ImportError(
                "neo4j package is not installed, please install it with "
                "`pip install neo4j`"
            ) from err

    def get_table_names(self) -> Dict[str, List[str]]:
        """Get all table names from the TuGraph by Neo4j driver."""
        # run the query to get vertex labels
        with self._driver.session(database=self._graph) as session:
            v_result = session.run("CALL db.vertexLabels()").data()
            v_data = [table_name["label"] for table_name in v_result]

            # run the query to get edge labels
            e_result = session.run("CALL db.edgeLabels()").data()
            e_data = [table_name["label"] for table_name in e_result]
            return {"vertex_tables": v_data, "edge_tables": e_data}

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
        self._driver.close()

    def run(self, query: str, fetch: str = "all") -> List:
        """Run GQL."""
        with self._driver.session(database=self._graph) as session:
            result = session.run(query)
            return list(result)

    def get_columns(self, table_name: str, table_type: str = "vertex") -> List[Dict]:
        """Get fields about specified graph.

        Args:
            table_name (str): table name (graph name)
            table_type (str): table type (vertex or edge)
        Returns:
            columns: List[Dict], which contains name: str, type: str,
                default_expression: str, is_in_primary_key: bool, comment: str
                eg:[{'name': 'id', 'type': 'int', 'default_expression': '',
                'is_in_primary_key': True, 'comment': 'id'}, ...]
        """
        with self._driver.session(database=self._graph) as session:
            data = []
            result = None
            if table_type == "vertex":
                result = session.run(f"CALL db.getVertexSchema('{table_name}')").data()
            else:
                result = session.run(f"CALL db.getEdgeSchema('{table_name}')").data()
            schema_info = json.loads(result[0]["schema"])
            for prop in schema_info.get("properties", []):
                prop_dict = {
                    "name": prop["name"],
                    "type": prop["type"],
                    "default_expression": "",
                    "is_in_primary_key": bool(
                        "primary" in schema_info
                        and prop["name"] == schema_info["primary"]
                    ),
                    "comment": prop["name"],
                }
                data.append(prop_dict)
            return data

    def get_indexes(self, table_name: str, table_type: str = "vertex") -> List[Dict]:
        """Get table indexes about specified table.

        Args:
            table_name:(str) table name
            table_type:(str）'vertex' | 'edge'
        Returns:
            List[Dict]:eg:[{'name': 'idx_key', 'column_names': ['id']}]
        """
        # [{'name':'id','column_names':['id']}]
        with self._driver.session(database=self._graph) as session:
            result = session.run(
                f"CALL db.listLabelIndexes('{table_name}','{table_type}')"
            ).data()
            transformed_data = []
            for item in result:
                new_dict = {"name": item["field"], "column_names": [item["field"]]}
                transformed_data.append(new_dict)
            return transformed_data

    @classmethod
    def is_graph_type(cls) -> bool:
        """Return whether the connector is a graph database connector."""
        return True
