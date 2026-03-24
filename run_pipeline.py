#!/usr/bin/env python3
"""Biotech Catalyst Tracker — data collection pipeline.

Usage:
    python run_pipeline.py                   # Full 30-day run
    python run_pipeline.py --days 7          # Last 7 days
    python run_pipeline.py --force-refresh   # Bypass all caches
    python run_pipeline.py --dry-run         # Skip Claude API calls
    python run_pipeline.py --ticker MRNA     # Single stock debug
"""

import argparse
import os
from datetime import date, timedelta

import pandas as pd
from tqdm import tqdm

import config
from data.collector import find_daily_movers, get_biotech_universe, fill_company_names
from data.news_fetcher import fetch_news_for_mover
from data.classifier import classify_mover_event


def load_existing_movers() -> pd.DataFrame:
    """Load existing movers.csv if it exists."""
    path = os.path.join(config.OUTPUT_DIR, "movers.csv")
    if os.path.exists(path):
        return pd.read_csv(path, dtype={"ticker": str, "date": str})
    return pd.DataFrame()


def save_movers(df: pd.DataFrame):
    """Save movers DataFrame to CSV atomically."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(config.OUTPUT_DIR, "movers.csv")
    tmp_path = path + ".tmp"
    df.to_csv(tmp_path, index=False)
    os.replace(tmp_path, path)


def save_trends(movers_df: pd.DataFrame):
    """Compute and save catalyst trends from movers data."""
    if movers_df.empty:
        return

    trends = (
        movers_df.groupby("catalyst_type")
        .agg(
            count=("ticker", "size"),
            avg_pct_change=("pct_change", lambda x: round(x.abs().mean(), 2)),
            pct_positive_moves=("pct_change", lambda x: round((x > 0).mean() * 100, 1)),
            avg_confidence=("catalyst_confidence", lambda x: round(x.mean(), 2)),
            most_common_ticker=("ticker", lambda x: x.value_counts().index[0] if len(x) > 0 else ""),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )
    trends["as_of_date"] = str(date.today())

    path = os.path.join(config.OUTPUT_DIR, "trends.csv")
    tmp_path = path + ".tmp"
    trends.to_csv(tmp_path, index=False)
    os.replace(tmp_path, path)


def upsert_movers(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Merge new rows into existing, using id as the key."""
    if existing.empty:
        return new
    if new.empty:
        return existing

    combined = pd.concat([existing, new], ignore_index=True)
    combined = combined.drop_duplicates(subset=["id"], keep="last")
    return combined.sort_values("date", ascending=False).reset_index(drop=True)


def run_pipeline(
    days: int = 30,
    force_refresh: bool = False,
    dry_run: bool = False,
    single_ticker: str = None,
):
    """Run the full data collection and classification pipeline."""

    start = date.today() - timedelta(days=days)
    end = date.today()

    # Step 1: Get biotech universe
    print(f"\n{'='*60}")
    print("BIOTECH CATALYST TRACKER")
    print(f"{'='*60}")
    print(f"Date range: {start} → {end} ({days} days)")

    if single_ticker:
        tickers = [single_ticker.upper()]
        print(f"Single ticker mode: {tickers[0]}")
    else:
        print("\nStep 1/5: Fetching biotech universe...")
        tickers = get_biotech_universe(force_refresh=force_refresh)
        print(f"  Found {len(tickers)} biotech tickers")

    # Step 2: Find daily movers
    print("\nStep 2/5: Detecting daily movers...")
    movers_df = find_daily_movers(tickers, start, end)
    print(f"  Found {len(movers_df)} mover events (>={config.MIN_PCT_CHANGE}% move)")

    if movers_df.empty:
        print("\nNo movers found. Try lowering MIN_PCT_CHANGE in config.py")
        return

    # Add unique ID column
    movers_df["id"] = movers_df["ticker"] + "_" + movers_df["date"]

    # Step 3: Fill company names
    print("\nStep 3/5: Looking up company names...")
    movers_df = fill_company_names(movers_df)

    # Step 4: Fetch news and classify
    print("\nStep 4/5: Fetching news & classifying catalysts...")
    if dry_run:
        print("  (dry-run mode: skipping Claude API calls)")

    for idx in tqdm(range(len(movers_df)), desc="Processing movers"):
        row = movers_df.iloc[idx]

        # Fetch news
        articles = fetch_news_for_mover(
            row["ticker"],
            row["date"],
            force_refresh=force_refresh,
        )

        # Classify
        classification = classify_mover_event(
            ticker=row["ticker"],
            company_name=row["company_name"],
            pct_change=row["pct_change"],
            articles=articles,
            dry_run=dry_run,
        )

        # Update row
        movers_df.at[movers_df.index[idx], "catalyst_type"] = classification["catalyst_type"]
        movers_df.at[movers_df.index[idx], "catalyst_confidence"] = classification["catalyst_confidence"]
        movers_df.at[movers_df.index[idx], "news_headline"] = classification["news_headline"]
        movers_df.at[movers_df.index[idx], "news_summary"] = classification["news_summary"]

        # Add news URL from first article if available
        if articles:
            movers_df.at[movers_df.index[idx], "news_url"] = articles[0].get("url", "")

    # Step 5: Save results
    print("\nStep 5/5: Saving results...")
    existing = load_existing_movers()
    final_df = upsert_movers(existing, movers_df)
    save_movers(final_df)
    save_trends(final_df)

    # Summary
    print(f"\n{'='*60}")
    print("PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"Total mover events: {len(final_df)}")
    print(f"Saved to: {os.path.join(config.OUTPUT_DIR, 'movers.csv')}")

    print(f"\nTop 10 biggest moves:")
    top = final_df.nlargest(10, "pct_change", keep="first")
    for _, r in top.iterrows():
        print(f"  {r['ticker']:6s} {r['pct_change']:+7.1f}%  {r['date']}  [{r['catalyst_type']}]  {r['news_headline'][:60]}")

    print(f"\nCatalyst distribution:")
    dist = final_df["catalyst_type"].value_counts()
    for cat, count in dist.items():
        pct = count / len(final_df) * 100
        print(f"  {cat:30s} {count:4d} ({pct:5.1f}%)")

    print(f"\nDashboard: python app.py  →  http://localhost:8050")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Biotech Catalyst Tracker Pipeline")
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back (default: 30)")
    parser.add_argument("--force-refresh", action="store_true", help="Bypass all caches")
    parser.add_argument("--dry-run", action="store_true", help="Skip Claude API calls")
    parser.add_argument("--ticker", type=str, default=None, help="Run for a single ticker only")
    args = parser.parse_args()

    run_pipeline(
        days=args.days,
        force_refresh=args.force_refresh,
        dry_run=args.dry_run,
        single_ticker=args.ticker,
    )
