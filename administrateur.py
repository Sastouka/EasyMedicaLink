# administrateur.py
# ──────────────────────────────────────────────────────────────────────────────
# Module d'administration centralisé pour EasyMedicaLink.
# Gère les utilisateurs, les licences, les paramètres de l'application,
# l'accès patient, les indisponibilités et les opérations de base de données.
#
# Améliorations clés :
# - Regroupement des vérifications d'autorisation via un décorateur @admin_required.
# - Intégration des fonctions auxiliaires directement dans le module pour un fichier unique.
# - Utilisation d'un template HTML intégré pour l'interface.
# - Routes RESTful pour une meilleure clarté et maintenabilité.
# - Commentaires détaillés pour chaque section et fonction.
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

# Internal module imports
import theme
import utils
import login # Import the entire login module to access ALL_BLUEPRINTS

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

# Define default roles and their limits
# MODIFICATION: All account limits are set to infinity to remove the limitation.
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
    """
    Decorator to ensure that only a logged-in user with the 'admin' role
    can access the route. Redirects to the login page if unauthorized.
    """
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
    """
    Generic decorator to ensure that a logged-in user has one of the allowed roles.
    Redirects to the home page with an error message if unauthorized.
    """
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
    """
    Retrieves the license plan of the logged-in administrator.
    Uses session information to load user data.
    """
    mapping = {
        f"essai_{TRIAL_DAYS}jours": f"Essai ({TRIAL_DAYS} jours)",
        "1 mois":   "1 mois",
        "1 an":     "1 an",
        "illimité": "Illimité",
    }
    # login.load_users() charge maintenant depuis le fichier centralisé
    user = login.load_users().get(session.get("email"))
    plan_raw = (
        user.get("activation", {}).get("plan", "").lower()
        if user else ""
    )
    return mapping.get(plan_raw, plan_raw.capitalize() or "Inconnu")

def generate_qr_code_data_uri(data: str) -> str:
    """
    Generates a QR code for the provided data and returns it as a data URI (base64).
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"

def get_admin_dashboard_context():
    """
    Prepares the data context for the administrator dashboard.
    Includes users, role limits, appointment booking links, etc.
    """
    admin_email = session['email']
    # login.load_users() charge maintenant tous les utilisateurs depuis le fichier centralisé
    full_users = login.load_users()

    # Prepares users for the table, ensuring all keys are present
    users_for_table = []
    # Initializes role counts with default keys
    current_role_counts = {role: 0 for role in DEFAULT_ROLE_LIMITS.keys()}

    for e, u in full_users.items():
        # Displays only users belonging to the current administrator
        # Et exclut l'administrateur lui-même du tableau
        if u.get('owner') == admin_email and e != admin_email:
            role = u.get('role', '')
            if role in current_role_counts:
                current_role_counts[role] += 1

            user_info = {
                'email': e,
                'nom': u.get('nom', ''),
                'prenom': u.get('prenom', ''),
                'role': role,
                'active': u.get('active', False),
                'phone': u.get('phone', ''),
                'linked_doctor': u.get('linked_doctor', ''),
                'allowed_pages': u.get('allowed_pages', [])
            }
            users_for_table.append(user_info)

    config = utils.load_config()
    # Loads configurable role limits, or uses default values
    role_limits_from_config = config.get('role_limits', DEFAULT_ROLE_LIMITS)

    # Updates current counts in the loaded role limits
    display_role_limits = {}
    for role, limits in role_limits_from_config.items():
        display_role_limits[role] = {
            "current": current_role_counts.get(role, 0),
            "max": "Illimité" if limits["max"] == float('inf') else limits["max"]
        }
    # Ensures all default roles are present even if not in config
    for role, default_limits in DEFAULT_ROLE_LIMITS.items():
        if role not in display_role_limits:
            display_role_limits[role] = {
                "current": current_role_counts.get(role, 0),
                "max": "Illimité" if default_limits["max"] == float('inf') else default_limits["max"]
            }

    current_date = datetime.now().strftime("%Y-%m-%d")

    # Retrieves available background files for the settings form
    backgrounds_folder = utils.BACKGROUND_FOLDER
    backgrounds = []
    logos = []
    if os.path.exists(backgrounds_folder):
        for f in os.listdir(backgrounds_folder):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                backgrounds.append(f)
                logos.append(f)

    # Generates a single patient appointment link and QR code for the administrator
    admin_email_prefix = admin_email.split('@')[0]

    # The general appointment booking link for the clinic (not specific to a doctor)
    # Ensure that the 'patient_rdv.patient_rdv_home' route can handle an 'admin_prefix' parameter without 'doctor_email'
    patient_appointment_link = url_for('patient_rdv.patient_rdv_home', admin_prefix=admin_email_prefix, _external=True)
    qr_code_data_uri = generate_qr_code_data_uri(patient_appointment_link)

    # Retrieves the list of doctors to link assistants (remains unchanged)
    doctors = [u for u in users_for_table if u['role'] == 'medecin' and u['active']]
    # Also include the main admin as a doctor
    main_admin = full_users.get(admin_email)
    if main_admin:
        doctors.append({'email': admin_email, 'nom': main_admin.get('nom', ''), 'prenom': main_admin.get('prenom', '')})
    
    # Sort doctors list
    doctors = sorted(doctors, key=lambda d: (d.get('prenom', ''), d.get('nom', '')))

    # Loads executable filenames
    static_folder = current_app.static_folder
    win64_filename = next((f for f in os.listdir(static_folder) if f.startswith('EasyMedicaLink-Win64.exe')), None)
    win32_filename = next((f for f in os.listdir(static_folder) if f.startswith('EasyMedicaLink-Win32.exe')), None)

    return {
        "users": users_for_table,
        "config": config,
        "current_date": current_date,
        "theme_vars": theme.current_theme(),
        "theme_names": list(theme.THEMES.keys()),
        "plan": get_current_plan_info(),
        "admin_email": admin_email,
        "win64_filename": win64_filename,
        "win32_filename": win32_filename,
        "backgrounds": backgrounds,
        "logos": logos,
        "patient_appointment_link": patient_appointment_link, # Unique link
        "qr_code_data_uri": qr_code_data_uri, # Unique QR code
        "doctors": doctors, # Still needed for creating/modifying assistants
        "role_limits": display_role_limits,
        "DEFAULT_ROLE_LIMITS": DEFAULT_ROLE_LIMITS,
        "all_blueprints": login.ALL_BLUEPRINTS, # Passer la liste complète des blueprints disponibles
        # NOUVEAU : Passer les listes de médicaments, analyses, radiologies pour les textareas
        "medications_options": config.get('medications_options', utils.default_medications_options),
        "analyses_options": config.get('analyses_options', utils.default_analyses_options),
        "radiologies_options": config.get('radiologies_options', utils.default_radiologies_options)
    }

# ──────────────────────────────────────────────────────────────────────────────
# 3. User Management Functions
# ──────────────────────────────────────────────────────────────────────────────
def get_user_details(user_email: str) -> dict:
    """Retrieves the details of a specific user belonging to the current administrator."""
    # login.load_users() charge maintenant depuis le fichier centralisé
    u = login.load_users().get(user_email)
    if not u or u.get('owner') != session.get('email'):
        return {}
    return {
        'nom': u.get('nom', ''),
        'prenom': u.get('prenom', ''),
        'role': u.get('role', ''),
        'phone': u.get('phone', ''),
        'linked_doctor': u.get('linked_doctor', ''),
        'allowed_pages': u.get('allowed_pages', []) # Récupérer les pages autorisées
    }

def create_new_user(form_data: dict) -> tuple[bool, str]:
    """Creates a new user account with necessary validations."""
    admin_email = session['email']
    nom = form_data['nom'].strip()
    prenom = form_data['prenom'].strip()
    role = form_data['role'].strip()
    password = form_data['password'].strip()
    phone = form_data.get('phone', '').strip()
    linked_doctor = form_data.get('linked_doctor', '').strip()
    
    # NOUVEAU: Récupérer les pages autorisées du formulaire
    allowed_pages = form_data.getlist('allowed_pages[]')
    
    admin_email_prefix = admin_email.split('@')[0]

    # Build the new user's email with the convention
    if role in ['medecin', 'assistante']:
        key = f"{prenom.lower()}.{nom.lower()}@{admin_email_prefix}.eml.com"
    else:
        key = f"{prenom.lower()}.{nom.lower()}@{admin_email_prefix}.eml-o.com"# Example convention

    cfg = utils.load_config()
    role_limits_config = cfg.get('role_limits', DEFAULT_ROLE_LIMITS)

    # login.load_users() charge maintenant tous les utilisateurs depuis le fichier centralisé
    users_owned_by_admin = [u for u in login.load_users().values() if u.get('owner') == admin_email]
    current_role_count = sum(1 for u in users_owned_by_admin if u.get('role') == role)

    # MODIFICATION: The limit check is always satisfied because max is float('inf')
    if current_role_count >= role_limits_config.get(role, {}).get('max', float('inf')):
        return False, f"Limite de comptes atteinte pour le rôle '{role}'."

    # Utilise la fonction _is_email_globally_unique centralisée de login.py
    if not login._is_email_globally_unique(key):
        return False, f"L'e-mail '{key}' est déjà utilisé par un autre compte."

    users = login.load_users()

    user_data = {
        'nom':      nom,
        'prenom':   prenom,
        'role':     role,
        'password': login.hash_password(password),
        'active':   True,
        'owner':    admin_email,
        'phone':    phone,
        'allowed_pages': allowed_pages # NOUVEAU: Enregistrer les pages autorisées
    }
    
    # Pour les rôles non-admin, assurez-vous que 'accueil' est toujours inclus
    if role != 'admin' and 'accueil' not in user_data['allowed_pages']:
        user_data['allowed_pages'].append('accueil')

    # NOUVEAU: Si le rôle est admin, il a toutes les permissions
    if role == 'admin':
        user_data['allowed_pages'] = login.ALL_BLUEPRINTS

    if role == 'assistante':
        user_data['linked_doctor'] = linked_doctor
    else:
        user_data.pop('linked_doctor', None) # Removes the link if the role is not assistant

    users[key] = user_data
    login.save_users(users) # Sauvegarde dans le fichier centralisé

    # Temporary assistant creation logic for a new doctor
    if role == 'medecin':
        existing_assistants_for_doctor = [
            u for u_email, u in users.items()
            if u.get('role') == 'assistante' and u.get('linked_doctor') == key
        ]
        if not existing_assistants_for_doctor:
            temp_assistant_email = f"assist.{prenom.lower()}.{nom.lower()}@{admin_email_prefix}.eml.com"
            # Utilise la fonction _is_email_globally_unique centralisée de login.py
            if login._is_email_globally_unique(temp_assistant_email):
                current_assistant_count = sum(1 for u in users_owned_by_admin if u.get('role') == 'assistante')
                # MODIFICATION: The limit check is always satisfied because max is float('inf')
                if current_assistant_count < role_limits_config.get('assistante', {}).get('max', float('inf')):
                    users[temp_assistant_email] = {
                        'nom': 'Temporaire',
                        'prenom': 'Assistante',
                        'role': 'assistante',
                        'password': login.hash_password('password'),
                        'active': True,
                        'owner': admin_email,
                        'phone': '',
                        'linked_doctor': key,
                        'allowed_pages': ['rdv', 'routes', 'facturation', 'patient_rdv', 'accueil'] # Default pages for assistant + accueil + routes (consultation)
                    }
                    login.save_users(users) # Sauvegarde dans le fichier centralisé
                    flash(f"Une assistante temporaire ({temp_assistant_email}) a été créée pour le médecin {prenom} {nom}.", "info")
                else:
                    flash(f"Impossible de créer une assistante temporaire pour le médecin {prenom} {nom} : limite d'assistantes atteinte.", "warning")
            else:
                flash(f"Impossible de créer une assistante temporaire pour le médecin {prenom} {nom} : l'e-mail temporaire est déjà utilisé.", "warning")

    return True, "Compte créé avec succès !"

def update_existing_user(form_data: dict) -> tuple[bool, str]:
    """Updates an existing user account."""
    old_email = form_data['email']
    new_email = form_data.get('new_email', old_email).strip().lower()
    new_password = form_data.get('new_password', '').strip() # Récupère le nouveau mot de passe
    confirm_password = form_data.get('confirm_password', '').strip() # Récupère la confirmation

    
    # NOUVEAU: Récupérer les pages autorisées du formulaire
    allowed_pages = form_data.getlist('allowed_pages[]')

    users = login.load_users() # Charge depuis le fichier centralisé

    if old_email not in users or users[old_email].get('owner') != session.get('email'):
        return False, "Action non autorisée."

    user = users.pop(old_email)

    # Utilise la fonction _is_email_globally_unique centralisée de login.py
    if new_email != old_email and not login._is_email_globally_unique(new_email):
        users[old_email] = user # Remet l'utilisateur si le nouvel email est déjà pris
        login.save_users(users) # Sauvegarde dans le fichier centralisé
        return False, f"Le nouvel e-mail '{new_email}' est déjà utilisé par un autre compte dans le système."

    # Update user data
    user['nom'] = form_data['nom'].strip()
    user['prenom'] = form_data['prenom'].strip()
    user['role'] = form_data['role'].strip()
    user['phone'] = form_data.get('phone', '').strip()
    user['allowed_pages'] = allowed_pages # NOUVEAU: Enregistrer les pages autorisées
    
    # Pour les rôles non-admin, assurez-vous que 'accueil' est toujours inclus
    if user['role'] != 'admin' and 'accueil' not in user['allowed_pages']:
        user['allowed_pages'].append('accueil')

    # NOUVEAU: Si le rôle est admin, il a toutes les permissions
    if user['role'] == 'admin':
        user['allowed_pages'] = login.ALL_BLUEPRINTS

    if user['role'] == 'assistante':
        user['linked_doctor'] = form_data.get('linked_doctor', '').strip()
    else:
        user.pop('linked_doctor', None) # Removes the link if the role is not assistant

    if new_password: # Si un nouveau mot de passe a été fourni
        if new_password != confirm_password: # Vérifie la correspondance
            return False, "Les mots de passe ne correspondent pas."
        user['password'] = login.hash_password(new_password) # Hache et stocke le nouveau mot de passe

    users[new_email] = user # Adds the user with the new email or the original email
    login.save_users(users) # Sauvegarde les utilisateurs
    return True, "Données utilisateur mises à jour avec succès."

def toggle_user_active_status(user_email: str) -> tuple[bool, str]:
    """Toggles a user's active/inactive status."""
    users = login.load_users() # Charge depuis le fichier centralisé
    if user_email in users and users[user_email].get('owner') == session.get('email'):
        users[user_email]['active'] = not users[user_email].get('active', True)
        login.save_users(users) # Sauvegarde dans le fichier centralisé
        return True, f"Statut de l'utilisateur {user_email} mis à jour."
    return False, "Utilisateur introuvable ou action non autorisée."

