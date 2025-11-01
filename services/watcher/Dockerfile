# Use the same base image as the original ingester
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies that might be needed by libraries like docling
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file from the root of the repo
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the watcher-specific code
COPY services/watcher/main.py .

# Command to run the watcher service
CMD ["python", "main.py"]
