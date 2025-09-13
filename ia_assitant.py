# ia_assitant.py - v5.0 - UX Améliorée avec Miniatures et Capacités Gemini étendues
import os
import pathlib
import datetime
import pandas as pd
import google.generativeai as genai

from flask import (
    Blueprint, render_template_string, session, redirect,
    url_for, flash, request, jsonify, Response
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# --- Imports des modules locaux ---
import utils
import login
import theme

# --- Configuration et Initialisation ---
ia_assitant_bp = Blueprint('ia_assitant', __name__, url_prefix='/ia_assitant')

# Association de la base de données à l'application Flask.
db = SQLAlchemy()

# --- Modèles de Base de Données ---
class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(150), nullable=False, default='Nouvelle Conversation')
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade="all, delete-orphan")

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'user' or 'model'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# --- Configuration de l'API Gemini ---
API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyALjQr4vF0coQaGDDtEr6wsdvRBUGCwPII") # Remplacez par votre clé
if API_KEY == "Votre_Cle_API_GOOGLE":
    print("AVERTISSEMENT: La clé API Google n'est pas configurée.")

try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except Exception as e:
    print(f"Erreur critique lors de la configuration de l'API Gemini : {e}")
    model = None

# --- Template de l'Interface Utilisateur ---
ia_assitant_template = """
<!DOCTYPE html>
<html lang="fr">
{{ pwa_head()|safe }}
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Assistant IA Synapse - EasyMedicaLink</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
    <style>
        :root {
            --background-main: #f0f4f9; --surface-color: #ffffff; --primary-accent: #1967d2;
            --text-primary: #202124; --text-secondary: #5f6368; --font-family: 'Google Sans', 'Segoe UI', system-ui, sans-serif;
            --border-radius: 16px; --box-shadow: 0 1px 3px rgba(0,0,0,0.1), 0 2px 6px rgba(0,0,0,0.06); --sidebar-width: 280px;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1.0); } }
        * { box-sizing: border-box; }
        body { font-family: var(--font-family); background: var(--background-main); color: var(--text-primary); margin: 0; display: flex; height: 100vh; }
        .sidebar { width: var(--sidebar-width); background: #e8f0fe; padding: 1rem; display: flex; flex-direction: column; border-right: 1px solid #dcdcdc; }
        .sidebar-header { display: flex; align-items: center; gap: 12px; padding-bottom: 1rem; border-bottom: 1px solid #d1e0ff; }
        .sidebar-header img { height: 32px; width: 32px; }
        .sidebar-header div { font-size: 1.1rem; font-weight: 500; }
        .new-chat-btn { background: var(--surface-color); color: var(--primary-accent); border: 1px solid #d1e0ff; border-radius: 24px; padding: 10px 16px; font-weight: 500; cursor: pointer; text-align: center; margin: 1rem 0; transition: background-color 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .new-chat-btn:hover { background-color: #f8f9fa; }
        .conversations-list { flex-grow: 1; overflow-y: auto; }
        .conversation-item { padding: 8px 12px; border-radius: 8px; cursor: pointer; margin-bottom: 8px; font-size: 0.9rem; transition: background-color 0.2s; display: flex; justify-content: space-between; align-items: center; }
        .conversation-item .title { flex-grow: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .conversation-item.active, .conversation-item:hover { background-color: #d1e0ff; }
        .delete-conv-btn { background: none; border: none; color: var(--text-secondary); cursor: pointer; padding: 4px 8px; border-radius: 50%; display: none; flex-shrink: 0; }
        .conversation-item:hover .delete-conv-btn { display: inline-block; }
        .delete-conv-btn:hover { background-color: #c4d7f7; color: #dc3545; }
        .main-container { flex-grow: 1; display: flex; justify-content: center; align-items: center; padding: 1rem; }
        .chat-container { width: 100%; max-width: 900px; height: 100%; display: flex; flex-direction: column; background: var(--surface-color); border-radius: var(--border-radius); box-shadow: var(--box-shadow); overflow: hidden; border: 1px solid #dee2e6; }
        .chat-header { padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem; background: #fff; border-bottom: 1px solid #dee2e6; }
        .chat-header-title { font-size: 1.25rem; font-weight: 600; color: var(--primary-accent); flex-grow: 1; }
        .back-to-home-btn { background: #f1f3f5; border: 1px solid #dee2e6; color: var(--text-secondary); border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; text-decoration: none; transition: background-color 0.2s; }
        .back-to-home-btn:hover { background-color: #e9ecef; }
        .chat-messages { flex-grow: 1; padding: 1.5rem; overflow-y: auto; display: flex; flex-direction: column; gap: 1.5rem; }
        .message { display: flex; align-items: flex-start; gap: 12px; max-width: 90%; animation: fadeIn 0.4s ease-out; position: relative; }
        .message .avatar { width: 40px; height: 40px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-weight: 500; flex-shrink: 0; font-size: 1.2rem; }
        .message .text-content { padding: 12px 18px; border-radius: var(--border-radius); line-height: 1.6; background: #f1f3f5; width: 100%; }
        .ai-message { align-self: flex-start; }
        .ai-message .avatar { background: var(--primary-accent); color: white; }
        .user-message { align-self: flex-end; flex-direction: row-reverse; }
        .user-message .avatar { background: #6c757d; color: white; }
        .user-message .text-content { background: var(--primary-accent); color: white; }
        .chat-input-area { padding: 1rem 1.5rem; border-top: 1px solid #dee2e6; background: #fff; }
        .file-preview-container { display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
        .file-preview { display: inline-flex; align-items: center; gap: 10px; background-color: #e9ecef; padding: 5px 8px; border-radius: 8px; font-size: 0.9rem; }
        .file-preview .cancel-file { cursor: pointer; color: var(--text-secondary); background: none; border: none; padding: 0 5px; font-size: 1.2rem; line-height: 1; }
        .chat-input-form { display: flex; gap: 10px; }
        #chat-textarea { flex-grow: 1; border: 1px solid #ced4da; border-radius: var(--border-radius); padding: 12px; font-size: 1rem; resize: none; }
        .chat-input-form button { background: var(--primary-accent); border: none; color: white; border-radius: 50%; width: 48px; height: 48px; cursor: pointer; flex-shrink: 0; }
        .chat-input-form button#file-btn { background: #f8f9fa; border: 1px solid #ced4da; color: var(--text-secondary); }
        .typing-indicator span { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #ccc; margin: 0 2px; animation: bounce 1.4s infinite ease-in-out both; }
        .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
        .action-buttons { position: absolute; bottom: 5px; right: -40px; display: flex; flex-direction: column; gap: 5px; opacity: 0; transition: all 0.2s; }
        .message:hover .action-buttons { opacity: 1; right: 5px; }
        .action-btn { background: #e9ecef; border: 1px solid #ced4da; color: var(--text-secondary); width: 30px; height: 30px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; }

        /* --- STYLES AJOUTÉS POUR UX --- */
        .message .text-content .message-attachments { display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
        .message .text-content .message-thumbnail { max-width: 150px; max-height: 150px; border-radius: 8px; cursor: pointer; border: 1px solid #dee2e6; }
        .file-preview .file-icon { font-size: 2rem; color: var(--text-secondary); }
        .text-content pre { background-color: #282c34; color: #abb2bf; border-radius: 8px; padding: 1rem; border: 1px solid #dee2e6; white-space: pre-wrap; word-wrap: break-word; }
        .text-content code { font-family: 'Courier New', Courier, monospace; }

        @media (max-width: 768px) {
            body { flex-direction: column; }
            .sidebar { width: 100%; height: 100%; border-right: none; border-bottom: 1px solid #dcdcdc; position: fixed; top: 0; left: 0; transform: translateX(-100%); transition: transform 0.3s ease-in-out; z-index: 1040; }
            .sidebar.show { transform: translateX(0); }
            .chat-container { border-radius: 0; box-shadow: none; height: 100vh; margin-top: 0; }
            .chat-header { padding: 0.75rem 1rem; }
            .chat-messages { padding: 1rem; gap: 1rem; }
            .chat-input-area { padding: 0.75rem 1rem; }
            .message { max-width: 95%; }
            .back-to-home-btn { display: none; }
            .sidebar-toggle-btn { display: block; background: none; border: none; color: var(--text-secondary); font-size: 1.5rem; cursor: pointer; }
        }
    </style>
</head>
<body>
    <div class="sidebar d-none d-md-flex">
        <div class="sidebar-header">
            <img src="{{ url_for('static', filename='pwa/icon-192.png') }}" alt="Logo">
            <div>EasyMedicaLink</div>
        </div>
        <button class="new-chat-btn" id="new-chat-btn"><i class="fas fa-plus"></i> Nouvelle Discussion</button>
        <div class="conversations-list" id="conversations-list"></div>
    </div>

    <div class="offcanvas offcanvas-start" tabindex="-1" id="offcanvasSidebar">
        <div class="offcanvas-header sidebar-header">
            <img src="{{ url_for('static', filename='pwa/icon-192.png') }}" alt="Logo">
            <h5 class="offcanvas-title">EasyMedicaLink</h5>
            <button type="button" class="btn-close text-reset" data-bs-dismiss="offcanvas" aria-label="Close"></button>
        </div>
        <div class="offcanvas-body d-flex flex-column" style="background: #e8f0fe;">
            <button class="new-chat-btn" id="new-chat-btn-mobile" onclick="startNewConversation()"><i class="fas fa-plus"></i> Nouvelle Discussion</button>
            <div class="conversations-list" id="conversations-list-mobile"></div>
        </div>
    </div>

    <div class="main-container">
        <div class="chat-container">
            <div class="chat-header">
                <button class="btn btn-light d-md-none" type="button" data-bs-toggle="offcanvas" data-bs-target="#offcanvasSidebar" aria-controls="offcanvasSidebar">
                    <i class="fas fa-bars"></i>
                </button>
                <a href="{{ url_for('accueil.accueil') }}" class="back-to-home-btn d-none d-md-flex" title="Retour à l'accueil">
                    <i class="fas fa-home"></i>
                </a>
                <div class="chat-header-title">Assistant Synapse</div>
            </div>

            <div class="chat-messages" id="chat-messages">
                <div class="message ai-message">
                    <div class="avatar"><i class="fas fa-robot"></i></div>
                    <div class="text-content"><p>Bonjour Dr. {{ (logged_in_doctor_name if logged_in_doctor_name and logged_in_doctor_name != 'None' else config.doctor_name or 'Connecté') }}. Je suis Synapse, votre assistant médical.</p></div>
                </div>
            </div>
            <div class="chat-input-area">
                <div id="file-preview-container"></div>
                <form class="chat-input-form" id="chat-form">
                    <button type="button" id="file-btn" title="Joindre un fichier"><i class="fas fa-paperclip"></i></button>
                    <input type="file" id="file-input" name="file_upload" accept=".pdf,.xlsx,.xls,.png,.jpg,.jpeg,.doc,.docx,.txt,.mp4,.mov,.mp3,.wav" style="display:none;" multiple>
                    <textarea id="chat-textarea" name="question" placeholder="Votre message..." required></textarea>
                    <button type="submit" title="Envoyer"><i class="fas fa-paper-plane"></i></button>
                </form>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    
    <script>
        let currentConversationId = null;
        let uploadedFilesCache = []; // Cache pour garder en mémoire les miniatures
        
        const chatForm = document.getElementById('chat-form');
        const chatMessages = document.getElementById('chat-messages');
        const fileBtn = document.getElementById('file-btn');
        const fileInput = document.getElementById('file-input');
        const questionTextarea = document.getElementById('chat-textarea');
        const filePreviewContainer = document.getElementById('file-preview-container');
        const newChatBtn = document.getElementById('new-chat-btn');
        const newChatBtnMobile = document.getElementById('new-chat-btn-mobile');
        const conversationsListDesktop = document.getElementById('conversations-list');
        const conversationsListMobile = document.getElementById('conversations-list-mobile');

        document.addEventListener('DOMContentLoaded', () => loadConversations());
        fileBtn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', handleFileSelection);
        newChatBtn.addEventListener('click', startNewConversation);
        if (newChatBtnMobile) {
            newChatBtnMobile.addEventListener('click', () => {
                startNewConversation();
                bootstrap.Offcanvas.getInstance(document.getElementById('offcanvasSidebar')).hide();
            });
        }

        questionTextarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
            }
        });

        function handleFileSelection() {
            filePreviewContainer.innerHTML = '';
            uploadedFilesCache = []; 
            const files = Array.from(fileInput.files);

            files.forEach(file => {
                const reader = new FileReader();
                const fileData = { name: file.name, type: file.type, dataURL: null };
                
                reader.onload = (e) => {
                    const preview = document.createElement('div');
                    preview.className = 'file-preview';
                    
                    if (file.type.startsWith('image/')) {
                        fileData.dataURL = e.target.result;
                        preview.innerHTML = `<img src="${e.target.result}" alt="${file.name}" style="width: 40px; height: 40px; border-radius: 4px; object-fit: cover;"> <span>${file.name}</span>`;
                    } else {
                        let iconClass = "fa-file";
                        if (file.type.includes("pdf")) iconClass = "fa-file-pdf";
                        if (file.type.includes("sheet") || file.type.includes("excel")) iconClass = "fa-file-excel";
                        if (file.type.includes("word")) iconClass = "fa-file-word";
                        if (file.type.includes("audio")) iconClass = "fa-file-audio";
                        if (file.type.includes("video")) iconClass = "fa-file-video";
                        preview.innerHTML = `<i class="fas ${iconClass} file-icon"></i> <span>${file.name}</span>`;
                    }
                    
                    const cancelButton = document.createElement('button');
                    cancelButton.type = 'button';
                    cancelButton.className = 'cancel-file';
                    cancelButton.innerHTML = '&times;';
                    cancelButton.dataset.filename = file.name;
                    cancelButton.onclick = (event) => removeFile(event, file.name);
                    
                    preview.appendChild(cancelButton);
                    filePreviewContainer.appendChild(preview);
                };
                
                if (file.type.startsWith('image/')) {
                    reader.readAsDataURL(file);
                } else {
                    reader.onload({ target: { result: null } }); // Trigger onload for non-image files
                }
                uploadedFilesCache.push(fileData);
            });
        }

        function removeFile(e, fileName) {
            const dt = new DataTransfer();
            Array.from(fileInput.files).forEach(file => {
                if (file.name !== fileName) dt.items.add(file);
            });
            fileInput.files = dt.files;
            
            // Re-render previews from the new file list
            handleFileSelection();
        }

        async function loadConversations() {
            const response = await fetch("{{ url_for('ia_assitant.get_conversations') }}");
            const conversations = await response.json();
            const renderList = (listElement) => {
                listElement.innerHTML = '';
                conversations.forEach(conv => {
                    const item = document.createElement('div');
                    item.className = 'conversation-item';
                    item.dataset.id = conv.id;
                    const title = document.createElement('span');
                    title.className = 'title';
                    title.textContent = conv.title;
                    title.onclick = () => {
                        loadConversation(conv.id);
                        if (window.innerWidth <= 768) {
                           bootstrap.Offcanvas.getInstance(document.getElementById('offcanvasSidebar')).hide();
                        }
                    };
                    const deleteBtn = document.createElement('button');
                    deleteBtn.className = 'delete-conv-btn';
                    deleteBtn.title = 'Supprimer la discussion';
                    deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
                    deleteBtn.onclick = (e) => deleteConversation(conv.id, e);
                    item.appendChild(title);
                    item.appendChild(deleteBtn);
                    listElement.appendChild(item);
                });
            };
            renderList(conversationsListDesktop);
            renderList(conversationsListMobile);
        }
        
        async function deleteConversation(id, event) {
            event.stopPropagation();
            Swal.fire({
                title: 'Êtes-vous sûr ?', text: "Cette action est irréversible !", icon: 'warning',
                showCancelButton: true, confirmButtonColor: '#d33', cancelButtonColor: '#3085d6',
                confirmButtonText: 'Oui, supprimer !', cancelButtonText: 'Annuler'
            }).then(async (result) => {
                if (result.isConfirmed) {
                    try {
                        const response = await fetch(`{{ url_for('ia_assitant.home_ia_assitant') }}conversations/delete/${id}`, { method: 'DELETE' });
                        const resData = await response.json();
                        if (!response.ok) throw new Error(resData.error || 'La suppression a échoué.');
                        Swal.fire('Supprimée!', 'La conversation a été supprimée.', 'success');
                        loadConversations();
                        if (currentConversationId == id) startNewConversation();
                    } catch (error) {
                        Swal.fire('Erreur!', error.message, 'error');
                    }
                }
            });
        }

        function startNewConversation() {
            currentConversationId = null;
            chatMessages.innerHTML = `<div class="message ai-message"><div class="avatar"><i class="fas fa-robot"></i></div><div class="text-content"><p>Bonjour Docteur {{ (logged_in_doctor_name if logged_in_doctor_name and logged_in_doctor_name != 'None' else config.doctor_name or 'Connecté') }}. Comment puis-je vous assister aujourd'hui ?</p></div></div>`;
            document.querySelectorAll('.conversation-item.active').forEach(el => el.classList.remove('active'));
            questionTextarea.focus();
        }

        async function loadConversation(id) {
            const response = await fetch(`{{ url_for('ia_assitant.home_ia_assitant') }}conversations/${id}`);
            const data = await response.json();
            chatMessages.innerHTML = '';
            data.messages.forEach(msg => {
                // Pour les anciens messages, on ne peut pas recréer les miniatures, on affiche juste le texte
                appendMessage(msg.role === 'model' ? 'ai' : 'user', msg.content, true, []);
            });
            chatMessages.querySelectorAll('pre code').forEach(block => hljs.highlightElement(block));
            currentConversationId = id;
            document.querySelectorAll('.conversation-item').forEach(el => el.classList.toggle('active', el.dataset.id == id));
            scrollToBottom();
        }

        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const question = questionTextarea.value.trim();
            if (!question && fileInput.files.length === 0) return;

            const attachmentsForDisplay = uploadedFilesCache.filter(f => f.dataURL);
            appendMessage('user', question, true, attachmentsForDisplay);
            questionTextarea.value = '';

            const formData = new FormData();
            formData.append('question', question);
            for (const file of fileInput.files) formData.append('file_upload', file);
            if (currentConversationId) formData.append('conversation_id', currentConversationId);
            
            fileInput.value = '';
            filePreviewContainer.innerHTML = '';
            
            const aiMessageDiv = appendMessage('ai', '<div class="typing-indicator"><span></span><span></span><span></span></div>', false);
            const aiTextContent = aiMessageDiv.querySelector('.text-content');
            
            try {
                const response = await fetch("{{ url_for('ia_assitant.chat_stream') }}", { method: 'POST', body: formData });
                if (!response.ok) throw new Error((await response.json()).error);
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullResponse = "";
                aiTextContent.innerHTML = "";

                if (response.headers.has('X-Conversation-Id') && !currentConversationId) {
                    currentConversationId = response.headers.get('X-Conversation-Id');
                    loadConversations();
                }

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    fullResponse += decoder.decode(value, { stream: true });
                    
                    let processedHtml = marked.parse(fullResponse);
                    processedHtml = processedHtml.replace(/\[thumbnail:([^\]]+)\]/g, (match, filename) => {
                        const cachedFile = uploadedFilesCache.find(f => f.name.trim() === filename.trim());
                        return (cachedFile && cachedFile.dataURL) ? `<img src="${cachedFile.dataURL}" alt="${filename}" class="message-thumbnail">` : '';
                    });

                    aiTextContent.innerHTML = processedHtml;
                    scrollToBottom();
                }
                
                aiTextContent.querySelectorAll('pre code').forEach(block => hljs.highlightElement(block));
                addAiMessageActions(aiMessageDiv, fullResponse);

            } catch (error) {
                aiTextContent.innerHTML = `<p style="color: #dc3545;"><strong>Erreur:</strong> ${error.message}</p>`;
            }
        });

        function appendMessage(sender, text, parseMarkdown = true, attachments = []) {
            const isUser = sender === 'user';
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user-message' : 'ai-message'}`;
            const avatarIcon = isUser ? '<i class="fas fa-user-md"></i>' : '<i class="fas fa-robot"></i>';
            const textContent = text ? (parseMarkdown ? marked.parse(text) : text) : '';
            
            let attachmentsHtml = '';
            if (attachments && attachments.length > 0) {
                attachmentsHtml = '<div class="message-attachments">';
                attachments.forEach(file => {
                    if (file.dataURL) attachmentsHtml += `<img src="${file.dataURL}" alt="${file.name}" class="message-thumbnail">`;
                });
                attachmentsHtml += '</div>';
            }

            messageDiv.innerHTML = `<div class="avatar">${avatarIcon}</div><div class="text-content">${textContent}${attachmentsHtml}</div>`;
            chatMessages.appendChild(messageDiv);
            scrollToBottom();
            
            if (!isUser && text && text.length > 1) {
                 addAiMessageActions(messageDiv, text);
            }
            return messageDiv;
        }
        
        function addAiMessageActions(messageDiv, rawContent) {
            let actions = messageDiv.querySelector('.action-buttons');
            if (!actions) {
                actions = document.createElement('div');
                actions.className = 'action-buttons';
                actions.innerHTML = `<button class="action-btn" title="Copier" onclick="copyToClipboard(this)"><i class="fas fa-copy"></i></button>`;
                messageDiv.appendChild(actions);
            }
            messageDiv.dataset.rawContent = rawContent;
        }

        function copyToClipboard(element) {
            const messageDiv = element.closest('.message');
            navigator.clipboard.writeText(messageDiv.dataset.rawContent);
            const icon = element.querySelector('i');
            icon.classList.replace('fa-copy', 'fa-check');
            setTimeout(() => { icon.classList.replace('fa-check', 'fa-copy'); }, 2000);
        }

        function scrollToBottom() { chatMessages.scrollTop = chatMessages.scrollHeight; }
    </script>
</body>
</html>
"""

