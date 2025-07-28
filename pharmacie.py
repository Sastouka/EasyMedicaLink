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
                            # MISE À JOUR: Ajout de 'Date_Enregistrement'
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
    # MISE À JOUR: Ajout de 'Date_Enregistrement'
    columns = ['Code_Produit', 'Nom', 'Type', 'Usage', 'Quantité', 'Prix_Achat', 'Prix_Vente', 'Fournisseur', 'Date_Expiration', 'Seuil_Alerte', 'Date_Enregistrement']
    numeric_cols = ['Quantité', 'Prix_Achat', 'Prix_Vente', 'Seuil_Alerte']
    df = _load_sheet_data(file_path, 'Inventaire', columns, numeric_cols)
    
    # Convertir 'Date_Expiration' en objets datetime, en forçant les erreurs
    df['Date_Expiration'] = pd.to_datetime(df['Date_Expiration'], errors='coerce')
    # Convertir 'Date_Enregistrement' en objets datetime, en forçant les erreurs
    df['Date_Enregistrement'] = pd.to_datetime(df['Date_Enregistrement'], errors='coerce')
    
    return df

def save_pharmacie_inventory(df, file_path):
    return _save_sheet_data(df, file_path, 'Inventaire', ALL_PHARMACIE_SHEETS)

def load_pharmacie_movements(file_path):
    columns = ['Date', 'Code_Produit', 'Nom_Produit', 'Type_Mouvement', 'Quantité_Mouvement', 'Nom_Responsable', 'Prenom_Responsable', 'Telephone_Responsable']
    numeric_cols = ['Quantité_Mouvement']
    return _load_sheet_data(file_path, 'Mouvements', columns, numeric_cols)

def save_pharmacie_movements(df, file_path):
    return _save_sheet_data(df, file_path, 'Mouvements', ALL_PHARMACIE_SHEETS)

# --- NOUVEAU: Fonctions utilitaires pour Comptabilite.xlsx (répliquées de comptabilite.py) ---

# Définir les feuilles attendues pour Comptabilite.xlsx. Doivent correspondre à la définition interne de comptabilite.py.
_ALL_COMPTA_SHEETS = ['Recettes', 'Depenses', 'Salaires', 'TiersPayants', 'DocumentsFiscaux']

def _load_comptabilite_sheet_data(file_path, sheet_name, default_columns, numeric_cols=[]):
    """
    Charge les données d'une feuille spécifique de Comptabilite.xlsx.
    Initialise la feuille avec les colonnes par défaut si elle n'existe pas ou est vide.
    """
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
    """
    Sauvegarde un DataFrame dans une feuille spécifique de Comptabilite.xlsx,
    en préservant les autres feuilles.
    """
    try:
        existing_sheets_data = {}
        if os.path.exists(file_path):
            existing_sheets_data = pd.read_excel(file_path, sheet_name=None, dtype=str)
        
        existing_sheets_data[sheet_name_to_update] = df_to_save

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer: # Utiliser openpyxl pour l'écriture multi-feuilles
            for s_name in all_sheet_names:
                if s_name in existing_sheets_data and not existing_sheets_data[s_name].empty:
                    existing_sheets_data[s_name].to_excel(writer, sheet_name=s_name, index=False)
                else:
                    # Créer des feuilles vides avec des en-têtes si elles n'existent pas
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

# Définir les colonnes pour la feuille 'Depenses' comme attendu par Comptabilite.xlsx
_DEPENSES_COLUMNS = ["Date", "Categorie", "Description", "Montant", "Justificatif_Fichier"]

def _add_expense_to_comptabilite(expense_data):
    """
    Ajoute une nouvelle entrée de dépense à la feuille 'Depenses' dans Comptabilite.xlsx.
    Cette fonction est autonome dans pharmacie.py.
    """
    if utils.EXCEL_FOLDER is None:
        print("Erreur: utils.EXCEL_FOLDER non défini. Impossible d'enregistrer la dépense comptable.")
        return False

    # Construire le chemin vers Comptabilite.xlsx basé sur le dossier Excel dynamique
    comptabilite_excel_file_path = os.path.join(utils.EXCEL_FOLDER, 'Comptabilite.xlsx')
    
    # Charger les données 'Depenses' existantes en utilisant l'aide interne
    df_depenses = _load_comptabilite_sheet_data(
        comptabilite_excel_file_path,
        'Depenses',
        _DEPENSES_COLUMNS,
        numeric_cols=['Montant']
    )

    # Ajouter les nouvelles données de dépense, en assurant l'ordre des colonnes
    new_depense_df = pd.DataFrame([expense_data], columns=_DEPENSES_COLUMNS)
    updated_depenses_df = pd.concat([df_depenses, new_depense_df], ignore_index=True)

    # Sauvegarder toutes les feuilles dans Comptabilite.xlsx en utilisant l'aide interne
    return _save_comptabilite_sheet_data(
        updated_depenses_df,
        comptabilite_excel_file_path,
        'Depenses',
        _ALL_COMPTA_SHEETS
    )

# --- FIN NOUVELLES AIDES ---


