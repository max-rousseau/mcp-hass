FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir hatchling

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Build wheel
RUN pip wheel --no-deps --wheel-dir /wheels .


FROM python:3.12-slim

WORKDIR /app

# Install git for pip git+https dependencies, then clean up
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash mcp

# Create /data directory for token persistence
RUN mkdir -p /data && chown mcp:mcp /data

# Copy wheel from builder and install
COPY --from=builder /wheels/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Switch to non-root user
USER mcp

# Default port for HTTP streaming transport
EXPOSE 3000

# Health check endpoint (FastMCP exposes this automatically)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:3000/health')" || exit 1

# Default command: HTTP streaming transport on all interfaces
ENTRYPOINT ["mcp-hass", "serve", "--transport", "http", "--host", "0.0.0.0"]
CMD ["--port", "3000"]