# --- Routes du Blueprint ---

@ia_assitant_bp.route('/')
def home_ia_assitant():
    """ Affiche la page principale du chat. """
    if 'email' not in session: return redirect(url_for('login.login'))
    if session.get('role') not in ['admin', 'medecin']:
        flash("Accès non autorisé.", "danger")
        return redirect(url_for('accueil.accueil'))
    
    config = utils.load_config()
    user_email = session.get('email')
    all_users = login.load_users()
    user_info = all_users.get(user_email, {})
    logged_in_full_name = f"{user_info.get('prenom', '')} {user_info.get('nom', '')}".strip()
    
    if not logged_in_full_name:
        logged_in_full_name = None

    return render_template_string(
        ia_assitant_template, 
        logged_in_doctor_name=logged_in_full_name,
        config=config
    )

@ia_assitant_bp.route('/conversations', methods=['GET'])
def get_conversations():
    """ Récupère la liste des conversations pour l'utilisateur connecté. """
    if 'email' not in session: return jsonify({"error": "Non autorisé"}), 401
    user_email = session['email']
    convs = Conversation.query.filter_by(user_email=user_email).order_by(Conversation.created_at.desc()).all()
    return jsonify([{'id': c.id, 'title': c.title} for c in convs])

@ia_assitant_bp.route('/conversations/<int:conv_id>', methods=['GET'])
def get_conversation_messages(conv_id):
    """ Récupère les messages d'une conversation spécifique. """
    if 'email' not in session: return jsonify({"error": "Non autorisé"}), 401
    conv = Conversation.query.get(conv_id)
    if not conv or conv.user_email != session['email']:
        return jsonify({"error": "Conversation non trouvée"}), 404
    
    messages = [{'role': m.role, 'content': m.content} for m in conv.messages]
    return jsonify({'title': conv.title, 'messages': messages})

