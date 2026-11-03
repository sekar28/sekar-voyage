/* Widget SDK - put inline into every generated widget's sandboxed frame (see widgetsmith.frame_html).
   The frame has an opaque origin and no network access; everything goes through the dashboard over postMessage. */
(() => {
  'use strict';
  const cfg = window.__WIDGET__ || {};
  const pending = new Map();
  let seq = 0, refreshFn = null, resizeFn = null, summaryFn = null, isReady = false, lastSize = null;

  const send = (type, data = {}) => parent.postMessage({ __w: 1, type, ...data }, '*');
  const call = (type, data = {}) => new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    send(type, { id, ...data });
    setTimeout(() => { if (pending.delete(id)) reject(new Error('The dashboard did not answer in time.')); }, 30000);
  });

  addEventListener('message', async e => {
    if (e.source !== parent) return;
    const m = e.data;
    if (!m || m.__w !== 1) return;
    if (m.type === 'reply') {
      const p = pending.get(m.id);
      if (!p) return;
      pending.delete(m.id);
      m.error ? p.reject(new Error(m.error)) : p.resolve(m.value);
    } else if (m.type === 'refresh') {
      try { refreshFn && await refreshFn(); } catch (err) { report(err); }
    } else if (m.type === 'resize') {
      lastSize = m.size;
      try { resizeFn && resizeFn(m.size); } catch (err) { report(err); }
    } else if (m.type === 'summary') {
      let text = '';
      try { text = summaryFn ? String(await summaryFn() || '') : (document.body.innerText || '').trim().slice(0, 300); }
      catch (err) { report(err); }
      send('summary', { req: m.req, text: text.slice(0, 600) });
    } else if (m.type === 'probe') {
      send('probe', { req: m.req, ready: isReady, textLength: (document.body.innerText || '').trim().length,
        nodes: document.body.querySelectorAll('*').length, svg: document.querySelectorAll('svg, canvas, img').length });
    }
  });

  const report = err => send('error', { message: String((err && err.message) || err).slice(0, 500) });
  addEventListener('error', e => send('error', {
    message: `${e.message || 'Script error'}${e.lineno ? ` (line ${e.lineno})` : ''}`.slice(0, 500) }));
  addEventListener('unhandledrejection', e => report(e.reason));
  addEventListener('securitypolicyviolation', e => send('error', {
    message: `Blocked by the sandbox: ${e.violatedDirective} ${e.blockedURI || ''}`.slice(0, 500) }));

  window.Widget = Object.freeze({
    id: cfg.id,
    async fetch(url, opts = {}) {
      const r = await call('fetch', { url: String(url), opts: { method: opts.method, headers: opts.headers, body: opts.body } });
      if (r.status >= 400) throw new Error(`${new URL(String(url)).hostname} answered ${r.status}`);
      if (opts.json === false) return r.text;
      try { return JSON.parse(r.text); } catch { throw new Error(`${new URL(String(url)).hostname} didn't send JSON`); }
    },
    store: Object.freeze({
      get: key => call('store', { op: 'get', key: String(key) }),
      set: (key, value) => call('store', { op: 'set', key: String(key), value: value === undefined ? null : value }),
    }),
    say(text) { send('say', { text: String(text).slice(0, 300) }); },
    onRefresh(fn) { refreshFn = fn; },
    onResize(fn) { resizeFn = fn; if (lastSize) { try { fn(lastSize); } catch (err) { report(err); } } },
    summary(fn) { summaryFn = fn; },
    ready() { if (!isReady) { isReady = true; send('ready'); } },
    error(message) { report(message); },
  });
  send('hello');
})();
