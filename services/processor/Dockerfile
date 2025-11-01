# Use the same base image
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required for docling
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file from the root
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the processor-specific code
COPY services/processor/main.py .

# Command to run the processor service
CMD ["python", "main.py"]
