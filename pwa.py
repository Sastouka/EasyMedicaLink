# --- pwa.py (mis à jour et fiabilisé) ---
from flask import (
    Blueprint, url_for, make_response,
    send_from_directory, current_app
)
import json, pathlib

# Blueprint PWA
pwa_bp = Blueprint(
    "pwa_bp", __name__,
    static_folder="static",
    url_prefix=""
)

BASE_DIR = pathlib.Path(__file__).resolve().parent
ICON_DIR = BASE_DIR / "static" / "pwa"
ICON_DIR.mkdir(parents=True, exist_ok=True)

# Manifest dynamique
def _manifest():
    return {
        "name":             "EasyMedicalink",
        "short_name":       "EML",
        "start_url":        "/login",
        "scope":            "/",
        "display":          "standalone",
        "theme_color":      "#1a73e8",
        "background_color": "#ffffff",
        "icons": [
            {
                "src":   url_for("pwa_bp.pwa_icon", filename="icon-192.png"),
                "sizes": "192x192",
                "type":  "image/png"
            },
            {
                "src":   url_for("pwa_bp.pwa_icon", filename="icon-512.png"),
                "sizes": "512x512",
                "type":  "image/png"
            }
        ]
    }

@pwa_bp.route("/manifest.webmanifest")
def manifest():
    resp = make_response(
        json.dumps(_manifest(), ensure_ascii=False, separators=(",", ":"))
    )
    resp.headers["Content-Type"] = "application/manifest+json"
    resp.cache_control.max_age = 86400
    return resp

@pwa_bp.route("/sw.js")
def sw():
    urls = [
        url_for("pwa_bp.manifest"),
        url_for("pwa_bp.sw"),
        url_for("pwa_bp.pwa_icon", filename="icon-192.png"),
        url_for("pwa_bp.pwa_icon", filename="icon-512.png"),
        "/",
        "/login",
        "/accueil",
        "/offline",
        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
        'https://cdn.jsdelivr.net/npm/sweetalert2@11',
        'https://cdn.tailwindcss.com',
    ]
    all_urls = list(set(urls + current_app.config.get("PWA_OFFLINE_URLS", [])))
    precache_urls_json = json.dumps(all_urls)

    sw_code = f"""
// sw.js - Service Worker pour EasyMedicaLink PWA

// Nom du cache : incrémenté pour forcer la mise à jour
const CACHE_NAME = 'easymedicalink-cache-v1.1.0';

const urlsToCache = {precache_urls_json};

// -----------------------------------------------------------------------------
// Événement 'install' : VERSION AMÉLIORÉE ET PLUS ROBUSTE
// Met en cache les fichiers un par un pour éviter un échec total.
// -----------------------------------------------------------------------------
self.addEventListener('install', (event) => {{
    console.log('[Service Worker] Installation...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {{
                console.log('[Service Worker] Pré-caching des assets de l\'application.');
                const cachePromises = urlsToCache.map((urlToCache) => {{
                    return cache.add(urlToCache).catch((error) => {{
                        console.warn(`[Service Worker] Échec du caching pour ${{urlToCache}}:`, error);
                    }});
                }});
                return Promise.all(cachePromises);
            }})
            .then(() => self.skipWaiting()) // Force l'activation du nouveau SW
            .catch((error) => {{
                console.error('[Service Worker] Erreur majeure lors de l\'installation:', error);
            }})
    );
}});

// -----------------------------------------------------------------------------
// Événement 'activate' : Gère la mise à jour des caches
// -----------------------------------------------------------------------------
self.addEventListener('activate', (event) => {{
    console.log('[Service Worker] Activation...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {{
            return Promise.all(
                cacheNames.map((cacheName) => {{
                    if (cacheName !== CACHE_NAME) {{
                        console.log('[Service Worker] Suppression de l\'ancien cache :', cacheName);
                        return caches.delete(cacheName);
                    }}
                }})
            );
        }}).then(() => self.clients.claim())
    );
}});

// -----------------------------------------------------------------------------
// Événement 'fetch' : VERSION AMÉLIORÉE
// Intercepte les requêtes et gère correctement les ressources externes (CDN).
// -----------------------------------------------------------------------------
self.addEventListener('fetch', (event) => {{
    if (event.request.method !== 'GET') {{
        return;
    }}

    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {{
            if (cachedResponse) {{
                return cachedResponse;
            }}

            return fetch(event.request)
                .then((networkResponse) => {{
                    // On vérifie seulement que la réponse est valide (status 200)
                    if (!networkResponse || networkResponse.status !== 200) {{
                        return networkResponse;
                    }}

                    const responseToCache = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {{
                        cache.put(event.request, responseToCache);
                    }});
                    return networkResponse;
                }})
                .catch(() => {{
                    // Si le réseau échoue, sert la page hors ligne pour la navigation.
                    if (event.request.mode === 'navigate') {{
                        return caches.match('/offline');
                    }}
                }});
        }})
    );
}});
"""
    resp = make_response(sw_code, 200)
    resp.headers["Content-Type"] = "text/javascript"
    resp.cache_control.no_cache = True
    return resp

# Alias pour service-worker.js pour une meilleure compatibilité
@pwa_bp.route("/service-worker.js")
def service_worker():
    return sw()

@pwa_bp.route("/icon/<path:filename>")
def pwa_icon(filename):
    return send_from_directory(ICON_DIR, filename)

@pwa_bp.app_context_processor
def inject_pwa():
    def pwa_head():
        return f"""
<link rel="manifest" href="{url_for('pwa_bp.manifest')}">
<link rel="apple-touch-icon" sizes="192x192"
      href="{url_for('pwa_bp.pwa_icon', filename='icon-192.png')}">
<meta name="theme-color" content="#1a73e8">
<meta name="mobile-web-app-capable" content="yes">
<script>
  if ('serviceWorker' in navigator) {{
    navigator.serviceWorker.register('{url_for('pwa_bp.sw')}', {{ scope: '/' }})
      .then(() => console.log('Service Worker enregistré avec succès'))
      .catch(err => console.error('Erreur d’enregistrement du Service Worker:', err));
  }}
</script>
"""
    return dict(pwa_head=pwa_head)