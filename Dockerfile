FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer-cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# The droplet host directory is bind-mounted at /data in production.
# Create it here as a fallback for local Docker runs without a bind mount.
RUN mkdir -p /data

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    THRESHOLD_DATA_DIR=/data

# Socket Mode — outbound WebSocket only, no inbound HTTP port needed.
CMD ["python", "app.py"]
