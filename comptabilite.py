# comptabilite.py
# Module pour la gestion de la comptabilité de la clinique
# Intègre un tableau de bord, la gestion des recettes, dépenses, salaires,
# un aperçu des stocks médicaux, et le suivi des tiers payants et documents fiscaux.
# Interactions avec facturation.py et pharmacie.py.

from flask import Blueprint, render_template_string, session, redirect, url_for, flash, request, jsonify, send_file
from datetime import datetime, date, timedelta
import utils
import theme
import pandas as pd
import os
import io
from fpdf import FPDF # Pour la génération de PDF (fiches de paie)
import json # Pour gérer les listes de catégories
from PIL import Image # Pour la gestion de l'image de fond si utile pour l'aperçu, bien que FPDF gère directement les images
import login

# Import des fonctions spécifiques de pharmacie et facturation pour lire les données
# On importe directement les fonctions pour charger les DataFrames pour éviter les dépendances circulaires
# ou les appels HTTP inter-Blueprints pour des données déjà stockées localement.
# NOTE: The imports are kept as per user instruction "sans besoin de modifier facturation.py et pharmarcie.py"
# but leur usage within home_comptabilite is removed.
try:
    from pharmacie import load_pharmacie_inventory, load_pharmacie_movements
    PHARMACIE_MODULE_AVAILABLE = True
except ImportError:
    PHARMACIE_MODULE_AVAILABLE = False
    print("AVERTISSEMENT: Module 'pharmacie' non trouvé. La section Stocks Médicaux sera limitée.")
    def load_pharmacie_inventory(file_path): return pd.DataFrame()
    def load_pharmacie_movements(file_path): return pd.DataFrame()

try:
    from facturation import load_invoices as load_all_invoices, generate_report_summary as get_invoice_summary
    FACTURATION_MODULE_AVAILABLE = True
except ImportError:
    FACTURATION_MODULE_AVAILABLE = False
    print("AVERTISSEMENT: Module 'facturation' non trouvé. La section Factures sera limitée.")
    def load_all_invoices(): return []
    def get_invoice_summary(): return {'count': 0, 'total_ht': 0.0, 'total_tva': 0.0, 'total_ttc': 0.0, 'currency': 'EUR'}


comptabilite_bp = Blueprint('comptabilite', __name__, url_prefix='/comptabilite')

# --- Constantes et Chemins ---
# Fichier Excel principal pour la comptabilité
COMPTABILITE_EXCEL_FILE: str = "" # Sera défini dynamiquement

# Noms des feuilles Excel attendues dans Comptabilite.xlsx
ALL_COMPTA_SHEETS = ['Recettes', 'Depenses', 'Salaires', 'TiersPayants', 'DocumentsFiscaux']

# Catégories par défaut pour les dépenses
DEFAULT_EXPENSE_CATEGORIES = [
    "Loyers & Charges locatives", "Salaires & Rémunérations", "Charges sociales",
    "Fournitures de bureau", "Achats de consommables médicaux", "Achats de médicaments",
    "Maintenance & Réparations", "Électricité & Eau", "Téléphone & Internet",
    "Assurances", "Frais bancaires", "Publicité & Marketing", "Frais de déplacement",
    "Formations professionnelles", "Impôts & Taxes", "Amortissements", "Autres"
]

# Catégories par défaut pour les types de documents fiscaux
DEFAULT_FISCAL_DOCUMENT_TYPES = [
    "Déclaration TVA", "Déclaration IR (Impôt sur le Revenu)", "Déclaration IS (Impôt sur les Sociétés)",
    "Bilan Comptable Annuel", "Compte de Résultat", "Grand Livre", "Balance Générale",
    "Déclaration CNSS", "Attestation Fiscale", "Contrat de Travail", "Facture Fournisseur",
    "Reçu de Caisse", "Bordereau de Versement", "Quittance de Loyer", "Justificatif de Dépense",
    "Autre Document Fiscal"
]


# --- Fonctions utilitaires pour charger/sauvegarder les feuilles Excel ---
def _load_sheet_data(file_path, sheet_name, default_columns, numeric_cols=[]):
    """
    Charge les données d'une feuille spécifique d'un fichier Excel.
    Initialise la feuille avec les colonnes par défaut si elle n'existe pas ou est vide.
    """
    # Assurez-vous que le répertoire existe
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

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
                    # Convertir en numérique, en forçant les erreurs à NaN, puis remplir NaN avec 0
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    if col in ['Montant', 'Salaire_Net', 'Charges_Sociales', 'Total_Brut', 'Montant_Attendu', 'Montant_Recu']:
                         # Convertir en float pour les montants, sans les rendre des entiers
                        df[col] = df[col].astype(float)
            return df
        except Exception as e:
            print(f"Erreur lors du chargement de la feuille '{sheet_name}' de {file_path}: {e}")
            # Retourne un DataFrame vide avec les colonnes par défaut et des zéros pour les colonnes numériques
            empty_df = pd.DataFrame(columns=default_columns)
            for col in numeric_cols:
                empty_df[col] = 0.0
            return empty_df
    # Retourne un DataFrame vide avec les colonnes par défaut si le fichier n'existe pas
    empty_df = pd.DataFrame(columns=default_columns)
    for col in numeric_cols:
        empty_df[col] = 0.0
    return empty_df

def _save_sheet_data(df_to_save, file_path, sheet_name, all_sheet_names):
    """
    Sauvegarde un DataFrame dans une feuille spécifique d'un fichier Excel,
    en préservant les autres feuilles.
    """
    try:
        existing_sheets_data = {}
        if os.path.exists(file_path):
            existing_sheets_data = pd.read_excel(file_path, sheet_name=None, dtype=str)
        
        existing_sheets_data[sheet_name] = df_to_save

        with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
            for s_name in all_sheet_names:
                if s_name in existing_sheets_data and not existing_sheets_data[s_name].empty:
                    existing_sheets_data[s_name].to_excel(writer, sheet_name=s_name, index=False)
                else: # Si une feuille est vide ou n'existe pas encore, la créer avec les colonnes par défaut
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
        print(f"Erreur lors de la sauvegarde de la feuille '{sheet_name}' vers {file_path}: {e}")
        flash(f"Erreur lors de la sauvegarde des données de {sheet_name}: {e}", "danger")
        return False

# --- Initialisation dynamique du chemin des fichiers Excel ---
@comptabilite_bp.before_request
def set_compta_paths():
    global COMPTABILITE_EXCEL_FILE
    if utils.EXCEL_FOLDER is None:
        # Fallback si le répertoire n'est pas encore défini (ex: accès direct à la route)
        admin_email = session.get('admin_email', 'default_admin@example.com')
        utils.set_dynamic_base_dir(admin_email)
    
    COMPTABILITE_EXCEL_FILE = os.path.join(utils.EXCEL_FOLDER, 'Comptabilite.xlsx')
    print(f"DEBUG: Chemin Comptabilite.xlsx défini à : {COMPTABILITE_EXCEL_FILE}")


# --- Fonctions pour les opérations CRUD (Recettes, Dépenses, Salaires, TiersPayants, Docs Fiscaux) ---

# Recettes
def load_recettes():
    cols = ['Date', 'Type_Acte', 'Patient_ID', 'Patient_Nom', 'Patient_Prenom', 'Montant', 'Mode_Paiement', 'Description', 'ID_Facture_Liee']
    numeric_cols = ['Montant']
    return _load_sheet_data(COMPTABILITE_EXCEL_FILE, 'Recettes', cols, numeric_cols)

def save_recettes(df):
    return _save_sheet_data(df, COMPTABILITE_EXCEL_FILE, 'Recettes', ALL_COMPTA_SHEETS)

# Dépenses
def load_depenses():
    cols = ['Date', 'Categorie', 'Description', 'Montant', 'Justificatif_Fichier']
    numeric_cols = ['Montant']
    return _load_sheet_data(COMPTABILITE_EXCEL_FILE, 'Depenses', cols, numeric_cols)

def save_depenses(df):
    return _save_sheet_data(df, COMPTABILITE_EXCEL_FILE, 'Depenses', ALL_COMPTA_SHEETS)

# Salaires
def load_salaires():
    cols = ['Mois_Annee', 'Nom_Employe', 'Prenom_Employe', 'Salaire_Net', 'Charges_Sociales', 'Total_Brut', 'Fiche_Paie_PDF']
    numeric_cols = ['Salaire_Net', 'Charges_Sociales', 'Total_Brut']
    return _load_sheet_data(COMPTABILITE_EXCEL_FILE, 'Salaires', cols, numeric_cols)

def save_salaires(df):
    return _save_sheet_data(df, COMPTABILITE_EXCEL_FILE, 'Salaires', ALL_COMPTA_SHEETS)

# Tiers Payants
def load_tiers_payants():
    cols = ['Date', 'Assureur', 'Patient_ID', 'Patient_Nom', 'Patient_Prenom', 'Montant_Attendu', 'Montant_Recu', 'Date_Reglement', 'ID_Facture_Liee', 'Statut']
    numeric_cols = ['Montant_Attendu', 'Montant_Recu']
    return _load_sheet_data(COMPTABILITE_EXCEL_FILE, 'TiersPayants', cols, numeric_cols)

def save_tiers_payants(df):
    return _save_sheet_data(df, COMPTABILITE_EXCEL_FILE, 'TiersPayants', ALL_COMPTA_SHEETS)

# Documents Fiscaux
def load_documents_fiscaux():
    cols = ['Date', 'Type_Document', 'Description', 'Fichier_PDF']
    return _load_sheet_data(COMPTABILITE_EXCEL_FILE, 'DocumentsFiscaux', cols)

def save_documents_fiscaux(df):
    return _save_sheet_data(df, COMPTABILITE_EXCEL_FILE, 'DocumentsFiscaux', ALL_COMPTA_SHEETS)


