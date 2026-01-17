# login.py
# ──────────────────────────────────────────────────────────────────────────────
# Module d'authentification 100% LOCAL & RESPONSIVE - DESIGN PRO TURQUOISE
# - Logique originale conservée (HMAC, Fichiers cachés, Champs spécifiques)
# - Nouveau Design : Split Screen, Palette Turquoise, QR Code, Icône robuste
# - AJOUT : Politique de Confidentialité & Support intégrés
# ──────────────────────────────────────────────────────────────────────────────

import os
import json
import hmac
import hashlib
import ctypes
import platform
import socket
import secrets
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, Dict, Any

from flask import (
    Blueprint,
    request,
    render_template_string,
    redirect,
    url_for,
    flash,
    session,
    current_app
)
from flask_mail import Message

import utils
from activation import TRIAL_DAYS

# ──────────────────────────────────────────────────────────────────────────────
# Configuration et Constantes
# ──────────────────────────────────────────────────────────────────────────────
login_bp = Blueprint("login", __name__)
USERS_FILE: Optional[Path] = None
HMAC_KEY = b"votre_cle_secrete_interne_a_remplacer"

ALL_BLUEPRINTS = [
    'accueil', 'rdv', 'facturation', 'biologie', 'radiologie', 'pharmacie',
    'comptabilite', 'statistique', 'administrateur_bp', 'developpeur_bp',
    'patient_rdv', 'routes', 'gestion_patient', 'guide', 'ia_assitant', 'ia_assistant_synapse'
]

# ──────────────────────────────────────────────────────────────────────────────
# Gestion des Fichiers & Sécurité (LOGIQUE ORIGINALE CONSERVÉE)
# ──────────────────────────────────────────────────────────────────────────────
def _set_login_paths():
    global USERS_FILE
    if USERS_FILE:
        return
    try:
        medicalink_data_root = Path(utils.application_path) / "MEDICALINK_DATA"
        medicalink_data_root.mkdir(parents=True, exist_ok=True)
        if platform.system() == "Windows":
            ctypes.windll.kernel32.SetFileAttributesW(str(medicalink_data_root), 0x02)
    except Exception as e:
        print(f"Info: {e}")
    USERS_FILE = medicalink_data_root / ".users.json"

def _sign(data: bytes) -> str:
    return hmac.new(HMAC_KEY, data, hashlib.sha256).hexdigest()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def generate_reset_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)

def _load_data_from_file(file_path: Optional[Path]) -> Dict[str, Any]:
    _set_login_paths()
    if not file_path or not file_path.exists():
        return {}
    try:
        raw_content = file_path.read_bytes()
        if not raw_content: return {}
        if b"\n---SIGNATURE---\n" not in raw_content:
             try: return json.loads(raw_content.decode("utf-8"))
             except: return {}
        payload, signature = raw_content.rsplit(b"\n---SIGNATURE---\n", 1)
        if not hmac.compare_digest(_sign(payload), signature.decode()):
            return {}
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return {}

def _save_data_to_file(data: Dict[str, Any], file_path: Optional[Path]):
    _set_login_paths()
    if not file_path: return
    try:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        signature = _sign(payload).encode()
        file_path.write_bytes(payload + b"\n---SIGNATURE---\n" + signature)
    except Exception:
        pass

def load_users() -> Dict[str, Any]: return _load_data_from_file(USERS_FILE)
def save_users(users: Dict[str, Any]): _save_data_to_file(users, USERS_FILE)
def _is_email_globally_unique(email_to_check: str) -> bool: return email_to_check not in load_users()

# ──────────────────────────────────────────────────────────────────────────────
# Logique Interne
# ──────────────────────────────────────────────────────────────────────────────
def _user() -> Optional[dict]:
    email = session.get("email")
    if not email: return None
    return load_users().get(email)

def lan_ip() -> str:
    ip = socket.gethostbyname(socket.gethostname())
    if ip.startswith("127."):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]
        except: ip = "0.0.0.0"
    return ip

def _find_user_in_centralized_users_file(target_email: str, target_password_hash: str) -> Optional[Dict]:
    user = load_users().get(target_email)
    if user and user.get("password") == target_password_hash:
        return {
            "user_data": user, 
            "admin_owner_email": user.get("owner", target_email), 
            "actual_role": user.get("role", "admin")
        }
    return None

