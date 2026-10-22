"""Puente local CMS → Hermes; socket Unix privado, sin puertos de red.

Un JSON UTF-8 terminado en LF por conexión. El proceso Hermes solo propone las
tres herramientas editoriales; el CMS autenticado conserva su ejecución.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import socketserver
import stat
import subprocess
import threading
import time

from hermes_worker import selected_profile, validate_request

MAX_REQUEST = 16 * 1024 * 1024
MAX_RESPONSE = 2 * 1024 * 1024
SAFE_ERROR = {'error': 'La conexión privada con Hermes no pudo completar la consulta.', 'status': 503}


def worker_environment(root, profile, profile_name):
    names = ('HOME', 'PATH', 'LANG', 'LC_ALL', 'TMPDIR', 'SSL_CERT_FILE', 'SSL_CERT_DIR')
    env = {name: os.environ[name] for name in names if name in os.environ}
    env.update(HERMES_HOME=str(profile), CISNE_HERMES_ROOT=str(root),
               CISNE_HERMES_PROFILE_DIR=str(profile), CISNE_HERMES_PROFILE_NAME=profile_name,
               PYTHONIOENCODING='utf-8',
               PYTHONUNBUFFERED='1', HERMES_LOG_LEVEL='CRITICAL')
    return env


class WorkerRunner:
    def __init__(self, root, profile):
        self.profile_name = selected_profile()
        self.root = Path(root).resolve()
        self.profile = Path(profile).resolve()
        self.python = self.root / 'venv/bin/python3'
        self.worker = Path(__file__).with_name('hermes_worker.py')
        if (self.profile.name != self.profile_name or self.profile.parent.name != 'profiles'
                or not self.python.is_file() or not (self.root / 'run_agent.py').is_file()
                or not (self.profile / 'config.yaml').is_file()
                or not (self.profile / 'SOUL.md').is_file()):
            raise ValueError('La instalación privada de Hermes no está preparada.')

    def __call__(self, request):
        validate_request(request)
        # El timeout del socket cliente deja margen para serializar el resultado.
        timeout = 18 if request['action'] == 'status' else 62
        result = subprocess.run([str(self.python), str(self.worker)],
            input=json.dumps(request, ensure_ascii=False, allow_nan=False),
            capture_output=True, text=True, timeout=timeout, check=False,
            cwd=str(self.profile), env=worker_environment(self.root, self.profile, self.profile_name))
        if result.returncode or len(result.stdout.encode('utf-8')) > MAX_RESPONSE:
            raise ValueError('worker failed')
        value = json.loads(result.stdout)
        if not isinstance(value, dict) or value.get('error'):
            raise ValueError('worker response')
        return value


class BridgeHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            deadline = time.monotonic() + 10
            data = bytearray()
            while b'\n' not in data:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                self.request.settimeout(remaining)
                part = self.request.recv(min(65536, MAX_REQUEST + 2 - len(data)))
                if not part:
                    raise ValueError('incomplete request')
                data.extend(part)
                if len(data) > MAX_REQUEST + 1:
                    raise ValueError('request size')
            raw, remainder = bytes(data).split(b'\n', 1)
            if remainder.strip():
                raise ValueError('multiple requests')
            value = json.loads(raw)
            validate_request(value)
            response = self.server.runner(value)
            if not isinstance(response, dict):
                raise ValueError('response type')
            encoded = json.dumps(response, ensure_ascii=False, allow_nan=False).encode('utf-8')
            if len(encoded) + 1 > MAX_RESPONSE:
                raise ValueError('response size')
        except Exception:
            encoded = json.dumps(SAFE_ERROR).encode('utf-8')
        try:
            self.request.settimeout(3)
            self.request.sendall(encoded + b'\n')
        except OSError:
            pass


class BridgeServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    request_queue_size = 4

    def __init__(self, path, runner):
        self.runner = runner
        self.slots = threading.BoundedSemaphore(2)
        self.socket_path = Path(path)
        if not self.socket_path.is_absolute():
            raise ValueError('El socket requiere una ruta absoluta privada.')
        parent = self.socket_path.parent
        parent.mkdir(mode=0o750, parents=True, exist_ok=True)
        if parent.is_symlink() or parent.stat().st_uid != os.geteuid():
            raise ValueError('El directorio del socket debe pertenecer al servicio.')
        parent.chmod(0o750)
        if self.socket_path.exists() or self.socket_path.is_symlink():
            previous = self.socket_path.lstat()
            if not stat.S_ISSOCK(previous.st_mode) or previous.st_uid != os.geteuid():
                raise ValueError('La ruta del socket no es un socket propio.')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                probe.settimeout(1)
                try:
                    probe.connect(str(self.socket_path))
                except ConnectionRefusedError:
                    self.socket_path.unlink()
                else:
                    raise ValueError('El socket ya está en uso.')
        super().__init__(str(self.socket_path), BridgeHandler)
        self.socket_path.chmod(0o660)
        self.socket_inode = self.socket_path.stat().st_ino

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(json.dumps({'error': 'Hermes está ocupado.', 'status': 429}).encode() + b'\n')
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def server_close(self):
        super().server_close()
        try:
            entry = self.socket_path.lstat()
            if stat.S_ISSOCK(entry.st_mode) and entry.st_ino == getattr(self, 'socket_inode', None):
                self.socket_path.unlink()
        except FileNotFoundError:
            pass


def main():
    os.umask(0o007)
    runner = WorkerRunner(os.environ.get('CISNE_HERMES_ROOT', '/usr/local/lib/hermes-agent'),
        os.environ.get('CISNE_HERMES_PROFILE_DIR', '/srv/cisne/hermes/profiles/' + selected_profile()))
    with BridgeServer(os.environ.get('CISNE_HERMES_SOCKET', '/srv/cisne/hermes/run/bridge.sock'), runner) as server:
        server.serve_forever(poll_interval=0.5)


if __name__ == '__main__':
    main()
