from contextlib import closing
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'scripts'))
from cms_server import create_app
from cms_content import initial_document
from prepare_import import adapt_document, prepare, rebase


class ImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)
        self.app = create_app({'CMS_ROOT': str(self.data / 'cms'), 'CMS_SITE': str(ROOT / 'sitio'),
                              'CMS_DEV': True, 'CMS_ORIGIN': 'http://localhost'})
        self.app.extensions['cms_media'].close()
        self.db = self.data / 'cms/cms.sqlite'
        with closing(sqlite3.connect(self.db)) as con, con:
            draft = json.loads(con.execute('select data from draft').fetchone()[0])
            draft['page']['hero_title'] = 'BORRADOR SIN PUBLICAR'
            con.execute('update draft set data=?', (json.dumps(draft),))
            con.execute('update revisions set output=?', (json.dumps({'index.html': 'PLANTILLA ANTERIOR'}),))
            self.before_draft = con.execute('select * from draft').fetchall()

    def tearDown(self):
        self.temp.cleanup()

    def test_rebuild_preserves_unpublished_draft_pointer_and_backup(self):
        result = prepare(self.data)
        self.assertEqual(result['published'], 1)
        with closing(sqlite3.connect(self.db)) as con:
            output = json.loads(con.execute('select output from revisions').fetchone()[0])
            self.assertNotIn('BORRADOR SIN PUBLICAR', output['index.html'])
            self.assertIn('data-menu-url', output['index.html'])
            self.assertEqual(self.before_draft, con.execute('select * from draft').fetchall())
        with closing(sqlite3.connect(result['backup'])) as backup:
            self.assertEqual(json.loads(backup.execute('select output from revisions').fetchone()[0]),
                             {'index.html': 'PLANTILLA ANTERIOR'})

    def test_invalid_render_does_not_partially_migrate(self):
        with patch('prepare_import.render_document', side_effect=ValueError('No compatible')):
            with self.assertRaises(ValueError):
                prepare(self.data)
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(json.loads(con.execute('select output from revisions').fetchone()[0]),
                             {'index.html': 'PLANTILLA ANTERIOR'})
        self.assertEqual(list((self.data / 'cms').glob('cms.before*')), [])

    def test_running_destination_is_rejected(self):
        with (self.data / 'runtime.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, 'Detén'):
                prepare(self.data)

    def test_only_exact_old_origin_is_rebased(self):
        data = {'image': 'https://cisnenegro.softvibes.art/assets/img/lugar/neon.jpg',
                'links': ['http://cisnenegro.softvibes.art/v2/menu/?mesa=1',
                          'https://cisnenegro.softvibes.art.ejemplo.com/foto.jpg',
                          'https://externo.example/foto.jpg']}
        result = rebase(data)
        self.assertEqual(result['image'], '/assets/img/lugar/neon.jpg')
        self.assertEqual(result['links'][0], 'https://cisnenegro.mx/menu/?mesa=1')
        self.assertEqual(result['links'][1:], data['links'][1:])

    def test_ids_match_group_name_and_brewery_preserving_editorial_fields(self):
        baseline = initial_document(ROOT / 'sitio')
        source = deepcopy(baseline)
        original = source['menu']['latas'][0]
        target_id = original['id']
        original.update(id='latas-id-anterior', precio=999, visible=False, disponible=False,
                        nombre_completo='Nombre editorial', descripcion='Descripción editorial')
        source['menu']['sin_alcohol'][0]['id'] = 'sin_alcohol-anterior'
        extra = deepcopy(original)
        extra.update(id='producto-editorial-nuevo', nombre='Otra cerveza de borrador')
        source['menu']['latas'].append(extra)
        result = adapt_document(source, baseline)
        self.assertEqual(result['menu']['latas'][0], dict(original, id=target_id))
        self.assertEqual(result['menu']['sin_alcohol'][0]['id'], baseline['menu']['sin_alcohol'][0]['id'])
        self.assertEqual(result['menu']['latas'][-1], extra)
        self.assertEqual(source['menu']['latas'][0]['id'], 'latas-id-anterior')

    def test_missing_variants_added_existing_prices_and_draft_variants_preserved(self):
        baseline = initial_document(ROOT / 'sitio')
        source = deepcopy(baseline)
        food = next(i for c in source['menu']['comida'] for i in c['items'] if i['id'] == 'chips-camote')
        food['precio'] = 89
        food['variantes'] = [{'id': '55g', 'nombre': 'Chico editorial', 'precio': 89},
                            {'id': 'especial', 'nombre': 'Especial nuevo', 'precio': 200}]
        water = next(i for i in source['menu']['sin_alcohol'] if i['id'] == 'bebida-agua-mineral')
        water.pop('variantes')
        water['id'] = 'sin_alcohol-agua-mineral'
        result = adapt_document(source, baseline)
        migrated_food = next(i for c in result['menu']['comida'] for i in c['items'] if i['id'] == 'chips-camote')
        self.assertEqual(migrated_food['precio'], 89)
        self.assertEqual(migrated_food['variantes'][:2], food['variantes'])
        self.assertEqual(migrated_food['variantes'][2], {'id': '110g', 'nombre': '110 g', 'precio': 135})
        migrated_water = next(i for i in result['menu']['sin_alcohol'] if i['id'] == 'bebida-agua-mineral')
        self.assertEqual([v['precio'] for v in migrated_water['variantes']], [35, 45])

    def test_ambiguous_names_and_duplicate_targets_are_rejected(self):
        baseline = initial_document(ROOT / 'sitio')
        source = deepcopy(baseline)
        source['menu']['latas'][0]['id'] = 'latas-anterior'
        ambiguous = deepcopy(baseline)
        ambiguous['menu']['latas'].append(dict(ambiguous['menu']['latas'][0], id='otra-identidad'))
        with self.assertRaisesRegex(ValueError, 'ambigua'):
            adapt_document(source, ambiguous)
        source['menu']['latas'].append(dict(source['menu']['latas'][0], id='otra-copia'))
        with self.assertRaisesRegex(ValueError, 'Dos productos'):
            adapt_document(source, baseline)

    def test_adaptation_is_idempotent_and_keeps_social_image_absolute(self):
        baseline = initial_document(ROOT / 'sitio')
        source = deepcopy(baseline)
        source['menu']['latas'][0]['id'] = 'latas-anterior'
        source['page']['hero_image'] = 'https://cisnenegro.softvibes.art/v2/assets/img/lugar/neon.jpg'
        source['page']['social_image'] = 'https://cisnenegro.softvibes.art/assets/img/lugar/neon.jpg'
        source['gallery'][0]['image'] = 'https://cisnenegro.softvibes.art/cms/media/foto-1/file'
        result = adapt_document(source, baseline)
        self.assertEqual(result['page']['hero_image'], '/assets/img/lugar/neon.jpg')
        self.assertEqual(result['page']['social_image'], 'https://cisnenegro.mx/assets/img/lugar/neon.jpg')
        self.assertEqual(result['gallery'][0]['image'], '/cms/media/foto-1/file')
        self.assertEqual(adapt_document(result, baseline), result)

    def test_missing_asset_or_media_only_in_draft_blocks_all_writes(self):
        for path in ('/assets/img/no-existe.jpg', '/cms/media/no-existe/file'):
            with self.subTest(path=path):
                with closing(sqlite3.connect(self.db)) as con, con:
                    draft = json.loads(con.execute('select data from draft').fetchone()[0])
                    # Poster in image mode still needs to exist before switching to video.
                    draft['page']['hero_poster'] = path
                    con.execute('update draft set data=?', (json.dumps(draft),))
                with self.assertRaisesRegex(ValueError, 'borrador'):
                    prepare(self.data)
                with closing(sqlite3.connect(self.db)) as con:
                    self.assertEqual(json.loads(con.execute('select output from revisions').fetchone()[0]),
                                     {'index.html': 'PLANTILLA ANTERIOR'})
                self.assertEqual(list((self.data / 'cms').glob('cms.before*')), [])

    def test_both_revision_and_draft_ids_migrate_without_publishing_draft_prices(self):
        with closing(sqlite3.connect(self.db)) as con, con:
            draft = json.loads(con.execute('select data from draft').fetchone()[0])
            revision = json.loads(con.execute('select data from revisions').fetchone()[0])
            canonical_id = draft['menu']['latas'][0]['id']
            price = revision['menu']['latas'][0]['precio']
            for doc in (draft, revision):
                doc['menu']['latas'][0]['id'] = 'latas-anterior'
            draft['menu']['latas'][0]['precio'] = 999
            con.execute('update draft set data=?', (json.dumps(draft),))
            con.execute('update revisions set data=?', (json.dumps(revision),))
        result = prepare(self.data)
        with closing(sqlite3.connect(self.db)) as con:
            draft_after = json.loads(con.execute('select data from draft').fetchone()[0])
            output = json.loads(con.execute('select output from revisions').fetchone()[0])
            published_menu = json.loads(output['data/menu.json'])
            self.assertEqual(draft_after['menu']['latas'][0]['id'], canonical_id)
            self.assertEqual(draft_after['menu']['latas'][0]['precio'], 999)
            self.assertEqual(published_menu['latas'][0]['id'], canonical_id)
            self.assertEqual(published_menu['latas'][0]['precio'], price)
            self.assertEqual(con.execute("select value from settings where key='published'").fetchone()[0], '1')
        with closing(sqlite3.connect(result['backup'])) as con:
            old = json.loads(con.execute('select data from draft').fetchone()[0])
            self.assertEqual(old['menu']['latas'][0]['id'], 'latas-anterior')


if __name__ == '__main__':
    unittest.main()
