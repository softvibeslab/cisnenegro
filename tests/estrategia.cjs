// Prueba de navegador del tablero /estrategia/ (solo lectura).
// Uso: python3 -m http.server 8099 --bind 127.0.0.1 --directory sitio &
//      NODE_PATH=<carpeta con playwright>/node_modules node tests/estrategia.cjs [http://127.0.0.1:8099]
// Capturas en sitio/qa/estrategia/ (fuera de git).
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE = (process.argv[2] || 'http://127.0.0.1:8099').replace(/\/$/, '');
const URL_T = `${BASE}/estrategia/`;
const OUT = path.join(__dirname, '..', 'sitio', 'qa', 'estrategia');
const VISTAS = ['inicio', 'planner', 'parrilla', 'matriz', 'temporada', 'laboratorio', 'estrategia', 'canales', 'cumplimiento'];
const datos = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'sitio', 'estrategia', 'data.json'), 'utf8'));

let fallas = 0, ok = 0;
const check = (cond, msg) => { if (cond) { ok++; } else { fallas++; console.log(`  ✗ ${msg}`); } };

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const errores = [];
  const vigilar = (page) => {
    page.on('pageerror', (e) => errores.push(`pageerror: ${e.message}`));
    page.on('console', (m) => { if (m.type() === 'error' && !/presentacion\.json/.test(m.text()) && !/404/.test(m.text())) errores.push(`console: ${m.text()}`); });
    page.on('requestfailed', (r) => { if (!/fonts\.(googleapis|gstatic)|presentacion\.json/.test(r.url())) errores.push(`requestfailed: ${r.url()}`); });
    page.on('response', (r) => { if (r.status() >= 400 && !/presentacion\.json/.test(r.url())) errores.push(`HTTP ${r.status()}: ${r.url()}`); });
  };

  // ---------------- escritorio
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  const page = await ctx.newPage();
  vigilar(page);
  await page.goto(URL_T, { waitUntil: 'networkidle' });
  check(await page.locator('.bienvenida h2').textContent() === datos.piloto.nombre, 'Inicio muestra el nombre del piloto');
  check((await page.locator('#fuente').textContent()).includes('Semilla'), 'La fuente indica la semilla (sin Hub publicado)');
  const tamNum = await page.locator('.stat-num').first().evaluate((n) => parseFloat(getComputedStyle(n).fontSize));
  check(tamNum >= 36, `los números de los indicadores se ven grandes (${tamNum}px)`);

  for (const v of VISTAS) {
    await page.goto(`${URL_T}#${v}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(150);
    const actual = await page.locator('.nav-item[aria-current=page]').getAttribute('data-vista');
    check(actual === v, `nav marca la vista ${v} (marca ${actual})`);
    check(await page.locator('#vista > *').count() > 0, `la vista ${v} tiene contenido`);
    await page.screenshot({ path: path.join(OUT, `escritorio-${v}.png`), fullPage: true });
  }

  // Matriz: cada mapa de calor tiene su propia fila de semanas
  await page.goto(`${URL_T}#matriz`, { waitUntil: 'networkidle' });
  const heats = await page.locator('.heat').count();
  const cabs = await page.locator('.heat-cab').count();
  check(heats === 2 && cabs > 0 && cabs % heats === 0 && (await page.locator('.heat').first().locator('.heat-cab').count()) === cabs / 2, `cada matriz tiene sus encabezados (${cabs} en ${heats})`);

  // Planner: mes de octubre con las piezas del arranque
  await page.goto(`${URL_T}#planner`, { waitUntil: 'networkidle' });
  const fichasOct = await page.locator('.cal .ficha').count();
  // la rejilla de octubre va del lunes 28-sep al domingo 1-nov; cada día muestra hasta 4 fichas
  const porDia = {};
  datos.piezas.filter((p) => p.fecha >= '2026-09-28' && p.fecha <= '2026-11-01').forEach((p) => { porDia[p.fecha] = (porDia[p.fecha] || 0) + 1; });
  const esperadasOct = Object.values(porDia).reduce((n, c) => n + Math.min(c, 4), 0);
  check(fichasOct === esperadasOct, `el mes de octubre pinta ${esperadasOct} fichas (${fichasOct})`);
  await page.getByRole('button', { name: 'Siguiente' }).click();
  check((await page.locator('.mes-titulo').textContent()).includes('noviembre'), 'el planner avanza a noviembre');
  await page.getByRole('button', { name: 'Semana', exact: true }).click();
  check(await page.locator('.semana-col').count() === 7, 'la vista semanal tiene 7 días');
  await page.getByRole('button', { name: 'Lista', exact: true }).click();
  check(await page.locator('.agenda-dia').count() > 20, 'la lista agrupa por día');

  // Ficha de pieza
  const primera = datos.piezas.find((p) => p.variantes.length >= 4);
  await page.goto(`${URL_T}#parrilla`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: primera.titulo, exact: true }).click();
  const dlg = page.locator('#pieza');
  check(await dlg.evaluate((d) => d.open), 'la ficha de pieza abre como diálogo');
  check(page.url().includes(`/pieza/${encodeURIComponent(primera.clave)}`), 'la URL lleva el enlace directo a la pieza');
  const tabs = dlg.locator('[role=tab]');
  check(await tabs.count() === primera.variantes.length, `hay una pestaña por variante (${await tabs.count()})`);
  const antes = await dlg.locator('.preview').innerHTML();
  await tabs.nth(1).click();
  check((await dlg.locator('.preview').innerHTML()) !== antes, 'cambiar de pestaña cambia la vista previa');
  check(await tabs.nth(1).getAttribute('aria-selected') === 'true', 'la pestaña elegida queda seleccionada');
  await page.screenshot({ path: path.join(OUT, 'escritorio-pieza.png') });
  await page.keyboard.press('Escape');
  check(!(await dlg.evaluate((d) => d.open)), 'Esc cierra la ficha');
  check(!page.url().includes('/pieza/'), 'al cerrar se limpia el enlace directo');

  // Enlace directo
  const stout = datos.piezas.find((p) => p.campana === 'dia-de-la-stout-2026');
  await page.goto(`${URL_T}#temporada/pieza/${encodeURIComponent(stout.clave)}`, { waitUntil: 'networkidle' });
  check((await page.locator('#pieza-titulo').textContent()) === stout.titulo, 'el enlace directo abre la pieza del Día de la Stout');
  await page.screenshot({ path: path.join(OUT, 'escritorio-pieza-stout.png') });
  await page.keyboard.press('Escape');

  // Filtros
  await page.goto(`${URL_T}#parrilla`, { waitUntil: 'networkidle' });
  const total = await page.locator('tbody tr').count();
  check(total === datos.piezas.length, `la parrilla lista las ${datos.piezas.length} piezas (${total})`);
  await page.locator('[data-red=gbp]').click();
  const gbp = datos.piezas.filter((p) => p.variantes.some((v) => v.canal === 'gbp')).length;
  check(await page.locator('tbody tr').count() === gbp, `el filtro de Google deja ${gbp} piezas`);
  await page.locator('#filtros-limpiar').click();
  await page.fill('#filtro-q', 'tlayuda');
  await page.waitForTimeout(400);
  const conTlayuda = await page.locator('tbody tr').count();
  check(conTlayuda >= 1 && conTlayuda < total, `la búsqueda «tlayuda» filtra (${conTlayuda})`);
  await page.locator('#filtros-limpiar').click();
  await page.selectOption('#filtro-campana', 'halloween-2026');
  const hall = datos.piezas.filter((p) => p.campana === 'halloween-2026').length;
  check(await page.locator('tbody tr').count() === hall, `el filtro de Halloween deja ${hall} piezas`);
  await page.locator('#filtros-limpiar').click();

  // CSV
  const [descarga] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Exportar CSV' }).click()]);
  const csv = fs.readFileSync(await descarga.path(), 'utf8');
  check(csv.split('\r\n').length === datos.piezas.length + 1, 'el CSV trae una fila por pieza más el encabezado');

  // Presentación
  await page.goto(`${URL_T}#inicio`, { waitUntil: 'networkidle' });
  await page.locator('#presentar').click();
  check(await page.evaluate(() => document.body.classList.contains('presentando')), 'Presentar activa el modo presentación');
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(200);
  check(page.url().endsWith('#temporada'), '→ avanza a Temporada');
  await page.screenshot({ path: path.join(OUT, 'presentacion-temporada.png') });
  await page.keyboard.press('ArrowLeft');
  await page.waitForTimeout(200);
  check(page.url().endsWith('#inicio'), '← regresa a Inicio');
  await page.locator('#pres-salir').click();
  check(!(await page.evaluate(() => document.body.classList.contains('presentando'))), 'Salir cierra la presentación');

  // ---------------- celular
  const movil = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const m = await movil.newPage();
  vigilar(m);
  for (const v of VISTAS) {
    await m.goto(`${URL_T}#${v}`, { waitUntil: 'networkidle' });
    await m.waitForTimeout(150);
    const desborde = await m.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(desborde <= 1, `sin desborde horizontal en celular: ${v} (${desborde}px)`);
    await m.screenshot({ path: path.join(OUT, `movil-${v}.png`), fullPage: true });
  }
  await m.goto(`${URL_T}#planner`, { waitUntil: 'networkidle' });
  check(await m.locator('.agenda-dia').count() > 0, 'en celular el planner abre en modo lista');
  const altoBadge = await m.locator('.lista-item .badge.prueba').first().evaluate((n) => n.getBoundingClientRect().height);
  check(altoBadge < 26, `la etiqueta R1 conserva su tamaño (${Math.round(altoBadge)}px)`);
  const anchoTitulo = await m.locator('.lista-item strong').first().evaluate((n) => n.getBoundingClientRect().width);
  check(anchoTitulo > 200, `los títulos de la lista tienen espacio en celular (${Math.round(anchoTitulo)}px)`);
  await m.locator('#menu-toggle').click();
  check(await m.locator('#sidebar.open').count() === 1, 'el menú lateral abre en celular');
  await m.locator('.nav-item[data-vista=matriz]').click();
  await m.waitForTimeout(200);
  check(m.url().endsWith('#matriz') && (await m.locator('#sidebar.open').count()) === 0, 'navegar cierra el menú en celular');
  await m.goto(`${URL_T}#planner/pieza/${encodeURIComponent(primera.clave)}`, { waitUntil: 'networkidle' });
  await m.screenshot({ path: path.join(OUT, 'movil-pieza.png') });

  check(errores.length === 0, `sin errores de consola ni de red${errores.length ? `:\n    ${[...new Set(errores)].join('\n    ')}` : ''}`);
  await browser.close();
  console.log(`\n${ok} verificaciones OK, ${fallas} fallas. Capturas en ${path.relative(process.cwd(), OUT)}/`);
  process.exit(fallas ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
