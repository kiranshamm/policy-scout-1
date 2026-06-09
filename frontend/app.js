/* ═══════════════════════════════════════════════════════════════════════
   PolicyScout — Application Logic
   Handles scan submission, polling, results rendering, and PDF download
═══════════════════════════════════════════════════════════════════════ */

// API base URL — set via /frontend/config.js on Vercel (POLICYSCOUT_API_URL env var)
// Falls back to localhost:8000 for local development
const API_BASE = (window.__POLICYSCOUT_CONFIG__ && window.__POLICYSCOUT_CONFIG__.apiBase)
  || 'http://localhost:8000';

// ── State ──────────────────────────────────────────────────────────────
let currentScanId = null;
let pollTimer = null;
let allResults = [];
let currentFilter = 'all';

// ── Category Icon Map ──────────────────────────────────────────────────
const CATEGORY_ICONS = {
  'Privacy Policy': { icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`, color: '#6366f1' },
  'Terms & Conditions': { icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`, color: '#06b6d4' },
  'Refund Policy': { icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg>`, color: '#f59e0b' },
  'Shipping Policy': { icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>`, color: '#22c55e' },
  'Contact Us': { icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.81a19.79 19.79 0 01-3.07-8.63A2 2 0 012 1h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.91 8.09a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>`, color: '#ec4899' },
  'About Us': { icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>`, color: '#8b5cf6' },
  'FAQ': { icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`, color: '#14b8a6' },
  'Cancellation Policy': { icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`, color: '#f97316' },
};

// ── View Management ────────────────────────────────────────────────────
function showView(name) {
  ['home', 'scanning', 'results', 'error'].forEach(v => {
    document.getElementById(`view-${v}`).classList.toggle('hidden', v !== name);
  });
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showHome() {
  stopPolling();
  showView('home');
  document.getElementById('scan-input').value = '';
  document.getElementById('scan-error').textContent = '';
}

// ── Scan Submission ────────────────────────────────────────────────────
async function startScan() {
  const input = document.getElementById('scan-input');
  const errorEl = document.getElementById('scan-error');
  const btn = document.getElementById('scan-btn');

  let url = input.value.trim();
  if (!url) {
    errorEl.textContent = 'Please enter a website URL.';
    input.focus();
    return;
  }

  // Auto-prepend https if missing
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    url = 'https://' + url;
  }

  errorEl.textContent = '';
  btn.disabled = true;
  btn.querySelector('.btn-scan-text').textContent = 'Starting…';

  try {
    const response = await fetch(`${API_BASE}/scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Server error: ${response.status}`);
    }

    const data = await response.json();
    currentScanId = data.scan_id;

    // Extract domain for display
    let domain = url;
    try { domain = new URL(url).hostname.replace('www.', ''); } catch (_) {}

    showScanningView(domain, url);
    startPolling(data.scan_id);

  } catch (err) {
    errorEl.textContent = err.message || 'Could not connect to the API. Make sure the backend is running.';
    btn.disabled = false;
    btn.querySelector('.btn-scan-text').textContent = 'Scan Website';
  }
}

// ── Scanning View ──────────────────────────────────────────────────────
function showScanningView(domain, url) {
  document.getElementById('scanning-domain').textContent = domain;
  showView('scanning');
  animateScanSteps();
}

function animateScanSteps() {
  const steps = ['step-crawl', 'step-classify', 'step-score', 'step-report'];
  const labels = ['Crawling website links…', 'Classifying policy pages…', 'Calculating compliance score…', 'Building report…'];
  const progressSteps = [20, 50, 75, 90];

  // Reset all
  steps.forEach(id => {
    const el = document.getElementById(id);
    el.classList.remove('active', 'done');
    el.querySelector('.step-status').className = 'step-status pending';
    el.querySelector('.step-status').innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/></svg>`;
  });

  setProgress(5, 'Connecting to website…');

  // Activate steps progressively (just for UX — real progress is from polling)
  let i = 0;
  const interval = setInterval(() => {
    if (i >= steps.length) { clearInterval(interval); return; }
    if (i > 0) {
      // Mark previous as done
      const prevEl = document.getElementById(steps[i - 1]);
      prevEl.classList.remove('active');
      prevEl.classList.add('done');
      prevEl.querySelector('.step-status').className = 'step-status done';
      prevEl.querySelector('.step-status').innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/></svg>`;
    }
    const el = document.getElementById(steps[i]);
    el.classList.add('active');
    el.querySelector('.step-status').className = 'step-status active';
    el.querySelector('.step-status').innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;
    setProgress(progressSteps[i], labels[i]);
    i++;
  }, 4000);
}

function setProgress(pct, label) {
  document.getElementById('progress-fill').style.width = `${pct}%`;
  document.getElementById('progress-label').textContent = label;
}

