#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pymysql

class MySQLOperator:
    """Connect MySQL Database fetch MetaData For LLM Prompt 
        Args:

        Usage:
    """

    default_db = ["information_schema", "performance_schema", "sys", "mysql"]
    def __init__(self, user, password, host="localhost", port=3306) -> None:
        
        self.conn = pymysql.connect(
            host=host,
            user=user,
            port=port,
            passwd=password,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )

    def get_schema(self, schema_name):
        
        with self.conn.cursor() as cursor:
            _sql = f"""
                select concat(table_name, "(" , group_concat(column_name), ")") as schema_info from information_schema.COLUMNS where table_schema="{schema_name}" group by TABLE_NAME;
            """
            cursor.execute(_sql)
            results = cursor.fetchall()
            return results
    
    def get_index(self, schema_name):
        pass

    def get_db_list(self):
        with self.conn.cursor() as cursor:
            _sql = """ 
                show databases;
            """
            cursor.execute(_sql)
            results = cursor.fetchall()

            dbs = [d["Database"] for d in results if d["Database"] not in self.default_db]
            return dbs

    def get_meta(self, schema_name):
        pass


