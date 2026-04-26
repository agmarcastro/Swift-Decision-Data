FROM python:3.11-slim

WORKDIR /app

# curl is available for any ad-hoc healthcheck or debug needs inside the container
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from project definition
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application packages
COPY agent/ ./agent/
COPY contextualize/ ./contextualize/
COPY ingest/ ./ingest/
COPY ui/ ./ui/

ENV PYTHONPATH=/app
