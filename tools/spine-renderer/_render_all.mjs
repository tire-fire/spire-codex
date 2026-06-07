// Render every card 1:1 via the live CardRender component, transparent bg.
// Neutralizes ancestor backgrounds and screenshots a clip rect expanded to
// include the orb/flame/banner overhang. Ancients get the 10-frame flame swap
// (animated). Temp tool.
import { chromium } from "playwright";
import fs from "fs";

const OUT = "/tmp/allcards";
fs.mkdirSync(OUT, { recursive: true });
const manifest = JSON.parse(fs.readFileSync("/tmp/cards_manifest.json", "utf8"));
const only = process.argv[2] ? new Set(process.argv[2].split(",")) : null;
const work = only ? manifest.filter((m) => only.has(m.id)) : manifest;
const CONC = parseInt(process.env.CONC || "4", 10);

// 10 ancient-flame frames as data URLs (same animation for every ancient).
const flame = [];
for (let i = 0; i < 10; i++) {
  const b = fs.readFileSync(`/tmp/flame_frames/f_0${i}.png`);
  flame.push("data:image/png;base64," + b.toString("base64"));
}

async function ready(page) {
  const card = page.locator(".relative.select-none").first();
  await card.waitFor({ state: "visible", timeout: 20000 });
  // Point card-frame assets at the LOCAL backend (which has the freshly
  // re-extracted banners/flame) instead of the CDN, so previews reflect local
  // changes without an R2 upload.
  await page.evaluate(() => {
    for (const im of document.querySelectorAll('img[src*="/card-frames/"]')) {
      im.src = im.src.replace(/^https?:\/\/[^/]+\/(?:static\/images\/)?card-frames\//,
        "http://localhost:8000/static/images/card-frames/");
    }
  });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => {
    const c = document.querySelector(".relative.select-none");
    if (!c) return false;
    return [...c.querySelectorAll("img")].every((i) => i.complete && i.naturalWidth > 0);
  }, { timeout: 20000 }).catch(() => {});
}

// Move the card out of the page into a clean transparent body so NO page
// chrome (nav, container border, tabs) can bleed in. Done last, right before
// the screenshot. Returns nothing; screenshot the #__w wrapper after.
async function isolate(page, ancient) {
  await page.evaluate((ancient) => {
    const card = document.querySelector(".relative.select-none");
    const wrap = document.createElement("div");
    wrap.id = "__w";
    const padTop = ancient ? 42 : 22; // ancients need flame-overhang room
    wrap.style.cssText = `display:inline-block;padding:${padTop}px 20px 12px 20px;background:transparent`;
    wrap.appendChild(card); // detaches from React; we screenshot immediately
    document.documentElement.style.cssText = "background:transparent";
    document.body.style.cssText = "margin:0;background:transparent";
    document.body.replaceChildren(wrap);
    window.scrollTo(0, 0);
  }, ancient);
}

async function shotEl(page, path) {
  await page.locator("#__w").screenshot({ path, omitBackground: true });
}

async function animated(page, name) {
  const h = await page.locator('#__w img[src*="ancient_flame"]').first().elementHandle();
  for (let i = 0; i < 10; i++) {
    await h.evaluate((el, src) => { el.src = src; }, flame[i]);
    await page.waitForTimeout(25);
    await shotEl(page, `${OUT}/${name}.f${i}.png`);
  }
}

// Toggle the upgrade view via a direct JS click (no Playwright auto-scroll,
// which would shift the sticky nav over the card).
async function toggleUpgrade(page) {
  const clicked = await page.evaluate(() => {
    const b = document.querySelector('button[title="Show upgraded"]');
    if (!b) return false;
    b.click();
    return true;
  });
  if (clicked) await page.waitForTimeout(260);
  return clicked;
}

async function renderOne(page, m) {
  await page.goto(`http://localhost:3000/cards/${m.id}`, { waitUntil: "domcontentloaded" });
  await ready(page);
  // upgraded first (needs the in-page toggle), captured on a second load.
  await isolate(page, m.ancient);
  if (m.ancient) await animated(page, m.id);
  else await shotEl(page, `${OUT}/${m.id}.png`);
  if (m.upg) {
    await page.goto(`http://localhost:3000/cards/${m.id}`, { waitUntil: "domcontentloaded" });
    await ready(page);
    if (await toggleUpgrade(page)) {
      await ready(page);
      await isolate(page, m.ancient);
      if (m.ancient) await animated(page, `${m.id}_upg`);
      else await shotEl(page, `${OUT}/${m.id}_upg.png`);
    }
  }
}

const browser = await chromium.launch({ args: ["--no-sandbox"] });
let done = 0;
const queue = [...work];
async function worker() {
  const ctx = await browser.newContext({ viewport: { width: 480, height: 760 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  while (queue.length) {
    const m = queue.shift();
    try { await renderOne(page, m); }
    catch (e) { console.log(`ERR ${m.id}: ${e.message.split("\n")[0]}`); }
    done++;
    if (done % 25 === 0) console.log(`${done}/${work.length}`);
  }
  await ctx.close();
}
await Promise.all(Array.from({ length: CONC }, () => worker()));
await browser.close();
console.log(`rendered ${done} cards -> ${OUT}`);
