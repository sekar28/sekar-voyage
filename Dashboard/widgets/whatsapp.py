"""Read the chat list from the dashboard's own WhatsApp Web window (read-only: it never clicks or types).

WhatsApp has no API for personal accounts, so this reads what the page already shows - chat names, unread
badges and the last-message previews - using accessibility attributes, which change less often than class names.
If WhatsApp changes its page, read() reports state "unreadable" instead of failing."""

READ_JS = r"""
(() => {
  const pane = document.querySelector('#pane-side');
  if (!pane) {
    const qr = document.querySelector('canvas[aria-label], [data-ref], div[data-testid="qrcode"]');
    return { state: qr ? 'qr' : 'loading', chats: [] };
  }
  const rows = pane.querySelectorAll('[role="listitem"], [role="row"]');
  const chats = [];
  for (const row of rows) {
    const titles = [...row.querySelectorAll('span[title]')].map(s => s.getAttribute('title')).filter(Boolean);
    if (!titles.length) continue;
    let unread = 0;
    for (const el of row.querySelectorAll('[aria-label]')) {
      const m = /(\d+)\s+unread message/i.exec(el.getAttribute('aria-label') || '');
      if (m) { unread = parseInt(m[1], 10); break; }
    }
    const lines = (row.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
    const time = lines.find(l => /^(\d{1,2}:\d{2}(\s?[ap]m)?|yesterday|today|\d{1,2}\/\d{1,2}\/\d{2,4}|monday|tuesday|wednesday|thursday|friday|saturday|sunday)$/i.test(l)) || '';
    const preview = titles.length > 1 ? titles[titles.length - 1]
      : (lines.filter(l => l !== titles[0] && l !== time && !/^\d+$/.test(l)).pop() || '');
    chats.push({ name: titles[0], preview, unread, time });
    if (chats.length >= 30) break;
  }
  return { state: chats.length ? 'ok' : (rows.length ? 'unreadable' : 'loading'), chats };
})()
"""


def read(window):
    try:
        result = window.evaluate_js(READ_JS)
    except Exception as e:
        return {"state": "unreadable", "chats": [], "error": str(e)}
    if not isinstance(result, dict):
        return {"state": "unreadable", "chats": []}
    result["chats"] = [c for c in result.get("chats") or [] if isinstance(c, dict) and c.get("name")]
    return result


def spoken(result):
    unread = [c for c in result.get("chats", []) if c.get("unread")]
    if result.get("state") == "qr":
        return "WhatsApp isn't linked yet. Say open WhatsApp and scan the code with your phone."
    if result.get("state") != "ok":
        return "I can't read WhatsApp right now. Try opening it."
    if not unread:
        return "No unread WhatsApp messages."
    parts = [f"{c['name']}: {c['preview']}" if c.get("preview") else c["name"] for c in unread[:5]]
    head = f"{len(unread)} unread chat{'s' if len(unread) != 1 else ''}. "
    return head + ". ".join(parts) + ("." if len(unread) <= 5 else f". And {len(unread) - 5} more.")