# ──────────────────────────────────────────────────────────────────────────────
# TEMPLATE HTML PRO TURQUOISE (DESIGN UPDATED)
# ──────────────────────────────────────────────────────────────────────────────

# Variable commune contenant le CSS et le Head
head_style_pro = """
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    {{ pwa_head()|safe }}
    
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">

    <style>
        :root {
            /* Palette Turquoise Pro */
            --primary-color: #00B4DB; 
            --secondary-color: #0083B0;
            --bg-gradient: linear-gradient(135deg, #00B4DB 0%, #0083B0 100%);
            --text-color: #5a5c69;
            --bg-page: #f0f2f5;
        }

        body {
            font-family: 'Poppins', sans-serif;
            background-color: var(--bg-page);
            height: 100vh;
            overflow-x: hidden;
        }

        .login-container { min-height: 100vh; display: flex; }

        /* --- VISUAL SIDE (Gauche) --- */
        .login-visual {
            flex: 1;
            background: var(--bg-gradient);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            color: white;
            padding: 2rem;
            position: relative;
            overflow: hidden;
        }
        .login-visual::before {
            content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0) 60%);
            animation: rotate 40s linear infinite;
        }
        @keyframes rotate { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        .visual-content { position: relative; z-index: 2; text-align: center; max-width: 85%; width: 100%; }

        /* Logo & Fallback */
        .logo-container { height: 110px; display: flex; align-items: center; justify-content: center; margin-bottom: 1.5rem; }
        .visual-logo-img { max-height: 100px; width: auto; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1)); }
        .fallback-icon { font-size: 5rem; color: white; display: none; text-shadow: 0 4px 10px rgba(0,0,0,0.2); }

        /* Testimonials Carousel Style */
        .testimonial-card {
            background: rgba(255,255,255,0.15); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.3);
            border-radius: 15px; padding: 20px; margin: 10px auto; max-width: 500px; color: white;
        }
        .stars { color: #FFD700; margin-bottom: 5px; }
        .quote { font-style: italic; font-size: 0.95rem; }
        .author { font-weight: 700; margin-top: 10px; font-size: 0.9rem; text-align: right; }

        /* --- FORM SIDE (Droite) --- */
        .login-form-wrapper {
            flex: 1; display: flex; flex-direction: column;
            justify-content: center; align-items: center;
            padding: 2rem; background: white; position: relative;
        }

        .form-card {
            width: 100%; max-width: 480px; padding: 2rem;
            animation: fadeInUp 0.7s ease-out;
        }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }

        h2 { font-weight: 700; color: #2c3e50; margin-bottom: 0.5rem; }
        p.subtitle { color: #858796; margin-bottom: 1.5rem; font-size: 0.9rem; }
        .text-primary-custom { color: var(--primary-color) !important; }

        /* Inputs Modernes */
        .form-floating > .form-control, .form-select {
            border-radius: 0.5rem; border: 1px solid #d1d3e2; height: calc(3.5rem + 2px);
        }
        .form-floating > .form-control:focus, .form-select:focus {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 0.25rem rgba(0, 180, 219, 0.25);
        }
        .form-floating > label { color: #858796; }

        /* Boutons */
        .btn-primary-custom {
            background: var(--bg-gradient); border: none; border-radius: 0.5rem; padding: 0.8rem;
            font-weight: 600; font-size: 1rem; transition: all 0.3s;
            width: 100%; color: white; box-shadow: 0 4px 15px rgba(0, 131, 176, 0.3);
        }
        .btn-primary-custom:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0, 131, 176, 0.4); color: white; }

        .links { margin-top: 1rem; text-align: center; font-size: 0.9rem; }
        .links a, .footer-link { color: var(--primary-color); text-decoration: none; font-weight: 500; cursor: pointer; }
        .links a:hover, .footer-link:hover { color: var(--secondary-color); text-decoration: underline; }

        .alert { border-radius: 0.5rem; font-size: 0.85rem; border: none; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .password-toggle { position: absolute; right: 15px; top: 20px; cursor: pointer; color: #aaa; z-index: 10; }

        /* Footer & QR */
        .footer-section { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e3e6f0; }
        .qr-code-box img { border: 1px solid #e3e6f0; padding: 2px; border-radius: 4px; }
        
        /* Modale Style */
        .modal-header { background: var(--bg-gradient); color: white; border-bottom: none; }
        .modal-title { font-weight: 600; }
        .btn-close-white { filter: invert(1) grayscale(100%) brightness(200%); }
        
        /* Mobile */
        @media (max-width: 991px) {
            .login-visual { display: none; }
            .login-form-wrapper { background: var(--bg-page); }
            .form-card { background: white; border-radius: 1rem; box-shadow: 0 10px 30px rgba(0,0,0,0.08); padding: 1.5rem; }
        }
    </style>
</head>
"""

