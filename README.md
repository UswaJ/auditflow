# AuditFlow

Automated ad tracking audit and cold outreach pipeline for Pakistani e-commerce brands.

Finds brands running Meta Ads, audits their website tracking setup, checks their Instagram activity and Google Ads presence, classifies what's broken, and generates a ready-to-send personalised DM — all without any manual steps between discovery and output.

---

## What it does

Most small e-commerce brands in Pakistan are running Meta or Google Ads with broken or missing tracking. They're spending money with zero conversion data going back to the algorithm. AuditFlow finds these brands automatically and tells you exactly what's wrong with each one.

**Full pipeline:**

1. Searches the Meta Ads Library (Pakistan, active ads) for your keywords
2. Filters qualifying brands — 3 to 25 active ads, no verified badge, has a website
3. Audits each website — Meta Pixel, GTM, Google Ads tag, dataLayer, conversion events across homepage, product page, and checkout
4. Scrapes Instagram — follower count, last post date, activity status
5. Checks Google Ads Transparency — whether the brand is also running Google Ads
6. Classifies the finding into one of 8 pitch types
7. Generates a personalised cold outreach DM under 100 words, ready to send
8. Saves everything to a timestamped CSV

---

## Output

Each run produces a CSV in `results/` — one row per brand.

![AuditFlow CSV Output](screenshots/csv_output.png)

**Fields include:**
- Brand name, Facebook URL, website URL, Instagram handle
- Active ad count, oldest ad age, formats, CTA type
- Instagram followers, activity status, last post (days ago)
- Pixel: fires homepage / product page / checkout
- GTM: present, dataLayer empty or configured, ecommerce events
- Google Ads tag, conversion tag, GA4
- Cookies: `_fbp`, `_gcl_au`, `_ga`
- Contact email and WhatsApp link found on website
- Google Ads Transparency result
- **Pitch type** — what's broken
- **DM** — ready to send

---

## Pitch types

| Code | Finding |
|------|---------|
| A1 | No tracking at all — running ads completely blind |
| A2 | No Meta Pixel installed |
| A3 | Pixel fires homepage only, drops at checkout |
| A4 | GTM installed but empty — no events configured |
| A5 | Google Ads running but no conversion tag |
| B1 | Image-only ads running 60+ days, no video |
| B2 | Instagram inactive 45+ days while ads are running |
| C  | Tracking clean — pivot to creative/strategy angle |

Priority order: most severe finding wins. A1 beats everything.

---

## Tech stack

- **Python 3.10+**
- **Playwright (async)** — browser automation for Meta Ads Library, Instagram, Google Transparency
- **Anti-bot measures** — randomised delays, incognito context, human-like interaction via `slow_mo`
- **Template-based DM generator** — no API, no cost, runs entirely offline
- **CSV reporter** — structured output, opens directly in Google Sheets

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/UswaJ/auditflow.git
cd auditflow
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure keywords
Edit `config.py` and add the product categories you want to search:
```python
KEYWORDS = [
    "lawn suits",
    "whitening serum",
    "online course",
]
```

---

## Usage

### Run the full pipeline
```bash
python main.py
```

### Target specific keywords
```bash
python main.py "skincare" "bakery"
```

### Audit a single website directly
```bash
python main.py --website https://brandname.pk
```

### Run headless (browser in background)
```bash
python main.py --headless
```

---

## Manual workflow this replaces

| Task | Manual time | With AuditFlow |
|------|-------------|----------------|
| 10 brands audited | ~90 minutes | 15–20 minutes |
| DMs written | ~30 minutes | 0 minutes |
| Spreadsheet filled | ~20 minutes | 0 minutes |

---

## Important notes

**Meta Ads Library** opens visibly so you can monitor it. Facebook sometimes shows a login prompt or CAPTCHA — log in when it does, the script waits and continues automatically.

**Instagram** works on public profiles without login. If it redirects to login, the scraper skips that field and marks `instagram_error`.

**Rate limits** — built-in random delays between requests. Default is 8 brands per keyword. Do not reduce the delays.

**DM accuracy** — the website audit catches ~85% of tracking issues correctly. Review each DM before sending and verify the finding is accurate.

---

## Folder structure

```
auditflow/
├── main.py                      ← Entry point
├── config.py                    ← Keywords, filters, delays
├── requirements.txt
├── scrapers/
│   ├── meta_ads.py              ← Meta Ads Library discovery
│   ├── website.py               ← Technical website audit
│   ├── instagram.py             ← Instagram profile scraper
│   └── google_transparency.py  ← Google Ads Transparency check
├── generator/
│   └── dm.py                    ← DM generation (no API, free)
├── utils/
│   └── reporter.py              ← CSV output
└── results/                     ← Output files appear here
```

---

## Built by

Uswa Jamil — CS Student @ COMSATS University Islamabad  
[linkedin.com/in/uswa-jamil-683909303](https://linkedin.com/in/uswa-jamil-683909303) · [github.com/UswaJ](https://github.com/UswaJ)
