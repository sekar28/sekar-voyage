// Shared by the laptop page and the phone page.
const $ = (sel) => document.querySelector(sel);

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
}

function fmtSize(bytes) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let n = bytes, i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return (i === 0 ? n : n.toFixed(n < 10 ? 1 : 0)) + ' ' + units[i];
}

function fmtTime(seconds) {
  const d = new Date(seconds * 1000);
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (d.toDateString() === new Date().toDateString()) return time;
  return d.toLocaleDateString([], { day: 'numeric', month: 'short' }) + ', ' + time;
}

let toastTimer;
function toast(message) {
  let node = $('.toast');
  if (!node) { node = el('div', 'toast'); node.setAttribute('role', 'status'); document.body.append(node); }
  node.textContent = message;
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, 2200);
}

// navigator.clipboard needs HTTPS; the phone page is plain HTTP, so fall back.
async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return toast('Copied');
    }
  } catch (e) { /* fall through */ }
  const ta = el('textarea');
  ta.value = text;
  ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
  document.body.append(ta);
  ta.select();
  ta.setSelectionRange(0, text.length);
  let ok = false;
  try { ok = document.execCommand('copy'); } catch (e) { /* ignore */ }
  ta.remove();
  toast(ok ? 'Copied' : 'Could not copy. Press and hold the text to copy it.');
}

async function postJson(url, data) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-LapDrop': '1' },
    body: JSON.stringify(data || {}),
  });
  if (!res.ok) throw new Error('Request failed');
  return res.json();
}

function sendFile(url, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url + '?name=' + encodeURIComponent(file.name));
    xhr.setRequestHeader('X-LapDrop', '1');
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
    xhr.onload = () => {
      if (xhr.status === 200) return resolve();
      let message = 'Failed';
      try { message = JSON.parse(xhr.responseText).error || message; } catch (e) { /* ignore */ }
      reject(new Error(message));
    };
    xhr.onerror = () => reject(new Error('Connection lost'));
    xhr.send(file);
  });
}

// Sends files one after another and shows a progress row for each.
let queue = Promise.resolve();
function uploadAll(files, url, listEl, onDone) {
  for (const file of files) {
    const li = el('li');
    const item = el('div', 'item');
    const meta = el('div', 'meta', 'Waiting · ' + fmtSize(file.size));
    const bar = el('div', 'bar');
    const fill = el('i');
    bar.append(fill);
    item.append(el('div', 'name', file.name), meta, bar);
    li.append(item);
    listEl.prepend(li);
    listEl.hidden = false;
    queue = queue.then(() => sendFile(url, file, (p) => {
      fill.style.width = (p * 100).toFixed(1) + '%';
      meta.textContent = Math.round(p * 100) + '% of ' + fmtSize(file.size);
    })).then(() => {
      li.className = 'done';
      meta.textContent = 'Sent · ' + fmtSize(file.size);
      bar.remove();
      if (onDone) onDone();
    }).catch((err) => {
      li.className = 'failed';
      meta.textContent = err.message + '. Try again.';
      bar.remove();
    });
  }
}

// ---- chat

// Puts text into `node`, turning web addresses into links. Never uses innerHTML.
function linkify(node, text) {
  for (const piece of text.split(/(https?:\/\/[^\s]+)/)) {
    if (/^https?:\/\//.test(piece)) {
      const a = el('a', null, piece);
      a.href = piece; a.target = '_blank'; a.rel = 'noopener noreferrer';
      node.append(a);
    } else if (piece) {
      node.append(piece);
    }
  }
}

let chatSeen = -1;      // id of the newest message already shown
function renderChat(log, messages, myId) {
  const nearBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 60;
  log.replaceChildren();
  if (!messages.length) {
    log.append(el('p', 'empty', 'No messages yet. What you type here shows on every connected device.'));
  }
  let previous = null;
  for (const m of messages) {
    const mine = m.sender === myId;
    const row = el('div', mine ? 'msg mine' : 'msg');
    // Every message says who sent it and from where. The address is recorded by
    // the laptop from the connection itself, so it cannot be typed in or faked.
    const where = m.host ? m.host + ' (' + m.addr + ')' : (m.addr || '');
    row.append(el('div', 'who', where ? m.name + ' · ' + where : m.name));
    const bubble = el('div', 'bubble');
    linkify(bubble, m.text);
    const meta = el('div', 'meta', fmtTime(m.time) + ' · ');
    const copy = el('button', 'linkbtn', 'Copy');
    copy.type = 'button';
    copy.onclick = () => copyText(m.text);
    meta.append(copy);
    row.append(bubble, meta);
    log.append(row);
    previous = m.sender;
  }
  const newest = messages.length ? messages[messages.length - 1].id : 0;
  if (nearBottom || newest !== chatSeen) log.scrollTop = log.scrollHeight;
  // Someone else wrote while this tab was in the background: flag it in the title.
  const last = messages[messages.length - 1];
  if (chatSeen !== -1 && newest > chatSeen && last.sender !== myId && document.hidden) {
    document.title = '(new) LapDrop';
  }
  chatSeen = newest;
}
document.addEventListener('visibilitychange', () => { if (!document.hidden) document.title = 'LapDrop'; });

// The "You: name" button. Clicking it turns it into a text box; Enter or
// leaving the box saves, Escape cancels. `save(name)` stores the new name.
function setupName(button, getName, save) {
  const show = () => { button.textContent = 'You: ' + getName(); };
  show();
  button.title = 'Change the name shown on your messages';
  button.onclick = () => {
    const input = el('input', 'name-input');
    input.value = getName();
    input.maxLength = 30;
    input.setAttribute('aria-label', 'Your name in the chat');
    button.replaceWith(input);
    input.focus();
    input.select();
    let finished = false;
    const finish = (keep) => {
      if (finished) return;
      finished = true;
      const name = input.value.trim();
      if (keep && name && name !== getName()) save(name);
      input.replaceWith(button);
      show();
    };
    input.onkeydown = (e) => {
      if (e.key === 'Enter') { e.preventDefault(); finish(true); }
      if (e.key === 'Escape') finish(false);
    };
    input.onblur = () => finish(true);
  };
  return show;
}

// Wires the message box. `me` returns {id, name} for this device.
function setupChat(url, me) {
  const form = $('#chatForm');
  const box = $('#chatText');
  form.onsubmit = async (e) => {
    e.preventDefault();
    const text = box.value.trim();
    if (!text) return;
    try {
      await postJson(url, Object.assign({ text }, me()));
      box.value = '';
      box.focus();
    } catch (err) {
      toast('Not sent. Check the connection.');
    }
  };
  // Keyboards: Enter sends, Shift+Enter makes a new line. Touch screens use the Send button.
  const touch = window.matchMedia('(pointer: coarse)').matches;
  box.onkeydown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !touch) { e.preventDefault(); form.requestSubmit(); }
  };
}

// Calls `render` with fresh state every second, only when something changed.
function poll(url, render, onGone) {
  let last = '';
  async function tick() {
    try {
      const res = await fetch(url, { cache: 'no-store' });
      if (res.status === 404 && onGone) return onGone();
      if (res.ok) {
        const text = await res.text();
        if (text !== last) { last = text; render(JSON.parse(text)); }
      }
    } catch (e) { /* laptop asleep or Wi-Fi dropped: keep trying */ }
    setTimeout(tick, 1000);
  }
  tick();
  return () => { last = ''; };
}
