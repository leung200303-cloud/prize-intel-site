// 直接用 Node 抓真數據（Node TLS 通，唔受 sandbox schannel 限制）
// 輸出：prize-intel/corpus/naming_results_crawl.jsonl
const https = require("https");
const fs = require("fs");
const path = require("path");

const OUT = path.join(__dirname, "..", "corpus", "naming_results_crawl.jsonl");

function get(url, depth = 0) {
  return new Promise((resolve, reject) => {
    https.get(url, { timeout: 30000, headers: { "User-Agent": "PrizeIntelBot/0.1 (beta data collection)", "Accept-Language": "ja" } }, res => {
      if ([301, 302, 307, 308].includes(res.statusCode) && depth < 5) {
        return resolve(get(res.headers.location, depth + 1));
      }
      if (res.statusCode !== 200) { res.resume(); return resolve(""); }
      let b = ""; res.setEncoding("utf8");
      res.on("data", d => (b += d));
      res.on("end", () => resolve(b));
    }).on("error", reject).on("timeout", function () { this.destroy(); reject(new Error("timeout")); });
  });
}

const strip = s => (s || "").replace(/<[^>]+>/g, " ")
  .replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#0?39;/g, "'")
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&nbsp;/g, " ")
  .replace(/\s+/g, " ").trim();

const rows = [];
const seen = new Set();

// ---------- bsp-prize：月別 schedule（官方商品名 + 發售日） ----------
const months = ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12"];
for (const m of months) {
  try {
    const html = await get(`https://bsp-prize.jp/schedule/?d=${m}`);
    const blocks = [...html.matchAll(/<div class="topProducts_item"[\s\S]*?<\/div>\s*<\/div>/g)].map(x => x[0]);
    const fallback = blocks.length ? blocks : [...html.matchAll(/<div class="topProducts_item"[\s\S]{0,900}?<\/div>/g)].map(x => x[0]);
    for (const b of fallback) {
      const u = (b.match(/href="(\/item\/\d+\/)"/) || [])[1];
      const n = strip((b.match(/class="topProducts_name"[^>]*>([\s\S]*?)<\/p>/) || [])[1]);
      const note = strip((b.match(/class="topProducts_note"[^>]*>([\s\S]*?)<\/p>/) || [])[1]);
      if (!u || !n) continue;
      const key = n + "|" + u;
      if (seen.has(key)) continue;
      seen.add(key);
      const dm = note.match(/(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日/);
      rows.push({ k: "bsp", n, d: dm ? `${dm[1]}-${String(dm[2]).padStart(2, "0")}-${String(dm[3]).padStart(2, "0")}` : "",
                  u: "https://bsp-prize.jp" + u });
    }
    console.log("bsp", m, "累計", rows.length);
  } catch (e) { console.log("bsp", m, "ERR", e.message); }
}

// ---------- 一番くじ：官方 lineup 月別頁 ----------
for (const m of [9, 10, 11, 12]) {
  try {
    const html = await get(`https://1kuji.com/products?sale_month=${m}&sale_year=2026`);
    for (const a of html.matchAll(/<a[^>]+href="(\/products\/[a-z0-9_\-]+)"[^>]*>([\s\S]*?)<\/a>/g)) {
      const href = a[1];
      if (seen.has(href)) continue;
      let text = strip(a[2]);
      if (text.length < 6) continue;
      const idx = text.indexOf("一番くじ");
      if (idx >= 0) text = text.slice(idx);
      text = text.replace(/(店頭販売|オンライン販売)[\s\S]*?予定/g, "").trim();
      if (text.length < 6) continue;
      seen.add(href);
      const dm = text.match(/(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日/);
      rows.push({ k: "kuji", n: text.slice(0, 100), d: dm ? `${dm[1]}-${String(dm[2]).padStart(2, "0")}-${String(dm[3]).padStart(2, "0")}` : "",
                  u: "https://1kuji.com" + href });
    }
    console.log("kuji", m, "累計", rows.length);
  } catch (e) { console.log("kuji", m, "ERR", e.message); }
}

// ---------- 輸出 JSONL（同 export_items.py 介面一致） ----------
const lines = rows.map(r => JSON.stringify({
  raw_title: r.n, official_name: r.n, is_kuji: r.k === "kuji",
  release_text: r.d, maker_jp: r.k === "bsp" ? "バンプレスト" : null,
  maker_code: r.k === "bsp" ? "bandai_spirits" : null, ip_title: null,
  size_cm: null, url: r.u,
}));
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, lines.join("\n"), "utf8");
console.log("wrote", OUT, lines.length, "筆");
