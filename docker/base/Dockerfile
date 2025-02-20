ARG BASE_IMAGE="nvidia/cuda:12.1.0-devel-ubuntu22.04"
FROM ${BASE_IMAGE} as builder
ARG BASE_IMAGE
ARG PYTHON_VERSION=3.10
ARG PYPI_MIRROR=https://pypi.org/simple
ARG EXTRAS="proxy_openai,rag,storage_chromadb,quant_bnb"
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
    python3-dev \
    python3-virtualenv \
    git \
    curl \
    wget \
    tzdata \
    sqlite3 \
    libpq-dev \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/* \
    && python${PYTHON_VERSION} -m pip install --upgrade pip \
    && python${PYTHON_VERSION} -m pip install --upgrade pipx \
    && python${PYTHON_VERSION} -m pipx ensurepath \
    && pipx ensurepath --global \
    && pipx install uv --global

WORKDIR /app

# Create a virtual environment
ENV VIRTUAL_ENV=/app/.venv
RUN python${PYTHON_VERSION} -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY pyproject.toml README.md uv.lock ./
COPY packages /app/packages

# Install dependencies with uv and install all local packages
RUN --mount=type=cache,target=/root/.cache/uv \
    extras=$(echo $EXTRAS | tr ',' '\n' | while read extra; do echo "--extra $extra"; done | tr '\n' ' ') && \
    uv sync --frozen --all-packages --no-dev $extras && \
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
    LC_ALL=C.UTF-8
    # Set PYTHONPATH

# Version label
LABEL version=${VERSION}

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtual environment from the previous stage
# Use antoher name to avoid conflict when mounting user's local .venv
ENV FINAL_VENV_NAME="/opt/.uv.venv"
COPY --from=builder /app/.venv ${FINAL_VENV_NAME}
COPY . .

# Fix the shebang of the dbgpt script
RUN sed -i "s|^#\!/app/\.venv/bin/python[0-9.]*|#!/${FINAL_VENV_NAME}/bin/python${PYTHON_VERSION}|" /${FINAL_VENV_NAME}/bin/dbgpt
RUN sed -i "s|^#\!/app/\.venv/bin/python[0-9.]*|#!/${FINAL_VENV_NAME}/bin/python${PYTHON_VERSION}|" /${FINAL_VENV_NAME}/bin/pip

ENV PATH="${FINAL_VENV_NAME}/bin:$PATH" \
    VIRTUAL_ENV="${FINAL_VENV_NAME}"
#    PYTHONPATH="/app/packages/dbgpt/src:/app/packages/dbgpt-core/src:/app/packages/dbgpt-app/src:/app/packages/dbgpt-serve/src:/app/packages/dbgpt-client/src:/app/packages/dbgpt-ext/src:/app/packages/dbgpt-accelerator/src"

# Default command
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-siliconflow.toml"]
