# Biotech Catalyst Tracker

A tool that finds the biggest daily movers in biotech stocks, figures out **why** each stock moved (FDA approval? Clinical trial? Earnings?), and shows you everything in an interactive dashboard.

Built to answer the question: **"What causes those crazy 100%+ jumps in biotech stocks?"**

---

## What It Does

1. **Scans ~300 biotech stocks** (pulled from XBI and IBB ETF holdings)
2. **Finds big movers** — any stock that moved 10%+ in a single day over the last 30 days
3. **Fetches news** for each mover from Finnhub (financial news API)
4. **Uses AI (Claude)** to read the news and classify *why* each stock moved:
   - FDA Approval / Rejection
   - Clinical Trial Results (positive or negative)
   - Earnings Reports
   - Partnerships or M&A
   - Short Squeeze
   - Analyst Rating Changes
   - Adverse Events
5. **Saves everything to CSV** so you can open it in Excel
6. **Shows an interactive dashboard** with charts and a filterable table

---

## Setup Instructions (Step by Step)

### Step 1: Get Your API Keys (Free)

You need two API keys before you can run this. Both are free to get:

**Finnhub (for stock news):**
1. Go to https://finnhub.io
2. Click "Get Free API Key" (top right)
3. Sign up with your email
4. After signing in, your API key will be shown on your dashboard
5. Copy this key — you'll need it in Step 3

**Anthropic (for AI classification):**
1. Go to https://console.anthropic.com
2. Click "Sign Up" and create an account
3. After signing in, go to "API Keys" in the left sidebar
4. Click "Create Key" and give it any name
5. Copy this key — you'll need it in Step 3
6. Note: You'll need to add a small amount of credit (~$5 is plenty). The tool costs about $0.60 per full 30-day run.

### Step 2: Open Terminal

1. Press **Cmd + Space** on your keyboard (opens Spotlight Search)
2. Type **Terminal** and press Enter
3. A black/white window will open — this is your Terminal

Now type the following command and press Enter:

```
cd ~/Desktop/biotech-catalyst-system
```

This moves you into the project folder.

### Step 3: Set Up Your API Keys

Type this command and press Enter:

```
cp .env.example .env
```

Now open the `.env` file to add your keys:

```
open -e .env
```

This opens the file in TextEdit. Replace the placeholder text with your actual keys:

```
FINNHUB_API_KEY=paste_your_finnhub_key_here
ANTHROPIC_API_KEY=paste_your_anthropic_key_here
```

Save the file (Cmd + S) and close TextEdit.

### Step 4: Activate the Virtual Environment

Every time you open a new Terminal window to use this tool, you need to run this command first:

```
source .venv/bin/activate
```

You should see `(.venv)` appear at the beginning of your terminal line. This means it's working.

### Step 5: Run the Pipeline (Collect Data)

This is the command that actually goes out, finds the big movers, fetches the news, and classifies everything:

```
python run_pipeline.py
```

This will take about 5–10 minutes the first time. You'll see progress bars and status updates.

**Want to test it quickly first?** Try a single stock with no AI calls:

```
python run_pipeline.py --ticker MRNA --days 5 --dry-run
```

### Step 6: Launch the Dashboard

```
python app.py
```

Then open your web browser and go to:

```
http://localhost:8050
```

You should see the dashboard with your data!

---

## Everyday Usage

Once you've done the setup above, here's what you do each day:

1. Open Terminal
2. Run these three commands:

```
cd ~/Desktop/biotech-catalyst-system
source .venv/bin/activate
python run_pipeline.py
```

3. Then launch the dashboard:

```
python app.py
```

4. Open http://localhost:8050 in your browser

The pipeline is smart — it won't re-download data it already has. So daily runs only take about 30 seconds.

---

## Command Options

| Command | What It Does |
|---------|-------------|
| `python run_pipeline.py` | Full 30-day scan (default) |
| `python run_pipeline.py --days 7` | Only look at last 7 days |
| `python run_pipeline.py --ticker MRNA` | Only look at one stock |
| `python run_pipeline.py --dry-run` | Skip AI classification (free, good for testing) |
| `python run_pipeline.py --force-refresh` | Re-download everything from scratch |

---

## Your Data Files

After running the pipeline, you'll find two CSV files you can open in Excel:

| File | What's In It |
|------|-------------|
| `output/movers.csv` | Every big mover event: date, ticker, company, % change, catalyst type, news headline, AI summary |
| `output/trends.csv` | Summary stats: how often each catalyst type appears, average % move per type |

To open in Excel, just double-click the file, or in Excel go to File > Open and navigate to the `output` folder.

---

## Dashboard Features

- **KPI Cards** — Quick stats at the top: total movers found, most common catalyst, biggest move
- **Filters** — Filter by catalyst type, direction (up/down), ticker search, or minimum % move
- **Movers Table** — Sortable table of every event. Click any row to see details
- **Catalyst Frequency Chart** — Bar chart showing which catalysts cause the most moves
- **Avg % Move by Catalyst** — Which catalyst types cause the biggest average moves
- **Timeline Scatter** — 30-day view of all events, colored by catalyst type
- **Stock Detail Panel** — Click a row in the table to see that stock's full history and news
- **Export** — Click "Export CSV" to download the currently filtered view

---

## Troubleshooting

**"command not found: python"**
Try `python3` instead of `python` in all commands above.

**"No movers found"**
The market might have been calm. Try lowering the threshold: open `config.py` in TextEdit and change `MIN_PCT_CHANGE = 10.0` to `MIN_PCT_CHANGE = 5.0`.

**"Finnhub error" or rate limit messages**
The free Finnhub tier allows 60 calls per minute. If you hit the limit, the tool will retry automatically. If problems persist, wait a minute and run again.

**"ANTHROPIC_API_KEY" error**
Make sure you added your key to the `.env` file (Step 3) and that there are no spaces around the `=` sign.

**Dashboard shows "No data"**
You need to run `python run_pipeline.py` first to collect data before the dashboard has anything to show.

**Need to start completely fresh?**
Delete the cache and output folders:
```
rm -rf cache/ output/
```
Then run the pipeline again.
