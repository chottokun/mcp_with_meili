# Use the same base image
FROM python:3.12-slim

WORKDIR /app

# Copy the requirements file from the root
COPY requirements.txt .

# Install Python dependencies including fastapi and uvicorn
RUN pip install --no-cache-dir -r requirements.txt

# Copy the fastmcp application code
COPY services/fastmcp/main.py .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
