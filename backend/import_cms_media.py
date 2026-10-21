#!/usr/bin/env python3
"""Import local Cisne Negro assets into a durable MediaStore, without publishing.

python3 backend/import_cms_media.py --root /var/lib/cisnenegro-cms/media \
    --site ./sitio --archive ./contenido

--site accepts the site's directory and imports only assets/img and assets/video.
--archive accepts the project's downloaded contenido directory, not a ZIP. Caption
and meta JSON files alongside Instagram images supply provenance when available.
All imports remain reviewed=false; imported originals are never publicly served.
Exact SHA256 duplicates keep the existing item and its metadata. An optional JSON
map records site-relative paths to media IDs, for the initial content import.
Requires Pillow and FFmpeg. --wait permits the durable video queue to finish before
exit (default waits up to 15 minutes); without it, the CMS process resumes that queue.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from PIL import Image, UnidentifiedImageError

from cms_media import IMAGE_SUFFIXES, MediaError, MediaStore

EXTENSIONS = set(IMAGE_SUFFIXES) | {'.mp4'}


def ingestion_filename(path):
    """Normalize mislabeled local downloads, without modifying the source.

    Only this trusted local importer adapts the extension. MediaStore.ingest keeps
    its strict validation of all submitted bytes, dimensions and permitted types.
    Browser uploads never call this helper.
    """
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        try:
            with Image.open(path) as image:
                extension = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp', 'HEIF': '.heic'}.get(image.format)
            if extension and IMAGE_SUFFIXES[suffix] != IMAGE_SUFFIXES[extension]:
                return path.stem + extension
        except (OSError, ValueError, UnidentifiedImageError):
            pass  # The ingestion validator supplies the definitive, bounded error.
    return path.name


def category_for(relative):
    text = relative.lower()
    if any(s in text for s in ('/marca/', 'logo', 'favicon', 'mascota', 'pluma', 'apple-touch')):
        return 'Marca'
    if any(s in text for s in ('/cervezas/', '/etiquetas/', 'cerveza', 'pinta', 'tarro')):
        return 'Cervezas'
    if any(s in text for s in ('/comida/', 'platillo', 'burger', 'hamburg', 'pizza', 'cocina', 'camaron', 'taco', 'tlayuda', 'dona', 'papas')):
        return 'Cocina'
    if any(s in text for s in ('ferment', 'elabor', 'produccion')):
        return 'Elaboración'
    if any(s in text for s in ('aniversario', 'evento', 'velas', 'oktoberfest', 'yoga')):
        return 'Eventos'
    if any(s in text for s in ('brindis', 'amigos', 'comunidad', 'pet-', 'equipo')):
        return 'Comunidad'
    if any(s in text for s in ('/lugar/', 'neon', 'barra', 'grifos', 'taproom', 'fachada')):
        return 'Barra y lugar'
    return ''


def _small_json(path):
    if path.is_file() and not path.is_symlink() and path.stat().st_size <= 1_000_000:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except (ValueError, OSError):
            pass
    return {}


def metadata_for(path, base, origin):
    relative = path.relative_to(base).as_posix()
    name = path.stem.replace('-', ' ').replace('_', ' ')
    metadata = {'title': name[:200], 'source': origin, 'category': category_for('/' + relative),
                'tags': ['importado', 'pendiente de revisión'], 'reviewed': False}
    channel = next((label for key, label in [('instagram/', 'Instagram'), ('tiktok/', 'TikTok'),
                    ('google-maps/', 'Google Maps'), ('sitio-web/', 'Sitio web original')]
                    if relative.startswith(key)), None)
    if channel:
        metadata['source'] = f'{origin} · {channel}'
        metadata['tags'].append(channel.lower())
    date_match = re.search(r'(20\d{2}-\d{2}-\d{2})', relative)
    if date_match:
        metadata['date'] = date_match.group(1)
    elif re.match(r'^20\d{6}_', path.name):
        d = path.name[:8]
        metadata['date'] = f'{d[:4]}-{d[4:6]}-{d[6:]}'
    meta = _small_json(path.parent / 'meta.json')
    if not meta:
        meta = _small_json(path.with_suffix('.info.json'))
    for key in ('url', 'webpage_url', 'webVideoUrl', 'postUrl'):
        url = meta.get(key)
        if isinstance(url, str) and url.startswith(('https://', 'http://')):
            metadata['source_url'] = url[:2000]
            break
    caption = path.parent / 'caption.txt'
    if not caption.is_file():
        caption = path.with_suffix('.description')
    if caption.is_file() and not caption.is_symlink() and caption.stat().st_size < 100_000:
        metadata['caption'] = caption.read_text(encoding='utf-8', errors='replace').strip()[:4000]
    if path.stem.isdigit():
        metadata['title'] = (metadata.get('caption', '').split('\n')[0][:160]
                             or f'{path.parent.name} · {path.stem}')
    return metadata


def candidates(base, origin, site=False):
    roots = [base / 'assets' / 'img', base / 'assets' / 'video'] if site else [base]
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob('*')):
            if (path.is_file() and not path.is_symlink() and path.suffix.lower() in EXTENSIONS
                    and base.resolve() in path.resolve().parents):
                # Never traverse sensitive folders even when a broader archive path is supplied.
                if any(part.upper() == 'PRIVADO' or part.startswith('.') for part in path.relative_to(base).parts):
                    continue
                yield path, base, origin


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', required=True, type=Path, help='Directorio persistente privado fuera del repositorio')
    parser.add_argument('--site', type=Path, help='Directorio sitio; importa assets/img y assets/video')
    parser.add_argument('--archive', type=Path, help='Directorio contenido del archivo propio')
    parser.add_argument('--map-out', type=Path, help='Mapa JSON opcional de rutas relativas → identificadores')
    parser.add_argument('--wait', action='store_true', help='Esperar conversiones de video antes de cerrar')
    parser.add_argument('--timeout', type=int, default=900, help='Espera máxima de video en segundos con --wait')
    args = parser.parse_args(argv)
    if not args.site and not args.archive:
        parser.error('Indica --site, --archive o ambos.')
    sources = []
    for base, origin, site in [(args.site, 'Sitio existente de Cisne Negro', True),
                               (args.archive, 'Archivo propio de Cisne Negro', False)]:
        if base:
            base = base.expanduser().resolve()
            if not base.is_dir():
                parser.error(f'No existe el directorio: {base.name}')
            sources.extend(candidates(base, origin, site))
    store = MediaStore(args.root)
    counts = {'importados': 0, 'duplicados': 0, 'errores': 0}
    mapping = {}
    try:
        for index, (path, base, origin) in enumerate(sources, 1):
            try:
                with path.open('rb') as source:
                    item = store.ingest(source, ingestion_filename(path), metadata_for(path, base, origin))
                state = 'duplicados' if item.get('duplicate') else 'importados'
                counts[state] += 1
                mapping[f'{base.name}/{path.relative_to(base).as_posix()}'] = item['id']
                print(f'[{index}/{len(sources)}] {state}: {path.name} · {item["status"]}', flush=True)
            except (MediaError, OSError) as error:
                counts['errores'] += 1
                print(f'[{index}/{len(sources)}] error: {path.name}: {error}', file=sys.stderr, flush=True)
        if args.map_out:
            args.map_out.parent.mkdir(parents=True, exist_ok=True)
            args.map_out.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if args.wait:
            if not store.wait_for_idle(max(1, args.timeout)):
                print('Quedan videos en cola; el servicio CMS continuará al iniciarse.', flush=True)
        with store._db() as db:
            failures = db.execute("SELECT count(*) FROM media WHERE status='error'").fetchone()[0]
        print(json.dumps({**counts, 'videos_con_error': failures, 'uso': store.usage()}, ensure_ascii=False))
        return 1 if counts['errores'] or failures else 0
    finally:
        store.close()


if __name__ == '__main__':
    raise SystemExit(main())
