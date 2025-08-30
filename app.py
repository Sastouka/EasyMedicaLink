import os
from datetime import datetime, timedelta
import webbrowser
# MODIFIÉ : Importation spécifique pour le blueprint et la base de données de l'assistant IA
from ia_assitant import ia_assitant_bp, db as ia_db
from flask import Flask, session, redirect, url_for, request, render_template_string, flash
# Construire le chemin absolu vers le nouvel emplacement du dossier 'instance'
instance_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MEDICALINK_DATA', 'instance')

# Créer l'application en spécifiant le nouveau chemin
app = Flask(__name__, instance_path=instance_folder_path)
from datetime import timedelta
# --- NOUVEAUX IMPORTS POUR FIREBASE ET LA PLANIFICATION ---
import json
from firebase import FirebaseManager
from apscheduler.schedulers.background import BackgroundScheduler
# ---------------------------------------------------------

# ───────────── 1. Création de l’application
def create_app():
    app = Flask(
        __name__,
        static_folder='static',
        static_url_path='/static',
        template_folder='templates'
    )
    # Utiliser une clé secrète depuis les variables d'environnement
    app.secret_key = os.environ.get("SECRET_KEY", "dev")
    app.permanent_session_lifetime = timedelta(days=7) # Les sessions durent 7 jours
    
    # NOUVEAU : Configuration de la base de données pour l'assistant IA
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medical_assistant.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # NOUVEAU : Initialisation de la base de données avec l'application Flask
    ia_db.init_app(app)
    
    # ───────────── 2. Thèmes
    import theme
    theme.init_theme(app)

    @app.context_processor
    def inject_theme_names():
        return {"theme_names": list(theme.THEMES.keys())}

    # ───────────── Injection des paramètres globaux dans tous les templates
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

    # ───────────── Enregistrement des Blueprints
    import pwa
    import login
    import accueil
    import administrateur
    import rdv
    import facturation
    import statistique
    import developpeur
    import routes 
    import activation 
    import patient_rdv
    import biologie
    import radiologie
    import pharmacie
    import comptabilite
    import gestion_patient
    import guide

    # Enregistrer les Blueprints
    app.register_blueprint(pwa.pwa_bp)
    app.register_blueprint(guide.guide_bp)
    app.register_blueprint(login.login_bp)
    app.register_blueprint(accueil.accueil_bp)
    app.register_blueprint(administrateur.administrateur_bp)
    app.register_blueprint(developpeur.developpeur_bp)
    app.register_blueprint(rdv.rdv_bp, url_prefix="/rdv")
    app.register_blueprint(facturation.facturation_bp)
    app.register_blueprint(statistique.statistique_bp, url_prefix="/statistique")
    app.register_blueprint(activation.activation_bp)
    app.register_blueprint(patient_rdv.patient_rdv_bp)
    app.register_blueprint(biologie.biologie_bp)
    app.register_blueprint(radiologie.radiologie_bp)
    app.register_blueprint(pharmacie.pharmacie_bp)
    app.register_blueprint(comptabilite.comptabilite_bp)
    app.register_blueprint(gestion_patient.gestion_patient_bp, url_prefix='/gestion_patient')
    # MODIFIÉ : Utilisation de la variable importée directement
    app.register_blueprint(ia_assitant_bp) 

    # ───────────── 7. Route racine
    @app.route("/", methods=["GET"])
    def root():
        return redirect(url_for("login.login")) if "email" not in session else redirect(url_for("accueil.accueil"))

    # ───────────── 8. Configuration des chemins dynamiques par administrateur
    @app.before_request
    def set_dynamic_paths_for_current_admin():
        admin_email = session.get('admin_email', 'default_admin@example.com')
        # print(f"DEBUG: L'application utilise le répertoire de données pour : {admin_email}") # Décommenter pour debug

        utils.set_dynamic_base_dir(admin_email)
        rdv.set_rdv_dirs()
        admin_email_prefix_for_patient_rdv = admin_email.split('@')[0]
        patient_rdv.set_patient_rdv_dirs()

        utils.init_app(app)
        utils.load_patient_data()

    # ───────────── 9. Intégration du middleware de sécurité
    activation.init_app(app)

    # ───────────── 10. Autres petites routes
    routes.register_routes(app)

    # ───────────── 11. Configuration PWA hors-ligne
    with app.app_context():
        offline_urls = []
        for rule in app.url_map.iter_rules():
            if "GET" in rule.methods and not ("<" in rule.rule or rule.rule.startswith("/static")):
                try:
                    url = url_for(rule.endpoint)
                    offline_urls.append(url)
                except Exception:
                    pass
        
        offline_urls.extend([
            '/offline', '/login', '/register', '/forgot_password',
            '/reset_password', '/activation', '/paypal_success', '/paypal_cancel',
            '/patient_rdv/', '/gestion_patient/'
        ])
        
        app.config['PWA_OFFLINE_URLS'] = list(set(offline_urls))
        # print(f"URLs hors ligne PWA définies : {app.config['PWA_OFFLINE_URLS']}") # Décommenter pour debug

    # ───────────── 12. Page de secours hors-ligne
    @app.route("/offline")
    def offline():
        return render_template_string("""
<!DOCTYPE html>
<html lang="fr">
  {{ pwa_head()|safe }}
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hors-ligne</title>
  <style>body{display:flex;flex-direction:column;justify-content:center;align-items:center;height:100vh;margin:0;font-family:sans-serif;background:#f0f0f0;color:#333;}h1{font-size:2.5rem;margin-bottom:0.5rem;}p{font-size:1.1rem;}</style>
</head>
<body><h1>Vous êtes hors-ligne</h1><p>Vérifiez votre connexion et réessayez plus tard.</p></body>
</html>
"""), 200

    # NOUVEAU : Création des tables de la base de données si elles n'existent pas
    with app.app_context():
        ia_db.create_all()

    print("Application Flask démarrée et Blueprints enregistrés.")
    return app

