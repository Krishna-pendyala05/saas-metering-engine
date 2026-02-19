# Stage 1: Builder — install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies using pip + requirements.txt (no Poetry needed at runtime)
COPY requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runner — lean production image
FROM python:3.11-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev curl && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY backend /app/backend
COPY alembic.ini /app/

# Set ownership
RUN chown -R app:app /app

# Switch to non-root user
USER app

ENV PYTHONPATH=/app/backend

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
