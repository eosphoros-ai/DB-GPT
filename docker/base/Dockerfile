FROM nvidia/cuda:11.8.0-devel-ubuntu22.04

RUN apt-get update && apt-get install -y git python3 pip wget \
    && apt-get clean

# download code from githu: https://github.com/csunny/DB-GPT
# ENV DBGPT_VERSION="v0.3.3"
# RUN wget https://github.com/csunny/DB-GPT/archive/refs/tags/$DBGPT_VERSION.zip

# clone latest code, and rename to /app
RUN git clone https://github.com/csunny/DB-GPT.git /app

WORKDIR /app

RUN pip3 install --upgrade pip \
    && pip3 install --no-cache-dir -r requirements.txt \
    && pip3 install seaborn mpld3 \
    && wget https://github.com/explosion/spacy-models/releases/download/zh_core_web_sm-3.5.0/zh_core_web_sm-3.5.0-py3-none-any.whl -O /tmp/zh_core_web_sm-3.5.0-py3-none-any.whl \
    && pip3 install /tmp/zh_core_web_sm-3.5.0-py3-none-any.whl \
    && rm /tmp/zh_core_web_sm-3.5.0-py3-none-any.whl \
    && rm -rf `pip3 cache dir` 

# RUN python3 -m spacy download zh_core_web_sm

EXPOSE 5000