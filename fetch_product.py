"""Fetch one product from wearhongxiu.com WP (env credentials) + download its images.

Usage: python3 fetch_product.py <slug> [work_dir]

Env: WEARHONGXIU_WP_URL / WEARHONGXIU_WP_USER / WEARHONGXIU_WP_APP_PASSWORD
Writes: <work_dir>/product.json (title, style, categories, images[file,name,bg])
"""

import base64
import io
import json
import os
import sys
import urllib.parse
import urllib.request

from PIL import Image

def env_value(name, default=""):
    """Read env var and strip whitespace + wrapping quote/backslash sequences (Coolify escaping artifacts, e.g. \\"value\\")."""
    v = (os.environ.get(name) or default).strip()
    while len(v) >= 2 and v[0] in "\\\"'" and v[-1] in "\\\"'":
        v = v[1:-1].strip()
    return v


WP = env_value("WEARHONGXIU_WP_URL", "https://wearhongxiu.com").rstrip("/")
USER = env_value("WEARHONGXIU_WP_USER", "")
PW = env_value("WEARHONGXIU_WP_APP_PASSWORD", "")
AUTH = "Basic " + base64.b64encode(f"{USER}:{PW}".encode()).decode() if USER and PW else ""


def api(path, params=None):
    url = f"{WP}/wp-json/wp{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    headers = {"User-Agent": "hx-video-worker/1.0"}
    if AUTH:
        headers["Authorization"] = AUTH
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def corner_bg(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    pts = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    vals = []
    for x, y in pts:
        box = im.crop((max(0, x - 14), max(0, y - 14), min(w, x + 15), min(h, y + 15)))
        vals.append(box.resize((1, 1)).getpixel((0, 0)))
    return "rgb(%d,%d,%d)" % tuple(sum(v[i] for v in vals) // 4 for i in range(3))


def fetch(slug, out_dir, style_hint=None):
    os.makedirs(out_dir, exist_ok=True)
    prods = api("/v2/product", {"slug": slug, "status": "publish", "_fields": "id,title,link,featured_media,product_cat"})
    if not prods:
        raise SystemExit(f"product not found: {slug}")
    p = prods[0]

    fm = api(f"/v2/media/{p['featured_media']}", {"_fields": "id,source_url"})
    fname = fm["source_url"].rsplit("/", 1)[-1]
    derived = fname.rsplit("-", 1)[0] if "-" in fname else fname.rsplit(".", 1)[0]
    style = style_hint or derived

    cat_names = []
    if p.get("product_cat"):
        cats = api("/v2/product_cat", {"include": ",".join(str(c) for c in p["product_cat"]), "_fields": "id,name", "per_page": 20})
        cat_names = [c["name"] for c in cats]

    media = api("/v2/media", {"search": style, "per_page": 30, "media_type": "image", "_fields": "id,source_url"})

    downloaded = []
    for m in media:
        url = m["source_url"]
        if not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        dest = os.path.join(out_dir, url.rsplit("/", 1)[-1])
        if not os.path.exists(dest):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            with open(dest, "wb") as fh:
                fh.write(data)
        try:
            bg = corner_bg(dest)
        except Exception:  # noqa: BLE001
            bg = "rgb(251,248,245)"
        downloaded.append({"file": dest, "name": os.path.basename(dest), "bg": bg})

    payload = {
        "product_id": p["id"],
        "slug": slug,
        "title": p["title"]["rendered"],
        "link": p["link"],
        "style": style,
        "categories": cat_names,
        "images": downloaded,
    }
    with io.open(os.path.join(out_dir, "product.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    print(f"fetched {style}: {len(downloaded)} images")
    return payload


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: fetch_product.py <slug> [work_dir]")
    fetch(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "work")
