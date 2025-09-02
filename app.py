# app.py (VERSION COMPLÈTE ET REVUE)
import os
from datetime import datetime, timedelta
import webbrowser
import json

# --- 1. CHARGEMENT DE LA CONFIGURATION EXTERNE ---
try:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'email.json')
    with open(config_path, 'r') as f:
        secrets = json.load(f)
        for key, value in secrets.items():
            os.environ[key] = value
    print("✅ Clés chargées avec succès depuis email.json")
except FileNotFoundError:
    print("🔥 ATTENTION: Fichier email.json non trouvé.")
except Exception as e:
    print(f"🔥 ERREUR lors de la lecture de email.json: {e}")

# --- 2. IMPORTS DES MODULES DE L'APPLICATION ---
from flask import Flask, session, redirect, url_for, request, flash
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler
from ia_assitant import ia_assitant_bp, db as ia_db
from firebase import FirebaseManager
import activation, theme, utils, pwa, login, accueil, administrateur, rdv, facturation, statistique, developpeur, routes, patient_rdv, biologie, radiologie, pharmacie, comptabilite, gestion_patient, guide

mail = Mail()

# --- 3. CRÉATION DE L'APPLICATION FLASK ---
def create_app():
    instance_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MEDICALINK_DATA', 'instance')
    app = Flask(__name__, instance_path=instance_folder_path, static_folder='static', static_url_path='/static', template_folder='templates')
    
    app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key")
    app.permanent_session_lifetime = timedelta(days=7)

    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url or f"sqlite:///{os.path.join(app.instance_path, 'medical_assistant.db')}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    
    ia_db.init_app(app)
    mail.init_app(app)
    theme.init_theme(app)

    @app.context_processor
    def inject_theme_names(): return {"theme_names": list(theme.THEMES.keys())}

    @app.context_processor
    def inject_config_values():
        cfg = utils.load_config()
        return {
            'app_name': cfg.get('app_name', 'EasyMedicalink'),
            'theme': cfg.get('theme', 'clair'),
            'logo_path': cfg.get('logo_path', '/static/pwa/icon-512.png'),
            'background_file_path': cfg.get('background_file_path', '')
        }

    for bp in [pwa.pwa_bp, guide.guide_bp, login.login_bp, accueil.accueil_bp, administrateur.administrateur_bp, developpeur.developpeur_bp, facturation.facturation_bp, patient_rdv.patient_rdv_bp, biologie.biologie_bp, radiologie.radiologie_bp, pharmacie.pharmacie_bp, comptabilite.comptabilite_bp, ia_assitant_bp]:
        app.register_blueprint(bp)
    for bp, prefix in [(rdv.rdv_bp, "/rdv"), (statistique.statistique_bp, "/statistique"), (activation.activation_bp, "/activation"), (gestion_patient.gestion_patient_bp, '/gestion_patient')]:
        app.register_blueprint(bp, url_prefix=prefix)

    @app.route("/", methods=["GET"])
    def root():
        return redirect(url_for("login.login")) if "email" not in session else redirect(url_for("accueil.accueil"))

    # --- GESTIONNAIRE DE REQUÊTES GLOBAL ---
    @app.before_request
    def central_request_guard():
        # --- MODIFICATION ---
        # Si la requête est pour le blueprint développeur, on ignore TOUTES les vérifications.
        if request.blueprint == 'developpeur_bp':
            return
        
        if request.path.startswith(('/static/', '/icon/')) or request.path in ['/sw.js', '/manifest.webmanifest', '/service-worker.js', '/offline']:
            return

        public_endpoints = [
            'login.login', 'login.register', 'login.complete_registration',
            'login.forgot_password', 'login.reset_password', 'activation.activation',
            'activation.paypal_success', 'activation.paypal_cancel'
        ]
        
        if request.endpoint in public_endpoints:
            return

        if "email" not in session or "admin_email" not in session:
            flash("Veuillez vous connecter pour accéder à cette page.", "warning")
            return redirect(url_for("login.login"))

        utils.set_dynamic_base_dir(session['admin_email'])
        
        current_user = activation._user()
        if not current_user or not current_user.get("active", True):
            session.clear()
            flash("Votre compte a été désactivé ou n'existe plus.", "warning")
            return redirect(url_for("login.login"))
            
        if not activation.check_activation():
            flash("Votre licence est invalide ou a expiré. Veuillez activer le produit.", "warning")
            return redirect(url_for("activation.activation"))
    
    routes.register_routes(app)
    with app.app_context(): ia_db.create_all()
    print("✅ Application Flask démarrée et Blueprints enregistrés.")
    return app

# --- 4. INITIALISATION ET EXÉCUTION ---
app = create_app()

# Configuration de Firebase (inchangé)
credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'firebase_credentials.json')
project_id = ""
if os.path.exists(credentials_path):
    with open(credentials_path, 'r') as f:
        creds = json.load(f)
        project_id = creds.get('project_id')

firebase_manager = None
if project_id:
    firebase_manager = FirebaseManager(credentials_path, project_id)
else:
    print("🔥 ATTENTION: ID de projet Firebase non trouvé. Le module Firebase est désactivé.")
app.firebase_manager = firebase_manager

# Tâche de sauvegarde planifiée (inchangé)
def daily_backup_task():
    print(f"🚀 [BACKUP] Démarrage de la sauvegarde à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    data_root_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MEDICALINK_DATA")
    if firebase_manager and os.path.exists(data_root_path):
        if firebase_manager.backup_directory(data_root_path, remote_folder="daily_backups"):
            print("✅ [BACKUP] Sauvegarde terminée avec succès.")
        else:
            print("🔥 [BACKUP] La sauvegarde a échoué.")
    else:
        print("ℹ️ [BACKUP] Sauvegarde annulée (Firebase non initialisé ou dossier de données manquant).")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(daily_backup_task, 'cron', hour='0,12', minute=0)
scheduler.start()
print("🗓️ Tâche de sauvegarde quotidienne planifiée.")

# Lancement du serveur de développement
if __name__ == '__main__':
    # Ouvre le navigateur uniquement lors du premier lancement, pas lors des redémarrages.
    if os.environ.get("WERKZEUG_RUN_MAIN") is None:
        try:
            webbrowser.open("http://127.0.0.1:3000/login")
        except Exception as e:
            print(f"Impossible d'ouvrir le navigateur web : {e}")
            
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)), debug=True)