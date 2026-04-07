FROM python:3.11-slim

WORKDIR /app

# Install system dependencies + Node.js (for frontend build)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (avoids pulling the 2GB CUDA build)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Build the React frontend so main.py can serve it as a SPA
RUN cd frontend && npm install && npm run build

# Pre-train ZoneScorerNet on synthetic data and bake weights into the image.
# This means inference is instant at runtime — no training cost per request.
RUN python agents/train_zone_scorer.py

# HF Spaces runs on port 7860
EXPOSE 7860

# Health check — used by HF Spaces to confirm deployment
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"

# Start FastAPI server
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
