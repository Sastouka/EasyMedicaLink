# developpeur.py – Espace Développeur : clés machines + comptes admin
from datetime import date
from pathlib import Path
import json, os
import shutil # Added for zipping/unzipping
import zipfile # Added for zipping/unzipping
from flask import (
    Blueprint, render_template_string, request,
    redirect, url_for, flash, session, jsonify, send_file, current_app
)
from typing import Optional

import login as login_mod
import activation
import utils # Import utils to access set_dynamic_base_dir and DYNAMIC_BASE_DIR

# ───────── 1. Paramètres ─────────
_DEV_MAIL = "sastoukadigital@gmail.com"
_DEV_HASH = login_mod.hash_password("Sastouka_1989")
TRIAL_DAYS = activation.TRIAL_DAYS
# MODIFIÉ : J'ai gardé votre liste de plans qui exclut "essai", mais j'ai ajouté l'option d'essai pour la modale.
PLANS = [
    (f"essai_{TRIAL_DAYS}jours", f"Essai {TRIAL_DAYS} jours"),
    ("1 mois",   "1 mois"),
    ("1 an",     "1 an"),
    ("illimité", "Illimité")
]

# KEY_DB will now be static, within the application's base data folder
# It does not need to be dynamic per admin, as it's for developer keys.
# It will be placed directly under MEDICALINK_DATA.
KEY_DB: Optional[Path] = None

def _set_dev_paths():
    """
    Définit le chemin du fichier dev_keys.json.
    Ce fichier est local à l'installation de l'application (sous MEDICALINK_DATA),
    indépendant des dossiers d'administrateur individuels.
    """
    global KEY_DB
    
    # Le répertoire MEDICALINK_DATA est la racine pour tous les fichiers de données.
    medicalink_data_root = Path(utils.application_path) / "MEDICALINK_DATA"
    medicalink_data_root.mkdir(parents=True, exist_ok=True)

    KEY_DB = medicalink_data_root / "dev_keys.json"
    print(f"DEBUG: Developer KEY_DB path set to: {KEY_DB}")


def _load_keys() -> dict:
    if KEY_DB is None:
        _set_dev_paths() # Tenter de définir les chemins si ce n'est pas déjà fait
        if KEY_DB is None: # Si toujours None, quelque chose s'est mal passé
            print("ERROR: KEY_DB n'est toujours pas défini après tentative de _set_dev_paths. Impossible de charger les clés.")
            return {}
    
    # Ensure the directory exists before trying to read the file
    if not KEY_DB.parent.exists():
        KEY_DB.parent.mkdir(parents=True, exist_ok=True)

    if KEY_DB.exists():
        try:
            print(f"DEBUG (_load_keys): Loading keys from {KEY_DB}")
            return json.loads(KEY_DB.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"ERROR (_load_keys): Failed to decode JSON from {KEY_DB}: {e}. Returning empty dict.")
            return {}
        except Exception as e:
            print(f"ERROR (_load_keys): Unexpected error loading keys from {KEY_DB}: {e}. Returning empty dict.")
            return {}
    print(f"DEBUG (_load_keys): {KEY_DB} does not exist. Returning empty dict.")
    return {}

def _save_keys(d: dict):
    if KEY_DB is None:
        _set_dev_paths() # Tenter de définir les chemins si ce n'est pas déjà fait
        if KEY_DB is None: # Si toujours None, quelque chose s'est mal passé
            print("ERROR: KEY_DB n'est toujours pas défini après tentative de _set_dev_paths. Impossible de sauvegarder les clés.")
            return
    
    # Ensure the directory exists before trying to write the file
    if not KEY_DB.parent.exists():
        KEY_DB.parent.mkdir(parents=True, exist_ok=True)

    try:
        KEY_DB.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"DEBUG (_save_keys): Keys saved successfully to {KEY_DB}")
    except Exception as e:
        print(f"ERROR (_save_keys): Failed to save keys to {KEY_DB}: {e}")

developpeur_bp = Blueprint("developpeur_bp", __name__, url_prefix="/developpeur")

# ───────── 3. Helpers ─────────
def _dev_only():
    if not session.get("is_developpeur"):
        return redirect(url_for("developpeur_bp.login_page"))

def _store_key(mid, plan, key, nom, prenom):
    d = _load_keys()
    d[mid] = {"plan": plan, "key": key, "nom": nom, "prenom": prenom}
    _save_keys(d)

def _zip_directory(source_dir, output_zip_path):
    """Compresse un répertoire entier."""
    try:
        shutil.make_archive(output_zip_path.removesuffix('.zip'), 'zip', source_dir)
        print(f"DEBUG (_zip_directory): Directory '{source_dir}' zipped to '{output_zip_path}'")
        return True
    except Exception as e:
        print(f"ERROR (_zip_directory): Failed to zip directory '{source_dir}': {e}")
        return False

