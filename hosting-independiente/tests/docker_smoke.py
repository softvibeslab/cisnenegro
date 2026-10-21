#!/usr/bin/env python3
"""Prueba una imagen local con datos efímeros; no conecta a producción ni DNS."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='cisne-independent:local')
    parser.add_argument('--context')
    parser.add_argument('--port', type=int, default=8388)
    args = parser.parse_args()
    docker = ['docker'] + (['--context', args.context] if args.context else [])
    name = 'cisne-smoke-' + uuid.uuid4().hex[:12]
    volume = name + '-data'
    temporary = 'cisne.softvibes.art'
    final = 'cisnenegro.mx'
    password = secrets.token_urlsafe(24)

    def command(*parts):
        return subprocess.run(docker + list(parts), check=True, capture_output=True, text=True).stdout.strip()

    def request(path, *, host=temporary, method='GET', data=None, headers=None):
        request_headers = {'Host': host, 'X-Forwarded-Proto': 'https'}
        request_headers.update(headers or {})
        if data is not None:
            request_headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(f'http://127.0.0.1:{args.port}' + path,
            method=method, headers=request_headers,
            data=json.dumps(data).encode() if data is not None else None)
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, response.headers, response.read()

    def healthy():
        for _ in range(60):
            try:
                if request('/healthz')[0] == 200:
                    return
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                pass
            time.sleep(.5)
        raise RuntimeError('El contenedor no pasó /healthz dentro del plazo.')

    command('volume', 'create', volume)
    try:
        with tempfile.TemporaryDirectory(prefix='cisne-docker-smoke-') as folder:
            env = Path(folder) / 'app.env'
            config = dict(CMS_ORIGIN='https://' + temporary,
                CMS_ALLOWED_ORIGINS=','.join('https://' + host for host in (temporary, final, 'www.cisnenegro.mx')),
                PUBLIC_INDEX_HOST=final, APP_BIND='0.0.0.0', APP_DATA_DIR='/var/data', PORT='8080',
                CLUB_SECRET=secrets.token_urlsafe(48), CLUB_ADMIN_TOKEN=secrets.token_urlsafe(48),
                CMS_BOOTSTRAP_USER='smoke-owner', CMS_BOOTSTRAP_PASSWORD=password)
            env.write_text(''.join(key + '=' + value + '\n' for key, value in config.items()))
            env.chmod(0o600)
            command('run', '-d', '--name', name, '--env-file', str(env),
                    '-p', f'127.0.0.1:{args.port}:8080',
                    '--mount', f'type=volume,source={volume},target=/var/data', args.image)
            healthy()
            for path in ('/', '/menu/', '/cms/', '/equipo/', '/privacidad/', '/data/menu.json',
                         '/assets/video/cisne-negro-hero-v2-720.mp4'):
                assert request(path)[0] == 200, path
            session_cookie = ''
            for host in (temporary, final):
                status, headers, body = request('/cms/api/login', host=host, method='POST',
                    headers={'Origin': 'https://' + host},
                    data={'username': 'smoke-owner', 'password': password})
                assert status == 200, (host, status)
                assert 'Secure' in headers['Set-Cookie'] and 'Domain=' not in headers['Set-Cookie']
                cookie = headers['Set-Cookie'].split(';', 1)[0]
                assert request('/admin/', host=host, headers={'Cookie': cookie})[0] == 200
                assert request('/api/admin/resumen', host=host, headers={'Cookie': cookie})[0] == 200
                if host == temporary:
                    session_cookie = cookie
            assert request('/cms/api/login', method='POST', data={},
                           headers={'Origin': 'https://externo.invalid'})[0] == 403
            assert request('/')[1]['X-Robots-Tag'] == 'noindex, nofollow'
            assert request('/', host=final)[1]['X-Robots-Tag'] == 'index, follow'
            assert b'Disallow: /\n' in request('/robots.txt')[2]
            assert request('/sitemap.xml', host=final)[0] == 200
            assert command('exec', name, 'id', '-u') == '10001'
            command('exec', name, 'python', '-c',
                    "import shutil,pathlib; assert shutil.which('ffmpeg') and shutil.which('ffprobe') and shutil.which('openssl'); "
                    "assert pathlib.Path('/app/scripts/create_team.py').is_file(); "
                    "assert pathlib.Path('/app/scripts/prepare_import.py').is_file()")
            command('restart', name)
            healthy()
            assert request('/cms/api/session', headers={'Cookie': session_cookie})[0] == 200
            print('Docker: rutas, acceso CMS/Admin en ambos dominios, orígenes, indexación, UID, herramientas y persistencia: OK')
    finally:
        subprocess.run(docker + ['rm', '-f', name], capture_output=True)
        subprocess.run(docker + ['volume', 'rm', volume], capture_output=True)


if __name__ == '__main__':
    main()
