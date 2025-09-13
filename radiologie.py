# radiologie.py
# Module pour la gestion des analyses radiologiques

from flask import Blueprint, render_template_string, session, redirect, url_for, flash, request, jsonify, send_from_directory, send_file
from datetime import datetime
import utils
import theme
import pandas as pd
import os
import io
import login

# Création du Blueprint pour les routes de radiologie
radiologie_bp = Blueprint('radiologie', __name__, url_prefix='/radiologie')

# Définition du template HTML pour la page de gestion des radiologies
radiologie_template = """
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Radiologie – {{ config.nom_clinique or 'EasyMedicaLink' }}</title>
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
                            <i class="fas fa-x-ray me-2"></i>Gestion des analyses radiologiques {# X-Ray Icon (original color) #}
                        </p>
                    </div>
                    <div class="card-body">
                        <ul class="nav nav-tabs justify-content-center" id="radiologieTab" role="tablist">
                            <li class="nav-item" role="presentation">
                                <button class="nav-link active" id="nouvelle-radiologie-tab"
                                        data-bs-toggle="tab" data-bs-target="#nouvelle-radiologie"
                                        type="button" role="tab">
                                    <i class="fas fa-plus-circle me-2" style="color: #4CAF50;"></i>Nouvelle Radiologie {# Green Plus Icon #}
                                </button>
                            </li>
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="historique-radiologies-tab"
                                        data-bs-toggle="tab" data-bs-target="#historique-radiologies"
                                        type="button" role="tab">
                                    <i class="fas fa-history me-2" style="color: #FFC107;"></i>Historique Radiologies {# Amber History Icon #}
                                </button>
                            </li>
                        </ul>

                        <div class="tab-content mt-3" id="radiologieTabContent">
                            <div class="tab-pane fade show active" id="nouvelle-radiologie" role="tabpanel">
                                <h4 class="text-primary mb-3">Saisir une nouvelle radiologie</h4>

                                {# Affichage du dernier patient ayant une radiologie prescrite #}
                                {% if last_patient %}
                                <div class="alert alert-info" role="alert">
                                    <strong>Dernier patient avec radiologie prescrite:</strong>
                                    ID: {{ last_patient.ID_Patient or 'N/A' }},
                                    Nom: {{ last_patient.NOM or 'N/A' }} {{ last_patient.PRENOM or 'N/A' }}
                                    (Radiologie: {{ last_patient.RADIOLOGIE or 'N/A' }})
                                </div>
                                {% else %}
                                <div class="alert alert-warning" role="alert">
                                    Aucun patient avec radiologie prescrite trouvé dans Radiologie.xlsx.
                                </div>
                                {% endif %}

                                <form action="{{ url_for('radiologie.save_radiologie') }}" method="POST" enctype="multipart/form-data">
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
                                        
                                        {# Container for dynamically added radiology input fields #}
                                        <div id="radiology_inputs_container" class="col-12 row g-3">
                                            {# Dynamically populated fields will go here #}
                                        </div>

                                        <div class="col-12 text-center">
                                            <button type="button" class="btn btn-outline-secondary mb-3" id="add_radiology_field">
                                                <i class="fas fa-plus me-2" style="color: #28A745;"></i>Ajouter une autre radiologie {# Green Plus Icon #}
                                            </button>
                                        </div>
                                        
                                        <div class="col-md-12 mb-3">
                                            <label for="radiology_pdf" class="form-label"><i class="fas fa-file-pdf me-2" style="color: #DC3545;"></i>Importer le résultat PDF</label> {# Red PDF Icon #}
                                            <input class="form-control" type="file" id="radiology_pdf" name="radiology_pdf" accept=".pdf">
                                        </div>
                                        <div class="col-12 text-center">
                                            <button type="submit" class="btn btn-primary"><i class="fas fa-save me-2" style="color: #FFFFFF;"></i>Enregistrer la radiologie(s)</button> {# White Save Icon #}
                                        </div>
                                    </div>
                                </form>
                            </div>
                            <div class="tab-pane fade" id="historique-radiologies" role="tabpanel">
                                <h4 class="text-primary mb-3">Historique des radiologies enregistrées</h4>
                                <p class="text-muted">Tableau de toutes les radiologies enregistrées dans le système, y compris les noms de radiologie et les conclusions du radiologue.</p>
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover">
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>ID Patient</th>
                                                <th>Nom Patient</th>
                                                <th>Prénom Patient</th>
                                                <th>Nom Radiologie</th>
                                                <th>Conclusion</th>
                                                <th>PDF</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% if radiologies_history %}
                                                {% for entry in radiologies_history %}
                                                <tr>
                                                    <td>{{ entry.Date }}</td>
                                                    <td>{{ entry.ID_Patient }}</td>
                                                    <td>{{ entry.NOM }}</td>
                                                    <td>{{ entry.PRENOM }}</td>
                                                    <td>{{ entry.RADIOLOGIE }}</td>
                                                    <td>{{ entry.CONCLUSION }}</td>
                                                    <td>
                                                        {% if entry.PDF_File %}
                                                            <a href="{{ url_for('radiologie.download_radiologie_pdf', filename=entry.PDF_File) }}" class="btn btn-sm btn-info" target="_blank">
                                                                <i class="fas fa-download" style="color: #17A2B8;"></i> {# Cyan Download Icon #}
                                                            </a>
                                                        {% else %}
                                                            N/A
                                                        {% endif %}
                                                    </td>
                                                </tr>
                                                {% endfor %}
                                            {% else %}
                                                <tr><td colspan="7">Aucune radiologie enregistrée.</td></tr>
                                            {% endif %}
                                        </tbody>
                                    </table>
                                </div>
                                <div class="text-center mt-4">
                                    <button class="btn btn-outline-secondary" onclick="exportRadiologieHistory()"><i class="fas fa-download me-2" style="color: #007BFF;"></i>Exporter l'historique</button> {# Blue Download Icon #}
                                </div>
                            </div>
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
            const triggerTabList = [].slice.call(document.querySelectorAll('#radiologieTab button'))
            triggerTabList.forEach(function (triggerEl) {
                const tabTrigger = new bootstrap.Tab(triggerEl)

                triggerEl.addEventListener('click', function (event) {
                    event.preventDefault()
                    tabTrigger.show()
                })
            })

            // Persistance de l'onglet actif (optionnel, comme sur d'autres pages)
            const activeTab = localStorage.getItem('activeRadiologieTab');
            if (activeTab) {
                const triggerEl = document.querySelector(`#radiologieTab button[data-bs-target="${activeTab}"]`);
                if (triggerEl) bootstrap.Tab.getOrCreateInstance(triggerEl).show();
            }

            document.querySelectorAll('#radiologieTab button').forEach(function(tabEl) {
                tabEl.addEventListener('shown.bs.tab', function(event) {
                    localStorage.setItem('activeRadiologieTab', event.target.getAttribute('data-bs-target'));
                });
            });

            // Auto-remplissage Nom et Prénom et ajout dynamique des radiologies en fonction de l'ID Patient
            const patientIdInput = document.getElementById('patient_id');
            const patientNomInput = document.getElementById('patient_nom');
            const patientPrenomInput = document.getElementById('patient_prenom');
            const radiologyInputsContainer = document.getElementById('radiology_inputs_container');
            const addRadiologyFieldButton = document.getElementById('add_radiology_field');

            const addRadiologyField = (radiologyName = '', conclusion = '') => {
                const newRadiologyGroup = document.createElement('div');
                newRadiologyGroup.classList.add('col-12', 'row', 'g-3', 'mb-3', 'border', 'p-3', 'rounded', 'shadow-sm', 'bg-light'); // Added styling for better visual grouping

                newRadiologyGroup.innerHTML = `
                    <div class="col-md-11 floating-label">
                        <input type="text" class="form-control" name="nom_radiologie[]" value="${radiologyName}" placeholder=" " required>
                        <label><i class="fas fa-x-ray me-2" style="color: #8A2BE2;"></i>Nom de la radiologie</label> {# Blue Violet X-Ray Icon #}
                    </div>
                    <div class="col-md-1 flex-grow-0 d-flex align-items-center justify-content-center">
                        <button type="button" class="btn btn-danger remove-radiology-field" title="Supprimer cette radiologie">
                            <i class="fas fa-trash" style="color: #FFFFFF;"></i> {# White Trash Icon #}
                        </button>
                    </div>
                    <div class="col-md-12 floating-label">
                        <textarea class="form-control" name="conclusion_radiologue[]" rows="3" placeholder=" " required>${conclusion}</textarea>
                        <label><i class="fas fa-diagnoses me-2" style="color: #6A5ACD;"></i>Conclusion du radiologue</label> {# Slate Blue Diagnoses Icon #}
                    </div>
                `;
                radiologyInputsContainer.appendChild(newRadiologyGroup);

                // Initialize floating labels for new inputs
                newRadiologyGroup.querySelectorAll('.floating-label input, .floating-label select, .floating-label textarea').forEach(input => {
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
                newRadiologyGroup.querySelector('.remove-radiology-field').addEventListener('click', () => {
                    newRadiologyGroup.remove();
                });
            };

            // Add initial empty radiology field on page load if none are present
            if (radiologyInputsContainer.children.length === 0) {
                 addRadiologyField();
            }

            addRadiologyFieldButton.addEventListener('click', () => {
                addRadiologyField();
            });


            patientIdInput.addEventListener('change', async (event) => {
                const patientId = event.target.value.trim();
                if (patientId) {
                    try {
                        const response = await fetch(`/radiologie/get_patient_details?patient_id=${patientId}`);
                        if (response.ok) {
                            const data = await response.json();
                            patientNomInput.value = data.nom || '';
                            patientPrenomInput.value = data.prenom || '';

                            // Clear existing dynamic radiology fields
                            radiologyInputsContainer.innerHTML = '';

                            if (data.radiologies && data.radiologies.length > 0) {
                                data.radiologies.forEach(radiology => {
                                    addRadiologyField(radiology.radiologie, radiology.conclusion);
                                });
                            } else {
                                // Add a single empty field if no radiologies are found for the patient
                                addRadiologyField();
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
                            radiologyInputsContainer.innerHTML = ''; // Clear radiologies
                            addRadiologyField(); // Add an empty one
                            [patientNomInput, patientPrenomInput].forEach(input => {
                                input.classList.remove('not-placeholder-shown');
                                input.dispatchEvent(new Event('change'));
                            });
                        }
                    } catch (error) {
                        console.error('Error fetching patient details:', error);
                        patientNomInput.value = '';
                        patientPrenomInput.value = '';
                        radiologyInputsContainer.innerHTML = ''; // Clear radiologies
                        addRadiologyField(); // Add an empty one
                        [patientNomInput, patientPrenomInput].forEach(input => {
                            input.classList.remove('not-placeholder-shown');
                            input.dispatchEvent(new Event('change'));
                        });
                    }
                } else {
                    patientNomInput.value = '';
                    patientPrenomInput.value = '';
                    radiologyInputsContainer.innerHTML = ''; // Clear radiologies
                    addRadiologyField(); // Add an empty one
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
        });

        function exportRadiologieHistory() {
            window.location.href = "{{ url_for('radiologie.export_radiologie_history') }}";
        }
    </script>
    {% include '_floating_assistant.html' %} 
</body>
</html>
"""