// ── Polling ────────────────────────────────────────────────────────────
function startPolling(scanId) {
  stopPolling();
  pollTimer = setInterval(() => pollScan(scanId), 2500);
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function pollScan(scanId) {
  try {
    const resp = await fetch(`${API_BASE}/scan/${scanId}`);
    if (!resp.ok) return;

    const data = await resp.json();

    if (data.status === 'completed') {
      stopPolling();
      setProgress(100, 'Scan complete!');
      setTimeout(() => showResults(data), 600);
    } else if (data.status === 'failed') {
      stopPolling();
      showError(data.error_message || 'The scan failed. Please try again.');
    }
  } catch (err) {
    console.warn('Poll error:', err);
  }
}

// ── Results View ───────────────────────────────────────────────────────
function showResults(data) {
  allResults = data.results || [];
  currentFilter = 'all';

  // Domain + date
  let domain = data.url;
  try { domain = new URL(data.url).hostname.replace('www.', ''); } catch (_) {}
  document.getElementById('results-domain').textContent = domain;
  document.getElementById('results-date').textContent = `Scanned ${formatDate(data.created_at)}`;

  // Stats
  const found = allResults.filter(r => r.status === 'found').length;
  const missing = allResults.filter(r => r.status === 'missing').length;
  const score = data.score || 0;

  document.getElementById('stat-links').textContent = data.total_links_found || '—';
  document.getElementById('stat-found').textContent = found;
  document.getElementById('stat-missing').textContent = missing;
  document.getElementById('stat-score').textContent = `${score}%`;

  document.getElementById('legend-found').textContent = `${found} Found`;
  document.getElementById('legend-missing').textContent = `${missing} Missing`;

  // Score ring animation
  animateScoreRing(score);

  // Missing alerts
  renderAlerts(allResults.filter(r => r.status === 'missing'));

  // Table
  renderTable(allResults);

  // Reset filter buttons
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('filter-all').classList.add('active');

  showView('results');
}

function animateScoreRing(score) {
  const circle = document.getElementById('score-circle');
  const circumference = 314.16;
  const offset = circumference - (score / 100) * circumference;

  // Color based on score
  let color;
  if (score >= 75) color = '#22c55e';
  else if (score >= 50) color = '#f59e0b';
  else color = '#ef4444';

  circle.style.stroke = color;
  document.getElementById('score-number').style.color = color;

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      circle.style.strokeDashoffset = offset;
      animateCounter('score-number', 0, score, '%', 1500);
    });
  });
}

