ARG BASE_IMAGE="nvidia/cuda:11.8.0-devel-ubuntu22.04"

FROM ${BASE_IMAGE}
ARG BASE_IMAGE

RUN apt-get update && apt-get install -y git python3 pip wget sqlite3 \
    && apt-get clean

ARG BUILD_LOCAL_CODE="false"
ARG LANGUAGE="en"
ARG PIP_INDEX_URL="https://pypi.org/simple"
ENV PIP_INDEX_URL=$PIP_INDEX_URL

# COPY only requirements.txt first to leverage Docker cache
COPY ./requirements.txt /tmp/requirements.txt

WORKDIR /app

RUN pip3 install --upgrade pip -i $PIP_INDEX_URL \
    && (if [ "${BUILD_LOCAL_CODE}" = "false" ]; \
        # if not build local code, clone latest code from git, and rename to /app, TODO: download by version, like: https://github.com/eosphoros-ai/DB-GPT/archive/refs/tags/$DBGPT_VERSION.zip
        then git clone https://github.com/eosphoros-ai/DB-GPT.git /app \
        && cp /app/requirements.txt /tmp/requirements.txt; \
    fi;) \
    && pip3 install -r /tmp/requirements.txt -i $PIP_INDEX_URL --no-cache-dir \
    && rm /tmp/requirements.txt

RUN (if [ "${LANGUAGE}" = "zh" ]; \
        # language is zh, download zh_core_web_sm from github
        then wget https://github.com/explosion/spacy-models/releases/download/zh_core_web_sm-3.5.0/zh_core_web_sm-3.5.0-py3-none-any.whl -O /tmp/zh_core_web_sm-3.5.0-py3-none-any.whl \
        && pip3 install /tmp/zh_core_web_sm-3.5.0-py3-none-any.whl -i $PIP_INDEX_URL \
        && rm /tmp/zh_core_web_sm-3.5.0-py3-none-any.whl; \
        # not zh, download directly
        else python3 -m spacy download zh_core_web_sm; \
    fi;) \
    && rm -rf `pip3 cache dir`

ARG BUILD_LOCAL_CODE="false"
# COPY the rest of the app
COPY . /tmp/app

# TODO：Need to find a better way to determine whether to build docker image with local code.
RUN (if [ "${BUILD_LOCAL_CODE}" = "true" ]; \
    then mv /tmp/app / && rm -rf /app/logs && rm -rf /app/pilot/data && rm -rf /app/pilot/message; \
    else rm -rf /tmp/app; \
    fi;)

ARG LOAD_EXAMPLES="true"

RUN (if [ "${LOAD_EXAMPLES}" = "true" ]; \
    then mkdir -p /app/pilot/data && sqlite3 /app/pilot/data/default_sqlite.db < /app/docker/examples/sqls/case_1_student_manager_sqlite.sql \
    && sqlite3 /app/pilot/data/default_sqlite.db < /app/docker/examples/sqls/case_2_ecom_sqlite.sql \
    && sqlite3 /app/pilot/data/default_sqlite.db < /app/docker/examples/sqls/test_case_info_sqlite.sql; \
    fi;)

EXPOSE 5000

CMD ["python3", "pilot/server/dbgpt_server.py"]