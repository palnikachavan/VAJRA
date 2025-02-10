from pymongo import MongoClient
from ixpDataRetriver import spacetrack_data, ixpdb_data, euroix_data, alternative_sources

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["space_ix_data"]  # Database name

# Satellite data
satellite_data = [
    {
        "ORDINAL": "1",
        "COMMENT": "GENERATED VIA SPACETRACK.ORG API",
        "ORIGINATOR": "18 SPCS",
        "NORAD_CAT_ID": "25544",
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_TYPE": "PAYLOAD",
        "CLASSIFICATION_TYPE": "U",
        "INTLDES": "98067A",
        "EPOCH": "2025-02-07 23:54:49",
        "EPOCH_MICROSECONDS": "703904",
        "MEAN_MOTION": "15.4990555",
        "ECCENTRICITY": "0.0003507",
        "INCLINATION": "51.6375",
        "RA_OF_ASC_NODE": "226.9065",
        "ARG_OF_PERICENTER": "286.8821",
        "MEAN_ANOMALY": "210.2731",
        "EPHEMERIS_TYPE": "0",
        "ELEMENT_SET_NO": "999",
        "REV_AT_EPOCH": "49512",
        "BSTAR": "0.00028399",
        "MEAN_MOTION_DOT": "0.00015732",
        "MEAN_MOTION_DDOT": "0",
        "FILE": "4633850",
        "TLE_LINE0": "0 ISS (ZARYA)",
        "TLE_LINE1": "1 25544U 98067A   25038.99640861  .00015732  00000-0  28399-3 0  9993",
        "TLE_LINE2": "2 25544  51.6375 226.9065 0003507 286.8821 210.2731 15.49905550495129",
        "OBJECT_ID": "1998-067A",
        "OBJECT_NUMBER": "25544",
        "SEMIMAJOR_AXIS": "6795.139",
        "PERIOD": "92.909",
        "APOGEE": "419.387",
        "PERIGEE": "414.621",
        "DECAYED": "0"
    }
]

# IX-F Data
ixf_data = [
    {
        "IX-F ID": "1153",
        "Name": "1-IX Kyiv (1-IX Internet Exchange)",
        "City": "Kyiv",
        "Country": "UA",
        "Last updated": "2022-10-18 15:08:19 UTC",
        "API Traffic": "0",
        "MANRS": "0",
        "# of ASNs": "0"
    },
    {
        "IX-F ID": "1152",
        "Name": "1-IX Warsaw (1-IX Internet Exchange Warsaw)",
        "City": "Warsaw",
        "Country": "PL",
        "Last updated": "2022-10-18 15:11:35 UTC",
        "API Traffic": "0",
        "MANRS": "0",
        "# of ASNs": "0"
    },
    {
        "IX-F ID": "899",
        "Name": "48 IX (48 IX)",
        "City": "",
        "Country": "US",
        "Last updated": "2024-10-18 5:06:28 UTC",
        "API Traffic": "0",
        "MANRS": "0",
        "# of ASNs": "5"
    },
    # Add more records here...
]

# Insert into MongoDB collections
db.satellite.insert_many(satellite_data)
db.ixf.insert_many(ixf_data)

print("Data successfully stored in MongoDB!")
