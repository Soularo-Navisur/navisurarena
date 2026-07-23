/**
 * bateau_photo.js — NAVISUR v9.9
 * Gestion de l'affichage de photos de référence des bateaux.
 * Offline-first : aucune erreur visible si pas de connexion.
 */

const BateauPhoto = {

  // Cache session (vide à chaque rechargement de page)
  cache: {},

  // Liste d'images disponibles pour "photo suivante"
  imagesCourantes: [],
  indexCourant: 0,
  containerId: null,

  // Emojis de fallback par type
  emojis: {
    'voilier': '⛵', 'catamaran': '⛵', 'trimaran': '⛵',
    'moteur': '🚤', 'semi-rigide': '🚤', 'vedette': '🚤',
    'jet ski': '🏄', 'scooter': '🏄',
    'peniche': '🚢', 'fluvial': '🚢',
    'yacht': '⛵',
  },

  getEmoji(type) {
    if (!type) return '⛵';
    const t = type.toLowerCase();
    for (const [k, v] of Object.entries(this.emojis)) {
      if (t.includes(k)) return v;
    }
    return '⛵';
  },

  // ── HTML des états ──────────────────────────────────────────────────

  htmlAttente(type) {
    const emoji = this.getEmoji(type);
    return `
      <div class="bateau-photo-placeholder">
        <span class="emoji">${emoji}</span>
        <p>Saisissez la marque<br>et le modèle pour<br>voir une photo</p>
      </div>`;
  },

  htmlChargement(marque, modele) {
    return `
      <div class="bateau-photo-placeholder">
        <div class="bateau-photo-spinner"></div>
        <p style="margin-top:8px"><strong>${marque}</strong><br>${modele}</p>
      </div>`;
  },

  htmlOffline() {
    return `
      <div class="bateau-photo-placeholder">
        <span class="emoji">📡</span>
        <p>Photo non disponible<br>hors connexion</p>
      </div>`;
  },

  htmlIntrouvable(type) {
    const emoji = this.getEmoji(type);
    return `
      <div class="bateau-photo-placeholder">
        <span class="emoji">${emoji}</span>
        <p>Aucune photo<br>trouvée</p>
      </div>`;
  },

  htmlPhoto(data, index, total, bateauId) {
    const autreBtn = total > 1
      ? `<button onclick="BateauPhoto.photoSuivante()" class="btn-photo-action">🔄 Autre photo (${index+1}/${total})</button>`
      : '';
    const uploadBtn = bateauId
      ? `<label class="btn-photo-action" style="cursor:pointer">
           📁 Ma photo
           <input type="file" accept="image/*" style="display:none" onchange="BateauPhoto.uploadPhoto(this, ${bateauId})">
         </label>`
      : '';
    return `
      <img src="${data.image_url}" class="bateau-photo-img" alt="${data.titre || ''}"
           onerror="this.parentElement.parentElement.innerHTML = BateauPhoto.htmlIntrouvable('')">
      <div class="bateau-photo-badge">
        📸 ${data.titre || ''}<br>
        <span style="opacity:.7">Source : ${data.source || 'Wikipédia'}</span>
      </div>
      ${autreBtn || uploadBtn ? `<div class="bateau-photo-actions">${autreBtn}${uploadBtn}</div>` : ''}`;
  },

  htmlSkeleton() {
    return `<div class="bateau-photo-skeleton"></div>`;
  },

  // ── Affichage dans un conteneur ─────────────────────────────────────

  setContenu(containerId, html) {
    const el = document.getElementById(containerId);
    if (el) el.innerHTML = html;
  },

  // ── Chargement principal ────────────────────────────────────────────

  async charger(marque, modele, type, containerId, bateauId) {
    this.containerId = containerId;

    if (!marque && !modele) {
      this.setContenu(containerId, this.htmlAttente(type));
      return;
    }

    const cle = `${marque}_${modele}`.toLowerCase().replace(/\s+/g,'_');

    // Cache hit
    if (this.cache[cle]) {
      const d = this.cache[cle];
      if (d.succes) {
        this.imagesCourantes = d.images || [d.image_url];
        this.indexCourant = 0;
        this.setContenu(containerId, this.htmlPhoto(d, 0, this.imagesCourantes.length, bateauId));
      } else {
        this.setContenu(containerId, this.htmlIntrouvable(type));
      }
      return;
    }

    // Offline check
    if (!navigator.onLine) {
      this.setContenu(containerId, this.htmlOffline());
      return;
    }

    // Afficher spinner
    this.setContenu(containerId, this.htmlChargement(marque, modele));

    try {
      const params = new URLSearchParams({ marque, modele, type: type || 'bateau' });
      const controller = new AbortController();
      const tid = setTimeout(() => controller.abort(), 6000);
      const resp = await fetch(`/api/bateau/photo?${params}`, { signal: controller.signal });
      clearTimeout(tid);
      const data = await resp.json();

      this.cache[cle] = data;

      if (data.succes) {
        this.imagesCourantes = data.images || [data.image_url];
        this.indexCourant = 0;
        this.setContenu(containerId, this.htmlPhoto(data, 0, this.imagesCourantes.length, bateauId));
      } else {
        this.setContenu(containerId, this.htmlIntrouvable(type));
      }
    } catch (e) {
      this.setContenu(containerId, this.htmlOffline());
    }
  },

  // ── Faire défiler les photos ────────────────────────────────────────

  photoSuivante() {
    if (this.imagesCourantes.length <= 1) return;
    this.indexCourant = (this.indexCourant + 1) % this.imagesCourantes.length;
    const url = this.imagesCourantes[this.indexCourant];
    // Récupérer le data courant depuis le cache
    const cle = Object.keys(this.cache).find(k => {
      const d = this.cache[k];
      return d.succes && (d.images || []).includes(url);
    });
    const data = cle ? { ...this.cache[cle], image_url: url } : { image_url: url, source: 'Wikimedia', titre: '' };
    this.setContenu(this.containerId, this.htmlPhoto(data, this.indexCourant, this.imagesCourantes.length, null));
  },

  // ── Upload photo manuelle ───────────────────────────────────────────

  async uploadPhoto(input, bateauId) {
    if (!input.files || !input.files[0]) return;
    const formData = new FormData();
    formData.append('photo', input.files[0]);
    try {
      const resp = await fetch(`/bateaux/${bateauId}/photo`, { method: 'POST', body: formData });
      const data = await resp.json();
      if (data.succes) {
        // Afficher immédiatement la photo uploadée
        const el = document.getElementById(this.containerId);
        if (el) {
          el.innerHTML = `
            <img src="${data.url}?t=${Date.now()}" class="bateau-photo-img" alt="Photo personnalisée">
            <div class="bateau-photo-badge">📁 Photo personnalisée</div>`;
        }
      }
    } catch (e) {
      // Silencieux si erreur
    }
  },

  // ── Init formulaire (avec debounce 1000ms) ──────────────────────────

  _debounceTimer: null,

  initFormulaire(bateauId) {
    const champs = ['marque', 'modele', 'type_bateau'];
    champs.forEach(nom => {
      const el = document.querySelector(`[name="${nom}"]`);
      if (!el) return;
      el.addEventListener('input', () => {
        clearTimeout(this._debounceTimer);
        this._debounceTimer = setTimeout(() => this._declencherFormulaire(bateauId), 1000);
      });
      el.addEventListener('change', () => this._declencherFormulaire(bateauId));
    });
    // Déclencher au chargement si marque+modele déjà remplis
    const m = document.querySelector('[name="marque"]')?.value;
    const mo = document.querySelector('[name="modele"]')?.value;
    if (m && mo) this._declencherFormulaire(bateauId);
  },

  _declencherFormulaire(bateauId) {
    const marque = document.querySelector('[name="marque"]')?.value?.trim() || '';
    const modele = document.querySelector('[name="modele"]')?.value?.trim() || '';
    const type   = document.querySelector('[name="type_bateau"]')?.value?.trim() || '';
    this.charger(marque, modele, type, 'photo-container-form', bateauId || null);
  },

  // ── Init fiche (lazy load) ──────────────────────────────────────────

  initFiche(marque, modele, type, bateauId) {
    const el = document.getElementById('photo-container-fiche');
    if (!el) return;
    // Skeleton pendant le chargement
    el.innerHTML = this.htmlSkeleton();
    // Vérifier si photo manuelle existe d'abord
    if (bateauId) {
      fetch(`/bateaux/${bateauId}/photo/voir`, { method: 'HEAD' })
        .then(r => {
          if (r.ok) {
            el.innerHTML = `
              <img src="/bateaux/${bateauId}/photo/voir" class="bateau-photo-img" alt="Photo du bateau"
                   onerror="BateauPhoto.charger('${marque}', '${modele}', '${type}', 'photo-container-fiche', ${bateauId})">
              <div class="bateau-photo-badge">📁 Photo personnalisée</div>
              <div class="bateau-photo-actions">
                <label class="btn-photo-action" style="cursor:pointer">
                  📁 Remplacer
                  <input type="file" accept="image/*" style="display:none" onchange="BateauPhoto.uploadPhoto(this, ${bateauId})">
                </label>
              </div>`;
            this.containerId = 'photo-container-fiche';
          } else {
            this.charger(marque, modele, type, 'photo-container-fiche', bateauId);
          }
        })
        .catch(() => this.charger(marque, modele, type, 'photo-container-fiche', bateauId));
    } else {
      this.charger(marque, modele, type, 'photo-container-fiche', null);
    }
  }
};
