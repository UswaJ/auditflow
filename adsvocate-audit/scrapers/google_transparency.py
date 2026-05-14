"""
GOOGLE ADS TRANSPARENCY CENTER SCRAPER
Checks adstransparency.google.com for a brand running Google Ads in Pakistan.
Returns: whether running, ad types, count.
"""

import asyncio
import random
from urllib.parse import quote
from playwright.async_api import Page
from config import DELAYS


TRANSPARENCY_URL = "https://adstransparency.google.com/"


async def _rand_sleep():
    lo, hi = DELAYS.get("after_navigation", (2, 4))
    await asyncio.sleep(random.uniform(lo, hi))


async def check_google_ads_transparency(page: Page, brand_name: str) -> dict:
    """
    Search Google Ads Transparency Center for a brand name, filtered to Pakistan.
    Returns dict with whether they're running Google Ads and what types.
    """
    result = {
        "google_ads_running": False,
        "google_ad_types": [],
        "google_ad_count_note": "",
        "google_transparency_error": "",
    }

    if not brand_name or brand_name.startswith("Brand_"):
        result["google_transparency_error"] = "generic brand name, skipped"
        return result

    try:
        # Navigate to transparency center with search
        search_url = f"{TRANSPARENCY_URL}?region=PK&domain={quote(brand_name)}"
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        await _rand_sleep()

        # Also try keyword search
        # adstransparency.google.com/?query=BRANDNAME&region=PK
        search_url2 = f"https://adstransparency.google.com/?query={quote(brand_name)}&region=PK"
        await page.goto(search_url2, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        page_text = await page.evaluate("() => document.body.innerText")
        page_text_lower = page_text.lower()

        # Check if any ads found
        no_results_signals = [
            "no ads",
            "no results",
            "0 ads",
            "couldn't find",
        ]
        if any(s in page_text_lower for s in no_results_signals):
            result["google_ads_running"] = False
            return result

        # Check for ad type indicators
        ad_types = []
        if "search" in page_text_lower:
            ad_types.append("Search")
        if "display" in page_text_lower:
            ad_types.append("Display")
        if "shopping" in page_text_lower:
            ad_types.append("Shopping")
        if "youtube" in page_text_lower:
            ad_types.append("YouTube")

        # If we see advertiser cards or ad results, they're running ads
        has_results = await page.evaluate("""
            () => {
                // Look for advertiser result cards
                const cards = document.querySelectorAll(
                    '[class*="advertiser"], [class*="ad-card"], [class*="result"]'
                );
                return cards.length > 0;
            }
        """)

        if has_results or (ad_types and "no results" not in page_text_lower):
            result["google_ads_running"] = True
            result["google_ad_types"] = ad_types
            result["google_ad_count_note"] = "Running Google Ads in PK — verify types manually"
        else:
            result["google_ads_running"] = False

    except Exception as e:
        result["google_transparency_error"] = str(e)

    return result
