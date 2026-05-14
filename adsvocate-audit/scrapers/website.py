"""
WEBSITE TECHNICAL AUDITOR — v2 (accuracy rewrite)
Uses console-based detection (window objects, cookies, page source)
instead of network interception, which was causing false positives.

Confidence scores per finding:
  HIGH   = multiple signals confirm the same thing
  MEDIUM = one strong signal
  LOW    = weak signal, verify manually
"""

import asyncio
import re
import random
from urllib.parse import urlparse
from playwright.async_api import Page, BrowserContext
from config import DELAYS, FUNNEL_PATHS


async def _rand_sleep(key="after_navigation"):
    lo, hi = DELAYS.get(key, (2, 4))
    await asyncio.sleep(random.uniform(lo, hi))


def _is_shopify(page_source: str, url: str) -> bool:
    return (
        "cdn.shopify.com" in page_source
        or "myshopify.com" in url
        or "Shopify.theme" in page_source
        or "/cdn/shop/" in page_source
    )


def _is_woocommerce(page_source: str) -> bool:
    return "woocommerce" in page_source.lower() or "wc-cart" in page_source


async def _deep_page_check(page: Page) -> dict:
    """
    Core detection using window objects + page source + cookies.
    This is more accurate than network interception.
    """
    return await page.evaluate("""
        () => {
            const result = {
                // Meta Pixel
                fbq_present:        typeof window.fbq === 'function',
                fbq_version:        '',
                pixel_ids:          [],

                // GTM
                gtm_present:        false,
                gtm_container_ids:  [],
                datalayer_present:  Array.isArray(window.dataLayer),
                datalayer_events:   [],
                datalayer_empty:    true,

                // Google Ads
                gads_present:       false,
                gads_ids:           [],

                // GA4
                ga4_present:        false,
                ga4_ids:            [],

                // Cookies
                cookie_fbp:         false,
                cookie_fbc:         false,
                cookie_gcl_au:      false,
                cookie_gcl_aw:      false,
                cookie_ga:          false,
                cookie_gid:         false,

                // Platform
                is_shopify:         false,
                is_woocommerce:     false,

                // Page source signals
                source_has_gtm:     false,
                source_has_pixel:   false,
                source_has_gads:    false,
                source_has_ga4:     false,
            };

            // ── Cookies ──────────────────────────────────────────────────
            const cookies = document.cookie;
            result.cookie_fbp    = cookies.includes('_fbp=');
            result.cookie_fbc    = cookies.includes('_fbc=');
            result.cookie_gcl_au = cookies.includes('_gcl_au=');
            result.cookie_gcl_aw = cookies.includes('_gcl_aw=');
            result.cookie_ga     = cookies.includes('_ga=');
            result.cookie_gid    = cookies.includes('_gid=');

            // ── GTM — require window.google_tag_manager object ───────────
            if (window.google_tag_manager && typeof window.google_tag_manager === 'object') {
                result.gtm_present = true;
                result.gtm_container_ids = Object.keys(window.google_tag_manager)
                    .filter(k => k.startsWith('GTM-'));
            }

            // ── DataLayer events ─────────────────────────────────────────
            if (Array.isArray(window.dataLayer)) {
                window.dataLayer.forEach(item => {
                    if (item && item.event) result.datalayer_events.push(item.event);
                });
                const noise = new Set(['gtm.js','gtm.dom','gtm.load','gtm.historyChange']);
                const real = result.datalayer_events.filter(e => !noise.has(e));
                result.datalayer_empty = real.length === 0;
            }

            // ── Meta Pixel — require window.fbq ─────────────────────────
            if (typeof window.fbq === 'function') {
                result.fbq_present = true;
                try {
                    if (window._fbq && window._fbq.pixelsByID) {
                        result.pixel_ids = Object.keys(window._fbq.pixelsByID);
                    }
                } catch(e) {}
            }

            // ── Google Ads / GA4 — check window.gtag and dataLayer ───────
            if (typeof window.gtag === 'function') {
                // gtag is present — check what IDs it's sending to
                if (Array.isArray(window.dataLayer)) {
                    window.dataLayer.forEach(item => {
                        if (Array.isArray(item)) {
                            const str = JSON.stringify(item);
                            const awMatch = str.match(/AW-[\\d]+/g);
                            const gaMatch = str.match(/G-[A-Z0-9]+/g);
                            if (awMatch) result.gads_ids.push(...awMatch);
                            if (gaMatch) result.ga4_ids.push(...gaMatch);
                        }
                    });
                }
            }

            // ── Page source scan ─────────────────────────────────────────
            const html = document.documentElement.innerHTML;

            // GTM in source: require actual GTM-XXXX container reference
            const gtmMatches = html.match(/GTM-[A-Z0-9]+/g);
            if (gtmMatches) {
                result.source_has_gtm = true;
                const unique = [...new Set(gtmMatches)];
                result.gtm_container_ids = [...new Set([...result.gtm_container_ids, ...unique])];
                if (!result.gtm_present) result.gtm_present = true;
            }

            // Meta Pixel in source: require fbq('init', 'PIXELID')
            const pixelMatches = html.match(/fbq\s*\(\s*['"]init['"]\s*,\s*['"]?(\d{10,})/g);
            if (pixelMatches) {
                result.source_has_pixel = true;
                pixelMatches.forEach(m => {
                    const id = m.match(/(\d{10,})/);
                    if (id) result.pixel_ids.push(id[1]);
                });
                if (!result.fbq_present) result.fbq_present = true;
            }

            // Google Ads in source: require AW-XXXXXXX conversion ID
            const awMatches = html.match(/AW-\d{7,}/g);
            if (awMatches) {
                result.source_has_gads = true;
                result.gads_ids = [...new Set([...result.gads_ids, ...awMatches])];
                result.gads_present = true;
            }

            // GA4 in source: require G-XXXXXXXXXX measurement ID
            const ga4Matches = html.match(/G-[A-Z0-9]{8,}/g);
            if (ga4Matches) {
                result.source_has_ga4 = true;
                result.ga4_ids = [...new Set([...result.ga4_ids, ...ga4Matches])];
                result.ga4_present = true;
            }

            // Platform detection
            result.is_shopify = (
                html.includes('cdn.shopify.com') ||
                html.includes('Shopify.theme') ||
                html.includes('/cdn/shop/')
            );
            result.is_woocommerce = html.toLowerCase().includes('woocommerce');

            return result;
        }
    """)


