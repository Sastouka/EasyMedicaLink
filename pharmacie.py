# pharmacie.py
# Module pour la gestion du stock des produits pharmaceutiques et parapharmaceutiques
# ──────────────────────────────────────────────────────────────────────────────
from flask import Blueprint, render_template_string, session, redirect, url_for, flash, request, jsonify, send_file
from datetime import datetime
import utils
import theme
import pandas as pd
import os
import io
from fpdf import FPDF # Import pour la génération de PDF
import math
import login

# Création du Blueprint pour les routes de pharmacie
pharmacie_bp = Blueprint('pharmacie', __name__, url_prefix='/pharmacie')

# Chemin du fichier Excel unique pour la pharmacie (sera défini dynamiquement)
PHARMACIE_EXCEL_FILE: str = ""

# Assurez-vous que PHARMACIE_EXCEL_FILE est correctement initialisé ici
# après que utils.EXCEL_FOLDER ait été défini par utils.set_dynamic_base_dir.
@pharmacie_bp.before_request
def set_pharmacie_excel_file_path():
    global PHARMACIE_EXCEL_FILE
    if utils.EXCEL_FOLDER is None:
        # Fallback si le répertoire n'est pas encore défini (ex: accès direct à la route)
        admin_email = session.get('admin_email', 'default_admin@example.com')
        utils.set_dynamic_base_dir(admin_email)
    PHARMACIE_EXCEL_FILE = os.path.join(utils.EXCEL_FOLDER, 'Pharmacie.xlsx')

def initialize_pharmacie_excel_file_if_not_exists():
    """
    Initialise le fichier Pharmacie.xlsx avec les feuilles Inventaire et Mouvements
    et leurs en-têtes si le fichier n'existe pas ou si des feuilles sont manquantes.
    """
    if not os.path.exists(PHARMACIE_EXCEL_FILE):
        print(f"DEBUG: Le fichier Pharmacie.xlsx n'existe pas. Initialisation...")
        try:
            with pd.ExcelWriter(PHARMACIE_EXCEL_FILE, engine='xlsxwriter') as writer:
                # Feuille Inventaire
                pd.DataFrame(columns=['Code_Produit', 'Nom', 'Type', 'Usage', 'Quantité', 'Prix_Achat', 'Prix_Vente', 'Fournisseur', 'Date_Expiration', 'Seuil_Alerte', 'Date_Enregistrement']).to_excel(writer, sheet_name='Inventaire', index=False)
                # Feuille Mouvements
                pd.DataFrame(columns=['Date', 'Code_Produit', 'Nom_Produit', 'Type_Mouvement', 'Quantité_Mouvement', 'Nom_Responsable', 'Prenom_Responsable', 'Telephone_Responsable']).to_excel(writer, sheet_name='Mouvements', index=False)
            print(f"DEBUG: Fichier {PHARMACIE_EXCEL_FILE} initialisé avec les feuilles Inventaire et Mouvements.")
        except Exception as e:
            print(f"ERREUR: Impossible de sauvegarder le fichier {PHARMACIE_EXCEL_FILE} lors de l'initialisation: {e}")
            flash(f"Erreur lors de l'initialisation du fichier Pharmacie.xlsx : {e}", "danger")
    else:
        print(f"DEBUG: Le fichier Pharmacie.xlsx existe déjà. Vérification des feuilles...")
        try:
            xls = pd.ExcelFile(PHARMACIE_EXCEL_FILE)
            sheets_to_create = []
            if 'Inventaire' not in xls.sheet_names:
                sheets_to_create.append('Inventaire')
            if 'Mouvements' not in xls.sheet_names:
                sheets_to_create.append('Mouvements')

            if sheets_to_create:
                print(f"DEBUG: Feuilles manquantes détectées: {sheets_to_create}. Recréation...")
                # Charger les feuilles existantes
                existing_dfs = {sheet_name: pd.read_excel(xls, sheet_name=sheet_name, dtype=str).fillna('') for sheet_name in xls.sheet_names}
                
                with pd.ExcelWriter(PHARMACIE_EXCEL_FILE, engine='xlsxwriter') as writer:
                    for sheet_name in ALL_PHARMACIE_SHEETS:
                        if sheet_name in existing_dfs:
                            existing_dfs[sheet_name].to_excel(writer, sheet_name=sheet_name, index=False)
                        else:
                            if sheet_name == 'Inventaire':
                                pd.DataFrame(columns=['Code_Produit', 'Nom', 'Type', 'Usage', 'Quantité', 'Prix_Achat', 'Prix_Vente', 'Fournisseur', 'Date_Expiration', 'Seuil_Alerte', 'Date_Enregistrement']).to_excel(writer, sheet_name=sheet_name, index=False)
                            elif sheet_name == 'Mouvements':
                                pd.DataFrame(columns=['Date', 'Code_Produit', 'Nom_Produit', 'Type_Mouvement', 'Quantité_Mouvement', 'Nom_Responsable', 'Prenom_Responsable', 'Telephone_Responsable']).to_excel(writer, sheet_name=sheet_name, index=False)
                print(f"DEBUG: Fichier {PHARMACIE_EXCEL_FILE} mis à jour avec les feuilles manquantes.")
        except Exception as e:
            print(f"ERREUR: Erreur lors de la vérification/mise à jour de Pharmacie.xlsx: {e}")
            flash(f"Erreur lors de la vérification du fichier Pharmacie.xlsx : {e}", "danger")


# Fonctions utilitaires pour charger et sauvegarder les données des feuilles Excel
def _load_sheet_data(file_path, sheet_name, default_columns, numeric_cols=[]):
    """
    Charge les données d'une feuille spécifique d'un fichier Excel.
    Initialise la feuille avec les colonnes par défaut si elle n'existe pas ou est vide.
    """
    if os.path.exists(file_path):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=str).fillna('')
            # S'assurer que toutes les colonnes attendues sont présentes, les ajouter si elles manquent
            for col in default_columns:
                if col not in df.columns:
                    df[col] = ''
            # Convertir les colonnes numériques
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    if col in ['Quantité', 'Seuil_Alerte', 'Quantité_Mouvement']: # Conversion spécifique en entier
                        df[col] = df[col].astype(int)
                    else: # Par défaut float pour les prix
                        df[col] = df[col].astype(float)
            return df
        except Exception as e:
            print(f"Erreur lors du chargement de la feuille '{sheet_name}' de {file_path}: {e}")
            flash(f"Erreur lors du chargement des données de {sheet_name}: {e}", "danger")
            return pd.DataFrame(columns=default_columns)
    return pd.DataFrame(columns=default_columns)

