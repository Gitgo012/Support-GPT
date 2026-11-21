FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HF_HOME=/data/hf-cache \
    SUPPORTGPT_DATABASE_PATH=/data/supportgpt.sqlite3 \
    SUPPORTGPT_LOAD_MODEL=0

RUN apt-get update \
    && apt-get install -y --no-install-recommends passwd ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv \
    && groupadd --system supportgpt \
    && useradd --system --gid supportgpt --create-home supportgpt \
    && mkdir -p /app /data/hf-cache \
    && chown -R supportgpt:supportgpt /app /data

WORKDIR /app
USER supportgpt

COPY --chown=supportgpt:supportgpt pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --extra ml --no-dev --no-install-project

COPY --chown=supportgpt:supportgpt app ./app
COPY --chown=supportgpt:supportgpt configs ./configs
COPY --chown=supportgpt:supportgpt src ./src
RUN uv sync --frozen --extra ml --no-dev --no-editable

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
