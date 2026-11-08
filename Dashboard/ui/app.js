'use strict';
/* Dashboard UI. Talks to app.py through pywebview's js_api (or fetch in --serve mode); app.py pushes
   events back through App.on(event, data). */

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* ================================================================ Icons */
const ICONS = {
  mic: '<path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z"/><path d="M19 11a7 7 0 0 1-14 0M12 18v3"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/>',
  max: '<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>',
  min: '<path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7"/>',
  prev: '<path d="M19 20 9 12l10-8v16ZM5 19V5"/>',
  next: '<path d="m5 4 10 8-10 8V4ZM19 5v14"/>',
  play: '<path d="M7 4v16l13-8L7 4Z" fill="currentColor"/>',
  pause: '<path d="M7 4h3v16H7zM14 4h3v16h-3z" fill="currentColor"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
  chat: '<path d="M20.5 11.5a8.5 8.5 0 0 1-12.6 7.4L3.5 20l1.2-4.2A8.5 8.5 0 1 1 20.5 11.5Z" fill="currentColor" stroke="none"/>',
  speaker: '<path d="M11 5 6 9H3v6h3l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
  speakerOff: '<path d="M11 5 6 9H3v6h3l5 4V5Z"/><path d="m16 9 6 6M22 9l-6 6"/>',
  sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/>',
  pencil: '<path d="M4 20h4L19 9l-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/>',
  hourglass: '<path d="M6 2h12M6 22h12M7 2v4l5 6-5 6v4M17 2v4l-5 6 5 6v4"/><path class="sand-top" d="M9 6h6l-3 4Z" fill="currentColor" stroke="none"/><path class="sand-bottom" d="M9 20h6l-3-3Z" fill="currentColor" stroke="none"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>',
  cloud: '<path d="M17.5 19H7a5 5 0 1 1 1.4-9.8A6 6 0 0 1 19.6 11 4 4 0 0 1 17.5 19Z"/>',
  cloudsun: '<path d="M12 2v2M4.9 4.9l1.4 1.4M2 12h2M19.1 4.9l-1.4 1.4"/><path d="M15.9 9.4A4 4 0 1 0 8.4 11"/><path d="M17.5 21H9a4 4 0 1 1 .9-7.9 5 5 0 0 1 9.4 2A3 3 0 0 1 17.5 21Z"/>',
  fog: '<path d="M4 14h16M4 18h16M6 10h12"/>',
  drizzle: '<path d="M17.5 15H7a5 5 0 1 1 1.4-9.8A6 6 0 0 1 19.6 7 4 4 0 0 1 17.5 15Z"/><path d="M8 19v1M12 19v1M16 19v1"/>',
  rain: '<path d="M17.5 14H7a5 5 0 1 1 1.4-9.8A6 6 0 0 1 19.6 6 4 4 0 0 1 17.5 14Z"/><path d="m8 17-1 3M12 17l-1 3M16 17l-1 3"/>',
  snow: '<path d="M17.5 14H7a5 5 0 1 1 1.4-9.8A6 6 0 0 1 19.6 6 4 4 0 0 1 17.5 14Z"/><path d="M8 18h.01M12 20h.01M16 18h.01"/>',
  storm: '<path d="M17.5 14H7a5 5 0 1 1 1.4-9.8A6 6 0 0 1 19.6 6 4 4 0 0 1 17.5 14Z"/><path d="m13 14-3 5h4l-3 4"/>',
};
const icon = (n, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[n]}</svg>`;

/* ================================================================ Bridge to Python */
const SERVE = new URLSearchParams(location.search).has('serve');
const Bridge = {
  ready: new Promise(resolve => {
    if (SERVE) return resolve();
    if (window.pywebview && window.pywebview.api) return resolve();
    window.addEventListener('pywebviewready', () => resolve(), { once: true });
  }),
  async call(name, ...args) {
    await this.ready;
    let res;
    if (SERVE) {
      const r = await fetch('/api/' + name, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(args) });
      res = await r.json();
    } else {
      res = await window.pywebview.api[name](...args);
    }
    if (res && typeof res === 'object' && res.__error__) throw new Error(res.__error__);
    return res;
  },
};

const S = { settings: null, maximized: null, volume: 60, ducked: false, duckCount: 0, duckPaused: false, lastInput: Date.now() };

function toast(text, kind = '') {
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = text;
  $('#toasts').append(el);
  setTimeout(() => el.remove(), 4000);
}
function reportState() {
  Bridge.call('ui_state', { volume: S.volume, song: Music.current()?.title || null, maximized: S.maximized }).catch(() => {});
  Timers.alarm();          // the banner shows only when the flashing Timers widget isn't in view
  Custom.mountVisible();   // custom widgets run only while on screen, and hear about size changes
}
function ago(ts) {
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (!ts) return '';
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

/* ================================================================ Clock */
function tickClock() {
  const now = new Date();
  const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const date = now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
  $('#time').textContent = time;
  $('#date').textContent = date;
  $('#photoClock').innerHTML = `<b>${esc(time)}</b><span>${esc(date)}</span>`;
  $('#zones').innerHTML = (S.settings?.world_clocks || []).map(([label, tz]) => {
    try {
      const t = now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', timeZone: tz });
      // "+1 day" / "-1 day" when that city is on a different date
      const dayOf = z => Number(now.toLocaleDateString('en-CA', { timeZone: z }).replaceAll('-', ''));
      const diff = Math.sign(dayOf(tz) - dayOf(Intl.DateTimeFormat().resolvedOptions().timeZone));
      return `<div class="zone" title="${esc(tz)}"><b>${esc(t)}</b><small>${esc(label)}${diff ? (diff > 0 ? ' · tomorrow' : ' · yesterday') : ''}</small></div>`;
    } catch { return ''; }                     // unknown time zone name
  }).join('');
}

/* ================================================================ Maximize / restore */
function maximize(tile) {
  const el = $(`.tile[data-tile="${tile}"]`);
  if (!el || tile === 'whatsapp' || tile === 'assistant') return;
  $$('.tile.max').forEach(t => t.classList.remove('max'));
  el.classList.add('max');
  document.body.classList.add('has-max');
  S.maximized = tile;
  $$('.max-btn').forEach(b => { b.innerHTML = icon(b.closest('.tile').classList.contains('max') ? 'min' : 'max'); });
  if (tile === 'stocks') Stocks.drawChart();
  if (tile === 'weather') Weather.renderFull();
  if (!Layout.shown(tile)) ({ news: () => GenNews.load(), pc: () => PC.load(), network: () => Net.load(), calendar: () => Cal.load() }[tile] || (() => {}))();
  reportState();
}
function restore() {
  $$('.tile.max').forEach(t => t.classList.remove('max'));
  document.body.classList.remove('has-max');
  S.maximized = null;
  $$('.max-btn').forEach(b => { b.innerHTML = icon('max'); });
  reportState();
}

/* ================================================================ Photos */
const Photos = {
  n: 0, count: 0, timer: null, front: 'A', seconds: 12,
  info(info) {
    this.count = info.count;
    this.seconds = info.seconds || 12;
    $('#photoSub').textContent = info.scanning ? 'scanning…' : `${info.count.toLocaleString()} photos`;
    if (!info.count) {
      $('#photoEmpty').textContent = info.scanning ? 'Looking for photos…' : 'No photos found. Pick folders in Settings → Tiles.';
      $('#photoEmpty').style.display = '';
      return;
    }
    if (!this.timer) { this.show(0); this.schedule(); }
  },
  schedule() {
    clearInterval(this.timer);
    this.timer = setInterval(() => this.step(1), this.seconds * 1000);
  },
  step(d) {
    if (!this.count) return;
    this.show((this.n + d + this.count) % this.count);
    this.schedule();
  },
  show(n) {
    const img = new Image();
    img.onload = () => {
      this.n = n;
      const next = this.front === 'A' ? $('#photoB') : $('#photoA');
      const cur = this.front === 'A' ? $('#photoA') : $('#photoB');
      next.src = img.src;
      next.classList.add('on');
      cur.classList.remove('on');
      this.front = this.front === 'A' ? 'B' : 'A';
      $('#photoBg').style.backgroundImage = `url("${img.src}")`;
      $('#photoEmpty').style.display = 'none';
    };
    img.onerror = () => { if (n !== this.n) this.n = n; };   // unreadable file: the next tick moves on
    img.src = `/photo/${n}`;
  },
};

/* ================================================================ Music (YouTube IFrame player) */
const Music = {
  player: null, ready: false, items: [], i: -1, playing: false, pending: null,
  current() { return this.items[this.i] || null; },
  init() {
    this.player = new YT.Player('ytPlayer', {
      width: '100%', height: '100%',
      playerVars: { autoplay: 1, playsinline: 1, rel: 0, modestbranding: 1, origin: location.origin },
      events: {
        onReady: () => {
          this.ready = true;
          this.player.setVolume(S.volume);
          if (this.pending) { const p = this.pending; this.pending = null; this.load(p); }
        },
        onStateChange: e => {
          this.playing = e.data === YT.PlayerState.PLAYING;
          $('#playBtn').innerHTML = icon(this.playing ? 'pause' : 'play');
          if (e.data === YT.PlayerState.ENDED) this.go(1);
        },
        onError: () => this.go(1),          // not embeddable / removed: try the next result
      },
    });
  },
  play(items) {
    this.items = items;
    this.renderQueue();
    this.load(0);
  },
  load(i) {
    if (!this.ready) { this.pending = i; return; }
    if (i < 0 || i >= this.items.length) return;
    this.i = i;
    const it = this.items[i];
    this.player.loadVideoById(it.id);
    this.player.setVolume(S.ducked ? Math.round(S.volume * (S.settings?.duck_level ?? 20) / 100) : S.volume);
    $('#songTitle').textContent = it.title;
    $('#songChannel').textContent = it.channel || '';
    $('#videoEmpty').style.display = 'none';
    $('.video-wrap').classList.add('loaded');
    this.renderQueue();
    reportState();
  },
  go(d) { if (this.items.length) this.load((this.i + d + this.items.length) % this.items.length); },
  pause() { this.ready && this.player.pauseVideo(); },
  resume() { this.ready && this.current() && this.player.playVideo(); },
  toggle() { this.playing ? this.pause() : this.resume(); },
  volume(v) {
    S.volume = v;
    $('#volume').value = v;
    if (this.ready && !S.ducked) this.player.setVolume(v);
    reportState();
  },
  /* Several things lower the music (you speaking, then the reply): count them, so the first one to finish
     doesn't bring the volume back while the other is still going. */
  duck(on) {
    S.duckCount = Math.max(0, S.duckCount + (on ? 1 : -1));
    const was = S.ducked;
    S.ducked = S.duckCount > 0;
    if (!this.ready || was === S.ducked) return;
    const level = S.settings?.duck_level ?? 20;
    if (level === 0) {                       // "0%" means pause instead
      if (S.ducked && this.playing) { S.duckPaused = true; this.pause(); }
      else if (!S.ducked && S.duckPaused) { S.duckPaused = false; this.resume(); }
      return;
    }
    this.player.setVolume(S.ducked ? Math.round(S.volume * level / 100) : S.volume);
  },
  renderQueue() {
    $('#queue').innerHTML = this.items.map((it, i) => `<li data-i="${i}" class="${i === this.i ? 'on' : ''}">
      <img src="https://i.ytimg.com/vi/${esc(it.id)}/mqdefault.jpg" alt=""><span>${esc(it.title)}</span></li>`).join('');
  },
  async search(q) {
    try { this.play(await Bridge.call('music_search', q)); }
    catch (e) { toast(e.message, 'err'); }
  },
};
window.onYouTubeIframeAPIReady = () => Music.init();

/* ================================================================ Stocks */
const RANGES = [['1d', '1D'], ['5d', '5D'], ['1mo', '1M'], ['6mo', '6M'], ['1y', '1Y'], ['5y', '5Y']];
const Stocks = {
  list: [], focus: null, range: '1d', chart: null,
  async load() {
    if (!Layout.visible('stocks')) return;
    try {
      this.list = await Bridge.call('stocks_list', '1d');
      $('#stocksSub').textContent = 'updated ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) { $('#stocksSub').textContent = e.message; return; }
    if (!this.focus || !this.list.some(q => q.symbol === this.focus)) this.focus = this.list[0]?.symbol;
    this.render();
    if (S.maximized === 'stocks') this.drawChart();
  },
  render() {
    $('#quotes').innerHTML = this.list.map(q => {
      if (q.error || q.price == null) return `<li data-sym="${esc(q.symbol)}"><div class="q-name"><b>${esc(q.name)}</b><small>${esc(q.symbol)}</small></div><span></span><div class="q-val"><small>no data</small></div></li>`;
      const dir = q.pct >= 0 ? 'up' : 'down';
      return `<li data-sym="${esc(q.symbol)}" class="${q.symbol === this.focus ? 'on' : ''}">
        <div class="q-name"><b>${esc(q.name)}</b><small>${esc(q.symbol)}</small></div>
        ${spark(q.points)}
        <div class="q-val"><b>${fmtPrice(q.price)}</b><small class="${dir}">${q.pct >= 0 ? '▲' : '▼'} ${Math.abs(q.pct).toFixed(2)}%</small></div></li>`;
    }).join('');
  },
  async drawChart() {
    const sym = this.focus;
    if (!sym) return;
    $('#ranges').innerHTML = RANGES.map(([r, l]) => `<button type="button" data-r="${r}" class="${r === this.range ? 'on' : ''}">${l}</button>`).join('');
    let q;
    try { q = await Bridge.call('stock_chart', sym, this.range); }
    catch (e) { $('#chart').innerHTML = `<p class="sub">${esc(e.message)}</p>`; return; }
    if (sym !== this.focus) return;
    this.chart = q;
    $('#chartName').textContent = q.name;
    const dir = q.pct >= 0 ? 'up' : 'down';
    $('#chartPrice').innerHTML = q.price == null ? '' : `${fmtPrice(q.price)} ${esc(q.currency)} · <span class="${dir}">${q.change >= 0 ? '+' : ''}${fmtPrice(q.change)} (${q.pct >= 0 ? '+' : ''}${q.pct.toFixed(2)}%)</span>`;
    lineChart($('#chart'), q.points, this.range);
  },
  setFocus(sym) {
    this.focus = sym;
    this.render();
    if (S.maximized === 'stocks') this.drawChart();
  },
};
function fmtPrice(v) {
  if (v == null) return '';
  const a = Math.abs(v);
  return v.toLocaleString(undefined, { minimumFractionDigits: a < 10 ? 2 : a > 10000 ? 0 : 2, maximumFractionDigits: a < 10 ? 3 : a > 10000 ? 0 : 2 });
}
function spark(points) {
  if (!points || points.length < 2) return '<svg class="spark"></svg>';
  const ys = points.map(p => p[1]);
  const min = Math.min(...ys), max = Math.max(...ys), w = 80, h = 26, pad = 2;
  const x = i => (i / (points.length - 1)) * w;
  const y = v => max === min ? h / 2 : pad + (1 - (v - min) / (max - min)) * (h - pad * 2);
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join('');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><path d="${d}" fill="none" stroke="var(--series)" stroke-width="1.5" vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>`;
}
function lineChart(box, points, range, fmtY = fmtPrice) {
  if (!points || points.length < 2) { box.innerHTML = '<p class="sub">No chart data.</p>'; return; }
  const W = box.clientWidth || 600, H = box.clientHeight || 300, L = 8, R = 64, T = 10, B = 24;
  const ys = points.map(p => p[1]);
  let min = Math.min(...ys), max = Math.max(...ys);
  const padY = (max - min) * 0.08 || max * 0.01;
  min -= padY; max += padY;
  const t0 = points[0][0], t1 = points[points.length - 1][0];
  const x = t => L + ((t - t0) / (t1 - t0 || 1)) * (W - L - R);
  const y = v => T + (1 - (v - min) / (max - min)) * (H - T - B);
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join('');
  const area = `${d}L${x(t1).toFixed(1)},${H - B}L${x(t0).toFixed(1)},${H - B}Z`;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => min + (max - min) * f);
  const fmtT = t => {
    const dt = new Date(t * 1000);
    return range === '1d' ? dt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
      : range === '5y' || range === '1y' ? dt.toLocaleDateString([], { month: 'short', year: '2-digit' })
      : dt.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };
  const xt = [0, 0.33, 0.66, 1].map(f => t0 + (t1 - t0) * f);
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Line chart">
    <defs><linearGradient id="fillg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--series)" stop-opacity=".22"/><stop offset="1" stop-color="var(--series)" stop-opacity="0"/></linearGradient></defs>
    ${ticks.map(v => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--grid)" stroke-width="1"/>
      <text x="${W - R + 8}" y="${y(v) + 4}" fill="var(--ink-3)" font-size="11">${fmtY(v)}</text>`).join('')}
    ${xt.map((t, i) => `<text x="${x(t)}" y="${H - 6}" fill="var(--ink-3)" font-size="11" text-anchor="${i === 0 ? 'start' : i === 3 ? 'end' : 'middle'}">${esc(fmtT(t))}</text>`).join('')}
    <path d="${area}" fill="url(#fillg)"/>
    <path d="${d}" fill="none" stroke="var(--series)" stroke-width="2" stroke-linejoin="round"/>
    <line class="xh" y1="${T}" y2="${H - B}" stroke="var(--ink-3)" stroke-width="1" stroke-dasharray="3 3" style="display:none"/>
    <circle class="dot" r="5" fill="var(--series)" stroke="var(--tile)" stroke-width="2" style="display:none"/>
    <rect x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent" class="hit"/>
  </svg><div class="tip"></div>`;
  const svg = $('svg', box), tip = $('.tip', box), xh = $('.xh', box), dot = $('.dot', box);
  const hide = () => { xh.style.display = dot.style.display = tip.style.display = 'none'; };
  $('.hit', box).addEventListener('pointermove', e => {
    const r = svg.getBoundingClientRect();
    const px = (e.clientX - r.left) * (W / r.width);
    const t = t0 + ((px - L) / (W - L - R)) * (t1 - t0);
    let best = points[0];
    for (const p of points) if (Math.abs(p[0] - t) < Math.abs(best[0] - t)) best = p;
    const cx = x(best[0]), cy = y(best[1]);
    xh.setAttribute('x1', cx); xh.setAttribute('x2', cx); xh.style.display = '';
    dot.setAttribute('cx', cx); dot.setAttribute('cy', cy); dot.style.display = '';
    const dt = new Date(best[0] * 1000);
    tip.innerHTML = `<b>${fmtY(best[1])}</b>${esc(range === '1d' || range === '5d' ? dt.toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' }) : dt.toLocaleDateString())}`;
    tip.style.left = (cx * r.width / W) + 'px';
    tip.style.top = (cy * r.height / H) + 'px';
    tip.style.display = 'block';
  });
  $('.hit', box).addEventListener('pointerleave', hide);
}

