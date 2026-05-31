FROM python:3.12-slim AS builder

WORKDIR /app

COPY app/pyproject.toml app/uv.lock app/README.md ./
COPY app/src ./src

RUN pip install --no-cache-dir uv \
  && uv sync --frozen --no-dev

FROM python:3.12-slim

WORKDIR /app 

COPY --from=builder /app/.venv /app/.venv
COPY app/src ./src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "ml_api.main:app", "--host", "0.0.0.0", "--port", "8000"]