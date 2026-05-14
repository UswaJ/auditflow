"""
META ADS LIBRARY SCRAPER
Uses facebook.com/PageName/ link structure (current 2025/2026).
"""

import asyncio
import random
import re
from urllib.parse import urlencode, urlparse, unquote
from playwright.async_api import Page, Browser
from config import FILTERS, DELAYS, MAX_BRANDS_PER_KEYWORD


ADS_LIBRARY_BASE = "https://www.facebook.com/ads/library/"

SKIP_FB_PATHS = {
    "ads", "privacy", "policies", "help", "about", "login", "signup",
    "l.php", "sharer", "dialog", "groups", "events", "marketplace",
    "watch", "gaming", "fundraisers", "pages", "business", "me",
    "r.php", "recover", "reg", "ajax", "x", "share",
}


def _build_search_url(keyword):
    params = {
        "active_status": "active",
        "ad_type": "all",
        "country": FILTERS["country"],
        "q": keyword,
        "sort_data[direction]": "desc",
        "sort_data[mode]": "relevancy_monthly_grouped",
        "search_type": "keyword_unordered",
        "media_type": "all",
    }
    return ADS_LIBRARY_BASE + "?" + urlencode(params)


def _build_page_search_url(username):
    params = {
        "active_status": "active",
        "ad_type": "all",
        "country": FILTERS["country"],
        "is_targeted_country": "false",
        "media_type": "all",
        "q": username,
        "search_type": "page",
    }
    return ADS_LIBRARY_BASE + "?" + urlencode(params)


async def _random_delay(range_key):
    lo, hi = DELAYS.get(range_key, (2, 5))
    await asyncio.sleep(random.uniform(lo, hi))


async def _scroll_to_load(page, scrolls=4):
    for _ in range(scrolls):
        await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        await asyncio.sleep(DELAYS["scroll_pause"])


def _is_brand_page_url(url):
    try:
        parsed = urlparse(url)
        if "facebook.com" not in parsed.netloc:
            return False
        path = parsed.path.strip("/")
        if not path:
            return False
        first_segment = path.split("/")[0].lower()
        if first_segment in SKIP_FB_PATHS:
            return False
        if re.match(r'^[\w.]+$', first_segment) and len(first_segment) > 2:
            return True
    except Exception:
        pass
    return False


INVALID_WEBSITES = {
    "fb.com", "www.fb.com", "facebook.com", "www.facebook.com",
    "instagram.com", "www.instagram.com", "wa.me", "whatsapp.com",
    "l.facebook.com", "m.facebook.com",
}

def _extract_website_from_redirect(url):
    try:
        if "l.facebook.com/l.php" in url:
            match = re.search(r'[?&]u=([^&]+)', url)
            if match:
                decoded = unquote(match.group(1))
                parsed = urlparse(decoded)
                domain = parsed.netloc.replace("www.", "")
                if parsed.netloc and "facebook" not in parsed.netloc and domain not in INVALID_WEBSITES:
                    return parsed.scheme + "://" + parsed.netloc
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        if parsed.netloc and "facebook.com" not in parsed.netloc and domain not in INVALID_WEBSITES:
            return parsed.scheme + "://" + parsed.netloc
    except Exception:
        pass
    return ""


async def _extract_brands_from_search_page(page):
    await asyncio.sleep(5)
    await _scroll_to_load(page, scrolls=6)
    await asyncio.sleep(3)

    all_links = await page.evaluate(
        "() => Array.from(document.querySelectorAll('a[href]')).map(a => a.href)"
    )

    print(f"    [DEBUG] Total links on page: {len(all_links)}")

    brand_pages = {}
    redirect_urls = []

    for link in all_links:
        if _is_brand_page_url(link):
            parsed = urlparse(link)
            username = parsed.path.strip("/").split("/")[0]
            if username not in brand_pages:
                brand_pages[username] = {
                    "username": username,
                    "page_url": f"https://www.facebook.com/{username}/",
                    "website_url": "",
                }
        if "l.facebook.com/l.php" in link:
            website = _extract_website_from_redirect(link)
            if website:
                redirect_urls.append(website)

    print(f"    [DEBUG] Brand pages found: {list(brand_pages.keys())}")
    print(f"    [DEBUG] Websites found: {redirect_urls[:5]}")

    brand_list = list(brand_pages.values())
    seen_websites = list(dict.fromkeys(redirect_urls))

    for i, brand in enumerate(brand_list):
        if i < len(seen_websites):
            brand["website_url"] = seen_websites[i]

    return brand_list


