# Soldier Production Dockerfile
# Multi-stage build for minimal final image

# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv for faster dependency installation
RUN pip install uv

# Copy project files
COPY pyproject.toml ./
COPY soldier/ ./soldier/

# Install dependencies
RUN uv pip install --system .

# Runtime stage
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash soldier
USER soldier

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app/soldier ./soldier

# Copy config files
COPY config/ ./config/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV SOLDIER_ENV=production

# Default command
CMD ["python", "-m", "soldier.api"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

EXPOSE 8000
