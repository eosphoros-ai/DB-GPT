FROM nvidia/cuda:11.8.0-devel-ubuntu22.04

RUN apt-get update && apt-get install -y \
	git \
	python3 \
	pip

	
WORKDIR /app

COPY . /app

RUN pip install -r requirements.txt

EXPOSE 7860
EXPOSE 8000

CMD ["python", "pilot/server/llmserver.py"]
CMD ["python", "pilot/server/webserver.py"]
