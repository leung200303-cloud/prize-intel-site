// 抓 コレトレ 文章頁 spec 表（真 official_name／size／maker）— 全 server-side
const https = await import("node:https");
const fs = await import("node:fs");
const path = await import("node:path");

const OUT = path.join(process.cwd(), "prize-intel", "corpus", "naming_results_kore.jsonl");

function get(url, depth = 0) {
  return new Promise((resolve, reject) => {
    https.default.get(url, { timeout: 30000, headers: { "User-Agent": "PrizeIntelBot/0.1", "Accept-Language": "ja" } }, res => {
      if ([301, 302, 307, 308].includes(res.statusCode) && depth < 5) return resolve(get(res.headers.location, depth + 1));
      if (res.statusCode !== 200) { res.resume(); return resolve(""); }
      let b = ""; res.setEncoding("utf8"); res.on("data", d => (b += d)); res.on("end", () => resolve(b));
    }).on("error", reject).on("timeout", function () { this.destroy(); reject(new Error("timeout")); });
  });
}
const strip = s => (s || "").replace(/<[^>]+>/g, " ")
  .replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#0?39;/g, "'").replace(/&nbsp;/g, " ")
  .replace(/\s+/g, " ").trim();

const listHtml = await get("https://kore-tore.com/prize-latest-figure/");
const links = [...new Set([...listHtml.matchAll(/href="(https:\/\/kore-tore\.com\/[a-z0-9\-]+\/)"/g)]
  .map(m => m[1]).filter(u => !/(prize-latest|about-our|privacy|inquiry|feed|category)/.test(u)))];
console.log("文章數:", links.length);

const rows = [];
for (const u of links.slice(0, 24)) {
  try {
    const html = await get(u);
    const h1 = strip((html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/) || [])[1]);
    const spec = {};
    for (const m of html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)) {
      const cells = [...m[1].matchAll(/<(th|td)[^>]*>([\s\S]*?)<\/\1>/g)].map(c => strip(c[2]));
      if (cells.length >= 2 && cells[0]) spec[cells[0]] = cells[1];
    }
    const name = spec["商品名"];
    if (!name) { console.log("skip(no name)", u.slice(-40)); continue; }
    const dm = (html.match(/(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日/) || []);
    const date = dm.length ? `${dm[1]}-${String(dm[2]).padStart(2, "0")}-${String(dm[3]).padStart(2, "0")}` : "";
    const sizeText = spec["サイズ"] || "";
    const sm = sizeText.match(/(\d+(?:\.\d+)?)\s*cm/g) || [];
    const sizes = sm.map(x => parseFloat(x)).sort((a, b) => b - a);
    rows.push({ raw_title: h1 || name, official_name: name, is_kuji: false,
      release_text: date, maker_jp: spec["メーカー"] || null, maker_code: null,
      ip_title: spec["作品名"] || null, size_text: sizeText || null,
      size_cm: sizes.length ? sizes[0] : null, url: u });
  } catch (e) { console.log("ERR", u.slice(-40), e.message); }
}

fs.writeFileSync(OUT, rows.map(r => JSON.stringify(r)).join("\n"), "utf8");
console.log("wrote", OUT, rows.length, "筆");