# Route pour la page d'accueil de la radiologie
@radiologie_bp.route('/')
def home_radiologie():
    if 'email' not in session:
        return redirect(url_for('login.login'))
    config = utils.load_config()
    session['theme'] = config.get('theme', theme.DEFAULT_THEME)
    host_address = f"http://{utils.LOCAL_IP}:3000"
    current_date = datetime.now().strftime("%Y-%m-%d")

    last_patient = None
    radiologies_history = []
    
    radiologie_data_path = os.path.join(utils.EXCEL_FOLDER, 'Radiologie.xlsx')

    if os.path.exists(radiologie_data_path):
        try:
            df_radiologie = pd.read_excel(radiologie_data_path, dtype=str).fillna('')
            
            # Convertir le DataFrame en liste de dictionnaires pour le template Jinja2
            radiologies_history = df_radiologie.to_dict(orient='records')

            # Filtrer les lignes où la colonne 'RADIOLOGIE' n'est pas vide/NA
            df_radiologies = df_radiologie[df_radiologie['RADIOLOGIE'].notna()]
            if not df_radiologies.empty:
                last_patient_series = df_radiologies.iloc[-1]
                last_patient = last_patient_series.to_dict()
                
        except Exception as e:
            flash(f"Erreur lors du chargement des données de radiologie: {e}", "danger")
            print(f"Erreur lors du chargement des données de radiologie: {e}")
    else:
        flash("Fichier Radiologie.xlsx non trouvé. Créez une nouvelle radiologie pour le générer.", "warning")

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
        radiologie_template,
        config=config,
        theme_vars=theme.current_theme(),
        theme_names=list(theme.THEMES.keys()),
        host_address=host_address,
        current_date=current_date,
        last_patient=last_patient,
        radiologies_history=radiologies_history,
        # --- PASSER LA NOUVELLE VARIABLE AU TEMPLATE ---
        logged_in_doctor_name=logged_in_full_name # Utilise le même nom de variable que dans main_template pour cohérence
        # --- FIN DU PASSAGE ---
    )

