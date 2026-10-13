// Render the "daily new product" video frames for one product (1080x1920 @ 30fps, ~13.2s).
// Usage: node render_frames.mjs <workDir> <framesDir> [pick1,pick2,pick3]
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const HERE = path.dirname(fileURLToPath(import.meta.url));

const WORK = process.argv[2];
const FRAMES = process.argv[3];
const picksArg = process.argv[4] || "";

const product = JSON.parse(fs.readFileSync(path.join(WORK, "product.json"), "utf8"));

// per-product scene copy: optional work/lines.json overrides the defaults
let L = {
  s2t: "Made to move with you.",
  s2n: "Reorder in days, not months",
  s3t: "Ready for your racks.",
  s3n: "2,000+ styles, one supplier",
  s3badge: "IN STOCK",
};
const linesPath = path.join(WORK, "lines.json");
if (fs.existsSync(linesPath)) {
  try {
    Object.assign(L, JSON.parse(fs.readFileSync(linesPath, "utf8")));
    console.log("lines:", JSON.stringify(L));
  } catch (e) {
    console.log("lines.json ignored:", String(e).slice(0, 120));
  }
}

const byName = {};
for (const im of product.images) byName[im.name] = { file: im.file.replace(/\\/g, "/"), bg: im.bg || "rgb(251,248,245)" };
const available = Object.keys(byName);
let picks = picksArg ? picksArg.split(",").map((s) => s.trim()).filter((k) => byName[k]) : [];
if (picks.length < 3) {
  const sorted = available.sort();
  picks = [sorted[1], sorted[Math.floor(sorted.length / 2)], sorted[sorted.length - 2]].filter(Boolean);
}
const imgs = picks.slice(0, 3).map((k) => "file:///" + byName[k].file);
const bgOf = (k) => byName[k].bg;
const rgba = (c, a) => c.replace("rgb(", "rgba(").replace(")", `,${a})`);

fs.mkdirSync(FRAMES, { recursive: true });
for (const f of fs.readdirSync(FRAMES)) fs.unlinkSync(path.join(FRAMES, f));

const FPS = 30;
const DURATION = 13.2;
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const title = esc(product.title || "");
const style = esc(product.style || "");
const cats = (product.categories || []).filter((c) => !/women swimwear|factory quality|best sellers/i.test(c));
const setCat = cats.find((c) => /set|three-piece/i.test(c));
const catLabel = esc((setCat || cats[0] || "SWIMWEAR").toUpperCase());
const now = new Date();
const dateStr = esc(now.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }).toUpperCase());

const LOGO_L = "file://" + path.join(HERE, "assets", "hongxiu-logo-light.png").replace(/\\/g, "/");
const LOGO_D = "file://" + path.join(HERE, "assets", "hongxiu-logo-dark.png").replace(/\\/g, "/");

const FONT_FILE = path.join(HERE, "assets", "fonts", "montserrat-latin-var.woff2");
const FONTS = fs.existsSync(FONT_FILE)
  ? `<style>@font-face{font-family:'Montserrat';font-style:normal;font-weight:600 900;font-display:block;src:url('file://${FONT_FILE.replace(/\\/g, "/")}') format('woff2')}</style>`
  : `<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800;900&display=swap" rel="stylesheet">`;

// timeline seconds
const T = { introIn: 0.15, photoStart: 2.0, photoLen: 2.6, xfade: 0.4, outroStart: 9.8, end: 13.2 };
const p2 = T.photoStart + T.photoLen - T.xfade / 2;
const p3 = T.photoStart + (T.photoLen - T.xfade / 2) * 2;

