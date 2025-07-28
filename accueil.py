# accueil.py
# ──────────────────────────────────────────────────────────────────────────────
# Page d’accueil – entièrement responsive (mobiles & tablettes)
#  • Icônes et libellés ne se chevauchent plus
#  • Ajout d’un pied-de-page signature + adresse IP locale
#  • ***NOUVEAU :*** icône « Statistique » (accessible Admin & Médecin, désactivée pour Assistante)
#  • Tout le code d’origine est conservé, seules les parties pertinentes sont
#    ajustées, sans perte de lignes non modifiées
#  • ***NOUVEAU :*** Ajout des cartes Biologie, Radiologies, Pharmacie, Comptabilité
#  • MISE À JOUR : La carte Biologie accède désormais à sa page dédiée.
#  • MISE À JOUR : Les cartes Radiologies, Pharmacie et Comptabilité ont maintenant des liens actifs.
#  • MISE À JOUR : Réorganisation des icônes : Statistiques est maintenant avant Admin.
#  • MISE À JOUR : Ajout de couleurs distinctes pour chaque icône.
#  • MISE À JOUR : Les icônes de navigation sont affichées dynamiquement selon les permissions de l'utilisateur.
#  • MISE À JOUR : Ajout de l'affichage des messages flash.
#  • NOUVEAU : Ajout de l'icône pour le module 'Gestion des Patients'.
#  • NOUVEAU : Animations améliorées pour les icônes.
#  • NOUVEAU : Fonctionnalité de glisser-déposer (drag and drop) pour les icônes, compatible tactile.
# ──────────────────────────────────────────────────────────────────────────────

from flask import Blueprint, render_template_string, redirect, url_for, session, flash
from datetime import datetime
import theme
import utils
import login
import os
from pathlib import Path
from openpyxl import Workbook

# Assurez-vous d'importer vos blueprints pour Radiologie, Pharmacie et Comptabilité
# Si ces fichiers n'existent pas encore, vous devrez les créer et y définir vos routes.
# Exemple : from radiologie import radiologie_bp
#           from pharmacie import pharmacie_bp
#           from comptabilite import comptabilite_bp
# Sans ces imports, les fonctions url_for correspondantes provoqueront des erreurs.

accueil_bp = Blueprint('accueil', __name__)

# Définition du chemin du fichier factures.xlsx ici pour être utilisé par la fonction d'initialisation
# Ce chemin dépendra du répertoire de données dynamique de l'utilisateur, donc il sera ajusté
# une fois que utils.EXCEL_FOLDER aura été défini.
FACTURES_EXCEL_FILE_PATH: Path = None # Sera initialisé dynamiquement

def initialize_factures_excel_file_if_not_exists():
    """
    Initialise le fichier factures.xlsx avec les colonnes nécessaires
    si il n'existe pas déjà.
    Cette fonction utilise utils.EXCEL_FOLDER qui doit être configuré au préalable.
    """
    global FACTURES_EXCEL_FILE_PATH # Déclare l'utilisation de la variable globale

    if utils.EXCEL_FOLDER is None:
        print("ERROR: utils.EXCEL_FOLDER n'est pas défini. Impossible d'initialiser factures.xlsx.")
        return

    # S'assurer que FACTURES_EXCEL_FILE_PATH pointe vers le bon emplacement
    FACTURES_EXCEL_FILE_PATH = Path(utils.EXCEL_FOLDER) / "factures.xlsx"

    if not FACTURES_EXCEL_FILE_PATH.exists():
        print(f"DEBUG: Le fichier des factures {FACTURES_EXCEL_FILE_PATH.name} n'existe pas. Initialisation...")
        wb = Workbook()
        sheet = wb.active
        sheet.title = "Factures"
        # Définir les en-têtes de colonne. Adaptez-les précisément à ce que vous attendez.
        sheet.append([
            "Numero",
            "DateFacture",
            "ID_Patient",
            "Nom_Patient",
            "Prenom_Patient",
            "Medecin_Email",
            "Service",
            "Montant",
            "StatutPaiement",
            "DatePaiement"
            # Ajoutez toutes les autres colonnes que vos factures sont censées avoir
        ])
        try:
            wb.save(FACTURES_EXCEL_FILE_PATH)
            print(f"DEBUG: Fichier {FACTURES_EXCEL_FILE_PATH.name} initialisé avec les colonnes nécessaires.")
        except Exception as e:
            print(f"ERREUR: Impossible de sauvegarder le fichier {FACTURES_EXCEL_FILE_PATH.name} lors de l'initialisation: {e}")
    else:
        print(f"DEBUG: Le fichier des factures {FACTURES_EXCEL_FILE_PATH.name} existe déjà. Pas d'initialisation requise.")


