FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Upgrade pip and install dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Railway provides PORT env variable
ENV PORT=8080

# Expose port
EXPOSE $PORT

# Run the application - use shell form to expand PORT variable
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
