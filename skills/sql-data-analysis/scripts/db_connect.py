#!/usr/bin/env python3
"""
Database connection utility for SQL data analysis skill.
Supports multiple database types: PostgreSQL, MySQL, SQLite.
"""

import sys
import argparse
import json


def connect_postgresql(host, port, database, user, password):
    """Connect to PostgreSQL database."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        return {"status": "success", "type": "postgresql", "message": "Connected to PostgreSQL"}
    except ImportError:
        return {"status": "error", "message": "psycopg2 not installed. Run: pip install psycopg2-binary"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def connect_mysql(host, port, database, user, password):
    """Connect to MySQL database."""
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        return {"status": "success", "type": "mysql", "message": "Connected to MySQL"}
    except ImportError:
        return {"status": "error", "message": "mysql-connector-python not installed. Run: pip install mysql-connector-python"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def connect_sqlite(database_path):
    """Connect to SQLite database."""
    try:
        import sqlite3
        conn = sqlite3.connect(database_path)
        return {"status": "success", "type": "sqlite", "message": f"Connected to SQLite: {database_path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def main():
    parser = argparse.ArgumentParser(description='Connect to a database')
    parser.add_argument('--type', required=True, choices=['postgresql', 'mysql', 'sqlite'], help='Database type')
    parser.add_argument('--host', help='Database host')
    parser.add_argument('--port', type=int, help='Database port')
    parser.add_argument('--database', help='Database name')
    parser.add_argument('--user', help='Database user')
    parser.add_argument('--password', help='Database password')
    parser.add_argument('--path', help='SQLite database path')
    
    args = parser.parse_args()
    
    if args.type == 'postgresql':
        result = connect_postgresql(args.host, args.port, args.database, args.user, args.password)
    elif args.type == 'mysql':
        result = connect_mysql(args.host, args.port, args.database, args.user, args.password)
    elif args.type == 'sqlite':
        result = connect_sqlite(args.path)
    
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
