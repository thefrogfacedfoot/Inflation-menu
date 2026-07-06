# Running the price scraper (US) — setup guide

Hi! Thanks for helping with my research project. This script visits ~13
US restaurant websites (Wendy's, Olive Garden, IHOP, etc.), records the
menu prices they publicly display, and saves them to a small database
file that you send back to me. It doesn't log into anything, doesn't
touch your accounts, and only reads public menu pages. One run takes
roughly 15–30 minutes and you can use your computer normally while it
goes.

You only need to do the **Setup** section once. After that, each run is
one command.

---

## Setup (one time, ~15 minutes)

### 1. Install Python

- Go to https://www.python.org/downloads/ and click the big yellow
  **Download Python** button (any version 3.9 or newer is fine).
- Run the installer.
- **Windows only — important:** on the first installer screen, tick the
  checkbox **"Add python.exe to PATH"** before clicking Install.
- Mac: just click through the installer.

### 2. Get the script

I'll send you one file: `live_scraper.py`. Save it into a new folder,
e.g. a folder called `scraper` inside your Documents.

### 3. Open a terminal in that folder

- **Windows:** open the `scraper` folder in File Explorer, click the
  address bar at the top, type `cmd`, press Enter. A black window opens.
- **Mac:** open Terminal (Cmd+Space, type "Terminal", Enter), then type
  `cd Documents/scraper` and press Enter.

Everything below gets typed into this window.

### 4. Install the scraper's tools

Copy-paste these two commands, pressing Enter after each. The second one
downloads a browser (~150 MB), so it takes a few minutes.

**Windows:**
```
py -m pip install playwright playwright-stealth fake-useragent requests beautifulsoup4
py -m playwright install chromium
```

**Mac:**
```
python3 -m pip install playwright playwright-stealth fake-useragent requests beautifulsoup4
python3 -m playwright install chromium
```

If a command says "pip is not recognized" or "python3 not found", the
Python install in step 1 didn't finish properly — easiest fix is to
re-run the installer (and on Windows, make sure the PATH checkbox was
ticked). Or just text me a screenshot.

---

## Running it (each time — takes 15–30 min)

In the terminal window (opened in the `scraper` folder like step 3):

**Windows:**
```
py live_scraper.py --country "United States"
```

**Mac:**
```
python3 live_scraper.py --country "United States"
```

### What you'll see

- Lines scrolling by like `Scraping Wendy's …` with item counts.
- **Some failures are completely normal and expected** — lines with ⚠
  or "failed". Part of this experiment is finding out *which* sites
  work from a US connection. Don't worry about them.
- At the end it prints either "All targets completed successfully" or a
  list of ones that still failed, then "Done. Results in uifpi.db".

If it seems frozen for more than ~5 minutes on one restaurant, that's
usually just a slow site timing out — give it time. If the window
crashes or shows a wall of red error text, screenshot it and send it to
me; nothing is broken on your computer.

### Sending me the results

After a run, the `scraper` folder will contain two new files:

1. **`uifpi.db`** — the database with all the prices (this is the
   important one)
2. **`scraper_log.txt`** — the log of what happened (also send this —
   it tells me *why* any site failed)

Email both to me, or drop them in our shared Google Drive folder —
whichever is easier. They're small (a few MB at most).

### Ideal schedule

If you're willing: run it **once or twice a month** (e.g. the 1st and
15th) and send me the same two files each time. The database file
accumulates — don't delete it between runs; each run adds that day's
prices to it.

That's it. Thank you so much — you're personally unlocking the US half
of this project. 💛
