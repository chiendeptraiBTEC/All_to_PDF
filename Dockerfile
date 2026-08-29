FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY frontend ./frontend

RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN mkdir -p /app/var/storage && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live')"

CMD ["uvicorn", "all_to_pdf.main:app", "--app-dir", "backend/src", "--host", "0.0.0.0", "--port", "8000"]
