/* Ejecutar: node tests/frontend-security.cjs. Sin dependencias ni servidor. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
let checks = 0;
const test = async (name, run) => { await run(); checks++; console.log('✓ ' + name); };
const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { 'Content-Type': 'application/json' },
});

function admin(fetcher) {
  const redirects = [];
  const calls = [];
  const elements = { '#aviso': {}, '#cerrar-sesion': {} };
  const ctx = vm.createContext({
    document: { readyState: 'loading', addEventListener() {}, querySelector: (key) => elements[key] },
    ResizeObserver: class {}, location: { assign: (to) => redirects.push(to) },
    fetch: async (...args) => { calls.push(args); return fetcher(...args); },
  });
  // Exponer solo funciones para la prueba, sin ejecutar el arranque de toda la interfaz.
  const source = fs.readFileSync(path.join(root, 'sitio/assets/js/admin.js'), 'utf8')
    .replace(/\}\)\(\);\s*$/, 'globalThis.testAdmin = { api, staffSession, cerrarSesion };\n})();');
  vm.runInContext(source, ctx);
  return { ...ctx.testAdmin, redirects, calls, elements };
}

const ORIGIN = 'https://cisne.example';
function sw() {
  const hooks = {}, buckets = new Map(), deleted = [], requests = [];
  const keyOf = (key) => new URL(typeof key === 'string' ? key : key.url, ORIGIN).href;
  const bucket = (name) => {
    if (!buckets.has(name)) buckets.set(name, new Map());
    const items = buckets.get(name);
    return {
      put: async (key, value) => items.set(keyOf(key), value.clone()),
      match: async (key) => items.get(keyOf(key))?.clone(),
    };
  };
  let network = async (key) => new Response('network:' + keyOf(key));
  const ctx = vm.createContext({
    URL, Response, Set,
    self: { location: { origin: ORIGIN }, addEventListener: (name, fn) => { hooks[name] = fn; },
      skipWaiting: async () => {}, clients: { claim: async () => {} } },
    caches: { open: async (name) => bucket(name), keys: async () => [...buckets.keys()],
      delete: async (name) => { deleted.push(name); return buckets.delete(name); } },
    fetch: async (...args) => { requests.push(args); return network(...args); },
  });
  vm.runInContext(fs.readFileSync(path.join(root, 'sitio/sw.js'), 'utf8'), ctx);
  const version = vm.runInContext('VERSION', ctx);
  const request = (url, opts = {}) => ({ url: new URL(url, ORIGIN).href, method: 'GET',
    cache: 'default', headers: new Headers(), mode: 'navigate', ...opts });
  return { buckets, deleted, requests, version, bucket,
    network: (fn) => { network = fn; },
    lifecycle: async (name) => { let p; hooks[name]({ waitUntil: (promise) => { p = promise; } }); await p; },
    dispatch: (url, opts) => { let result; hooks.fetch({ request: request(url, opts),
      respondWith: (promise) => { result = promise; } }); return result; },
  };
}

(async () => {
  await test('admin comparte la verificación de sesión y envía CSRF en POST/PUT', async () => {
    const app = admin(async (url) => url === '/cms/api/session'
      ? json({ user: { role: 'owner' }, csrf: 'test-csrf' }) : json({ ok: true }));
    await Promise.all([app.api('/canjear', { body: { codigo: 'CN-ABCDE' } }),
      app.api('/ajustes', { method: 'put', body: { wifi: { ssid: 'Prueba' } } })]);
    assert.equal(app.calls.filter(([url]) => url === '/cms/api/session').length, 1);
    for (const [url, opts] of app.calls.filter(([url]) => url.startsWith('/api/admin'))) {
      assert.equal(opts.headers['X-CSRF-Token'], 'test-csrf');
      assert.equal(opts.credentials, 'same-origin');
      assert.equal(opts.cache, 'no-store');
      assert.equal(opts.method, url.endsWith('ajustes') ? 'PUT' : 'POST');
    }
    await app.api('/estadisticas');
    assert.equal(app.calls.at(-1)[1].headers['X-CSRF-Token'], undefined);
  });
  await test('admin rechaza un rol sin permiso sin llamar a la API de administración', async () => {
    const app = admin(async () => json({ user: { role: 'editor' }, csrf: 'x' }));
    await assert.rejects(app.api('/resumen'), (ex) => ex.status === 403);
    assert.equal(app.calls.length, 1);
    assert.equal(app.redirects.length, 0);
  });
  await test('admin con sesión vencida vuelve al CMS y conserva el error 401', async () => {
    const app = admin(async () => json({ error: 'Sesión vencida' }, 401));
    await assert.rejects(app.api('/resumen'), (ex) => ex.status === 401);
    assert.deepEqual(app.redirects, ['/cms/?next=/admin/']);
    assert.equal(app.calls.length, 1);
  });
  await test('admin redirige también cuando vence la sesión entre peticiones', async () => {
    const app = admin(async (url) => url === '/cms/api/session'
      ? json({ user: { role: 'owner' }, csrf: 'x' }) : json({ error: 'Sesión vencida' }, 401));
    await assert.rejects(app.api('/canjear', { body: {} }), (ex) => ex.status === 401);
    assert.deepEqual(app.redirects, ['/cms/?next=/admin/']);
  });
  await test('admin no reintenta mutaciones rechazadas por el servidor', async () => {
    const app = admin(async (url) => url === '/cms/api/session'
      ? json({ user: { role: 'owner' }, csrf: 'x' }) : json({ error: 'CSRF inválido' }, 403));
    await assert.rejects(app.api('/canjear', { body: {} }), (ex) => ex.status === 403 && ex.message === 'CSRF inválido');
    assert.equal(app.calls.length, 2);
    assert.equal(app.redirects.length, 0);
  });
  await test('admin distingue desconexión y cierra sesión con POST y CSRF', async () => {
    await assert.rejects(admin(async () => { throw new TypeError('offline'); }).api('/resumen'),
      (ex) => ex.status === 0);
    const app = admin(async (url) => url === '/cms/api/session'
      ? json({ user: { role: 'owner' }, csrf: 'logout-csrf' }) : json({ ok: true }));
    await app.cerrarSesion();
    const [url, opts] = app.calls.at(-1);
    assert.equal(url, '/cms/api/logout');
    assert.equal(opts.method, 'POST');
    assert.equal(opts.headers['X-CSRF-Token'], 'logout-csrf');
    assert.deepEqual(app.redirects, ['/cms/?next=/admin/']);
  });
  await test('SW ignora paneles, APIs, preview, datos privados y peticiones sensibles', async () => {
    const worker = sw();
    for (const url of ['/cms', '/cms/', '/cms/api/session', '/cms/preview/', '/admin', '/admin/',
      '/equipo/', '/api', '/api/config', '/data/socios.json', '/preview/', '/v2/menu/',
      '/menu/?preview=1', '/menu/?token=abc', 'https://otro.example/menu/']) {
      assert.equal(worker.dispatch(url), undefined, url);
    }
    assert.equal(worker.dispatch('/menu/', { method: 'POST' }), undefined);
    assert.equal(worker.dispatch('/menu/', { cache: 'no-store' }), undefined);
    assert.equal(worker.dispatch('/menu/', { headers: new Headers({ Authorization: 'Bearer test' }) }), undefined);
    assert.equal(worker.requests.length, 0);
  });
  await test('SW borra únicamente versiones anteriores de su propia caché', async () => {
    const worker = sw();
    for (const name of ['otra-app', 'cn-equipo-v1', 'cn-public-antigua', worker.version]) worker.bucket(name);
    await worker.lifecycle('activate');
    assert.deepEqual(worker.deleted, ['cn-public-antigua']);
    assert(worker.buckets.has('otra-app'));
    assert(worker.buckets.has('cn-equipo-v1'));
  });
  await test('SW precarga sin cookies y abre el menú instalado sin red', async () => {
    const worker = sw();
    await worker.lifecycle('install');
    assert.equal(worker.requests.length, 3);
    for (const [, opts] of worker.requests) assert.equal(opts.credentials, 'omit');
    worker.network(async () => { throw new Error('offline'); });
    assert.match(await (await worker.dispatch('/menu/?app=1')).text(), /network:.*\/menu\//);
    const data = await worker.dispatch('/data/menu.json', { mode: 'cors' });
    assert.match(await data.text(), /network:.*\/data\/menu.json/);
  });
  await test('SW respeta no-store y private, y nunca ofrece HTML como JSON de respaldo', async () => {
    const worker = sw();
    for (const policy of ['no-store', 'max-age=0, private']) {
      worker.network(async () => new Response('privado', { headers: { 'Cache-Control': policy } }));
      assert.equal(await (await worker.dispatch('/menu/')).text(), 'privado');
      assert.equal(await worker.bucket(worker.version).match('/menu/'), undefined);
    }
    await worker.bucket('otra-app').put('/data/menu.json', new Response('datos de otra app'));
    worker.network(async () => { throw new Error('offline'); });
    const response = await worker.dispatch('/data/menu.json', { mode: 'cors' });
    assert.equal(response.status, 503);
    assert.match(response.headers.get('Content-Type'), /application\/json/);
    assert.match((await response.json()).error, /Sin conexión/);
  });
  await test('SW usa caché propia para assets versionados y nunca guarda respuestas de error', async () => {
    const worker = sw();
    const asset = '/assets/js/menu.js?v=2';
    await worker.bucket('otra-app').put(asset, new Response('otra app'));
    assert.match(await (await worker.dispatch(asset, { mode: 'cors' })).text(), /network:/);
    worker.network(async () => { throw new Error('offline'); });
    assert.match(await (await worker.dispatch(asset, { mode: 'cors' })).text(), /network:/);
    worker.network(async () => new Response('no autorizado', { status: 401 }));
    assert.equal((await worker.dispatch('/menu/')).status, 401);
    assert.equal(await worker.bucket(worker.version).match('/menu/'), undefined);
  });
  console.log(`\n${checks} pruebas aprobadas.`);
})().catch((ex) => { console.error(ex); process.exitCode = 1; });
