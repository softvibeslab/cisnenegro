#!/usr/bin/env python3
"""Copia privada consistente; detiene solo app durante la lectura de los datos."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile

DATABASES = ('club.db', 'cms/cms.sqlite', 'cms/media/media.sqlite')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_data(root):
    root = Path(root).resolve()
    for relative in DATABASES:
        with closing(sqlite3.connect((root / relative).as_uri() + '?mode=ro', uri=True)) as con:
            if con.execute('pragma integrity_check').fetchall() != [('ok',)]:
                raise ValueError(f'Base dañada: {relative}')
    media_root = root / 'cms/media'
    with closing(sqlite3.connect((media_root / 'media.sqlite').as_uri() + '?mode=ro', uri=True)) as con:
        rows = con.execute("select id,kind,original_ext from media where status='ready'").fetchall()
    for media_id, kind, extension in rows:
        for path in (media_root / 'originals' / f'{media_id}{extension}',
                     media_root / 'derivatives' / media_id / ('file.mp4' if kind == 'video' else 'file.webp'),
                     media_root / 'derivatives' / media_id / 'thumb.jpg'):
            if media_root not in path.resolve().parents or path.is_symlink() or not path.is_file():
                raise ValueError('Falta un original o derivado de un medio listo.')
    return len(rows)


def snapshot(data, destination):
    """Llamar solo con el proceso detenido y runtime.lock adquirido."""
    data, destination = Path(data).resolve(), Path(destination).resolve()
    for relative in DATABASES:
        if not (data / relative).is_file():
            raise ValueError(f'Falta {relative}; no se crea una base vacía.')
    destination.mkdir(mode=0o700)
    skip = set(DATABASES) | {'runtime.lock', 'backup-manifest.json'} | {
        d + suffix for d in DATABASES for suffix in ('-wal', '-shm', '-journal')}
    for source in sorted(data.rglob('*')):
        relative = source.relative_to(data)
        if source.is_symlink():
            raise ValueError('El directorio de datos contiene enlaces simbólicos; revisar antes del respaldo.')
        if source.is_dir():
            (destination / relative).mkdir(mode=0o700, exist_ok=True)
        elif source.is_file() and relative.as_posix() not in skip:
            target = destination / relative
            shutil.copyfile(source, target)
            target.chmod(0o600)
        elif not source.is_file():
            raise ValueError('El directorio de datos contiene un archivo especial.')
    for relative in DATABASES:
        source, target = data / relative, destination / relative
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src:
            with closing(sqlite3.connect(target)) as dst:
                src.backup(dst)
        target.chmod(0o600)


def archive_and_verify(snapshot_root, archive):
    snapshot_root, archive = Path(snapshot_root).resolve(), Path(archive).resolve()
    media_count = verify_data(snapshot_root)
    hashes = {p.relative_to(snapshot_root).as_posix(): digest(p)
              for p in sorted(snapshot_root.rglob('*')) if p.is_file()}
    manifest = snapshot_root / 'backup-manifest.json'
    manifest.write_text(json.dumps({'sha256': hashes, 'ready_media': media_count}, indent=2) + '\n')
    manifest.chmod(0o600)
    with tarfile.open(archive, 'w:gz', compresslevel=3) as tar:
        tar.add(snapshot_root, arcname='data')
    archive.chmod(0o600)
    with tempfile.TemporaryDirectory(prefix='.restore-check-', dir=archive.parent) as folder:
        with tarfile.open(archive, 'r:gz') as tar:
            tar.extractall(folder, filter='data')
        restored = Path(folder) / 'data'
        for relative, expected in hashes.items():
            if digest(restored / relative) != expected:
                raise ValueError('La restauración no coincide con el manifiesto.')
        verify_data(restored)
    return {'files': len(hashes), 'ready_media': media_count}


def run_backup(data, backups, compose, keep=14, command=subprocess.run):
    data, backups, compose = Path(data).resolve(), Path(backups).resolve(), Path(compose).resolve()
    if backups == data or data in backups.parents:
        raise ValueError('El respaldo debe estar fuera del directorio de datos.')
    if keep < 1:
        raise ValueError('La retención debe ser al menos 1.')
    backups.mkdir(parents=True, exist_ok=True, mode=0o700)
    backups.chmod(0o700)
    prefix = ['docker', 'compose', '-f', str(compose)]
    with (backups / '.backup.lock').open('a+') as backup_lock:
        fcntl.flock(backup_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        running = command(prefix + ['ps', '--status', 'running', '--services'],
                          check=True, capture_output=True, text=True).stdout.splitlines()
        restart = 'app' in running
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        archive = backups / f'cisne-{stamp}.tar.gz'
        partial = backups / f'.cisne-{stamp}.partial'
        with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=backups) as folder:
            destination = Path(folder) / 'data'
            # finally también intenta reactivar app si stop devuelve error.
            try:
                if restart:
                    command(prefix + ['stop', '--timeout', '40', 'app'], check=True)
                with (data / 'runtime.lock').open('r+') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    snapshot(data, destination)
            finally:
                if restart:
                    command(prefix + ['start', '--wait', '--wait-timeout', '120', 'app'], check=True)
            try:
                result = archive_and_verify(destination, partial)
                partial.rename(archive)
            finally:
                partial.unlink(missing_ok=True)
        candidates = sorted(p for p in backups.iterdir()
                            if re.fullmatch(r'cisne-\d{8}T\d{12}Z\.tar\.gz', p.name)
                            and p.is_file() and not p.is_symlink())
        for old in candidates[:-keep]:
            old.unlink()
        return {'archive': str(archive), 'restore_verified': True, **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('/srv/cisne/data'))
    parser.add_argument('--backup-dir', type=Path, default=Path('/var/backups/cisne'))
    parser.add_argument('--compose', type=Path, default=Path(__file__).with_name('compose.yaml'))
    parser.add_argument('--keep', type=int, default=14)
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(run_backup(args.data_dir, args.backup_dir, args.compose, args.keep)))


if __name__ == '__main__':
    main()
