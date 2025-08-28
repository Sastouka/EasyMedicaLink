# routes.py
from __future__ import annotations

import os
import pandas as pd
import uuid
from datetime import datetime
from typing import Dict
from pathlib import Path

# Dépendances internes
import utils
import theme
from templates import (
    main_template,
    settings_template,
    alert_template,
)
from flask import (
    request, render_template_string, redirect, url_for,
    send_file, flash, jsonify, session, current_app
)
import login # Importe le module login pour accéder aux données des utilisateurs

# LISTS_FILE reste statique comme demandé, il ne dépend PAS de l'e-mail de l'admin.
# Ce chemin est relatif au fichier routes.py
LISTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Liste_Medications_Analyses_Radiologies.xlsx')

# ---------------------------------------------------------------------------
#  HELPERS INTERNES AU MODULE
# ---------------------------------------------------------------------------

def _config() -> Dict:
    """Charge la configuration de l'application."""
    # utils.load_config() utilisera implicitement le chemin défini dynamiquement par le before_request in app.py
    print(f"DEBUG (routes.py - _config): Tentative de chargement de la config depuis {utils.CONFIG_FILE}")
    cfg = utils.load_config()
    print(f"DEBUG (routes.py - _config): Config chargée: {cfg.keys()}")
    return cfg

# ---------------------------------------------------------------------------
#  ENREGISTREMENT DES ROUTES D'APPLICATION
# ---------------------------------------------------------------------------