def delete_existing_user(user_email: str) -> tuple[bool, str]:
    """Deletes a user account."""
    users = login.load_users() # Charge depuis le fichier centralisé
    if user_email in users and users[user_email].get('owner') == session.get('email'):
        users.pop(user_email)
        login.save_users(users) # Sauvegarde dans le fichier centralisé
        return True, f"Utilisateur {user_email} supprimé avec succès."
    return False, "Utilisateur introuvable ou action non autorisée."

# ──────────────────────────────────────────────────────────────────────────────
# 4. Excel Data Management Functions
# ──────────────────────────────────────────────────────────────────────────────
def handle_excel_download() -> tuple[io.BytesIO, str]:
    """Generates a single Excel file containing all administrator data."""
    # S'assurer que utils.EXCEL_FOLDER est défini avant de l'utiliser
    admin_email = session.get('admin_email')
    if admin_email is None:
        raise ValueError("Email administrateur non trouvé en session. Impossible de déterminer le répertoire d'exportation.")

    utils.set_dynamic_base_dir(admin_email) # <-- AJOUT IMPORTANT ICI

    if utils.EXCEL_FOLDER is None:
        raise ValueError("Le répertoire Excel n'est pas défini après l'initialisation. Impossible de procéder à l'export.")

    df_map = _load_all_excels(utils.EXCEL_FOLDER)

    if not df_map:
        raise ValueError("Aucun fichier Excel trouvé pour l'export dans le répertoire de l'administrateur.")

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        for filename, data_content in df_map.items(): # data_content peut être un DataFrame ou un dict de DataFrames
            if isinstance(data_content, pd.DataFrame):
                # Si c'est un DataFrame simple (fichier Excel à une seule feuille)
                sheet_name = filename.replace(".xlsx", "").replace(".xls", "")
                sheet_name = "".join(c for c in sheet_name if c.isalnum() or c in [' ', '_', '-'])
                sheet_name = sheet_name[:31] or "Sheet" # Assure un nom de feuille non vide
                data_content.to_excel(writer, sheet_name=sheet_name, index=False)
            elif isinstance(data_content, dict):
                # Si c'est un dictionnaire de DataFrames (fichier Excel à plusieurs feuilles)
                for sheet_name_in_file, df_sheet in data_content.items():
                    # Nettoyer et tronquer le nom de la feuille
                    cleaned_sheet_name = "".join(c for c in sheet_name_in_file if c.isalnum() or c in [' ', '_', '-'])
                    cleaned_sheet_name = cleaned_sheet_name[:31] or "Sheet" + str(len(writer.sheets) + 1)
                    if not df_sheet.empty: # S'assurer que le DataFrame de la feuille n'est pas vide
                        df_sheet.to_excel(writer, sheet_name=cleaned_sheet_name, index=False)
                    else:
                        # Créer une feuille vide si le DataFrame est vide
                        pd.DataFrame().to_excel(writer, sheet_name=cleaned_sheet_name, index=False)
            else:
                print(f"AVERTISSEMENT: Type de données inattendu pour '{filename}': {type(data_content)}. Ignoré pour l'exportation.")
                continue # Passer à l'élément suivant dans df_map

    buffer.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"EasyMedicaLink_Donnees_Excel_{timestamp}.xlsx"
    return buffer, filename

def handle_excel_upload(uploaded_file) -> tuple[bool, str]:
    """Imports an Excel file and updates existing databases."""
    if not uploaded_file or uploaded_file.filename == '':
        return False, "Aucun fichier sélectionné."

    if not (uploaded_file.filename.lower().endswith('.xlsx') or uploaded_file.filename.lower().endswith('.xls')):
        return False, "Type de fichier non supporté. Veuillez uploader un fichier Excel (.xlsx ou .xls)."

    try:
        # Lire toutes les feuilles du fichier importé
        imported_dfs = pd.read_excel(uploaded_file.stream, sheet_name=None)
        updated_count = 0
        
        # Définir les chemins des fichiers de destination
        comptabilite_path = os.path.join(utils.EXCEL_FOLDER, 'Comptabilite.xlsx')
        pharmacie_path = os.path.join(utils.EXCEL_FOLDER, 'Pharmacie.xlsx')
        factures_path = os.path.join(utils.EXCEL_FOLDER, 'factures.xlsx')
        
        # Définir les mappings des noms de feuilles vers les chemins de fichiers
        # pour s'assurer que les données sont sauvegardées au bon endroit.
        sheet_to_file_mapping = {
            'Recettes': comptabilite_path,
            'Depenses': comptabilite_path,
            'Salaires': comptabilite_path,
            'TiersPayants': comptabilite_path,
            'DocumentsFiscaux': comptabilite_path,
            'Inventaire': pharmacie_path,
            'Mouvements': pharmacie_path,
            'Factures': factures_path,
            # Ajoutez d'autres mappings si nécessaire
        }
        
        for sheet_name, df_imported in imported_dfs.items():
            # Chercher le fichier de destination pour la feuille actuelle
            destination_file = sheet_to_file_mapping.get(sheet_name)
            
            if destination_file:
                # Charger toutes les feuilles du fichier de destination
                if os.path.exists(destination_file):
                    all_sheets = pd.read_excel(destination_file, sheet_name=None)
                else:
                    all_sheets = {}
                
                # Remplacer la feuille existante par la feuille importée
                all_sheets[sheet_name] = df_imported
                
                # Sauvegarder toutes les feuilles dans le fichier de destination
                with pd.ExcelWriter(destination_file, engine='openpyxl') as writer:
                    for name, df in all_sheets.items():
                        df.to_excel(writer, sheet_name=name, index=False)
                
                updated_count += 1
                
            else:
                print(f"AVERTISSEMENT: La feuille '{sheet_name}' n'a pas de fichier de destination défini. Elle sera ignorée.")

        if updated_count > 0:
            return True, f"{updated_count} feuille(s) Excel mise(s) à jour avec succès."
        return False, "Aucune feuille de calcul correspondante n'a été trouvée pour la mise à jour."

    except Exception as e:
        return False, f"Erreur lors de l'importation du fichier Excel : {e}"

