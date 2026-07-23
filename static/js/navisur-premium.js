/**
 * navisur-premium.js — NAVISUR v9.9
 * Micro-animations, sparklines SVG, ripple, indicateur connectivité.
 * Aucune dépendance externe.
 */

/* ── 1. Compteurs animés ──────────────────────────────────── */
function animateCounter(el, target, suffix, decimals) {
  if (!el) return;
  suffix = suffix || '';
  decimals = decimals || 0;
  const duration = 600;
  const start = performance.now();
  const easeOut = t => 1 - Math.pow(1 - t, 3);

  function frame(now) {
    const elapsed = Math.min((now - start) / duration, 1);
    const val = easeOut(elapsed) * target;
    const display = decimals > 0
      ? val.toFixed(decimals).replace('.', ',')
      : Math.floor(val).toLocaleString('fr-FR');
    el.textContent = display + suffix;
    if (elapsed < 1) requestAnimationFrame(frame);
    else el.textContent = (decimals > 0 ? target.toFixed(decimals).replace('.', ',') : target.toLocaleString('fr-FR')) + suffix;
  }
  requestAnimationFrame(frame);
}

/* ── 2. Sparkline SVG ──────────────────────────────────────── */
function buildSparkline(containerId, values) {
  const el = document.getElementById(containerId);
  if (!el || !values || values.length < 2) return;

  const W = 80, H = 28;
  const max = Math.max(...values) || 1;
  const min = Math.min(...values);
  const range = max - min || 1;

  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * W;
    const y = H - ((v - min) / range) * (H - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const fillPts = `0,${H} ${pts} ${W},${H}`;
  const uid = containerId + '_g';

  el.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" class="sparkline" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="${uid}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stop-color="#c9a84c" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="#c9a84c" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <polyline points="${fillPts}" fill="url(#${uid})" stroke="none"/>
      <polyline points="${pts}" fill="none"
        stroke="#c9a84c" stroke-width="1.6"
        stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`;
}

/* ── 3. Effet ripple sur les boutons ──────────────────────── */
function initRipple() {
  document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('mousedown', function(e) {
      const rect = this.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width  * 100).toFixed(1);
      const y = ((e.clientY - rect.top)  / rect.height * 100).toFixed(1);
      this.style.setProperty('--rx', x + '%');
      this.style.setProperty('--ry', y + '%');
    });
  });
}

/* ── 4. Indicateur connectivité dans la sidebar ───────────── */
function initConnectivity() {
  const dot = document.querySelector('.connectivity-dot');
  if (!dot) return;
  function update() {
    const online = navigator.onLine;
    dot.classList.toggle('online',  online);
    dot.classList.toggle('offline', !online);
    const label = dot.nextElementSibling;
    if (label) label.textContent = online ? 'En ligne' : 'Hors ligne';
  }
  update();
  window.addEventListener('online',  update);
  window.addEventListener('offline', update);
}

/* ── 5. Animation de la page (cards in cascade) ──────────── */
function initPageAnimations() {
  // Appliquer fadeInUp sur les cards du dashboard uniquement
  const dashboard = document.querySelector('[data-page="dashboard"]');
  if (!dashboard) return;
  dashboard.querySelectorAll('.kpi-card, .dash-alert-card').forEach((el, i) => {
    el.style.opacity = '0';
    el.style.animation = `fadeInUp .4s ease ${i * 60}ms forwards`;
  });
}

/* ── 6. Trend badge helper ────────────────────────────────── */
function renderTrend(current, previous) {
  if (!previous || previous === 0) return '';
  const delta = ((current - previous) / previous * 100).toFixed(1);
  const abs = Math.abs(delta);
  if (delta > 0.5)  return `<span class="kpi-trend-up">↗ +${abs}%</span>`;
  if (delta < -0.5) return `<span class="kpi-trend-down">↘ -${abs}%</span>`;
  return `<span class="kpi-trend-flat">→ 0%</span>`;
}

/* ── 7. Upgrade KPI cards avec sparklines ─────────────────── */
function upgradeKPICards(caParMois) {
  if (!caParMois || caParMois.length === 0) return;
  const container = document.getElementById('sparkline-ca');
  if (container) {
    buildSparkline('sparkline-ca', caParMois.slice(-8));
  }
}

/* ── 8. Tooltips personnalisés (data-tooltip) ─────────────── */
function initTooltips() {
  // Géré entièrement en CSS via ::after — rien à faire en JS
}

/* ── Exports globaux pour usage dans les templates ────────── */
window.buildSparkline = buildSparkline;
window.animateCounter = animateCounter;

/* ── INIT ─────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initRipple();
  initConnectivity();
  initPageAnimations();
  initTooltips();

  // Compteurs sur les KPI cards (data-count)
  document.querySelectorAll('[data-count]').forEach(el => {
    const v = parseFloat(el.dataset.count) || 0;
    const suffix = el.dataset.suffix || '';
    const dec = parseInt(el.dataset.decimals) || 0;
    animateCounter(el, v, suffix, dec);
  });

  // Sparkline CA (injectée depuis le template)
  if (window.__navisur_ca_mois) {
    upgradeKPICards(window.__navisur_ca_mois);
  }
});
