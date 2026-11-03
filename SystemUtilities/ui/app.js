'use strict';

/* ================================================================ Utilities */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const reduceMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = n => Math.round(n).toLocaleString();
const basename = p => p.replace(/[\\/]+$/, '').split(/[\\/]/).pop() || p;
const dirname = p => { const s = p.replace(/[\\/]+$/, ''); const i = s.lastIndexOf('\\'); return i > 2 ? s.slice(0, i) : s.slice(0, 3); };
const TAU = Math.PI * 2;

function fmtSize(n) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return i ? `${n.toFixed(1)} ${units[i]}` : `${Math.round(n)} B`;
}

const ICONS = {
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  folderPlus: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M12 10v6M9 13h6"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  cloud: '<path d="M7 18a4 4 0 0 1-.6-7.95A6 6 0 0 1 18 9a4.5 4.5 0 0 1-.5 9z"/>',
  explorer: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v2"/><path d="M3 7v10a2 2 0 0 0 2 2h5"/><circle cx="16.5" cy="16.5" r="3"/><path d="m21 21-2.3-2.3"/>',
  sparkle: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  back: '<path d="M15 18l-6-6 6-6"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
  open: '<path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  broom: '<path d="M20 4l-8.5 8.5"/><path d="M8.5 11.5l4 4-1.5 5.5H5.5L4 16z"/><path d="M7 21l1-3"/>',
  grid: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.8"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.8"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.8"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.8"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="m9 12 2 2 4-4"/>',
  alert: '<path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  drive: '<rect x="3" y="13" width="18" height="7" rx="2"/><path d="M5 13l2.5-8h9L19 13"/><path d="M7 16.5h.01"/>',
  files: '<path d="M15 3H8a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7z"/><path d="M3 8v11a2 2 0 0 0 2 2h9"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  auto: '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  zap: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  home: '<path d="M3 11 12 4l9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
  memory: '<rect x="3" y="7" width="18" height="10" rx="1.5"/><path d="M7 7v10M11 7v10M15 7v10M5 17v3M9 17v3M13 17v3M17 17v3M19 17v3"/>',
  monitor: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  windows: '<path d="M3 5.5 10.5 4.5v7H3zM12 4.3 21 3v8.5h-9zM3 12.5h7.5v7L3 18.5zM12 12.5h9V21l-9-1.3z"/>',
  battery: '<rect x="2" y="7" width="18" height="10" rx="2"/><path d="M22 11v2"/><path d="M5 10v4"/>',
  plug: '<path d="M9 2v6M15 2v6M6 8h12v4a6 6 0 0 1-12 0zM12 18v4"/>',
  restart: '<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.9-3.5L4 9"/><path d="M4 4v5h5"/><path d="M4 13a8 8 0 0 0 14.9 3.5L20 15"/><path d="M20 20v-5h-5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  chip: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  bug: '<rect x="7" y="8" width="10" height="12" rx="5"/><path d="M9 8a3 3 0 0 1 6 0M3 13h4M17 13h4M4 7l3 2M20 7l-3 2M4 19l3-2M20 19l-3-2"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 19h16"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6"/><path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/><path d="M9 7V4h6v3"/>',
  checkmark: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  video: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/>',
  music: '<path d="M9 18V5l11-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  gauge: '<path d="M4.5 18a9 9 0 1 1 15 0"/><path d="m12 13 4-5"/><circle cx="12" cy="13" r="1.4"/>',
  power: '<path d="M12 3v8"/><path d="M6.3 7a8 8 0 1 0 11.4 0"/>',
  wand: '<path d="m4 20 11-11"/><path d="m13 7 2-2 4 4-2 2z"/><path d="M8 3v3M6.5 4.5h3M19 14v3M17.5 15.5h3"/>',
};

const ACTS = {
  clean: { icon: 'broom', label: 'Clean contents', verb: 'Clean',
    note: 'Deletes the files inside this folder (the folder itself stays). Files that are in use are skipped.' },
  recycle: { icon: 'trash', label: 'Move to Recycle Bin', verb: 'Move to Recycle Bin',
    note: 'You can restore it from the Recycle Bin if you change your mind.' },
  freeup: { icon: 'cloud', label: 'Free up space', verb: 'Free up space',
    note: 'Keeps it safely in the cloud and removes the copy on this PC. It downloads again when you open it.' },
  empty_bin: { icon: 'trash', label: 'Empty Recycle Bin', verb: 'Empty Recycle Bin', danger: true,
    note: 'Permanently deletes everything in the Recycle Bin. This cannot be undone.' },
};
const icon = (name, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24">${ICONS[name] || ''}</svg>`;

function countUp(el, to, fmt = num, dur = 800) {
  if (!el) return;
  const from = el._v ?? 0;
  el._v = to;
  cancelAnimationFrame(el._raf);
  if (reduceMotion() || from === to) { el.textContent = fmt(to); return; }
  const t0 = performance.now();
  const step = now => {
    const t = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - t, 3);
    el.textContent = fmt(from + (to - from) * e);
    if (t < 1) el._raf = requestAnimationFrame(step);
  };
  el._raf = requestAnimationFrame(step);
}

function typeText(el, text) {
  return new Promise(resolve => {
    if (reduceMotion()) { el.textContent = text; return resolve(); }
    el.classList.add('caret');
    const chunk = Math.max(1, Math.round(text.length / 140));
    let i = 0;
    const tick = () => {
      i = Math.min(text.length, i + chunk);
      el.textContent = text.slice(0, i);
      if (i < text.length) setTimeout(tick, 14);
      else { el.classList.remove('caret'); resolve(); }
    };
    tick();
  });
}

const nextFrame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));

// Scroll only the given container (scrollIntoView would also shift the fixed page layout).
function scrollWithin(container, el, block = 'start') {
  const c = container.getBoundingClientRect(), r = el.getBoundingClientRect();
  let top = container.scrollTop + r.top - c.top - 8;
  if (block === 'nearest') {
    if (r.top >= c.top && r.bottom <= c.bottom) return;
    if (r.bottom > c.bottom) top = container.scrollTop + r.bottom - c.bottom + 8;
  }
  container.scrollTo({ top, behavior: reduceMotion() ? 'auto' : 'smooth' });
}

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

/* ================================================================ State */
const S = {
  mode: 'cleanup', scanning: false, root: null, folder: null, largest: [], tab: 'browse',
  sort: { key: 'size', dir: -1 }, filter: '', rows: [], sel: -1, segs: [], colorByPath: new Map(), rowByPath: new Map(),
  cats: [], ai: null, profile: null, plan: null, cloudNote: '', model: null, aiBusy: 0, drives: [],
  aiOn: false, admin: false, picks: null, specs: null, live: null, cls: null, aiLocal: true, aiConfirm: true, aiLabel: '',
  drv: { list: null, updates: null, summary: null, checking: false, installing: false, step: '', result: null, err: null, sel: null },
  perf: { snap: null, loading: false, busy: false, sel: null, last: null, summary: null, err: null },
  agent: { state: null, pending: null, job: null },
  qc: { targets: [], sizes: {}, results: {}, sel: null, measuring: true, cleaning: false },
};
const sleep = ms => new Promise(r => setTimeout(r, ms));

const App = {
  on(event, data) {
    const handler = Events[event];
    if (handler) handler(data);
  },
};
window.App = App;

/* ================================================================ Toasts */
function toast(kind, text, ms = 3800, action = null) {
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.innerHTML = icon(kind === 'ok' ? 'check' : kind === 'err' ? 'alert' : 'info') + `<span>${esc(text)}</span>` +
    (action ? `<button class="toast-act">${esc(action.label)}</button>` : '');
  if (action) $('.toast-act', el).onclick = () => { el.remove(); action.fn(); };
  $('#toasts').appendChild(el);
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 320); }, ms);
}
const fail = e => toast('err', e.message || String(e), 6000);

/* ================================================================ Theme */
let themePref = 'auto';
try { themePref = localStorage.getItem('theme') || 'auto'; } catch (e) { /* storage unavailable */ }
const darkQuery = matchMedia('(prefers-color-scheme: dark)');

function applyTheme(animate) {
  const dark = themePref === 'dark' || (themePref === 'auto' && darkQuery.matches);
  const html = document.documentElement;
  if (animate && !reduceMotion()) {
    html.classList.add('theme-anim');
    setTimeout(() => html.classList.remove('theme-anim'), 500);
  }
  html.dataset.theme = dark ? 'dark' : 'light';
  $('.theme-ic').innerHTML = icon(themePref === 'auto' ? 'auto' : dark ? 'moon' : 'sun');
  $('#themeLabel').textContent = `Theme: ${themePref[0].toUpperCase()}${themePref.slice(1)}`;
  if (S.folder) drawSunburst('none');
}
darkQuery.addEventListener('change', () => applyTheme(true));
$('#themeBtn').addEventListener('click', () => {
  themePref = { auto: 'light', light: 'dark', dark: 'auto' }[themePref];
  try { localStorage.setItem('theme', themePref); } catch (e) { /* storage unavailable */ }
  applyTheme(true);
});

/* ================================================================ Context menu */
const ctx = $('#ctx');
function showCtx(x, y, entries) {
  entries = entries.filter(e => e === '-' || !e.ai || S.aiOn)
    .filter((e, i, arr) => e !== '-' || (i > 0 && arr[i - 1] !== '-' && i < arr.length - 1));
  ctx.innerHTML = entries.map((e, i) => e === '-' ? '<hr>' :
    `<button data-i="${i}" class="${e.cls || ''}">${icon(e.icon)}${esc(e.label)}</button>`).join('');
  ctx._entries = entries;
  ctx.classList.add('show');
  const r = ctx.getBoundingClientRect();
  ctx.style.left = Math.min(x, innerWidth - r.width - 8) + 'px';
  ctx.style.top = Math.min(y, innerHeight - r.height - 8) + 'px';
}
const hideCtx = () => ctx.classList.remove('show');
ctx.addEventListener('click', e => {
  const b = e.target.closest('button');
  if (!b) return;
  hideCtx();
  ctx._entries[+b.dataset.i].fn();
});
document.addEventListener('mousedown', e => { if (!ctx.contains(e.target)) hideCtx(); });
addEventListener('blur', hideCtx);

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); } catch (e) { await Bridge.call('copy_text', text); }
  toast('ok', 'Path copied');
}
const reveal = path => Bridge.call('reveal', path).catch(fail);
const openItem = path => Bridge.call('open_item', path).catch(fail);

/* ================================================================ Drives & models */
async function loadDrives() {
  try {
    S.drives = await Bridge.call('list_drives');
  } catch (e) { return fail(e); }
  $('#drives').innerHTML = S.drives.map((d, i) => {
    const pct = d.used / d.total * 100;
    return `<button class="drive" data-path="${esc(d.path)}" style="--i:${i}" title="Scan ${esc(d.letter)}">
      <svg class="ring" viewBox="0 0 44 44"><circle class="ring-bg" cx="22" cy="22" r="18"/>
        <circle class="ring-fg ${pct > 90 ? 'hot' : ''}" cx="22" cy="22" r="18" pathLength="100" data-p="${pct}"/></svg>
      <div class="drive-info"><b>${esc(d.letter)} <span>${esc(d.label)}</span></b>
        <small>${fmtSize(d.free)} free of ${fmtSize(d.total)}</small></div></button>`;
  }).join('');
  await nextFrame();
  $$('.ring-fg').forEach(c => { c.style.strokeDashoffset = 100 - c.dataset.p; });
  markActiveDrive();
  renderHome();
}
$('#drives').addEventListener('click', e => {
  const b = e.target.closest('.drive');
  if (b && b.dataset.path) startScan(b.dataset.path);
});
function markActiveDrive() {
  $$('.drive').forEach(d => d.classList.toggle('active', !!S.root && S.root.path === d.dataset.path));
}

async function loadModels() {
  const dot = $('#aiDot'), status = $('#aiStatus'), sel = $('#modelSelect');
  status.textContent = 'Connecting…';
  try {
    const r = await Bridge.call('list_models');
    S.model = r.current;
    S.aiLocal = r.local;
    S.aiConfirm = r.confirm;
    S.aiLabel = r.label;
    sel.innerHTML = r.models.map(m => `<option ${m === r.current ? 'selected' : ''}>${esc(m)}</option>`).join('');
    sel.disabled = false;
    dot.className = 'dot on';
    status.textContent = r.local ? `${r.label} · ${r.models.length} model${r.models.length === 1 ? '' : 's'}` : `${r.label} · cloud API`;
    $('#aiProvider').textContent = `AI settings · ${r.local ? 'local' : 'API'}`;
    S.aiOn = true;
  } catch (e) {
    dot.className = 'dot off';
    status.textContent = /ollama/i.test(e.message) ? 'Ollama not running — using rules only' : 'AI not set up — open AI settings';
    status.title = e.message;
    S.aiOn = false;
  }
  applyAi();
}

/* ---------- AI provider settings ---------- */
const PROVIDERS = [
  ['ollama', 'Local (Ollama)', 'Free and private — runs on this PC. Any model you install.', 'home'],
  ['openai', 'OpenAI-compatible API', 'OpenAI, OpenRouter, Groq, Mistral, DeepSeek, LM Studio…', 'globe'],
  ['anthropic', 'Anthropic Claude', 'Claude models through the official Anthropic API.', 'sparkle'],
];

async function openAiSettings() {
  if ($('#modal').classList.contains('open')) return;     // already showing a dialog
  let s;
  try { s = await Bridge.call('ai_settings_get'); } catch (e) { return fail(e); }
  const known = s.presets.some(p => p.base === s.openai_base);
  const body = `<div class="ais">
    <div class="ais-providers">${PROVIDERS.map(([v, t, d, ic]) => `<label class="ais-prov"><input type="radio" name="aisProv" value="${v}" ${s.provider === v ? 'checked' : ''}>
      <span class="ais-ic">${icon(ic)}</span><span><b>${t}</b><small>${d}</small></span></label>`).join('')}</div>
    <div class="ais-sec" data-for="ollama">
      <label>Ollama address<input id="aisHost" value="${esc(s.ollama_host || '')}"></label>
      <p class="ais-note">Pick the model from the sidebar list. Install more with <code>ollama pull &lt;model&gt;</code> — Llama, Qwen, Mistral, Gemma, DeepSeek… all work.</p>
    </div>
    <div class="ais-sec" data-for="openai">
      <label>Service<select id="aisPreset">${s.presets.map(p => `<option value="${esc(p.base)}" ${p.base === s.openai_base ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}
        <option value="" ${known ? '' : 'selected'}>Custom…</option></select></label>
      <label>Base URL<input id="aisBase" value="${esc(s.openai_base || '')}" placeholder="https://…/v1"></label>
      <label>API key<input id="aisOKey" type="password" autocomplete="off" placeholder="${s.openai_key ? `Saved (${esc(s.openai_key)}) — leave blank to keep` : 'Paste your API key'}"></label>
      <label>Model <span class="ais-note" id="aisOCount" style="font-weight:500">${s.openai_model ? '— showing your saved model only. Click Test connection to see all models.' : '— click Test connection to see all models your key can use.'}</span>
        <select id="aisOModelSel">${s.openai_model ? `<option selected>${esc(s.openai_model.replace(/^models\//, ''))}</option>` : ''}
          <option value="__other">Other — type a model name…</option></select></label>
      <label id="aisOModelOther" hidden>Model name<input id="aisOModel" value="${esc((s.openai_model || '').replace(/^models\//, ''))}" placeholder="e.g. gemini-2.5-flash"></label>
      <div class="ais-row"><label>Input price, $ per 1M tokens<input id="aisPin" type="number" min="0" step="0.01" value="${s.price_in ?? ''}" placeholder="optional"></label>
        <label>Output price, $ per 1M tokens<input id="aisPout" type="number" min="0" step="0.01" value="${s.price_out ?? ''}" placeholder="optional"></label></div>
      <p class="ais-note">Prices are only used for the cost estimate shown before each request.</p>
    </div>
    <div class="ais-sec" data-for="anthropic">
      <label>API key<input id="aisAKey" type="password" autocomplete="off" placeholder="${s.anthropic_key ? `Saved (${esc(s.anthropic_key)}) — leave blank to keep` : 'Paste your key from console.anthropic.com'}"></label>
      <label>Model<select id="aisAModel">${[...new Set([s.anthropic_model, ...s.anthropic_models])].map(m => `<option ${m === s.anthropic_model ? 'selected' : ''}>${esc(m)}</option>`).join('')}</select></label>
      <p class="ais-note">To see all models your key can use, click Test connection. Token counts for Claude are exact (Anthropic's counting endpoint); cost uses list prices.</p>
    </div>
    <label class="ais-check"><input type="checkbox" id="aisConfirm" ${s.confirm ? 'checked' : ''}>Show tokens and estimated cost before every cloud AI request</label>
    <div class="ais-test"><button type="button" class="btn sm" id="aisTest">${icon('refresh')}Test connection</button><span id="aisTestOut"></span></div>
    <p class="ais-note warn-note">With a cloud API, folder and file names and paths from this PC are sent to that provider. API keys are stored in Windows Credential Manager, never in a file.</p>
  </div>`;

  const form = () => {
    const preset = $('#aisPreset');
    return {
      provider: $('input[name=aisProv]:checked').value,
      ollama_host: $('#aisHost').value.trim(),
      openai_base: $('#aisBase').value.trim(),
      openai_name: preset.value ? preset.selectedOptions[0].textContent : 'Custom API',
      openai_model: $('#aisOModelSel').value === '__other' ? $('#aisOModel').value.trim() : $('#aisOModelSel').value,
      price_in: $('#aisPin').value, price_out: $('#aisPout').value,
      anthropic_model: $('#aisAModel').value,
      confirm: $('#aisConfirm').checked,
      openai_key_new: $('#aisOKey').value.trim(), anthropic_key_new: $('#aisAKey').value.trim(),
    };
  };
  const pending = confirmDialog({ title: 'AI settings', icon: 'gear', okLabel: 'Save', body });
  $('.modal-card').classList.add('wide');
  const syncProv = () => {
    const p = $('input[name=aisProv]:checked').value;
    $$('.ais-sec').forEach(sec => { sec.hidden = sec.dataset.for !== p; });
    $('#aisTestOut').textContent = '';
  };
  $$('input[name=aisProv]').forEach(r => r.addEventListener('change', syncProv));
  syncProv();
  $('#aisPreset').addEventListener('change', e => {
    if (e.target.value) $('#aisBase').value = e.target.value;
    $('#aisOModelSel').innerHTML = '<option value="__other">Other — type a model name…</option>';   // models differ per service
    $('#aisOModel').value = '';
    $('#aisOModelOther').hidden = false;
    $('#aisOCount').textContent = '— click Test connection to see all models for this service.';
  });
  const syncOther = () => { $('#aisOModelOther').hidden = $('#aisOModelSel').value !== '__other'; };
  $('#aisOModelSel').addEventListener('change', syncOther);
  syncOther();
  $('#aisTest').addEventListener('click', async () => {
    const out = $('#aisTestOut'), btn = $('#aisTest');
    out.className = ''; out.textContent = 'Connecting…';
    busy(btn, true);
    try {
      const r = await Bridge.call('ai_test', form());
      out.className = 'ok';
      out.textContent = `✓ Connected to ${r.label} · ${r.models.length} model${r.models.length === 1 ? '' : 's'} available`;
      if (form().provider === 'openai') {
        const sel = $('#aisOModelSel'), cur = form().openai_model;
        const pick = r.models.includes(cur) ? cur : r.model;
        sel.innerHTML = r.models.map(m => `<option ${m === pick ? 'selected' : ''}>${esc(m)}</option>`).join('') +
          '<option value="__other">Other — type a model name…</option>';
        $('#aisOCount').textContent = `— ${r.models.length} chat models available. To refresh the list, click Test connection again.`;
        syncOther();
      } else if (form().provider === 'anthropic') {
        const sel = $('#aisAModel'), cur = sel.value;
        sel.innerHTML = [...new Set([cur, ...r.models])].map(m => `<option ${m === cur ? 'selected' : ''}>${esc(m)}</option>`).join('');
      }
    } catch (e) { out.className = 'bad'; out.textContent = e.message; }
    busy(btn, false);
  });
  const ok = await pending;
  const values = form();
  setTimeout(() => $('.modal-card').classList.remove('wide'), 300);
  if (!ok) return;
  try {
    const saved = await Bridge.call('ai_settings_save', values);
    toast(saved.error ? 'err' : 'ok', saved.error ? `Saved, but: ${saved.error}` : `AI settings saved · ${saved.label}`, 5000);
    if (!aiPref) await setAi(true, true); else await loadModels();
    renderHome();
  } catch (e) { fail(e); }
}
$('#aiSettingsBtn').addEventListener('click', openAiSettings);

/* ---------- token estimate before cloud requests ---------- */
async function confirmAiCost(op, path) {
  if (S.aiLocal || !S.aiConfirm) return true;
  let e;
  try { e = await Bridge.call('ai_estimate', op, path); } catch (err) { fail(err); return false; }
  if (e.local) return true;
  const what = { review: 'review the large folders', explain: 'explain this item', plan: 'suggest an organisation plan' }[op];
  const cost = e.cost != null ? `≈ $${e.cost < 0.01 ? e.cost.toFixed(4) : e.cost.toFixed(2)}` : 'add prices in AI settings';
  const ok = await confirmDialog({
    title: `Use ${e.label} to ${what}?`, icon: 'sparkle', okLabel: 'Continue',
    body: `<div class="est-total"><b>≈ ${num(e.input + e.output)}</b><span>tokens in total</span></div>
      <ul>
        <li><span>Model</span><span>${esc(e.model)}</span></li>
        <li><span>Requests</span><span>${e.requests}</span></li>
        <li><span>Input tokens ${e.exact ? '(exact count)' : '(estimate)'}</span><span>${e.exact ? '' : '≈ '}${num(e.input)}</span></li>
        <li><span>Output tokens (estimate)</span><span>≈ ${num(e.output)}</span></li>
        <li><span>Estimated cost</span><span>${cost}</span></li>
      </ul>
      ${e.thinking ? '<p>Claude may also spend some thinking tokens, billed as output.</p>' : ''}
      <p>Folder and file names and paths from this PC are sent to ${esc(e.label)}. Nothing is sent until you continue.</p>
      <label class="est-dont"><input type="checkbox" id="estDontAsk">Don't ask again (turn it back on in AI settings)</label>`,
  });
  if (ok && $('#estDontAsk') && $('#estDontAsk').checked) {
    S.aiConfirm = false;
    Bridge.call('ai_settings_save', { confirm: false }).catch(fail);
  }
  return ok;
}

function usageText(u) {
  if (!u || u.local || !(u.input + u.output)) return '';
  return ` · ${num(u.input + u.output)} tokens${u.cost != null ? ` (≈ $${u.cost < 0.01 ? u.cost.toFixed(4) : u.cost.toFixed(2)})` : ''}`;
}

/* ---------- AI on / off ---------- */
let aiPref = true;
try { aiPref = localStorage.getItem('ai') !== 'off'; } catch (e) { /* storage unavailable */ }

function applyAi() {
  document.body.classList.toggle('no-ai', !S.aiOn);
  $('#planLabel').textContent = S.aiOn ? 'AI plan' : 'Suggest plan';
  $('#planBtn').classList.toggle('ai', S.aiOn);
  $('#planBtn svg').innerHTML = ICONS[S.aiOn ? 'sparkle' : 'grid'];
}

async function setAi(on, save) {
  aiPref = on;
  $('#aiToggle').checked = on;
  if (save) { try { localStorage.setItem('ai', on ? 'on' : 'off'); } catch (e) { /* storage unavailable */ } }
  await Bridge.call('set_ai_enabled', on).catch(fail);
  if (on) return loadModels();
  S.aiOn = false;
  $('#aiDot').className = 'dot';
  $('#aiStatus').textContent = 'AI off — everything else works without it';
  $('#modelSelect').disabled = true;
  applyAi();
}
$('#aiToggle').addEventListener('change', e => {
  setAi(e.target.checked, true).then(() => toast('info', e.target.checked ? 'AI assistant on' : 'AI assistant off — using rules only'));
});
$('#modelSelect').addEventListener('change', e => {
  S.model = e.target.value;
  Bridge.call('set_model', S.model).then(() => toast('info', `AI model: ${S.model}`)).catch(fail);
});

function aiBusy(delta) {
  S.aiBusy = Math.max(0, S.aiBusy + delta);
  if ($('#aiDot').classList.contains('off')) return;
  $('#aiDot').className = 'dot ' + (S.aiBusy ? 'busy' : 'on');
}

/* ================================================================ Views */
const VIEW_TITLES = { home: 'Home', drivers: 'Drivers', perf: 'Performance', quick: 'Quick clean', welcome: 'Organise a folder', scanning: 'Scanning…' };
// Each section's own start screen; Clean-up and Organiser show the scan results instead when a scan is open.
const START_VIEW = { home: 'home', drivers: 'drivers', perf: 'perf', cleanup: 'quick', organise: 'welcome' };
const PANEL_MODES = ['cleanup', 'organise'];

