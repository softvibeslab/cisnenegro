"""Pruebas de contenido con datos públicos; nunca abre la base del Pasaporte.

uv run --with beautifulsoup4 python -m unittest discover -s tests -p test_cms_content.py
"""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from cms_content import editor_fields, initial_document, media_url, render_document, validate_document


def products(menu):
    return menu['barril'] + menu['latas'] + menu['sin_alcohol'] + [it for section in menu['comida'] for it in section['items']]


class ContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial = initial_document(ROOT / 'sitio')
        cls.legacy = json.loads((ROOT / 'sitio/data/menu.json').read_text())

    def setUp(self):
        self.doc = deepcopy(self.initial)

    def render(self, **kwargs):
        files = render_document(self.doc, ROOT / 'sitio', **kwargs)
        return files, BeautifulSoup(files['index.html'], 'html.parser'), json.loads(files['data/menu.json'])

    def test_import_is_deterministic_and_preserves_49_products(self):
        self.assertEqual(self.initial, initial_document(ROOT / 'sitio'))
        items = products(self.doc['menu'])
        self.assertEqual(len(items), 49)
        self.assertEqual(len({it['id'] for it in items}), 49)
        self.assertTrue(all(it['visible'] and it['disponible'] for it in items))
        for before, after in zip(products(self.legacy), items):
            for field, value in before.items():
                self.assertEqual(after[field], value, field)
        self.assertEqual(len(self.doc['gallery']), 8)
        self.assertEqual(len(self.doc['events']), 3)

    def test_initial_render_preserves_visible_copy_and_image_hero(self):
        _, soup, _ = self.render()
        original = BeautifulSoup((ROOT / 'sitio/index.html').read_text(), 'html.parser')
        self.assertEqual(soup.body.get_text(' ', strip=True), original.body.get_text(' ', strip=True))
        self.assertEqual(soup.select_one('.hero > img')['src'], original.select_one('.hero > img')['src'])
        self.assertIsNone(soup.select_one('.hero video'))
        self.assertEqual(len(soup.select('.pairs .pair')), 4)

    def test_renderer_is_pure_and_revision_is_pinned(self):
        before = deepcopy(self.doc)
        files, soup, menu = self.render(revision='rev-17')
        self.assertEqual(before, self.doc)
        self.assertEqual(set(files), {'index.html', 'menu/index.html', 'data/menu.json'})
        self.assertEqual(soup.body['data-menu-url'], '/data/menu.json?v=rev-17')
        self.assertEqual(menu['_meta']['revision'], 'rev-17')
        menu_soup = BeautifulSoup(files['menu/index.html'], 'html.parser')
        self.assertEqual(menu_soup.body['data-menu-url'], '/data/menu.json?v=rev-17')
        self.assertEqual(soup.select_one('script[src*="landing.js"]')['src'], '/assets/js/landing.js?v=cms-20261008-2')
        self.assertEqual(menu_soup.select_one('script[src*="menu.js"]')['src'], '/assets/js/menu.js?v=cms-20261008-2')

    def test_contact_and_schema_change_together(self):
        business = self.doc['menu']['negocio']
        business.update(telefono='+527719990000', telefono_display='771 999 0000', email='equipo@ejemplo.mx',
                        direccion='Calle de Prueba 12, Pachuca', whatsapp_url='https://wa.me/527719990000',
                        horario=[{'dias': 'Martes a domingo', 'horas': '17:00 – 23:00'}],
                        geo={'lat': 20.12, 'lng': -98.73})
        self.doc['page']['seo_title'] = 'Cerveza y comunidad | Cisne Negro'
        self.doc['page']['seo_description'] = 'Nueva descripción con acentos y información.'
        _, soup, menu = self.render()
        self.assertEqual(soup.title.string, self.doc['page']['seo_title'])
        self.assertEqual(soup.select_one('meta[name="description"]')['content'], self.doc['page']['seo_description'])
        self.assertTrue(all(a['href'] == 'tel:+527719990000' for a in soup.select('a[href^="tel:"]')))
        self.assertEqual(soup.select_one('.visit__addr').get_text(), business['direccion'])
        self.assertEqual(soup.select_one('.hours td').get_text(), '17:00 – 23:00')
        schema = json.loads(soup.select_one('script[type="application/ld+json"]').string)
        self.assertEqual(schema['telephone'], business['telefono'])
        self.assertEqual(schema['email'], business['email'])
        self.assertEqual(schema['address'], business['direccion'])
        self.assertEqual(len(schema['openingHoursSpecification']), 1)
        self.assertEqual(schema['openingHoursSpecification'][0]['dayOfWeek'], ['Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
        self.assertEqual(menu['negocio'], business)

    def test_prices_and_visibility_are_consistent(self):
        self.doc['menu']['barril'][0]['visible'] = False
        self.doc['menu']['barril'][1]['disponible'] = False
        self.doc['menu']['latas'][0]['visible'] = False
        self.doc['menu']['sin_alcohol'][0]['disponible'] = False
        self.doc['menu']['comida'][0]['visible'] = False
        self.doc['menu']['barril'][2]['precios'][1]['precio'] = 90
        _, soup, menu = self.render()
        self.assertNotIn('alarma', {b['id'] for b in menu['barril']})
        self.assertNotIn('henry-ix', {b['id'] for b in menu['barril']})
        self.assertEqual(menu['barril'][0]['precios'][1]['precio'], 90)
        self.assertEqual(menu['vuelo']['precio_desde'], 200)
        food_ids = {it['id'] for cat in menu['comida'] for it in cat['items']}
        self.assertTrue(all(ref in food_ids for b in menu['barril'] for ref in b['marida_con']))
        self.assertEqual(len(menu['latas']), 17)
        self.assertEqual(len(menu['sin_alcohol']), 4)
        self.assertEqual(len(soup.select('.pairs .pair')), 1)
        self.assertNotIn('camarones-piedra', food_ids)

    def test_no_available_products_is_a_valid_publication(self):
        for item in products(self.doc['menu']):
            item['disponible'] = False
        _, soup, menu = self.render()
        self.assertEqual(products(menu), [])
        self.assertIsNone(menu['vuelo']['precio_desde'])
        self.assertEqual(soup.select('.pairs .pair'), [])

    def test_mediahub_and_structured_collections_render(self):
        self.doc['page']['hero_image'] = '/cms/media/hero_123/file'
        self.doc['gallery'][0]['image'] = '/cms/media/gallery-4/file'
        self.doc['gallery'][0]['caption'] = 'Fotografía nueva'
        self.doc['events'][0].update(image='/cms/media/event-4/file', title='Noche de cerveza',
                                      date='2026-11-20', description='Música y cocina', url='https://ejemplo.mx/evento')
        self.doc['events'][1]['visible'] = False
        _, soup, _ = self.render()
        self.assertEqual(soup.select_one('.hero > img')['src'], '/cms/media/hero_123/file')
        self.assertEqual(soup.select_one('[data-gallery] img')['src'], '/cms/media/gallery-4/file')
        self.assertEqual(soup.select_one('.gallery__caption').get_text(), 'Fotografía nueva')
        self.assertEqual(len(soup.select('.events .event')), 2)
        self.assertEqual(soup.select_one('.events h3').get_text(), 'Noche de cerveza')
        self.assertEqual(soup.select_one('.events a')['href'], 'https://ejemplo.mx/evento')

    def test_video_mode_has_poster_and_mobile_fallback(self):
        self.doc['page'].update(hero_mode='video', hero_video_desktop='/cms/media/video-1/file',
                                hero_video_mobile='', hero_poster='/cms/media/poster-1/file')
        _, soup, _ = self.render()
        video = soup.select_one('.hero video')
        self.assertEqual(video['data-src'], '/cms/media/video-1/file')
        self.assertEqual(video['data-mobile-src'], '/cms/media/video-1/file')
        self.assertEqual(video['poster'], '/cms/media/poster-1/file')
        self.assertTrue(video.has_attr('muted') and video.has_attr('playsinline'))
        self.assertIsNotNone(soup.select_one('.hero__video-control'))
        self.assertIsNotNone(soup.select_one('script[src="/assets/js/hero-video.js"]'))

    def test_focal_points_are_captured_in_html_and_published_menu(self):
        poster, video, gallery, beer = ['/cms/media/' + key + '/file' for key in ('poster', 'video', 'gallery', 'beer')]
        self.doc['page'].update(hero_mode='video', hero_video_desktop=video, hero_poster=poster)
        self.doc['gallery'][0]['image'] = gallery
        self.doc['menu']['barril'][0]['img'] = beer
        focal = {poster: {'x': 0, 'y': 1}, video: {'x': 0.25, 'y': 0.75},
                 gallery: {'x': 0.8, 'y': 0.2}, beer: {'x': 0.3, 'y': 0.4}}
        before = deepcopy(self.doc)
        for preview in (False, True):
            files, soup, menu = self.render(preview=preview, revision=23, media_focal=focal)
            self.assertEqual(soup.select_one('.hero > img')['style'], 'object-position:0% 100%')
            self.assertEqual(soup.select_one('.hero video')['style'], 'object-position:25% 75%')
            self.assertEqual(soup.select_one('[data-gallery] img')['style'], 'object-position:80% 20%')
            self.assertEqual(soup.select_one('.pairs .pair__vaso')['style'], 'object-position:30% 40%')
            self.assertEqual(menu['_media_focal'], focal)
            self.assertEqual(menu['_meta']['revision'], '23')
            self.assertEqual(self.doc, before)
        captured = files['data/menu.json']
        focal[video]['x'] = 1
        self.assertEqual(json.loads(captured)['_media_focal'][video]['x'], 0.25)

    def test_focal_map_rejects_external_urls_and_invalid_coordinates(self):
        for url in ('https://example.org/cms/media/id/file', '/assets/photo.jpg', '/cms/media/id/file?x=1'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.render(media_focal={url: {'x': 0.5, 'y': 0.5}})
        for value in (-1, 1.01, True, '0.5', float('nan'), float('inf'), None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.render(media_focal={'/cms/media/id/file': {'x': value, 'y': 0.5}})

    def test_preview_does_not_navigate_and_preserves_editor_indexes(self):
        self.doc['menu']['barril'][0]['visible'] = False
        files, soup, menu = self.render(preview=True, revision='ignored')
        self.assertEqual(soup.body['data-menu-url'], '/cms/preview/data/menu.json')
        self.assertEqual(soup.body['data-cms-preview'], 'true')
        self.assertEqual(soup.select_one('.hero__title')['data-cms-key'], 'page.hero_title')
        self.assertEqual(menu['barril'][0]['_cms_key'], 'menu.barril.1')
        self.assertEqual(soup.select('a[href]'), [])
        self.assertIn("{type: 'cms-select', key: field.dataset.cmsKey}, location.origin", files['index.html'])
        self.assertNotIn('postMessage({type: \'cms-select\', key: field.dataset.cmsKey}, \'*\')', files['index.html'])
        self.assertEqual(BeautifulSoup(files['menu/index.html'], 'html.parser').select('form[action]'), [])

    def test_plain_text_and_jsonld_cannot_inject_markup(self):
        payload = '</script><script>alert(1)</script><img src=x onerror=alert(2)>'
        self.doc['page']['hero_title'] = payload
        self.doc['page']['schema_description'] = payload
        self.doc['events'][0]['title'] = payload
        self.doc['gallery'][0]['alt'] = '" onerror="alert(2)'
        files, soup, _ = self.render()
        self.assertEqual(soup.select_one('.hero__title').get_text(), payload)
        self.assertEqual(soup.select('[onerror]'), [])
        self.assertEqual(json.loads(soup.select_one('script[type="application/ld+json"]').string)['description'], payload)
        self.assertNotIn('<script>alert(1)</script>', files['index.html'])

    def test_malicious_media_and_links_are_rejected(self):
        for url in ['javascript:alert(1)', 'data:image/svg+xml,<svg/>', '//evil.test/x.jpg',
                    '/assets/../secret.jpg', '/assets/%2e%2e/secret.jpg', '/assets/file.svg',
                    'https://example.org/image.svg?ok=1', '/assets/file.js', '/private/file.jpg',
                    '/cms/media/id/../../../secret', 'http://example.org/file.jpg']:
            with self.subTest(url=url):
                doc = deepcopy(self.doc)
                doc['page']['hero_image'] = url
                with self.assertRaises(ValueError):
                    validate_document(doc)
        for url in ['javascript:alert(1)', 'data:text/html,hello', '//evil.test', '/%2f/evil.test']:
            doc = deepcopy(self.doc)
            doc['events'][0]['url'] = url
            with self.assertRaises(ValueError):
                validate_document(doc)
        self.assertEqual(media_url('/cms/media/abc/file'), '/cms/media/abc/file')
        self.assertEqual(media_url('etiquetas/alarma.jpg', 'cervezas'), '/assets/img/cervezas/etiquetas/alarma.jpg')

    def test_invalid_prices_ids_and_relations_are_rejected(self):
        for invalid in (-1, float('nan'), float('inf'), True, '100'):
            doc = deepcopy(self.doc)
            doc['menu']['barril'][0]['precios'][0]['precio'] = invalid
            with self.assertRaises(ValueError):
                validate_document(doc)
        doc = deepcopy(self.doc)
        doc['menu']['latas'][0]['id'] = doc['menu']['barril'][0]['id']
        with self.assertRaises(ValueError):
            validate_document(doc)
        doc = deepcopy(self.doc)
        doc['menu']['barril'][0]['marida_con'] = ['inexistente']
        with self.assertRaisesRegex(ValueError, 'Maridaje'):
            validate_document(doc)

    def test_flight_does_not_count_one_beer_twice(self):
        self.doc['menu']['barril'][0]['precios'].append({'medida': '4oz', 'precio': 1})
        with self.assertRaisesRegex(ValueError, 'repetir'):
            validate_document(self.doc)

    def test_editor_fields_are_valid_paths_and_ids_are_not_editable(self):
        fields = editor_fields(self.doc)
        self.assertEqual(len({f['key'] for f in fields}), len(fields))
        for field in fields:
            value = self.doc
            for part in field['key'].split('.'):
                value = value[int(part)] if isinstance(value, list) else value[part]
            self.assertFalse(field['key'].endswith('.id'))
        by_key = {field['key']: field for field in fields}
        self.assertEqual(by_key['page.hero_mode']['type'], 'select')
        self.assertEqual(by_key['menu.barril.0.marida_con']['type'], 'multiselect')
        self.assertNotIn('menu.negocio.google_review_url', by_key)

    @unittest.skipUnless(shutil.which('node'), 'Node no está disponible para verificar consumidores JS')
    def test_browser_helpers_use_mediahub_and_filter_unavailable(self):
        script = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const start = source.indexOf('  function dishLabel(item)');
const end = source.indexOf('  // ── Catálogo', start);
const context = { CMS_PREVIEW: false };
vm.runInNewContext(source.slice(start, end), context);
assert.equal(context.mediaUrl('/cms/media/id/file', 'menu'), '/cms/media/id/file');
assert.equal(context.mediaUrl('old.jpg', 'menu'), '/assets/img/menu/old.jpg');
assert.equal(context.mediaUrl('javascript:alert(1)', 'menu'), '');
assert.equal(context.dishLabel({id:'x', nombre:'De la casa', nombre_completo:'Plato del día', img:'renamed.jpg'}), 'Plato del día');
assert.equal(context.dishLabel({id:'hamburguesa-suadero', nombre:'De Suadero', img:'/cms/media/new/file'}), 'Sándwich de Suadero');
const data = context.menuDisponible({ barril:[{id:'a',disponible:false},{id:'b'}], latas:[{visible:false}], sin_alcohol:[], comida:[{visible:false,items:[{id:'c'}]},{items:[{id:'d',visible:false},{id:'e'}]}] });
assert.equal(data.barril.length, 1); assert.equal(data.barril[0].id, 'b');
assert.equal(data.latas.length, 0); assert.equal(data.comida.length, 1); assert.equal(data.comida[0].items[0].id, 'e');
assert(source.includes('if (!CMS_PREVIEW) iniciarPasaporte();'));
const url = '/cms/media/test/file', map = {[url]: {x:0.2,y:0.9}};
context.state = {data:{_media_focal:map}};
context.document = {createElement: () => ({style:{}, setAttribute(){}, append(){}})};
vm.runInNewContext(source.slice(source.indexOf('  function h(tag'), source.indexOf('  function svgUse')), context);
assert.equal(context.h('img', {src:url}).style.objectPosition, '20% 90%');
const image = {style:{}};
context.applyMediaFocal(image, url + '?v=1', map);
assert.equal(image.style.objectPosition, '20% 90%');
context.applyMediaFocal(image, '/assets/no-focal.jpg', map);
assert.equal(image.style.objectPosition, '');
context.applyMediaFocal(image, url, {[url]: {x:'0.2',y:0.9}});
assert.equal(image.style.objectPosition, '');
const landing = fs.readFileSync(process.argv[2], 'utf8');
vm.runInNewContext(landing.slice(landing.indexOf('  function applyMediaFocal('), landing.indexOf('  function indexDishes(')), context);
context.applyMediaFocal(image, url, map);
assert.equal(image.style.objectPosition, '20% 90%');
"""
        subprocess.run(['node', '-e', script, str(ROOT / 'sitio/assets/js/menu.js'), str(ROOT / 'sitio/assets/js/landing.js')], check=True, capture_output=True, text=True)
        for name in ('menu', 'landing'):
            subprocess.run(['node', '--check', str(ROOT / f'sitio/assets/js/{name}.js')], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