/* ================================================================ Cyber */
const Cyber = {
  data: null,
  async load(force = false) {
    try { this.data = await Bridge.call('cyber_news', force); }
    catch (e) { $('#cyberSub').textContent = e.message; return; }
    const d = this.data;
    $('#cyberSub').textContent = d.news.length ? `${d.news.length} stories` + (d.errors.length ? ` · ${d.errors.length} source(s) down` : '') : 'offline';
    $('#news').innerHTML = d.news.map((it, i) => `<li data-link="${esc(it.link)}"><b>${esc(it.title)}</b>
      <button class="xp" data-explain="${esc(it.link)}" title="AI explains this story and reads it out">${icon('sparkle')}Explain</button>
      <small>${esc(it.source)} · ${ago(it.time)}</small><p>${esc(it.summary)}</p></li>`).join('') || '<li><small>No stories loaded.</small></li>';
    $('#kev').innerHTML = d.kev.map(k => `<li data-link="${esc(k.link)}"><b>${esc(k.cve)}</b>${k.ransomware ? '<span class="tag ransom">RANSOMWARE</span>' : ''}
      <small>${esc(k.vendor)} ${esc(k.product)} · added ${esc(k.added)}</small><small>${esc(k.name)}</small></li>`).join('');
  },
};

/* ================================================================ AI explanation of one story */
/* kind is 'cyber' (Cyber threats tile) or 'news' (News tile); each tile has its own card #explain-<kind>. */
const Explain = {
  current: {},
  stories(kind) { return (kind === 'news' ? GenNews.data : Cyber.data)?.news || []; },
  busy(link, kind = 'cyber') {
    const story = this.stories(kind).find(it => it.link === link);
    $$('.xp.busy').forEach(b => b.classList.remove('busy'));
    const btn = $(`.xp[data-explain="${CSS.escape(link)}"]`);
    if (btn) btn.classList.add('busy');
    this.show(kind, `<div class="explain-head"><b>${esc(story?.title || 'Explaining…')}</b></div><p class="sub">Reading the article and explaining…</p>`);
  },
  show(kind, html) {
    const box = $(`#explain-${kind}`);
    box.innerHTML = html;
    box.hidden = false;
    box.scrollTop = 0;
  },
  render(out) {
    const kind = out.kind || 'cyber';
    this.current[kind] = out;
    $$('.xp.busy').forEach(b => b.classList.remove('busy'));
    this.show(kind, `<div class="explain-head"><b>${esc(out.title)}</b>
        <button class="icon-btn sm" data-x="close" data-kind="${kind}" title="Close" aria-label="Close explanation">✕</button></div>
      <p>${esc(out.text)}</p>
      <div class="explain-acts">
        <button class="btn sm" data-x="read" data-kind="${kind}">${icon('speaker')}Read aloud</button>
        <button class="btn sm" data-x="stop" data-kind="${kind}">${icon('stop')}Stop</button>
        <button class="btn sm" data-x="open" data-kind="${kind}">Open article</button>
        <small>${esc(out.source)} · AI summary of the ${out.from === 'article' ? 'full article' : 'news-feed summary (the site blocked reading)'}</small>
      </div>`);
  },
  async run(link, kind = 'cyber') {
    if (S.maximized !== kind) maximize(kind);
    this.busy(link, kind);
    try {
      const out = await Bridge.call('news_explain', kind, link);
      this.render(out);
      if (S.settings.speak_replies) Bridge.call('say_text', out.text);
    } catch (e) {
      $$('.xp.busy').forEach(b => b.classList.remove('busy'));
      this.show(kind, `<div class="explain-head"><b>Couldn't explain this story</b><button class="icon-btn sm" data-x="close" data-kind="${kind}" aria-label="Close">✕</button></div><p>${esc(e.message)}</p>`);
    }
  },
  action(what, kind = 'cyber') {
    const cur = this.current[kind];
    if (what === 'close') { $(`#explain-${kind}`).hidden = true; Bridge.call('stop_speaking'); }
    else if (what === 'read' && cur) Bridge.call('say_text', cur.text);
    else if (what === 'stop') Bridge.call('stop_speaking');
    else if (what === 'open' && cur) Bridge.call('open_url', cur.link);
  },
};

/* ================================================================ General news */
const GenNews = {
  data: null,
  async load(force = false) {
    if (!Layout.visible('news')) return;
    try { this.data = await Bridge.call('news_list', force); }
    catch (e) { $('#genSub').textContent = e.message; return; }
    const d = this.data;
    $('#genSub').textContent = d.news.length ? `${d.news.length} stories` + (d.errors.length ? ` · ${d.errors.length} source(s) down` : '') : 'offline';
    $('#genNews').innerHTML = d.news.map(it => `<li data-link="${esc(it.link)}"><b>${esc(it.title)}</b>
      <button class="xp" data-explain="${esc(it.link)}" data-kind="news" title="AI explains this story and reads it out">${icon('sparkle')}Explain</button>
      <small>${esc(it.source)} · ${ago(it.time)}</small><p>${esc(it.summary)}</p></li>`).join('') || '<li><small>No stories loaded.</small></li>';
  },
};

/* ================================================================ PC monitor */
const PC = {
  hist: { cpu: [], gpu: [] }, timer: null,
  async load() {
    if (!Layout.visible('pc')) return;
    let s;
    try { s = await Bridge.call('pc_stats'); } catch (e) { $('#pcSub').textContent = e.message; return; }
    const push = (k, v) => { if (v != null) { this.hist[k].push([Date.now() / 1000, v]); if (this.hist[k].length > 40) this.hist[k].shift(); } };
    push('cpu', s.cpu); push('gpu', s.gpu?.util);
    const gb = b => (b / 1024 ** 3).toFixed(b >= 10 * 1024 ** 3 ? 0 : 1);
    // highIsGood: for battery a full bar is fine and a low one is the warning
    const meter = (label, value, unit, pct, extra = '', highIsGood = false) => {
      const risk = highIsGood ? 100 - pct : pct;
      const cls = risk >= 90 ? 'full' : risk >= 75 ? 'hot' : '';
      return `<div class="meter"><small>${esc(label)}</small><b>${value}<span>${unit}</span></b>
        <div class="bar" role="img" aria-label="${esc(label)} ${Math.round(pct)}%"><i class="${cls}" style="width:${Math.min(100, Math.max(0, pct))}%"></i></div>${extra}</div>`;
    };
    const parts = [];
    if (s.cpu != null) parts.push(meter('CPU', Math.round(s.cpu), '%', s.cpu, spark(this.hist.cpu)));
    if (s.gpu) {
      parts.push(meter(`GPU · ${s.gpu.name}`, Math.round(s.gpu.util ?? 0), `%${s.gpu.temp ? ` · ${Math.round(s.gpu.temp)}°C` : ''}`, s.gpu.util ?? 0, spark(this.hist.gpu)));
      parts.push(meter('GPU memory', gb(s.gpu.mem_used), ` / ${gb(s.gpu.mem_total)} GB`, s.gpu.mem_used / s.gpu.mem_total * 100));
    }
    parts.push(meter('Memory', gb(s.mem_used), ` / ${gb(s.mem_total)} GB`, s.mem_pct));
    for (const d of s.drives) parts.push(meter(`Drive ${d.drive}: used`, gb(d.free), ` GB free of ${gb(d.total)}`, (1 - d.free / d.total) * 100));
    if (s.battery != null) parts.push(meter(`Battery${s.charging ? ' · charging' : s.plugged ? ' · plugged in' : ''}`, s.battery, '%', s.battery, '', true));
    $('#pcBody').innerHTML = parts.join('');
    $('#pcSub').textContent = `up ${Math.floor(s.uptime / 86400) ? Math.floor(s.uptime / 86400) + 'd ' : ''}${Math.floor(s.uptime % 86400 / 3600)}h`;
  },
};

