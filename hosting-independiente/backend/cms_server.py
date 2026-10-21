"""CMS Cisne Negro. WSGI: gunicorn 'cms_server:create_app()'.

Content and media live in CMS_ROOT, outside the deployed static site.
Publishing switches a SQLite pointer in one transaction. Club data is never restored.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup
from flask import Flask, Response, g, jsonify, redirect, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

COOKIE = 'cn_staff'
LIFETIME = 12 * 3600
MEDIA_RE = re.compile(r'/cms/media/([a-zA-Z0-9_-]+)/file')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_origin(value, *, secure=False):
    """Acepta solo un origen explícito, nunca rutas, comodines o credenciales."""
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError('Origen no válido.')
    try:
        parsed = urlsplit(value)
        port = parsed.port
        if (parsed.scheme not in (('https',) if secure else ('http', 'https'))
                or not parsed.hostname or parsed.username is not None or parsed.password is not None
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment
                or not re.fullmatch(r'[A-Za-z0-9.:[\]-]+', parsed.netloc)):
            raise ValueError('Origen no válido.')
        host = parsed.hostname.lower()
        if ':' in host:
            host = '[' + host + ']'
        if port is not None and port != (443 if parsed.scheme == 'https' else 80):
            host += ':' + str(port)
        return parsed.scheme + '://' + host
    except (ValueError, TypeError) as exc:
        raise ValueError('Origen no válido.') from exc


def public_metadata(html, public_host, path):
    """Adapta SEO al dominio final sin escribir en publicaciones ni borradores."""
    origin = 'https://' + public_host
    canonical = origin + path.removesuffix('index.html')
    own_hosts = {public_host, 'cisnenegro.mx', 'www.cisnenegro.mx',
                 'cisne.softvibes.art', 'cisnenegro.softvibes.art'}

    def own_url(value, *, relative=False):
        if not isinstance(value, str):
            return value
        try:
            parsed = urlsplit(value)
            owned = (parsed.scheme in ('http', 'https', '') and parsed.netloc in own_hosts)
            if not owned and not (relative and value.startswith('/') and not value.startswith('//')):
                return value
            return urlunsplit(('https', public_host, parsed.path or '/', parsed.query, parsed.fragment))
        except ValueError:
            return value

    url_fields = {'url', '@id', 'image', 'logo', 'menu', 'contentUrl', 'thumbnailUrl', 'embedUrl'}

    def linked_urls(value, field=''):
        if isinstance(value, dict):
            return {key: linked_urls(item, key) for key, item in value.items()}
        if isinstance(value, list):
            return [linked_urls(item, field) for item in value]
        return own_url(value, relative=True) if field in url_fields else value

    soup = BeautifulSoup(html, 'html.parser')
    if soup.head is None:
        return html
    links = soup.select('link[rel="canonical"]')
    link = links[0] if links else soup.new_tag('link', rel='canonical')
    link['href'] = canonical
    if not links:
        soup.head.append(link)
    for duplicate in links[1:]:
        duplicate.decompose()
    for node in soup.select('meta[property="og:url"]'):
        node['content'] = canonical
    for node in soup.select('meta[property="og:image"], meta[property="og:image:secure_url"], meta[name="twitter:image"]'):
        node['content'] = own_url(node.get('content', ''), relative=True)
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            content = json.loads(node.string or '')
        except (ValueError, TypeError):
            continue
        node.string = encoded(linked_urls(content)).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return str(soup)


def create_app(config=None):
    from cms_content import initial_document, editor_fields, validate_document, render_document
    from cms_media import MediaStore
    app = Flask(__name__, static_folder=None)
    app.config.update(
        CMS_ROOT=os.environ.get('CMS_ROOT', '/var/lib/cisnenegro-cms'),
        CMS_SITE=os.environ.get('CMS_SITE', str(Path(__file__).resolve().parents[1] / 'sitio')),
        CMS_ORIGIN=os.environ.get('CMS_ORIGIN', 'https://cisnenegro.mx'),
        CMS_ALLOWED_ORIGINS=os.environ.get('CMS_ALLOWED_ORIGINS', ''),
        PUBLIC_INDEX_HOST=os.environ.get('PUBLIC_INDEX_HOST', ''),
        CMS_DEV=os.environ.get('CMS_DEV', '') == '1',
        STAFF_TOKEN=os.environ.get('CLUB_ADMIN_TOKEN', ''),
        CLUB_URL=os.environ.get('CMS_CLUB_URL', 'http://127.0.0.1:8790'),
        MAX_CONTENT_LENGTH=105 * 1024 * 1024, MAX_FORM_MEMORY_SIZE=512 * 1024, MAX_FORM_PARTS=12,
    )
    if config:
        app.config.update(config)
    origin = normalize_origin(app.config['CMS_ORIGIN'], secure=not app.config['CMS_DEV'])
    configured = app.config['CMS_ALLOWED_ORIGINS']
    if not isinstance(configured, str):
        raise ValueError('CMS_ALLOWED_ORIGINS debe ser una lista separada por comas.')
    allowed_origins = frozenset(normalize_origin(item.strip(), secure=not app.config['CMS_DEV'])
        for item in (configured.split(',') if configured else [origin]))
    if origin not in allowed_origins:
        raise ValueError('CMS_ALLOWED_ORIGINS debe incluir CMS_ORIGIN.')
    app.config['CMS_ORIGIN'] = origin
    public_host = app.config['PUBLIC_INDEX_HOST']
    if not isinstance(public_host, str) or (public_host and (len(public_host) > 253
            or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+'
                                r'[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?', public_host)
            or 'https://' + public_host not in allowed_origins)):
        raise ValueError('PUBLIC_INDEX_HOST debe ser un hostname DNS de los orígenes HTTPS permitidos.')
    root = Path(app.config['CMS_ROOT']).resolve()
    site = Path(app.config['CMS_SITE']).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o750)
    dbpath = root / 'cms.sqlite'
    media = MediaStore(root / 'media')
    app.extensions['cms_media'] = media
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    def render_snapshot(doc, *, preview=False, revision=None):
        focal = {}
        for mid in set(MEDIA_RE.findall(encoded(doc))):
            item = media.get(mid)
            if item:
                focal['/cms/media/' + mid + '/file'] = {'x': item['focal_x'], 'y': item['focal_y']}
        return render_document(doc, site, preview=preview, revision=revision, media_focal=focal)

    @contextmanager
    def db():
        con = sqlite3.connect(dbpath, timeout=20)
        con.row_factory = sqlite3.Row
        con.execute('pragma foreign_keys=on')
        try:
            with con:
                yield con
        finally:
            con.close()

    with db() as con:
        con.executescript('''
          pragma journal_mode=wal;
          create table if not exists users(id integer primary key, username text unique not null,
            name text not null, password text not null, role text not null check(role in ('owner','editor')),
            active integer not null default 1, created_at text not null);
          create table if not exists sessions(token text primary key, user_id integer references users(id),
            csrf text not null, expires integer not null);
          create table if not exists attempts(key text not null, at integer not null);
          create index if not exists attempts_key on attempts(key,at);
          create table if not exists draft(id integer primary key check(id=1),version integer not null,
            data text not null,updated_at text not null,author text not null);
          create table if not exists revisions(id integer primary key autoincrement, data text not null,
            output text not null,created_at text not null,author text not null,note text not null);
          create table if not exists settings(key text primary key,value text not null);
          create table if not exists activity(id integer primary key,actor text not null,action text not null,
            created_at text not null);
        ''')
        if not con.execute('select 1 from draft').fetchone():
            doc = validate_document(initial_document(site))
            con.execute('insert into draft values(1,1,?,?,?)', (encoded(doc), now(), 'Importación inicial'))
            cur = con.execute('insert into revisions(data,output,created_at,author,note) values(?,?,?,?,?)',
                (encoded(doc), '{}', now(), 'Sistema', 'Contenido inicial del sitio'))
            rid = cur.lastrowid
            output = render_snapshot(doc, revision=rid)
            con.execute('update revisions set output=? where id=?', (encoded(output), rid))
            con.execute('insert into settings values(?,?)', ('published', str(rid)))

    def user_public(row):
        return {k: row[k] for k in ('id', 'username', 'name', 'role', 'active')}

    def audit(con, action):
        con.execute('insert into activity(actor,action,created_at) values(?,?,?)',
                    (g.user['name'] if getattr(g, 'user', None) else 'Sistema', action, now()))

    def fail(message, status=400):
        return jsonify(error=message), status

    def owner():
        return g.user and g.user['role'] == 'owner'

    def body():
        if request.content_length and request.content_length > 2 * 1024 * 1024:
            raise ValueError('Los datos de contenido superan el límite permitido.')
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError('Se esperaba un objeto JSON.')
        return data

    def published(con):
        return int(con.execute("select value from settings where key='published'").fetchone()[0])

    def revision(con, rid=None):
        return con.execute('select * from revisions where id=?', (rid or published(con),)).fetchone()

    def media_uses(mid, include_draft=True):
        needle = '/cms/media/' + mid + '/file'
        aliases = {needle}
        mapping_file = root / 'media-map.json'
        if mapping_file.exists():
            mapping = json.loads(mapping_file.read_text())
            for path, mapped_id in mapping.items():
                if mapped_id == mid and '/assets/' in path:
                    aliases.add('/assets/' + path.split('/assets/', 1)[1])
                    aliases.add(Path(path).name)
        uses = []
        def scan(value, path, label):
            if isinstance(value, dict):
                for k, v in value.items(): scan(v, path + '.' + k if path else k, label)
            elif isinstance(value, list):
                for i, v in enumerate(value): scan(v, f'{path}.{i}', label)
            elif isinstance(value, str) and value.split('?', 1)[0] in aliases:
                uses.append({'path': path, 'label': label})
        with db() as con:
            current = published(con)
            if include_draft:
                scan(json.loads(con.execute('select data from draft').fetchone()[0]), '', 'Borrador')
            for r in con.execute('select id,data from revisions order by id desc'):
                scan(json.loads(r['data']), '', f'Publicación {r["id"]}' + (' · actual' if r['id'] == current else ' · historial'))
        return uses

    def verify_media(doc):
        for mid in set(MEDIA_RE.findall(encoded(doc))):
            item = media.get(mid)
            if not item or item.get('status', 'ready') != 'ready':
                raise ValueError('Hay un archivo que no está listo. Revisa MediaHub antes de publicar.')
            media.path(mid, 'file')

    @app.before_request
    def authenticate():
        g.user, g.session = None, None
        token = request.cookies.get(COOKIE, '')
        if token:
            with db() as con:
                row = con.execute('''select s.csrf,s.expires,u.* from sessions s join users u on u.id=s.user_id
                   where s.token=? and s.expires>? and u.active=1''', (digest(token), int(time.time()))).fetchone()
                if row:
                    g.user, g.session = user_public(row), {'csrf': row['csrf'], 'expires': row['expires']}
        protected = request.path.startswith(('/cms/api/', '/cms/preview', '/api/admin/'))
        if protected and request.path != '/cms/api/login':
            if not g.user:
                return fail('Inicia sesión con tu cuenta del equipo.', 401)
            if request.path.startswith('/api/admin/') and not owner():
                return fail('Tu cuenta no tiene acceso a la operación del Pasaporte.', 403)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('Origin')
            if origin:
                try:
                    incoming_origin = normalize_origin(origin)
                    permitted = incoming_origin in allowed_origins
                    # Cada dominio usa sus propias cookies. Aun entre dominios admitidos,
                    # el navegador debe escribir en su mismo origen, sin confiar en Host solo.
                    if len(allowed_origins) > 1:
                        permitted = permitted and incoming_origin == normalize_origin(request.host_url)
                except ValueError:
                    permitted = False
                if not permitted:
                    return fail('Origen de solicitud no permitido.', 403)
            if protected and request.path != '/cms/api/login':
                supplied = request.headers.get('X-CSRF-Token', '')
                if not g.session or not hmac.compare_digest(g.session['csrf'], supplied):
                    return fail('La sesión de edición cambió. Recarga el panel.', 403)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        indexable = (public_host and request.host == public_host and request.scheme == 'https'
            and response.status_code == 200 and request.path in (
                '/', '/index.html', '/menu/', '/menu/index.html', '/privacidad/', '/privacidad/index.html'))
        response.headers['X-Robots-Tag'] = 'index, follow' if indexable else 'noindex, nofollow'
        if indexable and response.mimetype == 'text/html':
            response.direct_passthrough = False
            html = response.get_data(as_text=True)
            html = re.sub(r'(<meta\b(?=[^>]*\bname\s*=\s*[\"\']robots[\"\'])'
                          r'[^>]*\bcontent\s*=\s*)([\"\'])(.*?)\2',
                          lambda match: match[1] + match[2] + 'index, follow' + match[2], html, flags=re.I)
            response.set_data(public_metadata(html, public_host, request.path))
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Cache-Control'] = 'no-store' if request.path.startswith(('/cms', '/api/', '/admin', '/equipo', '/healthz')) else 'no-cache'
        if request.path.startswith('/cms') and not request.path.startswith('/cms/preview'):
            response.headers['Content-Security-Policy'] = ("default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob:; "
                "media-src 'self' blob:; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; "
                "object-src 'none'; base-uri 'self'; form-action 'self'")
        return response

    @app.errorhandler(Exception)
    def errors(exc):
        if isinstance(exc, ValueError): return fail(str(exc), getattr(exc, 'status_code', 400))
        if isinstance(exc, FileNotFoundError): return fail('Archivo no disponible.', 404)
        if isinstance(exc, HTTPException): return fail('Solicitud no admitida.' if exc.code != 413 else 'El archivo supera el límite de carga.', exc.code)
        app.logger.exception('CMS operation failed')
        return fail('No fue posible completar la operación. Inténtalo de nuevo.', 500)

    @app.get('/cms')
    def slash(): return redirect('/cms/', 308)

    @app.get('/cms/')
    def panel(): return send_from_directory(site / 'cms', 'index.html')

    @app.get('/cms/<name>')
    def static_cms(name):
        if name not in ('cms.css', 'cms.js', 'agent.css', 'agent.js'): return fail('No encontrado.', 404)
        return send_from_directory(site / 'cms', name)

    @app.get('/cms/auth/owner')
    def check_owner():
        return ('', 204) if owner() else ('', 403 if g.user else 401)

    @app.get('/cms/api/session')
    def session_info(): return jsonify(user=g.user, csrf=g.session['csrf'])

    @app.post('/cms/api/login')
    def login():
        b = body()
        username, password = str(b.get('username', '')).strip(), str(b.get('password', ''))
        if len(username) > 80 or len(password) > 200: return fail('Acceso no válido.', 401)
        key = digest(request.remote_addr or '')
        with db() as con:
            con.execute('delete from attempts where at<?', (int(time.time()) - 600,))
            if con.execute('select count(*) from attempts where key=?', (key,)).fetchone()[0] >= 15:
                return fail('Demasiados intentos. Espera diez minutos.', 429)
            con.execute('insert into attempts values(?,?)', (key, int(time.time())))
            u = con.execute('select * from users where username=? and active=1', (username,)).fetchone()
            good = False
            if u:
                saved = u['password']
                if saved.startswith('legacy:'):
                    hashed = saved[7:]
                    if hashed.startswith('$apr1$'):
                        salt = hashed.split('$')[2]
                        result = subprocess.run(['openssl', 'passwd', '-apr1', '-salt', salt, '-stdin'],
                            input=password + '\n', text=True, capture_output=True, timeout=5)
                        good = result.returncode == 0 and hmac.compare_digest(result.stdout.strip(), hashed)
                    elif hashed.startswith(('$2y$', '$2b$', '$2a$')):
                        import bcrypt
                        good = len(password.encode()) <= 72 and bcrypt.checkpw(password.encode(), hashed.encode())
                else:
                    good = check_password_hash(saved, password)
            else:
                hashlib.scrypt(password.encode(), salt=b'cn-invalid-account', n=16384, r=8, p=1)
            if not good: return fail('Usuario o contraseña incorrectos.', 401)
            if u['password'].startswith('legacy:'):
                con.execute('update users set password=? where id=?', (generate_password_hash(password), u['id']))
            con.execute('delete from attempts where key=?', (key,))
            token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
            con.execute('delete from sessions where expires<?', (int(time.time()),))
            con.execute('insert into sessions values(?,?,?,?)', (digest(token), u['id'], csrf, int(time.time()) + LIFETIME))
            g.user = user_public(u)
            audit(con, 'Inicio de sesión')
        response = jsonify(user=g.user, csrf=csrf)
        response.set_cookie(COOKIE, token, max_age=LIFETIME, httponly=True, secure=not app.config['CMS_DEV'], samesite='Lax', path='/')
        return response

    @app.post('/cms/api/logout')
    def logout():
        with db() as con: con.execute('delete from sessions where token=?', (digest(request.cookies.get(COOKIE, '')),))
        response = jsonify(ok=True)
        response.delete_cookie(COOKIE, path='/')
        return response

    @app.get('/cms/api/state')
    def state():
        with db() as con:
            row = con.execute('select * from draft').fetchone()
            doc = json.loads(row['data'])
            pr = published(con)
            live_document = json.loads(revision(con, pr)['data'])
        count = len(doc['menu']['barril']) + len(doc['menu']['latas']) + len(doc['menu']['sin_alcohol']) + sum(len(c['items']) for c in doc['menu']['comida'])
        usage = media.usage()
        return jsonify(document=doc, published_document=live_document, version=row['version'], published_version=pr,
            schema=editor_fields(doc), user=g.user,
            summary={'products': count, 'media': usage['items'], 'events': len(doc.get('events', [])),
                     'storage_bytes': usage['bytes'], 'storage_limit': usage['limit_bytes'], 'media_processing': usage['processing']})

    @app.put('/cms/api/draft')
    def save_draft():
        b = body()
        doc = validate_document(b.get('document'))
        with db() as con:
            con.execute('begin immediate')
            row = con.execute('select version from draft').fetchone()
            if b.get('version') != row[0]: return fail('Otra persona guardó cambios. Recarga antes de continuar.', 409)
            ver = row[0] + 1
            con.execute('update draft set version=?,data=?,updated_at=?,author=? where id=1', (ver, encoded(doc), now(), g.user['name']))
            audit(con, 'Borrador guardado')
        return jsonify(version=ver, document=doc, schema=editor_fields(doc))

    @app.post('/cms/api/publish')
    def publish():
        if not owner(): return fail('Solo el propietario puede publicar.', 403)
        b = body()
        with db() as con:
            con.execute('begin immediate')
            draft = con.execute('select * from draft').fetchone()
            if b.get('version') != draft['version']: return fail('El borrador cambió. Recarga antes de publicar.', 409)
            doc = validate_document(json.loads(draft['data']))
            verify_media(doc)
            cur = con.execute('insert into revisions(data,output,created_at,author,note) values(?,?,?,?,?)',
                (encoded(doc), '{}', now(), g.user['name'], str(b.get('note', 'Actualización de contenido'))[:300]))
            rid = cur.lastrowid
            output = render_snapshot(doc, revision=rid)
            con.execute('update revisions set output=? where id=?', (encoded(output), rid))
            con.execute("update settings set value=? where key='published'", (str(rid),))
            audit(con, f'Publicación {rid}')
        return jsonify(ok=True, version=draft['version'], published_version=rid)

    @app.get('/cms/api/revisions')
    def revisions():
        with db() as con:
            current = published(con)
            rows = [dict(r) | {'current': r['id'] == current} for r in con.execute('select id,created_at,author,note from revisions order by id desc limit 100')]
        return jsonify(items=rows)

    @app.post('/cms/api/restore')
    def restore():
        if not owner(): return fail('Solo el propietario puede recuperar versiones.', 403)
        b = body()
        with db() as con:
            con.execute('begin immediate')
            d = con.execute('select version from draft').fetchone()[0]
            if b.get('version') != d: return fail('El borrador cambió. Recarga antes de continuar.', 409)
            r = con.execute('select data from revisions where id=?', (b.get('id'),)).fetchone()
            if not r: return fail('Versión no encontrada.', 404)
            con.execute('update draft set data=?,version=?,author=?,updated_at=? where id=1', (r[0], d + 1, g.user['name'], now()))
            audit(con, f'Versión {b.get("id")} recuperada como borrador')
        return jsonify(version=d + 1, document=json.loads(r[0]))

    @app.get('/cms/api/media')
    def media_list():
        return jsonify(media.list(q=request.args.get('q', '')[:200], category=request.args.get('category', '')[:100],
            kind=request.args.get('kind', ''), page=max(1, int(request.args.get('page', 1))), archived=request.args.get('archived') == 'true'))

    @app.post('/cms/api/media')
    def media_upload():
        f = request.files.get('file')
        if not f: return fail('Selecciona un archivo.')
        metadata = json.loads(request.form.get('metadata', '{}'))
        if not isinstance(metadata, dict): raise ValueError('Metadatos no válidos.')
        item = media.ingest(f.stream, f.filename or 'archivo', metadata)
        with db() as con: audit(con, 'Archivo incorporado a MediaHub')
        return jsonify(item=item, **item), 201

    @app.patch('/cms/api/media/<mid>')
    def update_media(mid):
        item = media.update(mid, body())
        with db() as con: audit(con, 'Ficha multimedia actualizada')
        return jsonify(item=item, **item)

    @app.post('/cms/api/media/<mid>/archive')
    def archive_media(mid):
        archived = body().get('archived', True)
        if not isinstance(archived, bool): raise ValueError('Estado no válido.')
        item = media.archive(mid, archived)
        with db() as con: audit(con, 'Archivo archivado' if archived else 'Archivo recuperado')
        return jsonify(item=item, **item)

    @app.get('/cms/api/media/<mid>/usage')
    def usage_media(mid): return jsonify(uses=media_uses(mid))

    @app.get('/cms/api/media/storage')
    def media_storage(): return jsonify(media.usage())

    @app.post('/cms/api/media/<mid>/retry')
    def retry_media(mid):
        item = media.retry(mid)
        return jsonify(item=item, **item)

    @app.get('/cms/media/<mid>/<variant>')
    def media_file(mid, variant):
        if variant not in ('file', 'thumb'): return fail('No encontrado.', 404)
        if not g.user and not media_uses(mid, include_draft=False): return fail('No encontrado.', 404)
        path = media.path(mid, variant)
        response = send_file(path, conditional=True, max_age=0)
        response.headers['Content-Disposition'] = 'inline'
        return response

    @app.get('/cms/api/users')
    def users():
        if not owner(): return fail('Acceso reservado al propietario.', 403)
        with db() as con: items = [user_public(u) for u in con.execute('select * from users order by id')]
        return jsonify(items=items)

    @app.post('/cms/api/users')
    def add_user():
        if not owner(): return fail('Acceso reservado al propietario.', 403)
        b = body()
        username, password = str(b.get('username', '')).strip(), str(b.get('password', ''))
        name, role = str(b.get('name', '')).strip(), b.get('role', 'editor')
        if not re.fullmatch(r'[a-zA-Z0-9_.@-]{3,60}', username) or not name or len(name) > 80 or role not in ('owner', 'editor'):
            raise ValueError('Revisa nombre, usuario y rol.')
        if len(password) < 12 or len(password) > 200: raise ValueError('La contraseña debe tener entre 12 y 200 caracteres.')
        with db() as con:
            con.execute('begin immediate')
            if con.execute('select count(*) from users where active=1').fetchone()[0] >= 3: return fail('El panel admite tres cuentas activas.')
            if con.execute('select 1 from users where username=?', (username,)).fetchone(): return fail('Ese usuario ya existe.')
            cur = con.execute('insert into users(username,name,password,role,created_at) values(?,?,?,?,?)',
                (username, name, generate_password_hash(password), role, now()))
            audit(con, 'Cuenta de equipo creada')
        return jsonify(ok=True, id=cur.lastrowid), 201

    @app.patch('/cms/api/users/<int:uid>')
    def update_user(uid):
        if not owner(): return fail('Acceso reservado al propietario.', 403)
        b = body()
        with db() as con:
            con.execute('begin immediate')
            u = con.execute('select * from users where id=?', (uid,)).fetchone()
            if not u: return fail('Cuenta no encontrada.', 404)
            name, role, active = str(b.get('name', u['name'])).strip(), b.get('role', u['role']), b.get('active', bool(u['active']))
            if role not in ('owner', 'editor') or not name or len(name) > 80 or active not in (True, False, 0, 1): raise ValueError('Datos de cuenta no válidos.')
            if u['role'] == 'owner' and u['active'] and (not active or role != 'owner'):
                if con.execute("select count(*) from users where active=1 and role='owner' and id!=?", (uid,)).fetchone()[0] == 0:
                    return fail('Debe conservarse al menos un propietario activo.')
            if active and not u['active'] and con.execute('select count(*) from users where active=1').fetchone()[0] >= 3: return fail('El panel admite tres cuentas activas.')
            password = u['password']
            if b.get('password'):
                if not 12 <= len(str(b['password'])) <= 200: raise ValueError('La contraseña debe tener entre 12 y 200 caracteres.')
                password = generate_password_hash(str(b['password']))
            con.execute('update users set name=?,role=?,active=?,password=? where id=?', (name, role, int(active), password, uid))
            if not active or role != u['role'] or password != u['password']:
                con.execute('delete from sessions where user_id=?', (uid,))
            audit(con, 'Cuenta de equipo actualizada')
        return jsonify(ok=True)

    @app.get('/cms/api/activity')
    def activity():
        with db() as con: items = [dict(r) for r in con.execute('select actor,action,created_at from activity order by id desc limit 80')]
        return jsonify(items=items)

    def public_file(name):
        version = request.args.get('v')
        if version is not None and not version.isdigit(): return fail('Versión no válida.', 404)
        with db() as con: r = revision(con, int(version) if version else None)
        if not r: return fail('Versión no encontrada.', 404)
        data = json.loads(r['output']).get(name)
        if data is None: return fail('Página no encontrada.', 404)
        return Response(data, mimetype='application/json' if name.endswith('.json') else 'text/html')

    @app.get('/')
    @app.get('/index.html')
    def home(): return public_file('index.html')

    @app.get('/menu')
    def menu_slash(): return redirect('/menu/', 308)

    @app.get('/menu/')
    @app.get('/menu/index.html')
    def menu_page(): return public_file('menu/index.html')

    @app.get('/data/menu.json')
    def menu_json(): return public_file('data/menu.json')

    @app.get('/cms/preview/')
    @app.get('/cms/preview/menu/')
    @app.get('/cms/preview/data/menu.json')
    def preview():
        with db() as con: doc = json.loads(con.execute('select data from draft').fetchone()[0])
        out = render_snapshot(doc, preview=True)
        name = 'data/menu.json' if request.path.endswith('.json') else 'menu/index.html' if '/menu/' in request.path else 'index.html'
        return Response(out[name], mimetype='application/json' if name.endswith('.json') else 'text/html')

    @app.route('/api/admin/<path:tail>', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def club_proxy(tail):
        if not owner(): return fail('Acceso reservado al propietario.', 403)
        if not re.fullmatch(r'[a-zA-Z0-9_./-]+', tail) or '..' in tail: return fail('Ruta no válida.', 404)
        raw = request.get_data()
        if len(raw) > 20000: return fail('Solicitud demasiado grande.', 413)
        query = '?' + request.query_string.decode() if request.query_string else ''
        headers = {'Content-Type': 'application/json', 'X-Cisne-Staff-Token': app.config['STAFF_TOKEN']}
        req = urllib.request.Request(app.config['CLUB_URL'] + '/api/admin/' + tail + query,
            data=raw or None, headers=headers, method=request.method)
        try:
            with urllib.request.urlopen(req, timeout=15) as result:
                payload, status, ctype = result.read(), result.status, result.headers.get('Content-Type', 'application/json')
        except urllib.error.HTTPError as e:
            payload, status, ctype = e.read(), e.code, e.headers.get('Content-Type', 'application/json')
        if request.method != 'GET' and status < 400:
            with db() as con: audit(con, 'Operación del Pasaporte: ' + request.method + ' ' + tail.split('/')[0])
        return Response(payload, status=status, content_type=ctype)

    @app.get('/admin')
    def admin_slash(): return redirect('/admin/', 308)

    @app.get('/admin/')
    @app.get('/admin/index.html')
    def admin_panel():
        if not g.user: return redirect('/cms/?next=/admin/')
        if not owner(): return fail('Acceso reservado al propietario.', 403)
        return send_from_directory(site / 'admin', 'index.html')

    if app.config['CMS_DEV']:
        @app.get('/assets/<path:filename>')
        def dev_assets(filename): return send_from_directory(site / 'assets', filename)

    app.extensions['cms_db'] = db
    from agent_content import register_agent_content
    register_agent_content(app, db, body, audit, now, encoded)
    from agent_runtime import register_agent_runtime
    register_agent_runtime(app, db, body, audit, now, encoded)
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bootstrap-htpasswd')
    parser.add_argument('--dev-user')
    parser.add_argument('--port', type=int, default=8795)
    args = parser.parse_args()
    app = create_app()
    with app.extensions['cms_db']() as con:
        if args.bootstrap_htpasswd:
            if con.execute('select count(*) from users').fetchone()[0]:
                print('Cuentas existentes conservadas.')
            else:
                records = Path(args.bootstrap_htpasswd).read_text().strip().splitlines()
                for line in records[:3]:
                    username, hashed = line.split(':', 1)
                    if not hashed.startswith(('$apr1$', '$2y$', '$2b$', '$2a$')): raise ValueError('Formato de contraseña no admitido.')
                    con.execute('insert into users(username,name,password,role,created_at) values(?,?,?,?,?)',
                        (username, 'Propietario', 'legacy:' + hashed, 'owner', now()))
                print('Acceso del equipo importado; credenciales conservadas.')
            return
        if args.dev_user:
            pw = os.environ.get('CMS_DEV_PASSWORD', '')
            if not app.config['CMS_DEV'] or len(pw) < 12: raise ValueError('Solo desarrollo con contraseña segura definida.')
            con.execute('insert or ignore into users(username,name,password,role,created_at) values(?,?,?,?,?)',
                        (args.dev_user, 'Propietario de pruebas', generate_password_hash(pw), 'owner', now()))
    app.run(host='127.0.0.1', port=args.port, threaded=True, debug=False)


if __name__ == '__main__':
    main()
