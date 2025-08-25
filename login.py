# login.py
# Description: Gère l'authentification, l'enregistrement, la récupération et le changement de mot de passe.
# Version finale fusionnant la refactorisation et les fonctionnalités complètes.

import os
import json
import hmac
import hashlib
import ctypes
import platform
import socket
import secrets
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, Dict, Any

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

# Importations depuis les modules internes de l'application
import utils
from activation import TRIAL_DAYS, get_hardware_id

# --- Configuration et Constantes ---

login_bp = Blueprint("login", __name__)
USERS_FILE: Optional[Path] = None
HMAC_KEY = b"votre_cle_secrete_interne_a_remplacer" # IMPORTANT: À changer pour une clé plus robuste

ALL_BLUEPRINTS = [
    'accueil', 'rdv', 'facturation', 'biologie', 'radiologie', 'pharmacie',
    'comptabilite', 'statistique', 'administrateur_bp', 'developpeur_bp',
    'patient_rdv', 'routes', 'gestion_patient', 'guide', 'ia_assitant'
]

# --- Gestion des Fichiers et Chemins ---

def _set_login_paths():
    """Définit le chemin centralisé pour USERS_FILE sous MEDICALINK_DATA."""
    global USERS_FILE
    if USERS_FILE:
        return

    try:
        medicalink_data_root = Path(utils.application_path) / "MEDICALINK_DATA"
        medicalink_data_root.mkdir(parents=True, exist_ok=True)
        if platform.system() == "Windows":
            ctypes.windll.kernel32.SetFileAttributesW(str(medicalink_data_root), 0x02)
    except Exception as e:
        print(f"AVERTISSEMENT: Impossible de masquer le dossier MEDICALINK_DATA: {e}")

    USERS_FILE = medicalink_data_root / ".users.json"

# --- Sécurité et Hachage ---

def _sign(data: bytes) -> str:
    """Génère une signature HMAC-SHA256 pour des données."""
    return hmac.new(HMAC_KEY, data, hashlib.sha256).hexdigest()

def hash_password(password: str) -> str:
    """Hache un mot de passe en utilisant SHA256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def generate_reset_token(length: int = 32) -> str:
    """Génère un token sécurisé pour la réinitialisation de mot de passe."""
    return secrets.token_urlsafe(length)

# --- Lecture et Écriture des Données Utilisateurs ---

def load_users() -> Dict[str, Any]:
    """Charge les utilisateurs et vérifie leur intégrité."""
    _set_login_paths()
    if not USERS_FILE or not USERS_FILE.exists():
        return {}
    try:
        raw_content = USERS_FILE.read_bytes()
        payload, signature = raw_content.rsplit(b"\n---SIGNATURE---\n", 1)
        if not hmac.compare_digest(_sign(payload), signature.decode()):
            print(f"ERREUR FATALE: L'intégrité du fichier {USERS_FILE} est compromise !")
            return {}
        return json.loads(payload.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as e:
        print(f"ERREUR: Fichier {USERS_FILE} corrompu ou mal formé : {e}")
    except Exception as e:
        print(f"ERREUR inattendue lors de la lecture de {USERS_FILE}: {e}")
    return {}

def save_users(users: Dict[str, Any]):
    """Sauvegarde les utilisateurs avec une signature d'intégrité."""
    _set_login_paths()
    if not USERS_FILE:
        print("ERREUR: Chemin USERS_FILE non défini. Sauvegarde annulée.")
        return
    try:
        payload = json.dumps(users, ensure_ascii=False, indent=2).encode("utf-8")
        signature = _sign(payload).encode()
        USERS_FILE.write_bytes(payload + b"\n---SIGNATURE---\n" + signature)
    except Exception as e:
        print(f"ERREUR: Échec de la sauvegarde des utilisateurs dans {USERS_FILE}: {e}")

# --- Fonctions Utilitaires ---

def lan_ip() -> str:
    """Tente de trouver l'adresse IP sur le réseau local (LAN)."""
    ip = socket.gethostbyname(socket.gethostname())
    if ip.startswith("127."):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]
        except Exception:
            ip = "0.0.0.0"
    return ip