def _unzip_directory(zip_file_path, dest_dir):
    """Décompresse un fichier ZIP dans un répertoire de destination."""
    print(f"DEBUG (_unzip_directory): Attempting to unzip '{zip_file_path}' to '{dest_dir}'")
    try:
        dest_path = Path(dest_dir)
        # Ensure destination directory exists
        dest_path.mkdir(parents=True, exist_ok=True)
        print(f"DEBUG (_unzip_directory): Destination directory '{dest_dir}' ensured.")

        # Delete existing content of the destination directory (except the directory itself)
        if dest_path.exists():
            for item in dest_path.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                        print(f"DEBUG (_unzip_directory): Deleted file: {item}")
                    elif item.is_dir():
                        shutil.rmtree(item)
                        print(f"DEBUG (_unzip_directory): Deleted directory: {item}")
                except OSError as e:
                    print(f"ERROR (_unzip_directory): Failed to delete {item}: {e}")
                    # If we can't delete existing files, the unzip might fail later.
                    # This might be a permissions issue or file in use.
                    return False # Indicate failure if cleanup fails

            print(f"DEBUG (_unzip_directory): Existing content of '{dest_dir}' cleared.")

        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(dest_path)
        print(f"DEBUG (_unzip_directory): Zip file '{zip_file_path}' unzipped to '{dest_dir}' successfully.")
        return True
    except zipfile.BadZipFile as e:
        print(f"ERROR (_unzip_directory): Bad ZIP file '{zip_file_path}': {e}")
        return False
    except FileNotFoundError as e:
        print(f"ERROR (_unzip_directory): File not found during unzip operation: {e}")
        return False
    except PermissionError as e:
        print(f"ERROR (_unzip_directory): Permission denied during unzip operation: {e}")
        return False
    except Exception as e:
        print(f"ERROR (_unzip_directory): Unexpected error during unzip operation: {e}")
        return False

# ───────── 4. Routes ─────────
@developpeur_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        if request.form["email"].lower() == _DEV_MAIL \
           and login_mod.hash_password(request.form["password"]) == _DEV_HASH:
            session["is_developpeur"] = True
            flash("Mode développeur activé ✔", "success")
            return redirect(url_for("developpeur_bp.dashboard"))
        flash("Identifiants incorrects", "danger")
    return render_template_string(LOGIN_HTML)

@developpeur_bp.route("/dev_logout")
def dev_logout():
    session.pop("is_developpeur", None)
    flash("Mode développeur désactivé", "info")
    return redirect(url_for("login.login"))

@developpeur_bp.route("/")
def dashboard():
    if (r := _dev_only()): return r
    admins = {}
    all_users = login_mod.load_users()
    for e, u in all_users.items():
        if u.get("role") == "admin":
            # Rétrocompatibilité pour les anciennes entrées
            # Si clinic_creation_date n'existe pas, utiliser l'ancienne creation_date
            u['clinic_creation_date'] = u.get('clinic_creation_date', u.get('creation_date', 'N/A'))
            # Si account_creation_date n'existe pas, utiliser l'ancienne creation_date
            u['account_creation_date'] = u.get('account_creation_date', u.get('creation_date', 'N/A'))
            admins[e] = u
    return render_template_string(
        DASH_HTML,
        admins=admins,
        machines=_load_keys(),
        key=session.pop("generated_key", None),
        plans=PLANS
    )

@developpeur_bp.route("/generate", methods=["POST"])
def gen_custom():
    if (r := _dev_only()): return r
    mid   = request.form["machine_id"].strip().lower()
    plan  = request.form["plan"]
    nom   = request.form["nom"].strip()
    prenom= request.form["prenom"].strip()
    key   = activation.generate_activation_key_for_user(mid, plan)
    session["generated_key"] = key
    _store_key(mid, plan, key, nom, prenom)
    return redirect(url_for(".dashboard"))

@developpeur_bp.route("/create_admin", methods=["POST"])
def create_admin():
    if (r := _dev_only()): return r
    f, users = request.form, login_mod.load_users()
    email = f["email"].lower()
    if email in users:
        flash("Admin existe déjà", "warning")
        return redirect(url_for(".dashboard"))
    if f["password"] != f["confirm"]:
        flash("Les mots de passe ne correspondent pas", "danger")
        return redirect(url_for(".dashboard"))

    users[email] = {
        "role": "admin",
        "password": login_mod.hash_password(f["password"]),
        "clinic": f["clinic"],
        "clinic_creation_date": f["clinic_creation_date"], # Date from form for clinic
        "account_creation_date": date.today().isoformat(), # Date of account creation
        "address": f["address"],
        "phone": f["phone"], # Ajout du champ téléphone
        "active": True
    }
    login_mod.save_users(users)
    flash("Admin créé", "success")
    return redirect(url_for(".dashboard"))

