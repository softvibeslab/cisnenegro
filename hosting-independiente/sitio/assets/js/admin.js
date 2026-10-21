/* Cervecería Cisne Negro · Panel del equipo (v2)
 * Pestañas: Hoy · Estadísticas · NPS · Miembros · Ranking · Ajustes (con hash en la URL).
 * El CMS protege /admin y /api/admin con sesión de propietario y CSRF.
 * Todo texto que viene de la API se inserta con textContent (nunca innerHTML).
 */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const SEGUIMIENTO = { nuevo: 'Nuevo', contactado: 'Contactado', resuelto: 'Resuelto', cerrado: 'Cerrado' };
  const TABS = ['hoy', 'estadisticas', 'nps', 'miembros', 'ranking', 'ajustes'];
  const LIMITE = 20;
  const TZ = 'America/Mexico_City';
  const PERIODO_TXT = { semana: 'esta semana', mes: 'este mes', total: 'en total' };
  const NPS_AYUDA = {
    todos: 'Todas las respuestas, de la más reciente a la más antigua.',
    pendientes: 'Pendientes: calificaciones de 0 a 6 que aún no se resuelven. Contacta, escucha y anota qué se hizo.',
    detractores: 'Detractores: calificaciones de 0 a 6.',
    pasivos: 'Pasivos: calificaciones de 7 y 8.',
    promotores: 'Promotores: calificaciones de 9 y 10.',
  };

  const st = {
    tab: 'hoy', semanas: 12, stats: null,
    npsFiltro: 'todos', npsQ: '', npsPagina: 1,
    sociosQ: '', sociosOrden: 'recientes', sociosPagina: 1,
    rankPeriodo: 'mes',
    fichaId: null, ficha: null,
    dn: { modo: 'crear', id: null, socioId: null, volverA: null },
    wifi: null, wifiSucio: false, wifiPassPrevio: '',
  };

  // ── Utilidades ─────────────────────────────────────────────────────────────
  function h(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') n.className = v;
      else if (k === 'text') n.textContent = v;
      else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) {
      if (kid == null || kid === false) continue;
      n.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return n;
  }
  const num = (n) => Number(n || 0).toLocaleString('es-MX');
  const pl = (n, uno, varios) => `${num(n)} ${Number(n) === 1 ? uno : varios}`;
  const pct = (v) => (v == null ? '—' : `${v}%`);
  const npsTxt = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + v);
  const fecha = (iso) => new Date(iso).toLocaleString('es-MX', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: TZ });
  const dia = (d) => (d ? new Date(d.slice(0, 10) + 'T12:00:00-06:00').toLocaleDateString('es-MX', { day: 'numeric', month: 'short', year: 'numeric', timeZone: TZ }) : '—');
  const diaCorto = (d) => new Date(d + 'T12:00:00-06:00').toLocaleDateString('es-MX', { day: 'numeric', month: 'short', timeZone: TZ }).replace('.', '');
  const telFmt = (t) => String(t || '').replace(/^(\d{3})(\d{3})(\d{4})$/, '$1 $2 $3');
  const soloDigitos = (s) => String(s || '').replace(/\D/g, '');
  const claseScore = (s) => (s <= 6 ? 'det' : s <= 8 ? 'pas' : 'pro');
  const tipoScore = (s) => (s <= 6 ? 'Detractor' : s <= 8 ? 'Pasivo' : 'Promotor');
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  class ApiError extends Error { constructor(status, msg) { super(msg); this.status = status; } }

  let staffCsrf = null;
  let sessionRequest = null;
  function iniciarSesion() {
    staffCsrf = null;
    location.assign('/cms/?next=/admin/');
  }
  async function staffSession() {
    if (staffCsrf) return staffCsrf;
    if (!sessionRequest) {
      sessionRequest = (async () => {
        const res = await fetch('/cms/api/session', { credentials: 'same-origin', cache: 'no-store' });
        if (res.status === 401) {
          iniciarSesion();
          throw new ApiError(401, 'Necesitas iniciar sesión en el CMS.');
        }
        if (!res.ok) throw new ApiError(res.status, 'No se pudo verificar tu sesión.');
        const session = await res.json();
        if (!session.user || session.user.role !== 'owner') {
          throw new ApiError(403, 'Tu cuenta no tiene acceso a la administración del Pasaporte.');
        }
        if (!session.csrf) throw new ApiError(403, 'No se pudo verificar tu sesión. Vuelve a entrar al CMS.');
        staffCsrf = session.csrf;
        return staffCsrf;
      })();
    }
    try { return await sessionRequest; } finally { sessionRequest = null; }
  }

  async function api(path, opts = {}) {
    const method = (opts.method || (opts.body ? 'POST' : 'GET')).toUpperCase();
    let res;
    try {
      const csrf = await staffSession();
      res = await fetch('/api/admin' + path, {
        method, cache: 'no-store', credentials: 'same-origin',
        headers: { Accept: 'application/json',
          ...(opts.body ? { 'Content-Type': 'application/json' } : {}),
          ...(!['GET', 'HEAD', 'OPTIONS'].includes(method) ? { 'X-CSRF-Token': csrf } : {}) },
        body: opts.body ? JSON.stringify(opts.body) : undefined,
      });
    } catch (e) {
      if (e instanceof ApiError) throw e;
      throw new ApiError(0, 'Sin conexión. Revisa el internet de la barra.');
    }
    let data = {};
    try { data = await res.json(); } catch (e) { /* sin JSON */ }
    if (res.status === 401) {
      iniciarSesion();
      throw new ApiError(401, 'Necesitas iniciar sesión.');
    }
    if (!res.ok) throw new ApiError(res.status, data.error || 'Algo salió mal. Inténtalo otra vez.');
    return data;
  }

  async function cerrarSesion() {
    const btn = $('#cerrar-sesion');
    if (btn) btn.disabled = true;
    try {
      const csrf = await staffSession();
      const res = await fetch('/cms/api/logout', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: { 'X-CSRF-Token': csrf, Accept: 'application/json' },
      });
      if (!res.ok && res.status !== 401) throw new Error('No se pudo cerrar la sesión. Inténtalo de nuevo.');
      iniciarSesion();
    } catch (ex) {
      if (ex.status !== 401) avisar(ex.message || 'No se pudo cerrar la sesión. Revisa tu conexión.');
    } finally { if (btn) btn.disabled = false; }
  }

  function avisar(texto) {
    const a = $('#aviso');
    a.textContent = texto || '';
    a.hidden = !texto;
  }
  let toastT;
  function anunciar(texto) {
    const t = $('#toast');
    t.textContent = texto;
    t.classList.add('toast--on');
    clearTimeout(toastT);
    toastT = setTimeout(() => t.classList.remove('toast--on'), 4500);
  }

  // ── Pestañas (hash en la URL) ──────────────────────────────────────────────
  function irA(tab, enfocar) {
    if (!TABS.includes(tab)) tab = 'hoy';
    st.tab = tab;
    TABS.forEach((t) => {
      const on = t === tab;
      const a = $('#tab-' + t);
      a.setAttribute('aria-selected', String(on));
      a.tabIndex = on ? 0 : -1;
      $('#panel-' + t).hidden = !on;
    });
    const activo = $('#tab-' + tab);
    const nav = activo.parentElement;
    if (activo.offsetLeft < nav.scrollLeft || activo.offsetLeft + activo.offsetWidth > nav.scrollLeft + nav.clientWidth) {
      nav.scrollTo({ left: activo.offsetLeft - 16 });
    }
    if (enfocar) activo.focus();
    cargarTab(tab);
  }
  function cargarTab(tab) {
    ({ hoy: cargarResumen, estadisticas: cargarEstadisticas, nps: cargarNps, miembros: cargarSocios, ranking: cargarRanking, ajustes: cargarAjustes })[tab]();
  }
  function iniciarTabs() {
    window.addEventListener('hashchange', () => irA(location.hash.slice(1)));
    $('.tabs__in').addEventListener('keydown', (e) => {
      const i = TABS.indexOf(st.tab);
      const destino = { ArrowRight: TABS[(i + 1) % TABS.length], ArrowLeft: TABS[(i - 1 + TABS.length) % TABS.length], Home: TABS[0], End: TABS[TABS.length - 1] }[e.key];
      if (!destino) return;
      e.preventDefault();
      history.replaceState(null, '', '#' + destino);
      irA(destino, true);
    });
    // Un clic en la pestaña ya activa no dispara hashchange: recarga sus datos igual.
    TABS.forEach((t) => $('#tab-' + t).addEventListener('click', () => { if (st.tab === t) cargarTab(t); }));
    irA(location.hash.slice(1) || 'hoy');
  }

  // ── HOY: código del día + canje + métricas ─────────────────────────────────
  function metrica(k, v, s, mod, href) {
    return h(href ? 'a' : 'div', { class: 'metrica' + (mod ? ' metrica--' + mod : ''), href },
      h('p', { class: 'metrica__k', text: k }),
      h('p', { class: 'metrica__v', text: v }),
      s && h('p', { class: 'metrica__s', text: s }));
  }

  async function cargarResumen() {
    const box = $('#metricas');
    box.setAttribute('aria-busy', 'true');
    try {
      const r = await api('/resumen?dias=30');
      avisar('');
      $('#codigo').textContent = r.codigo_del_dia;
      $('#codigo').setAttribute('aria-label', 'Código del día: ' + String(r.codigo_del_dia).split('').join(' '));
      const f = new Date(r.fecha + 'T12:00:00-06:00');
      $('#codigo-fecha').textContent = f.toLocaleDateString('es-MX', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: TZ });

      const nps = r.nps || {};
      const rec = r.recompensas || {};
      const emitidas = Object.values(rec).reduce((a, b) => a + b, 0);
      const canjeadas = rec.canjeada || 0;
      box.replaceChildren(
        metrica('Socios', num(r.socios), `${pl(r.socios_nuevos, 'nuevo', 'nuevos')} en 30 días`),
        metrica('Visitas hoy', num(r.visitas_hoy), `${pl(r.visitas, 'visita', 'visitas')} en 30 días`),
        metrica('NPS', npsTxt(nps.score),
          nps.respuestas ? `${pl(nps.promotores, 'promotor', 'promotores')} · ${pl(nps.pasivos, 'pasivo', 'pasivos')} · ${pl(nps.detractores, 'detractor', 'detractores')}` : 'Aún no hay respuestas', 'nps'),
        metrica('Clics a reseña', num(r.clicks_resena), 'Clientes que abrieron Google después del NPS'),
        metrica('Cortesías', `${num(canjeadas)}/${num(emitidas)}`, `${pl(canjeadas, 'canjeada', 'canjeadas')} de ${pl(emitidas, 'emitida', 'emitidas')}`),
        metrica('Por recuperar', num(r.por_recuperar), 'Detractores sin resolver · ver en NPS', r.por_recuperar > 0 ? 'alerta' : null, '#nps'));
      const rec2 = box.lastElementChild;
      rec2.addEventListener('click', () => { st.npsFiltro = 'pendientes'; st.npsPagina = 1; });
    } catch (ex) {
      if (ex.status !== 401) box.replaceChildren(h('p', { class: 'fine', text: ex.message }));
    } finally {
      box.setAttribute('aria-busy', 'false');
    }
  }

  async function canjear(e) {
    e.preventDefault();
    const inp = $('#canje-codigo');
    const out = $('#canje-res');
    let codigo = inp.value.trim().toUpperCase().replace(/\s+/g, '');
    if (codigo && !codigo.startsWith('CN-')) codigo = 'CN-' + codigo.replace(/^CN/, '');
    out.className = 'resultado';
    out.replaceChildren();
    if (!/^CN-[A-Z0-9]{5}$/.test(codigo)) {
      out.classList.add('resultado--error');
      out.textContent = 'El código tiene la forma CN-XXXXX (5 letras o números).';
      inp.focus();
      return;
    }
    const btn = $('#canje button');
    btn.disabled = true;
    try {
      const r = await api('/canjear', { body: { codigo } });
      out.classList.add('resultado--ok');
      out.append(h('p', { class: 'resultado__t', text: '✓ Canjeada' }),
        h('p', null, h('b', { text: r.socio }), ' · ' + r.nombre + ' · ', h('span', { class: 'mono', text: codigo })));
      inp.value = '';
      cargarResumen();
    } catch (ex) {
      out.classList.add('resultado--error');
      out.textContent = '✗ ' + ex.message;
    } finally {
      btn.disabled = false;
      inp.focus();
    }
  }

  // ── ESTADÍSTICAS ───────────────────────────────────────────────────────────
  // Colores de las gráficas (validados con dataviz/validate_palette.js sobre --carbon #191714):
  // una serie = ámbar del neón; NPS divergente = pico (detractor) · gris neutro (pasivo) · lúpulo (promotor).
  const COL = { serie: '#F2C97D', det: '#FF5A1F', pas: '#8A8378', pro: '#B7C46A', grid: '#2B2823', base: '#4A453D', eje: '#A39B8E', texto: '#F3EDE2', fondo: '#191714' };
  const SVGNS = 'http://www.w3.org/2000/svg';
  function s(tag, attrs, ...kids) {
    const n = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v != null) n.setAttribute(k, v);
    kids.flat().forEach((k) => k && n.append(k.nodeType ? k : document.createTextNode(String(k))));
    return n;
  }
  const ro = new ResizeObserver((entries) => entries.forEach((en) => en.target._render && en.target._render()));

  function kpi(k, v, sub, desc, mod) {
    return h('div', { class: 'kpi' + (mod ? ' kpi--' + mod : '') },
      h('p', { class: 'kpi__k', text: k }),
      h('p', { class: 'kpi__v', text: v }),
      sub && h('p', { class: 'kpi__s', text: sub }),
      h('p', { class: 'kpi__d', text: desc }));
  }

  function pintarKpis(k) {
    $('#kpis').replaceChildren(
      kpi('Socios', num(k.socios), null, 'Personas con Pasaporte en total.'),
      kpi('Activos 30 días', num(k.socios_activos_30d), k.socios ? `${pct(Math.round(k.socios_activos_30d * 100 / k.socios))} de los socios` : null, 'Socios con al menos una visita en los últimos 30 días.'),
      kpi('Visitas por socio', k.visitas_por_socio == null ? '—' : k.visitas_por_socio.toLocaleString('es-MX'), `${pl(k.visitas_totales, 'visita registrada', 'visitas registradas')}`, 'Promedio de visitas de quienes ya vinieron al menos una vez.'),
      kpi('Retención', pct(k.retencion_pct), null, 'De los socios que ya vinieron, cuántos regresaron una segunda vez o más.'),
      kpi('NPS', npsTxt(k.nps), k.nps_promedio == null ? 'Sin respuestas' : `Promedio ${k.nps_promedio.toLocaleString('es-MX')} de 10`, '% de promotores (9–10) menos % de detractores (0–6). Va de −100 a +100.', 'nps'),
      kpi('Respuesta NPS', pct(k.tasa_respuesta_nps_pct), null, 'De las visitas registradas, cuántas contestaron la encuesta.'),
      kpi('Clic a reseña', pct(k.tasa_resena_pct), pl(k.clicks_resena, 'clic', 'clics'), 'De quienes contestaron el NPS, cuántos abrieron Google para reseñar.'),
      kpi('Canje de cortesías', pct(k.tasa_canje_pct), `${num(k.cortesias_canjeadas)} canjeadas de ${num(k.cortesias_emitidas)} emitidas`, 'Cortesías que sí se cobraron en la barra, de todas las que ganaron los socios.'),
      kpi('Opt-in WhatsApp', pct(k.optin_whatsapp_pct), null, 'Socios que aceptaron recibir avisos por WhatsApp.'));
  }

  async function cargarEstadisticas() {
    const cont = $('#panel-estadisticas');
    cont.classList.add('recargando');
    $$('[data-semanas]').forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.semanas) === st.semanas)));
    try {
      const r = await api('/estadisticas?semanas=' + st.semanas);
      avisar('');
      st.stats = r;
      pintarKpis(r.kpis || {});
      pintarGraficas(r);
    } catch (ex) {
      if (ex.status !== 401) $('#kpis').replaceChildren(h('p', { class: 'fine', text: ex.message }));
    } finally {
      cont.classList.remove('recargando');
      $('#kpis').setAttribute('aria-busy', 'false');
    }
  }

  /** Figura: título, gráfica (SVG) con tooltip, leyenda opcional y "Ver datos en tabla". */
  function figura({ titulo, sub, leyenda, columnas, filas }) {
    const lienzo = h('div', { class: 'graf__lienzo' });
    const tip = h('div', { class: 'graf__tip', role: 'status', 'aria-live': 'polite', hidden: true });
    lienzo.append(tip);
    const tabla = h('table', { class: 'graf__t' },
      h('caption', { class: 'sr-only', text: titulo }),
      h('thead', null, h('tr', null, columnas.map((c, i) => h('th', { scope: 'col', class: i ? 'num' : null, text: c })))),
      h('tbody', null, filas.map((f) => h('tr', null, f.map((c, i) => (i ? h('td', { class: 'num', text: c }) : h('th', { scope: 'row', text: c })))))));
    const fig = h('figure', { class: 'graf' },
      h('figcaption', null, h('h3', { class: 'graf__h', text: titulo }), sub && h('p', { class: 'graf__s', text: sub })),
      leyenda && h('ul', { class: 'graf__ley' }, leyenda.map(([color, txt]) => h('li', null, h('span', { class: 'graf__sw', style: 'background:' + color }), txt))),
      lienzo,
      h('details', { class: 'graf__tabla' }, h('summary', { text: 'Ver datos en tabla' }), h('div', { class: 'tabla-wrap' }, tabla)));
    return { fig, lienzo, tip };
  }

  function escalaNice(max) {
    if (max <= 0) return { top: 4, paso: 1 };
    const bruto = max / 4;
    const mag = 10 ** Math.floor(Math.log10(bruto));
    const paso = [1, 2, 5, 10].map((m) => m * mag).find((p) => p >= bruto) || 10 * mag;
    const pasoEntero = Math.max(1, Math.round(paso));
    return { top: Math.ceil(max / pasoEntero) * pasoEntero, paso: pasoEntero };
  }

  function barraPath(x, y, w, alto, base) {
    const r = Math.min(4, alto, w / 2);
    return `M${x},${base}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${base}Z`;
  }

  /** Mueve el tooltip junto al punto (x,y en px dentro del lienzo). */
  function ponerTip(lienzo, tip, x, y, valor, etiqueta) {
    tip.replaceChildren(h('b', { text: valor }), h('span', { text: etiqueta }));
    tip.hidden = false;
    const w = lienzo.clientWidth;
    const tw = tip.offsetWidth;
    tip.style.left = Math.max(0, Math.min(w - tw, x - tw / 2)) + 'px';
    tip.style.top = Math.max(0, y - tip.offsetHeight - 10) + 'px';
  }

  /**
   * Gráfica de columnas o de línea (un solo eje). datos: [{x, v, color?, tip:[valor, etiqueta]}]
   * opts: tipo 'columnas'|'linea', alto, dominio [min,max] (línea), ticks, cadaX (etiquetas), resaltar (índices con valor
   * a la vista), grupos (llaves bajo el eje: [[desde, hasta, texto]]), vacio (texto si no hay datos), aria.
   */
  function grafica(lienzo, tip, datos, opts) {
    let activo = null;
    const render = () => {
      const W = Math.max(260, lienzo.clientWidth);
      const H = opts.alto || 200;
      const m = { t: 22, r: 12, b: opts.grupos ? 50 : 28, l: 38 };
      const pw = W - m.l - m.r; const ph = H - m.t - m.b;
      const n = datos.length; const banda = pw / n;
      const linea = opts.tipo === 'linea';
      let min = 0; let max; let ticks;
      if (opts.dominio) { [min, max] = opts.dominio; ticks = opts.ticks; } else {
        const e = escalaNice(Math.max(0, ...datos.map((d) => d.v || 0)));
        max = e.top; ticks = []; for (let t = 0; t <= max; t += e.paso) ticks.push(t);
      }
      const y = (v) => m.t + ph - ((v - min) / (max - min)) * ph;
      const cx = (i) => m.l + banda * i + banda / 2;
      const svg = s('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': opts.aria, tabindex: '0', class: 'graf__svg' });

      // Rejilla horizontal (hairline sólida) + etiquetas del eje Y
      ticks.forEach((t) => {
        svg.append(s('line', { x1: m.l, x2: W - m.r, y1: y(t), y2: y(t), stroke: t === 0 ? COL.base : COL.grid, 'stroke-width': 1, 'shape-rendering': 'crispEdges' }));
        svg.append(s('text', { x: m.l - 8, y: y(t) + 4, 'text-anchor': 'end', class: 'graf__eje' }, opts.fmtEje ? opts.fmtEje(t) : num(t)));
      });
      // Etiquetas del eje X (saltando para que no choquen)
      const cada = opts.cadaX || Math.max(1, Math.ceil(n * 44 / pw));
      datos.forEach((d, i) => {
        if ((n - 1 - i) % cada === 0) svg.append(s('text', { x: cx(i), y: m.t + ph + 18, 'text-anchor': 'middle', class: 'graf__eje' }, d.x));
      });
      // Llaves de grupos (p. ej. Detractores 0–6 · Pasivos 7–8 · Promotores 9–10)
      (opts.grupos || []).forEach(([a, b, largo, color, corto]) => {
        const x1 = m.l + banda * a + 3; const x2 = m.l + banda * (b + 1) - 3; const yy = m.t + ph + 28;
        const txt = largo.length * 6.6 > x2 - x1 + 6 && corto ? corto : largo;   // si no cabe, la versión corta
        svg.append(s('path', { d: `M${x1},${yy - 4}V${yy}H${x2}V${yy - 4}`, stroke: color, 'stroke-width': 2, fill: 'none' }));
        svg.append(s('text', { x: (x1 + x2) / 2, y: yy + 15, 'text-anchor': 'middle', class: 'graf__grupo' }, txt));
      });

      const capaMarcas = s('g');
      const capaActiva = s('g');
      svg.append(capaActiva, capaMarcas);
      const bw = Math.max(3, Math.min(24, banda * 0.62));
      if (!linea) {
        datos.forEach((d, i) => {
          if (!d.v) return;
          const yy = y(d.v);
          capaMarcas.append(s('path', { d: barraPath(cx(i) - bw / 2, yy, bw, y(0) - yy, y(0)), fill: d.color || COL.serie, class: 'graf__barra', 'data-i': i }));
        });
      } else {
        // Línea de 2 px con huecos donde no hay dato
        let tramo = [];
        const tramos = [];
        datos.forEach((d, i) => { if (d.v == null) { if (tramo.length) tramos.push(tramo); tramo = []; } else tramo.push(i); });
        if (tramo.length) tramos.push(tramo);
        tramos.forEach((t) => {
          if (t.length > 1) capaMarcas.append(s('path', { d: t.map((i, k) => `${k ? 'L' : 'M'}${cx(i)},${y(datos[i].v)}`).join(''), fill: 'none', stroke: COL.serie, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
        });
        const ultimo = [...datos.keys()].reverse().find((i) => datos[i].v != null);
        datos.forEach((d, i) => {
          if (d.v == null) return;
          const aislado = (i === 0 || datos[i - 1].v == null) && (i === n - 1 || datos[i + 1].v == null);
          if (aislado || i === ultimo) capaMarcas.append(s('circle', { cx: cx(i), cy: y(d.v), r: 4, fill: COL.serie, stroke: COL.fondo, 'stroke-width': 2 }));
        });
      }
      // Etiquetas directas selectivas (el máximo y/o el último)
      (opts.resaltar || []).forEach((i) => {
        const d = datos[i];
        if (!d || d.v == null || (!linea && !d.v)) return;
        const etiqueta = opts.fmtValor ? opts.fmtValor(d.v) : num(d.v);
        const xx = linea && i === n - 1 ? cx(i) - 8 : cx(i);
        svg.append(s('text', { x: xx, y: y(d.v) - 9, 'text-anchor': linea && i === n - 1 ? 'end' : 'middle', class: 'graf__valor' }, etiqueta));
      });
      if (opts.vacio && datos.every((d) => !d.v)) {
        svg.append(s('text', { x: m.l + pw / 2, y: m.t + ph / 2, 'text-anchor': 'middle', class: 'graf__vacio' }, opts.vacio));
      }

      // Capa de interacción: cada banda es zona de toque (más grande que la marca)
      const mostrar = (i) => {
        activo = i;
        capaActiva.replaceChildren();
        if (i == null) { tip.hidden = true; return; }
        const d = datos[i];
        if (linea) {
          capaActiva.append(s('line', { x1: cx(i), x2: cx(i), y1: m.t, y2: m.t + ph, stroke: COL.eje, 'stroke-width': 1 }));
          if (d.v != null) capaActiva.append(s('circle', { cx: cx(i), cy: y(d.v), r: 5, fill: COL.serie, stroke: COL.fondo, 'stroke-width': 2 }));
        } else {
          capaActiva.append(s('rect', { x: m.l + banda * i, y: m.t, width: banda, height: ph, fill: 'rgba(243,237,226,.06)' }));
        }
        const yTip = d.v != null && (linea || d.v) ? y(d.v) : y(0);
        ponerTip(lienzo, tip, cx(i), Math.min(yTip, m.t + ph - 10), d.tip[0], d.tip[1]);
      };
      for (let i = 0; i < n; i++) {
        svg.append(s('rect', { x: m.l + banda * i, y: m.t, width: banda, height: ph + 20, fill: 'transparent', 'data-i': i, class: 'graf__hit' }));
      }
      svg.addEventListener('pointermove', (e) => { const i = e.target.getAttribute && e.target.getAttribute('data-i'); if (i != null) mostrar(Number(i)); });
      svg.addEventListener('pointerleave', () => { if (document.activeElement !== svg) mostrar(null); });
      svg.addEventListener('focus', () => mostrar(activo == null ? n - 1 : activo));
      svg.addEventListener('blur', () => mostrar(null));
      svg.addEventListener('keydown', (e) => {
        const paso = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
        if (paso == null && e.key !== 'Home' && e.key !== 'End') return;
        e.preventDefault();
        const cur = activo == null ? n - 1 : activo;
        mostrar(e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : Math.max(0, Math.min(n - 1, cur + paso)));
      });
      lienzo.querySelector('svg') ? lienzo.querySelector('svg').replaceWith(svg) : lienzo.prepend(svg);
      if (activo != null && document.activeElement === svg) mostrar(activo);
    };
    lienzo._render = render;
    ro.observe(lienzo);
    render();
  }

  function pintarGraficas(r) {
    const sem = r.semanal || [];
    const etiquetaSemana = (w) => 'Semana del ' + diaCorto(w.semana);
    const ultimo = sem.length - 1;
    const maxI = (arr, k) => arr.reduce((b, d, i) => (d[k] > (arr[b] || {})[k] ? i : b), 0);
    const resaltar = (arr, k) => [...new Set([maxI(arr, k), ultimo])];
    const rango = sem.length ? `Del ${diaCorto(sem[0].semana)} a hoy, por semana (lunes a domingo).` : '';

    // 1) Visitas por semana
    const totV = sem.reduce((a, w) => a + w.visitas, 0);
    const f1 = figura({ titulo: 'Visitas por semana', sub: `${pl(totV, 'visita', 'visitas')} en ${st.semanas} semanas. ${rango}`,
      columnas: ['Semana del', 'Visitas'], filas: sem.map((w) => [diaCorto(w.semana), num(w.visitas)]) });
    // 2) Socios nuevos por semana (gráfica aparte: misma unidad pero escala muy distinta)
    const totS = sem.reduce((a, w) => a + w.socios_nuevos, 0);
    const f2 = figura({ titulo: 'Socios nuevos por semana', sub: `${pl(totS, 'alta', 'altas')} en ${st.semanas} semanas.`,
      columnas: ['Semana del', 'Socios nuevos'], filas: sem.map((w) => [diaCorto(w.semana), num(w.socios_nuevos)]) });
    // 3) NPS semanal (con huecos)
    const conNps = sem.filter((w) => w.nps != null);
    const f3 = figura({ titulo: 'NPS por semana', sub: conNps.length ? `De −100 a +100. Las semanas sin respuestas quedan en blanco.` : 'Aún no hay respuestas en este periodo.',
      columnas: ['Semana del', 'NPS', 'Respuestas'], filas: sem.map((w) => [diaCorto(w.semana), npsTxt(w.nps), num(w.nps_respuestas)]) });
    $('#graf-semanal').replaceChildren(f1.fig, f2.fig, f3.fig);
    grafica(f1.lienzo, f1.tip, sem.map((w) => ({ x: diaCorto(w.semana), v: w.visitas, tip: [pl(w.visitas, 'visita', 'visitas'), etiquetaSemana(w)] })),
      { resaltar: resaltar(sem, 'visitas'), vacio: 'Aún no hay visitas en estas semanas', aria: `Visitas por semana, últimas ${st.semanas} semanas. Total ${totV}. Usa las flechas para recorrer las semanas.` });
    grafica(f2.lienzo, f2.tip, sem.map((w) => ({ x: diaCorto(w.semana), v: w.socios_nuevos, tip: [pl(w.socios_nuevos, 'socio nuevo', 'socios nuevos'), etiquetaSemana(w)] })),
      { resaltar: resaltar(sem, 'socios_nuevos'), vacio: 'Aún no hay altas en estas semanas', aria: `Socios nuevos por semana, últimas ${st.semanas} semanas. Total ${totS}.` });
    const ultNps = [...sem.keys()].reverse().find((i) => sem[i].nps != null);
    grafica(f3.lienzo, f3.tip, sem.map((w) => ({ x: diaCorto(w.semana), v: w.nps, tip: [w.nps == null ? 'Sin respuestas' : 'NPS ' + npsTxt(w.nps), `${etiquetaSemana(w)} · ${pl(w.nps_respuestas, 'respuesta', 'respuestas')}`] })),
      { tipo: 'linea', dominio: [-100, 100], ticks: [-100, -50, 0, 50, 100], fmtEje: npsTxt, fmtValor: npsTxt, resaltar: ultNps == null ? [] : [ultNps], vacio: 'Aún no hay respuestas', aria: `NPS por semana, de menos 100 a más 100, últimas ${st.semanas} semanas.` });

    // 4) Distribución 0–10 (divergente: detractor · pasivo neutro · promotor)
    const dist = r.distribucion_nps || [];
    const totN = dist.reduce((a, d) => a + d.n, 0);
    const suma = (a, b) => dist.filter((d) => d.score >= a && d.score <= b).reduce((x, d) => x + d.n, 0);
    const colorDe = (sc) => (sc <= 6 ? COL.det : sc <= 8 ? COL.pas : COL.pro);
    const f4 = figura({
      titulo: 'Distribución de calificaciones', sub: `${pl(totN, 'respuesta', 'respuestas')} desde el inicio.`,
      leyenda: [[COL.det, `Detractores 0–6 · ${num(suma(0, 6))}`], [COL.pas, `Pasivos 7–8 · ${num(suma(7, 8))}`], [COL.pro, `Promotores 9–10 · ${num(suma(9, 10))}`]],
      columnas: ['Calificación', 'Respuestas', 'Tipo'], filas: dist.map((d) => [String(d.score), num(d.n), tipoScore(d.score)]),
    });
    // 5) Visitas por día de la semana
    const dias = r.visitas_por_dia || [];
    const totD = dias.reduce((a, d) => a + d.n, 0);
    const NOMBRE_DIA = { Lun: 'Lunes', Mar: 'Martes', 'Mié': 'Miércoles', Jue: 'Jueves', Vie: 'Viernes', 'Sáb': 'Sábado', Dom: 'Domingo' };
    const f5 = figura({ titulo: 'Visitas por día de la semana', sub: `${pl(totD, 'visita', 'visitas')} desde el inicio. El lunes está cerrado (día de producción).`,
      columnas: ['Día', 'Visitas'], filas: dias.map((d) => [NOMBRE_DIA[d.dia] || d.dia, num(d.n)]) });
    $('#graf-historico').replaceChildren(f4.fig, f5.fig);
    const maxDist = dist.reduce((b, d, i) => (d.n > dist[b].n ? i : b), 0);
    grafica(f4.lienzo, f4.tip, dist.map((d) => ({ x: String(d.score), v: d.n, color: colorDe(d.score), tip: [pl(d.n, 'respuesta', 'respuestas'), `Calificación ${d.score} · ${tipoScore(d.score)}`] })),
      { resaltar: totN ? [maxDist] : [], cadaX: 1, grupos: [[0, 6, 'Detractores', COL.det, 'Detract.'], [7, 8, 'Pasivos', COL.pas, '7–8'], [9, 10, 'Promotores', COL.pro, '9–10']], vacio: 'Aún no hay respuestas', aria: `Distribución de calificaciones NPS del 0 al 10. ${suma(0, 6)} detractores, ${suma(7, 8)} pasivos y ${suma(9, 10)} promotores.` });
    const maxDia = dias.reduce((b, d, i) => (d.n > dias[b].n ? i : b), 0);
    grafica(f5.lienzo, f5.tip, dias.map((d) => ({ x: d.dia, v: d.n, tip: [pl(d.n, 'visita', 'visitas'), NOMBRE_DIA[d.dia] || d.dia] })),
      { resaltar: totD ? [maxDia] : [], cadaX: 1, vacio: 'Aún no hay visitas', aria: `Visitas por día de la semana desde el inicio. El día con más visitas es ${NOMBRE_DIA[(dias[maxDia] || {}).dia] || '—'}.` });
  }

  // ── NPS (CRUD) ─────────────────────────────────────────────────────────────
  function chipScore(score) {
    return h('span', { class: 'score score--' + claseScore(score), title: tipoScore(score) },
      h('span', { 'aria-hidden': 'true', text: String(score) }), h('span', { class: 'sr-only', text: `${score} de 10, ${tipoScore(score).toLowerCase()}` }));
  }
  const waLink = (tel) => 'https://wa.me/52' + soloDigitos(tel);

  function filaNps(r) {
    const det = r.score <= 6;
    return h('tr', null,
      h('td', { 'data-k': 'Fecha' }, h('span', { class: 'mono nowrap', text: fecha(r.creado_at) }), r.origen === 'panel' && h('small', { class: 'sub', text: 'Capturado en papel' })),
      h('td', { 'data-k': 'Socio' },
        h('button', { type: 'button', class: 'linkbtn', text: r.nombre, onclick: () => abrirFicha(r.socio_id) }),
        h('small', { class: 'sub mono', text: telFmt(r.telefono) })),
      h('td', { 'data-k': 'Score' }, chipScore(r.score)),
      h('td', { 'data-k': 'Comentario', class: 'tabla__com' }, r.comentario ? '“' + r.comentario + '”' : h('span', { class: 'vacio-txt', text: 'Sin comentario' })),
      h('td', { 'data-k': 'Seguimiento' },
        h('span', { class: 'estado estado--' + r.seguimiento, text: SEGUIMIENTO[r.seguimiento] || r.seguimiento }),
        r.notas && h('small', { class: 'sub', text: r.notas })),
      h('td', { 'data-k': 'Acciones', class: 'tabla__acc' },
        h('button', { type: 'button', class: 'btn btn--ghost btn--xs', text: 'Editar', 'aria-label': `Editar respuesta de ${r.nombre}`, onclick: () => abrirNps('editar', r) }),
        det && r.telefono && h('a', { class: 'btn btn--wa btn--xs', href: waLink(r.telefono), target: '_blank', rel: 'noopener', 'aria-label': `WhatsApp a ${r.nombre} (se abre en otra pestaña)`, text: 'WhatsApp' }),
        h('button', { type: 'button', class: 'btn btn--borrar btn--xs', text: 'Borrar', 'aria-label': `Borrar respuesta de ${r.nombre}`, onclick: () => borrarNps(r) })));
  }

  function pager(nav, total, pagina, alCambiar, nombre) {
    const paginas = Math.max(1, Math.ceil(total / LIMITE));
    nav.replaceChildren();
    if (total <= LIMITE) return;
    nav.append(
      h('button', { type: 'button', class: 'btn btn--ghost btn--sm', text: '← Anterior', disabled: pagina <= 1, onclick: () => alCambiar(pagina - 1) }),
      h('span', { class: 'pager__txt mono', text: `Página ${pagina} de ${paginas}` }),
      h('button', { type: 'button', class: 'btn btn--ghost btn--sm', text: 'Siguiente →', disabled: pagina >= paginas, onclick: () => alCambiar(pagina + 1), 'aria-label': `Siguiente página de ${nombre}` }));
  }

  async function cargarNps() {
    $$('[data-nps-filtro]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.npsFiltro === st.npsFiltro)));
    $('#nps-ayuda').textContent = NPS_AYUDA[st.npsFiltro];
    const tbody = $('#nps-tabla tbody');
    const est = $('#nps-estado');
    $('#nps-tabla').classList.add('recargando');
    try {
      const q = new URLSearchParams({ filtro: st.npsFiltro, q: st.npsQ, pagina: st.npsPagina, limite: LIMITE });
      const r = await api('/nps?' + q);
      avisar('');
      const rows = r.respuestas || [];
      if (!rows.length && st.npsPagina > 1) { st.npsPagina -= 1; return cargarNps(); }
      tbody.replaceChildren(...(rows.length ? rows.map(filaNps)
        : [h('tr', { class: 'tabla__vacia' }, h('td', { colspan: 6, text: st.npsQ ? 'Nada coincide con la búsqueda.' : st.npsFiltro === 'pendientes' ? 'Nada pendiente. ¡Bien!' : 'Aún no hay respuestas.' }))]));
      est.textContent = `${pl(r.total, 'respuesta', 'respuestas')}${st.npsQ ? ' con «' + st.npsQ + '»' : ''}.`;
      pager($('#nps-pager'), r.total, st.npsPagina, (p) => { st.npsPagina = p; cargarNps().then(() => $('#t-nps').scrollIntoView({ block: 'start' })); }, 'respuestas');
    } catch (ex) {
      est.textContent = ex.message;
    } finally { $('#nps-tabla').classList.remove('recargando'); }
    return null;
  }

  async function borrarNps(r) {
    const ok = await confirmar({ titulo: '¿Borrar esta respuesta?', texto: `Se borra el NPS de ${r.nombre} (${r.score}/10, ${fecha(r.creado_at)}). No se puede deshacer.`, boton: 'Borrar respuesta' });
    if (!ok) return;
    try {
      await api('/nps/' + r.id, { method: 'DELETE' });
      anunciar('Respuesta borrada.');
      cargarNps();
      if (st.fichaId) recargarFicha();
    } catch (ex) { anunciar('No se borró: ' + ex.message); }
  }

  // Modal capturar / editar NPS
  function construirModalNps() {
    $('#dn-scores').replaceChildren(...Array.from({ length: 11 }, (_, i) => h('label', { class: 'escala__op escala__op--' + claseScore(i) },
      h('input', { type: 'radio', name: 'dn-score', value: i }), h('span', { text: String(i) }))));
    $('#dn-seg').replaceChildren(...Object.entries(SEGUIMIENTO).map(([v, t]) => h('option', { value: v, text: t })));
    const d = $('#dlg-nps');
    $$('[data-cerrar]', d).forEach((b) => b.addEventListener('click', () => d.close()));
    d.addEventListener('close', () => { if (st.dn.volverA) st.dn.volverA.focus(); });
    $('#dn-buscar').addEventListener('input', debounce(buscarSocioNps, 250));
    $('#dn-resultados').addEventListener('change', (e) => { if (e.target.name === 'dn-socio') st.dn.socioId = Number(e.target.value); });
    $('#dn-form').addEventListener('submit', guardarNps);
    $('#dn-borrar').addEventListener('click', async () => {
      const r = st.dn.fila;
      d.close();
      await borrarNps(r);
    });
  }

  function abrirNps(modo, r, socio) {
    const d = $('#dlg-nps');
    st.dn = { modo, id: r ? r.id : null, socioId: socio ? socio.id : r ? r.socio_id : null, fila: r, volverA: document.activeElement };
    const crear = modo === 'crear';
    $('#dn-t').textContent = crear ? 'Capturar NPS en papel' : 'Editar respuesta NPS';
    $('#dn-buscador').hidden = !crear || !!socio;
    $('#dn-socio').hidden = crear && !socio;
    $('#dn-socio').textContent = crear ? (socio ? `${socio.nombre} · ${telFmt(socio.telefono)}` : '')
      : `${r.nombre} · ${fecha(r.creado_at)}${r.origen === 'panel' ? ' · capturado en papel' : ''}`;
    $('#dn-ayuda').hidden = !crear;
    $('#dn-borrar').hidden = crear;
    $('#dn-err').textContent = '';
    $('#dn-buscar').value = '';
    $('#dn-resultados').replaceChildren();
    $('#dn-resultados-box').hidden = true;
    $('#dn-buscar-estado').textContent = '';
    $$('input[name="dn-score"]').forEach((i) => { i.checked = !crear && Number(i.value) === r.score; });
    $('#dn-comentario').value = crear ? '' : r.comentario || '';
    $('#dn-seg').value = crear ? 'nuevo' : r.seguimiento;
    $('#dn-notas').value = crear ? '' : r.notas || '';
    d.showModal();
    (crear && !socio ? $('#dn-buscar') : $('input[name="dn-score"]:checked') || $('input[name="dn-score"]')).focus();
  }

  async function buscarSocioNps() {
    const q = $('#dn-buscar').value.trim();
    const box = $('#dn-resultados');
    const est = $('#dn-buscar-estado');
    if (q.length < 2) { box.replaceChildren(); $('#dn-resultados-box').hidden = true; est.textContent = ''; return; }
    try {
      const r = await api('/socios?' + new URLSearchParams({ q, limite: 8, orden: 'nombre' }));
      const socios = r.socios || [];
      $('#dn-resultados-box').hidden = !socios.length;
      box.replaceChildren(...socios.map((s2) => h('label', { class: 'elige-socio__op' },
        h('input', { type: 'radio', name: 'dn-socio', value: s2.id, checked: st.dn.socioId === s2.id }),
        h('span', null, h('b', { text: s2.nombre }), h('small', { class: 'mono', text: ` ${telFmt(s2.telefono)} · ${pl(s2.visitas, 'visita', 'visitas')}` })))));
      est.textContent = socios.length ? `${pl(r.total, 'socio encontrado', 'socios encontrados')}${r.total > 8 ? '; se muestran 8, afina la búsqueda' : ''}.` : 'No hay socios con esa búsqueda. Dalo de alta en Miembros.';
      if (socios.length === 1) { box.querySelector('input').checked = true; st.dn.socioId = socios[0].id; }
    } catch (ex) { est.textContent = ex.message; }
  }

  async function guardarNps(e) {
    e.preventDefault();
    const errEl = $('#dn-err');
    errEl.textContent = '';
    const sel = $('input[name="dn-score"]:checked');
    if (st.dn.modo === 'crear' && !st.dn.socioId) { errEl.textContent = 'Elige al socio.'; $('#dn-buscar').focus(); return; }
    if (!sel) { errEl.textContent = 'Elige una calificación del 0 al 10.'; $('input[name="dn-score"]').focus(); return; }
    const body = { score: Number(sel.value), comentario: $('#dn-comentario').value.trim(), seguimiento: $('#dn-seg').value, notas: $('#dn-notas').value.trim() };
    // La ficha del socio no trae las notas de cada NPS: si no se conocen y quedaron vacías, no se tocan.
    if (st.dn.modo === 'editar' && st.dn.fila && st.dn.fila.notas === undefined && !body.notas) delete body.notas;
    const btn = $('#dn-guardar');
    btn.disabled = true;
    try {
      let res = null;
      if (st.dn.modo === 'crear') res = await api('/nps', { body: { ...body, socio_id: st.dn.socioId } });
      else await api('/nps/' + st.dn.id, { method: 'PUT', body });
      $('#dlg-nps').close();
      const rec = res && res.recompensa;
      anunciar(st.dn.modo === 'crear'
        ? (rec ? `NPS capturado y visita registrada. ¡Ganó una cortesía! ${rec.nombre}: ${rec.codigo}` : 'NPS capturado.')
        : 'Respuesta actualizada.');
      if (st.tab === 'nps') cargarNps();
      if (st.fichaId) recargarFicha();
    } catch (ex) {
      errEl.textContent = ex.message;
    } finally { btn.disabled = false; }
  }

  // ── MIEMBROS (CRUD) ────────────────────────────────────────────────────────
  function filaSocio(sc) {
    return h('tr', null,
      h('td', { 'data-k': 'Nombre' }, h('button', { type: 'button', class: 'linkbtn tabla__nombre', text: sc.nombre, onclick: () => abrirFicha(sc.id) })),
      h('td', { 'data-k': 'Teléfono', class: 'mono nowrap', text: telFmt(sc.telefono) }),
      h('td', { 'data-k': 'Visitas', class: 'num mono', text: num(sc.visitas) }),
      h('td', { 'data-k': 'Última visita', class: 'nowrap', text: sc.ultima_visita ? dia(sc.ultima_visita) : '—' }),
      h('td', { 'data-k': 'NPS prom.', class: 'num mono', text: sc.nps_promedio == null ? '—' : sc.nps_promedio.toLocaleString('es-MX') }),
      h('td', { 'data-k': 'Cortesías vigentes', class: 'num mono', text: num(sc.cortesias_vigentes) }),
      h('td', { 'data-k': 'Acciones', class: 'tabla__acc' }, h('button', { type: 'button', class: 'btn btn--ghost btn--xs', text: 'Abrir ficha', 'aria-label': `Abrir ficha de ${sc.nombre}`, onclick: () => abrirFicha(sc.id) })));
  }

  async function cargarSocios() {
    const tbody = $('#socios-tabla tbody');
    const est = $('#socios-estado');
    $('#socios-tabla').classList.add('recargando');
    try {
      const q = new URLSearchParams({ q: st.sociosQ, orden: st.sociosOrden, pagina: st.sociosPagina, limite: LIMITE });
      const r = await api('/socios?' + q);
      avisar('');
      const rows = r.socios || [];
      if (!rows.length && st.sociosPagina > 1) { st.sociosPagina -= 1; return cargarSocios(); }
      tbody.replaceChildren(...(rows.length ? rows.map(filaSocio)
        : [h('tr', { class: 'tabla__vacia' }, h('td', { colspan: 7, text: st.sociosQ ? 'Nadie coincide con la búsqueda.' : 'Aún no hay socios.' }))]));
      est.textContent = `${pl(r.total, 'socio', 'socios')}${st.sociosQ ? ' con «' + st.sociosQ + '»' : ''}.`;
      pager($('#socios-pager'), r.total, st.sociosPagina, (p) => { st.sociosPagina = p; cargarSocios().then(() => $('#t-socios').scrollIntoView({ block: 'start' })); }, 'miembros');
    } catch (ex) {
      est.textContent = ex.message;
    } finally { $('#socios-tabla').classList.remove('recargando'); }
    return null;
  }

  function mostrarPin(contenedor, titulo, pin) {
    contenedor.querySelector('.pin-once__k').textContent = titulo;
    contenedor.querySelector('.pin-once__v').textContent = pin;
    contenedor.querySelector('.pin-once__v').setAttribute('aria-label', 'PIN ' + String(pin).split('').join(' '));
    contenedor.hidden = false;
    contenedor.focus();
  }

  async function altaSocio(e) {
    e.preventDefault();
    const f = e.currentTarget;
    const errEl = $('#alta-err');
    errEl.textContent = '';
    const nombre = f.nombre.value.trim();
    const tel = soloDigitos(f.telefono.value).replace(/^52(?=\d{10}$)/, '');
    const pin = soloDigitos(f.pin.value);
    const checks = [
      [f.nombre, !nombre, 'Escribe el nombre.'],
      [f.telefono, tel.length !== 10, 'El teléfono debe tener 10 dígitos.'],
      [f.pin, pin && !/^\d{4}$/.test(pin), 'El PIN son 4 números (o déjalo vacío).'],
      [f.acepta_privacidad, !f.acepta_privacidad.checked, 'El cliente debe aceptar el aviso de privacidad.'],
    ];
    checks.forEach(([el, bad]) => (bad ? el.setAttribute('aria-invalid', 'true') : el.removeAttribute('aria-invalid')));
    const malo = checks.find(([, bad]) => bad);
    if (malo) { errEl.textContent = malo[2]; malo[0].focus(); return; }
    const btn = f.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      const r = await api('/socios', { body: { nombre, telefono: tel, pin: pin || undefined, acepta_privacidad: true, acepta_whatsapp: f.acepta_whatsapp.checked, mostrar_ranking: f.mostrar_ranking.checked } });
      f.reset();
      mostrarPin($('#alta-pin'), `PIN de ${nombre.split(' ')[0]}`, r.pin);
      anunciar(`${nombre} quedó dado de alta.`);
      st.sociosPagina = 1;
      cargarSocios();
    } catch (ex) {
      errEl.textContent = ex.message;
    } finally { btn.disabled = false; }
  }

  // ── Ficha del socio (drawer) ───────────────────────────────────────────────
  function fiMsg(t) { $('#fi-msg').textContent = t || ''; }
  function fiErr(t) { $('#fi-err').textContent = t || ''; }

  async function abrirFicha(id) {
    const d = $('#ficha');
    st.fichaId = id;
    st.fichaVolver = document.activeElement;
    fiMsg(''); fiErr('');
    $('#fi-t').textContent = 'Ficha del socio';
    $('#fi-contenido').replaceChildren(h('p', { class: 'fine', text: 'Cargando…' }));
    if (!d.open) d.showModal();
    $('#fi-t').focus();
    await recargarFicha();
  }

  async function recargarFicha() {
    try {
      const r = await api('/socios/' + st.fichaId);
      st.ficha = r;
      pintarFicha(r);
    } catch (ex) {
      fiErr(ex.message);
      if (ex.status === 404) $('#fi-contenido').replaceChildren();
    }
  }

  function seccion(titulo, ...kids) { return h('section', { class: 'fi-sec' }, h('h3', { class: 'fi-sec__h', text: titulo }), ...kids); }

  function pintarFicha(r) {
    const sc = r.socio;
    const rk = r.ranking || {};
    $('#fi-t').textContent = sc.nombre;
    const pinBox = h('div', { class: 'pin-once pin-once--papel', tabindex: '-1', hidden: true },
      h('p', { class: 'pin-once__k' }), h('p', { class: 'pin-once__v mono' }),
      h('p', { class: 'pin-once__i' }, 'Dáselo al cliente ahora: ', h('b', { text: 'no se volverá a mostrar' }), '.'),
      h('button', { type: 'button', class: 'btn btn--ink btn--sm', text: 'Listo, ya se lo di', onclick: (e) => { e.currentTarget.parentElement.hidden = true; } }));
    const premioBox = h('div', { class: 'premio', tabindex: '-1', hidden: true });

    // Resumen
    const resumen = h('dl', { class: 'fi-resumen' },
      h('div', null, h('dt', { text: 'Visitas' }), h('dd', { class: 'mono', text: num(sc.visitas) })),
      h('div', null, h('dt', { text: 'Última' }), h('dd', { text: sc.ultima_visita ? dia(sc.ultima_visita) : '—' })),
      h('div', null, h('dt', { text: 'NPS prom.' }), h('dd', { class: 'mono', text: sc.nps_promedio == null ? '—' : sc.nps_promedio.toLocaleString('es-MX') })),
      h('div', null, h('dt', { text: 'Ranking del mes' }), h('dd', { class: 'mono', text: rk.posicion ? `#${rk.posicion} de ${rk.participantes}` : 'Sin visitas' })));

    // Datos editables
    const form = h('form', { class: 'form', novalidate: true },
      h('div', { class: 'field' }, h('label', { for: 'fi-nombre', text: 'Nombre' }), h('input', { id: 'fi-nombre', name: 'nombre', maxlength: 60, required: true, autocomplete: 'off' })),
      h('div', { class: 'field' }, h('label', { for: 'fi-tel', text: 'Teléfono' }),
        h('input', { id: 'fi-tel', name: 'telefono', type: 'tel', inputmode: 'numeric', maxlength: 14, autocomplete: 'off', 'aria-describedby': 'fi-tel-h', class: 'mono' }),
        h('small', { id: 'fi-tel-h', text: 'Si cambias el teléfono se genera un PIN nuevo (el PIN va ligado al teléfono).' })),
      h('div', { class: 'field' }, h('label', { for: 'fi-notas', text: 'Notas del equipo' }), h('textarea', { id: 'fi-notas', name: 'notas', rows: 2, maxlength: 500 })),
      h('label', { class: 'check' }, h('input', { type: 'checkbox', name: 'acepta_whatsapp' }), h('span', { text: 'Acepta avisos por WhatsApp.' })),
      h('label', { class: 'check' }, h('input', { type: 'checkbox', name: 'mostrar_ranking' }), h('span', { text: 'Aparece en el ranking público (nombre e inicial).' })),
      h('button', { type: 'submit', class: 'btn btn--primary btn--sm', text: 'Guardar cambios' }));
    form.nombre.value = sc.nombre;
    form.telefono.value = sc.telefono;
    form.notas.value = sc.notas || '';
    form.acepta_whatsapp.checked = !!sc.acepta_whatsapp;
    form.mostrar_ranking.checked = !!sc.mostrar_ranking;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      fiErr(''); fiMsg('');
      const tel = soloDigitos(form.telefono.value).replace(/^52(?=\d{10}$)/, '');
      if (!form.nombre.value.trim()) { fiErr('El nombre no puede quedar vacío.'); form.nombre.focus(); return; }
      if (tel.length !== 10) { fiErr('El teléfono debe tener 10 dígitos.'); form.telefono.focus(); return; }
      const body = { nombre: form.nombre.value.trim(), notas: form.notas.value.trim(), acepta_whatsapp: form.acepta_whatsapp.checked, mostrar_ranking: form.mostrar_ranking.checked };
      if (tel !== sc.telefono) body.telefono = tel;
      const btn = form.querySelector('button[type=submit]');
      btn.disabled = true;
      try {
        const res = await api('/socios/' + sc.id, { method: 'PUT', body });
        await recargarFicha();
        fiMsg('Cambios guardados.');
        if (res.pin) { const b = $('#fi-contenido .pin-once'); mostrarPin(b, 'PIN nuevo (cambió el teléfono)', res.pin); }
        refrescarListas();
      } catch (ex) { fiErr(ex.message); } finally { btn.disabled = false; }
    });

    // Acciones
    const acciones = h('div', { class: 'fi-acciones' },
      h('button', { type: 'button', class: 'btn btn--primary btn--sm', text: 'Registrar visita de hoy', onclick: async (e) => {
        const btn = e.currentTarget; btn.disabled = true; fiErr(''); fiMsg('');
        try {
          const res = await api(`/socios/${sc.id}/visitas`, { body: {} });
          await recargarFicha();
          if (res.ya_registrada) fiMsg('Ya tenía su visita de hoy registrada.');
          else fiMsg('Visita de hoy registrada.');
          if (res.recompensa) {
            const p = $('#fi-contenido .premio');
            p.replaceChildren(h('p', { class: 'premio__k', text: '¡Ganó una cortesía!' }), h('p', { class: 'premio__nombre', text: res.recompensa.nombre }),
              h('p', { class: 'premio__codigo mono', text: res.recompensa.codigo }), h('p', { class: 'premio__vence', text: 'Vigente hasta el ' + dia(res.recompensa.vence_at) + '. Ya aparece en su Pasaporte.' }));
            p.hidden = false; p.focus();
          }
          refrescarListas();
        } catch (ex) { fiErr(ex.message); } finally { btn.disabled = false; }
      } }),
      h('button', { type: 'button', class: 'btn btn--ink btn--sm', text: 'Restablecer PIN', onclick: async () => {
        const ok = await confirmar({ titulo: '¿Restablecer el PIN?', texto: `Se genera un PIN nuevo para ${sc.nombre} y se cierran sus sesiones abiertas. Lo verás una sola vez.`, boton: 'Restablecer PIN', peligro: false });
        if (!ok) return;
        fiErr(''); fiMsg('');
        try {
          const res = await api('/socios/' + sc.id, { method: 'PUT', body: { reset_pin: true } });
          mostrarPin($('#fi-contenido .pin-once'), `PIN nuevo de ${sc.nombre.split(' ')[0]}`, res.pin);
        } catch (ex) { fiErr(ex.message); }
      } }),
      h('button', { type: 'button', class: 'btn btn--ink btn--sm', text: 'Capturar NPS', onclick: () => abrirNps('crear', null, sc) }));

    // Historiales
    const visitas = r.visitas.length
      ? h('ul', { class: 'fi-lista' }, r.visitas.map((v) => h('li', null,
        h('span', null, h('b', { text: dia(v.dia) }), h('small', { text: v.origen === 'panel' ? ' · registrada en el panel' : ' · desde el menú' })),
        h('button', { type: 'button', class: 'btn btn--borrar-papel btn--xs', text: 'Borrar', 'aria-label': `Borrar visita del ${dia(v.dia)}`, onclick: async () => {
          const ok = await confirmar({ titulo: '¿Borrar esta visita?', texto: `Visita del ${dia(v.dia)}. También se borran su NPS y la cortesía que haya generado (si no se canjeó). No se puede deshacer.`, boton: 'Borrar visita' });
          if (!ok) return;
          fiErr(''); fiMsg('');
          try { await api('/visitas/' + v.id, { method: 'DELETE' }); await recargarFicha(); fiMsg('Visita borrada.'); refrescarListas(); } catch (ex) { fiErr(ex.message); }
        } }))))
      : h('p', { class: 'fine', text: 'Sin visitas todavía.' });
    const ESTADO_C = { emitida: 'Vigente', canjeada: 'Canjeada' };
    const ahora = new Date().toISOString();
    const cortesias = r.recompensas.length
      ? h('ul', { class: 'fi-lista' }, r.recompensas.map((c) => {
        const vencida = c.estado === 'emitida' && new Date(c.vence_at).toISOString() < ahora;
        return h('li', null, h('span', null, h('b', { class: 'mono', text: c.codigo }), ' ', c.nombre.replace(/ de cortesía$/, ''),
          h('small', { class: 'sub', text: c.estado === 'canjeada' ? `Canjeada el ${dia(c.canjeada_at)}` : `${vencida ? 'Venció' : 'Vence'} el ${dia(c.vence_at)}` })),
        h('span', { class: 'estado estado--' + (vencida ? 'cerrado' : c.estado === 'canjeada' ? 'resuelto' : 'nuevo'), text: vencida ? 'Vencida' : ESTADO_C[c.estado] || c.estado }));
      }))
      : h('p', { class: 'fine', text: 'Aún no ha ganado cortesías.' });
    const nps = r.nps.length
      ? h('ul', { class: 'fi-lista' }, r.nps.map((n) => h('li', null,
        h('span', { class: 'fi-nps' }, chipScore(n.score), h('span', null, n.comentario ? '“' + n.comentario + '”' : h('i', { text: 'Sin comentario' }), h('small', { class: 'sub', text: `${fecha(n.creado_at)} · ${SEGUIMIENTO[n.seguimiento] || n.seguimiento}` }))),
        h('button', { type: 'button', class: 'btn btn--ink btn--xs', text: 'Editar', 'aria-label': `Editar NPS del ${fecha(n.creado_at)}`, onclick: () => abrirNps('editar', { ...n, nombre: sc.nombre, telefono: sc.telefono, socio_id: sc.id }) }))))
      : h('p', { class: 'fine', text: 'No ha contestado el NPS.' });

    // Borrado (ARCO)
    const borrar = h('section', { class: 'fi-sec fi-peligro' },
      h('h3', { class: 'fi-sec__h', text: 'Borrar socio' }),
      h('p', { text: 'Borra para siempre al socio con sus visitas, cortesías y respuestas NPS. Es irreversible. Úsalo cuando el cliente lo pida (derechos ARCO: cancelación de sus datos personales).' }),
      h('button', { type: 'button', class: 'btn btn--peligro btn--sm', text: 'Borrar socio…', onclick: async () => {
        const ok = await confirmar({ titulo: `¿Borrar a ${sc.nombre}?`, texto: 'Se borran sus datos, visitas, cortesías y NPS. No se puede deshacer.', boton: 'Borrar para siempre', escribir: sc.nombre });
        if (!ok) return;
        try {
          await api('/socios/' + sc.id, { method: 'DELETE' });
          $('#ficha').close();
          anunciar(`${sc.nombre} fue borrado.`);
          refrescarListas();
        } catch (ex) { fiErr(ex.message); }
      } }));

    $('#fi-contenido').replaceChildren(pinBox, premioBox, resumen, seccion('Acciones', acciones), seccion('Datos', form),
      seccion(`Visitas (${r.visitas.length})`, visitas), seccion('Cortesías', cortesias), seccion('NPS', nps), borrar);
  }

  function refrescarListas() {
    if (st.tab === 'miembros') cargarSocios();
    else if (st.tab === 'nps') cargarNps();
    else if (st.tab === 'ranking') cargarRanking();
    else if (st.tab === 'hoy') cargarResumen();
  }

  // ── Confirmación (con "escribe el nombre" para lo irreversible) ───────────
  function confirmar({ titulo, texto, boton = 'Borrar', escribir = null, peligro = true }) {
    const d = $('#confirmar');
    const volver = document.activeElement;
    $('#cf-t').textContent = titulo;
    $('#cf-p').textContent = texto;
    const si = $('#cf-si');
    si.textContent = boton;
    si.className = 'btn btn--sm ' + (peligro ? 'btn--peligro' : 'btn--primary');
    const caja = $('#cf-escribir');
    const inp = $('#cf-input');
    caja.hidden = !escribir;
    inp.value = '';
    if (escribir) $('#cf-label').textContent = `Para confirmar escribe: ${escribir}`;
    const coincide = () => !escribir || inp.value.trim().toLowerCase() === escribir.trim().toLowerCase();
    si.disabled = !coincide();
    inp.oninput = () => { si.disabled = !coincide(); };
    return new Promise((resolve) => {
      let respuesta = false;
      const fin = () => { d.removeEventListener('close', fin); resolve(respuesta); if (volver && volver.isConnected) volver.focus(); };
      d.addEventListener('close', fin);
      $('#cf-no').onclick = () => d.close();
      $('#cf-form').onsubmit = (e) => { e.preventDefault(); if (!coincide()) return; respuesta = true; d.close(); };
      d.showModal();
      (escribir ? inp : $('#cf-no')).focus();
    });
  }

  // ── RANKING ────────────────────────────────────────────────────────────────
  async function cargarRanking() {
    $$('[data-rank]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.rank === st.rankPeriodo)));
    const tbody = $('#rank-tabla tbody');
    const est = $('#rank-estado');
    $('#rank-tabla').classList.add('recargando');
    try {
      const r = await api('/ranking?' + new URLSearchParams({ periodo: st.rankPeriodo, limite: 100 }));
      avisar('');
      const filas = r.ranking || [];
      tbody.replaceChildren(...(filas.length ? filas.map((f) => h('tr', { class: f.posicion <= 3 ? 'tabla__podio' : null },
        h('td', { 'data-k': 'Lugar', class: 'num' }, h('span', { class: 'lugar lugar--' + Math.min(f.posicion, 4), text: '#' + f.posicion })),
        h('td', { 'data-k': 'Nombre' }, h('button', { type: 'button', class: 'linkbtn tabla__nombre', text: f.nombre, onclick: () => abrirFicha(f.socio_id) })),
        h('td', { 'data-k': 'Visitas', class: 'num mono', text: num(f.visitas) }),
        h('td', { 'data-k': 'Acciones', class: 'tabla__acc' }, h('button', { type: 'button', class: 'btn btn--ghost btn--xs', text: 'Ver ficha', 'aria-label': `Ver ficha de ${f.nombre}`, onclick: () => abrirFicha(f.socio_id) }))))
        : [h('tr', { class: 'tabla__vacia' }, h('td', { colspan: 4, text: `Nadie ha registrado visitas ${PERIODO_TXT[st.rankPeriodo]}.` }))]));
      est.textContent = filas.length ? `${pl(filas.length, 'socio', 'socios')} con visitas ${PERIODO_TXT[st.rankPeriodo]}.` : '';
    } catch (ex) {
      est.textContent = ex.message;
    } finally { $('#rank-tabla').classList.remove('recargando'); }
  }

  // ── AJUSTES: Wi-Fi del menú ────────────────────────────────────────────────
  const WIFI_PASS_AYUDA = {
    WPA: 'WPA/WPA2: de 8 a 63 caracteres.',
    WEP: 'WEP: 5 o 13 caracteres de texto, o 10 o 26 hexadecimales.',
    nopass: 'Las redes abiertas no llevan contraseña.',
  };
  const WIFI_SEG_TXT = { WPA: 'WPA/WPA2', WEP: 'WEP', nopass: 'Abierta' };
  const WIFI_VIS_TXT = {
    publica: 'Pública: el menú muestra este QR a cualquiera.',
    socios: 'Solo socios: el menú lo muestra a quien entra con su Pasaporte.',
    oculta: 'Oculta: este QR no aparece en el menú.',
  };
  const WIFI_CAMPOS = { ssid: 'w-ssid', password: 'w-pass', seguridad: 'w-seg', visibilidad: 'w-vis' };

  /** Cadena estándar para que la cámara se conecte sola: WIFI:T:WPA;S:red;P:clave;; */
  const wifiEsc = (t) => String(t).replace(/([\\;,:"])/g, '\\$1');
  function wifiCadena({ ssid, password, seguridad }) {
    return `WIFI:T:${seguridad};S:${wifiEsc(ssid)};${seguridad === 'nopass' ? '' : `P:${wifiEsc(password)};`};`;
  }

  /** QR en SVG (negro sobre crema), construido con nodos: nada de innerHTML. */
  function qrSvg(texto) {
    if (typeof qrcode !== 'function') return null;
    if (qrcode.stringToBytesFuncs && qrcode.stringToBytesFuncs['UTF-8']) qrcode.stringToBytes = qrcode.stringToBytesFuncs['UTF-8'];
    const qr = qrcode(0, 'M');
    qr.addData(texto, 'Byte');
    qr.make();
    const n = qr.getModuleCount();
    const margen = 4;   // zona silenciosa estándar de 4 módulos
    const lado = n + margen * 2;
    let d = '';
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) d += `M${c + margen},${r + margen}h1v1h-1z`;
    return s('svg', { viewBox: `0 0 ${lado} ${lado}`, class: 'wifi__qr-svg', 'shape-rendering': 'crispEdges', 'aria-hidden': 'true', focusable: 'false' },
      s('rect', { width: lado, height: lado, fill: '#F3EDE2' }),
      s('path', { d, fill: '#0E0D0B' }));
  }

  function wifiForm() {
    const f = $('#wifi-form');
    return {
      ssid: f.ssid.value.trim(),
      password: f.seguridad.value === 'nopass' ? '' : f.password.value,
      seguridad: f.seguridad.value,
      visibilidad: (f.querySelector('input[name="visibilidad"]:checked') || {}).value || 'publica',
    };
  }

  function wifiPintarQr() {
    const w = wifiForm();
    const lienzo = $('#wifi-qr');
    const red = $('#wifi-qr-red');
    let svg = null;
    if (w.ssid) { try { svg = qrSvg(wifiCadena(w)); } catch (e) { svg = null; } }
    if (svg) {
      lienzo.replaceChildren(svg);
      lienzo.setAttribute('role', 'img');
      lienzo.setAttribute('aria-label', `Código QR para conectarse a la red ${w.ssid}, ${w.seguridad === 'nopass' ? 'abierta, sin contraseña' : 'seguridad ' + WIFI_SEG_TXT[w.seguridad]}.`);
      red.replaceChildren(h('b', { text: w.ssid }), h('span', { text: w.seguridad === 'nopass' ? 'Abierta, sin contraseña' : WIFI_SEG_TXT[w.seguridad] }));
    } else {
      lienzo.removeAttribute('role');
      lienzo.removeAttribute('aria-label');
      lienzo.replaceChildren(h('p', { class: 'wifi__qr-vacio', text: w.ssid ? 'No se pudo dibujar el QR.' : 'Escribe el nombre de la red para ver el QR.' }));
      red.replaceChildren();
    }
    $('#wifi-qr-vis').textContent = WIFI_VIS_TXT[w.visibilidad] || '';
    $('.wifi__qr').classList.toggle('wifi__qr--oculta', w.visibilidad === 'oculta');
  }

  function wifiSeguridad() {
    const f = $('#wifi-form');
    const abierta = f.seguridad.value === 'nopass';
    const pass = f.password;
    if (abierta && !pass.disabled) {
      st.wifiPassPrevio = pass.value;   // por si regresa a WPA/WEP sin guardar
      pass.value = '';
    } else if (!abierta && pass.disabled && !pass.value) {
      pass.value = st.wifiPassPrevio;
    }
    pass.disabled = abierta;
    pass.placeholder = abierta ? 'Sin contraseña' : '';
    $('#w-ver').disabled = abierta;
    pass.maxLength = f.seguridad.value === 'WEP' ? 26 : 63;
    $('#w-pass-h').textContent = WIFI_PASS_AYUDA[f.seguridad.value] || '';
  }

  function wifiVer(mostrar) {
    $('#w-pass').type = mostrar ? 'text' : 'password';
    $('#w-ver').setAttribute('aria-pressed', String(mostrar));
    $('#w-ver').textContent = mostrar ? 'Ocultar' : 'Mostrar';
  }

  function wifiLimpiarErrores() {
    Object.values(WIFI_CAMPOS).forEach((id) => {
      $('#' + id + '-err').textContent = '';
      const campo = $('#' + id);
      if (campo) campo.removeAttribute('aria-invalid');
    });
    $$('#wifi-form input[name="visibilidad"]').forEach((i) => i.removeAttribute('aria-invalid'));
    $('#wifi-err').textContent = '';
    $('#wifi-vivo').textContent = '';
  }

  /** Pone el mensaje del servidor junto al campo que corresponde (o abajo, si es general). */
  function wifiError(msg) {
    wifiLimpiarErrores();
    const campo = /nombre de la red/i.test(msg) ? 'ssid' : /contraseña/i.test(msg) ? 'password'
      : /seguridad/i.test(msg) ? 'seguridad' : /visibilidad/i.test(msg) ? 'visibilidad' : null;
    if (!campo) { $('#wifi-err').textContent = msg; return; }
    const id = WIFI_CAMPOS[campo];
    $('#' + id + '-err').textContent = msg;
    $('#wifi-vivo').textContent = msg;
    const el = campo === 'visibilidad' ? $('#wifi-form input[name="visibilidad"]:checked') : $('#' + id);
    if (campo === 'visibilidad') $$('#wifi-form input[name="visibilidad"]').forEach((i) => i.setAttribute('aria-invalid', 'true'));
    else el.setAttribute('aria-invalid', 'true');
    if (el && !el.disabled) el.focus();
  }

  function wifiActualizado(w) {
    $('#wifi-actualizado').textContent = 'Última actualización: ' + (w.actualizado_at
      ? new Date(w.actualizado_at).toLocaleString('es-MX', { dateStyle: 'long', timeStyle: 'short', timeZone: TZ })
      : 'Nunca');
    $('#wifi-ejemplo').hidden = !w.ejemplo;
  }

  function wifiLlenar(w) {
    const f = $('#wifi-form');
    st.wifi = w;
    st.wifiSucio = false;
    st.wifiPassPrevio = '';
    f.ssid.value = w.ssid || '';
    f.seguridad.value = w.seguridad || 'WPA';
    f.password.disabled = false;
    f.password.value = w.password || '';
    $$('input[name="visibilidad"]', f).forEach((i) => { i.checked = i.value === (w.visibilidad || 'publica'); });
    wifiVer(false);
    wifiSeguridad();
    wifiLimpiarErrores();
    wifiActualizado(w);
    wifiPintarQr();
  }

  async function cargarAjustes(forzar) {
    const box = $('#wifi');
    // Si hay cambios sin guardar y solo se volvió a la pestaña, no se pisan.
    if (st.wifi && st.wifiSucio && forzar !== true) { wifiPintarQr(); return; }
    box.setAttribute('aria-busy', 'true');
    try {
      const r = await api('/ajustes');
      avisar('');
      wifiLlenar(r.wifi || {});
    } catch (ex) {
      if (ex.status !== 401) $('#wifi-err').textContent = ex.message;
    } finally {
      box.setAttribute('aria-busy', 'false');
    }
  }

  async function guardarAjustes(e) {
    e.preventDefault();
    wifiLimpiarErrores();
    const btn = $('#w-guardar');
    btn.disabled = true;
    try {
      const r = await api('/ajustes', { method: 'PUT', body: { wifi: wifiForm() } });
      wifiLlenar(r.wifi);
      anunciar(r.wifi.visibilidad === 'oculta' ? 'Wi-Fi guardado. Está oculto en el menú.'
        : r.wifi.visibilidad === 'socios' ? 'Wi-Fi guardado. Lo verán los socios del Pasaporte.'
          : 'Wi-Fi guardado. Ya aparece en el menú.');
    } catch (ex) {
      if (ex.status !== 401) wifiError(ex.message);
    } finally { btn.disabled = false; }
  }

  function iniciarAjustes() {
    const f = $('#wifi-form');
    const cambio = () => { st.wifiSucio = true; wifiPintarQr(); };
    f.addEventListener('submit', guardarAjustes);
    f.ssid.addEventListener('input', () => { f.ssid.removeAttribute('aria-invalid'); $('#w-ssid-err').textContent = ''; cambio(); });
    f.password.addEventListener('input', () => { f.password.removeAttribute('aria-invalid'); $('#w-pass-err').textContent = ''; cambio(); });
    f.seguridad.addEventListener('change', () => { wifiSeguridad(); $('#w-pass-err').textContent = ''; f.password.removeAttribute('aria-invalid'); cambio(); });
    $$('input[name="visibilidad"]', f).forEach((i) => i.addEventListener('change', cambio));
    $('#w-ver').addEventListener('click', () => wifiVer($('#w-ver').getAttribute('aria-pressed') !== 'true'));
    wifiSeguridad();
  }

  // ── Arranque ───────────────────────────────────────────────────────────────
  function init() {
    $('.mbar__in').append(h('button', { type: 'button', id: 'cerrar-sesion',
      class: 'btn btn--ghost btn--sm', text: 'Cerrar sesión', onclick: cerrarSesion }));
    $('#canje').addEventListener('submit', canjear);
    $('#canje-codigo').addEventListener('input', (e) => { e.target.value = e.target.value.toUpperCase(); });
    $('#actualizar').addEventListener('click', () => { if (st.tab === 'ajustes') cargarAjustes(true); else cargarTab(st.tab); if (st.fichaId && $('#ficha').open) recargarFicha(); anunciar('Datos actualizados.'); });

    $$('[data-semanas]').forEach((b) => b.addEventListener('click', () => { st.semanas = Number(b.dataset.semanas); cargarEstadisticas(); }));
    $$('[data-nps-filtro]').forEach((b) => b.addEventListener('click', () => { st.npsFiltro = b.dataset.npsFiltro; st.npsPagina = 1; cargarNps(); }));
    $('#nps-q').addEventListener('input', debounce((e) => { st.npsQ = e.target.value.trim(); st.npsPagina = 1; cargarNps(); }, 300));
    $('#nps-nuevo').addEventListener('click', () => abrirNps('crear'));
    construirModalNps();

    $('#alta').addEventListener('submit', altaSocio);
    $$('#alta input').forEach((i) => i.addEventListener('input', () => i.removeAttribute('aria-invalid')));
    $('#a-pin').addEventListener('input', (e) => { e.target.value = soloDigitos(e.target.value).slice(0, 4); });
    $('#alta-pin-ok').addEventListener('click', () => { $('#alta-pin').hidden = true; $('#a-nombre').focus(); });
    $('#socios-q').addEventListener('input', debounce((e) => { st.sociosQ = e.target.value.trim(); st.sociosPagina = 1; cargarSocios(); }, 300));
    $('#socios-orden').addEventListener('change', (e) => { st.sociosOrden = e.target.value; st.sociosPagina = 1; cargarSocios(); });

    $$('[data-rank]').forEach((b) => b.addEventListener('click', () => { st.rankPeriodo = b.dataset.rank; cargarRanking(); }));

    const ficha = $('#ficha');
    $$('[data-cerrar]', ficha).forEach((b) => b.addEventListener('click', () => ficha.close()));
    ficha.addEventListener('click', (e) => { if (e.target === ficha) ficha.close(); });
    ficha.addEventListener('close', () => { st.fichaId = null; if (st.fichaVolver && st.fichaVolver.isConnected) st.fichaVolver.focus(); });

    iniciarAjustes();
    iniciarTabs();
    // El código cambia a medianoche y las métricas se mueven durante el servicio.
    setInterval(() => { if (!document.hidden && st.tab === 'hoy') cargarResumen(); }, 60000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
