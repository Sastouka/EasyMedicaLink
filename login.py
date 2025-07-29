# login.py — rôle Admin visible partout, création/reset ouverts à tous
import os
import sys
import json
import hmac
import hashlib
import ctypes
import platform
import socket
import uuid
import pathlib
import secrets
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, Dict

from flask import (
    Blueprint,
    request,
    render_template_string,
    redirect,
    url_for,
    flash,
    session,
    current_app
)

import utils # Import utils for dynamic base directory management
from activation import TRIAL_DAYS # Import TRIAL_DAYS from activation module

def generate_reset_token(length: int = 32) -> str:
    """
    Génère un token URL-safe pour la réinitialisation de mot de passe.
    """
    return secrets.token_urlsafe(length)

# Variable globale pour le chemin du fichier centralisé des utilisateurs
# CE CHEMIN EST MAINTENANT CENTRALISÉ SOUS MEDICALINK_DATA
USERS_FILE: Optional[Path] = None
# Cette clé HMAC doit être vraiment secrète et idéalement chargée depuis une variable d'environnement
# ou un système de gestion de configuration plus sécurisé dans un environnement de production.
HMAC_KEY = b"votre_cle_secrete_interne" # modifiez par une vraie clé

# Liste de tous les blueprints/pages de votre application pour les permissions
# Assurez-vous que cette liste est exhaustive et correspond aux noms de vos blueprints
ALL_BLUEPRINTS = [
    'accueil', 'rdv', 'facturation', 'biologie', 'radiologie', 'pharmacie',
    'comptabilite', 'statistique', 'administrateur_bp', 'developpeur_bp',
    'patient_rdv',
    'routes', # Ajout du blueprint 'routes' qui contient la page 'index' (consultation)
    'gestion_patient', # <--- ASSUREZ-VOUS QUE CETTE LIGNE EST PRÉSENTE
    'guide' # <--- AJOUTEZ CETTE LIGNE
]

def _set_login_paths():
    """
    Définit le chemin du fichier users.json centralisé et s'assure que le répertoire existe.
    Cette fonction ne dépend plus de l'email de l'administrateur pour le chemin de USERS_FILE.
    """
    global USERS_FILE

    # Le répertoire MEDICALINK_DATA est la racine pour tous les fichiers de données d'administrateur.
    # Le fichier users.json sera directement à cette racine.
    medicalink_data_root = Path(utils.application_path) / "MEDICALINK_DATA"
    medicalink_data_root.mkdir(parents=True, exist_ok=True)

    # Windows : attribuer l’attribut caché au dossier
    if platform.system() == "Windows":
        try:
            ctypes.windll.kernel32.SetFileAttributesW(str(medicalink_data_root), 0x02)
        except Exception as e:
            print(f"WARNING: Could not set hidden attribute on {medicalink_data_root}: {e}")

    USERS_FILE = medicalink_data_root / ".users.json" # préfixe point → cache sous *nix
    print(f"DEBUG (login): USERS_FILE path set to centralized: {USERS_FILE}")


# ── Calcul du HMAC d’un contenu bytes ───────────────────────────────────────
def _sign(data: bytes) -> str:
    return hmac.new(HMAC_KEY, data, hashlib.sha256).hexdigest()

# ── Lecture sécurisée ───────────────────────────────────────────────────────
def load_users() -> dict:
    """
    Charge tous les utilisateurs depuis le fichier .users.json centralisé.
    """
    _set_login_paths() # S'assure que USERS_FILE est défini

    if USERS_FILE is None:
        print("ERROR (login): USERS_FILE n'est pas défini. Impossible de charger les utilisateurs.")
        return {}
    if not USERS_FILE.exists():
        print(f"DEBUG (login): {USERS_FILE} does not exist. Returning empty users dict.")
        return {}
    
    try:
        raw = USERS_FILE.read_bytes()
        payload, sig = raw.rsplit(b"\n---SIGNATURE---\n", 1)
    except ValueError:
        print(f"ERROR (login): {USERS_FILE} corrupted: signature missing. Returning empty users dict.")
        return {}
    except Exception as e:
        print(f"ERROR (login): Unexpected error reading {USERS_FILE}: {e}. Returning empty users dict.")
        return {}

    if not hmac.compare_digest(_sign(payload), sig.decode()):
        print(f"ERROR (login): {USERS_FILE} corrupted: integrity compromised. Returning empty users dict.")
        return {}
    
    try:
        users_data = json.loads(payload.decode("utf-8"))
        print(f"DEBUG (login): Users loaded successfully from {USERS_FILE}. Total users: {len(users_data)}")
        return users_data
    except json.JSONDecodeError as e:
        print(f"ERROR (login): Failed to decode JSON from {USERS_FILE}: {e}. Returning empty users dict.")
        return {}