async def _get_ad_count_and_details(page, username):
    url = _build_page_search_url(username)
    details = {
        "ad_count": 0,
        "oldest_ad_days": 0,
        "ad_formats": "image",
        "image_only": True,
        "is_verified": False,
        "website_url": "",
        "cta_primary": "unknown",
    }

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)
        await _scroll_to_load(page, scrolls=3)

        data = await page.evaluate("""
            () => {
                const body = document.body.innerText;
                const result = {
                    ad_count: 0,
                    oldest_ad_days: 0,
                    has_video: false,
                    has_image: false,
                    is_verified: false,
                    website_urls: [],
                    cta_types: [],
                };

                const countPatterns = [
                    /(\\d+)\\s+results?/i,
                    /showing\\s+(\\d+)/i,
                    /(\\d+)\\s+ads?\\s+found/i,
                    /(\\d+)\\s+active\\s+ads?/i,
                ];
                for (const pattern of countPatterns) {
                    const m = body.match(pattern);
                    if (m) { result.ad_count = parseInt(m[1]); break; }
                }

                if (result.ad_count === 0) {
                    const cards = document.querySelectorAll('[role="article"]');
                    if (cards.length > 0) result.ad_count = cards.length;
                }

                if (body.includes('Verified Page')) result.is_verified = true;

                const dateRegex = /Started running on ([A-Za-z]+ \\d+,\\s*\\d{4})/g;
                const dates = [];
                let m;
                while ((m = dateRegex.exec(body)) !== null) {
                    try { dates.push(new Date(m[1])); } catch(e) {}
                }
                if (dates.length > 0) {
                    const oldest = Math.min(...dates.map(d => d.getTime()));
                    result.oldest_ad_days = Math.floor(
                        (Date.now() - oldest) / (1000 * 60 * 60 * 24)
                    );
                }

                result.has_video = document.querySelectorAll('video').length > 0;
                result.has_image = document.querySelectorAll('img[src*="fbcdn"]').length > 0;

                document.querySelectorAll('a[href*="l.facebook.com/l.php"]').forEach(a => {
                    const match = a.href.match(/[?&]u=([^&]+)/);
                    if (match) {
                        try {
                            const url = decodeURIComponent(match[1]);
                            const parsed = new URL(url);
                            if (!parsed.hostname.includes('facebook')) {
                                result.website_urls.push(parsed.protocol + '//' + parsed.hostname);
                            }
                        } catch(e) {}
                    }
                });

                ['Shop Now','Learn More','Send Message','Get Quote','Sign Up','Book Now'].forEach(cta => {
                    if (body.includes(cta)) result.cta_types.push(cta);
                });

                return result;
            }
        """)

        details["ad_count"]       = data.get("ad_count", 0)
        details["oldest_ad_days"] = data.get("oldest_ad_days", 0)
        details["is_verified"]    = data.get("is_verified", False)

        fmts = []
        if data.get("has_image"): fmts.append("image")
        if data.get("has_video"): fmts.append("video")
        details["ad_formats"] = "/".join(fmts) if fmts else "image"
        details["image_only"] = data.get("has_image") and not data.get("has_video")

        websites = list(dict.fromkeys(data.get("website_urls", [])))
        if websites:
            details["website_url"] = websites[0]

        ctas = data.get("cta_types", [])
        details["cta_primary"] = ctas[0] if ctas else "unknown"

    except Exception as e:
        print(f"      [WARN] {username}: {e}")

    return details


async def scrape_keyword(browser, keyword):
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        storage_state=None,
    )
    page = await context.new_page()
    results = []

    try:
        url = _build_search_url(keyword)
        print(f"  → Loading: {url[:80]}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await _random_delay("after_navigation")

        brands = await _extract_brands_from_search_page(page)
        print(f"  → Found {len(brands)} brand pages on search results")

        for brand in brands[:MAX_BRANDS_PER_KEYWORD * 2]:
            if len(results) >= MAX_BRANDS_PER_KEYWORD:
                break

            username = brand["username"]
            print(f"    Checking: {username}")
            await _random_delay("between_brands")

            details = await _get_ad_count_and_details(page, username)
            website_url = details.get("website_url") or brand.get("website_url", "")

            ad_count = details.get("ad_count", 0)
            if ad_count == 0:
                ad_count = 5
                details["ad_count_note"] = "count not extracted, verify manually"

            if ad_count < FILTERS["min_ads"] or ad_count > FILTERS["max_ads"]:
                print(f"      SKIP: {ad_count} ads")
                continue

            if FILTERS["skip_verified"] and details.get("is_verified"):
                print(f"      SKIP: verified")
                continue

            if FILTERS["require_website"] and not website_url:
                print(f"      SKIP: no website")
                continue

            result = {
                "keyword":          keyword,
                "brand_name":       username,
                "facebook_page_id": username,
                "facebook_url":     brand["page_url"],
                "website_url":      website_url,
                "instagram_handle": "",
                "active_ad_count":  ad_count,
                "oldest_ad_days":   details.get("oldest_ad_days", 0),
                "ad_formats":       details.get("ad_formats", "image"),
                "image_only":       details.get("image_only", True),
                "cta_primary":      details.get("cta_primary", "unknown"),
                "is_verified":      details.get("is_verified", False),
            }
            results.append(result)
            print(f"      KEEP: {ad_count} ads | {details.get('oldest_ad_days',0)}d | {website_url}")

    except Exception as e:
        print(f"  [ERROR] '{keyword}': {e}")
    finally:
        await context.close()

    return results