"""Integration checks for staff identity, publishing, permissions and private media."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from cms_server import create_app, now


class CMSIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({'CMS_ROOT': self.tmp.name, 'CMS_SITE': str(ROOT / 'sitio'),
            'CMS_DEV': True, 'CMS_ORIGIN': 'http://localhost', 'TESTING': True})
        with self.app.extensions['cms_db']() as con:
            con.execute('insert into users(username,name,password,role,created_at) values(?,?,?,?,?)',
                ('owner', 'Propietario', generate_password_hash('Owner-test-only-2026'), 'owner', now()))
            con.execute('insert into users(username,name,password,role,created_at) values(?,?,?,?,?)',
                ('editor', 'Editor', generate_password_hash('Editor-test-only-2026'), 'editor', now()))
        self.client = self.app.test_client()
        self.csrf = None

    def tearDown(self):
        self.app.extensions['cms_media'].close()
        self.tmp.cleanup()

    def login(self, user='owner'):
        r = self.client.post('/cms/api/login', json={'username': user, 'password': f'{user.title()}-test-only-2026'})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.csrf = r.json['csrf']
        return r

    def change(self, method, path, data):
        return self.client.open(path, method=method, json=data, headers={'X-CSRF-Token': self.csrf})

    def test_anonymous_draft_preview_and_operations_denied(self):
        for path in ['/cms/api/state', '/cms/preview/', '/cms/preview/data/menu.json', '/cms/api/users', '/api/admin/socios']:
            self.assertEqual(self.client.get(path).status_code, 401, path)
        self.assertEqual(self.client.get('/cms/auth/owner').status_code, 401)

    def test_invalid_password_and_cookie_flags(self):
        self.assertEqual(self.client.post('/cms/api/login', json={'username': 'owner', 'password': 'wrong'}).status_code, 401)
        r = self.login()
        self.assertIn('HttpOnly', r.headers['Set-Cookie'])
        self.assertIn('SameSite=Lax', r.headers['Set-Cookie'])

    def test_csrf_and_cross_origin(self):
        self.login()
        s = self.client.get('/cms/api/state').json
        b = {'document': s['document'], 'version': s['version']}
        self.assertEqual(self.client.put('/cms/api/draft', json=b).status_code, 403)
        self.assertEqual(self.client.put('/cms/api/draft', json=b, headers={'X-CSRF-Token': self.csrf, 'Origin': 'https://wrong.invalid'}).status_code, 403)

    def test_editor_cannot_publish_manage_users_or_read_club(self):
        self.login('editor')
        self.assertEqual(self.client.get('/cms/api/state').status_code, 200)
        self.assertEqual(self.change('POST', '/cms/api/publish', {'version': 1}).status_code, 403)
        self.assertEqual(self.client.get('/cms/api/users').status_code, 403)
        self.assertEqual(self.client.get('/api/admin/socios.csv').status_code, 403)
        self.assertEqual(self.client.get('/cms/auth/owner').status_code, 403)

    def test_draft_conflict_publish_and_restore(self):
        self.login()
        before = self.client.get('/').data
        s = self.client.get('/cms/api/state').json
        doc = s['document']; doc['page']['hero_title'] = 'Cerveza de prueba editorial'
        saved = self.change('PUT', '/cms/api/draft', {'document': doc, 'version': s['version']})
        self.assertEqual(saved.status_code, 200, saved.json)
        self.assertEqual(self.client.get('/').data, before)
        self.assertEqual(self.change('PUT', '/cms/api/draft', {'document': doc, 'version': s['version']}).status_code, 409)
        pub = self.change('POST', '/cms/api/publish', {'version': saved.json['version'], 'note': 'Prueba'})
        self.assertEqual(pub.status_code, 200, pub.json)
        self.assertIn('Cerveza de prueba editorial'.encode(), self.client.get('/').data)
        self.assertEqual(self.client.get('/?v=1').data, before)
        self.assertEqual(self.client.get('/data/menu.json?v=1').status_code, 200)
        restored = self.change('POST', '/cms/api/restore', {'id': 1, 'version': saved.json['version']})
        self.assertEqual(restored.status_code, 200)
        self.assertIn('Cerveza de prueba editorial'.encode(), self.client.get('/').data)
        self.assertEqual(self.change('POST', '/cms/api/publish', {'version': restored.json['version']}).status_code, 200)
        self.assertNotIn('Cerveza de prueba editorial'.encode(), self.client.get('/').data)

    def test_disabled_user_session_revoked(self):
        self.login('editor'); editor = self.client
        self.client = self.app.test_client(); self.login()
        self.assertEqual(self.change('PATCH', '/cms/api/users/2', {'active': False}).status_code, 200)
        self.assertEqual(editor.get('/cms/api/state').status_code, 401)
        self.assertEqual(self.change('PATCH', '/cms/api/users/1', {'active': False}).status_code, 400)

    def test_logout_revokes_session(self):
        self.login()
        self.assertEqual(self.change('POST', '/cms/api/logout', {}).status_code, 200)
        self.assertEqual(self.client.get('/cms/api/state').status_code, 401)

    def test_private_media_only_public_after_publication(self):
        self.login()
        buf = io.BytesIO(); Image.new('RGB', (40, 30), '#f2c97d').save(buf, 'PNG'); buf.seek(0)
        r = self.client.post('/cms/api/media', data={'file': (buf, 'cerveza.png'), 'metadata': json.dumps({'title': 'Cerveza'})},
            headers={'X-CSRF-Token': self.csrf}, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 201, r.json)
        item = r.json['item']; anonymous = self.app.test_client()
        self.assertEqual(anonymous.get(item['url']).status_code, 404)
        self.assertEqual(self.client.get(item['url']).status_code, 200)
        self.assertEqual(self.client.get(item['url'].replace('/file', '/original')).status_code, 404)
        state = self.client.get('/cms/api/state').json
        doc = state['document']; doc['page']['hero_image'] = item['url']
        saved = self.change('PUT', '/cms/api/draft', {'document': doc, 'version': state['version']})
        self.assertEqual(saved.status_code, 200, saved.json)
        self.assertEqual(anonymous.get(item['url']).status_code, 404)
        self.assertEqual(self.change('POST', '/cms/api/publish', {'version': saved.json['version']}).status_code, 200)
        self.assertEqual(anonymous.get(item['url']).status_code, 200)
        self.assertTrue(self.client.get(f'/cms/api/media/{item["id"]}/usage').json['uses'])
        self.change('POST', f'/cms/api/media/{item["id"]}/archive', {'archived': True})
        self.assertEqual(anonymous.get(item['url']).status_code, 200)

    def test_invalid_media_publication_preserves_current(self):
        self.login(); before = self.client.get('/').data
        s = self.client.get('/cms/api/state').json
        s['document']['page']['hero_image'] = '/cms/media/' + 'f' * 32 + '/file'
        saved = self.change('PUT', '/cms/api/draft', {'document': s['document'], 'version': s['version']})
        self.assertEqual(saved.status_code, 200, saved.json)
        self.assertEqual(self.change('POST', '/cms/api/publish', {'version': saved.json['version']}).status_code, 400)
        self.assertEqual(self.client.get('/').data, before)


if __name__ == '__main__': unittest.main()
