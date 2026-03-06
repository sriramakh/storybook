FROM python:3.12-slim

# System fonts for text_overlay.py (DejaVu is in the fallback chain)
RUN apt-get update && \
    apt-get install -y --no-install-recommends fonts-dejavu-core ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY tracks/ ./tracks/

# Ensure stories directory exists inside the container
RUN mkdir -p /app/stories

CMD ["python", "bot.py"]
