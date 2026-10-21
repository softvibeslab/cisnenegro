/* Only identifiers are curated here. All beer facts come from the existing menu.json. */
(() => {
  'use strict';
  const ids = ['alarma', 'agua-puerca'];
  const dataBox = document.querySelector('#beer-data');
  const status = document.querySelector('#load-status');
  const choices = document.querySelector('#choices');
  const fieldset = document.querySelector('#beer-choice');
  const detail = document.querySelector('#beer-detail');
  const retry = document.querySelector('#retry');
  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    element.className = className;
    element.textContent = text;
    return element;
  };
  const money = new Intl.NumberFormat('es-MX', {style:'currency', currency:'MXN', maximumFractionDigits:0});
  function selectBeer(beer) {
    const content = document.createDocumentFragment();
    content.append(node('p', 'beer-meta', `${beer.estilo} · ${beer.abv.toFixed(1)}% ABV`));
    content.append(node('h3', 'beer-name', beer.nombre));
    content.append(node('p', 'beer-notes', beer.notas));
    const prices = node('ul', 'prices', '');
    prices.setAttribute('aria-label', 'Precios en pesos mexicanos');
    beer.precios.forEach(price => {
      const item = node('li', '', price.medida);
      item.append(node('b', '', money.format(price.precio) + ' MXN'));
      prices.append(item);
    });
    content.append(prices);
    detail.replaceChildren(content);
    document.querySelector('#barra').dataset.beer = beer.id;
    document.querySelectorAll('[data-art]').forEach(art => { art.hidden = art.dataset.art !== beer.id; });
    document.querySelector('#art-caption').textContent = `${beer.nombre} · Ilustración de la cerveza${beer.id === 'alarma' ? ' y su etiqueta' : ''}.`;
  }
  async function load() {
    dataBox.setAttribute('aria-busy', 'true');
    status.hidden = false;
    status.textContent = 'Cargando la selección de la carta…';
    retry.hidden = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch('../data/menu.json', {signal:controller.signal, headers:{Accept:'application/json'}});
      if (!response.ok) throw new Error('No se pudo leer la carta');
      const data = await response.json();
      const beers = ids.map(id => data.barril?.find(beer => beer.id === id));
      if (beers.some(beer => !beer || typeof beer.nombre !== 'string' || typeof beer.estilo !== 'string' || typeof beer.notas !== 'string' || !Number.isFinite(beer.abv) || !Array.isArray(beer.precios) || !beer.precios.length || beer.precios.some(price => typeof price.medida !== 'string' || !Number.isFinite(price.precio)))) throw new Error('Selección incompleta');
      const fragment = document.createDocumentFragment();
      beers.forEach((beer, index) => {
        const label = node('label', 'choice', '');
        const input = document.createElement('input');
        input.type = 'radio'; input.name = 'cerveza'; input.value = beer.id;
        input.checked = index === 0;
        input.setAttribute('aria-controls', 'beer-detail beer-art');
        input.addEventListener('change', () => { if (input.checked) selectBeer(beer); });
        label.append(input, document.createTextNode(beer.nombre));
        fragment.append(label);
      });
      choices.replaceChildren(fragment);
      fieldset.hidden = false;
      selectBeer(beers[0]);
      status.hidden = true;
    } catch (_) {
      fieldset.hidden = true;
      detail.replaceChildren();
      status.textContent = 'No pudimos cargar las cervezas. Vuelve a intentar o abre la carta completa.';
      retry.hidden = false;
    } finally {
      clearTimeout(timeout);
      dataBox.setAttribute('aria-busy', 'false');
    }
  }
  retry.addEventListener('click', load);
  load();

  // Native scroll; only visible decorative planes move. No perpetual render loop.
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const coarse = matchMedia('(pointer: coarse)');
  const layers = [...document.querySelectorAll('[data-parallax]')];
  const visible = new Set();
  let frame = 0;
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => entry.isIntersecting ? visible.add(entry.target) : visible.delete(entry.target));
    schedule();
  });
  layers.forEach(layer => observer.observe(layer));
  function paint() {
    frame = 0;
    if (reduced.matches || coarse.matches) return;
    visible.forEach(layer => {
      const scene = layer.closest('.scene');
      const offset = Math.max(-600, Math.min(600, -scene.getBoundingClientRect().top));
      layer.style.setProperty('--shift', `${offset * Number(layer.dataset.parallax)}px`);
    });
  }
  function schedule() {
    if (!reduced.matches && !coarse.matches && !frame) frame = requestAnimationFrame(paint);
  }
  function configure() {
    cancelAnimationFrame(frame); frame = 0;
    window.removeEventListener('scroll', schedule);
    layers.forEach(layer => layer.style.removeProperty('--shift'));
    document.documentElement.dataset.motion = reduced.matches || coarse.matches ? 'off' : 'subtle';
    if (!reduced.matches && !coarse.matches) {
      window.addEventListener('scroll', schedule, {passive:true});
      schedule();
    }
  }
  reduced.addEventListener('change', configure);
  coarse.addEventListener('change', configure);
  window.addEventListener('resize', schedule, {passive:true});
  configure();
})();
