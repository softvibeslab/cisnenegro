/* Tablero de estrategia de contenido (solo lectura).
 * Lee la instantánea publicada desde el Hub (/cms/hub/presentacion.json) y, si no existe,
 * la semilla exportada (data.json, generada por deploy/build_estrategia.py).
 * Todo el contenido de datos se inserta como texto (nunca como HTML). */
(() => {
  'use strict';

  // ------------------------------------------------------------------ constantes
  const VISTAS = [
    ['inicio', 'Inicio', 'Piloto de temporada', 'home'],
    ['planner', 'Planner', 'Calendario de publicaciones', 'calendar'],
    ['parrilla', 'Parrilla', 'Todas las piezas', 'table'],
    ['matriz', 'Matriz', 'Pilares, redes y semanas', 'grid'],
    ['temporada', 'Temporada', 'Festividades del piloto', 'spark'],
    ['laboratorio', 'Laboratorio', 'Pruebas R1–R3 del método', 'flask'],
    ['estrategia', 'Estrategia', 'Método, pilares y secciones', 'layers'],
    ['canales', 'Canales', 'Rol y cadencia de cada red', 'share'],
    ['cumplimiento', 'Cumplimiento', 'COFEPRIS y reglas de temporada', 'shield'],
  ];
  const PRESENTACION = ['inicio', 'temporada', 'planner', 'matriz', 'laboratorio', 'estrategia', 'canales', 'cumplimiento'];
  const ESTADOS = [
    ['idea', 'Idea', '#6b645a'], ['borrador', 'Borrador', '#8a7f6f'], ['revision', 'En revisión', '#f2c97d'],
    ['observada', 'Observada', '#ff9a83'], ['aprobada', 'Aprobada', '#b7c46a'], ['programada', 'Programada', '#38bdf8'],
    ['publicada', 'Publicada', '#22c55e'], ['error', 'Error', '#ef4444'],
  ];
  const OBJETIVOS = { alcance: 'Alcance', comunidad: 'Comunidad', visita: 'Visita' };
  const ESTADO_PRUEBA = { no_empezada: 'No empezada', empezada: 'Empezada', vigente: 'Vigente', no_funciono: 'No funcionó' };
  const METODO_PUB = { manual: 'Asistida (manual)', meta_api: 'API de Meta', postiz: 'Postiz' };
  const COLORES_CAMPANA = ['#ff7a3d', '#f2c97d', '#c08b5c', '#a78bfa', '#38bdf8', '#fb7185'];
  const PASOS = [
    ['W0', 'Insumos', 'Línea base, reseñas e inventario de medios'],
    ['W1', 'Pilares y tópicos', 'Taller con los dueños'],
    ['W2', 'Ideas y secciones', 'Secciones con periodicidad'],
    ['W3', 'Temas por sección', '10 títulos con gancho'],
    ['W4', 'Formato y plantilla', 'Se diseña una vez y se reutiliza'],
    ['W5', 'Cumplimiento', 'Checklist COFEPRIS por pieza'],
    ['W6', 'Aprobación', 'El dueño aprueba desde un enlace'],
    ['W7', 'Prueba R1–R3', 'Contra la interacción ideal'],
    ['W8', 'Seguimiento', 'Normal, buena, saturada o agotada'],
  ];
  const CHECKLIST = [
    ['Leyenda sanitaria', 'Toda pieza que habla de cerveza lleva «EVITE EL EXCESO» al pie del texto y en la última lámina o toma.'],
    ['Nadie bebiendo en cuadro', 'Ni con el vaso en la mano. Barriles, latas y vasos solos sobre la barra sí.'],
    ['Personas de 25 años o más', 'Staff o clientes solo con permiso, mayores de 25 y sin consumo.'],
    ['Sin imperativos de consumo', 'Nada de «tómate», «pide» o «ven por tu chela»: se informa, no se ordena.'],
    ['Sin asociaciones prohibidas', 'La cerveza no va en la misma frase que fiesta, éxito, música, arte o deporte.'],
    ['Datos verificados', 'Estilos, ABV, maridajes, fechas y precios confirmados con el cliente antes de aprobar.'],
  ];
  const REGLAS_TEMPORADA = [
    'La palabra Halloween nunca va en la misma frase que la cerveza; el premio del concurso es sin alcohol.',
    'Día de Muertos: la ofrenda de los perrhijos no lleva cerveza; la ofrenda a las etiquetas sale solo con visto bueno legal.',
    'El Lunes de producción del 2 de noviembre no se relaciona con la festividad.',
    'Día Internacional de la Stout: la efeméride va sola en su propia frase.',
    'Buen Fin: promociones solo de comida o de growler revisado; nada de «barra libre».',
    'El 20 de noviembre es una fecha cívica y no se asocia a la cerveza.',
    'Los sábados solo hay stories: el feed descansa.',
  ];

  const ICONOS = {
    instagram: '<svg viewBox="0 0 24 24"><rect x="3.5" y="3.5" width="17" height="17" rx="5"/><circle cx="12" cy="12" r="3.8"/><circle cx="17.3" cy="6.7" r=".7" fill="currentColor"/></svg>',
    facebook: '<svg viewBox="0 0 24 24"><path d="M14.5 21v-7.5h2.6l.4-3h-3V8.7c0-.9.3-1.5 1.6-1.5h1.5V4.6c-.3 0-1.2-.1-2.3-.1-2.3 0-3.8 1.4-3.8 3.9v2.1H9v3h2.5V21"/></svg>',
    tiktok: '<svg viewBox="0 0 24 24"><path d="M14 4v10.6a3.6 3.6 0 1 1-3.6-3.6"/><path d="M14 4c.4 2.6 2.4 4.4 5 4.6"/></svg>',
    threads: '<svg viewBox="0 0 24 24"><path d="M16.4 11.2c-.3-2.6-1.9-3.9-4.3-3.9-2.6 0-4.2 1.9-4.2 4.7s1.6 4.8 4.3 4.8c2.3 0 3.7-1.2 3.7-3 0-2.3-2.7-2.9-4.8-2.4"/><path d="M19.5 9c-.9-3.4-3.7-5.5-7.4-5.5-4.9 0-8.1 3.4-8.1 8.5s3.2 8.5 8.1 8.5c3.3 0 5.6-1.5 6.8-4"/></svg>',
    youtube: '<svg viewBox="0 0 24 24"><rect x="2.5" y="5.5" width="19" height="13" rx="4"/><path d="M10.2 9.3v5.4l4.6-2.7z" fill="currentColor"/></svg>',
    google: '<svg viewBox="0 0 24 24"><path d="M20 12.2h-7.6"/><path d="M20 12.2A8 8 0 1 1 17.6 6.4"/></svg>',
    whatsapp: '<svg viewBox="0 0 24 24"><path d="M4 20l1.3-4.1A8 8 0 1 1 8.3 19z"/><path d="M9.2 8.8c.3 2.6 2.4 4.9 5.2 5.6l1-1.2-1.6-.9-.8.6c-1-.4-1.9-1.3-2.3-2.3l.6-.8-.8-1.6z" fill="currentColor" stroke="none"/></svg>',
    home: '<svg viewBox="0 0 24 24"><path d="M4 11l8-6.5 8 6.5"/><path d="M6 10v9.5h12V10"/></svg>',
    calendar: '<svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="15" rx="3"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>',
    table: '<svg viewBox="0 0 24 24"><rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><path d="M3.5 9.5h17M3.5 14.5h17M9 9.5v10"/></svg>',
    grid: '<svg viewBox="0 0 24 24"><rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/></svg>',
    spark: '<svg viewBox="0 0 24 24"><path d="M12 3.5l2.1 5.4 5.4 2.1-5.4 2.1L12 18.5l-2.1-5.4L4.5 11l5.4-2.1z"/></svg>',
    flask: '<svg viewBox="0 0 24 24"><path d="M9.5 3.5h5M10.5 3.5v5.2L5.2 18a1.8 1.8 0 0 0 1.6 2.5h10.4a1.8 1.8 0 0 0 1.6-2.5l-5.3-9.3V3.5"/><path d="M7.8 14.5h8.4"/></svg>',
    layers: '<svg viewBox="0 0 24 24"><path d="M12 4l8.5 4.5L12 13 3.5 8.5z"/><path d="M3.5 12.5L12 17l8.5-4.5M3.5 16.5L12 21l8.5-4.5"/></svg>',
    share: '<svg viewBox="0 0 24 24"><circle cx="6.5" cy="12" r="2.5"/><circle cx="17.5" cy="6" r="2.5"/><circle cx="17.5" cy="18" r="2.5"/><path d="M8.7 10.8l6.6-3.6M8.7 13.2l6.6 3.6"/></svg>',
    shield: '<svg viewBox="0 0 24 24"><path d="M12 3.5l7 2.8v5.2c0 4.4-3 7.8-7 9-4-1.2-7-4.6-7-9V6.3z"/><path d="M8.8 12l2.2 2.2 4.2-4.4"/></svg>',
  };

  const IMG = '/assets/img/';
  const CERVEZAS = [['alarma', /alarma/], ['agua-puerca', /agua puerca/], ['barrilete-cosmico', /barrilete/],
    ['a-poco-si-pa', /a poco si/], ['guamaica', /guamaica/], ['henry-ix', /henry/]];
  const ETIQUETAS = new Set(['alarma', 'a-poco-si-pa', 'barrilete-cosmico']);
  const COMIDA = [[/tlayuda/, 'menu/tlayuda.jpg'], [/camarones/, 'menu/camarones_piedra.jpg'], [/palomitas/, 'menu/palomitas.jpg'],
    [/taco de pescado/, 'menu/taco_pescado.jpg'], [/suadero/, 'menu/san_suadero.jpg'], [/costilla/, 'menu/hamburguesa_de_costilla.jpg'],
    [/hamburguesa/, 'menu/hamburguesa_cisne2.jpg'], [/ceviche/, 'menu/ceviche_de_atun.jpg'], [/postres/, 'menu/pastel_helado_de_campechanas.jpg']];
  const POSTERS = new Set(['resena-voz-alta', 'agenda-evento', 'ranking-pasaporte', 'si-haz', 'stories-en-vivo']);

  // ------------------------------------------------------------------ utilidades
  const $ = (s, root = document) => root.querySelector(s);
  function el(tag, attrs, ...hijos) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') n.className = v;
      else if (k === 'style') for (const [p, val] of Object.entries(v)) n.style.setProperty(p, val);
      else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? '' : v);
    }
    for (const h of hijos.flat(Infinity)) {
      if (h == null || h === false) continue;
      n.append(h instanceof Node ? h : document.createTextNode(String(h)));
    }
    return n;
  }
  function icono(nombre, clase = 'ico') {
    const s = el('span', { class: clase, 'aria-hidden': 'true' });
    s.innerHTML = ICONOS[nombre] || ''; // SVG estático de este archivo, nunca datos
    return s;
  }
  const norm = (s) => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const fd = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const sumar = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const lunesDe = (d) => sumar(d, -((d.getDay() + 6) % 7));
  const dias = (a, b) => Math.round((fd(b) - fd(a)) / 864e5);
  const fmt = (s, o) => new Intl.DateTimeFormat('es-MX', o).format(typeof s === 'string' ? fd(s) : s);
  const fechaCorta = (s) => fmt(s, { weekday: 'short', day: 'numeric', month: 'short' });
  const fechaLarga = (s) => fmt(s, { weekday: 'long', day: 'numeric', month: 'long' });
  const diaMes = (s) => fmt(s, { day: 'numeric', month: 'short' });
  const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;

  // ------------------------------------------------------------------ estado
  const S = {
    d: null, fuente: 'semilla', idx: {}, vista: 'inicio',
    filtros: { redes: new Set(), pilar: '', campana: '', q: '' },
    planner: { modo: null, ancla: null },
    parrilla: { tab: 'todas', orden: 'fecha', dir: 1 },
    pres: false, abierta: null, variante: 0, opener: null,
  };

  function preparar(d) {
    const por = (lista) => Object.fromEntries((lista || []).map((x) => [x.clave, x]));
    S.d = d;
    S.idx = {
      canales: por(d.canales), formatos: por(d.formatos), pilares: por(d.pilares), topicos: por(d.topicos),
      secciones: por(d.secciones), campanas: por(d.campanas), plantillas: por(d.plantillas), aliados: por(d.aliados),
      lab: Object.fromEntries((d.laboratorio || []).map((l) => [l.seccion, l])),
    };
    (d.campanas || []).forEach((c, i) => { c._color = COLORES_CAMPANA[i % COLORES_CAMPANA.length]; });
    const orden = (d.canales || []).map((c) => c.clave);
    d.piezas.sort((a, b) => (a.fecha + (a.hora || '')).localeCompare(b.fecha + (b.hora || '')));
    for (const p of d.piezas) {
      p._canales = orden.filter((c) => p.variantes.some((v) => v.canal === c));
      const sec = S.idx.secciones[p.seccion];
      p.pilar = p.pilar || (sec && S.idx.topicos[sec.topico] ? S.idx.topicos[sec.topico].pilar : null);
      p._buscar = norm([p.titulo, p.copy_base, sec && sec.nombre, ...p.variantes.map((v) => v.copy)].join(' '));
    }
    S.filtros.redes = new Set(orden);
  }

  const color = (p) => (S.idx.pilares[p.pilar] || {}).color || '#f2c97d';
  const nombreSeccion = (p) => (S.idx.secciones[p.seccion] || {}).nombre || p.seccion;
  const leyenda = () => S.d.leyenda || (S.d.estrategia || {}).leyenda_sanitaria || 'EVITE EL EXCESO';
  const hablaDeCerveza = (p) => !!(p.atributos && p.atributos.habla_de_cerveza);

  function visibles() {
    const f = S.filtros, q = norm(f.q).trim();
    return S.d.piezas.filter((p) =>
      p._canales.some((c) => f.redes.has(c)) &&
      (!f.pilar || p.pilar === f.pilar) &&
      (!f.campana || p.campana === f.campana) &&
      (!q || q.split(/\s+/).every((t) => p._buscar.includes(t))));
  }
  const filtrosActivos = () => {
    const f = S.filtros;
    return (f.redes.size < S.d.canales.length ? 1 : 0) + (f.pilar ? 1 : 0) + (f.campana ? 1 : 0) + (f.q.trim() ? 1 : 0);
  };
  function semanasPiloto() {
    const out = [];
    for (let d = lunesDe(fd(S.d.piloto.inicio)); iso(d) <= S.d.piloto.fin; d = sumar(d, 7)) out.push(iso(d));
    return out;
  }
  const semanaDe = (fecha) => iso(lunesDe(fd(fecha)));
  const campanasDelDia = (fecha) => (S.d.campanas || []).filter((c) => c.inicio <= fecha && fecha <= c.fin);

  // ------------------------------------------------------------------ piezas: imagen y elementos
  function imagenDe(p) {
    const t = norm(p.titulo);
    const cerveza = (p.atributos && p.atributos.cerveza_destacada) || (CERVEZAS.find(([, re]) => re.test(t)) || [])[0];
    const comida = (COMIDA.find(([re]) => re.test(t)) || [])[1];
    if (/perrhijos|mascotas/.test(t)) return ['ig/pet-friendly-border-collie.jpg', 'Border collie en la terraza del Cisne'];
    if (p.seccion === 'cerveza-para-todos') return ['ig/cerveza-para-todos-neon.jpg', 'Neón #CervezaParaTodos en el taproom'];
    if (/quien te sirve/.test(t)) return ['ig/noche-velas-equipo-neon.jpg', 'El equipo del Cisne bajo el neón'];
    if (/asi quedo/.test(t)) return ['ig/aniversario-primer-cumple.jpg', 'La comunidad del Cisne frente a la fachada'];
    if (POSTERS.has(p.plantilla)) return null;
    if (['maridaje-del-finde', 'el-plato-que-manda'].includes(p.seccion) && comida) return [comida, 'Platillo de la carta'];
    if (p.plantilla === 'volteo-etiqueta' && ETIQUETAS.has(cerveza)) return [`cervezas/etiquetas/${cerveza}.jpg`, 'Arte de la etiqueta'];
    if (cerveza) return [`cervezas/${cerveza}.jpg`, 'Ilustración de la cerveza en el vaso de la casa'];
    if (comida) return [comida, 'Platillo de la carta'];
    return ['lugar/neon.jpg', 'Letrero de neón de Cisne Negro'];
  }

  function poster(p) {
    const lineas = (p.copy_base || '').split('\n').map((l) => l.trim()).filter((l) => l && l !== `${leyenda()}.` && l !== leyenda());
    const sec = nombreSeccion(p);
    const hijos = [el('span', { class: 'kicker' }, sec)];
    if (p.plantilla === 'resena-voz-alta') {
      const m = (p.copy_base || '').match(/«([^»]+)»/);
      hijos.push(el('span', { class: 'estrellas', 'aria-label': 'Cinco estrellas' }, '★★★★★'),
        el('span', { class: 'cita' }, `«${(m ? m[1] : p.titulo).slice(0, 190)}»`), el('span', { class: 'fine' }, 'Reseña de Google'));
    } else {
      const titulo = p.titulo.includes(':') ? p.titulo.split(':').slice(1).join(':').trim() : p.titulo;
      hijos.push(el('span', { class: 'grande' }, titulo), el('span', { class: 'lineas' }, lineas.slice(1, 5).join('\n')));
    }
    if (hablaDeCerveza(p)) hijos.push(el('span', { class: 'leyenda' }, leyenda()));
    return el('div', { class: 'poster' }, hijos);
  }

  function media(p, clase) {
    const img = imagenDe(p);
    const caja = el('div', { class: `pv-media ${clase}` });
    caja.append(img ? el('img', { src: IMG + img[0], alt: img[1], loading: 'lazy', width: '600', height: '750' }) : poster(p));
    return caja;
  }

  function redIcono(clave) {
    const c = S.idx.canales[clave] || { color: '#888', nombre: clave, icono: '' };
    const s = el('span', { class: 'red-icono', style: { '--c': c.color }, title: c.nombre });
    s.append(icono(c.icono, 'ico'), el('span', { class: 'sr-only' }, c.nombre));
    return s;
  }
  const redesDe = (p) => el('span', { class: 'redes' }, p._canales.filter((c) => S.filtros.redes.has(c)).map(redIcono));
  const badgePrueba = (p) => (p.prueba ? el('span', { class: 'badge prueba', title: `Prueba ${p.prueba} del método` }, p.prueba) : null);
  function badgeEstado(p) {
    const e = ESTADOS.find((x) => x[0] === p.estado) || ['', p.estado, '#888'];
    return el('span', { class: 'badge gris' }, el('span', { class: 'punto', style: { '--c': e[2] } }), e[1]);
  }
  const abrir = (p) => (ev) => { S.opener = ev.currentTarget; abrirPieza(p.clave); };

  function ficha(p) {
    return el('button', { class: 'ficha', type: 'button', style: { '--c': color(p) }, onclick: abrir(p) },
      el('span', { class: 'ficha-top' }, el('span', { class: 'mono' }, p.hora || ''), redesDe(p), badgePrueba(p)),
      el('span', { class: 'ficha-titulo' }, p.titulo));
  }
  function itemLista(p, conFecha = true) {
    return el('li', {}, el('button', { class: 'lista-item', type: 'button', onclick: abrir(p) },
      conFecha ? el('span', { class: 'fecha' }, diaMes(p.fecha), el('br'), p.hora || '') : el('span', { class: 'fecha' }, p.hora || ''),
      el('span', { class: 'punto', style: { '--c': color(p) } }),
      el('div', {}, el('strong', {}, p.titulo), el('small', {}, nombreSeccion(p))),
      redesDe(p), badgePrueba(p)));
  }
  function seccionTitulo(titulo, texto, ...extra) {
    return el('div', { class: 'seccion-titulo' }, el('div', {}, el('h2', {}, titulo), texto ? el('p', {}, texto) : null), ...extra);
  }
  const vacio = (texto) => el('div', { class: 'vacio' }, texto || 'No hay piezas con estos filtros.',
    el('div', { class: 'button-row', style: { 'justify-content': 'center', 'margin-top': '12px' } },
      el('button', { class: 'button small secondary', type: 'button', onclick: limpiarFiltros }, 'Quitar filtros')));

  // ------------------------------------------------------------------ vistas
  const VISTA = {};

  VISTA.inicio = (main) => {
    const d = S.d, ps = visibles(), pil = d.piloto || {}, est = d.estrategia || {};
    const variantes = ps.reduce((n, p) => n + p.variantes.filter((v) => S.filtros.redes.has(v.canal)).length, 0);
    const feed = ps.filter((p) => p.variantes.some((v) => ['ig-carrusel', 'ig-reel', 'ig-imagen'].includes(v.formato))).length;
    const pendientes = ps.reduce((n, p) => n + (p.pendientes_validar || 0), 0);
    const conPendientes = ps.filter((p) => p.pendientes_validar).length;
    main.append(el('section', { class: 'bienvenida' },
      el('img', { class: 'sello', src: IMG + 'marca/cisne-mascota.jpg', alt: 'Mascota de Cisne Negro', width: '140', height: '140' }),
      el('p', { class: 'eyebrow' }, `Piloto de temporada · ${plural(pil.semanas || semanasPiloto().length, 'semana', 'semanas')}`),
      el('h2', {}, pil.nombre || 'Piloto de contenido'),
      el('p', {}, `Del ${fechaLarga(pil.inicio)} al ${fechaLarga(pil.fin)} de ${fmt(pil.fin, { year: 'numeric' })}. ${est.objetivo || ''}`),
      est.kpi_estrella ? el('p', {}, el('strong', {}, 'KPI estrella: '), est.kpi_estrella) : null,
      el('div', { class: 'button-row' },
        el('a', { class: 'button primary', href: '#planner' }, 'Ver el calendario →'),
        el('button', { class: 'button secondary', type: 'button', onclick: iniciarPresentacion }, 'Presentar ▶'))));
    main.append(el('div', { class: 'grid cuatro stats' },
      stat('Piezas', ps.length, 'en la parrilla del piloto'),
      stat('Variantes', variantes, 'adaptaciones por red'),
      stat('Feed de Instagram', feed, `publicaciones (meta: ≥3.5 por semana)`),
      stat('Por confirmar', pendientes, `datos con el cliente en ${plural(conPendientes, 'pieza', 'piezas')}`)));

    const hoy = iso(new Date());
    const desde = hoy > pil.inicio && hoy <= pil.fin ? hoy : pil.inicio;
    const proximas = ps.filter((p) => p.fecha >= desde).slice(0, 7);
    const conteo = Object.fromEntries(ESTADOS.map(([k]) => [k, ps.filter((p) => p.estado === k).length]));
    main.append(el('div', { class: 'grid dos', style: { 'margin-top': '20px' } },
      el('section', { class: 'card' }, el('div', { class: 'card-head' }, el('h2', {}, 'Lo que sigue'), el('a', { class: 'button small ghost', href: '#planner' }, 'Planner')),
        proximas.length ? el('ul', { class: 'lista' }, proximas.map((p) => itemLista(p))) : vacio()),
      el('section', { class: 'card' }, el('div', { class: 'card-head' }, el('h2', {}, 'Aprobación'), el('a', { class: 'button small ghost', href: '#parrilla' }, 'Parrilla')),
        el('p', {}, 'Cada pieza pasa por idea → borrador → revisión → aprobada → programada → publicada. El dueño aprueba desde un enlace en el celular.'),
        el('div', { class: 'estado-barra', role: 'img', 'aria-label': ESTADOS.map(([k, n]) => `${n}: ${conteo[k]}`).join(', ') },
          ESTADOS.filter(([k]) => conteo[k]).map(([k, , c]) => el('span', { style: { width: `${(conteo[k] / Math.max(ps.length, 1)) * 100}%`, background: c } }))),
        el('div', { class: 'leyenda-estados' }, ESTADOS.map(([k, n, c]) => el('span', {}, el('span', { class: 'punto', style: { '--c': c } }), `${n}: ${conteo[k]}`))),
        conteo.borrador === ps.length && ps.length ? el('p', { class: 'aviso' }, 'Todas las piezas están en borrador: el equipo las envía a revisión desde el CMS cuando confirma los datos pendientes.') : null)));

    main.append(el('section', { class: 'card', style: { 'margin-top': '20px' } },
      el('div', { class: 'card-head' }, el('h2', {}, 'Temporada'), el('a', { class: 'button small ghost', href: '#temporada' }, 'Ver festividades')),
      el('div', { class: 'button-row' }, (d.campanas || []).map((c) => el('button', {
        class: 'chip', type: 'button', style: { '--c': c._color }, 'aria-pressed': String(S.filtros.campana === c.clave),
        onclick: () => { S.filtros.campana = S.filtros.campana === c.clave ? '' : c.clave; sincronizarFiltros(); render(); },
      }, el('span', { class: 'punto' }), c.nombre, el('span', { class: 'count' }, `${diaMes(c.inicio)}${c.fin !== c.inicio ? ` – ${diaMes(c.fin)}` : ''}`))))));

    const diag = est.diagnostico || {};
    if ((diag.insights || []).length || (diag.debilidades || []).length) {
      main.append(seccionTitulo('De dónde partimos', 'Diagnóstico de la presencia digital que da origen a esta parrilla.'),
        el('div', { class: 'grid dos' },
          el('section', { class: 'card' }, el('h3', { style: { 'margin-bottom': '10px', color: 'var(--lupulo)' } }, 'Lo que funciona'), el('ul', { class: 'bullets' }, (diag.insights || []).map((t) => el('li', {}, t)))),
          el('section', { class: 'card' }, el('h3', { style: { 'margin-bottom': '10px', color: 'var(--danger)' } }, 'Lo que se corrige'), el('ul', { class: 'bullets' }, (diag.debilidades || []).map((t) => el('li', {}, t))))));
    }
  };
  function stat(titulo, numero, texto) {
    return el('div', { class: 'stat' }, el('p', { class: 'eyebrow' }, titulo), el('p', { class: 'stat-num' }, String(numero)), el('p', {}, texto));
  }

  VISTA.planner = (main) => {
    const P = S.planner, pil = S.d.piloto;
    if (!P.modo) P.modo = matchMedia('(max-width: 860px)').matches ? 'lista' : 'mes';
    if (!P.ancla) { const hoy = iso(new Date()); P.ancla = hoy >= pil.inicio && hoy <= pil.fin ? hoy : pil.inicio; }
    const ancla = fd(P.ancla);
    const tabs = el('div', { class: 'tabs', role: 'group', 'aria-label': 'Vista del calendario' },
      [['mes', 'Mes'], ['semana', 'Semana'], ['lista', 'Lista']].map(([k, n]) =>
        el('button', { type: 'button', 'aria-pressed': String(P.modo === k), onclick: () => { P.modo = k; render(); } }, n)));
    const mover = (n) => () => {
      P.ancla = iso(P.modo === 'mes' ? new Date(ancla.getFullYear(), ancla.getMonth() + n, 1) : sumar(ancla, 7 * n));
      render();
    };
    const titulo = P.modo === 'mes' ? fmt(ancla, { month: 'long', year: 'numeric' })
      : P.modo === 'semana' ? `Semana del ${diaMes(iso(lunesDe(ancla)))}` : 'Todo el piloto';
    main.append(el('div', { class: 'toolbar' }, tabs, el('span', { class: 'spacer' }),
      P.modo !== 'lista' ? [el('button', { class: 'icon-button', type: 'button', 'aria-label': 'Anterior', onclick: mover(-1) }, '‹'),
        el('h2', { class: 'mes-titulo', 'aria-live': 'polite' }, titulo),
        el('button', { class: 'icon-button', type: 'button', 'aria-label': 'Siguiente', onclick: mover(1) }, '›'),
        el('button', { class: 'button small ghost', type: 'button', onclick: () => { P.ancla = pil.inicio; render(); } }, 'Inicio del piloto')] : null));
    const ps = visibles();
    if (!ps.length) { main.append(vacio()); return; }
    const porDia = {};
    for (const p of ps) (porDia[p.fecha] = porDia[p.fecha] || []).push(p);
    const hoy = iso(new Date());

    if (P.modo === 'mes') {
      const primero = new Date(ancla.getFullYear(), ancla.getMonth(), 1);
      const ultimo = new Date(ancla.getFullYear(), ancla.getMonth() + 1, 0);
      const cal = el('div', { class: 'cal' },
        ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'].map((n) => el('div', { class: 'cal-dow', 'aria-hidden': 'true' }, n)));
      for (let d = lunesDe(primero); d <= ultimo || d.getDay() !== 1; d = sumar(d, 1)) {
        const f = iso(d), lista = porDia[f] || [];
        const fuera = d.getMonth() !== ancla.getMonth();
        const enPiloto = f >= pil.inicio && f <= pil.fin;
        const celda = el('div', { class: `cal-dia${fuera ? ' fuera' : ''}${!enPiloto && !fuera ? ' fuera-piloto' : ''}` },
          el('span', { class: 'cal-num' }, el('span', { class: 'sr-only' }, fechaLarga(f)), el('span', { class: f === hoy ? 'hoy' : '', 'aria-hidden': 'true' }, String(d.getDate())),
            lista.length ? el('span', { class: 'count' }, lista.length) : null),
          campanasDelDia(f).filter((c) => c.inicio === f || d.getDay() === 1).map((c) => el('span', { class: 'cal-campana', style: { '--c': c._color }, title: c.nombre }, c.nombre)));
        const max = 4;
        lista.slice(0, max).forEach((p) => celda.append(ficha(p)));
        if (lista.length > max) celda.append(el('button', { class: 'mas', type: 'button', onclick: () => { P.modo = 'semana'; P.ancla = f; render(); } }, `+${lista.length - max} más`));
        cal.append(celda);
      }
      main.append(cal, el('p', { class: 'fine', style: { 'margin-top': '10px' } }, 'Las franjas de color marcan cada festividad; los días rayados quedan fuera del piloto. El color del borde de cada pieza indica su pilar.'));
    } else if (P.modo === 'semana') {
      const lun = lunesDe(ancla);
      main.append(el('div', { class: 'semana' }, [0, 1, 2, 3, 4, 5, 6].map((i) => {
        const f = iso(sumar(lun, i));
        return el('section', { class: 'semana-col', 'aria-label': fechaLarga(f) },
          el('h3', {}, fmt(f, { weekday: 'long' }), el('strong', {}, String(fd(f).getDate())),
            campanasDelDia(f).map((c) => el('span', { class: 'cal-campana', style: { '--c': c._color } }, c.nombre))),
          (porDia[f] || []).map(tarjeta), !(porDia[f] || []).length ? el('p', { class: 'fine' }, fd(f).getDay() === 6 ? 'Solo stories' : '—') : null);
      })));
    } else {
      Object.keys(porDia).sort().forEach((f) => main.append(el('section', { class: 'agenda-dia' },
        el('h3', {}, fechaLarga(f), campanasDelDia(f).map((c) => el('span', { class: 'cal-campana', style: { '--c': c._color } }, c.nombre))),
        el('ul', { class: 'lista card', style: { padding: '0 14px' } }, porDia[f].map((p) => itemLista(p, false))))));
    }
  };
  function tarjeta(p) {
    const img = imagenDe(p);
    return el('button', { class: 'tarjeta', type: 'button', style: { '--c': color(p) }, onclick: abrir(p) },
      el('span', { class: 'tarjeta-media' }, img ? el('img', { src: IMG + img[0], alt: '', loading: 'lazy', width: '400', height: '300' })
        : el('span', { class: 'poster-mini' }, nombreSeccion(p))),
      el('span', { class: 'tarjeta-body' }, el('span', { class: 'ficha-top' }, el('span', { class: 'mono' }, p.hora || ''), redesDe(p), badgePrueba(p)),
        el('strong', {}, p.titulo), el('span', { class: 'fine' }, nombreSeccion(p))));
  }

  VISTA.parrilla = (main) => {
    const R = S.parrilla;
    const TABS = [['todas', 'Todas', () => true], ['pruebas', 'Pruebas R1–R3', (p) => p.prueba],
      ['pendientes', 'Con datos por confirmar', (p) => p.pendientes_validar], ['temporada', 'De temporada', (p) => p.campana],
      ['sin-cerveza', 'Sin cerveza', (p) => !hablaDeCerveza(p)]];
    const base = visibles();
    const filtro = (TABS.find((t) => t[0] === R.tab) || TABS[0])[2];
    const ps = base.filter(filtro);
    const claves = { fecha: (p) => p.fecha + (p.hora || ''), seccion: (p) => nombreSeccion(p), pilar: (p) => (S.idx.pilares[p.pilar] || {}).nombre || '', pendientes: (p) => String(p.pendientes_validar || 0).padStart(3, '0') };
    ps.sort((a, b) => claves[R.orden](a).localeCompare(claves[R.orden](b), 'es') * R.dir);
    main.append(el('div', { class: 'toolbar' },
      el('div', { class: 'tabs', role: 'group', 'aria-label': 'Filtrar parrilla' }, TABS.map(([k, n, f]) =>
        el('button', { type: 'button', 'aria-pressed': String(R.tab === k), onclick: () => { R.tab = k; render(); } }, n, ' ', el('span', { class: 'count' }, base.filter(f).length)))),
      el('span', { class: 'spacer' }),
      el('button', { class: 'button small secondary', type: 'button', onclick: () => exportarCSV(ps) }, 'Exportar CSV')));
    if (!ps.length) { main.append(vacio()); return; }
    const th = (k, n) => {
      if (!claves[k]) return el('th', { scope: 'col' }, n);
      const sort = R.orden === k ? (R.dir > 0 ? 'ascending' : 'descending') : 'none';
      return el('th', { scope: 'col', 'aria-sort': sort }, el('button', { type: 'button', onclick: () => { R.dir = R.orden === k ? -R.dir : 1; R.orden = k; render(); } }, n));
    };
    main.append(el('div', { class: 'table-wrap' }, el('table', {},
      el('caption', { class: 'sr-only' }, `Parrilla de contenido: ${plural(ps.length, 'pieza', 'piezas')}`),
      el('thead', {}, el('tr', {}, th('fecha', 'Fecha'), th(null, 'Pieza'), th('seccion', 'Sección'), th('pilar', 'Pilar'), th(null, 'Redes'),
        th(null, 'Prueba'), th(null, 'Objetivo'), th(null, 'Estado'), th('pendientes', 'Por confirmar'))),
      el('tbody', {}, ps.map((p) => el('tr', {},
        el('td', { class: 'nowrap' }, el('span', { class: 'mono' }, fechaCorta(p.fecha)), el('small', {}, p.hora || '')),
        el('td', {}, el('button', { class: 'link', type: 'button', onclick: abrir(p) }, p.titulo),
          p.campana ? el('small', {}, (S.idx.campanas[p.campana] || {}).nombre) : null),
        el('td', {}, nombreSeccion(p)),
        el('td', { class: 'nowrap' }, el('span', { class: 'punto', style: { '--c': color(p) } }), ' ', (S.idx.pilares[p.pilar] || {}).nombre || '—'),
        el('td', {}, redesDe(p)),
        el('td', {}, badgePrueba(p) || '—'),
        el('td', {}, OBJETIVOS[p.objetivo] || p.objetivo || '—'),
        el('td', {}, badgeEstado(p)),
        el('td', { class: 'mono' }, p.pendientes_validar ? String(p.pendientes_validar) : '✓')))))));
  };

  function exportarCSV(ps) {
    const seguro = (v) => { let s = String(v == null ? '' : v); if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`; return `"${s.replace(/"/g, '""')}"`; };
    const filas = [['fecha', 'hora', 'pieza', 'seccion', 'pilar', 'festividad', 'prueba', 'objetivo', 'estado', 'redes', 'formatos', 'por_confirmar', 'texto_base']];
    for (const p of ps) filas.push([p.fecha, p.hora, p.titulo, nombreSeccion(p), (S.idx.pilares[p.pilar] || {}).nombre, (S.idx.campanas[p.campana] || {}).nombre,
      p.prueba, OBJETIVOS[p.objetivo] || p.objetivo, p.estado, p._canales.map((c) => (S.idx.canales[c] || {}).nombre).join(' · '),
      p.variantes.map((v) => (S.idx.formatos[v.formato] || {}).nombre || v.formato).join(' · '), p.pendientes_validar || 0, p.copy_base]);
    const blob = new Blob(['\uFEFF' + filas.map((f) => f.map(seguro).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const a = el('a', { href: URL.createObjectURL(blob), download: `parrilla-cisne-negro-${S.d.piloto.inicio}.csv` });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  VISTA.matriz = (main) => {
    const ps = visibles(), sem = semanasPiloto();
    if (!ps.length) { main.append(vacio()); return; }
    const inicio = S.d.piloto.inicio;
    const cabecera = () => sem.map((s, i) => el('div', { class: 'heat-cab' }, `S${i}`, el('br'), diaMes(s < inicio ? inicio : s)));
    const heat = (filas) => {
      const max = Math.max(1, ...filas.flatMap((f) => f.valores));
      return el('div', { class: 'heat', style: { 'grid-template-columns': `minmax(110px,170px) repeat(${sem.length}, minmax(44px,1fr))` } },
        el('div', {}), cabecera(), filas.map((f) => [el('div', { class: 'heat-fila' }, f.etiqueta),
          f.valores.map((v, i) => el('div', { class: `heat-celda${v ? '' : ' cero'}${v / max > 0.55 ? ' intensa' : ''}`, style: { '--c': f.color, '--p': `${v ? Math.round((0.18 + 0.67 * (v / max)) * 100) : 0}%` },
            title: `${f.texto} · semana del ${diaMes(sem[i])}: ${v}` }, el('span', { class: 'sr-only' }, `${f.texto}, semana del ${diaMes(sem[i])}: `), String(v)))]));
    };
    const pilares = S.d.pilares.map((pl) => ({
      etiqueta: [el('span', { class: 'punto', style: { '--c': pl.color } }), pl.nombre], texto: pl.nombre, color: pl.color,
      valores: sem.map((s) => ps.filter((p) => p.pilar === pl.clave && semanaDe(p.fecha) === s).length),
    }));
    const redes = S.d.canales.filter((c) => S.filtros.redes.has(c.clave)).map((c) => ({
      etiqueta: [redIcono(c.clave), c.nombre], texto: c.nombre, color: c.color,
      valores: sem.map((s) => ps.reduce((n, p) => n + p.variantes.filter((v) => v.canal === c.clave && semanaDe(v.fecha || p.fecha) === s).length, 0)),
    }));
    main.append(seccionTitulo('Pilar × semana', 'Cuántas piezas lleva cada pilar por semana. S0 es el arranque del sábado 24 de octubre.'), el('div', { class: 'card' }, heat(pilares)));
    main.append(seccionTitulo('Red × semana', 'Variantes por red y semana, contra la cadencia de cada canal (ver Canales).'), el('div', { class: 'card' }, heat(redes)));
    const total = ps.length;
    main.append(el('div', { class: 'grid dos', style: { 'margin-top': '20px' } },
      el('section', { class: 'card' }, el('div', { class: 'card-head' }, el('h2', {}, 'Equilibrio de pilares')),
        el('p', { style: { 'margin-bottom': '16px' } }, 'La barra es el reparto real del piloto; la marca blanca, el objetivo del plan.'),
        el('div', { class: 'barras' }, S.d.pilares.map((pl) => {
          const real = Math.round((ps.filter((p) => p.pilar === pl.clave).length / total) * 100);
          return el('div', { class: 'barra-fila' }, el('span', {}, pl.nombre),
            el('div', { class: 'barra-pista', role: 'img', 'aria-label': `${pl.nombre}: ${real}% real contra ${pl.objetivo_pct}% objetivo` },
              el('div', { class: 'barra-real', style: { width: `${real}%`, '--c': pl.color } }), el('div', { class: 'barra-meta', style: { left: `${pl.objetivo_pct}%` } })),
            el('span', { class: 'mono' }, `${real}% / ${pl.objetivo_pct}%`));
        }))),
      el('section', { class: 'card' }, el('div', { class: 'card-head' }, el('h2', {}, 'Para qué sirve cada pieza')),
        el('p', { style: { 'margin-bottom': '16px' } }, 'El KPI estrella son las visitas: la mitad de la parrilla empuja a venir al Cisne.'),
        el('div', { class: 'barras' }, Object.entries(OBJETIVOS).map(([k, n], i) => {
          const c = ps.filter((p) => p.objetivo === k).length, pct = Math.round((c / total) * 100);
          return el('div', { class: 'barra-fila' }, el('span', {}, n),
            el('div', { class: 'barra-pista', role: 'img', 'aria-label': `${n}: ${c} piezas (${pct}%)` }, el('div', { class: 'barra-real', style: { width: `${pct}%`, '--c': ['#38bdf8', '#a78bfa', '#ff7a3d'][i] } })),
            el('span', { class: 'mono' }, `${c} · ${pct}%`));
        })))));
  };

  VISTA.temporada = (main) => {
    const pil = S.d.piloto, total = dias(pil.inicio, pil.fin) + 1, ps = visibles();
    if (pil.nota) main.append(el('p', { class: 'aviso', style: { 'margin-top': 0, 'margin-bottom': '20px' } }, pil.nota));
    const pos = (f) => (Math.min(Math.max(dias(pil.inicio, f), 0), total) / total) * 100;
    const ticks = [];
    for (let i = 0; i < total; i += 7) ticks.push(iso(sumar(fd(pil.inicio), i)));
    main.append(el('div', { class: 'gantt', role: 'img', 'aria-label': (S.d.campanas || []).map((c) => `${c.nombre}: del ${diaMes(c.inicio)} al ${diaMes(c.fin)}`).join('; ') },
      el('div', { class: 'gantt-eje', 'aria-hidden': 'true' }, ticks.map((t) => el('span', { style: { left: `${pos(t)}%` } }, diaMes(t)))),
      (S.d.campanas || []).map((c) => el('div', { class: 'gantt-fila' }, el('span', { class: 'gantt-nombre' }, c.nombre),
        el('div', { class: 'gantt-pista' }, el('div', { class: 'gantt-barra', style: { left: `${pos(c.inicio)}%`, width: `${Math.max(((dias(c.inicio, c.fin) + 1) / total) * 100, 6)}%`, '--c': c._color } },
          c.inicio === c.fin ? diaMes(c.inicio) : `${diaMes(c.inicio)} – ${diaMes(c.fin)}`))))));
    main.append(el('div', { class: 'grid dos', style: { 'margin-top': '20px' } }, (S.d.campanas || []).map((c) => {
      const piezas = ps.filter((p) => p.campana === c.clave);
      return el('section', { class: 'card campana-card', style: { '--c': c._color } },
        el('h2', {}, c.nombre), el('p', { class: 'fechas' }, c.inicio === c.fin ? fechaLarga(c.inicio) : `${fechaLarga(c.inicio)} → ${fechaLarga(c.fin)}`),
        el('p', {}, c.objetivo), piezas.length ? el('ul', { class: 'lista', style: { 'margin-top': '12px' } }, piezas.map((p) => itemLista(p))) : el('p', { class: 'fine', style: { 'margin-top': '10px' } }, 'Sin piezas con los filtros actuales.'));
    })));
  };

  VISTA.laboratorio = (main) => {
    const ps = visibles();
    main.append(el('p', { class: 'aviso', style: { 'margin-top': 0 } },
      'Cada sección se prueba tres veces (R1, R2 y R3). Una prueba cumple si llega al 100% de la interacción ideal de su formato, medida a las 24 horas. Con 2 de 3 la sección queda vigente; con 2 de 3 abajo, no funcionó. Si R1 falla, antes de R2 se cambia la hora, la plantilla o el formato.'));
    const secciones = {};
    for (const p of ps.filter((x) => x.prueba)) (secciones[p.seccion] = secciones[p.seccion] || {})[p.prueba] = p;
    const claves = Object.keys(secciones).sort((a, b) => Object.values(secciones[a])[0].fecha.localeCompare(Object.values(secciones[b])[0].fecha));
    if (!claves.length) { main.append(vacio('Ninguna prueba coincide con los filtros.')); return; }
    main.append(el('div', { class: 'grid dos', style: { 'margin-top': '20px' } }, claves.map((k) => {
      const s = S.idx.secciones[k] || { nombre: k }, lab = S.idx.lab[k] || {};
      const pl = S.idx.pilares[(S.idx.topicos[s.topico] || {}).pilar] || {};
      const ideal = s.interaccion_ideal || lab.interaccion_ideal || (S.idx.formatos[s.formato] || {}).interaccion_ideal;
      return el('section', { class: 'card pilar', style: { '--c': pl.color || '#f2c97d' } },
        el('div', { class: 'card-head' }, el('div', {}, el('h2', {}, s.nombre), el('p', { class: 'fine' }, s.periodicidad || '')),
          el('span', { class: 'badge gris' }, ESTADO_PRUEBA[lab.estado_prueba || s.estado_prueba] || 'No empezada')),
        el('p', { class: 'fine' }, ideal ? `Interacción ideal: ${Math.round(ideal)} (likes + comentarios + compartidos + guardados)` : 'Interacción ideal por calibrar con Insights'),
        el('div', { class: 'pruebas' }, ['R1', 'R2', 'R3'].map((r) => {
          const p = secciones[k][r], res = (lab.pruebas || {})[r];
          if (!p) return el('div', { class: 'prueba-slot vacia' }, el('span', { class: 'badge gris' }, r), el('p', {}, 'Queda para diciembre'));
          return el('div', { class: 'prueba-slot' }, el('span', { class: 'badge prueba' }, r),
            el('button', { type: 'button', onclick: abrir(p) }, p.titulo),
            el('small', {}, `${fechaCorta(p.fecha)} · ${p.hora || ''}`),
            el('small', {}, res && res.pct != null ? `${res.interaccion} / ${Math.round(res.ideal)} · ${Math.round(res.pct)}% · ${res.resultado}` : 'Por medir a las 24 h'));
        })));
    })));
  };

  VISTA.estrategia = (main) => {
    const ps = visibles();
    main.append(seccionTitulo('El método', 'De la línea base al seguimiento: cada paso tiene un entregable y una compuerta de calidad.'),
      el('div', { class: 'metodo' }, PASOS.map(([n, t, d]) => el('div', { class: 'paso' }, el('span', { class: 'mono' }, n), el('strong', {}, t), el('span', { class: 'fine' }, d)))));
    main.append(seccionTitulo('Pilares, tópicos y secciones', 'Cuatro pilares con su porcentaje objetivo. Las secciones marcadas entran a prueba en el piloto.'),
      el('div', { class: 'grid dos' }, S.d.pilares.map((pl) => el('section', { class: 'card pilar', style: { '--c': pl.color } },
        el('div', { class: 'card-head' }, el('h2', {}, pl.nombre), el('span', { class: 'pct' }, `${pl.objetivo_pct}%`)),
        el('p', {}, pl.descripcion),
        S.d.topicos.filter((t) => t.pilar === pl.clave).map((t) => el('div', { class: 'topico' }, el('h3', {}, t.nombre),
          S.d.secciones.filter((s) => s.topico === t.clave).map((s) => {
            const n = ps.filter((p) => p.seccion === s.clave).length;
            return el('div', { class: 'seccion-item' }, el('div', {}, el('strong', {}, s.nombre), el('small', {}, s.periodicidad || '')),
              el('div', { style: { display: 'flex', gap: '6px', 'align-items': 'center', 'flex-wrap': 'wrap', 'justify-content': 'flex-end' } },
                s.en_piloto ? el('span', { class: 'badge verde' }, 'En piloto') : null,
                el('span', { class: 'count' }, plural(n, 'pieza', 'piezas'))));
          })))))));
  };

  VISTA.canales = (main) => {
    const ps = visibles();
    main.append(el('div', { class: 'grid tres' }, S.d.canales.map((c) => {
      const n = ps.reduce((t, p) => t + p.variantes.filter((v) => v.canal === c.clave).length, 0);
      const formatos = S.d.formatos.filter((f) => f.canal === c.clave).map((f) => f.nombre).join(' · ');
      const ic = redIcono(c.clave);
      return el('section', { class: 'card' }, el('div', { class: 'canal-cab' }, ic, el('div', {}, el('h2', {}, c.nombre), el('p', { class: 'fine' }, c.handle || ''))),
        el('dl', { class: 'dl' }, el('dt', {}, 'Rol'), el('dd', {}, c.rol || '—'), el('dt', {}, 'Cadencia'), el('dd', {}, c.cadencia || '—'),
          el('dt', {}, 'Publicación'), el('dd', {}, METODO_PUB[c.metodo] || c.metodo || '—'), el('dt', {}, 'Formatos'), el('dd', {}, formatos || '—'),
          el('dt', {}, 'En el piloto'), el('dd', {}, plural(n, 'variante', 'variantes'))));
    })));
  };

  VISTA.cumplimiento = (main) => {
    const ps = visibles(), conCerveza = ps.filter(hablaDeCerveza);
    const conLeyenda = conCerveza.filter((p) => (p.copy_base || '').includes(leyenda()));
    main.append(el('div', { class: 'grid dos' },
      el('section', { class: 'card' }, el('div', { class: 'card-head' }, el('h2', {}, 'Checklist por pieza')),
        el('p', {}, 'Es obligatorio: sin los seis puntos la pieza no puede enviarse a revisión. Se marca en el CMS.'),
        el('div', {}, CHECKLIST.map(([t, d], i) => el('div', { class: 'check-item' }, el('span', { class: 'marca', 'aria-hidden': 'true' }, String(i + 1)), el('div', {}, el('strong', {}, t), el('p', {}, d)))))),
      el('div', { class: 'grid', style: { 'align-content': 'start' } },
        el('section', { class: 'card' }, el('h2', {}, 'Leyenda sanitaria'), el('span', { class: 'leyenda-sello' }, leyenda()),
          el('p', { style: { 'margin-top': '14px' } }, `${conLeyenda.length} de ${plural(conCerveza.length, 'pieza que habla', 'piezas que hablan')} de cerveza ya la llevan en el texto base. ${ps.length - conCerveza.length} piezas no hablan de cerveza (comida, mascotas, agenda o Google) y no la necesitan.`),
          conLeyenda.length < conCerveza.length ? el('p', { class: 'aviso' }, `Falta la leyenda en: ${conCerveza.filter((p) => !conLeyenda.includes(p)).map((p) => p.titulo).join(' · ')}`) : el('p', { class: 'aviso ok' }, 'Todas las piezas con cerveza llevan la leyenda.')),
        el('section', { class: 'card' }, el('h2', {}, 'Reglas de temporada'), el('ul', { class: 'bullets', style: { 'margin-top': '12px' } }, REGLAS_TEMPORADA.map((r) => el('li', {}, r)))))));
  };

  // ------------------------------------------------------------------ ficha de pieza (diálogo)
  const dialogo = () => $('#pieza');
  function abrirPieza(clave, actualizarHash = true) {
    const p = S.d.piezas.find((x) => x.clave === clave);
    if (!p) return;
    if (S.abierta !== clave) S.variante = Math.max(0, p.variantes.findIndex((v) => S.filtros.redes.has(v.canal)));
    S.abierta = clave;
    pintarPieza(p);
    const dlg = dialogo();
    if (!dlg.open) dlg.showModal();
    if (actualizarHash) history.replaceState(null, '', `#${S.vista}/pieza/${encodeURIComponent(clave)}`);
  }
  function cerrarPieza(actualizarHash = true) {
    const dlg = dialogo();
    S.abierta = null;
    if (dlg.open) dlg.close();
    if (actualizarHash) history.replaceState(null, '', `#${S.vista}`);
    if (S.opener && document.contains(S.opener)) S.opener.focus();
  }
  function moverPieza(n) {
    const ps = visibles(), i = ps.findIndex((p) => p.clave === S.abierta);
    if (i < 0 || !ps.length) return;
    abrirPieza(ps[(i + n + ps.length) % ps.length].clave);
  }

  function pintarPieza(p) {
    const dlg = dialogo(), v = p.variantes[S.variante] || p.variantes[0];
    const fmtV = S.idx.formatos[v.formato] || { nombre: v.formato };
    const canal = S.idx.canales[v.canal] || { nombre: v.canal, color: '#888' };
    const camp = S.idx.campanas[p.campana], aliado = S.idx.aliados[p.aliado], pl = S.idx.pilares[p.pilar] || {};
    const texto = v.copy || '';
    const tags = (v.hashtags || []).join(' ');
    const largo = texto.length + (tags ? tags.length + 2 : 0);
    const max = fmtV.max_caracteres;
    dlg.replaceChildren(
      el('header', { class: 'dlg-head' },
        el('div', {}, el('p', { class: 'eyebrow', style: { color: 'var(--pico)' } }, `${fechaLarga(p.fecha)} · ${p.hora || ''}`),
          el('h2', { id: 'pieza-titulo' }, p.titulo),
          el('div', { class: 'dlg-meta' },
            el('span', { class: 'badge gris' }, el('span', { class: 'punto', style: { '--c': pl.color || '#888' } }), pl.nombre || 'Sin pilar'),
            el('span', { class: 'badge gris' }, nombreSeccion(p)),
            camp ? el('span', { class: 'badge', style: { background: `color-mix(in srgb, ${camp._color} 22%, transparent)`, color: camp._color } }, camp.nombre) : null,
            badgePrueba(p), el('span', { class: 'badge gris' }, `Objetivo: ${OBJETIVOS[p.objetivo] || p.objetivo || '—'}`),
            aliado ? el('span', { class: 'badge pico' }, `Coautor: ${aliado.nombre}`) : null,
            badgeEstado(p))),
        el('div', { class: 'acciones' },
          el('button', { class: 'icon-button', type: 'button', 'aria-label': 'Pieza anterior', onclick: () => moverPieza(-1) }, '‹'),
          el('button', { class: 'icon-button', type: 'button', 'aria-label': 'Pieza siguiente', onclick: () => moverPieza(1) }, '›'),
          el('button', { class: 'icon-button', type: 'button', 'aria-label': 'Cerrar', onclick: () => cerrarPieza() }, '✕'))),
      el('div', { class: 'dlg-body' },
        el('div', {}, el('div', { class: 'preview' }, vistaPrevia(p, v, canal)),
          imagenDe(p) ? el('p', { class: 'nota-imagen' }, 'Imagen de referencia del archivo del Cisne; la pieza final lleva su propia foto o video.') : null),
        el('div', {},
          el('div', { class: 'dlg-tabs', role: 'tablist', 'aria-label': 'Variantes por red' }, p.variantes.map((x, i) => {
            const c = S.idx.canales[x.canal] || { color: '#888', nombre: x.canal };
            return el('button', { type: 'button', role: 'tab', 'aria-selected': String(i === S.variante), style: { '--c': c.color },
              onclick: () => { S.variante = i; pintarPieza(p); dialogo().querySelector('[role=tab][aria-selected=true]').focus(); } },
            redIcono(x.canal), (S.idx.formatos[x.formato] || {}).nombre || x.formato);
          })),
          el('p', { class: 'eyebrow' }, `Texto para ${canal.nombre} · ${fmtV.nombre}`),
          v.titulo ? el('p', { style: { 'font-weight': '800', margin: '6px 0' } }, v.titulo) : null,
          el('div', { class: 'copy', tabindex: '0', 'aria-label': 'Texto de la publicación' }, texto, tags ? el('div', { class: 'hashtags' }, tags) : null),
          el('div', { class: 'contador' },
            el('span', { class: max && largo > max ? 'exceso' : '' }, max ? `${largo.toLocaleString('es-MX')} / ${max.toLocaleString('es-MX')} caracteres` : `${largo} caracteres`),
            el('span', {}, `Sale ${fechaCorta(v.fecha || p.fecha)} · ${v.hora || p.hora || ''}`)),
          el('div', { class: 'button-row' },
            el('button', { class: 'button small secondary', type: 'button', onclick: (ev) => copiar(texto + (tags ? `\n\n${tags}` : ''), ev.currentTarget) }, 'Copiar texto'),
            el('a', { class: 'button small ghost', href: `#${S.vista}/pieza/${encodeURIComponent(p.clave)}`, onclick: (ev) => { ev.preventDefault(); copiar(location.href, ev.currentTarget, 'Enlace copiado'); } }, 'Copiar enlace')),
          p.pendientes_validar
            ? el('p', { class: 'aviso' }, `${plural(p.pendientes_validar, 'dato por confirmar', 'datos por confirmar')} con el cliente antes de enviarla a aprobación (el detalle está en el CMS).`)
            : el('p', { class: 'aviso ok' }, 'Sin datos por confirmar.'),
          el('p', { class: p.cumplimiento_ok ? 'aviso ok' : 'aviso' }, p.cumplimiento_ok ? 'Checklist COFEPRIS completo.' : 'Checklist COFEPRIS por marcar en el CMS antes de la revisión.'),
          hablaDeCerveza(p) ? el('p', { class: 'fine', style: { 'margin-top': '10px' } }, `Habla de cerveza: lleva «${leyenda()}» en el texto y en la última lámina o toma.`) : null)));
  }

  async function copiar(texto, boton, ok = 'Copiado') {
    const antes = boton.textContent;
    try { await navigator.clipboard.writeText(texto); boton.textContent = `${ok} ✓`; } catch { boton.textContent = 'No se pudo copiar'; }
    setTimeout(() => { boton.textContent = antes; }, 1600);
  }

  function vistaPrevia(p, v, canal) {
    const f = v.formato, tags = (v.hashtags || []).join(' ');
    const handle = String(canal.handle || '@cisnenegro.mx').split(' ')[0].replace(/^\//, '');
    const cuenta = handle.replace(/^@/, '');
    const cab = (sub) => el('div', { class: 'pv-head' }, el('span', { class: 'pv-avatar' }), el('div', {}, cuenta, el('small', {}, sub)));
    const telefono = (...hijos) => el('div', { class: 'phone', role: 'img', 'aria-label': `Vista previa en ${canal.nombre}` }, el('div', { class: 'phone-inner' }, hijos));
    if (['ig-carrusel', 'ig-imagen'].includes(f)) {
      return telefono(cab('Pachuca, Hidalgo'), media(p, 'r45'),
        f === 'ig-carrusel' ? el('div', { class: 'pv-dots', 'aria-hidden': 'true' }, [0, 1, 2, 3, 4].map(() => el('i'))) : null,
        el('div', { class: 'pv-acciones', 'aria-hidden': 'true' }, '♡', '💬', '➤'),
        el('div', { class: 'pv-caption' }, el('b', {}, cuenta), v.copy, tags ? el('div', { class: 'tags' }, tags) : null));
    }
    if (['ig-reel', 'fb-reel', 'tiktok-video', 'tiktok-slideshow', 'yt-short'].includes(f)) {
      const m = media(p, 'r916');
      m.append(el('div', { class: 'pv-lateral', 'aria-hidden': 'true' }, '♡', '💬', '↗'),
        el('div', { class: 'pv-overlay' }, el('b', {}, `@${cuenta}`), (v.titulo ? `${v.titulo}\n` : '') + (v.copy || '').slice(0, 260)));
      return telefono(m);
    }
    if (f === 'ig-story') {
      const m = media(p, 'r916');
      m.append(el('div', { class: 'pv-story-top' }, el('span', { class: 'barra' }), el('span', { class: 'pv-avatar' }), cuenta),
        el('div', { class: 'pv-overlay' }, v.copy));
      return telefono(m);
    }
    if (f.startsWith('fb-')) {
      return telefono(el('div', { class: 'fb' }, el('div', { class: 'pv-head' }, el('span', { class: 'pv-avatar' }),
        el('div', {}, 'Cervecería Cisne Negro', el('small', {}, `Programado · ${fechaCorta(v.fecha || p.fecha)}`))),
      el('div', { class: 'pv-caption' }, v.copy, tags ? el('div', { class: 'tags' }, tags) : null), media(p, 'r45'),
      el('div', { class: 'fb-acciones', 'aria-hidden': 'true' }, el('span', {}, 'Me gusta'), el('span', {}, 'Comentar'), el('span', {}, 'Compartir'))));
    }
    if (f.startsWith('threads-')) {
      return telefono(el('div', { class: 'threads' }, el('span', { class: 'pv-avatar' }),
        el('div', { style: { flex: '1', 'min-width': '0' } }, el('b', {}, cuenta), el('div', { class: 'threads-texto' }, v.copy),
          f === 'threads-imagen' ? el('div', { class: 'threads-img' }, media(p, 'r45')) : null)));
    }
    if (f.startsWith('gbp-')) {
      return telefono(el('div', { class: 'gbp' }, el('div', { class: 'gbp-cab' }, el('span', { class: 'g' }, 'G'),
        el('div', {}, el('b', {}, 'Cisne Negro'), el('small', { style: { display: 'block', color: '#666' } }, 'Publicación en Google'))),
      media(p, 'r43'), el('div', { class: 'gbp-texto' }, v.copy), el('span', { class: 'gbp-boton' }, 'Cómo llegar')));
    }
    if (f === 'wa-aviso') {
      return telefono(el('div', { class: 'wa' }, el('div', { class: 'wa-cab' }, el('span', { class: 'pv-avatar' }),
        el('div', {}, 'Cisne Negro', el('small', {}, 'Canal de WhatsApp'))),
      el('div', { class: 'wa-burbuja' }, v.copy, el('span', { class: 'hora' }, v.hora || p.hora || ''))));
    }
    return telefono(cab(canal.nombre), media(p, 'r45'), el('div', { class: 'pv-caption' }, v.copy));
  }

  // ------------------------------------------------------------------ filtros
  function construirFiltros() {
    const caja = $('#filtro-redes');
    caja.replaceChildren(...S.d.canales.map((c) => el('button', {
      class: 'chip', type: 'button', style: { '--c': c.color }, 'data-red': c.clave, 'aria-pressed': 'true',
      onclick: () => {
        const r = S.filtros.redes;
        if (r.size === S.d.canales.length) { r.clear(); r.add(c.clave); } else if (r.has(c.clave)) r.delete(c.clave); else r.add(c.clave);
        if (!r.size) S.d.canales.forEach((x) => r.add(x.clave));
        sincronizarFiltros(); render();
      },
    }, icono(c.icono), c.nombre)));
    const pilar = $('#filtro-pilar'), campana = $('#filtro-campana');
    S.d.pilares.forEach((p) => pilar.append(el('option', { value: p.clave }, p.nombre)));
    (S.d.campanas || []).forEach((c) => campana.append(el('option', { value: c.clave }, c.nombre)));
    pilar.addEventListener('change', () => { S.filtros.pilar = pilar.value; render(); });
    campana.addEventListener('change', () => { S.filtros.campana = campana.value; render(); });
    let t;
    $('#filtro-q').addEventListener('input', (e) => { clearTimeout(t); t = setTimeout(() => { S.filtros.q = e.target.value; render(); }, 160); });
    $('#filtros-limpiar').addEventListener('click', limpiarFiltros);
    $('#filtros-toggle').addEventListener('click', (e) => {
      const f = $('#filtros'), abierto = f.hidden;
      f.hidden = !abierto; e.currentTarget.setAttribute('aria-expanded', String(abierto));
      if (abierto) $('#filtro-q').focus();
    });
    if (matchMedia('(min-width: 861px)').matches) { $('#filtros').hidden = false; $('#filtros-toggle').setAttribute('aria-expanded', 'true'); }
  }
  function sincronizarFiltros() {
    document.querySelectorAll('[data-red]').forEach((b) => b.setAttribute('aria-pressed', String(S.filtros.redes.has(b.dataset.red))));
    $('#filtro-pilar').value = S.filtros.pilar;
    $('#filtro-campana').value = S.filtros.campana;
    $('#filtro-q').value = S.filtros.q;
    const n = filtrosActivos();
    $('#filtros-count').textContent = n ? `(${n})` : '';
  }
  function limpiarFiltros() {
    S.filtros = { redes: new Set(S.d.canales.map((c) => c.clave)), pilar: '', campana: '', q: '' };
    sincronizarFiltros(); render();
  }

  // ------------------------------------------------------------------ navegación y presentación
  function construirNav() {
    $('#nav').replaceChildren(...VISTAS.map(([k, n, , ic]) => el('a', { class: 'nav-item', href: `#${k}`, 'data-vista': k }, icono(ic), n)));
  }
  function leerHash() {
    const [v, tipo, clave] = decodeURIComponent(location.hash.slice(1)).split('/');
    S.vista = VISTAS.some((x) => x[0] === v) ? v : 'inicio';
    return tipo === 'pieza' ? clave : null;
  }
  function render() {
    const info = VISTAS.find((x) => x[0] === S.vista);
    document.querySelectorAll('.nav-item').forEach((a) => { if (a.dataset.vista === S.vista) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    $('#titulo-vista').textContent = info[1];
    $('#migas').textContent = info[2];
    document.title = `${info[1]} · Estrategia de contenido · Cisne Negro`;
    const main = $('#vista');
    main.replaceChildren();
    VISTA[S.vista](main);
    sincronizarFiltros();
    if (S.pres) $('#pres-pos').textContent = `${PRESENTACION.indexOf(S.vista) + 1} / ${PRESENTACION.length}`;
  }
  function irA(vista) {
    if (S.vista === vista) return;
    location.hash = vista;
  }
  function iniciarPresentacion() {
    S.pres = true;
    document.body.classList.add('presentando');
    $('#presentacion-controles').hidden = false;
    if (!PRESENTACION.includes(S.vista)) S.vista = 'inicio';
    if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen().catch(() => {});
    history.replaceState(null, '', `#${S.vista}`);
    render();
    $('#pres-next').focus();
  }
  function salirPresentacion() {
    if (!S.pres) return;
    S.pres = false;
    document.body.classList.remove('presentando');
    $('#presentacion-controles').hidden = true;
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    render();
  }
  function moverPresentacion(n) {
    const i = PRESENTACION.indexOf(S.vista);
    const j = Math.min(Math.max((i < 0 ? 0 : i) + n, 0), PRESENTACION.length - 1);
    irA(PRESENTACION[j]);
    window.scrollTo({ top: 0 });
  }

  function eventos() {
    window.addEventListener('hashchange', () => {
      const clave = leerHash();
      render();
      if (clave) abrirPieza(clave, false); else if (dialogo().open) cerrarPieza(false);
      if (!S.pres) $('#vista').focus({ preventScroll: true });
      cerrarMenu();
    });
    const dlg = dialogo();
    dlg.addEventListener('cancel', (e) => { e.preventDefault(); cerrarPieza(); });
    dlg.addEventListener('click', (e) => { if (e.target === dlg) cerrarPieza(); });
    document.addEventListener('keydown', (e) => {
      if (e.target.matches && e.target.matches('input, select, textarea')) return;
      if (dlg.open) {
        if (e.key === 'ArrowRight' && !e.target.closest('[role=tablist]')) moverPieza(1);
        if (e.key === 'ArrowLeft' && !e.target.closest('[role=tablist]')) moverPieza(-1);
        return;
      }
      if (!S.pres) return;
      if (['ArrowRight', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); moverPresentacion(1); }
      if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); moverPresentacion(-1); }
      if (e.key === 'Escape') salirPresentacion();
    });
    document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && S.pres) salirPresentacion(); });
    $('#presentar').addEventListener('click', iniciarPresentacion);
    $('#pres-next').addEventListener('click', () => moverPresentacion(1));
    $('#pres-prev').addEventListener('click', () => moverPresentacion(-1));
    $('#pres-salir').addEventListener('click', salirPresentacion);
    $('#menu-toggle').addEventListener('click', () => {
      const abierto = !$('#sidebar').classList.contains('open');
      $('#sidebar').classList.toggle('open', abierto);
      $('#sidebar-backdrop').hidden = !abierto;
      $('#menu-toggle').setAttribute('aria-expanded', String(abierto));
    });
    $('#sidebar-backdrop').addEventListener('click', cerrarMenu);
  }
  function cerrarMenu() {
    $('#sidebar').classList.remove('open');
    $('#sidebar-backdrop').hidden = true;
    $('#menu-toggle').setAttribute('aria-expanded', 'false');
  }

  // ------------------------------------------------------------------ arranque
  async function cargar() {
    const corte = new AbortController();
    const reloj = setTimeout(() => corte.abort(), 4000);
    try {
      const r = await fetch('/cms/hub/presentacion.json', { cache: 'no-store', credentials: 'omit', signal: corte.signal });
      if (r.ok) {
        const d = await r.json();
        if (d && d.tipo === 'hub-presentacion' && Array.isArray(d.piezas)) return [d, 'hub'];
      } else if (r.body) {
        r.body.cancel().catch(() => {}); // sin instantánea publicada: se libera la conexión
      }
    } catch { /* sin Hub publicado o sin respuesta a tiempo: se usa la semilla */ } finally { clearTimeout(reloj); }
    const r = await fetch('data.json', { cache: 'no-cache' });
    if (!r.ok) throw new Error(`data.json respondió ${r.status}`);
    return [await r.json(), 'semilla'];
  }

  async function iniciar() {
    try {
      const [d, fuente] = await cargar();
      S.fuente = fuente;
      preparar(d);
    } catch (err) {
      $('#vista').replaceChildren(el('div', { class: 'vacio' }, el('h2', {}, 'No se pudo cargar el tablero'), el('p', {}, String(err.message || err))));
      $('#fuente').textContent = 'Sin datos';
      return;
    }
    $('#fuente').replaceChildren(el('strong', {}, S.fuente === 'hub' ? 'Publicado desde el Hub' : 'Semilla del piloto'),
      S.fuente === 'hub' ? `Actualizado ${fmt(new Date(S.d.publicado_at), { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}`
        : `Parrilla del ${S.d.generado ? diaMes(S.d.generado) : '—'}. Aún no se publica desde el Hub.`);
    construirNav();
    construirFiltros();
    eventos();
    const clave = leerHash();
    render();
    if (clave) abrirPieza(clave, false);
  }
  iniciar();
})();