const html = `<!doctype html><html><head><meta charset="utf-8">${FONTS}<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1920px;overflow:hidden;font-family:'Montserrat',Arial,sans-serif;-webkit-font-smoothing:antialiased}
.scene{position:absolute;inset:0}
img{display:block}
.fitx{white-space:nowrap}
/* ---------- intro ---------- */
#intro{background:#a02025;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:0}
#intro .glow{position:absolute;inset:0;background:radial-gradient(60% 42% at 50% 42%, rgba(255,255,255,.10), rgba(255,255,255,0) 70%)}
#intro .logo{height:96px;margin-bottom:56px}
#intro .eyebrow{color:#f3c9cd;font-size:32px;font-weight:800;letter-spacing:.42em;text-transform:uppercase}
#intro h1{color:#fff;font-size:132px;font-weight:900;line-height:.98;letter-spacing:-.02em;text-align:center;margin-top:26px}
#intro .rule{width:120px;height:10px;background:#fff;margin:44px 0 40px}
#intro .chip{background:#fff;color:#a02025;font-size:38px;font-weight:900;letter-spacing:.14em;padding:20px 44px}
#intro .cat{color:#f6dce0;font-size:30px;font-weight:700;letter-spacing:.3em;margin-top:34px;text-transform:uppercase}
/* ---------- photos ---------- */
.photo{opacity:0;overflow:hidden}
.photo img{width:100%;height:100%;object-fit:contain;transform-origin:50% 42%}
.photo .shade{position:absolute;left:0;right:0;bottom:0;height:48%}
.photo .info{position:absolute;left:0;right:0;bottom:0;padding:0 84px 96px}
.photo .chip{display:inline-block;background:#a02025;color:#fff;font-size:30px;font-weight:900;letter-spacing:.1em;padding:14px 30px}
.photo .ttl{color:#17181c;font-size:56px;font-weight:900;line-height:1.1;margin-top:26px;max-width:900px}
.photo .note{display:inline-flex;align-items:center;gap:14px;margin-top:28px;font-size:31px;font-weight:800;color:#3c3f45}
.photo .note::before{content:"";width:11px;height:11px;border-radius:50%;background:#a02025;flex:none}
.photo .wm{position:absolute;right:76px;top:84px;height:58px;width:auto;object-fit:contain}
.photo .cap{position:absolute;left:84px;top:150px;background:#17181c;color:#fff;font-size:26px;font-weight:800;letter-spacing:.16em;padding:12px 24px}
/* ---------- outro ---------- */
#outro{background:#fbf8f5;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}
#outro .logo{height:104px;margin-bottom:54px}
#outro .word{color:#17181c;font-size:56px;font-weight:900;letter-spacing:.16em}
#outro .rule{width:96px;height:8px;background:#a02025;margin:44px 0}
#outro .pts{display:grid;gap:14px}
#outro .prow{display:flex;align-items:center;gap:18px;justify-content:center;font-size:30px;font-weight:800;color:#3c3f45}
#outro .dota{width:9px;height:9px;border-radius:50%;background:#a02025}
#outro .url{margin-top:56px;color:#a02025;font-size:44px;font-weight:900;letter-spacing:.02em}
#outro .daily{display:inline-block;margin-top:36px;border:2px solid #a02025;color:#a02025;font-size:27px;font-weight:900;letter-spacing:.26em;padding:16px 34px}
</style></head><body>

<div class="scene" id="intro">
  <div class="glow"></div>
  <img class="logo fit" src="${LOGO_D}" alt="">
  <div class="eyebrow fit">Today's New</div>
  <h1>NEW<br>ARRIVAL</h1>
  <div class="rule"></div>
  <div class="chip fit">STYLE ${style}</div>
  <div class="cat fit">${dateStr} &nbsp;·&nbsp; ${catLabel}</div>
</div>

<div class="scene photo" id="ph1" style="background:${bgOf(picks[0])}">
  <img src="${imgs[0]}" alt="">
  <div class="shade" style="background:linear-gradient(180deg, ${rgba(bgOf(picks[0]), 0)} 0%, ${rgba(bgOf(picks[0]), .92)} 62%, ${bgOf(picks[0])} 100%)"></div>
  <div class="info">
    <span class="chip fit">${style}</span>
    <div class="ttl">${title}</div>
    <div class="note fit">Ready stock · No MOQ</div>
  </div>
  <img class="wm" src="${LOGO_L}" alt="">
</div>

<div class="scene photo" id="ph2" style="background:${bgOf(picks[1])}">
  <img src="${imgs[1]}" alt="">
  <div class="shade" style="background:linear-gradient(180deg, ${rgba(bgOf(picks[1]), 0)} 0%, ${rgba(bgOf(picks[1]), .92)} 62%, ${bgOf(picks[1])} 100%)"></div>
  <div class="info">
    <span class="chip fit">${style}</span>
    <div class="ttl">${L.s2t.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</div>
    <div class="note fit">${L.s2n.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</div>
  </div>
  <img class="wm" src="${LOGO_L}" alt="">
</div>

<div class="scene photo" id="ph3" style="background:${bgOf(picks[2])}">
  <img src="${imgs[2]}" alt="">
  <div class="shade" style="background:linear-gradient(180deg, ${rgba(bgOf(picks[2]), 0)} 0%, ${rgba(bgOf(picks[2]), .92)} 62%, ${bgOf(picks[2])} 100%)"></div>
  <span class="cap fit">${L.s3badge}</span>
  <div class="info">
    <span class="chip fit">${style}</span>
    <div class="ttl">${L.s3t.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</div>
    <div class="note fit">${L.s3n.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</div>
  </div>
  <img class="wm" src="${LOGO_L}" alt="">
</div>

<div class="scene" id="outro">
  <img class="logo fit" src="${LOGO_L}" alt="">
  <div class="word fit">WHOLESALE SWIMWEAR</div>
  <div class="rule"></div>
  <div class="pts">
    <div class="prow"><b>2,000+ STYLES</b><i class="dota"></i><b>NO MOQ</b></div>
    <div class="prow"><b>FACTORY PRICES</b><i class="dota"></i><b>SHIPS WORLDWIDE</b></div>
  </div>
  <div class="url fit">wearhongxiu.com</div>
  <span class="daily fit">NEW STYLES DAILY</span>
</div>

<script>
const T = ${JSON.stringify(T)};
const p2 = T.photoStart + T.photoLen - T.xfade / 2;
const p3 = T.photoStart + (T.photoLen - T.xfade / 2) * 2;
const A = [];
function run(el, kf, opt) {
  const a = el.animate(kf, Object.assign({ fill: "both", easing: "linear" }, opt));
  a.pause();
  A.push(a);
  return a;
}
function fadeSlide(el, t0, t1, dy) {
  run(el, [
    { opacity: 0, transform: "translateY(" + (dy || 40) + "px)" },
    { opacity: 1, transform: "translateY(0px)" },
  ], { delay: t0 * 1000, duration: (t1 - t0) * 1000, easing: "cubic-bezier(.2,.7,.2,1)" });
}
const q = (s) => document.querySelector(s);

// intro
run(q("#intro"), [{ opacity: 1 }, { opacity: 1 }], { delay: 0, duration: T.photoStart * 1000 });
run(q("#intro"), [{ opacity: 1 }, { opacity: 0 }], { delay: (T.photoStart - 0.45) * 1000, duration: 450 });
fadeSlide(q("#intro .logo"), T.introIn, T.introIn + 0.6, 30);
fadeSlide(q("#intro .eyebrow"), T.introIn + 0.15, T.introIn + 0.75, 30);
fadeSlide(q("#intro h1"), T.introIn + 0.3, T.introIn + 1.0, 44);
fadeSlide(q("#intro .rule"), T.introIn + 0.5, T.introIn + 1.1, 20);
fadeSlide(q("#intro .chip"), T.introIn + 0.6, T.introIn + 1.2, 24);
fadeSlide(q("#intro .cat"), T.introIn + 0.75, T.introIn + 1.35, 24);

// photos: each fades in/out; img slow zoom
[[q("#ph1"), T.photoStart], [q("#ph2"), p2], [q("#ph3"), p3]].forEach(([el, t0], i) => {
  const inD = 0.5, outD = 0.45;
  run(el, [{ opacity: 0 }, { opacity: 1 }], { delay: t0 * 1000, duration: inD * 1000 });
  run(el, [{ opacity: 1 }, { opacity: 1 }], { delay: (t0 + inD) * 1000, duration: (T.outroStart - t0 - inD) * 1000, fill: "none" });
  run(el, [{ opacity: 1 }, { opacity: 0 }], { delay: T.outroStart * 1000, duration: outD * 1000, fill: "forwards" });
  const img = el.querySelector("img");
  run(img, [
    { transform: i % 2 === 0 ? "scale(1.0)" : "scale(1.015)" },
    { transform: i % 2 === 0 ? "scale(1.035)" : "scale(1.05)" },
  ], { delay: t0 * 1000, duration: (T.outroStart - t0) * 1000 });
  fadeSlide(el.querySelector(".info"), t0 + 0.25, t0 + 0.75, 46);
  fadeSlide(el.querySelector(".wm"), t0 + 0.45, t0 + 0.9, 20);
  const cap = el.querySelector(".cap");
  if (cap) fadeSlide(cap, t0 + 0.35, t0 + 0.85, 20);
});

// outro
run(q("#outro"), [{ opacity: 0 }, { opacity: 1 }], { delay: (T.outroStart - 0.2) * 1000, duration: 0.6 * 1000 });
fadeSlide(q("#outro .logo"), T.outroStart + 0.1, T.outroStart + 0.7, 34);
fadeSlide(q("#outro .word"), T.outroStart + 0.3, T.outroStart + 0.9, 30);
fadeSlide(q("#outro .rule"), T.outroStart + 0.5, T.outroStart + 1.1, 20);
fadeSlide(q("#outro .pts"), T.outroStart + 0.65, T.outroStart + 1.3, 30);
fadeSlide(q("#outro .url"), T.outroStart + 0.9, T.outroStart + 1.5, 30);
fadeSlide(q("#outro .daily"), T.outroStart + 1.1, T.outroStart + 1.7, 24);

window.__seek = (t) => {
  const ms = t * 1000;
  for (const a of document.getAnimations()) {
    a.pause();
    a.currentTime = ms;
  }
};
</script>
</body></html>`;

const htmlPath = path.join(WORK, "_video.html");
fs.writeFileSync(htmlPath, html, "utf8");

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"] });
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
await page.goto("file:///" + htmlPath.replace(/\\/g, "/"), { waitUntil: "load", timeout: 60000 });
await page.evaluate(async () => {
  await document.fonts.ready;
  await Promise.all(Array.from(document.images).map((i) => (i.complete ? null : new Promise((r) => { i.onload = r; i.onerror = r; }))));
});

const total = Math.round(DURATION * FPS);
console.log("frames:", total, "| picks:", picks.join(" | "));
for (let f = 0; f < total; f++) {
  const t = f / FPS;
  await page.evaluate((tt) => window.__seek(tt), t);
  await page.screenshot({ path: path.join(FRAMES, String(f).padStart(4, "0") + ".jpg"), type: "jpeg", quality: 92 });
  if (f % 60 === 0) console.log("  frame", f, "/", total);
}
console.log("frames done");
await browser.close();
