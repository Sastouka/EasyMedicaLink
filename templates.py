# templates.py (only relevant JS part, no Python changes needed in this file itself, but context is good)
main_template = """
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ config.nom_clinique or config.cabinet or 'EasyMedicaLink' }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&family=Great+Vibes&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="https://cdn.datatables.net/1.13.1/css/dataTables.bootstrap5.min.css">
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
      font-size: 2.0rem !important; /* Adjusted font size for brand */
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
    .card:hover {
      box-shadow: var(--shadow-medium);
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

    /* Floating Labels */
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
    .floating-label input[type="date"]:not([value=""])::-webkit-datetime-edit-text,
    .floating-label input[type="date"]:not([value=""])::-webkit-datetime-edit-month-field,
    .floating-label input[type="date"]:not([value=""])::-webkit-datetime-edit-day-field,
    .floating-label input[type="date"]:not([value=""])::-webkit-datetime-edit-year-field {
      color: var(--text-color);
    }
    .floating-label input[type="date"]::-webkit-calendar-picker-indicator {
      filter: {% if config.theme == 'dark' %}invert(1){% else %}none{% endif %};
    }


    /* Buttons */
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
    .btn-warning {
      background-color: var(--warning-color);
      border-color: var(--warning-color);
      color: white;
    }
    .btn-warning:hover {
      background-color: var(--warning-color-dark);
      border-color: var(--warning-color-dark);
      box-shadow: var(--shadow-medium);
    }
    .btn-danger {
      background-color: var(--danger-color);
      border-color: var(--danger-color);
      color: white;
    }
    .btn-danger:hover {
      background-color: var(--danger-color-dark);
      border-color: var(--danger-color-dark);
      box-shadow: var(--shadow-medium);
    }
    .btn-info { /* WhatsApp button */
      background-color: #25D366;
      border-color: #25D366;
      color: white;
    }
    .btn-info:hover {
      background-color: #1DA851;
      border-color: #1DA851;
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
    .btn-secondary {
      background-color: var(--secondary-color);
      border-color: var(--secondary-color);
      color: var(--button-text);
    }
    .btn-secondary:hover {
      background-color: var(--secondary-color-dark);
      border-color: var(--secondary-color-dark);
      box-shadow: var(--shadow-medium);
    }
    .btn-sm {
      padding: 0.5rem 0.8rem;
      font-size: 0.875rem;
    }

    /* Styles for navigation tabs */
    .nav-tabs {
      border-bottom: none;
      margin-bottom: 1rem;
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 1rem; /* Increased gap for more spacing between tabs */
    }

    .nav-tabs .nav-item {
      flex-grow: 1;
      text-align: center;
      flex-basis: auto;
      max-width: 250px; /* Increased max-width significantly */
    }

    .nav-tabs .nav-link {
      border: none;
      color: var(--text-color-light);
      font-weight: 500;
      font-size: 1.5rem; /* Kept font size as requested */
      padding: 0.8rem 1.2rem; /* Kept padding as requested */
      transition: all 0.2s ease;
      position: relative;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .nav-tabs .nav-link i {
      font-size: 1.7rem; /* Kept icon size as requested */
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

    /* Styles for form fields */
    .form-control,
    .form-select,
    textarea {
      background-color: var(--card-bg);
      color: var(--text-color);
      border: 1px solid var(--secondary-color);
      border-radius: var(--border-radius-sm);
    }

    .form-control:focus,
    .form-select:focus,
    textarea:focus {
      border-color: var(--primary-color);
      box-shadow: 0 0 0 0.25rem rgba(var(--primary-color-rgb), 0.25);
      background-color: var(--card-bg);
      color: var(--text-color);
    }

    .dynamic-list {
      border: 2px solid var(--secondary-color);
      border-radius: var(--border-radius-sm);
      transition: border-color 0.2s ease;
    }

    .dynamic-list:focus {
      border-color: var(--primary-color);
    }

    .icon-pulse {
      animation: pulse 1.5s infinite;
    }

    @keyframes pulse {
      0% { transform: scale(1); }
      50% { transform: scale(1.05); }
      100% { transform: scale(1); }
    }

    .btn-medical {
      background: var(--gradient-main);
      border: none;
      color: var(--button-text) !important;
      box-shadow: var(--shadow-light);
      transition: all 0.3s ease;
    }

    .btn-medical:hover {
      box-shadow: var(--shadow-medium);
      opacity: 0.9;
    }

    /* Styles for main card header */
    .card-header {
      background: var(--gradient-main);
      color: var(--button-text);
    }
    .card-header h1,
    .card-header .header-item,
    .card-header p {
      font-size: 1.8rem !important;
      color: var(--button-text) !important;
    }
    .card-header h1 i,
    .card-header .header-item i,
    .card-header p i {
      font-size: 1.8rem !important;
      color: var(--button-text) !important;
    }

    /* Styles for follow-up table */
    #consultationsTable {
      color: var(--text-color);
    }

    #consultationsTable thead {
      background-color: var(--primary-color);
      color: var(--button-text);
    }

    #consultationsTable tbody tr {
      background-color: var(--card-bg);
    }

    #consultationsTable tbody tr:nth-child(odd) {
      background-color: var(--table-striped-bg);
    }

    #consultationsTable tbody tr:hover {
      background-color: rgba(var(--primary-color-rgb), 0.05) !important;
    }

    /* Footer */
    .card-footer {
      background: var(--gradient-main);
      color: white;
      font-weight: 300;
      box-shadow: 0 -5px 15px rgba(0, 0, 0, 0.1);
      padding-top: 0.75rem; /* Reduced padding */
      padding-bottom: 0.75rem; /* Reduced padding */
    }
    .card-footer p {
        margin-bottom: 0.25rem; /* Reduced margin for paragraphs */
    }

    /* Modals */
    .modal-content {
      background-color: var(--card-bg);
      color: var(--text-color);
      border-radius: var(--border-radius-lg);
      box-shadow: var(--shadow-medium);
    }

    .modal-header {
      background: var(--gradient-main);
      color: var(--button-text);
      border-top-left-radius: var(--border-radius-lg);
      border-top-right-radius: var(--border-radius-lg);
    }
    .modal-title {
      color: var(--button-text);
    }
    .btn-close {
      filter: invert(1);
    }
    /* DataTables specific styles for inputs and selects */
    #consultationsTable_wrapper .dataTables_filter input,
    #consultationsTable_wrapper .dataTables_length select {
      border-radius: var(--border-radius-sm);
      border: 1px solid var(--secondary-color);
      padding: 0.5rem 0.75rem;
      background-color: var(--card-bg);
      color: var(--text-color);
    }
    #consultationsTable_wrapper .dataTables_filter input:focus,
    #consultationsTable_wrapper .dataTables_length select:focus {
      border-color: var(--primary-color);
      box-shadow: 0 0 0 0.25rem rgba(var(--primary-color-rgb), 0.25);
    }
    /* Hide the dropdown arrow for DataTables length select */
    #consultationsTable_wrapper .dataTables_length select {
      -webkit-appearance: none;
      -moz-appearance: none;
      appearance: none;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath fill='none' stroke='%23333' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M2 5l6 6 6-6'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: right 0.75rem center;
      background-size: 0.65em auto;
      padding-right: 2rem;
    }
    body.dark-theme #consultationsTable_wrapper .dataTables_length select {
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath fill='none' stroke='%23fff' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M2 5l6 6 6-6'/%3E%3C/svg%3E");
    }

    #consultationsTable_wrapper .dataTables_paginate .pagination .page-item .page-link {
      border-radius: var(--border-radius-sm);
      margin: 0 0.2rem;
      background-color: var(--card-bg);
      color: var(--text-color);
      border: 1px solid var(--secondary-color);
    }
    #consultationsTable_wrapper .dataTables_paginate .pagination .page-item.active .page-link {
      background: var(--gradient-main);
      border-color: var(--primary-color);
      color: var(--button-text);
    }
    #consultationsTable_wrapper .dataTables_paginate .pagination .page-item .page-link:hover {
      background-color: rgba(var(--primary-color-rgb), 0.1);
      color: var(--primary-color);
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
      .nav-tabs .nav-link {
        font-size: 1.1rem; /* Adjusted for smaller screens */
        padding: 0.5rem 0.7rem;
      }
      .nav-tabs .nav-link i {
        font-size: 1.2rem; /* Adjusted for smaller screens */
      }
      .btn {
        width: 100%;
        margin-bottom: 0.5rem;
      }
      .d-flex.gap-2 {
        flex-direction: column;
      }
      .dataTables_filter, .dataTables_length {
        text-align: center !important;
      }
      .dataTables_filter input, .dataTables_length select {
        width: 100%;
        margin-bottom: 0.5rem;
      }
    }
  </style>

</head>
<body>
<nav class="navbar navbar-dark fixed-top">
  <div class="container-fluid d-flex align-items-center">
    <button class="navbar-toggler" type="button" data-bs-toggle="offcanvas" data-bs-target="#settingsOffcanvas">
      <i class="fas fa-bars"></i>
    </button>
    <a class="navbar-brand ms-auto d-flex align-items-center"
       href="{{ url_for('accueil.accueil') }}">
      <i class="fas fa-home me-2"></i>
      <i class="fas fa-heartbeat me-2"></i>EasyMedicaLink
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
    <form id="settingsForm" action="{{ url_for('settings') }}" method="POST">
      <div class="mb-3 floating-label">
        <textarea class="form-control" name="liste_medicaments" id="liste_medicaments" rows="4" placeholder=" ">{% if config.medications_options %}{{ config.medications_options|join('\\n') }}{% endif %}</textarea>
        <label for="liste_medicaments">Liste des Médicaments</label>
      </div>
      <div class="mb-3 floating-label">
        <textarea class="form-control" name="liste_analyses" id="liste_analyses" rows="4" placeholder=" ">{% if config.analyses_options %}{{ config.analyses_options|join('\\n') }}{% endif %}</textarea>
        <label for="liste_analyses">Liste des Analyses</label>
      </div>
      <div class="mb-3 floating-label">
        <textarea class="form-control" name="liste_radiologies" id="liste_radiologies" rows="4" placeholder=" ">{% if config.radiologies_options %}{{ config.radiologies_options|join('\\n') }}{% endif %}</textarea>
        <label for="liste_radiologies">Liste des Radiologies</label>
      </div>
      <button type="submit" class="btn btn-success w-100">
        <i class="fas fa-save me-2"></i>Enregistrer
      </button>
    </form>
  </div>
</div>

<div class="container my-4">
  <div class="row justify-content-center">
    <div class="col-12">
      <div class="card shadow-lg">
        <div class="card-header text-center">
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
          <p class="mt-2 header-item">
            <i class="fas fa-calendar-day me-2"></i>{{ current_date }} {# Calendar Icon (original color) #}
          </p>
          <p class="mt-2 header-item">
            <i class="fas fa-stethoscope me-2"></i>Consultation {# Stethoscope Icon (original color) #}
          </p>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="container my-4">
  <div class="card shadow-lg">
    <div class="card-body">
      <form method="POST" enctype="multipart/form-data" id="mainForm">
        <ul class="nav nav-tabs justify-content-center" id="myTab" role="tablist">
          <li class="nav-item" role="presentation">
            <button class="nav-link active" id="basic-info-tab" data-bs-toggle="tab" data-bs-target="#basic-info">
              <i class="fas fa-user-injured me-2" style="color: #007BFF;"></i>Infos Base {# Blue User Injured Icon #}
            </button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="consultation-tab" data-bs-toggle="tab" data-bs-target="#consultation">
              <i class="fas fa-stethoscope me-2" style="color: #20B2AA;"></i>Diagnostique {# Light Sea Green Stethoscope Icon #}
            </button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="medicaments-tab" data-bs-toggle="tab" data-bs-target="#medicaments">
              <i class="fas fa-pills me-2" style="color: #4CAF50;"></i>Médicaments {# Green Pills Icon #}
            </button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="biologie-tab" data-bs-toggle="tab" data-bs-target="#biologie">
              <i class="fas fa-dna me-2" style="color: #DA70D6;"></i>Biologie {# Orchid DNA Icon #}
            </button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="radiologies-tab" data-bs-toggle="tab" data-bs-target="#radiologies">
              <i class="fas fa-x-ray me-2" style="color: #8A2BE2;"></i>Radiologies {# Blue Violet X-Ray Icon #}
            </button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="certificat-tab" data-bs-toggle="tab" data-bs-target="#certificat">
              <i class="fas fa-file-medical me-2" style="color: #FFD700;"></i>Certificat {# Gold File Medical Icon #}
            </button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="suivi-tab" data-bs-toggle="tab" data-bs-target="#suivi">
              <i class="fas fa-history me-2" style="color: #FFC107;"></i>Suivi {# Amber History Icon #}
            </button>
          </li>
        </ul>

        <div class="tab-content py-3">
          <div class="tab-pane fade show active" id="basic-info" role="tabpanel">
                <div class="card shadow-lg mb-4">
                  <div class="card-body">
                    <div class="row g-3"> {# Nouvelle ligne pour aligner les champs #}
                      <div class="col-md-6 floating-label">
                        <input type="text" class="form-control" name="doctor_name" id="doctor_name"
                              list="doctors_list" placeholder=" ">
                        <label for="doctor_name"><i class="fas fa-user-md me-2" style="color: #ADD8E6;"></i>Médecin</label> {# Light Blue Doctor Icon #}
                        <datalist id="doctors_list">
                          {% for doc_name in doctors_for_select %}
                          <option value="{{ doc_name }}">
                          {% endfor %}
                        </datalist>
                      </div>
                      <div class="col-md-6 floating-label">
                        <input type="text" class="form-control" name="location" id="location"
                              value="{{ request.form.get('location', config.location if config.location is defined else '') }}" placeholder=" ">
                        <label for="location"><i class="fas fa-map-marker-alt me-2" style="color: #90EE90;"></i>Lieu</label> {# Light Green Map Marker Icon #}
                      </div>
                    </div>
                    <div class="row g-3"> {# Nouvelle ligne pour aligner les champs patient #}
                      <div class="col-md-6 floating-label">
                        <input type="text" class="form-control" name="patient_id" id="patient_id" list="patient_ids"
                              value="{{ request.form.get('patient_id', last_consult.get('patient_id','')) }}" placeholder=" ">
                        <label for="patient_id"><i class="fas fa-id-card me-2" style="color: #6C757D;"></i>ID Patient</label> {# Gray ID Card Icon #}
                        <datalist id="patient_ids">
                          {% for pid in patient_ids %}
                          <option value="{{ pid }}">
                          {% endfor %}
                        </datalist>
                      </div>
                      <div class="col-md-6 floating-label">
                        <input type="text" class="form-control" name="patient_name" id="patient_name" list="patient_names"
                              value="{{ request.form.get('patient_name', last_consult.get('patient_name','')) }}" placeholder=" ">
                        <label for="patient_name"><i class="fas fa-user-tag me-2" style="color: #17A2B8;"></i>Nom Complet</label> {# Cyan User Tag Icon #}
                        <datalist id="patient_names">
                          {% for name in patient_names %}
                          <option value="{{ name }}"></option>
                          {% endfor %}
                        </datalist>
                      </div>
                    </div>
                    {# Les autres champs de la section basic-info (date_of_birth, gender, patient_age, antecedents, patient_phone)
                      doivent également être encapsulés dans des 'row g-3' avec des 'col-md-X' appropriés
                      pour maintenir la cohérence du layout. Je les laisse tels quels pour cette modification ciblée,
                      but you should adjust them if necessary. #}
                    <div class="mb-3 floating-label">
                      <input type="date" class="form-control" name="date_of_birth" id="date_of_birth"
                            value="{{ request.form.get('date_of_birth', last_consult.get('date_of_birth','')) }}" placeholder=" ">
                      <label for="date_of_birth"><i class="fas fa-calendar-alt me-2" style="color: #FFB6C1;"></i>Date Naissance</label> {# Light Pink Calendar Icon #}
                    </div>
                    <div class="mb-3 floating-label">
                      <select name="gender" class="form-select" id="gender" placeholder=" ">
                        <option value="Masculin" {% if request.form.get('gender', last_consult.get('gender','')) == 'Masculin' %}selected{% endif %}>Masculin</option>
                        <option value="Féminin"   {% if request.form.get('gender', last_consult.get('gender','')) == 'Féminin'   %}selected{% endif %}>Féminin</option>
                        <option value="Autre"      {% if request.form.get('gender', last_consult.get('gender','')) == 'Autre'      %}selected{% endif %}>Autre</option>
                      </select>
                      <label for="gender"><i class="fas fa-venus-mars me-2" style="color: #6A5ACD;"></i>Genre</label> {# Slate Blue Venus-Mars Icon #}
                    </div>
                    <div class="mb-3 floating-label">
                      <input type="text" class="form-control" name="patient_age" id="patient_age"
                            value="{{ request.form.get('patient_age', last_consult.get('age','')) }}" placeholder=" ">
                      <label for="patient_age"><i class="fas fa-calendar-day me-2" style="color: #FFC107;"></i>Âge</label> {# Amber Calendar Day Icon #}
                    </div>
                    <div class="mb-3 floating-label">
                      <input type="text" class="form-control" name="antecedents" id="antecedents"
                            value="{{ request.form.get('antecedents', last_consult.get('antecedents','')) }}" placeholder=" ">
                      <label for="antecedents"><i class="fas fa-file-medical me-2" style="color: #DA70D6;"></i>Antécédents</label> {# Orchid File Medical Icon #}
                    </div>
                    <div class="mb-3 floating-label">
                      <input type="text" class="form-control" name="patient_phone" id="patient_phone"
                            value="{{ request.form.get('patient_phone', last_consult.get('patient_phone','')) }}" placeholder=" ">
                      <label for="patient_phone"><i class="fas fa-phone me-2" style="color: #28A745;"></i>Téléphone</label> {# Green Phone Icon #}
                    </div>
                  </div>
                </div>
              </div>

          <div class="tab-pane fade" id="consultation" role="tabpanel">
            <div class="card shadow-lg mb-4">
              <div class="card-body">
                <div class="mb-3 floating-label">
                  <textarea class="form-control" name="clinical_signs" id="clinical_signs" rows="2" placeholder=" ">{{ request.form.get('clinical_signs', '') }}</textarea>
                  <label for="clinical_signs"><i class="fas fa-notes-medical me-2" style="color: #FF69B4;"></i>Signes Cliniques</label> {# Pink Notes Medical Icon #}
                </div>
                <div class="row mb-3 g-3">
                  <div class="col-sm-6 floating-label">
                    <input type="text" class="form-control" name="bp" id="bp" value="{{ request.form.get('bp', '') }}" placeholder=" ">
                    <label for="bp"><i class="fas fa-heartbeat me-2" style="color: #DC143C;"></i>Tension (mmHg)</label> {# Crimson Heartbeat Icon #}
                  </div>
                  <div class="col-sm-6 floating-label">
                    <input type="text" class="form-control" name="temperature" id="temperature" value="{{ request.form.get('temperature', '') }}" placeholder=" ">
                    <label for="temperature"><i class="fas fa-thermometer-half me-2" style="color: #FFD700;"></i>Température (°C)</label> {# Gold Thermometer Icon #}
                  </div>
                </div>
                <div class="row mb-3 g-3">
                  <div class="col-sm-6 floating-label">
                    <input type="text" class="form-control" name="heart_rate" id="heart_rate" value="{{ request.form.get('heart_rate', '') }}" placeholder=" ">
                    <label for="heart_rate"><i class="fas fa-heart me-2" style="color: #FF69B4;"></i>FC (bpm)</label> {# Pink Heart Icon #}
                  </div>
                  <div class="col-sm-6 floating-label">
                    <input type="text" class="form-control" name="respiratory_rate" id="respiratory_rate" value="{{ request.form.get('respiratory_rate', '') }}" placeholder=" ">
                    <label for="respiratory_rate"><i class="fas fa-lungs me-2" style="color: #8A2BE2;"></i>FR (rpm)</label> {# Blue Violet Lungs Icon #}
                  </div>
                </div>
                <div class="mb-3 floating-label">
                  <input type="text" class="form-control" name="diagnosis" id="diagnosis" value="{{ request.form.get('diagnosis', '') }}" placeholder=" ">
                  <label for="diagnosis"><i class="fas fa-diagnoses me-2" style="color: #6A5ACD;"></i>Diagnostic</label> {# Slate Blue Diagnoses Icon #}
                </div>
                <div class="mb-3 floating-label">
                  <textarea class="form-control" name="doctor_comment" id="doctor_comment" rows="3" placeholder=" ">{{ request.form.get('doctor_comment', '') }}</textarea>
                  <label for="doctor_comment"><i class="fas fa-comment-medical me-2" style="color: #17A2B8;"></i>Commentaire</label> {# Cyan Comment Medical Icon #}
                </div>
              </div>
            </div>
          </div>

          <div class="tab-pane fade" id="medicaments" role="tabpanel">
            <div class="card shadow-lg mb-4">
              <div class="card-body">
                <div class="mb-3">
                  <label for="medication_combobox" class="form-label"><i class="fas fa-prescription-bottle-alt me-2" style="color: #4CAF50;"></i>Médicament</label> {# Green Prescription Bottle Icon #}
                  <div class="input-group">
                    <input type="text" class="form-control" id="medication_combobox" placeholder="Sélectionnez un médicament" list="medications_options_list">
                    <datalist id="medications_options_list">
                      {# Assurez-vous que 'medications_options' est une liste de chaînes de caractères depuis le backend Flask #}
                      {% for m in medications_options %}
                      <option value="{{ m }}"></option>
                      {% endfor %}
                    </datalist>
                    <button type="button" class="btn btn-primary" onclick="addMedication()">
                      <i class="fas fa-plus-circle me-2" style="color: #FFFFFF;"></i>Ajouter {# White Plus Circle Icon #}
                    </button>
                  </div>
                  <select id="medications_listbox" name="medications_list" multiple class="form-select mt-2 dynamic-list" size="5">
                    {% if saved_medications %}
                      {% for med in saved_medications %}
                        <option selected value="{{ med }}">{{ loop.index }}. {{ med }}</option>
                      {% endfor %}
                    {% endif %}
                  </select>
                  <button type="button" class="btn btn-danger mt-2" onclick="removeMedication()">
                    <i class="fas fa-trash-alt me-2" style="color: #FFFFFF;"></i>Supprimer Sélection {# White Trash Alt Icon #}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="tab-pane fade" id="biologie" role="tabpanel">
            <div class="card shadow-lg mb-4">
              <div class="card-body">
                <div class="mb-3">
                  <label for="analysis_combobox" class="form-label"><i class="fas fa-microscope me-2" style="color: #DA70D6;"></i>Analyse</label> {# Orchid Microscope Icon #}
                  <div class="input-group">
                    <input type="text" class="form-control" id="analysis_combobox" placeholder="Sélectionnez une analyse" list="analyses_options_list">
                    <datalist id="analyses_options_list">
                      {# Assurez-vous que 'analyses_options' est une liste de chaînes de caractères depuis le backend Flask #}
                      {% for a in analyses_options %}
                      <option value="{{ a }}"></option>
                      {% endfor %}
                    </datalist>
                    <button type="button" class="btn btn-primary" onclick="addAnalysis()">
                      <i class="fas fa-plus-circle me-2" style="color: #FFFFFF;"></i>Ajouter {# White Plus Circle Icon #}
                    </button>
                  </div>
                  <select id="analyses_listbox" name="analyses_list" multiple class="form-select mt-2 dynamic-list" size="5">
                    {% if saved_analyses %}
                      {% for a in saved_analyses %}
                        <option selected value="{{ a }}">{{ loop.index }}. {{ a }}</option>
                      {% endfor %}
                    {% endif %}
                  </select>
                  <button type="button" class="btn btn-danger mt-2" onclick="removeAnalysis()">
                    <i class="fas fa-trash-alt me-2" style="color: #FFFFFF;"></i>Supprimer Sélection {# White Trash Alt Icon #}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="tab-pane fade" id="radiologies" role="tabpanel">
            <div class="card shadow-lg mb-4">
              <div class="card-body">
                <div class="mb-3">
                  <label for="radiology_combobox" class="form-label"><i class="fas fa-x-ray me-2" style="color: #8A2BE2;"></i>Radiologie</label> {# Blue Violet X-Ray Icon #}
                  <div class="input-group">
                    <input type="text" class="form-control" id="radiology_combobox" placeholder="Sélectionnez une radiologie" list="radiologies_options_list">
                    <datalist id="radiologies_options_list">
                      {# Assurez-vous que 'radiologies_options' est une liste de chaînes de caractères depuis le backend Flask #}
                      {% for r in radiologies_options %}
                      <option value="{{ r }}"></option>
                      {% endfor %}
                    </datalist>
                    <button type="button" class="btn btn-primary" onclick="addRadiology()">
                      <i class="fas fa-plus-circle me-2" style="color: #FFFFFF;"></i>Ajouter {# White Plus Circle Icon #}
                    </button>
                  </div>
                  <select id="radiologies_listbox" name="radiologies_list" multiple class="form-select mt-2 dynamic-list" size="5">
                    {% if saved_radiologies %}
                      {% for r in saved_radiologies %}
                        <option selected value="{{ r }}">{{ loop.index }}. {{ r }}</option>
                      {% endfor %}
                    {% endif %}
                  </select>
                  <button type="button" class="btn btn-danger mt-2" onclick="removeRadiology()">
                    <i class="fas fa-trash-alt me-2" style="color: #FFFFFF;"></i>Supprimer Sélection {# White Trash Alt Icon #}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="tab-pane fade" id="certificat" role="tabpanel">
            <div class="card shadow-lg mb-4">
              <div class="card-body">
                <div class="mb-3 floating-label">
                  <select class="form-select" name="certificate_category" id="certificate_category" placeholder=" ">
                    <option value="">-- Sélectionnez --</option>
                    {% for key in certificate_categories.keys() %}
                    <option value="{{ key }}" {% if request.form.get('certificate_category','') == key %}selected{% endif %}>{{ key }}</option>
                    {% endfor %}
                  </select>
                  <label for="certificate_category"><i class="fas fa-tags me-2" style="color: #FFD700;"></i>Catégorie</label> {# Gold Tags Icon #}
                </div>
                <div class="mb-3 floating-label">
                  <textarea class="form-control" name="certificate_content" id="certificate_content" rows="5" placeholder=" ">{{ (request.form.get('certificate_content', default_certificate_text) | replace('_x000D_', '')) }}</textarea>
                  <label for="certificate_content"><i class="fas fa-file-alt me-2" style="color: #007BFF;"></i>Contenu</label> {# Blue File Alt Icon #}
                </div>
                <div class="form-check">
                  <input class="form-check-input" type="checkbox" name="include_certificate" id="include_certificate" {% if request.form.get('include_certificate','')=='on' %}checked{% endif %}>
                  <label class="form-check-label" for="include_certificate">
                    <i class="fas fa-check-circle me-2" style="color: #28A745;"></i>Inclure le certificat {# Green Check Circle Icon #}
                  </label>
                </div>
              </div>
            </div>
          </div>

          <div class="tab-pane fade" id="suivi" role="tabpanel" aria-labelledby="suivi-tab">
            <div class="card shadow-lg mb-4">
              <div class="card-header">
                <h5 class="mb-0"><i class="fas fa-notes-medical me-2" style="color: #FF69B4;"></i>Suivi Patient</h5> {# Pink Notes Medical Icon #}
              </div>
              <div class="card-body">
                <div class="mb-4 row g-3">
                  <div class="col-md-6 floating-label">
                    <input type="text" id="suivi_patient_id" class="form-control" placeholder=" ">
                    <label for="suivi_patient_id">ID Patient</label>
                  </div>
                  <div class="col-md-6 floating-label">
                    <input type="text" id="suivi_patient_name" class="form-control" placeholder=" " readonly> {# AJOUT DE readonly ICI #}
                    <label for="suivi_patient_name">Nom Patient</label>
                  </div>
                </div>
                <div class="table-responsive rounded-lg overflow-auto" style="max-height:400px;">
                  <table id="consultationsTable"
                        class="table table-striped table-hover align-middle mb-0"
                        style="min-width:1200px;">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>ID</th>
                        <th>Nom Complet</th>
                        <th>Date Naissance</th>
                        <th>Sexe</th>
                        <th>Âge</th>
                        <th>Téléphone</th>
                        <th>Antécédents</th>
                        <th>Signes Cliniques</th>
                        <th>TA</th>
                        <th>Temp.</th>
                        <th>FC</th>
                        <th>FR</th>
                        <th>Diagnostic</th>
                        <th>Médicaments</th>
                        <th>Analyses</th>
                        <th>Radiologies</th>
                        <th>Catégorie Certif.</th>
                        <th>Durée Repos</th>
                        <th>Commentaire</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody></tbody>
                  </table>
                </div>

                <div class="card mt-4">
                  <div class="card-body d-flex justify-content-around flex-wrap gap-2">
                    <button type="button" id="refreshBtn" class="btn btn-primary"
                             onclick="refreshSuiviTab()">
                      <i class="fas fa-sync-alt me-2" style="color: #FFFFFF;"></i>Rafraîchir {# White Sync Alt Icon #}
                    </button>
                    <button type="button" class="btn btn-outline-success" onclick="generateHistoryPDF()">
                      <i class="fas fa-file-pdf me-2" style="color: #28A745;"></i>Historique Patient {# Green File PDF Icon #}
                    </button>
                  </div>
                </div>

              </div>
            </div>
          </div>
        </div>

        <div class="d-flex flex-wrap justify-content-around gap-2 mt-4 mb-5">
          <button
            type="button"
            id="submitBtn"
            class="btn btn-primary"
          >
            <i class="fas fa-save me-2" style="color: #FFFFFF;"></i>Enregistrer {# White Save Icon #}
          </button>
          <button
            type="reset"
            class="btn btn-danger"
          >
            <i class="fas fa-undo me-2" style="color: #FFFFFF;"></i>Réinitialiser {# White Undo Icon #}
          </button>
          <button
            type="button"
            class="btn btn-primary"
            onclick="generatePDF()"
          >
            <i class="fas fa-file-pdf me-2" style="color: #FFFFFF;"></i>Prescriptions PDF {# White File PDF Icon #}
          </button>
        </div>

<div class="card-footer text-center py-3">
  <div style="margin-bottom: 0 !important;">
  <p class="small mb-1" style="color: white;">
    <i class="fas fa-heartbeat me-1" style="color: #FF69B4;"></i>
    SASTOUKA DIGITAL © 2025 • sastoukadigital@gmail.com tel +212652084735
  </p>

  <p class="small mb-0" style="color: white;">
   Ouvrir l’application en réseau {{ host_address }}
  </p>
</div>

<div class="modal fade" id="importExcelModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title"><i class="fas fa-file-excel me-2"></i>Importer Excel</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <form id="importExcelForm" onsubmit="return ajaxFileUpload('importExcelForm','/import_excel')">
          <div class="mb-3">
            <label for="excel_file" class="form-label"><i class="fas fa-file-excel me-2"></i>Fichier Excel</label>
            <input type="file" class="form-control" name="excel_file" id="excel_file" required>
          </div>
          <div class="modal-footer">
            <button type="submit" class="btn btn-primary"><i class="fas fa-upload me-2"></i>Importer</button>
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</div>

<div class="modal fade" id="importBackgroundModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title"><i class="fas fa-image me-2"></i>Logo/Arrière-plan</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <form id="importBackgroundForm" onsubmit="return ajaxFileUpload('importBackgroundForm','/import_background')">
          <div class="mb-3">
            <label for="background_file" class="form-label"><i class="fas fa-file-image me-2"></i>Fichier</label>
            <input type="file" class="form-control" name="background_file" id="background_file" required>
          </div>
          <div class="modal-footer">
            <button type="submit" class="btn btn-primary"><i class="fas fa-upload me-2"></i>Importer</button>
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</div>

<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.datatables.net/1.13.1/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.1/js/dataTables.bootstrap5.min.js"></script>
<script>
  // Patient data from Flask backend
  var patientData = {{ patient_data|tojson }};
  var certificateTemplates = {{ certificate_categories|tojson }};

  console.log("Frontend: patientData au chargement:", patientData);

  document.addEventListener("DOMContentLoaded", function() {
    // Initialisation des compteurs pour les listes dynamiques
    window.medicationCount = 1;
    window.analysisCount = 1;
    window.radiologyCount = 1;

    // Gestion de la persistance des onglets
    const triggerTabList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tab"]'));
    triggerTabList.forEach(function (triggerEl) {
        const tabTrigger = new bootstrap.Tab(triggerEl);
        triggerEl.addEventListener('click', function (event) {
            event.preventDefault();
            tabTrigger.show();
        });
    });

    // --- MODIFICATION ICI: Supprimer ou commenter la logique de persistance des onglets ---
    // const activeTab = localStorage.getItem('activeTab');
    // if (activeTab) {
    //     const triggerEl = document.querySelector(`[data-bs-target="${activeTab}"]`);
    //     if (triggerEl) bootstrap.Tab.getOrCreateInstance(triggerEl).show();
    // }

    // Toujours activer le premier onglet ("Infos Base") au chargement de la page
    const firstTabTriggerEl = document.querySelector('[data-bs-target="#basic-info"]');
    if (firstTabTriggerEl) {
        bootstrap.Tab.getOrCreateInstance(firstTabTriggerEl).show();
    }
    // --- FIN DE LA MODIFICATION ---

    document.querySelectorAll('[data-bs-toggle="tab"]').forEach(function(tabEl) {
        tabEl.addEventListener('shown.bs.tab', function(event) {
            // Optionnel: Si vous voulez toujours enregistrer le dernier onglet visité MAIS NE PAS L'ACTIVER au rechargement
            // localStorage.setItem('activeTab', event.target.getAttribute('data-bs-target'));
            
            // Rafraîchir le tableau de suivi si l'onglet "Suivi" est activé
            if (event.target.id === 'suivi-tab') {
                $('#consultationsTable').DataTable().ajax.reload();
            }
        });
    });


    // Gestion du changement de catégorie de certificat
    document.getElementById("certificate_category").addEventListener("change", function() {
      var cat = this.value;
      if(certificateTemplates[cat]) { document.getElementById("certificate_content").value = certificateTemplates[cat]; }
    });

    // Gestion des événements "Enter" pour les combobox (médicaments, analyses, radiologies)
    document.querySelectorAll("#medication_combobox, #analysis_combobox, #radiology_combobox").forEach(function(input) {
      input.addEventListener("keydown", function(e) {
        if (e.key === "Enter") {
          e.preventDefault();
          if (this.id === "medication_combobox") addMedication();
          else if (this.id === "analysis_combobox") addAnalysis();
          else if (this.id === "radiology_combobox") addRadiology();
        }
      });
    });

    // Gestion du bouton de soumission principal avec SweetAlert
    document.getElementById("submitBtn").addEventListener("click", function(e) {
      e.preventDefault();
      Swal.fire({
        title: 'Vérification des onglets',
        text: "Avez-vous parcouru tous les onglets (Consultation, Médicaments, Biologie, Radiologies, Certificats) ?",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Oui, je confirme',
        cancelButtonText: 'Non, vérifier'
      }).then((result) => {
        if (result.isConfirmed) {
          document.querySelectorAll("#medications_listbox option").forEach(function(option) { option.selected = true; });
          document.querySelectorAll("#analyses_listbox option").forEach(function(option) { option.selected = true; });
          document.querySelectorAll("#radiologies_listbox option").forEach(function(option) { option.selected = true; });
          document.getElementById("mainForm").submit();
        }
      });
    });

    // Gestion de la mise à jour des champs patient lors de la sélection/saisie de l'ID patient dans l'onglet "Infos Base"
    document.getElementById("patient_id").addEventListener("change", function() {
      var id = this.value.trim();
      var id = this.value.trim();
      console.log("Frontend: patientData[id] lookup result (Infos Base):", patientData[id]);

      if(patientData[id]){
        document.getElementById("patient_name").value = patientData[id].name || '';
        document.getElementById("patient_age").value = patientData[id].age || '';
        document.getElementById("patient_phone").value = patientData[id].phone || '';
        document.getElementById("antecedents").value = patientData[id].antecedents || '';
        document.getElementById("date_of_birth").value = patientData[id].date_of_birth || '';
        document.getElementById("gender").value = patientData[id].gender || '';
        
        // Mettre à jour les champs de l'onglet Suivi
        document.getElementById("suivi_patient_id").value = id;
        document.getElementById("suivi_patient_name").value = patientData[id].name || '';
        // Pas de reload DataTable ici, car le changement de tab le fera si nécessaire.
        
      } else {
        console.log("Frontend: Aucune donnée de base trouvée pour cet ID dans patientData (Infos Base):", id);
        document.getElementById("patient_name").value = "";
        document.getElementById("patient_age").value = "";
        document.getElementById("patient_phone").value = "";
        document.getElementById("antecedents").value = "";
        document.getElementById("date_of_birth").value = "";
        document.getElementById("gender").value = "";

        // Réinitialiser les champs de l'onglet Suivi si l'ID n'est pas trouvé
        document.getElementById("suivi_patient_id").value = "";
        document.getElementById("suivi_patient_name").value = "";
      }

      // Récupération de la dernière consultation pour cet ID (pour remplir les champs de consultation)
      if(id){
        fetch("/get_last_consultation?patient_id=" + id)
        .then(response => response.json())
        .then(data => {
          console.log("Données de la dernière consultation:", data);
          if(Object.keys(data).length !== 0){
            document.getElementById("clinical_signs").value = data.clinical_signs || "";
            document.getElementById("bp").value = data.bp || "";
            document.getElementById("temperature").value = data.temperature || "";
            document.getElementById("heart_rate").value = data.heart_rate || "";
            document.getElementById("respiratory_rate").value = data.respiratory_rate || "";
            document.getElementById("diagnosis").value = data.diagnosis || "";

            var medications_listbox = document.getElementById("medications_listbox");
            medications_listbox.innerHTML = "";
            window.medicationCount = 1;
            if(data.medications){
              data.medications.split("; ").forEach((item)=>{
                if (item.trim() !== "") {
                  var option = document.createElement("option");
                  option.text = window.medicationCount + ". " + item.trim();
                  option.value = item.trim();
                  medications_listbox.add(option);
                  window.medicationCount++;
                }
              });
            }

            var analyses_listbox = document.getElementById("analyses_listbox");
            analyses_listbox.innerHTML = "";
            window.analysisCount = 1;
            if(data.analyses){
              data.analyses.split("; ").forEach((item)=>{
                if (item.trim() !== "") {
                  var option = document.createElement("option");
                  option.text = window.analysisCount + ". " + item.trim();
                  option.value = item.trim();
                  analyses_listbox.add(option);
                  window.analysisCount++;
                }
              });
            }

            var radiologies_listbox = document.getElementById("radiologies_listbox");
            radiologies_listbox.innerHTML = "";
            window.radiologyCount = 1;
            if(data.radiologies){
              data.radiologies.split("; ").forEach((item)=>{
                if (item.trim() !== "") {
                  var option = document.createElement("option");
                  option.text = window.radiologyCount + ". " + item.trim();
                  option.value = item.trim();
                  radiologies_listbox.add(option);
                  window.radiologyCount++;
                }
              });
            }
            document.getElementById("certificate_category").value = data.certificate_category || "";
            document.getElementById("certificate_content").value = data.certificate_content || "";
            document.getElementById("doctor_comment").value = data.doctor_comment || "";
          } else {
            console.log("Aucune dernière consultation trouvée pour cet ID:", id);
            document.getElementById("clinical_signs").value = "";
            document.getElementById("bp").value = "";
            document.getElementById("temperature").value = "";
            document.getElementById("heart_rate").value = "";
            document.getElementById("respiratory_rate").value = "";
            document.getElementById("diagnosis").value = "";
            document.getElementById("medications_listbox").innerHTML = "";
            document.getElementById("analyses_listbox").innerHTML = "";
            document.getElementById("radiologies_listbox").innerHTML = "";
            document.getElementById("certificate_category").value = "";
            document.getElementById("certificate_content").value = certificateTemplates[""] || "";
            document.getElementById("doctor_comment").value = "";
            window.medicationCount = 1;
            window.analysisCount = 1;
            window.radiologyCount = 1;
          }
        })
        .catch(error => { console.error("Erreur lors de la récupération de la dernière consultation :", error); });
      }
    });

    // NOUVEL ÉCOUTEUR D'ÉVÉNEMENT POUR L'ONGLET SUIVI - ID PATIENT
    document.getElementById("suivi_patient_id").addEventListener("change", function() {
      var id = this.value.trim();
      console.log("Frontend Suivi: Patient ID modifié (onglet Suivi):", id);

      if (patientData[id]) {
        document.getElementById("suivi_patient_name").value = patientData[id].name || '';
      } else {
        document.getElementById("suivi_patient_name").value = "";
      }
      // Recharger la DataTable pour afficher les consultations du patient sélectionné par ID
      $('#consultationsTable').DataTable().ajax.reload();
    });

    // SUPPRIMER L'ÉCOUTEUR POUR 'suivi_patient_name' SI VOUS NE VOULEZ PAS QUE LA SAISIE DU NOM DÉCLENCHE L'ID
    // document.getElementById("suivi_patient_name").addEventListener("change", function() { ... });
    // Le champ est maintenant en lecture seule (readonly) pour renforcer ce comportement.


    // Calcul de l'âge à partir de la date de naissance
    document.getElementById("date_of_birth").addEventListener("change", function() {
      var dob = this.value;
      if (dob) {
        var birthDate = new Date(dob);
        var today = new Date();
        var ageYears = today.getFullYear() - birthDate.getFullYear();
        var m = today.getMonth() - birthDate.getMonth();
        if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
          ageYears--;
        }
        var ageMonths = today.getMonth() - birthDate.getMonth();
        if (today.getDate() < birthDate.getDate()) {
          ageMonths--;
        }
        ageMonths = (ageMonths + 12) % 12;
        var ageString = ageYears > 0 ? ageYears + " ans " + ageMonths + " mois" : ageMonths + " mois";
        document.getElementById("patient_age").value = ageString;
      } else {
        document.getElementById("patient_age").value = "";
      }
    });

    // Fonctions d'ajout/suppression pour les listes dynamiques (médicaments, analyses, radiologies)
    function updateListNumbers(listboxId) {
      var listbox = document.getElementById(listboxId);
      for (var i = 0; i < listbox.options.length; i++) {
        var parts = listbox.options[i].value.split(". ");
        var text = (parts.length > 1) ? parts.slice(1).join(". ") : listbox.options[i].value;
        listbox.options[i].text = (i + 1) + ". " + text;
      }
    }

    window.addMedication = function() {
      var combo = document.getElementById("medication_combobox");
      var listbox = document.getElementById("medications_listbox");
      var value = combo.value.trim();
      if (value !== "" && !Array.from(listbox.options).some(option => option.value === value)) {
        var option = document.createElement("option");
        option.text = window.medicationCount + ". " + value;
        option.value = value;
        listbox.add(option);
        window.medicationCount++;
        combo.value = "";
      }
    };

    window.removeMedication = function() {
      var listbox = document.getElementById("medications_listbox");
      for (var i = listbox.options.length - 1; i >= 0; i--) { if (listbox.options[i].selected) { listbox.remove(i); } }
      updateListNumbers("medications_listbox");
      window.medicationCount = listbox.options.length + 1;
    };

    window.addAnalysis = function() {
      var combo = document.getElementById("analysis_combobox");
      var listbox = document.getElementById("analyses_listbox");
      var value = combo.value.trim();
      if (value !== "" && !Array.from(listbox.options).some(option => option.value === value)) {
        var option = document.createElement("option");
        option.text = window.analysisCount + ". " + value;
        option.value = value;
        listbox.add(option);
        window.analysisCount++;
        combo.value = "";
      }
    };

    window.removeAnalysis = function() {
      var listbox = document.getElementById("analyses_listbox");
      for (var i = listbox.options.length - 1; i >= 0; i--) { if (listbox.options[i].selected) { listbox.remove(i); } }
      updateListNumbers("analyses_listbox");
      window.analysisCount = listbox.options.length + 1;
    };

    window.addRadiology = function() {
      var combo = document.getElementById("radiology_combobox");
      var listbox = document.getElementById("radiologies_listbox");
      var value = combo.value.trim();
      if (value !== "" && !Array.from(listbox.options).some(option => option.value === value)) {
        var option = document.createElement("option");
        option.text = window.radiologyCount + ". " + value;
        option.value = value;
        listbox.add(option);
        window.radiologyCount++;
        combo.value = "";
      }
    };

    window.removeRadiology = function() {
      var listbox = document.getElementById("radiologies_listbox");
      for (var i = listbox.options.length - 1; i >= 0; i--) { if (listbox.options[i].selected) { listbox.remove(i); } }
      updateListNumbers("radiologies_listbox");
      window.radiologyCount = listbox.options.length + 1;
    };

    // Initialisation de la DataTable pour le suivi patient
    var consultationsTable = $('#consultationsTable').DataTable({
      ajax: {
        url: "/get_consultations",
        data: function(d) {
          d.patient_id = $('#suivi_patient_id').val(); // Seul le patient_id sera utilisé pour le filtrage
          // Le patient_name n'est plus un critère de filtre envoyée au backend depuis le frontend
          // car la source de vérité est l'ID.
        },
        dataSrc: ''
      },
      columns: [
        { data: "consultation_date", title: "Date" },
        { data: "patient_id", title: "ID" },
        { data: "patient_name", title: "Nom Complet" },
        { data: "date_of_birth", title: "Date Naissance" },
        { data: "gender", title: "Sexe" },
        { data: "age", title: "Âge" },
        { data: "patient_phone", title: "Téléphone" },
        { data: "antecedents", title: "Antécédents" },
        { data: "clinical_signs", title: "Signes Cliniques" },
        { data: "bp", title: "TA" },
        { data: "temperature", title: "Temp." },
        { data: "heart_rate", title: "FC" },
        { data: "respiratory_rate", title: "FR" },
        { data: "diagnosis", title: "Diagnostic" },
        { data: "medications", title: "Médicaments" },
        { data: "analyses", title: "Analyses" },
        { data: "radiologies", title: "Radiologies" },
        { data: "certificate_category", title: "Catégorie Certif." },
        { data: "rest_duration", title: "Durée Repos" },
        { data: "doctor_comment", title: "Commentaire" },
        {
          data: "consultation_id",
          title: "Actions",
          render: function(data, type, row, meta) {
            return '<button class="btn btn-sm btn-danger delete-btn" data-id="'+data+'">Supprimer</button>';
          }
        }
      ]
    });

    // Gestion de la suppression de consultation
    $('#consultationsTable tbody').on('click', '.delete-btn', function(e){
      e.preventDefault();
      var consultationId = $(this).data('id');
      Swal.fire({
        title: 'Êtes-vous sûr?',
        text: "Vous ne pourrez pas revenir en arrière!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Oui, supprimer!'
      }).then((result) => {
        if (result.isConfirmed) {
          $.ajax({
            url: '/delete_consultation',
            method: 'POST',
            data: { consultation_id: consultationId },
            success: function(response){
              consultationsTable.ajax.reload();
              Swal.fire('Supprimé!', 'La consultation a été supprimée.', 'success');
            },
            error: function(err){
              Swal.fire('Erreur', 'Erreur lors de la suppression.', 'error');
            }
          });
        }
      });
    });

    // Rafraîchir la table de consultation
    $('#refreshTableBtn').click(function(){
      consultationsTable.ajax.reload();
    });

    // Générer le PDF Historique
    window.generateHistoryPDF = function() {
       var id = document.getElementById("suivi_patient_id").value.trim();
       // Plus besoin de récupérer le nom, car le PDF est filtré uniquement par ID
       // var name = document.getElementById("suivi_patient_name").value.trim();
       
       if (!id) {
           Swal.fire({
               icon: 'warning',
               title: 'Attention',
               text: "Veuillez renseigner l'ID du patient pour générer l'historique."
           });
           return;
       }
       var params = new URLSearchParams();
       params.set("patient_id_filter", id); // Seulement l'ID est envoyé comme filtre
       
       var url = "{{ url_for('generate_history_pdf') }}" + "?" + params.toString();
       fetch(url, {
         method: 'GET',
         credentials: 'same-origin'
       })
       .then(resp => {
         if (!resp.ok) throw new Error("Erreur réseau ou fichier non trouvé");
         return resp.blob();
       })
       .then(blob => {
         const blobUrl = URL.createObjectURL(blob);
         const a = document.createElement('a');
         a.href = blobUrl;
         a.download = 'historique_consultations.pdf';
         document.body.appendChild(a);
         a.click();
         a.remove();
         URL.revokeObjectURL(blobUrl);
       })
       .catch(err => {
         console.error(err);
         Swal.fire('Erreur', 'Impossible de générer le PDF.', 'error');
       });
    };

    // Générer le PDF de la consultation actuelle
    window.generatePDF = function() {
      const doctor_name = document.getElementById("doctor_name").value;
      const patient_id = document.getElementById("patient_id").value; // Get patient ID for PDF
      const patient_name = document.getElementById("patient_name").value; // Nom complet
      const patient_age = document.getElementById("patient_age").value;
      const date_of_birth = document.getElementById("date_of_birth").value;
      const gender = document.getElementById("gender").value;
      const location = document.getElementById("location").value;
      const clinical_signs = document.getElementById("clinical_signs").value;
      const bp = document.getElementById("bp").value;
      const temperature = document.getElementById("temperature").value;
      const heart_rate = document.getElementById("heart_rate").value;
      const respiratory_rate = document.getElementById("respiratory_rate").value;
      const diagnosis = document.getElementById("diagnosis").value;
      const certificate_content = document.getElementById("certificate_content").value;
      const include_certificate = document.getElementById("include_certificate").checked ? "on" : "off";

      let medications = [];
      const medications_listbox = document.getElementById("medications_listbox");
      for (let option of medications_listbox.options) { medications.push(option.value); }
      let analyses = [];
      const analyses_listbox = document.getElementById("analyses_listbox");
      for (let option of analyses_listbox.options) { analyses.push(option.value); }
      let radiologies = [];
      const radiologies_listbox = document.getElementById("radiologies_listbox");
      for (let option of radiologies_listbox.options) { radiologies.push(option.value); }

      const params = new URLSearchParams();
      params.set("doctor_name", doctor_name);
      params.set("patient_id", patient_id); // Pass patient ID to PDF generation
      params.set("patient_name", patient_name);
      params.set("patient_age", patient_age);
      params.set("date_of_birth", date_of_birth);
      params.set("gender", gender);
      params.set("location", location);
      params.set("clinical_signs", clinical_signs);
      params.set("bp", bp);
      params.set("temperature", temperature);
      params.set("heart_rate", heart_rate);
      params.set("respiratory_rate", respiratory_rate);
      params.set("diagnosis", diagnosis);
      params.set("certificate_content", certificate_content);
      params.set("include_certificate", include_certificate);
      params.set("medications_list", medications.join("\\n"));
      params.set("analyses_list", analyses.join("\\n"));
      params.set("radiologies_list", radiologies.join("\\n"));

      const url = "{{ url_for('generate_pdf_route') }}" + "?" + params.toString();
      window.open(url, "_blank");
    };

    window.ajaxFileUpload = function(formId, endpoint) {
      var form = document.getElementById(formId);
      var formData = new FormData(form);
      fetch(endpoint, {
          method: "POST",
          body: formData
      })
      .then(response => response.json())
      .then(data => {
          Swal.fire({
              icon: data.status,
              title: data.status === "success" ? "Succès" : "Attention",
              text: data.message,
              timer: 2000,
              showConfirmButton: false
          });
          if (data.status === "success") {
              if (formId === "importExcelForm") {
                  $('#importExcelModal').modal('hide');
              } else if (formId === "importBackgroundForm") {
                  $('#importBackgroundModal').modal('hide');
              }
              setTimeout(() => window.location.reload(), 2100);
          }
      })
      .catch(error => {
          Swal.fire({
              icon: "error",
              title: "Erreur",
              text: error,
              timer: 2000,
              showConfirmButton: false
          });
      });
      return false;
    };

    document.getElementById("settingsForm").addEventListener("submit", function(e) {
      e.preventDefault();
      const form = this;
      const data = new FormData(form);

      fetch(form.action, {
        method: 'POST',
        body: data,
        headers: { 'Accept': 'application/json' }
      })
      .then(resp => {
        if (!resp.ok) throw new Error('Erreur réseau');
        return resp.json();
      })
      .then(json => {
        if (json.theme_vars) {
          Object.entries(json.theme_vars).forEach(([key, val]) => {
            document.documentElement.style.setProperty(`--${key}`, val);
          });
        }

        const headerH1 = document.querySelector('.card-header h1.header-item');
        if (headerH1) headerH1.innerHTML = `<i class="fas fa-hospital me-2"></i>${json.nom_clinique || ''}`;

        const doctorEl = document.querySelector('.card-header .header-item i.fa-user-md');
        if (doctorEl && doctorEl.parentNode) doctorEl.parentNode.innerHTML = `<i class="fas fa-user-md me-2"></i><span>${json.doctor_name || ''}</span>`;

        const locationEl = document.querySelector('.card-header .header-item i.fa-map-marker-alt');
        if (locationEl && locationEl.parentNode) locationEl.parentNode.parentNode.innerHTML = `<i class="fas fa-map-marker-alt me-2"></i><span>${json.location || ''}</span>`;

        Swal.fire({
          title: 'Paramètres enregistrés',
          text:  'Voulez-vous recharger pour appliquer les changements ?',
          icon:  'success',
          showCancelButton: true,
          confirmButtonText: 'Recharger',
          cancelButtonText:  'Plus tard'
        }).then(result => {
          if (result.isConfirmed) {
            window.location.reload();
          } else {
            const offcanvasEl = document.getElementById('settingsOffcanvas');
            if (offcanvasEl) bootstrap.Offcanvas.getInstance(offcanvas).hide();
          }
        });
      })
      .catch(err => {
        console.error(err);
        Swal.fire('Erreur', 'Impossible de sauvegarder vos paramètres', 'error');
      });
    });

    const form = document.getElementById('mainForm');
    const keep = ['doctor_name', 'location'];
    const listboxes = ['medications_listbox','analyses_listbox','radiologies_listbox'];

    document.querySelectorAll('button[type="reset"]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.preventDefault();
        customReset();
      });
    });

    function customReset() {
      const saved = {};
      keep.forEach(id => { const el=document.getElementById(id); if (el) saved[id]=el.value; });

      form.querySelectorAll('input, select, textarea').forEach(el => {
        if (keep.includes(el.id)) return;

        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
          if (['checkbox','radio'].includes(el.type)) el.checked = false;
          else el.value = '';
        } else if (el.tagName === 'SELECT') {
          el.selectedIndex = -1;
          if (el.multiple) el.innerHTML = '';
        }
      });

      listboxes.forEach(id => { const lb=document.getElementById(id); if (lb) lb.innerHTML=''; });

      window.medicationCount = 1;
      window.analysisCount   = 1;
      window.radiologyCount  = 1;

      Object.entries(saved).forEach(([id,val]) => { document.getElementById(id).value = val; });
    }

    const prefillSuiviPatientId = "{{ prefill_suivi_patient_id }}";
    const prefillSuiviPatientName = "{{ prefill_suivi_patient_name }}";

    // MODIFICATION ICI: Initialisation des champs de suivi et rechargement de la DataTable au chargement de la page
    // si des valeurs de préremplissage sont présentes (après soumission de formulaire par exemple).
    // Cette logique s'exécute une seule fois au chargement du DOM.
    const suiviPatientIdInput = document.getElementById("suivi_patient_id");
    const suiviPatientNameInput = document.getElementById("suivi_patient_name");
    const patientIdInput = document.getElementById("patient_id"); // Récupérer l'input patient_id de l'onglet principal

    if (prefillSuiviPatientId && prefillSuiviPatientId !== "None") {
        suiviPatientIdInput.value = prefillSuiviPatientId;
        suiviPatientNameInput.value = prefillSuiviPatientName;
        // Déclenche le rechargement du tableau après avoir défini les valeurs
        $('#consultationsTable').DataTable().ajax.reload();
        // Active l'onglet "Suivi" si des données préremplies sont présentes
        const suiviTabTrigger = document.querySelector('[data-bs-target="#suivi"]');
        if (suiviTabTrigger) {
            bootstrap.Tab.getOrCreateInstance(suiviTabTrigger).show();
        }
    } else {
        // NEW ADDITION: Trigger patient ID change event on page load if an ID is pre-filled in the main tab
        // Ceci gère le cas où l'utilisateur arrive sur la page et qu'un patient_id initial est déjà là (par ex. depuis last_consult)
        const initialPatientId = patientIdInput.value.trim();
        if (initialPatientId) {
            // Déclenche l'événement 'change' pour que la logique de remplissage s'exécute
            // et remplisse les champs de l'onglet "Suivi" et charge la dernière consultation.
            
            // patientIdInput.dispatchEvent(new Event('change')); // <-- LIGNE MISE EN COMMENTAIRE
        }
        }


  }); // Fin de DOMContentLoaded
// NEW ADDITION: Handle doctor_name combobox pre-selection or clear for custom input
const doctorNameInput = document.getElementById('doctor_name');
// Valeur du nom complet de l'utilisateur connecté (médecin, assistante, etc.)
const loggedInFullName = "{{ logged_in_doctor_name }}"; // Variable maintenant générique
// Valeur du nom du médecin définie par l'administrateur dans la configuration
const configDoctorName = "{{ config.doctor_name | default('') }}";
// Rôle de l'utilisateur connecté (doit être passé depuis Flask, e.g., session.get('role'))
const userRole = "{{ session.get('role') }}"; 

if (doctorNameInput) {
    let initialValue = "";

    // Si l'utilisateur est un médecin, pré-remplir avec son nom complet
    if (userRole === 'medecin' && loggedInFullName && loggedInFullName !== "None") {
        initialValue = loggedInFullName;
    }
    // Si l'utilisateur est une assistante ou un admin, pré-remplir avec le nom du médecin configuré
    // Cela permet à l'assistante de choisir le médecin pour lequel elle enregistre la consultation.
    else if ((userRole === 'assistante' || userRole === 'admin') && configDoctorName) {
        initialValue = configDoctorName;
    }
    // Sinon, initialValue reste vide, ou peut être basé sur la dernière consultation si c'est pertinent.
    // La logique de la dernière consultation sera gérée par l'événement 'change' sur patient_id.

    // AJOUTER "Dr. " ICI
    if (initialValue) { // N'ajoutez "Dr. " que si une valeur existe
        doctorNameInput.value = "Dr. " + initialValue;
    } else {
        doctorNameInput.value = initialValue; // Laisser vide si initialValue est vide
    }

    // Assurez-vous que l'étiquette flottante est active pour la valeur pré-remplie
    if (doctorNameInput.value) { // Vérifier la valeur APRÈS l'ajout de "Dr. "
        doctorNameInput.classList.add('not(:placeholder-shown)');
    } else {
        doctorNameInput.classList.remove('not(:placeholder-shown)');
    }

    // Déclenchez la mise à jour de l'étiquette flottante lors de la saisie/modification manuelle
    doctorNameInput.addEventListener('input', () => {
        if (doctorNameInput.value) {
            doctorNameInput.classList.add('not(:placeholder-shown)');
        } else {
            doctorNameInput.classList.remove('not(:placeholder-shown)');
        }        
    });
    
             // AJOUTEZ CETTE NOUVELLE FONCTION
    function refreshSuiviTab() {
      // 1. Récupère l'ID du patient depuis le premier onglet ("Infos Base")
      const patientIdFromTab1 = document.getElementById('patient_id').value.trim();

      if (!patientIdFromTab1) {
          Swal.fire({
              icon: 'info',
              title: 'Aucun patient sélectionné',
              text: "Veuillez d'abord saisir un ID Patient dans l'onglet 'Infos Base'."
          });
          return;
      }

      // 2. Met à jour les champs ID et Nom dans l'onglet "Suivi"
      document.getElementById('suivi_patient_id').value = patientIdFromTab1;

      // Met aussi à jour le nom pour la cohérence, en utilisant les données déjà chargées
      if (patientData && patientIdFromTab1 in patientData) {
          document.getElementById('suivi_patient_name').value = patientData[patientIdFromTab1].name || '';
      } else {
          document.getElementById('suivi_patient_name').value = '';
      }

      // 3. Recharge la table, qui utilisera maintenant le bon ID
      $('#consultationsTable').DataTable().ajax.reload();

      console.log(`Onglet Suivi rafraîchi avec l'ID du premier onglet : ${patientIdFromTab1}`);
    }
}
</script>
{% include '_floating_assistant.html' %} 
</body>
</html>
"""

