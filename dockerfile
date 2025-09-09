FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libasound2 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Установка Chromium для Playwright
RUN playwright install chromium

COPY . .

RUN mkdir -p /app/output /app/logs


ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV HEADLESS=true
ENV OUTPUT_DIR=/app/output
ENV LOGS_DIR=/app/logs


CMD ["python", "scheduler.py"]
