# --- pwa.py (mise à jour complète pour éviter les erreurs PWA) ---
# Ajout d'un alias pour service-worker.js afin de résoudre le 404
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

# BASE_DIR for PWA assets remains static as PWA assets are globally accessible
# and not specific to an admin's dynamic folder.
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
            # Déclaration de toutes les tailles courantes.
            # Le navigateur choisira la meilleure disponible.
            # Idéalement, ces fichiers devraient exister avec les dimensions exactes.
            # Sinon, le navigateur redimensionnera icon-192 ou icon-512.
            {
                "src": url_for("pwa_bp.pwa_icon", filename="icon-48.png"),
                "sizes": "48x48",
                "type": "image/png"
            },
            {
                "src": url_for("pwa_bp.pwa_icon", filename="icon-72.png"),
                "sizes": "72x72",
                "type": "image/png"
            },
            {
                "src": url_for("pwa_bp.pwa_icon", filename="icon-96.png"),
                "sizes": "96x96",
                "type": "image/png"
            },
            {
                "src": url_for("pwa_bp.pwa_icon", filename="icon-128.png"),
                "sizes": "128x128",
                "type": "image/png"
            },
            {
                "src": url_for("pwa_bp.pwa_icon", filename="icon-144.png"),
                "sizes": "144x144",
                "type": "image/png"
            },
            {
                "src": url_for("pwa_bp.pwa_icon", filename="icon-152.png"),
                "sizes": "152x152",
                "type": "image/png"
            },
            {
                "src": url_for("pwa_bp.pwa_icon", filename="icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable" # Ajout purpose aux icônes principales
            },
            {
                "src": url_for("pwa_bp.pwa_icon", filename="icon-256.png"),
                "sizes": "256x256",
                "type": "image/png"
            },
            {
                "src": url_for("pwa_bp.pwa_icon", filename="icon-384.png"),
                "sizes": "384x384",
                "type": "image/png"
            },
            {
                "src": url_for("pwa_bp.pwa_icon", filename="icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable" # Ajout purpose aux icônes principales
            }
        ]
    }

@pwa_bp.route("/manifest.webmanifest")
def manifest():
    resp = make_response(
        json.dumps(_manifest(), ensure_ascii=False, separators=(",", ":"))
    )
    resp.headers["Content-Type"] = "application/manifest+json"
    # Utiliser no-cache pour le manifeste pendant le développement
    # Ceci garantira que les changements du manifeste sont toujours immédiatement récupérés.
    resp.cache_control.no_cache = True
    return resp

