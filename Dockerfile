FROM python:3.11-slim

# Install system dependencies including git
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    libpq-dev \
    wget \
#     git \
#     curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Download and install Cloud SQL Auth Proxy
RUN wget https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.linux.amd64 -O /usr/local/bin/cloud-sql-proxy && \
    chmod +x /usr/local/bin/cloud-sql-proxy

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# COPY gen-ai-4all-115a57d466b1-jun2.json .
# Copy application code
COPY . .

# Create directories for temporary uploads
RUN mkdir -p /tmp/uploads /tmp/cloudsql

# Create startup script
RUN echo '#!/bin/bash\n\
# Start Cloud SQL Proxy in the background\n\
if [ -n "$INSTANCE_CONNECTION_NAME" ]; then\n\
  echo "Starting Cloud SQL Proxy..."\n\
  cloud-sql-proxy --unix-socket=/tmp/cloudsql "$INSTANCE_CONNECTION_NAME" &\n\
  echo "Waiting for Cloud SQL Proxy to start..."\n\
  sleep 2\n\
fi\n\
\n\
# Start the application\n\
echo "Starting FastAPI application..."\n\
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2\n\
' > /app/startup.sh && chmod +x /app/startup.sh

# Run startup script
CMD ["/app/startup.sh"]