alert_template = """
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
  <meta charset="UTF-8">
  <title>Alerte</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&family=Great+Vibes&display=swap" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
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
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  margin: 0;
  transition: background 0.3s ease, color 0.3s ease;
}
</style>

</head>
<body>
<script>
  Swal.fire({
    icon: '{{ alert_type }}',
    title: '{{ alert_title }}',
    html: '{{ alert_text }} {% if extra_info %} <br><br> {{ extra_info }} {% endif %}',
    timer: 3000,
    timerProgressBar: true,
    didClose: () => { window.location.href = "{{ redirect_url }}"; }
  });
</script>
</body>
</html>
"""

settings_template = """
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
  <title>Paramètres de l'application</title>
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
      padding-top: 20px; /* Adjusted for this simple page */
      transition: background 0.3s ease, color 0.3s ease;
    }

    .container {
      max-width: 700px; /* Slightly wider for settings */
      background: var(--card-bg);
      border-radius: var(--border-radius-lg);
      box-shadow: var(--shadow-medium);
      padding: 2rem;
    }

    h2 {
      color: var(--primary-color);
      font-weight: 700;
      margin-bottom: 1.5rem;
    }

    /* Floating Labels */
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

    /* Buttons */
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
    .btn-secondary {
      background-color: var(--secondary-color);
      border-color: var(--secondary-color);
      color: var(--button-text);
    }
    .btn-secondary:hover {
      background-color: var(--secondary-color-dark);
      border-color: var(--secondary-color-dark);
      box-shadow: var(--shadow-medium);
    }

    .alert {
      border-radius: var(--border-radius-md);
      font-weight: 600;
      position: relative;
      margin-bottom: 1rem;
      box-shadow: var(--shadow-light);
    }
  </style>
</head>
<body>
  <div class="container my-5">
    <h2 class="text-center mb-4">Paramètres de l'application</h2>
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat,msg in msgs %}
        <div class="alert alert-{{ cat }}">{{ msg }}</div>
      {% endfor %}
    {% endwith %}
    <form id="settingsForm" action="{{ url_for('settings') }}" method="POST">
      <div class="mb-3 floating-label">
        <input type="text" class="form-control" name="nom_clinique" id="nom_clinique"
               value="{{ config.nom_clinique or '' }}" placeholder=" ">
        <label for="nom_clinique">Nom Clinique / Cabinet</label>
      </div>
      <div class="mb-3 floating-label">
        <input type="text" class="form-control" name="centre_medecin" id="centre_medecin"
               value="{{ config.centre_medical or '' }}" placeholder=" ">
        <label for="centre_medecin">Centre Médical</label>
      </div>
      <div class="mb-3 floating-label">
        <input type="text" class="form-control" name="nom_medecin" id="nom_medecin"
               value="{{ config.doctor_name or '' }}" placeholder=" ">
        <label for="nom_medecin">Nom du Médecin</label>
      </div>
      <div class="mb-3 floating-label">
        <input type="text" class="form-control" name="lieu" id="lieu"
               value="{{ config.location or '' }}" placeholder=" ">
        <label for="lieu">Lieu</label>
      </div>
      <div class="mb-3 floating-label">
        <select class="form-select" name="theme" id="theme" placeholder=" ">
          {% for t in theme_names %}
            <option value="{{ t }}" {% if config.theme == t %}selected{% endif %}>{{ t.capitalize() }}</option>
          {% endfor %}
        </select>
        <label for="theme">Thème</label>
      </div>
      <div class="mb-3 floating-label">
        <input type="text" class="form-control" name="arriere_plan" id="arriere_plan"
               value="{{ config.background_file_path or '' }}" placeholder=" ">
        <label for="arriere_plan">Logo/Arrière-plan</label>
      </div>
      <div class="mb-3 floating-label">
        <textarea class="form-control" name="liste_medicaments" id="liste_medicaments" rows="4" placeholder=" ">{% if config.medications_options %}{{ config.medications_options|join('\\n') }}{% endif %}</textarea>
        <label for="liste_medicaments">Liste des Médicaments</label>
      </div>
      <div class="mb-3 floating-label">
        <textarea class="form-control" name="liste_analyses" id="liste_analyses" rows="4" placeholder=" ">{% if config.analyses_options %}{{ config.analyses_options|join('\\n') }}{% endif %}</textarea>
        <label for="liste_analyses">Liste des Analyses</label>
      </div>
      <div class="mb-3 floating-label">
        <textarea class="form-control" name="liste_radiologies" id="liste_radiologies" rows="4" placeholder=" ">{% if config.radiologies_options %}{{ config.radiologies_options|join('\\n') }}{% endif %}</textarea>
        <label for="liste_radiologies">Liste des Radiologies</label>
      </div>
      <button type="submit" class="btn btn-success w-100">Enregistrer Paramètres</button>
    </form>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
  <script>
    document.addEventListener('DOMContentLoaded', () => {
      const form = document.getElementById('settingsForm');
      form.addEventListener('submit', e => {
        e.preventDefault();
        fetch(form.action, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json'
          },
          body: new FormData(form)
        })
        .then(res => res.json())
        .then(data => {
          Swal.fire({ icon:'success', title:'Paramètres enregistrés', timer:800, showConfirmButton:false });
          const offcanvas = document.getElementById('settingsOffcanvas');
          if (offcanvas) bootstrap.Offcanvas.getInstance(offcanvas).hide();
          setTimeout(() => window.location.reload(), 3000);
        })
        .catch(() => {
          Swal.fire({ icon:'error', title:'Erreur', text:'Échec de la sauvegarde.' });
        });
      });
    });
  </script>
</body>
</html>
"""