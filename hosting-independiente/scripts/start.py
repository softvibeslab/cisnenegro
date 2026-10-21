#!/usr/bin/env python3
"""Arranca la copia independiente. Las credenciales de prueba solo se crean en local."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
import urllib.request

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'backend'))


def private_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def bind_host(production):
    value = os.environ.get('APP_BIND', '0.0.0.0' if production else '127.0.0.1')
    if value not in ('127.0.0.1', '0.0.0.0'):
        raise ValueError('APP_BIND debe ser 127.0.0.1 o 0.0.0.0.')
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--production', action='store_true')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8088')))
    parser.add_argument('--data-dir', type=Path)
    args = parser.parse_args()
    production = args.production
    try:
        bind = bind_host(production)
    except ValueError as exc:
        parser.error(str(exc))
    if production and not (args.data_dir or os.environ.get('APP_DATA_DIR')):
        parser.error('Producción requiere APP_DATA_DIR en un volumen persistente fuera del código.')
    data = (args.data_dir or Path(os.environ.get('APP_DATA_DIR', str(BASE.parent / '.hosting-independiente-local')))).expanduser().resolve()
    if data == BASE or BASE in data.parents:
        parser.error('Los datos deben estar fuera de la carpeta del paquete.')
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = open(data / 'runtime.lock', 'a+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error('Esta carpeta de datos ya está en uso por otra instancia.')
    origin = os.environ.get('CMS_ORIGIN', f'http://127.0.0.1:{args.port}').rstrip('/')
    if production and not origin.startswith('https://'):
        parser.error('Producción requiere CMS_ORIGIN=https://dominio-definitivo.')
    credentials_path = data / 'credenciales-locales.json'
    if production:
        secret, admin_token = os.environ.get('CLUB_SECRET', ''), os.environ.get('CLUB_ADMIN_TOKEN', '')
        if min(len(secret), len(admin_token)) < 32:
            parser.error('Producción requiere CLUB_SECRET y CLUB_ADMIN_TOKEN aleatorios de al menos 32 caracteres.')
        credentials = None
    else:
        if not credentials_path.exists():
            private_json(credentials_path, {
                'cms_usuario': 'admin-local', 'cms_password': secrets.token_urlsafe(18),
                'equipo_usuario': 'equipo-local', 'equipo_pin': f'{secrets.randbelow(10**6):06d}',
                'mesero_usuario': 'mesero-local', 'mesero_pin': f'{secrets.randbelow(10**6):06d}',
                'club_secret': secrets.token_urlsafe(48), 'admin_token': secrets.token_urlsafe(48),
            })
        credentials = json.loads(credentials_path.read_text())
        secret, admin_token = credentials['club_secret'], credentials['admin_token']
        access_path = data / 'ACCESOS-LOCALES.txt'
        access_text = (f'CISNE NEGRO · CUENTAS EXCLUSIVAS DE ESTA COPIA LOCAL\n\n'
                       f'Inicio: {origin}/\nMenú: {origin}/menu/\n'
                       f'CMS: {origin}/cms/#editor\nAdmin: {origin}/admin/\n'
                       f'Usuario CMS/Admin: {credentials["cms_usuario"]}\n'
                       f'Contraseña CMS/Admin: {credentials["cms_password"]}\n\n'
                       f'Equipo: {origin}/equipo/\nUsuario administrador: {credentials["equipo_usuario"]}\n'
                       f'PIN administrador: {credentials["equipo_pin"]}\n'
                       f'Usuario mesero: {credentials["mesero_usuario"]}\nPIN mesero: {credentials["mesero_pin"]}\n\n'
                       'Estas cuentas no pertenecen al sistema publicado. No subirlas al hosting.\n')
        fd = os.open(access_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(access_text)
    club_port = int(os.environ.get('CLUB_PORT', str(args.port + 1000)))
    os.environ.update({
        'CMS_SITE': str(BASE / 'sitio'), 'CMS_ROOT': str(data / 'cms'),
        'CMS_ORIGIN': origin, 'CMS_DEV': '0' if production else '1',
        'CMS_CLUB_URL': f'http://127.0.0.1:{club_port}',
        'CLUB_DB': str(data / 'club.db'), 'CLUB_SECRET': secret, 'CLUB_ADMIN_TOKEN': admin_token,
        'CLUB_PORT': str(club_port), 'CLUB_HOST': '127.0.0.1',
        'CLUB_COOKIE_PATH': '/api', 'CLUB_COOKIE_SECURE': '1' if production else '0',
        'CLUB_MENU': str(BASE / 'sitio/data/menu.json'), 'CLUB_CMS_DB': str(data / 'cms/cms.sqlite'),
    })
    from cms_server import create_app, now
    from werkzeug.security import generate_password_hash
    import club_server
    cms = create_app()
    with cms.extensions['cms_db']() as con:
        if credentials:
            con.execute('insert or ignore into users(username,name,password,role,created_at) values(?,?,?,?,?)',
                        (credentials['cms_usuario'], 'Administrador local', generate_password_hash(credentials['cms_password']), 'owner', now()))
        elif not con.execute('select 1 from users where active=1').fetchone():
            username, password = os.environ.get('CMS_BOOTSTRAP_USER', ''), os.environ.get('CMS_BOOTSTRAP_PASSWORD', '')
            if len(username) < 3 or len(password) < 12:
                cms.extensions['cms_media'].close()
                parser.error('Base sin usuarios. Importa la copia privada o define CMS_BOOTSTRAP_USER/PASSWORD para el primer arranque.')
            con.execute('insert into users(username,name,password,role,created_at) values(?,?,?,?,?)',
                        (username, 'Propietario', generate_password_hash(password), 'owner', now()))
    cms.extensions['cms_media'].close()
    club_server.init_db()
    if credentials:
        with club_server.db() as con:
            for prefix, name, role in [('equipo', 'Administrador local', 'admin'), ('mesero', 'Mesero local', 'mesero')]:
                if not con.execute('select 1 from staff where usuario=?', (credentials[prefix + '_usuario'],)).fetchone():
                    club_server.crear_staff(con, name, credentials[prefix + '_usuario'], role, credentials[prefix + '_pin'])
    children = []
    def stop(*_):
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=12)
            except subprocess.TimeoutExpired:
                child.kill()
        raise SystemExit(0)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        children.append(subprocess.Popen([sys.executable, str(BASE / 'backend/club_server.py')]))
        children.append(subprocess.Popen([sys.executable, '-m', 'gunicorn', '--bind', f'{bind}:{args.port}',
                         '--workers', '1', '--threads', '8', '--timeout', '240', '--graceful-timeout', '15',
                         '--access-logfile', os.devnull, 'app:create_portable_app()'], cwd=BASE / 'backend'))
        for _ in range(100):
            if any(p.poll() is not None for p in children):
                raise RuntimeError('Un servicio no pudo arrancar; revisa el error anterior.')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/healthz', timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(.15)
        else:
            raise RuntimeError('El servicio no pasó su comprobación de inicio.')
        print(f'Listo: {origin}/ · CMS: {origin}/cms/ · Equipo: {origin}/equipo/', flush=True)
        if credentials:
            print(f'Cuentas de prueba en: {data / "ACCESOS-LOCALES.txt"}', flush=True)
        while all(p.poll() is None for p in children):
            time.sleep(.5)
        raise RuntimeError('Un servicio se detuvo.')
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=12)
            except subprocess.TimeoutExpired:
                child.kill()
        lock.close()


if __name__ == '__main__':
    main()
