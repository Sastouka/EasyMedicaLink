# app.py (VERSION CORRIGÉE)
import os
import sys
from datetime import datetime, timedelta
import webbrowser
import json

# --- CHARGEMENT DES CLÉS DEPUIS email.json ---
try:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'email.json')
    with open(config_path, 'r') as f:
        secrets = json.load(f)
        for key, value in secrets.items():
            os.environ[key] = value
    print("✅ Clés chargées avec succès depuis email.json")
except FileNotFoundError:
    print("🔥 ATTENTION: Fichier email.json non trouvé. L'application pourrait ne pas fonctionner correctement.")
except Exception as e:
    print(f"🔥 ERREUR lors de la lecture de email.json: {e}")
# ------------------------------------------------

from ia_assitant import ia_assitant_bp, db as ia_db
from flask import Flask, session, redirect, url_for, request, render_template_string, flash
from flask_mail import Mail
from firebase import FirebaseManager
from apscheduler.schedulers.background import BackgroundScheduler
import activation # Importer activation pour utiliser ses fonctions

mail = Mail()

# ───────────── 1. Création de l’application
def create_app():
    instance_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MEDICALINK_DATA', 'instance')
    
    app = Flask(
        __name__,
        instance_path=instance_folder_path,
        static_folder='static',
        static_url_path='/static',
        template_folder='templates'
    )
    
    app.secret_key = os.environ.get("SECRET_KEY")
    app.permanent_session_lifetime = timedelta(days=7)
    
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        # Correction pour la compatibilité avec SQLAlchemy
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # Utilise la base de données PostgreSQL si disponible (sur Render), sinon SQLite (en local)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///medical_assistant.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    
    ia_db.init_app(app)
    mail.init_app(app)
    
    import theme
    theme.init_theme(app)

    @app.context_processor
    def inject_theme_names():
        return {"theme_names": list(theme.THEMES.keys())}

    import utils

    @app.context_processor
    def inject_config_values():
        cfg = utils.load_config()
        return {
            'app_name':             cfg.get('app_name', 'EasyMedicalink'),
            'theme':                cfg.get('theme', 'clair'),
            'logo_path':            cfg.get('logo_path', '/static/pwa/icon-512.png'),
            'background_file_path': cfg.get('background_file_path', '')
        }

    import pwa
    import login
    import accueil
    import administrateur
    import rdv
    import facturation
    import statistique
    import developpeur
    import routes 
    import patient_rdv
    import biologie
    import radiologie
    import pharmacie
    import comptabilite
    import gestion_patient
    import guide

    app.register_blueprint(pwa.pwa_bp)
    app.register_blueprint(guide.guide_bp)
    app.register_blueprint(login.login_bp)
    app.register_blueprint(accueil.accueil_bp)
    app.register_blueprint(administrateur.administrateur_bp)
    app.register_blueprint(developpeur.developpeur_bp)
    app.register_blueprint(rdv.rdv_bp, url_prefix="/rdv")
    app.register_blueprint(facturation.facturation_bp)
    app.register_blueprint(statistique.statistique_bp, url_prefix="/statistique")
    app.register_blueprint(activation.activation_bp, url_prefix="/activation") # Ajout d'un préfixe pour la clarté
    app.register_blueprint(patient_rdv.patient_rdv_bp)
    app.register_blueprint(biologie.biologie_bp)
    app.register_blueprint(radiologie.radiologie_bp)
    app.register_blueprint(pharmacie.pharmacie_bp)
    app.register_blueprint(comptabilite.comptabilite_bp)
    app.register_blueprint(gestion_patient.gestion_patient_bp, url_prefix='/gestion_patient')
    app.register_blueprint(ia_assitant_bp) 

    @app.route("/", methods=["GET"])
    def root():
        return redirect(url_for("login.login")) if "email" not in session else redirect(url_for("accueil.accueil"))

    # --- DÉBUT DE LA SECTION CORRIGÉE ---
    # Nouvelle fonction de vérification centralisée
    @app.before_request
    def central_request_guard():
        # Définir le chemin de base en premier
        login._set_login_paths()

        # Liste des pages qui sont TOUJOURS publiques, que l'utilisateur soit connecté ou non.
        public_endpoints = [
            'static',
            'login.login',
            'login.register',
            'login.complete_registration', # <-- ESSENTIEL
            'login.forgot_password',     # <-- ESSENTIEL
            'login.reset_password',        # <-- ESSENTIEL
            'activation.activation',
            'activation.paypal_success',
            'activation.paypal_cancel',
            'developpeur.home' # Exemple, ajoutez d'autres routes de 'developpeur' si nécessaire
        ]
        
        # Si la requête concerne un fichier statique ou une page PWA, on ne fait rien.
        if request.path.startswith(('/static/', '/icon/')) or request.path in [
            '/sw.js', '/manifest.webmanifest', '/service-worker.js', '/offline'
        ]:
            return
        
        # Si la page demandée est dans notre liste publique, on autorise l'accès.
        if request.endpoint in public_endpoints:
            return

        # --- À partir d'ici, toutes les autres routes nécessitent une connexion ---

        # 1. Vérifier si l'utilisateur est connecté
        if "email" not in session:
            flash("Veuillez vous connecter pour accéder à cette page.", "warning")
            return redirect(url_for("login.login"))

        # 2. Définir le répertoire de données pour l'utilisateur connecté
        utils.set_dynamic_base_dir(session['admin_email'])
        
        # 3. Vérifier si le compte est actif (active: true dans users.json)
        current_user = activation._user()
        if not current_user or not current_user.get("active", True):
            session.clear()
            flash("Votre compte a été désactivé ou n'existe plus.", "warning")
            return redirect(url_for("login.login"))
            
        # 4. Vérifier si la licence est valide
        if not activation.check_activation():
            flash("Votre licence est invalide ou a expiré. Veuillez activer le produit.", "warning")
            return redirect(url_for("activation.activation"))
    
    # --- FIN DE LA SECTION CORRIGÉE ---

    routes.register_routes(app)

    with app.app_context():
        # (le reste de la configuration PWA est inchangé)
        ia_db.create_all()

    print("Application Flask démarrée et Blueprints enregistrés.")
    return app

