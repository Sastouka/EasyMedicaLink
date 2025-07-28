import os
import webbrowser
from flask import Flask, session, redirect, url_for, request, render_template_string, flash
from datetime import timedelta

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
            'logo_path':            cfg.get('logo_path', '/static/logo.png'),
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
    import routes # Importe le module contenant la fonction register_routes
    import activation # Importe le module activation pour accéder à son blueprint
    import patient_rdv # NOUVEAU : Importe le blueprint pour les RDV patients
    import biologie
    import radiologie
    import pharmacie
    import comptabilite
    import gestion_patient # NOUVEAU : Importe le blueprint de gestion des patients
    import guide # IMPORTER LE BLUEPRINT GUIDE ICI

    # Enregistrer les Blueprints en premier. L'ordre est important.
    # Le blueprint 'guide' doit être enregistré avant 'login' car 'login' le référence.
    app.register_blueprint(pwa.pwa_bp)
    app.register_blueprint(guide.guide_bp) # ENREGISTRER GUIDE.GUIDE_BP ICI
    app.register_blueprint(login.login_bp)
    app.register_blueprint(accueil.accueil_bp)
    app.register_blueprint(administrateur.administrateur_bp)
    app.register_blueprint(developpeur.developpeur_bp)
    app.register_blueprint(rdv.rdv_bp, url_prefix="/rdv")
    app.register_blueprint(facturation.facturation_bp)
    app.register_blueprint(statistique.statistique_bp, url_prefix="/statistique")
    # Enregistrer le blueprint d'activation après les autres blueprints
    app.register_blueprint(activation.activation_bp)
    # NOUVEAU : Enregistrement du blueprint pour les RDV patients
    # L'URL prefix dynamique est défini DANS le blueprint patient_rdv_bp lui-même
    app.register_blueprint(patient_rdv.patient_rdv_bp)
    # NOUVEAU : Enregistrement des nouveaux Blueprints
    app.register_blueprint(biologie.biologie_bp)
    app.register_blueprint(radiologie.radiologie_bp)
    app.register_blueprint(pharmacie.pharmacie_bp)
    app.register_blueprint(comptabilite.comptabilite_bp)
    app.register_blueprint(gestion_patient.gestion_patient_bp, url_prefix='/gestion_patient') # NOUVEAU


    # ───────────── 7. Route racine
    @app.route("/", methods=["GET"])
    def root():
        # Si non connecté, redirige vers login ; sinon vers accueil
        return redirect(url_for("login.login")) if "email" not in session else redirect(url_for("accueil.accueil"))

    # ───────────── 8. Configuration des chemins dynamiques par administrateur
    # Ce before_request est responsable de définir les chemins de données spécifiques à l'administrateur
    # pour les modules qui utilisent des dossiers de données par administrateur (Excel, PDF, Config, etc.).
    @app.before_request
    def set_dynamic_paths_for_current_admin():
        admin_email = session.get('admin_email', 'default_admin@example.com')
        print(f"DEBUG: L'application utilise le répertoire de données pour : {admin_email}")

        utils.set_dynamic_base_dir(admin_email) # Configure les chemins de base dynamiques pour utils
        rdv.set_rdv_dirs() # Initialise les répertoires spécifiques à RDV
        admin_email_prefix_for_patient_rdv = admin_email.split('@')[0]
        patient_rdv.set_patient_rdv_dirs(admin_email_prefix_for_patient_rdv) # Initialise les répertoires pour les RDV patients

        utils.init_app(app) # Réinitialise les utilitaires avec l'instance de l'application (charge la config, etc.)
        utils.load_patient_data() # Charge les données patient après la configuration des chemins

    # ───────────── 9. Intégration du middleware de sécurité (activation et permissions)
    # La logique de garde d'activation et de permissions est maintenant gérée par le module activation.
    # Ceci est crucial pour que les vérifications de sécurité s'appliquent à toutes les routes.
    activation.init_app(app)


    # ───────────── 10. Autres petites routes
    # Appeler routes.register_routes(app) ici, APRÈS que les before_request soient enregistrés.
    routes.register_routes(app)

    # ───────────── 11. Configuration PWA hors-ligne
    with app.app_context():
        # Utiliser app.test_request_context() pour construire des URLs en dehors d'une vraie requête.
        offline_urls = []
        for rule in app.url_map.iter_rules():
            # Exclure les règles avec des paramètres dynamiques (comme <string:admin_prefix>)
            # et les routes statiques qui sont gérées séparément par le service worker.
            if "GET" in rule.methods and not ("<" in rule.rule or rule.rule.startswith("/static")):
                try:
                    url = url_for(rule.endpoint)
                    offline_urls.append(url)
                except Exception as e:
                    # print(f"Ignorer l'URL pour le cache hors ligne PWA ({rule.endpoint}) : {e}")
                    pass # Ignorer les règles qui ne peuvent pas être construites sans paramètres
        
        # AJOUTER LA ROUTE DU GUIDE ICI POUR LE CACHE PWA
        # offline_urls.append('/guide/') # Assurez-vous que cette URL correspond à la route du guide

        # Ajouter manuellement les URLs nécessaires qui pourraient ne pas être capturées
        offline_urls.extend([
            '/offline',
            '/login',
            '/register',
            '/forgot_password',
            '/reset_password',
            '/activation',
            '/paypal_success',
            '/paypal_cancel'
        ])
        
        # Ajouter les routes spécifiques aux patients pour le RDV
        # Puisque patient_rdv_home a un préfixe dynamique, nous devons générer un exemple
        # ou s'assurer que le service worker peut gérer les routes dynamiques.
        # Pour la simplicité PWA, on peut inclure le pattern de base.
        # Note: Le service worker ne peut pas pré-cacher toutes les URL dynamiques.
        # Il gérera le "fetch" pour celles-ci.
        offline_urls.append('/patient_rdv/') # Le service worker peut intercepter les requêtes pour ce préfixe.
        offline_urls.append('/gestion_patient/') # NOUVEAU: Ajouter la route de gestion des patients

        app.config['PWA_OFFLINE_URLS'] = list(set(offline_urls)) # Supprimer les doublons
        print(f"URLs hors ligne PWA définies : {app.config['PWA_OFFLINE_URLS']}")


    # ───────────── 12. Page de secours hors-ligne
    @app.route("/offline")
    def offline():
        # Le contenu de cette route est un HTML autonome
        return render_template_string("""
<!DOCTYPE html>
<html lang="fr">
  {{ pwa_head()|safe }}
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hors-ligne</title>
  <style>
    body { display:flex;flex-direction:column;justify-content:center;align-items:center;height:100vh;margin:0;font-family:sans-serif;background:#f0f0f0;color:#333; }
    h1{font-size:2.5rem;margin-bottom:0.5rem;} p{font-size:1.1rem;}
  </style>
</head>
<body>
  <h1>Vous êtes hors-ligne</h1>
  <p>Vérifiez votre connexion et réessayez plus tard.</p>
</body>
</html>
"""), 200

    print("Application Flask démarrée et Blueprints enregistrés.")
    return app

# ───────────── Initialisation de l'application pour Gunicorn
# Cette ligne est déplacée ici pour que 'app' soit disponible au niveau du module
app = create_app()

# ───────────── 13. Lancement pour le développement local
if __name__ == '__main__':
    try:
        # Ouvrir dans le navigateur web seulement si pas dans un environnement conteneurisé (comme replit)
        if os.environ.get("FLASK_ENV") != "production" and not os.environ.get("REPL_SLUG"):
             webbrowser.open("http://127.0.0.1:3000/login")
    except Exception as e:
        print(f"Impossible d'ouvrir le navigateur web : {e}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