@ia_assitant_bp.route('/conversations/delete/<int:conv_id>', methods=['DELETE'])
def delete_conversation(conv_id):
    """ Supprime une conversation spécifique. """
    if 'email' not in session: return jsonify({"error": "Non autorisé"}), 401
    user_email = session['email']
    conv = Conversation.query.get(conv_id)

    if not conv or conv.user_email != user_email:
        return jsonify({"error": "Accès non autorisé"}), 403

    try:
        db.session.delete(conv)
        db.session.commit()
        return jsonify({"success": "Conversation supprimée"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erreur lors de la suppression de la conversation {conv_id}: {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@ia_assitant_bp.route('/chat-stream', methods=['POST'])
def chat_stream():
    """ Gère l'envoi de message et le streaming de la réponse. """
    if 'email' not in session: return jsonify({"error": "Non autorisé"}), 401
    if not model: return jsonify({"error": "Modèle IA non initialisé"}), 500

    data = request.form
    files = request.files.getlist('file_upload')
    question = data.get('question', '')
    conversation_id = data.get('conversation_id')

    if not question and not files:
        return jsonify({"error": "Veuillez fournir un message ou un fichier"}), 400

    if not utils.DYNAMIC_BASE_DIR:
        return jsonify({"error": "Le répertoire utilisateur n'est pas initialisé"}), 500
    dynamic_upload_folder = os.path.join(utils.DYNAMIC_BASE_DIR, "IA_Assistant_Uploads")
    os.makedirs(dynamic_upload_folder, exist_ok=True)
    
    prompt_parts, user_message_content, temp_files = [], [], []

    # --- NOUVEAU PROMPT SYSTÈME AMÉLIORÉ ---
    system_instruction = f"""
    Tu es Synapse, un assistant médical IA de pointe intégré à l'application EasyMedicaLink.
    Date et heure actuelles : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

    **Mission Principale** :
    Assister les professionnels de santé (médecins, pharmaciens, chercheurs) avec précision, rigueur et professionnalisme.

    **Périmètre de Compétences STRICT** :
    1.  **Domaines Autorisés** : Médecine, santé humaine, biologie, pharmacologie, radiologie, interprétation de résultats d'analyses, et gestion administrative de cabinet médical.
    2.  **Sujets Interdits** : TOUT ce qui ne relève pas des domaines ci-dessus (ex: histoire, finance, programmation, culture générale). Si une question est hors sujet, décline poliment en rappelant ta spécialisation. Exemple : "Je suis Synapse, un assistant spécialisé dans le domaine médical. Je ne peux malheureusement pas répondre aux questions concernant la programmation."

    **Directives de Communication** :
    - **Clarté et Structure** : Utilise Markdown (titres, listes, gras, tableaux) pour structurer tes réponses. Formate le code avec des blocs de code appropriés.
    - **Précision** : Fournis des réponses factuelles. Si une information est incertaine, nuance ta réponse.
    - **Multimodalité** : Tu peux recevoir des images, des documents, de l'audio et de la vidéo.
        - Pour analyser une image (radio, ECG, photo de symptôme), sois descriptif et méthodique.
        - **IMPORTANT** : Si tu fais référence à une image envoyée par l'utilisateur dans ta réponse, utilise la balise `[thumbnail:nom_exact_du_fichier.ext]` pour que l'interface puisse l'afficher.
    - **Sécurité** : Ne jamais demander, stocker ou deviner des informations personnelles identifiables (IPI) d'un patient. Toutes les données doivent rester anonymes.
    - **Langage** : Reste formel et professionnel. Adresse-toi à l'utilisateur comme "Docteur".
    """
    prompt_parts.append(system_instruction)

    try:
        for file in files:
            secure_name = secure_filename(file.filename)
            temp_path = os.path.join(dynamic_upload_folder, secure_name)
            file.save(temp_path)
            temp_files.append(temp_path)
            
            # Traitement spécifique pour les fichiers non-images/vidéos si nécessaire
            if secure_name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(temp_path)
                prompt_parts.append(f"Analyse du fichier Excel '{secure_name}':\n{df.to_string()}")
            else:
                uploaded_file = genai.upload_file(path=temp_path)
                prompt_parts.append(uploaded_file)
            user_message_content.append(f"Fichier joint: {secure_name}")

        if question:
            prompt_parts.append(question)
            user_message_content.append(question)

        user_email = session['email']
        if conversation_id:
            conv = Conversation.query.get(conversation_id)
            if not conv or conv.user_email != user_email:
                return jsonify({"error": "Conversation invalide"}), 403
        else:
            title = (question[:50] + '...') if len(question) > 50 else question
            if not title and files:
                title = f"Analyse de {files[0].filename}"
            conv = Conversation(user_email=user_email, title=title)
            db.session.add(conv)
            db.session.commit() # Commit pour obtenir l'ID de la nouvelle conversation

        user_msg = Message(conversation_id=conv.id, role='user', content="\n".join(user_message_content))
        db.session.add(user_msg)
        db.session.commit()

        # Construction de l'historique pour le modèle
        chat_history = []
        for msg in conv.messages:
             # Le rôle pour l'API est 'model' pour l'IA, 'user' pour l'utilisateur
            chat_history.append({'role': msg.role, 'parts': [part for part in msg.content.split('\n') if part]})

        chat_session = model.start_chat(history=chat_history[:-1]) # Historique sans le dernier message de l'utilisateur
        
        full_response_text = ""
        try:
            response_stream = chat_session.send_message(prompt_parts, stream=True)
            for chunk in response_stream:
                if chunk.text:
                    full_response_text += chunk.text
        except Exception as e:
            print(f"Erreur pendant l'appel à l'API Gemini: {e}")
            full_response_text = f"**Erreur de communication avec l'assistant IA.**\nDétails: {str(e)}"

        ai_msg = Message(conversation_id=conv.id, role='model', content=full_response_text)
        db.session.add(ai_msg)
        db.session.commit()

        def generate_stream(text_to_stream):
            yield text_to_stream

        resp = Response(generate_stream(full_response_text), mimetype='text/plain; charset=utf-8')
        resp.headers['X-Conversation-Id'] = str(conv.id)
        return resp

    except Exception as e:
        print(f"Erreur générale dans /chat-stream : {e}")
        return jsonify({"error": f"Une erreur est survenue: {str(e)}"}), 500
    finally:
        for temp_path in temp_files:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError as e:
                    print(f"Erreur lors de la suppression du fichier temporaire {temp_path}: {e}")