@developpeur_bp.route("/edit_admin", methods=["POST"])
def edit_admin():
    if (r := _dev_only()): return r
    f = request.form
    original_email = f["original_email"].lower()
    new_email = f["email"].lower()
    new_password = f.get("password")
    confirm_password = f.get("confirm_password")

    users = login_mod.load_users()

    if original_email not in users:
        return jsonify({"status": "error", "message": "Compte admin non trouvé."})

    user_data = users[original_email]

    # Check if email is being changed to an existing email (that isn't the original)
    if new_email != original_email and new_email in users:
        return jsonify({"status": "error", "message": "Le nouvel email existe déjà."})

    # Update password if provided
    if new_password:
        if new_password != confirm_password:
            return jsonify({"status": "error", "message": "Les mots de passe ne correspondent pas."})
        user_data["password"] = login_mod.hash_password(new_password)

    # Update other fields (clinic's creation date, address, phone, active status)
    user_data["clinic"] = f["clinic"]
    user_data["clinic_creation_date"] = f["clinic_creation_date"] # Update clinic creation date
    user_data["address"] = f["address"]
    user_data["phone"] = f["phone"]
    user_data["active"] = f.get("active") == "on"
    # The 'account_creation_date' is NOT updated here, it remains the original creation date of the account.

    # If email changed, delete old entry and add new one
    if new_email != original_email:
        del users[original_email]
        users[new_email] = user_data
    else:
        users[new_email] = user_data # Ensure changes are saved to the correct key

    login_mod.save_users(users)
    return jsonify({"status": "success", "message": "Compte admin mis à jour."})

# AJOUT : NOUVELLE ROUTE POUR GÉRER LE CHANGEMENT DE PLAN
@developpeur_bp.route("/change_plan", methods=["POST"])
def change_admin_plan():
    if (r := _dev_only()): return r
    f = request.form
    admin_email = f.get("admin_email")
    new_plan = f.get("plan")
    machine_id = f.get("machine_id", "").strip().lower()
    
    # MODIFIÉ : On récupère et on valide la date d'activation depuis la modale
    date_str = f.get("activation_date")
    try:
        ref_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        flash("Date d'activation invalide pour le changement de plan.", "danger")
        return redirect(url_for(".dashboard"))

    if not all([admin_email, new_plan, machine_id]):
        flash("Information manquante pour changer le plan.", "danger")
        return redirect(url_for(".dashboard"))
    if len(machine_id) != 16:
        flash("L'ID machine doit faire exactement 16 caractères.", "danger")
        return redirect(url_for(".dashboard"))

    users = login_mod.load_users()
    if admin_email not in users:
        flash("Compte administrateur non trouvé.", "danger")
        return redirect(url_for(".dashboard"))

    # MODIFIÉ : On utilise la date choisie pour générer la clé
    new_key = activation.generate_activation_key_for_user(machine_id, new_plan, ref=ref_date)
    
    if 'activation' not in users[admin_email]:
        users[admin_email]['activation'] = {}

    users[admin_email]["activation"]["plan"] = new_plan
    # MODIFIÉ : On sauvegarde la date choisie comme date d'activation
    users[admin_email]["activation"]["activation_date"] = ref_date.isoformat()
    users[admin_email]["activation"]["activation_code"] = new_key
    
    login_mod.save_users(users)
    flash(f"Le plan pour {admin_email} a été mis à jour vers '{new_plan}'. Nouvelle clé générée : {new_key}", "success")
    return redirect(url_for(".dashboard"))

@developpeur_bp.route("/toggle_active/<admin_email>")
def toggle_active(admin_email):
    if (r := _dev_only()): return r
    users = login_mod.load_users()
    if admin_email in users and users[admin_email]["role"] == "admin":
        users[admin_email]["active"] = not users[admin_email].get("active", True)
        login_mod.save_users(users)
    return redirect(url_for(".dashboard"))

@developpeur_bp.route("/delete_admin/<admin_email>")
def delete_admin(admin_email):
    if (r := _dev_only()): return r
    users = login_mod.load_users()
    users.pop(admin_email, None)
    login_mod.save_users(users)
    return redirect(url_for(".dashboard"))

@developpeur_bp.route("/data/medicalink/export")
def export_medicalink_data():
    if (r := _dev_only()): return r
    
    medicalink_data_path = Path(utils.application_path) / "MEDICALINK_DATA"
    output_zip_name = f"MEDICALINK_DATA_backup_{date.today().isoformat()}.zip"
    output_zip_path = Path(utils.application_path) / output_zip_name

    if _zip_directory(str(medicalink_data_path), str(output_zip_path)):
        print(f"DEBUG (export_medicalink_data): Sending file: {output_zip_path}")
        return send_file(str(output_zip_path), as_attachment=True, download_name=output_zip_name)
    else:
        flash("Erreur lors de l'exportation du dossier MEDICALINK_DATA.", "danger")
        return redirect(url_for(".dashboard"))

