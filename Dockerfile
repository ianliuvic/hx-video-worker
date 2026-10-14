FROM mcr.microsoft.com/playwright:v1.55.0-jammy

ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PORT=3010 \
    NODE_OPTIONS=--max-old-space-size=1024 \
    DEBIAN_FRONTEND=noninteractive

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
      cron python3-pip ffmpeg tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
 && pip3 install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple pillow requests pg8000

WORKDIR /app

COPY package.json /app/package.json
RUN npm install --no-fund --no-audit

COPY . /app
RUN chmod +x /app/start.sh \
 && mkdir -p /app/work /app/output

# daily video batch at 09:00 Asia/Shanghai (one hour after the 1688 daily sync at 08:00)
# CRON_TZ makes the schedule independent of the container clock
RUN printf 'CRON_TZ=Asia/Shanghai\n0 9 * * * root cd /app && /usr/bin/python3 make_daily_videos.py >> /var/log/video-worker.log 2>&1\n' > /etc/cron.d/video-worker \
 && chmod 0644 /etc/cron.d/video-worker

EXPOSE 3010

CMD ["bash", "/app/start.sh"]
