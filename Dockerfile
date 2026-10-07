# Use lightweight official Python image
FROM python:3.11-slim

# Prevent Python from writing .pyc files to disk and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for efficient layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Cloud Run injects the PORT environment variable dynamically (defaults to 8080)
ENV PORT=8080

# Run uvicorn on 0.0.0.0 to listen on all network interfaces
CMD exec uvicorn app.main:app --host 0.0.0.0 --port $PORT