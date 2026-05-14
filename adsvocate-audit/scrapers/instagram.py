"""
INSTAGRAM PROFILE SCRAPER
Scrapes public Instagram profiles without requiring login.
Gets: followers, following, post count, last post date, bio, link in bio.
"""

import asyncio
import re
import json
import random
from datetime import datetime
from playwright.async_api import Page
from config import DELAYS


async def _rand_sleep():
    lo, hi = DELAYS.get("after_navigation", (2, 4))
    await asyncio.sleep(random.uniform(lo, hi))


async def scrape_instagram_profile(page: Page, handle: str) -> dict:
    """
    Scrape a public Instagram profile.
    Returns dict with follower count, post count, last post date, etc.
    """
    if not handle:
        return {"instagram_error": "no handle provided"}

    handle = handle.lstrip("@").strip()
    url = f"https://www.instagram.com/{handle}/"

    result = {
        "instagram_handle": handle,
        "instagram_url": url,
        "ig_followers": 0,
        "ig_followers_raw": "",
        "ig_following": 0,
        "ig_post_count": 0,
        "ig_last_post_days_ago": 999,  # 999 = unknown / very old
        "ig_bio": "",
        "ig_link_in_bio": "",
        "ig_is_business": False,
        "ig_activity": "UNKNOWN",   # ACTIVE / SLOW / INACTIVE
        "instagram_error": "",
    }

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await _rand_sleep()

        # Instagram may show login prompt. Try to dismiss or work around it.
        # The page still renders profile data in meta tags and JSON-LD even without login.
        
        # Strategy 1: Extract from JSON-LD or __additionalData in page source
        page_source = await page.content()

        # Try to get data from window._sharedData or meta tags
        insta_data = await page.evaluate("""
            () => {
                const result = {
                    followers: 0,
                    following: 0,
                    posts: 0,
                    bio: '',
                    external_url: '',
                    is_business: false,
                    username: '',
                };

                // Strategy 1: Meta tags (most reliable without login)
                const metaTags = document.querySelectorAll('meta[property], meta[name]');
                let description = '';
                metaTags.forEach(tag => {
                    const prop = tag.getAttribute('property') || tag.getAttribute('name');
                    const content = tag.getAttribute('content') || '';
                    if (prop === 'og:description') description = content;
                    if (prop === 'og:title') result.username = content;
                });

                // Instagram og:description format:
                // "X Followers, Y Following, Z Posts - See Instagram photos..."
                if (description) {
                    const followerMatch = description.match(/([\\d,.]+)\\s*Followers?/i);
                    const followingMatch = description.match(/([\\d,.]+)\\s*Following/i);
                    const postsMatch = description.match(/([\\d,.]+)\\s*Posts?/i);
                    if (followerMatch) result.followers = followerMatch[1];
                    if (followingMatch) result.following = followingMatch[1];
                    if (postsMatch) result.posts = postsMatch[1];
                }

                // Strategy 2: Try script tags with JSON data
                const scripts = document.querySelectorAll('script[type="application/json"]');
                scripts.forEach(s => {
                    try {
                        const data = JSON.parse(s.textContent);
                        // Look for follower count deep in the data
                        const str = JSON.stringify(data);
                        const fMatch = str.match(/"edge_followed_by":\\{"count":(\\d+)\\}/);
                        if (fMatch && result.followers === 0) result.followers = fMatch[1];
                    } catch(e) {}
                });

                // Strategy 3: Visible page text
                const body = document.body.innerText;
                if (result.followers === 0) {
                    // Look for "X followers" pattern in visible text
                    const visibleMatch = body.match(/([\\d,\\.]+[KMk]?)\\s*followers/i);
                    if (visibleMatch) result.followers = visibleMatch[1];
                }

                // Bio: look for profile description in JSON-LD
                const jsonLd = document.querySelector('script[type="application/ld+json"]');
                if (jsonLd) {
                    try {
                        const ld = JSON.parse(jsonLd.textContent);
                        result.bio = ld.description || '';
                        result.external_url = ld.url || '';
                    } catch(e) {}
                }

                return result;
            }
        """)

        result["ig_bio"] = insta_data.get("bio", "")
        result["ig_link_in_bio"] = insta_data.get("external_url", "")
        result["ig_is_business"] = insta_data.get("is_business", False)

        # Parse follower count (handles "1.2K", "12.5K", "1.2M" formats)
        raw_followers = str(insta_data.get("followers", "0"))
        result["ig_followers_raw"] = raw_followers
        result["ig_followers"] = _parse_follower_count(raw_followers)

        raw_posts = str(insta_data.get("posts", "0"))
        result["ig_post_count"] = _parse_follower_count(raw_posts)

        # ── Last post date ───────────────────────────────────────────────────
        # Try to find timestamps in the page (requires some posts to be visible)
        last_post_days = await page.evaluate("""
            () => {
                // Instagram shows time as "ago" text or in datetime attributes
                const timeEls = document.querySelectorAll('time[datetime]');
                const timestamps = [];
                timeEls.forEach(el => {
                    const dt = el.getAttribute('datetime');
                    if (dt) timestamps.push(new Date(dt).getTime());
                });
                if (timestamps.length === 0) return -1;
                const mostRecent = Math.max(...timestamps);
                const days = Math.floor((Date.now() - mostRecent) / (1000 * 60 * 60 * 24));
                return days;
            }
        """)

        if last_post_days >= 0:
            result["ig_last_post_days_ago"] = last_post_days
        else:
            # If we couldn't find timestamps, check if posts are visible at all
            result["ig_last_post_days_ago"] = 999  # Unknown

        # ── Activity classification ──────────────────────────────────────────
        days_ago = result["ig_last_post_days_ago"]
        result["ig_activity"] = _classify_activity(days_ago)

    except Exception as e:
        result["instagram_error"] = str(e)

    return result


def _parse_follower_count(raw: str) -> int:
    """Convert '1.2K', '12.5K', '1.2M', '12,345' to integer."""
    if not raw:
        return 0
    raw = str(raw).strip().replace(",", "")
    try:
        if raw.endswith("K") or raw.endswith("k"):
            return int(float(raw[:-1]) * 1000)
        elif raw.endswith("M") or raw.endswith("m"):
            return int(float(raw[:-1]) * 1_000_000)
        else:
            return int(float(raw))
    except (ValueError, TypeError):
        return 0


def _classify_activity(days_ago: int) -> str:
    """ACTIVE = posted in last 7 days. SLOW = 7-45 days. INACTIVE = 45+ days."""
    if days_ago == 999:
        return "UNKNOWN"
    if days_ago <= 7:
        return "ACTIVE"
    if days_ago <= 45:
        return "SLOW"
    return "INACTIVE"


async def extract_instagram_from_website(page: Page, website_url: str) -> str:
    """
    Visit a brand's website and look for Instagram link in footer/nav.
    Returns handle string or empty string.
    """
    try:
        await page.goto(website_url, wait_until="domcontentloaded", timeout=20000)
        handles = await page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a[href*="instagram.com"]'));
                const handles = [];
                links.forEach(a => {
                    const match = a.href.match(/instagram\\.com\\/([\\w.]+)\\/?/);
                    if (match && match[1] && !['p', 'explore', 'accounts'].includes(match[1])) {
                        handles.push(match[1]);
                    }
                });
                return [...new Set(handles)];
            }
        """)
        return handles[0] if handles else ""
    except Exception:
        return ""
