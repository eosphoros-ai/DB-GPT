ARG BASE_IMAGE="eosphorosai/dbgpt:latest"

FROM ${BASE_IMAGE}

RUN apt-get update && apt-get install -y wget gnupg lsb-release net-tools

RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 467B942D3A79BD29

RUN wget https://dev.mysql.com/get/mysql-apt-config_0.8.17-1_all.deb
RUN dpkg -i mysql-apt-config_0.8.17-1_all.deb

RUN apt-get update && apt-get install -y mysql-server && apt-get clean

# Remote access
RUN sed -i 's/bind-address\s*=\s*127.0.0.1/bind-address = 0.0.0.0/g' /etc/mysql/mysql.conf.d/mysqld.cnf \
    && echo "[mysqld]\ncharacter_set_server=utf8mb4\ncollation-server=utf8mb4_unicode_ci\ninit_connect='SET NAMES utf8mb4'\n[mysql]\ndefault-character-set=utf8mb4\n[client]\ndefault-character-set=utf8mb4\n" >> /etc/mysql/my.cnf

# Init sql
RUN mkdir /docker-entrypoint-initdb.d \
    && echo "USE mysql;\nUPDATE user SET Host='%' WHERE User='root';\nFLUSH PRIVILEGES;" > /docker-entrypoint-initdb.d/init.sql

ENV MYSQL_ROOT_PASSWORD=aa123456
ENV LOCAL_DB_PASSWORD="$MYSQL_ROOT_PASSWORD"

RUN cp /app/assets/schema/knowledge_management.sql /docker-entrypoint-initdb.d/

COPY docker/allinone/allinone-entrypoint.sh /usr/local/bin/allinone-entrypoint.sh
COPY docker/examples/sqls/*_mysql.sql /docker-entrypoint-initdb.d/

ENTRYPOINT ["/usr/local/bin/allinone-entrypoint.sh"]