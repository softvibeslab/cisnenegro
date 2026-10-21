/* Cervecería Cisne Negro · Landing
 * - Barril de hoy y Vuelo del Cisne desde /data/menu.json (fuente única).
 * - Oculta maridajes cuya cerveza ya no está en barril.
 * - Lightbox de la galería con <dialog>.
 */
(function () {
  'use strict';

  var DATA_URL = document.body.dataset.menuUrl || '/data/menu.json';
  var CMS_PREVIEW = document.body.dataset.cmsPreview === 'true';
  var PERFIL_LABEL = { lupulada: 'Lupulada', oscura: 'Oscura', acida: 'Ácida', ligera: 'Ligera' };
  var ASK = '¿Por qué se llama así? Pregúntale a tu bartender.';
  var MEDIA_FOCAL = {};

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function money(n) { return '$' + Number(n).toLocaleString('es-MX'); }
  function abv(n) { return Number(n).toFixed(1) + '% ABV'; }

  // El nombre del platillo no depende del nombre del archivo de su fotografía.
  function dishLabel(item) {
    if (item.nombre_completo) return item.nombre_completo;
    if (/^De /.test(item.nombre) && item.id === 'hamburguesa-suadero') return 'Sándwich de ' + item.nombre.slice(3);
    if (/^De /.test(item.nombre) && /^hamburguesa-/.test(item.id || '')) return 'Hamburguesa de ' + item.nombre.slice(3);
    return item.nombre;
  }

  function available(item) { return item.visible !== false && item.disponible !== false; }
  function mediaUrl(value, group) {
    if (!value) return '';
    if (/^(?:\/assets\/|\/cms\/media\/[A-Za-z0-9_-]+\/file(?:[?#]|$)|https:\/\/)/.test(value)) return value;
    if (/^[A-Za-z0-9_./-]+$/.test(value) && value.split('/').indexOf('..') < 0) return '/assets/img/' + group + '/' + value;
    return '';
  }
  function applyMediaFocal(node, url, map) {
    var key = String(url || '').split(/[?#]/)[0];
    var point = map && map[key];
    if (!/^\/cms\/media\/[A-Za-z0-9_-]+\/file$/.test(key) || !point ||
        !['x', 'y'].every(function (axis) { return typeof point[axis] === 'number' && Number.isFinite(point[axis]) && point[axis] >= 0 && point[axis] <= 1; })) {
      node.style.objectPosition = '';
      return;
    }
    node.style.objectPosition = (point.x * 100) + '% ' + (point.y * 100) + '%';
  }

  function indexDishes(comida) {
    var map = {};
    (comida || []).forEach(function (sec) {
      if (sec.visible === false) return;
      (sec.items || []).filter(available).forEach(function (it) { map[it.id] = it; });
    });
    return map;
  }

  function renderTap(beer, i, perfiles, dishes) {
    var card = el('article', 'tap');
    card.id = 'barril-' + beer.id;
    if (CMS_PREVIEW) card.setAttribute('data-cms-key', (beer._cms_key || 'menu.barril.' + i) + '.nombre');

    if (beer.img) {
      var fig = el('figure', 'tap__fig');
      var img = el('img', 'tap__img');
      img.src = mediaUrl(beer.img, 'cervezas');
      applyMediaFocal(img, img.getAttribute('src'), MEDIA_FOCAL);
      if (CMS_PREVIEW) img.setAttribute('data-cms-key', (beer._cms_key || 'menu.barril.' + i) + '.img');
      img.alt = (beer.etiqueta ? 'Diseño de ' + beer.nombre + ' inspirado en su etiqueta' : 'Ilustración de ' + beer.nombre) + ' (' + beer.estilo + '), servida en el vaso de Cisne Negro';
      img.width = 900; img.height = 900; img.loading = 'lazy'; img.decoding = 'async';
      fig.appendChild(img);
      card.appendChild(fig);
    }

    var top = el('div', 'tap__top');
    top.appendChild(el('span', 'tap__num', String(i + 1).padStart(2, '0')));
    if (beer.etiqueta) {
      var etq = el('a', 'tap__etq', 'Ver etiqueta');
      etq.href = mediaUrl(beer.etiqueta, 'cervezas');
      etq.target = '_blank'; etq.rel = 'noopener';
      etq.setAttribute('aria-label', 'Ver el arte oficial de la etiqueta de ' + beer.nombre + ' (se abre en otra pestaña)');
      top.appendChild(etq);
    }
    if (beer.perfil) {
      top.appendChild(el('span', 'chip chip--' + beer.perfil, PERFIL_LABEL[beer.perfil] || beer.perfil));
    }
    card.appendChild(top);

    card.appendChild(el('h3', 'tap__name', beer.nombre));
    card.appendChild(el('p', 'tap__meta', [beer.estilo, abv(beer.abv), beer.ibu ? beer.ibu + ' IBU' : ''].filter(Boolean).join(' · ')));
    if (beer.cerveceria) card.appendChild(el('p', 'tap__guest', 'De ' + beer.cerveceria));

    if (beer.notas) card.appendChild(el('p', 'tap__notes', beer.notas));
    if (beer.perfil && perfiles && perfiles[beer.perfil]) {
      card.appendChild(el('p', 'tap__profile', 'Perfil: ' + perfiles[beer.perfil]));
    }

    var hasStory = beer.historia && beer.historia.trim();
    card.appendChild(el('p', 'tap__story' + (hasStory ? '' : ' tap__story--ask'), hasStory ? beer.historia.trim() : ASK));

    var pairs = (beer.marida_con || []).map(function (id) { return dishes[id]; }).filter(Boolean);
    if (pairs.length) {
      var p = el('p', 'tap__pairs');
      p.appendChild(document.createTextNode('Va perfecto con: '));
      p.appendChild(el('b', null, pairs.map(dishLabel).join(' · ')));
      card.appendChild(p);
    }

    if (beer.precios && beer.precios.length) {
      var ul = el('ul', 'tap__prices');
      ul.setAttribute('aria-label', 'Precios');
      beer.precios.forEach(function (pr) {
        var li = el('li');
        li.appendChild(el('span', null, pr.medida));
        li.appendChild(el('b', null, money(pr.precio)));
        ul.appendChild(li);
      });
      card.appendChild(ul);
    }
    return card;
  }

  function renderVuelo(vuelo) {
    var box = document.getElementById('vuelo');
    if (!box || !vuelo) return;
    box.querySelector('[data-vuelo-nombre]').textContent = vuelo.nombre || 'Vuelo del Cisne';
    box.querySelector('[data-vuelo-desc]').textContent = vuelo.descripcion || '';
    box.querySelector('[data-vuelo-nota]').textContent = vuelo.nota || '';
    var price = box.querySelector('[data-vuelo-precio]');
    if (vuelo.precio_desde != null) {
      price.textContent = money(vuelo.precio_desde);
    } else {
      price.parentNode.hidden = true;
    }
    box.hidden = false;
  }

  function syncPairs(barril, dishes) {
    var ids = {};
    barril.forEach(function (b) { ids[b.id] = true; });
    document.querySelectorAll('.pair[data-beer]').forEach(function (card) {
      var food = card.getAttribute('data-food');
      card.hidden = !ids[card.getAttribute('data-beer')] || !!(food && !dishes[food]);
    });
  }

  function showError(container) {
    container.innerHTML = '';
    var p = el('p', 'taps__status');
    p.appendChild(document.createTextNode('No pudimos cargar el barril en este momento. Consulta el '));
    var a = el('a', null, 'menú completo');
    a.href = '/menu/';
    p.appendChild(a);
    p.appendChild(document.createTextNode('.'));
    container.appendChild(p);
  }

  function loadBarril() {
    var container = document.getElementById('taps');
    if (!container) return;
    container.appendChild(el('p', 'taps__status', 'Cargando el barril…'));
    fetch(DATA_URL, { headers: { Accept: 'application/json' } })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (data) {
        MEDIA_FOCAL = data._media_focal || {};
        document.querySelectorAll('.hero video').forEach(function (video) {
          function positionVideo() {
            var source = video.getAttribute('src') || (window.matchMedia('(max-width: 767px)').matches ? video.dataset.mobileSrc : video.dataset.src);
            applyMediaFocal(video, source, MEDIA_FOCAL);
          }
          positionVideo();
          video.addEventListener('loadstart', positionVideo);
        });
        var barril = Array.isArray(data.barril) ? data.barril.filter(available) : [];
        var dishes = indexDishes(data.comida);
        var frag = document.createDocumentFragment();
        barril.forEach(function (b, i) { frag.appendChild(renderTap(b, i, data.perfiles, dishes)); });
        container.innerHTML = '';
        container.appendChild(frag);
        if (!barril.length) container.appendChild(el('p', 'taps__status', 'Por ahora no hay cervezas disponibles en barril. Consulta las demás opciones del menú.'));
        if (barril.filter(function (beer) { return (beer.precios || []).some(function (price) { return /^4\s*oz$/i.test(price.medida); }); }).length >= 4) renderVuelo(data.vuelo);
        syncPairs(barril, dishes);
      })
      .catch(function () { showError(container); })
      .then(function () { container.setAttribute('aria-busy', 'false'); });
  }

  function initLightbox() {
    var dlg = document.getElementById('lightbox');
    var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-gallery] button[data-full]'));
    if (!dlg || !buttons.length || typeof dlg.showModal !== 'function') return;

    var img = dlg.querySelector('img');
    var cap = dlg.querySelector('figcaption');
    var current = 0;
    var opener = null;

    function show(i) {
      current = (i + buttons.length) % buttons.length;
      var b = buttons[current];
      var thumb = b.querySelector('img');
      img.src = b.getAttribute('data-full');
      img.style.objectPosition = thumb ? thumb.style.objectPosition : '';
      img.alt = thumb ? thumb.alt : '';
      img.width = thumb ? thumb.width : 1400;
      img.height = thumb ? thumb.height : 1400;
      cap.textContent = thumb ? thumb.alt : '';
    }

    buttons.forEach(function (b, i) {
      b.setAttribute('aria-label', 'Ampliar foto: ' + (b.querySelector('img') || {}).alt);
      b.addEventListener('click', function () {
        opener = b;
        show(i);
        dlg.showModal();
      });
    });

    dlg.querySelector('[data-close]').addEventListener('click', function () { dlg.close(); });
    dlg.querySelector('[data-prev]').addEventListener('click', function () { show(current - 1); });
    dlg.querySelector('[data-next]').addEventListener('click', function () { show(current + 1); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
    dlg.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') show(current - 1);
      if (e.key === 'ArrowRight') show(current + 1);
    });
    dlg.addEventListener('close', function () { if (opener) opener.focus(); });
  }

  function init() {
    loadBarril();
    initLightbox();
    var y = document.querySelector('[data-year]');
    if (y) y.textContent = String(new Date().getFullYear());
  }

  // WhatsApp flotante: aparece al pasar el hero, para no tapar sus botones en teléfonos pequeños.
  function waFlotante() {
    var wa = document.querySelector('.wa-float');
    var hero = document.querySelector('.hero');
    if (!wa || !hero || !('IntersectionObserver' in window)) return;
    wa.classList.add('wa-float--oculto');
    new IntersectionObserver(function (entradas) {
      var visible = entradas[0].isIntersecting && entradas[0].intersectionRatio > 0.35;
      wa.classList.toggle('wa-float--oculto', visible);
      if (visible) wa.setAttribute('tabindex', '-1'); else wa.removeAttribute('tabindex');
    }, { threshold: [0, 0.35, 1] }).observe(hero);
  }

  function arrancar() { init(); waFlotante(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', arrancar);
  else arrancar();
})();
