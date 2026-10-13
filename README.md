# hx-video-worker

每日新品视频 Worker（Coolify 部署）：从当日发布到 wearhongxiu.com 的产品中随机选 ≤5 个，
每个生成一条 13.2s / 1080×1920 / 含品牌配乐的视频，通过飞书发送（不展示价格）。

## 运行链路

```
1688 每日采集任务 (08:00 Asia/Shanghai)
        │  +1 小时
        ▼
本容器 cron (09:00 Asia/Shanghai)
  make_daily_videos.py
    ├─ WP 查询：今日发布的产品（after=今天00:00）
    ├─ 随机取 ≤5 个（VIDEO_MAX_PER_DAY）
    ├─ fetch_product.py  → 取标题/类目/图片（全部来自 WP 媒体库）
    ├─ render_frames.mjs → 396 帧（Playwright/Chromium，本地字体）
    ├─ ffmpeg            → H.264 + 品牌音乐
    └─ 飞书              → 上传素材 + 发视频消息 + 汇总文本
```

## 环境变量（Coolify 配置）

| Key | 说明 |
|---|---|
| `WEARHONGXIU_WP_URL` / `WEARHONGXIU_WP_USER` / `WEARHONGXIU_WP_APP_PASSWORD` | WP REST 凭据 |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书应用 |
| `FEISHU_CHAT_ID` | 接收群（chat_id） |
| `VIDEO_MAX_PER_DAY` | 每日上限，默认 5 |

## 手动执行

```bash
docker exec <container> python3 /app/make_daily_videos.py
```

日志：容器内 `/var/log/video-worker.log`；产物：`/app/output/*.mp4`（可选挂载卷或上传 R2）。
