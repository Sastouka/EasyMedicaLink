import os
import io
import re
import locale
import logging
from datetime import datetime
from functools import lru_cache
from typing import Optional, Union

import pandas as pd
import matplotlib
matplotlib.use('Agg') # Utiliser le backend 'Agg' pour le tracé non interactif
import matplotlib.pyplot as plt

from flask import (
    Blueprint, request, render_template_string,
    redirect, url_for, flash, session, jsonify, abort
)

import utils
import theme
import login

statistique_bp = Blueprint("statistique", __name__, url_prefix="/statistique")

# Configurer la journalisation pour un meilleur suivi des erreurs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Définir la locale pour le formatage des dates (par exemple, les noms de mois en français)
try:
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
except locale.Error:
    logging.warning("Impossible de définir la locale 'fr_FR.UTF-8', tentative de la locale par défaut.")
    try:
        locale.setlocale(locale.LC_TIME, '') # Revenir à la locale système par défaut
    except locale.Error:
        logging.error("Impossible de définir une locale système.")

# Définir diverses palettes de couleurs pour les graphiques (utilisées en JS, mais définies ici pour la cohérence).
PIE_CHART_COLORS_1_HEX = ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40", "#C9CBCF", "#6A8CFF", "#FF8C4A", "#A1F200"]
PIE_CHART_COLORS_2_HEX = ["#FF9800", "#673AB7", "#009688", "#CDDC39", "#795548", "#607D8B", "#F44336", "#2196F3", "#00BCD4", "#E91E63"]


@lru_cache(maxsize=1)
def load_cached_data():
    """Charge tous les fichiers Excel du dossier spécifié et les met en cache."""
    return _load_all_excels(utils.EXCEL_FOLDER)

