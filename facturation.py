import os
import uuid
from datetime import datetime, date, time
import json

import pandas as pd
import qrcode
from flask import (
    Blueprint, request, render_template_string, redirect, url_for,
    flash, send_file, current_app, jsonify, session
)
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from PIL import Image
import utils # Assumant que utils contient get_base_dir() ou un chemin direct vers excel_dir
import theme
from rdv import load_patients # This load_patients will now implicitly use dynamic paths from utils
from routes import LISTS_FILE
from utils import merge_with_background_pdf # Import added
import login # <--- ASSUREZ-VOUS QUE CET IMPORT EST PRÉSENT

# Crée un Blueprint pour la gestion de la facturation
facturation_bp = Blueprint('facturation', __name__, url_prefix='/facturation')

def _json_default(obj):
    """
    Rend les objets datetime/date/time sérialisables pour Jinja |tojson.
    • datetime → 'YYYY-MM-DD HH:MM:SS'
    • date     → 'YYYY-MM-DD'
    • time     → 'HH:MM'
    Tous les autres types non compatibles JSON sont convertis en str().
    """
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%MM:%S')
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, time):
        return obj.strftime('%H:%M')
    return str(obj)

def _to_json_safe(obj):
    """
    Rend les objets date/time sérialisables pour Flask|tojson.
    • datetime  → 'YYYY-MM-DD HH:MM:SS'
    • date      → 'YYYY-MM-DD'
    • time      → 'HH:MM'
    """
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%MM:%S')
    if isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')
    if isinstance(obj, time):
        return obj.strftime('%H:%M')
    raise TypeError(f"Type non sérialisable: {type(obj)}")

# --- Fonction d'aide pour la manipulation du fichier Excel Comptabilite.xlsx ---
def update_recettes_excel(data):
    """
    Met à jour la feuille 'Recettes' dans Comptabilite.xlsx.
    Crée le fichier et toutes les feuilles par défaut s'ils n'existent pas.
    'data' doit être un dictionnaire avec des clés correspondant aux colonnes Excel.
    """
    excel_dir = utils.EXCEL_FOLDER
    if excel_dir is None:
        flash("Erreur: Le répertoire Excel n'est pas défini. Veuillez vous connecter ou relancer l'application.", "danger")
        return False

    os.makedirs(excel_dir, exist_ok=True)

    excel_file_path = os.path.join(excel_dir, 'Comptabilite.xlsx')
    sheet_name_recettes = 'Recettes'

    # Définir les colonnes attendues pour chaque feuille (correspondant aux CSV originaux)
    recettes_columns = ['Date', 'Type_Acte', 'Patient_ID', 'Patient_Nom', 'Patient_Prenom', 'Montant', 'Mode_Paiement', 'Description', 'ID_Facture_Liee', 'Preuve_Paiement_Fichier'] # Ajout de Preuve_Paiement_Fichier
    depenses_columns = ["Date", "Categorie", "Description", "Montant", "Justificatif_Fichier"]
    salaires_columns = ["Mois_Annee", "Nom_Employe", "Prenom_Employe", "Salaire_Net", "Charges_Sociales", "Total_Brut", "Fiche_Paie_PDF"]
    tierspayants_columns = ["Date", "Assureur", "Patient_ID", "Patient_Nom", "Patient_Prenom", "Montant_Attendu", "Montant_Recu", "Date_Reglement", "ID_Facture_Liee", "Statut"]
    documentsfiscaux_columns = ["Date", "Type_Document", "Description", "Fichier_PDF"]

    all_sheets_data = {}

    if os.path.exists(excel_file_path):
        try:
            xls = pd.ExcelFile(excel_file_path)
            for sheet in xls.sheet_names:
                all_sheets_data[sheet] = pd.read_excel(xls, sheet_name=sheet)
        except Exception as e:
            flash(f"Erreur lors de la lecture du fichier Excel: {e}. Un nouveau fichier pourrait être créé.", "warning")
            all_sheets_data = {}
    else:
        flash(f"Le fichier Comptabilite.xlsx n'existe pas. Il sera créé à: {excel_file_path}", "info")

    # Assurer que toutes les feuilles nécessaires sont présentes et ont les bonnes colonnes
    if sheet_name_recettes not in all_sheets_data:
        all_sheets_data[sheet_name_recettes] = pd.DataFrame(columns=recettes_columns)
    else:
        for col in recettes_columns:
            if col not in all_sheets_data[sheet_name_recettes].columns:
                all_sheets_data[sheet_name_recettes][col] = None

    if 'Depenses' not in all_sheets_data:
        all_sheets_data['Depenses'] = pd.DataFrame(columns=depenses_columns)
    else:
        for col in depenses_columns:
            if col not in all_sheets_data['Depenses'].columns:
                all_sheets_data['Depenses'][col] = None

    if 'Salaires' not in all_sheets_data:
        all_sheets_data['Salaires'] = pd.DataFrame(columns=salaires_columns)
    else:
        for col in salaires_columns:
            if col not in all_sheets_data['Salaires'].columns:
                all_sheets_data['Salaires'][col] = None

    if 'Tiers Payants' not in all_sheets_data: # Note: 'TiersPayants' vs 'Tiers Payants'
        all_sheets_data['Tiers Payants'] = pd.DataFrame(columns=tierspayants_columns)
    else:
        for col in tierspayants_columns:
            if col not in all_sheets_data['Tiers Payants'].columns:
                all_sheets_data['Tiers Payants'][col] = None

    if 'Documents Fiscaux' not in all_sheets_data: # Note: 'DocumentsFiscaux' vs 'Documents Fiscaux'
        all_sheets_data['Documents Fiscaux'] = pd.DataFrame(columns=documentsfiscaux_columns)
    else:
        for col in documentsfiscaux_columns:
            if col not in all_sheets_data['Documents Fiscaux'].columns:
                all_sheets_data['Documents Fiscaux'][col] = None


    # Convertir les nouvelles données de recette en DataFrame
    # S'assurer que les clés de 'data' correspondent aux 'recettes_columns'
    new_recette_df = pd.DataFrame([data], columns=recettes_columns)

    # Ajouter les nouvelles données au DataFrame 'Recettes'
    updated_recettes_df = pd.concat([all_sheets_data[sheet_name_recettes], new_recette_df], ignore_index=True)
    all_sheets_data[sheet_name_recettes] = updated_recettes_df

    # Écrire toutes les DataFrames dans le fichier Excel
    try:
        with pd.ExcelWriter(excel_file_path, engine='openpyxl') as writer:
            for sheet, df in all_sheets_data.items():
                df.to_excel(writer, sheet_name=sheet, index=False)
        flash("Les données de recettes ont été mises à jour avec succès dans Comptabilite.xlsx", "success")
        return True
    except Exception as e:
        flash(f"Erreur lors de l'écriture dans le fichier Excel: {e}", "danger")
        return False


class PDFInvoice(FPDF):
    def __init__(self, app, numero, patient, phone, date_str, services, currency, vat, patient_id=None): # Ajout de patient_id
        super().__init__(orientation='P', unit='mm', format='A5')  # A5 pour la compacité
        self.app      = app
        self.numero   = numero
        self.patient  = patient
        self.phone    = phone
        self.date_str = date_str
        self.services = services
        self.currency = currency
        self.vat      = float(vat)
        self.patient_id = patient_id # Stocke l'ID du patient
        self.set_left_margin(20)
        self.set_right_margin(20)
        self.set_top_margin(17)
        self.set_auto_page_break(auto=False)
        self.add_page()

    def header(self):
        # Utiliser utils.background_file qui est mis à jour dynamiquement
        bg = getattr(self.app, 'background_path', None) or getattr(utils, 'background_file', None)
        if bg and not os.path.isabs(bg):
            # Assurez-vous que BACKGROUND_FOLDER est défini avant d'y accéder
            if utils.BACKGROUND_FOLDER:
                bg = os.path.join(utils.BACKGROUND_FOLDER, bg)
            else:
                print("AVERTISSEMENT: utils.BACKGROUND_FOLDER non défini. Impossible de charger l'image de fond.")
                bg = None # Empêcher les erreurs si le chemin n'est pas défini

        if bg and os.path.isfile(bg) and bg.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            try:
                self.image(bg, x=0, y=0, w=self.w, h=self.h)
            except Exception:
                pass
        self.set_font('Helvetica', 'B', 18)
        self.set_text_color(0, 0, 0)
        self.ln(15)
        self.cell(0, 8, 'Facture', align='C')
        self.ln(8)
        y_numero = self.get_y()
        self.set_font('Helvetica', '', 10)
        self.cell(0, 6, f"Numéro : {self.numero}", align='C')
        self.ln(4)
        self.cell(0, 6, f"Date : {self.date_str}", align='C')

        qr_data = f"Facture {self.numero} le {self.date_str}"
        qr_img = self._generate_qr(qr_data)
        tmp_qr = "temp_qr.png"
        qr_img.save(tmp_qr)
        self.image(tmp_qr, x=self.w - self.r_margin - 20, y=y_numero, w=20, h=20)
        os.remove(tmp_qr)
        self.ln(15)

    def footer(self):
        pass

    def _generate_qr(self, data):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return img.resize((100, 100), Image.Resampling.LANCZOS)

    def add_invoice_details(self):
        self.set_font('Helvetica', 'B', 12)
        lh = 8
        cw = 50
        details = [
            ('Patient', self.patient),
            ('Téléphone', self.phone),
            ('Date facture', self.date_str),
            ('Taux TVA', f"{self.vat}%")
        ]
        # Ajout de l'ID Patient si disponible
        if self.patient_id:
            details.insert(1, ('ID Patient', self.patient_id)) # Insère après 'Patient'

        for label, val in details:
            self.cell(cw, lh, f"{label}:", ln=0)
            self.set_font('Helvetica', '', 12)
            self.cell(0, lh, str(val), ln=1)
            self.set_font('Helvetica', 'B', 12)
        self.ln(5)

    def add_invoice_table(self):
        # Dimensions
        table_width = self.w - self.l_margin - self.r_margin
        w_service   = table_width * 0.7
        w_price     = table_width * 0.3

        # === En-tête stylisé ===
        self.set_fill_color(50, 115, 220)        # bleu fort
        self.set_text_color(255, 255, 255)       # texte blanc
        self.set_font('Helvetica', 'B', 12)
        self.cell(w_service, 10, 'SERVICE', border=1, align='C', fill=True)
        self.cell(w_price,   10, f'PRIX ({self.currency})', border=1, align='C', fill=True)
        self.ln()

        # Préparation du corps
        line_height = self.font_size * 1.5
        total_ht    = 0.0
        fill        = False

        # Couleurs pour l'alternance
        color_light = (245, 245, 245)
        color_dark  = (255, 255, 255)

        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', '', 11)

        for svc in self.services:
            # Nettoyage du texte
            name  = svc['name']
            price = f"{svc['price']:.2f}"

            # Choisir l'arrière-plan de la ligne
            self.set_fill_color(*(color_light if fill else color_dark))

            # Calculer la hauteur de la cellule en fonction du texte
            lines = self.multi_cell(w_service, line_height, name,
                                    border=0, align='L', split_only=True)
            cell_h = len(lines) * line_height

            x0, y0 = self.get_x(), self.get_y()

            # Colonne Service (multi-cellule)
            self.multi_cell(w_service, line_height, name,
                            border=1, align='L', fill=True)

            # Colonne Prix, repositionnée
            self.set_xy(x0 + w_service, y0)
            self.cell(w_price, cell_h, price,
                      border=1, align='R', fill=True)

            # Passer à la ligne suivante
            self.ln(cell_h)
            total_ht += svc['price']
            fill = not fill

        # === Ligne de séparation avant les totaux ===
        self.set_draw_color(50, 115, 220)
        self.set_line_width(0.5)
        y = self.get_y() + 2
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(6)

        # Totaux en gras
        tva_amount = total_ht * (self.vat / 100)
        total_ttc  = total_ht + tva_amount

        self.set_font('Helvetica', 'B', 12)
        labels = [('Sous-total HT', total_ht),
                  (f'TVA {self.vat:.0f}%',    tva_amount),
                  ('TOTAL TTC', total_ttc)]
        for label, amt in labels:
            self.cell(w_service, 8, label, border=1, align='R')
            self.cell(w_price,   8, f"{amt:.2f}", border=1, align='R')
            self.ln()

