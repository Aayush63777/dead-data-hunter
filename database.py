import os

from pymongo import MongoClient


from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://localhost:27017/",
)

MONGO_DB = os.environ.get(
    "MONGO_DB",
    "dead_data_hunter",
)


_client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000,
)


_db = _client[MONGO_DB]

reports = _db["scan_reports"]


def ensure_indexes():
    """
    Create indexes required by the application.

    The compound index makes website history queries
    faster and keeps the newest scans first.
    """

    try:
        reports.create_index(
            [
                ("website", 1),
                ("scanned_on", -1),
            ]
        )
    except Exception:
        # MongoDB may be unavailable during startup.
        # The application can still start without the index.
        pass