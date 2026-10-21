#!/usr/bin/env python3
"""Genera una propuesta HTML autónoma a partir del Markdown aprobado.

Requiere pandoc. Imágenes, fuentes y PDF se incrustan para compartir un solo HTML.
Uso: python3 propuesta-economica/generar_html.py
"""
import base64
import html
import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = HERE / 'propuesta-economica.md'
AST = json.loads(subprocess.check_output(['pandoc', str(SOURCE), '-t', 'json']))


def render(blocks):
    document = {**AST, 'blocks': blocks}
    return subprocess.check_output(
        ['pandoc', '-f', 'json', '-t', 'html5', '--wrap=none'],
        input=json.dumps(document).encode(),
    ).decode().strip()


def inline_text(nodes):
    result = []
    for item in nodes:
        kind, value = item['t'], item.get('c')
        if kind == 'Str': result.append(value)
        elif kind in ('Space', 'SoftBreak', 'LineBreak'): result.append(' ')
        elif kind in ('Strong', 'Emph', 'SmallCaps'): result.append(inline_text(value))
    return ''.join(result)


def data_uri(path, mime):
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()


def photo(path, alt, width, height, lazy=True):
    uri = data_uri(ROOT / 'sitio/assets/img' / path, 'image/jpeg')
    return f'<img src="{uri}" alt="{html.escape(alt)}" width="{width}" height="{height}" decoding="async" {"loading=lazy" if lazy else "fetchpriority=high"}>'


def heading(number, title):
    return f'<div class="section-head"><span class="section-no" aria-hidden="true">{number:02d}</span><h2>{html.escape(title)}</h2></div>'


intro = []
sections = []
for block in AST['blocks'][1:]:
    if block['t'] == 'Header' and block['c'][0] == 2:
        sections.append({'title': inline_text(block['c'][2]), 'blocks': []})
    elif sections:
        sections[-1]['blocks'].append(block)
    else:
        intro.append(block)
assert len(intro) == 4 and len(sections) == 7, 'Revisar estructura del Markdown antes de maquetar.'

delivery = []
for block in sections[1]['blocks']:
    if block['t'] == 'Header' and block['c'][0] == 3:
        delivery.append({'title': inline_text(block['c'][2]), 'blocks': []})
    else:
        delivery[-1]['blocks'].append(block)

scope_html = []
for index, item in enumerate(delivery, 1):
    image = ''
    extra = ''
    classname = 'deliverable'
    if index == 2:
        image = '<figure class="deliverable__photo">' + photo('ig/barra-grifos.jpg', 'Pintas, grifos y amigos en la barra de Cisne Negro', 1400, 1400) + '<figcaption>La cerveza, al centro.</figcaption></figure>'
    elif index == 3:
        image = '<figure class="deliverable__photo">' + photo('ig/noche-velas-brindis.jpg', 'Una pareja brinda con cerveza durante una noche de velas en Cisne Negro', 1123, 1400) + '<figcaption>Experiencias que invitan a volver.</figcaption></figure>'
    elif index == 4:
        classname += ' deliverable--cms'
        extra = '<p class="cms-note">El contenido en manos de su equipo.</p><div class="cms-stamp"><span>3 cuentas</span><span>2 roles</span></div>'
    scope_html.append(f'<article class="{classname}"><div class="deliverable__label"><span class="deliverable__number">ENTREGABLE {index:02d}</span><h3>{html.escape(item["title"])}</h3>{extra}{image}</div><div class="deliverable__body">{render(item["blocks"])}</div></article>')

monthly = sections[2]['blocks']
assert [b['t'] for b in monthly] == ['Para', 'Table', 'Para', 'Para', 'Para']
calendar = sections[3]['blocks']
assert [b['t'] for b in calendar] == ['Para', 'Table', 'Table', 'Para']

