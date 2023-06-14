Connections
---------
**In order to interact more conveniently with users' private environments, the project has designed a connection module, which can support connection to databases, Excel, knowledge bases, and other environments to achieve information and data exchange.**

DB-GPT provides base class BaseConnect, you can inheriting and implement get_session(), get_table_names(), get_index_info(), get_database_list() and run().

- `mysql_connection <./connections/mysql_connection.html>`_: supported mysql_connection.


.. toctree::
   :maxdepth: 2
   :caption: Connections
   :name: mysql_connection
   :hidden:

   ./connections/mysql/mysql_connection.md