# ── Écriture sécurisée ──────────────────────────────────────────────────────
def save_users(users: dict):
    """
    Sauvegarde tous les utilisateurs dans le fichier .users.json centralisé.
    AVERTISSEMENT: En environnement multi-processus/multi-thread,
    l'écriture concurrente sur un fichier plat peut entraîner une corruption des données.
    Pour une application en production avec plusieurs instances ou un trafic élevé,
    une base de données est fortement recommandée.
    """
    _set_login_paths() # S'assure que USERS_FILE est défini

    if USERS_FILE is None:
        print("ERREUR (login): USERS_FILE n'est pas défini. Impossible de sauvegarder les utilisateurs.")
        return

    try:
        payload = json.dumps(users, ensure_ascii=False, indent=2).encode("utf-8")
        sig     = _sign(payload).encode()
        blob    = payload + b"\n---SIGNATURE---\n" + sig
        USERS_FILE.write_bytes(blob)
        print(f"DEBUG (login): Users saved successfully to {USERS_FILE}. Total users: {len(users)}")
    except Exception as e:
        print(f"ERROR (login): Failed to save users to {USERS_FILE}: {e}")

# ── Hachage de mot de passe ─────────────────────────────────────────────────
def hash_password(password: str) -> str:
    """
    Renvoie le SHA256 du mot de passe.
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

# ── QR et utils localhost ────────────────────────────────────────────────────
def lan_ip() -> str:
    ip = socket.gethostbyname(socket.gethostname())
    if ip.startswith("127."):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except:
            ip = "0.0.0.0"
    return ip

def is_localhost(req) -> bool:
    return req.remote_addr in ("127.0.0.1", "::1")

# ────────────────────────────────────────────────────────────────────────────
# Blueprint
# ────────────────────────────────────────────────────────────────────────────
login_bp = Blueprint("login", __name__)

# Fonction helper pour chercher l'utilisateur dans le fichier users.json centralisé
def _find_user_in_centralized_users_file(target_email: str, target_password_hash: str, target_role: str) -> Optional[Dict]:
    """
    Cherche un utilisateur dans le fichier .users.json centralisé.
    """
    users_data = load_users() # Charge tous les utilisateurs depuis le fichier centralisé

    user_found = users_data.get(target_email)
    if user_found:
        # Vérifier le mot de passe
        if user_found.get("password") != target_password_hash:
            return None # Mot de passe incorrect

        # Vérifier le rôle
        # Pour l'admin, le rôle doit correspondre exactement.
        # Pour les autres rôles, on vérifie d'abord si le rôle correspond.
        # Si le rôle dans la base est 'admin', il peut se connecter avec n'importe quel rôle si l'email et le mot de passe correspondent.
        if user_found.get("role", "admin") == 'admin':
            pass # Un admin peut se connecter avec n'importe quel rôle si les identifiants sont corrects.
        elif user_found.get("role", "admin") == target_role:
            pass # Rôle correspond
        else:
            return None # Rôle incorrect

        # Si l'utilisateur est trouvé et correspond aux critères
        # Déterminer l'email du propriétaire du compte.
        # Pour un admin, l'owner est lui-même. Pour les autres, c'est l'admin qui les a créés.
        owner_email = user_found.get("owner", target_email) # Si 'owner' n'est pas défini, l'utilisateur est son propre propriétaire (cas admin)

        return {
            "user_data": user_found,
            "admin_owner_email": owner_email, # C'est l'email à utiliser pour session['admin_email']
            "actual_role": user_found.get("role", "admin") # Le rôle réel du compte dans la BDD
        }
    return None

# NEW: Function to check if an email is globally unique across all admin folders
def _is_email_globally_unique(email_to_check: str) -> bool:
    """
    Vérifie si un email existe dans le fichier users.json centralisé.
    Retourne True si unique (non trouvé), False si déjà existe.
    """
    users_data = load_users() # Charge tous les utilisateurs depuis le fichier centralisé
    return email_to_check not in users_data

# ────────────────────────────────────────────────────────────────────────────
# TEMPLATES (inchangés, car ils sont définis dans templates.py et utilisés via render_template_string)
# ────────────────────────────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────────
# TEMPLATES (inchangés, car ils sont définis dans templates.py et utilisés via render_template_string)
# ────────────────────────────────────────────────────────────────────────────
login_template = """
<!DOCTYPE html><html lang='fr'>
{{ pwa_head()|safe }}
<head>
  <meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>Connexion</title>
  <link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'>
  <link href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css' rel='stylesheet'>
  <style>
    @keyframes fadeInUp {
      from { opacity: 0; transform: translateY(20px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @keyframes gradientFlow {
      0% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
      100% { background-position: 0% 50%; }
    }

    body {
      background: linear-gradient(135deg, #f0fafe 0%, #e3f2fd 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column; /* Added to stack card and signature */
    }

    .card {
      border-radius: 20px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.1);
      border: none;
      overflow: hidden;
      animation: fadeInUp 0.6s ease-out;
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(10px);
    }

    .btn-gradient {
      background: linear-gradient(45deg, #1a73e8, #0d9488);
      background-size: 200% auto;
      color: white;
      border: none;
      transition: all 0.3s ease;
      position: relative;
      overflow: hidden;
    }

    .btn-gradient:hover {
      background-position: right center;
      transform: translateY(-2px);
      box-shadow: 0 5px 15px rgba(26, 115, 232, 0.3);
    }

    .btn-gradient::after {
      content: '';
      position: absolute;
      top: 0;
      left: -200%;
      width: 200%;
      height: 100%;
      background: linear-gradient(
        to right,
        rgba(255,255,255,0) 0%,
        rgba(255,255,255,0.3) 50%,
        rgba(255,255,255,0) 100%
      );
      transform: skewX(-30deg);
      transition: left 0.6s;
    }

    .btn-gradient:hover::after {
      left: 200%;
    }

    .qr-container {
      transition: transform 0.3s ease;
    }

    .qr-container:hover {
      transform: scale(1.05);
    }

    .link-hover {
      transition: color 0.3s ease;
      position: relative;
    }

    .link-hover::after {
      content: '';
      position: absolute;
      bottom: -2px;
      left: 0;
      width: 0;
      height: 2px;
      background: #1a73e8;
      transition: width 0.3s ease;
    }

    .link-hover:hover::after {
      width: 100%;
    }

    .download-badge {
      position: relative;
      padding: 8px 15px;
      border-radius: 25px;
      font-size: 0.9rem;
      transition: all 0.3s ease;
    }
    /* New styles for contact info */
    .contact-info {
        margin-top: 20px;
        padding-top: 15px;
        border-top: 1px solid #eee;
        text-align: center;
    }
    .contact-info a {
        margin: 0 10px;
    }
    .signature {
        margin-top: 20px;
        text-align: center;
        font-size: 0.8rem;
        color: #777;
    }
    .app-icon { /* Nouveau style pour l'icône */
        width: 100px; /* Ajustez la taille selon vos préférences */
        height: 100px; /* Gardez la même valeur que la largeur pour un cercle/carré */
        margin-bottom: 20px;
        border-radius: 20%; /* Peut être '50%' pour un cercle */
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
  </style>
</head>
<body class='p-3'>
  <div class='card p-4' style='max-width:420px'>
    {# Ligne corrigée : Utilisation d'un chemin statique direct pour l'icône #}
    <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon mx-auto d-block">

    <h3 class='text-center mb-4 fw-bold' style="color: #1a73e8;">
      <i class='fas fa-user-lock me-2'></i>Connexion
    </h3>

    {% if win64_filename or win32_filename %}
    <div class="alert alert-info small text-center mb-3" role="alert">
      <i class="fas fa-desktop me-2"></i>
      Pour une expérience optimale et un travail collaboratif en mode local avec vos équipes,
      en toute tranquillité, pensez à télécharger notre application pour Windows.
      <br>
      <small>Les liens de téléchargement (32 et 64 bits) se trouvent plus bas sur cette page.</small>
    </div>
    {% endif %}
    {% with m=get_flashed_messages(with_categories=true) %}
      {% for c,msg in m %}
      <div class='alert alert-{{c}} small animate__animated animate__fadeIn'>{{msg}}</div>
      {% endfor %}
    {% endwith %}

    <form method='POST' class='animate__animated animate__fadeIn animate__delay-1s'>
      <div class='mb-3'>
        <label class='form-label small text-muted'><i class='fas fa-users-cog me-1'></i>Rôle</label>
        <select name='role_select' class='form-select form-select-lg shadow-sm'>
          <option value='admin'>Admin</option>
          <option value='medecin'>Médecin</option>
          <option value='assistante'>Assistante</option>
          <option value='comptable'>Comptable</option>
          <option value='biologiste'>Biologiste</option>
          <option value='radiologue'>Radiologue</option>
          <option value='pharmacie/magasin'>Pharmacie & Magasin</option>
        </select>
      </div>

      <div class='mb-3'>
        <label class='form-label small text-muted'><i class='fas fa-envelope me-1'></i>Email</label>
        <input name='email' type='email' class='form-control form-control-lg shadow-sm'>
      </div>

      <div class='mb-4'>
        <label class='form-label small text-muted'><i class='fas fa-key me-1'></i>Mot de passe</label>
        <input name='password' type='password' class='form-control form-control-lg shadow-sm'>
      </div>

      <button class='btn btn-gradient btn-lg w-100 py-3 fw-bold'>
        Se connecter
      </button>
    </form>

    <div class='d-flex gap-3 my-4 flex-column flex-md-row'>
      <div class='text-center flex-fill qr-container'>
        <canvas id='qrLocal' width='120' height='120'></canvas>
        <div class='small mt-2 text-muted'>Accès Web</div>
      </div>
      <div class='text-center flex-fill qr-container'>
        <canvas id='qrLan' width='120' height='120'></canvas>
        <div class='small mt-2 text-muted'>Réseau local</div>
      </div>
    </div>

    <div class='d-flex flex-column gap-2 mt-3'>
      <div class='d-flex flex-sm-row gap-2'>
        <a href='{{ url_for("login.register") }}'
           class='btn btn-gradient flex-fill py-2'>
          <i class='fas fa-user-plus me-1'></i>Créer un compte
        </a>
        <a href='{{ url_for("login.forgot_password") }}'
           class='btn btn-gradient flex-fill py-2'>
          <i class='fas fa-unlock-alt me-1'></i>Récupération
        </a>
      </div>
      
      {# Ancien bouton Guide Utilisateur - supprimé #}
      {#
      <a href='{{ url_for("guide.guide_home") }}'
         class='btn btn-outline-info flex-fill py-2 mt-2'>
        <i class='fas fa-book me-1'></i>Guide Utilisateur
      </a>
      #}
      {% if win64_filename or win32_filename %}
      <div class='text-center mt-3'>
        <div class='d-flex gap-2 justify-content-center'>
          {% if win64_filename %}
          <a href="{{ url_for('static', filename=win64_filename) }}"
             class='download-badge btn-gradient text-white text-decoration-none'>
             <i class='fas fa-download me-1'></i>Windows 64-bit
          </a>
          {% endif %}
          {% if win32_filename %}
          <a href="{{ url_for('static', filename=win32_filename) }}"
             class='download-badge btn-gradient text-white text-decoration-none'>
             <i class='fas fa-download me-1'></i>Windows 32-bit
          </a>
          {% endif %}
        </div>
      </div>
      {% endif %}
    </div>

    <div class='contact-info'>
        <p>N'hésitez pas à nous contacter par e-mail à sastoukadigital@gmail.com ou par téléphone au +212-652-084735. :</p>
        <a href='mailto:sastoukadigital@gmail.com' class='btn btn-outline-info'><i class='fas fa-envelope'></i> Email</a>
        <a href='https://wa.me/212652084735' class='btn btn-outline-success' target='_blank'><i class='fab fa-whatsapp'></i> WhatsApp</a>
    </div>

  </div>
  <div class="signature">
    Développé par SastoukaDigital
  </div>

  <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
  <script src='https://cdnjs.cloudflare.com/ajax/libs/qrious/4.0.2/qrious.min.js'></script>
  <script>
    // Animation au chargement
    document.addEventListener('DOMContentLoaded', () => {
      document.querySelectorAll('.animate__animated').forEach(el => {
        el.style.opacity = '0';
        setTimeout(() => el.style.opacity = '1', 100);
      });
    });

    // Génération des QR codes
    new QRious({
      element: document.getElementById('qrLocal'),
      value: 'https://easymedicalink.onrender.com/',
      size: 120,
      foreground: '#1a73e8'
    });

    new QRious({
      element: document.getElementById('qrLan'),
      value: '{{ url_lan }}',
      size: 120,
      foreground: '#0d9488'
    });
  </script>
</body>
</html>
"""

register_template = '''
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Enregistrement</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
  <style>
    .btn-medical { background: linear-gradient(45deg,#1a73e8,#0d9488); color:white; }
    body {
        background:#f0fafe;
        display: flex; /* Added for centering */
        flex-direction: column; /* Added for stacking */
        align-items: center; /* Added for centering */
        justify-content: center; /* Added for centering */
        min-height: 100vh; /* Added for full viewport height */
    }
    /* New styles for contact info */
    .contact-info {
        margin-top: 20px;
        padding-top: 15px;
        border-top: 1px solid #eee;
        text-align: center;
    }
    .contact-info a {
        margin: 0 10px;
    }
    .signature {
        margin-top: 20px;
        text-align: center;
        font-size: 0.8rem;
        color: #777;
    }
  </style>
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100 p-3">
  <div class="card p-4 shadow w-100" style="max-width: 480px;">
    <h3 class="text-center mb-3"><i class="fas fa-user-plus"></i> Enregistrement</h3>
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat,msg in msgs %}<div class="alert alert-{{cat}} small">{{msg}}</div>{% endfor %}
    {% endwith %}
    <form id="registerForm" method="POST">
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-envelope me-2"></i>Email</label>
        <input type="email" name="email" class="form-control form-control-lg" required>
      </div>
      <div class="mb-3 row g-2">
        <div class="col-12 col-md-6">
          <label class="form-label small"><i class="fas fa-key me-2"></i>Mot de passe</label>
          <input type="password" name="password" class="form-control form-control-lg" required>
        </div>
        <div class="col-12 col-md-6">
          <label class="form-label small"><i class="fas fa-key me-2"></i>Confirmer</label>
          <input type="password" name="confirm" class="form-control form-control-lg" required>
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-users-cog me-2"></i>Rôle</label>
        <select name="role" class="form-select form-select-lg" required>
          <option value="admin">Admin</option>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-hospital-symbol me-2"></i>Nom Clinique/Cabinet</label>
        <input type="text" name="clinic" class="form-control form-control-lg" required>
      </div>
      <div class="mb-3 row g-2">
        <div class="col-12 col-md-6">
          <label class="form-label small"><i class="fas fa-calendar-alt me-2"></i>Date de création (Clinique)</label> {# Updated label #}
          <input type="date" name="clinic_creation_date" class="form-control form-control-lg" required> {# Updated name #}
        </div>
        <div class="col-12 col-md-6">
          <label class="form-label small"><i class="fas fa-map-marker-alt me-2"></i>Adresse</label>
          <input type="text" name="address" class="form-control form-control-lg" required>
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-phone me-2"></i>Téléphone</label>
        <input type="tel" name="phone" class="form-control form-control-lg" placeholder="+212XXXXXXXXX" required pattern="^\\+\\d{9,}$">
        <div class="form-text text-muted">Le numéro de téléphone doit commencer par un '+' et contenir au moins 9 chiffres.</div>
      </div>
      <button type="submit" class="btn btn-medical btn-lg w-100">S'enregistrer</button>
    </form>
    <div class="text-center mt-3">
      <a href="{{ url_for('login.login') }}" class="btn btn-outline-secondary d-inline-flex align-items-center">
        <i class="fas fa-arrow-left me-1"></i> Retour Connexion
      </a>
    </div>
    <div class='contact-info'>
        <p>Besoin d'aide ? Contactez-nous :</p>
        <a href='mailto:sastoukadigital@gmail.com' class='btn btn-outline-info'><i class='fas fa-envelope'></i> Email</a>
        <a href='https://wa.me/212652084735' class='btn btn-outline-success' target='_blank'><i class='fab fa-whatsapp'></i> WhatsApp</a>
    </div>
  </div>
  <div class="signature">
    Développé par SastoukaDigital
  </div>
  <script>
    document.getElementById('registerForm').addEventListener('submit', function(e) {
      e.preventDefault();
      Swal.fire({
        title: 'Important',
        text: 'Veuillez conserver précieusement votre email, le nom de la clinique, la date de création et l’adresse. Ces informations seront nécessaires pour récupérer votre mot de passe.',
        icon: 'info',
        confirmButtonText: 'OK'
      }).then((result) => {
        if (result.isConfirmed) {
          this.submit();
        }
      });
    });
  </script>
  <script>
    // Fonction pour copier le texte dans le presse-papiers
    function copyToClipboard(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            Swal.fire({
                icon: 'success',
                title: 'Copié!',
                text: 'Détails du compte copiés dans le presse-papiers.',
                timer: 1500,
                showConfirmButton: false
            });
        } catch (err) {
            console.error('Échec de la copie: ', err);
            Swal.fire({
                icon: 'error',
                title: 'Erreur!',
                text: 'Échec de la copie des détails du compte.',
                timer: 1500,
                showConfirmButton: false
            });
        }
        document.body.removeChild(textarea);
    }

    document.addEventListener('DOMContentLoaded', function() {
        // Vérifie si des détails de nouvel utilisateur sont passés (après une inscription réussie)
        const newUserDetails = {{ new_user_details | tojson | safe }};
        const registrationSuccess = {{ registration_success | tojson | safe }};

        if (registrationSuccess && newUserDetails) {
            const detailsHtml = `
                <p>Votre compte administrateur a été créé avec succès !</p>
                <p>Veuillez conserver précieusement ces informations. Elles sont nécessaires pour la récupération de votre mot de passe et la gestion de votre espace.</p>
                <div style="text-align: left; background: #f0f0f0; padding: 10px; border-radius: 5px; margin-top: 15px; font-family: monospace;" id="accountDetails">
                    <strong>Email:</strong> ${newUserDetails.email}<br>
                    <strong>Nom Clinique/Cabinet:</strong> ${newUserDetails.clinic}<br>
                    <strong>Date de création:</strong> ${newUserDetails.creation_date}<br>
                    <strong>Adresse:</strong> ${newUserDetails.address}<br>
                    <strong>Téléphone:</strong> ${newUserDetails.phone}
                </div>
                <button id="copyDetailsBtn" class="swal2-confirm swal2-styled" style="margin-top: 20px;">
                    <i class="fas fa-copy me-2"></i>Copier les détails
                </button>
            `;

            Swal.fire({
                title: 'Compte créé !',
                icon: 'success',
                html: detailsHtml,
                showCancelButton: false,
                showConfirmButton: true,
                confirmButtonText: 'OK',
                didOpen: () => {
                    document.getElementById('copyDetailsBtn').addEventListener('click', () => {
                        const textToCopy = document.getElementById('accountDetails').innerText;
                        copyToClipboard(textToCopy);
                    });
                }
            }).then(() => {
                // Rediriger vers la page de connexion après que l'utilisateur ait cliqué sur OK
                window.location.href = "{{ url_for('login.login') }}";
            });
        }
    });
  </script>
</body>
</html>
'''

reset_template = '''
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Réinitialiser mot de passe</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
  <style>
    .btn-medical { background: linear-gradient(45deg,#1a73e8,#0d9488); color:white; }
    body {
        background:#f0fafe;
        display: flex; /* Added for centering */
        flex-direction: column; /* Added for stacking */
        align-items: center; /* Added for centering */
        justify-content: center; /* Added for centering */
        min-height: 100vh; /* Added for full viewport height */
    }
    /* New styles for contact info */
    .contact-info {
        margin-top: 20px;
        padding-top: 15px;
        border-top: 1px solid #eee;
        text-align: center;
    }
    .contact-info a {
        margin: 0 10px;
    }
    .signature {
        margin-top: 20px;
        text-align: center;
        font-size: 0.8rem;
        color: #777;
    }
  </style>
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100 p-3">
  <div class="card p-4 shadow w-100" style="max-width: 400px;">
    <h3 class="text-center mb-3"><i class="fas fa-redo-alt"></i> Réinitialiser mot de passe</h3>
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat,msg in msgs %}<div class="alert alert-{{cat}} small">{{msg}}</div>{% endfor %}
    {% endwith %}
    <form method="POST">
      <div class="mb-3 row g-2">
        <div class="col-12 col-md-6">
          <label class="form-label small">Nouveau mot de passe</label>
          <input type="password" name="password" class="form-control form-control-lg" required>
        </div>
        <div class="col-12 col-md-6">
          <label class="form-label small">Confirmer</label>
          <input type="password" name="confirm" class="form-control form-control-lg" required>
        </div>
      </div>
      <button type="submit" class="btn btn-medical btn-lg w-100">Mettre à jour</button>
    </form>
    <div class='contact-info'>
        <p>Besoin d'aide ? Contactez-nous :</p>
        <a href='mailto:sastoukadigital@gmail.com' class='btn btn-outline-info'><i class='fas fa-envelope'></i> Email</a>
        <a href='https://wa.me/212652084735' class='btn btn-outline-success' target='_blank'><i class='fab fa-whatsapp'></i> WhatsApp</a>
    </div>
  </div>
  <div class="signature">
    Développé par SastoukaDigital
  </div>
</body>
</html>
'''

forgot_template = '''
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Récupération mot de passe</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
  <style>
    .btn-medical { background: linear-gradient(45deg,#1a73e8,#0d9488); color:white; }
    body {
        background:#f0fafe;
        display: flex; /* Added for centering */
        flex-direction: column; /* Added for stacking */
        align-items: center; /* Added for centering */
        justify-content: center; /* Added for centering */
        min-height: 100vh; /* Added for full viewport height */
    }
    /* New styles for contact info */
    .contact-info {
        margin-top: 20px;
        padding-top: 15px;
        border-top: 1px solid #eee;
        text-align: center;
    }
    .contact-info a {
        margin: 0 10px;
    }
    .signature {
        margin-top: 20px;
        text-align: center;
        font-size: 0.8rem;
        color: #777;
    }
  </style>
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100 p-3">
  <div class="card p-4 shadow w-100" style="max-width: 400px;">
    <h3 class="text-center mb-3"><i class="fas fa-unlock-alt"></i>Récupération</h3>
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat,msg in msgs %}<div class="alert alert-{{cat}} small">{{msg}}</div>{% endfor %}
    {% endwith %}
    <form method="POST">
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-envelope me-2"></i>Email</label>
        <input type="email" name="email" class="form-control form-control-lg" required>
      </div>
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-hospital me-2"></i>Nom Clinique</label>
        <input type="text" name="clinic" class="form-control form-control-lg" required>
      </div>
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-calendar-alt me-2"></i>Date de création</label>
        <input type="date" name="creation_date" class="form-control form-control-lg" required>
      </div>
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-map-marker-alt me-2"></i>Adresse</label>
        <input type="text" name="address" class="form-control form-control-lg" required>
      </div>
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-phone me-2"></i>Téléphone</label>
        <input type="tel" class="form-control form-control-lg" placeholder="+212XXXXXXXXX" required pattern="^\\+\\d{9,}$">
        <div class="form-text text-muted">Le numéro de téléphone doit commencer par un '+' et contenir au moins 9 chiffres.</div>
      </div>
      <button type="submit" class="btn btn-medical btn-lg w-100">Valider</button>
    </form>
    <div class='contact-info'>
        <p>Besoin d'aide ? Contactez-nous :</p>
        <a href='mailto:sastoukadigital@gmail.com' class='btn btn-outline-info'><i class='fas fa-envelope'></i> Email</a>
        <a href='https://wa.me/212652084735' class='btn btn-outline-success' target='_blank'><i class='fab fa-whatsapp'></i> WhatsApp</a>
    </div>
  </div>
  <div class="signature">
    Développé par SastoukaDigital
  </div>
</body>
</html>
'''

# ───────── 4. Routes
@login_bp.route("/login", methods=["GET", "POST"])
def login():
    # S'assure que le chemin du fichier users.json centralisé est défini.
    # Les autres chemins dynamiques (pour les données spécifiques à l'admin)
    # seront définis par app.py.
    _set_login_paths()

    local = is_localhost(request)

    # Nouveau code pour détection des exécutables
    static_folder = current_app.static_folder
    contents = os.listdir(static_folder) if os.path.exists(static_folder) else []
    win64_filename = next((f for f in contents if f.startswith('EasyMedicaLink-Win64.exe')), None)
    win32_filename = next((f for f in contents if f.startswith('EasyMedicaLink-Win32.exe')), None)

    if request.method == "POST":
        role_selected = request.form["role_select"] # Renommé pour éviter conflit avec 'role' de l'utilisateur réel
        email = request.form["email"].lower().strip()
        pwd = request.form["password"]
        pwd_hash = hash_password(pwd) # Hash the password for lookup

        # --- Recherche d'utilisateur dans le fichier centralisé ---
        found_user_info = _find_user_in_centralized_users_file(email, pwd_hash, role_selected)

        if found_user_info:
            user_data = found_user_info["user_data"]
            admin_owner_email = found_user_info["admin_owner_email"]
            actual_role = found_user_info["actual_role"] # Le rôle réel du compte dans la BDD

            # Authentification réussie. Définir les variables de session.
            session["email"] = email
            session["role"] = actual_role # Utiliser le rôle réel du compte trouvé
            session["admin_email"] = admin_owner_email # CRUCIAL: Définir admin_email au propriétaire!
            session.permanent = True

            # Redirection vers la page d'accueil pour TOUS les rôles.
            # Tout message flashé avant cette redirection (par exemple, un message d'erreur
            # d'une page précédente due à une expiration de session) sera affiché sur la page d'accueil.
            return redirect(url_for("accueil.accueil"))

        flash("Identifiants ou rôle invalides.", "danger")

    return render_template_string(
        login_template,
        url_lan = f"http://{lan_ip()}:3000",
        win64_filename=win64_filename,
        win32_filename=win32_filename
    )

@login_bp.route("/register", methods=["GET","POST"])
def register():
    # S'assure que le chemin du fichier users.json centralisé est défini.
    _set_login_paths()

    # Initialisation des variables pour le template
    registration_success = False
    new_user_details = None

    if request.method == "POST":
        email_to_register = request.form["email"].lower().strip()

        f = request.form
        users = load_users() # Charge tous les utilisateurs depuis le fichier centralisé
        email = f["email"].lower()
        phone = f["phone"].strip() # Récupérer le numéro de téléphone

        # NOUVEAU : Vérification d'unicité globale de l'email
        if not _is_email_globally_unique(email):
            flash(f"L'e-mail '{email}' est déjà utilisé par un autre compte administrateur.", "danger")
            # Ne pas rediriger, rester sur la page d'enregistrement pour afficher le message
            return render_template_string(register_template)

        if email in users: # Cette vérification est maintenant redondante avec _is_email_globally_unique mais peut rester
            flash("Email déjà enregistré.","danger")
        elif f["password"] != f["confirm"]:
            flash("Les mots de passe ne correspondent pas.","danger")
        elif not phone.startswith('+') or len(phone) < 10: # Validation du numéro de téléphone
            flash("Le numéro de téléphone doit commencer par '+' et contenir au moins 9 chiffres.","danger")
        else:
            # Assigner explicitement les dates
            clinic_creation_date_val = f["clinic_creation_date"]
            account_creation_date_val = date.today().isoformat()

            print(f"DEBUG (login/register): Tentative de création de compte pour {email}")
            print(f"DEBUG (login/register): clinic_creation_date_val = {clinic_creation_date_val}")
            print(f"DEBUG (login/register): account_creation_date_val = {account_creation_date_val}")

            users[email] = {
                "password":      hash_password(f["password"]),
                "role":          f["role"], # Ce sera toujours 'admin' depuis le formulaire actuel
                "clinic":        f["clinic"],
                "clinic_creation_date": clinic_creation_date_val, # Use the explicit variable
                "account_creation_date": account_creation_date_val, # Use the explicit variable
                "address":       f["address"],
                "phone":         phone, # Sauvegarder le numéro de téléphone
                "active":        True, # Les nouveaux comptes sont actifs par défaut
                "owner":         email, # Pour un admin, il est son propre propriétaire
                "allowed_pages": ALL_BLUEPRINTS, # Par défaut, un admin a accès à toutes les pages
                "account_limits": { # Initialiser les limites de comptes pour le nouvel admin
                    "medecin": 0, "assistante": 0, "comptable": 0,
                    "biologiste": 0, "radiologue": 0, "pharmacie": 0
                },
                # Initialiser l'activation pour une période d'essai de 7 jours
                "activation": {
                    "plan": f"essai_{TRIAL_DAYS}jours", # Plan d'essai
                    "activation_date": date.today().isoformat(), # Date d'aujourd'hui
                    "activation_code": "0000-0000-0000-0000" # Clé d'essai spécifique
                }
            }
            save_users(users) # Sauvegarde dans le fichier centralisé
            
            # Définir les détails de l'utilisateur pour l'affichage dans SweetAlert
            new_user_details = {
                "email": email,
                "clinic": f["clinic"],
                "creation_date": clinic_creation_date_val, # Use clinic_creation_date_val for this display
                "address": f["address"],
                "phone": phone
            }
            registration_success = True
            # Ne pas flasher de message ici, SweetAlert le gérera
            # flash("Compte créé.","success") # REMOVED: SweetAlert gérera le succès

    return render_template_string(
        register_template,
        registration_success=registration_success,
        new_user_details=new_user_details
    )

@login_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    # S'assure que le chemin du fichier users.json centralisé est défini.
    _set_login_paths()

    local = is_localhost(request)

    if request.method == "POST":
        email_form = request.form['email'].strip().lower()
        clinic_form = request.form['clinic']
        clinic_creation_date_form = request.form['creation_date'] # Use the existing form field name
        address_form = request.form['address']
        phone_form = request.form['phone'].strip()

        # Charger tous les utilisateurs depuis le fichier centralisé
        users = load_users()
        user_found_globally = None

        for email_candidate, user_candidate in users.items():
            # For password recovery, check against clinic creation date ('clinic_creation_date' field for new accounts
            # or 'creation_date' for old accounts).
            # The form in forgot_template still uses 'creation_date' name.
            user_clinic_creation_date = user_candidate.get('clinic_creation_date', user_candidate.get('creation_date', ''))
            
            if (user_candidate.get('role') == 'admin' # Seuls les admins peuvent récupérer leur mot de passe via ce formulaire
                and email_candidate == email_form # L'email doit correspondre
                and user_candidate.get('clinic') == clinic_form
                and user_clinic_creation_date == clinic_creation_date_form # Check against the date from the form
                and user_candidate.get('address') == address_form
                and user_candidate.get('phone') == phone_form):
                user_found_globally = user_candidate
                break # Utilisateur trouvé, arrêter la recherche

        if user_found_globally:
            # Utilisateur trouvé et validé.
            token  = generate_reset_token()
            expiry = (datetime.now() + timedelta(hours=1)).isoformat()

            user_found_globally['reset_token']  = token
            user_found_globally['reset_expiry'] = expiry
            save_users(users) # Sauvegarde dans le fichier centralisé

            flash('Un lien de réinitialisation a été envoyé à votre email.', 'info') # Informer l'utilisateur
            return redirect(url_for('login.reset_password', token=token))

        flash('Données non reconnues, veuillez réessayer.', "danger")

    return render_template_string(
        forgot_template,
        local=local
    )

@login_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    email = session.get('email')
    if not email:
        flash('Vous devez être connecté pour changer votre mot de passe.', 'warning')
        return redirect(url_for('login.login'))

    # S'assure que le chemin du fichier users.json centralisé est défini.
    _set_login_paths()

    users = load_users() # Charge depuis le fichier centralisé
    user  = users.get(email)

    if request.method == 'POST':
        pwd     = request.form['password']
        confirm = request.form['confirm']
        if pwd != confirm:
            flash('Les mots de passe ne correspondent pas', 'warning')
        else:
            user['password'] = hash_password(pwd)
            save_users(users) # Sauvegarde dans le fichier centralisé
            flash('Mot de passe mis à jour', 'success')
            return redirect(url_for('login.login'))

    return render_template_string(reset_template)

@login_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # S'assure que le chemin du fichier users.json centralisé est défini.
    _set_login_paths()

    user_to_reset_data = None
    user_email_for_reset = None

    # Chercher l'utilisateur associé à ce token dans le fichier centralisé
    users = load_users()
    for email_candidate, user_candidate in users.items():
        if user_candidate.get('reset_token') == token:
            user_to_reset_data = user_candidate
            user_email_for_reset = email_candidate # Stocke l'email réel de l'utilisateur
            break # Token et utilisateur trouvés, arrêter la recherche

    if user_to_reset_data and user_email_for_reset:
        user = users.get(user_email_for_reset) # Récupère l'objet utilisateur mis à jour

        if user is None: # Ne devrait pas arriver si le token a été trouvé
            flash('Lien invalide ou utilisateur introuvable après rechargement.', "danger")
            return redirect(url_for('login.forgot_password'))

        expiry = datetime.fromisoformat(user.get('reset_expiry'))
        if datetime.now() > expiry:
            flash('Le lien a expiré', "danger")
            return redirect(url_for('login.forgot_password'))
        if request.method == 'POST':
            pwd     = request.form['password']
            confirm = request.form['confirm']
            if pwd != confirm:
                flash('Les mots de passe ne correspondent pas', 'warning')
            else:
                user['password']     = hash_password(pwd)
                user['reset_token']  = ''
                user['reset_expiry'] = ''
                save_users(users) # Sauvegarde dans le fichier centralisé
                flash('Mot de passe mis à jour', 'success')
                return redirect(url_for('login.login'))
        return render_template_string(reset_template)
    flash('Lien invalide', "danger")
    return redirect(url_for('login.forgot_password'))

@login_bp.route('/logout')
def logout():
    session.pop('email', None)
    session.pop('role',  None)
    session.pop('admin_email', None) # Efface admin_email à la déconnexion
    return redirect(url_for('login.login'))
