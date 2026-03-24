"""Fetch biotech stock universe and detect daily movers using yfinance."""

import json
import os
import signal
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from tqdm import tqdm


class _DownloadTimeout(Exception):
    pass

import config


def _cache_path(name: str) -> Path:
    return Path(config.CACHE_DIR) / name


def get_biotech_universe(force_refresh: bool = False) -> list[str]:
    """Get deduplicated list of biotech tickers from XBI + IBB ETF holdings."""
    cache_file = _cache_path("biotech_universe.json")

    if not force_refresh and cache_file.exists():
        with open(cache_file) as f:
            cached = json.load(f)
        return cached["tickers"]

    tickers = set()
    for etf_symbol in config.BIOTECH_ETFS:
        try:
            etf = yf.Ticker(etf_symbol)
            # Try holdings from funds_data
            if hasattr(etf, "funds_data"):
                try:
                    holdings = etf.funds_data.top_holdings
                    if holdings is not None and not holdings.empty:
                        tickers.update(holdings.index.tolist())
                        continue
                except Exception:
                    pass

            # Fallback: try .holdings attribute
            try:
                holdings_df = etf.get_holdings()
                if holdings_df is not None and not holdings_df.empty:
                    if "Symbol" in holdings_df.columns:
                        tickers.update(holdings_df["Symbol"].tolist())
                    elif "symbol" in holdings_df.columns:
                        tickers.update(holdings_df["symbol"].tolist())
                    else:
                        tickers.update(holdings_df.index.tolist())
                    continue
            except Exception:
                pass

            print(f"  Warning: Could not fetch holdings for {etf_symbol}")
        except Exception as e:
            print(f"  Error fetching {etf_symbol}: {e}")

    # Clean up tickers
    cleaned = set()
    for t in tickers:
        if not isinstance(t, str):
            continue
        t = t.strip().upper()
        if t and len(t) <= 5 and t.isalpha():
            cleaned.add(t)

    result = sorted(cleaned)

    if not result:
        print("  Warning: No tickers fetched from ETFs. Using fallback list.")
        result = _fallback_biotech_tickers()

    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump({"tickers": result, "fetched": str(date.today())}, f)

    return result


def _fallback_biotech_tickers() -> list[str]:
    """Hardcoded fallback of well-known biotech tickers if ETF fetch fails."""
    return sorted([
        "ABBV", "AMGN", "BIIB", "BMRN", "BNTX", "CRSP", "EXAS", "EXEL",
        "FOLD", "GILD", "HALO", "IONS", "MRNA", "NBIX", "PCVX", "REGN",
        "SGEN", "SRPT", "UTHR", "VRTX", "ALNY", "ARGX", "ARWR", "BEAM",
        "BGNE", "BHVN", "CORT", "CPRX", "CRNX", "CYTK", "DAWN", "DNLI",
        "DRNA", "DVAX", "EDIT", "ELVN", "ENTA", "FATE", "GERN", "IDYA",
        "IMVT", "INSM", "IOVA", "IRON", "ITCI", "KROS", "KRYS", "LGND",
        "MCRB", "MDGL", "MIRM", "MRUS", "NUVB", "PTCT", "RARE", "RCKT",
        "RLAY", "RVMD", "RXRX", "SAGE", "SAVA", "SMMT", "TGTX", "TWST",
        "VCNX", "VERA", "VRNA", "XNCR",
    ])


