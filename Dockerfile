# Dockerfile para o dashboard fundiário do Ceará
FROM python:3.12-slim


WORKDIR /app


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_ROOT_USER_ACTION=ignore \
    STREAMLIT_SERVER_PORT=8501 \
    DATA_SERVICE_URL=http://0.0.0.0:8000


RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .


RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


COPY . .


EXPOSE 8501


CMD ["streamlit", "run", "/app/app.py", "--server.port=8501", "--server.address=0.0.0.0"]