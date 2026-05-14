"""
REPORTER
Saves audit results to CSV in real time (one row per brand, appended as we go).
Also prints a rich summary table to terminal.
"""

import csv
import os
from datetime import datetime
from pathlib import Path


# All columns in the CSV, in display order
COLUMNS = [
    # Identification
    "keyword", "brand_name", "facebook_url", "website_url",
    "instagram_handle", "instagram_url",
    # Meta Ads Library data
    "active_ad_count", "oldest_ad_days", "ad_formats", "image_only", "cta_primary",
    # Instagram
    "ig_followers", "ig_followers_raw", "ig_post_count",
    "ig_last_post_days_ago", "ig_activity", "ig_bio", "ig_link_in_bio",
    # Website technical audit
    "pixel_fires_homepage", "pixel_fires_product", "pixel_drops_at_checkout",
    "pixel_viewcontent", "pixel_addtocart", "pixel_purchase",
    "fbq_in_code", "pixel_id",
    "gtm_present", "datalayer_present", "datalayer_empty", "datalayer_has_ecommerce",
    "datalayer_events",
    "google_ads_tag_present", "gads_id", "ga4_present", "ga4_id",
    "cookie_fbp", "cookie_gcl_au", "cookie_ga",
    # Contact
    "contact_email", "whatsapp_link", "contact_lead_fires",
    # Summary flags
    "has_meta_pixel", "has_gtm", "has_google_ads_tag", "tracking_clean",
    # Google Ads Transparency
    "google_ads_running", "google_ad_types",
    # Audit errors
    "audit_error", "instagram_error",
    # Output
    "pitch_type", "dm",
]


def _format_value(v) -> str:
    if isinstance(v, bool):
        return "YES" if v else "NO"
    if isinstance(v, list):
        return "|".join(str(x) for x in v)
    if v is None:
        return ""
    return str(v)


class Reporter:
    def __init__(self, output_path: str):
        self.output_path = output_path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_csv()
        self.count = 0

    def _initialize_csv(self):
        """Write header row."""
        with open(self.output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            writer.writeheader()

    def append(self, brand: dict):
        """Append one brand's data to the CSV."""
        row = {col: _format_value(brand.get(col, "")) for col in COLUMNS}
        with open(self.output_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            writer.writerow(row)
        self.count += 1

    def print_summary(self, brand: dict):
        """Print a compact audit summary to terminal."""
        print(f"\n  {'─' * 55}")
        print(f"  BRAND : {brand.get('brand_name', '?')}")
        print(f"  SITE  : {brand.get('website_url', '?')}")
        print(f"  IG    : @{brand.get('instagram_handle', '?')} | "
              f"{brand.get('ig_followers_raw', '?')} followers | "
              f"{brand.get('ig_activity', '?')}")
        print(f"  ADS   : {brand.get('active_ad_count', '?')} active | "
              f"{brand.get('oldest_ad_days', '?')}d old | "
              f"Formats: {brand.get('ad_formats', '?')}")
        print(f"  META PIXEL : {'✓' if brand.get('has_meta_pixel') else '✗'} | "
              f"Checkout drop: {'YES' if brand.get('pixel_drops_at_checkout') else 'NO'}")
        print(f"  GTM        : {'✓' if brand.get('has_gtm') else '✗'} | "
              f"Empty: {'YES' if brand.get('datalayer_empty') else 'NO'}")
        print(f"  G-ADS TAG  : {'✓' if brand.get('has_google_ads_tag') else '✗'} | "
              f"G-ADS running: {'YES' if brand.get('google_ads_running') else 'NO'}")
        print(f"  PITCH TYPE : {brand.get('pitch_type', '?')}")
        print(f"  CONTACT    : {brand.get('contact_email', 'not found')}")
        print(f"\n  DM DRAFT:\n  {brand.get('dm', '')}")
        print(f"  {'─' * 55}")
