FROM python:3.10-slim

ARG SENTENCE_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NLTK_DATA=/opt/nltk_data \
    HF_HOME=/opt/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/opt/huggingface \
    APP_MODEL_PATH=/app/model/classifier.joblib \
    APP_MODEL_METADATA_PATH=/app/model/metadata.json

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates \
    && python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt \
    && python -m spacy download en_core_web_sm \
    && python -m spacy download es_core_news_md \
    && mkdir -p /opt/nltk_data /opt/huggingface /app/model \
    && python -m nltk.downloader -d /opt/nltk_data vader_lexicon \
    && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${SENTENCE_MODEL}')" \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/* /root/.cache

COPY train_model.py /app/train_model.py
COPY data/muestra_nlp_sample.jsonl /app/data/muestra_nlp_sample.jsonl

RUN TRAINING_DATA_PATH=/app/data/muestra_nlp_sample.jsonl \
    MODEL_OUTPUT_PATH=/app/model/classifier.joblib \
    MODEL_METADATA_PATH=/app/model/metadata.json \
    python /app/train_model.py \
    && rm -rf /app/data

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY app.py /app/app.py

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin app \
    && chown -R 10001:10001 /app /opt/nltk_data /opt/huggingface

USER 10001:10001

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=10m --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/health/live', timeout=3)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
