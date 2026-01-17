
# biologie.py
# Module pour la gestion des analyses biologiques
from flask import Blueprint, render_template_string, session, redirect, url_for, flash, request, jsonify, send_from_directory, send_file
from datetime import datetime
import utils
import theme
import pandas as pd
import os
import io
import login

biologie_bp = Blueprint('biologie', __name__, url_prefix='/biologie')

biologie_template = """
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Biologie – {{ config.nom_clinique or 'EasyMedicaLink' }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
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
        }
        footer a {
            color: white;
            text-decoration: none;
            transition: color 0.2s ease;
        }
        footer a:hover {
            color: var(--text-color-light);
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
        }
        /* Styles for navigation tabs (copied from main_template/facturation_template) */
        .nav-tabs {
            border-bottom: none;
            margin-bottom: 1rem;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 1rem;
        }
        .nav-tabs .nav-item {
            flex-grow: 1;
            text-align: center;
            flex-basis: auto;
            max-width: 250px;
        }
        .nav-tabs .nav-link {
            border: none;
            color: var(--text-color-light);
            font-weight: 500;
            font-size: 1.1rem;
            padding: 0.8rem 1.2rem;
            transition: all 0.2s ease;
            position: relative;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .nav-tabs .nav-link i {
            font-size: 1.2rem;
            margin-right: 0.25rem;
        }
        .nav-tabs .nav-link::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 0;
            height: 3px;
            background: var(--primary-color);
            transition: width 0.3s ease;
        }
        .nav-tabs .nav-link.active {
            background: transparent;
            color: var(--primary-color) !important;
        }
        .nav-tabs .nav-link.active::after {
            width: 100%;
        }
        /* Floating Labels (consistent with other pages) */
        .floating-label {
            position: relative;
            margin-bottom: 1rem;
        }
        .floating-label input,
        .floating-label select,
        .floating-label textarea {
            padding: 1rem 0.75rem 0.5rem;
            height: auto;
            border-radius: var(--border-radius-sm);
            border: 1px solid var(--secondary-color);
            background-color: var(--card-bg);
            color: var(--text-color);
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }
        .floating-label input:focus,
        .floating-label select:focus,
        .floating-label textarea:focus {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 0.25rem rgba(var(--primary-color-rgb), 0.25);
            background-color: var(--card-bg);
            color: var(--text-color);
        }
        .floating-label label {
            position: absolute;
            top: 0.75rem;
            left: 0.75rem;
            font-size: 1rem;
            color: var(--text-color-light);
            transition: all 0.2s ease;
            pointer-events: none;
        }
        .floating-label input:focus + label,
        .floating-label input:not(:placeholder-shown) + label,
        .floating-label select:focus + label,
        .floating-label select:not([value=""]) + label,
        .floating-label textarea:focus + label,
        .floating-label textarea:not(:placeholder-shown) + label {
            top: 0.25rem;
            left: 0.75rem;
            font-size: 0.75rem;
            color: var(--primary-color);
            background-color: var(--card-bg);
            padding: 0 0.25rem;
            transform: translateX(-0.25rem);
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
                <a href="{{ url_for('login.logout') }}" class="btn btn-outline-secondary flex-fill">
                    <i class="fas fa-sign-out-alt me-2" style="color: #DC143C;"></i>Déconnexion {# Crimson Sign-out Icon #}
                </a>
            </div>
        </div>
    </div>

    <div class="container-fluid my-4">
        {# Messages d'alerte #}
        {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
        <div class="alert-container">
            {% for category, message in messages %}
            <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                {{ message }}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
            {% endfor %}
        </div>
        {% endif %}
        {% endwith %}

        <div class="row justify-content-center">
            <div class="col-12">
                <div class="card shadow-lg">
                    <div class="card-header py-3 text-center">
                        <h1 class="mb-2 header-item">
                            <i class="fas fa-hospital me-2"></i> {# Hospital Icon (original color) #}
                            {{ config.nom_clinique or config.cabinet or 'NOM CLINIQUE/CABINET/CENTRE MEDICAL' }}
                        </h1>
                        <div class="d-flex justify-content-center gap-4 flex-wrap">
                            <div class="d-flex align-items-center header-item">
                                <i class="fas fa-user me-2"></i><span>{{ logged_in_doctor_name if logged_in_doctor_name and logged_in_doctor_name != 'None' else config.doctor_name or 'NOM MEDECIN' }}</span> {# Simple User Icon #}
                            </div>
                            <div class="d-flex align-items-center header-item">
                                <i class="fas fa-map-marker-alt me-2"></i><span>{{ config.location or 'LIEU' }}</span> {# Map Marker Icon (original color) #}
                            </div>
                        </div>
                        {# Déplacer la date avant le titre de la section #}
                        <p class="mt-2 header-item">
                            <i class="fas fa-calendar-day me-2"></i>{{ current_date }} {# Calendar Icon (original color) #}
                        </p>
                        <p class="mt-2 header-item">
                            <i class="fas fa-flask me-2"></i>Gestion des analyses biologiques {# Flask Icon (original color) #}
                        </p>
                    </div>
                    <div class="card-body">
                        <ul class="nav nav-tabs justify-content-center" id="biologieTab" role="tablist">
                            <li class="nav-item" role="presentation">
                                <button class="nav-link active" id="nouvelle-analyse-tab"
                                        data-bs-toggle="tab" data-bs-target="#nouvelle-analyse"
                                        type="button" role="tab">
                                    <i class="fas fa-plus-circle me-2" style="color: #4CAF50;"></i>Nouvelle Analyse {# Green Plus Icon #}
                                </button>
                            </li>
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="historique-analyses-tab"
                                        data-bs-toggle="tab" data-bs-target="#historique-analyses"
                                        type="button" role="tab">
                                    <i class="fas fa-history me-2" style="color: #FFC107;"></i>Historique Analyses {# Amber History Icon #}
                                </button>
                            </li>
                            {# REMOVED: Tab for "Liste des Analyses" #}
                            {# <li class="nav-item" role="presentation">
                                <button class="nav-link" id="liste-analyses-tab"
                                        data-bs-toggle="tab" data-bs-target="#liste-analyses"
                                        type="button" role="tab">
                                    <i class="fas fa-list me-2"></i>Liste des Analyses
                                </button>
                            </li> #}
                        </ul>

                        <div class="tab-content mt-3" id="biologieTabContent">
                            <div class="tab-pane fade show active" id="nouvelle-analyse" role="tabpanel">
                                <h4 class="text-primary mb-3">Saisir une nouvelle analyse</h4>

                                {# Affichage du dernier patient ayant une analyse prescrite #}
                                {% if last_patient %}
                                <div class="alert alert-info" role="alert">
                                    <strong>Dernier patient avec analyse prescrite:</strong>
                                    ID: {{ last_patient.ID_Patient or 'N/A' }},
                                    Nom: {{ last_patient.NOM or 'N/A' }} {{ last_patient.PRENOM or 'N/A' }}
                                    (Analyse: {{ last_patient.ANALYSE or 'N/A' }})
                                </div>
                                {% else %}
                                <div class="alert alert-warning" role="alert">
                                    Aucun patient avec analyse prescrite trouvé dans Biologie.xlsx.
                                </div>
                                {% endif %}

                                <form action="{{ url_for('biologie.save_analyse') }}" method="POST" enctype="multipart/form-data">
                                    <div class="row g-3">
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" id="patient_id" name="patient_id" placeholder=" " required>
                                            <label for="patient_id"><i class="fas fa-id-card me-2" style="color: #6C757D;"></i>ID Patient</label> {# Gray ID Card Icon #}
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" id="patient_nom" name="patient_nom" placeholder=" " readonly>
                                            <label for="patient_nom"><i class="fas fa-user me-2" style="color: #007BFF;"></i>Nom du Patient</label> {# Blue User Icon #}
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" id="patient_prenom" name="patient_prenom" placeholder=" " readonly>
                                            <label for="patient_prenom"><i class="fas fa-user-tag me-2" style="color: #17A2B8;"></i>Prénom du Patient</label> {# Cyan User Tag Icon #}
                                        </div>
                                        
                                        {# Container for dynamically added analysis input fields #}
                                        <div id="analysis_inputs_container" class="col-12 row g-3">
                                            {# Dynamically populated fields will go here #}
                                        </div>

                                        <div class="col-12 text-center">
                                            <button type="button" class="btn btn-outline-secondary mb-3" id="add_analysis_field">
                                                <i class="fas fa-plus me-2" style="color: #28A745;"></i>Ajouter une autre analyse {# Green Plus Icon #}
                                            </button>
                                        </div>
                                        
                                        <div class="col-md-12 mb-3">
                                            <label for="analyse_pdf" class="form-label"><i class="fas fa-file-pdf me-2" style="color: #DC3545;"></i>Importer le résultat PDF</label> {# Red PDF Icon #}
                                            <input class="form-control" type="file" id="analyse_pdf" name="analyse_pdf" accept=".pdf">
                                        </div>
                                        <div class="col-12 text-center">
                                            <button type="submit" class="btn btn-primary"><i class="fas fa-save me-2" style="color: #FFFFFF;"></i>Enregistrer l'analyse(s)</button> {# White Save Icon #}
                                        </div>
                                    </div>
                                </form>
                            </div>
                            <div class="tab-pane fade" id="historique-analyses" role="tabpanel">
                                <h4 class="text-primary mb-3">Historique des analyses enregistrées</h4>
                                <p class="text-muted">Tableau de toutes les analyses enregistrées dans le système, y compris les noms d'analyse et les conclusions du biologiste.</p>
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover">
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>ID Patient</th>
                                                <th>Nom Patient</th>
                                                <th>Prénom Patient</th>
                                                <th>Nom Analyse</th>
                                                <th>Conclusion</th>
                                                <th>PDF</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% if analyses_history %}
                                                {% for entry in analyses_history %}
                                                <tr>
                                                    <td>{{ entry.Date }}</td>
                                                    <td>{{ entry.ID_Patient }}</td>
                                                    <td>{{ entry.NOM }}</td>
                                                    <td>{{ entry.PRENOM }}</td>
                                                    <td>{{ entry.ANALYSE }}</td>
                                                    <td>{{ entry.CONCLUSION }}</td>
                                                    <td>
                                                        {% if entry.PDF_File %}
                                                            <a href="{{ url_for('biologie.download_analyse_pdf', filename=entry.PDF_File) }}" class="btn btn-sm btn-info" target="_blank">
                                                                <i class="fas fa-download" style="color: #17A2B8;"></i> {# Cyan Download Icon #}
                                                            </a>
                                                        {% else %}
                                                            N/A
                                                        {% endif %}
                                                    </td>
                                                </tr>
                                                {% endfor %}
                                            {% else %}
                                                <tr><td colspan="7">Aucune analyse enregistrée.</td></tr>
                                            {% endif %}
                                        </tbody>
                                    </table>
                                </div>
                                <div class="text-center mt-4">
                                    <button class="btn btn-outline-secondary" onclick="exportBiologieHistory()"><i class="fas fa-download me-2" style="color: #007BFF;"></i>Exporter l'historique</button> {# Blue Download Icon #}
                                </div>
                            </div>
                            {# REMOVED: Tab content for "Liste des Analyses" #}
                            {# <div class="tab-pane fade" id="liste-analyses" role="tabpanel">
                                <h4 class="text-primary mb-3">Liste des analyses disponibles</h4>
                                <p class="text-muted">Gérez les options d'analyses biologiques par défaut.</p>
                                <form id="saveAnalysesListForm" action="{{ url_for('biologie.save_analyses_list') }}" method="POST">
                                    <div class="mb-3 floating-label">
                                        <textarea class="form-control" name="analyses_list_content" id="analyses_list_content" rows="10" placeholder=" ">{{ config.analyses_options|join('\\n') }}</textarea>
                                        <label for="analyses_list_content">Liste des analyses (une par ligne)</label>
                                    </div>
                                    <div class="text-center">
                                        <button type="submit" class="btn btn-success"><i class="fas fa-save me-2"></i>Enregistrer la liste des analyses</button>
                                    </div>
                                </form>
                            </div> #}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <footer class="text-center py-1 small">
        <div class="card-footer text-center py-1">
            <div style="margin-bottom: 0 !important;">
                <p class="small mb-1" style="color: white;">
                    <i class="fas fa-heartbeat me-1" style="color: #FF69B4;"></i> {# Pink Heartbeat Icon #}
                    SASTOUKA DIGITAL © 2025 • sastoukadigital@gmail.com tel +212652084735
                </p>
                <p class="small mb-0" style="color: white;">
                    Ouvrir l’application en réseau {{ host_address }}
                </p>
            </div>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            // Initialisation des onglets Bootstrap
            const triggerTabList = [].slice.call(document.querySelectorAll('#biologieTab button'))
            triggerTabList.forEach(function (triggerEl) {
                const tabTrigger = new bootstrap.Tab(triggerEl)

                triggerEl.addEventListener('click', function (event) {
                    event.preventDefault()
                    tabTrigger.show()
                })
            })

            // Persistance de l'onglet actif (optionnel, comme sur d'autres pages)
            const activeTab = localStorage.getItem('activeBiologieTab');
            if (activeTab) {
                const triggerEl = document.querySelector(`#biologieTab button[data-bs-target="${activeTab}"]`);
                if (triggerEl) bootstrap.Tab.getOrCreateInstance(triggerEl).show();
            }

            document.querySelectorAll('#biologieTab button').forEach(function(tabEl) {
                tabEl.addEventListener('shown.bs.tab', function(event) {
                    localStorage.setItem('activeBiologieTab', event.target.getAttribute('data-bs-target'));
                });
            });

            // Auto-remplissage Nom et Prénom et ajout dynamique des analyses en fonction de l'ID Patient
            const patientIdInput = document.getElementById('patient_id');
            const patientNomInput = document.getElementById('patient_nom');
            const patientPrenomInput = document.getElementById('patient_prenom');
            const analysisInputsContainer = document.getElementById('analysis_inputs_container');
            const addAnalysisFieldButton = document.getElementById('add_analysis_field');

            const addAnalysisField = (analysisName = '', conclusion = '') => {
                const newAnalysisGroup = document.createElement('div');
                newAnalysisGroup.classList.add('col-12', 'row', 'g-3', 'mb-3', 'border', 'p-3', 'rounded', 'shadow-sm', 'bg-light'); // Added styling for better visual grouping

                newAnalysisGroup.innerHTML = `
                    <div class="col-md-11 floating-label">
                        <input type="text" class="form-control" name="nom_analyse[]" value="${analysisName}" placeholder=" " required>
                        <label><i class="fas fa-flask me-2" style="color: #DA70D6;"></i>Nom de l'analyse</label> {# Orchid Flask Icon #}
                    </div>
                    <div class="col-md-1 flex-grow-0 d-flex align-items-center justify-content-center">
                        <button type="button" class="btn btn-danger remove-analysis-field" title="Supprimer cette analyse">
                            <i class="fas fa-trash" style="color: #FFFFFF;"></i> {# White Trash Icon #}
                        </button>
                    </div>
                    <div class="col-md-12 floating-label">
                        <textarea class="form-control" name="conclusion_biologiste[]" rows="3" placeholder=" " required>${conclusion}</textarea>
                        <label><i class="fas fa-microscope me-2" style="color: #20B2AA;"></i>Conclusion du biologiste</label> {# Light Sea Green Microscope Icon #}
                    </div>
                `;
                analysisInputsContainer.appendChild(newAnalysisGroup);

                // Initialize floating labels for new inputs
                newAnalysisGroup.querySelectorAll('.floating-label input, .floating-label select, .floating-label textarea').forEach(input => {
                    if (input.value) {
                        input.classList.add('not-placeholder-shown');
                    }
                    input.addEventListener('focus', () => input.classList.add('not-placeholder-shown'));
                    input.addEventListener('blur', () => {
                        if (!input.value) {
                            input.classList.remove('not-placeholder-shown');
                        }
                    });
                });

                // Add event listener for remove button
                newAnalysisGroup.querySelector('.remove-analysis-field').addEventListener('click', () => {
                    newAnalysisGroup.remove();
                });
            };

            // Add initial empty analysis field on page load if none are present
            if (analysisInputsContainer.children.length === 0) {
                 addAnalysisField();
            }

            addAnalysisFieldButton.addEventListener('click', () => {
                addAnalysisField();
            });


            patientIdInput.addEventListener('change', async (event) => {
                const patientId = event.target.value.trim();
                if (patientId) {
                    try {
                        const response = await fetch(`/biologie/get_patient_details?patient_id=${patientId}`);
                        if (response.ok) {
                            const data = await response.json();
                            patientNomInput.value = data.nom || '';
                            patientPrenomInput.value = data.prenom || '';

                            // Clear existing dynamic analysis fields
                            analysisInputsContainer.innerHTML = '';

                            if (data.analyses && data.analyses.length > 0) {
                                data.analyses.forEach(analysis => {
                                    addAnalysisField(analysis.analyse, analysis.conclusion);
                                });
                            } else {
                                // Add a single empty field if no analyses are found for the patient
                                addAnalysisField();
                            }
                            
                            // Trigger floating label update for static inputs
                            [patientNomInput, patientPrenomInput].forEach(input => {
                                if (input.value) {
                                    input.classList.add('not-placeholder-shown');
                                } else {
                                    input.classList.remove('not-placeholder-shown');
                                }
                                input.dispatchEvent(new Event('change'));
                            });

                        } else {
                            console.error('Failed to fetch patient details:', response.statusText);
                            patientNomInput.value = '';
                            patientPrenomInput.value = '';
                            analysisInputsContainer.innerHTML = ''; // Clear analyses
                            addAnalysisField(); // Add an empty one
                            [patientNomInput, patientPrenomInput].forEach(input => {
                                input.classList.remove('not-placeholder-shown');
                                input.dispatchEvent(new Event('change'));
                            });
                        }
                    } catch (error) {
                        console.error('Error fetching patient details:', error);
                        patientNomInput.value = '';
                        patientPrenomInput.value = '';
                        analysisInputsContainer.innerHTML = ''; // Clear analyses
                        addAnalysisField(); // Add an empty one
                        [patientNomInput, patientPrenomInput].forEach(input => {
                            input.classList.remove('not-placeholder-shown');
                            input.dispatchEvent(new Event('change'));
                        });
                    }
                } else {
                    patientNomInput.value = '';
                    patientPrenomInput.value = '';
                    analysisInputsContainer.innerHTML = ''; // Clear analyses
                    addAnalysisField(); // Add an empty one
                    [patientNomInput, patientPrenomInput].forEach(input => {
                        input.classList.remove('not-placeholder-shown');
                        input.dispatchEvent(new Event('change'));
                    });
                }
            });

            // Ensure labels float correctly on page load if inputs have values (for initial static fields)
            document.querySelectorAll('.floating-label input, .floating-label select, .floating-label textarea').forEach(input => {
                if (input.value) {
                    input.classList.add('not-placeholder-shown'); // Custom class for floating label
                }
                input.addEventListener('focus', () => input.classList.add('not-placeholder-shown'));
                input.addEventListener('blur', () => {
                    if (!input.value) {
                        input.classList.remove('not-placeholder-shown');
                    }
                });
            });


            // Soumission AJAX paramètres (copié depuis les templates partagés)
            document.getElementById('settingsForm').addEventListener('submit', e=>{
                e.preventDefault();
                fetch(e.target.action,{method:e.target.method,body:new FormData(e.target),credentials:'same-origin'})
                    .then(r=>{ if(!r.ok) throw new Error('Échec réseau'); return r; })
                    .then(()=>Swal.fire({icon:'success',title:'Enregistré',text:'Paramètres sauvegardés.'}).then(()=>location.reload()))
                    .catch(err=>Swal.fire({icon:'error',title:'Erreur',text:err.message}));
            });

            // REMOVED: Soumission AJAX pour la liste des analyses
            // document.getElementById('saveAnalysesListForm').addEventListener('submit', async (e) => {
            //     e.preventDefault();
            //     const formData = new FormData(e.target);
            //     try {
            //         const response = await fetch(e.target.action, {
            //             method: 'POST',
            //             body: formData,
            //             credentials: 'same-origin'
            //         });
            //         if (response.ok) {
            //             Swal.fire({
            //                 icon: 'success',
            //                 title: 'Enregistré',
            //                 text: 'Liste des analyses sauvegardée avec succès.'
            //             }).then(() => {
            //                 location.reload(); // Reload to reflect changes in settings offcanvas
            //             });
            //         } else {
            //             const errorData = await response.json();
            //             throw new Error(errorData.message || 'Échec de la sauvegarde de la liste des analyses.');
            //         }
            //     } catch (error) {
            //         Swal.fire({
            //             icon: 'error',
            //             title: 'Erreur',
            //             text: error.message
            //         });
            //     }
            // });
        });

        function exportBiologieHistory() {
            window.location.href = "{{ url_for('biologie.export_biologie_history') }}";
        }
    </script>
    {% include '_floating_assistant.html' %}
</body>
</html>
"""