def _find_user_in_centralized_users_file(target_email: str, target_password_hash: str) -> Optional[Dict]:
    """Cherche un utilisateur par email et hash de mot de passe."""
    user = load_users().get(target_email)
    if user and user.get("password") == target_password_hash:
        owner_email = user.get("owner", target_email)
        return {
            "user_data": user,
            "admin_owner_email": owner_email,
            "actual_role": user.get("role", "admin")
        }
    return None

def _is_email_globally_unique(email_to_check: str) -> bool:
    """Vérifie si un email est déjà utilisé."""
    return email_to_check not in load_users()

# --- Routes du Blueprint ---

@login_bp.route("/login", methods=["GET", "POST"])
def login():
    _set_login_paths()
    if request.method == "POST":
        email = request.form["email"].lower().strip()
        pwd_hash = hash_password(request.form["password"])
        found_user_info = _find_user_in_centralized_users_file(email, pwd_hash)

        if found_user_info:
            # --- DÉBUT DE LA MODIFICATION ---
            # Vérifier si le compte est actif AVANT de créer la session
            if not found_user_info["user_data"].get("active", True):
                flash(
                    "Votre compte est inactif. Veuillez contacter le propriétaire de l'application.", 
                    "danger"
                )
                # Rediriger vers la page d'activation pour afficher le message
                return redirect(url_for("activation.activation"))
            # --- FIN DE LA MODIFICATION ---

            session["email"] = email
            session["role"] = found_user_info["actual_role"]
            session["admin_email"] = found_user_info["admin_owner_email"]
            session.permanent = True

            # Collecte de l'ID machine pour les admins
            if session["role"] == 'admin':
                try:
                    hw_id = get_hardware_id()
                    users = load_users()
                    if email in users and users[email].get('machine_id') != hw_id:
                        users[email]['machine_id'] = hw_id
                        save_users(users)
                except Exception as e:
                    print(f"ERREUR: Impossible de sauvegarder l'ID machine pour {email}: {e}")

            return redirect(url_for("accueil.accueil"))
        flash("Identifiants ou rôle invalides.", "danger")

    static_folder = current_app.static_folder
    contents = os.listdir(static_folder) if os.path.exists(static_folder) else []
    win64 = next((f for f in contents if f.startswith('EasyMedicaLink-Win64.exe')), None)
    win32 = next((f for f in contents if f.startswith('EasyMedicaLink-Win32.exe')), None)

    return render_template_string(login_template, url_lan=f"http://{lan_ip()}:3000", win64_filename=win64, win32_filename=win32)

@login_bp.route("/register", methods=["GET", "POST"])
def register():
    _set_login_paths()
    registration_success, new_user_details = False, None
    if request.method == "POST":
        f = request.form
        email = f["email"].lower().strip()
        phone = f["phone"].strip()

        if not _is_email_globally_unique(email):
            flash(f"L'e-mail '{email}' est déjà utilisé.", "danger")
        elif f["password"] != f["confirm"]:
            flash("Les mots de passe ne correspondent pas.", "danger")
        elif not phone.startswith('+') or len(phone) < 10:
            flash("Le numéro de téléphone est invalide.", "danger")
        else:
            users = load_users()
            creation_date = f["clinic_creation_date"]
            users[email] = {
                "password": hash_password(f["password"]), "role": "admin", "clinic": f["clinic"],
                "clinic_creation_date": creation_date, "account_creation_date": date.today().isoformat(),
                "address": f["address"], "phone": phone, "active": True, "owner": email,
                "allowed_pages": ALL_BLUEPRINTS,
                "account_limits": {"medecin":0, "assistante":0, "comptable":0, "biologiste":0, "radiologue":0, "pharmacie":0},
                "activation": {"plan": f"essai_{TRIAL_DAYS}jours", "activation_date": date.today().isoformat(), "activation_code": "0000-0000-0000-0000"}
            }
            save_users(users)
            new_user_details = {"email": email, "clinic": f["clinic"], "creation_date": creation_date, "address": f["address"], "phone": phone}
            registration_success = True
    return render_template_string(register_template, registration_success=registration_success, new_user_details=new_user_details)

