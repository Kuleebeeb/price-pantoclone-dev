# The screen is built here rather than committed as a folder of built files.
# A dist/ in the repository is a thing that can disagree with the source beside
# it, and the day it does nobody can tell which one is on the server.
FROM node:22-alpine AS web
WORKDIR /build
COPY pantongone-frontend/package.json pantongone-frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY pantongone-frontend/ ./
RUN npm run build

FROM python:3.13-slim
ARG SOURCE_REV=unknown
LABEL org.opencontainers.image.revision=$SOURCE_REV

# UID fixed as a NUMBER: Docker volumes keep ownership by number, not by name.
# Change it on a later build and the new container cannot write the data the
# old one created.
RUN groupadd -g 10001 -r app && useradd -u 10001 -r -g app -m -d /home/app app
ENV HOME=/home/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/app

COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server/core/ ./core/
COPY server/api/ ./api/
COPY server/tests/ ./tests/
COPY server/deploy/import_local_history.py ./deploy/import_local_history.py

# Served by the API itself at /, so this host needs no second container and
# no change to nginx - which is what keeps the .exe's update path (/api/version
# and /download) exactly where every installed copy expects it.
COPY --from=web /build/dist/ ./web/

USER app
EXPOSE 8100

# A real check: it opens the app's own /api/health, which pings Postgres and
# answers 503 with the reason when the database is gone. A constant {"ok":true}
# would let a deploy with no database at all report success.
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/api/health', timeout=4).status==200 else 1)"

CMD ["python", "-m", "uvicorn", "main:app", "--app-dir", "api", "--host", "0.0.0.0", "--port", "8100"]
