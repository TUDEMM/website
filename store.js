/* TUDEMM storefront — renders products from /api/products and sends buyers to
   Stripe Checkout (redirect to the Stripe-hosted payment page).
   Prices are display-only here; the server re-validates the real price from
   data/products.json, so the amount charged cannot be tampered with. */
(function () {
  'use strict';

  function money(cents) {
    return '$' + (cents / 100).toFixed(cents % 100 === 0 ? 0 : 2);
  }

  /* Detail-page URL for a product. The server sends `slug`; fall back to the id
     so the grid still links somewhere sane if a slug is ever missing. */
  function detailUrl(p) {
    return '/ebooks/' + (p.slug || p.id);
  }

  function card(p) {
    var badge = p.badge ? '<span class="product-badge">' + p.badge + '</span>' : '';
    var compare = p.compare_at_cents ? '<small>' + money(p.compare_at_cents) + '</small>' : '';
    var href = detailUrl(p);
    return '' +
      '<article class="product reveal in">' +
        '<a class="product-cover" href="' + href + '" aria-label="' + p.name + ' — details">' + badge +
          '<img src="/assets/' + p.cover + '" alt="E-book cover: ' + p.name + '" loading="lazy" />' +
        '</a>' +
        '<span class="product-cat">' + p.category + '</span>' +
        '<h3><a href="' + href + '">' + p.name + '</a></h3>' +
        '<p>' + p.description + '</p>' +
        '<div class="product-foot">' +
          '<span class="product-price">' + money(p.price_cents) + compare + '</span>' +
          '<div class="product-actions">' +
            '<a class="btn btn-ghost" href="' + href + '">Details</a>' +
            '<button class="btn btn-primary" type="button" data-buy="' + p.id + '">Get it</button>' +
          '</div>' +
        '</div>' +
      '</article>';
  }

  /* ---------- Stripe Checkout ---------- */
  async function startCheckout(productId, btn) {
    var original = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Loading…';
    try {
      var res = await fetch('/api/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId }),
      });
      var data = await res.json().catch(function () { return {}; });
      if (res.ok && data.url) { window.location.href = data.url; return; }
      alert(data.error || 'Sorry, checkout is unavailable right now. Please try again.');
    } catch (e) {
      alert('We could not reach checkout. Please try again, or email info@tudemm.com.');
    }
    btn.disabled = false;
    btn.textContent = original;
  }

  function bindButtons(root) {
    root.querySelectorAll('[data-buy]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        startCheckout(btn.getAttribute('data-buy'), btn);
      });
    });
  }

  document.addEventListener('DOMContentLoaded', async function () {
    var grid = document.querySelector('[data-products-grid]');

    /* Single-product detail pages (/ebooks/*) ship their buy button in static
       HTML for SEO, so there is no grid to render — just wire it up. */
    if (!grid) {
      bindButtons(document);
      return;
    }

    try {
      var res = await fetch('/api/products');
      var data = await res.json();
      if (data.products && data.products.length) {
        grid.innerHTML = data.products.map(card).join('');
        bindButtons(grid);
        return;
      }
    } catch (e) { /* fall through to whatever static buttons exist */ }
    bindButtons(document);
  });
})();
