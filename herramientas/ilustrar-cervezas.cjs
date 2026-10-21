/* Ilustraciones de las cervezas de barril en el estilo de dibujo de Cisne Negro
 * (tinta negra a mano sobre crema, como sus posts "Cisne Negro te sugiere…").
 * Dibuja el vaso shaker con el logo "CISNE ⚡ NEGRO" (foto de referencia: google-maps/fotos/022.jpg)
 * con el color de cada estilo, un elemento propio de la cerveza y anotaciones a mano.
 *
 * Uso: NODE_PATH=<carpeta con playwright>/node_modules node herramientas/ilustrar-cervezas.cjs
 * Salida: sitio/assets/img/cervezas/<id>.png (luego se convierte a .jpg)
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUT = path.join(__dirname, '..', 'sitio', 'assets', 'img', 'cervezas');
fs.mkdirSync(OUT, { recursive: true });

const TINTA = '#16120E';
const CREMA = '#FBF6E6';

// ── Utilidades de trazo a mano ───────────────────────────────────────────────
function rng(seed) { let s = seed; return () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646; }
/** Trazo tembloroso que pasa por los puntos (subdivide y suaviza con curvas). */
function mano(puntos, r, amp = 2.2, cerrado = false) {
  const pts = [];
  const lista = cerrado ? [...puntos, puntos[0]] : puntos;
  for (let i = 0; i < lista.length - 1; i++) {
    const [x1, y1] = lista[i], [x2, y2] = lista[i + 1];
    const n = Math.max(2, Math.round(Math.hypot(x2 - x1, y2 - y1) / 38));
    for (let k = 0; k < n; k++) {
      const t = k / n;
      pts.push([x1 + (x2 - x1) * t + (r() - .5) * amp * 2, y1 + (y2 - y1) * t + (r() - .5) * amp * 2]);
    }
  }
  if (!cerrado) pts.push(lista[lista.length - 1]);
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const mx = (pts[i][0] + pts[i + 1][0]) / 2, my = (pts[i][1] + pts[i + 1][1]) / 2;
    d += ` Q${pts[i][0].toFixed(1)},${pts[i][1].toFixed(1)} ${mx.toFixed(1)},${my.toFixed(1)}`;
  }
  const u = pts[pts.length - 1];
  d += ` L${u[0].toFixed(1)},${u[1].toFixed(1)}` + (cerrado ? 'Z' : '');
  return d;
}
const linea = (d, w = 7, extra = '') => `<path d="${d}" fill="none" stroke="${TINTA}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" ${extra}/>`;
const relleno = (d, color, w = 6) => `<path d="${d}" fill="${color}" stroke="${TINTA}" stroke-width="${w}" stroke-linejoin="round"/>`;

/** Flecha a mano de (x1,y1) a (x2,y2) con curva. */
function flecha(r, x1, y1, x2, y2, curva = 40) {
  const mx = (x1 + x2) / 2 + curva, my = (y1 + y2) / 2 - curva * .4;
  const d = `M${x1},${y1} Q${mx},${my} ${x2},${y2}`;
  const ang = Math.atan2(y2 - my, x2 - mx);
  const a1 = ang + Math.PI * .82, a2 = ang - Math.PI * .82, L = 22;
  const punta = `M${(x2 + Math.cos(a1) * L).toFixed(1)},${(y2 + Math.sin(a1) * L).toFixed(1)} L${x2},${y2} L${(x2 + Math.cos(a2) * L).toFixed(1)},${(y2 + Math.sin(a2) * L).toFixed(1)}`;
  return linea(d, 4.5) + linea(punta, 4.5);
}
const texto = (x, y, s, t, extra = '') =>
  `<text x="${x}" y="${y}" font-family="'Gloria Hallelujah', 'Comic Sans MS', cursive" font-size="${s}" fill="${TINTA}" ${extra}>${t}</text>`;