# ───────────── Initialisation de l'application pour Gunicorn
app = create_app()

# --- NOUVEAU : Initialisation de Firebase et planification de la sauvegarde ---

# 1. Initialisation du FirebaseManager
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

# 2. Rendre le manager accessible depuis l'objet app (pour les routes)
app.firebase_manager = firebase_manager

# 3. Fonction de sauvegarde à exécuter par le planificateur
def daily_backup_task():
    """
    Tâche qui compresse et téléverse le dossier MEDICALINK_DATA vers Firebase.
    """
    print(f"🚀 [BACKUP] Démarrage de la tâche de sauvegarde quotidienne à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    # Le chemin vers le dossier parent de toutes les données
    data_root_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MEDICALINK_DATA")
    
    if firebase_manager and os.path.exists(data_root_path):
        # On sauvegarde le dossier MEDICALINK_DATA en entier dans un dossier "daily_backups" sur Firebase
        success = firebase_manager.backup_directory(data_root_path, remote_folder="daily_backups")
        if success:
            print("✅ [BACKUP] Tâche de sauvegarde quotidienne terminée avec succès.")
        else:
            print("🔥 [BACKUP] La tâche de sauvegarde quotidienne a échoué.")
    else:
        print("ℹ️ [BACKUP] Le gestionnaire Firebase n'est pas initialisé ou le dossier MEDICALINK_DATA n'existe pas. Sauvegarde annulée.")

# 4. Planification de la tâche
scheduler = BackgroundScheduler(daemon=True)
# Exécute la tâche tous les jours à minuit (00:00)
scheduler.add_job(daily_backup_task, 'cron', hour=0, minute=0)
scheduler.start()
print("🗓️ Tâche de sauvegarde quotidienne planifiée pour s'exécuter tous les jours à minuit.")
# --- FIN DES AJOUTS ---


# ───────────── 13. Lancement pour le développement local
if __name__ == '__main__':
    try:
        if os.environ.get("FLASK_ENV") != "production" and not os.environ.get("REPL_SLUG"):
             webbrowser.open("http://127.0.0.1:3000/login")
    except Exception as e:
        print(f"Impossible d'ouvrir le navigateur web : {e}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))