@statistique_bp.route("/", methods=["GET"])
def stats_home():
    """
    Route principale pour le tableau de bord des statistiques.
    Charge, traite et filtre les données, calcule les KPI et prépare les données des graphiques.
    """
    # 1. Vérification d'autorisation
    role = session.get("role")
    if role not in ["admin", "medecin"]:
        flash("Accès réservé aux administrateurs et médecins.", "danger")
        return redirect(url_for("accueil.accueil"))

    logged_in_full_name = None 
    user_email = session.get('email')
    
    if user_email:
        admin_email_from_session = session.get('admin_email', 'default_admin@example.com')
        utils.set_dynamic_base_dir(admin_email_from_session)
        
        all_users_data = login.load_users()
        user_info = all_users_data.get(user_email)
        if user_info:
            logged_in_full_name = f"{user_info.get('prenom', '')} {user_info.get('nom', '')}".strip()
            if not logged_in_full_name:
                logged_in_full_name = None

    # 2. Chargement des données
    df_map = _load_all_excels(utils.EXCEL_FOLDER)

    # Extraction des DataFrames
    df_consult_raw = df_map.get("ConsultationData.xlsx", pd.DataFrame())
    factures_data_loaded = df_map.get("factures.xlsx", pd.DataFrame())
    if isinstance(factures_data_loaded, dict):
        # Si le fichier a plusieurs feuilles, prenez la feuille nommée 'Factures' ou la première
        df_facture_raw = factures_data_loaded.get("Factures", next(iter(factures_data_loaded.values()), pd.DataFrame()))
    else:
        # Sinon, utilisez le DataFrame directement
        df_facture_raw = factures_data_loaded
    df_rdv_raw = df_map.get("DonneesRDV.xlsx", pd.DataFrame())
    compta_data = df_map.get("Comptabilite.xlsx", {})
    df_comptabilite_recettes_raw = compta_data.get("Recettes", pd.DataFrame())
    df_comptabilite_depenses_raw = compta_data.get("Depenses", pd.DataFrame())
    df_comptabilite_salaires_raw = compta_data.get("Salaires", pd.DataFrame())
    df_comptabilite_tiers_payants_raw = compta_data.get("TiersPayants", pd.DataFrame())
    pharmacie_data_loaded = df_map.get("Pharmacie.xlsx", pd.DataFrame())
    
    if isinstance(pharmacie_data_loaded, dict):
        df_pharmacie_inventory_raw = pharmacie_data_loaded.get("Inventaire", pd.DataFrame())
        df_pharmacie_movements_raw = pharmacie_data_loaded.get("Mouvements", pd.DataFrame())
    else:
        df_pharmacie_inventory_raw = pharmacie_data_loaded
        df_pharmacie_movements_raw = pd.DataFrame()

    # 3. Récupérer et définir les filtres de date (AVEC PÉRIODE PAR DÉFAUT)
    start_str = request.args.get("start_date")
    end_str = request.args.get("end_date")
    start_dt, end_dt = None, None

    # Si aucune date n'est fournie, appliquer le filtre par défaut
    if not start_str and not end_str:
        today = datetime.now().date()
        start_dt = datetime(today.year, 1, 1)
        end_dt = datetime.now().replace(hour=23, minute=59, second=59)
        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = end_dt.strftime('%Y-%m-%d')
    else:
        # Sinon, utiliser les dates fournies par l'utilisateur
        try:
            if start_str:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d")
            if end_str:
                end_dt = datetime.strptime(end_str, "%Y-%m-%d")
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            flash("Format de date invalide, utilisez YYYY-MM-DD.", "warning")
            return redirect(url_for(".stats_home"))

    doctor_filter_email = "" 
    selected_charts_param = request.args.getlist('selected_charts')
    no_charts_selected_indicator = request.args.get('no_charts_selected')

    if no_charts_selected_indicator == 'true':
        selected_charts = []
    elif not selected_charts_param and (start_str or end_str): # If dates are set, but no charts, keep selection
        selected_charts = [
            "consultChart", "caChart", "genderChart", "ageChart", "salariesMonthlyChart",
            "rdvDoctorChart", "expensesCategoryChart", "revenueTypeChart", 
            "topProductsChart", "movementTypeChart"
        ]
    elif not selected_charts_param:
        selected_charts = [
            "consultChart", "caChart", "genderChart", "ageChart", "salariesMonthlyChart",
            "rdvDoctorChart", "expensesCategoryChart", "revenueTypeChart", 
            "topProductsChart", "movementTypeChart"
        ]
    else:
        selected_charts = selected_charts_param

    # 4. Traiter et filtrer les DataFrames
    df_rdv_for_processing = df_rdv_raw.copy()
    if doctor_filter_email and not df_rdv_for_processing.empty:
        doctor_email_col = _find_column(df_rdv_for_processing, ["Medecin_Email", "Email Médecin", "Médecin"])
        if doctor_email_col:
            df_rdv_for_processing = df_rdv_for_processing[df_rdv_for_processing[doctor_email_col] == doctor_filter_email]

    df_consult = process_consultations(df_consult_raw, start_dt, end_dt)
    df_facture = process_factures(df_facture_raw, start_dt, end_dt)
    df_rdv = process_rdv(df_rdv_for_processing, start_dt, end_dt)
    df_comptabilite_recettes = process_comptabilite_recettes(df_comptabilite_recettes_raw, start_dt, end_dt)
    df_comptabilite_depenses = process_comptabilite_depenses(df_comptabilite_depenses_raw, start_dt, end_dt)
    df_comptabilite_salaires = _process_dataframe(df_comptabilite_salaires_raw, date_keys=["Mois_Annee"], numeric_cols={"Total_Brut": 0.0}, start_dt=start_dt, end_dt=end_dt)
    df_comptabilite_tiers_payants = process_comptabilite_tiers_payants(df_comptabilite_tiers_payants_raw, start_dt, end_dt)
    df_pharmacie_inventory = process_pharmacie_inventory(df_pharmacie_inventory_raw, start_dt, end_dt)
    df_pharmacie_movements = process_pharmacie_movements(df_pharmacie_movements_raw, start_dt, end_dt)

    # 5. Filtrage des patients
    df_patient = process_patients_from_consultations(df_consult)

    # 6. Vérifier la disponibilité des données
    data_available = not (df_consult.empty and df_facture.empty and df_patient.empty and df_rdv.empty and
                          df_comptabilite_recettes.empty and df_comptabilite_depenses.empty and
                          df_pharmacie_inventory.empty and df_pharmacie_movements.empty and
                          df_comptabilite_salaires.empty and df_comptabilite_tiers_payants.empty)

    if not data_available:
        flash("Aucune donnée disponible pour la période sélectionnée ou le médecin filtré.", "warning")

    # 7. Calculs des KPI
    metrics = {
        "total_factures": len(df_facture),
        "total_patients": df_patient[_find_column(df_patient, ["patient_id", "Patient ID", "ID Patient"])].nunique() if not df_patient.empty and _find_column(df_patient, ["patient_id", "Patient ID", "ID Patient"]) else 0,
        "total_revenue": 0.0,
        "total_appointments": len(df_rdv),
        "daily_appointments": 0,
        "total_stock_value": _total_stock_value(df_pharmacie_inventory),
        "total_expenses": 0.0,
        "net_profit": 0.0,
    }

    # AJOUTEZ CE BLOC À LA PLACE
    # --- Calcul fiable des RDV du jour ---
    date_col_rdv = _find_column(df_rdv_raw, ["date", "jour", "Date RDV", "Date Rendez-vous"])
    daily_appointments_count = 0

    if date_col_rdv and not df_rdv_raw.empty:
        # On fait une copie temporaire pour travailler dessus
        temp_df = df_rdv_raw.copy()
        
        # On convertit la colonne de date en s'assurant que les erreurs ne bloquent pas tout
        temp_df[date_col_rdv] = pd.to_datetime(temp_df[date_col_rdv], errors='coerce')
        
        # On supprime les lignes où la conversion de date a échoué
        temp_df.dropna(subset=[date_col_rdv], inplace=True)
        
        # On récupère la date d'aujourd'hui (sans l'heure)
        today_date = datetime.now().date()
        
        # On filtre le DataFrame en comparant UNIQUEMENT la partie "date" (jour/mois/année)
        today_s_rdv = temp_df[temp_df[date_col_rdv].dt.date == today_date]
        
        # Le compte final est la longueur de ce DataFrame filtré
        daily_appointments_count = len(today_s_rdv)

    metrics["daily_appointments"] = daily_appointments_count
    # --- Fin du calcul fiable ---

    total_recettes_directes = df_comptabilite_recettes[_find_column(df_comptabilite_recettes, ["Montant"])].sum() if not df_comptabilite_recettes.empty and _find_column(df_comptabilite_recettes, ["Montant"]) else 0
    total_tiers_payants_recus = df_comptabilite_tiers_payants[df_comptabilite_tiers_payants[_find_column(df_comptabilite_tiers_payants, ["Statut"])].isin(['Réglé', 'Partiellement réglé'])][_find_column(df_comptabilite_tiers_payants, ["Montant_Recu"])].sum() if not df_comptabilite_tiers_payants.empty and _find_column(df_comptabilite_tiers_payants, ["Montant_Recu"]) and _find_column(df_comptabilite_tiers_payants, ["Statut"]) else 0
    metrics["total_revenue"] = round(total_recettes_directes + total_tiers_payants_recus, 2)

    total_depenses_directes = df_comptabilite_depenses[_find_column(df_comptabilite_depenses, ["Montant"])].sum() if not df_comptabilite_depenses.empty and _find_column(df_comptabilite_depenses, ["Montant"]) else 0
    total_salaires_brut = df_comptabilite_salaires[_find_column(df_comptabilite_salaires, ["Total_Brut"])].sum() if not df_comptabilite_salaires.empty and _find_column(df_comptabilite_salaires, ["Total_Brut"]) else 0
    metrics["total_expenses"] = round(total_depenses_directes + total_salaires_brut, 2)
    metrics["net_profit"] = round(metrics["total_revenue"] - metrics["total_expenses"], 2)

    # 8. Données Chart.js et analyse textuelle
    charts = {}
    
    # ... (le reste de la fonction pour le calcul des graphiques reste inchangé) ...
    if not df_consult.empty:
        date_col = _find_column(df_consult, ["consultation_date", "date_rdv", "Date RDV", "Date", "Date Consultation"])
        if date_col:
            activ = (
                df_consult
                .dropna(subset=[date_col])
                .groupby(df_consult[date_col].dt.to_period("M"))
                .size()
                .rename("count")
                .reset_index()
            )
            charts["activite_labels"] = activ[date_col].dt.strftime("%Y-%m").tolist()
            charts["activite_values"] = activ["count"].tolist()
            if charts["activite_values"]:
                max_consult = max(charts["activite_values"])
                max_consult_month_idx = charts["activite_values"].index(max_consult)
                max_consult_month = charts["activite_labels"][max_consult_month_idx]
                charts["activite_analysis"] = f"Le mois avec le plus grand nombre de consultations est **{max_consult_month}** avec **{max_consult}** consultations."
            else:
                charts["activite_analysis"] = "Aucune donnée de consultation disponible pour cette période."
        else:
            charts["activite_labels"] = []
            charts["activite_values"] = []
            charts["activite_analysis"] = "Colonne de date de consultation introuvable."
    else:
        charts["activite_labels"] = []
        charts["activite_values"] = []
        charts["activite_analysis"] = "Aucune donnée de consultation disponible pour cette période."

    finance_ts = _finance_timeseries(df_facture)
    charts.update(finance_ts)
    if charts.get("ca_values") and charts["ca_values"]:
        max_ca = max(charts["ca_values"])
        max_ca_month_idx = charts["ca_values"].index(max_ca)
        max_ca_month = charts["ca_labels"][max_ca_month_idx]
        total_ca = sum(charts["ca_values"])
        charts["ca_analysis"] = f"Le total des recettes le plus élevé a été enregistré en **{max_ca_month}** avec **{max_ca:.2f} {utils.load_config().get('currency', 'EUR')}**. Le total des recettes pour la période est de **{total_ca:.2f} {utils.load_config().get('currency', 'EUR')}**."
    else:
        charts["ca_analysis"] = "Aucune donnée de total des recettes disponible pour cette période."

    if not df_patient.empty:
        sexe_col = _find_column(df_patient, ["gender", "Sexe", "Genre"])
        patient_id_col = _find_column(df_patient, ["patient_id", "ID", "Patient ID", "ID Patient"])
        if sexe_col and patient_id_col:
            genre = df_patient.groupby(sexe_col)[patient_id_col].count()
            charts["genre_labels"] = genre.index.tolist()
            charts["genre_values"] = genre.values.tolist()
            if charts["genre_values"] and sum(charts["genre_values"]) > 0:
                total_patients = sum(charts["genre_values"])
                sorted_genres = sorted(zip(charts["genre_values"], charts["genre_labels"]), reverse=True)
                most_common_gender_count, most_common_gender = sorted_genres[0]
                most_common_percentage = (most_common_gender_count / total_patients) * 100
                charts["genre_analysis"] = f"Les patients sont majoritairement de sexe **{most_common_gender}** ({most_common_percentage:.1f}%), représentant {most_common_gender_count} patients."
            else:
                charts["genre_analysis"] = "Aucune donnée de répartition par sexe disponible."
        else:
            charts["genre_analysis"] = "Colonnes 'gender'/'Sexe' ou 'patient_id' introuvables dans les données patient dérivées."
    else:
        charts["genre_labels"] = []
        charts["genre_values"] = []
        charts["genre_analysis"] = "Aucune donnée de répartition par sexe disponible."

    age_dist = _age_distribution(df_patient)
    charts.update(age_dist)
    if charts.get("age_values") and charts["age_values"]:
        max_age_count = max(charts["age_values"])
        max_age_group_idx = charts["age_values"].index(max_age_count)
        max_age_group = charts["age_labels"][max_age_group_idx]
        charts["age_analysis"] = f"La tranche d'âge la plus représentée est **{max_age_group}** avec **{max_age_count}** patients."
    else:
        charts["age_analysis"] = "Aucune donnée de tranche d'âge disponible pour cette période."

    if not df_comptabilite_salaires.empty:
        mois_annee_col = _find_column(df_comptabilite_salaires, ["Mois_Annee"])
        total_brut_col = _find_column(df_comptabilite_salaires, ["Total_Brut"])
        if mois_annee_col and total_brut_col:
            df_salaries_processed = _process_dataframe(df_comptabilite_salaires, date_keys=[mois_annee_col], numeric_cols={total_brut_col: 0.0})
            
            if not df_salaries_processed.empty:
                monthly_salaries = df_salaries_processed.groupby(df_salaries_processed[mois_annee_col].dt.to_period("M"))[total_brut_col].sum()

                if not monthly_salaries.empty:
                    all_months = pd.period_range(monthly_salaries.index.min(), monthly_salaries.index.max(), freq="M")
                    monthly_salaries = monthly_salaries.reindex(all_months, fill_value=0)
                
                charts["salaries_monthly_labels"] = [p.strftime("%Y-%m") for p in monthly_salaries.index]
                charts["salaries_monthly_values"] = monthly_salaries.round(2).tolist()
                
                if charts["salaries_monthly_values"] and sum(charts["salaries_monthly_values"]) > 0:
                    max_salaries = max(charts["salaries_monthly_values"])
                    max_salaries_month_idx = charts["salaries_monthly_values"].index(max_salaries)
                    max_salaries_month = charts["salaries_monthly_labels"][max_salaries_month_idx]
                    total_salaries_period = sum(charts["salaries_monthly_values"])
                    charts["salaries_monthly_analysis"] = f"Le total des salaires le plus élevé a été enregistré en **{max_salaries_month}** avec **{max_salaries:.2f} {utils.load_config().get('currency', 'EUR')}**. Le total des salaires pour la période est de **{total_salaries_period:.2f} {utils.load_config().get('currency', 'EUR')}**."
                else:
                    charts["salaries_monthly_analysis"] = "Aucune donnée de salaires mensuels disponible pour cette période."
            else:
                charts["salaries_monthly_labels"] = []
                charts["salaries_monthly_values"] = []
                charts["salaries_monthly_analysis"] = "Aucune donnée de salaires mensuels disponible pour cette période."
        else:
            charts["salaries_monthly_labels"] = []
            charts["salaries_monthly_values"] = []
            charts["salaries_monthly_analysis"] = "Colonnes 'Mois_Annee' ou 'Total_Brut' des salaires introuvables."
    else:
        charts["salaries_monthly_labels"] = []
        charts["salaries_monthly_values"] = []
        charts["salaries_monthly_analysis"] = "Aucune donnée de salaires mensuels disponible pour cette période."

    if not df_rdv.empty:
        doctor_email_col = _find_column(df_rdv, ["Medecin_Email", "Email Médecin", "Médecin"])
        if doctor_email_col:
            rdv_doctor_counts = df_rdv[doctor_email_col].value_counts()
            charts["rdv_doctor_labels"] = rdv_doctor_counts.index.tolist()
            charts["rdv_doctor_values"] = rdv_doctor_counts.values.tolist()
            if charts["rdv_doctor_values"] and sum(charts["rdv_doctor_values"]) > 0:
                top_doctor_email = charts["rdv_doctor_labels"][0]
                top_doctor_count = charts["rdv_doctor_values"][0]
                charts["rdv_doctor_analysis"] = f"Le médecin avec le plus de rendez-vous est **{top_doctor_email.split('@')[0]}** avec **{top_doctor_count}** rendez-vous."
            else:
                charts["rdv_doctor_analysis"] = "Aucune donnée de rendez-vous par médecin disponible pour cette période."
        else:
            charts["rdv_doctor_analysis"] = "Colonne 'Medecin_Email' des rendez-vous introuvable."
    else:
        charts["rdv_doctor_labels"] = []
        charts["rdv_doctor_values"] = []
        charts["rdv_doctor_analysis"] = "Aucune donnée de rendez-vous par médecin disponible pour cette période."

    if not df_comptabilite_depenses.empty:
        category_col = _find_column(df_comptabilite_depenses, ["Categorie", "Catégorie Dépense"])
        montant_col = _find_column(df_comptabilite_depenses, ["Montant", "Montant Dépense"])
        if category_col and montant_col:
            df_comptabilite_depenses_processed = _process_dataframe(df_comptabilite_depenses, numeric_cols={montant_col: 0.0})
            expenses_by_category = df_comptabilite_depenses_processed.groupby(category_col)[montant_col].sum()
            charts["expenses_category_labels"] = expenses_by_category.index.tolist()
            charts["expenses_category_values"] = expenses_by_category.values.tolist()
            if charts["expenses_category_values"] and sum(charts["expenses_category_values"]) > 0:
                total_expenses_chart = sum(charts["expenses_category_values"])
                sorted_expenses = sorted(zip(charts["expenses_category_values"], charts["expenses_category_labels"]), reverse=True)
                largest_amount, largest_category = sorted_expenses[0]
                largest_percentage = (largest_amount / total_expenses_chart) * 100
                charts["expenses_category_analysis"] = f"La catégorie de dépenses la plus importante est **{largest_category}** avec **{largest_amount:.2f} {utils.load_config().get('currency', 'EUR')}** ({largest_percentage:.1f}% du total)."
            else:
                charts["expenses_category_analysis"] = "Aucune donnée de dépenses disponible pour cette période."
        else:
            charts["expenses_category_analysis"] = "Colonnes 'Catégorie' ou 'Montant' des dépenses introuvables."
    else:
        charts["expenses_category_labels"] = []
        charts["expenses_category_values"] = []
        charts["expenses_category_analysis"] = "Aucune donnée de dépenses disponible pour cette période."

    if not df_comptabilite_recettes.empty:
        type_acte_col = _find_column(df_comptabilite_recettes, ["Type_Acte", "Type Acte"])
        montant_col = _find_column(df_comptabilite_recettes, ["Montant", "Montant Recette"])
        if type_acte_col and montant_col:
            df_comptabilite_recettes_processed = _process_dataframe(df_comptabilite_recettes, numeric_cols={montant_col: 0.0})
            revenue_by_type_acte = df_comptabilite_recettes_processed.groupby(type_acte_col)[montant_col].sum()
            charts["revenue_type_labels"] = revenue_by_type_acte.index.tolist()
            charts["revenue_type_values"] = revenue_by_type_acte.values.tolist()
            if charts["revenue_type_values"] and sum(charts["revenue_type_values"]) > 0:
                total_revenue_acte = sum(charts["revenue_type_values"])
                sorted_revenue = sorted(zip(charts["revenue_type_values"], charts["revenue_type_labels"]), reverse=True)
                top_amount, top_type = sorted_revenue[0]
                top_percentage = (top_amount / total_revenue_acte) * 100
                charts["revenue_type_analysis"] = f"La source de recettes principale est **'{top_type}'** avec **{top_amount:.2f} {utils.load_config().get('currency', 'EUR')}** ({top_percentage:.1f}% du total)."
            else:
                charts["revenue_type_analysis"] = "Aucune donnée de recettes disponible pour cette période."
        else:
            charts["revenue_type_analysis"] = "Colonnes 'Type_Acte' ou 'Montant' des recettes introuvables."
    else:
        charts["revenue_type_labels"] = []
        charts["revenue_type_values"] = []
        charts["revenue_analysis"] = "Aucune donnée de recettes disponible pour cette période."

    if not df_pharmacie_inventory.empty:
        nom_col = _find_column(df_pharmacie_inventory, ["Nom", "Nom Produit"])
        quantite_col = _find_column(df_pharmacie_inventory, ["Quantité", "Quantite Stock"])
        if nom_col and quantite_col:
            top_products = df_pharmacie_inventory.nlargest(10, quantite_col).set_index(nom_col)[quantite_col]
            charts["top_products_labels"] = top_products.index.tolist()
            charts["top_products_values"] = top_products.values.tolist()
            if charts["top_products_values"] and sum(charts["top_products_values"]) > 0:
                top_product_name = charts["top_products_labels"][0]
                top_product_qty = top_products.iloc[0]
                charts["top_products_analysis"] = f"Le produit le plus en stock est **'{top_product_name}'** avec **{top_product_qty}** unités."
            else:
                charts["top_products_analysis"] = "Aucune donnée de stock disponible pour les top produits."
        else:
            charts["top_products_analysis"] = "Colonnes 'Nom' ou 'Quantité' de l'inventaire introuvables."
    else:
        charts["top_products_labels"] = []
        charts["top_products_values"] = []
        charts["top_products_analysis"] = "Aucune donnée de stock disponible pour les top produits."

    if not df_pharmacie_movements.empty:
        type_mouvement_col = _find_column(df_pharmacie_movements, ["Type_Mouvement", "Type Mouvement"])
        if type_mouvement_col:
            movement_types = df_pharmacie_movements[type_mouvement_col].value_counts()
            charts["movement_type_labels"] = movement_types.index.tolist()
            charts["movement_type_values"] = movement_types.values.tolist()
            if charts["movement_type_values"] and sum(charts["movement_type_values"]) > 0:
                entry_count = movement_types.get("Entrée", 0)
                exit_count = movement_types.get("Sortie", 0)
                charts["movement_type_analysis"] = f"Il y a eu **{entry_count}** mouvements d'entrée et **{exit_count}** mouvements de sortie enregistrés."
            else:
                charts["movement_type_analysis"] = "Aucune donnée de mouvement de stock disponible."
        else:
            charts["movement_type_analysis"] = "Colonne 'Type_Mouvement' des mouvements de stock introuvable."
    else:
        charts["movement_type_labels"] = []
        charts["movement_type_values"] = []
        charts["movement_type_analysis"] = "Aucune donnée de mouvement de stock disponible."

    unique_doctors = []

    # 9. Rendre le modèle avec toutes les données calculées et l'analyse
    return render_template_string(
        _TEMPLATE,
        config=utils.load_config(),
        theme_vars=theme.current_theme(),
        metrics=metrics,
        charts=charts,
        theme_names=list(theme.THEMES.keys()),
        currency=utils.load_config().get("currency", "EUR"),
        start_date=start_str,
        end_date=end_str,
        today=datetime.now().strftime("%Y-%m-%d"),
        logged_in_doctor_name=logged_in_full_name,
        data_available=data_available,
        unique_doctors=unique_doctors,
        selected_doctor="",
        selected_charts=selected_charts
    )