acceuil_template = """
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
  <meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>{{ config.nom_clinique or config.cabinet or 'EasyMedicaLink' }}</title>

  <link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'>
  <link rel='stylesheet' href='https://cdn.datatables.net/1.13.1/css/dataTables.bootstrap5.min.css'>

  <link href='https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&family=Great+Vibes&display=swap' rel='stylesheet'>
  <link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'>

  <script src='https://cdn.tailwindcss.com'></script>
  <script src='https://cdn.jsdelivr.net/npm/sweetalert2@11'></script>

  <style>
    :root {
      {% for var, val in theme_vars.items() %}
      --{{ var }}: {{ val }};
      {% endfor %}
      --font-primary: 'Poppins', sans-serif;
      --font-secondary: 'Great Vibes', cursive;
      --gradient-main: linear-gradient(45deg, var(--primary-color) 0%, var(--secondary-color) 100%);
      --shadow-light: 0 5px 15px rgba(0, 0, 0, 0.1);
      --shadow-medium: 0 8px 25px rgba(0, 0, 0, 0.2);
      --border-radius-lg: 1rem;
      --border-radius-md: 0.75rem;
      --border-radius-sm: 0.5rem;
    }

    body {
      font-family: var(--font-primary);
      background: var(--bg-color);
      color: var(--text-color);
      padding-top: 56px;
      transition: background 0.3s ease, color 0.3s ease;
    }

    .navbar {
      background: var(--gradient-main) !important;
      box-shadow: var(--shadow-medium);
    }
    .navbar-brand {
      font-family: var(--font-secondary);
      font-size: 2.0rem !important; /* Adjusted font size for brand */
      color: white !important;
      display: flex;
      align-items: center;
      transition: transform 0.3s ease;
    }
    .navbar-brand:hover {
      transform: scale(1.05);
    }
    .navbar-toggler {
      border: none;
      outline: none;
    }
    .navbar-toggler i {
      color: white;
      font-size: 1.5rem;
    }

    .offcanvas-header {
      background: var(--gradient-main) !important;
      color: white;
    }
    .offcanvas-body {
      background: var(--card-bg) !important;
      color: var(--text-color) !important;
    }
    .offcanvas-title {
      font-weight: 600;
    }

    .card {
      border-radius: var(--border-radius-lg);
      box-shadow: var(--shadow-light);
      background: var(--card-bg) !important;
      color: var(--text-color) !important;
      border: none;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    /* Removed card:hover transform here to allow icon-card hover to be distinct */

    .card-header {
      background: var(--primary-color) !important;
      color: var(--button-text) !important;
      border-top-left-radius: var(--border-radius-lg);
      border-top-right-radius: var(--border-radius-lg);
      padding: 1.5rem;
      position: relative;
      overflow: hidden;
    }
    .card-header::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(255, 255, 255, 0.1);
      transform: skewY(-5deg);
      transform-origin: top left;
      z-index: 0;
    }
    .card-header h1, .card-header .header-item, .card-header p {
      position: relative;
      z-index: 1;
      font-size: 1.8rem !important;
      font-weight: 700;
    }
    .card-header i {
      font-size: 1.8rem !important;
      margin-right: 0.5rem;
    }
    .header-item {
      font-size: 1.2rem !important;
      font-weight: 400;
    }

    /* Floating Labels (for consistency, even if not used on this page) */
    .floating-label {
      position: relative;
      margin-bottom: 1rem;
    }
    .floating-label input,
    .floating-label select {
      padding: 1rem 0.75rem 0.5rem;
      height: auto;
      border-radius: var(--border-radius-sm);
      border: 1px solid var(--secondary-color);
      background-color: var(--card-bg);
      color: var(--text-color);
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .floating-label input:focus + label,
    .floating-label input:not(:placeholder-shown) + label,
    .floating-label select:focus + label,
    .floating-label select:not([value=""]) + label {
      top: 0.25rem;
      left: 0.75rem;
      font-size: 0.75rem;
      color: var(--primary-color);
      background-color: var(--card-bg);
      padding: 0 0.25rem;
      transform: translateX(-0.25rem);
    }
    .floating-label input:focus,
    .floating-label select:focus {
      border-color: var(--primary-color);
      box-shadow: 0 0 0 0.25rem rgba(var(--primary-color-rgb), 0.25);
      background-color: var(--card-bg);
      color: var(--text-color);
    }
    .floating-label input[type='date']:not([value=''])::-webkit-datetime-edit-text,
    .floating-label input[type='date']:not([value=''])::-webkit-datetime-edit-month-field,
    .floating-label input[type='date']:not([value=''])::-webkit-datetime-edit-day-field,
    .floating-label input[type='date']::-webkit-datetime-edit-year-field {
      color: var(--text-color);
    }
    .floating-label input[type='date']::-webkit-calendar-picker-indicator {
      filter: {% if session.theme == 'dark' %}invert(1){% else %}none{% endif %};
    }


    /* Buttons */
    .btn {
      border-radius: var(--border-radius-md);
      font-weight: 600;
      transition: all 0.3s ease;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0.75rem 1.25rem;
    }
    .btn i {
      margin-right: 0.5rem;
    }
    .btn-primary {
      background: var(--gradient-main);
      border: none;
      color: var(--button-text);
      box-shadow: var(--shadow-light);
    }
    .btn-primary:hover {
      box-shadow: var(--shadow-medium);
      background: var(--gradient-main);
      opacity: 0.9;
    }
    .btn-success {
      background-color: var(--success-color);
      border-color: var(--success-color);
      color: white;
    }
    .btn-success:hover {
      background-color: var(--success-color-dark);
      border-color: var(--success-color-dark);
      box-shadow: var(--shadow-medium);
    }
    .btn-warning {
      background-color: var(--warning-color);
      border-color: var(--warning-color);
      color: white;
    }
    .btn-warning:hover {
      background-color: var(--warning-color-dark);
      border-color: var(--warning-color-dark);
      box-shadow: var(--shadow-medium);
    }
    .btn-danger {
      background-color: var(--danger-color);
      border-color: var(--danger-color);
      color: white;
    }
    .btn-danger:hover {
      background-color: var(--danger-color-dark);
      border-color: var(--danger-color-dark);
      box-shadow: var(--shadow-medium);
    }
    .btn-info { /* WhatsApp button */
      background-color: #25D366;
      border-color: #25D366;
      color: white;
    }
    .btn-info:hover {
      background-color: #1DA851;
      border-color: #1DA851;
      box-shadow: var(--shadow-medium);
    }
    .btn-outline-secondary {
      border-color: var(--secondary-color);
      color: var(--text-color);
      background-color: transparent;
    }
    .btn-outline-secondary:hover {
      background-color: var(--secondary-color);
      color: white;
      box-shadow: var(--shadow-light);
    }
    .btn-secondary {
      background-color: var(--secondary-color);
      border-color: var(--secondary-color);
      color: var(--button-text);
    }
    .btn-secondary:hover {
      background-color: var(--secondary-color-dark);
      border-color: var(--secondary-color-dark);
      box-shadow: var(--shadow-medium);
    }
    .btn-sm {
      padding: 0.5rem 0.8rem;
      font-size: 0.875rem;
    }

    /* Icon Cards */
    .icon-card {
      flex: 1 1 170px; /* Adjusted flex-basis for better responsiveness */
      max-width: 180px;
      color: var(--primary-color); /* This will be overridden by specific Tailwind classes on icons */
      padding: 0.5rem;
      text-decoration: none; /* Ensure links don't have underlines */
      transition: transform 0.3s ease-out, box-shadow 0.3s ease-out, background-color 0.3s ease-out; /* Plus belle animation */
      cursor: grab; /* Indique que l'élément est déplaçable */
      position: relative; /* Nécessaire pour le positionnement absolu du clone */
    }
    .icon-card:hover {
      transform: translateY(-8px) scale(1.05); /* Effet de levage et léger agrandissement */
      box-shadow: var(--shadow-medium);
      background-color: rgba(var(--primary-color-rgb), 0.05); /* Léger fond coloré au survol */
    }
    .icon-card i {
      font-size: 40px !important;
      margin-bottom: 0.5rem; /* Added margin for spacing */
      /* No color set here, colors will be applied via Tailwind classes */
    }
    .icon-card span {
      font-size: 1.1rem !important; /* Adjusted font size for better readability */
      font-weight: 600; /* Make text bolder */
      color: var(--text-color); /* Ensure text color is consistent */
    }
    .icon-card .border {
      border-radius: var(--border-radius-lg); /* Match card border-radius */
      border: 1px solid var(--border-color) !important; /* Use theme border color */
      background-color: var(--card-bg); /* Ensure background is card-bg */
      box-shadow: var(--shadow-light); /* Add shadow to inner div */
      transition: all 0.3s ease-out; /* Animation pour la bordure intérieure */
    }
    .icon-card:hover .border {
      border-color: var(--primary-color) !important; /* Highlight border on hover */
    }
    .icon-card.disabled {
      opacity: 0.5;
      pointer-events: none;
    }
    .icon-card.dragging { /* Style pour l'élément en cours de glissement */
      opacity: 0.7;
      border: 2px dashed var(--primary-color);
      transform: scale(0.95); /* Légère réduction pendant le glisser */
      box-shadow: var(--shadow-medium);
    }
    /* Styles pour le clone de l'icône pendant le glisser-déposer tactile */
    .icon-card-clone {
        position: absolute;
        pointer-events: none;
        z-index: 1000;
        opacity: 0.8;
        box-shadow: var(--shadow-medium);
        border-radius: var(--border-radius-lg);
        background-color: var(--card-bg);
        transition: none; /* Pas de transition sur le clone pour un mouvement fluide */
    }


    .header-item {
      font-size: 1.2rem !important; /* Adjusted to match rdv_template */
      font-weight: 400;
    }
    .header-item h1 {
      font-size: 1.8rem !important; /* Adjusted to match rdv_template */
      font-weight: 700;
    }
    .header-item i {
      font-size: 1.8rem !important;
      margin-right: 0.5rem;
    }

    /* Flash messages */
    .alert {
      border-radius: var(--border-radius-md);
      font-weight: 600;
      position: fixed;
      top: 70px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 1060;
      width: 90%;
      max-width: 500px;
      box-shadow: var(--shadow-medium);
      animation: fadeInOut 5s forwards;
    }

    @keyframes fadeInOut {
      0% { opacity: 0; transform: translateX(-50%) translateY(-20px); }
      10% { opacity: 1; transform: translateX(-50%) translateY(0); }
      90% { opacity: 1; transform: translateX(-50%) translateY(0); }
      100% { opacity: 0; transform: translateX(-50%) translateY(-20px); }
    }

    /* Footer */
    footer {
      background: var(--gradient-main);
      color: white;
      font-weight: 300;
      box-shadow: 0 -5px 15px rgba(0, 0, 0, 0.1);
    }
    footer a {
      color: white;
      text-decoration: none;
      transition: color 0.2s ease;
    }
    footer a:hover {
      color: var(--text-color-light);
    }

    /* Responsive adjustments */
    @media (max-width: 768px) {
      .card-header h1 {
        font-size: 1.5rem !important;
      }
      .card-header .header-item {
        font-size: 1rem !important;
      }
      .card-header i {
        font-size: 1.5rem !important;
      }
      .icon-card {
        flex: 1 1 140px;
        max-width: 160px;
      }
      .icon-card i {
        font-size: 32px !important;
      }
      .icon-card span {
        font-size: 20px !important;
      }
      .btn {
        width: 100%;
        margin-bottom: 0.5rem;
      }
      .d-flex.gap-2 {
        flex-direction: column;
      }
    }
  </style>
</head>
<body>

  <nav class="navbar navbar-dark fixed-top">
    <div class="container-fluid d-flex align-items-center">
      <button class="navbar-toggler" type="button"
              data-bs-toggle="offcanvas" data-bs-target="#settingsOffcanvas">
        <i class="fas fa-bars"></i>
      </button>
      <a class="navbar-brand ms-auto d-flex align-items-center" href="{{ url_for('accueil.accueil') }}">
        <i class="fas fa-heartbeat me-2"></i>EasyMedicaLink
      </a>
    </div>
  </nav>

  <div class="offcanvas offcanvas-start" tabindex="-1" id="settingsOffcanvas">
    <div class="offcanvas-header text-white">
      <h5 class="offcanvas-title"><i class="fas fa-cog me-2"></i>Paramètres</h5>
      <button type="button" class="btn-close btn-close-white" data-bs-dismiss="offcanvas"></button>
    </div>
    <div class="offcanvas-body">
      <div class="d-flex gap-2 mb-4">
        <a href="{{ url_for('login.logout') }}" class="btn btn-outline-secondary flex-fill">
          <i class="fas fa-sign-out-alt me-2" style="color: #DC143C;"></i>Déconnexion
        </a>
      </div>
    </div>
  </div>

  {# BLOC DE MESSAGES FLASH AJOUTÉ ICI #}
  {% with m=get_flashed_messages(with_categories=true) %}
    {% for c,msg in m %}
    <div class='alert alert-{{c}} small animate__animated animate__fadeIn'>{{msg}}</div>
    {% endfor %}
  {% endwith %}

  <div class="container-fluid my-4">
    <div class="row justify-content-center">
      <div class="col-12">
        <div class="card shadow-lg">
          <div class="card-header py-3 text-center">
            <h1 class="mb-2 header-item"><i class="fas fa-hospital me-2"></i>{{ config.nom_clinique or config.cabinet or 'NOM CLINIQUE/CABINET/CENTRE MEDICAL' }}</h1>
            <div class="d-flex justify-content-center gap-4 flex-wrap">
              <div class="d-flex align-items-center header-item"><i class="fas fa-user me-2"></i><span>{{ logged_in_doctor_name if logged_in_doctor_name and logged_in_doctor_name != 'None' else config.doctor_name or 'NOM MEDECIN' }}</span></div>
              <div class="d-flex align-items-center header-item"><i class="fas fa-map-marker-alt me-2"></i><span>{{ config.location or 'LIEU' }}</span></div>
            </div>
            <p class="mt-2 header-item"><i class="fas fa-calendar-day me-2"></i>{{ current_date }}</p>
          </div>

          <div class="card-body d-flex flex-wrap gap-3 justify-content-center" id="icon-container">
            {# Chaque 'icon-card' doit avoir un attribut 'data-id' unique pour l'identification #}
            {# L'attribut 'draggable="true"' est ajouté pour permettre le glisser-déposer #}

            {% if 'rdv' in allowed_pages %}
            <a href="{{ url_for('rdv.rdv_home') }}" class="icon-card text-center" draggable="true" data-id="rdv">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-calendar-check mb-2 text-blue-500"></i><span>RDV</span>
              </div>
            </a>
            {% endif %}

            {% if 'routes' in allowed_pages %}
            <a href="{{ url_for('index') }}" class="icon-card text-center" draggable="true" data-id="consultations">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-stethoscope mb-2 text-purple-500"></i><span>Consultations</span>
              </div>
            </a>
            {% endif %}

            {% if 'facturation' in allowed_pages %}
            <a href="{{ url_for('facturation.home_facturation') }}" class="icon-card text-center" draggable="true" data-id="factures">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-file-invoice-dollar mb-2 text-green-500"></i><span>Factures</span>
              </div>
            </a>
            {% endif %}

            {% if 'biologie' in allowed_pages %}
            <a class="icon-card text-center" href="{{ url_for('biologie.home_biologie') }}" draggable="true" data-id="biologie">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-flask mb-2 text-indigo-500"></i><span>Biologie</span>
              </div>
            </a>
            {% endif %}

            {% if 'radiologie' in allowed_pages %}
            <a class="icon-card text-center" href="{{ url_for('radiologie.home_radiologie') }}" draggable="true" data-id="radiologies">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-x-ray mb-2 text-red-500"></i><span>Radiologies</span>
              </div>
            </a>
            {% endif %}

            {% if 'pharmacie' in allowed_pages %}
            <a class="icon-card text-center" href="{{ url_for('pharmacie.home_pharmacie') }}" draggable="true" data-id="phc-stock">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-prescription-bottle-alt mb-2 text-yellow-500"></i><span>PHC & Stock</span>
              </div>
            </a>
            {% endif %}

            {% if 'comptabilite' in allowed_pages %}
            <a class="icon-card text-center" href="{{ url_for('comptabilite.home_comptabilite') }}" draggable="true" data-id="comptabilite">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-calculator mb-2 text-teal-500"></i><span>Comptabilité</span>
              </div>
            </a>
            {% endif %}
            
            {# NOUVELLE CARTE POUR LA GESTION DES PATIENTS #}
            {% if 'gestion_patient' in allowed_pages %}
            <a class="icon-card text-center" href="{{ url_for('gestion_patient.home_gestion_patient') }}" draggable="true" data-id="patients">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-users mb-2 text-blue-600"></i><span>Patients</span>
              </div>
            </a>
            {% endif %}

            {% if 'statistique' in allowed_pages %}
              <a href="{{ url_for('statistique.stats_home') }}" class="icon-card text-center" draggable="true" data-id="statistiques">
                <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                  <i class="fas fa-chart-pie mb-2 text-orange-500"></i><span>Statistiques</span>
                </div>
              </a>
            {% endif %}

            {% if 'administrateur_bp' in allowed_pages %}
            <a href="{{ url_for('administrateur_bp.dashboard') }}" class="icon-card text-center" draggable="true" data-id="admin">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-user-shield mb-2 text-pink-500"></i><span>Admin</span>
              </div>
            </a>
            {% endif %}

            {# NOUVELLE CARTE POUR LE GUIDE INTERACTIF (remplace l'ancien bouton) #}
            {% if 'guide' in allowed_pages %}
            <a href="{{ url_for('guide.guide_home') }}" class="icon-card text-center" draggable="true" data-id="guide">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-book mb-2 text-info"></i><span>Guide</span> {# Utilisez une couleur de votre choix #}
              </div>
            </a>
            {% endif %}
          </div> {# FIN du card-body #}
        </div> {# FIN de la carte principale (.card) #}
      </div>
    </div>
  </div>

  <footer class="text-center py-1 small">
    <div class="card-footer text-center py-1">
      <div style="margin-bottom: 0 !important;">
        <p class="small mb-1" style="color: white;">
          <i class="fas fa-heartbeat me-1"></i>
          SASTOUKA DIGITAL © 2025 • sastoukadigital@gmail.com tel +212652084735
        </p>
        <p class="small mb-0" style="color: white;">
          Ouvrir l’application en réseau {{ host_address }}
        </p>
      </div>
  </footer>

  <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
  <script src='https://cdn.jsdelivr.net/npm/sweetalert2@11'></script>
<script>
    // --- Fonctionnalité de glisser-déposer pour les icônes (souris et tactile) ---
    const iconContainer = document.getElementById('icon-container');
    let draggedItem = null;
    let clone = null; // Pour le clone de l'élément glissé (tactile)
    let touchStartX = 0;
    let touchStartY = 0;
    let currentX = 0;
    let currentY = 0;
    let isDragging = false; // Drapeau pour suivre si un glisser-déposer a eu lieu
    const DRAG_THRESHOLD = 5; // Seuil de pixels pour considérer un mouvement comme un glisser
    let longPressTimeout = null; // Variable pour stocker l'ID du timeout de l'appui long

    // Charger l'ordre des icônes depuis le stockage local
    function loadIconOrder() {
        const savedOrder = localStorage.getItem('iconOrder');
        if (savedOrder) {
            const orderArray = JSON.parse(savedOrder);
            const currentIcons = Array.from(iconContainer.children);
            const orderedIcons = [];

            // Réorganiser les icônes en fonction de l'ordre sauvegardé
            orderArray.forEach(id => {
                const icon = currentIcons.find(item => item.dataset.id === id);
                if (icon) {
                    orderedIcons.push(icon);
                }
            });

            // Ajouter les icônes qui n'étaient pas dans l'ordre sauvegardé (nouvelles icônes)
            currentIcons.forEach(icon => {
                if (!orderedIcons.includes(icon)) {
                    iconContainer.appendChild(icon); // Ajoute les nouvelles icônes à la fin
                }
            });

            // Vider le conteneur et ajouter les icônes dans le nouvel ordre
            // Ceci est plus efficace pour réorganiser que d'insérer un par un si la liste est longue
            const fragment = document.createDocumentFragment();
            orderedIcons.forEach(icon => fragment.appendChild(icon));
            iconContainer.innerHTML = ''; // Vide le conteneur
            iconContainer.appendChild(fragment); // Ajoute tous les éléments en une seule fois
        }
    }

    // Sauvegarder l'ordre actuel des icônes dans le stockage local
    function saveIconOrder() {
        const currentOrder = Array.from(iconContainer.children).map(item => item.dataset.id);
        localStorage.setItem('iconOrder', JSON.stringify(currentOrder));
    }

    // --- Gestion du glisser-déposer (Souris) ---
    iconContainer.addEventListener('dragstart', (e) => {
        if (e.target.classList.contains('icon-card')) {
            draggedItem = e.target;
            e.target.classList.add('dragging');
            e.dataTransfer.setData('text/plain', e.target.dataset.id);
            e.dataTransfer.effectAllowed = 'move';
            isDragging = true; // Définit le drapeau pour le glisser de la souris
        }
    });

    iconContainer.addEventListener('dragover', (e) => {
        e.preventDefault(); // Nécessaire pour permettre le dépôt
        const target = e.target.closest('.icon-card');
        if (target && target !== draggedItem) {
            const boundingBox = target.getBoundingClientRect();
            const offset = e.clientY - boundingBox.top;
            const center = boundingBox.height / 2;

            // Détermine si on insère avant ou après l'élément cible
            if (offset < center) {
                iconContainer.insertBefore(draggedItem, target);
            } else {
                iconContainer.insertBefore(draggedItem, target.nextSibling);
            }
        }
    });

    iconContainer.addEventListener('dragend', (e) => {
        if (e.target.classList.contains('icon-card')) {
            e.target.classList.remove('dragging');
            draggedItem = null;
            saveIconOrder(); // Sauvegarder le nouvel ordre
            isDragging = false; // Réinitialise le drapeau pour le glisser de la souris
        }
    });

    // --- Gestion du glisser-déposer (Tactile) ---
    // L'option { passive: false } est cruciale pour permettre l'appel de e.preventDefault()
    // dans touchmove, ce qui empêche le défilement par défaut de la page lors du glisser.
    iconContainer.addEventListener('touchstart', (e) => {
        const target = e.target.closest('.icon-card');
        if (target) {
            draggedItem = target;
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            isDragging = false; // Réinitialiser le drapeau au début de chaque toucher

            // Démarrer un timeout pour l'appui long (1 seconde)
            longPressTimeout = setTimeout(() => {
                isDragging = true; // C'est un appui long, on active le mode glisser
                draggedItem.classList.add('dragging');

                // Créer un clone de l'élément pour le glisser visuellement
                clone = draggedItem.cloneNode(true);
                clone.classList.add('icon-card-clone');
                clone.style.width = draggedItem.offsetWidth + 'px';
                clone.style.height = draggedItem.offsetHeight + 'px';
                document.body.appendChild(clone);

                const rect = draggedItem.getBoundingClientRect();
                // Ajuster touchStartX/Y pour le décalage du clone par rapport au doigt
                touchStartX = e.touches[0].clientX - rect.left;
                touchStartY = e.touches[0].clientY - rect.top;
            }, 1000); // 1000 ms = 1 seconde
        }
    }, { passive: false }); 

    iconContainer.addEventListener('touchmove', (e) => {
        if (draggedItem) {
            const deltaX = Math.abs(e.touches[0].clientX - touchStartX);
            const deltaY = Math.abs(e.touches[0].clientY - touchStartY);

            // Si le mouvement dépasse le seuil ET que le drag n'a pas encore commencé (pas d'appui long confirmé)
            if ((deltaX > DRAG_THRESHOLD || deltaY > DRAG_THRESHOLD) && !isDragging) {
                // Annuler l'appui long si l'utilisateur commence à faire défiler
                if (longPressTimeout) {
                    clearTimeout(longPressTimeout);
                    longPressTimeout = null;
                }
                // Ne pas appeler e.preventDefault() ici pour permettre le défilement normal
                return; 
            }

            // Si le drag a été activé (par appui long ou par souris)
            if (isDragging) { 
                e.preventDefault(); // Empêche le défilement de la page et le zoom

                currentX = e.touches[0].clientX;
                currentY = e.touches[0].clientY;

                if (clone) {
                    clone.style.left = (currentX - touchStartX) + 'px';
                    clone.style.top = (currentY - touchStartY) + 'px';
                }

                // Déterminer l'élément sous le doigt pour l'insertion
                const targetElement = document.elementFromPoint(currentX, currentY);
                const targetCard = targetElement ? targetElement.closest('.icon-card') : null;

                if (targetCard && targetCard !== draggedItem) {
                    const boundingBox = targetCard.getBoundingClientRect();
                    const offset = currentY - boundingBox.top;
                    const center = boundingBox.height / 2;

                    // Détermine si on insère avant ou après l'élément cible
                    if (offset < center) {
                        iconContainer.insertBefore(draggedItem, targetCard);
                    } else {
                        iconContainer.insertBefore(draggedItem, targetCard.nextSibling);
                    }
                }
            }
        }
    }, { passive: false }); // L'option { passive: false } est cruciale ici aussi

    iconContainer.addEventListener('touchend', (e) => {
        if (draggedItem) {
            // Si un appui long était en attente, l'annuler
            if (longPressTimeout) {
                clearTimeout(longPressTimeout);
                longPressTimeout = null;
            }

            if (isDragging) { // Si un drag a eu lieu
                draggedItem.classList.remove('dragging');
                if (clone) {
                    clone.remove(); // Supprimer le clone
                    clone = null;
                }
                saveIconOrder(); // Sauvegarder le nouvel ordre
                // IMPORTANT: preventDefault sur touchend pour éviter le "click" après un drag.
                // Ne l'appeler que si un drag a réellement eu lieu pour ne pas bloquer les clics normaux.
                e.preventDefault();
            }
            draggedItem = null;
            isDragging = false; // Réinitialiser le drapeau
        }
    });

    // Charger l'ordre des icônes au chargement de la page
    document.addEventListener('DOMContentLoaded', loadIconOrder);
</script>
</body>
</html>
"""

