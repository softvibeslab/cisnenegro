"""Persistent, private originals and publishable derivatives for Cisne Negro CMS.

Requires Pillow; ffprobe/ffmpeg for MP4; pillow-heif is optional. No network fetches.
Images are bounded synchronous work. MP4 probing is bounded to 15 seconds; encoding
runs in one daemon worker per process, with a SQLite lease preventing duplicate
work across processes. Pending jobs survive restart. The worker retries an abandoned
lease after ten minutes. An encoding failure is visible as status='error', never as
a public original. Call retry(id) to retry a failed video, close() on shutdown.

root must be a private durable directory outside this repository. Back up the whole
directory (SQLite online backup or stop writers), not only media.sqlite. Routes,
permissions and references from published content are managed by the CMS server.
Archiving only hides an item from the active library; its URLs remain usable.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
import warnings
from datetime import date, datetime, timezone
from contextlib import contextmanager
from urllib.parse import urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError

try:
    from pillow_heif import register_heif_opener
except ImportError:
    HEIF_AVAILABLE = False
else:
    register_heif_opener()
    HEIF_AVAILABLE = True

PHOTO_LIMIT = 20 * 1024 * 1024
VIDEO_LIMIT = 100 * 1024 * 1024
PIXEL_LIMIT = 40_000_000
DURATION_LIMIT = 300
STORAGE_LIMIT = 10 * 1024 ** 3
PAGE_SIZE = 36
VIDEO_RESERVATION = 256 * 1024 * 1024
VIDEO_TIMEOUT = 180
LEASE_SECONDS = 600
ID_RE = re.compile(r"^[a-f0-9]{32}$")
IMAGE_SUFFIXES = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP',
                  '.heic': 'HEIF', '.heif': 'HEIF'}
DEFAULT_CATEGORIES = ['Cervezas', 'Cocina', 'Barra y lugar', 'Elaboración', 'Comunidad', 'Eventos', 'Marca']
EDITABLE = {'name', 'title', 'alt', 'caption', 'category', 'tags', 'source', 'source_url', 'date',
            'focal_x', 'focal_y', 'reviewed'}
SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, title TEXT NOT NULL, alt TEXT NOT NULL DEFAULT '',
 caption TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]',
 source TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '', date TEXT NOT NULL DEFAULT '',
 kind TEXT NOT NULL CHECK(kind IN ('image','video')), width INTEGER NOT NULL, height INTEGER NOT NULL,
 size INTEGER NOT NULL, hash TEXT NOT NULL UNIQUE, archived INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, status TEXT NOT NULL,
 error TEXT NOT NULL DEFAULT '', original_ext TEXT NOT NULL, web_ext TEXT NOT NULL,
 duration REAL, storage_bytes INTEGER NOT NULL DEFAULT 0, reserved_bytes INTEGER NOT NULL DEFAULT 0,
 lease_until REAL NOT NULL DEFAULT 0, lease_owner TEXT NOT NULL DEFAULT '',
 focal_x REAL NOT NULL DEFAULT 0.5, focal_y REAL NOT NULL DEFAULT 0.5,
 reviewed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS media_library ON media(archived, created_at DESC);
"""


