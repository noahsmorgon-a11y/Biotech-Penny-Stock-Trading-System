import os
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

# Model
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# Date Range
TODAY = date.today()
LOOKBACK_DAYS = 30
START_DATE = TODAY - timedelta(days=LOOKBACK_DAYS)

# Mover Detection
MIN_PCT_CHANGE = 20.0  # Minimum absolute % daily move to qualify (penny stocks are noisy)
MIN_VOLUME_MULTIPLIER = 0.0  # Disabled — don't filter out movers by volume

# Penny stock filter
MAX_SHARE_PRICE = 5.0  # Only keep movers trading under $5/share
MAX_MARKET_CAP = 300_000_000  # Universe screener: under $300M (micro/nano-cap)

# Biotech Universe Source ETFs
BIOTECH_ETFS = ["XBI", "IBB"]

# Claude Batch Size (articles per API call)
CLAUDE_BATCH_SIZE = 10

# Finnhub rate limit: stay under 60/min
FINNHUB_DELAY = 1.1  # seconds between calls

# Paths
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# Canonical catalyst categories — single source of truth
CATALYST_TYPES = [
    "FDA_APPROVAL",
    "FDA_REJECTION",
    "CLINICAL_TRIAL_POSITIVE",
    "CLINICAL_TRIAL_NEGATIVE",
    "EARNINGS",
    "PARTNERSHIP_OR_MA",
    "SHORT_SQUEEZE",
    "ANALYST_RATING",
    "ADVERSE_EVENT",
    "OTHER",
    "UNKNOWN",
]