// ── Vaso shaker de Cisne Negro ──────────────────────────────────────────────
function vaso(b, r) {
  const T = { y: 268, l: 232, r: 586 }, B = { y: 868, l: 282, r: 536 };
  const ins = 13;
  const xIzq = (y) => T.l + (B.l - T.l) * (y - T.y) / (B.y - T.y);
  const xDer = (y) => T.r + (B.r - T.r) * (y - T.y) / (B.y - T.y);
  const espumaY = T.y + b.espuma; // donde termina la espuma
  const fondoY = B.y - 34;
  let s = '';
  // sombra en la mesa
  s += `<ellipse cx="${(B.l + B.r) / 2}" cy="${B.y + 14}" rx="170" ry="18" fill="${TINTA}" opacity=".10"/>`;
  if (b.vidrio) {
    const vid = [[T.l, T.y], [B.l, B.y], [B.r, B.y], [T.r, T.y]];
    s += `<path d="${mano(vid, r, 1, true)}" fill="${b.vidrio}"/>`;
  }
  // cuerpo de la cerveza
  const cuerpo = [[xIzq(espumaY) + ins, espumaY], [xDer(espumaY) - ins, espumaY], [xDer(fondoY) - ins, fondoY], [xIzq(fondoY) + ins, fondoY]];
  s += `<path d="${mano(cuerpo, r, 1.4, true)}" fill="url(#cerveza)"/>`;
  // grano / textura (como los dibujos de la marca)
  for (let i = 0; i < b.grano; i++) {
    const y = espumaY + 20 + r() * (fondoY - espumaY - 30);
    const x = xIzq(y) + ins + 8 + r() * (xDer(y) - xIzq(y) - ins * 2 - 16);
    s += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(1.2 + r() * 2.2).toFixed(1)}" fill="${b.granoColor}" opacity="${(.25 + r() * .45).toFixed(2)}"/>`;
  }
  // burbujas
  for (let i = 0; i < b.burbujas; i++) {
    const y = espumaY + 40 + r() * (fondoY - espumaY - 60);
    const x = xIzq(y) + ins + 20 + r() * (xDer(y) - xIzq(y) - ins * 2 - 40);
    s += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(3 + r() * 5).toFixed(1)}" fill="none" stroke="${b.burbujaColor}" stroke-width="2.5" opacity=".75"/>`;
  }
  // turbidez (hazy)
  if (b.turbia) s += `<path d="${mano(cuerpo, r, 1.4, true)}" fill="url(#turbia)"/>`;
  // espuma: corona con burbujas arriba del borde y borde inferior ondulado
  const espuma = [];
  const n = 9;
  for (let i = 0; i <= n; i++) {
    const x = T.l + 4 + (T.r - T.l - 8) * i / n;
    espuma.push([x, T.y - 22 - Math.sin(i / n * Math.PI) * 26 - r() * 14]);
  }
  for (let i = n; i >= 0; i--) {
    const y = espumaY + (i % 2 ? 10 : -4);
    const x = xIzq(y) + ins - 2 + (xDer(y) - xIzq(y) - ins * 2 + 4) * i / n;
    espuma.push([x, y]);
  }
  s += relleno(mano(espuma, r, 2.5, true), b.espumaColor, 6);
  for (let i = 0; i < 7; i++) {
    const x = T.l + 40 + r() * (T.r - T.l - 80), y = T.y - 10 + r() * (b.espuma - 6);
    s += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(4 + r() * 6).toFixed(1)}" fill="none" stroke="${TINTA}" stroke-width="2.5" opacity=".35"/>`;
  }
  // logo impreso en el vaso: "CISNE ⚡ NEGRO" + "CERVECERÍA MEXICANA INDEPENDIENTE"
  const lc = b.logoClaro ? CREMA : TINTA;
  const ly = 530;
  const fuente = `font-family="'Big Shoulders Display', Impact, sans-serif" font-weight="900" font-size="42" fill="${lc}"`;
  s += `<text x="397" y="${ly}" text-anchor="end" ${fuente}>CISNE</text>`;
  s += `<text x="421" y="${ly}" text-anchor="start" ${fuente}>NEGRO</text>`;
  s += `<path d="M412,${ly - 33} L400,${ly - 12} L409,${ly - 12} L402,${ly + 2} L417,${ly - 19} L408,${ly - 19} Z" fill="${lc}"/>`; // rayo del logo
  s += `<text x="409" y="${ly + 24}" text-anchor="middle" font-family="'Big Shoulders Display', Impact, sans-serif" font-weight="800" font-size="13" letter-spacing="1.2" fill="${lc}">CERVECERÍA MEXICANA INDEPENDIENTE</text>`;
  // contorno del vaso (doble trazo ligero, como dibujo a tinta)
  const contorno = [[T.l, T.y], [B.l, B.y], [B.r, B.y], [T.r, T.y]];
  s += linea(mano(contorno, r, 2.4), 7.5);
  s += linea(mano([[T.l, T.y], [T.r, T.y]], r, 1.6), 5);
  s += linea(mano([[B.l + 6, B.y - 34], [B.r - 6, B.y - 34]], r, 1.4), 4); // base gruesa del vaso
  // reflejo
  s += linea(mano([[T.l + 30, T.y + 60], [T.l + 52, T.y + 380]], r, 1), 9, `stroke="${CREMA}" opacity=".55"`).replace(`stroke="${TINTA}" `, '');
  return s;
}