@accueil_bp.route('/accueil')
def accueil():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    current_user_data = login.load_users().get(session.get('email'))

    if not current_user_data:
        session.clear()
        flash("Votre session a expiré ou votre compte n'existe plus. Veuillez vous reconnecter.", "danger")
        return redirect(url_for('login.login'))

    admin_email_from_session = session.get('admin_email', 'default_admin@example.com')
    utils.set_dynamic_base_dir(admin_email_from_session)

    # Assurez-vous que FACTURES_EXCEL_FILE_PATH est correctement initialisé ici
    # après que utils.EXCEL_FOLDER ait été défini par utils.set_dynamic_base_dir.
    initialize_factures_excel_file_if_not_exists()

    if current_user_data.get('role') == 'admin':
        allowed_pages = login.ALL_BLUEPRINTS
    else:
        allowed_pages = current_user_data.get('allowed_pages', [])
        if 'accueil' not in allowed_pages:
            allowed_pages.append('accueil')
        # S'assurer que 'guide' est inclus si l'utilisateur y a accès
        if 'guide' not in allowed_pages and 'guide' in login.ALL_BLUEPRINTS: # Vérifie si 'guide' existe dans ALL_BLUEPRINTS
             allowed_pages.append('guide')


    config = utils.load_config()
    session['theme'] = config.get('theme', theme.DEFAULT_THEME)
    current_date = datetime.now().strftime("%Y-%m-%d")
    host_address = f"http://{utils.LOCAL_IP}:3000"

    logged_in_full_name = None 
    user_email = session.get('email')
    
    if user_email:
        all_users_data = login.load_users()
        user_info = all_users_data.get(user_email)
        if user_info:
            logged_in_full_name = f"{user_info.get('prenom', '')} {user_info.get('nom', '')}".strip()
            if not logged_in_full_name:
                logged_in_full_name = None

    return render_template_string(
        acceuil_template,
        config=config,
        current_date=current_date,
        host_address=host_address,
        theme_vars=theme.current_theme(),
        theme_names=list(theme.THEMES.keys()),
        allowed_pages=allowed_pages, # Passer la liste des pages autorisées
        logged_in_doctor_name=logged_in_full_name
    )
