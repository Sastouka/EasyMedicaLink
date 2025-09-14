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
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); text-align: center; padding: 20px; }}
                .header img {{ width: 80px; height: 80px; }}
                .content {{ padding: 30px; color: #333; line-height: 1.6; }}
                .content h1 {{ color: #667eea; }}
                .button {{ display: inline-block; background: linear-gradient(45deg, #20c997, #0d9488); color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 20px; }}
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
                    <a href="{login_url}" class="button">Accéder à mon compte</a>
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
                    <a href="{completion_url}" style="background: linear-gradient(45deg, #667eea, #764ba2); color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
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
                    <a href="{reset_url}" style="background: linear-gradient(45deg, #667eea, #764ba2); color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
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

    return render_template_string(login_template, url_lan=f"http://{lan_ip()}:3000", win64_filename=win64, win32_filename=win32, TRIAL_DAYS=TRIAL_DAYS)

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

# Base CSS and Head for all templates to ensure consistency
base_head_and_style = '''
<head>
  <meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
  {{ pwa_head()|safe }}
  <link rel='preconnect' href='https://fonts.googleapis.com'>
  <link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>
  <link href='https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap' rel='stylesheet'>
  <link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>
  <link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'>
  <style>
    :root {
      --gradient-start: #667eea;
      --gradient-end: #764ba2;
      --web-start: #007bff;
      --web-end: #00d4ff;
      --local-start: #28a745;
      --local-end: #20c997;
      --popular-bg: #ffc107;
      --primary-accent: #667eea;
    }
    body {
      background: linear-gradient(135deg, var(--gradient-start) 0%, var(--gradient-end) 100%);
      font-family: 'Poppins', sans-serif;
      color: #495057;
      min-height: 100vh;
    }
    .container { padding-top: 2rem; padding-bottom: 2rem; }
    .main-card {
      background-color: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(10px);
      border-radius: 20px;
      border: 1px solid rgba(255, 255, 255, 0.2);
      box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
      max-width: 500px;
    }
    .main-card-large { max-width: 960px; }
    .app-icon { width: 80px; height: 80px; margin-bottom: 1rem; border-radius: 20%; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .card-title { color: var(--primary-accent); }
    .btn-gradient {
      font-weight: 600;
      padding: 0.75rem 1rem;
      border-radius: 50px;
      border: none;
      transition: all .3s ease;
      color: white !important;
      background-image: linear-gradient(to right, var(--gradient-start) 0%, var(--gradient-end) 51%, var(--gradient-start) 100%);
      background-size: 200% auto;
      text-decoration: none;
    }
    .btn-gradient:hover { background-position: right center; transform: translateY(-2px); }
    .plan-card {
      border-radius: 15px;
      transition: all .3s ease;
      border: none;
      box-shadow: 0 4px 15px rgba(0,0,0,.1);
      display: flex;
      flex-direction: column;
      position: relative;
      overflow: hidden;
      background-color: #fff;
    }
    .plan-card:hover{
      transform: translateY(-10px);
      box-shadow: 0 10px 25px rgba(0,0,0,.15);
    }
    .plan-card .card-header{
      border-top-left-radius: 15px;
      border-top-right-radius: 15px;
      font-weight: 700;
      color: white;
      padding: 1rem;
    }
    .header-web { background: linear-gradient(45deg, var(--web-start), var(--web-end)); }
    .header-local { background: linear-gradient(45deg, var(--local-start), var(--local-end)); }
    .btn-plan {
      font-weight: 600;
      padding: 0.6rem 1rem;
      border-radius: 50px;
      border: none;
      transition: all .3s ease;
      color: white !important;
      text-decoration: none;
      display: block;
    }
    .btn-web { background-image: linear-gradient(to right, var(--web-start) 0%, var(--web-end) 51%, var(--web-start) 100%); background-size: 200% auto; }
    .btn-local { background-image: linear-gradient(to right, var(--local-start) 0%, var(--local-end) 51%, var(--local-start) 100%); background-size: 200% auto; }
    .btn-plan:hover { background-position: right center; }
    .badge-popular {
      position: absolute;
      top: 15px;
      right: -30px;
      transform: rotate(45deg);
      background-color: var(--popular-bg);
      color: #212529;
      font-weight: bold;
      padding: 1px 30px;
      font-size: 0.7rem;
    }
    .btn-journal {
        display: block; width: 100%;
        padding: 0.5rem 0.25rem;
        border-radius: 50px;
        border: none;
        color: white !important;
        font-weight: 600; font-size: 0.75rem;
        text-align: center; text-decoration: none;
        transition: all .3s ease;
        background-size: 200% auto;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .btn-journal:hover {
        background-position: right center;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .btn-pubmed { background-image: linear-gradient(to right, #2c5282 0%, #319795 51%, #2c5282 100%); }
    .btn-scholar { background-image: linear-gradient(to right, #4285F4 0%, #1a73e8 51%, #4285F4 100%); }
    .btn-lancet { background-image: linear-gradient(to right, #005f6a 0%, #008797 51%, #005f6a 100%); }
    .btn-nejm { background-image: linear-gradient(to right, #007398 0%, #0099cc 51%, #007398 100%); }
    .btn-jama { background-image: linear-gradient(to right, #b22222 0%, #d14747 51%, #b22222 100%); }
    .btn-bmj { background-image: linear-gradient(to right, #006847 0%, #00845a 51%, #006847 100%); }
    .btn-oms { background-image: linear-gradient(to right, #0093d5 0%, #3fa9f5 51%, #0093d5 100%); }
    .btn-qmed { background-image: linear-gradient(to right, #0055a4 0%, #ef4135 51%, #0055a4 100%); }
  </style>
</head>
'''

login_template = f'''
<!DOCTYPE html><html lang='fr'>
{base_head_and_style}
<title>Connexion - EasyMedicalink</title>
<body>
<div class='container'>
<div class='main-card main-card-large mx-auto p-4 p-md-5'>
    <div class='row g-5'>
        <div class='col-lg-5'>
            <div class='text-center'>
                <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon">
                <h3 class='card-title fw-bold'><i class='fas fa-user-lock me-2'></i>Connexion</h3>
            </div>
            
            <div id="pwa-install-banner" class="alert alert-primary small mt-3 d-none">
                <div class="d-flex align-items-center">
                    <div class="flex-grow-1">
                        <h6 class="mb-0 fw-bold"><i class="fas fa-rocket me-2"></i>Accès rapide</h6>
                        <p class="mb-0 small">Installez l'application.</p>
                    </div>
                    <button id="pwa-install-button" class="btn btn-sm btn-primary ms-3 flex-shrink-0">Installer</button>
                </div>
            </div>

            {{% with m=get_flashed_messages(with_categories=true) %}}
              {{% for c,msg in m %}}
              <div class='alert alert-{{{{c}}}} small mt-3'>{{{{msg}}}}</div>
              {{% endfor %}}
            {{% endwith %}}

            <form method='POST' class='mt-3'>
              <div class='mb-3'>
                <label class='form-label small text-muted'><i class='fas fa-users-cog me-1'></i> Rôle</label>
                <select name='role_select' class='form-select form-select-lg'>
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
                <input name='email' type='email' class='form-control form-control-lg'>
              </div>
              <div class='mb-4'>
                <label class='form-label small text-muted'><i class='fas fa-key me-1'></i> Mot de passe</label>
                <input name='password' type='password' class='form-control form-control-lg'>
              </div>
              <button class='btn btn-gradient btn-lg w-100 py-3 fw-bold'>Se connecter</button>
            </form>
            <div class='d-flex flex-column gap-2 mt-3'>
                <a href='{{{{ url_for("login.register") }}}}' class='btn btn-outline-secondary w-100'><i class='fas fa-user-plus me-1'></i> Créer un compte</a>
                <a href='{{{{ url_for("login.forgot_password") }}}}' class='btn btn-link text-muted w-100 small'><i class='fas fa-unlock-alt me-1'></i> Mot de passe oublié ?</a>
            </div>
        </div>

        <div class='col-lg-7'>
            <h3 class='text-center mb-3 fw-bold card-title'>
                <i class='fas fa-rocket me-2'></i>Découvrez Nos Offres
            </h3>
            <p class="text-center text-muted small mb-4">
                Profitez de votre essai gratuit de {{{{ TRIAL_DAYS }}}} jours, puis choisissez un plan pour un accès complet.
            </p>
            <div class='row g-3'>
                <div class='col-md-6 mb-3 mb-md-0'>
                    <div class='plan-card h-100'>
                        <div class='card-header text-center fs-6 header-web'><i class="fas fa-globe me-2"></i>Version Web</div>
                        <div class='card-body d-flex flex-column p-3 text-center'>
                            <p class='small'>Accès universel depuis n'importe quel navigateur.</p>
                            <div class='my-2'><span class="fs-4 fw-bold">$15</span><span class="text-muted small">/mois</span></div>
                            <a href="{{{{ url_for('activation.activation') }}}}" class='btn btn-sm btn-plan btn-web mt-auto'>Choisir 1 Mois</a>
                            <hr class='my-2'>
                            <div class='my-2'><span class="fs-4 fw-bold">$100</span><span class="text-muted small">/an</span></div>
                            <a href="{{{{ url_for('activation.activation') }}}}" class='btn btn-sm btn-plan btn-web mt-auto'>Choisir 1 An</a>
                            <div class="badge-popular">Économie</div>
                        </div>
                    </div>
                </div>
                <div class='col-md-6'>
                    <div class='plan-card h-100'>
                        <div class='card-header text-center fs-6 header-local'><i class="fab fa-windows me-2"></i>Version Locale</div>
                        <div class='card-body d-flex flex-column p-3 text-center'>
                            <p class='small'>Performance maximale sur votre PC Windows.</p>
                            <div class='my-2'><span class="fs-4 fw-bold">$50</span><span class="text-muted small">/an</span></div>
                            <a href="{{{{ url_for('activation.activation') }}}}" class='btn btn-sm btn-plan btn-local mt-auto'>Licence 1 An</a>
                            <hr class='my-2'>
                            <div class='my-2'><span class="fs-4 fw-bold">$120</span><span class="text-muted small">/à vie</span></div>
                            <a href="{{{{ url_for('activation.activation') }}}}" class='btn btn-sm btn-plan btn-local mt-auto'>Licence Illimitée</a>
                            <div class="badge-popular">__  Meilleur Choix</div>
                        </div>
                    </div>
                </div>
            </div>
            
            {{% if win64_filename or win32_filename %}}
            <div class='text-center mt-4 pt-4 border-top'>
                <h5 class='fw-bold card-title'><i class="fab fa-windows"></i> Version Locale</h5>
                <p class="small text-muted mb-3">Pour une expérience optimale sur votre ordinateur, téléchargez l'application.</p>
                <div class='d-flex gap-2 justify-content-center'>
                  {{% if win64_filename %}}
                  <a href="{{{{ url_for('static', filename=win64_filename) }}}}" class='btn btn-sm btn-success'><i class='fas fa-download me-1'></i> Win 64-bit</a>
                  {{% endif %}}
                  {{% if win32_filename %}}
                  <a href="{{{{ url_for('static', filename=win32_filename) }}}}" class='btn btn-sm btn-secondary'><i class='fas fa-download me-1'></i> Win 32-bit</a>
                  {{% endif %}}
                </div>
            </div>
            {{% endif %}}
        </div>
    </div>

    <hr class="my-4">
    <div class='mt-2'>
        <h4 class='text-center mb-3 fw-bold card-title small'>Accès aux Revues et Publications Scientifiques</h4>
        <div class="journal-grid">
            <div class="row row-cols-4 row-cols-md-8 g-2 justify-content-center">
                <div class="col"><a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" class="btn-journal btn-pubmed">PubMed</a></div>
                <div class="col"><a href="https://scholar.google.com/" target="_blank" class="btn-journal btn-scholar">Scholar</a></div>
                <div class="col"><a href="https://www.thelancet.com/" target="_blank" class="btn-journal btn-lancet">Lancet</a></div>
                <div class="col"><a href="https://www.nejm.org/" target="_blank" class="btn-journal btn-nejm">NEJM</a></div>
                <div class="col"><a href="https://jamanetwork.com/" target="_blank" class="btn-journal btn-jama">JAMA</a></div>
                <div class="col"><a href="https://www.bmj.com/" target="_blank" class="btn-journal btn-bmj">BMJ</a></div>
                <div class="col"><a href="https://www.who.int/fr" target="_blank" class="btn-journal btn-oms">OMS</a></div>
                <div class="col"><a href="https://www.lequotidiendumedecin.fr/" target="_blank" class="btn-journal btn-qmed" title="Quotidien du Médecin">Q. Médecin</a></div>
            </div>
        </div>
    </div>
    <div class='mt-4 pt-3 border-top text-center'>
        <p class='text-muted small'>Contact: sastoukadigital@gmail.com | +212652084735</p>
    </div>

</div></div>
  <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
  <script>
    document.addEventListener('DOMContentLoaded', () => {{
        let deferredPrompt;
        const installBanner = document.getElementById('pwa-install-banner');
        const installButton = document.getElementById('pwa-install-button');
        if (installBanner) {{ installBanner.classList.add('d-none'); }}
        window.addEventListener('beforeinstallprompt', (e) => {{
            e.preventDefault();
            deferredPrompt = e;
            if (installBanner) {{ installBanner.classList.remove('d-none'); }}
        }});
        if (installButton) {{
            installButton.addEventListener('click', async () => {{
                if (deferredPrompt) {{
                    deferredPrompt.prompt();
                    await deferredPrompt.userChoice;
                    deferredPrompt = null;
                    if (installBanner) {{ installBanner.classList.add('d-none'); }}
                }}
            }});
        }}
    }});
  </script>
  {{% include '_floating_assistant.html' %}}
</body>
</html>
'''

register_start_template = f'''
<!DOCTYPE html>
<html lang="fr">
{base_head_and_style}
<title>Créer un compte - Étape 1</title>
<body class="d-flex align-items-center">
  <div class="container">
    <div class="main-card mx-auto p-4 p-md-5 text-center">
      <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon mx-auto d-block">
      <h3 class="card-title fw-bold"><i class="fas fa-user-plus me-2"></i> Créer un compte</h3>
      <p class="text-muted small mb-4">Saisissez votre e-mail pour recevoir un lien sécurisé et finaliser votre inscription.</p>
      {{% with msgs = get_flashed_messages(with_categories=true) %}}
        {{% for cat,msg in msgs %}}<div class="alert alert-{{{{cat}}}} small">{{{{msg}}}}</div>{{% endfor %}}
      {{% endwith %}}
      <form method="POST">
        <div class="mb-3">
            <label class="form-label small text-start w-100"><i class="fas fa-envelope me-2"></i>Adresse e-mail</label>
            <input type="email" name="email" class="form-control form-control-lg" required>
        </div>
        <button type="submit" class="btn btn-gradient btn-lg w-100">Envoyer le lien</button>
      </form>
      <div class="mt-3">
        <a href="{{{{ url_for('login.login') }}}}" class="btn btn-sm btn-link text-muted"><i class="fas fa-arrow-left me-1"></i> Retour à la connexion</a>
      </div>
    </div>
  </div>
</body>
</html>
'''

register_template = f'''
<!DOCTYPE html>
<html lang="fr">
{base_head_and_style}
<title>Finaliser l'inscription - EasyMedicalink</title>
<body class="d-flex align-items-center">
  <div class="container">
    <div class="main-card mx-auto p-4 p-md-5">
      <div class="text-center">
        <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon">
        <h3 class="card-title fw-bold"><i class="fas fa-check-circle me-2"></i> Finaliser l'inscription</h3>
      </div>
      {{% with msgs = get_flashed_messages(with_categories=true) %}}
        {{% for cat,msg in msgs %}}<div class="alert alert-{{{{cat}}}} small mt-3">{{{{msg}}}}</div>{{% endfor %}}
      {{% endwith %}}
      <form id="registerForm" method="POST" class="mt-3">
        <div class="mb-3">
          <label class="form-label small"><i class="fas fa-envelope me-2"></i>Email (vérifié)</label>
          <input type="email" name="email" class="form-control" value="{{{{ email }}}}" readonly>
        </div>
        <div class="row g-2 mb-3">
          <div class="col-md-6">
            <label class="form-label small"><i class="fas fa-key me-2"></i>Mot de passe</label>
            <input type="password" name="password" class="form-control" required>
          </div>
          <div class="col-md-6">
            <label class="form-label small"><i class="fas fa-key me-2"></i>Confirmer</label>
            <input type="password" name="confirm" class="form-control" required>
          </div>
        </div>
        <div class="mb-3">
          <label class="form-label small"><i class="fas fa-hospital-symbol me-2"></i>Nom Clinique/Cabinet</label>
          <input type="text" name="clinic" class="form-control" required>
        </div>
        <div class="row g-2 mb-3">
          <div class="col-md-6">
            <label class="form-label small"><i class="fas fa-calendar-alt me-2"></i>Date de création</label>
            <input type="date" name="clinic_creation_date" class="form-control" required>
          </div>
          <div class="col-md-6">
            <label class="form-label small"><i class="fas fa-map-marker-alt me-2"></i>Adresse</label>
            <input type="text" name="address" class="form-control" required>
          </div>
        </div>
        <div class="mb-4">
          <label class="form-label small"><i class="fab fa-whatsapp me-2"></i>Téléphone</label>
          <input type="tel" name="phone" class="form-control" placeholder="ex: +212XXXXXXXXX" required pattern="^\\+\\d{{9,}}$">
        </div>
        <button type="submit" class="btn btn-gradient btn-lg w-100">Créer mon compte</button>
      </form>
    </div>
  </div>
</body>
</html>
'''

reset_template = f'''
<!DOCTYPE html>
<html lang="fr">
{base_head_and_style}
<title>Réinitialiser mot de passe</title>
<body class="d-flex align-items-center">
  <div class="container">
    <div class="main-card mx-auto p-4 p-md-5 text-center">
      <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon">
      <h3 class="card-title fw-bold"><i class="fas fa-redo-alt me-2"></i>Nouveau Mot de Passe</h3>
      {{% with msgs = get_flashed_messages(with_categories=true) %}}
        {{% for cat,msg in msgs %}}<div class="alert alert-{{{{cat}}}} small mt-3">{{{{msg}}}}</div>{{% endfor %}}
      {{% endwith %}}
      <form method="POST" class="mt-3">
        <div class="mb-3">
            <label class="form-label small text-start w-100"><i class="fas fa-key me-2"></i>Nouveau mot de passe</label>
            <input type="password" name="password" class="form-control form-control-lg" required>
        </div>
        <div class="mb-4">
            <label class="form-label small text-start w-100"><i class="fas fa-key me-2"></i>Confirmer le mot de passe</label>
            <input type="password" name="confirm" class="form-control form-control-lg" required>
        </div>
        <button type="submit" class="btn btn-gradient btn-lg w-100">Mettre à jour</button>
      </form>
    </div>
  </div>
</body>
</html>
'''

forgot_template = f'''
<!DOCTYPE html>
<html lang="fr">
{base_head_and_style}
<title>Récupération mot de passe</title>
<body class="d-flex align-items-center">
  <div class="container">
    <div class="main-card mx-auto p-4 p-md-5 text-center">
        <img src="/static/pwa/icon-512.png" alt="EasyMedicalink Icon" class="app-icon">
        <h3 class="card-title fw-bold"><i class="fas fa-unlock-alt me-2"></i> Récupération</h3>
        <p class="text-center text-muted small mb-4">Saisissez l'e-mail de votre compte. Un lien pour réinitialiser votre mot de passe vous sera envoyé.</p>
        {{% with msgs = get_flashed_messages(with_categories=true) %}}
          {{% for cat,msg in msgs %}}<div class="alert alert-{{{{cat}}}} small">{{{{msg}}}}</div>{{% endfor %}}
        {{% endwith %}}
        <form method="POST">
          <div class="mb-3">
              <label class="form-label small text-start w-100"><i class="fas fa-envelope me-2"></i>Adresse e-mail</label>
              <input type="email" name="email" class="form-control form-control-lg" required>
          </div>
          <button type="submit" class="btn btn-gradient btn-lg w-100">Envoyer le lien</button>
        </form>
        <div class="mt-3">
          <a href="{{{{ url_for('login.login') }}}}" class="btn btn-sm btn-link text-muted"><i class="fas fa-arrow-left me-1"></i> Retour à la connexion</a>
        </div>
    </div>
  </div>
</body>
</html>
'''