// Service Worker for AirWatch ASEAN PWA
const CACHE_NAME = 'airwatch-v1';
const OFFLINE_URL = '/';

// Assets to cache
const ASSETS = [
    '/',
    '/index.html',
    '/manifest.json',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
    'https://unpkg.com/leaflet.markercluster/dist/leaflet.markercluster.js',
    'https://unpkg.com/leaflet.heat/dist/leaflet-heat.js',
    'https://cdn.jsdelivr.net/npm/chart.js',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css'
];

// Install
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS))
            .then(() => self.skipWaiting())
    );
});

// Activate
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch - Network first, cache fallback
self.addEventListener('fetch', event => {
    // Skip API requests - always fetch fresh
    if (event.request.url.includes('/api/')) {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then(response => {
                // Clone and cache successful responses
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, clone);
                    });
                }
                return response;
            })
            .catch(() => {
                // Fallback to cache
                return caches.match(event.request)
                    .then(cached => cached || caches.match(OFFLINE_URL));
            })
    );
});

// Push Notification Handler (for future use)
self.addEventListener('push', event => {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body || 'Có cảnh báo mới về chất lượng không khí',
            icon: '/icon-192.png',
            badge: '/icon-72.png',
            vibrate: [100, 50, 100],
            data: { url: data.url || '/' },
            actions: [
                { action: 'view', title: 'Xem chi tiết' },
                { action: 'close', title: 'Đóng' }
            ]
        };
        event.waitUntil(
            self.registration.showNotification(data.title || 'AirWatch ASEAN', options)
        );
    }
});

// Notification Click Handler
self.addEventListener('notificationclick', event => {
    event.notification.close();
    if (event.action === 'view' || !event.action) {
        event.waitUntil(
            clients.openWindow(event.notification.data.url || '/')
        );
    }
});
