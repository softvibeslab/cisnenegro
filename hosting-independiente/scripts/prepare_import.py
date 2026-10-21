#!/usr/bin/env python3
"""Regenera una COPIA privada del CMS sobre v2, sin publicar su borrador."""
import argparse
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata
from urllib.parse import urlsplit

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'backend'))
from cms_content import initial_document, media_url, render_document, validate_document


def rebase(value, field=()):
    """Solo cambia URLs propias; conserva textos, campos y destinos externos."""
    if isinstance(value, dict):
        return {key: rebase(item, field + (key,)) for key, item in value.items()}
    if isinstance(value, list):
        return [rebase(item, field) for item in value]
    if isinstance(value, str):
        for origin in ('https://cisnenegro.softvibes.art', 'http://cisnenegro.softvibes.art',
                       'https://cisne.softvibes.art', 'https://www.cisnenegro.mx', 'https://cisnenegro.mx'):
            if value == origin or value.startswith(origin + '/'):
                path = value[len(origin):]
                if path == '/v2' or path.startswith('/v2/'):
                    path = path[3:]
                if field != ('page', 'social_image') and path.startswith(('/assets/', '/cms/media/')):
                    return path
                return 'https://cisnenegro.mx' + (path or '/')
    return value


def _products(menu):
    for group in ('barril', 'latas', 'sin_alcohol'):
        for item in menu[group]:
            yield group, item
    for category in menu['comida']:
        for item in category['items']:
            yield 'comida', item


def _normalized(value):
    value = unicodedata.normalize('NFKD', value)
    return ' '.join(''.join(c for c in value if not unicodedata.combining(c)).casefold().split())


def adapt_document(document, baseline):
    """Reconcilia identidades v2 sin reemplazar precios ni contenido editorial."""
    result = rebase(document)
    by_id, by_identity = {}, {}
    for group, item in _products(baseline['menu']):
        by_id[(group, item['id'])] = item
        identity = (group, _normalized(item['nombre']),
                    _normalized(item.get('cerveceria', item.get('marca', ''))))
        by_identity.setdefault(identity, []).append(item)
    mapped, assigned = {}, set()
    for group, item in _products(result['menu']):
        target = by_id.get((group, item['id']))
        if target is None:
            identity = (group, _normalized(item['nombre']),
                        _normalized(item.get('cerveceria', item.get('marca', ''))))
            matches = by_identity.get(identity, [])
            if len(matches) > 1:
                raise ValueError(f'Identidad v2 ambigua: {group}/{item["nombre"]}.')
            target = matches[0] if matches else None
        if target is None:
            continue  # Un producto editorial nuevo conserva su identidad.
        if target['id'] in assigned:
            raise ValueError(f'Dos productos del CMS coinciden con {target["id"]}.')
        assigned.add(target['id'])
        mapped[item['id']] = target['id']
        item['id'] = target['id']
        if target.get('variantes'):
            variants = item.setdefault('variantes', [])
            existing = {variant['id'] for variant in variants}
            variants.extend(deepcopy(variant) for variant in target['variantes']
                            if variant['id'] not in existing)
    for key, value in result['page'].items():
        if re.fullmatch(r'pair_\d+_(?:beer|food)_id', key):
            result['page'][key] = mapped.get(value, value)
    for beer in result['menu']['barril']:
        for key in ('marida_con', 'marida_oficial'):
            if key in beer:
                beer[key] = [mapped.get(value, value) for value in beer[key]]
    return validate_document(result)


def _strings(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, str):
        yield value


