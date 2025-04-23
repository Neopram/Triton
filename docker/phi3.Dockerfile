# Phi-3 Local Maritime AI Service Dockerfile
# Lightweight image optimized for local deployment
FROM python:3.10-slim AS base

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies (minimized for smaller image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Copy requirements first for better caching
COPY ai-services/phi3/requirements.txt .

# Install Python dependencies
# Use --no-cache-dir to keep the image smaller
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for security
RUN useradd -m -u 1000 appuser

# Create directories with proper permissions
RUN mkdir -p /app/model_cache /app/logs \
    && chown -R appuser:appuser /app

# Copy application code
COPY ai-services/phi3/ /app/

# Set environment variables for Phi-3
ENV PHI3_MODEL_PATH="microsoft/phi-3-mini-4k-instruct"
ENV PHI3_PORT=8001
ENV PHI3_IDLE_TIMEOUT=1800
ENV PHI3_CACHE_TTL=3600
ENV PHI3_CACHE_ENABLED=true
ENV PHI3_MAX_TOKENS=1024
ENV PHI3_DEFAULT_TEMPERATURE=0.5
ENV PHI3_USE_4BIT=true
ENV PHI3_LOW_CPU_MEM_USAGE=true
ENV TRANSFORMERS_CACHE=/app/model_cache

# Change to non-root user
USER appuser

# Expose the port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Pre-download the model during build to avoid first-request delay
RUN python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('microsoft/phi-3-mini-4k-instruct', trust_remote_code=True)"

# Command to run the application
CMD ["python", "phi3_service.py"]