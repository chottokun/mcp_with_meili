# Use the same base image
FROM python:3.12-slim

WORKDIR /app

# No heavy system dependencies needed for this service, but keeping consistency
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file from the root
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the ingester-specific code
COPY services/ingester/main.py .

# Command to run the ingester service
CMD ["python", "main.py"]