def _save_sheet_data(df_to_save, file_path, sheet_name, all_sheet_names):
    """
    Sauvegarde un DataFrame dans une feuille spécifique d'un fichier Excel,
    en préservant les autres feuilles.
    """
    try:
        # Lire toutes les feuilles existantes si le fichier existe
        existing_sheets_data = {}
        if os.path.exists(file_path):
            existing_sheets_data = pd.read_excel(file_path, sheet_name=None, dtype=str)
        
        # Mettre à jour le DataFrame de la feuille spécifique
        existing_sheets_data[sheet_name] = df_to_save

        # Écrire toutes les feuilles (mises à jour et non modifiées) dans le fichier
        with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
            for s_name in all_sheet_names:
                if s_name in existing_sheets_data:
                    # Assurez-vous que le DataFrame de chaque feuille a les bonnes colonnes
                    # si elles ont été lues avec dtype=str, sinon elles peuvent être vides
                    if not existing_sheets_data[s_name].empty:
                        existing_sheets_data[s_name].to_excel(writer, sheet_name=s_name, index=False)
                    else: # Si le DataFrame est vide, créer une feuille vide avec les colonnes
                         # Cela est important pour que les entêtes soient toujours présentes
                        if s_name == 'Inventaire':
                            pd.DataFrame(columns=['Code_Produit', 'Nom', 'Type', 'Usage', 'Quantité', 'Prix_Achat', 'Prix_Vente', 'Fournisseur', 'Date_Expiration', 'Seuil_Alerte', 'Date_Enregistrement']).to_excel(writer, sheet_name=s_name, index=False)
                        elif s_name == 'Mouvements':
                            pd.DataFrame(columns=['Date', 'Code_Produit', 'Nom_Produit', 'Type_Mouvement', 'Quantité_Mouvement', 'Nom_Responsable', 'Prenom_Responsable', 'Telephone_Responsable']).to_excel(writer, sheet_name=s_name, index=False)
                elif s_name == sheet_name: # Cas où la feuille est nouvelle et est celle que nous sauvons
                    df_to_save.to_excel(writer, sheet_name=s_name, index=False)

        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde de la feuille '{sheet_name}' vers {file_path}: {e}")
        flash(f"Erreur lors de la sauvegarde des données de {sheet_name}: {e}", "danger")
        return False

# Noms de toutes les feuilles que nous attendons dans Pharmacie.xlsx
ALL_PHARMACIE_SHEETS = ['Inventaire', 'Mouvements']

# Fonctions spécifiques pour le stock et les mouvements, utilisant les helpers
def load_pharmacie_inventory(file_path):
    columns = ['Code_Produit', 'Nom', 'Type', 'Usage', 'Quantité', 'Prix_Achat', 'Prix_Vente', 'Fournisseur', 'Date_Expiration', 'Seuil_Alerte', 'Date_Enregistrement']
    numeric_cols = ['Quantité', 'Prix_Achat', 'Prix_Vente', 'Seuil_Alerte']
    df = _load_sheet_data(file_path, 'Inventaire', columns, numeric_cols)
    
    # Convertir les colonnes de date en objets datetime, en forçant les erreurs
    df['Date_Expiration'] = pd.to_datetime(df['Date_Expiration'], errors='coerce')
    df['Date_Enregistrement'] = pd.to_datetime(df['Date_Enregistrement'], errors='coerce')
    
    return df

def save_pharmacie_inventory(df, file_path):
    return _save_sheet_data(df, file_path, 'Inventaire', ALL_PHARMACIE_SHEETS)

def load_pharmacie_movements(file_path):
    columns = ['Date', 'Code_Produit', 'Nom_Produit', 'Type_Mouvement', 'Quantité_Mouvement', 'Nom_Responsable', 'Prenom_Responsable', 'Telephone_Responsable']
    numeric_cols = ['Quantité_Mouvement']
    df = _load_sheet_data(file_path, 'Mouvements', columns, numeric_cols)
    
    # Convertir la colonne 'Date' en objets datetime, en gérant divers formats et en forçant les erreurs
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    
    return df

def save_pharmacie_movements(df, file_path):
    return _save_sheet_data(df, file_path, 'Mouvements', ALL_PHARMACIE_SHEETS)

# --- Fonctions utilitaires pour Comptabilite.xlsx ---
_ALL_COMPTA_SHEETS = ['Recettes', 'Depenses', 'Salaires', 'TiersPayants', 'DocumentsFiscaux']

def _load_comptabilite_sheet_data(file_path, sheet_name, default_columns, numeric_cols=[]):
    if not os.path.exists(file_path):
        empty_df = pd.DataFrame(columns=default_columns)
        for col in numeric_cols:
            empty_df[col] = 0.0
        return empty_df
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=str).fillna('')
        for col in default_columns:
            if col not in df.columns:
                df[col] = ''
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                if col in ['Montant', 'Salaire_Net', 'Charges_Sociales', 'Total_Brut', 'Montant_Attendu', 'Montant_Recu']:
                    df[col] = df[col].astype(float)
        return df
    except Exception as e:
        print(f"Erreur lors du chargement de la feuille '{sheet_name}' de {file_path}: {e}")
        empty_df = pd.DataFrame(columns=default_columns)
        for col in numeric_cols:
            empty_df[col] = 0.0
        return empty_df

def _save_comptabilite_sheet_data(df_to_save, file_path, sheet_name_to_update, all_sheet_names):
    try:
        existing_sheets_data = {}
        if os.path.exists(file_path):
            existing_sheets_data = pd.read_excel(file_path, sheet_name=None, dtype=str)
        
        existing_sheets_data[sheet_name_to_update] = df_to_save

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            for s_name in all_sheet_names:
                if s_name in existing_sheets_data and not existing_sheets_data[s_name].empty:
                    existing_sheets_data[s_name].to_excel(writer, sheet_name=s_name, index=False)
                else:
                    if s_name == 'Recettes':
                        pd.DataFrame(columns=['Date', 'Type_Acte', 'Patient_ID', 'Patient_Nom', 'Patient_Prenom', 'Montant', 'Mode_Paiement', 'Description', 'ID_Facture_Liee']).to_excel(writer, sheet_name=s_name, index=False)
                    elif s_name == 'Depenses':
                        pd.DataFrame(columns=['Date', 'Categorie', 'Description', 'Montant', 'Justificatif_Fichier']).to_excel(writer, sheet_name=s_name, index=False)
                    elif s_name == 'Salaires':
                        pd.DataFrame(columns=['Mois_Annee', 'Nom_Employe', 'Prenom_Employe', 'Salaire_Net', 'Charges_Sociales', 'Total_Brut', 'Fiche_Paie_PDF']).to_excel(writer, sheet_name=s_name, index=False)
                    elif s_name == 'TiersPayants':
                        pd.DataFrame(columns=['Date', 'Assureur', 'Patient_ID', 'Patient_Nom', 'Patient_Prenom', 'Montant_Attendu', 'Montant_Recu', 'Date_Reglement', 'ID_Facture_Liee', 'Statut']).to_excel(writer, sheet_name=s_name, index=False)
                    elif s_name == 'DocumentsFiscaux':
                        pd.DataFrame(columns=['Date', 'Type_Document', 'Description', 'Fichier_PDF']).to_excel(writer, sheet_name=s_name, index=False)
        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde de la feuille '{sheet_name_to_update}' vers {file_path}: {e}")
        return False

_DEPENSES_COLUMNS = ["Date", "Categorie", "Description", "Montant", "Justificatif_Fichier"]

def _add_expense_to_comptabilite(expense_data):
    if utils.EXCEL_FOLDER is None:
        print("Erreur: utils.EXCEL_FOLDER non défini. Impossible d'enregistrer la dépense comptable.")
        return False
    comptabilite_excel_file_path = os.path.join(utils.EXCEL_FOLDER, 'Comptabilite.xlsx')
    df_depenses = _load_comptabilite_sheet_data(comptabilite_excel_file_path, 'Depenses', _DEPENSES_COLUMNS, numeric_cols=['Montant'])
    new_depense_df = pd.DataFrame([expense_data], columns=_DEPENSES_COLUMNS)
    updated_depenses_df = pd.concat([df_depenses, new_depense_df], ignore_index=True)
    return _save_comptabilite_sheet_data(updated_depenses_df, comptabilite_excel_file_path, 'Depenses', _ALL_COMPTA_SHEETS)

