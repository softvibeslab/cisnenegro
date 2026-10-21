/* Cervecería Cisne Negro · "Mi pedido" (funciones puras, sin DOM)
 *
 * El cliente arma su pedido en el teléfono y se lo MUESTRA al mesero (sin pagos). El pedido vive en
 * localStorage (`cisne-pedido-v1`) y caduca a las 12 h (cada visita al bar empieza limpia). Al tocar
 * "Mostrar al mesero" se envía a /api/pedidos y la tarjeta muestra un QR que el mesero escanea con la
 * app del equipo; sin conexión, el QR lleva el pedido dentro (`paraQR` / `desdeQR`).
 *
 * Pedido: { creado_at: ISO, mesa: string, lineas: Linea[] }
 * Linea:  { tipo: barril|lata|comida|bebida|vuelo, id, variante, cantidad (1–20), nota (≤40),
 *           precio (unitario), nombre, huella, cervezas? (solo vuelo: 4 ids) }
 *   - barril: variante = medida ("12 oz", "14 oz", "4 oz"); precio según la medida.
 *   - comida / bebida / lata con `variantes`: variante = id de la variante; precio de la variante.
 *   - vuelo: id = "vuelo", variante = null, cervezas = 4 ids de barril; precio = suma de sus 4 oz.
 * Ninguna función muta el pedido que recibe: siempre devuelven uno nuevo (o lanzan Error en español).
 *
 * Se expone como `window.CisnePedido` en el navegador y con `module.exports` en Node (pruebas).
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.CisnePedido = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const CLAVE = 'cisne-pedido-v1';
  const CADUCIDAD_MS = 12 * 60 * 60 * 1000;
  const MAX_CANTIDAD = 20;
  const MAX_LINEAS = 40;
  const MAX_NOTA = 40;
  const MAX_MESA = 10;
  const VUELO_N = 4;
  const TIPOS = ['barril', 'lata', 'comida', 'bebida', 'vuelo'];
  // Orden de la tarjeta para el mesero: primero bebidas (barril, vuelo, latas, sin alcohol), luego comida.
  const ORDEN_BEBIDAS = ['barril', 'vuelo', 'lata', 'bebida'];
  const ID_RE = /^[a-z0-9][a-z0-9_-]{0,79}$/;

  // ── Utilidades ─────────────────────────────────────────────────────────────
  const iso = (ms) => new Date(ms).toISOString();
  const ahoraMs = (ahora) => (ahora instanceof Date ? ahora.getTime() : typeof ahora === 'number' ? ahora : Date.now());

  function cantidadValida(n) {
    return typeof n === 'number' && Number.isInteger(n) && n >= 1 && n <= MAX_CANTIDAD;
  }

  /** Quita caracteres de control, junta espacios y recorta. */
  function limpiarTexto(s, max) {
    if (typeof s !== 'string') return '';
    return s.replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max);
  }
  const limpiarNota = (s) => limpiarTexto(s, MAX_NOTA);
  const limpiarMesa = (s) => limpiarTexto(typeof s === 'number' ? String(s) : s, MAX_MESA);

  function vacio(ahora) {
    return { creado_at: iso(ahoraMs(ahora)), mesa: '', lineas: [] };
  }

  function copiar(pedido) {
    return {
      creado_at: pedido.creado_at,
      mesa: pedido.mesa || '',
      lineas: (pedido.lineas || []).map((l) => ({ ...l, ...(l.cervezas ? { cervezas: l.cervezas.slice() } : {}) })),
    };
  }

  /** Las hamburguesas y sándwiches se llaman "De X" en el menú; fuera de su sección necesitan contexto
   *  (misma regla que menu.js y landing.js). */
  function nombrePlatillo(item) {
    const n = item.nombre;
    if (/^De /.test(n) && item.img) {
      const resto = 'de ' + n.slice(3);
      if (/^hambur/.test(item.img)) return 'Hamburguesa ' + resto;
      if (/^san_/.test(item.img)) return 'Sándwich ' + resto;
    }
    return n;
  }

  const precio4oz = (b) => (b && b.precios || []).find((p) => /^4\s*oz$/i.test(p.medida));

  // ── Catálogo ───────────────────────────────────────────────────────────────
  function buscarProducto(menu, tipo, id) {
    if (!menu) return null;
    if (tipo === 'barril') return (menu.barril || []).find((b) => b.id === id) || null;
    if (tipo === 'lata') return (menu.latas || []).find((b) => b.id === id) || null;
    if (tipo === 'bebida') return (menu.sin_alcohol || []).find((b) => b.id === id) || null;
    if (tipo === 'comida') {
      for (const s of menu.comida || []) {
        const it = (s.items || []).find((d) => d.id === id);
        if (it) return it;
      }
    }
    return null;
  }

  /** Resuelve un producto del catálogo publicado.
   *  → { ok: true, nombre, detalle, precio, variante, cervezas? }  o  { ok: false, motivo }
   *  motivo: 'no_existe' | 'agotado' | 'variante' (la medida o variante ya no existe). */
  function resolver(menu, tipo, id, variante, cervezas) {
    if (tipo === 'vuelo') {
      if (menu.vuelo && menu.vuelo.visible === false) return { ok: false, motivo: 'no_existe' };
      if (!Array.isArray(cervezas) || cervezas.length !== VUELO_N) return { ok: false, motivo: 'variante' };
      let precio = 0;
      const nombres = [];
      for (const cid of cervezas) {
        const b = buscarProducto(menu, 'barril', cid);
        if (!b) return { ok: false, motivo: 'no_existe' };
        if (b.disponible === false) return { ok: false, motivo: 'agotado' };
        const p = precio4oz(b);
        if (!p) return { ok: false, motivo: 'variante' };
        precio += p.precio;
        nombres.push(b.nombre);
      }
      return { ok: true, nombre: (menu.vuelo && menu.vuelo.nombre) || 'Vuelo del Cisne', detalle: VUELO_N + ' × 4 oz', precio, variante: null, cervezas: cervezas.slice(), nombresCervezas: nombres };
    }
    const prod = buscarProducto(menu, tipo, id);
    if (!prod) return { ok: false, motivo: 'no_existe' };
    if (prod.disponible === false) return { ok: false, motivo: 'agotado' };
    const nombre = tipo === 'comida' ? nombrePlatillo(prod) : prod.nombre;
    if (tipo === 'barril') {
      const m = (prod.precios || []).find((p) => p.medida === variante);
      if (!m) return { ok: false, motivo: 'variante' };
      return { ok: true, nombre, detalle: m.medida, precio: m.precio, variante: m.medida };
    }
    if (Array.isArray(prod.variantes) && prod.variantes.length) {
      const v = prod.variantes.find((x) => x.id === variante);
      if (!v || v.disponible === false) return { ok: false, motivo: 'variante' };
      const precio = typeof v.precio === 'number' ? v.precio : prod.precio + (v.extra || 0);
      return { ok: true, nombre, detalle: v.nombre, precio, variante: v.id };
    }
    if (variante != null && variante !== '') return { ok: false, motivo: 'variante' };
    return { ok: true, nombre, detalle: '', precio: prod.precio, variante: null };
  }

  /** Huella de lo que el cliente vio al agregar (nombre, medida/variante y precio). */
  const huellaDe = (r) => JSON.stringify([r.nombre, r.detalle, r.precio, r.cervezas || null]);

  const claveDe = (l) => [l.tipo, l.id, l.variante || '', (l.cervezas || []).join('+'), l.nota || ''].join('|');

  // ── Operaciones ────────────────────────────────────────────────────────────
  /** Agrega un producto. item: { tipo, id, variante?, cantidad = 1, nota = '', cervezas? (vuelo) }.
   *  Junta la misma tipo + id + variante (+ cervezas) + nota. Lanza Error si algo no es válido. */
  function agregar(pedido, item, menu, ahora) {
    const it = item || {};
    const cantidad = it.cantidad === undefined ? 1 : it.cantidad;
    if (!cantidadValida(cantidad)) throw new Error(`La cantidad debe ser un número entero del 1 al ${MAX_CANTIDAD}.`);
    if (!TIPOS.includes(it.tipo)) throw new Error('Ese producto no está en el menú.');
    const id = it.tipo === 'vuelo' ? 'vuelo' : it.id;
    const r = resolver(menu, it.tipo, id, it.variante, it.cervezas);
    if (!r.ok) {
      throw new Error(r.motivo === 'agotado' ? 'Ese producto está agotado por hoy.'
        : r.motivo === 'variante' ? (it.tipo === 'vuelo' ? `Elige ${VUELO_N} cervezas de barril para tu vuelo.` : 'Elige una medida o presentación disponible.')
          : 'Ese producto ya no está en el menú.');
    }
    const nota = limpiarNota(it.nota);
    const base = pedido && Array.isArray(pedido.lineas) ? copiar(pedido) : vacio(ahora);
    const nuevo = base.lineas.length ? base : { ...base, creado_at: iso(ahoraMs(ahora)) };
    const linea = {
      tipo: it.tipo, id, variante: r.variante, cantidad, nota,
      precio: r.precio, nombre: r.nombre, huella: huellaDe(r),
      ...(r.cervezas ? { cervezas: r.cervezas } : {}),
    };
    const k = claveDe(linea);
    const igual = nuevo.lineas.find((l) => claveDe(l) === k);
    if (igual) {
      if (igual.cantidad + cantidad > MAX_CANTIDAD) throw new Error(`Puedes pedir hasta ${MAX_CANTIDAD} de cada producto.`);
      igual.cantidad += cantidad;
      Object.assign(igual, { precio: r.precio, nombre: r.nombre, huella: linea.huella });
      delete igual.no_disponible; delete igual.precio_cambiado; delete igual.precio_nuevo;
    } else {
      if (nuevo.lineas.length >= MAX_LINEAS) throw new Error(`Tu pedido admite hasta ${MAX_LINEAS} productos distintos.`);
      nuevo.lineas.push(linea);
    }
    return nuevo;
  }

  function validarIndice(pedido, i) {
    if (!pedido || !Array.isArray(pedido.lineas) || !Number.isInteger(i) || i < 0 || i >= pedido.lineas.length) {
      throw new Error('Ese producto ya no está en tu pedido.');
    }
  }

  /** Si dos líneas quedaron iguales (p. ej. al editar una nota), las junta (máximo 20). */
  function juntarIguales(lineas) {
    const out = [];
    for (const l of lineas) {
      const igual = out.find((x) => claveDe(x) === claveDe(l));
      if (igual) igual.cantidad = Math.min(MAX_CANTIDAD, igual.cantidad + l.cantidad);
      else out.push(l);
    }
    return out;
  }

  function cambiarCantidad(pedido, i, cantidad) {
    validarIndice(pedido, i);
    if (!cantidadValida(cantidad)) throw new Error(`La cantidad debe ser un número entero del 1 al ${MAX_CANTIDAD}.`);
    const nuevo = copiar(pedido);
    nuevo.lineas[i].cantidad = cantidad;
    return nuevo;
  }

  function cambiarNota(pedido, i, nota) {
    validarIndice(pedido, i);
    const nuevo = copiar(pedido);
    nuevo.lineas[i].nota = limpiarNota(nota);
    nuevo.lineas = juntarIguales(nuevo.lineas);
    return nuevo;
  }

  function quitar(pedido, i) {
    validarIndice(pedido, i);
    const nuevo = copiar(pedido);
    nuevo.lineas.splice(i, 1);
    return nuevo;
  }

  function ponerMesa(pedido, mesa) {
    const nuevo = copiar(pedido);
    nuevo.mesa = limpiarMesa(mesa);
    return nuevo;
  }

  /** Acepta el precio nuevo de una línea marcada por `revalidar`. */
  function aceptarPrecio(pedido, i) {
    validarIndice(pedido, i);
    const nuevo = copiar(pedido);
    const l = nuevo.lineas[i];
    if (l.precio_cambiado) {
      l.precio = l.precio_nuevo;
      l.huella = l.huella_nueva || l.huella;
    }
    delete l.precio_cambiado; delete l.precio_nuevo; delete l.huella_nueva;
    return nuevo;
  }

  // ── Persistencia ───────────────────────────────────────────────────────────
  /** Texto para localStorage (sin las marcas de revalidación, que se recalculan al cargar). */
  function serializar(pedido) {
    const p = pedido || vacio();
    return JSON.stringify({
      creado_at: p.creado_at, mesa: p.mesa || '',
      lineas: (p.lineas || []).map((l) => {
        const o = { tipo: l.tipo, id: l.id, variante: l.variante == null ? null : l.variante, cantidad: l.cantidad, nota: l.nota || '', precio: l.precio, nombre: l.nombre, huella: l.huella };
        if (l.cervezas) o.cervezas = l.cervezas.slice();
        return o;
      }),
    });
  }

  /** Lee lo guardado. Tolera JSON corrupto o manipulado y vacía el pedido si tiene más de 12 h. */
  function restaurar(raw, ahora) {
    const t = ahoraMs(ahora);
    let d;
    try { d = typeof raw === 'string' ? JSON.parse(raw) : raw; } catch (e) { return vacio(t); }
    if (!d || typeof d !== 'object' || !Array.isArray(d.lineas)) return vacio(t);
    const creado = Date.parse(d.creado_at);
    if (!Number.isFinite(creado) || t - creado > CADUCIDAD_MS || creado - t > 5 * 60 * 1000) return vacio(t);
    const lineas = [];
    for (const x of d.lineas) {
      if (lineas.length >= MAX_LINEAS) break;
      if (!x || typeof x !== 'object' || !TIPOS.includes(x.tipo)) continue;
      if (typeof x.id !== 'string' || !ID_RE.test(x.id) || !cantidadValida(x.cantidad)) continue;
      if (typeof x.precio !== 'number' || !Number.isFinite(x.precio) || x.precio < 0) continue;
      const l = {
        tipo: x.tipo, id: x.id,
        variante: typeof x.variante === 'string' && x.variante.length <= 40 ? x.variante : null,
        cantidad: x.cantidad, nota: limpiarNota(x.nota), precio: x.precio,
        nombre: limpiarTexto(x.nombre, 80) || x.id,
        huella: typeof x.huella === 'string' ? x.huella.slice(0, 400) : '',
      };
      if (x.tipo === 'vuelo') {
        if (!Array.isArray(x.cervezas) || x.cervezas.length !== VUELO_N || !x.cervezas.every((c) => typeof c === 'string' && ID_RE.test(c))) continue;
        l.cervezas = x.cervezas.slice();
      }
      lineas.push(l);
    }
    return { creado_at: iso(creado), mesa: limpiarMesa(d.mesa), lineas: juntarIguales(lineas) };
  }

  const caducado = (pedido, ahora) => !pedido || ahoraMs(ahora) - Date.parse(pedido.creado_at) > CADUCIDAD_MS;

  // ── Revalidación contra el menú publicado ──────────────────────────────────
  /** Marca cada línea: `no_disponible` (ya no existe, se agotó o el barril rotó) o
   *  `precio_cambiado` + `precio_nuevo`. Si solo cambió el nombre, lo actualiza en silencio. */
  function revalidar(pedido, menu) {
    const nuevo = copiar(pedido);
    nuevo.lineas.forEach((l) => {
      delete l.no_disponible; delete l.motivo; delete l.precio_cambiado; delete l.precio_nuevo; delete l.huella_nueva;
      const r = resolver(menu, l.tipo, l.id, l.variante, l.cervezas);
      if (!r.ok) { l.no_disponible = true; l.motivo = r.motivo; return; }
      l.nombre = r.nombre;
      if (r.precio !== l.precio) {
        l.precio_cambiado = true;
        l.precio_nuevo = r.precio;
        l.huella_nueva = huellaDe(r);
      } else {
        l.huella = huellaDe(r);
      }
    });
    return nuevo;
  }

  /** Líneas que el cliente debe revisar antes de mostrar el pedido. */
  const pendientes = (pedido) => (pedido.lineas || []).filter((l) => l.no_disponible || l.precio_cambiado).length;

  // ── Totales y tarjeta ──────────────────────────────────────────────────────
  /** Total estimado: excluye lo no disponible y usa el precio nuevo donde cambió. */
  function total(pedido) {
    return (pedido && pedido.lineas || []).reduce((s, l) => {
      if (l.no_disponible) return s;
      return s + (l.precio_cambiado ? l.precio_nuevo : l.precio) * l.cantidad;
    }, 0);
  }

  /** Número de productos (suma de cantidades) que cuentan para la barra. */
  const contar = (pedido) => (pedido && pedido.lineas || []).reduce((s, l) => s + (l.no_disponible ? 0 : l.cantidad), 0);

  /** Tarjeta "Para tu mesero". Revalida contra el menú y EXCLUYE las líneas no disponibles y las de
   *  precio cambiado sin aceptar (no entran hasta que el cliente las revise).
   *  → { mesa, secciones: [{ titulo, lineas: [{ cantidad, nombre, detalle, cervezas?, nota, precio, importe }] }],
   *      total, productos, omitidas } */
  function tarjeta(pedido, menu) {
    const p = menu ? revalidar(pedido, menu) : copiar(pedido);
    const nombreCerveza = (id) => { const b = buscarProducto(menu, 'barril', id); return b ? b.nombre : id; };
    const fila = (l) => ({
      tipo: l.tipo, cantidad: l.cantidad, nombre: l.nombre,
      detalle: l.tipo === 'vuelo' ? VUELO_N + ' × 4 oz' : l.tipo === 'barril' ? l.variante : (l.variante ? detalleVariante(menu, l) : ''),
      ...(l.cervezas ? { cervezas: l.cervezas.map(nombreCerveza) } : {}),
      nota: l.nota || '', precio: l.precio, importe: l.precio * l.cantidad,
    });
    const validas = p.lineas.filter((l) => !l.no_disponible && !l.precio_cambiado);
    const bebidas = [];
    ORDEN_BEBIDAS.forEach((t) => validas.filter((l) => l.tipo === t).forEach((l) => bebidas.push(fila(l))));
    const comida = validas.filter((l) => l.tipo === 'comida').map(fila);
    const secciones = [];
    if (bebidas.length) secciones.push({ titulo: 'Bebidas', lineas: bebidas });
    if (comida.length) secciones.push({ titulo: 'Comida', lineas: comida });
    return {
      mesa: p.mesa || '',
      secciones,
      total: validas.reduce((s, l) => s + l.precio * l.cantidad, 0),
      productos: validas.reduce((s, l) => s + l.cantidad, 0),
      omitidas: p.lineas.length - validas.length,
    };
  }

  function detalleVariante(menu, l) {
    const prod = buscarProducto(menu, l.tipo, l.id);
    const v = prod && (prod.variantes || []).find((x) => x.id === l.variante);
    return v ? v.nombre : l.variante;
  }

  /** Texto de la medida o variante de una línea, para el drawer. */
  function detalleLinea(l, menu) {
    if (l.tipo === 'vuelo') return VUELO_N + ' × 4 oz';
    if (l.tipo === 'barril') return l.variante || '';
    return l.variante ? detalleVariante(menu, l) : '';
  }

  // ── Wi-Fi (cadena estándar para el QR) ─────────────────────────────────────
  /** WIFI:T:WPA;S:red;P:clave;;  — escapa \ ; , : " y en redes abiertas omite P:. */
  function cadenaWifi(w) {
    const esc = (s) => String(s == null ? '' : s).replace(/([\\;,:"])/g, '\\$1');
    const t = w && (w.seguridad === 'WEP' || w.seguridad === 'nopass') ? w.seguridad : 'WPA';
    return 'WIFI:T:' + t + ';S:' + esc(w && w.ssid) + ';' + (t === 'nopass' ? '' : 'P:' + esc(w && w.password) + ';') + ';';
  }

  // ── Pedido para el mesero (QR) ─────────────────────────────────────────────
  // En línea: el menú envía el pedido a POST /api/pedidos y el QR lleva la URL /equipo/?p=<código>.
  // Sin conexión: el QR lleva el pedido dentro (/equipo/#d=<base64url de {mesa, lineas}>).
  const CLAVE_CODIGO = 'cisne-pedido-codigo-v1';
  const MAX_QR = 900;                       // caracteres del payload #d= (la URL completa queda < ~1000)
  const MARGEN_CADUCIDAD_MS = 2 * 60 * 1000; // un código que vence en < 2 min ya no se reutiliza
  const CODIGO_RE = /^[A-Z0-9]{4,16}$/;

  /** Líneas que viajan al servidor: solo lo que el cliente ya revisó, con los campos mínimos
   *  (el servidor recalcula nombres y precios desde menu.json). */
  function lineasParaServidor(pedido) {
    return (pedido && pedido.lineas || [])
      .filter((l) => !l.no_disponible && !l.precio_cambiado)
      .map((l) => {
        const o = { tipo: l.tipo, id: l.id, variante: l.variante == null ? null : l.variante, cantidad: l.cantidad, nota: l.nota || '' };
        if (l.cervezas) o.cervezas = l.cervezas.slice();
        return o;
      });
  }

  /** Huella de lo que se envió (mesa + líneas): si no cambia, se reutiliza el mismo código. */
  const huellaPedido = (pedido) => JSON.stringify([limpiarMesa(pedido && pedido.mesa), lineasParaServidor(pedido)]);

  /** Código guardado que aún sirve para esta huella → código, o null. `guardado`: objeto o JSON. */
  function codigoVigente(guardado, huella, ahora) {
    let g = guardado;
    if (typeof g === 'string') { try { g = JSON.parse(g); } catch (e) { return null; } }
    if (!g || typeof g !== 'object' || g.huella !== huella || typeof g.codigo !== 'string' || !CODIGO_RE.test(g.codigo)) return null;
    const vence = Date.parse(g.expira_at);
    if (!Number.isFinite(vence) || vence - ahoraMs(ahora) < MARGEN_CADUCIDAD_MS) return null;
    return g.codigo;
  }

  /** "K7M2Q9AB" → "K7M2-Q9AB" (grupos de 4 para dictarlo si la cámara falla). */
  const formatoCodigo = (c) => (String(c || '').toUpperCase().replace(/[^A-Z0-9]/g, '').match(/.{1,4}/g) || []).join('-');

  // base64url sobre UTF-8 (acentos, "ñ" y emojis en las notas viajan intactos).
  function aBase64url(texto) {
    const bytes = new TextEncoder().encode(texto);
    let bin = '';
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
  function deBase64url(s) {
    if (typeof s !== 'string' || !/^[A-Za-z0-9_-]+$/.test(s)) throw new Error('base64url');
    let b = s.replace(/-/g, '+').replace(/_/g, '/');
    while (b.length % 4) b += '=';
    const bin = atob(b);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  }

  /** Línea compacta para el QR: omite lo que vale por defecto (variante null, cantidad 1, nota vacía). */
  function lineaCompacta(l, nota) {
    const o = { tipo: l.tipo, id: l.id };
    if (l.variante != null && l.variante !== '') o.variante = l.variante;
    if (l.cantidad !== 1) o.cantidad = l.cantidad;
    if (nota) o.nota = nota;
    if (l.cervezas) o.cervezas = l.cervezas.slice();
    return o;
  }

  /** Recorta una nota a n caracteres (con "…"); n = 0 la quita. */
  const recortarNota = (nota, n) => (!nota || nota.length <= n ? nota : n >= 4 ? nota.slice(0, n - 1).trim() + '…' : '');

  /** Pedido dentro del QR (respaldo sin conexión).
   *  → { datos: base64url de {mesa?, lineas}, recortado: bool (se cortaron notas), cabe: bool (datos ≤ max) }
   *  Si no cabe en `max` caracteres: 1) recorta todas las notas al mismo largo (hasta 8 caracteres);
   *  2) si aún no cabe, conserva las primeras notas (hasta 20 caracteres) mientras quepan y quita las demás.
   *  Las líneas nunca se quitan: en el peor caso el QR va sin notas (cabe: false si ni así cabe). */
  function paraQR(pedido, opciones) {
    const max = (opciones && opciones.max) || MAX_QR;
    const lineas = lineasParaServidor(pedido);
    const mesa = limpiarMesa(pedido && pedido.mesa);
    // Marca de creación (segundos en base 36): distingue una segunda ronda idéntica del mismo QR escaneado dos veces.
    const creado = Date.parse(pedido && pedido.creado_at);
    const armar = (notas) => {
      const o = {};
      if (Number.isFinite(creado)) o.t = Math.floor(creado / 1000).toString(36);
      if (mesa) o.mesa = mesa;
      o.lineas = lineas.map((l, i) => lineaCompacta(l, notas[i]));
      return aBase64url(JSON.stringify(o));
    };
    const tope = (n) => lineas.map((l) => recortarNota(l.nota, n));
    let datos = armar(tope(MAX_NOTA));
    if (datos.length <= max) return { datos, recortado: false, cabe: true };
    for (let n = MAX_NOTA - 2; n >= 8; n -= 2) {
      datos = armar(tope(n));
      if (datos.length <= max) return { datos, recortado: true, cabe: true };
    }
    const notas = lineas.map(() => '');
    datos = armar(notas);
    if (datos.length > max) return { datos, recortado: true, cabe: false };
    for (let i = 0; i < lineas.length; i++) {
      if (!lineas[i].nota) continue;
      notas[i] = recortarNota(lineas[i].nota, 20);
      const prueba = armar(notas);
      if (prueba.length <= max) datos = prueba; else notas[i] = '';
    }
    return { datos, recortado: true, cabe: true };
  }

  /** Lee el pedido de un QR sin conexión: acepta la URL completa, "#d=…" o solo el base64url.
   *  → { mesa, lineas: [{ tipo, id, variante, cantidad, nota, cervezas? }] }  o  null si no es válido. */
  function desdeQR(texto) {
    if (typeof texto !== 'string') return null;
    const m = texto.match(/[#?&]d=([A-Za-z0-9_-]+)/);
    let d;
    try { d = JSON.parse(deBase64url(m ? m[1] : texto.trim())); } catch (e) { return null; }
    if (!d || typeof d !== 'object' || !Array.isArray(d.lineas) || !d.lineas.length || d.lineas.length > MAX_LINEAS) return null;
    const lineas = [];
    for (const x of d.lineas) {
      if (!x || typeof x !== 'object' || !TIPOS.includes(x.tipo)) return null;
      const id = x.tipo === 'vuelo' ? 'vuelo' : x.id;
      const cantidad = x.cantidad === undefined ? 1 : x.cantidad;
      if (typeof id !== 'string' || !ID_RE.test(id) || !cantidadValida(cantidad)) return null;
      if (x.variante != null && (typeof x.variante !== 'string' || x.variante.length > 40)) return null;
      const l = { tipo: x.tipo, id, variante: x.variante == null || x.variante === '' ? null : x.variante, cantidad, nota: limpiarNota(x.nota) };
      if (x.tipo === 'vuelo') {
        if (!Array.isArray(x.cervezas) || x.cervezas.length !== VUELO_N || !x.cervezas.every((c) => typeof c === 'string' && ID_RE.test(c))) return null;
        l.cervezas = x.cervezas.slice();
      }
      lineas.push(l);
    }
    const r = { mesa: limpiarMesa(d.mesa), lineas };
    if (typeof d.t === 'string' && /^[0-9a-z]{1,12}$/.test(d.t)) r.t = d.t;
    return r;
  }

  return {
    CLAVE, CADUCIDAD_MS, MAX_CANTIDAD, MAX_LINEAS, MAX_NOTA, VUELO_N, CLAVE_CODIGO, MAX_QR,
    vacio, cantidadValida, limpiarNota, nombrePlatillo, resolver,
    agregar, cambiarCantidad, cambiarNota, quitar, ponerMesa, aceptarPrecio,
    serializar, restaurar, caducado, revalidar, pendientes,
    total, contar, tarjeta, detalleLinea, cadenaWifi,
    lineasParaServidor, huellaPedido, codigoVigente, formatoCodigo, paraQR, desdeQR,
  };
}));