# ───────────── Initialisation de l'application pour Gunicorn
app = create_app()

# ... (le reste du fichier pour Firebase, Scheduler et le lancement local est inchangé) ...
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
    print("🔥 ATTENTION: ID de projet Firebase non trouvé ou fichier de crédentials manquant. Le module Firebase est désactivé.")

app.firebase_manager = firebase_manager

def daily_backup_task():
    print(f"🚀 [BACKUP] Démarrage de la tâche de sauvegarde quotidienne à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    data_root_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MEDICALINK_DATA")
    if firebase_manager and os.path.exists(data_root_path):
        success = firebase_manager.backup_directory(data_root_path, remote_folder="daily_backups")
        if success:
            print("✅ [BACKUP] Tâche de sauvegarde quotidienne terminée avec succès.")
        else:
            print("🔥 [BACKUP] La tâche de sauvegarde quotidienne a échoué.")
    else:
        print("ℹ️ [BACKUP] Le gestionnaire Firebase n'est pas initialisé ou le dossier MEDICALINK_DATA n'existe pas. Sauvegarde annulée.")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(daily_backup_task, 'cron', hour='0,12', minute=0)
scheduler.start()
print("🗓️ Tâche de sauvegarde quotidienne planifiée pour s'exécuter tous les jours à minuit.")

if __name__ == '__main__':
    if os.environ.get("WERKZEUG_RUN_MAIN") is None:
        try:
            if os.environ.get("FLASK_ENV") != "production" and not os.environ.get("REPL_SLUG"):
                webbrowser.open("http://127.0.0.1:3000/login")
        except Exception as e:
            print(f"Impossible d'ouvrir le navigateur web : {e}")
            
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)), debug=True)