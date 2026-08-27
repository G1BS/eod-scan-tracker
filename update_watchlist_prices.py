"""
update_watchlist_prices.py
---------------------------
Runs once daily (after NSE close) via GitHub Actions. For every 'active'
row in watchlist_items:
  1. Fetches today's close price via yfinance
  2. Records it in watchlist_price_history
  3. Classifies the move as As Expected / Against Expectation / Reversed /
     Flat / Target Hit, and writes that back onto watchlist_items

Requires env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os
from datetime import date

import requests
import yfinance as yf

MOVE_THRESHOLD_PCT = 2.0  # below this magnitude, a move counts as "Flat"


def sb_headers(service_key):
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def fetch_active_watchlist(base_url, headers):
    resp = requests.get(
        f"{base_url}/rest/v1/watchlist_items",
        headers=headers,
        params={"status": "eq.active", "select": "*"},
    )
    resp.raise_for_status()
    return resp.json()


def yf_symbol(ticker: str) -> str:
    # Assume NSE unless the user already typed an exchange suffix
    if "." in ticker:
        return ticker.upper()
    return f"{ticker.upper()}.NS"


def get_close_price(ticker: str):
    sym = yf_symbol(ticker)
    hist = yf.Ticker(sym).history(period="5d")
    if hist.empty:
        return None
    return round(float(hist["Close"].iloc[-1]), 2)


def classify(entry_price, direction, latest_price, target, prior_peak_favorable):
    sign = 1 if direction == "bullish" else -1
    pct_change = (latest_price - entry_price) / entry_price * 100
    adjusted = pct_change * sign  # positive = moving in your favor

    peak_favorable = max(prior_peak_favorable or 0, adjusted)

    target_hit = False
    if target:
        target_hit = (direction == "bullish" and latest_price >= target) or \
                     (direction == "bearish" and latest_price <= target)

    if target_hit:
        status = "Target Hit"
    elif adjusted >= MOVE_THRESHOLD_PCT:
        status = "As Expected"
    elif adjusted <= -MOVE_THRESHOLD_PCT:
        status = "Reversed" if (prior_peak_favorable or 0) >= MOVE_THRESHOLD_PCT else "Against Expectation"
    else:
        status = "Flat"

    return pct_change, peak_favorable, status


def main():
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_KEY"]
    headers = sb_headers(service_key)
    today = str(date.today())

    items = fetch_active_watchlist(base_url, headers)
    print(f"Found {len(items)} active watchlist item(s).")

    for item in items:
        ticker = item["ticker"]
        try:
            price = get_close_price(ticker)
            if price is None:
                print(f"  {ticker}: no price data, skipping.")
                continue

            pct_change, peak_favorable, status = classify(
                entry_price=item["entry_price"],
                direction=item["direction"],
                latest_price=price,
                target=item.get("target"),
                prior_peak_favorable=item.get("peak_favorable_pct"),
            )

            # 1. Record daily price history (upsert on unique watchlist_id+date)
            requests.post(
                f"{base_url}/rest/v1/watchlist_price_history",
                headers={**headers, "Prefer": "resolution=merge-duplicates"},
                json=[{"watchlist_id": item["id"], "price_date": today, "price": price}],
            )

            # 2. Update the summary row
            requests.patch(
                f"{base_url}/rest/v1/watchlist_items",
                headers=headers,
                params={"id": f"eq.{item['id']}"},
                json={
                    "latest_price": price,
                    "latest_price_date": today,
                    "pct_change": round(pct_change, 2),
                    "peak_favorable_pct": round(peak_favorable, 2),
                    "computed_status": status,
                },
            )
            print(f"  {ticker}: {price} ({pct_change:+.2f}%) -> {status}")

        except Exception as e:
            print(f"  {ticker}: FAILED - {type(e).__name__}: {e}")

    print("Done.")


if __name__ == "__main__":
    main()
