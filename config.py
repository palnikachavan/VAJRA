import os

# Environment Variables
SPACE_TRACK_USERNAME = os.getenv('SPACE_TRACK_USERNAME', 'shreejitsen@astraeusnextgen.com')
SPACE_TRACK_PASSWORD = os.getenv('SPACE_TRACK_PASSWORD', 'AstraeusNext2024')
# IXPDB_API_KEY = os.getenv('IXPDB_API_KEY', 'your_api_key_here')
NASA_API_KEY = os.getenv('NASA_API_KEY', 'AnSQx7gOblYXG0pUrIKtTcaLeLDxdMfCt80aedJj')
PEERINGDB_TOKEN = os.getenv('PEERINGDB_TOKEN', 'fLrf9Ovq.BYQ0AjiXwgm66qswYO97acGlVdIfI8NX')
# N2YO_TOKEN = os.getenv('N2YO_TOKEN', 'C4SLGL-TUJ2WH-KR5C8P-5EOH')

# Environment variables for Razorpay credentials
RAZORPAY_API_KEY = os.getenv("rzp_test_zJLa0siNBO1NL1")
RAZORPAY_API_SECRET = os.getenv("Wo9sPkvBJ40lChcgw9724BMq")

# Network Interface for Traffic Monitoring
MONITOR_INTERFACE = os.getenv('MONITOR_INTERFACE', 'eth0')

# Traffic Thresholds
TRAFFIC_THRESHOLD_MBPS = int(os.getenv('TRAFFIC_THRESHOLD_MBPS', 500))
ELEPHANT_FLOW_SIZE_MB = int(os.getenv('ELEPHANT_FLOW_SIZE_MB', 100))
LATENCY_THRESHOLD_MS = int(os.getenv('LATENCY_THRESHOLD_MS', 50))

# Default and Backup Gateways
DEFAULT_GATEWAY = os.getenv('DEFAULT_GATEWAY', '192.168.1.1')
BACKUP_GATEWAY = os.getenv('BACKUP_GATEWAY', '192.168.1.254')