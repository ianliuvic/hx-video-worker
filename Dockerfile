FROM mcr.microsoft.com/playwright:v1.55.0-jammy

ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PORT=3010 \
    NODE_OPTIONS=--max-old-space-size=1024 \
    DEBIAN_FRONTEND=noninteractive

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
      python3-pip ffmpeg tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
 && pip3 install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple pillow requests pg8000

WORKDIR /app

COPY package.json /app/package.json
RUN npm install --no-fund --no-audit

COPY . /app
RUN chmod +x /app/start.sh \
 && mkdir -p /app/work /app/output

EXPOSE 3010

CMD ["bash", "/app/start.sh"]
