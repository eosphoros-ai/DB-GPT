#!/usr/bin/env python3
"""
Execute SQL queries on connected databases.
Supports SELECT, INSERT, UPDATE, DELETE operations.
"""

import sys
import argparse
import json


def execute_query(db_type, query, **db_params):
    """Execute a SQL query on the specified database."""
    try:
        if db_type == 'postgresql':
            import psycopg2
            conn = psycopg2.connect(
                host=db_params.get('host'),
                port=db_params.get('port'),
                database=db_params.get('database'),
                user=db_params.get('user'),
                password=db_params.get('password')
            )
        elif db_type == 'mysql':
            import mysql.connector
            conn = mysql.connector.connect(
                host=db_params.get('host'),
                port=db_params.get('port'),
                database=db_params.get('database'),
                user=db_params.get('user'),
                password=db_params.get('password')
            )
        elif db_type == 'sqlite':
            import sqlite3
            conn = sqlite3.connect(db_params.get('path'))
        else:
            return {"status": "error", "message": f"Unsupported database type: {db_type}"}
        
        cursor = conn.cursor()
        cursor.execute(query)
        
        # Check if query returns results
        if query.strip().upper().startswith('SELECT'):
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]
            conn.close()
            return {
                "status": "success",
                "type": "select",
                "columns": columns,
                "row_count": len(results),
                "data": results
            }
        else:
            conn.commit()
            affected_rows = cursor.rowcount
            conn.close()
            return {
                "status": "success",
                "type": "mutation",
                "affected_rows": affected_rows,
                "message": f"Query executed successfully. {affected_rows} rows affected."
            }
    except ImportError as e:
        return {"status": "error", "message": f"Missing dependency: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def main():
    parser = argparse.ArgumentParser(description='Execute SQL query')
    parser.add_argument('--type', required=True, choices=['postgresql', 'mysql', 'sqlite'], help='Database type')
    parser.add_argument('--query', required=True, help='SQL query to execute')
    parser.add_argument('--host', help='Database host')
    parser.add_argument('--port', type=int, help='Database port')
    parser.add_argument('--database', help='Database name')
    parser.add_argument('--user', help='Database user')
    parser.add_argument('--password', help='Database password')
    parser.add_argument('--path', help='SQLite database path')
    
    args = parser.parse_args()
    
    db_params = {
        'host': args.host,
        'port': args.port,
        'database': args.database,
        'user': args.user,
        'password': args.password,
        'path': args.path
    }
    
    result = execute_query(args.type, args.query, **db_params)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
