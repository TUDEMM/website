#!/usr/bin/env python3
"""Generate one static, SEO-optimised page per product into /ebooks/.

Reads:
    data/products.json         canonical product data (price, cover, id)
    data/product_content.json  build-time editorial copy (slug, sections, FAQ)
    tools/product_page.template.html

Writes:
    ebooks/<slug>.html         one page per product  ->  https://tudemm.com/ebooks/<slug>
    sitemap.xml                regenerated with static pages + every product page
    pages/products.html        ItemList JSON-LD block (between ITEMLIST markers)
    pages/sitemap.html         product links (between PRODUCTS markers)

Each page carries Product, BreadcrumbList and FAQPage JSON-LD.

Deliberately NOT emitted: aggregateRating / review markup. Google's structured
data policy prohibits self-serving or fabricated review data, and inventing it
risks a manual action. Add it only when real, verifiable customer reviews exist.

Usage:
    python tools/build_product_pages.py
"""
import html
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://tudemm.com"
TEMPLATE = ROOT / "tools" / "product_page.template.html"
OUT_DIR = ROOT / "ebooks"

# Static (non-product) pages, kept in sync with the site structure.
STATIC_PAGES = [
    ("/", "weekly", "1.0"),
    ("/pages/web-development", "monthly", "0.9"),
    ("/pages/seo", "monthly", "0.9"),
    ("/pages/products", "weekly", "0.9"),
    ("/pages/about", "monthly", "0.7"),
    ("/pages/contact", "monthly", "0.8"),
    ("/pages/sitemap", "monthly", "0.3"),
]


def money(cents: int) -> str:
    return "$" + f"{cents / 100:.2f}".rstrip("0").rstrip(".")


def esc(text: str) -> str:
    """Escape for HTML text/attribute context."""
    return html.escape(str(text), quote=True)


def jsonld(obj: dict) -> str:
    """Serialise JSON-LD, neutralising any '</' that could break out of <script>."""
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("</", "<\\/")


def _replace_between(path: Path, start: str, end: str, body: str) -> None:
    """Replace the content between two marker comments, keeping the markers."""
    text = path.read_text()
    if start not in text or end not in text:
        raise SystemExit(f"Markers not found in {path.name}: {start}")
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    path.write_text(f"{head}{start}\n{body}\n{end}{tail}")


