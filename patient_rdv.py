# patient_rdv.py

from flask import Blueprint, request, render_template_string, jsonify, session, redirect, url_for, flash
from datetime import datetime, date, timedelta
import pandas as pd
import utils
import theme
import os
import re
import json
from openpyxl import Workbook
from typing import Optional
from pathlib import Path
import login # NOUVEAU: Import login module to get doctors list

# Ces variables seront définies dynamiquement une fois set_patient_rdv_dirs est appelée
EXCEL_DIR: Optional[Path] = None
EXCEL_FILE: Optional[Path] = None
BASE_PATIENT_FILE: Optional[Path] = None
DISABLED_PERIODS_FILE: Optional[Path] = None # Nouveau chemin pour le fichier de périodes désactivées


# ------------------------------------------------------------------
# CONFIGURATION DES RÉPERTOIRES pour patient_rdv
# ------------------------------------------------------------------
def set_patient_rdv_dirs():
    """
    Définit les chemins de répertoires dynamiques.
    Cette fonction se base sur utils.DYNAMIC_BASE_DIR qui doit être défini au préalable par la route.
    """
    global EXCEL_DIR, EXCEL_FILE, BASE_PATIENT_FILE, DISABLED_PERIODS_FILE

    if utils.DYNAMIC_BASE_DIR is None:
        raise ValueError("utils.DYNAMIC_BASE_DIR n'est pas défini. Impossible d'initialiser les chemins.")

    base_dir = Path(utils.DYNAMIC_BASE_DIR)
    excel_folder = base_dir / "Excel"
    config_folder = base_dir / "Config"

    os.makedirs(excel_folder, exist_ok=True)
    os.makedirs(config_folder, exist_ok=True)

    EXCEL_DIR = excel_folder
    EXCEL_FILE = EXCEL_DIR / "DonneesRDV.xlsx"
    BASE_PATIENT_FILE = EXCEL_DIR / "info_Base_patient.xlsx"
    DISABLED_PERIODS_FILE = config_folder / "disabled_periods.json"
    print(f"DEBUG: Chemins RDV patient définis. EXCEL_DIR: {EXCEL_DIR}")


# Fonctions d'aide pour la gestion des fichiers Excel (adaptées de rdv.py)
def initialize_excel_file():
    """Initialise le fichier DonneesRDV.xlsx avec les colonnes unifiées."""
    if EXCEL_FILE is None:
        print("ERREUR : EXCEL_FILE non défini. Impossible d'initialiser le fichier Excel.")
        return
    wb = Workbook()
    sheet = wb.active
    sheet.title = "RDV"
    # Colonnes unifiées pour les rendez-vous
    sheet.append([
        "Num Ordre", "ID", "Nom", "Prenom", "DateNaissance", "Sexe", "Âge",
        "Antécédents", "Téléphone", "Date", "Heure", "Statut", "Medecin_Email" # NOUVEAU: Ajout de Medecin_Email
    ])
    wb.save(EXCEL_FILE)
    print(f"DEBUG : Fichier DonneesRDV.xlsx initialisé avec les colonnes unifiées.")

