# Dead Data Hunter

Dead Data Hunter scans any website and detects:

- Outdated years / stale dates
- Expired deadlines
- Broken links
- Invalid contact numbers
- Missing / inaccessible PDFs & documents

---

## 🧰 Tech Stack

- **Python 3**
- **Flask**
- **Requests**
- **BeautifulSoup**
- **MongoDB**

---

## 🚀 Quickstart (Local Setup)

### 1) Clone the repo

```bash
git clone <your-repo-url>
cd dead-data-hunter
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Start the application

```bash
python app.py
```

The Flask application will start locally and provide the Dead Data Hunter scanning dashboard.

---

## 🔎 Website Scanning

The dashboard allows you to enter a website URL and configure the scan before starting it.

You can control:

- **Crawl depth** — how deeply the scanner follows links.
- **Max pages** — maximum number of pages to crawl.
- **Max links** — maximum number of links to analyze.

You can also trigger a scan through the API:

```http
POST /scan
```

Example request:

```json
{
  "url": "https://example.com"
}
```

### Scan Dashboard Output

The following screenshot shows the application running locally with the website scanning interface and recent scan results.

![Dead Data Hunter scanning dashboard](assets/scan-dashboard.png)

---

## 📊 Scan Results & Analytics

After scans are completed, Dead Data Hunter displays recent scans with their severity and detected issue count.

The dashboard supports the following severity levels:

- **LOW**
- **MEDIUM**
- **HIGH**
- **CRITICAL**

The generated output also provides an analytics summary, including total scans, average issues per scan, healthy sites, and total issues found.

### Example Output

![Dead Data Hunter analytics summary](assets/analytics-summary.png)

The output shown in the generated scan report includes:

| Metric | Result |
|---|---:|
| Total Scans | 21 |
| Avg Issues / Scan | 5 |
| Healthy Sites | 12 |
| Healthy Sites (%) | 57% |
| Total Issues Found | 108 |

### Scan Metrics Trend

The dashboard visualizes detected issues over time and separates them into:

- **Outdated Items**
- **Broken Links**
- **Invalid Contacts**

![Dead Data Hunter scan metrics trend](assets/scan-analytics.png)

---

## 🧪 Example Scan Results

The generated output contains scan results for multiple websites, with each result showing its timestamp, severity, and number of detected issues.

Examples include:

- `https://github.com/Aayush63777`
- `https://github.com`
- `https://www.bbc.com/news`
- `https://httpbin.org`
- `https://example.com`
- `https://www.wikipedia.org`
- `https://www.w3schools.com/`

---

## 🎯 Purpose

Dead Data Hunter helps identify potentially stale or unusable website content so that website owners and developers can quickly find data that may need to be reviewed, updated, or fixed.
