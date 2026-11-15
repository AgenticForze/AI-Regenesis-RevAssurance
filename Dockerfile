# Revenue Assurance: API, console, MCP and A2A endpoints in one image.
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY evals ./evals
RUN pip install .
COPY skills ./skills
COPY config ./config
COPY data/taxonomy.yaml ./data/taxonomy.yaml
# Run as a non-root user with a writable data volume only.
RUN useradd --system --uid 10001 ra && mkdir /data && chown ra /data
USER ra
ENV RA_DATA_DIR=/data RA_SKILLS_DIR=/app/skills RA_PLUGINS_CONFIG=/app/config/plugins.yaml \
    PYTHONPATH=/app/src
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz')"
CMD ["python", "-m", "ra.cli", "serve", "--host", "0.0.0.0", "--port", "8080"]
