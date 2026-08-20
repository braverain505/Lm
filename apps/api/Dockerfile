# SchoolOS API — production image.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/api

# System deps for psycopg2-binary are pre-bundled; nothing else needed.
# Copy the whole app then install so the package (app/*) is present — pip install
# with a bare pyproject (no package) would otherwise fail.
COPY apps/api .
RUN pip install --upgrade pip && pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]