# activation.py – gestion licences & activation (VERSION CORRIGÉE)
from __future__ import annotations
import os, json, uuid, hashlib, socket, requests, calendar
from datetime import date, timedelta
from typing import Optional, Dict
from flask import (
    request, render_template_string, redirect, url_for,
    flash, session, Blueprint
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
SECRET_SALT = "S2!eUrltaMnSecet25lrao"

# ─────────────────────────────────────────────────────────────
# 3. Générateur de clé (Logique mise à jour)
# ─────────────────────────────────────────────────────────────
def _week_of_month(d: date) -> int:
    return ((d.day + calendar.monthrange(d.year, d.month)[0] - 1) // 7) + 1

def get_hardware_id() -> str:
    return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()[:16]

def generate_activation_key_for_user(
    hwid: str, plan: str, ref: Optional[date] = None
) -> str:
    """
    Génère une clé d'activation avec une logique qui dépend du plan.
    - Essai: lié à la semaine du mois.
    - 1 mois: lié au jour exact (JJ/MM/AAAA).
    - 1 an: lié à l'année (AAAA).
    - Illimité: indépendant de la date.
    """
    ref = ref or date.today()
    plan_lower = plan.lower().strip()
    date_component = ""

    if plan_lower.startswith("essai"):
        date_component = ref.strftime("%m%Y") + str(_week_of_month(ref))
    elif plan_lower == "1 mois":
        date_component = ref.strftime("%d%m%Y")
    elif plan_lower == "1 an":
        date_component = ref.strftime("%Y")
    elif plan_lower == "illimité":
        date_component = ""

    payload = f"{hwid}{SECRET_SALT}{plan_lower}{date_component}"
    digest  = hashlib.sha256(payload.encode()).hexdigest().upper()[:16]
    return "-".join(digest[i:i+4] for i in range(0, 16, 4))

# ─────────────────────────────────────────────────────────────
# 4. Accès users.json
# ─────────────────────────────────────────────────────────────
def _user() -> Optional[dict]:
    email = session.get("email")
    if not email:
        return None
    return login.load_users().get(email)

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
        return True

    role = u.get("role", "admin").lower()

    def _check_single_activation_record(activation_record: Dict) -> bool:
        plan = activation_record["plan"].lower()
        act_date = date.fromisoformat(activation_record["activation_date"])
        today = date.today()

        if plan.startswith("essai") and activation_record.get("activation_code") == "0000-0000-0000-0000":
            return today <= act_date + timedelta(days=TRIAL_DAYS)
        
        exp_code = generate_activation_key_for_user(get_hardware_id(), plan, act_date)
        if activation_record.get("activation_code") != exp_code:
            return False

        if plan.startswith("essai"):
            return today <= act_date + timedelta(days=TRIAL_DAYS)
        if plan == "1 mois":
            return today <= _add_month(act_date)
        if plan == "1 an":
            try:
                lim = act_date.replace(year=act_date.year + 1)
            except ValueError:
                lim = act_date + timedelta(days=365)
            return today <= lim
        if plan == "illimité":
            return True
        return False

    if role == "admin":
        _ensure_placeholder(u)
        act = u["activation"]
        return _check_single_activation_record(act)

    admin_owner_email = u.get("owner")
    if not admin_owner_email:
        return False
    
    all_users = login.load_users()
    admin_owner_user = all_users.get(admin_owner_email)

    if not admin_owner_user or "activation" not in admin_owner_user:
        return False

    admin_act = admin_owner_user["activation"]
    return _check_single_activation_record(admin_act)


def update_activation(plan: str, code: str):
    u = _user()
    if not u: return
    u["activation"] = {
        "plan": plan,
        "activation_date": date.today().isoformat(),
        "activation_code": code
    }
    _save_user(u)

update_activation_after_payment = update_activation

# ──────────────────────────
# 6. PayPal
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
    body  = {
        "intent":"CAPTURE",
        "purchase_units":[{"amount":{"currency_code":"USD","value":amount}}],
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
# 7. Templates (HTML condensé)
# ─────────────────────────────────────────────────────────────
activation_template = """
<!DOCTYPE html><html lang='fr'>
{{ pwa_head()|safe }}
<head>
<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Activation</title>
<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'>
<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'>
<style>
body{background:#f8f9fa; display: flex; align-items: center; justify-content: center; min-height: 100vh;}
.card{border-radius:1rem;box-shadow:0 4px 20px rgba(0,0,0,.1); width: 100%; max-width: 500px;}
.btn-primary{background:linear-gradient(45deg,#0069d9,#6610f2);border:none}
.contact-info {margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee; text-align: center;}
.contact-info a {margin: 0 10px;}
</style>
</head><body><div class='container'>
<div class='row justify-content-center'><div class='col-md-6'>
<div class='card p-4'><h3 class='card-title text-center mb-3'><i class='fas fa-key'></i> Activation</h3>
<p class='small text-center'>Mois/année : <b>{{ month_year }}</b> • Semaine #<b>{{ week_rank }}</b></p>
<form method='POST'><input type='hidden' name='choix' id='planField'>
<div class='mb-3'><label class='form-label'><i class='fas fa-desktop'></i> ID machine :</label>
<input class='form-control' readonly value='{{ machine_id }}'></div>
<div class='mb-3'><label class='form-label'><i class='fas fa-code'></i> Clé (optionnelle)</label>
<input name='activation_code' class='form-control' placeholder='XXXX-XXXX-XXXX-XXXX'></div>
<div class='d-grid gap-2 mb-3'>
<button type='submit' class='btn btn-primary' onclick="setPlan('1 mois')">
  <i class='fas fa-calendar-day'></i> 1 mois (25 $)
</button>
<button type='submit' class='btn btn-info' onclick="setPlan('1 an')">
  <i class='fas fa-calendar-alt'></i> 1 an (50 $)
</button>
<button type='submit' class='btn btn-warning' onclick="setPlan('illimité')">
  <i class='fas fa-infinity'></i> Illimité (120 $)
</button>
{% with m = get_flashed_messages(with_categories=true) %}
  {% for c,msg in m %}<div class='alert alert-{{c}}'>{{msg}}</div>{% endfor %}{% endwith %}
</form>
<div class='contact-info'>
    <p>Pour toute question concernant l'activation, le paiement ou le support technique, contactez-nous. Vous pouvez nous joindre par email à sastoukadigital@gmail.com pour des requêtes détaillées, ou via WhatsApp au +212652084735 pour une assistance rapide et directe.</p>
    <a href='mailto:sastoukadigital@gmail.com' class='btn btn-outline-info'><i class='fas fa-envelope'></i> Email</a>
    <a href='https://wa.me/212652084735' class='btn btn-outline-success' target='_blank'><i class='fab fa-whatsapp'></i> WhatsApp</a>
</div>
</div></div></div></div>
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

    # Si la licence est DÉJÀ valide, on redirige vers l'accueil.
    if "email" in session and check_activation():
        return redirect(url_for("accueil.accueil"))

    hwid, today = get_hardware_id(), date.today()
    ctx = dict(machine_id=hwid,
               week_rank=_week_of_month(today),
               month_year=today.strftime("%m/%Y"),
               TRIAL_DAYS=TRIAL_DAYS)

    if request.method == "POST":
        plan = request.form["choix"]
        code = request.form.get("activation_code","").strip().upper()
        
        tariffs = {"1 mois":"25.00","1 an":"50.00","illimité":"120.00"}
        if plan in tariffs:
            # Vérification de la clé manuelle (si fournie)
            expected_paid_code = generate_activation_key_for_user(hwid, plan, today)
            if code and code == expected_paid_code:
                update_activation(plan, code)
                flash("Plan activé par clé !","success")
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
                flash(f"Erreur PayPal : {e}","danger")
        else:
            flash("Plan de paiement invalide sélectionné.", "danger")

    return render_template_string(activation_template, **ctx)

@activation_bp.route("/paypal_success")
def paypal_success():
    login._set_login_paths()
    oid = request.args.get("token")
    if oid and oid in orders and capture_paypal_order(oid):
        plan, code = orders.pop(oid)
        update_activation(plan, code)
        flash("Paiement validé – licence activée !","success")
        return redirect(url_for("accueil.accueil"))
    return render_template_string(failed_activation_template)

@activation_bp.route("/paypal_cancel")
def paypal_cancel():
    login._set_login_paths()
    flash("Paiement annulé.","warning")
    return redirect(url_for("activation.activation"))