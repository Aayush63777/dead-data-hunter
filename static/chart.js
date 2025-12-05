// static/js/dashboard.js
async function dashboardLoad() {
  await loadRecentScans();
  await drawOverviewChart();
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
    let html = '<ul>';
    data.forEach(d => {
      const w = encodeURIComponent(d.website);
      const scanned = d.scanned_on || '';
      html += `<li><a class="smalllink" href="/report?url=${w}">${d.website}</a> — ${scanned}</li>`;
    });
    html += '</ul>';
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = "<p>Error loading scans.</p>";
  }
}

async function drawOverviewChart() {
  try {
    const res = await fetch('/reports?limit=50');
    const data = await res.json();
    // build dataset: count of outdated_dates per scan
    const labels = data.map(d => d.scanned_on ? d.scanned_on.substr(0,19).replace('T',' ') : 'unknown');
    const values = data.map(d => Array.isArray(d.outdated_dates) ? d.outdated_dates.length : 0);
    const ctx = document.getElementById('overviewChart').getContext('2d');
    if (window._overviewChart) { window._overviewChart.destroy(); }
    window._overviewChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels.reverse(),
        datasets: [{
          label: 'Outdated items per scan',
          data: values.reverse(),
          backgroundColor: 'rgba(11,94,215,0.7)'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { x: { ticks: { maxRotation:45, minRotation:0 } } }
      }
    });
  } catch (e) {
    console.error("chart error", e);
  }
}
