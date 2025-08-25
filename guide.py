# guide.py
from flask import Blueprint, render_template_string, session, redirect, url_for, request # Import request
import utils
import theme
import login
from datetime import datetime # Import datetime for current date in template

guide_bp = Blueprint('guide', __name__, url_prefix='/guide')

guide_template = """
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Guide Utilisateur – {{ config.nom_clinique or 'EasyMedicaLink' }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&family=Great+Vibes&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script> <style>
        /* Variables CSS pour le thème */
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
        /* Styles généraux du corps de la page */
        body {
            font-family: var(--font-primary);
            background: var(--bg-color);
            color: var(--text-color);
            padding-top: 56px; /* Espace pour la barre de navigation fixe */
            transition: background 0.3s ease, color 0.3s ease;
            text-align: justify; /* Justifier le texte des paragraphes */
        }
        /* Styles de la barre de navigation */
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
        /* Styles du menu latéral (offcanvas) */
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
        /* Styles des cartes (sections du guide) */
        .card {
            border-radius: var(--border-radius-lg);
            box-shadow: var(--shadow-light);
            background: var(--card-bg) !important;
            color: var(--text-color) !important;
            border: none;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .card-header {
            background: var(--primary-color) !important;
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
        /* Styles des boutons */
        .btn {
            border-radius: var(--border-radius-md);
            font-weight: 600;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.75rem 1.25rem;
        }
        .btn i {
            margin-right: 0.5rem;
        }
        .btn-primary {
            background: var(--gradient-main);
            border: none;
            color: var(--button-text);
            box-shadow: var(--shadow-light);
        }
        .btn-primary:hover {
            box-shadow: var(--shadow-medium);
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
            box-shadow: var(--shadow-medium);
        }
        .btn-outline-secondary {
            border-color: var(--secondary-color);
            color: var(--text-color);
            background-color: transparent;
        }
        .btn-outline-secondary:hover {
            background-color: var(--secondary-color);
            color: white;
            box-shadow: var(--shadow-light);
        }
        /* Styles du pied de page */
        footer {
            background: var(--gradient-main);
            color: white;
            font-weight: 300;
            box-shadow: 0 -5px 15px rgba(0, 0, 0, 0.1);
        }
        footer a {
            color: white;
            text-decoration: none;
            transition: color 0.2s ease;
        }
        footer a:hover {
            color: var(--text-color-light);
        }
        /* Ajustements responsifs pour les petits écrans */
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
            /* Ajustements pour les titres de section */
            .guide-section h3 {
                font-size: 1.2rem !important;
            }
            .guide-section h4 {
                font-size: 1rem !important;
            }
            .guide-item i {
                font-size: 1.5rem !important;
            }
            .btn {
                padding: 0.6rem 1rem;
                font-size: 0.9rem;
            }
            .d-flex.gap-2 {
                flex-direction: column;
            }
        }
        /* Styles des sections du guide */
        .guide-section {
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }
        .guide-section:last-child {
            border-bottom: none;
        }

        .guide-section h3, .guide-section h4 {
            font-size: 1.4rem; /* Taille de police augmentée pour les titres */
            font-weight: 700; /* Plus gras pour les titres */
            margin-bottom: 0.75rem; /* Marge ajustée */
        }
        .guide-section h3 {
            color: var(--primary-color);
            margin-top: 1.5rem; /* Espacement avant les titres de section principaux */
        }
        .guide-section h4 {
            color: var(--secondary-color);
            margin-top: 1.5rem; /* Espacement pour les sous-titres */
        }
        .guide-item {
            display: flex;
            align-items: flex-start;
            margin-bottom: 1rem;
        }
        .guide-item i {
            font-size: 1.8rem;
            margin-right: 1rem;
            color: var(--primary-color);
        }
        .guide-item .text-content {
            flex-grow: 1;
        }
        /* Styles des conteneurs d'iframe */
        .guide-iframe-container {
            position: relative;
            width: 100%;
            height: 130vh; /* Hauteur ajustée pour plus de contenu */
            border: 1px solid #ddd;
            border-radius: var(--border-radius-md);
            overflow: hidden; /* Masquer les barres de défilement si le contenu déborde */
            margin-top: 1rem;
            margin-bottom: 1rem;
            box-shadow: var(--shadow-light);
            background-color: var(--card-bg); /* Assurer un fond pour le message de chargement */
        }
        .guide-iframe-container iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
        .iframe-loading-message {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(var(--primary-color-rgb), 0.05); /* Utiliser la couleur primaire avec opacité */
            display: flex;
            justify-content: center;
            align-items: center;
            flex-direction: column;
            color: var(--text-color-light);
            font-size: 1.2rem;
            z-index: 10;
            text-align: center;
        }
        /* Styles pour le code en ligne */
        .inline-code {
            font-family: 'Courier New', monospace;
            background-color: rgba(var(--primary-color-rgb), 0.1);
            padding: 0.2em 0.4em;
            border-radius: 3px;
            font-size: 0.9em;
        }
        /* Styles pour la table des modules */
        .module-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1.5rem;
        }
        .module-table th, .module-table td {
            border: 1px solid var(--border-color);
            padding: 0.75rem;
            text-align: left;
            vertical-align: top;
        }
        .module-table th {
            background-color: var(--primary-color);
            color: var(--button-text);
            font-weight: 600;
        }
        .module-table tr:nth-child(even) {
            background-color: var(--table-striped-bg);
        }
        .module-table td i {
            margin-right: 0.5rem;
            color: var(--primary-color); /* Couleur pour les icônes dans le tableau */
        }
        /* Permet le défilement horizontal du tableau sur les petits écrans */
        .table-responsive {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch; /* Améliore le défilement sur iOS */
        }
        /* Styles pour la mise en surbrillance de recherche */
        .highlight {
            background-color: yellow;
            font-weight: bold;
            scroll-margin-top: 70px; /* Espace pour la barre de navigation fixe */
        }
        .highlight.active {
            background-color: orange; /* Couleur pour le résultat actif */
        }
        /* Centrage du contenu principal */
        .container-main-content {
            max-width: 960px; /* Largeur maximale pour le contenu */
            margin-left: auto;
            margin-right: auto;
        }
        /* Ajustements pour l'impression PDF */
        @media print {
            body {
                padding-top: 0;
                color: black;
                background: white;
            }
            .navbar, .offcanvas, footer, .search-bar-container, .iframe-actions {
                display: none !important;
            }
            .guide-section {
                border-bottom: 1px solid #eee;
                page-break-inside: avoid; /* Éviter de couper les sections entre les pages */
            }
            .guide-iframe-container {
                height: 400px; /* Hauteur plus petite pour l'impression */
                overflow: hidden; /* Masquer les barres de défilement pour l'impression */
                border: none;
                box-shadow: none;
            }
        }
        /* Styles personnalisés pour les paragraphes */
        p {
            margin-bottom: 1em; /* Ajoute un espace après chaque paragraphe */
        }
        /* Styles pour le texte en gras (remplace les astérisques) */
        strong {
            font-weight: 600; /* Moins gras que 'bold' */
            color: var(--text-color); /* Utilise la couleur de texte normale pour éviter le contraste trop fort */
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark fixed-top">
        <div class="container-fluid d-flex align-items-center">
            <button class="navbar-toggler" type="button" data-bs-toggle="offcanvas" data-bs-target="#settingsOffcanvas">
                <i class="fas fa-bars"></i>
            </button>
            <a class="navbar-brand ms-auto d-flex align-items-center" href="{{ url_for('accueil.accueil') }}">
                <i class="fas fa-home me-2"></i> EasyMedicaLink
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
                <a href="{{ url_for('login.logout') }}" class="btn btn-outline-secondary flex-fill">
                    <i class="fas fa-sign-out-alt me-2" style="color: #DC143C;"></i>Déconnexion
                </a>
            </div>
        </div>
    </div>

    <div class="container-fluid my-4 container-main-content">
        <div class="row justify-content-center">
            <div class="col-12">
                <div class="card shadow-lg">
                    <div class="card-header py-3 text-center">
                        <h1 class="mb-2 header-item">
                            <i class="fas fa-hospital me-2"></i> {{ config.nom_clinique or config.cabinet or 'EasyMedicaLink' }}
                        </h1>
                        <p class="mt-2 header-item">
                            <i class="fas fa-book me-2"></i> Guide d'utilisation
                        </p>
                    </div>
                    <div class="card-body p-4" id="guide-content">
                        <div class="guide-section">
                            <h3><i class="fas fa-hand-point-right me-2" style="color: #4CAF50;"></i>Introduction</h3>
                            <p>Bienvenue dans le guide d'utilisation d'EasyMedicaLink ! Cette application a été conçue pour simplifier la gestion quotidienne de votre clinique ou cabinet médical.</p>
                            <p>Ce guide vous accompagnera <strong>étape par étape</strong> pour maîtriser toutes les fonctionnalités.</p>
                        </div>

                        <div class="guide-section">
                            <h3><i class="fas fa-th-large me-2" style="color: #2196F3;"></i>Aperçu des Modules</h3>
                            <p>EasyMedicaLink est organisé en plusieurs modules, chacun dédié à une facette de la gestion de votre clinique. L'accès à certains modules dépendra de votre <strong>rôle</strong>.</p>
                            <div class="table-responsive"> <table class="module-table">
                                    <thead>
                                        <tr>
                                            <th>Module</th>
                                            <th>Fonctionnalité principale</th>
                                            <th>Rôles typiques</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr>
                                            <td><i class="fas fa-user-shield" style="color: #FFD700;"></i> Administration</td>
                                            <td>Gestion des utilisateurs, paramètres généraux, licences.</td>
                                            <td><strong>Admin</strong></td>
                                        </tr>
                                        <tr>
                                            <td><i class="fas fa-users" style="color: #007BFF;"></i> Patients</td>
                                            <td>Base de données patients, badges, transfert vers consultation.</td>
                                            <td><strong>Admin</strong>, <strong>Assistante</strong>, <strong>Médecin</strong></td>
                                        </tr>
                                        <tr>
                                            <td><i class="fas fa-calendar-check" style="color: #4CAF50;"></i> Rendez-vous (RDV)</td>
                                            <td>Prise de rendez-vous, gestion de la salle d'attente.</td>
                                            <td><strong>Admin</strong>, <strong>Assistante</strong>, <strong>Médecin</strong></td>
                                        </tr>
                                        <tr>
                                            <td><i class="fas fa-stethoscope" style="color: #20B2AA;"></i> Consultation</td>
                                            <td>Enregistrement des détails de consultation, ordonnances, certificats.</td>
                                            <td><strong>Médecin</strong></td>
                                        </tr>
                                        <tr>
                                            <td><i class="fas fa-file-invoice-dollar" style="color: #FFD700;"></i> Facturation</td>
                                            <td>Émission de factures, enregistrement des paiements, rapports financiers.</td>
                                            <td><strong>Admin</strong>, <strong>Comptable</strong>, <strong>Assistante</strong></td>
                                        </tr>
                                        <tr>
                                            <td><i class="fas fa-flask" style="color: #DA70D6;"></i> Biologie</td>
                                            <td>Gestion des analyses biologiques et leurs résultats.</td>
                                            <td><strong>Biologiste</strong>, <strong>Médecin</strong>, <strong>Admin</strong></td>
                                        </tr>
                                        <tr>
                                            <td><i class="fas fa-x-ray" style="color: #8A2BE2;"></i> Radiologie</td>
                                            <td>Gestion des analyses radiologiques et leurs résultats.</td>
                                            <td><strong>Radiologue</strong>, <strong>Médecin</strong>, <strong>Admin</strong></td>
                                        </tr>
                                        <tr>
                                            <td><i class="fas fa-prescription-bottle-alt" style="color: #FF9800;"></i> Pharmacie & Stock</td>
                                            <td>Inventaire des produits, mouvements de stock, alertes.</td>
                                            <td><strong>Pharmacien/Magasinier</strong>, <strong>Admin</strong></td>
                                        </tr>
                                        <tr>
                                            <td><i class="fas fa-calculator" style="color: #00BCD4;"></i> Comptabilité</td>
                                            <td>Gestion des recettes, dépenses, salaires, documents fiscaux.</td>
                                            <td><strong>Comptable</strong>, <strong>Admin</strong></td>
                                        </tr>
                                        <tr>
                                            <td><i class="fas fa-chart-pie" style="color: #4CAF50;"></i> Statistiques</td>
                                            <td>Tableaux de bord, KPIs, graphiques d'analyse d'activité.</td>
                                            <td><strong>Admin</strong>, <strong>Médecin</strong></td>
                                        </tr>
                                        <tr>
                                            <td><i class="fas fa-robot" style="color: #6f42c1;"></i> Assistant IA</td>
                                            <td>Assistant médical pour aide à la décision et analyse de documents.</td>
                                            <td><strong>Admin</strong>, <strong>Médecin</strong></td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div class="guide-section">
                            <h3><i class="fas fa-user-shield me-2" style="color: #FFD700;"></i>1. Module de Connexion et d'Activation</h3>
                            <p>Ce module gère l'<strong>accès à l'application</strong> et la <strong>validité de votre licence</strong>.</p>
                            
                            <h4><i class="fas fa-sign-in-alt me-2" style="color: #1a73e8;"></i>Page de Connexion</h4>
                            <p>C'est votre point d'entrée dans EasyMedicaLink. Vous y entrerez vos identifiants pour accéder à l'application.</p>
                            <div class="guide-item">
                                <i class="fas fa-users-cog" style="color: #673AB7;"></i><div class="text-content"><strong>Sélection du Rôle</strong> : Choisissez votre rôle (<strong>Admin</strong>, <strong>Médecin</strong>, <strong>Assistante</strong>, etc.) pour la session. Cela détermine les fonctionnalités auxquelles vous aurez accès.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-envelope" style="color: #FF5722;"></i><div class="text-content"><strong>Champ Email</strong> : Saisissez votre adresse e-mail enregistrée.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-key" style="color: #E91E63;"></i><div class="text-content"><strong>Champ Mot de passe</strong> : Saisissez votre mot de passe sécurisé.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-sign-in-alt" style="color: #4CAF50;"></i><div class="text-content"><strong>Bouton "Se connecter"</strong> : Cliquez ici pour valider vos identifiants et accéder à l'application.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-user-plus" style="color: #00BCD4;"></i><div class="text-content"><strong>Lien "Créer un compte"</strong> : Permet à un nouvel administrateur de s'enregistrer.</div>
                            </div>
                            <p class="alert alert-info"><strong>Note</strong> : Pour interagir pleinement avec cette page (et les suivantes) dans le guide, il est recommandé d'être déjà connecté à l'application principale dans un autre onglet avec un compte administrateur.</p>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('login.login') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="login_iframe" src="{{ url_for('login.login', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>

                            <h4><i class="fas fa-user-plus me-2" style="color: #00BCD4;"></i>Page d'Enregistrement</h4>
                            <p>Cette page est exclusivement destinée à la <strong>création du compte administrateur principal</strong> de la clinique. Les informations que vous saisissez ici sont cruciales pour la récupération de votre mot de passe en cas d'oubli.</p>
                            <div class="guide-item">
                                <i class="fas fa-envelope" style="color: #FF5722;"></i><div class="text-content"><strong>Champ Email</strong> : L'adresse e-mail qui sera associée à ce compte administrateur.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-key" style="color: #E91E63;"></i><div class="text-content"><strong>Champs Mot de passe / Confirmer</strong> : Définissez et confirmez votre mot de passe.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-hospital-symbol" style="color: #000080;"></i><div class="text-content"><strong>Nom Clinique/Cabinet</strong> : Le nom officiel de votre établissement.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-calendar-alt" style="color: #FF69B4;"></i><div class="text-content"><strong>Date de création (Clinique)</strong> : La date d'établissement de votre clinique.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-map-marker-alt" style="color: #28A745;"></i><div class="text-content"><strong>Adresse</strong> : L'adresse physique de votre clinique.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-phone" style="color: #17A2B8;"></i><div class="text-content"><strong>Téléphone</strong> : Le numéro de contact de la clinique.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-user-plus" style="color: #4CAF50;"></i><div class="text-content"><strong>Bouton "S'enregistrer"</strong> : Crée votre compte administrateur.</div>
                            </div>
                            <p class="alert alert-info"><strong>Conseil</strong> : Notez bien toutes les informations d'enregistrement (<strong>Email</strong>, <strong>Nom Clinique</strong>, <strong>Date de création</strong>, <strong>Adresse</strong>, <strong>Téléphone</strong>) dans un endroit sûr ! Elles sont indispensables pour la récupération de votre compte.</p>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('login.register') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="register_iframe" src="{{ url_for('login.register', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>

                            <h4><i class="fas fa-power-off me-2" style="color: #DC3545;"></i>Page d'Activation</h4>
                            <p>Si votre licence d'utilisation n'est pas valide ou a expiré, vous serez automatiquement redirigé vers cette page. Elle est essentielle pour maintenir votre accès complet à l'application.</p>
                            <div class="guide-item">
                                <i class="fas fa-desktop" style="color: #607D8B;"></i><div class="text-content"><strong>ID machine</strong> : Un identifiant unique de votre appareil, nécessaire pour générer une clé d'activation.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-code" style="color: #9E9E9E;"></i><div class="text-content"><strong>Clé (optionnelle)</strong> : Si vous avez une clé d'activation fournie par le support, saisissez-la ici.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-hourglass-start" style="color: #FFC107;"></i><div class="text-content"><strong>Bouton "Essai 7 jours"</strong> : Active une période d'essai gratuite pour découvrir l'application.</div>
                            </div>
                            <div class="guide-item">
                                <i class="fas fa-calendar-day" style="color: #FF9800;"></i><div class="text-content"><strong>Boutons "1 mois"</strong>, <strong>"1 an"</strong>, <strong>"Illimité"</strong> : Permettent de choisir un plan d'abonnement et de procéder au paiement.</div>
                            </div>
                            <p class="alert alert-warning"><strong>Important</strong> : Le <strong>plan d'essai</strong> est généralement activé automatiquement à la création d'un compte admin. Si la période d'essai est terminée, vous devrez choisir un plan payant pour continuer à utiliser l'application.</p>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('activation.activation') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="activation_iframe" src="{{ url_for('activation.activation', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                        </div>

                        <div class="guide-section">
                            <h3><i class="fas fa-home me-2" style="color: #0d9488;"></i>2. Accueil (Tableau de Bord Principal)</h3>
                            <p>Après une connexion réussie, vous arrivez sur la page d'accueil. C'est votre centre de commande, offrant un accès rapide à tous les modules de l'application via des icônes interactives.</p>
                            <h4><i class="fas fa-tachometer-alt me-2" style="color: #1a73e8;"></i>Page d'Organisation de l'Accueil</h4>
                            <p>La page d'accueil est divisée en plusieurs sections clés :</p>
                            <ul>
                                <li><strong>En-tête de la Clinique</strong> : Affiche le nom de votre clinique (ex: "{{ config.nom_clinique or 'EasyMedicaLink' }}"), le nom du médecin connecté (ex: "{{ logged_in_doctor_name or config.doctor_name or 'NOM MEDECIN' }}") et le lieu (ex: "{{ config.location or 'LIEU' }}"), ainsi que la date du jour (ex: "{{ datetime.now().strftime('%d/%m/%Y') }}").</li>
                                <li><strong>Icônes des Modules</strong> : Une grille d'icônes représente chaque module de l'application. Vous pouvez les <strong>glisser-déposer</strong> pour les réorganiser selon vos préférences. Un simple clic sur une icône vous mènera au module correspondant.</li>
                                <li><strong>Menu Latéral</strong> (<i class="fas fa-bars" style="color: #6c757d;"></i>) : Accessible en cliquant sur l'icône en haut à gauche. Il contient des options rapides comme la <strong>Déconnexion</strong> (<i class="fas fa-sign-out-alt" style="color: #DC143C;"></i>) et la <strong>Modification de votre mot de passe</strong> (<i class="fas fa-key" style="color: #FFD700;"></i>).</li>
                            </ul>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('accueil.accueil') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="accueil_iframe" src="{{ url_for('accueil.accueil', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                            <p class="alert alert-info"><strong>Astuce</strong> : Les icônes des modules sont dynamiques. Seuls les modules auxquels votre rôle a accès seront visibles ici, garantissant une interface épurée et pertinente pour chaque utilisateur.</p>
                        </div>
                        
                        {% if 'administrateur_bp' in allowed_pages %}
                        <div class="guide-section">
                            <h3><i class="fas fa-users-cog me-2" style="color: #FFD700;"></i>3. Module Administration</h3>
                            <p>Ce module, accessible via l'icône <i class="fas fa-user-shield" style="color: #FFD700;"></i> sur le tableau de bord, est <strong>réservé aux administrateurs</strong>. Il offre un contrôle total sur la configuration de l'application, la gestion des utilisateurs et les données de la clinique.</p>
                            <h4><i class="fas fa-desktop me-2" style="color: #007BFF;"></i>Page Principale : Tableau de Bord Administrateur</h4>
                            <p>Cette page centralise tous les outils nécessaires à la gestion de votre environnement EasyMedicaLink, organisés en plusieurs sections :</p>
                            <ul>
                                <li><strong>Informations de Licence</strong> : Affiche le type de votre plan actuel (<strong>Essai</strong>, <strong>1 mois</strong>, <strong>1 an</strong>, <strong>Illimité</strong>) et l'e-mail de l'administrateur principal.</li>
                                <li><strong>Paramètres Généraux de l'Application</strong> :
                                    <ul>
                                        <li>Champs pour le <strong>Nom Clinique/Cabinet</strong> (<i class="fas fa-hospital"></i>), le <strong>Nom du Médecin</strong> principal (<i class="fas fa-user-md"></i>), le <strong>Lieu</strong> (<i class="fas fa-map-marker-alt"></i>).</li>
                                        <li>Sélection du <strong>Thème</strong> (<i class="fas fa-palette"></i>) visuel de l'application.</li>
                                        <li>Définition de la <strong>Devise</strong> (<i class="fas fa-money-bill-wave"></i>) (ex: MAD, EUR) et du <strong>Taux de TVA (%)</strong> (<i class="fas fa-percent"></i>) par défaut.</li>
                                        <li>Configuration des <strong>Heures de début/fin de RDV</strong> (<i class="fas fa-clock"></i>) et de l'<strong>Intervalle</strong> des créneaux pour la prise de RDV en ligne.</li>
                                        <li>Bouton <strong>"Importer Logo/Arrière-plan"</strong> (<i class="fas fa-image" style="color: #DA70D6;"></i>) pour personnaliser vos documents PDF (factures, certificats) avec l'image de votre clinique.</li>
                                        <li><strong>Bouton "Enregistrer les paramètres"</strong> (<i class="fas fa-save" style="color: #28a745;"></i>) pour sauvegarder vos modifications.</li>
                                    </ul>
                                </li>
                                <li><strong>Gestion des Listes (Médicaments, Analyses, Radiologies)</strong> :
                                    <ul>
                                        <li>Trois zones de texte distinctes pour personnaliser les listes de <strong>Médicaments</strong> (<i class="fas fa-pills" style="color: #4CAF50;"></i>), d'<strong>Analyses</strong> (<i class="fas fa-flask" style="color: #DA70D6;"></i>) et de <strong>Radiologies</strong> (<i class="fas fa-x-ray" style="color: #8A2BE2;"></i>) qui apparaissent dans le module Consultation. Chaque élément doit être sur une nouvelle ligne.</li>
                                        <li><strong>Bouton "Enregistrer les listes"</strong> (<i class="fas fa-save" style="color: #28a745;"></i>) pour sauvegarder ces listes personnalisées.</li>
                                    </ul>
                                </li>
                                <li><strong>Accès Patient & Indisponibilités</strong> :
                                    <ul>
                                        <li>Affiche un <strong>Lien de prise de rendez-vous</strong> (<i class="fas fa-link" style="color: #007BFF;"></i>) unique et un <strong>QR Code</strong> (<i class="fas fa-qrcode" style="color: #6C757D;"></i>) que vous pouvez partager avec vos patients pour qu'ils prennent rendez-vous en ligne. Le bouton <strong>"Copier le lien"</strong> (<i class="fas fa-copy" style="color: #17A2B8;"></i>) est disponible.</li>
                                        <li>Section <strong>"Gérer les indisponibilités"</strong> (<i class="fas fa-calendar-times" style="color: #DC3545;"></i>) pour ajouter des périodes où le cabinet est fermé (avec dates de début/fin et une raison). Les patients ne pourront pas prendre de RDV en ligne pendant ces périodes. Le bouton <strong>"Ajouter une période"</strong> (<i class="fas fa-plus-circle" style="color: #4CAF50;"></i>) et des boutons <strong>"Supprimer"</strong> (<i class="fas fa-trash" style="color: #DC3545;"></i>) pour les périodes existantes sont fournis.</li>
                                    </ul>
                                </li>
                                <li><strong>Administration des Comptes</strong> :
                                    <ul>
                                        <li>Formulaire <strong>"Créer un compte"</strong> (<i class="fas fa-user-plus" style="color: #00BCD4;"></i>) pour ajouter de nouveaux utilisateurs (<strong>Médecins</strong>, <strong>Assistantes</strong>, <strong>Comptables</strong>, <strong>Biologistes</strong>, <strong>Radiologues</strong>, <strong>Pharmacie & Magasin</strong>). Vous définissez leur <strong>Nom</strong>, <strong>Prénom</strong>, <strong>Téléphone</strong>, <strong>Rôle</strong>, <strong>Mot de passe</strong> et les <strong>Autorisations d'accès aux pages</strong> (modules spécifiques). Pour les assistantes, vous pouvez lier un <strong>Médecin lié</strong>.</li>
                                        <li>Tableau <strong>"Comptes admin"</strong> (<i class="fas fa-users" style="color: #007BFF;"></i>) listant tous les utilisateurs gérés par cet administrateur. Pour chaque utilisateur, vous pouvez :
                                            <ul>
                                                <li><strong>Modifier</strong> (<i class="fas fa-pen" style="color: #FFC107;"></i>) : Pour mettre à jour leurs informations ou leurs permissions.</li>
                                                <li><strong>Activer/Désactiver</strong> (<i class="fas fa-power-off" style="color: #6C757D;"></i>) : Pour suspendre ou réactiver leur accès.</li>
                                                <li><strong>WhatsApp</strong> (<i class="fab fa-whatsapp" style="color: #25D366;"></i>) : Pour contacter l'utilisateur.</li>
                                                <li><strong>Supprimer</strong> (<i class="fas fa-trash" style="color: #DC3545;"></i>) : Pour retirer définitivement un compte.</li>
                                            </ul>
                                        </li>
                                    </ul>
                                </li>
                                <li><strong>Gestion des Fichiers & Applications</strong> :
                                    <ul>
                                        <li><strong>"Télécharger votre base de données"</strong> (<i class="fas fa-file-excel" style="color: #28A745;"></i>) : Exporte toutes les données de votre clinique (patients, RDV, consultations, factures, comptabilité, pharmacie) dans un fichier Excel unique.</li>
                                        <li><strong>"Importer votre base de données"</strong> (<i class="fas fa-upload" style="color: #17A2B8;"></i>) : Permet de restaurer les données à partir d'un fichier Excel de sauvegarde.</li>
                                        <li><strong>"Télécharger EasyMedicaLink Win64/Win32"</strong> (<i class="fas fa-download" style="color: #007BFF;"></i>) : Pour obtenir la version installable de l'application sur Windows, utile pour un travail collaboratif en réseau local.</li>
                                    </ul>
                                </li>
                            </ul>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('administrateur_bp.dashboard') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="admin_iframe" src="{{ url_for('administrateur_bp.dashboard', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                        </div>
                        {% endif %}

                        {% if 'rdv' in allowed_pages %}
                        <div class="guide-section">
                            <h3><i class="fas fa-calendar-check me-2" style="color: #4CAF50;"></i>4. Module Rendez-vous (RDV)</h3>
                            <p>Le module RDV, accessible via l'icône <i class="fas fa-calendar-check" style="color: #4CAF50;"></i> sur le tableau de bord, est conçu pour gérer efficacement les rendez-vous des patients, aussi bien pour le personnel de la clinique que pour les patients eux-mêmes via la prise de RDV en ligne.</p>
                            <h4><i class="fas fa-desktop me-2" style="color: #007BFF;"></i>Page Principale : Gestion des RDV (Côté Clinique)</h4>
                            <p>Cette page est votre interface pour visualiser, ajouter, modifier et gérer tous les rendez-vous de votre clinique.</p>
                            <ul>
                                <li><strong>Formulaire de Prise de RDV</strong> : Situé en haut de page, il permet d'enregistrer manuellement un nouveau rendez-vous. C'est un processus en deux étapes :
                                    <ul>
                                        <li><strong>Étape 1 : Identité Patient</strong> (<i class="fas fa-user" style="color: #007BFF;"></i>) : Saisissez l'<strong>ID Patient</strong> (<i class="fas fa-id-card" style="color: #6C757D;"></i>) (qui peut auto-remplir les autres champs si le patient existe déjà), son <strong>Nom</strong>, <strong>Prénom</strong>, <strong>Sexe</strong>, <strong>Date de naissance</strong>, <strong>Téléphone</strong> et ses <strong>Antécédents médicaux</strong>. Le bouton <strong>"Suivant"</strong> (<i class="fas fa-arrow-right" style="color: #6c757d;"></i>) vous mène à l'étape 2.</li>
                                        <li><strong>Étape 2 : Détails du RDV</strong> (<i class="fas fa-calendar-plus" style="color: #4CAF50;"></i>) : Choisissez la <strong>Date souhaitée</strong> (<i class="fas fa-calendar-day" style="color: #FFC107;"></i>), le <strong>Médecin</strong> (<i class="fas fa-user-md" style="color: #ADD8E6;"></i>) et l'<strong>Heure souhaitée</strong> (<i class="fas fa-clock" style="color: #20B2AA;"></i>) parmi les créneaux disponibles. Le bouton <strong>"Confirmer le RDV"</strong> (<i class="fas fa-check-circle" style="color: #6c757d;"></i>) valide le rendez-vous.</li>
                                    </ul>
                                </li>
                                <li><strong>Filtres de RDV</strong> : Une barre de recherche et un sélecteur de date vous permettent de filtrer les rendez-vous affichés dans le tableau principal.
                                    <ul>
                                        <li><strong>Bouton "Filtrer"</strong> (<i class="fas fa-filter" style="color: #6c757d;"></i>) : Applique le filtre de date.</li>
                                        <li><strong>Bouton "Tous"</strong> (<i class="fas fa-list" style="color: #6c757d;"></i>) : Réinitialise les filtres et affiche tous les rendez-vous enregistrés.</li>
                                    </ul>
                                </li>
                                <li><strong>Rendez-vous du Jour</strong> : Une section dédiée affiche les rendez-vous prévus pour la date actuelle (aujourd'hui), permettant un accès rapide à la consultation pour les patients en attente. Un bouton <strong>"Consultation"</strong> (<i class="fas fa-stethoscope" style="color: #6c757d;"></i>) est disponible pour chaque RDV.</li>
                                <li><strong>Tableau des Rendez-vous Confirmés</strong> : Une liste détaillée de tous les rendez-vous enregistrés. Pour chaque entrée, vous pouvez :
                                    <ul>
                                        <li><strong>Bouton "Consultation"</strong> (<i class="fas fa-stethoscope" style="color: #6c757d;"></i>) : Passe directement à l'enregistrement d'une consultation pour ce patient.</li>
                                        <li><strong>Bouton "Modifier"</strong> (<i class="fas fa-pen" style="color: #6c757d;"></i>) : Ouvre le formulaire de RDV avec les informations pré-remplies pour modification.</li>
                                        <li><strong>Bouton "Supprimer"</strong> (<i class="fas fa-trash" style="color: #6c757d;"></i>) : Annule un rendez-vous après confirmation.</li>
                                        <li><strong>Bouton "WhatsApp"</strong> (<i class="fab fa-whatsapp" style="color: #25D366;"></i>) : Ouvre une conversation WhatsApp pré-remplie avec un rappel de rendez-vous pour le patient.</li>
                                    </ul>
                                </li>
                                <li><strong>Bouton "RDV du Jour"</strong> (<i class="fas fa-file-pdf" style="color: #6c757d;"></i>) : Génère un PDF de la liste des rendez-vous pour la date actuelle, utile pour l'impression.</li>
                            </ul>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('rdv.rdv_home') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="rdv_clinic_iframe" src="{{ url_for('rdv.rdv_home', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                            <p class="alert alert-info"><strong>Rôle</strong> : Ce module est généralement utilisé par les Assistantes et les Médecins.</p>

                            <h4><i class="fas fa-globe me-2" style="color: #2196F3;"></i>Page de Prise de RDV en Ligne (Côté Patient)</h4>
                            <p>Cette page est accessible aux patients via un lien ou un QR code fourni par l'administrateur. Elle permet aux patients de soumettre des demandes de rendez-vous en ligne, sans avoir besoin de se connecter.</p>
                            <ul>
                                <li><strong>Formulaire Guidé</strong> : Le patient remplit ses informations personnelles (identité, contact) puis choisit une date, un médecin et un créneau horaire disponible.
                                    <ul>
                                        <li><strong>Étape 1 : Vos informations</strong> (<i class="fas fa-user" style="color: #007BFF;"></i>) : Saisie de l'<strong>ID Patient</strong> (<i class="fas fa-id-card" style="color: #6C757D;"></i>), <strong>Nom</strong>, <strong>Prénom</strong>, <strong>Sexe</strong>, <strong>Date de naissance</strong>, <strong>Téléphone</strong> et <strong>Antécédents médicaux</strong>. Le bouton <strong>"Suivant"</strong> (<i class="fas fa-arrow-right" style="color: #6c757d;"></i>) vous mène à l'étape suivante.</li>
                                        <li><strong>Étape 2 : Choisissez votre RDV</strong> (<i class="fas fa-calendar-plus" style="color: #4CAF50;"></i>) : Sélection de la <strong>Date souhaitée</strong> (<i class="fas fa-calendar-day" style="color: #FFC107;"></i>) et du <strong>Médecin</strong> (<i class="fas fa-user-md" style="color: #ADD8E6;"></i>). La liste des <strong>Heures souhaitées</strong> (<i class="fas fa-clock" style="color: #20B2AA;"></i>) est mise à jour dynamiquement pour n'afficher que les créneaux disponibles pour le médecin et la date choisis.</li>
                                    </ul>
                                </li>
                                <li><strong>Vérification des Créneaux</strong> : Le système affiche uniquement les créneaux disponibles et bloque les dates où le cabinet est indisponible (configuré par l'administrateur dans le module Administration).</li>
                                <li><strong>Confirmation</strong> : Après soumission via le bouton <strong>"Confirmer le RDV"</strong> (<i class="fas fa-check-circle" style="color: #6c757d;"></i>) , le rendez-vous est marqué "En attente d'approbation" dans le système de la clinique. Une confirmation sera envoyée au patient après approbation par le cabinet.</li>
                            </ul>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('patient_rdv.patient_rdv_home', admin_prefix='default_admin') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="rdv_patient_iframe" src="{{ url_for('patient_rdv.patient_rdv_home', admin_prefix='default_admin', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                            <p class="alert alert-warning"><strong>Note</strong> : Ce module est public et ne nécessite aucune connexion pour le patient. Il est le point d'entrée pour la prise de RDV en ligne.</p>
                        </div>
                        {% endif %}

                        {% if 'routes' in allowed_pages %}
                        <div class="guide-section">
                            <h3><i class="fas fa-stethoscope me-2" style="color: #20B2AA;"></i>5. Module Consultation</h3>
                            <p>Le module Consultation, accessible via l'icône <i class="fas fa-stethoscope" style="color: #20B2AA;"></i> sur le tableau de bord, est l'outil principal pour les médecins. Il permet d'enregistrer toutes les informations pertinentes d'une consultation médicale.</p>
                            <h4><i class="fas fa-desktop me-2" style="color: #007BFF;"></i>Page Principale : Enregistrement de Consultation</h4>
                            <p>Cette page est un formulaire complet organisé en onglets pour faciliter la saisie des données cliniques et administratives d'une consultation.</p>
                            <ul>
                                <li><strong>Onglet "Infos Base"</strong> (<i class="fas fa-user-injured" style="color: #007BFF;"></i>) : Saisie des informations du médecin consultant et du patient. Le champ "<span class="inline-code">ID Patient</span>" (<i class="fas fa-id-card" style="color: #6C757D;"></i>) est crucial : en le remplissant, les informations du patient (Nom, Prénom, Âge, etc.) sont automatiquement pré-remplies si le patient existe dans la base de données.</li>
                                <li><strong>Onglet "Diagnostique"</strong> (<i class="fas fa-stethoscope" style="color: #20B2AA;"></i>) : Pour enregistrer les <span class="inline-code">Signes Cliniques</span> (<i class="fas fa-notes-medical" style="color: #FF69B4;"></i>), les paramètres vitaux (Tension <i class="fas fa-heartbeat" style="color: #DC143C;"></i>, Température <i class="fas fa-thermometer-half" style="color: #FFD700;"></i>, Fréquence Cardiaque <i class="fas fa-heart" style="color: #FF69B4;"></i>, Fréquence Respiratoire <i class="fas fa-lungs" style="color: #8A2BE2;"></i>) et le <span class="inline-code">Diagnostic</span> (<i class="fas fa-diagnoses" style="color: #6A5ACD;"></i>) du médecin, ainsi que des commentaires généraux (<i class="fas fa-comment-medical" style="color: #17A2B8;"></i>).</li>
                                <li><strong>Onglet "Médicaments"</strong> (<i class="fas fa-pills" style="color: #4CAF50;"></i>) : Permet d'ajouter les médicaments prescrits à partir d'une liste personnalisable (gérée par l'admin), ou d'en saisir de nouveaux. Utilisez le bouton "<span class="inline-code">Ajouter</span>" (<i class="fas fa-plus-circle" style="color: #6c757d;"></i>) et "<span class="inline-code">Supprimer Sélection</span>" (<i class="fas fa-trash-alt" style="color: #6c757d;"></i>).</li>
                                <li><strong>Onglet "Biologie"</strong> (<i class="fas fa-dna" style="color: #DA70D6;"></i>) : Pour les analyses biologiques demandées, avec la même logique de liste personnalisable d'ajout/suppression.</li>
                                <li><strong>Onglet "Radiologies"</strong> (<i class="fas fa-x-ray" style="color: #8A2BE2;"></i>) : Pour les radiologies prescrites, avec des options d'ajout/suppression similaires.</li>
                                <li><strong>Onglet "Certificat"</strong> (<i class="fas fa-file-medical" style="color: #FFD700;"></i>) : Pour générer divers types de certificats médicaux (maladie, bonne santé, sport, etc.). Choisissez une <span class="inline-code">Catégorie</span> (<i class="fas fa-tags" style="color: #FFD700;"></i>) pour pré-remplir le <span class="inline-code">Contenu</span> (<i class="fas fa-file-alt" style="color: #007BFF;"></i>), puis modifiez-le si nécessaire. Cochez "<span class="inline-code">Inclure le certificat</span>" (<i class="fas fa-check-circle" style="color: #28A745;"></i>) pour l'intégrer au PDF final.</li>
                                <li><strong>Onglet "Suivi"</strong> (<i class="fas fa-history" style="color: #FFC107;"></i>) : Affiche l'historique de toutes les consultations précédentes pour le patient sélectionné, permettant un suivi longitudinal de son état de santé. Les boutons "<span class="inline-code">Rafraîchir</span>" (<i class="fas fa-sync-alt" style="color: #6c757d;"></i>) et "<span class="inline-code">Historique Patient</span>" (<i class="fas fa-file-pdf" style="color: #28A745;"></i>) (pour générer un PDF complet des consultations du patient) sont disponibles.</li>
                            </ul>
                            <p>En bas de la page, des boutons d'action vous permettent de :</p>
                            <ul>
                                <li><span class="inline-code">Enregistrer</span> (<i class="fas fa-save" style="color: #6c757d;"></i>) : Sauvegarder toutes les informations de la consultation dans le système.</li>
                                <li><span class="inline-code">Réinitialiser</span> (<i class="fas fa-undo" style="color: #6c757d;"></i>) : Efface tous les champs du formulaire de la consultation actuelle.</li>
                                <li><span class="inline-code">Prescriptions PDF</span> (<i class="fas fa-file-pdf" style="color: #6c757d;"></i>) : Générer et télécharger un PDF incluant l'ordonnance, les demandes d'analyses/radiologies et le certificat (si inclus).</li>
                            </ul>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('index') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="consultation_iframe" src="{{ url_for('index', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                            <p class="alert alert-info"><strong>Rôle</strong> : Ce module est principalement utilisé par les Médecins.</p>
                        </div>
                        {% endif %}
                        
                        {% if 'gestion_patient' in allowed_pages %}
                        <div class="guide-section">
                            <h3><i class="fas fa-users me-2" style="color: #007BFF;"></i>6. Module Patients</h3>
                            <p>Ce module, accessible via l'icône <i class="fas fa-users" style="color: #007BFF;"></i> sur le tableau de bord, centralise la gestion de votre base de données patients.</p>
                            <h4><i class="fas fa-desktop me-2" style="color: #007BFF;"></i>Page Principale : Liste et Gestion des Patients</h4>
                            <p>La page est divisée en deux onglets principaux pour une gestion claire :</p>
                            <ul>
                                <li><strong>Onglet "Ajouter Patient"</strong> (<i class="fas fa-user-plus" style="color: #28A745;"></i>) : Un formulaire dédié pour enregistrer de nouveaux patients avec leurs informations démographiques et médicales :
                                    <ul>
                                        <li><span class="inline-code">ID Patient</span> (<i class="fas fa-id-card" style="color: #6C757D;"></i>) : Un identifiant unique pour le patient (ex: numéro de CIN).</li>
                                        <li><span class="inline-code">Nom</span> (<i class="fas fa-user" style="color: #007BFF;"></i>) & <span class="inline-code">Prénom</span> (<i class="fas fa-user-tag" style="color: #17A2B8;"></i>) : Informations d'identité du patient.</li>
                                        <li><span class="inline-code">Date de Naissance</span> (<i class="fas fa-calendar-alt" style="color: #FFB6C1;"></i>) : Importante pour le calcul automatique de l'âge.</li>
                                        <li><span class="inline-code">Sexe</span> (<i class="fas fa-venus-mars" style="color: #6A5ACD;"></i>) : Masculin, Féminin, Autre.</li>
                                        <li><span class="inline-code">Téléphone</span> (<i class="fas fa-phone" style="color: #28A745;"></i>) : Numéro de contact du patient.</li>
                                        <li><span class="inline-code">Antécédents Médicaux</span> (<i class="fas fa-file-medical" style="color: #DA70D6;"></i>) : Informations importantes sur l'historique médical du patient.</li>
                                        <li><strong>Bouton "Ajouter Patient"</strong> (<i class="fas fa-plus-circle" style="color: #6c757d;"></i>) : Pour enregistrer le nouveau patient.</li>
                                    </ul>
                                </li>
                                <li><strong>Onglet "Liste des Patients"</strong> (<i class="fas fa-list" style="color: #007BFF;"></i>) : Un tableau interactif affichant tous les patients enregistrés. Pour chaque patient listé, vous pouvez effectuer les actions suivantes :
                                    <ul>
                                        <li><strong>Bouton "Modifier"</strong> (<i class="fas fa-edit" style="color: #FFC107;"></i>) : Pour ouvrir un formulaire de modification et mettre à jour les informations d'un patient existant.</li>
                                        <li><strong>Bouton "Supprimer"</strong> (<i class="fas fa-trash" style="color: #DC3545;"></i>) : Pour retirer définitivement un patient de la base de données.</li>
                                        <li><strong>Bouton "Générer Badge"</strong> (<i class="fas fa-id-badge" style="color: #17A2B8;"></i>) : Crée un badge d'identification au format PDF pour le patient, incluant ses informations clés et un QR code.</li>
                                        <li><strong>Bouton "Envoyer message WhatsApp"</strong> (<i class="fab fa-whatsapp" style="color: #25D366;"></i>) : Ouvre une conversation WhatsApp pré-remplie pour contacter le patient rapidement.</li>
                                        <li><strong>Bouton "Nouvelle Consultation"</strong> (<i class="fas fa-stethoscope" style="color: #20B2AA;"></i>) : Prépare et pré-remplit un nouveau formulaire de consultation avec les données de ce patient, vous faisant gagner du temps.</li>
                                    </ul>
                                </li>
                                <li>Un bouton <span class="inline-code">Générer Tous les Badges</span> (<i class="fas fa-file-pdf" style="color: #DC3545;"></i>) est également disponible pour créer un seul fichier PDF contenant les badges de tous vos patients.</li>
                            </ul>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('gestion_patient.home_gestion_patient') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="patients_iframe" src="{{ url_for('gestion_patient.home_gestion_patient', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                            <p class="alert alert-info"><strong>Rôles</strong> : Ce module est essentiel pour l'Admin, l'Assistante et le Médecin.</p>
                        </div>
                        {% endif %}

                        {% if 'facturation' in allowed_pages %}
                        <div class="guide-section">
                            <h3><i class="fas fa-file-invoice-dollar me-2" style="color: #FFD700;"></i>7. Module Facturation</h3>
                            <p>Le module Facturation, accessible via l'icône <i class="fas fa-file-invoice-dollar" style="color: #FFD700;"></i> sur le tableau de bord, gère l'aspect financier des services fournis par votre clinique.</p>
                            <h4><i class="fas fa-desktop me-2" style="color: #007BFF;"></i>Page Principale : Gestion Financière</h4>
                            <p>La page est divisée en plusieurs onglets pour une gestion financière complète :</p>
                            <ul>
                                <li><strong>Onglet "Facturation"</strong> (<i class="fas fa-file-invoice-dollar" style="color: #FFD700;"></i>) : Pour <strong>Générer une facture</strong>.
                                    <ul>
                                        <li>Sélectionnez un <strong>ID Patient</strong> (<i class="fas fa-user-injured" style="color: #007BFF;"></i>) pour pré-remplir ses informations.</li>
                                        <li>Ajoutez des <strong>Services</strong> (<i class="fas fa-cubes" style="color: #8A2BE2;"></i>) à la facture, soit en les sélectionnant dans une liste, soit en saisissant de nouveaux services avec leur prix.</li>
                                        <li>Le système calcule automatiquement le Sous-total HT, la TVA et le Total TTC.</li>
                                        <li>Cliquez sur <strong>"Générer la facture"</strong> (<i class="fas fa-receipt" style="color: #6c757d;"></i>) pour créer le document PDF et l'enregistrer.</li>
                                    </ul>
                                </li>
                                <li><strong>Onglet "Enregistrer un Paiement"</strong> (<i class="fas fa-money-check-alt" style="color: #28A745;"></i>) : Pour enregistrer les paiements reçus.
                                    <ul>
                                        <li>Saisissez la <strong>Date du Paiement</strong> (<i class="fas fa-calendar-alt" style="color: #FFB6C1;"></i>), le <strong>Montant</strong> (<i class="fas fa-money-bill-wave" style="color: #28A745;"></i>) et le <strong>Mode de Paiement</strong> (<i class="fas fa-wallet" style="color: #FFD700;"></i>).</li>
                                        <li>Vous pouvez lier le paiement à un <strong>Numéro de Facture</strong> (<i class="fas fa-file-invoice" style="color: #007BFF;"></i>) existant et marquer la facture comme "Payée".</li>
                                        <li>Possibilité de <strong>Joindre une preuve de paiement</strong> (<i class="fas fa-paperclip" style="color: #6C757D;"></i>) (image ou PDF).</li>
                                        <li>Cliquez sur <strong>"Enregistrer Paiement"</strong> (<i class="fas fa-save" style="color: #6c757d;"></i>) ou <strong>"Générer Reçu"</strong> (<i class="fas fa-receipt" style="color: #28A745;"></i>) pour créer un reçu PDF.</li>
                                    </ul>
                                </li>
                                <li><strong>Onglet "Rapport global"</strong> (<i class="fas fa-chart-line" style="color: #4CAF50;"></i>) : Offre un aperçu financier avec des indicateurs clés (total des factures, chiffre d'affaires total TTC, total HT, total TVA, moyenne par facture). Vous pouvez filtrer ce rapport par <strong>période</strong> (date de début/fin).</li>
                                <li><strong>Onglet "Paiements antérieurs" (Historique)</strong> (<i class="fas fa-history" style="color: #FFC107;"></i>) : Une liste complète de toutes les factures émises et des paiements enregistrés. Pour chaque entrée, vous pouvez :
                                    <ul>
                                        <li><strong>"Télécharger Facture"</strong> (<i class="fas fa-download" style="color: #007BFF;"></i>) : Télécharger le PDF de la facture.</li>
                                        <li><strong>"Générer Reçu"</strong> (<i class="fas fa-receipt" style="color: #28A745;"></i>) : Générer un reçu pour cette facture (si elle est marquée comme payée).</li>
                                        <li><strong>"Télécharger Preuve"</strong> (<i class="fas fa-file-image" style="color: #17A2B8;"></i>) : Télécharger la preuve de paiement jointe.</li>
                                        <li><strong>"Supprimer"</strong> (<i class="fas fa-trash" style="color: #DC3545;"></i>) : Supprimer une facture et ses paiements associés.</li>
                                    </ul>
                                </li>
                            </ul>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('facturation.home_facturation') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="facturation_iframe" src="{{ url_for('facturation.home_facturation', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                            <p class="alert alert-info"><strong>Rôles</strong> : Ce module est essentiel pour l'Admin, le Comptable et l'Assistante.</p>
                        </div>
                        {% endif %}

                        {% if 'biologie' in allowed_pages %}
                        <div class="guide-section">
                            <h3><i class="fas fa-flask me-2" style="color: #DA70D6;"></i>8. Module Biologie</h3>
                            <p>Accessible via l'icône <i class="fas fa-flask" style="color: #DA70D6;"></i> sur le tableau de bord, ce module est dédié à la gestion des analyses biologiques des patients.</p>
                            <h4><i class="fas fa-desktop me-2" style="color: #007BFF;"></i>Page Principale : Gestion des Analyses Biologiques</h4>
                            <p>Cette page vous permet de saisir de nouvelles analyses et de consulter l'historique complet, organisée en deux onglets :</p>
                            <ul>
                                <li><strong>Onglet "Nouvelle Analyse"</strong> (<i class="fas fa-plus-circle" style="color: #4CAF50;"></i>) : Pour <strong>Saisir une nouvelle analyse</strong>.
                                    <ul>
                                        <li>Saisissez l'<strong>ID Patient</strong> (<i class="fas fa-id-card" style="color: #6C757D;"></i>) pour auto-remplir ses informations et afficher les analyses déjà prescrites.</li>
                                        <li>Entrez le <strong>Nom de l'analyse</strong> (<i class="fas fa-flask" style="color: #DA70D6;"></i>) et la <strong>Conclusion du biologiste</strong> (<i class="fas fa-microscope" style="color: #20B2AA;"></i>).</li>
                                        <li>Le bouton <strong>"Ajouter une autre analyse"</strong> (<i class="fas fa-plus" style="color: #28A745;"></i>) vous permet d'ajouter plusieurs analyses pour le même patient en une seule fois.</li>
                                        <li>Vous pouvez <strong>"Importer le résultat PDF"</strong> (<i class="fas fa-file-pdf" style="color: #DC3545;"></i>) du laboratoire.</li>
                                        <li>Cliquez sur <strong>"Enregistrer l'analyse(s)"</strong> (<i class="fas fa-save" style="color: #6c757d;"></i>) pour sauvegarder. Les conclusions sont automatiquement ajoutées au commentaire du médecin dans le dossier de consultation du patient.</li>
                                    </ul>
                                </li>
                                <li><strong>Onglet "Historique Analyses"</strong> (<i class="fas fa-history" style="color: #FFC107;"></i>) : Affiche un tableau listant toutes les analyses saisies.
                                    <ul>
                                        <li>Pour chaque analyse, vous pouvez <strong>"Télécharger"</strong> (<i class="fas fa-download" style="color: #007BFF;"></i>) le fichier PDF du résultat si disponible.</li>
                                        <li>Un bouton <strong>"Exporter l'historique"</strong> (<i class="fas fa-download" style="color: #007BFF;"></i>) permet de télécharger toutes les analyses dans un fichier Excel unique.</li>
                                    </ul>
                                </li>
                            </ul>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('biologie.home_biologie') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="biologie_iframe" src="{{ url_for('biologie.home_biologie', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                            <p class="alert alert-info"><strong>Rôles</strong> : Ce module est généralement utilisé par le Biologiste, le Médecin et l'Admin.</p>
                        </div>
                        {% endif %}
                        
                        {% if 'radiologie' in allowed_pages %}
                        <div class="guide-section">
                            <h3><i class="fas fa-x-ray me-2" style="color: #8A2BE2;"></i>9. Module Radiologie</h3>
                            <p>Le module Radiologie, accessible via l'icône <i class="fas fa-x-ray" style="color: #8A2BE2;"></i> sur le tableau de bord, est spécifiquement conçu pour la gestion des analyses radiologiques.</p>
                            <h4><i class="fas fa-desktop me-2" style="color: #007BFF;"></i>Page Principale : Gestion des Analyses Radiologiques</h4>
                            <p>Similaire au module Biologie, cette page offre des fonctionnalités pour l'enregistrement et le suivi des radiologies, organisée en deux onglets :</p>
                            <ul>
                                <li><strong>Onglet "Nouvelle Radiologie"</strong> (<i class="fas fa-plus-circle" style="color: #4CAF50;"></i>) : Pour <strong>Saisir une nouvelle radiologie</strong>.
                                    <ul>
                                        <li>Saisissez l'<strong>ID Patient</strong> (<i class="fas fa-id-card" style="color: #6C757D;"></i>) pour auto-remplir ses informations et afficher les radiologies déjà prescrites.</li>
                                        <li>Entrez le <strong>Nom de la radiologie</strong> (<i class="fas fa-x-ray" style="color: #8A2BE2;"></i>) et la <strong>Conclusion du radiologue</strong> (<i class="fas fa-diagnoses" style="color: #6A5ACD;"></i>).</li>
                                        <li>Le bouton <strong>"Ajouter une autre radiologie"</strong> (<i class="fas fa-plus" style="color: #28A745;"></i>) vous permet d'ajouter plusieurs radiologies pour le même patient en une seule fois.</li>
                                        <li>Vous pouvez <strong>"Importer le résultat PDF"</strong> (<i class="fas fa-file-pdf" style="color: #DC3545;"></i>) du laboratoire.</li>
                                        <li>Cliquez sur <strong>"Enregistrer la radiologie(s)"</strong> (<i class="fas fa-save" style="color: #6c757d;"></i>) pour sauvegarder. Les conclusions sont également intégrées au commentaire du médecin dans le dossier du patient.</li>
                                    </ul>
                                </li>
                                <li><strong>Onglet "Historique Radiologies"</strong> (<i class="fas fa-history" style="color: #FFC107;"></i>) : Affiche un tableau listant toutes les radiologies saisies.
                                    <ul>
                                        <li>Pour chaque radiologie, vous pouvez <strong>"Télécharger"</strong> (<i class="fas fa-download" style="color: #007BFF;"></i>) le fichier PDF du résultat si disponible.</li>
                                        <li>Un bouton <strong>"Exporter l'historique"</strong> (<i class="fas fa-download" style="color: #007BFF;"></i>) permet de télécharger toutes les radiologies dans un fichier Excel unique.</li>
                                    </ul>
                                </li>
                            </ul>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('radiologie.home_radiologie') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="radiologie_iframe" src="{{ url_for('radiologie.home_radiologie', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                            <p class="alert alert-info"><strong>Rôles</strong> : Ce module est principalement utilisé par le Radiologue, le Médecin et l'Admin.</p>
                        </div>
                        {% endif %}

                        {% if 'pharmacie' in allowed_pages %}
                        <div class="guide-section">
                            <h3><i class="fas fa-prescription-bottle-alt me-2" style="color: #FF9800;"></i>10. Module Pharmacie & Stock</h3>
                            <p>Accessible via l'icône <i class="fas fa-prescription-bottle-alt" style="color: #FF9800;"></i> sur le tableau de bord, ce module est essentiel pour le suivi de l'inventaire des produits pharmaceutiques et parapharmaceutiques de votre clinique.</p>
                            <h4><i class="fas fa-desktop me-2" style="color: #007BFF;"></i>Page Principale : Gestion du Stock</h4>
                            <p>Cette page est divisée en plusieurs onglets pour une gestion complète du stock :</p>
                            <ul>
                                <li><strong>Onglet "Aperçu"</strong> (<i class="fas fa-chart-pie" style="color: #17A2B8;"></i>) : Un tableau de bord rapide affichant :
                                    <ul>
                                        <li>Le <strong>Total Produits</strong> (<i class="fas fa-box-open" style="color: #4682B4;"></i>) : Nombre total d'articles dans votre inventaire.</li>
                                        <li>Les <strong>Alertes Stock Bas</strong> (<i class="fas fa-exclamation-triangle" style="color: #FF4500;"></i>) : Nombre de produits dont la quantité est inférieure au seuil d'alerte.</li>
                                        <li>Les <strong>Produits Expirés</strong> (<i class="fas fa-calendar-times" style="color: #DC3545;"></i>) : Liste des articles dont la date de péremption est dépassée.</li>
                                        <li>Les <strong>Derniers Mouvements</strong> (<i class="fas fa-history" style="color: #8A2BE2;"></i>) : Un aperçu des 10 dernières entrées ou sorties de stock.</li>
                                    </ul>
                                </li>
                                <li><strong>Onglet "Inventaire"</strong> (<i class="fas fa-boxes" style="color: #007BFF;"></i>) : La liste complète de tous les produits en stock, avec leurs détails (code, nom, quantité, prix d'achat/vente, fournisseur, date d'expiration, seuil d'alerte, date d'enregistrement) et leur statut (En Stock, Stock Bas, Rupture).
                                    <ul>
                                        <li><strong>Bouton "Supprimer"</strong> (<i class="fas fa-trash" style="color: #DC3545;"></i>) : Pour retirer un produit de l'inventaire.</li>
                                        <li><strong>Boutons "Exporter PDF"</strong> (<i class="fas fa-file-pdf" style="color: #DC3545;"></i>) et <strong>"Exporter Excel"</strong> (<i class="fas fa-file-excel" style="color: #28A745;"></i>) pour l'inventaire.</li>
                                    </ul>
                                </li>
                                <li><strong>Onglet "Mouvements"</strong> (<i class="fas fa-exchange-alt" style="color: #FFC107;"></i>) : Pour enregistrer les entrées (achats) et sorties (ventes/consommation) de produits.
                                    <ul>
                                        <li>Sélectionnez le <strong>Produit</strong> (<i class="fas fa-pills" style="color: #6A5ACD;"></i>), le <strong>Type de Mouvement</strong> (<i class="fas fa-sign-in-alt" style="color: #20B2AA;"></i>) et la <strong>Quantité</strong> (<i class="fas fa-sort-numeric-up-alt" style="color: #FF8C00;"></i>).</li>
                                        <li>Indiquez les <strong>Détails du Responsable</strong> (<i class="fas fa-user-circle" style="color: #6c757d;"></i>) : Nom, Prénom et Téléphone de la personne effectuant le mouvement.</li>
                                        <li>Le bouton <strong>"Enregistrer le mouvement"</strong> (<i class="fas fa-save" style="color: #6c757d;"></i>) valide l'opération.</li>
                                        <li>Un tableau <strong>"Historique des Mouvements"</strong> suit toutes les entrées et sorties.</li>
                                        <li><strong>Boutons "Exporter PDF"</strong> (<i class="fas fa-file-pdf" style="color: #DC3545;"></i>) et <strong>"Exporter Excel"</strong> (<i class="fas fa-file-excel" style="color: #28A745;"></i>) pour l'historique des mouvements.</li>
                                    </ul>
                                </li>
                                <li><strong>Onglet "Ajouter Produit"</strong> (<i class="fas fa-plus-circle" style="color: #28A745;"></i>) : Un formulaire pour ajouter de nouveaux produits à votre inventaire ou modifier les produits existants.
                                    <ul>
                                        <li>Saisissez le <strong>Code Produit</strong> (<i class="fas fa-qrcode" style="color: #6C757D;"></i>), <strong>Nom du Produit</strong> (<i class="fas fa-pills" style="color: #4CAF50;"></i>), <strong>Type</strong> (<i class="fas fa-tag" style="color: #DAA520;"></i>) & <strong>Usage</strong> (<i class="fas fa-hand-paper" style="color: #6A5ACD;"></i>), <strong>Quantité</strong> (<i class="fas fa-boxes" style="color: #4682B4;"></i>).</li>
                                        <li>Indiquez les <strong>Prix d'Achat</strong> (<i class="fas fa-coins" style="color: #FFD700;"></i>) & <strong>de Vente</strong> (<i class="fas fa-hand-holding-usd" style="color: #28A745;"></i>), le <strong>Fournisseur</strong> (<i class="fas fa-truck-moving" style="color: #DC143C;"></i>), la <strong>Date d'Expiration</strong> (<i class="fas fa-calendar-times" style="color: #FF4500;"></i>) et le <strong>Seuil d'Alerte</strong> (<i class="fas fa-bell" style="color: #FFC107;"></i>).</li>
                                        <li>Les achats sont automatiquement enregistrés comme des dépenses dans la comptabilité.</li>
                                    </ul>
                                </li>
                            </ul>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('pharmacie.home_pharmacie') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="pharmacie_iframe" src="{{ url_for('pharmacie.home_pharmacie', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                            <p class="alert alert-info"><strong>Rôles</strong> : Ce module est principalement utilisé par le personnel de la Pharmacie/Magasin et l'Admin.</p>
                        </div>
                        {% endif %}

                        {% if 'comptabilite' in allowed_pages %}
                        <div class="guide-section">
                            <h3><i class="fas fa-calculator me-2" style="color: #00BCD4;"></i>11. Module Comptabilité</h3>
                            <p>Le module Comptabilité, accessible via l'icône <i class="fas fa-calculator" style="color: #00BCD4;"></i> sur le tableau de bord, vous permet de gérer et de suivre toutes les opérations financières de votre clinique.</p>
                            <h4><i class="fas fa-desktop me-2" style="color: #007BFF;"></i>Page Principale : Tableau de Bord Financier</h4>
                            <p>Cette page est organisée en plusieurs onglets pour un suivi financier détaillé :</p>
                            <ul>
                                <li><strong>Onglet "Tableau de Bord"</strong> (<i class="fas fa-chart-line" style="color: #4CAF50;"></i>) : Un aperçu financier avec les indicateurs clés (recettes totales, dépenses totales, bénéfice net) et des graphiques de tendance mensuelle (recettes, dépenses, bénéfice net), répartition des recettes par type d'acte, et répartition des dépenses par catégorie. Un filtre par mois est disponible.</li>
                                <li><strong>Onglet "Recettes"</strong> (<i class="fas fa-money-bill-wave" style="color: #28A745;"></i>) : Pour enregistrer toutes les entrées d'argent, en les liant optionnellement à un patient ou à une facture.</li>
                                <li><strong>Onglet "Dépenses"</strong> (<i class="fas fa-money-check-alt" style="color: #DC1435;"></i>) : Pour enregistrer toutes les sorties d'argent, avec une catégorisation et la possibilité de joindre des justificatifs (factures, reçus).</li>
                                <li><strong>Onglet "Salaires & Paie"</strong> (<i class="fas fa-users-cog" style="color: #673AB7;"></i>) : Pour enregistrer les salaires des employés, calculer les totaux (net, charges, brut) et générer des fiches de paie au format PDF. Des fonctions d'import/export Excel sont également disponibles.</li>
                                <li><strong>Onglet "Tiers Payants / Assurances"</strong> (<i class="fas fa-handshake" style="color: #20B2AA;"></i>) : Pour suivre les montants attendus et reçus des organismes d'assurance ou mutuelles, avec gestion du statut de règlement.</li>
                                <li><strong>Onglet "Documents Fiscaux"</strong> (<i class="fas fa-file-alt" style="color: #FF5722;"></i>) : Une section pour archiver et accéder facilement à tous vos documents fiscaux importants (déclarations, bilans, etc.) au format PDF.</li>
                                <li><strong>Onglet "Rapports"</strong> (<i class="fas fa-chart-area" style="color: #FF9800;"></i>) : Pour générer des rapports financiers personnalisés (revenus/dépenses) sur une période donnée et les exporter en Excel.</li>
                                </ul>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('comptabilite.home_comptabilite') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="comptabilite_iframe" src="{{ url_for('comptabilite.home_comptabilite', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                            <p class="alert alert-info"><strong>Rôles</strong> : Ce module est principalement utilisé par le Comptable et l'Admin.</p>
                        </div>
                        {% endif %}

                        {% if 'statistique' in allowed_pages %}
                        <div class="guide-section">
                            <h3><i class="fas fa-chart-pie me-2" style="color: #4CAF50;"></i>12. Module Statistiques</h3>
                            <p>Le module Statistiques, accessible via l'icône <i class="fas fa-chart-pie" style="color: #4CAF50;"></i> sur le tableau de bord, offre une analyse approfondie des performances de votre clinique à travers des indicateurs clés et des visualisations graphiques.</p>
                            <h4><i class="fas fa-desktop me-2" style="color: #007BFF;"></i>Page Principale : Tableau de Bord Statistique</h4>
                            <p>Cette page présente un aperçu dynamique de l'activité de votre clinique. Elle inclut :</p>
                            <ul>
                                <li><strong>Filtres de Données</strong> : Vous pouvez filtrer les données affichées par une période spécifique (dates de début et de fin) et par médecin, pour des analyses ciblées. Vous pouvez également choisir quels graphiques vous souhaitez afficher.</li>
                                <li><strong>Indicateurs Clés de Performance (KPIs)</strong> : Des chiffres récapitulatifs pour les métriques les plus importantes, telles que le nombre total de factures, de patients uniques, de rendez-vous, la valeur du stock, le total des recettes, le total des dépenses et le bénéfice net.</li>
                                <li><strong>Graphiques Dynamiques</strong> : Une série de graphiques (à barres et circulaires) illustrant diverses facettes de votre activité :
                                    <ul>
                                        <li>Consultations mensuelles</li>
                                        <li>Total des recettes mensuel</li>
                                        <li>Répartition des patients par sexe et par tranches d'âge</li>
                                        <li>Salaires mensuels</li>
                                        <li>Nombre de rendez-vous par médecin</li>
                                        <li>Dépenses par catégorie</li>
                                        <li>Recettes par type d'acte</li>
                                        <li>Top 10 des produits en stock</li>
                                        <li>Types de mouvements de stock</li>
                                    </ul>
                                </li>
                            </ul>
                            <p class="alert alert-success">Chaque graphique est accompagné d'une brève analyse textuelle pour vous aider à interpréter rapidement les tendances et les répartitions.</p>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('statistique.stats_home') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="statistiques_iframe" src="{{ url_for('statistique.stats_home', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                            <p class="alert alert-info"><strong>Rôles</strong> : Ce module est principalement utilisé par l'Admin et le Médecin pour le suivi et l'analyse stratégique.</p>
                        </div>
                        {% endif %}

                        {% if 'ia_assitant' in allowed_pages %}
                        <div class="guide-section">
                            <h3><i class="fas fa-robot me-2" style="color: #6f42c1;"></i>13. Module Assistant IA (Synapse)</h3>
                            <p>Accessible via l'icône <i class="fas fa-robot" style="color: #6f42c1;"></i> sur le tableau de bord, Synapse est votre assistant médical intelligent. Il est conçu pour assister les professionnels de la santé en répondant à des questions complexes, en analysant des documents et en fournissant des informations factuelles basées sur les dernières données médicales.</p>
                            <p class="alert alert-warning"><strong>Important</strong> : L'assistant Synapse est programmé pour répondre <strong>uniquement</strong> aux questions relatives aux domaines de la médecine, santé, biologie, pharmacologie et radiologie. Toute question hors de ce cadre sera poliment déclinée.</p>
                            <h4><i class="fas fa-desktop me-2" style="color: #007BFF;"></i>Page Principale : Interface de Chat Intelligente</h4>
                            <p>L'interface de l'assistant est conçue pour être intuitive et efficace, centrée autour d'une conversation fluide.</p>
                            <ul>
                                <li><strong>Barre Latérale des Conversations</strong> (<i class="fas fa-history" style="color: #FFC107;"></i>) : Sur la gauche, vous trouverez l'historique de vos conversations. Vous pouvez démarrer une <strong>"Nouvelle Discussion"</strong> (<i class="fas fa-plus-circle" style="color: #4CAF50;"></i>), naviguer entre les anciennes conversations ou les <strong>supprimer</strong> (<i class="fas fa-trash" style="color: #DC3545;"></i>).</li>
                                <li><strong>Fenêtre de Chat Principale</strong> (<i class="fas fa-comments" style="color: #007BFF;"></i>) : Affiche le dialogue entre vous (l'utilisateur) et Synapse (l'IA). Les réponses de l'IA sont formatées pour une lecture facile et peuvent être <strong>copiées</strong> (<i class="fas fa-copy" style="color: #17A2B8;"></i>) en un clic.</li>
                                <li><strong>Zone de Saisie</strong> (<i class="fas fa-keyboard" style="color: #6C757D;"></i>) : En bas de la page, vous pouvez taper votre question, <strong>joindre des fichiers</strong> (<i class="fas fa-paperclip" style="color: #FF9800;"></i>) comme des rapports PDF, des feuilles de calcul Excel ou des images, puis envoyer votre requête à l'assistant.</li>
                            </ul>
                            <div class="iframe-actions text-center mb-2">
                                <button class="btn btn-sm btn-outline-secondary" onclick="window.open('{{ url_for('ia_assitant.home_ia_assitant') }}', '_blank')">Ouvrir dans un nouvel onglet</button>
                            </div>
                            <div class="guide-iframe-container">
                                <div class="iframe-loading-message">Chargement de la page...</div>
                                <iframe id="ia_assistant_iframe" src="{{ url_for('ia_assitant.home_ia_assitant', iframe_mode='true') }}" loading="lazy" onload="this.previousElementSibling.style.display='none';" onerror="this.previousElementSibling.style.display='none'; this.style.display='none'; Swal.fire({ icon: 'error', title: 'Erreur de chargement', text: 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', confirmButtonText: 'OK' });"></iframe>
                            </div>
                            <p class="alert alert-info"><strong>Rôles</strong> : Ce module avancé est accessible aux rôles <strong>Admin</strong> et <strong>Médecin</strong>.</p>
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <footer class="text-center py-1 small">
        <div class="card-footer text-center py-1">
            <div style="margin-bottom: 0 !important;">
                <p class="small mb-1" style="color: white;">
                    <i class="fas fa-heartbeat me-1"></i>
                    SASTOUKA DIGITAL © 2025 • sastoukadigital@gmail.com tel +212652084735
                </p>
            </div>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const guideContent = document.getElementById('guide-content');
            const searchInput = document.getElementById('searchInput');
            const searchButton = document.getElementById('searchButton');
            const clearSearchButton = document.getElementById('clearSearchButton');
            const prevResultButton = document.getElementById('prevResultButton');
            const nextResultButton = document.getElementById('nextResultButton');

            let currentHighlights = []; // Stores all highlighted elements
            let currentHighlightIndex = -1; // Index of the currently focused highlight

            // Function to remove all highlights
            function removeHighlights() {
                currentHighlights.forEach(span => {
                    // Replace the span with its text content
                    span.parentNode.replaceChild(document.createTextNode(span.textContent), span);
                });
                currentHighlights = [];
                currentHighlightIndex = -1;
                // Hide navigation buttons
                // Check if buttons exist before trying to access their style property
                if (prevResultButton) prevResultButton.style.display = 'none';
                if (nextResultButton) nextResultButton.style.display = 'none';
            }

            // Function to perform search and highlight
            function performSearch() {
                removeHighlights(); // Clear previous highlights
                const searchTerm = searchInput.value.trim();

                if (searchTerm === '') {
                    return;
                }

                const regex = new RegExp(`(${searchTerm})`, 'gi'); // Case-insensitive, global

                // Create a temporary div to hold the content for safe manipulation
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = guideContent.innerHTML; // Copy current content

                // Iterate over text nodes to avoid breaking HTML structure
                const walker = document.createTreeWalker(tempDiv, NodeFilter.SHOW_TEXT, null, false);
                let node;
                const textNodesToProcess = [];

                while (node = walker.nextNode()) {
                    // Avoid processing script, style, and already highlighted nodes
                    if (node.parentNode.nodeName !== 'SCRIPT' && node.parentNode.nodeName !== 'STYLE' && !node.parentNode.classList.contains('highlight')) {
                        textNodesToProcess.push(node);
                    }
                }

                textNodesToProcess.forEach(node => {
                    const parent = node.parentNode;
                    const text = node.nodeValue;
                    if (text && regex.test(text)) {
                        const fragment = document.createDocumentFragment();
                        let lastIndex = 0;
                        text.replace(regex, (match, p1, offset) => {
                            // Add text before the match
                            if (offset > lastIndex) {
                                fragment.appendChild(document.createTextNode(text.substring(lastIndex, offset)));
                            }
                            // Add the highlighted span
                            const span = document.createElement('span');
                            span.className = 'highlight'; // Add highlight class
                            span.textContent = match;
                            fragment.appendChild(span);
                            lastIndex = offset + match.length;
                            return match; // Return match for replace function
                        });
                        // Add any remaining text after the last match
                        if (lastIndex < text.length) {
                            fragment.appendChild(document.createTextNode(text.substring(lastIndex)));
                        }
                        parent.replaceChild(fragment, node);
                    }
                });

                // Replace the original content with the modified content
                guideContent.innerHTML = tempDiv.innerHTML;

                // Collect all new highlight elements
                currentHighlights = Array.from(guideContent.querySelectorAll('.highlight'));

                if (currentHighlights.length > 0) {
                    currentHighlightIndex = 0;
                    scrollToHighlight(currentHighlightIndex);
                    // Show navigation buttons
                    if (prevResultButton) prevResultButton.style.display = 'inline-flex';
                    if (nextResultButton) nextResultButton.style.display = 'inline-flex';
                } else {
                    // Use custom modal for alerts
                    showCustomAlert('Aucun résultat', 'Aucune occurrence trouvée pour votre recherche.', 'info', 2000);
                }
            }

            // Function to scroll to a specific highlight
            function scrollToHighlight(index) {
                if (currentHighlights.length === 0) return;

                // Remove 'active' class from previous highlight
                if (currentHighlightIndex >= 0 && currentHighlightIndex < currentHighlights.length) {
                    currentHighlights[currentHighlightIndex].classList.remove('active');
                }

                // Set new active highlight
                currentHighlightIndex = index;
                const activeHighlight = currentHighlights[currentHighlightIndex];
                activeHighlight.classList.add('active'); // Add 'active' class for different styling

                // Scroll to the active highlight
                activeHighlight.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }

            // Custom alert function
            function showCustomAlert(title, message, icon, timer = 0) {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: icon,
                        title: title,
                        text: message,
                        timer: timer,
                        showConfirmButton: timer === 0 // Show confirm button only if no timer
                    });
                } else {
                    alert(`${title}: ${message}`);
                }
            }


            // Event Listeners for search
            if (searchButton) searchButton.addEventListener('click', performSearch);
            if (searchInput) {
                searchInput.addEventListener('keydown', function(event) {
                    if (event.key === 'Enter') {
                        performSearch();
                    }
                });
            }
            if (clearSearchButton) {
                clearSearchButton.addEventListener('click', function() {
                    searchInput.value = '';
                    removeHighlights();
                });
            }

            // Navigation buttons for search results
            if (prevResultButton) {
                prevResultButton.addEventListener('click', () => {
                    if (currentHighlights.length === 0) return;
                    let newIndex = currentHighlightIndex - 1;
                    if (newIndex < 0) {
                        newIndex = currentHighlights.length - 1; // Wrap around to the last
                    }
                    scrollToHighlight(newIndex);
                });
            }

            if (nextResultButton) {
                nextResultButton.addEventListener('click', () => {
                    if (currentHighlights.length === 0) return;
                    let newIndex = currentHighlightIndex + 1;
                    if (newIndex >= currentHighlights.length) {
                        newIndex = 0; // Wrap around to the first
                    }
                    scrollToHighlight(newIndex);
                });
            }

            // Function to open iframe
            window.openIframe = function(iframeId, url) {
                const iframe = document.getElementById(iframeId);
                // Check if iframe and its previous sibling (loading message) exist
                if (!iframe || !iframe.previousElementSibling) {
                    console.error('Iframe or loading message not found for ID:', iframeId);
                    // Use custom alert instead of Swal.fire directly
                    showCustomAlert('Erreur de chargement', 'Élément iframe ou message de chargement introuvable.', 'error');
                    return;
                }

                const loadingMessage = iframe.previousElementSibling; // The div with loading message

                loadingMessage.style.display = 'flex'; // Show loading message
                iframe.style.display = 'none'; // Hide iframe until loaded
                iframe.src = url;
                iframe.onload = function() {
                    // Use a small delay to ensure rendering is complete before hiding loading message
                    setTimeout(() => {
                        loadingMessage.style.display = 'none'; // Hide loading message
                        iframe.style.display = 'block'; // Show iframe
                    }, 100); // 100ms delay
                };
                iframe.onerror = function() {
                    loadingMessage.style.display = 'none';
                    iframe.style.display = 'none';
                    // Use custom alert instead of Swal.fire directly
                    showCustomAlert('Erreur de chargement', 'Impossible de charger la page dans le guide. Veuillez vérifier que l\'application est en cours d\'exécution et accessible, ou utilisez le bouton \"Ouvrir dans un nouvel onglet\".', 'error');
                };
            };
        });
    </script>
</body>
</html>
"""

