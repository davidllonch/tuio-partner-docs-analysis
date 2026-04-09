FROM python:3.12-slim

# Install system-level dependencies:
# - tesseract-ocr: the OCR engine that reads text from scanned images
# - tesseract-ocr-spa: Spanish language pack for better accuracy on Spanish documents
# - libgl1, libglib2.0-0: required by PyMuPDF (the PDF processing library)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1 \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    fonts-liberation \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies first (Docker layer caching optimization)
# This means re-building after code changes won't re-download all packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# The document storage directory will be mounted as a Docker volume in production.
# We create it here as a fallback for local testing.
RUN mkdir -p /data/documents

EXPOSE 8000

# Start the application with 2 worker processes.
# Each worker can handle one request at a time; 2 workers allow some parallelism.
# For production under heavy load, increase workers or use --workers $(nproc).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
