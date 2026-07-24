# Backend Dockerfile for Render
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including Playwright browser dependencies)
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    chromium \
    chromium-driver \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
# Docker build context should be set to 'backend/' in Render settings
# If context is root, this will fail - ensure Docker Build Context Directory is set to 'backend'
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers for social media scraping
# Note: System dependencies are installed above
RUN pip install playwright && \
    playwright install chromium && \
    playwright install-deps chromium

# Copy application code
COPY . .

# Expose port (Render sets PORT env var)
EXPOSE 8000

# Start command
# Render will set PORT environment variable
# Use sh -c to properly expand PORT env var
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"

