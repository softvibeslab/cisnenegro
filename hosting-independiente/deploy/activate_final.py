#!/usr/bin/env python3
"""Activa sólo el vhost final de Cisne cuando ambos dominios apuntan al VPS."""
from contextlib import contextmanager
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time

DOMAINS = ('cisnenegro.mx', 'www.cisnenegro.mx')
RESOLVERS = ('1.1.1.1', '8.8.8.8')
TARGET_IP = '31.220.63.211'
MARKER = '# Managed by cisne-final-domain'
VHOST = Path('/etc/nginx/sites-available/cisne-final')
CERTIFICATE = Path('/etc/letsencrypt/live/cisne-final')
LOCK = Path('/run/lock/cisne-final-domain.lock')


def final_config():
    return f'''{MARKER}
# HTTPS final; renovación del certificado mediante Certbot del host.
server {{
    listen 80;
    listen [::]:80;
    server_name cisnenegro.mx www.cisnenegro.mx;
    location ^~ /.well-known/acme-challenge/ {{
        root /var/lib/cisne-acme;
        try_files $uri =404;
    }}
    location / {{ return 301 https://cisnenegro.mx$request_uri; }}
}}

server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name www.cisnenegro.mx;
    ssl_certificate /etc/letsencrypt/live/cisne-final/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cisne-final/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    return 301 https://cisnenegro.mx$request_uri;
}}

server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name cisnenegro.mx;
    ssl_certificate /etc/letsencrypt/live/cisne-final/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cisne-final/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 105m;
    client_body_timeout 240s;
    location / {{
        proxy_pass http://127.0.0.1:8888;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Forwarded "";
        proxy_set_header X-Cisne-Staff-Token "";
        proxy_set_header Connection "";
        proxy_connect_timeout 5s;
        proxy_read_timeout 240s;
        proxy_send_timeout 240s;
        proxy_request_buffering off;
    }}
}}
'''


def answer_addresses(output, record_type):
    """Lee respuestas dig completas; admite CNAME sin confundirlo con una IP."""
    if not re.search(r'\bstatus: NOERROR\b', output):
        raise ValueError('La consulta DNS no terminó con NOERROR.')
    addresses = set()
    for line in output.splitlines():
        if not line.strip() or line.startswith(';'):
            continue
        fields = line.split()
        if len(fields) != 5 or fields[2] != 'IN':
            raise ValueError('Respuesta DNS no reconocida.')
        if fields[3] == 'CNAME':
            continue
        if fields[3] != record_type:
            raise ValueError('Tipo de respuesta DNS inesperado.')
        address = ipaddress.ip_address(fields[4])
        if address.version != (4 if record_type == 'A' else 6):
            raise ValueError('Familia de dirección DNS incorrecta.')
        addresses.add(str(address))
    return addresses


def dns_ready(command=subprocess.run):
    for resolver in RESOLVERS:
        for domain in DOMAINS:
            for record_type, expected in (('A', {TARGET_IP}), ('AAAA', set())):
                try:
                    result = command(['dig', '@' + resolver, domain, record_type,
                                      '+noall', '+answer', '+comments', '+time=3', '+tries=1'],
                                     check=True, capture_output=True, text=True, timeout=8)
                    if answer_addresses(result.stdout, record_type) != expected:
                        return False
                except (subprocess.SubprocessError, ValueError):
                    return False
    return True


@contextmanager
def activation_lock(path):
    with Path(path).open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def read_managed(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('El vhost debe ser un archivo regular, sin enlace simbólico.')
    content = path.read_bytes()
    if content.splitlines()[0:1] != [MARKER.encode()]:
        raise ValueError('El vhost no tiene el marcador de esta instalación; no se modifica.')
    return content


def replace_atomically(path, content):
    descriptor, temporary = tempfile.mkstemp(prefix='.cisne-final-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def activate(vhost=VHOST, certificate=CERTIFICATE, lock=LOCK, command=subprocess.run):
    vhost, certificate = Path(vhost), Path(certificate)
    with activation_lock(lock):
        before = read_managed(vhost)
        desired = final_config().encode()
        certificate_files = (certificate / 'fullchain.pem', certificate / 'privkey.pem')
        if before == desired and all(path.is_file() for path in certificate_files):
            return {'status': 'already_active'}
        if not dns_ready(command):
            return {'status': 'waiting_for_dns'}
        retry_after = Path(lock).with_suffix('.retry-after')
        if retry_after.exists() and float(retry_after.read_text()) > time.time():
            return {'status': 'waiting_for_certificate_retry'}
        # Nunca solicitar ni instalar TLS sobre una configuración previa inválida.
        command(['nginx', '-t'], check=True, capture_output=True, text=True, timeout=20)
        try:
            command(['certbot', 'certonly', '--non-interactive', '--webroot',
                     '-w', '/var/lib/cisne-acme', '--cert-name', 'cisne-final',
                     '--reuse-key', '--keep-until-expiring',
                     '-d', DOMAINS[0], '-d', DOMAINS[1]],
                    check=True, capture_output=True, text=True, timeout=240)
        except subprocess.SubprocessError:
            # El timer sigue mirando DNS cada cinco minutos, pero un fallo ACME
            # espera una hora para no consumir límites de validación del proveedor.
            replace_atomically(retry_after, str(time.time() + 3600).encode())
            raise
        retry_after.unlink(missing_ok=True)
        if not all(path.is_file() for path in certificate_files):
            raise ValueError('Certbot terminó sin los archivos de certificado esperados.')
        if read_managed(vhost) != before:
            raise ValueError('El vhost cambió durante la activación; no se sustituye.')
        replace_atomically(vhost, desired)
        try:
            command(['nginx', '-t'], check=True, capture_output=True, text=True, timeout=20)
        except Exception:
            # Una configuración no válida jamás llega al proceso nginx en ejecución.
            replace_atomically(vhost, before)
            raise
        try:
            command(['systemctl', 'reload', 'nginx'], check=True,
                    capture_output=True, text=True, timeout=30)
        except Exception:
            replace_atomically(vhost, before)
            command(['nginx', '-t'], check=True, capture_output=True, text=True, timeout=20)
            command(['systemctl', 'reload', 'nginx'], check=True,
                    capture_output=True, text=True, timeout=30)
            raise
        return {'status': 'activated', 'domains': list(DOMAINS)}


def main():
    try:
        print(json.dumps(activate()))
    except BlockingIOError:
        print(json.dumps({'status': 'already_running'}))
    except subprocess.CalledProcessError as exc:
        # Los comandos capturan su salida: no imprimir contenido de configuración.
        print(json.dumps({'status': 'error', 'command': Path(exc.cmd[0]).name,
                          'exit_code': exc.returncode}))
        raise SystemExit(1) from None
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'status': 'error', 'type': type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
