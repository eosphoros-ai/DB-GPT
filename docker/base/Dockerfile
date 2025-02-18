ARG BASE_IMAGE="nvidia/cuda:12.1.0-devel-ubuntu22.04"
FROM ${BASE_IMAGE} as builder
ARG BASE_IMAGE
ARG PYTHON_VERSION=3.10
ARG PYPI_MIRROR=https://pypi.org/simple
ARG EXTRAS="proxy_openai,rag,storage_chromadb,llama_cpp,llama_cpp_server,quant_bnb"
ARG VERSION=latest

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIP_INDEX_URL=${PYPI_MIRROR}

RUN apt-get update && apt-get install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python3-pip \
    git \
    curl \
    wget \
    tzdata \
    sqlite3 \
    libpq-dev \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv and make sure the path is correct
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    cp /root/.local/bin/uv /usr/local/bin/uv

# Create a virtual environment
ENV VIRTUAL_ENV=/app/.venv
RUN python${PYTHON_VERSION} -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY pyproject.toml README.md uv.lock ./
COPY packages /app/packages

# Install dependencies with uv and install all local packages
RUN mkdir -p /root/.cache/uv && \
    extras=$(echo $EXTRAS | tr ',' '\n' | while read extra; do echo "--extra $extra"; done | tr '\n' ' ') && \
    uv sync --all-packages $extras && \
    # Install local packages, pay attention to the installation order
    cd /app/packages/dbgpt-accelerator && pip install -e . && \
    cd /app/packages/dbgpt-core && pip install -e . && \
    cd /app/packages/dbgpt-ext && pip install -e . && \
    cd /app/packages/dbgpt-client && pip install -e . && \
    cd /app/packages/dbgpt-serve && pip install -e . && \
    cd /app/packages/dbgpt-app && pip install -e . && \
    # Verify installation
    python -c "import dbgpt; print(dbgpt.__version__)"

ARG BUILD_LOCAL_CODE="false"
ARG LANGUAGE="en"
ARG PIP_INDEX_URL="https://pypi.org/simple"
ENV PIP_INDEX_URL=$PIP_INDEX_URL
ARG DB_GPT_INSTALL_MODEL="default"
ENV DB_GPT_INSTALL_MODEL=$DB_GPT_INSTALL_MODEL


FROM ${BASE_IMAGE}

ARG PYTHON_VERSION=3.10
ARG VERSION=latest

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    # Set PYTHONPATH
    PYTHONPATH="/app/packages/dbgpt/src:/app/packages/dbgpt-core/src:/app/packages/dbgpt-app/src:/app/packages/dbgpt-serve/src:/app/packages/dbgpt-client/src:/app/packages/dbgpt-ext/src:/app/packages/dbgpt-accelerator/src"

# Version label
LABEL version=${VERSION}

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtual environment from the previous stage
COPY --from=builder /app/.venv /opt/venv
COPY . .

ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv" \
    PYTHONPATH="/app/packages/dbgpt/src:/app/packages/dbgpt-core/src:/app/packages/dbgpt-app/src:/app/packages/dbgpt-serve/src:/app/packages/dbgpt-client/src:/app/packages/dbgpt-ext/src:/app/packages/dbgpt-accelerator/src"

# Default command
CMD ["/opt/venv/bin/python", "packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py", "--config", "configs/dbgpt-siliconflow.toml"]
