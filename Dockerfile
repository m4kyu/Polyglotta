FROM python:3.13-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 polyglotta && useradd --uid 10001 --gid polyglotta --create-home polyglotta \
    && install -d -m 0700 -o polyglotta -g polyglotta /var/lib/polyglotta /var/lib/anki /run/polyglotta
COPY polyglotta/ polyglotta/

FROM base AS web
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py alembic.ini ./
COPY migrations/ migrations/
COPY static/ static/
USER polyglotta
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS anki
COPY requirements-anki.txt .
RUN pip install --no-cache-dir -r requirements-anki.txt && python -c "from anki.collection import Collection"
USER polyglotta
CMD ["python", "-m", "polyglotta.anki_service", "serve"]
