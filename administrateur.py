# administrateur.py
# ──────────────────────────────────────────────────────────────────────────────
# Module d'administration centralisé pour EasyMedicaLink.
# Gère les utilisateurs, les licences, les paramètres de l'application,
# l'accès patient, les indisponibilités et les opérations de base de données.
#
# MODIFICATIONS FINALES :
# - Correction du chemin pour la création de l'archive ZIP en se basant sur utils.EXCEL_FOLDER.
# - Amélioration de l'UI du template : couleurs d'icônes diversifiées et listes déroulantes optimisées.
# - Correction de la liste déroulante "Médecin lié" pour afficher le nom des paramètres généraux.
# - MISE À JOUR CRITIQUE: Implémentation de la limite globale de 3 comptes secondaires pour l'administrateur.
# - Correction pré-remplissage nom clinique et médecin dans get_admin_dashboard_context.
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# 0. Importations et Initialisation
# ──────────────────────────────────────────────────────────────────────────────

from flask import Blueprint, render_template_string, request, redirect, url_for, flash, session, jsonify, current_app, send_file
from datetime import datetime, date, timedelta
from functools import wraps
import json
import os
import pandas as pd
import re
from werkzeug.utils import secure_filename
import qrcode
import base64
import io
import shutil
import zipfile
import tempfile

# Internal module imports
import theme
import utils
import login

# Import the function to load all excels from statistique.py
# Fallback if statistique.py is not directly importable
try:
    from statistique import _load_all_excels
except ImportError:
    print("ATTENTION: Impossible d'importer _load_all_excels de statistique.py. Assurez-vous que le fichier est présent et accessible.")
    def _load_all_excels(folder: str) -> dict:
        print(f"AVERTISSEMENT: _load_all_excels n'est pas disponible. Le téléchargement/importation Excel ne fonctionnera pas.")
        return {}

# Retrieve TRIAL_DAYS for display
try:
    from activation import TRIAL_DAYS
except ImportError:
    TRIAL_DAYS = 7

# Create the Blueprint for administration routes
administrateur_bp = Blueprint('administrateur_bp', __name__, url_prefix='/administrateur')

# Define default roles and their limits (Used for UI/structure, but global limit now applied in creation logic)
DEFAULT_ROLE_LIMITS = {
    "medecin": {"max": float('inf'), "current": 0},
    "assistante": {"max": float('inf'), "current": 0},
    "comptable": {"max": float('inf'), "current": 0},
    "biologiste": {"max": float('inf'), "current": 0},
    "radiologue": {"max": float('inf'), "current": 0},
    "pharmacie/magasin": {"max": float('inf'), "current": 0},
    "admin": {"max": float('inf'), "current": 0} # The main administrator
}