async def _check_funnel_pages(page: Page, base_url: str) -> dict:
    """
    Navigate to product and contact pages, check if tracking
    continues firing. Marks Shopify checkout as unverifiable.
    """
    funnel = {
        "product_page_checked":  False,
        "product_page_pixel":    False,
        "product_page_gtm":      False,
        "contact_page_checked":  False,
        "contact_lead_event":    False,
        "shopify_checkout_note": "",
        "pixel_drops_at_product": False,
    }

    # Product page
    for sel in FUNNEL_PATHS["product_selectors"]:
        try:
            link = page.locator(sel).first
            if await link.count() > 0:
                href = await link.get_attribute("href")
                if href and "javascript" not in href:
                    product_url = href if href.startswith("http") else base_url.rstrip("/") + "/" + href.lstrip("/")
                    await page.goto(product_url, wait_until="domcontentloaded", timeout=20000)
                    await _rand_sleep()
                    check = await _deep_page_check(page)
                    funnel["product_page_checked"] = True
                    funnel["product_page_pixel"] = check.get("fbq_present") or check.get("cookie_fbp")
                    funnel["product_page_gtm"]   = check.get("gtm_present")
                    break
        except Exception:
            continue

    # Contact page
    for sel in FUNNEL_PATHS["contact_selectors"]:
        try:
            link = page.locator(sel).first
            if await link.count() > 0:
                href = await link.get_attribute("href")
                if href and "javascript" not in href:
                    contact_url = href if href.startswith("http") else base_url.rstrip("/") + "/" + href.lstrip("/")
                    await page.goto(contact_url, wait_until="domcontentloaded", timeout=20000)
                    await _rand_sleep()
                    check = await _deep_page_check(page)
                    funnel["contact_page_checked"] = True
                    dl_events = check.get("datalayer_events", [])
                    funnel["contact_lead_event"] = any(
                        "lead" in e.lower() or "generate_lead" in e.lower()
                        for e in dl_events
                    )
                    break
        except Exception:
            continue

    return funnel


