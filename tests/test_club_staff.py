"""Real HTTP check: club administration accepts only the internal CMS proxy."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request


class ClubStaff(unittest.TestCase):
    def test_internal_token_and_public_health(self):
        with tempfile.TemporaryDirectory() as folder:
            with socket.socket() as port_socket:
                port_socket.bind(('127.0.0.1', 0))
                port = port_socket.getsockname()[1]
            environment = os.environ | {'CLUB_PORT': str(port), 'CLUB_DB': str(Path(folder) / 'club.db'),
                                        'CLUB_ADMIN_TOKEN': 'internal-local-test-token'}
            script = Path(__file__).resolve().parents[1] / 'backend/club_server.py'
            process = subprocess.Popen([sys.executable, str(script)], env=environment,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            base = f'http://127.0.0.1:{port}'
            try:
                for _ in range(40):
                    try:
                        with urllib.request.urlopen(base + '/api/salud', timeout=1) as r:
                            self.assertTrue(json.load(r)['ok'])
                        break
                    except (urllib.error.URLError, ConnectionError): time.sleep(.05)
                else: self.fail('No arrancó el backend de prueba.')
                for headers in ({}, {'X-Cisne-Staff': 'incorrecto'}):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(urllib.request.Request(base + '/api/admin/resumen', headers=headers))
                    self.assertEqual(error.exception.code, 403)
                request = urllib.request.Request(base + '/api/admin/resumen',
                    headers={'X-Cisne-Staff': 'internal-local-test-token'})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIsInstance(json.load(response), dict)
            finally:
                process.terminate()
                process.wait(timeout=5)


if __name__ == '__main__': unittest.main()
