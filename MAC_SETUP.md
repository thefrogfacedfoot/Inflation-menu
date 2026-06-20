# Foodpanda Scraper - Mac Local Setup

## Why This Will Work
Your Mac has a **residential IP** (not cloud/VPN) which **won't be blocked** by Foodpanda's anti-bot system. The cloud container was getting blocked because it's an IP they recognize as automated.

## Setup on Your Mac

### 1. Install Dependencies
```bash
pip install playwright beautifulsoup4 requests sqlite3
playwright install chromium
```

### 2. Copy These Files to Your Mac
Keep only these files:
- `live_scraper.py` ← **Main scraper**
- `verify_scrape.py` ← Check results
- `uifpi.db` ← Database

Delete all `test_*.py`, `debug_*.py`, etc. files (they don't work anyway)

### 3. Run the Scraper
```bash
cd /path/to/Inflation-menu
python live_scraper.py
```

### 4. Verify Results
```bash
python verify_scrape.py
```

---

## Expected Output

**First run (test mode - 1 restaurant):**
```
UIFPI Collection Run: 2026-06-09
Testing: 1 restaurant(s)

  Loading Rubato...
  Found X add-to-cart buttons
  ✓ Rubato (foodpanda): X items

Done. Check uifpi.db for results.
```

**Then check results:**
```
📊 SCRAPER RESULTS
==================================================
Total records in database: X
Records from today: X items

✓ SUCCESS! Collected X menu items
```

---

## Run Full Scrape (All 30 Restaurants)

Edit `live_scraper.py` line ~270:

**Change:**
```python
test_targets = TARGETS[:1]  # Only first restaurant
```

**To:**
```python
test_targets = TARGETS  # All restaurants
```

Then run:
```bash
python live_scraper.py
```

Estimated time: ~60-90 minutes (2-3 min per restaurant)

---

## Troubleshooting

**Still getting CAPTCHA?**
- Use a VPN with residential IP
- Wait 10 minutes between runs (avoid rate limiting)
- Try running during off-peak hours

**Database locked?**
- Close any other instances of the script
- Delete `uifpi.db` to start fresh

**Getting fewer items than expected?**
- Some restaurants may have fewer menu items on Foodpanda
- Network timeouts are normal - just re-run

---

## Commands Reference

```bash
# Test with 1 restaurant
python live_scraper.py

# Change to all restaurants, then run again
python live_scraper.py

# Check how many items were collected
python verify_scrape.py

# View database directly
sqlite3 uifpi.db "SELECT COUNT(*) FROM prices;"
```
