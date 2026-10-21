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

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const state = {
    data: null, dishes: {}, filtro: null, vuelo: [],
    token: safeGet(TOKEN_KEY), socio: null, visitaId: null, npsScore: null,
    comprobando: false, sinRed: false, reintento: null, espera: 0,
    periodo: 'mes', ranking: {}, tab: 'pase',
  };

  // ── Utilidades ─────────────────────────────────────────────────────────────
  function safeGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function safeSet(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) { /* modo privado */ } }

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
    if (tag === 'img') applyMediaFocal(n, attrs && attrs.src, state.data && state.data._media_focal);
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

  // El nombre contextual es contenido explícito; cambiar la foto no cambia el producto.
  function dishLabel(item) {
    if (item.nombre_completo) return item.nombre_completo;
    if (/^De /.test(item.nombre) && item.id === 'hamburguesa-suadero') return 'Sándwich de ' + item.nombre.slice(3);
    if (/^De /.test(item.nombre) && /^hamburguesa-/.test(item.id || '')) return 'Hamburguesa de ' + item.nombre.slice(3);
    return item.nombre;
  }

  const disponible = item => item.visible !== false && item.disponible !== false;
  function mediaUrl(value, group) {
    if (!value) return '';
    if (/^(?:\/assets\/|\/cms\/media\/[A-Za-z0-9_-]+\/file(?:[?#]|$)|https:\/\/)/.test(value)) return value;
    if (/^[A-Za-z0-9_./-]+$/.test(value) && !value.split('/').includes('..')) return '/assets/img/' + group + '/' + value;
    return '';
  }
  function applyMediaFocal(node, url, map) {
    const key = String(url || '').split(/[?#]/)[0];
    const point = map && map[key];
    if (!/^\/cms\/media\/[A-Za-z0-9_-]+\/file$/.test(key) || !point ||
        !['x', 'y'].every(axis => typeof point[axis] === 'number' && Number.isFinite(point[axis]) && point[axis] >= 0 && point[axis] <= 1)) {
      node.style.objectPosition = '';
      return;
    }
    node.style.objectPosition = (point.x * 100) + '% ' + (point.y * 100) + '%';
  }
  function menuDisponible(data) {
    const next = { ...data };
    ['barril', 'latas', 'sin_alcohol'].forEach(key => { next[key] = (data[key] || []).filter(disponible); });
    next.comida = (data.comida || []).filter(cat => cat.visible !== false).map(cat => ({ ...cat, items: (cat.items || []).filter(disponible) })).filter(cat => cat.items.length);
    return next;
  }
  const cmsKey = (item, fallback, suffix) => CMS_PREVIEW ? (item._cms_key || fallback) + '.' + suffix : null;

  // ── Catálogo ───────────────────────────────────────────────────────────────
  async function cargarMenu() {
    const res = await fetch(DATA_URL, { cache: 'no-cache' });
    if (!res.ok) throw new Error('menu ' + res.status);
    return menuDisponible(await res.json());
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
        h('ul', { class: 'tap__prices', 'aria-label': 'Precios' },
          (b.precios || []).map((p) => h('li', null, h('span', { text: p.medida }), h('b', { text: money(p.precio) })))),
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
        h('ul', { class: 'rows' }, items.map((l) => h('li', { class: 'row', 'data-perfil': p, 'data-cms-key': cmsKey(l, 'menu.latas.' + latas.indexOf(l), 'nombre') },
          h('div', null,
            h('span', { class: 'row__n', text: l.nombre }),
            h('span', { class: 'row__e', text: [l.estilo, abv(l.abv)].filter(Boolean).join(' · ') }),
            h('span', { class: 'row__o', text: [l.cerveceria, l.origen].filter(Boolean).join(' · ') })),
          h('span', { class: 'row__p', text: money(l.precio) }))))));
    });
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
              d.descripcion && h('p', { class: 'plato__d', text: d.descripcion })),
            con.length > 0 && h('p', { class: 'pidelo' },
              h('span', { class: 'pidelo__t', text: 'Pídelo con…' }),
              con.map((b) => h('a', { href: '#barril-' + b.id, 'data-barril': b.id },
                b.img ? h('img', { class: 'pidelo__img', src: mediaUrl(b.img, 'cervezas'), alt: '', width: 32, height: 32, loading: 'lazy', decoding: 'async' })
                  : h('span', { class: 'dot dot--' + b.perfil }), b.nombre))));
        }))));
    });
  }

  function renderSinAlcohol() {
    $('#lista-sin').replaceChildren(...state.data.sin_alcohol.map((s, i) => h('li', { class: 'row', 'data-cms-key': cmsKey(s, 'menu.sin_alcohol.' + i, 'nombre') },
      h('div', null, h('span', { class: 'row__n', text: s.nombre }), s.detalle && h('span', { class: 'row__o', text: s.detalle })),
      h('span', { class: 'row__p', text: money(s.precio) }))));
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
    const links = $$('.tabs a');
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
    const etq = $('#etiqueta');
    $('#lista-barril').addEventListener('click', (e) => {
      const btn = e.target.closest('.tap__etq');
      if (!btn) return;
      $('#etq-t').textContent = btn.dataset.nombre;
      const img = $('#etq-img');
      img.src = mediaUrl(btn.dataset.etiqueta, 'cervezas');
      applyMediaFocal(img, img.getAttribute('src'), state.data && state.data._media_focal);
      img.alt = 'Arte oficial de la etiqueta de ' + btn.dataset.nombre;
      etq.showModal();
    });
    $$('#etiqueta [data-cerrar]').forEach((b) => b.addEventListener('click', () => etq.close()));
    etq.addEventListener('click', (e) => { if (e.target === e.currentTarget) etq.close(); });
    $$('#vuelo-tarjeta [data-cerrar]').forEach((b) => b.addEventListener('click', () => $('#vuelo-tarjeta').close()));
    $('#vuelo-tarjeta').addEventListener('click', (e) => { if (e.target === e.currentTarget) e.currentTarget.close(); });
    pintarVuelo(true);
    if (opciones.length < VUELO_N) $('#vuelo-estado').textContent = 'Por ahora no hay cuatro cervezas disponibles para armar el vuelo.';
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
    state.socio = socio;
    guardarCache(socio);
    state.ranking = {};   // la posición del socio cambió o puede cambiar
  }
  function cerrarSesionLocal() {
    state.token = null; safeSet(TOKEN_KEY, null);
    state.socio = null; state.visitaId = null; guardarCache(null);
    state.ranking = {};
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
    if (!CMS_PREVIEW) iniciarPasaporte();
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
    anclasMaridaje();
    $('#cargando').remove();
    $$('main > .msec, #pie').forEach((s) => { s.hidden = false; });
    scrollSpy();
    // Si se llegó con un ancla a una sección o platillo, recoloca la vista ya con contenido.
    const hash = location.hash.slice(1);
    if (hash && hash !== 'pasaporte') { const t = document.getElementById(hash); if (t) t.scrollIntoView(); }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