/* ================================================================ Network (display only - data from Sekar's Network Watch) */
const Net = {
  async load() {
    if (!Layout.visible('network')) return;
    let s;
    try { s = await Bridge.call('net_status'); } catch (e) { $('#netSub').textContent = e.message; return; }
    const body = $('#netBody');
    if (!s.running) {
      $('#netSub').textContent = 'not running';
      body.innerHTML = `<div class="net-off"><p>${s.installed ? "Sekar's Network Watch isn't running." : "This tile needs Sekar's Network Watch installed and running."}</p>
        ${s.installed ? '<button class="btn sm" data-net-open="">Start Network Watch</button>' : ''}</div>`;
      return;
    }
    if (!s.connected) { $('#netSub').textContent = 'offline'; body.innerHTML = '<div class="net-off"><p>Not connected to a network.</p></div>'; return; }
    const n = s.network, c = s.counts;
    const mbit = b => { const v = b * 8 / 1e6; return v >= 10 ? v.toFixed(0) : v.toFixed(v >= 1 ? 1 : 2); };
    $('#netSub').textContent = n.label || n.ssid || n.gateway;
    const unk = s.unapproved.slice(0, 4).map(d => `<li class="warn"><b>! ${esc(d.name)}</b><small>${esc(d.ip)} · ${esc(d.mac)}</small></li>`).join('');
    const mons = s.monitors.map(m => `<li class="${m.down ? 'bad' : ''}"><span>${m.down ? '✕' : m.ok ? '●' : '…'} ${esc(m.name)}</span><small>${m.down ? 'down' : m.ok ? (m.ms ?? 0) + ' ms' : 'checking'}</small></li>`).join('');
    body.innerHTML = `
      <div class="net-stats">
        <div><b>${c.online}</b><small>online</small></div>
        <div class="${c.unapproved ? 'warn' : ''}"><b>${c.unapproved}</b><small>${c.unapproved ? '! to approve' : 'to approve'}</small></div>
        <div><b>${mbit(s.traffic.rx)}</b><small>↓ Mbit/s</small></div>
        <div><b>${mbit(s.traffic.tx)}</b><small>↑ Mbit/s</small></div>
      </div>
      ${unk ? `<h3>Not approved</h3><ul class="net-list">${unk}</ul>${s.unapproved.length > 4 ? `<small class="net-more">+${s.unapproved.length - 4} more</small>` : ''}` : ''}
      ${mons ? `<h3>Monitors</h3><ul class="net-list mons">${mons}</ul>` : ''}
      ${s.alerts.length ? `<h3>Latest</h3><ul class="net-list">${s.alerts.slice(0, 3).map(a => `<li><span>${esc(a.text)}</span><small>${ago(a.ts)}</small></li>`).join('')}</ul>` : ''}
      ${c.unapproved ? '<button class="btn sm" data-net-open="devices">Review devices</button>' : ''}`;
  },
};
document.addEventListener('click', e => {
  const b = e.target.closest('[data-net-open], #netOpen'); if (!b) return;
  Bridge.call('net_open', b.dataset.netOpen || '').then(() => setTimeout(() => Net.load(), 4000)).catch(err => toast(err.message, 'error'));
});

/* ================================================================ Calendar */
const Cal = {
  data: null, offset: 0,                // months away from the current one (‹ › buttons)
  month() {
    const today = new Date();
    const first = new Date(today.getFullYear(), today.getMonth() + this.offset, 1);
    const days = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
    const lead = first.getDay();        // weeks start on Sunday, like most Indian wall calendars
    const names = [...Array(7)].map((_, i) => new Date(2023, 0, 1 + i).toLocaleDateString([], { weekday: 'narrow' }));
    const cells = [...Array(lead)].map(() => '<span></span>').concat([...Array(days)].map((_, i) => {
      const d = new Date(first.getFullYear(), first.getMonth(), i + 1);
      const isToday = d.toDateString() === today.toDateString();
      const weekend = d.getDay() === 0 || d.getDay() === 6;
      return `<span class="${isToday ? 'today' : ''}${weekend ? ' wkend' : ''}" ${isToday ? 'aria-current="date"' : ''}>${i + 1}</span>`;
    }));
    return `<li class="month">
      <div class="month-head"><button class="icon-btn sm" data-month="-1" aria-label="Previous month">${icon('left')}</button>
        <b>${esc(first.toLocaleDateString([], { month: 'long', year: 'numeric' }))}</b>
        <button class="icon-btn sm" data-month="1" aria-label="Next month">${icon('right')}</button>
        ${this.offset ? '<button class="btn sm" data-month="0">Today</button>' : ''}</div>
      <div class="month-grid">${names.map(n => `<em>${esc(n)}</em>`).join('')}${cells.join('')}</div>
      ${this.offset ? '' : `<p class="month-today">${esc(today.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' }))}</p>`}</li>`;
  },
  async load(force = false) {
    if (!Layout.visible('calendar')) return;
    try { this.data = await Bridge.call('calendar_events', force); }
    catch (e) { $('#calSub').textContent = e.message; return; }
    this.render();
  },
  render() {
    const d = this.data, list = $('#calList');
    if (!d) return;
    if (d.none) {                       // no calendar linked: a plain month calendar
      $('#calSub').textContent = 'Not synced · add a calendar in Settings → Tiles';
      list.innerHTML = this.month();
      return;
    }
    $('#calSub').textContent = d.errors.length ? `${d.errors.length} calendar(s) failed` : `${d.events.length} events · 7 days`;
    const now = new Date();
    let next = d.events.find(e => !e.all_day && new Date(e.start) > now);
    const byDay = {};
    for (const e of d.events) (byDay[e.start.slice(0, 10)] ||= []).push(e);
    const label = k => {
      const day = new Date(k + 'T12:00'), t = new Date(); t.setHours(12, 0, 0, 0);
      const diff = Math.round((day - t) / 86400000);
      return diff === 0 ? 'Today' : diff === 1 ? 'Tomorrow' : day.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'short' });
    };
    const hm = s => new Date(s).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    list.innerHTML = Object.keys(byDay).sort().map(k => `<li class="cal-day">${esc(label(k))}</li>` + byDay[k].map(e => {
      const st = new Date(e.start), en = new Date(e.end);
      const cls = !e.all_day && st <= now && now < en ? 'now' : e === next ? 'next' : !e.all_day && en < now ? 'past' : '';
      return `<li class="cal-ev ${cls}"><time>${e.all_day ? 'All day' : hm(e.start)}</time><b>${esc(e.title)}</b>
        <small>${e.all_day ? '' : `until ${hm(e.end)}`}${e.location ? ` · ${esc(e.location)}` : ''}</small></li>`;
    }).join('')).join('') || '<li class="cal-empty">Nothing in the next 7 days.</li>';
  },
};

/* ================================================================ Timers & reminders */
const Timers = {
  items: [],
  set(items) { this.items = items || []; this.render(); },
  fmt(secs) {
    secs = Math.max(0, Math.round(secs));
    const h = Math.floor(secs / 3600), m = Math.floor(secs % 3600 / 60), s = secs % 60;
    return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
  },
  ringing() { return this.items.filter(t => t.fired_at); },
  // Share of the time still left (1 = just started, 0 = due); red under 20 %.
  left(t, now) { const total = t.at - (t.created || t.at); return total > 0 ? Math.max(0, Math.min(1, (t.at - now) / total)) : 0; },
  render() {
    const now = Date.now() / 1000;
    $('#timerList').innerHTML = this.items.map(t => {
      const label = `${t.kind === 'reminder' ? '⏰ ' : ''}${esc(t.label)}`;
      if (t.fired_at) {
        return `<li class="timer done" data-id="${t.id}" title="Click to stop"><b>${t.kind === 'timer' ? "Time's up" : 'Reminder'}</b>
          <button class="btn sm" data-timer="snooze" title="Ring again in 5 minutes">Snooze 5</button>
          <button class="btn sm stop" data-timer="ack">Stop</button>
          <small>${label}</small></li>`;
      }
      const left = this.left(t, now), low = left < 0.2;
      const big = t.kind === 'timer' || t.at - now < 3600
        ? this.fmt(t.at - now)
        : new Date(t.at * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', ...(t.at - now > 86400 ? { weekday: 'short' } : {}) });
      return `<li class="timer${low ? ' low' : ''}" data-id="${t.id}"><b data-kind="${t.kind}"><span class="hourglass" aria-hidden="true">${icon('hourglass')}</span>${esc(big)}</b>
        <button class="icon-btn sm" data-timer="plus" title="Add a minute" aria-label="Add a minute">+1</button>
        <button class="icon-btn sm" data-timer="cancel" title="Cancel" aria-label="Cancel">✕</button>
        <small>${label}</small>
        <div class="tbar" role="img" aria-label="${Math.round(left * 100)}% of the time left"><i style="width:${(left * 100).toFixed(1)}%"></i></div></li>`;
    }).join('') || '<li class="none">No timers. Try "set a timer for 10 minutes" or "remind me at 6 pm to call Amma".</li>';
    this.alarm();
  },
  // Update in place (re-rendering every second would swallow clicks on the buttons).
  tick() {
    const now = Date.now() / 1000;
    for (const t of this.items) {
      if (t.fired_at) continue;
      const li = $(`#timerList .timer[data-id="${t.id}"]`);
      if (!li) continue;
      const left = this.left(t, now);
      li.classList.toggle('low', left < 0.2);
      $('.tbar i', li).style.width = `${(left * 100).toFixed(1)}%`;
      if (t.kind === 'timer' || t.at - now < 3600) $('b', li).lastChild.textContent = this.fmt(t.at - now);
    }
  },
  // Finished timers: the widget flashes until acknowledged; if the widget isn't on screen, a banner does.
  alarm() {
    const ring = this.ringing();
    $('.tile.timers').classList.toggle('alarm', ring.length > 0);
    const banner = $('#alarmBanner');
    const tileVisible = Layout.visible('timers') && (!S.maximized || S.maximized === 'timers');
    banner.hidden = !ring.length || tileVisible;
    if (!banner.hidden) {
      banner.innerHTML = `${icon('hourglass')}<b>${esc(ring.map(t => t.label).join(' · '))}</b>
        <span>${ring[0].kind === 'timer' ? "Time's up" : 'Reminder'}</span>
        <button class="btn sm" data-timer="snooze">Snooze 5</button><button class="btn sm stop" data-timer="ack">Stop</button>`;
    }
  },
};

/* ================================================================ Tasks (ageing list, linked to Telegram) */
const Tasks = {
  items: [],
  set(items) { this.items = items || []; this.render(); },
  render() {
    const pending = this.items.filter(t => !t.done_at), over = pending.filter(t => t.overdue).length;
    $('#taskSub').textContent = pending.length ? `${pending.length} pending${over ? ` · ${over} overdue` : ''}` : 'Nothing pending';
    $('#taskList').innerHTML = this.items.map(t => {
      if (t.done_at) {
        return `<li class="task is-done" data-id="${t.id}"><b>${esc(t.title)}</b>
          <button class="icon-btn sm" data-task="reopen" title="Not done after all" aria-label="Reopen">↺</button>
          <button class="icon-btn sm" data-task="delete" title="Delete" aria-label="Delete">✕</button>
          <small>Done · added ${esc(t.added_text)}</small></li>`;
      }
      const old = !t.overdue && (Date.now() / 1000 - t.created) > 3 * 86400;
      return `<li class="task${t.overdue ? ' over' : ''}${old ? ' old' : ''}" data-id="${t.id}"><b>${esc(t.title)}</b>
        <button class="icon-btn sm" data-task="done" title="Mark complete" aria-label="Mark complete">✓</button>
        <button class="icon-btn sm" data-task="delete" title="Delete" aria-label="Delete">✕</button>
        <small><span class="age">Pending ${esc(t.age)}</span> · added ${esc(t.added_text)}${t.due_text ? ` · ${t.overdue ? 'was due' : 'due'} ${esc(t.due_text)}` : ''}</small></li>`;
    }).join('') || '<li class="none">No tasks. Type one below, or message your Telegram bot: add: buy milk</li>';
  },
};

/* ================================================================ Layout (12 x 8 grid, editable) */
const Layout = {
  items: [], editing: false, backup: null,
  get widgets() { return S.settings?.widgets || {}; },
  get grid() { return S.settings?.grid || [12, 8]; },
  shown(id) { return this.items.some(i => i.id === id); },
  visible(id) { return this.shown(id) || S.maximized === id; },
  apply(items) {
    this.items = items.map(i => ({ ...i }));
    for (const tile of $$('.grid > .tile')) {
      const it = this.items.find(i => i.id === tile.dataset.tile);
      tile.classList.toggle('off', !it);
      tile.style.gridColumn = it ? `${it.x + 1} / span ${it.w}` : '';
      tile.style.gridRow = it ? `${it.y + 1} / span ${it.h}` : '';
    }
    if (this.editing) this.renderAdd();
    reportState();
  },
  refreshData() {
    // Widgets that were just added get their data now instead of at their next poll.
    GenNews.load(); PC.load(); Net.load(); Cal.load(); Weather.load(); Stocks.load();
    if (Layout.shown('timers')) Bridge.call('timers_list').then(t => Timers.set(t)).catch(() => {});
    if (Layout.shown('tasks')) Bridge.call('tasks_list').then(t => Tasks.set(t)).catch(() => {});
  },
  collides(cand, ignoreId) {
    return this.items.some(o => o.id !== ignoreId &&
      cand.x < o.x + o.w && o.x < cand.x + cand.w && cand.y < o.y + o.h && o.y < cand.y + cand.h);
  },
  inside(c) { return c.x >= 0 && c.y >= 0 && c.x + c.w <= this.grid[0] && c.y + c.h <= this.grid[1]; },
  pitch() {
    const g = $('#grid'), cs = getComputedStyle(g);
    const pad = parseFloat(cs.paddingLeft), gap = parseFloat(cs.columnGap);
    return { x: (g.clientWidth - pad * 2 + gap) / this.grid[0], y: (g.clientHeight - pad * 2 + gap) / this.grid[1] };
  },
  edit() {
    if (this.editing) return;
    if (S.maximized) restore();
    this.editing = true;
    this.backup = this.items.map(i => ({ ...i }));
    document.body.classList.add('editing');
    for (const tile of $$('.grid > .tile')) {
      if ($('.ed', tile)) continue;
      const name = this.widgets[tile.dataset.tile]?.name || tile.dataset.tile;
      tile.insertAdjacentHTML('beforeend', `<div class="ed ed-move"><b>${esc(name)}</b><small>drag to move</small></div>
        <button class="ed ed-remove" title="Remove ${esc(name)}" aria-label="Remove ${esc(name)}">✕</button>
        ${tile.classList.contains('custom') ? `<button class="ed ed-ai" title="Change ${esc(name)} with the widget agent">✎ Edit with AI</button>` : ''}
        <div class="ed ed-resize" title="Drag to resize" aria-hidden="true"></div>`);
    }
    $('#editBar').hidden = false;
    this.renderAdd();
  },
  renderAdd() {
    const hidden = Object.entries(this.widgets).filter(([id]) => !this.shown(id));
    $('#editAdd').innerHTML = hidden.map(([id, w]) => `<button data-add="${esc(id)}">+ ${esc(w.name)}</button>`).join('')
      + '<button data-studio class="studio-btn">✨ Create widget…</button>';
  },
  add(id) {
    const w = this.widgets[id];
    if (!this.place(id, 3, 3)) toast(`No room for ${w.name} - make a widget smaller or remove one first.`, 'err');
  },
  /* First free spot: the preferred size if it fits anywhere, else the minimum size. */
  place(id, prefW, prefH) {
    const w = this.widgets[id];
    const [W, H] = this.grid;
    for (const [cw, ch] of [[Math.max(w.min_w, prefW), Math.max(w.min_h, prefH)], [w.min_w, w.min_h]]) {
      for (let y = 0; y + ch <= H; y++) for (let x = 0; x + cw <= W; x++) {
        const c = { id, x, y, w: cw, h: ch };
        if (!this.collides(c)) { this.apply([...this.items, c]); this.refreshData(); return true; }
      }
    }
    return false;
  },
  remove(id) { this.apply(this.items.filter(i => i.id !== id)); },
  async done() {
    try { this.apply(await Bridge.call('layout_save', this.items)); toast('Layout saved'); }
    catch (e) { toast(e.message, 'err'); return; }
    this.close();
  },
  cancel() { this.apply(this.backup); this.close(); },
  reset() { this.apply(S.settings.default_layout); this.refreshData(); },
  close() {
    this.editing = false;
    document.body.classList.remove('editing');
    $('#editBar').hidden = true;
    S.settings.layout = this.items;
    if (S.maximized === 'stocks') Stocks.drawChart();
  },
  pointerDown(e) {
    const handle = e.target.closest('.ed-move, .ed-resize');
    if (!handle || !this.editing) return;
    const tile = handle.closest('.tile'), id = tile.dataset.tile;
    const start = this.items.find(i => i.id === id);
    if (!start) return;
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);
    const resize = handle.classList.contains('ed-resize');
    const p = this.pitch(), min = this.widgets[id];
    let cand = { ...start };
    tile.classList.add('dragging');
    const move = ev => {
      const dx = Math.round((ev.clientX - e.clientX) / p.x), dy = Math.round((ev.clientY - e.clientY) / p.y);
      cand = resize
        ? { ...start, w: Math.max(min.min_w, start.w + dx), h: Math.max(min.min_h, start.h + dy) }
        : { ...start, x: start.x + dx, y: start.y + dy };
      const ok = this.inside(cand) && !this.collides(cand, id);
      tile.classList.toggle('bad', !ok);
      // Preview clamped to the grid, so an out-of-bounds drag doesn't add extra grid tracks.
      const w = Math.min(cand.w, this.grid[0]), h = Math.min(cand.h, this.grid[1]);
      const x = Math.min(Math.max(0, cand.x), this.grid[0] - w), y = Math.min(Math.max(0, cand.y), this.grid[1] - h);
      tile.style.gridColumn = `${x + 1} / span ${w}`;
      tile.style.gridRow = `${y + 1} / span ${h}`;
    };
    const up = () => {
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', up);
      handle.removeEventListener('pointercancel', up);
      tile.classList.remove('dragging', 'bad');
      const ok = this.inside(cand) && !this.collides(cand, id);
      this.apply(this.items.map(i => (i.id === id && ok ? cand : i)));   // refused moves snap back
      if (!ok) toast('That spot is taken - widgets can\'t overlap.');
      if (id === 'stocks' || id === 'weather') { Stocks.render(); Weather.renderFull(); }
    };
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', up);
    handle.addEventListener('pointercancel', up);
  },
};

