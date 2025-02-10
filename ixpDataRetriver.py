import datetime
import time
import requests
from bs4 import BeautifulSoup
import json
from cachetools import TTLCache
import sqlite3
import pandas as pd
import xmltodict
import logging
import os
import asyncio
import pyshark
from config import PEERINGDB_TOKEN, SPACE_TRACK_USERNAME, SPACE_TRACK_PASSWORD

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("IXP Traffic Monitor")

MONITOR_INTERFACE = "enp4s0"

# Cache to store API responses for 10 minutes (600 seconds)
cache = TTLCache(maxsize=10, ttl=600)

class IXPDataRetriever:
    def __init__(self):
        self.cache_db = 'ixp_data_cache.sqlite'
        self.setup_cache_database()

    def setup_cache_database(self):
        """Create SQLite cache for persistent data storage"""
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ixp_data (
                id TEXT PRIMARY KEY,
                name TEXT,
                location TEXT,
                last_updated DATETIME,
                data TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def fetch_peeringdb_data(self):
        """Fetch PeeringDB API data and return JSON."""
        if 'peeringdb_data' in cache:
            logging.info("Using cached PeeringDB data")
            return cache['peeringdb_data']
        
        headers = {'Authorization': f'Api-Key {PEERINGDB_TOKEN}', 'Content-Type': 'application/json'}
        url = 'https://peeringdb.com/api/net'
        
        max_retries = 5
        delay = 2
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    cache['peeringdb_data'] = data
                    return data
                elif response.status_code == 429:
                    logging.warning(f"Rate limit hit. Retrying in {delay} seconds...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    logging.error(f"Unexpected status code: {response.status_code}")
                    break
            except requests.exceptions.RequestException as e:
                logging.error(f"PeeringDB API Error: {e}")
                time.sleep(delay)
                delay *= 2
        return None  

    def fetch_spacetrack_data(self):
        """Fetch satellite data from SpaceTrack and return JSON."""
        try:
            session = requests.Session()
            login_data = {'identity': SPACE_TRACK_USERNAME, 'password': SPACE_TRACK_PASSWORD}
            response = session.post('https://www.space-track.org/ajaxauth/login', data=login_data)
            response.raise_for_status()

            spacetrack_url = 'https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/NORAD_CAT_ID/25544'
            response = session.get(spacetrack_url)
            response.raise_for_status()

            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"SpaceTrack API Error: {e}")
            return None

    def fetch_ixpdb_data(self):
        """Scrape IXPDB data and return JSON."""
        url = "https://ixpdb.euro-ix.net/en/explore/ixps/"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.find("table", class_="table-striped")
            if not table:
                logging.error("IXPDB Table not found!")
                return None

            headers = [th.text.strip() for th in table.find_all("th")]
            rows = []
            for tr in table.find_all("tr")[1:]:
                cells = [td.text.strip() for td in tr.find_all("td")]
                while len(cells) < len(headers):
                    cells.append("")
                while len(cells) > len(headers):
                    cells = cells[:len(headers)]
                rows.append(dict(zip(headers, cells)))

            return rows  # Returning JSON (list of dictionaries)
        except requests.exceptions.RequestException as e:
            logging.error(f"IXPDB Scraping Error: {e}")
            return None

    def fetch_euroix_data(self):
        """Fetch and return EuroIX data as JSON."""
        url = "https://ixpdb.euro-ix.net/en/"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            ixp_data = []
            tables = soup.find_all("table", class_="table-striped")
            if not tables:
                logging.error("No tables found on EuroIX page.")
                return []

            for table in tables:
                headers = [th.text.strip() for th in table.find_all("th")]
                for row in table.find_all("tr")[1:]:
                    cells = [td.text.strip() for td in row.find_all("td")]
                    if len(cells) == len(headers):
                        ixp_data.append(dict(zip(headers, cells)))

            return ixp_data  # Returning JSON (list of dictionaries)
        except requests.exceptions.RequestException as e:
            logging.error(f"EuroIX Scraping Error: {e}")
            return []

    def fetch_alternative_sources(self):
        """Fetch alternative IXP sources and return JSON."""
        sources = {"pch": "https://www.pch.net/ixp/dir"}
        combined_data = []

        for source_name, url in sources.items():
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()

                if "json" in content_type:
                    data = response.json()
                    combined_data.append(data)
                elif "xml" in content_type or "<xml" in response.text[:10].lower():
                    data = xmltodict.parse(response.text)
                    combined_data.append(data)
                elif "html" in content_type:
                    soup = BeautifulSoup(response.text, "html.parser")
                    table = soup.find("table")
                    if not table:
                        logging.error(f"No table found in HTML response from {source_name}")
                        continue

                    headers = [th.get_text(strip=True) for th in table.find_all("th")]
                    rows = []
                    for tr in table.find_all("tr")[1:]:
                        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                        if len(cells) == len(headers):
                            rows.append(dict(zip(headers, cells)))

                    if rows:
                        combined_data.append({source_name: rows})

            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to fetch data from {source_name}: {e}")

        return combined_data  # Returning JSON (list of dictionaries)

    def get_cached_ixp_data(self):
        """Retrieve cached IXP data as JSON."""
        conn = sqlite3.connect(self.cache_db)
        df = pd.read_sql_query("SELECT * FROM ixp_data", conn)
        conn.close()
        return df.to_dict(orient="records")  # Convert to JSON

def enhanced_traffic_monitoring():
    data_retriever = IXPDataRetriever()
    peering_data = data_retriever.fetch_peeringdb_data()
    print(peering_data)
    print()
    spacetrack_data = data_retriever.fetch_spacetrack_data()
    print(spacetrack_data)
    print()
    ixpdb_data = data_retriever.fetch_ixpdb_data()
    print(ixpdb_data)
    print()
    euroix_data = data_retriever.fetch_euroix_data()
    print(euroix_data)
    print()
    alternative_sources = data_retriever.fetch_alternative_sources()
    print(alternative_sources)
    print()
    if alternative_sources:
        data_retriever.cache_ixp_data(alternative_sources)

if __name__ == "__main__":
    enhanced_traffic_monitoring()