// ── Elementos propios de cada cerveza ───────────────────────────────────────
function lupulo(r, cx, cy, esc = 1) {
  let s = `<g transform="translate(${cx},${cy}) scale(${esc}) rotate(-12)">`;
  s += linea(mano([[0, -96], [4, -124], [22, -142]], r, 1.2), 5);
  s += relleno(mano([[10, -128], [58, -150], [66, -108], [24, -104]], r, 1.6, true), '#6E9A3E', 5);
  s += linea(mano([[16, -122], [52, -128]], r, .8), 3);
  // filas de brácteas de abajo hacia arriba: la de arriba se dibuja al final y tapa a la de abajo
  const filas = [[96, 1, 26], [62, 2, 32], [26, 3, 36], [-12, 3, 38], [-50, 3, 36], [-84, 2, 30]];
  for (const [y, k, w] of filas) for (let i = 0; i < k; i++) {
    const x = (i - (k - 1) / 2) * w * 1.25;
    const esc = [[x - w, y - 10], [x - w * .55, y - w * .9], [x + w * .55, y - w * .9], [x + w, y - 10], [x, y + w * .55]];
    s += relleno(mano(esc, r, 1.2, true), (i + k) % 2 ? '#A6CB5E' : '#BBD978', 5);
    s += linea(mano([[x, y - w * .7], [x, y + w * .2]], r, .6), 2.5, 'opacity=".45"');
  }
  return s + '</g>';
}
function sirena(r, cx, cy) {
  let s = `<g transform="translate(${cx},${cy})">`;
  for (const [a, l] of [[-150, 46], [-120, 40], [-90, 52], [-60, 40], [-30, 46]]) {
    const rad = a * Math.PI / 180;
    s += linea(mano([[Math.cos(rad) * 96, Math.sin(rad) * 96 - 20], [Math.cos(rad) * (96 + l), Math.sin(rad) * (96 + l) - 20]], r, 1), 6);
  }
  s += relleno(mano([[-62, 30], [-58, -30], [-34, -72], [0, -84], [34, -72], [58, -30], [62, 30]], r, 1.8, true), '#E2352B', 6);
  s += `<path d="M-30,-48 Q-40,-14 -38,18" fill="none" stroke="${CREMA}" stroke-width="10" stroke-linecap="round" opacity=".7"/>`;
  s += relleno(mano([[-86, 30], [86, 30], [86, 66], [-86, 66]], r, 1.6, true), '#2B2622', 6);
  return s + '</g>';
}
function corona(r, cx, cy) {
  let s = `<g transform="translate(${cx},${cy}) rotate(8)">`;
  s += relleno(mano([[-90, 50], [-100, -40], [-50, 4], [0, -70], [50, 4], [100, -40], [90, 50]], r, 2, true), '#F2C14E', 6);
  s += relleno(mano([[-92, 50], [92, 50], [92, 78], [-92, 78]], r, 1.4, true), '#E0A92E', 6);
  for (const [x, y, c] of [[-100, -48, '#E2352B'], [0, -80, '#2E6FD8'], [100, -48, '#E2352B'], [-40, 64, '#2E6FD8'], [40, 64, '#E2352B']])
    s += `<circle cx="${x}" cy="${y}" r="11" fill="${c}" stroke="${TINTA}" stroke-width="5"/>`;
  return s + '</g>';
}
function pina(r, cx, cy) {
  let s = `<g transform="translate(${cx},${cy}) rotate(10)">`;
  for (const [a, l] of [[-112, 92], [-90, 112], [-68, 92], [-128, 66], [-52, 66]]) {
    const rad = a * Math.PI / 180, x2 = Math.cos(rad) * l, y2 = Math.sin(rad) * l - 72;
    s += relleno(mano([[-12, -66], [x2, y2], [12, -66]], r, 1.4, true), '#5E9E3E', 5);
  }
  const cuerpoPina = mano([[0, -78], [58, -50], [70, 20], [44, 84], [0, 100], [-44, 84], [-70, 20], [-58, -50]], r, 2, true);
  s += `<clipPath id="pinaC"><path d="${cuerpoPina}"/></clipPath>`;
  s += relleno(cuerpoPina, '#F2B632', 6);
  s += '<g clip-path="url(#pinaC)">';
  for (let i = -3; i <= 3; i++) {
    s += linea(mano([[-60 + i * 4, -40 + i * 22], [60 + i * 4, 30 + i * 22]], r, 1), 3.5, 'opacity=".55"');
    s += linea(mano([[60 + i * 4, -40 + i * 22], [-60 + i * 4, 30 + i * 22]], r, 1), 3.5, 'opacity=".55"');
  }
  s += '</g>' + linea(cuerpoPina, 6);
  return s + '</g>';
}
function mango(r, cx, cy) {
  let s = `<g transform="translate(${cx},${cy}) rotate(-28)">`;
  s += `<defs><linearGradient id="mangoG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F7C431"/><stop offset=".55" stop-color="#F59A2A"/><stop offset="1" stop-color="#E5552E"/></linearGradient></defs>`;
  s += relleno(mano([[-72, 10], [-60, -34], [-18, -60], [40, -54], [78, -14], [72, 34], [34, 58], [-24, 56], [-62, 40]], r, 1.6, true), 'url(#mangoG)', 6);
  s += `<path d="M-38,-30 Q0,-48 40,-30" fill="none" stroke="${CREMA}" stroke-width="9" stroke-linecap="round" opacity=".55"/>`;
  s += linea(mano([[-56, -36], [-74, -58]], r, .8), 6);
  s += relleno(mano([[-72, -56], [-118, -70], [-96, -40]], r, 1.2, true), '#5E9E3E', 5);
  return s + '</g>';
}
function granoCafe(r, cx, cy, rot) {
  let s = `<g transform="translate(${cx},${cy}) rotate(${rot})">`;
  s += relleno(mano([[-38, 0], [-26, -26], [0, -34], [26, -26], [38, 0], [26, 26], [0, 34], [-26, 26]], r, 1.4, true), '#5A3420', 6);
  s += linea(mano([[0, -30], [-10, -8], [10, 8], [0, 30]], r, 1), 5);
  return s + '</g>';
}
function chocolate(r, cx, cy) {
  let s = `<g transform="translate(${cx},${cy}) rotate(-10)">`;
  s += relleno(mano([[-80, -50], [80, -50], [80, 50], [-80, 50]], r, 1.6, true), '#3B2416', 6);
  for (const x of [-27, 27]) s += linea(mano([[x, -48], [x, 48]], r, 1), 4.5, `stroke="${'#1E120C'}"`).replace(`stroke="${TINTA}" `, '');
  s += linea(mano([[-78, 0], [78, 0]], r, 1), 4.5);
  return s + '</g>';
}
function guayaba(r, cx, cy) {
  let s = `<g transform="translate(${cx},${cy}) rotate(-8)">`;
  s += relleno(mano([[-82, 0], [-58, -60], [0, -84], [58, -60], [82, 0], [58, 60], [0, 84], [-58, 60]], r, 2, true), '#9BBF4E', 6);
  s += relleno(mano([[-62, 0], [-44, -44], [0, -64], [44, -44], [62, 0], [44, 44], [0, 64], [-44, 44]], r, 1.6, true), '#F2A5A0', 5);
  s += `<circle r="30" fill="#E76F7A" opacity=".8"/>`;
  for (let i = 0; i < 14; i++) {
    const a = r() * Math.PI * 2, d = 10 + r() * 22;
    s += `<ellipse cx="${(Math.cos(a) * d).toFixed(1)}" cy="${(Math.sin(a) * d).toFixed(1)}" rx="4" ry="6" fill="${CREMA}" stroke="${TINTA}" stroke-width="2"/>`;
  }
  return s + '</g>';
}
function jamaica(r, cx, cy) {
  let s = `<g transform="translate(${cx},${cy})">`;
  for (let i = 0; i < 5; i++) {
    const a = i * 72 * Math.PI / 180;
    const pts = [[0, 0], [Math.cos(a - .5) * 70, Math.sin(a - .5) * 70], [Math.cos(a) * 84, Math.sin(a) * 84], [Math.cos(a + .5) * 70, Math.sin(a + .5) * 70]];
    s += relleno(mano(pts, r, 2, true), i % 2 ? '#B3264A' : '#C8335A', 5);
  }
  s += `<circle r="16" fill="#F2C14E" stroke="${TINTA}" stroke-width="5"/>`;
  return s + '</g>';
}
function estrella(r, cx, cy, t) {
  return relleno(mano([[cx, cy - t], [cx + t * .22, cy - t * .22], [cx + t, cy], [cx + t * .22, cy + t * .22], [cx, cy + t], [cx - t * .22, cy + t * .22], [cx - t, cy], [cx - t * .22, cy - t * .22]], r, .8, true), '#F2C97D', 5);
}
function papalote(r, cx, cy) {
  // "Barrilete" = papalote (como en la etiqueta oficial de Barrilete Cósmico)
  let s = `<g transform="translate(${cx},${cy}) rotate(-16)">`;
  const A = [0, -96], B = [68, -6], C = [0, 104], D = [-68, -6], O = [0, -6];
  s += relleno(mano([A, B, O], r, 1.2, true), '#F2C14E', 5);
  s += relleno(mano([B, C, O], r, 1.2, true), '#F08A24', 5);
  s += relleno(mano([C, D, O], r, 1.2, true), '#2FA39A', 5);
  s += relleno(mano([D, A, O], r, 1.2, true), '#9BCB5E', 5);
  s += linea(mano([A, C], r, .8), 4) + linea(mano([D, B], r, .8), 4);
  s += linea(mano([[0, 104], [-24, 150], [18, 190], [-10, 236], [24, 270]], r, 2), 4.5);
  for (const [x, y, c] of [[-24, 150, '#E2352B'], [18, 190, '#F2C14E'], [-10, 236, '#2E6FD8']])
    s += relleno(mano([[x - 14, y - 8], [x + 14, y + 8], [x - 14, y + 8], [x + 14, y - 8]], r, .6, true), c, 4);
  return s + '</g>';
}

