#!/usr/bin/env python3
"""
ADSVOCATE AUDIT PIPELINE
─────────────────────────────────────────────────────
Automated cold outreach audit tool.

Usage:
    python main.py                          # runs all keywords in config.py
    python main.py "lawn suits" "bakery"    # run specific keywords
    python main.py --website https://xyz.pk # audit single website only
    python main.py --help

Output: results/audit_YYYYMMDD_HHMMSS.csv
─────────────────────────────────────────────────────
"""

import asyncio
import sys
import argparse
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

import config
from scrapers.meta_ads import scrape_keyword
from scrapers.website import audit_website
from scrapers.instagram import scrape_instagram_profile, extract_instagram_from_website
from scrapers.google_transparency import check_google_ads_transparency
from generator.dm import generate as generate_dm
from utils.reporter import Reporter


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="Adsvocate Audit Pipeline")
    parser.add_argument("keywords", nargs="*", help="Keywords to search (overrides config.py)")
    parser.add_argument("--website", help="Audit a single website URL directly")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--limit", type=int, default=config.MAX_BRANDS_PER_KEYWORD,
                        help="Max brands per keyword")
    return parser.parse_args()


# ── Single website audit mode ─────────────────────────────────────────────────

async def run_single_website(url: str, browser):
    """Audit one website directly — skips Meta Ads Library discovery."""
    print(f"\n[SINGLE AUDIT] {url}")

    async def make_context():
        return await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

    audit = await audit_website(make_context, url)

    # Try to get Instagram from website
    ctx = await make_context()
    page = await ctx.new_page()
    ig_handle = await extract_instagram_from_website(page, url)

    ig_data = {}
    if ig_handle:
        print(f"  → Instagram found: @{ig_handle}")
        ig_data = await scrape_instagram_profile(page, ig_handle)
    await ctx.close()

    # Google Ads check
    ctx2 = await make_context()
    page2 = await ctx2.new_page()
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.replace("www.", "")
    g_data = await check_google_ads_transparency(page2, domain)
    await ctx2.close()

    brand = {
        "keyword": "direct_audit",
        "brand_name": domain,
        "website_url": url,
        "instagram_handle": ig_handle,
        **audit,
        **ig_data,
        **g_data,
    }

    pitch_type, dm = generate_dm(brand)
    brand["pitch_type"] = pitch_type
    brand["dm"] = dm

    reporter = Reporter(f"results/single_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    reporter.append(brand)
    reporter.print_summary(brand)
    print(f"\n[SAVED] {reporter.output_path}")


# ── Full pipeline ─────────────────────────────────────────────────────────────

async def run_pipeline(keywords: list[str], browser):
    """Full discovery + audit pipeline for a list of keywords."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"{config.OUTPUT_DIR}/audit_{timestamp}.csv"
    reporter = Reporter(output_path)

    print(f"\n{'═' * 60}")
    print(f"  ADSVOCATE AUDIT PIPELINE")
    print(f"  Keywords: {', '.join(keywords)}")
    print(f"  Output  : {output_path}")
    print(f"{'═' * 60}")

    async def make_context():
         return await browser.new_context(
            user_agent=(
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        storage_state=None,          # explicitly blank — no cookies, no sessions
        ignore_https_errors=False,
    )

    # ── Step 1: Discover brands from Meta Ads Library ────────────────────────
    all_brands = []
    for keyword in keywords:
        print(f"\n[STEP 1] Meta Ads Library → '{keyword}'")
        brands = await scrape_keyword(browser, keyword)
        print(f"  → {len(brands)} qualifying brands found")
        all_brands.extend(brands)

    # Deduplicate (same brand might appear in multiple keyword searches)
    seen_pages = set()
    unique_brands = []
    for b in all_brands:
        key = b.get("facebook_page_id", b.get("brand_name", ""))
        if key not in seen_pages:
            seen_pages.add(key)
            unique_brands.append(b)

    print(f"\n[TOTAL] {len(unique_brands)} unique brands to audit")

    if not unique_brands:
        print("[WARN] No brands found. Try different keywords or check Meta Ads Library manually.")
        return output_path

    # ── Step 2: Full audit per brand ─────────────────────────────────────────
    for i, brand in enumerate(unique_brands, 1):
        print(f"\n[{i}/{len(unique_brands)}] {brand['brand_name']}")

        # ── 2a: Website technical audit ─────────────────────────────────────
        if brand.get("website_url"):
            print(f"  [STEP 2a] Website audit: {brand['website_url']}")
            audit_data = await audit_website(make_context, brand["website_url"])
            brand.update(audit_data)

            # Extract Instagram from website if not already found
            if not brand.get("instagram_handle"):
                ctx = await make_context()
                page = await ctx.new_page()
                ig_handle = await extract_instagram_from_website(page, brand["website_url"])
                await ctx.close()
                brand["instagram_handle"] = ig_handle
        else:
            print(f"  [STEP 2a] SKIP — no website URL")

        # ── 2b: Instagram audit ──────────────────────────────────────────────
        if brand.get("instagram_handle"):
            print(f"  [STEP 2b] Instagram: @{brand['instagram_handle']}")
            ctx = await make_context()
            page = await ctx.new_page()
            ig_data = await scrape_instagram_profile(page, brand["instagram_handle"])
            await ctx.close()
            brand.update(ig_data)
        else:
            print(f"  [STEP 2b] SKIP — no Instagram handle found")
            brand.update({
                "ig_followers": 0,
                "ig_activity": "UNKNOWN",
                "ig_last_post_days_ago": 999,
            })

        # ── 2c: Google Ads Transparency ──────────────────────────────────────
        print(f"  [STEP 2c] Google Ads Transparency: {brand['brand_name']}")
        ctx = await make_context()
        page = await ctx.new_page()
        g_data = await check_google_ads_transparency(page, brand["brand_name"])
        await ctx.close()
        brand.update(g_data)

        # ── 2d: Generate DM ──────────────────────────────────────────────────
        pitch_type, dm = generate_dm(brand)
        brand["pitch_type"] = pitch_type
        brand["dm"] = dm

        # ── 2e: Save + print ─────────────────────────────────────────────────
        reporter.append(brand)
        reporter.print_summary(brand)

    print(f"\n{'═' * 60}")
    print(f"  COMPLETE — {reporter.count} brands audited")
    print(f"  CSV saved: {output_path}")
    print(f"{'═' * 60}\n")

    return output_path


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    args = parse_args()
    headless = args.headless or config.HEADLESS

    async with async_playwright() as p:
        browser = await p.chromium.launch(
         headless=headless,
         slow_mo=config.SLOW_MO,
         channel=None,          # forces Playwright's own Chromium, never your installed Chrome
          args=[
             "--no-sandbox",
             "--disable-blink-features=AutomationControlled",
             "--disable-infobars",
             "--incognito",
         ]
)

        try:
            if args.website:
                # Single website mode
                await run_single_website(args.website, browser)
            else:
                # Full pipeline
                keywords = args.keywords if args.keywords else config.KEYWORDS
                if not keywords:
                    print("[ERROR] No keywords specified. Edit config.py or pass keywords as arguments.")
                    sys.exit(1)
                await run_pipeline(keywords, browser)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
