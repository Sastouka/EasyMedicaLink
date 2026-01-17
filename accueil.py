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
#  • REORGANISATION : La carte 'Patient' est maintenant après 'RDV' et 'Assistant IA' est à la fin.
#  • MODERNISATION (Style Angular) : Animations d'entrée, UX du glisser-déposer améliorée avec un placeholder.
# ──────────────────────────────────────────────────────────────────────────────

from flask import Blueprint, render_template_string, redirect, url_for, session, flash
from datetime import datetime
import theme
import utils
import login
import os
from pathlib import Path
from openpyxl import Workbook
import json

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
      font-size: 1.8rem !important; /* Adjusted font size for a sleeker brand */
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

    .card-header {
      background: transparent;
      border-top-left-radius: var(--border-radius-lg);
      border-top-right-radius: var(--border-radius-lg);
      padding: 1.5rem;
      position: relative;
      overflow: hidden;
      background: var(--gradient-main);
    }

    .card-header h1, .card-header .header-item, .card-header p {
      position: relative;
      z-index: 1;
      font-size: 1.8rem !important;
      font-weight: 700;
      color: white; /* Ensure text is white on gradient */
      text-shadow: 1px 1px 3px rgba(0,0,0,0.2);
    }
    .card-header i {
      font-size: 1.8rem !important;
      margin-right: 0.5rem;
    }
    .header-item {
      font-size: 1.2rem !important;
      font-weight: 400;
    }

    /* Icon Cards */
    .icon-card {
      flex: 1 1 170px;
      max-width: 180px;
      padding: 0.5rem;
      text-decoration: none;
      transition: transform 0.3s ease-out, box-shadow 0.3s ease-out;
      cursor: grab;
      /* Animation d'entrée */
      opacity: 0;
      transform: translateY(20px);
      animation: fadeInUp 0.5s ease-out forwards;
    }
    @keyframes fadeInUp {
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .icon-card:hover {
      transform: translateY(-8px);
      box-shadow: var(--shadow-medium);
    }
    .icon-card i {
      font-size: 40px !important;
      margin-bottom: 0.5rem;
    }
    .icon-card span {
      font-size: 1.1rem !important;
      font-weight: 600;
      color: var(--text-color);
    }
    .icon-card .border {
      border-radius: var(--border-radius-lg);
      border: 1px solid var(--border-color) !important;
      background-color: var(--card-bg);
      box-shadow: var(--shadow-light);
      transition: all 0.3s ease-out;
    }
    .icon-card:hover .border {
      border-color: var(--primary-color) !important;
      background-color: rgba(var(--primary-color-rgb), 0.05);
    }
    .icon-card.disabled {
      opacity: 0.5;
      pointer-events: none;
    }
    .icon-card.dragging {
      opacity: 0.4;
      transform: scale(0.95);
    }
    /* Style pour le placeholder pendant le drag */
    .drop-placeholder {
        flex: 1 1 170px;
        max-width: 180px;
        background-color: rgba(var(--primary-color-rgb), 0.1);
        border: 2px dashed var(--primary-color);
        border-radius: var(--border-radius-lg);
        margin: 0.5rem;
        transition: all 0.2s ease;
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
      background: var(--bg-color); /* Match body background */
      color: var(--text-color);
      font-weight: 400;
      opacity: 0.7;
    }
    footer a {
      color: var(--primary-color);
      text-decoration: none;
      transition: color 0.2s ease;
    }
    footer a:hover {
      color: var(--secondary-color);
    }

    /* Responsive adjustments */
    @media (max-width: 768px) {
      .card-header h1 { font-size: 1.5rem !important; }
      .card-header .header-item { font-size: 1rem !important; }
      .card-header i { font-size: 1.5rem !important; }
      .icon-card { flex: 1 1 140px; max-width: 160px; }
      .icon-card i { font-size: 32px !important; }
      .icon-card span { font-size: 1rem !important; }
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
        <a href="{{ url_for('login.logout') }}" class="btn btn-outline-secondary w-100">
          <i class="fas fa-sign-out-alt me-2 text-danger"></i>Déconnexion
        </a>
    </div>
  </div>

  {% with m=get_flashed_messages(with_categories=true) %}
    {% for c,msg in m %}
    <div class='alert alert-{{c}}'>{{msg}}</div>
    {% endfor %}
  {% endwith %}

  <div class="container-fluid my-4">
    <div class="row justify-content-center">
      <div class="col-12">
        <div class="card shadow-lg">
          <div class="card-header py-3 text-center">
            <h1 class="mb-2 header-item"><i class="fas fa-hospital me-2"></i>{{ config.nom_clinique or config.cabinet or 'NOM CLINIQUE/CABINET' }}</h1>
            <div class="d-flex justify-content-center gap-4 flex-wrap">
              <div class="d-flex align-items-center header-item"><i class="fas fa-user me-2"></i><span>{{ logged_in_doctor_name if logged_in_doctor_name and logged_in_doctor_name != 'None' else config.doctor_name or 'NOM MEDECIN' }}</span></div>
              <div class="d-flex align-items-center header-item"><i class="fas fa-map-marker-alt me-2"></i><span>{{ config.location or 'LIEU' }}</span></div>
            </div>
            <p class="mt-2 header-item"><i class="fas fa-calendar-day me-2"></i>{{ current_date }}</p>
          </div>

          <div class="card-body d-flex flex-wrap gap-3 justify-content-center" id="icon-container">
            {# L'ordre des icônes a été ajusté selon la demande #}

            {% if 'rdv' in allowed_pages %}
            <a href="{{ url_for('rdv.rdv_home') }}" class="icon-card text-center" draggable="true" data-id="rdv">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-calendar-check mb-2 text-blue-500"></i><span>RDV</span>
              </div>
            </a>
            {% endif %}
            
            {# CARTE PATIENTS DÉPLACÉE ICI #}
            {% if 'gestion_patient' in allowed_pages %}
            <a class="icon-card text-center" href="{{ url_for('gestion_patient.home_gestion_patient') }}" draggable="true" data-id="patients">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-users mb-2 text-blue-600"></i><span>Patients</span>
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

            {% if 'guide' in allowed_pages %}
            <a href="{{ url_for('guide.guide_home') }}" class="icon-card text-center" draggable="true" data-id="guide">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-book mb-2 text-cyan-500"></i><span>Guide</span>
              </div>
            </a>
            {% endif %}

            {# CARTE ASSISTANT IA DÉPLACÉE À LA FIN #}
            {% if 'ia_assitant' in allowed_pages %}
            <a class="icon-card text-center" href="{{ url_for('ia_assitant.home_ia_assitant') }}" draggable="true" data-id="ia-assitant">
              <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                <i class="fas fa-robot mb-2 text-purple-600"></i><span>Assistant IA</span>
              </div>
            </a>
            {% endif %}

          </div>
        </div>
      </div>
    </div>
  </div>

  <footer class="text-center py-2 small">
    <p class="mb-1">
      <i class="fas fa-heartbeat me-1 text-primary"></i>
      SASTOUKA DIGITAL © 2025 • <a href="mailto:sastoukadigital@gmail.com">sastoukadigital@gmail.com</a> • +212652084735
    </p>
    <p class="mb-0">
      Accès réseau : <a href="{{ host_address }}">{{ host_address }}</a>
    </p>
  </footer>

  <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
  <script src='https://cdn.jsdelivr.net/npm/sweetalert2@11'></script>
<script>
document.addEventListener('DOMContentLoaded', () => {
    // --- Fonctionnalité de glisser-déposer améliorée ---
    const iconContainer = document.getElementById('icon-container');
    let draggedItem = null;
    let placeholder = null;

    // Appliquer une animation d'entrée décalée
    const icons = document.querySelectorAll('.icon-card');
    icons.forEach((icon, index) => {
        icon.style.animationDelay = `${index * 0.05}s`;
    });

    function createPlaceholder() {
        const p = document.createElement('div');
        p.className = 'drop-placeholder';
        return p;
    }

    function saveIconOrder() {
        const currentOrder = Array.from(iconContainer.children)
            .filter(el => el.classList.contains('icon-card'))
            .map(item => item.dataset.id);
        localStorage.setItem('iconOrder', JSON.stringify(currentOrder));
    }

    function loadIconOrder() {
        const savedOrder = localStorage.getItem('iconOrder');
        if (!savedOrder) return;

        const orderArray = JSON.parse(savedOrder);
        const fragment = document.createDocumentFragment();
        const currentIcons = new Map(
            Array.from(iconContainer.children).map(icon => [icon.dataset.id, icon])
        );
        
        orderArray.forEach(id => {
            if (currentIcons.has(id)) {
                fragment.appendChild(currentIcons.get(id));
                currentIcons.delete(id);
            }
        });
        
        // Ajouter les nouvelles icônes (non présentes dans l'ordre sauvegardé) à la fin
        currentIcons.forEach(icon => fragment.appendChild(icon));
        
        iconContainer.innerHTML = '';
        iconContainer.appendChild(fragment);
    }

    function getDragAfterElement(container, y) {
        const draggableElements = [...container.querySelectorAll('.icon-card:not(.dragging)')];
        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            if (offset < 0 && offset > closest.offset) {
                return { offset: offset, element: child };
            } else {
                return closest;
            }
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }
    
    // --- Événements Souris ---
    iconContainer.addEventListener('dragstart', e => {
        if (e.target.classList.contains('icon-card')) {
            draggedItem = e.target;
            setTimeout(() => {
                draggedItem.classList.add('dragging');
            }, 0);
            placeholder = createPlaceholder();
            e.dataTransfer.effectAllowed = 'move';
        }
    });

    iconContainer.addEventListener('dragover', e => {
        e.preventDefault();
        if (!draggedItem) return;

        const afterElement = getDragAfterElement(iconContainer, e.clientY);
        if (afterElement == null) {
            iconContainer.appendChild(placeholder);
        } else {
            iconContainer.insertBefore(placeholder, afterElement);
        }
    });

    iconContainer.addEventListener('dragend', e => {
        if (draggedItem) {
            draggedItem.classList.remove('dragging');
            if (placeholder && placeholder.parentNode) {
                placeholder.parentNode.replaceChild(draggedItem, placeholder);
            }
            placeholder = null;
            draggedItem = null;
            saveIconOrder();
        }
    });
    
    // Charger l'ordre initial
    loadIconOrder();
});
</script>
{% include '_floating_assistant.html' %} 
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
    
    initialize_factures_excel_file_if_not_exists()

    if current_user_data.get('role') == 'admin':
        allowed_pages = login.ALL_BLUEPRINTS
    else:
        allowed_pages = current_user_data.get('allowed_pages', [])
        if 'accueil' not in allowed_pages:
            allowed_pages.append('accueil')
        if 'guide' not in allowed_pages and 'guide' in login.ALL_BLUEPRINTS:
             allowed_pages.append('guide')


    config = utils.load_config()
    session['theme'] = config.get('theme', theme.DEFAULT_THEME)
    current_date = datetime.now().strftime("%Y-%m-%d")
    host_address = f"http://{utils.LOCAL_IP}:3001"

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
        allowed_pages=allowed_pages,
        logged_in_doctor_name=logged_in_full_name
    )