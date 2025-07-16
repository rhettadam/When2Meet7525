# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy app code
COPY . .

# Expose port (Dash/Flask default is 8050, but Fly expects 8080)
ENV PORT 8080
CMD exec gunicorn --bind :8080 --workers 3 app:server