def _load_excel_safe(path: str) -> Union[pd.DataFrame, dict]:
    """
    Charge en toute sécurité un fichier Excel dans un DataFrame ou un dictionnaire de DataFrames
    s'il a plusieurs feuilles. Gère les erreurs de fichier introuvable et de corruption.
    Retourne un DataFrame vide ou un dictionnaire vide si le chargement échoue.
    """
    if not os.path.exists(path):
        logging.warning(f"Fichier non trouvé: {path}")
        return pd.DataFrame()

    try:
        xls = pd.ExcelFile(path)
        if len(xls.sheet_names) > 1:
            loaded_data = {sheet_name: pd.read_excel(xls, sheet_name=sheet_name, dtype=str).fillna("") for sheet_name in xls.sheet_names}
            logging.info(f"Fichier Excel '{os.path.basename(path)}' avec plusieurs feuilles chargé avec succès.")
            return loaded_data
        else:
            df = pd.read_excel(xls, dtype=str).fillna("")
            logging.info(f"Fichier Excel '{os.path.basename(path)}' chargé avec succès.")
            return df
    except Exception as e:
        logging.error(f"Erreur inattendue lors du chargement du fichier Excel '{path}': {e}")
        return pd.DataFrame()

def _load_all_excels(folder: str) -> dict:
    """
    Charge tous les fichiers .xlsx/.xls du dossier spécifié.
    Retourne un dictionnaire où les clés sont les noms de fichiers et les valeurs sont des DataFrames
    (ou des dictionnaires de DataFrames pour les fichiers à plusieurs feuilles).
    """
    df_map = {}
    if not os.path.isdir(folder):
        logging.warning(f"Dossier Excel non trouvé: {folder}")
        return df_map
    for fname in os.listdir(folder):
        if not fname.lower().endswith((".xlsx", ".xls")) or fname.startswith("~$"):
            continue
        full_path = os.path.join(folder, fname)
        df_map[fname] = _load_excel_safe(full_path)
    return df_map

def _find_column(df: pd.DataFrame, keys: list[str]) -> Optional[str]:
    """
    Trouve une colonne dans le DataFrame qui correspond à l'une des clés données.
    Priorise les correspondances exactes, insensibles à la casse, puis les correspondances partielles.
    Retourne le nom de colonne original ou None si aucune correspondance n'est trouvée.
    """
    if df.empty:
        return None

    df_columns_lower = {col.lower(): col for col in df.columns}

    for key in keys:
        if key.lower() in df_columns_lower:
            return df_columns_lower[key.lower()]

    for col_lower, original_col in df_columns_lower.items():
        for key in keys:
            if key.lower() in col_lower:
                return original_col
    return None

def _process_dataframe(df: pd.DataFrame, date_keys: Optional[list[str]] = None,
                       numeric_cols: Optional[dict] = None, start_dt: Optional[datetime] = None,
                       end_dt: Optional[datetime] = None) -> pd.DataFrame:
    """
    Fonction générique pour traiter les DataFrames : normaliser les colonnes de date, convertir les numériques,
    gérer les valeurs manquantes et filtrer par plage de dates.
    Retourne un DataFrame traité, qui peut être vide si l'entrée est vide ou si le filtrage ne produit aucune ligne.
    """
    if df.empty:
        print(f"DEBUG _process_dataframe: DataFrame d'entrée vide. Retourne un DataFrame vide.")
        return pd.DataFrame()

    processed_df = df.copy()
    print(f"DEBUG _process_dataframe: Début du traitement pour un DataFrame avec {len(processed_df)} lignes.")
    print(f"DEBUG _process_dataframe: Colonnes du DataFrame: {processed_df.columns.tolist()}")

    # Traitement de la colonne de date
    date_col = None
    if date_keys:
        date_col = _find_column(processed_df, date_keys)
        if date_col:
            print(f"DEBUG _process_dataframe: Colonne de date trouvée: '{date_col}'.")
            
            # Convert to string and strip whitespace
            date_strings = processed_df[date_col].astype(str).str.strip()

            # Attempt parsing with multiple common formats
            parsed_dates = pd.Series(pd.NaT, index=date_strings.index)
            
            # List of common date formats to try
            common_formats = [
                '%Y-%m-%d %H:%M:%S', # YYYY-MM-DD HH:MM:SS
                '%Y-%m-%d %H:%M',   # YYYY-MM-DD HH:MM
                '%Y-%m-%d',         # YYYY-MM-DD
                '%d/%m/%Y %H:%M:%S', # DD/MM/YYYY HH:MM:SS
                '%d/%m/%Y %H:%M',   # DD/MM/YYYY HH:MM
                '%d/%m/%Y',         # DD/MM/YYYY
                '%d-%m-%Y %H:%M:%S', # DD-MM-YYYY HH:MM:SS
                '%d-%m-%Y %H:%M',   # DD-MM-Y HH:MM
                '%d-%m-%Y',         # DD-MM-YYYY
                '%Y/%m/%d %H:%M:%S', # YYYY/MM/DD HH:MM:SS
                '%Y/%m/%d %H:%M',   # YYYY/MM/DD HH:MM
                '%Y/%m/%d',         # YYYY/MM/DD
                '%Y-%m',            # YYYY-MM (for month-year only, e.g., salaries)
                '%m/%Y',            # MM/YYYY
            ]

            for fmt in common_formats:
                unparsed_mask = parsed_dates.isna()
                if not unparsed_mask.any(): # All dates parsed, break loop
                    break
                parsed_dates[unparsed_mask] = pd.to_datetime(date_strings[unparsed_mask], format=fmt, errors='coerce')
                
            # Fallback for any remaining unparsed dates (e.g., if dayfirst is truly needed or a very odd format)
            unparsed_mask = parsed_dates.isna()
            if unparsed_mask.any():
                print(f"DEBUG _process_dataframe: {unparsed_mask.sum()} dates non parsées avec formats explicites. Tentative d'inférence avec dayfirst=True.")
                parsed_dates[unparsed_mask] = pd.to_datetime(date_strings[unparsed_mask], errors='coerce', dayfirst=True) # Try inference with dayfirst

            processed_df[date_col] = parsed_dates
            
            # Supprimer les lignes où la conversion de date a échoué (NaT - Not a Time)
            initial_rows = len(processed_df)
            processed_df = processed_df.dropna(subset=[date_col])
            if len(processed_df) < initial_rows:
                print(f"DEBUG _process_dataframe: {initial_rows - len(processed_df)} lignes supprimées en raison de dates invalides après toutes les tentatives de parsage.")

            mask = pd.Series([True] * len(processed_df), index=processed_df.index)
            if start_dt:
                print(f"DEBUG _process_dataframe: Application du filtre de date de début: {start_dt}.")
                mask &= (processed_df[date_col] >= start_dt)
            if end_dt:
                print(f"DEBUG _process_dataframe: Application du filtre de date de fin: {end_dt}.")
                mask &= (processed_df[date_col] <= end_dt)
            processed_df = processed_df[mask]
            print(f"DEBUG _process_dataframe: Après filtrage par date, {len(processed_df)} lignes restantes.")
        else:
            logging.warning(f"Aucune colonne de date trouvée pour le DataFrame. Clés recherchées: {date_keys}. Le filtrage par date ne sera pas appliqué.")
            pass 

    # Traitement des colonnes numériques
    if numeric_cols:
        for col_name, fill_value in numeric_cols.items():
            found_col = _find_column(processed_df, [col_name])
            if found_col:
                print(f"DEBUG _process_dataframe: Traitement de la colonne numérique: '{found_col}'.")
                processed_df[found_col] = (
                    processed_df[found_col].astype(str)
                    .str.replace(r"[^\d,.\-]", "", regex=True)
                    .str.replace(",", ".", regex=False)
                )
                converted_series = pd.to_numeric(processed_df[found_col], errors="coerce")
                nan_count = converted_series.isna().sum()
                if nan_count > 0:
                    print(f"DEBUG _process_dataframe: {nan_count} valeurs non numériques trouvées dans '{found_col}' et converties en NaN.")
                
                processed_df[found_col] = converted_series.fillna(fill_value)
                print(f"DEBUG _process_dataframe: Colonne '{found_col}' convertie. Dtype: {processed_df[found_col].dtype}. Somme: {processed_df[found_col].sum()}.")
            else:
                logging.warning(f"Colonne numérique '{col_name}' non trouvée dans le DataFrame. Elle ne sera pas traitée.")

    print(f"DEBUG _process_dataframe: Fin du traitement. DataFrame résultant a {len(processed_df)} lignes.")
    return processed_df