class MediaError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = self.status_code = status


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def _text(value, field, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise MediaError(f'{field}: texto inválido o demasiado largo (máximo {limit}).')
    if any(ord(c) < 32 and c not in '\n\r\t' for c in value):
        raise MediaError(f'{field}: contiene caracteres de control.')
    return value.strip()


def _filename(value):
    name = _text(value, 'Nombre', 240)
    if not name or '/' in name or '\\' in name or name in ('.', '..') or '\n' in name or '\r' in name:
        raise MediaError('El nombre debe ser un archivo, sin rutas.')
    return name


def _metadata(patch):
    if patch is None:
        return {}
    if not isinstance(patch, dict) or set(patch) - EDITABLE:
        raise MediaError('Metadatos desconocidos o inválidos.')
    out = {}
    limits = {'title': 200, 'alt': 500, 'caption': 4000, 'category': 80, 'source': 240,
              'source_url': 2000, 'date': 40}
    for key, value in patch.items():
        if key == 'name':
            out[key] = _filename(value)
        elif key == 'tags':
            if not isinstance(value, list) or len(value) > 30:
                raise MediaError('Usa una lista de hasta 30 etiquetas.')
            out[key] = list(dict.fromkeys(_text(v, 'Etiqueta', 64) for v in value))
            out[key] = [v for v in out[key] if v]
        elif key in ('focal_x', 'focal_y'):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise MediaError('El punto focal debe estar entre 0 y 1.')
            out[key] = value
        elif key == 'reviewed':
            if not isinstance(value, bool):
                raise MediaError('reviewed debe ser booleano.')
            out[key] = int(value)
        else:
            out[key] = _text(value, key, limits[key])
    url = out.get('source_url', '')
    if url:
        try:
            parsed = urlsplit(url)
            valid = (parsed.scheme in ('https', 'http') and parsed.hostname and not parsed.username
                     and not parsed.password and not any(c.isspace() for c in url) and '\\' not in url)
            _ = parsed.port
        except ValueError:
            valid = False
        if not valid:
            raise MediaError('El enlace de origen debe ser una URL http(s) válida, sin credenciales.')
    if out.get('date'):
        try:
            value = out['date']
            date.fromisoformat(value) if len(value) == 10 else datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            raise MediaError('La fecha debe estar en formato ISO (AAAA-MM-DD).') from None
    return out


class MediaStore:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        project = Path(__file__).resolve().parents[1]
        if self.root == project or project in self.root.parents:
            raise MediaError('La biblioteca persistente debe estar fuera del repositorio.')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.originals = self.root / 'originals'
        self.derivatives = self.root / 'derivatives'
        self.incoming = self.root / 'incoming'
        for directory in (self.originals, self.derivatives, self.incoming):
            directory.mkdir(exist_ok=True, mode=0o700)
            if directory.is_symlink():
                raise MediaError('La biblioteca no permite directorios enlazados.')
        self.db_path = self.root / 'media.sqlite'
        with self._db() as db:
            db.executescript(SCHEMA)
        os.chmod(self.db_path, 0o600)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._owner = uuid.uuid4().hex
        self._worker_thread = threading.Thread(target=self._work, name='cisne-media', daemon=True)
        self._worker_thread.start()

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA busy_timeout=30000')
            db.execute('PRAGMA journal_mode=WAL')
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _item(row):
        if row is None:
            return None
        item = dict(row)
        for hidden in ('original_ext', 'web_ext', 'storage_bytes', 'reserved_bytes', 'lease_until', 'lease_owner'):
            item.pop(hidden, None)
        item['tags'] = json.loads(item['tags'])
        item['archived'] = bool(item['archived'])
        item['reviewed'] = bool(item['reviewed'])
        item['url'] = f"/cms/media/{item['id']}/file"
        item['thumbnail'] = f"/cms/media/{item['id']}/thumb"
        return item

    def get(self, id):
        if not isinstance(id, str) or not ID_RE.fullmatch(id):
            return None
        with self._db() as db:
            return self._item(db.execute('SELECT * FROM media WHERE id=?', (id,)).fetchone())

    def list(self, q='', category='', kind='', page=1, archived=False):
        q = _text(q, 'Búsqueda', 200)
        category = _text(category, 'Categoría', 80)
        if kind not in ('', 'image', 'video') or not isinstance(archived, bool):
            raise MediaError('Filtro de biblioteca inválido.')
        try:
            page = min(1_000_000, max(1, int(page)))
        except (TypeError, ValueError):
            raise MediaError('Página inválida.') from None
        conditions, args = ['archived=?'], [int(archived)]
        if q:
            escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            conditions.append("(name LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\' OR alt LIKE ? ESCAPE '\\' OR caption LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\')")
            args.extend([f'%{escaped}%'] * 5)
        if category:
            conditions.append('category=?'); args.append(category)
        if kind:
            conditions.append('kind=?'); args.append(kind)
        where = ' AND '.join(conditions)
        with self._db() as db:
            total = db.execute(f'SELECT count(*) FROM media WHERE {where}', args).fetchone()[0]
            pages = max(1, math.ceil(total / PAGE_SIZE))
            rows = db.execute(f'SELECT * FROM media WHERE {where} ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',
                              args + [PAGE_SIZE, (page - 1) * PAGE_SIZE]).fetchall()
            existing = [r[0] for r in db.execute("SELECT DISTINCT category FROM media WHERE category<>'' ORDER BY category")]
        return {'items': [self._item(r) for r in rows], 'total': total, 'page': page, 'pages': pages,
                'categories': list(dict.fromkeys(DEFAULT_CATEGORIES + existing))}

    def usage(self):
        with self._db() as db:
            row = db.execute("SELECT coalesce(sum(storage_bytes),0) bytes,coalesce(sum(reserved_bytes),0) reserved_bytes,count(*) items,sum(status='processing') processing FROM media").fetchone()
        return {'bytes': row['bytes'], 'reserved_bytes': row['reserved_bytes'], 'limit_bytes': STORAGE_LIMIT,
                'items': row['items'], 'processing': row['processing'] or 0}

    def _probe(self, path):
        executable = shutil.which('ffprobe')
        if not executable:
            raise MediaError('El servidor necesita ffprobe para validar videos.', 503)
        try:
            result = subprocess.run([executable, '-v', 'error', '-protocol_whitelist', 'file,pipe',
                                     '-show_format', '-show_streams', '-of', 'json', str(path)],
                                    capture_output=True, timeout=15, check=True)
            data = json.loads(result.stdout)
            formats = set(data.get('format', {}).get('format_name', '').split(','))
            brand = str(data.get('format', {}).get('tags', {}).get('major_brand', '')).strip()
            streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'video'
                       and not s.get('disposition', {}).get('attached_pic')]
            if not formats.intersection({'mov', 'mp4'}) or not brand or brand == 'qt' or len(streams) != 1:
                raise ValueError()
            stream = streams[0]
            width, height = int(stream['width']), int(stream['height'])
            duration = float(data['format'].get('duration') or stream.get('duration') or 0)
            if width <= 0 or height <= 0 or width * height > PIXEL_LIMIT:
                raise MediaError('El video supera el límite de 40 megapíxeles.')
            if not math.isfinite(duration) or not 0 < duration <= DURATION_LIMIT:
                raise MediaError('El video debe durar como máximo cinco minutos.')
            return width, height, duration
        except MediaError:
            raise
        except (subprocess.SubprocessError, ValueError, KeyError, TypeError, OSError):
            raise MediaError('No se pudo validar el contenido MP4.') from None

    def _image_derivatives(self, path, suffix, id):
        if suffix in ('.heic', '.heif') and not HEIF_AVAILABLE:
            raise MediaError('HEIC no está habilitado: exporta la foto como JPG o PNG.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(path) as check:
                    actual = check.format
                    if actual != IMAGE_SUFFIXES[suffix]:
                        raise MediaError('La extensión no coincide con el contenido de la imagen.')
                    if check.width * check.height > PIXEL_LIMIT:
                        raise MediaError('La imagen supera el límite de 40 megapíxeles.')
                    if getattr(check, 'is_animated', False):
                        raise MediaError('Usa una imagen fija o un video MP4; no se admiten imágenes animadas.')
                    check.verify()
                with Image.open(path) as original:
                    im = ImageOps.exif_transpose(original)
                    width, height = im.size
                    im = im.convert('RGBA' if 'A' in im.getbands() or 'transparency' in im.info else 'RGB')
                    im.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
                    directory = self.derivatives / id
                    directory.mkdir(mode=0o700)
                    im.save(directory / 'file.webp', format='WEBP', quality=84, method=4)
                    im.thumbnail((480, 480), Image.Resampling.LANCZOS)
                    if im.mode == 'RGBA':
                        bg = Image.new('RGB', im.size, (243, 237, 226)); bg.paste(im, mask=im.getchannel('A')); im = bg
                    im.save(directory / 'thumb.jpg', format='JPEG', quality=82, optimize=True)
                    return width, height
        except MediaError:
            raise
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
            raise MediaError('Imagen dañada, no admitida o demasiado grande.') from None

    def ingest(self, fileobj, filename, metadata=None):
        filename = _filename(filename)
        meta = _metadata(metadata)
        suffix = Path(filename).suffix.lower()
        if suffix not in IMAGE_SUFFIXES and suffix != '.mp4':
            raise MediaError('Formato no admitido. Usa JPG, PNG, WebP, HEIC compatible o MP4.')
        kind = 'video' if suffix == '.mp4' else 'image'
        maximum = VIDEO_LIMIT if kind == 'video' else PHOTO_LIMIT
        id = uuid.uuid4().hex
        fd, temporary = tempfile.mkstemp(prefix='upload-', suffix=suffix, dir=self.incoming)
        temporary = Path(temporary)
        committed = False
        moved_original = None
        try:
            total, digest = 0, hashlib.sha256()
            with os.fdopen(fd, 'wb') as target:
                while True:
                    chunk = fileobj.read(1024 * 1024)
                    if not chunk:
                        break
                    if not isinstance(chunk, bytes):
                        raise MediaError('La carga debe contener datos binarios.')
                    total += len(chunk)
                    if total > maximum:
                        raise MediaError('El archivo supera 100 MB de video o 20 MB de imagen.', 413)
                    digest.update(chunk); target.write(chunk)
                target.flush(); os.fsync(target.fileno())
            if not total:
                raise MediaError('El archivo está vacío.')
            sha = digest.hexdigest()
            with self._db() as db:
                existing = db.execute('SELECT * FROM media WHERE hash=?', (sha,)).fetchone()
                if existing:
                    if suffix != existing['original_ext'] and not (suffix in ('.jpg', '.jpeg') and existing['original_ext'] in ('.jpg', '.jpeg')):
                        raise MediaError('La extensión no coincide con el archivo ya registrado.')
                    return {**self._item(existing), 'duplicate': True}
            if kind == 'video':
                if not shutil.which('ffmpeg'):
                    raise MediaError('El servidor necesita ffmpeg para preparar videos.', 503)
                width, height, duration = self._probe(temporary)
                reserve, storage = VIDEO_RESERVATION, total
            else:
                width, height = self._image_derivatives(temporary, suffix, id)
                duration = None
                storage = total + sum(p.stat().st_size for p in (self.derivatives / id).iterdir())
                reserve = 0
            stamp = _now()
            values = dict(id=id, name=filename, title=Path(filename).stem, alt='', caption='', category='', tags=[],
                          source='', source_url='', date='', kind=kind, width=width, height=height, size=total,
                          hash=sha, archived=0, created_at=stamp, updated_at=stamp,
                          status='processing' if kind == 'video' else 'ready', original_ext=suffix,
                          web_ext='.mp4' if kind == 'video' else '.webp', duration=duration,
                          storage_bytes=storage, reserved_bytes=reserve, focal_x=0.5, focal_y=0.5, reviewed=0)
            values.update(meta)
            values['tags'] = json.dumps(values['tags'], ensure_ascii=False)
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT * FROM media WHERE hash=?', (sha,)).fetchone()
                if existing:
                    return {**self._item(existing), 'duplicate': True}
                used = db.execute('SELECT coalesce(sum(storage_bytes+reserved_bytes),0) FROM media').fetchone()[0]
                if used + storage + reserve > STORAGE_LIMIT:
                    raise MediaError('La biblioteca alcanzó la cuota de 10 GB, incluyendo conversiones pendientes.', 413)
                moved_original = self.originals / f'{id}{suffix}'
                os.replace(temporary, moved_original)
                db.execute(f"INSERT INTO media ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", list(values.values()))
            committed = True
            self._wake.set()
            return {**self.get(id), 'duplicate': False}
        finally:
            temporary.unlink(missing_ok=True)
            if not committed:
                if moved_original:
                    moved_original.unlink(missing_ok=True)
                shutil.rmtree(self.derivatives / id, ignore_errors=True)

    def update(self, id, patch):
        if self.get(id) is None:
            raise MediaError('Archivo no encontrado.', 404)
        values = _metadata(patch)
        if 'tags' in values:
            values['tags'] = json.dumps(values['tags'], ensure_ascii=False)
        values['updated_at'] = _now()
        with self._db() as db:
            db.execute(f"UPDATE media SET {','.join(k+'=?' for k in values)} WHERE id=?", list(values.values()) + [id])
        return self.get(id)

    def archive(self, id, archived=True):
        if not isinstance(archived, bool):
            raise MediaError('El estado archivado debe ser booleano.')
        if self.get(id) is None:
            raise MediaError('Archivo no encontrado.', 404)
        with self._db() as db:
            db.execute('UPDATE media SET archived=?,updated_at=? WHERE id=?', (int(archived), _now(), id))
        return self.get(id)

    def path(self, id, variant='file') -> Path:
        if variant not in ('file', 'thumb'):
            raise MediaError('Solo se sirven derivados; variante desconocida.', 404)
        item = self.get(id)
        if not item or item['status'] != 'ready':
            raise FileNotFoundError('El archivo todavía no está listo o no existe.')
        filename = 'thumb.jpg' if variant == 'thumb' else ('file.mp4' if item['kind'] == 'video' else 'file.webp')
        path = self.derivatives / id / filename
        if path.is_symlink() or self.derivatives not in path.resolve().parents or not path.is_file():
            raise FileNotFoundError('Derivado no encontrado.')
        return path

    def retry(self, id):
        item = self.get(id)
        if not item or item['kind'] != 'video' or item['status'] != 'error':
            raise MediaError('Solo pueden reintentarse videos que fallaron.')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT status FROM media WHERE id=?', (id,)).fetchone()
            if current['status'] != 'error':
                raise MediaError('El video ya está en proceso o listo.')
            used = db.execute('SELECT coalesce(sum(storage_bytes+reserved_bytes),0) FROM media').fetchone()[0]
            if used + VIDEO_RESERVATION > STORAGE_LIMIT:
                raise MediaError('No hay espacio para volver a preparar el video.', 413)
            db.execute("UPDATE media SET status='processing',error='',reserved_bytes=?,lease_until=0,lease_owner='' WHERE id=?", (VIDEO_RESERVATION, id))
        self._wake.set()
        return self.get(id)

    def _claim(self):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM media WHERE status='processing' AND lease_until<? ORDER BY created_at LIMIT 1", (time.time(),)).fetchone()
            if row:
                db.execute('UPDATE media SET lease_until=?,lease_owner=? WHERE id=?', (time.time() + LEASE_SECONDS, self._owner, row['id']))
            return dict(row) if row else None

    def _convert_video(self, row):
        id = row['id']
        original = self.originals / f"{id}{row['original_ext']}"
        staging = Path(tempfile.mkdtemp(prefix=f'video-{id}-', dir=self.incoming))
        try:
            ffmpeg = shutil.which('ffmpeg')
            if not ffmpeg:
                raise MediaError('ffmpeg no está disponible.', 503)
            common = [ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-protocol_whitelist', 'file,pipe']
            # Re-encoding removes arbitrary streams, subtitles, attachments and metadata.
            scale = "scale=w='min(1920,iw)':h='min(1080,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1"
            subprocess.run(common + ['-i', str(original), '-map', '0:v:0', '-an', '-sn', '-dn', '-map_metadata', '-1',
                                     '-vf', scale, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24',
                                     '-maxrate', '5M', '-bufsize', '10M', '-pix_fmt', 'yuv420p', '-r', '30',
                                     '-threads', '2', '-t', str(DURATION_LIMIT), '-movflags', '+faststart', str(staging / 'file.mp4')],
                           capture_output=True, timeout=VIDEO_TIMEOUT, check=True)
            subprocess.run(common + ['-i', str(staging / 'file.mp4'), '-frames:v', '1', '-vf', 'scale=480:-2',
                                     '-q:v', '3', '-threads', '1', str(staging / 'thumb.jpg')],
                           capture_output=True, timeout=20, check=True)
            added = sum(p.stat().st_size for p in staging.iterdir())
            if added > row['reserved_bytes']:
                raise MediaError('El derivado de video excede el espacio reservado.')
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                current = db.execute('SELECT lease_owner FROM media WHERE id=?', (id,)).fetchone()
                if not current or current['lease_owner'] != self._owner:
                    return
                target = self.derivatives / id
                if target.exists():
                    shutil.rmtree(target)
                os.replace(staging, target)
                db.execute("UPDATE media SET status='ready',error='',storage_bytes=size+?,reserved_bytes=0,lease_until=0,lease_owner='',updated_at=? WHERE id=?", (added, _now(), id))
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _work(self):
        while not self._stop.is_set():
            row = None
            try:
                row = self._claim()
                if row:
                    self._convert_video(row)
            except Exception as exc:
                if row:
                    message = str(exc) if isinstance(exc, MediaError) else 'No se pudo preparar el video. Reintenta o usa otro MP4.'
                    try:
                        with self._db() as db:
                            db.execute("UPDATE media SET status='error',error=?,reserved_bytes=0,lease_until=0,lease_owner='',updated_at=? WHERE id=? AND lease_owner=?", (message[:300], _now(), row['id'], self._owner))
                    except sqlite3.Error:
                        pass  # Lease makes the job recoverable after a process/database outage.
                self._stop.wait(1)
            if not row:
                self._wake.wait(2); self._wake.clear()

    def wait_for_idle(self, timeout=300):
        deadline = time.monotonic() + timeout
        while self.usage()['processing'] and time.monotonic() < deadline:
            self._wake.set(); time.sleep(0.1)
        return self.usage()['processing'] == 0

    def close(self, wait=True):
        self._stop.set(); self._wake.set()
        self._worker_thread.join(timeout=VIDEO_TIMEOUT + 25 if wait else 0)
