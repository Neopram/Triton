# DeepSeek Maritime AI Service Dockerfile
# Base image with CUDA support for GPU acceleration
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 AS base

# Set working directory
WORKDIR /app

# Avoid warnings by switching to noninteractive
ENV DEBIAN_FRONTEND=noninteractive

# Set Python to not create .pyc files and ensure stdout/stderr are sent straight to terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    build-essential \
    wget \
    git \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic link to use python instead of python3
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Upgrade pip
RUN python -m pip install --upgrade pip

# Copy requirements first for better caching
COPY ai-services/deepseek/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user
RUN useradd -m -u 1000 appuser

# Copy application code
COPY ai-services/deepseek/ /app/

# Set environment variables
ENV DEEPSEEK_MODEL="deepseek-ai/deepseek-coder-33b-instruct"
ENV DEEPSEEK_PORT=8000
ENV DEEPSEEK_IDLE_TIMEOUT=3600
ENV DEEPSEEK_CACHE_TTL=3600
ENV DEEPSEEK_CACHE_ENABLED=true
ENV DEEPSEEK_MAX_TOKENS=2048
ENV DEEPSEEK_DEFAULT_TEMPERATURE=0.7
ENV PYTHONPATH=/app

# Create a directory for the model cache with proper permissions
RUN mkdir -p /app/model_cache && chown -R appuser:appuser /app/model_cache
ENV TRANSFORMERS_CACHE=/app/model_cache

# Change to non-root user
USER appuser

# Create a directory for logs with proper permissions
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# Expose the port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the application
CMD ["python", "deepseek_service.py"]