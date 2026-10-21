/* Auditoría responsiva multi-dispositivo y multi-motor de cisnenegro.softvibes.art.
 *
 * Uso:
 *   python3 backend/dev_server.py 8082 &          # sitio + club con datos de prueba
 *   NODE_PATH=<carpeta con playwright>/node_modules node tests/responsive/audit.cjs [baseURL] [filtro]
 *
 * Mide en cada vista: desbordamiento horizontal (y qué lo causa), objetivos táctiles pequeños,
 * inputs que hacen zoom en iOS (<16px), texto recortado y errores de consola. Guarda capturas y
 * un reporte JSON en sitio/qa/responsive/ (ignorado por git y fuera del deploy).
 */
const { chromium, webkit, firefox, devices } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.argv[2] || 'http://127.0.0.1:8082';
const FILTRO = process.argv[3] || '';
const OUT = path.join(__dirname, '..', '..', 'sitio', 'qa', 'responsive');
fs.mkdirSync(OUT, { recursive: true });

const MOTORES = { chromium, webkit, firefox };
const PERFILES = [
  // Teléfonos
  { id: 'android-320-galaxy-s9', motor: 'chromium', d: devices['Galaxy S9+'] },
  { id: 'android-360-galaxy-s24', motor: 'chromium', d: devices['Galaxy S24'] },
  { id: 'android-412-pixel7', motor: 'chromium', d: devices['Pixel 7'] },
  { id: 'android-pixel7-horizontal', motor: 'chromium', d: devices['Pixel 7 landscape'] },
  { id: 'iphone-375-se', motor: 'webkit', d: devices['iPhone SE (3rd gen)'] },
  { id: 'iphone-393-16', motor: 'webkit', d: devices['iPhone 16'] },
  { id: 'iphone-440-16promax', motor: 'webkit', d: devices['iPhone 16 Pro Max'] },
  { id: 'iphone-16-horizontal', motor: 'webkit', d: devices['iPhone 16 landscape'] },
  // Tabletas
  { id: 'ipad-mini-768', motor: 'webkit', d: devices['iPad Mini'] },
  { id: 'ipad-pro11-834', motor: 'webkit', d: devices['iPad Pro 11'] },
  { id: 'ipad-pro11-horizontal', motor: 'webkit', d: devices['iPad Pro 11 landscape'] },
  { id: 'android-tab-s9', motor: 'chromium', d: devices['Galaxy Tab S9'] },
  { id: 'android-tab-s9-horizontal', motor: 'chromium', d: devices['Galaxy Tab S9 landscape'] },
  // Escritorio
  { id: 'mac-safari-1440', motor: 'webkit', d: { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 } },
  { id: 'mac-chrome-1512', motor: 'chromium', d: { viewport: { width: 1512, height: 982 }, deviceScaleFactor: 2 } },
  { id: 'win-chrome-1366', motor: 'chromium', d: { viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 } },
  { id: 'win-edge-1536-125pct', motor: 'chromium', d: { viewport: { width: 1536, height: 864 }, deviceScaleFactor: 1.25 } },
  { id: 'win-firefox-1920', motor: 'firefox', d: { viewport: { width: 1920, height: 1080 } } },
  { id: 'win-laptop-1280', motor: 'firefox', d: { viewport: { width: 1280, height: 720 } } },
  { id: 'desktop-2560', motor: 'chromium', d: { viewport: { width: 2560, height: 1440 } } },
];

const VISTAS = [
  { id: 'landing', url: '/' },
  { id: 'menu', url: '/menu/' },
  { id: 'menu-pasaporte-invitado', url: '/menu/#pasaporte' },
  { id: 'menu-pasaporte-socio', url: '/menu/#pasaporte', socio: true },
  { id: 'menu-ranking', url: '/menu/#ranking', socio: true },
  { id: 'admin-hoy', url: '/admin/#hoy' },
  { id: 'admin-estadisticas', url: '/admin/#estadisticas' },
  { id: 'admin-nps', url: '/admin/#nps' },
  { id: 'admin-miembros', url: '/admin/#miembros' },
  { id: 'admin-ranking', url: '/admin/#ranking' },
  { id: 'analisis', url: '/analisis/' },
  { id: 'proyecto', url: '/proyecto/' },
  { id: 'privacidad', url: '/privacidad/' },
];

