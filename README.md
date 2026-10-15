# hx-video-worker

每日新品视频 Worker（Coolify 部署）：从当日发布到 wearhongxiu.com 的产品中随机选 ≤5 个，
每个生成一条 13.2s / 1080×1920 / 含品牌配乐的视频，通过飞书发送（不展示价格）。

## 运行链路

```
Coolify 调度器任务「1688 新品视频生成」(09:00 Asia/Shanghai)
        │  调度器 → dsh worker agent → curl POST /run
        ▼
本容器 (hx-video-worker)
  health_server.py 收到 /run（Bearer 令牌校验、当日幂等）
    ├─ 启动 make_daily_videos.py（继承容器完整环境变量）
    │    ├─ 采集器数据库：今日首发到 WP 的产品（first_published_at）
    │    ├─ 随机取 ≤5 个（VIDEO_MAX_PER_DAY）
    │    ├─ fetch_product.py  → 取标题/类目/图片（全部来自 WP 媒体库）
    │    ├─ render_frames.mjs → 396 帧（Playwright/Chromium，本地字体）
    │    ├─ ffmpeg            → H.264 + 品牌音乐
    │    └─ 飞书              → 上传素材 + 发视频消息 + 汇总文本
    └─ 状态写入 /app/output/.state.json（同日重复触发会跳过，?force=1 强制）
```

## 环境变量（Coolify 配置）

| Key | 说明 |
|---|---|
| `WEARHONGXIU_WP_URL` / `WEARHONGXIU_WP_USER` / `WEARHONGXIU_WP_APP_PASSWORD` | WP REST 凭据 |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书应用 |
| `FEISHU_CHAT_ID` | 接收群（chat_id） |
| `DATABASE_URL` | 采集器 PostgreSQL（读取今日首发记录） |
| `VIDEO_WORKER_TOKEN` | 触发接口令牌（与 dsh-worker 中的同名变量一致） |
| `VIDEO_MAX_PER_DAY` | 每日上限，默认 5 |

## 手动触发 / 查看状态

```bash
curl -X POST -H "Authorization: Bearer $VIDEO_WORKER_TOKEN" http://<本应用域名>/run
curl -H "Authorization: Bearer $VIDEO_WORKER_TOKEN" http://<本应用域名>/status
```

日志：容器内 `/app/output/run-*.log`；产物：`/app/output/*.mp4`。