@login_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    _set_login_paths()
    if request.method == "POST":
        f = request.form
        email, clinic, address, phone = f['email'].strip().lower(), f['clinic'], f['address'], f['phone'].strip()
        creation_date = f['creation_date']
        users = load_users()
        user_found = None

        if email in users and users[email].get('role') == 'admin':
            user = users[email]
            user_creation_date = user.get('clinic_creation_date', user.get('creation_date'))
            if (user.get('clinic') == clinic and user_creation_date == creation_date and
                user.get('address') == address and user.get('phone') == phone):
                user_found = user

        if user_found:
            token, expiry = generate_reset_token(), (datetime.now() + timedelta(hours=1)).isoformat()
            users[email]['reset_token'], users[email]['reset_expiry'] = token, expiry
            save_users(users)
            flash('Un lien de réinitialisation a été généré.', 'info')
            return redirect(url_for('login.reset_password', token=token))
        flash('Données non reconnues, veuillez réessayer.', "danger")
    return render_template_string(forgot_template)

@login_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    _set_login_paths()
    users = load_users()
    user_email, user_data = None, None
    for e, u in users.items():
        if u.get('reset_token') == token:
            user_email, user_data = e, u
            break

    if not user_data:
        flash('Lien invalide ou expiré.', "danger")
        return redirect(url_for('login.forgot_password'))

    if datetime.now() > datetime.fromisoformat(user_data.get('reset_expiry')):
        flash('Le lien a expiré.', "danger")
        return redirect(url_for('login.forgot_password'))

    if request.method == 'POST':
        pwd, confirm = request.form['password'], request.form['confirm']
        if pwd != confirm:
            flash('Les mots de passe ne correspondent pas.', 'warning')
        else:
            users[user_email]['password'] = hash_password(pwd)
            users[user_email].pop('reset_token', None)
            users[user_email].pop('reset_expiry', None)
            save_users(users)
            flash('Mot de passe mis à jour avec succès.', 'success')
            return redirect(url_for('login.login'))
    return render_template_string(reset_template)

@login_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    """Route pour que l'utilisateur connecté change son propre mot de passe."""
    if 'email' not in session:
        flash('Vous devez être connecté pour changer votre mot de passe.', 'warning')
        return redirect(url_for('login.login'))

    if request.method == 'POST':
        pwd, confirm = request.form['password'], request.form['confirm']
        if pwd != confirm:
            flash('Les mots de passe ne correspondent pas.', 'warning')
        else:
            _set_login_paths()
            users = load_users()
            if session['email'] in users:
                users[session['email']]['password'] = hash_password(pwd)
                save_users(users)
                flash('Mot de passe mis à jour avec succès.', 'success')
                return redirect(url_for('accueil.accueil')) # Redirige vers l'accueil après succès
            else:
                flash('Utilisateur non trouvé.', 'danger')

    return render_template_string(reset_template) # Réutilise le template de réinitialisation

@login_bp.route('/logout')
def logout():
    session.clear()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for('login.login'))

