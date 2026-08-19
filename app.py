import json
import os
from datetime import UTC, datetime
from urllib.parse import quote, unquote

from bson import ObjectId
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from database import ensure_indexes, reports
from scraper import scrape_website


# --------------------------------------------------
# Helper: Convert MongoDB ObjectId to string
# --------------------------------------------------

def convert_objectid(data):
    """Recursively convert MongoDB ObjectId values to strings."""

    if isinstance(data, ObjectId):
        return str(data)

    if isinstance(data, list):
        return [convert_objectid(item) for item in data]

    if isinstance(data, dict):
        return {
            key: convert_objectid(value)
            for key, value in data.items()
        }

    return data


# --------------------------------------------------
# Flask configuration
# --------------------------------------------------

APP_PORT = int(
    os.environ.get(
        "PORT",
        os.environ.get("FLASK_PORT", 5000),
    )
)

APP_HOST = os.environ.get(
    "FLASK_HOST",
    "0.0.0.0",
)

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)


# --------------------------------------------------
# MongoDB indexes
# --------------------------------------------------

ensure_indexes()


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def index():
    """Render the main scanner page."""

    return render_template("index.html")


# --------------------------------------------------
# SCAN API
# --------------------------------------------------

@app.route("/scan", methods=["POST"])
def scan_api():
    """Scan a website and save the generated report."""

    data = request.get_json(silent=True) or {}

    url = (
        data.get("url")
        or request.form.get("url")
        or ""
    ).strip()

    if not url:
        return jsonify({
            "error": "URL missing",
        }), 400

    # Add HTTP scheme when only a domain is provided.
    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    # --------------------------------------------------
    # Read crawl settings
    # --------------------------------------------------

    try:
        depth = int(
            data.get("depth")
            or request.form.get("depth")
            or 2
        )
    except (TypeError, ValueError):
        depth = 2

    try:
        max_pages = int(
            data.get("max_pages")
            or request.form.get("max_pages")
            or 8
        )
    except (TypeError, ValueError):
        max_pages = 8

    try:
        max_links_to_check = int(
            data.get("max_links_to_check")
            or request.form.get("max_links_to_check")
            or 50
        )
    except (TypeError, ValueError):
        max_links_to_check = 50

    # Keep crawler settings within safe limits.
    depth = max(1, min(depth, 3))
    max_pages = max(1, min(max_pages, 25))
    max_links_to_check = max(
        10,
        min(max_links_to_check, 100),
    )

    # --------------------------------------------------
    # Run scanner
    # --------------------------------------------------

    try:
        result = scrape_website(
            url,
            max_links_to_check=max_links_to_check,
            max_depth=depth,
            max_pages=max_pages,
        )
    except Exception as exc:
        return jsonify({
            "error": "Scan failed",
            "message": str(exc),
        }), 500

    # Add scan metadata.
    result["scanned_on"] = datetime.now(UTC).isoformat()
    result["website"] = url

    # --------------------------------------------------
    # Save report to MongoDB
    # --------------------------------------------------

    try:
        reports.insert_one(result)
    except Exception as exc:
        # Scanner result should still be returned
        # if MongoDB is temporarily unavailable.
        result["_db_error"] = "Database unavailable"
        print("MongoDB insert failed:", exc)

    # --------------------------------------------------
    # Save local JSON report
    # --------------------------------------------------

    try:
        with open(
            "report.json",
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                result,
                file,
                indent=2,
                default=str,
                ensure_ascii=False,
            )
    except OSError:
        # Local report creation is optional.
        pass

    # --------------------------------------------------
    # Form submission
    # --------------------------------------------------

    if request.form.get("url"):
        return redirect(
            url_for(
                "report_detail",
                url=quote(url, safe=""),
            )
        )

    # --------------------------------------------------
    # JSON API response
    # --------------------------------------------------

    return jsonify({
        "message": "Scan Complete",
        "data": convert_objectid(result),
    })


# --------------------------------------------------
# REPORTS API
# --------------------------------------------------

@app.route("/reports")
def get_reports():
    """Return recent scan reports."""

    try:
        limit = int(
            request.args.get("limit", 50)
        )
    except (TypeError, ValueError):
        limit = 50

    # Prevent unreasonable limits.
    limit = max(1, min(limit, 100))

    try:
        docs = list(
            reports.find()
            .sort("scanned_on", -1)
            .limit(limit)
        )
    except Exception:
        return jsonify({
            "error": "Unable to fetch reports",
        }), 500

    return jsonify(convert_objectid(docs))


# --------------------------------------------------
# HISTORY API
# --------------------------------------------------

@app.route("/history/<path:url>")
def history_page(url):
    """Return scan history for a specific website."""

    decoded_url = unquote(url)

    try:
        docs = list(
            reports.find({
                "website": decoded_url,
            })
            .sort("scanned_on", -1)
        )
    except Exception:
        return jsonify({
            "error": "Unable to fetch history",
        }), 500

    return jsonify(convert_objectid(docs))


# --------------------------------------------------
# REPORT DETAIL
# --------------------------------------------------

@app.route("/report")
def report_detail():
    """Render the latest report for a website."""

    url = request.args.get(
        "url",
        "",
    ).strip()

    if not url:
        return (
            "url param required "
            "(ex: /report?url=https://example.com)",
            400,
        )

    try:
        doc = reports.find_one(
            {
                "website": url,
            },
            sort=[
                (
                    "scanned_on",
                    -1,
                )
            ],
        )
    except Exception:
        return "Unable to load report", 500

    if not doc:
        return render_template(
            "report_detail.html",
            report=None,
            website=url,
        )

    doc = convert_objectid(doc)

    return render_template(
        "report_detail.html",
        report=doc,
        website=url,
    )


# --------------------------------------------------
# RUN SERVER
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host=APP_HOST,
        port=APP_PORT,
        debug=False,
    )