FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-pol tesseract-ocr-eng fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.11.8 \
    && groupadd --gid 10001 broker && useradd --uid 10001 --gid broker --create-home broker
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN uv sync --project backend --frozen --no-dev
COPY --chown=broker:broker backend ./backend
COPY --chown=broker:broker scripts ./scripts
COPY --chown=broker:broker fixtures ./fixtures
RUN python scripts/check_ocr.py
RUN mkdir -p /app/.local/media && chown -R broker:broker /app/.local
USER broker
ENV PATH="/app/backend/.venv/bin:$PATH" PYTHONPATH=/app/backend
WORKDIR /app/backend
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
