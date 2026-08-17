// static/js/dashboard.js
async function dashboardLoad() {
  await loadRecentScans();
  await drawOverviewChart();
  await loadAnalyticsSummary();
}

async function loadRecentScans() {
  const el = document.getElementById('recentList');
  el.innerHTML = "Loading...";
  try {
    const res = await fetch('/reports?limit=20');
    const data = await res.json();
    if (!Array.isArray(data) || data.length === 0) {
      el.innerHTML = "<p>No recent scans yet.</p>";
      return;
    }
    let html = '<div class="recent-scans-list">';
    data.forEach((d, i) => {
      const w = encodeURIComponent(d.website);
      const scanned = d.scanned_on || '';
      const issues = (d.outdated_dates?.length || 0) + (d.broken_links?.length || 0) + (d.invalid_contacts?.length || 0) + (d.resources?.length || 0);
      const severity = d.summary?.severity || (issues >= 25 ? 'critical' : issues >= 15 ? 'high' : issues >= 8 ? 'medium' : 'low');
      const severityClass = severity.toLowerCase();
      const color = severityClass === 'critical' ? '#dc3545' : severityClass === 'high' ? '#ff7a00' : severityClass === 'medium' ? '#ffc107' : '#28a745';
      html += `
        <a class="scan-item" href="/report?url=${w}" style="animation-delay: ${i * 0.05}s">
          <div class="scan-item-left">
            <div class="scan-website">${d.website}</div>
            <div class="scan-date">${scanned}</div>
          </div>
          <div class="scan-item-right">
            <span class="scan-severity ${severityClass}">${severity}</span>
            <span class="scan-indicator" style="background: ${color}">⚠ ${issues}</span>
          </div>
        </a>
      `;
    });
    html += '</div>';
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = "<p>Error loading scans.</p>";
  }
}

async function drawOverviewChart() {
  try {
    const res = await fetch('/reports?limit=50');
    const data = await res.json();
    
    // Build datasets for multi-chart view
    const labels = data.map(d => d.scanned_on ? d.scanned_on.substr(0,10) : 'unknown');
    const outdatedValues = data.map(d => Array.isArray(d.outdated_dates) ? d.outdated_dates.length : 0);
    const brokenValues = data.map(d => Array.isArray(d.broken_links) ? d.broken_links.length : 0);
    const contactValues = data.map(d => Array.isArray(d.invalid_contacts) ? d.invalid_contacts.length : 0);
    const resourceValues = data.map(d => Array.isArray(d.resources) ? d.resources.length : 0);
    
    const ctx = document.getElementById('overviewChart').getContext('2d');
    if (window._overviewChart) { window._overviewChart.destroy(); }
    
    window._overviewChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels.reverse(),
        datasets: [
          {
            label: 'Outdated Items',
            data: outdatedValues.reverse(),
            backgroundColor: 'rgba(255, 193, 7, 0.8)',
            borderColor: '#ffc107',
            borderWidth: 1,
            borderRadius: 6,
            tension: 0.4
          },
          {
            label: 'Broken Links',
            data: brokenValues.reverse(),
            backgroundColor: 'rgba(220, 53, 69, 0.8)',
            borderColor: '#dc3545',
            borderWidth: 1,
            borderRadius: 6,
            tension: 0.4
          },
          {
            label: 'Invalid Contacts',
            data: contactValues.reverse(),
            backgroundColor: 'rgba(255, 107, 107, 0.7)',
            borderColor: '#ff6b6b',
            borderWidth: 1,
            borderRadius: 6,
            tension: 0.4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: { padding: 15, font: { size: 12, weight: 'bold' } }
          },
          tooltip: {
            backgroundColor: 'rgba(0,0,0,0.8)',
            padding: 12,
            titleFont: { size: 13, weight: 'bold' },
            bodyFont: { size: 12 },
            borderColor: 'rgba(255,255,255,0.2)',
            borderWidth: 1,
            cornerRadius: 6
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { maxRotation: 45, minRotation: 0, font: { size: 11 } }
          },
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(0,0,0,0.05)', drawBorder: false },
            ticks: { font: { size: 11 } }
          }
        }
      }
    });
  } catch (e) {
    console.error("chart error", e);
  }
}

async function loadAnalyticsSummary() {
  try {
    const res = await fetch('/reports?limit=100');
    const data = await res.json();
    
    if (!Array.isArray(data) || data.length === 0) return;
    
    // Calculate metrics
    const totalScans = data.length;
    const totalOutdated = data.reduce((sum, d) => sum + (d.outdated_dates?.length || 0), 0);
    const totalBroken = data.reduce((sum, d) => sum + (d.broken_links?.length || 0), 0);
    const totalInvalid = data.reduce((sum, d) => sum + (d.invalid_contacts?.length || 0), 0);
    const avgIssues = Math.round((totalOutdated + totalBroken + totalInvalid) / totalScans);
    const healthyScans = data.filter(d => 
      (d.outdated_dates?.length || 0) === 0 && 
      (d.broken_links?.length || 0) === 0
    ).length;
    
    // Find stats element or create one
    let statsEl = document.getElementById('analyticsStats');
    if (statsEl) {
      statsEl.innerHTML = `
        <div class="analytics-grid">
          <div class="analytics-card">
            <div class="analytics-label">Total Scans</div>
            <div class="analytics-value">${totalScans}</div>
          </div>
          <div class="analytics-card">
            <div class="analytics-label">Avg Issues/Scan</div>
            <div class="analytics-value">${avgIssues}</div>
          </div>
          <div class="analytics-card">
            <div class="analytics-label">Healthy Sites</div>
            <div class="analytics-value">${healthyScans}</div>
            <div class="analytics-percent">${((healthyScans/totalScans)*100).toFixed(0)}%</div>
          </div>
          <div class="analytics-card">
            <div class="analytics-label">Total Issues Found</div>
            <div class="analytics-value">${totalOutdated + totalBroken + totalInvalid}</div>
          </div>
        </div>
      `;
    }
  } catch (e) {
    console.error("analytics error", e);
  }
}