/* ================================================================ Weather */
const Weather = {
  data: null,
  async load(force = false) {
    if (!S.settings?.weather_label) {
      $('#wxPlace').textContent = 'Set your city';
      $('#wxTemp').textContent = '--°';
      $('#wxRange').textContent = '';
      $('#wxIc').innerHTML = icon('cloudsun');
      return;
    }
    try { this.data = await Bridge.call('weather_now', force); }
    catch (e) { $('#wxPlace').textContent = 'Weather offline'; return; }
    const w = this.data, today = w.days[0];
    $('#wxIc').innerHTML = icon(w.icon === 'sun' && !w.is_day ? 'moon' : w.icon);
    $('#wxTemp').textContent = `${Math.round(w.temp)}°`;
    $('#wxPlace').textContent = `${w.place.split(',')[0]} · ${w.label}`;
    $('#wxRange').textContent = today ? `H ${Math.round(today.max)}° · L ${Math.round(today.min)}°${today.rain ? ` · ${today.rain}% rain` : ''}` : '';
    $('#wxBtn').title = `${w.place}: ${w.label}, ${Math.round(w.temp)}${w.unit}`;
    if (Layout.visible('weather')) this.renderFull();
  },
  renderFull() {
    const w = this.data, body = $('#wxBody');
    if (!w) {
      body.innerHTML = `<div class="wx-empty">${S.settings?.weather_label ? 'Loading the weather…' : 'Set your city in Settings → Tiles to see the weather.'}</div>`;
      return;
    }
    $('#wxSub').textContent = `${w.place} · updated ${new Date(w.fetched * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    const day = d => new Date(d + 'T12:00').toLocaleDateString([], { weekday: 'short' });
    const hm = t => new Date(t).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    body.innerHTML = `
      <div class="wx-now">${icon(w.icon === 'sun' && !w.is_day ? 'moon' : w.icon)}
        <b>${Math.round(w.temp)}${esc(w.unit)}</b><span class="lbl">${esc(w.label)}</span>
        <dl><dt>Feels like</dt><dd>${Math.round(w.feels)}${esc(w.unit)}</dd>
          <dt>Humidity</dt><dd>${w.humidity}%</dd>
          <dt>Wind</dt><dd>${Math.round(w.wind)} ${esc(w.wind_unit)}</dd>
          ${w.days[0] ? `<dt>Sunrise</dt><dd>${hm(w.days[0].sunrise)}</dd><dt>Sunset</dt><dd>${hm(w.days[0].sunset)}</dd>` : ''}</dl></div>
      <div class="wx-charts"><h3>Temperature · next 24 hours</h3><div class="wx-temp" id="wxTempChart"></div>
        <h3>Chance of rain</h3><div class="wx-rain" id="wxRainChart"></div></div>
      <div class="wx-days">${w.days.map((d, i) => `<div class="wx-day"><b>${i ? day(d.date) : 'Today'}</b>${icon(d.icon)}
        <span>${Math.round(d.max)}° / ${Math.round(d.min)}°</span><small>${esc(d.label)}</small><small>${d.rain ?? 0}% rain</small></div>`).join('')}</div>`;
    const pts = w.hours.map(h => [new Date(h.time).getTime() / 1000, h.temp]);
    requestAnimationFrame(() => {
      lineChart($('#wxTempChart'), pts, '1d', v => `${Math.round(v)}°`);
      rainBars($('#wxRainChart'), w.hours);
    });
  },
};
function rainBars(box, hours) {
  const W = box.clientWidth || 600, H = box.clientHeight || 120, L = 8, R = 64, T = 6, B = 20;
  const n = hours.length, slot = (W - L - R) / n, bw = Math.max(3, slot - 2);
  const y = v => T + (1 - v / 100) * (H - T - B);
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Chance of rain by hour">
    ${[0, 50, 100].map(v => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--grid)"/>
      <text x="${W - R + 8}" y="${y(v) + 4}" fill="var(--ink-3)" font-size="11">${v}%</text>`).join('')}
    ${hours.map((h, i) => { const top = y(h.rain || 0), ht = Math.max(0, H - B - top);
      return `<path d="M${L + i * slot + 1},${H - B}V${top + Math.min(4, ht)}q0,-4 4,-4h${Math.max(0, bw - 8)}q4,0 4,4V${H - B}Z" fill="var(--series)" opacity="${ht ? 1 : 0}"/>
      <rect x="${L + i * slot}" y="${T}" width="${slot}" height="${H - T - B}" fill="transparent" data-i="${i}"/>`; }).join('')}
    ${[0, Math.floor(n / 2), n - 1].map((i, k) => `<text x="${L + i * slot + slot / 2}" y="${H - 5}" fill="var(--ink-3)" font-size="11" text-anchor="${k === 0 ? 'start' : k === 2 ? 'end' : 'middle'}">${esc(new Date(hours[i].time).toLocaleTimeString([], { hour: 'numeric' }))}</text>`).join('')}
  </svg><div class="tip"></div>`;
  const svg = $('svg', box), tip = $('.tip', box);
  svg.addEventListener('pointermove', e => {
    const i = e.target.dataset?.i;
    if (i == null) { tip.style.display = 'none'; return; }
    const h = hours[i], r = svg.getBoundingClientRect();
    tip.innerHTML = `<b>${h.rain ?? 0}%</b>${esc(new Date(h.time).toLocaleTimeString([], { weekday: 'short', hour: 'numeric' }))}`;
    tip.style.left = ((L + i * slot + slot / 2) * r.width / W) + 'px';
    tip.style.top = (y(h.rain || 0) * r.height / H) + 'px';
    tip.style.display = 'block';
  });
  svg.addEventListener('pointerleave', () => { tip.style.display = 'none'; });
}

/* ================================================================ WhatsApp chats */
function renderChats(r) {
  const list = $('#waChats'), status = $('#waStatus');
  const unread = (r.chats || []).filter(c => c.unread);
  if (r.state === 'browser') { status.textContent = 'Chats show in the dashboard app'; list.innerHTML = ''; return; }
  if (r.state === 'qr') { status.textContent = 'Not linked - open it and scan the QR code'; list.innerHTML = ''; return; }
  if (r.state === 'loading' || r.state === 'off') { status.textContent = 'Connecting…'; list.innerHTML = ''; return; }
  if (r.state !== 'ok') { status.textContent = "Can't read chats - open WhatsApp"; list.innerHTML = ''; return; }
  status.textContent = unread.length ? `${unread.length} unread chat${unread.length > 1 ? 's' : ''}` : 'No unread messages';
  const show = unread.length ? unread : (r.chats || []).slice(0, 4);
  list.innerHTML = show.map(c => `<li><b>${esc(c.name)}</b><small>${esc(c.time)}</small>
    <span>${esc(c.preview)}</span>${c.unread ? `<em class="badge">${c.unread}</em>` : ''}</li>`).join('')
    || '<li><span class="none">No chats.</span></li>';
}

/* ================================================================ Mute */
function setMuted(muted) {
  const b = $('#muteBtn');
  b.innerHTML = icon(muted ? 'speakerOff' : 'speaker');
  b.setAttribute('aria-pressed', muted ? 'true' : 'false');
  b.title = muted ? 'Spoken replies are muted - click to unmute' : 'Mute spoken replies';
  if (S.settings) S.settings.speak_replies = !muted;
}

/* ================================================================ Assistant log + voice bar */
function logLine(kind, text, meta = '') {
  const log = $('#log');
  $('.empty', log)?.remove();
  const li = document.createElement('li');
  li.className = kind;
  li.innerHTML = esc(text) + (meta ? `<small>${esc(meta)}</small>` : '');
  log.append(li);
  while (log.children.length > 40) log.firstChild.remove();
  log.scrollTop = log.scrollHeight;
}
const VOICE_LABEL = { off: 'Voice off', starting: 'Starting voice…', listening: 'Listening for', recording: 'Listening… speak now',
  transcribing: 'Understanding…', thinking: 'Thinking…', error: 'Voice problem' };
let voicePopTimer = null;
/* The mic shows the state by colour; the text bubble under it appears only while something is happening
   (and for a few seconds after a reply), so the header stays compact. Hovering the mic shows it too. */
function popVoice(ms) {
  const bar = $('#voiceBar');
  bar.classList.add('show');
  clearTimeout(voicePopTimer);
  if (ms) voicePopTimer = setTimeout(() => bar.classList.remove('show'), ms);
}
function setVoice(v) {
  const bar = $('#voiceBar');
  bar.dataset.state = v.state;
  let label = VOICE_LABEL[v.state] || v.state;
  if (v.state === 'listening') label += ` "${v.detail || 'Hey Jarvis'}"`;
  $('#voiceState').textContent = label;
  $('#micBtn').title = `${label} · click to talk (Ctrl+Alt+Space)`;
  if ((v.state === 'error' || v.state === 'starting') && v.detail) $('#voiceLine').textContent = v.detail;
  if (['recording', 'transcribing', 'thinking'].includes(v.state)) { $('#voiceLine').textContent = v.state === 'recording' ? 'Speak now…' : $('#voiceLine').textContent; popVoice(0); }
  else if (v.state === 'error') popVoice(8000);
}

/* ================================================================ Custom widgets (made in Widget Studio)
   Each runs in <iframe sandbox="allow-scripts"> (opaque origin: no access to this page, its bridge or storage).
   It reaches the dashboard only through these postMessages; the reply always goes back to the same frame. */
const Custom = {
  frames: new Map(),        // contentWindow -> {kind: 'widget'|'draft', ref, el, refresh, timer, onReady, onError}
  waiting: new Map(),       // summary/probe request id -> resolve
  seq: 0,
  saidAt: 0,
  list() { return Object.entries(S.settings?.widgets || {}).filter(([, w]) => w.custom); },
  meta(id) { return (S.settings?.custom_widgets || []).find(m => 'cw:' + m.id === id); },
  // One <section> per kept widget; the frame inside only exists while the widget is on screen.
  sync() {
    const ids = new Set(this.list().map(([id]) => id));
    for (const tile of $$('.grid > .tile.custom')) if (!ids.has(tile.dataset.tile)) { this.unload(tile); tile.remove(); }
    for (const [id, w] of this.list()) {
      let tile = $(`.grid > .tile[data-tile="${CSS.escape(id)}"]`);
      if (!tile) {
        $('#grid').insertAdjacentHTML('beforeend', `<section class="tile custom off" data-tile="${esc(id)}">
          <div class="tile-head"><h2>${esc(w.name)}</h2><span class="sub">${esc(this.meta(id)?.description || '')}</span>
          <div class="head-acts"><button class="icon-btn sm max-btn" title="Maximize" aria-label="Maximize">${icon('max')}</button></div></div>
          <div class="cw-body"></div></section>`);
      } else {
        $('h2', tile).textContent = w.name;
      }
    }
    this.mountVisible();
  },
  mountVisible() {
    for (const tile of $$('.grid > .tile.custom')) {
      const id = tile.dataset.tile, on = Layout.visible(id);
      const frame = $('iframe', tile);
      if (on && !frame) this.mount(tile, 'widget', id.slice(3), `/cw/${id.slice(3)}/frame`);
      else if (!on && frame) this.unload(tile);
    }
    this.resizeAll();
  },
  mount(container, kind, ref, src, hooks = {}) {
    const body = $('.cw-body', container) || container;
    body.innerHTML = '';
    const f = document.createElement('iframe');
    f.setAttribute('sandbox', 'allow-scripts');            // never add allow-same-origin
    f.setAttribute('referrerpolicy', 'no-referrer');
    f.setAttribute('title', kind === 'draft' ? 'Widget preview' : $('h2', container)?.textContent || 'Widget');
    f.className = 'cw-frame';
    body.append(f);
    const meta = kind === 'widget' ? this.meta('cw:' + ref) : hooks.manifest;
    const rec = { kind, ref, el: f, refresh: meta?.refresh_seconds || 0, timer: null, ...hooks };
    if (rec.refresh) rec.timer = setInterval(() => { if (!document.hidden) this.post(f, { type: 'refresh' }); }, rec.refresh * 1000);
    f.addEventListener('load', () => this.resize(f));
    f.src = src;
    this.frames.set(f.contentWindow, rec);
    return f;
  },
  unload(container) {
    const f = $('iframe', container);
    if (!f) return;
    for (const [win, rec] of this.frames) if (rec.el === f) { clearInterval(rec.timer); this.frames.delete(win); }
    f.remove();
  },
  post(frame, msg) { frame.contentWindow?.postMessage({ __w: 1, ...msg }, '*'); },
  size(frame) {
    const tile = frame.closest('.tile');
    const it = tile && Layout.items.find(i => i.id === tile.dataset.tile);
    if (tile?.classList.contains('max')) return { w: 12, h: 8, maximized: true };
    if (it) return { w: it.w, h: it.h, maximized: false };
    const p = $('.studio-preview'); return { w: Number(p?.dataset.w || 3), h: Number(p?.dataset.h || 3), maximized: false };
  },
  resize(frame) { this.post(frame, { type: 'resize', size: this.size(frame) }); },
  resizeAll() { for (const rec of this.frames.values()) this.resize(rec.el); },
  ask(frame, type) {        // summary / probe: ask the widget, wait for its answer
    const req = ++this.seq;
    return new Promise(resolve => {
      this.waiting.set(req, resolve);
      this.post(frame, { type, req });
      setTimeout(() => { if (this.waiting.delete(req)) resolve(null); }, 4000);
    });
  },
  async readAloud(id) {
    const tile = $(`.grid > .tile[data-tile="${CSS.escape('cw:' + id)}"]`);
    let frame = tile && $('iframe', tile);
    if (!frame) { maximize('cw:' + id); await new Promise(r => setTimeout(r, 2500)); frame = tile && $('iframe', tile); }
    const r = frame && await this.ask(frame, 'summary');
    const text = r?.text || "That widget didn't give me a summary.";
    logLine('ai', text, this.meta('cw:' + id)?.name || 'widget');
    Bridge.call('say_text', text);
  },
  async onMessage(e) {
    const rec = this.frames.get(e.source);
    const m = e.data;
    if (!rec || !m || m.__w !== 1 || typeof m.type !== 'string') return;      // only our own frames
    const reply = (value, error) => e.source.postMessage({ __w: 1, type: 'reply', id: m.id, value, error }, '*');
    try {
      switch (m.type) {
        case 'hello': this.resize(rec.el); break;
        case 'fetch':
          if (typeof m.url !== 'string') throw new Error('Bad request.');
          reply(await Bridge.call('widget_fetch', rec.kind, rec.ref, m.url, m.opts || {}));
          break;
        case 'store':
          if (!['get', 'set'].includes(m.op)) throw new Error('Bad request.');
          reply(await Bridge.call('widget_store', rec.kind, rec.ref, m.op, String(m.key), m.value ?? null));
          break;
        case 'say':                          // at most one sentence every 10 s, and never from a hidden preview
          if (Date.now() - this.saidAt > 10000 && typeof m.text === 'string') { this.saidAt = Date.now(); Bridge.call('widget_say', m.text); }
          break;
        case 'ready': rec.onReady?.(); break;
        case 'error': rec.onError?.(String(m.message || 'error').slice(0, 500)); break;
        case 'summary': case 'probe': { const r = this.waiting.get(m.req); if (r) { this.waiting.delete(m.req); r(m); } break; }
      }
    } catch (err) { if (m.id) reply(null, err.message); }
  },
};
window.addEventListener('message', e => Custom.onMessage(e));

/* ================================================================ Widget Studio */
const Studio = {
  s: null, busy: false, fixRounds: 0, errors: [], version: 0,
  async open({ id = null, request = '' } = {}) {
    if (Layout.editing) await Layout.done();
    if (this.s) await this.close(true);
    try { this.s = await Bridge.call('widget_studio_open', id ? id.replace(/^cw:/, '') : null); }
    catch (e) { return toast(e.message, 'err'); }
    this.render();
    $('#studio').showModal();
    this.sizePreview();                  // needs the dialog on screen to measure the stage
    if (this.s.manifest) this.preview();
    if (request) this.send(request);
    else $('#studioInput').focus();
  },
  render() {
    const s = this.s, m = s.manifest;
    const w = m?.default_w || 3, h = m?.default_h || 3;
    $('#studio').innerHTML = `<div class="studio-wrap">
      <div class="studio-side">
        <div class="set-head"><h2>${esc(m?.name || 'New widget')}</h2><span class="sub">Widget Studio</span></div>
        <ol class="studio-chat" id="studioChat">${s.history.length ? '' : `<li class="hint">Describe the widget you want, e.g.
          <i>"Bitcoin price in rupees with a 24-hour chart"</i>, <i>"countdown to Diwali"</i> or <i>"a water tracker with + and − buttons"</i>.</li>`}</ol>
        <div class="studio-keys" id="studioKeys"></div>
        <form class="studio-ask" id="studioForm" autocomplete="off">
          <input id="studioInput" placeholder="${m ? 'Ask for a change… e.g. make the price bigger' : 'Describe a widget…'}" aria-label="Describe the widget or a change">
          <button class="btn primary" id="studioSend">Send</button></form>
        <div class="studio-foot">
          ${s.existing ? '<button type="button" class="btn sm" data-st="export">Export</button><button type="button" class="btn sm danger" data-st="delete">Delete widget</button>'
                       : '<button type="button" class="btn sm" data-st="import">Import a widget file…</button>'}
          <span class="grow"></span>
          <button type="button" class="btn sm" data-st="close">${s.existing ? 'Close' : 'Discard'}</button>
          <button type="button" class="btn sm primary" data-st="keep" ${m ? '' : 'disabled'}>${s.existing ? 'Save changes' : 'Keep'}</button>
        </div>
      </div>
      <div class="studio-main">
        <div class="studio-bar"><span id="studioStatus" class="sub">${m ? '' : 'Nothing built yet'}</span><span class="grow"></span>
          <label>Preview size <select id="studioW">${[2, 3, 4, 5, 6, 8, 12].map(n => `<option ${n === w ? 'selected' : ''}>${n}</option>`).join('')}</select> ×
          <select id="studioH">${[2, 3, 4, 5, 6, 8].map(n => `<option ${n === h ? 'selected' : ''}>${n}</option>`).join('')}</select> cells</label></div>
        <div class="studio-stage"><section class="tile studio-preview" data-w="${w}" data-h="${h}"><div class="tile-head"><h2>${esc(m?.name || 'Preview')}</h2></div><div class="cw-body"></div></section></div>
        <div class="studio-perm" id="studioPerm"></div>
      </div></div>
      <input type="file" id="studioFile" accept=".dashwidget,application/json" hidden>`;
    for (const h of s.history) this.chat(h.role, h.text);
    this.sizePreview();
    this.renderKeys();
    $('#studioForm').addEventListener('submit', e => { e.preventDefault(); const t = $('#studioInput').value.trim(); if (t) { $('#studioInput').value = ''; this.send(t); } });
    $('#studioW').addEventListener('change', () => this.sizePreview());
    $('#studioH').addEventListener('change', () => this.sizePreview());
    $('#studioFile').addEventListener('change', e => this.importFile(e.target.files[0]));
  },
  chat(role, text, cls = '') {
    const ol = $('#studioChat');
    $('.hint', ol)?.remove();
    const li = document.createElement('li');
    li.className = `${role} ${cls}`;
    li.textContent = text;
    ol.append(li);
    ol.scrollTop = ol.scrollHeight;
    return li;
  },
  status(text, kind = '') { const el = $('#studioStatus'); el.textContent = text; el.className = `sub ${kind}`; },
  sizePreview() {
    const p = $('.studio-preview'), pitch = Layout.pitch(), gap = 10;
    const w = Number($('#studioW').value), h = Number($('#studioH').value);
    const stage = $('.studio-stage');
    const scale = Math.min(1, (stage.clientWidth - 8) / (w * pitch.x), (stage.clientHeight - 8) / (h * pitch.y));
    p.dataset.w = w; p.dataset.h = h;
    p.style.width = `${w * pitch.x - gap}px`; p.style.height = `${h * pitch.y - gap}px`;
    p.style.transform = scale > 0 && scale < 1 ? `scale(${scale})` : '';   // shrink a big preview to fit
    const f = $('iframe', p); if (f) Custom.resize(f);
  },
  async send(text, problems = null, echo = true) {
    if (this.busy) return;
    this.busy = true;
    $('#studioSend').disabled = true;
    if (text) { if (echo) this.chat('user', text); this.fixRounds = 0; }
    const working = this.chat('agent', problems ? 'Fixing a problem the preview found…' : 'Building… this takes up to a minute.', 'working');
    this.status('Working…');
    let r;
    try { r = await Bridge.call('widget_studio_send', this.s.session, text, problems); }
    catch (e) { working.remove(); this.chat('agent', e.message, 'err'); this.status('Failed', 'err'); return this.done(); }
    working.remove();
    if (r.need_key) { this.askKey(r, text); this.status('Add an API key to continue'); return this.done(); }
    this.s = { ...this.s, ...r };
    if (r.question) { this.chat('agent', r.question); this.status('Waiting for your answer'); return this.done(); }
    this.chat('agent', r.note || 'Done.');
    $('#studio .set-head h2').textContent = r.manifest.name;
    $('.studio-preview h2').textContent = r.manifest.name;
    $('[data-st="keep"]').disabled = false;
    this.renderKeys();
    this.done();
    this.preview(r.model);
  },
  done() { this.busy = false; const b = $('#studioSend'); if (b) b.disabled = false; },
  // Load the draft in the preview frame and check it: it must call Widget.ready(), throw no errors and show something.
  preview(model) {
    const p = $('.studio-preview');
    this.errors = [];
    let finished = false;
    const finish = async ready => {
      if (finished) return;
      finished = true;
      const probe = await Custom.ask(f, 'probe');
      if (probe && !probe.nodes && !probe.textLength) this.errors.push('The widget shows nothing (empty page).');
      if (!ready && !this.errors.length) this.errors.push('The widget never called Widget.ready().');
      const problems = [...new Set(this.errors)];
      if (problems.length && this.fixRounds < 2) {
        this.fixRounds++;
        this.chat('agent', `Preview problem: ${problems[0]}`, 'err');
        return this.send(null, problems);
      }
      const left = this.s.problems || [];
      this.status(problems.length ? `Problems: ${problems.join(' ')}` : left.length ? left.join(' ') : `Self-check passed${model ? ` · ${model}` : ''}`,
        problems.length ? 'err' : 'ok');
    };
    const f = Custom.mount(p, 'draft', this.s.session, `/cw/draft/${this.s.session}/frame?v=${++this.version}`, {
      manifest: this.s.manifest,
      onReady: () => setTimeout(() => finish(true), 1500),      // give it a moment to report fetch errors
      onError: msg => { this.errors.push(msg); },
    });
    this.status('Checking the preview…');
    setTimeout(() => finish(false), 8000);
  },
  renderKeys() {
    const m = this.s.manifest, box = $('#studioKeys');
    if (!m || !m.secrets.length) { box.innerHTML = ''; return; }
    box.innerHTML = `<b>Keys this widget needs</b> <small>(saved for this widget on this PC only)</small>` + m.secrets.map(n =>
      `<form class="keyrow" data-key="${esc(n)}"><label>${esc(n)}</label>
        <input type="password" placeholder="${this.s.keys?.[n] ? 'saved - paste to replace' : 'paste the key'}" autocomplete="off">
        <button class="btn sm">Save</button></form>`).join('');
    for (const form of $$('.keyrow', box)) form.addEventListener('submit', async e => {
      e.preventDefault();
      try { this.s = { ...this.s, ...await Bridge.call('widget_studio_key', this.s.session, form.dataset.key, $('input', form).value) }; this.renderKeys(); this.preview(); }
      catch (err) { toast(err.message, 'err'); }
    });
  },
  // No key for the widget agent on this PC yet: ask for one (each person uses their own key).
  askKey(r, retryText) {
    const li = this.chat('agent', '', 'keyask');
    li.innerHTML = `The widget agent needs your own ${esc(r.provider)} API key on this PC.
      ${r.provider === 'Google Gemini' ? 'Get one free at <b>aistudio.google.com/apikey</b>.' : ''}
      <form class="keyrow"><input type="password" placeholder="Paste your API key" autocomplete="off" aria-label="API key"><button class="btn sm primary">Save key</button></form>
      ${r.reuse_available ? '<label class="check"><input type="checkbox" class="reuse"> Or use the key already saved on this PC for speech-to-text</label>' : ''}
      <small>It's stored in Windows Credential Manager for your Windows account only - never in the dashboard's files or widgets.</small>`;
    $('form', li).addEventListener('submit', async e => {
      e.preventDefault();
      const key = $('input[type=password]', li).value.trim(), reuse = $('.reuse', li)?.checked;
      if (!key && !reuse) return;
      try {
        S.settings = await Bridge.call('settings_save', key ? { widget_agent_key_new: key } : { widget_reuse_key: true });
        li.remove();
        this.chat('agent', 'Key saved.');
        if (retryText) this.send(retryText, null, false);     // your request is already in the chat
      } catch (err) { toast(err.message, 'err'); }
    });
  },
  // Keep: show what the widget will be allowed to do, then add it to the dashboard.
  keep() {
    const m = this.s.manifest, missing = m.secrets.filter(n => !this.s.keys?.[n]);
    $('#studioPerm').innerHTML = `<div class="perm"><b>Before adding “${esc(m.name)}”</b>
      <p>${m.domains.length ? `It will read data from: <b>${m.domains.map(esc).join(', ')}</b>` : 'It doesn\'t use the internet.'}</p>
      ${m.secrets.length ? `<p>It uses ${m.secrets.length === 1 ? 'a key' : 'keys'}: ${m.secrets.map(esc).join(', ')}${missing.length ? ` - <b>add ${missing.map(esc).join(', ')} on the left first</b>` : ' (saved)'}</p>` : ''}
      <p class="sub">It runs sandboxed: no access to your files, your other keys or the rest of the dashboard.</p>
      <div class="row"><button type="button" class="btn sm" data-st="perm-no">Not yet</button>
        <button type="button" class="btn sm primary" data-st="perm-yes" ${missing.length ? 'disabled' : ''}>Allow and ${this.s.existing ? 'save' : 'add'}</button></div></div>`;
  },
  async approve() {
    try {
      const r = await Bridge.call('widget_keep', this.s.session);
      S.settings = r.settings;
      const wasNew = !this.s.existing;
      this.s.existing = true;
      Custom.sync();
      let placed = true;
      if (wasNew) {
        const m = r.manifest;
        placed = Layout.place(r.id, m.default_w, m.default_h);
        if (placed) await Bridge.call('layout_save', Layout.items).then(items => Layout.apply(items)).catch(() => {});
      } else {
        for (const tile of $$(`.grid > .tile[data-tile="${CSS.escape(r.id)}"]`)) Custom.unload(tile);
        Custom.mountVisible();
      }
      await this.close();
      if (placed) toast(`${r.manifest.name} ${wasNew ? 'added' : 'saved'}`);
      else {                                 // the grid is full: kept, and waiting in the layout editor's add list
        toast(`${r.manifest.name} is saved, but the screen is full - make a widget smaller or remove one, then add it.`, 'err');
        Layout.edit();
      }
    } catch (e) { toast(e.message, 'err'); }
  },
  async remove() {
    if (!confirmDanger(`Delete “${this.s.manifest?.name}”? Its saved data and keys are removed too.`)) return;
    try { S.settings = await Bridge.call('widget_delete', this.s.id); this.s.existing = false; Custom.sync(); Layout.apply(S.settings.layout); this.close(); }
    catch (e) { toast(e.message, 'err'); }
  },
  async exportFile() {
    try {
      const r = await Bridge.call('widget_export', this.s.id);
      if (r.text) {                          // browser preview: download it
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([r.text], { type: 'application/json' }));
        a.download = r.filename; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      } else if (r.saved) toast('Widget exported (without any keys)');
    } catch (e) { toast(e.message, 'err'); }
  },
  async importFile(file) {
    if (!file) return;
    try {
      const r = await Bridge.call('widget_import', await file.text());
      S.settings = r.settings;
      Custom.sync();
      const placed = Layout.place(r.id, r.manifest.default_w, r.manifest.default_h);
      if (placed) Layout.apply(await Bridge.call('layout_save', Layout.items));
      await this.close();
      toast(`${r.manifest.name} imported${placed ? '' : ' - the screen is full, add it from the layout editor'}` +
            `${r.manifest.secrets.length ? ' - add its keys with ✎ Edit with AI' : ''}`);
      if (!placed) Layout.edit();
    } catch (e) { toast(e.message, 'err'); }
  },
  async close() {
    const s = this.s;
    this.s = null;
    Custom.unload($('.studio-preview') || document.createElement('div'));
    $('#studio').close();
    $('#studio').innerHTML = '';
    if (s) await Bridge.call('widget_studio_close', s.session).catch(() => {});
  },
  click(e) {
    const b = e.target.closest('[data-st]');
    if (!b) return;
    ({ keep: () => this.keep(), 'perm-yes': () => this.approve(), 'perm-no': () => { $('#studioPerm').innerHTML = ''; },
       close: () => this.close(), delete: () => this.remove(), export: () => this.exportFile(),
       import: () => $('#studioFile').click() })[b.dataset.st]?.();
  },
};
function confirmDanger(text) { return window.confirm(text); }

/* ================================================================ Events from Python */
const Events = {
  ui(d) {
    switch (d.do) {
      case 'play': Music.play(d.items); break;
      case 'pause': Music.pause(); break;
      case 'resume': Music.resume(); break;
      case 'next': Music.go(1); break;
      case 'previous': Music.go(-1); break;
      case 'volume': Music.volume(d.level); break;
      case 'duck': Music.duck(d.on); break;
      case 'maximize': maximize(d.tile); break;
      case 'restore': restore(); break;
      case 'next_photo': Photos.step(1); break;
      case 'previous_photo': Photos.step(-1); break;
      case 'stock_focus':
        if (!Stocks.list.some(q => q.symbol === d.symbol)) Stocks.list.unshift({ symbol: d.symbol, name: d.symbol, points: [] });
        Stocks.setFocus(d.symbol); maximize('stocks'); break;
      case 'watchlist': Stocks.load(); break;
      case 'settings': if (!$('#settings').open) Settings.open(); break;
      case 'weather': Weather.load(true); break;
      case 'explaining': if (S.maximized !== (d.kind || 'cyber')) maximize(d.kind || 'cyber'); Explain.busy(d.link, d.kind || 'cyber'); break;
      case 'explained': Explain.render(d); break;
      case 'toast': toast(d.text); break;
      case 'edit_layout': if (!$('#settings').open) Layout.edit(); break;
      case 'widget_studio':
        if (Studio.s && !d.id) { if (d.request) Studio.send(d.request); }
        else Studio.open({ id: d.id ? 'cw:' + d.id : null, request: d.request || '' });
        break;
      case 'read_widget': Custom.readAloud(d.id); break;
      case 'briefing': break;            // the reply event logs it (as a briefing card)
      case 'reload_player': if (Music.current()) Music.load(Music.i); break;
      case 'whatsapp': if (SERVE) window.open('https://web.whatsapp.com/', '_blank'); break;
    }
  },
  heard(d) {
    $('#voiceLine').textContent = `“${d.text}”`;
    logLine('you', d.text, d.spoken ? `spoken · ${d.how === 'cloud' ? 'cloud speech-to-text' : d.how || ''}` : 'typed');
    setVoice({ state: 'thinking' });
  },
  reply(d) {
    if (d.text) $('#voiceLine').textContent = d.text;
    if (d.action === 'briefing' && d.text) logLine('brief', d.text, 'briefing');
    else if (d.text || d.source === 'error') logLine(d.source === 'error' ? 'err' : 'ai', d.text || 'Done.',
      d.action === 'pc_agent' || d.source === 'agent' ? "Sekar's System Utilities" : d.source === 'ai' ? 'AI' : d.source === 'rule' ? 'command' : '');
    else logLine('ai', '✓ ' + (d.action || 'done').replace(/_/g, ' '), 'command');
    setVoice(window.__voice || { state: 'off' });
    popVoice(d.text ? Math.min(15000, 4000 + d.text.length * 40) : 2500);   // long answers stay up longer
  },
  voice(v) { window.__voice = v; setVoice(v); },
  muted(m) { setMuted(m); },
  youtube(y) { if (S.settings) S.settings.youtube_signed_in = y.signed_in; $('#musicSub').textContent = y.signed_in ? 'YouTube · signed in' : 'YouTube'; },
  whatsapp(r) { renderChats(r); },
  timers(items) { Timers.set(items); },
  tasks(items) { Tasks.set(items); },
  telegram(st) { if (S.settings) S.settings.telegram_paired = st.paired; Settings.tgStatus?.(st); },
  studio_progress(d) {                   // what the widget agent is doing right now (probing, fixing, waiting)
    if (!Studio.s || d.session !== Studio.s.session) return;
    const w = $('#studioChat .working');
    if (w) w.textContent = d.text;
    Studio.status(d.text);
  },
  async widgets_changed() {              // a widget was kept, imported or deleted (possibly from the tray / voice)
    try { S.settings = await Bridge.call('settings_get'); Custom.sync(); Layout.apply(S.settings.layout); } catch { /* next load */ }
  },
  timer_due(t) {
    logLine('ai', t.text, t.kind);
    if (S.maximized && S.maximized !== 'timers') restore();   // so the flashing widget is in view
  },
  photos(info) { Photos.info(info); },
};
window.App = { on(event, data) { const h = Events[event]; if (h) h(data); } };

async function pollEvents() {     // --serve mode only: pywebview pushes events directly
  for (;;) {
    try {
      const events = await (await fetch('/api/_events')).json();
      events.forEach(([e, d]) => App.on(e, d));
    } catch { /* server restarting */ }
    await new Promise(r => setTimeout(r, 400));
  }
}

/* ================================================================ Settings */
const Settings = {
  tab: 'ai',
  open() {
    const s = S.settings;
    const dlg = $('#settings');
    const keyField = (name, label, hint) => `<label class="field"><span>${label}${s[name + '_key'] ? ` · saved ${esc(s[name + '_key'])}` : ''}</span>
      <input type="password" name="${name}_key_new" placeholder="${s[name + '_key'] ? 'Leave blank to keep the saved key' : 'Paste key'}" autocomplete="off">
      ${hint ? `<small>${hint}</small>` : ''}</label>`;
    const opt = (v, cur, label) => `<option value="${esc(v)}" ${String(v) === String(cur) ? 'selected' : ''}>${esc(label)}</option>`;
    dlg.innerHTML = `<form method="dialog" id="setForm">
      <div class="set-head"><h2>Settings</h2><div class="set-tabs">
        ${[['ai', 'AI'], ['voice', 'Voice'], ['tiles', 'Tiles'], ['screen', 'Screen']].map(([t, l]) => `<button type="button" data-tab="${t}" class="${t === this.tab ? 'on' : ''}">${l}</button>`).join('')}</div></div>
      <div class="set-body">
        <div class="set-page ${this.tab === 'ai' ? 'on' : ''}" data-page="ai">
          <label class="field check"><input type="checkbox" name="ai_on" ${s.ai_on ? 'checked' : ''}> Use AI for anything beyond the basic commands</label>
          <div class="field"><span>Provider</span><div class="seg">
            ${[['ollama', 'Ollama (local)'], ['openai', 'OpenAI-compatible API'], ['anthropic', 'Claude']].map(([v, l]) =>
              `<label><input type="radio" name="provider" value="${v}" ${s.provider === v ? 'checked' : ''}>${l}</label>`).join('')}</div></div>
          <div class="row" data-for="ollama"><label class="field"><span>Ollama address</span><input name="ollama_host" value="${esc(s.ollama_host)}"></label>
            <label class="field"><span>Model (blank = pick automatically)</span><input name="ollama_model" value="${esc(s.ollama_model || '')}" list="modelList"></label></div>
          <div class="row" data-for="openai"><label class="field"><span>Service</span><select name="openai_preset">${opt('', '', 'Custom')}${s.presets.map(p => opt(p.base, s.openai_base, p.name)).join('')}</select></label>
            <label class="field"><span>Base URL</span><input name="openai_base" value="${esc(s.openai_base)}"></label></div>
          <div class="row" data-for="openai"><label class="field"><span>Model</span><input name="openai_model" value="${esc(s.openai_model || '')}" list="modelList"></label>${keyField('openai', 'API key', 'Shared with Storage Analyzer.')}</div>
          <div class="row" data-for="anthropic"><label class="field"><span>Model</span><select name="anthropic_model">${s.anthropic_models.map(m => opt(m, s.anthropic_model, m)).join('')}</select></label>${keyField('anthropic', 'Anthropic API key', 'Shared with Storage Analyzer.')}</div>
          <datalist id="modelList"></datalist>
          <div class="note">Now using: <b>${esc(s.ai_label || 'none')}</b>${s.ai_model ? ` · ${esc(s.ai_model)}` : ''}${s.ai_error ? `<br>${esc(s.ai_error)}` : ''}</div>
          <h3 class="set-sub">Widget agent (builds widgets in Widget Studio)</h3>
          <div class="row"><label class="field"><span>Provider</span><select name="widget_provider">${Object.entries(s.widget_providers).map(([k, v]) => opt(k, s.widget_provider, v)).join('')}</select></label>
            <label class="field"><span>Model ("auto" = best available)</span><input name="widget_model" value="${esc(s.widget_model || 'auto')}"></label></div>
          <label class="field" data-wfor="openai"><span>Base URL (OpenAI-compatible service)</span><input name="widget_base" value="${esc(s.widget_base || '')}" placeholder="${esc(s.openai_base)}"></label>
          <div data-wfor="gemini openai anthropic">${keyField('widget_agent', 'Widget agent API key', 'Your own key, stored in Windows Credential Manager for your Windows account - never in the dashboard\'s files, widgets or exports.')}
          ${s.widget_reuse_available ? `<label class="field check"><input type="checkbox" name="widget_reuse_key" ${s.widget_reuse_key ? 'checked' : ''}> If no key is set above, use the key already saved on this PC for the same service</label>` : ''}</div>
        </div>
        <div class="set-page ${this.tab === 'voice' ? 'on' : ''}" data-page="voice">
          ${s.voice_missing.length ? `<div class="note">Voice needs a few packages. In a terminal run:<br><code>pip install ${esc(s.voice_missing.join(' '))} faster-whisper piper-tts</code></div>` : ''}
          <label class="field check"><input type="checkbox" name="voice_on" ${s.voice_on ? 'checked' : ''}> Listen for the wake word</label>
          <div class="row"><label class="field"><span>Wake word</span><select name="wake_word">${Object.entries(s.wake_words).map(([k, v]) => opt(k, s.wake_word, v)).join('')}</select>
            <small>Ctrl+Alt+Space or the mic button skips the wake word.</small></label>
            <label class="field"><span>Speech-to-text</span><select name="stt_mode">${Object.entries(s.stt_modes).map(([k, v]) => opt(k, s.stt_mode, v)).join('')}</select>
            <small>Local Whisper: ${s.local_whisper ? esc(s.whisper_status) : 'not installed (pip install faster-whisper)'}</small></label></div>
          <div class="row"><label class="field"><span>Local Whisper model</span><select name="whisper_model">${Object.entries(s.whisper_models).map(([k, v]) => opt(k, s.whisper_model, v)).join('')}</select>
            <small>Downloaded on first use. Bigger is more accurate but slower.</small></label>
            <label class="field"><span>Run Whisper on</span><select name="whisper_device">${Object.entries(s.whisper_devices).map(([k, v]) => opt(k, s.whisper_device, v)).join('')}</select>
            <small>The GPU makes Large v3 Turbo fast (under a second).</small></label></div>
          <div class="row">
            <label class="field"><span>Stop listening after a pause of (seconds)</span><input type="number" name="stt_pause" min="0.6" max="5" step="0.1" value="${s.stt_pause}">
            <small>Raise it if you get cut off mid-sentence.</small></label></div>
          <div class="row"><label class="field"><span>Cloud service</span><select name="stt_preset">${opt('', '', 'Custom')}${s.stt_presets.map(p => opt(p.base, s.stt_base, p.name)).join('')}</select></label>
            <label class="field"><span>Model</span><input name="stt_model" value="${esc(s.stt_model)}"></label></div>
          <label class="field"><span>Base URL</span><input name="stt_base" value="${esc(s.stt_base)}"></label>
          ${keyField('stt', 'Speech-to-text API key', 'For OpenAI, the AI key above is used when this is blank.')}
          <label class="field check"><input type="checkbox" name="speak_replies" ${s.speak_replies ? 'checked' : ''}> Speak replies (${esc(s.tts_engine)})</label>
          <label class="field"><span>Piper voice</span><input name="tts_voice" value="${esc(s.tts_voice)}"><small>Any voice name from the Piper voice list, e.g. en_US-amy-medium, en_GB-alan-medium. Downloaded on first use.</small></label>
        </div>
        <div class="set-page ${this.tab === 'tiles' ? 'on' : ''}" data-page="tiles">
          <label class="field"><span>Photo folders (one per line; blank = ${esc(s.default_photo_folders.join(', ') || 'Pictures')})</span><textarea name="photo_folders">${esc((s.photo_folders || []).join('\n'))}</textarea></label>
          <div class="row"><label class="field"><span>Seconds per photo</span><input type="number" min="3" max="600" name="photo_seconds" value="${s.photo_seconds}"></label>
            <label class="field"><span>Photo cache size (MB)</span><input type="number" min="100" name="photo_cache_mb" value="${s.photo_cache_mb}"></label>
            <label class="field"><span>Slideshow after idle (minutes, 0 = never)</span><input type="number" min="0" name="idle_minutes" value="${s.idle_minutes}"></label></div>
          <label class="field check"><input type="checkbox" name="photo_include_cloud" ${s.photo_include_cloud ? 'checked' : ''}> Include online-only OneDrive photos (downloaded one at a time, then freed again)</label>
          <div class="row"><label class="field"><span>Weather city</span><input name="weather_city" value="${esc(s.weather_city)}" placeholder="e.g. Bengaluru">
            <small id="wxFound">${s.weather_label ? 'Using ' + esc(s.weather_label) : 'Type a city and press Find'}</small></label>
            <label class="field" style="flex:0 0 auto;justify-content:flex-end"><button type="button" class="btn" id="wxFind">Find</button></label>
            <label class="field"><span>Units</span><select name="weather_units">${opt('celsius', s.weather_units, '°C, km/h')}${opt('fahrenheit', s.weather_units, '°F, mph')}</select></label></div>
          <label class="field check"><input type="checkbox" name="whatsapp_watch" ${s.whatsapp_watch ? 'checked' : ''}> Keep WhatsApp Web open in the background to show unread chats (read-only)</label>
          <div class="field"><span>YouTube account</span><div class="row" style="align-items:center"><button type="button" class="btn" id="ytSignin" style="flex:0 0 auto">${s.youtube_signed_in ? 'Switch account' : 'Sign in to YouTube'}</button>
            <small>${s.youtube_signed_in === true ? '✓ Signed in - songs play with your account (no ads with Premium).'
              : s.youtube_signed_in === false ? 'Not signed in. Sign in, then close the sign-in window.'
              : 'Checking… Songs play with your account once you\'re signed in (no ads with Premium).'}</small></div></div>
          <label class="field"><span>Stock watchlist (Yahoo tickers, comma separated)</span><input name="watchlist" value="${esc(s.watchlist.join(', '))}">
            <small>Examples: ^GSPC (S&P 500), ^NSEI (Nifty 50), RELIANCE.NS, TSLA, BTC-USD. You can also say "add Tesla to my stocks".</small></label>
          ${keyField('youtube', 'YouTube Data API key (optional)', 'Makes song search more reliable. Free from Google Cloud Console → YouTube Data API v3.')}
          ${keyField('telegram', 'Telegram bot token (task alerts and commands)', 'In Telegram, message @BotFather, send /newbot and paste the token it gives you. Save, then press Pair and send the code to your bot. Stored encrypted like an API key.')}
          <div class="field"><span>Telegram link</span><div class="row" style="align-items:center">
            <button type="button" class="btn" id="tgPair" style="flex:0 0 auto">Pair my Telegram</button>
            <button type="button" class="btn" id="tgTest" style="flex:0 0 auto">Send test</button>
            <button type="button" class="btn danger" id="tgUnpair" style="flex:0 0 auto">Unpair</button></div>
            <small id="tgStatus">Checking…</small></div>
          <div class="row"><label class="field"><span>Daily task summary on Telegram at (blank = off)</span><input type="time" name="tasks_digest_time" value="${esc(s.tasks_digest_time || '')}"></label>
            <label class="field"><span>Repeat overdue alerts every (hours)</span><input type="number" min="1" max="168" name="tasks_repeat_hours" value="${esc(s.tasks_repeat_hours ?? 12)}"></label></div>
          <label class="field"><span>Calendars${s.calendar_names.length ? ` · saved: ${esc(s.calendar_names.join(', '))}` : ''}</span>
            <textarea name="calendars_new" placeholder="${s.calendar_names.length ? 'Leave blank to keep the saved calendars' : 'Personal | https://calendar.google.com/calendar/ical/…/basic.ics'}"></textarea>
            <small>One per line: <b>Name | private ICS link</b>. Google: calendar settings → "Secret address in iCal format". Outlook: Settings → Calendar → Shared calendars → Publish → ICS. Stored encrypted like an API key.</small></label>
          ${s.calendar_names.length ? '<label class="field check"><input type="checkbox" name="calendars_clear"> Remove the saved calendars</label>' : ''}
          <label class="field"><span>World clocks in the top bar (one per line: Name | time zone, up to 4)</span>
            <textarea name="world_clocks" id="zonesInput">${esc(s.world_clocks.map(z => z.join(' | ')).join('\n'))}</textarea>
            <small id="zonesHelp">Time zone names like America/New_York, Europe/London, Asia/Dubai, Asia/Singapore, Australia/Sydney, America/Los_Angeles, UTC.</small></label>
          <label class="field"><span>News sources (one per line: Name | RSS link)</span><textarea name="news_feeds">${esc(s.news_feeds.map(f => f.join(' | ')).join('\n'))}</textarea></label>
          <div class="row"><label class="field"><span>Morning briefing time (blank = only when asked)</span><input type="time" name="briefing_time" value="${esc(s.briefing_time)}">
            <small>Spoken the first time you use the PC after this time. Say "good morning" any time.</small></label>
            <div class="field"><span>On these days</span><div class="seg">${['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d, i) =>
              `<label><input type="checkbox" name="briefing_day" value="${i}" ${s.briefing_days.includes(i) ? 'checked' : ''}>${d}</label>`).join('')}</div></div></div>
          <label class="field"><span>Music volume while you speak or it replies: <b id="duckOut">${s.duck_level}%</b> (0 = pause)</span>
            <input type="range" name="duck_level" min="0" max="60" step="5" value="${s.duck_level}" oninput="document.getElementById('duckOut').textContent = this.value + '%'"></label>
          <div class="field"><span>Layout</span><div class="row" style="align-items:center"><button type="button" class="btn" id="setLayout" style="flex:0 0 auto">Edit layout…</button>
            <small>Move, resize, add or remove widgets. Also from the pencil button in the header, or say "edit layout".</small></div></div>
        </div>
        <div class="set-page ${this.tab === 'screen' ? 'on' : ''}" data-page="screen">
          <label class="field"><span>Show the dashboard on</span><select name="screen">${opt('', s.screen ?? '', 'Automatic (the smaller second monitor)')}${s.screens.map(x => opt(x.i, s.screen ?? '', `Screen ${x.i + 1}: ${x.label}`)).join('')}</select>
            <small>Takes effect next time the dashboard starts.</small></label>
          <div class="note">Esc restores a maximized tile. Run <code>python app.py --window</code> for a normal window.</div>
        </div>
      </div>
      <div class="set-foot"><span class="out" id="setOut"></span>
        <button type="button" class="btn" id="aiTest">Test AI</button>
        <button type="button" class="btn" value="cancel" id="setCancel">Cancel</button>
        <button type="submit" class="btn primary">Save</button></div>
    </form>`;
    const form = $('#setForm');
    const sync = () => {
      const p = form.provider.value, wp = form.widget_provider.value;
      $$('[data-for]', form).forEach(el => el.classList.toggle('on', el.dataset.for === p));
      $$('[data-wfor]', form).forEach(el => { el.hidden = !el.dataset.wfor.split(' ').includes(wp); });
    };
    sync();
    form.addEventListener('change', e => {
      if (e.target.name === 'provider' || e.target.name === 'widget_provider') sync();
      if (e.target.name === 'openai_preset' && e.target.value) {
        form.openai_base.value = e.target.value;
      }
      if (e.target.name === 'stt_preset' && e.target.value) {
        const p = s.stt_presets.find(x => x.base === e.target.value);
        form.stt_base.value = p.base; form.stt_model.value = p.model;
      }
    });
    $$('.set-tabs button', form).forEach(b => b.addEventListener('click', () => {
      this.tab = b.dataset.tab;
      $$('.set-tabs button', form).forEach(x => x.classList.toggle('on', x === b));
      $$('.set-page', form).forEach(p => p.classList.toggle('on', p.dataset.page === this.tab));
    }));
    $('#setCancel').onclick = () => dlg.close();
    $('#setLayout').onclick = () => { dlg.close(); Layout.edit(); };
    $('#wxFind').onclick = async () => {
      $('#wxFound').textContent = 'Looking…';
      try { const p = await Bridge.call('weather_find', form.weather_city.value); $('#wxFound').textContent = `Found ${p.label} - press Save to use it`; }
      catch (e) { $('#wxFound').textContent = '✗ ' + e.message; }
    };
    $('#ytSignin').onclick = async () => {
      try { const r = await Bridge.call('youtube_signin'); if (r.url) window.open(r.url, '_blank'); }
      catch (e) { toast(e.message, 'err'); }
    };
    this.tgStatus = st => {
      const el = $('#tgStatus');
      if (!el) return;
      el.textContent = st.state === 'ok' ? `✓ Connected as ${st.bot}${st.paired ? ' · your Telegram is paired' : ' · not paired yet'}`
        : st.state === 'error' ? `✗ ${st.error || 'Cannot reach Telegram'}`
        : st.state === 'connecting' ? 'Connecting…' : 'No bot token saved';
    };
    Bridge.call('telegram_status').then(st => this.tgStatus(st)).catch(() => {});
    $('#tgPair').onclick = async () => {
      try {
        const r = await Bridge.call('telegram_pair');
        $('#tgStatus').innerHTML = `Open your bot${r.bot ? ' <b>' + esc(r.bot) + '</b>' : ''} in Telegram and send: <b>/pair ${esc(r.code)}</b> (valid ${r.minutes} minutes)`;
      } catch (e) { $('#tgStatus').textContent = '✗ ' + e.message; }
    };
    $('#tgTest').onclick = async () => {
      try { await Bridge.call('telegram_test'); $('#tgStatus').textContent = '✓ Test message sent - check Telegram'; }
      catch (e) { $('#tgStatus').textContent = '✗ ' + e.message; }
    };
    $('#tgUnpair').onclick = async () => {
      try { this.tgStatus(await Bridge.call('telegram_unpair')); } catch (e) { $('#tgStatus').textContent = '✗ ' + e.message; }
    };
    $('#aiTest').onclick = async () => {
      $('#setOut').textContent = 'Testing…';
      try {
        const r = await Bridge.call('ai_test', this.collect(form));
        $('#modelList').innerHTML = r.models.map(m => `<option value="${esc(m)}">`).join('');
        $('#setOut').textContent = `✓ ${r.label} · ${r.model}: ${r.reply}`;
      } catch (e) { $('#setOut').textContent = '✗ ' + e.message; }
    };
    form.addEventListener('submit', async e => {
      e.preventDefault();
      try {
        S.settings = await Bridge.call('settings_save', this.collect(form));
        applySettings();
        dlg.close();
        toast('Settings saved');
      } catch (err) { $('#setOut').textContent = '✗ ' + err.message; }
    });
    dlg.showModal();
  },
  collect(form) {
    const f = new FormData(form);
    const out = {};
    for (const [k, v] of f.entries()) out[k] = v;
    for (const k of ['ai_on', 'voice_on', 'speak_replies', 'photo_include_cloud', 'whatsapp_watch']) out[k] = form[k].checked;
    out.calendars_clear = !!form.calendars_clear?.checked;
    out.widget_reuse_key = !!form.widget_reuse_key?.checked;
    for (const k of ['photo_seconds', 'photo_cache_mb', 'idle_minutes', 'stt_pause', 'duck_level']) out[k] = Number(out[k]) || 0;
    out.briefing_days = f.getAll('briefing_day').map(Number);
    delete out.briefing_day;
    out.news_feeds = (out.news_feeds || '').split('\n').map(l => l.split('|').map(x => x.trim()))
      .filter(p => p.length >= 2 && p[1]).map(p => [p[0], p.slice(1).join('|')]);
    const validZone = tz => { try { new Intl.DateTimeFormat([], { timeZone: tz }); return true; } catch { return false; } };
    out.world_clocks = (out.world_clocks || '').split('\n').map(l => l.split('|').map(x => x.trim())).filter(p => p.some(Boolean))
      .map(p => (p.length > 1 ? [p[0], p[1]] : ['', p[0]]));
    const bad = out.world_clocks.filter(([, tz]) => !validZone(tz)).map(([, tz]) => tz);
    if (bad.length) throw new Error(`Unknown time zone: ${bad.join(', ')} (use names like Europe/London)`);
    if (!out.calendars_new?.trim()) delete out.calendars_new;
    out.photo_folders = (out.photo_folders || '').split('\n').map(x => x.trim()).filter(Boolean);
    out.watchlist = (out.watchlist || '').split(',').map(x => x.trim()).filter(Boolean);
    out.screen = out.screen === '' ? null : Number(out.screen);
    out.ollama_model = out.ollama_model || null;
    return out;
  },
};
function applySettings() {
  const s = S.settings;
  $('#aiSub').textContent = s.ai_on ? (s.ai_label || 'AI not set up') + (s.ai_model ? ` · ${s.ai_model}` : '') : 'basic commands only';
  if (Photos.seconds !== s.photo_seconds && Photos.timer) { Photos.seconds = s.photo_seconds; Photos.schedule(); }
  setMuted(!s.speak_replies);
  tickClock();
  Custom.sync();                        // sections for widgets made in Widget Studio, before placing them
  Layout.apply(s.layout);
  Layout.refreshData();
}

/* ================================================================ Wiring */
function wire() {
  $('#micBtn').innerHTML = icon('mic');
  $('#settingsBtn').innerHTML = icon('gear');
  $$('.max-btn').forEach(b => { b.innerHTML = icon('max'); });
  $('[data-photo="prev"]').innerHTML = icon('left');
  $('[data-photo="next"]').innerHTML = icon('right');
  $('[data-music="previous"]').innerHTML = icon('prev');
  $('[data-music="next"]').innerHTML = icon('next');
  $('#playBtn').innerHTML = icon('play');
  $('.wa-ic').innerHTML = icon('chat');

  document.addEventListener('click', e => {
    const mx = e.target.closest('.max-btn');
    if (mx) { const t = mx.closest('.tile'); return t.classList.contains('max') ? restore() : maximize(t.dataset.tile); }
    const ph = e.target.closest('[data-photo]');
    if (ph) return Photos.step(ph.dataset.photo === 'next' ? 1 : -1);
    const mu = e.target.closest('[data-music]');
    if (mu) return mu.dataset.music === 'toggle' ? Music.toggle() : Music.go(mu.dataset.music === 'next' ? 1 : -1);
    const qi = e.target.closest('#queue li');
    if (qi) return Music.load(Number(qi.dataset.i));
    const st = e.target.closest('#quotes li');
    if (st) { Stocks.setFocus(st.dataset.sym); if (S.maximized !== 'stocks') maximize('stocks'); return; }
    const rg = e.target.closest('#ranges button');
    if (rg) { Stocks.range = rg.dataset.r; return Stocks.drawChart(); }
    if (e.target.closest('[data-studio]')) return Studio.open();
    if (Layout.editing) {
      const ai = e.target.closest('.ed-ai');
      if (ai) return Studio.open({ id: ai.closest('.tile').dataset.tile });
      const rm = e.target.closest('.ed-remove');
      if (rm) return Layout.remove(rm.closest('.tile').dataset.tile);
      const ad = e.target.closest('[data-add]');
      if (ad) return Layout.add(ad.dataset.add);
      return;
    }
    const xp = e.target.closest('[data-explain]');
    if (xp) return Explain.run(xp.dataset.explain, xp.dataset.kind || 'cyber');
    const xa = e.target.closest('[data-x]');
    if (xa) return Explain.action(xa.dataset.x, xa.dataset.kind || 'cyber');
    const tm = e.target.closest('[data-timer]');
    if (tm) {
      const id = tm.closest('.timer')?.dataset.id || null;      // banner buttons act on every ringing one
      const method = { cancel: 'timer_cancel', plus: 'timer_extend', ack: 'timer_ack', snooze: 'timer_snooze' }[tm.dataset.timer];
      return Bridge.call(method, id).catch(err => toast(err.message, 'err'));
    }
    const mo = e.target.closest('[data-month]');
    if (mo) { const n = Number(mo.dataset.month); Cal.offset = n === 0 ? 0 : Cal.offset + n; return Cal.render(); }
    const ringing = e.target.closest('.timer.done, .tile.timers.alarm');
    if (ringing) return Bridge.call('timer_ack', ringing.dataset.id || null);
    const link = e.target.closest('[data-link]');
    if (link && link.dataset.link) return Bridge.call('open_url', link.dataset.link);
    if (e.target.closest('.photos.max .photo-stage')) return restore();
  });
  $('#volume').addEventListener('input', e => Music.volume(Number(e.target.value)));
  $('#musicForm').addEventListener('submit', e => { e.preventDefault(); const q = $('#musicInput').value.trim(); if (q) Music.search(q); });
  $('#askForm').addEventListener('submit', e => {
    e.preventDefault();
    const q = $('#askInput').value.trim();
    if (!q) return;
    $('#askInput').value = '';
    Bridge.call('command', q).catch(err => toast(err.message, 'err'));
  });
  $('#micBtn').addEventListener('click', async () => {
    try {
      if (!window.__voice || window.__voice.state === 'off' || window.__voice.state === 'error') {
        setVoice(await Bridge.call('voice_toggle', true));
      } else await Bridge.call('voice_listen');
    } catch (err) { toast(err.message, 'err'); }
  });
  $('#settingsBtn').addEventListener('click', () => Settings.open());
  $('#studio').addEventListener('click', e => Studio.click(e));
  $('#studio').addEventListener('cancel', e => { e.preventDefault(); Studio.close(); });   // Esc
  $('#layoutBtn').innerHTML = icon('pencil');
  $('#layoutBtn').addEventListener('click', () => (Layout.editing ? Layout.done() : Layout.edit()));
  $('#editDone').addEventListener('click', () => Layout.done());
  $('#editCancel').addEventListener('click', () => Layout.cancel());
  $('#editReset').addEventListener('click', () => Layout.reset());
  $('#grid').addEventListener('pointerdown', e => Layout.pointerDown(e));
  $('#timerForm').addEventListener('submit', e => {
    e.preventDefault();
    let q = $('#timerInput').value.trim();
    if (!q) return;
    $('#timerInput').value = '';
    if (!/timer|remind/i.test(q)) q = /^\s*(at|in)\b/i.test(q) ? `remind me ${q}` : `set a timer for ${q}`;
    Bridge.call('command', q).catch(err => toast(err.message, 'err'));
  });
  $('#taskForm').addEventListener('submit', async e => {
    e.preventDefault();
    const q = $('#taskInput').value.trim();
    if (!q) return;
    $('#taskInput').value = '';
    try { toast(await Bridge.call('task_add', q)); } catch (err) { toast(err.message, 'err'); }
  });
  $('#taskList').addEventListener('click', async e => {
    const b = e.target.closest('[data-task]');
    if (!b) return;
    const id = b.closest('.task').dataset.id;
    const method = { done: 'task_complete', reopen: 'task_reopen', delete: 'task_delete' }[b.dataset.task];
    try { Tasks.set(await Bridge.call(method, id)); } catch (err) { toast(err.message, 'err'); }
  });
  $('#muteBtn').addEventListener('click', async () => {
    try { setMuted(await Bridge.call('replies_mute', !!S.settings.speak_replies)); }
    catch (err) { toast(err.message, 'err'); }
  });
  $('#wxBtn').addEventListener('click', () => {
    if (!S.settings?.weather_label) { Settings.tab = 'tiles'; return Settings.open(); }
    S.maximized === 'weather' ? restore() : maximize('weather');
  });
  $('#briefBtn').addEventListener('click', () => Bridge.call('command', 'brief me on the latest cyber attacks'));
  $('#waBtn').addEventListener('click', async () => {
    try {
      const r = await Bridge.call('whatsapp_open');
      if (r.url) window.open(r.url, '_blank');
    } catch (err) { toast(err.message, 'err'); }
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && Layout.editing) return Layout.cancel();
    if (e.key === 'Escape' && Timers.ringing().length) return Bridge.call('timer_ack', null);
    if (e.key === 'Escape' && S.maximized && !$('#settings').open) restore();
  });
  for (const ev of ['pointermove', 'keydown', 'pointerdown']) document.addEventListener(ev, () => { S.lastInput = Date.now(); }, { passive: true });
  window.addEventListener('resize', () => { if (S.maximized === 'stocks' && Stocks.chart) lineChart($('#chart'), Stocks.chart.points, Stocks.range); });
}

function idleCheck() {
  const mins = S.settings?.idle_minutes;
  if (mins && !S.maximized && Photos.count && Date.now() - S.lastInput > mins * 60000) maximize('photos');
}

async function start() {
  wire();
  tickClock();
  setInterval(tickClock, 10_000);
  $('#log').innerHTML = '<li class="empty">Try: "play Believer by Imagine Dragons", "how\'s the market", "brief me on cyber attacks", "show photos full screen", "open WhatsApp".</li>';
  if (SERVE) pollEvents();
  try {
    const init = await Bridge.call('init');
    S.settings = init.settings;
    setVoice(init.voice);
    window.__voice = init.voice;
  } catch (e) { toast(e.message, 'err'); return; }
  applySettings();
  Photos.info(await Bridge.call('photos_info'));
  Cyber.load();
  Bridge.call('whatsapp_chats').then(renderChats).catch(() => {});
  Bridge.call('timers_list').then(t => Timers.set(t)).catch(() => {});
  Bridge.call('tasks_list').then(t => Tasks.set(t)).catch(() => {});
  setInterval(() => Bridge.call('tasks_list').then(t => Tasks.set(t)).catch(() => {}), 60_000);   // ages tick forward
  setInterval(() => Weather.load(), 15 * 60_000);
  setInterval(() => Stocks.load(), 60_000);
  setInterval(() => Cyber.load(), 15 * 60_000);
  setInterval(() => GenNews.load(), 15 * 60_000);
  setInterval(() => Cal.load(), 15 * 60_000);
  setInterval(() => { Cal.render(); }, 60_000);       // move the "now" / "next" markers
  setInterval(() => PC.load(), 3_000);
  setInterval(() => Net.load(), 10_000);
  setInterval(() => Timers.tick(), 1_000);
  setInterval(idleCheck, 30_000);
}
start();