function showView(name) {
  $$('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + name));
  $('.topbar').classList.toggle('no-tools', name !== 'explorer');
  if (name === 'explorer' && S.folder) renderCrumbs();
  else if (VIEW_TITLES[name]) $('#crumbs').innerHTML = `<span class="crumb last">${VIEW_TITLES[name]}</span>`;
  if (name === 'welcome') fetchPicks(true);
  if (name === 'home') renderHome();
  if (name === 'drivers') openDrivers();
  if (name === 'perf') openPerf();
  updateBack();
}

// The back arrow goes up a folder in the explorer, or from a section's start screen back to the scan results.
// It is hidden whenever there is nowhere to go.
function updateBack() {
  const b = $('#upBtn'), active = v => $('#view-' + v).classList.contains('active');
  const inExplorer = active('explorer');
  const can = inExplorer ? !!(S.folder && S.folder.parent) : (active('quick') || active('welcome')) && !!S.folder && !S.scanning;
  b.classList.toggle('gone', !can);
  b.disabled = !can;
  b.title = inExplorer ? 'Up one folder (Backspace)' : `Back to ${S.folder ? S.folder.name : 'scan results'}`;
}
const homeView = () => START_VIEW[S.mode];

/* ================================================================ Confirmation dialog */
// extra: [{label, icon, value}] closes and resolves with value; [{label, icon, fn}] runs fn and stays open.
// cancelLabel: null hides Cancel (Escape / clicking outside then resolve false, which callers treat as "close").
function confirmDialog({ title, body, okLabel = 'OK', icon: ic = 'broom', danger = false, cancelLabel = 'Cancel', extra = [] }) {
  return new Promise(resolve => {
    const m = $('#modal'), ok = $('#modalOk'), cancel = $('#modalCancel');
    $('#modalTitle').textContent = title;
    $('#modalBody').innerHTML = body;
    $('#modalIc').innerHTML = icon(ic);
    $('#modalIc').className = 'modal-ic' + (danger ? ' danger' : '');
    ok.textContent = okLabel;
    ok.className = 'btn ' + (danger ? 'danger' : 'clean');
    cancel.textContent = cancelLabel || 'Cancel';
    cancel.hidden = cancelLabel === null;
    const extras = extra.map(x => {
      const b = document.createElement('button');
      b.className = 'btn';
      b.innerHTML = (x.icon ? icon(x.icon) : '') + esc(x.label);
      b.onclick = () => (x.fn ? x.fn() : done(x.value));
      cancel.parentElement.insertBefore(b, cancel);
      return b;
    });
    m.classList.add('open');
    setTimeout(() => ok.focus(), 50);
    const key = e => {
      if (e.key === 'Escape') { e.stopPropagation(); done(false); }
      else if (e.key === 'Enter' && !ok.disabled) { e.preventDefault(); e.stopPropagation(); done(true); }
    };
    const done = v => {
      m.classList.remove('open');
      ok.onclick = cancel.onclick = m.onclick = null;
      extras.forEach(b => b.remove());
      cancel.hidden = false;
      document.removeEventListener('keydown', key, true);
      resolve(v);
    };
    ok.onclick = () => done(true);
    cancel.onclick = () => done(false);
    m.onclick = e => { if (e.target === m) done(false); };
    document.addEventListener('keydown', key, true);
  });
}

/* ================================================================ Quick clean */
async function loadQuick() {
  S.qc.sizes = {};
  S.qc.measuring = true;
  renderQuick();
  try {
    const r = await Bridge.call('quick_targets');
    S.qc.targets = r.targets;
    S.admin = r.admin;
    if (!S.qc.sel) S.qc.sel = new Set(r.targets.filter(t => t.default).map(t => t.id));
    renderQuick();
  } catch (e) { fail(e); }
}

function qcTags(t, m) {
  const tags = [];
  const res = S.qc.results[t.id];
  if (res) {
    tags.push(`<span class="tag ok">${icon('checkmark')}Freed ${fmtSize(res.freed)}</span>`);
    if (res.skipped) tags.push(`<span class="tag">${num(res.skipped)} in use, skipped</span>`);
    if (res.error) tags.push(`<span class="tag warn">${esc(res.error)}</span>`);
  }
  if (t.admin && !S.admin && m && m.denied) tags.push('<span class="tag warn">Needs administrator</span>');
  if (m && m.running && m.running.length) {
    tags.push(`<span class="tag warn">Close ${m.running.map(a => a.replace('.exe', '')).join(', ')} to clean fully</span>`);
  }
  return tags.join('');
}

function qcCard(t, i, shown) {
  const m = S.qc.sizes[t.id];
  const checked = S.qc.sel && S.qc.sel.has(t.id);
  const cls = ['qc-item', checked && 'checked', t.kind === 'recycle' && 'recycle', m && !m.size && 'empty', shown && 'shown']
    .filter(Boolean).join(' ');
  return `<label class="${cls}" data-id="${t.id}" style="--i:${i}${shown ? ';animation:none' : ''}">
    <input type="checkbox" ${checked ? 'checked' : ''}><span class="check">${icon('checkmark')}</span>
    <span class="qc-ic">${icon(t.icon)}</span>
    <div class="qc-text"><b>${esc(t.name)}</b><small>${esc(t.desc)}</small><div class="qc-tags">${qcTags(t, m)}</div>
      ${m && m.files && t.kind !== 'recycle' ? `<button type="button" class="qc-see" data-see="${t.id}">${icon('eye')}See data</button>` : ''}</div>
    <div class="qc-size">${!m ? '<i class="shimmer"></i>'
      : t.kind === 'shortcuts' ? `<b>${num(m.files)}</b><small>shortcut${m.files === 1 ? '' : 's'}</small>`
      : `<b>${fmtSize(m.size)}</b><small>${m.files || t.kind !== 'cleanmgr' ? `${num(m.files)} ${t.kind === 'recycle' ? 'items' : 'files'}` : 'nothing found'}</small>`}</div>
    <span class="qc-bar"></span></label>`;
}

function renderQuick() {
  const list = $('#qcList');
  if (!S.qc.targets.length) {
    list.innerHTML = Array.from({ length: 6 }, (_, i) => `<div class="qc-item" style="--i:${i}"><span></span><span class="qc-ic"></span>
      <div class="qc-text"><i class="shimmer" style="height:14px;width:60%"></i><i class="shimmer" style="height:10px;width:90%;margin-top:8px"></i></div>
      <div class="qc-size"><i class="shimmer"></i></div></div>`).join('');
  } else {
    const shown = list.dataset.shown === '1';
    list.innerHTML = S.qc.targets.map((t, i) => qcCard(t, i, shown)).join('');
    list.dataset.shown = '1';
  }
  updateQuickTotals();
}

function updateQuickCard(id) {
  const t = S.qc.targets.find(x => x.id === id), el = $(`.qc-item[data-id="${id}"]`);
  if (!t || !el) return;
  const wasCleaning = el.classList.contains('cleaning');
  el.outerHTML = qcCard(t, 0, true);
  const fresh = $(`.qc-item[data-id="${id}"]`);
  if (wasCleaning) fresh.classList.add('cleaning');
  if (S.qc.results[id] && S.qc.results[id]._flash) { fresh.classList.add('cleaned'); S.qc.results[id]._flash = false; }
}

function updateQuickTotals() {
  const sizes = S.qc.sizes;
  const all = Object.values(sizes).reduce((n, m) => n + m.size, 0);
  const sel = S.qc.sel ? [...S.qc.sel].reduce((n, id) => n + (sizes[id] ? sizes[id].size : 0), 0) : 0;
  countUp($('#qcTotal'), sel, fmtSize, 700);
  countUp($('#qcSel'), sel, fmtSize, 700);
  $('#quickNavSize').textContent = all ? fmtSize(all) : '';
  renderHome();
  $('.qc-ring').classList.toggle('measuring', S.qc.measuring);
  $('.qc-ring-fg').style.strokeDashoffset = S.qc.measuring ? '' : 100 - (all ? Math.max(3, sel / all * 100) : 0);
  $('#qcCleanBtn').disabled = S.qc.cleaning || !sel;
  const needAdmin = S.qc.targets.some(t => t.admin && sizes[t.id] && sizes[t.id].denied) && !S.admin;
  $('#qcAdmin').classList.toggle('hidden', !needAdmin);
}

$('#qcList').addEventListener('click', e => {
  const b = e.target.closest('[data-see]');
  if (!b) return;
  e.preventDefault();          // the card is a <label>: don't toggle its checkbox
  e.stopPropagation();
  seeQuickData(b.dataset.see);
});

// "See data": which folders and files a quick-clean location holds.
async function seeQuickData(id) {
  const t = S.qc.targets.find(x => x.id === id), m = S.qc.sizes[id];
  let d;
  try { d = await Bridge.call('quick_details', id); } catch (e) { return fail(e); }
  const short = p => p.replace(/^C:\\Users\\[^\\]+/i, '~');
  const row = (name, where, size, path) => `<div class="see-row" data-path="${esc(path)}" title="Show in Explorer">
    <span><b>${esc(name)}</b><small>${esc(short(where))}</small></span><em>${size}</em>${icon('explorer')}</div>`;
  let body;
  if (d.shortcuts.length) {
    body = `<p>These shortcuts point to something that no longer exists. They go to the Recycle Bin, so you can restore them.</p>
      <div class="see-list">${d.shortcuts.map(s => row(s.name, `→ ${s.target} (missing)`, '', s.path)).join('')}</div>`;
  } else {
    body = `<p>${esc(t.desc)}</p>
      ${d.locations.length ? `<h4 class="see-h">${d.locations.length} location${d.locations.length === 1 ? '' : 's'}</h4>
        <div class="see-list">${d.locations.slice(0, 30).map(l => row(basename(l.path), l.path, `${fmtSize(l.size)} · ${num(l.files)}`, l.path)).join('')}</div>` : ''}
      ${d.files.length ? `<h4 class="see-h">Largest files${d.total_files > d.files.length ? ` (${d.files.length} of ${num(d.total_files)})` : ''}</h4>
        <div class="see-list">${d.files.map(f => row(f.name, f.folder, fmtSize(f.size), `${f.folder}\\${f.name}`)).join('')}</div>` : ''}`;
  }
  await confirmDialog({ title: `${t.name}${m ? ` · ${t.kind === 'shortcuts' ? `${num(m.files)} shortcuts` : fmtSize(m.size)}` : ''}`,
    icon: t.icon, body: `<div class="see">${body}</div>`, okLabel: 'Got it', cancelLabel: null });
}
$('#modalBody').addEventListener('click', e => {
  const r = e.target.closest('.see-row');
  if (r) Bridge.call('reveal', r.dataset.path).catch(fail);
});

$('#qcList').addEventListener('change', e => {
  const card = e.target.closest('.qc-item');
  if (!card || !S.qc.sel) return;
  const id = card.dataset.id;
  if (e.target.checked) S.qc.sel.add(id); else S.qc.sel.delete(id);
  card.classList.toggle('checked', e.target.checked);
  updateQuickTotals();
});
$('#qcRecheck').addEventListener('click', () => { S.qc.results = {}; loadQuick(); });
// Buttons that jump to a section's start screen (Home cards, panel chips).
document.addEventListener('click', e => {
  const b = e.target.closest('[data-go]');
  if (!b) return;
  if (b.dataset.path) { setMode('organise', 'welcome'); return startScan(b.dataset.path); }
  if (S.scanning && !['drivers', 'perf'].includes(b.dataset.go)) return toast('info', 'A scan is running — wait for it or cancel it first');
  const mode = { quick: 'cleanup', welcome: 'organise', drivers: 'drivers', perf: 'perf' }[b.dataset.go];
  setMode(mode, START_VIEW[mode]);
  if (b.dataset.go === 'quick') loadQuick();
});
$('#adminBtn').addEventListener('click', async () => {
  const ok = await confirmDialog({ title: 'Restart as administrator?', icon: 'lock', okLabel: 'Restart',
    body: '<p>Windows will ask for permission, then the app reopens with access to system locations such as ' +
      'Windows temporary files and Windows Update leftovers. Your current scan will be closed.</p>' });
  if (ok) Bridge.call('restart_as_admin').catch(fail);
});

$('#qcCleanBtn').addEventListener('click', async () => {
  const ids = [...S.qc.sel].filter(id => S.qc.sizes[id] && S.qc.sizes[id].size > 0);
  if (!ids.length) return;
  const total = ids.reduce((n, id) => n + S.qc.sizes[id].size, 0);
  const name = id => S.qc.targets.find(t => t.id === id).name;
  const bin = ids.includes('recycle'), setup = ids.includes('win_setup');
  const ok = await confirmDialog({
    title: 'Clean these locations?', icon: 'broom', danger: bin || setup, okLabel: `Clean ${fmtSize(total)}`,
    body: `<ul>${ids.map(id => `<li><span>${esc(name(id))}</span><span>${fmtSize(S.qc.sizes[id].size)}</span></li>`).join('')}</ul>
      <p>Only throwaway files are removed. Anything in use is skipped automatically.</p>
      ${ids.includes('broken_shortcuts') ? '<p>Broken shortcuts go to the Recycle Bin, so they can be restored.</p>' : ''}
      ${setup ? "<p class=\"warn\">Windows setup files: after this you can't go back to your previous Windows version. Windows' Disk Cleanup does the removal and asks for administrator permission.</p>" : ''}
      ${bin ? '<p class="warn">Emptying the Recycle Bin is permanent.</p>' : ''}`,
  });
  if (!ok) return;
  const btn = $('#qcCleanBtn');
  S.qc.cleaning = true;
  busy(btn, true);
  try {
    const r = await Bridge.call('quick_clean', ids);
    toast('ok', `Freed ${fmtSize(r.freed)}` + (r.skipped ? ` · ${num(r.skipped)} files in use were skipped` : ''), 5000);
    if (S.folder) refreshFolder();
  } catch (e) { fail(e); }
  S.qc.cleaning = false;
  busy(btn, false);
  updateQuickTotals();
});

async function refreshFolder() {
  if (!S.folder) return;
  try {
    const f = await Bridge.call('get_folder', S.folder.path);
    S.folder = f;
    renderStats();
    drawSunburst('none');
    renderList(false);
    S.largest = await Bridge.call('get_largest');
  } catch (e) {
    if (S.folder.parent) go(S.folder.parent, 'out');   // the open folder itself was removed
  }
}

/* ================================================================ Scanning */
async function startScan(path) {
  if (S.scanning) return toast('info', 'A scan is already running');
  try {
    await Bridge.call('start_scan', path);
  } catch (e) { return fail(e); }
  S.scanning = true;
  $('#scanTitle').textContent = `Scanning ${path}`;
  ['#scanFiles', '#scanDirs'].forEach(s => { $(s)._v = 0; $(s).textContent = '0'; });
  $('#scanTime').textContent = '0s';
  $('#scanPath').textContent = path;
  if (!PANEL_MODES.includes(S.mode)) setMode('cleanup');   // shows the scanning view
  else showView('scanning');
}
$('#cancelBtn').addEventListener('click', () => Bridge.call('cancel_scan').catch(fail));
async function pickAndScan() {
  let path = await Bridge.call('pick_folder').catch(fail);
  if (!path && SERVE) path = prompt('Folder to scan');
  if (path) startScan(path);
}
$('#scanFolderBtn').addEventListener('click', pickAndScan);
$('#changeFolderBtn').addEventListener('click', pickAndScan);
$('#orgPickBtn').addEventListener('click', pickAndScan);

/* ---------- organiser start screen ---------- */
async function fetchPicks(force) {
  if (S.picks && !force) return S.picks;
  try { S.picks = await Bridge.call('known_folders'); } catch (e) { S.picks = S.picks || []; }
  renderPicks();
  renderHome();
  return S.picks;
}
function renderPicks() {
  const folders = S.picks || [];
  $('#orgPicks').innerHTML = folders.map((f, i) => `<button class="org-pick" data-path="${esc(f.path)}" style="--i:${i}" title="${esc(f.path)}">
    <span class="org-pick-ic">${icon(f.icon)}</span>
    <span><b>${esc(f.name)}</b><small>${esc(f.path)}</small>
      <em class="${f.loose >= 10 ? '' : 'ok'}">${f.loose >= 10 ? `${num(f.loose)} loose files to sort` : `${num(f.items)} items · looks tidy`}</em></span>
    ${icon('chevron', 'chev')}</button>`).join('');
}
$('#orgPicks').addEventListener('click', e => {
  const b = e.target.closest('.org-pick');
  if (b) startScan(b.dataset.path);
});

const Events = {
  scan_progress(d) {
    countUp($('#scanFiles'), d.files, num, 250);
    countUp($('#scanDirs'), d.dirs, num, 250);
    $('#scanTime').textContent = `${d.elapsed.toFixed(0)}s`;
    $('#scanPath').textContent = d.path;
  },
  async scan_done(d) {
    S.scanning = false;
    S.root = d;
    S.cats = []; S.ai = null; S.profile = null; S.plan = null; S.vd = null; S.cls = null; S.tab = 'browse';
    markActiveDrive();
    renderCats();
    resetOrganiser();
    try {
      await openFolder(d.path, 'in');
      S.largest = await Bridge.call('get_largest');
    } catch (e) { fail(e); }
    const msg = `Scanned ${num(d.files)} files in ${d.elapsed.toFixed(1)}s — ${fmtSize(d.size)} on disk`;
    if (PANEL_MODES.includes(S.mode)) {
      showView('explorer');
      toast('ok', msg);
    } else {   // the user moved to Home/Drivers while it scanned: don't pull them away
      toast('ok', msg, 8000, { label: 'View', fn: () => setMode('cleanup') });
    }
    setTab('browse', false);
    renderHome();
    if (S.mode === 'organise' && d.path.length > 3) analyse();   // a folder picked to organise: health check straight away
  },
  scan_cancelled() {
    S.scanning = false;
    showView(PANEL_MODES.includes(S.mode) && S.folder ? 'explorer' : homeView());
    toast('info', 'Scan cancelled');
  },
  agent_line(d) { agentLine(d); S.agent.pending = d.pending; S.agent.job = d.job; renderAgentStatus(); },
  agent_pending(d) { S.agent.pending = d; renderAgentStatus(); },
  agent_job(d) { S.agent.job = d.job; renderAgentStatus(); },
  agent_show(d) { agentShow(d); },
  agent_voice(v) { renderAgentVoice(v); },
  driver_progress(d) {
    S.drv.step = d.step;
    const el = $('#drvStep');
    if (el) el.textContent = d.step + '…';
  },
  quick_size(d) {
    S.qc.sizes[d.id] = d;
    updateQuickCard(d.id);
    updateQuickTotals();
  },
  quick_measured() {
    S.qc.measuring = false;
    updateQuickTotals();
  },
  quick_cleaning(d) {
    const el = $(`.qc-item[data-id="${d.id}"]`);
    if (el) el.classList.add('cleaning');
  },
  quick_cleaned(d) {
    S.qc.results[d.id] = { ...d, _flash: true };
    const el = $(`.qc-item[data-id="${d.id}"]`);
    if (el) el.classList.remove('cleaning');
  },
  organise_progress(d) {
    const label = $('#previewOrgBtn span');
    if (label) label.textContent = `Moving ${d.done + 1} of ${d.total}…`;
  },
  classify_progress(d) {
    if (!S.cls || !S.cls.running) return;
    Object.assign(S.cls, d);
    renderCls();
  },
  vdupe_progress(d) {
    if (!S.vd || !S.vd.running) return;
    Object.assign(S.vd, { done: d.done, total: d.total, name: d.name });
    renderVd();
  },
  clean_progress(d) {
    const card = $$('#cats .cat').find(c => c.dataset.name === d.name);
    const sub = card && $('.cat-title small', card);
    if (sub) sub.textContent = `Cleaning ${d.done + 1} of ${d.total}…`;
  },
  ai_review_start(d) {
    S.ai = { running: true, done: 0, total: d.total, model: d.model, items: [], shown: 0 };
    renderAiCard();
  },
  ai_review_progress(d) {
    if (!S.ai) return;
    S.ai.done = d.done;
    renderAiCard();
  },
  ai_review_batch(d) {
    if (!S.ai) return;
    S.ai.items.push(...d.items);
    S.ai.done = d.done;
    renderAiCard();
    updateTiles();
  },
};

/* ================================================================ Explorer */
async function openFolder(path, dir = 'in') {
  const f = await Bridge.call('get_folder', path);
  S.folder = f;
  S.sel = -1;
  S.filter = '';
  $('#filter').value = '';
  renderCrumbs();
  renderStats();
  drawSunburst(dir);
  if (S.tab !== 'browse') setTab('browse', false);
  else renderList();
  updateBack();
  $('#revealBtn').disabled = false;
  updateOrgFolder();
}
const go = (path, dir) => openFolder(path, dir).catch(fail);
const goUp = () => {
  if (!$('#view-explorer').classList.contains('active')) { if (S.folder && !S.scanning) showView('explorer'); }
  else if (S.folder && S.folder.parent) go(S.folder.parent, 'out');
};
$('#upBtn').addEventListener('click', goUp);
$('#revealBtn').addEventListener('click', () => {
  const item = S.rows[S.sel];
  if (item) reveal(item.path); else if (S.folder) openItem(S.folder.path);
});

function renderCrumbs() {
  const crumbs = S.folder.crumbs;
  $('#crumbs').innerHTML = crumbs.map((c, i) => {
    const last = i === crumbs.length - 1;
    const sep = i ? `<span class="crumb-sep" style="--i:${i}">${icon('chevron')}</span>` : '';
    return sep + (last ? `<span class="crumb last" style="--i:${i}">${esc(c.name)}</span>`
      : `<button class="crumb" data-path="${esc(c.path)}" style="--i:${i}">${esc(c.name)}</button>`);
  }).join('');
  // Keep the current folder visible when the path is too long; fade the hidden start.
  const el = $('#crumbs');
  el.scrollLeft = el.scrollWidth;
  el.classList.toggle('overflow', el.scrollWidth > el.clientWidth);
}
$('#crumbs').addEventListener('click', e => {
  const b = e.target.closest('button.crumb');
  if (b) go(b.dataset.path, 'out');
});

function renderStats() {
  const f = S.folder;
  const stats = [
    ['drive', 'On this PC', f.size, fmtSize],
    ['cloud', 'Online-only', f.cloud, fmtSize],
    ['files', 'Files', f.files, num],
    ['folder', 'Subfolders here', f.dirs, num],
  ];
  const box = $('#stats');
  if (!box.children.length) {
    box.innerHTML = stats.map((s, i) => `<div class="stat" style="--i:${i}"><small>${icon(s[0])}${s[1]}</small><b>0</b></div>`).join('');
  }
  $$('.stat b', box).forEach((b, i) => countUp(b, stats[i][2], stats[i][3], 700));
}

/* ---------- list ---------- */
const HEADS = {
  browse: [['name', 'Name'], ['size', 'Size', 'r'], ['files', 'Files', 'r'], [null, '']],
  largest: [['name', 'File'], ['size', 'Size', 'r'], [null, ''], [null, '']],
};

function currentRows() {
  let rows = S.tab === 'browse' ? (S.folder ? S.folder.items : []) : S.largest;
  if (S.filter) {
    const q = S.filter.toLowerCase();
    rows = rows.filter(r => r.name.toLowerCase().includes(q));
  }
  const { key, dir } = S.sort;
  if (key === 'name') rows = [...rows].sort((a, b) => a.name.localeCompare(b.name) * -dir);
  else if (key === 'files') rows = [...rows].sort((a, b) => ((a.files || 0) - (b.files || 0)) * dir);
  else rows = [...rows].sort((a, b) => ((a.size - b.size) || ((a.cloud || 0) - (b.cloud || 0))) * dir);
  return rows;
}

function renderList(animate = true) {
  const list = $('#list');
  $('#listHead').innerHTML = HEADS[S.tab].map(([key, label, cls]) => key
    ? `<button data-sort="${key}" class="${cls || ''}">${label}${S.sort.key === key ? (S.sort.dir < 0 ? ' ↓' : ' ↑') : ''}</button>`
    : `<span>${label}</span>`).join('');

  S.rows = currentRows();
  S.rowByPath = new Map();
  const total = S.tab === 'browse' ? (S.folder.size || 1) : (S.largest[0] ? S.largest[0].size : 1);
  const rows = S.rows.map((r, i) => {
    const pct = r.size / total * 100;
    const cloudOnly = r.kind === 'file' && r.cloud && !r.size;
    const ic = r.kind === 'dir' ? 'folder' : cloudOnly ? 'cloud' : 'file';
    const color = S.colorByPath.get(r.path) || '';
    const extra = S.tab === 'largest'
      ? `<small title="${esc(r.dir)}">${esc(r.dir)}</small>`
      : `${r.denied ? '<span class="tag warn">no access</span>' : ''}${r.cloud ? `<span class="tag cloud">${icon('cloud')}${fmtSize(r.cloud)}</span>` : ''}`;
    return `<div class="row ${r.kind}${cloudOnly ? ' cloudonly' : ''}${i === S.sel ? ' sel' : ''}" data-i="${i}" style="--d:${Math.min(i, 24) * 18}ms">
      <div class="name"><span class="ic-wrap">${icon(ic)}</span><div class="nm-wrap">
        <div class="nm-line"><span class="nm" title="${esc(r.name)}">${esc(r.name)}</span>${extra}</div>
        <div class="track"><i data-w="${Math.max(pct, r.size ? .6 : 0)}%" ${color ? `style="--c:${color}"` : ''}></i></div></div></div>
      <div class="size r">${fmtSize(r.size)}<small>${pct.toFixed(pct < 10 ? 1 : 0)}%</small></div>
      <div class="cnt r">${r.kind === 'dir' ? num(r.files) : ''}</div>
      <button class="row-act" data-act="reveal" title="Show in Explorer">${icon('explorer')}</button>
    </div>`;
  });
  if (S.tab === 'browse' && S.folder.more.count && !S.filter) {
    rows.push(`<div class="more-row">+ ${num(S.folder.more.count)} smaller items (${fmtSize(S.folder.more.size)})</div>`);
  }
  list.innerHTML = rows.join('') || `<div class="list-empty">${S.filter ? 'Nothing matches the filter.' : 'This folder is empty.'}</div>`;
  $$('.row', list).forEach(el => S.rowByPath.set(S.rows[+el.dataset.i].path, el));
  if (animate) { list.classList.remove('anim'); void list.offsetWidth; list.classList.add('anim'); list.scrollTop = 0; }
  const bars = $$('.track i', list);
  if (animate) nextFrame().then(() => bars.forEach(b => { b.style.width = b.dataset.w; }));
  else bars.forEach(b => { b.style.transition = 'none'; b.style.width = b.dataset.w; });
}

$('#listHead').addEventListener('click', e => {
  const b = e.target.closest('button[data-sort]');
  if (!b) return;
  const key = b.dataset.sort;
  S.sort = { key, dir: S.sort.key === key ? -S.sort.dir : (key === 'name' ? 1 : -1) };
  S.sel = -1;
  renderList();
});
$('#filter').addEventListener('input', e => { S.filter = e.target.value; S.sel = -1; renderList(false); });

function select(i, scroll) {
  const list = $('#list');
  $$('.row.sel', list).forEach(r => r.classList.remove('sel'));
  S.sel = i;
  const el = $(`.row[data-i="${i}"]`, list);
  if (el) { el.classList.add('sel'); if (scroll) scrollWithin(list, el, 'nearest'); }
}
function activate(r) {
  if (!r) return;
  if (r.kind === 'dir') go(r.path, 'in'); else reveal(r.path);
}

const list = $('#list');
list.addEventListener('click', e => {
  const row = e.target.closest('.row');
  if (!row) return;
  const r = S.rows[+row.dataset.i];
  if (e.target.closest('[data-act="reveal"]')) { e.stopPropagation(); return reveal(r.path); }
  select(+row.dataset.i);
});
list.addEventListener('dblclick', e => {
  const row = e.target.closest('.row');
  if (row && !e.target.closest('.row-act')) activate(S.rows[+row.dataset.i]);
});
list.addEventListener('contextmenu', e => {
  const row = e.target.closest('.row');
  if (!row) return;
  e.preventDefault();
  select(+row.dataset.i);
  showCtx(e.clientX, e.clientY, itemMenu(S.rows[+row.dataset.i]));
});
list.addEventListener('mouseover', e => {
  const row = e.target.closest('.row');
  highlight(row ? S.rows[+row.dataset.i].path : null, 'list');
});
list.addEventListener('mouseleave', () => highlight(null));

function itemMenu(r) {
  const isDir = r.kind === 'dir';
  const entries = [];
  if (isDir) entries.push({ label: 'Open folder', icon: 'folder', fn: () => go(r.path, 'in') });
  if (S.tab === 'largest') entries.push({ label: 'Go to its folder', icon: 'arrow', fn: () => go(dirname(r.path), 'in') });
  entries.push({ label: 'Show in Explorer', icon: 'explorer', fn: () => reveal(r.path) });
  entries.push({ label: isDir ? 'Open in Explorer' : 'Open file', icon: 'open', fn: () => openItem(r.path) });
  entries.push('-');
  entries.push({ label: 'Ask AI: can I delete this?', icon: 'sparkle', cls: 'ai', ai: true, fn: () => openDrawerForPath(r) });
  if (isDir) entries.push({ label: 'Organise this folder', icon: 'grid', cls: 'ai', fn: () => organiseFolder(r.path) });
  entries.push('-');
  entries.push({ label: 'Copy path', icon: 'copy', fn: () => copyText(r.path) });
  return entries;
}

/* ---------- tabs ---------- */
function setTab(tab, animate = true) {
  S.tab = tab;
  S.sel = -1;
  S.sort = { key: 'size', dir: -1 };
  $$('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  moveInk();
  if (S.folder) renderList(animate);
}
function moveInk() {
  const b = $('#tabs button.active'), ink = $('.tab-ink');
  if (b) { ink.style.left = b.offsetLeft + 'px'; ink.style.width = b.offsetWidth + 'px'; }
}
$('#tabs').addEventListener('click', e => { const b = e.target.closest('button'); if (b) setTab(b.dataset.tab); });
addEventListener('resize', moveInk);

/* ================================================================ Sunburst */
const HUES = [258, 199, 158, 32, 330, 48, 286, 178, 12, 222, 96, 350];
const RINGS = { 1: [56, 103], 2: [106, 146] };
let sbRaf = 0;

function segColor(s, idx, isDark) {
  if (s.other || s.it.kind === 'files') return isDark ? 'hsl(225 10% 34%)' : 'hsl(225 14% 82%)';
  const h = HUES[idx % HUES.length];
  if (s.ring === 1) {
    if (s.it.kind === 'file') return isDark ? `hsl(${h} 22% 50%)` : `hsl(${h} 25% 66%)`;
    return isDark ? `hsl(${h} 72% 64%)` : `hsl(${h} 74% 58%)`;
  }
  const shade = (s.j % 3) * 5;
  return isDark ? `hsl(${h} 52% ${44 - shade}%)` : `hsl(${h} 70% ${76 - shade}%)`;
}

function arcPath(r0, r1, a0, a1) {
  let da = a1 - a0;
  if (da <= 0.0005) return '';
  if (da >= TAU - 1e-4) { a1 = a0 + TAU - 1e-4; da = a1 - a0; }
  const large = da > Math.PI ? 1 : 0;
  const p = (r, a) => `${(r * Math.sin(a)).toFixed(2)} ${(-r * Math.cos(a)).toFixed(2)}`;
  return `M${p(r1, a0)}A${r1} ${r1} 0 ${large} 1 ${p(r1, a1)}L${p(r0, a1)}A${r0} ${r0} 0 ${large} 0 ${p(r0, a0)}Z`;
}

function buildSegments(f) {
  const total = f.size;
  const inner = [], outer = [];
  if (!total) return { inner, outer };
  let a = 0, other = f.more.size;
  for (const it of f.items) {
    if (it.size <= 0) continue;
    const da = it.size / total * TAU;
    if (da < 0.03) { other += it.size; continue; }
    inner.push({ it, a0: a, a1: a + da, ring: 1, ci: inner.length });
    a += da;
  }
  if (other > 0) inner.push({ it: { name: 'Smaller items', size: other, kind: 'other' }, a0: a, a1: Math.min(TAU, a + other / total * TAU), ring: 1, other: true });
  for (const s of inner) {
    if (s.it.kind !== 'dir' || !s.it.kids || !s.it.size) continue;
    let b = s.a0;
    const span = s.a1 - s.a0;
    s.it.kids.forEach((k, j) => {
      const db = k.size / s.it.size * span;
      if (db >= 0.014) outer.push({ it: k, a0: b, a1: b + db, ring: 2, parent: s, j });
      b += db;
    });
  }
  return { inner, outer };
}

function drawSunburst(dir = 'in') {
  const svg = $('#sunburst'), f = S.folder;
  const isDark = document.documentElement.dataset.theme === 'dark';
  const { inner, outer } = buildSegments(f);
  const all = [...inner, ...outer];
  S.segs = all;
  S.colorByPath = new Map();
  inner.forEach(s => { s.color = segColor(s, s.ci, isDark); if (s.it.path) S.colorByPath.set(s.it.path, s.color); });
  outer.forEach(s => { s.color = segColor(s, s.parent.ci, isDark); });

  const from = dir === 'in' ? 'from-in' : dir === 'out' ? 'from-out' : '';
  svg.innerHTML = `<g class="g ${from}"><circle class="center" r="52"/>${all.map((s, i) => `<path data-i="${i}" fill="${s.color}"/>`).join('')}</g>`;
  const g = svg.firstChild, paths = $$('path', svg);
  if (from) nextFrame().then(() => g.classList.remove(from));

  cancelAnimationFrame(sbRaf);
  const dur = dir === 'none' || reduceMotion() ? 0 : 950;
  const t0 = performance.now();
  const frame = now => {
    const t = dur ? Math.min(1, (now - t0) / dur) : 1;
    const e = 1 - Math.pow(1 - t, 3);
    all.forEach((s, i) => {
      const [r0, r1] = RINGS[s.ring];
      const grow = s.ring === 2 ? Math.max(0, Math.min(1, (e - .25) / .75)) : 1;
      paths[i].setAttribute('d', arcPath(r0, r0 + (r1 - r0) * grow, s.a0 * e, s.a1 * e));
    });
    if (t < 1) sbRaf = requestAnimationFrame(frame);
  };
  sbRaf = requestAnimationFrame(frame);

  $('#chartCenter').innerHTML = `<b>${fmtSize(f.size)}</b><span>${esc(f.name)}</span>${f.parent ? '<small>click to go up</small>' : ''}`;
  $('#legend').innerHTML = inner.slice(0, 8).map((s, i) =>
    `<button data-i="${i}" style="--i:${i}"><i style="background:${s.color}"></i><span>${esc(s.it.name)}</span><em>${(s.it.size / (f.size || 1) * 100).toFixed(1)}%</em></button>`).join('');
}

const sb = $('#sunburst'), tip = $('#tip');
sb.addEventListener('mousemove', e => {
  const p = e.target.closest('path');
  if (!p) { tip.classList.remove('show'); return highlight(null); }
  const s = S.segs[+p.dataset.i];
  const base = s.ring === 1 ? S.folder.size : s.parent.it.size;
  tip.innerHTML = `<b>${esc(s.it.name)}</b>${fmtSize(s.it.size)} · ${(s.it.size / (base || 1) * 100).toFixed(1)}%${s.ring === 2 ? ` of ${esc(s.parent.it.name)}` : ''}`;
  const box = sb.parentElement.getBoundingClientRect();
  tip.style.left = Math.min(e.clientX - box.left + 14, box.width - 150) + 'px';
  tip.style.top = (e.clientY - box.top + 14) + 'px';
  tip.classList.add('show');
  highlight(s.ring === 1 ? s.it.path : s.parent.it.path, 'chart', s);
});
sb.addEventListener('mouseleave', () => { tip.classList.remove('show'); highlight(null); });
sb.addEventListener('click', e => {
  if (e.target.classList.contains('center')) return goUp();
  const p = e.target.closest('path');
  if (!p) return;
  const s = S.segs[+p.dataset.i];
  tip.classList.remove('show');
  if (s.other) return;
  if (s.it.kind === 'dir') return go(s.it.path, 'in');
  if (s.it.kind === 'files') return go(s.it.path, 'in');
  const row = S.rowByPath.get(s.it.path);
  if (row) select(+row.dataset.i, true);
});
$('#legend').addEventListener('click', e => {
  const b = e.target.closest('button');
  if (!b) return;
  const s = S.segs[+b.dataset.i];
  if (s.it.kind === 'dir') go(s.it.path, 'in');
  else { const row = S.rowByPath.get(s.it.path); if (row) select(+row.dataset.i, true); }
});
$('#legend').addEventListener('mouseover', e => {
  const b = e.target.closest('button');
  highlight(b ? S.segs[+b.dataset.i].it.path : null, 'legend');
});
$('#legend').addEventListener('mouseleave', () => highlight(null));

let lastHl = null;
function highlight(path, source, seg) {
  const key = path + '|' + (seg ? seg.it.path + seg.ring : '');
  if (key === lastHl) return;
  lastHl = key;
  $$('#list .row.hl, #legend button.hl').forEach(el => el.classList.remove('hl'));
  const paths = $$('#sunburst path');
  paths.forEach(p => p.classList.remove('hl'));
  sb.classList.toggle('hovering', !!path);
  if (!path) return;
  S.segs.forEach((s, i) => {
    const owner = s.ring === 1 ? s.it.path : s.parent.it.path;
    if (owner === path && (!seg || seg.ring === 1 || s === seg || s === seg.parent)) paths[i].classList.add('hl');
  });
  const row = S.rowByPath.get(path);
  if (row) row.classList.add('hl');
  const li = S.segs.findIndex(s => s.ring === 1 && s.it.path === path);
  if (li >= 0 && li < 8) $(`#legend button[data-i="${li}"]`)?.classList.add('hl');
}

/* ================================================================ Mode switching */
function setMode(mode, view) {
  S.mode = mode;
  $$('#nav button').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
  movePill();
  $('.app').classList.toggle('no-panel', !PANEL_MODES.includes(mode));
  $('#panel-cleanup').classList.toggle('active', mode === 'cleanup');
  $('#panel-organise').classList.toggle('active', mode === 'organise');
  closeDrawer();
  updateOrgFolder();
  if (S.scanning && PANEL_MODES.includes(mode)) return showView('scanning');
  const target = view || (PANEL_MODES.includes(mode) && S.folder ? 'explorer' : START_VIEW[mode]);
  showView(target);
  if (target === 'quick' && !S.qc.targets.length) loadQuick();
}
function movePill() {
  const b = $('#nav button.active');
  if (b) $('.nav-pill').style.transform = `translateY(${b.offsetTop}px)`;
}
$('#nav').addEventListener('click', e => { const b = e.target.closest('button'); if (b) setMode(b.dataset.mode); });
addEventListener('resize', movePill);

function busy(btn, on) { btn.classList.toggle('loading', on); btn.disabled = on; }
// Action tiles show a scan beam and a status line instead of a spinner.
function tileBusy(btn, on, label) {
  if (!btn) return;
  btn.classList.toggle('scanning', on);
  btn.disabled = on;
  const small = $('small', btn);
  if (small) small.textContent = on ? label : small.dataset.idle;
}
const scanAnim = () => '<div class="scan-anim"><i></i><i></i><i></i><b></b></div>';
const needScan = () => { if (!S.root) { toast('info', 'Scan a drive or folder first'); return true; } return false; };

/* ================================================================ Clean-up mode */
const RISK_ICON = { Safe: 'shield', Review: 'eye', Caution: 'alert', Keep: 'lock' };

$('#findBtn').addEventListener('click', async () => {
  if (needScan()) return;
  const btn = $('#findBtn');
  busy(btn, true);
  try {
    S.cats = await Bridge.call('find_candidates');
    S.ai = null;
    renderCats();
    toast('ok', `Found ${num(S.cats.reduce((n, c) => n + c.count, 0))} items in ${S.cats.length} categories`);
  } catch (e) { fail(e); }
  busy(btn, false);
});

$('#reviewBtn').addEventListener('click', async () => {
  if (needScan()) return;
  const btn = $('#reviewBtn');
  busy(btn, true);
  if (!await confirmAiCost('review')) return busy(btn, false);
  aiBusy(1);
  try {
    if (!S.cats.length) { S.cats = await Bridge.call('find_candidates'); renderCats(); }
    const r = await Bridge.call('ai_review');
    if (S.ai) { S.ai.running = false; renderAiCard(); }
    if (!r.count) toast('info', 'No large unrecognised folders to review');
    else toast('ok', `${r.model} reviewed ${r.count} folders${usageText(r.usage)}`, 6000);
  } catch (e) {
    if (S.ai) { S.ai.running = false; renderAiCard(); }
    fail(e);
  }
  aiBusy(-1);
  busy(btn, false);
});

function totals() {
  const t = { Safe: 0, Review: 0, Caution: 0, Keep: 0 };
  S.cats.forEach(c => { t[c.risk] += c.total; });
  if (!S.ai) return t;
  // AI suggestions can be nested (a folder and one of its subfolders) or contain rule items - count each byte once.
  const lower = p => p.toLowerCase().replace(/[\\/]+$/, '');
  const counted = S.cats.flatMap(c => (c.items || []).map(i => lower(i.path)));
  const inside = (p, q) => p === q || p.startsWith(q + '\\');
  [...S.ai.items].sort((a, b) => a.path.length - b.path.length).forEach(i => {
    const p = lower(i.path);
    if (counted.some(q => inside(p, q))) return;
    const within = counted.filter(q => inside(q, p));       // rule items already counted inside this folder
    t[i.risk] += Math.max(0, i.size - S.cats.flatMap(c => c.items || []).filter(x => within.includes(lower(x.path))).reduce((n, x) => n + x.size, 0));
    counted.push(p);
  });
  return t;
}
function updateTiles() {
  const t = totals();
  const empty = !S.cats.length && !S.ai;
  [['#tSafe', t.Safe], ['#tReview', t.Review + t.Caution], ['#tKeep', t.Keep]].forEach(([sel, v]) => {
    const el = $(sel);
    if (empty) { el._v = 0; el.textContent = '—'; return; }
    if (el._v !== v) {
      countUp(el, v, fmtSize, 900);
      const tile = el.parentElement;
      tile.classList.remove('bump'); void tile.offsetWidth; tile.classList.add('bump');
    }
  });
}

function catHtml(c, ci) {
  return `<div class="cat risk-${c.risk}" data-ci="${ci}" data-name="${esc(c.name)}" style="--d:${ci * 45}ms">
    <button class="cat-head"><span class="cat-ic">${icon(RISK_ICON[c.risk])}</span>
      <span class="cat-title"><b title="${esc(c.name)}">${esc(c.name)}</b><small>${num(c.count)} item${c.count === 1 ? '' : 's'}</small></span>
      <span class="cat-size">${fmtSize(c.total)}</span><span class="pill">${c.risk}</span>${icon('chevron', 'chev')}</button>
    <div class="cat-body"><div class="cat-inner"><div class="pad"></div></div></div></div>`;
}

function itemHtml(it, ii, showRisk, extra = '') {
  const a = it.act && ACTS[it.act];
  return `<div class="item ${extra}${a ? ' has-act' : ''}" data-ii="${ii}" style="--i:${Math.min(ii, 16)}">
    <div class="item-name"><b>${esc(basename(it.path))}</b><small>${esc(dirname(it.path))}</small></div>
    <div class="item-size">${showRisk ? `<span class="pill risk-${it.risk}">${it.risk}</span>` : ''}${fmtSize(it.size)}<small>${esc(it.note)}</small></div>
    ${a ? `<button class="item-act ${it.act}" data-act="clean" title="${a.label}">${icon(a.icon)}</button>` : ''}
    <button class="row-act" data-act="reveal" title="Show in Explorer">${icon('explorer')}</button></div>`;
}

function fillCat(card, c, limit = 40) {
  const pad = $('.pad', card);
  const bulk = c.bulk && ACTS[c.bulk];
  pad.innerHTML = `${bulk ? `<div class="bulk-row"><small>${esc(bulk.note)}</small>
      <button class="btn clean sm" data-act="bulk">${icon(bulk.icon)}${bulk.verb} all · ${fmtSize(c.total)}</button></div>` : ''}
    <p class="cat-text"><b>Impact:</b> ${esc(c.impact)}<br><b>How:</b> ${esc(c.how)}</p>
    <div class="items">${c.items.slice(0, limit).map((it, ii) => itemHtml(it, ii, false)).join('')}</div>
    ${c.items.length > limit ? `<button class="link more" data-limit="${limit + 100}">Show ${Math.min(100, c.items.length - limit)} more</button>` : ''}
    ${c.count > c.items.length ? `<div class="more-row">Showing the largest ${c.items.length} of ${num(c.count)}</div>` : ''}`;
  card._filled = true;
}

function renderCats() {
  const box = $('#cats');
  if (!S.cats.length && !S.ai) {
    box.innerHTML = `<div id="vdSlot"></div><div class="empty-state">${icon('broom')}${S.root ? 'Ready. Click <b>Find clean-up candidates</b> to see what can go.' : 'Scan a drive, then find clean-up candidates.'}</div>`;
  } else {
    box.innerHTML = '<div id="vdSlot"></div><div id="aiSlot"></div>' + S.cats.map(catHtml).join('');
    renderAiCard();
  }
  renderVd();
  updateTiles();
}

function renderAiCard() {
  let slot = $('#aiSlot');
  if (!slot) { renderCats(); slot = $('#aiSlot'); if (!slot) return; }
  const a = S.ai;
  if (!a) { slot.innerHTML = ''; return; }
  const total = a.items.reduce((n, i) => n + i.size, 0);
  const sub = a.running ? `Asking ${esc(a.model)}… ${a.done}/${a.total} folders` : `${a.items.length} folders reviewed by ${esc(a.model)}`;
  const items = a.items.map((it, ii) => itemHtml(it, ii, true, ii >= a.shown ? 'pop' : '')).join('');
  const placeholders = a.running ? '<i class="shimmer" style="height:46px;margin:4px 0"></i><i class="shimmer" style="height:46px;width:80%"></i>' : '';
  const pct = a.total ? a.done / a.total * 100 : 0;
  slot.innerHTML = `<div class="cat risk-AI open" data-ci="ai">
    <button class="cat-head"><span class="cat-ic">${icon('sparkle')}</span>
      <span class="cat-title"><b>AI review of large folders</b><small>${sub}</small></span>
      <span class="cat-size">${fmtSize(total)}</span><span class="pill">AI</span>${icon('chevron', 'chev')}</button>
    ${a.running ? `<div class="ai-progress ${a.done ? '' : 'indet'}"><i style="width:${pct}%"></i></div>` : ''}
    <div class="cat-body"><div class="cat-inner"><div class="pad">
      <p class="cat-text">Suggestions from your local model for big folders the rules don't recognise. <b>AI can be wrong — check before deleting.</b></p>
      <div class="items">${items}${placeholders}</div></div></div></div></div>`;
  a.shown = a.items.length;
}

const catsBox = $('#cats');
catsBox.addEventListener('click', e => {
  const card = e.target.closest('.cat');
  if (!card || card.classList.contains('vd-card')) return;
  const isAi = card.dataset.ci === 'ai';
  const c = isAi ? null : S.cats[+card.dataset.ci];
  if (e.target.closest('.cat-head')) {
    if (!isAi && !card._filled) fillCat(card, c);
    card.classList.toggle('open');
    return;
  }
  const more = e.target.closest('.more');
  if (more) return fillCat(card, c, +more.dataset.limit);
  if (e.target.closest('[data-act="bulk"]')) return cleanCategory(c, e.target.closest('button'));
  const itemEl = e.target.closest('.item');
  if (!itemEl) return;
  const it = isAi ? S.ai.items[+itemEl.dataset.ii] : c.items[+itemEl.dataset.ii];
  if (e.target.closest('[data-act="reveal"]')) return reveal(it.path);
  if (e.target.closest('[data-act="clean"]')) return cleanItem(it, itemEl);
  openDrawerForItem(it, c);
});

/* ---------- cleaning from the panel ---------- */
async function cleanItem(it, el) {
  const a = ACTS[it.act];
  const cloudWarn = it.cloud && it.act === 'recycle'
    ? '<p class="warn">This is in a cloud-synced folder, so it is also removed from the cloud (OneDrive keeps it in its own recycle bin for a while).</p>' : '';
  const ok = await confirmDialog({
    title: `${a.verb}?`, icon: a.icon, danger: !!a.danger, okLabel: a.verb,
    body: `<ul><li><span>${esc(basename(it.path) || it.path)}</span><span>${fmtSize(it.size)}</span></li></ul>
      <p>${esc(a.note)}</p>${cloudWarn}`,
  });
  if (!ok) return;
  if (el) el.style.opacity = '.5';
  try {
    const r = await Bridge.call('clean_item', it.path);
    if (el) { el.classList.add('leaving'); await sleep(400); }
    if (drawerPath === it.path) closeDrawer();
    applyCleanResult(r);
    toast('ok', `${it.act === 'freeup' ? 'Freed up' : 'Freed'} ${fmtSize(r.freed)}` +
      (r.skipped ? ` · ${num(r.skipped)} files in use were skipped` : ''));
    refreshFolder();
  } catch (e) {
    if (el) el.style.opacity = '';
    fail(e);
  }
}

async function cleanCategory(c, btn) {
  const a = ACTS[c.bulk];
  const ok = await confirmDialog({
    title: `${a.verb} all ${c.count} item${c.count === 1 ? '' : 's'}?`, icon: a.icon, danger: !!a.danger,
    okLabel: `${a.verb} · ${fmtSize(c.total)}`,
    body: `<ul>${c.items.slice(0, 8).map(it => `<li><span>${esc(basename(it.path))}</span><span>${fmtSize(it.size)}</span></li>`).join('')}
      ${c.count > 8 ? `<li><span>… and ${c.count - 8} more</span><span></span></li>` : ''}</ul><p>${esc(a.note)}</p>`,
  });
  if (!ok) return;
  busy(btn, true);
  try {
    const r = await Bridge.call('clean_category', c.name);
    applyCleanResult(r);
    toast(r.errors.length ? 'info' : 'ok', `Freed ${fmtSize(r.freed)}` +
      (r.skipped ? ` · ${num(r.skipped)} files in use were skipped` : '') +
      (r.errors.length ? ` · ${r.errors.length} could not be cleaned` : ''), 5000);
    refreshFolder();
  } catch (e) { fail(e); busy(btn, false); }
}

function applyCleanResult(r) {
  const open = new Set($$('#cats .cat.open').map(c => c.dataset.name));
  S.cats = r.categories;
  if (r.ai_items && S.ai) { S.ai.items = r.ai_items; S.ai.shown = r.ai_items.length; }
  renderCats();
  $$('#cats .cat[data-name]').forEach(card => {
    if (!open.has(card.dataset.name)) return;
    card.style.animation = 'none';
    fillCat(card, S.cats[+card.dataset.ci]);
    card.classList.add('open');
    $$('.item', card).forEach(i => { i.style.animation = 'none'; });
  });
}
catsBox.addEventListener('contextmenu', e => {
  const itemEl = e.target.closest('.item'), card = e.target.closest('.cat');
  if (!itemEl || card.classList.contains('vd-card')) return;
  e.preventDefault();
  const isAi = card.dataset.ci === 'ai';
  const c = isAi ? null : S.cats[+card.dataset.ci];
  const it = isAi ? S.ai.items[+itemEl.dataset.ii] : c.items[+itemEl.dataset.ii];
  showCtx(e.clientX, e.clientY, [
    ...(it.act ? [{ label: ACTS[it.act].label, icon: ACTS[it.act].icon, fn: () => cleanItem(it, itemEl) }, '-'] : []),
    { label: 'Details & impact', icon: 'info', fn: () => openDrawerForItem(it, c) },
    { label: 'Show in Explorer', icon: 'explorer', fn: () => reveal(it.path) },
    { label: 'Go to in explorer view', icon: 'arrow', fn: () => go(it.kind === 'dir' ? it.path : dirname(it.path), 'in') },
    '-',
    { label: 'Ask AI about this', icon: 'sparkle', cls: 'ai', ai: true, fn: () => { openDrawerForItem(it, c); askAi(it.path); } },
    { label: 'Copy path', icon: 'copy', fn: () => copyText(it.path) },
  ]);
});

/* ================================================================ Details drawer */
const drawer = $('#drawer'), drawerInner = $('#drawerInner');
let drawerPath = null;

let drawerAction = null;
function openDrawer({ kicker, risk, title, path, chips = [], sections = [], callouts = [], action = null }) {
  drawerPath = path;
  drawerAction = action;
  drawerInner.style.setProperty('--c', risk ? `var(--${risk.toLowerCase()})` : 'var(--accent)');
  drawerInner.innerHTML = `
    <div class="d-top"><div class="d-title"><div class="d-kicker">${esc(kicker)}</div><h3>${esc(title)}</h3><div class="d-path">${esc(path)}</div></div>
      <button class="icon-btn" data-act="close" title="Close (Esc)">${icon('x')}</button></div>
    <div class="d-meta">${risk ? `<span class="pill risk-${risk}">${risk}</span>` : ''}${chips.map(c => `<span class="chip">${esc(c)}</span>`).join('')}</div>
    ${sections.filter(s => s[1]).map((s, i) => `<div class="d-sec" style="--i:${i}"><h4>${esc(s[0])}</h4><p>${esc(s[1])}</p></div>`).join('')}
    ${callouts.map(c => `<div class="callout ${c[0]}">${icon(c[0] === 'warn' ? 'alert' : 'cloud')}<span>${esc(c[1])}</span></div>`).join('')}
    <div class="d-actions">
      ${action ? `<button class="btn ${ACTS[action.act].danger ? 'danger' : 'clean'}" data-act="do">${icon(ACTS[action.act].icon)}${ACTS[action.act].label}</button>` : ''}
      <button class="btn" data-act="reveal">${icon('explorer')}Show in Explorer</button>
      <button class="btn ai ai-only" data-act="ai">${icon('sparkle')}Ask AI</button>
      <button class="btn" data-act="copy">${icon('copy')}Copy path</button>
    </div>
    <div id="aiAnswer"></div>`;
  drawer.classList.add('open');
}
function closeDrawer() { drawer.classList.remove('open'); drawerPath = null; }

function openDrawerForItem(it, c) {
  const isAi = !c;
  const callouts = [];
  if (it.risk === 'Keep') callouts.push(['warn', 'Do not delete this manually — see "How to clean" for the safe way.']);
  if (it.cloud && !isAi && c.name !== 'Cloud files kept on this PC') callouts.push(['info', S.cloudNote]);
  openDrawer({
    kicker: isAi ? 'AI review' : c.name, risk: it.risk, title: basename(it.path) || it.path, path: it.path,
    chips: [fmtSize(it.size), it.note].filter(Boolean),
    sections: isAi
      ? [['What it is', it.note], ['Impact', it.impact], ['Suggested action', it.action]]
      : [['Impact', c.impact], ['How to clean', c.how]],
    callouts: isAi ? [['warn', 'AI suggestion — it can be wrong. Check before deleting.'], ...callouts] : callouts,
    action: it.act ? { act: it.act, fn: () => cleanItem(it, null) } : null,
  });
}

function openDrawerForPath(r) {
  if (S.mode !== 'cleanup') setMode('cleanup');
  openDrawer({
    kicker: r.kind === 'dir' ? 'Folder' : 'File', title: r.name, path: r.path,
    chips: [fmtSize(r.size) + ' on disk', r.cloud ? fmtSize(r.cloud) + ' online-only' : '', r.kind === 'dir' ? num(r.files) + ' files' : ''].filter(Boolean),
  });
  if (S.aiOn) askAi(r.path);
}

async function askAi(path) {
  if (!$('#aiAnswer') || !await confirmAiCost('explain', path)) return;
  const box = $('#aiAnswer');
  if (!box || drawerPath !== path) return;
  box.innerHTML = `<div class="ai-answer"><div class="ai-head">${icon('sparkle')}Asking ${esc(S.model || 'AI')}…</div><span class="thinking"><i></i><i></i><i></i></span></div>`;
  scrollWithin(drawerInner, box, 'nearest');
  aiBusy(1);
  try {
    const r = await Bridge.call('ai_explain', path);
    if (drawerPath !== path) return;
    box.innerHTML = `<div class="ai-answer"><div class="ai-head">${icon('sparkle')}${esc(r.model)}<span class="muted" style="font-weight:500">${esc(usageText(r.usage))}</span></div><p class="ai-text"></p>
      <p class="disclaimer" style="text-align:left;margin:8px 0 0">AI answers can be wrong — check before deleting.</p></div>`;
    await typeText($('.ai-text', box), r.answer);
  } catch (e) {
    box.innerHTML = '';
    fail(e);
  } finally { aiBusy(-1); }
}

drawer.addEventListener('click', e => {
  if (e.target === drawer) return closeDrawer();
  const b = e.target.closest('[data-act]');
  if (!b || !drawerPath) return;
  const act = b.dataset.act;
  if (act === 'close') closeDrawer();
  else if (act === 'do' && drawerAction) drawerAction.fn();
  else if (act === 'reveal') reveal(drawerPath);
  else if (act === 'copy') copyText(drawerPath);
  else if (act === 'ai') askAi(drawerPath);
});

/* ================================================================ Organiser mode */
const TYPE_COLORS = { Documents: '#6d4aff', Images: '#0ea5e9', Videos: '#f43f5e', Audio: '#f59e0b', Archives: '#84cc16',
  Installers: '#ef4444', Code: '#14b8a6', Other: '#94a3b8' };

function updateOrgFolder() {
  const el = $('#orgFolder');
  if (!S.folder) return;
  const stale = S.profile && S.profile.path !== S.folder.path;
  el.innerHTML = `${esc(S.folder.path)} · ${fmtSize(S.folder.size + S.folder.cloud)}${stale ? ' · <b>not analysed yet</b>' : ''}`;
}
function resetOrganiser() {
  $('#orgBody').innerHTML = `<div id="clsSlot"></div><div id="vdSlotOrg"></div><div class="empty-state">${icon('grid')}Pick a folder in the middle of the screen (Downloads, Documents…) or choose any folder. Its health check and plan appear here.</div>`;
  renderVd();
  renderCls();
}

async function analyse() {
  if (needScan()) return null;
  const btn = $('#analyseBtn');
  busy(btn, true);
  try {
    S.profile = await Bridge.call('analyse_folder', S.folder.path);
    S.plan = null;
    renderProfile(S.profile);
    updateOrgFolder();
    return S.profile;
  } catch (e) { fail(e); return null; } finally { busy(btn, false); }
}
$('#analyseBtn').addEventListener('click', analyse);

/* ---------- one dialog: what the plan does, optional deep analysis, token comparison ---------- */
const fmtCost = c => (c == null ? null : `≈ $${c < 0.01 ? c.toFixed(4) : c.toFixed(2)}`);

// The three ways to run deep analysis when a cloud API is configured. Deep analysis = file names + a short excerpt
// from files whose names say nothing; the "light" choice drops the excerpts, so those files stay "check by hand".
function deepModes(group, d, label) {
  const n = d.reads.length, s = n === 1 ? '' : 's';
  const unclear = n ? ` (${d.reads.slice(0, 3).map(esc).join(', ')}${n > 3 ? '…' : ''})` : '';
  return `
    ${d.ollama ? `<label><input type="radio" name="${group}" value="local" checked><span>
      <b>Full deep analysis on this PC (local model)</b>
      <small>Names and short excerpts are checked by Ollama on your computer — nothing leaves your PC. Slower.</small></span></label>` : ''}
    ${n ? `<label><input type="radio" name="${group}" value="full" ${d.ollama ? '' : ''}><span>
      <b>Full deep analysis with ${esc(label)}</b>
      <small>Sends file names <u>and</u> the first ~1,500 characters of ${n} file${s} whose names say nothing${unclear}. Most accurate.</small></span></label>` : ''}
    <label><input type="radio" name="${group}" value="names_only" ${d.ollama ? '' : 'checked'}><span>
      <b>Light analysis with ${esc(label)} — names only</b>
      <small>Only file names are sent; nothing inside files is read. ${n ? `The ${n} file${s} with unclear names can't be sorted and stay "check by hand".` : ''}</small></span></label>`;
}

async function planDialog() {
  if (needScan()) return;
  if (!S.profile || S.profile.path !== S.folder.path) { if (!await analyse()) return; }
  const btn = $('#planBtn'), path = S.folder.path;
  busy(btn, true);
  let e;
  try { e = await Bridge.call('plan_estimate', path); } catch (err) { busy(btn, false); return fail(err); }
  busy(btn, false);
  const d = e.deep, s = n => (n === 1 ? '' : 's');
  const canDeep = d.docs > 0;
  const cloudDeep = e.ai && !e.local && (d.names.length || d.reads.length);
  const planTok = e.plan ? e.plan.input + e.plan.output : 0;
  const deepTok = d.estimate ? d.estimate.input + d.estimate.output : 0;
  const bothCost = e.plan && e.plan.cost != null ? (e.plan.cost + (d.estimate && d.estimate.cost != null ? d.estimate.cost : 0)) : null;
  const costCell = c => (e.local ? 'free' : fmtCost(c) || 'add prices in AI settings');
  const sent = { names: d.names.length ? `${d.names.length} file name${s(d.names.length)}` : '',
                 reads: d.reads.length ? `text from inside ${d.reads.length} file${s(d.reads.length)}` : '' };
  const deepLeaves = mode => (e.local || mode === 'local') ? 'file names & folder facts — deep analysis stays on this PC'
    : `+ ${[sent.names, mode === 'names_only' ? '' : sent.reads].filter(Boolean).join(' & ') || 'nothing more'}`;
  const cmp = e.ai && e.plan ? `<table class="pd-cmp" id="pdCmp">
      <tr><th></th><th>Plan only</th><th>Plan + deep analysis</th></tr>
      <tr><td>Requests</td><td>${e.plan.requests}</td><td>${e.plan.requests + (d.estimate ? d.estimate.requests : 0)}</td></tr>
      <tr><td>Tokens</td><td>≈ ${num(planTok)}</td><td>≈ ${num(planTok + deepTok)}</td></tr>
      <tr><td>${e.local ? 'Cost' : 'Estimated cost'}</td><td>${costCell(e.plan.cost)}</td><td>${costCell(bothCost)}</td></tr>
      <tr><td>Leaves your PC</td><td>${e.local ? 'nothing' : 'file names & folder facts'}</td>
        <td id="pdLeaves">${e.local ? 'nothing' : deepLeaves(d.ollama ? 'local' : 'names_only')}</td></tr>
    </table>
    <p class="ais-note">${e.local ? `Runs on this PC with ${esc(e.model)} — free and private. Usually 1–3 minutes.` : `Uses ${esc(e.label)} (${esc(e.model)}). Token counts are ${e.plan.exact ? 'exact' : 'estimates'}.`}</p>` : '';
  const privacy = cloudDeep ? `<div id="pdPrivacy" hidden>
      <div class="warn-note" style="margin-top:4px"><b>Privacy for deep analysis:</b> with a cloud model it would send
        ${[sent.names, sent.reads ? `${sent.reads} (${d.reads.slice(0, 5).map(esc).join(', ')}${d.reads.length > 5 ? '…' : ''})` : ''].filter(Boolean).join(' and ')}
        to ${esc(e.label)}. Personal documents are safer with a local model.</div>
      <div class="cls-modes">${deepModes('pdMode', d, e.label)}</div></div>` : '';
  const pending = confirmDialog({
    title: e.ai ? 'AI analysis' : 'Suggest a plan', icon: 'sparkle', okLabel: 'Create plan',
    body: `<div class="pd-sec"><div class="pd-head">${icon(e.ai ? 'sparkle' : 'grid')}<b>${e.ai ? 'AI organisation plan' : 'Suggested plan (rules)'}</b><span class="pill">included</span></div>
        <p>${e.ai ? `Looks at the file names, types, dates and subfolders in <b>${esc(S.folder.name)}</b> and suggests a folder structure — and which files should go where.`
          : `Groups the loose files in <b>${esc(S.folder.name)}</b> by type into folders (Documents, Pictures, Archives…). No AI.`}</p>
        ${e.ai ? `<p class="ais-note">${e.local ? 'Runs locally.' : `Only names and folder facts are sent to ${esc(e.label)}`} — never what's inside your files.</p>` : ''}</div>
      <label class="pd-sec pd-opt${canDeep ? '' : ' off'}"><input type="checkbox" id="pdDeep" ${canDeep ? '' : 'disabled'}>
        <div><div class="pd-head">${icon('files')}<b>Also deep analyse documents</b><span class="pill">optional</span></div>
        <p>${canDeep ? `Sorts the ${d.docs} PDF / Word / Excel / text file${s(d.docs)} stored on this PC into Bills, KYC, Bank & tax… so they land in the right folder.` : 'There are no document files stored on this PC directly in this folder.'}</p>
        ${canDeep ? `<p class="ais-note">${d.by_name} by name (not opened) · ${d.names.length} name${s(d.names.length)} ${e.ai ? 'checked by AI' : 'left for you'} · ${d.reads.length} ${e.ai ? `short excerpt${s(d.reads.length)} read` : 'unclear names left for you'}${d.cached ? ` · ${d.cached} already done` : ''}</p>` : ''}</div></label>
      ${privacy}
      ${cmp}
      <p class="ais-note">Nothing is moved yet — you'll see the plan first, then decide.</p>`,
  });
  $('.modal-card').classList.add('wide');
  const deepBox = $('#pdDeep');
  const syncDeep = () => {
    const on = deepBox && deepBox.checked;
    if ($('#pdPrivacy')) $('#pdPrivacy').hidden = !on;
    if ($('#pdCmp')) $('#pdCmp').classList.toggle('deep', !!on);
  };
  if (deepBox) deepBox.addEventListener('change', syncDeep);
  $$('input[name=pdMode]').forEach(r => r.addEventListener('change', () => {
    if ($('#pdLeaves')) $('#pdLeaves').textContent = deepLeaves(r.value);
  }));
  const ok = await pending;
  const deep = !!(deepBox && deepBox.checked);
  const choice = $('input[name=pdMode]:checked');
  $('.modal-card').classList.remove('wide');
  if (!ok) return;
  runPlan(path, e.ai, deep, cloudDeep && deep ? (choice ? choice.value : 'names_only') : 'full');
}

async function runPlan(path, useAi, deep, deepMode) {
  const btn = $('#planBtn');
  busy(btn, true);
  if (useAi || deep) aiBusy(1);
  const box = $('#planBox');
  box.innerHTML = `<div class="cat risk-AI"><div class="scan-card-run">${scanAnim()}<div class="grow">
      <b>${deep ? 'Deep analysing documents, then planning…' : useAi ? `Asking ${esc(S.model || 'AI')} for a plan…` : 'Building the plan…'} <span class="muted" id="planTimer">0s</span></b>
      <small id="planStage">${S.aiLocal ? 'Usually 1–3 minutes with a local model.' : 'Usually under a minute with a cloud model.'} You can keep exploring meanwhile.</small>
      <div class="ai-progress indet"><i></i></div></div></div></div>`;
  scrollWithin($('#orgBody'), box);
  const t0 = Date.now();
  const timer = setInterval(() => { const t = $('#planTimer'); if (t) t.textContent = Math.round((Date.now() - t0) / 1000) + 's'; }, 1000);
  try {
    const plan = await Bridge.call(useAi ? 'ai_plan' : 'rule_plan', path, deep, deepMode);
    if (S.profile && S.profile.path === path) {
      S.plan = plan;
      if (plan.deep) { S.cls = { ...plan.deep, merged: true }; renderCls(); }
      await renderPlan(plan);
      scrollWithin($('#orgBody'), $('#planBox'));
    }
    toast('ok', `Plan ready${plan.deep ? ' (with deep analysis)' : ''}${usageText(plan.usage)}`, 6000);
  } catch (e) { box.innerHTML = ''; fail(e); }
  clearInterval(timer);
  if (useAi || deep) aiBusy(-1);
  busy(btn, false);
}

const makePlan = () => planDialog();
$('#planBtn').addEventListener('click', makePlan);

function organiseFolder(path) {
  setMode('organise');
  go(path, 'in').then(makePlan);
}

function renderProfile(p) {
  const score = p.score;
  const level = score >= 80 ? ['safe', 'Tidy'] : score >= 55 ? ['review', 'Could be tidier'] : ['keep', 'Messy'];
  const typeTotal = p.by_type.reduce((n, t) => n + t[1], 0) || 1;
  const listCard = (key, title, risk, items, note = '') => items.length ? `
    <div class="cat risk-${risk}" data-org="${key}"><button class="cat-head"><span class="cat-ic">${icon(key === 'dups' ? 'copy' : key === 'empty' ? 'folder' : 'files')}</span>
      <span class="cat-title"><b>${title}</b><small>${num(items.length)} shown</small></span><span></span><span></span>${icon('chevron', 'chev')}</button>
      <div class="cat-body"><div class="cat-inner"><div class="pad">${note ? `<div class="cat-text">${note}</div>` : ''}<div class="items">${items.map((it, ii) => `
        <div class="item" data-path="${esc(it.path)}" style="--i:${Math.min(ii, 16)}"><div class="item-name"><b>${esc(basename(it.path))}</b><small>${esc(it.sub || dirname(it.path))}</small></div>
        <div class="item-size"></div><button class="row-act" data-act="reveal" title="Show in Explorer">${icon('explorer')}</button></div>`).join('')}</div></div></div></div></div>` : '';

  $('#orgBody').innerHTML = `
    <div class="card health" style="--c:var(--${level[0]})">
      <div class="gauge"><svg viewBox="0 0 150 88"><path class="g-bg" d="M12 80 A63 63 0 0 1 138 80" pathLength="100"/>
        <path class="g-fg" d="M12 80 A63 63 0 0 1 138 80" pathLength="100"/></svg>
        <div class="gauge-val"><b id="scoreVal">0</b><small>${level[1]}</small></div></div>
      <div class="health-facts">
        <div><small>Total size</small><b>${fmtSize(p.size)}</b></div><div><small>Files</small><b>${num(p.file_count)}</b></div>
        <div><small>Subfolders</small><b>${num(p.subfolder_count)}</b></div><div><small>Loose files</small><b>${num(p.direct_count)}</b></div>
      </div></div>
    ${p.by_type.length ? `<div class="card section-card" style="--d:80ms"><h4>${icon('grid')}What's inside (on disk)</h4>
      <div class="stack">${p.by_type.map(t => `<i data-w="${t[1] / typeTotal * 100}%" style="background:${TYPE_COLORS[t[0]] || '#94a3b8'}" title="${esc(t[0])} ${fmtSize(t[1])}"></i>`).join('')}</div>
      <div class="stack-legend">${p.by_type.map(t => `<span><i style="background:${TYPE_COLORS[t[0]] || '#94a3b8'}"></i>${esc(t[0])} ${fmtSize(t[1])}</span>`).join('')}</div></div>` : ''}
    <div class="card section-card" style="--d:160ms"><h4>${icon('alert')}Health check</h4><ul class="issues">
      ${p.issues.length ? p.issues.map((t, i) => `<li style="--i:${i}">${icon('alert')}<span>${esc(t)}</span></li>`).join('')
        : `<li class="ok">${icon('check')}<span>No obvious problems found.</span></li>`}</ul></div>
    <div id="clsSlot"></div>
    <div id="vdSlotOrg"></div>
    ${dupCardHtml(p.duplicates)}
    ${listCard('copies', 'Copies & versions', 'Review', p.copies.sample.map(path => ({ path })),
      `<b>What is this?</b> Files or folders whose <b>names</b> suggest an extra version — "copy", "(1)", "final", "New folder" and similar.
       They are <b>not necessarily the same file</b>: one may be a newer edit. Open them, keep the one you need and delete the others yourself.
       <div style="margin-top:8px"><button class="btn sm" data-org-act="vd">${icon('copy')}Find exact duplicates among them</button></div>`)}
    ${listCard('empty', 'Empty folders', 'Safe', p.empty.sample.map(path => ({ path })),
      '<b>What is this?</b> Folders with nothing inside (no files at any level). They take no space but add clutter — safe to delete.')}
    <div id="planBox" style="display:flex;flex-direction:column;gap:10px"></div>`;

  renderVd();
  renderCls();
  nextFrame().then(() => {
    const fg = $('#orgBody .g-fg');
    if (fg) fg.style.strokeDashoffset = 100 - score;
    $$('#orgBody .stack i').forEach(i => { i.style.width = i.dataset.w; });
    countUp($('#scoreVal'), score, num, 1300);
  });
}

async function renderPlan(plan) {
  const groups = new Map();
  for (const s of plan.structure) if (s && s.folder) groups.set(String(s.folder), { purpose: s.purpose || '', moves: [] });
  for (const m of plan.moves) {
    if (!m) continue;
    const to = String(m.to || 'Other');
    if (!groups.has(to)) groups.set(to, { purpose: '', moves: [] });
    groups.get(to).moves.push(m);
  }
  const box = $('#planBox');
  const byRules = String(plan.model || '').startsWith('Rules');
  box.innerHTML = `
    <div class="ai-answer"><div class="ai-head">${icon(byRules ? 'grid' : 'sparkle')}${byRules ? 'Suggested plan · based on file types (no AI)'
      : `AI organisation plan · ${esc(plan.model)}`}</div><p class="ai-text" id="planSummary"></p></div>
    <div class="plan-tree">${[...groups].map(([folder, g], i) => `
      <div class="pnode" style="--i:${i}"><div class="pnode-head"><span class="ic-wrap">${icon('folder')}</span>
        <div><b>${esc(folder)}</b><small>${esc(g.purpose)}</small></div></div>
        ${g.moves.length ? `<div class="pmoves">${g.moves.slice(0, 8).map((m, j) =>
          `<div class="pmove" style="--i:${i};--j:${j}"><span>←</span><div><b>${esc(m.what)}</b>${m.why ? ` <em>— ${esc(m.why)}</em>` : ''}</div></div>`).join('')}
          ${g.moves.length > 8 ? `<div class="pmove muted" style="--i:${i};--j:8">+ ${g.moves.length - 8} more</div>` : ''}</div>` : ''}
      </div>`).join('')}</div>
    ${plan.issues.length || plan.tips.length ? `<div class="card section-card"><h4>${icon('sparkle')}Also worth doing</h4><ul class="issues">
      ${plan.issues.filter(x => x && x.problem).map((x, i) => `<li class="fix" style="--i:${i}">${icon('arrow')}<span>${esc(x.problem)} <em>→ ${esc(x.fix || '')}</em></span></li>`).join('')}
      ${plan.tips.map((t, i) => `<li class="fix" style="--i:${i + plan.issues.length}">${icon('check')}<span>${esc(t)}</span></li>`).join('')}</ul></div>` : ''}
    ${plan.moves.length ? `<div class="card org-apply">
      <span class="org-apply-ic">${icon('wand')}</span>
      <div><b>Let the app do it</b><small>See exactly which files move where, untick anything you want to keep, then apply. You can undo it afterwards.</small></div>
      <button class="btn clean" id="previewOrgBtn">${icon('wand')}<span>Organise for me</span></button></div>` : ''}
    <p class="disclaimer">${byRules ? 'Suggestions' : 'AI suggestions'} — nothing is moved until you confirm.</p>`;
  const btn = $('#previewOrgBtn');
  if (btn) btn.onclick = () => previewOrganise(btn);
  await typeText($('#planSummary'), plan.summary || 'Here is a suggested structure.');
}

/* ---------- duplicates found by the health check ---------- */
function dupCardHtml(d) {
  if (!d || !d.count) return '';
  const extra = d.sample.reduce((n, g) => n + (g.paths.length - 1), 0);
  return `<div class="cat risk-Review dup-card" data-org="dups"><button class="cat-head"><span class="cat-ic">${icon('copy')}</span>
      <span class="cat-title"><b>Duplicates · ${fmtSize(d.waste)} wasted</b><small>${num(d.count)} file${d.count === 1 ? '' : 's'} stored more than once in this folder</small></span>
      <span></span><span></span>${icon('chevron', 'chev')}</button>
    <div class="cat-body"><div class="cat-inner"><div class="pad">
      <div class="cat-text"><b>What is this?</b> The same file name and size found in more than one place inside this folder (subfolders included).
        Before anything is deleted, the app compares the actual contents (SHA-256) and removes <b>only byte-for-byte identical</b> copies.
        <b>One copy is always kept</b> — the one nearest the top of the folder — and removed copies go to the Recycle Bin, so you can restore them.
        Online-only (OneDrive/iCloud) copies are not compared, because that would download them.</div>
      <div class="bulk-row"><small>${d.sample.length < d.count ? `Showing ${d.sample.length} of ${num(d.count)} sets` : `${d.sample.length} set${d.sample.length === 1 ? '' : 's'}`}</small>
        <button class="btn clean sm" data-dup="all">${icon('trash')}Remove ${extra} extra cop${extra === 1 ? 'y' : 'ies'}</button></div>
      ${d.sample.map((g, gi) => `<div class="vd-group" style="--i:${Math.min(gi, 10)}">
        <div class="vd-keep">${icon('copy')}<span><b>${esc(g.name)}</b></span><small>${fmtSize(g.size)} each · ${g.paths.length} copies</small>
          <button class="btn sm" data-dup="${gi}" style="margin-left:auto;flex:none">Remove extras</button></div>
        ${g.paths.map(path => `<div class="item" data-path="${esc(path)}"><div class="item-name"><b>${path === g.keep ? 'Kept' : 'Extra copy'}</b><small title="${esc(path)}">${esc(dirname(path))}</small></div>
          <div class="item-size">${path === g.keep ? '<span class="mtag name">keep</span>' : '<span class="mtag unrecognised">remove</span>'}</div>
          <button class="row-act" data-act="reveal" title="Show in Explorer">${icon('explorer')}</button></div>`).join('')}</div>`).join('')}
    </div></div></div></div>`;
}

async function removeDuplicates(groups, btn) {
  const extra = groups.reduce((n, g) => n + g.paths.length - 1, 0);
  const size = groups.reduce((n, g) => n + g.size * (g.paths.length - 1), 0);
  const ok = await confirmDialog({
    title: `Remove ${extra} extra cop${extra === 1 ? 'y' : 'ies'}?`, icon: 'trash', okLabel: `Check & remove · up to ${fmtSize(size)}`,
    body: `<ul>${groups.slice(0, 8).map(g => `<li><span>${esc(g.name)} · ${g.paths.length - 1} extra</span><span>${fmtSize(g.size * (g.paths.length - 1))}</span></li>`).join('')}
      ${groups.length > 8 ? `<li><span>… and ${groups.length - 8} more files</span><span></span></li>` : ''}</ul>
      <p>Each copy's contents are compared first; only identical copies are removed and one copy of each file is kept.
      Removed copies go to the Recycle Bin.</p>`,
  });
  if (!ok) return;
  busy(btn, true);
  try {
    const r = await Bridge.call('remove_duplicates', groups.map(g => g.paths));
    toast(r.removed ? 'ok' : 'info', `Removed ${r.removed} cop${r.removed === 1 ? 'y' : 'ies'} · freed ${fmtSize(r.freed)}` +
      (r.notes.length ? ` · ${r.notes.length} kept: ${r.notes[0]}` : ''), 8000);
    await refreshFolder();
    await analyse();
  } catch (e) { fail(e); busy(btn, false); }
}

/* ---------- carrying out the plan ---------- */
function moveGroupHtml(g, gi) {
  const size = g.items.reduce((n, i) => n + i.size, 0);
  return `<div class="mv-group" data-g="${gi}">
    <label class="mv-head"><input type="checkbox" class="mv-all" checked>
      <span class="mv-ic">${icon('folder')}</span>
      <span class="mv-title"><b>${esc(g.target)}</b><small>${g.exists ? 'existing folder' : 'new folder'} · ${g.items.length} item${g.items.length === 1 ? '' : 's'} · ${fmtSize(size)}</small></span>
      <button type="button" class="mv-toggle" title="Show items">${icon('chevron', 'chev')}</button></label>
    <div class="mv-items">${g.items.map(it => `<label class="mv-item"><input type="checkbox" class="mv-one" data-name="${esc(it.name)}" checked>
      ${icon(it.kind === 'dir' ? 'folder' : 'file')}<span>${esc(it.name)}</span><em>${fmtSize(it.size)}</em></label>`).join('')}</div></div>`;
}

async function previewOrganise(btn) {
  const path = S.folder && S.folder.path;
  if (!path) return;
  busy(btn, true);
  let p;
  try { p = await Bridge.call('preview_organise', path); } catch (e) { busy(btn, false); return fail(e); }
  busy(btn, false);
  const total = p.groups.reduce((n, g) => n + g.items.length, 0);
  if (!total) {
    return toast('info', 'None of the suggestions matched files that can be moved safely' +
      (p.unmatched.length ? ` (${p.unmatched.length} suggestion(s) were too vague)` : ''), 6000);
  }
  const body = `<p>${total} item${total === 1 ? '' : 's'} will move into ${p.groups.length} folder${p.groups.length === 1 ? '' : 's'} inside
      <b>${esc(basename(path))}</b>. Untick anything you want to leave where it is.</p>
    <div class="mv-list">${p.groups.map(moveGroupHtml).join('')}</div>
    ${p.unmatched.length ? `<p class="mv-note">${icon('info')}Couldn't match ${p.unmatched.length} suggestion${p.unmatched.length === 1 ? '' : 's'} to files: ${p.unmatched.slice(0, 4).map(esc).join(' · ')}</p>` : ''}
    ${p.skipped.length ? `<p class="mv-note">${icon('lock')}Left alone for safety: ${p.skipped.slice(0, 5).map(s => `${esc(s.name)} (${esc(s.reason)})`).join(' · ')}</p>` : ''}`;

  const modalBody = $('#modalBody');
  $('.modal-card').classList.add('wide');
  const sync = () => {
    $$('.mv-group', modalBody).forEach(g => {
      const ones = $$('.mv-one', g), on = ones.filter(c => c.checked).length;
      const all = $('.mv-all', g);
      all.checked = on === ones.length;
      all.indeterminate = on > 0 && on < ones.length;
    });
    const n = $$('.mv-one:checked', modalBody).length;
    $('#modalOk').textContent = `Move ${n} item${n === 1 ? '' : 's'}`;
    $('#modalOk').disabled = !n;
  };
  const onChange = e => {
    if (e.target.classList.contains('mv-all')) {
      $$('.mv-one', e.target.closest('.mv-group')).forEach(c => { c.checked = e.target.checked; });
    }
    sync();
  };
  const onClick = e => {
    const t = e.target.closest('.mv-toggle');
    if (t) { e.preventDefault(); t.closest('.mv-group').classList.toggle('open'); }
  };
  const pending = confirmDialog({ title: 'Organise these files?', icon: 'wand', okLabel: `Move ${total} items`, body });
  modalBody.addEventListener('change', onChange);
  modalBody.addEventListener('click', onClick);
  const ok = await pending;
  modalBody.removeEventListener('change', onChange);
  modalBody.removeEventListener('click', onClick);
  const names = $$('.mv-one:checked', modalBody).map(c => c.dataset.name);
  $('.modal-card').classList.remove('wide');
  $('#modalOk').disabled = false;
  if (!ok || !names.length) return;
  applyOrganise(path, names, btn);
}

async function applyOrganise(path, names, btn) {
  btn.disabled = true;
  $('span', btn).textContent = 'Moving…';
  try {
    const r = await Bridge.call('apply_organise', path, names);
    const folderName = basename(path) || path;
    const msg = `Moved ${num(r.moved)} file${r.moved === 1 ? '' : 's'} into ${r.achieved.length} folder${r.achieved.length === 1 ? '' : 's'}`;
    await refreshFolder();
    await analyse();
    $('#planBox').innerHTML = `<div class="card org-done"><span class="org-apply-ic done">${icon('checkmark')}</span>
      <div><b>${esc(msg)}</b><small>${r.left.length ? `${r.left.length} file${r.left.length === 1 ? '' : 's'} still loose in ${esc(folderName)} — they need sorting by hand` : 'Nothing left loose — the folder is tidy'}</small></div>
      <div style="display:flex;gap:6px">${r.left.length ? `<button class="btn" id="leftOrgBtn">${icon('info')}<span>What's left</span></button>` : ''}
      ${r.undo_id ? `<button class="btn" id="undoOrgBtn">${icon('back')}<span>Undo</span></button>` : ''}</div></div>`;
    const u = $('#undoOrgBtn');
    if (u) u.onclick = () => undoOrganise(r.undo_id, u);
    const l = $('#leftOrgBtn');
    if (l) l.onclick = () => organiseReport(r, path);
    organiseReport(r, path);
  } catch (e) {
    fail(e);
    btn.disabled = false;
    $('span', btn).textContent = 'Organise for me';
  }
}

/* "Organising done": what was achieved, what is left and why - the user sorts the rest by hand. */
async function organiseReport(r, path) {
  const folderName = basename(path) || path;
  const s = n => (n === 1 ? '' : 's');
  const byReason = {};
  for (const f of r.left) (byReason[f.reason] = byReason[f.reason] || []).push(f);
  const body = `
    <div class="rep-top"><span class="org-apply-ic done">${icon('checkmark')}</span>
      <div><b>Moved ${num(r.moved)} file${s(r.moved)} into ${r.achieved.length} folder${s(r.achieved.length)}</b>
      <small>${num(r.before)} file${s(r.before)} were loose in ${esc(folderName)} · ${num(r.left.length)} still ${r.left.length === 1 ? 'is' : 'are'}</small></div></div>
    ${r.achieved.length ? `<ul class="rep-folders">${r.achieved.map(a => `<li><span>${icon('folder')}${esc(a.folder)}</span><span>${num(a.count)} file${s(a.count)}</span></li>`).join('')}</ul>` : ''}
    ${r.left.length ? `
      <h4 class="rep-h">${num(r.left.length)} file${s(r.left.length)} left in ${esc(folderName)}</h4>
      <p class="rep-ask">Please organise these by hand — open the folder and move them where they belong. Click a file to show it in Explorer.</p>
      <div class="rep-left">${Object.entries(byReason).map(([reason, files]) => `
        <div class="rep-reason"><span class="mtag unrecognised">${files.length}</span>${esc(reason.charAt(0).toUpperCase() + reason.slice(1))}</div>
        ${files.map(f => `<div class="rep-row" data-path="${esc(f.path)}"><span>${icon('file')}</span>
          <div><b title="${esc(f.name)}">${esc(f.name)}</b>${f.warn ? `<small class="rep-warn">⚠ ${esc(f.warn)}</small>` : ''}</div>
          <em>${fmtSize(f.size)}</em></div>`).join('')}`).join('')}</div>`
      : '<p class="rep-ask">Nothing is left loose — the folder is tidy.</p>'}`;
  const extra = [];
  if (r.left.length) extra.push({ label: 'Open folder in Explorer', icon: 'explorer', fn: () => openItem(path) });
  if (r.undo_id) extra.push({ label: 'Undo', icon: 'back', value: 'undo' });
  const pending = confirmDialog({ title: 'Organising done', icon: 'checkmark', okLabel: 'Done', cancelLabel: null, extra, body });
  $('.modal-card').classList.add('wide');
  const onRow = ev => { const row = ev.target.closest('.rep-row'); if (row) reveal(row.dataset.path); };
  $('#modalBody').addEventListener('click', onRow);
  const v = await pending;
  $('#modalBody').removeEventListener('click', onRow);
  $('.modal-card').classList.remove('wide');
  if (v === 'undo') undoOrganise(r.undo_id, $('#undoOrgBtn'));
}

async function undoOrganise(id, btn) {
  if (btn) busy(btn, true);
  try {
    const r = await Bridge.call('undo_organise', id);
    toast(r.failed.length ? 'info' : 'ok', `Put back ${num(r.restored)} item${r.restored === 1 ? '' : 's'}` +
      (r.failed.length ? ` · ${r.failed.length} couldn't be restored` : ''), 6000);
    await refreshFolder();
    if (S.mode === 'organise') await analyse();
  } catch (e) { fail(e); if (btn) busy(btn, false); }
}

/* ---------- duplicate versions (both panels) ---------- */
function vdHtml() {
  const v = S.vd;
  if (!v) return '';
  const where = esc(basename(v.folder) || v.folder);
  if (v.running) {
    const pct = v.total ? (v.done / v.total) * 100 : 0;
    return `<div class="cat risk-AI vd-card"><div class="scan-card-run">${scanAnim()}<div class="grow">
      <b>Checking duplicate versions…</b><small>${v.total ? `Comparing contents · ${v.done + 1} of ${v.total} · ${esc(v.name || '')}` : `Looking for name(1), name(2)… in ${where}`}</small>
      <div class="ai-progress ${v.total ? '' : 'indet'}"><i style="width:${pct}%"></i></div></div></div></div>`;
  }
  const notes = [
    v.different ? `${v.different} name famil${v.different === 1 ? 'y has' : 'ies have'} different content — real versions, left alone.` : '',
    v.skipped_cloud ? `${v.skipped_cloud} online-only file${v.skipped_cloud === 1 ? ' was' : 's were'} skipped (checking would download ${v.skipped_cloud === 1 ? 'it' : 'them'}).` : '',
  ].filter(Boolean).join(' ');
  if (!v.groups.length) {
    return `<div class="cat risk-Safe vd-card"><div class="cat-head"><span class="cat-ic">${icon('check')}</span>
      <span class="cat-title"><b>No duplicate versions in ${where}</b><small>${num(v.hashed)} file${v.hashed === 1 ? '' : 's'} compared by content. ${esc(notes)}</small></span>
      <span></span><button class="btn sm" data-vd="rerun">${icon('refresh')}Re-check</button><span></span></div></div>`;
  }
  return `<div class="cat risk-Review vd-card open">
    <button class="cat-head"><span class="cat-ic">${icon('copy')}</span>
      <span class="cat-title"><b>Duplicate versions in ${where}</b><small>${v.copies} identical cop${v.copies === 1 ? 'y' : 'ies'} in ${v.groups.length} set${v.groups.length === 1 ? '' : 's'} · checked by SHA-256</small></span>
      <span class="cat-size">${fmtSize(v.waste)}</span><span class="pill">Hash</span>${icon('chevron', 'chev')}</button>
    <div class="cat-body"><div class="cat-inner"><div class="pad">
      <div class="bulk-row"><small>Same name family and byte-for-byte identical. One file of each set stays.</small>
        <button class="btn clean sm" data-vd="all">${icon('trash')}Remove ${v.copies} · ${fmtSize(v.waste)}</button></div>
      ${v.groups.slice(0, 60).map((g, gi) => `<div class="vd-group" style="--i:${Math.min(gi, 10)}">
        <div class="vd-keep">${icon('checkmark')}<span>Keep <b>${esc(g.keep.name)}</b></span><small>${fmtSize(g.size)} · ${esc(g.dir)}</small></div>
        ${g.dupes.map(d => `<div class="item has-act vd-dupe" data-path="${esc(d.path)}">
          <div class="item-name"><b>${esc(d.name)}</b><small class="vd-hash">identical · ${g.hash}…</small></div>
          <div class="item-size">${fmtSize(d.size)}</div>
          <button class="item-act recycle" data-vd="one" title="Move to Recycle Bin">${icon('trash')}</button>
          <button class="row-act" data-act="reveal" title="Show in Explorer">${icon('explorer')}</button></div>`).join('')}</div>`).join('')}
      ${v.groups.length > 60 ? `<div class="more-row">+ ${v.groups.length - 60} more sets (all included in Remove)</div>` : ''}
      ${notes ? `<p class="cat-text">${esc(notes)}</p>` : ''}
    </div></div></div></div>`;
}

function renderVd() {
  const html = vdHtml();
  ['#vdSlot', '#vdSlotOrg'].forEach(sel => { const el = $(sel); if (el) el.innerHTML = html; });
}

async function runVd() {
  if (needScan()) return;
  if (S.vd && S.vd.running) return;
  const path = S.folder.path;
  S.vd = { running: true, folder: path, done: 0, total: 0 };
  renderVd();
  $$('.vd-btn').forEach(b => tileBusy(b, true, 'Checking file contents…'));
  try {
    S.vd = await Bridge.call('find_version_dupes', path);
    renderVd();
    toast(S.vd.copies ? 'info' : 'ok', S.vd.copies
      ? `Found ${S.vd.copies} identical cop${S.vd.copies === 1 ? 'y' : 'ies'} (${fmtSize(S.vd.waste)})`
      : 'No duplicate versions found');
  } catch (e) { S.vd = null; renderVd(); fail(e); }
  $$('.vd-btn').forEach(b => tileBusy(b, false));
}
$$('.vd-btn').forEach(b => b.addEventListener('click', runVd));

async function removeVd(paths, btn) {
  const all = S.vd.groups.flatMap(g => g.dupes.map(d => ({ ...d, size: g.size })));
  const picked = all.filter(d => paths.includes(d.path));
  const size = picked.reduce((n, d) => n + d.size, 0);
  const n = picked.length;
  const ok = await confirmDialog({
    title: `Move ${n} duplicate cop${n === 1 ? 'y' : 'ies'} to the Recycle Bin?`, icon: 'trash',
    okLabel: `Remove ${n} · ${fmtSize(size)}`,
    body: `<ul>${picked.slice(0, 8).map(d => `<li><span>${esc(d.name)}</span><span>${fmtSize(d.size)}</span></li>`).join('')}
      ${n > 8 ? `<li><span>… and ${n - 8} more</span><span></span></li>` : ''}</ul>
      <p>Each one has exactly the same content (SHA-256) as a file that stays. You can restore them from the Recycle Bin.</p>`,
  });
  if (!ok) return;
  if (btn) busy(btn, true);
  try {
    const r = await Bridge.call('remove_version_dupes', paths);
    S.vd = r.result;
    renderVd();
    toast(r.failed.length ? 'info' : 'ok', `Removed ${r.removed} cop${r.removed === 1 ? 'y' : 'ies'} · freed ${fmtSize(r.freed)}` +
      (r.failed.length ? ` · ${r.failed.length} skipped: ${r.failed[0]}` : ''), 6000);
    refreshFolder();
  } catch (e) { fail(e); if (btn) busy(btn, false); }
}

function onVdClick(e) {
  const card = e.target.closest('.vd-card');
  if (!card) return;
  const row = e.target.closest('.vd-dupe');
  if (e.target.closest('[data-vd="rerun"]')) return runVd();
  if (e.target.closest('[data-vd="all"]')) return removeVd(S.vd.groups.flatMap(g => g.dupes.map(d => d.path)), e.target.closest('button'));
  if (row && e.target.closest('[data-vd="one"]')) return removeVd([row.dataset.path]);
  if (row && e.target.closest('[data-act="reveal"]')) return reveal(row.dataset.path);
  if (e.target.closest('.cat-head') && card.querySelector('.cat-body')) card.classList.toggle('open');
}
catsBox.addEventListener('click', onVdClick);

/* ---------- smart document classification (only when the user asks) ---------- */
const METHOD_LABEL = { name: 'from name', 'ai-name': 'AI · name only', read: 'AI · read inside', 'no-text': 'no text inside',
  unreadable: "can't read", unrecognised: 'check by hand' };

function clsRows(files) {
  return files.map((f, i) => `<div class="item" data-path="${esc(f.path)}" style="--i:${Math.min(i, 12)}">
    <div class="item-name"><b title="${esc(f.name)}">${esc(f.name)}</b><small>${esc(f.summary || ' ')}</small></div>
    <div class="item-size"><span class="mtag ${f.method}">${METHOD_LABEL[f.method] || f.method}</span></div>
    <button class="row-act" data-act="reveal" title="Show in Explorer">${icon('explorer')}</button></div>`).join('');
}

function clsHtml() {
  const c = S.cls;
  if (!c || (S.folder && c.folder && c.folder !== S.folder.path)) return '';
  if (c.running) {
    const pct = c.total ? (c.done / c.total) * 100 : 0;
    return `<div class="cat risk-AI cls-card"><div class="scan-card-run">${scanAnim()}<div class="grow">
      <b>Deep analysing documents…</b><small>${esc(c.stage)}${c.total ? ` · batch ${c.done + 1} of ${c.total}` : ''}</small>
      <div class="ai-progress ${c.total ? '' : 'indet'}"><i style="width:${pct}%"></i></div></div></div></div>`;
  }
  const total = c.groups.reduce((n, g) => n + g.files.length, 0);
  const notes = [c.cloud_skipped ? `${c.cloud_skipped} online-only skipped (not downloaded)` : '',
    c.ignored ? `${c.ignored} non-document files ignored` : ''].filter(Boolean).join(' · ');
  return `<div class="cat risk-AI cls-card open">
    <button class="cat-head"><span class="cat-ic">${icon('files')}</span>
      <span class="cat-title"><b>Documents in ${esc(c.name)}</b><small>${total} classified${c.unrecognised.length ? ` · ${c.unrecognised.length} to check by hand` : ''}${usageText(c.usage)}</small></span>
      <span></span><span class="pill">Smart</span>${icon('chevron', 'chev')}</button>
    <div class="cat-body"><div class="cat-inner"><div class="pad">
      ${c.groups.map((g, i) => `<div class="cls-group" style="--i:${i}"><div class="vd-keep">${icon('folder')}<span><b>${esc(g.label)}</b></span>
        <small>→ ${esc(g.folder)} · ${g.files.length}</small></div><div class="items">${clsRows(g.files)}</div></div>`).join('')}
      ${c.unrecognised.length ? `<div class="cls-group"><div class="vd-keep">${icon('alert')}<span><b>Check by hand</b></span><small>left where they are</small></div>
        <div class="items">${clsRows(c.unrecognised)}</div></div>` : ''}
      ${notes ? `<p class="cat-text">${esc(notes)}</p>` : ''}
      ${c.merged ? '<p class="cat-text">These categories are part of the plan below — use its <b>Organise for me</b>.</p>' : ''}
      ${total && !c.merged ? `<div class="card org-apply" style="animation-delay:0s"><span class="org-apply-ic">${icon('wand')}</span>
        <div><b>Move them into category folders</b><small>Preview first, untick anything to keep where it is, undo any time.</small></div>
        <button class="btn clean" id="clsOrgBtn">${icon('wand')}<span>Organise for me</span></button></div>` : ''}
    </div></div></div></div>`;
}

function renderCls() {
  const el = $('#clsSlot');
  if (!el) return;
  el.innerHTML = clsHtml();
  const b = $('#clsOrgBtn');
  if (b) b.onclick = () => previewOrganise(b);
}

async function classifyDocs() {
  if (needScan()) return;
  if (S.mode !== 'organise') setMode('organise');
  const path = S.folder.path, btn = $('#clsBtn');
  tileBusy(btn, true, 'Looking at the documents in this folder…');
  let p;
  try { p = await Bridge.call('classify_preview', path); } catch (e) { tileBusy(btn, false); return fail(e); }
  tileBusy(btn, false);
  if (!p.docs) {
    return toast('info', `No document files stored on this PC directly in ${p.name}` +
      (p.cloud_skipped ? ` (${p.cloud_skipped} online-only skipped)` : ''), 6000);
  }
  const sends = p.ai && (p.names.length || p.reads.length);
  const cloud = sends && !p.local;
  const s = n => (n === 1 ? '' : 's');
  const est = p.estimate;
  const cost = est && est.cost != null ? ` · ≈ $${est.cost < 0.01 ? est.cost.toFixed(4) : est.cost.toFixed(2)}` : '';
  const privacy = cloud ? `<div class="warn-note" style="margin-top:12px"><b>Privacy:</b> this uses ${esc(p.label)}, a cloud service. Depending on your choice below, these would leave your PC:
      ${p.names.length ? `<br>• ${p.names.length} file name${s(p.names.length)}` : ''}
      ${p.reads.length ? `<br>• text from inside ${p.reads.length} file${s(p.reads.length)}: ${p.reads.slice(0, 6).map(esc).join(', ')}${p.reads.length > 6 ? `, +${p.reads.length - 6} more` : ''}` : ''}
      <br>Bank statements, IDs and other personal documents are safer with a local model.</div>
    <div class="cls-modes">${deepModes('clsMode', p, p.label)}</div>` : '';
  const step = (n, title, text, count, off) => `<div class="what-step${off ? ' off' : ''}"><span class="n">${n}</span>
    <div><b>${title}</b><small>${text}</small></div><em>${count == null ? '' : num(count)}</em></div>`;
  const skipped = [p.cached ? `${p.cached} already done earlier` : '', p.no_text.length ? `${p.no_text.length} scanned (no text)` : '',
    p.unreadable.length ? `${p.unreadable.length} can't be read (old .doc/.xls/.ppt)` : '',
    p.cloud_skipped ? `${p.cloud_skipped} online-only (not downloaded)` : '', p.ignored ? `${p.ignored} non-documents ignored` : '']
    .filter(Boolean).join(' · ');
  const estimate = !p.ai ? `<div class="est-card"><b>AI is off</b> — only the name rules run. Files they can't place stay "check by hand".</div>`
    : !sends ? ''
    : p.local ? `<div class="est-card"><b>Runs on this PC with ${esc(p.model)}</b> — free and private, nothing leaves your PC.
        <div class="est-rows"><span>≈ <b>${num(est.input + est.output)}</b> tokens</span><span><b>${est.requests}</b> request${s(est.requests)}</span><span>usually under a minute or two</span></div></div>`
    : `<div class="est-card"><div class="est-total"><b>≈ ${num(est.input + est.output)}</b><span>tokens if names and excerpts are sent</span></div>
        <div class="est-rows"><span>Service <b>${esc(p.label)}</b></span><span>Model <b>${esc(p.model)}</b></span><span><b>${est.requests}</b> request${s(est.requests)}</span>
        <span>Input ${est.exact ? '' : '≈ '}<b>${num(est.input)}</b></span><span>Output ≈ <b>${num(est.output)}</b></span>
        <span>Cost <b>${est.cost != null ? cost.replace(' · ', '') : 'add prices in AI settings'}</b></span></div></div>`;
  const ok = await confirmDialog({
    title: `Deep analyse & classify ${p.docs} document${s(p.docs)}?`, icon: 'files', okLabel: 'Start analysis',
    body: `<p>In <b>${esc(p.name)}</b> — only PDF, Word, Excel, PowerPoint and text files stored on this PC. Here's what will happen:</p>
      <div class="what-steps">
        ${step(1, 'Recognise from the file name', 'Bills, KYC, bank & tax… sorted from their names. These files are not opened.', p.by_name)}
        ${step(2, p.ai ? 'Ask AI about the names' : 'Names the rules don\'t know', p.ai ? 'Only the file names are sent — never the contents.' : 'AI is off, so these stay "check by hand".', p.names.length, !p.names.length)}
        ${step(3, p.ai ? 'Read a short excerpt' : 'Names that say nothing', p.ai ? 'Only for files like "download.pdf" or "Doc1.docx": the first ~1,500 characters are read to understand them.' : 'AI is off, so these stay "check by hand".', p.reads.length, !p.reads.length)}
        ${step(4, 'You review the results', 'Nothing is moved or changed. "Organise for me" moves files only if you choose — with preview and undo.', null)}
      </div>
      ${skipped ? `<p class="what-skip">Skipped: ${skipped}.</p>` : ''}
      ${estimate}
      ${privacy}`,
  });
  const choice = $('input[name=clsMode]:checked');
  const mode = cloud ? (choice ? choice.value : 'names_only') : 'full';
  if (!ok) return;
  runClassify(path, mode, sends);
}

async function runClassify(path, mode, usesAi) {
  const btn = $('#clsBtn');
  tileBusy(btn, true, 'Deep analysing the documents…');
  if (usesAi) aiBusy(1);
  S.cls = { running: true, stage: 'Starting…', done: 0, total: 0, folder: path };
  renderCls();
  const slot = $('#clsSlot');
  if (slot) scrollWithin($('#orgBody'), slot);
  try {
    const r = await Bridge.call('classify_run', path, mode);
    S.cls = r;
    renderCls();
    const n = r.groups.reduce((t, g) => t + g.files.length, 0);
    toast('ok', `Classified ${n} document${n === 1 ? '' : 's'} into ${r.groups.length} categor${r.groups.length === 1 ? 'y' : 'ies'}${usageText(r.usage)}`, 6000);
  } catch (e) { S.cls = null; renderCls(); fail(e); }
  if (usesAi) aiBusy(-1);
  tileBusy(btn, false);
}
$('#clsBtn').addEventListener('click', classifyDocs);

const orgBody = $('#orgBody');
orgBody.addEventListener('click', onVdClick);
orgBody.addEventListener('click', e => {
  if (e.target.closest('.vd-card')) return;
  const dup = e.target.closest('[data-dup]');
  if (dup && S.profile) {
    const sets = S.profile.duplicates.sample;
    return removeDuplicates(dup.dataset.dup === 'all' ? sets : [sets[+dup.dataset.dup]], dup);
  }
  if (e.target.closest('[data-org-act="vd"]')) return runVd();
  const head = e.target.closest('.cat-head');
  if (head) return head.parentElement.classList.toggle('open');
  const item = e.target.closest('.item');
  if (item) reveal(item.dataset.path);
});

/* ================================================================ Home dashboard */
let homeTimer = 0;
function renderHome() {           // many events feed the dashboard; batch them
  clearTimeout(homeTimer);
  homeTimer = setTimeout(renderHomeNow, 80);
}

function hrows(rows, max) {
  return rows.map((r, i) => `<div class="hrow" style="--i:${i}"><span title="${esc(r.title || r.label)}">${esc(r.label)}</span><em>${esc(r.value)}</em>
    ${r.bar != null ? `<div class="track"><i style="width:${max ? Math.max(2, r.bar / max * 100) : 0}%"></i></div>` : ''}</div>`).join('');
}

function renderHomeNow() {
  updateNavBadges();
  if (!$('#view-home').classList.contains('active')) return;
  const h = new Date().getHours();
  $('#homeDate').textContent = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
  $('#homeHello').textContent = h < 5 ? 'Working late?' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
  const sys = S.drv.summary && S.drv.summary.system;
  $('#homeSys').textContent = sys
    ? `${sys.oem || sys.manufacturer} ${sys.model} · ${(sys.os || '').replace('Microsoft ', '')} (build ${sys.build})`
    : 'Reading your PC…';

  // drives
  const hd = $('#homeDrives');
  if (S.drives.length && hd.childElementCount !== S.drives.length) {
    hd.innerHTML = S.drives.map((d, i) => {
      const pct = d.used / d.total * 100;
      return `<div class="hdrive" style="--i:${i}"><div class="hdrive-wrap"><svg class="ring" viewBox="0 0 44 44"><circle class="ring-bg" cx="22" cy="22" r="18"/>
        <circle class="ring-fg ${pct > 90 ? 'hot' : ''}" cx="22" cy="22" r="18" pathLength="100" data-p="${pct}"/></svg>
        <div class="hdrive-val">${Math.round(pct)}%</div></div><b>${esc(d.letter)} ${esc(d.label)}</b><small>${fmtSize(d.free)} free</small></div>`;
    }).join('');
    nextFrame().then(() => $$('#homeDrives .ring-fg').forEach(c => { c.style.strokeDashoffset = 100 - c.dataset.p; }));
  }

  // clean-up card
  const sizes = Object.values(S.qc.sizes);
  const freeable = sizes.reduce((n, m) => n + m.size, 0);
  countUp($('#homeFree'), freeable, fmtSize, 900);
  countUp($('#hcCleanBig'), freeable, fmtSize, 900);
  $('#hcCleanSub').textContent = S.qc.measuring ? 'measuring…' : `can be freed from ${sizes.filter(m => m.size).length} always-safe places`;
  const top = [...sizes].sort((a, b) => b.size - a.size).slice(0, 4).filter(m => m.size);
  const name = id => (S.qc.targets.find(t => t.id === id) || {}).name || id;
  $('#hcCleanList').innerHTML = top.length ? hrows(top.map(m => ({ label: name(m.id), value: fmtSize(m.size), bar: m.size })), top[0].size)
    : '<i class="shimmer" style="height:18px"></i><i class="shimmer" style="height:18px;width:70%"></i>';
  if (S.cats.length) {
    const t = totals();
    $('#hcCleanExtra').innerHTML = `<span class="tag ok">Scan: ${fmtSize(t.Safe)} safe</span><span class="tag warn">${fmtSize(t.Review + t.Caution)} to review</span>`;
  } else {
    $('#hcCleanExtra').innerHTML = S.root ? `<span class="tag">Scanned ${esc(S.root.path)} · find candidates in Clean-up</span>`
      : '<span class="tag">Scan a drive for a full breakdown</span>';
  }

  // organiser card
  const picks = S.picks || [];
  const loose = picks.reduce((n, f) => n + f.loose, 0);
  if (S.picks) countUp($('#hcOrgBig'), loose, num, 900);
  $('#hcOrgSub').textContent = S.picks ? `loose files across ${picks.length} main folders` : 'looking…';
  const messy = [...picks].sort((a, b) => b.loose - a.loose);
  $('#hcOrgList').innerHTML = messy.length ? hrows(messy.slice(0, 4).map(f => ({ label: f.name, title: f.path, value: `${num(f.loose)} loose`, bar: f.loose })), messy[0].loose)
    : '<i class="shimmer" style="height:18px"></i><i class="shimmer" style="height:18px;width:70%"></i>';
  const worst = messy[0];
  const orgBtn = $('#hcOrgBtn');
  if (worst && worst.loose >= 10) { orgBtn.dataset.path = worst.path; orgBtn.textContent = `Organise ${worst.name}`; }
  else { delete orgBtn.dataset.path; orgBtn.textContent = 'Open Organiser'; }
  $('#hcOrgExtra').innerHTML = S.profile ? `<span class="tag ${S.profile.score >= 80 ? 'ok' : 'warn'}">Last check: ${esc(S.profile.name)} scored ${S.profile.score}/100</span>` : '';

  // drivers card
  const s = S.drv.summary;
  if (s) countUp($('#hcDrvBig'), s.count, num, 900);
  $('#hcDrvSub').textContent = s ? `vendor drivers · ${num(s.total)} devices in total` : 'reading drivers…';
  $('#hcDrvList').innerHTML = s ? hrows([
    { label: 'Windows Update', value: S.drv.checking ? 'checking…' : s.updates == null ? '—' : s.updates ? `${s.updates} update${s.updates === 1 ? '' : 's'}` : 'up to date' },
    { label: 'Older than 3 years', value: String(s.old) },
    { label: '1–3 years old', value: String(s.older) },
    { label: `BIOS ${s.system.bios || ''}`, value: s.system.bios_age != null ? `${s.system.bios_age} yrs old` : '—' },
  ]) : '<i class="shimmer" style="height:18px"></i><i class="shimmer" style="height:18px;width:70%"></i>';
  const tags = [];
  if (S.drv.checking) tags.push('<span class="tag">Asking Windows Update…</span>');
  else if (s && s.updates) tags.push(`<span class="tag warn">${s.updates} driver update${s.updates === 1 ? '' : 's'} ready</span>`);
  else if (s && s.updates === 0) tags.push('<span class="tag ok">Up to date with Windows Update</span>');
  if (s && s.blocked) tags.push(`<span class="tag bad">${s.blocked} firmware offer blocked (older than your BIOS)</span>`);
  $('#hcDrvExtra').innerHTML = tags.join('');

  // performance card
  const p = S.perf.summary, pl = S.live || (p && p.live);
  if (pl) countUp($('#hcPerfBig'), pl.mem_pct, n => `${Math.round(n)}%`, 900);
  $('#hcPerfSub').textContent = pl ? `memory in use · ${(pl.mem_used / 2 ** 30).toFixed(1)} of ${Math.round(pl.mem_total / 2 ** 30)} GB` : 'checking…';
  $('#hcPerfList').innerHTML = p ? hrows([
    { label: 'Processor', value: pl && pl.cpu != null ? `${Math.round(pl.cpu)}%` : '…' },
    { label: 'Background helpers safe to close', value: p.safe ? `${p.safe} · ${fmtSize(p.safe_mem)}` : 'none' },
    { label: 'Apps starting with Windows', value: String(p.startup_on) },
    { label: 'Running processes', value: num(p.processes) },
  ]) : '<i class="shimmer" style="height:18px"></i><i class="shimmer" style="height:18px;width:70%"></i>';
  const ptags = [];
  if (pl && pl.mem_pct >= 85) ptags.push('<span class="tag bad">Memory nearly full</span>');
  else if (p && p.safe) ptags.push(`<span class="tag warn">${fmtSize(p.safe_mem)} can be freed by closing helpers</span>`);
  else if (p) ptags.push('<span class="tag ok">Nothing unnecessary running</span>');
  $('#hcPerfExtra').innerHTML = ptags.join('');

  // footer chips
  $('#homeAi').innerHTML = `<span class="tag">${icon('sparkle')}${S.aiOn ? `AI assistant on · ${esc(S.aiLabel)} · ${esc(S.model || '')}` : 'AI assistant off — rules only'}</span>
    <span class="tag">${icon('lock')}${S.admin ? 'Running as administrator' : 'Standard user — asks before admin tasks'}</span>`;
}

/* ---------- system specs on the home screen ---------- */
const diskSize = n => (n >= 1e12 ? `${(n / 1e12).toFixed(n >= 1.5e12 ? 1 : 0)} TB` : `${Math.round(n / 1e9)} GB`);
function uptimeText(s) {
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
}

async function loadSpecs() {
  try { S.specs = await Bridge.call('sys_specs'); } catch (e) { $('#homeSpecs').innerHTML = ''; return; }
  renderSpecs();
}

function specTile(i, color, ic, label, value, meterId, emId, title) {
  return `<div class="spec" style="--i:${i};--sc:${color}" title="${esc(title || value)}"><span class="spec-ic">${icon(ic)}</span>
    <small><span>${label}</span><em id="${emId || ''}"></em></small><b id="${emId ? emId + 'B' : ''}">${esc(value)}</b>
    ${meterId ? `<div class="meter"><i id="${meterId}"></i></div>` : ''}</div>`;
}

function renderSpecs() {
  const s = S.specs, el = $('#homeSpecs');
  if (!s || !el) return;
  const gpu = s.gpus[0], gpu2 = s.gpus[1];
  const gpuText = gpu ? `${gpu.name.replace(/^NVIDIA GeForce |^AMD Radeon |\(R\)/g, '')}${gpu.vram ? ` · ${Math.round(gpu.vram / 2 ** 30)} GB` : ''}` : '—';
  const disks = s.disks.map(d => `${diskSize(d.size)} ${d.bus === 'NVMe' ? 'NVMe ' : ''}${d.media && d.media !== 'Unspecified' ? d.media : ''}`.trim()).join(' + ');
  el.innerHTML = [
    specTile(0, 'var(--accent)', 'chip', 'Processor', s.cpu.name, 'specCpuM', 'specCpu',
      `${s.cpu.name} · ${s.cpu.cores} cores / ${s.cpu.threads} threads · ${(s.cpu.mhz / 1000).toFixed(1)} GHz base`),
    specTile(1, 'var(--accent2)', 'memory', 'Memory', `${Math.round(s.ram.total / 2 ** 30)} GB · ${s.ram.speed} MT/s`, 'specMemM', 'specMem',
      `${Math.round(s.ram.total / 2 ** 30)} GB in ${s.ram.sticks} module(s) at ${s.ram.speed} MT/s`),
    specTile(2, '#76b900', 'monitor', 'Graphics', gpuText, 'specGpuM', 'specGpu',
      s.gpus.map(g => `${g.name}${g.vram ? ` (${Math.round(g.vram / 2 ** 30)} GB)` : ''}`).join(' + ') + (gpu ? ` · ${gpu.width}×${gpu.height}` : '')),
    specTile(3, 'var(--review)', 'drive', 'Storage', disks || '—', null, 'specDisk', s.disks.map(d => `${d.name} (${diskSize(d.size)} ${d.bus} ${d.media})`).join(' + ')),
    specTile(4, 'var(--accent)', 'windows', 'Windows', `${s.os.name.replace('Microsoft ', '')} ${s.os.version || ''}`, null, 'specOs', `${s.os.name} ${s.os.version} · build ${s.os.build}`),
    specTile(5, 'var(--safe)', 'battery', 'Power', '…', 'specBatM', 'specBat'),
  ].join('');
  $('#specGpu').textContent = gpu2 ? `+ ${gpu2.name.replace(/\(R\)/g, '').replace(/^Intel /, 'Intel ').split(' Graphics')[0]}` : (gpu ? `${gpu.width}×${gpu.height}` : '');
  $('#specDisk').textContent = `${s.disks.length} drive${s.disks.length === 1 ? '' : 's'}`;
  applyLive();
}

function applyLive() {
  const L = S.live;
  if (!L || !$('#specCpu')) return;
  const meter = (id, pct) => { const m = $('#' + id); if (m) { m.style.width = `${Math.max(2, pct)}%`; m.classList.toggle('hot', pct > 85); } };
  $('#specCpu').textContent = L.cpu == null ? '…' : `${Math.round(L.cpu)}%`;
  if (L.cpu != null) meter('specCpuM', L.cpu);
  $('#specMem').textContent = `${L.mem_pct}%`;
  if (S.specs) $('#specMemB').textContent = `${(L.mem_used / 2 ** 30).toFixed(1)} of ${Math.round(S.specs.ram.total / 2 ** 30)} GB · ${S.specs.ram.speed} MT/s`;
  meter('specMemM', L.mem_pct);
  $('#specOs').textContent = `up ${uptimeText(L.uptime)}`;
  // GPU usage like Task Manager: the main (biggest-memory) GPU on the meter, a second one beside it
  if (L.gpus && L.gpus.length && S.specs && S.specs.gpus.length) {
    const short = n => n.replace(/\(R\)|\(TM\)/g, '').replace(/^(NVIDIA GeForce|Intel|AMD Radeon)\s*/i, '').replace(/ Laptop GPU| Graphics/i, '').trim();
    const usage = name => (L.gpus.find(g => g.name === name) || L.gpus.find(g => short(g.name) === short(name)) || {}).pct;
    const main = S.specs.gpus[0], other = S.specs.gpus[1];
    const a = usage(main.name), b = other ? usage(other.name) : undefined;
    if (a != null) {
      $('#specGpu').textContent = `${Math.round(a)}%` + (b != null ? ` · ${short(other.name)} ${Math.round(b)}%` : '');
      meter('specGpuM', a);
      $('#specGpu').closest('.spec').title = L.gpus.map(g => `${g.name}: ${g.pct}%`).join('\n');
    }
  }
  const tile = $('#specBat').closest('.spec');
  if (L.battery == null) {
    $('#specBatB').textContent = 'Mains power';
    $('#specBat').textContent = '';
    tile.querySelector('.spec-ic').innerHTML = icon('plug');
    $('#specBatM').parentElement.style.display = 'none';
  } else {
    $('#specBatB').textContent = `${L.battery}% · ${L.plugged ? (L.charging ? 'charging' : 'plugged in') : 'on battery'}`;
    $('#specBat').textContent = L.plugged ? '' : 'battery';
    tile.style.setProperty('--sc', L.battery < 20 && !L.plugged ? 'var(--keep)' : 'var(--safe)');
    meter('specBatM', L.battery);
    $('#specBatM').classList.remove('hot');
  }
}

let liveTimer = 0;
async function pollLive() {
  clearTimeout(liveTimer);
  const perfOn = $('#view-perf').classList.contains('active');
  if (($('#view-home').classList.contains('active') || perfOn) && !document.hidden) {
    try { S.live = await Bridge.call('sys_live'); applyLive(); if (perfOn) applyPerfLive(); } catch (e) { /* ignore a missed reading */ }
  }
  liveTimer = setTimeout(pollLive, 2500);
}

function updateNavBadges() {
  const s = S.drv.summary;
  $('#drvNavBadge').textContent = s && s.updates ? s.updates : '';
  const p = S.perf.summary;
  $('#perfNavBadge').textContent = p && p.live.mem_pct >= 80 ? `${p.live.mem_pct}%` : '';
}

/* ================================================================ Drivers */
const DRV_ORDER = ['Graphics', 'Network', 'Audio & media', 'Bluetooth', 'Camera', 'Storage controllers', 'System & chipset',
  'Input devices', 'USB', 'Software components', 'Firmware', 'Biometrics', 'Printers', 'Other'];
const VENDOR_COLORS = { NVIDIA: '#76b900', Intel: '#0071c5', AMD: '#ed1c24', MSI: '#e60012' };
const VENDOR_MARKS = { NVIDIA: 'NV', Intel: 'IN', AMD: 'AMD', MSI: 'MSI', Dell: 'DELL', Lenovo: 'LEN', ASUS: 'ASUS', Acer: 'ACER', HP: 'HP' };

async function loadDriverSummary() {
  try { S.drv.summary = await Bridge.call('drivers_summary'); } catch (e) { S.drv.summary = null; }
  renderHome();
  checkDrivers(false);
}

async function checkDrivers(refresh) {
  if (S.drv.checking || S.drv.installing) return;
  S.drv.checking = true;
  S.drv.err = null;
  renderDrvUpdates(); renderDrvHero(); renderHome();
  try {
    S.drv.updates = await Bridge.call('drivers_check', !!refresh);
    S.drv.sel = new Set(S.drv.updates.updates.filter(u => !u.is_firmware && !u.downgrade).map(u => u.id));
  } catch (e) { S.drv.err = e.message; }
  S.drv.checking = false;
  try { S.drv.summary = await Bridge.call('drivers_summary'); } catch (e) { /* keep the old one */ }
  renderDrvUpdates(); renderDrvHero(); renderHome();
}

async function openDrivers() {
  if (!S.drv.list) {
    $('#drvBody').innerHTML = '<i class="shimmer" style="height:150px"></i><i class="shimmer" style="height:120px"></i><i class="shimmer" style="height:240px"></i>';
    try { S.drv.list = await Bridge.call('drivers_list'); } catch (e) {
      $('#drvBody').innerHTML = `<div class="empty-state">${icon('alert')}Couldn't read the driver list: ${esc(e.message)}</div>`;
      return;
    }
  }
  renderDrivers();
  if (!S.drv.updates && !S.drv.checking) checkDrivers(false);
}

function ageBadge(d) {
  if (d.age == null) return '<span class="age inbox">built-in</span>';
  const cls = d.age < 1 ? 'fine' : d.age <= 3 ? 'older' : 'old';
  return `<span class="age ${cls}" title="Driver dated ${esc(d.date)}">${d.age < 1 ? '< 1 yr' : `${d.age} yrs`}</span>`;
}
function drvRow(d) {
  return `<button class="drv-row" data-i="${S.drv.list.drivers.indexOf(d)}" title="Details and how to update">
    <span>${esc(d.name)}<small>${esc(d.provider)}</small></span>
    <code title="Driver version">${esc(d.version)}</code>${ageBadge(d)}${icon('chevron')}</button>`;
}

// Windows Update offers that belong to this device (matched on the device name).
function drvOffers(d) {
  const ups = (S.drv.updates && S.drv.updates.updates) || [];
  const name = d.name.toLowerCase();
  return ups.filter(u => {
    const model = (u.model || '').toLowerCase();
    return model && (model.includes(name) || name.includes(model));
  });
}

function ageText(d) {
  if (d.age == null) return 'This is a driver built into Windows. It is updated together with Windows itself.';
  if (d.age < 1) return 'Released in the last year - nothing to worry about.';
  return `Released ${d.age} years ago. Age alone doesn't mean it's out of date: makers often stop releasing new versions once a driver works well. ` +
    'It only needs updating if its maker has a newer version for your PC.';
}

async function driverDetail(d) {
  const src = d.source, D = S.drv, offers = drvOffers(d).filter(u => !u.downgrade);
  const wu = D.checking ? 'Windows Update is still being checked…'
    : !D.updates ? "Windows Update hasn't been checked yet."
    : offers.length ? `Windows Update offers: ${offers.map(u => u.title).join(', ')}`
    : 'Windows Update has no newer driver for this device (optional driver updates included).';
  const body = `<div class="drv-detail">
      <div><small>Version</small><b>${esc(d.version)}</b></div>
      <div><small>Released</small><b>${esc(d.date || '—')}</b> ${ageBadge(d)}</div>
      <div><small>Maker</small><b>${esc(d.provider || '—')}</b></div>
      <div><small>Type</small><b>${esc(d.group)}</b></div></div>
    <p>${esc(ageText(d))}</p>
    <div class="drv-src">${icon(offers.length ? 'download' : 'check')}<span><b>Windows Update</b>${esc(wu)}</span></div>
    ${src.target ? `<div class="drv-src">${icon('open')}<span><b>Best place to update: ${esc(src.label)}</b>${esc(src.why)}</span></div>`
      : `<div class="drv-src">${icon('chip')}<span><b>${esc(src.label)}</b>${esc(src.why)}</span></div>`}`;
  const extra = offers.length && src.target ? [{ label: `Open ${src.label}`, icon: 'open', value: 'tool' }] : [];
  const choice = await confirmDialog({
    title: d.name, icon: 'chip', body, extra, cancelLabel: 'Close',
    okLabel: offers.length ? 'Install from Windows Update' : src.target ? `Open ${src.label}` : 'OK',
  });
  if (choice === 'tool' || (choice === true && !offers.length && src.target)) {
    Bridge.call('open_vendor_tool', src.target).then(() => toast('info', `Opened ${src.label}`)).catch(fail);
  } else if (choice === true && offers.length) {
    D.sel = new Set(offers.map(u => u.id));
    renderDrvUpdates();
    installDrivers();
  }
}

// One button: install what Windows Update offers, then open each official tool that covers the rest.
async function updateAllDrivers() {
  const D = S.drv;
  if (D.checking || D.installing) return toast('info', 'Wait for the Windows Update check to finish');
  const offers = ((D.updates && D.updates.updates) || []).filter(u => !u.downgrade && !u.is_firmware);
  const tools = new Map();
  D.list.drivers.filter(d => !d.virtual && d.source.target).forEach(d => {
    const t = tools.get(d.source.target) || { label: d.source.label, target: d.source.target, names: [] };
    t.names.push(d.name);
    tools.set(d.source.target, t);
  });
  const list = [...tools.values()];
  const firmware = ((D.updates && D.updates.updates) || []).filter(u => !u.downgrade && u.is_firmware);
  const ok = await confirmDialog({
    title: 'Update all drivers safely', icon: 'download', okLabel: offers.length ? 'Start' : 'Open the tools',
    body: `<p>Only official sources are used: Microsoft's Windows Update and the makers' own tools. Nothing comes from third-party driver sites.</p>
      <div class="what-steps">
        <div class="what-step"><span class="n">1</span><span><b>Windows Update</b><small>${offers.length
          ? `Installs ${offers.length} driver update${offers.length === 1 ? '' : 's'} automatically, after creating a restore point.`
          : 'Nothing to install - Windows Update has no newer drivers for this PC.'}</small></span><span></span></div>
        ${list.map((t, i) => `<div class="what-step"><span class="n">${i + 2}</span><span><b>${esc(t.label)}</b><small>Opens so you can install its updates for ${t.names.length} driver${t.names.length === 1 ? '' : 's'}
          (${esc(t.names.slice(0, 3).join(', '))}${t.names.length > 3 ? '…' : ''}).</small></span><span></span></div>`).join('')}
      </div>
      ${firmware.length ? '<p class="warn">BIOS / firmware updates are not included. Install them on their own from the list, with the laptop plugged in.</p>' : ''}`,
  });
  if (!ok) return;
  if (offers.length) {
    D.sel = new Set(offers.map(u => u.id));
    await installDrivers(true);
  }
  for (const t of list) {
    try { await Bridge.call('open_vendor_tool', t.target); } catch (e) { fail(e); }
  }
  if (list.length) toast('info', `Opened ${list.map(t => t.label).join(', ')} - install their updates there`, 9000);
}

function renderDrivers() {
  const L = S.drv.list;
  const real = L.drivers.filter(d => !d.virtual), virt = L.drivers.filter(d => d.virtual);
  const groups = DRV_ORDER.map(g => [g, real.filter(d => d.group === g)]).filter(([, ds]) => ds.length);
  $('#drvBody').innerHTML = `
    <div class="card drv-hero" id="drvHero"></div>
    <div class="card drv-card" id="drvUpdates"></div>
    <div class="card drv-card"><h3>${icon('open')}Vendor tools</h3>
      <p>These can have newer drivers than Windows Update. They open in their own app or your browser — you install from there.</p>
      <div class="drv-tools">${L.tools.map(t => `<button class="drv-tool" data-target="${esc(t.target)}">
        <span class="vend" style="background:${VENDOR_COLORS[t.vendor] || 'var(--accent)'}">${esc(VENDOR_MARKS[t.vendor] || t.vendor.slice(0, 3).toUpperCase())}</span>
        <span><b>${esc(t.label)}</b><small>${esc(t.note || (t.installed ? 'Installed — opens the app' : 'Opens the official page'))}</small></span>${icon('open')}</button>`).join('')}</div></div>
    <div class="drv-groups">${groups.map(([g, ds], i) => `<div class="card drv-group" style="--i:${i}"><h4>${esc(g)} <small>${ds.length}</small></h4>${ds.map(drvRow).join('')}</div>`).join('')}
      ${virt.length ? `<details class="card drv-group drv-virtual"><summary>Virtual adapters (VPN, VMware…) · ${virt.length}</summary>${virt.map(drvRow).join('')}</details>` : ''}</div>`;
  renderDrvHero();
  renderDrvUpdates();
}

function renderDrvHero() {
  const el = $('#drvHero');
  if (!el || !S.drv.list) return;
  const sys = S.drv.list.system, s = S.drv.summary || {};
  const upd = S.drv.checking ? '…' : s.updates == null ? '—' : String(s.updates);
  el.innerHTML = `<div class="drv-pc"><span class="drv-pc-ic">${icon('chip')}</span><div><h1>Drivers</h1>
      <p>${esc(sys.oem || sys.manufacturer)} ${esc(sys.model)} · ${esc((sys.os || '').replace('Microsoft ', ''))} build ${esc(sys.build)}</p></div></div>
    <div class="drv-hero-btns">
      <button class="btn" id="drvCheckBtn" ${S.drv.checking || S.drv.installing ? 'disabled' : ''}>${icon('refresh')}Check again</button>
      <button class="btn clean" id="drvAllBtn" ${S.drv.checking || S.drv.installing ? 'disabled' : ''}
        title="Windows Update first, then each maker's official tool">${icon('download')}Update everything safely</button></div>
    <div class="drv-stats">
      <div class="stat"><small>${icon('chip')}Vendor drivers</small><b>${num(S.drv.list.drivers.length)}</b></div>
      <div class="stat"><small>${icon('download')}Updates available</small><b class="${s.updates ? 'warn' : 'ok'}">${upd}</b></div>
      <div class="stat"><small>${icon('clock')}Older than 3 years</small><b class="${s.old ? 'warn' : 'ok'}">${num(s.old || 0)}</b></div>
      <div class="stat"><small>${icon('lock')}BIOS ${esc(sys.bios || '')}</small><b>${sys.bios_age != null ? `${sys.bios_age} yrs` : '—'}</b></div>
    </div>`;
  $('#drvCheckBtn').onclick = () => checkDrivers(true);
  $('#drvAllBtn').onclick = updateAllDrivers;
}

function renderDrvUpdates() {
  const el = $('#drvUpdates');
  if (!el) return;
  const D = S.drv;
  if (D.installing) {
    el.innerHTML = `<h3>${icon('download')}Installing driver updates</h3>
      <p>Windows may ask for administrator permission. Keep the PC on and plugged in until this finishes.</p>
      <div class="drv-step"><span class="thinking"><i></i><i></i><i></i></span><span id="drvStep">${esc(D.step || 'Waiting for administrator permission')}…</span></div>`;
    return;
  }
  let html = '';
  if (D.result) {
    const r = D.result;
    html += `<h3>${icon('check')}Last install</h3>
      ${r.restore_point ? `<p>Restore point: ${esc(r.restore_point)}</p>` : ''}
      ${r.error ? `<div class="drv-result fail">${icon('alert')}<span>${esc(r.error)}</span></div>` : ''}
      ${(r.updates || []).map(u => `<div class="drv-result ${u.ok ? 'ok' : 'fail'}">${icon(u.ok ? 'check' : 'alert')}<span>${esc(u.title)}</span>
        <em>${esc(u.note || u.status)}${u.hresult && !u.ok ? ` (${esc(u.hresult)})` : ''}</em></div>`).join('')}
      ${r.reboot ? `<div class="reboot-banner">${icon('restart')}<span>Restart Windows to finish installing.</span>
        <button class="btn sm" data-drv="later">Later</button><button class="btn clean sm" data-drv="restart">Restart now</button></div>` : ''}
      <hr style="border:0;border-top:1px solid var(--border);margin:16px 0">`;
  }
  if (D.checking) {
    html += `<h3>${icon('download')}Windows Update</h3><p>Asking Windows Update which driver updates fit this PC (usually 30–60 seconds)…</p>
      <div class="ai-progress indet" style="margin:0"><i></i></div><i class="shimmer" style="height:64px;margin-top:12px"></i>`;
  } else if (D.err) {
    html += `<h3>${icon('alert')}Windows Update</h3><p>Couldn't check for updates: ${esc(D.err)}</p>`;
  } else if (D.updates) {
    const ups = D.updates.updates;
    const checked = new Date(D.updates.checked_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (!ups.length) {
      html += `<h3>${icon('check')}Up to date with Windows Update</h3><p>No driver updates are offered for this PC (checked at ${checked}). The vendor tools below may still have newer versions.</p>`;
    } else {
      const n = ups.filter(u => D.sel.has(u.id)).length;
      html += `<h3>${icon('download')}${ups.length} update${ups.length === 1 ? '' : 's'} from Windows Update</h3>
        <p>Matched to this PC's hardware by Microsoft (checked at ${checked}). Tick what you want to install.</p>
        <div class="qc-list">${ups.map((u, i) => {
          const on = D.sel.has(u.id);
          return `<label class="qc-item drv-update shown ${u.is_firmware ? 'fw' : ''} ${u.downgrade ? 'blocked' : ''} ${on ? 'checked' : ''}" data-id="${esc(u.id)}" style="--i:${i};animation:none">
            <input type="checkbox" ${on ? 'checked' : ''} ${u.downgrade ? 'disabled' : ''}><span class="check">${icon('checkmark')}</span>
            <span class="qc-ic">${icon(u.is_firmware ? 'chip' : 'download')}</span>
            <div class="qc-text"><b>${esc(u.title)}</b><small>${esc([u.model, u.date && `released ${u.date}`].filter(Boolean).join(' · '))}</small>
              <div class="qc-tags">${u.downgrade ? `<span class="tag warn" style="color:var(--keep)">Older than your installed BIOS (${esc(S.drv.list ? S.drv.list.system.bios : '')}) — blocked</span>`
                : u.is_firmware ? '<span class="tag warn">Firmware — keep the laptop plugged in, don\'t turn it off</span>' : ''}
                ${u.reboot ? '<span class="tag">Restart needed</span>' : ''}</div></div>
            <div class="qc-size"><b>${fmtSize(u.size)}</b></div></label>`;
        }).join('')}</div>
        <div class="drv-actions"><label><input type="checkbox" id="drvRestore" checked>Create a restore point first</label>
          <button class="btn clean" id="drvInstallBtn" ${n ? '' : 'disabled'}>${icon('download')}Install selected (${n})</button></div>`;
    }
  }
  el.innerHTML = html;
  const ib = $('#drvInstallBtn');
  if (ib) ib.onclick = installDrivers;
}

async function installDrivers(confirmed = false) {
  const D = S.drv;
  const picked = D.updates.updates.filter(u => D.sel.has(u.id) && !u.downgrade);
  if (!picked.length) return;
  const restore = $('#drvRestore') ? $('#drvRestore').checked : true;
  const fw = picked.some(u => u.is_firmware);
  const ok = confirmed === true || await confirmDialog({
    title: `Install ${picked.length} driver update${picked.length === 1 ? '' : 's'}?`, icon: 'download', danger: fw,
    okLabel: 'Install',
    body: `<ul>${picked.map(u => `<li><span>${esc(u.title)}</span><span>${fmtSize(u.size)}</span></li>`).join('')}</ul>
      <p>Windows will ask for administrator permission. ${restore ? 'A restore point is created first, so you can roll back.' : 'No restore point will be created.'}</p>
      ${fw ? '<p class="warn">This includes firmware. Keep the laptop plugged in and don\'t turn it off until it finishes.</p>' : ''}`,
  });
  if (!ok) return;
  D.installing = true; D.step = ''; D.result = null;
  renderDrvUpdates(); renderDrvHero();
  try {
    D.result = await Bridge.call('drivers_install', picked.map(u => u.id), restore);
    const good = (D.result.updates || []).filter(u => u.ok).length;
    toast(good ? 'ok' : 'info', `${good} of ${picked.length} driver update${picked.length === 1 ? '' : 's'} installed` +
      (D.result.reboot ? ' · restart to finish' : ''), 8000);
  } catch (e) { fail(e); }
  D.installing = false;
  D.updates = null; D.list = null;      // re-read what is installed now
  await openDrivers();
  checkDrivers(true);
}

$('#drvBody').addEventListener('change', e => {
  const card = e.target.closest('.drv-update');
  if (!card || !S.drv.sel) return;
  if (e.target.checked) S.drv.sel.add(card.dataset.id); else S.drv.sel.delete(card.dataset.id);
  card.classList.toggle('checked', e.target.checked);
  const n = S.drv.sel.size, ib = $('#drvInstallBtn');
  if (ib) { ib.disabled = !n; ib.lastChild.textContent = `Install selected (${n})`; }
});
$('#drvBody').addEventListener('click', async e => {
  const tool = e.target.closest('.drv-tool');
  if (tool) return Bridge.call('open_vendor_tool', tool.dataset.target).catch(fail);
  const row = e.target.closest('.drv-row');
  if (row) return driverDetail(S.drv.list.drivers[+row.dataset.i]);
  const b = e.target.closest('[data-drv]');
  if (!b) return;
  if (b.dataset.drv === 'later') { S.drv.result.reboot = false; return renderDrvUpdates(); }
  const ok = await confirmDialog({ title: 'Restart Windows now?', icon: 'restart', okLabel: 'Restart in 10 seconds', danger: true,
    body: '<p>Save your work in other apps first. Windows restarts 10 seconds after you confirm.</p>' });
  if (ok) Bridge.call('restart_pc').then(() => toast('info', 'Windows will restart in 10 seconds', 10000)).catch(fail);
});

/* ================================================================ Performance */
async function loadPerfSummary() {
  try { S.perf.summary = await Bridge.call('perf_summary'); } catch (e) { S.perf.summary = null; }
  renderHome();
}

async function openPerf(refresh = false) {
  const P = S.perf;
  if (P.snap && !refresh) return renderPerf();
  if (P.loading) return;
  P.loading = true; P.err = null;
  if (!P.snap) $('#perfBody').innerHTML = '<i class="shimmer" style="height:170px"></i><i class="shimmer" style="height:140px"></i><i class="shimmer" style="height:260px"></i>';
  else renderPerfHero();
  try {
    P.snap = await Bridge.call('perf_snapshot');
    P.sel = new Set(P.snap.groups.filter(g => g.cat === 'safe').map(g => g.key));
    S.live = P.snap.live;
  } catch (e) { P.err = e.message; }
  P.loading = false;
  if (!P.snap) {
    $('#perfBody').innerHTML = `<div class="empty-state">${icon('alert')}Couldn't read the running processes: ${esc(P.err)}</div>`;
    return;
  }
  renderPerf();
  loadPerfSummary();
}

const perfGroups = cat => S.perf.snap.groups.filter(g => g.cat === cat);
const procLabel = g => g.desc && g.desc.toLowerCase() !== g.name.toLowerCase() ? g.desc : g.name;
const procMeta = g => [g.count > 1 ? `${g.count} processes` : `${g.name}.exe`, g.company].filter(Boolean).join(' · ');
const cpuTag = g => g.cpu >= 1 ? `<span class="tag ${g.cpu >= 10 ? 'warn' : ''}">CPU ${g.cpu}%</span>` : '';

function renderPerf() {
  const P = S.perf, sn = P.snap;
  const safe = perfGroups('safe'), apps = perfGroups('app'), review = perfGroups('review');
  const sys = sn.groups.filter(g => ['windows', 'self', 'keep'].includes(g.cat));
  $('#perfBody').innerHTML = `
    <div class="card drv-hero perf-hero" id="perfHero"></div>
    <div id="perfResult"></div>
    <div class="card drv-card"><h3>${icon('zap')}Safe to close <small class="perf-count">${safe.length}</small></h3>
      <p>Background helpers with no window open: updaters, tray icons and apps that kept running after you closed them. They start again on their own when needed.</p>
      ${safe.length ? `<div class="qc-list perf-list">${safe.map((g, i) => {
        const on = P.sel.has(g.key);
        return `<label class="qc-item perf-item shown ${on ? 'checked' : ''}" data-key="${esc(g.key)}" style="--i:${i};animation:none">
          <input type="checkbox" ${on ? 'checked' : ''}><span class="check">${icon('checkmark')}</span><span class="qc-ic">${icon('zap')}</span>
          <div class="qc-text"><b>${esc(procLabel(g))}</b><small>${esc(procMeta(g))}</small><small class="why">${esc(g.reason)}</small>
            <div class="qc-tags">${cpuTag(g)}</div></div>
          <div class="qc-size"><b>${fmtSize(g.mem)}</b><small>memory</small></div></label>`;
      }).join('')}</div>
      <div class="drv-actions"><span class="muted" id="perfSelInfo"></span>
        <button class="btn clean" id="perfCloseBtn">${icon('x')}Close selected</button></div>`
        : `<div class="perf-empty">${icon('check')}Nothing unnecessary is running in the background.</div>`}
    </div>
    <div class="card drv-card"><h3>${icon('monitor')}Open apps <small class="perf-count">${apps.length}</small></h3>
      <p>Apps with a window. Closing asks the app to quit normally, so it can ask you to save your work first.</p>
      <div class="perf-rows">${apps.map(g => procRow(g, [['close', 'x', 'Close']])).join('') || '<div class="perf-empty">No apps open.</div>'}</div></div>
    <div class="card drv-card"><h3>${icon('eye')}Other background processes <small class="perf-count">${review.length}</small></h3>
      <p>Not part of Windows and not on the safe list: sync tools, drivers' helpers, services from apps you installed. Close one only if you know what it is${S.aiOn ? ' - or ask the AI to explain it' : ''}.</p>
      <div class="perf-rows">${review.map(g => procRow(g, [...(S.aiOn ? [['explain', 'sparkle', 'Explain']] : []), ['reveal', 'explorer', ''], ['close', 'x', 'Close']])).join('')
        || '<div class="perf-empty">None.</div>'}</div></div>
    <div class="card drv-card" id="perfStartup"></div>
    <div class="card drv-card" id="perfWins"></div>
    <details class="card drv-card perf-sys"><summary>${icon('lock')}Windows, services and this app · ${sys.length} programs, ${num(sys.reduce((n, g) => n + g.count, 0))} processes
      <small>never closed from here</small></summary>
      <div class="perf-rows">${sys.map(g => procRow(g, [])).join('')}</div></details>`;
  renderPerfHero();
  renderPerfResult();
  renderStartup();
  renderQuickWins();
  updatePerfSel();
}

function procRow(g, actions) {
  return `<div class="perf-row" data-key="${esc(g.key)}">
    <span class="perf-name"><b title="${esc(g.path || g.name)}">${esc(procLabel(g))}</b><small title="${esc(g.reason)}">${esc(g.title ? `“${g.title}” · ` : '')}${esc(procMeta(g))}</small></span>
    ${cpuTag(g)}<em>${fmtSize(g.mem)}</em>
    <span class="perf-acts">${actions.map(([act, ic, label]) => `<button class="btn sm" data-pact="${act}" title="${act === 'reveal' ? 'Show in Explorer' : label}">${icon(ic)}${label}</button>`).join('')}</span></div>`;
}

function renderPerfHero() {
  const el = $('#perfHero');
  if (!el || !S.perf.snap) return;
  const P = S.perf, busy = P.busy || P.loading;
  el.innerHTML = `<div class="drv-pc"><div class="perf-gauge"><svg class="ring" viewBox="0 0 44 44"><circle class="ring-bg" cx="22" cy="22" r="18"/>
        <circle class="ring-fg" id="perfRing" cx="22" cy="22" r="18" pathLength="100"/></svg><b id="perfMemPct">—</b><small>memory</small></div>
      <div><h1>Performance</h1><p id="perfMemText">…</p></div></div>
    <div class="drv-hero-btns">
      <button class="btn" id="perfRefresh" ${busy ? 'disabled' : ''}>${icon('refresh')}Refresh</button>
      <button class="btn" id="perfTrimBtn" ${busy ? 'disabled' : ''} title="Trim the memory apps aren't using">${icon('memory')}Clean RAM</button>
      <button class="btn clean" id="perfBoostBtn" ${busy ? 'disabled' : ''}>${icon('zap')}Boost now</button></div>
    <div class="drv-stats">
      <div class="stat"><small>${icon('chip')}Processor</small><b id="perfCpu">…</b></div>
      <div class="stat"><small>${icon('grid')}Processes</small><b>${num(P.snap.total)}</b></div>
      <div class="stat"><small>${icon('zap')}Safe to close</small><b class="${perfGroups('safe').length ? 'warn' : 'ok'}">${fmtSize(perfGroups('safe').reduce((n, g) => n + g.mem, 0))}</b></div>
      <div class="stat"><small>${icon('clock')}Up since restart</small><b id="perfUp">…</b></div>
    </div>
    <p class="perf-note">${icon('info')}<span>Free memory alone doesn't make Windows faster - Windows uses spare RAM as a cache. What helps is closing background apps
      that use memory or CPU, keeping fewer apps starting with Windows, and trimming memory when it's nearly full (above ~80%).</span></p>`;
  $('#perfRefresh').onclick = () => openPerf(true);
  $('#perfTrimBtn').onclick = cleanRam;
  $('#perfBoostBtn').onclick = boostNow;
  applyPerfLive();
}

function applyPerfLive() {
  const L = S.live, ring = $('#perfRing');
  if (!L || !ring) return;
  ring.style.strokeDashoffset = 100 - L.mem_pct;
  ring.classList.toggle('hot', L.mem_pct >= 85);
  $('#perfMemPct').textContent = `${L.mem_pct}%`;
  $('#perfMemText').textContent = `${(L.mem_used / 2 ** 30).toFixed(1)} GB of ${Math.round(L.mem_total / 2 ** 30)} GB memory in use` +
    (L.mem_pct >= 85 ? ' - nearly full' : L.mem_pct >= 70 ? ' - fairly busy' : ' - plenty free');
  if (L.cpu != null) $('#perfCpu').textContent = `${Math.round(L.cpu)}%`;
  $('#perfUp').textContent = uptimeText(L.uptime);
}

function renderPerfResult() {
  const el = $('#perfResult'), r = S.perf.last;
  if (!el) return;
  if (!r) { el.innerHTML = ''; return; }
  const b = r.before, a = r.after;
  el.innerHTML = `<div class="card perf-done">${icon('check')}<div><b>${esc(r.title)}</b>
      <small>Memory ${b.mem_pct}% → ${a.mem_pct}% · ${fmtSize(Math.max(0, b.mem_used - a.mem_used))} freed${r.closed ? ` · closed ${r.closed} program${r.closed === 1 ? '' : 's'}` : ''}</small>
      ${(r.failed || []).map(f => `<small class="warn">${esc(f.name)}: ${esc(f.error)}</small>`).join('')}</div>
    <button class="icon-btn" id="perfDoneX" title="Dismiss">${icon('x')}</button></div>`;
  $('#perfDoneX').onclick = () => { S.perf.last = null; renderPerfResult(); };
}

function updatePerfSel() {
  const P = S.perf, info = $('#perfSelInfo'), btn = $('#perfCloseBtn');
  if (!info) return;
  const picked = perfGroups('safe').filter(g => P.sel.has(g.key));
  info.textContent = `${picked.length} selected · ${fmtSize(picked.reduce((n, g) => n + g.mem, 0))}`;
  btn.disabled = !picked.length || P.busy;
}

async function closeGroups(groups, { title, force = false, extraBody = '' } = {}) {
  const P = S.perf;
  const before = S.live || P.snap.live;
  P.busy = true; renderPerfHero();
  let r;
  try { r = await Bridge.call('perf_end', groups.map(g => g.key), force); } catch (e) { fail(e); }
  P.busy = false;
  if (r) {
    P.last = { title: title || 'Closed', before, after: r.live, closed: r.closed.length, failed: r.failed };
    S.live = r.live;
    toast(r.closed.length ? 'ok' : 'info', `${r.closed.length} closed${r.failed.length ? ` · ${r.failed.length} couldn't be closed` : ''}`);
  }
  await openPerf(true);
  return r;
}

$('#perfBody').addEventListener('change', e => {
  const card = e.target.closest('.perf-item');
  if (card) {
    if (e.target.checked) S.perf.sel.add(card.dataset.key); else S.perf.sel.delete(card.dataset.key);
    card.classList.toggle('checked', e.target.checked);
    return updatePerfSel();
  }
  const sw = e.target.closest('.st-toggle input');
  if (sw) toggleStartup(sw);
});

$('#perfBody').addEventListener('click', async e => {
  if (e.target.id === 'perfCloseBtn' || e.target.closest('#perfCloseBtn')) return closeSafe();
  const b = e.target.closest('[data-pact]');
  if (!b) return;
  const g = S.perf.snap.groups.find(x => x.key === b.closest('[data-key]').dataset.key);
  if (!g) return;
  if (b.dataset.pact === 'reveal') return Bridge.call('perf_reveal', g.key).catch(fail);
  if (b.dataset.pact === 'explain') return explainProcess(g, b);
  if (b.dataset.pact === 'close') return closeOne(g);
});

async function closeSafe() {
  const picked = perfGroups('safe').filter(g => S.perf.sel.has(g.key));
  if (!picked.length) return;
  const ok = await confirmDialog({
    title: `Close ${picked.length} background helper${picked.length === 1 ? '' : 's'}?`, icon: 'zap', okLabel: 'Close them',
    body: `<ul>${picked.map(g => `<li><span>${esc(procLabel(g))}</span><span>${fmtSize(g.mem)}</span></li>`).join('')}</ul>
      <p>They have no open windows, so no work is lost. They start again on their own when needed - for good, turn them off under Startup apps.</p>`,
  });
  if (ok) closeGroups(picked, { title: 'Background helpers closed' });
}

async function closeOne(g) {
  const isApp = g.cat === 'app';
  const ok = await confirmDialog({
    title: `Close ${procLabel(g)}?`, icon: isApp ? 'monitor' : 'alert', okLabel: 'Close', danger: !isApp,
    body: isApp ? `<p>${esc(procLabel(g))} is asked to quit normally${g.title ? ` (“${esc(g.title)}”)` : ''}. If you have unsaved work, it will ask you first.</p>`
      : `<p><b>${esc(g.name)}.exe</b>${g.company ? ` from ${esc(g.company)}` : ''} - ${esc(g.reason)}</p>
        <p class="warn">This isn't on the safe list. If something stops working, restart the app it belongs to (or your PC).</p>
        <p class="muted">${esc(g.path || '')}</p>`,
  });
  if (!ok) return;
  const r = await closeGroups([g], { title: `${procLabel(g)} closed` });
  const stuck = r && r.failed.find(f => f.app);
  if (stuck) {
    const force = await confirmDialog({
      title: `${procLabel(g)} is still open`, icon: 'alert', danger: true, okLabel: 'Force close',
      body: '<p>It may be showing a "save your changes?" prompt - check its window first.</p><p class="warn">Force closing ends it immediately: anything unsaved is lost.</p>',
    });
    if (force) {
      const fresh = S.perf.snap.groups.find(x => x.key === g.key);
      if (fresh) closeGroups([fresh], { title: `${procLabel(g)} force closed`, force: true });
    }
  }
}

async function explainProcess(g, btn) {
  if (!S.aiLocal && S.aiConfirm) {
    const ok = await confirmDialog({ title: 'Ask the cloud AI?', icon: 'sparkle', okLabel: 'Ask',
      body: `<p>Sends <b>${esc(g.name)}.exe</b>, its file path, publisher and description to ${esc(S.aiLabel)}. Nothing else leaves your PC.</p>` });
    if (!ok) return;
  }
  busy(btn, true); aiBusy(1);
  try {
    const r = await Bridge.call('perf_explain', g.key);
    const close = await confirmDialog({
      title: procLabel(g), icon: 'sparkle', cancelLabel: 'Done', okLabel: 'Close it…',
      body: `<div class="ai-answer">${esc(r.answer).replace(/\n/g, '<br>')}</div><p class="muted">${esc(r.model)}${usageText(r.usage)} · AI can be wrong - double-check before closing.</p>`,
    });
    if (close) closeOne(g);
  } catch (e) { fail(e); }
  busy(btn, false); aiBusy(-1);
}

async function cleanRam() {
  const L = S.live || S.perf.snap.live;
  const ok = await confirmDialog({
    title: 'Clean RAM?', icon: 'memory', okLabel: 'Clean RAM',
    extra: [{ label: 'Also clear standby cache (admin)', icon: 'lock', value: 'purge' }],
    body: `<p>Asks every app to give back memory it isn't actively using. Nothing is closed and no work is lost.</p>
      <p>Memory is at <b>${L.mem_pct}%</b> now. ${L.mem_pct >= 80 ? 'Worth doing - it is nearly full.' : "It isn't full, so the effect will be small."}
      Apps take memory back as they need it, so this is a quick fix, not a permanent one.</p>
      <p class="muted">"Also clear standby cache" also empties Windows' file cache. It needs administrator permission, and the first opening of files and apps is slower afterwards.</p>`,
  });
  if (!ok) return;
  const P = S.perf;
  P.busy = true; renderPerfHero();
  try {
    const r = await Bridge.call('perf_trim');
    let after = r.after, title = 'Memory cleaned';
    if (ok === 'purge') {
      try { after = (await Bridge.call('perf_purge_standby')).after; title = 'Memory and standby cache cleaned'; }
      catch (e) { fail(e); }
    }
    P.last = { title, before: r.before, after, closed: 0 };
    S.live = after;
    toast('ok', `${title} · ${fmtSize(Math.max(0, r.before.mem_used - after.mem_used))} freed`);
  } catch (e) { fail(e); }
  P.busy = false;
  renderPerfHero(); renderPerfResult(); loadPerfSummary();
}

async function boostNow() {
  const picked = perfGroups('safe').filter(g => S.perf.sel.has(g.key));
  const ok = await confirmDialog({
    title: 'Boost now', icon: 'zap', okLabel: 'Boost',
    body: `<div class="what-steps">
      <div class="what-step"><span class="n">1</span><span><b>Close background helpers</b><small>${picked.length
        ? `${picked.length} selected (${fmtSize(picked.reduce((n, g) => n + g.mem, 0))}): ${esc(picked.slice(0, 4).map(procLabel).join(', '))}${picked.length > 4 ? '…' : ''}`
        : 'None selected - skipped.'}</small></span><span></span></div>
      <div class="what-step"><span class="n">2</span><span><b>Clean RAM</b><small>Apps give back memory they aren't using. Nothing else is closed.</small></span><span></span></div>
    </div><p>Open apps and anything not on the safe list are left alone.</p>`,
  });
  if (!ok) return;
  const P = S.perf, before = S.live || P.snap.live;
  P.busy = true; renderPerfHero();
  let closed = 0, failed = [];
  try {
    if (picked.length) {
      const r = await Bridge.call('perf_end', picked.map(g => g.key), false);
      closed = r.closed.length; failed = r.failed;
    }
    const t = await Bridge.call('perf_trim');
    P.last = { title: 'Boost done', before, after: t.after, closed, failed };
    S.live = t.after;
    toast('ok', `Boost done · memory ${before.mem_pct}% → ${t.after.mem_pct}%`, 6000);
  } catch (e) { fail(e); }
  P.busy = false;
  await openPerf(true);
}

function renderStartup() {
  const el = $('#perfStartup'), items = S.perf.snap.startup || [];
  if (!el) return;
  const on = items.filter(i => i.enabled).length;
  el.innerHTML = `<h3>${icon('power')}Startup apps <small class="perf-count">${on} of ${items.length} on</small></h3>
    <p>Apps that start every time you sign in. Fewer of them means Windows starts faster and has more memory free. Turning one off doesn't uninstall it
      and you can turn it back on at any time - it's the same switch as in Task Manager.</p>
    <div class="perf-rows">${items.map(i => `<div class="perf-row st-row ${i.enabled ? '' : 'off'}">
      <span class="perf-name"><b title="${esc(i.command)}">${esc(i.name)}</b><small>${esc([i.desc && i.desc !== i.name ? i.desc : '', i.company, i.where].filter(Boolean).join(' · '))}</small></span>
      ${i.admin ? '<span class="tag" title="Windows asks for administrator permission to change this one">admin</span>' : ''}
      <em title="Memory it uses right now">${i.running_mem ? fmtSize(i.running_mem) : ''}</em>
      <label class="ai-toggle st-toggle" title="${i.enabled ? 'Starts with Windows' : 'Turned off'}"><input type="checkbox" data-id="${esc(i.id)}" ${i.enabled ? 'checked' : ''}><span class="switch"></span></label>
    </div>`).join('') || '<div class="perf-empty">No startup apps found.</div>'}</div>`;
}

async function toggleStartup(input) {
  const item = S.perf.snap.startup.find(i => i.id === input.dataset.id);
  const want = input.checked;
  if (item.admin) {
    const ok = await confirmDialog({ title: `${want ? 'Turn on' : 'Turn off'} ${item.name}?`, icon: 'lock', okLabel: want ? 'Turn on' : 'Turn off',
      body: '<p>This one is set up for all users, so Windows asks for administrator permission.</p>' });
    if (!ok) { input.checked = !want; return; }
  }
  input.disabled = true;
  try {
    const r = await Bridge.call('perf_set_startup', item.id, want);
    item.enabled = r.enabled;
    toast('ok', `${item.name} ${r.enabled ? 'will start' : "won't start"} with Windows`);
  } catch (e) { fail(e); input.checked = item.enabled; }
  input.disabled = false;
  input.closest('.st-row').classList.toggle('off', !item.enabled);
  const on = S.perf.snap.startup.filter(i => i.enabled).length;
  $('#perfStartup .perf-count').textContent = `${on} of ${S.perf.snap.startup.length} on`;
  loadPerfSummary();
}

function renderQuickWins() {
  const el = $('#perfWins'), sn = S.perf.snap;
  if (!el) return;
  const temp = Object.values(S.qc.sizes).reduce((n, m) => n + m.size, 0);
  const days = Math.floor(sn.live.uptime / 86400);
  const tips = [
    [temp > 500 * 2 ** 20 ? 'warn' : 'ok', 'broom', 'Temporary files', temp ? `${fmtSize(temp)} of junk can be removed safely.` : 'Measured in Quick clean.',
      '<button class="btn sm" data-go="quick">Open Quick clean</button>'],
    [days >= 3 ? 'warn' : 'ok', 'restart', 'Restart', days >= 3 ? `Not restarted for ${days} days. A restart clears memory leaks and finishes pending updates.`
      : `Restarted ${uptimeText(sn.live.uptime)} ago - fine.`, days >= 3 ? '<button class="btn sm" data-pwin="restart">Restart…</button>' : ''],
    [sn.power === 'Best power efficiency' ? 'warn' : 'ok', 'power', `Power mode: ${sn.power || 'unknown'}`,
      sn.power === 'Best performance' ? 'Already set for the most speed (uses more battery).'
        : sn.power === 'Best power efficiency' ? 'Saves battery but slows the PC down. Choose Balanced or Best performance when plugged in.'
        : 'Balanced is a good default. Best performance is faster when plugged in.',
      '<button class="btn sm" data-pwin="power">Power settings</button>'],
  ];
  el.innerHTML = `<h3>${icon('wand')}Other quick wins</h3><div class="perf-wins">${tips.map(([lvl, ic, t, d, btn]) =>
    `<div class="perf-win ${lvl}">${icon(ic)}<span><b>${esc(t)}</b><small>${esc(d)}</small></span>${btn}</div>`).join('')}</div>`;
  $$('[data-pwin]', el).forEach(b => b.onclick = async () => {
    if (b.dataset.pwin === 'power') return Bridge.call('perf_power_settings').catch(fail);
    const ok = await confirmDialog({ title: 'Restart Windows now?', icon: 'restart', okLabel: 'Restart in 10 seconds', danger: true,
      body: '<p>Save your work in other apps first. Windows restarts 10 seconds after you confirm.</p>' });
    if (ok) Bridge.call('restart_pc').then(() => toast('info', 'Windows will restart in 10 seconds', 10000)).catch(fail);
  });
}

/* ================================================================ Jarvis assistant */
const agentPanel = $('#agentPanel');
const timeOf = ts => new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

async function openAgent() {
  agentPanel.classList.add('open');
  try {
    const st = await Bridge.call('agent_state');
    S.agent = { state: st, pending: st.pending, job: st.job };
    $('#agentMonitor').checked = st.monitor;
    $('#agentStartup').checked = st.startup;
    renderAgentVoice(st.voice);
    $('#agentLog').innerHTML = '';
    st.transcript.forEach(agentLine);
    if (!st.transcript.length) agentLine({ who: 'jarvis', ts: Date.now() / 1000,
      text: 'Hi! Ask me to check your PC, clean junk, find files you can delete, organise a folder, boost performance or review startup apps.' });
  } catch (e) { fail(e); }
  renderAgentStatus();
  setTimeout(() => $('#agentText').focus(), 200);
}
function closeAgent() { agentPanel.classList.remove('open'); }

function agentLine(d) {
  const log = $('#agentLog');
  if (!log || !d.text) return;
  const el = document.createElement('div');
  el.className = `agent-msg ${d.who === 'you' ? 'you' : 'jarvis'} ${d.kind || ''}`;
  el.innerHTML = `<p>${esc(d.text)}</p><small>${d.kind === 'critical' ? `${icon('alert')}Critical · ` : d.kind === 'alert' ? `${icon('alert')}Heads up · ` : ''}${d.source === 'dashboard' ? "by voice (Sekar's Dashboard) · " : d.source === 'voice' ? 'by voice · ' : ''}${timeOf(d.ts)}</small>`;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
}

function renderAgentStatus() {
  const p = S.agent.pending, job = S.agent.job;
  $('#agentBadge').textContent = p ? '1' : '';
  $('#agentOrb').classList.toggle('busy', !!job);
  $('#agentStatus').textContent = job ? `${job}…` : p ? 'Waiting for your answer' : 'Say "Hey Jarvis", or type below';
  const box = $('#agentPending');
  box.hidden = !p;
  if (!p) return;
  box.innerHTML = `<b>${esc(p.question)}</b>
    ${p.items.length ? `<details><summary>${num(p.count)} item${p.count === 1 ? '' : 's'}</summary><ul>${p.items.map(i => `<li>${esc(i)}</li>`).join('')}
      ${p.count > p.items.length ? `<li>… and ${num(p.count - p.items.length)} more</li>` : ''}</ul></details>` : ''}
    <div class="agent-btns"><button class="btn clean sm" data-ans="yes">${icon('checkmark')}Yes</button>
      <button class="btn sm" data-ans="no">No</button>${p.review && p.review.view ? `<button class="btn sm" data-ans="review">${icon('eye')}Review</button>` : ''}</div>`;
}

// Jarvis's own microphone (System Utilities listens itself while the Dashboard is closed).
function renderAgentVoice(v) {
  const mic = $('#agentMic'), line = $('#agentVoiceState');
  if (!v) { mic.hidden = true; line.textContent = 'Voice isn\'t available on this PC (speech packages missing).'; return; }
  mic.hidden = v.mode === 'off';
  $('#agentVoiceMode').value = v.mode;
  $('#agentSpeak').checked = v.speak;
  mic.classList.toggle('rec', v.state === 'recording');
  mic.classList.toggle('busy', v.state === 'transcribing');
  const states = { recording: 'Listening to you…', transcribing: 'Working out what you said…', starting: v.detail || 'Starting the microphone…',
    error: `Voice problem: ${v.detail || 'unknown'}` };
  line.textContent = v.mode === 'off' ? 'Voice is off - type below.'
    : states[v.state] || (v.dashboard ? `Sekar's Dashboard is listening for "Hey Jarvis". Here: mic button or ${v.hotkey}.`
      : v.wake ? `Listening for "Hey Jarvis" · or press ${v.hotkey}` : `Press the mic button or ${v.hotkey} to talk`);
}
$('#agentMic').addEventListener('click', () => Bridge.call('agent_voice_listen').then(renderAgentVoice).catch(fail));
$('#agentVoiceMode').addEventListener('change', e => Bridge.call('agent_voice_settings', e.target.value, null).then(renderAgentVoice).catch(fail));
$('#agentSpeak').addEventListener('change', e => Bridge.call('agent_voice_settings', null, e.target.checked).then(renderAgentVoice).catch(fail));

async function agentSend(text) {
  if (!text.trim()) return;
  try { await Bridge.call('agent_ask', text); } catch (e) { fail(e); }
}

// "Review" / "show me": open the screen the assistant was talking about.
async function agentShow(d) {
  const v = d.view;
  if (v === 'assistant') return openAgent();
  if (v === 'learned') return showLearned();
  closeAgent();
  if (v === 'quick') { setMode('cleanup', 'quick'); return loadQuick(); }
  if (v === 'perf' || v === 'performance') return setMode('perf');
  if (v === 'drivers') return setMode('drivers');
  if (v === 'home') return setMode('home');
  if (v === 'organiser') { setMode('organise'); if (d.path && S.root) await openFolder(d.path, 'in'); return; }
  if (v === 'cleanup' || v === 'explorer') {
    setMode(v === 'cleanup' ? 'cleanup' : 'organise');
    if (S.root && d.path) await openFolder(d.path, 'in');
    if (v === 'cleanup') {
      try {
        const r = await Bridge.call('current_candidates');
        S.cats = r.categories;
        if (r.ai_items) S.ai = { running: false, done: 0, total: 0, model: r.model, items: r.ai_items, shown: r.ai_items.length };
        renderCats();
      } catch (e) { fail(e); }
    }
  }
}

async function showLearned() {
  let L;
  try { L = await Bridge.call('agent_learned'); } catch (e) { return fail(e); }
  const policyText = { never: 'never suggested', usual: 'you usually delete these', default: 'suggested after a while', ask: 'still learning' };
  const label = p => p.kind === 'docs' ? `${p.category} documents` : `${p.kind}${p.category ? ` · ${p.category}` : ''}`;
  const body = () => `<div class="learned">
    <p>Everything here was learned on this PC only and stays in <code>${esc(L.folder)}</code>. It's never synced or shipped with the app.
      Only short rules (below) are ever given to the AI.</p>
    <div class="learned-stats"><span><b>${num(L.counts.decisions)}</b>answers</span><span><b>${num(L.counts.procs)}</b>programs seen</span>
      <span><b>${num(L.opened)}</b>documents you opened</span><span><b>${num(L.counts.requests)}</b>requests</span></div>
    <h4 class="see-h">Rules I follow</h4>
    ${L.rules.length ? `<ul>${L.rules.map(r => `<li>${esc(r)}</li>`).join('')}</ul>` : '<p class="muted">None yet - they build up as you answer yes or no.</p>'}
    <h4 class="see-h">Your answers</h4>
    <div class="see-list">${L.patterns.map(p => `<div class="learn-row"><span><b>${esc(label(p))}</b>
        <small>${p.yes} yes · ${p.no} no${p.review ? ` · ${p.review} reviewed` : ''}${p.policy ? ` · ${policyText[p.policy] || p.policy}` : ''}</small></span>
        ${p.kind === 'docs' ? `<button class="btn sm" data-teach="docs|${esc(p.category)}|keep">Keep these</button><button class="btn sm" data-teach="docs|${esc(p.category)}|delete">OK to delete</button>` : ''}
        <button class="btn sm" data-forget="pattern:${esc(p.kind)}|${esc(p.category)}" title="Forget">${icon('x')}</button></div>`).join('') || '<p class="muted">No answers yet.</p>'}</div>
    <h4 class="see-h">Programs that look suspicious</h4>
    <div class="see-list">${L.suspicious.map(s => `<div class="learn-row"><span><b>${esc(s.name)}</b><small>${esc(s.reasons.join('; '))}</small></span>
        <button class="btn sm" data-teach="process|${esc(s.exe)}|ok">Not suspicious</button></div>`).join('') || '<p class="muted">None.</p>'}</div>`;
  // buttons inside the dialog re-render it with what the backend now knows
  showLearned._refresh = async promise => { try { L = await promise; $('#modalBody').innerHTML = body(); } catch (e) { fail(e); } };
  await confirmDialog({ title: 'What Jarvis has learned', icon: 'sparkle', body: body(), okLabel: 'Done', cancelLabel: null,
    extra: [{ label: 'Forget everything', icon: 'trash', fn: () => {
      if (!window.confirm('Forget everything Jarvis has learned on this PC?')) return;
      showLearned._refresh(Bridge.call('agent_forget', 'all')).then(() => toast('ok', 'Jarvis forgot everything'));
    } }] });
  showLearned._refresh = null;
}
$('#modalBody').addEventListener('click', e => {
  const t = e.target.closest('[data-teach]'), f = e.target.closest('[data-forget]');
  if (!showLearned._refresh || !(t || f)) return;
  if (t) { const [kind, cat, choice] = t.dataset.teach.split('|'); showLearned._refresh(Bridge.call('agent_teach', kind, cat, choice)); }
  else showLearned._refresh(Bridge.call('agent_forget', f.dataset.forget));
});

$('#agentBtn').addEventListener('click', () => (agentPanel.classList.contains('open') ? closeAgent() : openAgent()));
$('#agentClose').addEventListener('click', closeAgent);
$('#agentLearnedBtn').addEventListener('click', showLearned);
$('#agentForm').addEventListener('submit', e => {
  e.preventDefault();
  const input = $('#agentText');
  agentSend(input.value);
  input.value = '';
});
$('#agentPending').addEventListener('click', async e => {
  const b = e.target.closest('[data-ans]');
  if (!b) return;
  try { await Bridge.call('agent_answer', b.dataset.ans); } catch (err) { fail(err); }
});
$('#agentMonitor').addEventListener('change', e => Bridge.call('agent_settings', e.target.checked, null).catch(fail));
$('#agentStartup').addEventListener('change', e => Bridge.call('agent_settings', null, e.target.checked)
  .then(() => toast('ok', e.target.checked ? "Sekar's System Utilities will start in the tray when you sign in" : 'Removed from startup')).catch(fail));

/* ================================================================ Keyboard */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { hideCtx(); closeDrawer(); return; }
  if (e.target.matches('input, select, textarea')) return;
  if (!S.folder || !$('#view-explorer').classList.contains('active')) return;
  if (e.key === 'Backspace') { e.preventDefault(); goUp(); }
  else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    const n = S.rows.length;
    if (n) select(Math.max(0, Math.min(n - 1, S.sel + (e.key === 'ArrowDown' ? 1 : -1))), true);
  } else if (e.key === 'Enter') activate(S.rows[S.sel]);
});

/* ================================================================ Start */
$$('[data-icon]').forEach(el => el.insertAdjacentHTML('afterbegin', icon(el.dataset.icon)));
applyTheme(false);
moveInk();
renderQuick();
setMode('home');

(async () => {
  await Bridge.ready;
  if (SERVE) {
    setInterval(async () => {
      try { (await (await fetch('/api/_events')).json()).forEach(([ev, d]) => App.on(ev, d)); } catch (e) { /* server restarting */ }
    }, 300);
  }
  try {
    const info = await Bridge.call('init');
    S.cloudNote = info.cloud_note;
    S.admin = info.admin;
  } catch (e) { fail(e); }
  loadDrives();
  setAi(aiPref, false).then(renderHome);
  loadQuick();
  fetchPicks();
  loadSpecs();
  pollLive();
  loadDriverSummary();
  loadPerfSummary();
})();
