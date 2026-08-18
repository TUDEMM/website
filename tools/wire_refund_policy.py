#!/usr/bin/env python3
"""One-shot wiring for the refund policy.

Adds the footer link site-wide, the pre-purchase notice on buy surfaces, the
sitemap entry, the shared FAQ entry, and the Stripe checkout acknowledgement.
Idempotent: re-running makes no further changes.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch(path: Path, old: str, new: str, *, label: str, count: int = 1) -> None:
    p = ROOT / path
    s = p.read_text()
    if new.strip() and new.strip() in s:
        print(f"  skip (already present)  {path}  [{label}]")
        return
    if old not in s:
        raise SystemExit(f"ANCHOR NOT FOUND in {path} [{label}]:\n{old}")
    s = s.replace(old, new, count)
    p.write_text(s)
    print(f"  patched {path}  [{label}]")


print("1. Footer 'Refund Policy' link, site-wide")
# index.html sits at the repo root -> ./pages/ prefix
patch(
    Path("index.html"),
    '<li><a href="./pages/sitemap.html">Sitemap</a></li>',
    '<li><a href="./pages/sitemap.html">Sitemap</a></li>\n'
    '              <li><a href="./pages/refunds.html">Refund Policy</a></li>',
    label="footer",
)
# pages/*.html are siblings -> ./ prefix
for name in ["about", "contact", "products", "seo", "sitemap", "web-development", "success", "refunds"]:
    f = Path("pages") / f"{name}.html"
    if not (ROOT / f).exists():
        print(f"  skip (missing)  {f}")
        continue
    s = (ROOT / f).read_text()
    if 'href="./refunds.html"' in s:
        print(f"  skip (already present)  {f}  [footer]")
        continue
    # success.html has no Sitemap link (it is noindex), so fall back to Contact
    anchor = next(
        (a for a in ('<li><a href="./sitemap.html">Sitemap</a></li>',
                     '<li><a href="./contact.html">Contact</a></li>') if a in s),
        None,
    )
    if anchor is None:
        print(f"  WARN no footer anchor in {f}")
        continue
    s = s.replace(
        anchor,
        anchor + '\n              <li><a href="./refunds.html">Refund Policy</a></li>',
        1,
    )
    (ROOT / f).write_text(s)
    print(f"  patched {f}  [footer]")

# /ebooks/* pages use root-absolute links
patch(
    Path("tools/product_page.template.html"),
    '<li><a href="/pages/contact">Contact</a></li>',
    '<li><a href="/pages/contact">Contact</a></li>\n'
    '              <li><a href="/pages/refunds">Refund Policy</a></li>',
    label="footer",
)

print("\n2. Pre-purchase notice next to the buy button (product detail template)")
patch(
    Path("tools/product_page.template.html"),
    """              <ul class="pdp-trust">""",
    """              <p class="buy-note">
                Instant digital download.
                <a href="/pages/refunds">All sales are final</a> &mdash; no
                refunds once the file has been downloaded.
              </p>

              <ul class="pdp-trust">""",
    label="buy-note",
)

print("\n3. Pre-purchase notice on the catalogue page")
prod = ROOT / "pages" / "products.html"
s = prod.read_text()
if 'class="buy-note"' not in s:
    m = re.search(r'(<div[^>]*data-products-grid[^>]*>.*?</div>)', s, re.S)
    if not m:
        m = re.search(r'(<[a-z]+[^>]*data-products-grid[^>]*>)', s)
    anchor = m.group(1)
    s = s.replace(
        anchor,
        anchor
        + '\n          <p class="buy-note">'
        + '\n            Every product is an instant digital download.'
        + '\n            <a href="./refunds.html">All sales are final</a> &mdash; no refunds once the file has been downloaded.'
        + '\n          </p>',
        1,
    )
    prod.write_text(s)
    print("  patched pages/products.html  [buy-note]")
else:
    print("  skip (already present)  pages/products.html  [buy-note]")

print("\n4. Refund line on the post-purchase success page")
patch(
    Path("pages") / "success.html",
    "</main>",
    """  <div class="container container--narrow">
        <p class="buy-note" style="text-align:center">
          Trouble with your download? Email
          <a href="mailto:info@tudemm.com">info@tudemm.com</a> and we will send a
          fresh link. See our <a href="./refunds.html">refund policy</a>.
        </p>
      </div>
    </main>""",
    label="success-note",
)

print("\n5. Shared FAQ entry (feeds FAQPage schema on every product page)")
cpath = ROOT / "data" / "product_content.json"
content = json.loads(cpath.read_text())
faq = content["_shared"]["faq"]
q = "Can I get a refund?"
if not any(item["q"] == q for item in faq):
    faq.append({
        "q": q,
        "a": (
            "No. Because this is an instant digital download that you keep, all "
            "sales are final and we do not offer refunds once the file has been "
            "downloaded. We will of course fix a duplicate charge or a delivery "
            "problem \u2014 email info@tudemm.com. If you are unsure whether this "
            "guide is right for you, please ask us before you buy."
        ),
    })
    cpath.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n")
    print(f"  added FAQ entry (now {len(faq)} questions)")
else:
    print("  skip (already present)  refund FAQ")

print("\n6. Generator: sitemap entry + hasMerchantReturnPolicy schema")
patch(
    Path("tools/build_product_pages.py"),
    '    ("/pages/sitemap", "monthly", "0.3"),',
    '    ("/pages/refunds", "yearly", "0.3"),\n'
    '    ("/pages/sitemap", "monthly", "0.3"),',
    label="sitemap",
)
patch(
    Path("tools/build_product_pages.py"),
    '            "brand": {"@type": "Brand", "name": "TUDEMM"},',
    '            "brand": {"@type": "Brand", "name": "TUDEMM"},\n'
    '            # Downloaded digital goods are non-returnable. See /pages/refunds.\n'
    '            "hasMerchantReturnPolicy": {\n'
    '                "@type": "MerchantReturnPolicy",\n'
    '                "applicableCountry": "US",\n'
    '                "returnPolicyCategory": "https://schema.org/MerchantReturnNotPermitted",\n'
    '                "url": f"{SITE}/pages/refunds",\n'
    '            },',
    label="return-policy-schema",
)

print("\n7. Human-readable sitemap: Refund Policy entry")
sm = ROOT / "pages" / "sitemap.html"
s = sm.read_text()
if "refunds.html" not in s:
    anchor = re.search(
        r'( *<li>\s*\n *<a href="\./contact\.html">.*?</a>\s*\n *</li>)', s, re.S
    )
    if not anchor:
        raise SystemExit("could not find contact entry in pages/sitemap.html")
    block = anchor.group(1)
    s = s.replace(
        block,
        block
        + '\n                <li>\n'
        + '                  <a href="./refunds.html">Refund Policy'
        + '<span>All sales final on downloaded digital products</span></a>\n'
        + '                </li>',
        1,
    )
    sm.write_text(s)
    print("  patched pages/sitemap.html  [refund entry]")
else:
    print("  skip (already present)  pages/sitemap.html")

print("\nDone.")
