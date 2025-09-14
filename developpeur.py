# developpeur.py – Espace Développeur (VERSION CORRIGÉE ET MISE À JOUR)
from datetime import date
from pathlib import Path
import json
import os
import shutil
import zipfile
from flask import (
    Blueprint, render_template_string, request,
    redirect, url_for, flash, session, jsonify, send_file, current_app
)
from typing import Optional
import qrcode
import io
import base64

import login as login_mod
import activation
import utils
from activation import get_hardware_id, create_paypal_order, capture_paypal_order
from ia_assitant import db as ia_db # Ajout pour corriger le verrouillage de la DB

# ───────── 1. Paramètres ─────────
_DEV_MAIL = "sastoukadigital@gmail.com"
_DEV_HASH = login_mod.hash_password("Sastouka_1989")
TRIAL_DAYS = activation.TRIAL_DAYS

PLANS = [
    (f"essai_{TRIAL_DAYS}jours", f"Essai {TRIAL_DAYS} jours"),
    ("web_1_mois", "Web - 1 Mois (15$)"),
    ("web_1_an", "Web - 1 An (100$)"),
    ("local_1_an", "Local Windows - 1 An (50$)"),
    ("local_illimite", "Local Windows - Illimité (120$)")
]

KEY_DB: Optional[Path] = None
payment_orders = {}  # Pour suivre les paiements personnalisés

def _set_dev_paths():
    global KEY_DB
    medicalink_data_root = Path(utils.application_path) / "MEDICALINK_DATA"
    medicalink_data_root.mkdir(parents=True, exist_ok=True)
    KEY_DB = medicalink_data_root / "dev_keys.json"

def _load_keys() -> dict:
    if KEY_DB is None: _set_dev_paths()
    if KEY_DB.exists():
        try:
            return json.loads(KEY_DB.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"ERROR (_load_keys): Erreur chargement {KEY_DB}: {e}.")
            return {}
    return {}

def _save_keys(d: dict):
    if KEY_DB is None: _set_dev_paths()
    try:
        KEY_DB.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"ERROR (_save_keys): Erreur sauvegarde {KEY_DB}: {e}")

developpeur_bp = Blueprint("developpeur_bp", __name__, url_prefix="/developpeur")

# ───────── 3. Helpers ─────────
def _dev_only():
    pass

def _store_key(mid, plan, key, nom, prenom):
    d = _load_keys()
    d[mid] = {"plan": plan, "key": key, "nom": nom, "prenom": prenom}
    _save_keys(d)

def _zip_directory(source_dir, output_zip_path):
    try:
        shutil.make_archive(output_zip_path.removesuffix('.zip'), 'zip', source_dir)
        return True
    except Exception as e:
        print(f"ERROR (_zip_directory): Echec zip '{source_dir}': {e}")
        return False

def _unzip_directory(zip_file_path, dest_dir):
    try:
        dest_path = Path(dest_dir)
        dest_path.mkdir(parents=True, exist_ok=True)
        if dest_path.exists():
            for item in dest_path.iterdir():
                if item.is_file(): item.unlink()
                elif item.is_dir(): shutil.rmtree(item)
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(dest_path)
        return True
    except Exception as e:
        print(f"ERROR (_unzip_directory): Echec unzip '{zip_file_path}': {e}")
        return False

# ───────── 4. Routes ─────────
@developpeur_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        if request.form["email"].lower() == _DEV_MAIL and login_mod.hash_password(request.form["password"]) == _DEV_HASH:
            session["is_developpeur"] = True
            flash("Session développeur activée ✔", "success")
            return redirect(url_for("developpeur_bp.dashboard"))
        flash("Identifiants incorrects", "danger")
    return render_template_string(LOGIN_HTML)

@developpeur_bp.route("/dev_logout")
def dev_logout():
    session.pop("is_developpeur", None)
    flash("Session développeur désactivée", "info")
    return redirect(url_for("login.login"))

@developpeur_bp.route("/")
def dashboard():
    if (r := _dev_only()): return r
    admins = {}
    all_users = login_mod.load_users()
    for e, u in all_users.items():
        if u.get("role") == "admin":
            u['clinic_creation_date'] = u.get('clinic_creation_date', u.get('creation_date', 'N/A'))
            u['account_creation_date'] = u.get('account_creation_date', u.get('creation_date', 'N/A'))
            admins[e] = u
            
    payment_link = session.pop("payment_link", None)
    qr_code_base64 = session.pop("qr_code_base64", None)
    payment_amount = session.pop("payment_amount", None)
    payment_description = session.pop("payment_description", None)

    return render_template_string(
        DASH_HTML,
        admins=admins,
        machines=_load_keys(),
        key=session.pop("generated_key", None),
        plans=PLANS,
        today_date=date.today().isoformat(),
        payment_link=payment_link,
        qr_code_base64=qr_code_base64,
        payment_amount=payment_amount,
        payment_description=payment_description
    )

