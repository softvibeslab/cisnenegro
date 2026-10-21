/* Cervecería Cisne Negro · App del equipo (/equipo/)
 * Login de meseros y administrador, escaneo del QR del pedido, cuentas por mesa, cobro con propina,
 * historial, corte del mesero, cierre del día y gestión de cuentas.
 * Rutas absolutas (/api, /assets, /equipo): deploy/construir-v2.py las reescribe para /v2.
 */
(function () {
  'use strict';

  const API = '/api/equipo';
  const JSQR_SRC = '/assets/js/lib/jsqr.js?v=20261007a';
  const TZ = 'America/Mexico_City';
  const MET = { efectivo: 'Efectivo', tarjeta_credito: 'Crédito', tarjeta_debito: 'Débito' };
  const MET_LARGO = { efectivo: 'Efectivo', tarjeta_credito: 'Tarjeta de crédito', tarjeta_debito: 'Tarjeta de débito' };
  const MAX_CANT = 20;
  const LIMITE_HIST = 20;

  // ── Funciones puras (también se prueban desde Playwright vía window.CNEquipo) ──────────────

  function limpiarCodigo(c) { return String(c || '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 12); }
  function fmtCodigo(c) { c = limpiarCodigo(c); return c.length === 8 ? c.slice(0, 4) + '-' + c.slice(4) : c; }

  /** Texto escaneado o escrito → {codigo} | {d} | null.
   *  Acepta …/equipo/?p=CÓDIGO, …/equipo/#d=<base64url>, …/equipo/p/CÓDIGO o el código suelto (con o sin guion). */
  function interpretar(texto) {
    const t = String(texto || '').trim();
    if (!t) return null;
    const d = t.match(/#d=([A-Za-z0-9_-]{8,})/) || t.match(/^d=([A-Za-z0-9_-]{8,})$/);
    if (d) return { d: d[1] };
    const p = t.match(/[?&]p=([A-Za-z0-9-]{4,16})(?=[&#]|$)/);
    if (p) return { codigo: limpiarCodigo(p[1]) };
    const r = t.match(/\/equipo\/p\/([A-Za-z0-9-]{4,16})\/?(?=[?#]|$)/);
    if (r) return { codigo: limpiarCodigo(r[1]) };
    if (/^[A-Za-z0-9]{2,8}([-\s][A-Za-z0-9]{2,8})?$/.test(t)) {
      const c = limpiarCodigo(t);
      if (c.length >= 4) return { codigo: c };
    }
    return null;
  }

  /** base64url (sin relleno) de JSON {mesa, lineas} → {mesa, lineas} | null */
  function decodificarDatos(b64) {
    try {
      let s = String(b64 || '').replace(/-/g, '+').replace(/_/g, '/');
      while (s.length % 4) s += '=';
      const bin = atob(s);
      const bytes = Uint8Array.from(bin, (ch) => ch.charCodeAt(0));
      const j = JSON.parse(new TextDecoder().decode(bytes));
      if (!j || !Array.isArray(j.lineas) || !j.lineas.length) return null;
      const lineas = j.lineas.filter((l) => l && typeof l === 'object' && typeof l.tipo === 'string');
      if (!lineas.length) return null;
      const r = { mesa: j.mesa == null ? '' : String(j.mesa).slice(0, 10), lineas };
      if (typeof j.t === 'string' && /^[0-9a-z]{1,12}$/.test(j.t)) r.t = j.t; // marca del QR: el servidor deduplica con ella
      return r;
    } catch (e) {
      return null;
    }
  }

  /** "1,234.50" / "$48.5" → centavos (entero). Vacío → 0. Inválido → NaN. */
  function aCentavos(v) {
    const s = String(v == null ? '' : v).replace(/[$\s,]/g, '');
    if (!s) return 0;
    if (!/^\d+(\.\d{0,2})?$/.test(s)) return NaN;
    return Math.round(parseFloat(s) * 100);
  }

  const API_PURA = { interpretar, decodificarDatos, limpiarCodigo, fmtCodigo, aCentavos };
  if (typeof module === 'object' && module.exports) module.exports = API_PURA;
  if (typeof document === 'undefined') return;
  window.CNEquipo = API_PURA;

  // ── Formato ─────────────────────────────────────────────────────────────

  const fMXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' });
  const $ = (n) => fMXN.format(Number(n) || 0);
  const c$ = (c) => fMXN.format((Number(c) || 0) / 100);
  const fHora = new Intl.DateTimeFormat('es-MX', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: TZ });
  const fDia = new Intl.DateTimeFormat('es-MX', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' });
  const fDiaCorto = new Intl.DateTimeFormat('es-MX', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' });
  const fFechaHora = new Intl.DateTimeFormat('es-MX', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: TZ });
  const hora = (iso) => (iso ? fHora.format(new Date(iso)) : '');
  const diaLargo = (ymd) => (ymd ? fDia.format(new Date(ymd + 'T12:00:00Z')).replace(',', '') : '');
  const diaCorto = (ymd) => (ymd ? fDiaCorto.format(new Date(ymd + 'T12:00:00Z')).replace(/[,.]/g, '') : '');
  const fechaHora = (iso) => (iso ? fFechaHora.format(new Date(iso)).replace(',', '') : '');
  const rondasTxt = (n) => (n === 1 ? '1 ronda' : n + ' rondas');
  const cuentasTxt = (n) => (n === 1 ? '1 cuenta' : n + ' cuentas');
  const fmtNum = (c) => (c / 100).toFixed(2);
  const primerNombre = (n) => String(n || '').split(' ')[0];

  // ── DOM ─────────────────────────────────────────────────────────────────

  const el = (id) => document.getElementById(id);
  function add(e, kids) {
    for (const c of kids.flat(Infinity)) {
      if (c == null || c === false || c === '') continue;
      e.append(c instanceof Node ? c : String(c));
    }
  }
  function h(tag, props, ...kids) {
    const e = document.createElement(tag);
    for (const k in props || {}) {
      const v = props[k];
      if (v == null || v === false) continue;
      if (k === 'class') e.className = v;
      else if (k === 'text') e.textContent = v;
      else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
      else if (k === 'value' || k === 'checked' || k === 'hidden' || k === 'disabled' || k === 'selected') e[k] = v;
      else e.setAttribute(k, v === true ? '' : v);
    }
    add(e, kids);
    return e;
  }
  const NS = 'http://www.w3.org/2000/svg';
  function s(tag, attrs, ...kids) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) {
      const v = attrs[k];
      if (v == null) continue;
      if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
      else if (k === 'text') e.textContent = v;
      else e.setAttribute(k, v);
    }
    add(e, kids);
    return e;
  }

  // ── Estado ──────────────────────────────────────────────────────────────

  const S = {
    staff: null, dia: null, horaCorte: '05:00',
    nav: 0, vista: null, prev: null, auto: null,
    abiertas: [], cuenta: null, cobro: null, staffLista: null,
    hist: { rango: 'hoy', estado: 'cerrada', metodo: '', mesa: '', mesero: '', desde: '', hasta: '', hora: false, hd: '00:00', hh: '23:59', pagina: 1 },
    esc: { abierto: false, stream: null, detector: null, timer: null, ultimo: '' },
  };
  const esAdmin = () => !!S.staff && S.staff.rol === 'admin';

  // ── API ─────────────────────────────────────────────────────────────────

  async function api(metodo, ruta, cuerpo) {
    let r;
    try {
      r = await fetch(API + ruta, {
        method: metodo, credentials: 'same-origin', cache: 'no-store',
        headers: cuerpo !== undefined ? { 'Content-Type': 'application/json' } : {},
        body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
      });
    } catch (e) {
      return { ok: false, status: 0, data: { error: 'Sin conexión. Revisa el internet e inténtalo otra vez.' } };
    }
    let data = {};
    try { data = await r.json(); } catch (e) { data = r.ok ? {} : { error: 'Respuesta inesperada del servidor (' + r.status + ').' }; }
    if (!data || typeof data !== 'object') data = {};
    if (!r.ok && !data.error) data.error = 'Algo salió mal (' + r.status + '). Inténtalo otra vez.';
    if (r.status === 401 && ruta !== '/login' && S.staff) sesionVencida();
    return { ok: r.ok, status: r.status, data };
  }

  // ── Avisos y diálogos ───────────────────────────────────────────────────

  let toastT = null;
  function toast(msg) {
    const t = el('toast');
    t.textContent = msg;
    requestAnimationFrame(() => t.classList.add('toast--on'));
    clearTimeout(toastT);
    toastT = setTimeout(() => {
      t.classList.remove('toast--on');
      setTimeout(() => { if (!t.classList.contains('toast--on')) t.textContent = ''; }, 300);
    }, 3800);
  }

  function atraparFoco(e) {
    if (e.key !== 'Tab') return;
    const f = [...e.currentTarget.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])')]
      .filter((x) => x.offsetParent !== null || x === document.activeElement);
    if (!f.length) return;
    const a = f[0], z = f[f.length - 1];
    if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
    else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
  }

  /** Diálogo modal genérico → Promise<{valor, datos}|null>. Esc o «Cancelar» devuelven null. */
  function dialogo({ titulo, cuerpo = [], acciones }) {
    const d = el('dlg');
    const previo = document.activeElement;
    return new Promise((resolve) => {
      const err = h('p', { class: 'error', role: 'alert' });
      let hecho = false;
      const fin = (v) => {
        if (hecho) return;
        hecho = true;
        if (d.open) d.close();
        resolve(v);
        if (previo && previo.isConnected && typeof previo.focus === 'function') previo.focus({ preventScroll: true });
      };
      const datos = (form) => {
        const o = {};
        for (const x of form.elements) {
          if (!x.name) continue;
          if (x.type === 'radio') { if (x.checked) o[x.name] = x.value; } else if (x.type === 'checkbox') o[x.name] = x.checked;
          else o[x.name] = x.value;
        }
        return o;
      };
      const botones = acciones.map((a) => h('button', {
        type: 'button', class: 'btn ' + (a.clase || 'btn--quiet'), 'data-principal': a.principal ? '1' : null,
        onclick: () => {
          if (a.valor == null) return fin(null);
          const dd = datos(form);
          const e = a.validar ? a.validar(dd) : '';
          if (e) { err.textContent = e; const f = form.querySelector('input, textarea, select'); if (f) f.focus(); return; }
          fin({ valor: a.valor, datos: dd });
        },
      }, a.texto));
      const form = h('form', { novalidate: true, onsubmit: (e) => { e.preventDefault(); const p = form.querySelector('[data-principal]'); if (p) p.click(); } },
        h('div', { class: 'modal__body' }, h('h2', { class: 'modal__t', id: 'dlg-t', tabindex: '-1', text: titulo }), cuerpo, err),
        h('div', { class: 'modal__pie' }, botones));
      d.replaceChildren(form);
      d.oncancel = (e) => { e.preventDefault(); fin(null); };
      d.onclose = () => fin(null);
      d.showModal();
      const primero = form.querySelector('input:not([type=radio]), textarea, input[type=radio]:checked, input[type=radio]') || form.querySelector('[data-principal]') || botones[0];
      if (primero) primero.focus();
    });
  }

  async function confirmar({ titulo, texto, si = 'Sí', no = 'Cancelar', peligro = false }) {
    const r = await dialogo({
      titulo, cuerpo: [h('p', { text: texto })],
      acciones: [{ texto: no }, { texto: si, clase: peligro ? 'btn--peligro' : 'btn--primary', valor: 'si', principal: true }],
    });
    return !!r;
  }

  async function pedirMotivo({ titulo, texto, etiqueta = 'Motivo', boton, peligro = true }) {
    const r = await dialogo({
      titulo,
      cuerpo: [texto ? h('p', { text: texto }) : null,
        h('div', { class: 'campo' }, h('label', { for: 'dlg-motivo', text: etiqueta }),
          h('textarea', { id: 'dlg-motivo', name: 'motivo', rows: '3', maxlength: '200', required: true }))],
      acciones: [{ texto: 'Volver' }, {
        texto: boton, clase: peligro ? 'btn--peligro' : 'btn--primary', valor: 'ok', principal: true,
        validar: (d) => (d.motivo.trim() ? '' : 'Escribe el motivo.'),
      }],
    });
    return r ? r.datos.motivo.trim() : null;
  }

  // ── Vistas y navegación ─────────────────────────────────────────────────

  const VISTAS = ['cargando', 'login', 'inicio', 'pedido', 'cuenta', 'cobro', 'historial', 'corte', 'cierre', 'equipo'];
  const NAV_DE = { inicio: 'inicio', pedido: 'inicio', cuenta: 'inicio', cobro: 'inicio', historial: 'historial', corte: 'corte', cierre: 'admin', equipo: 'admin' };
  const TITULOS = { login: 'Entrar', inicio: 'Inicio', pedido: 'Pedido', cuenta: 'Cuenta', cobro: 'Cobrar', historial: 'Historial', corte: 'Mi corte', cierre: 'Cierre del día', equipo: 'Equipo' };

  function mostrar(v, { foco = true } = {}) {
    VISTAS.forEach((x) => { el('v-' + x).hidden = x !== v; });
    const dentro = !!S.staff && v !== 'login' && v !== 'cargando';
    el('bnav').hidden = !dentro;
    el('ebar-acc').hidden = !dentro;
    document.body.classList.toggle('con-nav', dentro);
    document.body.classList.toggle('ancha', v === 'cierre' || v === 'equipo' || v === 'historial');
    el('bnav').querySelectorAll('a').forEach((a) => {
      if (a.dataset.v === NAV_DE[v]) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    document.title = (TITULOS[v] || 'Cisne Equipo') + ' · Cisne Equipo';
    if (S.vista !== v) { S.prev = S.vista; S.vista = v; }
    el('aviso').hidden = true;
    if (foco) enfocar(v);
  }
  function enfocar(v) {
    const t = el('v-' + v).querySelector('.h1');
    if (t) t.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }

  function ruta() {
    const raw = location.hash.replace(/^#/, '');
    if (raw.startsWith('d=')) return { v: 'importar', arg: raw.slice(2) };
    const [v, ...resto] = raw.split('/');
    let arg = resto.join('/');
    try { arg = decodeURIComponent(arg); } catch (e) { /* tal cual */ }
    return { v: v || 'inicio', arg };
  }

  function pararAuto() { clearInterval(S.auto); S.auto = null; }

  async function navegar() {
    pararAuto();
    const tok = ++S.nav;
    if (!S.staff) return mostrarLogin();
    const { v, arg } = ruta();
    switch (v) {
      case 'inicio': return vistaInicio(tok);
      case 'pedido': return vistaPedido(tok, arg);
      case 'importar': return vistaImportar(tok, arg);
      case 'cuenta': return vistaCuenta(tok, arg);
      case 'cobro': return vistaCobro(tok, arg);
      case 'historial': return vistaHistorial(tok);
      case 'corte': return vistaCorte(tok);
      case 'cierre': return esAdmin() ? vistaCierre(tok) : soloAdmin(tok);
      case 'equipo': return esAdmin() ? vistaEquipo(tok) : soloAdmin(tok);
      default:
        history.replaceState(null, '', '#inicio');
        return vistaInicio(tok);
    }
  }
  function ir(hash) {
    if (location.hash === hash) navegar(); else location.hash = hash;
  }
  function soloAdmin(tok) {
    history.replaceState(null, '', '#inicio');
    vistaInicio(tok);
    toast('Esa sección es solo para el administrador.');
  }

  // ── Sesión ──────────────────────────────────────────────────────────────

  function ponerSesion(d) {
    S.staff = d.staff;
    S.dia = d.dia_operativo || S.dia;
    S.horaCorte = d.hora_corte || S.horaCorte;
    el('quien').textContent = S.staff.nombre + (esAdmin() ? ' · Admin' : '');
    el('nav-admin').hidden = !esAdmin();
    el('h-mesero-campo').hidden = !esAdmin();
  }

  function sesionVencida() {
    S.staff = null;
    pararAuto();
    cerrarEscaner();
    if (el('dlg').open) el('dlg').close();
    mostrarLogin('Tu sesión terminó. Vuelve a entrar.');
  }

  function mostrarLogin(msg) {
    S.staff = null;
    mostrar('login', { foco: false });
    el('login-error').textContent = msg || '';
    const { v, arg } = ruta();
    el('login-sub').textContent = v === 'pedido' && arg ? 'Entra para abrir el pedido ' + fmtCodigo(arg) + '.'
      : v === 'importar' ? 'Entra para registrar el pedido sin internet.'
        : 'Usa tu usuario y tu PIN de 6 números.';
    const u = el('l-usuario');
    if (!u.value) u.value = localStorage.getItem('cn-eq-usuario') || '';
    el('l-pin').value = '';
    (u.value ? el('l-pin') : u).focus({ preventScroll: true });
  }

  let entrando = false;
  async function entrar(e) {
    if (e) e.preventDefault();
    if (entrando) return;
    const usuario = el('l-usuario').value.trim().toLowerCase();
    const pin = el('l-pin').value;
    const err = el('login-error');
    if (!usuario) { err.textContent = 'Escribe tu usuario.'; el('l-usuario').focus(); return; }
    if (!/^\d{6}$/.test(pin)) { err.textContent = 'El PIN tiene 6 números.'; el('l-pin').focus(); return; }
    entrando = true;
    err.textContent = '';
    const btn = el('f-login').querySelector('.teclado__ok');
    btn.disabled = true;
    const r = await api('POST', '/login', { usuario, pin });
    entrando = false;
    btn.disabled = false;
    if (!r.ok) {
      err.textContent = r.data.error || 'No se pudo entrar.';
      el('l-pin').value = '';
      el('l-pin').focus();
      return;
    }
    localStorage.setItem('cn-eq-usuario', usuario);
    el('l-pin').value = '';
    const yo = await api('GET', '/yo');
    ponerSesion(yo.ok ? yo.data : r.data);
    navegar();
  }

  async function salir() {
    await api('POST', '/logout', {});
    S.staff = null;
    S.staffLista = null;
    pararAuto();
    history.replaceState(null, '', location.pathname);
    mostrarLogin('Saliste del turno.');
  }

  // ── Inicio ──────────────────────────────────────────────────────────────

  function tarjetaCuenta(c, conMesero) {
    return h('a', { class: 'ccard', href: '#cuenta/' + c.id },
      h('span', { class: 'ccard__mesa' }, h('small', { text: 'Mesa' }), h('b', { text: c.mesa })),
      h('span', { class: 'ccard__info' },
        h('span', { class: 'ccard__t', text: rondasTxt(c.rondas) + (conMesero ? ' · ' + c.mesero : '') }),
        h('span', { class: 'ccard__m', text: 'Abierta desde las ' + hora(c.abierta_at) })),
      h('span', { class: 'ccard__total', text: $(c.total) }));
  }

  async function vistaInicio(tok) {
    el('t-inicio').textContent = 'Hola, ' + primerNombre(S.staff.nombre);
    el('inicio-dia').replaceChildren('Día operativo: ', h('b', { text: diaLargo(S.dia) }), ' · cambia a las ' + S.horaCorte);
    el('codigo-error').textContent = '';
    mostrar('inicio');
    await cargarAbiertas(tok);
    S.auto = setInterval(() => { if (!document.hidden && S.vista === 'inicio') cargarAbiertas(S.nav); }, 30000);
  }

  async function cargarAbiertas(tok) {
    const r = await api('GET', '/cuentas?estado=abierta');
    if (tok !== S.nav || !S.staff) return;
    const mias = el('lista-mias');
    if (!r.ok) { mias.replaceChildren(h('p', { class: 'error', text: r.data.error })); return; }
    S.abiertas = r.data.cuentas || [];
    const propias = S.abiertas.filter((c) => c.mesero_id === S.staff.id);
    mias.replaceChildren(propias.length
      ? h('div', { class: 'cuentas' }, propias.map((c) => tarjetaCuenta(c, false)))
      : h('p', { class: 'vacio', text: 'No tienes cuentas abiertas. Escanea un pedido para abrir una.' }));
    const otras = S.abiertas.filter((c) => c.mesero_id !== S.staff.id);
    el('bloque-todas').hidden = !esAdmin();
    if (esAdmin()) {
      el('lista-todas').replaceChildren(otras.length
        ? h('div', { class: 'cuentas' }, otras.map((c) => tarjetaCuenta(c, true)))
        : h('p', { class: 'vacio', text: 'Nadie más tiene cuentas abiertas.' }));
    }
  }

  function abrirResultado(r) {
    if (r.d) ir('#d=' + r.d);
    else ir('#pedido/' + r.codigo);
  }

  // ── Pedido escaneado ────────────────────────────────────────────────────

  function chipPedido(estado) {
    const m = { pendiente: ['chip--neon', 'Pendiente'], tomado: ['chip--ok', 'Tomado'], caducado: ['chip--gris', 'Caducado'], cancelado: ['chip--alerta', 'Cancelado'] };
    const [c, t] = m[estado] || ['chip--gris', estado];
    return h('span', { class: 'chip ' + c, text: t });
  }
  function chipCuenta(c) {
    const m = { abierta: ['chip--neon', 'Abierta'], cerrada: ['chip--ok', 'Cerrada'], cancelada: ['chip--alerta', 'Cancelada'] };
    const [k, t] = m[c.estado] || ['chip--gris', c.estado];
    return [h('span', { class: 'chip ' + k, text: t }), c.corte_id ? h('span', { class: 'chip chip--gris', text: 'En corte' }) : null];
  }

  function cervezasVuelo(l) {
    const d = String(l.detalle || '');
    const i = d.indexOf(':');
    const nombres = (i >= 0 ? d.slice(i + 1) : d).split('·').map((x) => x.trim()).filter(Boolean);
    return nombres.length ? h('ul', { class: 'vuelo', 'aria-label': 'Cervezas del vuelo' }, nombres.map((n) => h('li', { text: n }))) : null;
  }

  function cuerpoLinea(l) {
    const nohay = l.cantidad === 0;
    return h('div', null,
      h('p', { class: 'linea__n' }, h('span', { class: 'linea__q', text: l.cantidad + '×' }), l.nombre),
      l.tipo === 'vuelo'
        ? [h('p', { class: 'linea__d', text: '4 × 4 oz' }), cervezasVuelo(l)]
        : (l.detalle ? h('p', { class: 'linea__d', text: l.detalle }) : null),
      l.nota ? h('p', { class: 'linea__nota', text: 'Nota: ' + l.nota }) : null,
      nohay ? h('span', { class: 'chip chip--alerta', text: 'No hay' }) : null);
  }
  function precioLinea(l, sinUnitario) {
    return h('div', { class: 'linea__p' }, $(l.precio * l.cantidad),
      l.cantidad > 1 && !sinUnitario ? h('span', { class: 'linea__u', text: $(l.precio) + ' c/u' }) : null);
  }
  function listaLineas(lineas) {
    return h('ul', { class: 'lineas' }, lineas.map((l) => h('li', { class: 'linea' + (l.cantidad === 0 ? ' linea--nohay' : '') }, cuerpoLinea(l), precioLinea(l))));
  }

  function volverA(texto, href) { return h('a', { class: 'volver', href, text: '← ' + texto }); }

  async function vistaPedido(tok, codigo, extra) {
    codigo = limpiarCodigo(codigo);
    const cont = el('pedido-cont');
    cont.replaceChildren(h('p', { class: 'cargando', text: 'Buscando el pedido ' + fmtCodigo(codigo) + '…' }));
    mostrar('pedido', { foco: false });
    const [r, ab] = await Promise.all([api('GET', '/pedidos/' + encodeURIComponent(codigo)), api('GET', '/cuentas?estado=abierta')]);
    if (tok !== S.nav) return;
    if (ab.ok) S.abiertas = ab.data.cuentas || [];
    if (!r.ok) {
      cont.replaceChildren(volverA('Inicio', '#inicio'),
        h('h1', { class: 'h1', id: 't-pedido', tabindex: '-1', text: 'Pedido ' + fmtCodigo(codigo) }),
        h('p', { class: 'error', role: 'alert', text: r.data.error }),
        h('button', { type: 'button', class: 'btn btn--primary btn--lg btn--block', onclick: abrirEscaner, text: 'Escanear otra vez' }));
      enfocar('pedido');
      return;
    }
    renderPedido(r.data.pedido, extra);
    enfocar('pedido');
  }

  function textoAvisoMesa(p, mesa) {
    if (!mesa) return 'Escribe la mesa para tomar el pedido.';
    const c = (mesa === p.mesa && p.cuenta_mesa) || S.abiertas.find((x) => x.mesa === mesa);
    if (!c) return 'Se abrirá una cuenta nueva para la mesa ' + mesa + '.';
    const de = c.mesero_id === S.staff.id ? '' : ' de ' + c.mesero;
    return 'Se agregará a la cuenta de la mesa ' + mesa + de + ' · ronda ' + (c.rondas + 1);
  }

  function renderPedido(p, extra) {
    const cont = el('pedido-cont');
    const pend = p.estado === 'pendiente';
    const errBox = h('p', { class: 'error', role: 'alert', id: 'pedido-error' });
    const partes = [
      volverA('Inicio', '#inicio'),
      h('div', { class: 'ped__top' },
        h('p', { class: 'eyebrow' }, 'Pedido ' + fmtCodigo(p.codigo), p.origen === 'offline' ? h('span', { class: 'chip chip--neon', text: 'Llegó sin internet' }) : null),
        h('h1', { class: 'h1', id: 't-pedido', tabindex: '-1', text: p.mesa ? 'Mesa ' + p.mesa : 'Pedido sin mesa' }),
        h('div', { class: 'ped__estado' }, chipPedido(p.estado), h('span', { class: 'sub', text: 'Creado a las ' + hora(p.creado_at) }))),
    ];
    if (extra && extra.importado) {
      partes.push(h('p', { class: 'nota-ok', role: 'status', text: 'Pedido sin internet registrado con el código ' + fmtCodigo(p.codigo) + '. Ya puedes tomarlo.' }));
    }
    if (p.socio) {
      partes.push(h('div', { class: 'card socio' },
        h('span', { class: 'socio__ico', 'aria-hidden': 'true', text: '★' }),
        h('div', null, h('p', { class: 'h3', text: 'Socio del Pasaporte: ' + p.socio.alias }),
          h('p', { class: 'sub', text: p.socio.visitas === 1 ? '1 visita registrada' : p.socio.visitas + ' visitas registradas' }))));
    }
    partes.push(h('div', { class: 'card' }, listaLineas(p.lineas),
      h('div', { class: 'total' }, h('span', { text: 'Total' }), h('span', { class: 'mono', text: $(p.total) }))));

    if (pend) {
      const aviso = h('p', { class: 'nota-info', id: 'aviso-mesa', 'aria-live': 'polite' });
      const mesa = h('input', { id: 'p-mesa', type: 'text', inputmode: 'text', maxlength: '10', autocomplete: 'off', value: p.mesa || '', required: true, 'aria-describedby': 'aviso-mesa' });
      const pinta = () => { aviso.textContent = textoAvisoMesa(p, mesa.value.trim()); };
      mesa.addEventListener('input', pinta);
      pinta();
      const btn = h('button', { type: 'submit', class: 'btn btn--primary btn--lg btn--block', id: 'tomar', text: 'Tomar pedido' });
      const form = h('form', { class: 'card', novalidate: true, onsubmit: (e) => { e.preventDefault(); tomar(p, mesa, btn, errBox); } },
        h('div', { class: 'campo' }, h('label', { for: 'p-mesa', text: p.mesa ? 'Mesa' : 'Mesa (el cliente no la puso)' }), mesa),
        aviso);
      partes.push(form, errBox, h('div', { class: 'accbar' }, btn));
      btn.setAttribute('form', 'f-tomar');
      form.id = 'f-tomar';
      partes.push(h('button', { type: 'button', class: 'btn btn--quiet btn--sm', onclick: () => cancelarPedido(p), text: 'Cancelar pedido' }));
    } else if (p.estado === 'tomado') {
      const mio = p.tomado_por === S.staff.nombre;
      partes.push(h('p', { class: 'nota-info', role: 'status', text: (mio ? 'Tú tomaste este pedido' : 'Este pedido ya lo tomó ' + p.tomado_por) + ' a las ' + hora(p.tomado_at) + '.' }));
      if (p.cuenta_id && (mio || esAdmin())) partes.push(h('a', { class: 'btn btn--primary btn--lg btn--block', href: '#cuenta/' + p.cuenta_id, text: 'Ver la cuenta' }));
    } else {
      partes.push(h('p', { class: 'error', role: 'alert', text: p.estado === 'caducado' ? 'Este pedido caducó (pasaron más de 3 horas sin que nadie lo tomara). Pide al cliente que lo vuelva a enviar.' : 'Este pedido se canceló.' }));
    }
    cont.replaceChildren(...partes);
  }

  async function tomar(p, inputMesa, btn, errBox) {
    const mesa = inputMesa.value.trim();
    if (!mesa) { errBox.textContent = 'Indica la mesa.'; inputMesa.focus(); return; }
    btn.disabled = true;
    btn.textContent = 'Tomando…';
    errBox.textContent = '';
    const r = await api('POST', '/pedidos/' + p.codigo + '/tomar', { mesa });
    if (!r.ok) {
      errBox.textContent = r.data.error;
      btn.textContent = 'Tomar pedido';
      if (r.status === 409 || r.status === 410) {
        btn.hidden = true;
        errBox.after(h('a', { class: 'btn btn--ghost btn--block', href: '#inicio', text: 'Volver al inicio' }));
      } else btn.disabled = false;
      return;
    }
    const c = r.data.cuenta;
    toast('Pedido tomado · Mesa ' + c.mesa + ' · ronda ' + c.rondas);
    S.cuenta = c;
    ir('#cuenta/' + c.id);
  }

  async function cancelarPedido(p) {
    const motivo = await pedirMotivo({ titulo: 'Cancelar pedido', texto: 'El pedido ' + fmtCodigo(p.codigo) + ' no se tomará.', boton: 'Cancelar pedido' });
    if (!motivo) return;
    const r = await api('POST', '/pedidos/' + p.codigo + '/cancelar', { motivo });
    if (!r.ok) { toast(r.data.error); return; }
    toast('Pedido cancelado');
    navegar();
  }

  // Pedido que llegó sin internet (#d=…)
  function hashCorto(t) { let x = 5381; for (let i = 0; i < t.length; i++) x = ((x << 5) + x + t.charCodeAt(i)) >>> 0; return x.toString(36) + t.length; }

  async function vistaImportar(tok, b64) {
    const cont = el('pedido-cont');
    mostrar('pedido', { foco: false });
    const datos = decodificarDatos(b64);
    if (!datos) {
      cont.replaceChildren(volverA('Inicio', '#inicio'),
        h('h1', { class: 'h1', id: 't-pedido', tabindex: '-1', text: 'Pedido sin internet' }),
        h('p', { class: 'error', role: 'alert', text: 'No pudimos leer ese QR. Pide al cliente que lo muestre otra vez, o escribe el código si lo tiene.' }),
        h('button', { type: 'button', class: 'btn btn--primary btn--lg btn--block', onclick: abrirEscaner, text: 'Escanear otra vez' }));
      enfocar('pedido');
      return;
    }
    const clave = 'cn-eq-imp:' + hashCorto(b64);
    let previo = null;
    try { previo = JSON.parse(localStorage.getItem(clave) || 'null'); } catch (e) { previo = null; }
    if (previo && Date.now() - previo.t < 6 * 3600e3) {
      history.replaceState(null, '', location.pathname + '#pedido/' + previo.codigo);
      return vistaPedido(tok, previo.codigo);
    }
    const n = datos.lineas.reduce((a, l) => a + (Number(l.cantidad) || 1), 0);
    cont.replaceChildren(volverA('Inicio', '#inicio'),
      h('p', { class: 'eyebrow', text: 'Pedido sin internet' }),
      h('h1', { class: 'h1', id: 't-pedido', tabindex: '-1', text: datos.mesa ? 'Mesa ' + datos.mesa : 'Pedido sin mesa' }),
      h('p', { class: 'nota-info', role: 'status', text: 'Registrando ' + (n === 1 ? '1 producto' : n + ' productos') + ' con los precios del menú…' }),
      h('div', { class: 'card' }, h('ul', { class: 'lineas' }, datos.lineas.map((l) => h('li', { class: 'linea' },
        h('div', null, h('p', { class: 'linea__n' }, h('span', { class: 'linea__q', text: (Number(l.cantidad) || 1) + '×' }), l.nombre || (l.tipo === 'vuelo' ? 'Vuelo' : l.id)),
          l.variante ? h('p', { class: 'linea__d', text: l.variante }) : null), h('span'))))));
    enfocar('pedido');
    const r = await api('POST', '/pedidos/importar', { datos });
    if (tok !== S.nav) return;
    if (!r.ok) {
      cont.querySelector('.nota-info').replaceWith(h('p', { class: 'error', role: 'alert', text: r.data.error }),
        h('button', { type: 'button', class: 'btn btn--primary btn--lg btn--block', onclick: () => vistaImportar(S.nav, b64), text: 'Reintentar' }));
      return;
    }
    const cod = r.data.pedido.codigo;
    try { localStorage.setItem(clave, JSON.stringify({ codigo: cod, t: Date.now() })); } catch (e) { /* sin espacio */ }
    history.replaceState(null, '', location.pathname + '#pedido/' + cod);
    vistaPedido(tok, cod, { importado: true });
  }

  // ── Cuenta ──────────────────────────────────────────────────────────────

  const editable = (c) => c.estado === 'abierta' && !c.corte_id && (esAdmin() || c.mesero_id === S.staff.id);

  async function vistaCuenta(tok, id) {
    const cont = el('cuenta-cont');
    cont.replaceChildren(h('p', { class: 'cargando', text: 'Cargando la cuenta…' }));
    mostrar('cuenta', { foco: false });
    const r = await api('GET', '/cuentas/' + encodeURIComponent(id));
    if (tok !== S.nav) return;
    if (!r.ok) {
      cont.replaceChildren(volverA('Inicio', '#inicio'), h('h1', { class: 'h1', id: 't-cuenta', tabindex: '-1', text: 'Cuenta' }),
        h('p', { class: 'error', role: 'alert', text: r.data.error }));
      enfocar('cuenta');
      return;
    }
    S.cuenta = r.data.cuenta;
    renderCuenta();
    enfocar('cuenta');
  }

  function textoEvento(e) {
    let d = {};
    try { d = JSON.parse(e.detalle || '{}') || {}; } catch (x) { d = {}; }
    switch (e.tipo) {
      case 'cuenta_abierta': return 'Abrió la cuenta de la mesa ' + d.mesa;
      case 'pedido_tomado': return 'Tomó la ronda ' + fmtCodigo(d.codigo) + ' (' + $(d.total) + ')';
      case 'linea_ajustada': return d.producto + ': ' + d.antes + ' → ' + (d.despues === 0 ? 'no hay' : d.despues);
      case 'cuenta_cerrada': return 'Cerró la cuenta: ' + $(d.total) + ' + propina ' + $(d.propina);
      case 'cuenta_cancelada': return 'Canceló la cuenta: ' + d.motivo;
      case 'cuenta_transferida': return 'Transfirió la cuenta a ' + d.a;
      default: return String(e.tipo || '').replace(/_/g, ' ');
    }
  }

  function renderCuenta(enfocarClave) {
    const c = S.cuenta;
    const ed = editable(c);
    const cont = el('cuenta-cont');
    const desde = S.prev === 'historial' ? ['Historial', '#historial'] : S.prev === 'corte' ? ['Mi corte', '#corte'] : S.prev === 'cierre' ? ['Cierre del día', '#cierre'] : ['Inicio', '#inicio'];
    const partes = [
      volverA(desde[0], desde[1]),
      h('div', { class: 'ped__top' },
        h('p', { class: 'eyebrow', text: 'Cuenta ' + c.id + ' · ' + (c.mesero || '') }),
        h('h1', { class: 'h1', id: 't-cuenta', tabindex: '-1', text: 'Mesa ' + c.mesa }),
        h('div', { class: 'ped__estado' }, chipCuenta(c),
          h('span', { class: 'sub', text: rondasTxt(c.rondas) + ' · abierta a las ' + hora(c.abierta_at) + (c.cerrada_at ? ' · ' + (c.estado === 'cancelada' ? 'cancelada' : 'cerrada') + ' a las ' + hora(c.cerrada_at) : '') }))),
    ];
    if (c.estado === 'cancelada' && c.motivo) partes.push(h('p', { class: 'nota-info', text: 'Motivo de la cancelación: ' + c.motivo }));
    (c.pedidos || []).forEach((p, ip) => {
      const filas = p.lineas.map((l, i) => {
        const k = p.id + '-' + i;
        if (!ed) return h('li', { class: 'linea' + (l.cantidad === 0 ? ' linea--nohay' : '') }, cuerpoLinea(l), precioLinea(l));
        const nombre = l.nombre + (l.detalle && l.tipo !== 'vuelo' ? ' ' + l.detalle : '');
        return h('li', { class: 'linea linea--edit' + (l.cantidad === 0 ? ' linea--nohay' : '') },
          cuerpoLinea(l), precioLinea(l, true),
          h('div', { class: 'linea__pie' },
            h('span', { class: 'sub', text: $(l.precio) + ' c/u' }),
            h('div', { class: 'stepper', role: 'group', 'aria-label': 'Cantidad de ' + nombre },
              h('button', { type: 'button', 'data-k': k + '-menos', 'aria-label': 'Quitar uno de ' + nombre, disabled: l.cantidad <= 0, onclick: () => ajustar(p, i, l.cantidad - 1, k + '-menos') }, '−'),
              h('output', { 'aria-live': 'polite', 'aria-label': 'Cantidad', text: String(l.cantidad) }),
              h('button', { type: 'button', 'data-k': k + '-mas', 'aria-label': 'Agregar uno de ' + nombre, disabled: l.cantidad >= MAX_CANT, onclick: () => ajustar(p, i, l.cantidad + 1, k + '-mas') }, '＋'))));
      });
      partes.push(h('section', { class: 'card ronda', 'aria-label': 'Ronda ' + (ip + 1) },
        h('div', { class: 'ronda__h' }, h('h2', { class: 'h3', text: 'Ronda ' + (ip + 1) }),
          h('span', { class: 'mono', text: hora(p.tomado_at) + ' · ' + fmtCodigo(p.codigo) + (p.tomado_por && p.tomado_por !== c.mesero ? ' · ' + p.tomado_por : '') })),
        h('ul', { class: 'lineas' }, filas),
        h('div', { class: 'total' }, h('span', { text: 'Subtotal' }), h('span', { class: 'mono', text: $(p.total) }))));
    });
    if (c.estado === 'cerrada') {
      partes.push(h('section', { class: 'card', 'aria-labelledby': 't-pago' },
        h('h2', { class: 'h3', id: 't-pago', text: 'Pago' }),
        h('dl', { class: 'metodos' },
          h('div', null, h('dt', { text: 'Cuenta' }), h('dd', { text: $(c.total) })),
          h('div', null, h('dt', { text: 'Propina' }), h('dd', { text: $(c.propina) })),
          c.pagos.map((pg) => h('div', null, h('dt', { text: MET_LARGO[pg.metodo] || pg.metodo }), h('dd', { text: $(pg.monto) })))),
        h('div', { class: 'total' }, h('span', { text: 'Total cobrado' }), h('span', { class: 'mono', text: $(c.total + c.propina) }))));
    } else if (!ed) {
      partes.push(h('div', { class: 'total' }, h('span', { text: 'Total' }), h('span', { class: 'mono', text: $(c.total) })));
    }
    if (c.eventos && c.eventos.length) {
      partes.push(h('details', { class: 'card bitacora' },
        h('summary', { text: 'Bitácora (' + c.eventos.length + ')' }),
        h('ol', null, c.eventos.map((e) => h('li', null, h('time', { datetime: e.creado_at, text: hora(e.creado_at) }),
          h('span', { text: (e.staff ? primerNombre(e.staff) + ': ' : '') + textoEvento(e) }))))));
    }
    if (ed) {
      partes.push(h('div', { class: 'cta-fila' },
        h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onclick: abrirEscaner, text: 'Agregar ronda' }),
        h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onclick: () => transferir(c, () => ir('#inicio')), text: 'Transferir' })));
      partes.push(h('button', { type: 'button', class: 'btn btn--quiet btn--sm', onclick: () => cancelarCuenta(c), text: 'Cancelar cuenta' }));
      const cero = c.total <= 0;
      partes.push(h('div', { class: 'accbar' },
        h('div', { class: 'accbar__total' }, h('span', { text: 'Total' }), h('span', { class: 'mono', id: 'cuenta-total', text: $(c.total) })),
        cero ? h('p', { class: 'sub', text: 'La cuenta está en $0: cancélala en lugar de cobrarla.' }) : null,
        h('a', { class: 'btn btn--primary btn--lg btn--block', href: cero ? null : '#cobro/' + c.id, 'aria-disabled': cero ? 'true' : null, id: 'cerrar-cuenta', text: 'Cerrar cuenta' })));
    }
    cont.replaceChildren(...partes);
    if (enfocarClave) {
      const b = cont.querySelector('[data-k="' + enfocarClave + '"]');
      const alt = cont.querySelector('[data-k="' + enfocarClave.replace(/menos$|mas$/, (m) => (m === 'menos' ? 'mas' : 'menos')) + '"]');
      const f = b && !b.disabled ? b : alt;
      if (f) f.focus({ preventScroll: true });
    }
  }

  let ajustando = false;
  async function ajustar(p, i, n, clave) {
    if (ajustando) return;
    const l = p.lineas[i];
    const nombre = l.nombre + (l.detalle && l.tipo !== 'vuelo' ? ' ' + l.detalle : '');
    if (n === 0) {
      const ok = await confirmar({ titulo: '¿No hay?', texto: '«' + nombre + '» quedará en 0 y no se cobrará. Podrás devolverlo con ＋ si sí hay.', si: 'Sí, no hay', peligro: true });
      if (!ok) return;
    }
    ajustando = true;
    el('cuenta-cont').querySelectorAll('.stepper button').forEach((b) => { b.disabled = true; });
    const r = await api('POST', '/cuentas/' + S.cuenta.id + '/linea', { pedido_id: p.id, indice: i, cantidad: n });
    ajustando = false;
    if (!r.ok) { toast(r.data.error); renderCuenta(clave); return; }
    S.cuenta = r.data.cuenta;
    renderCuenta(clave);
    toast(n === 0 ? nombre + ': no hay' : nombre + ': ' + n);
  }

  async function transferir(c, despues) {
    const r = await api('GET', '/companeros');
    if (!r.ok) { toast(r.data.error); return; }
    const ops = (r.data.staff || []).filter((x) => x.id !== c.mesero_id);
    if (!ops.length) { toast('No hay otra persona activa para recibir la cuenta.'); return; }
    const res = await dialogo({
      titulo: 'Transferir mesa ' + c.mesa,
      cuerpo: [h('p', { text: 'La cuenta (' + $(c.total) + ') pasará a:' }),
        h('div', { class: 'opciones', role: 'radiogroup', 'aria-label': 'Compañero que recibe la cuenta' },
          ops.map((x) => h('label', { class: 'opcion' }, h('input', { type: 'radio', name: 'staff_id', value: String(x.id) }),
            x.nombre + (x.rol === 'admin' ? ' (admin)' : ''))))],
      acciones: [{ texto: 'Cancelar' }, { texto: 'Transferir', clase: 'btn--primary', valor: 'ok', principal: true, validar: (d) => (d.staff_id ? '' : 'Elige a quién se la pasas.') }],
    });
    if (!res) return;
    const dest = ops.find((x) => String(x.id) === res.datos.staff_id);
    const t = await api('POST', '/cuentas/' + c.id + '/transferir', { staff_id: Number(res.datos.staff_id) });
    if (!t.ok) { toast(t.data.error); return; }
    toast('Mesa ' + c.mesa + ' transferida a ' + (dest ? dest.nombre : 'otro compañero'));
    if (despues) despues();
  }

  async function cancelarCuenta(c) {
    const motivo = await pedirMotivo({ titulo: 'Cancelar cuenta', texto: 'La cuenta de la mesa ' + c.mesa + ' (' + $(c.total) + ') quedará cancelada y no se cobrará.', boton: 'Cancelar cuenta' });
    if (!motivo) return;
    const r = await api('POST', '/cuentas/' + c.id + '/cancelar', { motivo });
    if (!r.ok) { toast(r.data.error); return; }
    toast('Cuenta de la mesa ' + c.mesa + ' cancelada');
    ir('#inicio');
  }

  // ── Cobro ───────────────────────────────────────────────────────────────

  async function vistaCobro(tok, id) {
    mostrar('cobro', { foco: false });
    el('cobro-volver').href = '#cuenta/' + id;
    el('cobro-error').textContent = '';
    el('cobrar').disabled = true;
    const r = await api('GET', '/cuentas/' + encodeURIComponent(id));
    if (tok !== S.nav) return;
    if (!r.ok) { toast(r.data.error); history.replaceState(null, '', '#inicio'); return vistaInicio(tok); }
    const c = r.data.cuenta;
    S.cuenta = c;
    if (!editable(c)) { toast('Esa cuenta ya no está abierta.'); history.replaceState(null, '', '#cuenta/' + c.id); return vistaCuenta(tok, c.id); }
    S.cobro = { id: c.id, mesa: c.mesa, totalC: Math.round(c.total * 100), pct: 0, otra: '', pagos: [] };
    el('cobro-sub').textContent = 'Mesa ' + c.mesa + ' · ' + rondasTxt(c.rondas) + ' · ' + c.mesero;
    el('cobro-cuenta').textContent = $(c.total);
    el('propina-otra').value = '';
    pintarPropinaSeg();
    renderPagos();
    actualizarCobro();
    enfocar('cobro');
  }

  function propinaC() {
    const k = S.cobro;
    if (k.otra.trim() !== '') return aCentavos(k.otra);
    return Math.round(k.totalC * k.pct / 100);
  }
  function pintarPropinaSeg() {
    const k = S.cobro;
    el('propina-seg').querySelectorAll('button').forEach((b) => {
      b.setAttribute('aria-pressed', String(k.otra.trim() === '' && Number(b.dataset.p) === k.pct));
    });
  }

  function renderPagos() {
    const k = S.cobro;
    el('pagos').replaceChildren(...k.pagos.map((pg, i) => {
      const n = i + 1;
      const monto = h('input', { id: 'pago-monto-' + i, type: 'text', inputmode: 'decimal', autocomplete: 'off', placeholder: '$0.00', value: pg.monto,
        oninput: (e) => { pg.monto = e.target.value; actualizarCobro(); } });
      const li = h('li', { class: 'pago', 'data-i': String(i) },
        h('div', { class: 'pago__top' }, h('span', { class: 'pago__n', text: 'Pago ' + n }),
          h('button', { type: 'button', class: 'btn btn--quiet btn--xs', 'aria-label': 'Quitar el pago ' + n, text: 'Quitar',
            onclick: () => { k.pagos.splice(i, 1); renderPagos(); actualizarCobro(); el('pago-agregar').focus(); } })),
        h('div', { class: 'seg seg--3', role: 'group', 'aria-label': 'Forma de pago del pago ' + n },
          Object.keys(MET).map((m) => h('button', { type: 'button', 'data-m': m, 'aria-pressed': String(pg.metodo === m), text: MET[m],
            onclick: () => { pg.metodo = m; renderPagos(); actualizarCobro(); const b = el('pagos').querySelector('[data-i="' + i + '"] [data-m="' + m + '"]'); if (b) b.focus(); } }))),
        h('div', { class: 'campo' }, h('label', { for: 'pago-monto-' + i, text: 'Monto en ' + MET_LARGO[pg.metodo].toLowerCase() }), monto));
      if (pg.metodo === 'efectivo') {
        li.append(h('div', { class: 'pago__cambio' },
          h('div', { class: 'campo' }, h('label', { for: 'pago-recibe-' + i, text: '¿Con cuánto paga?' }),
            h('input', { id: 'pago-recibe-' + i, type: 'text', inputmode: 'decimal', autocomplete: 'off', placeholder: 'Opcional', value: pg.recibe || '',
              oninput: (e) => { pg.recibe = e.target.value; actualizarCobro(); } })),
          h('output', { id: 'pago-cambio-' + i, for: 'pago-recibe-' + i, 'aria-live': 'polite' })));
      }
      return li;
    }));
  }

  function actualizarCobro() {
    const k = S.cobro;
    if (!k) return;
    const prop = propinaC();
    const propOk = !isNaN(prop) && prop >= 0;
    el('propina-txt').textContent = !propOk ? 'Escribe la propina como número, por ejemplo 50 o 48.50.'
      : prop ? 'Propina: ' + c$(prop) + (k.otra.trim() === '' && k.pct ? ' (' + k.pct + '% de ' + c$(k.totalC) + ')' : '') : 'Sin propina';
    const total = k.totalC + (propOk ? prop : 0);
    let pagado = 0, malos = 0;
    k.pagos.forEach((pg, i) => {
      const v = aCentavos(pg.monto);
      if (isNaN(v) || v <= 0) malos++; else pagado += v;
      const out = el('pago-cambio-' + i);
      if (out) {
        const rec = aCentavos(pg.recibe);
        if (!pg.recibe || isNaN(rec) || isNaN(v) || v <= 0) out.replaceChildren();
        else if (rec >= v) out.replaceChildren(h('small', { text: 'Cambio' }), c$(rec - v));
        else out.replaceChildren(h('small', { text: 'Le faltan' }), c$(v - rec));
      }
    });
    const resta = total - pagado;
    el('cobro-total').textContent = c$(total);
    const caja = el('resta');
    caja.classList.toggle('resta--ok', resta === 0 && k.pagos.length > 0);
    caja.classList.toggle('resta--falta', resta > 0);
    caja.classList.toggle('resta--sobra', resta < 0);
    el('resta-k').textContent = resta < 0 ? 'Sobran' : resta === 0 && k.pagos.length ? 'Todo cubierto' : 'Resta por cobrar';
    el('resta-v').textContent = c$(Math.abs(resta));
    const hay = pagado > 0;
    el('rapidos').querySelectorAll('button').forEach((b) => {
      b.querySelector('small').textContent = hay ? 'lo que resta' : 'todo';
      b.setAttribute('aria-label', 'Cobrar ' + (hay ? 'lo que resta' : 'todo') + ' en ' + MET_LARGO[b.dataset.m].toLowerCase());
      b.disabled = hay && resta <= 0;
    });
    const valido = propOk && k.pagos.length > 0 && malos === 0 && resta === 0;
    const btn = el('cobrar');
    btn.disabled = !valido;
    btn.textContent = valido ? 'Cobrar ' + c$(total) : 'Cobrar';
    return { valido, total, prop, resta, malos, propOk };
  }

  function cobrarRapido(m) {
    const k = S.cobro;
    const prop = propinaC();
    if (isNaN(prop)) { el('cobro-error').textContent = 'Corrige la propina primero.'; return; }
    const total = k.totalC + prop;
    const pagado = k.pagos.reduce((a, pg) => { const v = aCentavos(pg.monto); return a + (isNaN(v) || v < 0 ? 0 : v); }, 0);
    if (pagado === 0) {
      k.pagos = [{ metodo: m, monto: fmtNum(total), recibe: '' }];
    } else {
      const resta = total - pagado;
      if (resta <= 0) { toast('Ya no resta nada por cobrar.'); return; }
      const vacio = k.pagos.find((pg) => !(aCentavos(pg.monto) > 0));
      if (vacio) { vacio.metodo = m; vacio.monto = fmtNum(resta); } else k.pagos.push({ metodo: m, monto: fmtNum(resta), recibe: '' });
    }
    el('cobro-error').textContent = '';
    renderPagos();
    actualizarCobro();
  }

  async function cobrar(e) {
    e.preventDefault();
    const k = S.cobro;
    const v = actualizarCobro();
    const err = el('cobro-error');
    if (!v.propOk) { err.textContent = 'La propina no es válida.'; el('propina-otra').focus(); return; }
    if (!k.pagos.length) { err.textContent = 'Agrega al menos un pago.'; return; }
    if (v.malos) { err.textContent = 'Cada pago necesita un monto mayor a $0.'; return; }
    if (v.resta !== 0) { err.textContent = v.resta > 0 ? 'Faltan ' + c$(v.resta) + ' por cobrar.' : 'Los pagos suman ' + c$(-v.resta) + ' de más.'; return; }
    const btn = el('cobrar');
    btn.disabled = true;
    btn.textContent = 'Cobrando…';
    err.textContent = '';
    const r = await api('POST', '/cuentas/' + k.id + '/cerrar', {
      pagos: k.pagos.map((pg) => ({ metodo: pg.metodo, monto: aCentavos(pg.monto) / 100 })),
      propina: v.prop / 100,
    });
    if (!r.ok) { err.textContent = r.data.error; actualizarCobro(); return; }
    S.cobro = null;
    S.cuenta = r.data.cuenta;
    toast('Mesa ' + k.mesa + ' cerrada · ' + c$(v.total) + (v.prop ? ' con ' + c$(v.prop) + ' de propina' : ''));
    ir('#inicio');
  }

  // ── Gráficas e indicadores ──────────────────────────────────────────────

  function kpi(k, v, hero) {
    return h('div', { class: 'kpi' + (hero ? ' kpi--hero' : '') }, h('p', { class: 'kpi__k', text: k }), h('p', { class: 'kpi__v', text: v }));
  }

  /** Barras horizontales (una serie, valor en la punta). items: [{k, v, txt}] */
  function barras(titulo, sub, items, vacio) {
    const max = Math.max(0, ...items.map((x) => x.v));
    return h('figure', { class: 'card graf' },
      h('figcaption', null, h('h3', { class: 'graf__h', text: titulo }), sub ? h('p', { class: 'graf__s', text: sub }) : null),
      !items.length || max <= 0 ? h('p', { class: 'sub', text: vacio || 'Sin datos en este rango.' })
        : h('ul', { class: 'barras' }, items.map((x) => h('li', { class: 'barra' },
          h('span', { class: 'barra__k', text: x.k, title: x.k }), h('span', { class: 'barra__v', text: x.txt }),
          h('div', { class: 'barra__pista', 'aria-hidden': 'true' },
            x.v > 0 ? h('div', { class: 'barra__fill', style: 'width:' + Math.max(1, (x.v / max) * 100).toFixed(1) + '%' }) : null)))));
  }

  function colPath(x, y, w, alto, r) {
    r = Math.min(r, w / 2, alto);
    return 'M' + x + ',' + (y + alto) + 'V' + (y + r) + 'Q' + x + ',' + y + ' ' + (x + r) + ',' + y + 'H' + (x + w - r) + 'Q' + (x + w) + ',' + y + ' ' + (x + w) + ',' + (y + r) + 'V' + (y + alto) + 'Z';
  }

  /** Columnas por hora (una serie). Huecos rellenos con 0 para que el eje sea continuo. */
  function columnasHora(porHora) {
    const fig = h('figure', { class: 'card graf' },
      h('figcaption', null, h('h3', { class: 'graf__h', text: 'Cuentas por hora' }), h('p', { class: 'graf__s', text: 'Hora en que se abrió cada cuenta' })));
    if (!porHora || !porHora.length) { fig.append(h('p', { class: 'sub', text: 'Sin datos en este rango.' })); return fig; }
    const m = new Map(porHora.map((x) => [parseInt(x.hora, 10), x.cuentas]));
    const hs = [...m.keys()];
    let a = Math.min(...hs), b = Math.max(...hs);
    if (b - a < 3) { a = Math.max(0, a - 1); b = Math.min(23, b + 1); }
    const datos = [];
    for (let i = a; i <= b; i++) datos.push({ h: i, n: m.get(i) || 0 });
    const max = Math.max(...datos.map((x) => x.n));
    // Ancho lógico ~ancho real de la tarjeta para que las columnas no pasen de 24 px al escalar.
    const W = Math.max(320, datos.length * 30), banda = W / datos.length, H = 150, base = 122, top = 16;
    const bw = Math.min(19, banda - 10); // ≤ 24 px reales con el escalado máximo (1.25×)
    const cont = h('div', { class: 'colgraf' });
    const tip = h('div', { class: 'tip', hidden: true, role: 'presentation' });
    const svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'group', 'aria-label': 'Cuentas por hora', style: 'max-width:' + Math.round(W * 1.25) + 'px' });
    svg.append(s('line', { x1: 0, x2: W, y1: base + 0.5, y2: base + 0.5, stroke: 'var(--borde)', 'stroke-width': 1 }));
    const etiquetaCada = datos.length > 12 ? 2 : 1;
    datos.forEach((d, i) => {
      const x = i * banda + (banda - bw) / 2;
      const alto = max ? Math.round((d.n / max) * (base - top)) : 0;
      const etiqueta = String(d.h).padStart(2, '0') + ':00';
      const hit = s('rect', { class: 'hit', x: i * banda, y: 0, width: banda, height: base, tabindex: '0', role: 'img', 'aria-label': etiqueta + ': ' + cuentasTxt(d.n) });
      const ver = () => {
        tip.hidden = false;
        tip.replaceChildren(h('b', { text: cuentasTxt(d.n) }), etiqueta);
        const rs = svg.getBoundingClientRect();
        const k = rs.width / W;
        tip.style.left = ((x + bw / 2) * k) + 'px';
        tip.style.top = (Math.max(0, base - alto - 6) * (rs.height / H)) + 'px';
      };
      hit.addEventListener('pointerenter', ver);
      hit.addEventListener('focus', ver);
      hit.addEventListener('pointerleave', () => { tip.hidden = true; });
      hit.addEventListener('blur', () => { tip.hidden = true; });
      svg.append(hit);
      if (alto > 0) svg.append(s('path', { class: 'col', d: colPath(x, base - alto, bw, alto, 4), 'aria-hidden': 'true' }));
      if (d.n > 0 && (d.n === max || datos.length <= 12)) svg.append(s('text', { class: 'val', x: x + bw / 2, y: base - alto - 5, 'text-anchor': 'middle', 'aria-hidden': 'true', text: String(d.n) }));
      if (i % etiquetaCada === 0) svg.append(s('text', { class: 'eje', x: x + bw / 2, y: base + 16, 'text-anchor': 'middle', 'aria-hidden': 'true', text: String(d.h).padStart(2, '0') }));
    });
    cont.append(svg, tip);
    fig.append(cont);
    return fig;
  }

  function graficasIndicadores(ind) {
    return h('div', { class: 'graficas' },
      barras('Por forma de pago', 'Cobrado, incluye propinas', Object.keys(MET_LARGO).map((m) => ({ k: MET_LARGO[m], v: ind.por_metodo[m] || 0, txt: $(ind.por_metodo[m] || 0) })), 'Sin cobros en este rango.'),
      barras('Productos más pedidos', 'Unidades en cuentas cerradas', (ind.top_productos || []).map((p) => ({ k: p.producto, v: p.cantidad, txt: String(p.cantidad) }))),
      columnasHora(ind.por_hora));
  }

  // ── Historial ───────────────────────────────────────────────────────────

  function histQuery(conPagina) {
    const f = S.hist;
    const q = new URLSearchParams();
    if (f.rango !== 'personalizado') q.set('rango', f.rango);
    else {
      const d = f.desde || S.dia;
      const ha = f.hasta || d;
      if (f.hora) { q.set('desde', d + 'T' + (f.hd || '00:00')); q.set('hasta', ha + 'T' + (f.hh || '23:59')); }
      else { q.set('desde', d); q.set('hasta', ha); }
    }
    q.set('estado', f.estado);
    if (f.metodo) q.set('metodo', f.metodo);
    if (f.mesa) q.set('mesa', f.mesa);
    if (f.mesero && esAdmin()) q.set('mesero', f.mesero);
    if (conPagina) { q.set('pagina', String(f.pagina)); q.set('limite', String(LIMITE_HIST)); }
    return q.toString();
  }

  function leerFiltros() {
    const f = S.hist;
    f.estado = el('h-estado').value;
    f.metodo = el('h-metodo').value;
    f.mesa = el('h-mesa').value.trim();
    f.mesero = el('h-mesero').value;
    f.desde = el('h-desde').value;
    f.hasta = el('h-hasta').value;
    f.hora = el('h-hora').checked;
    f.hd = el('h-desde-hora').value;
    f.hh = el('h-hasta-hora').value;
  }

  function pintarRango() {
    const f = S.hist;
    el('rango-chips').querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.r === f.rango)));
    el('rango-personal').hidden = f.rango !== 'personalizado';
    el('rango-personal').classList.toggle('con-hora', f.hora);
    el('rango-personal').querySelectorAll('.campo--hora').forEach((x) => { x.hidden = !f.hora; });
  }

  async function vistaHistorial(tok) {
    mostrar('historial');
    if (!el('h-desde').value) { el('h-desde').value = S.dia; el('h-hasta').value = S.dia; }
    el('h-desde').max = S.dia;
    el('h-hasta').max = S.dia;
    pintarRango();
    if (esAdmin() && !S.staffLista) {
      const r = await api('GET', '/staff');
      if (r.ok) S.staffLista = r.data.staff;
    }
    if (esAdmin() && S.staffLista) {
      const sel = el('h-mesero');
      const actual = sel.value;
      sel.replaceChildren(h('option', { value: '', text: 'Todos' }), S.staffLista.map((x) => h('option', { value: String(x.id), text: x.nombre + (x.activo ? '' : ' (inactivo)') })));
      sel.value = actual;
    }
    cargarHistorial(tok);
  }

  async function cargarHistorial(tok) {
    tok = tok || S.nav;
    leerFiltros();
    const f = S.hist;
    const csv = el('h-csv');
    csv.href = API + '/historial.csv?' + histQuery(false);
    csv.setAttribute('download', 'cisne-historial-' + (f.rango === 'personalizado' ? (f.desde || S.dia) : f.rango + '-' + S.dia) + '.csv');
    const ind = el('h-indicadores');
    ind.classList.add('recargando');
    const r = await api('GET', '/historial?' + histQuery(true));
    if (tok !== S.nav) return;
    ind.classList.remove('recargando');
    if (!r.ok) {
      ind.replaceChildren(h('p', { class: 'error', role: 'alert', text: r.data.error }));
      el('h-lista').replaceChildren();
      el('h-paginas').replaceChildren();
      el('h-rango-txt').textContent = '';
      return;
    }
    const d = r.data;
    const rg = d.rango;
    const rangoTxt = rg.por_dia ? (rg.desde === rg.hasta ? diaLargo(rg.desde) : diaCorto(rg.desde) + ' – ' + diaCorto(rg.hasta)) : fechaHora(rg.desde) + ' – ' + fechaHora(rg.hasta);
    el('h-rango-txt').textContent = rangoTxt.charAt(0).toUpperCase() + rangoTxt.slice(1) + ' · ' + cuentasTxt(d.total_cuentas);
    const i = d.indicadores;
    ind.replaceChildren(...[
      h('div', { class: 'kpis', id: 'h-kpis' },
        kpi('Total vendido', $(i.total), true), kpi('Cuentas cerradas', String(i.cuentas)),
        kpi('Ticket promedio', $(i.ticket_promedio)), kpi('Propinas', $(i.propinas))),
      (i.canceladas || i.abiertas) ? h('p', { class: 'sub', text: 'Canceladas: ' + i.canceladas + ' · Abiertas: ' + i.abiertas }) : null,
      graficasIndicadores(i)].filter(Boolean));
    const lista = el('h-lista');
    lista.replaceChildren(d.cuentas.length
      ? h('div', { class: 'cuentas' }, d.cuentas.map((c) => h('a', { class: 'hcard', href: '#cuenta/' + c.id },
        h('span', { class: 'hcard__t', text: 'Mesa ' + c.mesa + (esAdmin() ? ' · ' + c.mesero : '') }),
        h('span', { class: 'hcard__m', text: diaCorto(c.dia_operativo) + ' · ' + hora(c.abierta_at) + (c.cerrada_at ? '–' + hora(c.cerrada_at) : '') +
          (c.pagos.length ? ' · ' + c.pagos.map((p) => MET[p.metodo]).join(' + ') : '') }),
        h('span', { class: 'hcard__v' }, h('span', { text: $(c.total + (c.propina || 0)) }), chipCuenta(c)))))
      : h('p', { class: 'vacio', text: 'No hay cuentas con estos filtros.' }));
    const pags = Math.max(1, Math.ceil(d.total_cuentas / LIMITE_HIST));
    const pg = el('h-paginas');
    if (pags <= 1) pg.replaceChildren();
    else {
      pg.replaceChildren(
        h('button', { type: 'button', class: 'btn btn--ghost btn--sm', disabled: f.pagina <= 1, text: '← Anteriores', onclick: () => { f.pagina--; cargarHistorial(); } }),
        h('span', { class: 'sub', text: 'Página ' + f.pagina + ' de ' + pags }),
        h('button', { type: 'button', class: 'btn btn--ghost btn--sm', disabled: f.pagina >= pags, text: 'Siguientes →', onclick: () => { f.pagina++; cargarHistorial(); } }));
    }
  }

  // ── Mi corte ────────────────────────────────────────────────────────────

  function metodosDl(pm) {
    return h('dl', { class: 'metodos' }, Object.keys(MET_LARGO).map((m) => h('div', null, h('dt', { text: MET_LARGO[m] }), h('dd', { text: $(pm[m] || 0) }))));
  }

  function textoCorte(res, creado) {
    return ['Corte de ' + res.staff + ' · Cervecería Cisne Negro',
      'Día operativo: ' + diaLargo(res.dia_operativo),
      creado ? 'Hecho a las ' + hora(creado) : '',
      'Cuentas cerradas: ' + res.cuentas + (res.canceladas ? ' · Canceladas: ' + res.canceladas : ''),
      'Total vendido: ' + $(res.total),
      ...Object.keys(MET_LARGO).map((m) => MET_LARGO[m] + ': ' + $((res.por_metodo || {})[m] || 0)),
      'Propinas: ' + $(res.propinas)].filter(Boolean).join('\n');
  }

  async function compartir(texto) {
    if (navigator.share) {
      try { await navigator.share({ title: 'Corte · Cisne Negro', text: texto }); return; } catch (e) { if (e && e.name === 'AbortError') return; }
    }
    try { await navigator.clipboard.writeText(texto); toast('Corte copiado. Pégalo donde lo necesites.'); return; } catch (e) { /* sin portapapeles */ }
    await dialogo({ titulo: 'Copia el corte', cuerpo: [h('div', { class: 'campo' }, h('label', { for: 'dlg-corte', text: 'Texto del corte' }), h('textarea', { id: 'dlg-corte', rows: '9', readonly: true, text: texto }))], acciones: [{ texto: 'Listo', clase: 'btn--primary', valor: 'ok', principal: true }] });
  }

  async function vistaCorte(tok) {
    const cont = el('corte-cont');
    cont.replaceChildren(h('p', { class: 'cargando', text: 'Cargando tu corte…' }));
    mostrar('corte');
    const r = await api('GET', '/corte');
    if (tok !== S.nav) return;
    if (!r.ok) { cont.replaceChildren(h('p', { class: 'error', role: 'alert', text: r.data.error })); return; }
    renderCorte(r.data, tok);
  }

  function renderCorte(d, tok) {
    const cont = el('corte-cont');
    const partes = [h('p', { class: 'sub', text: 'Día operativo: ' + diaLargo(d.dia_operativo) + ' (cambia a las ' + S.horaCorte + ')' })];
    if (d.corte) {
      const res = d.corte.resumen;
      partes.push(h('p', { class: 'nota-ok', role: 'status', id: 'corte-hecho', text: 'Corte hecho a las ' + hora(d.corte.creado_at) + '.' }),
        h('div', { class: 'kpis' }, kpi('Total vendido', $(res.total), true), kpi('Cuentas cerradas', String(res.cuentas)), kpi('Propinas', $(res.propinas)), kpi('Canceladas', String(res.canceladas || 0))),
        h('section', { class: 'card' }, h('h2', { class: 'h3', text: 'Por forma de pago' }), metodosDl(res.por_metodo || {})),
        h('button', { type: 'button', class: 'btn btn--primary btn--lg btn--block', id: 'corte-compartir', onclick: () => compartir(textoCorte(res, d.corte.creado_at)), text: 'Compartir' }),
        h('p', { class: 'sub', text: 'El corte ya no se puede modificar. Si algo está mal, avisa al administrador.' }));
      cont.replaceChildren(...partes);
      return;
    }
    const i = d.indicadores;
    partes.push(h('div', { class: 'kpis' }, kpi('Total vendido', $(i.total), true), kpi('Cuentas cerradas', String(i.cuentas)), kpi('Propinas', $(i.propinas)), kpi('Canceladas', String(i.canceladas))),
      h('section', { class: 'card' }, h('h2', { class: 'h3', text: 'Por forma de pago' }), metodosDl(i.por_metodo)));
    const ab = d.abiertas || [];
    if (ab.length) {
      partes.push(h('section', { class: 'bloque', 'aria-labelledby': 't-corte-ab' },
        h('h2', { class: 'h2', id: 't-corte-ab', text: 'Cuentas abiertas' }),
        h('p', { class: 'nota-info', id: 'corte-bloqueo', text: (ab.length === 1 ? 'Tienes 1 cuenta abierta' : 'Tienes ' + ab.length + ' cuentas abiertas') + '. Ciérrala, cancélala o transfiérela antes del corte.' }),
        h('div', { class: 'cuentas' }, ab.map((c) => h('div', { class: 'card' },
          h('div', { class: 'bloque__top' }, h('span', { class: 'h3', text: 'Mesa ' + c.mesa + ' · ' + rondasTxt(c.rondas) }), h('span', { class: 'mono', text: $(c.total) })),
          h('div', { class: 'cta-fila', style: 'margin-top:10px' },
            h('a', { class: 'btn btn--primary btn--sm', href: '#cobro/' + c.id, text: 'Cerrar' }),
            h('button', { type: 'button', class: 'btn btn--ghost btn--sm', onclick: () => transferir(c, () => vistaCorte(S.nav)), text: 'Transferir' })))))));
    }
    const err = h('p', { class: 'error', role: 'alert' });
    partes.push(err, h('button', {
      type: 'button', class: 'btn btn--primary btn--lg btn--block', id: 'hacer-corte', disabled: ab.length > 0,
      'aria-describedby': ab.length ? 'corte-bloqueo' : null, text: 'Hacer mi corte',
      onclick: async () => {
        const ok = await confirmar({ titulo: '¿Hacer tu corte?', texto: 'Total ' + $(i.total) + ' en ' + cuentasTxt(i.cuentas) + ', propinas ' + $(i.propinas) + '. Después ya no podrás modificar estas cuentas.', si: 'Sí, hacer mi corte' });
        if (!ok) return;
        const r = await api('POST', '/corte', {});
        if (!r.ok) {
          err.textContent = r.data.error;
          if (r.data.abiertas) renderCorte({ ...d, abiertas: r.data.abiertas }, tok);
          return;
        }
        toast('Corte hecho');
        vistaCorte(S.nav);
      },
    }));
    cont.replaceChildren(...partes);
  }

  // ── Cierre del día (admin) ──────────────────────────────────────────────

  async function vistaCierre(tok) {
    const inp = el('cierre-dia');
    if (!inp.value) inp.value = S.dia;
    inp.max = S.dia;
    mostrar('cierre');
    cargarCierre(tok);
  }

  async function cargarCierre(tok) {
    tok = tok || S.nav;
    const dia = el('cierre-dia').value || S.dia;
    const cont = el('cierre-cont');
    cont.classList.add('recargando');
    if (!cont.firstChild) cont.replaceChildren(h('p', { class: 'cargando', text: 'Cargando el día…' }));
    const r = await api('GET', '/cierre?dia=' + encodeURIComponent(dia));
    if (tok !== S.nav) return;
    cont.classList.remove('recargando');
    if (!r.ok) { cont.replaceChildren(h('p', { class: 'error', role: 'alert', text: r.data.error })); return; }
    renderCierre(r.data);
  }

  function renderCierre(d) {
    const cont = el('cierre-cont');
    const i = d.indicadores;
    const cerrado = d.cierre && !d.cierre.reabierto_at;
    const sinCorte = d.por_mesero.filter((m) => !m.corte).map((m) => m.nombre);
    const estado = [];
    if (cerrado) {
      estado.push(h('p', { class: 'nota-ok', role: 'status', id: 'cierre-estado', text: 'Día cerrado a las ' + hora(d.cierre.creado_at) + (d.cierre.forzado ? ' (cierre forzado)' : '') + '.' }));
      if (d.cierre.motivo) estado.push(h('p', { class: 'sub', text: 'Motivo: ' + d.cierre.motivo }));
      estado.push(h('button', { type: 'button', class: 'btn btn--ghost', id: 'reabrir-dia', onclick: () => reabrirDia(d), text: 'Reabrir día' }));
    } else {
      if (d.cierre && d.cierre.reabierto_at) {
        estado.push(h('p', { class: 'nota-info', role: 'status', id: 'cierre-estado', text: 'Día reabierto a las ' + hora(d.cierre.reabierto_at) + (d.cierre.reabierto_motivo ? '. Motivo: ' + d.cierre.reabierto_motivo : '.') }));
      } else estado.push(h('p', { class: 'sub', id: 'cierre-estado', text: 'El día sigue abierto.' }));
      const falta = [];
      if (sinCorte.length) falta.push('Sin corte: ' + sinCorte.join(', ') + '.');
      if (i.abiertas) falta.push(i.abiertas === 1 ? '1 cuenta sigue abierta.' : i.abiertas + ' cuentas siguen abiertas.');
      estado.push(falta.length ? h('p', { class: 'nota-info', text: falta.join(' ') }) : h('p', { class: 'sub', text: 'Todos los cortes están hechos y no hay cuentas abiertas.' }));
      estado.push(h('button', { type: 'button', class: 'btn btn--primary btn--lg', id: 'cerrar-dia', onclick: () => cerrarDia(d), text: 'Cerrar día' }));
    }
    const tabla = d.por_mesero.length
      ? h('div', { class: 'tabla-wrap' }, h('table', { class: 'tabla' },
        h('caption', { class: 'sr-only', text: 'Resumen por mesero' }),
        h('thead', null, h('tr', null, h('th', { scope: 'col', text: 'Mesero' }), h('th', { scope: 'col', text: 'Corte' }),
          h('th', { scope: 'col', class: 'num', text: 'Cuentas' }), h('th', { scope: 'col', class: 'num', text: 'Abiertas' }),
          h('th', { scope: 'col', class: 'num', text: 'Total' }), h('th', { scope: 'col', class: 'num', text: 'Propinas' }))),
        h('tbody', null, d.por_mesero.map((m) => h('tr', null,
          h('th', { scope: 'row', text: m.nombre }),
          h('td', null, m.corte ? h('span', { class: 'chip chip--ok', text: '✓ ' + hora(m.corte.creado_at) }) : h('span', { class: 'chip chip--alerta', text: 'Sin corte' })),
          h('td', { class: 'num', text: String(m.cuentas) }), h('td', { class: 'num', text: String(m.abiertas) }),
          h('td', { class: 'num', text: $(m.total) }), h('td', { class: 'num', text: $(m.propinas) }))))))
      : h('p', { class: 'vacio', text: 'Nadie registró cuentas este día.' });
    cont.replaceChildren(h('div', { class: 'cierre-grid' },
      h('div', { class: 'cierre-col' },
        h('section', { class: 'card estado-dia', 'aria-label': 'Estado del día' }, h('h2', { class: 'h2', text: diaLargo(d.dia_operativo) }), estado),
        h('div', { class: 'kpis kpis--6' }, kpi('Total vendido', $(i.total), true), kpi('Cuentas cerradas', String(i.cuentas)), kpi('Ticket promedio', $(i.ticket_promedio)),
          kpi('Propinas', $(i.propinas)), kpi('Abiertas', String(i.abiertas)), kpi('Canceladas', String(i.canceladas))),
        h('section', { class: 'bloque', 'aria-labelledby': 't-pormesero' }, h('h2', { class: 'h2', id: 't-pormesero', text: 'Por mesero' }), tabla),
        columnasHora(i.por_hora)),
      h('div', { class: 'cierre-col' },
        barras('Por forma de pago', 'Cobrado, incluye propinas', Object.keys(MET_LARGO).map((m) => ({ k: MET_LARGO[m], v: i.por_metodo[m] || 0, txt: $(i.por_metodo[m] || 0) })), 'Sin cobros este día.'),
        barras('Productos más pedidos', 'Unidades en cuentas cerradas', (i.top_productos || []).map((p) => ({ k: p.producto, v: p.cantidad, txt: String(p.cantidad) }))),
        h('section', { class: 'card', 'aria-labelledby': 't-club' }, h('h2', { class: 'h3', id: 't-club', text: 'Pasaporte Cisne (club)' }),
          h('div', { class: 'club', style: 'margin-top:10px' }, kpi('Visitas', String(d.club.visitas)), kpi('NPS', String(d.club.nps)), kpi('Cortesías', String(d.club.cortesias_canjeadas)))),
        h('p', { class: d.pedidos_pendientes ? 'nota-info' : 'sub', text: d.pedidos_pendientes
          ? (d.pedidos_pendientes === 1 ? '1 pedido de cliente sigue sin tomar' : d.pedidos_pendientes + ' pedidos de clientes siguen sin tomar') + '. Al cerrar el día se marcan como caducados.'
          : 'No hay pedidos de clientes sin tomar.' }))));
  }

  async function cerrarDia(d) {
    const dia = d.dia_operativo;
    const i = d.indicadores;
    const ok = await confirmar({ titulo: '¿Cerrar el día?', texto: 'Se cerrará el ' + diaLargo(dia) + ' con ' + $(i.total) + ' en ' + cuentasTxt(i.cuentas) + '. Las cuentas de ese día quedarán bloqueadas.', si: 'Cerrar día' });
    if (!ok) return;
    const r = await api('POST', '/cierre', { dia });
    if (r.ok) { toast('Día cerrado'); renderCierre(r.data); el('t-cierre').focus(); return; }
    if (r.status === 409 && (r.data.sin_corte || r.data.cuentas_abiertas != null)) {
      const sc = r.data.sin_corte || [];
      const ab = r.data.cuentas_abiertas || 0;
      const res = await dialogo({
        titulo: 'Faltan pendientes',
        cuerpo: [
          sc.length ? [h('p', { text: 'Sin corte:' }), h('ul', { class: 'lista' }, sc.map((n) => h('li', { text: n })))] : null,
          ab ? h('p', { text: ab === 1 ? '1 cuenta sigue abierta.' : ab + ' cuentas siguen abiertas.' }) : null,
          h('p', { class: 'sub', text: 'Lo ideal es que cada mesero haga su corte y que no queden cuentas abiertas. Si aun así necesitas cerrar, escribe el motivo y fuerza el cierre.' }),
          h('div', { class: 'campo' }, h('label', { for: 'dlg-forzar', text: 'Motivo del cierre forzado' }), h('textarea', { id: 'dlg-forzar', name: 'motivo', rows: '3', maxlength: '200' }))],
        acciones: [{ texto: 'Volver' }, { texto: 'Forzar cierre', clase: 'btn--peligro', valor: 'forzar', principal: true, validar: (x) => (x.motivo.trim() ? '' : 'Escribe el motivo para forzar el cierre.') }],
      });
      if (!res) return;
      const r2 = await api('POST', '/cierre', { dia, forzar: true, motivo: res.datos.motivo.trim() });
      if (!r2.ok) { toast(r2.data.error); return; }
      toast('Día cerrado (forzado)');
      renderCierre(r2.data);
      return;
    }
    toast(r.data.error);
  }

  async function reabrirDia(d) {
    const motivo = await pedirMotivo({ titulo: 'Reabrir día', texto: 'El ' + diaLargo(d.dia_operativo) + ' volverá a aceptar cambios. Queda registrado quién lo reabrió y por qué.', boton: 'Reabrir día', peligro: false });
    if (!motivo) return;
    const r = await api('POST', '/cierre/reabrir', { dia: d.dia_operativo, motivo });
    if (!r.ok) { toast(r.data.error); return; }
    toast('Día reabierto');
    renderCierre(r.data);
  }

  // ── Equipo (admin) ──────────────────────────────────────────────────────

  async function vistaEquipo(tok) {
    mostrar('equipo');
    el('alta-error').textContent = '';
    cargarStaff(tok);
  }

  async function cargarStaff(tok) {
    tok = tok || S.nav;
    const r = await api('GET', '/staff');
    if (tok !== S.nav) return;
    const ul = el('staff-lista');
    if (!r.ok) { ul.replaceChildren(h('li', { class: 'error', text: r.data.error })); return; }
    S.staffLista = r.data.staff;
    ul.replaceChildren(...S.staffLista.map((x) => {
      const yo = x.id === S.staff.id;
      return h('li', { class: x.activo ? '' : 'inactivo' },
        h('div', null,
          h('p', { class: 'staff__n', text: x.nombre + (yo ? ' (tú)' : '') }),
          h('p', { class: 'staff__u', text: '@' + x.usuario }),
          h('div', { class: 'staff__chips' },
            h('span', { class: 'chip ' + (x.rol === 'admin' ? 'chip--neon' : ''), text: x.rol === 'admin' ? 'Administrador' : 'Mesero' }),
            h('span', { class: 'chip ' + (x.activo ? 'chip--ok' : 'chip--gris'), text: x.activo ? 'Activo' : 'Inactivo' }))),
        h('div', { class: 'staff__acc' },
          h('button', { type: 'button', class: 'btn btn--ghost btn--xs', 'aria-label': 'Editar a ' + x.nombre, text: 'Editar', onclick: () => editarStaff(x) }),
          h('button', { type: 'button', class: 'btn btn--ghost btn--xs', 'aria-label': 'Nuevo PIN para ' + x.nombre, text: 'Nuevo PIN', onclick: () => resetPin(x) }),
          yo ? null : h('button', { type: 'button', class: 'btn btn--quiet btn--xs', 'aria-label': (x.activo ? 'Desactivar a ' : 'Activar a ') + x.nombre, text: x.activo ? 'Desactivar' : 'Activar', onclick: () => activarStaff(x) })));
    }));
  }

  async function mostrarPin(x, pin, nuevo) {
    await dialogo({
      titulo: nuevo ? 'Cuenta creada' : 'PIN nuevo',
      cuerpo: [h('p', null, h('b', { text: x.nombre }), ' entra con el usuario ', h('b', { class: 'mono', text: x.usuario }), ' y este PIN:'),
        h('p', { class: 'pin-grande', id: 'pin-mostrado', 'aria-label': 'PIN: ' + pin.split('').join(' '), text: pin }),
        h('p', { class: 'sub', text: 'Anótalo y entrégalo en persona: solo se muestra esta vez.' })],
      acciones: [{ texto: 'Ya lo anoté', clase: 'btn--primary', valor: 'ok', principal: true }],
    });
  }

  async function alta(e) {
    e.preventDefault();
    const err = el('alta-error');
    const nombre = el('a-nombre').value.trim();
    const usuario = el('a-usuario').value.trim().toLowerCase();
    const pin = el('a-pin').value.trim();
    if (!nombre) { err.textContent = 'Escribe el nombre.'; el('a-nombre').focus(); return; }
    if (!/^[a-z0-9._-]{3,30}$/.test(usuario)) { err.textContent = 'El usuario necesita 3 o más minúsculas, números, punto o guion.'; el('a-usuario').focus(); return; }
    if (pin && !/^\d{6}$/.test(pin)) { err.textContent = 'El PIN debe tener 6 números (o déjalo vacío).'; el('a-pin').focus(); return; }
    err.textContent = '';
    const btn = el('f-alta').querySelector('button[type=submit]');
    btn.disabled = true;
    const r = await api('POST', '/staff', { nombre, usuario, rol: el('a-rol').value, pin: pin || undefined });
    btn.disabled = false;
    if (!r.ok) { err.textContent = r.data.error; return; }
    el('f-alta').reset();
    S.staffLista = null;
    await mostrarPin(r.data.staff, r.data.pin, true);
    cargarStaff();
  }

  async function editarStaff(x) {
    const res = await dialogo({
      titulo: 'Editar a ' + primerNombre(x.nombre),
      cuerpo: [h('div', { class: 'campo' }, h('label', { for: 'dlg-nombre', text: 'Nombre' }), h('input', { id: 'dlg-nombre', name: 'nombre', type: 'text', maxlength: '60', value: x.nombre })),
        h('div', { class: 'campo' }, h('label', { for: 'dlg-rol', text: 'Rol' }),
          h('select', { id: 'dlg-rol', name: 'rol' }, h('option', { value: 'mesero', text: 'Mesero', selected: x.rol === 'mesero' }), h('option', { value: 'admin', text: 'Administrador', selected: x.rol === 'admin' })))],
      acciones: [{ texto: 'Cancelar' }, { texto: 'Guardar', clase: 'btn--primary', valor: 'ok', principal: true, validar: (d) => (d.nombre.trim() ? '' : 'El nombre no puede quedar vacío.') }],
    });
    if (!res) return;
    const cambios = {};
    if (res.datos.nombre.trim() !== x.nombre) cambios.nombre = res.datos.nombre.trim();
    if (res.datos.rol !== x.rol) cambios.rol = res.datos.rol;
    if (!Object.keys(cambios).length) return;
    const r = await api('PUT', '/staff/' + x.id, cambios);
    if (!r.ok) { toast(r.data.error); return; }
    toast('Cambios guardados');
    S.staffLista = null;
    cargarStaff();
  }

  async function resetPin(x) {
    const ok = await confirmar({ titulo: '¿PIN nuevo?', texto: 'El PIN actual de ' + x.nombre + ' dejará de funcionar y se cerrará su sesión.', si: 'Generar PIN nuevo', peligro: true });
    if (!ok) return;
    const r = await api('PUT', '/staff/' + x.id, { reset_pin: true });
    if (!r.ok) { toast(r.data.error); return; }
    await mostrarPin(r.data.staff, r.data.pin, false);
  }

  async function activarStaff(x) {
    if (x.activo) {
      const ok = await confirmar({ titulo: '¿Desactivar?', texto: x.nombre + ' ya no podrá entrar y se cerrará su sesión. Sus cuentas y cortes se conservan.', si: 'Desactivar', peligro: true });
      if (!ok) return;
    }
    const r = await api('PUT', '/staff/' + x.id, { activo: !x.activo });
    if (!r.ok) { toast(r.data.error); return; }
    toast(x.nombre + (x.activo ? ' desactivado' : ' activado'));
    S.staffLista = null;
    cargarStaff();
  }

  // ── Escáner ─────────────────────────────────────────────────────────────

  let jsqrP = null;
  function cargarJsQR() {
    if (window.jsQR) return Promise.resolve();
    if (jsqrP) return jsqrP;
    jsqrP = new Promise((ok, mal) => {
      const sc = document.createElement('script');
      sc.src = JSQR_SRC;
      sc.async = true;
      sc.onload = () => (window.jsQR ? ok() : mal(new Error('jsqr')));
      sc.onerror = () => { jsqrP = null; sc.remove(); mal(new Error('jsqr')); };
      document.head.append(sc);
    });
    return jsqrP;
  }

  async function crearDetector() {
    if (!('BarcodeDetector' in window)) return null;
    try {
      if (window.BarcodeDetector.getSupportedFormats) {
        const f = await window.BarcodeDetector.getSupportedFormats();
        if (!f.includes('qr_code')) return null;
      }
      return new window.BarcodeDetector({ formats: ['qr_code'] });
    } catch (e) {
      return null;
    }
  }

  function estadoEsc(t) { el('esc-estado').textContent = t; }

  function sinCamara(msg) {
    pararCamara();
    el('dlg-escaner').classList.add('sin-camara');
    estadoEsc(msg);
    el('esc-ayuda').textContent = 'Escribe el código de 8 letras y números que aparece debajo del QR, en el teléfono del cliente.';
    el('esc-ayuda').hidden = false;
    el('esc-codigo').focus();
  }

  async function abrirEscaner() {
    const d = el('dlg-escaner');
    const E = S.esc;
    d.classList.remove('sin-camara');
    el('esc-ayuda').hidden = true;
    el('esc-codigo').value = '';
    E.ultimo = '';
    if (!d.open) d.showModal();
    el('t-escaner').setAttribute('tabindex', '-1');
    el('t-escaner').focus();
    E.abierto = true;
    estadoEsc('Abriendo la cámara…');
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return sinCamara('Este teléfono no deja usar la cámara desde aquí (o la página no está en https).');
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
    } catch (e) {
      const permiso = e && (e.name === 'NotAllowedError' || e.name === 'SecurityError');
      return sinCamara(permiso
        ? 'No hay permiso para usar la cámara. Actívalo en los ajustes del navegador (ícono del candado junto a la dirección) o escribe el código.'
        : 'No encontramos una cámara disponible.');
    }
    if (!E.abierto) { stream.getTracks().forEach((t) => t.stop()); return; }
    E.stream = stream;
    const v = el('esc-video');
    v.srcObject = stream;
    try { await v.play(); } catch (e) { /* autoplay silencioso */ }
    E.detector = await crearDetector();
    if (!E.detector) {
      try { await cargarJsQR(); } catch (e) { return sinCamara('No se pudo cargar el lector de QR. Escribe el código.'); }
    }
    if (!E.abierto) return;
    estadoEsc('Apunta al QR del pedido del cliente.');
    ciclo();
  }

  let lienzo = null;
  async function ciclo() {
    const E = S.esc;
    if (!E.abierto || !E.stream) return;
    const v = el('esc-video');
    let txt = null;
    try {
      if (v.readyState >= 2 && v.videoWidth) {
        if (E.detector) {
          const r = await E.detector.detect(v);
          if (r && r.length) txt = r[0].rawValue;
        } else if (window.jsQR) {
          lienzo = lienzo || document.createElement('canvas');
          const k = Math.min(1, 720 / Math.max(v.videoWidth, v.videoHeight));
          const w = Math.round(v.videoWidth * k), hh = Math.round(v.videoHeight * k);
          lienzo.width = w; lienzo.height = hh;
          const ctx = lienzo.getContext('2d', { willReadFrequently: true });
          ctx.drawImage(v, 0, 0, w, hh);
          const img = ctx.getImageData(0, 0, w, hh);
          const c = window.jsQR(img.data, w, hh, { inversionAttempts: 'attemptBoth' });
          if (c && c.data) txt = c.data;
        }
      }
    } catch (e) { /* cuadro inválido: seguimos */ }
    if (!E.abierto) return;
    if (txt) {
      const r = interpretar(txt);
      if (r) {
        if (navigator.vibrate) navigator.vibrate(60);
        cerrarEscaner();
        abrirResultado(r);
        return;
      }
      if (txt !== E.ultimo) { E.ultimo = txt; estadoEsc('Ese QR no es de un pedido del Cisne. Prueba con el QR de la tarjeta «Para tu mesero».'); }
    }
    E.timer = setTimeout(ciclo, 160);
  }

  function pararCamara() {
    const E = S.esc;
    clearTimeout(E.timer);
    if (E.stream) E.stream.getTracks().forEach((t) => t.stop());
    E.stream = null;
    const v = el('esc-video');
    if (v) { v.pause(); v.srcObject = null; }
  }

  function cerrarEscaner() {
    S.esc.abierto = false;
    pararCamara();
    const d = el('dlg-escaner');
    if (d && d.open) d.close();
  }

  // ── Arranque ────────────────────────────────────────────────────────────

  function enlazar() {
    el('f-login').addEventListener('submit', entrar);
    const pin = el('l-pin');
    if (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) pin.setAttribute('inputmode', 'none');
    pin.addEventListener('input', () => {
      pin.value = pin.value.replace(/\D/g, '').slice(0, 6);
      if (pin.value.length === 6 && el('l-usuario').value.trim()) entrar();
    });
    el('teclado').addEventListener('click', (e) => {
      const b = e.target.closest('button[data-n]');
      if (!b) return;
      if (b.dataset.n === 'borrar') pin.value = pin.value.slice(0, -1);
      else if (pin.value.length < 6) pin.value += b.dataset.n;
      el('login-error').textContent = '';
      if (pin.value.length === 6 && el('l-usuario').value.trim()) entrar();
    });

    el('salir').addEventListener('click', salir);
    el('escanear').addEventListener('click', abrirEscaner);
    el('top-escanear').addEventListener('click', abrirEscaner);
    el('inicio-actualizar').addEventListener('click', () => cargarAbiertas(S.nav));
    el('f-codigo').addEventListener('submit', (e) => {
      e.preventDefault();
      const r = interpretar(el('codigo-input').value);
      if (!r) { el('codigo-error').textContent = 'Escribe el código de 8 letras y números que aparece debajo del QR.'; el('codigo-input').focus(); return; }
      el('codigo-error').textContent = '';
      el('codigo-input').value = '';
      abrirResultado(r);
    });

    // Escáner
    el('esc-cerrar').addEventListener('click', cerrarEscaner);
    el('dlg-escaner').addEventListener('close', () => { S.esc.abierto = false; pararCamara(); });
    el('esc-manual').addEventListener('submit', (e) => {
      e.preventDefault();
      const r = interpretar(el('esc-codigo').value);
      if (!r) { estadoEsc('Ese código no parece de un pedido. Son 8 letras y números.'); el('esc-codigo').focus(); return; }
      cerrarEscaner();
      abrirResultado(r);
    });

    // Cobro
    el('propina-seg').addEventListener('click', (e) => {
      const b = e.target.closest('button[data-p]');
      if (!b || !S.cobro) return;
      S.cobro.pct = Number(b.dataset.p);
      S.cobro.otra = '';
      el('propina-otra').value = '';
      pintarPropinaSeg();
      actualizarCobro();
    });
    el('propina-otra').addEventListener('input', (e) => {
      if (!S.cobro) return;
      S.cobro.otra = e.target.value;
      pintarPropinaSeg();
      actualizarCobro();
    });
    el('rapidos').replaceChildren(...Object.keys(MET).map((m) => h('button', { type: 'button', class: 'btn btn--ghost', 'data-m': m, onclick: () => cobrarRapido(m) },
      MET[m], h('small', { text: 'todo' }))));
    el('pago-agregar').addEventListener('click', () => {
      if (!S.cobro) return;
      const usados = S.cobro.pagos.map((p) => p.metodo);
      const metodo = Object.keys(MET).find((m) => !usados.includes(m)) || 'efectivo';
      S.cobro.pagos.push({ metodo, monto: '', recibe: '' });
      renderPagos();
      actualizarCobro();
      const i = S.cobro.pagos.length - 1;
      el('pago-monto-' + i).focus();
    });
    el('f-cobro').addEventListener('submit', cobrar);

    // Historial
    el('rango-chips').addEventListener('click', (e) => {
      const b = e.target.closest('button[data-r]');
      if (!b) return;
      S.hist.rango = b.dataset.r;
      S.hist.pagina = 1;
      pintarRango();
      cargarHistorial();
    });
    el('h-hora').addEventListener('change', () => { S.hist.hora = el('h-hora').checked; pintarRango(); cargarHistorial(); });
    ['h-estado', 'h-metodo', 'h-mesero', 'h-desde', 'h-hasta', 'h-desde-hora', 'h-hasta-hora'].forEach((id) => {
      el(id).addEventListener('change', () => { S.hist.pagina = 1; cargarHistorial(); });
    });
    el('f-filtros').addEventListener('submit', (e) => { e.preventDefault(); S.hist.pagina = 1; cargarHistorial(); });

    // Admin
    el('cierre-dia').addEventListener('change', () => cargarCierre());
    el('f-alta').addEventListener('submit', alta);

    // Diálogos: foco atrapado
    el('dlg').addEventListener('keydown', atraparFoco);
    el('dlg-escaner').addEventListener('keydown', atraparFoco);

    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && S.staff && S.vista === 'inicio') cargarAbiertas(S.nav);
    });
    window.addEventListener('hashchange', () => { if (el('dlg').open) el('dlg').close(); navegar(); });
  }

  async function iniciar() {
    const p = new URLSearchParams(location.search).get('p');
    if (p && limpiarCodigo(p)) history.replaceState(null, '', location.pathname + '#pedido/' + limpiarCodigo(p));
    enlazar();
    const r = await api('GET', '/yo');
    if (r.ok) ponerSesion(r.data);
    else if (r.status === 0) {
      mostrarLogin();
      el('login-error').textContent = r.data.error;
      return;
    }
    navegar();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
