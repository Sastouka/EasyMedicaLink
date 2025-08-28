# gestion_patient.py
# ──────────────────────────────────────────────────────────────────────────────
# Module de gestion des patients et de génération de badges PDF.
# Gère l'ajout, la modification, la suppression et l'affichage des patients
# à partir du fichier Excel 'info_Base_patient.xlsx'.
# Permet de générer des badges PDF personnalisés pour chaque patient.
# ──────────────────────────────────────────────────────────────────────────────

from flask import Blueprint, render_template_string, request, redirect, url_for, flash, session, send_file, jsonify, get_flashed_messages
from datetime import datetime, date
import pandas as pd
import os
import io
import uuid # Importez uuid pour generer un consultation_id unique
from fpdf import FPDF
import qrcode
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter # Maintenu pour la concaténation de pages FPDF
import base64

# Imports internes
import utils
import theme
import login

# Création du Blueprint pour les routes de gestion des patients
gestion_patient_bp = Blueprint('gestion_patient', __name__, url_prefix='/gestion_patient')

# Définition manuelle du format A6 paysage pour FPDF (largeur, hauteur en mm)
# A6: 105mm x 148mm. En paysage: 148mm (largeur) x 105mm (hauteur)
PAGE_SIZE_A6_LANDSCAPE = (105, 148)

# --------------------------------------------------------------------------
# Fonctions d'aide pour la gestion des fichiers Excel
# --------------------------------------------------------------------------