def handle_image_upload(image_file, image_type: str) -> tuple[bool, str]:
    """Imports an image (logo or background) and updates the configuration."""
    if not image_file or image_file.filename == "":
        return False, "Aucun fichier sélectionné pour l'image."

    filename = secure_filename(image_file.filename)
    path = os.path.join(utils.BACKGROUND_FOLDER, filename)

    try:
        image_file.save(path)
        ext = os.path.splitext(filename)[1].lower()
        # MODIFICATION HERE: Added '.pdf' for file acceptance
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".pdf"):
            os.remove(path)
            return False, "Format non supporté (seuls PNG, JPG, JPEG, GIF, BMP, PDF sont acceptés)."
        
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
        utils.init_app(current_app._get_current_object()) # Updates global variables of utils

        return True, message
    except Exception as e:
        return False, f"Erreur lors de l'importation de l'image : {e}"

# ──────────────────────────────────────────────────────────────────────────────
# 5. Unavailability Management Functions
# ──────────────────────────────────────────────────────────────────────────────
def manage_unavailability_periods(form_data: dict) -> tuple[bool, str]:
    """Manages adding or deleting unavailability periods."""
    action = form_data.get('action')
    config = utils.load_config()
    unavailability = config.get('unavailability_periods', [])

    if action == 'add':
        start_date_str = form_data.get('start_date')
        end_date_str = form_data.get('end_date')
        reason = form_data.get('reason', '').strip()

        if not start_date_str or not end_date_str:
            return False, "Les dates de début et de fin sont requises."

        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            if start_date > end_date:
                return False, "La date de début ne peut pas être postérieure à la date de fin."

            unavailability.append({
                'start_date': start_date_str,
                'end_date': end_date_str,
                'reason': reason
            })
            config['unavailability_periods'] = unavailability
            utils.save_config(config)
            return True, "Période d'indisponibilité ajoutée avec succès."
        except ValueError:
            return False, "Format de date invalide. Utilisez AAAA-MM-JJ."
        except Exception as e:
            return False, f"Erreur lors de l'ajout: {e}"

    elif action == 'delete':
        index_to_delete = form_data.get('index', type=int)
        if 0 <= index_to_delete < len(unavailability):
            unavailability.pop(index_to_delete)
            config['unavailability_periods'] = unavailability
            utils.save_config(config)
            return True, "Période d'indisponibilité supprimée avec succès."
        else:
            return False, "Index d'indisponibilité invalide."

    return False, "Action non reconnue."
 
# NOUVEAU : Fonctions de gestion du fichier Liste_Medications_Analyses_Radiologies.xlsx
def handle_medication_list_download() -> tuple[io.BytesIO, str]:
    """Prépare le fichier Liste_Medications_Analyses_Radiologies.xlsx pour le téléchargement."""
    if not os.path.exists(utils.LISTS_FILE):
        # Si le fichier n'existe pas, le créer avec les listes par défaut
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
            raise ValueError(f"Erreur lors de la création du fichier de listes par défaut : {e}")

    buffer = io.BytesIO()
    try:
        with open(utils.LISTS_FILE, 'rb') as f:
            buffer.write(f.read())
        buffer.seek(0)
        return buffer, os.path.basename(utils.LISTS_FILE)
    except Exception as e:
        raise ValueError(f"Erreur lors du chargement du fichier de listes pour le téléchargement : {e}")

def handle_medication_list_upload(uploaded_file) -> tuple[bool, str]:
    """Importe et met à jour le fichier Liste_Medications_Analyses_Radiologies.xlsx."""
    if not uploaded_file or uploaded_file.filename == '':
        return False, "Aucun fichier sélectionné."

    if not (uploaded_file.filename.endswith('.xlsx') or uploaded_file.filename.endswith('.xls')):
        return False, "Type de fichier non supporté. Veuillez uploader un fichier Excel (.xlsx ou .xls)."

    try:
        # Sauvegarder le fichier temporairement pour le traitement
        temp_path = os.path.join(utils.CONFIG_FOLDER, secure_filename(uploaded_file.filename))
        uploaded_file.save(temp_path)

        # Lire le fichier Excel et extraire les données des feuilles
        xls = pd.ExcelFile(temp_path)
        
        # Mettre à jour les listes dans la configuration si les feuilles existent
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
            # Mettre à jour le fichier physique LISTS_FILE également, pour la cohérence
            df_meds_to_save = pd.DataFrame({'Médicaments': config.get('medications_options', [])})
            df_analyses_to_save = pd.DataFrame({'Analyses': config.get('analyses_options', [])})
            df_radios_to_save = pd.DataFrame({'Radiologies': config.get('radiologies_options', [])})

            with pd.ExcelWriter(utils.LISTS_FILE, engine='xlsxwriter') as writer:
                df_meds_to_save.to_excel(writer, sheet_name='Médicaments', index=False)
                df_analyses_to_save.to_excel(writer, sheet_name='Analyses', index=False)
                df_radios_to_save.to_excel(writer, sheet_name='Radiologies', index=False)

            os.remove(temp_path) # Supprimer le fichier temporaire
            utils.init_app(current_app._get_current_object()) # Re-initialiser pour charger les nouvelles valeurs
            return True, "Listes de médicaments, analyses et radiologies mises à jour avec succès."
        else:
            os.remove(temp_path)
            return False, "Le fichier Excel importé ne contient pas les feuilles 'Médicaments', 'Analyses' ou 'Radiologies' avec les colonnes attendues."

    except Exception as e:
        return False, f"Erreur lors de l'importation du fichier de listes : {e}"  

