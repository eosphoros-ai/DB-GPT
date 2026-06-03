#!/usr/bin/env python3
"""Сделать источник fmcg видимым для user_id 001 (как mock-пользователь в UI)."""
import os
import subprocess
import sys

MYSQL_ROOT = os.getenv("MYSQL_ROOT_PASSWORD", "aa123456")
SQL = (
    "USE dbgpt; "
    "UPDATE connect_config SET user_id='' WHERE db_name='fmcg'; "
    "SELECT id, db_name, user_id FROM connect_config;"
)

def main() -> None:
    cmd = [
        "docker",
        "exec",
        "dbgpt-mysql",
        "mysql",
        "-uroot",
        f"-p{MYSQL_ROOT}",
        "-e",
        SQL,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)
    print("fix_fmcg_user_id: OK")


if __name__ == "__main__":
    main()