# --- Classes pour la génération de PDF (Fiche de Paie) ---
class PayslipPDF(FPDF):
    def __init__(self, app_config, emp_data, currency="MAD"):
        super().__init__(orientation='P', unit='mm', format='A5')  # Format A5
        self.app_config = app_config  # Configuration de l'application (nom clinique, adresse, etc.)
        self.emp_data = emp_data      # Dictionnaire avec toutes les données de l'employé
        self.currency = currency
        self.set_left_margin(10)  # Marges plus petites pour A5
        self.set_right_margin(10)
        self.set_top_margin(35)
        self.set_auto_page_break(auto=True, margin=10) # Marge inférieure également réduite
        self.add_page()

    def header(self):
        # Arrière-plan
        bg_file = utils.background_file
        if bg_file and os.path.isfile(bg_file) and bg_file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            try:
                self.image(bg_file, x=0, y=0, w=self.w, h=self.h)
            except Exception as e:
                print(f"Erreur lors de l'insertion de l'image de fond pour la fiche de paie: {e}")
        
        # Positionnement initial pour le contenu de l'en-tête, en tenant compte des marges
        current_y = self.t_margin # Commence à la marge supérieure

        self.set_font('Helvetica', 'B', 18) # Police plus petite pour A5
        self.set_text_color(20, 60, 100)  # Bleu foncé
        # Centrer le titre principal "FICHE DE PAIE"
        self.set_xy(self.l_margin, current_y)
        self.cell(self.w - self.l_margin - self.r_margin, 8, 'FICHE DE PAIE', 0, 1, 'C')
        current_y += 8 # Avance la position Y
        self.ln(3) # Espace après le titre

        # Informations de l'entreprise (gauche)
        info_block_y = current_y + 5 # Légèrement en dessous du titre

        self.set_font('Helvetica', 'B', 9) # Police plus petite pour A5
        self.set_text_color(0, 0, 0) # Noir

        nom_clinique = self.app_config.get('nom_clinique', 'Nom de la Clinique')
        cabinet = self.app_config.get('cabinet', 'Cabinet Médical')
        location = self.app_config.get('location', 'Adresse de la Clinique')

        company_info_text = f"{nom_clinique}\n{cabinet}\n{location}" # Suppression téléphone et email
        
        self.set_xy(self.l_margin, info_block_y)
        self.multi_cell((self.w / 2) - self.l_margin - 2, 4, company_info_text, 0, 'L') # Ajustement de la largeur pour A5
        
        # Date d'édition (droite)
        self.set_xy(self.w - self.r_margin - 60, info_block_y + 3) # 60mm de largeur pour la cellule de date
        self.set_font('Helvetica', '', 8) # Police plus petite pour A5
        self.cell(60, 5, f"Date d'édition : {datetime.now().strftime('%d/%m/%Y')}", 0, 1, 'R')
        
        # Mettre à jour la position Y globale après l'en-tête complet
        # Estimer la hauteur du bloc info (3 lignes * 4mm/ligne) + espace
        self.set_y(max(self.get_y(), info_block_y + (3 * 4) + 5))
        self.ln(10) # Espace avant le début du corps pour la clarté

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 6) # Police plus petite pour A5
        self.set_text_color(100, 100, 100) # Gris
        self.cell(0, 3, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

    def chapter_body(self):
        self.set_text_color(0, 0, 0) # Noir pour le corps
        
        # Largeur disponible pour le contenu principal (entre les marges)
        content_width = self.w - self.l_margin - self.r_margin

        # Section Informations de l'Employé
        self.set_fill_color(220, 230, 240) # Bleu très clair
        self.set_font('Helvetica', 'B', 10) # Police plus petite pour A5
        self.set_x(self.l_margin) # Positionne X à la marge gauche
        self.cell(content_width, 6, 'INFORMATIONS DE L\'EMPLOYÉ', 1, 1, 'C', True) # Hauteur de cellule réduite
        
        self.set_font('Helvetica', '', 9) # Police plus petite pour A5
        self.set_x(self.l_margin)
        self.cell(content_width / 2, 6, 'Nom et Prénom:', 'LR', 0, 'L')
        self.cell(content_width / 2, 6, f"{self.emp_data['Nom_Employe']} {self.emp_data['Prenom_Employe']}", 'R', 1, 'L')
        
        self.set_x(self.l_margin)
        self.cell(content_width / 2, 6, 'Mois de Paie:', 'LRB', 0, 'L')
        self.cell(content_width / 2, 6, self.emp_data['Mois_Annee'], 'RB', 1, 'L')
        self.ln(7) # Espace réduit

        # Section Détails de la Rémunération
        self.set_fill_color(220, 230, 240) # Bleu très clair
        self.set_font('Helvetica', 'B', 10) # Police plus petite pour A5
        self.set_x(self.l_margin)
        self.cell(content_width, 6, 'DÉTAILS DE LA RÉMUNÉRATION', 1, 1, 'C', True) # Hauteur de cellule réduite
        
        # Entêtes du tableau de rémunération
        self.set_font('Helvetica', 'B', 9) # Police plus petite pour A5
        self.set_fill_color(240, 240, 240) # Gris clair
        col1_width = content_width * 0.55 # 55% de la largeur pour le libellé
        col2_width = content_width * 0.225 # 22.5% pour Gains
        col3_width = content_width * 0.225 # 22.5% pour Retenues

        self.set_x(self.l_margin)
        self.cell(col1_width, 6, 'Libellé', 1, 0, 'L', True) # Hauteur de cellule réduite
        self.cell(col2_width, 6, 'Gains (' + self.currency + ')', 1, 0, 'R', True) # Hauteur de cellule réduite
        self.cell(col3_width, 6, 'Retenues (' + self.currency + ')', 1, 1, 'R', True) # Hauteur de cellule réduite
        
        self.set_font('Helvetica', '', 9) # Police plus petite pour A5
        
        # Salaire Brut (Gains)
        self.set_x(self.l_margin)
        self.cell(col1_width, 6, 'Salaire de base', 'LR', 0, 'L') # Hauteur de cellule réduite
        self.cell(col2_width, 6, f"{self.emp_data['Total_Brut']:.2f}", 'R', 0, 'R') # Hauteur de cellule réduite
        self.cell(col3_width, 6, '', 'R', 1, 'R') # Hauteur de cellule réduite

        # Charges Sociales (Retenues)
        self.set_x(self.l_margin)
        self.cell(col1_width, 6, 'Cotisations sociales', 'LR', 0, 'L') # Hauteur de cellule réduite
        self.cell(col2_width, 6, '', 'R', 0, 'R') # Hauteur de cellule réduite
        self.cell(col3_width, 6, f"{self.emp_data['Charges_Sociales']:.2f}", 'R', 1, 'R') # Hauteur de cellule réduite

        # Ajout de lignes vides pour la consistance visuelle du tableau
        # Diminué de 3 lignes par rapport à la version précédente (maintenant 0 lignes vides explicitement ajoutées)
        for _ in range(0): 
            self.set_x(self.l_margin)
            self.cell(col1_width, 6, '', 'LR', 0, 'L') # Hauteur de cellule réduite
            self.cell(col2_width, 6, '', 'R', 0, 'R') # Hauteur de cellule réduite
            self.cell(col3_width, 6, '', 'R', 1, 'R') # Hauteur de cellule réduite
        
        # Fermeture du tableau avec une ligne de fond
        self.set_x(self.l_margin)
        self.cell(col1_width, 6, '', 'LBR', 0, 'L') # Hauteur de cellule réduite
        self.cell(col2_width, 6, '', 'BR', 0, 'R') # Hauteur de cellule réduite
        self.cell(col3_width, 6, '', 'BR', 1, 'R') # Hauteur de cellule réduite

        self.ln(7) # Espace réduit
        
        # Totaux
        self.set_font('Helvetica', 'B', 10) # Police plus petite pour A5
        
        # TOTAL BRUT
        self.set_fill_color(200, 220, 240) # Bleu moyen
        self.set_x(self.l_margin)
        self.cell(content_width * 0.55, 7, 'TOTAL BRUT', 1, 0, 'L', True) # Hauteur de cellule réduite
        self.cell(content_width * 0.45, 7, f"{self.emp_data['Total_Brut']:.2f} {self.currency}", 1, 1, 'R', True) # Hauteur de cellule réduite

        # TOTAL RETENUES
        self.set_fill_color(240, 200, 200) # Rouge clair
        self.set_x(self.l_margin)
        self.cell(content_width * 0.55, 7, 'TOTAL RETENUES', 1, 0, 'L', True) # Hauteur de cellule réduite
        self.cell(content_width * 0.45, 7, f"{self.emp_data['Charges_Sociales']:.2f}", 'R', 1, 'R') # Hauteur de cellule réduite
        
        # NET À PAYER
        self.set_fill_color(180, 250, 180) # Vert clair
        self.set_font('Helvetica', 'B', 12) # Police plus petite pour A5
        self.set_x(self.l_margin)
        self.cell(content_width * 0.55, 10, 'NET À PAYER', 1, 0, 'L', True) # Hauteur de cellule réduite
        self.cell(content_width * 0.45, 10, f"{self.emp_data['Salaire_Net']:.2f} {self.currency}", 1, 1, 'R', True) # Hauteur de cellule réduite
        
        self.ln(10) # Espace réduit

        # Mentions légales et signature
        self.set_font('Helvetica', 'I', 8) # Police plus petite pour A5
        self.set_x(self.l_margin) # Positionne X à la marge gauche
        # Utilisez multi_cell pour les mentions légales pour qu'elles s'adaptent à la largeur
        self.multi_cell(content_width, 3, 'Conformément à la législation en vigueur, cette fiche de paie est un document justificatif de rémunération. En cas de désaccord, veuillez contacter le service de gestion du personnel dans les plus brefs délais.', 0, 'C')
        self.ln(5) # Espace réduit
        
        self.set_font('Helvetica', 'B', 9) # Police plus petite pour A5
        self.set_x(self.l_margin) # Positionne X à la marge gauche
        # Positionne la signature à droite de la zone de contenu
        self.cell(content_width, 5, 'Cachet et Signature de l\'Employeur', 0, 1, 'R')


# --- Routes du Blueprint ---
@comptabilite_bp.route('/')
def home_comptabilite():
    if 'email' not in session:
        return redirect(url_for('login.login'))
    
    config = utils.load_config()
    session['theme'] = config.get('theme', theme.DEFAULT_THEME)
    currency = config.get('currency', 'MAD')
    
    host_address = f"http://{utils.LOCAL_IP}:3000"
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Récupérer le mois sélectionné depuis la requête (si présent)
    selected_month_str = request.args.get('selected_month')
    selected_year = None
    selected_month_num = None

    if selected_month_str:
        try:
            selected_date_obj = datetime.strptime(selected_month_str, '%Y-%m')
            selected_year = selected_date_obj.year
            selected_month_num = selected_date_obj.month
        except ValueError:
            flash("Format de mois invalide. Utilisez AAAA-MM.", "danger")
            selected_month_str = None

    # --- Initialisation des données pour les onglets ---
    recettes_df = load_recettes()
    depenses_df = load_depenses()
    salaires_df = load_salaires()
    tiers_payants_df = load_tiers_payants()
    documents_fiscaux_df = load_documents_fiscaux()

    # Ensure parsed date columns exist immediately after loading original DFs
    if not recettes_df.empty and 'Date' in recettes_df.columns:
        recettes_df['Date_Parsed'] = pd.to_datetime(recettes_df['Date'], errors='coerce')
    else:
        recettes_df['Date_Parsed'] = pd.Series(dtype='datetime64[ns]')

    if not depenses_df.empty and 'Date' in depenses_df.columns:
        depenses_df['Date_Parsed'] = pd.to_datetime(depenses_df['Date'], errors='coerce')
    else:
        depenses_df['Date_Parsed'] = pd.Series(dtype='datetime64[ns]')

    if not salaires_df.empty and 'Mois_Annee' in salaires_df.columns:
        salaires_df['Mois_Annee_Parsed'] = pd.to_datetime(salaires_df['Mois_Annee'], format='%Y-%m', errors='coerce')
    else:
        salaires_df['Mois_Annee_Parsed'] = pd.Series(dtype='datetime64[ns]')

    # Add Date_Parsed for tiers_payants_df
    if not tiers_payants_df.empty and 'Date_Reglement' in tiers_payants_df.columns:
        tiers_payants_df['Date_Parsed'] = pd.to_datetime(tiers_payants_df['Date_Reglement'], errors='coerce')
    else:
        tiers_payants_df['Date_Parsed'] = pd.Series(dtype='datetime64[ns]')


    # Apply month filter to DataFrames for KPIs and pie charts
    filtered_recettes_df = recettes_df.copy()
    filtered_depenses_df = depenses_df.copy()
    filtered_salaires_df = salaires_df.copy()
    filtered_tiers_payants_df = tiers_payants_df.copy() # Add this line

    # Also apply filter to the data for the monthly trend chart if a month is selected
    monthly_trend_recettes_df = recettes_df.copy()
    monthly_trend_depenses_df = depenses_df.copy()
    monthly_trend_salaires_df = salaires_df.copy()
    monthly_trend_tiers_payants_df = tiers_payants_df.copy() # Add this line


    if selected_year and selected_month_num:
        # Filter for KPIs and pie charts
        filtered_recettes_df = filtered_recettes_df[
            (filtered_recettes_df['Date_Parsed'].dt.year == selected_year) &
            (filtered_recettes_df['Date_Parsed'].dt.month == selected_month_num)
        ]

        filtered_depenses_df = filtered_depenses_df[
            (filtered_depenses_df['Date_Parsed'].dt.year == selected_year) &
            (filtered_depenses_df['Date_Parsed'].dt.month == selected_month_num)
        ]

        filtered_salaires_df = filtered_salaires_df[
            (filtered_salaires_df['Mois_Annee_Parsed'].dt.year == selected_year) &
            (filtered_salaires_df['Mois_Annee_Parsed'].dt.month == selected_month_num)
        ]
        
        # Filter tiers_payants for KPIs and pie charts by Date_Reglement
        filtered_tiers_payants_df = filtered_tiers_payants_df[
            (filtered_tiers_payants_df['Date_Parsed'].dt.year == selected_year) &
            (filtered_tiers_payants_df['Date_Parsed'].dt.month == selected_month_num)
        ]

        # Apply filter to monthly trend dataframes too if a specific month is selected
        monthly_trend_recettes_df = monthly_trend_recettes_df[
            (monthly_trend_recettes_df['Date_Parsed'].dt.year == selected_year) &
            (monthly_trend_recettes_df['Date_Parsed'].dt.month == selected_month_num)
        ]

        monthly_trend_depenses_df = monthly_trend_depenses_df[
            (monthly_trend_depenses_df['Date_Parsed'].dt.year == selected_year) &
            (monthly_trend_depenses_df['Date_Parsed'].dt.month == selected_month_num)
        ]
        
        monthly_trend_salaires_df = monthly_trend_salaires_df[
            (monthly_trend_salaires_df['Mois_Annee_Parsed'].dt.year == selected_year) &
            (monthly_trend_salaires_df['Mois_Annee_Parsed'].dt.month == selected_month_num)
        ]

        # Filter monthly_trend_tiers_payants_df by Date_Reglement
        monthly_trend_tiers_payants_df = monthly_trend_tiers_payants_df[
            (monthly_trend_tiers_payants_df['Date_Parsed'].dt.year == selected_year) &
            (monthly_trend_tiers_payants_df['Date_Parsed'].dt.month == selected_month_num)
        ]

    # --- Calcul des indicateurs pour le Tableau de Bord (utilisant les DFs filtrés) ---
    total_revenues_from_recettes = float(filtered_recettes_df['Montant'].sum()) if not filtered_recettes_df.empty else 0.0
    # Include only received amounts from tiers payants with 'Réglé' or 'Partiellement réglé' status
    total_revenues_from_tiers_payants = float(filtered_tiers_payants_df[
        filtered_tiers_payants_df['Statut'].isin(['Réglé', 'Partiellement réglé'])
    ]['Montant_Recu'].sum()) if not filtered_tiers_payants_df.empty else 0.0
    
    total_revenues = total_revenues_from_recettes + total_revenues_from_tiers_payants
    
    total_expenses_value = float(filtered_depenses_df['Montant'].sum()) if not filtered_depenses_df.empty else 0.0
    total_salaries_value = float(filtered_salaires_df['Total_Brut'].sum()) if not filtered_salaires_df.empty else 0.0
    
    # Calculate combined expenses for the dashboard display
    combined_total_expenses = total_expenses_value + total_salaries_value
    
    net_profit = total_revenues - combined_total_expenses # Use combined_total_expenses here

    # Graphique 1: Tendances Mensuelles (Recettes, Dépenses, Bénéfice Net)
    monthly_data = {
        'labels': [],
        'revenues': [],
        'expenses': [],
        'profit': []
    }
    
    all_dates_in_trend_dfs = pd.Series(dtype='datetime64[ns]')
    if not monthly_trend_recettes_df.empty and not monthly_trend_recettes_df['Date_Parsed'].isna().all():
        all_dates_in_trend_dfs = pd.concat([all_dates_in_trend_dfs, monthly_trend_recettes_df['Date_Parsed'].dropna()])
    if not monthly_trend_depenses_df.empty and not monthly_trend_depenses_df['Date_Parsed'].isna().all():
        all_dates_in_trend_dfs = pd.concat([all_dates_in_trend_dfs, monthly_trend_depenses_df['Date_Parsed'].dropna()])
    if not monthly_trend_salaires_df.empty and not monthly_trend_salaires_df['Mois_Annee_Parsed'].isna().all():
        all_dates_in_trend_dfs = pd.concat([all_dates_in_trend_dfs, monthly_trend_salaires_df['Mois_Annee_Parsed'].dropna()])
    if not monthly_trend_tiers_payants_df.empty and not monthly_trend_tiers_payants_df['Date_Parsed'].isna().all():
        # Only include received amounts for monthly trend tiers payants
        all_dates_in_trend_dfs = pd.concat([all_dates_in_trend_dfs, monthly_trend_tiers_payants_df['Date_Parsed'].dropna()])

    all_dates = all_dates_in_trend_dfs.tolist()

    if all_dates:
        min_date_val = min(all_dates)
        max_date_val = max(all_dates)
        
        if selected_year and selected_month_num:
            current = datetime(selected_year, selected_month_num, 1)
            end_date_for_range = current
        else:
            current = datetime(min_date_val.year, min_date_val.month, 1)
            end_date_for_range = datetime.now().replace(day=1)
            if max_date_val and max_date_val.replace(day=1) > end_date_for_range:
                end_date_for_range = max_date_val.replace(day=1)


        while current <= end_date_for_range:
            month_str = current.strftime('%Y-%m')
            monthly_data['labels'].append(month_str)
            
            m_rev_series = monthly_trend_recettes_df[
                (monthly_trend_recettes_df['Date_Parsed'].dt.year == current.year) &
                (monthly_trend_recettes_df['Date_Parsed'].dt.month == current.month)
            ]['Montant']
            m_rev = m_rev_series.sum() if not m_rev_series.empty else 0

            m_tp_rev_series = monthly_trend_tiers_payants_df[
                (monthly_trend_tiers_payants_df['Date_Parsed'].dt.year == current.year) &
                (monthly_trend_tiers_payants_df['Date_Parsed'].dt.month == current.month) &
                (monthly_trend_tiers_payants_df['Statut'].isin(['Réglé', 'Partiellement réglé']))
            ]['Montant_Recu']
            m_tp_rev = m_tp_rev_series.sum() if not m_tp_rev_series.empty else 0

            total_m_rev = m_rev + m_tp_rev

            m_exp_series = monthly_trend_depenses_df[
                (monthly_trend_depenses_df['Date_Parsed'].dt.year == current.year) &
                (monthly_trend_depenses_df['Date_Parsed'].dt.month == current.month)
            ]['Montant']
            m_exp = m_exp_series.sum() if not m_exp_series.empty else 0


            m_sal_series = monthly_trend_salaires_df[
                (monthly_trend_salaires_df['Mois_Annee_Parsed'].dt.year == current.year) &
                (monthly_trend_salaires_df['Mois_Annee_Parsed'].dt.month == current.month)
            ]['Total_Brut']
            m_sal = m_sal_series.sum() if not m_sal_series.empty else 0


            monthly_data['revenues'].append(float(total_m_rev)) # Updated to include Tiers Payants
            monthly_data['expenses'].append(float(m_exp + m_sal))
            monthly_data['profit'].append(float(total_m_rev - (m_exp + m_sal))) # Updated to include Tiers Payants
            
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1)
            else:
                current = datetime(current.year, current.month + 1, 1)

    else:
        if selected_month_str:
            monthly_data['labels'].append(selected_month_str)
            monthly_data['revenues'].append(0)
            monthly_data['expenses'].append(0)
            monthly_data['profit'].append(0)
        else:
            today = datetime.now()
            for i in range(5, -1, -1):
                month = today - timedelta(days=30 * i)
                month_str = month.strftime('%Y-%m')
                monthly_data['labels'].append(month_str)
                monthly_data['revenues'].append(0)
                monthly_data['expenses'].append(0)
                monthly_data['profit'].append(0)


    # Graphique 2: Répartition des Recettes par Type d'Acte (utilisant les DFs filtrés)
    revenue_by_type_data = {'labels': [], 'data': [], 'colors': []}
    # Create a combined DataFrame for revenues including received tiers payants
    # This assumes 'Type_Acte' can be inferred or defined for Tiers Payants.
    # For simplicity, we'll treat them as a separate 'Tiers Payant' type if no specific act type is available.
    combined_revenues_df = filtered_recettes_df[['Type_Acte', 'Montant']].copy()
    
    # Filter tiers_payants for received amounts and add them to combined_revenues_df
    received_tiers_payants_for_chart = filtered_tiers_payants_df[
        filtered_tiers_payants_df['Statut'].isin(['Réglé', 'Partiellement réglé'])
    ].copy()

    if not received_tiers_payants_for_chart.empty:
        # If no specific 'Type_Acte' for Tiers Payants, assign a default
        received_tiers_payants_for_chart['Type_Acte'] = 'Tiers Payant' 
        received_tiers_payants_for_chart = received_tiers_payants_for_chart.rename(columns={'Montant_Recu': 'Montant'})
        combined_revenues_df = pd.concat([combined_revenues_df, received_tiers_payants_for_chart[['Type_Acte', 'Montant']]], ignore_index=True)


    if not combined_revenues_df.empty:
        type_counts = combined_revenues_df.groupby('Type_Acte')['Montant'].sum().sort_values(ascending=False)
        if not type_counts.empty:
            revenue_by_type_data['labels'] = type_counts.index.tolist()
            revenue_by_type_data['data'] = type_counts.values.tolist()
            colors = [
                '#4CAF50', '#2196F3', '#FFC107', '#E91E63', '#9C27B0',
                '#00BCD4', '#FF5722', '#CDDC39', '#607D8B', '#795548'
            ]
            for i in range(len(revenue_by_type_data['labels'])):
                revenue_by_type_data['colors'].append(colors[i % len(colors)])
    
    # Graphique 3: Répartition des Dépenses par Catégorie (utilisant les DFs filtrés et incluant salaires)
    expenses_by_category_data = {'labels': [], 'data': [], 'colors': []}
    
    # Combine regular expenses and salaries into a single DataFrame for the pie chart
    combined_expenses_df_for_chart = filtered_depenses_df[['Categorie', 'Montant']].copy()
    if not filtered_salaires_df.empty:
        # Assign a specific category for salaries
        salaries_for_chart = filtered_salaires_df.assign(
            Categorie='Salaires & Charges Sociales', 
            Montant=filtered_salaires_df['Total_Brut']
        )
        combined_expenses_df_for_chart = pd.concat([combined_expenses_df_for_chart, salaries_for_chart[['Categorie', 'Montant']]], ignore_index=True)

    if not combined_expenses_df_for_chart.empty:
        category_counts = combined_expenses_df_for_chart.groupby('Categorie')['Montant'].sum().sort_values(ascending=False)
        if not category_counts.empty:
            expenses_by_category_data['labels'] = category_counts.index.tolist()
            expenses_by_category_data['data'] = category_counts.values.tolist()
            colors = [
                '#F44336', '#FF9800', '#673AB7', '#009688', '#FFEB3B',
                '#8BC34A', '#795548', '#9E9E9E', '#607D8B', '#3F51B5'
            ]
            for i in range(len(expenses_by_category_data['labels'])):
                expenses_by_category_data['colors'].append(colors[i % len(colors)])


    # --- DÉBUT DE L'AJOUT POUR LA DÉFINITION DE logged_in_full_name ---
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
    # --- FIN DE L'AJOUT POUR LA DÉFINITION DE logged_in_full_name ---

    return render_template_string(
        comptabilite_template,
        config=config,
        theme_vars=theme.current_theme(),
        theme_names=list(theme.THEMES.keys()),
        host_address=host_address,
        current_date=current_date,
        currency=currency,
        total_revenues=total_revenues,
        total_expenses=combined_total_expenses, # Pass the combined value
        net_profit=net_profit,
        monthly_data=monthly_data,
        revenue_by_type_data=revenue_by_type_data,
        expenses_by_category_data=expenses_by_category_data,
        selected_month=selected_month_str,
        recettes=recettes_df.to_dict(orient='records'),
        depenses=depenses_df.to_dict(orient='records'),
        salaires=salaires_df.to_dict(orient='records'),
        tiers_payants=tiers_payants_df.to_dict(orient='records'),
        documents_fiscaux=documents_fiscaux_df.to_dict(orient='records'),
        expense_categories=DEFAULT_EXPENSE_CATEGORIES,
        fiscal_document_types=DEFAULT_FISCAL_DOCUMENT_TYPES,
        # --- PASSER LA NOUVELLE VARIABLE AU TEMPLATE ---
        logged_in_doctor_name=logged_in_full_name # Utilise le même nom de variable que dans main_template pour cohérence
        # --- FIN DU PASSAGE ---
    )

