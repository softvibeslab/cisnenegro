/* Cervecería Cisne Negro · Menú digital, Pasaporte Cisne y NPS
 * - Catálogo desde /data/menu.json (fuente única; no se inventan datos).
 * - Maridaje en ambos sentidos: barril → "Va perfecto con…", platillo → "Pídelo con…".
 * - Filtro por perfil (barril + latas) y constructor del Vuelo del Cisne.
 * - Pasaporte (registro, entrada, check-in con código del día, cortesías), ranking y NPS contra /api.
 *
 * Sesión (v2): la cookie HttpOnly `cn_sesion` (180 días) que pone el servidor es la fuente de verdad.
 * El localStorage solo guarda una caché del último `socio` para pintar al instante; Safari puede
 * borrarlo a los 7 días sin que eso cierre la sesión. Solo un 401 o "Salir" terminan la sesión;
 * un error de red o 5xx conserva el estado, muestra un aviso y reintenta.
 */
(() => {
  'use strict';

  const DATA_URL = document.body.dataset.menuUrl || '/data/menu.json';
  const CMS_PREVIEW = document.body.dataset.cmsPreview === 'true';
  // Pausa temporal de las opciones del menú; conserva cuentas y configuración.
  const WIFI_VISIBLE = document.body.dataset.wifi !== 'false';
  const PASAPORTE_VISIBLE = document.body.dataset.pasaporte !== 'false';
  const PEDIDO_QR_VISIBLE = document.body.dataset.pedidoQr !== 'false';
  const TOKEN_KEY = 'cisne.pasaporte.token';       // v1: token Bearer (se conserva como respaldo de la cookie)
  const CACHE_KEY = 'cisne.pasaporte.socio';       // v2: {dia, socio} del último /api/yo
  const SALIR_KEY = 'cisne.pasaporte.salir';       // "Salir" sin red: se completa en la siguiente carga
  const PERIODOS = { semana: 'esta semana', mes: 'este mes', total: 'en total' };
  const PRIMERO = { semana: 'Sé el primero de la semana: registra tu visita.', mes: 'Sé el primero del mes: registra tu visita.', total: 'Sé el primero: registra tu visita.' };
  // Después del NPS se invita a Google a TODOS, sin premio (las políticas de Google prohíben incentivar
  // reseñas o pedirlas solo a quien califica alto). [titular, texto, botón] según el `tono` del servidor.
  const RESENA = {
    promotor: ['¡Gracias!', '¿Nos ayudas contándolo en Google?', 'Contarlo en Google'],
    pasivo: ['Gracias', 'Si quieres, cuéntanos tu experiencia en Google.', 'Contar mi experiencia en Google'],
    detractor: ['Gracias por decírnoslo', 'El equipo lo va a revisar. También puedes dejar tu opinión en Google.', 'Dejar mi opinión en Google'],
  };
  const tonoDe = (score) => (score >= 9 ? 'promotor' : score >= 7 ? 'pasivo' : 'detractor');
  const PERFILES = ['lupulada', 'oscura', 'acida', 'ligera'];
  const PERFIL_LABEL = { lupulada: 'Lupulada', oscura: 'Oscura', acida: 'Ácida', ligera: 'Ligera' };
  const ASK = '¿Por qué se llama así? Pregúntale a tu bartender.';
  const VUELO_N = 4;
  const PREMIOS = { 5: '4 oz', 10: '12 oz' };   // casillas premiadas del Pasaporte (ver club_server.RECOMPENSAS)
  const VER = '?v=20261007b';                     // versión de caché de los assets (ver /sw.js)
  const INSTALAR_KEY = 'cisne.instalar.descartado'; // "Ahora no" en la invitación a instalar (30 días)
  const INSTALADA_KEY = 'cisne.instalar.hecho';      // "Ya la instalé" (iOS/Safari no avisan cuando se instala)
  const INSTALAR_PAUSA = 30 * 24 * 60 * 60 * 1000;
  const P = window.CisnePedido;                   // funciones puras de "Mi pedido" (assets/js/pedido.js)

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const state = {
    data: null, dishes: {}, filtro: null, vuelo: [],
    token: safeGet(TOKEN_KEY), socio: null, visitaId: null, npsScore: null,
    comprobando: false, sinRed: false, reintento: null, espera: 0,
    periodo: 'mes', ranking: {}, tab: 'pase',
    pedido: null, wakeLock: null, avisoT: null, qr: null, qrT: null,
    wifi: null, wifiEstado: 'cargando', wifiTrasLogin: false, configPidiendo: 0,
    promptInstalar: null, instalada: false,
  };

  // La invitación nativa a instalar llega en cualquier momento (Android y Chrome/Edge de escritorio).
  if (!CMS_PREVIEW && PASAPORTE_VISIBLE) {
    window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); state.promptInstalar = e; if (document.readyState !== 'loading') pintarInstalar(); });
    window.addEventListener('appinstalled', () => { state.promptInstalar = null; state.instalada = true; pintarInstalar(); });
  }

  // ── Utilidades ─────────────────────────────────────────────────────────────
  function safeGet(k) { if (CMS_PREVIEW) return null; try { return localStorage.getItem(k); } catch (e) { return null; } }
  function safeSet(k, v) { if (CMS_PREVIEW) return; try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) { /* modo privado */ } }

  /** Crea un elemento. attrs: class, text, html no se usa (todo es textContent). */
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
    if (tag === 'img') applyMediaFocal(n, attrs && attrs.src);
    return n;
  }
  function svgUse(id, cls) {
    const ns = 'http://www.w3.org/2000/svg';
    const s = document.createElementNS(ns, 'svg');
    s.setAttribute('aria-hidden', 'true'); s.setAttribute('focusable', 'false');
    s.setAttribute('viewBox', '0 0 24 48');
    if (cls) s.setAttribute('class', cls);
    const u = document.createElementNS(ns, 'use');
    u.setAttribute('href', '#' + id);
    s.append(u);
    return s;
  }
  function checkSvg() {
    const ns = 'http://www.w3.org/2000/svg';
    const s = document.createElementNS(ns, 'svg');
    s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('aria-hidden', 'true'); s.setAttribute('focusable', 'false');
    const p = document.createElementNS(ns, 'path');
    p.setAttribute('d', 'M5 12.5l4.2 4.2L19 7'); p.setAttribute('fill', 'none'); p.setAttribute('stroke', 'currentColor');
    p.setAttribute('stroke-width', '3'); p.setAttribute('stroke-linecap', 'round'); p.setAttribute('stroke-linejoin', 'round');
    s.append(p);
    return s;
  }
  const money = (n) => '$' + Number(n).toLocaleString('es-MX');
  const abv = (n) => Number(n).toFixed(1) + '% ABV';
  const precio4oz = (b) => (b.precios || []).find((p) => /^4\s*oz$/i.test(p.medida));
  const fechaLarga = (iso) => new Date(iso).toLocaleDateString('es-MX', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'America/Mexico_City' });
  const soloDigitos = (s) => String(s || '').replace(/\D/g, '');
  const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Las hamburguesas y sándwiches se llaman "De X" en el menú; fuera de su sección necesitan contexto.
  // Misma regla que la landing (assets/js/landing.js).
  function dishLabel(item) {
    if (item.nombre_completo) return item.nombre_completo;
    if (/^De /.test(item.nombre) && item.id === 'hamburguesa-suadero') return 'Sándwich de ' + item.nombre.slice(3);
    if (/^De /.test(item.nombre) && /^hamburguesa-/.test(item.id || '')) return 'Hamburguesa de ' + item.nombre.slice(3);
    return item.nombre;
  }

  function mediaUrl(value, group) {
    if (!value) return '';
    if (/^(?:\/assets\/|\/cms\/media\/[A-Za-z0-9_-]+\/file(?:[?#]|$)|https:\/\/)/.test(value)) return value;
    if (/^[A-Za-z0-9_./-]+$/.test(value) && !value.split('/').includes('..')) return '/assets/img/' + group + '/' + value;
    return '';
  }

  function applyMediaFocal(node, url) {
    const key = String(url || '').split(/[?#]/)[0];
    const point = state.data && state.data._media_focal && state.data._media_focal[key];
    if (!/^\/cms\/media\/[A-Za-z0-9_-]+\/file$/.test(key) || !point ||
        !['x', 'y'].every(axis => typeof point[axis] === 'number' && Number.isFinite(point[axis]) && point[axis] >= 0 && point[axis] <= 1)) return;
    node.style.objectPosition = (point.x * 100) + '% ' + (point.y * 100) + '%';
  }

  const cmsKey = (item, fallback, suffix) => CMS_PREVIEW ? (item._cms_key || fallback) + '.' + suffix : null;

  // ── Catálogo ───────────────────────────────────────────────────────────────
  async function cargarMenu() {
    const res = await fetch(DATA_URL, { cache: 'no-cache' });
    if (!res.ok) throw new Error('menu ' + res.status);
    return res.json();
  }

  function renderBarril() {
    const { barril, perfiles } = state.data;
    const lista = $('#lista-barril');
    lista.replaceChildren();
    barril.forEach((b, i) => {
      const pairs = (b.marida_con || []).map((id) => state.dishes[id]).filter(Boolean);
      const oficial = b.marida_oficial || [];
      const card = h('article', { class: 'tap', id: 'barril-' + b.id, 'data-perfil': b.perfil, 'aria-labelledby': 'tn-' + b.id, 'data-cms-key': cmsKey(b, 'menu.barril.' + i, 'nombre') },
        b.img && h('figure', { class: 'tap__fig' },
          h('img', { class: 'tap__img', src: mediaUrl(b.img, 'cervezas'), 'data-cms-key': cmsKey(b, 'menu.barril.' + i, 'img'), alt: (b.etiqueta ? 'Diseño de ' + b.nombre + ' inspirado en su etiqueta' : 'Ilustración de ' + b.nombre) + ' (' + b.estilo + '), servida en el vaso de Cisne Negro', width: 900, height: 900, loading: i < 2 ? 'eager' : 'lazy', decoding: 'async' })),
        h('div', { class: 'tap__top' },
          h('span', { class: 'tap__num', text: String(i + 1).padStart(2, '0') }),
          b.etiqueta && h('button', { type: 'button', class: 'tap__etq', 'data-etiqueta': b.etiqueta, 'data-nombre': b.nombre },
            h('img', { src: mediaUrl(b.etiqueta, 'cervezas'), alt: '', width: 44, height: 44, loading: 'lazy', decoding: 'async' }),
            h('span', { text: 'Ver etiqueta' })),
          b.perfil && h('span', { class: 'chip chip--' + b.perfil }, h('span', { class: 'dot dot--' + b.perfil }), PERFIL_LABEL[b.perfil] || b.perfil)),
        h('h3', { class: 'tap__name', id: 'tn-' + b.id, text: b.nombre }),
        h('p', { class: 'tap__meta', text: [b.estilo, abv(b.abv), b.ibu && b.ibu + ' IBU'].filter(Boolean).join(' · ') }),
        b.cerveceria && h('p', { class: 'tap__guest', text: 'Invitada de ' + b.cerveceria }),
        b.notas && h('p', { class: 'tap__notes', text: b.notas }),
        b.perfil && perfiles[b.perfil] && h('p', { class: 'tap__profile', text: 'Perfil: ' + perfiles[b.perfil] }),
        (b.historia || '').trim()
          ? h('p', { class: 'tap__story', text: b.historia.trim() })
          : h('p', { class: 'tap__story tap__story--ask', text: ASK }),
        b.disponible === false
          ? h('div', { class: 'tap__agotado' },
            h('ul', { class: 'tap__prices', 'aria-label': 'Precios' },
              (b.precios || []).map((p) => h('li', null, h('span', { text: p.medida }), h('b', { text: money(p.precio) })))),
            h('p', { class: 'agotado', text: 'Agotado por hoy' }))
          : pedirUI('barril', b.id, b.nombre, (b.precios || []).map((p) => ({ valor: p.medida, etiqueta: p.medida, precio: p.precio })), 'tap__pedir'),
        pairs.length > 0 && h('div', { class: 'marida' },
          h('p', { class: 'marida__t', text: 'Va perfecto con…' }),
          h('ul', { class: 'marida__lista' }, pairs.map((d) => h('li', null,
            h('a', { class: 'mini', href: '#plato-' + d.id },
              d.img && h('img', { src: mediaUrl(d.img, 'menu'), alt: '', width: 112, height: 112, loading: 'lazy', decoding: 'async' }),
              h('span', { class: 'mini__n' }, dishLabel(d), oficial.includes(d.id) && h('span', { class: 'mini__casa', text: 'De la casa' })),
              h('span', { class: 'mini__p', text: money(d.precio) })))))));
      lista.append(card);
    });
    lista.append(h('p', { class: 'vacio', id: 'barril-vacio', hidden: true }));
  }

  function renderFiltros() {
    const { perfiles } = state.data;
    $$('[data-filtro]').forEach((box) => {
      box.replaceChildren(
        h('div', { class: 'filtro__chips' },
          h('button', { type: 'button', class: 'filtro__btn', 'data-perfil-btn': '', 'aria-pressed': 'true', text: 'Todas' }),
          PERFILES.filter((p) => perfiles[p]).map((p) => h('button', {
            type: 'button', class: 'filtro__btn', 'data-perfil-btn': p, 'aria-pressed': 'false',
          }, h('span', { class: 'dot dot--' + p }), PERFIL_LABEL[p]))),
        h('p', { class: 'filtro__desc', 'aria-live': 'polite' }));
    });
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-perfil-btn]');
      if (!btn) return;
      const p = btn.getAttribute('data-perfil-btn') || null;
      aplicarFiltro(state.filtro === p ? null : p);
    });
    aplicarFiltro(null, true);
  }

  function aplicarFiltro(perfil, silencioso) {
    state.filtro = perfil;
    const { perfiles } = state.data;
    $$('[data-perfil-btn]').forEach((b) => b.setAttribute('aria-pressed', String((b.getAttribute('data-perfil-btn') || null) === perfil)));
    let nB = 0; let nL = 0;
    $$('#lista-barril .tap').forEach((c) => { const ok = !perfil || c.dataset.perfil === perfil; c.hidden = !ok; if (ok) nB++; });
    $$('#lista-latas .row').forEach((r) => { const ok = !perfil || r.dataset.perfil === perfil; r.hidden = !ok; if (ok) nL++; });
    $$('#lista-latas .grupo').forEach((g) => { g.hidden = !!perfil && g.dataset.perfil !== perfil; });
    const vacio = $('#barril-vacio');
    vacio.hidden = nB > 0;
    vacio.textContent = perfil ? `Hoy no hay ${PERFIL_LABEL[perfil].toLowerCase()} en barril. Mira las latas o pregunta en la barra.` : '';
    $$('.filtro__desc').forEach((d) => {
      d.replaceChildren();
      if (!perfil) { d.textContent = 'Toca un perfil para filtrar el barril y las latas.'; return; }
      d.append(h('b', { text: PERFIL_LABEL[perfil] + ': ' }), perfiles[perfil] + '. ',
        `${nB} de barril · ${nL} en lata o botella.`);
    });
    if (!silencioso) { /* aria-live de .filtro__desc ya anuncia el cambio */ }
  }

  function renderLatas() {
    const { latas, perfiles } = state.data;
    const cont = $('#lista-latas');
    cont.replaceChildren();
    const orden = [...PERFILES, ...new Set(latas.map((l) => l.perfil).filter((p) => !PERFILES.includes(p)))];
    orden.forEach((p) => {
      const items = latas.filter((l) => (l.perfil || 'otras') === p);
      if (!items.length) return;
      cont.append(h('div', { class: 'grupo', 'data-perfil': p },
        h('div', { class: 'grupo__h' },
          h('h3', null, h('span', { class: 'dot dot--' + p }), PERFIL_LABEL[p] || p),
          perfiles[p] && h('p', { text: perfiles[p] })),
        h('ul', { class: 'rows' }, items.map((l) => filaPedible('lata', l, p,
          h('div', null,
            h('span', { class: 'row__n', text: l.nombre }),
            h('span', { class: 'row__e', text: [l.estilo, abv(l.abv)].filter(Boolean).join(' · ') }),
            h('span', { class: 'row__o', text: [l.cerveceria, l.origen, l.detalle].filter(Boolean).join(' · ') })))))));
    });
  }

  /** Opciones de variante de un producto (Chips de Camote 55 g / 110 g, agua mineral natural / rusa). */
  function opcionesDe(prod) {
    if (!Array.isArray(prod.variantes) || !prod.variantes.length) return null;
    return prod.variantes.filter((v) => v.disponible !== false).map((v) => ({
      valor: v.id, etiqueta: v.nombre, precio: typeof v.precio === 'number' ? v.precio : prod.precio + (v.extra || 0),
    }));
  }

  /** Fila de lata o bebida: nombre a la izquierda; precio y "＋ Agregar" a la derecha.
   *  Con variantes, los chips (con su precio) y el botón ocupan una segunda línea. */
  function filaPedible(tipo, prod, perfil, info) {
    const ops = opcionesDe(prod);
    const agotado = prod.disponible === false;
    const group = tipo === 'lata' ? 'latas' : 'sin_alcohol';
    return h('li', { class: 'row' + (ops && !agotado ? ' row--var' : ''), 'data-perfil': perfil || null,
      'data-cms-key': cmsKey(prod, 'menu.' + group + '.' + state.data[group].indexOf(prod), 'nombre') },
      info,
      ops && !agotado
        ? pedirUI(tipo, prod.id, prod.nombre, ops, 'row__pedir')
        : h('div', { class: 'row__der' },
          h('span', { class: 'row__p', text: money(prod.precio) }),
          agotado ? h('span', { class: 'agotado', text: 'Agotado' }) : pedirUI(tipo, prod.id, prod.nombre, null, 'row__pedir row__pedir--solo')));
  }

  /** Selector de medida o variante (chips con su precio) + botón "＋ Agregar". */
  function pedirUI(tipo, id, nombre, opciones, clase) {
    const grupo = opciones && opciones.length > 0 && h('div', {
      class: 'opciones', role: 'group', 'aria-label': (tipo === 'barril' ? 'Medida de ' : 'Presentación de ') + nombre,
    }, opciones.map((o, j) => h('button', {
      type: 'button', class: 'opc-chip', 'data-opcion': o.valor, 'aria-pressed': String(j === 0),
    }, h('span', { class: 'opc-chip__t', text: o.etiqueta }), h('b', { class: 'opc-chip__p', text: money(o.precio) }))));
    return h('div', { class: 'pedir ' + (clase || '') },
      grupo,
      h('button', {
        type: 'button', class: 'btn btn--sm agregar', 'data-agregar': tipo, 'data-id': id,
        'aria-label': 'Agregar ' + nombre + ' a tu pedido',
      }, h('span', { 'aria-hidden': 'true', text: '＋' }), 'Agregar'));
  }

  function renderComida() {
    const { comida, barril } = state.data;
    const cont = $('#lista-comida');
    cont.replaceChildren();
    comida.forEach((sec, si) => {
      const hid = 'sec-comida-' + si;
      cont.append(h('section', { class: 'seccion', 'aria-labelledby': hid },
        h('h3', { class: 'seccion__h', id: hid, text: sec.seccion }),
        h('ul', { class: 'platos' }, (sec.items || []).map((d) => {
          const con = barril.filter((b) => (b.marida_con || []).includes(d.id));
          return h('li', { class: 'plato', id: 'plato-' + d.id, 'data-cms-key': cmsKey(d, 'menu.comida.' + si + '.items.' + sec.items.indexOf(d), 'nombre') },
            d.img
              ? h('img', { class: 'plato__img', src: mediaUrl(d.img, 'menu'), 'data-cms-key': cmsKey(d, 'menu.comida.' + si + '.items.' + sec.items.indexOf(d), 'img'), alt: 'Foto del platillo ' + dishLabel(d), width: 400, height: 400, loading: 'lazy', decoding: 'async' })
              : h('span', { class: 'plato__img', 'aria-hidden': 'true' }),
            h('div', { class: 'plato__body' },
              h('div', { class: 'plato__top' },
                h('h4', { class: 'plato__n', text: d.nombre }),
                h('span', { class: 'plato__p', text: money(d.precio) })),
              d.descripcion && h('p', { class: 'plato__d', text: d.descripcion }),
              d.disponible === false && h('p', { class: 'plato__agotado agotado', text: 'Agotado por hoy' }),
              d.disponible !== false && !opcionesDe(d) && pedirUI('comida', d.id, dishLabel(d), null, 'plato__pedir plato__pedir--solo')),
            d.disponible !== false && opcionesDe(d) && pedirUI('comida', d.id, dishLabel(d), opcionesDe(d), 'plato__pedir'),
            con.length > 0 && h('p', { class: 'pidelo' },
              h('span', { class: 'pidelo__t', text: 'Pídelo con…' }),
              con.map((b) => h('a', { href: '#barril-' + b.id, 'data-barril': b.id },
                b.img ? h('img', { class: 'pidelo__img', src: mediaUrl(b.img, 'cervezas'), alt: '', width: 32, height: 32, loading: 'lazy', decoding: 'async' })
                  : h('span', { class: 'dot dot--' + b.perfil }), b.nombre))));
        }))));
    });
  }

  function renderSinAlcohol() {
    $('#lista-sin').replaceChildren(...state.data.sin_alcohol.map((s) => filaPedible('bebida', s, null,
      h('div', null, h('span', { class: 'row__n', text: s.nombre }), s.detalle && h('span', { class: 'row__o', text: s.detalle })))));
  }

  function renderPie() {
    const n = state.data.negocio;
    $('#horario tbody').replaceChildren(...(n.horario || []).map((r) => h('tr', { class: /cerrado/i.test(r.horas) ? 'off' : null },
      h('th', { scope: 'row', text: r.dias }), h('td', { text: r.horas }))));
    $('#direccion').textContent = n.direccion || '';
    const wa = $('#pie-wa'); if (n.whatsapp_url) wa.href = n.whatsapp_url; else wa.hidden = true;
    const mapa = $('#pie-mapa'); if (n.google_maps_url) mapa.href = n.google_maps_url; else mapa.hidden = true;
  }

  // Si un ancla apunta a una cerveza oculta por el filtro, quita el filtro antes de saltar.
  function anclasMaridaje() {
    document.addEventListener('click', (e) => {
      const a = e.target.closest('a[href^="#barril-"], a[href^="#plato-"]');
      if (!a) return;
      const dest = document.getElementById(a.getAttribute('href').slice(1));
      if (dest && dest.hidden) aplicarFiltro(null);
    });
  }

  // Pestañas pegajosas: resalta la sección visible.
  function scrollSpy() {
    const links = $$('.tabs a').filter((a) => !a.hidden && !a.closest('li').hidden);
    const byId = Object.fromEntries(links.map((a) => [a.getAttribute('href').slice(1), a]));
    const visibles = new Map();
    const marcar = (id) => {
      links.forEach((a) => a.removeAttribute('aria-current'));
      const a = byId[id]; if (!a) return;
      a.setAttribute('aria-current', 'true');
      const nav = a.closest('.tabs__in');
      const left = a.offsetLeft - 16;
      if (left < nav.scrollLeft || a.offsetLeft + a.offsetWidth > nav.scrollLeft + nav.clientWidth) {
        nav.scrollTo({ left, behavior: reduceMotion() ? 'auto' : 'smooth' });
      }
    };
    let fijoHasta = 0;   // tras tocar una pestaña, respeta la elección mientras dura el desplazamiento
    const ids = Object.keys(byId);
    const actualizar = () => {
      if (Date.now() < fijoHasta) return;
      const alFondo = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
      const id = alFondo ? ids[ids.length - 1] : ids.find((x) => visibles.get(x));
      if (id) marcar(id);
    };
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => visibles.set(en.target.id, en.isIntersecting));
      actualizar();
    }, { rootMargin: '-120px 0px -55% 0px' });
    window.addEventListener('scroll', () => { if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) actualizar(); }, { passive: true });
    links.forEach((a) => a.addEventListener('click', () => { marcar(a.getAttribute('href').slice(1)); fijoHasta = Date.now() + 1200; }));
    Object.keys(byId).forEach((id) => { const s = document.getElementById(id); if (s) io.observe(s); });
  }

  // ── Vuelo del Cisne ────────────────────────────────────────────────────────
  function renderVuelo() {
    const v = state.data.vuelo || {};
    $$('.tabs a[href="#vuelo"]').forEach((a) => {
      a.hidden = v.visible === false;
      a.closest('li').hidden = v.visible === false;
    });
    $('#t-vuelo').textContent = v.nombre || 'Vuelo del Cisne';
    $('#vuelo-desc').textContent = v.descripcion || '';
    $('#vuelo-nota').textContent = v.nota || '';
    const opciones = state.data.barril.filter(precio4oz);
    $('#vuelo-opciones').replaceChildren(...opciones.map((b) => h('li', null,
      h('button', { type: 'button', class: 'opcion', 'data-vuelo': b.id, 'aria-pressed': 'false' },
        h('span', { class: 'opcion__box' }, checkSvg()),
        h('span', null, h('span', { class: 'opcion__n', text: b.nombre }), h('span', { class: 'opcion__e', text: [b.estilo, abv(b.abv)].join(' · ') })),
        h('span', { class: 'opcion__p', text: money(precio4oz(b).precio) })))));

    $('#vuelo-opciones').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-vuelo]');
      if (!btn || btn.disabled) return;
      const id = btn.dataset.vuelo;
      const i = state.vuelo.indexOf(id);
      if (i >= 0) state.vuelo.splice(i, 1);
      else if (state.vuelo.length < VUELO_N) state.vuelo.push(id);
      pintarVuelo();
    });
    $('#vuelo-vasos').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-quitar]');
      if (!btn) return;
      state.vuelo = state.vuelo.filter((x) => x !== btn.dataset.quitar);
      pintarVuelo();
    });
    $('#vuelo-vaciar').addEventListener('click', () => { state.vuelo = []; pintarVuelo(); });
    $('#vuelo-mostrar').addEventListener('click', mostrarVuelo);
    $('#vuelo-agregar').addEventListener('click', () => {
      if (state.vuelo.length !== VUELO_N) return;
      agregarAlPedido({ tipo: 'vuelo', cervezas: state.vuelo.slice() },
        (v.nombre || 'Vuelo del Cisne') + ' (' + state.vuelo.map((id) => beerById(id).nombre).join(', ') + ')');
    });
    const etq = $('#etiqueta');
    $('#lista-barril').addEventListener('click', (e) => {
      const btn = e.target.closest('.tap__etq');
      if (!btn) return;
      $('#etq-t').textContent = btn.dataset.nombre;
      const img = $('#etq-img');
      img.src = mediaUrl(btn.dataset.etiqueta, 'cervezas');
      applyMediaFocal(img, img.getAttribute('src'));
      img.alt = 'Arte oficial de la etiqueta de ' + btn.dataset.nombre;
      etq.showModal();
    });
    $$('#etiqueta [data-cerrar]').forEach((b) => b.addEventListener('click', () => etq.close()));
    etq.addEventListener('click', (e) => { if (e.target === e.currentTarget) etq.close(); });
    $$('#vuelo-tarjeta [data-cerrar]').forEach((b) => b.addEventListener('click', () => $('#vuelo-tarjeta').close()));
    $('#vuelo-tarjeta').addEventListener('click', (e) => { if (e.target === e.currentTarget) e.currentTarget.close(); });
    pintarVuelo(true);
  }

  const beerById = (id) => state.data.barril.find((b) => b.id === id);
  const totalVuelo = () => state.vuelo.reduce((s, id) => s + precio4oz(beerById(id)).precio, 0);

  function pintarVuelo(inicial) {
    const n = state.vuelo.length;
    const lleno = n === VUELO_N;
    $$('#vuelo-opciones [data-vuelo]').forEach((b) => {
      const sel = state.vuelo.includes(b.dataset.vuelo);
      b.setAttribute('aria-pressed', String(sel));
      b.disabled = lleno && !sel;
    });
    const vasos = [];
    for (let i = 0; i < VUELO_N; i++) {
      const b = beerById(state.vuelo[i]);
      vasos.push(h('li', null, b
        ? h('button', { type: 'button', class: 'vaso vaso--lleno vaso--' + b.perfil, 'data-quitar': b.id, 'aria-label': `Vaso ${i + 1}: ${b.nombre}. Toca para quitarla` },
          h('span', { class: 'vaso__copa' }), h('span', { class: 'vaso__n', text: b.nombre }))
        : h('div', { class: 'vaso' }, h('span', { class: 'vaso__copa' }), h('span', { class: 'vaso__n vaso__n--vacio', text: `Vaso ${i + 1}` }))));
    }
    $('#vuelo-vasos').replaceChildren(...vasos);
    $('#vuelo-total').textContent = money(totalVuelo());
    if (!inicial) {
      $('#vuelo-estado').textContent = lleno
        ? `¡Listo! Tu vuelo suma ${money(totalVuelo())}.`
        : `Llevas ${n} de ${VUELO_N}. ${n ? 'Elige ' + (VUELO_N - n) + ' más.' : ''}`;
    } else {
      $('#vuelo-estado').textContent = `Elige ${VUELO_N} cervezas de barril.`;
    }
    $('#vuelo-mostrar').disabled = !lleno;
    $('#vuelo-agregar').disabled = !lleno;
    $('#vuelo-vaciar').disabled = n === 0;
  }

  function mostrarVuelo() {
    if (state.vuelo.length !== VUELO_N) return;
    $('#vcard-lista').replaceChildren(...state.vuelo.map((id) => {
      const b = beerById(id);
      return h('li', null,
        h('span', null, h('span', { class: 'vcard__n', text: b.nombre }), h('span', { class: 'vcard__e', text: [b.estilo, abv(b.abv)].join(' · ') })),
        h('span', { class: 'vcard__p', text: money(precio4oz(b).precio) }));
    }));
    $('#vcard-total').textContent = money(totalVuelo());
    $('#vuelo-tarjeta').showModal();
  }

  // ── Diálogos: foco atrapado (Tab / Mayús+Tab) ──────────────────────────────
  const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
  function atraparFoco(d) {
    d.addEventListener('keydown', (e) => {
      if (e.key !== 'Tab') return;
      const els = $$(FOCUSABLE, d).filter((el) => !el.closest('[hidden]') && el.getClientRects().length > 0);
      if (!els.length) return;
      const primero = els[0]; const ultimo = els[els.length - 1];
      if (e.shiftKey && (document.activeElement === primero || !d.contains(document.activeElement))) { e.preventDefault(); ultimo.focus(); }
      else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus(); }
    });
    d.addEventListener('click', (e) => { if (e.target === d) d.close(); });   // clic en el fondo
  }

  // ── Mi pedido ──────────────────────────────────────────────────────────────
  function cargarPedido() {
    state.pedido = P.revalidar(P.restaurar(safeGet(P.CLAVE), Date.now()), state.data);
  }
  function guardarPedido() {
    const p = state.pedido;
    safeSet(P.CLAVE, p.lineas.length || p.mesa ? P.serializar(p) : null);
  }
  /** Cambia el pedido, lo guarda y repinta la barra (y el panel si está abierto). */
  function actualizarPedido(nuevo, repintarPanel = true) {
    state.pedido = nuevo;
    guardarPedido();
    pintarBarra();
    if (repintarPanel && $('#pedido').open) pintarPanel();
  }

  /** Aviso breve con aria-live ("Agregado: ¡Alarma! 12 oz"). */
  function avisar(texto) {
    const t = $('#pedido-aviso');
    clearTimeout(state.avisoT);
    t.textContent = '';
    // Un tick vacío para que el lector de pantalla anuncie aunque se repita el mismo texto.
    setTimeout(() => { t.textContent = texto; }, 30);
    state.avisoT = setTimeout(() => { t.textContent = ''; }, 3200);
  }

  function agregarAlPedido(item, etiqueta) {
    try {
      const r = P.resolver(state.data, item.tipo, item.tipo === 'vuelo' ? 'vuelo' : item.id, item.variante, item.cervezas);
      actualizarPedido(P.agregar(state.pedido, item, state.data, Date.now()));
      avisar('Agregado: ' + (etiqueta || [r.nombre, r.detalle].filter(Boolean).join(' ')));
    } catch (ex) {
      avisar(ex.message);
    }
  }

  function iniciarAgregar() {
    // Chips de medida o variante: uno seleccionado por grupo.
    document.addEventListener('click', (e) => {
      const chip = e.target.closest('.opc-chip');
      if (chip) {
        $$('.opc-chip', chip.parentElement).forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
        return;
      }
      const btn = e.target.closest('[data-agregar]');
      if (!btn) return;
      const sel = $('.opc-chip[aria-pressed="true"]', btn.closest('.pedir'));
      agregarAlPedido({ tipo: btn.dataset.agregar, id: btn.dataset.id, variante: sel ? sel.dataset.opcion : null });
    });
  }

  function pintarBarra() {
    const p = state.pedido;
    const hay = !!p && p.lineas.length > 0;
    $('#pedido-barra').hidden = !hay;
    document.body.classList.toggle('con-pedido', hay);
    if (!hay) return;
    const n = P.contar(p);
    const tot = money(P.total(p));
    const revisar = P.pendientes(p);
    $('#pbar-n').textContent = String(n);
    $('#pbar-total').textContent = tot;
    $('#pedido-barra').classList.toggle('pbar--aviso', revisar > 0);
    $('#abrir-pedido').setAttribute('aria-label', `Mi pedido: ${n} ${n === 1 ? 'producto' : 'productos'}, total estimado ${tot}` + (revisar ? '. Hay avisos por revisar' : ''));
  }

  function abrirPedido() {
    const d = $('#pedido');
    pedidoErr('');
    $('#pedido-confirma').hidden = true;
    $('#pedido-vaciar').hidden = false;
    pintarPanel();
    if (!d.open) d.showModal();
    $('#pedido-t').focus();
    if (PEDIDO_QR_VISIBLE) cargarQR().catch(() => {});
  }
  function pedidoErr(t) { $('#pedido-err').textContent = t || ''; }
  function pedidoEstado(t) { const s = $('#pedido-estado'); s.textContent = ''; setTimeout(() => { s.textContent = t; }, 30); }

  const etiquetaLinea = (l) => [l.nombre, P.detalleLinea(l, state.data)].filter(Boolean).join(' ');

  /** Repinta el panel conservando el foco (por línea y acción). */
  function pintarPanel() {
    const p = state.pedido;
    const act = document.activeElement;
    const foco = act && act.closest && act.closest('#pedido-lineas') && act.dataset.acc ? { k: act.closest('[data-k]').dataset.k, acc: act.dataset.acc } : null;
    const vacio = p.lineas.length === 0;
    $('#pedido-vacio').hidden = !vacio;
    $('#pedido-pie').hidden = vacio;
    $('#pedido-lineas').replaceChildren(...p.lineas.map((l, i) => lineaPanel(l, i)));
    $('#pedido-total').textContent = money(P.total(p));
    const mesa = $('#pedido-mesa');
    if (document.activeElement !== mesa) mesa.value = p.mesa || '';
    if (foco) {
      const li = $(`#pedido-lineas [data-k="${CSS.escape(foco.k)}"]`);
      let el = li && $(`[data-acc="${foco.acc}"]`, li);
      if (el && el.disabled) el = $('[data-acc="' + (foco.acc === 'menos' ? 'mas' : 'menos') + '"]', li);
      (el || $('#pedido-t')).focus();
    }
  }

  function lineaPanel(l, i) {
    const nombre = etiquetaLinea(l);
    const unit = l.precio_cambiado ? l.precio_nuevo : l.precio;
    const detalle = P.detalleLinea(l, state.data);
    const aviso = l.no_disponible
      ? h('div', { class: 'pl__aviso', role: 'note' },
        h('p', { text: l.tipo === 'barril' || l.tipo === 'vuelo' ? 'Ya no está en barril.' : 'Ya no está disponible.' }),
        h('button', { type: 'button', class: 'btn btn--ink btn--sm', 'data-acc': 'quitar-aviso', 'aria-label': 'Quitar ' + nombre + ' del pedido' }, 'Quitar'))
      : l.precio_cambiado
        ? h('div', { class: 'pl__aviso', role: 'note' },
          h('p', null, 'Cambió el precio: ', h('b', { class: 'mono', text: money(l.precio_nuevo) }), h('span', { class: 'pl__antes mono', text: ' (antes ' + money(l.precio) + ')' })),
          h('div', { class: 'pl__aviso-acc' },
            h('button', { type: 'button', class: 'btn btn--ink btn--sm', 'data-acc': 'quitar-aviso', 'aria-label': 'Quitar ' + nombre + ' del pedido' }, 'Quitar'),
            h('button', { type: 'button', class: 'btn btn--primary btn--sm', 'data-acc': 'aceptar', 'aria-label': 'Aceptar el precio nuevo de ' + nombre }, 'Aceptar')))
        : null;
    return h('li', { class: 'pl' + (aviso ? ' pl--aviso' : ''), 'data-i': i, 'data-k': [l.tipo, l.id, l.variante || '', (l.cervezas || []).join('+'), l.nota].join('|') },
      h('div', { class: 'pl__top' },
        h('div', { class: 'pl__info' },
          h('p', { class: 'pl__n', text: l.nombre }),
          h('p', { class: 'pl__d mono', text: [detalle, money(unit) + (l.cantidad > 1 ? ' c/u' : '')].filter(Boolean).join(' · ') }),
          l.cervezas && h('p', { class: 'pl__vuelo', text: l.cervezas.map((id) => (beerById(id) || { nombre: id }).nombre).join(' · ') })),
        h('b', { class: 'pl__imp mono', text: l.no_disponible ? '—' : money(unit * l.cantidad) })),
      aviso,
      !l.no_disponible && h('div', { class: 'pl__ctrl' },
        h('div', { class: 'cant', role: 'group', 'aria-label': 'Cantidad de ' + nombre },
          h('button', { type: 'button', class: 'cant__b', 'data-acc': 'menos', 'aria-label': 'Uno menos de ' + nombre, disabled: l.cantidad <= 1 }, '−'),
          h('span', { class: 'cant__v mono', text: String(l.cantidad) }),
          h('button', { type: 'button', class: 'cant__b', 'data-acc': 'mas', 'aria-label': 'Uno más de ' + nombre, disabled: l.cantidad >= P.MAX_CANTIDAD }, '＋')),
        !l.precio_cambiado && h('button', { type: 'button', class: 'linkbtn pl__quitar', 'data-acc': 'quitar', 'aria-label': 'Quitar ' + nombre + ' del pedido' }, 'Quitar')),
      !l.no_disponible && h('div', { class: 'pl__nota' },
        h('label', { class: 'sr-only', for: 'pl-nota-' + i, text: 'Nota para ' + nombre }),
        h('input', { id: 'pl-nota-' + i, class: 'pl__nota-in', 'data-acc': 'nota', maxlength: P.MAX_NOTA, value: l.nota || '', placeholder: 'Nota (ej. sin cebolla)', autocomplete: 'off', enterkeyhint: 'done' })));
  }

  function iniciarPedido() {
    const d = $('#pedido');
    $('#ptar-qr').hidden = !PEDIDO_QR_VISIBLE;
    atraparFoco(d);
    $('#abrir-pedido').addEventListener('click', abrirPedido);
    $$('[data-cerrar]', d).forEach((b) => b.addEventListener('click', () => d.close()));
    d.addEventListener('close', () => { if (!$('#pedido-barra').hidden) $('#abrir-pedido').focus({ preventScroll: true }); });

    const lista = $('#pedido-lineas');
    lista.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-acc]');
      if (!btn) return;
      const li = btn.closest('[data-i]');
      const i = Number(li.dataset.i);
      const l = state.pedido.lineas[i];
      if (!l) return;
      const nombre = etiquetaLinea(l);
      pedidoErr('');
      try {
        if (btn.dataset.acc === 'menos' || btn.dataset.acc === 'mas') {
          const n = l.cantidad + (btn.dataset.acc === 'mas' ? 1 : -1);
          actualizarPedido(P.cambiarCantidad(state.pedido, i, n));
          pedidoEstado(`${nombre}: ${n}`);
        } else if (btn.dataset.acc === 'quitar' || btn.dataset.acc === 'quitar-aviso') {
          const sig = li.nextElementSibling || li.previousElementSibling;
          actualizarPedido(P.quitar(state.pedido, i));
          pedidoEstado(`Quitamos ${nombre} de tu pedido.`);
          const dest = sig && $(`#pedido-lineas [data-k="${CSS.escape(sig.dataset.k)}"] .pl__quitar, #pedido-lineas [data-k="${CSS.escape(sig.dataset.k)}"] [data-acc="quitar-aviso"]`);
          (dest || $('#pedido-t')).focus();
        } else if (btn.dataset.acc === 'aceptar') {
          actualizarPedido(P.aceptarPrecio(state.pedido, i));
          pedidoEstado(`Aceptaste el precio nuevo de ${nombre}.`);
          const nuevo = $(`#pedido-lineas [data-i="${i}"] [data-acc="mas"]`) || $(`#pedido-lineas [data-i="${i}"] [data-acc="nota"]`);
          (nuevo || $('#pedido-t')).focus();
        }
      } catch (ex) { pedidoErr(ex.message); }
    });
    // Notas: se guardan al confirmar (change). Solo se repinta si dos líneas quedaron iguales y se juntaron.
    lista.addEventListener('change', (e) => {
      const inp = e.target.closest('[data-acc="nota"]');
      if (!inp) return;
      const i = Number(inp.closest('[data-i]').dataset.i);
      const antes = state.pedido.lineas.length;
      try {
        const nuevo = P.cambiarNota(state.pedido, i, inp.value);
        const junto = nuevo.lineas.length !== antes;
        actualizarPedido(nuevo, junto);
        if (!junto) {
          const l = nuevo.lineas[i];
          inp.value = l.nota;
          inp.closest('[data-i]').dataset.k = [l.tipo, l.id, l.variante || '', (l.cervezas || []).join('+'), l.nota].join('|');
        } else {
          pedidoEstado('Juntamos dos productos iguales.');
        }
      } catch (ex) { pedidoErr(ex.message); }
    });
    lista.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.target.matches('[data-acc="nota"]')) { e.preventDefault(); e.target.dispatchEvent(new Event('change', { bubbles: true })); }
    });
    const mesa = $('#pedido-mesa');
    mesa.addEventListener('input', () => actualizarPedido(P.ponerMesa(state.pedido, mesa.value), false));
    mesa.addEventListener('change', () => { mesa.value = state.pedido.mesa; });

    $('#pedido-mostrar').addEventListener('click', mostrarAlMesero);
    $('#pedido-vaciar').addEventListener('click', () => {
      $('#pedido-vaciar').hidden = true;
      $('#pedido-confirma').hidden = false;
      $('#pedido-confirma-no').focus();
    });
    $('#pedido-confirma-no').addEventListener('click', () => {
      $('#pedido-confirma').hidden = true;
      $('#pedido-vaciar').hidden = false;
      $('#pedido-vaciar').focus();
    });
    $('#pedido-confirma-si').addEventListener('click', () => {
      $('#pedido-confirma').hidden = true;
      $('#pedido-vaciar').hidden = false;
      actualizarPedido(P.vacio(Date.now()));
      pedidoEstado('Vaciamos tu pedido.');
      $('#pedido-t').focus();
    });

    // Tarjeta para el mesero
    const t = $('#pedido-tarjeta');
    atraparFoco(t);
    $$('[data-cerrar]', t).forEach((b) => b.addEventListener('click', () => t.close()));
    t.addEventListener('close', () => {
      soltarPantalla();
      detenerQR();
      if ($('#pedido').open) ($('#pedido-pie').hidden ? $('#pedido-t') : $('#pedido-mostrar')).focus();
    });
    const terminar = (mensaje) => {
      t.close();
      $('#pedido').close();
      avisar(mensaje);
      const m = $('#contenido'); m.setAttribute('tabindex', '-1'); m.focus({ preventScroll: true });
    };
    $('#ptar-listo').addEventListener('click', () => {
      actualizarPedido(P.vacio(Date.now()), false);
      safeSet(P.CLAVE_CODIGO, null);
      terminar('¡Salud! Vaciamos tu pedido para la próxima ronda.');
    });
    $('#ptar-ok').addEventListener('click', () => terminar('¡Salud! Tu pedido ya está con el equipo.'));
    $('#ptar-nuevo').addEventListener('click', () => {
      if (!PEDIDO_QR_VISIBLE) return;
      safeSet(P.CLAVE_CODIGO, null);
      prepararQR();
      $('#ptar-qr-t').setAttribute('tabindex', '-1');
      $('#ptar-qr-t').focus();
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) return;
      if (t.open && state.qr && state.qr.modo === 'codigo') consultarEstado(state.qr.gen);   // reanuda el sondeo
      if (t.open && !state.wakeLock) mantenerPantalla();   // el navegador lo suelta al ocultar la página
      if (state.pedido && state.pedido.lineas.length && P.caducado(state.pedido, Date.now())) actualizarPedido(P.vacio(Date.now()));
    });
  }

  function mostrarAlMesero() {
    const p = state.pedido;
    if (!p.lineas.length) return;
    if (P.pendientes(p)) {
      pedidoErr('Revisa los avisos marcados antes de mostrar tu pedido.');
      const b = $('#pedido-lineas .pl--aviso button');
      if (b) b.focus();
      return;
    }
    pedidoErr('');
    const t = P.tarjeta(p, state.data);
    const mesa = $('#ptar-mesa');
    mesa.hidden = !t.mesa;
    mesa.textContent = t.mesa ? (/^\d/.test(t.mesa) ? 'Mesa ' + t.mesa : t.mesa) : '';
    $('#ptar-secciones').replaceChildren(...t.secciones.map((s) => h('section', { class: 'ptar__sec', 'aria-label': s.titulo },
      h('h3', { class: 'ptar__h', text: s.titulo }),
      h('ul', { class: 'ptar__lista' }, s.lineas.map((l) => h('li', null,
        h('span', { class: 'ptar__c mono', text: l.cantidad + '×' }),
        h('span', { class: 'ptar__info' },
          h('span', { class: 'vcard__n', text: l.nombre }),
          l.detalle && h('span', { class: 'vcard__e', text: l.detalle }),
          l.cervezas && h('ol', { class: 'ptar__vuelo' }, l.cervezas.map((c) => h('li', { text: c }))),
          l.nota && h('span', { class: 'ptar__nota', text: 'Nota: ' + l.nota })),
        h('span', { class: 'vcard__p', text: money(l.importe) })))))));
    $('#ptar-total').textContent = money(t.total);
    $('#ptar-listo').hidden = false;
    $('#pedido-tarjeta [data-cerrar]').hidden = false;
    $('#ptar-ok').hidden = true;
    const d = $('#pedido-tarjeta');
    d.showModal();
    d.scrollTop = 0;
    $('#ptar-t').setAttribute('tabindex', '-1');
    $('#ptar-t').focus({ preventScroll: true });
    mantenerPantalla();
    prepararQR();
  }

  // ── QR del pedido para el mesero ───────────────────────────────────────────
  // En línea: POST /api/pedidos → código → QR con /equipo/?p=<código> y sondeo del estado cada 5 s.
  // Sin conexión o 5xx: QR con el pedido dentro (/equipo/#d=…) y sin sondeo.
  const SONDEO_MS = 5000;
  const ESPERA_ENVIO_MS = 9000;
  let qrGen = 0;

  /** Pinta el bloque del QR según el modo: cargando | codigo | offline | vencido | error | tomado. */
  function pintarQR(modo, o = {}) {
    const caja = $('#ptar-qr');
    caja.dataset.modo = modo;
    const tomado = modo === 'tomado';
    $('#ptar-qr-t').hidden = tomado;
    $('#ptar-qr-img').hidden = tomado || modo === 'vencido' || modo === 'error';
    $('#ptar-codigo').hidden = modo !== 'codigo';
    $('#ptar-qr-nota').hidden = !(modo === 'codigo' || modo === 'offline');
    $('#ptar-tomado').hidden = !tomado;
    const aviso = $('#ptar-qr-aviso');
    aviso.hidden = !o.aviso;
    aviso.textContent = o.aviso || '';
    const nuevo = $('#ptar-nuevo');
    nuevo.hidden = !o.boton;
    nuevo.textContent = o.boton || '';
    if (modo === 'cargando') $('#ptar-qr-img').replaceChildren(h('span', { class: 'ptar__qr-msg', text: 'Generando código…' }));
    if (o.anuncio) { const s = $('#ptar-qr-estado'); s.textContent = ''; setTimeout(() => { s.textContent = o.anuncio; }, 30); }
  }

  /** Dibuja el QR (carga la librería si hace falta). Si no se puede, deja un mensaje en su lugar. */
  function dibujarQR(gen, texto, etiqueta, siFalla) {
    const caja = $('#ptar-qr-img');
    const nivel = texto.length > 500 ? 'L' : 'M';   // el respaldo sin conexión es largo: menos corrección, módulos más grandes
    return cargarQR().then(() => {
      if (gen !== qrGen) return;
      caja.replaceChildren(qrSvg(texto, etiqueta, 'ptar__svg', nivel));
      caja.dataset.texto = texto;
    }).catch(() => {
      if (gen !== qrGen) return;
      delete caja.dataset.texto;
      caja.replaceChildren(h('span', { class: 'ptar__qr-msg', text: siFalla }));
    });
  }

  function prepararQR() {
    // En modo de lectura el pedido se queda en el teléfono, sin envío ni sondeo.
    if (!PEDIDO_QR_VISIBLE) { detenerQR(); return; }
    const gen = ++qrGen;
    clearTimeout(state.qrT);
    const p = state.pedido;
    const huella = P.huellaPedido(p);
    state.qr = { gen, huella, codigo: null, modo: 'cargando', consultando: false };
    const reutilizar = P.codigoVigente(safeGet(P.CLAVE_CODIGO), huella, Date.now());
    if (reutilizar) {
      mostrarCodigo(gen, reutilizar);
      consultarEstado(gen);
      return;
    }
    pintarQR('cargando', { anuncio: 'Generando código…' });
    crearPedido(gen, p, huella);
  }

  async function crearPedido(gen, p, huella) {
    let res = null;
    let datos = {};
    const ctrl = 'AbortController' in window ? new AbortController() : null;
    const espera = ctrl && setTimeout(() => ctrl.abort(), ESPERA_ENVIO_MS);
    try {
      res = await fetch('/api/pedidos', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store', signal: ctrl ? ctrl.signal : undefined,
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ lineas: P.lineasParaServidor(p), mesa: p.mesa || '' }),
      });
      datos = await res.json().catch(() => ({}));
    } catch (e) { res = null; }
    clearTimeout(espera);
    if (gen !== qrGen) return;
    if (res && res.status === 201 && typeof datos.codigo === 'string') {
      safeSet(P.CLAVE_CODIGO, JSON.stringify({ huella, codigo: datos.codigo, expira_at: datos.expira_at }));
      mostrarCodigo(gen, datos.codigo);
      programarSondeo(gen);
    } else if (!res || res.status >= 500) {
      mostrarSinConexion(gen, p);
    } else {
      state.qr.modo = 'error';
      pintarQR('error', { aviso: datos.error || 'No pudimos generar el código.', boton: 'Reintentar', anuncio: datos.error || 'No pudimos generar el código.' });
    }
  }

  function mostrarCodigo(gen, codigo) {
    const legible = P.formatoCodigo(codigo);
    state.qr.codigo = codigo;
    state.qr.modo = 'codigo';
    $('#ptar-codigo').textContent = legible;
    $('#ptar-codigo').setAttribute('aria-label', 'Código ' + legible.split('').join(' '));
    pintarQR('codigo', { anuncio: 'Código listo: ' + legible });
    $('#ptar-qr-img').replaceChildren(h('span', { class: 'ptar__qr-msg', text: 'Dibujando el código…' }));
    dibujarQR(gen, location.origin + '/equipo/?p=' + encodeURIComponent(codigo), 'Código QR del pedido ' + legible,
      'No pudimos dibujar el QR. Díctale a tu mesero el código de abajo.');
  }

  function mostrarSinConexion(gen, p) {
    const base = location.origin + '/equipo/#d=';
    const q = P.paraQR(p, { max: Math.max(400, 1000 - base.length) });
    state.qr.modo = 'offline';
    const aviso = 'Sin conexión: el código lleva tu pedido completo.' + (q.recortado ? ' Las notas van resumidas: que tu mesero las lea en esta pantalla.' : '');
    pintarQR('offline', { aviso, anuncio: aviso });
    $('#ptar-qr-img').replaceChildren(h('span', { class: 'ptar__qr-msg', text: 'Dibujando el código…' }));
    dibujarQR(gen, base + q.datos, 'Código QR con tu pedido completo', 'Sin conexión no pudimos dibujar el código. Muéstrale esta pantalla a tu mesero.');
  }

  function programarSondeo(gen) {
    clearTimeout(state.qrT);
    state.qrT = setTimeout(() => consultarEstado(gen), SONDEO_MS);
  }

  /** Consulta /api/pedidos/<código>/estado. Se pausa con la pestaña oculta y se detiene al cerrar. */
  async function consultarEstado(gen) {
    const qr = state.qr;
    if (gen !== qrGen || !qr || qr.modo !== 'codigo' || qr.consultando) return;
    clearTimeout(state.qrT);
    if (document.hidden) return;   // visibilitychange lo reanuda
    qr.consultando = true;
    let res = null;
    let d = {};
    try {
      res = await fetch('/api/pedidos/' + encodeURIComponent(qr.codigo) + '/estado', { cache: 'no-store', credentials: 'same-origin', headers: { Accept: 'application/json' } });
      d = await res.json().catch(() => ({}));
    } catch (e) { res = null; }
    qr.consultando = false;
    if (gen !== qrGen || qr.modo !== 'codigo') return;
    if (res && res.ok && d.estado === 'tomado') return pedidoTomado(d.mesero);
    if (res && ((res.ok && (d.estado === 'caducado' || d.estado === 'cancelado')) || res.status === 404)) return codigoVencido(d.estado === 'cancelado');
    programarSondeo(gen);   // pendiente, sin red o 5xx: se vuelve a intentar
  }

  function pedidoTomado(mesero) {
    clearTimeout(state.qrT);
    state.qr.modo = 'tomado';
    safeSet(P.CLAVE_CODIGO, null);
    actualizarPedido(P.vacio(Date.now()));   // como "Ya lo pedí": el pedido local queda vacío
    const texto = mesero ? 'Pedido tomado por ' + mesero : 'Tu pedido ya lo tomó el equipo';
    $('#ptar-tomado-t').textContent = texto;
    pintarQR('tomado', { anuncio: '✓ ' + texto });
    $('#ptar-listo').hidden = true;
    $('#pedido-tarjeta [data-cerrar]').hidden = true;
    $('#ptar-ok').hidden = false;
    $('#pedido-tarjeta').scrollTop = 0;
    $('#ptar-ok').focus({ preventScroll: true });
  }

  function codigoVencido(cancelado) {
    clearTimeout(state.qrT);
    state.qr.modo = 'vencido';
    safeSet(P.CLAVE_CODIGO, null);
    const aviso = cancelado ? 'El equipo canceló este código.' : 'Este código caducó: nadie lo tomó a tiempo.';
    pintarQR('vencido', { aviso, boton: 'Generar un código nuevo', anuncio: aviso });
  }

  function detenerQR() {
    qrGen++;
    clearTimeout(state.qrT);
    state.qr = null;
  }

  /** Pide que la pantalla no se apague mientras el mesero lee la tarjeta (si el navegador lo permite). */
  async function mantenerPantalla() {
    if (!('wakeLock' in navigator) || state.wakeLock) return;
    try {
      const lock = await navigator.wakeLock.request('screen');
      if (!$('#pedido-tarjeta').open) { lock.release().catch(() => {}); return; }
      state.wakeLock = lock;
      lock.addEventListener && lock.addEventListener('release', () => { if (state.wakeLock === lock) state.wakeLock = null; });
    } catch (e) { /* sin permiso o batería baja: la tarjeta funciona igual */ }
  }
  function soltarPantalla() {
    const lock = state.wakeLock;
    state.wakeLock = null;
    if (lock) { try { lock.release().catch(() => {}); } catch (e) { /* ya liberado */ } }
  }

  // ── Wi-Fi ──────────────────────────────────────────────────────────────────
  async function cargarConfig() {
    if (!WIFI_VISIBLE) return;
    const pedido = ++state.configPidiendo;
    try {
      const res = await fetch('/api/config', { headers: { Accept: 'application/json' }, cache: 'no-store', credentials: 'same-origin' });
      if (!res.ok) throw new Error('config ' + res.status);
      const c = await res.json();
      if (pedido !== state.configPidiendo) return;
      state.wifi = c.wifi && c.wifi.ssid ? c.wifi : null;
      state.wifiEstado = state.wifi ? 'ok' : c.wifi_requiere_pasaporte ? 'socios' : 'oculto';
      if (state.wifi) cargarQR().catch(() => {});
    } catch (e) {
      if (pedido !== state.configPidiendo) return;
      if (state.wifiEstado === 'cargando') state.wifiEstado = 'error';   // si ya se conocía, se conserva
    }
    pintarWifi();
  }

  function pintarWifi() {
    const visible = WIFI_VISIBLE && (state.wifiEstado === 'ok' || state.wifiEstado === 'socios' || state.wifiEstado === 'error');
    $('#abrir-wifi').hidden = !visible;
    $('#pie-wifi').hidden = !visible;
    const d = $('#wifi-dlg');
    if (!d.open) return;
    const e = state.wifiEstado;
    $('#wifi-cargando').hidden = e !== 'cargando';
    $('#wifi-datos').hidden = e !== 'ok';
    $('#wifi-socios').hidden = e !== 'socios';
    $('#wifi-error').hidden = e !== 'error' && e !== 'oculto';
    $('#wifi-error p').textContent = e === 'oculto'
      ? 'El Wi-Fi no está disponible desde el menú. Pregunta en la barra.'
      : 'No pudimos revisar los datos del Wi-Fi. Pregunta la contraseña en la barra.';
    $('#wifi-reintentar').hidden = e === 'oculto';
    if (e !== 'ok') return;
    const w = state.wifi;
    const abierta = w.seguridad === 'nopass';
    $('#wifi-ssid').textContent = w.ssid;
    $('#wifi-pass').textContent = abierta ? '' : w.password;
    $('#wifi-fila-pass').hidden = abierta;
    $('#wifi-abierta').hidden = !abierta;
    const caja = $('#wifi-qr');
    const cadena = P.cadenaWifi(w);
    if (caja.dataset.cadena === cadena && caja.firstChild) return;
    caja.dataset.cadena = cadena;
    caja.replaceChildren(h('span', { class: 'wifi__qr-cargando', text: 'Preparando el código…' }));
    const dibujar = (intento) => cargarQR().then(() => {
      if (caja.dataset.cadena !== cadena) return;
      caja.replaceChildren(qrSvg(cadena, 'Código QR para conectarte a la red ' + w.ssid));
    }).catch(() => {
      if (caja.dataset.cadena !== cadena) return;
      if (intento < 2) { setTimeout(() => dibujar(intento + 1), 800 * (intento + 1)); return; }   // red inestable: reintenta
      caja.replaceChildren(h('span', { class: 'wifi__qr-cargando', text: 'No pudimos dibujar el código. Usa la red y la contraseña de arriba.' }));
    });
    dibujar(0);
  }

  let qrPromesa = null;
  let qrIntentos = 0;
  /** Carga la librería del QR solo cuando hace falta. Si falla, el siguiente intento usa otra URL
   *  (así el service worker no repite una copia dañada). */
  function cargarQR() {
    if (window.qrcode) return Promise.resolve();
    if (!qrPromesa) {
      const n = qrIntentos++;
      qrPromesa = new Promise((ok, mal) => {
        const s = document.createElement('script');
        s.src = '/assets/js/lib/qrcode.js' + VER + (n ? '&r=' + n : '');
        s.async = true;
        const fallo = () => { qrPromesa = null; s.remove(); mal(new Error('qrcode')); };
        s.onload = () => (window.qrcode ? ok() : fallo());
        s.onerror = fallo;
        document.head.append(s);
      });
    }
    return qrPromesa;
  }

  /** QR negro sobre crema, en SVG (con margen de 4 módulos para que la cámara lo lea bien). */
  function qrSvg(texto, etiqueta, clase = 'wifi__svg', nivel = 'M') {
    const q = window.qrcode;
    q.stringToBytes = q.stringToBytesFuncs['UTF-8'];
    const qr = q(0, nivel);
    qr.addData(texto, 'Byte');
    qr.make();
    const n = qr.getModuleCount();
    const m = 4;
    const lado = n + m * 2;
    let d = '';
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) d += `M${c + m} ${r + m}h1v1h-1z`;
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', `0 0 ${lado} ${lado}`);
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', etiqueta);
    svg.setAttribute('shape-rendering', 'crispEdges');
    svg.setAttribute('class', clase);
    const fondo = document.createElementNS(ns, 'rect');
    fondo.setAttribute('width', lado); fondo.setAttribute('height', lado); fondo.setAttribute('fill', '#F3EDE2');
    const path = document.createElementNS(ns, 'path');
    path.setAttribute('d', d); path.setAttribute('fill', '#0E0D0B');
    svg.append(fondo, path);
    return svg;
  }

  async function copiarTexto(texto, dentro) {
    try {
      if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(texto); return true; }
    } catch (e) { /* sin permiso: respaldo abajo */ }
    const ta = h('textarea', { readonly: true, 'aria-hidden': 'true', tabindex: '-1', class: 'copiar-respaldo' });
    ta.value = texto;
    dentro.append(ta);   // dentro del diálogo modal: lo de afuera está inerte
    ta.select();
    ta.setSelectionRange(0, texto.length);
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    ta.remove();
    return ok;
  }

  function abrirWifi() {
    if (!WIFI_VISIBLE) return;
    const d = $('#wifi-dlg');
    $('#wifi-copiado').textContent = '';
    if (!d.open) d.showModal();
    pintarWifi();
    $('#wifi-t').setAttribute('tabindex', '-1');
    $('#wifi-t').focus();
    if (state.wifiEstado === 'error') cargarConfig();
  }

  function iniciarWifi() {
    const d = $('#wifi-dlg');
    atraparFoco(d);
    $('#abrir-wifi').addEventListener('click', abrirWifi);
    $('#pie-wifi').addEventListener('click', (e) => { e.preventDefault(); abrirWifi(); });
    $$('[data-cerrar]', d).forEach((b) => b.addEventListener('click', () => d.close()));
    d.addEventListener('close', () => {
      if (location.hash === '#wifi') history.replaceState(null, '', location.pathname + location.search);
      const b = $('#abrir-wifi');
      if (!b.hidden && !$('#pasaporte').open) b.focus({ preventScroll: true });
    });
    $$('[data-copiar]', d).forEach((b) => b.addEventListener('click', async () => {
      if (!state.wifi) return;
      const cual = b.dataset.copiar;
      const ok = await copiarTexto(String(state.wifi[cual] || ''), d);
      $('#wifi-copiado').textContent = ok
        ? (cual === 'ssid' ? 'Copiamos el nombre de la red.' : 'Copiamos la contraseña.')
        : 'No se pudo copiar. Mantén presionado el texto para copiarlo.';
      if (ok) {
        b.textContent = 'Copiado';
        setTimeout(() => { b.textContent = 'Copiar'; }, 2000);
      }
    }));
    $('#wifi-reintentar').addEventListener('click', () => { state.wifiEstado = 'cargando'; pintarWifi(); cargarConfig(); });
    $('#wifi-pasaporte').addEventListener('click', () => {
      state.wifiTrasLogin = true;
      d.close();
      history.replaceState(null, '', '#pasaporte');
      abrirPasaporte('pase');
    });
    window.addEventListener('hashchange', () => { if (location.hash === '#wifi') abrirWifi(); });
    if (location.hash === '#wifi') abrirWifi();
    cargarConfig();
  }

  // ── App instalable (invitación solo para socios) ───────────────────────────
  function modoApp() {
    const mm = (q) => { try { return window.matchMedia(q).matches; } catch (e) { return false; } };
    return mm('(display-mode: standalone)') || mm('(display-mode: fullscreen)') || mm('(display-mode: minimal-ui)') || navigator.standalone === true;
  }

  /** Navegador y dispositivo, para elegir la forma de instalar.
   *  → { guia: 'ios-safari'|'ios-otro'|'android'|'samsung'|'firefox-android'|'chrome'|'edge'|'mac-safari'|'firefox'|'otro', equipo } */
  function dispositivo() {
    const ua = navigator.userAgent || '';
    const ipad = /iPad/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
    if (ipad || /iPhone|iPod/.test(ua)) {
      return { guia: /CriOS|EdgiOS|FxiOS|OPiOS/.test(ua) ? 'ios-otro' : 'ios-safari', equipo: ipad ? 'iPad' : 'iPhone' };
    }
    if (/Android/.test(ua)) {
      const guia = /SamsungBrowser/.test(ua) ? 'samsung' : /Firefox\//.test(ua) ? 'firefox-android' : 'android';
      return { guia, equipo: /Mobile/.test(ua) ? 'celular Android' : 'tableta Android' };
    }
    const equipo = /Windows/.test(ua) ? 'Windows' : /Macintosh/.test(ua) ? 'Mac' : /CrOS/.test(ua) ? 'Chromebook' : 'computadora';
    if (/Firefox\//.test(ua)) return { guia: 'firefox', equipo };
    if (/Edg\//.test(ua)) return { guia: 'edge', equipo };
    if (/Chrome|Chromium|OPR\//.test(ua)) return { guia: 'chrome', equipo };
    const safari = /Macintosh/.test(ua) && /Safari\//.test(ua);
    if (safari && Number((ua.match(/Version\/(\d+)/) || [])[1] || 0) >= 17) return { guia: 'mac-safari', equipo };
    return { guia: 'otro', equipo };
  }

  // Íconos de los pasos (como se ven en cada navegador)
  const ICO = {
    compartir: '<path d="M12 3v12M7.5 7.5L12 3l4.5 4.5M6 11H5v10h14V11h-1" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    agregar: '<rect x="4" y="4" width="16" height="16" rx="3.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 8.5v7M8.5 12h7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    puntos: '<circle cx="12" cy="5.5" r="1.8" fill="currentColor"/><circle cx="12" cy="12" r="1.8" fill="currentColor"/><circle cx="12" cy="18.5" r="1.8" fill="currentColor"/>',
    puntosH: '<circle cx="5.5" cy="12" r="1.8" fill="currentColor"/><circle cx="12" cy="12" r="1.8" fill="currentColor"/><circle cx="18.5" cy="12" r="1.8" fill="currentColor"/>',
    lineas: '<path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    pantalla: '<rect x="3" y="4" width="18" height="12.5" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M8.5 20h7M12 7v6M9.5 10.5L12 13l2.5-2.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  };
  const ico = (n) => {
    const sp = h('span', { class: 'pasos__ico' });
    sp.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + ICO[n] + '</svg>';
    return sp;
  };
  const b = (t) => h('b', { text: t });
  const kbd = (t) => h('kbd', { text: t });

  /** Pasos por navegador. Cada paso es una lista de nodos/textos. */
  const GUIAS = {
    'ios-safari': { titulo: 'iPhone o iPad (Safari)', pasos: [
      ['Toca ', ico('compartir'), ' ', b('Compartir'), ' en la barra de Safari (si no lo ves, toca primero ', ico('puntosH'), ').'],
      ['Desliza hacia abajo y elige ', ico('agregar'), ' ', b('«Agregar a inicio»'), '.'],
      ['Toca ', b('«Agregar»'), '. El Cisne aparece en tu pantalla de inicio.'],
    ], nota: 'Al abrir la app desde el ícono, entra una vez con tu teléfono y PIN.' },
    'ios-otro': { titulo: 'iPhone o iPad (Chrome, Edge o Firefox)', pasos: [
      ['Toca ', ico('compartir'), ' ', b('Compartir'), ' junto a la barra de direcciones (en Firefox está en el menú ', ico('lineas'), ').'],
      ['Elige ', ico('agregar'), ' ', b('«Agregar a inicio»'), '.'],
      ['Toca ', b('«Agregar»'), '.'],
    ], nota: 'Necesita iOS 16.4 o posterior; si no ves la opción, ábrela en Safari. Al abrir la app, entra una vez con tu teléfono y PIN.' },
    android: { titulo: 'Android (Chrome)', pasos: [
      ['Toca el menú ', ico('puntos'), ' arriba a la derecha.'],
      ['Elige ', b('«Instalar app»'), ' o ', b('«Agregar a la pantalla principal»'), '.'],
      ['Confirma con ', b('«Instalar»'), '.'],
    ] },
    samsung: { titulo: 'Android (Samsung Internet)', pasos: [
      ['Toca el menú ', ico('lineas'), ' abajo a la derecha.'],
      ['Elige ', b('«Agregar página a»'), ' y luego ', b('«Pantalla de inicio»'), '.'],
      ['Confirma con ', b('«Agregar»'), '.'],
    ] },
    'firefox-android': { titulo: 'Android (Firefox)', pasos: [
      ['Toca el menú ', ico('puntos'), '.'],
      ['Elige ', b('«Agregar a la pantalla de inicio»'), ' o ', b('«Instalar»'), '.'],
      ['Confirma con ', b('«Agregar»'), '.'],
    ] },
    chrome: { titulo: 'Windows, Mac o Chromebook (Chrome)', pasos: [
      ['Haz clic en ', ico('pantalla'), ' ', b('Instalar'), ' a la derecha de la barra de direcciones.'],
      ['Si no aparece: menú ', ico('puntos'), ' → ', b('«Transmitir, guardar y compartir»'), ' → ', b('«Instalar página como app»'), '.'],
      ['Confirma con ', b('«Instalar»'), '. Queda en tu escritorio y en el menú de inicio o el Launchpad.'],
    ] },
    edge: { titulo: 'Windows o Mac (Edge)', pasos: [
      ['Haz clic en ', ico('pantalla'), ' en la barra de direcciones.'],
      ['Si no aparece: menú ', ico('puntosH'), ' → ', b('«Aplicaciones»'), ' → ', b('«Instalar este sitio como una aplicación»'), '.'],
      ['Confirma con ', b('«Instalar»'), '.'],
    ] },
    'mac-safari': { titulo: 'Mac (Safari)', pasos: [
      ['En la barra de menús elige ', b('Archivo → «Agregar al Dock»'), ' (o ', ico('compartir'), ' → ', b('«Agregar al Dock»'), ').'],
      ['Haz clic en ', b('«Agregar»'), '. El Cisne queda en tu Dock.'],
    ] },
    firefox: { titulo: 'Computadora (Firefox)', pasos: [
      ['Firefox no instala apps web: guárdala en favoritos con ', kbd('Ctrl'), ' o ', kbd('⌘'), ' + ', kbd('D'), '.'],
      ['Para tenerla como app, abre esta página en ', b('Chrome'), ' o ', b('Edge'), ' y toca «Instalar app».'],
    ] },
    otro: { titulo: 'Otro navegador', pasos: [
      ['Busca en el menú del navegador ', b('«Instalar»'), ', ', b('«Agregar a inicio»'), ' o ', b('«Agregar al Dock»'), '.'],
      ['Si no aparece, guárdala en favoritos o ábrela en Chrome, Edge o Safari.'],
    ] },
  };
  const OTROS = ['ios-safari', 'android', 'samsung', 'chrome', 'edge', 'mac-safari'];

  const instaladaAqui = () => state.instalada || modoApp() || safeGet(INSTALADA_KEY) === '1';

  function pintarInstalar() {
    const socio = PASAPORTE_VISIBLE && !!state.socio;
    const listo = instaladaAqui();
    const boton = $('#abrir-instalar');
    if (boton) boton.hidden = !socio || listo;
    const card = $('#instalar');
    if (!card) return;
    const descartado = Number(safeGet(INSTALAR_KEY) || 0);
    const pausa = descartado > 0 && Date.now() - descartado < INSTALAR_PAUSA;
    card.hidden = !socio || listo || pausa;
    card.dataset.plataforma = state.promptInstalar ? 'prompt' : dispositivo().guia;
    if (listo && $('#instalar-dlg').open) $('#instalar-dlg').close();
  }

  function pintarGuia(guia, equipo) {
    const g = GUIAS[guia] || GUIAS.otro;
    $('#inst-disp').textContent = guia === 'otro' ? 'En tu navegador:' : 'En tu ' + equipo + ':';
    $('#inst-pasos').replaceChildren(...g.pasos.map((p) => h('li', null, ...p)));
    $('#inst-nota').hidden = !g.nota;
    $('#inst-nota').textContent = g.nota || '';
    $('#inst-otros').replaceChildren(...OTROS.filter((k) => k !== guia).map((k) =>
      h('div', { class: 'inst__otro' }, h('h3', { class: 'inst__otro-t', text: GUIAS[k].titulo }),
        h('ol', { class: 'pasos pasos--chico' }, ...GUIAS[k].pasos.map((p) => h('li', null, ...p.map((n) => (n && n.nodeType ? n.cloneNode(true) : n))))))));
  }

  /** "Instalar app": la invitación nativa si el navegador la ofrece (Android, Chrome/Edge en Windows, Mac,
   *  Chromebook); si no (iPhone/iPad, Safari, Firefox, Samsung sin invitación), la guía de su dispositivo. */
  async function instalar(origen) {
    const ev = state.promptInstalar;
    if (ev) {
      state.promptInstalar = null;   // la invitación nativa solo se puede usar una vez
      try {
        await ev.prompt();
        const r = await ev.userChoice;
        if (r && r.outcome === 'accepted') { state.instalada = true; avisar('¡Listo! El Cisne quedó instalado.'); }
      } catch (e) { abrirGuia(origen); }
      pintarInstalar();
      return;
    }
    abrirGuia(origen);
  }

  function abrirGuia(origen) {
    const d = $('#instalar-dlg');
    const { guia, equipo } = dispositivo();
    pintarGuia(guia, equipo);
    d.querySelector('.inst__otros').open = false;
    d.dataset.origen = origen || '';
    d.dataset.guia = guia;
    if (!d.open) d.showModal();
    $('#inst-t').setAttribute('tabindex', '-1');
    $('#inst-t').focus();
  }

  function iniciarInstalar() {
    const d = $('#instalar-dlg');
    atraparFoco(d);
    $('#abrir-instalar').addEventListener('click', () => instalar('barra'));
    $('#instalar-btn').addEventListener('click', () => instalar('pasaporte'));
    $$('[data-cerrar]', d).forEach((x) => x.addEventListener('click', () => d.close()));
    $('#inst-hecho').addEventListener('click', () => {
      safeSet(INSTALADA_KEY, '1');
      d.close();
      pintarInstalar();
    });
    d.addEventListener('close', () => {
      const vuelta = d.dataset.origen === 'pasaporte' ? $('#instalar-btn') : $('#abrir-instalar');
      if (vuelta && !vuelta.hidden && vuelta.offsetParent) vuelta.focus({ preventScroll: true });
      else if ($('#pasaporte').open) { $('#pase-t').setAttribute('tabindex', '-1'); $('#pase-t').focus(); }
    });
    $('#instalar-no').addEventListener('click', () => {
      safeSet(INSTALAR_KEY, String(Date.now()));
      pintarInstalar();
      $('#pase-t').setAttribute('tabindex', '-1');
      $('#pase-t').focus();
    });
    try { window.matchMedia('(display-mode: standalone)').addEventListener('change', pintarInstalar); } catch (e) { /* navegadores viejos */ }
  }

  // ── API del club ───────────────────────────────────────────────────────────
  class ApiError extends Error { constructor(status, msg) { super(msg); this.status = status; } }

  /** Llama a /api con la cookie de sesión. Si hay un token v1 guardado también lo manda (Bearer);
   *  si ese token ya no sirve (401) reintenta una vez solo con la cookie antes de rendirse. */
  async function api(path, body, reintento) {
    const headers = { Accept: 'application/json' };
    if (body) headers['Content-Type'] = 'application/json';
    const publica = path === '/login' || path === '/registro';
    const conToken = !!state.token && !reintento && !publica;
    if (conToken) headers.Authorization = 'Bearer ' + state.token;
    let res;
    try {
      res = await fetch('/api' + path, { method: body ? 'POST' : 'GET', headers, body: body ? JSON.stringify(body) : undefined, cache: 'no-store', credentials: 'same-origin' });
    } catch (e) {
      throw new ApiError(0, 'No hay conexión. Revisa tu internet e inténtalo otra vez.');
    }
    if (res.status === 401 && conToken) {
      state.token = null; safeSet(TOKEN_KEY, null);
      return api(path, body, true);
    }
    let data = {};
    try { data = await res.json(); } catch (e) { /* respuesta sin JSON (p. ej. 502 del proxy) */ }
    if (!res.ok) throw new ApiError(res.status, data.error || (res.status >= 500 ? 'El servidor no respondió. Inténtalo en un momento.' : 'Algo salió mal. Inténtalo otra vez.'));
    return data;
  }
  const esFalloDeRed = (ex) => ex && (ex.status === 0 || ex.status >= 500 || ex.status === 429);

  // ── Pasaporte ──────────────────────────────────────────────────────────────
  const dlg = () => $('#pasaporte');
  const hoyMx = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Mexico_City' });

  function msg(texto) { $('#pase-msg').textContent = texto || ''; }
  function err(texto) { $('#pase-err').textContent = texto || ''; }

  function abrirPasaporte(tab) {
    if (!PASAPORTE_VISIBLE) return;
    const d = dlg();
    if (!d.open) d.showModal();
    elegirPestana(tab || state.tab, true);
    pintarPasaporte();
    if (state.tab === 'ranking') { $('#rank-h').focus(); return; }
    const foco = state.socio
      ? ($('#checkin-form').hidden ? $('#pase-t') : $('#checkin-codigo'))
      : $('#tab-registro[aria-selected="true"], #tab-entrar[aria-selected="true"]');
    if (foco && !foco.closest('[hidden]')) { if (foco === $('#pase-t')) foco.setAttribute('tabindex', '-1'); foco.focus(); }
    else { $('#pase-t').setAttribute('tabindex', '-1'); $('#pase-t').focus(); }
  }
  function cerrarPasaporte() { dlg().close(); }

  function onCerrado() {
    if (location.hash === '#pasaporte' || location.hash === '#ranking') history.replaceState(null, '', location.pathname + location.search);
    msg(''); err('');
    $('#abrir-pasaporte').focus({ preventScroll: true });
    // Si vino del Wi-Fi "solo socios" y ya entró, vuelve al Wi-Fi.
    if (state.wifiTrasLogin) {
      state.wifiTrasLogin = false;
      if (state.socio) abrirWifi();
    }
  }

  // Pestañas del diálogo: Mi Pasaporte · Ranking
  function elegirPestana(cual, silencioso) {
    state.tab = cual === 'ranking' ? 'ranking' : 'pase';
    const rk = state.tab === 'ranking';
    $('#ptab-pase').setAttribute('aria-selected', String(!rk));
    $('#ptab-ranking').setAttribute('aria-selected', String(rk));
    $('#ptab-pase').tabIndex = rk ? -1 : 0;
    $('#ptab-ranking').tabIndex = rk ? 0 : -1;
    $('#ppanel-pase').hidden = rk;
    $('#ppanel-ranking').hidden = !rk;
    if (rk) cargarRanking(state.periodo);
    if (!silencioso) { msg(''); err(''); }
  }

  /** Guarda la caché local del socio (con el día, para no arrastrar "visita de hoy" a mañana). */
  function guardarCache(socio) {
    safeSet(CACHE_KEY, socio ? JSON.stringify({ dia: hoyMx(), socio }) : null);
  }
  function leerCache() {
    try {
      const c = JSON.parse(safeGet(CACHE_KEY) || 'null');
      if (!c || !c.socio || !c.socio.nombre) return null;
      const s = c.socio;
      if (c.dia !== hoyMx()) { s.visita_hoy = null; s.nps_hoy = false; }
      const ahora = new Date().toISOString();
      s.recompensas = (s.recompensas || []).filter((r) => !r.vence_at || new Date(r.vence_at).toISOString() >= ahora);
      return s;
    } catch (e) { return null; }
  }

  function guardarSesion(token, socio) {
    if (token) { state.token = token; safeSet(TOKEN_KEY, token); }
    actualizarSocio(socio);
    safeSet(SALIR_KEY, null);
  }
  function actualizarSocio(socio) {
    const antes = !!state.socio;
    state.socio = socio;
    guardarCache(socio);
    state.ranking = {};   // la posición del socio cambió o puede cambiar
    if (antes !== !!socio) alCambiarSesion();
  }
  function cerrarSesionLocal() {
    const antes = !!state.socio;
    state.token = null; safeSet(TOKEN_KEY, null);
    state.socio = null; state.visitaId = null; guardarCache(null);
    state.ranking = {};
    if (antes) alCambiarSesion();
  }
  /** Entró o salió un socio: el Wi-Fi "solo socios" depende de la sesión (cookie). */
  function alCambiarSesion() {
    cargarConfig();   // la respuesta más reciente gana (state.configPidiendo)
  }
  function sesionVencida() {
    cerrarSesionLocal();
    $('#premio').hidden = true; $('#nps-gracias').hidden = true; $('#checkin-form').hidden = true;
    pintarPasaporte();
    err('Tu sesión venció. Vuelve a entrar con tu teléfono y PIN.');
    elegirTab('entrar');
  }

  // Aviso discreto de "sin conexión" + reintento con espera creciente (5 s, 10 s, 20 s… hasta 60 s).
  function marcarSinRed(si) {
    state.sinRed = si;
    $('#pase-red').hidden = !si;
    $('#pase-red-t').textContent = state.socio
      ? 'Sin conexión. Te mostramos tu Pasaporte guardado y reintentamos solos.'
      : 'Sin conexión. No pudimos revisar tu Pasaporte; reintentamos solos.';
    $('#abrir-pasaporte').classList.toggle('mbar__pass--sinred', si);
    clearTimeout(state.reintento);
    if (si) {
      state.espera = Math.min(60000, state.espera ? state.espera * 2 : 5000);
      state.reintento = setTimeout(refrescarSocio, state.espera);
    } else {
      state.espera = 0;
    }
  }

  function pintarBoton() {
    const c = $('#pase-sellos');
    const btn = $('#abrir-pasaporte');
    btn.classList.toggle('mbar__pass--socio', !!state.socio);
    if (state.socio) {
      c.hidden = false;
      c.textContent = `${state.socio.sellos_ciclo}/${state.socio.ciclo}`;
      btn.setAttribute('aria-label', `Pasaporte Cisne: ${state.socio.sellos_ciclo} de ${state.socio.ciclo} sellos`);
    } else {
      c.hidden = true;
      btn.removeAttribute('aria-label');
    }
  }

  function pintarPasaporte(opts = {}) {
    pintarBoton();
    pintarPreferencia();
    pintarInstalar();
    const s = state.socio;
    const esperando = !s && state.comprobando;
    $('#pase-cargando').hidden = !esperando;
    $('#pase-invitado').hidden = !!s || esperando;
    $('#pase-socio').hidden = !s;
    if (!s) return;

    $('#pase-hola').textContent = '¡Hola, ' + s.nombre.split(' ')[0] + '!';
    const rk = s.ranking || {};
    const chip = $('#pase-rank');
    chip.hidden = !rk.posicion;
    if (rk.posicion) {
      chip.textContent = `#${rk.posicion} este mes`;
      chip.setAttribute('aria-label', `Vas en el lugar ${rk.posicion} de ${rk.participantes} este mes. Ver ranking`);
    }
    pintarSellos(s, opts.nuevo);

    const prog = $('#pase-prog');
    prog.replaceChildren();
    if (s.sellos_ciclo >= s.ciclo) {
      prog.append('¡Completaste tu Pasaporte! Tu siguiente visita empieza uno nuevo.');
    } else if (s.proxima_recompensa) {
      const f = s.proxima_recompensa.faltan;
      prog.append(`Te ${f === 1 ? 'falta 1 visita' : 'faltan ' + f + ' visitas'} para tu ${s.proxima_recompensa.nombre.charAt(0).toLowerCase() + s.proxima_recompensa.nombre.slice(1)}.`);
    }
    prog.append(h('span', { class: 'mono', text: `${s.visitas} ${s.visitas === 1 ? 'visita' : 'visitas'} en total · tel. •••• ${s.telefono_final}` }));

    const yaHoy = !!s.visita_hoy;
    if (yaHoy) state.visitaId = s.visita_hoy;
    $('#checkin-inicio').hidden = yaHoy || !$('#checkin-form').hidden;
    if (yaHoy) $('#checkin-form').hidden = true;
    $('#checkin-hecho').hidden = !yaHoy;

    // NPS: solo con visita de hoy y si no lo ha contestado; no mientras se muestra la recompensa.
    const npsVisible = yaHoy && !s.nps_hoy && $('#premio').hidden && $('#nps-gracias').hidden;
    if (npsVisible && $('#nps').hidden) resetNps();
    $('#nps').hidden = !npsVisible;

    const rs = s.recompensas || [];
    $('#cortesias-bloque').hidden = rs.length === 0;
    $('#cortesias').replaceChildren(...rs.map((r) => h('li', null,
      h('span', { class: 'mono', text: r.codigo }),
      h('b', { text: r.nombre.replace(/ de cortesía$/, '') }),
      h('small', { text: 'Vigente hasta el ' + fechaLarga(r.vence_at) + '. Muéstraselo al equipo.' }))));
  }

  function pintarSellos(s, nuevo) {
    const lista = $('#sellos');
    const items = [];
    for (let i = 1; i <= s.ciclo; i++) {
      const lleno = i <= s.sellos_ciclo;
      const premio = PREMIOS[i];
      const cls = ['sello', lleno && 'sello--lleno', premio && 'sello--premio', lleno && nuevo === i && !reduceMotion() && 'sello--nuevo'].filter(Boolean).join(' ');
      const label = `Visita ${i}${premio ? ', premio de ' + premio : ''}: ${lleno ? 'sellada' : 'pendiente'}`;
      items.push(h('li', { class: cls, 'aria-label': label },
        lleno ? svgUse('pluma') : h('span', { 'aria-hidden': 'true', text: String(i) }),
        premio && h('span', { class: 'sello__tag', 'aria-hidden': 'true', text: premio })));
    }
    lista.replaceChildren(...items);
    lista.setAttribute('aria-label', `Sellos de este ciclo: ${s.sellos_ciclo} de ${s.ciclo}`);
  }

  function elegirTab(cual) {
    const reg = cual === 'registro';
    $('#tab-registro').setAttribute('aria-selected', String(reg));
    $('#tab-entrar').setAttribute('aria-selected', String(!reg));
    $('#tab-registro').tabIndex = reg ? 0 : -1;
    $('#tab-entrar').tabIndex = reg ? -1 : 0;
    $('#form-registro').hidden = !reg;
    $('#form-entrar').hidden = reg;
  }

  function marcarInvalido(input, invalido) {
    if (invalido) input.setAttribute('aria-invalid', 'true'); else input.removeAttribute('aria-invalid');
  }

  function ocupado(form, si) {
    $$('button, input, textarea', form).forEach((x) => { x.disabled = si; });
    form.setAttribute('aria-busy', String(si));
  }

  async function enviarRegistro(e) {
    e.preventDefault();
    const f = e.currentTarget;
    err(''); msg('');
    const nombre = f.nombre.value.trim();
    const tel = soloDigitos(f.telefono.value).replace(/^52(?=\d{10}$)/, '');
    const pin = soloDigitos(f.pin.value);
    const checks = [
      [f.nombre, !nombre, 'Escribe tu nombre.'],
      [f.telefono, tel.length !== 10, 'El teléfono debe tener 10 dígitos.'],
      [f.pin, !/^\d{4}$/.test(pin), 'El PIN son 4 números.'],
      [f.acepta_privacidad, !f.acepta_privacidad.checked, 'Necesitamos que aceptes el aviso de privacidad.'],
    ];
    checks.forEach(([el, bad]) => marcarInvalido(el, bad));
    const malo = checks.find(([, bad]) => bad);
    if (malo) { err(malo[2]); malo[0].focus(); return; }
    ocupado(f, true);
    try {
      const r = await api('/registro', { nombre, telefono: tel, pin, acepta_privacidad: true, acepta_whatsapp: f.acepta_whatsapp.checked });
      guardarSesion(r.token, r.socio);
      marcarSinRed(false);
      f.reset();
      pintarPasaporte();
      msg(`¡Listo, ${r.socio.nombre.split(' ')[0]}! Tu Pasaporte ya está activo.`);
      $('#checkin-abrir').focus();
    } catch (ex) {
      err(ex.message);
      if (ex.status === 409) { elegirTab('entrar'); $('#l-tel').value = tel; $('#l-pin').focus(); }
    } finally { ocupado(f, false); }
  }

  async function enviarLogin(e) {
    e.preventDefault();
    const f = e.currentTarget;
    err(''); msg('');
    const tel = soloDigitos(f.telefono.value).replace(/^52(?=\d{10}$)/, '');
    const pin = soloDigitos(f.pin.value);
    marcarInvalido(f.telefono, tel.length !== 10);
    marcarInvalido(f.pin, !/^\d{4}$/.test(pin));
    if (tel.length !== 10) { err('El teléfono debe tener 10 dígitos.'); f.telefono.focus(); return; }
    if (!/^\d{4}$/.test(pin)) { err('El PIN son 4 números.'); f.pin.focus(); return; }
    ocupado(f, true);
    try {
      const r = await api('/login', { telefono: tel, pin });
      guardarSesion(r.token, r.socio);
      marcarSinRed(false);
      f.reset();
      pintarPasaporte();
      msg(`¡Qué gusto verte, ${r.socio.nombre.split(' ')[0]}!`);
      if (state.socio.visita_hoy) { $('#pase-t').setAttribute('tabindex', '-1'); $('#pase-t').focus(); }
      else $('#checkin-abrir').focus();
    } catch (ex) {
      err(ex.message);
    } finally { ocupado(f, false); }
  }

  function abrirCheckin() {
    err(''); msg('');
    $('#checkin-inicio').hidden = true;
    $('#checkin-form').hidden = false;
    const inp = $('#checkin-codigo');
    inp.value = ''; marcarInvalido(inp, false);
    inp.focus();
  }
  function cancelarCheckin() {
    $('#checkin-form').hidden = true;
    $('#checkin-inicio').hidden = false;
    err('');
    $('#checkin-abrir').focus();
  }

  async function enviarCheckin(e) {
    e.preventDefault();
    const f = e.currentTarget;
    const inp = $('#checkin-codigo');
    const codigo = soloDigitos(inp.value);
    err(''); msg('');
    if (codigo.length !== 4) { marcarInvalido(inp, true); err('El código del día son 4 números.'); inp.focus(); return; }
    ocupado(f, true);
    try {
      const r = await api('/checkin', { codigo });
      marcarInvalido(inp, false);
      marcarSinRed(false);
      actualizarSocio(r.socio);
      state.visitaId = r.visita_id;
      $('#checkin-form').hidden = true;
      if (r.ya_registrada) {
        msg('Tu visita de hoy ya estaba registrada.');
        pintarPasaporte();
      } else if (r.recompensa) {
        mostrarPremio(r.recompensa);
        pintarPasaporte({ nuevo: r.socio.sellos_ciclo });
        msg(`¡Sellado! Visita ${r.socio.visitas} registrada.`);
        $('#premio').focus();
      } else {
        pintarPasaporte({ nuevo: r.socio.sellos_ciclo });
        msg(`¡Sellado! Visita ${r.socio.visitas} registrada.`);
        if (!$('#nps').hidden) setTimeout(() => $('#nps').scrollIntoView({ behavior: reduceMotion() ? 'auto' : 'smooth', block: 'start' }), reduceMotion() ? 0 : 700);
      }
    } catch (ex) {
      if (ex.status === 401) return sesionVencida();
      marcarInvalido(inp, ex.status === 400);
      err(ex.message);
      inp.select();
    } finally {
      ocupado(f, false);
      if (!$('#checkin-form').hidden) inp.focus();
    }
  }

  function mostrarPremio(r) {
    $('#premio-nombre').textContent = r.nombre;
    $('#premio-codigo').textContent = r.codigo;
    $('#premio-vence').textContent = 'Vigente hasta el ' + fechaLarga(r.vence_at);
    $('#premio').hidden = false;
  }
  function seguirDespuesPremio() {
    $('#premio').hidden = true;
    pintarPasaporte();
    const nps = $('#nps');
    if (!nps.hidden) { nps.focus(); nps.scrollIntoView({ behavior: reduceMotion() ? 'auto' : 'smooth', block: 'start' }); }
    else $('#pase-t').focus();
  }

  // ── NPS ────────────────────────────────────────────────────────────────────
  function construirEscala() {
    const box = $('#nps-escala');
    box.setAttribute('role', 'radiogroup');
    box.setAttribute('aria-label', 'Del 0, nada probable, al 10, muy probable');
    for (let i = 0; i <= 10; i++) {
      box.append(h('button', { type: 'button', role: 'radio', 'aria-checked': 'false', 'data-score': i, tabindex: i === 0 ? 0 : -1, text: String(i) }));
    }
    box.addEventListener('click', (e) => {
      const b = e.target.closest('[data-score]');
      if (b) elegirScore(Number(b.dataset.score));
    });
    box.addEventListener('keydown', (e) => {
      const keys = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
      if (!(e.key in keys) && e.key !== 'Home' && e.key !== 'End') return;
      e.preventDefault();
      const cur = state.npsScore == null ? -1 : state.npsScore;
      let n = e.key === 'Home' ? 0 : e.key === 'End' ? 10 : Math.min(10, Math.max(0, cur + keys[e.key]));
      if (cur === -1 && keys[e.key] === -1) n = 0;
      elegirScore(n, true);
    });
  }
  function elegirScore(n, foco) {
    state.npsScore = n;
    $$('#nps-escala [data-score]').forEach((b) => {
      const on = Number(b.dataset.score) === n;
      b.setAttribute('aria-checked', String(on));
      b.tabIndex = on ? 0 : -1;
      if (on && foco) b.focus();
    });
    $('#nps-enviar').disabled = false;
  }
  function resetNps() {
    state.npsScore = null;
    $$('#nps-escala [data-score]').forEach((b, i) => { b.setAttribute('aria-checked', 'false'); b.tabIndex = i === 0 ? 0 : -1; });
    $('#nps-comentario').value = '';
    $('#nps-enviar').disabled = true;
  }

  async function enviarNps(e) {
    e.preventDefault();
    const f = e.currentTarget;
    if (state.npsScore == null) { err('Elige un número del 0 al 10.'); return; }
    const visita = state.visitaId || (state.socio && state.socio.visita_hoy);
    err(''); msg('');
    ocupado(f, true);
    try {
      const score = state.npsScore;
      const r = await api('/nps', { visita_id: visita, score, comentario: $('#nps-comentario').value.trim() });
      if (state.socio) { state.socio.nps_hoy = true; guardarCache(state.socio); }
      $('#nps').hidden = true;
      const [titulo, texto, boton] = RESENA[r.tono] || RESENA[tonoDe(score)];
      $('#gracias-t').textContent = r.ya_respondida ? '¡Gracias!' : titulo;
      $('#gracias-p').textContent = r.ya_respondida ? 'Ya nos habías respondido hoy. Si quieres, cuéntanos tu experiencia en Google.' : texto;
      const btn = $('#resena');
      btn.hidden = !(r.invitar_resena && r.resena_url);
      if (!btn.hidden) { btn.href = r.resena_url; $('#resena-t').textContent = r.ya_respondida ? 'Contarlo en Google' : boton; }
      $('#nps-gracias').hidden = false;
      $('#nps-gracias').focus();
    } catch (ex) {
      if (ex.status === 401) return sesionVencida();
      err(ex.message);
    } finally { ocupado(f, false); if (state.npsScore != null) $('#nps-enviar').disabled = false; }
  }

  function clickResena() {
    // El enlace abre la reseña en otra pestaña por sí mismo; aquí solo se registra el clic (con la cookie).
    const visita = state.visitaId || (state.socio && state.socio.visita_hoy);
    const headers = { 'Content-Type': 'application/json' };
    if (state.token) headers.Authorization = 'Bearer ' + state.token;
    try {
      fetch('/api/resena-click', {
        method: 'POST', keepalive: true, credentials: 'same-origin', headers,
        body: JSON.stringify({ visita_id: visita }),
      }).catch(() => {});
    } catch (e) { /* sin red: no bloquea la reseña */ }
  }

  // ── Ranking ────────────────────────────────────────────────────────────────
  function pintarPreferencia() {
    const s = state.socio;
    $('#rank-pref').hidden = !s;
    if (!s) return;
    const on = s.mostrar_ranking !== false;
    $('#rank-switch').setAttribute('aria-checked', String(on));
    $('#rank-switch-h').textContent = on
      ? 'Apareces como «' + (s.alias || s.nombre.split(' ')[0]) + '». Puedes ocultarte cuando quieras.'
      : 'No apareces en la lista pública, pero sigues sumando visitas y ves tu lugar.';
  }

  async function cargarRanking(periodo, forzar) {
    state.periodo = periodo;
    $$('[data-periodo]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.periodo === periodo)));
    const cache = state.ranking[periodo];
    if (cache && !forzar) { pintarRanking(cache); return; }
    const estado = $('#rank-estado');
    $('#rank-lista').setAttribute('aria-busy', 'true');
    if (!cache) estado.textContent = 'Cargando ranking…';
    try {
      const r = await api('/ranking?periodo=' + periodo);
      state.ranking[periodo] = r;
      if (state.periodo === periodo) pintarRanking(r);
    } catch (ex) {
      if (state.periodo !== periodo) return;
      estado.replaceChildren(ex.status === 0 ? 'Sin conexión: no pudimos cargar el ranking. ' : ex.message + ' ',
        h('button', { type: 'button', class: 'linkbtn', text: 'Reintentar', onclick: () => cargarRanking(periodo, true) }));
    } finally {
      $('#rank-lista').setAttribute('aria-busy', 'false');
    }
  }

  function medalla(pos) {
    if (pos === 1) {
      return h('span', { class: 'rank__pos rank__pos--1', 'aria-hidden': 'true' },
        h('span', { class: 'sticker rank__sticker' }, h('img', { src: '/assets/img/marca/favicon-192.png', alt: '', width: 192, height: 192 })),
        h('span', { class: 'rank__n', text: '1' }));
    }
    if (pos <= 3) {
      return h('span', { class: 'rank__pos rank__pos--' + pos, 'aria-hidden': 'true' }, svgUse('pluma', 'rank__pluma'), h('span', { class: 'rank__n', text: String(pos) }));
    }
    return h('span', { class: 'rank__pos', 'aria-hidden': 'true' }, h('span', { class: 'rank__n', text: String(pos) }));
  }

  function pintarRanking(r) {
    const periodo = r.periodo || state.periodo;
    const filas = r.ranking || [];
    const yo = r.yo;
    const s = state.socio;
    $('#rank-estado').textContent = filas.length ? `Top ${filas.length} ${PERIODOS[periodo]}.` : '';

    // "Tú vas en el lugar N de M"
    const box = $('#rank-yo');
    box.hidden = false;
    if (yo && yo.posicion) {
      box.replaceChildren(h('p', null, 'Tú vas en el lugar ', h('b', { class: 'mono', text: '#' + yo.posicion }), ` de ${yo.participantes} ${PERIODOS[periodo]}`),
        h('small', { text: `${yo.visitas} ${yo.visitas === 1 ? 'visita' : 'visitas'} ${PERIODOS[periodo]}.` }));
    } else if (s) {
      box.replaceChildren(h('p', { text: `Aún no tienes visitas ${PERIODOS[periodo]}.` }),
        h('small', { text: 'Registra la de hoy con el código del día para entrar al ranking.' }));
    } else {
      box.replaceChildren(h('p', { text: '¿Quieres aparecer aquí?' }),
        h('button', { type: 'button', class: 'linkbtn', text: 'Crea tu Pasaporte y registra tus visitas', onclick: () => { elegirPestana('pase'); elegirTab('registro'); $('#r-nombre').focus(); } }));
    }

    const lista = $('#rank-lista');
    if (!filas.length) {
      lista.replaceChildren(h('li', { class: 'rank__vacio' }, svgUse('pluma', 'rank__vacio-ico'), h('span', { text: PRIMERO[periodo] })));
      return;
    }
    const esYo = (f) => s && yo && s.mostrar_ranking !== false && f.alias === s.alias && f.visitas === yo.visitas;
    lista.replaceChildren(...filas.map((f) => {
      const mio = esYo(f);
      return h('li', { class: 'rank__fila' + (f.posicion <= 3 ? ' rank__fila--podio' : '') + (mio ? ' rank__fila--yo' : '') },
        medalla(f.posicion),
        h('span', { class: 'rank__alias' }, h('span', { class: 'sr-only', text: `Lugar ${f.posicion}: ` }), f.alias, mio && h('span', { class: 'rank__tu', text: 'Tú' })),
        h('span', { class: 'rank__v mono', text: `${f.visitas} ${f.visitas === 1 ? 'visita' : 'visitas'}` }));
    }));
  }

  async function cambiarPreferencia() {
    const s = state.socio;
    if (!s) return;
    const sw = $('#rank-switch');
    const nuevo = sw.getAttribute('aria-checked') !== 'true';
    sw.setAttribute('aria-checked', String(nuevo));   // optimista
    sw.disabled = true;
    err('');
    try {
      const r = await api('/yo/preferencias', { mostrar_ranking: nuevo });
      actualizarSocio(r.socio);
      marcarSinRed(false);
      pintarPasaporte();
      msg(nuevo ? 'Listo: apareces en el ranking público.' : 'Listo: ya no apareces en el ranking público.');
      cargarRanking(state.periodo, true);
    } catch (ex) {
      sw.setAttribute('aria-checked', String(!nuevo));
      if (ex.status === 401) { sesionVencida(); return; }
      err(ex.status === 0 ? 'Sin conexión: no se guardó el cambio. Inténtalo otra vez.' : ex.message);
    } finally { sw.disabled = false; sw.focus(); }
  }

  // ── Sesión: arranque, refresco y salida ────────────────────────────────────
  async function salir() {
    const tok = state.token;
    cerrarSesionLocal();
    marcarSinRed(false);
    $('#premio').hidden = true; $('#nps-gracias').hidden = true; $('#checkin-form').hidden = true;
    pintarPasaporte();
    msg('Saliste de tu Pasaporte. ¡Vuelve pronto!');
    elegirTab('entrar');
    $('#tab-entrar').focus();
    safeSet(SALIR_KEY, '1');   // si no hay red, la siguiente carga termina de borrar la cookie
    if (await cerrarEnServidor(tok)) safeSet(SALIR_KEY, null);
    else msg('Saliste en este celular. Cuando vuelva la conexión cerraremos también tu sesión en el servidor.');
  }

  /** POST /api/logout: el servidor borra la sesión y la cookie. true si respondió (200 o 401). */
  async function cerrarEnServidor(tok) {
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (tok) headers.Authorization = 'Bearer ' + tok;
      const res = await fetch('/api/logout', { method: 'POST', credentials: 'same-origin', headers, body: '{}' });
      if (res.status === 401 && tok) return cerrarEnServidor(null);   // token viejo: borra la de la cookie
      return res.status < 500;
    } catch (e) { return false; }
  }

  /** Pide /api/yo SIEMPRE (la cookie puede existir aunque Safari haya borrado el localStorage).
   *  Solo un 401 cierra la sesión; red caída o 5xx conservan el estado y reintentan. */
  async function refrescarSocio() {
    clearTimeout(state.reintento);
    if (safeGet(SALIR_KEY)) {
      if (!(await cerrarEnServidor(state.token))) { state.comprobando = false; pintarPasaporte(); marcarSinRed(true); return; }
      safeSet(SALIR_KEY, null);
      cerrarSesionLocal();
    }
    const tenia = !!state.socio;
    try {
      const r = await api('/yo');
      actualizarSocio(r.socio);
      marcarSinRed(false);
    } catch (ex) {
      if (ex.status === 401) {
        cerrarSesionLocal();
        marcarSinRed(false);
        if (tenia) { err('Tu sesión venció. Vuelve a entrar con tu teléfono y PIN.'); elegirTab('entrar'); }
      } else if (esFalloDeRed(ex)) {
        marcarSinRed(true);
      }
    } finally {
      state.comprobando = false;
    }
    pintarPasaporte();
  }

  function iniciarPasaporte() {
    const d = dlg();
    $('#abrir-pasaporte').addEventListener('click', (e) => { e.preventDefault(); history.replaceState(null, '', '#pasaporte'); abrirPasaporte('pase'); });
    $$('[data-cerrar]', d).forEach((b) => b.addEventListener('click', cerrarPasaporte));
    d.addEventListener('click', (e) => { if (e.target === d) cerrarPasaporte(); });
    d.addEventListener('close', onCerrado);
    window.addEventListener('hashchange', () => {
      if (location.hash === '#pasaporte') abrirPasaporte('pase');
      else if (location.hash === '#ranking') abrirPasaporte('ranking');
    });

    // Pestañas Mi Pasaporte / Ranking (flechas izquierda/derecha, Inicio/Fin)
    $('#ptab-pase').addEventListener('click', () => elegirPestana('pase'));
    $('#ptab-ranking').addEventListener('click', () => elegirPestana('ranking'));
    $('#ptab-pase').parentElement.addEventListener('keydown', (e) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
      e.preventDefault();
      const destino = e.key === 'Home' ? 'pase' : e.key === 'End' ? 'ranking' : (state.tab === 'pase' ? 'ranking' : 'pase');
      elegirPestana(destino);
      $(destino === 'pase' ? '#ptab-pase' : '#ptab-ranking').focus();
    });
    $('#pase-rank').addEventListener('click', () => { state.periodo = 'mes'; elegirPestana('ranking'); $('#rank-h').focus(); });
    $$('[data-periodo]').forEach((b) => b.addEventListener('click', () => cargarRanking(b.dataset.periodo)));
    $('#rank-switch').addEventListener('click', cambiarPreferencia);

    $('#tab-registro').addEventListener('click', () => { err(''); elegirTab('registro'); });
    $('#tab-entrar').addEventListener('click', () => { err(''); elegirTab('entrar'); });
    $('#tab-registro').parentElement.addEventListener('keydown', (e) => {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      const reg = $('#tab-registro').getAttribute('aria-selected') === 'true';
      elegirTab(reg ? 'entrar' : 'registro');
      (reg ? $('#tab-entrar') : $('#tab-registro')).focus();
    });
    $('#form-registro').addEventListener('submit', enviarRegistro);
    $('#form-entrar').addEventListener('submit', enviarLogin);
    $$('.pin, #checkin-codigo, input[type="tel"]').forEach((i) => i.addEventListener('input', () => {
      const max = i.classList.contains('pin') || i.id === 'checkin-codigo' ? 4 : 14;
      const limpio = i.type === 'tel' ? i.value.replace(/[^\d\s+()-]/g, '') : soloDigitos(i.value).slice(0, max);
      if (limpio !== i.value) i.value = limpio;
      marcarInvalido(i, false);
    }));

    $('#checkin-abrir').addEventListener('click', abrirCheckin);
    $('#checkin-cancelar').addEventListener('click', cancelarCheckin);
    $('#checkin-form').addEventListener('submit', enviarCheckin);
    $('#premio-seguir').addEventListener('click', seguirDespuesPremio);
    construirEscala();
    $('#nps').addEventListener('submit', enviarNps);
    $('#resena').addEventListener('click', clickResena);
    $('#salir').addEventListener('click', salir);

    // 1) Pinta YA con la caché (sin parpadeo de formularios). 2) Refresca en segundo plano.
    state.socio = leerCache();
    state.comprobando = !state.socio;
    pintarPasaporte();
    if (location.hash === '#pasaporte') abrirPasaporte('pase');
    else if (location.hash === '#ranking') abrirPasaporte('ranking');
    refrescarSocio();
    // Al volver a la pestaña (p. ej. al día siguiente) o al recuperar la red, refresca.
    window.addEventListener('online', () => refrescarSocio());
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refrescarSocio(); });
  }

  // ── Arranque ───────────────────────────────────────────────────────────────
  async function init() {
    $('#abrir-pasaporte').hidden = !PASAPORTE_VISIBLE;
    if (!CMS_PREVIEW) {
      if (PASAPORTE_VISIBLE) {
        iniciarPasaporte();
        iniciarInstalar();
      }
      if (WIFI_VISIBLE) iniciarWifi();
      iniciarAgregar();
      iniciarPedido();
    }
    try {
      state.data = await cargarMenu();
    } catch (e) {
      $('#cargando').textContent = 'No pudimos cargar el menú. Revisa tu conexión y recarga la página.';
      return;
    }
    state.dishes = {};
    (state.data.comida || []).forEach((s) => (s.items || []).forEach((it) => { state.dishes[it.id] = it; }));
    renderBarril();
    renderLatas();
    renderFiltros();
    renderVuelo();
    renderComida();
    renderSinAlcohol();
    renderPie();
    if (!CMS_PREVIEW) {
      anclasMaridaje();
      cargarPedido();
      pintarBarra();
    }
    $('#cargando').remove();
    $$('main > .msec, #pie').forEach((s) => {
      s.hidden = s.id === 'vuelo' && state.data.vuelo?.visible === false;
    });
    if (!CMS_PREVIEW) scrollSpy();
    // Si se llegó con un ancla a una sección o platillo, recoloca la vista ya con contenido.
    const hash = location.hash.slice(1);
    if (hash && hash !== 'pasaporte' && hash !== 'wifi') { const t = document.getElementById(hash); if (t && !t.hidden) t.scrollIntoView(); }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