# Las filas del calendario se presentan como pasos; su texto no cambia.
table_markup = render([calendar[1]])
row_markup = re.findall(r'<tr[^>]*>(.*?)</tr>', table_markup, flags=re.S)[1:]
steps = []
for row in row_markup:
    cells = re.findall(r'<td[^>]*>(.*?)</td>', row, flags=re.S)
    assert len(cells) == 2
    steps.append(f'<li class="timeline-step"><h3>{cells[0]}</h3><p>{cells[1]}</p></li>')

conditions = render(sections[4]['blocks']).replace('<ul>', '<ul class="conditions-list">', 1)
exclusions = sections[5]['blocks']
roi_blocks = sections[6]['blocks']
assert [b['t'] for b in roi_blocks] == ['Para', 'Para', 'Table', 'Para', 'Table', 'Para', 'Table', 'Para']
story_html = '''<div class="story">
  <p class="eyebrow">La transformación, en orden</p>
  <ol class="story-rail">
    <li class="story-beat">
      <div class="story-mark" aria-hidden="true">01</div>
      <div class="story-body">
        <h3>Hoy</h3>
        <p class="story-kicker">6 de octubre de 2026. La casa ya tiene reputación. Lo que todavía no existe es una lista de quién vuelve.</p>
        <div class="meter" role="meter" aria-valuenow="37" aria-valuemin="0" aria-valuemax="100" aria-label="Presencia digital, 37 de 100"><span class="meter-fill" style="--w:37%"></span></div>
        <p class="meter-num"><b>37</b> / 100 presencia digital</p>
        <ul class="lanes" aria-label="Puntaje por canal en el análisis del 6 de octubre de 2026">
          <li><span>Sitio web</span><span class="track"><i style="--w:60%"></i></span><b>60</b></li>
          <li><span>Instagram</span><span class="track"><i style="--w:60%"></i></span><b>60</b></li>
          <li><span>Google</span><span class="track"><i style="--w:50%"></i></span><b>50</b></li>
          <li><span>TikTok</span><span class="track"><i style="--w:30%"></i></span><b>30</b></li>
          <li><span>Facebook</span><span class="track"><i style="--w:10%"></i></span><b>10</b></li>
          <li><span>Tripadvisor / Untappd</span><span class="track"><i style="--w:10%"></i></span><b>10</b></li>
        </ul>
        <p class="story-note">Misma rúbrica del análisis: presencia, exactitud, actividad, tracción y conversión, 20 puntos cada una. Google: 4.5 estrellas, 69 reseñas, 0 respuestas. Instagram: 3,513 seguidores. Socios en producción: 0.</p>
        <ul class="spend" aria-label="Rangos de gasto declarados en 30 reseñas de Google">
          <li><span>$100–200</span><span class="track"><i style="--w:17%"></i></span><b>3</b></li>
          <li class="is-mode"><span>$200–300</span><span class="track"><i style="--w:100%"></i></span><b>18</b></li>
          <li><span>$300–400</span><span class="track"><i style="--w:11%"></i></span><b>2</b></li>
          <li><span>$400–500</span><span class="track"><i style="--w:22%"></i></span><b>4</b></li>
          <li><span>$500–600</span><span class="track"><i style="--w:17%"></i></span><b>3</b></li>
        </ul>
        <p class="story-note">30 reseñas declararon un rango. 18 caen entre $200 y $300. $250 es el punto medio de esa banda y el gasto con el que abre la calculadora. El ticket de caja lo confirma la cervecería.</p>
      </div>
    </li>
    <li class="story-beat">
      <div class="story-mark" aria-hidden="true">02</div>
      <div class="story-body">
        <h3>Cuatro semanas</h3>
        <p class="story-kicker">Desde el anticipo, los accesos y los contenidos. Cada semana deja encendida una parte de la plataforma.</p>
        <ol class="arc" aria-label="Calendario de implementación">
          <li><b>1</b><strong>Semana 1</strong><span>Catálogo, reglas del Pasaporte, contenido, diseño y campos del CMS.</span></li>
          <li><b>2</b><strong>Semana 2</strong><span>CMS integrado. Revisión de la página y del menú.</span></li>
          <li><b>3</b><strong>Semana 3</strong><span>Permisos, publicación, registro, visitas, canjes, respaldos y piloto con el personal.</span></li>
          <li><b>4</b><strong>Semana 4</strong><span>Ajustes, capacitación y lanzamiento en el dominio acordado.</span></li>
        </ol>
      </div>
    </li>
    <li class="story-beat">
      <div class="story-mark" aria-hidden="true">03</div>
      <div class="story-body">
        <h3>El día que abre</h3>
        <p class="story-kicker">Lo que el equipo puede hacer cuando la plataforma entra en operación, en una sucursal y en español.</p>
        <div class="shift"><div class="shift-from"><small>Hoy</small><p>La página pública se cambia con desarrollo.</p></div><div class="shift-arrow" aria-hidden="true">→</div><div class="shift-to"><small>En operación</small><p>El editor guarda un borrador y publica textos, precios, fotos, galería y eventos.</p></div></div>
        <div class="shift"><div class="shift-from"><small>Hoy</small><p>El menú todavía no vive en un QR del dominio final.</p></div><div class="shift-arrow" aria-hidden="true">→</div><div class="shift-to"><small>En operación</small><p>QR en PNG y SVG, hasta 60 productos, disponibilidad, vuelo y maridajes aprobados.</p></div></div>
        <div class="shift"><div class="shift-from"><small>Hoy</small><p>Socios en producción: 0. Cada visita sigue siendo anónima.</p></div><div class="shift-arrow" aria-hidden="true">→</div><div class="shift-to"><small>En operación</small><p>Registro, sello con el código del día, una visita diaria, canje y exportación CSV.</p></div></div>
        <div class="shift"><div class="shift-from"><small>Hoy</small><p>La satisfacción de la visita no tiene serie propia.</p></div><div class="shift-arrow" aria-hidden="true">→</div><div class="shift-to"><small>En operación</small><p>Encuesta, comentarios y un resumen mensual de socios, visitas, canjes y satisfacción.</p></div></div>
        <p class="story-note">Un socio recorre ciclos de 10 visitas. La cortesía incluida es de 4 oz en la visita 5 y de 12 oz en la visita 10. Son 16 oz por ciclo, a cargo de la cervecería.</p>
        <ol class="stamps" aria-label="Ciclo de diez visitas con cortesía en la quinta y la décima">
          <li>1</li><li>2</li><li>3</li><li>4</li><li class="is-gift">5<small>4 oz</small></li><li>6</li><li>7</li><li>8</li><li>9</li><li class="is-gift">10<small>12 oz</small></li>
        </ol>
      </div>
    </li>
    <li class="story-beat">
      <div class="story-mark" aria-hidden="true">04</div>
      <div class="story-body">
        <h3>A los 90 días</h3>
        <p class="story-kicker">El panel ya tiene una serie. Estas lecturas dicen si la mecánica se está usando. El juicio de dinero espera el margen real.</p>
        <div class="reads">
          <article><h4>Socios sellados</h4><p>Si la cuenta sigue en cero, el código del día no se está usando en barra.</p></article>
          <article><h4>Recurrencia</h4><p>Socios con 2 o más visitas, dividido entre los socios.</p></article>
          <article><h4>Satisfacción</h4><p>La primera quincena de operación fija la línea base de NPS y comentarios.</p></article>
          <article><h4>Onzas</h4><p>16 oz por cada ciclo de 10 visitas completado.</p></article>
          <article><h4>Menú del editor</h4><p>Publicado dentro de 2 días hábiles, dentro de las 3 horas del mes.</p></article>
          <article><h4>Respaldo</h4><p>La prueba mensual de recuperación responde sí o no.</p></article>
        </div>
      </div>
    </li>
  </ol>
</div>
<p class="eyebrow story-next">Umbral de cobertura</p>'''
nav_items = [('inversion', 'Inversión'), ('entregables', 'Entregables'), ('administracion', 'Administración'), ('calendario', 'Calendario'), ('retorno', 'Retorno'), ('condiciones', 'Condiciones'), ('alcance', 'Fuera del paquete')]
nav = ''.join(f'<a href="#{key}"><span aria-hidden="true">{n:02d}</span>{label}</a>' for n, (key, label) in enumerate(nav_items, 1))
pdf = data_uri(HERE / 'propuesta-economica-cisne-negro.pdf', 'application/pdf')
download = f'<a class="button" href="{pdf}" download="Propuesta-Cisne-Negro.pdf">Descargar PDF <span aria-hidden="true">↓</span></a>'
pluma = data_uri(ROOT / 'sitio/assets/img/marca/pluma.png', 'image/png')
favicon = data_uri(ROOT / 'sitio/assets/img/marca/favicon-192.png', 'image/png')
neon = photo('lugar/neon.jpg', 'Letrero de neón Cisne Negro en la cervecería de Pachuca', 1600, 1067, False)
mascot = photo('marca/cisne-mascota.jpg', 'Mascota de Cisne Negro con un tarro de cerveza', 1080, 1080, False)
fonts = (HERE / 'fuentes.css').read_text()
styles = (HERE / 'estilo.css').read_text()
document = f'''<!doctype html>
<html lang="es-MX">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <meta name="theme-color" content="#0e0d0b">
  <meta name="description" content="Propuesta económica de Softvibes para Cervecería Cisne Negro: página web, menú digital, Pasaporte Cisne, CMS y administración.">
  <title>Propuesta económica · Cervecería Cisne Negro × Softvibes</title>
  <link rel="icon" type="image/png" href="{favicon}">
  <style>{fonts}\n:root{{--pluma:url('{pluma}');}}\n{styles}</style>
</head>
<body>
<a class="skip" href="#contenido">Saltar a la propuesta</a>
<header class="masthead" id="portada"><div class="wrap">
  <a class="wordmark" href="#portada" aria-label="Cervecería Cisne Negro, inicio de la propuesta">CISNE NEGRO</a>
  <div class="masthead__right"><span class="byline">Una propuesta de <strong>Softvibes</strong></span>{download}</div>
</div></header>
<nav class="proposal-nav" aria-label="Propuestas para Cisne Negro"><div class="wrap">
  <a href="#portada" aria-current="page"><strong>Plataforma digital</strong><span>Web, menú, Pasaporte y CMS</span></a>
  <a href="../consultoria-beervibes/index.html"><strong>Consultoría Beervibes</strong><span>Plan comercial de 90 días</span></a>
</div></nav>
<main id="contenido">
  <section class="cover wrap" aria-labelledby="titulo">
    <div class="cover__grid"><div>
      <p class="eyebrow">Cervecería independiente · Pachuca</p>
      <h1 id="titulo">Propuesta <span>económica</span></h1>
      <div class="cover__client">{render([intro[0]])}</div>
    </div><figure class="cover__photo">{neon}<figcaption>Cerveza hecha aquí.<br>Historias de barra.</figcaption><div class="sticker">{mascot}</div></figure></div>
    <div class="cover__meta mono"><span>CN-2026-01 · WEB / MENÚ / PASAPORTE / CMS</span><span>Preparada para los dueños de Cisne Negro</span></div>
  </section>
  <nav class="section-nav" aria-label="Secciones de la propuesta"><div class="wrap">{nav}</div></nav>
  <div class="intro wrap"><div class="intro__lead">{render([intro[1]])}</div><div class="intro__support">{render([intro[3]])}</div></div>
  <div class="price-overview wrap">{render([intro[2]])}</div>
  <section class="section paper" id="inversion"><div class="wrap">
    {heading(1, 'Inversión de implementación')}
    <div class="investment-grid"><div class="investment-aside"><p class="tag">Un solo paquete</p><div class="investment-amount">$32,000<small>MXN</small></div><p>Implementación inicial.<br>Importe antes de los impuestos aplicables.</p></div><div class="investment-table">{render([sections[0]['blocks'][0]])}</div></div>
    <div class="investment-note">{render(sections[0]['blocks'][1:])}</div>
  </div></section>
  <section class="section deliverables wrap" id="entregables">
    {heading(2, 'Qué se entrega')}
    {''.join(scope_html)}
  </section>
  <section class="section monthly" id="administracion"><div class="wrap">
    {heading(3, 'Administración y mantenimiento mensual')}
    <div class="monthly-top"><div class="monthly-price">$2,900<span>MXN AL MES · ANTES DE IMPUESTOS</span></div>{render([monthly[0]])}</div>
    {render([monthly[1]])}<div class="monthly-notes">{render(monthly[2:])}</div>
  </div></section>
  <section class="section paper" id="calendario"><div class="wrap">
    {heading(4, 'Calendario y forma de pago')}
    <div class="calendar-intro">{render([calendar[0]])}</div>
    <p class="eyebrow" style="margin-top:32px">Etapa · Entrega</p>
    <ol class="timeline" aria-label="Calendario de cuatro semanas">{''.join(steps)}</ol>
    <div class="payments">{render([calendar[2]])}</div>
    <div class="year-total">{render([calendar[3]])}</div>
  </div></section>
  <section class="section paper" id="retorno"><div class="wrap">
    {heading(5, 'Retorno medible')}
    <div class="roi-lead">{render(roi_blocks[:2])}</div>
    {story_html}
    <div class="roi-controls" role="group" aria-label="Gasto supuesto por visita">
      <button type="button" data-ticket="200">Gasto $200</button>
      <button type="button" data-ticket="250" aria-pressed="true">Gasto $250</button>
      <button type="button" data-ticket="400">Gasto $400</button>
    </div>
    <div class="roi-controls" role="group" aria-label="Margen de contribución supuesto">
      <button type="button" data-margin="30">Margen 30%</button>
      <button type="button" data-margin="50" aria-pressed="true">Margen 50%</button>
      <button type="button" data-margin="70">Margen 70%</button>
    </div>
    <div class="roi-figures">
      <div><b id="roi-year">535</b><span>visitas para igualar el año 1</span></div>
      <div><b id="roi-month">24</b><span>visitas al mes para la cuota</span></div>
      <div><b id="roi-contrib">$125</b><span>aporte supuesto por visita</span></div>
    </div>
    <p class="roi-live" id="roi-live">Con gasto de $250 y margen de 50%, la obra sola equivaldría a 256 visitas de ese aporte.</p>
    <div class="roi-tables">{render(roi_blocks[2:])}</div>
  </div></section>
  <section class="section conditions wrap" id="condiciones">
    {heading(6, 'Condiciones de alcance')}{conditions}
  </section>
  <section class="section exclusions wrap" id="alcance">
    {heading(7, 'Servicios fuera del paquete')}<div class="exclusions-body">{render(exclusions[:-1])}</div>
    <div class="closing">{render([exclusions[-1]])}</div>
  </section>
  <aside class="endnote"><div class="wrap"><div><p class="display">¡Cuéntalo en el Cisne!</p><p>Cervecería Cisne Negro · Pachuca, Hidalgo</p></div><div class="endnote__actions">{download}<button class="button button--line" id="imprimir" type="button" hidden>Imprimir propuesta</button></div></div></aside>
</main>
<footer class="footer"><div class="wrap"><span>SOFTVIBES × CISNE NEGRO · PROPUESTA CN-2026-01</span><a href="#portada">Volver al inicio ↑</a></div></footer>
<script>
(function () {{
  var printButton = document.getElementById('imprimir');
  printButton.hidden = false;
  printButton.addEventListener('click', function () {{ window.print(); }});
  var ticket = 250;
  var margin = 50;
  function roiCeil(cost) {{ return Math.ceil(cost / (ticket * margin / 100)); }}
  function roiMoney(value) {{ return value.toLocaleString('es-MX'); }}
  function paintRoi() {{
    var contrib = Math.round(ticket * margin / 100);
    document.getElementById('roi-year').textContent = roiMoney(roiCeil(66800));
    document.getElementById('roi-month').textContent = roiMoney(roiCeil(2900));
    document.getElementById('roi-contrib').textContent = '$' + roiMoney(contrib);
    document.getElementById('roi-live').textContent = 'Con gasto de $' + ticket + ' y margen de ' + margin + '%, la obra sola equivaldría a ' + roiMoney(roiCeil(32000)) + ' visitas de ese aporte.';
    document.querySelectorAll('[data-ticket]').forEach(function (button) {{
      button.setAttribute('aria-pressed', button.getAttribute('data-ticket') === String(ticket) ? 'true' : 'false');
    }});
    document.querySelectorAll('[data-margin]').forEach(function (button) {{
      button.setAttribute('aria-pressed', button.getAttribute('data-margin') === String(margin) ? 'true' : 'false');
    }});
  }}
  document.querySelectorAll('[data-ticket]').forEach(function (button) {{
    button.addEventListener('click', function () {{ ticket = Number(button.getAttribute('data-ticket')); paintRoi(); }});
  }});
  document.querySelectorAll('[data-margin]').forEach(function (button) {{
    button.addEventListener('click', function () {{ margin = Number(button.getAttribute('data-margin')); paintRoi(); }});
  }});
  paintRoi();
  var beats = Array.prototype.slice.call(document.querySelectorAll('.story-beat'));
  var story = document.querySelector('.story');
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (story && beats.length && ('IntersectionObserver' in window) && !reduceMotion) {{
    story.classList.add('story-live');
    var beatObserver = new IntersectionObserver(function (entries) {{
      entries.forEach(function (entry) {{
        if (entry.isIntersecting) entry.target.classList.add('is-on');
      }});
    }}, {{ threshold: 0.22, rootMargin: '0px 0px -6% 0px' }});
    beats.forEach(function (beat) {{ beatObserver.observe(beat); }});
  }}
  if (!('IntersectionObserver' in window)) return;
  var links = Array.from(document.querySelectorAll('.section-nav a'));
  var observer = new IntersectionObserver(function (entries) {{
    entries.forEach(function (entry) {{
      if (!entry.isIntersecting) return;
      links.forEach(function (link) {{
        if (link.getAttribute('href') === '#' + entry.target.id) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      }});
    }});
  }}, {{ rootMargin: '-10% 0px -65% 0px', threshold: 0 }});
  links.forEach(function (link) {{ observer.observe(document.querySelector(link.getAttribute('href'))); }});
}})();
</script>
</body>
</html>'''


