# TUDEMM LLC — Website (Vercel-ready)

Marketing site **and e-book store** for TUDEMM LLC — digital products,
professional web development, and SEO services. Static HTML/CSS/JS with
serverless functions for the contact form and a secure Stripe checkout that
delivers e-books by email after payment.

## Project structure

```
.
├── index.html              Home page
├── pages/                  About, Contact, Products, SEO, Web Development
│   └── success.html        Post-purchase "thank you" page
├── style.css, base.css     Styles
├── app.js                  Front-end behavior + contact form submission
├── store.js                Storefront: renders products, starts Stripe checkout
├── assets/                 Images (e-book covers, hero art)
├── data/
│   ├── products.json       Product catalog (prices, file keys) — EDIT THIS
│   └── ebooks/             Placeholder — real PDFs go in private storage
├── api/
│   ├── contact.py          Serverless — contact form email
│   ├── products.py         Serverless — public catalog (no file keys)
│   ├── checkout.py         Serverless — creates a Stripe Checkout Session
│   ├── webhook.py          Serverless — Stripe webhook → emails download link
│   ├── download.py         Serverless — validates token → serves the file
│   └── _lib/store.py       Shared: catalog lookup + signed download tokens
├── vercel.json             Vercel config (clean URLs)
└── requirements.txt        Python deps (stripe)
```

---

## Part A — Contact form (already working)

The form on `/pages/contact.html` POSTs to `/api/contact`, which validates input
and emails it to your inbox via [Resend](https://resend.com). Env vars:

| Name             | Value                                    |
| ---------------- | ---------------------------------------- |
| `RESEND_API_KEY` | your Resend key (`re_...`)               |
| `CONTACT_TO`     | `info.tudemm@gmail.com`                  |
| `CONTACT_FROM`   | `TUDEMM <info@tudemm.com>` once domain is verified, else `onboarding@resend.dev` |

---

## Part B — Secure e-book checkout (new)

### How it works (the security model)

1. The products page loads the catalog from `/api/products` (prices and covers,
   **never** the file location).
2. When a buyer clicks **Buy**, the browser sends only the `product_id` to
   `/api/checkout`. The server looks up the real price from `data/products.json`
   and creates a Stripe Checkout Session — so the amount charged **cannot be
   tampered with** in the browser.
3. The buyer pays on **Stripe's** hosted page (Stripe handles all card data —
   you are never PCI-exposed).
4. Stripe calls `/api/webhook`. The signature is verified (so no one can fake a
   "paid" event), then the buyer is emailed a **secure, expiring download link**.
5. The link points to `/api/download?token=...`. The token is HMAC-signed and
   expires (default 24h), so paid files can't be guessed, forged, or shared
   forever. A valid token redirects to the file in your private storage.

### Step 1 — Add your e-books to the catalog

Edit `data/products.json`. It ships with 3 sample products; add the rest up to
~50. Each entry:

```json
{
  "id": "unique-slug",                       // URL-safe, no spaces
  "name": "The Book Title",
  "category": "Growth · E-book",
  "description": "One or two sentences.",
  "price_cents": 1900,                        // $19.00 — integer cents only
  "compare_at_cents": 2900,                   // optional strikethrough price, or null
  "cover": "ebook1.png",                      // file in /assets
  "file_key": "unique-slug.pdf",              // the PDF's name in private storage
  "badge": "New"                              // optional: "Bestseller", "New", or null
}
```

Add each cover image to `/assets/`. **Adding products is just JSON + an image —
no HTML changes needed.** The grid renders itself from `/api/products`.

### Step 2 — Put the actual PDF files in private storage

The PDFs must **not** live in the public repo. Use any private file host that
serves files over HTTPS, for example:

- **Vercel Blob** (simplest if you're already on Vercel) — upload your PDFs and
  use the base URL.
- **AWS S3 / Cloudflare R2 / Backblaze B2** private bucket.

Upload all PDFs there, named exactly to match each `file_key` (e.g.
`unique-slug.pdf`). The base URL becomes your `FILES_BASE_URL` env var; the
download function appends `/{file_key}`.

> The files in `data/ebooks/` are placeholders only — they are not served.

### Step 3 — Get your Stripe secret key

1. Create a [Stripe account](https://dashboard.stripe.com) and activate it.
2. **Developers → API keys** → copy the **Secret key** (`sk_test_...` while
   testing, `sk_live_...` when ready for real money).
3. You do **not** need to create products in the Stripe dashboard — `checkout.py`
   builds each line item on the fly from `products.json`.

### Step 4 — Set environment variables on Vercel

Vercel → project → **Settings → Environment Variables**. Add these on top of the
contact-form vars from Part A:

| Name                   | Value / example                                              |
| ---------------------- | ------------------------------------------------------------ |
| `STRIPE_SECRET_KEY`    | `sk_live_...` (or `sk_test_...` while testing)               |
| `STRIPE_WEBHOOK_SECRET`| `whsec_...` (from Step 5)                                    |
| `DOWNLOAD_SECRET`      | a long random string you make up (signs download links)      |
| `SITE_URL`             | `https://tudemm.com`                                         |
| `FILES_BASE_URL`       | base URL of your private PDF storage (no trailing slash)     |
| `DOWNLOAD_TTL_SECONDS` | optional — link lifetime in seconds (default `86400` = 24h)  |

Tip for `DOWNLOAD_SECRET`: run `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

The webhook reuses your existing `RESEND_API_KEY` and `CONTACT_FROM` to send the
delivery email, so make sure those are set too.

### Step 5 — Create the Stripe webhook

1. Deploy the site once so the function exists, then in Stripe go to
   **Developers → Webhooks → Add endpoint**.
2. Endpoint URL: `https://tudemm.com/api/webhook`
3. Events to send: select **`checkout.session.completed`**.
4. Save, then copy the endpoint's **Signing secret** (`whsec_...`) into the
   `STRIPE_WEBHOOK_SECRET` env var and **redeploy** so it takes effect.

### Step 6 — Test the full flow (use Stripe test mode first)

1. Set `STRIPE_SECRET_KEY` to your `sk_test_...` key and create the webhook in
   **test mode** (toggle top-left in Stripe).
2. Open `https://tudemm.com/pages/products.html`, click **Buy**.
3. On Stripe's page use test card **`4242 4242 4242 4242`**, any future expiry,
   any CVC, any ZIP.
4. You should land on `success.html`, and within a minute receive the e-book
   email with a working download link.
5. When everything works, swap to your **live** `sk_live_...` key and create a
   **live-mode** webhook (repeat Step 5 in live mode for a new `whsec_...`).

> **Fees:** Stripe charges ~2.9% + $0.30 per successful charge. On a $19 e-book
> that's about $0.85.

---

## Connect your domain
Vercel → **Settings → Domains** → add `tudemm.com` and add the DNS records at
GoDaddy (A record `@ → 76.76.21.21`, CNAME `www → cname.vercel-dns.com`).

## Local preview (optional)
Static pages open directly in a browser, but the `/api/*` functions only run on
Vercel. To test functions locally, install the Vercel CLI (`npm i -g vercel`)
and run `vercel dev` from this folder (set the env vars in a `.env` file first).
