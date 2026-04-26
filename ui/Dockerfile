FROM python:3.11-slim

WORKDIR /app

# curl is used by the app healthcheck (CMD-SHELL in docker-compose)
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

EXPOSE 8000

CMD ["chainlit", "run", "ui/app.py", "--host", "0.0.0.0", "--port", "8000"]
