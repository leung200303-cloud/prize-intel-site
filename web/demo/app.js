/* 景品情報索引 — 前端 MVP（純靜態，零後端）
 * 私隱：所有搜尋／篩選／排序喺記憶體完成；收藏、瀏覽記錄、最近搜尋只寫 localStorage。
 * 數據：taxonomy.json（分類樹）+ items.json（示範索引）。standalone.html 會內聯。
 */
(() => {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  // ------------------------------------------------------------ 正規化（鏡像 module1）
  const ZEN = (() => {
    const m = {};
    for (let i = 0; i < 94; i++) m[String.fromCharCode(0xff01 + i)] = String.fromCharCode(0x21 + i);
    return m;
  })();
  const DECOR = new Set(' 　【】[]（）()「」『』・･-–—_/／:：!！?？★☆♪♡♥、,，.。~〜'.split(''));

  function norm(s) {
    if (!s) return '';
    let t = '';
    for (const ch of String(s)) t += (ZEN[ch] || ch);
    t = t.toLowerCase().replace(/[\u30a1-\u30f6]/g, c => String.fromCharCode(c.charCodeAt(0) - 96));
    t = Array.from(t).map(c => (DECOR.has(c) ? ' ' : c)).join('');
    return t.replace(/\s+/g, ' ').trim();
  }
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ------------------------------------------------------------ localStorage
  const LS = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* 私隱模式等 */ } },
    del(k) { try { localStorage.removeItem(k); } catch {} },
  };
  const K = { fav: 'pi.favs', hist: 'pi.history', q: 'pi.recentQ', view: 'pi.view', filt: 'pi.filters' };

  // ------------------------------------------------------------ 狀態
  const state = {
    tax: null, payload: null, items: [], preview: [],
    q: '', channel: 'all', view: LS.get(K.view, 'player'), sort: 'relevance',
    filters: { maker: new Set(), brand: new Set(), ip: new Set(), category: new Set(), tier: new Set(), size: new Set(), month: new Set(), status: new Set() },
    favs: new Set(LS.get(K.fav, [])),
    history: LS.get(K.hist, []),
    recentQ: LS.get(K.q, []),
  };

  // ------------------------------------------------------------ 資料載入
  async function loadData() {
    if (window.__PI_INLINE__) return window.__PI_INLINE__;
    // @NET-BEGIN —— build_demo.py 內聯時會剷走呢段（standalone 版零網絡原語）
    const [tax, items] = await Promise.all([
      fetch('./data/taxonomy.json').then(r => r.json()),
      fetch('./data/items.json').then(r => r.json()),
    ]);
    return { taxonomy: tax, items };
    // @NET-END
  }

  // ------------------------------------------------------------ 名稱查找
  const maps = { maker: {}, makerAl: {}, ip: {}, brand: {}, brandAl: {}, cat: {}, ch: {}, st: {} };
  const STATUS_LABEL = {
    on_sale: ['已發售', '発売中', '已发售'],
    announced: ['予告', '未發売', '未発売', '發售預定', '發售預定'],
  };
  function buildMaps() {
    (state.tax.filters.maker || []).forEach(m => {
      maps.maker[m.code] = m.name_jp || m.code;
      maps.makerAl[m.code] = m.aliases || [];
    });
    (state.tax.filters.ip_work || []).forEach(w => {
      maps.ip[w.code] = { jp: w.title_jp, en: w.title_en, zh: w.title_zh, al: w.aliases || [] };
    });
    (state.tax.filters.brand_line || []).forEach(b => {
      maps.brand[b.code] = b.name;
      maps.brandAl[b.code] = b.aliases || [];
    });
    (state.tax.filters.category || []).forEach(c => {
      maps.cat[c.code] = `${c.label_zh || ''} ${c.label_jp || ''}`.trim();
    });
    (state.tax.filters.channel_type || []).forEach(c => {
      maps.ch[c.code] = `${c.label_zh || ''} ${c.label_jp || ''}`.trim();
    });
  }
  const makerName = c => maps.maker[c] || c || '—';
  const ipLabel = c => (maps.ip[c] ? maps.ip[c].jp : (c || '—'));
  const brandName = c => maps.brand[c] || c || '';
  const catName = c => maps.cat[c] || c || '';

  // ------------------------------------------------------------ 搜尋索引
  function searchBlob(it) {
    const ip = maps.ip[it.ip] || {};
    const parts = [
      it.official_name, it.raw_title,
      makerName(it.maker), ...(maps.makerAl[it.maker] || []),
      brandName(it.brand), ...(maps.brandAl[it.brand] || []),
      ip.jp, ip.en, ip.zh, ...(ip.al || []),
      (it.characters || []).join(' '),
      catName(it.category),
      maps.ch[it.channel] || '',
      ...(STATUS_LABEL[it.status] || []),
      it.series_group ? `vol.${it.series_group} 第${it.series_group}弾` : '',
      it.prize_tier || '',
      it.prize_tier && it.prize_tier.includes('ラストワン') ? '最終賞 尾賞 last one' : '',
    ];
    // 尺寸／月份／再販／獎池都要搜得到（自測發現 miss）
    if (it.size_cm) parts.push(`${it.size_cm}cm`, `約${it.size_cm}cm`);
    if (it.release_month) {
      const [y, m] = it.release_month.split('-');
      parts.push(it.release_month, `${y}年${Number(m)}月`);
    }
    if (it.is_resale) parts.push('再販', '再版');
    if (it.is_kuji_pool) parts.push('獎池', 'プール');
    return norm(parts.filter(Boolean).join(' '));
  }
  function indexItems() { state.items.forEach(it => { it._blob = searchBlob(it); }); }

  // ------------------------------------------------------------ 篩選 + 搜尋
  function passesFilters(it) {
    const f = state.filters;
    const test = (set, v) => set.size === 0 || set.has(String(v));
    if (!test(f.maker, it.maker)) return false;
    if (!test(f.brand, it.brand)) return false;
    if (!test(f.ip, it.ip)) return false;
    if (!test(f.category, it.category)) return false;
    if (!test(f.tier, it.prize_tier || '')) return false;
    if (!test(f.size, it.size_cm)) return false;
    if (!test(f.month, it.release_month)) return false;
    if (!test(f.status, it.status)) return false;
    return true;
  }

  function currentRows() {
    if (state.channel === 'preview') return [];
    if (state.channel === 'favorites') {
      return state.items.filter(it => state.favs.has(it.id) && passesFilters(it));
    }
    let rows = state.items.filter(passesFilters);
    if (state.channel !== 'all') rows = rows.filter(it => it.channel === state.channel);
    const q = norm(state.q);
    state._orFallback = false;
    if (q) {
      const toks = q.split(' ').filter(Boolean);
      let hit = rows.filter(it => toks.every(t => it._blob.includes(t)));
      if (!hit.length && toks.length > 1) {
        // 多詞完全冇 → 退回「任一詞」並喺 UI 講清楚（唔好靜靜報 0）
        hit = rows.filter(it => toks.some(t => it._blob.includes(t)));
        state._orFallback = hit.length > 0;
      }
      rows = hit;
      rows.forEach(it => { it._score = toks.filter(t => norm(it.official_name).includes(t)).length; });
    }
    rows = sortRows(rows);
    return rows;
  }

  function sortRows(rows) {
    const by = {
      // 冇搜尋詞時「相關度」退化為瀏覽熱度＋新舊，避免開頁第一眼係隨機順序
      relevance: (a, b) => (b._score || 0) - (a._score || 0)
        || (b.views_7d || 0) - (a.views_7d || 0)
        || (b.release_month || '').localeCompare(a.release_month || ''),
      newest: (a, b) => (b.release_month || '').localeCompare(a.release_month || ''),
      views: (a, b) => (b.views_7d || 0) - (a.views_7d || 0),
      price: (a, b) => ((b.price && b.price.baseline_jpy) || 0) - ((a.price && a.price.baseline_jpy) || 0),
      size: (a, b) => (b.size_cm || 0) - (a.size_cm || 0),
    }[state.sort];
    return rows.slice().sort(by);
  }

  // ------------------------------------------------------------ 高亮
  function highlight(text) {
    const safe = esc(text);
    const q = state.q.trim();
    if (!q) return safe;
    const toks = norm(q).split(' ').filter(t => t.length >= 2);
    let out = safe;
    toks.forEach(t => {
      // 用原始字串做寬鬆對照（避免 norm 後位置偏移）：直接對未 norm 文字做 case-insensitive 取代
      const re = new RegExp(`(${t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'ig');
      out = out.replace(re, '<mark>$1</mark>');
    });
    return out;
  }

  // ------------------------------------------------------------ 排序文字
  const MONTH_LABEL = m => (m ? m.replace('-', '年') + '月' : '—');
  const jpy = n => (n == null ? '—' : '¥' + Number(n).toLocaleString('ja-JP'));

  // ------------------------------------------------------------ 卡片
  function cardHTML(it) {
    const fav = state.favs.has(it.id) ? ' on' : '';
    const chips = [];
    chips.push(`<span class="chip maker">${esc(makerName(it.maker))}</span>`);
    if (it.brand) chips.push(`<span class="chip brand">${esc(brandName(it.brand))}</span>`);
    if (it.ip) chips.push(`<span class="chip ip">${esc(ipLabel(it.ip))}</span>`);
    if (it.channel === 'ichiban_kuji') chips.push(`<span class="chip kuji">一番くじ${it.prize_tier ? '・' + esc(it.prize_tier) : ''}</span>`);
    chips.push(it.demo ? '<span class="chip demo">DEMO</span>' : '<span class="chip real">実データ</span>');

    const price = it.price || {};
    const stale = price.captured_at && price.captured_at < '2026-09-20';
    const showViews = state.view === 'player' && DATA_FLAGS.views;
    const showSeries = state.view === 'shop' && it.series_group;

    const links = [
      `<a href="${esc(it.market_links.surugaya)}" target="_blank" rel="noopener noreferrer">駿河屋</a>`,
      `<a href="${esc(it.market_links.mercari)}" target="_blank" rel="noopener noreferrer">メルカリ</a>`,
      `<a href="${esc(it.market_links.yahoo)}" target="_blank" rel="noopener noreferrer">ヤフオク</a>`,
    ].join('');

    return `<article class="card" data-id="${it.id}">
      <div class="card-top">
        <h3 class="card-title">${highlight(it.official_name)}</h3>
        <button class="fav${fav}" data-fav="${it.id}" type="button" title="收藏">★</button>
      </div>
      <div class="chips">${chips.join('')}</div>
      <div class="card-meta">
        <span>發售 <b>${esc(MONTH_LABEL(it.release_month))}</b></span>
        <span>尺寸 <b>${it.size_cm ? '約' + it.size_cm + 'cm' : '—'}</b></span>
        <span>${it.status === 'on_sale' ? '已發售' : '予告'}</span>
        ${it.is_resale ? '<span style="color:#a8792b">再販</span>' : ''}
        ${showSeries ? `<span>系列號 <b>${esc(it.series_group)}</b></span>` : ''}
        ${it.is_kuji_pool ? '<span>獎池</span>' : ''}
      </div>
      <div class="price">
        <span><span class="k">基準</span> <span class="v">${jpy(price.baseline_jpy)}</span></span>
        <span><span class="k">成交樣本</span> <span class="v">${jpy(price.sold_min_jpy)}–${jpy(price.sold_max_jpy)}</span></span>
        <span class="stale">${esc(price.captured_at || '')}${stale ? '（已過期）' : ''}</span>
      </div>
      <div class="card-foot">
        <div class="links">${links}</div>
        ${showViews && DATA_FLAGS.views ? `<span class="views">瀏覽 <b>${Number(it.views_7d || 0).toLocaleString('ja-JP')}</b></span>` : ''}
      </div>
    </article>`;
  }

  // ------------------------------------------------------------ 篩選欄
  const FILTER_DEFS = [
    { key: 'maker', label: '廠商', get: it => it.maker, name: makerName },
    { key: 'brand', label: '系列線', get: it => it.brand, name: brandName },
    { key: 'ip', label: '作品 IP', get: it => it.ip, name: ipLabel },
    { key: 'category', label: '品類', get: it => it.category, name: catName },
    { key: 'month', label: '發售月', get: it => it.release_month, name: MONTH_LABEL },
    { key: 'size', label: '尺寸（5cm 桶）', get: it => it.size_cm, name: v => '約' + v + 'cm' },
    { key: 'status', label: '狀態', get: it => it.status, name: v => (v === 'on_sale' ? '已發售' : '予告') },
  ];
  const SHOW_LIMIT = 6;

  function renderFilters() {
    const rows = state.channel === 'all' || state.channel === 'favorites' || state.channel === 'preview'
      ? state.items : state.items.filter(it => it.channel === state.channel);
    const html = FILTER_DEFS.map(def => {
      const counts = new Map();
      rows.forEach(it => {
        const v = def.get(it);
        if (v === null || v === undefined || v === '') return;
        const k = String(v);
        counts.set(k, (counts.get(k) || 0) + 1);
      });
      let entries = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
      if (def.key === 'size') entries.sort((a, b) => Number(a[0]) - Number(b[0]));
      if (def.key === 'month') entries.sort((a, b) => a[0].localeCompare(b[0]));
      const more = entries.length > SHOW_LIMIT;
      const shown = entries.slice(0, SHOW_LIMIT);
      const rest = entries.slice(SHOW_LIMIT);
      const opt = ([v, n]) => `<div class="fopt"><input type="checkbox" id="f_${def.key}_${esc(v)}" data-fkey="${def.key}" value="${esc(v)}" ${state.filters[def.key].has(v) ? 'checked' : ''}><label for="f_${def.key}_${esc(v)}">${esc(def.name(v))}</label><span class="n">${n}</span></div>`;
      return `<div class="fgroup" data-fg="${def.key}">
        <h3>${def.label}${state.filters[def.key].size ? ' <button class="clr" data-clr="${def.key}" type="button">清除</button>' : ''}</h3>
        ${shown.map(opt).join('')}
        ${rest.length ? `<div class="hidden" data-more="${def.key}">${rest.map(opt).join('')}</div><button class="fmore" data-morebtn="${def.key}" type="button">＋ 更多（${rest.length}）</button>` : ''}
      </div>`;
    }).join('');

    $('#filters').innerHTML = `${html}
      <div class="filter-foot"><button id="resetFilters" type="button">重設全部篩選</button></div>`;
  }

  // ------------------------------------------------------------ 榜單 / 側欄
  function renderRankings() {
    const onSale = state.items;
    if (state.view === 'player') {
      $('#rank1Title').textContent = DATA_FLAGS.views ? '7 日瀏覽熱度 TOP10' : '瀏覽熱度（未接）';
      $('#rank1Note').textContent = DATA_FLAGS.views ? '玩家瀏覽熱度（非採購行情指標）' : '等 item_view_daily 接入，唔會用假數';
      const top = onSale.slice().sort((a, b) => b.views_7d - a.views_7d).slice(0, 10);
      $('#rankItems').innerHTML = top.map(it => `<li><button data-goto="${it.id}" type="button"><span class="t">${esc(it.official_name)}</span><span class="m">${Number(it.views_7d).toLocaleString('ja-JP')} 次瀏覽</span></button></li>`).join('');

      $('#rank2Title').textContent = 'IP 瀏覽熱度';
      $('#rank2Note').textContent = '按商品瀏覽量彙總，唔係搜尋查詢量';
      const byIp = new Map();
      onSale.forEach(it => { if (!it.ip) return; byIp.set(it.ip, (byIp.get(it.ip) || 0) + (it.views_7d || 0)); });
      const ips = Array.from(byIp.entries()).sort((a, b) => b[1] - a[1]).slice(0, 8);
      $('#rankIp').innerHTML = ips.map(([ip, v]) => `<li><button data-ip="${esc(ip)}" type="button"><span class="t">${esc(ipLabel(ip))}</span><span class="m">${Number(v).toLocaleString('ja-JP')} 瀏覽</span></button></li>`).join('');
    } else {
      $('#rank1Title').textContent = '同系列款數 TOP10';
      $('#rank1Note').textContent = '店舖視角：睇邊個系列出貨最密';
      const bySeries = new Map();
      onSale.forEach(it => { if (it.brand) bySeries.set(it.brand, (bySeries.get(it.brand) || 0) + 1); });
      const top = Array.from(bySeries.entries()).sort((a, b) => b[1] - a[1]).slice(0, 10);
      $('#rankItems').innerHTML = top.map(([b, n]) => `<li><button data-brand="${esc(b)}" type="button"><span class="t">${esc(brandName(b))}</span><span class="m">${n} 款</span></button></li>`).join('');

      $('#rank2Title').textContent = '預告／再販清單';
      $('#rank2Note').textContent = '店舖視角：入貨前要知嘅時間點';
      const soon = onSale.filter(it => it.status === 'announced' || it.is_resale)
        .sort((a, b) => (a.release_month || '').localeCompare(b.release_month || '')).slice(0, 8);
      $('#rankIp').innerHTML = soon.map(it => `<li><button data-goto="${it.id}" type="button"><span class="t">${esc(it.official_name)}</span><span class="m">${esc(MONTH_LABEL(it.release_month))}${it.is_resale ? ' ・再販' : ''}</span></button></li>`).join('');
    }

    // 收藏
    const favs = state.items.filter(it => state.favs.has(it.id));
    $('#favList').innerHTML = favs.length
      ? favs.map(it => `<li><button data-goto="${it.id}" type="button">${esc(it.official_name.slice(0, 34))}</button></li>`).join('')
      : '<li class="muted">未有收藏</li>';
    $('#favCount').textContent = String(favs.length);

    // 最近搜尋
    $('#recentQ').innerHTML = state.recentQ.length
      ? state.recentQ.slice(0, 6).map(q => `<li><button data-q="${esc(q)}" type="button">${esc(q)}</button></li>`).join('')
      : '<li class="muted">—</li>';
  }

  // ------------------------------------------------------------ 列表 / 速報
  function render() {
    const rows = currentRows();
    const list = $('#list');
    const prev = $('#previewList');
    const empty = $('#empty');

    if (state.channel === 'preview') {
      list.classList.add('hidden');
      empty.classList.add('hidden');
      prev.classList.remove('hidden');
      prev.innerHTML = state.preview.map(p => `<div class="prow"><p class="pt">${esc(p.title)}</p><p class="pm">${esc(p.maker_text)} ・ ${esc(p.source)} ・ ${esc(p.note)}</p></div>`).join('');
      $('#resultCount').textContent = `新貨速報 ${state.preview.length} 條（預告看板，唔入商品索引）`;
      renderFilters(); renderRankings();
      return;
    }
    prev.classList.add('hidden');
    list.classList.remove('hidden');
    empty.classList.toggle('hidden', rows.length > 0);
    list.innerHTML = rows.map(cardHTML).join('');
    $('#resultCount').textContent = `顯示 ${rows.length} / ${state.items.length} 款` +
      (state.q ? `（搜尋：${state.q}）` : '') +
      (state._orFallback ? '　⚠️ 冇完全符合，顯示部分符合' : '');
    renderFilters();
    renderRankings();
  }

  // ------------------------------------------------------------ 排序 select
  function syncSortDefault() {
    // 店舖視角預設按發售月；玩家視角預設相關度
    if (!state._sortTouched) {
      state.sort = state.view === 'shop' ? 'newest' : 'relevance';
      $('#sort').value = state.sort;
    }
  }

  // ------------------------------------------------------------ 意見・要望・苦情（mailto，零後端）
  const META = {
    email: (document.querySelector('meta[name="contact-email"]') || {}).content || '',
    version: (document.querySelector('meta[name="beta-version"]') || {}).content || 'v0.1',
  };
  const DATA_FLAGS = { views: true, price: true };

  const emailReady = !!META.email && !/__|example\.com/i.test(META.email);

  function contactHref() {
    const subj = encodeURIComponent(`[景品情報索引 ${META.version}] 意見・要望・苦情`);
    return `mailto:${emailReady ? META.email : ''}?subject=${subj}`;
  }
  function applyContact() {
    $$('[data-contact]').forEach(a => {
      if (emailReady) { a.href = contactHref(); delete a.dataset.pending; }
      else { a.href = '#'; a.dataset.pending = '1'; }   // 未設定：撳咗複製模板，唔開空白郵件
    });
    if (!emailReady) console.warn('[prize-intel] 聯絡郵箱未設定：改 config.json 嘅 contact_email 再 build');
  }

  function mailTemplate() {
    const active = Object.entries(state.filters)
      .filter(([, s]) => s.size)
      .map(([k, s]) => `${k}=${Array.from(s).join('|')}`);
    return [
      `[景品情報索引 ${META.version}] 意見・要望・苦情`,
      `版本：${META.version}`,
      `視角：${state.view === 'shop' ? '店舖採購' : '一般玩家'}`,
      `最近搜尋：${state.recentQ.join(' / ') || '（無）'}`,
      `當時篩選：${active.join(' ; ') || '（無）'}`,
      '',
      '我想反映：',
      '① 缺邊個 IP／系列：',
      '② 搵唔到邊件貨（搜尋詞）：',
      '③ 其他（資料錯／用落唔順／想加功能）：',
      '',
      '（可唔可以回覆我：願意／唔願意）',
    ].join('\n');
  }

  async function copyMailTemplate() {
    const text = mailTemplate();
    const note = $('#tplNote');
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      try {
        const ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove();
      } catch { window.prompt('複製唔到，請手動複製：', text); }
    }
    if (note) {
      note.textContent = emailReady
        ? '模板已複製。撳上面「意見・要望・苦情はこちら」開郵件，貼上就發。'
        : '模板已複製，但聯絡郵箱未設定（Beta 設定中）。';
      note.classList.add('ok');
    }
  }

  // ------------------------------------------------------------ 事件
  function bind() {
    $('#q').addEventListener('input', e => {
      state.q = e.target.value;
      if (state.q.trim().length >= 2) rememberQuery(state.q.trim());
      render();
    });
    $('#clearQ').addEventListener('click', () => { state.q = ''; $('#q').value = ''; render(); });

    $('#sort').addEventListener('change', e => { state.sort = e.target.value; state._sortTouched = true; render(); });

    $$('.tabs button').forEach(b => b.addEventListener('click', () => {
      $$('.tabs button').forEach(x => x.classList.toggle('active', x === b));
      state.channel = b.dataset.channel;
      render();
    }));

    $$('.viewtoggle button').forEach(b => b.addEventListener('click', () => {
      state.view = b.dataset.view;
      LS.set(K.view, state.view);
      $$('.viewtoggle button').forEach(x => x.classList.toggle('active', x === b));
      syncSortDefault();
      render();
    }));

    // 篩選（事件委派）
    $('#filters').addEventListener('change', e => {
      const cb = e.target.closest('input[data-fkey]');
      if (!cb) return;
      const set = state.filters[cb.dataset.fkey];
      cb.checked ? set.add(cb.value) : set.delete(cb.value);
      render();
    });
    $('#filters').addEventListener('click', e => {
      const clr = e.target.closest('[data-clr]');
      if (clr) { state.filters[clr.dataset.clr].clear(); render(); return; }
      const more = e.target.closest('[data-morebtn]');
      if (more) {
        const box = $(`[data-more="${more.dataset.morebtn}"]`);
        box.classList.toggle('hidden');
        more.textContent = box.classList.contains('hidden') ? `＋ 更多` : '− 收起';
        return;
      }
      if (e.target.closest('#resetFilters')) {
        Object.values(state.filters).forEach(s => s.clear());
        render();
      }
    });

    // 收藏 / 前往
    $('#list').addEventListener('click', e => {
      const fav = e.target.closest('[data-fav]');
      if (fav) { toggleFav(fav.dataset.fav); return; }
      const card = e.target.closest('.card');
      if (card) recordHistory(card.dataset.id);
    });
    $('#sidebar')?.addEventListener('click', () => {});
    document.addEventListener('click', e => {
      const goto = e.target.closest('[data-goto]');
      if (goto) {
        const it = state.items.find(x => x.id === goto.dataset.goto);
        if (it) { recordHistory(it.id); $('#q').value = it.official_name; state.q = it.official_name; render(); }
        return;
      }
      const byIp = e.target.closest('[data-ip]');
      if (byIp) { state.filters.ip = new Set([byIp.dataset.ip]); state.channel = 'all'; render(); return; }
      const byBrand = e.target.closest('[data-brand]');
      if (byBrand) { state.filters.brand = new Set([byBrand.dataset.brand]); state.channel = 'all'; render(); return; }
      const recent = e.target.closest('[data-q]');
      if (recent) { state.q = recent.dataset.q; $('#q').value = state.q; render(); return; }
      if (e.target.closest('#clearLocal')) { clearLocal(); }
      if (e.target.closest('#exportFeedback')) { copyFeedback(); }
      const pending = e.target.closest('[data-contact][data-pending]');
      if (pending) { e.preventDefault(); copyMailTemplate(); return; }
      if (e.target.closest('#copyTemplate, #copyTemplateFoot')) { copyMailTemplate(); }
    });
  }

  function toggleFav(id) {
    state.favs.has(id) ? state.favs.delete(id) : state.favs.add(id);
    LS.set(K.fav, Array.from(state.favs));
    render();
  }
  function recordHistory(id) {
    if (!id) return;
    state.history = [id, ...state.history.filter(x => x !== id)].slice(0, 50);
    LS.set(K.hist, state.history);
  }
  function rememberQuery(q) {
    if (!q) return;
    if (state.recentQ[0] === q) return;
    state.recentQ = [q, ...state.recentQ.filter(x => x !== q)].slice(0, 8);
    LS.set(K.q, state.recentQ);
  }
  function clearLocal() {
    state.favs.clear(); state.history = []; state.recentQ = [];
    Object.keys(K).forEach(k => LS.del(K[k]));
    render();
  }

  // ---- Beta 自願回報：只複製文字到剪貼板，零網絡、零上傳
  function feedbackText() {
    const active = Object.entries(state.filters)
      .filter(([, s]) => s.size)
      .map(([k, s]) => `${k}=${Array.from(s).join('|')}`);
    return [
      `[景品情報索引 Beta 回饋] ${new Date().toISOString().slice(0, 10)}`,
      `視角：${state.view === 'shop' ? '店舖採購' : '一般玩家'}`,
      `最近搜尋（最多 8 個）：${state.recentQ.join(' / ') || '（無）'}`,
      `當時篩選：${active.join(' ; ') || '（無）'}`,
      `收藏數：${state.favs.size}　現時分類：${state.channel}`,
      `想搵但搵唔到（請自行填）：`,
      `覺得缺邊個 IP／系列（請自行填）：`,
    ].join('\n');
  }

  async function copyFeedback() {
    const text = feedbackText();
    const note = $('#fbNote');
    try {
      await navigator.clipboard.writeText(text);
      note.textContent = '已複製到剪貼板（只喺你部機，冇上傳）。貼返俾我就可以，多謝。';
      note.classList.add('ok');
      return;
    } catch { /* 落 fallback */ }
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
      note.textContent = '已複製（fallback）。貼返俾我就得。';
      note.classList.add('ok');
    } catch {
      window.prompt('複製唔到，請手動複製以下文字：', text);
    }
  }

  // ------------------------------------------------------------ 啟動
  (async function boot() {
    try {
      const data = await loadData();
      state.tax = data.taxonomy;
      state.payload = data.items;
      state.items = data.items.items || [];
      state.preview = data.items.preview || [];
      buildMaps(); indexItems();

      const meta = data.items._meta || {};
      DATA_FLAGS.views = meta.views_available !== false;
      DATA_FLAGS.price = meta.price_available !== false;
      const c = meta.counts || {};
      const total = c.total || state.items.length;
      $('#metaCount').textContent = (c.real === total)
        ? `真數據 ${total} 款（全部實抓）・索引由 taxonomy.json 同步`
        : `示範數據 ${total} 款（真實標題 ${c.real ?? '—'}）・索引由 taxonomy.json 同步`;

      // 初始化 UI
      $$('.viewtoggle button').forEach(b => b.classList.toggle('active', b.dataset.view === state.view));
      $('#sort').value = state.sort;
      syncSortDefault();
      applyContact();
      bind();
      render();
      console.info('[prize-intel] demo ready:', c, 'privacy=local-only');
    } catch (err) {
      document.body.insertAdjacentHTML('afterbegin',
        `<div class="notice" style="color:#b03a2e">載入失敗：${esc(err.message)}。如果係用 file:// 直接開，請改用 <code>standalone.html</code>，或者起個靜態 server（<code>pwsh -File serve.ps1</code>）。</div>`);
      console.error(err);
    }
  })();
})();
