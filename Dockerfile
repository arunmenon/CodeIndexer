FROM python:3.10-slim

WORKDIR /app

# Install necessary system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt /app/
COPY requirements-test.txt /app/

# Install Python dependencies 
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/workspace /app/logs /app/config

# Set environment variables
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO
ENV WORKSPACE_DIR=/app/workspace

# Set up entrypoint
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Default command (will be overridden in docker-compose)
CMD ["python", "-m", "code_indexer.api.search_api"]