# ──────────────────────────────────────────────────────────────────────────────
# 1. Decorators
# ──────────────────────────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'email' not in session:
            flash("Veuillez vous connecter pour accéder à cette page.", "warning")
            return redirect(url_for('login.login'))
        if session.get('role') != 'admin':
            flash("Accès non autorisé. Seuls les administrateurs peuvent accéder à cette page.", "danger")
            return redirect(url_for('accueil.accueil'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'email' not in session:
                flash("Veuillez vous connecter pour accéder à cette page.", "warning")
                return redirect(url_for('login.login'))

            user_role = session.get('role')
            if user_role not in allowed_roles:
                flash("Accès non autorisé. Vous n'avez pas les permissions nécessaires pour cette page.", "danger")
                return redirect(url_for('accueil.accueil'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ──────────────────────────────────────────────────────────────────────────────
# 2. Helper Functions for Dashboard and License Information
# ──────────────────────────────────────────────────────────────────────────────
def get_current_plan_info() -> str:
    mapping = {
        f"essai_{TRIAL_DAYS}jours": f"Essai ({TRIAL_DAYS} jours)",
        "1 mois":   "1 mois",
        "1 an":     "1 an",
        "illimité": "Illimité",
    }
    user = login.load_users().get(session.get("email"))
    plan_raw = (user.get("activation", {}).get("plan", "").lower() if user else "")
    return mapping.get(plan_raw, plan_raw.capitalize() or "Inconnu")

def generate_qr_code_data_uri(data: str) -> str:
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"

def get_admin_dashboard_context():
    admin_email = session['email']
    full_users = login.load_users()
    config = utils.load_config() # Charger la config existante depuis config.json

    # ---> NOUVELLE LOGIQUE CORRIGÉE : Pré-remplissage des valeurs par défaut <---
    admin_user_data = full_users.get(admin_email)

    # Vérifier et pré-remplir si les valeurs de config sont vides ou inexistantes
    if admin_user_data:
        # Pré-remplir le nom de la clinique si non défini ou vide dans config.json
        if not config.get('nom_clinique') or not str(config['nom_clinique']).strip():
            config['nom_clinique'] = admin_user_data.get('clinic', '').strip() # Utilise la clé 'clinic' du user data

        # Pré-remplir le nom du médecin si non défini ou vide dans config.json
        if not config.get('doctor_name') or not str(config['doctor_name']).strip():
            admin_prenom = admin_user_data.get('prenom', '')
            admin_nom = admin_user_data.get('nom', '')
            if admin_prenom or admin_nom:
                # Combine prénom et nom depuis le user data
                config['doctor_name'] = f"{admin_prenom} {admin_nom}".strip()
    # ---> FIN NOUVELLE LOGIQUE CORRIGÉE <---

    users_for_table = []
    current_role_counts = {role: 0 for role in DEFAULT_ROLE_LIMITS.keys()}

    for e, u in full_users.items():
        if u.get('owner') == admin_email and e != admin_email:
            role = u.get('role', '')
            if role in current_role_counts:
                current_role_counts[role] += 1

            user_info = {
                'email': e, 'nom': u.get('nom', ''), 'prenom': u.get('prenom', ''), 'role': role,
                'active': u.get('active', False), 'phone': u.get('phone', ''),
                'linked_doctor': u.get('linked_doctor', ''), 'allowed_pages': u.get('allowed_pages', [])
            }
            users_for_table.append(user_info)

    # Remplacer DEFAULT_ROLE_LIMITS par la logique de la limite globale (3 utilisateurs max)
    # Pour l'affichage, nous devons quand même calculer le nombre actuel

    # Compter le nombre d'utilisateurs secondaires (rôles autres qu'admin)
    current_non_admin_users = sum(1 for u in full_users.values() if u.get('owner') == admin_email and u.get('role') != 'admin' and u.get('email') != admin_email)
    GLOBAL_USER_LIMIT = 3

    display_role_limits = {}
    for role, default_limits in DEFAULT_ROLE_LIMITS.items():
         if role == 'admin':
             max_limit = "Illimité"
         else:
             # Afficher la limite de 3 pour les rôles secondaires
             max_limit = str(GLOBAL_USER_LIMIT)

         display_role_limits[role] = {
             "current": current_role_counts.get(role, 0),
             "max": max_limit
         }

    current_date = datetime.now().strftime("%Y-%m-%d")

    backgrounds_folder = utils.BACKGROUND_FOLDER
    backgrounds = []
    if os.path.exists(backgrounds_folder):
        for f in os.listdir(backgrounds_folder):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                backgrounds.append(f)

    admin_email_prefix = admin_email.split('@')[0]
    patient_appointment_link = url_for('patient_rdv.patient_rdv_home', admin_prefix=admin_email_prefix, _external=True)
    qr_code_data_uri = generate_qr_code_data_uri(patient_appointment_link)

    # Build the list of doctors for the dropdown
    doctors = [u for u in users_for_table if u['role'] == 'medecin' and u['active']]
    main_admin = full_users.get(admin_email)

    admin_email_in_doctors_list = any(d['email'] == admin_email for d in doctors)

    if main_admin and not admin_email_in_doctors_list:
        # ---> CORRECTION : Utiliser le nom du médecin depuis 'config' (qui a été pré-rempli si besoin) <---
        config_doctor_name = config.get('doctor_name', '').strip()

        if config_doctor_name:
            parts = config_doctor_name.split(' ', 1)
            prenom = parts[0]
            nom = parts[1] if len(parts) > 1 else ''
        else: # Fallback si même la config est vide (peu probable après pré-remplissage)
            prenom = main_admin.get('prenom', '')
            nom = main_admin.get('nom', '')
        # ---> FIN CORRECTION <---

        doctors.append({'email': admin_email, 'nom': nom, 'prenom': prenom})

    doctors = sorted(doctors, key=lambda d: (d.get('prenom', ''), d.get('nom', '')))

    # Calculer logged_in_doctor_name pour l'en-tête (basé sur l'utilisateur connecté)
    logged_in_doctor_name_header = ""
    if admin_user_data:
        logged_in_doctor_name_header = f"{admin_user_data.get('prenom', '')} {admin_user_data.get('nom', '')}".strip()

    return {
        "users": users_for_table,
        "config": config, # <-- Passer le dictionnaire config (potentiellement modifié)
        "current_date": current_date,
        "theme_vars": theme.current_theme(),
        "theme_names": list(theme.THEMES.keys()),
        "plan": get_current_plan_info(),
        "admin_email": admin_email,
        "backgrounds": backgrounds,
        "patient_appointment_link": patient_appointment_link,
        "qr_code_data_uri": qr_code_data_uri,
        "doctors": doctors,
        "role_limits": display_role_limits,
        "DEFAULT_ROLE_LIMITS": DEFAULT_ROLE_LIMITS,
        "all_blueprints": login.ALL_BLUEPRINTS,
        "medications_options": config.get('medications_options', utils.default_medications_options),
        "analyses_options": config.get('analyses_options', utils.default_analyses_options),
        "radiologies_options": config.get('radiologies_options', utils.default_radiologies_options),
        "global_user_count": current_non_admin_users,
        "global_user_limit": GLOBAL_USER_LIMIT,
        "logged_in_doctor_name": logged_in_doctor_name_header # Pour l'affichage dans l'en-tête
    }

# ──────────────────────────────────────────────────────────────────────────────
# 3. User Management Functions
# ──────────────────────────────────────────────────────────────────────────────
def get_user_details(user_email: str) -> dict:
    u = login.load_users().get(user_email)
    if not u or u.get('owner') != session.get('email'):
        return {}
    return {
        'nom': u.get('nom', ''), 'prenom': u.get('prenom', ''), 'role': u.get('role', ''),
        'phone': u.get('phone', ''), 'linked_doctor': u.get('linked_doctor', ''),
        'allowed_pages': u.get('allowed_pages', [])
    }

def create_new_user(form_data: dict) -> tuple[bool, str]:
    """
    Crée un nouvel utilisateur en appliquant une limite globale de 3 comptes
    secondaires maximum pour l'administrateur.
    """
    admin_email = session['email']
    nom, prenom, role, password = (
        form_data['nom'].strip(), form_data['prenom'].strip(),
        form_data['role'].strip(), form_data['password'].strip()
    )
    phone, linked_doctor = form_data.get('phone', '').strip(), form_data.get('linked_doctor', '').strip()
    allowed_pages = form_data.getlist('allowed_pages[]')

    # --- LOGIQUE DE VÉRIFICATION DE LA LIMITE GLOBALE (3 comptes max) ---
    GLOBAL_USER_LIMIT = 3

    users = login.load_users()
    users_owned_by_admin = [u for u in users.values() if u.get('owner') == admin_email]

    # Compter le nombre actuel d'utilisateurs non-admin (pour éviter de compter l'admin lui-même)
    current_non_admin_count = sum(1 for u in users_owned_by_admin if u.get('email') != admin_email and u.get('role') != 'admin')

    if role != 'admin' and current_non_admin_count >= GLOBAL_USER_LIMIT:
        return False, f"Limite globale atteinte. L'administrateur est limité à un maximum de {GLOBAL_USER_LIMIT} comptes secondaires (actuellement {current_non_admin_count})."
    # --- FIN DE LA LOGIQUE DE VÉRIFICATION DE LA LIMITE GLOBALE ---

    # --- LOGIQUE DE CRÉATION D'EMAIL BASÉE SUR L'ADMIN PRINCIPAL ---
    admin_email_prefix = admin_email.split('@')[0]

    # Structure de l'email pour les rôles secondaires (non-admin)
    if role != 'admin':
        # Exemple: jean.dupont@adminprefixe.eml.com
        key = f"{prenom.lower()}.{nom.lower()}@{admin_email_prefix}.eml.com"
    else:
        # Si pour une raison quelconque on tentait de créer un autre admin, on donne un autre domaine
        key = f"{prenom.lower()}.{nom.lower()}@{admin_email_prefix}.eml-admin.com"

    # Vérification d'unicité de l'email
    if not login._is_email_globally_unique(key):
        return False, f"L'e-mail généré '{key}' existe déjà. Veuillez utiliser des noms et prénoms différents."

    # --- CONSTRUCTION DES DONNÉES UTILISATEUR ---
    user_data = {
        'nom': nom, 'prenom': prenom, 'role': role,
        'password': login.hash_password(password),
        'active': True, 'owner': admin_email, 'phone': phone,
        'allowed_pages': allowed_pages
    }

    # Gestion des permissions spécifiques et de la liaison
    if role != 'admin' and 'accueil' not in user_data['allowed_pages']:
        user_data['allowed_pages'].append('accueil')

    if role == 'admin':
        # Les admins ont toutes les permissions par défaut
        user_data['allowed_pages'] = login.ALL_BLUEPRINTS

    if role == 'assistante':
        user_data['linked_doctor'] = linked_doctor
    else:
        user_data.pop('linked_doctor', None)

    # Sauvegarde du nouvel utilisateur
    users[key] = user_data
    login.save_users(users)

    # Logique optionnelle de création d'une assistante temporaire pour le médecin (conservée)
    if role == 'medecin':
        # Cette logique est lourde et non nécessaire avec la limite globale stricte,
        # mais je la maintiens car elle faisait partie du comportement original.
        existing_assistants = [u for u in users.values() if u.get('role') == 'assistante' and u.get('linked_doctor') == key]
        if not existing_assistants and current_non_admin_count < GLOBAL_USER_LIMIT :
            temp_assistant_email = f"assist.{prenom.lower()}.{nom.lower()}@{admin_email_prefix}.eml.com"
            if login._is_email_globally_unique(temp_assistant_email):

                # Double vérification pour s'assurer qu'ajouter l'assistante ne dépasse pas 3
                if current_non_admin_count + 1 <= GLOBAL_USER_LIMIT:
                    users[temp_assistant_email] = {
                        'nom': 'Temporaire', 'prenom': 'Assistante', 'role': 'assistante',
                        'password': login.hash_password('password'), 'active': True, 'owner': admin_email, 'phone': '',
                        'linked_doctor': key, 'allowed_pages': ['rdv', 'routes', 'facturation', 'patient_rdv', 'accueil']
                    }
                    login.save_users(users) # Nouvelle sauvegarde pour l'assistante
                    flash(f"Assistante temporaire ({temp_assistant_email}) créée pour {prenom} {nom}.", "info")
                else:
                    flash(f"ATTENTION: L'assistante par défaut n'a pas pu être créée car vous êtes à la limite de {GLOBAL_USER_LIMIT} utilisateurs.", "warning")

    return True, "Compte créé avec succès !"

def update_existing_user(form_data: dict) -> tuple[bool, str]:
    old_email = form_data['email']
    new_email = form_data.get('new_email', old_email).strip().lower()
    new_password, confirm_password = form_data.get('new_password', '').strip(), form_data.get('confirm_password', '').strip()
    allowed_pages = form_data.getlist('allowed_pages[]')
    users = login.load_users()

    if old_email not in users or users[old_email].get('owner') != session.get('email'):
        return False, "Action non autorisée."

    user = users.pop(old_email)
    if new_email != old_email and not login._is_email_globally_unique(new_email):
        users[old_email] = user
        login.save_users(users)
        return False, f"Le nouvel e-mail '{new_email}' est déjà utilisé."

    user.update({
        'nom': form_data['nom'].strip(), 'prenom': form_data['prenom'].strip(), 'role': form_data['role'].strip(),
        'phone': form_data.get('phone', '').strip(), 'allowed_pages': allowed_pages
    })

    if user['role'] != 'admin' and 'accueil' not in user['allowed_pages']:
        user['allowed_pages'].append('accueil')
    if user['role'] == 'admin':
        user['allowed_pages'] = login.ALL_BLUEPRINTS
    if user['role'] == 'assistante':
        user['linked_doctor'] = form_data.get('linked_doctor', '').strip()
    else:
        user.pop('linked_doctor', None)
    if new_password:
        if new_password != confirm_password:
            users[old_email] = user # Remettre l'utilisateur avec l'ancien email en cas d'erreur
            login.save_users(users)
            return False, "Les mots de passe ne correspondent pas."
        user['password'] = login.hash_password(new_password)

    users[new_email] = user
    login.save_users(users)
    return True, "Données utilisateur mises à jour."

def toggle_user_active_status(user_email: str) -> tuple[bool, str]:
    users = login.load_users()
    if user_email in users and users[user_email].get('owner') == session.get('email'):
        users[user_email]['active'] = not users[user_email].get('active', True)
        login.save_users(users)
        return True, f"Statut de l'utilisateur {user_email} mis à jour."
    return False, "Utilisateur introuvable ou action non autorisée."

def delete_existing_user(user_email: str) -> tuple[bool, str]:
    users = login.load_users()
    if user_email in users and users[user_email].get('owner') == session.get('email'):
        users.pop(user_email)
        login.save_users(users)
        return True, f"Utilisateur {user_email} supprimé."
    return False, "Utilisateur introuvable ou action non autorisée."

# ──────────────────────────────────────────────────────────────────────────────
# 4. Data Backup and Restoration Functions (ZIP)
# ──────────────────────────────────────────────────────────────────────────────
def handle_backup_download() -> tuple[io.BytesIO, str]:
    admin_email = session.get('admin_email')
    if not admin_email:
        raise ValueError("Email administrateur non trouvé en session.")
    utils.set_dynamic_base_dir(admin_email)

    # MODIFICATION CORRIGÉE : On déduit le dossier de base à partir d'un chemin connu.
    admin_data_dir = os.path.dirname(utils.EXCEL_FOLDER)

    if not os.path.isdir(admin_data_dir):
        raise ValueError(f"Le répertoire de données '{admin_data_dir}' n'existe pas.")

    with tempfile.TemporaryDirectory() as temp_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"EasyMedicaLink_Sauvegarde_{timestamp}"
        archive_path = os.path.join(temp_dir, archive_name)
        shutil.make_archive(base_name=archive_path, format='zip', root_dir=admin_data_dir)
        buffer = io.BytesIO()
        with open(f"{archive_path}.zip", 'rb') as f:
            buffer.write(f.read())
        buffer.seek(0)
        return buffer, f"{archive_name}.zip"

def handle_backup_upload(uploaded_file) -> tuple[bool, str]:
    if not uploaded_file or uploaded_file.filename == '':
        return False, "Aucun fichier sélectionné."
    if not uploaded_file.filename.lower().endswith('.zip'):
        return False, "Type de fichier non supporté. Veuillez uploader une archive ZIP (.zip)."
    try:
        admin_email = session.get('admin_email')
        if not admin_email:
            return False, "Session administrateur invalide."
        utils.set_dynamic_base_dir(admin_email)

        # MODIFICATION CORRIGÉE : On déduit le dossier de base à partir d'un chemin connu.
        admin_data_dir = os.path.dirname(utils.EXCEL_FOLDER)

        os.makedirs(admin_data_dir, exist_ok=True)
        for item in os.listdir(admin_data_dir):
            item_path = os.path.join(admin_data_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
        with zipfile.ZipFile(uploaded_file.stream, 'r') as zip_ref:
            zip_ref.extractall(admin_data_dir)
        return True, "Sauvegarde importée avec succès."
    except zipfile.BadZipFile:
        return False, "Le fichier n'est pas une archive ZIP valide."
    except Exception as e:
        return False, f"Erreur lors du traitement de l'archive : {e}"

def handle_image_upload(image_file, image_type: str) -> tuple[bool, str]:
    if not image_file or image_file.filename == "":
        return False, "Aucun fichier sélectionné."
    filename = secure_filename(image_file.filename)
    path = os.path.join(utils.BACKGROUND_FOLDER, filename)
    try:
        image_file.save(path)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".pdf"):
            os.remove(path)
            return False, "Format non supporté."
        cfg = utils.load_config()
        if image_type == "background":
            cfg["background_file_path"] = filename
            message = f"Arrière-plan importé : {filename}"
        elif image_type == "logo":
            cfg["logo_file_path"] = filename
            message = f"Logo importé : {filename}"
        else:
            os.remove(path)
            return False, "Type d'image non valide."
        utils.save_config(cfg)
        utils.init_app(current_app._get_current_object())
        return True, message
    except Exception as e:
        return False, f"Erreur lors de l'importation de l'image : {e}"

# ──────────────────────────────────────────────────────────────────────────────
# 5. Unavailability Management Functions
# ──────────────────────────────────────────────────────────────────────────────
def manage_unavailability_periods(form_data: dict) -> tuple[bool, str]:
    action = form_data.get('action')
    config = utils.load_config()
    unavailability = config.get('unavailability_periods', [])
    if action == 'add':
        start_date_str, end_date_str = form_data.get('start_date'), form_data.get('end_date')
        reason = form_data.get('reason', '').strip()
        if not start_date_str or not end_date_str:
            return False, "Les dates sont requises."
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            if start_date > end_date:
                return False, "La date de début ne peut pas être postérieure à la date de fin."
            unavailability.append({'start_date': start_date_str, 'end_date': end_date_str, 'reason': reason})
            config['unavailability_periods'] = unavailability
            utils.save_config(config)
            return True, "Période d'indisponibilité ajoutée."
        except Exception as e:
            return False, f"Erreur lors de l'ajout: {e}"
    elif action == 'delete':
        index_to_delete = form_data.get('index', type=int)
        if 0 <= index_to_delete < len(unavailability):
            unavailability.pop(index_to_delete)
            config['unavailability_periods'] = unavailability
            utils.save_config(config)
            return True, "Période d'indisponibilité supprimée."
        else:
            return False, "Index invalide."
    return False, "Action non reconnue."

def handle_medication_list_download() -> tuple[io.BytesIO, str]:
    if not os.path.exists(utils.LISTS_FILE):
        try:
            df_meds = pd.DataFrame({'Médicaments': utils.default_medications_options})
            df_analyses = pd.DataFrame({'Analyses': utils.default_analyses_options})
            df_radios = pd.DataFrame({'Radiologies': utils.default_radiologies_options})
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_meds.to_excel(writer, sheet_name='Médicaments', index=False)
                df_analyses.to_excel(writer, sheet_name='Analyses', index=False)
                df_radios.to_excel(writer, sheet_name='Radiologies', index=False)
            buffer.seek(0)
            return buffer, os.path.basename(utils.LISTS_FILE)
        except Exception as e:
            raise ValueError(f"Erreur lors de la création du fichier de listes : {e}")
    buffer = io.BytesIO()
    try:
        with open(utils.LISTS_FILE, 'rb') as f:
            buffer.write(f.read())
        buffer.seek(0)
        return buffer, os.path.basename(utils.LISTS_FILE)
    except Exception as e:
        raise ValueError(f"Erreur lors du chargement du fichier de listes : {e}")

def handle_medication_list_upload(uploaded_file) -> tuple[bool, str]:
    if not uploaded_file or uploaded_file.filename == '':
        return False, "Aucun fichier sélectionné."
    if not (uploaded_file.filename.endswith('.xlsx') or uploaded_file.filename.endswith('.xls')):
        return False, "Type de fichier non supporté."
    try:
        temp_path = os.path.join(utils.CONFIG_FOLDER, secure_filename(uploaded_file.filename))
        uploaded_file.save(temp_path)
        xls = pd.ExcelFile(temp_path)
        config = utils.load_config()
        updated_any = False
        if 'Médicaments' in xls.sheet_names:
            df_meds = xls.parse('Médicaments')
            if 'Médicaments' in df_meds.columns:
                config['medications_options'] = df_meds['Médicaments'].dropna().astype(str).tolist()
                updated_any = True
        if 'Analyses' in xls.sheet_names:
            df_analyses = xls.parse('Analyses')
            if 'Analyses' in df_analyses.columns:
                config['analyses_options'] = df_analyses['Analyses'].dropna().astype(str).tolist()
                updated_any = True
        if 'Radiologies' in xls.sheet_names:
            df_radios = xls.parse('Radiologies')
            if 'Radiologies' in df_radios.columns:
                config['radiologies_options'] = df_radios['Radiologies'].dropna().astype(str).tolist()
                updated_any = True
        if updated_any:
            utils.save_config(config)
            df_meds_to_save = pd.DataFrame({'Médicaments': config.get('medications_options', [])})
            df_analyses_to_save = pd.DataFrame({'Analyses': config.get('analyses_options', [])})
            df_radios_to_save = pd.DataFrame({'Radiologies': config.get('radiologies_options', [])})
            with pd.ExcelWriter(utils.LISTS_FILE, engine='xlsxwriter') as writer:
                df_meds_to_save.to_excel(writer, sheet_name='Médicaments', index=False)
                df_analyses_to_save.to_excel(writer, sheet_name='Analyses', index=False)
                df_radios_to_save.to_excel(writer, sheet_name='Radiologies', index=False)
            os.remove(temp_path)
            utils.init_app(current_app._get_current_object())
            return True, "Listes mises à jour."
        else:
            os.remove(temp_path)
            return False, "Le fichier Excel ne contient pas les feuilles ou colonnes attendues."
    except Exception as e:
        return False, f"Erreur lors de l'importation du fichier de listes : {e}"

# ──────────────────────────────────────────────────────────────────────────────
# 6. Routes du Blueprint administrateur_bp
# ──────────────────────────────────────────────────────────────────────────────
@administrateur_bp.route('/', methods=['GET'])
@admin_required
def dashboard():
    context = get_admin_dashboard_context()
    return render_template_string(administrateur_template, **context)

@administrateur_bp.route('/users/<user_email>', methods=['GET'])
@admin_required
def get_user(user_email):
    user_details = get_user_details(user_email)
    return jsonify(user_details) if user_details else (jsonify({}), 404)

@administrateur_bp.route('/users', methods=['POST'])
@admin_required
def create_user():
    success, message = create_new_user(request.form)
    flash(message, "success" if success else "danger")
    return redirect(url_for('administrateur_bp.dashboard'))

@administrateur_bp.route('/users/edit', methods=['POST'])
@admin_required
def edit_user():
    success, message = update_existing_user(request.form)
    flash(message, "success" if success else "danger")
    return redirect(url_for('administrateur_bp.dashboard'))

@administrateur_bp.route('/users/<user_email>/toggle-active', methods=['GET'])
@admin_required
def toggle_user_active(user_email):
    success, message = toggle_user_active_status(user_email)
    flash(message, "success" if success else "danger")
    return redirect(url_for('administrateur_bp.dashboard'))

@administrateur_bp.route('/users/<user_email>/delete', methods=['GET'])
@admin_required
def delete_user(user_email):
    success, message = delete_existing_user(user_email)
    # L'utilisateur supprimé doit être retiré du compteur global si c'était un utilisateur secondaire
    if success and message.startswith("Utilisateur"):
        # Relancer la fonction d'affichage pour recalculer le compteur et l'afficher correctement
        context = get_admin_dashboard_context()
        current_user_count = context['global_user_count']
        flash(f"Utilisateur {user_email} supprimé. Compteurs : {current_user_count}/{context['global_user_limit']} disponibles.", "success")
    else:
        flash(message, "danger")
    return redirect(url_for('administrateur_bp.dashboard'))

@administrateur_bp.route("/data/backup/download", methods=["GET"])
@admin_required
def download_backup():
    try:
        buffer, filename = handle_backup_download()
        return send_file(
            buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(f"ERREUR CRITIQUE LORS DE LA CRÉATION DU ZIP : {e}")
        flash(f"Erreur lors de la génération de la sauvegarde : {e}", "danger")
        return redirect(url_for("administrateur_bp.dashboard"))

@administrateur_bp.route("/data/backup/upload", methods=["POST"])
@admin_required
def upload_backup():
    if 'backup_file' not in request.files:
        flash("Aucun fichier n'a été sélectionné.", "warning")
        return redirect(url_for("administrateur_bp.dashboard"))
    file = request.files['backup_file']
    success, message = handle_backup_upload(file)
    flash(message, "success" if success else "danger")
    return redirect(url_for("administrateur_bp.dashboard"))

@administrateur_bp.route("/data/image/upload", methods=["POST"])
@admin_required
def import_image():
    image_type = request.form.get("image_type")
    image_file = request.files.get("image_file")
    success, message = handle_image_upload(image_file, image_type)
    return jsonify({"status": "success" if success else "error", "message": message})

@administrateur_bp.route("/unavailability", methods=["POST"])
@admin_required
def manage_unavailability():
    success, message = manage_unavailability_periods(request.form)
    return jsonify({"status": "success" if success else "error", "message": message})

@administrateur_bp.route("/update_general_settings", methods=["POST"])
@admin_required
def update_general_settings():
    try:
        config = utils.load_config()
        if 'nom_clinique' in request.form:
            config['nom_clinique'] = request.form.get('nom_clinique', '').strip()
        if 'doctor_name' in request.form:
            config['doctor_name'] = request.form.get('doctor_name', '').strip()
        if 'location' in request.form:
            config['location'] = request.form.get('location', '').strip()
        if 'theme' in request.form:
            config['theme'] = request.form.get('theme', theme.DEFAULT_THEME)
        if 'currency' in request.form:
            config['currency'] = request.form.get('currency', 'EUR').strip()
        if 'vat' in request.form:
            config['vat'] = float(request.form.get('vat', '20.0').strip())
        if 'medications_options' in request.form:
            med_input = request.form.get('medications_options', '').strip()
            if med_input:
                config['medications_options'] = [line.strip() for line in med_input.split('\n') if line.strip()]
        if 'analyses_options' in request.form:
            ana_input = request.form.get('analyses_options', '').strip()
            if ana_input:
                config['analyses_options'] = [line.strip() for line in ana_input.split('\n') if line.strip()]
        if 'radiologies_options' in request.form:
            rad_input = request.form.get('radiologies_options', '').strip()
            if rad_input:
                config['radiologies_options'] = [line.strip() for line in rad_input.split('\n') if line.strip()]
        if 'rdv_start_time' in request.form:
            config['rdv_start_time'] = request.form.get('rdv_start_time', '08:00').strip()
        if 'rdv_end_time' in request.form:
            config['rdv_end_time'] = request.form.get('rdv_end_time', '17:45').strip()
        if 'rdv_interval_minutes' in request.form:
            config['rdv_interval_minutes'] = int(request.form.get('rdv_interval_minutes', 15))
        utils.save_config(config)
        utils.init_app(current_app._get_current_object())
        return jsonify({"status": "success", "message": "Paramètres mis à jour."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur: {e}"}), 500
      
@administrateur_bp.route("/lists/medications/download", methods=["GET"])
@admin_required
def download_medication_lists():
    try:
        buffer, filename = handle_medication_list_download()
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f"Erreur inattendue lors de la génération du fichier de listes : {e}", "danger")
        return redirect(url_for("administrateur_bp.dashboard"))

@administrateur_bp.route("/lists/medications/upload", methods=["POST"])
@admin_required
def upload_medication_lists():
    if 'lists_file' not in request.files:
        flash("Aucun fichier n'a été sélectionné.", "warning")
        return redirect(url_for("administrateur_bp.dashboard"))
    file = request.files['lists_file']
    success, message = handle_medication_list_upload(file)
    flash(message, "success" if success else "danger")
    return redirect(url_for("administrateur_bp.dashboard"))
# ──────────────────────────────────────────────────────────────────────────────
# 7. Integrated HTML Template
# ──────────────────────────────────────────────────────────────────────────────
administrateur_template = """
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
  <title>Administration - {{ config.nom_clinique or 'EasyMedicaLink' }}</title>

  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.datatables.net/1.13.1/css/dataTables.bootstrap5.min.css" rel="stylesheet">
  <link href="https://cdn.datatables.net/responsive/2.4.1/css/responsive.bootstrap5.min.css" rel="stylesheet">

  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&family=Great+Vibes&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>

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
      font-size: 2.0rem !important;
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
    .card:hover {
      box-shadow: var(--shadow-medium);
    }

    .card-header {
      background: var(--gradient-main) !important; /* Changed to gradient */
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

    .btn {
      border-radius: var(--border-radius-md);
      font-weight: 600;
      transition: all 0.3s ease;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0.75rem 1.25rem;
      box-shadow: var(--shadow-light);
    }
    .btn:hover {
      box-shadow: var(--shadow-medium);
      transform: translateY(-2px);
    }
    .btn i {
      margin-right: 0.5rem;
    }
    .btn-primary {
      background: var(--gradient-main);
      border: none;
      color: var(--button-text);
    }
    .btn-primary:hover {
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
    }
    .btn-warning {
      background-color: var(--warning-color);
      border-color: var(--warning-color);
      color: white;
    }
    .btn-warning:hover {
      background-color: var(--warning-color-dark);
      border-color: var(--warning-color-dark);
    }
    .btn-danger {
      background-color: var(--danger-color);
      border-color: var(--danger-color);
      color: white;
    }
    .btn-danger:hover {
      background-color: var(--danger-color-dark);
      border-color: var(--danger-color-dark);
    }
    .btn-info {
      background-color: #25D366;
      border-color: #25D366;
      color: white;
    }
    .btn-info:hover {
      background-color: #1DA851;
      border-color: #1DA851;
    }
    .btn-outline-secondary {
      border-color: var(--secondary-color);
      color: var(--text-color);
      background-color: transparent;
    }
    .btn-outline-secondary:hover {
      background-color: var(--secondary-color);
      color: white;
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

    .floating-label {
      position: relative;
    }
    .floating-label label {
      position: absolute;
      top: 0.75rem;
      left: 0.75rem;
      padding: 0 0.25rem;
      transition: all 0.2s ease-out;
      pointer-events: none;
      background-color: var(--card-bg);
      color: var(--text-color);
      display: flex;
      align-items: center;
      gap: 0.25rem;
      height: calc(1.5em + 0.75rem + 0.75rem);
    }
    .floating-label input, .floating-label select, .floating-label textarea {
        padding-top: 1.5rem;
        background-color: var(--input-bg) !important;
        color: var(--text-color) !important;
        border-color: var(--border-color) !important;
        border-radius: var(--border-radius-md);
    }
    .floating-label input:focus, .floating-label select:focus, .floating-label textarea:focus {
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 0.25rem rgba(var(--primary-color-rgb), 0.25);
    }
    .form-control:focus ~ label,
    .form-control:not(:placeholder-shown) ~ label,
    .form-select:focus ~ label,
    .form-select:not([value=""]) ~ label {
      transform: translateY(-1.5rem) scale(0.8);
      font-size: 0.75rem;
      color: var(--primary-color);
    }

    #usersTable_wrapper .dataTables_filter input,
    #usersTable_wrapper .dataTables_length select {
      border-radius: var(--border-radius-sm);
      border: 1px solid var(--secondary-color);
      padding: 0.5rem 0.75rem;
      background-color: var(--card-bg);
      color: var(--text-color);
    }
    
    .table {
      --bs-table-bg: var(--card-bg);
      --bs-table-color: var(--text-color);
      --bs-table-striped-bg: var(--table-striped-bg);
      --bs-table-striped-color: var(--text-color);
      --bs-table-border-color: var(--border-color);
    }
    .table thead th {
      background-color: var(--primary-color);
      color: var(--button-text);
      border-color: var(--primary-color);
    }

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

    footer {
      background: var(--gradient-main);
      color: white;
      font-weight: 300;
      box-shadow: 0 -5px 15px rgba(0, 0, 0, 0.1);
      padding-top: 0.75rem;
      padding-bottom: 0.75rem;
    }
    
    .checkbox-list {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 10px;
        padding-left: 10px;
    }
    .checkbox-list div {
        flex: 1 1 180px;
        min-width: 150px;
    }

    .modal-content {
      background-color: var(--card-bg);
      color: var(--text-color);
      border-radius: var(--border-radius-lg);
      box-shadow: var(--shadow-medium);
    }
    .modal-header {
      background: var(--gradient-main);
      color: var(--button-text);
      border-top-left-radius: var(--border-radius-lg);
      border-top-right-radius: var(--border-radius-lg);
    }
    .btn-close {
      filter: invert(1);
    }

    @media (max-width: 768px) {
      .btn {
        width: 100%;
        margin-bottom: 0.5rem;
      }
      .backup-buttons .btn .full-text, .executable-buttons .btn .full-text {
          display: none;
      }
      .backup-buttons .btn .abbr-text, .executable-buttons .btn .abbr-text {
          display: inline;
      }
    }

    @media (min-width: 769px) {
        .backup-buttons .btn .full-text, .executable-buttons .btn .full-text {
            display: inline;
        }
        .backup-buttons .btn .abbr-text, .executable-buttons .btn .abbr-text {
            display: none;
        }
    }
  </style>
</head>
<body>
  <nav class="navbar navbar-dark fixed-top">
    <div class="container-fluid d-flex align-items-center">
      <button class="navbar-toggler" type="button" data-bs-toggle="offcanvas" data-bs-target="#settingsOffcanvas">
        <i class="fas fa-bars"></i>
      </button>
      <a class="navbar-brand ms-auto d-flex align-items-center"
        href="{{ url_for('accueil.accueil') }}">
        <i class="fas fa-home me-2"></i>
        <i class="fas fa-heartbeat me-2"></i>EasyMedicaLink
      </a>
    </div>
  </nav>

<div class="offcanvas offcanvas-start" tabindex="-1" id="settingsOffcanvas">
  <div class="offcanvas-header text-white">
    <h5 class="offcanvas-title"><i class="fas fa-cog me-2" style="color: #FFD700;"></i>Paramètres</h5>
    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="offcanvas"></button>
  </div>
  <div class="offcanvas-body">
    <div class="d-flex gap-2 mb-4">
      <a href="{{ url_for('login.change_password') }}" class="btn btn-outline-secondary flex-fill">
        <i class="fas fa-key me-2" style="color: #FFD700;"></i>Modifier passe
      </a>
      <a href="{{ url_for('login.logout') }}" class="btn btn-outline-secondary flex-fill">
        <i class="fas fa-sign-out-alt me-2" style="color: #DC143C;"></i>Déconnexion
      </a>
    </div>
  </div>
</div>

  <div class="container-fluid my-4">
    <div class="row justify-content-center">
      <div class="col-12">
        <div class="card shadow-lg">
          <div class="card-header py-3 text-center">
            <h1 class="mb-2 header-item"><i class="fas fa-hospital me-2" style="color: #F0F8FF;"></i>{{ config.nom_clinique or 'NOM CLINIQUE/CABINET/CENTRE MEDICAL' }}</h1>
            <div class="d-flex justify-content-center gap-4 flex-wrap">
              <div class="d-flex align-items-center header-item">
                <i class="fas fa-user me-2" style="color: #90EE90;"></i><span>{{ logged_in_doctor_name if logged_in_doctor_name and logged_in_doctor_name != 'None' else config.doctor_name or 'NOM MEDECIN' }}</span>
              </div>
              <div class="d-flex align-items-center header-item">
                <i class="fas fa-map-marker-alt me-2" style="color: #FF6347;"></i><span>{{ config.location or 'LIEU' }}</span>
              </div>
            </div>
            <p class="mt-2 header-item"><i class="fas fa-calendar-day me-2" style="color: #87CEEB;"></i>{{ current_date }}</p>
            <p class="mt-2 header-item"><i class="fas fa-user-shield me-2" style="color: #FFD700;"></i>Administrateur</p>
          </div>
          <div class="card-body">
            <div class="mb-3 text-center">
              <h6 class="fw-bold"><i class="fas fa-id-badge me-2" style="color: #6C757D;"></i>Informations de licence</h6>
              <p class="mb-1"><strong>Plan :</strong> {{ plan }}</p>
              <p class="mb-4"><strong>Administrateur :</strong> {{ admin_email }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="container-fluid my-4">
      <div class="row justify-content-center">
        <div class="col-12">
          <div class="card">
            <div class="card-header text-center"><h2 class="header-item"><i class="fas fa-cogs me-2" style="color: #FFD700;"></i>Paramètres Généraux de l'Application</h2></div>
            <div class="card-body">
              <form id="mainSettingsForm" action="{{ url_for('administrateur_bp.update_general_settings') }}" method="POST">
                <div class="row g-3">
                  <div class="col-md-6 floating-label">
                                    <input type="text" class="form-control" name="nom_clinique" id="nom_clinique_main" value="{{ config.nom_clinique | default('') }}" placeholder=" " readonly>
                                    <label for="nom_clinique_main"><i class="fas fa-hospital me-2" style="color: #17a2b8;"></i>Nom Clinique / Cabinet/Centre Médical</label>
                                  </div>
                  <div class="col-md-6 floating-label">
                    <input type="text" class="form-control" name="doctor_name" id="doctor_name_main" value="{{ config.doctor_name | default('') }}" placeholder=" ">
                    <label for="doctor_name_main"><i class="fas fa-user-md me-2" style="color: #28a745;"></i>Nom Médecin</label>
                  </div>
                  <div class="col-md-6 floating-label">
                    <input type="text" class="form-control" name="location" id="location_main" value="{{ config.location | default('') }}" placeholder=" ">
                    <label for="location_main"><i class="fas fa-map-marker-alt me-2" style="color: #dc3545;"></i>Lieu</label>
                  </div>
                  <div class="col-md-6 floating-label">
                    <select id="theme_main" name="theme" class="form-select" placeholder=" ">
                      {% for t in theme_names %}<option value="{{ t }}" {% if config.theme == t %}selected{% endif %}>{{ t.capitalize() }}</option>{% endfor %}
                    </select>
                    <label for="theme_main"><i class="fas fa-palette me-2" style="color: #fd7e14;"></i>Thème</label>
                  </div>
                  <div class="col-md-6 floating-label">
                    <select id="currency_main" name="currency" class="form-select" placeholder=" ">
                      {% set currencies = [('EUR','Euro'),('USD','Dollar US'),('MAD','Dirham marocain'),('DZD','Dinar algérien'),('TND','Dinar tunisien'),('XOF','Franc CFA (BCEAO)'),('XAF','Franc CFA (BEAC)'),('CHF','Franc suisse'),('CAD','Dollar canadien'),('HTG','Gourde haïtienne'),('GNF','Franc guinéen')] %}
                      {% for code, name in currencies %}<option value="{{ code }}" {% if config.currency == code %}selected{% endif %}>{{ name }} ({{ code }})</option>{% endfor %}
                    </select>
                    <label for="currency_main"><i class="fas fa-money-bill-wave me-2" style="color: #20c997;"></i>Devise</label>
                  </div>
                  <div class="col-md-6 floating-label">
                    <input type="number" id="vat_main" name="vat" class="form-control" value="{{ config.vat | default(20.0) }}" step="0.01" min="0" max="100" placeholder=" ">
                    <label for="vat_main"><i class="fas fa-percent me-2" style="color: #6f42c1;"></i>TVA (%)</label>
                  </div>
                  <div class="col-md-4 floating-label">
                    <input type="time" class="form-control" name="rdv_start_time" id="rdv_start_time_main" value="{{ config.rdv_start_time | default('08:00') }}" placeholder=" ">
                    <label for="rdv_start_time_main"><i class="fas fa-clock me-2" style="color: #17a2b8;"></i>Heure de début RDV</label>
                  </div>
                  <div class="col-md-4 floating-label">
                    <input type="time" class="form-control" name="rdv_end_time" id="rdv_end_time_main" value="{{ config.rdv_end_time | default('17:45') }}" placeholder=" ">
                    <label for="rdv_end_time_main"><i class="fas fa-clock me-2" style="color: #dc3545;"></i>Heure de fin RDV</label>
                  </div>
                  <div class="col-md-4 floating-label">
                    <input type="number" class="form-control" name="rdv_interval_minutes" id="rdv_interval_minutes_main" value="{{ config.rdv_interval_minutes | default(15) }}" min="1" placeholder=" ">
                    <label for="rdv_interval_minutes_main"><i class="fas fa-hourglass-half me-2" style="color: #ffc107;"></i>Intervalle RDV (minutes)</label>
                  </div>
                  <div class="col-12 text-center d-flex justify-content-center flex-wrap gap-2">
                    <button type="submit" class="btn btn-success"><i class="fas fa-save me-2"></i>Enregistrer les paramètres</button>
                    <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#importBackgroundModal"><i class="fas fa-image me-2"></i>Importer Logo/Arrière-plan</button>
                  </div>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>

  <div class="container-fluid my-4">
    <div class="row justify-content-center">
      <div class="col-12">
        <div class="card">
          <div class="card-header text-center"><h2 class="header-item"><i class="fas fa-list-alt me-2" style="color: #87CEEB;"></i>Gestion des Listes (Médicaments, Analyses, Radiologies)</h2></div>
          <div class="card-body">
            <form id="listsSettingsForm" action="{{ url_for('administrateur_bp.update_general_settings') }}" method="POST">
              <div class="row g-3">
                <div class="col-md-4 floating-label">
                  <textarea class="form-control" name="medications_options" id="medications_options_main" rows="10" placeholder=" ">{{ "\n".join(medications_options) }}</textarea>
                  <label for="medications_options_main">Liste des Médicaments</label>
                </div>
                <div class="col-md-4 floating-label">
                  <textarea class="form-control" name="analyses_options" id="analyses_options_main" rows="10" placeholder=" ">{{ "\n".join(analyses_options) }}</textarea>
                  <label for="analyses_options_main">Liste des Analyses</label>
                </div>
                <div class="col-md-4 floating-label">
                  <textarea class="form-control" name="radiologies_options" id="radiologies_options_main" rows="10" placeholder=" ">{{ "\n".join(radiologies_options) }}</textarea>
                  <label for="radiologies_options_main">Liste des Radiologies</label>
                </div>
                <div class="col-12 text-center">
                  <button type="submit" class="btn btn-success"><i class="fas fa-save me-2"></i>Enregistrer les listes</button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="container-fluid my-4">
    <div class="row justify-content-center">
      <div class="col-12">
        <div class="card">
          <div class="card-header text-center"><h2 class="header-item"><i class="fas fa-calendar-check me-2" style="color: #90EE90;"></i>Accès Patient & Indisponibilités</h2></div>
          <div class="card-body">
            <div class="row">
              <div class="col-md-6 mb-4">
                <h5 class="fw-bold text-center"><i class="fas fa-link me-2" style="color: #17a2b8;"></i>Lien de prise de rendez-vous</h5>
                <div class="mb-3 p-2 border rounded text-center">
                  <p class="text-break small mb-1">{{ patient_appointment_link }}</p>
                  <button class="btn btn-secondary btn-sm mb-2" onclick="copyToClipboard('{{ patient_appointment_link }}')"><i class="fas fa-copy me-2"></i>Copier le lien</button>
                  {% if qr_code_data_uri %}
                      <div class="text-center d-flex justify-content-center">
                        <img src="{{ qr_code_data_uri }}" alt="QR Code Rendez-vous" class="img-fluid" style="max-width: 120px;">
                      </div>
                  {% endif %}
                </div>
              </div>
              <div class="col-md-6">
                <h5 class="fw-bold text-center"><i class="fas fa-calendar-times me-2" style="color: #dc3545;"></i>Gérer les indisponibilités</h5>
                <form id="addUnavailabilityForm" class="row g-2 mb-3" action="{{ url_for('administrateur_bp.manage_unavailability') }}" method="POST">
                  <input type="hidden" name="action" value="add">
                  <div class="col-md-6 floating-label">
                    <input type="date" class="form-control" id="unavailabilityStartDate" name="start_date" placeholder=" " required>
                    <label for="unavailabilityStartDate"><i class="fas fa-calendar-alt me-2"></i>Date de début</label>
                  </div>
                  <div class="col-md-6 floating-label">
                    <input type="date" class="form-control" id="unavailabilityEndDate" name="end_date" placeholder=" " required>
                    <label for="unavailabilityEndDate"><i class="fas fa-calendar-alt me-2"></i>Date de fin</label>
                  </div>
                  <div class="col-12 floating-label">
                    <input type="text" class="form-control" id="unavailabilityReason" name="reason" placeholder=" ">
                    <label for="unavailabilityReason"><i class="fas fa-info-circle me-2"></i>Raison (optionnel)</label>
                  </div>
                  <div class="col-12">
                    <button type="submit" class="btn btn-primary w-100"><i class="fas fa-plus-circle me-2"></i>Ajouter une période</button>
                  </div>
                </form>
                <h6 class="mt-4 fw-bold"><i class="fas fa-list-alt me-2"></i>Périodes actuelles :</h6>
                <ul class="list-group">
                  {% if config.unavailability_periods %}
                    {% for period in config.unavailability_periods %}
                      <li class="list-group-item d-flex justify-content-between align-items-center">
                        {{ period.start_date }} au {{ period.end_date }} {% if period.reason %}({{ period.reason }}){% endif %}
                        <button type="button" class="btn btn-danger btn-sm" onclick="deleteUnavailability({{ loop.index0 }})"><i class="fas fa-trash"></i></button>
                      </li>
                    {% endfor %}
                  {% else %}
                    <li class="list-group-item">Aucune période configurée.</li>
                  {% endif %}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="container-fluid my-4">
    <div class="row justify-content-center">
      <div class="col-12">
        <div class="card">
          <div class="card-header text-center"><h2 class="header-item"><i class="fas fa-users-cog me-2" style="color: #6f42c1;"></i>Administration des comptes</h2></div>
          <div class="card-body">
            <form class="row g-3 mb-4" method="POST" action="{{ url_for('administrateur_bp.create_user') }}">
              <div class="col-12 col-md-2 floating-label">
                <input name="nom" id="createNom" class="form-control" placeholder=" " required>
                <label for="createNom"><i class="fas fa-user me-2"></i>Nom</label>
              </div>
              <div class="col-12 col-md-2 floating-label">
                <input name="prenom" id="createPrenom" class="form-control" placeholder=" " required>
                <label for="createPrenom"><i class="fas fa-user-tag me-2"></i>Prénom</label>
              </div>
              <div class="col-12 col-md-2 floating-label">
                <input name="phone" id="createPhone" class="form-control" placeholder=" ">
                <label for="createPhone"><i class="fas fa-phone me-2"></i>Téléphone</label>
              </div>
              <div class="col-12 col-md-2 floating-label">
                <select name="role" id="createRole" class="form-select" placeholder=" " required>
                  <option value="" disabled selected>Sélectionner un rôle</option>
                  <option value="medecin">Médecin</option>
                  <option value="assistante">Assistante</option>
                  <option value="comptable">Comptable</option>
                  <option value="biologiste">Biologiste</option>
                  <option value="radiologue">Radiologue</option>
                  <option value="pharmacie/magasin">Pharmacie & Magasin</option>
                </select>
                <label for="createRole"><i class="fas fa-user-shield me-2"></i>Rôle</label>
              </div>
              <div class="col-12 col-md-2 floating-label" id="createLinkedDoctorDiv" style="display: none;">
                <select name="linked_doctor" id="createLinkedDoctor" class="form-select" placeholder=" ">
                  <option value="" disabled selected>Sélectionner un médecin...</option>
                  <option value="">Aucun médecin lié</option>
                  {% for doc in doctors %}<option value="{{ doc.email }}">{{ doc.prenom }} {{ doc.nom }}</option>{% endfor %}
                </select>
                <label for="createLinkedDoctor"><i class="fas fa-link me-2"></i>Médecin lié</label>
              </div>
              <div class="col-12 col-md-2 floating-label">
                <input name="password" id="createPassword" type="password" class="form-control" placeholder=" " required>
                <label for="createPassword"><i class="fas fa-lock me-2"></i>Mot de passe</label>
              </div>
              <div class="col-12 mb-3">
                <label class="form-label fw-semibold"><i class="fas fa-shield-alt me-2" style="color: #0d6efd;"></i>Autorisations d'accès :</label>
                <div class="checkbox-list" id="createAccessCheckboxes"></div>
              </div>
              <div class="col-12 col-md-2">
                <button class="btn btn-primary w-100" type="submit"><i class="fas fa-user-plus me-1"></i>Créer</button>
              </div>
            </form>

            <div class="table-responsive">
              <table id="usersTable" class="table table-striped table-hover nowrap" style="width:100%">
                <thead><tr><th>Nom</th><th>Prénom</th><th>Email</th><th>Rôle</th><th>Téléphone</th><th>Médecin Lié</th><th>Pages Autorisées</th><th>Actif</th><th>Actions</th></tr></thead>
                <tbody>
                  {% for user_info in users %}
                  <tr>
                    <td>{{ user_info.nom }}</td>
                    <td>{{ user_info.prenom }}</td>
                    <td>{{ user_info.email }}</td>
                    <td>{{ user_info.role }}</td>
                    <td>{{ user_info.phone }}</td>
                    <td>{{ user_info.linked_doctor.split('@')[0] if user_info.linked_doctor else 'N/A' }}</td>
                    <td>
                        {% if user_info.role == 'admin' %}<span class="badge bg-primary">Toutes</span>
                        {% else %}{% for page in user_info.allowed_pages %}<span class="badge bg-secondary">{{ page | replace('_', ' ') | title }}</span>{% endfor %}{% endif %}
                    </td>
                    <td>
                      <span class="badge rounded-pill bg-{{ 'success' if user_info.active else 'danger' }}">
                        {{ 'Oui' if user_info.active else 'Non' }}
                      </span>
                    </td>
                    <td class="text-nowrap">
                      <a href="#" class="btn btn-sm btn-warning me-1 editBtn" data-email="{{ user_info.email }}" title="Modifier"><i class="fas fa-edit"></i></a>
                      <a href="{{ url_for('administrateur_bp.toggle_user_active', user_email=user_info.email) }}" class="btn btn-sm btn-outline-secondary me-1" title="Activer/Désactiver">
                        {% if user_info.active %}<i class="fas fa-user-slash"></i>{% else %}<i class="fas fa-user-check"></i>{% endif %}
                      </a>
                      {% if user_info.phone %}<a href="https://wa.me/{{ user_info.phone }}" target="_blank" class="btn btn-sm btn-info me-1" title="WhatsApp"><i class="fab fa-whatsapp"></i></a>{% endif %}
                      <a href="#" class="btn btn-sm btn-danger" title="Supprimer" data-email="{{ user_info.email }}"><i class="fas fa-trash"></i></a>
                    </td>
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="container-fluid my-4">
    <div class="row justify-content-center">
      <div class="col-12">
        <div class="card">
          <div class="card-header text-center"><h2 class="header-item"><i class="fas fa-archive me-2" style="color: #fd7e14;"></i>Sauvegarde & Restauration</h2></div>
          <div class="card-body">
            <div class="row">
              <div class="col-12 mb-4">
                <h5 class="fw-bold text-center"><i class="fas fa-database me-2" style="color: #6c757d;"></i>Sauvegarde des Données (ZIP)</h5>
                <div class="d-flex justify-content-center gap-3 flex-wrap backup-buttons">
                  <a href="{{ url_for('administrateur_bp.download_backup') }}" class="btn btn-warning">
                    <i class="fas fa-file-archive me-2" style="color: #FFFFFF;"></i><span class="full-text">Télécharger une sauvegarde (ZIP)</span><span class="abbr-text">Exporter ZIP</span>
                  </a>
                  <form action="{{ url_for('administrateur_bp.upload_backup') }}" method="POST" enctype="multipart/form-data" id="uploadBackupForm">
                      <input type="file" name="backup_file" id="backup_file_upload" accept=".zip" class="d-none">
                      <label for="backup_file_upload" class="btn btn-danger">
                          <i class="fas fa-upload me-2" style="color: #FFFFFF;"></i><span class="full-text">Importer une sauvegarde (ZIP)</span><span class="abbr-text">Importer ZIP</span>
                      </label>
                      <button type="submit" class="btn btn-danger" id="upload_button" style="display:none;">
                          <span id="upload_button_text"><i class="fas fa-arrow-up me-2"></i>Confirmer l'importation</span>
                          <span id="upload_spinner" class="spinner-border spinner-border-sm" role="status" aria-hidden="true" style="display:none;"></span>
                      </button>
                  </form>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

<div class="modal fade" id="editModal" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog">
      <form id="editForm" method="POST" class="modal-content" action="{{ url_for('administrateur_bp.edit_user') }}">
        <div class="modal-header"><h5 class="modal-title">Modifier l'utilisateur</h5><button class="btn-close btn-close-white" type="button" data-bs-dismiss="modal"></button></div>
        <div class="modal-body">
          <input type="hidden" name="email" id="editEmail">
          <div class="mb-3 floating-label">
            <input id="newEmail" name="new_email" type="email" class="form-control" placeholder=" " required>
            <label for="newEmail"><i class="fas fa-envelope me-2"></i>Adresse email</label>
          </div>
          <div class="mb-3 floating-label">
            <input id="newPassword" name="new_password" type="password" class="form-control" placeholder=" ">
            <label for="newPassword"><i class="fas fa-lock me-2"></i>Nouveau mot de passe</label>
          </div>
          <div class="mb-3 floating-label">
            <input id="confirmPassword" name="confirm_password" type="password" class="form-control" placeholder=" ">
            <label for="confirmPassword"><i class="fas fa-lock me-2"></i>Confirmer mot de passe</label>
          </div>
          <div class="mb-3 floating-label">
            <input id="editNom" name="nom" class="form-control" placeholder=" " required>
            <label for="editNom"><i class="fas fa-user me-2"></i>Nom</label>
          </div>
          <div class="mb-3 floating-label">
            <input id="editPrenom" name="prenom" class="form-control" placeholder=" " required>
            <label for="editPrenom"><i class="fas fa-user-tag me-2"></i>Prénom</label>
          </div>
          <div class="mb-3 floating-label">
            <input id="editPhone" name="phone" class="form-control" placeholder=" ">
            <label for="editPhone"><i class="fas fa-phone me-2"></i>Téléphone</label>
          </div>
          <div class="mb-3 floating-label">
            <select name="role" id="editRole" class="form-select" placeholder=" " required>
              <option value="medecin">Médecin</option>
              <option value="assistante">Assistante</option>
              <option value="comptable">Comptable</option>
              <option value="biologiste">Biologiste</option>
              <option value="radiologue">Radiologue</option>
              <option value="pharmacie/magasin">Pharmacie & Magasin</option>
            </select>
            <label for="editRole"><i class="fas fa-user-shield me-2"></i>Rôle</label>
          </div>
          <div class="mb-3 floating-label" id="editLinkedDoctorDiv" style="display: none;">
            <select name="linked_doctor" id="editLinkedDoctor" class="form-select" placeholder=" ">
              <option value="" disabled selected>Sélectionner un médecin...</option>
              <option value="">Aucun médecin lié</option>
              {% for doc in doctors %}<option value="{{ doc.email }}">{{ doc.prenom }} {{ doc.nom }}</option>{% endfor %}
            </select>
            <label for="editLinkedDoctor"><i class="fas fa-link me-2"></i>Médecin lié</label>
          </div>
          <div class="col-12 mb-3">
            <label class="form-label fw-semibold"><i class="fas fa-shield-alt me-2"></i>Autorisations d'accès :</label>
            <div class="checkbox-list" id="editAccessCheckboxes"></div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
          <button type="submit" class="btn btn-primary">Enregistrer</button>
        </div>
      </form>
    </div>
  </div>
  
  <footer class="text-center py-3">
    <p class="small mb-1" style="color: white;">
      <i class="fas fa-heartbeat me-1"></i>
      SASTOUKA DIGITAL © 2025 • sastoukadigital@gmail.com tel +212652084735
    </p>
  </footer>

  <div class="modal fade" id="importBackgroundModal" tabindex="-1">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title"><i class="fas fa-image me-2"></i>Importer Image</h5>
          <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body">
          <form id="importBackgroundForm" onsubmit="return ajaxFileUpload('importBackgroundForm','{{ url_for('administrateur_bp.import_image') }}')">
            <div class="mb-3">
              <label for="image_type" class="form-label"><i class="fas fa-cogs me-2"></i>Type d'image</label>
              <select class="form-select" name="image_type" id="image_type" required>
                <option value="background">Arrière-plan</option>
              </select>
            </div>
            <div class="mb-3">
              <label for="image_file_admin" class="form-label"><i class="fas fa-file-image me-2"></i>Fichier</label>
              <input type="file" class="form-control" name="image_file" id="image_file_admin" accept=".png,.jpg,.jpeg,.gif,.bmp,.pdf" required>
            </div>
            <div class="modal-footer">
              <button type="submit" class="btn btn-primary"><i class="fas fa-upload me-2"></i>Importer</button>
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>


<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
  <script src="https://cdn.datatables.net/1.13.1/js/jquery.dataTables.min.js"></script>
  <script src="https://cdn.datatables.net/1.13.1/js/dataTables.bootstrap5.min.js"></script>
  <script src="https://cdn.datatables.net/responsive/2.4.1/js/dataTables.responsive.min.js"></script>
  <script src="https://cdn.datatables.net/responsive/2.4.1/js/responsive.bootstrap5.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
  <script>
    // ──────────────────────────────────────────────────────────────────────────
    // 1. Fonctions d'assistance (Helpers)
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Affiche une alerte SweetAlert standardisée pour les réponses fetch.
     * @param {object} data - L'objet de réponse JSON du serveur (attend {status: '...', message: '...'})
     * @param {boolean} reloadOnSuccess - Si la page doit être rechargée en cas de succès.
     */
    function showFetchAlert(data, reloadOnSuccess = true) {
        Swal.fire({
            icon: data.status,
            title: data.status === "success" ? "Succès" : "Attention",
            text: data.message,
            timer: 2000,
            showConfirmButton: false
        }).then(() => {
            if (data.status === "success" && reloadOnSuccess) {
                // Utilise un timestamp pour forcer le rechargement depuis le serveur
                window.location.href = window.location.pathname + "?_t=" + new Date().getTime();
            }
        });
    }

    /**
     * Affiche une alerte SweetAlert pour les erreurs réseau.
     * @param {Error} error - L'objet d'erreur.
     */
    function showFetchError(error) {
        console.error("Erreur Fetch:", error);
        Swal.fire({
            icon: 'error',
            title: 'Erreur Réseau',
            text: `Impossible de contacter le serveur. Veuillez vérifier votre connexion. (${error.message})`
        });
    }
    
    /**
     * Méthode de repli (fallback) pour la copie dans le presse-papiers (pour HTTP).
     */
    function fallbackCopyTextToClipboard(text) {
        var textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.top = 0;
        textArea.style.left = 0;
        textArea.style.width = "1px";
        textArea.style.height = "1px";
        textArea.style.padding = 0;
        textArea.style.border = "none";
        textArea.style.outline = "none";
        textArea.style.boxShadow = "none";
        textArea.style.background = "transparent";
        
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            var successful = document.execCommand('copy');
            if (successful) {
                Swal.fire({icon: 'success', title: 'Copié!', text: 'Le lien a été copié.', timer: 2000, showConfirmButton: false});
            } else {
                Swal.fire({icon: 'error', title: 'Oups!', text: "La copie a échoué. Veuillez copier le lien manuellement.", timer: 2500, showConfirmButton: false});
            }
        } catch (err) {
            Swal.fire({icon: 'error', title: 'Erreur!', text: "Impossible de copier. Veuillez copier le lien manuellement.", timer: 2500, showConfirmButton: false});
        }
        
        document.body.removeChild(textArea);
    }

    /**
     * Copie du texte dans le presse-papiers (méthode moderne avec fallback).
     */
    window.copyToClipboard = function(text) {
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(() => {
                Swal.fire({icon: 'success', title: 'Copié!', text: 'Le lien a été copié.', timer: 1500, showConfirmButton: false});
            }, () => {
                fallbackCopyTextToClipboard(text); // Fallback si permission refusée
            });
        } else {
            fallbackCopyTextToClipboard(text); // Fallback pour HTTP
        }
    }

    /**
     * Gère l'upload de fichiers via Fetch et affiche le résultat.
     */
    window.ajaxFileUpload = function(formId, endpoint) {
        fetch(endpoint, {
            method: "POST", 
            body: new FormData(document.getElementById(formId))
        })
        .then(response => response.json())
        .then(data => showFetchAlert(data, true))
        .catch(showFetchError);
        return false; // Empêche la soumission traditionnelle du formulaire
    };

    /**
     * Génère les cases à cocher pour les permissions.
     */
    function generateCheckboxes(containerId, currentAllowedPages = [], isCreateForm = false, userRole = null) {
        const PERMISSION_BLUEPRINTS = ['rdv', 'routes', 'facturation', 'biologie', 'radiologie', 'pharmacie', 'comptabilite', 'statistique', 'gestion_patient', 'ia_assitant'];
        
        // Map pour des noms plus conviviaux
        const DISPLAY_NAME_MAP = {
            'routes': 'Consultations',
            'gestion_patient': 'Patients',
            'ia_assitant': 'Assistant IA',
            'rdv': 'Rendez-vous'
            // Les autres seront formatés par défaut (ex: 'Biologie')
        };

        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';

        PERMISSION_BLUEPRINTS.forEach(bp_name => {
            const div = document.createElement('div');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.name = 'allowed_pages[]';
            checkbox.value = bp_name;
            checkbox.id = `${isCreateForm ? 'create' : 'edit'}_access_${bp_name}`;

            if (isCreateForm) {
                // Logique pour le formulaire de *création*
                let defaultChecked = ['rdv', 'routes', 'facturation', 'biologie', 'radiologie', 'pharmacie', 'comptabilite', 'statistique', 'gestion_patient', 'ia_assitant'];
                if (userRole === 'medecin') {
                    defaultChecked = ['rdv', 'routes', 'biologie', 'radiologie', 'statistique', 'gestion_patient', 'ia_assitant'];
                }
                if (defaultChecked.includes(bp_name)) checkbox.checked = true;
            } else {
                // Logique pour le formulaire d' *édition*
                if (currentAllowedPages.includes(bp_name)) checkbox.checked = true;
            }

            if (userRole === 'admin') {
                checkbox.checked = true;
                checkbox.disabled = true;
            }

            const label = document.createElement('label');
            label.htmlFor = checkbox.id;
            
            let display_name = DISPLAY_NAME_MAP[bp_name] || bp_name.replace(/_/g, ' ').replace('bp', '').trim();
            if (!DISPLAY_NAME_MAP[bp_name]) {
                 display_name = display_name.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            }
            
            label.textContent = " " + display_name; // Ajoute un espace
            div.appendChild(checkbox);
            div.appendChild(label);
            container.appendChild(div);
        });
    }

    /**
     * Supprime une période d'indisponibilité.
     */
    window.deleteUnavailability = function(index) {
        Swal.fire({
            title: 'Êtes-vous sûr?', text: "Cette action est irréversible.", icon: 'warning',
            showCancelButton: true, confirmButtonColor: '#d33', confirmButtonText: 'Oui, supprimer!', cancelButtonText: 'Annuler'
        }).then((result) => {
            if (result.isConfirmed) {
                const formData = new FormData();
                formData.append('action', 'delete');
                formData.append('index', index);
                
                fetch('{{ url_for('administrateur_bp.manage_unavailability') }}', {method: 'POST', body: formData})
                .then(response => response.json())
                .then(data => showFetchAlert(data, true))
                .catch(showFetchError);
            }
        });
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 2. Initialisation (DOMContentLoaded)
    // ──────────────────────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
      
      // Initialisation de la table des utilisateurs
      try {
          new DataTable('#usersTable', {
              responsive: true,
              lengthChange: true,
              language: { url: "//cdn.datatables.net/plug-ins/1.13.1/i18n/fr-FR.json" }
          });
      } catch (e) {
          console.error("Impossible d'initialiser DataTable:", e);
      }
      
      // Génération des cases à cocher initiales pour la création
      generateCheckboxes('createAccessCheckboxes', [], true, document.getElementById('createRole').value);
      
      // --- Gestionnaires d'événements (Event Listeners) ---

      // Toggle l'affichage du champ "Médecin lié" (Création)
      document.getElementById('createRole').addEventListener('change', function() {
          document.getElementById('createLinkedDoctorDiv').style.display = this.value === 'assistante' ? 'block' : 'none';
          generateCheckboxes('createAccessCheckboxes', [], true, this.value);
      });

      // Toggle l'affichage du champ "Médecin lié" (Édition)
      document.getElementById('editRole').addEventListener('change', function() {
          document.getElementById('editLinkedDoctorDiv').style.display = this.value === 'assistante' ? 'block' : 'none';
          generateCheckboxes('editAccessCheckboxes', [], false, this.value);
      });

      // Délégation d'événement pour le bouton "Modifier"
      $('#usersTable tbody').on('click', '.editBtn', function(e) {
          e.preventDefault();
          const email = $(this).data('email');
          fetch(`/administrateur/users/${encodeURIComponent(email)}`)
              .then(response => {
                  if (!response.ok) throw new Error('Utilisateur non trouvé');
                  return response.json();
              })
              .then(u => {
                  if (!u || Object.keys(u).length === 0) {
                      showFetchError({message: "Les détails de l'utilisateur sont vides."});
                      return;
                  }
                  document.getElementById('editEmail').value = email;
                  document.getElementById('newEmail').value = email;
                  document.getElementById('editNom').value = u.nom || '';
                  document.getElementById('editPrenom').value = u.prenom || '';
                  document.getElementById('editPhone').value = u.phone || '';
                  document.getElementById('editRole').value = u.role || 'assistante';
                  
                  const editLinkedDoctorDiv = document.getElementById('editLinkedDoctorDiv');
                  editLinkedDoctorDiv.style.display = u.role === 'assistante' ? 'block' : 'none';
                  if (u.role === 'assistante') {
                      document.getElementById('editLinkedDoctor').value = u.linked_doctor || '';
                  }
                  
                  generateCheckboxes('editAccessCheckboxes', u.allowed_pages || [], false, u.role);
                  new bootstrap.Modal(document.getElementById('editModal')).show();
              })
              .catch(showFetchError);
      });

      // Délégation d'événement pour le bouton "Supprimer"
      $('#usersTable tbody').on('click', '.btn-danger[title="Supprimer"]', function(e) {
          e.preventDefault();
          const email = $(this).data('email');
          Swal.fire({
              title: 'Êtes-vous sûr?', text: `Supprimer ${email} est irréversible!`, icon: 'warning',
              showCancelButton: true, confirmButtonColor: '#d33', confirmButtonText: 'Oui, supprimer!', cancelButtonText: 'Annuler'
          }).then((result) => {
              if (result.isConfirmed) {
                  window.location.href = `{{ url_for('administrateur_bp.delete_user', user_email='PLACEHOLDER') }}`.replace('PLACEHOLDER', encodeURIComponent(email));
              }
          });
      });

      // Soumission du formulaire d'édition (MODAL)
      document.getElementById('editForm').addEventListener('submit', function(e) {
          e.preventDefault();
          fetch(e.target.action, { method: 'POST', body: new FormData(e.target) })
              .then(response => {
                  // Le rechargement de la page gérera le flash message de Flask
                  if (response.ok) {
                      window.location.reload();
                  } else {
                      throw new Error('La mise à jour a échoué.');
                  }
              })
              .catch(showFetchError);
      });

      // Affichage du bouton de confirmation d'upload (Backup)
      document.getElementById('backup_file_upload').addEventListener('change', function() {
          document.getElementById('upload_button').style.display = this.files.length > 0 ? 'inline-flex' : 'none';
      });

      // Affichage du spinner lors de l'upload (Backup)
      document.getElementById('uploadBackupForm').addEventListener('submit', function() {
          const btn = document.getElementById('upload_button');
          btn.querySelector('#upload_button_text').style.display = 'none';
          btn.querySelector('#upload_spinner').style.display = 'inline-block';
          btn.disabled = true;
      });
      
      // Soumission du formulaire d'indisponibilité
      document.getElementById('addUnavailabilityForm').addEventListener('submit', function(e) {
          e.preventDefault();
          fetch('{{ url_for('administrateur_bp.manage_unavailability') }}', {method: 'POST', body: new FormData(this)})
              .then(response => response.json())
              .then(data => showFetchAlert(data, true))
              .catch(showFetchError);
      });

      // Soumission du formulaire des paramètres généraux
      document.getElementById('mainSettingsForm').addEventListener('submit', function(e) {
          e.preventDefault();
          fetch(e.target.action, { method: 'POST', body: new FormData(e.target) })
              .then(r => r.json())
              .then(data => showFetchAlert(data, true))
              .catch(showFetchError);
      });
      
      // Soumission du formulaire des listes (Médicaments, etc.)
      document.getElementById('listsSettingsForm').addEventListener('submit', function(e) {
          e.preventDefault();
          fetch(e.target.action, { method: 'POST', body: new FormData(e.target) })
              .then(r => r.json())
              .then(data => showFetchAlert(data, true))
              .catch(showFetchError);
      });

    });
  </script>
  {% include '_floating_assistant.html' %}
</body>
</html>
"""