FROM python:3.10-slim

WORKDIR /code

# 1. Instalamos las herramientas de compilación del sistema (necesarias para spaCy/thinc)
RUN apt-get update && apt-get install -y build-essential python3-dev && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /code/requirements.txt

# 2. Actualizamos pip antes de instalar las librerías
RUN pip install --no-cache-dir --upgrade pip

# 3. Instalamos las dependencias del proyecto
RUN pip install --no-cache-dir -r /code/requirements.txt
RUN python -m spacy download en_core_web_sm
RUN python -m spacy download es_core_news_md

# 4. Configuramos el usuario para Hugging Face Spaces
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user . $HOME/app

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]