# ────────────────────────────────────────────────────────────────────────────
# TEMPLATES (inchangés, car ils sont définis dans templates.py et utilisés via render_template_string)
# ────────────────────────────────────────────────────────────────────────────
login_template = '''
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
    body {
      background: linear-gradient(135deg, #f0fafe 0%, #e3f2fd 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
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
    }
    .btn-gradient:hover {
      background-position: right center;
      transform: translateY(-2px);
      box-shadow: 0 5px 15px rgba(26, 115, 232, 0.3);
    }
    .contact-info { margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee; text-align: center; }
    .signature { margin-top: 20px; text-align: center; font-size: 0.8rem; color: #777; }
    .app-icon { width: 100px; height: 100px; margin-bottom: 20px; border-radius: 20%; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    
    /* NOUVEAU : Style pour la bannière d'installation PWA */
    .pwa-install-banner {
        background-color: #e3f2fd;
        border: 1px solid #1a73e8;
        border-radius: 12px;
        padding: 1rem;
        transition: all 0.5s ease-in-out;
    }
  </style>
</head>
<body class='p-3'>
  <div class='card p-4' style='max-width:420px'>
    <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon mx-auto d-block">

    <h3 class='text-center mb-4 fw-bold'>
      <i class='fas fa-user-lock me-2' style="color: #1a73e8;"></i>Connexion
    </h3>
    
    <div id="pwa-install-banner" class="pwa-install-banner mb-3 d-none">
        <div class="d-flex align-items-center">
            <div class="flex-grow-1">
                <h5 class="mb-1" style="color: #1a73e8;"><i class="fas fa-rocket me-2"></i>Accès rapide</h5>
                <p class="mb-0 small">Installez cette application sur votre appareil pour une expérience améliorée.</p>
            </div>
            <button id="pwa-install-button" class="btn btn-gradient ms-3 flex-shrink-0">
                <i class="fas fa-download me-2"></i>Installer
            </button>
        </div>
    </div>

    {% with m=get_flashed_messages(with_categories=true) %}
      {% for c,msg in m %}
      <div class='alert alert-{{c}} small'>{{msg}}</div>
      {% endfor %}
    {% endwith %}

    <form method='POST'>
      <div class='mb-3'>
        <label class='form-label small text-muted'><i class='fas fa-users-cog me-1' style="color: #673AB7;"></i>Rôle</label>
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
        <label class='form-label small text-muted'><i class='fas fa-envelope me-1' style="color: #FF5722;"></i>Email</label>
        <input name='email' type='email' class='form-control form-control-lg shadow-sm'>
      </div>
      <div class='mb-4'>
        <label class='form-label small text-muted'><i class='fas fa-key me-1' style="color: #E91E63;"></i>Mot de passe</label>
        <input name='password' type='password' class='form-control form-control-lg shadow-sm'>
      </div>
      <button class='btn btn-gradient btn-lg w-100 py-3 fw-bold'>Se connecter</button>
    </form>
    
    <div class='d-flex gap-3 my-4 flex-column flex-md-row'>
        <div class='text-center flex-fill'><canvas id='qrLocal' width='120' height='120'></canvas><div class='small mt-2 text-muted'>Accès Web</div></div>
        <div class='text-center flex-fill'><canvas id='qrLan' width='120' height='120'></canvas><div class='small mt-2 text-muted'>Réseau local</div></div>
    </div>

    <div class='d-flex flex-column gap-2 mt-3'>
        <a href='{{ url_for("login.register") }}' class='btn btn-outline-primary flex-fill py-2'><i class='fas fa-user-plus me-1' style="color: #00BCD4;"></i>Créer un compte</a>
        <a href='{{ url_for("login.forgot_password") }}' class='btn btn-outline-secondary flex-fill py-2'><i class='fas fa-unlock-alt me-1' style="color: #FFC107;"></i>Récupération</a>
    </div>
    
    {% if win64_filename or win32_filename %}
    <div class='text-center mt-3'>
        <div class="alert alert-info small text-center mb-3" role="alert">
          <i class="fas fa-desktop me-2" style="color: #007BFF;"></i>
          Pour une expérience en version locale sur PC Windows, pensez à télécharger notre application locale.
        <div class='d-flex gap-2 justify-content-center'>
          {% if win64_filename %}
          <a href="{{ url_for('static', filename=win64_filename) }}" class='btn btn-gradient text-white text-decoration-none'><i class='fas fa-download me-1'></i>Windows 64-bit</a>
          {% endif %}
          {% if win32_filename %}
          <a href="{{ url_for('static', filename=win32_filename) }}" class='btn btn-gradient text-white text-decoration-none'><i class='fas fa-download me-1'></i>Windows 32-bit</a>
          {% endif %}
        </div>
    </div>
    {% endif %}

    <div class='contact-info'>
        <p>Contactez-nous: sastoukadigital@gmail.com | +212652084735</p>
        <a href='mailto:sastoukadigital@gmail.com' class='btn btn-outline-info'><i class='fas fa-envelope'></i> Email</a>
        <a href='https://wa.me/212652084735' class='btn btn-outline-success' target='_blank'><i class='fab fa-whatsapp'></i> WhatsApp</a>
    </div>
  </div>
  <div class="signature">Développé par SastoukaDigital</div>

  <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
  <script src='https://cdnjs.cloudflare.com/ajax/libs/qrious/4.0.2/qrious.min.js'></script>
  <script>
    new QRious({ element: document.getElementById('qrLocal'), value: 'https://easymedicalink.onrender.com/', size: 120, foreground: '#1a73e8' });
    new QRious({ element: document.getElementById('qrLan'), value: '{{ url_lan }}', size: 120, foreground: '#0d9488' });
  </script>
  
  <script>
    document.addEventListener('DOMContentLoaded', () => {
        let deferredPrompt;
        const installBanner = document.getElementById('pwa-install-banner');
        const installButton = document.getElementById('pwa-install-button');

        // Cache la bannière par défaut
        installBanner.classList.add('d-none');

        // Ne montrer la bannière que si l'événement est déclenché ET que l'app n'est pas déjà installée
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            installBanner.classList.remove('d-none');
        });

        if (installButton) {
            installButton.addEventListener('click', async () => {
                if (deferredPrompt) {
                    deferredPrompt.prompt();
                    const { outcome } = await deferredPrompt.userChoice;
                    console.log(`User response to the install prompt: ${outcome}`);
                    deferredPrompt = null;
                    if (installBanner) {
                        installBanner.classList.add('d-none');
                    }
                }
            });
        }
    });
  </script>
</body>
</html>
'''

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
    .contact-info { margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee; text-align: center; }
    .signature { margin-top: 20px; text-align: center; font-size: 0.8rem; color: #777; }
    .app-icon { width: 100px; height: 100px; margin-bottom: 20px; border-radius: 20%; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
  </style>
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100 p-3">
  <div class="card p-4 shadow w-100" style="max-width: 480px;">
    <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon mx-auto d-block">
    <h3 class="text-center mb-3"><i class="fas fa-user-plus" style="color: #00BCD4;"></i> Enregistrement</h3>
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat,msg in msgs %}<div class="alert alert-{{cat}} small">{{msg}}</div>{% endfor %}
    {% endwith %}
    <form id="registerForm" method="POST">
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-envelope me-2" style="color: #FF5722;"></i>Email</label>
        <input type="email" name="email" class="form-control form-control-lg" required>
      </div>
      <div class="mb-3 row g-2">
        <div class="col-12 col-md-6">
          <label class="form-label small"><i class="fas fa-key me-2" style="color: #E91E63;"></i>Mot de passe</label>
          <input type="password" name="password" class="form-control form-control-lg" required>
        </div>
        <div class="col-12 col-md-6">
          <label class="form-label small"><i class="fas fa-key me-2" style="color: #E91E63;"></i>Confirmer</label>
          <input type="password" name="confirm" class="form-control form-control-lg" required>
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-users-cog me-2" style="color: #673AB7;"></i>Rôle</label>
        <select name="role" class="form-select form-select-lg" required>
          <option value="admin">Admin</option>
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-hospital-symbol me-2" style="color: #000080;"></i>Nom Clinique/Cabinet</label>
        <input type="text" name="clinic" class="form-control form-control-lg" required>
      </div>
      <div class="mb-3 row g-2">
        <div class="col-12 col-md-6">
          <label class="form-label small"><i class="fas fa-calendar-alt me-2" style="color: #FF69B4;"></i>Date de création (Clinique)</label> {# Updated label #}
          <input type="date" name="clinic_creation_date" class="form-control form-control-lg" required> {# Updated name #}
        </div>
        <div class="col-12 col-md-6">
          <label class="form-label small"><i class="fas fa-map-marker-alt me-2" style="color: #28A745;"></i>Adresse</label>
          <input type="text" name="address" class="form-control form-control-lg" required>
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-phone me-2" style="color: #17A2B8;"></i>Téléphone (Whatsapp)</label>
        <input type="tel" name="phone" class="form-control form-control-lg" placeholder="ex :+212XXXXXXXXX" required pattern="^\\+\\d{9,}$">
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
    function copyToClipboard(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            Swal.fire({ icon: 'success', title: 'Copié!', text: 'Détails du compte copiés.', timer: 1500, showConfirmButton: false });
        } catch (err) {
            Swal.fire({ icon: 'error', title: 'Erreur!', text: 'Échec de la copie.', timer: 1500, showConfirmButton: false });
        }
        document.body.removeChild(textarea);
    }

    document.addEventListener('DOMContentLoaded', function() {
        const newUserDetails = {{ new_user_details | tojson | safe }};
        const registrationSuccess = {{ registration_success | tojson | safe }};

        if (registrationSuccess && newUserDetails) {
            const detailsHtml = `
                <p>Votre compte administrateur a été créé avec succès !</p>
                <p>Veuillez conserver précieusement ces informations.</p>
                <div style="text-align: left; background: #f0f0f0; padding: 10px; border-radius: 5px; margin-top: 15px; font-family: monospace;" id="accountDetails">
                    <strong>Email:</strong> ${newUserDetails.email}<br>
                    <strong>Nom Clinique:</strong> ${newUserDetails.clinic}<br>
                    <strong>Date création:</strong> ${newUserDetails.creation_date}<br>
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
                confirmButtonText: 'OK',
                didOpen: () => {
                    document.getElementById('copyDetailsBtn').addEventListener('click', () => {
                        copyToClipboard(document.getElementById('accountDetails').innerText);
                    });
                }
            }).then(() => {
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
    body { background:#f0fafe; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; }
    .contact-info { margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee; text-align: center; }
    .signature { margin-top: 20px; text-align: center; font-size: 0.8rem; color: #777; }
    .app-icon { width: 100px; height: 100px; margin-bottom: 20px; border-radius: 20%; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
  </style>
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100 p-3">
  <div class="card p-4 shadow w-100" style="max-width: 400px;">
    <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon mx-auto d-block">
    <h3 class="text-center mb-3"><i class="fas fa-redo-alt" style="color: #1a73e8;"></i> Réinitialiser mot de passe</h3>
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat,msg in msgs %}<div class="alert alert-{{cat}} small">{{msg}}</div>{% endfor %}
    {% endwith %}
    <form method="POST">
      <div class="mb-3 row g-2">
        <div class="col-12 col-md-6">
          <label class="form-label small"><i class="fas fa-key me-2" style="color: #E91E63;"></i>Nouveau mot de passe</label>
          <input type="password" name="password" class="form-control form-control-lg" required>
        </div>
        <div class="col-12 col-md-6">
          <label class="form-label small"><i class="fas fa-key me-2" style="color: #E91E63;"></i>Confirmer</label>
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
    body { background:#f0fafe; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; }
    .contact-info { margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee; text-align: center; }
    .signature { margin-top: 20px; text-align: center; font-size: 0.8rem; color: #777; }
    .app-icon { width: 100px; height: 100px; margin-bottom: 20px; border-radius: 20%; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
  </style>
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100 p-3">
  <div class="card p-4 shadow w-100" style="max-width: 400px;">
    <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon mx-auto d-block">
    <h3 class="text-center mb-3"><i class="fas fa-unlock-alt" style="color: #FFC107;"></i>Récupération</h3>
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat,msg in msgs %}<div class="alert alert-{{cat}} small">{{msg}}</div>{% endfor %}
    {% endwith %}
    <form method="POST">
      <div class="mb-3"><label class="form-label small"><i class="fas fa-envelope me-2" style="color: #FF5722;"></i>Email</label><input type="email" name="email" class="form-control form-control-lg" required></div>
      <div class="mb-3"><label class="form-label small"><i class="fas fa-hospital-symbol me-2" style="color: #000080;"></i>Nom Clinique</label><input type="text" name="clinic" class="form-control form-control-lg" required></div>
      <div class="mb-3"><label class="form-label small"><i class="fas fa-calendar-alt me-2" style="color: #FF69B4;"></i>Date de création</label><input type="date" name="creation_date" class="form-control form-control-lg" required></div>
      <div class="mb-3"><label class="form-label small"><i class="fas fa-map-marker-alt me-2" style="color: #28A745;"></i>Adresse</label><input type="text" name="address" class="form-control form-control-lg" required></div>
      <div class="mb-3"><label class="form-label small"><i class="fas fa-phone me-2" style="color: #17A2B8;"></i>Téléphone</label><input type="tel" name="phone" class="form-control form-control-lg" placeholder="ex :+212XXXXXXXXX" required pattern="^\\+\\d{9,}$"></div>
      <button type="submit" class="btn btn-medical btn-lg w-100">Valider</button>
    </form>
    <div class='contact-info'>
        <p>Besoin d'aide ? Contactez-nous :</p>
        <a href='mailto:sastoukadigital@gmail.com' class='btn btn-outline-info'><i class='fas fa-envelope'></i> Email</a>
        <a href='https://wa.me/212652084735' class='btn btn-outline-success' target='_blank'><i class='fab fa-whatsapp'></i> WhatsApp</a>
    </div>
  </div>
  <div class="signature">Développé par SastoukaDigital</div>
</body>
</html>
'''