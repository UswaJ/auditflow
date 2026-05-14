"""
DM GENERATOR
Generates the cold outreach DM using the exact pitch angles from the
Adsvocate Cold Outreach Audit Workflow document.

100% template-based. No API required. Completely free.

DM structure (from Part 10 of the doc):
  Sentence 1: Specific finding from audit
  Sentence 2: What it costs them in plain language
  Sentence 3: Soft offer
  Ending: One question, answerable in 10 seconds
  Total: under 100 words
"""


# ── Pitch type determination ──────────────────────────────────────────────────

def determine_pitch_type(brand: dict) -> str:
    """
    Returns pitch type label based on audit findings.
    Priority order: most severe finding wins.
    """
    # Type A: Broken tracking (highest value)
    if not brand.get("has_meta_pixel") and not brand.get("has_google_ads_tag"):
        return "A1_no_tracking_at_all"

    if not brand.get("has_meta_pixel"):
        return "A2_no_meta_pixel"

    if brand.get("pixel_drops_at_checkout"):
        return "A3_pixel_drops_checkout"

    if brand.get("has_gtm") and brand.get("datalayer_empty"):
        return "A4_gtm_empty"

    if not brand.get("has_google_ads_tag") and brand.get("google_ads_running"):
        return "A5_google_ads_blind"

    if not brand.get("cookie_gcl_au") and brand.get("google_ads_running"):
        return "A5_google_ads_blind"

    # Type B: Weak strategy
    if (brand.get("image_only") and brand.get("oldest_ad_days", 0) >= 60):
        return "B1_image_only_no_video"

    if brand.get("ig_activity") in ("INACTIVE", "SLOW") and brand.get("ig_last_post_days_ago", 999) >= 45:
        return "B2_instagram_dead_ads_running"

    # Dual platform with tracking issues
    if brand.get("google_ads_running") and brand.get("active_ad_count", 0) > 0:
        if not brand.get("tracking_clean"):
            return "A1_no_tracking_at_all"  # Running both, tracking broken

    # Type C: Not running ads (shouldn't reach here — filtered in Meta scraper)
    return "C_no_issues_found"


# ── DM templates by pitch type ────────────────────────────────────────────────

def _get_oldest_ad_signal(brand: dict) -> str:
    days = brand.get("oldest_ad_days", 0)
    if days >= 90:
        return f"same ad running {days} days"
    if days >= 30:
        return f"ad running {days} days"
    return "active ad spend"


def generate_dm(brand: dict, pitch_type: str) -> str:
    """
    Generate the cold outreach DM for a brand based on pitch type.
    Returns string under 100 words. No portfolio, no agency mention.
    """

    name = brand.get("brand_name", "")
    cta  = brand.get("cta_primary", "Shop Now")
    oldest = _get_oldest_ad_signal(brand)
    ig_days = brand.get("ig_last_post_days_ago", 999)

    # ── A1: No tracking at all (running ads blind) ───────────────────────────
    if pitch_type == "A1_no_tracking_at_all":
        return (
            f"You have no pixel or conversion tag installed — "
            f"your Meta and Google campaigns are spending with zero data on who's buying. "
            f"Every sale you generate is invisible to both algorithms. "
            f"Want me to show you exactly what's missing and how to fix it?"
        )

    # ── A2: No Meta Pixel ────────────────────────────────────────────────────
    if pitch_type == "A2_no_meta_pixel":
        return (
            f"Your Meta Pixel isn't installed. "
            f"If you start or scale Facebook ads right now, "
            f"Meta has no way to learn who buys from you — "
            f"so it optimises toward people who land, not people who buy. "
            f"Want me to send you the fix?"
        )

    # ── A3: Pixel fires homepage only, drops at checkout ────────────────────
    if pitch_type == "A3_pixel_drops_checkout":
        return (
            f"Your Meta Pixel fires on the homepage but stops at checkout. "
            f"Every purchase you make is invisible to the algorithm. "
            f"Meta's Smart Bidding is optimising toward browsers, not buyers — "
            f"which means your CPA is higher than it should be. "
            f"Want me to send you the exact fix?"
        )

    # ── A4: GTM installed but empty ──────────────────────────────────────────
    if pitch_type == "A4_gtm_empty":
        return (
            f"Google Tag Manager is installed on your site but it's empty — "
            f"no purchase events, no lead events, nothing configured. "
            f"Your GA4 shows sessions but can't see revenue, "
            f"and Google Ads has no conversion signal to work from. "
            f"Want me to send you what needs to be set up?"
        )

    # ── A5: Google Ads running but no conversion tag ─────────────────────────
    if pitch_type == "A5_google_ads_blind":
        return (
            f"Your Google Ads account has no conversion tracking active. "
            f"Every click you pay for disappears into a void — "
            f"Smart Bidding is guessing because it can't see a single purchase. "
            f"Want me to send you the setup that fixes this?"
        )

    # ── B1: Image-only ads, no video, running 60+ days ──────────────────────
    if pitch_type == "B1_image_only_no_video":
        return (
            f"Every ad in your account is a static image — "
            f"same {oldest}. "
            f"Meta uses video engagement to find buyers who look like your customers. "
            f"Without it, your targeting is working with one hand tied behind its back. "
            f"Want me to send you what a simple video test setup looks like?"
        )

    # ── B2: Instagram dead, ads still running ───────────────────────────────
    if pitch_type == "B2_instagram_dead_ads_running":
        return (
            f"Your ads are sending people to your Instagram "
            f"and it hasn't posted in {ig_days if ig_days < 999 else '45+'} days. "
            f"An empty feed tells potential customers you're no longer active. "
            f"Your ad spend and your content need to work together. "
            f"Want me to send you how other brands fix this?"
        )

    # ── C: Tracking clean — pivot to campaign strategy ───────────────────────
    if pitch_type == "C_no_issues_found":
        if brand.get("oldest_ad_days", 0) >= 90:
            return (
                f"Your tracking is set up correctly — that's rare. "
                f"What I did notice: your {oldest} is running with no fresh creative. "
                f"At this frequency, Meta's algorithm has seen your audience "
                f"nearly every angle of that ad. "
                f"Want me to send you what a creative refresh test looks like?"
            )
        return (
            f"Checked your setup — tracking looks solid. "
            f"Are you testing different ad angles or running the same creative across all ad sets?"
        )

    return "DM template not matched. Review audit findings manually."


# ── Main entry point ──────────────────────────────────────────────────────────

def generate(brand: dict) -> tuple[str, str]:
    """
    Generate pitch type + DM for a brand.
    Returns (pitch_type, dm_text).
    """
    pitch_type = determine_pitch_type(brand)
    dm = generate_dm(brand, pitch_type)
    return pitch_type, dm
