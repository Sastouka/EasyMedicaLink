# login.py
# Description: Gère l'authentification, l'enregistrement, la récupération et le changement de mot de passe.
# Version finale avec toutes les corrections appliquées.

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
from flask_mail import Message

import utils
from activation import TRIAL_DAYS, get_hardware_id

# --- Configuration et Constantes ---
login_bp = Blueprint("login", __name__)
USERS_FILE: Optional[Path] = None
PENDING_REGISTRATIONS_FILE: Optional[Path] = None
HMAC_KEY = b"votre_cle_secrete_interne_a_remplacer" 

ALL_BLUEPRINTS = [
    'accueil', 'rdv', 'facturation', 'biologie', 'radiologie', 'pharmacie',
    'comptabilite', 'statistique', 'administrateur_bp', 'developpeur_bp',
    'patient_rdv', 'routes', 'gestion_patient', 'guide', 'ia_assitant'
]

# --- Fonctions d'envoi d'e-mail ---

def send_welcome_email(recipient_email: str):
    """Envoie un e-mail de bienvenue et de confirmation après l'enregistrement."""
    from app import mail
    try:
        if current_app.debug:
            base_url = f"http://{lan_ip()}:3000"
        else:
            base_url = os.environ.get('APP_BASE_URL')
            if not base_url:
                print("🔥 ERREUR CRITIQUE : APP_BASE_URL n'est pas définie pour le mode production !")
                base_url = ""

        icon_url = f"{base_url}/static/pwa/icon-512.png"
        login_url = f"{base_url}{url_for('login.login')}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f7f6; }}
                .container {{ width: 100%; max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }}
                .header {{ background-color: #e3f2fd; text-align: center; padding: 20px; }}
                .header img {{ width: 80px; height: 80px; }}
                .content {{ padding: 30px; color: #333; line-height: 1.6; }}
                .content h1 {{ color: #0d47a1; }}
                .button {{ display: inline-block; background-color: #1a73e8; color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 20px; }}
                .footer {{ font-size: 0.8em; text-align: center; color: #777; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <img src="{icon_url}" alt="EasyMedicalink Logo">
                </div>
                <div class="content">
                    <h1>Bienvenue sur EasyMedicalink !</h1>
                    <p>Bonjour,</p>
                    <p>Votre compte a été créé avec succès. Nous sommes ravis de vous compter parmi nous.</p>
                    <p>EasyMedicalink est une solution complète conçue pour simplifier la gestion de votre cabinet médical, optimiser vos rendez-vous et améliorer le suivi de vos patients.</p>
                    <p>Pour commencer, cliquez sur le bouton ci-dessous pour accéder à votre espace :</p>
                    <a href="{login_url}" style="background: linear-gradient(45deg, #20c997, #0d9488); color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; margin-top: 20px;">Accéder à mon compte</a>
                </div>
                <div class="footer">
                    <p>&copy; {date.today().year} EasyMedicalink. Tous droits réservés.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = Message(
            subject="Bienvenue ! Votre compte EasyMedicalink est prêt.",
            sender=("EasyMedicalink", current_app.config['MAIL_USERNAME']),
            recipients=[recipient_email],
            html=html_body
        )
        mail.send(msg)
        print(f"E-mail de bienvenue envoyé à {recipient_email}")
    except Exception as e:
        print(f"ERREUR CRITIQUE: Échec de l'envoi de l'e-mail de bienvenue : {e}")
        flash("Votre compte a été créé, mais l'envoi de l'e-mail de bienvenue a échoué.", "warning")

def send_registration_link_email(email: str, token: str):
    """Envoie un e-mail avec un lien pour finaliser l'enregistrement."""
    from app import mail
    try:
        if current_app.debug:
            base_url = f"http://{lan_ip()}:3000"
        else:
            base_url = os.environ.get('APP_BASE_URL')
            if not base_url:
                print("🔥 ERREUR CRITIQUE : APP_BASE_URL n'est pas définie pour le mode production !")
                return

        relative_url = url_for('login.complete_registration', token=token)
        completion_url = f"{base_url}{relative_url}"
        
        print(f"Génération du lien de finalisation d'enregistrement : {completion_url}")

        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2>Finalisez votre inscription EasyMedicalink</h2>
                <p>Cliquez sur le lien ci-dessous pour terminer la création de votre compte. Ce lien expirera dans 24 heures.</p>
                <p style="text-align: center; margin-top: 20px; margin-bottom: 20px;">
                    <a href="{completion_url}" style="background-color: #1a73e8; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Terminer mon inscription
                    </a>
                </p>
                <p>Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail.</p>
            </body>
        </html>
        """
        msg = Message(
            subject="Finalisez votre inscription EasyMedicalink",
            sender=("EasyMedicalink", current_app.config['MAIL_USERNAME']),
            recipients=[email],
            html=html_body
        )
        mail.send(msg)
        print(f"E-mail de finalisation d'inscription envoyé à {email}")
    except Exception as e:
        print(f"ERREUR CRITIQUE: Échec de l'envoi de l'e-mail de finalisation : {e}")
        flash("Une erreur est survenue lors de l'envoi de l'e-mail. Veuillez réessayer.", "danger")

def send_password_reset_email(email: str, token: str):
    """Envoie un e-mail avec le lien de réinitialisation de mot de passe."""
    from app import mail
    try:
        if current_app.debug:
            base_url = f"http://{lan_ip()}:3000"
            mode = "Local (Debug)"
        else:
            base_url = os.environ.get('APP_BASE_URL')
            mode = "Production"
            if not base_url:
                print("🔥 ERREUR CRITIQUE : APP_BASE_URL n'est pas définie pour le mode production !")
                return

        relative_url = url_for('login.reset_password', token=token)
        reset_url = f"{base_url}{relative_url}"
        
        print(f"Génération du lien de réinitialisation ({mode}) : {reset_url}")

        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2>Réinitialisation de votre mot de passe</h2>
                <p>Cliquez sur le lien ci-dessous pour choisir un nouveau mot de passe. Ce lien expirera dans 1 heure.</p>
                <p>Si le lien n'est pas cliquable, copiez et collez cette adresse dans votre navigateur : {reset_url}</p>
                <p style="text-align: center; margin-top: 20px; margin-bottom: 20px;">
                    <a href="{reset_url}" style="background-color: #1a73e8; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Réinitialiser mon mot de passe
                    </a>
                </p>
                <p>Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail.</p>
            </body>
        </html>
        """
        msg = Message(
            subject="Instructions pour réinitialiser votre mot de passe EasyMedicalink",
            sender=("EasyMedicalink", current_app.config['MAIL_USERNAME']),
            recipients=[email],
            html=html_body
        )
        mail.send(msg)
        print(f"E-mail de réinitialisation envoyé à {email}")
    except Exception as e:
        print(f"ERREUR CRITIQUE: Échec de l'envoi de l'e-mail de réinitialisation : {e}")
        flash("Une erreur est survenue lors de l'envoi de l'e-mail. Veuillez réessayer.", "danger")

# --- Gestion des Fichiers et Chemins ---
def _set_login_paths():
    global USERS_FILE, PENDING_REGISTRATIONS_FILE
    if USERS_FILE and PENDING_REGISTRATIONS_FILE:
        return
    try:
        medicalink_data_root = Path(utils.application_path) / "MEDICALINK_DATA"
        medicalink_data_root.mkdir(parents=True, exist_ok=True)
        if platform.system() == "Windows":
            ctypes.windll.kernel32.SetFileAttributesW(str(medicalink_data_root), 0x02)
    except Exception as e:
        print(f"AVERTISSEMENT: Impossible de masquer le dossier MEDICALINK_DATA: {e}")
    USERS_FILE = medicalink_data_root / ".users.json"
    PENDING_REGISTRATIONS_FILE = medicalink_data_root / ".pending_registrations.json"

# --- Sécurité et Hachage ---
def _sign(data: bytes) -> str:
    return hmac.new(HMAC_KEY, data, hashlib.sha256).hexdigest()
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()
def generate_reset_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)

# --- Lecture et Écriture des Données ---
def _load_data_from_file(file_path: Optional[Path]) -> Dict[str, Any]:
    _set_login_paths()
    if not file_path or not file_path.exists():
        return {}
    try:
        raw_content = file_path.read_bytes()
        payload, signature = raw_content.rsplit(b"\n---SIGNATURE---\n", 1)
        if not hmac.compare_digest(_sign(payload), signature.decode()):
            print(f"ERREUR FATALE: L'intégrité du fichier {file_path} est compromise !")
            return {}
        return json.loads(payload.decode("utf-8"))
    except Exception as e:
        print(f"ERREUR lors de la lecture de {file_path}: {e}")
    return {}
def _save_data_to_file(data: Dict[str, Any], file_path: Optional[Path]):
    _set_login_paths()
    if not file_path:
        print(f"ERREUR: Chemin de fichier non défini. Sauvegarde annulée.")
        return
    try:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        signature = _sign(payload).encode()
        file_path.write_bytes(payload + b"\n---SIGNATURE---\n" + signature)
    except Exception as e:
        print(f"ERREUR: Échec de la sauvegarde dans {file_path}: {e}")
def load_users() -> Dict[str, Any]:
    return _load_data_from_file(USERS_FILE)
def save_users(users: Dict[str, Any]):
    _save_data_to_file(users, USERS_FILE)
def load_pending_registrations() -> Dict[str, Any]:
    return _load_data_from_file(PENDING_REGISTRATIONS_FILE)
def save_pending_registrations(pending_data: Dict[str, Any]):
    _save_data_to_file(pending_data, PENDING_REGISTRATIONS_FILE)

# --- Fonctions Utilitaires ---
def lan_ip() -> str:
    ip = socket.gethostbyname(socket.gethostname())
    if ip.startswith("127."):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]
        except Exception:
            ip = "0.0.0.0"
    return ip
def _find_user_in_centralized_users_file(target_email: str, target_password_hash: str) -> Optional[Dict]:
    user = load_users().get(target_email)
    if user and user.get("password") == target_password_hash:
        return {"user_data": user, "admin_owner_email": user.get("owner", target_email), "actual_role": user.get("role", "admin")}
    return None
def _is_email_globally_unique(email_to_check: str) -> bool:
    return email_to_check not in load_users()

# --- Routes du Blueprint ---
@login_bp.route("/login", methods=["GET", "POST"])
def login():
    _set_login_paths()
    if request.method == "POST":
        email = request.form["email"].lower().strip()
        pwd_hash = hash_password(request.form["password"])
        selected_role = request.form.get("role_select")
        
        found_user_info = _find_user_in_centralized_users_file(email, pwd_hash)

        if found_user_info:
            actual_role = found_user_info["actual_role"]
            is_pharmacy_role_match = (selected_role == 'pharmacie/magasin' and actual_role == 'pharmacie')

            if selected_role != actual_role and not is_pharmacy_role_match:
                flash("Le rôle sélectionné est incorrect pour cet utilisateur.", "danger")
                return redirect(url_for('login.login'))

            if not found_user_info["user_data"].get("active", True):
                flash("Votre compte est inactif. Veuillez contacter le propriétaire de l'application.", "danger")
                return redirect(url_for("activation.activation"))

            session["email"] = email
            session["role"] = actual_role
            session["admin_email"] = found_user_info["admin_owner_email"]
            session.permanent = True

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
        
        flash("Identifiants invalides.", "danger")

    static_folder = current_app.static_folder
    contents = os.listdir(static_folder) if os.path.exists(static_folder) else []
    win64 = next((f for f in contents if f.startswith('EasyMedicaLink-Win64.exe')), None)
    win32 = next((f for f in contents if f.startswith('EasyMedicaLink-Win32.exe')), None)

    return render_template_string(login_template, url_lan=f"http://{lan_ip()}:3000", win64_filename=win64, win32_filename=win32)

@login_bp.route("/register", methods=["GET", "POST"])
def register():
    _set_login_paths()
    if request.method == "POST":
        email = request.form["email"].lower().strip()
        if not _is_email_globally_unique(email):
            flash(f"L'adresse e-mail '{email}' est déjà utilisée par un compte actif.", "danger")
            return redirect(url_for('login.register'))
            
        pending = load_pending_registrations()
        if email in pending and datetime.now() < datetime.fromisoformat(pending[email]['expiry']):
             flash("Un lien d'enregistrement a déjà été envoyé à cette adresse. Veuillez vérifier votre boîte de réception.", "info")
             return redirect(url_for('login.login'))
             
        token, expiry = generate_reset_token(), (datetime.now() + timedelta(hours=24)).isoformat()
        
        pending[email] = {"token": token, "expiry": expiry}
        save_pending_registrations(pending)
        send_registration_link_email(email, token)
        
        flash(f"Étape 1 terminée ! Un e-mail a été envoyé à {email}. Veuillez cliquer sur le lien dans cet e-mail pour continuer.", "success")
        return redirect(url_for('login.login'))
        
    return render_template_string(register_start_template)

@login_bp.route("/register/complete/<token>", methods=["GET", "POST"])
def complete_registration(token):
    _set_login_paths()
    pending = load_pending_registrations()
    email_found, registration_data = None, None
    for email, data in pending.items():
        if data.get('token') == token:
            email_found, registration_data = email, data
            break
            
    if not registration_data:
        flash("Ce lien d'enregistrement est invalide ou a déjà été utilisé.", "danger")
        return redirect(url_for('login.register'))

    if datetime.now() > datetime.fromisoformat(registration_data.get('expiry')):
        pending.pop(email_found, None)
        save_pending_registrations(pending)
        flash("Votre lien d'enregistrement a expiré. Veuillez recommencer.", "danger")
        return redirect(url_for('login.register'))

    if request.method == "POST":
        f = request.form
        phone = f["phone"].strip()

        if f["password"] != f["confirm"]:
            flash("Les mots de passe ne correspondent pas.", "danger")
        elif not phone.startswith('+') or len(phone) < 10:
            flash("Le numéro de téléphone est invalide.", "danger")
        else:
            users = load_users()
            creation_date = f["clinic_creation_date"]
            
            users[email_found] = {
                "password": hash_password(f["password"]), "role": "admin", "clinic": f["clinic"],
                "clinic_creation_date": creation_date, "account_creation_date": date.today().isoformat(),
                "address": f["address"], "phone": phone, "active": True, "owner": email_found,
                "allowed_pages": ALL_BLUEPRINTS,
                "account_limits": {"medecin":0, "assistante":0, "comptable":0, "biologiste":0, "radiologue":0, "pharmacie":0},
                "activation": {"plan": f"essai_{TRIAL_DAYS}jours", "activation_date": date.today().isoformat(), "activation_code": "0000-0000-0000-0000"}
            }
            save_users(users)
            
            pending.pop(email_found, None)
            save_pending_registrations(pending)
            
            send_welcome_email(email_found)
            
            flash(f"Compte créé avec succès ! Un e-mail de bienvenue a été envoyé à {email_found}.", "success")
            return redirect(url_for('login.login'))
            
    return render_template_string(register_template, email=email_found, token=token)

@login_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    _set_login_paths()
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        users = load_users()
        if email in users:
            token, expiry = generate_reset_token(), (datetime.now() + timedelta(hours=1)).isoformat()
            users[email]['reset_token'], users[email]['reset_expiry'] = token, expiry
            save_users(users)
            send_password_reset_email(email, token)

        flash("Si un compte correspondant à cet e-mail existe, un lien de réinitialisation a été envoyé.", 'info')
        return redirect(url_for('login.login'))

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
                return redirect(url_for('accueil.accueil'))
            else:
                flash('Utilisateur non trouvé.', 'danger')

    return render_template_string(reset_template)

@login_bp.route('/logout')
def logout():
    session.clear()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for('login.login'))


# --- TEMPLATES HTML ---
login_template = '''
<!DOCTYPE html><html lang='fr'>
{{ pwa_head()|safe }}
<head>
  <meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>Connexion - EasyMedicalink</title>
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
      padding-top: 2rem;
      padding-bottom: 2rem;
    }
    .card {
      border-radius: 20px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.1);
      border: none;
      overflow: hidden;
      animation: fadeInUp 0.6s ease-out;
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(10px);
      max-width: 480px;
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
    .app-icon { width: 100px; height: 100px; margin-bottom: 20px; border-radius: 20%; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .pwa-install-banner {
        background-color: #e3f2fd;
        border: 1px solid #1a73e8;
        border-radius: 12px;
        padding: 1rem;
    }
    .trust-signal h5 { font-size: 1rem; }
    .trust-signal p { font-size: 0.85rem; }
    .footer-links {
        font-size: 0.8rem;
        color: #6c757d;
    }
    .footer-links a {
        color: #6c757d;
        text-decoration: none;
    }
    .footer-links a:hover {
        text-decoration: underline;
    }
    .journal-grid .journal-logo {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 60px; /* Adjust height as needed */
      width: 100%;
      border: 1px solid #f0f0f0;
      border-radius: 8px;
      transition: all 0.2s ease-in-out;
      text-decoration: none;
      color: #333;
      font-size: 1rem;
      font-weight: bold;
      box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .journal-grid a:hover .journal-logo {
      transform: scale(1.05);
      box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .journal-grid .pubmed-logo { font-size: 1.2rem; }
    .journal-grid .google-scholar-logo { color: #4285F4; }
    .journal-grid .lancet-logo { color: #0070c0; }
    .journal-grid .nejm-logo { font-size: 0.9rem; }
    .journal-grid .jama-logo { color: #8C1C1C; }
    .journal-grid .bmj-logo { color: #5B84B1; }
    .journal-grid .nature-med-logo { color: #008000; font-size: 0.9rem; }
    .journal-grid .presse-med-logo { font-size: 0.7rem; }
    .journal-grid .quotidien-med-logo { font-size: 0.8rem; }
    .journal-grid .revue-prat-logo { font-size: 0.7rem; }
    .journal-grid .nejm-jw-logo { font-size: 0.8rem; }
    .journal-grid .who-logo { font-size: 1.2rem; }
    .journal-grid .cell-logo { color: #1a73e8; }
    .journal-grid .annals-logo { font-size: 0.7rem; }
    .journal-grid .ejph-logo { font-size: 0.7rem; }
  </style>
</head>
<body class='p-3'>
  <div class='card p-4'>
    <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon mx-auto d-block">

    <h3 class='text-center mb-4 fw-bold'>
      <i class='fas fa-user-lock me-2' style="color: #1a73e8;"></i>Connexion
    </h3>
    
    <div id="pwa-install-banner" class="pwa-install-banner mb-3 d-none">
        <div class="d-flex align-items-center">
            <div class="flex-grow-1">
                <h5 class="mb-1" style="color: #1a73e8;"><i class="fas fa-rocket me-2"></i>Accès rapide</h5>
                <p class="mb-0 small">Installez l'application pour une meilleure expérience.</p>
            </div>
            <button id="pwa-install-button" class="btn btn-gradient ms-3 flex-shrink-0">Installer</button>
        </div>
    </div>

    {% with m=get_flashed_messages(with_categories=true) %}
      {% for c,msg in m %}
      <div class='alert alert-{{c}} small'>{{msg}}</div>
      {% endfor %}
    {% endwith %}

    <form method='POST'>
      <div class='mb-3'>
        <label class='form-label small text-muted'><i class='fas fa-users-cog me-1'></i> Rôle</label>
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
        <label class='form-label small text-muted'><i class='fas fa-envelope me-1'></i> Email</label>
        <input name='email' type='email' class='form-control form-control-lg shadow-sm'>
      </div>
      <div class='mb-4'>
        <label class='form-label small text-muted'><i class='fas fa-key me-1'></i> Mot de passe</label>
        <input name='password' type='password' class='form-control form-control-lg shadow-sm'>
      </div>
      <button class='btn btn-gradient btn-lg w-100 py-3 fw-bold'>Se connecter</button>
    </form>
    
    <div class='d-flex gap-3 my-4 flex-column flex-md-row'>
        <div class='text-center flex-fill'><canvas id='qrLocal' width='120' height='120'></canvas><div class='small mt-2 text-muted'>Accès Web</div></div>
        <div class='text-center flex-fill'><canvas id='qrLan' width='120' height='120'></canvas><div class='small mt-2 text-muted'>Réseau local</div></div>
    </div>

    <div class='d-flex flex-column gap-2 mt-3'>
        <a href='{{ url_for("login.register") }}' class='btn btn-outline-primary flex-fill py-2'><i class='fas fa-user-plus me-1'></i> Créer un compte</a>
        <a href='{{ url_for("login.forgot_password") }}' class='btn btn-outline-secondary flex-fill py-2'><i class='fas fa-unlock-alt me-1'></i> Récupération</a>
    </div>
    
    {% if win64_filename or win32_filename %}
    <div class='text-center mt-3'>
        <div class="alert alert-info small text-center mb-3">
          <i class="fas fa-desktop me-2"></i>
          Pour une expérience locale sur PC Windows, téléchargez notre application.
        <div class='d-flex gap-2 justify-content-center'>
          {% if win64_filename %}
          <a href="{{ url_for('static', filename=win64_filename) }}" class='btn btn-gradient text-white text-decoration-none'><i class='fas fa-download me-1'></i> Windows 64-bit</a>
          {% endif %}
          {% if win32_filename %}
          <a href="{{ url_for('static', filename=win32_filename) }}" class='btn btn-gradient text-white text-decoration-none'><i class='fas fa-download me-1'></i> Windows 32-bit</a>
          {% endif %}
        </div>
    </div>
    {% endif %}

    <div class='mt-4 pt-4 border-top'>
        <h4 class='text-center mb-3 fw-bold'>Nos Engagements</h4>
        <div class='row text-center trust-signal'>
            <div class='col-12 col-md-4 mb-3'>
                <h5><i class='fas fa-shield-alt text-primary mb-2'></i> Sécurité</h5>
                <p class='small text-muted'>Données chiffrées, sauvegardes quotidiennes.</p>
            </div>
            <div class='col-12 col-md-4 mb-3'>
                <h5><i class='fas fa-headset text-success mb-2'></i> Support</h5>
                <p class='small text-muted'>Profitez de l'essai gratuit et contactez-nous par Email ou WhatsApp.</p>
            </div>
            <div class='col-12 col-md-4 mb-3'>
                <h5><i class='fas fa-cogs text-info mb-2'></i> Évolution</h5>
                <p class='small text-muted'>Mises à jour régulières pour répondre à vos besoins.</p>
            </div>
        </div>
    </div>

    <div class='text-center pt-3 border-top'>
        <h4 class='text-center mb-3 fw-bold'>Recommandé par nos utilisateurs</h4>
        <div id="testimonialCarousel" class="carousel slide" data-bs-ride="carousel">
            <div class="carousel-inner">
                
                <div class="carousel-item active" data-bs-interval="5000">
                    <div class='mb-2'>
                        <i class='fas fa-star' style='color: #FFC107;'></i><i class='fas fa-star' style='color: #FFC107;'></i><i class='fas fa-star' style='color: #FFC107;'></i><i class='fas fa-star' style='color: #FFC107;'></i><i class='fas fa-star' style='color: #FFC107;'></i>
                    </div>
                    <p class='text-muted small fst-italic'>"Un outil intuitif qui a transformé la gestion de mon cabinet. Je gagne un temps précieux chaque jour !"</p>
                    <p class="fw-bold small mb-0">- Dr. Amadou</p>
                </div>

                <div class="carousel-item" data-bs-interval="5000">
                    <div class='mb-2'>
                        <i class='fas fa-star' style='color: #FFC107;'></i><i class='fas fa-star' style='color: #FFC107;'></i><i class='fas fa-star' style='color: #FFC107;'></i><i class='fas fa-star' style='color: #FFC107;'></i><i class='fas fa-star' style='color: #FFC107;'></i>
                    </div>
                    <p class='text-muted small fst-italic'>"La fonctionnalité de facturation est simple et efficace. Mes assistantes l'adorent."</p>
                    <p class="fw-bold small mb-0">- Dr. Fatou</p>
                </div>

                <div class="carousel-item" data-bs-interval="5000">
                    <div class='mb-2'>
                        <i class='fas fa-star' style='color: #FFC107;'></i><i class='fas fa-star' style='color: #FFC107;'></i><i class='fas fa-star' style='color: #FFC107;'></i><i class='fas fa-star' style='color: #FFC107;'></i><i class='fas fa-star' style='color: #FFC107;'></i>
                    </div>
                    <p class='text-muted small fst-italic'>"Indispensable pour le suivi de mes patients. Accessible et très complet."</p>
                    <p class="fw-bold small mb-0">- Dr. Karim</p>
                </div>
            </div>
        </div>
    </div>
    
    <div class='mt-4 pt-4 border-top'>
        <h4 class='text-center mb-3 fw-bold'>Accéder aux Revues et Publications</h4>
        <div class="container journal-grid">
            <div class="row row-cols-3 row-cols-md-4 g-2 g-md-3 justify-content-center">
                <div class="col text-center">
                    <a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank">
                        <span class="journal-logo pubmed-logo">PubMed</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://scholar.google.com/" target="_blank">
                        <span class="journal-logo google-scholar-logo">Scholar</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://www.thelancet.com/" target="_blank">
                        <span class="journal-logo lancet-logo">Lancet</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://www.nejm.org/" target="_blank">
                        <span class="journal-logo nejm-logo">NEJM</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://jamanetwork.com/" target="_blank">
                        <span class="journal-logo jama-logo">JAMA</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://www.bmj.com/" target="_blank">
                        <span class="journal-logo bmj-logo">BMJ</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://www.nature.com/nm/" target="_blank">
                        <span class="journal-logo nature-med-logo">Nature Medicine</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://www.sciencedirect.com/journal/la-presse-medicale" target="_blank">
                        <span class="journal-logo presse-med-logo">La Presse Médicale</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://www.lequotidiendumedecin.fr/" target="_blank">
                        <span class="journal-logo quotidien-med-logo">Le Quotidien du Médecin</span>
                    </a>
                </div>
                 <div class="col text-center">
                    <a href="https://www.larevuedupraticien.fr/" target="_blank">
                        <span class="journal-logo revue-prat-logo">Revue du Praticien</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://www.nejm.org/journal-watch" target="_blank">
                        <span class="journal-logo nejm-jw-logo">NEJM Journal Watch</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://www.who.int/fr" target="_blank">
                        <span class="journal-logo who-logo">OMS</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://www.cell.com/" target="_blank">
                        <span class="journal-logo cell-logo">Cell</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://journals.lww.com/annals-of-internal-medicine/pages/default.aspx" target="_blank">
                        <span class="journal-logo annals-logo">Annals of Internal Medicine</span>
                    </a>
                </div>
                <div class="col text-center">
                    <a href="https://www.ephjournal.com/" target="_blank">
                        <span class="journal-logo ejph-logo">European Journal of Public Health</span>
                    </a>
                </div>
            </div>
        </div>
    </div>
    <div class='contact-info'>
        <p>Contactez-nous: sastoukadigital@gmail.com | +212652084735</p>
        <a href='mailto:sastoukadigital@gmail.com' class='btn btn-outline-info'><i class='fas fa-envelope'></i> Email</a>
        <a href='https://wa.me/212652084735' class='btn btn-outline-success' target='_blank'><i class='fab fa-whatsapp'></i> WhatsApp</a>
    </div>
  </div>
  
  <div class="text-center mt-3 footer-links">
    <span>Développé par SastoukaDigital</span>
  </div>

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
        if (installBanner) { installBanner.classList.add('d-none'); }
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            if (installBanner) { installBanner.classList.remove('d-none'); }
        });
        if (installButton) {
            installButton.addEventListener('click', async () => {
                if (deferredPrompt) {
                    deferredPrompt.prompt();
                    await deferredPrompt.userChoice;
                    deferredPrompt = null;
                    if (installBanner) { installBanner.classList.add('d-none'); }
                }
            });
        }
    });
  </script>
  {% include '_floating_assistant.html' %}
</body>
</html>
'''

register_start_template = '''
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Créer un compte - Étape 1</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
  <style>
    .btn-medical { background: linear-gradient(45deg,#1a73e8,#0d9488); color:white; }
    body { background:#f0fafe; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; }
    .app-icon { width: 100px; height: 100px; margin-bottom: 20px; border-radius: 20%; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
  </style>
</head>
<body class="d-flex flex-column align-items-center justify-content-center min-vh-100 p-3">
  <div class="card p-4 shadow w-100" style="max-width: 420px;">
    <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon mx-auto d-block">
    <h3 class="text-center mb-3"><i class="fas fa-user-plus text-info"></i> Créer un compte</h3>
    <p class="text-center text-muted small mb-3">Veuillez saisir votre adresse e-mail. Nous vous enverrons un lien sécurisé pour finaliser votre inscription.</p>
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat,msg in msgs %}<div class="alert alert-{{cat}} small">{{msg}}</div>{% endfor %}
    {% endwith %}
    <form method="POST">
      <div class="mb-3">
          <label class="form-label small"><i class="fas fa-envelope me-2"></i>Adresse e-mail</label>
          <input type="email" name="email" class="form-control form-control-lg" required>
      </div>
      <button type="submit" class="btn btn-medical btn-lg w-100">Envoyer le lien d'inscription</button>
    </form>
     <div class="text-center mt-3">
      <a href="{{ url_for('login.login') }}" class="btn btn-sm btn-outline-secondary"><i class="fas fa-arrow-left me-1"></i> Retour à la connexion</a>
    </div>
  </div>
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
  <title>Finaliser l'inscription - EasyMedicalink</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
  <style>
    .btn-medical { background: linear-gradient(45deg,#1a73e8,#0d9488); color:white; }
    body { background:#f0fafe; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; }
    .app-icon { width: 100px; height: 100px; margin-bottom: 20px; border-radius: 20%; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
  </style>
</head>
<body class="d-flex flex-column align-items-center justify-content-center min-vh-100 p-3">
  <div class="card p-4 shadow w-100" style="max-width: 480px;">
    <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon mx-auto d-block">
    <h3 class="text-center mb-3"><i class="fas fa-user-plus text-info"></i> Finaliser l'inscription</h3>
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat,msg in msgs %}<div class="alert alert-{{cat}} small">{{msg}}</div>{% endfor %}
    {% endwith %}
    <form id="registerForm" method="POST">
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-envelope me-2"></i>Email (vérifié)</label>
        <input type="email" name="email" class="form-control form-control-lg" value="{{ email }}" readonly>
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
        <label class="form-label small"><i class="fas fa-hospital-symbol me-2"></i>Nom Clinique/Cabinet</label>
        <input type="text" name="clinic" class="form-control form-control-lg" required>
      </div>
      <div class="mb-3 row g-2">
        <div class="col-12 col-md-6">
          <label class="form-label small"><i class="fas fa-calendar-alt me-2"></i>Date de création (Clinique)</label>
          <input type="date" name="clinic_creation_date" class="form-control form-control-lg" required>
        </div>
        <div class="col-12 col-md-6">
          <label class="form-label small"><i class="fas fa-map-marker-alt me-2"></i>Adresse</label>
          <input type="text" name="address" class="form-control form-control-lg" required>
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label small"><i class="fas fa-phone me-2"></i>Téléphone (Whatsapp)</label>
        <input type="tel" name="phone" class="form-control form-control-lg" placeholder="ex: +212XXXXXXXXX" required pattern="^\\+\\d{9,}$">
      </div>
      <button type="submit" class="btn btn-medical btn-lg w-100">Finaliser et créer mon compte</button>
    </form>
  </div>
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
    .app-icon { width: 100px; height: 100px; margin-bottom: 20px; border-radius: 20%; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .footer-links { font-size: 0.8rem; color: #6c757d; }
    .footer-links a { color: #6c757d; text-decoration: none; }
    .footer-links a:hover { text-decoration: underline; }
  </style>
</head>
<body class="d-flex flex-column align-items-center justify-content-center min-vh-100 p-3">
  <div class="card p-4 shadow w-100" style="max-width: 400px;">
    <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon mx-auto d-block">
    <h3 class="text-center mb-3"><i class="fas fa-redo-alt text-primary"></i> Réinitialiser</h3>
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat,msg in msgs %}<div class="alert alert-{{cat}} small">{{msg}}</div>{% endfor %}
    {% endwith %}
    <form method="POST">
      <div class="mb-3">
          <label class="form-label small"><i class="fas fa-key me-2"></i>Nouveau mot de passe</label>
          <input type="password" name="password" class="form-control form-control-lg" required>
      </div>
      <div class="mb-3">
          <label class="form-label small"><i class="fas fa-key me-2"></i>Confirmer</label>
          <input type="password" name="confirm" class="form-control form-control-lg" required>
      </div>
      <button type="submit" class="btn btn-medical btn-lg w-100">Mettre à jour</button>
    </form>
  </div>
  <div class="text-center mt-3 footer-links">
    <span>Développé par SastoukaDigital</span>
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
    .app-icon { width: 100px; height: 100px; margin-bottom: 20px; border-radius: 20%; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .footer-links { font-size: 0.8rem; color: #6c757d; }
    .footer-links a { color: #6c757d; text-decoration: none; }
    .footer-links a:hover { text-decoration: underline; }
  </style>
</head>
<body class="d-flex flex-column align-items-center justify-content-center min-vh-100 p-3">
  <div class="card p-4 shadow w-100" style="max-width: 400px;">
    <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon mx-auto d-block">
    <h3 class="text-center mb-3"><i class="fas fa-unlock-alt text-warning"></i> Récupération</h3>
    <p class="text-center text-muted small mb-3">Veuillez saisir l'adresse e-mail de votre compte. Un lien pour réinitialiser votre mot de passe vous sera envoyé.</p>
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat,msg in msgs %}<div class="alert alert-{{cat}} small">{{msg}}</div>{% endfor %}
    {% endwith %}
    <form method="POST">
      <div class="mb-3">
          <label class="form-label small"><i class="fas fa-envelope me-2"></i>Adresse e-mail</label>
          <input type="email" name="email" class="form-control" required>
      </div>
      <button type="submit" class="btn btn-medical btn-lg w-100">Envoyer le lien de récupération</button>
    </form>
     <div class="text-center mt-3">
      <a href="{{ url_for('login.login') }}" class="btn btn-sm btn-outline-secondary"><i class="fas fa-arrow-left me-1"></i> Retour à la connexion</a>
    </div>
  </div>
  <div class="text-center mt-3 footer-links">
    <span>Développé par SastoukaDigital</span>
  </div>
</body>
</html>
'''
