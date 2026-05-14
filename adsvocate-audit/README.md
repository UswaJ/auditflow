# ADSVOCATE AUDIT PIPELINE
## Automated Cold Outreach Audit Tool — Completely Free

---

## WHAT IT DOES

1. **Searches Meta Ads Library** (Pakistan, active ads) for your keywords
2. **Filters qualifying brands** (3–25 active ads, no verified badge, has website)
3. **Audits each website** — checks Meta Pixel, GTM, Google Ads tag, cookies, dataLayer
4. **Scrapes Instagram** — followers, last post date, activity status
5. **Checks Google Ads Transparency** — whether they're also running Google Ads
6. **Generates the DM** — exact pitch based on what's broken, under 100 words
7. **Saves everything to CSV** — one row per brand, all fields

---

## SETUP (one-time, ~5 minutes)

### 1. Install Python 3.10+
If not already installed: https://python.org/downloads

### 2. Install dependencies
```bash
cd adsvocate-audit
pip install -r requirements.txt
playwright install chromium
```

### 3. Edit config.py
Add the keywords you want to search. That's it.

---

## HOW TO RUN

### Full pipeline (all keywords in config.py):
```bash
python main.py
```

### Specific keywords only:
```bash
python main.py "lawn suits" "whitening serum"
```

### Audit a single website directly:
```bash
python main.py --website https://brandname.pk
```

### Headless mode (browser runs in background, faster):
```bash
python main.py --headless
```

---

## OUTPUT

Results save to: `results/audit_YYYYMMDD_HHMMSS.csv`

Each row = one brand. Columns include:
- Brand name, Facebook URL, Website URL, Instagram handle
- Ad count, oldest ad age, formats, CTA type
- Instagram followers, activity status, last post days ago
- Pixel fires homepage / product / checkout
- GTM present, dataLayer empty or not, ecommerce events
- Google Ads tag present, cookies (_fbp, _gcl_au, _ga)
- Contact email found on website
- WhatsApp link found on website
- Google Ads Transparency result
- **Pitch type** (A1/A2/A3/A4/A5/B1/B2/C)
- **DM** (ready to send, under 100 words)

Open in Google Sheets for easy filtering and outreach management.

---

## PITCH TYPES

| Code | What it means |
|------|--------------|
| A1   | No tracking at all — running ads completely blind |
| A2   | No Meta Pixel installed |
| A3   | Pixel fires homepage only, drops at checkout |
| A4   | GTM installed but empty — no events configured |
| A5   | Google Ads running but no conversion tag |
| B1   | Image-only ads, no video, running 60+ days |
| B2   | Instagram inactive 45+ days while ads are running |
| C    | Tracking clean — pivot to creative/strategy angle |

---

## IMPORTANT NOTES

**Meta Ads Library:** The browser opens visibly so you can monitor what's happening.
Facebook sometimes shows login prompts or CAPTCHAs. If it does:
- Log into Facebook in the browser that opens
- The script will wait and continue automatically

**Instagram:** Public profiles work without login. If Instagram redirects to login,
the scraper skips that field and marks instagram_error.

**Rate limits:** Built-in random delays between requests. Default is 10 brands max
per keyword. Do not reduce the delays — Meta and Instagram will block you.

**DM quality:** Review every DM before sending. The generator uses the exact
pitch angles from your audit workflow doc. Always verify the finding is accurate
before DMing — the website audit catches ~85% of tracking issues correctly.

---

## FOLDER STRUCTURE

```
adsvocate-audit/
├── main.py                    ← Run this
├── config.py                  ← Edit keywords and filters here
├── requirements.txt
├── scrapers/
│   ├── meta_ads.py            ← Meta Ads Library discovery
│   ├── website.py             ← Technical website audit
│   ├── instagram.py           ← Instagram profile scraper
│   └── google_transparency.py ← Google Ads Transparency check
├── generator/
│   └── dm.py                  ← DM generation (no API, free)
├── utils/
│   └── reporter.py            ← CSV output
└── results/                   ← Output files appear here
```

---

## COST

Zero. Completely free.
- Playwright: free, open source
- DM generator: template-based, no API
- Meta Ads Library: public, no API needed
- Instagram: public profiles, no API
- Google Transparency: public, no API

---

## DAILY WORKFLOW (from your audit doc)

10 brands = ~90 minutes manually → ~15-20 minutes with this tool (mostly waiting for pages to load).

1. `python main.py "your keyword"` 
2. Watch the terminal output
3. Open the CSV in Google Sheets
4. Review DMs (edit if needed)
5. Send from Instagram on your phone following anti-spam protocol:
   - Follow first
   - Like 1–2 posts
   - Wait 30 minutes
   - Send DM
   - Max 10 DMs per day from new account
