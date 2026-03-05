FROM pytorch/pytorch:2.10.0-cuda12.8-cudnn9-runtime

WORKDIR /app

# System deps (ffmpeg for audio conversion, libsndfile for soundfile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# App — copy all backend modules
COPY backend/ /app/backend/
WORKDIR /app/backend

EXPOSE 8882

CMD ["python", "serve.py"]
