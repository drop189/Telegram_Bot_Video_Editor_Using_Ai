FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive

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
    && rm -rf /var/lib/apt/lists/*

RUN wget http://ftp.debian.org/debian/pool/contrib/m/msttcorefonts/ttf-mscorefonts-installer_3.8_all.deb && \
    dpkg -i ttf-mscorefonts-installer_3.8_all.deb && \
    fc-cache -fv && \
    rm ttf-mscorefonts-installer_3.8_all.deb

WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .


CMD ["python", "main.py"]