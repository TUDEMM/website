#!/usr/bin/env python3
"""One-shot builder for pages/refunds.html.

Reuses the exact <header> and <footer> markup from pages/about.html so the new
legal page cannot drift from the rest of the site. Run once; after that edit
pages/refunds.html directly.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://tudemm.com"
UPDATED = "August 18, 2026"

src = (ROOT / "pages" / "about.html").read_text()

header = re.search(r"( *<header class=\"header\">.*?</header>)", src, re.S).group(1)
footer = re.search(r"( *<footer class=\"footer\">.*?</footer>)", src, re.S).group(1)
favicon = re.search(r' *<link rel="icon".*?/>\n', src, re.S).group(0)
scripts = re.search(r"((?: *<script[^>]*></script>\n)+)\s*</body>", src, re.S)
scripts = scripts.group(1) if scripts else '    <script src="../app.js"></script>\n'

# nav highlighting: about.html marks its own link current; strip that here
header = header.replace(' aria-current="page"', "")

TITLE = "Refund Policy — All Sales Final on Digital Downloads — TUDEMM"
DESC = (
    "TUDEMM Digital Services refund policy for digital products: all sales are final and no "
    "refunds are issued on downloaded digital products. Limited exceptions for "
    "duplicate charges and non-delivery."
)

MAIN = f"""
    <main id="main">
      <section class="page-hero">
        <div class="container container--narrow">
          <p class="breadcrumb">
            <a href="../index.html">Home</a> &rsaquo; Refund Policy
          </p>
          <span class="eyebrow">Legal</span>
          <h1>Refund Policy</h1>
          <p>
            This policy explains how refunds work on everything sold through
            tudemm.com. Please read it before you buy &mdash; completing a purchase
            means you accept these terms.
          </p>
          <p class="legal-updated">Last updated {UPDATED}</p>
        </div>
      </section>

      <section>
        <div class="container container--narrow">
          <div class="legal-key reveal">
            <h2>All sales are final</h2>
            <p>
              <strong
                >TUDEMM Digital Services does not issue refunds, returns, exchanges, or
                cancellations on digital products once the product has been
                downloaded or otherwise accessed.</strong
              >
              Our digital products are delivered instantly and can be copied and
              kept permanently, so a download cannot be returned or taken back the
              way a physical item can.
            </p>
          </div>

          <div class="legal-prose reveal">
            <h2>What this covers</h2>
            <p>
              This policy applies to every digital product sold on this site,
              including all e-books, guides, plans, and any other downloadable
              file or digital file delivered by email or download link.
            </p>

            <h2>Your acknowledgement at checkout</h2>
            <p>
              Because delivery is immediate, when you complete a purchase you
              expressly request that delivery begin right away, and you
              acknowledge that you lose any right to cancel or withdraw from the
              purchase once the download has been made available to you.
            </p>

            <h2>Limited exceptions</h2>
            <p>
              We will always make a payment problem right. We will review a refund
              request in these situations:
            </p>
            <ul>
              <li>
                <strong>You were charged more than once</strong> for the same
                product. We refund the duplicate charge in full.
              </li>
              <li>
                <strong>You never received your product</strong> and we are unable
                to deliver it to you. If a download link fails or expires, contact
                us first &mdash; we will always send a fresh link, and a working
                link counts as delivery.
              </li>
              <li>
                <strong>You were charged for the wrong product</strong> and have
                not downloaded it.
              </li>
              <li>
                <strong>The charge was not authorised by you.</strong> Contact us
                immediately so we can investigate.
              </li>
            </ul>
            <p>
              Outside of these situations, a completed purchase of a downloaded
              digital product is not refundable. In particular, we do not offer
              refunds because you changed your mind, bought the wrong item by
              mistake and already downloaded it, did not read the product
              description, already owned similar material, or did not get the
              result you hoped for from the information.
            </p>

            <h2>Before you buy</h2>
            <p>
              Every product page lists exactly what the product covers, who it is
              for, and what you receive. If anything is unclear, please
              <a href="./contact.html">ask us before you purchase</a> &mdash; we
              would much rather answer a question up front than have you buy
              something that is not right for you.
            </p>
            <p>
              Our digital products are educational material. They are not medical,
              legal, or financial advice, and no particular outcome or result is
              promised.
            </p>

            <h2>How to make a request</h2>
            <p>
              Email
              <a href="mailto:info@tudemm.com">info@tudemm.com</a> within 14 days
              of your purchase with your order or receipt number, the email address
              you used at checkout, the product name, and a short explanation. We
              respond to every request, normally within two business days. Approved
              refunds go back to the original payment method and typically take
              5&ndash;10 business days to appear, depending on your bank or card
              issuer.
            </p>

            <h2>Payment disputes</h2>
            <p>
              If you believe there is a problem with a charge, please contact us
              first. We can usually resolve it faster than a bank dispute. Nothing
              in this policy removes any right you have to dispute a charge with
              your card issuer or payment provider.
            </p>

            <h2>Your statutory rights</h2>
            <p>
              Nothing in this policy is intended to limit any right you have that
              cannot be waived under the consumer protection law that applies to
              you. Where such a law gives you a right to a remedy, that law takes
              precedence over this policy. If a product is faulty, corrupted, or
              not as described, contact us and we will repair, replace, or refund
              it.
            </p>

            <h2>Changes to this policy</h2>
            <p>
              We may update this policy from time to time. The version published on
              this page at the moment you complete your purchase is the version
              that applies to that purchase.
            </p>

            <h2>Contact</h2>
            <p>
              TUDEMM Digital Services &middot; Worthington, Ohio, United States<br />
              <a href="mailto:info@tudemm.com">info@tudemm.com</a>
            </p>
          </div>

          <p class="legal-foot text-muted">
            This page describes our commercial refund terms. It is not legal
            advice, and it is not a substitute for having a lawyer review your
            terms of sale.
          </p>
        </div>
      </section>

      <section>
        <div class="container">
          <div class="cta-band reveal">
            <h2>Still have a question about a product?</h2>
            <p>
              Ask before you buy &mdash; we are happy to tell you whether something
              is the right fit for you.
            </p>
            <div class="cta-actions">
              <a href="./contact.html" class="btn btn-light">Contact us</a>
              <a href="./products.html" class="btn btn-light">Browse products</a>
            </div>
          </div>
        </div>
      </section>
    </main>
"""

html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
{favicon.rstrip()}
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{TITLE}</title>
    <link rel="canonical" href="{SITE}/pages/refunds" />
    <meta name="description" content="{DESC}" />
    <meta property="og:title" content="{TITLE}" />
    <meta property="og:url" content="{SITE}/pages/refunds" />
    <meta property="og:image" content="../assets/hero.png" />
    <link rel="preconnect" href="https://api.fontshare.com" />
    <link href="https://api.fontshare.com/v2/css?f[]=clash-display@500,600&f[]=general-sans@400,500,600&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="../base.css" />
    <link rel="stylesheet" href="../style.css" />
  </head>
  <body>
    <a href="#main" class="sr-only">Skip to content</a>
{header}
{MAIN.strip(chr(10))}
{footer}
{scripts.rstrip()}
  </body>
</html>
"""

out = ROOT / "pages" / "refunds.html"
out.write_text(html)
print(f"wrote {out.relative_to(ROOT)} ({len(html.splitlines())} lines)")