def register_routes(app):
    """Attache toutes les routes à l'instance Flask passée en argument."""

    print(f"DEBUG (routes.py): Enregistrement des routes Flask.")

    # ---------------------------------------------------------------------
    #  PAGE PRINCIPALE – ENREGISTREMENT CONSULTATION
    # ---------------------------------------------------------------------
    @app.route("/consultation", methods=["GET", "POST"])
    def index():
        print(f"DEBUG (routes.py): Accès à la route /consultation (méthode: {request.method})")
        config = _config() # Utilise les chemins définis dynamiquement
        theme_names = list(theme.THEMES.keys())
        # utils.background_file est déjà mis à jour par utils.init_app lors du before_request

        # --- DÉBUT MODIFICATION: Récupérer le nom complet de l'utilisateur connecté et la liste des médecins ---
        logged_in_full_name = None
        user_email = session.get('email')
        user_role = session.get('role')
        admin_email_for_path = session.get('admin_email')

        doctors_for_select = [] # Liste pour le champ de sélection des médecins

        if admin_email_for_path:
            utils.set_dynamic_base_dir(admin_email_for_path)
            all_users_data = login.load_users() # Charger tous les utilisateurs pour cet admin

            # 1. Ajouter le nom du médecin défini par l'admin dans la config (s'il existe)
            #    et s'assurer qu'il est ajouté en premier ou qu'il ne soit pas en double avec les comptes existants
            config_doctor_name_from_admin = config.get('doctor_name', '').strip()
            if config_doctor_name_from_admin:
                doctors_for_select.append(config_doctor_name_from_admin)

            # 2. Ajouter les noms de tous les utilisateurs (médecins) qui appartiennent à cet administrateur.
            for email, user_info in all_users_data.items():
                if user_info.get('role') == 'medecin' and user_info.get('owner') == admin_email_for_path:
                    full_name = f"{user_info.get('prenom', '')} {user_info.get('nom', '')}".strip()
                    if full_name: # S'assurer que le nom n'est pas vide
                        doctors_for_select.append(full_name)

            # Supprimer les doublons et trier
            doctors_for_select = sorted(list(set(doctors_for_select)))

            # Déterminer le nom complet de l'utilisateur connecté pour l'affichage dans le header
            if user_email:
                user_info = all_users_data.get(user_email)
                if user_info:
                    logged_in_full_name = f"{user_info.get('prenom', '')} {user_info.get('nom', '')}".strip()
                    if not logged_in_full_name:
                        logged_in_full_name = None
        # --- FIN MODIFICATION ---

        # 1️⃣ Charger la liste "de base" depuis Excel ou constantes par défaut
        # LISTS_FILE est un chemin statique, donc pas de changement ici.
        base_meds = utils.default_medications_options
        base_analyses = utils.default_analyses_options
        base_radios = utils.default_radiologies_options

        if os.path.exists(LISTS_FILE):
            try:
                df_lists = pd.read_excel(LISTS_FILE, sheet_name=0, dtype=str).fillna('')
                if 'Medications' in df_lists.columns:
                    base_meds = df_lists['Medications'].dropna().astype(str).tolist()
                if 'Analyses' in df_lists.columns:
                    base_analyses = df_lists['Analyses'].dropna().astype(str).tolist()
                if 'Radiologies' in df_lists.columns:
                    base_radios = df_lists['Radiologies'].dropna().astype(str).tolist()
                print(f"DEBUG (routes.py - index): Listes par défaut chargées depuis {LISTS_FILE}")
            except Exception as e:
                print(f"ERREUR (routes.py - index): Erreur lors du chargement de {LISTS_FILE}: {e}")
        else:
            print(f"DEBUG (routes.py - index): Fichier {LISTS_FILE} non trouvé. Utilisation des listes par défaut intégrées.")


        # 2️⃣ Récupérer les ajouts du menu Paramètres
        cfg_meds = config.get("medications_options", [])
        cfg_analyses = config.get("analyses_options", [])
        cfg_radios = config.get("radiologies_options", [])

        # 2️⃣5️⃣ Récupérer la dernière consultation
        # Utilise utils.EXCEL_FILE_PATH qui est maintenant dynamique
        consult_file = Path(utils.EXCEL_FILE_PATH)
        last_consult = {}
        if consult_file.exists():
            try:
                df_last = pd.read_excel(consult_file, sheet_name=0, dtype=str).fillna('')
                if not df_last.empty:
                    last_consult = df_last.iloc[-1].to_dict()
                    print(f"DEBUG (routes.py - index): Dernière consultation chargée pour affichage.")
            except Exception as e:
                print(f"ERREUR (routes.py - index): Erreur lors du chargement de la dernière consultation depuis {consult_file}: {e}")
                last_consult = {}
        else:
            print(f"DEBUG (routes.py - index): Fichier de consultation {consult_file} non trouvé. Aucune dernière consultation à charger.")


        # 3️⃣ Fusionner Excel + Paramètres en supprimant les doublons
        meds_options = list(dict.fromkeys(base_meds + cfg_meds))
        analyses_options = list(dict.fromkeys(base_analyses + cfg_analyses))
        radiologies_options = list(dict.fromkeys(base_radios + cfg_radios))
        print(f"DEBUG (routes.py - index): Options fusionnées: Médicaments={len(meds_options)}, Analyses={len(analyses_options)}, Radiologies={len(radiologies_options)}")


        saved_medications, saved_analyses, saved_radiologies = [], [], []

        if request.method == "POST":
            print(f"DEBUG (routes.py - index): Traitement de la requête POST pour la consultation.")
            form_data = request.form.to_dict()
            consultation_date = request.form.get("consultation_date", datetime.now().strftime("%Y-%m-%d"))
            # Récupérer les listes multi-sélectionnées
            medication_list = request.form.getlist("medications_list")
            analyses_list = request.form.getlist("analyses_list")
            radiologies_list = request.form.getlist("radiologies_list")

            patient_id = form_data.get("patient_id", "").strip()
            nom = form_data.get("nom", "").strip()
            prenom = form_data.get("prenom", "").strip()
            patient_name = form_data.get("patient_name", "").strip() # Nom complet du patient

            # Si les champs nom/prenom sont vides mais patient_name est rempli, tenter de splitter
            if not nom and not prenom and patient_name:
                name_parts = patient_name.split(' ', 1)
                nom = name_parts[0] if name_parts else ""
                prenom = name_parts[1] if len(name_parts) > 1 else ""
            # Si nom et prenom sont remplis, reconstruire patient_name si nécessaire
            elif nom or prenom:
                patient_name = f"{nom} {prenom}".strip()

            certificate_category = form_data.get("certificate_category", "").strip()
            certificate_full_content = form_data.get("certificate_content", "").strip()
            rest_duration = utils.extract_rest_duration(certificate_full_content)

            if not patient_id:
                print(f"ATTENTION (routes.py - index): ID Patient manquant lors de la soumission.")
                return render_template_string(
                    alert_template,
                    alert_type="warning",
                    alert_title="Attention",
                    alert_text="Veuillez entrer l'ID du patient.",
                    redirect_url=url_for(".index"),
                )

            # Vérification d'unicité ID/nom (dans ConsultationData.xlsx pour cohérence)
            # Utilise utils.EXCEL_FILE_PATH qui est maintenant dynamique
            if os.path.exists(utils.EXCEL_FILE_PATH):
                try:
                    df_existing_consult = pd.read_excel(utils.EXCEL_FILE_PATH, sheet_name=0, dtype=str).fillna('')
                    if patient_id in df_existing_consult["patient_id"].astype(str).tolist():
                        existing_entries_for_id = df_existing_consult[df_existing_consult["patient_id"].astype(str) == patient_id]
                        if not existing_entries_for_id.empty:
                            most_common_full_name = ""
                            if 'nom' in existing_entries_for_id.columns and 'prenom' in existing_entries_for_id.columns:
                                temp_df = existing_entries_for_id.copy()
                                temp_df['full_name_combined'] = temp_df['nom'].fillna('') + ' ' + temp_df['prenom'].fillna('')
                                temp_df['full_name_combined'] = temp_df['full_name_combined'].str.strip()
                                if not temp_df['full_name_combined'].empty:
                                    most_common_full_name = temp_df['full_name_combined'].mode().iloc[0]
                                elif not existing_entries_for_id['patient_name'].empty:
                                    most_common_full_name = existing_entries_for_id['patient_name'].mode().iloc[0]
                            elif not existing_entries_for_id['patient_name'].empty:
                                most_common_full_name = existing_entries_for_id['patient_name'].mode().iloc[0]

                            if most_common_full_name.strip().lower() != patient_name.strip().lower():
                                print(f"ATTENTION (routes.py - index): Conflit ID patient. ID '{patient_id}' déjà associé à '{most_common_full_name}'.")
                                flash(f"L'ID patient '{patient_id}' est déjà associé à '{most_common_full_name}'. Veuillez utiliser ce nom ou un autre ID.", "error")
                                return redirect(url_for(".index"))
                except Exception as e:
                    print(f"ERREUR (routes.py - index): Erreur lors de la vérification d'unicité dans {utils.EXCEL_FILE_PATH}: {e}")
                    # Continuer le flux pour ne pas bloquer, mais le flash message est important.
                    flash(f"Erreur interne lors de la gestion de la consultation : {e}", "error")


            # Gestion de la fusion des données existantes (mise à jour de consultation existante)
            new_entry = True
            df = pd.DataFrame()
            # Utilise utils.EXCEL_FILE_PATH qui est maintenant dynamique
            if os.path.exists(utils.EXCEL_FILE_PATH):
                try:
                    df = pd.read_excel(utils.EXCEL_FILE_PATH, sheet_name=0, dtype=str).fillna('')
                    df['date_obj'] = pd.to_datetime(df['consultation_date'].astype(str).str[:10], errors='coerce').dt.date
                    current_date_obj = datetime.strptime(consultation_date, "%Y-%m-%d").date()

                    mask = (df['patient_id'] == patient_id) & (df['date_obj'] == current_date_obj)
                    existing_entries = df[mask]

                    if not existing_entries.empty:
                        new_entry = False
                        idx = existing_entries.index[0]
                        print(f"DEBUG (routes.py - index): Mise à jour d'une consultation existante pour ID {patient_id} à la date {consultation_date}.")

                        def merge_items(existing, new_items_list):
                            existing_str = str(existing) if pd.notna(existing) else ''
                            existing_list = [item.strip() for item in existing_str.split('; ') if item.strip()]
                            merged = list(dict.fromkeys(existing_list + new_items_list))
                            return merged

                        df.at[idx, 'medications'] = '; '.join(merge_items(df.at[idx, 'medications'], medication_list))
                        df.at[idx, 'analyses'] = '; '.join(merge_items(df.at[idx, 'analyses'], analyses_list))
                        df.at[idx, 'radiologies'] = '; '.join(merge_items(df.at[idx, 'radiologies'], radiologies_list))

                        update_fields = [
                            'clinical_signs', 'bp', 'temperature', 'heart_rate',
                            'respiratory_rate', 'diagnosis', 'doctor_comment',
                            'certificate_category', 'rest_duration'
                        ]
                        for field in update_fields:
                            if field == 'certificate_category':
                                df.at[idx, field] = certificate_category
                            elif field == 'rest_duration':
                                df.at[idx, field] = rest_duration
                            elif form_data.get(field):
                                df.at[idx, field] = form_data[field]

                        df.at[idx, 'nom'] = nom
                        df.at[idx, 'prenom'] = prenom
                        df.at[idx, 'patient_name'] = patient_name

                        if 'certificate_content' in df.columns:
                            df.at[idx, 'certificate_content'] = ''

                        df.drop('date_obj', axis=1, inplace=True)
                        df.to_excel(utils.EXCEL_FILE_PATH, index=False)
                        flash("Consultation mise à jour avec succès", "success")
                    else:
                        print(f"DEBUG (routes.py - index): Aucune consultation existante trouvée pour ID {patient_id} à la date {consultation_date}.")
                except Exception as e:
                    print(f"ERREUR (routes.py - index): Erreur lors de la lecture ou de la mise à jour de {utils.EXCEL_FILE_PATH}: {e}")
                    flash(f"Erreur interne lors de la gestion de la consultation : {e}", "error")


            if new_entry:
                print(f"DEBUG (routes.py - index): Création d'une nouvelle consultation pour ID {patient_id}.")
                new_row = {
                    "consultation_date": consultation_date,
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "nom": nom,
                    "prenom": prenom,
                    "date_of_birth": form_data.get("date_of_birth", "").strip(),
                    "gender": form_data.get("gender", "").strip(),
                    "age": form_data.get("patient_age", "").strip(),
                    "patient_phone": form_data.get("patient_phone", "").strip(),
                    "antecedents": form_data.get("antecedents", "").strip(),
                    "clinical_signs": form_data.get("clinical_signs", "").strip(),
                    "bp": form_data.get("bp", "").strip(),
                    "temperature": form_data.get("temperature", "").strip(),
                    "heart_rate": form_data.get("heart_rate", "").strip(),
                    "respiratory_rate": form_data.get("respiratory_rate", "").strip(),
                    "diagnosis": form_data.get("diagnosis", "").strip(),
                    "medications": "; ".join(medication_list),
                    "analyses": "; ".join(analyses_list),
                    "radiologies": "; ".join(radiologies_list),
                    "certificate_category": certificate_category,
                    "certificate_content":  "",
                    "rest_duration": rest_duration,
                    "doctor_comment": form_data.get("doctor_comment", "").strip(),
                    "consultation_id": str(uuid.uuid4()),
                    "Medecin_Email": user_email # Enregistre l'email du médecin connecté
                }

                required_cols_for_df = [
                    "consultation_date", "patient_id", "patient_name", "nom", "prenom",
                    "date_of_birth", "gender", "age", "patient_phone", "antecedents",
                    "clinical_signs", "bp", "temperature", "heart_rate", "respiratory_rate",
                    "diagnosis", "medications", "analyses", "radiologies",
                    "certificate_category", "certificate_content", "rest_duration",
                    "doctor_comment", "consultation_id", "Medecin_Email" # Ajout de Medecin_Email
                ]
                # S'assurer que toutes les colonnes nécessaires existent dans le DataFrame avant d'ajouter une nouvelle ligne
                if df.empty:
                    df = pd.DataFrame(columns=required_cols_for_df)
                else:
                    for col in required_cols_for_df:
                        if col not in df.columns:
                            df[col] = ''
                
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

                df.to_excel(utils.EXCEL_FILE_PATH, index=False)
                flash("Nouvelle consultation enregistrée", "success")

            session['prefill_suivi_patient_id'] = patient_id
            session['prefill_suivi_patient_name'] = patient_name

            # Recharger les données patient après modification
            utils.load_patient_data()
            saved_medications, saved_analyses, saved_radiologies = medication_list, analyses_list, radiologies_list

        # 4️⃣ Lecture des données pour l'affichage (après POST ou pour GET)
        consult_path = Path(utils.EXCEL_FILE_PATH)
        df_consult = pd.DataFrame()
        if consult_path.exists():
            try:
                df_consult = pd.read_excel(consult_path, sheet_name=0, dtype=str).fillna('')
                print(f"DEBUG (routes.py - index): Données de consultation lues depuis {consult_path} pour l'affichage du tableau.")
            except Exception as e:
                print(f"ERREUR (routes.py - index): Erreur lors du chargement de df_consult depuis {consult_path}: {e}")
                df_consult = pd.DataFrame()
        else:
            print(f"DEBUG (routes.py - index): Fichier de consultation {consult_path} non trouvé pour l'affichage du tableau.")


        consult_rows = df_consult.to_dict(orient="records")

        # Le dictionnaire patient_data est construit à partir des mappings de utils.py
        # qui sont maintenant mis à jour pour inclure nom et prenom
        patient_data = {
            pid: {
                "name":          utils.patient_id_to_name.get(pid, ""),
                "nom":           utils.patient_id_to_nom.get(pid, ""),
                "prenom":        utils.patient_id_to_prenom.get(pid, ""),
                "age":           utils.patient_id_to_age.get(pid, ""),
                "phone":         utils.patient_id_to_phone.get(pid, ""),
                "antecedents":   utils.patient_id_to_antecedents.get(pid, ""),
                "date_of_birth": utils.patient_id_to_dob.get(pid, ""),
                "gender":        utils.patient_id_to_gender.get(pid, ""),
            }
            for pid in utils.patient_ids
        }
        print(f"DEBUG (routes.py - index): patient_ids pour datalist: {utils.patient_ids[:5]}...")
        print(f"DEBUG (routes.py - index): patient_names pour datalist: {utils.patient_names[:5]}...")


        prefill_suivi_patient_id = session.pop('prefill_suivi_patient_id', None)
        prefill_suivi_patient_name = session.pop('prefill_suivi_patient_name', None)

        return render_template_string(
            main_template,
            config=config,
            current_date=datetime.now().strftime("%d/%m/%Y"),
            medications_options=meds_options,
            analyses_options=analyses_options,
            radiologies_options=radiologies_options,
            certificate_categories=utils.certificate_categories,
            default_certificate_text=utils.default_certificate_text,
            patient_ids=utils.patient_ids,
            patient_names=utils.patient_names,
            host_address=f"http://{utils.LOCAL_IP}:3000",
            patient_data=patient_data,
            saved_medications=saved_medications,
            saved_analyses=saved_analyses,
            saved_radiologies=saved_radiologies,
            theme_names=theme_names,
            consult_rows=consult_rows,
            last_consult=last_consult,
            prefill_suivi_patient_id=prefill_suivi_patient_id,
            prefill_suivi_patient_name=prefill_suivi_patient_name,
            # --- MODIFICATION: Passer le nom générique de l'utilisateur connecté ---
            logged_in_doctor_name=logged_in_full_name, # La variable du template est conservée pour moins de modifications HTML
            doctors_for_select=doctors_for_select,
            session=session # Passer la session entière pour accéder au rôle dans le JS du template
            # --- FIN MODIFICATION ---
        )

    # ---------------------------------------------------------------------
    #  API JSON / TABLEAU SUIVI
    # ---------------------------------------------------------------------
    @app.route("/get_last_consultation")
    def get_last_consultation():
        print(f"DEBUG (routes.py): Accès à la route /get_last_consultation.")
        pid = request.args.get("patient_id", "").strip()
        if not pid:
            print(f"DEBUG (routes.py - get_last_consultation): ID patient vide.")
            return jsonify({})
        
        # S'assurer que le chemin dynamique est défini pour l'utilisateur courant
        # avant de charger les données.
        admin_email = session.get('admin_email', 'default_admin@example.com')
        utils.set_dynamic_base_dir(admin_email)

        print(f"DEBUG (routes.py - get_last_consultation): Tentative de récupération de la dernière consultation pour ID: {pid}")
        # Utilise utils.EXCEL_FILE_PATH qui est maintenant dynamique
        if os.path.exists(utils.EXCEL_FILE_PATH):
            try:
                df = pd.read_excel(utils.EXCEL_FILE_PATH, sheet_name=0, dtype=str).fillna('')
                df = df[df["patient_id"].astype(str) == pid]
                if not df.empty:
                    last_consult = df.iloc[-1].to_dict()
                    last_consult.pop('certificate_content', None) # Supprime la clé si elle existe
                    print(f"DEBUG (routes.py - get_last_consultation): Dernière consultation trouvée pour {pid}.")
                    return jsonify(last_consult)
                else:
                    print(f"DEBUG (routes.py - get_last_consultation): Aucune consultation trouvée pour ID: {pid}.")
            except Exception as e:
                print(f"ERREUR (routes.py - get_last_consultation): Erreur lors de la lecture de {utils.EXCEL_FILE_PATH}: {e}")
        else:
            print(f"DEBUG (routes.py - get_last_consultation): Fichier {utils.EXCEL_FILE_PATH} non trouvé.")
        return jsonify({})

    @app.route("/get_consultations")
    def get_consultations():
        print(f"DEBUG (routes.py): Accès à la route /get_consultations.")
        pid = request.args.get("patient_id", "").strip()
        
        # S'assurer que le chemin dynamique est défini pour l'utilisateur courant
        # avant de charger les données.
        admin_email = session.get('admin_email', 'default_admin@example.com')
        utils.set_dynamic_base_dir(admin_email)

        print(f"DEBUG (routes.py - get_consultations): Tentative de récupération de toutes les consultations pour ID: {pid}")
        # Utilise utils.EXCEL_FILE_PATH qui est maintenant dynamique
        if os.path.exists(utils.EXCEL_FILE_PATH):
            try:
                df = pd.read_excel(utils.EXCEL_FILE_PATH, sheet_name=0, dtype=str).fillna('')
                df = df[df["patient_id"].astype(str) == pid]

                # --- DÉBUT DE LA CORRECTION ---
                # Créez la colonne 'patient_name' en combinant 'nom' et 'prenom' si elles existent,
                # sinon utilisez la colonne 'patient_name' existante ou une chaîne vide.
                if 'nom' in df.columns and 'prenom' in df.columns:
                    df['patient_name'] = df['nom'].fillna('') + ' ' + df['prenom'].fillna('')
                    df['patient_name'] = df['patient_name'].str.strip()
                    # Si 'patient_name' était vide après combinaison mais existait déjà, on peut aussi le prendre
                    df['patient_name'] = df.apply(
                        lambda row: row['patient_name'] if row['patient_name'] else (row['patient_name_old'] if 'patient_name_old' in row and pd.notnull(row['patient_name_old']) else ''),
                        axis=1
                    )
                elif 'patient_name' not in df.columns:
                    df['patient_name'] = '' # Assurez-vous que la colonne existe même si vide
                # --- FIN DE LA CORRECTION ---

                if 'certificate_content' in df.columns:
                    df = df.drop(columns=['certificate_content'])
                print(f"DEBUG (routes.py - get_consultations): {len(df)} consultations trouvées pour {pid}.")
                return df.to_json(orient="records", force_ascii=False)
            except Exception as e:
                print(f"ERREUR (routes.py - get_consultations): Erreur lors de la lecture de {utils.EXCEL_FILE_PATH}: {e}")
        else:
            print(f"DEBUG (routes.py - get_consultations): Fichier {utils.EXCEL_FILE_PATH} non trouvé.")
        return "[]"

    @app.route("/delete_consultation", methods=["POST"])
    def delete_consultation():
        print(f"DEBUG (routes.py): Accès à la route /delete_consultation (méthode: POST).")
        cid = request.form.get("consultation_id", "").strip()
        if cid:
            print(f"DEBUG (routes.py - delete_consultation): Tentative de suppression de la consultation avec ID: {cid}")
            try:
                # S'assurer que le chemin dynamique est défini pour l'utilisateur courant
                # avant de charger les données.
                admin_email = session.get('admin_email', 'default_admin@example.com')
                utils.set_dynamic_base_dir(admin_email)

                # Utilise utils.EXCEL_FILE_PATH qui est maintenant dynamique
                df = pd.read_excel(utils.EXCEL_FILE_PATH, sheet_name=0, dtype=str).fillna('')
                original_rows = len(df)
                df = df[df["consultation_id"] != cid]
                if len(df) < original_rows:
                    df.to_excel(utils.EXCEL_FILE_PATH, index=False)
                    print(f"DEBUG (routes.py - delete_consultation): Consultation {cid} supprimée avec succès.")
                    return "OK", 200
                else:
                    print(f"ATTENTION (routes.py - delete_consultation): Consultation {cid} non trouvée pour suppression.")
                    return "Not Found", 404
            except Exception as e:
                print(f"ERREUR (routes.py - delete_consultation): Erreur lors de la suppression de la consultation {cid} dans {utils.EXCEL_FILE_PATH}: {e}")
                return str(e), 500
        print(f"ATTENTION (routes.py - delete_consultation): Paramètres manquants pour la suppression.")
        return "Missing parameters", 400

    # ---------------------------------------------------------------------
    #  PDF À LA VOLÉE
    # ---------------------------------------------------------------------
    @app.route("/generate_pdf_route")
    def generate_pdf_route():
        print(f"DEBUG (routes.py): Accès à la route /generate_pdf_route.")
        form_data = {
            k: request.args.get(k, "") for k in [
                "doctor_name", "patient_name", "patient_age", "date_of_birth", "gender",
                "location", "clinical_signs", "bp", "temperature", "heart_rate",
                "respiratory_rate", "diagnosis", "certificate_content", "patient_id" # Ajout de patient_id
            ]
        }
        form_data["include_certificate"] = request.args.get("include_certificate", "off")
        medications = request.args.get("medications_list", "").split("\n")
        analyses    = request.args.get("analyses_list", "").split("\n")
        radiologies = request.args.get("radiologies_list", "").split("\n")

        medications = [item for item in medications if item.strip()]
        analyses    = [item for item in analyses if item.strip()]
        radiologies = [item for item in radiologies if item.strip()]

        # Ajout de l'e-mail du médecin pour le contenu du QR code
        form_data["doctor_email_for_qr"] = session.get('email', '')
        # Passage de la date actuelle pour le contenu du QR code
        form_data["current_date_for_qr"] = datetime.now().strftime('%d/%m/%Y')

        # S'assurer que le chemin dynamique est défini pour l'utilisateur courant
        # avant de générer le PDF.
        admin_email = session.get('admin_email', 'default_admin@example.com')
        utils.set_dynamic_base_dir(admin_email)

        # Utilise utils.PDF_FOLDER qui est maintenant dynamique
        pdf_filename = f"Ordonnance_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        pdf_path = os.path.join(utils.PDF_FOLDER, pdf_filename)
        print(f"DEBUG (routes.py - generate_pdf_route): Génération du PDF vers {pdf_path}")
        try:
            utils.generate_pdf_file(pdf_path, form_data, medications, analyses, radiologies)
            print(f"DEBUG (routes.py - generate_pdf_route): PDF généré avec succès.")
            return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))
        except Exception as e:
            print(f"ERREUR (routes.py - generate_pdf_route): Erreur lors de la génération du PDF : {e}")
            flash(f"Erreur lors de la génération du PDF : {e}", "error")
            return redirect(url_for(".index"))


    @app.route("/generate_history_pdf")
    def generate_history_pdf():
        print(f"DEBUG (routes.py): Accès à la route /generate_history_pdf.")
        pid   = request.args.get("patient_id_filter", "").strip()
        pname = request.args.get("patient_name_filter", "").strip()

        # S'assurer que le chemin dynamique est défini pour l'utilisateur courant
        # avant de charger les données.
        admin_email = session.get('admin_email', 'default_admin@example.com')
        utils.set_dynamic_base_dir(admin_email)

        if not os.path.exists(utils.EXCEL_FILE_PATH):
            print(f"ATTENTION (routes.py - generate_history_pdf): Fichier de données Excel non trouvé : {utils.EXCEL_FILE_PATH}")
            flash("Aucune donnée de consultation.", "warning")
            return redirect(url_for(".index"))

        df = pd.DataFrame()
        try:
            df = pd.read_excel(utils.EXCEL_FILE_PATH, sheet_name=0, dtype=str).fillna('')
            print(f"DEBUG (routes.py - generate_history_pdf): Données lues depuis {utils.EXCEL_FILE_PATH}.")
        except Exception as e:
            print(f"ERREUR (routes.py - generate_history_pdf): Erreur lors de la lecture de {utils.EXCEL_FILE_PATH} pour l'historique : {e}")
            flash(f"Erreur lors de la lecture des données pour l'historique : {e}", "error")
            return redirect(url_for(".index"))

        df_filtered = pd.DataFrame()
        if pid:
            df_filtered = df[df["patient_id"].astype(str) == pid]
            print(f"DEBUG (routes.py - generate_history_pdf): Filtrage par ID patient '{pid}'.")
        elif pname:
            df_filtered = df[df["patient_name"].astype(str).str.contains(pname, case=False, na=False)]
            print(f"DEBUG (routes.py - generate_history_pdf): Filtrage par nom patient '{pname}'.")
        else:
            print(f"ATTENTION (routes.py - generate_history_pdf): ID ou nom de patient manquant pour l'historique.")
            flash("Sélectionnez l'ID ou le nom du patient.", "warning")
            return redirect(url_for(".index"))

        if df_filtered.empty:
            print(f"DEBUG (routes.py - generate_history_pdf): Aucune consultation trouvée après filtrage.")
            flash("Aucune consultation trouvée pour ce patient.", "info")
            return redirect(url_for(".index"))
        
        if 'certificate_content' in df_filtered.columns:
            df_filtered = df_filtered.drop(columns=['certificate_content'])

        pdf_filename = f"Historique_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        pdf_path = os.path.join(utils.PDF_FOLDER, pdf_filename)
        print(f"DEBUG (routes.py - generate_history_pdf): Génération du PDF d'historique vers {pdf_path}")
        try:
            utils.generate_history_pdf_file(pdf_path, df_filtered)
            print(f"DEBUG (routes.py - generate_history_pdf): PDF d'historique généré avec succès.")
            return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))
        except Exception as e:
            print(f"ERREUR (routes.py - generate_history_pdf): Erreur lors de la génération du PDF d'historique : {e}")
            flash(f"Erreur lors de la génération du PDF d'historique : {e}", "error")
            return redirect(url_for(".index"))


    # ---------------------------------------------------------------------
    #  IMPORT EXCEL / BACKGROUND
    # ---------------------------------------------------------------------
    @app.route("/import_excel", methods=["POST"])
    def import_excel():
        print(f"DEBUG (routes.py): Accès à la route /import_excel (méthode: POST).")
        if "excel_file" not in request.files or request.files["excel_file"].filename == "":
            print(f"ATTENTION (routes.py - import_excel): Aucun fichier sélectionné pour l'importation Excel.")
            return jsonify({"status": "warning", "message": "Aucun fichier sélectionné."})
        f = request.files["excel_file"]
        filename = utils.secure_filename(f.filename)
        file_path = os.path.join(utils.EXCEL_FOLDER, filename)
        print(f"DEBUG (routes.py - import_excel): Tentative de sauvegarde du fichier Excel vers {file_path}")
        try:
            f.save(file_path)
            print(f"DEBUG (routes.py - import_excel): Fichier Excel '{filename}' sauvegardé avec succès.")
            # Tenter de lire le fichier importé et de mettre à jour les listes
            df_imported = pd.read_excel(file_path, dtype=str).fillna('')
            df_imported.columns = [c.lower() for c in df_imported.columns]

            cfg = _config()
            current_meds = set(cfg.get("medications_options", []))
            current_analyses = set(cfg.get("analyses_options", []))
            current_radios = set(cfg.get("radiologies_options", []))

            if "medications" in df_imported.columns:
                current_meds.update(df_imported["medications"].dropna().tolist())
            if "analyses" in df_imported.columns:
                current_analyses.update(df_imported["analyses"].dropna().tolist())
            if "radiologies" in df_imported.columns:
                current_radios.update(df_imported["radiologies"].dropna().tolist())

            cfg.update({
                "medications_options": sorted(list(current_meds)),
                "analyses_options": sorted(list(current_analyses)),
                "radiologies_options": sorted(list(current_radios)),
            })
            utils.save_config(cfg)
            print(f"DEBUG (routes.py - import_excel): Listes de médicaments/analyses/radiologies mises à jour.")

            # Si le fichier importé est info_Base_patient.xlsx ou ConsultationData.xlsx,
            # forcer un rechargement complet des données patient
            if filename == "info_Base_patient.xlsx" or filename == "ConsultationData.xlsx":
                utils.load_patient_data()
                print(f"DEBUG (routes.py - import_excel): Données patient rechargées suite à l'import de {filename}.")

            return jsonify({"status": "success", "message": "Import réussi."})
        except Exception as e:
            print(f"ERREUR (routes.py - import_excel): Erreur lors de l'importation du fichier Excel {filename}: {e}")
            return jsonify({"status": "error", "message": f"Erreur : {e}"})

    @app.route("/import_background", methods=["POST"])
    def import_background():
        print(f"DEBUG (routes.py): Accès à la route /import_background (méthode: POST).")
        if "background_file" not in request.files or request.files["background_file"].filename == "":
            print(f"ATTENTION (routes.py - import_background): Aucun fichier sélectionné pour l'arrière-plan.")
            return jsonify({"status": "warning", "message": "Aucun fichier sélectionné."})
        f = request.files["background_file"]
        filename = utils.secure_filename(f.filename)
        path = os.path.join(utils.BACKGROUND_FOLDER, filename)
        print(f"DEBUG (routes.py - import_background): Tentative de sauvegarde du fichier d'arrière-plan vers {path}")
        try:
            f.save(path)
            print(f"DEBUG (routes.py - import_background): Fichier d'arrière-plan '{filename}' sauvegardé avec succès.")
            ext = os.path.splitext(filename)[1].lower()
            if ext not in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".pdf"):
                os.remove(path) # Supprimer le fichier non supporté
                print(f"ATTENTION (routes.py - import_background): Format de fichier non supporté pour l'arrière-plan : {ext}")
                return jsonify({"status": "warning", "message": "Format non supporté (seuls PNG, JPG, JPEG, GIF, BMP, PDF sont acceptés)."})
            
            # Stocker UNIQUEMENT le nom du fichier dans la configuration
            cfg = _config()
            cfg["background_file_path"] = filename # MODIFICATION CLÉ ICI
            utils.save_config(cfg)
            
            # Mettre à jour la variable globale dans utils pour un effet immédiat
            utils.init_app(current_app) # Recharge la config et met à jour utils.background_file
            
            print(f"DEBUG (routes.py - import_background): Chemin de l'arrière-plan mis à jour dans la configuration et utils.background_file.")
            return jsonify({"status": "success", "message": f"Arrière plan importé : {filename}"})
        except Exception as e:
            print(f"ERREUR (routes.py - import_background): Erreur lors de l'importation de l'arrière-plan {filename}: {e}")
            return jsonify({"status": "error", "message": f"Erreur : {e}"})

    # ---------------------------------------------------------------------
    #  COMMENTAIRE DE SUIVI PATIENT
    # ---------------------------------------------------------------------
    @app.route("/update_comment", methods=["POST"])
    def update_comment():
        print(f"DEBUG (routes.py): Accès à la route /update_comment (méthode: POST).")
        pid = request.form.get("suivi_patient_id", "").strip()
        new_comment = request.form.get("new_doctor_comment", "").strip()
        if not pid:
            print(f"ATTENTION (routes.py - update_comment): ID patient manquant pour la mise à jour du commentaire.")
            flash("Veuillez entrer l'ID du patient.", "warning")
            return redirect(url_for(".index"))
        
        # S'assurer que le chemin dynamique est défini pour l'utilisateur courant
        # avant de charger les données.
        admin_email = session.get('admin_email', 'default_admin@example.com')
        utils.set_dynamic_base_dir(admin_email)

        print(f"DEBUG (routes.py - update_comment): Tentative de mise à jour du commentaire pour ID: {pid}")
        if os.path.exists(utils.EXCEL_FILE_PATH):
            try:
                df = pd.read_excel(utils.EXCEL_FILE_PATH, sheet_name=0, dtype=str).fillna('')
                if 'doctor_comment' not in df.columns:
                    df['doctor_comment'] = '' # Ajouter la colonne si elle n'existe pas
                
                # S'assurer que le patient existe avant de tenter la mise à jour
                if any(df["patient_id"].astype(str) == pid):
                    df.loc[df["patient_id"].astype(str) == pid, "doctor_comment"] = new_comment
                    df.to_excel(utils.EXCEL_FILE_PATH, index=False)
                    print(f"DEBUG (routes.py - update_comment): Commentaire mis à jour pour ID: {pid}.")
                    flash("Commentaire mis à jour.", "success")
                else:
                    print(f"ATTENTION (routes.py - update_comment): Patient avec ID {pid} non trouvé pour la mise à jour du commentaire.")
                    flash("Patient non trouvé.", "error")
            except Exception as e:
                print(f"ERREUR (routes.py - update_comment): Erreur lors de la mise à jour du commentaire dans {utils.EXCEL_FILE_PATH}: {e}")
                flash("Erreur interne lors de la mise à jour du commentaire.", "error")
        else:
            print(f"ATTENTION (routes.py - update_comment): Fichier de données Excel non trouvé : {utils.EXCEL_FILE_PATH}.")
            flash("Fichier de données non trouvé.", "error")
        return redirect(url_for(".index"))

    # ---------------------------------------------------------------------
    #  PARAMÈTRES APP
    # ---------------------------------------------------------------------

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        print(f"DEBUG (routes.py): Accès à la route /settings (méthode: {request.method}).")
        
        # S'assurer que le chemin dynamique est défini pour l'utilisateur courant
        admin_email = session.get('admin_email', 'default_admin@example.com')
        utils.set_dynamic_base_dir(admin_email)

        cfg = _config()
        theme_names = list(theme.THEMES.keys())

        if request.method == "POST":
            print(f"DEBUG (routes.py - settings): Traitement de la requête POST pour les paramètres.")
            cfg.update({
                "nom_clinique":         request.form.get("nom_clinique", ""),
                "cabinet":              request.form.get("cabinet", ""), # Assurez-vous que c'est bien 'cabinet' si utilisé
                "centre_medical":       request.form.get("centre_medecin", ""),
                "doctor_name":          request.form.get("nom_medecin", ""),
                "location":             request.form.get("lieu", ""),
                "theme":                request.form.get("theme", cfg.get("theme", theme.DEFAULT_THEME)),
                "background_file_path": request.form.get("arriere_plan", ""), # Stocke le nom du fichier directement depuis le formulaire
            })

            cfg["medications_options"] = (
                [item.strip() for item in request.form.get("liste_medicaments","").splitlines() if item.strip()]
                if request.form.get("liste_medicaments","") else utils.default_medications_options
            )
            cfg["analyses_options"] = (
                [item.strip() for item in request.form.get("liste_analyses","").splitlines() if item.strip()]
                if request.form.get("liste_analyses","") else utils.default_analyses_options
            )
            cfg["radiologies_options"] = (
                [item.strip() for item in request.form.get("liste_radiologies","").splitlines() if item.strip()]
                if request.form.get("liste_radiologies","") else utils.default_radiologies_options
            )
            print(f"DEBUG (routes.py - settings): Options des listes mises à jour à partir du formulaire.")

            utils.save_config(cfg)
            session["theme"] = cfg["theme"]

            # Re-initialisation de l'app pour s'assurer que les config globales sont à jour
            # et que background_file est bien rechargé.
            utils.init_app(current_app) # Important pour mettre à jour app.config
            # current_app.config["background_file_path"] est déjà mis à jour via utils.init_app
            # utils.background_file est déjà mis à jour via utils.init_app
            print(f"DEBUG (routes.py - settings): Configuration sauvegardée et utils.background_file mis à jour.")


            utils.load_patient_data() # Recharger les données patient au cas où des imports aient eu lieu

            if request.accept_mimetypes.accept_json:
                print(f"DEBUG (routes.py - settings): Réponse JSON pour les paramètres.")
                return jsonify({
                    "nom_clinique":         cfg.get("nom_clinique"),
                    "cabinet":              cfg.get("cabinet"),
                    "centre_medical":       cfg.get("centre_medical"),
                    "doctor_name":          cfg.get("doctor_name"),
                    "location":             cfg.get("location"),
                    "background_file_path": cfg.get("background_file_path",""),
                    "theme":                cfg.get("theme"),
                    "medications_options":  cfg.get("medications_options"),
                    "analyses_options":     cfg.get("analyses_options"),
                    "radiologies_options":  cfg.get("radiologies_options"),
                    "theme_names":          theme_names,
                    "theme_vars":           theme.current_theme(),
                })
            print(f"DEBUG (routes.py - settings): Réponse succès pour les paramètres (non JSON).")
            return jsonify({"status": "success"})

        print(f"DEBUG (routes.py - settings): Rendu du template des paramètres.")
        return render_template_string(
            settings_template,
            config=cfg,
            theme_names=theme_names,
            theme_vars=theme.current_theme()
        )

    # ---------------------------------------------------------------------
    #  TÉLÉCHARGEMENT DE L'APPLI WINDOWS
    # ---------------------------------------------------------------------
    @app.route("/download_app")
    def download_app():
        print(f"DEBUG (routes.py): Accès à la route /download_app.")
        # Cette route utilise utils.application_path, qui est statique pour le chemin de l'exécutable
        file_path = os.path.join(utils.application_path, "EasyMedicalink.rar")
        if os.path.exists(file_path):
            print(f"DEBUG (routes.py - download_app): Fichier de téléchargement trouvé : {file_path}")
            return send_file(file_path, as_attachment=True, download_name="EasyMedicalink.rar")
        print(f"ATTENTION (routes.py - download_app): Fichier de téléchargement non trouvé : {file_path}")
        flash("Le fichier n'existe pas.", "error")
        return redirect(url_for(".index"))