class PDFReceipt(FPDF):
    def __init__(self, app, payment_data, invoice_details, config, receipt_number): # Ajout de receipt_number
        super().__init__(orientation='P', unit='mm', format='A5')
        self.app = app
        self.payment_data = payment_data
        self.invoice_details = invoice_details
        self.config = config
        self.receipt_number = receipt_number # Stocke le numéro de reçu
        self.set_left_margin(20)
        self.set_right_margin(20)
        self.set_top_margin(17)
        self.set_auto_page_break(auto=False)
        self.add_page()

    def header(self):
        # Utiliser utils.background_file qui est mis à jour dynamiquement
        bg = getattr(self.app, 'background_path', None) or getattr(utils, 'background_file', None)
        if bg and not os.path.isabs(bg):
            # Assurez-vous que BACKGROUND_FOLDER est défini avant d'y accéder
            if utils.BACKGROUND_FOLDER:
                bg = os.path.join(utils.BACKGROUND_FOLDER, bg)
            else:
                bg = None # Empêcher les erreurs si le chemin n'est pas défini

        if bg and os.path.isfile(bg) and bg.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            try:
                self.image(bg, x=0, y=0, w=self.w, h=self.h)
            except Exception:
                pass

        self.set_font('Helvetica', 'B', 18)
        self.set_text_color(0, 0, 0)
        self.ln(15)
        self.cell(0, 8, 'REÇU DE PAIEMENT', align='C') # Titre pour le reçu
        self.ln(8)
        y_numero = self.get_y()
        self.set_font('Helvetica', '', 10)
        self.cell(0, 6, f"Numéro Reçu : {self.receipt_number}", align='C') # Numéro de reçu
        self.ln(4)
        # Utiliser la date de paiement de payment_data
        payment_date_str = self.payment_data.get('Date', 'N/A')
        self.cell(0, 6, f"Date Paiement : {payment_date_str}", align='C')
        
        # QR code pour le reçu
        qr_data = f"Reçu {self.receipt_number} - Montant {self.payment_data.get('Montant', 0):.2f} {self.config.get('currency', 'EUR')}"
        qr_img = self._generate_qr(qr_data)
        tmp_qr = "temp_qr_receipt.png" # Utiliser un nom de fichier temporaire différent
        qr_img.save(tmp_qr)
        self.image(tmp_qr, x=self.w - self.r_margin - 20, y=y_numero, w=20, h=20)
        os.remove(tmp_qr)
        self.ln(15)

    def _generate_qr(self, data):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return img.resize((100, 100), Image.Resampling.LANCZOS)

    def add_receipt_details(self):
        self.set_font('Helvetica', 'B', 12)
        lh = 8
        cw = 50

        self.cell(0, lh, 'Détails du Paiement:', ln=1)
        self.set_font('Helvetica', '', 12)
        self.cell(cw, lh, "Date du Paiement:", ln=0)
        self.cell(0, lh, str(self.payment_data.get('Date', '')), ln=1)
        self.cell(cw, lh, "Montant Payé:", ln=0)
        self.cell(0, lh, f"{float(self.payment_data.get('Montant', 0)):.2f} {self.config.get('currency', 'EUR')}", ln=1)
        self.cell(cw, lh, "Mode de Paiement:", ln=0)
        self.cell(0, lh, str(self.payment_data.get('Mode_Paiement', '')), ln=1)

        self.set_font('Helvetica', 'B', 12)
        self.cell(0, lh, 'Informations Patient:', ln=1)
        self.set_font('Helvetica', '', 12)
        self.cell(cw, lh, "ID Patient:", ln=0)
        self.cell(0, lh, str(self.payment_data.get('Patient_ID', '')), ln=1)
        self.cell(cw, lh, "Nom Complet:", ln=0)
        self.cell(0, lh, f"{self.payment_data.get('Patient_Nom', '')} {self.payment_data.get('Patient_Prenom', '')}", ln=1)
        self.ln(5)

        if self.invoice_details and self.invoice_details.get('Numero'):
            self.set_font('Helvetica', 'B', 12)
            self.cell(0, lh, 'Facture Liée:', ln=1)
            self.set_font('Helvetica', '', 12)
            self.cell(cw, lh, "Numéro de Facture:", ln=0)
            self.cell(0, lh, str(self.invoice_details.get('Numero', '')), ln=1)
            self.cell(cw, lh, "Date Facture:", ln=0)
            self.cell(0, lh, str(self.invoice_details.get('Date', '')), ln=1)
            self.cell(cw, lh, "Montant Total Facture:", ln=0)
            self.cell(0, lh, f"{float(self.invoice_details.get('Total', 0)):.2f} {self.config.get('currency', 'EUR')}", ln=1)
            self.ln(5)


# --- Nouvelle Route pour récupérer les détails de la facture ---
@facturation_bp.route('/get_invoice_details/<invoice_number>', methods=['GET'])
def get_invoice_details(invoice_number):
    factures_df = load_invoices_df() # Charge le DataFrame des factures
    invoice_details = {}
    if not factures_df.empty:
        invoice = factures_df[factures_df['Numero'] == invoice_number]
        if not invoice.empty:
            invoice_data = invoice.iloc[0].to_dict()
            # Convertir les types non sérialisables en string
            for key, value in invoice_data.items():
                if isinstance(value, (datetime, date, time)):
                    invoice_data[key] = _json_default(value)
                elif pd.isna(value): # Gérer les NaN de pandas
                    invoice_data[key] = None

            # Split patient name
            patient_full_name = invoice_data.get('Patient', '')
            # Try to get Patient_ID from the invoice data first
            patient_id_from_invoice = invoice_data.get('Patient_ID', '')
            # If Patient_ID is not directly in invoice, try to find it from patients_info
            if not patient_id_from_invoice and patient_full_name:
                # Load patients info to find ID
                info_path = os.path.join(utils.EXCEL_FOLDER, 'info_Base_patient.xlsx')
                if os.path.exists(info_path):
                    df_pat = pd.read_excel(info_path, dtype=str)
                    matching_patient = df_pat[
                        (df_pat['Nom'] + ' ' + df_pat['Prenom']).str.strip() == patient_full_name.strip()
                    ]
                    if not matching_patient.empty:
                        patient_id_from_invoice = matching_patient.iloc[0].get('ID', '')

            name_parts = patient_full_name.split(' ', 1)
            patient_nom = name_parts[0] if name_parts else ''
            patient_prenom = name_parts[1] if len(name_parts) > 1 else ''

            # Determine Type_Acte based on services
            services_str = invoice_data.get('Services', '')
            services_list = [s.strip().split('(')[0] for s in services_str.split(';') if s.strip()]
            calculated_type_acte = 'Paiement' # Default fallback
            if len(services_list) == 1:
                calculated_type_acte = services_list[0]
            elif len(services_list) > 1:
                calculated_type_acte = 'Divers'


            invoice_details = {
                'Numero': invoice_data.get('Numero'),
                'Patient': patient_full_name,
                'Patient_ID': patient_id_from_invoice, # Utilise l'ID trouvé
                'Patient_Nom': patient_nom, # Ajout de Patient_Nom
                'Patient_Prenom': patient_prenom, # Ajout de Patient_Prenom
                'Telephone': invoice_data.get('Téléphone'),
                'Date': invoice_data.get('Date'),
                'Services': services_str,
                'Sous_total': invoice_data.get('Sous-total'),
                'TVA': invoice_data.get('TVA'),
                'Total': invoice_data.get('Total'),
                'Statut_Paiement': invoice_data.get('Statut_Paiement'),
                'Calculated_Type_Acte': calculated_type_acte # Nouveau champ pour le type d'acte calculé
            }
    return jsonify(invoice_details)


# --- Nouvelle Route pour enregistrer les paiements ---
@facturation_bp.route('/record_payment', methods=['GET', 'POST'])
def record_payment():
    if request.method == 'POST':
        try:
            payment_date = request.form['payment_date']
            amount = float(request.form['amount'])
            payment_method = request.form['payment_method']
            invoice_number = request.form.get('invoice_number', '').strip() # Nouveau champ
            patient_id = request.form.get('patient_id', '').strip()
            patient_nom = request.form.get('patient_nom', '').strip()
            patient_prenom = request.form.get('patient_prenom', '').strip()
            type_acte = request.form.get('type_acte', 'Paiement').strip() # Valeur par défaut 'Paiement'
            payment_status = request.form.get('payment_status', '') # "Payé" si coché

            # Construire la description automatiquement
            description = "Paiement manuel"
            invoice_details_for_receipt = {}
            if invoice_number:
                factures_df = load_invoices_df()
                invoice_info = factures_df[factures_df['Numero'] == invoice_number]
                if not invoice_info.empty:
                    invoice_data = invoice_info.iloc[0].to_dict()
                    invoice_patient_name = invoice_data.get('Patient', '')
                    description = f"Paiement Facture #{invoice_number} - Patient {invoice_patient_name}"
                    # Prepare invoice details for receipt
                    invoice_details_for_receipt = {
                        'Numero': invoice_data.get('Numero'),
                        'Date': invoice_data.get('Date'),
                        'Total': invoice_data.get('Total')
                    }
                else:
                    description = f"Paiement Facture #{invoice_number} (facture non trouvée)"


            attachment_filename = "" # Initialiser à vide
            if 'payment_attachment' in request.files:
                uploaded_file = request.files['payment_attachment']
                if uploaded_file.filename != '':
                    if utils.EXCEL_FOLDER is None:
                        flash("Erreur: Le répertoire Excel n'est pas défini.", "danger")
                        return redirect(url_for('facturation.record_payment', tab='paiements'))

                    # Chemin vers le sous-dossier 'Preuves'
                    proofs_dir = os.path.join(utils.EXCEL_FOLDER, 'Preuves')
                    os.makedirs(proofs_dir, exist_ok=True)

                    # Utiliser un nom de fichier unique pour éviter les conflits
                    attachment_filename = f"{uuid.uuid4()}_{uploaded_file.filename}"
                    full_attachment_path = os.path.join(proofs_dir, attachment_filename)
                    uploaded_file.save(full_attachment_path)
                    flash(f"Preuve de paiement enregistrée: {attachment_filename}", "info")


            payment_data = {
                "Date": payment_date,
                "Type_Acte": type_acte,
                "Patient_ID": patient_id,
                "Patient_Nom": patient_nom,
                "Patient_Prenom": patient_prenom,
                "Montant": amount,
                "Mode_Paiement": payment_method,
                "Description": description, # Utilise la description générée
                "ID_Facture_Liee": invoice_number if invoice_number else '',
                "Preuve_Paiement_Fichier": attachment_filename # Enregistre le nom du fichier de preuve
            }

            if update_recettes_excel(payment_data):
                flash("Paiement enregistré avec succès!", "success")
                receipt_filename = None

                # Mise à jour du statut de la facture dans factures.xlsx si liée
                if invoice_number and payment_status == 'Payé': # Only update if checkbox is checked
                    factures_path = os.path.join(utils.EXCEL_FOLDER, 'factures.xlsx')
                    if os.path.exists(factures_path):
                        df_fact = pd.read_excel(factures_path, dtype={'Numero': str})
                        # Trouver la facture par son numéro
                        idx = df_fact[df_fact['Numero'] == invoice_number].index
                        if not idx.empty:
                            df_fact.loc[idx, 'Statut_Paiement'] = 'Payée'
                            df_fact.to_excel(factures_path, index=False)
                            flash(f"Statut de la facture '{invoice_number}' mis à jour à 'Payée'.", "info")

                        else:
                            flash(f"Facture '{invoice_number}' non trouvée dans factures.xlsx pour la mise à jour du statut.", "warning")
                    else:
                        flash("Le fichier factures.xlsx n'existe pas. Impossible de mettre à jour le statut de la facture.", "warning")

                return redirect(url_for('facturation.home_facturation', tab='paiements'))
            else:
                flash("Échec de l'enregistrement du paiement.", "danger")
                return redirect(url_for('facturation.home_facturation', tab='paiements')) # Always redirect to show message
        except ValueError:
            flash("Montant invalide. Veuillez entrer un nombre.", "danger")
            return redirect(url_for('facturation.home_facturation', tab='paiements'))
        except Exception as e:
            # Catch all other exceptions and flash them
            current_app.logger.error(f"Error in record_payment: {e}", exc_info=True) # Log full traceback
            flash(f"Une erreur inattendue est survenue lors de l'enregistrement: {e}", "danger")
            return redirect(url_for('facturation.home_facturation', tab='paiements'))

    # Rendre le formulaire pour les requêtes GET ou en cas d'échec du POST
    from datetime import date
    # Récupérer les factures pour la datalist et la dernière facture pour pré-remplir
    all_invoices = load_invoices()
    last_invoice_info = {}
    if all_invoices:
        last_invoice = all_invoices[0] # La dernière facture est la première car elles sont triées par date descendante
        last_invoice_info['Numero'] = last_invoice.get('Numero', '')
        last_invoice_info['Patient'] = last_invoice.get('Patient', '')
        last_invoice_info['Total'] = last_invoice.get('Total', 0.0)
        
        # Try to get Patient_ID, Nom and Prenom from the last invoice
        last_invoice_info['Patient_ID'] = last_invoice.get('Patient_ID', '')
        patient_full_name = last_invoice.get('Patient', '')
        name_parts = patient_full_name.split(' ', 1) # Split only on the first space
        last_invoice_info['Patient_Nom'] = name_parts[0] if name_parts else ''
        last_invoice_info['Patient_Prenom'] = name_parts[1] if len(name_parts) > 1 else ''

        # Determine Calculated_Type_Acte for the last invoice
        services_str = last_invoice.get('Services', '')
        services_list = [s.strip().split('(')[0] for s in services_str.split(';') if s.strip()]
        calculated_type_acte = 'Paiement' # Default fallback
        if len(services_list) == 1:
            calculated_type_acte = services_list[0]
        elif len(services_list) > 1:
            calculated_type_acte = 'Divers'
        last_invoice_info['Calculated_Type_Acte'] = calculated_type_acte


    return render_template_string(facturation_template,
                                  today=date.today().isoformat(),
                                  last_invoice_info=last_invoice_info,
                                  factures=all_invoices, # Passer toutes les factures pour la datalist
                                  config=utils.load_config(), # Assurez-vous que config est passé
                                  theme_vars=theme.current_theme(),
                                  theme_names=list(theme.THEMES.keys()),
                                  services_by_category={}, # Ces éléments ne sont pas nécessaires pour cette route seule
                                  patients_info=[], # Ces éléments ne sont pas nécessaires pour cette route seule
                                  last_patient={}, # Ces éléments ne sont pas nécessaires pour cette route seule
                                  numero_default="", # Ces éléments ne sont pas nécessaires pour cette route seule
                                  vat_default=utils.load_config().get('vat', 20.0),
                                  currency=utils.load_config().get('currency', 'EUR'),
                                  background_files=[],
                                  report_summary={}
                                )

# --- Nouvelle Route pour générer le reçu à la demande ---
@facturation_bp.route('/generate_receipt/<invoice_number>', methods=['GET'])
def generate_receipt(invoice_number):
    if utils.EXCEL_FOLDER is None or utils.PDF_FOLDER is None:
        return jsonify(success=False, error="Erreur: Les chemins de dossier ne sont pas définis. Veuillez vous connecter."), 500

    excel_file_path = os.path.join(utils.EXCEL_FOLDER, 'Comptabilite.xlsx')
    sheet_name_recettes = 'Recettes'
    payment_data = None

    if os.path.exists(excel_file_path):
        try:
            df_recettes = pd.read_excel(excel_file_path, sheet_name=sheet_name_recettes, dtype={'ID_Facture_Liee': str}).fillna("")
            # Trouver le premier paiement lié à ce numéro de facture
            matching_payments = df_recettes[df_recettes['ID_Facture_Liee'] == invoice_number]
            if not matching_payments.empty:
                payment_data = matching_payments.iloc[0].to_dict()
                # Assurez-vous que la date est dans un format affichable, si c'est un objet datetime
                if isinstance(payment_data.get('Date'), (datetime, date)):
                    payment_data['Date'] = payment_data['Date'].strftime('%Y-%m-%d')
            else:
                return jsonify(success=False, error=f"Aucun paiement trouvé pour la facture {invoice_number}."), 404
        except Exception as e:
            return jsonify(success=False, error=f"Erreur lors de la lecture des paiements: {e}"), 500
    else:
        return jsonify(success=False, error="Fichier Comptabilite.xlsx introuvable."), 404

    # Récupérer les détails de la facture pour le contexte dans le reçu
    invoice_details_response = get_invoice_details(invoice_number)
    invoice_details = json.loads(invoice_details_response.get_data(as_text=True))

    if not payment_data:
        return jsonify(success=False, error=f"Aucun paiement trouvé pour la facture {invoice_number}."), 404

    config = utils.load_config()
    
    # Générer un numéro de reçu unique basé sur le numéro de facture
    receipt_num = f"REC-{invoice_number}"

    receipt_pdf = PDFReceipt(
        app=current_app,
        payment_data=payment_data,
        invoice_details=invoice_details,
        config=config,
        receipt_number=receipt_num # Passer le numéro de reçu
    )
    receipt_pdf.add_receipt_details() # Cette méthode existe déjà et remplit les détails
    
    receipt_filename = f"Recu_Paiement_{invoice_number}.pdf" # Nom de fichier cohérent
    receipt_output_path = os.path.join(utils.PDF_FOLDER, receipt_filename)
    receipt_pdf.output(receipt_output_path)
    
    merge_with_background_pdf(receipt_output_path) # Appliquer l'arrière-plan

    return send_file(
        receipt_output_path,
        as_attachment=True,
        download_name=receipt_filename,
        mimetype='application/pdf'
    )