// ── Las 6 cervezas de barril (datos de sitio/data/menu.json) ─────────────────
const CERVEZAS = [
  { id: 'alarma', seed: 11, nombre: '¡ALARMA!', estilo: 'RED IPA · 7.0%', de: 'DE CISNE NEGRO',
    c1: '#C4532A', c2: '#8E2F17', espuma: 74, espumaColor: '#FFF4DE', grano: 70, granoColor: '#5E1F0E', burbujas: 10, burbujaColor: '#F6C9A0',
    nota: ['MALTA CARAMELO', '+ LÚPULO'], extra: (r) => sirena(r, 790, 300) + lupulo(r, 810, 720, .75), notaXY: [800, 500], flechaA: [700, 470, 598, 560] },
  { id: 'henry-ix', seed: 23, nombre: 'HENRY IX', estilo: 'IPA · 5.0%', de: 'DE CISNE NEGRO',
    c1: '#F2C14E', c2: '#D89A24', espuma: 66, espumaColor: '#FFF8E8', grano: 60, granoColor: '#A8701A', burbujas: 16, burbujaColor: '#FFF1C8',
    nota: ['DORADA', 'Y LIGERA'], extra: (r) => corona(r, 790, 320) + lupulo(r, 815, 730, .7), notaXY: [800, 520], flechaA: [700, 490, 598, 590] },
  { id: 'a-poco-si-pa', seed: 37, nombre: '¿A POCO SÍ PA\'?', estilo: 'AMERICAN IPA · 6.9%', de: 'DE CISNE NEGRO',
    c1: '#F0A32C', c2: '#C9741A', espuma: 70, espumaColor: '#FFF6E2', grano: 64, granoColor: '#8A4E10', burbujas: 12, burbujaColor: '#FFE3B0',
    nota: ['PIÑA, MANGO', 'Y PAPAYA'], extra: (r) => pina(r, 800, 330) + mango(r, 815, 720), notaXY: [800, 530], flechaA: [700, 500, 598, 600] },
  { id: 'agua-puerca', seed: 41, nombre: 'AGUA PUERCA', estilo: 'IMPERIAL STOUT · 8.9%', de: 'DE CISNE NEGRO', logoClaro: true,
    c1: '#2A1A12', c2: '#140B07', espuma: 62, espumaColor: '#D9B48A', grano: 90, granoColor: '#F3E3C8', burbujas: 0, burbujaColor: '#000',
    nota: ['CHOCOLATE', 'Y CAFÉ'], extra: (r) => chocolate(r, 800, 330) + granoCafe(r, 770, 700, -20) + granoCafe(r, 870, 750, 30), notaXY: [800, 520], flechaA: [700, 490, 598, 580] },
  { id: 'guamaica', seed: 53, nombre: 'GUAMAICA', estilo: 'SOUR · 4.0%', de: 'DE CUATRO PALOS',
    c1: '#D6456A', c2: '#A3223F', espuma: 58, espumaColor: '#FFE7EC', grano: 50, granoColor: '#6E1027', burbujas: 22, burbujaColor: '#FFD3DD',
    nota: ['GUAYABA', 'Y JAMAICA'], extra: (r) => guayaba(r, 800, 320) + jamaica(r, 815, 720), notaXY: [800, 520], flechaA: [700, 490, 598, 590] },
  { id: 'barrilete-cosmico', seed: 67, nombre: 'BARRILETE CÓSMICO', estilo: 'HAZY IPA · 6.1%', de: 'DE CISNE NEGRO', turbia: true,
    c1: '#F6C14A', c2: '#E9A52E', espuma: 72, espumaColor: '#FFF8E6', grano: 40, granoColor: '#B8761C', burbujas: 4, burbujaColor: '#FFF0C8',
    nota: ['TURBIA', 'Y JUGOSA'], extra: (r) => papalote(r, 805, 300) + estrella(r, 690, 200, 26) + estrella(r, 930, 410, 20) + estrella(r, 860, 770, 30) + estrella(r, 690, 800, 16),
    notaXY: [800, 660], flechaA: [700, 635, 598, 690] },
];