# Route pour obtenir les détails du patient et ses radiologies passées
@radiologie_bp.route('/get_patient_details', methods=['GET'])
def get_patient_details():
    if 'email' not in session:
        return jsonify({"error": "Non autorisé"}), 401

    patient_id = request.args.get('patient_id')
    if not patient_id:
        return jsonify({"error": "L'ID du patient est requis"}), 400

    patient_id = str(patient_id).strip()

    nom = utils.patient_id_to_nom.get(patient_id, '')
    prenom = utils.patient_id_to_prenom.get(patient_id, '')
    
    # Initialiser une liste vide pour contenir les radiologies
    patient_radiologies = []

    if utils.CONSULT_FILE_PATH and os.path.exists(utils.CONSULT_FILE_PATH):
        try:
            df_consult = pd.read_excel(utils.CONSULT_FILE_PATH, dtype=str).fillna('')
            if 'patient_id' in df_consult.columns:
                patient_consultations = df_consult[df_consult['patient_id'] == patient_id]
                if not patient_consultations.empty and 'radiologies' in patient_consultations.columns:
                    # Itérer sur toutes les consultations du patient
                    for index, row in patient_consultations.iterrows():
                        radiologies_str = row['radiologies']
                        if radiologies_str:
                            # Séparer la chaîne de radiologies par '; ' et ajouter chacune à la liste
                            individual_radiologies = [r.strip() for r in radiologies_str.split('; ') if r.strip()]
                            for radiology_name in individual_radiologies:
                                # La conclusion est initialement vide car ConsultationData.xlsx ne la stocke pas
                                patient_radiologies.append({"radiologie": radiology_name, "conclusion": ""}) 
        except Exception as e:
            print(f"Erreur lors de la récupération des radiologies de consultation pour le patient {patient_id}: {e}")

    if nom or prenom or patient_radiologies: # Si des données sont trouvées
        return jsonify({
            "nom": nom,
            "prenom": prenom,
            "radiologies": patient_radiologies # Retourner la liste des radiologies
        })
    else:
        return jsonify({"nom": "", "prenom": "", "radiologies": [], "message": "Patient non trouvé dans les dossiers"}), 404