# Template Javascript commun (Fallback Icon + Toggle Password)
js_scripts = """
<script>
    function togglePassword(inputId) {
        const input = document.getElementById(inputId);
        const icon = input.parentElement.querySelector('.password-toggle');
        if (input.type === "password") {
            input.type = "text";
            icon.classList.remove("fa-eye");
            icon.classList.add("fa-eye-slash");
        } else {
            input.type = "password";
            icon.classList.remove("fa-eye-slash");
            icon.classList.add("fa-eye");
        }
    }
</script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
"""

# Template HTML principal (Wrapper)
def render_auth_page(content_html, title="EasyMedicaLink", show_visual=True):
    visual_html = """
    <div class="login-visual">
        <div class="visual-content">
            <div class="logo-container">
                <img src="/static/pwa/icon-512.png" alt="EasyMedicaLink" class="visual-logo-img"
                     onerror="this.style.display='none'; document.getElementById('fallback-icon-desktop').style.display='block';">
                <i id="fallback-icon-desktop" class="fas fa-heartbeat fallback-icon"></i>
            </div>
            
            <h1 class="display-5 fw-bold mb-3">EasyMedicaLink</h1>
            <p class="lead mb-4 opacity-75">La gestion clinique 100% Locale, Sécurisée et sans abonnement.</p>
            
            <div id="reviewCarousel" class="carousel slide" data-bs-ride="carousel" data-bs-interval="4000">
                <div class="carousel-inner">
                    <div class="carousel-item active"><div class="testimonial-card"><div class="stars"><i class="fas fa-star"></i><i class="fas fa-star"></i><i class="fas fa-star"></i><i class="fas fa-star"></i><i class="fas fa-star"></i></div><p class="quote mb-0">"Une interface incroyablement intuitive."</p><div class="author">- Dr. Amine</div></div></div>
                    <div class="carousel-item"><div class="testimonial-card"><div class="stars"><i class="fas fa-star"></i><i class="fas fa-star"></i><i class="fas fa-star"></i><i class="fas fa-star"></i><i class="fas fa-star"></i></div><p class="quote mb-0">"La facturation est devenue un jeu d'enfant."</p><div class="author">- Dr. Fatou</div></div></div>
                    <div class="carousel-item"><div class="testimonial-card"><div class="stars"><i class="fas fa-star"></i><i class="fas fa-star"></i><i class="fas fa-star"></i><i class="fas fa-star"></i><i class="fas fa-star-half-alt"></i></div><p class="quote mb-0">"Support technique très réactif."</p><div class="author">- Dr. Mamadou</div></div></div>
                </div>
            </div>
            
            <div class="mt-5 small opacity-50">&copy; EasyMedicaLink - 100% Offline</div>
        </div>
    </div>
    """ if show_visual else ""

    current_date_str = date.today().strftime('%B %Y')

    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    {head_style_pro}
    <title>{title}</title>
    <body>
    <div class="login-container">
        {visual_html}
        <div class="login-form-wrapper">
            <div class="form-card">
                <div class="text-center mb-4 d-lg-none">
                     <div style="height: 70px; display: flex; align-items: center; justify-content: center;">
                        <img src="/static/pwa/icon-512.png" alt="Logo" style="max-height: 60px;"
                             onerror="this.style.display='none'; document.getElementById('fallback-icon-mobile').style.display='inline-block';">
                        <i id="fallback-icon-mobile" class="fas fa-heartbeat fa-3x text-primary-custom" style="display:none;"></i>
                    </div>
                    <h4 class="fw-bold text-primary-custom mt-2">EasyMedicaLink</h4>
                </div>

                {{% with messages = get_flashed_messages(with_categories=true) %}}
                    {{% if messages %}}
                        {{% for category, message in messages %}}
                            <div class="alert alert-{{{{ 'danger' if category=='danger' else 'success' if category=='success' else 'primary' }}}} d-flex align-items-center">
                                <i class="fas fa-{{{{ 'exclamation-circle' if category=='danger' else 'check-circle' }}}}" style="margin-right:10px;"></i>
                                <div>{{{{ message }}}}</div>
                            </div>
                        {{% endfor %}}
                    {{% endif %}}
                {{% endwith %}}

                {content_html}

                <div class="footer-section">
                    <div class="row align-items-center">
                        <div class="col-8">
                            <div class="d-flex gap-2 text-muted small mb-2 flex-wrap">
                                <a href="https://www.easymedicalink.com" target="_blank" class="footer-link">Site Officiel</a> | 
                                <a href="#" data-bs-toggle="modal" data-bs-target="#privacyModal" class="footer-link">Confidentialité</a> |
                                <a href="#" data-bs-toggle="modal" data-bs-target="#supportModal" class="footer-link">Support</a>
                            </div>
                        </div>
                        <div class="col-4 text-end qr-code-box">
                            <img src="https://api.qrserver.com/v1/create-qr-code/?size=70x70&color=0083B0&data=https://www.easymedicalink.com" alt="QR" width="60" height="60">
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="supportModal" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content border-0 shadow">
          <div class="modal-header">
            <h5 class="modal-title"><i class="fas fa-headset me-2"></i>Service Support</h5>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-center py-4">
            <p><a href="mailto:sastoukadigital@gmail.com" class="text-decoration-none text-primary-custom fw-bold">sastoukadigital@gmail.com</a></p>
            <p><a href="https://wa.me/212652084735" target="_blank" class="btn btn-success rounded-pill px-4"><i class="fab fa-whatsapp me-2"></i>+212 652 084 735</a></p>
          </div>
        </div>
      </div>
    </div>

    <div class="modal fade" id="privacyModal" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered modal-lg">
        <div class="modal-content border-0 shadow">
          <div class="modal-header">
            <h5 class="modal-title"><i class="fas fa-lock me-2"></i>Confidentialité & Données Locales</h5>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-secondary" style="max-height: 60vh; overflow-y: auto;">
            <h6 class="fw-bold text-dark"><i class="fas fa-hdd me-2"></i>1. Architecture 100% Locale</h6>
            <p>Cette application fonctionne exclusivement en local sur votre machine ou votre réseau interne. <strong>Aucune donnée</strong> n'est transmise via internet vers des serveurs externes ou cloud.</p>

            <h6 class="fw-bold text-dark mt-3"><i class="fas fa-user-shield me-2"></i>2. Pas de Collecte de Données</h6>
            <p>EasyMedicalink ne collecte, ne stocke et n'analyse aucune de vos informations. Nous n'avons aucun accès à vos dossiers patients, votre chiffre d'affaires ou vos statistiques.</p>

            <h6 class="fw-bold text-dark mt-3"><i class="fas fa-database me-2"></i>3. Souveraineté Totale</h6>
            <p>Vos données sont stockées physiquement sur votre ordinateur (Dossier MEDICALINK_DATA). Vous en êtes le seul propriétaire et le seul responsable. Pensez à effectuer des sauvegardes régulières.</p>
            
            <hr>
            <p class="small text-muted mb-0">Dernière mise à jour : {current_date_str}.</p>
          </div>
          <div class="modal-footer border-0 bg-light">
            <button type="button" class="btn btn-primary-custom px-4" data-bs-dismiss="modal">J'ai compris</button>
          </div>
        </div>
      </div>
    </div>

    {js_scripts}
    </body>
    </html>
    """

# ──────────────────────────────────────────────────────────────────────────────
# Routes Flask (LOGIQUE CONSERVÉE, MAIS APPEL DES NOUVEAUX TEMPLATES)
# ──────────────────────────────────────────────────────────────────────────────

@login_bp.route("/login", methods=["GET", "POST"])
def login():
    _set_login_paths()
    if request.method == "POST":
        email = request.form["email"].lower().strip()
        pwd_hash = hash_password(request.form["password"])
        selected_role = request.form.get("role_select")

        found_user_info = _find_user_in_centralized_users_file(email, pwd_hash)

        if found_user_info:
            actual_role = found_user_info["actual_role"]
            is_pharmacy_role_match = (selected_role == 'pharmacie/magasin' and actual_role == 'pharmacie')

            if selected_role != actual_role and not is_pharmacy_role_match:
                flash("Rôle incorrect pour cet utilisateur.", "danger")
                return redirect(url_for('login.login'))

            if not found_user_info["user_data"].get("active", True):
                flash("Compte inactif. Contactez l'administrateur.", "danger")
                return redirect(url_for("activation.activation"))

            session["email"] = email
            session["role"] = actual_role
            session["admin_email"] = found_user_info["admin_owner_email"]
            session["user_nom"] = found_user_info["user_data"].get("nom", "")
            session["user_prenom"] = found_user_info["user_data"].get("prenom", "")
            session.permanent = True

            if actual_role == "admin" and email == found_user_info["admin_owner_email"]:
                utils.set_dynamic_base_dir(found_user_info["admin_owner_email"])
                config = utils.load_config()
                admin_data = found_user_info["user_data"]
                needs_save = False
                if not config.get('nom_clinique'):
                    config['nom_clinique'] = admin_data.get('clinic', '')
                    needs_save = True
                if not config.get('doctor_name'):
                    config['doctor_name'] = f"{admin_data.get('prenom','')} {admin_data.get('nom','')}".strip()
                    needs_save = True
                if needs_save:
                    try: utils.save_config(config)
                    except: pass

            return redirect(url_for("accueil.accueil"))

        flash("Email ou mot de passe incorrect.", "danger")

    # Contenu spécifique du formulaire Login
    login_form = """
    <h2 class="text-center">Connexion</h2>
    <p class="subtitle text-center">Accédez à votre espace sécurisé</p>
    <form method="POST">
        <div class="mb-3">
            <div class="form-floating">
                <select name='role_select' class='form-select' id="roleSelect" style="padding-top: 1.625rem;">
                  <option value='admin'>Administrateur</option>
                  <option value='medecin'>Médecin</option>
                  <option value='assistante'>Assistante</option>
                  <option value='comptable'>Comptable</option>
                  <option value='biologiste'>Biologiste</option>
                  <option value='radiologue'>Radiologue</option>
                  <option value='pharmacie/magasin'>Pharmacie & Stock</option>
                </select>
                <label for="roleSelect">Profil Utilisateur</label>
            </div>
        </div>
        <div class="form-floating mb-3">
            <input name='email' type='email' class='form-control' id="email" placeholder="Email" required>
            <label for="email">Adresse Email</label>
        </div>
        <div class="form-floating mb-3 position-relative">
            <input name='password' type='password' class='form-control' id="password" placeholder="Mot de passe" required>
            <label for="password">Mot de passe</label>
            <i class="fas fa-eye password-toggle" onclick="togglePassword('password')"></i>
        </div>
        
        <div class="d-flex justify-content-between align-items-center mb-3">
             <div class="form-check">
                <input class="form-check-input" type="checkbox" id="remember">
                <label class="form-check-label small" for="remember">Se souvenir</label>
            </div>
            <a href="{{ url_for('login.forgot_password') }}" class="small text-decoration-none">Mot de passe oublié ?</a>
        </div>

        <button type="submit" class="btn btn-primary-custom">
            Se connecter <i class="fas fa-arrow-right ms-2"></i>
        </button>
    </form>
    <div class="links">
        Nouveau cabinet ? <a href="{{ url_for('login.register') }}" class="fw-bold">Créer un compte Admin</a>
    </div>
    """
    return render_template_string(render_auth_page(login_form))

@login_bp.route("/register", methods=["GET", "POST"])
def register():
    _set_login_paths()
    if request.method == "POST":
        f = request.form
        email = f["email"].lower().strip()
        phone = f["phone"].strip()
        nom = f.get("nom", "").strip()
        prenom = f.get("prenom", "").strip()
        pwd = f["password"]
        confirm = f["confirm"]

        if not _is_email_globally_unique(email):
            flash(f"L'adresse e-mail '{email}' est déjà utilisée.", "danger")
            return redirect(url_for('login.register'))

        if pwd != confirm:
            flash("Les mots de passe ne correspondent pas.", "danger")
            return redirect(url_for('login.register'))

        if not nom or not prenom:
             flash("Nom et prénom requis.", "danger")
             return redirect(url_for('login.register'))

        users = load_users()
        users[email] = {
            "password": hash_password(pwd),
            "role": "admin",
            "nom": nom,
            "prenom": prenom,
            "clinic": f["clinic"],
            "clinic_creation_date": f["clinic_creation_date"],
            "account_creation_date": date.today().isoformat(),
            "address": f["address"],
            "phone": phone,
            "active": True,
            "owner": email,
            "allowed_pages": ALL_BLUEPRINTS,
            "account_limits": {"global_max_users": 3, "current_users": 0},
            "activation": {"plan": f"essai_{TRIAL_DAYS}jours", "activation_date": date.today().isoformat(), "activation_code": "0000-0000-0000-0000"}
        }
        
        save_users(users)
        flash("Compte créé avec succès ! Connectez-vous.", "success")
        return redirect(url_for('login.login'))

    # Formulaire d'inscription PRO (avec tous vos champs spécifiques)
    register_form = """
    <h2 class="text-center">Configuration Initiale</h2>
    <p class="subtitle text-center">Créez votre compte administrateur</p>
    <form method="POST">
        <div class="row g-2 mb-2">
            <div class="col-6 form-floating">
                <input type="text" name="nom" class="form-control" id="nom" placeholder="Nom" required>
                <label for="nom">Nom</label>
            </div>
            <div class="col-6 form-floating">
                <input type="text" name="prenom" class="form-control" id="prenom" placeholder="Prénom" required>
                <label for="prenom">Prénom</label>
            </div>
        </div>
        
        <div class="row g-2 mb-2">
            <div class="col-7 form-floating">
                <input type="email" name="email" class="form-control" id="email" placeholder="Email" required>
                <label for="email">Email Pro</label>
            </div>
             <div class="col-5 form-floating">
                <input type="tel" name="phone" class="form-control" id="phone" placeholder="Tél" required>
                <label for="phone">Tél</label>
            </div>
        </div>

        <div class="form-floating mb-2">
            <input type="text" name="clinic" class="form-control" id="clinic" placeholder="Structure" required>
            <label for="clinic">Nom de la Clinique/Cabinet</label>
        </div>
        
        <div class="row g-2 mb-2">
            <div class="col-6 form-floating">
                 <input type="date" name="clinic_creation_date" class="form-control" id="date" required>
                 <label for="date">Date Création</label>
            </div>
             <div class="col-6 form-floating">
                 <input type="text" name="address" class="form-control" id="addr" placeholder="Ville" required>
                 <label for="addr">Adresse/Ville</label>
            </div>
        </div>

        <div class="row g-2 mb-3">
            <div class="col-6 form-floating position-relative">
                <input type="password" name="password" class="form-control" id="pwd" placeholder="Mdp" required>
                <label for="pwd">Mot de passe</label>
            </div>
            <div class="col-6 form-floating">
                <input type="password" name="confirm" class="form-control" id="conf" placeholder="Conf" required>
                <label for="conf">Confirmer</label>
            </div>
        </div>
        
        <button type="submit" class="btn btn-primary-custom">
            Valider <i class="fas fa-check-circle ms-2"></i>
        </button>
    </form>
    <div class="links">
        Déjà un compte ? <a href="{{ url_for('login.login') }}">Se connecter</a>
    </div>
    """
    return render_template_string(render_auth_page(register_form, "Création Compte"))

@login_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    _set_login_paths()
    if 'email' not in session:
        flash('Vous devez être connecté pour changer votre mot de passe.', 'warning')
        return redirect(url_for('login.login'))

    if request.method == 'POST':
        pwd = request.form.get('password')
        confirm = request.form.get('confirm')
        
        if pwd != confirm:
            flash('Les mots de passe ne correspondent pas.', 'warning')
        else:
            users = load_users()
            email = session['email']
            if email in users:
                users[email]['password'] = hash_password(pwd)
                save_users(users)
                flash('Mot de passe mis à jour avec succès.', 'success')
                return redirect(url_for('accueil.accueil'))
            else:
                flash('Utilisateur introuvable.', 'danger')
    
    # Formulaire Changement MP (Version simple interne)
    content = """
    <h2 class="text-center">Sécurité</h2>
    <p class="subtitle text-center">Changez votre mot de passe</p>
    <form method="POST">
        <div class="form-floating mb-3">
             <input type="password" name="password" class="form-control" id="pwd" placeholder="Nouveau" required>
             <label for="pwd">Nouveau mot de passe</label>
        </div>
        <div class="form-floating mb-3">
             <input type="password" name="confirm" class="form-control" id="conf" placeholder="Confirmer" required>
             <label for="conf">Confirmer le mot de passe</label>
        </div>
        <button type="submit" class="btn btn-primary-custom">Mettre à jour</button>
    </form>
    <div class="links"><a href="{{ url_for('accueil.accueil') }}">Annuler</a></div>
    """
    return render_template_string(render_auth_page(content, "Changer mot de passe", show_visual=False))

@login_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    _set_login_paths()
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        users = load_users()
        
        if email in users:
            token = generate_reset_token()
            users[email]['reset_token'] = token
            users[email]['reset_expiry'] = (datetime.now() + timedelta(hours=1)).isoformat()
            save_users(users)
            
            try:
                mail = current_app.extensions.get('mail')
                if not mail:
                    # FALLBACK LOCAL POUR TEST SI MAIL NON CONFIGURÉ
                    print(f"DEBUG: Token reset pour {email} : {token}")
                    flash("Service Mail non actif (Mode Dev). Token affiché en console serveur.", "warning")
                    return redirect(url_for('login.login'))

                reset_link = url_for('login.reset_password_token', token=token, _external=True)
                
                msg = Message(
                    subject="Réinitialisation de mot de passe - EasyMedicalink",
                    sender=current_app.config.get('MAIL_USERNAME'),
                    recipients=[email]
                )
                msg.body = f"""Bonjour,\n\nCliquez sur ce lien pour réinitialiser : {reset_link}\n\nCordialement."""
                mail.send(msg)
                flash("E-mail envoyé. Vérifiez votre boîte de réception.", "success")
                return redirect(url_for('login.login'))
            
            except Exception as e:
                print(f"Erreur d'envoi d'email: {e}")
                flash(f"Erreur technique: {e}", "danger")
        else:
            flash("Si cet email existe, un lien a été envoyé.", "info")
            return redirect(url_for('login.login'))

    content = """
    <div class="text-center mb-4">
         <div class="bg-light rounded-circle mx-auto d-flex align-items-center justify-content-center" style="width:70px; height:70px;">
            <i class="fas fa-key fa-2x text-primary-custom"></i>
         </div>
    </div>
    <h2 class="text-center">Récupération</h2>
    <p class="subtitle text-center">Entrez votre email pour recevoir le lien</p>
    <form method="POST">
        <div class="form-floating mb-3">
            <input type="email" name="email" class="form-control" id="email" placeholder="Email" required>
            <label for="email">Email</label>
        </div>
        <button type="submit" class="btn btn-primary-custom">Envoyer</button>
    </form>
    <div class="links"><a href="{{ url_for('login.login') }}">Retour</a></div>
    """
    return render_template_string(render_auth_page(content, "Récupération"))

@login_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password_token(token):
    _set_login_paths()
    users = load_users()
    user_email = None
    
    for email, data in users.items():
        if data.get('reset_token') == token:
            expiry = data.get('reset_expiry')
            if expiry:
                if datetime.fromisoformat(expiry) > datetime.now():
                    user_email = email
                else:
                    flash("Lien expiré.", "warning")
                    return redirect(url_for('login.forgot_password'))
            break
    
    if not user_email:
        flash("Lien invalide.", "danger")
        return redirect(url_for('login.login'))

    if request.method == 'POST':
        pwd = request.form.get('password')
        confirm = request.form.get('confirm')
        
        if pwd != confirm:
            flash("Les mots de passe ne correspondent pas.", "danger")
        elif not pwd:
            flash("Mot de passe vide interdit.", "danger")
        else:
            users[user_email]['password'] = hash_password(pwd)
            users[user_email].pop('reset_token', None)
            users[user_email].pop('reset_expiry', None)
            save_users(users)
            
            flash("Mot de passe modifié. Connectez-vous.", "success")
            return redirect(url_for('login.login'))

    content = """
    <h2 class="text-center">Nouveau Mot de Passe</h2>
    <form method="POST">
        <div class="form-floating mb-3">
             <input type="password" name="password" class="form-control" id="p" placeholder="New" required>
             <label for="p">Nouveau mot de passe</label>
        </div>
        <div class="form-floating mb-3">
             <input type="password" name="confirm" class="form-control" id="c" placeholder="Conf" required>
             <label for="c">Confirmer</label>
        </div>
        <button type="submit" class="btn btn-primary-custom">Valider</button>
    </form>
    """
    return render_template_string(render_auth_page(content, "Reset Password"))

@login_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login.login'))