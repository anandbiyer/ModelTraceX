# ModelTraceX v2 backend image (Phase 4 deploy).
#
# Runs the FastAPI app (modeltracex.api:create_app) under uvicorn. Built to run
# on Render's free/Starter web-service tier; the same image runs on Fly.io or
# any container host. Frontend ships separately to Vercel (see vercel.json).
FROM python:3.12-slim

# graphviz binary is needed only if the SVG/PDF lineage exporters are used;
# everything else (Mermaid text, OpenLineage JSON, draw.io XML) is pure-Python.
# Keep the image small by skipping it; uncomment to enable.
# RUN apt-get update && apt-get install -y --no-install-recommends graphviz && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy metadata first for better layer caching.
COPY pyproject.toml README.md ./
COPY modeltracex ./modeltracex

# Install the package + the extras the API path actually exercises.
# `[llm]` pulls anthropic; drop it if you're running local-only.
RUN pip install --no-cache-dir -e ".[api,store,export,lineage,security,llm]"

ENV PYTHONUNBUFFERED=1 \
    MODELTRACEX_DB_PATH=/data/modeltracex.db

# Render's free tier has no persistent disk — db lives ephemerally in /data.
# On Starter+disk, attach a disk mounted at /data so runs survive restarts.
RUN mkdir -p /data

# Render injects $PORT; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn modeltracex.api:create_app --factory --host 0.0.0.0 --port ${PORT}"]
