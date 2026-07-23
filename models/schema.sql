-- NAVISUR v9.9 — Schéma complet

CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL, record_id INTEGER NOT NULL,
        action TEXT NOT NULL, champ_modifie TEXT,
        ancienne_valeur TEXT, nouvelle_valeur TEXT,
        date_action TEXT DEFAULT CURRENT_TIMESTAMP,
        auteur TEXT DEFAULT "utilisateur"
    );
CREATE TABLE IF NOT EXISTS avenants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contrat_id INTEGER NOT NULL,
        numero TEXT, date_avenant TEXT NOT NULL,
        type_avenant TEXT NOT NULL, description TEXT NOT NULL,
        ancienne_valeur TEXT DEFAULT "", nouvelle_valeur TEXT DEFAULT "",
        prime_nouvelle REAL, statut TEXT DEFAULT "en_cours",
        document_id INTEGER, notes TEXT DEFAULT "",
        date_creation TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (contrat_id) REFERENCES contrats(id)
    );
CREATE TABLE IF NOT EXISTS bateaux (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        nom_bateau TEXT,
        marque TEXT,
        modele TEXT,
        type_bateau TEXT,
        immatriculation TEXT,
        annee_fabrication INTEGER,
        longueur REAL,
        largeur REAL,
        valeur_assurance REAL DEFAULT 0,
        valeur_a_neuf REAL DEFAULT 0,
        pavillon TEXT DEFAULT 'Français',
        port_attache TEXT,
        zone_navigation TEXT,
        usage TEXT DEFAULT 'plaisance',
        moteur_marque TEXT,
        moteur_modele TEXT,
        moteur_puissance REAL,
        moteur_annee INTEGER,
        moteur_type TEXT DEFAULT 'hors_bord',
        moteur_carburant TEXT DEFAULT 'essence',
        moteur_serie TEXT,
        moteur2_marque TEXT,
        moteur2_puissance REAL,
        moteur2_serie TEXT,
        notes TEXT,
        date_creation TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
CREATE TABLE IF NOT EXISTS bordereaux_assureurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compagnie TEXT NOT NULL,
    date_bordereau TEXT DEFAULT CURRENT_DATE,
    montant_total_ttc REAL DEFAULT 0,
    total_frais_courtage REAL DEFAULT 0,
    montant_virement REAL DEFAULT 0,
    rib_courtier TEXT DEFAULT '',
    reference_virement TEXT DEFAULT '',
    statut TEXT DEFAULT 'brouillon',
    notes TEXT DEFAULT '',
    date_creation TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bordereaux_lignes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bordereau_id INTEGER NOT NULL,
    contrat_id INTEGER,
    client_nom TEXT,
    police_numero TEXT,
    prime_ttc REAL DEFAULT 0,
    frais_courtage REAL DEFAULT 0,
    net_a_reverser REAL DEFAULT 0,
    FOREIGN KEY (bordereau_id) REFERENCES bordereaux_assureurs(id),
    FOREIGN KEY (contrat_id) REFERENCES contrats(id)
);
CREATE TABLE IF NOT EXISTS calendrier_prelevements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quittance_id INTEGER NOT NULL,
        numero_echeance INTEGER NOT NULL,
        date_prelevement TEXT NOT NULL,
        montant REAL NOT NULL,
        statut TEXT DEFAULT 'prevu',
        date_confirmation TEXT,
        FOREIGN KEY (quittance_id) REFERENCES quittances_suivi(id)
    );
CREATE TABLE IF NOT EXISTS checklist_pieces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contrat_id INTEGER NOT NULL,
        libelle TEXT NOT NULL,
        obligatoire INTEGER DEFAULT 1,
        recu INTEGER DEFAULT 0,
        date_reception TEXT,
        notes TEXT,
        FOREIGN KEY (contrat_id) REFERENCES contrats(id)
    );
CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT DEFAULT 'particulier',
        nom TEXT NOT NULL,
        prenom TEXT,
        email TEXT,
        telephone TEXT,
        adresse TEXT,
        code_postal TEXT,
        ville TEXT,
        siren TEXT,
        statut TEXT DEFAULT 'prospect',
        date_creation TEXT DEFAULT CURRENT_DATE,
        notes TEXT
    , civilite TEXT DEFAULT "", telephone2 TEXT DEFAULT "", telephone_fixe TEXT DEFAULT "", pays_code TEXT DEFAULT "FR", pays_nom TEXT DEFAULT "France", email_statut TEXT DEFAULT "", telephone_formate TEXT DEFAULT "", telephone_pays TEXT DEFAULT "FR", forme_juridique TEXT DEFAULT "", code_naf TEXT DEFAULT "", nom_dirigeant TEXT DEFAULT "", date_naissance TEXT, commune_naissance TEXT, date_permis_mer TEXT, type_permis_mer TEXT);
CREATE TABLE IF NOT EXISTS commissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contrat_id INTEGER,
        compagnie TEXT,
        mois INTEGER,
        annee INTEGER,
        montant_brut REAL DEFAULT 0,
        taux REAL DEFAULT 0,
        montant_net REAL DEFAULT 0,
        statut TEXT DEFAULT 'attendu',
        date_paiement TEXT,
        notes TEXT,
        FOREIGN KEY (contrat_id) REFERENCES contrats(id)
    );
CREATE TABLE IF NOT EXISTS compagnie_contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compagnie_id INTEGER NOT NULL,
        nom TEXT NOT NULL, prenom TEXT, poste TEXT,
        email TEXT, telephone TEXT, telephone_direct TEXT, notes TEXT,
        FOREIGN KEY (compagnie_id) REFERENCES compagnies(id)
    );
CREATE TABLE IF NOT EXISTS compagnies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        code_courtier TEXT,
        taux_commission REAL DEFAULT 0,
        type_convention TEXT DEFAULT 'convention',
        adresse TEXT, code_postal TEXT, ville TEXT,
        site_web TEXT, email_general TEXT, telephone_general TEXT,
        produits TEXT, notes TEXT,
        date_creation TEXT DEFAULT CURRENT_DATE,
        actif INTEGER DEFAULT 1
    );
CREATE TABLE IF NOT EXISTS compta_commissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compagnie TEXT NOT NULL,
        contrat_id INTEGER,
        client_id INTEGER,
        type_commission TEXT DEFAULT 'apport',
        periode TEXT,
        date_prevue TEXT,
        montant_attendu REAL DEFAULT 0,
        date_encaissement TEXT,
        montant_percu REAL DEFAULT 0,
        ecart REAL DEFAULT 0,
        statut TEXT DEFAULT 'attendue',
        notes TEXT,
        date_creation TEXT DEFAULT CURRENT_DATE,
        recette_id INTEGER
    );
CREATE TABLE IF NOT EXISTS compta_depenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_ordre INTEGER,
        date_depense TEXT NOT NULL,
        fournisseur TEXT,
        categorie TEXT NOT NULL,
        montant REAL NOT NULL,
        mode_paiement TEXT DEFAULT 'virement',
        recurrence TEXT DEFAULT 'ponctuel',
        notes TEXT,
        annee INTEGER,
        mois INTEGER
    );
CREATE TABLE IF NOT EXISTS compta_factures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE NOT NULL,
        client_id INTEGER,
        date_emission TEXT,
        date_echeance TEXT,
        date_paiement TEXT,
        objet TEXT,
        montant_ht REAL DEFAULT 0,
        taux_tva REAL DEFAULT 0,
        montant_ttc REAL DEFAULT 0,
        statut TEXT DEFAULT 'brouillon',
        notes TEXT,
        annee INTEGER,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
CREATE TABLE IF NOT EXISTS compta_recettes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_ordre INTEGER UNIQUE,
        date_encaissement TEXT NOT NULL,
        reference TEXT,
        client_id INTEGER,
        compagnie TEXT,
        contrat_id INTEGER,
        nature_recette TEXT NOT NULL,
        montant REAL NOT NULL,
        mode_reglement TEXT DEFAULT 'virement',
        periode_couverte TEXT,
        notes TEXT,
        valide INTEGER DEFAULT 0,
        date_validation TEXT,
        annee INTEGER,
        mois INTEGER
    );
