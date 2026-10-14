"""Daily batch: pick up to N products published to WP today, render one video each, send to Feishu.

Env:
  WEARHONGXIU_WP_URL / WEARHONGXIU_WP_USER / WEARHONGXIU_WP_APP_PASSWORD
  FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_CHAT_ID   (chat_id target)
  VIDEO_MAX_PER_DAY (default 5), TZ assumed Asia/Shanghai for "today"

Flow: WP query -> random pick -> fetch images -> render 396 frames -> ffmpeg mux
      -> Feishu upload + media message -> summary text.
"""

import datetime
import glob
import io
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.parse

import requests

try:
    import pg8000.dbapi as pgdb
except Exception:  # noqa: BLE001
    pgdb = None

APP_DIR = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(APP_DIR, "work")
FRAMES = os.path.join(WORK, "frames")
OUT = os.path.join(APP_DIR, "output")
MUSIC = os.path.join(APP_DIR, "assets", "music-brand.mp3")
RENDER = os.path.join(APP_DIR, "render_frames.mjs")

MAX_PER_DAY = int(os.environ.get("VIDEO_MAX_PER_DAY", "5").strip().strip('"').strip("'") or "5")
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "").strip().strip('"').strip("'")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "").strip().strip('\\"').strip("'")
FEISHU_CHAT_ID = os.environ.get("FEISHU_CHAT_ID", "").strip().strip('"').strip("'")
TZ = datetime.timezone(datetime.timedelta(hours=8))

sys.path.insert(0, APP_DIR)
from fetch_product import fetch, api  # noqa: E402


# ---------- Feishu ----------
def feishu_token():
    r = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    if d.get("code") != 0:
        raise RuntimeError(f"feishu token failed: {d}")
    return d["tenant_access_token"]


def feishu_send_media(token, mp4_path, file_name):
    with open(mp4_path, "rb") as fh:
        r = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"file_type": "mp4", "file_name": file_name},
            files={"file": (file_name, fh, "video/mp4")},
            timeout=180,
        )
    d = r.json()
    if d.get("code") != 0:
        raise RuntimeError(f"feishu upload failed: {d}")
    file_key = d["data"]["file_key"]
    r2 = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        params={"receive_id_type": "chat_id"},
        json={"receive_id": FEISHU_CHAT_ID, "msg_type": "media", "content": json.dumps({"file_key": file_key})},
        timeout=60,
    )
    d2 = r2.json()
    if d2.get("code") != 0:
        raise RuntimeError(f"feishu send failed: {d2}")
    return d2["data"].get("message_id")


def feishu_send_text(token, text):
    requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        params={"receive_id_type": "chat_id"},
        json={"receive_id": FEISHU_CHAT_ID, "msg_type": "text", "content": json.dumps({"text": text})},
        timeout=60,
    )


# ---------- pipeline helpers ----------
def todays_products():
    start = datetime.datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    after = start.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return api("/v2/product", {
        "after": after, "per_page": 50, "orderby": "date", "order": "desc",
        "_fields": "id,slug,title,link,date",
    })


