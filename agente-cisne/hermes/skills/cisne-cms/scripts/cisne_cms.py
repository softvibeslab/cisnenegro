#!/usr/bin/env python3
"""Cliente editorial limitado, stdlib, con sesión privada por perfil Hermes."""
import argparse
import hashlib
import http.client
import http.cookies
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import ssl
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

COLLECTIONS = {'barril', 'latas', 'sin_alcohol', 'comida', 'events', 'gallery', 'page', 'negocio'}
MAX_RESPONSE = 16 * 1024 * 1024
MAX_UPLOAD = 20 * 1024 * 1024
SECRET_KEYS = {'password', 'csrf', 'cookie', 'authorization', 'access_token', 'refresh_token', 'api_key'}


class ClientError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def normalize_url(raw):
    try:
        url = urllib.parse.urlsplit(raw)
        host = url.hostname
        port = url.port
        if not host or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
            raise ValueError
        loopback = host == 'localhost'
        try:
            loopback = loopback or ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
        if url.scheme != 'https' and not (url.scheme == 'http' and loopback):
            raise ValueError
        if any(c.isspace() or ord(c) < 32 for c in raw):
            raise ValueError
        authority = '[' + host + ']' if ':' in host else host
        if port is not None:
            authority += ':' + str(port)
        return url.scheme + '://' + authority
    except ValueError:
        raise ClientError('CISNE_CMS_URL debe ser un origen HTTPS, o HTTP de loopback para pruebas, sin rutas ni credenciales.') from None


def scrub(value, private_values=()):
    if isinstance(value, dict):
        return {k: ('[privado]' if k.lower() in SECRET_KEYS else scrub(v, private_values)) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, private_values) for v in value]
    if isinstance(value, str):
        for secret in private_values:
            if secret:
                value = value.replace(secret, '[privado]')
    return value


