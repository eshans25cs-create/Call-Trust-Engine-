FROM python:3.11-slim

# Install system audio and networking libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    libportaudio2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agent/ agent/
COPY client/ client/
COPY .env.example .env.example

# Expose Telephony Gateway port
EXPOSE 8000

# Default command: launch the FastAPI / WebSocket telephony gateway
CMD ["python", "-m", "agent.telephony.gateway"]
