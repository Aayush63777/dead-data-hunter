import os
import json
from flask import Flask, request, jsonify, render_template, redirect, url_for
from datetime import datetime, UTC
from scraper import scrape_website
from database import reports, ensure_indexes
from urllib.parse import quote, unquote
from pymongo import MongoClient
from bson import ObjectId

# --------------------------------------------------
# 🔥 FIX — Helper to convert ObjectId → str
# --------------------------------------------------
def convert_objectid(data):
    if isinstance(data, list):
        return [convert_objectid(item) for item in data]
    if isinstance(data, dict):
        return {k: convert_objectid(v) for k, v in data.items()}
    if isinstance(data, ObjectId):
        return str(data)
    return data


# MongoDB client
client = MongoClient("mongodb://localhost:27017/")
db = client["dead_data_hunter"]
# collection = db["reports"]
collection = db["scan_reports"]
reports = collection


APP_PORT = int(os.environ.get("FLASK_PORT", 5000))
APP_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")

app = Flask(__name__, template_folder="templates", static_folder="static")

# Ensure indexes exist
ensure_indexes()

# HOME page
@app.route("/")
def index():
    return render_template("index.html")


# --------------------------------------------------
# 🚀 /scan API — MAIN FIX APPLIED HERE
# --------------------------------------------------
@app.route("/scan", methods=["POST"])
def scan_api():
    data = request.get_json() or {}
    url = data.get("url") or request.form.get("url")

    if not url:
        return jsonify({"error": "URL missing"}), 400

    # Auto prepend http:// if missing
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url

    # Scrape website
    result = scrape_website(url)
    result["scanned_on"] = datetime.now(UTC).isoformat()
    result["website"] = url

    # Save to DB
    try:
        reports.insert_one(result)
    except Exception as e:
        result["_db_error"] = str(e)

    # Save local JSON copy
    try:
        with open("report.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str, ensure_ascii=False)
    except:
        pass

    # If form request → redirect to report page
    if request.form.get("url"):
        return redirect(url_for("report_detail", url=quote(url, safe="")))

    # API JSON response
    return jsonify({
        "message": "Scan Complete",
        "data": convert_objectid(result)
    })


# --------------------------------------------------
# 📌 /reports API — FIXED WITH convert_objectid
# --------------------------------------------------
@app.route("/reports")
def get_reports():
    try:
        limit = int(request.args.get("limit", 50))
    except:
        limit = 50

    docs = list(reports.find().sort("scanned_on", -1).limit(limit))
    docs = convert_objectid(docs)

    return jsonify(docs)


# --------------------------------------------------
# 📌 /history API — FIXED
# --------------------------------------------------
@app.route("/history/<path:url>")
def history_page(url):
    decoded = unquote(url)
    docs = list(reports.find({"website": decoded}).sort("scanned_on", -1))
    docs = convert_objectid(docs)

    return jsonify(docs)


# --------------------------------------------------
# 📌 Report detail HTML page
# --------------------------------------------------
@app.route("/report")
def report_detail():
    url = request.args.get("url")
    if not url:
        return "url param required (ex: /report?url=https://example.com)", 400

    doc = reports.find_one({"website": url}, sort=[("scanned_on", -1)])

    if not doc:
        return render_template("report_detail.html", report=None, website=url)

    doc = convert_objectid(doc)
    return render_template("report_detail.html", report=doc, website=url)


# --------------------------------------------------
# Run server
# --------------------------------------------------
if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=True)