async def _scrape_contacts(page: Page, base_url: str) -> dict:
    """Scrape contact email and WhatsApp from website."""
    contacts = {"contact_email": "", "whatsapp_link": ""}
    try:
        body = await page.evaluate("() => document.body.innerText")
        emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", body)
        skip = ["noreply", "support@shopify", "privacy@", "legal@", "example@",
                "test@", "admin@wordpress", "woocommerce@"]
        for email in emails:
            if not any(s in email.lower() for s in skip):
                contacts["contact_email"] = email.lower()
                break

        wa_links = await page.evaluate("""
            () => Array.from(document.querySelectorAll('a[href*="wa.me"], a[href*="whatsapp.com"]'))
                 .map(a => a.href)
        """)
        if wa_links:
            contacts["whatsapp_link"] = wa_links[0]
    except Exception:
        pass
    return contacts


def _compute_confidence(audit: dict) -> dict:
    """
    Add confidence level per key finding.
    HIGH = 2+ independent signals. MEDIUM = 1 strong signal. LOW = weak.
    """
    confidence = {}

    # Meta Pixel confidence
    pixel_signals = sum([
        bool(audit.get("fbq_present")),
        bool(audit.get("cookie_fbp")),
        bool(audit.get("source_has_pixel")),
        bool(audit.get("pixel_ids")),
    ])
    if pixel_signals >= 2:
        confidence["pixel_confidence"] = "HIGH"
    elif pixel_signals == 1:
        confidence["pixel_confidence"] = "MEDIUM"
    else:
        confidence["pixel_confidence"] = "HIGH"  # HIGH confidence it's NOT there

    # GTM confidence
    gtm_signals = sum([
        bool(audit.get("gtm_present")),
        bool(audit.get("gtm_container_ids")),
        bool(audit.get("source_has_gtm")),
        bool(audit.get("datalayer_present")),
    ])
    if gtm_signals >= 2:
        confidence["gtm_confidence"] = "HIGH"
    elif gtm_signals == 1:
        confidence["gtm_confidence"] = "MEDIUM"
    else:
        confidence["gtm_confidence"] = "HIGH"

    # Google Ads confidence
    gads_signals = sum([
        bool(audit.get("gads_present")),
        bool(audit.get("gads_ids")),
        bool(audit.get("cookie_gcl_au")),
        bool(audit.get("source_has_gads")),
    ])
    if gads_signals >= 2:
        confidence["gads_confidence"] = "HIGH"
    elif gads_signals == 1:
        confidence["gads_confidence"] = "MEDIUM"
    else:
        confidence["gads_confidence"] = "HIGH"

    return confidence


