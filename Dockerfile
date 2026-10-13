FROM mcr.microsoft.com/playwright:v1.55.0-jammy

ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PORT=3010 \
    NODE_OPTIONS=--max-old-space-size=1024

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
 && apt-get update \
 && apt-get install -y --no-install-recommends cron python3-pip ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && pip3 install --no-cache-dir pillow requests

WORKDIR /app

COPY package.json /app/package.json
RUN npm install --no-fund --no-audit

COPY . /app
RUN chmod +x /app/start.sh \
 && mkdir -p /app/work /app/output

# daily video batch at 09:00 Asia/Shanghai (one hour after the 1688 daily sync at 08:00)
RUN printf '0 9 * * * root cd /app && /usr/bin/python3 make_daily_videos.py >> /var/log/video-worker.log 2>&1\n' > /etc/cron.d/video-worker \
 && chmod 0644 /etc/cron.d/video-worker

EXPOSE 3010

CMD ["bash", "/app/start.sh"]