CREATE TABLE IF NOT EXISTS compta_urssaf (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type_periode TEXT DEFAULT 'trimestriel',
        periode_label TEXT NOT NULL,
        annee INTEGER NOT NULL,
        trimestre INTEGER,
        mois INTEGER,
        ca_periode REAL DEFAULT 0,
        cotisations_sociales REAL DEFAULT 0,
        versement_liberatoire REAL DEFAULT 0,
        total_a_payer REAL DEFAULT 0,
        date_limite TEXT,
        date_declaration TEXT,
        statut TEXT DEFAULT 'a_faire',
        notes TEXT
    );
CREATE TABLE IF NOT EXISTS contrats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        bateau_id INTEGER,
        numero TEXT,
        compagnie TEXT,
        type_assurance TEXT,
        objet TEXT,
        date_debut TEXT,
        date_fin TEXT,
        prime_annuelle REAL DEFAULT 0,
        periodicite TEXT DEFAULT 'annuelle',
        statut TEXT DEFAULT 'en_cours',
        franchise REAL DEFAULT 0,
        garanties TEXT,
        notes TEXT,
        date_creation TEXT DEFAULT CURRENT_DATE, tacite_reconduction INTEGER DEFAULT 1, devis_id INTEGER, annee_prime_validee INTEGER, prime_annee_en_cours REAL, date_derniere_maj_prime TEXT, date_transmission_cie TEXT, date_acceptation_cie TEXT, numero_police_cie TEXT DEFAULT "", date_emission_police TEXT, taux_commission REAL DEFAULT 15, statut_relance TEXT DEFAULT "a_relancer", mode_paiement TEXT DEFAULT "annuel", prochaine_echeance_prime TEXT, nb_fractions INTEGER DEFAULT 1, checklist_done INTEGER DEFAULT 0, risque_id INTEGER,
        FOREIGN KEY (client_id) REFERENCES clients(id),
        FOREIGN KEY (bateau_id) REFERENCES bateaux(id)
    );
CREATE TABLE IF NOT EXISTS dda_recueils (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        date_recueil TEXT DEFAULT CURRENT_DATE,
        conseiller TEXT,
        objectif_assurance TEXT,
        type_navigation TEXT,
        zone_navigation TEXT,
        experience_navigation TEXT,
        nb_personnes_bord TEXT,
        valeur_bateau TEXT,
        garanties_souhaitees TEXT,
        garanties_exclues TEXT,
        budget_annuel TEXT,
        situation_assurance TEXT,
        sinistres_anterieurs TEXT,
        besoins_specifiques TEXT,
        recommandation TEXT,
        accepte_signature INTEGER DEFAULT 0,
        statut TEXT DEFAULT 'brouillon',
        notes TEXT, contrat_id INTEGER, date_signature TEXT, version INTEGER DEFAULT 1,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
CREATE TABLE IF NOT EXISTS devis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        date_devis TEXT DEFAULT CURRENT_DATE,
        compagnie TEXT,
        type_assurance TEXT,
        prime_proposee REAL DEFAULT 0,
        franchise_proposee REAL DEFAULT 0,
        garanties TEXT,
        statut TEXT DEFAULT 'en_attente',
        date_reponse TEXT,
        notes TEXT, note_conseil TEXT DEFAULT "", raison_non_retenu TEXT DEFAULT "", date_envoi_client TEXT, moyen_envoi TEXT DEFAULT "email", validite_jours INTEGER DEFAULT 30, date_expiration TEXT, type_acceptation TEXT, date_accord_client TEXT,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        compagnie_id INTEGER,
        type_document TEXT NOT NULL,
        nom_original TEXT NOT NULL,
        nom_stockage TEXT NOT NULL,
        nom_fichier TEXT,
        taille INTEGER DEFAULT 0,
        description TEXT,
        notes TEXT,
        date_upload TEXT DEFAULT CURRENT_DATE, contrat_id INTEGER, sinistre_id INTEGER, categorie TEXT DEFAULT "autre",
        FOREIGN KEY (client_id) REFERENCES clients(id),
        FOREIGN KEY (compagnie_id) REFERENCES compagnies(id)
    );
CREATE TABLE IF NOT EXISTS email_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categorie TEXT,
        titre TEXT NOT NULL,
        sujet TEXT,
        corps TEXT NOT NULL,
        date_creation TEXT DEFAULT CURRENT_DATE
    );
