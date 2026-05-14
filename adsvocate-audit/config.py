# ============================================================
#  ADSVOCATE AUDIT PIPELINE — CONFIG
#  Edit this file to control keywords, filters, and delays.
# ============================================================

# --- Keywords to search in Meta Ads Library ---
# Add/remove any keywords. Each runs as a separate search.
KEYWORDS = [
    "lawn suits",
    "kurta",
    "whitening serum",
    "face wash",
    "skincare",
    "burger restaurant",
    "bakery",
    "dental clinic",
    "solar panels",
    "online course",
]

# --- Brand filters (which brands to KEEP) ---
FILTERS = {
    "country": "PK",          # Country code for Meta Ads Library
    "min_ads": 3,             # Minimum active ads to keep
    "max_ads": 25,            # Maximum active ads (too many = big agency)
    "skip_verified": True,    # Skip blue-tick verified pages
    "require_website": True,  # Skip brands with no website in their ads
}

# --- Delays (seconds) to avoid bot detection ---
# Uses random range: (min, max)
DELAYS = {
    "between_keywords": (5, 10),
    "between_brands": (3, 7),
    "after_navigation": (2, 4),
    "scroll_pause": 1.5,
}

# --- How many brands to audit per keyword ---
MAX_BRANDS_PER_KEYWORD = 8

# --- Output ---
OUTPUT_DIR = "results"

# --- Browser settings ---
HEADLESS = False   # False = you see the browser. Set True for background runs.
SLOW_MO = 50      # Milliseconds between Playwright actions (human-like)

# --- Funnel pages to check for tracking ---
# Common paths to check for ViewContent / AddToCart / Purchase firing
FUNNEL_PATHS = {
    "product_selectors": [
        "a[href*='/product']",
        "a[href*='/products']",
        "a[href*='/shop']",
        "a[href*='/item']",
        ".product-card a",
        ".product-item a",
        ".product a",
    ],
    "cart_selectors": [
        "a[href*='/cart']",
        "button[class*='cart']",
        "button[class*='add-to-cart']",
        "[data-action*='cart']",
    ],
    "checkout_selectors": [
        "a[href*='/checkout']",
        "button[class*='checkout']",
    ],
    "contact_selectors": [
        "a[href*='/contact']",
        "a[href*='/contact-us']",
        "a[href*='#contact']",
        "a:text('contact')",
        "a:text('Contact')",
    ],
}
