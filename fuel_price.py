import json
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from string import Template

TARGET_URL = "https://www.thefuelprice.com/F$country/en"
OUTPUT_FILE = "/home/fuelughn/public_html/fuel_prices_$country.json"
DEBUG_HTML_FILE = "fuel_prices_debug.html"
MAX_RETRIES = 4
COUNTRY_LIST = ['jo' , 'sy' , 'iq']

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

CURRENCY_MAP = {
    'Jordan': 'JOD',
    'Syria': 'SYP',
    'Iraq': 'IQD',
}


def clean_text(value: str) -> str:
    return " ".join(value.split()).strip()


def extract_number(raw_price: str):
    digits = re.sub(r"[^\d.]", "", raw_price)
    if not digits:
        return None
    if "." in digits:
        return float(digits)
    return int(digits)


def fetch_html(url: str) -> str:
    last_status = None
    session = requests.Session()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=30, headers=REQUEST_HEADERS)
            last_status = response.status_code

            if response.status_code == 200:
                return response.text
        except requests.RequestException:
            pass

        if attempt < MAX_RETRIES:
            time.sleep(attempt * 1.5)

    raise RuntimeError(
        f"Failed to fetch page after {MAX_RETRIES} attempts. "
        f"Last HTTP status: {last_status}. "
        f"The site may be rate-limiting or blocking non-browser requests."
    )


def scrape_fuel_table(url: str) -> dict:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    table = soup.select_one("table.table.table-striped")
    if table is None:
        with open(DEBUG_HTML_FILE, "w", encoding="utf-8") as f:
            f.write(html)
        raise ValueError(
            "Fuel table not found on page. Saved raw HTML to "
            f"{DEBUG_HTML_FILE} for inspection."
        )

    headers = [clean_text(th.get_text(" ", strip=True)) for th in table.select("thead th")]
    rows = []

    for tr in table.select("tbody tr"):
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue

        fuel_type = clean_text(cells[0].get_text(" ", strip=True))
        raw_price = clean_text(cells[1].get_text(" ", strip=True))
        unit = clean_text(cells[2].get_text(" ", strip=True))
        starting_from = clean_text(cells[3].get_text(" ", strip=True))

        rows.append(
            {
                "type": fuel_type,
                "price_text": raw_price,
                "price_numeric": extract_number(raw_price),
                "unit": unit,
                "starting_from": starting_from,
            }
        )

    return {
        "source_url": url,
        "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        "headers": headers,
        "count": len(rows),
        "prices": rows,
    }

def caputre_country_from_url(url: str) -> str:
    if 'jo' in url:
        return 'Jordan'
    elif 'sy' in url:
        return 'Syria'
    elif 'iq' in url:
        return 'Iraq'
    else:
        return 'Unknown'

def process_data(data: dict) -> dict:
    last_updated = data['scraped_at_utc'][:10]
    country = caputre_country_from_url(data['source_url'])
    currency = CURRENCY_MAP[country]
    prices = {}
    for p in data['prices']:
        if "Normal" in p['type'] or "90" in p['type']:
            prices[90] = p['price_numeric']
        elif "95" in p['type']:
            prices[95] = p['price_numeric']
        else:
            continue
    return {
        'last_updated': last_updated,
        'country': country,
        'currency': currency,
        'prices': prices,
    }



def main():
    for country in COUNTRY_LIST:
        target_url = Template(TARGET_URL).substitute(country=country)
        output_file = Template(OUTPUT_FILE).substitute(country=country)
        data = scrape_fuel_table(target_url)
        processed_data = process_data(data)
        print(processed_data)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=2)
        print(f"Last updated: {processed_data['last_updated']}")
        print(f"Country: {processed_data['country']}")
        print(f"Currency: {processed_data['currency']}")
        print(f"Prices: {processed_data['prices']}")

if __name__ == "__main__":
    main()
    print("Done")