def main() -> None:
    products = json.loads((ROOT / "data" / "products.json").read_text())
    content = json.loads((ROOT / "data" / "product_content.json").read_text())
    template = TEMPLATE.read_text()
    shared = content["_shared"]

    OUT_DIR.mkdir(exist_ok=True)
    price_valid_until = (date.today() + timedelta(days=365)).isoformat()
    built = []

    items = products["products"]
    for product in items:
        pid = product["id"]
        if pid not in content:
            raise SystemExit(f"Missing editorial content for product id '{pid}' "
                             f"in data/product_content.json")
        c = content[pid]
        slug = c["slug"]
        url = f"{SITE}/ebooks/{slug}"
        cover_rel = f"/assets/{product['cover']}"
        cover_abs = f"{SITE}{cover_rel}"
        price = money(product["price_cents"])
        price_plain = f"{product['price_cents'] / 100:.2f}"

        # ---------- JSON-LD: Product ----------
        offer = {
            "@type": "Offer",
            "url": url,
            "price": price_plain,
            "priceCurrency": "USD",
            "priceValidUntil": price_valid_until,
            "availability": "https://schema.org/InStock",
            "itemCondition": "https://schema.org/NewCondition",
            "seller": {"@type": "Organization", "name": "TUDEMM LLC", "url": SITE},
        }
        product_schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product["name"],
            "description": product["description"],
            "image": [cover_abs],
            "sku": pid,
            "category": product.get("category", ""),
            "url": url,
            "brand": {"@type": "Brand", "name": "TUDEMM"},
            "publisher": {"@type": "Organization", "name": "TUDEMM LLC", "url": SITE},
            "isFamilyFriendly": True,
            "offers": offer,
            "additionalProperty": [
                {"@type": "PropertyValue", "name": "Format", "value": "PDF (digital download)"},
                {"@type": "PropertyValue", "name": "Delivery", "value": "Emailed instantly after purchase"},
            ],
        }

        # ---------- JSON-LD: BreadcrumbList ----------
        breadcrumb_schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
                {"@type": "ListItem", "position": 2, "name": "Digital Products",
                 "item": f"{SITE}/pages/products"},
                {"@type": "ListItem", "position": 3, "name": product["name"], "item": url},
            ],
        }

        # ---------- JSON-LD: FAQPage ----------
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f["q"],
                 "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                for f in shared["faq"]
            ],
        }

        # ---------- HTML fragments ----------
        covers_html = "\n".join(
            f'            <div class="pdp-cover-card reveal">\n'
            f'              <h3>{esc(item["title"])}</h3>\n'
            f'              <p>{esc(item["body"])}</p>\n'
            f'            </div>'
            for item in c["covers"]
        )

        audience_html = "\n".join(
            f'                <li><span class="mission-num">✓</span>'
            f'<span>{esc(line)}</span></li>'
            for line in c["audience"]
        )

        delivery_html = "\n".join(
            f'            <div class="feature reveal">\n'
            f'              <h3>{esc(item["title"])}</h3>\n'
            f'              <p>{esc(item["body"])}</p>\n'
            f'            </div>'
            for item in shared["delivery"]
        )

        faq_html = "\n".join(
            f'            <details class="pdp-faq-item">\n'
            f'              <summary>{esc(f["q"])}</summary>\n'
            f'              <p>{esc(f["a"])}</p>\n'
            f'            </details>'
            for f in shared["faq"]
        )

        # Related: the other products, in catalogue order, wrapping around.
        others = [p for p in items if p["id"] != pid][:4]
        related_html = "\n".join(
            f'            <a class="pdp-related reveal" '
            f'href="/ebooks/{content[o["id"]]["slug"]}">\n'
            f'              <img src="/assets/{o["cover"]}" '
            f'alt="E-book cover: {esc(o["name"])}" loading="lazy" />\n'
            f'              <span class="pdp-related-name">{esc(o["name"])}</span>\n'
            f'              <span class="pdp-related-price">{money(o["price_cents"])}</span>\n'
            f'            </a>'
            for o in others
        )

        badge_html = (f'<span class="product-badge">{esc(product["badge"])}</span>'
                      if product.get("badge") else "")
        compare_html = (f"<small>{money(product['compare_at_cents'])}</small>"
                        if product.get("compare_at_cents") else "")

        # ---------- Render ----------
        page = template
        replacements = {
            "{{SEO_TITLE}}": esc(c["seo_title"]),
            "{{META_DESCRIPTION}}": esc(c["meta_description"]),
            "{{KEYWORDS}}": esc(c["keywords"]),
            "{{CANONICAL}}": url,
            "{{COVER_ABS}}": cover_abs,
            "{{COVER_REL}}": cover_rel,
            "{{NAME}}": esc(product["name"]),
            "{{CATEGORY}}": esc(product.get("category", "")),
            "{{DESCRIPTION}}": esc(product["description"]),
            "{{TAGLINE}}": esc(c["tagline"]),
            "{{INTRO}}": esc(c["intro"]),
            "{{PRICE}}": price,
            "{{PRICE_PLAIN}}": price_plain,
            "{{COMPARE_AT}}": compare_html,
            "{{BADGE}}": badge_html,
            "{{ID}}": esc(pid),
            "{{COVERS}}": covers_html,
            "{{AUDIENCE}}": audience_html,
            "{{DELIVERY}}": delivery_html,
            "{{FAQ}}": faq_html,
            "{{RELATED}}": related_html,
            "{{DISCLAIMER_HEADING}}": esc(shared["disclaimer_heading"]),
            "{{DISCLAIMER}}": esc(shared["disclaimer"]),
            "{{SCHEMA_PRODUCT}}": jsonld(product_schema),
            "{{SCHEMA_BREADCRUMB}}": jsonld(breadcrumb_schema),
            "{{SCHEMA_FAQ}}": jsonld(faq_schema),
        }
        for token, value in replacements.items():
            page = page.replace(token, value)

        leftover = [t for t in replacements if t in page]
        if "{{" in page:
            raise SystemExit(f"Unreplaced template token remains in {slug}.html")

        (OUT_DIR / f"{slug}.html").write_text(page)
        built.append((f"/ebooks/{slug}", product["name"]))
        print(f"  wrote ebooks/{slug}.html")

    # ---------- Regenerate sitemap.xml ----------
    today = date.today().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
             '',
             '  <!-- Core pages -->']
    for path, freq, prio in STATIC_PAGES:
        lines += ['  <url>',
                  f'    <loc>{SITE}{path}</loc>',
                  f'    <lastmod>{today}</lastmod>',
                  f'    <changefreq>{freq}</changefreq>',
                  f'    <priority>{prio}</priority>',
                  '  </url>',
                  '']
    lines.append('  <!-- Product pages (generated by tools/build_product_pages.py) -->')
    for path, name in built:
        lines += ['  <url>',
                  f'    <loc>{SITE}{path}</loc>',
                  f'    <lastmod>{today}</lastmod>',
                  '    <changefreq>monthly</changefreq>',
                  '    <priority>0.8</priority>',
                  '  </url>',
                  '']
    lines.append('</urlset>')
    (ROOT / "sitemap.xml").write_text("\n".join(lines) + "\n")

    # ---------- Inject ItemList JSON-LD into the catalogue page ----------
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "TUDEMM Digital Products",
        "url": f"{SITE}/pages/products",
        "numberOfItems": len(items),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i,
                "url": f"{SITE}/ebooks/{content[p['id']]['slug']}",
                "name": p["name"],
            }
            for i, p in enumerate(items, start=1)
        ],
    }
    _replace_between(
        ROOT / "pages" / "products.html",
        "<!-- ITEMLIST:START (generated by tools/build_product_pages.py) -->",
        "<!-- ITEMLIST:END -->",
        '    <script type="application/ld+json">\n'
        + jsonld(item_list)
        + "\n    </script>",
    )

    # ---------- Inject product links into the human-readable sitemap ----------
    links = "\n".join(
        f'                <li>\n'
        f'                  <a href="/ebooks/{content[p["id"]]["slug"]}">{esc(p["name"])}'
        f'<span>{esc(content[p["id"]]["tagline"])} · {money(p["price_cents"])}</span></a>\n'
        f'                </li>'
        for p in items
    )
    _replace_between(
        ROOT / "pages" / "sitemap.html",
        "<!-- PRODUCTS:START (generated by tools/build_product_pages.py) -->",
        "<!-- PRODUCTS:END -->",
        links,
    )

    print(f"\n  wrote sitemap.xml ({len(STATIC_PAGES) + len(built)} URLs)")
    print("  updated pages/products.html (ItemList schema)")
    print("  updated pages/sitemap.html (product links)")
    print(f"  {len(built)} product pages generated.")


if __name__ == "__main__":
    main()