CREATE TABLE IF NOT EXISTS factures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        contrat_id INTEGER,
        numero TEXT,
        objet TEXT,
        date_emission TEXT,
        date_echeance TEXT,
        montant_ht REAL DEFAULT 0,
        montant_taxes REAL DEFAULT 0,
        montant_frais_courtage REAL DEFAULT 0,
        montant_frais_compagnie REAL DEFAULT 0,
        montant_ttc REAL DEFAULT 0,
        statut TEXT DEFAULT 'brouillon',
        notes TEXT,
        iban TEXT,
        date_creation TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (client_id) REFERENCES clients(id),
        FOREIGN KEY (contrat_id) REFERENCES contrats(id)
    );
CREATE TABLE IF NOT EXISTS formations_dda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL,
        organisme TEXT DEFAULT '',
        date_formation TEXT NOT NULL,
        duree_heures REAL NOT NULL DEFAULT 0,
        type_formation TEXT DEFAULT 'continue',
        attestation_fichier TEXT,
        notes TEXT DEFAULT '',
        date_creation TEXT DEFAULT CURRENT_DATE
    );
CREATE TABLE IF NOT EXISTS journal_activites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        contrat_id INTEGER,
        date_activite TEXT NOT NULL,
        type_contact TEXT NOT NULL,
        sens TEXT DEFAULT 'sortant',
        objet TEXT NOT NULL,
        contenu TEXT,
        resultat TEXT,
        suite_a_donner TEXT,
        auteur TEXT,
        date_creation TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
CREATE TABLE IF NOT EXISTS lignes_quittance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        facture_id INTEGER NOT NULL,
        ordre INTEGER DEFAULT 0,
        type_ligne TEXT DEFAULT 'libre',
        description TEXT NOT NULL,
        montant_ht REAL DEFAULT 0,
        taux_taxe REAL DEFAULT 0,
        montant_taxe REAL DEFAULT 0,
        montant_ttc REAL DEFAULT 0,
        FOREIGN KEY (facture_id) REFERENCES factures(id)
    );
CREATE TABLE IF NOT EXISTS mandats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compagnie TEXT NOT NULL,
        type_mandat TEXT,
        numero_mandat TEXT,
        contact_nom TEXT,
        contact_email TEXT,
        contact_telephone TEXT,
        date_debut TEXT,
        date_fin TEXT,
        produits TEXT,
        statut TEXT DEFAULT 'actif',
        notes TEXT,
        date_creation TEXT DEFAULT CURRENT_DATE
    );
CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        titre TEXT NOT NULL,
        message TEXT,
        lien TEXT,
        lu INTEGER DEFAULT 0,
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP,
        priorite TEXT DEFAULT 'normale'
    );
CREATE TABLE IF NOT EXISTS numerotation_factures (
    annee INTEGER PRIMARY KEY,
    dernier_numero INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS parametres (
        cle TEXT PRIMARY KEY,
        valeur TEXT
    );
CREATE TABLE IF NOT EXISTS parametres_fiscaux (
        annee INTEGER PRIMARY KEY,
        plafond_micro_bnc REAL DEFAULT 77700,
        taux_urssaf REAL DEFAULT 22.0,
        note TEXT DEFAULT '',
        date_maj TEXT DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE IF NOT EXISTS primes_historique (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contrat_id INTEGER NOT NULL,
        annee INTEGER NOT NULL,
        prime_ht REAL DEFAULT 0,
        frais_compagnie REAL DEFAULT 0,
        taxes REAL DEFAULT 0,
        prime_ttc REAL NOT NULL,
        variation_pct REAL,
        note TEXT DEFAULT '',
        date_saisie TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(contrat_id, annee),
        FOREIGN KEY (contrat_id) REFERENCES contrats(id)
    );
CREATE TABLE IF NOT EXISTS primes_paiements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contrat_id INTEGER NOT NULL,
        fraction INTEGER DEFAULT 1,
        montant REAL DEFAULT 0,
        date_echeance TEXT,
        date_paiement TEXT,
        mode_paiement TEXT DEFAULT 'virement',
        statut TEXT DEFAULT 'attendu',
        reference TEXT,
        notes TEXT,
        FOREIGN KEY (contrat_id) REFERENCES contrats(id)
    );
CREATE TABLE IF NOT EXISTS quittances_suivi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contrat_id INTEGER NOT NULL,
        annee INTEGER NOT NULL,
        frequence TEXT NOT NULL DEFAULT 'annuel',
        mode_paiement TEXT NOT NULL DEFAULT 'prelevement',
        numero_quittance INTEGER NOT NULL DEFAULT 1,
        total_quittances INTEGER NOT NULL DEFAULT 1,
        montant_ttc REAL NOT NULL,
        date_emission TEXT,
        date_echeance TEXT NOT NULL,
        envoyee_client INTEGER DEFAULT 0,
        date_envoi_client TEXT,
        canal_envoi TEXT DEFAULT 'email',
        statut_paiement TEXT DEFAULT 'en_attente',
        date_paiement TEXT,
        relance_envoyee INTEGER DEFAULT 0,
        date_relance TEXT,
        note_relance TEXT DEFAULT '',
        taux_commission REAL DEFAULT 0,
        commission_attendue REAL DEFAULT 0,
        commission_recue REAL DEFAULT 0,
        date_reception_commission TEXT,
        bordereau_reference TEXT DEFAULT '',
        ecart_commission REAL DEFAULT 0,
        note TEXT DEFAULT '',
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP, prime_ht REAL DEFAULT 0, taux_taxe REAL DEFAULT 0, montant_taxe REAL DEFAULT 0, frais_courtage REAL DEFAULT 0, net_a_reverser REAL DEFAULT 0, rib_courtier TEXT DEFAULT '', numero_facture TEXT DEFAULT '', date_facture TEXT DEFAULT '', tva_collectee REAL DEFAULT 0, taux_tva REAL DEFAULT 20,
        FOREIGN KEY (contrat_id) REFERENCES contrats(id)
    );
