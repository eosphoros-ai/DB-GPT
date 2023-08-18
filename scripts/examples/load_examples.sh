#!/bin/bash
# Only support SQLite now

SCRIPT_LOCATION=$0
cd "$(dirname "$SCRIPT_LOCATION")"
WORK_DIR=$(pwd)
WORK_DIR="$WORK_DIR/../.."

if ! command -v sqlite3 > /dev/null 2>&1
then
  echo "sqlite3 not found, please install sqlite3"
  exit 1
fi

DEFAULT_DB_FILE="DB-GPT/pilot/data/default_sqlite.db"
DEFAULT_SQL_FILE="DB-GPT/docker/examples/sqls/*_sqlite.sql"
DB_FILE="$WORK_DIR/pilot/data/default_sqlite.db"
SQL_FILE=""

usage () {
    echo "USAGE: $0 [--db-file sqlite db file] [--sql-file sql file path to run]"
    echo "  [-d|--db-file sqlite db file path] default: ${DEFAULT_DB_FILE}"
    echo "  [-f|--sql-file sqlte file to run] default: ${DEFAULT_SQL_FILE}"
    echo "  [-h|--help] Usage message"
}

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -d|--db-file)
        DB_FILE="$2"
        shift # past argument
        shift # past value
        ;;
        -f|--sql-file)
        SQL_FILE="$2"
        shift
        shift
        ;;
        -h|--help)
        help="true"
        shift
        ;;
        *)
        usage
        exit 1
        ;;
    esac
done

if [[ $help ]]; then
    usage
    exit 0
fi

if [ -n $SQL_FILE ];then
    mkdir -p $WORK_DIR/pilot/data
    for file in $WORK_DIR/docker/examples/sqls/*_sqlite.sql
    do
        echo "execute sql file: $file"
        sqlite3 $DB_FILE  < "$file"
    done

else
    echo "Execute SQL file ${SQL_FILE}"
    sqlite3 $DB_FILE < $SQL_FILE
fi


