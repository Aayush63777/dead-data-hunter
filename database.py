# database.py

import os

from dotenv import load_dotenv
from pymongo import MongoClient

# Load variables from .env if available.
load_dotenv()

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://localhost:27017/",
)

MONGO_DB = os.environ.get(
    "MONGO_DB",
    "dead_data_hunter",
)

# Create MongoDB client.
_client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000,
)

# Select database.
_db = _client[MONGO_DB]

# Collection for scan reports.
reports = _db["scan_reports"]


def ensure_indexes():
    """
    Create indexes required by the application.

    The index improves history/report queries by website
    and keeps the newest scans first.
    """
    try:
        reports.create_index(
            [
                ("website", 1),
                ("scanned_on", -1),
            ]
        )
    except Exception:
        # MongoDB may be unavailable when the application starts.
        # The application can still run without the index.
        pass