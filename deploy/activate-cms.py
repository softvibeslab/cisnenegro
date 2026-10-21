#!/usr/bin/env python3
"""Activate the prepared CMS while preserving TLS, /v2 and unrelated routes."""
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

config = Path('/etc/nginx/sites-available/cisnenegro.softvibes.art')
previous = config.read_text()
for route in ('/', '/cms/', '/cms/cms.js'):
    for attempt in range(20):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8795' + route, timeout=10) as response:
                assert response.status == 200
            break
        except urllib.error.URLError:
            if attempt == 19: raise
            time.sleep(.5)
candidate = previous
if 'include snippets/cisnenegro-cms.conf;' not in candidate:
    for route in ('/admin/', '/api/admin/'):
        candidate, count = re.subn(r'    location ' + re.escape(route) + r' \{[^{}]*\}\n', '', candidate)
        if count != 1:
            raise SystemExit('Configuración inesperada: revisar bloque ' + route)
    marker = '    include snippets/cisnenegro-v2.conf;'
    if marker not in candidate:
        raise SystemExit('Falta la referencia esperada a /v2; revisar configuración antes de activar.')
    candidate = candidate.replace(marker, '    include snippets/cisnenegro-cms.conf;\n' + marker)
config.write_text(candidate)
try:
    subprocess.run(['nginx', '-t'], check=True)
    subprocess.run(['systemctl', 'restart', 'cisnenegro-club'], check=True)
    subprocess.run(['systemctl', 'is-active', '--quiet', 'cisnenegro-club'], check=True)
    subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
except Exception:
    config.write_text(previous)
    raise
print('CMS activado. Configuración TLS y /v2 conservadas.')
