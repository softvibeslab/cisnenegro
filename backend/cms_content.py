"""Contenido editorial de Cisne Negro. No consulta ni modifica datos del Pasaporte.

La base del CMS guarda el documento completo. render_document produce una versión
pública derivada y no escribe archivos: su activación corresponde al publicador.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote, urlencode, urlsplit

from bs4 import BeautifulSoup, Tag


HERO_KEYS = ('hero_mode', 'hero_image', 'hero_video_desktop', 'hero_video_mobile', 'hero_poster')
PROFILE_NAMES = ('lupulada', 'oscura', 'acida', 'ligera')
ID_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$')
DAY_NAMES = ('lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo')
DAY_SCHEMA = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
FULL_NAMES = {
    'hamburguesa-suadero': 'Sándwich de Suadero',
    'hamburguesa-res': 'Hamburguesa de Res',
    'hamburguesa-costilla': 'Hamburguesa de Costilla de Res',
    'hamburguesa-manchego': 'Hamburguesa de Manchego Frito',
}

# selector, atributo (None = texto), tipo, sección, etiqueta
PAGE_BINDINGS = {
    'hero_kicker': ('.hero__kicker', None, 'text', 'Portada', 'Ubicación breve'),
    'hero_title': ('.hero__title', None, 'text', 'Portada', 'Título'),
    'hero_desc': ('.hero__desc', None, 'text', 'Portada', 'Descriptor'),
    'hero_lead': ('.hero__lead', None, 'textarea', 'Portada', 'Introducción'),
    'hero_image': ('.hero > img.hero__bg', 'src', 'image', 'Portada', 'Fotografía'),
    'hero_image_alt': ('.hero > img.hero__bg', 'alt', 'text', 'Portada', 'Texto alternativo de portada'),
    'hero_sticker_image': ('.hero__sticker img', 'src', 'image', 'Portada', 'Mascota'),
    'hero_sticker_alt': ('.hero__sticker img', 'alt', 'text', 'Portada', 'Texto alternativo de mascota'),
    'historia_image': ('.story__photo img', 'src', 'image', 'Historia', 'Fotografía de historia'),
    'historia_image_alt': ('.story__photo img', 'alt', 'text', 'Historia', 'Texto alternativo'),
    'historia_caption': ('.story__photo figcaption', None, 'text', 'Historia', 'Pie de foto'),
    'seo_title': ('title', None, 'text', 'Buscadores', 'Título de la página'),
    'seo_description': ('meta[name="description"]', 'content', 'textarea', 'Buscadores', 'Descripción'),
    'social_title': ('meta[property="og:title"]', 'content', 'text', 'Buscadores', 'Título al compartir'),
    'social_description': ('meta[property="og:description"]', 'content', 'textarea', 'Buscadores', 'Descripción al compartir'),
    'social_image': ('meta[property="og:image"]', 'content', 'image', 'Buscadores', 'Imagen al compartir'),
    'social_image_alt': ('meta[property="og:image:alt"]', 'content', 'text', 'Buscadores', 'Texto alternativo social'),
    'footer_tagline': ('.footer__tag', None, 'text', 'Pie de página', 'Frase del pie'),
}


def _text(node):
    return node.get_text(' ', strip=True) if node else ''


def _slug(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')[:70] or 'elemento'


def _identity(prefix, value):
    return prefix + '-' + hashlib.sha256(value.encode()).hexdigest()[:12]


def _soup(site_root, filename='index.html'):
    return BeautifulSoup((Path(site_root) / filename).read_text(encoding='utf-8'), 'html.parser')


def _bindings(soup):
    """Rutas estables de campos; la plantilla es código confiable, nunca HTML del CMS."""
    out = []
    seen = set()
    for key, (selector, attr, kind, section, label) in PAGE_BINDINGS.items():
        node = soup.select_one(selector)
        if node:
            out.append((key, node, attr, kind, section, label))
            if attr is None:
                seen.add(id(node))
    containers = [('hero', soup.select_one('.hero'), 'Portada')]
    containers += [(n.get('id'), n, n.get('id', '').capitalize()) for n in soup.select('main > section[id]')]
    counters = {}
    for prefix, container, section in containers:
        if not container:
            continue
        for node in container.select('h2,h3,p,li,cite'):
            if id(node) in seen or node.find_parent(class_=['events', 'gallery', 'pairs']) or node.find_parent('noscript'):
                continue
            if node.select_one('h2,h3,p,li') or node.get('data-vuelo-nombre') is not None:
                continue
            if node.has_attr('data-vuelo-desc') or node.has_attr('data-vuelo-nota') or node.select_one('[data-vuelo-precio]'):
                continue
            if not _text(node):
                continue
            counters[(prefix, node.name)] = counters.get((prefix, node.name), 0) + 1
            key = f'{prefix}_{node.name}_{counters[(prefix, node.name)]}'
            out.append((key, node, None, 'textarea' if node.name == 'p' else 'text', section,
                        _text(node)[:65]))
            seen.add(id(node))
    return out


def initial_document(site_root: Path) -> dict:
    site_root = Path(site_root)
    menu = json.loads((site_root / 'data/menu.json').read_text(encoding='utf-8'))
    used = {it['id'] for it in menu['barril']}
    used.update(it['id'] for section in menu['comida'] for it in section['items'])
    for group in ('barril', 'latas', 'sin_alcohol'):
        for index, item in enumerate(menu[group]):
            if not item.get('id'):
                identity = f'{group}-{_slug(item["nombre"])}'
                if identity in used:
                    identity += f'-{index+1}'
                item['id'] = identity
            used.add(item['id'])
            item.setdefault('visible', True)
            item.setdefault('disponible', True)
    for section in menu['comida']:
        section.setdefault('id', 'categoria-' + _slug(section['seccion']))
        section.setdefault('visible', True)
        for item in section['items']:
            item.setdefault('visible', True)
            item.setdefault('disponible', True)
            item.setdefault('nombre_completo', FULL_NAMES.get(item['id'], item['nombre']))
    soup = _soup(site_root)
    page = {key: str(node.get(attr, '')) if attr else _text(node)
            for key, node, attr, *_ in _bindings(soup)}
    video = soup.select_one('.hero video')
    page.update(hero_mode='video' if video else 'image',
                hero_video_desktop=video.get('data-src', '') if video else '/assets/video/cisne-negro-hero-v2.mp4',
                hero_video_mobile=video.get('data-mobile-src', '') if video else '/assets/video/cisne-negro-hero-v2-720.mp4',
                hero_poster=page['hero_image'])
    linked = soup.select_one('script[type="application/ld+json"]')
    schema = json.loads(linked.string) if linked else {}
    page['schema_description'] = schema.get('description', page.get('seo_description', ''))
    food = [it for section in menu['comida'] for it in section['items']]
    for i, card in enumerate(soup.select('.pairs .pair')):
        photo = card.select_one('img:not(.pair__vaso)')
        photo_path = urlsplit((photo or {}).get('src', '')).path
        dish = next((it for it in food if urlsplit(media_url(it.get('img', ''), 'menu')).path == photo_path), None)
        page[f'pair_{i}_beer_id'] = card.get('data-beer', '')
        page[f'pair_{i}_food_id'] = dish['id'] if dish else ''
        page[f'pair_{i}_description'] = _text(card.select_one('.pair__why'))
    gallery = []
    for li in soup.select('[data-gallery] > li'):
        img = li.find('img')
        if img:
            gallery.append(dict(id=_identity('galeria', img['src']), image=img['src'],
                                alt=img.get('alt', ''), caption='', width=int(img.get('width', 1400)),
                                height=int(img.get('height', 1400)), wide='gallery__item--wide' in li.get('class', [])))
    events = []
    for node in soup.select('.events > .event'):
        img = node.find('img')
        title = _text(node.find('h3'))
        description = '\n'.join(_text(li) for li in node.select('li')) or _text(node.select_one('.event__body p'))
        events.append(dict(id=_identity('evento', title), title=title, date='', description=description,
                           image=img.get('src', '') if img else '', alt=img.get('alt', '') if img else '',
                           url='', visible=True, width=int(img.get('width', 1400)) if img else 1400,
                           height=int(img.get('height', 1400)) if img else 1400))
    return validate_document(dict(menu=menu, page=page, gallery=gallery, events=events))


def safe_url(value, *, media=False, optional=True):
    if not isinstance(value, str):
        raise ValueError('La URL debe ser texto.')
    if not value and optional:
        return value
    if not value or value != value.strip() or re.search(r'[\x00-\x20\x7f\\]', value):
        raise ValueError('URL inválida.')
    decoded = unquote(unquote(value))
    if re.search(r'[\x00-\x1f\x7f\\]', decoded) or decoded.startswith('//'):
        raise ValueError('URL inválida.')
    parsed = urlsplit(value)
    if parsed.scheme:
        if parsed.scheme.lower() not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError('Solo se permiten URLs http(s) o rutas internas.')
        if media and parsed.scheme.lower() != 'https':
            raise ValueError('Los medios externos requieren HTTPS.')
    elif not value.startswith('/') or value.startswith('//'):
        raise ValueError('La ruta interna debe comenzar con una sola diagonal.')
    path = urlsplit(decoded).path
    if '..' in path.split('/') or '.' in path.split('/'):
        raise ValueError('La URL contiene segmentos no permitidos.')
    if path.lower().endswith(('.svg', '.svgz')):
        raise ValueError('SVG no es un formato permitido para campos de contenido.')
    if media:
        if path.lower().endswith(('.svg', '.svgz', '.html', '.htm', '.js')):
            raise ValueError('Formato de medio no permitido.')
        if not parsed.scheme and not (path.startswith('/assets/') or re.fullmatch(r'/cms/media/[A-Za-z0-9_-]+/file', path)):
            raise ValueError('El medio debe pertenecer a assets o MediaHub.')
    return value


def media_url(value, group='menu'):
    if not value:
        return ''
    if value.startswith('/') or urlsplit(value).scheme:
        return safe_url(value, media=True)
    # Compatibilidad con nombres relativos del catálogo importado.
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', value):
        raise ValueError('Nombre de archivo inválido.')
    return safe_url('/assets/img/' + group + '/' + value, media=True)


def _plain(value, label, limit=12000, required=False):
    if not isinstance(value, str) or len(value) > limit or '\x00' in value:
        raise ValueError(f'{label}: texto inválido o demasiado largo.')
    if required and not value.strip():
        raise ValueError(f'{label}: el campo es obligatorio.')
    return value


def _number(value, label, low=0, high=1000000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label}: número fuera de rango.')
    return value


def _list(value, label, maximum=1000):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f'{label}: lista inválida.')
    return value


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f'{label}: objeto inválido.')
    return value


def _identities(items, label):
    ids = []
    for item in items:
        _object(item, label)
        identity = item.get('id', '')
        if not isinstance(identity, str) or not ID_RE.fullmatch(identity):
            raise ValueError(f'{label}: identificador inválido.')
        ids.append(identity)
    if len(ids) != len(set(ids)):
        raise ValueError(f'{label}: identificadores repetidos.')
    return set(ids)


def opening_hours(rows):
    result = []
    for row in rows:
        _object(row, 'Horario')
        days = _plain(row.get('dias'), 'Días', 100, True)
        hours = _plain(row.get('horas'), 'Horas', 150, True)
        normalized = unicodedata.normalize('NFKD', days).encode('ascii', 'ignore').decode().lower()
        indexes = [i for i, day in enumerate(DAY_NAMES) if re.search(r'\b' + day + r'\b', normalized)]
        if not indexes:
            raise ValueError('Horario: usa nombres de días de la semana.')
        if re.search(r'\ba\b', normalized) and len(indexes) == 2:
            indexes = list(range(indexes[0], indexes[1] + 1))
        if re.search(r'cerrad', hours, re.I):
            continue
        match = re.fullmatch(r'\s*(\d{1,2}):(\d{2})\s*[–—-]\s*(\d{1,2}):(\d{2})\s*', hours)
        if not match:
            raise ValueError('Horario: usa HH:MM – HH:MM o Cerrado.')
        h1, m1, h2, m2 = map(int, match.groups())
        if max(h1, h2) > 23 or max(m1, m2) > 59:
            raise ValueError('Horario fuera de rango.')
        result.append(dict(**{'@type': 'OpeningHoursSpecification'}, dayOfWeek=[DAY_SCHEMA[i] for i in indexes],
                           opens=f'{h1:02d}:{m1:02d}', closes=f'{h2:02d}:{m2:02d}'))
    return result


def validate_document(doc) -> dict:
    """Devuelve copia validada, sin eliminar borradores ni productos ocultos."""
    _object(doc, 'Documento')
    result = deepcopy(doc)
    menu = _object(result.get('menu'), 'Menú')
    page = _object(result.get('page'), 'Página')
    _list(result.get('gallery'), 'Galería', 200)
    _list(result.get('events'), 'Eventos', 100)
    business = _object(menu.get('negocio'), 'Negocio')
    for key, value in business.items():
        if key in ('horario', 'geo'):
            continue
        _plain(value, 'Negocio ' + key, required=key in ('nombre', 'direccion'))
        if key.endswith('_url'):
            safe_url(value)
    for key in ('nombre', 'direccion', 'telefono', 'telefono_display', 'email'):
        _plain(business.get(key), 'Negocio ' + key, 500, True)
    if not re.fullmatch(r'\+?[0-9 ()-]{7,30}', business['telefono']):
        raise ValueError('Teléfono inválido.')
    if not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', business['email']):
        raise ValueError('Correo inválido.')
    opening_hours(_list(business.get('horario'), 'Horario', 14))
    geo = _object(business.get('geo'), 'Coordenadas')
    _number(geo.get('lat'), 'Latitud', -90, 90)
    _number(geo.get('lng'), 'Longitud', -180, 180)
    profiles = _object(menu.get('perfiles'), 'Perfiles')
    for key, value in profiles.items():
        if not ID_RE.fullmatch(key):
            raise ValueError('Perfil inválido.')
        _plain(value, 'Perfil', 500)
    categories = _list(menu.get('comida'), 'Categorías', 100)
    _identities(categories, 'Categorías')
    foods = []
    for section in categories:
        _plain(section.get('seccion'), 'Categoría', 160, True)
        if not isinstance(section.setdefault('visible', True), bool):
            raise ValueError('Visibilidad de categoría inválida.')
        foods.extend(_list(section.get('items'), 'Productos'))
    groups = {key: _list(menu.get(key), key) for key in ('barril', 'latas', 'sin_alcohol')}
    all_items = foods + [item for group in groups.values() for item in group]
    _identities(all_items, 'Productos')
    food_ids = {item['id'] for item in foods}
    for item in all_items:
        _plain(item.get('nombre'), 'Nombre de producto', 200, True)
        for flag in ('visible', 'disponible'):
            if not isinstance(item.setdefault(flag, True), bool):
                raise ValueError(f'{flag}: debe ser verdadero o falso.')
        for key in ('descripcion', 'notas', 'historia', 'estilo', 'cerveceria', 'origen', 'detalle', 'nombre_completo'):
            if key in item:
                _plain(item[key], key)
        if 'precio' in item:
            _number(item['precio'], 'Precio')
        if 'abv' in item:
            _number(item['abv'], 'ABV', 0, 100)
        if 'ibu' in item:
            _number(item['ibu'], 'IBU', 0, 500)
        if 'perfil' in item and item['perfil'] not in profiles:
            raise ValueError('Perfil de cerveza desconocido.')
        for key in ('img', 'etiqueta'):
            if key in item:
                media_url(_plain(item[key], key, 2000), 'cervezas' if item in groups['barril'] else 'menu')
    for item in foods + groups['latas'] + groups['sin_alcohol']:
        _number(item.get('precio'), 'Precio')
    for beer in groups['barril']:
        prices = _list(beer.get('precios'), 'Presentaciones', 20)
        if not prices:
            raise ValueError('Cada barril necesita al menos un precio.')
        measures = set()
        for price in prices:
            _object(price, 'Presentación')
            _plain(price.get('medida'), 'Medida', 60, True)
            _number(price.get('precio'), 'Precio')
            measure = re.sub(r'\s+', '', price['medida']).lower()
            if measure in measures:
                raise ValueError('Un barril no puede repetir la misma presentación.')
            measures.add(measure)
        for key in ('marida_con', 'marida_oficial'):
            refs = _list(beer.get(key, []), 'Maridajes', 100)
            if any(not isinstance(ref, str) or ref not in food_ids for ref in refs):
                raise ValueError('Maridaje con producto inexistente.')
    for beer in groups['barril'] + groups['latas']:
        _plain(beer.get('estilo'), 'Estilo', 200, True)
        _number(beer.get('abv'), 'ABV', 0, 100)
        if beer.get('perfil') not in profiles:
            raise ValueError('Selecciona un perfil de cerveza válido.')
    flight = _object(menu.get('vuelo'), 'Vuelo')
    for key in ('nombre', 'descripcion', 'nota'):
        _plain(flight.get(key, ''), 'Vuelo ' + key)
    if flight.get('precio_desde') is not None:
        _number(flight['precio_desde'], 'Precio del vuelo')
    for key in HERO_KEYS:
        if key not in page:
            raise ValueError('Falta el campo de portada: ' + key)
    if page['hero_mode'] not in ('image', 'video'):
        raise ValueError('Modo de portada inválido.')
    for key, value in page.items():
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,99}', key):
            raise ValueError('Campo de página inválido.')
        _plain(value, key)
        if key in ('hero_image', 'hero_poster', 'hero_video_desktop', 'hero_video_mobile', 'social_image') or key.endswith('_image'):
            safe_url(value, media=True, optional=key not in ('hero_image', 'hero_poster'))
    if page['hero_mode'] == 'video' and not page['hero_video_desktop']:
        raise ValueError('Selecciona el video de portada.')
    beer_ids = {item['id'] for item in groups['barril']}
    for key, value in page.items():
        if re.fullmatch(r'pair_\d+_beer_id', key) and value and value not in beer_ids:
            raise ValueError('La pareja destacada hace referencia a un barril inexistente.')
        if re.fullmatch(r'pair_\d+_food_id', key) and value and value not in food_ids:
            raise ValueError('La pareja destacada hace referencia a un platillo inexistente.')
    for collection in ('gallery', 'events'):
        _identities(result[collection], collection)
        for item in result[collection]:
            safe_url(_plain(item.get('image'), 'Imagen', 2000), media=True, optional=False)
            for key in ('alt', 'caption') if collection == 'gallery' else ('title', 'date', 'description', 'alt'):
                item.setdefault(key, '')
                _plain(item[key], key, required=key == 'title')
            for dimension in ('width', 'height'):
                if dimension in item:
                    _number(item[dimension], dimension, 1, 20000)
            if 'wide' in item and not isinstance(item['wide'], bool):
                raise ValueError('Formato de galería inválido.')
            if collection == 'events':
                safe_url(item.setdefault('url', ''))
                if not isinstance(item.setdefault('visible', True), bool):
                    raise ValueError('Visibilidad de evento inválida.')
    return result


def editor_fields(doc) -> list[dict]:
    """Campos con rutas dotted (índices en colecciones); los IDs no son editables."""
    fields = []
    def add(key, label, kind, section, **extra):
        fields.append(dict(key=key, label=label, type=kind, section=section, **extra))
    page = doc['page']
    for key in page:
        if key in PAGE_BINDINGS:
            _, _, kind, section, label = PAGE_BINDINGS[key]
        else:
            kind = 'textarea' if key.endswith(('_description', '_lead')) or '_p_' in key else 'text'
            section, label = key.split('_')[0].capitalize(), key.replace('_', ' ').capitalize()
        if key == 'hero_mode':
            add('page.' + key, 'Tipo de portada', 'select', 'Portada', options=[{'value': 'image', 'label': 'Fotografía'}, {'value': 'video', 'label': 'Video'}])
            continue
        if key.startswith('hero_video_'):
            kind, section = 'video', 'Portada'
        if key == 'hero_poster':
            kind, section, label = 'image', 'Portada', 'Fotografía de respaldo'
        if re.fullmatch(r'pair_\d+_(beer|food)_id', key):
            choices = doc['menu']['barril'] if key.endswith('_beer_id') else [it for cat in doc['menu']['comida'] for it in cat['items']]
            add('page.' + key, 'Cerveza destacada' if key.endswith('_beer_id') else 'Platillo destacado', 'select', 'Maridajes destacados',
                options=[dict(value='', label='Sin selección')] + [dict(value=it['id'], label=it.get('nombre_completo') or it['nombre']) for it in choices])
            continue
        add('page.' + key, label, kind, section)
    foods = [it for cat in doc['menu']['comida'] for it in cat['items']]
    food_options = [dict(value=it['id'], label=it.get('nombre_completo') or it['nombre']) for it in foods]
    labels = {'nombre': 'Nombre', 'nombre_completo': 'Nombre fuera de su categoría', 'precio': 'Precio MXN',
              'disponible': 'Disponible', 'visible': 'Visible', 'img': 'Imagen', 'etiqueta': 'Etiqueta',
              'descripcion': 'Descripción', 'historia': 'Historia', 'notas': 'Notas de cata', 'abv': 'Alcohol (%)',
              'ibu': 'IBU', 'marida_con': 'Marida con', 'marida_oficial': 'Maridajes de la casa'}
    def walk(value, path, section):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('id', '_meta') or (path == 'menu.negocio' and key == 'google_review_url'):
                    continue
                if path == 'menu.vuelo' and key == 'precio_desde':
                    # Se calcula con las cuatro presentaciones disponibles de menor precio.
                    continue
                child_path = path + '.' + key
                if key in ('marida_con', 'marida_oficial'):
                    add(child_path, labels[key], 'multiselect', section, options=food_options)
                else:
                    walk(child, child_path, section)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                group = section
                if isinstance(child, dict):
                    name = child.get('nombre') or child.get('seccion') or child.get('title')
                    if name:
                        group += ' · ' + name
                walk(child, path + '.' + str(i), group)
        else:
            key = path.rsplit('.', 1)[-1]
            kind = 'boolean' if isinstance(value, bool) else 'number' if isinstance(value, (int, float)) else 'text'
            if key in ('img', 'etiqueta', 'image'):
                kind = 'image'
            elif key.endswith('_url') or key == 'url':
                kind = 'url'
            elif key in ('descripcion', 'description', 'notas', 'historia'):
                kind = 'textarea'
            add(path, labels.get(key, key.replace('_', ' ').capitalize()), kind, section)
    for group, title in [('negocio', 'Datos del negocio'), ('perfiles', 'Perfiles'), ('barril', 'Barriles'),
                         ('vuelo', 'Vuelo'), ('latas', 'Latas'), ('comida', 'Comida'), ('sin_alcohol', 'Sin alcohol')]:
        walk(doc['menu'][group], 'menu.' + group, title)
    walk(doc['gallery'], 'gallery', 'Galería')
    walk(doc['events'], 'events', 'Eventos')
    return fields


def _available(item):
    return item.get('visible', True) and item.get('disponible', True)


def published_menu(menu):
    menu = deepcopy(menu)
    for key in ('barril', 'latas', 'sin_alcohol'):
        menu[key] = [item for item in menu[key] if _available(item)]
    categories = []
    for cat in menu['comida']:
        if not cat.get('visible', True):
            continue
        cat['items'] = [item for item in cat['items'] if _available(item)]
        if cat['items']:
            categories.append(cat)
    menu['comida'] = categories
    ids = {item['id'] for cat in categories for item in cat['items']}
    for beer in menu['barril']:
        for key in ('marida_con', 'marida_oficial'):
            if key in beer:
                beer[key] = [ref for ref in beer[key] if ref in ids]
    flight_prices = sorted(price['precio'] for beer in menu['barril'] for price in beer['precios']
                           if re.fullmatch(r'4\s*oz', price['medida'], re.I))
    menu['vuelo']['precio_desde'] = sum(flight_prices[:4]) if len(flight_prices) >= 4 else None
    return menu


def _set_text(node, value):
    # Retiene em, enlaces y otros detalles de la plantilla si no cambió el texto.
    if _text(node) != value:
        node.clear()
        node.append(value)


def _mark(node, key, preview):
    if preview and node:
        node['data-cms-key'] = key


def _new(soup, name, text=None, **attrs):
    node = soup.new_tag(name, attrs=attrs)
    if text is not None:
        node.string = str(text)
    return node


def _contact(soup, menu, source_menu, preview):
    business = menu['negocio']
    original = source_menu['negocio']
    for anchor in soup.select('a[href]'):
        href = anchor['href']
        if href.startswith('tel:'):
            anchor['href'] = 'tel:' + re.sub(r'[^+0-9]', '', business['telefono'])
            _set_text(anchor, ('Llamar ' if _text(anchor).startswith('Llamar ') else '') + business['telefono_display'])
            _mark(anchor, 'menu.negocio.telefono', preview)
        elif href.startswith('mailto:'):
            anchor['href'] = 'mailto:' + business['email']
            _set_text(anchor, business['email'])
            _mark(anchor, 'menu.negocio.email', preview)
        else:
            for key, old in original.items():
                if key.endswith('_url') and old and href == old:
                    if business.get(key):
                        anchor['href'] = business[key]
                    else:
                        anchor.attrs.pop('href', None)
                        anchor['hidden'] = ''
                    _mark(anchor, 'menu.negocio.' + key, preview)
                    break
    address = soup.select_one('.visit__addr')
    if address:
        if business['direccion'] != original['direccion']:
            _set_text(address, business['direccion'])
        _mark(address, 'menu.negocio.direccion', preview)
    hours = soup.select_one('.hours tbody')
    if hours:
        if business['horario'] != original['horario']:
            hours.clear()
            for row in business['horario']:
                tr = _new(soup, 'tr', **({'class': 'hours__off'} if re.search('cerrad', row['horas'], re.I) else {}))
                tr.append(_new(soup, 'th', row['dias'], scope='row'))
                tr.append(_new(soup, 'td', row['horas']))
                hours.append(tr)
        for i, row in enumerate(hours.find_all('tr')):
            _mark(row.find('th'), f'menu.negocio.horario.{i}.dias', preview)
            _mark(row.find('td'), f'menu.negocio.horario.{i}.horas', preview)
    name = soup.select_one('.footer__name')
    if name:
        _set_text(name, business['nombre'])
        _mark(name, 'menu.negocio.nombre', preview)
    iframe = soup.select_one('.visit__map iframe')
    if iframe:
        geo = business['geo']
        iframe['src'] = 'https://maps.google.com/maps?' + urlencode({'q': f'{geo["lat"]},{geo["lng"]}', 'z': 17, 'hl': 'es', 'output': 'embed'})
        _mark(iframe.parent, 'menu.negocio.geo.lat', preview)


def _gallery_events(soup, doc, preview):
    box = soup.select_one('[data-gallery]')
    if box:
        box.clear()
        for i, item in enumerate(doc['gallery']):
            li = _new(soup, 'li', **{'class': 'gallery__item' + (' gallery__item--wide' if item.get('wide') else '')})
            button = _new(soup, 'button', type='button', **{'data-full': item['image']})
            img = _new(soup, 'img', src=item['image'], alt=item['alt'], width=item.get('width', 1400),
                       height=item.get('height', 1400), loading='lazy', decoding='async')
            _mark(img, f'gallery.{i}.image', preview)
            button.append(img)
            li.append(button)
            if item.get('caption'):
                caption = _new(soup, 'p', item['caption'], **{'class': 'gallery__caption'})
                _mark(caption, f'gallery.{i}.caption', preview)
                li.append(caption)
            box.append(li)
    box = soup.select_one('.events')
    if box:
        box.clear()
        for i, item in enumerate(doc['events']):
            if not item['visible']:
                continue
            article = _new(soup, 'article', **{'class': 'event'})
            img = _new(soup, 'img', src=item['image'], alt=item.get('alt', ''), width=item.get('width', 1400),
                       height=item.get('height', 1400), loading='lazy', decoding='async')
            _mark(img, f'events.{i}.image', preview)
            article.append(img)
            body = _new(soup, 'div', **{'class': 'event__body'})
            title = _new(soup, 'h3', item['title'])
            _mark(title, f'events.{i}.title', preview)
            body.append(title)
            if item['date']:
                date = _new(soup, 'p', item['date'], **{'class': 'event__date'})
                _mark(date, f'events.{i}.date', preview)
                body.append(date)
            if '\n' in item['description']:
                description = _new(soup, 'ul')
                for line in item['description'].splitlines():
                    if line.strip():
                        description.append(_new(soup, 'li', line))
            else:
                description = _new(soup, 'p', item['description'])
            _mark(description, f'events.{i}.description', preview)
            body.append(description)
            if item['url']:
                link = _new(soup, 'a', 'Ver evento', href=item['url'], target='_blank', rel='noopener')
                _mark(link, f'events.{i}.url', preview)
                body.append(link)
            article.append(body)
            box.append(article)


def _hero(soup, page, preview):
    hero = soup.select_one('.hero')
    if not hero:
        return
    for node in hero.select('video, .hero__video-control'):
        node.decompose()
    image = hero.select_one('img.hero__bg')
    if page['hero_mode'] == 'image':
        hero['class'] = [c for c in hero.get('class', []) if c != 'hero--video']
        return
    hero['class'] = list(dict.fromkeys(hero.get('class', []) + ['hero--video']))
    image['class'] = list(dict.fromkeys(image.get('class', []) + ['hero__poster']))
    image['src'] = page['hero_poster']
    _mark(image, 'page.hero_poster', preview)
    video = _new(soup, 'video', **{'class': 'hero__bg hero__video', 'id': 'hero-video', 'muted': '', 'loop': '',
                                 'playsinline': '', 'preload': 'none', 'aria-hidden': 'true', 'tabindex': '-1',
                                 'width': 1920, 'height': 1080, 'poster': page['hero_poster'],
                                 'data-src': page['hero_video_desktop'],
                                 'data-mobile-src': page['hero_video_mobile'] or page['hero_video_desktop']})
    image.insert_after(video)
    _mark(video, 'page.hero_video_desktop', preview)
    control = _new(soup, 'button', type='button', hidden='', **{'class': 'hero__video-control', 'aria-controls': 'hero-video'})
    control.append(_new(soup, 'span', '▶', **{'data-video-icon': '', 'aria-hidden': 'true'}))
    control.append(_new(soup, 'span', 'Reproducir video', **{'data-video-label': ''}))
    video.insert_after(control)
    if not soup.select_one('link[href="/assets/css/hero-video.css"]'):
        soup.head.append(_new(soup, 'link', rel='stylesheet', href='/assets/css/hero-video.css'))
    if not soup.select_one('script[src="/assets/js/hero-video.js"]'):
        soup.body.append(_new(soup, 'script', src='/assets/js/hero-video.js', defer=''))


PREVIEW_SCRIPT = r"""(() => {
  'use strict';
  const tell = node => {
    const field = node && node.closest && node.closest('[data-cms-key]');
    if (field && window.parent !== window) window.parent.postMessage({type: 'cms-select', key: field.dataset.cmsKey}, location.origin);
  };
  document.addEventListener('click', e => {
    if (e.target.closest('.hero__video-control')) return;
    tell(e.target);
    if (e.target.closest('a,button,input,select,textarea,form,[data-cms-key]')) {
      e.preventDefault(); e.stopImmediatePropagation();
    }
  }, true);
  document.addEventListener('submit', e => { e.preventDefault(); e.stopImmediatePropagation(); }, true);
  document.addEventListener('keydown', e => {
    if (e.target.closest('.hero__video-control')) return;
    if (e.key === 'Enter' || e.key === ' ') {
      tell(e.target); e.preventDefault(); e.stopImmediatePropagation();
    }
  }, true);
})();"""


def _instrument(soup, preview, revision):
    url = '/cms/preview/data/menu.json' if preview else '/data/menu.json'
    if revision is not None and not preview:
        url += '?' + urlencode({'v': str(revision)})
    soup.body['data-menu-url'] = url
    if revision is not None:
        soup.body['data-cms-revision'] = str(revision)
    for script in soup.select('script[src]'):
        path = urlsplit(script['src']).path
        if path in ('/assets/js/landing.js', '/assets/js/menu.js'):
            script['src'] = path + '?v=cms-20261008-2'
    if not preview:
        return
    soup.body['data-cms-preview'] = 'true'
    for iframe in soup.find_all('iframe'):
        iframe['tabindex'] = '-1'
        iframe['style'] = 'pointer-events:none'
    for form in soup.find_all('form'):
        form.attrs.pop('action', None)
    for anchor in soup.find_all('a'):
        anchor.attrs.pop('href', None)
        anchor.attrs.pop('target', None)
    style = _new(soup, 'style')
    style.string = '[data-cms-key]{cursor:crosshair!important}[data-cms-key]:hover{outline:2px solid #f2c97d;outline-offset:3px}'
    soup.head.append(style)
    script = _new(soup, 'script')
    script.string = PREVIEW_SCRIPT
    # Captura eventos antes de que los controladores normales se registren.
    soup.head.insert(0, script)


def _validated_focal(media_focal):
    """Only MediaHub URLs and normalized finite coordinates enter a release."""
    if media_focal is None:
        return {}
    if not isinstance(media_focal, dict):
        raise ValueError('El mapa de puntos focales no es válido.')
    result = {}
    for url, point in media_focal.items():
        if not isinstance(url, str) or not re.fullmatch(r'/cms/media/[A-Za-z0-9_-]+/file', url):
            raise ValueError('El punto focal debe pertenecer a un archivo de MediaHub.')
        if not isinstance(point, dict):
            raise ValueError('El punto focal no es válido.')
        result[url] = {axis: _number(point.get(axis), 'Punto focal', low=0, high=1) for axis in ('x', 'y')}
    return result


def _apply_focal(soup, focal):
    for node in soup.select('img, video'):
        sources = ('src', 'data-src', 'poster') if node.name == 'video' else ('src',)
        point = next((focal[urlsplit(node.get(attr, '')).path] for attr in sources
                      if urlsplit(node.get(attr, '')).path in focal and not urlsplit(node.get(attr, '')).netloc), None)
        if point is None:
            continue
        style = node.get('style', '')
        # Replace an existing position while preserving unrelated inline styles.
        style = re.sub(r'(^|;)\s*object-position\s*:[^;]*(;|$)', r'\1', style, flags=re.I).strip().rstrip(';')
        position = f'{point["x"] * 100:g}% {point["y"] * 100:g}%'
        node['style'] = (style + ';' if style else '') + 'object-position:' + position


def render_document(doc, site_root: Path, preview=False, revision=None, media_focal=None) -> dict[str, str]:
    doc = validate_document(doc)
    focal = _validated_focal(media_focal)
    site_root = Path(site_root)
    original_menu = json.loads((site_root / 'data/menu.json').read_text(encoding='utf-8'))
    if preview:
        for group in ('barril', 'latas', 'sin_alcohol'):
            for i, item in enumerate(doc['menu'][group]):
                item['_cms_key'] = f'menu.{group}.{i}'
        for i, category in enumerate(doc['menu']['comida']):
            category['_cms_key'] = f'menu.comida.{i}'
            for j, item in enumerate(category['items']):
                item['_cms_key'] = f'menu.comida.{i}.items.{j}'
    menu = published_menu(doc['menu'])
    menu.pop('_media_focal', None)
    if focal:
        menu['_media_focal'] = focal
    if revision is not None:
        menu.setdefault('_meta', {})['revision'] = str(revision)
    soup = _soup(site_root)
    for key, node, attr, *_ in _bindings(soup):
        if key not in doc['page']:
            continue
        value = doc['page'][key]
        if attr:
            node[attr] = value
        else:
            _set_text(node, value)
        _mark(node, 'page.' + key, preview)
    _contact(soup, menu, original_menu, preview)
    _hero(soup, doc['page'], preview)
    _gallery_events(soup, doc, preview)
    dishes = {item['id']: item for cat in menu['comida'] for item in cat['items']}
    beers = {item['id']: item for item in menu['barril']}
    original_beers = {item['id']: item for item in original_menu['barril']}
    for i, card in enumerate(soup.select('.pairs .pair')):
        original_card_beer = card.get('data-beer')
        beer_id = doc['page'].get(f'pair_{i}_beer_id', card.get('data-beer'))
        food_id = doc['page'].get(f'pair_{i}_food_id')
        beer, dish = beers.get(beer_id), dishes.get(food_id)
        if not beer or not dish or food_id not in beer.get('marida_con', []):
            card.decompose()
            continue
        card['data-beer'] = beer_id
        card['data-food'] = food_id
        food_img = card.select_one('img:not(.pair__vaso)')
        if food_img:
            food_img['src'] = media_url(dish.get('img', ''), 'menu')
            _mark(food_img, f'page.pair_{i}_food_id', preview)
        beer_img = card.select_one('.pair__vaso')
        if beer_img:
            beer_img['src'] = media_url(beer.get('img', ''), 'cervezas')
            _mark(beer_img, f'page.pair_{i}_beer_id', preview)
        title = card.select_one('.pair__dish')
        _set_text(title, dish.get('nombre_completo') or dish['nombre'])
        _mark(title, f'page.pair_{i}_food_id', preview)
        if original_card_beer != beer_id or any(beer.get(key) != original_beers.get(beer_id, {}).get(key) for key in ('nombre', 'estilo', 'abv')):
            title = card.select_one('.pair__beer')
            title.clear()
            title.append(_new(soup, 'span', f'{beer.get("estilo", "")} · {beer.get("abv", 0):.1f}%', **{'class': 'mono'}))
            title.append(' ' + beer['nombre'])
        why = card.select_one('.pair__why')
        _set_text(why, doc['page'].get(f'pair_{i}_description', _text(why)))
        _mark(why, f'page.pair_{i}_description', preview)
    page = doc['page']
    for name, value in [('twitter:title', page.get('social_title', page.get('seo_title', ''))),
                        ('twitter:description', page.get('social_description', page.get('seo_description', ''))),
                        ('twitter:image', page.get('social_image', page['hero_image']))]:
        node = soup.select_one(f'meta[name="{name}"]')
        if node:
            node['content'] = value
    for node in soup.select('meta[property="og:site_name"]'):
        node['content'] = menu['negocio']['nombre']
    preload = soup.select_one('link[rel="preload"][as="image"]')
    if preload:
        preload['href'] = page['hero_poster'] if page['hero_mode'] == 'video' else page['hero_image']
    linked = soup.select_one('script[type="application/ld+json"]')
    if linked:
        data = json.loads(linked.string)
        business = menu['negocio']
        data.update(name=business['nombre'], slogan=business.get('eslogan', ''),
                    description=page.get('schema_description', page.get('seo_description', '')),
                    telephone=business['telefono'], email=business['email'],
                    image=page.get('social_image') or page['hero_image'],
                    hasMap=business.get('google_maps_url', ''),
                    geo={'@type': 'GeoCoordinates', 'latitude': business['geo']['lat'], 'longitude': business['geo']['lng']},
                    openingHoursSpecification=opening_hours(business['horario']),
                    sameAs=[business[k] for k in ('instagram_url', 'facebook_url', 'tiktok_url') if business.get(k)])
        if business['direccion'] != original_menu['negocio']['direccion']:
            data['address'] = business['direccion']
        linked.string = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    _apply_focal(soup, focal)
    _instrument(soup, preview, revision)
    menu_soup = _soup(site_root, 'menu/index.html')
    if menu_soup.title:
        _set_text(menu_soup.title, 'Menú · ' + menu['negocio']['nombre'])
    _contact(menu_soup, menu, original_menu, preview)
    _apply_focal(menu_soup, focal)
    _instrument(menu_soup, preview, revision)
    return {'index.html': str(soup), 'menu/index.html': str(menu_soup),
            'data/menu.json': json.dumps(menu, ensure_ascii=False, indent=2) + '\n'}
