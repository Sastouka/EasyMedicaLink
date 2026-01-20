# activation.py – gestion licences & activation (TARIFS MIS À JOUR EURO)
from __future__ import annotations
import os, json, uuid, hashlib, socket, requests, calendar
from datetime import date, timedelta
from typing import Optional, Dict
from flask import (
    request, render_template_string, redirect, url_for,
    flash, session, Blueprint, current_app
)

# ─────────────────────────────────────────────────────────────
# 1. Imports internes
# ─────────────────────────────────────────────────────────────
import theme, utils
import login

# ─────────────────────────────────────────────────────────────
# 2. Configuration
# ─────────────────────────────────────────────────────────────
TRIAL_DAYS  = 7
SECRET_SALT = "S2!eUrltaMnSecet25lrao" # Le sel reste une composante de la sécurité

# ─────────────────────────────────────────────────────────────
# 3. Générateur de clé
# ─────────────────────────────────────────────────────────────
def _week_of_month(d: date) -> int:
    return ((d.day + calendar.monthrange(d.year, d.month)[0] - 1) // 7) + 1

# NOTE: Cette fonction est conservée pour la compatibilité externe.
def get_hardware_id() -> str:
    return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()[:16]

def generate_activation_key_for_user(
    admin_email: str, plan: str, ref: Optional[date] = None
) -> str:
    """
    Génère une clé d'activation basée UNIQUEMENT sur l'e-mail de l'admin et la date.
    """
    ref = ref or date.today()
    plan_lower = plan.lower().strip()
    date_component = ""

    # L'email remplace l'ID machine dans le payload
    email_component = hashlib.sha256(admin_email.encode()).hexdigest()[:8]

    if plan_lower.startswith("essai"):
        date_component = ref.strftime("%m%Y") + str(_week_of_month(ref))
    elif "1_mois" in plan_lower:
        date_component = ref.strftime("%d%m%Y")
    elif "1_an" in plan_lower:
        date_component = ref.strftime("%Y")
    elif "illimite" in plan_lower:
        date_component = ""

    payload = f"{email_component}{SECRET_SALT}{plan_lower}{date_component}"
    digest  = hashlib.sha256(payload.encode()).hexdigest().upper()[:16]
    return "-".join(digest[i:i+4] for i in range(0, 16, 4))

# ─────────────────────────────────────────────────────────────
# 4. Accès users.json
# ─────────────────────────────────────────────────────────────
def _user() -> Optional[dict]:
    email = session.get("email")
    if not email:
        return None
    return login._user() if hasattr(login, '_user') else login.load_users().get(email)


def _save_user(u: dict):
    email = session.get("email")
    if not email:
        return
    users = login.load_users()
    users[email] = u
    login.save_users(users)
        
def _ensure_placeholder(u: dict):
    if "activation" not in u:
        u["activation"] = {
            "plan": f"essai_{TRIAL_DAYS}jours",
            "activation_date": date.today().isoformat(),
            "activation_code": "0000-0000-0000-0000"
        }
        _save_user(u)
        
# ─────────────────────────────────────────────────────────────
# 5. Validation licences
# ─────────────────────────────────────────────────────────────
def _add_month(d: date) -> date:
    nxt_mo = d.month % 12 + 1
    nxt_yr = d.year + d.month // 12
    try:
        return d.replace(year=nxt_yr, month=nxt_mo)
    except ValueError:
        return (d.replace(day=1, year=nxt_yr, month=nxt_mo) - timedelta(days=1))

def check_activation() -> bool:
    u = _user()
    if not u:
        return False

    # Tous les comptes dépendent de la licence de l'administrateur
    admin_owner_email = u.get("owner", u.get("email"))
    
    all_users = login.load_users()
    admin_owner_user = all_users.get(admin_owner_email)

    if not admin_owner_user or "activation" not in admin_owner_user:
        return False
    
    admin_act = admin_owner_user["activation"]
    
    def _check_admin_activation_record(admin_email: str, activation_record: Dict) -> bool:
        plan = activation_record["plan"].lower()
        act_date = date.fromisoformat(activation_record["activation_date"])
        today = date.today()
        current_code = activation_record.get("activation_code")
        
        if plan.startswith("essai") and current_code == "0000-0000-0000-0000":
            return today <= act_date + timedelta(days=TRIAL_DAYS)
        
        # GÉNÉRATION DE LA CLÉ ATTENDUE (AVEC EMAIL ADMIN)
        exp_code = generate_activation_key_for_user(admin_email, plan, act_date)
        
        if current_code != exp_code:
            return False

        if plan.startswith("essai"):
            return today <= act_date + timedelta(days=TRIAL_DAYS)
        if "1_mois" in plan:
            return today <= _add_month(act_date)
        if "1_an" in plan:
            try:
                lim = act_date.replace(year=act_date.year + 1)
            except ValueError:
                lim = act_date + timedelta(days=365)
            return today <= lim
        if "illimite" in plan:
            return True
        return False

    if u.get("role") == "admin":
        _ensure_placeholder(u)

    return _check_admin_activation_record(admin_owner_email, admin_act)


def update_activation(plan: str, code: str):
    u = _user()
    if not u: return
    # Mise à jour sur l'enregistrement de l'admin
    admin_email = u.get("owner", u.get("email"))
    
    users = login.load_users()
    admin_user = users.get(admin_email)
    
    if admin_user:
        admin_user["activation"] = {
            "plan": plan,
            "activation_date": date.today().isoformat(),
            "activation_code": code
        }
        login.save_users(users)

update_activation_after_payment = update_activation

# ──────────────────────────
# 6. PayPal (MISE A JOUR DEVISE EUR)
# ──────────────────────────
PAYPAL_CLIENT_ID  = os.environ.get("PAYPAL_CLIENT_ID") or "AYPizBBNq1vp8WyvzvTHITGq9KoUUTXmzE0DBA7D_lWl5Ir6wEwVCB-gorvd1jgyX35ZqyURK6SMvps5"
PAYPAL_SECRET     = os.environ.get("PAYPAL_SECRET")    or "EKSvwa_yK7ZYTuq45VP60dbRMzChbrko90EnhQsRzrMNZhqU2mHLti4_UTYV60ytY9uVZiAg7BoBlNno"
PAYPAL_OAUTH_URL  = "https://api-m.paypal.com/v1/oauth2/token"
PAYPAL_ORDER_API  = "https://api-m.paypal.com/v2/checkout/orders"

def get_paypal_access_token() -> str:
    r = requests.post(PAYPAL_OAUTH_URL,
        auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
        data={"grant_type":"client_credentials"})
    if r.ok: return r.json()["access_token"]
    raise RuntimeError(r.text)

def create_paypal_order(amount, return_url, cancel_url):
    token = get_paypal_access_token()
    hdr   = {"Authorization":f"Bearer {token}", "Content-Type":"application/json"}
    # MODIFICATION ICI : currency_code passé à "EUR"
    body  = {
        "intent":"CAPTURE",
        "purchase_units":[{"amount":{"currency_code":"EUR","value":amount}}],
        "application_context":{"return_url":return_url,"cancel_url":cancel_url}
    }
    r = requests.post(PAYPAL_ORDER_API, json=body, headers=hdr)
    if r.ok:
        j = r.json()
        return j["id"], next(l["href"] for l in j["links"] if l["rel"]=="approve")
    raise RuntimeError(r.text)

def capture_paypal_order(oid):
    token = get_paypal_access_token()
    r = requests.post(f"{PAYPAL_ORDER_API}/{oid}/capture",
        headers={"Authorization":f"Bearer {token}"})
    return r.ok and r.json().get("status") == "COMPLETED"

# ─────────────────────────────────────────────────────────────
# 7. Templates (HTML condensé - PRIX MIS A JOUR)
# ─────────────────────────────────────────────────────────────

activation_template = """
<!DOCTYPE html><html lang='fr'>
{{ pwa_head()|safe }}
<head>
<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Activation EasyMedicalink</title>
<link rel='preconnect' href='https://fonts.googleapis.com'>
<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>
<link href='https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap' rel='stylesheet'>
<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>
<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'>
<style>
:root {
    --gradient-start: #667eea;
    --gradient-end: #764ba2;
    --web-start: #007bff;
    --web-end: #00d4ff;
    --local-start: #28a745;
    --local-end: #20c997;
    --popular-bg: #ffc107;
}
body{
    background: linear-gradient(135deg, var(--gradient-start) 0%, var(--gradient-end) 100%);
    font-family: 'Poppins', sans-serif;
    color: #495057;
}
.container{max-width:960px; padding-top:2rem; padding-bottom: 2rem;}
.main-card{
    background-color: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
}
.plan-card {
    border-radius: 15px;
    transition: all .3s ease;
    border: none;
    box-shadow: 0 4px 15px rgba(0,0,0,.1);
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
}
.plan-card:hover{
    transform: translateY(-10px);
    box-shadow: 0 10px 25px rgba(0,0,0,.15);
}
.plan-card .card-header{
    border-top-left-radius: 15px;
    border-top-right-radius: 15px;
    font-weight: 700;
    color: white;
    padding: 1.25rem 1rem;
}
.header-web { background: linear-gradient(45deg, var(--web-start), var(--web-end)); }
.header-local { background: linear-gradient(45deg, var(--local-start), var(--local-end)); }
.btn-plan {
    font-weight: 600;
    padding: 0.75rem 1rem;
    border-radius: 50px;
    border: none;
    transition: all .3s ease;
    color: white;
}
.btn-web { background-image: linear-gradient(to right, var(--web-start) 0%, var(--web-end) 51%, var(--web-start) 100%); background-size: 200% auto; }
.btn-local { background-image: linear-gradient(to right, var(--local-start) 0%, var(--local-end) 51%, var(--local-start) 100%); background-size: 200% auto; }
.btn-plan:hover { background-position: right center; }
.badge-popular {
    position: absolute;
    top: 18px;
    right: -30px;
    transform: rotate(45deg);
    background-color: var(--popular-bg);
    color: #212529;
    font-weight: bold;
    padding: 2px 30px;
    font-size: 0.8rem;
}
.mono {font-family: 'Courier New', Courier, monospace; background-color: #e9ecef; padding: .2em .4em; border-radius: .3em;}
.list-unstyled .fa-stack { font-size: 0.9em; } 
.activation-steps .step-number {
    background-image: linear-gradient(135deg, var(--gradient-start) 0%, var(--gradient-end) 100%);
}
</style>
</head><body><div class='container'>
<div class='main-card p-4 p-md-5'>
  <div class='text-center mb-5'>
    <h1 class='card-title fw-bold' style="color: var(--gradient-start);"><i class='fas fa-rocket'></i> Activez Votre Licence</h1>
    <p class='fs-5 text-muted'>Rejoignez-nous et simplifiez votre gestion dès aujourd'hui.</p>
  </div>
  
  {% with m = get_flashed_messages(with_categories=true) %}
    {% for c,msg in m %}<div class='alert alert-{{c}}'>{{msg}}</div>{% endfor %}
  {% endwith %}

  <form method='POST'>
    <div class='mb-4 p-3 bg-light rounded border text-center'>
      <label class='form-label fw-bold'><i class='fas fa-envelope'></i> E-mail de Licence Administrateur</label>
      <div class='fs-5 mono'>{{ admin_owner_email }}</div>
      <p class="small text-danger mt-2">Attention: L'activation est liée uniquement à cet e-mail.</p>
    </div>
    
    <div class="mb-4 text-center">
        <label for="activation_code" class='form-label fw-bold'>Déjà une clé d'activation ?</label>
        <input name='activation_code' id='activation_code' class='form-control form-control-lg mono text-center mx-auto' style="max-width:350px;" placeholder='XXXX-XXXX-XXXX-XXXX'>
        <div class="form-text mt-2">Entrez votre clé et cliquez sur le bouton du plan correspondant pour activer.</div>
    </div>

    <hr class="my-4">

    <input type='hidden' name='choix' id='planField'>
    <div class='row g-4'>
      <div class='col-lg-6 mb-4 mb-lg-0'>
        <div class='plan-card h-100'>
          <div class='card-header text-center fs-4 header-web'><i class="fas fa-globe me-2"></i>Version Web</div>
          <div class='card-body d-flex flex-column p-4'>
            <p class='text-center'>Accès universel depuis n'importe quel navigateur. Idéal pour la mobilité.</p>
            <div class='text-center my-3'>
                <span class="fs-1 fw-bold">50 €</span>
                <span class="text-muted">/ mois</span>
            </div>
            <button type='submit' class='btn btn-plan btn-web' onclick="setPlan('web_1_mois')">Choisir ce plan</button>
            <hr>
             <div class='text-center my-3'>
                <span class="fs-1 fw-bold">500 €</span>
                <span class="text-muted">/ an</span>
            </div>
            <button type='submit' class='btn btn-plan btn-web' onclick="setPlan('web_1_an')">Abonnement Annuel</button>
            <div class="badge-popular">Économie</div>
          </div>
        </div>
      </div>

      <div class='col-lg-6'>
        <div class='plan-card h-100'>
          <div class='card-header text-center fs-4 header-local'><i class="fab fa-windows me-2"></i>Version Locale</div>
          <div class='card-body d-flex flex-column p-4'>
            <p class='text-center'>Performance maximale sur votre PC Windows, même hors ligne.</p>
            <div class='text-center my-3'>
                <span class="fs-1 fw-bold">50 €</span>
                <span class="text-muted">/ an</span>
            </div>
            <button type='submit' class='btn btn-plan btn-local' onclick="setPlan('local_1_an')">Licence 1 An</button>
            <hr>
            <div class='text-center my-3'>
                <span class="fs-1 fw-bold">120 €</span>
                <span class="text-muted">/ à vie</span>
            </div>
            <button type='submit' class='btn btn-plan btn-local' onclick="setPlan('local_illimite')">Licence Illimitée</button>
            <div class="badge-popular">-    Meilleur Choix</div>
          </div>
        </div>
      </div>
    </div>
  </form>
  
  <hr class="my-5">

  <div class="px-lg-5">
    <h2 class='text-center fw-bold mb-4' style="color: var(--gradient-start);"><i class="fas fa-question-circle"></i> Comment ça marche ?</h2>
    <div class="row g-4">
      <div class="col-md-6">
          <h4 class="text-center mb-3 header-web text-white p-2 rounded-pill"><i class="fas fa-globe me-2"></i>Pour la Version Web</h4>
          <ul class="list-unstyled">
              <li class="d-flex align-items-center mb-3"><span class="fa-stack fa-lg me-3"><i class="fas fa-circle fa-stack-2x" style="color:var(--web-start);"></i><strong class="fa-stack-1x fa-inverse">1</strong></span> <p class="mb-0">Choisissez votre plan (1 Mois ou 1 An) et cliquez sur le bouton correspondant pour payer via PayPal.</p></li>
              <li class="d-flex align-items-center mb-3"><span class="fa-stack fa-lg me-3"><i class="fas fa-circle fa-stack-2x" style="color:var(--web-start);"></i><strong class="fa-stack-1x fa-inverse">2</strong></span> <p class="mb-0">Une fois le paiement effectué, votre licence est <strong>instantanément activée</strong>.</p></li>
              <li class="d-flex align-items-center"><span class="fa-stack fa-lg me-3"><i class="fas fa-circle fa-stack-2x" style="color:var(--web-start);"></i><strong class="fa-stack-1x fa-inverse">3</strong></span> <p class="mb-0">Vous pouvez vous connecter et utiliser l'application depuis <strong>n'importe quel navigateur</strong> (PC, Mac, tablette...).</p></li>
          </ul>
      </div>
      <div class="col-md-6">
           <h4 class="text-center mb-3 header-local text-white p-2 rounded-pill"><i class="fab fa-windows me-2"></i>Pour la Version Locale</h4>
           <ul class="list-unstyled">
              <li class="d-flex align-items-center mb-3"><span class="fa-stack fa-lg me-3"><i class="fas fa-circle fa-stack-2x" style="color:var(--local-start);"></i><strong class="fa-stack-1x fa-inverse">1</strong></span> <p class="mb-0"><strong>Téléchargez l'exécutable</strong> (64-bit ou 32-bit) depuis les liens ci-dessous et installez-le.</p></li>
              <li class="d-flex align-items-center mb-3"><span class="fa-stack fa-lg me-3"><i class="fas fa-circle fa-stack-2x" style="color:var(--local-start);"></i><strong class="fa-stack-1x fa-inverse">2</strong></span> <p class="mb-0">Lancez l'application. Elle vous amènera sur cette page pour activer votre licence <strong>liée à l'e-mail de l'administrateur</strong>.</p></li>
              <li class="d-flex align-items-center"><span class="fa-stack fa-lg me-3"><i class="fas fa-circle fa-stack-2x" style="color:var(--local-start);"></i><strong class="fa-stack-1x fa-inverse">3</strong></span> <p class="mb-0">Choisissez votre licence (1 An ou Illimitée), payez, et l'application sera <strong>débloquée sur le compte admin</strong>.</p></li>
          </ul>
      </div>
    </div>
  </div>

  <div class="text-center mt-5 p-4 rounded-3" style="background-color: #e3f2fd;">
      <h3 class="fw-bold mb-3" style="color: var(--local-start);"><i class="fab fa-windows"></i> Téléchargement Version Locale</h3>
      <p class="mb-4 text-muted">Pour une expérience optimale sur votre ordinateur, téléchargez la version compatible avec votre système.</p>
      <div class="d-grid gap-3 d-sm-flex justify-content-sm-center">
          {% if win64_filename %}
            <a href="{{ url_for('static', filename=win64_filename) }}" class='btn btn-lg btn-success'><i class='fas fa-download me-2'></i> Windows 64-bit</a>
          {% endif %}
          {% if win32_filename %}
            <a href="{{ url_for('static', filename=win32_filename) }}" class='btn btn-lg btn-secondary'><i class='fas fa-download me-2'></i> Windows 32-bit</a>
          {% endif %}
      </div>
  </div>

  <div class='mt-4 pt-4 border-top text-center'>
    <p class='text-muted small'>Pour toute question, contactez le support technique.</p>
    <div>
        <a href="{{ url_for('login.login') }}" class='btn btn-outline-primary btn-sm'><i class='fas fa-arrow-left me-1'></i> Retour à la connexion</a>
        <a href='mailto:sastoukadigital@gmail.com' class='btn btn-outline-secondary btn-sm'><i class='fas fa-envelope me-1'></i> Email</a>
        <a href='https://wa.me/212652084735' class='btn btn-outline-success btn-sm' target='_blank'><i class='fab fa-whatsapp me-1'></i> WhatsApp</a>
    </div>
  </div>

</div></div>
<script>
function setPlan(p){document.getElementById('planField').value=p;}
</script>
{% include '_floating_assistant.html' %}
</body></html>"""

failed_activation_template = """<html>
{{ pwa_head()|safe }}
<head><meta http-equiv='refresh' content='5;url={{ url_for("activation.activation") }}'>
<title>Échec</title><link rel='stylesheet'
href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'></head>
<body class='vh-100 d-flex align-items-center justify-content-center'>
<div class='alert alert-danger text-center'>Activation invalide – contactez le support.</div></body></html>"""

activation_bp = Blueprint("activation", __name__)

# ─────────────────────────────────────────────────────────────
# 8. Routes
# ─────────────────────────────────────────────────────────────
orders: Dict[str, tuple[str,str]] = {}

@activation_bp.route("/", methods=["GET","POST"])
def activation():
    login._set_login_paths()

    if "email" not in session:
        flash("Veuillez vous connecter pour accéder à la page d'activation.", "danger")
        return redirect(url_for("login.login"))

    if check_activation():
        return redirect(url_for("accueil.accueil"))

    user = login._user()
    admin_owner_email = user.get("owner", user.get("email", ""))
    
    if admin_owner_email != session.get('admin_email'):
        flash("Seul le compte administrateur principal peut gérer l'activation ici.", "danger")
        return redirect(url_for("accueil.accueil"))

    hwid, today = get_hardware_id(), date.today()
    
    static_folder = current_app.static_folder
    contents = os.listdir(static_folder) if os.path.exists(static_folder) else []
    win64 = next((f for f in contents if f.startswith('EasyMedicaLink-Win64.exe')), None)
    win32 = next((f for f in contents if f.startswith('EasyMedicaLink-Win32.exe')), None)

    ctx = dict(machine_id=hwid,
               admin_owner_email=admin_owner_email,
               week_rank=_week_of_month(today),
               month_year=today.strftime("%m/%Y"),
               TRIAL_DAYS=TRIAL_DAYS,
               win64_filename=win64,
               win32_filename=win32)

    if request.method == "POST":
        plan = request.form["choix"]
        code = request.form.get("activation_code","").strip().upper()
        
        # --- NOUVEAUX TARIFS EN EUROS ---
        tariffs = {
            "web_1_mois": "50.00",
            "web_1_an": "500.00",
            "local_1_an": "50.00",
            "local_illimite": "120.00",
        }

        if plan in tariffs:
            # Vérification de la clé manuelle
            expected_paid_code = generate_activation_key_for_user(admin_owner_email, plan, today)
            
            if code and code == expected_paid_code:
                update_activation(plan, code)
                flash("Plan activé avec succès par clé !","success")
                return redirect(url_for("accueil.accueil"))

            # Sinon, on lance le paiement PayPal
            try:
                oid, url = create_paypal_order(
                    tariffs[plan],
                    return_url=url_for("activation.paypal_success", _external=True),
                    cancel_url=url_for("activation.paypal_cancel",  _external=True)
                )
                orders[oid] = (plan, expected_paid_code)
                return redirect(url)
            except Exception as e:
                flash(f"Erreur de communication avec PayPal : {e}","danger")
        else:
            flash("Veuillez sélectionner un plan valide.", "danger")

    return render_template_string(activation_template, **ctx)

@activation_bp.route("/paypal_success")
def paypal_success():
    login._set_login_paths()
    oid = request.args.get("token")
    if oid and oid in orders and capture_paypal_order(oid):
        plan, code = orders.pop(oid)
        update_activation(plan, code)
        flash("Paiement validé – votre licence est maintenant activée !","success")
        return redirect(url_for("accueil.accueil"))
    return render_template_string(failed_activation_template)

@activation_bp.route("/paypal_cancel")
def paypal_cancel():
    login._set_login_paths()
    flash("Le paiement a été annulé. Vous pouvez réessayer.","warning")
    return redirect(url_for("activation.activation"))