# Route pour sauvegarder les radiologies
@radiologie_bp.route('/save_radiologie', methods=['POST'])
def save_radiologie():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    patient_id = request.form.get('patient_id')
    patient_nom = request.form.get('patient_nom')
    patient_prenom = request.form.get('patient_prenom')
    # Récupérer tous les noms de radiologie et les conclusions sous forme de listes
    nom_radiologies = request.form.getlist('nom_radiologie[]')
    conclusion_radiologues = request.form.getlist('conclusion_radiologue[]')
    
    radiology_pdf_file = request.files.get('radiology_pdf')
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Assurez-vous que les répertoires dynamiques sont définis
    if not utils.EXCEL_FOLDER or not utils.PDF_FOLDER:
        flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
        return redirect(url_for('radiologie.home_radiologie'))

    radiologie_data_path = os.path.join(utils.EXCEL_FOLDER, 'Radiologie.xlsx')
    pdf_upload_dir = os.path.join(utils.PDF_FOLDER, 'Radiologies') # Sous-dossier pour les PDF de radiologie

    os.makedirs(pdf_upload_dir, exist_ok=True)

    pdf_filename = None
    if radiology_pdf_file and radiology_pdf_file.filename:
        safe_filename = utils.secure_filename(radiology_pdf_file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        pdf_filename = f"radiologie_{patient_id}_{timestamp}_{safe_filename}"
        pdf_path = os.path.join(pdf_upload_dir, pdf_filename)
        try:
            radiology_pdf_file.save(pdf_path)
            flash(f"Fichier PDF '{pdf_filename}' enregistré.", "success")
        except Exception as e:
            flash(f"Erreur lors de l'enregistrement du PDF : {e}", "danger")
            print(f"Erreur lors de l'enregistrement du PDF : {e}")
            pdf_filename = None

    try:
        if os.path.exists(radiologie_data_path):
            df_radiologie = pd.read_excel(radiologie_data_path, dtype=str).fillna('')
        else:
            df_radiologie = pd.DataFrame(columns=['Date', 'ID_Patient', 'NOM', 'PRENOM', 'RADIOLOGIE', 'CONCLUSION', 'PDF_File'])

        # Itérer sur les listes de radiologies et de conclusions pour sauvegarder dans Radiologie.xlsx
        for i in range(len(nom_radiologies)):
            radiology_name = nom_radiologies[i]
            # Assurez-vous que l'index existe pour la conclusion, sinon utilisez une chaîne vide
            radiologist_conclusion = conclusion_radiologues[i] if i < len(conclusion_radiologues) else ''

            new_row = {
                'Date': current_date,
                'ID_Patient': patient_id,
                'NOM': patient_nom if patient_nom else utils.patient_id_to_nom.get(patient_id, ''),
                'PRENOM': patient_prenom if patient_prenom else utils.patient_id_to_prenom.get(patient_id, ''),
                'RADIOLOGIE': radiology_name,
                'CONCLUSION': radiologist_conclusion,
                'PDF_File': pdf_filename if pdf_filename else '' # Le PDF est associé à l'ensemble du formulaire, pas par ligne de radiologie pour l'instant
            }
            df_radiologie = pd.concat([df_radiologie, pd.DataFrame([new_row])], ignore_index=True)

        df_radiologie.to_excel(radiologie_data_path, index=False)
        flash("Radiologie(s) enregistrée(s) avec succès dans Radiologie.xlsx.", "success")

        # --- Mettre à jour ConsultationData.xlsx avec les commentaires de radiologie ---
        if utils.CONSULT_FILE_PATH and os.path.exists(utils.CONSULT_FILE_PATH):
            try:
                df_consult = pd.read_excel(utils.CONSULT_FILE_PATH, dtype=str).fillna('')

                # Trouver toutes les consultations pour le patient
                # Nous supposons que la dernière entrée pour un patient_id donné est la dernière consultation.
                # Si une définition plus précise de "dernière" (par exemple, basée sur une colonne d'horodatage) est nécessaire,
                # la logique de tri devrait être ajustée ici.
                patient_consultations_indices = df_consult[df_consult['patient_id'] == patient_id].index

                if not patient_consultations_indices.empty:
                    # Obtenir l'index de la dernière consultation pour ce patient
                    last_consultation_index = patient_consultations_indices[-1]

                    # Construire la chaîne de commentaires à partir de toutes les radiologies et conclusions soumises
                    comments_list = []
                    for i in range(len(nom_radiologies)):
                        radiology_name = nom_radiologies[i]
                        radiologist_conclusion = conclusion_radiologues[i] if i < len(conclusion_radiologues) else ''
                        
                        # Ajouter uniquement si les deux sont présents ou au moins le nom de la radiologie est présent
                        if radiology_name and radiologist_conclusion:
                            comments_list.append(f"Radiologie: {radiology_name} (Conclusion: {radiologist_conclusion})")
                        elif radiology_name: 
                            comments_list.append(f"Radiologie: {radiology_name}")

                    new_radiology_comments_str = "; ".join(comments_list)

                    # Assurez-vous que la colonne 'doctor_comment' existe, créez-la si ce n'est pas le cas
                    if 'doctor_comment' not in df_consult.columns:
                        df_consult['doctor_comment'] = ''
                    
                    # Récupérer le commentaire existant
                    existing_doctor_comment = df_consult.loc[last_consultation_index, 'doctor_comment']
                    
                    # Ajouter les nouveaux commentaires aux commentaires existants, séparés par un retour à la ligne si les deux existent
                    updated_doctor_comment = existing_doctor_comment
                    if new_radiology_comments_str: # Mettre à jour uniquement s'il y a de nouveaux commentaires à ajouter
                        if existing_doctor_comment:
                            updated_doctor_comment = f"{existing_doctor_comment}\n{new_radiology_comments_str}"
                        else: # Si le commentaire existant est vide, il suffit de le définir aux nouvelles radiologies
                            updated_doctor_comment = new_radiology_comments_str
                    
                    # Mettre à jour la colonne 'doctor_comment' pour la dernière consultation
                    df_consult.loc[last_consultation_index, 'doctor_comment'] = updated_doctor_comment

                    # Sauvegarder le DataFrame mis à jour dans le fichier Excel
                    df_consult.to_excel(utils.CONSULT_FILE_PATH, index=False)
                    flash(f"La colonne 'Commentaire du docteur' de la dernière consultation pour le patient {patient_id} a été mise à jour avec les radiologies dans ConsultationData.xlsx.", "info")
                else:
                    print(f"Aucune consultation trouvée pour le patient {patient_id} dans ConsultationData.xlsx pour mettre à jour les commentaires.")
            except Exception as e:
                flash(f"Erreur lors de la mise à jour de ConsultationData.xlsx avec les commentaires de radiologie : {e}", "danger")
                print(f"Erreur lors de la mise à jour de ConsultationData.xlsx : {e}")
        else:
            print("Le fichier ConsultationData.xlsx n'a pas été trouvé. Impossible de mettre à jour la colonne 'doctor_comment'.")

    except Exception as e:
        flash(f"Erreur lors de l'enregistrement de la radiologie(s) dans Radiologie.xlsx: {e}", "danger")
        print(f"Erreur: {e}")

    return redirect(url_for('radiologie.home_radiologie'))

# Route pour télécharger les PDF des radiologies
@radiologie_bp.route('/download_radiologie_pdf/<filename>')
def download_radiologie_pdf(filename):
    if 'email' not in session:
        return redirect(url_for('login.login'))
    
    if not utils.PDF_FOLDER:
        flash("Erreur: Le répertoire PDF n'est pas défini. Veuillez vous reconnecter.", "danger")
        return redirect(url_for('radiologie.home_radiologie'))

    pdf_upload_dir = os.path.join(utils.PDF_FOLDER, 'Radiologies')
    
    return send_from_directory(pdf_upload_dir, filename, as_attachment=True)

# Route pour exporter l'historique des radiologies
@radiologie_bp.route('/export_radiologie_history')
def export_radiologie_history():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    radiologie_data_path = os.path.join(utils.EXCEL_FOLDER, 'Radiologie.xlsx')

    if os.path.exists(radiologie_data_path):
        try:
            df_radiologie = pd.read_excel(radiologie_data_path, dtype=str).fillna('')
            output = io.BytesIO()
            writer = pd.ExcelWriter(output, engine='xlsxwriter')
            df_radiologie.to_excel(writer, sheet_name='Historique Radiologies', index=False)
            writer.close()
            output.seek(0)
            
            return send_file(output, as_attachment=True, download_name='Historique_Radiologies.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception as e:
            flash(f"Erreur lors de l'exportation de l'historique : {e}", "danger")
            print(f"Erreur lors de l'exportation de l'historique : {e}")
    else:
        flash("Aucun historique de radiologies à exporter.", "warning")
    return redirect(url_for('radiologie.home_radiologie'))
