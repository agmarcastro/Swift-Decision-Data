FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[mcp]" 2>/dev/null || pip install --no-cache-dir mcp psycopg2-binary

COPY contextualize/mcp_server/ ./contextualize/mcp_server/
COPY contextualize/__init__.py ./contextualize/__init__.py

ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["python", "-m", "contextualize.mcp_server.server"]
