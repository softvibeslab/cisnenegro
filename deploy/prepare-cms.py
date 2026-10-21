#!/usr/bin/env python3
"""Provision CMS on the existing Cisne Negro VPS; no nginx activation here.

Run as root after staging code in /opt/cisnenegro-cms. Initial imported media,
if supplied, is at /var/lib/cisnenegro-cms-import. Never replaces existing CMS data.
"""
import os
import pwd
import secrets
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

def run(*args, **kw):
    return subprocess.run(args, check=True, **kw)

def main():
    if os.geteuid() != 0:
        raise SystemExit('Requiere root en el VPS.')
    root = Path('/var/lib/cisnenegro-cms')
    app = Path('/opt/cisnenegro-cms')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/var/backups/cisnenegro-cms-deploy') / stamp
    backup.mkdir(parents=True, mode=0o700)
    backup.parent.chmod(0o700)
    for path in [Path('/etc/cisnenegro-club.env'), Path('/etc/nginx/sites-available/cisnenegro.softvibes.art'),
                 Path('/opt/cisnenegro-club/club_server.py'), Path('/var/www/cisnenegro/assets/js/admin.js'),
                 Path('/var/www/cisnenegro/assets/js/menu.js'), Path('/var/www/cisnenegro/assets/js/landing.js')]:
        if path.exists():
            shutil.copy2(path, backup / path.name)
    source = sqlite3.connect('file:/var/lib/cisnenegro-club/club.db?mode=ro', uri=True)
    target = sqlite3.connect(backup / 'club.db')
    source.backup(target)
    target.close(); source.close()
    try: account = pwd.getpwnam('cisnecms')
    except KeyError:
        run('useradd', '--system', '--home', str(root), '--shell', '/usr/sbin/nologin', 'cisnecms')
        account = pwd.getpwnam('cisnecms')
    root.mkdir(exist_ok=True, mode=0o750)
    staging = Path('/var/lib/cisnenegro-cms-import')
    if not (root / 'media').exists() and (staging / 'media/media.sqlite').exists():
        shutil.move(str(staging / 'media'), str(root / 'media'))
        shutil.copy2(staging / 'media-map.json', root / 'media-map.json')
    cms_env = Path('/etc/cisnenegro-cms.env')
    if cms_env.exists():
        values = dict(line.split('=', 1) for line in cms_env.read_text().splitlines() if '=' in line and not line.startswith('#'))
        token = values['CLUB_ADMIN_TOKEN']
    else:
        token = secrets.token_urlsafe(48)
        values = {'CMS_ROOT': str(root), 'CMS_SITE': '/var/www/cisnenegro',
                  'CMS_ORIGIN': 'https://cisnenegro.softvibes.art',
                  'CMS_CLUB_URL': 'http://127.0.0.1:8790', 'CLUB_ADMIN_TOKEN': token}
        cms_env.write_text(''.join(f'{k}={v}\n' for k, v in values.items()))
        cms_env.chmod(0o600)
    club_env = Path('/etc/cisnenegro-club.env')
    lines = [line for line in club_env.read_text().splitlines() if not line.startswith('CLUB_ADMIN_TOKEN=')]
    club_env.write_text('\n'.join(lines) + '\nCLUB_ADMIN_TOKEN=' + token + '\n')
    club_env.chmod(0o600)
    run(str(app / 'venv/bin/python'), str(app / 'cms_server.py'), '--bootstrap-htpasswd',
        '/etc/nginx/.htpasswd-cisnenegro', env=os.environ | values)
    run('chown', '-R', f'{account.pw_uid}:{account.pw_gid}', str(root))
    root.chmod(0o750)
    Path('/var/backups/cisnenegro-cms').mkdir(exist_ok=True, mode=0o700)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', '--now', 'cisnenegro-cms')
    print('CMS preparado. Respaldo previo:', backup)
    print('Falta validar loopback y activar el include nginx; el sitio sigue en la configuración anterior.')

if __name__ == '__main__': main()