def load_df() -> pd.DataFrame:
    """Charge le DataFrame depuis DonneesRDV.xlsx, ajoutant les colonnes manquantes si nécessaire."""
    if EXCEL_FILE is None:
        print("ERREUR : EXCEL_FILE non défini. Impossible de charger le dataframe.")
        return pd.DataFrame() # Retourne un DataFrame vide pour éviter d'autres erreurs

    if not EXCEL_FILE.exists():
        initialize_excel_file()
    df = pd.read_excel(EXCEL_FILE, dtype=str).fillna('')
    # Assurez-vous que toutes les colonnes attendues sont présentes
    expected_cols = [
        "Num Ordre", "ID", "Nom", "Prenom", "DateNaissance", "Sexe", "Âge",
        "Antécédents", "Téléphone", "Date", "Heure", "Statut", "Medecin_Email" # NOUVEAU: Medecin_Email
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = '' # Ajoute les colonnes manquantes avec des valeurs vides
    return df

def save_df(df: pd.DataFrame):
    """Sauvegarde le DataFrame dans DonneesRDV.xlsx."""
    if EXCEL_FILE is None:
        print("ERREUR : EXCEL_FILE non défini. Impossible de sauvegarder le dataframe.")
        return
    df.to_excel(EXCEL_FILE, index=False)

def initialize_base_patient_file():
    """Initialise le fichier info_Base_patient.xlsx avec les colonnes unifiées."""
    if BASE_PATIENT_FILE is None:
        print("ERREUR : BASE_PATIENT_FILE non défini. Impossible d'initialiser le fichier patient de base.")
        return
    wb = Workbook()
    sheet = wb.active
    sheet.title = "BasePatients"
    # Colonnes unifiées pour la base de données des patients
    sheet.append([
        "ID", "Nom", "Prenom", "DateNaissance", "Sexe", "Âge",
        "Antécédents", "Téléphone"
    ])
    wb.save(BASE_PATIENT_FILE)
    print(f"DEBUG : Fichier info_Base_patient.xlsx initialisé avec les colonnes unifiées.")

def save_base_patient_df(df_new: pd.DataFrame):
    """Sauvegarde ou met à jour les données dans info_Base_patient.xlsx."""
    if BASE_PATIENT_FILE is None:
        print("ERREUR : BASE_PATIENT_FILE non défini. Impossible de sauvegarder le dataframe patient de base.")
        return

    if not BASE_PATIENT_FILE.exists():
        initialize_base_patient_file()
        df_existing = pd.DataFrame(columns=[
            "ID", "Nom", "Prenom", "DateNaissance", "Sexe", "Âge",
            "Antécédents", "Téléphone"
        ])
    else:
        df_existing = pd.read_excel(BASE_PATIENT_FILE, dtype=str).fillna('')

    # Assurez-vous que df_new a les colonnes attendues pour info_Base_patient
    expected_cols = ["ID", "Nom", "Prenom", "DateNaissance", "Sexe", "Âge", "Antécédents", "Téléphone"]
    for col in expected_cols:
        if col not in df_new.columns:
            df_new[col] = '' # Ajoute la colonne si manquante

    df_new_filtered = df_new[expected_cols]

    # Concaténer et supprimer les doublons basés sur l'ID (conserve la dernière entrée pour un ID donné)
    df_combined = pd.concat([df_existing, df_new_filtered], ignore_index=True)
    if "ID" in df_combined.columns:
        df_combined.drop_duplicates(subset=["ID"], keep="last", inplace=True)

    df_combined.to_excel(BASE_PATIENT_FILE, index=False)
    print(f"DEBUG : Données sauvegardées dans info_Base_patient.xlsx. Total d'entrées : {len(df_combined)}")


def load_base_patients() -> dict:
    """Charge les patients depuis info_Base_patient.xlsx."""
    if BASE_PATIENT_FILE is None:
        print("ERREUR : BASE_PATIENT_FILE non défini. Impossible de charger les patients de base.")
        return {}
    if not BASE_PATIENT_FILE.exists():
        initialize_base_patient_file()

    patients = {}
    df = pd.read_excel(BASE_PATIENT_FILE, dtype=str).fillna('')
    for _, row in df.iterrows():
        pid = str(row["ID"]).strip()
        if not pid:
            continue
        patients[pid] = {
            "name":          f"{row['Nom']} {row['Prenom']}".strip(),
            "nom":           str(row["Nom"]).strip(), # Explicitly add 'nom'
            "prenom":        str(row["Prenom"]).strip(), # Explicitly add 'prenom'
            "date_of_birth": str(row["DateNaissance"]),
            "gender":        str(row["Sexe"]),
            "age":           str(row["Âge"]),
            "antecedents":   str(row["Antécédents"]),
            "phone":         str(row["Téléphone"]),
        }
    return patients


# Fonctions de calcul et de validation
# generate_time_slots et calculate_order_number sont maintenant importées de utils
# def generate_time_slots():
#     """Génère une liste de créneaux horaires par intervalles de 15 minutes de 8h00 à 17h45."""
#     start = datetime.strptime("08:00", "%H:%M")
#     return [
#         (start + timedelta(minutes=i*15)).strftime("%H:%M")
#         for i in range(44) # 44 * 15 minutes = 11 heures (de 8h00 à 18h00)
#     ]

# def calculate_order_number(time_str: str):
#     """Calcule un numéro d'ordre pour un créneau horaire donné."""
#     rdv_time = datetime.strptime(time_str, "%H:%M").time()
#     delta = (rdv_time.hour - 8) * 60 + rdv_time.minute
#     return (delta // 15) + 1 if 8 <= rdv_time.hour <= 17 else "N/A"

def compute_age_str(dob: date) -> str:
    """Calcule l'âge en années et mois à partir d'une date de naissance."""
    today_date = date.today()
    years = today_date.year - dob.year - (
        (today_date.month, today_date.day) < (dob.month, dob.day)
    )
    months = today_date.month - dob.month - (today_date.day < dob.day)
    if months < 0:
        months += 12
    return f"{years} ans {months} mois"

# Expression régulière pour la validation du numéro de téléphone
PHONE_RE = re.compile(r"^[+0]\d{6,14}$")

# Fonctions pour gérer les périodes désactivées
def load_disabled_periods() -> list:
    """Charge les périodes désactivées depuis disabled_periods.json."""
    if DISABLED_PERIODS_FILE is None:
        print("ERREUR : DISABLED_PERIODS_FILE non défini. Impossible de charger les périodes désactivées.")
        return []
    if DISABLED_PERIODS_FILE.exists():
        try:
            with open(DISABLED_PERIODS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERREUR : Erreur de décodage JSON pour {DISABLED_PERIODS_FILE}: {e}")
            return []
    return []

def save_disabled_periods(periods: list):
    """Sauvegarde les périodes désactivées dans disabled_periods.json."""
    if DISABLED_PERIODS_FILE is None:
        print("ERREUR : DISABLED_PERIODS_FILE non défini. Impossible de sauvegarder les périodes désactivées.")
        return
    with open(DISABLED_PERIODS_FILE, 'w', encoding='utf-8') as f:
        json.dump(periods, f, ensure_ascii=False, indent=2)

def get_disabled_period_reason(check_date: str, disabled_periods: list) -> Optional[str]:
    """Vérifie si une date est dans une période désactivée et retourne le motif."""
    check_dt = datetime.strptime(check_date, "%Y-%m-%d").date()
    for period in disabled_periods:
        start_dt = datetime.strptime(period['start_date'], "%Y-%m-%d").date()
        end_dt = datetime.strptime(period['end_date'], "%Y-%m-%d").date()
        if start_dt <= check_dt <= end_dt:
            return period.get('reason', 'Raison non spécifiée')
    return None

# ------------------------------------------------------------------
# DÉCLARATION DU BLUEPRINT
# Le préfixe d'URL pour ce blueprint inclus directement le paramètre dynamique 'admin_prefix'.
# Cela signifie que toutes les routes définies ci-dessous hériteront de ce préfixe.
# Exemple: /patient_rdv/monadmin/
# ------------------------------------------------------------------
patient_rdv_bp = Blueprint('patient_rdv', __name__, url_prefix='/patient_rdv/<string:admin_prefix>')

# ------------------------------------------------------------------
# ROUTES DU BLUEPRINT
# ------------------------------------------------------------------
@patient_rdv_bp.route("/", methods=["GET", "POST"])
def patient_rdv_home(admin_prefix):
    # ----- LOGIQUE CORRIGÉE -----
    # 1. Définir le contexte de l'administrateur à partir de l'URL.
    full_email_for_utils = f"{admin_prefix}@gmail.com"
    utils.set_dynamic_base_dir(full_email_for_utils)
    
    # 2. Initialiser les chemins de fichiers qui dépendent de ce contexte.
    set_patient_rdv_dirs()
    
    # 3. Charger les configurations et données.
    config = utils.load_config()
    theme_vars = theme.THEMES.get(config.get('theme', theme.DEFAULT_THEME), theme.THEMES[theme.DEFAULT_THEME])
    df = load_df()
    patients = load_base_patients()
    disabled_periods = load_disabled_periods()
    # ----- FIN DE LA CORRECTION -----
    # Définir les variables de thème en fonction de la configuration de l'admin
    theme_vars = theme.THEMES.get(config.get('theme', theme.DEFAULT_THEME), theme.THEMES[theme.DEFAULT_THEME])

    # Charger les données de rendez-vous et de patients pour cet administrateur
    df = load_df() # Charge DonneesRDV.xlsx
    patients = load_base_patients() # Charge info_Base_patient.xlsx
    disabled_periods = load_disabled_periods() # Charger les périodes désactivées

    # NOUVEAU : Récupérer les paramètres de temps de la configuration
    rdv_start_time = config.get('rdv_start_time', '08:00')
    rdv_end_time = config.get('rdv_end_time', '17:45')
    rdv_interval_minutes = config.get('rdv_interval_minutes', 15)

    # NOUVEAU : Générer les créneaux horaires en utilisant les paramètres de la configuration
    all_available_timeslots = utils.generate_time_slots(
        rdv_start_time, rdv_end_time, rdv_interval_minutes
    )

    # NOUVEAU : Charger la liste des médecins pour cet administrateur
    doctors = []
    # Reconstruire l'e-mail complet de l'admin à partir du préfixe URL
    full_email_for_admin = f"{admin_prefix}@gmail.com" # Assurez-vous que le domaine est correct (.com, .eml.com, etc.)

    # 1. Obtenir le nom du médecin depuis la configuration générale de l'administrateur
    config_doctor_name = config.get('doctor_name', '').strip()
    if config_doctor_name:
        # AJOUT / MODIFICATION ICI : Utiliser l'email réel de l'admin pour le médecin configuré
        name_parts = config_doctor_name.split(' ')
        prenom_config = ' '.join(name_parts[:-1]) if len(name_parts) > 1 else ''
        nom_config = name_parts[-1] if name_parts else ''
        doctors.append({'email': full_email_for_admin, 'nom': nom_config, 'prenom': prenom_config})

    # 2. Ajouter les médecins ayant des comptes
    all_users = login.load_users()
    for email, user_data in all_users.items():
        # Filtrer les utilisateurs qui appartiennent à cet administrateur
        if user_data.get('role') == 'medecin' and user_data.get('owner') == full_email_for_admin:
            full_name = f"{user_data.get('prenom', '')} {user_data.get('nom', '')}".strip()
            # N'ajoutez que si ce n'est pas déjà le nom du médecin de la config
            if full_name and full_name != config_doctor_name:
                doctors.append({'email': email, 'nom': user_data.get('nom'), 'prenom': user_data.get('prenom')})

    # Trier la liste des médecins par prénom puis nom pour un affichage cohérent
    doctors = sorted(doctors, key=lambda x: (x.get('prenom', ''), x.get('nom', '')))

    iso_today = datetime.now().strftime("%Y-%m-%d")
    # Récupérer les créneaux déjà réservés pour la date d'aujourd'hui (initialement pour aucun médecin)
    # Les créneaux réservés seront filtrés par médecin via JS
    reserved_slots = df[df["Date"] == iso_today]["Heure"].tolist() # This is a placeholder, JS will re-filter

    # Vérifier si la date d'aujourd'hui est désactivée
    today_disabled_reason = get_disabled_period_reason(iso_today, disabled_periods)


    # Gestion des soumissions de formulaire (méthode POST)
    if request.method == "POST":
        f         = request.form
        pid       = f.get("patient_id", "").strip()
        nom       = f.get("patient_nom", "").strip()
        prenom    = f.get("patient_prenom", "").strip()
        gender    = f.get("patient_gender", "").strip()
        dob_str   = f.get("patient_dob", "").strip()
        ant       = f.get("patient_ant", "").strip()
        phone     = f.get("patient_phone", "").strip()
        date_rdv  = f.get("rdv_date", "").strip()
        time_rdv  = f.get("rdv_time", "").strip()
        medecin_email = f.get("medecin_select", "").strip() # NOUVEAU: Récupérer l'email du médecin

        # Validation des champs obligatoires
        if not all([pid, nom, prenom, gender, dob_str, ant, phone, date_rdv, time_rdv, medecin_email]):
            return render_template_string(patient_rdv_template,
                config=config, theme_vars=theme_vars, timeslots=all_available_timeslots,
                iso_today=iso_today, reserved_slots=reserved_slots,
                message="Veuillez remplir tous les champs, y compris le médecin.", message_type="warning",
                role=session.get('role'), disabled_periods=disabled_periods,
                today_disabled_reason=today_disabled_reason, doctors=doctors
            )

        # Validation du format du numéro de téléphone
        if not PHONE_RE.fullmatch(phone):
            return render_template_string(patient_rdv_template,
                config=config, theme_vars=theme_vars, timeslots=all_available_timeslots,
                iso_today=iso_today, reserved_slots=reserved_slots,
                message="Le format du numéro de téléphone est invalide. Utilisez un format comme +212XXXXXXXXX ou 0XXXXXXXXX.", message_type="warning",
                role=session.get('role'), disabled_periods=disabled_periods,
                today_disabled_reason=today_disabled_reason, doctors=doctors
            )

        # Validation de la date de naissance
        try:
            dob_date = datetime.strptime(dob_str, "%Y-%m-%d").date()
            if dob_date > date.today():
                raise ValueError
        except ValueError:
            return render_template_string(patient_rdv_template,
                config=config, theme_vars=theme_vars, timeslots=all_available_timeslots,
                iso_today=iso_today, reserved_slots=reserved_slots,
                message="La date de naissance est invalide ou se situe dans le futur.", message_type="warning",
                role=session.get('role'), disabled_periods=disabled_periods,
                today_disabled_reason=today_disabled_reason, doctors=doctors
            )

        age_text = compute_age_str(dob_date)
        full_name = f"{nom} {prenom}".strip()

        # Validation de la date désactivée
        disabled_reason = get_disabled_period_reason(date_rdv, disabled_periods)
        if disabled_reason:
             return render_template_string(patient_rdv_template,
                config=config, theme_vars=theme_vars, timeslots=all_available_timeslots,
                iso_today=iso_today, reserved_slots=reserved_slots,
                message=f"La date du {date_rdv} est désactivée ({disabled_reason}). Veuillez choisir une autre date.", message_type="warning",
                role=session.get('role'), disabled_periods=disabled_periods,
                today_disabled_reason=today_disabled_reason, doctors=doctors
            )

        # --- DÉBUT DE LA CORRECTION D'ORDRE ---

        # 1. VÉRIFICATION DU CRÉNEAU HORAIRE (MAINTENANT EN PREMIER)
        if ((df["Date"] == date_rdv) & (df["Heure"] == time_rdv) & (df["Medecin_Email"] == medecin_email)).any():
            return render_template_string(patient_rdv_template,
                config=config, theme_vars=theme_vars, timeslots=all_available_timeslots,
                iso_today=iso_today, reserved_slots=reserved_slots,
                message=f"Le créneau du {date_rdv} à {time_rdv} est déjà réservé pour le médecin sélectionné. Veuillez choisir une autre heure ou date.", message_type="warning",
                role=session.get('role'), disabled_periods=disabled_periods,
                today_disabled_reason=today_disabled_reason, doctors=doctors
            )

        # 2. VÉRIFICATION DU RDV DUPLIQUÉ POUR LE PATIENT (MAINTENANT EN SECOND)
        if ((df["ID"] == pid) & (df["Date"] == date_rdv) & (df["Medecin_Email"] == medecin_email)).any():
            return render_template_string(patient_rdv_template,
                config=config, theme_vars=theme_vars, timeslots=all_available_timeslots,
                iso_today=iso_today, reserved_slots=reserved_slots,
                message=f"Vous avez déjà un rendez-vous planifié pour le {date_rdv} avec ce médecin. Un seul rendez-vous par jour est autorisé.", message_type="warning",
                role=session.get('role'), disabled_periods=disabled_periods,
                today_disabled_reason=today_disabled_reason, doctors=doctors
            )
            
        # --- FIN DE LA CORRECTION D'ORDRE ---

        # Validation du format du numéro de téléphone
        if not PHONE_RE.fullmatch(phone):
            return render_template_string(patient_rdv_template,
                config=config, theme_vars=theme_vars, timeslots=all_available_timeslots, # Utiliser all_available_timeslots
                iso_today=iso_today, reserved_slots=reserved_slots,
                message="Le format du numéro de téléphone est invalide. Utilisez un format comme +212XXXXXXXXX ou 0XXXXXXXXX.", message_type="warning",
                role=session.get('role'), disabled_periods=disabled_periods,
                today_disabled_reason=today_disabled_reason, doctors=doctors
            )

        # Validation de la date de naissance (doit être une date valide et non dans le futur)
        try:
            dob_date = datetime.strptime(dob_str, "%Y-%m-%d").date()
            if dob_date > date.today():
                raise ValueError
        except ValueError:
            return render_template_string(patient_rdv_template,
                config=config, theme_vars=theme_vars, timeslots=all_available_timeslots, # Utiliser all_available_timeslots
                iso_today=iso_today, reserved_slots=reserved_slots,
                message="La date de naissance est invalide ou se situe dans le futur.", message_type="warning",
                role=session.get('role'), disabled_periods=disabled_periods,
                today_disabled_reason=today_disabled_reason, doctors=doctors
            )

        age_text = compute_age_str(dob_date)
        full_name = f"{nom} {prenom}".strip()

        # NOUVELLE VALIDATION : Vérifier si la date est désactivée par l'admin
        disabled_reason = get_disabled_period_reason(date_rdv, disabled_periods)
        if disabled_reason:
             return render_template_string(patient_rdv_template,
                config=config, theme_vars=theme_vars, timeslots=all_available_timeslots, # Utiliser all_available_timeslots
                iso_today=iso_today, reserved_slots=reserved_slots,
                message=f"La date du {date_rdv} est désactivée ({disabled_reason}). Veuillez choisir une autre date.", message_type="warning",
                role=session.get('role'), disabled_periods=disabled_periods,
                today_disabled_reason=today_disabled_reason, doctors=doctors
            )

        # NOUVELLE VALIDATION : un seul rendez-vous par patient par jour (pour ce médecin)
        if ((df["ID"] == pid) & (df["Date"] == date_rdv) & (df["Medecin_Email"] == medecin_email)).any():
            return render_template_string(patient_rdv_template,
                config=config, theme_vars=theme_vars, timeslots=all_available_timeslots, # Utiliser all_available_timeslots
                iso_today=iso_today, reserved_slots=reserved_slots,
                message=f"Vous avez déjà un rendez-vous planifié pour le {date_rdv} avec ce médecin. Un seul rendez-vous par jour est autorisé.", message_type="warning",
                role=session.get('role'), disabled_periods=disabled_periods,
                today_disabled_reason=today_disabled_reason, doctors=doctors
            )

        # Vérifier si un créneau horaire est déjà réservé (pour ce médecin)
        if ((df["Date"] == date_rdv) & (df["Heure"] == time_rdv) & (df["Medecin_Email"] == medecin_email)).any():
            return render_template_string(patient_rdv_template,
                config=config, theme_vars=theme_vars, timeslots=all_available_timeslots, # Utiliser all_available_timeslots
                iso_today=iso_today, reserved_slots=reserved_slots,
                message=f"Le créneau du {date_rdv} à {time_rdv} est déjà réservé pour le médecin sélectionné. Veuillez choisir une autre heure ou date.", message_type="warning",
                role=session.get('role'), disabled_periods=disabled_periods,
                today_disabled_reason=today_disabled_reason, doctors=doctors
            )

        # Vérifier si l'ID patient existe déjà avec des informations différentes dans le fichier patient de base
        if pid in patients and (
            patients[pid]["name"].lower() != full_name.lower() or
            patients[pid]["date_of_birth"] != dob_str or
            patients[pid]["gender"] != gender
        ):
             return render_template_string(patient_rdv_template,
                config=config, theme_vars=theme_vars, timeslots=all_available_timeslots, # Utiliser all_available_timeslots
                iso_today=iso_today, reserved_slots=reserved_slots,
                message=f"L'ID patient '{pid}' existe déjà mais les informations de nom, date de naissance ou sexe ne correspondent pas. Veuillez vérifier vos données.", message_type="error",
                role=session.get('role'), disabled_periods=disabled_periods,
                today_disabled_reason=today_disabled_reason, doctors=doctors
            )


        # Ajouter le nouveau rendez-vous à DonneesRDV.xlsx
        # NOUVEAU : Utiliser la fonction calculate_order_number avec les paramètres de la configuration
        num_ord = utils.calculate_order_number(
            time_rdv, rdv_start_time, rdv_interval_minutes
        )
        new_rdv_row_data = {
            "Num Ordre": num_ord,
            "ID": pid,
            "Nom": nom,
            "Prenom": prenom,
            "DateNaissance": dob_str,
            "Sexe": gender,
            "Âge": age_text,
            "Antécédents": ant,
            "Téléphone": phone,
            "Date": date_rdv,
            "Heure": time_rdv,
            "Statut": "En attente d'approbation", # Marquer comme en attente d'approbation par l'admin
            "Medecin_Email": medecin_email # NOUVEAU: Ajout de l'email du médecin
        }
        # Créer un DataFrame à partir de la nouvelle ligne pour concaténation
        # S'assurer que les colonnes du nouveau DataFrame correspondent à celles de df
        new_rdv_row_df = pd.DataFrame([new_rdv_row_data], columns=df.columns)
        df = pd.concat([df, new_rdv_row_df], ignore_index=True)
        save_df(df) # Sauvegarde le fichier DonneesRDV.xlsx

        # Supprimer la ligne suivante pour ne plus mettre à jour info_Base_patient.xlsx
        # patient_base_data = pd.DataFrame([{
        #     "ID": pid, "Nom": nom, "Prenom": prenom, "DateNaissance": dob_str,
        #     "Sexe": gender, "Âge": age_text, "Antécédents": ant, "Téléphone": phone
        # }])
        # save_base_patient_df(patient_base_data) # Sauvegarde le fichier info_Base_patient.xlsx

        return render_template_string(patient_rdv_template,
            config=config, theme_vars=theme_vars, timeslots=all_available_timeslots, # Utiliser all_available_timeslots
            iso_today=iso_today, reserved_slots=reserved_slots,
            message="Votre rendez-vous a été soumis avec succès. Une confirmation vous sera envoyée après approbation par le cabinet.", message_type="success",
            role=session.get('role'), disabled_periods=disabled_periods,
            today_disabled_reason=today_disabled_reason, doctors=doctors
        )

    # Pour la requête GET (affichage initial du formulaire)
    return render_template_string(
        patient_rdv_template,
        config=config,
        theme_vars=theme_vars,
        timeslots=all_available_timeslots, # Always pass timeslots
        iso_today=iso_today,
        reserved_slots=reserved_slots, # This will be re-filtered by JS for selected doctor
        message=None, # Pas de message au chargement initial
        role=session.get('role'), # Passer le rôle de l'utilisateur
        disabled_periods=disabled_periods, # Passer les périodes à afficher pour affichage
        today_disabled_reason=today_disabled_reason,
        doctors=doctors # NOUVEAU: Passer la liste des médecins au template
    )

@patient_rdv_bp.route("/get_reserved_slots", methods=["GET"])
def get_reserved_slots_patient(admin_prefix):
    # ----- LOGIQUE CORRIGÉE -----
    full_email_for_utils = f"{admin_prefix}@gmail.com"
    utils.set_dynamic_base_dir(full_email_for_utils)
    set_patient_rdv_dirs()
    config = utils.load_config()
    # ----- FIN DE LA CORRECTION -----

    date_param, medecin_email_param = request.args.get("date"), request.args.get("medecin_email")
    medecin_email_param = request.args.get("medecin_email") # NOUVEAU: Récupérer l'email du médecin

    if not date_param or not medecin_email_param:
        return jsonify({"error": "Date or doctor email parameter is required"}), 400

    df = load_df() # Charge DonneesRDV.xlsx pour cet administrateur
    # NOUVEAU: Filtrer les créneaux par médecin
    reserved_slots = df[(df["Date"] == date_param) & (df["Medecin_Email"] == medecin_email_param)]["Heure"].tolist()

    # AJOUT : Vérifier si la date est désactivée
    disabled_periods = load_disabled_periods()
    disabled_reason = get_disabled_period_reason(date_param, disabled_periods)

    # NOUVEAU : Récupérer les paramètres de temps de la configuration pour générer tous les créneaux possibles
    rdv_start_time = config.get('rdv_start_time', '08:00')
    rdv_end_time = config.get('rdv_end_time', '17:45')
    rdv_interval_minutes = config.get('rdv_interval_minutes', 15)
    all_possible_slots = utils.generate_time_slots(
        rdv_start_time, rdv_end_time, rdv_interval_minutes
    )


    # Si la date est désactivée, tous les créneaux horaires sont considérés comme réservés
    if disabled_reason:
        return jsonify({"reserved_slots": all_possible_slots, "date_disabled": True, "reason": disabled_reason, "all_possible_slots": all_possible_slots}) # Renvoyer all_possible_slots
    
    return jsonify({"reserved_slots": reserved_slots, "date_disabled": False, "reason": None, "all_possible_slots": all_possible_slots}) # Renvoyer all_possible_slots


@patient_rdv_bp.route("/manage_disabled_periods", methods=["GET", "POST"])
def manage_disabled_periods(admin_prefix):
    if session.get('role') != 'admin':
        return redirect(url_for('login.login'))

    # ----- LOGIQUE CORRIGÉE ET UNIFORMISÉE -----
    full_email_for_utils = f"{admin_prefix}@gmail.com"
    utils.set_dynamic_base_dir(full_email_for_utils)
    set_patient_rdv_dirs()
    config = utils.load_config()
    theme_vars = theme.THEMES.get(config.get('theme', theme.DEFAULT_THEME), theme.THEMES[theme.DEFAULT_THEME])
    # ----- FIN DE LA CORRECTION -----
    theme_vars = theme.THEMES.get(config.get('theme', theme.DEFAULT_THEME), theme.THEMES[theme.DEFAULT_THEME])

    # NOUVEAU : Récupérer les paramètres de temps de la configuration pour générer les créneaux
    rdv_start_time = config.get('rdv_start_time', '08:00')
    rdv_end_time = config.get('rdv_end_time', '17:45')
    rdv_interval_minutes = config.get('rdv_interval_minutes', 15)
    all_available_timeslots = utils.generate_time_slots(
        rdv_start_time, rdv_end_time, rdv_interval_minutes
    )

    if request.method == "POST":
        action = request.form.get('action')

        if action == 'add':
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            reason = request.form.get('reason', '').strip()

            if not all([start_date_str, end_date_str, reason]):
                flash("Veuillez remplir tous les champs pour ajouter une période.", "warning")
            else:
                try:
                    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    if start_dt > end_dt:
                        flash("La date de début ne peut pas être postérieure à la date de fin.", "danger")
                    else:
                        periods = load_disabled_periods()
                        periods.append({
                            "start_date": start_date_str,
                            "end_date": end_date_str,
                            "reason": reason
                        })
                        save_disabled_periods(periods)
                        flash("Période désactivée ajoutée avec succès.", "success")
                except ValueError:
                    flash("Format de date invalide. UtilisezYYYY-MM-DD.", "danger")
        elif action == 'delete':
            index_to_delete = request.form.get('index', type=int)
            periods = load_disabled_periods()
            if 0 <= index_to_delete < len(periods):
                del periods[index_to_delete]
                save_disabled_periods(periods)
                flash("Période désactivée supprimée avec succès.", "success")
            else:
                flash("Index de période invalide.", "danger")
        return redirect(url_for('patient_rdv.manage_disabled_periods', admin_prefix=admin_prefix))

    disabled_periods = load_disabled_periods()
    return render_template_string(
        patient_rdv_template, # Utiliser le même template
        config=config,
        theme_vars=theme_vars,
        theme_names=list(theme.THEMES.keys()),
        iso_today=datetime.now().strftime("%Y-%m-%d"),
        role=session.get('role'), # Passer le rôle pour l'affichage conditionnel
        disabled_periods=disabled_periods, # Passer les périodes à afficher dans le tableau
        show_admin_panel=True, # Indiquer au template d'afficher le panneau admin
        message=None, # Pas de message initial
        timeslots=all_available_timeslots, # Always pass timeslots
        doctors=[] # Pas besoin de la liste des médecins pour le panneau admin
    )


# ------------------------------------------------------------------
# JINJA TEMPLATE (interface responsive pour la prise de RDV patient)
# ------------------------------------------------------------------
patient_rdv_template = r"""
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&family=Great+Vibes&display=swap" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
<title>Prendre RDV – {{ config.nom_clinique or 'EasyMedicaLink' }}</title>

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
    font-size: 2rem !important;
    color: white !important;
    display: flex;
    align-items: center;
    justify-content: center; /* Centrer le texte de la marque */
    flex-grow: 1; /* Permet au brand de prendre l'espace disponible */
    transition: transform 0.3s ease;
  }
  .navbar-brand:hover {
    transform: scale(1.05);
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

  /* Étapes du formulaire (Wizard Steps) */
  .step-circle {
    width: 3rem;
    height: 3rem;
    border-radius: 50%;
    background: var(--secondary-color);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 1.2rem;
    transition: all 0.3s ease;
    box-shadow: var(--shadow-light);
  }
  .step-circle.active {
    background: var(--primary-color);
    transform: scale(1.1);
    box-shadow: var(--shadow-medium);
  }
  .step-line {
    flex: 1;
    height: 4px;
    background: var(--secondary-color);
    transition: background 0.3s ease;
  }
  .step-line.active {
    background: var(--primary-color);
  }

  /* Étiquettes flottantes (Floating Labels) */
  .floating-label {
    position: relative;
    margin-bottom: 1rem;
  }
  .floating-label input,
  .floating-label select {
    padding: 1rem 0.75rem 0.5rem;
    height: auto;
    border-radius: var(--border-radius-sm);
    border: 1px solid var(--secondary-color);
    background-color: var(--card-bg);
    color: var(--text-color);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }
  .floating-label input:focus,
  .floating-label select:focus {
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
  .floating-label select:not([value=""]) + label {
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
    filter: {% if theme_vars.get('name') == 'dark' %}invert(1){% else %}none{% endif %};
  }

  /* Boutons radio de genre (Gender Radio Buttons) */
  .gender-btn {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
  }
  .gender-btn input {
    display: none;
  }
  .gender-btn label {
    flex: 1 1 calc(33.333% - 0.5rem);
    border: 2px solid var(--secondary-color);
    border-radius: var(--border-radius-md);
    padding: 0.75rem 0;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    text-align: center;
    user-select: none;
    background-color: var(--card-bg);
    color: var(--text-color);
    font-weight: 600;
  }
  .gender-btn label:hover {
    background-color: rgba(var(--secondary-color-rgb), 0.1);
  }
  .gender-btn input:checked + label {
    background: var(--gradient-main);
    color: var(--button-text);
    box-shadow: var(--shadow-medium);
    border-color: var(--primary-color);
  }

  /* Boutons (Buttons) */
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

  /* Messages Flash / SweetAlert */
  .alert-container {
    position: fixed;
    top: 70px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 1060;
    width: 90%;
    max-width: 500px;
  }

  /* Pied de page (Footer) */
  footer {
    background: var(--gradient-main);
    color: white;
    font-weight: 300;
    box-shadow: 0 -5px 15px rgba(0, 0, 0, 0.1);
    padding-top: 0.75rem;
    padding-bottom: 0.75rem;
  }

  /* Ajustements responsives (Responsive adjustments) */
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
    .gender-btn label {
      flex: 1 1 100%;
    }
    .btn {
      width: 100%;
      margin-bottom: 0.5rem;
    }
  }

  /* Styles pour le panneau d'administration */
  .admin-panel {
      border: 2px dashed var(--primary-color);
      border-radius: var(--border-radius-lg);
      padding: 1.5rem;
      margin-top: 2rem;
      background-color: rgba(var(--primary-color-rgb), 0.05); /* Légère transparence */
  }
  .admin-panel h4 {
      color: var(--primary-color);
  }
  .admin-panel label {
      font-weight: 600;
  }
  .disabled-periods-table th {
      background-color: var(--secondary-color);
      color: var(--button-text);
  }
  .disabled-periods-table tbody tr:nth-child(odd) {
      background-color: rgba(var(--secondary-color-rgb), 0.1);
  }
</style>
</head>
<body>

<nav class="navbar navbar-dark fixed-top">
  <div class="container-fluid d-flex align-items-center justify-content-center">
    <a class="navbar-brand d-flex align-items-center" href="#">
      <i class="fas fa-heartbeat me-2"></i>Prendre RDV
    </a>
    {# Bouton "Gérer Indisponibilités" retiré d'ici #}
  </div>
</nav>

<div class="container-fluid my-4">
  <div class="row justify-content-center">
    <div class="col-12">
      <div class="card shadow-lg">
        <div class="card-header py-3 text-center">
          <h1 class="mb-2 header-item">
            <i class="fas fa-hospital me-2"></i>
            {{ config.nom_clinique or config.cabinet or 'NOM CLINIQUE/CABINET/CENTRE MEDICAL' }}
          </h1>
          <div class="d-flex justify-content-center gap-4 flex-wrap">
            <div class="d-flex align-items-center header-item">
            </div>
            <div class="d-flex align-items-center header-item">
              <i class="fas fa-map-marker-alt me-2"></i><span>{{ config.location or 'LIEU' }}</span>
            </div>
          </div>
          <p class="mt-2 header-item">
            <i class="fas fa-calendar-day me-2"></i>Prenez votre rendez-vous en ligne
          </p>
        </div>
      </div>
    </div>
  </div>

<div class="container-fluid my-4">
  <div class="row justify-content-center">
    <div class="col-12 col-lg-10">
      {% if message %}
      <div class="alert alert-{{ message_type or 'info' }} alert-dismissible fade show" role="alert">
        {{ message }}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
      </div>
      {% endif %}

      {% if today_disabled_reason %}
        <div class="alert alert-warning text-center" role="alert">
            <i class="fas fa-exclamation-triangle me-2"></i>
            Le cabinet est actuellement fermé pour les rendez-vous en ligne pour cette période : <strong>{{ today_disabled_reason }}</strong>.
        </div>
      {% endif %}

      {# Section principale de prise de rendez-vous pour les patients #}
      {% if not show_admin_panel %}
        <div class="d-flex align-items-center mb-3">
          <div class="step-circle active" id="step1Circle">1</div>
          <div class="step-line" id="line1"></div>
          <div class="step-circle" id="step2Circle">2</div>
        </div>
        <form method="POST" class="card p-4 shadow-sm" id="wizardForm">
          <div id="step1">
            <h4 class="text-primary mb-3"><i class="fas fa-user me-2"></i>Vos informations</h4>
            <div class="row g-3">
              <div class="col-md-4 floating-label">
                <input type="text" name="patient_id" id="patient_id"
                       class="form-control" placeholder=" " required>
                <label for="patient_id">ID Patient (ex: Identité Nationale)</label>
              </div>
              <div class="col-md-4 floating-label">
                <input type="text" name="patient_nom" id="patient_nom"
                       class="form-control" placeholder=" " required>
                <label for="patient_nom">Nom</label>
              </div>
              <div class="col-md-4 floating-label">
                <input type="text" name="patient_prenom" id="patient_prenom"
                       class="form-control" placeholder=" " required>
                <label for="patient_prenom">Prénom</label>
              </div>
              <div class="col-12">
                <div class="gender-btn">
                  <input type="radio" id="genderM" name="patient_gender" value="Masculin" required>
                  <label for="genderM"><i class="fas fa-mars"></i> Masculin</label>
                  <input type="radio" id="genderF" name="patient_gender" value="Féminin" required>
                  <label for="genderF"><i class="fas fa-venus"></i> Féminin</label>
                  <input type="radio" id="genderO" name="patient_gender" value="Autre" required>
                  <label for="genderO"><i class="fas fa-genderless"></i> Autre</label>
                </div>
              </div>
              <div class="col-md-4 floating-label">
                <input type="date" name="patient_dob" id="patient_dob"
                       class="form-control" placeholder=" " required>
                <label for="patient_dob">Date de naissance</label>
              </div>
              <div class="col-md-4 floating-label">
                <input type="tel" name="patient_phone" id="patient_phone"
                       class="form-control" placeholder=" " required>
                <label for="patient_phone">Téléphone</label>
              </div>
              <div class="col-md-4 floating-label">
                <input type="text" name="patient_ant" id="patient_ant"
                       class="form-control" placeholder=" ">
                <label for="patient_ant">Antécédents médicaux</label>
              </div>
            </div>
            <button type="button" id="toStep2" class="btn btn-primary mt-3 w-100"> Suivant <i class="fas fa-arrow-right ms-1"></i>
            </button>
          </div>
          <div id="step2" class="d-none">
            <h4 class="text-primary mb-3"><i class="fas fa-calendar-plus me-2"></i>Choisissez votre RDV</h4>
            <div class="row g-3">
              <div class="col-md-6 floating-label">
                <input type="date" name="rdv_date" id="rdv_date"
                       value="{{ iso_today }}"
                       class="form-control" placeholder=" " required>
                <label for="rdv_date">Date souhaitée</label>
              </div>
              <div class="col-md-6 floating-label">
                <select name="medecin_select" id="medecin_select" class="form-select" required>
                  <option value="">Sélectionnez un médecin</option>
                  {% for doctor in doctors %}
                  <option value="{{ doctor.email }}">
                    {{ doctor.prenom }} {{ doctor.nom }}
                  </option>
                  {% endfor %}
                </select>
                <label for="medecin_select">Médecin</label>
              </div>
              <div class="col-12 floating-label">
                <select name="rdv_time" id="rdv_time" class="form-select" required>
                  {# Options chargées par JS #}
                </select>
                <label for="rdv_time">Heure souhaitée</label>
              </div>
            </div>
            <div class="d-flex justify-content-between mt-3"> <button type="button" id="backStep1" class="btn btn-outline-secondary">
                <i class="fas fa-arrow-left me-1"></i>Précédent
              </button>
              <button class="btn btn-success">
                <i class="fas fa-check-circle me-1"></i>Confirmer le RDV
              </button>
            </div>
          </div>
        </form>
      {% endif %}

      {# Panneau d'administration pour gérer les périodes désactivées #}
      {% if role == 'admin' and show_admin_panel %}
        <div class="admin-panel card p-4 shadow-sm">
            <h4 class="mb-3"><i class="fas fa-calendar-times me-2"></i>Gérer les périodes d'indisponibilité</h4>

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

            <form method="POST" action="{{ url_for('patient_rdv.manage_disabled_periods', admin_prefix=request.path.split('/')[2]) }}">
                <input type="hidden" name="action" value="add">
                <div class="row g-3 mb-3">
                    <div class="col-md-4">
                        <label for="start_date" class="form-label">Date de début</label>
                        <input type="date" name="start_date" id="start_date" class="form-control" required value="{{ iso_today }}">
                    </div>
                    <div class="col-md-4">
                        <label for="end_date" class="form-label">Date de fin</label>
                        <input type="date" name="end_date" id="end_date" class="form-control" required value="{{ iso_today }}">
                    </div>
                    <div class="col-md-4">
                        <label for="reason" class="form-label">Motif</label>
                        <input type="text" name="reason" id="reason" class="form-control" placeholder="Ex: Congés, Formation" required>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary"><i class="fas fa-plus-circle me-2"></i>Ajouter une période</button>
            </form>

            <h5 class="mt-4 mb-3">Périodes désactivées actuelles :</h5>
            {% if disabled_periods %}
                <div class="table-responsive">
                    <table class="table table-striped table-bordered disabled-periods-table">
                        <thead>
                            <tr>
                                <th>Début</th>
                                <th>Fin</th>
                                <th>Motif</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for period in disabled_periods %}
                            <tr>
                                <td>{{ period.start_date }}</td>
                                <td>{{ period.end_date }}</td>
                                <td>{{ period.reason }}</td>
                                <td>
                                    <form method="POST" action="{{ url_for('patient_rdv.manage_disabled_periods', admin_prefix=request.path.split('/')[2]) }}" onsubmit="return confirm('Êtes-vous sûr de vouloir supprimer cette période ?');">
                                        <input type="hidden" name="action" value="delete">
                                        <input type="hidden" name="index" value="{{ loop.index0 }}">
                                        <button type="submit" class="btn btn-danger btn-sm"><i class="fas fa-trash-alt"></i></button>
                                    </form>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            {% else %}
                <p class="text-muted">Aucune période désactivée n'est configurée pour le moment.</p>
            {% endif %}
            <div class="text-center mt-4">
                <a href="{{ url_for('administrateur_bp.dashboard') }}" class="btn btn-secondary">
                    <i class="fas fa-arrow-left me-2"></i>Retour à Admin
                </a>
            </div>
        </div>
      {% endif %}
    </div>
  </div>
</div>

<footer class="text-center py-3 small">
  SASTOUKA DIGITAL © 2025
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script>
document.addEventListener('DOMContentLoaded',()=>{
  /* Navigation de l'assistant (Wizard navigation) */
  const step1=document.getElementById('step1'),step2=document.getElementById('step2');
  const s1c=document.getElementById('step1Circle'),s2c=document.getElementById('step2Circle'),line1=document.getElementById('line1');

  const toStep2Button = document.getElementById('toStep2');
  if (toStep2Button) { // S'assurer que le bouton existe (il n'existera pas en mode admin)
    toStep2Button.onclick=()=>{
      // Validation de base pour l'étape 1 avant de continuer
      const patientId = document.getElementById('patient_id').value;
      const patientNom = document.getElementById('patient_nom').value;
      const patientPrenom = document.getElementById('patient_prenom').value;
      // Vérifier si au moins un bouton radio de genre est coché
      const patientGenderM = document.getElementById('genderM').checked;
      const patientGenderF = document.getElementById('genderF').checked;
      const patientGenderO = document.getElementById('genderO').checked;
      const isGenderSelected = patientGenderM || patientGenderF || patientGenderO;

      const patientDob = document.getElementById('patient_dob').value;
      const patientPhone = document.getElementById('patient_phone').value;
      const patientAnt = document.getElementById('patient_ant').value; // Antécédents peut être vide

      if (!patientId || !patientNom || !patientPrenom || !isGenderSelected || !patientDob || !patientPhone) {
        Swal.fire({
          icon: 'error',
          title: 'Champs manquants',
          text: 'Veuillez remplir tous les champs obligatoires (ID, Nom, Prénom, Sexe, Date de naissance, Téléphone) avant de continuer.',
          confirmButtonText: 'OK'
        });
        return;
      }

      step1.classList.add('d-none');step2.classList.remove('d-none');
      s1c.classList.remove('active');line1.classList.add('active');s2c.classList.add('active');
    };
  }

  const backStep1Button = document.getElementById('backStep1');
  if (backStep1Button) { // S'assurer que le bouton existe
    backStep1Button.onclick=()=>{
      step2.classList.add('d-none');step1.classList.remove('d-none');
      s2c.classList.remove('active');line1.classList.remove('active');s1c.classList.add('active');
    };
  }

  // Function to update time slots based on the selected date AND selected doctor
  function updateTimeSlots(selectedDate, selectedDoctorEmail) {
      const rdvTimeSelect = document.getElementById('rdv_time');
      const medecinSelect = document.getElementById('medecin_select');

      // Disable time slot selection if no doctor is chosen
      if (!selectedDoctorEmail) {
          rdvTimeSelect.innerHTML = '<option value="">Sélectionnez un médecin d\'abord</option>';
          rdvTimeSelect.disabled = true;
          return;
      }
      rdvTimeSelect.disabled = false; // Enable once a doctor is selected

      const adminPrefix = window.location.pathname.split('/')[2]; // Extract admin_prefix from URL

      fetch(`/patient_rdv/${adminPrefix}/get_reserved_slots?date=${encodeURIComponent(selectedDate)}&medecin_email=${encodeURIComponent(selectedDoctorEmail)}`)
          .then(response => response.json())
          .then(data => {
              const allTimeSlots = data.all_possible_slots; // Utiliser les créneaux possibles renvoyés par le backend

              rdvTimeSelect.innerHTML = ''; // Clear current options
              let hasSelectedOption = false;

              if (data.date_disabled) {
                  // If the date is disabled, disable all slots and show message
                  const option = document.createElement('option');
                  option.value = '';
                  option.textContent = 'Indisponible';
                  option.disabled = true;
                  rdvTimeSelect.appendChild(option);
                  Swal.fire({
                      icon: 'warning',
                      title: 'Date indisponible',
                      text: `Cette date est désactivée pour les rendez-vous. Motif : ${data.reason || 'Raison non spécifiée'}`,
                      confirmButtonText: 'OK'
                  });
              } else {
                  // Otherwise, populate normally and disable reserved slots
                  allTimeSlots.forEach(time => {
                      const option = document.createElement('option');
                      option.value = time;
                      option.textContent = time;
                      if (data.reserved_slots.includes(time)) {
                          option.disabled = true;
                      }
                      rdvTimeSelect.appendChild(option);
                  });
              }

              // Add default 'Sélectionnez une heure' if no option is selected/pre-selected
              if (!hasSelectedOption && rdvTimeSelect.options.length > 0) {
                  const defaultOption = document.createElement('option');
                  defaultOption.value = '';
                  defaultOption.textContent = 'Sélectionnez une heure';
                  defaultOption.selected = true;
                  defaultOption.disabled = true;
                  rdvTimeSelect.prepend(defaultOption);
              }
          })
          .catch(error => {
              console.error('Erreur lors de la récupération des créneaux réservés:', error);
              rdvTimeSelect.innerHTML = '<option value="">Erreur de chargement des heures</option>';
              rdvTimeSelect.disabled = true;
          });
  }

  // Event listener for RDV date change AND doctor selection change
  const rdvDateInput = document.getElementById('rdv_date');
  const medecinSelect = document.getElementById('medecin_select');

  if (rdvDateInput && medecinSelect) {
      // Trigger update when date or doctor changes
      rdvDateInput.addEventListener('change', function() {
          updateTimeSlots(this.value, medecinSelect.value);
      });
      medecinSelect.addEventListener('change', function() {
          updateTimeSlots(rdvDateInput.value, this.value);
      });

      // Initial call on page load to populate time slots based on initial date and (possibly empty) doctor selection
      updateTimeSlots(rdvDateInput.value, medecinSelect.value);
  }

    // Gestion du panneau d'administration des dates (Admin only)
    const isAdminPanel = {{ 'true' if show_admin_panel else 'false' }};
    if (isAdminPanel) {
        const startDateInput = document.getElementById('start_date');
        const endDateInput = document.getElementById('end_date');

        // Empêcher la date de fin d'être antérieure à la date de début
        startDateInput.addEventListener('change', function() {
            if (endDateInput.value < this.value) {
                endDateInput.value = this.value;
            }
            endDateInput.min = this.value;
        });

        // Appliquer la date minimale à la date de fin au chargement
        endDateInput.min = startDateInput.value;
    }
});
</script>
{% include '_floating_assistant.html' %} 
</body>
</html>
"""