# ──────────────────────────────────────────────────────────────────────────────
# 6. Integrated HTML Template
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

    /* KPI Cards */
    .kpi-card {
      background: var(--card-bg);
      border: 2px solid var(--primary-color); /* Use primary color for border */
      border-radius: var(--border-radius-md);
      transition: transform .2s ease, box-shadow .2s ease;
      box-shadow: var(--shadow-light);
    }
    .kpi-card:hover {
      transform: translateY(-5px);
      box-shadow: var(--shadow-medium);
    }
    .kpi-value {
      font-size: 2.2rem;
      font-weight: 700;
      color: var(--primary-color); /* Use primary color for value */
    }
    .kpi-label {
      font-size: 1rem;
      color: var(--text-color);
    }

    /* Chart Cards */
    .chart-card {
      background: var(--card-bg);
      border-radius: var(--border-radius-lg);
      box-shadow: var(--shadow-light);
      border: none;
    }
    .chart-card .card-header {
      background: var(--secondary-color) !important; /* Use secondary color for chart headers */
      color: var(--button-text) !important;
      border-top-left-radius: var(--border-radius-lg);
      border-top-right-radius: var(--border-radius-lg);
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
      box-shadow: var(--shadow-light); /* Added consistent shadow */
    }
    .btn:hover {
      box-shadow: var(--shadow-medium); /* Added consistent hover shadow */
      transform: translateY(-2px); /* Subtle lift on hover */
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
      background: var(--gradient-main); /* Keep gradient on hover */
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
    .btn-info { /* WhatsApp button */
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

    /* Icon Cards - Kept for potential future use or if user changes mind, but not actively used in admin dashboard currently */
    .icon-card {
      flex: 1 1 170px;
      max-width: 180px;
      color: var(--primary-color);
      padding: 0.5rem;
      text-decoration: none;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .icon-card:hover {
      transform: translateY(-5px);
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
      transition: all 0.2s ease;
    }
    .icon-card:hover .border {
      border-color: var(--primary-color) !important;
    }

    /* Floating Labels for Forms */
    .form-control:focus ~ label,
    .form-control:not(:placeholder-shown) ~ label,
    .form-select:focus ~ label,
    .form-select:not([value=""]) ~ label { /* For select with a default empty option */
      transform: translateY(-1.5rem) scale(0.8);
      font-size: 0.75rem;
      color: var(--primary-color);
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
      background-color: var(--card-bg); /* To hide text under label */
      color: var(--text-color);
      display: flex;
      align-items: center;
      gap: 0.25rem;
      height: calc(1.5em + 0.75rem + 0.75rem); /* Match input height */
    }
    .floating-label input, .floating-label select, .floating-label textarea {
        padding-top: 1.5rem; /* Ensure space for label */
        background-color: var(--input-bg) !important; /* Consistent input background */
        color: var(--text-color) !important;
        border-color: var(--border-color) !important;
        border-radius: var(--border-radius-md);
    }
    .floating-label input:focus, .floating-label select:focus, .floating-label textarea:focus {
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 0.25rem rgba(var(--primary-color-rgb), 0.25);
    }


    /* DataTables */
    #usersTable_wrapper .dataTables_filter input,
    #usersTable_wrapper .dataTables_length select {
      border-radius: var(--border-radius-sm);
      border: 1px solid var(--secondary-color);
      padding: 0.5rem 0.75rem;
      background-color: var(--card-bg);
      color: var(--text-color);
    }
    #usersTable_wrapper .dataTables_filter input:focus,
    #usersTable_wrapper .dataTables_length select:focus {
      border-color: var(--primary-color);
      box-shadow: 0 0 0 0.25rem rgba(var(--primary-color-rgb), 0.25);
    }
    /* Hide the dropdown arrow for DataTables length select */
    #usersTable_wrapper .dataTables_length select {
      -webkit-appearance: none;
      -moz-appearance: none;
      appearance: none;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath fill='none' stroke='%23333' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M2 5l6 6 6-6'/%3E%3Csvg%3E");
      background-repeat: no-repeat;
      background-position: right 0.75rem center;
      background-size: 0.65em auto;
      padding-right: 2rem;
    }
    body.dark-theme #usersTable_wrapper .dataTables_length select {
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath fill='none' stroke='%23fff' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M2 5l6 6 6-6'/%3E%3Csvg%3E");
    }


    #usersTable_wrapper .dataTables_paginate .pagination .page-item .page-link {
      border-radius: var(--border-radius-sm);
      margin: 0 0.2rem;
      background-color: var(--card-bg);
      color: var(--text-color);
      border: 1px solid var(--secondary-color);
    }
    #usersTable_wrapper .dataTables_paginate .pagination .page-item.active .page-link {
      background: var(--gradient-main);
      border-color: var(--primary-color);
      color: var(--button-text);
    }
    #usersTable_wrapper .dataTables_paginate .pagination .page-item .page-link:hover {
      background-color: rgba(var(--primary-color-rgb), 0.1);
      color: var(--primary-color);
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
    .table tbody tr {
      transition: background-color 0.2s ease;
    }
    .table tbody tr:hover {
      background-color: rgba(var(--primary-color-rgb), 0.05) !important;
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
      padding-top: 0.75rem;
      padding-bottom: 0.75rem;
    }
    footer p {
      margin-bottom: 0.25rem;
    }
    
    /* Checkbox list styling */
    .checkbox-list {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 10px;
        padding-left: 10px;
    }
    .checkbox-list div {
        flex: 1 1 180px; /* Adjust as needed for responsive columns */
        min-width: 150px;
    }
    .checkbox-list input[type="checkbox"] {
        margin-right: 5px;
    }


    /* Modals */
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
    .modal-title {
      color: var(--button-text);
    }
    .btn-close {
      filter: invert(1);
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
      .dataTables_filter, .dataTables_length {
        text-align: center !important;
      }
      .dataTables_filter input, .dataTables_length select {
        width: 100%;
        margin-bottom: 0.5rem;
      }

      /* Responsive for export/import buttons */
      .excel-buttons .btn {
          padding: 0.6rem 1rem; /* Smaller padding */
          font-size: 0.9rem; /* Smaller font */
      }
      .excel-buttons .btn .full-text {
          display: none; /* Hide full text on small screens */
      }
      .excel-buttons .btn .abbr-text {
          display: inline; /* Show abbreviation on small screens */
      }
      .executable-buttons .btn {
          padding: 0.6rem 1rem; /* Smaller padding */
          font-size: 0.9rem; /* Smaller font */
      }
      .executable-buttons .btn .abbr-text {
          display: inline; /* Show abbreviation on small screens */
      }
    }

    @media (min-width: 769px) {
        .excel-buttons .btn .full-text {
            display: inline; /* Show full text on larger screens */
        }
        .excel-buttons .btn .abbr-text {
            display: none; /* Hide abbreviation on larger screens */
        }
        .executable-buttons .btn .full-text {
            display: inline; /* Show full text on larger screens */
        }
        .executable-buttons .btn .abbr-text {
            display: none; /* Hide abbreviation on larger screens */
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
        <i class="fas fa-home me-2"></i> {# Home Icon (original color) #}
        <i class="fas fa-heartbeat me-2"></i>EasyMedicaLink {# Heartbeat Icon (original color) #}
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
      <a href="{{ url_for('login.change_password') }}" class="btn btn-outline-secondary flex-fill">
        <i class="fas fa-key me-2" style="color: #FFD700;"></i>Modifier passe
      </a>
      <a href="{{ url_for('login.logout') }}" class="btn btn-outline-secondary flex-fill">
        <i class="fas fa-sign-out-alt me-2" style="color: #DC143C;"></i>Déconnexion
      </a>
    </div>
    {# Le formulaire de paramètres généraux a été déplacé sur la page principale.
       Cet offcanvas ne contient maintenant que les actions de l'utilisateur. #}
  </div>
</div>

  <script>
    // Script pour le formulaire de paramètres dans l'offcanvas (si des champs y étaient)
    // Ce script est maintenant obsolète pour les paramètres généraux, mais peut être conservé
    // si des champs spécifiques à l'offcanvas devaient exister.
    // Pour l'instant, il est vide ou peut être supprimé si l'offcanvas n'a plus de formulaire.
    // document.getElementById('offcanvasSettingsForm')?.addEventListener('submit',e=>{
    //   e.preventDefault();
    //   fetch(e.target.action,{method:'POST',body:new FormData(e.target),credentials:'same-origin'})
    //     .then(r=>{
    //       if(!r.ok) {
    //         Swal.fire({icon:'error',title:'Erreur',text:'Échec de la sauvegarde.'});
    //         throw new Error('Network response was not ok.');
    //       }
    //       return r.json(); // Assuming the settings endpoint returns JSON
    //     })
    //     .then(data => {
    //       Swal.fire({icon:'success',title:'Succès',text:data.message}).then(() => {
    //         location.reload();
    //       });
    //     })
    //     .catch(error => {
    //       console.error('Error:', error);
    //       Swal.fire({icon:'error',title:'Erreur',text:'Une erreur inattendue est survenue lors de la sauvegarde.'});
    //     });
    // });
  </script>

  <div class="container-fluid my-4">
    <div class="row justify-content-center">
      <div class="col-12">
        <div class="card shadow-lg">
          <div class="card-header py-3 text-center">
            <h1 class="mb-2 header-item"><i class="fas fa-hospital me-2"></i>{{ config.nom_clinique or 'NOM CLINIQUE/CABINET/CENTRE MEDICAL' }}</h1>
            <div class="d-flex justify-content-center gap-4 flex-wrap">
              <div class="d-flex align-items-center header-item">
                <i class="fas fa-user me-2"></i><span>{{ logged_in_doctor_name if logged_in_doctor_name and logged_in_doctor_name != 'None' else config.doctor_name or 'NOM MEDECIN' }}</span> {# Simple User Icon #}
              </div>
              <div class="d-flex align-items-center header-item">
                <i class="fas fa-map-marker-alt me-2"></i><span>{{ config.location or 'LIEU' }}</span> {# Map Marker Icon (original color) #}
              </div>
            </div>
            <p class="mt-2 header-item"><i class="fas fa-calendar-day me-2"></i>{{ current_date }}</p>
            <p class="mt-2 header-item"><i class="fas fa-user-shield me-2" style="color: #FFFFFF;"></i>Administrateur</p> {# Added Administrator line #}
          </div>

          <div class="card-body">
            <div class="mb-3 text-center">
              <h6 class="fw-bold"><i class="fas fa-id-badge me-2" style="color: #6C757D;"></i>Informations de licence</h6>
              <p class="mb-1"><strong>Plan :</strong> {{ plan }}</p>
              <p class="mb-4"><strong>Administrateur :</strong> {{ admin_email }}</p>
            </div>

            <div class="d-flex justify-content-around flex-wrap gap-3">
              {# Removed all icons as per user request #}
              {#
              <a class="icon-card text-center" href="{{ url_for('biologie.home_biologie') }}">
                <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                  <i class="fas fa-flask mb-2 text-indigo-500"></i><span>Biologie</span>
                </div>
              </a>
              <a class="icon-card text-center" href="{{ url_for('radiologie.home_radiologie') }}">
                <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                  <i class="fas fa-x-ray mb-2 text-red-500"></i><span>Radiologies</span>
                </div>
              </a>
              <a class="icon-card text-center" href="{{ url_for('pharmacie.home_pharmacie') }}">
                <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                  <i class="fas fa-prescription-bottle-alt mb-2 text-yellow-500"></i><span>PHC & Stock</span>
                </div>
                </a>
              <a class="icon-card text-center" href="{{ url_for('comptabilite.home_comptabilite') }}">
                <div class="border rounded h-100 p-3 d-flex flex-column justify-content-center align-items-center">
                  <i class="fas fa-calculator mb-2 text-teal-500"></i><span>Comptabilité</span>
                </div>
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  {# Début de la nouvelle section pour les paramètres généraux sur la page #}
  <div class="container-fluid my-4">
      <div class="row justify-content-center">
        <div class="col-12">
          <div class="card">
            <div class="card-header text-center"><h2 class="header-item"><i class="fas fa-cogs me-2" style="color: #FFD700;"></i>Paramètres Généraux de l'Application</h2></div>
            <div class="card-body">
              <form id="mainSettingsForm" action="{{ url_for('administrateur_bp.update_general_settings') }}" method="POST">
                <div class="row g-3">
                  <div class="col-md-6 floating-label">
                    <input type="text" class="form-control" name="nom_clinique" id="nom_clinique_main"
                          value="{{ config.nom_clinique | default('') }}" placeholder=" ">
                    <label for="nom_clinique_main"><i class="fas fa-hospital me-2" style="color: #007BFF;"></i>Nom Clinique / Cabinet/Centre Médical</label>
                  </div>
                  <div class="col-md-6 floating-label">
                    <input type="text" class="form-control" name="doctor_name" id="doctor_name_main"
                          value="{{ config.doctor_name | default('') }}" placeholder=" ">
                    <label for="doctor_name_main"><i class="fas fa-user-md me-2" style="color: #20B2AA;"></i>Nom Médecin</label>
                  </div>
                  <div class="col-md-6 floating-label">
                    <input type="text" class="form-control" name="location" id="location_main"
                          value="{{ config.location | default('') }}" placeholder=" ">
                    <label for="location_main"><i class="fas fa-map-marker-alt me-2" style="color: #28A745;"></i>Lieu</label>
                  </div>
                  <div class="col-md-6 floating-label">
                    <select id="theme_main" name="theme" class="form-select" placeholder=" ">
                      {% for t in theme_names %}
                        <option value="{{ t }}" {% if config.theme == t %}selected{% endif %}>{{ t.capitalize() }}</option>
                      {% endfor %}
                    </select>
                    <label for="theme_main"><i class="fas fa-palette me-2" style="color: #9C27B0;"></i>Thème</label>
                  </div>
                  <div class="col-md-6 floating-label">
                    <select id="currency_main" name="currency" class="form-select" placeholder=" ">
                      {% set currencies = [
                        ('EUR','Euro'),('USD','Dollar US'),
                        ('MAD','Dirham marocain'),('DZD','Dinar algérien'),
                        ('TND','Dinar tunisien'),('XOF','Franc CFA (BCEAO)'),
                        ('XAF','Franc CFA (BEAC)'),('CHF','Franc suisse'),
                        ('CAD','Dollar canadien'),('HTG','Gourde haïtienne'),
                        ('GNF','Franc guinéen')
                      ] %}
                      {% for code, name in currencies %}
                        <option value="{{ code }}" {% if config.currency == code %}selected{% endif %}>
                          {{ name }} ({{ code }})
                        </option>
                      {% endfor %}
                    </select>
                    <label for="currency_main"><i class="fas fa-money-bill-wave me-2" style="color: #FFD700;"></i>Devise</label>
                  </div>
                  <div class="col-md-6 floating-label">
                    <input type="number" id="vat_main" name="vat" class="form-control"
                          value="{{ config.vat | default(20.0) }}" step="0.01" min="0" max="100" placeholder=" ">
                    <label for="vat_main"><i class="fas fa-percent me-2" style="color: #FF5722;"></i>TVA (%)</label>
                  </div>
                  {# NOUVEAUX CHAMPS POUR LES INTERVALLES DE RDV #}
                  <div class="col-md-4 floating-label">
                    <input type="time" class="form-control" name="rdv_start_time" id="rdv_start_time_main"
                          value="{{ config.rdv_start_time | default('08:00') }}" placeholder=" ">
                    <label for="rdv_start_time_main"><i class="fas fa-clock me-2" style="color: #6C757D;"></i>Heure de début RDV</label>
                  </div>
                  <div class="col-md-4 floating-label">
                    <input type="time" class="form-control" name="rdv_end_time" id="rdv_end_time_main"
                          value="{{ config.rdv_end_time | default('17:45') }}" placeholder=" ">
                    <label for="rdv_end_time_main"><i class="fas fa-clock me-2" style="color: #6C757D;"></i>Heure de fin RDV</label>
                  </div>
                  <div class="col-md-4 floating-label">
                    <input type="number" class="form-control" name="rdv_interval_minutes" id="rdv_interval_minutes_main"
                          value="{{ config.rdv_interval_minutes | default(15) }}" min="1" placeholder=" ">
                    <label for="rdv_interval_minutes_main"><i class="fas fa-hourglass-half me-2" style="color: #FFC107;"></i>Intervalle RDV (minutes)</label>
                  </div>
                  {# FIN NOUVEAUX CHAMPS #}
                  <div class="col-12 text-center d-flex justify-content-center flex-wrap gap-2"> {# Added flex-wrap and gap-2 for responsiveness #}
                    <button type="submit" class="btn btn-success">
                      <i class="fas fa-save me-2"></i>Enregistrer les paramètres
                    </button>
                    <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#importBackgroundModal">
                      <i class="fas fa-image me-2"></i>Importer Logo/Arrière-plan
                    </button>
                  </div>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  {# Fin de la nouvelle section pour les paramètres généraux sur la page #}

  {# NOUVELLE SECTION POUR LA GESTION DES LISTES DE MÉDICAMENTS/ANALYSES/RADIOLOGIES #}
  <div class="container-fluid my-4">
    <div class="row justify-content-center">
      <div class="col-12">
        <div class="card">
          <div class="card-header text-center"><h2 class="header-item"><i class="fas fa-list-alt me-2" style="color: #FF8C00;"></i>Gestion des Listes (Médicaments, Analyses, Radiologies)</h2></div>
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
                  <button type="submit" class="btn btn-success">
                    <i class="fas fa-save me-2"></i>Enregistrer les listes
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
  {# FIN NOUVELLE SECTION #}

  <div class="container-fluid my-4">
    <div class="row justify-content-center">
      <div class="col-12">
        <div class="card">
          <div class="card-header text-center"><h2 class="header-item"><i class="fas fa-calendar-check me-2" style="color: #4CAF50;"></i>Accès Patient & Indisponibilités</h2></div>
          <div class="card-body">
            <div class="row">
              <div class="col-md-6 mb-4">
                <h5 class="fw-bold text-center"><i class="fas fa-link me-2" style="color: #007BFF;"></i>Lien de prise de rendez-vous pour la clinique</h5>
                <div class="mb-3 p-2 border rounded text-center">
                  <p class="text-break small mb-1">{{ patient_appointment_link }}</p>
                  <button class="btn btn-secondary btn-sm mb-2" onclick="copyToClipboard('{{ patient_appointment_link }}')">
                    <i class="fas fa-copy me-2"></i>Copier le lien
                  </button>
                  {% if qr_code_data_uri %}
                      <div class="text-center d-flex justify-content-center"> {# Ajout des classes flexbox #}
                        <img src="{{ qr_code_data_uri }}" alt="QR Code Rendez-vous" class="img-fluid" style="max-width: 120px; border-radius: var(--border-radius-md);">
                      </div>
                    {% else %}
                      <p class="text-danger small">Impossible de générer le QR Code.</p>
                    {% endif %}
                </div>
              </div>
              <div class="col-md-6">
                <h5 class="fw-bold text-center"><i class="fas fa-calendar-times me-2" style="color: #DC3545;"></i>Gérer les indisponibilités</h5>
                <form id="addUnavailabilityForm" class="row g-2 mb-3" action="{{ url_for('administrateur_bp.manage_unavailability') }}" method="POST">
                  <input type="hidden" name="action" value="add">
                  <div class="col-md-6 floating-label">
                    <input type="date" class="form-control" id="unavailabilityStartDate" name="start_date" placeholder=" " required>
                    <label for="unavailabilityStartDate"><i class="fas fa-calendar-alt me-2" style="color: #FFB6C1;"></i>Date de début</label>
                  </div>
                  <div class="col-md-6 floating-label">
                    <input type="date" class="form-control" id="unavailabilityEndDate" name="end_date" placeholder=" " required>
                    <label for="unavailabilityEndDate"><i class="fas fa-calendar-alt me-2" style="color: #FFB6C1;"></i>Date de fin</label>
                  </div>
                  <div class="col-12 floating-label">
                    <input type="text" class="form-control" id="unavailabilityReason" name="reason" placeholder=" ">
                    <label for="unavailabilityReason"><i class="fas fa-info-circle me-2" style="color: #17A2B8;"></i>Raison (optionnel)</label>
                  </div>
                  <div class="col-12">
                    <button type="submit" class="btn btn-primary w-100">
                      <i class="fas fa-plus-circle me-2"></i>Ajouter une période
                    </button>
                  </div>
                </form>
                <h6 class="mt-4 fw-bold"><i class="fas fa-list-alt me-2" style="color: #6C757D;"></i>Périodes actuelles :</h6>
                <ul class="list-group">
                  {% if config.unavailability_periods %}
                    {% for period in config.unavailability_periods %}
                      <li class="list-group-item d-flex justify-content-between align-items-center bg-transparent text-color border-color rounded mb-2">
                        {{ period.start_date }} au {{ period.end_date }} {% if period.reason %}({{ period.reason }}){% endif %}
                        <button type="button" class="btn btn-danger btn-sm" onclick="deleteUnavailability({{ loop.index0 }})">
                          <i class="fas fa-trash"></i>
                        </button>
                      </li>
                    {% endfor %}
                  {% else %}
                    <li class="list-group-item bg-transparent text-color border-color rounded">Aucune période d'indisponibilité configurée.</li>
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
          <div class="card-header text-center"><h2 class="header-item"><i class="fas fa-users-cog me-2" style="color: #FFC107;"></i>Administration des comptes</h2></div>
          <div class="card-body">
            <form class="row g-3 mb-4" method="POST" action="{{ url_for('administrateur_bp.create_user') }}">
              <div class="col-12 col-md-2 floating-label">
                <input name="nom" id="createNom" class="form-control" placeholder=" " required>
                <label for="createNom"><i class="fas fa-user me-2" style="color: #007BFF;"></i>Nom</label>
              </div>
              <div class="col-12 col-md-2 floating-label">
                <input name="prenom" id="createPrenom" class="form-control" placeholder=" " required>
                <label for="createPrenom"><i class="fas fa-user-tag me-2" style="color: #17A2B8;"></i>Prénom</label>
              </div>
              <div class="col-12 col-md-2 floating-label">
                <input name="phone" id="createPhone" class="form-control" placeholder=" ">
                <label for="createPhone"><i class="fas fa-phone me-2" style="color: #28A745;"></i>Téléphone</label>
              </div>
              <div class="col-12 col-md-2 floating-label">
                <select name="role" id="createRole" class="form-select" placeholder=" " required>
                  <option value="">Sélectionner un rôle</option>
                  <option value="medecin">Médecin</option>
                  <option value="assistante">Assistante</option>
                  <option value="comptable">Comptable</option>
                  <option value="biologiste">Biologiste</option>
                  <option value="radiologue">Radiologue</option>
                  <option value="pharmacie/magasin">Pharmacie & Magasin</option>
                </select>
                <label for="createRole"><i class="fas fa-user-shield me-2" style="color: #6F42C1;"></i>Rôle</label>
              </div>
              <div class="col-12 col-md-2 floating-label" id="createLinkedDoctorDiv" style="display: none;">
                <select name="linked_doctor" id="createLinkedDoctor" class="form-select" placeholder=" ">
                  <option value="">Aucun médecin lié</option>
                  {% for doc in doctors %}
                    <option value="{{ doc.email }}">{{ doc.prenom }} {{ doc.nom }}</option>
                  {% endfor %}
                </select>
                <label for="createLinkedDoctor"><i class="fas fa-link me-2" style="color: #FD7E14;"></i>Médecin lié (pour assistante)</label>
              </div>
              <div class="col-12 col-md-2 floating-label">
                <input name="password" id="createPassword" type="password" class="form-control" placeholder=" " required>
                <label for="createPassword"><i class="fas fa-lock me-2" style="color: #DC3545;"></i>Mot de passe</label>
              </div>
              {# NOUVEAU: CASES À COCHER POUR LES AUTORISATIONS DE CRÉATION #}
              <div class="col-12 mb-3">
                <label class="form-label fw-semibold"><i class="fas fa-shield-alt me-2"></i>Autorisations d'accès aux pages :</label>
                <div class="checkbox-list" id="createAccessCheckboxes">
                  {# Les checkboxes seront remplies dynamiquement par JavaScript #}
                </div>
              </div>
              {# FIN NOUVELLES CASES À COCHER #}
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
                        {% if user_info.role == 'admin' %}
                            <span class="badge bg-primary">Toutes</span>
                        {% else %}
                            {% for page in user_info.allowed_pages %}
                                <span class="badge bg-secondary">{{ page | replace('_', ' ') | title }}</span>
                            {% endfor %}
                        {% endif %}
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
                      {% if user_info.phone %}
                        <a href="https://wa.me/{{ user_info.phone }}" target="_blank" class="btn btn-sm btn-info me-1" title="Contacter via WhatsApp"><i class="fab fa-whatsapp"></i></a>
                      {% endif %}
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
          <div class="card-header text-center"><h2 class="header-item"><i class="fas fa-file-alt me-2" style="color: #8A2BE2;"></i>Gestion des Fichiers & Applications</h2></div>
          <div class="card-body">
            <div class="row">
              <div class="col-md-6 mb-4">
                <h5 class="fw-bold text-center"><i class="fas fa-database me-2" style="color: #007BFF;"></i>Base de Données Excel</h5>
                <div class="d-flex justify-content-center gap-3 flex-wrap excel-buttons">
                  <a href="{{ url_for('administrateur_bp.download_all_excels') }}" class="btn btn-success">
                    <i class="fas fa-file-excel me-2" style="color: #FFFFFF;"></i><span class="full-text">Télécharger votre base de données</span><span class="abbr-text">Export DB</span>
                  </a>
                  <form action="{{ url_for('administrateur_bp.upload_excel_database') }}" method="POST" enctype="multipart/form-data" id="uploadExcelForm">
                      <input type="file" name="excel_file" id="excel_file_upload" accept=".xlsx,.xls" class="d-none">
                      <label for="excel_file_upload" class="btn btn-info">
                          <i class="fas fa-upload me-2" style="color: #FFFFFF;"></i><span class="full-text">Importer votre base de données</span><span class="abbr-text">Import DB</span>
                      </label>
                      <button type="submit" class="btn btn-info" id="upload_button" style="display:none;">
                          <span id="upload_button_text"><i class="fas fa-arrow-up me-2"></i>Confirmer l'importation</span>
                          <span id="upload_spinner" class="spinner-border spinner-border-sm" role="status" aria-hidden="true" style="display:none;"></span>
                      </button>
                  </form>
                </div>
              </div>
              <div class="col-md-6 mb-4">
                <h5 class="fw-bold text-center"><i class="fas fa-download me-2" style="color: #28A745;"></i>Téléchargement d'Applications</h5>
                <div class="d-flex justify-content-center gap-3 flex-wrap executable-buttons">
                  {% if win64_filename %}
                  <a href="{{ url_for('static', filename=win64_filename) }}" class="btn btn-primary">
                    <i class="fas fa-download me-2" style="color: #FFFFFF;"></i><span class="full-text">Télécharger EasyMedicalLink Win64</span><span class="abbr-text">Win64</span>
                  </a>
                  {% endif %}
                  {% if win32_filename %}
                  <a href="{{ url_for('static', filename=win32_filename) }}" class="btn btn-primary">
                    <i class="fas fa-download me-2" style="color: #FFFFFF;"></i><span class="full-text">Télécharger EasyMedicalLink Win32</span><span class="abbr-text">Win32</span>
                  </a>
                  {% endif %}
                </div>
              </div>
              {# ANCIEN EMPLACEMENT DU BOUTON "IMPORTER IMAGE" - À SUPPRIMER #}
              {#
              <div class="col-12 mt-4">
                <h5 class="fw-bold text-center"><i class="fas fa-image me-2" style="color: #FFD700;"></i>Gestion des Images (Logo/Arrière-plan)</h5>
                <div class="d-flex justify-content-center">
                  <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#importBackgroundModal">
                    <i class="fas fa-upload me-2"></i>Importer une image
                  </button>
                </div>
               {# administrateur.py - dans la variable administrateur_template #}

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
            <label for="newEmail"><i class="fas fa-envelope me-2" style="color: #007BFF;"></i>Adresse email</label>
          </div>



          <div class="mb-3 floating-label">
            <input id="newPassword" name="new_password" type="password" class="form-control" placeholder=" ">
            <label for="newPassword"><i class="fas fa-lock me-2" style="color: #DC3545;"></i>Nouveau mot de passe</label>
          </div>
          <div class="mb-3 floating-label">
            <input id="confirmPassword" name="confirm_password" type="password" class="form-control" placeholder=" ">
            <label for="confirmPassword"><i class="fas fa-lock me-2" style="color: #DC3545;"></i>Confirmer nouveau mot de passe</label>
          </div>
          <div class="mb-3 floating-label">
          {# AJOUTER CE BLOC POUR LE CHAMP NOM #}
          <div class="mb-3 floating-label">
            <input id="editNom" name="nom" class="form-control" placeholder=" " required>
            <label for="editNom"><i class="fas fa-user me-2" style="color: #007BFF;"></i>Nom</label>
          </div>
          {# FIN DE L'AJOUT #}
            <input id="editPrenom" name="prenom" class="form-control" placeholder=" " required>
            <label for="editPrenom"><i class="fas fa-user-tag me-2" style="color: #17A2B8;"></i>Prénom</label>
          </div>
          <div class="mb-3 floating-label">
            <input id="editPhone" name="phone" class="form-control" placeholder=" ">
            <label for="editPhone"><i class="fas fa-phone me-2" style="color: #28A745;"></i>Téléphone</label>
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
            <label for="editRole"><i class="fas fa-user-shield me-2" style="color: #6F42C1;"></i>Rôle</label>
          </div>
          <div class="mb-3 floating-label" id="editLinkedDoctorDiv" style="display: none;">
            <select name="linked_doctor" id="editLinkedDoctor" class="form-select" placeholder=" ">
              <option value="">Aucun médecin lié</option>
              {% for doc in doctors %}
                <option value="{{ doc.email }}">{{ doc.prenom }} {{ doc.nom }}</option>
              {% endfor %}
            </select>
            <label for="editLinkedDoctor"><i class="fas fa-link me-2" style="color: #FD7E14;"></i>Médecin lié (pour assistante)</label>
          </div>
          <div class="col-12 mb-3">
            <label class="form-label fw-semibold"><i class="fas fa-shield-alt me-2"></i>Autorisations d'accès aux pages :</label>
            <div class="checkbox-list" id="editAccessCheckboxes">
              {# Les checkboxes seront remplies dynamiquement par JavaScript #}
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
          <button type="submit" class="btn btn-primary">Enregistrer les modifications</button>
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

  <div class="modal fade" id="importBackgroundModal" tabindex="-1"> {# Changed ID #}
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title"><i class="fas fa-image me-2"></i>Importer Image</h5>
          <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body">
          <form id="importBackgroundForm" onsubmit="return ajaxFileUpload('importBackgroundForm','{{ url_for('administrateur_bp.import_image') }}')"> {# Changed ID #}
            <div class="mb-3">
              <label for="image_type" class="form-label"><i class="fas fa-cogs me-2" style="color: #6C757D;"></i>Type d'image</label>
              <select class="form-select" name="image_type" id="image_type" required>
                <option value="background">Arrière-plan</option>
                {# REMOVED: <option value="logo">Logo</option> #}
              </select>
            </div>
            <div class="mb-3">
              <label for="image_file_admin" class="form-label"><i class="fas fa-file-image me-2" style="color: #FFD700;"></i>Fichier</label>
              <input type="file" class="form-control" name="image_file" id="image_file_admin" accept=".png,.jpg,.jpeg,.gif,.bmp,.pdf" required> {# Added .pdf #}
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
    document.addEventListener('DOMContentLoaded', () => {
      // Initialisation de DataTables
      const usersTable = new DataTable('#usersTable', {
        responsive: true,
        lengthChange: true,
        language: { url: "//cdn.datatables.net/plug-ins/1.13.1/i18n/fr-FR.json" }
      });

      // Liste des blueprints disponibles pour les permissions
      // Note: 'accueil' est géré séparément car toujours autorisé pour les non-admins
      // 'administrateur_bp' est toujours autorisé pour les admins
      const PERMISSION_BLUEPRINTS = ['rdv', 'routes', 'facturation', 'biologie', 'radiologie', 'pharmacie', 'comptabilite', 'statistique', 'gestion_patient', 'ia_assitant'];

      function generateCheckboxes(containerId, currentAllowedPages = [], isCreateForm = false, userRole = null) {
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

              // Déterminer l'état coché par défaut
              if (isCreateForm) {
                  // Pour le formulaire de création, cocher par défaut les pages communes
                  const defaultCreateChecked = ['rdv', 'routes', 'facturation', 'biologie', 'radiologie', 'pharmacie', 'comptabilite', 'statistique', 'gestion_patient', 'ia_assitant'];
                  if (defaultCreateChecked.includes(bp_name)) {
                      checkbox.checked = true;
                  }
              } else {
                  // Pour le formulaire d'édition, utiliser les pages déjà autorisées par l'utilisateur
                  if (currentAllowedPages.includes(bp_name)) {
                      checkbox.checked = true;
                  }
              }
              
              // Si le rôle est admin, toutes les cases sont cochées et désactivées
              if (userRole === 'admin') {
                  checkbox.checked = true;
                  checkbox.disabled = true;
              }

              // NEW: Set default permissions for 'medecin' and 'ia_assitant'
              if (isCreateForm && userRole === 'medecin') {
                  const defaultDoctorPermissions = ['rdv', 'routes', 'biologie', 'radiologie', 'statistique', 'gestion_patient', 'ia_assitant'];
                  if (defaultDoctorPermissions.includes(bp_name)) {
                      checkbox.checked = true;
                  } else {
                      checkbox.checked = false;
                  }
              }

              const label = document.createElement('label');
              label.htmlFor = checkbox.id;
              let display_name = bp_name.replace('_', ' ').replace('bp', '').trim();
              if (display_name === 'routes') {
                  display_name = 'Consultations';
              } else if (display_name === 'gestion patient') { // Spécifique pour gestion_patient
                  display_name = 'Patients';
              }
              else if (display_name === 'ia assitant') { // Spécifique pour ia_assitant
                  display_name = 'Assistant IA';
              }
              else {
                  display_name = display_name.split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
              }
              label.textContent = display_name;

              div.appendChild(checkbox);
              div.appendChild(label);
              container.appendChild(div);
          });
      }

      // Appel initial pour le formulaire de création
      generateCheckboxes('createAccessCheckboxes', [], true, document.getElementById('createRole').value);

      // Fonction pour copier le texte dans le presse-papiers
      window.copyToClipboard = function(text) { // Ajoute 'window.' pour la rendre globale
          const textarea = document.createElement('textarea');
          textarea.value = text;
          document.body.appendChild(textarea);
          textarea.select();
          try {
              document.execCommand('copy');
              Swal.fire({
                  icon: 'success',
                  title: 'Copié!',
                  text: 'Lien copié dans le presse-papiers.',
                  timer: 1500,
                  showConfirmButton: false
              });
          } catch (err) {
              console.error('Échec de la copie: ', err);
              Swal.fire({
                  icon: 'error',
                  title: 'Erreur!',
                  text: 'Échec de la copie du lien.',
                  timer: 1500,
                  showConfirmButton: false
              });
          }
          document.body.removeChild(textarea);
      }

      // Gestion du changement de rôle pour la création d'utilisateur
      document.getElementById('createRole').addEventListener('change', function() {
          const linkedDoctorDiv = document.getElementById('createLinkedDoctorDiv');
          const role = this.value;
          if (role === 'assistante') {
              linkedDoctorDiv.style.display = 'block';
              document.getElementById('createLinkedDoctor').setAttribute('required', 'required');
          } else {
              linkedDoctorDiv.style.display = 'none';
              document.getElementById('createLinkedDoctor').removeAttribute('required');
          }
          // Régénérer les checkboxes avec le rôle mis à jour
          generateCheckboxes('createAccessCheckboxes', [], true, role);
      });

      // Délégation d'événements pour les boutons du tableau
      // Ceci est crucial pour les tableaux DataTables car le contenu est re-rendu.
      $('#usersTable tbody').on('click', '.editBtn', function(e) {
        e.preventDefault();
        const email = $(this).data('email'); // Utilise jQuery pour récupérer data-email
        fetch(`/administrateur/users/${encodeURIComponent(email)}`)
          .then(r => {
            if (!r.ok) {
              Swal.fire({ icon: 'error', title: 'Erreur', text: 'Échec du chargement des données utilisateur.' });
              throw new Error('Failed to load user data.');
            }
            return r.json();
          })
          .then(u => {
            document.getElementById('editEmail').value = email;
            document.getElementById('newEmail').value = email;
            document.getElementById('editNom').value = u.nom;
            document.getElementById('editPrenom').value = u.prenom;
            document.getElementById('editPhone').value = u.phone;
            document.getElementById('editRole').value = u.role;

            const editLinkedDoctorDiv = document.getElementById('editLinkedDoctorDiv');
            if (u.role === 'assistante') {
              editLinkedDoctorDiv.style.display = 'block';
              document.getElementById('editLinkedDoctor').value = u.linked_doctor || '';
              document.getElementById('editLinkedDoctor').setAttribute('required', 'required');
            } else {
              editLinkedDoctorDiv.style.display = 'none';
              document.getElementById('editLinkedDoctor').removeAttribute('required');
            }

            // Régénérer les checkboxes avec les permissions de l'utilisateur et son rôle
            generateCheckboxes('editAccessCheckboxes', u.allowed_pages, false, u.role);

            new bootstrap.Modal(document.getElementById('editModal')).show();
          })
          .catch(error => {
            console.error('Erreur lors du chargement des données utilisateur:', error);
            Swal.fire({ icon: 'error', title: 'Erreur', text: 'Une erreur est survenue lors du chargement des données.' });
          });
      });

      $('#usersTable tbody').on('click', '.btn-danger', function(e) {
          e.preventDefault();
          const email = $(this).data('email'); // Récupère l'email directement du bouton
          confirmDeleteUser(email);
      });
      
      // Fonction SweetAlert pour la confirmation de suppression d'utilisateur
      function confirmDeleteUser(email) {
          Swal.fire({
              title: 'Êtes-vous sûr?',
              text: `Vous êtes sur le point de supprimer l'utilisateur ${email}. Cette action est irréversible!`,
              icon: 'warning',
              showCancelButton: true,
              confirmButtonColor: '#d33',
              cancelButtonColor: '#3085d6',
              confirmButtonText: 'Oui, supprimer!',
              cancelButtonText: 'Annuler'
          }).then((result) => {
              if (result.isConfirmed) {
                  // C'est LA ligne à modifier : Passer l'email directement à url_for
                  window.location.href = `{{ url_for('administrateur_bp.delete_user', user_email='PLACEHOLDER_EMAIL') }}`.replace('PLACEHOLDER_EMAIL', encodeURIComponent(email));
              }
          });
      }

      // Handle edit user form role change for permissions checkboxes
      document.getElementById('editRole').addEventListener('change', function() {
          const role = this.value;
          // Régénérer les checkboxes avec les permissions par défaut pour le nouveau rôle
          generateCheckboxes('editAccessCheckboxes', [], false, role);
      });

      document.getElementById('editForm').addEventListener('submit',e=>{
        e.preventDefault();
        fetch(e.target.action,{method:'POST',body:new FormData(e.target),credentials:'same-origin'})
          .then(r=>{
            if(!r.ok) {
              Swal.fire({icon:'error',title:'Erreur',text:'Échec de la sauvegarde.'});
              throw new Error('Network response was not ok.');
            }
            return r.text();
          })
          .then(()=>location.reload())
          .catch(error => {
            console.error('Error:', error);
            if (!error.message.includes('Network response was not ok.')) {
              Swal.fire({icon:'error',title:'Erreur',text:'Une erreur inattendue est survenue.'});
            }
          });
      });
document.getElementById('editForm').addEventListener('submit',e=>{
    e.preventDefault();
    fetch(e.target.action,{method:'POST',body:new FormData(e.target),credentials:'same-origin'})
      .then(r=>{
        if(!r.ok) {
          Swal.fire({icon:'error',title:'Erreur',text:'Échec de la sauvegarde.'});
          throw new Error('Network response was not ok.');
        }
        return r.text(); // Devrait être r.json() si le backend renvoie du JSON
      })
      .then(()=>location.reload()) // Recharge la page en cas de succès
      .catch(error => {
        console.error('Error:', error);
        if (!error.message.includes('Network response was not ok.')) {
          Swal.fire({icon:'error',title:'Erreur',text:'Une erreur inattendue est survenue.'});
        }
      });
  });
      // Gérer l'affichage du bouton de confirmation d'importation et l'indicateur de chargement pour Excel
      document.getElementById('excel_file_upload').addEventListener('change', function() {
          const uploadButton = document.getElementById('upload_button');
          if (this.files.length > 0) {
              uploadButton.style.display = 'inline-flex';
          } else {
              uploadButton.style.display = 'none';
          }
      });

      document.getElementById('uploadExcelForm').addEventListener('submit', function() {
          const uploadButton = document.getElementById('upload_button');
          const uploadButtonText = document.getElementById('upload_button_text');
          const uploadSpinner = document.getElementById('upload_spinner');

          uploadButtonText.style.display = 'none';
          uploadSpinner.style.display = 'inline-block';
          uploadButton.disabled = true;
          uploadButton.classList.add('no-pointer-events');
      });

      // Fonction de téléchargement de fichiers AJAX
      window.ajaxFileUpload = function(formId, endpoint) {
        var form = document.getElementById(formId);
        var formData = new FormData(form);
        fetch(endpoint, {
            method: "POST",
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            Swal.fire({
                icon: data.status,
                title: data.status === "success" ? "Succès" : "Attention",
                text: data.message,
                timer: 2000,
                showConfirmButton: false
            });
            if (data.status === "success") {
                const modalElement = document.getElementById('importBackgroundModal');
                if (modalElement) {
                    bootstrap.Modal.getInstance(modalElement).hide();
                }
                setTimeout(() => window.location.reload(), 2100);
            }
        })
        .catch(error => {
            Swal.fire({
                icon: "error",
                title: "Erreur",
                text: error,
                timer: 2000,
                showConfirmButton: false
            });
            console.error('Error:', error);
        });
        return false;
      };

      // Gérer la soumission du formulaire d'indisponibilité
      document.getElementById('addUnavailabilityForm').addEventListener('submit', function(e) {
          e.preventDefault();
          const formData = new FormData(this);
          formData.append('action', 'add');

          fetch('{{ url_for('administrateur_bp.manage_unavailability') }}', {
              method: 'POST',
              body: formData
          })
          .then(response => response.json())
          .then(data => {
              Swal.fire({
                  icon: data.status,
                  title: data.status === "success" ? "Succès" : "Attention",
                  text: data.message,
                  timer: 2000,
                  showConfirmButton: false
              });
              if (data.status === "success") {
                  setTimeout(() => window.location.reload(), 2100);
              }
          })
          .catch(error => {
              Swal.fire({
                  icon: "error",
                  title: "Erreur",
                  text: "Erreur lors de l'ajout de la période d'indisponibilité.",
                  timer: 2000,
                  showConfirmButton: false
              });
              console.error('Error:', error);
          });
      });
    // Gérer l'affichage du bouton de confirmation d'importation et l'indicateur de chargement pour les listes
    // Removed the event listeners for 'lists_file_upload' and 'uploadListsForm' since the section is removed.

      // Fonction pour supprimer une période d'indisponibilité
      function deleteUnavailability(index) {
          Swal.fire({
              title: 'Êtes-vous sûr?',
              text: "Vous êtes sur le point de supprimer cette période d'indisponibilité.",
              icon: 'warning',
              showCancelButton: true,
              confirmButtonColor: '#d33',
              cancelButtonColor: '#3085d6',
              confirmButtonText: 'Oui, supprimer!',
              cancelButtonText: 'Annuler'
          }).then((result) => {
              if (result.isConfirmed) {
                  const formData = new FormData();
                  formData.append('action', 'delete');
                  formData.append('index', index);

                  fetch('{{ url_for('administrateur_bp.manage_unavailability') }}', {
                      method: 'POST',
                      body: formData
                  })
                  .then(response => response.json())
                  .then(data => {
                      Swal.fire({
                          icon: data.status,
                          title: data.status === "success" ? "Succès" : "Attention",
                          text: data.message,
                          timer: 2000,
                          showConfirmButton: false
                      });
                      if (data.status === "success") {
                          setTimeout(() => window.location.reload(), 2100);
                      }
                  })
                  .catch(error => {
                      Swal.fire({
                          icon: "error",
                          title: "Erreur",
                          text: "Erreur lors de la suppression de la période d'indisponibilité.",
                          timer: 2000,
                          showConfirmButton: false
                      });
                      console.error('Error:', error);
                  });
              }
          });
      }

    }); // Fin de DOMContentLoaded

    // Script pour le formulaire de paramètres généraux sur la page principale
    document.getElementById('mainSettingsForm').addEventListener('submit',e=>{
      e.preventDefault();
      fetch(e.target.action,{method:'POST',body:new FormData(e.target),credentials:'same-origin'})
        .then(r=>{
          if(!r.ok) {
            Swal.fire({icon:'error',title:'Erreur',text:'Échec de la sauvegarde.'});
            throw new Error('Network response was not ok.');
          }
          return r.json(); // Assuming the settings endpoint returns JSON
        })
        .then(data => {
          Swal.fire({icon:'success',title:'Succès',text:data.message}).then(() => {
            // LIGNE MODIFIÉE : Forcer un rechargement sans utiliser le cache
            window.location.href = "{{ url_for('administrateur_bp.dashboard') }}?_t=" + new Date().getTime(); // MODIFIÉ ICI
          });
        })
        .catch(error => {
          console.error('Error:', error);
          Swal.fire({icon:'error',title:'Erreur',text:'Une erreur inattendue est survenue lors de la sauvegarde.'});
        });
    });

    // Script pour le formulaire des listes (médicaments, analyses, radiologies)
    document.getElementById('listsSettingsForm').addEventListener('submit',e=>{
      e.preventDefault();
      fetch(e.target.action,{method:'POST',body:new FormData(e.target),credentials:'same-origin'})
        .then(r=>{
          if(!r.ok) {
            Swal.fire({icon:'error',title:'Erreur',text:'Échec de la sauvegarde des listes.'});
            throw new Error('Network response was not ok.');
          }
          return r.json(); // Assuming the settings endpoint returns JSON
        })
        .then(data => {
          Swal.fire({icon:'success',title:'Succès',text:data.message}).then(() => {
            // Recharger la page pour refléter les changements
            window.location.href = "{{ url_for('administrateur_bp.dashboard') }}?_t=" + new Date().getTime();
          });
        })
        .catch(error => {
          console.error('Error:', error);
          Swal.fire({icon:'error',title:'Erreur',text:'Une erreur inattendue est survenue lors de la sauvegarde des listes.'});
        });
    });
  </script>
</body>
</html>
"""

# ──────────────────────────────────────────────────────────────────────────────
# 7. Routes du Blueprint administrateur_bp
# ──────────────────────────────────────────────────────────────────────────────
@administrateur_bp.route('/', methods=['GET'])
@admin_required
def dashboard():
    """
    Main administrator dashboard route.
    Displays license information, module links, user management, and unavailability.
    """
    # --- DÉBUT DES MODIFICATIONS/AJOUTS ---
    logged_in_full_name = None 
    user_email = session.get('email')
    
    if user_email:
        # Assurez-vous que utils.set_dynamic_base_dir a été appelé pour que login.load_users fonctionne correctement
        # (normalement géré par before_request, mais bonne pratique de s'assurer)
        admin_email_from_session = session.get('admin_email', 'default_admin@example.com')
        utils.set_dynamic_base_dir(admin_email_from_session)
        
        all_users_data = login.load_users()
        user_info = all_users_data.get(user_email)
        if user_info:
            logged_in_full_name = f"{user_info.get('prenom', '')} {user_info.get('nom', '')}".strip()
            if not logged_in_full_name:
                logged_in_full_name = None
    # --- FIN DES MODIFICATIONS/AJOUTS ---

    context = get_admin_dashboard_context()
    # --- AJOUTER logged_in_doctor_name au contexte ---
    context['logged_in_doctor_name'] = logged_in_full_name 
    # --- FIN AJOUT ---

    return render_template_string(administrateur_template, **context)

@administrateur_bp.route('/users/<user_email>', methods=['GET'])
@admin_required
def get_user(user_email):
    """
    API endpoint to retrieve details of a specific user.
    Used by the user modification form.
    """
    user_details = get_user_details(user_email)
    if not user_details:
        return jsonify({}), 404
    return jsonify(user_details)

@administrateur_bp.route('/users', methods=['POST'])
@admin_required
def create_user():
    """
    Route to create a new user account (doctor, assistant, etc.).
    """
    success, message = create_new_user(request.form)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    return redirect(url_for('administrateur_bp.dashboard'))

@administrateur_bp.route('/users/edit', methods=['POST'])
@admin_required
def edit_user():
    """
    Route to modify an existing user account.
    """
    success, message = update_existing_user(request.form)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    return redirect(url_for('administrateur_bp.dashboard'))

@administrateur_bp.route('/users/<user_email>/toggle-active', methods=['GET'])
@admin_required
def toggle_user_active(user_email):
    """
    Route to toggle a user's active/inactive status.
    Uses GET method for link simplicity, but a POST/PUT request would be more RESTful.
    """
    success, message = toggle_user_active_status(user_email)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    return redirect(url_for('administrateur_bp.dashboard'))

@administrateur_bp.route('/users/<user_email>/delete', methods=['GET'])
@admin_required
def delete_user(user_email):
    """
    Route to delete a user account.
    Uses GET method for link simplicity, but a DELETE request would be more RESTful.
    """
    success, message = delete_existing_user(user_email)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    return redirect(url_for('administrateur_bp.dashboard'))

@administrateur_bp.route("/data/excel/download", methods=["GET"])
@admin_required
def download_all_excels():
    """
    Route to download a single Excel file containing all administrator data.
    """
    try:
        buffer, filename = handle_excel_download()
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except ValueError as e: # Capture l'erreur spécifique si le répertoire n'est pas défini
        flash(str(e), "danger") # Utilisez "danger" pour les erreurs critiques
        return redirect(url_for("administrateur_bp.dashboard"))
    except Exception as e:
        flash(f"Erreur inattendue lors de la génération du fichier Excel : {e}", "danger")
        return redirect(url_for("administrateur_bp.dashboard"))

@administrateur_bp.route("/data/excel/upload", methods=["POST"])
@admin_required
def upload_excel_database():
    """
    Route to import an Excel file and update existing databases.
    """
    if 'excel_file' not in request.files:
        flash("Aucun fichier n'a été sélectionné.", "warning")
        return redirect(url_for("administrateur_bp.dashboard"))

    file = request.files['excel_file']
    success, message = handle_excel_upload(file)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    return redirect(url_for("administrateur_bp.dashboard"))

@administrateur_bp.route("/data/image/upload", methods=["POST"])
@admin_required
def import_image():
    """
    Route to import an image (logo or background) and update the configuration.
    """
    image_type = request.form.get("image_type")
    image_file = request.files.get("image_file")

    success, message = handle_image_upload(image_file, image_type)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    return jsonify({"status": "success" if success else "error", "message": message}) # JSON response for AJAX

@administrateur_bp.route("/unavailability", methods=["POST"])
@admin_required
def manage_unavailability():
    """
    Route to manage adding or deleting unavailability periods.
    """
    success, message = manage_unavailability_periods(request.form)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    return jsonify({"status": "success" if success else "error", "message": message}) # JSON response for AJAX

@administrateur_bp.route("/update_general_settings", methods=["POST"])
@admin_required
def update_general_settings():
    """
    Route to update general application settings (clinic info, theme, currency, VAT, lists, RDV intervals).
    Ensures that existing settings and lists are not cleared if their respective form fields are not present in the submission.
    """
    try:
        config = utils.load_config()

        # Update clinic/doctor/location info only if present in the form
        if 'nom_clinique' in request.form:
            config['nom_clinique'] = request.form.get('nom_clinique', '').strip()
        if 'cabinet' in request.form:
            config['cabinet'] = request.form.get('cabinet', '').strip()
        if 'centre_medical' in request.form:
            config['centre_medical'] = request.form.get('centre_medical', '').strip()
        if 'doctor_name' in request.form:
            config['doctor_name'] = request.form.get('doctor_name', '').strip()
        if 'location' in request.form:
            config['location'] = request.form.get('location', '').strip()

        # Update theme only if present in the form
        if 'theme' in request.form:
            selected_theme = request.form.get('theme', theme.DEFAULT_THEME)
            if selected_theme in theme.THEMES:
                config['theme'] = selected_theme
        
        # Update currency only if present in the form
        if 'currency' in request.form:
            config['currency'] = request.form.get('currency', 'EUR').strip()

        # Update VAT only if present in the form
        if 'vat' in request.form:
            vat_value = request.form.get('vat', '20.0').strip()
            try:
                config['vat'] = float(vat_value)
            except ValueError:
                return jsonify({"status": "error", "message": "Valeur de TVA invalide."}), 400

        # Mettre à jour les listes (médicaments, analyses, radiologies)
        # Conditionnel : met à jour la liste UNIQUEMENT si le champ du formulaire est présent ET non vide.
        # Cela empêche d'effacer accidentellement la liste existante si l'utilisateur ne modifie pas le textarea ou si le champ n'est pas envoyé.
        if 'medications_options' in request.form:
            medications_input = request.form.get('medications_options', '').strip()
            # Si le champ est présent et vide, il effacera la liste.
            # Si vous voulez qu'un champ vide ne modifie pas la liste, retirez la condition `if medications_input:`
            # et laissez-la simplement écraser avec une liste vide si le champ est vide.
            # La version actuelle (avec `if medications_input:`) ne met à jour que si l'input n'est PAS vide.
            if medications_input:
                config['medications_options'] = [line.strip() for line in medications_input.split('\n') if line.strip()]
            # else: # Si vous voulez qu'un champ vide efface la liste, décommentez cette partie
            #     config['medications_options'] = []

        if 'analyses_options' in request.form:
            analyses_input = request.form.get('analyses_options', '').strip()
            if analyses_input:
                config['analyses_options'] = [line.strip() for line in analyses_input.split('\n') if line.strip()]
            # else:
            #     config['analyses_options'] = []

        if 'radiologies_options' in request.form:
            radiologies_input = request.form.get('radiologies_options', '').strip()
            if radiologies_input:
                config['radiologies_options'] = [line.strip() for line in radiologies_input.split('\n') if line.strip()]
            # else:
            #     config['radiologies_options'] = []

        # Update RDV interval parameters only if present in the form
        if 'rdv_start_time' in request.form:
            config['rdv_start_time'] = request.form.get('rdv_start_time', '08:00').strip()
        if 'rdv_end_time' in request.form:
            config['rdv_end_time'] = request.form.get('rdv_end_time', '17:45').strip()
        if 'rdv_interval_minutes' in request.form:
            try:
                interval = int(request.form.get('rdv_interval_minutes', 15))
                if interval <= 0:
                    raise ValueError("L'intervalle de rendez-vous doit être un nombre positif.")
                config['rdv_interval_minutes'] = interval
            except ValueError:
                return jsonify({"status": "error", "message": "Intervalle de rendez-vous invalide."}), 400

        utils.save_config(config)
        
        # Re-initialize app utilities to load new config values globally
        utils.init_app(current_app._get_current_object())

        return jsonify({"status": "success", "message": "Paramètres mis à jour avec succès."})
    except Exception as e:
        print(f"Erreur lors de la mise à jour des paramètres : {e}")
        return jsonify({"status": "error", "message": f"Erreur lors de la mise à jour des paramètres : {e}"}), 500
      
@administrateur_bp.route("/lists/medications/download", methods=["GET"])
@admin_required
def download_medication_lists():
    """Route pour télécharger le fichier Excel des listes de médicaments, analyses et radiologies."""
    try:
        buffer, filename = handle_medication_list_download()
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("administrateur_bp.dashboard"))
    except Exception as e:
        flash(f"Erreur inattendue lors de la génération du fichier de listes : {e}", "danger")
        return redirect(url_for("administrateur_bp.dashboard"))

@administrateur_bp.route("/lists/medications/upload", methods=["POST"])
@admin_required
def upload_medication_lists():
    """Route pour importer et mettre à jour le fichier Excel des listes de médicaments, analyses et radiologies."""
    if 'lists_file' not in request.files:
        flash("Aucun fichier n'a été sélectionné.", "warning")
        return redirect(url_for("administrateur_bp.dashboard"))

    file = request.files['lists_file']
    success, message = handle_medication_list_upload(file)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    return redirect(url_for("administrateur_bp.dashboard"))