@developpeur_bp.route("/generer_paiement", methods=["POST"])
def generer_paiement():
    if (r := _dev_only()): return r
    try:
        amount = request.form.get("amount")
        description = request.form.get("description", "Paiement personnalisé")
        if not amount or float(amount) <= 0:
            flash("Veuillez entrer un montant valide.", "danger")
            return redirect(url_for(".dashboard"))

        return_url = url_for("developpeur_bp.paiement_succes", _external=True)
        cancel_url = url_for("developpeur_bp.paiement_annule", _external=True)
        
        oid, payment_link = create_paypal_order(amount, return_url, cancel_url)
        payment_orders[oid] = {"amount": amount, "description": description}
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(payment_link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        session["payment_link"] = payment_link
        session["qr_code_base64"] = qr_code_base64
        session["payment_amount"] = amount
        session["payment_description"] = description
        
        flash("Lien de paiement généré avec succès !", "success")
    except Exception as e:
        flash(f"Erreur lors de la génération du lien : {e}", "danger")
    return redirect(url_for(".dashboard"))

@developpeur_bp.route("/paiement_succes")
def paiement_succes():
    oid = request.args.get("token")
    if oid and oid in payment_orders and capture_paypal_order(oid):
        details = payment_orders.pop(oid)
        return render_template_string(PAYMENT_SUCCESS_HTML, details=details)
    return render_template_string(PAYMENT_FAIL_HTML)

@developpeur_bp.route("/paiement_annule")
def paiement_annule():
    oid = request.args.get("token")
    if oid in payment_orders:
        payment_orders.pop(oid)
    return render_template_string(PAYMENT_CANCEL_HTML)


@developpeur_bp.route("/generate", methods=["POST"])
def gen_custom():
    if (r := _dev_only()): return r
    mid, plan, nom, prenom = request.form["machine_id"].strip().lower(), request.form["plan"], request.form["nom"].strip(), request.form["prenom"].strip()
    key = activation.generate_activation_key_for_user(mid, plan)
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
    elif f["password"] != f["confirm"]:
        flash("Les mots de passe ne correspondent pas", "danger")
    else:
        users[email] = {
            "role": "admin", "password": login_mod.hash_password(f["password"]),
            "clinic": f["clinic"], "clinic_creation_date": f["clinic_creation_date"],
            "account_creation_date": date.today().isoformat(), "address": f["address"],
            "phone": f["phone"], "active": True
        }
        login_mod.save_users(users)
        flash("Admin créé", "success")
    return redirect(url_for(".dashboard"))

@developpeur_bp.route("/edit_admin", methods=["POST"])
def edit_admin():
    if (r := _dev_only()): return r
    f = request.form
    original_email, new_email = f["original_email"].lower(), f["email"].lower()
    new_password, confirm_password = f.get("password"), f.get("confirm_password")
    users = login_mod.load_users()

    if original_email not in users:
        return jsonify({"status": "error", "message": "Compte admin non trouvé."})
    if new_email != original_email and new_email in users:
        return jsonify({"status": "error", "message": "Le nouvel email existe déjà."})
    if new_password and new_password != confirm_password:
        return jsonify({"status": "error", "message": "Les mots de passe ne correspondent pas."})

    user_data = users.pop(original_email)
    if new_password: user_data["password"] = login_mod.hash_password(new_password)
    user_data.update({
        "clinic": f["clinic"], "clinic_creation_date": f["clinic_creation_date"],
        "address": f["address"], "phone": f["phone"], "active": f.get("active") == "on"
    })
    users[new_email] = user_data
    login_mod.save_users(users)
    return jsonify({"status": "success", "message": "Compte admin mis à jour."})

@developpeur_bp.route("/change_plan", methods=["POST"])
def change_admin_plan():
    if (r := _dev_only()): return r
    f = request.form
    admin_email, new_plan, machine_id = f.get("admin_email"), f.get("plan"), f.get("machine_id", "").strip().lower()
    date_str = f.get("activation_date")

    try: ref_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        flash("Date d'activation invalide.", "danger")
        return redirect(url_for(".dashboard"))

    if not all([admin_email, new_plan, machine_id]) or len(machine_id) != 16:
        flash("Information manquante ou ID machine invalide.", "danger")
        return redirect(url_for(".dashboard"))

    users = login_mod.load_users()
    if admin_email not in users:
        flash("Compte admin non trouvé.", "danger")
        return redirect(url_for(".dashboard"))

    new_key = activation.generate_activation_key_for_user(machine_id, new_plan, ref=ref_date)
    users[admin_email].setdefault('activation', {})
    users[admin_email]["activation"].update({
        "plan": new_plan, "activation_date": ref_date.isoformat(), "activation_code": new_key
    })
    login_mod.save_users(users)
    flash(f"Plan pour {admin_email} mis à jour. Nouvelle clé : {new_key}", "success")
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
        return send_file(str(output_zip_path), as_attachment=True, download_name=output_zip_name)
    flash("Erreur lors de l'exportation du dossier MEDICALINK_DATA.", "danger")
    return redirect(url_for(".dashboard"))

@developpeur_bp.route("/data/medicalink/import", methods=["POST"])
def import_medicalink_data():
    if (r := _dev_only()): return r
    if 'medicalink_zip' not in request.files or not request.files['medicalink_zip'].filename.endswith('.zip'):
        return jsonify({"status": "error", "message": "Fichier ZIP invalide ou manquant."})

    uploaded_file = request.files['medicalink_zip']
    temp_zip_path = Path(utils.application_path) / "temp_medicalink_import.zip"
    medicalink_data_path = Path(utils.application_path) / "MEDICALINK_DATA"
    try:
        uploaded_file.save(str(temp_zip_path))
        if _unzip_directory(str(temp_zip_path), str(medicalink_data_path)):
            login_mod.load_users()
            return jsonify({"status": "success", "message": "Données importées. Veuillez redémarrer l'application."})
        return jsonify({"status": "error", "message": "Échec de la décompression du ZIP."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur lors de l'importation: {e}"})
    finally:
        if temp_zip_path.exists(): temp_zip_path.unlink()

@developpeur_bp.route('/trigger-backup', methods=['POST'])
def trigger_backup_dev():
    if (r := _dev_only()): return r
    firebase_manager = current_app.firebase_manager
    if not firebase_manager:
        flash("Service Firebase non configuré.", "danger")
        return redirect(url_for('developpeur_bp.dashboard'))
    
    try:
        current_machine_id = get_hardware_id()
    except Exception as e:
        flash(f"Impossible de récupérer l'ID de la machine locale : {e}", "danger")
        return redirect(url_for('developpeur_bp.dashboard'))

    local_data_path = str(Path(utils.application_path) / "MEDICALINK_DATA")
    
    flash(f"Lancement de la sauvegarde pour cette machine (ID: {current_machine_id})...", "info")
    
    success = firebase_manager.backup_directory(
        local_data_path,
        remote_folder="client_backups",
        machine_id=current_machine_id
    )

    if success:
        flash(f"Sauvegarde pour la machine {current_machine_id} réussie !", "success")
    else:
        flash("La sauvegarde a échoué. Vérifiez les logs.", "danger")
        
    return redirect(url_for('developpeur_bp.dashboard'))

@developpeur_bp.route('/restore-from-backup', methods=['POST'])
def restore_from_backup_dev():
    if (r := _dev_only()): return r
    firebase_manager = current_app.firebase_manager
    if not firebase_manager:
        flash("Service Firebase non configuré.", "danger")
        return redirect(url_for('developpeur_bp.dashboard'))

    machine_id_to_restore = request.form.get('machine_id_to_restore', '').strip()
    if not machine_id_to_restore:
        flash("Veuillez fournir un ID machine pour la restauration.", "danger")
        return redirect(url_for('developpeur_bp.dashboard'))

    local_data_path = str(Path(utils.application_path) / "MEDICALINK_DATA")
    
    flash(f"Lancement de la restauration pour la machine '{machine_id_to_restore}'...", "info")
    
    # --- SOLUTION FINALE : FERMETURE COMPLÈTE ---
    try:
        # 1. On arrête le planificateur de tâches en arrière-plan
        print("ℹ️ Arrêt du planificateur de tâches...")
        if current_app.scheduler.running:
            current_app.scheduler.shutdown()
        
        # 2. On ferme la session de la base de données
        print("ℹ️ Fermeture de la session de la base de données...")
        ia_db.session.remove()
        
        # 3. On ferme les connexions du moteur de la base de données
        print("ℹ️ Fermeture des connexions du moteur...")
        ia_db.engine.dispose()
        
    except Exception as e:
        print(f"🔥 Avertissement lors de l'arrêt des services : {e}")
    
    success = firebase_manager.restore_latest_backup(
        local_data_path, 
        remote_folder="client_backups",
        machine_id=machine_id_to_restore
    )

    if success:
        flash(f"Restauration réussie depuis la sauvegarde de '{machine_id_to_restore}'. Redémarrez l'application.", "success")
    else:
        flash(f"Restauration pour '{machine_id_to_restore}' échouée. Vérifiez l'ID et l'existence d'une sauvegarde.", "danger")
        
    return redirect(url_for('developpeur_bp.dashboard'))

@developpeur_bp.route('/firebase-browser')
def firebase_browser():
    if (r := _dev_only()): return r
    firebase_manager = current_app.firebase_manager
    if not firebase_manager:
        flash("Service Firebase non configuré.", "danger")
        return redirect(url_for('developpeur_bp.dashboard'))

    current_path = request.args.get('path', '')
    files, folders = firebase_manager.list_files(prefix=current_path)

    for f in files:
        f.download_url = firebase_manager.get_download_url(f.name)

    path_parts = []
    if current_path:
        parts = current_path.strip('/').split('/')
        for i, part in enumerate(parts):
            path_parts.append({
                'name': part,
                'path': '/'.join(parts[:i+1]) + '/'
            })

    return render_template_string(
        FIREBASE_BROWSER_HTML,
        files=files,
        folders=folders,
        current_path=current_path,
        path_parts=path_parts
    )
@developpeur_bp.route('/firebase-delete-blob', methods=['POST'])
def firebase_delete_blob():
    if (r := _dev_only()): return r
    blob_name = request.form.get('blob_name')
    if not blob_name:
        flash("Nom de fichier manquant.", "danger")
        return redirect(url_for('.firebase_browser'))
    
    parent_path = '/'.join(blob_name.split('/')[:-1])
    if parent_path: parent_path += '/'

    firebase_manager = current_app.firebase_manager
    if firebase_manager.delete_blob(blob_name):
        flash(f"Fichier '{blob_name}' supprimé.", "success")
    else:
        flash(f"Échec de la suppression du fichier '{blob_name}'.", "danger")
    
    return redirect(url_for('.firebase_browser', path=parent_path))

@developpeur_bp.route('/firebase-delete-folder', methods=['POST'])
def firebase_delete_folder():
    if (r := _dev_only()): return r
    folder_prefix = request.form.get('folder_prefix')
    if not folder_prefix:
        flash("Nom de dossier manquant.", "danger")
        return redirect(url_for('.firebase_browser'))

    parent_path = '/'.join(folder_prefix.strip('/').split('/')[:-1])
    if parent_path: parent_path += '/'

    firebase_manager = current_app.firebase_manager
    if firebase_manager.delete_folder(folder_prefix):
        flash(f"Dossier '{folder_prefix}' supprimé.", "success")
    else:
        flash(f"Échec de la suppression du dossier '{folder_prefix}'.", "danger")

    return redirect(url_for('.firebase_browser', path=parent_path))

@developpeur_bp.route('/firebase-upload-blob', methods=['POST'])
def firebase_upload_blob():
    if (r := _dev_only()): return r
    
    destination_path = request.form.get('path', '')
    if 'uploaded_file' not in request.files or not request.files['uploaded_file'].filename:
        flash("Aucun fichier sélectionné pour le téléversement.", "warning")
        return redirect(url_for('.firebase_browser', path=destination_path))

    file = request.files['uploaded_file']
    remote_blob_name = f"{destination_path}{file.filename}"

    firebase_manager = current_app.firebase_manager
    if firebase_manager.upload_file_to_storage(file.stream, remote_blob_name):
        flash(f"Fichier '{file.filename}' téléversé avec succès vers '{destination_path}'.", "success")
    else:
        flash(f"Échec du téléversement du fichier '{file.filename}'.", "danger")

    return redirect(url_for('.firebase_browser', path=destination_path))
    
# ───────── 5. Templates (HTML condensé) ─────────
LOGIN_HTML = """
<!doctype html><html lang='fr'>
<head><meta charset='utf-8'><title>Développeur | Connexion</title><meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no"><link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'><link href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css' rel='stylesheet'><style>:root{--grad1:#4b6cb7;--grad2:#182848;}body{background:linear-gradient(90deg,var(--grad1),var(--grad2));display:flex;align-items:center;justify-content:center;min-height:100vh;}.card{border-radius:1rem;overflow:hidden;}.card-header{background:linear-gradient(45deg,var(--grad1),var(--grad2));color:#fff;font-weight:600;text-align:center;padding:1.5rem 0;border-bottom:none;}.form-control:focus{border-color:var(--grad1);box-shadow:0 0 0 .25rem rgba(75,108,183,.25);}.btn-grad{background:linear-gradient(90deg,var(--grad1),var(--grad2));border:none;color:#fff;padding:.75rem 1.5rem;border-radius:.5rem;transition:all .3s ease;}.btn-grad:hover{transform:translateY(-2px);box-shadow:0 4px 8px rgba(0,0,0,.2);}.alert{border-radius:.5rem;}</style></head>
<body><div class='container'><div class='row justify-content-center'><div class='col-md-6 col-lg-5'><div class='card shadow-lg'><h3 class='card-header'><i class='fas fa-code me-2'></i>Mode Développeur</h3><div class='card-body p-4'>{% with m=get_flashed_messages(with_categories=true) %}{% if m %}{% for c,msg in m %}<div class='alert alert-{{c}} alert-dismissible fade show shadow-sm' role='alert'><i class='fas fa-info-circle me-2'></i>{{msg}}<button type='button' class='btn-close' data-bs-dismiss='alert'></button></div>{% endfor %}{% endif %}{% endwith %}<form method='POST'><div class='mb-3'><label for='emailInput' class='form-label fw-semibold'>Email</label><div class='input-group'><span class='input-group-text'><i class='fas fa-envelope'></i></span><input type='email' class='form-control' id='emailInput' name='email' required></div></div><div class='mb-4'><label for='passwordInput' class='form-label fw-semibold'>Mot de passe</label><div class='input-group'><span class='input-group-text'><i class='fas fa-lock'></i></span><input type='password' class='form-control' id='passwordInput' name='password' required></div></div><div class='d-grid'><button type='submit' class='btn btn-grad'><i class='fas fa-sign-in-alt me-2'></i>Se connecter</button></div></form></div></div></div></div></div><script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script></body></html>
"""

DASH_HTML = """
<!doctype html><html lang='fr'>
<head><meta charset='utf-8'><title>Développeur | Dashboard</title><meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no"><link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'><link href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css' rel='stylesheet'><link href='https://cdn.datatables.net/1.13.1/css/dataTables.bootstrap5.min.css' rel='stylesheet'><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>:root{--grad1:#4b6cb7;--grad2:#182848;}body{background:#f5f7fb;}.navbar{background:linear-gradient(90deg,var(--grad1),var(--grad2));}.card-header{background:linear-gradient(45deg,var(--grad1),var(--grad2));color:#fff;font-weight:600;}.section-icon{margin-right:.45rem;}.table thead{background:#e9ecef}.btn-grad{background:linear-gradient(90deg,var(--grad1),var(--grad2));border:none;color:#fff;}.no-pointer-events {pointer-events: none;}.mono{font-family: monospace; font-size: 0.9em; color: #E83E8C;}</style></head>
<body>
<nav class='navbar navbar-dark shadow'><div class='container-fluid'><span class='navbar-brand d-flex align-items-center gap-2'><i class='fas fa-code'></i> Mode Développeur <span class='fw-light'>EASYMEDICALINK</span></span><a href='{{ url_for("developpeur_bp.dev_logout") }}' class='btn btn-sm btn-outline-light rounded-pill'><i class='fas fa-sign-out-alt'></i> Quitter</a></div></nav>
<div class='container my-4'>
  {% with m=get_flashed_messages(with_categories=true) %}{% if m %}{% for c,msg in m %}<div class='alert alert-{{c}} alert-dismissible fade show shadow-sm' role='alert'><i class='fas fa-info-circle me-2'></i>{{msg}}<button type='button' class='btn-close' data-bs-dismiss='alert'></button></div>{% endfor %}{% endif %}{% endwith %}
  
  <div class='card shadow-sm mb-4'><h5 class='card-header'><i class='fas fa-key section-icon'></i>Générer une clé machine</h5><div class='card-body'><form class='row gy-2 gx-3 align-items-end' method='POST' action='{{ url_for("developpeur_bp.gen_custom") }}'><div class='col-12 col-md-3'><label class='form-label fw-semibold'><i class='fas fa-desktop me-1'></i>ID machine</label><input name='machine_id' class='form-control' placeholder='16 caractères' required></div><div class='col-12 col-md-2'><label class='form-label fw-semibold'><i class='fas fa-user me-1'></i>Nom</label><input name='nom' class='form-control' required></div><div class='col-12 col-md-2'><label class='form-label fw-semibold'><i class='fas fa-user me-1'></i>Prénom</label><input name='prenom' class='form-control' required></div><div class='col-12 col-md-3'><label class='form-label fw-semibold'><i class='fas fa-calendar-alt me-1'></i>Date d'activation</label><input name='activation_date' type='date' class='form-control' value='{{ today_date }}' required></div><div class='col-12 col-md-2'><label class='form-label fw-semibold'><i class='fas fa-file-signature me-1'></i>Plan</label><select name='plan' class='form-select'>{% for c,l in plans %}<option value='{{c}}'>{{l}}</option>{% endfor %}</select></div><div class='col-12 d-grid mt-3'><button class='btn btn-grad'><i class='fas fa-magic me-1'></i>Générer la Clé</button></div>{% if key %}<div class='col-12'><div class='alert alert-info mt-3 shadow-sm'><i class='fas fa-check-circle me-2'></i><strong>Clé&nbsp;:</strong> {{key}}</div></div>{% endif %}</form></div></div>
  <div class='card shadow-sm mb-4'><h5 class='card-header'><i class='fas fa-server section-icon'></i>Clés machines</h5><div class='card-body'><div class="table-responsive"><table id='tblKeys' class='table table-striped table-hover rounded overflow-hidden'><thead><tr><th>ID</th><th>Propriétaire</th><th>Plan</th><th>Clé</th></tr></thead><tbody>{% for mid,info in machines.items() %}<tr><td class='fw-semibold'>{{mid}}</td><td>{{info.prenom}}&nbsp;{{info.nom}}</td><td>{{info.plan}}</td><td class='text-break'>{{info.key}}</td></tr>{% endfor %}</tbody></table></div></div></div>
  <div class='card shadow-sm mb-4'><h5 class='card-header'><i class='fas fa-user-plus section-icon'></i>Créer un compte admin</h5><div class='card-body'><form class='row gy-2 gx-3 align-items-end' method='POST' action='{{ url_for("developpeur_bp.create_admin") }}'><div class='col-12 col-md-4'><label class='form-label fw-semibold'><i class='fas fa-envelope me-1'></i>Email</label><input name='email' type='email' class='form-control' required></div><div class='col-12 col-md-4'><label class='form-label fw-semibold'><i class='fas fa-key me-1'></i>Mot de passe</label><input name='password' type='password' class='form-control' required></div><div class='col-12 col-md-4'><label class='form-label fw-semibold'><i class='fas fa-key me-1'></i>Confirmer</label><input name='confirm' type='password' class='form-control' required></div><div class='col-12 col-md-4'><label class='form-label fw-semibold'><i class='fas fa-hospital me-1'></i>Clinique</label><input name='clinic' class='form-control' required></div><div class='col-12 col-md-4'><label class='form-label fw-semibold'><i class='fas fa-calendar-alt me-1'></i>Date création (Clinique)</label><input name='clinic_creation_date' type='date' class='form-control' required></div><div class='col-12 col-md-4'><label class='form-label fw-semibold'><i class='fas fa-map-marker-alt me-1'></i>Adresse</label><input name='address' class='form-control' required></div><div class='col-12 col-md-4'><label class='form-label fw-semibold'><i class='fas fa-phone me-1'></i>Téléphone</label><input name='phone' type='tel' class='form-control' placeholder='Numéro de téléphone' required></div><input type='hidden' name='role' value='admin'><div class='col-12 d-grid mt-2'><button class='btn btn-grad'><i class='fas fa-user-plus me-1'></i>Créer</button></div></form></div></div>
  <div class='card shadow-sm mb-4'><h5 class='card-header'><i class='fas fa-users section-icon'></i>Comptes admin</h5><div class='card-body'><div class="table-responsive"><table id='tblAdmin' class='table table-striped table-hover rounded overflow-hidden'><thead><tr><th>Email</th><th>Clinique</th><th>Téléphone</th><th>Adresse</th><th>Date création (Clinique)</th><th>Date création (Compte)</th><th>Plan</th><th>ID Machine</th><th>Actif</th><th>Actions</th></tr></thead><tbody>
            {% for e,u in admins.items() %}<tr><td>{{e}}</td><td>{{u.clinic}}</td><td>{{u.phone}}</td><td>{{u.address}}</td><td>{{u.clinic_creation_date}}</td><td>{{u.account_creation_date}}</td><td><span class="badge bg-primary">{{ u.get("activation", {}).get("plan", "N/A") }}</span></td><td class="mono">{{ u.get("machine_id", "N/A") }}</td><td><span class='badge {{'bg-success' if u.active else 'bg-secondary'}}'>{{'Oui' if u.active else 'Non'}}</span></td><td class='text-nowrap'>{% if u.phone %}<a class='btn btn-sm btn-success me-1' title='Contacter via WhatsApp' href='https://wa.me/{{ u.phone | replace("+", "") }}' target='_blank'><i class='fab fa-whatsapp'></i></a>{% endif %}<button class='btn btn-sm btn-info me-1 edit-admin-btn' title='Modifier' data-bs-toggle='modal' data-bs-target='#editAdminModal' data-email='{{ e }}' data-clinic='{{ u.clinic }}' data-clinic_creation_date='{{ u.clinic_creation_date }}' data-address='{{ u.address }}' data-phone='{{ u.phone }}' data-active='{{ u.get('active', False) | tojson }}'><i class='fas fa-pen'></i></button><button class='btn btn-sm btn-warning me-1 change-plan-btn' title='Modifier Plan' data-bs-toggle='modal' data-bs-target='#changePlanModal' data-email='{{ e }}' data-plan='{{ u.get("activation", {}).get("plan", "") }}' data-machine_id='{{ u.get("machine_id", "") }}'><i class='fas fa-file-invoice-dollar'></i></button><a class='btn btn-sm btn-outline-secondary' title='Activer/Désactiver' href='{{ url_for('developpeur_bp.toggle_active',admin_email=e) }}'><i class='fas fa-power-off'></i></a><a class='btn btn-sm btn-outline-danger' title='Supprimer' href='{{ url_for('developpeur_bp.delete_admin',admin_email=e) }}'><i class='fas fa-trash'></i></a></td></tr>{% endfor %}
          </tbody></table></div></div></div>

  <div class='card shadow-sm mb-4'><h5 class='card-header'><i class='fab fa-paypal section-icon'></i>Générer un Lien de Paiement</h5><div class='card-body'><form class='row gy-2 gx-3 align-items-end' method='POST' action='{{ url_for("developpeur_bp.generer_paiement") }}'><div class='col-12 col-md-4'><label class='form-label fw-semibold'><i class='fas fa-dollar-sign me-1'></i>Montant (USD)</label><input name='amount' type='number' step='0.01' class='form-control' placeholder='Ex: 25.50' required></div><div class='col-12 col-md-8'><label class='form-label fw-semibold'><i class='fas fa-info-circle me-1'></i>Description (pour le client)</label><input name='description' type='text' class='form-control' placeholder='Ex: Frais de configuration' required></div><div class='col-12 d-grid mt-3'><button class='btn btn-grad'><i class='fas fa-link me-1'></i>Générer le Lien de Paiement</button></div></form></div></div>
  
  {% if payment_link %}
  <div class='card shadow-sm mb-4'><h5 class='card-header' style='background: linear-gradient(45deg, #28a745, #20c997); color: white;'><i class='fas fa-check-circle section-icon'></i>Lien de Paiement Prêt</h5><div class='card-body text-center'><p>Le lien de paiement pour <strong>{{ payment_amount }} USD</strong> ({{ payment_description }}) a été généré.</p><div class='my-3'><img src="data:image/png;base64,{{ qr_code_base64 }}" alt="QR Code de Paiement" class="img-fluid" style="max-width: 200px; border: 1px solid #ddd; padding: 5px; border-radius: 10px;"></div><div class='input-group mb-3'><input type='text' class='form-control' value='{{ payment_link }}' id='paymentLinkInput' readonly><button class='btn btn-outline-secondary' type='button' onclick='copyLink()'><i class='fas fa-copy'></i> Copier</button></div><a href="{{ payment_link }}" target="_blank" class="btn btn-success"><i class="fab fa-paypal me-2"></i>Ouvrir le lien de paiement</a></div></div>
  {% endif %}

  <div class='card shadow-sm mt-4'><h5 class='card-header'><i class='fas fa-database section-icon'></i>Gestion des Données et Sauvegardes</h5><div class='card-body'><div class="d-flex justify-content-center gap-3 flex-wrap"><a href="{{ url_for('developpeur_bp.export_medicalink_data') }}" class="btn btn-success"><i class="fas fa-file-archive me-2"></i>Exporter Données Locales</a><form action="{{ url_for('developpeur_bp.trigger_backup_dev') }}" method="POST" onsubmit="return confirm('Ceci va sauvegarder les données de CETTE machine (serveur) dans un dossier cloud portant son propre ID. Continuer ?');"><button type="submit" class="btn btn-warning"><i class="fas fa-cloud-upload-alt me-2"></i>Forcer Sauvegarde (Cette Machine)</button></form><a href="{{ url_for('developpeur_bp.firebase_browser') }}" class="btn btn-primary"><i class="fab fa-google me-2"></i>Gérer Espace Cloud</a></div></div></div>
  <div class='card shadow-sm mt-4'><h5 class='card-header'><i class='fas fa-cloud-download-alt section-icon'></i>Restauration des Données Cloud</h5><div class='card-body text-center'><p class='text-muted'>Pour restaurer, entrez l'ID machine du client. Ceci remplacera **toutes** les données locales par la dernière sauvegarde trouvée pour cet ID dans le dossier <strong>client_backups</strong>. À utiliser avec une extrême prudence.</p><form action="{{ url_for('developpeur_bp.restore_from_backup_dev') }}" method="POST" onsubmit="return confirm('ATTENTION : Êtes-vous certain de vouloir restaurer les données pour la machine spécifiée ? Toutes les données locales actuelles seront définitivement écrasées !');"><div class="input-group mb-3 mx-auto" style="max-width: 400px;"><span class="input-group-text"><i class="fas fa-desktop"></i></span><input type="text" name="machine_id_to_restore" class="form-control" placeholder="Entrez l'ID machine du client" required></div><button type="submit" class="btn btn-danger"><i class="fas fa-exclamation-triangle me-2"></i>Lancer la Restauration</button></form></div></div>
</div>

<div class="modal fade" id="editAdminModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Modifier le compte Admin</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form id="editAdminForm" method="POST" action=""><div class="modal-body"><input type="hidden" name="original_email" id="edit_original_email"><div class="mb-3"><label class="form-label">Email</label><input type="email" class="form-control" id="edit_email" name="email" required></div><div class="mb-3"><label class="form-label">Nom de la clinique</label><input type="text" class="form-control" id="edit_clinic" name="clinic" required></div><div class="mb-3"><label class="form-label">Date de création (Clinique)</label><input type="date" class="form-control" id="edit_clinic_creation_date" name="clinic_creation_date" required></div><div class="mb-3"><label class="form-label">Adresse</label><input type="text" class="form-control" id="edit_address" name="address" required></div><div class="mb-3"><label class="form-label">Téléphone</label><input type="tel" class="form-control" id="edit_phone" name="phone" placeholder='Numéro de téléphone' required></div><div class="mb-3"><label class="form-label">Nouveau mot de passe (laisser vide si inchangé)</label><input type="password" class="form-control" id="edit_password" name="password"></div><div class="mb-3"><label class="form-label">Confirmer le nouveau mot de passe</label><input type="password" class="form-control" id="edit_confirm_password" name="confirm_password"></div><div class="form-check"><input class="form-check-input" type="checkbox" id="edit_active" name="active"><label class="form-check-label" for="edit_active">Actif</label></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button><button type="submit" class="btn btn-primary">Enregistrer</button></div></form></div></div></div>
<div class="modal fade" id="changePlanModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Modifier Plan de Licence</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form method="POST" action="{{ url_for('developpeur_bp.change_admin_plan') }}"><div class="modal-body"><input type="hidden" name="admin_email" id="plan_admin_email"><p>Compte : <strong id="plan_admin_email_display"></strong></p><div class="mb-3"><label class="form-label">ID Machine Client</label><input type="text" class="form-control mono" id="plan_machine_id" name="machine_id" required minlength="16" maxlength="16" placeholder="ID auto-collecté"><div class="form-text">Cet ID est normalement collecté à la connexion du client.</div></div><div class="mb-3"><label class="form-label">Nouveau Plan</label><select name="plan" id="plan_select" class="form-select">{% for value, label in plans %}<option value="{{ value }}">{{ label }}</option>{% endfor %}</select></div><div class="mb-3"><label class="form-label">Date d'activation</label><input type="date" class="form-control" id="plan_activation_date" name="activation_date" required></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button><button type="submit" class="btn btn-primary">Mettre à jour</button></div></form></div></div></div>
<script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script><script src='https://code.jquery.com/jquery-3.6.0.min.js'></script><script src='https://cdn.datatables.net/1.13.1/js/jquery.dataTables.min.js'></script><script src='https://cdn.datatables.net/1.13.1/js/dataTables.bootstrap5.min.js'></script>
<script>
function copyLink() {
  var copyText = document.getElementById("paymentLinkInput");
  copyText.select();
  copyText.setSelectionRange(0, 99999);
  document.execCommand("copy");
  Swal.fire({icon:'success',title:'Copié !',text:'Le lien a été copié dans le presse-papiers.',timer:1500,showConfirmButton:false});
}
$(function(){
  $('#tblKeys, #tblAdmin').DataTable({lengthChange:false,language:{url:'//cdn.datatables.net/plug-ins/1.13.1/i18n/fr-FR.json'}});
  $('#editAdminModal').on('show.bs.modal',function(e){const t=$(e.relatedTarget),a=t.data("email"),l=t.data("clinic"),i=t.data("clinic_creation_date"),d=t.data("address"),n=t.data("phone"),s=t.data("active"),o=$(this);o.find("#edit_original_email").val(a),o.find("#edit_email").val(a),o.find("#edit_clinic").val(l),o.find("#edit_clinic_creation_date").val(i),o.find("#edit_address").val(d),o.find("#edit_phone").val(n),o.find("#edit_active").prop("checked",s),o.find("#editAdminForm").attr("action","{{ url_for('developpeur_bp.edit_admin') }}")});
  $('#editAdminForm').on('submit',function(e){e.preventDefault();const t=$(this),a=t.serialize(),l=$("#edit_password").val(),i=$("#edit_confirm_password").val();if(l&&l!==i)return void Swal.fire({icon:"error",title:"Erreur",text:"Les mots de passe ne correspondent pas."});fetch(t.attr("action"),{method:"POST",body:new URLSearchParams(a),headers:{"Content-Type":"application/x-www-form-urlencoded"}}).then(e=>e.json()).then(e=>{"success"===e.status?Swal.fire({icon:"success",title:"Succès",text:e.message}).then(()=>{location.reload()}):Swal.fire({icon:"error",title:"Erreur",text:e.message})}).catch(e=>{console.error("Error:",e),Swal.fire({icon:"error",title:"Erreur réseau",text:"Impossible de se connecter."})})});
  $('#changePlanModal').on('show.bs.modal',function(e){const t=$(e.relatedTarget),a=$(this),l=t.data("email"),i=t.data("machine_id"),d=(new Date).toISOString().split("T")[0];a.find("#plan_admin_email").val(l),a.find("#plan_admin_email_display").text(l),a.find("#plan_select").val(t.data("plan")),a.find("#plan_machine_id").val(i),a.find("#plan_activation_date").val(d),i||a.find("#plan_machine_id").attr("placeholder","Le client doit se connecter...")});
});
</script></body></html>
"""

FIREBASE_BROWSER_HTML = """
<!doctype html><html lang='fr'>
<head><meta charset='utf-8'><title>Gestionnaire Cloud</title><meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no"><link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'><link href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css' rel='stylesheet'><style>:root{--grad1:#4b6cb7;--grad2:#182848;}body{background:#f5f7fb;}.navbar{background:linear-gradient(90deg,var(--grad1),var(--grad2));}.breadcrumb-item a{text-decoration:none;}</style></head>
<body>
<nav class='navbar navbar-dark shadow-sm'><div class='container-fluid'><span class='navbar-brand d-flex align-items-center gap-2'><i class='fab fa-google'></i> Gestionnaire de Fichiers Firebase</span><a href='{{ url_for("developpeur_bp.dashboard") }}' class='btn btn-sm btn-outline-light rounded-pill'><i class='fas fa-arrow-left'></i> Retour Dashboard</a></div></nav>
<div class='container my-4'>
    {% with m=get_flashed_messages(with_categories=true) %}{% if m %}{% for c,msg in m %}<div class='alert alert-{{c}} alert-dismissible fade show' role='alert'>{{msg}}<button type='button' class='btn-close' data-bs-dismiss='alert'></button></div>{% endfor %}{% endif %}{% endwith %}
    <div class='card shadow-sm'>
        <div class='card-header'><nav aria-label="breadcrumb"><ol class="breadcrumb mb-0 py-1"><li class="breadcrumb-item"><a href="{{ url_for('.firebase_browser') }}"><i class="fas fa-home"></i></a></li>{% for part in path_parts %}<li class="breadcrumb-item"><a href="{{ url_for('.firebase_browser', path=part.path) }}">{{ part.name }}</a></li>{% endfor %}</ol></nav></div>
        <div class='card-body'><table class='table table-hover align-middle'><thead><tr><th>Nom</th><th>Taille</th><th>Modifié le</th><th class="text-end">Actions</th></tr></thead>
                <tbody>
                {% for folder in folders %}<tr><td><a href="{{ url_for('.firebase_browser', path=folder) }}" class="text-decoration-none text-dark fw-bold"><i class="fas fa-folder text-warning me-2"></i>{{ folder.replace(current_path, '').strip('/') }}</a></td><td>--</td><td>--</td><td class="text-end"><form class="d-inline" action="{{ url_for('.firebase_delete_folder') }}" method="POST" onsubmit="return confirm('Voulez-vous vraiment supprimer ce dossier et tout son contenu ?');"><input type="hidden" name="folder_prefix" value="{{ folder }}"><button type="submit" class="btn btn-sm btn-outline-danger" title="Supprimer le dossier"><i class="fas fa-trash"></i></button></form></td></tr>{% endfor %}
                {% for file in files %}<tr><td><i class="fas fa-file-archive text-secondary me-2"></i>{{ file.name.replace(current_path, '') }}</td><td>{{ "%.2f"|format(file.size / (1024*1024)) }} MB</td><td>{{ file.updated.strftime('%Y-%m-%d %H:%M') }}</td><td class="text-end"><a href="{{ file.download_url }}" class="btn btn-sm btn-outline-success" title="Télécharger le fichier"><i class="fas fa-download"></i></a><form class="d-inline" action="{{ url_for('.firebase_delete_blob') }}" method="POST" onsubmit="return confirm('Voulez-vous vraiment supprimer ce fichier ?');"><input type="hidden" name="blob_name" value="{{ file.name }}"><button type="submit" class="btn btn-sm btn-outline-danger" title="Supprimer le fichier"><i class="fas fa-trash"></i></button></form></td></tr>{% endfor %}
                {% if not folders and not files %}<tr><td colspan="4" class="text-center text-muted">Ce dossier est vide.</td></tr>{% endif %}
                </tbody></table></div>
        <div class="card-footer"><form action="{{ url_for('.firebase_upload_blob') }}" method="POST" enctype="multipart/form-data"><input type="hidden" name="path" value="{{ current_path }}"><div class="input-group"><input type="file" class="form-control" name="uploaded_file" required><button class="btn btn-primary" type="submit"><i class="fas fa-upload me-2"></i>Téléverser vers ce dossier</button></div></form></div>
    </div></div>
<script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
</body></html>
"""

PAYMENT_SUCCESS_HTML = """
<!DOCTYPE html><html lang='fr'>
<head><meta charset='UTF-8'><title>Paiement Réussi</title><link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'><link href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css' rel='stylesheet'><style>body{background-color:#f0f9f5; display: flex; align-items: center; justify-content: center; height: 100vh;}.card{border: 2px solid #198754; border-radius: 1rem;}</style></head>
<body><div class='container'><div class='row justify-content-center'><div class='col-md-6'><div class='card shadow-lg text-center p-4'>
<h1 class='text-success'><i class='fas fa-check-circle fa-3x'></i></h1><h2 class='mt-3'>Paiement Réussi !</h2>
<p class='lead'>Merci pour votre paiement de <strong>{{ details.amount }} USD</strong> pour <em>"{{ details.description }}"</em>.</p>
<p class='text-muted'>Votre transaction a été complétée avec succès. Vous pouvez fermer cette page.</p>
</div></div></div></div></body></html>
"""

PAYMENT_CANCEL_HTML = """
<!DOCTYPE html><html lang='fr'>
<head><meta charset='UTF-8'><title>Paiement Annulé</title><link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'><link href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css' rel='stylesheet'><style>body{background-color:#fff8f5; display: flex; align-items: center; justify-content: center; height: 100vh;}.card{border: 2px solid #ffc107; border-radius: 1rem;}</style></head>
<body><div class='container'><div class='row justify-content-center'><div class='col-md-6'><div class='card shadow-lg text-center p-4'>
<h1 class='text-warning'><i class='fas fa-exclamation-triangle fa-3x'></i></h1><h2 class='mt-3'>Paiement Annulé</h2>
<p class='lead'>La transaction a été annulée.</p>
<p class='text-muted'>Aucun paiement n'a été effectué. Vous pouvez fermer cette page ou essayer à nouveau.</p>
</div></div></div></div></body></html>
"""

PAYMENT_FAIL_HTML = """
<!DOCTYPE html><html lang='fr'>
<head><meta charset='UTF-8'><title>Échec du Paiement</title><link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'><link href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css' rel='stylesheet'><style>body{background-color:#fbeff0; display: flex; align-items: center; justify-content: center; height: 100vh;}.card{border: 2px solid #dc3545; border-radius: 1rem;}</style></head>
<body><div class='container'><div class='row justify-content-center'><div class='col-md-6'><div class='card shadow-lg text-center p-4'>
<h1 class='text-danger'><i class='fas fa-times-circle fa-3x'></i></h1><h2 class='mt-3'>Échec du Paiement</h2>
<p class='lead'>Nous n'avons pas pu valider votre paiement.</p>
<p class='text-muted'>Veuillez contacter le support si le problème persiste.</p>
</div></div></div></div></body></html>
"""