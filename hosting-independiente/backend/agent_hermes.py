"""Adaptador privado entre el CMS y el perfil Hermes autorizado de Cisne.

Hermes propone llamadas; solo el CMS las ejecuta con la sesión que hizo la
petición. El proceso recibe JSON por stdin, nunca cookies o claves del CMS.
"""
from __future__ import annotations

import json
import errno
import os
from pathlib import Path
import socket
import subprocess
import threading
import time

from hermes_worker import selected_profile


class HermesError(ValueError):
    status_code = 503


class HermesProvider:
    def __init__(self, config, tools):
        self.profile = selected_profile(config.get('AGENT_HERMES_PROFILE_NAME'))
        self.root = Path(config.get('AGENT_HERMES_ROOT') or os.environ.get(
            'CISNE_HERMES_ROOT') or Path.home() / '.hermes/hermes-agent').expanduser().absolute()
        self.home = Path(config.get('AGENT_HERMES_PROFILE_DIR') or os.environ.get(
            'CISNE_HERMES_PROFILE_DIR') or Path.home() / '.hermes/profiles' / self.profile).expanduser().absolute()
        self.python = self.root / 'venv/bin/python3'
        self.worker = Path(__file__).with_name('hermes_worker.py')
        socket_path = config.get('AGENT_HERMES_SOCKET') or os.environ.get('CISNE_HERMES_SOCKET')
        self.socket_path = str(socket_path) if socket_path else None
        if self.socket_path and (not Path(self.socket_path).is_absolute() or '\x00' in self.socket_path):
            raise ValueError('CISNE_HERMES_SOCKET debe ser una ruta absoluta privada.')
        self.tools = tools
        self._slots = threading.BoundedSemaphore(2)
        self._status_lock = threading.Lock()
        self._status = None
        self._status_at = 0

    def _environment(self):
        # No heredar claves CMS, tokens de publicación o configuración de otro perfil.
        names = ('HOME', 'PATH', 'LANG', 'LC_ALL', 'TMPDIR', 'SSL_CERT_FILE', 'SSL_CERT_DIR')
        env = {name: os.environ[name] for name in names if name in os.environ}
        env.update(HERMES_HOME=str(self.home), CISNE_HERMES_ROOT=str(self.root),
                   CISNE_HERMES_PROFILE_DIR=str(self.home), CISNE_HERMES_PROFILE_NAME=self.profile,
                   PYTHONIOENCODING='utf-8',
                   PYTHONUNBUFFERED='1', HERMES_LOG_LEVEL='CRITICAL')
        return env

    def _call(self, payload, timeout):
        payload = {**payload, 'expected_profile': self.profile}
        if self.socket_path:
            return self._socket_call(payload, timeout)
        if self.home.name != self.profile or self.home.parent.name != 'profiles' or not (self.home / 'config.yaml').is_file() or not self.python.is_file() or not self.worker.is_file():
            raise HermesError('El perfil Hermes configurado no está disponible en este servidor.')
        try:
            result = subprocess.run([str(self.python), str(self.worker)],
                input=json.dumps(payload, ensure_ascii=False, allow_nan=False),
                capture_output=True, text=True, timeout=timeout, check=False,
                cwd=str(self.home), env=self._environment())
        except subprocess.TimeoutExpired:
            raise HermesError('Hermes tardó demasiado en responder. Revisa el borrador antes de volver a intentarlo.') from None
        except (OSError, UnicodeError, ValueError):
            raise HermesError('No fue posible iniciar la conexión con Hermes.') from None
        # Nunca propagar stderr, trazas de proveedores, rutas privadas ni credenciales.
        if result.returncode or len(result.stdout) > 2 * 1024 * 1024:
            raise HermesError('Hermes no pudo completar la consulta. Revisa la conexión del perfil configurado.')
        try:
            value = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise HermesError('Hermes no devolvió una respuesta válida.') from None
        if not isinstance(value, dict) or value.get('error'):
            raise HermesError('Hermes no pudo completar la consulta. Revisa la conexión del perfil configurado.')
        return value

    def _socket_call(self, payload, timeout):
        """Un intercambio privado; no hereda rutas, procesos ni secretos del host."""
        try:
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
            if len(data) > 16 * 1024 * 1024:
                raise ValueError('request size')
            deadline = time.monotonic() + timeout
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(timeout)
                connection.connect(self.socket_path)
                connection.settimeout(max(0.001, deadline - time.monotonic()))
                try:
                    connection.sendall(data + b'\n')
                except OSError as exc:
                    # Un bridge ocupado puede responder y cerrar antes de recibir
                    # el cuerpo. Leer esa respuesta, nunca reenviar la operación.
                    if exc.errno not in (errno.EPIPE, errno.ENOTCONN, errno.ECONNRESET):
                        raise
                chunks = bytearray()
                while b'\n' not in chunks:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError()
                    connection.settimeout(remaining)
                    part = connection.recv(min(65536, 2 * 1024 * 1024 + 1 - len(chunks)))
                    if not part:
                        raise ValueError('incomplete response')
                    chunks.extend(part)
                    if len(chunks) > 2 * 1024 * 1024:
                        raise ValueError('response size')
            raw, remainder = bytes(chunks).split(b'\n', 1)
            if remainder.strip():
                raise ValueError('multiple responses')
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError('response type')
        except (OSError, UnicodeError, ValueError, TypeError):
            raise HermesError('No fue posible completar la conexión privada con Hermes. Revisa el borrador antes de volver a intentarlo.') from None
        if value.get('error'):
            error = HermesError('Hermes no pudo completar la consulta. Revisa la conexión del perfil configurado.')
            if value.get('status') == 429:
                error.status_code = 429
            raise error
        return value

    def status(self):
        with self._status_lock:
            if self._status is not None and time.monotonic() - self._status_at < 30:
                return dict(self._status)
            try:
                result = self._call({'action': 'status'}, 20)
                if result.get('configured') is not True or result.get('profile') != self.profile:
                    raise HermesError('El perfil Hermes conectado no coincide con la configuración esperada.')
                model = result.get('model')
                self._status = {'configured': True,
                    'model': model[:120] if isinstance(model, str) else None,
                    'provider': 'hermes', 'profile': self.profile}
            except HermesError:
                self._status = {'configured': False, 'model': None,
                    'provider': 'hermes', 'profile': self.profile}
            self._status_at = time.monotonic()
            return dict(self._status)

    def respond(self, instructions, inputs):
        if not self._slots.acquire(blocking=False):
            error = HermesError('Hermes está atendiendo otras consultas. Intenta de nuevo en un momento.')
            error.status_code = 429
            raise error
        try:
            if not self.status()['configured']:
                raise HermesError('El perfil Hermes configurado no está conectado. Revisa su configuración.')
            return self._call({'action': 'respond', 'instructions': instructions,
                               'inputs': inputs, 'tools': self.tools}, 65)
        finally:
            self._slots.release()
