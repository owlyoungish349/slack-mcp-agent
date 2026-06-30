FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer-cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# The Fly Volume will be mounted at /data; THRESHOLD_DATA_DIR points there.
# The directory is created here as a fallback for local Docker runs without a volume.
RUN mkdir -p /data

ENV THRESHOLD_DATA_DIR=/data

# Socket Mode — outbound WebSocket only, no inbound HTTP port needed.
CMD ["python", "app.py"]
