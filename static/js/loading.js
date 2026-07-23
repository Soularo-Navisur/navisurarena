/**
 * loading.js — NAVISUR v9.9
 * Overlay de chargement universel + protection anti-doublon côté JS.
 * Pas de dépendance externe.
 */

const NavisurLoading = {

  show(titre, sousTitre) {
    const overlay = document.getElementById('loading-overlay');
    if (!overlay) return;
    document.getElementById('loading-title').textContent = titre || 'Traitement en cours...';
    document.getElementById('loading-sub').textContent   = sousTitre || 'Veuillez patienter';
    overlay.style.display = 'flex';
    // Désactiver scroll de la page
    document.body.style.overflow = 'hidden';
  },

  hide() {
    const overlay = document.getElementById('loading-overlay');
    if (!overlay) return;
    overlay.style.display = 'none';
    document.body.style.overflow = '';
  }
};

document.addEventListener('DOMContentLoaded', () => {

  // ── Protection anti-doublon universelle sur TOUS les formulaires ──
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', function(e) {
      if (this._navisurSubmitting) {
        e.preventDefault();
        return;
      }
      this._navisurSubmitting = true;

      const titre  = this.dataset.loadingTitle || 'Enregistrement en cours...';
      const sub    = this.dataset.loadingSub || 'Veuillez patienter, traitement de votre demande...';

      // Griser + spinner sur le bouton submit
      const btn = this.querySelector('[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.classList.add('btn-loading');
        // Sauvegarder le texte original
        btn._originalHtml = btn.innerHTML;
        btn.innerHTML = '<span class="btn-spinner"></span> ' + (btn._originalHtml || 'En cours...');
      }

      NavisurLoading.show(titre, sub);
    });
  });

  // ── Liens/boutons individuels avec data-loading-title ────────────
  document.querySelectorAll('a[data-loading-title], button[data-loading-title]').forEach(el => {
    // Ignorer les boutons de type submit (gérés par le form parent)
    if (el.type === 'submit') return;
    // Ignorer les boutons toggle/modal/accordion Bootstrap
    if (el.dataset.bsToggle) return;

    el.addEventListener('click', function(e) {
      if (this._navisurClicked) {
        e.preventDefault();
        return;
      }
      this._navisurClicked = true;
      this.classList.add('btn-loading');

      NavisurLoading.show(
        this.dataset.loadingTitle,
        this.dataset.loadingSub || 'Veuillez patienter...'
      );
    });
  });

  // ── Masquer si retour navigateur (bouton précédent pywebview) ─────
  window.addEventListener('pageshow', e => {
    if (e.persisted) NavisurLoading.hide();
  });

  // ── Sécurité : masquer après 30s max (timeout de garde) ──────────
  const overlay = document.getElementById('loading-overlay');
  if (overlay) {
    const obs = new MutationObserver(() => {
      if (overlay.style.display === 'flex') {
        clearTimeout(overlay._timeout);
        overlay._timeout = setTimeout(() => NavisurLoading.hide(), 30000);
      }
    });
    obs.observe(overlay, { attributes: true, attributeFilter: ['style'] });
  }

});