@guide_bp.route('/')
def guide_home():
    config = utils.load_config()
    theme_name_from_session = session.get('theme', theme.DEFAULT_THEME)
    
    logged_in_full_name = None 
    user_email = session.get('email')
    
    # Initialize allowed_pages
    allowed_pages = []

    # Vérifie si la requête provient d'une iframe du guide (via un paramètre d'URL spécifique)
    # ou si l'utilisateur est déjà connecté.
    # Si la requête vient d'une iframe ET n'est PAS déjà connectée, on simule une connexion admin par défaut.
    is_iframe_request = request.args.get('iframe_mode') == 'true'

    if is_iframe_request and 'email' not in session:
        # Simuler une session admin par défaut pour l'iframe
        session['email'] = "saja@gmail.com"
        session['role'] = "admin"
        session['admin_email'] = "saja@gmail.com"
        session.permanent = True
        print("DEBUG: Session admin 'saja@gmail.com' simulée pour l'iframe du guide.")
        # Recharger la configuration et les chemins avec le nouvel admin_email simulé
        utils.set_dynamic_base_dir(session['admin_email'])
        config = utils.load_config() # Recharger la config avec le contexte par défaut
        allowed_pages = login.ALL_BLUEPRINTS # Admin gets all blueprints
    
    elif user_email: # Si l'utilisateur est réellement connecté (pas seulement une simulation d'iframe)
        admin_email_from_session = session.get('admin_email') 
        temp_admin_email_for_utils_init = admin_email_from_session if admin_email_from_session else "default_admin@example.com"
        utils.set_dynamic_base_dir(temp_admin_email_for_utils_init)
        
        all_users_data = login.load_users()
        user_info = all_users_data.get(user_email)
        if user_info:
            logged_in_full_name = f"{user_info.get('prenom', '')} {user_info.get('nom', '')}".strip()
            if not logged_in_full_name:
                logged_in_full_name = None
            
            # Déterminer les pages autorisées en fonction du rôle
            if user_info.get('role') == 'admin':
                allowed_pages = login.ALL_BLUEPRINTS
            else:
                allowed_pages = user_info.get('allowed_pages', [])
                # S'assurer que 'accueil' et 'guide' sont toujours inclus si l'utilisateur y a accès
                if 'accueil' not in allowed_pages:
                    allowed_pages.append('accueil')
                if 'guide' not in allowed_pages:
                    allowed_pages.append('guide')

    else: # If not logged in and not in iframe mode, use a default admin_email for the guide
        utils.set_dynamic_base_dir("default_admin@example.com")
        config = utils.load_config() # Re-load config with default context
        # For a non-logged-in user accessing directly (not via iframe_mode),
        # they should only see public sections (login, register, activation, accueil, guide)
        # Ensure that these sections either have no 'if allowed_pages' conditions or that these blueprints
        # are always in allowed_pages by default.
        allowed_pages = ['login', 'register', 'activation', 'accueil', 'guide'] # Limit access for non-logged-in users

    return render_template_string(
        guide_template,
        config=config,
        theme_vars=theme.get_theme(theme_name_from_session),
        logged_in_doctor_name=logged_in_full_name,
        datetime=datetime,
        allowed_pages=allowed_pages # PASSER LA VARIABLE ALLOWED_PAGES AU TEMPLATE
    )