def todays_from_collector_db():
    """Authoritative selection: products FIRST PUBLISHED to WP today (CN),
    from the 1688 collector database. Returns None when the DB is unavailable."""
    dsn = env_value("DATABASE_URL")
    if not dsn or pgdb is None:
        return None
    u = urllib.parse.urlparse(dsn)
    conn = pgdb.connect(
        user=u.username, password=u.password, host=u.hostname,
        port=u.port or 5432, database=(u.path or "/").lstrip("/"), timeout=30,
    )
    try:
        cur = conn.cursor()
        cur.execute(
            """
            select p.style_no, p.wp_post_id, to_char(p.first_published_at at time zone 'Asia/Shanghai', 'HH24:MI')
            from product_wordpress_publications p
            where p.wp_status = 'publish'
              and p.wp_post_id is not null
              and (coalesce(p.first_published_at, p.created_at) at time zone 'Asia/Shanghai')::date
                  = (now() at time zone 'Asia/Shanghai')::date
            order by p.first_published_at desc nulls last
            """
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [{"style": r[0], "post_id": r[1], "at": r[2]} for r in rows]


def pick_images(product):
    """Lowest-numbered shots first (hero/model shots), up to 3."""
    style = product["style"]

    def key(it):
        nums = [int(x) for x in re.findall(r"\d+", it["name"].replace(style, "", 1))[:2]]
        return nums or [999, 999]

    return [it["name"] for it in sorted(product["images"], key=key)[:3]]


def render_video(slug, product):
    picks = pick_images(product)
    if len(picks) < 3:
        picks = picks + [product["images"][i]["name"] for i in range(min(3, len(product["images"]))) if product["images"][i]["name"] not in picks][: 3 - len(picks)]
    r = subprocess.run(
        ["node", RENDER, WORK, FRAMES, ",".join(picks)],
        cwd=APP_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    print((r.stdout or "")[-300:])
    if r.returncode != 0:
        raise RuntimeError("render failed: " + (r.stderr or "")[-400:])

    stamp = datetime.datetime.now(TZ).date().isoformat()
    out_mp4 = os.path.join(OUT, f"{product['style']}-{stamp}.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", "30", "-i", os.path.join(FRAMES, "%04d.jpg"),
        "-i", MUSIC,
        "-filter_complex", "[0:v]format=yuv420p[v]",
        "-map", "[v]", "-map", "1:a",
        "-af", "afade=t=in:st=0:d=0.5,afade=t=out:st=11.9:d=1.3,volume=0.85",
        "-c:v", "libx264", "-crf", "19", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-t", "13.2", "-movflags", "+faststart", out_mp4,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_mp4


def cleanup():
    for pat in (os.path.join(WORK, "*"),):
        for f in glob.glob(pat):
            if os.path.isfile(f):
                os.remove(f)
    for f in glob.glob(os.path.join(FRAMES, "*")):
        os.remove(f)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)

    # selection: collector DB first (products first published to WP today),
    # WP publish-date query only as fallback (collector backdates WP post dates).
    candidates = []
    try:
        rows = todays_from_collector_db()
        if rows is not None:
            candidates = [{"post_id": r["post_id"], "style": r["style"], "at": r["at"]} for r in rows]
            print(f"collector db: {len(candidates)} product(s) first published today")
        else:
            print("collector db unavailable; falling back to WP date query")
            candidates = [{"post_id": p["id"], "style": None} for p in todays_products()]
    except Exception as exc:  # noqa: BLE001
        print(f"selection failed: {str(exc)[:200]}")
        if FEISHU_APP_ID and FEISHU_CHAT_ID:
            try:
                feishu_send_text(feishu_token(), f"⚠️ 新品视频任务：选品失败\n{str(exc)[:180]}")
            except Exception:  # noqa: BLE001
                pass
        return 1

    if not candidates:
        print("no products first published today; nothing to do")
        return 0

    random.shuffle(candidates)
    chosen = candidates[:MAX_PER_DAY]
    print(f"picked {len(chosen)} of {len(candidates)}: " + ", ".join(str(c.get('style') or c.get('post_id')) for c in chosen))

    token = feishu_token() if (FEISHU_APP_ID and FEISHU_CHAT_ID) else None
    done, failed = [], []

    for c in chosen:
        try:
            cleanup()
            prod = api(f"/v2/product/{c['post_id']}", {"_fields": "id,slug,title,link"})
            slug = prod["slug"]
            product = fetch(slug, WORK)
            mp4 = render_video(slug, product)
            size_mb = os.path.getsize(mp4) / 1024 / 1024
            if token:
                feishu_send_media(token, mp4, os.path.basename(mp4))
            done.append(f"{product['style']} ({size_mb:.1f}MB)")
            print(f"OK {product['style']} -> {mp4}")
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{c.get('style') or c.get('post_id')}: {str(exc)[:120]}")
            print(f"FAIL {c.get('style') or c.get('post_id')}: {exc}")

    if token:
        lines = [f"今日新品视频：{len(done)}/{len(chosen)} 条"]
        if done:
            lines.append("✅ " + "、".join(done))
        if failed:
            lines.append("⚠️ 失败：" + "；".join(failed))
        feishu_send_text(token, "\n".join(lines))

    cleanup()
    print(f"batch done: {len(done)} ok, {len(failed)} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