@pwa_bp.route("/sw.js")
def sw():
    # PWA service worker URLs, typically static and don't depend on dynamic user folders
    urls = [
        url_for("pwa_bp.manifest"),
        url_for("pwa_bp.sw"),
        # Ajout de toutes les icônes supplémentaires pour le pré-caching
        url_for("pwa_bp.pwa_icon", filename="icon-48.png"),
        url_for("pwa_bp.pwa_icon", filename="icon-72.png"),
        url_for("pwa_bp.pwa_icon", filename="icon-96.png"),
        url_for("pwa_bp.pwa_icon", filename="icon-128.png"),
        url_for("pwa_bp.pwa_icon", filename="icon-144.png"),
        url_for("pwa_bp.pwa_icon", filename="icon-152.png"),
        url_for("pwa_bp.pwa_icon", filename="icon-192.png"),
        url_for("pwa_bp.pwa_icon", filename="icon-256.png"),
        url_for("pwa_bp.pwa_icon", filename="icon-384.png"),
        url_for("pwa_bp.pwa_icon", filename="icon-512.png"),
        "/",
        "/login",
        "/accueil", # Ajouté pour s'assurer que la page d'accueil est pré-cachée
        "/offline", # Ajouté pour s'assurer que la page hors ligne est pré-cachée
        "/static/logo.png", # Exemple de ressource statique
        # Ajoutez ici d'autres ressources statiques importantes (CSS, JS, images)
        # Par exemple:
        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
        'https://cdn.jsdelivr.net/npm/sweetalert2@11',
        'https://cdn.tailwindcss.com',
    ]
    # Étendre avec les URLs définies dans app.py pour le mode hors ligne
    all_urls = list(set(urls + current_app.config.get("PWA_OFFLINE_URLS", [])))
    
    # Sérialiser la liste des URLs en une chaîne JSON valide pour JavaScript
    # Nous allons la passer comme une chaîne et la "parser" dans le SW.
    precache_urls_js_string = json.dumps(all_urls, ensure_ascii=False)

    sw_code = f"""
// sw.js - Service Worker pour EasyMedicaLink PWA

// Nom du cache pour cette version du Service Worker
// Changez cette version si vous modifiez les assets à pré-cacher
const CACHE_NAME = 'easymedicalink-cache-v1.0.7'; // Version incrémentée pour forcer la mise à jour

// Liste des URLs à pré-cacher lors de l'installation du Service Worker
// Ces URLs sont définies dans app.py et passées au template pwa_head()
// Assurez-vous que toutes les ressources critiques sont listées ici.
// Les URLs dynamiques (comme /patient_rdv/...) ne peuvent pas être pré-cachées
// de cette manière et seront gérées par la stratégie de cache au runtime.
// Nous utilisons JSON.parse pour garantir un tableau JavaScript valide.
const urlsToCache = JSON.parse('{precache_urls_js_string}');

// -----------------------------------------------------------------------------
// Événement 'install' : Se déclenche lorsque le Service Worker est installé
// C'est ici que nous pré-cachons les assets essentiels
// -----------------------------------------------------------------------------
self.addEventListener('install', (event) => {{
    console.log('[Service Worker] Installation...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {{
                console.log('[Service Worker] Pré-caching des assets de l\'application.');
                return cache.addAll(urlsToCache).catch(error => {{
                    console.error('[Service Worker] Échec du pré-caching :', error);
                    // Ne pas rejeter l'installation si une seule URL échoue,
                    // mais c'est une bonne pratique de s'assurer que les URLs sont valides.
                }});
            }})
            .then(() => self.skipWaiting()) // Force l'activation du nouveau Service Worker immédiatement
            .catch((error) => {{
                console.error('[Service Worker] Erreur lors de l\'ouverture du cache ou de l\'ajout des URLs :', error);
            }})
    );
}});

// -----------------------------------------------------------------------------
// Événement 'activate' : Se déclenche lorsque le Service Worker est activé
// C'est ici que nous gérons la mise à jour des caches (suppression des anciens caches)
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
        }}).then(() => self.clients.claim()) // Permet au Service Worker de prendre le contrôle des clients immédiatement
    );
}});

// -----------------------------------------------------------------------------
// Événement 'fetch' : Intercepte toutes les requêtes réseau
// C'est ici que nous définissons les stratégies de cache (Cache-First, Network-First, etc.)
// -----------------------------------------------------------------------------
self.addEventListener('fetch', (event) => {{
    // Ne pas intercepter les requêtes non-GET ou les requêtes vers des origines externes
    // à moins que ce ne soit explicitement nécessaire pour des APIs spécifiques.
    if (event.request.method !== 'GET') {{
        return;
    }}

    // Stratégie Cache-First pour les assets (images, CSS, JS)
    // Tente de répondre depuis le cache en premier, sinon va chercher sur le réseau.
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {{
            if (cachedResponse) {{
                // Si la ressource est dans le cache, la retourner
                return cachedResponse;
            }}

            // Si la ressource n'est pas dans le cache, essayer le réseau
            return fetch(event.request)
                .then((networkResponse) => {{
                    // Vérifier si la réponse est valide avant de la mettre en cache
                    // type 'basic' exclut les réponses opaques (cross-origin sans CORS)
                    if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {{
                        return networkResponse;
                    }}

                    // Cloner la réponse car elle est un flux et ne peut être lue qu'une fois
                    const responseToCache = networkResponse.clone();

                    caches.open(CACHE_NAME).then((cache) => {{
                        cache.put(event.request, responseToCache);
                    }});

                    return networkResponse;
                }})
                .catch(() => {{
                    // Si le réseau échoue et que la ressource n'est pas dans le cache,
                    // tenter de servir une page hors ligne générique si c'est une navigation.
                    if (event.request.mode === 'navigate') {{
                        return caches.match('/offline'); // Redirige vers la page hors ligne
                    }}
                    // Pour les autres types de requêtes (images, scripts), simplement échouer
                    // ou retourner une réponse d'erreur si nécessaire.
                    return new Response('Network error or resource not found in cache.', {{ status: 503, statusText: 'Service Unavailable' }});
                }});
        }})
    );
}});

// -----------------------------------------------------------------------------
// Événement 'message' : Permet de communiquer entre le Service Worker et les pages
// -----------------------------------------------------------------------------
self.addEventListener('message', (event) => {{
    if (event.data && event.data.type === 'SKIP_WAITING') {{
        self.skipWaiting();
    }}
}});

// -----------------------------------------------------------------------------
// Événement 'push' et 'sync' (pour des fonctionnalités avancées)
// Ajoutez ces écouteurs si vous implémentez les notifications push ou la synchronisation en arrière-plan.
// Pour l'instant, ils sont commentés ou laissés vides.
// -----------------------------------------------------------------------------
/*
self.addEventListener('push', (event) => {{
    console.log('[Service Worker] Push Received.');
    const title = 'EasyMedicaLink Notification';
    const options = {{
        body: event.data.text(),
        icon: '/static/logo.png', // Chemin vers une petite icône pour la notification
        badge: '/static/logo.png' // Chemin vers une icône de badge
    }};
    event.waitUntil(self.registration.showNotification(title, options));
}});

self.addEventListener('notificationclick', (event) => {{
    console.log('[Service Worker] Notification click Received.');
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/') // Ouvre l'application lorsque la notification est cliquée
    );
}});

self.addEventListener('sync', (event) => {{
    console.log('[Service Worker] Sync event fired', event.tag);
    if (event.tag === 'sync-data') {{
        event.waitUntil(
            // Ici, vous mettriez la logique pour synchroniser les données en arrière-plan
            console.log('Synchronisation des données en arrière-plan...')
            // Par exemple, envoyer des données en attente au serveur
        );
    }}
}});
*/
"""
    resp = make_response(sw_code, 200)
    resp.headers["Content-Type"] = "text/javascript"
    resp.cache_control.no_cache = True # Ne pas cacher le Service Worker lui-même
    return resp

# Suppression de la route alias /service-worker.js pour éviter les redirections.
# @pwa_bp.route("/service-worker.js")
# def service_worker():
#     return sw()

@pwa_bp.route("/icon/<path:filename>")
def pwa_icon(filename):
    # Assurez-vous que l'en-tête Content-Type est correct pour les images
    return send_from_directory(ICON_DIR, filename, mimetype='image/png')

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
    // IMPORTANT : Pointer directement vers pwa_bp.sw (qui correspond à /sw.js)
    navigator.serviceWorker.register('{url_for('pwa_bp.sw')}', {{ scope: '/' }})
      .then(() => console.log('Service Worker enregistré'))
      .catch(err => console.error('Erreur d’enregistrement SW:', err));
  }}
</script>
"""
    return dict(pwa_head=pwa_head)