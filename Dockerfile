FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/apps/api/src:/app/packages/domain/src:/app/packages/scoring/src:/app/integrations/maps_scraper/src:/app/integrations/website_auditor/src

WORKDIR /app

RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "pydantic-settings>=2.5" \
    "sqlalchemy>=2.0" \
    "psycopg[binary]>=3.2" \
    "redis>=5.0" \
    "alembic>=1.13" \
    "httpx>=0.27" \
    "playwright>=1.50" \
    "beautifulsoup4>=4.12" \
    "python-multipart>=0.0.9"

COPY apps ./apps
COPY packages ./packages
COPY integrations ./integrations
COPY infrastructure ./infrastructure
COPY scripts ./scripts
COPY config ./config

# The auditor is provider-backed and must have a browser available when it is
# deliberately enabled. No browser is launched during image build.
RUN playwright install --with-deps chromium

EXPOSE 8000

CMD ["sh", "-c", "python scripts/migrate.py --database-url \"$LBOE_DATABASE_URL\" && exec uvicorn lboe_api.main:app --host 0.0.0.0 --port 8000"]