@developpeur_bp.route("/data/medicalink/import", methods=["POST"])
def import_medicalink_data():
    if (r := _dev_only()): return r

    if 'medicalink_zip' not in request.files or request.files['medicalink_zip'].filename == '':
        return jsonify({"status": "error", "message": "Aucun fichier ZIP sélectionné."})

    uploaded_file = request.files['medicalink_zip']
    if not uploaded_file.filename.endswith('.zip'):
        return jsonify({"status": "error", "message": "Le fichier doit être un fichier ZIP."})

    temp_zip_path = Path(utils.application_path) / "temp_medicalink_import.zip"
    medicalink_data_path = Path(utils.application_path) / "MEDICALINK_DATA"

    try:
        uploaded_file.save(str(temp_zip_path))
        print(f"DEBUG (import_medicalink_data): Temporary zip saved to {temp_zip_path}")

        # Arrêter l'application n'est pas possible directement depuis Flask.
        # Le message d'avertissement dans le frontend est crucial.

        if _unzip_directory(str(temp_zip_path), str(medicalink_data_path)):
            # Recharger les utilisateurs après l'importation pour rafraîchir les données
            login_mod.load_users()
            print(f"DEBUG (import_medicalink_data): MEDICALINK_DATA imported successfully.")
            return jsonify({"status": "success", "message": "Données MEDICALINK_DATA importées avec succès. Veuillez redémarrer l'application pour que tous les changements prennent effet."})
        else:
            return jsonify({"status": "error", "message": "Échec de la décompression du fichier ZIP."})
    except Exception as e:
        print(f"ERROR (import_medicalink_data): Error during import: {e}")
        return jsonify({"status": "error", "message": f"Erreur lors de l'importation: {e}"})
    finally:
        if temp_zip_path.exists():
            temp_zip_path.unlink() # Supprimer le fichier temporaire
            print(f"DEBUG (import_medicalink_data): Temporary zip file {temp_zip_path} removed.")

# --- NOUVELLE ROUTE POUR DÉCLENCHER UNE SAUVEGARDE MANUELLE ---
@developpeur_bp.route('/trigger-backup', methods=['POST'])
def trigger_backup_dev():
    """
    Déclenche manuellement la sauvegarde du dossier MEDICALINK_DATA vers Firebase.
    """
    if (r := _dev_only()): return r

    firebase_manager = current_app.firebase_manager
    if not firebase_manager:
        flash("Le service de sauvegarde Firebase n'est pas configuré.", "danger")
        return redirect(url_for('developpeur_bp.dashboard'))

    # Chemin du dossier racine des données à sauvegarder
    local_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MEDICALINK_DATA")
    
    # Appel de la fonction de sauvegarde
    flash("Lancement de la sauvegarde manuelle... Cela peut prendre quelques instants.", "info")
    success = firebase_manager.backup_directory(local_data_path, remote_folder="daily_backups")

    if success:
        flash("Sauvegarde manuelle vers Firebase terminée avec succès !", "success")
    else:
        flash("La sauvegarde manuelle a échoué. Veuillez vérifier les journaux (logs) du serveur.", "danger")
        
    return redirect(url_for('developpeur_bp.dashboard'))

# --- NOUVELLE ROUTE POUR LA RESTAURATION DEPUIS L'ESPACE DÉVELOPPEUR ---
@developpeur_bp.route('/restore-from-backup', methods=['POST'])
def restore_from_backup_dev():
    """
    Déclenche la restauration de la dernière sauvegarde depuis Firebase.
    Cette route est protégée et accessible uniquement par le développeur.
    """
    # Vérifie si l'utilisateur est bien le développeur
    if (r := _dev_only()): return r

    firebase_manager = current_app.firebase_manager
    if not firebase_manager:
        flash("Le service de sauvegarde Firebase n'est pas configuré.", "danger")
        return redirect(url_for('developpeur_bp.dashboard'))

    # Chemin du dossier racine des données à restaurer
    local_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MEDICALINK_DATA")
    
    # Appel de la fonction de restauration
    success = firebase_manager.restore_latest_backup(local_data_path, remote_folder="daily_backups")

    if success:
        flash("Restauration à partir de la dernière sauvegarde réussie ! Il est recommandé de redémarrer l'application pour que tous les changements soient pris en compte.", "success")
    else:
        flash("La restauration a échoué. Veuillez vérifier les journaux (logs) du serveur pour plus de détails.", "danger")
        
    return redirect(url_for('developpeur_bp.dashboard'))

