# Use the official Python image from the DockerHub
FROM python:3.11-slim

# Install the necessary package for ping command
RUN apt-get update && apt-get install -y iputils-ping

# Set the working directory in docker
WORKDIR /app

# Install system tools and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*


# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the content of the local src directory to the working directory
COPY . .

# Specify the command to run on container start
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]