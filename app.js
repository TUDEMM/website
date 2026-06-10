/* TUDEMM — shared interactions */
(function () {
  // Theme toggle
  const toggle = document.querySelector('[data-theme-toggle]');
  const root = document.documentElement;
  let mode = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  root.setAttribute('data-theme', mode);
  const sun =
    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  const moon =
    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg>';
  function paint() {
    if (toggle) toggle.innerHTML = mode === 'dark' ? sun : moon;
  }
  paint();
  if (toggle) {
    toggle.addEventListener('click', function () {
      mode = mode === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', mode);
      toggle.setAttribute('aria-label', 'Switch to ' + (mode === 'dark' ? 'light' : 'dark') + ' mode');
      paint();
    });
  }

  // Mobile menu
  const navToggle = document.querySelector('[data-nav-toggle]');
  const mobileMenu = document.querySelector('.mobile-menu');
  if (navToggle && mobileMenu) {
    navToggle.addEventListener('click', function () {
      const open = mobileMenu.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    mobileMenu.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        mobileMenu.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  // Header shadow on scroll
  const header = document.querySelector('.header');
  if (header) {
    const onScroll = function () {
      header.classList.toggle('header--scrolled', window.scrollY > 8);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  // Scroll reveal
  const reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && reveals.length) {
    const io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) {
            e.target.classList.add('in');
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -8% 0px' }
    );
    reveals.forEach(function (el) {
      io.observe(el);
    });
  } else {
    reveals.forEach(function (el) {
      el.classList.add('in');
    });
  }

  // Contact form — posts to the TUDEMM backend, which saves every
  // submission immediately. Works locally and once deployed via the proxy.
  const API = '__PORT_8000__'.startsWith('__') ? 'http://localhost:8000' : '__PORT_8000__';
  const form = document.querySelector('[data-contact-form]');
  if (form) {
    const fields = form.querySelector('[data-form-fields]');
    const success = form.querySelector('.form-success');
    const errorEl = form.querySelector('[data-form-error]');
    const btn = form.querySelector('[data-submit-btn]');
    const btnLabel = form.querySelector('[data-btn-label]');

    function showError(msg) {
      if (!errorEl) return;
      errorEl.textContent = msg;
      errorEl.hidden = false;
    }
    function clearError() {
      if (!errorEl) return;
      errorEl.hidden = true;
      errorEl.textContent = '';
    }

    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      clearError();

      const data = new FormData(form);
      const payload = {
        name: (data.get('name') || '').toString().trim(),
        email: (data.get('email') || '').toString().trim(),
        company: (data.get('company') || '').toString().trim(),
        service: (data.get('service') || '').toString().trim(),
        message: (data.get('message') || '').toString().trim(),
      };

      // Lightweight client-side guard before hitting the server.
      if (!payload.name || !payload.email || !payload.message) {
        showError('Please fill in your name, email, and message.');
        return;
      }

      if (btn) btn.disabled = true;
      if (btnLabel) btnLabel.textContent = 'Sending\u2026';

      try {
        const res = await fetch(`${API}/api/contact`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const result = await res.json().catch(function () { return {}; });

        if (!res.ok) {
          let msg = 'Something went wrong. Please try again or email info@tudemm.com.';
          if (result && result.detail) {
            msg = Array.isArray(result.detail)
              ? (result.detail[0] && result.detail[0].msg) || msg
              : result.detail;
          }
          showError(msg);
          if (btn) btn.disabled = false;
          if (btnLabel) btnLabel.textContent = 'Send inquiry';
          return;
        }

        if (fields && success) {
          fields.style.display = 'none';
          success.style.display = 'flex';
        }
      } catch (err) {
        showError('We could not reach the server. Please try again, or email info@tudemm.com.');
        if (btn) btn.disabled = false;
        if (btnLabel) btnLabel.textContent = 'Send inquiry';
      }
    });
  }

  // Footer year
  const yr = document.querySelector('[data-year]');
  if (yr) yr.textContent = new Date().getFullYear();
})();
