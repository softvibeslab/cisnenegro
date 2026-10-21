#!/usr/bin/env python3
"""Respaldo privado de CMS + MediaHub, sin detener SQLite ni tocar el Pasaporte.

Diario (root): python3 backup-cms.py
Restauración de prueba: python3 backup-cms.py --verify [snapshot|latest]
Pruebas aisladas: --source /tmp/origen --destination /tmp/respaldos --date YYYY-MM-DD

Los archivos se comparten mediante hardlinks ENTRE snapshots ya independientes;
nunca se enlazan archivos de producción. --verify restaura a /tmp y comprueba
hashes, SQLite y referencias; no restaura ni modifica la instalación activa.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date, datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile


FORMAT = 'cisne-negro-cms-backup-v1'
MANIFEST = 'manifest.json'
KEEP = 14
DATABASES = ('cms.sqlite', 'media/media.sqlite')
ID = re.compile(r'^[A-Za-z0-9_-]+$')
MEDIA_REF = re.compile(r'/cms/media/([A-Za-z0-9_-]+)/file')


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def regular(root, relative):
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or '..' in parts:
        raise ValueError('Ruta no permitida en el respaldo.')
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('No se respaldan ni restauran enlaces simbólicos.')
    if not current.is_file() or not current.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Archivo requerido ausente: {relative}')
    return current


def connect_readonly(path):
    con = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def online_database(source, destination):
    with closing(connect_readonly(source)) as src, closing(sqlite3.connect(destination)) as target:
        src.backup(target, pages=256, sleep=.05)
        target.execute('pragma journal_mode=delete')
        target.commit()
    os.chmod(destination, 0o600)


def manifest(snapshot):
    file = regular(snapshot, MANIFEST)
    value = json.loads(file.read_text(encoding='utf-8'))
    if value.get('format') != FORMAT or not isinstance(value.get('files'), dict):
        raise ValueError('El directorio no es un respaldo de Cisne Negro CMS reconocido.')
    return value


def completed(destination):
    result = []
    for child in destination.iterdir():
        if child.is_symlink() or not child.is_dir() or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', child.name):
            continue
        try:
            date.fromisoformat(child.name)
            manifest(child)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        result.append(child)
    return sorted(result)


def verify_contents(snapshot, recorded):
    expected_files = recorded['files']
    for relative, meta in expected_files.items():
        path = regular(snapshot, relative)
        if path.stat().st_size != meta['bytes'] or checksum(path) != meta['sha256']:
            raise ValueError(f'Integridad de archivo incorrecta: {relative}')
    for name in DATABASES:
        if name not in expected_files:
            raise ValueError('Falta una base obligatoria en el manifiesto.')
        with closing(connect_readonly(regular(snapshot, name))) as db:
            if db.execute('pragma integrity_check').fetchone()[0] != 'ok':
                raise ValueError(f'SQLite inconsistente: {name}')
            if db.execute('pragma foreign_key_check').fetchone():
                raise ValueError(f'Referencias SQLite inconsistentes: {name}')
    with closing(connect_readonly(snapshot / 'media/media.sqlite')) as db:
        rows = {row['id']: dict(row) for row in db.execute('select * from media')}
    for identity, row in rows.items():
        if not ID.fullmatch(identity) or not re.fullmatch(r'\.[a-zA-Z0-9]{1,8}', row['original_ext']):
            raise ValueError('Identificador de medio no seguro en el respaldo.')
        original = f'media/originals/{identity}{row["original_ext"]}'
        if original not in expected_files:
            raise ValueError(f'Original ausente del manifiesto: {identity}')
        if checksum(regular(snapshot, original)) != row['hash']:
            raise ValueError(f'Original no coincide con MediaHub: {identity}')
        if row['status'] == 'ready':
            for filename in ('thumb.jpg', 'file.mp4' if row['kind'] == 'video' else 'file.webp'):
                relative = f'media/derivatives/{identity}/{filename}'
                if relative not in expected_files:
                    raise ValueError(f'Derivado requerido ausente: {identity}/{filename}')
                regular(snapshot, relative)
    referenced, draft_refs = set(), set()
    with closing(connect_readonly(snapshot / 'cms.sqlite')) as db:
        for table in ('draft', 'revisions'):
            for row in db.execute(f'select data from {table}'):
                data = json.loads(row['data'])
                refs = MEDIA_REF.findall(json.dumps(data, ensure_ascii=False))
                (draft_refs if table == 'draft' else referenced).update(refs)
        published = db.execute("select value from settings where key='published'").fetchone()
        if published and not db.execute('select 1 from revisions where id=?', (published['value'],)).fetchone():
            raise ValueError('La revisión publicada no existe en el respaldo.')
    if referenced - rows.keys():
        raise ValueError('Una revisión publicada hace referencia a medios ausentes del respaldo.')
    if any(rows[mid]['status'] != 'ready' for mid in referenced):
        raise ValueError('Una revisión publicada contiene medios sin terminar de procesar.')
    if 'media-map.json' in expected_files:
        mapping = json.loads((snapshot / 'media-map.json').read_text(encoding='utf-8'))
        if not isinstance(mapping, dict) or any(not isinstance(mid, str) or mid not in rows for mid in mapping.values()):
            raise ValueError('El mapa de importación contiene referencias inválidas.')
    return dict(files=len(expected_files), media=len(rows), referenced_media=len(referenced),
                draft_missing_media=len(draft_refs - rows.keys()),
                draft_pending_media=sum(rows[mid]['status'] != 'ready' for mid in draft_refs & rows.keys()))


def verify(snapshot, restore=False):
    snapshot = Path(snapshot)
    if snapshot.is_symlink():
        raise ValueError('La ruta del respaldo no puede ser un enlace.')
    snapshot = snapshot.resolve()
    recorded = manifest(snapshot)
    result = verify_contents(snapshot, recorded)
    if restore:
        with tempfile.TemporaryDirectory(prefix='cisne-cms-restore-', dir='/tmp') as folder:
            target = Path(folder)
            for relative in recorded['files']:
                source = regular(snapshot, relative)
                dest = target / relative
                dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
                os.chmod(dest, 0o600)
            verify_contents(target, recorded)
        result['temporary_restore'] = 'ok'
    return result


def create_backup(source, destination, day=None):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or destination.is_symlink():
        raise ValueError('Las raíces no pueden ser enlaces simbólicos.')
    source, destination = source.resolve(), destination.resolve()
    if source == destination or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('Origen y destino deben estar separados.')
    destination.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(destination, 0o700)
    day = day or datetime.now(timezone.utc).date().isoformat()
    date.fromisoformat(day)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        raise ValueError('Fecha inválida.')
    lock_path = destination / '.backup.lock'
    if lock_path.is_symlink():
        raise ValueError('Archivo de bloqueo no válido.')
    with lock_path.open('a') as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        target = destination / day
        if target.exists() or target.is_symlink():
            return target, verify(target)
        previous = completed(destination)
        previous = previous[-1] if previous else None
        old_files = manifest(previous)['files'] if previous else {}
        temporary = Path(tempfile.mkdtemp(prefix='.partial-', dir=destination))
        records = {}
        try:
            # Primero CMS y después MediaHub: una referencia editorial nueva se
            # guarda solo después del alta del medio. Verificar detecta carreras.
            for relative in DATABASES:
                dest = temporary / relative
                dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                online_database(regular(source, relative), dest)
                records[relative] = dict(bytes=dest.stat().st_size, sha256=checksum(dest))
            paths = []
            for relative in ('media/originals', 'media/derivatives'):
                folder = source / relative
                if folder.is_symlink() or not folder.is_dir():
                    raise ValueError('Falta el árbol persistente de medios.')
                (temporary / relative).mkdir(parents=True, mode=0o700, exist_ok=True)
                for item in sorted(folder.rglob('*')):
                    if item.is_symlink():
                        raise ValueError('No se permiten enlaces en el árbol de medios.')
                    if item.is_file():
                        paths.append(item.relative_to(source).as_posix())
            if (source / 'media-map.json').exists():
                paths.append('media-map.json')
            for relative in paths:
                file = regular(source, relative)
                file_hash = checksum(file)
                dest = temporary / relative
                dest.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                meta = dict(bytes=file.stat().st_size, sha256=file_hash)
                prior = None
                if previous and old_files.get(relative) == meta:
                    try:
                        candidate = regular(previous, relative)
                        if checksum(candidate) == file_hash:
                            prior = candidate
                    except (ValueError, OSError):
                        pass
                if prior:
                    os.link(prior, dest)
                else:
                    shutil.copyfile(file, dest)
                    os.chmod(dest, 0o600)
                if checksum(dest) != file_hash:
                    raise ValueError(f'El archivo cambió durante el respaldo: {relative}')
                records[relative] = meta
            info = dict(format=FORMAT, created_at=datetime.now(timezone.utc).isoformat(),
                        source=str(source), files=records)
            manifest_path = temporary / MANIFEST
            manifest_path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            os.chmod(manifest_path, 0o600)
            result = verify_contents(temporary, info)
            os.replace(temporary, target)
            for old in completed(destination)[:-KEEP]:
                # Solo snapshots nuestros, completos y de nombres ISO; nunca
                # carpetas ajenas, symlinks ni respaldos parciales.
                shutil.rmtree(old)
            return target, result
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(os.environ.get('CMS_ROOT', '/var/lib/cisnenegro-cms')))
    parser.add_argument('--destination', type=Path, default=Path('/var/backups/cisnenegro-cms'))
    parser.add_argument('--date', help='Fecha ISO del snapshot, para pruebas o ejecución programada')
    parser.add_argument('--verify', nargs='?', const='latest', help='Verifica y restaura temporalmente el snapshot indicado o el último')
    args = parser.parse_args()
    if args.verify:
        choices = completed(args.destination) if args.verify == 'latest' else [Path(args.verify)]
        if not choices:
            parser.error('No hay snapshots completos para verificar.')
        print(json.dumps({'snapshot': str(choices[-1]), **verify(choices[-1], restore=True)}, ensure_ascii=False))
    else:
        snapshot, result = create_backup(args.source, args.destination, args.date)
        print(json.dumps({'snapshot': str(snapshot), **result}, ensure_ascii=False))


if __name__ == '__main__':
    main()