@biologie_bp.route('/')
def home_biologie():
    if 'email' not in session:
        return redirect(url_for('login.login'))
    config = utils.load_config()
    session['theme'] = config.get('theme', theme.DEFAULT_THEME)
    host_address = f"http://{utils.LOCAL_IP}:3000"
    current_date = datetime.now().strftime("%Y-%m-%d")

    last_patient = None
    analyses_history = []
    
    biologie_data_path = os.path.join(utils.EXCEL_FOLDER, 'Biologie.xlsx')

    if os.path.exists(biologie_data_path):
        try:
            df_biologie = pd.read_excel(biologie_data_path, dtype=str).fillna('')
            
            # Convert DataFrame to list of dictionaries for Jinja2 template
            analyses_history = df_biologie.to_dict(orient='records')

            # Filter for rows where 'ANALYSE' column is not empty/NA
            df_analyses = df_biologie[df_biologie['ANALYSE'].notna()]
            if not df_analyses.empty:
                last_patient_series = df_analyses.iloc[-1]
                last_patient = last_patient_series.to_dict()
                
        except Exception as e:
            flash(f"Erreur lors du chargement des données de biologie: {e}", "danger")
            print(f"Erreur lors du chargement des données de biologie: {e}")
    else:
        flash("Fichier Biologie.xlsx non trouvé. Créez une nouvelle analyse pour le générer.", "warning")

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

    return render_template_string(
        biologie_template,
        config=config,
        theme_vars=theme.current_theme(),
        theme_names=list(theme.THEMES.keys()),
        host_address=host_address,
        current_date=current_date,
        last_patient=last_patient,
        analyses_history=analyses_history,
        # --- PASSER LA NOUVELLE VARIABLE AU TEMPLATE ---
        logged_in_doctor_name=logged_in_full_name # Utilise le même nom de variable que dans main_template pour cohérence
        # --- FIN DU PASSAGE ---
    )


