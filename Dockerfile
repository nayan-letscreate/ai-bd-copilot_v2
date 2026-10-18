# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Unprivileged user: a compromised process cannot write to the image or bind privileged ports.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
 && mkdir -p /data && chown app:app /data

# Hash-pinned dependencies first (cached layer). --require-hashes refuses anything not in the lock file.
COPY requirements.txt .
RUN pip install --require-hashes -r requirements.txt

COPY app ./app

USER app

# Render injects PORT (10000 by default). SQLite lives on /data for single-container use;
# production should set DATABASE_URL to PostgreSQL.
ENV PORT=8000 \
    DATABASE_URL=sqlite:////data/bd_copilot.db \
    FORWARDED_ALLOW_IPS=*
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=4).status == 200 else 1)"]

# exec so uvicorn is PID 1 and receives SIGTERM; --no-server-header hides the server version.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --no-server-header"]