# Recettes
@comptabilite_bp.route('/add_recette', methods=['POST'])
def add_recette():
    if 'email' not in session: return redirect(url_for('login.login'))
    f = request.form
    new_recette = {
        'Date': f['date_recette'],
        'Type_Acte': f['type_acte'],
        'Patient_ID': f['patient_id_recette'],
        'Patient_Nom': f['patient_nom_recette'],
        'Patient_Prenom': f['patient_prenom_recette'],
        'Montant': float(f['montant_recette']),
        'Mode_Paiement': f['mode_paiement'],
        'Description': f['description_recette'],
        'ID_Facture_Liee': f['id_facture_liee'] or ''
    }
    df = load_recettes()
    df = pd.concat([df, pd.DataFrame([new_recette])], ignore_index=True)
    if save_recettes(df):
        flash("Recette ajoutée avec succès.", "success")
    else:
        flash("Erreur lors de l'ajout de la recette.", "danger")
    return redirect(url_for('comptabilite.home_comptabilite', _anchor="recettes-tab"))

@comptabilite_bp.route('/delete_recette/<int:index>')
def delete_recette(index):
    if 'email' not in session: return redirect(url_for('login.login'))
    df = load_recettes()
    if 0 <= index < len(df):
        df = df.drop(df.index[index]).reset_index(drop=True)
        if save_recettes(df):
            flash("Recette supprimée avec succès.", "success")
        else:
            flash("Erreur lors de la suppression de la recette.", "danger")
    return redirect(url_for('comptabilite.home_comptabilite', _anchor="recettes-tab"))

# Factures - Mettre à jour le statut de paiement - REMOVED ROUTE
# @comptabilite_bp.route('/update_invoice_status', methods=['POST'])
# def update_invoice_status():
#     if 'email' not in session: return jsonify(success=False), 401
    
#     invoice_numero = request.form.get('invoice_numero')
#     new_status = request.form.get('new_status')

#     FACTURES_EXCEL_PATH = os.path.join(utils.EXCEL_FOLDER, 'factures.xlsx')
#     if not os.path.exists(FACTURES_EXCEL_PATH):
#         return jsonify(success=False, message="Fichier factures.xlsx non trouvé."), 404

#     try:
#         df_factures = pd.read_excel(FACTURES_EXCEL_PATH, dtype=str).fillna('')
#         if 'Statut_Paiement' not in df_factures.columns:
#             df_factures['Statut_Paiement'] = 'Impayée'
        
#         idx = df_factures[df_factures['Numero'] == invoice_numero].index
#         if not idx.empty:
#             df_factures.loc[idx, 'Statut_Paiement'] = new_status
#             df_factures.to_excel(FACTURES_EXCEL_PATH, index=False)
#             return jsonify(success=True, message="Statut mis à jour.")
#         return jsonify(success=False, message="Facture non trouvée."), 404
#     except Exception as e:
#         print(f"Erreur lors de la mise à jour du statut de facture: {e}")
#         return jsonify(success=False, message=str(e)), 500


