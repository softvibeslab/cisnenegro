"""La edición de v2 se prueba en bases nuevas; no usa datos ni accesos reales."""
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from bs4 import BeautifulSoup
from PIL import Image
from werkzeug.security import generate_password_hash
from cms_content import initial_document, render_document, validate_document
from cms_server import create_app, now


class V2CMS(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({'CMS_ROOT': self.temp.name, 'CMS_SITE': str(ROOT / 'sitio'),
            'CMS_DEV': True, 'CMS_ORIGIN': 'http://localhost', 'TESTING': True,
            'STAFF_TOKEN': 'test-internal-token', 'CLUB_URL': 'http://127.0.0.1:18790'})
        for username, role in [('owner', 'owner'), ('editor', 'editor')]:
            with self.app.extensions['cms_db']() as db:
                db.execute('insert into users(username,name,password,role,created_at) values(?,?,?,?,?)',
                    (username, username, generate_password_hash('testing-only-password'), role, now()))
        self.client = self.app.test_client()
        self.csrf = ''

    def tearDown(self):
        self.app.extensions['cms_media'].close()
        self.temp.cleanup()

    def login(self, user='owner'):
        response = self.client.post('/cms/api/login', json={'username': user, 'password': 'testing-only-password'},
                                    headers={'Origin': 'http://localhost'})
        self.assertEqual(response.status_code, 200, response.json)
        self.csrf = response.json['csrf']
        return response

    def change(self, method, path, data):
        return self.client.open(path, method=method, json=data,
                                headers={'Origin': 'http://localhost', 'X-CSRF-Token': self.csrf})

    def test_v2_initial_content_and_operational_markup_are_preserved(self):
        doc = initial_document(ROOT / 'sitio')
        source = json.loads((ROOT / 'sitio/data/menu.json').read_text())
        def identities(menu):
            return {group: [it['id'] for it in menu[group]] for group in ('barril', 'latas', 'sin_alcohol')} | {
                'comida': [it['id'] for section in menu['comida'] for it in section['items']]}
        self.assertEqual(identities(source), identities(doc['menu']))
        output = render_document(doc, ROOT / 'sitio', revision=1)
        original = BeautifulSoup((ROOT / 'sitio/index.html').read_text(), 'html.parser')
        home = BeautifulSoup(output['index.html'], 'html.parser')
        self.assertEqual(original.body.get_text(' ', strip=True), home.body.get_text(' ', strip=True))
        menu = BeautifulSoup(output['menu/index.html'], 'html.parser')
        self.assertIsNotNone(menu.select_one('#pedido'))
        self.assertIsNotNone(menu.select_one('script[src*="pedido.js"]'))
        self.assertEqual(menu.body['data-menu-url'], '/data/menu.json?v=1')
        self.assertNotIn('/v2/', output['index.html'] + output['menu/index.html'])

    def test_draft_is_private_until_published_with_revision_prices(self):
        self.login()
        current = self.client.get('/data/menu.json').json
        state = self.client.get('/cms/api/state').json
        doc = state['document']
        doc['page']['hero_title'] = 'Portada de ensayo local'
        doc['menu']['barril'][0]['precios'][0]['precio'] += 13
        saved = self.change('PUT', '/cms/api/draft', {'document': doc, 'version': state['version']})
        self.assertEqual(saved.status_code, 200, saved.json)
        self.assertEqual(self.client.get('/data/menu.json').json, current)
        preview = self.client.get('/cms/preview/')
        self.assertIn(b'Portada de ensayo local', preview.data)
        published = self.change('POST', '/cms/api/publish', {'version': saved.json['version']})
        self.assertEqual(published.status_code, 200, published.json)
        self.assertIn(b'Portada de ensayo local', self.client.get('/').data)
        self.assertEqual(self.client.get('/data/menu.json').json['barril'][0]['precios'][0]['precio'],
                         current['barril'][0]['precios'][0]['precio'] + 13)
        self.assertEqual(self.client.get('/data/menu.json?v=1').json, current)
        with self.app.extensions['cms_db']() as db:
            active = db.execute("select r.output from revisions r join settings s on r.id=cast(s.value as integer) where s.key='published'").fetchone()
        self.assertEqual(json.loads(json.loads(active[0])['data/menu.json']), self.client.get('/data/menu.json').json)

    def test_preview_does_not_install_worker_or_enable_navigation(self):
        self.login()
        for path in ('/cms/preview/', '/cms/preview/menu/'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            soup = BeautifulSoup(response.data, 'html.parser')
            self.assertEqual(soup.body['data-cms-preview'], 'true')
            self.assertEqual(soup.body['data-menu-url'], '/cms/preview/data/menu.json')
            self.assertIsNone(soup.select_one('link[rel="manifest"]'))
            self.assertNotIn('serviceWorker.register', response.get_data(as_text=True))
            self.assertFalse(soup.select('a[href]'))
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get('/cms/preview/data/menu.json').status_code, 401)

    def test_variants_preserved_and_invalid_variant_price_rejected(self):
        doc = initial_document(ROOT / 'sitio')
        variant_item = next(it for cat in doc['menu']['comida'] for it in cat['items'] if it.get('variantes'))
        source_variants = deepcopy(variant_item['variantes'])
        self.assertEqual(validate_document(doc)['menu'], doc['menu'])
        self.assertEqual(variant_item['variantes'], source_variants)
        variant_item['variantes'][0]['precio'] = -1
        with self.assertRaises(ValueError): validate_document(doc)

    def test_hidden_flight_is_not_offered_in_published_or_preview_markup(self):
        doc = initial_document(ROOT / 'sitio')
        doc['menu']['vuelo']['visible'] = False
        for preview in (False, True):
            with self.subTest(preview=preview):
                output = render_document(doc, ROOT / 'sitio', preview=preview)
                flight = json.loads(output['data/menu.json'])['vuelo']
                self.assertFalse(flight['visible'])
                self.assertIsNone(flight['precio_desde'])
                for path in ('index.html', 'menu/index.html'):
                    soup = BeautifulSoup(output[path], 'html.parser')
                    self.assertTrue(soup.select_one('#vuelo').has_attr('hidden'))
                menu = BeautifulSoup(output['menu/index.html'], 'html.parser')
                if not preview:  # La vista previa elimina todos los href.
                    link = menu.select_one('a[href="#vuelo"]')
                    self.assertTrue(link.has_attr('hidden') or link.parent.has_attr('hidden'))
                self.assertIsNotNone(menu.select_one('#vuelo-opciones'))
                self.assertIsNotNone(menu.select_one('#pedido'))

    def test_flight_visibility_defaults_to_true_and_rejects_non_booleans(self):
        doc = initial_document(ROOT / 'sitio')
        doc['menu']['vuelo'].pop('visible', None)
        self.assertTrue(validate_document(doc)['menu']['vuelo']['visible'])
        output = render_document(doc, ROOT / 'sitio')
        flight = json.loads(output['data/menu.json'])['vuelo']
        self.assertTrue(flight['visible'])
        self.assertGreater(flight['precio_desde'], 0)
        for invalid in ('false', 0, None):
            doc['menu']['vuelo']['visible'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_document(doc)

    def test_admin_owner_guard_is_independent_of_dev_mode(self):
        self.app.config['CMS_DEV'] = False
        self.assertEqual(self.client.get('/admin/').status_code, 302)
        self.assertEqual(self.client.get('/admin/index.html').status_code, 302)
        login = self.login('editor')
        self.assertIn('Secure', login.headers['Set-Cookie'])
        self.assertEqual(self.client.get('/admin/').status_code, 403)
        self.assertEqual(self.client.get('/api/admin/socios').status_code, 403)
        self.login('owner')
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        response.close()

    def test_admin_proxy_uses_only_server_token_and_csrf(self):
        self.login()
        class Upstream:
            status = 200
            headers = {'Content-Type': 'application/json'}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"ok":true}'
        with patch('cms_server.urllib.request.urlopen', return_value=Upstream()) as upstream:
            response = self.client.get('/api/admin/socios', headers={'X-Cisne-Staff-Token': 'forged'})
            self.assertEqual(response.status_code, 200)
            forwarded = upstream.call_args.args[0]
            self.assertEqual(dict(forwarded.header_items())['X-cisne-staff-token'], 'test-internal-token')
            self.assertEqual(self.client.post('/api/admin/canje', json={}).status_code, 403)
            self.assertEqual(upstream.call_count, 1)

    def test_mediahub_image_is_private_until_published(self):
        self.login()
        data = io.BytesIO()
        Image.new('RGB', (24, 24), '#9b7e4a').save(data, 'PNG')
        data.seek(0)
        response = self.client.post('/cms/api/media', data={'file': (data, 'foto-prueba.png')},
                                    headers={'Origin': 'http://localhost', 'X-CSRF-Token': self.csrf})
        self.assertEqual(response.status_code, 201, response.json)
        url = response.json['item']['url']
        anon = self.app.test_client()
        self.assertEqual(anon.get(url).status_code, 404)
        state = self.client.get('/cms/api/state').json
        state['document']['page']['hero_image'] = url
        saved = self.change('PUT', '/cms/api/draft', {'document': state['document'], 'version': state['version']})
        self.assertEqual(self.change('POST', '/cms/api/publish', {'version': saved.json['version']}).status_code, 200)
        response = anon.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertIn(url.encode(), anon.get('/').data)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'Requiere ffmpeg y ffprobe')
    def test_mediahub_video_upload_processing_publication_and_range(self):
        video_path = Path(self.temp.name) / 'fixture.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'color=c=orange:s=160x90:d=1', '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p', '-threads', '1', str(video_path)], check=True, timeout=20)
        self.login()
        with video_path.open('rb') as video:
            uploaded = self.client.post('/cms/api/media', data={'file': (video, 'video-prueba.mp4')},
                headers={'Origin': 'http://localhost', 'X-CSRF-Token': self.csrf})
        self.assertEqual(uploaded.status_code, 201, uploaded.json)
        item = uploaded.json['item']
        self.assertEqual(item['kind'], 'video')
        store = self.app.extensions['cms_media']
        self.assertTrue(store.wait_for_idle(timeout=20))
        ready = store.get(item['id'])
        self.assertEqual(ready['status'], 'ready', ready.get('error'))
        anon = self.app.test_client()
        self.assertEqual(anon.get(item['url']).status_code, 404)
        state = self.client.get('/cms/api/state').json
        state['document']['page'].update(hero_mode='video', hero_video_desktop=item['url'], hero_video_mobile='')
        saved = self.change('PUT', '/cms/api/draft', {'document': state['document'], 'version': state['version']})
        self.assertEqual(self.change('POST', '/cms/api/publish', {'version': saved.json['version']}).status_code, 200)
        for url, headers, status in [(item['url'], {'Range': 'bytes=0-99'}, 206),
                                     (item['url'].replace('/file', '/thumb'), {}, 200)]:
            response = anon.get(url, headers=headers)
            self.assertEqual(response.status_code, status)
            self.assertTrue(response.data)
            response.close()
        soup = BeautifulSoup(anon.get('/').data, 'html.parser')
        self.assertEqual(soup.select_one('.hero video')['data-src'], item['url'])


if __name__ == '__main__': unittest.main()