CREATE TABLE IF NOT EXISTS reclamations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        contrat_id INTEGER,
        date_reception TEXT NOT NULL,
        canal TEXT DEFAULT 'email',
        objet TEXT NOT NULL,
        description TEXT DEFAULT '',
        statut TEXT DEFAULT 'recue',
        date_accuse TEXT,
        date_reponse_prevue TEXT,
        date_reponse_effective TEXT,
        reponse_apportee TEXT DEFAULT '',
        satisfait INTEGER DEFAULT 0,
        mediateur_saisi INTEGER DEFAULT 0,
        date_mediateur TEXT,
        notes TEXT DEFAULT '',
        date_creation TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
CREATE TABLE IF NOT EXISTS relances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contrat_id INTEGER NOT NULL,
        client_id INTEGER NOT NULL,
        type_relance TEXT,
        date_prevue TEXT,
        date_effectuee TEXT,
        moyen TEXT DEFAULT 'email',
        statut TEXT DEFAULT 'a_faire',
        message TEXT,
        reponse TEXT,
        date_creation TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (contrat_id) REFERENCES contrats(id),
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
CREATE TABLE IF NOT EXISTS rendez_vous (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL,
        client_id INTEGER,
        contrat_id INTEGER,
        date_rdv TEXT NOT NULL,
        heure_debut TEXT,
        heure_fin TEXT,
        lieu TEXT,
        type_rdv TEXT DEFAULT 'appel',
        statut TEXT DEFAULT 'prevu',
        notes TEXT,
        rappel_avant INTEGER DEFAULT 60,
        date_creation TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
CREATE TABLE IF NOT EXISTS resiliations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contrat_id INTEGER NOT NULL UNIQUE,
        client_id INTEGER NOT NULL,
        date_resiliation TEXT NOT NULL,
        date_effet TEXT,
        motif TEXT NOT NULL,
        motif_detail TEXT DEFAULT '',
        ristourne_montant REAL DEFAULT 0,
        ristourne_recue INTEGER DEFAULT 0,
        ristourne_date TEXT,
        commission_initiale REAL DEFAULT 0,
        commission_a_deduire REAL DEFAULT 0,
        commission_mode TEXT DEFAULT 'aucun',
        commission_regularisee INTEGER DEFAULT 0,
        commission_regularisation_date TEXT,
        frais_courtage_appliquer INTEGER DEFAULT 0,
        frais_courtage_montant REAL DEFAULT 0,
        frais_courtage_facture_id INTEGER,
        notes TEXT,
        date_creation TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (contrat_id) REFERENCES contrats(id),
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
CREATE TABLE IF NOT EXISTS rgpd_consentements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        type_traitement TEXT,
        consentement INTEGER DEFAULT 1,
        date_consentement TEXT,
        source TEXT,
        notes TEXT,
        date_creation TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
CREATE TABLE IF NOT EXISTS rgpd_demandes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        type_demande TEXT,
        date_demande TEXT DEFAULT CURRENT_DATE,
        statut TEXT DEFAULT 'en_cours',
        date_traitement TEXT,
        notes TEXT,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
CREATE TABLE IF NOT EXISTS risques (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        categorie TEXT NOT NULL DEFAULT 'Bateau',
        sous_categorie TEXT NOT NULL DEFAULT 'Bateau à moteur',
        libelle TEXT NOT NULL,
        valeur_assurance REAL DEFAULT 0,
        valeur_a_neuf REAL DEFAULT 0,
        adresse TEXT DEFAULT '',
        code_postal TEXT DEFAULT '',
        ville TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        details TEXT DEFAULT '{}',
        date_creation TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
CREATE TABLE IF NOT EXISTS sinistres (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        contrat_id INTEGER,
        bateau_id INTEGER,
        numero TEXT,
        date_declaration TEXT,
        date_sinistre TEXT,
        type_sinistre TEXT,
        lieu_sinistre TEXT,
        description TEXT,
        montant_estime REAL DEFAULT 0,
        montant_indemnise REAL DEFAULT 0,
        statut TEXT DEFAULT 'ouvert',
        notes TEXT,
        date_creation TEXT DEFAULT CURRENT_DATE, numero_sinistre_cie TEXT DEFAULT "", gestionnaire_cie TEXT DEFAULT "", telephone_gestionnaire TEXT DEFAULT "", date_declaration_cie TEXT, date_expertise TEXT, date_cloture TEXT, cause_refus TEXT DEFAULT "", recours_possible INTEGER DEFAULT 0, recours_date TEXT, recours_notes TEXT DEFAULT "",
        FOREIGN KEY (client_id) REFERENCES clients(id),
        FOREIGN KEY (contrat_id) REFERENCES contrats(id),
        FOREIGN KEY (bateau_id) REFERENCES bateaux(id)
    );
CREATE TABLE IF NOT EXISTS taches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL,
        description TEXT,
        client_id INTEGER,
        contrat_id INTEGER,
        date_echeance TEXT,
        priorite TEXT DEFAULT 'normale',
        statut TEXT DEFAULT 'a_faire',
        date_creation TEXT DEFAULT CURRENT_DATE,
        date_cloture TEXT,
        FOREIGN KEY (client_id) REFERENCES clients(id),
        FOREIGN KEY (contrat_id) REFERENCES contrats(id)
    );
CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_log(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_bordereau_compagnie ON bordereaux_assureurs(compagnie);
CREATE INDEX IF NOT EXISTS idx_bordereau_ligne_bordereau ON bordereaux_lignes(bordereau_id);
CREATE INDEX IF NOT EXISTS idx_bordereau_statut ON bordereaux_assureurs(statut);
CREATE INDEX IF NOT EXISTS idx_contrats_date_fin ON contrats(date_fin);
CREATE INDEX IF NOT EXISTS idx_contrats_statut ON contrats(statut);
CREATE INDEX IF NOT EXISTS idx_formations_date ON formations_dda(date_formation);
CREATE INDEX IF NOT EXISTS idx_primes_hist ON primes_historique(contrat_id, annee);
CREATE INDEX IF NOT EXISTS idx_quittances_contrat ON quittances_suivi(contrat_id);
CREATE INDEX IF NOT EXISTS idx_quittances_echeance ON quittances_suivi(date_echeance);
CREATE INDEX IF NOT EXISTS idx_quittances_statut ON quittances_suivi(statut_paiement);
CREATE INDEX IF NOT EXISTS idx_reclamations_client ON reclamations(client_id);
CREATE INDEX IF NOT EXISTS idx_reclamations_statut ON reclamations(statut);
CREATE INDEX IF NOT EXISTS idx_clients_nom ON clients(nom);
CREATE INDEX IF NOT EXISTS idx_contrats_client ON contrats(client_id);
CREATE INDEX IF NOT EXISTS idx_risques_client ON risques(client_id);