# Dépenses
@comptabilite_bp.route('/add_depense', methods=['POST'])
def add_depense():
    if 'email' not in session: return redirect(url_for('login.login'))
    f = request.form
    justificatif_file = request.files.get('justificatif_file')
    justificatif_filename = ""

    if justificatif_file and justificatif_file.filename:
        filename = utils.secure_filename(justificatif_file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        justificatif_filename = f"depense_{timestamp}_{filename}"
        save_path = os.path.join(utils.PDF_FOLDER, 'Justificatifs_Depenses')
        os.makedirs(save_path, exist_ok=True)
        try:
            justificatif_file.save(os.path.join(save_path, justificatif_filename))
            flash(f"Justificatif '{justificatif_filename}' enregistré.", "success")
        except Exception as e:
            flash(f"Erreur lors de l'enregistrement du justificatif : {e}", "danger")
            justificatif_filename = "" # Reset filename if save fails

    new_depense = {
        'Date': f['date_depense'],
        'Categorie': f['categorie_depense'],
        'Description': f['description_depense'],
        'Montant': float(f['montant_depense']),
        'Justificatif_Fichier': justificatif_filename
    }
    df = load_depenses()
    df = pd.concat([df, pd.DataFrame([new_depense])], ignore_index=True)
    if save_depenses(df):
        flash("Dépense ajoutée avec succès.", "success")
    else:
        flash("Erreur lors de l'ajout de la dépense.", "danger")
    return redirect(url_for('comptabilite.home_comptabilite', _anchor="depenses-tab"))

@comptabilite_bp.route('/delete_depense/<int:index>')
def delete_depense(index):
    if 'email' not in session: return redirect(url_for('login.login'))
    df = load_depenses()
    if 0 <= index < len(df):
        # Supprimer le fichier justificatif si existant
        justificatif_filename = df.loc[index, 'Justificatif_Fichier']
        if justificatif_filename:
            file_path = os.path.join(utils.PDF_FOLDER, 'Justificatifs_Depenses', justificatif_filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Justificatif {justificatif_filename} supprimé.")
        
        df = df.drop(df.index[index]).reset_index(drop=True)
        if save_depenses(df):
            flash("Dépense supprimée avec succès.", "success")
        else:
            flash("Erreur lors de la suppression de la dépense.", "danger")
    return redirect(url_for('comptabilite.home_comptabilite', _anchor="depenses-tab"))

@comptabilite_bp.route('/download_justificatif/<filename>')
def download_justificatif(filename):
    if 'email' not in session: return redirect(url_for('login.login'))
    return send_file(os.path.join(utils.PDF_FOLDER, 'Justificatifs_Depenses', filename), as_attachment=True)


# Salaires & Paie
@comptabilite_bp.route('/add_salaire', methods=['POST'])
def add_salaire():
    if 'email' not in session: return redirect(url_for('login.login'))
    f = request.form
    salaire_net = float(f['salaire_net'])
    charges_sociales = float(f['charges_sociales'])
    total_brut = salaire_net + charges_sociales # Calcul simple du brut

    new_salaire = {
        'Mois_Annee': f['mois_annee'],
        'Nom_Employe': f['nom_employe'],
        'Prenom_Employe': f['prenom_employe'],
        'Salaire_Net': salaire_net,
        'Charges_Sociales': charges_sociales,
        'Total_Brut': total_brut,
        'Fiche_Paie_PDF': '' # Sera rempli après génération PDF
    }
    df = load_salaires()
    df = pd.concat([df, pd.DataFrame([new_salaire])], ignore_index=True)
    if save_salaires(df):
        flash("Salaire ajouté avec succès.", "success")
    else:
        flash("Erreur lors de l'ajout du salaire.", "danger")
    return redirect(url_for('comptabilite.home_comptabilite', _anchor="salaires-tab"))

@comptabilite_bp.route('/delete_salaire/<int:index>')
def delete_salaire(index):
    if 'email' not in session: return redirect(url_for('login.login'))
    df = load_salaires()
    if 0 <= index < len(df):
        # Supprimer le fichier PDF de la fiche de paie si existant
        fiche_paie_filename = df.loc[index, 'Fiche_Paie_PDF']
        if fiche_paie_filename:
            file_path = os.path.join(utils.PDF_FOLDER, 'Fiches_Paie', fiche_paie_filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Fiche de paie {fiche_paie_filename} supprimée.")
        
        df = df.drop(df.index[index]).reset_index(drop=True)
        if save_salaires(df):
            flash("Salaire supprimé avec succès.", "success")
        else:
            flash("Erreur lors de la suppression du salaire.", "danger")
    return redirect(url_for('comptabilite.home_comptabilite', _anchor="salaires-tab"))

@comptabilite_bp.route('/generate_payslip/<int:index>')
def generate_payslip(index):
    if 'email' not in session: return redirect(url_for('login.login'))
    df = load_salaires()
    if not (0 <= index < len(df)):
        flash("Fiche de paie introuvable.", "danger")
        return redirect(url_for('comptabilite.home_comptabilite', _anchor="salaires-tab"))

    salaire_entry = df.iloc[index]
    
    # Récupérer la devise et les informations de l'entreprise de la config générale
    config = utils.load_config()
    currency = config.get('currency', 'MAD')

    # Passer toutes les données nécessaires à la classe PDFInvoice
    pdf = PayslipPDF(
        app_config={
            'nom_clinique': config.get('nom_clinique', 'EasyMedicaLink'),
            'cabinet': config.get('cabinet', 'Cabinet Médical'),
            'location': config.get('location', 'Adresse non définie'),
            'phone': config.get('phone', 'N/A'), # Assurez-vous que le numéro de téléphone est dans votre config
            'email': session.get('admin_email', 'contact@clinique.com') # Utiliser l'email de session pour l'exemple
        },
        emp_data={
            'Nom_Employe': salaire_entry['Nom_Employe'],
            'Prenom_Employe': salaire_entry['Prenom_Employe'],
            'Mois_Annee': salaire_entry['Mois_Annee'],
            'Salaire_Net': float(salaire_entry['Salaire_Net']),
            'Charges_Sociales': float(salaire_entry['Charges_Sociales']),
            'Total_Brut': float(salaire_entry['Total_Brut'])
        },
        currency=currency
    )
    pdf.chapter_body()
    
    pdf_dir = os.path.join(utils.PDF_FOLDER, 'Fiches_Paie')
    os.makedirs(pdf_dir, exist_ok=True)
    
    filename = f"Fiche_Paie_{salaire_entry['Prenom_Employe']}_{salaire_entry['Nom_Employe']}_{salaire_entry['Mois_Annee'].replace('/', '-')}.pdf"
    file_path = os.path.join(pdf_dir, filename)
    pdf.output(file_path)

    # Fusionner avec l'arrière-plan si un PDF est configuré
    if utils.background_file and utils.background_file.lower().endswith('.pdf'):
        try:
            utils.merge_with_background_pdf(file_path)
        except Exception as e:
            print(f"Erreur lors de la fusion du PDF de fiche de paie avec l'arrière-plan: {e}")
            flash(f"Avertissement: Impossible de fusionner l'arrière-plan PDF. {e}", "warning")


    # Mettre à jour le chemin du PDF dans le DataFrame des salaires
    df.loc[index, 'Fiche_Paie_PDF'] = filename
    save_salaires(df)

    return send_file(file_path, as_attachment=True, download_name=filename)


@comptabilite_bp.route('/import_salaires_excel', methods=['POST'])
def import_salaires_excel():
    if 'email' not in session:
        flash("Veuillez vous connecter pour importer des données.", "danger")
        return redirect(url_for('login.login'))

    if 'file' not in request.files:
        flash("Aucun fichier n'a été sélectionné.", "danger")
        return redirect(url_for('comptabilite.home_comptabilite', _anchor="salaires-tab"))

    file = request.files['file']
    if file.filename == '':
        flash("Aucun fichier n'a été sélectionné.", "danger")
        return redirect(url_for('comptabilite.home_comptabilite', _anchor="salaires-tab"))

    if file and file.filename.endswith(('.xlsx', '.xls')):
        try:
            # Read the uploaded Excel file into a DataFrame
            imported_df = pd.read_excel(file, dtype=str).fillna('')
            
            # Define expected columns for salaries sheet
            expected_cols = ['Mois_Annee', 'Nom_Employe', 'Prenom_Employe', 'Salaire_Net', 'Charges_Sociales', 'Total_Brut'] # Fiche_Paie_PDF is generated, not imported

            # Check if all expected columns are present
            if not all(col in imported_df.columns for col in expected_cols):
                missing_cols = [col for col in expected_cols if col not in imported_df.columns]
                flash(f"Le fichier Excel ne contient pas toutes les colonnes requises. Colonnes manquantes : {', '.join(missing_cols)}", "danger")
                return redirect(url_for('comptabilite.home_comptabilite', _anchor="salaires-tab"))

            # Load existing salaries data
            existing_df = load_salaires()

            # Prepare imported_df to match existing_df structure
            # Ensure 'Fiche_Paie_PDF' column is present in imported_df before concatenation
            if 'Fiche_Paie_PDF' not in imported_df.columns:
                imported_df['Fiche_Paie_PDF'] = '' # Add with empty string for new imports

            # Append new data; ensure consistent column order including 'Fiche_Paie_PDF'
            imported_df = imported_df[existing_df.columns.tolist()] # Select and reorder columns
            updated_df = pd.concat([existing_df, imported_df], ignore_index=True)

            # Convert numeric columns after concatenation, as _load_sheet_data does
            numeric_cols = ['Salaire_Net', 'Charges_Sociales', 'Total_Brut']
            for col in numeric_cols:
                if col in updated_df.columns:
                    updated_df[col] = pd.to_numeric(updated_df[col], errors='coerce').fillna(0).astype(float)

            if save_salaires(updated_df):
                flash("Données des salaires importées avec succès.", "success")
            else:
                flash("Erreur lors de la sauvegarde des données des salaires après l'importation.", "danger")

        except Exception as e:
            flash(f"Erreur lors de l'importation du fichier Excel : {e}", "danger")
    else:
        flash("Format de fichier non supporté. Veuillez uploader un fichier Excel (.xlsx ou .xls).", "danger")

    return redirect(url_for('comptabilite.home_comptabilite', _anchor="salaires-tab"))


@comptabilite_bp.route('/export_salaires_excel', methods=['GET'])
def export_salaires_excel():
    if 'email' not in session:
        flash("Veuillez vous connecter pour exporter des données.", "danger")
        return redirect(url_for('login.login'))

    try:
        df = load_salaires()
        
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, sheet_name='Salaires', index=False)
        writer.close()
        output.seek(0)

        filename = f"Salaires_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except Exception as e:
        flash(f"Erreur lors de l'exportation des données des salaires : {e}", "danger")
        return redirect(url_for('comptabilite.home_comptabilite', _anchor="salaires-tab"))


# Tiers Payants
@comptabilite_bp.route('/add_tiers_payant', methods=['POST'])
def add_tiers_payant():
    if 'email' not in session: return redirect(url_for('login.login'))
    f = request.form
    new_tp = {
        'Date': f['date_tiers_payant'],
        'Assureur': f['assureur'],
        'Patient_ID': f['patient_id_tp'],
        'Patient_Nom': f['patient_nom_tp'],
        'Patient_Prenom': f['patient_prenom_tp'],
        'Montant_Attendu': float(f['montant_attendu']),
        'Montant_Recu': float(f['montant_recu']),
        'Date_Reglement': f['date_reglement'] or '',
        'ID_Facture_Liee': f['id_facture_liee_tp'] or '',
        'Statut': f['statut_tp']
    }
    df = load_tiers_payants()
    df = pd.concat([df, pd.DataFrame([new_tp])], ignore_index=True)
    if save_tiers_payants(df):
        flash("Règlement Tiers Payant ajouté avec succès.", "success")
    else:
        flash("Erreur lors de l'ajout du règlement Tiers Payant.", "danger")
    return redirect(url_for('comptabilite.home_comptabilite', _anchor="tiers-payants-tab"))

@comptabilite_bp.route('/delete_tiers_payant/<int:index>')
def delete_tiers_payant(index):
    if 'email' not in session: return redirect(url_for('login.login'))
    df = load_tiers_payants()
    if 0 <= index < len(df):
        df = df.drop(df.index[index]).reset_index(drop=True)
        if save_tiers_payants(df):
            flash("Règlement Tiers Payant supprimé avec succès.", "success")
        else:
            flash("Erreur lors de la suppression du règlement Tiers Payant.", "danger")
    return redirect(url_for('comptabilite.home_comptabilite', _anchor="tiers-payants-tab"))


# Documents Fiscaux
@comptabilite_bp.route('/add_document_fiscal', methods=['POST'])
def add_document_fiscal():
    if 'email' not in session: return redirect(url_for('login.login'))
    f = request.form
    document_file = request.files.get('document_file')
    document_filename = ""

    if document_file and document_file.filename:
        filename = utils.secure_filename(document_file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        document_filename = f"fiscal_doc_{timestamp}_{filename}"
        save_path = os.path.join(utils.PDF_FOLDER, 'Documents_Fiscaux')
        os.makedirs(save_path, exist_ok=True)
        try:
            document_file.save(os.path.join(save_path, document_filename))
            flash(f"Document fiscal '{document_filename}' enregistré.", "success")
        except Exception as e:
            flash(f"Erreur lors de l'enregistrement du document fiscal : {e}", "danger")
            document_filename = ""

    new_doc = {
        'Date': f['date_doc_fiscal'],
        'Type_Document': f['type_doc_fiscal'],
        'Description': f['description_doc_fiscal'],
        'Fichier_PDF': document_filename
    }
    df = load_documents_fiscaux()
    df = pd.concat([df, pd.DataFrame([new_doc])], ignore_index=True)
    if save_documents_fiscaux(df):
        flash("Document fiscal ajouté avec succès.", "success")
    else:
        flash("Erreur lors de l'ajout du document fiscal.", "danger")
    return redirect(url_for('comptabilite.home_comptabilite', _anchor="documents-fiscaux-tab"))

@comptabilite_bp.route('/delete_document_fiscal/<int:index>')
def delete_document_fiscal(index):
    if 'email' not in session: return redirect(url_for('login.login'))
    df = load_documents_fiscaux()
    if 0 <= index < len(df):
        # Supprimer le fichier PDF si existant
        doc_filename = df.loc[index, 'Fichier_PDF']
        if doc_filename:
            file_path = os.path.join(utils.PDF_FOLDER, 'Documents_Fiscaux', doc_filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Document fiscal {doc_filename} supprimé.")
        
        df = df.drop(df.index[index]).reset_index(drop=True)
        if save_documents_fiscaux(df):
            flash("Document fiscal supprimé avec succès.", "success")
        else:
            flash("Erreur lors de la suppression du document fiscal.", "danger")
    return redirect(url_for('comptabilite.home_comptabilite', _anchor="documents-fiscaux-tab"))

@comptabilite_bp.route('/download_document_fiscal/<filename>')
def download_document_fiscal(filename):
    if 'email' not in session: return redirect(url_for('login.login'))
    return send_file(os.path.join(utils.PDF_FOLDER, 'Documents_Fiscaux', filename), as_attachment=True)


# --- Rapports (Export PDF/Excel) ---
@comptabilite_bp.route('/generate_compta_report')
def generate_compta_report():
    if 'email' not in session: return redirect(url_for('login.login'))
    
    report_type = request.args.get('report_type')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else None
    end_dt = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else None

    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')

    if report_type == 'revenu_depense':
        recettes_df = load_recettes()
        depenses_df = load_depenses()
        salaires_df = load_salaires()
        tiers_payants_df = load_tiers_payants() # Load tiers payants for the report

        # Ensure Date_Parsed/Mois_Annee_Parsed exist immediately after loading original DFs
        if not recettes_df.empty and 'Date' in recettes_df.columns:
            recettes_df['Date_Parsed'] = pd.to_datetime(recettes_df['Date'], errors='coerce')
        else:
            recettes_df['Date_Parsed'] = pd.Series(dtype='datetime64[ns]')

        if not depenses_df.empty and 'Date' in depenses_df.columns:
            depenses_df['Date_Parsed'] = pd.to_datetime(depenses_df['Date'], errors='coerce')
        else:
            depenses_df['Date_Parsed'] = pd.Series(dtype='datetime64[ns]')

        if not salaires_df.empty and 'Mois_Annee' in salaires_df.columns:
            salaires_df['Mois_Annee_Parsed'] = pd.to_datetime(salaires_df['Mois_Annee'], errors='coerce')
        else:
            salaires_df['Mois_Annee_Parsed'] = pd.Series(dtype='datetime64[ns]')

        if not tiers_payants_df.empty and 'Date_Reglement' in tiers_payants_df.columns:
            tiers_payants_df['Date_Parsed'] = pd.to_datetime(tiers_payants_df['Date_Reglement'], errors='coerce')
        else:
            tiers_payants_df['Date_Parsed'] = pd.Series(dtype='datetime64[ns]')

        # Apply start date filter
        if start_dt:
            recettes_df = recettes_df[recettes_df['Date_Parsed'] >= start_dt]
            depenses_df = depenses_df[depenses_df['Date_Parsed'] >= start_dt]
            salaires_df = salaires_df[salaires_df['Mois_Annee_Parsed'] >= start_dt]
            tiers_payants_df = tiers_payants_df[tiers_payants_df['Date_Parsed'] >= start_dt] # Filter tiers payants

        # Apply end date filter
        if end_dt:
            recettes_df = recettes_df[recettes_df['Date_Parsed'] <= end_dt]
            depenses_df = depenses_df[depenses_df['Date_Parsed'] <= end_dt]
            salaires_df = salaires_df[salaires_df['Mois_Annee_Parsed'] <= end_dt]
            tiers_payants_df = tiers_payants_df[tiers_payants_df['Date_Parsed'] <= end_dt] # Filter tiers payants
        
        # Drop the parsed columns AFTER all filtering is done
        if 'Date_Parsed' in recettes_df.columns:
            recettes_df = recettes_df.drop(columns=['Date_Parsed'])
        if 'Date_Parsed' in depenses_df.columns:
            depenses_df = depenses_df.drop(columns=['Date_Parsed'])
        if 'Mois_Annee_Parsed' in salaires_df.columns:
            salaires_df = salaires_df.drop(columns=['Mois_Annee_Parsed'])
        if 'Date_Parsed' in tiers_payants_df.columns: # Drop for tiers payants
            tiers_payants_df = tiers_payants_df.drop(columns=['Date_Parsed'])

        # Consolidate all revenues for the report, including received tiers payants
        # Create a temporary DataFrame for received tiers payants that looks like a revenue entry
        received_tiers_payants_for_report = tiers_payants_df[
            tiers_payants_df['Statut'].isin(['Réglé', 'Partiellement réglé'])
        ].assign(
            Type_Acte='Tiers Payant Réglé', # Or more specific if available in tiers_payants_df
            Montant=tiers_payants_df['Montant_Recu'],
            Mode_Paiement='Tiers Payant', # Or actual mode if recorded
            Description='Règlement Tiers Payant: ' + tiers_payants_df['Assureur'] + ' pour Patient ' + tiers_payants_df['Patient_Nom'] + ' ' + tiers_payants_df['Patient_Prenom'],
            ID_Facture_Liee=tiers_payants_df['ID_Facture_Liee']
        )[['Date', 'Type_Acte', 'Patient_ID', 'Patient_Nom', 'Patient_Prenom', 'Montant', 'Mode_Paiement', 'Description', 'ID_Facture_Liee']]

        # Concatenate explicit recettes and received tiers payants
        all_revenues = pd.concat([
            recettes_df,
            received_tiers_payants_for_report
        ], ignore_index=True).sort_values(by='Date').fillna('')


        # Consolider les dépenses et salaires en une seule liste pour le rapport
        all_expenses_report = pd.concat([
            depenses_df.assign(Type='Dépense', Description=depenses_df['Description']),
            salaires_df.assign(Type='Salaire', Montant=salaires_df['Total_Brut'], Description=salaires_df['Nom_Employe'] + ' ' + salaires_df['Prenom_Employe'])
        ], ignore_index=True)[['Date', 'Type', 'Montant', 'Description']].fillna('')


        if not all_revenues.empty:
            all_revenues.to_excel(writer, sheet_name='Recettes_Consolidees', index=False)
        if not all_expenses_report.empty: # Use the new consolidated dataframe for report
            all_expenses_report.to_excel(writer, sheet_name='Depenses_et_Salaires', index=False)
        
        total_recettes_report = all_revenues['Montant'].sum() # Sum from consolidated revenues
        total_depenses_report = depenses_df['Montant'].sum() # Still get sum from original for summary
        total_salaires_report = salaires_df['Total_Brut'].sum() # Still get sum from original for summary
        benefice_net_report = total_recettes_report - total_depenses_report - total_salaires_report
        
        summary_df = pd.DataFrame({
            'Indicateur': ['Total Recettes (incl. Tiers Payants Réglés)', 'Total Dépenses', 'Total Salaires', 'Bénéfice Net'],
            'Montant': [total_recettes_report, total_depenses_report, total_salaires_report, benefice_net_report]
        })
        summary_df.to_excel(writer, sheet_name='Résumé Financier', index=False)
        
        filename = f"Rapport_Comptable_{start_date_str or 'Debut'}_{end_date_str or 'Fin'}.xlsx"

    # Ajoutez d'autres types de rapports ici si nécessaire
    else:
        flash("Type de rapport non reconnu.", "danger")
        return redirect(url_for('comptabilite.home_comptabilite', _anchor="rapports-tab"))

    writer.close()
    output.seek(0)
    
    return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# Définition du template HTML pour la page de gestion de la comptabilité
comptabilite_template = """
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Comptabilité – {{ config.nom_clinique or 'EasyMedicaLink' }}</title>
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
            /* Styles pour cacher la flèche déroulante du sélecteur d'entrées DataTables */
            -webkit-appearance: none; /* Masque la flèche par défaut dans les navigateurs WebKit (Chrome, Safari) */
            -moz-appearance: none;    /* Masque la flèche par défaut dans Firefox */
            appearance: none;         /* Masque la flèche par défaut dans IE/Edge et la plupart des navigateurs modernes */
            padding-right: 1.5em;     /* Ajoute une petite marge à droite pour le texte si nécessaire */
        }
        /* Pour IE 10+ */
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

        /* Styles pour les overlays "no data" */
        .no-data-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            color: var(--text-color-light);
            font-size: 1.2rem;
            background-color: var(--card-bg);
            z-index: 10;
            pointer-events: none; /* Permet aux événements de souris de passer à travers si le canvas est en dessous */
            text-align: center;
            padding: 1rem;
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
                <a href="{{ url_for('login.change_password') }}" class="btn btn-outline-secondary flex-fill">
                    <i class="fas fa-key me-2"></i>Modifier passe
                </a>
                <a href="{{ url_for('login.logout') }}" class="btn btn-outline-secondary flex-fill">
                    <i class="fas fa-sign-out-alt me-2"></i>Déconnexion
                </a>
            </div>
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
                        <p class="mt-2 header-item">{{ current_date }}</p>
                        <p class="mt-2 header-item">
                            <i class="fas fa-calculator me-2"></i>Gestion des finances
                        </p>
                    </div>
                    <div class="card-body">
                        <ul class="nav nav-tabs justify-content-center" id="comptabiliteTab" role="tablist">
                            <li class="nav-item" role="presentation">
                                <button class="nav-link active" id="dashboard-tab"
                                        data-bs-toggle="tab" data-bs-target="#dashboard"
                                        type="button" role="tab">
                                    <i class="fas fa-chart-line me-2" style="color: #4CAF50;"></i>Tableau de Bord
                                </button>
                            </li>
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="recettes-tab-btn"
                                        data-bs-toggle="tab" data-bs-target="#recettes"
                                        type="button" role="tab">
                                    <i class="fas fa-money-bill-wave me-2" style="color: #32CD32;"></i>Recettes
                                </button>
                            </li>
                            {# REMOVED FACTURES TAB #}
                            {# <li class="nav-item" role="presentation">
                                <button class="nav-link" id="factures-tab"
                                        data-bs-toggle="tab" data-bs-target="#factures"
                                        type="button" role="tab">
                                    <i class="fas fa-file-invoice me-2" style="color: #FF8C00;"></i>Factures
                                </button>
                            </li> #}
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="depenses-tab-btn"
                                        data-bs-toggle="tab" data-bs-target="#depenses"
                                        type="button" role="tab">
                                    <i class="fas fa-money-check-alt me-2" style="color: #DC143C;"></i>Dépenses
                                </button>
                            </li>
                            {# REMOVED STOCKS MEDICAUX TAB #}
                            {# <li class="nav-item" role="presentation">
                                <button class="nav-link" id="stocks-tab"
                                        data-bs-toggle="tab" data-bs-target="#stocks"
                                        type="button" role="tab">
                                    <i class="fas fa-boxes me-2" style="color: #1E90FF;"></i>Stocks Médicaux
                                </button>
                            </li> #}
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="salaires-tab-btn"
                                        data-bs-toggle="tab" data-bs-target="#salaires"
                                        type="button" role="tab">
                                    <i class="fas fa-users-cog me-2" style="color: #9370DB;"></i>Salaires & Paie
                                </button>
                            </li>
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="rapports-tab-btn"
                                        data-bs-toggle="tab" data-bs-target="#rapports"
                                        type="button" role="tab">
                                    <i class="fas fa-chart-area me-2" style="color: #FFD700;"></i>Rapports
                                </button>
                            </li>
                             <li class="nav-item" role="presentation">
                                <button class="nav-link" id="tiers-payants-tab-btn"
                                        data-bs-toggle="tab" data-bs-target="#tiers-payants"
                                        type="button" role="tab">
                                    <i class="fas fa-handshake me-2" style="color: #20B2AA;"></i>Tiers Payants
                                </button>
                            </li>
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="documents-fiscaux-tab-btn"
                                        data-bs-toggle="tab" data-bs-target="#documents-fiscaux"
                                        type="button" role="tab">
                                    <i class="fas fa-file-alt me-2" style="color: #FFA07A;"></i>Docs Fiscaux
                                </button>
                            </li>
                        </ul>

                        <div class="tab-content mt-3" id="comptabiliteTabContent">
                            {# 1. Tableau de Bord (Dashboard) #}
                            <div class="tab-pane fade show active" id="dashboard" role="tabpanel">
                                <h4 class="text-primary mb-3"><i class="fas fa-chart-pie me-2" style="color: #4CAF50;"></i>Aperçu Financier</h4>
                                <div class="row row-cols-1 row-cols-md-3 g-3 mb-4">
                                    <div class="col">
                                        <div class="card text-center p-3">
                                            <div class="fs-4 fw-bold text-success">{{ "%.2f"|format(total_revenues) }} {{ currency }}</div>
                                            <small class="text-muted">Total Recettes</small>
                                        </div>
                                    </div>
                                    <div class="col">
                                        <div class="card text-center p-3">
                                            <div class="fs-4 fw-bold text-danger">{{ "%.2f"|format(total_expenses) }} {{ currency }}</div>
                                            <small class="text-muted">Total Dépenses</small>
                                        </div>
                                    </div>
                                    <div class="col">
                                        <div class="card text-center p-3">
                                            <div class="fs-4 fw-bold {% if net_profit >= 0 %}text-primary{% else %}text-danger{% endif %}">{{ "%.2f"|format(net_profit) }} {{ currency }}</div>
                                            <small class="text-muted">Bénéfice Net</small>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="row mt-4">
                                    <form class="row g-3 align-items-center mb-4 justify-content-center" method="get" action="{{ url_for('comptabilite.home_comptabilite') }}">
                                        <div class="col-md-auto floating-label">
                                            <input type="month" class="form-control" id="monthFilter" name="selected_month" value="{{ selected_month or '' }}" placeholder=" ">
                                            <label for="monthFilter">Filtrer par Mois</label>
                                        </div>
                                        <div class="col-md-auto">
                                            <button type="submit" class="btn btn-primary">
                                                <i class="fas fa-filter me-2"></i>Filtrer
                                            </button>
                                            <a href="{{ url_for('comptabilite.home_comptabilite') }}" class="btn btn-outline-secondary ms-2">
                                                <i class="fas fa-redo me-2"></i>Réinitialiser
                                            </a>
                                        </div>
                                    </form>

                                    <div class="col-12 mb-4">
                                        <div class="card h-100 p-3">
                                            <h5 class="text-primary text-center mb-3"><i class="fas fa-chart-bar me-2" style="color: #FF6347;"></i>Tendances Mensuelles (Recettes, Dépenses, Bénéfice Net)</h5>
                                            <div style="height: 300px; position: relative;">
                                                <canvas id="monthlyChart"></canvas>
                                                <div id="monthlyNoDataMessage" class="no-data-overlay">
                                                    Aucune donnée disponible pour ce graphique.
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-lg-6 col-md-12 mb-4">
                                        <div class="card h-100 p-3">
                                            <h5 class="text-primary text-center mb-3"><i class="fas fa-chart-pie me-2" style="color: #2196F3;"></i>Recettes par Type d'Acte</h5>
                                            <div style="height: 250px; position: relative;">
                                                <canvas id="revenueByTypeChart"></canvas>
                                                <div id="revenueNoDataMessage" class="no-data-overlay">
                                                    Aucune donnée disponible pour ce graphique.
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-lg-6 col-md-12 mb-4">
                                        <div class="card h-100 p-3">
                                            <h5 class="text-primary text-center mb-3"><i class="fas fa-chart-pie me-2" style="color: #F44336;"></i>Dépenses par Catégorie</h5>
                                            <div style="height: 250px; position: relative;">
                                                <canvas id="expensesByCategoryChart"></canvas>
                                                <div id="expensesNoDataMessage" class="no-data-overlay">
                                                    Aucune donnée disponible pour ce graphique.
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {# 2. Recettes #}
                            <div class="tab-pane fade" id="recettes" role="tabpanel">
                                <h4 class="text-primary mb-3"><i class="fas fa-money-bill-wave me-2" style="color: #32CD32;"></i>Gestion des Recettes</h4>
                                <form action="{{ url_for('comptabilite.add_recette') }}" method="POST" class="mb-4">
                                    <div class="row g-3">
                                        <div class="col-md-4 floating-label">
                                            <input type="date" class="form-control" name="date_recette" value="{{ current_date }}" required placeholder=" ">
                                            <label>Date</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" name="type_acte" required placeholder=" ">
                                            <label>Type d'acte</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="number" class="form-control" name="montant_recette" step="0.01" min="0" required placeholder=" ">
                                            <label>Montant ({{ currency }})</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" name="patient_id_recette" placeholder=" ">
                                            <label>ID Patient</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" name="patient_nom_recette" placeholder=" ">
                                            <label>Nom Patient</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" name="patient_prenom_recette" placeholder=" ">
                                            <label>Prénom Patient</label>
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <select class="form-select" name="mode_paiement" required placeholder=" ">
                                                <option value="" disabled selected>Sélectionnez un mode</option>
                                                <option value="Espèces">Espèces</option>
                                                <option value="Carte Bancaire">Carte Bancaire</option>
                                                <option value="Chèque">Chèque</option>
                                                <option value="Virement">Virement</option>
                                                <option value="Autre">Autre</option>
                                            </select>
                                            <label>Mode de Paiement</label>
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <input type="text" class="form-control" name="id_facture_liee" placeholder=" ">
                                            <label>ID Facture Liée (optionnel)</label>
                                        </div>
                                        <div class="col-md-12 floating-label">
                                            <textarea class="form-control" name="description_recette" rows="2" placeholder=" "></textarea>
                                            <label>Description (optionnel)</label>
                                        </div>
                                        <div class="col-12 text-center">
                                            <button type="submit" class="btn btn-primary"><i class="fas fa-plus-circle me-2"></i>Ajouter Recette</button>
                                        </div>
                                    </div>
                                </form>

                                <h5 class="mt-4 mb-3"><i class="fas fa-history me-2" style="color: #FFC107;"></i>Historique des Recettes</h5>
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover" id="recettesTable">
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>Type d'acte</th>
                                                <th>Patient</th>
                                                <th>Montant</th>
                                                <th>Mode</th>
                                                <th>Facture Liée</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% for recette in recettes %}
                                            <tr>
                                                <td>{{ recette.Date }}</td>
                                                <td>{{ recette.Type_Acte }}</td>
                                                <td>{{ recette.Patient_Nom }} {{ recette.Patient_Prenom }} ({{ recette.Patient_ID }})</td>
                                                <td>{{ "%.2f"|format(recette.Montant) }} {{ currency }}</td>
                                                <td>{{ recette.Mode_Paiement }}</td>
                                                <td>{{ recette.ID_Facture_Liee }}</td>
                                                <td>
                                                    <a href="{{ url_for('comptabilite.delete_recette', index=loop.index0) }}" class="btn btn-sm btn-danger"><i class="fas fa-trash"></i></a>
                                                </td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            {# 3. Factures - REMOVED CONTENT #}
                            {# <div class="tab-pane fade" id="factures" role="tabpanel">
                                <h4 class="text-primary mb-3"><i class="fas fa-file-invoice me-2" style="color: #FF8C00;"></i>Suivi des Factures</h4>
                                {% if FACTURATION_MODULE_AVAILABLE %}
                                <div class="text-center mb-4">
                                    <p class="lead">Total des factures : <strong>{{ invoice_summary.count }}</strong></p>
                                    <p class="lead">Chiffre d'affaires total facturé : <strong>{{ "%.2f"|format(invoice_summary.total_ttc) }} {{ currency }}</strong></p>
                                    <a href="{{ url_for('facturation.facturation_home') }}" class="btn btn-info">
                                        <i class="fas fa-plus-circle me-2"></i>Générer une nouvelle facture
                                    </a>
                                </div>
                                <h5 class="mt-4 mb-3"><i class="fas fa-list-alt me-2" style="color: #6C757D;"></i>Liste Complète des Factures</h5>
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover" id="facturesTable">
                                        <thead>
                                            <tr>
                                                <th>Numéro</th>
                                                <th>Date</th>
                                                <th>Patient</th>
                                                <th>Montant HT</th>
                                                <th>TVA</th>
                                                <th>Total TTC</th>
                                                <th>Statut</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% for invoice in all_invoices %}
                                            <tr>
                                                <td>{{ invoice.Numero }}</td>
                                                <td>{{ invoice.Date }}</td>
                                                <td>{{ invoice.Patient }}</td>
                                                <td>{{ "%.2f"|format(invoice['Sous-total']) }} {{ currency }}</td>
                                                <td>{{ "%.2f"|format(invoice.TVA) }} {{ currency }}</td>
                                                <td>{{ "%.2f"|format(invoice.Total) }} {{ currency }}</td>
                                                <td>
                                                    <span class="badge
                                                        {% if invoice.Statut_Paiement == 'Payée' %}bg-success
                                                        {% elif invoice.Statut_Paiement == 'Partielle' %}bg-warning text-dark
                                                        {% else %}bg-danger{% endif %}">
                                                        {{ invoice.Statut_Paiement }}
                                                    </span>
                                                </td>
                                                <td>
                                                    <a href="{{ url_for('facturation.download_invoice', filename='Facture_' ~ invoice.Numero ~ '.pdf') }}" class="btn btn-sm btn-primary" title="Télécharger"><i class="fas fa-download"></i></a>
                                                    <button class="btn btn-sm btn-secondary change-status-btn" data-invoice-numero="{{ invoice.Numero }}" data-current-status="{{ invoice.Statut_Paiement }}" title="Changer Statut"><i class="fas fa-exchange-alt"></i></button>
                                                </td>
                                            </tr>
                                            {% else %}
                                                <tr><td colspan="8" class="text-center text-muted">Aucune facture enregistrée.</td></tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                                {% else %}
                                <p class="text-center text-muted">Le module de facturation n'est pas disponible ou est mal configuré. Impossible d'afficher les factures.</p>
                                {% endif %}
                            </div> #}

                            {# 4. Dépenses #}
                            <div class="tab-pane fade" id="depenses" role="tabpanel">
                                <h4 class="text-primary mb-3"><i class="fas fa-money-check-alt me-2" style="color: #DC143C;"></i>Enregistrement des Dépenses</h4>
                                <form action="{{ url_for('comptabilite.add_depense') }}" method="POST" enctype="multipart/form-data" class="mb-4">
                                    <div class="row g-3">
                                        <div class="col-md-4 floating-label">
                                            <input type="date" class="form-control" name="date_depense" value="{{ current_date }}" required placeholder=" ">
                                            <label>Date</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <select class="form-select" name="categorie_depense" required placeholder=" ">
                                                <option value="" disabled selected>Sélectionnez une catégorie</option>
                                                {% for cat in expense_categories %}
                                                <option value="{{ cat }}">{{ cat }}</option>
                                                {% endfor %}
                                            </select>
                                            <label>Catégorie</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="number" class="form-control" name="montant_depense" step="0.01" min="0" required placeholder=" ">
                                            <label>Montant ({{ currency }})</label>
                                        </div>
                                        <div class="col-md-12 floating-label">
                                            <textarea class="form-control" name="description_depense" rows="2" placeholder=" "></textarea>
                                            <label>Description</label>
                                        </div>
                                        <div class="col-md-12 mb-3">
                                            <label for="justificatif_file" class="form-label"><i class="fas fa-paperclip me-2"></i>Justificatif (PDF/Image)</label>
                                            <input class="form-control" type="file" id="justificatif_file" name="justificatif_file" accept=".pdf,.png,.jpg,.jpeg">
                                        </div>
                                        <div class="col-12 text-center">
                                            <button type="submit" class="btn btn-primary"><i class="fas fa-plus-circle me-2"></i>Ajouter Dépense</button>
                                        </div>
                                    </div>
                                </form>
                                <h5 class="mt-4 mb-3"><i class="fas fa-history me-2" style="color: #FFC107;"></i>Historique des Dépenses</h5>
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover" id="depensesTable">
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>Catégorie</th>
                                                <th>Description</th>
                                                <th>Montant</th>
                                                <th>Justificatif</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% for depense in depenses %}
                                            <tr>
                                                <td>{{ depense.Date }}</td>
                                                <td>{{ depense.Categorie }}</td>
                                                <td>{{ depense.Description }}</td>
                                                <td>{{ "%.2f"|format(depense.Montant) }} {{ currency }}</td>
                                                <td>
                                                    {% if depense.Justificatif_Fichier %}
                                                    <a href="{{ url_for('comptabilite.download_justificatif', filename=depense.Justificatif_Fichier) }}" target="_blank" class="btn btn-sm btn-info"><i class="fas fa-file-download"></i></a>
                                                    {% else %} N/A {% endif %}
                                                </td>
                                                <td>
                                                    <a href="{{ url_for('comptabilite.delete_depense', index=loop.index0) }}" class="btn btn-sm btn-danger"><i class="fas fa-trash"></i></a>
                                                </td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            {# 5. Stocks médicaux - REMOVED CONTENT #}
                            {# <div class="tab-pane fade" id="stocks" role="tabpanel">
                                <h4 class="text-primary mb-3"><i class="fas fa-boxes me-2" style="color: #1E90FF;"></i>Aperçu des Stocks Médicaux</h4>
                                {% if PHARMACIE_MODULE_AVAILABLE %}
                                <div class="text-center mb-4">
                                    <p class="lead">Produits en stock bas : <strong>{{ low_stock_alerts|length }}</strong></p>
                                    <p class="lead">Produits expirés : <strong>{{ expired_products|length }}</strong></p>
                                    <a href="{{ url_for('pharmacie.home_pharmacie') }}" class="btn btn-info">
                                        <i class="fas fa-external-link-alt me-2"></i>Accéder à la gestion des stocks complète
                                    </a>
                                </div>
                                {% if low_stock_alerts %}
                                <h5 class="mt-4 mb-3 text-warning"><i class="fas fa-exclamation-triangle me-2"></i>Alertes Stock Bas</h5>
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover">
                                        <thead><tr><th>Code</th><th>Nom</th><th>Quantité</th><th>Seuil Alerte</th></tr></thead>
                                        <tbody>
                                            {% for product in low_stock_alerts %}
                                            <tr class="table-warning">
                                                <td>{{ product.Code_Produit }}</td><td>{{ product.Nom }}</td><td>{{ product.Quantité }}</td><td>{{ product.Seuil_Alerte }}</td>
                                            </tr>
                                            {% else %}
                                                <tr><td colspan="4" class="text-center text-muted">Aucune alerte de stock bas.</td></tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                                {% endif %}

                                {% if expired_products %}
                                <h5 class="mt-4 mb-3 text-danger"><i class="fas fa-calendar-times me-2"></i>Produits Expirés</h5>
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover">
                                        <thead><tr><th>Code</th><th>Nom</th><th>Date Expiration</th><th>Quantité</th></tr></thead>
                                        <tbody>
                                            {% for product in expired_products %}
                                            <tr class="table-danger">
                                                <td>{{ product.Code_Produit }}</td><td>{{ product.Nom }}</td><td>{{ product.Date_Expiration.strftime('%Y-%m-%d') if product.Date_Expiration else 'N/A' }}</td><td>{{ product.Quantité }}</td>
                                            </tr>
                                            {% else %}
                                                <tr><td colspan="4" class="text-center text-muted">Aucun produit expiré.</td></tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                                {% endif %}

                                {% else %}
                                <p class="text-center text-muted">Le module Pharmacie n'est pas disponible ou est mal configuré. Impossible d'afficher les stocks.</p>
                                {% endif %}
                            </div> #}

                            {# 6. Salaires & Paie #}
                            <div class="tab-pane fade" id="salaires" role="tabpanel">
                                <h4 class="text-primary mb-3"><i class="fas fa-users-cog me-2" style="color: #9370DB;"></i>Gestion des Salaires</h4>
                                <form action="{{ url_for('comptabilite.add_salaire') }}" method="POST" class="mb-4">
                                    <div class="row g-3">
                                        <div class="col-md-4 floating-label">
                                            <input type="month" class="form-control" name="mois_annee" value="{{ current_date[:7] }}" required placeholder=" ">
                                            <label>Mois/Année</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" name="nom_employe" required placeholder=" ">
                                            <label>Nom Employé</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" name="prenom_employe" required placeholder=" ">
                                            <label>Prénom Employé</label>
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <input type="number" class="form-control" name="salaire_net" step="0.01" min="0" required placeholder=" ">
                                            <label>Salaire Net ({{ currency }})</label>
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <input type="number" class="form-control" name="charges_sociales" step="0.01" min="0" required placeholder=" ">
                                            <label>Charges Sociales ({{ currency }})</label>
                                        </div>
                                        <div class="col-12 text-center">
                                            <button type="submit" class="btn btn-primary"><i class="fas fa-plus-circle me-2"></i>Ajouter Salaire</button>
                                        </div>
                                    </div>
                                </form>
                                <div class="d-flex justify-content-center gap-2 mb-4">
                                    <button type="button" class="btn btn-success" data-bs-toggle="modal" data-bs-target="#importSalairesModal">
                                        <i class="fas fa-file-import me-2"></i>Importer Excel
                                    </button>
                                    <button type="button" class="btn btn-info" data-bs-toggle="modal" data-bs-target="#exportSalairesModal">
                                        <i class="fas fa-file-export me-2"></i>Exporter Excel
                                    </button>
                                </div>
                                <h5 class="mt-4 mb-3"><i class="fas fa-history me-2" style="color: #FFC107;"></i>Historique des Salaires</h5>
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover" id="salairesTable">
                                        <thead>
                                            <tr>
                                                <th>Mois/Année</th>
                                                <th>Employé</th>
                                                <th>Salaire Net</th>
                                                <th>Charges Sociales</th>
                                                <th>Total Brut</th>
                                                <th>Fiche Paie</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% for salaire in salaires %}
                                            <tr>
                                                <td>{{ salaire.Mois_Annee }}</td>
                                                <td>{{ salaire.Nom_Employe }} {{ salaire.Prenom_Employe }}</td>
                                                <td>{{ "%.2f"|format(salaire.Salaire_Net) }} {{ currency }}</td>
                                                <td>{{ "%.2f"|format(salaire.Charges_Sociales) }} {{ currency }}</td>
                                                <td>{{ "%.2f"|format(salaire.Total_Brut) }} {{ currency }}</td>
                                                <td>
                                                    <a href="{{ url_for('comptabilite.generate_payslip', index=loop.index0) }}" class="btn btn-sm btn-info"><i class="fas fa-file-pdf"></i></a>
                                                </td>
                                                <td>
                                                    <a href="{{ url_for('comptabilite.delete_salaire', index=loop.index0) }}" class="btn btn-sm btn-danger"><i class="fas fa-trash"></i></a>
                                                </td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            {# Modal Import Salaires #}
                            <div class="modal fade" id="importSalairesModal" tabindex="-1" aria-labelledby="importSalairesModalLabel" aria-hidden="true">
                                <div class="modal-dialog">
                                    <div class="modal-content">
                                        <div class="modal-header bg-primary text-white">
                                            <h5 class="modal-title" id="importSalairesModalLabel">Importer les Salaires (Excel)</h5>
                                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                                        </div>
                                        <form action="{{ url_for('comptabilite.import_salaires_excel') }}" method="POST" enctype="multipart/form-data">
                                            <div class="modal-body">
                                                <p>Veuillez sélectionner un fichier Excel (.xlsx ou .xls) contenant les données des salaires. Assurez-vous que les colonnes suivantes sont présentes : <strong>Mois_Annee, Nom_Employe, Prenom_Employe, Salaire_Net, Charges_Sociales, Total_Brut</strong>.</p>
                                                <div class="mb-3">
                                                    <label for="excelFile" class="form-label">Fichier Excel</label>
                                                    <input class="form-control" type="file" id="excelFile" name="file" accept=".xlsx, .xls" required>
                                                </div>
                                            </div>
                                            <div class="modal-footer">
                                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
                                                <button type="submit" class="btn btn-success">Importer</button>
                                            </div>
                                        </form>
                                    </div>
                                </div>
                            </div>

                            {# Modal Export Salaires #}
                            <div class="modal fade" id="exportSalairesModal" tabindex="-1" aria-labelledby="exportSalairesModalLabel" aria-hidden="true">
                                <div class="modal-dialog">
                                    <div class="modal-content">
                                        <div class="modal-header bg-info text-white">
                                            <h5 class="modal-title" id="exportSalairesModalLabel">Exporter les Salaires (Excel)</h5>
                                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                                        </div>
                                        <div class="modal-body">
                                            <p>Cliquez sur "Exporter" pour télécharger toutes les données des salaires actuelles dans un fichier Excel.</p>
                                        </div>
                                        <div class="modal-footer">
                                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
                                            <a href="{{ url_for('comptabilite.export_salaires_excel') }}" id="confirmExportBtn" class="btn btn-success">Exporter</a>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {# 7. Rapports #}
                            <div class="tab-pane fade" id="rapports" role="tabpanel">
                                <h4 class="text-primary mb-3"><i class="fas fa-chart-area me-2" style="color: #FFD700;"></i>Générer des Rapports Financiers</h4>
                                <form action="{{ url_for('comptabilite.generate_compta_report') }}" method="GET" class="mb-4">
                                    <div class="row g-3">
                                        <div class="col-md-4 floating-label">
                                            <select class="form-select" name="report_type" required placeholder=" ">
                                                <option value="" disabled selected>Sélectionnez un type de rapport</option>
                                                <option value="revenu_depense">Rapport Revenus/Dépenses</option>
                                                {# Autres options de rapport futures #}
                                            </select>
                                            <label>Type de Rapport</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="date" class="form-control" name="start_date" placeholder=" ">
                                            <label>Date de Début</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="date" class="form-control" name="end_date" placeholder=" ">
                                            <label>Date de Fin</label>
                                        </div>
                                        <div class="col-12 text-center">
                                            <button type="submit" class="btn btn-primary"><i class="fas fa-file-excel me-2"></i>Générer Rapport Excel</button>
                                            {# <button type="submit" class="btn btn-info ms-2"><i class="fas fa-file-pdf me-2"></i>Générer Rapport PDF</button> #}
                                        </div>
                                    </div>
                                </form>
                            </div>

                            {# 8. Tiers Payants / Assurances #}
                            <div class="tab-pane fade" id="tiers-payants" role="tabpanel">
                                <h4 class="text-primary mb-3"><i class="fas fa-handshake me-2" style="color: #20B2AA;"></i>Suivi des Tiers Payants / Assurances</h4>
                                <form action="{{ url_for('comptabilite.add_tiers_payant') }}" method="POST" class="mb-4">
                                    <div class="row g-3">
                                        <div class="col-md-4 floating-label">
                                            <input type="date" class="form-control" name="date_tiers_payant" value="{{ current_date }}" required placeholder=" ">
                                            <label>Date</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" name="assureur" required placeholder=" ">
                                            <label>Assureur / Mutuelle</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" name="patient_id_tp" placeholder=" ">
                                            <label>ID Patient</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" name="patient_nom_tp" placeholder=" ">
                                            <label>Nom Patient</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" name="patient_prenom_tp" placeholder=" ">
                                            <label>Prénom Patient</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="number" class="form-control" name="montant_attendu" step="0.01" min="0" required placeholder=" ">
                                            <label>Montant Attendu ({{ currency }})</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="number" class="form-control" name="montant_recu" step="0.01" min="0" value="0" placeholder=" ">
                                            <label>Montant Reçu ({{ currency }})</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="date" class="form-control" name="date_reglement" placeholder=" ">
                                            <label>Date de Règlement</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <input type="text" class="form-control" name="id_facture_liee_tp" placeholder=" ">
                                            <label>ID Facture Liée (optionnel)</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <select class="form-select" name="statut_tp" required placeholder=" ">
                                                <option value="En attente" selected>En attente</option>
                                                <option value="Partiellement réglé">Partiellement réglé</option>
                                                <option value="Réglé">Réglé</option>
                                                <option value="Rejeté">Rejeté</option>
                                            </select>
                                            <label>Statut</label>
                                        </div>
                                        <div class="col-12 text-center">
                                            <button type="submit" class="btn btn-primary"><i class="fas fa-plus-circle me-2"></i>Ajouter Règlement</button>
                                        </div>
                                    </div>
                                </form>
                                <h5 class="mt-4 mb-3"><i class="fas fa-list-alt me-2" style="color: #6C757D;"></i>Historique Tiers Payants</h5>
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover" id="tiersPayantsTable">
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>Assureur</th>
                                                <th>Patient</th>
                                                <th>Montant Attendu</th>
                                                <th>Montant Reçu</th>
                                                <th>Statut</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% for tp in tiers_payants %}
                                            <tr>
                                                <td>{{ tp.Date }}</td>
                                                <td>{{ tp.Assureur }}</td>
                                                <td>{{ tp.Patient_Nom }} {{ tp.Patient_Prenom }} ({{ tp.Patient_ID }})</td>
                                                <td>{{ "%.2f"|format(tp.Montant_Attendu) }} {{ currency }}</td>
                                                <td>{{ "%.2f"|format(tp.Montant_Recu) }} {{ currency }}</td>
                                                <td>
                                                    <span class="badge
                                                        {% if tp.Statut == 'Réglé' %}bg-success
                                                        {% elif tp.Statut == 'Partiellement réglé' %}bg-warning text-dark
                                                        {% else %}bg-secondary{% endif %}">
                                                        {{ tp.Statut }}
                                                    </span>
                                                </td>
                                                <td>
                                                    <a href="{{ url_for('comptabilite.delete_tiers_payant', index=loop.index0) }}" class="btn btn-sm btn-danger"><i class="fas fa-trash"></i></a>
                                                </td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            {# 9. Documents Fiscaux #}
                            <div class="tab-pane fade" id="documents-fiscaux" role="tabpanel">
                                <h4 class="text-primary mb-3"><i class="fas fa-file-alt me-2" style="color: #FFA07A;"></i>Documents Fiscaux</h4>
                                <form action="{{ url_for('comptabilite.add_document_fiscal') }}" method="POST" enctype="multipart/form-data" class="mb-4">
                                    <div class="row g-3">
                                        <div class="col-md-4 floating-label">
                                            <input type="date" class="form-control" name="date_doc_fiscal" value="{{ current_date }}" required placeholder=" ">
                                            <label>Date</label>
                                        </div>
                                        <div class="col-md-4 floating-label">
                                            <select class="form-select" name="type_doc_fiscal" required placeholder=" ">
                                                <option value="" disabled selected>Sélectionnez un type</option>
                                                {% for doc_type in fiscal_document_types %}
                                                <option value="{{ doc_type }}">{{ doc_type }}</option>
                                                {% endfor %}
                                            </select>
                                            <label>Type de Document</label>
                                        </div>
                                        <div class="col-md-4 mb-3">
                                            <label for="document_file" class="form-label"><i class="fas fa-file-upload me-2"></i>Fichier (PDF)</label>
                                            <input class="form-control" type="file" id="document_file" name="document_file" accept=".pdf" required>
                                        </div>
                                        <div class="col-md-12 floating-label">
                                            <textarea class="form-control" name="description_doc_fiscal" rows="2" placeholder=" "></textarea>
                                            <label>Description (optionnel)</label>
                                        </div>
                                        <div class="col-12 text-center">
                                            <button type="submit" class="btn btn-primary"><i class="fas fa-plus-circle me-2"></i>Ajouter Document</button>
                                        </div>
                                    </div>
                                </form>
                                <h5 class="mt-4 mb-3"><i class="fas fa-history me-2" style="color: #FFC107;"></i>Historique des Documents</h5>
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover" id="documentsFiscauxTable">
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>Type</th>
                                                <th>Description</th>
                                                <th>Fichier</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% for doc in documents_fiscaux %}
                                            <tr>
                                                <td>{{ doc.Date }}</td>
                                                <td>{{ doc.Type_Document }}</td>
                                                <td>{{ doc.Description }}</td>
                                                <td>
                                                    {% if doc.Fichier_PDF %}
                                                    <a href="{{ url_for('comptabilite.download_document_fiscal', filename=doc.Fichier_PDF) }}" target="_blank" class="btn btn-sm btn-info"><i class="fas fa-file-download"></i></a>
                                                    {% else %} N/A {% endif %}
                                                </td>
                                                <td>
                                                    <a href="{{ url_for('comptabilite.delete_document_fiscal', index=loop.index0) }}" class="btn btn-sm btn-danger"><i class="fas fa-trash"></i></a>
                                                </td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
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
                    <i class="fas fa-heartbeat me-1"></i>
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
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.1/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.1/js/dataTables.bootstrap5.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0"></script>


    <script>
        document.addEventListener('DOMContentLoaded', () => {
            // Initialisation des onglets Bootstrap
            const tabButtons = document.querySelectorAll('#comptabiliteTab button[data-bs-toggle="tab"]');
            tabButtons.forEach(button => {
                button.addEventListener('click', function(event) {
                    event.preventDefault();
                    const tabTargetId = this.getAttribute('data-bs-target');
                    console.log('Tab button clicked:', this.id, 'Target:', tabTargetId); // Debugging log
                    const tab = new bootstrap.Tab(this);
                    tab.show();
                });
            });

            // Persistance de l'onglet actif et gestion des événements 'shown.bs.tab'
            const storedActiveTab = localStorage.getItem('activeComptabiliteTab');
            const defaultTabButton = document.getElementById('dashboard-tab'); // The dashboard button
            let initialTabToActivate = defaultTabButton;

            if (storedActiveTab) {
                const storedTabButton = document.querySelector(`#comptabiliteTab button[data-bs-target="${storedActiveTab}"]`);
                if (storedTabButton) {
                    initialTabToActivate = storedTabButton;
                }
            }

            // Activate the initial tab and set up event listeners
            const initialTabInstance = new bootstrap.Tab(initialTabToActivate);
            initialTabInstance.show(); // Show the correct tab on load

            tabButtons.forEach(tabEl => {
                tabEl.addEventListener('shown.bs.tab', function(event) {
                    const activatedTabTarget = event.target.getAttribute('data-bs-target');
                    localStorage.setItem('activeComptabiliteTab', activatedTabTarget);
                    console.log('Tab shown:', event.target.id, 'Target:', activatedTabTarget); // Debugging log

                    // Re-initialiser les graphiques Chart.js lorsque l'onglet du tableau de bord est affiché
                    if (activatedTabTarget === '#dashboard') {
                        console.log('Initializing charts for Dashboard tab...'); // Debugging log
                        // Détruire les instances précédentes pour éviter les conflits
                        if (monthlyChart) monthlyChart.destroy();
                        if (revenueByTypeChart) revenueByTypeChart.destroy();
                        if (expensesByCategoryChart) expensesByCategoryChart.destroy();
                        
                        initializeMonthlyChart();
                        initializeRevenueByTypeChart();
                        initializeExpensesByCategoryChart();
                    } else {
                        // Pour les autres onglets, ajuster les colonnes des DataTables
                        console.log('Adjusting DataTables for non-dashboard tab...'); // Debugging log
                        $.fn.DataTable.tables({ visible: true, api: true }).columns.adjust();
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

            // Initialisation des DataTables
            function initializeDataTables() {
                // Initialise les DataTables pour toutes les tables si elles existent
                // Ensure this runs only once or destroys existing instances
                ['#recettesTable', '#depensesTable', '#salairesTable', '#tiersPayantsTable', '#documentsFiscauxTable'].forEach(tableId => {
                    if ($.fn.DataTable.isDataTable(tableId)) {
                        $(tableId).DataTable().destroy(); // Destroy existing instance
                    }
                    $(tableId).DataTable({
                        "language": {
                            "url": "//cdn.datatables.net/plug-ins/1.13.1/i18n/fr-FR.json"
                        },
                        "paging": true,
                        "searching": true,
                        "info": true,
                        "order": []
                    });
                });
            }
            initializeDataTables(); // Call on DOMContentLoaded

            // Variables globales pour les instances de graphique
            let monthlyChart, revenueByTypeChart, expensesByCategoryChart;

            // Définir les valeurs par défaut globales pour Chart.js (inspiré de statistique.py)
            Chart.defaults.color = 'var(--text-color)';
            Chart.defaults.font.family = "'Poppins', sans-serif";
            Chart.defaults.devicePixelRatio = 2;
            if(window.ChartDataLabels){ Chart.register(window.ChartDataLabels); } // Enregistrer le plugin si disponible
            Chart.defaults.plugins.datalabels.font = {weight:'600'};

            // Fonction pour initialiser le graphique de tendance mensuelle (Histogramme)
    function initializeMonthlyChart() {
        const ctx = document.getElementById('monthlyChart').getContext('2d');
        const monthlyData = {{ monthly_data | tojson | safe }};

        const hasRealData = monthlyData.revenues.some(val => val !== 0) ||
                            monthlyData.expenses.some(val => val !== 0) ||
                            monthlyData.profit.some(val => val !== 0);

        const noDataMessageDiv = document.getElementById('monthlyNoDataMessage');

        if (!hasRealData) {
            ctx.canvas.style.display = 'none';
            noDataMessageDiv.style.display = 'flex';
            if (monthlyChart) { monthlyChart.destroy(); monthlyChart = null; }
            return;
        } else {
            ctx.canvas.style.display = 'block';
            noDataMessageDiv.style.display = 'none';
        }

        monthlyChart = new Chart(ctx, {
            type: 'bar', // Changé en 'bar' pour un histogramme
            data: {
                labels: monthlyData.labels,
                datasets: [
                    {
                        label: 'Recettes',
                        data: monthlyData.revenues,
                        backgroundColor: '#4CAF50', // Vert pour les recettes
                        borderColor: '#4CAF50',
                        borderWidth: 1,
                        borderRadius: 4,
                        categoryPercentage: 0.7,
                        barPercentage: 0.8
                    },
                    {
                        label: 'Dépenses',
                        data: monthlyData.expenses,
                        backgroundColor: '#F44336', // Rouge pour les dépenses
                        borderColor: '#F44336',
                        borderWidth: 1,
                        borderRadius: 4,
                        categoryPercentage: 0.7,
                        barPercentage: 0.8
                    },
                    {
                        label: 'Bénéfice Net',
                        data: monthlyData.profit,
                        backgroundColor: '#2196F3', // Bleu pour le bénéfice net
                        borderColor: '#2196F3',
                        borderWidth: 1,
                        borderRadius: 4,
                        categoryPercentage: 0.7,
                        barPercentage: 0.8
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: 'var(--text-color)'
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    // Correction pour le tooltip
                                    label += new Intl.NumberFormat('fr-FR', { style: 'currency', currency: '{{ currency }}', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(context.parsed.y);
                                }
                                return label;
                            }
                        }
                    },
                    // NOUVEAU: Configuration du plugin datalabels
                    datalabels: {
                        color: 'white', // Couleur du texte des labels
                        anchor: 'end', // Position du label (à la fin de la barre)
                        align: 'start', // Alignement du label (juste après la fin)
                        formatter: function(value, context) {
                            // Formater la valeur avec deux décimales
                            if (value === 0) return '';
                            return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: '{{ currency }}', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: 'var(--text-color-light)',
                            autoSkip: false,
                            maxRotation: 45,
                            minRotation: 45
                        },
                        grid: {
                            color: 'rgba(var(--text-color-rgb), 0.1)'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: 'var(--text-color-light)',
                            callback: function(value, index, values) {
                                // Correction pour les tics de l'axe Y
                                return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: '{{ currency }}', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
                            }
                        },
                        grid: {
                            color: 'rgba(var(--text-color-rgb), 0.1)'
                        }
                    }
                },
                indexAxis: 'x',
                parsing: {
                    xAxisKey: 'label',
                    yAxisKey: 'value'
                }
            }
        });
    }
            // Fonction pour initialiser le graphique de répartition des recettes par type d'acte (Camembert)
            function initializeRevenueByTypeChart() {
                const ctx = document.getElementById('revenueByTypeChart').getContext('2d');
                const revenueData = {{ revenue_by_type_data | tojson | safe }};

                const hasRealData = revenueData.data.some(val => val !== 0);
                const noDataMessageDiv = document.getElementById('revenueNoDataMessage');

                if (!hasRealData) {
                    ctx.canvas.style.display = 'none';
                    noDataMessageDiv.style.display = 'flex';
                    if (revenueByTypeChart) { revenueByTypeChart.destroy(); revenueByTypeChart = null; }
                    return;
                } else {
                    ctx.canvas.style.display = 'block';
                    noDataMessageDiv.style.display = 'none';
                }

                revenueByTypeChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: revenueData.labels,
                        datasets: [{
                            data: revenueData.data,
                            backgroundColor: revenueData.colors,
                            hoverOffset: 10,
                            borderColor: 'var(--card-bg)',
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: {
                                    color: 'var(--text-color)'
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        let label = context.label || '';
                                        if (label) {
                                            label += ': ';
                                        }
                                        if (context.parsed !== null) {
                                            label += new Intl.NumberFormat('fr-FR', { style: 'currency', currency: '{{ currency }}' }).format(context.parsed);
                                        }
                                        return label;
                                    }
                                }
                            },
                            datalabels: {
                                color: 'var(--button-text)',
                                formatter: (value, context) => {
                                    const total = context.dataset.data.reduce((acc, val) => acc + val, 0);
                                    const percentage = total > 0 ? (value * 100 / total).toFixed(1) + '%' : '';
                                    return percentage;
                                }
                            }
                        }
                    },
                    plugins: [ChartDataLabels]
                });
            }

            // Fonction pour initialiser le graphique de répartition des dépenses par catégorie (Camembert)
            function initializeExpensesByCategoryChart() {
                const ctx = document.getElementById('expensesByCategoryChart').getContext('2d');
                const expensesData = {{ expenses_by_category_data | tojson | safe }};

                const hasRealData = expensesData.data.some(val => val !== 0);
                const noDataMessageDiv = document.getElementById('expensesNoDataMessage');

                if (!hasRealData) {
                    ctx.canvas.style.display = 'none';
                    noDataMessageDiv.style.display = 'flex';
                    if (expensesByCategoryChart) { expensesByCategoryChart.destroy(); expensesByCategoryChart = null; }
                    return;
                } else {
                    ctx.canvas.style.display = 'block';
                    noDataMessageDiv.style.display = 'none';
                }

                expensesByCategoryChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: expensesData.labels,
                        datasets: [{
                            data: expensesData.data,
                            backgroundColor: expensesData.colors,
                            hoverOffset: 10,
                            borderColor: 'var(--card-bg)',
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: {
                                    color: 'var(--text-color)'
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        let label = context.label || '';
                                        if (label) {
                                            label += ': ';
                                        }
                                        if (context.parsed !== null) {
                                            label += new Intl.NumberFormat('fr-FR', { style: 'currency', currency: '{{ currency }}' }).format(context.parsed);
                                        }
                                        return label;
                                    }
                                }
                            },
                            datalabels: {
                                color: 'var(--button-text)',
                                formatter: (value, context) => {
                                    const total = context.dataset.data.reduce((acc, val) => acc + val, 0);
                                    const percentage = total > 0 ? (value * 100 / total).toFixed(1) + '%' : '';
                                    return percentage;
                                }
                            }
                        }
                    },
                    plugins: [ChartDataLabels]
                });
            }

            // Initialiser tous les graphiques si l'onglet du tableau de bord est actif au chargement
            // et si la page n'a pas été chargée via un filtre de mois (pour éviter la double initialisation)
            // L'initialisation se fera via l'événement 'shown.bs.tab' ou si le monthFilter est présent
            const initialSelectedMonth = "{{ selected_month | default('') }}";
            if (document.getElementById('dashboard-tab').classList.contains('active')) {
                // If a month filter is present in the URL, initialize charts immediately.
                // Otherwise, rely on the 'shown.bs.tab' event for initial load.
                if (initialSelectedMonth) {
                    initializeMonthlyChart();
                    initializeRevenueByTypeChart();
                    initializeExpensesByCategoryChart();
                } else {
                    // If no month filter, check if the tab is truly active and init
                    // This handles the first page load when no filter is applied yet
                    if (document.getElementById('dashboard').classList.contains('show')) {
                        initializeMonthlyChart();
                        initializeRevenueByTypeChart();
                        initializeExpensesByCategoryChart();
                    }
                }
            }


            // Floating Labels behavior
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

            // Confirmer suppression pour toutes les actions de suppression
            document.querySelectorAll('.btn-danger[href*="delete_"]').forEach(button => {
                button.addEventListener('click', function(e) {
                    e.preventDefault();
                    const deleteUrl = this.href;
                    Swal.fire({
                        title: 'Êtes-vous sûr ?',
                        text: "Cette action est irréversible !",
                        icon: 'warning',
                        showCancelButton: true,
                        confirmButtonColor: '#d33',
                        cancelButtonColor: '#3085d6',
                        confirmButtonText: 'Oui, supprimer !',
                        cancelButtonText: 'Annuler'
                    }).then((result) => {
                        if (result.isConfirmed) {
                            window.location.href = deleteUrl;
                        }
                    });
                });
            });

            // Gérer la fermeture de la modale d'exportation de salaires
            document.getElementById('confirmExportBtn').addEventListener('click', function() {
                var exportModal = bootstrap.Modal.getInstance(document.getElementById('exportSalairesModal'));
                if (exportModal) {
                    exportModal.hide();
                    Swal.fire({
                        icon: 'success',
                        title: 'Exportation réussie !',
                        text: 'Le fichier Excel des salaires a été exporté avec succès.',
                        confirmButtonText: 'OK'
                    });
                }
            });
        });
    </script>
</body>
</html>
"""