function animateCounter(id, from, to, suffix, duration) {
  const el = document.getElementById(id);
  const start = performance.now();
  const update = (t) => {
    const progress = Math.min((t - start) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 4);
    el.textContent = `${Math.round(from + (to - from) * ease)}${suffix}`;
    if (progress < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

function renderAlerts(missing) {
  const el = document.getElementById('alert-section');
  el.innerHTML = '';
  missing.forEach(item => {
    const chip = document.createElement('div');
    chip.className = 'alert-chip';
    chip.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
        <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
      ${item.category} Missing
    `;
    el.appendChild(chip);
  });
}

function renderTable(results) {
  const body = document.getElementById('results-table-body');
  body.innerHTML = '';

  const filtered = currentFilter === 'all' ? results
    : results.filter(r => r.status === currentFilter);

  filtered.forEach((item, idx) => {
    const info = CATEGORY_ICONS[item.category] || { icon: '?', color: '#64748b' };
    const isFound = item.status === 'found';
    const conf = Math.round((item.confidence || 0) * 100);

    const row = document.createElement('div');
    row.className = `table-row ${!isFound ? 'row-missing' : ''}`;
    row.style.animationDelay = `${idx * 40}ms`;

    row.innerHTML = `
      <div class="td-category">
        <div class="category-icon" style="background: ${info.color}20; color: ${info.color}">
          ${info.icon}
        </div>
        ${item.category}
      </div>
      <div>
        <span class="status-badge ${item.status}">
          ${isFound
            ? `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"/></svg> Found`
            : `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg> Missing`
          }
        </span>
      </div>
      <div class="td-url">
        ${isFound && item.url
          ? `<a href="${escHtml(item.url)}" target="_blank" rel="noopener noreferrer" title="${escHtml(item.url)}">${escHtml(item.url)}</a>`
          : `<span class="missing-text">Not found on website</span>`
        }
      </div>
      <div class="td-confidence">
        ${isFound ? `
          <div class="confidence-bar-wrapper">
            <div class="confidence-bar">
              <div class="confidence-fill" style="width: ${conf}%"></div>
            </div>
            <span class="confidence-pct">${conf}%</span>
          </div>
        ` : '<span style="color: var(--text-dim)">—</span>'}
      </div>
    `;
    body.appendChild(row);
  });

  if (filtered.length === 0) {
    body.innerHTML = `<div style="padding: 40px; text-align: center; color: var(--text-dim);">No results for this filter.</div>`;
  }
}

function filterResults(filter, btn) {
  currentFilter = filter;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderTable(allResults);
}

// ── PDF Download ───────────────────────────────────────────────────────
async function downloadReport() {
  if (!currentScanId) return;
  const btn = document.getElementById('btn-download');
  btn.textContent = 'Generating…';
  btn.disabled = true;

  try {
    const resp = await fetch(`${API_BASE}/report/${currentScanId}`);
    if (!resp.ok) throw new Error('Report generation failed');

    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `compliance-report-${currentScanId.slice(0, 8)}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    alert('Could not download report: ' + err.message);
  } finally {
    btn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      Download PDF Report
    `;
    btn.disabled = false;
  }
}

// ── Error View ─────────────────────────────────────────────────────────
function showError(message) {
  document.getElementById('error-message').textContent = message;
  showView('error');
}

// ── Utilities ──────────────────────────────────────────────────────────
function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatDate(isoStr) {
  if (!isoStr) return 'just now';
  try {
    return new Intl.DateTimeFormat('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(isoStr));
  } catch (_) { return isoStr; }
}

// ── Keyboard Handling ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('scan-input');
  if (input) {
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') startScan();
    });
  }

  // Inject SVG gradient for score ring
  const svgDef = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svgDef.setAttribute('width', '0');
  svgDef.setAttribute('height', '0');
  svgDef.style.position = 'absolute';
  svgDef.innerHTML = `
    <defs>
      <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#6366f1"/>
        <stop offset="50%" stop-color="#8b5cf6"/>
        <stop offset="100%" stop-color="#06b6d4"/>
      </linearGradient>
    </defs>
  `;
  document.body.prepend(svgDef);

  // Navbar scroll effect
  window.addEventListener('scroll', () => {
    const nav = document.getElementById('navbar');
    if (window.scrollY > 20) nav.style.background = 'rgba(2, 6, 23, 0.95)';
    else nav.style.background = 'rgba(2, 6, 23, 0.8)';
  });
});

// ── Demo Mode (when backend is unavailable) ───────────────────────────
// Intercept fetch errors and provide a mock response for demo purposes
const _origFetch = window.fetch;
window.fetch = async function(...args) {
  try {
    const resp = await _origFetch(...args);
    return resp;
  } catch (err) {
    const url = typeof args[0] === 'string' ? args[0] : args[0].url || '';

    // Mock POST /scan
    if (url.includes('/scan') && !url.match(/\/scan\/[a-z0-9-]{36}/)) {
      const mockId = 'demo-' + Math.random().toString(36).slice(2, 10);
      // Schedule mock completion
      _scheduleMockCompletion(mockId, args[1]?.body);
      return new Response(JSON.stringify({ scan_id: mockId, status: 'queued', message: 'Demo mode — backend not connected.' }), {
        status: 202, headers: { 'Content-Type': 'application/json' }
      });
    }

    // Mock GET /scan/{id}
    const pollMatch = url.match(/\/scan\/(demo-[a-z0-9]+)$/);
    if (pollMatch) {
      const stored = sessionStorage.getItem('mock_' + pollMatch[1]);
      if (stored) {
        return new Response(stored, { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
      return new Response(JSON.stringify({ scan_id: pollMatch[1], status: 'running', score: 0, results: [], total_links_found: 0, created_at: new Date().toISOString() }), {
        status: 200, headers: { 'Content-Type': 'application/json' }
      });
    }

    // Mock GET /report/{id}
    if (url.includes('/report/')) {
      return new Response(new Blob(['PDF demo not available in offline mode'], { type: 'application/pdf' }), { status: 200 });
    }

    throw err;
  }
};

function _scheduleMockCompletion(scanId, body) {
  let submittedUrl = 'https://example.com';
  try { submittedUrl = JSON.parse(body).url; } catch (_) {}

  let domain = submittedUrl;
  try { domain = new URL(submittedUrl).hostname.replace('www.', ''); } catch (_) {}

  const buildUrl = (path) => `${submittedUrl.replace(/\/$/, '')}/${path}`;

  const mockResults = [
    { category: 'Privacy Policy', status: 'found', url: buildUrl('privacy-policy'), title: 'Privacy Policy', confidence: 0.97 },
    { category: 'Terms & Conditions', status: 'found', url: buildUrl('terms'), title: 'Terms & Conditions', confidence: 0.95 },
    { category: 'Refund Policy', status: 'found', url: buildUrl('refund-policy'), title: 'Refund Policy', confidence: 0.91 },
    { category: 'Shipping Policy', status: 'missing', url: null, title: null, confidence: 0 },
    { category: 'Contact Us', status: 'found', url: buildUrl('contact'), title: 'Contact Us', confidence: 0.93 },
    { category: 'About Us', status: 'found', url: buildUrl('about'), title: 'About Us', confidence: 0.88 },
    { category: 'FAQ', status: 'found', url: buildUrl('faq'), title: 'FAQ', confidence: 0.90 },
    { category: 'Cancellation Policy', status: 'missing', url: null, title: null, confidence: 0 },
  ];

  const score = (mockResults.filter(r => r.status === 'found').length / mockResults.length) * 100;

  const completedData = JSON.stringify({
    scan_id: scanId,
    url: submittedUrl,
    domain: domain,
    status: 'completed',
    score: Math.round(score * 10) / 10,
    total_links_found: 47,
    created_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    results: mockResults,
    error_message: null,
  });

  // Store after ~12 seconds (simulates real scan time)
  setTimeout(() => {
    sessionStorage.setItem('mock_' + scanId, completedData);
  }, 12000);
}
