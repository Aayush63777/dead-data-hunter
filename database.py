# database.py
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "dead_data_hunter")

_client = MongoClient(MONGO_URI)
_db = _client[MONGO_DB]

# collection for scan reports
reports = _db["scan_reports"]

# helper: create index (safe to call at startup)
def ensure_indexes():
    try:
        reports.create_index([("website", 1), ("scanned_on", -1)])
    except Exception:
        pass
