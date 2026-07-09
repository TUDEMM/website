/* TUDEMM storefront — renders products from /api/products and offers two
   secure payment paths:
     1) Stripe Checkout  (redirect to Stripe-hosted page)
     2) PayPal           (in-page PayPal buttons, order created + captured
                          server-side)
   Prices are display-only here; the server re-validates the real price for
   BOTH methods, so the amount charged cannot be tampered with. */
(function () {
  'use strict';

  var PAYPAL = { clientId: '', env: 'sandbox', sdkLoading: null };

  function money(cents) {
    return '$' + (cents / 100).toFixed(cents % 100 === 0 ? 0 : 2);
  }

  function card(p) {
    var badge = p.badge ? '<span class="product-badge">' + p.badge + '</span>' : '';
    var compare = p.compare_at_cents ? '<small>' + money(p.compare_at_cents) + '</small>' : '';
    var paypalBtn = PAYPAL.clientId
      ? '<button class="btn btn-ghost btn-paypal" type="button" data-paypal="' + p.id +
        '" aria-label="Pay with PayPal">PayPal</button>'
      : '';
    return '' +
      '<article class="product reveal in">' +
        '<div class="product-cover">' + badge +
          '<img src="../assets/' + p.cover + '" alt="E-book cover: ' + p.name + '" loading="lazy" />' +
        '</div>' +
        '<span class="product-cat">' + p.category + '</span>' +
        '<h3>' + p.name + '</h3>' +
        '<p>' + p.description + '</p>' +
        '<div class="product-foot">' +
          '<span class="product-price">' + money(p.price_cents) + compare + '</span>' +
          '<div class="product-actions">' +
            '<button class="btn btn-primary" type="button" data-buy="' + p.id + '">Get it</button>' +
            paypalBtn +
          '</div>' +
        '</div>' +
      '</article>';
  }

  /* ---------- Stripe path (unchanged) ---------- */
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

  /* ---------- PayPal path ---------- */
  function loadPayPalSdk() {
    if (PAYPAL.sdkLoading) return PAYPAL.sdkLoading;
    PAYPAL.sdkLoading = new Promise(function (resolve, reject) {
      if (window.paypal) { resolve(window.paypal); return; }
      var s = document.createElement('script');
      var cur = 'USD';
      s.src = 'https://www.paypal.com/sdk/js?client-id=' +
        encodeURIComponent(PAYPAL.clientId) + '&currency=' + cur + '&intent=capture';
      s.onload = function () { resolve(window.paypal); };
      s.onerror = function () { reject(new Error('PayPal SDK failed to load')); };
      document.head.appendChild(s);
    });
    return PAYPAL.sdkLoading;
  }

  function openPayPalModal(productId, productName) {
    var overlay = document.createElement('div');
    overlay.className = 'pp-overlay';
    overlay.innerHTML =
      '<div class="pp-modal" role="dialog" aria-modal="true" aria-label="Pay with PayPal">' +
        '<button class="pp-close" aria-label="Close">&times;</button>' +
        '<h4>Checkout with PayPal</h4>' +
        '<p class="pp-item">' + productName + '</p>' +
        '<div class="pp-buttons" id="pp-buttons"></div>' +
        '<p class="pp-note">You\'ll get a secure download link by email after payment.</p>' +
      '</div>';
    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';

    function close() {
      document.body.style.overflow = '';
      overlay.remove();
    }
    overlay.querySelector('.pp-close').addEventListener('click', close);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });

    loadPayPalSdk().then(function (paypal) {
      paypal.Buttons({
        style: { layout: 'vertical', color: 'gold', shape: 'pill', label: 'paypal' },
        createOrder: function () {
          return fetch('/api/paypal_create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId }),
          }).then(function (r) { return r.json(); }).then(function (d) {
            if (!d.id) throw new Error(d.error || 'Could not start PayPal order');
            return d.id;
          });
        },
        onApprove: function (data) {
          return fetch('/api/paypal_capture', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_id: data.orderID }),
          }).then(function (r) { return r.json(); }).then(function (d) {
            if (d.status === 'COMPLETED') {
              close();
              window.location.href = '/pages/success.html?paypal=' +
                encodeURIComponent(data.orderID);
            } else {
              alert(d.error || 'Payment could not be completed.');
            }
          });
        },
        onError: function () {
          alert('Something went wrong with PayPal. Please try again, or use card checkout.');
        },
      }).render('#pp-buttons');
    }).catch(function () {
      var box = overlay.querySelector('#pp-buttons');
      if (box) box.innerHTML = '<p class="pp-note">PayPal is unavailable right now. Please use card checkout.</p>';
    });
  }

  function bindButtons(root) {
    root.querySelectorAll('[data-buy]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        startCheckout(btn.getAttribute('data-buy'), btn);
      });
    });
    root.querySelectorAll('[data-paypal]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var article = btn.closest('article');
        var nameEl = article ? article.querySelector('h3') : null;
        openPayPalModal(btn.getAttribute('data-paypal'), nameEl ? nameEl.textContent : 'Your e-book');
      });
    });
  }

  document.addEventListener('DOMContentLoaded', async function () {
    var grid = document.querySelector('[data-products-grid]');
    if (!grid) return;
    try {
      var res = await fetch('/api/products');
      var data = await res.json();
      PAYPAL.clientId = data.paypal_client_id || '';
      PAYPAL.env = data.paypal_env || 'sandbox';
      if (data.products && data.products.length) {
        grid.innerHTML = data.products.map(card).join('');
        bindButtons(grid);
        return;
      }
    } catch (e) { /* fall through to existing static buttons */ }
    bindButtons(document);
  });
})();
