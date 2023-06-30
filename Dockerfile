FROM nvidia/cuda:11.8.0-devel-ubuntu22.04

WORKDIR /app

RUN apt-get update && apt-get install -y \
	git \
	python3 \
	pip

# upgrade pip
RUN pip3 install --upgrade pip

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

RUN python3 -m spacy download zh_core_web_sm


COPY . /app

EXPOSE 7860
EXPOSE 8000