// Minimalist Workbench Frontend Logic
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  loadRawData();
  loadCleanedData();
  loadEDA();
  loadVisualizations();
  loadModel('logistic');
  loadModelComparison();

  const chartDropdown = document.getElementById('chart-dropdown');
  if (chartDropdown) {
    chartDropdown.addEventListener('change', (e) => {
      renderSelectedChart(e.target.value);
    });
  }

  const modelBtns = document.querySelectorAll('.model-btn');
  modelBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      modelBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const modelType = btn.getAttribute('data-model');
      loadModel(modelType);
    });
  });
});

let globalVisData = null;
let mainChartInstance = null;
let featureChartInstance = null;
let compareChartInstance = null;

// Minimal Color Palette
const COLORS = {
  primary: '#2563eb',
  slate: '#0f172a',
  muted: '#64748b',
  border: '#cbd5e1',
  teal: '#0d9488',
  amber: '#d97706',
  rose: '#e11d48',
  subtleBg: '#f1f5f9'
};

function initNavigation() {
  const navBtns = document.querySelectorAll('.nav-btn');
  navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      navBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const targetId = btn.getAttribute('data-target');
      const targetSec = document.getElementById(targetId);
      if (targetSec) {
        targetSec.scrollIntoView({ behavior: 'smooth' });
      }
    });
  });
}

async function loadRawData() {
  try {
    const res = await fetch('/api/raw-data?limit=150');
    const data = await res.json();
    renderRawTable(data);
    setupSearch('raw-search', 'raw-tbody');
  } catch (err) {
    console.error('Error loading raw data:', err);
  }
}