# Fonctions de génération de PDF
class PDF(FPDF):
    """
    Classe personnalisée héritant de FPDF pour la génération de rapports PDF.
    Inclut des méthodes pour l'en-tête, le pied de page, les titres de chapitre
    et une méthode améliorée pour la création de tableaux.
    """
    def __init__(self, orientation='P', unit='mm', format='A4'):
        super().__init__(orientation, unit, format)
        # Tenter d'ajouter les polices Arial. Si elles ne sont pas trouvées, FPDF utilisera Helvetica par défaut.
        try:
            self.add_font('Arial', '', 'C:\\Windows\\Fonts\\arial.ttf', uni=True)
            self.add_font('Arial', 'B', 'C:\\Windows\\Fonts\\arialbd.ttf', uni=True)
            self.add_font('Arial', 'I', 'C:\\Windows\\Fonts\\ariali.ttf', uni=True)
            self.add_font('Arial', 'BI', 'C:\\Windows\\Fonts\\arialbi.ttf', uni=True)
            self.font_family = 'Arial'
        except RuntimeError: # FPDF lève une RuntimeError si le fichier de police n'est pas trouvé
            print("AVERTISSEMENT: Polices Arial non trouvées, utilisation des polices FPDF par défaut (Helvetica).")
            self.font_family = 'Helvetica'
        self.title = '' # Initialiser le titre

    def header(self):
        """
        Définit le contenu de l'en-tête de chaque page du PDF.
        Affiche le titre du document centré.
        """
        self.set_font(self.font_family, 'B', 15)
        # Centrer le titre sur la page, en tenant compte de l'orientation paysage
        page_width = self.w
        title_width = self.get_string_width(self.title if self.title else '')
        self.set_x((page_width - title_width) / 2)
        self.cell(title_width, 10, self.title if self.title else '', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        """
        Définit le contenu du pied de page de chaque page du PDF.
        Affiche le numéro de page centré.
        """
        self.set_y(-15) # Position à 15 mm du bas
        self.set_font(self.font_family, 'I', 8) # Police italique, taille 8
        # Numéro de page (Page X/total)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

    def chapter_title(self, title):
        """
        Ajoute un titre de chapitre au document.
        """
        self.set_font(self.font_family, 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(5)

    def create_table_improved(self, header, data, col_widths, align='C'):
        """
        Crée un tableau dynamique avec gestion des retours à la ligne et des sauts de page.
        Les noms des colonnes et le texte des lignes ne débordent pas au-delà des limites.
        
        Args:
            header (list): Liste des titres de colonnes.
            data (list of lists): Les données du tableau.
            col_widths (list): Largeurs des colonnes en mm (doit correspondre à la longueur de header).
            align (str): Alignement du texte dans les cellules ('L', 'C', 'R').
        """
        # Paramètres généraux du tableau
        self.set_fill_color(200, 220, 255) # Bleu clair pour l'en-tête
        self.set_text_color(0, 0, 0)
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.3)
        self.set_font(self.font_family, 'B', 8) # Police pour l'en-tête (en gras)

        table_width = sum(col_widths)
        page_width = self.w - self.l_margin - self.r_margin 
        # Calcule la position X de début du tableau pour le centrer
        start_x_table = self.l_margin + (page_width - table_width) / 2 

        # --- Calculer la hauteur maximale pour l'en-tête du tableau ---
        # Cette hauteur sera utilisée pour toutes les cellules de l'en-tête,
        # permettant aux noms de colonnes longs de s'enrouler.
        max_header_height = 8  # Hauteur par défaut pour une ligne d'en-tête
        temp_y_before_measure_header = self.get_y() # Sauvegarde la position Y actuelle avant mesure

        # Simuler le dessin de chaque cellule d'en-tête pour trouver la hauteur maximale nécessaire
        for i, col in enumerate(header):
            # Positionne temporairement X pour la mesure (important pour le calcul de multi_cell)
            self.set_x(start_x_table + sum(col_widths[:i])) 
            # Mesure la hauteur en utilisant multi_cell avec dry_run=True (ne dessine pas)
            # col_widths[i] - 1 offre une marge plus généreuse pour le wrap de l'en-tête
            self.multi_cell(col_widths[i] - 1, 8, col, 0, 'C', 0, dry_run=True)
            measured_header_height = self.get_y() - temp_y_before_measure_header
            # Restaure la position Y après la mesure pour la prochaine cellule "virtuelle" de la même ligne
            self.set_y(temp_y_before_measure_header) 
            if measured_header_height > max_header_height:
                max_header_height = measured_header_height
        
        # Ajoute un rembourrage supplémentaire pour un meilleur rendu visuel des en-têtes enroulés
        max_header_height += 1.5 

        # --- Dessine l'en-tête du tableau avec les hauteurs calculées ---
        current_x_for_header_drawing = start_x_table
        for i, col in enumerate(header):
            # Dessine le fond et la bordure de la cellule d'en-tête
            self.set_xy(current_x_for_header_drawing, temp_y_before_measure_header)
            self.cell(col_widths[i], max_header_height, '', 1, 0, 'C', 1) 
            
            # Dessine le texte de l'en-tête à l'intérieur de la cellule
            # Ajuste la position X et Y pour un petit rembourrage (0.5mm)
            self.set_xy(current_x_for_header_drawing + 0.5, temp_y_before_measure_header + 0.5) 
            # Utilise multi_cell pour l'en-tête afin de gérer le retour à la ligne
            # La largeur du texte est `col_widths[i] - 1` pour laisser 0.5mm de padding de chaque côté
            self.multi_cell(col_widths[i] - 1, 8, col, 0, 'C', 0) 

            current_x_for_header_drawing += col_widths[i] # Avance pour la prochaine cellule d'en-tête
        
        # Déplace le curseur Y sous la ligne d'en-tête et réinitialise X
        self.set_y(temp_y_before_measure_header + max_header_height)
        self.set_x(start_x_table)
        
        # Passe à la police normale pour les données du tableau
        self.set_font(self.font_family, '', 8)
        self.set_fill_color(240, 248, 255) # Couleur de remplissage pour les lignes de données
        fill = False # Alternance de couleur de remplissage
        # Hauteur de ligne par défaut pour les cellules de données, ajustée pour un meilleur espacement
        line_height = 6.5 # Légèrement augmenté pour éviter les chevauchements

        # Itère sur chaque ligne de données pour dessiner le tableau
        for row_data in data:
            max_row_height = line_height # Réinitialise la hauteur maximale pour la ligne actuelle
            
            # --- Phase 1: Calculer la hauteur maximale pour la ligne de données actuelle (sans dessiner) ---
            temp_y_before_measure = self.get_y() # Sauvegarde la position Y actuelle
            
            for i, item in enumerate(row_data):
                cell_width = col_widths[i]
                text_content = str(item)
                
                # Positionne temporairement X pour la mesure (important pour le calcul de multi_cell)
                self.set_x(start_x_table + sum(col_widths[:i])) 
                
                # Mesure la hauteur en utilisant multi_cell avec dry_run=True (ne dessine pas)
                # cell_width - 1 laisse 0.5mm de padding de chaque côté du texte
                self.multi_cell(cell_width - 1, line_height, text_content, 0, align, 0, dry_run=True) 
                measured_height = self.get_y() - temp_y_before_measure
                
                # Restaure la position Y après la mesure pour la prochaine cellule "virtuelle" de la même ligne
                self.set_y(temp_y_before_measure) 

                if measured_height > max_row_height:
                    max_row_height = measured_height
            
            # Restaure la position X après toutes les mesures pour la ligne
            self.set_x(start_x_table)

            # Ajoute un petit rembourrage pour un meilleur rendu visuel vertical
            max_row_height += 1.5 

            # --- Phase 2: Vérifier le saut de page et dessiner la ligne ---
            # Si la ligne actuelle déborde, ajoute une nouvelle page et redessine l'en-tête
            # self.b_margin est la marge inférieure, self.h est la hauteur totale de la page
            if self.get_y() + max_row_height + self.b_margin > self.h: 
                self.add_page(orientation='L') 
                self.set_x(start_x_table)
                self.set_fill_color(200, 220, 255) # Couleur de l'en-tête
                self.set_font(self.font_family, 'B', 8) # Police de l'en-tête
                
                # Redessine l'en-tête sur la nouvelle page avec la même logique de multi_cell
                temp_y_after_page_break = self.get_y()
                current_x_for_header_drawing_on_new_page = start_x_table
                for i, col in enumerate(header):
                    self.set_xy(current_x_for_header_drawing_on_new_page, temp_y_after_page_break)
                    self.cell(col_widths[i], max_header_height, '', 1, 0, 'C', 1) 
                    self.set_xy(current_x_for_header_drawing_on_new_page + 0.5, temp_y_after_page_break + 0.5)
                    self.multi_cell(col_widths[i] - 1, 8, col, 0, 'C', 0)
                    current_x_for_header_drawing_on_new_page += col_widths[i]
                
                self.set_y(temp_y_after_page_break + max_header_height)
                self.set_x(start_x_table) # Réinitialise X pour la première cellule de la nouvelle ligne de données
                
                # Rétablit les paramètres pour les lignes de données
                self.set_font(self.font_family, '', 8)
                self.set_fill_color(240, 248, 255) 

            # Obtenir la position Y de début réelle pour le dessin de cette ligne de données
            actual_start_y_row = self.get_y()
            
            # --- Phase 3: Dessiner les boîtes de cellule (arrière-plan et bordure) pour toute la ligne ---
            # Dessine toutes les bordures et fonds de cellules pour la ligne en cours, en utilisant max_row_height
            current_x_for_box_drawing = start_x_table
            for i in range(len(row_data)):
                self.set_xy(current_x_for_box_drawing, actual_start_y_row)
                self.cell(col_widths[i], max_row_height, '', 1, 0, 'C', fill) # Dessine l'arrière-fond et la bordure
                current_x_for_box_drawing += col_widths[i]
            
            # --- Phase 4: Dessiner le contenu texte de chaque cellule ---
            # Dessine le texte de chaque cellule DANS les boîtes précédemment dessinées
            current_x_for_text_drawing = start_x_table
            for i, item in enumerate(row_data):
                cell_width = col_widths[i]
                text_content = str(item)

                # Positionne le curseur pour dessiner le contenu texte *à l'intérieur* de la boîte de cellule
                # Ajoute un petit rembourrage à gauche et en haut pour le texte (0.5mm)
                text_x_pos = current_x_for_text_drawing + 0.5
                text_y_pos = actual_start_y_row + 0.5

                self.set_xy(text_x_pos, text_y_pos)
                
                # Dessine le contenu texte en utilisant multi_cell. Pas de bordure/remplissage ici (0, 0)
                # Soustrait le double du rembourrage (1mm total) de la largeur pour s'assurer que le texte reste dans les limites.
                self.multi_cell(cell_width - 1, line_height, text_content, 0, align, 0)
                
                # Avance X pour le dessin du texte de la cellule suivante
                current_x_for_text_drawing += cell_width
            
            # Enfin, déplace le curseur à la position Y de début de la ligne suivante
            self.set_y(actual_start_y_row + max_row_height)
            self.set_x(start_x_table) # Réinitialise X pour le début de la ligne suivante

            fill = not fill # Change la couleur de remplissage pour la prochaine ligne (effet zébré)


def generate_inventory_pdf(df, currency):
    """
    Génère un rapport d'inventaire de pharmacie au format PDF en paysage.
    
    Args:
        df (pd.DataFrame): DataFrame contenant les données de l'inventaire.
        currency (str): Symbole de la devise (ex: '€', '$', 'MAD').
        
    Returns:
        io.BytesIO: Un objet BytesIO contenant le PDF généré.
    """
    print(f"DEBUG generate_inventory_pdf: Début de la génération du PDF d'inventaire.")
    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15) 
    pdf.title = 'Rapport d\'Inventaire du Stock' 
    pdf.add_page() 

    pdf.set_font(pdf.font_family, '', 10)
    pdf.cell(0, 10, f'Date du rapport: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'L')
    pdf.ln(5)

    if not df.empty:
        print(f"DEBUG generate_inventory_pdf: DataFrame d'inventaire non vide ({len(df)} lignes).")
        # MISE À JOUR: Ajout de 'Date Enreg.' dans l'en-tête
        header = ['Code Prod.', 'Nom', 'Type', 'Usage', 'Qté', 
                  f'Prix Ach. ({currency})', f'Prix Vte. ({currency})', 
                  'Fournisseur', 'Date Exp.', 'Seuil Al.', 'Statut', 'Date Enreg.']

        pdf_data = []
        for index, row in df.iterrows():
            product_status = ""
            if row['Quantité'] == 0:
                product_status = "Rupture"
            elif row['Quantité'] <= row['Seuil_Alerte']:
                product_status = "Stock Bas"
            else:
                product_status = "En Stock"
            
            # Formate les valeurs numériques (prix) et les dates
            prix_achat_formatted = "%.2f" % float(row['Prix_Achat']) if pd.notna(row['Prix_Achat']) else "N/A"
            prix_vente_formatted = "%.2f" % float(row['Prix_Vente']) if pd.notna(row['Prix_Vente']) else "N/A"
            
            date_exp_formatted = ""
            if pd.notna(row['Date_Expiration']):
                if isinstance(row['Date_Expiration'], datetime):
                    date_exp_formatted = row['Date_Expiration'].strftime('%Y-%m-%d')
                elif isinstance(row['Date_Expiration'], pd.Timestamp): # Gérer les timestamps de pandas
                    date_exp_formatted = row['Date_Expiration'].strftime('%Y-%m-%d')
                else:
                    date_exp_formatted = str(row['Date_Expiration'])
            else:
                date_exp_formatted = "N/A"

            # MISE À JOUR: Formatage de Date_Enregistrement
            date_enregistrement_formatted = ""
            if pd.notna(row['Date_Enregistrement']):
                if isinstance(row['Date_Enregistrement'], datetime):
                    date_enregistrement_formatted = row['Date_Enregistrement'].strftime('%Y-%m-%d')
                elif isinstance(row['Date_Enregistrement'], pd.Timestamp):
                    date_enregistrement_formatted = row['Date_Enregistrement'].strftime('%Y-%m-%d')
                else:
                    date_enregistrement_formatted = str(row['Date_Enregistrement'])
            else:
                date_enregistrement_formatted = "N/A"


            pdf_data.append([
                str(row['Code_Produit']),
                str(row['Nom']),
                str(row['Type']),
                str(row['Usage']),
                str(row['Quantité']),
                prix_achat_formatted,
                prix_vente_formatted,
                str(row['Fournisseur']),
                date_exp_formatted,
                str(row['Seuil_Alerte']),
                product_status,
                date_enregistrement_formatted # Ajout de la date d'enregistrement
            ])
        
        # Calcul dynamique des largeurs de colonnes
        # page_width_available = 297 (A4 landscape) - 10 (left margin) - 10 (right margin) = 277 mm
        page_width_available = pdf.w - pdf.l_margin - pdf.r_margin
        
        # Largeur minimale par colonne pour la lisibilité
        min_col_width = 15 
        
        # Calculer la largeur maximale nécessaire pour chaque colonne (en-tête et données)
        col_max_widths = []
        pdf.set_font(pdf.font_family, 'B', 8) # Pour mesurer les en-têtes
        for i, h in enumerate(header):
            max_width_for_col = pdf.get_string_width(h) # Largeur de l'en-tête
            
            # Parcourir les données pour trouver la plus grande largeur dans cette colonne
            for row in pdf_data:
                pdf.set_font(pdf.font_family, '', 8) # Set font for content
                cell_content_width = pdf.get_string_width(str(row[i]))
                if cell_content_width > max_width_for_col:
                    max_width_for_col = cell_content_width
            
            col_max_widths.append(max_width_for_col + 4) # Ajouter un peu de padding
        
        # Ajuster les largeurs pour qu'elles rentrent dans la page
        total_calculated_width = sum(col_max_widths)
        col_widths = []
        if total_calculated_width > page_width_available:
            # Si trop large, réduire proportionnellement
            scaling_factor = page_width_available / total_calculated_width
            col_widths = [max(min_col_width, w * scaling_factor) for w in col_max_widths]
        else:
            # Si suffisamment d'espace, distribuer l'espace restant
            remaining_space = page_width_available - total_calculated_width
            # Distribuer le reste uniformément
            col_widths = [w + (remaining_space / len(header)) for w in col_max_widths]
            col_widths = [max(min_col_width, w) for w in col_widths] # Assurer la largeur minimale


        # Appel de la fonction de création de tableau améliorée
        pdf.create_table_improved(header, pdf_data, col_widths, align='C') 
    else:
        print("DEBUG generate_inventory_pdf: DataFrame d'inventaire vide. Le PDF sera vide.")
        pdf.set_font(pdf.font_family, 'I', 12)
        pdf.cell(0, 10, "Aucun produit en stock.", 0, 1, 'C')

    output = io.BytesIO()
    pdf.output(output, 'S') # Génère le PDF en tant que chaîne (représentation binaire)
    output.seek(0) # Rembobine le pointeur au début du flux
    print(f"DEBUG generate_inventory_pdf: PDF d'inventaire généré avec succès.")
    return output

def generate_movements_pdf(df):
    """
    Génère un rapport des mouvements de stock au format PDF en paysage.
    
    Args:
        df (pd.DataFrame): DataFrame contenant les données des mouvements de stock.
        
    Returns:
        io.BytesIO: Un objet BytesIO contenant le PDF généré.
    """
    print(f"DEBUG generate_movements_pdf: Début de la génération du PDF des mouvements.")
    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15) # Active le saut de page automatique
    pdf.title = 'Rapport des Mouvements de Stock' # Définit le titre du document
    pdf.add_page() # Ajoute la première page

    pdf.set_font(pdf.font_family, '', 10)
    pdf.cell(0, 10, f'Date du rapport: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'L')
    pdf.ln(5)

    if not df.empty:
        print(f"DEBUG generate_movements_pdf: DataFrame de mouvements non vide ({len(df)} lignes).")
        # Définit les en-têtes abrégés
        header = ['Date', 'Code Prod.', 'Nom Prod.', 'Type Movt.', 'Qté', 'Nom Resp.', 'Prénom Resp.', 'Téléphone']

        # Convertit les données du DataFrame en liste de listes pour FPDF
        # Assurez-vous que toutes les colonnes sont traitées comme des chaînes de caractères
        pdf_data = []
        for index, row in df.iterrows():
            date_formatted = ""
            if isinstance(row['Date'], (datetime, pd.Timestamp)):
                date_formatted = row['Date'].strftime('%Y-%m-%d %H:%M')
            else:
                date_formatted = str(row['Date'])

            pdf_data.append([
                date_formatted,
                str(row['Code_Produit']),
                str(row['Nom_Produit']),
                str(row['Type_Mouvement']),
                str(row['Quantité_Mouvement']),
                str(row['Nom_Responsable']),
                str(row['Prenom_Responsable']),
                str(row['Telephone_Responsable'])
            ])
        
        # Calcul dynamique des largeurs de colonnes
        page_width_available = pdf.w - pdf.l_margin - pdf.r_margin
        min_col_width = 15 # Largeur minimale par colonne

        col_max_widths = []
        pdf.set_font(pdf.font_family, 'B', 8) # Pour mesurer les en-têtes
        for i, h in enumerate(header):
            max_width_for_col = pdf.get_string_width(h) # Largeur de l'en-tête
            
            # Parcourir les données pour trouver la plus grande largeur dans cette colonne
            for row in pdf_data:
                pdf.set_font(pdf.font_family, '', 8) # Set font for content
                cell_content_width = pdf.get_string_width(str(row[i]))
                if cell_content_width > max_width_for_col:
                    max_width_for_col = cell_content_width
            
            col_max_widths.append(max_width_for_col + 4) # Ajouter un peu de padding
        
        # Ajuster les largeurs pour qu'elles rentrent dans la page
        total_calculated_width = sum(col_max_widths)
        col_widths = []
        if total_calculated_width > page_width_available:
            # Si trop large, réduire proportionnellement
            scaling_factor = page_width_available / total_calculated_width
            col_widths = [max(min_col_width, w * scaling_factor) for w in col_max_widths]
        else:
            # Si suffisamment d'espace, distribuer l'espace restant
            remaining_space = page_width_available - total_calculated_width
            col_widths = [w + (remaining_space / len(header)) for w in col_max_widths]
            col_widths = [max(min_col_width, w) for w in col_widths] # Assurer la largeur minimale

        # Appel de la fonction de création de tableau améliorée
        pdf.create_table_improved(header, pdf_data, col_widths, align='C') 
    else:
        print("DEBUG generate_movements_pdf: DataFrame de mouvements vide. Le PDF sera vide.")
        pdf.set_font(pdf.font_family, 'I', 12)
        pdf.cell(0, 10, "Aucun mouvement enregistré.", 0, 1, 'C')

    output = io.BytesIO()
    pdf.output(output, 'S') # Génère le PDF en mémoire
    output.seek(0) # Rembobine le pointeur
    print(f"DEBUG generate_movements_pdf: PDF des mouvements généré avec succès.")
    return output

# Route pour la page d'accueil de la pharmacie
@pharmacie_bp.route('/')
def home_pharmacie():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    # Assurez-vous que les répertoires dynamiques sont définis via utils.py
    if utils.EXCEL_FOLDER is None:
        if 'email' in session:
            utils.set_dynamic_base_dir(session['email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))

    # Assurez-vous que le fichier Pharmacie.xlsx est complet (avec toutes les feuilles)
    initialize_pharmacie_excel_file_if_not_exists()

    # Chemin du fichier Excel unique pour la pharmacie
    # PHARMACIE_EXCEL_FILE est maintenant global et défini par @pharmacie_bp.before_request
    global PHARMACIE_EXCEL_FILE 

    config = utils.load_config()
    session['theme'] = config.get('theme', theme.DEFAULT_THEME)
    
    # Get currency from config, default to 'MAD' if not set
    currency = config.get('currency', 'MAD') 

    host_address = f"http://{utils.LOCAL_IP}:3000"
    current_date = datetime.now().strftime("%Y-%m-%d")

    inventory_df = load_pharmacie_inventory(PHARMACIE_EXCEL_FILE)
    movements_df = load_pharmacie_movements(PHARMACIE_EXCEL_FILE)

    total_products = len(inventory_df)

    # Identifier les produits en stock bas
    low_stock_alerts = inventory_df[inventory_df['Quantité'] <= inventory_df['Seuil_Alerte']].to_dict(orient='records')

    # Identifier les produits expirés
    current_date_dt = datetime.now()
    expired_products = inventory_df[
        (inventory_df['Date_Expiration'].notna()) & 
        (inventory_df['Date_Expiration'] < current_date_dt)
    ].to_dict(orient='records')

    # Récupérer les 10 derniers mouvements
    recent_movements = movements_df.sort_values(by='Date', ascending=False).head(10).to_dict(orient='records')

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
        pharmacie_template,
        config=config,
        theme_vars=theme.current_theme(),
        theme_names=list(theme.THEMES.keys()),
        host_address=host_address,
        current_date=current_date,
        total_products=total_products,
        low_stock_alerts=low_stock_alerts,
        expired_products=expired_products, # NOUVEAU PARAMÈTRE
        recent_movements=recent_movements,
        inventory=inventory_df.to_dict(orient='records'), # Passer l'inventaire complet pour le tableau
        movements_history=movements_df.to_dict(orient='records'), # Passer l'historique complet pour le tableau
        currency=currency, # Pass currency to template
        # Pass user's name/phone from session for pre-filling responsible fields
        user_nom=session.get('user_nom', ''),
        user_prenom=session.get('user_prenom', ''),
        user_phone=session.get('user_phone', ''),
        # --- PASSER LA NOUVELLE VARIABLE AU TEMPLATE ---
        logged_in_doctor_name=logged_in_full_name # Utilise le même nom de variable que dans main_template pour cohérence
        # --- FIN DU PASSAGE ---
    )
    
# Route pour ajouter ou modifier un produit
@pharmacie_bp.route('/add_or_update_product', methods=['POST'])
def add_or_update_product():
    # ... (code existant pour la vérification de session, les imports, etc.) ...

    # Assurez-vous que les répertoires dynamiques sont définis via utils.py
    if utils.EXCEL_FOLDER is None:
        if 'admin_email' in session:
            utils.set_dynamic_base_dir(session['admin_email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('pharmacie.home_pharmacie'))

    # PHARMACIE_EXCEL_FILE est maintenant global et défini par @pharmacie_bp.before_request
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
            'Code_Produit': code_produit,
            'Nom': nom_produit,
            'Type': type_produit,
            'Usage': usage_produit,
            'Quantité': quantite,
            'Prix_Achat': prix_achat,
            'Prix_Vente': prix_vente,
            'Fournisseur': fournisseur,
            'Date_Expiration': date_expiration,
            'Seuil_Alerte': seuil_alerte,
            'Date_Enregistrement': datetime.now().strftime("%Y-%m-%d")
        }
        inventory_df = pd.concat([inventory_df, pd.DataFrame([new_product_row])], ignore_index=True)


    if save_pharmacie_inventory(inventory_df, PHARMACIE_EXCEL_FILE):
        # Logique pour enregistrer la dépense dans Comptabilite.xlsx
        if is_new_entry:
            try:
                depense_data = {
                    "Date": datetime.now().strftime("%Y-%m-%d"),
                    "Categorie": "Achats de consommables médicaux",
                    "Description": f"Achat de {quantite} unités de {nom_produit} (Code: {code_produit})",
                    "Montant": prix_achat * quantite,  # Le montant est le prix d'achat * la quantité
                    "Justificatif_Fichier": ""
}

                if _add_expense_to_comptabilite(depense_data):
                    flash(f"Dépense pour l'achat de '{nom_produit}' enregistrée dans la comptabilité.", "info")
                else:
                    flash(f"Erreur lors de l'enregistrement de la dépense pour '{nom_produit}' dans la comptabilité.", "warning")

            except Exception as e:
                flash(f"Erreur inattendue lors de l'enregistrement de la dépense comptable : {e}", "danger")
                print(f"Erreur inattendue lors de l'enregistrement de la dépense comptable : {e}")

        if original_product_code:
            flash(f"Produit '{nom_produit}' mis à jour avec succès !", "success")
        else:
            flash(f"Produit '{nom_produit}' ajouté avec succès !", "success")
    else:
        flash(f"Erreur lors de la sauvegarde du produit '{nom_produit}'.", "danger")

    return redirect(url_for('pharmacie.home_pharmacie'))

# Route pour supprimer un produit
# Route pour supprimer un produit
@pharmacie_bp.route('/delete_product', methods=['POST'])
def delete_product():
    if 'email' not in session:
        return jsonify(success=False, message="Non autorisé"), 401

    if utils.EXCEL_FOLDER is None:
        if 'email' in session:
            utils.set_dynamic_base_dir(session['email'])
        else:
            return jsonify(success=False, message="Erreur: Répertoires non définis. Reconnexion nécessaire."), 401
            
    # PHARMACIE_EXCEL_FILE est maintenant global et défini par @pharmacie_bp.before_request
    global PHARMACIE_EXCEL_FILE 

    product_code = request.form.get('product_code').strip()

    inventory_df = load_pharmacie_inventory(PHARMACIE_EXCEL_FILE)

    if product_code not in inventory_df['Code_Produit'].values:
        return jsonify(success=False, message=f"Produit avec le code '{product_code}' introuvable."), 404

    # 1. Sauvegarder les informations du produit pour la suppression des dépenses
    product_name_to_delete = inventory_df[inventory_df['Code_Produit'] == product_code]['Nom'].iloc[0]

    # Utiliser .copy() pour éviter SettingWithCopyWarning si des opérations ultérieures modifient le df original
    inventory_df_filtered = inventory_df[inventory_df['Code_Produit'] != product_code].copy()

    if save_pharmacie_inventory(inventory_df_filtered, PHARMACIE_EXCEL_FILE): # Sauvegarder le DataFrame filtré
        # 2. Supprimer les entrées de dépenses correspondantes dans Comptabilite.xlsx
        comptabilite_excel_file_path = os.path.join(utils.EXCEL_FOLDER, 'Comptabilite.xlsx')
        _DEPENSES_COLUMNS = ["Date", "Categorie", "Description", "Montant", "Justificatif_Fichier"]
        _ALL_COMPTA_SHEETS = ['Recettes', 'Depenses', 'Salaires', 'TiersPayants', 'DocumentsFiscaux']

        try:
            df_depenses = _load_comptabilite_sheet_data(comptabilite_excel_file_path, 'Depenses', _DEPENSES_COLUMNS, numeric_cols=['Montant'])
            
            # Utiliser la description pour identifier les dépenses liées au produit
            depenses_to_delete = df_depenses['Description'].str.contains(f"Achat de.*\(Code: {product_code}\)").fillna(False)

            # Créer un nouveau DataFrame sans les lignes à supprimer
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
# Route pour enregistrer un mouvement de stock
@pharmacie_bp.route('/record_movement', methods=['POST'])
def record_movement():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    if utils.EXCEL_FOLDER is None:
        if 'email' in session:
            utils.set_dynamic_base_dir(session['email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))
            
    # PHARMACIE_EXCEL_FILE est maintenant global et défini par @pharmacie_bp.before_request
    global PHARMACIE_EXCEL_FILE 

    product_code = request.form.get('product_code').strip()
    movement_type = request.form.get('movement_type').strip()
    quantity_movement = int(request.form.get('quantity_movement'))
    
    # Get responsible details from form
    nom_responsable = request.form.get('nom_responsable', '').strip()
    prenom_responsable = request.form.get('prenom_responsable', '').strip()
    telephone_responsable = request.form.get('telephone_responsable', '').strip()

    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    inventory_df = load_pharmacie_inventory(PHARMACIE_EXCEL_FILE)
    movements_df = load_pharmacie_movements(PHARMACIE_EXCEL_FILE)

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
        new_movement = {
            'Date': current_date,
            'Code_Produit': product_code,
            'Nom_Produit': product_name,
            'Type_Mouvement': movement_type,
            'Quantité_Mouvement': quantity_movement,
            'Nom_Responsable': nom_responsable, # New field
            'Prenom_Responsable': prenom_responsable, # New field
            'Telephone_Responsable': telephone_responsable # New field
        }
        movements_df = pd.concat([movements_df, pd.DataFrame([new_movement])], ignore_index=True)
        save_pharmacie_movements(movements_df, PHARMACIE_EXCEL_FILE)
        flash(flash_message, "success")
    return redirect(url_for('pharmacie.home_pharmacie'))

# Route pour exporter l'inventaire en Excel
@pharmacie_bp.route('/export_inventory')
def export_inventory():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    if utils.EXCEL_FOLDER is None:
        if 'email' in session:
            utils.set_dynamic_base_dir(session['email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))

    # PHARMACIE_EXCEL_FILE est maintenant global et défini par @pharmacie_bp.before_request
    global PHARMACIE_EXCEL_FILE 

    inventory_df = load_pharmacie_inventory(PHARMACIE_EXCEL_FILE)
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # Convertir les objets datetime en chaînes pour l'export Excel si nécessaire
    inventory_df_for_excel = inventory_df.copy()
    if 'Date_Expiration' in inventory_df_for_excel.columns:
        inventory_df_for_excel['Date_Expiration'] = inventory_df_for_excel['Date_Expiration'].dt.strftime('%Y-%m-%d').fillna('')
    # MISE À JOUR: Convertir 'Date_Enregistrement' en chaînes pour l'export Excel
    if 'Date_Enregistrement' in inventory_df_for_excel.columns:
        inventory_df_for_excel['Date_Enregistrement'] = inventory_df_for_excel['Date_Enregistrement'].dt.strftime('%Y-%m-%d').fillna('')


    inventory_df_for_excel.to_excel(writer, sheet_name='Inventaire Pharmacie', index=False)
    writer.close()
    output.seek(0)
    
    return send_file(output, as_attachment=True, download_name='Inventaire_Pharmacie.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# Route pour exporter l'historique des mouvements en Excel
@pharmacie_bp.route('/export_movements_history')
def export_movements_history():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    if utils.EXCEL_FOLDER is None:
        if 'email' in session:
            utils.set_dynamic_base_dir(session['email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))

    # PHARMACIE_EXCEL_FILE est maintenant global et défini par @pharmacie_bp.before_request
    global PHARMACIE_EXCEL_FILE 

    movements_df = load_pharmacie_movements(PHARMACIE_EXCEL_FILE)
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    movements_df.to_excel(writer, sheet_name='Historique Mouvements Pharmacie', index=False)
    writer.close()
    output.seek(0)
    
    return send_file(output, as_attachment=True, download_name='Historique_Mouvements_Pharmacie.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# Route pour exporter l'inventaire en PDF
@pharmacie_bp.route('/export_inventory_pdf')
def export_inventory_pdf():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    if utils.EXCEL_FOLDER is None:
        if 'email' in session:
            utils.set_dynamic_base_dir(session['email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))

    # PHARMACIE_EXCEL_FILE est maintenant global et défini par @pharmacie_bp.before_request
    global PHARMACIE_EXCEL_FILE 

    inventory_df = load_pharmacie_inventory(PHARMACIE_EXCEL_FILE)
    config = utils.load_config()
    currency = config.get('currency', 'MAD')
    pdf_output = generate_inventory_pdf(inventory_df, currency)
    
    return send_file(pdf_output, as_attachment=True, download_name='Inventaire_Pharmacie.pdf', mimetype='application/pdf')

# Route pour exporter l'historique des mouvements en PDF
@pharmacie_bp.route('/export_movements_history_pdf')
def export_movements_history_pdf():
    if 'email' not in session:
        return redirect(url_for('login.login'))

    if utils.EXCEL_FOLDER is None:
        if 'email' in session:
            utils.set_dynamic_base_dir(session['email'])
        else:
            flash("Erreur: Les répertoires de données dynamiques ne sont pas définis. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('login.login'))

    # PHARMACIE_EXCEL_FILE est maintenant global et défini par @pharmacie_bp.before_request
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
                <i class="fas fa-bars" style="color: #ADD8E6;"></i> {# Icône Barres Bleu Clair #}
            </button>
            <a class="navbar-brand ms-auto d-flex align-items-center" href="{{ url_for('accueil.accueil') }}">
                <i class="fas fa-home me-2" style="color: #FFFFFF;"></i> {# Icône Accueil - BLANC #}
                <i class="fas fa-heartbeat me-2" style="color: #FFFFFF;"></i>EasyMedicaLink {# Icône Battement de cœur - BLANC #}
            </a>
        </div>
    </nav>

    <div class="offcanvas offcanvas-start" tabindex="-1" id="settingsOffcanvas">
        <div class="offcanvas-header text-white">
            <h5 class="offcanvas-title"><i class="fas fa-cog me-2" style="color: #FFD700;"></i>Paramètres</h5> {# Icône Engrenage Doré #}
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="offcanvas"></button>
        </div>
        <div class="offcanvas-body">
            <div class="d-flex gap-2 mb-4">
                <a href="{{ url_for('login.logout') }}" class="btn btn-outline-secondary flex-fill">
                    <i class="fas fa-sign-out-alt me-2" style="color: #DC143C;"></i>Déconnexion {# Icône Déconnexion Cramoisie #}
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
                            <i class="fas fa-hospital me-2" style="color: #FFFFFF;"></i> {# Icône Hôpital - BLANC #}
                            {{ config.nom_clinique or config.cabinet or 'NOM CLINIQUE/CABINET/CENTRE MEDICAL' }}
                        </h1>
                        <div class="d-flex justify-content-center gap-4 flex-wrap">
                            <div class="d-flex align-items-center header-item">
                                <i class="fas fa-user me-2" style="color: #FFFFFF;"></i><span>{{ logged_in_doctor_name if logged_in_doctor_name and logged_in_doctor_name != 'None' else config.doctor_name or 'NOM MEDECIN' }}</span> {# Simple User Icon #}
                            </div>
                            <div class="d-flex align-items-center header-item">
                                <i class="fas fa-map-marker-alt me-2" style="color: #FFFFFF;"></i><span>{{ config.location or 'LIEU' }}</span> {# Map Marker Icon (original color) #}
                            </div>
                        </div>
                        <p class="mt-2 header-item">
                            <i class="fas fa-calendar-day me-2" style="color: #FFFFFF;"></i>{{ current_date }} {# Icône Jour de calendrier - BLANC #}
                        </p>
                        <p class="mt-2 header-item">
                            <i class="fas fa-prescription-bottle-alt me-2" style="color: #FFFFFF;"></i>Pharmacie & Gestion des stocks {# Icône Flacon de prescription - BLANC #}
                        </p>
                    </div>
                    <div class="card-body">
                        <ul class="nav nav-tabs justify-content-center" id="pharmacieTab" role="tablist">
                            <li class="nav-item" role="presentation">
                                <button class="nav-link active" id="apercu-tab"
                                        data-bs-toggle="tab" data-bs-target="#apercu"
                                        type="button" role="tab">
                                    <i class="fas fa-chart-pie me-2" style="color: #17A2B8;"></i>Aperçu {# Icône Tarte graphique Info #}
                                </button>
                            </li>
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="inventaire-tab"
                                        data-bs-toggle="tab" data-bs-target="#inventaire"
                                        type="button" role="tab">
                                    <i class="fas fa-boxes me-2" style="color: #007BFF;"></i>Inventaire {# Icône Boîtes primaires #}
                                </button>
                            </li>
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="mouvements-tab"
                                        data-bs-toggle="tab" data-bs-target="#mouvements"
                                        type="button" role="tab">
                                    <i class="fas fa-exchange-alt me-2" style="color: #FFC107;"></i>Mouvements {# Icône Échange Avertissement #}
                                </button>
                            </li>
                            <li class="nav-item" role="presentation">
                                <button class="nav-link" id="ajouter-produit-tab"
                                        data-bs-toggle="tab" data-bs-target="#ajouter-produit"
                                        type="button" role="tab">
                                    <i class="fas fa-plus-circle me-2" style="color: #28A745;"></i>Ajouter Produit {# Icône Cercle plus succès #}
                                </button>
                            </li>
                        </ul>

                        <div class="tab-content mt-3" id="pharmacieTabContent">
                            {# Tab Aperçu #}
                            <div class="tab-pane fade show active" id="apercu" role="tabpanel">
                                <h4 class="text-primary mb-3">Aperçu du Stock</h4>
                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <div class="card h-100 shadow-sm">
                                            <div class="card-body text-center">
                                                <i class="fas fa-box-open fa-3x text-info mb-3" style="color: #4682B4;"></i> {# Icône Boîte ouverte en acier bleu #}
                                                <h5 class="card-title">Total Produits</h5>
                                                <p class="card-text fs-4">{{ total_products }}</p>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <div class="card h-100 shadow-sm">
                                            <div class="card-body text-center">
                                                <i class="fas fa-exclamation-triangle fa-3x text-warning mb-3" style="color: #FF4500;"></i> {# Icône Triangle d'exclamation rouge orangé #}
                                                <h5 class="card-title">Alertes Stock Bas</h5>
                                                <p class="card-text fs-4">{{ low_stock_alerts|length }}</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <h5 class="text-warning mt-4"><i class="fas fa-bell me-2" style="color: #FFD700;"></i>Produits en Stock Bas</h5> {# Icône Cloche Dorée #}
                                {% if low_stock_alerts %}
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover" id="lowStockTable">
                                        <thead>
                                            <tr>
                                                <th>Nom Prod.</th>
                                                <th>Qté Act.</th>
                                                <th>Seuil Al.</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% for product in low_stock_alerts %}
                                            <tr>
                                                <td>{{ product.Nom }}</td>
                                                <td>{{ product.Quantité }}</td>
                                                <td>{{ product.Seuil_Alerte }}</td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                                {% endif %}

                                {# NOUVELLE SECTION: Produits Expirés #}
                                <h5 class="text-danger mt-4"><i class="fas fa-calendar-times me-2" style="color: #DC3545;"></i>Produits Expirés</h5>
                                {% if expired_products %}
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover" id="expiredProductsTable">
                                        <thead>
                                            <tr>
                                                <th>Nom Prod.</th>
                                                <th>Code Prod.</th>
                                                <th>Date Exp.</th>
                                                <th>Qté</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% for product in expired_products %}
                                            <tr class="table-danger">
                                                <td>{{ product.Nom }}</td>
                                                <td>{{ product.Code_Produit }}</td>
                                                <td>{{ product.Date_Expiration.strftime('%Y-%m-%d') if product.Date_Expiration else 'N/A' }}</td>
                                                <td>{{ product.Quantité }}</td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                                {% endif %}


                                <h5 class="mt-4"><i class="fas fa-history me-2" style="color: #8A2BE2;"></i>Derniers Mouvements</h5> {# Icône Historique Bleu Violet #}
                                {% if recent_movements %}
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover" id="recentMovementsTable">
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>Code Prod.</th>
                                                <th>Nom Prod.</th>
                                                <th>Type Movt.</th>
                                                <th>Qté</th>
                                                <th>Nom Resp.</th>
                                                <th>Prénom Resp.</th>
                                                <th>Téléphone</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% for movement in recent_movements %}
                                            <tr>
                                                <td>{{ movement.Date }}</td>
                                                <td>{{ movement.Code_Produit }}</td>
                                                <td>{{ movement.Nom_Produit }}</td>
                                                <td>{{ movement.Type_Mouvement }}</td>
                                                <td>{{ movement.Quantité_Mouvement }}</td>
                                                <td>{{ movement.Nom_Responsable }}</td>
                                                <td>{{ movement.Prenom_Responsable }}</td>
                                                <td>{{ movement.Telephone_Responsable }}</td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                                {% endif %}
                            </div>

                            {# Tab Inventaire #}
                            <div class="tab-pane fade" id="inventaire" role="tabpanel">
                                <h4 class="text-primary mb-3">Inventaire Actuel</h4>
                                <p class="text-muted">Liste complète des produits en stock avec leurs détails.</p>
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover" id="inventoryTable">
                                        <thead>
                                            <tr>
                                                <th>Code Prod.</th>
                                                <th>Nom</th>
                                                <th>Type</th>
                                                <th>Usage</th>
                                                <th>Qté</th>
                                                <th>Prix Ach. ({{ currency }})</th>
                                                <th>Prix Vte. ({{ currency }})</th>
                                                <th>Fournisseur</th>
                                                <th>Date Exp.</th>
                                                <th>Seuil Al.</th>
                                                <th>Statut</th>
                                                <th>Date Enreg.</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% if inventory %}
                                                {% for product in inventory %}
                                                <tr>
                                                    <td>{{ product.Code_Produit }}</td>
                                                    <td>{{ product.Nom }}</td>
                                                    <td>{{ product.Type }}</td>
                                                    <td>{{ product.Usage }}</td>
                                                    <td>{{ product.Quantité }}</td>
                                                    <td>{{ "%.2f"|format(product.Prix_Achat) }}</td>
                                                    <td>{{ "%.2f"|format(product.Prix_Vente) }}</td>
                                                    <td>{{ product.Fournisseur }}</td>
                                                    <td>{{ product.Date_Expiration.strftime('%Y-%m-%d') if product.Date_Expiration else 'N/A' }}</td>
                                                    <td>{{ product.Seuil_Alerte }}</td>
                                                    <td>
                                                        {% if product.Quantité == 0 %}
                                                            <span class="badge bg-danger"><i class="fas fa-times-circle me-1"></i>Rupture</span>
                                                        {% elif product.Quantité <= product.Seuil_Alerte %}
                                                            <span class="badge bg-warning text-dark"><i class="fas fa-exclamation-triangle me-1"></i>Stock Bas</span>
                                                        {% else %}
                                                            <span class="badge bg-success"><i class="fas fa-check-circle me-1"></i>En Stock</span>
                                                        {% endif %}
                                                    </td>
                                                    <td>{{ product.Date_Enregistrement.strftime('%Y-%m-%d') if product.Date_Enregistrement else 'N/A' }}</td>
                                                    <td>
                                                        <div class="d-flex justify-content-center align-items-center">
                                                            <button class="btn btn-sm btn-danger delete-product-btn" data-id="{{ product.Code_Produit }}">
                                                                <i class="fas fa-trash" style="color: #FFFFFF;"></i>
                                                            </button>
                                                        </div>
                                                    </td>
                                                </tr>
                                                {% endfor %}
                                            {% endif %}
                                        </tbody>
                                    </table>
                                </div>
                                <div class="d-flex justify-content-center mb-3 mt-3">
                                    <button class="btn btn-outline-secondary" onclick="exportInventoryPdf()"><i class="fas fa-file-pdf me-2" style="color: #DC3545;"></i>Exporter PDF</button>
                                </div>
                            </div>                   

                            {# Tab Mouvements #}
                            <div class="tab-pane fade" id="mouvements" role="tabpanel">
                                <h4 class="text-primary mb-3">Enregistrer un Mouvement de Stock</h4>
                                <form id="movementForm" action="{{ url_for('pharmacie.record_movement') }}" method="POST">
                                    <div class="row g-3">
                                        <div class="col-md-12 mb-3">
                                            <div class="card shadow-sm">
                                                <div class="card-header bg-secondary text-white">
                                                    <h6 class="mb-0"><i class="fas fa-flask me-2" style="color: #F0F8FF;"></i>Détails du Mouvement</h6> {# Icône Flacon Alice Blue #}
                                                </div>
                                                <div class="card-body">
                                                    <div class="row g-3">
                                                        <div class="col-md-6 floating-label">
                                                            <select class="form-select" id="product_code_movement" name="product_code" required placeholder=" ">
                                                                <option value="" disabled selected>Sélectionnez un produit</option>
                                                                {% for product in inventory %}
                                                                <option value="{{ product.Code_Produit }}" data-quantite="{{ product.Quantité }}">{{ product.Nom }} ({{ product.Code_Produit }}) - Stock: {{ product.Quantité }}</option>
                                                                {% endfor %}
                                                            </select>
                                                            <label for="product_code_movement"><i class="fas fa-pills me-2" style="color: #6A5ACD;"></i>Produit</label> {# Icône Pilules Ardoise Bleue #}
                                                        </div>
                                                        <div class="col-md-6 floating-label">
                                                            <select class="form-select" id="movement_type" name="movement_type" required placeholder=" ">
                                                                <option value="" disabled selected>Sélectionnez le type</option>
                                                                <option value="Entrée">Entrée</option>
                                                                <option value="Sortie">Sortie</option>
                                                            </select>
                                                            <label for="movement_type"><i class="fas fa-sign-in-alt me-2" style="color: #20B2AA;"></i>Type de Mouvement</label> {# Icône Connexion Vert Mer Clair #}
                                                        </div>
                                                        <div class="col-md-12 floating-label">
                                                            <input type="number" class="form-control" id="quantity_movement" name="quantity_movement" min="1" required placeholder=" ">
                                                            <label for="quantity_movement"><i class="fas fa-sort-numeric-up-alt me-2" style="color: #FF8C00;"></i>Quantité</label> {# Icône Tri numérique croissant Orange foncé #}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        <div class="col-md-12 mb-3">
                                            <div class="card shadow-sm">
                                                <div class="card-header bg-secondary text-white">
                                                    <h6 class="mb-0"><i class="fas fa-user-circle me-2" style="color: #F0F8FF;"></i>Détails du Responsable</h6> {# Icône Cercle utilisateur Alice Blue #}
                                                </div>
                                                <div class="card-body">
                                                    <div class="row g-3">
                                                        <div class="col-md-4 floating-label">
                                                            <input type="text" class="form-control" id="nom_responsable" name="nom_responsable" value="{{ session.get('user_nom', '') }}" required placeholder=" ">
                                                            <label for="nom_responsable"><i class="fas fa-user me-2" style="color: #007BFF;"></i>Nom</label> {# Icône Utilisateur Bleu #}
                                                        </div>
                                                        <div class="col-md-4 floating-label">
                                                            <input type="text" class="form-control" id="prenom_responsable" name="prenom_responsable" value="{{ session.get('user_prenom', '') }}" required placeholder=" ">
                                                            <label for="prenom_responsable"><i class="fas fa-user-tag me-2" style="color: #17A2B8;"></i>Prénom</label> {# Icône Étiquette utilisateur Cyan #}
                                                        </div>
                                                        <div class="col-md-4 floating-label">
                                                            <input type="tel" class="form-control" id="telephone_responsable" name="telephone_responsable" value="{{ session.get('user_phone', '') }}" placeholder=" ">
                                                            <label for="telephone_responsable"><i class="fas fa-phone me-2" style="color: #28A745;"></i>Téléphone</label> {# Icône Téléphone Vert #}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-12 text-center">
                                            <button type="submit" class="btn btn-primary"><i class="fas fa-save me-2" style="color: #FFFFFF;"></i>Enregistrer le mouvement</button> {# Icône Enregistrer Blanche #}
                                        </div>
                                    </div>
                                </form>

                                <h5 class="mt-4"><i class="fas fa-scroll me-2" style="color: #CD853F;"></i>Historique des Mouvements</h5> {# Icône Défilement Pérou #}
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover" id="movementsHistoryTable">
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>Code Prod.</th>
                                                <th>Nom Prod.</th>
                                                <th>Type Movt.</th>
                                                <th>Qté</th>
                                                <th>Nom Resp.</th>
                                                <th>Prénom Resp.</th>
                                                <th>Téléphone</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {% if movements_history %}
                                                {% for movement in movements_history %}
                                                <tr>
                                                    <td>{{ movement.Date }}</td>
                                                    <td>{{ movement.Code_Produit }}</td>
                                                    <td>{{ movement.Nom_Produit }}</td>
                                                    <td>{{ movement.Type_Mouvement }}</td>
                                                    <td>{{ movement.Quantité_Mouvement }}</td>
                                                    <td>{{ movement.Nom_Responsable }}</td>
                                                    <td>{{ movement.Prenom_Responsable }}</td>
                                                    <td>{{ movement.Telephone_Responsable }}</td>
                                                </tr>
                                                {% endfor %}
                                            {% endif %}
                                        </tbody>
                                    </table>
                                </div>
                                <div class="d-flex justify-content-center mb-3 mt-3"> {# Centrer le bouton #}
                                    <button class="btn btn-outline-secondary" onclick="exportMovementsHistoryPdf()"><i class="fas fa-file-pdf me-2" style="color: #DC3545;"></i>Exporter PDF</button> {# Icône PDF Rouge #}
                                </div>
                            </div>

                            {# Tab Ajouter Produit #}
                            <div class="tab-pane fade" id="ajouter-produit" role="tabpanel">
                                <h4 class="text-primary mb-3">Ajouter / Modifier un Produit</h4>
                                <form id="productForm" action="{{ url_for('pharmacie.add_or_update_product') }}" method="POST">
                                    <input type="hidden" id="original_product_code" name="original_product_code">
                                    <div class="row g-3">
                                        <div class="col-md-6 floating-label">
                                            <input type="text" class="form-control" id="code_produit" name="code_produit" required placeholder=" ">
                                            <label for="code_produit"><i class="fas fa-qrcode me-2" style="color: #6C757D;"></i>Code Produit</label> {# Icône Qrcode Grise #}
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <input type="text" class="form-control" id="nom_produit" name="nom_produit" required placeholder=" ">
                                            <label for="nom_produit"><i class="fas fa-pills me-2" style="color: #4CAF50;"></i>Nom du Produit</label> {# Icône Pilules Vertes #}
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <select class="form-select" id="type_produit" name="type_produit" required placeholder=" ">
                                                <option value="" disabled selected>Sélectionnez un type</option>
                                                <option value="Dispositifs médicaux">Dispositifs médicaux</option>
                                                <option value="Mobilier médical">Mobilier médical</option>
                                                <option value="Matériel de diagnostic">Matériel de diagnostic</option>
                                                <option value="Matériel de chirurgie & soins">Matériel de chirurgie & soins</option>
                                                <option value="Stérilisation & hygiène">Stérilisation & hygiène</option>
                                                <option value="Consommables médicaux">Consommables médicaux</option>
                                                <option value="Équipement de rééducation & kinésithérapie">Équipement de rééducation & kinésithérapie</option>
                                                <option value="Matériel de premiers secours">Matériel de premiers secours</option>
                                                <option value="Produits de confort et bien-être">Produits de confort et bien-être</option>
                                                <option value="Produits d’hygiène et désinfection">Produits d’hygiène et désinfection</option>
                                                <option value="Informatique & gestion médicale">Informatique & gestion médicale</option>
                                            </select>
                                            <label for="type_produit"><i class="fas fa-tag me-2" style="color: #DAA520;"></i>Type</label> {# Icône Étiquette Dorée #}
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <select class="form-select" id="usage_produit" name="usage_produit" required placeholder=" ">
                                                <option value="" disabled selected>Sélectionnez un usage</option>
                                                <option value="Usage Interne">Usage Interne (clinique/cabinet)</option>
                                                <option value="Vente">Vente (aux patients)</option>
                                            </select>
                                            <label for="usage_produit"><i class="fas fa-hand-paper me-2" style="color: #6A5ACD;"></i>Usage</label> {# Icône Main Papier Ardoise Bleue #}
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <input type="number" class="form-control" id="quantite" name="quantite" min="0" required placeholder=" ">
                                            <label for="quantite"><i class="fas fa-boxes me-2" style="color: #4682B4;"></i>Quantité</label> {# Icône Boîtes en acier bleu #}
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <input type="number" class="form-control" id="prix_achat" name="prix_achat" step="0.01" min="0" placeholder=" ">
                                            <label for="prix_achat"><i class="fas fa-coins me-2" style="color: #FFD700;"></i>Prix d'Achat ({{ currency }})</label> {# Icône Pièces Dorées #}
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <input type="number" class="form-control" id="prix_vente" name="prix_vente" step="0.01" min="0" placeholder=" ">
                                            <label for="prix_vente"><i class="fas fa-hand-holding-usd me-2" style="color: #28A745;"></i>Prix de Vente ({{ currency }})</label> {# Icône Main tenant USD Vert #}
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <input type="text" class="form-control" id="fournisseur" name="fournisseur" placeholder=" ">
                                            <label for="fournisseur"><i class="fas fa-truck-moving me-2" style="color: #DC143C;"></i>Fournisseur</label> {# Icône Camion en mouvement Cramoisie #}
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <input type="date" class="form-control" id="date_expiration" name="date_expiration" placeholder=" ">
                                            <label for="date_expiration"><i class="fas fa-calendar-times me-2" style="color: #FF4500;"></i>Date d'Expiration</label> {# Icône Calendrier Temps Rouge Orange #}
                                        </div>
                                        <div class="col-md-6 floating-label">
                                            <input type="number" class="form-control" id="seuil_alerte" name="seuil_alerte" min="0" required placeholder=" ">
                                            <label for="seuil_alerte"><i class="fas fa-bell me-2" style="color: #FFC107;"></i>Seuil d'Alerte</label> {# Icône Cloche Ambre #}
                                        </div>
                                        <div class="col-12 text-center">
                                            <button type="submit" class="btn btn-primary" id="submitProductBtn"><i class="fas fa-plus me-2" style="color: #FFFFFF;"></i>Ajouter Produit</button> {# Icône Plus Blanche #}
                                            <button type="button" class="btn btn-secondary mt-2" id="clearFormBtn" style="display:none;"><i class="fas fa-eraser me-2" style="color: #FFFFFF;"></i>Effacer Formulaire</button> {# Icône Gomme Blanche #}
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
                    <i class="fas fa-heartbeat me-1" style="color: #FF69B4;"></i> {# Icône Battement de cœur Rose Vif #}
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
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <script src="https://cdn.datatables.net/1.13.1/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.1/js/dataTables.bootstrap5.min.js"></script>

    <script>
    document.addEventListener('DOMContentLoaded', () => {
        // Initialisation des onglets Bootstrap
        const tabButtons = document.querySelectorAll('#pharmacieTab button');
        tabButtons.forEach(button => {
            button.addEventListener('click', function(event) {
                event.preventDefault(); // Empêche l'action par défaut du bouton
                const tabTargetId = this.getAttribute('data-bs-target');
                const tab = new bootstrap.Tab(this);
                tab.show();
            });
        });

        // Persistance de l'onglet actif et gestion des événements 'shown.bs.tab'
        const activeTab = localStorage.getItem('activePharmacieTab');
        if (activeTab) {
            const triggerEl = document.querySelector(`#pharmacieTab button[data-bs-target="${activeTab}"]`);
            if (triggerEl) bootstrap.Tab.getOrCreateInstance(triggerEl).show();
        }

        document.querySelectorAll('#pharmacieTab button').forEach(function(tabEl) {
            tabEl.addEventListener('shown.bs.tab', function(event) {
                localStorage.setItem('activePharmacieTab', event.target.getAttribute('data-bs-target'));
                // Ajuster les colonnes des DataTables lorsque l'onglet est affiché
                $.fn.DataTable.tables({ visible: true, api: true }).columns.adjust();
            });
        });

        // Initialisation des DataTables pour toutes les tables
        function initializeDataTables() {
            // Détruire les instances existantes avant d'en créer de nouvelles
            if ($.fn.DataTable.isDataTable('#inventoryTable')) {
                $('#inventoryTable').DataTable().destroy();
            }
            $('#inventoryTable').DataTable({
                "language": {
                    "url": "//cdn.datatables.net/plug-ins/1.13.1/i18n/fr-FR.json"
                },
                "paging": true,
                "searching": true,
                "info": true,
                "order": [[1, 'asc']], // Tri par nom de produit par défaut
                "columnDefs": [ // Assurer que la colonne d'actions est bien rendue et non triable
                    { "orderable": false, "targets": -1 }
                ]
            });

            if ($.fn.DataTable.isDataTable('#lowStockTable')) {
                $('#lowStockTable').DataTable().destroy();
            }
            $('#lowStockTable').DataTable({
                "language": {
                    "url": "//cdn.datatables.net/plug-ins/1.13.1/i18n/fr-FR.json"
                },
                "paging": true,
                "searching": true,
                "info": true,
                "order": [[0, 'asc']]
            });

            if ($.fn.DataTable.isDataTable('#recentMovementsTable')) {
                $('#recentMovementsTable').DataTable().destroy();
            }
            $('#recentMovementsTable').DataTable({
                "language": {
                    "url": "//cdn.datatables.net/plug-ins/1.13.1/i18n/fr-FR.json"
                },
                "paging": true,
                "searching": true,
                "info": true,
                "order": [[0, 'desc']] // Tri par date décroissante
            });

            if ($.fn.DataTable.isDataTable('#movementsHistoryTable')) {
                $('#movementsHistoryTable').DataTable().destroy();
            }
            $('#movementsHistoryTable').DataTable({
                "language": {
                    "url": "//cdn.datatables.net/plug-ins/1.13.1/i18n/fr-FR.json"
                },
                "paging": true,
                "searching": true,
                "info": true,
                "order": [[0, 'desc']] // Tri par date décroissante
            });

            if ($.fn.DataTable.isDataTable('#expiredProductsTable')) {
                $('#expiredProductsTable').DataTable().destroy();
            }
            $('#expiredProductsTable').DataTable({
                "language": {
                    "url": "//cdn.datatables.net/plug-ins/1.13.1/i18n/fr-FR.json"
                },
                "paging": true,
                "searching": true,
                "info": true,
                "order": [[2, 'asc']] // Tri par date d'expiration croissante
            });
        }

        // Initialiser DataTables au chargement initial
        initializeDataTables();
        
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

        // Soumission AJAX paramètres (settings offcanvas)
        // Note: Le formulaire settingsOffcanvas n'est pas dans le template fourni.
        // Si vous l'ajoutez, assurez-vous d'avoir l'élément avec l'id 'settingsForm'.
        const settingsForm = document.getElementById('settingsForm');
        if(settingsForm) {
            settingsForm.addEventListener('submit', e=>{
                e.preventDefault();
                fetch(e.target.action,{method:e.target.method,body:new FormData(e.target),credentials:'same-origin'})
                    .then(r=>{ if(!r.ok) throw new Error('Échec réseau'); return r; })
                    .then(()=>Swal.fire({icon:'success',title:'Enregistré',text:'Paramètres sauvegardés.'}).then(()=>location.reload()))
                    .catch(err=>Swal.fire({icon:'error',title:'Erreur',text:err.message}));
            });
        }

        // Gestion du formulaire Ajouter/Modifier Produit
        const productForm = document.getElementById('productForm');
        const originalProductCodeInput = document.getElementById('original_product_code');
        const codeProduitInput = document.getElementById('code_produit');
        const nomProduitInput = document.getElementById('nom_produit');
        const typeProduitSelect = document.getElementById('type_produit');
        const usageProduitSelect = document.getElementById('usage_produit');
        const quantiteInput = document.getElementById('quantite');
        const prixAchatInput = document.getElementById('prix_achat');
        const prixVenteInput = document.getElementById('prix_vente');
        const fournisseurInput = document.getElementById('fournisseur');
        const dateExpirationInput = document.getElementById('date_expiration');
        const seuilAlerteInput = document.getElementById('seuil_alerte');
        const submitProductBtn = document.getElementById('submitProductBtn');
        const clearFormBtn = document.getElementById('clearFormBtn');

        // Fonction pour réinitialiser le formulaire
        const resetProductForm = () => {
            productForm.reset();
            originalProductCodeInput.value = '';
            submitProductBtn.innerHTML = '<i class="fas fa-plus me-2" style="color: #FFFFFF;"></i>Ajouter Produit';
            submitProductBtn.classList.remove('btn-warning');
            submitProductBtn.classList.add('btn-primary');
            clearFormBtn.style.display = 'none';
            codeProduitInput.readOnly = false;
            
            // Réinitialiser les étiquettes flottantes
            document.querySelectorAll('#productForm .floating-label input, #productForm .floating-label select, #productForm .floating-label textarea').forEach(input => {
                input.classList.remove('not-placeholder-shown');
            });
        };

        clearFormBtn.addEventListener('click', resetProductForm);

        // Correction finale du gestionnaire de clic pour le bouton de suppression
        // Utilisation de l'API DataTables pour récupérer les données de la ligne,
        // et ajout de e.stopPropagation() pour éviter les interférences.
        $('#inventoryTable tbody').on('click', '.delete-product-btn', function(e) {
            e.stopPropagation();
            e.preventDefault();

            const row = $(this).closest('tr');
            const productCode = $('#inventoryTable').DataTable().row(row).data()[0];
            
            Swal.fire({
                title: 'Êtes-vous sûr ?',
                text: "Vous ne pourrez pas revenir en arrière !",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
                confirmButtonText: 'Oui, supprimer !',
                cancelButtonText: 'Annuler'
            }).then((result) => {
                if (result.isConfirmed) {
                    fetch(`{{ url_for('pharmacie.delete_product') }}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                        body: `product_code=${encodeURIComponent(productCode)}`
                    })
                    .then(response => {
                        if (!response.ok) {
                            return response.json().then(err => { throw new Error(err.message || 'Échec de la suppression'); });
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data.success) {
                            Swal.fire('Supprimé !', 'Le produit a été supprimé.', 'success').then(() => location.reload());
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

        // Gestion du formulaire de mouvement de stock
        const productCodeMovementSelect = document.getElementById('product_code_movement');
        const quantityMovementInput = document.getElementById('quantity_movement');
        const movementTypeSelect = document.getElementById('movement_type');
        let currentProductStock = 0;

        productCodeMovementSelect.addEventListener('change', () => {
            const selectedOption = productCodeMovementSelect.options[productCodeMovementSelect.selectedIndex];
            currentProductStock = parseInt(selectedOption.dataset.quantite || 0);
        });

        movementTypeSelect.addEventListener('change', () => {
            validateQuantityOnTypeChange();
        });

        quantityMovementInput.addEventListener('input', () => {
            validateQuantityOnTypeChange();
        });

        function validateQuantityOnTypeChange() {
            const quantity = parseInt(quantityMovementInput.value);
            const movementType = movementTypeSelect.value;

            if (movementType === 'Sortie' && quantity > currentProductStock) {
                quantityMovementInput.setCustomValidity(`Quantité insuffisante. Stock disponible: ${currentProductStock}`);
            } else {
                quantityMovementInput.setCustomValidity('');
            }
        }

        // Soumission du formulaire de mouvement
        document.getElementById('movementForm').addEventListener('submit', function(e) {
            const quantity = parseInt(quantityMovementInput.value);
            const movementType = movementTypeSelect.value;
            if (movementType === 'Sortie' && quantity > currentProductStock) {
                Swal.fire('Erreur de stock', `Quantité de sortie (${quantity}) supérieure au stock disponible (${currentProductStock}).`, 'error');
                e.preventDefault();
            }
        });

    });

    // Fonctions d'exportation PDF directement
    function exportInventoryPdf() {
        window.location.href = "{{ url_for('pharmacie.export_inventory_pdf') }}";
    }

    function exportMovementsHistoryPdf() {
        window.location.href = "{{ url_for('pharmacie.export_movements_history_pdf') }}";
    }
</script>
</body>
</html>
"""