def load_patients_df() -> pd.DataFrame:
    """Charge le DataFrame des patients depuis info_Base_patient.xlsx."""
    if utils.PATIENT_BASE_FILE is None:
        print("DEBUG: utils.PATIENT_BASE_FILE est None. Impossible de charger les patients.")
        return pd.DataFrame()

    print(f"DEBUG: Tentative de chargement du fichier Excel: {utils.PATIENT_BASE_FILE}")
    if not os.path.exists(utils.PATIENT_BASE_FILE):
        print(f"DEBUG: Le fichier {utils.PATIENT_BASE_FILE} n'existe pas. Création d'un nouveau fichier.")
        df = pd.DataFrame(columns=[
            "ID", "Nom", "Prenom", "DateNaissance", "Sexe", "Âge",
            "Antécédents", "Téléphone", "Email"
        ])
        df.to_excel(utils.PATIENT_BASE_FILE, index=False)
        print(f"DEBUG: Fichier {utils.PATIENT_BASE_FILE} initialisé et enregistré.")
        return df

    try:
        df = pd.read_excel(utils.PATIENT_BASE_FILE, dtype=str).fillna('')
        print(f"DEBUG: Fichier {utils.PATIENT_BASE_FILE} chargé avec succès.")
        print(f"DEBUG: Colonnes du DataFrame chargé: {df.columns.tolist()}")

        expected_cols = ["ID", "Nom", "Prenom", "DateNaissance", "Sexe", "Âge", "Antécédents", "Téléphone", "Email"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = ''
                print(f"DEBUG: Ajout de la colonne manquante: {col}")

        # S'assurer que 'ID' est un string sans espaces
        if 'ID' in df.columns:
            df['ID'] = df['ID'].astype(str).str.strip()
            print("DEBUG: Colonne 'ID' nettoyée (espaces supprimés).")

        return df
    except Exception as e:
        print(f"ERREUR: Erreur lors du chargement de {utils.PATIENT_BASE_FILE}: {e}")
        flash(f"Erreur lors du chargement des données patients: {e}", "danger")
        return pd.DataFrame()

def save_patients_df(df: pd.DataFrame):
    """Sauvegarde le DataFrame des patients dans info_Base_patient.xlsx."""
    if utils.PATIENT_BASE_FILE is None:
        print("DEBUG: utils.PATIENT_BASE_FILE est None. Impossible de sauvegarder les patients.")
        return False
    try:
        # S'assurer que 'ID' est un string sans espaces avant la sauvegarde
        if 'ID' in df.columns:
            df['ID'] = df['ID'].astype(str).str.strip()
            print("DEBUG: Colonne 'ID' nettoyée avant sauvegarde.")

        df.to_excel(utils.PATIENT_BASE_FILE, index=False)
        print(f"DEBUG: Fichier {utils.PATIENT_BASE_FILE} sauvegardé avec succès.")
        return True
    except Exception as e:
        print(f"ERREUR: Erreur lors de la sauvegarde de {utils.PATIENT_BASE_FILE}: {e}")
        flash(f"Erreur lors de la sauvegarde des données patients: {e}", "danger")
        return False

# --------------------------------------------------------------------------
# Fonctions de génération de badge PDF
# --------------------------------------------------------------------------

# --- Classe de génération du PDF ---
class PatientBadgePDF(FPDF):
    def __init__(self, config, patient_data, rdv_link_qr_data_uri, logged_in_full_name=None):
        super().__init__(orientation='L', unit='mm', format=PAGE_SIZE_A6_LANDSCAPE)
        print(f"DEBUG PDF Init: FPDF initialized with orientation='L', format={PAGE_SIZE_A6_LANDSCAPE}. Actual page size: w={self.w}mm, h={self.h}mm")
        self.config = config
        self.patient_data = patient_data
        self.rdv_link_qr_data_uri = rdv_link_qr_data_uri
        self.logged_in_full_name = logged_in_full_name
        self.set_auto_page_break(auto=False)
        self.add_page()
        self.primary_color = (33, 150, 243)
        self.secondary_color = (76, 175, 80)
        self.text_color_dark = (50, 50, 50)
        self.text_color_light = (100, 100, 100)
        self.bg_light = (240, 248, 255)

    def generate_qr_code_data_uri(self, data: str) -> str:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"

    def print_badge(self):
        print(f"DEBUG print_badge: Current FPDF page dimensions: w={self.w}mm, h={self.h}mm")
        page_width = self.w
        page_height = self.h

        margin_x = 10
        margin_y = 8
        qr_size = 32
        qr_offset_y = (page_height - qr_size) / 2

        # Définir la zone de texte centrale pour éviter les QR codes
        # Ajouter un padding pour s'assurer qu'il n'y a pas de chevauchement
        padding_around_qr = 0 # Espace entre le QR et le texte central

        effective_left_bound = margin_x + qr_size + padding_around_qr
        effective_right_bound = page_width - margin_x - qr_size - padding_around_qr

        text_area_start_x = effective_left_bound
        text_area_width = effective_right_bound - effective_left_bound

        # S'assurer d'une largeur minimale si la zone est trop petite
        if text_area_width < 50:
            text_area_width = 50
            text_area_start_x = (page_width - text_area_width) / 2

        text_area_y = margin_y
        text_area_height = page_height - (2 * margin_y)

        print(f"DEBUG Layout: text_area_start_x={text_area_start_x}mm, text_area_width={text_area_width}mm, text_area_height={text_area_height}mm")

        # Insertion du logo en arrière-plan avec 50% d'opacité
        if utils.background_file and os.path.exists(utils.background_file) and \
           utils.background_file.lower().endswith(('.png','.jpg','.jpeg','.gif','.bmp')):
            try:
                img_path = utils.background_file
                img_pil = Image.open(img_path).convert("RGBA")

                # Ajuster l'opacité à 50%
                alpha = img_pil.split()[3]
                alpha = Image.eval(alpha, lambda x: x * 0.5)
                img_pil.putalpha(alpha)

                # Calculer la taille et la position pour centrer le logo sur toute la page
                central_bg_image_max_width = page_width * 0.7
                central_bg_image_max_height = page_height * 0.7
                original_width, original_height = img_pil.size
                aspect_ratio = original_width / original_height

                if (central_bg_image_max_width / aspect_ratio) > central_bg_image_max_height:
                    scaled_width = central_bg_image_max_height * aspect_ratio
                    scaled_height = central_bg_image_max_height
                else:
                    scaled_width = central_bg_image_max_width
                    scaled_height = central_bg_image_max_width / aspect_ratio

                scaled_width_px = int(scaled_width * self.dpi / 25.4)
                scaled_height_px = int(scaled_height * self.dpi / 25.4)

                img_pil = img_pil.resize((scaled_width_px, scaled_height_px), Image.LANCZOS)

                central_bg_image_x = (page_width - scaled_width) / 2
                central_bg_image_y = (page_height - scaled_height) / 2

                buffered_central_img = io.BytesIO()
                img_pil.save(buffered_central_img, format="PNG")
                buffered_central_img.seek(0)

                self.image(buffered_central_img, x=central_bg_image_x, y=central_bg_image_y, w=scaled_width, h=scaled_height)
            except Exception as e:
                print(f"Erreur lors de l'insertion du logo en arrière-plan du badge: {e}")

        self.set_line_width(0.5)
        self.set_draw_color(self.primary_color[0], self.primary_color[1], self.primary_color[2])
        self.rect(margin_x / 2, margin_y / 2, page_width - margin_x, page_height - margin_y)

        # --- QR Code Patient (Gauche) ---
        patient_qr_data = (
            f"ID: {self.patient_data.get('ID', 'N/A')}\n"
            f"Nom: {self.patient_data.get('Nom', 'N/A')}\n"
            f"Prénom: {self.patient_data.get('Prenom', 'N/A')}\n"
            f"Clinique: {self.config.get('nom_clinique', 'N/A')}\n"
            f"Médecin: {self.config.get('doctor_name', 'N/A')}"
        )
        patient_qr_img_data_uri = self.generate_qr_code_data_uri(patient_qr_data)
        patient_qr_image_bytes = base64.b64decode(patient_qr_img_data_uri.split(',')[1])
        patient_qr_image = Image.open(io.BytesIO(patient_qr_image_bytes))
        self.image(patient_qr_image, x=margin_x, y=qr_offset_y, w=qr_size, h=qr_size)

        self.set_font('Helvetica', '', 6)
        self.set_text_color(self.text_color_dark[0], self.text_color_dark[1], self.text_color_dark[2])
        self.set_xy(margin_x, qr_offset_y + qr_size + 1)
        self.cell(qr_size, 3, "Scan Info Patient", 0, 0, 'C')

        # --- QR Code Lien RDV (Droite) ---
        rdv_qr_image_bytes = base64.b64decode(self.rdv_link_qr_data_uri.split(',')[1])
        rdv_qr_image = Image.open(io.BytesIO(rdv_qr_image_bytes))
        self.image(rdv_qr_image, x=page_width - margin_x - qr_size, y=qr_offset_y, w=qr_size, h=qr_size)

        self.set_font('Helvetica', '', 6)
        self.set_xy(page_width - margin_x - qr_size, qr_offset_y + qr_size + 1)
        self.multi_cell(qr_size, 3, "Scan pour RDV", 0, 'C')

        # Afficher l'adresse complète du lien de prise de RDV sous le QR de RDV
        self.set_font('Helvetica', '', 4) # Police très petite pour l'URL complète
        self.set_text_color(self.text_color_light[0], self.text_color_light[1], self.text_color_light[2])
        self.set_xy(page_width - margin_x - qr_size, self.get_y())
        original_rdv_link = self.config.get('rdv_base_url', 'Lien de RDV non disponible')
        self.multi_cell(qr_size, 2, original_rdv_link, 0, 'C')

        # --- Zone de texte centrale : Informations Clinique/Médecin ---
        current_y = text_area_y + 3 # Début de la zone de contenu textuel

        # Nom de la clinique / cabinet / centre médical (affichage tel quel)
        final_clinic_name_for_display = ""
        if self.config.get('nom_clinique'):
            final_clinic_name_for_display = self.config['nom_clinique']
        elif self.config.get('cabinet'):
            final_clinic_name_for_display = self.config['cabinet']
        elif self.config.get('centre_medical'):
            final_clinic_name_for_display = self.config['centre_medical']
        else:
            final_clinic_name_for_display = "NOM CLINIQUE/CABINET/CENTRE MEDICAL" # Valeur de secours si rien n'est configuré

        # Alignement du nom de l'établissement
        self.set_xy(text_area_start_x, current_y)
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(self.primary_color[0], self.primary_color[1], self.primary_color[2])

        text_width_clinic = self.get_string_width(final_clinic_name_for_display)
        if text_width_clinic <= text_area_width:
            self.cell(text_area_width, 7, final_clinic_name_for_display, 0, 1, 'C')
        else:
            self.multi_cell(text_area_width, 7, final_clinic_name_for_display, 0, 'C')
        current_y = self.get_y() # Mettre à jour current_y après l'impression du nom de la clinique

        # Nom du médecin et lieu
        self.set_x(text_area_start_x)
        self.set_font('Helvetica', '', 10)
        self.set_text_color(self.text_color_dark[0], self.text_color_dark[1], self.text_color_dark[2])

        # LOGIQUE MODIFIÉE POUR LE NOM DU MÉDECIN :
        # Priorité : 1. Nom complet du médecin connecté (logged_in_full_name), 2. Nom du médecin configuré (doctor_name), 3. "Nom du Médecin"
        doctor_display_name = ""
        if self.logged_in_full_name and self.logged_in_full_name != 'None':
            doctor_display_name = self.logged_in_full_name
        elif self.config.get('doctor_name'):
            doctor_display_name = self.config['doctor_name']
        else:
            doctor_display_name = "Nom du Médecin"

        # Le format est "NOM DU MÉDECIN - Lieu"
        full_info_line = f"Dr. {doctor_display_name} - {self.config.get('location', 'Lieu')}"
        text_width_doctor = self.get_string_width(full_info_line)
        if text_width_doctor <= text_area_width:
            self.cell(text_area_width, 5, full_info_line, 0, 1, 'C')
        else:
            self.multi_cell(text_area_width, 5, full_info_line, 0, 'C')

        current_y = self.get_y() + 4

        # Ligne de séparation élégante (ÉLIMINÉE)
        current_y += 5

        # --- Informations Patient (Mises en avant) ---
        # Alignement "INFORMATIONS PATIENT"
        self.set_x(text_area_start_x)
        self.set_font('Helvetica', 'BU', 11)
        self.set_text_color(self.primary_color[0], self.primary_color[1], self.primary_color[2])
        self.multi_cell(text_area_width, 6, "INFORMATIONS PATIENT", 0, 'C')
        current_y = self.get_y() + 3

        # Nom et Prénom du patient
        self.set_x(text_area_start_x)
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(self.text_color_dark[0], self.text_color_dark[1], self.text_color_dark[2])
        patient_full_name = f"{self.patient_data.get('Nom', 'N/A').upper()} {self.patient_data.get('Prenom', 'N/A')}"
        self.multi_cell(text_area_width, 8, patient_full_name, 0, 'C')
        current_y = self.get_y() + 2

        # ID Patient
        self.set_x(text_area_start_x)
        self.set_font('Helvetica', '', 10)
        self.set_text_color(self.text_color_dark[0], self.text_color_dark[1], self.text_color_dark[2])
        self.multi_cell(text_area_width, 5, f"ID: {self.patient_data.get('ID', 'N/A')}", 0, 'C')
        current_y = self.get_y() + 4

        # Autres informations du patient
        self.set_font('Helvetica', '', 9)
        self.set_text_color(self.text_color_dark[0], self.text_color_dark[1], self.text_color_dark[2])

        data_rows = [
            ("Date de Naissance", self.patient_data.get('DateNaissance', 'N/A')),
            ("Sexe", self.patient_data.get('Sexe', 'N/A')),
            ("Âge", self.patient_data.get('Âge', 'N/A')),
            ("Téléphone", self.patient_data.get('Téléphone', 'N/A')),
            # ("Email", self.patient_data.get('Email', 'N/A')) # ÉLIMINÉ
        ]

        for label, value in data_rows:
            # Change 'L' to 'C' for center alignment and remove '- ' prefix
            self.set_x(text_area_start_x) # Reset X to start of text area for centering
            self.multi_cell(text_area_width, 4.5, f"{label}: {value}", 0, 'C')
            current_y = self.get_y()

        # --- Message de pied de page du badge ---
        final_message_y = page_height - margin_y - 7
        self.set_y(final_message_y)
        self.set_x(text_area_start_x)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(self.text_color_light[0], self.text_color_light[1], self.text_color_light[2])
        self.multi_cell(text_area_width, 3, "Veuillez présenter ce badge lors de votre prochaine visite. Pour toute question, contactez la clinique.", 0, 'C')

@gestion_patient_bp.route('/')
def home_gestion_patient():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    if utils.EXCEL_FOLDER is None:
        if 'admin_email' in session:
            utils.set_dynamic_base_dir(session['admin_email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))

    config = utils.load_config()
    session['theme'] = config.get('theme', theme.DEFAULT_THEME)
    host_address = f"http://{utils.LOCAL_IP}:3000"
    current_date = datetime.now().strftime("%Y-%m-%d")

    patients_df = load_patients_df()
    patients_list = patients_df.to_dict(orient='records')

    # Passer les messages flash au template pour que JavaScript puisse les lire
    flashed_messages = get_flashed_messages(with_categories=True)

    # --- DÉBUT DES MODIFICATIONS/AJOUTS ---
    logged_in_full_name = None 
    user_email = session.get('email')
    
    if user_email:
        all_users_data = login.load_users()
        user_info = all_users_data.get(user_email)
        if user_info:
            logged_in_full_name = f"{user_info.get('prenom', '')} {user_info.get('nom', '')}".strip()
            if not logged_in_full_name:
                logged_in_full_name = None
    # --- FIN DES MODIFICATIONS/AJOUTS ---

    return render_template_string(
        gestion_patient_template,
        config=config,
        theme_vars=theme.current_theme(),
        theme_names=list(theme.THEMES.keys()),
        host_address=host_address,
        current_date=current_date,
        patients=patients_list,
        flashed_messages=flashed_messages, # Passer les messages flash ici
        # --- PASSER LA NOUVELLE VARIABLE AU TEMPLATE ---
        logged_in_doctor_name=logged_in_full_name # Utilise le même nom de variable que dans main_template pour cohérence
        # --- FIN DU PASSAGE ---
    )

@gestion_patient_bp.route('/add_patient', methods=['POST'])
def add_patient():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    f = request.form
    patient_id = f.get('ID').strip()
    nom = f.get('Nom').strip()
    prenom = f.get('Prenom').strip()
    date_naissance = f.get('DateNaissance').strip()
    sexe = f.get('Sexe').strip()
    antecedents = f.get('Antécédents').strip()
    telephone = f.get('Téléphone').strip()
    email = f.get('Email').strip()

    if not all([patient_id, nom, prenom, date_naissance, sexe, telephone]):
        flash("Veuillez remplir tous les champs obligatoires (ID, Nom, Prénom, Date de Naissance, Sexe, Téléphone).", "warning")
        return redirect(url_for('gestion_patient.home_gestion_patient'))

    patients_df = load_patients_df()

    if patient_id in patients_df['ID'].values:
        flash(f"Un patient avec l'ID '{patient_id}' existe déjà.", "danger")
        return redirect(url_for('gestion_patient.home_gestion_patient'))

    age = ""
    try:
        dob_date = datetime.strptime(date_naissance, "%Y-%m-%d").date()
        today_date = date.today()
        years = today_date.year - dob_date.year - ((today_date.month, today_date.day) < (dob_date.month, dob_date.day))
        months = today_date.month - dob_date.month - (today_date.day < dob_date.day)
        if months < 0:
            months += 12
        age = f"{years} ans {months} mois"
    except ValueError:
        flash("Format de date de naissance invalide. Utilisez AAAA-MM-JJ.", "warning")
        return redirect(url_for('gestion_patient.home_gestion_patient'))

    new_patient = {
        "ID": patient_id,
        "Nom": nom,
        "Prenom": prenom,
        "DateNaissance": date_naissance,
        "Sexe": sexe,
        "Âge": age,
        "Antécédents": antecedents,
        "Téléphone": telephone,
        "Email": email
    }

    patients_df = pd.concat([patients_df, pd.DataFrame([new_patient])], ignore_index=True)
    if save_patients_df(patients_df):
        flash("Patient ajouté avec succès!", "success_and_redirect_to_list") # Catégorie spécifique
        utils.load_patient_data()
    return redirect(url_for('gestion_patient.home_gestion_patient'))

@gestion_patient_bp.route('/edit_patient', methods=['POST'])
def edit_patient():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    f = request.form
    original_patient_id = f.get('original_ID').strip()
    patient_id = f.get('ID').strip()
    nom = f.get('Nom').strip()
    prenom = f.get('Prenom').strip()
    date_naissance = f.get('DateNaissance').strip()
    sexe = f.get('Sexe').strip()
    antecedents = f.get('Antécédents').strip()
    telephone = f.get('Téléphone').strip()
    email = f.get('Email').strip()

    if not all([patient_id, nom, prenom, date_naissance, sexe, telephone]):
        flash("Veuillez remplir tous les champs obligatoires (ID, Nom, Prénom, Date de Naissance, Sexe, Téléphone).", "warning")
        return redirect(url_for('gestion_patient.home_gestion_patient'))

    patients_df = load_patients_df()

    if patient_id != original_patient_id and patient_id in patients_df['ID'].values:
        flash(f"Le nouvel ID '{patient_id}' existe déjà pour un autre patient.", "danger")
        return redirect(url_for('gestion_patient.home_gestion_patient'))

    age = ""
    try:
        dob_date = datetime.strptime(date_naissance, "%Y-%m-%d").date()
        today_date = date.today()
        years = today_date.year - dob_date.year - ((today_date.month, today_date.day) < (dob_date.month, dob_date.day))
        months = today_date.month - dob_date.month - (today_date.day < dob_date.day)
        if months < 0:
            months += 12
        age = f"{years} ans {months} mois"
    except ValueError:
        flash("Format de date de naissance invalide. Utilisez AAAA-MM-JJ.", "warning")
        return redirect(url_for('gestion_patient.home_gestion_patient'))

    idx = patients_df[patients_df['ID'] == original_patient_id].index
    if idx.empty:
        flash("Patient introuvable pour la modification.", "danger")
        return redirect(url_for('gestion_patient.home_gestion_patient'))

    patients_df.loc[idx, "ID"] = patient_id
    patients_df.loc[idx, "Nom"] = nom
    patients_df.loc[idx, "Prenom"] = prenom
    patients_df.loc[idx, "DateNaissance"] = date_naissance
    patients_df.loc[idx, "Sexe"] = sexe
    patients_df.loc[idx, "Âge"] = age
    patients_df.loc[idx, "Antécédents"] = antecedents
    patients_df.loc[idx, "Téléphone"] = telephone
    patients_df.loc[idx, "Email"] = email

    if save_patients_df(patients_df):
        flash("Patient mis à jour avec succès!", "success_and_redirect_to_list") # Catégorie spécifique
        utils.load_patient_data()
    return redirect(url_for('gestion_patient.home_gestion_patient'))

@gestion_patient_bp.route('/delete_patient/<patient_id>', methods=['POST'])
def delete_patient(patient_id):
    if 'email' not in session:
        return jsonify(success=False, message="Non autorisé"), 401

    patients_df = load_patients_df()
    original_rows_count = len(patients_df)

    patients_df = patients_df[patients_df['ID'] != patient_id]

    if len(patients_df) < original_rows_count:
        if save_patients_df(patients_df):
            flash("Patient supprimé avec succès!", "success_and_redirect_to_list") # Catégorie spécifique
            utils.load_patient_data()
            return jsonify(success=True)
        else:
            return jsonify(success=False, message="Erreur lors de la suppression du patient."), 500
    else:
        return jsonify(success=False, message="Patient non trouvé."), 404

@gestion_patient_bp.route('/get_patient_details/<patient_id>', methods=['GET'])
def get_patient_details(patient_id):
    if 'email' not in session:
        return jsonify(error="Non autorisé"), 401

    patients_df = load_patients_df()
    patient_data = patients_df[patients_df['ID'] == patient_id].to_dict(orient='records')

    if patient_data:
        return jsonify(patient_data[0])
    return jsonify(error="Patient non trouvé"), 404

@gestion_patient_bp.route('/generate_badge/<patient_id>')
def generate_badge(patient_id):
    if 'email' not in session:
        return redirect(url_for('login.login'))

    print(f"DEBUG: Tenter de générer un badge pour le patient ID: '{patient_id}'")
    patients_df = load_patients_df()
    print(f"DEBUG: DataFrame des patients chargé. Contient {len(patients_df)} entrées.")
    if not patients_df.empty:
        print(f"DEBUG: IDs présents dans le DataFrame: {patients_df['ID'].tolist()}")
    else:
        print("DEBUG: Le DataFrame des patients est vide.")

    patient_id_stripped = str(patient_id).strip()

    patient_data = patients_df[patients_df['ID'] == patient_id_stripped].to_dict(orient='records')

    if not patient_data:
        print(f"ERREUR: Patient avec l'ID '{patient_id_stripped}' non trouvé dans le DataFrame.")
        flash("Patient non trouvé pour générer le badge.", "danger")
        return redirect(url_for('gestion_patient.home_gestion_patient'))

    patient_data = patient_data[0]
    print(f"DEBUG: Données du patient trouvées pour '{patient_id_stripped}': {patient_data}")

    config = utils.load_config()

    admin_email_prefix = session.get('admin_email', 'default_admin@example.com').split('@')[0]
    patient_appointment_link = url_for('patient_rdv.patient_rdv_home', admin_prefix=admin_email_prefix, _external=True)

    config['rdv_base_url'] = patient_appointment_link

    # Récupérer le nom complet de l'utilisateur connecté pour le passer au badge
    logged_in_full_name = None
    user_email = session.get('email')
    if user_email:
        all_users_data = login.load_users()
        user_info = all_users_data.get(user_email)
        if user_info:
            logged_in_full_name = f"{user_info.get('prenom', '')} {user_info.get('nom', '')}".strip()
            if not logged_in_full_name:
                logged_in_full_name = None


    temp_pdf_instance = PatientBadgePDF(config, {}, "", logged_in_full_name) # Passer logged_in_full_name
    rdv_link_qr_data_uri = temp_pdf_instance.generate_qr_code_data_uri(patient_appointment_link)

    pdf = PatientBadgePDF(config, patient_data, rdv_link_qr_data_uri, logged_in_full_name) # PASSER logged_in_full_name ICI
    pdf.print_badge()

    response = io.BytesIO()
    pdf.output(response, 'S')
    response.seek(0)

    badge_filename = f"Badge_Patient_{patient_data.get('Nom', '')}_{patient_data.get('Prenom', '')}_{patient_data.get('ID', '')}.pdf"

    return send_file(response, as_attachment=True, download_name=badge_filename, mimetype='application/pdf')


@gestion_patient_bp.route('/generate_all_badges')
def generate_all_badges():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    patients_df = load_patients_df()
    if patients_df.empty:
        flash("Aucun patient enregistré pour générer les badges.", "warning")
        return redirect(url_for('gestion_patient.home_gestion_patient'))

    config = utils.load_config()
    admin_email_prefix = session.get('admin_email', 'default_admin@example.com').split('@')[0]
    patient_appointment_link = url_for('patient_rdv.patient_rdv_home', admin_prefix=admin_email_prefix, _external=True)

    # Récupérer le nom complet de l'utilisateur connecté pour le passer au badge
    logged_in_full_name = None
    user_email = session.get('email')
    if user_email:
        all_users_data = login.load_users()
        user_info = all_users_data.get(user_email)
        if user_info:
            logged_in_full_name = f"{user_info.get('prenom', '')} {user_info.get('nom', '')}".strip()
            if not logged_in_full_name:
                logged_in_full_name = None

    from PyPDF2 import PdfWriter, PdfReader

    pdf_writer = PdfWriter()

    temp_pdf_instance = PatientBadgePDF(config, {}, "", logged_in_full_name) # Passer logged_in_full_name
    rdv_link_qr_data_uri = temp_pdf_instance.generate_qr_code_data_uri(patient_appointment_link)

    for _, patient_data in patients_df.iterrows():
        config['rdv_base_url'] = patient_appointment_link
        pdf = PatientBadgePDF(config, patient_data.to_dict(), rdv_link_qr_data_uri, logged_in_full_name) # PASSER logged_in_full_name ICI
        pdf.print_badge()

        individual_badge_buffer = io.BytesIO()
        pdf.output(individual_badge_buffer, 'S')
        individual_badge_buffer.seek(0)

        individual_pdf_reader = PdfReader(individual_badge_buffer)

        for page_num in range(len(individual_pdf_reader.pages)):
            page = individual_pdf_reader.pages[page_num]
            pdf_writer.add_page(page)

    final_output_buffer = io.BytesIO()
    pdf_writer.write(final_output_buffer)
    final_output_buffer.seek(0)

    all_badges_filename = f"Tous_Badges_Patients_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"

    return send_file(final_output_buffer, as_attachment=True, download_name=all_badges_filename, mimetype='application/pdf')

# NOUVELLE ROUTE POUR LE TRANSFERT VERS LA CONSULTATION
@gestion_patient_bp.route('/transfer_to_consultation', methods=['POST'])
def transfer_to_consultation():
    if 'email' not in session:
        return jsonify(success=False, message="Non autorisé"), 401

    patient_id = request.form.get('patient_id')

    if not patient_id:
        return jsonify(success=False, message="ID patient manquant."), 400

    # 1. Charger les détails complets du patient depuis info_Base_patient.xlsx
    patients_df = load_patients_df()
    patient_row = patients_df[patients_df['ID'] == patient_id]

    if patient_row.empty:
        return jsonify(success=False, message="Patient non trouvé dans la base de données."), 404

    patient_data = patient_row.iloc[0].to_dict()

    # 2. Préparer les données pour ConsultationData.xlsx
    # Assurez-vous que utils.EXCEL_FOLDER est bien défini par le before_request de Flask
    if utils.EXCEL_FOLDER is None:
        return jsonify(success=False, message="Erreur interne : répertoire Excel non défini."), 500

    consultation_file_path = os.path.join(utils.EXCEL_FOLDER, 'ConsultationData.xlsx')

    # Définir toutes les colonnes attendues dans ConsultationData.xlsx
    # Ces colonnes doivent correspondre à celles utilisées dans routes.py pour l'enregistrement
    consultation_columns = [
        "consultation_date", "patient_id", "patient_name", "nom", "prenom",
        "date_of_birth", "gender", "age", "patient_phone", "antecedents",
        "clinical_signs", "bp", "temperature", "heart_rate", "respiratory_rate",
        "diagnosis", "medications", "analyses", "radiologies",
        "certificate_category", "certificate_content", "rest_duration",
        "doctor_comment", "consultation_id", "Medecin_Email"
    ]

    df_consult = pd.DataFrame()
    if os.path.exists(consultation_file_path):
        try:
            df_consult = pd.read_excel(consultation_file_path, dtype=str).fillna('')
            # Assurer que toutes les colonnes requises existent dans le DataFrame existant
            for col in consultation_columns:
                if col not in df_consult.columns:
                    df_consult[col] = ''
        except Exception as e:
            print(f"Erreur lors du chargement de ConsultationData.xlsx: {e}")
            # Si le fichier est corrompu ou illisible, initialiser un nouveau DataFrame vide
            df_consult = pd.DataFrame(columns=consultation_columns)
    else:
        # Si le fichier n'existe pas, créer un DataFrame avec les en-têtes
        df_consult = pd.DataFrame(columns=consultation_columns)

    # Vérifier si une consultation existe déjà pour ce patient à cette date
    current_date = datetime.now().strftime("%Y-%m-%d")
    existing_consult = df_consult[
        (df_consult['patient_id'] == patient_id) &
        (df_consult['consultation_date'] == current_date)
    ]

    if not existing_consult.empty:
        return jsonify(success=False, message="Une consultation existe déjà pour ce patient aujourd'hui. Veuillez modifier la consultation existante ou choisir un autre patient."), 409 # Conflict

    # Remplir les données de la nouvelle consultation
    new_consult_data = {
        "consultation_date": current_date,
        "patient_id": patient_data.get('ID', ''),
        "patient_name": f"{patient_data.get('Nom', '')} {patient_data.get('Prenom', '')}".strip(),
        "nom": patient_data.get('Nom', ''),
        "prenom": patient_data.get('Prenom', ''),
        "date_of_birth": patient_data.get('DateNaissance', ''),
        "gender": patient_data.get('Sexe', ''),
        "age": patient_data.get('Âge', ''),
        "patient_phone": patient_data.get('Téléphone', ''),
        "antecedents": patient_data.get('Antécédents', ''),
        "clinical_signs": "", # Vide par défaut
        "bp": "", "temperature": "", "heart_rate": "", "respiratory_rate": "",
        "diagnosis": "", "medications": "", "analyses": "", "radiologies": "",
        "certificate_category": "", "certificate_content": "", "rest_duration": "",
        "doctor_comment": "",
        "consultation_id": str(uuid.uuid4()), # Générer un ID unique pour la consultation
        "Medecin_Email": session.get('email', '') # Associer la consultation à l'email du médecin/utilisateur connecté
    }

    # Assurez-vous que l'ordre des colonnes est respecté lors de la concaténation
    new_consult_df = pd.DataFrame([new_consult_data], columns=consultation_columns)
    df_consult = pd.concat([df_consult, new_consult_df], ignore_index=True)

    try:
        df_consult.to_excel(consultation_file_path, index=False)
        return jsonify(success=True, message="Consultation créée avec succès dans ConsultationData.xlsx."), 200
    except Exception as e:
        return jsonify(success=False, message=f"Erreur lors de l'enregistrement de la consultation : {e}"), 500

# --------------------------------------------------------------------------
# JINJA TEMPLATE pour la gestion des patients
# --------------------------------------------------------------------------
gestion_patient_template = """
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Gestion Patients – {{ config.nom_clinique or 'EasyMedicaLink' }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&family=Great+Vibes&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- Liens pour DataTables et Responsive -->
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/responsive/2.5.0/css/responsive.bootstrap5.min.css">
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
        /* DataTable specific styles for better appearance */
        .dataTables_wrapper .dataTables_filter input {
            border-radius: var(--border-radius-sm);
            border: 1px solid var(--secondary-color);
            background-color: var(--card-bg);
            color: var(--text-color);
            padding: 0.5rem 0.75rem;
            margin-left: 0.5rem;
            width: auto;
        }
        .dataTables_wrapper .dataTables_filter label {
            color: var(--text-color);
            font-weight: 500;
        }
        .dataTables_wrapper .dataTables_length select {
            border-radius: var(--border-radius-sm);
            border: 1px solid var(--secondary-color);
            background-color: var(--card-bg);
            color: var(--text-color);
            padding: 0.25rem 0.5rem;
            margin: 0 0.5rem;
            -webkit-appearance: none;
            -moz-appearance: none;
            appearance: none;
            padding-right: 1.5em;
        }
        .dataTables_wrapper .dataTables_length select::-ms-expand {
            display: none;
        }
        .dataTables_wrapper .dataTables_length label {
            color: var(--text-color);
            font-weight: 500;
        }
        .dataTables_wrapper .dataTables_info {
            color: var(--text-color-light);
            font-size: 0.9rem;
        }
        .dataTables_wrapper .dataTables_paginate .paginate_button {
            border-radius: var(--border-radius-sm);
            margin: 0 0.2rem;
            padding: 0.5rem 0.75rem;
            background-color: var(--card-bg);
            color: var(--primary-color) !important;
            border: 1px solid var(--primary-color);
            transition: all 0.2s ease;
        }
        .dataTables_wrapper .dataTables_paginate .paginate_button.current,
        .dataTables_wrapper .dataTables_paginate .paginate_button.current:hover {
            background: var(--gradient-main) !important;
            color: white !important;
            border-color: var(--primary-color);
        }
        .dataTables_wrapper .dataTables_paginate .paginate_button:hover {
            background-color: var(--secondary-color);
            color: white !important;
        }
        .table {
            --bs-table-bg: var(--card-bg);
            --bs-table-striped-bg: var(--bg-color);
            --bs-table-hover-bg: rgba(var(--primary-color-rgb), 0.1);
            color: var(--text-color);
            /* Removed width: 100% !important; here to allow content to overflow */
        }
        .table thead {
            background-color: var(--primary-color);
            color: white;
        }
        .table th {
                padding: 1rem;
                border-bottom: 2px solid var(--secondary-color);
            }
            .table td {
                padding: 0.75rem;
                vertical-align: middle;
                white-space: nowrap; /* Empêche le texte de se couper */
            }
            .badge {
                padding: 0.5em 0.75em;
                border-radius: 0.5rem;
                font-size: 0.85em;
                font-weight: 600;
                display: inline-flex;
                align-items: center;
            }
            .badge i {
                margin-right: 0.25rem;
                font-size: 0.9em;
            }
        /* Force le défilement horizontal pour les tableaux responsives */
        .table-responsive {
            overflow-x: auto !important; 
            -webkit-overflow-scrolling: touch; /* Améliore le défilement sur iOS */
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
                    <i class="fas fa-home me-2"></i>
                    <i class="fas fa-heartbeat me-2"></i>EasyMedicaLink
                </a>
            </div>
        </nav>

        <div class="offcanvas offcanvas-start" tabindex="-1" id="settingsOffcanvas">
            <div class="offcanvas-header text-white">
                <h5 class="offcanvas-title"><i class="fas fa-cog me-2"></i>Paramètres</h5>
                <button type="button" class="btn-close" data-bs-dismiss="offcanvas"></button>
            </div>
            <div class="offcanvas-body">
                <div class="d-flex gap-2 mb-4">
                    <a href="{{ url_for('login.change_password') }}" class="btn btn-outline-secondary flex-fill">
                        <i class="fas fa-key me-2" style="color: #FFD700;"></i>Modifier passe
                    </a>
                    <a href="{{ url_for('login.logout') }}" class="btn btn-outline-secondary flex-fill">
                        <i class="fas fa-sign-out-alt me-2" style="color: #DC143C;"></i>Déconnexion
                    </a>
                </div>
                <form id="settingsForm" action="{{ url_for('settings') }}" method="POST">
                    <div class="mb-3 floating-label">
                        <input type="text" class="form-control" name="nom_clinique" id="nom_clinique" value="{{ config.nom_clinique or '' }}" placeholder=" ">
                        <label for="nom_clinique">Nom de la clinique</label>
                    </div>
                    <div class="mb-3 floating-label">
                        <input type="text" class="form-control" name="cabinet" id="cabinet" value="{{ config.cabinet or '' }}" placeholder=" ">
                        <label for="cabinet">Cabinet</label>
                    </div>
                    <div class="mb-3 floating-label">
                        <input type="text" class="form-control" name="centre_medecin" id="centre_medecin" value="{{ config.centre_medical or '' }}" placeholder=" ">
                        <label for="centre_medecin">Centre médical</label>
                    </div>
                    <div class="mb-3 floating-label">
                        <input type="text" class="form-control" name="nom_medecin" id="nom_medecin" value="{{ config.doctor_name or '' }}" placeholder=" ">
                        <label for="nom_medecin">Nom du médecin</label>
                    </div>
                    <div class="mb-3 floating-label">
                        <input type="text" class="form-control" name="lieu" id="lieu" value="{{ config.location or '' }}" placeholder=" ">
                        <label for="lieu">Lieu</label>
                    </div>
                    <div class="mb-3 floating-label">
                        <select class="form-select" name="theme" id="theme_select" placeholder=" ">
                            {% for t in theme_names %}<option value="{{ t }}" {% if config.theme == t %}selected{% endif %}>{{ t.capitalize() }}</option>{% endfor %}
                        </select>
                        <label for="theme_select">Thème</label>
                    </div>
                    <button type="submit" class="btn btn-success w-100">
                        <i class="fas fa-save me-2"></i>Enregistrer
                    </button>
                </form>
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
                                <i class="fas fa-hospital me-2"></i>
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
                                <i class="fas fa-calendar-day me-2"></i>{{ current_date }}
                            </p>
                            <p class="mt-2 header-item">
                                <i class="fas fa-users me-2"></i>Gestion des Patients
                            </p>
                        </div>
                        <div class="card-body">
                            <ul class="nav nav-tabs justify-content-center" id="patientTab" role="tablist">
                                <li class="nav-item" role="presentation">
                                    <button class="nav-link active" id="liste-patients-tab"
                                            data-bs-toggle="tab" data-bs-target="#liste-patients"
                                            type="button" role="tab">
                                        <i class="fas fa-list me-2" style="color: #007BFF;"></i>Liste des Patients
                                    </button>
                                </li>
                                <li class="nav-item" role="presentation">
                                    <button class="nav-link" id="ajouter-patient-tab"
                                            data-bs-toggle="tab" data-bs-target="#ajouter-patient"
                                            type="button" role="tab">
                                        <i class="fas fa-user-plus me-2" style="color: #28A745;"></i>Ajouter Patient
                                    </button>
                                </li>
                            </ul>

                            <div class="tab-content mt-3" id="patientTabContent">
                                {# Tab Liste des Patients #}
                                <div class="tab-pane fade show active" id="liste-patients" role="tabpanel">
                                    <h4 class="text-primary mb-3">Liste Complète des Patients</h4>
                                    <div class="d-flex justify-content-center mb-3"> {# MODIFIÉ ICI: justify-content-center #}
                                        <button class="btn btn-info" onclick="generateAllBadges()">
                                            <i class="fas fa-file-pdf me-2"></i>Générer Tous les Badges
                                        </button>
                                    </div>
                                    <div class="table-responsive">
                                        <table class="table table-striped table-hover" id="patientsTable">
                                            <thead>
                                                <tr>
                                                    <th>ID</th>
                                                    <th>Nom</th>
                                                    <th>Prénom</th>
                                                    <th>Date Naissance</th>
                                                    <th>Sexe</th>
                                                    <th>Âge</th>
                                                    <th>Antécédents</th>
                                                    <th>Téléphone</th>
                                                    <th>Email</th>
                                                    <th>Actions</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {# Les données seront remplies par DataTables via JavaScript #}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>

                                {# Tab Ajouter Patient #}
                                <div class="tab-pane fade" id="ajouter-patient" role="tabpanel">
                                    <h4 class="text-primary mb-3">Ajouter un nouveau patient</h4>
                                    <form id="addPatientForm" action="{{ url_for('gestion_patient.add_patient') }}" method="POST">
                                        <div class="row g-3">
                                            <div class="col-md-6 floating-label">
                                                <input type="text" class="form-control" id="patient_id_add" name="ID" required placeholder=" ">
                                                <label for="patient_id_add">ID Patient</label>
                                            </div>
                                            <div class="col-md-6 floating-label">
                                                <input type="text" class="form-control" id="nom_add" name="Nom" required placeholder=" ">
                                                <label for="nom_add">Nom</label>
                                            </div>
                                            <div class="col-md-6 floating-label">
                                                <input type="text" class="form-control" id="prenom_add" name="Prenom" required placeholder=" ">
                                                <label for="prenom_add">Prénom</label>
                                            </div>
                                            <div class="col-md-6 floating-label">
                                                <input type="date" class="form-control" id="datenaissance_add" name="DateNaissance" required placeholder=" ">
                                                <label for="datenaissance_add">Date de Naissance</label>
                                            </div>
                                            <div class="col-md-6 floating-label">
                                                <select class="form-select" id="sexe_add" name="Sexe" required placeholder=" ">
                                                    <option value="" disabled selected>Sélectionnez le sexe</option>
                                                    <option value="Masculin">Masculin</option>
                                                    <option value="Féminin">Féminin</option>
                                                    <option value="Autre">Autre</option>
                                                </select>
                                                <label for="sexe_add">Sexe</label>
                                            </div>
                                            <div class="col-md-6 floating-label">
                                                <input type="text" class="form-control" id="telephone_add" name="Téléphone" required placeholder=" ">
                                                <label for="telephone_add">Téléphone</label>
                                            </div>
                                            <div class="col-md-6 floating-label">
                                                <input type="email" class="form-control" id="email_add" name="Email" placeholder=" ">
                                                <label for="email_add">Email (optionnel)</label>
                                            </div>
                                            <div class="col-md-12 floating-label">
                                                <textarea class="form-control" id="antecedents_add" name="Antécédents" rows="3" placeholder=" "></textarea>
                                                <label for="antecedents_add">Antécédents Médicaux (optionnel)</label>
                                            </div>
                                            <div class="col-12 text-center">
                                                <button type="submit" class="btn btn-primary"><i class="fas fa-plus-circle me-2"></i>Ajouter Patient</button>
                                            </div>
                                        </div>
                                    </form>
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
                        <i class="fas fa-heartbeat me-1"></i>
                        SASTOUKA DIGITAL © 2025 • sastoukadigital@gmail.com tel +212652084735
                    </p>
                    <p class="small mb-0" style="color: white;">
                        Ouvrir l’application en réseau {{ host_address }}
                    </p>
                </div>
            </div>
        </footer>

        {# Modal Modifier Patient #}
        <div class="modal fade" id="editPatientModal" tabindex="-1" aria-labelledby="editPatientModalLabel" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="editPatientModalLabel">Modifier Patient</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <form id="editPatientForm" action="{{ url_for('gestion_patient.edit_patient') }}" method="POST">
                        <div class="modal-body">
                            <input type="hidden" id="original_ID" name="original_ID">
                            <div class="mb-3 floating-label">
                                <input type="text" class="form-control" id="patient_id_edit" name="ID" required placeholder=" ">
                                <label for="patient_id_edit">ID Patient</label>
                            </div>
                            <div class="mb-3 floating-label">
                                <input type="text" class="form-control" id="nom_edit" name="Nom" required placeholder=" ">
                                <label for="nom_edit">Nom</label>
                            </div>
                            <div class="mb-3 floating-label">
                                <input type="text" class="form-control" id="prenom_edit" name="Prenom" required placeholder=" ">
                                <label for="prenom_edit">Prénom</label>
                            </div>
                            <div class="mb-3 floating-label">
                                <input type="date" class="form-control" id="datenaissance_edit" name="DateNaissance" required placeholder=" ">
                                <label for="datenaissance_edit">Date de Naissance</label>
                            </div>
                            <div class="mb-3 floating-label">
                                <select class="form-select" id="sexe_edit" name="Sexe" required placeholder=" ">
                                    <option value="Masculin">Masculin</option>
                                    <option value="Féminin">Féminin</option>
                                    <option value="Autre">Autre</option>
                                </select>
                                <label for="sexe_edit">Sexe</label>
                            </div>
                            <div class="mb-3 floating-label">
                                <input type="text" class="form-control" id="telephone_edit" name="Téléphone" required placeholder=" ">
                                <label for="telephone_edit">Téléphone</label>
                            </div>
                            <div class="mb-3 floating-label">
                                <input type="email" class="form-control" id="email_edit" name="Email" placeholder=" ">
                                <label for="email_edit">Email (optionnel)</label>
                            </div>
                            <div class="mb-3 floating-label">
                                <textarea class="form-control" id="antecedents_edit" name="Antécédents" rows="3" placeholder=" "></textarea>
                                <label for="antecedents_edit">Antécédents Médicaux (optionnel)</label>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
                            <button type="submit" class="btn btn-primary">Enregistrer les modifications</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>

        <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <!-- Scripts pour DataTables et Responsive -->
        <script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.7/js/dataTables.bootstrap5.min.js"></script>
        <script src="https://cdn.datatables.net/responsive/2.5.0/js/dataTables.responsive.min.js"></script>
        <script src="https://cdn.datatables.net/responsive/2.5.0/js/responsive.bootstrap5.min.js"></script>
        <script>
            document.addEventListener('DOMContentLoaded', () => {
                // Initialisation des onglets Bootstrap
                const triggerTabList = [].slice.call(document.querySelectorAll('#patientTab button'));
                triggerTabList.forEach(function (triggerEl) {
                    const tabTrigger = new bootstrap.Tab(triggerEl);
                    triggerEl.addEventListener('click', function (event) {
                        event.preventDefault();
                        tabTrigger.show();
                    });
                });

                // Récupérer les messages flash passés par Flask
                const flashedMessages = {{ flashed_messages | tojson | safe }};
                let shouldRedirectToList = false;

                // Vérifier si un message de succès avec redirection vers la liste est présent
                for (const [category, message] of flashedMessages) {
                    if (category === "success_and_redirect_to_list") {
                        shouldRedirectToList = true;
                        break;
                    }
                }

                // Activer l'onglet approprié au chargement de la page
                if (shouldRedirectToList) {
                    // Si une action a réussi, activer l'onglet "Liste des Patients"
                    bootstrap.Tab.getOrCreateInstance(document.getElementById('liste-patients-tab')).show();
                    localStorage.setItem('activePatientTab', '#liste-patients'); // Mettre à jour localStorage
                } else {
                    // Sinon, utiliser l'onglet précédemment actif (si défini) ou l'onglet par défaut (liste-patients)
                    const activeTab = localStorage.getItem('activePatientTab');
                    if (activeTab) {
                        const triggerEl = document.querySelector(`#patientTab button[data-bs-target="${activeTab}"]`);
                        if (triggerEl) bootstrap.Tab.getOrCreateInstance(triggerEl).show();
                    } else {
                        // Par défaut, si rien n'est en localStorage et pas de redirection forcée, activez la liste
                        bootstrap.Tab.getOrCreateInstance(document.getElementById('liste-patients-tab')).show();
                    }
                }

                // Garder la logique pour enregistrer l'onglet sélectionné manuellement par l'utilisateur
                document.querySelectorAll('#patientTab button').forEach(function(tabEl) {
                    tabEl.addEventListener('shown.bs.tab', function(event) {
                        localStorage.setItem('activePatientTab', event.target.getAttribute('data-bs-target'));
                        if ($.fn.DataTable.isDataTable('#patientsTable')) {
                            // Tenter de recalculer les largeurs de colonnes après un petit délai
                            setTimeout(function() {
                                $('#patientsTable').DataTable().columns.adjust().responsive.recalc();
                            }, 300); // Augmenté le délai à 300ms
                        }
                    });
                });

                const patientsData = {{ patients | tojson | safe }};

                if ($.fn.DataTable.isDataTable('#patientsTable')) {
                    $('#patientsTable').DataTable().destroy();
                }
                $('#patientsTable').DataTable({
                    data: patientsData,
                    columns: [
                        { data: 'ID', title: 'ID' },
                        { data: 'Nom', title: 'Nom' },
                        { data: 'Prenom', title: 'Prénom' },
                        { data: 'DateNaissance', title: 'Date Naissance' },
                        { data: 'Sexe', title: 'Sexe' },
                        { data: 'Âge', title: 'Âge' },
                        { data: 'Antécédents', title: 'Antécédents' },
                        { data: 'Téléphone', title: 'Téléphone' },
                        { data: 'Email', title: 'Email' },
                        {
                            data: null,
                            title: 'Actions',
                            render: function (data, type, row) {
                                // Utiliser un conteneur div avec des classes flexbox pour une disposition cohérente
                                const editBtn = `<button class="btn btn-sm btn-warning edit-patient-btn"
                                                data-id="${row.ID}" data-nom="${row.Nom}" data-prenom="${row.Prenom}"
                                                data-datenaissance="${row.DateNaissance}" data-sexe="${row.Sexe}"
                                                data-antecedents="${row.Antécédents}" data-telephone="${row.Téléphone}"
                                                data-email="${row.Email}"
                                                title="Modifier"><i class="fas fa-edit"></i></button>`;
                                const deleteBtn = `<button class="btn btn-sm btn-danger delete-patient-btn"
                                                data-id="${row.ID}" title="Supprimer"><i class="fas fa-trash"></i></button>`;

                                const badgeLink = `<a href="/gestion_patient/generate_badge/${row.ID}"
                                                class="btn btn-sm btn-info" target="_blank" title="Générer Badge">
                                                <i class="fas fa-id-badge"></i></a>`;

                                const whatsappBtn = `<a href="#" class="btn btn-sm btn-success whatsapp-btn"
                                                    data-phone="${row.Téléphone}"
                                                    data-patient-nom="${row.Nom}"
                                                    data-patient-prenom="${row.Prenom}"
                                                    title="Envoyer message WhatsApp">
                                                    <i class="fab fa-whatsapp"></i></a>`;
                                const consultBtn = `<button class="btn btn-sm btn-primary consult-patient-btn"
                                                    data-patient-id="${row.ID}"
                                                    title="Nouvelle Consultation">
                                                    <i class="fas fa-stethoscope"></i></button>`;
                                return `
                                    <div class="d-flex flex-column gap-1">
                                        <div class="d-flex gap-1 justify-content-center">
                                            ${editBtn} ${deleteBtn}
                                        </div>
                                        <div class="d-flex gap-1 justify-content-center">
                                            ${badgeLink} ${whatsappBtn}
                                        </div>
                                        <div class="d-flex gap-1 justify-content-center">
                                            ${consultBtn}
                                        </div>
                                    </div>
                                `;
                            }
                        }
                    ],
                    "language": {
                        // CORRECTION ici : Utilisez url_for pour charger le fichier de traduction en local
                        "url": "{{ url_for('static', filename='i18n/fr-FR.json') }}"
                    },
                    "paging": true,
                    "searching": true,
                    "info": true,
                    "order": [[1, 'asc']],
                    "responsive": false // MODIFICATION: Désactivé l'extension Responsive
                });

                // CORRECTION ici : Ajout d'une vérification pour s'assurer que l'élément settingsForm existe
                const settingsForm = document.getElementById('settingsForm');
                if (settingsForm) {
                    settingsForm.addEventListener('submit', e => {
                        e.preventDefault();
                        fetch(e.target.action, { method: e.target.method, body: new FormData(e.target), credentials: 'same-origin' })
                            .then(r => { if (!r.ok) throw new Error('Échec réseau'); return r; })
                            .then(() => Swal.fire({ icon: 'success', title: 'Enregistré', text: 'Paramètres sauvegardés.' }).then(() => location.reload()))
                            .catch(err => Swal.fire({ icon: 'error', title: 'Erreur', text: err.message }));
                    });
                } else {
                    console.warn("L'élément avec l'ID 'settingsForm' n'a pas été trouvé. L'écouteur d'événements ne peut pas être attaché.");
                }

                document.querySelectorAll('.floating-label input, .floating-label select, .floating-label textarea').forEach(input => {
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

                $('#patientsTable tbody').on('click', '.edit-patient-btn', function() {
                    const patientId = $(this).data('id');
                    fetch(`/gestion_patient/get_patient_details/${patientId}`)
                        .then(response => response.json())
                        .then(data => {
                            if (data.ID) {
                                document.getElementById('original_ID').value = data.ID;
                                document.getElementById('patient_id_edit').value = data.ID;
                                document.getElementById('nom_edit').value = data.Nom;
                                document.getElementById('prenom_edit').value = data.Prenom;
                                document.getElementById('datenaissance_edit').value = data.DateNaissance;
                                document.getElementById('sexe_edit').value = data.Sexe;
                                document.getElementById('telephone_edit').value = data.Téléphone;
                                document.getElementById('antecedents_edit').value = data.Antécédents;
                                document.getElementById('email_edit').value = data.Email;

                                document.querySelectorAll('#editPatientModal .floating-label input, #editPatientModal .floating-label select, #editPatientModal .floating-label textarea').forEach(input => {
                                    if (input.value) {
                                        input.classList.add('not-placeholder-shown');
                                    } else {
                                        input.classList.remove('not-placeholder-shown');
                                    }
                                });

                                const editModal = new bootstrap.Modal(document.getElementById('editPatientModal'));
                                editModal.show();
                            } else {
                                Swal.fire('Erreur', 'Détails du patient introuvables.', 'error');
                            }
                        })
                        .catch(error => {
                            console.error('Erreur:', error);
                            Swal.fire('Erreur', 'Impossible de récupérer les détails du patient.', 'error');
                        });
                });

                document.getElementById('editPatientForm').addEventListener('submit', function(e) {
                    e.preventDefault();
                    const form = this;
                    const formData = new FormData(form);

                    fetch(form.action, {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => {
                        if (!response.ok) {
                            return response.text().then(text => { throw new Error(text); });
                        }
                        return response.text();
                    })
                    .then(() => {
                        Swal.fire('Modifié!', 'Le patient a été mis à jour.', 'success').then(() => {
                            location.reload(); // Recharger la page après modification
                        });
                    })
                    .catch(error => {
                        console.error('Erreur:', error);
                        Swal.fire('Erreur', error.message || 'Erreur lors de la modification du patient.', 'error');
                    });
                });


                $('#patientsTable tbody').on('click', '.delete-patient-btn', function() {
                    const patientId = $(this).data('id');
                    Swal.fire({
                        title: 'Êtes-vous sûr ?',
                        text: "Vous ne pourrez pas revenir en arrière !",
                        icon: 'warning',
                        showCancelButton: true,
                        confirmButtonColor: '#d33',
                        cancelButtonColor: '#3085d6',
                        confirmButtonText: 'Oui, supprimer !',
                        cancelButtonText: 'Annuler'
                    }).then((result) => {
                        if (result.isConfirmed) {
                            fetch(`/gestion_patient/delete_patient/${patientId}`, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/x-www-form-urlencoded',
                                },
                                body: `patient_id=${patientId}`
                            })
                            .then(response => {
                                if (!response.ok) throw new Error('Échec de la suppression');
                                return response.json();
                            })
                            .then(data => {
                                if (data.success) {
                                    Swal.fire('Supprimé !', 'Le patient a été supprimé.', 'success').then(() => location.reload()); // Recharger la page après suppression
                                } else {
                                    Swal.fire('Erreur !', data.message, 'error');
                                }
                            })
                            .catch(error => {
                                Swal.fire('Erreur !', error.message, 'error');
                            });
                        }
                    });
                });

                window.generateAllBadges = function() {
                    Swal.fire({
                        title: 'Générer tous les badges ?',
                        text: "Cela créera un seul fichier PDF contenant un badge pour chaque patient.",
                        icon: 'info',
                        showCancelButton: true,
                        confirmButtonColor: '#28a745',
                        cancelButtonColor: '#6c757d',
                        confirmButtonText: 'Oui, générer !',
                        cancelButtonText: 'Annuler'
                    }).then((result) => {
                        if (result.isConfirmed) {
                            window.location.href = "{{ url_for('gestion_patient.generate_all_badges') }}";
                        }
                    });
                };

                // NOUVEAU: Logique pour le bouton WhatsApp
                $('#patientsTable tbody').on('click', '.whatsapp-btn', function(e) {
                    e.preventDefault();
                    const phone = $(this).data('phone');
                    const patientNom = $(this).data('patientNom');
                    const patientPrenom = $(this).data('patientPrenom');

                    let message = `Bonjour ${patientPrenom} ${patientNom},\n\n`;
                    message += `Ceci est un message de votre clinique/Cabinet Médical (Nom Clinique ou Cabinet).\n\n`;
                    message += `(Personnalisez ce message ici)`;

                    const formattedPhone = phone.replace(/[^0-9]/g, ''); // Supprime les caractères non numériques
                    const whatsappLink = `https://wa.me/${formattedPhone}?text=${encodeURIComponent(message)}`;
                    window.open(whatsappLink, '_blank');
                });

                // NOUVEAU: Logique pour le bouton Consultation (envoi AJAX au lieu de redirection directe)
                $('#patientsTable tbody').on('click', '.consult-patient-btn', function(e) {
                    e.preventDefault();
                    const patientId = $(this).data('patientId');

                    Swal.fire({
                        title: 'Créer une consultation ?',
                        text: "Les données de ce patient seront utilisées pour une nouvelle consultation.",
                        icon: 'question',
                        showCancelButton: true,
                        confirmButtonColor: '#3085d6',
                        cancelButtonColor: '#6c757d',
                        confirmButtonText: 'Oui, créer',
                        cancelButtonText: 'Annuler'
                    }).then((result) => {
                        if (result.isConfirmed) {
                            fetch("{{ url_for('gestion_patient.transfer_to_consultation') }}", {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/x-www-form-urlencoded',
                                },
                                body: `patient_id=${patientId}`
                            })
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    Swal.fire({
                                        icon: 'success',
                                        title: 'Consultation créée !',
                                        text: data.message,
                                        timer: 2000,
                                        showConfirmButton: false
                                    }).then(() => {
                                        // Optionnel: rediriger vers la page de consultation
                                        // window.location.href = "{{ url_for('index') }}";
                                    });
                                } else {
                                    Swal.fire({
                                        icon: 'error',
                                        title: 'Erreur',
                                        text: data.message
                                    });
                                }
                            })
                            .catch(error => {
                                console.error('Erreur:', error);
                                Swal.fire({
                                    icon: 'error',
                                    title: 'Erreur réseau',
                                    text: 'Impossible de créer la consultation.'
                                });
                            });
                        }
                    });
                });
            });
        </script>
    </body>
    </html>
"""