function renderRawTable(payload) {
  const thead = document.getElementById('raw-thead');
  const tbody = document.getElementById('raw-tbody');
  if (!thead || !tbody) return;

  thead.innerHTML = '';
  tbody.innerHTML = '';

  const headerRow = document.createElement('tr');
  payload.columns.forEach(col => {
    const th = document.createElement('th');
    th.textContent = col;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);

  payload.data.forEach((row, i) => {
    const tr = document.createElement('tr');
    payload.columns.forEach(col => {
      const td = document.createElement('td');
      const val = row[col];
      if (col === '#') {
        td.className = 'index-col';
        td.textContent = `# ${val}`;
      } else if (val === 'NaN' || val === null || val === undefined) {
        td.innerHTML = `<span class="nan-badge">NaN</span>`;
      } else {
        td.textContent = val;
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

async function loadCleanedData() {
  try {
    const res = await fetch('/api/cleaned-data?limit=150');
    const data = await res.json();
    renderCleanedTable(data);
    setupSearch('clean-search', 'clean-tbody');
  } catch (err) {
    console.error('Error loading cleaned data:', err);
  }
}

function renderCleanedTable(payload) {
  const thead = document.getElementById('clean-thead');
  const tbody = document.getElementById('clean-tbody');
  if (!thead || !tbody) return;

  thead.innerHTML = '';
  tbody.innerHTML = '';

  const headerRow = document.createElement('tr');
  payload.columns.forEach(col => {
    const th = document.createElement('th');
    th.textContent = col;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);

  payload.data.forEach(row => {
    const tr = document.createElement('tr');
    payload.columns.forEach(col => {
      const td = document.createElement('td');
      const val = row[col];
      if (col === '#') {
        td.className = 'index-col';
        td.textContent = `# ${val}`;
      } else if (['screen_intensity', 'sleep_efficiency', 'screentime_scaled'].includes(col)) {
        td.innerHTML = `<span class="feature-badge">${val}</span>`;
      } else if (['gender_code', 'target_binary'].includes(col)) {
        td.innerHTML = `<span class="imputed-badge">${val}</span>`;
      } else {
        td.textContent = val !== null ? val : '';
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function setupSearch(inputId, tbodyId) {
  const input = document.getElementById(inputId);
  const tbody = document.getElementById(tbodyId);
  if (!input || !tbody) return;

  input.addEventListener('keyup', () => {
    const filter = input.value.toLowerCase();
    const rows = tbody.getElementsByTagName('tr');
    Array.from(rows).forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(filter) ? '' : 'none';
    });
  });
}

async function loadEDA() {
  try {
    const res = await fetch('/api/eda');
    const data = await res.json();

    document.getElementById('kpi-total').textContent = `${data.total_records.toLocaleString()}`;
    const highRatio = data.binary_ratios['High Sleep Debt'] || 0;
    document.getElementById('kpi-target-ratio').textContent = `${highRatio}%`;
    document.getElementById('kpi-target-subtext').textContent = 
      `${data.binary_target_counts['High Sleep Debt']} Debt / ${data.binary_target_counts['Good / Normal Sleep']} Normal`;

    document.getElementById('kpi-screentime').textContent = `${data.key_averages.avg_screentime} m`;
    document.getElementById('kpi-sleep-hrs').textContent = `${data.key_averages.avg_sleep_hours} hrs`;

    const tbody = document.getElementById('eda-stats-tbody');
    if (tbody) {
      tbody.innerHTML = '';
      data.summary_stats.forEach(stat => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${stat.feature}</strong></td>
          <td>${stat.mean}</td>
          <td>${stat.std}</td>
          <td>${stat.min}</td>
          <td>${stat.q25}</td>
          <td>${stat.median}</td>
          <td>${stat.q75}</td>
          <td>${stat.max}</td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {
    console.error('Error loading EDA data:', err);
  }
}

async function loadVisualizations() {
  try {
    const res = await fetch('/api/visualizations');
    globalVisData = await res.json();
    renderSelectedChart('pie');
  } catch (err) {
    console.error('Error loading visualizations data:', err);
  }
}

function renderSelectedChart(type) {
  if (!globalVisData) return;

  const titleElem = document.getElementById('chart-title');
  const descElem = document.getElementById('chart-desc');
  const renderArea = document.getElementById('chart-render-area');

  if (mainChartInstance) {
    mainChartInstance.destroy();
    mainChartInstance = null;
  }

  renderArea.innerHTML = '<canvas id="main-chart"></canvas>';
  const ctx = document.getElementById('main-chart').getContext('2d');

  if (type === 'pie') {
    titleElem.textContent = 'Target Sleep Debt & Demographic Split';
    descElem.textContent = 'Distribution of subjects across sleep debt severity levels.';
    
    mainChartInstance = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: globalVisData.pie.target.labels,
        datasets: [{
          data: globalVisData.pie.target.values,
          backgroundColor: ['#0f172a', '#2563eb', '#64748b', '#94a3b8'],
          borderWidth: 1,
          borderColor: '#ffffff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'right', labels: { color: '#0f172a', font: { family: 'Inter' } } }
        }
      }
    });
  } 
  else if (type === 'bar') {
    titleElem.textContent = 'High Sleep Debt Rate by Primary Bedtime App';
    descElem.textContent = 'Percentage of subjects exhibiting sleep debt categorized by bedtime app.';

    mainChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: globalVisData.bar.app.labels,
        datasets: [{
          label: 'Sleep Debt Rate (%)',
          data: globalVisData.bar.app.rates,
          backgroundColor: '#0f172a',
          borderRadius: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: '#475569' }, grid: { color: '#f1f5f9' } },
          y: { ticks: { color: '#475569' }, grid: { color: '#f1f5f9' }, max: 100 }
        },
        plugins: { legend: { display: false } }
      }
    });
  }
  else if (type === 'scatter') {
    titleElem.textContent = 'Screentime (Min) vs. Sleep Duration (Hours)';
    descElem.textContent = 'Continuous scatterplot showing phone usage against total sleep duration.';

    mainChartInstance = new Chart(ctx, {
      type: 'scatter',
      data: {
        datasets: [
          {
            label: 'High Sleep Debt',
            data: globalVisData.scatter.high_debt,
            backgroundColor: '#e11d48',
            pointRadius: 3
          },
          {
            label: 'Good / Normal Sleep',
            data: globalVisData.scatter.good_sleep,
            backgroundColor: '#2563eb',
            pointRadius: 3
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { title: { display: true, text: 'Bedtime Phone Minutes', color: '#475569' }, ticks: { color: '#475569' }, grid: { color: '#f1f5f9' } },
          y: { title: { display: true, text: 'Total Sleep Hours', color: '#475569' }, ticks: { color: '#475569' }, grid: { color: '#f1f5f9' } }
        },
        plugins: { legend: { labels: { color: '#0f172a' } } }
      }
    });
  }
  else if (type === 'boxplot') {
    titleElem.textContent = 'Sleep Latency Quantiles Grouped by Target Class';
    descElem.textContent = 'Distribution quantiles for sleep latency (minutes).';

    const latencyData = globalVisData.boxplot.sleep_latency_min;
    mainChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['High Sleep Debt', 'Good Sleep'],
        datasets: [
          {
            label: 'Median Latency (min)',
            data: [latencyData.high_debt.median, latencyData.good_sleep.median],
            backgroundColor: ['#0f172a', '#2563eb'],
            borderRadius: 2
          },
          {
            label: 'Q75 Latency (min)',
            data: [latencyData.high_debt.q75, latencyData.good_sleep.q75],
            backgroundColor: ['#64748b', '#94a3b8'],
            borderRadius: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: '#475569' }, grid: { color: '#f1f5f9' } },
          y: { ticks: { color: '#475569' }, grid: { color: '#f1f5f9' } }
        },
        plugins: { legend: { labels: { color: '#0f172a' } } }
      }
    });
  }
  else if (type === 'heatmap') {
    titleElem.textContent = 'Pearson Correlation Matrix Heatmap';
    descElem.textContent = 'Correlation coefficients between numerical features.';

    const cols = globalVisData.heatmap.columns;
    const matrix = globalVisData.heatmap.matrix;

    let html = `<div style="overflow-x:auto;"><table class="heatmap-table"><thead><tr><th></th>`;
    cols.forEach(c => html += `<th>${c}</th>`);
    html += `</tr></thead><tbody>`;

    matrix.forEach((row, i) => {
      html += `<tr><th>${cols[i]}</th>`;
      row.forEach((val, j) => {
        let bg = '#ffffff';
        if (val > 0) {
          bg = `rgba(37, 99, 235, ${Math.min(Math.abs(val) * 0.4 + 0.05, 0.8)})`;
        } else if (val < 0) {
          bg = `rgba(225, 29, 72, ${Math.min(Math.abs(val) * 0.4 + 0.05, 0.8)})`;
        }
        html += `<td><div class="heatmap-cell" style="background:${bg}">${val.toFixed(2)}</div></td>`;
      });
      html += `</tr>`;
    });
    html += `</tbody></table></div>`;

    renderArea.innerHTML = html;
  }
  else if (type === 'line_countplot') {
    titleElem.textContent = 'Age Group Trends & Blue Light Snoozes';
    descElem.textContent = 'Average total sleep hours across age groups.';

    const trend = globalVisData.line_countplot;
    mainChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: trend.age_labels,
        datasets: [
          {
            label: 'Avg Sleep Hours',
            data: trend.sleep_by_age,
            borderColor: '#0f172a',
            backgroundColor: 'rgba(15, 23, 42, 0.05)',
            fill: true,
            tension: 0.1
          },
          {
            label: 'Avg Screentime (scaled / 10)',
            data: trend.phone_by_age.map(x => x / 10),
            borderColor: '#2563eb',
            borderDash: [4, 4],
            tension: 0.1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: '#475569' }, grid: { color: '#f1f5f9' } },
          y: { ticks: { color: '#475569' }, grid: { color: '#f1f5f9' } }
        },
        plugins: { legend: { labels: { color: '#0f172a' } } }
      }
    });
  }
}

async function loadModel(modelType) {
  try {
    const res = await fetch(`/api/train-model?model_type=${modelType}`);
    const data = await res.json();
    renderModelResults(data);
  } catch (err) {
    console.error(`Error training model ${modelType}:`, err);
  }
}

function renderModelResults(data) {
  const m = data.metrics;
  document.getElementById('m-acc').textContent = (m.accuracy * 100).toFixed(2) + '%';
  document.getElementById('m-prec').textContent = (m.precision * 100).toFixed(2) + '%';
  document.getElementById('m-rec').textContent = (m.recall * 100).toFixed(2) + '%';
  document.getElementById('m-f1').textContent = (m.f1_score * 100).toFixed(2) + '%';
  document.getElementById('m-auc').textContent = (m.roc_auc * 100).toFixed(2) + '%';

  const cm = data.confusion_matrix;
  document.getElementById('cm-tn').textContent = cm.tn.toLocaleString();
  document.getElementById('cm-fp').textContent = cm.fp.toLocaleString();
  document.getElementById('cm-fn').textContent = cm.fn.toLocaleString();
  document.getElementById('cm-tp').textContent = cm.tp.toLocaleString();

  const ctx = document.getElementById('feature-chart').getContext('2d');
  if (featureChartInstance) {
    featureChartInstance.destroy();
  }

  const topFeatures = data.feature_importances.slice(0, 7);
  featureChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: topFeatures.map(f => f.feature),
      datasets: [{
        label: 'Importance / Weight',
        data: topFeatures.map(f => f.importance),
        backgroundColor: '#0f172a',
        borderRadius: 2
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: '#475569' }, grid: { color: '#f1f5f9' } },
        y: { ticks: { color: '#0f172a' }, grid: { display: false } }
      },
      plugins: { legend: { display: false } }
    }
  });
}

