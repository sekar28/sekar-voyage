/* Sekar's Voyage: tiny progressive enhancement. The page works fully without this file. */
(() => {
  const root = document.documentElement;
  const header = document.querySelector('.site-header');
  const bar = document.querySelector('.progress');

  /* Scroll progress bar + condensed header (one rAF-throttled passive listener) */
  let queued = false;
  let spy = null;                       /* set below when the page has a contents rail */
  let topBtn = null;
  let topFill = null;
  const onScroll = () => {
    if (spy) spy();
    const y = window.scrollY;
    const max = root.scrollHeight - window.innerHeight;
    if (bar) bar.style.transform = `scaleX(${max > 0 ? Math.min(1, y / max) : 0})`;
    if (header) header.classList.toggle('is-scrolled', y > 8);
    if (topBtn) {
      topBtn.classList.toggle('show', y > window.innerHeight * 0.8);
      topFill.style.strokeDashoffset = String(125.66 * (1 - (max > 0 ? Math.min(1, y / max) : 0)));
    }
    queued = false;
  };
  window.addEventListener('scroll', () => {
    if (!queued) { queued = true; requestAnimationFrame(onScroll); }
  }, { passive: true });
  onScroll();

  /* Article pages: anchor links on headings, a contents rail that follows the reader */
  const heads = [...document.querySelectorAll('.prose h2')];
  if (heads.length) {
    const used = new Set();
    heads.forEach((h) => {
      let id = h.id || h.textContent.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'section';
      while (used.has(id)) id += '-2';
      used.add(id);
      h.id = id;
      const a = document.createElement('a');
      a.className = 'anchor';
      a.href = `#${id}`;
      a.setAttribute('aria-label', `Link to ${h.textContent.trim()}`);
      a.textContent = '#';
      h.appendChild(a);
    });
    const host = document.querySelector('.article-container');
    if (host && heads.length > 2) {
      const toc = document.createElement('aside');
      toc.className = 'toc';
      toc.setAttribute('aria-label', 'On this page');
      toc.innerHTML = '<div class="toc-inner"><p>On this page</p></div>';
      const links = heads.map((h) => {
        const a = document.createElement('a');
        a.href = `#${h.id}`;
        a.textContent = h.firstChild.textContent.trim();
        toc.firstChild.appendChild(a);
        return a;
      });
      host.appendChild(toc);
      /* Current section = the last heading that has passed the reading line (30% down the screen) */
      spy = () => {
        let current = -1;
        heads.forEach((h, i) => { if (h.getBoundingClientRect().top <= window.innerHeight * 0.3) current = i; });
        links.forEach((l, i) => l.classList.toggle('on', i === current));
      };
      spy();
    }
  }

  /* Screenshot viewer: wraps each figure image in a button and opens it in a native <dialog> */
  const shots = [...document.querySelectorAll('.post-figure img')];
  if (shots.length && typeof HTMLDialogElement === 'function') {
    const dlg = document.createElement('dialog');
    dlg.className = 'lightbox';
    dlg.setAttribute('aria-label', 'Screenshot viewer');
    dlg.innerHTML = '<figure><img alt=""><figcaption></figcaption></figure>' +
      '<button class="lb-btn lb-close" type="button" aria-label="Close">&times;</button>' +
      '<button class="lb-btn lb-prev" type="button" aria-label="Previous screenshot">&lsaquo;</button>' +
      '<button class="lb-btn lb-next" type="button" aria-label="Next screenshot">&rsaquo;</button>' +
      '<span class="lb-count" aria-live="polite"></span>';
    document.body.appendChild(dlg);
    const big = dlg.querySelector('img');
    const cap = dlg.querySelector('figcaption');
    const count = dlg.querySelector('.lb-count');
    let at = 0;
    let opener = null;
    const show = (i) => {
      at = (i + shots.length) % shots.length;
      const src = shots[at];
      big.src = src.currentSrc || src.src;
      big.alt = src.alt;
      cap.textContent = src.closest('figure').querySelector('figcaption')?.textContent || src.alt;
      count.textContent = `${at + 1} / ${shots.length}`;
      [at - 1, at + 1].forEach((n) => { const s = shots[(n + shots.length) % shots.length]; new Image().src = s.currentSrc || s.src; });
    };
    shots.forEach((img, i) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'zoom';
      btn.setAttribute('aria-label', `Enlarge screenshot: ${img.alt}`);
      img.parentNode.insertBefore(btn, img);
      btn.appendChild(img);
      btn.addEventListener('click', () => { opener = btn; show(i); dlg.showModal(); document.body.classList.add('lb-open'); });
    });
    const cleanUp = () => { document.body.classList.remove('lb-open'); if (opener) opener.focus(); };
    const shut = () => { dlg.close(); cleanUp(); };
    dlg.querySelector('.lb-close').addEventListener('click', shut);
    dlg.querySelector('.lb-prev').addEventListener('click', () => show(at - 1));
    dlg.querySelector('.lb-next').addEventListener('click', () => show(at + 1));
    dlg.addEventListener('click', (e) => { if (e.target === dlg) shut(); });
    dlg.addEventListener('close', cleanUp);          /* Escape closes through the browser, so listen for it too */
    dlg.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') show(at - 1);
      if (e.key === 'ArrowRight') show(at + 1);
    });
    let x0 = null;
    dlg.addEventListener('touchstart', (e) => { x0 = e.changedTouches[0].clientX; }, { passive: true });
    dlg.addEventListener('touchend', (e) => {
      if (x0 === null) return;
      const dx = e.changedTouches[0].clientX - x0;
      x0 = null;
      if (Math.abs(dx) > 50) show(at + (dx < 0 ? 1 : -1));
    }, { passive: true });
  }

  /* Back to top, with a progress ring */
  topBtn = document.createElement('button');
  topBtn.type = 'button';
  topBtn.className = 'to-top';
  topBtn.setAttribute('aria-label', 'Back to top');
  topBtn.innerHTML = '<svg viewBox="0 0 48 48" aria-hidden="true"><circle class="track" cx="24" cy="24" r="20"/><circle class="fill" cx="24" cy="24" r="20"/></svg>' +
    '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 14l6-6 6 6"/></svg>';
  topFill = topBtn.querySelector('.fill');
  topBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }));
  document.body.appendChild(topBtn);
  onScroll();

  /* Nav: mark the section in view (home page) or the section the story belongs to */
  const navLinks = [...document.querySelectorAll('.nav nav a')];
  const secLinks = navLinks.filter((a) => a.hash && a.pathname === location.pathname);
  if (secLinks.length) {
    const secs = secLinks.map((a) => document.querySelector(a.hash)).filter(Boolean);
    const markNav = () => {
      let cur = null;
      secs.forEach((s) => { if (s.getBoundingClientRect().top <= window.innerHeight * 0.35) cur = s.id; });
      secLinks.forEach((a) => (a.hash === `#${cur}` ? a.setAttribute('aria-current', 'location') : a.removeAttribute('aria-current')));
    };
    const prior = spy;
    spy = () => { if (prior) prior(); markNav(); };
    spy();
  } else {
    const here = navLinks.find((a) => a.hash === '#projects');
    if (here && location.pathname.includes('/projects/')) here.setAttribute('aria-current', 'true');
  }

  /* Hero: rotating keyword, pointer parallax (only where motion and a mouse are available) */
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const hero = document.querySelector('.hero');
  const word = hero && hero.querySelector('.accent');
  if (word && !calm) {
    const words = ['security', 'your PC', 'your desk'];
    let n = 0;
    let hold = false;
    hero.addEventListener('pointerenter', () => { hold = true; });
    hero.addEventListener('pointerleave', () => { hold = false; });
    hero.addEventListener('focusin', () => { hold = true; });
    hero.addEventListener('focusout', () => { hold = false; });
    setInterval(() => {
      if (hold || document.hidden) return;
      word.classList.add('out');
      setTimeout(() => { n = (n + 1) % words.length; word.textContent = words[n]; word.classList.remove('out'); }, 360);
    }, 3400);
  }
  if (hero && !calm && matchMedia('(hover: hover) and (pointer: fine)').matches) {
    let pending = false;
    hero.addEventListener('pointermove', (e) => {
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => {
        const r = hero.getBoundingClientRect();
        hero.style.setProperty('--px', ((e.clientX - r.left) / r.width - 0.5).toFixed(3));
        hero.style.setProperty('--py', ((e.clientY - r.top) / r.height - 0.5).toFixed(3));
        pending = false;
      });
    }, { passive: true });
    hero.addEventListener('pointerleave', () => { hero.style.setProperty('--px', 0); hero.style.setProperty('--py', 0); });
  }

  /* Copy the contact address, with a polite status message for screen readers too */
  const copyBtn = document.querySelector('[data-copy]');
  if (copyBtn) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.setAttribute('role', 'status');
    document.body.appendChild(toast);
    let timer = 0;
    const say = (msg) => {
      toast.textContent = msg;
      toast.classList.add('show');
      clearTimeout(timer);
      timer = setTimeout(() => toast.classList.remove('show'), 2600);
    };
    copyBtn.addEventListener('click', async () => {
      const mail = document.querySelector('[data-email]').textContent.trim();
      const legacyCopy = () => {
        const box = document.createElement('textarea');
        box.value = mail;
        box.setAttribute('readonly', '');
        box.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
        document.body.appendChild(box);
        box.select();
        const ok = document.execCommand('copy');
        box.remove();
        return ok;
      };
      try {
        await navigator.clipboard.writeText(mail);
        say('Address copied');
      } catch (e) {
        try { say(legacyCopy() ? 'Address copied' : 'Could not copy. The address is shown above.'); }
        catch (e2) { say('Could not copy. The address is shown above.'); }
      }
    });
  }

  /* Pause endless animations while their section is off-screen */
  if ('IntersectionObserver' in window) {
    const watch = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) e.target.removeAttribute('data-offscreen'); else e.target.setAttribute('data-offscreen', ''); });
    }, { rootMargin: '80px' });
    document.querySelectorAll('.hero, #demo, #about, .site-footer').forEach((el) => watch.observe(el));
  }

  /* Demo loop: a visible pause control (people must be able to stop moving content) */
  const demo = document.querySelector('.demo');
  const demoBtn = demo && demo.querySelector('.demo-toggle');
  if (demoBtn) {
    demoBtn.addEventListener('click', () => {
      const paused = demo.classList.toggle('paused');
      demoBtn.setAttribute('aria-pressed', String(paused));
      demoBtn.textContent = paused ? 'Play demo' : 'Pause demo';
    });
  }

  /* Warm up the next page: prefetch same-site links when the pointer arrives or a finger lands */
  const warmed = new Set();
  const warm = (e) => {
    const a = e.target.closest && e.target.closest('a[href]');
    if (!a || a.origin !== location.origin || a.target === '_blank' || a.hasAttribute('download')) return;
    const url = a.href.split('#')[0];
    if (url === location.href.split('#')[0] || warmed.has(url)) return;
    warmed.add(url);
    const l = document.createElement('link');
    l.rel = 'prefetch';
    l.href = url;
    document.head.appendChild(l);
  };
  document.addEventListener('pointerover', warm, { passive: true });
  document.addEventListener('touchstart', warm, { passive: true });

  /* Primary buttons lean a few pixels toward the pointer (mouse only) */
  if (matchMedia('(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)').matches) {
    document.querySelectorAll('.btn:not(.btn-ghost), .download').forEach((b) => {
      b.addEventListener('pointermove', (e) => {
        const r = b.getBoundingClientRect();
        const x = ((e.clientX - r.left) / r.width - 0.5) * 8;
        const y = ((e.clientY - r.top) / r.height - 0.5) * 6;
        b.style.transform = `translate(${x}px, ${y - 2}px)`;
      });
      b.addEventListener('pointerleave', () => { b.style.transform = ''; });
    });
  }

  /* Mobile menu: closes on Escape, on a tap outside, and after choosing a link */
  const menuBtn = document.querySelector('.menu-toggle');
  if (menuBtn && header) {
    const setOpen = (open) => {
      header.classList.toggle('nav-open', open);
      menuBtn.setAttribute('aria-expanded', String(open));
    };
    menuBtn.addEventListener('click', () => setOpen(!header.classList.contains('nav-open')));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setOpen(false); });
    document.addEventListener('click', (e) => { if (!header.contains(e.target)) setOpen(false); });
    header.querySelectorAll('nav a').forEach((a) => a.addEventListener('click', () => setOpen(false)));
  }

  /* Theme toggle: remembers the choice (the early script in <head> applies it before first paint) */
  const toggle = document.querySelector('.theme-toggle');
  if (toggle) {
    const dark = () => root.dataset.theme === 'dark' || (!root.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);
    const sync = () => toggle.setAttribute('aria-pressed', String(dark()));
    sync();
    toggle.addEventListener('click', () => {
      const next = dark() ? 'light' : 'dark';
      root.dataset.theme = next;
      try { localStorage.setItem('theme', next); } catch (e) { /* private mode: the choice just isn't kept */ }
      sync();
    });
  }

  /* Fade lazy images in once they have loaded */
  document.querySelectorAll('img[loading="lazy"]').forEach((img) => {
    const done = () => img.classList.add('loaded');
    if (img.complete && img.naturalWidth) done();
    else { img.addEventListener('load', done, { once: true }); img.addEventListener('error', done, { once: true }); }
  });

  /* Card spotlight follows the pointer (mouse and pen only) */
  document.querySelectorAll('.card').forEach((card) => {
    card.addEventListener('pointermove', (e) => {
      if (e.pointerType === 'touch') return;
      const b = card.getBoundingClientRect();
      card.style.setProperty('--mx', `${e.clientX - b.left}px`);
      card.style.setProperty('--my', `${e.clientY - b.top}px`);
    }, { passive: true });
  });

  /* Reveal on scroll, staggered within each parent */
  const items = document.querySelectorAll('[data-reveal]');
  if (!('IntersectionObserver' in window)) { items.forEach((el) => el.classList.add('in')); return; }
  const seen = new Map();
  items.forEach((el) => {
    const n = seen.get(el.parentNode) || 0;
    seen.set(el.parentNode, n + 1);
    el.style.setProperty('--d', `${Math.min(n, 5) * 80}ms`);
  });
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  items.forEach((el) => io.observe(el));
})();
