/* ui_inventory.js — 盤點優先（inventory-first）
 * 用法：喺 Chrome DevTools Console 貼呢個檔，然後：
 *   __ui()          → 印出當前頁面所有可互動元件（index|tag|label|x|y）
 *   __ui.click(3)   → 撳第 3 個（用清單入面嘅 index，唔靠猜圖標）
 *   __ui.find('copy') → 按 label 關鍵字搵 index
 * 規則：先盤點、後配對、最後先發 HID / JS 點擊。
 */
window.__ui = (() => {
  const SEL = 'button,a[href],input,select,textarea,[role="button"],[onclick],summary';
  const seen = new Set();
  const inv = () => {
    const rows = [];
    document.querySelectorAll(SEL).forEach((e) => {
      const b = e.getBoundingClientRect();
      if (b.width < 5 || b.height < 5) return;
      if (b.bottom < 0 || b.top > innerHeight) return;
      const label = (e.innerText || e.value || e.getAttribute('aria-label') || e.title || '').trim().replace(/\s+/g, ' ').slice(0, 24);
      const key = Math.round(b.x) + ',' + Math.round(b.y) + ',' + label;
      if (seen.has(key)) return; seen.add(key);
      rows.push({ i: rows.length, tag: e.tagName.toLowerCase(), label,
        x: Math.round(b.x + b.width / 2), y: Math.round(b.y + b.height / 2), el: e });
    });
    return rows;
  };
  const api = () => {
    seen.clear();
    const rows = inv();
    return rows.map((r) => [r.i, r.tag, r.label, r.x, r.y].join('|')).join('\n');
  };
  api.rows = () => { seen.clear(); return inv(); };
  api.find = (kw) => { const k = kw.toLowerCase(); const rows = api.rows(); return rows.filter((r) => r.label.toLowerCase().includes(k)).map((r) => r.i + '|' + r.tag + '|' + r.label + '|' + r.x + '|' + r.y).join('\n') || 'NOT FOUND'; };
  api.click = (i) => { const r = api.rows()[i]; if (!r) return 'NO INDEX ' + i; r.el.click(); return 'CLICKED ' + i + ' ' + r.label + ' @' + r.x + ',' + r.y; };
  api.coords = (i) => { const r = api.rows()[i]; return r ? r.x + ',' + r.y : 'NO INDEX'; };
  return api;
})();
'__ui loaded — 用 __ui() 列清單、__ui.find("copy")、__ui.click(n)'