@biologie_bp.route('/get_patient_details', methods=['GET'])
def get_patient_details():
    if 'email' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    patient_id = request.args.get('patient_id')
    if not patient_id:
        return jsonify({"error": "Patient ID is required"}), 400

    patient_id = str(patient_id).strip()

    nom = utils.patient_id_to_nom.get(patient_id, '')
    prenom = utils.patient_id_to_prenom.get(patient_id, '')
    
    # Initialize an empty list to hold the analyses
    patient_analyses = []

    if utils.CONSULT_FILE_PATH and os.path.exists(utils.CONSULT_FILE_PATH):
        try:
            df_consult = pd.read_excel(utils.CONSULT_FILE_PATH, dtype=str).fillna('')
            if 'patient_id' in df_consult.columns:
                patient_consultations = df_consult[df_consult['patient_id'] == patient_id]
                if not patient_consultations.empty and 'analyses' in patient_consultations.columns:
                    # Iterate through all consultations for the patient
                    for index, row in patient_consultations.iterrows():
                        analyses_str = row['analyses']
                        if analyses_str:
                            # Split the analyses string by '; ' and add each to the list
                            individual_analyses = [a.strip() for a in analyses_str.split('; ') if a.strip()]
                            for analysis_name in individual_analyses:
                                patient_analyses.append({"analyse": analysis_name, "conclusion": ""}) # Conclusion is initially empty, as ConsultationData.xlsx doesn't store it
        except Exception as e:
            print(f"Erreur lors de la récupération des analyses de consultation pour le patient {patient_id}: {e}")

    if nom or prenom or patient_analyses: # If any data is found
        return jsonify({
            "nom": nom,
            "prenom": prenom,
            "analyses": patient_analyses # Return the list of analyses
        })
    else:
        return jsonify({"nom": "", "prenom": "", "analyses": [], "message": "Patient non trouvé dans les dossiers"}), 404