async function loadModelComparison() {
  try {
    const res = await fetch('/api/compare-models');
    const data = await res.json();
    renderComparison(data);
  } catch (err) {
    console.error('Error loading model comparison:', err);
  }
}

function renderComparison(data) {
  const tbody = document.getElementById('compare-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const models = data.models;
  const bestModelName = data.best_model;

  const modelKeys = Object.keys(models);
  const chartLabels = [];
  const accData = [];
  const precData = [];
  const recData = [];
  const f1Data = [];

  modelKeys.forEach(key => {
    const m = models[key];
    const metrics = m.metrics;

    chartLabels.push(m.display_name.replace(/^[^\s]+\s/, ''));
    accData.push(metrics.accuracy);
    precData.push(metrics.precision);
    recData.push(metrics.recall);
    f1Data.push(metrics.f1_score);

    const isBest = m.display_name === bestModelName;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>
        <strong>${m.display_name.replace(/^[^\s]+\s/, '')}</strong>
        ${isBest ? '<span class="winner-badge">Best Model</span>' : ''}
      </td>
      <td class="${isBest ? 'metric-high' : ''}">${(metrics.accuracy * 100).toFixed(2)}%</td>
      <td class="${isBest ? 'metric-high' : ''}">${(metrics.precision * 100).toFixed(2)}%</td>
      <td class="${isBest ? 'metric-high' : ''}">${(metrics.recall * 100).toFixed(2)}%</td>
      <td class="${isBest ? 'metric-high' : ''}">${(metrics.f1_score * 100).toFixed(2)}%</td>
      <td>${(metrics.roc_auc * 100).toFixed(2)}%</td>
      <td>${isBest ? 'Champion' : 'Trained'}</td>
    `;
    tbody.appendChild(tr);
  });

  const ctx = document.getElementById('compare-chart').getContext('2d');
  if (compareChartInstance) {
    compareChartInstance.destroy();
  }

  compareChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: chartLabels,
      datasets: [
        { label: 'Accuracy', data: accData, backgroundColor: '#0f172a' },
        { label: 'Precision', data: precData, backgroundColor: '#2563eb' },
        { label: 'Recall', data: recData, backgroundColor: '#64748b' },
        { label: 'F1 Score', data: f1Data, backgroundColor: '#94a3b8' }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: '#0f172a' }, grid: { color: '#f1f5f9' } },
        y: { ticks: { color: '#475569' }, grid: { color: '#f1f5f9' }, min: 0.8, max: 1.0 }
      },
      plugins: {
        legend: { labels: { color: '#0f172a' } }
      }
    }
  });
}
