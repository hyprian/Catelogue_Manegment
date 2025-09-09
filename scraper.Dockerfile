# scraper.Dockerfile
# Use a base image that supports ARM64 (aarch64)
FROM --platform=linux/arm64 python:3.10-slim-bookworm

# Set environment variables for Python and Pip
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on

# Set the working directory inside the container
WORKDIR /app

# --- Install System Dependencies and CHROMIUM ---
# This is the proven setup from your test
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# --- Install Python Dependencies ---
# Copy ONLY the scraper-specific requirements file
COPY scrapers/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy Project Code ---
# Copy the necessary Python modules for the scraper to run
COPY scrapers/ scrapers/
COPY connectors/ connectors/
COPY utils/ utils/
COPY settings.yaml .

# --- Create a directory for logs inside the container ---
RUN mkdir -p /app/logs

# The default command to run when the container starts
CMD ["python", "scrapers/amazon_enrichment.py"]