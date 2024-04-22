import pytest
from dbgpt.datasource.conn_tugraph import TuGraphConnector

# 设定数据库连接参数
HOST = 'localhost'
PORT = 7687
USER = 'admin'
PWD = '73@TuGraph'
DB_NAME = 'default'

@pytest.fixture(scope="session")
def connector():
    """Create a TuGraphConnector for the entire test session."""
    # 初始化连接
    connector = TuGraphConnector.from_uri_db(HOST, PORT, USER, PWD, DB_NAME)
    yield connector
    # 所有测试完成后关闭连接
    # connector.close()

def test_get_table_names(connector):
    """Test retrieving table names from the graph database."""
    table_names = connector.get_table_names()
    # 验证 vertex 和 edge 表是否存在
    assert 'vertex_tables' in table_names and 'edge_tables' in table_names
    # 验证 vertex 和 edge 表的数量
    assert len(table_names['vertex_tables']) == 5
    assert len(table_names['edge_tables']) == 8

def test_get_columns(connector):
    """Test retrieving columns for a specific table."""
    # 获取名为 'person' 的顶点表的列信息
    columns = connector.get_columns('person', 'vertex')
    # 验证列的数量
    assert len(columns) == 4
    # 验证是否存在名为 'id' 的列
    assert any(col['name'] == 'id' for col in columns)

def test_get_indexes(connector):
    """Test retrieving indexes for a specific table."""
    # 获取名为 'person' 的顶点表的索引信息
    indexes = connector.get_indexes('person', 'vertex')
    # 验证是否获取到了索引信息
    assert len(indexes) > 0

