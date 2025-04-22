ARG BASE_IMAGE="nvidia/cuda:12.4.0-devel-ubuntu22.04"
# Add parameter to control whether to use Tsinghua Ubuntu mirror
ARG USE_TSINGHUA_UBUNTU="false"

FROM ${BASE_IMAGE} as builder
ARG BASE_IMAGE
ARG PYTHON_VERSION=3.11
# Use Tsinghua PyPI mirror, It's faster in most countries
ARG PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
ARG UV_TRUSTED_HOST="127.0.0.1"
ARG UV_HTTP_TIMEOUT=180
ARG EXTRAS="base,proxy_openai,rag,storage_chromadb,cuda121,hf,quant_bnb,dbgpts"
ARG VERSION=latest
ARG USE_TSINGHUA_UBUNTU
ARG CMAKE_ARGS
ARG INSTALL_RUST="true"
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=${UV_TRUSTED_HOST} \
    UV_TRUSTED_HOST=${UV_TRUSTED_HOST} \
    UV_INSECURE_HOST=${UV_TRUSTED_HOST} \
    UV_HTTP_TIMEOUT=${UV_HTTP_TIMEOUT} \
    CMAKE_ARGS=${CMAKE_ARGS} \
    INSTALL_RUST=${INSTALL_RUST}

# Configure apt sources based on the USE_TSINGHUA_UBUNTU parameter
RUN if [ "$USE_TSINGHUA_UBUNTU" = "true" ]; then \
        sed -i 's/archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
        sed -i 's/security.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends gnupg ca-certificates apt-transport-https && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update && apt-get install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python${PYTHON_VERSION}-venv \
    python3-pip \
    git \
    curl \
    wget \
    tzdata \
    sqlite3 \
    libpq-dev \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && python${PYTHON_VERSION} -m pip install --upgrade pip --trusted-host ${UV_TRUSTED_HOST} \
    && python${PYTHON_VERSION} -m pip install --upgrade pipx --trusted-host ${UV_TRUSTED_HOST} \
    && python${PYTHON_VERSION} -m pipx ensurepath \
    && pipx ensurepath --global \
    && pipx install uv --global --pip-args="--trusted-host ${UV_TRUSTED_HOST}"

# Install Rust toolchain for building lyric-py
RUN if [ "$INSTALL_RUST" = "true" ]; then \
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y; \
    fi

ENV PATH="/root/.cargo/bin:${PATH}"

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
    uv sync --frozen --all-packages \
    --no-dev $extras \
    --index-url=$PIP_INDEX_URL \
    --trusted-host=$UV_TRUSTED_HOST \
    && \
    # Verify installation
    python -c "import dbgpt; print(dbgpt.__version__)"
ARG LANGUAGE="en"
ARG PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
ENV PIP_INDEX_URL=$PIP_INDEX_URL

FROM ${BASE_IMAGE}
ARG PYTHON_VERSION=3.11
ARG VERSION=latest
ARG USE_TSINGHUA_UBUNTU
# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
    # Set PYTHONPATH
# Version label
LABEL version=${VERSION}

# Configure apt sources based on the USE_TSINGHUA_UBUNTU parameter
RUN if [ "$USE_TSINGHUA_UBUNTU" = "true" ]; then \
        sed -i 's/archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
        sed -i 's/security.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends git sqlite3 gnupg ca-certificates apt-transport-https && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update && apt-get install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Copy the virtual environment from the previous stage
# Use another name to avoid conflict when mounting user's local .venv
ENV FINAL_VENV_NAME="/opt/.uv.venv"
COPY --from=builder /app/.venv ${FINAL_VENV_NAME}
COPY . .
# Fix the shebang of the dbgpt script
RUN sed -i "s|^#\!/app/\.venv/bin/python[0-9.]*|#!/${FINAL_VENV_NAME}/bin/python${PYTHON_VERSION}|" /${FINAL_VENV_NAME}/bin/dbgpt
RUN sed -i "s|^#\!/app/\.venv/bin/python[0-9.]*|#!/${FINAL_VENV_NAME}/bin/python${PYTHON_VERSION}|" /${FINAL_VENV_NAME}/bin/pip
RUN sed -i "s|/app/\.venv|${FINAL_VENV_NAME}|g" /${FINAL_VENV_NAME}/bin/activate

ENV PATH="${FINAL_VENV_NAME}/bin:$PATH" \
    VIRTUAL_ENV="${FINAL_VENV_NAME}"
# Default command
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-siliconflow.toml"]