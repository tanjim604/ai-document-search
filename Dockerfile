FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf-cache

# Tesseract reads text in images and scanned PDFs.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch first: the default wheel bundles CUDA and adds gigabytes.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the models into the image so the first request is not slow and the
# container works without internet access: text embeddings and image captioning.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
RUN python -c "from transformers import BlipProcessor, BlipForConditionalGeneration as B; n='Salesforce/blip-image-captioning-base'; BlipProcessor.from_pretrained(n); B.from_pretrained(n)"

COPY app ./app
COPY sample_files ./sample_files

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
