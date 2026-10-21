/* Ejecutar: node tests/menu-availability.cjs. No crea pedidos en el servidor. */
'use strict';
const assert = require('node:assert/strict');
const P = require('../sitio/assets/js/pedido.js');
const menu = structuredClone(require('../sitio/data/menu.json'));
const beers = menu.barril.slice(0, 4).map((b) => b.id);
const item = { tipo: 'vuelo', cervezas: beers };

// Las publicaciones anteriores sin el indicador conservan su comportamiento.
delete menu.vuelo.visible;
assert.equal(P.resolver(menu, 'vuelo', 'vuelo', null, beers).ok, true);
const original = P.agregar(P.vacio(), item, menu);
const hidden = structuredClone(menu);
hidden.vuelo.visible = false;
assert.deepEqual(P.resolver(hidden, 'vuelo', 'vuelo', null, beers), { ok: false, motivo: 'no_existe' });
assert.throws(() => P.agregar(P.vacio(), item, hidden));

// Un carrito guardado pide revisión al retirarse la oferta, sin alterar su copia previa.
const revalidated = P.revalidar(original, hidden);
assert.equal(P.pendientes(revalidated), 1);
assert.equal(P.total(revalidated), 0);
assert.equal(original.lineas[0].no_disponible, undefined);
const b = menu.barril[0];
assert.deepEqual(P.resolver(hidden, 'barril', b.id, b.precios[0].medida),
  P.resolver(menu, 'barril', b.id, b.precios[0].medida));
console.log('OK: oferta oculta rechazada, carrito revalidado y productos individuales conservados.');