# Fonctions de traitement spécifiques utilisant l'aide générique _process_dataframe
def process_consultations(df, start_dt=None, end_dt=None):
    return _process_dataframe(df, date_keys=["consultation_date", "date_rdv", "Date RDV", "Date", "Date Consultation"],
                              start_dt=start_dt, end_dt=end_dt)

def process_factures(df, start_dt=None, end_dt=None):
    return _process_dataframe(df, date_keys=["date", "jour", "day", "Date Facture"],
                              numeric_cols={"Montant": 0.0, "Sous-total": 0.0, "TVA": 0.0, "Total TTC": 0.0},
                              start_dt=start_dt, end_dt=end_dt)

def process_rdv(df, start_dt=None, end_dt=None):
    return _process_dataframe(df, date_keys=["date", "jour", "Date RDV", "Date Rendez-vous"],
                              start_dt=start_dt, end_dt=end_dt)

def process_comptabilite_recettes(df, start_dt=None, end_dt=None):
    return _process_dataframe(df, date_keys=["Date", "Date Recette"],
                              numeric_cols={"Montant": 0.0},
                              start_dt=start_dt, end_dt=end_dt)

def process_comptabilite_depenses(df, start_dt=None, end_dt=None):
    return _process_dataframe(df, date_keys=["Date", "Date Dépense"],
                              numeric_cols={"Montant": 0.0},
                              start_dt=start_dt, end_dt=end_dt)

def process_comptabilite_tiers_payants(df, start_dt=None, end_dt=None):
    return _process_dataframe(df, date_keys=["Date_Reglement", "Date Reglement"],
                              numeric_cols={"Montant_Attendu": 0.0, "Montant_Recu": 0.0},
                              start_dt=start_dt, end_dt=end_dt)

def process_pharmacie_inventory(df, start_dt=None, end_dt=None):
    print(f"DEBUG process_pharmacie_inventory: Chargement de l'inventaire brut pour traitement.")
    return _process_dataframe(df, 
                              date_keys=["Date_Enregistrement", "Date Enregistrement", "Date d'enregistrement"],
                              numeric_cols={"Quantité": 0, "Prix_Vente": 0.0, "Prix_Achat": 0.0, "Seuil_Alerte": 0},
                              start_dt=start_dt, end_dt=end_dt) # Passed start_dt and end_dt

def process_pharmacie_movements(df, start_dt=None, end_dt=None):
    return _process_dataframe(df, date_keys=["Date", "Date Mouvement", "Date Transaction"],
                              numeric_cols={"Quantité": 0},
                              start_dt=start_dt, end_dt=end_dt)

def process_patients_from_consultations(df_consult: pd.DataFrame) -> pd.DataFrame:
    """
    Extrait les données démographiques uniques des patients à partir du DataFrame des consultations.
    Suppose que les colonnes 'patient_id', 'date_of_birth' et 'gender' sont présentes dans df_consult.
    """
    if df_consult.empty:
        return pd.DataFrame()

    patient_id_col = _find_column(df_consult, ["patient_id", "Patient ID", "ID Patient"])
    date_naissance_col = _find_column(df_consult, ["date_of_birth", "DateNaissance", "Date de Naissance", "DOB"])
    sexe_col = _find_column(df_consult, ["gender", "Sexe", "Genre"])

    if not patient_id_col:
        logging.warning("Colonne 'patient_id' introuvable dans le DataFrame des consultations pour extraire les patients.")
        return pd.DataFrame()

    columns_to_select = [patient_id_col]
    if date_naissance_col and date_naissance_col in df_consult.columns:
        columns_to_select.append(date_naissance_col)
    if sexe_col and sexe_col in df_consult.columns:
        columns_to_select.append(sexe_col)

    patient_demographics = df_consult[columns_to_select].copy()

    unique_patients_df = patient_demographics.drop_duplicates(subset=[patient_id_col], keep='first')

    if date_naissance_col and date_naissance_col in unique_patients_df.columns:
        # LOGIQUE DE PARSING DE DATE AMÉLIORÉE ET HARMONISÉE
        date_strings_patient = unique_patients_df[date_naissance_col].astype(str).str.strip()
        parsed_dates_patient = pd.Series(pd.NaT, index=date_strings_patient.index)
        
        # Utilisation de la liste de formats complète, identique à _process_dataframe
        common_formats = [
            '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d',
            '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y',
            '%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M', '%d-%m-%Y',
            '%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M', '%Y/%m/%d',
            '%Y-%m', '%m/%Y',
        ]
        
        for fmt in common_formats:
            unparsed_mask_patient = parsed_dates_patient.isna()
            if not unparsed_mask_patient.any():
                break
            parsed_dates_patient[unparsed_mask_patient] = pd.to_datetime(date_strings_patient[unparsed_mask_patient], format=fmt, errors='coerce')
        
        # Fallback pour les formats non reconnus
        if parsed_dates_patient.isna().any():
            parsed_dates_patient[parsed_dates_patient.isna()] = pd.to_datetime(date_strings_patient[parsed_dates_patient.isna()], errors='coerce', dayfirst=True)

        unique_patients_df[date_naissance_col] = parsed_dates_patient
        unique_patients_df = unique_patients_df.dropna(subset=[date_naissance_col])
    else:
        logging.warning("Colonne 'DateNaissance' non trouvée dans le DataFrame patient dérivé des consultations.")

    return unique_patients_df

def _total_revenue(df_facture: pd.DataFrame) -> float:
    """Calcule le chiffre d'affaires total à partir des factures (Sous-total + TVA)."""
    if df_facture.empty:
        return 0.0

    sous_total_col = _find_column(df_facture, ["Sous-total", "HT", "subtotal", "Montant HT"])
    tva_col = _find_column(df_facture, ["TVA", "tax", "vat", "Montant TVA"])
    total_ttc_col = _find_column(df_facture, ["Total TTC", "Total"])

    if total_ttc_col:
        df_processed = _process_dataframe(df_facture, numeric_cols={total_ttc_col: 0.0})
        if not df_processed.empty:
            return round(df_processed[total_ttc_col].sum(), 2)

    if not sous_total_col or not tva_col:
        logging.warning("Colonnes 'Sous-total' ou 'TVA' introuvables pour le calcul du chiffre d'affaires.")
        return 0.0

    df_processed = _process_dataframe(df_facture, numeric_cols={sous_total_col: 0.0, tva_col: 0.0})

    if df_processed.empty:
        return 0.0

    ttc_calculated = df_processed[sous_total_col] + df_processed[tva_col]
    return round(ttc_calculated.sum(), 2)

def _total_stock_value(df_pharmacie_inventory: pd.DataFrame) -> float:
    """Calcule la valeur totale du stock (Quantité * Prix d'achat)."""
    print(f"DEBUG _total_stock_value: Début du calcul de la valeur du stock.")
    if df_pharmacie_inventory.empty:
        print("DEBUG _total_stock_value: DataFrame d'inventaire vide. Retourne 0.0.")
        return 0.0

    quantite_col = _find_column(df_pharmacie_inventory, ["Quantité", "Quantite Stock"])
    prix_achat_col = _find_column(df_pharmacie_inventory, ["Prix_Achat", "Prix Achat", "Prix Unitaire Achat"])

    if not quantite_col or not prix_achat_col:
        logging.warning(f"Colonnes 'Quantité' ('{quantite_col}') ou 'Prix_Achat' ('{prix_achat_col}') introuvables pour le calcul de la valeur du stock.")
        print("DEBUG _total_stock_value: Colonnes requises manquantes. Retourne 0.0.")
        return 0.0

    df_inventory_processed = df_pharmacie_inventory
    print(f"DEBUG _total_stock_value: DataFrame d'inventaire traité. Lignes: {len(df_inventory_processed)}.")
    print(f"DEBUG _total_stock_value: Colonnes 'Quantité' (dtype: {df_inventory_processed[quantite_col].dtype}) et 'Prix_Achat' (dtype: {df_inventory_processed[prix_achat_col].dtype}).")
    print(f"DEBUG _total_stock_value: Premières valeurs de Quantité: {df_inventory_processed[quantite_col].head().tolist()}")
    print(f"DEBUG _total_stock_value: Premières valeurs de Prix_Achat: {df_inventory_processed[prix_achat_col].head().tolist()}")


    if df_inventory_processed.empty:
        print("DEBUG _total_stock_value: DataFrame d'inventaire traité est vide. Retourne 0.0.")
        return 0.0

    calculated_value = (df_inventory_processed[quantite_col] * df_inventory_processed[prix_achat_col]).sum()
    final_value = round(calculated_value, 2)
    print(f"DEBUG _total_stock_value: Valeur calculée brute: {calculated_value}. Valeur finale arrondie: {final_value}.")
    return final_value