/* Se ejecuta dentro de la página. */
function medir(esTactil) {
  const W = document.documentElement.clientWidth;
  const desc = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    if (el.classList.length) s += '.' + [...el.classList].slice(0, 2).join('.');
    return s;
  };
  const visible = (el, cs) => cs.display !== 'none' && cs.visibility !== 'hidden' && cs.opacity !== '0';
  const enContenedorConScroll = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if (o === 'auto' || o === 'scroll' || o === 'hidden' || o === 'clip') return true;
    }
    return false;
  };
  const res = { ancho: W, desborde: document.documentElement.scrollWidth - W, culpables: [], tactiles: [], zoomIOS: [], recortes: [] };
  const todos = [...document.querySelectorAll('body *')];
  const culpables = new Set();
  for (const el of todos) {
    const cs = getComputedStyle(el);
    if (!visible(el, cs) || cs.position === 'fixed') continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if ((r.right > W + 1 || r.left < -1) && !enContenedorConScroll(el) && !el.closest('dialog:not([open])')) culpables.add(el);
    const soloLector = r.width <= 1 || r.height <= 1 || cs.clip !== 'auto' || el.classList.contains('sr-only');
    if (!soloLector && cs.overflow === 'hidden' && el.scrollWidth > el.clientWidth + 2 && el.children.length === 0 && el.textContent.trim()
        && cs.textOverflow !== 'ellipsis') res.recortes.push(desc(el) + ' «' + el.textContent.trim().slice(0, 30) + '»');
  }
  // Solo el culpable más externo de cada rama
  for (const el of culpables) {
    if (el.parentElement && culpables.has(el.parentElement)) continue;
    res.culpables.push(desc(el) + ' right=' + Math.round(el.getBoundingClientRect().right));
  }
  const SEL = 'a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=tab],[role=switch],summary';
  for (const el of document.querySelectorAll(SEL)) {
    const cs = getComputedStyle(el);
    if (!visible(el, cs)) continue;
    if (el.closest('dialog:not([open])')) continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (/^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName) && parseFloat(cs.fontSize) < 16 && !/checkbox|radio|range|color/.test(el.type))
      res.zoomIOS.push(desc(el) + ' ' + cs.fontSize);
    if (!esTactil) continue;
    const enTexto = el.tagName === 'A' && cs.display === 'inline' && el.closest('p,li,td,dd,small,figcaption,label,span');
    const tipo = (el.type || '').toLowerCase();
    if (enTexto) continue;
    // checkbox/radio cuentan con su label; se mide el label si existe
    let caja = r;
    if (tipo === 'checkbox' || tipo === 'radio') {
      const lab = el.closest('label') || (el.id && document.querySelector(`label[for="${el.id}"]`));
      if (lab) caja = lab.getBoundingClientRect();
    }
    const min = Math.min(caja.width, caja.height);
    if (min < 40) res.tactiles.push(desc(el) + ` ${Math.round(caja.width)}×${Math.round(caja.height)}` + (el.textContent.trim() ? ' «' + el.textContent.trim().slice(0, 18) + '»' : ''));
  }
  res.tactiles = [...new Set(res.tactiles)].slice(0, 25);
  res.recortes = [...new Set(res.recortes)].slice(0, 15);
  return res;
}

async function main() {
  const reporte = [];
  const porMotor = {};
  for (const p of PERFILES.filter((x) => !FILTRO || x.id.includes(FILTRO))) (porMotor[p.motor] ||= []).push(p);
  await Promise.all(Object.entries(porMotor).map(async ([motor, perfiles]) => {
    const browser = await MOTORES[motor].launch();
    for (const perfil of perfiles) {
      const d = { ...perfil.d };
      if (motor === 'firefox') delete d.isMobile;
      for (const vista of VISTAS) {
        const ctx = await browser.newContext({ ...d, baseURL: BASE, locale: 'es-MX', timezoneId: 'America/Mexico_City' });
        if (vista.socio) await ctx.request.post('/api/login', { data: { telefono: '7711000000', pin: '1111' } });
        const page = await ctx.newPage();
        const errores = [];
        page.on('pageerror', (e) => errores.push(String(e.message).slice(0, 120)));
        page.on('console', (m) => { if (m.type() === 'error' && !/favicon|fonts\.g|ERR_|Failed to load resource/.test(m.text())) errores.push(m.text().slice(0, 120)); });
        try {
          await page.goto(vista.url, { waitUntil: 'networkidle', timeout: 30000 });
        } catch (e) { errores.push('carga: ' + e.message.slice(0, 80)); }
        await page.waitForTimeout(700);
        const m = await page.evaluate(medir, !!d.hasTouch).catch((e) => ({ error: e.message }));
        const archivo = `${perfil.id}__${vista.id}.png`;
        await page.screenshot({ path: path.join(OUT, archivo) }).catch(() => {});
        reporte.push({ perfil: perfil.id, motor, vista: vista.id, ...m, errores, captura: archivo });
        await ctx.close();
      }
    }
    await browser.close();
  }));
  fs.writeFileSync(path.join(OUT, 'reporte.json'), JSON.stringify(reporte, null, 2));
  // Resumen
  const prob = reporte.filter((r) => r.desborde > 0 || r.tactiles?.length || r.zoomIOS?.length || r.recortes?.length || r.errores?.length || r.error);
  console.log(`Vistas auditadas: ${reporte.length} · con hallazgos: ${prob.length}`);
  for (const r of prob) {
    const partes = [];
    if (r.desborde > 0) partes.push(`DESBORDE +${r.desborde}px [${(r.culpables || []).slice(0, 4).join(', ')}]`);
    if (r.zoomIOS?.length) partes.push(`ZOOM-iOS ${r.zoomIOS.slice(0, 3).join(', ')}`);
    if (r.tactiles?.length) partes.push(`TÁCTIL(${r.tactiles.length}) ${r.tactiles.slice(0, 4).join(' | ')}`);
    if (r.recortes?.length) partes.push(`RECORTE ${r.recortes.slice(0, 3).join(', ')}`);
    if (r.errores?.length || r.error) partes.push(`ERROR ${(r.errores || []).concat(r.error || []).slice(0, 2).join(' | ')}`);
    console.log(`- ${r.perfil} · ${r.vista}: ${partes.join(' · ')}`);
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