function svg(b) {
  const r = rng(b.seed);
  const nombreSize = b.nombre.length > 12 ? 50 : 64;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" width="1000" height="1000">
  <defs>
    <linearGradient id="cerveza" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${b.c1}"/><stop offset="1" stop-color="${b.c2}"/></linearGradient>
    <linearGradient id="turbia" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#FFF6DA" stop-opacity=".35"/><stop offset=".5" stop-color="#FFF6DA" stop-opacity=".12"/><stop offset="1" stop-color="#FFF6DA" stop-opacity=".3"/></linearGradient>
    <filter id="papel"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="${b.seed}"/><feColorMatrix values="0 0 0 0 0.09  0 0 0 0 0.07  0 0 0 0 0.05  0 0 0 .07 0"/><feComposite in2="SourceGraphic" operator="in"/></filter>
  </defs>
  <rect width="1000" height="1000" fill="${CREMA}"/>
  <rect width="1000" height="1000" fill="${CREMA}" filter="url(#papel)"/>
  ${b.extra(r)}
  ${vaso(b, r)}
  ${texto(54, 112, nombreSize, b.nombre)}
  ${texto(58, 172, 32, b.estilo)}
  ${texto(b.notaXY[0], b.notaXY[1] - 36, 30, b.nota[0], 'text-anchor="middle"')}
  ${texto(b.notaXY[0], b.notaXY[1], 30, b.nota[1], 'text-anchor="middle"')}
  ${flecha(r, b.flechaA[0], b.flechaA[1], b.flechaA[2], b.flechaA[3], -30)}
  ${texto(560, 950, 30, b.de)}
  ${flecha(r, 548, 930, 500, 885, 30)}
</svg>`;
}


// ── Diseños especializados con base en la etiqueta oficial ──────────────────
const ETQ_DIR = path.join(OUT, 'etiquetas');
const dataUri = (f, mime = 'image/jpeg') => `data:${mime};base64,${fs.readFileSync(f).toString('base64')}`;

/** Calcomanía con la etiqueta real (recorte opcional), margen de papel y borde de tinta. */
function calcomania(uri, img, crop, x, y, w, rot, papel = '#FBF6E6') {
  const [cx, cy, cw, ch] = crop || [0, 0, img[0], img[1]];
  const h = w * ch / cw, m = 14;
  return `<g transform="translate(${x},${y}) rotate(${rot})">
    <rect x="${-w / 2 - m + 10}" y="${-h / 2 - m + 14}" width="${w + m * 2}" height="${h + m * 2}" rx="10" fill="#000" opacity=".28"/>
    <rect x="${-w / 2 - m}" y="${-h / 2 - m}" width="${w + m * 2}" height="${h + m * 2}" rx="10" fill="${papel}" stroke="${TINTA}" stroke-width="6"/>
    <svg x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" viewBox="${cx} ${cy} ${cw} ${ch}" preserveAspectRatio="xMidYMid slice">
      <image href="${uri}" width="${img[0]}" height="${img[1]}"/></svg>
    <rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" fill="none" stroke="${TINTA}" stroke-width="3"/>
  </g>`;
}
const HALO = (c) => `<filter id="halo" x="-15%" y="-15%" width="130%" height="130%"><feMorphology in="SourceAlpha" operator="dilate" radius="6" result="d"/><feFlood flood-color="${c}"/><feComposite in2="d" operator="in" result="h"/><feMerge><feMergeNode in="h"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
const vasoEn = (b, r, tx, ty, esc, filtro = '') => `<g transform="translate(${tx},${ty}) scale(${esc})" ${filtro}>${vaso(b, r)}</g>`;
function lluvia(r, n, x0, y0, x1, y1, colores, rmin, rmax, op = 1) {
  let s = '';
  for (let i = 0; i < n; i++) s += `<circle cx="${(x0 + r() * (x1 - x0)).toFixed(1)}" cy="${(y0 + r() * (y1 - y0)).toFixed(1)}" r="${(rmin + r() * (rmax - rmin)).toFixed(1)}" fill="${colores[i % colores.length]}" opacity="${op}"/>`;
  return s;
}
function cola(r, x, y, dir, color) {
  // cola de diablo rosa como en la etiqueta de ¡Alarma!
  const d = dir;
  const c = `M${x},${y} C${x + 30 * d},${y + 8} ${x + 34 * d},${y + 56} ${x + 46 * d},${y + 44}`;
  let s = `<path d="${c}" fill="none" stroke="${TINTA}" stroke-width="20" stroke-linecap="round"/>`;
  s += `<path d="${c}" fill="none" stroke="${color}" stroke-width="10" stroke-linecap="round"/>`;
  const px = x + 46 * d, py = y + 44;
  s += relleno(mano([[px - 8 * d, py - 26], [px + 40 * d, py - 4], [px - 4 * d, py + 26], [px + 8 * d, py]], r, .5, true), color, 5);
  return s;
}
function llama(r, x, base, alto, ancho, c1, c2) {
  const pts = [[x - ancho / 2, base], [x - ancho * .45, base - alto * .45], [x - ancho * .15, base - alto * .7], [x - ancho * .05, base - alto], [x + ancho * .2, base - alto * .62], [x + ancho * .42, base - alto * .5], [x + ancho / 2, base]];
  const ext = relleno(mano(pts, r, 2, true), c1, 5);
  const int = pts.map(([px, py]) => [x + (px - x) * .55, base - (base - py) * .62]);
  return ext + `<path d="${mano(int, r, 1.4, true)}" fill="${c2}"/>`;
}

const DISENOS = {
  alarma: (b, r) => {
    const etq = dataUri(path.join(ETQ_DIR, 'alarma.jpg'));
    const pluma = dataUri(path.join(OUT, '..', 'marca', 'pluma.png'), 'image/png');
    const ROSA = '#E8505B', MOSTAZA = '#CEC14E', CREMA2 = '#FBFBE3';
    return `<rect width="1000" height="1000" fill="${CREMA2}"/>
      <rect x="60" y="250" width="880" height="630" rx="30" fill="${MOSTAZA}"/>
      ${lluvia(r, 1400, 70, 260, 930, 870, ['#A89A2E', '#E3D86E'], .8, 2.2, .55)}
      <rect x="60" y="250" width="880" height="630" rx="30" fill="none" stroke="${TINTA}" stroke-width="12"/>
      ${cola(r, 66, 760, -1, ROSA)}${cola(r, 934, 330, 1, ROSA)}
      ${vasoEn(b, r, 6, 66, .92)}
      ${calcomania(etq, [809, 1000], null, 735, 545, 290, 7)}
      <g transform="rotate(-3 440 150)">
        <rect x="120" y="70" width="640" height="160" rx="44" fill="${ROSA}" stroke="${TINTA}" stroke-width="12"/>
        <text x="440" y="182" text-anchor="middle" font-family="'Rubik Wet Paint', 'Rubik Dirt', Impact, sans-serif" font-size="104" fill="${TINTA}">¡ALARMA!</text>
      </g>
      <image href="${pluma}" x="740" y="34" width="110" height="222" transform="rotate(24 795 145)"/>
      <polygon points="262,920 768,920 748,956 242,956" fill="${ROSA}"/>
      <text x="500" y="952" text-anchor="middle" font-family="'Big Shoulders Display', Impact, sans-serif" font-weight="900" font-size="66" fill="${TINTA}">RED IPA · 7.0%</text>`;
  },
  'a-poco-si-pa': (b, r) => {
    const etq = dataUri(path.join(ETQ_DIR, 'a-poco-si-pa.jpg'));
    let s = `<defs>
        <radialGradient id="rojo" cx=".82" cy=".85" r=".75"><stop offset="0" stop-color="#8A1F1F"/><stop offset="1" stop-color="#8A1F1F" stop-opacity="0"/></radialGradient>
        <radialGradient id="morado" cx=".12" cy=".18" r=".6"><stop offset="0" stop-color="#2C2552"/><stop offset="1" stop-color="#2C2552" stop-opacity="0"/></radialGradient>
        <linearGradient id="rayas" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#2B3C8E"/><stop offset=".3" stop-color="#2B3C8E"/><stop offset=".3" stop-color="#C43A2C"/><stop offset=".55" stop-color="#C43A2C"/>
          <stop offset=".55" stop-color="#E8892E"/><stop offset=".78" stop-color="#E8892E"/><stop offset=".78" stop-color="#F2C24B"/><stop offset="1" stop-color="#F2C24B"/></linearGradient>
        ${HALO('#FBF1DC')}
      </defs>
      <rect width="1000" height="1000" fill="#141012"/><rect width="1000" height="1000" fill="url(#morado)"/><rect width="1000" height="1000" fill="url(#rojo)"/>`;
    // rayos de santo, como el halo del póster
    for (let i = 0; i < 28; i++) {
      const a = (-170 + i * (160 / 27)) * Math.PI / 180;
      s += `<line x1="${(360 + Math.cos(a) * 250).toFixed(1)}" y1="${(470 + Math.sin(a) * 250).toFixed(1)}" x2="${(360 + Math.cos(a) * 470).toFixed(1)}" y2="${(470 + Math.sin(a) * 470).toFixed(1)}" stroke="#F3E3C0" stroke-width="5" stroke-linecap="round" opacity=".28"/>`;
    }
    // llamas al pie, como en el póster
    for (let i = 0; i < 16; i++) s += llama(r, 30 + i * 66, 1012, 150 + (i % 3) * 55 + r() * 40, 120, '#E8562B', '#F2B33D');
    s += vasoEn({ ...b, vidrio: 'rgba(251,241,220,.10)' }, r, 0, 70, .88, 'filter="url(#halo)"');
    s += calcomania(etq, [1000, 1000], [195, 55, 610, 890], 790, 560, 270, -6);
    s += `<text x="506" y="156" text-anchor="middle" font-family="'Bungee', Impact, sans-serif" font-size="100" fill="#0B0A0A">¿A POCO SÍ PA'?</text>
      <text x="500" y="150" text-anchor="middle" font-family="'Bungee', Impact, sans-serif" font-size="100" fill="url(#rayas)" stroke="#FBF1DC" stroke-width="4" paint-order="stroke">¿A POCO SÍ PA'?</text>
      <text x="500" y="214" text-anchor="middle" font-family="'JetBrains Mono', monospace" font-weight="700" font-size="30" letter-spacing="2" fill="#F3E3C0">AMERICAN IPA · 6.9% · 62 IBU</text>`;
    return s;
  },
  'barrilete-cosmico': (b, r) => {
    const etq = dataUri(path.join(ETQ_DIR, 'barrilete-cosmico.jpg'));
    const ORO = '#E8D9A0';
    let s = `<defs>${HALO('#F1E6C2')}</defs><rect width="1000" height="1000" fill="#101E21"/>`;
    s += lluvia(r, 340, 0, 0, 1000, 1000, ['#E0A64A', '#D6C677', '#F2C97D'], 1, 4.5, .85);
    // remolino cósmico (ola turquesa y azul de la etiqueta)
    const giro = 'M120,900 C-40,620 120,330 430,300 C760,270 960,470 900,700 C850,880 640,960 480,930';
    s += `<path d="${giro}" fill="none" stroke="#0D383D" stroke-width="150" stroke-linecap="round"/>`;
    s += `<path d="${giro}" fill="none" stroke="#1E6C70" stroke-width="70" stroke-linecap="round" opacity=".95"/>`;
    s += `<path d="${giro}" fill="none" stroke="#2E7DBA" stroke-width="16" stroke-linecap="round" stroke-dasharray="120 46"/>`;
    // constelación
    const pts = [[90, 330], [190, 250], [300, 300], [700, 290], [820, 230], [915, 330]];
    s += `<polyline points="${pts.map((p) => p.join(',')).join(' ')}" fill="none" stroke="${ORO}" stroke-width="2.5" opacity=".9"/>`;
    for (const [x, y] of pts) s += estrella(r, x, y, 15);
    s += `<g transform="translate(150,520) scale(.6)">${papalote(r, 0, 0)}</g><g transform="translate(870,500) scale(.5) rotate(22)">${papalote(r, 0, 0)}</g>`;
    // vaso con salpicadura de espuma
    s += vasoEn({ ...b, vidrio: 'rgba(241,230,194,.10)' }, r, 155, 150, .76, 'filter="url(#halo)"');
    for (const [x, y, rr] of [[380, 318, 13], [350, 292, 8], [612, 312, 15], [646, 286, 9], [470, 268, 7], [560, 262, 10], [330, 340, 6], [676, 330, 6]])
      s += `<circle cx="${x}" cy="${y}" r="${rr}" fill="#FFF8E6" stroke="${TINTA}" stroke-width="4"/>`;
    s += calcomania(etq, [1000, 908], null, 820, 850, 250, 7, '#F1E6C2');
    s += `<text x="500" y="60" text-anchor="middle" font-family="'Big Shoulders Display', Impact, sans-serif" font-weight="900" font-size="34" letter-spacing="2" fill="${ORO}">CISNE ⚡ NEGRO</text>
      <text x="500" y="160" text-anchor="middle" font-family="'Big Shoulders Display', Impact, sans-serif" font-weight="900" font-size="112" letter-spacing="2" fill="#F1E6C2">BARRILETE</text>
      <text x="500" y="248" text-anchor="middle" font-family="'Rubik Wet Paint', Impact, sans-serif" font-size="92" fill="#F1E6C2">CÓSMICO</text>
      <text x="56" y="955" font-family="'JetBrains Mono', monospace" font-weight="700" font-size="32" letter-spacing="2" fill="${ORO}">HAZY IPA · 6.1%</text>`;
    return s;
  },
};

function svgDiseno(b) {
  const r = rng(b.seed + 1000);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" width="1000" height="1000">
    <defs><linearGradient id="cerveza" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${b.c1}"/><stop offset="1" stop-color="${b.c2}"/></linearGradient>
    <linearGradient id="turbia" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#FFF6DA" stop-opacity=".35"/><stop offset=".5" stop-color="#FFF6DA" stop-opacity=".12"/><stop offset="1" stop-color="#FFF6DA" stop-opacity=".3"/></linearGradient></defs>
    ${DISENOS[b.id](b, r)}</svg>`;
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1000, height: 1000 }, deviceScaleFactor: 1 });
  for (const b of CERVEZAS) {
    await page.setContent(`<!doctype html><html><head>
      <link href="https://fonts.googleapis.com/css2?family=Gloria+Hallelujah&family=Big+Shoulders+Display:wght@800;900&family=Rubik+Wet+Paint&family=Bungee&family=JetBrains+Mono:wght@700&display=block" rel="stylesheet">
      <style>html,body{margin:0;background:${CREMA}}svg{display:block}</style></head><body>${DISENOS[b.id] ? svgDiseno(b) : svg(b)}</body></html>`, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path.join(OUT, `${b.id}.png`) });
    console.log('✓', b.id);
  }
  await browser.close();
})();