def _validate_resources(doc, rendered, site, data, media_rows, label):
    resources = set(_strings(doc))
    for group, item in _products(doc['menu']):
        for key in ('img', 'etiqueta'):
            if item.get(key):
                resources.add(media_url(item[key], 'cervezas' if group == 'barril' else 'menu'))
    for output in rendered.values():
        if 'cisnenegro.softvibes.art' in output:
            raise ValueError(f'{label} aún depende del dominio anterior.')
        resources.update(re.findall(r'(?:src|href|data-src|data-mobile-src)=[\"\']([^\"\']+)', output))
    for resource in resources:
        parsed = urlsplit(resource)
        if parsed.netloc and parsed.netloc != 'cisnenegro.mx':
            continue
        path = parsed.path
        if path.startswith('/assets/'):
            asset = (site / path.lstrip('/')).resolve()
            if site not in asset.parents or not asset.is_file():
                raise ValueError(f'Falta un recurso de {label}: {path}')
        match = re.fullmatch(r'/cms/media/([A-Za-z0-9_-]+)/file', path)
        if match:
            mid = match[1]
            row = media_rows.get(mid)
            if not row or row['status'] != 'ready':
                raise ValueError(f'Medio no disponible en {label}: {mid}')
            root = (data / 'cms/media/derivatives').resolve()
            asset = root / mid / ('file.mp4' if row['kind'] == 'video' else 'file.webp')
            if asset.is_symlink() or root not in asset.resolve().parents or not asset.is_file():
                raise ValueError(f'Falta un derivado de {label}: {mid}')


def prepare(data_dir, site_root=BASE / 'sitio'):
    data = Path(data_dir).resolve()
    site = Path(site_root).resolve()
    if data == BASE or BASE in data.parents:
        raise ValueError('Usa una copia de datos privada fuera del código.')
    db_path = data / 'cms/cms.sqlite'
    if not db_path.is_file():
        raise ValueError('Falta cms/cms.sqlite; no se crea ni publica contenido inicial.')
    with (data / 'runtime.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Detén la instalación de destino antes de adaptar sus datos.') from None
        with closing(sqlite3.connect(db_path)) as con:
            if con.execute('pragma integrity_check').fetchone()[0] != 'ok':
                raise ValueError('La copia CMS no pasa integrity_check.')
            published = con.execute("select value from settings where key='published'").fetchone()
            revisions = con.execute('select id,data from revisions order by id').fetchall()
            if not published or int(published[0]) not in {r[0] for r in revisions}:
                raise ValueError('Falta la publicación activa; no se selecciona otra automáticamente.')
            draft = con.execute('select data from draft where id=1').fetchone()
            if not draft:
                raise ValueError('Falta el borrador del CMS.')
            baseline = initial_document(site)
            draft_data = adapt_document(json.loads(draft[0]), baseline)
            focal = {}
            media_rows = {}
            media_db = data / 'cms/media/media.sqlite'
            if media_db.is_file():
                with closing(sqlite3.connect(f'file:{media_db}?mode=ro', uri=True)) as media:
                    media.row_factory = sqlite3.Row
                    media_rows = {row['id']: dict(row) for row in media.execute('select * from media')}
                    focal = {'/cms/media/' + mid + '/file': {'x': x, 'y': y}
                             for mid, x, y in media.execute('select id,focal_x,focal_y from media')}
            preview = render_document(draft_data, site, preview=True, media_focal=focal)
            _validate_resources(draft_data, preview, site, data, media_rows, 'el borrador')
            outputs = []
            for revision, raw in revisions:
                doc = adapt_document(json.loads(raw), baseline)
                rendered = render_document(doc, site, revision=revision, media_focal=focal)
                _validate_resources(doc, rendered, site, data, media_rows, f'la publicación {revision}')
                outputs.append((json.dumps(doc, ensure_ascii=False, separators=(',', ':')),
                                json.dumps(rendered, ensure_ascii=False, separators=(',', ':')), revision))
            # Todo se valida antes de alterar la copia. El respaldo incluye usuarios y borrador.
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup = db_path.with_name(f'cms.before-v2-{stamp}.sqlite')
            fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
            with closing(sqlite3.connect(backup)) as destination:
                con.backup(destination)
            with con:
                con.executemany('update revisions set data=?,output=? where id=?', outputs)
                if draft_data != json.loads(draft[0]):
                    con.execute('update draft set data=? where id=1',
                                (json.dumps(draft_data, ensure_ascii=False, separators=(',', ':')),))
            return {'revisions': len(outputs), 'published': int(published[0]),
                    'draft_preserved': True, 'backup': str(backup)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True,
                        help='Copia importada en destino detenido; nunca apuntar al sistema original.')
    args = parser.parse_args()
    print(json.dumps(prepare(args.data_dir), ensure_ascii=False))


if __name__ == '__main__':
    main()