def _conversion_rdv_consultation(df_rdv: pd.DataFrame, df_consult: pd.DataFrame) -> str:
    """
    Calcule le taux de conversion des rendez-vous (RDV) en consultations.
    Suppose la colonne 'Statut' dans df_rdv et 'patient_id' dans les deux.
    """
    if df_rdv.empty or df_consult.empty:
        return "0.00%"

    rdv_patient_id_col = _find_column(df_rdv, ["patient_id", "Patient ID", "ID Patient"])
    consult_patient_id_col = _find_column(df_consult, ["patient_id", "Patient ID", "ID Patient"])
    rdv_status_col = _find_column(df_rdv, ["Statut", "Status RDV"])

    if not rdv_patient_id_col or not consult_patient_id_col or not rdv_status_col:
        logging.warning("Colonnes nécessaires pour le taux de conversion RDV -> Consultation introuvables.")
        return "N/A"

    confirmed_rdv_patients = df_rdv[df_rdv[rdv_status_col].isin(["Confirmé", "Terminé", "Effectué"])][rdv_patient_id_col].nunique()

    consulted_patients = df_consult[consult_patient_id_col].nunique()

    if confirmed_rdv_patients == 0:
        return "0.00%"
    
    conversion_rate = (consulted_patients / confirmed_rdv_patients) * 100
    return f"{conversion_rate:.2f}%"

def _top_sold_products(df_pharmacie_movements: pd.DataFrame) -> dict:
    """
    Identifie les 3 produits les plus vendus/utilisés en fonction des mouvements de 'Sortie'.
    Retourne un dictionnaire avec le nom du produit et la quantité.
    """
    if df_pharmacie_movements.empty:
        return {"name": "N/A", "quantity": 0}

    product_name_col = _find_column(df_pharmacie_movements, ["Nom_Produit", "Produit", "Nom Produit"])
    type_mouvement_col = _find_column(df_pharmacie_movements, ["Type_Mouvement", "Type Mouvement"])
    quantite_col = _find_column(df_pharmacie_movements, ["Quantité", "Quantite Mouvement"])

    if not product_name_col or not type_mouvement_col or not quantite_col:
        logging.warning("Colonnes nécessaires pour les produits les plus vendus introuvables.")
        return {"name": "N/A", "quantity": 0}

    df_movements_processed = _process_dataframe(df_pharmacie_movements, numeric_cols={quantite_col: 0})
    
    sales_df = df_movements_processed[df_movements_processed[type_mouvement_col] == "Sortie"]

    if sales_df.empty:
        return {"name": "Aucun produit vendu", "quantity": 0}

    product_sales = sales_df.groupby(product_name_col)[quantite_col].sum().nlargest(3)

    if product_sales.empty:
        return {"name": "Aucun produit vendu", "quantity": 0}

    top_product_name = product_sales.index[0]
    top_product_quantity = product_sales.iloc[0]

    return {"name": top_product_name, "quantity": int(top_product_quantity)}

def _net_profit(df_recettes: pd.DataFrame, df_depenses: pd.DataFrame, df_salaires: pd.DataFrame, df_tiers_payants: pd.DataFrame) -> float:
    """
    Calcule le bénéfice net : Recettes + Tiers Payants Reçus - (Dépenses + Salaires).
    """
    total_recettes = 0.0
    montant_recette_col = _find_column(df_recettes, ["Montant", "Montant Recette"])
    if not df_recettes.empty and montant_recette_col:
        df_recettes_processed = _process_dataframe(df_recettes, numeric_cols={montant_recette_col: 0.0})
        total_recettes = df_recettes_processed[montant_recette_col].sum()
    else:
        logging.warning("Colonne 'Montant' des recettes introuvable ou DataFrame vide pour le calcul du bénéfice net.")

    total_tiers_payants_recus = 0.0
    montant_recu_tp_col = _find_column(df_tiers_payants, ["Montant_Recu", "Montant Recu"])
    statut_tp_col = _find_column(df_tiers_payants, ["Statut"])
    if not df_tiers_payants.empty and montant_recu_tp_col and statut_tp_col:
        df_tp_processed = _process_dataframe(df_tiers_payants, numeric_cols={montant_recu_tp_col: 0.0})
        total_tiers_payants_recus = df_tp_processed[
            df_tp_processed[statut_tp_col].isin(['Réglé', 'Partiellement réglé'])
        ][montant_recu_tp_col].sum()
    else:
        logging.warning("Colonnes 'Montant_Recu' ou 'Statut' des tiers payants introuvables ou DataFrame vide pour le calcul du bénéfice net.")

    total_depenses = 0.0
    montant_depense_col = _find_column(df_depenses, ["Montant", "Montant Dépense"])
    if not df_depenses.empty and montant_depense_col:
        df_depenses_processed = _process_dataframe(df_depenses, numeric_cols={montant_depense_col: 0.0})
        total_depenses = df_depenses_processed[montant_depense_col].sum()
    else:
        logging.warning("Colonne 'Montant' des dépenses introuvable ou DataFrame vide pour le calcul du bénéfice net.")

    total_salaires = 0.0
    montant_salaire_col = _find_column(df_salaires, ["Total_Brut"]) 
    if not df_salaires.empty and montant_salaire_col:
        df_salaires_processed = _process_dataframe(df_salaires, numeric_cols={montant_salaire_col: 0.0})
        total_salaires = df_salaires_processed[montant_salaire_col].sum()
    else:
        logging.warning("Colonne 'Total_Brut' des salaires introuvable ou DataFrame vide pour le calcul du bénéfice net.")

    total_revenues = total_recettes + total_tiers_payants_recus
    total_expenses = total_depenses + total_salaires

    net_profit = total_revenues - total_expenses
    return round(net_profit, 2)

def _finance_timeseries(df_facture: pd.DataFrame) -> dict:
    """
    Prépare les données pour le graphique de série chronologique des revenus mensuels.
    Calcule le total TTC à partir des colonnes 'Sous-total' et 'TVA'.
    """
    if df_facture.empty:
        return {"ca_labels": [], "ca_values": []}

    date_col = _find_column(df_facture, ["date", "jour", "day", "Date Facture"])
    sous_total_col = _find_column(df_facture, ["Sous-total", "HT", "subtotal", "Montant HT"])
    tva_col = _find_column(df_facture, ["TVA", "tax", "vat", "Montant TVA"])
    total_ttc_col = _find_column(df_facture, ["Total TTC", "Total"])

    df_processed = df_facture.copy()

    if total_ttc_col:
        df_processed = _process_dataframe(df_facture, date_keys=[date_col], numeric_cols={total_ttc_col: 0.0})
        if not df_processed.empty:
            df_processed['calculated_total_ttc'] = df_processed[total_ttc_col]
        else:
            logging.warning("La colonne 'Total TTC' est vide ou invalide après traitement.")
            return {"ca_labels": [], "ca_values": []}
    elif date_col and sous_total_col and tva_col:
        df_processed = _process_dataframe(df_facture, date_keys=[date_col], numeric_cols={sous_total_col: 0.0, tva_col: 0.0})
        if not df_processed.empty:
            df_processed['calculated_total_ttc'] = df_processed[sous_total_col] + df_processed[tva_col]
        else:
            logging.warning("Les colonnes 'Sous-total' ou 'TVA' sont vides ou invalides après traitement.")
            return {"ca_labels": [], "ca_values": []}
    else:
        logging.warning("Colonnes nécessaires pour la série temporelle financière introuvables.")
        return {"ca_labels": [], "ca_values": []}

    if df_processed.empty:
        return {"ca_labels": [], "ca_values": []}

    df_processed = df_processed.dropna(subset=[date_col, 'calculated_total_ttc'])
    if df_processed.empty:
        return {"ca_labels": [], "ca_values": []}

    df_processed["period"] = df_processed[date_col].dt.to_period("M")

    ca = df_processed.groupby("period")['calculated_total_ttc'].sum()

    if not ca.empty:
        all_months = pd.period_range(ca.index.min(), ca.index.max(), freq="M")
        ca = ca.reindex(all_months, fill_value=0)
    else:
        return {"ca_labels": [], "ca_values": []}

    labels = [p.strftime("%Y-%m") for p in ca.index]
    values = ca.round(2).tolist()

    return {"ca_labels": labels, "ca_values": values}

def _age_distribution(df_patient: pd.DataFrame) -> dict:
    """Calcule la distribution d'âge des patients en tranches prédéfinies."""
    date_naissance_col = _find_column(df_patient, ["date_of_birth", "DateNaissance", "Date de Naissance", "DOB"])
    if not date_naissance_col:
        logging.warning("Colonne 'date_of_birth'/'DateNaissance' introuvable pour la distribution par âge dans le DataFrame patient dérivé.")
        return {"age_labels": [], "age_values": []}

    if not pd.api.types.is_datetime64_any_dtype(df_patient[date_naissance_col]):
        df_patient_processed = _process_dataframe(df_patient, date_keys=[date_naissance_col])
    else:
        df_patient_processed = df_patient.copy()

    if df_patient_processed.empty:
        return {"age_labels": [], "age_values": []}

    naissance = df_patient_processed[date_naissance_col]
    today = pd.Timestamp.today()
    age_y = ((today - naissance).dt.days / 365.25).round().astype("Int64")
    age_y = age_y.where((age_y >= 0) & (age_y <= 120))
    df_age = pd.DataFrame({"age": age_y}).dropna()

    labels = ["0-2","3-5","6-11","12-14","15-17","18-29","30-39","40-49","50-59","60-69","70+"]
    bins = [0,3,6,12,15,18,30,40,50,60,70,120]
    
    if df_age.empty:
        return {"age_labels": labels, "age_values": [0]*len(labels)}

    df_age["group"] = pd.cut(df_age["age"], bins=bins, labels=labels, right=False)
    grp = df_age.groupby("group", observed=False)["age"].count().reindex(labels, fill_value=0)
    return {"age_labels": grp.index.tolist(), "age_values": grp.values.tolist()}


