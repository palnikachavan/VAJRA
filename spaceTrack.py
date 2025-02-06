
import os
import requests
import json
import logging
import sqlite3
import threading
import asyncio
import pyshark
from datetime import datetime
from skyfield.api import load
from config import SPACE_TRACK_USERNAME, SPACE_TRACK_PASSWORD, PEERINGDB_TOKEN

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("IXP Traffic Monitor")

# Threshold configurations
TRAFFIC_THRESHOLD_MBPS = 500
MONITOR_INTERFACE = "eth0"

# Space Track and IXPDB Configuration
class IXPDataRetriever:
    def __init__(self):
        self.cache_db = 'ixp_data_cache.sqlite'
        self.setup_cache_database()

    def setup_cache_database(self):
        """Initialize SQLite database for caching IXP data."""
        try:
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
        except Exception as e:
            logger.error(f"Error setting up cache database: {e}")

    def fetch_space_track_data(self):
        """Retrieve TLE data for satellites"""
        # TLE is two line element data
        try:
            session = requests.Session()
            login_url = 'https://www.space-track.org/ajaxauth/login'
            data_url = 'https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/orderby/EPOCH%20desc/format/json'
            
            login_data = {
                'identity': SPACE_TRACK_USERNAME,
                'password': SPACE_TRACK_PASSWORD
            }

            session.post(login_url, data=login_data)
            response = session.get(data_url)

            if response.status_code == 200:
                tle_data = response.json()
                tle_lines = [item["TLE_LINE1"] + "\n" + item["TLE_LINE2"] for item in tle_data]

                positions = self.calculate_satellite_positions(tle_lines)
                if positions:
                    logger.info(f"Satellite positions: {positions}")
                else:
                    logger.info("No satellite positions found.")
                return tle_data
            else:
                logger.error("Space Track data retrieval failed")
                return None
        except Exception as e:
            logger.error(f"Error retrieving Space Track data: {e}")
            return None

    def calculate_satellite_positions(self, tle_data):
        """Calculate satellite positions from Space-Track TLE data."""
        try:
            satellites = load.tle_file(tle_data)
            positions = []
            for satellite in satellites:
                position = satellite.at(datetime.now()).position.km
                positions.append(f"Satellite: {satellite.name}, Position (km): {position}")

            return positions
        except Exception as e:
            logger.error(f"Error calculating satellite positions: {e}")
            return None

    def fetch_peeringdb_data(self):
        """Fetch PeeringDB data with rate-limiting and error handling."""
        try:
            headers = {
                'Authorization': f'Bearer {PEERINGDB_TOKEN}',
                'Content-Type': 'application/json'
            }
            response = requests.get(
                'https://peeringdb.com/api/ix', 
                headers=headers, 
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"PeeringDB API Error: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"PeeringDB Request Failed: {e}")
            return None

    def fetch_ixpdb_data(self):
        """Fetch data from IXPDB."""
        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.get(
                'https://api.ixpdb.net/v1/participant/list', 
                headers=headers, 
                timeout=30
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"IXPDB API Error: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"IXPDB Request Failed: {e}")
            return None

    def cache_ixp_data(self, data):
        """Cache IXP data to SQLite database."""
        try:
            conn = sqlite3.connect(self.cache_db)
            cursor = conn.cursor()

            for entry in data:
                serialized_data = json.dumps(entry)

                cursor.execute('''
                    INSERT OR REPLACE INTO ixp_data 
                    (id, name, location, last_updated, data) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    entry.get('id', ''),
                    entry.get('name', ''),
                    entry.get('location', ''),
                    datetime.now(),
                    serialized_data
                ))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error caching IXP data: {e}")

    def fetch_cached_traffic_data(self):
        """Simulate fetching traffic data for monitoring from the cache."""
        try:
            conn = sqlite3.connect(self.cache_db)
            cursor = conn.cursor()

            cursor.execute("SELECT name, data FROM ixp_data")
            traffic_data = {}

            for row in cursor.fetchall():
                ixp_name, ixp_data_json = row
                ixp_data = json.loads(ixp_data_json)
                traffic_data[ixp_name] = ixp_data.get("traffic_volume", 0)

            conn.close()
            return traffic_data
        except Exception as e:
            logger.error(f"Error fetching traffic data from cache: {e}")
            return {}
        
    def fetch_pch_data(self, status="active"):
        """Fetch IXP data from PCH API."""
        url = f"https://www.pch.net/api/ixp/directory/{status}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if not data or (isinstance(data, dict) and "error" in data[0]):
                logger.error("PCH API returned an error or empty data.")
                return None
            logger.info(f"Successfully fetched PCH data: {len(data)} records")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching PCH data: {e}")
            return None


def monitor_traffic():
    """Monitor network traffic using pyshark with asynchronous processing."""
    try:
        logger.info(f"Starting traffic monitoring on interface: {MONITOR_INTERFACE}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        capture = pyshark.LiveCapture(interface=MONITOR_INTERFACE)
        loop.run_until_complete(capture.sniff_continuously(packet_callback=process_packet))
    except Exception as e:
        logger.error(f"Error in traffic monitoring: {e}")

def process_packet( packet):
    """Process captured packets."""
    logger.info(f"Packet captured: {packet}")

def start_monitoring():
    """Start the IXP Traffic Monitoring System."""
    logger.info("Starting IXP Traffic Monitoring System")

    # Initialize data retriever
    data_retriever = IXPDataRetriever()
    
    # Fetch data from Space Track and IXPDB
    space_track_data = data_retriever.fetch_space_track_data()
    ixpdb_data = data_retriever.fetch_ixpdb_data()

    if space_track_data:
        data_retriever.cache_ixp_data(space_track_data)
        logger.info("SpaceTrack data retrieved and cached")

    if ixpdb_data:
        data_retriever.cache_ixp_data(ixpdb_data)
        logger.info("IXPDB data retrieved and cached")

    # Start traffic monitoring in a new thread
    monitoring_thread = threading.Thread(target=monitor_traffic, daemon=True)
    monitoring_thread.start()
    monitoring_thread.join()  # Ensure the thread doesn't exit prematurely

if __name__ == "__main__":
    try:
        start_monitoring()
    except Exception as e:
        logger.error(f"Error during start monitoring: {e}")