# --- Fonctions de génération de PDF ---
class PDF(FPDF):
    def __init__(self, orientation='P', unit='mm', format='A4'):
        super().__init__(orientation, unit, format)
        # CORRECTION : On supprime la tentative de chargement des polices spécifiques à Windows.
        # FPDF utilisera ses polices de base (ex: Helvetica, Times) qui sont universelles
        # et garantissent que le code fonctionne sur n'importe quel système.
        self.font_family = 'Helvetica' # Police de secours universelle et fiable
        self.title = ''

    def header(self):
        self.set_font(self.font_family, 'B', 15)
        page_width = self.w
        title_width = self.get_string_width(self.title if self.title else '')
        self.set_x((page_width - title_width) / 2)
        self.cell(title_width, 10, self.title if self.title else '', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.font_family, 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font(self.font_family, 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(5)

    def create_table_improved(self, header, data, col_widths, align='C'):
        self.set_fill_color(200, 220, 255)
        self.set_text_color(0, 0, 0)
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.3)
        self.set_font(self.font_family, 'B', 8)
        table_width = sum(col_widths)
        page_width = self.w - self.l_margin - self.r_margin 
        start_x_table = self.l_margin + (page_width - table_width) / 2 
        max_header_height = 8
        temp_y_before_measure_header = self.get_y()
        for i, col in enumerate(header):
            self.set_x(start_x_table + sum(col_widths[:i])) 
            self.multi_cell(col_widths[i] - 1, 8, col, 0, 'C', 0, dry_run=True)
            measured_header_height = self.get_y() - temp_y_before_measure_header
            self.set_y(temp_y_before_measure_header) 
            if measured_header_height > max_header_height:
                max_header_height = measured_header_height
        max_header_height += 1.5 
        current_x_for_header_drawing = start_x_table
        for i, col in enumerate(header):
            self.set_xy(current_x_for_header_drawing, temp_y_before_measure_header)
            self.cell(col_widths[i], max_header_height, '', 1, 0, 'C', 1) 
            self.set_xy(current_x_for_header_drawing + 0.5, temp_y_before_measure_header + 0.5) 
            self.multi_cell(col_widths[i] - 1, 8, col, 0, 'C', 0) 
            current_x_for_header_drawing += col_widths[i]
        self.set_y(temp_y_before_measure_header + max_header_height)
        self.set_x(start_x_table)
        self.set_font(self.font_family, '', 8)
        self.set_fill_color(240, 248, 255)
        fill = False
        line_height = 6.5
        for row_data in data:
            max_row_height = line_height
            temp_y_before_measure = self.get_y()
            for i, item in enumerate(row_data):
                cell_width = col_widths[i]
                text_content = str(item)
                self.set_x(start_x_table + sum(col_widths[:i])) 
                self.multi_cell(cell_width - 1, line_height, text_content, 0, align, 0, dry_run=True) 
                measured_height = self.get_y() - temp_y_before_measure
                self.set_y(temp_y_before_measure) 
                if measured_height > max_row_height:
                    max_row_height = measured_height
            self.set_x(start_x_table)
            max_row_height += 1.5 
            if self.get_y() + max_row_height + self.b_margin > self.h: 
                self.add_page(orientation='L') 
                self.set_x(start_x_table)
                self.set_fill_color(200, 220, 255)
                self.set_font(self.font_family, 'B', 8)
                temp_y_after_page_break = self.get_y()
                current_x_for_header_drawing_on_new_page = start_x_table
                for i, col in enumerate(header):
                    self.set_xy(current_x_for_header_drawing_on_new_page, temp_y_after_page_break)
                    self.cell(col_widths[i], max_header_height, '', 1, 0, 'C', 1) 
                    self.set_xy(current_x_for_header_drawing_on_new_page + 0.5, temp_y_after_page_break + 0.5)
                    self.multi_cell(col_widths[i] - 1, 8, col, 0, 'C', 0)
                    current_x_for_header_drawing_on_new_page += col_widths[i]
                self.set_y(temp_y_after_page_break + max_header_height)
                self.set_x(start_x_table)
                self.set_font(self.font_family, '', 8)
                self.set_fill_color(240, 248, 255) 
            actual_start_y_row = self.get_y()
            current_x_for_box_drawing = start_x_table
            for i in range(len(row_data)):
                self.set_xy(current_x_for_box_drawing, actual_start_y_row)
                self.cell(col_widths[i], max_row_height, '', 1, 0, 'C', fill)
                current_x_for_box_drawing += col_widths[i]
            current_x_for_text_drawing = start_x_table
            for i, item in enumerate(row_data):
                cell_width = col_widths[i]
                text_content = str(item)
                text_x_pos = current_x_for_text_drawing + 0.5
                text_y_pos = actual_start_y_row + 0.5
                self.set_xy(text_x_pos, text_y_pos)
                self.multi_cell(cell_width - 1, line_height, text_content, 0, align, 0)
                current_x_for_text_drawing += cell_width
            self.set_y(actual_start_y_row + max_row_height)
            self.set_x(start_x_table)
            fill = not fill 

def generate_inventory_pdf(df, currency):
    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15) 
    pdf.title = 'Rapport d\'Inventaire du Stock' 
    pdf.add_page() 
    pdf.set_font(pdf.font_family, '', 10)
    pdf.cell(0, 10, f'Date du rapport: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'L')
    pdf.ln(5)
    if not df.empty:
        header = ['Code Prod.', 'Nom', 'Type', 'Usage', 'Qté', f'Prix Ach. ({currency})', f'Prix Vte. ({currency})', 'Fournisseur', 'Date Exp.', 'Seuil Al.', 'Statut', 'Date Enreg.']
        pdf_data = []
        for index, row in df.iterrows():
            product_status = "En Stock"
            if row['Quantité'] == 0: product_status = "Rupture"
            elif row['Quantité'] <= row['Seuil_Alerte']: product_status = "Stock Bas"
            
            prix_achat_formatted = "%.2f" % float(row['Prix_Achat']) if pd.notna(row['Prix_Achat']) else "N/A"
            prix_vente_formatted = "%.2f" % float(row['Prix_Vente']) if pd.notna(row['Prix_Vente']) else "N/A"
            date_exp_formatted = row['Date_Expiration'].strftime('%Y-%m-%d') if pd.notna(row['Date_Expiration']) else "N/A"
            date_enregistrement_formatted = row['Date_Enregistrement'].strftime('%Y-%m-%d') if pd.notna(row['Date_Enregistrement']) else "N/A"
            
            pdf_data.append([
                str(row['Code_Produit']), str(row['Nom']), str(row['Type']), str(row['Usage']), str(row['Quantité']),
                prix_achat_formatted, prix_vente_formatted, str(row['Fournisseur']), date_exp_formatted,
                str(row['Seuil_Alerte']), product_status, date_enregistrement_formatted
            ])
        
        page_width_available = pdf.w - pdf.l_margin - pdf.r_margin
        min_col_width = 15 
        col_max_widths = []
        pdf.set_font(pdf.font_family, 'B', 8)
        for i, h in enumerate(header):
            max_width_for_col = pdf.get_string_width(h)
            for row in pdf_data:
                pdf.set_font(pdf.font_family, '', 8)
                cell_content_width = pdf.get_string_width(str(row[i]))
                if cell_content_width > max_width_for_col: max_width_for_col = cell_content_width
            col_max_widths.append(max_width_for_col + 4)
        
        total_calculated_width = sum(col_max_widths)
        if total_calculated_width > page_width_available:
            scaling_factor = page_width_available / total_calculated_width
            col_widths = [max(min_col_width, w * scaling_factor) for w in col_max_widths]
        else:
            remaining_space = page_width_available - total_calculated_width
            col_widths = [w + (remaining_space / len(header)) for w in col_max_widths]
            col_widths = [max(min_col_width, w) for w in col_widths]
        
        pdf.create_table_improved(header, pdf_data, col_widths, align='C') 
    else:
        pdf.set_font(pdf.font_family, 'I', 12)
        pdf.cell(0, 10, "Aucun produit en stock.", 0, 1, 'C')
    output = io.BytesIO()
    pdf.output(output, 'S')
    output.seek(0)
    return output

def generate_movements_pdf(df):
    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.title = 'Rapport des Mouvements de Stock'
    pdf.add_page()
    pdf.set_font(pdf.font_family, '', 10)
    pdf.cell(0, 10, f'Date du rapport: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'L')
    pdf.ln(5)
    if not df.empty:
        header = ['Date', 'Code Prod.', 'Nom Prod.', 'Type Movt.', 'Qté', 'Nom Resp.', 'Prénom Resp.', 'Téléphone']
        pdf_data = []
        for index, row in df.iterrows():
            date_formatted = row['Date'].strftime('%Y-%m-%d %H:%M') if pd.notna(row['Date']) else "N/A"
            pdf_data.append([
                date_formatted, str(row['Code_Produit']), str(row['Nom_Produit']), str(row['Type_Mouvement']),
                str(row['Quantité_Mouvement']), str(row['Nom_Responsable']), str(row['Prenom_Responsable']),
                str(row['Telephone_Responsable'])
            ])
        
        page_width_available = pdf.w - pdf.l_margin - pdf.r_margin
        min_col_width = 15
        col_max_widths = []
        pdf.set_font(pdf.font_family, 'B', 8)
        for i, h in enumerate(header):
            max_width_for_col = pdf.get_string_width(h)
            for row in pdf_data:
                pdf.set_font(pdf.font_family, '', 8)
                cell_content_width = pdf.get_string_width(str(row[i]))
                if cell_content_width > max_width_for_col: max_width_for_col = cell_content_width
            col_max_widths.append(max_width_for_col + 4)
        
        total_calculated_width = sum(col_max_widths)
        if total_calculated_width > page_width_available:
            scaling_factor = page_width_available / total_calculated_width
            col_widths = [max(min_col_width, w * scaling_factor) for w in col_max_widths]
        else:
            remaining_space = page_width_available - total_calculated_width
            col_widths = [w + (remaining_space / len(header)) for w in col_max_widths]
            col_widths = [max(min_col_width, w) for w in col_widths]
        
        pdf.create_table_improved(header, pdf_data, col_widths, align='C') 
    else:
        pdf.set_font(pdf.font_family, 'I', 12)
        pdf.cell(0, 10, "Aucun mouvement enregistré.", 0, 1, 'C')
    output = io.BytesIO()
    pdf.output(output, 'S')
    output.seek(0)
    return output

# Route pour la page d'accueil de la pharmacie
@pharmacie_bp.route('/')
def home_pharmacie():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    if utils.EXCEL_FOLDER is None:
        if 'email' in session:
            utils.set_dynamic_base_dir(session['email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))

    initialize_pharmacie_excel_file_if_not_exists()
    global PHARMACIE_EXCEL_FILE 

    config = utils.load_config()
    session['theme'] = config.get('theme', theme.DEFAULT_THEME)
    currency = config.get('currency', 'MAD') 
    host_address = f"http://{utils.LOCAL_IP}:3000"
    current_date_str = datetime.now().strftime("%Y-%m-%d")

    inventory_df = load_pharmacie_inventory(PHARMACIE_EXCEL_FILE)
    movements_df = load_pharmacie_movements(PHARMACIE_EXCEL_FILE)
    total_products = len(inventory_df)

    # --- LOGIQUE DE FILTRAGE (AVANT LA CONVERSION EN STRING) ---
    low_stock_alerts = inventory_df[inventory_df['Quantité'] <= inventory_df['Seuil_Alerte']].to_dict(orient='records')
    
    current_date_dt = datetime.now()
    expired_products_df = inventory_df[
        (inventory_df['Date_Expiration'].notna()) & 
        (inventory_df['Date_Expiration'] < current_date_dt)
    ].copy() # Use .copy() to avoid SettingWithCopyWarning

    recent_movements_df = movements_df.sort_values(by='Date', ascending=False).head(10).copy()

    # --- PRÉ-FORMATAGE DES DATES POUR L'AFFICHAGE ---
    # Convertit les colonnes de date en chaînes de caractères ('YYYY-MM-DD' ou 'N/A')
    # Ceci est fait APRES le filtrage pour ne pas casser la logique de comparaison de dates.
    inventory_df['Date_Expiration'] = inventory_df['Date_Expiration'].dt.strftime('%Y-%m-%d').fillna('N/A')
    inventory_df['Date_Enregistrement'] = inventory_df['Date_Enregistrement'].dt.strftime('%Y-%m-%d').fillna('N/A')
    movements_df['Date'] = movements_df['Date'].dt.strftime('%Y-%m-%d %H:%M').fillna('N/A')
    
    # Formater aussi les dataframes déjà filtrés
    expired_products_df['Date_Expiration'] = expired_products_df['Date_Expiration'].dt.strftime('%Y-%m-%d').fillna('N/A')
    recent_movements_df['Date'] = recent_movements_df['Date'].dt.strftime('%Y-%m-%d %H:%M').fillna('N/A')

    # Obtenir le nom de l'utilisateur connecté
    logged_in_full_name = None 
    user_email = session.get('email')
    if user_email:
        admin_email_from_session = session.get('admin_email', 'default_admin@example.com')
        utils.set_dynamic_base_dir(admin_email_from_session)
        user_info = login.load_users().get(user_email)
        if user_info:
            logged_in_full_name = f"{user_info.get('prenom', '')} {user_info.get('nom', '')}".strip() or None

    return render_template_string(
        pharmacie_template,
        config=config,
        theme_vars=theme.current_theme(),
        theme_names=list(theme.THEMES.keys()),
        host_address=host_address,
        current_date=current_date_str,
        total_products=total_products,
        low_stock_alerts=low_stock_alerts,
        expired_products=expired_products_df.to_dict(orient='records'),
        recent_movements=recent_movements_df.to_dict(orient='records'),
        inventory=inventory_df.to_dict(orient='records'),
        movements_history=movements_df.to_dict(orient='records'),
        currency=currency,
        user_nom=session.get('user_nom', ''),
        user_prenom=session.get('user_prenom', ''),
        user_phone=session.get('user_phone', ''),
        logged_in_doctor_name=logged_in_full_name
    )

# --- Routes add_or_update_product, delete_product, record_movement, etc. (inchangées) ---

@pharmacie_bp.route('/add_or_update_product', methods=['POST'])
def add_or_update_product():
    if utils.EXCEL_FOLDER is None:
        if 'admin_email' in session:
            utils.set_dynamic_base_dir(session['admin_email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('pharmacie.home_pharmacie'))

    global PHARMACIE_EXCEL_FILE 

    original_product_code = request.form.get('original_product_code')
    code_produit = request.form.get('code_produit').strip()
    nom_produit = request.form.get('nom_produit').strip()
    type_produit = request.form.get('type_produit').strip()
    usage_produit = request.form.get('usage_produit').strip()
    quantite = int(request.form.get('quantite'))
    prix_achat = float(request.form.get('prix_achat') or 0.0)
    prix_vente = float(request.form.get('prix_vente') or 0.0)
    fournisseur = request.form.get('fournisseur').strip()
    date_expiration_str = request.form.get('date_expiration').strip()
    date_expiration = pd.to_datetime(date_expiration_str, errors='coerce')
    seuil_alerte = int(request.form.get('seuil_alerte'))

    inventory_df = load_pharmacie_inventory(PHARMACIE_EXCEL_FILE)
    is_new_entry = True

    if original_product_code:
        if code_produit != original_product_code:
            inventory_df = inventory_df[inventory_df['Code_Produit'] != original_product_code]
            if code_produit in inventory_df['Code_Produit'].values:
                flash(f"Erreur: Le nouveau code produit '{code_produit}' existe déjà pour un autre produit.", "danger")
                return redirect(url_for('pharmacie.home_pharmacie'))
        else:
            is_new_entry = False
            product_index = inventory_df[inventory_df['Code_Produit'] == code_produit].index
            if not product_index.empty:
                inventory_df.loc[product_index, 'Nom'] = nom_produit
                inventory_df.loc[product_index, 'Type'] = type_produit
                inventory_df.loc[product_index, 'Usage'] = usage_produit
                inventory_df.loc[product_index, 'Quantité'] = quantite
                inventory_df.loc[product_index, 'Prix_Achat'] = prix_achat
                inventory_df.loc[product_index, 'Prix_Vente'] = prix_vente
                inventory_df.loc[product_index, 'Fournisseur'] = fournisseur
                inventory_df.loc[product_index, 'Date_Expiration'] = date_expiration
                inventory_df.loc[product_index, 'Seuil_Alerte'] = seuil_alerte
            else:
                flash(f"Erreur: Produit avec le code '{code_produit}' introuvable pour modification.", "danger")
                return redirect(url_for('pharmacie.home_pharmacie'))

    if is_new_entry or (original_product_code and code_produit != original_product_code):
        if code_produit in inventory_df['Code_Produit'].values:
            flash(f"Erreur: Un produit avec le code '{code_produit}' existe déjà.", "danger")
            return redirect(url_for('pharmacie.home_pharmacie'))

        new_product_row = {
            'Code_Produit': code_produit, 'Nom': nom_produit, 'Type': type_produit, 'Usage': usage_produit,
            'Quantité': quantite, 'Prix_Achat': prix_achat, 'Prix_Vente': prix_vente, 'Fournisseur': fournisseur,
            'Date_Expiration': date_expiration, 'Seuil_Alerte': seuil_alerte,
            'Date_Enregistrement': datetime.now().strftime("%Y-%m-%d")
        }
        inventory_df = pd.concat([inventory_df, pd.DataFrame([new_product_row])], ignore_index=True)

    if save_pharmacie_inventory(inventory_df, PHARMACIE_EXCEL_FILE):
        if is_new_entry:
            try:
                depense_data = {
                    "Date": datetime.now().strftime("%Y-%m-%d"),
                    "Categorie": "Achats de consommables médicaux",
                    "Description": f"Achat de {quantite} unités de {nom_produit} (Code: {code_produit})",
                    "Montant": prix_achat * quantite,
                    "Justificatif_Fichier": ""
                }
                if _add_expense_to_comptabilite(depense_data):
                    flash(f"Dépense pour l'achat de '{nom_produit}' enregistrée dans la comptabilité.", "info")
                else:
                    flash(f"Erreur lors de l'enregistrement de la dépense pour '{nom_produit}' dans la comptabilité.", "warning")
            except Exception as e:
                flash(f"Erreur inattendue lors de l'enregistrement de la dépense comptable : {e}", "danger")
                print(f"Erreur inattendue lors de l'enregistrement de la dépense comptable : {e}")

        flash_msg = f"Produit '{nom_produit}' mis à jour avec succès !" if original_product_code else f"Produit '{nom_produit}' ajouté avec succès !"
        flash(flash_msg, "success")
    else:
        flash(f"Erreur lors de la sauvegarde du produit '{nom_produit}'.", "danger")

    return redirect(url_for('pharmacie.home_pharmacie'))

@pharmacie_bp.route('/delete_product', methods=['POST'])
def delete_product():
    if 'email' not in session: return jsonify(success=False, message="Non autorisé"), 401
    if utils.EXCEL_FOLDER is None:
        if 'email' in session: utils.set_dynamic_base_dir(session['email'])
        else: return jsonify(success=False, message="Erreur: Répertoires non définis. Reconnexion nécessaire."), 401
            
    global PHARMACIE_EXCEL_FILE 
    product_code = request.form.get('product_code').strip()
    inventory_df = load_pharmacie_inventory(PHARMACIE_EXCEL_FILE)

    if product_code not in inventory_df['Code_Produit'].values:
        return jsonify(success=False, message=f"Produit avec le code '{product_code}' introuvable."), 404

    product_name_to_delete = inventory_df[inventory_df['Code_Produit'] == product_code]['Nom'].iloc[0]
    inventory_df_filtered = inventory_df[inventory_df['Code_Produit'] != product_code].copy()

    if save_pharmacie_inventory(inventory_df_filtered, PHARMACIE_EXCEL_FILE):
        comptabilite_excel_file_path = os.path.join(utils.EXCEL_FOLDER, 'Comptabilite.xlsx')
        try:
            df_depenses = _load_comptabilite_sheet_data(comptabilite_excel_file_path, 'Depenses', _DEPENSES_COLUMNS, numeric_cols=['Montant'])
            depenses_to_delete = df_depenses['Description'].str.contains(rf"Achat de.*\(Code: {product_code}\)").fillna(False)
            df_depenses_cleaned = df_depenses[~depenses_to_delete].copy()
            if len(df_depenses_cleaned) < len(df_depenses):
                if _save_comptabilite_sheet_data(df_depenses_cleaned, comptabilite_excel_file_path, 'Depenses', _ALL_COMPTA_SHEETS):
                    print(f"Dépense(s) liée(s) au produit '{product_name_to_delete}' (Code: {product_code}) supprimée(s) avec succès de la comptabilité.")
                else:
                    print(f"ATTENTION: Échec de la suppression des dépenses liées au produit '{product_name_to_delete}' (Code: {product_code}).")
        except Exception as e:
            print(f"Erreur lors de la suppression des dépenses liées au produit '{product_code}': {e}")
            flash(f"Avertissement: Erreur lors de la mise à jour de la comptabilité: {e}", "warning")
        return jsonify(success=True, message=f"Produit '{product_name_to_delete}' et ses dépenses associées ont été supprimés avec succès.")
    else:
        return jsonify(success=False, message="Erreur lors de la suppression du produit."), 500

@pharmacie_bp.route('/record_movement', methods=['POST'])
def record_movement():
    if 'email' not in session: return redirect(url_for('login.login'))
    if utils.EXCEL_FOLDER is None:
        if 'email' in session: utils.set_dynamic_base_dir(session['email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))
            
    global PHARMACIE_EXCEL_FILE 
    product_code = request.form.get('product_code').strip()
    movement_type = request.form.get('movement_type').strip()
    quantity_movement = int(request.form.get('quantity_movement'))
    nom_responsable = request.form.get('nom_responsable', '').strip()
    prenom_responsable = request.form.get('prenom_responsable', '').strip()
    telephone_responsable = request.form.get('telephone_responsable', '').strip()

    inventory_df = load_pharmacie_inventory(PHARMACIE_EXCEL_FILE)
    if product_code not in inventory_df['Code_Produit'].values:
        flash(f"Erreur: Produit avec le code '{product_code}' introuvable.", "danger")
        return redirect(url_for('pharmacie.home_pharmacie'))

    product_index = inventory_df[inventory_df['Code_Produit'] == product_code].index[0]
    current_quantity = inventory_df.loc[product_index, 'Quantité']
    product_name = inventory_df.loc[product_index, 'Nom']

    if movement_type == 'Sortie':
        if current_quantity < quantity_movement:
            flash(f"Erreur: Quantité insuffisante pour '{product_name}'. Stock disponible: {current_quantity}", "danger")
            return redirect(url_for('pharmacie.home_pharmacie'))
        inventory_df.loc[product_index, 'Quantité'] -= quantity_movement
        flash_message = f"Sortie de {quantity_movement} unités de '{product_name}' enregistrée."
    elif movement_type == 'Entrée':
        inventory_df.loc[product_index, 'Quantité'] += quantity_movement
        flash_message = f"Entrée de {quantity_movement} unités de '{product_name}' enregistrée."
    else:
        flash("Type de mouvement invalide.", "danger")
        return redirect(url_for('pharmacie.home_pharmacie'))

    if save_pharmacie_inventory(inventory_df, PHARMACIE_EXCEL_FILE):
        movements_df = load_pharmacie_movements(PHARMACIE_EXCEL_FILE)
        new_movement = {
            'Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Code_Produit': product_code, 'Nom_Produit': product_name,
            'Type_Mouvement': movement_type, 'Quantité_Mouvement': quantity_movement, 'Nom_Responsable': nom_responsable,
            'Prenom_Responsable': prenom_responsable, 'Telephone_Responsable': telephone_responsable
        }
        movements_df = pd.concat([movements_df, pd.DataFrame([new_movement])], ignore_index=True)
        save_pharmacie_movements(movements_df, PHARMACIE_EXCEL_FILE)
        flash(flash_message, "success")
    return redirect(url_for('pharmacie.home_pharmacie'))

@pharmacie_bp.route('/export_inventory')
def export_inventory():
    if 'email' not in session: return redirect(url_for('login.login'))
    if utils.EXCEL_FOLDER is None:
        if 'email' in session: utils.set_dynamic_base_dir(session['email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))

    global PHARMACIE_EXCEL_FILE 
    inventory_df = load_pharmacie_inventory(PHARMACIE_EXCEL_FILE)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        inventory_df_for_excel = inventory_df.copy()
        if 'Date_Expiration' in inventory_df_for_excel.columns:
            inventory_df_for_excel['Date_Expiration'] = inventory_df_for_excel['Date_Expiration'].dt.strftime('%Y-%m-%d').fillna('')
        if 'Date_Enregistrement' in inventory_df_for_excel.columns:
            inventory_df_for_excel['Date_Enregistrement'] = inventory_df_for_excel['Date_Enregistrement'].dt.strftime('%Y-%m-%d').fillna('')
        inventory_df_for_excel.to_excel(writer, sheet_name='Inventaire Pharmacie', index=False)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='Inventaire_Pharmacie.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@pharmacie_bp.route('/export_movements_history')
def export_movements_history():
    if 'email' not in session: return redirect(url_for('login.login'))
    if utils.EXCEL_FOLDER is None:
        if 'email' in session: utils.set_dynamic_base_dir(session['email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))
    
    global PHARMACIE_EXCEL_FILE 
    movements_df = load_pharmacie_movements(PHARMACIE_EXCEL_FILE)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        movements_df.to_excel(writer, sheet_name='Historique Mouvements Pharmacie', index=False)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='Historique_Mouvements_Pharmacie.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@pharmacie_bp.route('/export_inventory_pdf')
def export_inventory_pdf():
    if 'email' not in session: return redirect(url_for('login.login'))
    if utils.EXCEL_FOLDER is None:
        if 'email' in session: utils.set_dynamic_base_dir(session['email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))

    global PHARMACIE_EXCEL_FILE 
    inventory_df = load_pharmacie_inventory(PHARMACIE_EXCEL_FILE)
    config = utils.load_config()
    currency = config.get('currency', 'MAD')
    pdf_output = generate_inventory_pdf(inventory_df, currency)
    return send_file(pdf_output, as_attachment=True, download_name='Inventaire_Pharmacie.pdf', mimetype='application/pdf')

@pharmacie_bp.route('/export_movements_history_pdf')
def export_movements_history_pdf():
    if 'email' not in session: return redirect(url_for('login.login'))
    if utils.EXCEL_FOLDER is None:
        if 'email' in session: utils.set_dynamic_base_dir(session['email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))

    global PHARMACIE_EXCEL_FILE 
    movements_df = load_pharmacie_movements(PHARMACIE_EXCEL_FILE)
    pdf_output = generate_movements_pdf(movements_df)
    return send_file(pdf_output, as_attachment=True, download_name='Historique_Mouvements_Pharmacie.pdf', mimetype='application/pdf')

# Définition du template HTML pour la page de gestion de la pharmacie
pharmacie_template = """
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>PHC & Gestion des stocks – {{ config.nom_clinique or 'EasyMedicaLink' }}</title>
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
            box_shadow: var(--shadow-medium);
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
        }
        /* Styles for navigation tabs */
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
            width: auto; /* Ensure it's not too wide */
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
        }
        /* Badges for status */
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
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="offcanvas"></button>
        </div>
        <div class="offcanvas-body">
            <div class="d-flex gap-2 mb-4">
                <a href="{{ url_for('login.logout') }}" class="btn btn-outline-secondary flex-fill">
                    <i class="fas fa-sign-out-alt me-2"></i>Déconnexion
                </a>
            </div>
            <form id="settingsForm" action="{{ url_for('settings') }}" method="POST">
            </form>
        </div>
    </div>

    <div class="container-fluid my-4">
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

        <div class="card shadow-lg">
            <div class="card-header py-3 text-center">
                <h1 class="mb-2 header-item">
                    <i class="fas fa-hospital me-2"></i>
                    {{ config.nom_clinique or config.cabinet or 'NOM CLINIQUE/CABINET/CENTRE MEDICAL' }}
                </h1>
                <div class="d-flex justify-content-center gap-4 flex-wrap">
                    <div class="d-flex align-items-center header-item">
                        <i class="fas fa-user me-2"></i><span>{{ logged_in_doctor_name if logged_in_doctor_name and logged_in_doctor_name != 'None' else config.doctor_name or 'NOM MEDECIN' }}</span>
                    </div>
                    <div class="d-flex align-items-center header-item">
                        <i class="fas fa-map-marker-alt me-2"></i><span>{{ config.location or 'LIEU' }}</span>
                    </div>
                </div>
                <p class="mt-2 header-item">{{ current_date }}</p>
                <p class="mt-2 header-item">
                    <i class="fas fa-prescription-bottle-alt me-2"></i>Pharmacie & Gestion des stocks
                </p>
            </div>
            <div class="card-body">
                <ul class="nav nav-tabs justify-content-center" id="pharmacieTab" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#apercu" type="button">
                            <i class="fas fa-chart-pie me-2" style="color: #4CAF50;"></i>Aperçu
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#inventaire" type="button">
                            <i class="fas fa-boxes me-2" style="color: #1E90FF;"></i>Inventaire
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#mouvements" type="button">
                            <i class="fas fa-exchange-alt me-2" style="color: #FFC107;"></i>Mouvements
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#ajouter-produit" type="button">
                            <i class="fas fa-plus-circle me-2" style="color: #32CD32;"></i>Ajouter/Modifier Produit
                        </button>
                    </li>
                </ul>

                <div class="tab-content mt-3">
                    <div class="tab-pane fade show active" id="apercu" role="tabpanel">
                        <div class="row row-cols-1 row-cols-md-2 g-3 text-center mb-4">
                            <div class="col"><div class="card h-100 p-3"><div class="fs-4 fw-bold text-primary">{{ total_products }}</div><small class="text-muted">Total Produits</small></div></div>
                            <div class="col"><div class="card h-100 p-3"><div class="fs-4 fw-bold text-warning">{{ low_stock_alerts|length }}</div><small class="text-muted">Alertes Stock Bas</small></div></div>
                        </div>

                        {% if low_stock_alerts %}
                        <h5 class="text-warning mt-4"><i class="fas fa-bell me-2"></i>Produits en Stock Bas</h5>
                        <div class="table-responsive"><table class="table table-sm table-hover"><thead><tr><th>Nom</th><th>Qté</th><th>Seuil</th></tr></thead><tbody>
                        {% for product in low_stock_alerts %}<tr><td>{{ product.Nom }}</td><td>{{ product.Quantité }}</td><td>{{ product.Seuil_Alerte }}</td></tr>{% endfor %}
                        </tbody></table></div>
                        {% endif %}
                        
                        {% if expired_products %}
                        <h5 class="text-danger mt-4"><i class="fas fa-calendar-times me-2"></i>Produits Expirés</h5>
                        <div class="table-responsive"><table class="table table-sm table-hover"><thead><tr><th>Nom</th><th>Code</th><th>Date Exp.</th><th>Qté</th></tr></thead><tbody>
                        {% for product in expired_products %}<tr class="table-danger"><td>{{ product.Nom }}</td><td>{{ product.Code_Produit }}</td><td>{{ product.Date_Expiration }}</td><td>{{ product.Quantité }}</td></tr>{% endfor %}
                        </tbody></table></div>
                        {% endif %}

                        {% if recent_movements %}
                        <h5 class="mt-4"><i class="fas fa-history me-2"></i>Derniers Mouvements</h5>
                        <div class="table-responsive"><table class="table table-sm table-hover"><thead><tr><th>Date</th><th>Nom</th><th>Type</th><th>Qté</th><th>Responsable</th></tr></thead><tbody>
                        {% for m in recent_movements %}<tr><td>{{ m.Date }}</td><td>{{ m.Nom_Produit }}</td><td><span class="badge {% if m.Type_Mouvement == 'Entrée' %}bg-success{% else %}bg-danger{% endif %}">{{ m.Type_Mouvement }}</span></td><td>{{ m.Quantité_Mouvement }}</td><td>{{ m.Prenom_Responsable }} {{ m.Nom_Responsable }}</td></tr>{% endfor %}
                        </tbody></table></div>
                        {% endif %}
                    </div>

                    <div class="tab-pane fade" id="inventaire" role="tabpanel">
                        <div class="d-flex justify-content-end mb-3">
                             <button class="btn btn-outline-secondary" onclick="exportInventoryPdf()"><i class="fas fa-file-pdf me-2"></i>Exporter PDF</button>
                             <button class="btn btn-outline-secondary ms-2" onclick="exportInventoryExcel()"><i class="fas fa-file-excel me-2"></i>Exporter Excel</button>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-striped table-hover" id="inventoryTable">
                                <thead><tr><th>Code</th><th>Nom</th><th>Qté</th><th>Prix Vte</th><th>Date Exp.</th><th>Statut</th><th>Actions</th></tr></thead>
                                <tbody>
                                {% for p in inventory %}
                                <tr>
                                    <td>{{ p.Code_Produit }}</td><td>{{ p.Nom }}</td><td>{{ p.Quantité }}</td><td>{{ "%.2f"|format(p.Prix_Vente) }} {{ currency }}</td><td>{{ p.Date_Expiration }}</td>
                                    <td>
                                        {% if p.Quantité == 0 %}<span class="badge bg-danger">Rupture</span>
                                        {% elif p.Quantité <= p.Seuil_Alerte %}<span class="badge bg-warning text-dark">Stock Bas</span>
                                        {% else %}<span class="badge bg-success">En Stock</span>{% endif %}
                                    </td>
                                    <td>
                                        <button class="btn btn-sm btn-info edit-product-btn" data-product='{{ p | tojson | forceescape }}'><i class="fas fa-edit"></i></button>
                                        <button class="btn btn-sm btn-danger delete-product-btn" data-id="{{ p.Code_Produit }}"><i class="fas fa-trash"></i></button>
                                    </td>
                                </tr>
                                {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>                   

                    <div class="tab-pane fade" id="mouvements" role="tabpanel">
                        <h4 class="text-primary mb-3">Enregistrer un Mouvement</h4>
                        <form action="{{ url_for('pharmacie.record_movement') }}" method="POST">
                            <div class="row g-3">
                                <div class="col-md-6 floating-label"><select class="form-select" name="product_code" required placeholder=" ">{% for p in inventory %}<option value="{{ p.Code_Produit }}">{{ p.Nom }} (Stock: {{ p.Quantité }})</option>{% endfor %}</select><label>Produit</label></div>
                                <div class="col-md-6 floating-label"><select class="form-select" name="movement_type" required placeholder=" "><option value="Entrée">Entrée</option><option value="Sortie">Sortie</option></select><label>Type</label></div>
                                <div class="col-12 floating-label"><input type="number" class="form-control" name="quantity_movement" min="1" required placeholder=" "><label>Quantité</label></div>
                                <div class="col-md-4 floating-label"><input type="text" class="form-control" name="nom_responsable" value="{{ user_nom }}" required placeholder=" "><label>Nom Resp.</label></div>
                                <div class="col-md-4 floating-label"><input type="text" class="form-control" name="prenom_responsable" value="{{ user_prenom }}" required placeholder=" "><label>Prénom Resp.</label></div>
                                <div class="col-md-4 floating-label"><input type="tel" class="form-control" name="telephone_responsable" value="{{ user_phone }}" placeholder=" "><label>Téléphone</label></div>
                                <div class="col-12 text-center"><button type="submit" class="btn btn-primary"><i class="fas fa-save me-2"></i>Enregistrer</button></div>
                            </div>
                        </form>
                        <hr>
                        <div class="d-flex justify-content-end mb-3">
                            <button class="btn btn-outline-secondary" onclick="exportMovementsHistoryPdf()"><i class="fas fa-file-pdf me-2"></i>Exporter PDF</button>
                            <button class="btn btn-outline-secondary ms-2" onclick="exportMovementsHistoryExcel()"><i class="fas fa-file-excel me-2"></i>Exporter Excel</button>
                        </div>
                        <div class="table-responsive mt-4">
                             <table class="table table-striped table-hover" id="movementsHistoryTable">
                                <thead><tr><th>Date</th><th>Nom</th><th>Type</th><th>Qté</th><th>Responsable</th></tr></thead>
                                <tbody>
                                {% for m in movements_history %}
                                <tr><td>{{ m.Date }}</td><td>{{ m.Nom_Produit }}</td><td><span class="badge {% if m.Type_Mouvement == 'Entrée' %}bg-success{% else %}bg-danger{% endif %}">{{ m.Type_Mouvement }}</span></td><td>{{ m.Quantité_Mouvement }}</td><td>{{ m.Prenom_Responsable }} {{ m.Nom_Responsable }}</td></tr>
                                {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div class="tab-pane fade" id="ajouter-produit" role="tabpanel">
                        <h4 class="text-primary mb-3" id="productFormTitle">Ajouter un Produit</h4>
                        <form id="productForm" action="{{ url_for('pharmacie.add_or_update_product') }}" method="POST">
                            <input type="hidden" name="original_product_code" id="original_product_code">
                            <div class="row g-3">
                                <div class="col-md-6 floating-label"><input type="text" class="form-control" name="code_produit" id="code_produit" required placeholder=" "><label for="code_produit">Code Produit</label></div>
                                <div class="col-md-6 floating-label"><input type="text" class="form-control" name="nom_produit" id="nom_produit" required placeholder=" "><label for="nom_produit">Nom du Produit</label></div>
                                <div class="col-md-6 floating-label"><select class="form-select" name="type_produit" id="type_produit" required placeholder=" "><option value="" disabled selected>Choisir...</option><option>Dispositifs médicaux</option><option>Mobilier médical</option><option>Matériel de diagnostic</option><option>Consommables médicaux</option></select><label for="type_produit">Type</label></div>
                                <div class="col-md-6 floating-label"><select class="form-select" name="usage_produit" id="usage_produit" required placeholder=" "><option value="Usage Interne">Usage Interne</option><option value="Vente">Vente</option></select><label for="usage_produit">Usage</label></div>
                                <div class="col-md-6 floating-label"><input type="number" class="form-control" name="quantite" id="quantite" min="0" required placeholder=" "><label for="quantite">Quantité</label></div>
                                <div class="col-md-6 floating-label"><input type="number" class="form-control" name="prix_achat" id="prix_achat" step="0.01" min="0" placeholder=" "><label for="prix_achat">Prix d'Achat ({{ currency }})</label></div>
                                <div class="col-md-6 floating-label"><input type="number" class="form-control" name="prix_vente" id="prix_vente" step="0.01" min="0" placeholder=" "><label for="prix_vente">Prix de Vente ({{ currency }})</label></div>
                                <div class="col-md-6 floating-label"><input type="text" class="form-control" name="fournisseur" id="fournisseur" placeholder=" "><label for="fournisseur">Fournisseur</label></div>
                                <div class="col-md-6 floating-label"><input type="date" class="form-control" name="date_expiration" id="date_expiration" placeholder=" "><label for="date_expiration">Date d'Expiration</label></div>
                                <div class="col-md-6 floating-label"><input type="number" class="form-control" name="seuil_alerte" id="seuil_alerte" min="0" required placeholder=" "><label for="seuil_alerte">Seuil d'Alerte</label></div>
                                <div class="col-12 text-center d-flex gap-2 justify-content-center">
                                    <button type="submit" id="productFormSubmitBtn" class="btn btn-primary"><i class="fas fa-plus me-2"></i>Ajouter Produit</button>
                                    <button type="button" id="cancelEditBtn" class="btn btn-outline-secondary" style="display: none;"><i class="fas fa-times me-2"></i>Annuler</button>
                                </div>
                            </div>
                        </form>
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

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.1/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.1/js/dataTables.bootstrap5.min.js"></script>
    <script>
    document.addEventListener('DOMContentLoaded', () => {
        // Tab persistence logic
        const tabButtons = document.querySelectorAll('#pharmacieTab button[data-bs-toggle="tab"]');
        const storedActiveTab = localStorage.getItem('activePharmacieTab');
        const defaultTabButton = document.querySelector('#pharmacieTab button[data-bs-target="#apercu"]');
        let initialTabToActivate = defaultTabButton;

        if (storedActiveTab) {
            const storedTabButton = document.querySelector(`#pharmacieTab button[data-bs-target="${storedActiveTab}"]`);
            if (storedTabButton) {
                initialTabToActivate = storedTabButton;
            }
        }
        
        const initialTabInstance = new bootstrap.Tab(initialTabToActivate);
        initialTabInstance.show();

        tabButtons.forEach(tabEl => {
            tabEl.addEventListener('shown.bs.tab', e => {
                const activatedTabTarget = e.target.getAttribute('data-bs-target');
                localStorage.setItem('activePharmacieTab', activatedTabTarget);
                $.fn.DataTable.tables({ visible: true, api: true }).columns.adjust();
            });
        });

        // Initialize DataTables
        ['#inventoryTable', '#movementsHistoryTable'].forEach(tableId => {
            if ($.fn.DataTable.isDataTable(tableId)) {
                $(tableId).DataTable().destroy();
            }
            $(tableId).DataTable({
                "language": { "url": "//cdn.datatables.net/plug-ins/1.13.1/i18n/fr-FR.json" },
                "paging": true, "searching": true, "info": true,
                "order": [[0, 'desc']]
            });
        });
        
        // Edit product logic
        const form = document.getElementById('productForm');
        const title = document.getElementById('productFormTitle');
        const submitBtn = document.getElementById('productFormSubmitBtn');
        const cancelBtn = document.getElementById('cancelEditBtn');
        const addProductTab = new bootstrap.Tab(document.querySelector('button[data-bs-target="#ajouter-produit"]'));

        document.querySelectorAll('.edit-product-btn').forEach(button => {
            button.addEventListener('click', function() {
                const productData = JSON.parse(this.getAttribute('data-product').replace(/&quot;/g, '"'));
                
                title.textContent = 'Modifier le Produit';
                submitBtn.innerHTML = '<i class="fas fa-save me-2"></i>Enregistrer Modifications';
                cancelBtn.style.display = 'inline-flex';
                
                form.querySelector('#original_product_code').value = productData.Code_Produit;
                form.querySelector('#code_produit').value = productData.Code_Produit;
                form.querySelector('#nom_produit').value = productData.Nom;
                form.querySelector('#type_produit').value = productData.Type;
                form.querySelector('#usage_produit').value = productData.Usage;
                form.querySelector('#quantite').value = productData.Quantité;
                form.querySelector('#prix_achat').value = productData.Prix_Achat;
                form.querySelector('#prix_vente').value = productData.Prix_Vente;
                form.querySelector('#fournisseur').value = productData.Fournisseur;
                form.querySelector('#date_expiration').value = productData.Date_Expiration.startsWith('N/A') ? '' : productData.Date_Expiration.split(' ')[0];
                form.querySelector('#seuil_alerte').value = productData.Seuil_Alerte;

                addProductTab.show();
                window.scrollTo(0, 0); // Scroll to top to see the form
            });
        });

        cancelBtn.addEventListener('click', function() {
            title.textContent = 'Ajouter un Produit';
            submitBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Ajouter Produit';
            cancelBtn.style.display = 'none';
            form.reset();
            form.querySelector('#original_product_code').value = '';
        });

        // Delete product confirmation
        $('#inventoryTable tbody').on('click', '.delete-product-btn', function(e) {
            e.preventDefault();
            const productCode = $(this).data('id');
            Swal.fire({
                title: 'Êtes-vous sûr ?', text: "Cette action est irréversible !", icon: 'warning',
                showCancelButton: true, confirmButtonColor: '#d33', cancelButtonColor: '#3085d6',
                confirmButtonText: 'Oui, supprimer !', cancelButtonText: 'Annuler'
            }).then((result) => {
                if (result.isConfirmed) {
                    fetch(`{{ url_for('pharmacie.delete_product') }}`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: `product_code=${encodeURIComponent(productCode)}`
                    })
                    .then(res => res.json())
                    .then(data => {
                        if(data.success) {
                            Swal.fire('Supprimé !', data.message, 'success').then(() => location.reload());
                        } else {
                            Swal.fire('Erreur', data.message, 'error');
                        }
                    })
                    .catch(err => Swal.fire('Erreur', 'Une erreur de communication est survenue.', 'error'));
                }
            });
        });
    });
    function exportInventoryPdf() { window.location.href = "{{ url_for('pharmacie.export_inventory_pdf') }}"; }
    function exportInventoryExcel() { window.location.href = "{{ url_for('pharmacie.export_inventory') }}"; }
    function exportMovementsHistoryPdf() { window.location.href = "{{ url_for('pharmacie.export_movements_history_pdf') }}"; }
    function exportMovementsHistoryExcel() { window.location.href = "{{ url_for('pharmacie.export_movements_history') }}"; }
    </script>
    {% include '_floating_assistant.html' %} 
</body>
</html>
"""