@biologie_bp.route('/save_analyse', methods=['POST'])
def save_analyse():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    patient_id = request.form.get('patient_id')
    patient_nom = request.form.get('patient_nom')
    patient_prenom = request.form.get('patient_prenom')
    # Get all analysis names and conclusions as lists
    nom_analyses = request.form.getlist('nom_analyse[]')
    conclusion_biologistes = request.form.getlist('conclusion_biologiste[]')
    
    analyse_pdf_file = request.files.get('analyse_pdf')
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Assurez-vous que les répertoires dynamiques sont définis
    if not utils.EXCEL_FOLDER or not utils.PDF_FOLDER:
        flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
        return redirect(url_for('biologie.home_biologie'))

    biologie_data_path = os.path.join(utils.EXCEL_FOLDER, 'Biologie.xlsx')
    pdf_upload_dir = os.path.join(utils.PDF_FOLDER, 'Analyses_Biologiques')

    os.makedirs(pdf_upload_dir, exist_ok=True)

    pdf_filename = None
    if analyse_pdf_file and analyse_pdf_file.filename:
        safe_filename = utils.secure_filename(analyse_pdf_file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        pdf_filename = f"analyse_{patient_id}_{timestamp}_{safe_filename}"
        pdf_path = os.path.join(pdf_upload_dir, pdf_filename)
        try:
            analyse_pdf_file.save(pdf_path)
            flash(f"Fichier PDF '{pdf_filename}' enregistré.", "success")
        except Exception as e:
            flash(f"Erreur lors de l'enregistrement du PDF : {e}", "danger")
            print(f"Erreur lors de l'enregistrement du PDF : {e}")
            pdf_filename = None

    try:
        if os.path.exists(biologie_data_path):
            df_biologie = pd.read_excel(biologie_data_path, dtype=str).fillna('')
        else:
            df_biologie = pd.DataFrame(columns=['Date', 'ID_Patient', 'NOM', 'PRENOM', 'ANALYSE', 'CONCLUSION', 'PDF_File'])

        # Iterate over the lists of analyses and conclusions to save in Biologie.xlsx
        for i in range(len(nom_analyses)):
            analysis_name = nom_analyses[i]
            # Ensure index exists for conclusion, default to empty string if not
            biologist_conclusion = conclusion_biologistes[i] if i < len(conclusion_biologistes) else ''

            new_row = {
                'Date': current_date,
                'ID_Patient': patient_id,
                'NOM': patient_nom if patient_nom else utils.patient_id_to_nom.get(patient_id, ''),
                'PRENOM': patient_prenom if patient_prenom else utils.patient_id_to_prenom.get(patient_id, ''),
                'ANALYSE': analysis_name,
                'CONCLUSION': biologist_conclusion,
                'PDF_File': pdf_filename if pdf_filename else '' # PDF is associated with the whole form submission, not per analysis line for now
            }
            df_biologie = pd.concat([df_biologie, pd.DataFrame([new_row])], ignore_index=True)

        df_biologie.to_excel(biologie_data_path, index=False)
        flash("Analyse(s) enregistrée(s) avec succès dans Biologie.xlsx.", "success")

        # --- Update ConsultationData.xlsx with analysis comments ---
        if utils.CONSULT_FILE_PATH and os.path.exists(utils.CONSULT_FILE_PATH):
            try:
                df_consult = pd.read_excel(utils.CONSULT_FILE_PATH, dtype=str).fillna('')

                # Find all consultations for the patient
                # We assume that the last entry for a given patient_id is the latest consultation.
                # If a more precise definition of "last" (e.g., based on a timestamp column) is needed,
                # the sorting logic would have to be adjusted here.
                patient_consultations_indices = df_consult[df_consult['patient_id'] == patient_id].index

                if not patient_consultations_indices.empty:
                    # Get the index of the last consultation for this patient
                    last_consultation_index = patient_consultations_indices[-1]

                    # Construct the comment string from all submitted analyses and conclusions
                    comments_list = []
                    for i in range(len(nom_analyses)):
                        analysis_name = nom_analyses[i]
                        biologist_conclusion = conclusion_biologistes[i] if i < len(conclusion_biologistes) else ''
                        
                        # Only add if both are present or at least analysis name is present
                        if analysis_name and biologist_conclusion:
                            comments_list.append(f"{analysis_name}: {biologist_conclusion}")
                        elif analysis_name: 
                            comments_list.append(analysis_name)

                    new_analysis_comments_str = "; ".join(comments_list)

                    # Ensure the 'doctor_comment' column exists, create if not
                    if 'doctor_comment' not in df_consult.columns:
                        df_consult['doctor_comment'] = ''
                    
                    # Retrieve existing comment
                    existing_doctor_comment = df_consult.loc[last_consultation_index, 'doctor_comment']
                    
                    # Append new comments to existing comments, separated by a newline if both exist
                    updated_doctor_comment = existing_doctor_comment
                    if new_analysis_comments_str: # Only update if there are new comments to add
                        if existing_doctor_comment:
                            updated_doctor_comment = f"{existing_doctor_comment}\nAnalyses: {new_analysis_comments_str}"
                        else: # If existing comment is empty, just set it to the new analyses
                            updated_doctor_comment = f"Analyses: {new_analysis_comments_str}"
                    
                    # Update the 'doctor_comment' column for the last consultation
                    df_consult.loc[last_consultation_index, 'doctor_comment'] = updated_doctor_comment

                    # Save the updated DataFrame back to the Excel file
                    df_consult.to_excel(utils.CONSULT_FILE_PATH, index=False)
                    flash(f"La colonne 'Commentaire du docteur' de la dernière consultation pour le patient {patient_id} a été mise à jour avec les analyses dans ConsultationData.xlsx.", "info")
                else:
                    print(f"Aucune consultation trouvée pour le patient {patient_id} dans ConsultationData.xlsx pour mettre à jour les commentaires.")
            except Exception as e:
                flash(f"Erreur lors de la mise à jour de ConsultationData.xlsx avec les commentaires d'analyse : {e}", "danger")
                print(f"Erreur lors de la mise à jour de ConsultationData.xlsx : {e}")
        else:
            print("Le fichier ConsultationData.xlsx n'a pas été trouvé. Impossible de mettre à jour la colonne 'doctor_comment'.")

    except Exception as e:
        flash(f"Erreur lors de l'enregistrement de l'analyse(s) dans Biologie.xlsx: {e}", "danger")
        print(f"Erreur: {e}")

    return redirect(url_for('biologie.home_biologie'))

@biologie_bp.route('/download_analyse_pdf/<filename>')
def download_analyse_pdf(filename):
    if 'email' not in session:
        return redirect(url_for('login.login'))
    
    if not utils.PDF_FOLDER:
        flash("Erreur: Le répertoire PDF n'est pas défini. Veuillez vous reconnecter.", "danger")
        return redirect(url_for('biologie.home_biologie'))

    pdf_upload_dir = os.path.join(utils.PDF_FOLDER, 'Analyses_Biologiques')
    
    return send_from_directory(pdf_upload_dir, filename, as_attachment=True)

@biologie_bp.route('/export_biologie_history')
def export_biologie_history():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    biologie_data_path = os.path.join(utils.EXCEL_FOLDER, 'Biologie.xlsx')

    if os.path.exists(biologie_data_path):
        try:
            df_biologie = pd.read_excel(biologie_data_path, dtype=str).fillna('')
            output = io.BytesIO()
            writer = pd.ExcelWriter(output, engine='xlsxwriter')
            df_biologie.to_excel(writer, sheet_name='Historique Analyses Biologiques', index=False)
            writer.close()
            output.seek(0)
            
            return send_file(output, as_attachment=True, download_name='Historique_Analyses_Biologiques.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception as e:
            flash(f"Erreur lors de l'exportation de l'historique : {e}", "danger")
            print(f"Erreur lors de l'exportation de l'historique : {e}")
    else:
        flash("Aucun historique d'analyses à exporter.", "warning")
    return redirect(url_for('biologie.home_biologie'))

# REMOVED: @biologie_bp.route('/save_analyses_list', methods=['POST'])
# def save_analyses_list():
#     """Sauvegarde la liste des analyses par défaut."""
#     if 'email' not in session:
#         return jsonify({"message": "Non autorisé"}), 401

#     analyses_content = request.form.get('analyses_list_content', '')
#     # Divise par les retours à la ligne et filtre les lignes vides
#     analyses_options = [line.strip() for line in analyses_content.split('\\n') if line.strip()]

#     config = utils.load_config()
#     config['analyses_options'] = analyses_options
#     utils.save_config(config)
    
#     return jsonify({"message": "Liste des analyses sauvegardée avec succès!"})
