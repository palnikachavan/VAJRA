from spaceTrack import IXPDataRetriever, start_monitoring
from advancedIXPRouter import AdvancedIXPRouter
import logging
import time
from threading import Thread
from bgpview_data import get_asn_data  # Import the new function
from config import TRAFFIC_THRESHOLD_MBPS
from flask import Flask, jsonify, request
import atexit

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("IXP Controller")

# Threshold configuration
# TRAFFIC_THRESHOLD_MBPS = 500  # Maximum allowed traffic before rerouting

def monitor_high_traffic(data_retriever):
    """
    Monitor traffic levels and identify overloaded IXPs.
    """
    # Simulate fetching traffic data for IXPs
    traffic_data = IXPDataRetriever().fetch_cached_traffic_data()  # From cached traffic data
    
    for ixp, traffic_volume in traffic_data.items():
        if traffic_volume > TRAFFIC_THRESHOLD_MBPS:
            return ixp  # Return overloaded IXP
    return None

def main():
    logger.info("Initializing IXP Traffic Controller System")

    # Initialize components
    data_retriever = IXPDataRetriever()
    ixp_router = AdvancedIXPRouter()

    # Fetch and cache initial data
    logger.info("Fetching and caching IXP and SpaceTrack data...")
    peeringdb_data = data_retriever.fetch_peeringdb_data()
    space_track_data = data_retriever.fetch_space_track_data()
    ixpdb_data = data_retriever.fetch_ixpdb_data()
    pch_data = data_retriever.fetch_pch_data()
    
    # Cache retrieved data
    if peeringdb_data:
        logger.info("PeeringDB data retrieved")
        data_retriever.cache_ixp_data(peeringdb_data)

    if space_track_data:
        logger.info("SpaceTrack data and satellite retrieved")
        data_retriever.cache_ixp_data(space_track_data)

    if ixpdb_data:
        data_retriever.cache_ixp_data(ixpdb_data)
        logger.info("Cached IXPDB data")
        
    if pch_data:
        logger.info("PCH data retrieved successfully")
        data_retriever.cache_ixp_data(pch_data)

    # Start live monitoring in a background thread
    logger.info("Starting traffic monitoring...")
    start_monitoring()  # Integrated live monitoring with Pyshark

    # Monitor traffic and manage rerouting
    while True:
        overloaded_ixp = monitor_high_traffic(data_retriever)
        
        if overloaded_ixp:
            logger.warning(f"High traffic detected on IXP: {overloaded_ixp}")
            alternative_route = ixp_router.dynamic_reroute(overloaded_ixp, TRAFFIC_THRESHOLD_MBPS)
            
            if alternative_route:
                logger.info(f"Traffic rerouted to: {alternative_route}")
            else:
                logger.error(f"No suitable alternative route found for: {overloaded_ixp}")
        else:
            logger.info("No overloaded IXPs detected. Traffic is within normal limits.")

        # Pause monitoring loop briefly
        time.sleep(5)

def monitor_high_traffic_background():
    main()  # Or a part of it you want to run in the background

# API configuration
app = Flask(__name__)

@app.route('/api/asn', methods=['GET'])
def fetch_asn_data():
    """
    API endpoint to fetch ASN data based on ASN provided as a query parameter.
    """
    as_number = request.args.get('asn')  # Get the ASN from query parameters
    
    if not as_number:
        return jsonify({"error": "ASN number is required"}), 400

    # Validate the ASN number
    try:
        as_number = int(as_number)
    except ValueError:
        return jsonify({"error": "Invalid ASN number"}), 400
    
    # Get ASN data from bgpview_data.py
    asn_data = get_asn_data(as_number)
    
    if asn_data:
        return jsonify(asn_data), 200
    else:
        return jsonify({"error": "Failed to fetch data"}), 500

# Graceful shutdown handler
def cleanup():
    logger.info("Shutting down traffic monitoring and Flask server...")

atexit.register(cleanup)

if __name__ == "__main__":
    # Start the monitoring function in a separate thread
    monitor_thread = Thread(target=monitor_high_traffic_background, daemon=True)
    monitor_thread.start()

    # Run Flask app
    logger.info("Starting Flask app...")
    try:
        app.run(debug=True)
    except KeyboardInterrupt:
        logger.info("Flask app stopping...")
        exit(0)
