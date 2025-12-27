FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive

# 1. Устанавливаем зависимости
RUN apt-get update && apt-get install -y \
    wget \
    ffmpeg \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libtiff5-dev \
    libraqm-dev \
    cabextract \
    xfonts-utils \
    && echo "deb http://deb.debian.org/debian trixie contrib non-free" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y ttf-mscorefonts-installer \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]