async def audit_website(browser_context_factory, website_url: str) -> dict:
    """
    Full technical audit. Returns dict with all findings + confidence scores.
    """
    if not website_url or website_url in ("https://fb.com", "http://www.fb.com",
                                           "https://www.facebook.com", "https://facebook.com"):
        return {"audit_error": "invalid or facebook URL — skip this brand"}

    if not website_url.startswith("http"):
        website_url = "https://" + website_url

    parsed = urlparse(website_url)
    domain = parsed.netloc.replace("www.", "")

    audit = {
        "website_url":   website_url,
        "domain":        domain,

        # Meta Pixel
        "fbq_present":           False,
        "pixel_ids":             [],
        "source_has_pixel":      False,
        "cookie_fbp":            False,
        "cookie_fbc":            False,

        # GTM
        "gtm_present":           False,
        "gtm_container_ids":     [],
        "source_has_gtm":        False,
        "datalayer_present":     False,
        "datalayer_empty":       True,
        "datalayer_events":      [],

        # Google Ads
        "gads_present":          False,
        "gads_ids":              [],
        "source_has_gads":       False,
        "cookie_gcl_au":         False,

        # GA4
        "ga4_present":           False,
        "ga4_ids":               [],
        "source_has_ga4":        False,
        "cookie_ga":             False,

        # Platform
        "is_shopify":            False,
        "is_woocommerce":        False,

        # Funnel
        "product_page_pixel":    False,
        "pixel_drops_at_product": False,
        "contact_lead_event":    False,
        "shopify_checkout_note": "",

        # Contact
        "contact_email":         "",
        "whatsapp_link":         "",

        # Summary flags (used by DM generator)
        "has_meta_pixel":        False,
        "has_gtm":               False,
        "has_google_ads_tag":    False,
        "has_ga4":               False,
        "tracking_clean":        False,

        # Confidence
        "pixel_confidence":      "UNKNOWN",
        "gtm_confidence":        "UNKNOWN",
        "gads_confidence":       "UNKNOWN",

        "audit_error":           "",
        "manual_check_needed":   "",
    }

    try:
        context = await browser_context_factory()
        page = await context.new_page()

        # ── Homepage ────────────────────────────────────────────────────────
        await page.goto(website_url, wait_until="domcontentloaded", timeout=30000)
        await _rand_sleep()
        await asyncio.sleep(2)  # let tracking tags fire

        homepage = await _deep_page_check(page)
        audit.update({k: v for k, v in homepage.items() if k in audit})

        # ── Shopify flag ─────────────────────────────────────────────────────
        if homepage.get("is_shopify"):
            audit["is_shopify"] = True
            audit["shopify_checkout_note"] = (
                "SHOPIFY DETECTED — checkout.shopify.com is locked. "
                "Pixel-at-checkout CANNOT be verified automatically. "
                "Verify manually: visit checkout page with Meta Pixel Helper extension."
            )
            audit["manual_check_needed"] = "Shopify checkout pixel — verify manually"

        # ── Funnel pages ────────────────────────────────────────────────────
        funnel = await _check_funnel_pages(page, website_url)
        audit.update(funnel)

        # If homepage pixel present but product page pixel absent: flag it
        if homepage.get("fbq_present") and funnel.get("product_page_checked") and not funnel.get("product_page_pixel"):
            audit["pixel_drops_at_product"] = True

        # ── Contacts ────────────────────────────────────────────────────────
        await page.goto(website_url, wait_until="domcontentloaded", timeout=20000)
        contacts = await _scrape_contacts(page, website_url)
        audit.update(contacts)

        # ── Confidence scores ───────────────────────────────────────────────
        confidence = _compute_confidence(audit)
        audit.update(confidence)

        # ── Summary flags ────────────────────────────────────────────────────
        audit["has_meta_pixel"]     = homepage.get("fbq_present", False) or homepage.get("cookie_fbp", False)
        audit["has_gtm"]            = homepage.get("gtm_present", False)
        audit["has_google_ads_tag"] = homepage.get("gads_present", False) or homepage.get("cookie_gcl_au", False)
        audit["has_ga4"]            = homepage.get("ga4_present", False) or homepage.get("cookie_ga", False)

        audit["tracking_clean"] = (
            audit["has_meta_pixel"]
            and audit["has_gtm"]
            and not audit["datalayer_empty"]
            and audit["has_google_ads_tag"]
        )

        await context.close()

    except Exception as e:
        audit["audit_error"] = str(e)

    return audit