@facturation_bp.route('/new_patient', methods=['GET', 'POST'])
def new_patient():
    # Ensure utils.EXCEL_FOLDER is defined before use
    if utils.EXCEL_FOLDER is None:
        return "Erreur: Les chemins de dossier ne sont pas définis. Veuillez vous connecter.", 500

    excel_path = os.path.join(utils.EXCEL_FOLDER, 'info_Base_patient.xlsx')

    # Ensure patient file exists
    if not os.path.exists(excel_path):
        os.makedirs(utils.EXCEL_FOLDER, exist_ok=True)
        # Required columns for listing patients
        df_empty = pd.DataFrame(columns=['ID', 'Nom', 'Prenom', 'Téléphone'])
        df_empty.to_excel(excel_path, index=False)

    if request.method == 'POST':
        id_     = request.form.get('ID')
        nom     = request.form.get('Nom')
        prenom  = request.form.get('Prenom')
        tel     = request.form.get('Téléphone', '')
        if not (id_ and nom and prenom):
            flash('Veuillez remplir ID, Nom et Prénom', 'danger')
            return redirect(url_for('facturation.new_patient'))
        df = pd.read_excel(excel_path)
        df = pd.concat([df, pd.DataFrame([{'ID': id_, 'Nom': nom, 'Prenom': prenom, 'Téléphone': tel}])], ignore_index=True)
        df.to_excel(excel_path, index=False)
        flash('Patient ajouté ✔', 'success')
        return redirect(url_for('facturation.home_facturation'))
    return render_template_string(new_patient_template)

@facturation_bp.route('/download/<path:filename>')
def download_invoice(filename):
    """
    Serves the requested PDF file if present in utils.PDF_FOLDER,
    otherwise returns 404/flash.
    """
    # Ensure utils.PDF_FOLDER is defined before use
    if utils.PDF_FOLDER == None:
        return jsonify(success=False, error="Erreur: Les chemins de dossier ne sont pas définis. Veuillez vous connecter."), 500
    file_path = os.path.join(utils.PDF_FOLDER, filename)
    if not os.path.isfile(file_path):
        return jsonify(success=False, error="Fichier introuvable !"), 404

    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# Nouvelle route pour télécharger la preuve de paiement
@facturation_bp.route('/download_payment_proof/<filename>')
def download_payment_proof(filename):
    """
    Sert le fichier de preuve de paiement demandé depuis le dossier 'Preuves'.
    """
    if utils.EXCEL_FOLDER is None:
        return jsonify(success=False, error="Erreur: Le répertoire Excel n'est pas défini."), 500
    
    proofs_folder = os.path.join(utils.EXCEL_FOLDER, 'Preuves')
    file_path = os.path.join(proofs_folder, filename)
    
    if not os.path.isfile(file_path):
        return jsonify(success=False, error="Preuve de paiement introuvable !"), 404
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/octet-stream' # Type MIME générique pour divers types de fichiers
    )


@facturation_bp.route('/delete/<invoice_number>', methods=['DELETE'])
def delete_invoice(invoice_number):
    """
    Deletes an invoice entry from 'factures.xlsx' and its corresponding PDF file.
    Also deletes associated payment data from 'Comptabilite.xlsx'.
    """
    # Ensure utils.EXCEL_FOLDER and utils.PDF_FOLDER are defined before use
    if utils.EXCEL_FOLDER is None or utils.PDF_FOLDER is None:
        return jsonify(success=False, error="Les chemins de dossier ne sont pas définis."), 500

    factures_path = os.path.join(utils.EXCEL_FOLDER, 'factures.xlsx')
    comptabilite_path = os.path.join(utils.EXCEL_FOLDER, 'Comptabilite.xlsx')
    pdf_file_name = f"Facture_{invoice_number}.pdf"
    pdf_path = os.path.join(utils.PDF_FOLDER, pdf_file_name)
    receipt_pdf_file_name = f"Recu_Paiement_{invoice_number}.pdf"
    receipt_pdf_path = os.path.join(utils.PDF_FOLDER, receipt_pdf_file_name)

    proofs_folder = os.path.join(utils.EXCEL_FOLDER, 'Preuves')


    try:
        # Delete from factures.xlsx
        if os.path.exists(factures_path):
            df = pd.read_excel(factures_path, dtype={'Numero': str})
            df_filtered = df[df['Numero'] != invoice_number]
            if len(df_filtered) < len(df):
                df_filtered.to_excel(factures_path, index=False)
            else:
                return jsonify(success=False, error="Facture non trouvée dans l'Excel."), 404
        else:
            return jsonify(success=False, error="Fichier Excel des factures introuvable."), 404

        # Delete associated data from Comptabilite.xlsx (Recettes sheet)
        if os.path.exists(comptabilite_path):
            xls = pd.ExcelFile(comptabilite_path)
            all_sheets_data = {sheet: pd.read_excel(xls, sheet_name=sheet) for sheet in xls.sheet_names}
            
            sheet_name_recettes = 'Recettes'
            if sheet_name_recettes in all_sheets_data:
                df_recettes = all_sheets_data[sheet_name_recettes]
                # Ensure 'ID_Facture_Liee' column exists and is string type for comparison
                if 'ID_Facture_Liee' in df_recettes.columns:
                    # Get the proof filename before filtering
                    proof_filename_to_delete = df_recettes[df_recettes['ID_Facture_Liee'] == invoice_number]['Preuve_Paiement_Fichier'].iloc[0] if 'Preuve_Paiement_Fichier' in df_recettes.columns and not df_recettes[df_recettes['ID_Facture_Liee'] == invoice_number].empty else None

                    df_recettes['ID_Facture_Liee'] = df_recettes['ID_Facture_Liee'].astype(str)
                    df_recettes_filtered = df_recettes[df_recettes['ID_Facture_Liee'] != invoice_number]
                    all_sheets_data[sheet_name_recettes] = df_recettes_filtered
                    
                    with pd.ExcelWriter(comptabilite_path, engine='openpyxl') as writer:
                        for sheet, df in all_sheets_data.items():
                            df.to_excel(writer, sheet_name=sheet, index=False)
                    
                    # Delete the actual proof file if it exists
                    if proof_filename_to_delete and os.path.exists(os.path.join(proofs_folder, proof_filename_to_delete)):
                        os.remove(os.path.join(proofs_folder, proof_filename_to_delete))
                        print(f"Fichier de preuve de paiement supprimé: {proof_filename_to_delete}")

                else:
                    print(f"AVERTISSEMENT: La colonne 'ID_Facture_Liee' n'existe pas dans la feuille '{sheet_name_recettes}'.")
            else:
                print(f"AVERTISSEMENT: La feuille '{sheet_name_recettes}' n'existe pas dans Comptabilite.xlsx.")
        else:
            print(f"AVERTISSEMENT: Fichier Comptabilite.xlsx introuvable pour la suppression des paiements liés.")


        # Delete PDF files
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        else:
            print(f"Fichier PDF non trouvé pour la suppression: {pdf_path}")
        
        if os.path.exists(receipt_pdf_path):
            os.remove(receipt_pdf_path)
        else:
            print(f"Fichier PDF de reçu non trouvé pour la suppression: {receipt_pdf_path}")


        return jsonify(success=True), 200

    except Exception as e:
        print(f"Erreur lors de la suppression de la facture {invoice_number}: {e}")
        return jsonify(success=False, error=str(e)), 500


