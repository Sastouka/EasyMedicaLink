# app.py (VERSION CORRIGÉE AVEC ACCÈS RESET PASSWORD)
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
    print("🔥 ATTENTION: Fichier email.json non trouvé. (Mode dev sans email)")
except Exception as e:
    print(f"🔥 ERREUR lors de la lecture de email.json: {e}")

# --- 2. IMPORTS DES MODULES DE L'APPLICATION ---
from flask import Flask, session, redirect, url_for, request, flash
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler

# Import de tous les Blueprints de l'application
from ia_assitant import ia_assitant_bp
from ia_assistant_synapse import ia_assistant_synapse_bp
import activation, theme, utils, pwa, login, accueil, administrateur, rdv, facturation, statistique, developpeur, routes, patient_rdv, biologie, radiologie, pharmacie, comptabilite, gestion_patient, guide
from firebase import FirebaseManager

mail = Mail()

# --- 3. CRÉATION DE L'APPLICATION FLASK (APPLICATION FACTORY) ---
def create_app():
    instance_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MEDICALINK_DATA', 'instance')
    app = Flask(__name__, instance_path=instance_folder_path, static_folder='static', static_url_path='/static', template_folder='templates')
    
    # Configuration générale de l'application
    app.secret_key = os.environ.get("SECRET_KEY", "une_cle_secrete_par_defaut_pour_le_dev")
    app.permanent_session_lifetime = timedelta(days=7)

    # Configuration de l'envoi d'emails (Flask-Mail)
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    
    # Initialisation des extensions Flask
    mail.init_app(app)
    theme.init_theme(app)

    # Processeurs de contexte pour injecter des variables dans tous les templates
    @app.context_processor
    def inject_theme_names():
        return {"theme_names": list(theme.THEMES.keys())}

    @app.context_processor
    def inject_config_values():
        cfg = utils.load_config() if utils.CONFIG_FILE else {}
        return {
            'app_name': cfg.get('app_name', 'EasyMedicalink'),
            'theme': cfg.get('theme', 'clair'),
            'logo_path': cfg.get('logo_path', '/static/pwa/icon-512.png'),
            'background_file_path': cfg.get('background_file_path', '')
        }

    # Enregistrement des Blueprints
    blueprints_to_register = [
        # Blueprints sans préfixe d'URL
        (pwa.pwa_bp, None), (guide.guide_bp, None), (login.login_bp, None),
        (accueil.accueil_bp, None), (administrateur.administrateur_bp, None),
        (developpeur.developpeur_bp, None), (facturation.facturation_bp, None),
        (patient_rdv.patient_rdv_bp, None), (biologie.biologie_bp, None),
        (radiologie.radiologie_bp, None), (pharmacie.pharmacie_bp, None),
        (comptabilite.comptabilite_bp, None), (ia_assitant_bp, None),
        (ia_assistant_synapse_bp, None),

        # Blueprints avec préfixe d'URL
        (rdv.rdv_bp, "/rdv"),
        (statistique.statistique_bp, "/statistique"),
        (activation.activation_bp, "/activation"),
        (gestion_patient.gestion_patient_bp, '/gestion_patient')
    ]

    for bp, url_prefix in blueprints_to_register:
        app.register_blueprint(bp, url_prefix=url_prefix)
    print("✅ Blueprints enregistrés.")
    
    # Route racine
    @app.route("/", methods=["GET"])
    def root():
        if "email" in session:
            return redirect(url_for("accueil.accueil"))
        return redirect(url_for("login.login"))

    # Gardien de sécurité global s'exécutant avant chaque requête
    @app.before_request
    def central_request_guard():
        # Accès public pour les assets statiques et le service worker
        if request.path.startswith(('/static/', '/icon/')) or request.path in ['/sw.js', '/manifest.webmanifest', '/service-worker.js', '/offline']:
            return

        # Accès public pour les blueprints ne nécessitant pas de connexion
        if request.blueprint in ['developpeur_bp', 'ia_assistant_synapse']:
            return
        
        # Accès public pour des pages spécifiques (connexion, inscription, RESET PASSWORD)
        public_endpoints = [
            'login.login', 'login.register', 'login.complete_registration',
            'login.forgot_password', 
            'login.reset_password_token',  # <--- CORRECTION ICI (C'était login.reset_password avant)
            'activation.activation',
            'activation.paypal_success', 'activation.paypal_cancel'
        ]
        if request.endpoint in public_endpoints:
            return

        # Si aucune des conditions ci-dessus n'est remplie, l'utilisateur doit être connecté
        if "email" not in session or "admin_email" not in session:
            flash("Veuillez vous connecter pour accéder à cette page.", "warning")
            return redirect(url_for("login.login"))

        # Vérifications de la validité du compte et de la licence
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
    
    print("✅ Application Flask démarrée.")
    return app

# --- 4. INITIALISATION ET EXÉCUTION ---
app = create_app()

# Configuration de Firebase pour les sauvegardes
credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'firebase_credentials.json')
project_id = ""
if os.path.exists(credentials_path):
    try:
        with open(credentials_path, 'r') as f:
            project_id = json.load(f).get('project_id', '')
    except:
        pass

app.firebase_manager = FirebaseManager(credentials_path, project_id) if project_id else None
if app.firebase_manager:
    print("✅ Connexion à Firebase Storage réussie.")
else:
     print("ℹ️ ID de projet Firebase non trouvé (Sauvegardes locales uniquement).")

# Tâche de sauvegarde planifiée
def daily_backup_task():
    print(f"🚀 [BACKUP] Démarrage de la sauvegarde à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    data_root_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MEDICALINK_DATA")
    if app.firebase_manager and os.path.exists(data_root_path):
        if app.firebase_manager.backup_directory(data_root_path, remote_folder="daily_backups"):
            print("✅ [BACKUP] Sauvegarde terminée avec succès.")
        else:
            print("🔥 [BACKUP] La sauvegarde a échoué.")
    else:
        print("ℹ️ [BACKUP] Sauvegarde annulée (Firebase non initialisé ou dossier de données manquant).")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(daily_backup_task, 'cron', hour='0,12', minute=0)
scheduler.start()
app.scheduler = scheduler
print("🗓️ Tâche de sauvegarde quotidienne planifiée.")

# Lancement du serveur de développement
if __name__ == '__main__':
    # Ouvre le navigateur uniquement lors du premier lancement
    if os.environ.get("WERKZEUG_RUN_MAIN") is None:
        webbrowser.open("http://127.0.0.1:3001/login")
            
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3001)), debug=True)