class VisibleText(HTMLParser):
    def __init__(self): super().__init__(); self.chunks = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script'): self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ('style', 'script'): self.hidden -= 1
    def handle_data(self, text):
        if not self.hidden: self.chunks.append(text)


def normalized_markup(markup):
    parser = VisibleText(); parser.feed(markup)
    return ' '.join(' '.join(parser.chunks).split())


# Verificación de fidelidad: cada párrafo, condición y celda aprobada sigue presente.
plain = normalized_markup(document)
source_markup = render(AST['blocks'])
fragments = re.findall(r'<(?:p|td|th|li)(?:\s[^>]*)?>(.*?)</(?:p|td|th|li)>', source_markup, re.S)
missing = [normalized_markup(piece) for piece in fragments if normalized_markup(piece) not in plain]
assert not missing, 'Contenido aprobado ausente: ' + repr(missing)
assert len(steps) == 4 and len(delivery) == 5
assert not re.search(r'(?:src|href)="https?://|url\(https?://', document), 'Dependencia remota inesperada.'
output = HERE / 'index.html'
output.write_text(document)
print(f'{output}: {output.stat().st_size:,} bytes; {len(fragments)} fragmentos aprobados verificados; 0 dependencias remotas.')
site_output = ROOT / 'sitio/propuesta/index.html'
site_output.parent.mkdir(parents=True, exist_ok=True)
site_output.write_text(document.replace('href="../consultoria-beervibes/index.html"', 'href="beervibes/"', 1))
print(f'Copia lista para publicar: {site_output}')
