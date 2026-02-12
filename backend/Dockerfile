# Multi-stage: build deps then minimal runtime
FROM python:3.12-slim as builder

WORKDIR /app

# Install build deps if any (e.g. for Pillow)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.12-slim as runtime

WORKDIR /app

# Non-root user
RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# Gunicorn + uvicorn workers for async FastAPI
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "-w", "2", "--access-logfile", "-", "--capture-output"]
