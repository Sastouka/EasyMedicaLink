# -*- coding: utf-8 -*-
# Assistant IA Synapse v16.0 - Version Texte Seulement
import os
import uuid
import time
import re
import google.generativeai as genai
from flask import (
    Blueprint, render_template,
    request, jsonify, Response, url_for
)

# --- 1. CONFIGURATION DU BLUEPRINT ---
ia_assistant_synapse_bp = Blueprint(
    'ia_assistant_synapse', __name__,
    url_prefix='/synapse',
    template_folder='templates',
    static_folder='static'
)
basedir = os.path.abspath(os.path.dirname(__file__))

# --- 2. CONFIGURATION DU SERVICE IA ---
# Clé API récupérée depuis les variables d'environnement
API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyDG42WVlylJ9Ox7TeTD-vrbo4Q1jhnnLz4")
if "Votre_Cle_API_GOOGLE" in API_KEY:
    print("AVERTISSEMENT: La clé d'accès Google n'est pas configurée pour l'assistant Synapse.")

try:
    genai.configure(api_key=API_KEY)
    # MODIFICATION : Utilisation du modèle Flash pour la rapidité et l'économie de quota
    model = genai.GenerativeModel('gemini-flash-latest')
except Exception as e:
    print(f"Erreur critique lors de la configuration du service IA : {e}")
    model = None

# Base de connaissances chargée depuis un fichier externe
try:
    with open('knowledge.txt', 'r', encoding='utf-8') as f:
        KNOWLEDGE_BASE = f.read()
except FileNotFoundError:
    KNOWLEDGE_BASE = "Aucune base de données textuelle (knowledge.txt) n'a été fournie."

# --- 3. ROUTES DU BLUEPRINT ---
@ia_assistant_synapse_bp.route('/')
def home():
    """Sert la page principale de l'assistant."""
    # Le dictionnaire des voix a été supprimé car la fonctionnalité vocale est désactivée.
    return render_template('ia_assistant_synapse.html')

@ia_assistant_synapse_bp.route('/chat-texte', methods=['POST'])
def chat_texte():
    """Gère les requêtes de chat textuelles et renvoie une réponse en streaming."""
    if not model:
        return jsonify({"error": "Le modèle IA n'est pas initialisé"}), 500
    
    data = request.json
    chat_history = data.get('history', [])
    if not chat_history:
        return jsonify({"error": "L'historique est vide"}), 400
    
    question = chat_history[-1]['parts'][0]
    
    try:
        # Prompt système amélioré pour un ton professionnel et neutre, focalisé sur le texte.
        system_instruction = f"""
        Tu es Synapse, un assistant IA professionnel intégré à l'application EasyMedicalink.
        Ta personnalité est experte, claire et concise. Tu es un outil d'aide à la décision pour les professionnels.
        
        **Mission et Périmètre STRICT :**
        - Ta mission est de fournir des informations factuelles et utiles basées **uniquement** sur la BASE DE CONNAISSANCES fournie.
        - **NE JAMAIS** répondre à des questions hors du domaine médical ou de la gestion de cabinet. Si la question est hors sujet, décline poliment : "Ma spécialisation se limite au domaine médical. Comment puis-je vous aider dans ce contexte ?"
        
        **Directives de Réponse :**
        - **Format :** Structure tes réponses avec des titres (en gras avec **), des listes à puces (-), et mets en évidence les termes clés **en gras**.
        - **Ton :** Adopte un ton direct et professionnel. Évite les salutations superflues comme "Bonjour". Va droit au but. Ne te réfère pas à l'utilisateur par un titre (comme "Docteur").
        - **Confidentialité :** Ne révèle jamais ta nature d'IA. Ne mentionne jamais les noms de fichiers (`.py`, `.xlsx`).
        
        **BASE DE CONNAISSANCES :**
        ---
        {KNOWLEDGE_BASE}
        ---
        """
        chat_session = model.start_chat(history=chat_history[:-1])
        response_stream = chat_session.send_message([system_instruction, question], stream=True)
        
        def generate_chunks():
            """Génère les morceaux de texte de la réponse."""
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        
        return Response(generate_chunks(), mimetype='text/plain; charset=utf-8')

    except Exception as e:
        print(f"Erreur lors de la conversation : {e}")
        return jsonify({"error": f"Une erreur est survenue: {str(e)}"}), 500