@facturation_bp.route('/', methods=['GET', 'POST'])
def home_facturation():
    # utils.set_dynamic_base_dir is called in app.before_request,
    # so utils.EXCEL_FOLDER and utils.PDF_FOLDER should be available here.

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

    # ---------- 0. Context, themes & BG ----------------------------------
    config      = utils.load_config()
    theme_vars  = theme.current_theme()

    # Assurez-vous que utils.BACKGROUND_FOLDER est défini avant de l'utiliser
    bg_folder = utils.BACKGROUND_FOLDER if utils.BACKGROUND_FOLDER else ""
    background_files = []
    if os.path.exists(bg_folder):
        background_files = [
            f for f in os.listdir(bg_folder)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.pdf'))
        ]
    current_app.background_path = config.get('background_file_path')

    # ---------- 1. Available services/acts ---------------------------
    # LISTS_FILE est statique, donc son chemin n'est pas affecté
    df_lists = pd.read_excel(LISTS_FILE, sheet_name=1)
    cols     = list(df_lists.columns)
    services_by_category = {}
    for cat in ['Consultation', 'Analyses', 'Radiologies', 'Autre_Acte']:
        match = next((c for c in cols if c.strip().lower() == cat.lower()), None)
        if not match:
            match = next((c for c in cols if cat.lower() in c.strip().lower()), None)
        services_by_category[cat] = (
            df_lists[match].dropna().astype(str).tolist() if match else []
        )

    # ---------- 2. Patient database ------------------------------------------
    # Utilise utils.EXCEL_FOLDER qui est maintenant dynamique
    info_path = os.path.join(utils.EXCEL_FOLDER, 'info_Base_patient.xlsx')
    # Initialize last_patient outside the if-else block
    patients_info = []
    last_patient  = {}

    if os.path.exists(info_path):
        df_pat        = pd.read_excel(info_path, dtype=str)
        patients_info = df_pat.to_dict(orient='records')
        last_patient  = df_pat.iloc[-1].to_dict() if not df_pat.empty else {}


    # ---------- 3. POST : invoice creation (Now handles AJAX) --------------------------------
    if request.method == 'POST':
        try:
            # 3-A. Background
            sel_bg = request.form.get('background', config.get('background_file_path'))
            if sel_bg:
                if not os.path.isabs(sel_bg):
                    # Assurez-vous que utils.BACKGROUND_FOLDER est défini
                    if utils.BACKGROUND_FOLDER:
                        sel_bg = os.path.join(utils.BACKGROUND_FOLDER, sel_bg)
                    else:
                        print("AVERTISSEMENT: utils.BACKGROUND_FOLDER non défini. Impossible de définir l'arrière-plan.")
                        sel_bg = None
                current_app.background_path   = sel_bg
                if sel_bg: # Only update config if sel_bg is valid
                    config['background_file_path'] = os.path.basename(sel_bg)
                    utils.save_config(config)

            # 3-B. VAT
            vat_value = request.form.get('vat')
            if not vat_value:
                return jsonify(success=False, error='Le taux de TVA est requis'), 400
            try:
                vat_float = float(vat_value)
                if not 0 <= vat_float <= 100:
                    raise ValueError
                if config.get('vat') != vat_float:
                    config['vat'] = vat_float
                    utils.save_config(config)
                    # flash(f'Taux TVA mis à jour à {vat_float} %', 'success') # Flash not used for AJAX
            except ValueError:
                return jsonify(success=False, error='Le taux de TVA doit être un nombre entre 0 et 100'), 400

            # 3-C. Patient info
            pid  = request.form.get('patient_id')

            # MODIFICATION ICI: Valider si l'ID patient existe dans patients_info
            # patients_info est déjà chargé globalement par home_facturation
            patient_exists = any(str(p['ID']) == pid for p in patients_info)

            if not patient_exists:
                # MESSAGE D'ERREUR MIS À JOUR
                return jsonify(success=False, error=f"L'ID patient '{pid}' est introuvable. Veuillez vérifier l'ID saisi ou ajouter le patient à la base de données avant de générer la facture."), 400

            # Si le patient existe, trouver ses informations complètes
            rec  = next((p for p in patients_info if str(p['ID']) == pid), {})
            
            if not rec:
                 return jsonify(success=False, error=f"Erreur interne: Impossible de récupérer les détails pour l'ID patient '{pid}'."), 500

            patient_name = f"{rec.get('Nom','')} {rec.get('Prenom','')}".strip()
            phone        = rec.get('Téléphone', '')

            # 3-D. Invoice number
            date_str = request.form.get('date')
            date_key = date_str.replace('-', '')

            # Utilise utils.PDF_FOLDER qui est maintenant dynamique
            existing = []
            if utils.PDF_FOLDER and os.path.exists(utils.PDF_FOLDER): # Added check for utils.PDF_FOLDER existence
                existing = [
                    fn for fn in os.listdir(utils.PDF_FOLDER)
                    if fn.startswith(f"Facture_{date_key}")
                ]
            numero = f"{date_key}-{len(existing)+1:03d}"

            # 3-E. Selected services (Now parsed from JSON string)
            services_raw = request.form.get('services_json') # Expecting a JSON string of services
            if services_raw:
                services = json.loads(services_raw)
            else:
                services = []

            if not services:
                return jsonify(success=False, error='Veuillez sélectionner au moins un service'), 400

            # 3-F. Totals
            total_ht   = sum(s['price'] for s in services)
            tva_amount = total_ht * (config.get('vat', 20) / 100)
            total_ttc  = total_ht + tva_amount

            # 3-G. Currency
            selected_currency   = request.form.get('currency', config.get('currency', 'EUR'))
            config['currency']  = selected_currency
            utils.save_config(config)

            # 3-H. PDF Creation
            pdf = PDFInvoice(
                app      = current_app,
                numero   = numero,
                patient  = patient_name,
                phone    = phone,
                date_str = date_str,
                services = services,
                currency = selected_currency,
                vat       = config.get('vat', 20),
                patient_id = pid # Passe l'ID du patient au PDF
            )
            pdf.add_invoice_details()
            pdf.add_invoice_table()

            # Utilise utils.PDF_FOLDER qui est maintenant dynamique
            output_file_name = f"Facture_{numero}.pdf"
            output_path = os.path.join(utils.PDF_FOLDER, output_file_name)
            pdf.output(output_path)

            # 3-I. Background merge
            merge_with_background_pdf(output_path)

            # 3-J. Excel Save
            # Utilise utils.EXCEL_FOLDER qui est maintenant dynamique
            factures_path = os.path.join(utils.EXCEL_FOLDER, 'factures.xlsx')
            if os.path.exists(factures_path):
                df_fact = pd.read_excel(factures_path, dtype={'Numero': str})
            else:
                df_fact = pd.DataFrame(columns=[
                    'Numero', 'Patient', 'Téléphone', 'Date',
                    'Services', 'Sous-total', 'TVA', 'Total', 'Statut_Paiement', 'Patient_ID', 'PDF_Filename' # Ajout de Statut_Paiement, Patient_ID et PDF_Filename
                ])
            df_fact = pd.concat([
                df_fact,
                pd.DataFrame([{
                    'Numero'    : numero,
                    'Patient'   : patient_name,
                    'Téléphone' : phone,
                    'Date'      : date_str,
                    'Services'  : "; ".join(f"{s['name']}({s['price']:.2f})" for s in services),
                    'Sous-total': total_ht,
                    'TVA'       : tva_amount,
                    'Total'     : total_ttc,
                    'Statut_Paiement': 'Impayée', # Nouvelle facture par défaut impayée
                    'Patient_ID': pid, # Enregistre l'ID du patient dans factures.xlsx
                    'PDF_Filename': output_file_name # Enregistre le nom du fichier PDF
                }])
            ], ignore_index=True)
            df_fact.to_excel(factures_path, index=False)

            # Prepare the invoice details to send back to the client
            response_invoice_details = {
                'Numero': numero,
                'Patient': patient_name,
                'Patient_ID': pid,
                'Patient_Nom': patient_name.split(' ', 1)[0] if patient_name.split(' ', 1) else '',
                'Patient_Prenom': patient_name.split(' ', 1)[1] if len(patient_name.split(' ', 1)) > 1 else '',
                'Total': total_ttc,
                'Date': date_str,
                # Calculate Type_Acte based on services for the payment tab
                'Calculated_Type_Acte': 'Paiement' if len(services) == 1 and services[0]['name'].lower() == 'paiement'
                                        else (services[0]['name'] if len(services) == 1 else 'Divers'),
                'pdf_filename': output_file_name
            }

            # flash('Facture générée et enregistrée ✔', 'success') # Flash not used for AJAX
            return jsonify(success=True, invoice=response_invoice_details, message="Facture générée et enregistrée ✔")

        except Exception as e:
            current_app.logger.error(f"Erreur lors de la génération de la facture: {e}", exc_info=True)
            # flash(f"Erreur lors de la génération de la facture: {e}", "danger") # Flash not used for AJAX
            return jsonify(success=False, error=str(e)), 500

    # ---------- 4. GET variables (default form) -------------------------
    from datetime import date # ensure date is imported
    today_iso         = date.today().isoformat()
    date_key          = today_iso.replace('-', '')

    # Utilise utils.PDF_FOLDER qui est maintenant dynamique
    existing_pdf      = []
    if utils.PDF_FOLDER and os.path.exists(utils.PDF_FOLDER): # Added check for utils.PDF_FOLDER existence
        existing_pdf = [
            fn for fn in os.listdir(utils.PDF_FOLDER)
            if fn.startswith(f"Facture_{date_key}")
        ]
    numero_default    = f"{date_key}-{len(existing_pdf)+1:03d}"
    vat_default       = config.get('vat', 20.0)
    selected_currency = config.get('currency', 'EUR')

    # ---------- 5. JSON-safe data for template ---------------------
    factures        = load_invoices() # load_invoices utilise utils.EXCEL_FOLDER/factures.xlsx
    report_summary  = generate_report_summary() # utilise load_invoices

    services_json       = json.loads(json.dumps(services_by_category, default=_json_default))
    patients_json       = json.loads(json.dumps(patients_info,       default=_json_default))
    factures_json       = json.loads(json.dumps(factures,            default=_json_default))
    report_summary_json = json.loads(json.dumps(report_summary,      default=_json_default))

    # Récupérer les informations de la dernière facture pour l'onglet de paiement
    last_invoice_info = {}
    if factures:
        # La dernière facture est la première car load_invoices trie par date descendante
        last_invoice = factures[0]
        last_invoice_info['Numero'] = last_invoice.get('Numero', '')
        last_invoice_info['Patient'] = last_invoice.get('Patient', '')
        last_invoice_info['Total'] = last_invoice.get('Total', 0.0)
        # Tente de récupérer Patient_ID, Nom et Prénom de la dernière facture
        last_invoice_info['Patient_ID'] = last_invoice.get('Patient_ID', '')
        patient_full_name = last_invoice.get('Patient', '')
        name_parts = patient_full_name.split(' ', 1) # Split only on the first space
        last_invoice_info['Patient_Nom'] = name_parts[0] if name_parts else ''
        last_invoice_info['Patient_Prenom'] = name_parts[1] if len(name_parts) > 1 else ''

        # Determine Calculated_Type_Acte for the last invoice
        services_str = last_invoice.get('Services', '')
        services_list = [s.strip().split('(')[0] for s in services_str.split(';') if s.strip()]
        calculated_type_acte = 'Paiement' # Default fallback
        if len(services_list) == 1:
            calculated_type_acte = services_list[0]
        elif len(services_list) > 1:
            calculated_type_acte = 'Divers'
        last_invoice_info['Calculated_Type_Acte'] = calculated_type_acte


    # ---------- Display message if no invoice ---------------------
    if not factures_json:
        flash("Aucune donnée de facturation disponible.", "warning")

    # ---------- 6. Render ---------------------------------------------------
    return render_template_string(
        facturation_template,
        config               = config,
        theme_vars           = theme_vars,
        theme_names          = list(theme.THEMES.keys()),
        services_by_category = services_json,
        patients_info        = patients_json,
        last_patient         = last_patient,
        today                = today_iso,
        numero_default       = numero_default,
        vat_default          = vat_default,
        currency             = selected_currency,
        background_files     = background_files,
        factures             = factures_json,
        report_summary       = report_summary_json,
        last_invoice_info    = last_invoice_info, # Passer les infos de la dernière facture
        # --- PASSER LA NOUVELLE VARIABLE AU TEMPLATE ---
        logged_in_doctor_name=logged_in_full_name # Utilise le même nom de variable que dans main_template pour cohérence
        # --- FIN DU PASSAGE ---
    )

@facturation_bp.route('/add_service', methods=['POST'])
def add_service():
    # LISTS_FILE est statique, donc son chemin n'est pas affecté
    data = request.get_json() or {}
    cat = data.get('category', '').strip()
    name = data.get('name', '').strip()
    price = data.get('price', '').strip()
    if not (cat and name and price):
        return jsonify(success=False, error="Données incomplètes"), 400
    xls = pd.read_excel(LISTS_FILE, sheet_name=None)
    sheet_name = list(xls.keys())[1]
    df = xls[sheet_name]
    col = next((c for c in df.columns if c.strip().lower() == cat.lower()), None)
    if col is None:
        col = cat
        df[col] = pd.NA
    df.loc[len(df), col] = f"{name}|{price}"
    with pd.ExcelWriter(LISTS_FILE, engine='openpyxl') as writer:
        for sname, sheet_df in xls.items():
            if sname == sheet_name:
                sheet_df = df
            sheet_df.to_excel(writer, sheet_name=sname, index=False)
    return jsonify(success=True)

@facturation_bp.route('/report')
def report():
    start = request.args.get('start') or None
    end   = request.args.get('end')   or None
    summary = generate_report_summary(start, end)
    count = summary['count']
    summary['average'] = summary['total_ttc'] / count if count else 0.0
    return jsonify(summary)

# Nouvelle route pour récupérer les données des factures en JSON
@facturation_bp.route('/get_invoices_data', methods=['GET'])
def get_invoices_data():
    """
    Returns invoice data as JSON for AJAX requests.
    """
    invoices = load_invoices()
    return jsonify(invoices)

def load_invoices():
    """
    Loads the 'factures.xlsx' workbook and returns a list of dictionaries
    ready for display.
    Also merges with 'Comptabilite.xlsx' to get 'Preuve_Paiement_Fichier'.

    • Forces the 'Numero' column to remain a **string** (dtype={'Numero': str})
      to avoid any str + int concatenation in the template.
    • Formats the 'Date' column to DD/MM/YYYY format.
    • Returns records sorted by invoice number (Numero) in descending order,
      assuming Numero in JacquelineMMDD-XXX format guarantees recency.
    """
    if utils.EXCEL_FOLDER is None:
        print("ERREUR: utils.EXCEL_FOLDER est None dans load_invoices.")
        return []

    factures_path = os.path.join(utils.EXCEL_FOLDER, 'factures.xlsx')
    comptabilite_path = os.path.join(utils.EXCEL_FOLDER, 'Comptabilite.xlsx')

    df_fact = pd.DataFrame()
    if os.path.exists(factures_path):
        df_fact = pd.read_excel(factures_path, dtype={'Numero': str}).fillna("")
        if 'Date' in df_fact.columns:
            df_fact['Date'] = pd.to_datetime(df_fact['Date'], errors='coerce').dt.strftime('%Y-%m-%d') # Format date for consistency
        if 'PDF_Filename' not in df_fact.columns:
            df_fact['PDF_Filename'] = df_fact['Numero'].apply(lambda x: f"Facture_{x}.pdf")
    
    df_recettes = pd.DataFrame()
    if os.path.exists(comptabilite_path):
        try:
            df_recettes = pd.read_excel(comptabilite_path, sheet_name='Recettes', dtype={'ID_Facture_Liee': str}).fillna("")
            # Sélectionner uniquement les colonnes nécessaires de df_recettes
            df_recettes = df_recettes[['ID_Facture_Liee', 'Preuve_Paiement_Fichier']]
            # Renommer 'ID_Facture_Liee' pour la fusion
            df_recettes = df_recettes.rename(columns={'ID_Facture_Liee': 'Numero'})
        except Exception as e:
            print(f"AVERTISSEMENT: Erreur lors du chargement de la feuille 'Recettes' de Comptabilite.xlsx: {e}")
            df_recettes = pd.DataFrame(columns=['Numero', 'Preuve_Paiement_Fichier']) # Créer un DataFrame vide avec les colonnes attendues

    # Fusionner les DataFrames
    if not df_fact.empty and not df_recettes.empty:
        df_merged = pd.merge(df_fact, df_recettes, on='Numero', how='left', suffixes=('_fact', '_rec')).fillna("")
    else:
        df_merged = df_fact # Si df_recettes est vide, utiliser df_fact tel quel

    # S'assurer que 'Preuve_Paiement_Fichier' est toujours présente, même si vide
    if 'Preuve_Paiement_Fichier' not in df_merged.columns:
        df_merged['Preuve_Paiement_Fichier'] = ""

    # Tri par Numero (descendant).
    return df_merged.sort_values(by='Numero', ascending=False, na_position='last') \
             .to_dict('records')

def load_invoices_df():
    """
    Loads the 'factures.xlsx' workbook and returns a DataFrame.
    Used internally for operations where DataFrame is preferred.
    """
    if utils.EXCEL_FOLDER is None:
        print("ERREUR: utils.EXCEL_FOLDER est None dans load_invoices_df.")
        return pd.DataFrame() # Retourne un DataFrame vide

    factures_path = os.path.join(utils.EXCEL_FOLDER, 'factures.xlsx')
    if os.path.exists(factures_path):
        # Assurez-vous que 'Numero' est de type string lors du chargement
        df = pd.read_excel(factures_path, dtype={'Numero': str}).fillna("")
        return df
    return pd.DataFrame()

def generate_report_summary(start=None, end=None):
    factures = load_invoices()
    config = utils.load_config() # S'assurer que la config est chargée pour la devise
    currency = config.get('currency', 'EUR')
    if not factures:
        return {
            'count': 0,
            'total_ht': 0.0,
            'total_tva': 0.0,
            'total_ttc': 0.0,
            'currency': currency
        }
    df = pd.DataFrame(factures)
    df['Date_dt'] = pd.to_datetime(df['Date'], format='%Y-%m-%d') # Changer le format pour correspondre à load_invoices
    if start:
        df = df[df['Date_dt'] >= pd.to_datetime(start)]
    if end:
        df = df[df['Date_dt'] <= pd.to_datetime(end)]
    count = len(df)
    total_ht  = df['Sous-total'].sum()
    total_tva = df['TVA'].sum()
    total_ttc = df['Total'].sum()
    return {
        'count': int(count),
        'total_ht': float(total_ht),
        'total_tva': float(total_tva),
        'total_ttc': float(total_ttc),
        'currency': currency
    }

def load_services():
    # LISTS_FILE est statique, donc son chemin n'est pas affecté
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), LISTS_FILE)
    if not os.path.exists(path):
        return []

    df = pd.read_excel(path, dtype=str)
    df = df.fillna("")
    return df.to_dict("records")

