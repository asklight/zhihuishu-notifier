FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CHROME_PATH=/usr/bin/chromium \
    TZ=Asia/Shanghai

WORKDIR /app

# 换成阿里云 Debian 镜像源，解决 ECS 上 apt 超时问题
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-common \
    ca-certificates \
    fonts-noto-cjk \
    libglib2.0-0 \
    libnss3 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

# pip 也换成阿里云镜像
RUN pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

COPY . .

RUN mkdir -p /app/data \
    && [ -f /app/data/cookie.json ] || echo "{}" > /app/data/cookie.json \
    && [ -f /app/data/homework_cache.json ] || echo "{}" > /app/data/homework_cache.json

CMD ["python", "main.py"]