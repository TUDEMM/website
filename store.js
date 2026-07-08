/* TUDEMM storefront — renders products from /api/products and starts
   Stripe Checkout via /api/checkout. Prices are display-only here; the
   server re-validates the real price, so the cart cannot be tampered with. */
(function () {
  'use strict';

  function money(cents) {
    return '$' + (cents / 100).toFixed(cents % 100 === 0 ? 0 : 2);
  }

  function card(p) {
    const badge = p.badge
      ? `<span class="product-badge">${p.badge}</span>` : '';
    const compare = p.compare_at_cents
      ? `<small>${money(p.compare_at_cents)}</small>` : '';
    return `
      <article class="product reveal in">
        <div class="product-cover">
          ${badge}
          <img src="../assets/${p.cover}" alt="E-book cover: ${p.name}" loading="lazy" />
        </div>
        <span class="product-cat">${p.category}</span>
        <h3>${p.name}</h3>
        <p>${p.description}</p>
        <div class="product-foot">
          <span class="product-price">${money(p.price_cents)}${compare}</span>
          <button class="btn btn-primary" type="button" data-buy="${p.id}">Get it</button>
        </div>
      </article>`;
  }

  async function startCheckout(productId, btn) {
    const original = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Loading…';
    try {
      const res = await fetch('/api/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.url) {
        window.location.href = data.url; // Stripe-hosted secure checkout
        return;
      }
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
    const grid = document.querySelector('[data-products-grid]');
    if (!grid) return;
    try {
      const res = await fetch('/api/products');
      const data = await res.json();
      if (data.products && data.products.length) {
        grid.innerHTML = data.products.map(card).join('');
        bindButtons(grid);
        return;
      }
    } catch (e) { /* fall through to existing static buttons */ }
    // Fallback: if the API isn't available, wire any pre-rendered buttons.
    bindButtons(document);
  });
})();