# ───────── 5. Templates (HTML condensé) ─────────
LOGIN_HTML = """
<!doctype html>
<html lang='fr'>
{{ pwa_head()|safe }}
<head>
<meta charset='utf-8'>
<title>Développeur | Connexion</title>
<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
<link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'>
<link href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css' rel='stylesheet'>
<style>
:root{
  --grad1:#4b6cb7;  /* bleu   */
  --grad2:#182848;  /* indigo */
}
body{
  background:linear-gradient(90deg,var(--grad1),var(--grad2));
  display:flex;align-items:center;justify-content:center;min-height:100vh;
}
.card{border-radius:1rem;overflow:hidden;}
.card-header{
  background:linear-gradient(45deg,var(--grad1),var(--grad2));
  color:#fff;font-weight:600;text-align:center;padding:1.5rem 0;
  border-bottom:none;
}
.form-control:focus{
  border-color:var(--grad1);
  box-shadow:0 0 0 .25rem rgba(75,108,183,.25);
}
.btn-grad{
  background:linear-gradient(90deg,var(--grad1),var(--grad2));
  border:none;color:#fff;
  padding:.75rem 1.5rem;border-radius:.5rem;
  transition:all .3s ease;
}
.btn-grad:hover{
  transform:translateY(-2px);
  box-shadow:0 4px 8px rgba(0,0,0,.2);
}
.alert{border-radius:.5rem;}
</style>
</head>
<body>
<div class='container'>
  <div class='row justify-content-center'>
    <div class='col-md-6 col-lg-5'>
      <div class='card shadow-lg'>
        <h3 class='card-header'><i class='fas fa-code me-2'></i>Mode Développeur</h3>
        <div class='card-body p-4'>
          {% with m=get_flashed_messages(with_categories=true) %}
            {% if m %}
              {% for c,msg in m %}
                <div class='alert alert-{{c}} alert-dismissible fade show shadow-sm' role='alert'>
                  <i class='fas fa-info-circle me-2'></i>{{msg}}
                  <button type='button' class='btn-close' data-bs-dismiss='alert'></button>
                </div>
              {% endfor %}
            {% endif %}
          {% endwith %}
          <form method='POST'>
            <div class='mb-3'>
              <label for='emailInput' class='form-label fw-semibold'>Email</label>
              <div class='input-group'>
                <span class='input-group-text'><i class='fas fa-envelope'></i></span>
                <input type='email' class='form-control' id='emailInput' name='email' required>
              </div>
            </div>
            <div class='mb-4'>
              <label for='passwordInput' class='form-label fw-semibold'>Mot de passe</label>
              <div class='input-group'>
                <span class='input-group-text'><i class='fas fa-lock'></i></span>
                <input type='password' class='form-control' id='passwordInput' name='password' required>
              </div>
            </div>
            <div class='d-grid'>
              <button type='submit' class='btn btn-grad'><i class='fas fa-sign-in-alt me-2'></i>Se connecter</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</div>
<script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
</body>
</html>
"""

