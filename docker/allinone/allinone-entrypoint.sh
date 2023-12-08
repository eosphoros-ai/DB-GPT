#!/bin/bash

service mysql start

# execute all mysql init script
for file in /docker-entrypoint-initdb.d/*.sql
do
    echo "execute sql file: $file"
    mysql -u root -p${MYSQL_ROOT_PASSWORD} < "$file"
done

mysql -u root -p${MYSQL_ROOT_PASSWORD} -e "
ALTER USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY '$MYSQL_ROOT_PASSWORD';
FLUSH PRIVILEGES;
"

python3 dbgpt/app/dbgpt_server.py