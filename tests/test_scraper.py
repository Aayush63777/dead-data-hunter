from scraper import classify_scan_summary


def test_classify_scan_summary_returns_severity_and_counts():
    summary = classify_scan_summary(
        outdated_dates=[2020, 2021],
        broken_links=[{"url": "https://example.com/missing", "status": 404}],
        invalid_contacts=[{"raw": "1234567890", "digits": "1234567890"}],
        resources=["https://example.com/a.pdf", "https://example.com/b.pdf"],
    )

    assert summary["total_issues"] == 5
    assert summary["severity"] in {"low", "medium", "high", "critical"}
    assert summary["counts"]["outdated_dates"] == 2
    assert summary["counts"]["broken_links"] == 1
    assert summary["counts"]["invalid_contacts"] == 1
    assert summary["counts"]["resources"] == 2