# ---------------------------------------------------------------------------
# --------------------------- TEMPLATE PRINCIPAL ----------------------------
# ---------------------------------------------------------------------------
facturation_template = r"""
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
  <meta name="mobile-web-app-capable" content="yes"> {# Added for PWA compatibility #}
  <title>Facturation – {{ config.nom_clinique or 'EasyMedicaLink' }}</title>

  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&family=Great+Vibes&display=swap" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
  {% include '_floating_assistant.html' %} 

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
      filter: {% if session.theme == 'dark' %}invert(1){% else %}none{% endif %};
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
    .btn-info { /* Bouton WhatsApp */
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

    /* DataTables */
    #invoiceTable_wrapper .dataTables_filter input,
    #invoiceTable_wrapper .dataTables_length select {
      border-radius: var(--border-radius-sm);
      border: 1px solid var(--secondary-color);
      padding: 0.5rem 0.75rem;
      background-color: var(--card-bg);
      color: var(--text-color);
    }
    #invoiceTable_wrapper .dataTables_filter input:focus,
    #invoiceTable_wrapper .dataTables_length select:focus {
      border-color: var(--primary-color);
      box-shadow: 0 0 0 0.25rem rgba(var(--primary-color-rgb), 0.25);
    }
    /* Masquer la flèche déroulante pour la sélection de la longueur de DataTables */
    #invoiceTable_wrapper .dataTables_length select {
      -webkit-appearance: none;
      -moz-appearance: none;
      appearance: none;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath fill='none' stroke='%23333' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M2 5l6 6 6-6'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: right 0.75rem center;
      background-size: 0.65em auto;
      padding-right: 2rem;
    }
    body.dark-theme #invoiceTable_wrapper .dataTables_length select {
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath fill='none' stroke='%23fff' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M2 5l6 6 6-6'/%3E%3C/svg%3E");
    }

    #invoiceTable_wrapper .dataTables_paginate .pagination .page-item .page-link {
      border-radius: var(--border-radius-sm);
      margin: 0 0.2rem;
      background-color: var(--card-bg);
      color: var(--text-color);
      border: 1px solid var(--secondary-color);
    }
    #invoiceTable_wrapper .dataTables_paginate .pagination .page-item.active .page-link {
      background: var(--gradient-main);
      border-color: var(--primary-color);
      color: var(--button-text);
    }
    #invoiceTable_wrapper .dataTables_paginate .pagination .page-item .page-link:hover {
      background-color: rgba(var(--primary-color-rgb), 0.1);
      color: var(--primary-color);
    }
    .table {
      --bs-table-bg: var(--card-bg);
      --bs-table-color: var(--text-color);
      --bs-table-striped-bg: var(--table-striped-bg);
      --bs-table-striped-color: var(--text-color);
      --bs-table-border-color: var(--border-color);
    }
    .table thead th {
      background-color: var(--primary-color);
      color: var(--button-text);
      border-color: var(--primary-color);
    }
    .table tbody tr {
      transition: background-color 0.2s ease;
    }
    .table tbody tr:hover {
      background-color: rgba(var(--primary-color-rgb), 0.05) !important;
    }

    /* Messages flash */
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
      /* animation: fadeInOut 5s forwards; */ /* Temporarily removed for debugging */
      opacity: 1; /* Ensure it's always visible for debugging */
    }

    @keyframes fadeInOut {
      0% { opacity: 0; transform: translateX(-50%) translateY(-20px); }
      10% { opacity: 1; transform: translateX(-50%) translateY(0); }
      90% { opacity: 1; transform: translateX(-50%) translateY(0); }
      100% { opacity: 0; transform: translateX(-50%) translateY(-20px); }
    }

    /* Pied de page */
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

    /* Onglets de navigation */
    .nav-tabs .nav-link {
      border: none;
      color: var(--text-color-light); /* Ajusté pour le thème */
      font-weight: 500;
      font-size: 1.1rem; /* Ajusté pour la cohérence */
      transition: all 0.2s ease;
      position: relative;
      padding: 0.75rem 1.25rem; /* Rembourrage ajusté */
    }
    .nav-tabs .nav-link i { font-size: 1.2rem; margin-right: 0.5rem; } /* Taille d'icône ajustée */
    .nav-tabs .nav-link::after {
      content: '';
      position: absolute;
      bottom: 0; left: 0;
      width: 0; height: 3px;
      background: var(--primary-color);
      transition: width 0.3s ease;
    }
    .nav-tabs .nav-link.active {
      background: transparent;
      color: var(--primary-color)!important;
    }
    .nav-tabs .nav-link.active::after { width: 100%; }

    /* Cartes de service */
    .service-card {
      border-radius: var(--border-radius-md);
      box-shadow: var(--shadow-light);
      background: var(--card-bg) !important;
      color: var(--text-color) !important;
      border: 1px solid var(--border-color); /* Utiliser la couleur de bordure du thème */
      transition: all 0.2s ease;
      cursor: pointer;
    }
    .service-card:hover {
      transform: translateY(-3px); /* Léger soulèvement au survol */
      box-shadow: var(--shadow-medium);
    }
    .service-card.active {
      background: var(--gradient-main) !important; /* Utiliser le dégradé pour l'état actif */
      color: var(--button-text) !important;
      border-color: var(--primary-color);
      box-shadow: var(--shadow-medium);
    }
    .service-card i {
      font-size: 2rem !important; /* Taille d'icône ajustée */
      margin-bottom: 0.25rem; /* Marge réduite */
    }
    .service-card .small {
      font-size: 0.85rem; /* Taille de texte ajustée */
      font-weight: 600;
    }

    /* Ajustements responsifs */
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
        font-size: 0.9rem;
        padding: 0.5rem 0.75rem;
      }
      .nav-tabs .nav-link i {
        font-size: 1rem;
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
      <i class="fas fa-home me-2"></i> {# Icône Accueil (couleur originale) #}
      <i class="fas fa-heartbeat me-2"></i>EasyMedicaLink {# Icône Battement de cœur (couleur originale) #}
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

<script>
  // Soumission AJAX paramètres
  const settingsForm = document.getElementById('settingsForm');
  if (settingsForm) {
    settingsForm.addEventListener('submit', e=>{
      e.preventDefault();
      fetch(e.target.action,{method:e.target.method,body:new FormData(e.target),credentials:'same-origin'})
        .then(r=>{ if(!r.ok) throw new Error('Échec réseau'); return r; })
        .then(()=>Swal.fire({icon:'success',title:'Enregistré',text:'Paramètres sauvegardés.'}).then(()=>location.reload()))
        .catch(err=>Swal.fire({icon:'error',title:'Erreur',text:err.message}));
    });
  } else {
      console.warn("L'élément avec l'ID 'settingsForm' n'a pas été trouvé. L'écouteur d'événements ne peut pas être attaché.");
  }
</script>
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
              <i class="fas fa-user me-2"></i><span>{{ logged_in_doctor_name if logged_in_doctor_name and logged_in_doctor_name != 'None' else config.doctor_name or 'NOM MEDECIN' }}</span> {# Simple User Icon #}
            </div>
            <div class="d-flex align-items-center header-item">
              <i class="fas fa-map-marker-alt me-2"></i><span>{{ config.location or 'LIEU' }}</span> {# Map Marker Icon (original color) #}
            </div>
          </div>
          <p class="mt-2 header-item">
            <i class="fas fa-calendar-day me-2"></i>{{ today }}
          </p>
          <p class="mt-2 header-item">
            <i class="fas fa-file-invoice-dollar me-2" style="color: #FFFFFF;"></i>Facturation {# Icône Facture Dollar Dorée #}
          </p>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="container-fluid my-4">
  <ul class="nav nav-tabs justify-content-center" id="factTab" role="tablist">
    <li class="nav-item" role="presentation">
      <button class="nav-link active" id="tab-facturation"
              data-bs-toggle="tab" data-bs-target="#facturation"
              type="button" role="tab">
        <i class="fas fa-file-invoice-dollar me-2" style="color: #FFD700;"></i>Facturation {# Icône Facture Dollar Dorée #}
      </button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="tab-paiements"
              data-bs-toggle="tab" data-bs-target="#paiements"
              type="button" role="tab">
        <i class="fas fa-money-check-alt me-2" style="color: #28A745;"></i>Enregistrer un Paiement {# Icône Chèque Monnaie Verte #}
      </button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="tab-rapports"
              data-bs-toggle="tab" data-bs-target="#rapports"
              type="button" role="tab">
        <i class="fas fa-chart-line me-2" style="color: #4CAF50;"></i>Rapport global {# Icône Ligne de Graphique Verte #}
      </button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="tab-historique"
              data-bs-toggle="tab" data-bs-target="#historique"
              type="button" role="tab">
        <i class="fas fa-history me-2" style="color: #FFC107;"></i>Paiements antérieurs {# Icône Historique Ambre #}
      </button>
    </li>
  </ul>

  <div class="tab-content mt-3" id="factTabContent">
    <div class="tab-pane fade show active" id="facturation" role="tabpanel">
      <div class="row justify-content-center">
        <div class="col-12">

          <div class="card mb-4">
            <div class="card-header text-center">
              <h5><i class="fas fa-user me-2" style="color: #007BFF;"></i>Dernier patient</h5> {# Icône Utilisateur Bleue #}
            </div>
            <div class="card-body">
              <p id="last_patient_id"><strong>ID :</strong> {{ last_patient.get('ID','') }}</p>
              <p id="last_patient_name"><strong>Nom :</strong> {{ last_patient.get('Nom','') }} {{ last_patient.get('Prenom','') }}</p>
              <p id="last_patient_phone"><strong>Téléphone :</strong> {{ last_patient.get('Téléphone','') }}</p>
              <a href="{{ url_for('facturation.new_patient') }}" class="btn btn-secondary">
                <i class="fas fa-user-plus me-1" style="color: #FFFFFF;"></i>Ajouter un nouveau patient {# Icône Utilisateur Plus Blanche #}
              </a>
            </div>
          </div>

          <div class="card">
            <div class="card-header text-center">
              <h5><i class="fas fa-file-invoice-dollar me-2" style="color: #FFD700;"></i>Générer une facture</h5> {# Icône Facture Dollar Dorée #}
            </div>
            <div class="card-body">
              <form method="post" id="invoiceForm">
                <div class="row gy-3">
                  <div class="col-md-4 floating-label">
                    <input type="text"
                          class="form-control"
                          value="{{ config.get('background_file_path') or 'Aucun arrière-plan' }}"
                          readonly
                          placeholder=" ">
                    <label><i class="fas fa-image me-2" style="color: #DA70D6;"></i>Arrière-plan</label> {# Icône Image Orchidée #}
                    <input type="hidden" name="background" value="{{ config.get('background_file_path') }}">
                  </div>

                  <div class="col-md-4 floating-label">
                    <input type="text" name="numero" class="form-control" value="{{ numero_default }}" readonly placeholder=" ">
                    <label><i class="fas fa-hashtag me-2" style="color: #6C757D;"></i>Numéro</label> {# Icône Hashtag Grise #}
                  </div>
                  <div class="col-md-4 floating-label">
                    <input type="date" name="date" class="form-control" value="{{ today }}" placeholder=" ">
                    <label><i class="fas fa-calendar-day me-2" style="color: #FFB6C1;"></i>Date</label> {# Icône Jour Calendrier Rose Clair #}
                  </div>
                  {% set currencies = [
                    ('EUR','Euro'),('USD','Dollar US'),
                    ('MAD','Dirham marocain'),('DZD','Dinar algérien'),
                    ('TND','Dinar tunisien'),('XOF','Franc CFA (BCEAO)'),
                    ('XAF','Franc CFA (BEAC)'),('CHF','Franc suisse'),
                    ('CAD','Dollar canadien'),('HTG','Gourde haïtienne'),
                    ('GNF','Franc guinéen')
                  ] %}
                  <div class="col-md-4 floating-label">
                    <input type="number"
                           id="vatInput"
                           name="vat"
                           class="form-control"
                           value="{{ vat_default }}"
                           step="0.01"
                           min="0"
                           max="100"
                           required
                           placeholder=" ">
                    <label><i class="fas fa-percent me-2" style="color: #DC143C;"></i>TVA (%)</label> {# Icône Pourcentage Cramoisie #}
                  </div>
                  <div class="col-md-4 floating-label">
                    <select name="currency" class="form-select" placeholder=" ">
                      {% for code, name in currencies %}
                        <option value="{{ code }}" {% if currency == code %}selected{% endif %}>
                          {{ name }} ({{ code }})
                        </option>
                      {% endfor %}
                    </select>
                    <label><i class="fas fa-money-bill-wave me-2" style="color: #28A745;"></i>Devise</label> {# Icône Vague Billet Vert #}
                  </div>
                  {# MODIFICATION ICI: Nouveau champ de saisie pour l'ID Patient #}
                  <div class="col-md-4 floating-label">
                    <input type="text" list="patientsDatalist" id="patientIdInputFacturation" name="patient_id" class="form-control"
                           value="{{ last_patient.ID if last_patient.ID else '' }}" required placeholder=" ">
                    <label for="patientIdInputFacturation"><i class="fas fa-user-injured me-2" style="color: #007BFF;"></i>ID Patient</label>
                    <datalist id="patientsDatalist">
                      {% for p in patients_info %}
                      <option value="{{ p.ID }}">{{ p.ID }} – {{ p.Nom }} {{ p.Prenom }}</option>
                      {% endfor %}
                    </datalist>
                  </div>
                </div>

                <div class="card mb-4 mt-4">
                  <div class="card-header"><h6><i class="fas fa-cubes me-2" style="color: #8A2BE2;"></i>Services</h6></div> {# Icône Cubes Bleu Violet #}
                  <div class="card-body">

                    <div class="row mb-3">
                      {% for cat in services_by_category.keys() %}
                      <div class="col-6 col-md-3 mb-2">
                        <div class="card service-card h-100 text-center" data-cat="{{ cat }}">
                          <div class="card-body p-2">
                            {% if cat.lower() == 'consultation' %}
                              <i class="fas fa-stethoscope mb-1" style="color: #20B2AA;"></i> {# Icône Stéthoscope Vert Mer Clair #}
                            {% elif cat.lower() == 'analyses' %}
                              <i class="fas fa-vial mb-1" style="color: #DA70D6;"></i> {# Icône Fiole Orchidée #}
                            {% elif cat.lower() == 'radiologies' %}
                              <i class="fas fa-x-ray mb-1" style="color: #8A2BE2;"></i> {# Icône Rayon X Bleu Violet #}
                            {% else %}
                              <i class="fas fa-briefcase-medical mb-1" style="color: #FF69B4;"></i> {# Icône Mallette Médicale Rose #}
                            {% endif %}
                            <div class="small text-uppercase">{{ cat }}</div>
                          </div>
                        </div>
                      </div>
                      {% endfor %}
                    </div>

                    <div class="d-flex gap-2 mb-3">
                      <div class="floating-label flex-grow-1">
                        <input list="serviceList" id="serviceSelect" class="form-control" placeholder=" ">
                        <label for="serviceSelect"><i class="fas fa-search me-2" style="color: #6C757D;"></i>Rechercher ou saisir un service…</label> {# Icône Recherche Grise #}
                      </div>
                      <div class="floating-label" style="width:100px">
                        <input type="number" id="servicePrice" class="form-control" placeholder=" " step="0.01">
                        <label for="servicePrice"><i class="fas fa-money-check-alt me-2" style="color: #28A745;"></i>Prix</label> {# Icône Chèque Monnaie Verte #}
                      </div>
                      <datalist id="serviceList"></datalist>
                      <button type="button" id="addServiceBtn" class="btn btn-primary">
                        <i class="fas fa-plus" style="color: #FFFFFF;"></i> {# Icône Plus Blanche #}
                      </button>
                    </div>

                    <div class="modal fade" id="catalogModal" tabindex="-1">
                      <div class="modal-dialog"><div class="modal-content">
                        <form id="catalogForm">
                          <div class="modal-header">
                            <h5 class="modal-title"><i class="fas fa-folder-plus me-2"></i>Ajouter un service au catalogue</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                          </div>
                          <div class="modal-body">
                            <div class="mb-3 floating-label">
                              <select id="catalogCategory" class="form-select" placeholder=" ">
                                {% for cat in services_by_category.keys() %}
                                <option value="{{ cat }}">{{ cat.capitalize() }}</option>
                                {% endfor %}
                              </select>
                              <label for="catalogCategory"><i class="fas fa-tags me-2" style="color: #6C757D;"></i>Catégorie</label> {# Icône Étiquettes Grises #}
                            </div>
                            <div class="mb-3 floating-label">
                              <input type="text" id="catalogName" class="form-control" required placeholder=" ">
                              <label for="catalogName"><i class="fas fa-file-alt me-2" style="color: #007BFF;"></i>Désignation</label> {# Icône Fichier Alt Bleu #}
                            </div>
                            <div class="mb-3 floating-label">
                              <input type="number" id="catalogPrice" class="form-control" step="0.01" required placeholder=" ">
                              <label for="catalogPrice"><i class="fas fa-money-check-alt me-2" style="color: #28A745;"></i>Prix</label> {# Icône Chèque Monnaie Verte #}
                            </div>
                          </div>
                          <div class="modal-footer">
                            <button type="submit" class="btn btn-primary"><i class="fas fa-save me-2"></i>Enregistrer</button> {# Icône Enregistrer Blanche #}
                          </div>
                        </form>
                      </div></div>
                    </div>

                    <div class="table-responsive mb-3">
                      <table class="table table-bordered" id="servicesTable">
                        <thead class="table-light">
                          <tr>
                            <th>Désignation</th>
                            <th style="width:120px">Prix ({{ currency }})</th>
                            <th style="width:50px"></th>
                          </tr>
                        </thead>
                        <tbody></tbody>
                      </table>
                    </div>
                    <div class="d-flex justify-content-end gap-4">
                      <div><strong>Sous-total HT :</strong> <span id="totalHT">0.00</span> {{ currency }}</div>
                      <div>
                        <strong>TVA (<span id="vatPercent">{{ vat_default }}</span>%) :</strong>
                        <span id="totalTVA">0.00</span> {{ currency }}
                      </div>
                      <div><strong>Total TTC :</strong> <span id="totalTTC">0.00</span> {{ currency }}</div>
                    </div>

                  </div>
                </div>
                <div class="text-center mt-4"> {# Changed from text-end to text-center #}
                  <button type="button" id="submitInvoiceBtn" class="btn btn-primary">
                    <i class="fas fa-receipt me-1" style="color: #FFFFFF;"></i>Générer la facture {# Icône Reçu Blanche #}
                  </button>
                </div>
              </form>
            </div>
          </div>

        </div>
      </div>
    </div>

<div class="tab-pane fade" id="paiements" role="tabpanel">
    <div class="row justify-content-center">
        <div class="col-12">
            <div class="card shadow-lg">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0"><i class="fas fa-money-check-alt me-2" style="color: #28A745;"></i>Enregistrer un nouveau Paiement</h5> {# Icône Chèque Monnaie Verte #}
                </div>
                <div class="card-body">
                    <form method="post" action="{{ url_for('facturation.record_payment') }}" enctype="multipart/form-data">
                        <div class="mb-3 floating-label">
                            <input type="date" name="payment_date" class="form-control" value="{{ today }}" required placeholder=" ">
                            <label for="payment_date"><i class="fas fa-calendar-alt me-2" style="color: #FFB6C1;"></i>Date du Paiement</label> {# Icône Calendrier Alt Rose Clair #}
                        </div>
                        <div class="mb-3 floating-label">
                            <input list="invoiceNumbersList" name="invoice_number" id="invoiceNumberInput" class="form-control" placeholder="Numéro de facture (optionnel)" value="{{ last_invoice_info.Numero if last_invoice_info.Numero else '' }}">
                            <label for="invoiceNumberInput"><i class="fas fa-file-invoice me-2" style="color: #007BFF;"></i>Numéro de Facture</label> {# Icône Facture Bleue #}
                            <datalist id="invoiceNumbersList">
                                {% for inv in factures %}
                                <option value="{{ inv.Numero }}">{{ inv.Numero }} - {{ inv.Patient }} ({{ '%.2f'|format(inv.Total) }} {{ currency }}) - {{ inv.Statut_Paiement }}</option>
                                {% endfor %}
                            </datalist>
                        </div>

                        <!-- Nouvelle disposition pour les informations du patient -->
                        <div class="row gy-3 mb-3">
                            <div class="col-md-4 floating-label">
                                <input type="text" name="patient_id" id="patientIdInput" class="form-control" placeholder=" " value="{{ last_invoice_info.Patient_ID if last_invoice_info.Patient_ID else '' }}">
                                <label for="patientIdInput"><i class="fas fa-id-card me-2" style="color: #6C757D;"></i>ID Patient</label> {# Icône Carte d'Identité Grise #}
                            </div>
                            <div class="col-md-4 floating-label">
                                <input type="text" name="patient_nom" id="patientNomInput" class="form-control" placeholder=" " value="{{ last_invoice_info.Patient_Nom if last_invoice_info.Patient_Nom else '' }}">
                                <label for="patientNomInput"><i class="fas fa-user me-2" style="color: #007BFF;"></i>Nom Patient</label> {# Icône Utilisateur Bleue #}
                            </div>
                            <div class="col-md-4 floating-label">
                                <input type="text" name="patient_prenom" id="patientPrenomInput" class="form-control" placeholder=" " value="{{ last_invoice_info.Patient_Prenom if last_invoice_info.Patient_Prenom else '' }}">
                                <label for="patientPrenomInput"><i class="fas fa-user me-2" style="color: #007BFF;"></i>Prénom Patient</label> {# Icône Utilisateur Bleue #}
                            </div>
                        </div>

                        <!-- Nouvelle disposition pour les détails du paiement -->
                        <div class="row gy-3 mb-3">
                            <div class="col-md-4 floating-label">
                                <input type="text" name="type_acte" id="typeActeInput" class="form-control" placeholder="Ex: Consultation, Opération" value="{{ last_invoice_info.Calculated_Type_Acte if last_invoice_info.Calculated_Type_Acte else 'Paiement' }}" required>
                                <label for="typeActeInput"><i class="fas fa-notes-medical me-2" style="color: #FF69B4;"></i>Type d'Acte</label> {# Icône Notes Médicales Rose #}
                            </div>
                            <div class="col-md-4 floating-label">
                                <input type="number" name="amount" id="amountInput" class="form-control" step="0.01" value="{{ '%.2f'|format(last_invoice_info.Total) if last_invoice_info.Total else '' }}" required placeholder=" ">
                                <label for="amountInput"><i class="fas fa-money-bill-wave me-2" style="color: #28A745;"></i>Montant</label> {# Icône Vague Billet Vert #}
                            </div>
                            <div class="col-md-4 floating-label">
                                <select name="payment_method" class="form-select" required placeholder=" ">
                                    <option value="Espèces">Espèces</option>
                                    <option value="Chèque">Chèque</option>
                                    <option value="Virement Bancaire">Virement Bancaire</option>
                                    <option value="Carte Bancaire">Carte Bancaire</option>
                                    <option value="Autre">Autre</option>
                                </select>
                                <label for="payment_method"><i class="fas fa-wallet me-2" style="color: #FFD700;"></i>Mode de Paiement</label> {# Icône Portefeuille Dorée #}
                            </div>
                        </div>

                        <div class="mb-3 form-check">
                            <input type="checkbox" name="payment_status" id="payment_status" class="form-check-input" value="Payé" checked>
                            <label class="form-check-label" for="payment_status">Marquer comme Payé</label>
                        </div>
                        <div class="mb-3">
                            <label for="payment_attachment" class="form-label"><i class="fas fa-paperclip me-2" style="color: #6C757D;"></i>Joindre une preuve de paiement (optionnel)</label> {# Icône Trombone Grise #}
                            <input type="file" name="payment_attachment" id="payment_attachment" class="form-control" accept="image/*,.pdf">
                        </div>
                        <div class="d-flex justify-content-center gap-2 mt-4"> {# Changed from justify-content-end to justify-content-center #}
                            <button type="submit" class="btn btn-primary">
                                <i class="fas fa-save me-2" style="color: #FFFFFF;"></i>Enregistrer Paiement {# Icône Enregistrer Blanche #}
                            </button>
                            <button type="button" id="generateReceiptFromPaymentTab" class="btn btn-success">
                                <i class="fas fa-receipt me-2" style="color: #28A745;"></i>Générer Reçu {# Icône Reçu Verte #}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
</div>


<div class="tab-pane fade" id="rapports" role="tabpanel">
  <div class="row justify-content-center">
    <div class="col-12">
      <div class="card shadow-lg">
        <div class="card-header bg-primary text-white">
          <h5 class="mb-0"><i class="fas fa-chart-pie me-2" style="color: #4CAF50;"></i>Rapport financier</h5> {# Icône Graphique Circulaire Vert #}
        </div>
        <div class="card-body">
          <div class="row">
            <div class="col-md-6">
              <div class="card mb-3">
                <div class="card-body">
                  <h6 class="text-muted">Statistiques globales</h6>
                  <div class="d-flex justify-content-between align-items-center">
                    <div>
                      <p class="mb-0">Total des factures</p>
                      <h3 id="invoiceCount" class="text-primary">{{ report_summary.count }}</h3>
                    </div>
                    <i class="fas fa-file-invoice fa-3x text-primary" style="color: #007BFF;"></i> {# Icône Facture Bleue #}
                  </div>
                </div>
              </div>
            </div>
            <div class="col-md-6">
              <div class="card mb-3">
                <div class="card-body">
                  <h6 class="text-muted">Total des Factures</h6>
                  <div class="d-flex justify-content-between align-items-center">
                    <div>
                      <p class="mb-0">Total TTC</p>
                      <h3 id="totalTTCCard" class="text-success">{{ "%.2f"|format(report_summary.total_ttc) }} {{ report_summary.currency }}</h3>
                    </div>
                    <i class="fas fa-chart-line fa-3x text-success" style="color: #28A745;"></i> {# Icône Ligne de Graphique Verte #}
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="row">
            <div class="col-md-4">
              <div class="card mb-3">
                <div class="card-body">
                  <h6 class="text-muted">Total HT</h6>
                  <div class="d-flex justify-content-between align-items-center">
                    <div>
                      <h4 id="totalHTCard" class="text-info">
                        {{ "%.2f"|format(report_summary.total_ht) }} {{ report_summary.currency }}
                      </h4>
                      <span class="text-muted small">Hors taxes</span>
                    </div>
                    <i class="fas fa-money-bill-wave fa-3x text-info" style="color: #17A2B8;"></i> {# Icône Vague Billet Cyan #}
                  </div>
                </div>
              </div>
            </div>

            <div class="col-md-4">
              <div class="card mb-3">
                <div class="card-body">
                  <h6 class="text-muted">Total TVA</h6>
                  <div class="d-flex justify-content-between align-items-center">
                    <div>
                      <h4 id="totalTVACard" class="text-danger">
                        {{ "%.2f"|format(report_summary.total_tva) }} {{ report_summary.currency }}
                      </h4>
                      <span class="text-muted small">TVA collectée</span>
                    </div>
                    <i class="fas fa-percent fa-3x text-danger" style="color: #DC3545;"></i> {# Icône Pourcentage Rouge #}
                  </div>
                </div>
              </div>
            </div>

            <div class="col-md-4">
              <div class="card mb-3">
                <div class="card-body">
                  <h6 class="text-muted">Moyenne/facture</h6>
                  <div class="d-flex justify-content-between align-items-center">
                    <div>
                      <h4 id="averageCard" class="text-warning">
                        {{ "%.2f"|format(report_summary.total_ttc / report_summary.count if report_summary.count else 0) }}
                        {{ report_summary.currency }}
                      </h4>
                      <span class="text-muted small">Montant moyen</span>
                    </div>
                    <i class="fas fa-chart-bar fa-3x text-warning" style="color: #FFC107;"></i> {# Icône Barre de Graphique Ambre #}
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="mt-4">
            <h5><i class="fas fa-filter me-2" style="color: #6C757D;"></i>Filtrer par période</h5> {# Icône Filtre Grise #}
            <div class="row g-3">
              <div class="col-md-4 floating-label">
                <input type="date" class="form-control" id="startDate" placeholder=" ">
                <label for="startDate"><i class="fas fa-calendar-alt me-2" style="color: #FFB6C1;"></i>Date de début</label> {# Icône Calendrier Alt Rose Clair #}
              </div>
              <div class="col-md-4 floating-label">
                <input type="date" class="form-control" id="endDate" placeholder=" ">
                <label for="endDate"><i class="fas fa-calendar-alt me-2" style="color: #FFB6C1;"></i>Date de fin</label> {# Icône Calendrier Alt Rose Clair #}
              </div>
              <div class="col-md-4">
                <button class="btn btn-primary w-100" onclick="updateReport()">
                  <i class="fas fa-sync me-2" style="color: #FFFFFF;"></i>Actualiser {# Icône Synchronisation Blanche #}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="tab-pane fade" id="historique" role="tabpanel">
  <div class="row justify-content-center">
    <div class="col-12">
      <div class="card shadow-lg">
        <div class="card-header bg-primary text-white">
          <h5 class="mb-0"><i class="fas fa-history me-2" style="color: #FFC107;"></i>Historique des paiements</h5> {# Icône Historique Ambre #}
        </div>
        <div class="card-body">
          <div class="table-responsive">
            <table class="table table-hover" id="invoiceTable">
              <thead class="table-light">
                <tr>
                  <th>Numéro</th>
                  <th>Date</th>
                  <th>Patient</th>
                  <th>ID Patient</th> {# Nouvelle colonne #}
                  <th>Services</th>
                  <th class="text-end">Montant HT</th>
                  <th class="text-end">TVA</th>
                  <th class="text-end">Total</th>
                  <th class="text-center">Statut</th> {# Nouvelle colonne pour le statut #}
                  <th class="text-center">Actions</th>
                  <th>Preuve</th> {# Nouvelle colonne pour la preuve de paiement #}
                </tr>
              </thead>
              <tbody>
                {# Factures will be loaded dynamically by DataTables #}
              </tbody>
            </table>
          </div>

          <div class="d-flex justify-content-between align-items-center mt-3">
            <div class="text-muted small">
              Affichage de <span id="invoiceCountHistory">0</span> paiements
            </div>
        </div>
      </div>
    </div>
  </div>
</div>

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/dataTables.bootstrap5.min.js"></script>
<script>
console.log("Script loaded.");

// Fonction pour afficher une boîte de dialogue de confirmation personnalisée avec SweetAlert2
function showConfirmDialog(message, confirmAction) {
  Swal.fire({
    title: 'Êtes-vous sûr ?',
    text: message,
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#3085d6',
    cancelButtonColor: '#d33',
    confirmButtonText: 'Oui, supprimer !',
    cancelButtonText: 'Annuler'
  }).then((result) => {
    if (result.isConfirmed) {
      confirmAction();
    }
  });
}

let invoiceDataTable; // Déclarer la variable pour la DataTable

// Fonction pour charger et rafraîchir les données de la table des factures
function loadAndRefreshInvoiceTable() {
    console.log("Loading and refreshing invoice table data...");
    const currency = "{{ currency }}"; // Récupérer la devise

    // Fetch the latest invoices data from the new API endpoint
    fetch('{{ url_for("facturation.get_invoices_data") }}')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(factures => {
            console.log("Invoice data fetched:", factures);

            if (invoiceDataTable) {
                invoiceDataTable.destroy(); // Détruire l'instance existante de DataTables
            }

            const tableBody = document.querySelector('#invoiceTable tbody');
            tableBody.innerHTML = ''; // Vider le corps de la table

            if (factures && factures.length > 0) {
                factures.forEach(f => {
                    const tr = document.createElement('tr');
                    const isPaid = f.Statut_Paiement === 'Payée';
                    tr.innerHTML = `
                        <td>${f.Numero}</td>
                        <td>${f.Date}</td>
                        <td>${f.Patient}</td>
                        <td>${f.Patient_ID || ''}</td> {# Ajout de l'ID Patient #}
                        <td>${f.Services}</td>
                        <td class="text-end">${f['Sous-total'].toFixed(2)} ${currency}</td>
                        <td class="text-end">${f.TVA.toFixed(2)} ${currency}</td>
                        <td class="text-end">${f.Total.toFixed(2)} ${currency}</td>
                        <td class="text-center">
                            <span class="badge bg-${isPaid ? 'success' : 'warning'}">
                                ${f.Statut_Paiement || 'Inconnu'}
                            </span>
                        </td>
                        <td class="text-center">
                            <a href="{{ url_for('facturation.download_invoice', filename='') }}${f.PDF_Filename}"
                               class="btn btn-sm btn-outline-primary" title="Télécharger Facture" target="_blank">
                              <i class="fas fa-download" style="color: #007BFF;"></i>
                            </a>
                            {# MODIFICATION ICI: Désactiver le bouton de reçu si la facture est impayée #}
                            <button class="btn btn-sm btn-outline-success generate-receipt"
                                    data-invoice-id="${f.Numero}" title="Générer Reçu" ${isPaid ? '' : 'disabled'}>
                              <i class="fas fa-receipt" style="color: #28A745;"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger delete-invoice"
                                    data-id="${f.Numero}" title="Supprimer">
                              <i class="fas fa-trash" style="color: #DC3545;"></i>
                            </button>
                        </td>
                        <td class="text-center">
                            ${f.Preuve_Paiement_Fichier ? `
                            <a href="{{ url_for('facturation.download_payment_proof', filename='') }}${f.Preuve_Paiement_Fichier}"
                               class="btn btn-sm btn-outline-info" title="Télécharger Preuve" target="_blank">
                              <i class="fas fa-file-image" style="color: #17A2B8;"></i>
                            </a>` : ''}
                        </td>
                    `;
                    tableBody.appendChild(tr);
                });
            } 
            
            // Réinitialiser DataTables avec les nouvelles données
            invoiceDataTable = $('#invoiceTable').DataTable({
                language: {
                    url: '//cdn.datatables.net/plug-ins/1.13.7/i18n/fr-FR.json'
                },
                order: [[ 1, 'desc' ]], // Tri par date descendante
                pageLength: 25,
                destroy: true // Permet de réinitialiser la table si elle existe déjà
            });

            document.getElementById('invoiceCountHistory').textContent = factures.length;

            // Réattacher les écouteurs d'événements après le rechargement de la table
            attachInvoiceTableEventListeners();
        })
        .catch(error => {
            console.error('Error fetching invoice data:', error);
            Swal.fire({
                icon: 'error',
                title: 'Erreur',
                text: 'Erreur lors du chargement des données de factures: ' + error.message,
                confirmButtonText: 'OK'
            });
        });
}

// Fonction pour attacher les écouteurs d'événements aux boutons de la table
function attachInvoiceTableEventListeners() {
    // Supprimer la facture
    document.querySelectorAll('.delete-invoice').forEach(btn => {
        btn.onclick = null; // Supprimer les anciens écouteurs
        btn.addEventListener('click', function() {
            const invoiceId = this.dataset.id;
            showConfirmDialog(`Supprimer la facture ${invoiceId} ? Cette action est irréversible !`, () => {
                fetch(`/facturation/delete/${invoiceId}`, { method: 'DELETE' })
                    .then(response => {
                        if (response.ok) {
                            Swal.fire({
                                icon: 'success',
                                title: 'Supprimé !',
                                text: 'La facture a été supprimée.',
                                confirmButtonText: 'OK'
                            }).then(() => {
                                loadAndRefreshInvoiceTable(); // Recharger les données de la table après suppression
                            });
                        } else {
                            response.json().then(errorData => {
                                Swal.fire({
                                    icon: 'error',
                                    title: 'Erreur',
                                    text: errorData.error || 'Erreur lors de la suppression.',
                                    confirmButtonText: 'OK'
                                });
                            }).catch(() => {
                                Swal.fire({
                                    icon: 'error',
                                    title: 'Erreur',
                                    text: 'Erreur lors de la suppression (réponse non JSON).',
                                    confirmButtonText: 'OK'
                                });
                            });
                        }
                    })
                    .catch((error) => {
                        console.error('Erreur réseau lors de la suppression:', error);
                        Swal.fire({
                            icon: 'error',
                            title: 'Erreur',
                            text: 'Erreur réseau lors de la suppression.',
                            confirmButtonText: 'OK'
                        });
                    });
            });
        });
    });

    // Générer le reçu (bouton dans l'historique)
    document.querySelectorAll('.generate-receipt').forEach(btn => {
        btn.onclick = null; // Supprimer les anciens écouteurs
        btn.addEventListener('click', function() {
            const invoiceId = this.dataset.invoiceId;
            // Le bouton est déjà désactivé pour les factures impayées, donc pas besoin de vérification ici
            window.open(`/facturation/generate_receipt/${invoiceId}`, '_blank');
        });
    });
}


// Générer le reçu (NOUVEAU BOUTON dans l'onglet Paiements)
document.getElementById('generateReceiptFromPaymentTab').addEventListener('click', function() {
    const invoiceNumber = document.getElementById('invoiceNumberInput').value.trim();
    if (!invoiceNumber) {
        Swal.fire({
            icon: 'warning',
            title: 'Attention',
            text: 'Veuillez entrer un numéro de facture pour générer un reçu.'
        });
        return;
    }

    // MODIFICATION ICI: Fetch invoice details to check payment status
    fetch(`/facturation/get_invoice_details/${invoiceNumber}`)
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => Promise.reject(err));
            }
            return response.json();
        })
        .then(data => {
            if (data && data.Statut_Paiement === 'Payée') {
                window.open(`/facturation/generate_receipt/${invoiceNumber}`, '_blank');
            } else if (data && data.Numero) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Impossible de générer le reçu',
                    text: `La facture ${invoiceNumber} n'est pas encore marquée comme 'Payée'.`
                });
            } else {
                Swal.fire({
                    icon: 'error',
                    title: 'Erreur',
                    text: `Facture ${invoiceNumber} introuvable.`
                });
            }
        })
        .catch(error => {
            console.error('Erreur lors de la récupération des détails de la facture:', error);
            Swal.fire({
                icon: 'error',
                title: 'Erreur',
                text: 'Erreur lors de la récupération des détails de la facture pour la génération du reçu.'
            });
        });
});


// Exporter vers Excel (inchangé)
function exportToExcel() {
  fetch('/facturation/export')
    .then(response => response.blob())
    .then(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `export_factures_${new Date().toISOString().slice(0,10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    });
}

// Mettre à jour le rapport
function updateReport() {
  const start = document.getElementById('startDate').value;
  const end   = document.getElementById('endDate').value;

  fetch(`/facturation/report?start=${start}&end=${end}`)
    .then(res => res.json())
    .then(data => {
      document.getElementById('invoiceCount' ).textContent = data.count;
      document.getElementById('totalHTCard' ).textContent = data.total_ht.toFixed(2)  + ' ' + data.currency;
      document.getElementById('totalTVACard').textContent = data.total_tva.toFixed(2) + ' ' + data.currency;
      document.getElementById('totalTTCCard').textContent = data.total_ttc.toFixed(2) + ' ' + data.currency;
      document.getElementById('averageCard').textContent = data.average.toFixed(2)   + ' ' + data.currency;
    })
    .catch(() => Swal.fire({icon:'error', title:'Erreur', text:'Erreur lors de la mise à jour du rapport.'}));
}

// MODIFICATION ICI: Mise à jour de l'affichage du patient sélectionné/saisi dans l'onglet Facturation
const patientsInfo = {{ patients_info|tojson }};
const patientIdInputFacturation = document.getElementById('patientIdInputFacturation'); // Nouveau champ de saisie ID Patient
const lastPatientIdDisplay = document.getElementById('last_patient_id');
const lastPatientNameDisplay = document.getElementById('last_patient_name');
const lastPatientPhoneDisplay = document.getElementById('last_patient_phone');

function updatePatientDisplay(patientId) {
    const selectedPatient = patientsInfo.find(p => String(p.ID) === String(patientId)) || {};
    if (lastPatientIdDisplay) lastPatientIdDisplay.innerHTML = `<strong>ID :</strong> ${selectedPatient.ID || ''}`;
    if (lastPatientNameDisplay) lastPatientNameDisplay.innerHTML = `<strong>Nom :</strong> ${(selectedPatient.Nom || '') + ' ' + (selectedPatient.Prenom || '')}`.trim();
    if (lastPatientPhoneDisplay) lastPatientPhoneDisplay.innerHTML = `<strong>Téléphone :</strong> ${selectedPatient.Téléphone || ''}`;
}

if (patientIdInputFacturation) {
    patientIdInputFacturation.addEventListener('input', () => {
        updatePatientDisplay(patientIdInputFacturation.value);
    });
    // Initialiser l'affichage avec la valeur par défaut si elle existe
    updatePatientDisplay(patientIdInputFacturation.value);
}


// Variables globales pour l'onglet Facturation
const vatInput      = document.getElementById('vatInput');
const vatPercent    = document.getElementById('vatPercent');
let vatRate         = parseFloat(vatInput.value) || 0;
const serviceSelect  = document.getElementById('serviceSelect'); // Renommé pour éviter conflit
const servicePrice = document.getElementById('servicePrice'); // Ajouté pour référence
const addServiceBtn = document.getElementById('addServiceBtn');
const addToCatalog  = document.getElementById('addToCatalogBtn');
const servicesTable = document.querySelector('#servicesTable tbody');
const totalHTElm    = document.getElementById('totalHT');
const totalTVAElem  = document.getElementById('totalTVA');
const totalTTCElem  = document.getElementById('totalTTC');
const datalist      = document.getElementById('serviceList');
const cards         = document.querySelectorAll('.service-card');
const servicesByCategory = {{ services_by_category|tojson }};

// Validation TVA
if (vatInput) {
  vatInput.addEventListener('change', () => {
    const val = parseFloat(vatInput.value);
    if (isNaN(val) || val < 0 || val > 100) {
        Swal.fire({icon:'error', title:'Erreur', text:"Le taux de TVA doit être entre 0 et 100"});
        vatInput.value = "{{ vat_default }}";
        return;
    }
    vatRate = val;
    if (vatPercent) vatPercent.textContent = val.toFixed(2);
    recalcTotals();
  });
}

// Recalculer les totaux
function recalcTotals() {
  let ht = 0;
  if (servicesTable) { // Vérifier si la table existe
    servicesTable.querySelectorAll('.price-input').forEach(i => {
      ht += parseFloat(i.value) || 0;
    });
  }
  const tva = ht * vatRate / 100;
  if (totalHTElm) totalHTElm.textContent   = ht.toFixed(2);
  if (totalTVAElem) totalTVAElem.textContent = tva.toFixed(2);
  if (totalTTCElem) totalTTCElem.textContent = (ht + tva).toFixed(2);
}

// Remplir la datalist
function fillDatalist(cat) {
  if (datalist) datalist.innerHTML = '';
  // Vérifier si servicesByCategory[cat] est défini et non vide
  if (servicesByCategory[cat] && servicesByCategory[cat].length > 0) {
    servicesByCategory[cat].forEach(svc => {
      let name, price;
      if (svc.includes('|')) [name, price] = svc.split('|');
      else { name=svc; price=''; } // Si pas de prix, utiliser une chaîne vide
      const opt = document.createElement('option');
      opt.value = price ? `${name}|${price}` : name;
      if (datalist) datalist.appendChild(opt);
    });
  } else {
    // Ajouter une option de placeholder si la catégorie est vide
    const opt = document.createElement('option');
    opt.value = "Aucun service disponible pour cette catégorie";
    opt.disabled = true; // Rendre non sélectionnable
    if (datalist) datalist.appendChild(opt);
  }
}


// Catégories cliquables
cards.forEach(card => {
  card.addEventListener('click', () => {
    cards.forEach(c => c.classList.remove('active'));
    card.classList.add('active');
    fillDatalist(card.dataset.cat);
    if (serviceSelect) serviceSelect.focus();
  });
});
// Remplissage initial au chargement de la page
if (cards.length > 0 && servicesByCategory[cards[0].dataset.cat]) { // Vérifier si la première catégorie a des données
  cards[0].classList.add('active');
  fillDatalist(cards[0].dataset.cat);
} else if (cards.length > 0) { // Si la première catégorie est vide, l'activer quand même
  cards[0].classList.add('active');
  fillDatalist(cards[0].dataset.cat); // Affichera "Aucun service..."
}


// Liaison du champ de prix
if (serviceSelect) {
  serviceSelect.addEventListener('change', () => {
    const val = serviceSelect.value.trim();
    let price = '';
    if (val.includes('|')) {
      [, price] = val.split('|');
    }
    if (servicePrice) servicePrice.value = parseFloat(price) || '';
    if (servicePrice) servicePrice.focus();
  });
}


// Ajouter une ligne de service
if (addServiceBtn) {
  addServiceBtn.addEventListener('click', () => {
    const raw   = serviceSelect.value.trim();
    if (!raw || raw === "Aucun service disponible pour cette catégorie") { // Empêcher l'ajout du texte de placeholder
      Swal.fire({icon:'warning', title:'Attention', text:'Veuillez sélectionner un service valide.'});
      return;
    }
    const name  = raw.includes('|') ? raw.split('|')[0] : raw;
    const price = parseFloat(servicePrice.value) || 0;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${name}</td>
      <td>
        <input type="number" class="form-control form-control-sm price-input"
               value="${price.toFixed(2)}" step="0.01">
      </td>
      <td class="text-center">
        <button type="button" class="btn btn-sm btn-outline-danger remove-btn">
          <i class="fas fa-trash" style="color: #DC3545;"></i> {# Icône Corbeille Rouge #}
        </button>
      </td>
      {# Removed hidden input for individual service, now collected via JS #}
    `;
    tr.querySelector('.remove-btn').onclick    = () => { tr.remove(); recalcTotals(); };
    tr.querySelector('.price-input').oninput   = recalcTotals;
    if (servicesTable) servicesTable.appendChild(tr);
    recalcTotals();
    if (serviceSelect) serviceSelect.value = '';
    if (servicePrice) servicePrice.value  = '';
    if (serviceSelect) serviceSelect.focus();
  });
}


// Ajouter au catalogue
if (addToCatalog) {
  addToCatalog.addEventListener('click', () => {
    const active = document.querySelector('.service-card.active');
    if (active) document.getElementById('catalogCategory').value = active.dataset.cat;
    new bootstrap.Modal(document.getElementById('catalogModal')).show();
  });
}

const catalogForm = document.getElementById('catalogForm');
if (catalogForm) {
  catalogForm.addEventListener('submit', e => {
    e.preventDefault();
    const cat = document.getElementById('catalogCategory').value;
    const name = document.getElementById('catalogName').value.trim();
    const price= document.getElementById('catalogPrice').value;
    fetch("{{ url_for('facturation.add_service') }}", {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({category:cat,name,price})
    })
    .then(r => r.json())
    .then(res => {
      if (res.success) {
        servicesByCategory[cat].push(`${name}|${price}`);
        if (document.querySelector('.service-card.active').dataset.cat===cat) fillDatalist(cat);
        if (serviceSelect) serviceSelect.value = price?`${name}|${price}`:name;
        if (addServiceBtn) addServiceBtn.click();
        bootstrap.Modal.getInstance(document.getElementById('catalogModal')).hide();
        Swal.fire({icon:'success', title:'Service ajouté', text:'Le service a été ajouté au catalogue.'});
      } else Swal.fire({icon:'error', title:'Erreur', text:res.error||'Erreur'});
    })
    .catch(()=>Swal.fire({icon:'error', title:'Erreur réseau', text:'Impossible d’ajouter le service.'}));
  });
}


// Activer la recherche, le tri et la pagination sur la table des factures
$(document).ready(function () {
  console.log("DOM Ready.");

  // Gérer la persistance des onglets au rechargement de la page
  const urlParams = new URLSearchParams(window.location.search);
  const activeTabId = urlParams.get('tab');
  if (activeTabId) {
    const tabElement = document.getElementById(`tab-${activeTabId}`);
    if (tabElement) {
      const tab = new bootstrap.Tab(tabElement);
      tab.show();
    }
  } else {
    // Si aucun onglet n'est spécifié, par défaut le premier onglet (Facturation)
    const firstTab = document.querySelector('#factTab .nav-link.active');
    if (firstTab) {
      const tab = new bootstrap.Tab(firstTab);
      tab.show();
    }
  }

  // Mettre à jour le hachage de l'URL lorsqu'un onglet est affiché
  $('button[data-bs-toggle="tab"]').on('shown.bs.tab', function (e) {
    const targetTabId = e.target.id.replace('tab-', '');
    history.replaceState(null, '', `?tab=${targetTabId}`);
    console.log(`Tab ${targetTabId} shown.`);
    // Si l'onglet "paiements" est affiché, initialiser sa logique
    if (targetTabId === 'paiements') {
      initPaymentTabLogic();
    } else if (targetTabId === 'historique') {
      loadAndRefreshInvoiceTable(); // Refresh history table when it's shown
    }
  });

  // --- Logique spécifique à l'onglet de paiement ---
  // Déplacé dans une fonction pour être appelée lors de l'affichage de l'onglet
  function initPaymentTabLogic() {
    console.log("initPaymentTabLogic called.");
    const invoiceNumberInput = document.getElementById('invoiceNumberInput');
    console.log("invoiceNumberInput element:", invoiceNumberInput); // Check if element is found
    const patientIdInput = document.getElementById('patientIdInput');
    const patientNomInput = document.getElementById('patientNomInput');
    const patientPrenomInput = document.getElementById('patientPrenomInput');
    const amountInput = document.getElementById('amountInput');
    const typeActeInput = document.getElementById('typeActeInput');

    // Function to clear all payment fields
    function clearPaymentFields() {
      console.log("Clearing payment fields.");
      if (patientIdInput) patientIdInput.value = '';
      if (patientNomInput) patientNomInput.value = '';
      if (patientPrenomInput) patientPrenomInput.value = '';
      if (amountInput) amountInput.value = '';
      if (typeActeInput) typeActeInput.value = 'Paiement'; // Reset to generic default
    }

    // Initial fill for the payment tab when it loads with last_invoice_info
    const lastInvoiceData = {{ last_invoice_info | tojson }};
    if (lastInvoiceData && lastInvoiceData.Numero) {
        // Only pre-fill if the invoice number input is currently empty
        if (invoiceNumberInput && invoiceNumberInput.value === '') { 
            invoiceNumberInput.value = lastInvoiceData.Numero || '';
            if (patientIdInput) patientIdInput.value = lastInvoiceData.Patient_ID || '';
            if (patientNomInput) patientNomInput.value = lastInvoiceData.Patient_Nom || '';
            if (patientPrenomInput) patientPrenomInput.value = lastInvoiceData.Patient_Prenom || '';
            if (amountInput) amountInput.value = lastInvoiceData.Total ? parseFloat(lastInvoiceData.Total).toFixed(2) : '';
            if (typeActeInput) typeActeInput.value = lastInvoiceData.Calculated_Type_Acte || 'Paiement';
            console.log("Initial fields filled from last invoice data.");
        }
    }
  }

  // Attach event delegation for invoiceNumberInput once DOM is ready
  // This handles elements that might not be immediately present or are dynamically added/removed
  $('#factTabContent').on('input', '#invoiceNumberInput', function() {
    // Call the logic for handling invoice number input
    // We need to pass 'this' context if handleInvoiceNumberInput expects it
    // Or, better, refactor handleInvoiceNumberInput to accept the input element directly
    const invoiceNumberInput = this; // 'this' refers to the #invoiceNumberInput element
    const invoiceNumber = invoiceNumberInput.value.trim();
    console.log(`Delegated input event fired for invoiceNumberInput. Value: "${invoiceNumber}"`);

    const patientIdInput = document.getElementById('patientIdInput');
    const patientNomInput = document.getElementById('patientNomInput');
    const patientPrenomInput = document.getElementById('patientPrenomInput');
    const amountInput = document.getElementById('amountInput');
    const typeActeInput = document.getElementById('typeActeInput');

    function clearFields() {
        if (patientIdInput) patientIdInput.value = '';
        if (patientNomInput) patientNomInput.value = '';
        if (patientPrenomInput) patientPrenomInput.value = '';
        if (amountInput) amountInput.value = '';
        if (typeActeInput) typeActeInput.value = 'Paiement';
    }

    if (invoiceNumber) {
        fetch(`/facturation/get_invoice_details/${invoiceNumber}`)
            .then(response => {
                if (!response.ok) {
                    console.error(`HTTP error! status: ${response.status}`);
                    return response.json().then(err => Promise.reject(err));
                }
                return response.json();
            })
            .then(data => {
                if (data && data.Numero) {
                    if (patientIdInput) patientIdInput.value = data.Patient_ID || '';
                    if (patientNomInput) patientNomInput.value = data.Patient_Nom || '';
                    if (patientPrenomInput) patientPrenomInput.value = data.Patient_Prenom || '';
                    if (amountInput) amountInput.value = data.Total ? parseFloat(data.Total).toFixed(2) : '';
                    if (typeActeInput) typeActeInput.value = data.Calculated_Type_Acte || 'Facturation';
                } else {
                    clearFields();
                }
            })
            .catch(error => {
                console.error('Erreur lors de la récupération des détails de la facture:', error);
                clearFields();
            });
    } else {
        clearFields();
    }
  });


  // Call initPaymentTabLogic if the payments tab is the one initially active on page load
  const initialActiveTab = document.querySelector('#factTab .nav-link.active');
  if (initialActiveTab && initialActiveTab.id === 'tab-paiements') {
    initPaymentTabLogic();
  } else if (initialActiveTab && initialActiveTab.id === 'tab-historique') {
    loadAndRefreshInvoiceTable(); // Load history table on initial load if it's the active tab
  }
  console.log("DOM Ready finished.");
});

// Modifié le gestionnaire d'événements du bouton de soumission de facture pour utiliser AJAX
document.getElementById('submitInvoiceBtn').addEventListener('click', function() {
    const form = document.getElementById('invoiceForm');
    const formData = new FormData(form);

    // Collecter les services sélectionnés depuis la table
    const selectedServices = [];
    document.querySelectorAll('#servicesTable tbody tr').forEach(row => {
        const name = row.querySelector('td:first-child').textContent.trim();
        const priceInput = row.querySelector('.price-input');
        const price = parseFloat(priceInput ? priceInput.value : '0'); // Assurez-vous que l'input existe
        selectedServices.push({name: name, price: price});
    });
    formData.append('services_json', JSON.stringify(selectedServices));

    // MODIFICATION ICI: Récupérer l'ID patient du nouveau champ de saisie
    const patientId = document.getElementById('patientIdInputFacturation').value.trim();
    if (!patientId) {
        Swal.fire({
            icon: 'warning',
            title: 'Attention',
            text: 'Veuillez saisir un ID patient.'
        });
        return; // Empêcher la soumission si l'ID patient est vide
    }
    formData.append('patient_id', patientId); // Ajouter l'ID patient aux données du formulaire

    fetch(form.action, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            // Si la réponse n'est pas OK (ex: 400, 500), tenter de lire l'erreur JSON
            return response.json().then(err => Promise.reject(err));
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            Swal.fire({
                icon: 'success',
                title: 'Facture générée !',
                text: data.message,
                confirmButtonText: 'OK'
            }).then(() => {
                // 1. Remplir l'onglet Paiement
                const invoiceData = data.invoice;
                document.getElementById('invoiceNumberInput').value = invoiceData.Numero || '';
                document.getElementById('patientIdInput').value = invoiceData.Patient_ID || '';
                document.getElementById('patientNomInput').value = invoiceData.Patient_Nom || '';
                document.getElementById('patientPrenomInput').value = invoiceData.Patient_Prenom || '';
                document.getElementById('amountInput').value = invoiceData.Total ? parseFloat(invoiceData.Total).toFixed(2) : '';
                document.getElementById('typeActeInput').value = invoiceData.Calculated_Type_Acte || 'Paiement';

                // 2. Basculer vers l'onglet Paiement
                const paymentTabButton = document.getElementById('tab-paiements');
                const paymentTab = new bootstrap.Tab(paymentTabButton);
                paymentTab.show();

                // 3. Déclencher le téléchargement du PDF
                if (invoiceData.pdf_filename) {
                    window.open(`{{ url_for('facturation.download_invoice', filename='') }}${invoiceData.pdf_filename}`, '_blank');
                }

                // No longer reloading the page. The history tab will refresh when activated.
            });
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Erreur !',
                text: data.error || 'Une erreur est survenue lors de la génération de la facture.'
            });
        }
    })
    .catch(error => {
        console.error('Erreur:', error);
        Swal.fire({
            icon: 'error',
            title: 'Erreur réseau',
            text: 'Impossible de se connecter au serveur.'
        });
    });
});
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# --------------------------- TEMPLATE PATIENT ------------------------------
# ---------------------------------------------------------------------------
new_patient_template = r"""
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
  <title>Ajouter un patient</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-5">
  <h1 class="mb-4">Ajouter un nouveau patient</h1>
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% for cat, msg in messages %}
      <div class="alert alert-{{ cat }}">{{ msg }}</div>
    {% endfor %}
  {% endwith %}
  <form method="post">
    <div class="mb-3">
      <label class="form-label">ID</label>
      <input type="text" name="ID" class="form-control" required>
    </div>
    <div class="mb-3">
      <label class="form-label">Nom</label>
      <input type="text" name="Nom" class="form-control" required>
    </div>
    <div class="mb-3">
      <label class="form-label">Prénom</label>
      <input type="text" name="Prenom" class="form-control" required>
    </div>
    <div class="mb-3">
      <label class="form-label">Téléphone</label>
      <input type="text" name="Téléphone" class="form-control">
    </div>
    <button type="submit" class="btn btn-primary">Enregistrer</button>
    <a href="{{ url_for('facturation.home_facturation') }}" class="btn btn-secondary ms-2">Annuler</a>
  </form>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
