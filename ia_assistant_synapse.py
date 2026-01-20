# -*- coding: utf-8 -*-
# Assistant IA Synapse v16.1 - Avec lecture email.json
import os
import json
import google.generativeai as genai
from flask import (
    Blueprint, render_template,
    request, jsonify, Response
)

# --- 1. CONFIGURATION DU BLUEPRINT ---
ia_assistant_synapse_bp = Blueprint(
    'ia_assistant_synapse', __name__,
    url_prefix='/synapse',
    template_folder='templates',
    static_folder='static'
)

# --- 2. CHARGEMENT CONFIGURATION (Json ou Env) ---
def get_google_api_key():
    # 1. Priorité aux variables d'environnement (Render)
    api_key = os.environ.get("GOOGLE_API_KEY")
    
    # 2. Sinon, lecture du fichier local email.json
    if not api_key:
        try:
            basedir = os.path.abspath(os.path.dirname(__file__))
            json_path = os.path.join(basedir, 'email.json')
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    api_key = config.get("GOOGLE_API_KEY")
        except Exception as e:
            print(f"Erreur lecture email.json: {e}")
            
    return api_key

API_KEY = get_google_api_key()

if not API_KEY or "AIza" not in API_KEY:
    print("❌ ERREUR CRITIQUE: Clé API Google manquante ou invalide.")
    model = None
else:
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-flash-latest')
        print("✅ Service IA (Synapse) initialisé avec succès.")
    except Exception as e:
        print(f"❌ Erreur configuration Gemini: {e}")
        model = None

# Base de connaissances
try:
    with open('knowledge.txt', 'r', encoding='utf-8') as f:
        KNOWLEDGE_BASE = f.read()
except FileNotFoundError:
    KNOWLEDGE_BASE = "Base de connaissances non trouvée."

# --- 3. ROUTES ---
@ia_assistant_synapse_bp.route('/')
def home():
    return render_template('ia_assistant_synapse.html')

@ia_assistant_synapse_bp.route('/chat-texte', methods=['POST'])
def chat_texte():
    if not model:
        return jsonify({"error": "Service IA non disponible (Clé API invalide)"}), 500
    
    data = request.json
    chat_history = data.get('history', [])
    if not chat_history:
        return jsonify({"error": "L'historique est vide"}), 400
    
    question = chat_history[-1]['parts'][0]
    
    try:
        system_instruction = f"""
        Tu es Synapse, un assistant IA professionnel intégré à l'application EasyMedicalink.
        Ton rôle est de répondre de manière factuelle et concise.
        
        **BASE DE CONNAISSANCES :**
        {KNOWLEDGE_BASE}
        """
        chat_session = model.start_chat(history=chat_history[:-1])
        response_stream = chat_session.send_message([system_instruction, question], stream=True)
        
        def generate_chunks():
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        
        return Response(generate_chunks(), mimetype='text/plain; charset=utf-8')

    except Exception as e:
        return jsonify({"error": f"Erreur IA: {str(e)}"}), 500