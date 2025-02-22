"""TuGraph Connector."""

import json
from dataclasses import dataclass, field
from typing import Dict, Generator, Iterator, List, Type, cast

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.base import BaseConnector
from dbgpt.datasource.parameter import BaseDatasourceParameters
from dbgpt.util.i18n_utils import _


@auto_register_resource(
    label=_("TuGraph datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_(
        "TuGraph is a high-performance graph database jointly developed by Ant Group "
        "and Tsinghua University."
    ),
)
@dataclass
class TuGraphParameters(BaseDatasourceParameters):
    """TuGraph connection parameters."""

    __type__ = "tugraph"

    host: str = field(metadata={"help": _("TuGraph server host")})
    user: str = field(metadata={"help": _("TuGraph server user")})
    password: str = field(
        default="${env:DBGPT_DB_PASSWORD}",
        metadata={
            "help": _(
                "Database password, you can write your password directly, of course, "
                "you can also use environment variables, such as "
                "${env:DBGPT_DB_PASSWORD}"
            ),
            "tags": "privacy",
        },
    )
    port: int = field(
        default=7687, metadata={"help": _("TuGraph server port, default 7687")}
    )
    database: str = field(
        default="default", metadata={"help": _("Database name, default 'default'")}
    )

    def create_connector(self) -> "BaseConnector":
        """Create TuGraph connector."""
        return TuGraphConnector.from_parameters(self)

    def db_url(self, ssl=False, charset=None):
        """Get the database URL."""
        raise NotImplementedError("TuGraph does not support db_url")


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
        self._is_closed = False

    def create_graph(self, graph_name: str) -> bool:
        """Create a new graph in the database if it doesn't already exist."""
        try:
            with self._driver.session(database="default") as session:
                graph_list = session.run("CALL dbms.graph.listGraphs()").data()
                exists = any(item["graph_name"] == graph_name for item in graph_list)
                if not exists:
                    session.run(
                        f"CALL dbms.graph.createGraph('{graph_name}', '', 2048)"
                    )
        except Exception as e:
            raise Exception(f"Failed to create graph '{graph_name}': {str(e)}") from e

        return not exists

    def is_exist(self, graph_name: str) -> bool:
        """Check a new graph in the database if it doesn't already exist."""
        try:
            with self._driver.session(database="default") as session:
                graph_list = session.run("CALL dbms.graph.listGraphs()").data()
                exists = any(item["graph_name"] == graph_name for item in graph_list)
        except Exception as e:
            raise Exception(
                f"Failed to check graph exist'{graph_name}': {str(e)}"
            ) from e

        return exists

    def delete_graph(self, graph_name: str) -> None:
        """Delete a graph in the database if it exists."""
        with self._driver.session(database="default") as session:
            graph_list = session.run("CALL dbms.graph.listGraphs()").data()
            exists = any(item["graph_name"] == graph_name for item in graph_list)
            if exists:
                session.run(f"Call dbms.graph.deleteGraph('{graph_name}')")

    @classmethod
    def param_class(cls) -> Type[TuGraphParameters]:
        """Return the parameter class."""
        return TuGraphParameters

    @classmethod
    def from_parameters(cls, parameters: TuGraphParameters) -> "TuGraphConnector":
        """Create a new TuGraphConnector from parameters."""
        return cls.from_uri_db(
            parameters.host,
            parameters.port,
            parameters.user,
            parameters.password,
            parameters.database,
        )

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

    def get_system_info(self) -> Dict:
        """Get system info from the TuGraph."""
        with self._driver.session(database="default") as session:
            system_info_list = session.run("CALL dbms.system.info()")
            system_info = {}
            for info in system_info_list:
                system_info[info["name"]] = info["value"]
            return system_info

    def get_table_names(self) -> Iterator[str]:
        """Get all table names from the TuGraph by Neo4j driver."""
        with self._driver.session(database=self._graph) as session:
            # Run the query to get vertex labels
            raw_vertex_labels = session.run("CALL db.vertexLabels()").data()
            vertex_labels = [table_name["label"] for table_name in raw_vertex_labels]

            # Run the query to get edge labels
            raw_edge_labels = session.run("CALL db.edgeLabels()").data()
            edge_labels = [table_name["label"] for table_name in raw_edge_labels]

            return iter(vertex_labels + edge_labels)

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
        if self._is_closed:
            return
        self._driver.close()
        self._is_closed = True

    def run(self, query: str, fetch: str = "all") -> List:
        """Run query."""
        with self._driver.session(database=self._graph) as session:
            try:
                result = session.run(query)
                return list(result)
            except Exception as e:
                raise Exception(f"Query execution failed: {e}\nQuery: {query}") from e

    def run_stream(self, query: str) -> Generator:
        """Run GQL."""
        with self._driver.session(database=self._graph) as session:
            result = session.run(query)
            yield from result

    def get_columns(self, table_name: str, table_type: str = "vertex") -> List[Dict]:
        """Retrieve the column for a specified vertex or edge table in the graph db.

        This function queries the schema of a given table (vertex or edge) and returns
        detailed information about its columns (properties).

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
            table_name (str): table name
            table_type (str): 'vertex' | 'edge'
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
