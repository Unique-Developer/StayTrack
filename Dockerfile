FROM python:3.11-slim

# Install system packages required for PDF parsing and OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ /app/backend/

WORKDIR /app/backend

# Ensure storage directories exist
RUN mkdir -p storage/reports storage/staging

ENV PYTHONPATH=/app/backend

# Expose Render standard port (10000) and local port (8000)
EXPOSE 10000 8000

# Bind to Render's injected $PORT (defaults to 10000 on Render)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