def find_daily_movers(
    tickers: list[str],
    start: date,
    end: date,
    min_pct_change: float = None,
    batch_size: int = 50,
) -> pd.DataFrame:
    """Find all (date, ticker) pairs with big daily moves.

    Downloads price history in batches for efficiency, then filters for
    days where abs(pct_change) >= threshold.
    """
    if min_pct_change is None:
        min_pct_change = config.MIN_PCT_CHANGE

    # Add buffer days before start for rolling average calculation
    download_start = start - timedelta(days=40)

    all_movers = []
    batches = [tickers[i : i + batch_size] for i in range(0, len(tickers), batch_size)]

    for batch in tqdm(batches, desc="Downloading price data"):
        def _alarm(signum, frame):
            raise _DownloadTimeout()

        try:
            old_handler = signal.signal(signal.SIGALRM, _alarm)
            signal.alarm(30)  # 30-second timeout per batch
            df = yf.download(
                batch,
                start=download_start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        except _DownloadTimeout:
            print(f"  Timeout downloading batch (Yahoo Finance may be slow). Retrying...")
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
            try:
                old_handler = signal.signal(signal.SIGALRM, _alarm)
                signal.alarm(30)
                df = yf.download(
                    batch,
                    start=download_start.isoformat(),
                    end=(end + timedelta(days=1)).isoformat(),
                    auto_adjust=True,
                    progress=False,
                    threads=True,
                )
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            except (_DownloadTimeout, Exception):
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
                print(f"  Skipping batch after retry timeout")
                continue
        except Exception as e:
            signal.alarm(0)
            print(f"  Error downloading batch: {e}")
            continue

        if df.empty:
            continue

        # yfinance 1.2+ always returns multi-level columns: (Price, Ticker)
        # Flatten for each ticker
        for ticker in batch:
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    if ("Close", ticker) not in df.columns:
                        continue
                    ticker_df = df.xs(ticker, level=1, axis=1).copy()
                else:
                    # Flat columns (single ticker, older yfinance)
                    if "Close" not in df.columns:
                        continue
                    ticker_df = df.copy()
                _process_single_ticker(ticker_df, ticker, start, min_pct_change, all_movers)
            except (KeyError, TypeError):
                continue

    if not all_movers:
        return pd.DataFrame(columns=[
            "date", "ticker", "company_name", "open", "close",
            "volume", "pct_change", "catalyst_type", "catalyst_confidence",
            "news_headline", "news_summary", "news_url",
        ])

    result = pd.DataFrame(all_movers)
    result = result.sort_values("pct_change", key=abs, ascending=False).reset_index(drop=True)
    return result


def _process_single_ticker(
    df: pd.DataFrame,
    ticker: str,
    start: date,
    min_pct_change: float,
    results: list,
):
    """Process price data for one ticker and append movers to results list."""
    if "Close" not in df.columns or df["Close"].dropna().empty:
        return

    df = df.copy()
    df["pct_change"] = df["Close"].pct_change() * 100
    df["avg_volume_20d"] = df["Volume"].rolling(window=20, min_periods=5).mean()

    # Filter to our target date range (after rolling window warmup)
    mask = df.index >= pd.Timestamp(start)
    df = df.loc[mask]

    for idx, row in df.iterrows():
        pct = row.get("pct_change")
        if pd.isna(pct) or abs(pct) < min_pct_change:
            continue

        avg_vol = row.get("avg_volume_20d", 0)
        vol = row.get("Volume", 0)
        if pd.notna(avg_vol) and avg_vol > 0 and vol < avg_vol * config.MIN_VOLUME_MULTIPLIER:
            continue

        results.append({
            "date": idx.strftime("%Y-%m-%d"),
            "ticker": ticker,
            "company_name": "",  # filled later
            "open": round(row.get("Open", 0), 2),
            "close": round(row.get("Close", 0), 2),
            "volume": int(row.get("Volume", 0)),
            "pct_change": round(pct, 2),
            "catalyst_type": "UNKNOWN",
            "catalyst_confidence": 0.0,
            "news_headline": "",
            "news_summary": "",
            "news_url": "",
        })


def fill_company_names(movers_df: pd.DataFrame) -> pd.DataFrame:
    """Fill in company_name column by looking up ticker info via yfinance."""
    if movers_df.empty:
        return movers_df

    cache_file = _cache_path("ticker_info.json")
    if cache_file.exists():
        with open(cache_file) as f:
            info_cache = json.load(f)
    else:
        info_cache = {}

    unique_tickers = movers_df["ticker"].unique()
    for ticker in tqdm(unique_tickers, desc="Fetching company names"):
        if ticker in info_cache:
            continue
        try:
            t = yf.Ticker(ticker)
            name = t.info.get("longName") or t.info.get("shortName") or ticker
            info_cache[ticker] = name
        except Exception:
            info_cache[ticker] = ticker

    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(info_cache, f)

    movers_df["company_name"] = movers_df["ticker"].map(info_cache).fillna(movers_df["ticker"])
    return movers_df
