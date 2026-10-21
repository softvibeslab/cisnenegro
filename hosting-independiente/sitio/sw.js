/* Caché pública del menú y Pasaporte. Las sesiones y la operación usan siempre red.
 * Solo esta familia de cachés se limpia al actualizar; otras apps conservan las suyas.
 */
const CACHE_PREFIX = 'cn-public-';
const VERSION = CACHE_PREFIX + '20261009a';
const ESENCIAL = ['/menu/', '/data/menu.json', '/offline.html'];
const PAGINAS = new Set(['/', '/index.html', '/menu/', '/menu/index.html',
  '/privacidad/', '/privacidad/index.html', '/offline.html']);
const PUBLIC_QUERY = new Set(['v', 'rev', 'app']);

function publicRequest(req) {
  if (req.method !== 'GET' || req.cache === 'no-store' || req.headers.has('Authorization')) return false;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return false;
  // Una ruta pública con parámetros de preview/sesión tampoco debe entrar a caché.
  if ([...url.searchParams.keys()].some((key) => !PUBLIC_QUERY.has(key))) return false;
  if (/^\/(?:cms|admin|equipo|api|preview|v2)(?:\/|$)/i.test(url.pathname)) return false;
  return PAGINAS.has(url.pathname) || url.pathname === '/data/menu.json' || url.pathname.startsWith('/assets/');
}

function cacheable(res) {
  return res.ok && !res.redirected && res.type !== 'opaque'
    && !/(?:^|,)\s*(?:no-store|private)\b/i.test(res.headers.get('Cache-Control') || '');
}

async function guardar(key, res) {
  if (cacheable(res)) {
    // Una cuota agotada no debe convertir una respuesta válida de red en un error.
    try { await (await caches.open(VERSION)).put(key, res.clone()); } catch (_) { /* seguir en línea */ }
  }
  return res;
}

self.addEventListener('install', (e) => {
  e.waitUntil(Promise.all(ESENCIAL.map(async (path) => {
    // El precache nunca solicita una representación ligada a la sesión del usuario.
    const res = await fetch(path, { credentials: 'omit', cache: 'reload' });
    if (!res.ok || res.redirected) throw new Error('No se pudo preparar el modo sin conexión.');
    return guardar(path, res);
  })).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys
    .filter((key) => key.startsWith(CACHE_PREFIX) && key !== VERSION)
    .map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (!publicRequest(req)) return;
  const url = new URL(req.url);
  if (req.mode === 'navigate' || url.pathname === '/data/menu.json') {
    e.respondWith(fetch(req).then((res) => guardar(req, res)).catch(async () => {
      const cache = await caches.open(VERSION);
      const saved = await cache.match(req);
      if (saved) return saved;
      // Permite abrir la app instalada (?app=1) con el menú público precargado.
      const canonical = await cache.match(url.pathname);
      if (canonical) return canonical;
      if (req.mode === 'navigate') {
        return (await cache.match('/offline.html')) || new Response('Sin conexión.', { status: 503 });
      }
      return new Response(JSON.stringify({ error: 'Sin conexión. No hay un menú guardado.' }), {
        status: 503, headers: { 'Content-Type': 'application/json; charset=utf-8' },
      });
    }));
  } else if (url.pathname.startsWith('/assets/') && url.searchParams.has('v')) {
    e.respondWith(caches.open(VERSION).then(async (cache) =>
      (await cache.match(req)) || fetch(req).then((res) => guardar(req, res))));
  }
});
