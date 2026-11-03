# GoWhere as one container: one process, Waitress serving the Flask app (DECISIONS.md
# sections 4, 17 and 36). Never run more than one: sessions live in this process's memory.
FROM python:3.13-slim

# The code is owned by root and read-only to the app user, so don't try to write .pyc files.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so this layer is reused until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only what the running app reads (gowhere/config.py).
COPY gowhere/ gowhere/
COPY data/snapshot.db data/eat.db data/events.db data/
COPY data/reference/ data/reference/

# A non-root user that can still write data/: serve.py writes data/logs/ at start-up, and
# SQLite in WAL mode creates events.db-wal and events.db-shm next to events.db.
RUN useradd --create-home --uid 10001 gowhere \
    && mkdir -p data/logs \
    && chown -R gowhere:gowhere /app/data
USER gowhere

EXPOSE 8000
CMD ["sh", "-c", "python -m gowhere.serve --host 0.0.0.0 --port ${PORT:-8000}"]