DASH_HTML = """
<!doctype html>
<html lang='fr'>
{{ pwa_head()|safe }}
<head>
<meta charset='utf-8'>
<title>Développeur | Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">

<link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'>
<link href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css' rel='stylesheet'>
<link href='https://cdn.datatables.net/1.13.1/css/dataTables.bootstrap5.min.css' rel='stylesheet'>
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>

<style>
:root{
  --grad1:#4b6cb7;
  --grad2:#182848;
}
body{background:#f5f7fb;}
.navbar{
  background:linear-gradient(90deg,var(--grad1),var(--grad2));
}
.card-header{
  background:linear-gradient(45deg,var(--grad1),var(--grad2));
  color:#fff;font-weight:600;
}
.section-icon{margin-right:.45rem;}
.table thead{background:#e9ecef}
.btn-grad{
  background:linear-gradient(90deg,var(--grad1),var(--grad2));
  border:none;color:#fff;
}
.no-pointer-events {
    pointer-events: none;
}
.mono{font-family: monospace; font-size: 0.9em; color: #E83E8C;}
</style>
</head>

<body>
<nav class='navbar navbar-dark shadow'>
  <div class='container-fluid'>
    <span class='navbar-brand d-flex align-items-center gap-2'>
      <i class='fas fa-code'></i> Mode Développeur <span class='fw-light'>EASYMEDICALINK</span>
    </span>
    <a href='{{ url_for("developpeur_bp.dev_logout") }}'
       class='btn btn-sm btn-outline-light rounded-pill'><i class='fas fa-sign-out-alt'></i> Quitter</a>
  </div>
</nav>

<div class='container my-4'>

  {% with m=get_flashed_messages(with_categories=true) %}
    {% if m %}
      {% for c,msg in m %}
        <div class='alert alert-{{c}} alert-dismissible fade show shadow-sm' role='alert'>
          <i class='fas fa-info-circle me-2'></i>{{msg}}
          <button type='button' class='btn-close' data-bs-dismiss='alert'></button>
        </div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  <div class='card shadow-sm mb-4'>
    <h5 class='card-header'><i class='fas fa-key section-icon'></i>Générer une clé machine</h5>
    <div class='card-body'>
      <form class='row gy-2 gx-3 align-items-end' method='POST'
            action='{{ url_for("developpeur_bp.gen_custom") }}'>
        <div class='col-12 col-md-3'>
          <label class='form-label fw-semibold'><i class='fas fa-desktop me-1'></i>ID machine</label>
          <input name='machine_id' class='form-control' placeholder='16 caractères' required>
        </div>
        <div class='col-12 col-md-2'>
          <label class='form-label fw-semibold'><i class='fas fa-user me-1'></i>Nom</label>
          <input name='nom' class='form-control' required>
        </div>
        <div class='col-12 col-md-2'>
          <label class='form-label fw-semibold'><i class='fas fa-user me-1'></i>Prénom</label>
          <input name='prenom' class='form-control' required>
        </div>
        <div class='col-12 col-md-3'>
          <label class='form-label fw-semibold'><i class='fas fa-calendar-alt me-1'></i>Date d'activation</label>
          <input name='activation_date' type='date' class='form-control' value='{{ today_date }}' required>
        </div>
        <div class='col-12 col-md-2'>
          <label class='form-label fw-semibold'><i class='fas fa-file-signature me-1'></i>Plan</label>
          <select name='plan' class='form-select'>
            {% for c,l in plans %}<option value='{{c}}'>{{l}}</option>{% endfor %}
          </select>
        </div>
        <div class='col-12 d-grid mt-3'>
          <button class='btn btn-grad'><i class='fas fa-magic me-1'></i>Générer la Clé</button>
        </div>
        {% if key %}
          <div class='col-12'>
            <div class='alert alert-info mt-3 shadow-sm'>
              <i class='fas fa-check-circle me-2'></i>
              <strong>Clé&nbsp;:</strong> {{key}}
            </div>
          </div>
        {% endif %}
      </form>
    </div>
  </div>

  <div class='card shadow-sm mb-4'>
    <h5 class='card-header'><i class='fas fa-server section-icon'></i>Clés machines</h5>
    <div class='card-body'>
      <div class="table-responsive">
        <table id='tblKeys' class='table table-striped table-hover rounded overflow-hidden'>
          <thead><tr><th>ID</th><th>Propriétaire</th><th>Plan</th><th>Clé</th></tr></thead>
          <tbody>
            {% for mid,info in machines.items() %}
              <tr>
                <td class='fw-semibold'>{{mid}}</td>
                <td>{{info.prenom}}&nbsp;{{info.nom}}</td>
                <td>{{info.plan}}</td>
                <td class='text-break'>{{info.key}}</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <div class='card shadow-sm mb-4'>
    <h5 class='card-header'><i class='fas fa-user-plus section-icon'></i>Créer un compte admin</h5>
    <div class='card-body'>
      <form class='row gy-2 gx-3 align-items-end' method='POST'
            action='{{ url_for("developpeur_bp.create_admin") }}'>
        <div class='col-12 col-md-4'>
          <label class='form-label fw-semibold'><i class='fas fa-envelope me-1'></i>Email</label>
          <input name='email' type='email' class='form-control' required>
        </div>
        <div class='col-12 col-md-4'>
          <label class='form-label fw-semibold'><i class='fas fa-key me-1'></i>Mot de passe</label>
          <input name='password' type='password' class='form-control' required>
        </div>
        <div class='col-12 col-md-4'>
          <label class='form-label fw-semibold'><i class='fas fa-key me-1'></i>Confirmer</label>
          <input name='confirm' type='password' class='form-control' required>
        </div>
        <div class='col-12 col-md-4'>
          <label class='form-label fw-semibold'><i class='fas fa-hospital me-1'></i>Clinique</label>
          <input name='clinic' class='form-control' required>
        </div>
        <div class='col-12 col-md-4'>
          <label class='form-label fw-semibold'><i class='fas fa-calendar-alt me-1'></i>Date création (Clinique)</label>
          <input name='clinic_creation_date' type='date' class='form-control' required>
        </div>
        <div class='col-12 col-md-4'>
          <label class='form-label fw-semibold'><i class='fas fa-map-marker-alt me-1'></i>Adresse</label>
          <input name='address' class='form-control' required>
        </div>
        <div class='col-12 col-md-4'>
          <label class='form-label fw-semibold'><i class='fas fa-phone me-1'></i>Téléphone</label>
          <input name='phone' type='tel' class='form-control' placeholder='Numéro de téléphone' required>
        </div>
        <input type='hidden' name='role' value='admin'>
        <div class='col-12 d-grid mt-2'>
          <button class='btn btn-grad'><i class='fas fa-user-plus me-1'></i>Créer</button>
        </div>
      </form>
    </div>
  </div>

  <div class='card shadow-sm'>
    <h5 class='card-header'><i class='fas fa-users section-icon'></i>Comptes admin</h5>
    <div class='card-body'>
      <div class="table-responsive">
        <table id='tblAdmin' class='table table-striped table-hover rounded overflow-hidden'>
          <thead><tr><th>Email</th><th>Clinique</th><th>Téléphone</th><th>Adresse</th><th>Date création (Clinique)</th><th>Date création (Compte)</th><th>Plan</th><th>ID Machine</th><th>Actif</th><th>Actions</th></tr></thead>
          <tbody>
            {% for e,u in admins.items() %}
              <tr>
                <td>{{e}}</td>
                <td>{{u.clinic}}</td>
                <td>{{u.phone}}</td>
                <td>{{u.address}}</td>
                <td>{{u.clinic_creation_date}}</td>
                <td>{{u.account_creation_date}}</td>
                <td><span class="badge bg-primary">{{ u.get("activation", {}).get("plan", "N/A") }}</span></td>
                <td class="mono">{{ u.get("machine_id", "N/A") }}</td>
                <td><span class='badge {{'bg-success' if u.active else 'bg-secondary'}}'>{{'Oui' if u.active else 'Non'}}</span></td>
                <td class='text-nowrap'>
                  {% if u.phone %}
                  <a class='btn btn-sm btn-success me-1' title='Contacter via WhatsApp'
                     href='https://wa.me/{{ u.phone | replace("+", "") }}' target='_blank'>
                     <i class='fab fa-whatsapp'></i>
                  </a>
                  {% endif %}
                  <button class='btn btn-sm btn-info me-1 edit-admin-btn' title='Modifier'
                          data-bs-toggle='modal' data-bs-target='#editAdminModal'
                          data-email='{{ e }}' 
                          data-clinic='{{ u.clinic }}'
                          data-clinic_creation_date='{{ u.clinic_creation_date }}'
                          data-address='{{ u.address }}'
                          data-phone='{{ u.phone }}'
                          data-active='{{ u.get('active', False) | tojson }}'>
                     <i class='fas fa-pen'></i>
                  </button>
                  <button class='btn btn-sm btn-warning me-1 change-plan-btn' title='Modifier Plan' 
                          data-bs-toggle='modal' data-bs-target='#changePlanModal'
                          data-email='{{ e }}' 
                          data-plan='{{ u.get("activation", {}).get("plan", "") }}' 
                          data-machine_id='{{ u.get("machine_id", "") }}'>
                     <i class='fas fa-file-invoice-dollar'></i>
                  </button>
                  <a class='btn btn-sm btn-outline-secondary' title='Activer/Désactiver'
                     href='{{ url_for('developpeur_bp.toggle_active',admin_email=e) }}'>
                     <i class='fas fa-power-off'></i></a>
                  <a class='btn btn-sm btn-outline-danger' title='Supprimer'
                     href='{{ url_for('developpeur_bp.delete_admin',admin_email=e) }}'>
                     <i class='fas fa-trash'></i></a>
                </td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <div class='card shadow-sm mt-4'>
    <h5 class='card-header'><i class='fas fa-database section-icon'></i>Gestion des Données et Sauvegardes</h5>
    <div class='card-body'>
      <div class="d-flex justify-content-center gap-3 flex-wrap">
        <a href="{{ url_for('developpeur_bp.export_medicalink_data') }}" class="btn btn-success">
          <i class="fas fa-file-archive me-2"></i>Exporter les Données Locales (ZIP)
        </a>
        <form action="{{ url_for('developpeur_bp.trigger_backup_dev') }}" method="POST"
              onsubmit="return confirm('Voulez-vous vraiment lancer une sauvegarde manuelle maintenant ? Cela créera une nouvelle archive sur le cloud.');">
          <button type="submit" class="btn btn-warning">
            <i class="fas fa-cloud-upload-alt me-2"></i>Forcer une Sauvegarde
          </button>
        </form>
      </div>
    </div>
  </div>
  
  <div class='card shadow-sm mt-4'>
    <h5 class='card-header'><i class='fas fa-cloud-download-alt section-icon'></i>Restauration des Données Cloud</h5>
    <div class='card-body text-center'>
      <p class='text-muted'>
        Cette action va remplacer **toutes** les données locales actuelles par la dernière sauvegarde quotidienne stockée sur Firebase.
        Utilisez cette fonction avec une extrême prudence, uniquement en cas de perte de données majeure.
      </p>
      
      <form action="{{ url_for('developpeur_bp.restore_from_backup_dev') }}" method="POST"
            onsubmit="return confirm('ATTENTION : Êtes-vous absolument certain de vouloir restaurer les données ? Toutes les données locales actuelles seront définitivement écrasées !');">
        <button type="submit" class="btn btn-danger">
          <i class="fas fa-exclamation-triangle me-2"></i>Lancer la Restauration
        </button>
      </form>
      
    </div>
  </div>

</div>

<div class="modal fade" id="editAdminModal" tabindex="-1" aria-labelledby="editAdminModalLabel" aria-hidden="true">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="editAdminModalLabel">Modifier le compte Admin</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <form id="editAdminForm" method="POST" action="">
        <div class="modal-body">
          <input type="hidden" name="original_email" id="edit_original_email">
          <div class="mb-3">
            <label for="edit_email" class="form-label">Email</label>
            <input type="email" class="form-control" id="edit_email" name="email" required>
          </div>
          <div class="mb-3">
            <label for="edit_clinic" class="form-label">Nom de la clinique</label>
            <input type="text" class="form-control" id="edit_clinic" name="clinic" required>
          </div>
          <div class="mb-3">
            <label for="edit_clinic_creation_date" class="form-label">Date de création (Clinique)</label>
            <input type="date" class="form-control" id="edit_clinic_creation_date" name="clinic_creation_date" required>
          </div>
          <div class="mb-3">
            <label for="edit_address" class="form-label">Adresse</label>
            <input type="text" class="form-control" id="edit_address" name="address" required>
          </div>
          <div class="mb-3">
            <label for="edit_phone" class="form-label">Téléphone</label>
            <input type="tel" class="form-control" id="edit_phone" name="phone" placeholder='Numéro de téléphone' required>
          </div>
          <div class="mb-3">
            <label for="edit_password" class="form-label">Nouveau mot de passe (laisser vide si inchangé)</label>
            <input type="password" class="form-control" id="edit_password" name="password">
          </div>
          <div class="mb-3">
            <label for="edit_confirm_password" class="form-label">Confirmer le nouveau mot de passe</label>
            <input type="password" class="form-control" id="edit_confirm_password" name="confirm_password">
          </div>
          <div class="form-check">
            <input class="form-check-input" type="checkbox" id="edit_active" name="active">
            <label class="form-check-label" for="edit_active">
              Actif
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
          <button type="submit" class="btn btn-primary">Enregistrer les modifications</button>
        </div>
      </form>
    </div>
  </div>
</div>

<div class="modal fade" id="changePlanModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Modifier Plan de Licence</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<form method="POST" action="{{ url_for('developpeur_bp.change_admin_plan') }}">
<div class="modal-body">
    <input type="hidden" name="admin_email" id="plan_admin_email">
    <p>Compte : <strong id="plan_admin_email_display"></strong></p>
    <div class="mb-3"><label for="plan_machine_id" class="form-label">ID Machine Client</label><input type="text" class="form-control mono" id="plan_machine_id" name="machine_id" required minlength="16" maxlength="16" placeholder="ID auto-collecté"><div class="form-text">Cet ID est normalement collecté à la connexion du client.</div></div>
    <div class="mb-3"><label for="plan_select" class="form-label">Nouveau Plan</label><select name="plan" id="plan_select" class="form-select">{% for value, label in plans %}<option value="{{ value }}">{{ label }}</option>{% endfor %}</select></div>
    <div class="mb-3"><label for="plan_activation_date" class="form-label">Date d'activation</label><input type="date" class="form-control" id="plan_activation_date" name="activation_date" required></div>
</div>
<div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button><button type="submit" class="btn btn-primary">Mettre à jour</button></div>
</form></div></div></div>

<script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
<script src='https://code.jquery.com/jquery-3.6.0.min.js'></script>
<script src='https://cdn.datatables.net/1.13.1/js/jquery.dataTables.min.js'></script>
<script src='https://cdn.datatables.net/1.13.1/js/dataTables.bootstrap5.min.js'></script>
<script>
  $(function(){
    $('#tblKeys, #tblAdmin').DataTable({
      lengthChange:false,
      language:{url:'//cdn.datatables.net/plug-ins/1.13.1/i18n/fr-FR.json'}
    });

    $('#editAdminModal').on('show.bs.modal', function (event) {
      const button = $(event.relatedTarget);
      const email = button.data('email');
      const clinic = button.data('clinic');
      const clinic_creation_date = button.data('clinic_creation_date');
      const address = button.data('address');
      const phone = button.data('phone');
      const active = button.data('active');
      const modal = $(this);
      modal.find('#edit_original_email').val(email);
      modal.find('#edit_email').val(email);
      modal.find('#edit_clinic').val(clinic);
      modal.find('#edit_clinic_creation_date').val(clinic_creation_date);
      modal.find('#edit_address').val(address);
      modal.find('#edit_phone').val(phone);
      modal.find('#edit_active').prop('checked', active);
      modal.find('#editAdminForm').attr('action', '{{ url_for("developpeur_bp.edit_admin") }}');
    });

    $('#editAdminForm').on('submit', function(e) {
      e.preventDefault();
      const form = $(this);
      const formData = form.serialize();
      const newPassword = $('#edit_password').val();
      const confirmPassword = $('#edit_confirm_password').val();

      if (newPassword && newPassword !== confirmPassword) {
        Swal.fire({ icon: 'error', title: 'Erreur', text: 'Les mots de passe ne correspondent pas.' });
        return;
      }

      fetch(form.attr('action'), {
        method: 'POST',
        body: new URLSearchParams(formData),
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      })
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          Swal.fire({ icon: 'success', title: 'Succès', text: data.message })
          .then(() => { location.reload(); });
        } else {
          Swal.fire({ icon: 'error', title: 'Erreur', text: data.message });
        }
      })
      .catch(error => {
        console.error('Error:', error);
        Swal.fire({ icon: 'error', title: 'Erreur réseau', text: 'Impossible de se connecter.' });
      });
    });

    $('#changePlanModal').on('show.bs.modal', function(e){
      const btn = $(e.relatedTarget), modal = $(this);
      const email = btn.data('email'), machine_id = btn.data('machine_id');
      const today = new Date().toISOString().split('T')[0];
      modal.find('#plan_admin_email').val(email);
      modal.find('#plan_admin_email_display').text(email);
      modal.find('#plan_select').val(btn.data('plan'));
      modal.find('#plan_machine_id').val(machine_id);
      modal.find('#plan_activation_date').val(today);
      if (!machine_id) modal.find('#plan_machine_id').attr('placeholder', 'Le client doit se connecter...');
    });
  });
</script>
</body>
</html>
"""