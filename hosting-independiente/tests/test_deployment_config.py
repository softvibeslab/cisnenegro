"""Orígenes temporales/finales con datos ficticios y bind explícito del servidor."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'scripts'))
from cms_server import create_app, now
from app import create_portable_app
from start import bind_host
from bs4 import BeautifulSoup
from werkzeug.security import generate_password_hash

TEMPORARY = 'https://cisne.softvibes.art'
FINAL = 'https://cisnenegro.mx'
WWW = 'https://www.cisnenegro.mx'
ALLOWED = ','.join((TEMPORARY, FINAL, WWW))


class DeploymentConfig(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cisne-domains-test-')
        self.addCleanup(self.temp.cleanup)

    def app(self, allowed=ALLOWED, origin=TEMPORARY, public_host='', portable=False):
        factory = create_portable_app if portable else create_app
        app = factory({'CMS_ROOT': self.temp.name, 'CMS_SITE': str(ROOT / 'sitio'),
            'CMS_DEV': False, 'CMS_ORIGIN': origin, 'CMS_ALLOWED_ORIGINS': allowed,
            'PUBLIC_INDEX_HOST': public_host, 'TESTING': True})
        self.addCleanup(app.extensions['cms_media'].close)
        with app.extensions['cms_db']() as con:
            con.execute('insert or ignore into users(username,name,password,role,created_at) values(?,?,?,?,?)',
                ('owner', 'Owner', generate_password_hash('deployment-test-password'), 'owner', now()))
        return app

    def login(self, client, target, origin):
        return client.post('/cms/api/login', base_url=target, headers={'Origin': origin},
            json={'username': 'owner', 'password': 'deployment-test-password'})

    def test_each_allowed_domain_can_login_with_host_only_secure_cookie(self):
        app = self.app()
        for origin in (TEMPORARY, FINAL, WWW):
            with self.subTest(origin=origin):
                response = self.login(app.test_client(), origin, origin)
                self.assertEqual(response.status_code, 200, response.json)
                cookie = response.headers['Set-Cookie']
                self.assertIn('Secure', cookie)
                self.assertIn('HttpOnly', cookie)
                self.assertNotIn('Domain=', cookie)

    def test_cross_domain_external_and_forged_host_origins_are_rejected(self):
        client = self.app().test_client()
        for target, origin in ((TEMPORARY, FINAL), (FINAL, TEMPORARY),
                (TEMPORARY, 'https://external.invalid'),
                ('https://external.invalid', 'https://external.invalid'),
                ('https://external.invalid', TEMPORARY),
                (TEMPORARY, 'null'), (TEMPORARY, TEMPORARY + '/unexpected')):
            with self.subTest(target=target, origin=origin):
                self.assertEqual(self.login(client, target, origin).status_code, 403)

    def test_unconfigured_allowlist_keeps_single_origin(self):
        client = self.app(allowed='').test_client()
        self.assertEqual(self.login(client, TEMPORARY, TEMPORARY).status_code, 200)
        self.assertEqual(self.login(client, FINAL, FINAL).status_code, 403)

    def test_allowed_origin_does_not_replace_csrf(self):
        client = self.app().test_client()
        login = self.login(client, FINAL, FINAL)
        self.assertEqual(login.status_code, 200)
        failed = client.post('/cms/api/logout', base_url=FINAL, json={}, headers={'Origin': FINAL})
        self.assertEqual(failed.status_code, 403)
        succeeded = client.post('/cms/api/logout', base_url=FINAL, json={},
            headers={'Origin': FINAL, 'X-CSRF-Token': login.json['csrf']})
        self.assertEqual(succeeded.status_code, 200)

    def test_invalid_configurations_fail_before_opening_data(self):
        for allowed in ('https://*.softvibes.art', TEMPORARY + '/cms',
                TEMPORARY + '?redirect=x', TEMPORARY + '#x',
                'https://user:password@cisne.softvibes.art',
                'http://cisne.softvibes.art', TEMPORARY + ',', FINAL):
            with self.subTest(allowed=allowed), self.assertRaises(ValueError):
                self.app(allowed=allowed)

    def test_bind_defaults_and_explicit_loopback(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(bind_host(False), '127.0.0.1')
            self.assertEqual(bind_host(True), '0.0.0.0')
        with patch.dict(os.environ, {'APP_BIND': '127.0.0.1'}):
            self.assertEqual(bind_host(True), '127.0.0.1')
        for invalid in ('', 'localhost', '0.0.0.0:8080', '0.0.0.0 --reload'):
            with patch.dict(os.environ, {'APP_BIND': invalid}), self.assertRaises(ValueError):
                bind_host(True)

    def test_only_configured_final_https_host_indexes_public_html(self):
        client = self.app(public_host='cisnenegro.mx', portable=True).test_client()
        for path in ('/', '/index.html', '/menu/', '/menu/index.html', '/privacidad/', '/privacidad/index.html'):
            for origin, expected in ((FINAL, 'index, follow'), (TEMPORARY, 'noindex, nofollow'),
                    (WWW, 'noindex, nofollow'), ('http://cisnenegro.mx', 'noindex, nofollow')):
                with self.subTest(path=path, origin=origin), client.get(path, base_url=origin) as response:
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.headers['X-Robots-Tag'], expected)
                    meta = BeautifulSoup(response.data, 'html.parser').select_one('meta[name="robots"]')
                    self.assertEqual(meta['content'].replace(' ', ''), expected.replace(' ', ''))

    def test_final_host_private_routes_errors_and_historical_preview_stay_noindex(self):
        client = self.app(public_host='cisnenegro.mx', portable=True).test_client()
        for path in ('/cms/', '/cms/api/session', '/admin/', '/equipo/', '/unknown', '/cms/preview/'):
            with self.subTest(path=path), client.get(path, base_url=FINAL) as response:
                self.assertEqual(response.headers['X-Robots-Tag'], 'noindex, nofollow')
        with client.get('/?v=999999', base_url=FINAL) as response:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.headers['X-Robots-Tag'], 'noindex, nofollow')

    def test_indexing_is_disabled_by_default(self):
        client = self.app(portable=True).test_client()
        with client.get('/', base_url=FINAL) as response:
            self.assertEqual(response.headers['X-Robots-Tag'], 'noindex, nofollow')
            self.assertIn(b'noindex', response.data)
        self.assertEqual(client.get('/sitemap.xml', base_url=FINAL).status_code, 404)
        self.assertIn(b'Disallow: /\n', client.get('/robots.txt', base_url=FINAL).data)

    def test_robots_and_sitemap_are_enabled_only_on_final_https_host(self):
        client = self.app(public_host='cisnenegro.mx', portable=True).test_client()
        for origin in (TEMPORARY, WWW, 'http://cisnenegro.mx', 'https://external.invalid'):
            self.assertEqual(client.get('/sitemap.xml', base_url=origin).status_code, 404)
            self.assertEqual(client.get('/robots.txt', base_url=origin).data, b'User-agent: *\nDisallow: /\n')
        response = client.get('/sitemap.xml', base_url=FINAL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b'<url>'), 3)
        self.assertIn(b'https://cisnenegro.mx/menu/', response.data)
        robots = client.get('/robots.txt', base_url=FINAL).data
        self.assertIn(b'Allow: /\n', robots)
        self.assertIn(b'Disallow: /cms\n', robots)
        self.assertIn(b'Sitemap: https://cisnenegro.mx/sitemap.xml', robots)

    def test_saved_publication_metadata_uses_apex_without_changing_content_or_database(self):
        app = self.app(origin=FINAL, public_host='cisnenegro.mx', portable=True)
        old_html = '''<!doctype html><html><head><meta name="robots" content="noindex,nofollow">
          <link rel="canonical" href="https://www.cisnenegro.mx/index.html">
          <meta property="og:url" content="https://www.cisnenegro.mx/">
          <meta property="og:image" content="https://www.cisnenegro.mx/assets/a.jpg?size=1">
          <meta name="twitter:image" content="https://images.example/a.jpg">
          <script type="application/ld+json">{"@context":"https://schema.org","url":"https://www.cisnenegro.mx/",
          "image":"/assets/a.jpg","logo":{"url":"https://cisne.softvibes.art/assets/logo.png"},
          "menu":"https://www.cisnenegro.mx/menu/","sameAs":["https://instagram.com/cisne"],
          "description":"https://www.cisnenegro.mx/","name":"Cisne & Negro"}</script></head>
          <body><a href="https://www.cisnenegro.mx/menu/">Editorial intacto</a></body></html>'''
        with app.extensions['cms_db']() as con:
            row = con.execute('select id, output from revisions order by id desc limit 1').fetchone()
            output = json.loads(row['output'])
            output['index.html'] = old_html
            con.execute('update revisions set output=? where id=?', (json.dumps(output), row['id']))
            before_revisions = [tuple(row) for row in con.execute('select * from revisions')]
            before_draft = [tuple(row) for row in con.execute('select * from draft')]
        client = app.test_client()
        response = client.get('/index.html?utm_source=test', base_url=FINAL)
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.data, 'html.parser')
        self.assertEqual(soup.select_one('link[rel="canonical"]')['href'], FINAL + '/')
        self.assertEqual(soup.select_one('meta[property="og:url"]')['content'], FINAL + '/')
        self.assertEqual(soup.select_one('meta[property="og:image"]')['content'], FINAL + '/assets/a.jpg?size=1')
        self.assertEqual(soup.select_one('meta[name="twitter:image"]')['content'], 'https://images.example/a.jpg')
        self.assertEqual(soup.a['href'], WWW + '/menu/')
        linked = json.loads(soup.select_one('script[type="application/ld+json"]').string)
        self.assertEqual(linked['url'], FINAL + '/')
        self.assertEqual(linked['image'], FINAL + '/assets/a.jpg')
        self.assertEqual(linked['logo']['url'], FINAL + '/assets/logo.png')
        self.assertEqual(linked['menu'], FINAL + '/menu/')
        self.assertEqual(linked['sameAs'], ['https://instagram.com/cisne'])
        self.assertEqual(linked['description'], WWW + '/')
        self.assertEqual(linked['name'], 'Cisne & Negro')
        self.assertEqual(client.get('/', base_url=TEMPORARY).get_data(as_text=True), old_html)
        with app.extensions['cms_db']() as con:
            self.assertEqual(before_revisions, [tuple(row) for row in con.execute('select * from revisions')])
            self.assertEqual(before_draft, [tuple(row) for row in con.execute('select * from draft')])

    def test_each_public_page_has_one_clean_canonical_url(self):
        client = self.app(public_host='cisnenegro.mx', portable=True).test_client()
        for path in ('/', '/index.html', '/menu/', '/menu/index.html', '/privacidad/', '/privacidad/index.html'):
            with self.subTest(path=path), client.get(path + '?utm_source=test', base_url=FINAL) as response:
                soup = BeautifulSoup(response.data, 'html.parser')
                links = soup.select('link[rel="canonical"]')
                self.assertEqual(len(links), 1)
                self.assertEqual(links[0]['href'], FINAL + path.removesuffix('index.html'))

    def test_public_index_host_must_be_explicit_allowed_dns_hostname(self):
        for host in ('https://www.cisnenegro.mx', 'www.cisnenegro.mx:443', 'www.cisnenegro.mx/menu',
                '*.cisnenegro.mx', 'external.invalid', '127.0.0.1', ['www.cisnenegro.mx']):
            with self.subTest(host=host), self.assertRaises(ValueError):
                self.app(public_host=host)


if __name__ == '__main__':
    unittest.main()
