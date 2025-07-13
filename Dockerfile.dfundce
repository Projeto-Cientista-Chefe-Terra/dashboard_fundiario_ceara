# Dcokerfile do terra_ce

FROM python:3.13-slim-bullseye
LABEL maintainer="Wellington Wagner F. Sarmento <wwagner@virtual.ufc.br>" \
      description="Dockerfile do Terra.Ce"

WORKDIR /terra_ce

# Variáveis de ambiente (configurações Python e timezone)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_ROOT_USER_ACTION=ignore \
    TZ=America/Fortaleza \
    CPLUS_INCLUDE_PATH=/usr/include/gdal \
    C_INCLUDE_PATH=/usr/include/gdal

# Instalação de dependências do sistema e Python, seguida de limpeza
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    python3-gdal \
    tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    apt-get purge -y --auto-remove build-essential libgdal-dev libgeos-dev libproj-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

# Copiando o código da aplicação 
COPY . .


EXPOSE 8501


ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