_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
<title>Statistiques – {{ config.nom_clinique or 'EasyMedicaLink' }}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&family=Great+Vibes&display=swap" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>{% include '_floating_assistant.html' %} 

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

  /* KPI Cards */
  .kpi-card {
    background: var(--card-bg);
    border: 2px solid var(--primary-color);
    border-radius: var(--border-radius-md);
    transition: transform .2s ease, box-shadow .2s ease;
    box-shadow: var(--shadow-light);
  }
  .kpi-card:hover {
    transform: translateY(-5px);
    box-shadow: var(--shadow-medium);
  }
  .kpi-value {
    font-size: 2.2rem;
    font-weight: 700;
    color: var(--primary-color);
  }
  .kpi-label {
    font-size: 1rem;
    color: var(--text-color);
  }

  /* Chart Cards */
  .chart-card {
    background: var(--card-bg);
    border-radius: var(--border-radius-lg);
    box-shadow: var(--shadow-light);
    border: none;
  }
  .chart-card .card-header {
    background: var(--secondary-color) !important;
    color: var(--button-text) !important;
    border-top-left-radius: var(--border-radius-lg);
    border-top-right-radius: var(--border-radius-lg);
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
    box_shadow: var(--shadow-medium);
  }
  .btn-warning {
    background-color: var(--warning-color);
    border-color: var(--warning-color);
    color: white;
  }
  .btn-warning:hover {
    background-color: var(--warning-color-dark);
    border-color: var(--warning-color-dark);
    box_shadow: var(--shadow-medium);
  }
  .btn-danger {
    background-color: var(--danger-color);
    border-color: var(--danger-color);
    color: white;
  }
  .btn-danger:hover {
    background-color: var(--danger-color-dark);
    border-color: var(--danger-color-dark);
    box_shadow: var(--shadow-medium);
  }
  .btn-info {
    background-color: #25D366;
    border-color: #25D366;
    color: white;
  }
  .btn-info:hover {
    background-color: #1DA851;
    border-color: #1DA851;
    box_shadow: var(--shadow-medium);
  }
  .btn-outline-secondary {
    border-color: var(--secondary-color);
    color: var(--text-color);
    background-color: transparent;
  }
  .btn-outline-secondary:hover {
    background-color: var(--secondary-color);
    color: white;
    box_shadow: var(--shadow-light);
  }
  .btn-secondary {
    background-color: var(--secondary-color);
    border-color: var(--secondary-color);
    color: var(--button-text);
  }
  .btn-secondary:hover {
    background-color: var(--secondary-color-dark);
    border-color: var(--secondary-color-dark);
    box_shadow: var(--shadow-medium);
  }
  .btn-sm {
    padding: 0.5rem 0.8rem;
    font-size: 0.875rem;
  }

  /* Form controls */
  .form-control, .form-select {
    border-radius: var(--border-radius-sm);
    border: 1px solid var(--secondary-color);
    padding: 0.5rem 0.75rem;
    background-color: var(--card-bg);
    color: var(--text-color);
  }
  .form-control:focus, .form-select:focus {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 0.25rem rgba(var(--primary-color-rgb), 0.25);
  }

  /* Footer */
  footer {
    background: var(--gradient-main);
    color: white;
    font-weight: 300;
    box-shadow: 0 -5px 15px rgba(0, 0, 0, 0.1);
    padding-top: 0.75rem;
    padding-bottom: 0.75rem;
    margin-top: 2rem;
  }
  footer p {
    margin-bottom: 0.25rem;
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
  .chart-analysis {
      margin-top: 1rem;
      padding: 0.75rem 1rem;
      background-color: var(--table-striped-bg);
      border-radius: var(--border-radius-sm);
      color: var(--text-color);
      font-size: 0.9rem;
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
      <i class="fas fa-home me-2" style="color: #FFFFFF;"></i>
      <i class="fas fa-heartbeat me-2" style="color: #FFFFFF;"></i>EasyMedicaLink
    </a>
  </div>
</nav>

<div class="offcanvas offcanvas-start" tabindex="-1" id="settingsOffcanvas">
  <div class="offcanvas-header text-white">
    <h5 class="offcanvas-title"><i class="fas fa-cog me-2" style="color: #FFFFFF;"></i>Paramètres</h5>
    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="offcanvas"></button>
  </div>
  <div class="offcanvas-body">
    <div class="d-flex gap-2 mb-4">
      <a href="{{ url_for('login.logout') }}" class="btn btn-outline-secondary flex-fill">
        <i class="fas fa-sign-out-alt me-2" style="color: #FFFFFF;"></i>Déconnexion
      </a>
    </div>
  </div>
</div>

<script>
  // Soumission AJAX paramètres
  document.getElementById('settingsForm').addEventListener('submit', e=>{
    e.preventDefault();
    fetch(e.target.action,{method:e.target.method,body:new FormData(e.target),credentials:'same-origin'})
      .then(r=>{ if(!r.ok) throw new Error('Échec réseau'); return r; })
      .then(()=>Swal.fire({icon:'success',title:'Enregistré',text:'Paramètres sauvegardés.'}).then(()=>location.reload()))
      .catch(err=>Swal.fire({icon:'error',title:'Erreur',text:err.message}));
  });
</script>

<div class="container-fluid my-4">
  <div class="row justify-content-center">
    <div class="col-12">
      <div class="card shadow-lg">
        <div class="card-header py-3 text-center">
          <h1 class="mb-2 header-item">
            <i class="fas fa-hospital me-2" style="color: #FFFFFF;"></i>
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
            <i class="fas fa-calendar-day me-2" style="color: #FFFFFF;"></i>{{ today }}
          </p>
          <p class="mt-2 header-item">
            <i class="fas fa-chart-pie me-2" style="color: #FFFFFF;"></i>Statistiques
          </p>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="container-fluid my-4">
  <div class="row justify-content-center">
    <div class="col-12">
      <form class="row g-2 mb-4 justify-content-center" method="get" id="filterForm">
        <h6 class="mb-2">Choisir une période :</h6>
        <div class="col-md-3">
          <input type="date" name="start_date" class="form-control" value="{{ start_date }}" placeholder="Date de début">
        </div>
        <div class="col-md-3">
          <input type="date" name="end_date" class="form-control" value="{{ end_date }}" placeholder="Date de fin">
        </div>
        {# Removed the doctor filter combobox #}
        <div class="col-12 mt-3">
          <div class="card p-3">
            <h6 class="mb-2">Sélectionner les graphiques à afficher :</h6>
            <div class="row g-2">
              <div class="col-sm-6 col-md-4 col-lg-3">
                <div class="form-check">
                  <input class="form-check-input chart-checkbox" type="checkbox" name="selected_charts" value="consultChart" id="chartConsult" {% if 'consultChart' in selected_charts %}checked{% endif %}>
                  <label class="form-check-label" for="chartConsult">Consultations mensuelles</label>
                </div>
              </div>
              <div class="col-sm-6 col-md-4 col-lg-3">
                <div class="form-check">
                  <input class="form-check-input chart-checkbox" type="checkbox" name="selected_charts" value="caChart" id="chartCa" {% if 'caChart' in selected_charts %}checked{% endif %}>
                  <label class="form-check-label" for="chartCa">Total Recettes Mensuel</label>
                </div>
              </div>
              <div class="col-sm-6 col-md-4 col-lg-3">
                <div class="form-check">
                  <input class="form-check-input chart-checkbox" type="checkbox" name="selected_charts" value="genderChart" id="chartGender" {% if 'genderChart' in selected_charts %}checked{% endif %}>
                  <label class="form-check-label" for="chartGender">Répartition par sexe</label>
                </div>
              </div>
              <div class="col-sm-6 col-md-4 col-lg-3">
                <div class="form-check">
                  <input class="form-check-input chart-checkbox" type="checkbox" name="selected_charts" value="ageChart" id="chartAge" {% if 'ageChart' in selected_charts %}checked{% endif %}>
                  <label class="form-check-label" for="chartAge">Tranches d’âge</label>
                </div>
              </div>
              <div class="col-sm-6 col-md-4 col-lg-3">
                <div class="form-check">
                  <input class="form-check-input chart-checkbox" type="checkbox" name="selected_charts" value="salariesMonthlyChart" id="chartSalariesMonthly" {% if 'salariesMonthlyChart' in selected_charts %}checked{% endif %}>
                  <label class="form-check-label" for="chartSalariesMonthly">Salaires mensuels</label>
                </div>
              </div>
              <div class="col-sm-6 col-md-4 col-lg-3">
                <div class="form-check">
                  <input class="form-check-input chart-checkbox" type="checkbox" name="selected_charts" value="rdvDoctorChart" id="chartRdvDoctor" {% if 'rdvDoctorChart' in selected_charts %}checked{% endif %}>
                  <label class="form-check-label" for="chartRdvDoctor">Rendez-vous par médecin</label>
                </div>
              </div>
              <div class="col-sm-6 col-md-4 col-lg-3">
                <div class="form-check">
                  <input class="form-check-input chart-checkbox" type="checkbox" name="selected_charts" value="expensesCategoryChart" id="chartExpensesCategory" {% if 'expensesCategoryChart' in selected_charts %}checked{% endif %}>
                  <label class="form-check-label" for="chartExpensesCategory">Dépenses par catégorie</label>
                </div>
              </div>
              <div class="col-sm-6 col-md-4 col-lg-3">
                <div class="form-check">
                  <input class="form-check-input chart-checkbox" type="checkbox" name="selected_charts" value="revenueTypeChart" id="chartRevenueType" {% if 'revenueTypeChart' in selected_charts %}checked{% endif %}>
                  <label class="form-check-label" for="chartRevenueType">Recettes par type d'acte</label>
                </div>
              </div>
              <div class="col-sm-6 col-md-4 col-lg-3">
                <div class="form-check">
                  <input class="form-check-input chart-checkbox" type="checkbox" name="selected_charts" value="topProductsChart" id="chartTopProducts" {% if 'topProductsChart' in selected_charts %}checked{% endif %}>
                  <label class="form-check-label" for="chartTopProducts">Top 10 produits en stock</label>
                </div>
              </div>
              <div class="col-sm-6 col-md-4 col-lg-3">
                <div class="form-check">
                  <input class="form-check-input chart-checkbox" type="checkbox" name="selected_charts" value="movementTypeChart" id="chartMovementType" {% if 'movementTypeChart' in selected_charts %}checked{% endif %}>
                  <label class="form-check-label" for="chartMovementType">Types de mouvements de stock</label>
                </div>
              </div>
            </div>
            <div class="mt-3 d-flex justify-content-center gap-2">
              <button type="button" class="btn btn-sm btn-outline-secondary" id="selectAllCharts">Sélectionner tout</button>
            </div>
          </div>
        </div>
        <div class="col-auto"> {# Moved this div to be after the chart selection card #}
          <button type="submit" class="btn btn-primary"><i class="fas fa-filter me-2" style="color: #FFFFFF;"></i>Filtrer</button>
        </div>
      </form>

      <div class="row g-4">
        <div class="col-12 col-lg-3"> {# Ajusté à col-lg-3 pour 4 colonnes #}
          <div class="p-3 kpi-card h-100 text-center">
            <div class="kpi-value">{{ metrics.total_factures }}</div>
            <div class="kpi-label">Nombre total des factures</div>
          </div>
        </div>
        <div class="col-12 col-lg-3"> {# Ajusté à col-lg-3 pour 4 colonnes #}
          <div class="p-3 kpi-card h-100 text-center">
            <div class="kpi-value">{{ metrics.total_patients }}</div>
            <div class="kpi-label">Patients uniques</div>
          </div>
        </div>
        <div class="col-12 col-lg-3"> {# Ajusté à col-lg-3 pour 4 colonnes #}
          <div class="p-3 kpi-card h-100 text-center">
            <div class="kpi-value">{{ "%.2f"|format(metrics.total_revenue) }} {{ currency }}</div>
            <div class="kpi-label">Total Recettes</div>
          </div>
        </div>
        <div class="col-12 col-lg-3"> {# Ajusté à col-lg-3 pour 4 colonnes #}
          <div class="p-3 kpi-card h-100 text-center">
            <div class="kpi-value">{{ metrics.total_appointments }}</div>
            <div class="kpi-label">Total des RDV</div> {# ÉTIQUETTE MODIFIÉE #}
          </div>
        </div>
        <div class="col-12 col-lg-3"> {# Ajusté à col-lg-3 pour 4 colonnes #}
          <div class="p-3 kpi-card h-100 text-center">
            <div class="kpi-value">{{ metrics.daily_appointments }}</div> {# NOUVELLE VALEUR #}
            <div class="kpi-label">Nombre de RDV du jour</div> {# ÉTIQUETTE MODIFIÉE #}
          </div>
        </div>
        <div class="col-12 col-lg-3"> {# Ajusté à col-lg-3 pour 4 colonnes #}
          <div class="p-3 kpi-card h-100 text-center">
            <div class="kpi-value">{{ "%.2f"|format(metrics.total_stock_value) }} {{ currency }}</div>
            <div class="kpi-label">Valeur du stock (Achat)</div> {# ÉTIQUETTE MODIFIÉE #}
          </div>
        </div>
        <div class="col-12 col-lg-3"> {# Ajusté à col-lg-3 pour 4 colonnes #}
          <div class="p-3 kpi-card h-100 text-center">
            <div class="kpi-value">{{ "%.2f"|format(metrics.total_expenses) }} {{ currency }}</div>
            <div class="kpi-label">Total Dépenses</div>
          </div>
        </div>
        <div class="col-12 col-lg-3"> {# Ajusté à col-lg-3 pour 4 colonnes #}
          <div class="p-3 kpi-card h-100 text-center">
            <div class="kpi-value">{{ "%.2f"|format(metrics.net_profit) }} {{ currency }}</div>
            <div class="kpi-label">Bénéfice Net</div>
          </div>
        </div>
      </div>

      <div class="row g-4 mt-4">
        <div class="col-12 col-xl-6 chart-container" id="consultChartContainer">
          <div class="card chart-card">
            <div class="card-header"><i class="fas fa-chart-line me-2" style="color: #FFFFFF;"></i>Consultations mensuelles</div>
            <div class="card-body">
              <canvas id="consultChart"></canvas>
              <div class="chart-analysis">
                <p>{{ charts.activite_analysis | safe }}</p>
              </div>
            </div>
          </div>
        </div>
        <div class="col-12 col-xl-6 chart-container" id="caChartContainer">
          <div class="card chart-card">
            <div class="card-header"><i class="fas fa-coins me-2" style="color: #FFFFFF;"></i>Total Recettes Mensuel</div>
            <div class="card-body">
              <canvas id="caChart"></canvas>
              <div class="chart-analysis">
                <p>{{ charts.ca_analysis | safe }}</p>
              </div>
            </div>
          </div>
        </div>
        <div class="col-12 col-xl-6 chart-container" id="genderChartContainer">
          <div class="card chart-card">
            <div class="card-header"><i class="fas fa-venus-mars me-2" style="color: #FFFFFF;"></i>Répartition par sexe</div>
            <div class="card-body">
              <canvas id="genderChart"></canvas>
              <div class="chart-analysis">
                <p>{{ charts.genre_analysis | safe }}</p>
              </div>
            </div>
          </div>
        </div>
        <div class="col-12 col-xl-6 chart-container" id="ageChartContainer">
          <div class="card chart-card">
            <div class="card-header"><i class="fas fa-chart-area me-2" style="color: #FFFFFF;"></i>Tranches d’âge</div>
            <div class="card-body">
              <canvas id="ageChart"></canvas>
              <div class="chart-analysis">
                <p>{{ charts.age_analysis | safe }}</p>
              </div>
            </div>
          </div>
        </div>
        <div class="col-12 col-xl-6 chart-container" id="salariesMonthlyChartContainer">
            <div class="card chart-card">
                <div class="card-header"><i class="fas fa-money-bill-wave me-2" style="color: #FFFFFF;"></i>Salaires mensuels</div>
                <div class="card-body">
                  <canvas id="salariesMonthlyChart"></canvas>
                  <div class="chart-analysis">
                    <p>{{ charts.salaries_monthly_analysis | safe }}</p>
                  </div>
                </div>
            </div>
        </div>
        <div class="col-12 col-xl-6 chart-container" id="rdvDoctorChartContainer">
            <div class="card chart-card">
                <div class="card-header"><i class="fas fa-user-md me-2" style="color: #FFFFFF;"></i>Rendez-vous par médecin</div>
                <div class="card-body">
                  <canvas id="rdvDoctorChart"></canvas>
                  <div class="chart-analysis">
                    <p>{{ charts.rdv_doctor_analysis | safe }}</p>
                  </div>
                </div>
            </div>
        </div>
        <div class="col-12 col-xl-6 chart-container" id="expensesCategoryChartContainer">
            <div class="card chart-card">
                <div class="card-header"><i class="fas fa-money-check-alt me-2" style="color: #FFFFFF;"></i>Dépenses par catégorie</div>
                <div class="card-body">
                  <canvas id="expensesCategoryChart"></canvas>
                  <div class="chart-analysis">
                    <p>{{ charts.expenses_category_analysis | safe }}</p>
                  </div>
                </div>
            </div>
        </div>
        <div class="col-12 col-xl-6 chart-container" id="revenueTypeChartContainer">
            <div class="card chart-card">
                <div class="card-header"><i class="fas fa-dollar-sign me-2" style="color: #FFFFFF;"></i>Recettes par type d'acte</div>
                <div class="card-body">
                  <canvas id="revenueTypeChart"></canvas>
                  <div class="chart-analysis">
                    <p>{{ charts.revenue_type_analysis | safe }}</p>
                  </div>
                </div>
            </div>
        </div>
        <div class="col-12 col-xl-6 chart-container" id="topProductsChartContainer">
            <div class="card chart-card">
                <div class="card-header"><i class="fas fa-box me-2" style="color: #FFFFFF;"></i>Top 10 produits en stock</div>
                <div class="card-body">
                  <canvas id="topProductsChart"></canvas>
                  <div class="chart-analysis">
                    <p>{{ charts.top_products_analysis | safe }}</p>
                  </div>
                </div>
            </div>
        </div>
        <div class="col-12 col-xl-6 chart-container" id="movementTypeChartContainer">
            <div class="card chart-card">
                <div class="card-header"><i class="fas fa-truck-loading me-2" style="color: #FFFFFF;"></i>Types de mouvements de stock</div>
                <div class="card-body">
                  <canvas id="movementTypeChart"></canvas>
                  <div class="chart-analysis">
                    <p>{{ charts.movement_type_analysis | safe }}</p>
                  </div>
                </div>
            </div>
        </div>
      </div>
    </div>
  </div>
</div>

<footer class="text-center py-3">
  <p class="small mb-1" style="color: white;">
    <i class="fas fa-heartbeat me-1"></i>
    SASTOUKA DIGITAL © 2025 • sastoukadigital@gmail.com tel +212652084735
  </p>
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0"></script>
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
const CHARTS={{ charts|tojson }};
const CURRENCY = "{{ currency | safe }}";
const SELECTED_CHARTS = {{ selected_charts|tojson }};

Chart.defaults.color='var(--text-color)';
Chart.defaults.font.family="'Poppins', sans-serif";
Chart.defaults.devicePixelRatio = 2;

if(window.ChartDataLabels){ Chart.register(window.ChartDataLabels); }

Chart.defaults.plugins.datalabels.font={weight:'600'};

Chart.defaults.plugins.tooltip.mode = 'index';
Chart.defaults.plugins.tooltip.intersect = false;
Chart.defaults.plugins.tooltip.callbacks.label = function(context) {
    let label = context.dataset.label || '';
    if (label) {
        label += ': ';
    }
    const isFinancialChart = [
        'Total Recettes', 'Dépenses', 'Recettes', 'Bénéfice Net', 'Salaires'
    ].includes(context.dataset.label);

    const isStockQuantityChart = context.dataset.label === 'Quantité en stock';

    if (isFinancialChart) {
        if (context.parsed.y !== undefined) {
            label += new Intl.NumberFormat('fr-FR', { style: 'currency', currency: CURRENCY, minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(context.parsed.y);
        } else if (context.parsed !== undefined) {
            label += new Intl.NumberFormat('fr-FR', { style: 'currency', currency: CURRENCY, minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(context.parsed);
        }
    } else if (isStockQuantityChart) {
        if (context.parsed.y !== undefined) {
            label += new Intl.NumberFormat('fr-FR').format(context.parsed.y) + ' unités';
        } else if (context.parsed !== undefined) {
             label += new Intl.NumberFormat('fr-FR').format(context.parsed) + ' unités';
        }
    } else if (context.dataset.label === 'Taux de conversion') {
        if (context.parsed.y !== undefined) {
            label += new Intl.NumberFormat('fr-FR', { style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(context.parsed.y / 100);
        } else if (context.parsed !== undefined) {
            label += new Intl.NumberFormat('fr-FR', { style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(context.parsed / 100);
        }
    }
    else {
        if (context.parsed.y !== undefined) {
            label += new Intl.NumberFormat('fr-FR').format(context.parsed.y);
        } else if (context.parsed !== undefined) {
            label += new Intl.NumberFormat('fr-FR').format(context.parsed);
        }
    }
    return label;
};
Chart.defaults.plugins.tooltip.backgroundColor = 'var(--card-bg)';
Chart.defaults.plugins.tooltip.titleColor = 'var(--text-color)';
Chart.defaults.plugins.tooltip.bodyColor = 'var(--text-color)';
Chart.defaults.plugins.tooltip.borderColor = 'var(--border-color)';
Chart.defaults.plugins.tooltip.borderWidth = 1;


const COLORS_PALETTE = {
  primary: getComputedStyle(document.documentElement).getPropertyValue('--primary-color').trim(),
  secondary: getComputedStyle(document.documentElement).getPropertyValue('--secondary-color').trim(),
  success: '#4CAF50',
  danger: '#F44336',
  warning: '#FFC107',
  info: '#2196F3',
  purple: '#9C27B0',
  teal: '#009688',
  orange: '#FF9800',
  pink: '#E91E63',
  cyan: '#00BCD4',
  lime: '#CDDC39',
  brown: '#795548',
  gray: '#607D8B'
};

const PIE_CHART_COLORS_1 = ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40", "#C9CBCF", "#6A8CFF", "#FF8C4A", "#A1F200"];
const PIE_CHART_COLORS_2 = ["#FF9800", "#673AB7", "#009688", "#CDDC39", "#795548", "#607D8B", "#F44336", "#2196F3", "#00BCD4", "#E91E63"];
const BAR_CHART_COLOR_1 = COLORS_PALETTE.primary;
const BAR_CHART_COLOR_2 = COLORS_PALETTE.secondary;


function createChart(ctx, type, labels, data, backgroundColor, options = {}, datasetLabel = '') {
    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'bottom',
                labels: { color: 'var(--text-color)' }
            },
            datalabels: {
                color: 'var(--button-text)',
                formatter: (value, context) => {
                    if (type === 'pie' || type === 'doughnut') {
                        const total = context.dataset.data.reduce((acc, val) => acc + val, 0);
                        return total > 0 ? (value * 100 / total).toFixed(1) + '%' : '';
                    }
                    return value;
                }
            },
            tooltip: {
                enabled: true
            }
        },
        scales: {
            x: {
                ticks: {
                    color: 'var(--text-color-light)',
                    maxRotation: 0,
                    minRotation: 0,
                    autoSkip: true,
                    maxTicksLimit: 10
                },
                grid: { color: 'rgba(var(--text-color-rgb), 0.1)' }
            },
            y: {
                beginAtZero: true,
                ticks: { color: 'var(--text-color-light)' },
                grid: { color: 'rgba(var(--text-color-rgb), 0.1)' }
            }
        }
    };

    const mergedOptions = Chart.helpers.merge(defaultOptions, options);

    if (type === 'bar' && mergedOptions.scales.x) {
        mergedOptions.scales.x.ticks.autoSkip = true;
        mergedOptions.scales.x.ticks.maxTicksLimit = 15;

        const avgLabelLength = labels.reduce((acc, label) => acc + label.length, 0) / labels.length;

        if (labels.length > 5 || avgLabelLength > 7) {
            mergedOptions.scales.x.ticks.maxRotation = 45;
            mergedOptions.scales.x.ticks.minRotation = 45;
        } else {
            mergedOptions.scales.x.ticks.maxRotation = 0;
            mergedOptions.scales.x.ticks.minRotation = 0;
        }

        if (labels.length > 7 && !options.indexAxis) {
            mergedOptions.indexAxis = 'y';
            const tempX = mergedOptions.scales.x;
            mergedOptions.scales.x = mergedOptions.scales.y;
            mergedOptions.scales.y = tempX;
            if (mergedOptions.scales.x) mergedOptions.scales.x.ticks.maxRotation = 0;
            if (mergedOptions.scales.y) {
                mergedOptions.scales.y.ticks.maxRotation = 0;
                mergedOptions.scales.y.grid.display = false;
            }
        }
    }

    if (type === 'bar') {
        mergedOptions.datasets = {
            bar: {
                categoryPercentage: 0.8,
                barPercentage: 0.9
            }
        };
    }

    if (!labels || labels.length === 0 || !data || data.every(val => val === 0)) {
        return new Chart(ctx, {
            type: type,
            data: {
                labels: [''],
                datasets: [{
                    data: [1],
                    backgroundColor: ['#cccccc'],
                    borderWidth: 0,
                    label: datasetLabel
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false },
                    datalabels: {
                        color: 'var(--text-color)',
                        formatter: () => 'Aucune donnée disponible',
                        align: 'center',
                        anchor: 'center',
                        font: { size: 14, weight: 'bold' }
                    }
                },
                scales: {
                    x: { display: false },
                    y: { display: false }
                },
                elements: { arc: { borderWidth: 0 } },
                layout: {
                    padding: {
                        left: 20, right: 20, top: 20, bottom: 20
                    }
                }
            },
            plugins: [ChartDataLabels]
        });
    }


    return new Chart(ctx, {
        type: type,
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: backgroundColor,
                borderRadius: type === 'bar' ? 4 : 0,
                borderColor: 'transparent',
                label: datasetLabel
            }]
        },
        options: mergedOptions,
        plugins: [ChartDataLabels]
    });
}


document.addEventListener('DOMContentLoaded', function() {
    const chartConfigs = [
        { id: 'consultChart', type: 'bar', labels: CHARTS.activite_labels, values: CHARTS.activite_values, color: BAR_CHART_COLOR_1, label: 'Consultations' },
        { id: 'caChart', type: 'bar', labels: CHARTS.ca_labels, values: CHARTS.ca_values, color: BAR_CHART_COLOR_2, options: { scales: { y: { ticks: { callback: (value) => new Intl.NumberFormat('fr-FR', { style: 'currency', currency: CURRENCY, minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value) } } } }, label: 'Total Recettes' },
        { id: 'genderChart', type: 'doughnut', labels: CHARTS.genre_labels, values: CHARTS.genre_values, color: PIE_CHART_COLORS_1, label: 'Patients' },
        { id: 'ageChart', type: 'bar', labels: CHARTS.age_labels, values: CHARTS.age_values, color: BAR_CHART_COLOR_1, label: 'Patients' },
        { id: 'salariesMonthlyChart', type: 'bar', labels: CHARTS.salaries_monthly_labels, values: CHARTS.salaries_monthly_values, color: BAR_CHART_COLOR_2, options: { scales: { y: { ticks: { callback: (value) => new Intl.NumberFormat('fr-FR', { style: 'currency', currency: CURRENCY, minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value) } } } }, label: 'Salaires' },
        { id: 'rdvDoctorChart', type: 'bar', labels: CHARTS.rdv_doctor_labels, values: CHARTS.rdv_doctor_values, color: BAR_CHART_COLOR_1, label: 'Rendez-vous' },
        { id: 'expensesCategoryChart', type: 'doughnut', labels: CHARTS.expenses_category_labels, values: CHARTS.expenses_category_values, color: PIE_CHART_COLORS_2, label: 'Dépenses' },
        { id: 'revenueTypeChart', type: 'doughnut', labels: CHARTS.revenue_type_labels, values: CHARTS.revenue_type_values, color: PIE_CHART_COLORS_1, label: 'Recettes' },
        { id: 'topProductsChart', type: 'bar', labels: CHARTS.top_products_labels, values: CHARTS.top_products_values, color: BAR_CHART_COLOR_2, options: { indexAxis: 'y', scales: { x: { ticks: { color: 'var(--text-color-light)' }, grid: { color: 'rgba(var(--text-color-rgb), 0.1)' } }, y: { ticks: { color: 'var(--text-color-light)' }, grid: { display: false } } } }, label: 'Quantité en stock' },
        { id: 'movementTypeChart', type: 'bar', labels: CHARTS.movement_type_labels, values: CHARTS.movement_type_values, color: BAR_CHART_COLOR_1, label: 'Mouvements' }
    ];

    chartConfigs.forEach(config => {
        const container = document.getElementById(config.id + 'Container');
        if (container) {
            if (SELECTED_CHARTS.includes(config.id)) {
                container.classList.remove('d-none');
                const ctx = document.getElementById(config.id).getContext('2d');
                createChart(ctx, config.type, config.labels, config.values, config.color, config.options, config.label);
            } else {
                container.classList.add('d-none');
            }
        }
    });

    document.getElementById('selectAllCharts').addEventListener('click', function() {
        document.querySelectorAll('.chart-checkbox').forEach(checkbox => {
            checkbox.checked = true;
        });
        document.getElementById('filterForm').submit();
    });

    // Handle form submission when a checkbox is changed
    document.querySelectorAll('.chart-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            // Remove the 'no_charts_selected' hidden input if a checkbox is manually checked
            const form = document.getElementById('filterForm');
            const hiddenInput = document.getElementById('no_charts_selected');
            if (hiddenInput) {
                hiddenInput.remove();
            }

            // If all checkboxes are unchecked, add the 'no_charts_selected' hidden input
            const allCheckboxes = document.querySelectorAll('.chart-checkbox');
            const anyChecked = Array.from(allCheckboxes).some(cb => cb.checked);

            if (!anyChecked) {
                const newHiddenInput = document.createElement('input');
                newHiddenInput.type = 'hidden';
                newHiddenInput.name = 'no_charts_selected';
                newHiddenInput.value = 'true';
                newHiddenInput.id = 'no_charts_selected'; // Add ID for easy removal
                form.appendChild(newHiddenInput);
            }
            document.getElementById('filterForm').submit();
        });
    });


    const flashMessages = document.querySelectorAll('.alert.alert-warning');
    let hasDataWarning = false;
    flashMessages.forEach(msg => {
        if (msg.textContent.includes("Aucune donnée disponible")) {
            hasDataWarning = true;
        }
    });

    if (hasDataWarning) {
        new bootstrap.Modal(document.getElementById('dataAlertModal')).show();
    }
});
</script>
<div class="modal fade" id="dataAlertModal" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header bg-warning">
        <h5 class="modal-title">
          <i class="fas fa-database me-2"></i>Données manquantes
        </h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div class="d-flex align-items-center gap-3">
          <i class="fas fa-exclamation-triangle text-warning fs-2"></i>
          <div>
            <p class="mb-0">Impossible de générer le rapport ou d'afficher certains graphiques car :</p>
            <ul class="mt-2">
              {% if not data_available %}
                <li>Aucune donnée pertinente trouvée pour la période et les filtres sélectionnés.</li>
              {% else %}
                <li>Vérifiez les dates ou le filtre médecin appliqués.</li>
                <li>Assurez-vous que les fichiers Excel nécessaires sont présents et non corrompus.</li>
                <li>Certaines colonnes de données critiques pourraient être manquantes ou mal nommées dans vos fichiers.</li>
              {% endif %}
            </ul>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal"></button>
      </div>
    </div>
  </div>
</div>

<style>
  #dataAlertModal .modal-content {
    border: 2px solid var(--warning-color);
    border-radius: var(--border-radius-lg);
    box-shadow: 0 0 15px rgba(255, 193, 7, 0.3);
  }

  #dataAlertModal .modal-header {
    border-bottom: 2px dashed var(--warning-color);
  }

  #dataAlertModal ul {
    list-style: none;
    padding-left: 1.5rem;
  }

  #dataAlertModal ul li {
    position: relative;
    padding-left: 1.5rem;
    margin-bottom: 0.5rem;
  }

  #dataAlertModal ul li::before {
    content: "❌";
    position: absolute;
    left: 0;
  }
  .card-body canvas {
    max-height: 300px;
    width: 100% !important;
    height: auto !important;
  }

</style>

</body>
</html>
"""
