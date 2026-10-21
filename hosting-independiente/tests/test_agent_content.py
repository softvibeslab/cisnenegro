"""CRUD editorial del agente sobre bases efímeras, sin servicios externos."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from agent_content import apply_operation, read_content
from cms_content import initial_document
from cms_server import create_app, now
from werkzeug.security import generate_password_hash


class AgentContent(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({'CMS_ROOT': self.temp.name, 'CMS_SITE': str(ROOT / 'sitio'),
                              'CMS_DEV': True, 'CMS_ORIGIN': 'http://localhost', 'TESTING': True})
        with self.app.extensions['cms_db']() as con:
            for role in ('owner', 'editor'):
                con.execute('insert into users(username,name,password,role,created_at) values(?,?,?,?,?)',
                            (role, role, generate_password_hash('agent-test-password'), role, now()))
        self.client = self.app.test_client()
        login = self.client.post('/cms/api/login', json={'username': 'editor', 'password': 'agent-test-password'},
                                 headers={'Origin': 'http://localhost'})
        self.assertEqual(login.status_code, 200, login.json)
        self.headers = {'Origin': 'http://localhost', 'X-CSRF-Token': login.json['csrf']}

    def tearDown(self):
        self.app.extensions['cms_media'].close()
        self.temp.cleanup()

    def state(self):
        response = self.client.get('/cms/api/agent/content')
        self.assertEqual(response.status_code, 200, response.json)
        return response.json

    def mutate(self, operation, version=None):
        if version is None:
            version = self.state()['version']
        return self.client.post('/cms/api/agent/content',
                                json={'version': version, 'operation': operation}, headers=self.headers)

    def test_editor_can_create_read_update_delete_beer_only_in_draft(self):
        before = self.state()
        live_before = self.client.get('/data/menu.json').json
        data = {'nombre': 'Cerveza de prueba', 'estilo': 'IPA', 'abv': 5.5,
                'perfil': next(iter(before['document']['menu']['perfiles'])),
                'precios': [{'medida': '16 oz', 'precio': 100}], 'visible': False}
        created = self.mutate({'action': 'create', 'collection': 'barril', 'id': 'ensayo-ipa', 'data': data})
        self.assertEqual(created.status_code, 200, created.json)
        self.assertEqual(created.json['version'], before['version'] + 1)
        self.assertIsNone(created.json['change']['before'])
        self.assertFalse(created.json['change']['after']['visible'])
        self.assertEqual(read_content(created.json['document'], 'barril', 'ensayo-ipa')['nombre'], data['nombre'])
        updated = self.mutate({'action': 'update', 'collection': 'barril', 'id': 'ensayo-ipa',
                               'data': {'nombre': 'IPA actualizada'}})
        self.assertEqual(updated.status_code, 200, updated.json)
        self.assertFalse(updated.json['change']['after']['visible'])
        self.assertEqual(updated.json['change']['after']['precios'], data['precios'])
        deleted = self.mutate({'action': 'delete', 'collection': 'barril', 'id': 'ensayo-ipa'})
        self.assertEqual(deleted.status_code, 200, deleted.json)
        self.assertIsNone(deleted.json['change']['after'])
        self.assertEqual(deleted.json['document'], before['document'])
        self.assertEqual(self.client.get('/data/menu.json').json, live_before)
        self.assertEqual(self.state()['published_version'], before['published_version'])
        with self.app.extensions['cms_db']() as con:
            actions = [dict(row) for row in con.execute("select actor,action from activity where action like 'Agente:%'")]
        self.assertEqual(len(actions), 3)
        self.assertTrue(all(row['actor'] == 'editor' and 'barril:ensayo-ipa' in row['action'] for row in actions))

    def test_food_uses_category_id_and_preserves_other_categories_and_flags(self):
        before = self.state()['document']
        category = before['menu']['comida'][0]
        item = category['items'][0]
        result = self.mutate({'action': 'update', 'collection': 'comida', 'category_id': category['id'],
                              'id': item['id'], 'data': {'precio': item['precio'] + 1}})
        self.assertEqual(result.status_code, 200, result.json)
        expected = deepcopy(before)
        expected['menu']['comida'][0]['items'][0]['precio'] += 1
        self.assertEqual(result.json['document'], expected)
        for bad_category in (0, 'categoria-inexistente', None):
            response = self.mutate({'action': 'update', 'collection': 'comida', 'category_id': bad_category,
                                    'id': item['id'], 'data': {'precio': 1}})
            self.assertIn(response.status_code, (400, 404), response.json)
        self.assertEqual(self.state()['document'], expected)

    def test_event_gallery_page_and_business_operations(self):
        before = self.state()['document']
        image = before['page']['hero_image']
        for collection, data in (('events', {'title': 'Cata de ensayo', 'image': image, 'date': '2026-11-01'}),
                                 ('gallery', {'image': image, 'alt': 'Prueba local'})):
            with self.subTest(collection=collection):
                created = self.mutate({'action': 'create', 'collection': collection, 'id': 'local-agent-test', 'data': data})
                self.assertEqual(created.status_code, 200, created.json)
                updated = self.mutate({'action': 'update', 'collection': collection, 'id': 'local-agent-test',
                                       'data': {'alt': 'Texto alternativo actualizado'}})
                self.assertEqual(updated.status_code, 200, updated.json)
                self.assertEqual(updated.json['change']['after']['alt'], 'Texto alternativo actualizado')
                deleted = self.mutate({'action': 'delete', 'collection': collection, 'id': 'local-agent-test'})
                self.assertEqual(deleted.status_code, 200, deleted.json)
        page = self.mutate({'action': 'update', 'collection': 'page', 'data': {'hero_title': 'Ensayo de portada'}})
        self.assertEqual(page.status_code, 200, page.json)
        self.assertEqual(page.json['change']['before'], {'hero_title': before['page']['hero_title']})
        business = self.mutate({'action': 'update', 'collection': 'negocio',
                                'data': {'horario': [{'dias': 'Lunes a viernes', 'horas': '16:00 – 22:00'}]}})
        self.assertEqual(business.status_code, 200, business.json)
        self.assertEqual(business.json['document']['menu']['negocio']['nombre'], before['menu']['negocio']['nombre'])

    def test_stale_version_is_409_without_overwriting(self):
        version = self.state()['version']
        operation = {'action': 'update', 'collection': 'page', 'data': {'hero_title': 'Primer cambio'}}
        first = self.mutate(operation, version)
        self.assertEqual(first.status_code, 200, first.json)
        operation['data']['hero_title'] = 'Cambio obsoleto'
        second = self.mutate(operation, version)
        self.assertEqual(second.status_code, 409, second.json)
        self.assertEqual(self.state()['document'], first.json['document'])

    def test_anonymous_csrf_and_origin_guards_are_reused(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get('/cms/api/agent/content').status_code, 401)
        self.assertEqual(anonymous.post('/cms/api/agent/content', json={}).status_code, 401)
        operation = {'action': 'update', 'collection': 'page', 'data': {'hero_title': 'No guardar'}}
        before = self.state()
        payload = {'version': before['version'], 'operation': operation}
        self.assertEqual(self.client.post('/cms/api/agent/content', json=payload).status_code, 403)
        self.assertEqual(self.client.post('/cms/api/agent/content', json=payload,
                         headers=self.headers | {'Origin': 'https://external.invalid'}).status_code, 403)
        self.assertEqual(self.state(), before)

    def test_owner_and_editor_both_edit_but_service_never_publishes(self):
        editor_state = self.state()
        self.assertNotIn('user', editor_state)
        login = self.client.post('/cms/api/login', json={'username': 'owner', 'password': 'agent-test-password'})
        self.headers['X-CSRF-Token'] = login.json['csrf']
        saved = self.mutate({'action': 'update', 'collection': 'page', 'data': {'hero_title': 'Propietario'}})
        self.assertEqual(saved.status_code, 200, saved.json)
        self.assertEqual(self.state()['published_version'], editor_state['published_version'])

    def test_invalid_operations_do_not_change_draft_or_activity(self):
        before = self.state()
        beer = before['document']['menu']['barril'][0]
        cases = [
            {'action': 'publish', 'collection': 'barril'},
            {'action': 'update', 'collection': 'users', 'id': 'owner', 'data': {'role': 'owner'}},
            {'action': 'update', 'collection': 'barril', 'id': beer['id'], 'data': {'id': 'renamed'}},
            {'action': 'update', 'collection': 'barril', 'id': beer['id'], 'data': {'precios': [{'medida': '16 oz', 'precio': -1}]}},
            {'action': 'update', 'collection': 'barril', 'id': beer['id'], 'data': {'abv': 101}},
            {'action': 'update', 'collection': 'barril', 'id': beer['id'], 'data': {'precios': [{'medida': '16 oz', 'precio': 1, 'secret': 'x'}]}},
            {'action': 'create', 'collection': 'barril', 'id': beer['id'], 'data': {'nombre': 'Duplicado'}},
            {'action': 'update', 'collection': 'barril', 'id': 0, 'data': {'nombre': 'Índice'}},
            {'action': 'update', 'collection': 'page', 'data': {'server_token': 'x'}},
            {'action': 'delete', 'collection': 'page'},
            {'action': 'delete', 'collection': 'barril', 'id': beer['id'], 'data': {}},
        ]
        for operation in cases:
            with self.subTest(operation=operation):
                result = self.mutate(operation)
                self.assertIn(result.status_code, (400, 409), result.json)
                self.assertEqual(self.state(), before)
        with self.app.extensions['cms_db']() as con:
            self.assertEqual(con.execute("select count(*) from activity where action like 'Agente:%'").fetchone()[0], 0)

    def test_delete_referenced_food_is_rejected_without_touching_references(self):
        before = self.state()
        doc = before['document']
        beer = doc['menu']['barril'][0]
        category = doc['menu']['comida'][0]
        food = category['items'][0]
        paired = self.mutate({'action': 'update', 'collection': 'barril', 'id': beer['id'],
                              'data': {'marida_con': [food['id']]}})
        self.assertEqual(paired.status_code, 200, paired.json)
        result = self.mutate({'action': 'delete', 'collection': 'comida', 'category_id': category['id'], 'id': food['id']})
        self.assertEqual(result.status_code, 400, result.json)
        self.assertIn('inexistente', result.json['error'])
        self.assertEqual(self.state()['document'], paired.json['document'])

    def test_pure_functions_copy_inputs_and_reject_unknown_nested_fields(self):
        original = initial_document(ROOT / 'sitio')
        preserved = deepcopy(original)
        copied = read_content(original, 'barril')
        copied[0]['nombre'] = 'Sin efecto'
        self.assertEqual(original, preserved)
        with self.assertRaises(ValueError):
            apply_operation(original, {'action': 'update', 'collection': 'negocio',
                                        'data': {'geo': {'lat': 0, 'lng': 0, 'token': 'invalid'}}})
        self.assertEqual(original, preserved)
        changed, _ = apply_operation(original, {'action': 'update', 'collection': 'page',
                                                'data': {'hero_title': 'Solo la copia'}})
        self.assertNotEqual(changed['page']['hero_title'], original['page']['hero_title'])
        self.assertEqual(original, preserved)

    def test_version_must_be_integer_and_request_cannot_smuggle_extra_fields(self):
        before = self.state()
        operation = {'action': 'update', 'collection': 'page', 'data': {'hero_title': 'No guardar'}}
        for version in (True, 0, '1', 1.0):
            result = self.mutate(operation, version)
            self.assertEqual(result.status_code, 400, result.json)
        result = self.client.post('/cms/api/agent/content', headers=self.headers,
            json={'version': before['version'], 'operation': operation, 'publish': True})
        self.assertEqual(result.status_code, 400, result.json)
        self.assertEqual(self.state(), before)


if __name__ == '__main__':
    unittest.main()
