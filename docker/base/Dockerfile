ARG BASE_IMAGE="nvidia/cuda:11.8.0-runtime-ubuntu22.04"

FROM ${BASE_IMAGE}
ARG BASE_IMAGE

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y git python3 pip wget sqlite3 tzdata \
    && apt-get clean

ARG BUILD_LOCAL_CODE="false"
ARG LANGUAGE="en"
ARG PIP_INDEX_URL="https://pypi.org/simple"
ENV PIP_INDEX_URL=$PIP_INDEX_URL

ARG DB_GPT_INSTALL_MODEL="default"
ENV DB_GPT_INSTALL_MODEL=$DB_GPT_INSTALL_MODEL

RUN mkdir -p /app

# COPY only requirements.txt first to leverage Docker cache
COPY ./setup.py /app/setup.py
COPY ./README.md /app/README.md

WORKDIR /app

# ENV CMAKE_ARGS="-DLLAMA_CUBLAS=ON -DLLAMA_AVX2=OFF -DLLAMA_F16C=OFF -DLLAMA_FMA=OFF"
# ENV FORCE_CMAKE=1
# Install all
# RUN pip3 install -i $PIP_INDEX_URL ".[all]"

RUN pip3 install --upgrade pip -i $PIP_INDEX_URL \
    && pip3 install -i $PIP_INDEX_URL ".[$DB_GPT_INSTALL_MODEL]" \
    # install openai for proxyllm
    && pip3 install -i $PIP_INDEX_URL ".[openai]"

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
COPY . /app

ARG LOAD_EXAMPLES="true"

RUN (if [ "${LOAD_EXAMPLES}" = "true" ]; \
    then mkdir -p /app/pilot/data && sqlite3 /app/pilot/data/default_sqlite.db < /app/docker/examples/sqls/case_1_student_manager_sqlite.sql \
    && sqlite3 /app/pilot/data/default_sqlite.db < /app/docker/examples/sqls/case_2_ecom_sqlite.sql \
    && sqlite3 /app/pilot/data/default_sqlite.db < /app/docker/examples/sqls/test_case_info_sqlite.sql; \
    fi;)

RUN (if [ "${LANGUAGE}" = "zh" ]; \
    then ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone; \
    fi;)

ENV PYTHONPATH "/app:$PYTHONPATH"
EXPOSE 5000

CMD ["dbgpt", "start", "webserver"]