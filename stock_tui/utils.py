import os
import json
import logging
import requests
from bs4 import BeautifulSoup

CONFIG_PATH = os.path.expanduser("~/.stock_tui_config.json")

def load_config():
    # ... (rest of the file remains same)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
    return {"history": [], "pinned": []}

def save_config(config):
    # Merge with existing config
    current = load_config()
    current.update(config)
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(current, f)
    except Exception as e:
        logging.error(f"Failed to save config: {e}")

def fetch_finviz_data(symbol):
    """Fetch company info and fundamental data from Finviz."""
    url = f"https://finviz.com/quote.ashx?t={symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Get Sector, Industry, Country
        meta_data = {"sector": "N/A", "industry": "N/A", "country": "N/A"}

        # In the new design, they are in a flex container with links
        quote_links = soup.find("div", class_="quote-links")
        if quote_links:
            links = quote_links.find_all("a", class_="tab-link")
            if len(links) >= 3:
                meta_data["sector"] = links[0].text.strip()
                meta_data["industry"] = links[1].text.strip()
                meta_data["country"] = links[2].text.strip()

        # 2. Get Snapshot Table (Fundamentals)
        snapshot_data = {}
        table = soup.find("table", class_="snapshot-table2")
        if table:
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                for i in range(0, len(cols), 2):
                    label = cols[i].text.strip()
                    value = cols[i+1].text.strip()
                    snapshot_data[label] = value

        # 3. Get Company Name and Description
        full_name = "N/A"
        description = "N/A"

        # Name is in a <h2> with a specific class
        name_container = soup.find("h2", class_="quote-header_ticker-wrapper_company")
        if name_container:
            full_name = name_container.text.strip()

        desc_elem = soup.find("td", class_="fullview-profile")
        if desc_elem:
            description = desc_elem.text.strip()

        return {
            "name": full_name,
            "meta": meta_data,
            "snapshot": snapshot_data,
            "description": description
        }
    except Exception as e:
        logging.error(f"Finviz fetch failed for {symbol}: {e}")
        return None
