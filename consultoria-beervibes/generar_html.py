#!/usr/bin/env python3
"""Genera la propuesta visual autónoma; conserva el plan completo en desplegables.
Uso: python3 consultoria-beervibes/generar_html.py (requiere Pandoc).
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
AST = json.loads(subprocess.check_output(['pandoc', str(ROOT / '05-consultoria-beervibes-90-dias.md'), '-t', 'json']))


def render(blocks):
    return subprocess.check_output(['pandoc', '-f', 'json', '-t', 'html5', '--wrap=none'],
        input=json.dumps({**AST, 'blocks': blocks}).encode()).decode().strip()


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('style', 'script'):
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.chunks.append(data)


def plain(markup):
    parser = Text()
    parser.feed(markup)
    return ' '.join(' '.join(parser.chunks).split())


def uri(path):
    mime = 'image/png' if path.suffix == '.png' else 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode()


def photo(filename, alt, width, height, eager=False):
    loading = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return f'<img src="{uri(ROOT / "sitio/assets/img" / filename)}" alt="{html.escape(alt)}" width="{width}" height="{height}" {loading} decoding="async">'


photos = {
    'barra': ('ig/barra-grifos.jpg', 'Pintas de cerveza y conversación junto a los grifos de Cisne Negro', 1400, 1400),
    'pizza': ('ig/noche-velas-pizza-pinta.jpg', 'Una pizza y una pinta de cerveza en la mesa', 1052, 1400),
    'brindis': ('ig/noche-velas-brindis.jpg', 'Dos personas brindan con cerveza en el taproom', 1123, 1400),
    'equipo': ('ig/noche-velas-equipo-neon.jpg', 'Equipo de Cisne Negro bajo el letrero de neón', 1400, 938),
    'taproom': ('ig/taproom-lleno-neon.jpg', 'La comunidad reunida en la barra de Cisne Negro', 1400, 1400),
    'barrilete': ('cervezas/barrilete-cosmico.jpg', 'Ilustración de la cerveza Barrilete Cósmico de Cisne Negro', 900, 900),
    'neon': ('lugar/neon.jpg', 'Letrero de neón de Cisne Negro', 1600, 1067),
}
# Todo el plan se conserva, sin duplicar su lectura en el relato principal.
groups = []
for block in AST['blocks'][1:]:
    if block['t'] == 'Header' and block['c'][0] == 2:
        groups.append({'title': plain(render([block])), 'blocks': []})
    else:
        groups[-1]['blocks'].append(block)
assert len(groups) == 11
annex = []
for n, group in enumerate(groups):
    markup = render(group['blocks'])
    # Las tablas detalladas mantienen encabezados legibles en móvil, sin un lienzo ancho.
    def stack_table(match):
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', match.group(0), re.S)
        headers = re.findall(r'<th[^>]*>(.*?)</th>', rows[0], re.S)
        body = []
        for row in rows[1:]:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
            assert len(cells) == len(headers)
            body.append('<tr>' + ''.join(f'<td data-label="{html.escape(plain(headers[i]), quote=True)}">{cell}</td>' for i, cell in enumerate(cells)) + '</tr>')
        return '<table><thead><tr>' + ''.join(f'<th scope="col">{h}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table>'
    markup = re.sub(r'<table.*?</table>', stack_table, markup, flags=re.S)
    label = re.sub(r'^\d+\.\s*', '', group['title']) if n else 'Resumen del programa'
    annex.append(f'<details id="detalle-{n}"><summary>{html.escape(label)}<span aria-hidden="true">+</span></summary><div class="detail-body">{markup}</div></details>')

values = {
    'FONTS': (ROOT / 'propuesta-economica/fuentes.css').read_text(),
    'CSS': (HERE / 'estilo.css').read_text(),
    'FAVICON': uri(ROOT / 'sitio/assets/img/marca/favicon-192.png'),
    'PLUMA': uri(ROOT / 'sitio/assets/img/marca/pluma.png'),
    'MASCOTA': photo('marca/cisne-mascota.jpg', 'El cisne de la cervecería', 1080, 1080),
    'ANNEX': '\n'.join(annex),
}
for key, asset in photos.items():
    values['PHOTO_' + key.upper()] = photo(*asset, eager=(key == 'barra'))
document = (HERE / 'plantilla.html').read_text()
for key, value in values.items():
    document = document.replace('@@' + key + '@@', value)
assert '@@' not in document, 'Marcador de plantilla pendiente.'
source_markup = render(AST['blocks'])
fragments = re.findall(r'<(?:p|td|th|li)(?:\s[^>]*)?>(.*?)</(?:p|td|th|li)>', source_markup, re.S)
visible = plain(document)
assert all(plain(fragment) in visible for fragment in fragments), 'Falta contenido del plan completo.'
ids = re.findall(r'\bid="([^"]+)"', document)
assert len(ids) == len(set(ids)), 'ID duplicado.'
assert all(anchor in ids for anchor in re.findall(r'href="#([^"]+)"', document)), 'Ancla sin destino.'
assert len(re.findall(r'class="journey-step"', document)) == 5
assert len(re.findall(r'class="story-card"', document)) == 6
assert len(re.findall(r'class="timeline-step"', document)) == 4
assert not re.search(r'(?:src="https?://|url\([\'"]?https?://|rel="stylesheet"[^>]*https?://)', document), 'Dependencia remota.'
assert all(re.search(r'\balt="[^"]+"', tag) for tag in re.findall(r'<img\b[^>]+>', document)), 'Imagen sin alternativa.'
main_story = document.split('<!-- PLAN COMPLETO -->')[0]
print(f'Relato principal: {len(plain(main_story).split())} palabras; {document.count("<img ")} imágenes; {len(fragments)} fragmentos conservados en el detalle.')
(HERE / 'index.html').write_text(document)
site = ROOT / 'sitio/propuesta/beervibes/index.html'
site.parent.mkdir(parents=True, exist_ok=True)
site_document = document.replace('href="../propuesta-economica/index.html"', 'href="../"', 1)
# La versión del sitio reutiliza y permite cachear las fotos ya presentes en assets.
# La versión local conserva imágenes incrustadas para abrirla sin conexión.
asset_names = [asset[0] for asset in photos.values()] + ['marca/cisne-mascota.jpg', 'marca/pluma.png', 'marca/favicon-192.png']
for filename in asset_names:
    path = ROOT / 'sitio/assets/img' / filename
    assert path.is_file()
    site_document = site_document.replace(uri(path), '/assets/img/' + filename)
site.write_text(site_document)
print(f'HTML autónomo: {len(document.encode()):,} bytes; HTML para el sitio: {len(site_document.encode()):,} bytes. 5 pasos, 6 historias, 4 etapas; anclas y contenido verificados.')
