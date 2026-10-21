import contextlib
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jF1sAAAAASUVORK5CYII=')
WEBP = base64.b64decode('UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


client_module = load('cisne_cms', ROOT / 'skills/cisne-cms/scripts/cisne_cms.py')
installer = load('cisne_install', ROOT / 'preparar_perfil.py')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def handle_request(self):
        data = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        self.server.calls.append((self.command, self.path, dict(self.headers), data))
        if self.server.redirect and self.path.endswith('/agent/content'):
            self.send_response(302)
            self.send_header('Location', self.server.redirect)
            self.end_headers()
            return
        status = 200
        result = {}
        if self.path == '/cms/api/login':
            self.server.logins += 1
            status = 200 if json.loads(data).get('password') == 'private-password' else 401
            result = {'csrf': 'private-csrf', 'user': {'role': 'editor'}}
        elif self.headers.get('Cookie') != 'cn_staff=private-cookie':
            status = 401
        elif self.command == 'POST' and self.headers.get('X-CSRF-Token') != 'private-csrf':
            status = 403
        elif self.path == '/cms/api/session':
            result = {'csrf': 'private-csrf'}
        elif self.server.failure:
            status = self.server.failure
            result = {'error': 'private-password private-cookie private-csrf'}
        elif self.path == '/cms/api/state':
            result = {'document': {'menu': {}}, 'published_document': {'menu': {}}, 'version': 3, 'published_version': 2}
        elif self.path == '/cms/api/agent/content':
            if self.command == 'POST':
                result = {'version': json.loads(data)['version'] + 1, 'change': {'saved': True}}
            else:
                result = {'document': {'menu': {}}, 'version': 3, 'published_version': 2, 'schema': []}
        elif self.path == '/cms/api/agent/images':
            result = {'id': 'job-1', 'status': 'queued', 'version': json.loads(data)['version']}
        elif self.path == '/cms/api/agent/images/job-1':
            result = {'id': 'job-1', 'status': self.server.job_status, 'version': 3,
                      'product': {'collection': 'barril', 'id': 'colchita'},
                      'media': {'id': self.server.job_media_id, 'title': 'Prueba ilustrada', 'status': 'ready', 'url': 'https://not-a-download-target.example/secret'}}
        elif self.path == '/cms/media/image-1/file':
            if self.server.download_redirect:
                self.send_response(302)
                self.send_header('Location', self.server.download_redirect)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type', self.server.image_content_type)
            if self.server.image_content_length is not None:
                self.send_header('Content-Length', str(self.server.image_content_length))
            self.end_headers()
            self.wfile.write(self.server.image_body)
            return
        elif self.path == '/cms/api/media':
            result = {'id': 'reference-1', 'status': 'ready'}
        elif self.path == '/cms/api/publish':
            status = 403
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        if self.path == '/cms/api/login' and status == 200:
            self.send_header('Set-Cookie', 'cn_staff=private-cookie; HttpOnly; Path=/')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.server.calls = []
        self.server.logins = 0
        self.server.redirect = None
        self.server.failure = None
        self.server.job_status = 'ready'
        self.server.job_media_id = 'image-1'
        self.server.download_redirect = None
        self.server.image_body = PNG
        self.server.image_content_type = 'image/png'
        self.server.image_content_length = None
        self.env = {'HERMES_HOME': self.temp.name, 'CISNE_CMS_URL': f'http://127.0.0.1:{self.server.server_port}', 'CISNE_CMS_USER': 'editor', 'CISNE_CMS_PASSWORD': 'private-password'}

    def connect(self):
        client = client_module.Client(self.env)
        client.authenticate()
        return client

    def test_auth_cache_reused_with_private_permissions(self):
        first = self.connect()
        self.assertEqual(first.state()['version'], 3)
        self.assertEqual(first.cache_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(first.cache_dir.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.connect().state()['version'], 3)
        self.assertEqual(self.server.logins, 1)

    def test_reject_insecure_remote_and_url_credentials(self):
        for url in ('http://example.com', 'https://u:p@example.com', 'https://example.com/path', 'https://example.com/?key=secret', 'https://example.com/#secret', 'http://localhost.evil.test', 'file:///tmp/a'):
            with self.subTest(url=url), self.assertRaises(client_module.ClientError):
                client_module.normalize_url(url)
        self.assertEqual(client_module.normalize_url('https://cisnenegro.mx/'), 'https://cisnenegro.mx')
        self.assertEqual(client_module.normalize_url('http://[::1]:8088'), 'http://[::1]:8088')

    def test_redirect_not_followed_or_credentials_forwarded(self):
        client = self.connect()
        self.server.redirect = self.env['CISNE_CMS_URL'] + '/credential-sink'
        with self.assertRaises(client_module.ClientError) as error:
            client.state()
        self.assertEqual(error.exception.status, 302)
        self.assertFalse(any('/credential-sink' == call[1] for call in self.server.calls))

    def test_mutation_version_and_csrf(self):
        client = self.connect()
        payload = {'version': 3, 'operation': {'action': 'update', 'collection': 'barril', 'id': 'colchita', 'data': {'visible': False}}}
        self.assertEqual(client.mutate(payload)['version'], 4)
        call = self.server.calls[-1]
        self.assertEqual(call[2]['X-Csrf-Token'], 'private-csrf')
        self.assertEqual(json.loads(call[3]), payload)
        self.server.failure = 409
        with self.assertRaises(client_module.ClientError) as error:
            client.mutate(payload)
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(sum(c[0] == 'POST' and c[1].endswith('/agent/content') for c in self.server.calls), 2)

    def test_publication_requires_flag_and_server_role(self):
        client = self.connect()
        with self.assertRaises(client_module.ClientError):
            client.publish(3, 'Aprobado', False)
        self.assertFalse(any(c[1].endswith('/publish') for c in self.server.calls))
        with self.assertRaises(client_module.ClientError) as error:
            client.publish(3, 'Aprobado', True)
        self.assertEqual(error.exception.status, 403)
        self.assertIn('published_document', client.state(True))

    def test_image_job_contract_and_path_validation(self):
        client = self.connect()
        self.assertEqual(client.generate_image({'version': 3, 'collection': 'barril', 'id': 'colchita', 'reference_media_id': 'ref-1'})['status'], 'queued')
        self.assertEqual(client.image_status('job-1')['status'], 'ready')
        for identifier in ('../login', 'job?secret=x', '/bad'):
            with self.assertRaises(client_module.ClientError):
                client.image_status(identifier)

    def test_upload_uses_safe_filename_and_metadata(self):
        client = self.connect()
        file = Path(self.temp.name) / 'original"nombre.png'
        file.write_bytes(b'\x89PNG\r\n\x1a\nmock')
        self.assertEqual(client.upload(file, {'title': 'Etiqueta original', 'category': 'cervezas'})['id'], 'reference-1')
        body = self.server.calls[-1][3]
        self.assertIn(b'filename="etiqueta.png"', body)
        self.assertNotIn(b'original"nombre', body)
        self.assertIn(b'Etiqueta original', body)

    def test_cli_download_private_binary_and_no_overwrite(self):
        output = io.StringIO()
        with patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stdout(output):
            code = client_module.main(['image-download', 'job-1'])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        destination = Path(result['filepath'])
        self.assertEqual(destination.parent, Path(self.temp.name).resolve() / '.cisne-generated')
        self.assertEqual(destination.suffix, '.png')
        self.assertEqual(destination.read_bytes(), PNG)
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        self.assertEqual(destination.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(result['bytes'], len(PNG))
        self.assertEqual(result['media']['id'], 'image-1')
        self.assertNotIn('url', result['media'])
        second = self.connect().image_download('job-1')
        self.assertNotEqual(second['filepath'], result['filepath'])
        self.assertEqual(destination.read_bytes(), PNG)
        downloads = [call for call in self.server.calls if call[1].startswith('/cms/media/')]
        self.assertEqual(len(downloads), 2)
        self.assertEqual(downloads[0][1], '/cms/media/image-1/file')
        self.assertEqual(downloads[0][2]['Cookie'], 'cn_staff=private-cookie')
        self.assertNotIn('private-cookie', output.getvalue())

    def test_download_webp_and_nonimage_rejection(self):
        client = self.connect()
        self.server.image_body, self.server.image_content_type = WEBP, 'image/webp'
        result = client.image_download('job-1')
        self.assertEqual(Path(result['filepath']).read_bytes(), WEBP)
        self.assertEqual(result['mime_type'], 'image/webp')
        self.server.image_body = b'<html>not an image</html>'
        with self.assertRaises(client_module.ClientError):
            client.image_download('job-1')
        self.assertEqual(len(list((Path(self.temp.name) / '.cisne-generated').iterdir())), 1)

    def test_download_requires_ready_and_valid_media_id(self):
        client = self.connect()
        self.server.job_status = 'queued'
        with self.assertRaises(client_module.ClientError):
            client.image_download('job-1')
        self.server.job_status, self.server.job_media_id = 'ready', '../secret'
        with self.assertRaises(client_module.ClientError):
            client.image_download('job-1')
        self.assertFalse(any(c[1].startswith('/cms/media/') for c in self.server.calls))

    def test_download_rejects_redirect_and_oversize(self):
        client = self.connect()
        self.server.download_redirect = self.env['CISNE_CMS_URL'] + '/download-sink'
        with self.assertRaises(client_module.ClientError) as error:
            client.image_download('job-1')
        self.assertEqual(error.exception.status, 302)
        self.assertFalse(any(c[1] == '/download-sink' for c in self.server.calls))
        self.server.download_redirect = None
        with patch.object(client_module, 'MAX_UPLOAD', 10):
            with self.assertRaises(client_module.ClientError):
                client.image_download('job-1')
        self.server.image_content_length = client_module.MAX_UPLOAD + 1
        with self.assertRaises(client_module.ClientError):
            client.image_download('job-1')
        self.assertFalse((Path(self.temp.name) / '.cisne-generated').exists())

    def test_download_does_not_follow_output_directory_symlink(self):
        client = self.connect()
        with tempfile.TemporaryDirectory() as outside:
            (Path(self.temp.name) / '.cisne-generated').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(client_module.ClientError):
                client.image_download('job-1')
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_cli_error_never_prints_reflected_secrets(self):
        self.connect()
        self.server.failure = 500
        output = io.StringIO()
        with patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stdout(output):
            code = client_module.main(['state'])
        self.assertEqual(code, 1)
        value = json.loads(output.getvalue())
        self.assertEqual(value['status'], 500)
        for secret in ('private-password', 'private-cookie', 'private-csrf'):
            self.assertNotIn(secret, output.getvalue())

    def test_reject_world_readable_session(self):
        client = self.connect()
        client.cache_path.chmod(0o644)
        with self.assertRaises(client_module.ClientError):
            client_module.Client(self.env)

    def test_reject_unknown_collection_before_mutation(self):
        client = self.connect()
        with self.assertRaises(client_module.ClientError):
            client.mutate({'version': 3, 'operation': {'action': 'delete', 'collection': 'users'}})
        with self.assertRaises(client_module.ClientError):
            client.mutate({'version': True, 'operation': {'action': 'delete', 'collection': 'barril'}})
        self.assertFalse(any(c[1].endswith('/agent/content') for c in self.server.calls))


class InstallerTests(unittest.TestCase):
    def test_dry_run_does_not_create_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = {'HERMES_HOME': temporary, 'HERMES_BIN': '/fake/hermes'}
            report = installer.install(env)
            self.assertTrue(report['create'])
            self.assertFalse(Path(report['destination']).exists())

    def test_fresh_profile_no_clone_and_repeat_preserves(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = {'HERMES_HOME': temporary, 'HERMES_BIN': '/fake/hermes'}
            calls = []
            def runner(binary, args, environment):
                calls.append(args)
                destination = Path(temporary) / 'profiles/cisne-negro'
                destination.mkdir(parents=True)
                (destination / 'SOUL.md').write_text('Generic default')
            report = installer.install(env, True, runner)
            destination = Path(report['destination'])
            self.assertIn('--no-skills', calls[0])
            self.assertNotIn('--clone', calls[0])
            self.assertEqual((destination / 'SOUL.hermes-default.md').read_text(), 'Generic default')
            self.assertTrue((destination / 'skills/cisne-cms/scripts/cisne_cms.py').is_file())
            (destination / 'SOUL.md').write_text('Custom identity')
            installer.install(env, True, runner)
            self.assertEqual((destination / 'SOUL.md').read_text(), 'Custom identity')
            self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
