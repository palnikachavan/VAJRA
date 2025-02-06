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
                data BLOB
            )
        ''')
        conn.commit()
        conn.close()
    
    def fetch_peeringdb_data(self):
        """Fetch PeeringDB API data with rate limiting and retry mechanism."""
        
        # If data is cached, return it to avoid excess API calls
        if 'peeringdb_data' in cache:
            logging.info("Using cached PeeringDB data")
            return cache['peeringdb_data']
        
        headers = {
            'Authorization': f'Api-Key {PEERINGDB_TOKEN}',
            'Content-Type': 'application/json'
        }
        url = 'https://peeringdb.com/api/net'
        
        max_retries = 5
        delay = 2  # Start with 2 seconds
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Cache the response to limit API calls
                    cache['peeringdb_data'] = data
                    return data
                
                elif response.status_code == 429:  # Too Many Requests
                    logging.warning(f"Rate limit hit. Retrying in {delay} seconds...")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                
                else:
                    logging.error(f"Unexpected status code: {response.status_code}")
                    break  # Don't retry for other errors
            
            except requests.exceptions.RequestException as e:
                logging.error(f"PeeringDB API Error: {e}")
                time.sleep(delay)
                delay *= 2  # Increase delay for the next retry
        
        return None  # If all retries fail

    def fetch_spacetrack_data(self):
        """Fetch satellite data from SpaceTrack"""
        try:
            session = requests.Session()
            login_data = {
                'identity': SPACE_TRACK_USERNAME,
                'password': SPACE_TRACK_PASSWORD
            }
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
        """Scrape tabular data from IXPDB Explore Page and handle column mismatch."""
        url = "https://ixpdb.euro-ix.net/en/explore/ixps/"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.find("table", class_="table-striped")

            if not table:
                logging.error("IXPDB Table not found!")
                return None

            # Extract headers
            headers = [th.text.strip() for th in table.find_all("th")]

            rows = []
            for tr in table.find_all("tr")[1:]:  # Skip header row
                cells = [td.text.strip() for td in tr.find_all("td")]

                # Ensure row length matches the headers count
                while len(cells) < len(headers):
                    cells.append("")  # Fill missing values with empty string
                while len(cells) > len(headers):
                    cells = cells[:len(headers)]  # Trim extra columns

                rows.append(cells)

            # Convert to DataFrame
            df = pd.DataFrame(rows, columns=headers)

            return df

        except requests.exceptions.RequestException as e:
            logging.error(f"IXPDB Scraping Error: {e}")
            return None



    def fetch_euroix_data(self):
        """Fetch and extract tabular data from EuroIX"""
        url = "https://ixpdb.euro-ix.net/en/"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            ixp_data = []
            
            # Find all tables
            tables = soup.find_all("table", class_="table-striped")

            if not tables:
                logging.error("No tables found on EuroIX page.")
                return []

            for table in tables:
                headers = [th.text.strip() for th in table.find_all("th")]
                
                for row in table.find_all("tr")[1:]:  # Skip header row
                    cells = [td.text.strip() for td in row.find_all("td")]

                    if len(cells) == len(headers):
                        ixp_data.append(dict(zip(headers, cells)))
                    else:
                        logging.warning(f"Skipping row due to mismatch: {cells}")

            return ixp_data

        except requests.exceptions.RequestException as e:
            logging.error(f"EuroIX Scraping Error: {e}")
            return []

    def fetch_alternative_sources(self):
        """Aggregate IXP data from multiple alternative sources with robust error handling and HTML scraping for PCH"""

        sources = {
            "pch": "https://www.pch.net/ixp/dir",
        }

        combined_data = []

        for source_name, url in sources.items():
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()  # Raise an error for HTTP issues

                content_type = response.headers.get("Content-Type", "").lower()

                # Handle JSON response
                if "json" in content_type:
                    try:
                        data = response.json()
                        combined_data.append(data)
                    except json.JSONDecodeError as e:
                        logging.error(f"JSON Parsing Error for {source_name}: {e}")
                        continue

                # Handle XML response
                elif "xml" in content_type or "<xml" in response.text[:10].lower():
                    try:
                        data = xmltodict.parse(response.text)
                        combined_data.append(data)
                    except Exception as e:
                        logging.error(f"XML Parsing Error for {source_name}: {e}")
                        continue

                # Handle HTML response (Scrape PCH IXP directory)
                elif "html" in content_type:
                    try:
                        soup = BeautifulSoup(response.text, "html.parser")
                        table = soup.find("table")  # Find the first table
                        if not table:
                            logging.error(f"No table found in HTML response from {source_name}")
                            continue

                        headers = [th.get_text(strip=True) for th in table.find_all("th")]
                        rows = []
                        for tr in table.find_all("tr")[1:]:  # Skip the header row
                            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                            if len(cells) == len(headers):  # Ensure consistent columns
                                rows.append(dict(zip(headers, cells)))

                        if rows:
                            combined_data.append({source_name: rows})
                        else:
                            logging.warning(f"No data extracted from {source_name}")

                    except Exception as e:
                        logging.error(f"HTML Parsing Error for {source_name}: {e}")
                        continue

                else:
                    logging.warning(f"Unknown data format from {source_name}: {content_type}")

            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to fetch data from {source_name}: {e}")

        return combined_data


    def cache_ixp_data(self, data):
        """Cache retrieved IXP data in SQLite"""
        conn = sqlite3.connect(self.cache_db)
        cursor = conn.cursor()
        
        for entry in data:
            cursor.execute('''
                INSERT OR REPLACE INTO ixp_data 
                (id, name, location, last_updated, data) 
                VALUES (?, ?, ?, ?, ?)
            ''', (
                entry.get('id', ''),
                entry.get('name', ''),
                entry.get('location', ''),
                datetime.datetime.now().isoformat(),
                json.dumps(entry)
            ))
        
        conn.commit()
        conn.close()

    def get_cached_ixp_data(self):
        """Retrieve cached IXP data"""
        conn = sqlite3.connect(self.cache_db)
        df = pd.read_sql_query("SELECT * FROM ixp_data", conn)
        conn.close()
        return df

def sync_monitor_traffic():
    """Runs sniffing synchronously and processes packets."""
    try:
        logger.info(f"Starting traffic monitoring on interface: {MONITOR_INTERFACE}")
        
        capture = pyshark.LiveCapture(interface=MONITOR_INTERFACE)
        
        for packet in capture.sniff_continuously():  # Regular for-loop (not async)
            process_packet(packet)  # Call the callback function manually

    except Exception as e:
        logger.error(f"Error in traffic monitoring: {e}")

async def async_monitor_traffic():
    """Runs the sync function in a background thread to prevent blocking the event loop."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, sync_monitor_traffic)  # Run sync function in a thread

def monitor_traffic():
    """Starts monitoring traffic, handling existing event loops properly."""
    loop = asyncio.get_event_loop()
    
    if loop.is_running():
        asyncio.create_task(async_monitor_traffic())  # Run in the background
    else:
        asyncio.run(async_monitor_traffic()) 

def process_packet(packet):
    # Implement packet processing logic here
    pass

def reroute_traffic(ixp_data):
    """Reroute traffic based on IXP load"""
    low_traffic_ixps = [ixp for ixp in ixp_data if ixp.get('traffic', 0) < 50]
    return low_traffic_ixps

def enhanced_traffic_monitoring():
    data_retriever = IXPDataRetriever()
    # peering_data = data_retriever.fetch_peeringdb_data()
    
    spacetrack_data = data_retriever.fetch_spacetrack_data()
    
    ixpdb_data = data_retriever.fetch_ixpdb_data()
    # print(ixpdb_data)
    
    euroix_data = data_retriever.fetch_euroix_data()
    # print(euroix_data[0])
    
    alternative_sources = data_retriever.fetch_alternative_sources()
    # print(alternative_sources)
    if alternative_sources:
        data_retriever.cache_ixp_data(alternative_sources)
    
    monitor_traffic()

if __name__ == "__main__":
    enhanced_traffic_monitoring()