class Client:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.url = normalize_url(env.get('CISNE_CMS_URL', ''))
        self.user = env.get('CISNE_CMS_USER', '')
        self.password = env.get('CISNE_CMS_PASSWORD', '')
        if not self.user:
            raise ClientError('Falta CISNE_CMS_USER en el entorno privado del perfil.')
        if not env.get('HERMES_HOME'):
            raise ClientError('Falta HERMES_HOME: usa un perfil privado dedicado a Cisne Negro.')
        home = Path(env['HERMES_HOME']).expanduser()
        if not home.is_dir():
            raise ClientError('HERMES_HOME debe ser un directorio privado existente.')
        self.home = home.resolve()
        self.cache_dir = home / '.cisne-cms-session'
        if self.cache_dir.is_symlink():
            raise ClientError('Directorio de sesión no válido.')
        self.cache_dir.mkdir(mode=0o700, exist_ok=True)
        self.cache_dir.chmod(0o700)
        identity = hashlib.sha256((self.url + '\n' + self.user).encode()).hexdigest()[:24]
        self.cache_path = self.cache_dir / (identity + '.json')
        self.cookie = ''
        self.csrf = ''
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        self._load_cache()

    @property
    def private_values(self):
        return (self.password, self.cookie, self.csrf)

    def _load_cache(self):
        try:
            fd = os.open(self.cache_path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(fd) as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                    raise ClientError('La caché de sesión debe ser un archivo privado con modo 600.')
                value = json.loads(stream.read(10000))
            if value.get('origin') == self.url and value.get('user') == self.user:
                self.cookie = str(value.get('cookie', ''))
                self.csrf = str(value.get('csrf', ''))
                if not re.fullmatch(r'[A-Za-z0-9_-]*', self.cookie + self.csrf):
                    self.cookie = self.csrf = ''
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            raise ClientError('No se pudo leer la caché privada de sesión.') from None

    def _save_cache(self):
        value = {'origin': self.url, 'user': self.user, 'cookie': self.cookie, 'csrf': self.csrf}
        fd, temporary = tempfile.mkstemp(dir=self.cache_dir, prefix='.session-')
        try:
            with os.fdopen(fd, 'w') as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(value, stream)
            os.replace(temporary, self.cache_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _request(self, method, route, payload=None, content_type='application/json', authenticated=True):
        if not route.startswith('/cms/') or '?' in route or '#' in route or '..' in route:
            raise ClientError('Ruta de cliente no admitida.')
        headers = {'Accept': 'application/json', 'Origin': self.url, 'User-Agent': 'Cisne-Hermes/1'}
        if authenticated:
            headers['Cookie'] = 'cn_staff=' + self.cookie
            if method != 'GET':
                headers['X-CSRF-Token'] = self.csrf
        data = payload if isinstance(payload, bytes) else (json.dumps(payload, ensure_ascii=False, allow_nan=False).encode() if payload is not None else None)
        if data is not None:
            headers['Content-Type'] = content_type
        request = urllib.request.Request(self.url + route, data=data, method=method, headers=headers)
        try:
            with self.opener.open(request, timeout=45) as response:
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise ClientError('La respuesta supera el límite del cliente; consulta el CMS directamente.')
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ClientError('Respuesta CMS no válida.')
                if not authenticated:
                    cookie = http.cookies.SimpleCookie()
                    for header in response.headers.get_all('Set-Cookie', []):
                        cookie.load(header)
                    if 'cn_staff' in cookie:
                        self.cookie = cookie['cn_staff'].value
                return result
        except urllib.error.HTTPError as error:
            error.close()
            messages = {401: 'La sesión o los accesos CMS no son válidos.', 403: 'El servidor rechazó el permiso o CSRF; no se realizó la operación.', 404: 'La función o el recurso no existe en este CMS.', 409: 'El borrador cambió. Vuelve a leer y compara antes de guardar.', 429: 'El servidor limitó los intentos; espera antes de volver a autenticar.'}
            if 300 <= error.code < 400:
                message = 'Redirección bloqueada. Configura el origen HTTPS canónico sin redirecciones.'
            else:
                message = messages.get(error.code, 'El CMS rechazó la solicitud. Revisa el resultado en el panel antes de reintentar.')
            raise ClientError(message, error.code) from None
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
            raise ClientError('No se pudo confirmar la respuesta CMS. Consulta el estado antes de repetir una escritura.') from None
        except (ValueError, UnicodeError):
            raise ClientError('El CMS no devolvió JSON válido; no se repetirá la escritura automáticamente.') from None

    def authenticate(self):
        if self.cookie:
            try:
                value = self._request('GET', '/cms/api/session')
                self.csrf = value['csrf']
                self._save_cache()
                return
            except ClientError as error:
                if error.status != 401:
                    raise
                self.cookie = self.csrf = ''
        if not self.password:
            raise ClientError('Falta CISNE_CMS_PASSWORD en el entorno privado del perfil.')
        value = self._request('POST', '/cms/api/login', {'username': self.user, 'password': self.password}, authenticated=False)
        self.csrf = value.get('csrf', '')
        if not self.cookie or not self.csrf or not re.fullmatch(r'[A-Za-z0-9_-]+', self.cookie + self.csrf):
            raise ClientError('El CMS no creó una sesión válida.')
        self._save_cache()

    def state(self, include_published=False):
        return self._request('GET', '/cms/api/state' if include_published else '/cms/api/agent/content')

    def mutate(self, payload):
        operation = payload.get('operation', {})
        if not isinstance(operation, dict) or operation.get('action') not in ('create', 'update', 'delete') or operation.get('collection') not in COLLECTIONS:
            raise ClientError('Operación editorial no admitida.')
        validate_version(payload)
        return self._request('POST', '/cms/api/agent/content', payload)

    def generate_image(self, payload):
        validate_version(payload)
        if payload.get('collection') not in ('barril', 'latas'):
            raise ClientError('La imagen requiere una cerveza de barril o lata.')
        for key in ('id', 'reference_media_id'):
            validate_id(payload.get(key))
        return self._request('POST', '/cms/api/agent/images', payload)

    def image_status(self, identifier):
        validate_id(identifier)
        return self._request('GET', '/cms/api/agent/images/' + identifier)

    def image_download(self, identifier):
        job = self.image_status(identifier)
        if job.get('status') != 'ready':
            raise ClientError('La imagen todavía no está lista. Consulta image-status antes de descargarla.')
        media = job.get('media')
        if not isinstance(media, dict):
            raise ClientError('El trabajo listo no contiene un medio válido.')
        validate_id(media.get('id'))
        # Solo el ID de MediaHub determina la ruta; nunca se sigue una URL devuelta por el modelo.
        route = '/cms/media/' + media['id'] + '/file'
        request = urllib.request.Request(self.url + route, headers={
            'Accept': 'image/png,image/webp', 'Origin': self.url,
            'User-Agent': 'Cisne-Hermes/1', 'Cookie': 'cn_staff=' + self.cookie,
        }, method='GET')
        try:
            with self.opener.open(request, timeout=45) as response:
                size_header = response.headers.get('Content-Length')
                if size_header is not None and (not size_header.isdecimal() or int(size_header) > MAX_UPLOAD):
                    raise ClientError('La imagen supera el límite de descarga de 20 MB o tiene un tamaño inválido.')
                data = response.read(MAX_UPLOAD + 1)
                if len(data) > MAX_UPLOAD:
                    raise ClientError('La imagen supera el límite de descarga de 20 MB.')
                if data.startswith(b'\x89PNG\r\n\x1a\n'):
                    suffix, mime = '.png', 'image/png'
                elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
                    suffix, mime = '.webp', 'image/webp'
                else:
                    raise ClientError('El recurso no es una imagen PNG o WebP reconocible.')
                if response.headers.get_content_type() != mime:
                    raise ClientError('El tipo declarado del recurso no coincide con la imagen descargada.')
        except urllib.error.HTTPError as error:
            error.close()
            message = ('Redirección de imagen bloqueada; no se enviaron credenciales al destino.'
                       if 300 <= error.code < 400 else 'No se pudo descargar el medio privado. Revisa sesión, permisos y estado en CMS.')
            raise ClientError(message, error.code) from None
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
            raise ClientError('No se pudo completar la descarga de imagen. No se modificó el borrador.') from None

        destination = self.home / '.cisne-generated'
        if destination.is_symlink():
            raise ClientError('El directorio privado de imágenes no puede ser un enlace simbólico.')
        destination.mkdir(mode=0o700, exist_ok=True)
        destination.chmod(0o700)
        # mkstemp crea un nombre nuevo en el directorio fijo: no hay argumento de ruta de salida.
        fd, name = tempfile.mkstemp(prefix=identifier + '-', suffix=suffix, dir=destination)
        try:
            with os.fdopen(fd, 'wb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(data)
        except BaseException:
            Path(name).unlink(missing_ok=True)
            raise
        return {'ok': True, 'job_id': identifier, 'status': 'ready', 'filepath': name,
                'mime_type': mime, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                'media': {key: media[key] for key in ('id', 'title', 'alt', 'status') if key in media},
                'product': job.get('product'), 'version': job.get('version')}

    def upload(self, path, metadata):
        path = Path(path)
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_UPLOAD:
            raise ClientError('Selecciona una imagen local de hasta 20 MB, sin enlaces simbólicos.')
        if path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
            raise ClientError('La etiqueta debe ser JPG, PNG o WebP.')
        boundary = 'cisne-' + secrets.token_hex(24)
        # Nombre generado: evita inyección de cabeceras mediante el nombre del adjunto.
        filename = 'etiqueta' + path.suffix.lower()
        mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        data = ('--' + boundary + '\r\nContent-Disposition: form-data; name="metadata"\r\nContent-Type: application/json\r\n\r\n').encode()
        data += json.dumps(metadata, ensure_ascii=False, allow_nan=False).encode()
        data += ('\r\n--' + boundary + '\r\nContent-Disposition: form-data; name="file"; filename="' + filename + '"\r\nContent-Type: ' + mime + '\r\n\r\n').encode()
        data += path.read_bytes() + ('\r\n--' + boundary + '--\r\n').encode()
        return self._request('POST', '/cms/api/media', data, 'multipart/form-data; boundary=' + boundary)

    def publish(self, version, note, confirmed):
        if not confirmed:
            raise ClientError('Publicar requiere --confirm-publication después de una instrucción explícita y revisión del borrador completo.')
        validate_version({'version': version})
        return self._request('POST', '/cms/api/publish', {'version': version, 'note': note})


def validate_version(payload):
    if type(payload.get('version')) is not int or payload['version'] < 0:
        raise ClientError('Se requiere version entera leída del CMS.')


def validate_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', value):
        raise ClientError('Identificador no válido.')


def read_json(path):
    try:
        raw = sys.stdin.read(MAX_RESPONSE + 1) if path == '-' else Path(path).read_text(encoding='utf-8')
        if len(raw) > MAX_RESPONSE:
            raise ValueError
        value = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (OSError, ValueError, UnicodeError):
        raise ClientError('Se requiere un archivo JSON válido con un objeto, o - para stdin.') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('state').add_argument('--include-published', action='store_true')
    for name in ('mutate', 'generate-image'):
        commands.add_parser(name).add_argument('json_file', help='Archivo JSON o - para stdin')
    upload = commands.add_parser('media-upload')
    upload.add_argument('path')
    upload.add_argument('--metadata', help='Archivo JSON de metadatos')
    commands.add_parser('image-status').add_argument('id')
    commands.add_parser('image-download').add_argument('id')
    publish = commands.add_parser('publish')
    publish.add_argument('--version', type=int, required=True)
    publish.add_argument('--note', default='Publicación autorizada mediante agente Cisne Negro')
    publish.add_argument('--confirm-publication', action='store_true')
    args = parser.parse_args(argv)
    client = None
    try:
        client = Client()
        client.authenticate()
        if args.command == 'state':
            result = client.state(args.include_published)
        elif args.command == 'mutate':
            result = client.mutate(read_json(args.json_file))
        elif args.command == 'generate-image':
            result = client.generate_image(read_json(args.json_file))
        elif args.command == 'media-upload':
            result = client.upload(args.path, read_json(args.metadata) if args.metadata else {'category': 'cervezas', 'title': 'Etiqueta de referencia'})
        elif args.command == 'image-status':
            result = client.image_status(args.id)
        elif args.command == 'image-download':
            result = client.image_download(args.id)
        else:
            result = client.publish(args.version, args.note, args.confirm_publication)
        print(json.dumps(scrub(result, client.private_values), ensure_ascii=False, allow_nan=False))
        return 0
    except (ClientError, OSError, ValueError, KeyError, TypeError) as error:
        message = str(error) if isinstance(error, ClientError) else 'No se pudo completar la operación; revisa la configuración y el estado antes de reintentar.'
        result = {'ok': False, 'error': message}
        if isinstance(error, ClientError) and error.status:
            result['status'] = error.status
        print(json.dumps(scrub(result, client.private_values if client else (os.environ.get('CISNE_CMS_PASSWORD', ''),)), ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
