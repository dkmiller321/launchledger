FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev && sed -i 's/\r$//' scripts/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["sh", "scripts/entrypoint.sh"]
