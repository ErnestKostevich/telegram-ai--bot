# Lightweight image for the Telegram bot on Fly.io.
# Python 3.11 (same version as Render's PYTHON_VERSION).
FROM python:3.11-slim

# Don't write .pyc files and don't buffer stdout (so `fly logs` is live)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install OS-level deps that aiohttp/cryptography sometimes need at runtime.
# Slim image already has libc; this keeps image small.
RUN apt-get update -y \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer-cache reuse
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY . .

# Bot does long-polling AND serves HTTP on 8080 (NOWPayments webhook + Mini App).
EXPOSE 8080
CMD ["python", "main.py"]
