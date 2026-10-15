FROM python:3.11-slim

# Install system dependencies required for PDF conversion and C++ compilation
RUN apt-get update && apt-get install -y \
    libreoffice \
    gcc \
    g++ \
    python3-dev \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Start the server using run_app.py to ensure frontend is mounted and sys.path is correct
CMD ["python", "backend/run_cloud.py"]
