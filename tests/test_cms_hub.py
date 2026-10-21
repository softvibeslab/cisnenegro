"""Pruebas del Content Hub (backend/cms_hub.py y backend/hub_seed.py).

Run: python -m unittest discover -s tests -p 'test_cms_hub.py' -v
Crea el CMS en una carpeta temporal, registra el Hub y carga la semilla mínima.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from cms_server import create_app, now  # noqa: E402
from cms_hub import register_hub, estado_seccion_calculado, faltantes_checklist  # noqa: E402
import hub_seed  # noqa: E402

SEMILLA = ROOT / 'tests' / 'fixtures' / 'hub-semilla-min.json'
SEMILLA_REAL = ROOT / 'estrategia-contenido' / 'datos' / 'parrilla-piloto.json'
CHECK_OK = {'leyenda': True, 'sin_consumo_en_cuadro': True, 'personas_25_mas': True, 'sin_imperativo': True,
            'sin_asociacion_prohibida': True, 'datos_verificados': True}


class HubBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cisne-hub-test-')
        self.app = create_app({'CMS_ROOT': self.tmp.name, 'CMS_SITE': str(ROOT / 'sitio'),
                               'CMS_DEV': True, 'CMS_ORIGIN': 'http://localhost', 'TESTING': True})
        with self.app.extensions['cms_db']() as con:
            for username, name, role in (('owner', 'Propietario', 'owner'), ('editor', 'Editor', 'editor'),
                                         ('aprobador', 'Aprobadora', 'editor')):
                con.execute('insert into users(username,name,password,role,created_at) values(?,?,?,?,?)',
                            (username, name, generate_password_hash(f'{username.title()}-test-only-2026'), role, now()))
        register_hub(self.app)
        hub_seed.cargar(self.tmp.name, json.loads(SEMILLA.read_text(encoding='utf-8')))
        with self.app.extensions['hub_db']() as con:
            con.execute("insert into roles_hub(user_id,rol,creado_at) values(3,'aprobador',?)", (now(),))
        self.sessions = {}
        self._cat = None

    def tearDown(self):
        self.app.extensions['cms_media'].close()
        self.tmp.cleanup()

    # -- helpers -------------------------------------------------------------
    def session(self, user):
        if user not in self.sessions:
            client = self.app.test_client()
            r = client.post('/cms/api/login', json={'username': user, 'password': f'{user.title()}-test-only-2026'})
            self.assertEqual(r.status_code, 200, r.get_json())
            self.sessions[user] = (client, r.json['csrf'])
        return self.sessions[user]

    def api(self, user, method, path, data=None, **kw):
        client, csrf = self.session(user)
        return client.open(path, method=method, json=data, headers={'X-CSRF-Token': csrf}, **kw)

    def ok(self, r, status=200):
        self.assertEqual(r.status_code, status, r.get_json(silent=True) or r.data[:300])
        return r.get_json()

    def cat(self, refresh=False):
        if self._cat is None or refresh:
            self._cat = self.ok(self.api('owner', 'GET', '/cms/api/hub/catalogos'))
        return self._cat

    def id(self, catalogo, clave):
        return next(i['id'] for i in self.cat(True)[catalogo] if i['clave'] == clave)

    def pieza(self, clave):
        items = self.ok(self.api('owner', 'GET', '/cms/api/hub/piezas?q=' + clave))['items']
        return next(p for p in items if p['clave'] == clave)

    def detalle(self, pid, user='owner'):
        return self.ok(self.api(user, 'GET', f'/cms/api/hub/piezas/{pid}'))['item']

    def put_pieza(self, pid, cambios, user='owner'):
        p = self.detalle(pid, user)
        return self.api(user, 'PUT', f'/cms/api/hub/piezas/{pid}', dict(cambios, version=p['version']))

    def estado(self, pid, estado, user='owner', motivo=''):
        return self.api(user, 'POST', f'/cms/api/hub/piezas/{pid}/estado', {'estado': estado, 'motivo': motivo})

    def a_revision(self, pid):
        self.ok(self.put_pieza(pid, {'cumplimiento': CHECK_OK}))
        self.ok(self.estado(pid, 'revision'))

    def publicar(self, pid):
        self.a_revision(pid)
        self.ok(self.estado(pid, 'aprobada'))
        self.ok(self.estado(pid, 'programada'))
        for v in self.detalle(pid)['variantes']:
            self.ok(self.api('editor', 'POST', f"/cms/api/hub/variantes/{v['id']}/publicada",
                             {'url': f"https://www.instagram.com/p/{v['id']}/", 'publicado_at': '2026-10-20T18:30:00+00:00'}))
        return self.detalle(pid)

    def medir(self, pid, likes, horas=24):
        vid = self.detalle(pid)['variantes'][0]['id']
        return self.ok(self.api('editor', 'POST', f'/cms/api/hub/variantes/{vid}/metricas',
                                {'likes': likes, 'comentarios': 0, 'horas_desde_pub': horas}), 201)

    def nueva(self, seccion, prueba, fecha, hora='12:30', formato='ig-carrusel', titulo=None, plantilla=None):
        data = {'titulo': titulo or f'{seccion} {prueba or ""} {fecha}', 'seccion_id': self.id('secciones', seccion),
                'prueba': prueba, 'fecha': fecha, 'hora': hora,
                'variantes': [{'canal_id': self.id('canales', 'ig'), 'formato_id': self.id('formatos', formato),
                               'copy': 'Texto de prueba. EVITE EL EXCESO'}]}
        if plantilla:
            data['plantilla_id'] = self.id('plantillas', plantilla)
        return self.ok(self.api('owner', 'POST', '/cms/api/hub/piezas', data), 201)['item']['id']

    def lab(self, seccion):
        items = self.ok(self.api('owner', 'GET', '/cms/api/hub/laboratorio'))['items']
        return next(s for s in items if s['clave'] == seccion)


class AuthAndCatalogs(HubBase):
    def test_auth_required(self):
        anon = self.app.test_client()
        for path in ('/cms/api/hub/catalogos', '/cms/api/hub/piezas', '/cms/api/hub/resumen', '/cms/api/hub/laboratorio',
                     '/cms/api/hub/canales', '/cms/api/hub/piezas.csv', '/cms/api/hub/ajustes', '/cms/api/hub/media'):
            self.assertEqual(anon.get(path).status_code, 401, path)
        self.assertEqual(anon.post('/cms/api/hub/piezas', json={'titulo': 'x'}).status_code, 401)

    def test_csrf_and_origin(self):
        client, csrf = self.session('owner')
        self.assertEqual(client.post('/cms/api/hub/piezas', json={'titulo': 'Sin CSRF'}).status_code, 403)
        self.assertEqual(client.post('/cms/api/hub/piezas', json={'titulo': 'Origen'},
                                     headers={'X-CSRF-Token': csrf, 'Origin': 'https://malo.invalid'}).status_code, 403)
        self.assertEqual(client.post('/cms/api/hub/piezas', json={'titulo': 'Bien'}, headers={'X-CSRF-Token': csrf}).status_code, 201)

    def test_catalogos_payload(self):
        c = self.cat()
        for k in ('canales', 'formatos', 'plantillas', 'pilares', 'topicos', 'secciones', 'temas', 'aliados', 'campanas',
                  'atributos', 'usuarios', 'meta', 'ajustes', 'yo'):
            self.assertIn(k, c)
        sec = next(s for s in c['secciones'] if s['clave'] == 'barril-de-la-semana')
        self.assertEqual(sec['interaccion_ideal_efectiva'], 56)
        self.assertEqual({u['name'] for u in c['usuarios']}, {'Propietario', 'Editor', 'Aprobadora'})
        self.assertNotIn('username', c['usuarios'][0])
        self.assertEqual(next(u for u in c['usuarios'] if u['id'] == 3)['roles_hub'], ['aprobador'])
        self.assertEqual(len(c['temas']), 2)

    def test_crud_every_catalog(self):
        ig, pilar, topico, seccion = (self.id('canales', 'ig'), self.id('pilares', 'barril'),
                                      self.id('topicos', 'barril-semana'), self.id('secciones', 'barril-de-la-semana'))
        casos = {
            'canales': ({'nombre': 'TikTok', 'color': '#000000', 'metodo': 'manual'}, {'cadencia': '3 por semana'}),
            'formatos': ({'canal_id': ig, 'nombre': 'Imagen', 'tipo': 'imagen', 'proporcion': '4:5', 'interaccion_ideal': 43},
                         {'max_laminas': 1}),
            'plantillas': ({'nombre': 'Meme', 'enlace': 'https://www.canva.com/x'}, {'tiempo': 'Rápido'}),
            'pilares': ({'nombre': 'La Mesa', 'color': '#aa3300', 'objetivo_pct': 25}, {'descripcion': 'Comida'}),
            'topicos': ({'pilar_id': pilar, 'nombre': 'Maridaje'}, {'orden': 3}),
            'secciones': ({'topico_id': topico, 'nombre': 'Lunes de producción', 'formato_id': self.id('formatos', 'ig-reel')},
                          {'en_piloto': True, 'interaccion_ideal': 40}),
            'temas': ({'seccion_id': seccion, 'titulo': 'Un tema nuevo'}, {'explicacion': 'Por qué funciona'}),
            'aliados': ({'nombre': '@chef.prueba', 'tipo': 'Chef'}, {'contacto': 'DM'}),
            'campanas': ({'nombre': 'Aniversario III', 'inicio': '2026-11-20', 'fin': '2026-11-29'}, {'objetivo': 'Visitas'}),
            'atributos': ({'entidad': 'pieza', 'nombre': 'Con coautor', 'tipo': 'booleano', 'filtrable': True}, {'columna': True}),
        }
        for nombre, (alta, cambio) in casos.items():
            with self.subTest(nombre):
                item = self.ok(self.api('editor', 'POST', f'/cms/api/hub/{nombre}', alta), 201)['item']
                if nombre != 'temas':
                    self.assertTrue(item['clave'])
                listado = self.ok(self.api('editor', 'GET', f'/cms/api/hub/{nombre}'))['items']
                self.assertIn(item['id'], [i['id'] for i in listado])
                editado = self.ok(self.api('editor', 'PUT', f"/cms/api/hub/{nombre}/{item['id']}", cambio))['item']
                for k, v in cambio.items():
                    self.assertEqual(editado[k], v)
                self.assertEqual(self.ok(self.api('editor', 'DELETE', f"/cms/api/hub/{nombre}/{item['id']}"))['archivado'], True)
                self.assertNotIn(item['id'], [i['id'] for i in self.ok(self.api('editor', 'GET', f'/cms/api/hub/{nombre}'))['items']])
                todos = self.ok(self.api('editor', 'GET', f'/cms/api/hub/{nombre}?archivados=1'))['items']
                self.assertTrue(next(i for i in todos if i['id'] == item['id'])['archivado'])
                self.assertEqual(self.api('editor', 'DELETE', f"/cms/api/hub/{nombre}/{item['id']}?definitivo=1").status_code, 403)
                self.assertTrue(self.ok(self.api('owner', 'DELETE', f"/cms/api/hub/{nombre}/{item['id']}?definitivo=1"))['eliminado'])
        acciones = [a['accion'] for a in self.ok(self.api('owner', 'GET', '/cms/api/hub/actividad'))['items']]
        self.assertIn('Alta de canal', acciones)
        self.assertIn('Borrado definitivo de atributo', acciones)

    def test_catalog_validation(self):
        ig = self.id('canales', 'ig')
        malos = [
            ('canales', {'nombre': 'X', 'color': 'rojo'}), ('canales', {'nombre': 'X', 'metodo': 'robot'}),
            ('canales', {'color': '#fff'}), ('canales', {'nombre': 'X', 'clave': 'Con Espacios'}),
            ('canales', {'nombre': 'X', 'config': {'access_token': 'abc'}}),
            ('formatos', {'nombre': 'Sin canal'}), ('formatos', {'canal_id': 99999, 'nombre': 'X'}),
            ('formatos', {'canal_id': ig, 'nombre': 'X', 'max_caracteres': -5}),
            ('plantillas', {'nombre': 'X', 'enlace': 'javascript:alert(1)'}),
            ('pilares', {'nombre': 'X', 'objetivo_pct': 140}),
            ('campanas', {'nombre': 'X', 'inicio': '2026-11-10', 'fin': '2026-11-01'}),
            ('campanas', {'nombre': 'X', 'inicio': '2026-13-40'}),
            ('atributos', {'entidad': 'pieza', 'nombre': 'Lista vacía', 'tipo': 'lista'}),
            ('atributos', {'entidad': 'usuario', 'nombre': 'X', 'tipo': 'texto'}),
            ('secciones', {'topico_id': self.id('topicos', 'barril-semana'), 'nombre': 'X', 'estado_prueba': 'quizas'}),
        ]
        for nombre, data in malos:
            with self.subTest(nombre=nombre, data=data):
                r = self.api('editor', 'POST', f'/cms/api/hub/{nombre}', data)
                self.assertEqual(r.status_code, 400, r.get_json())
                self.assertIn('error', r.get_json())
        self.assertEqual(self.api('editor', 'POST', '/cms/api/hub/canales', {'nombre': 'Otro', 'clave': 'ig'}).status_code, 409)
        self.assertEqual(self.api('editor', 'GET', '/cms/api/hub/usuarios').status_code, 404)
        self.assertEqual(self.api('editor', 'POST', '/cms/api/hub/variantes', {}).status_code, 404)
        self.assertEqual(self.api('editor', 'PUT', '/cms/api/hub/canales/99999', {'nombre': 'X'}).status_code, 404)

    def test_archive_vs_definitive_with_dependencies(self):
        pilar = self.id('pilares', 'barril')
        r = self.api('owner', 'DELETE', f'/cms/api/hub/pilares/{pilar}?definitivo=1')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json['dependencias'], {'topicos': 1})
        canal = self.id('canales', 'ig')
        r = self.api('owner', 'DELETE', f'/cms/api/hub/canales/{canal}?definitivo=1')
        self.assertEqual(r.status_code, 409)
        self.assertIn('formatos', r.json['dependencias'])
        self.assertTrue(self.ok(self.api('editor', 'DELETE', f'/cms/api/hub/pilares/{pilar}'))['archivado'])
        restaurado = self.ok(self.api('editor', 'PUT', f'/cms/api/hub/pilares/{pilar}', {'archivado': False}))['item']
        self.assertFalse(restaurado['archivado'])


class Attributes(HubBase):
    def test_define_assign_filter_and_csv(self):
        attr = self.ok(self.api('owner', 'POST', '/cms/api/hub/atributos',
                                {'clave': 'con_coautor', 'entidad': 'pieza', 'nombre': 'Con coautor', 'tipo': 'booleano',
                                 'filtrable': True, 'columna': True}), 201)['item']
        r1 = self.pieza('2026-10-20-barril-r1')
        self.assertEqual(r1['atributos'], {'gancho': 'Dato'})
        self.ok(self.put_pieza(r1['id'], {'atributos': {'con_coautor': True, 'presupuesto': 250}}))
        datos = self.ok(self.api('owner', 'GET', '/cms/api/hub/piezas?attr.gancho=Dato'))['items']
        self.assertEqual([p['clave'] for p in datos], ['2026-10-20-barril-r1'])
        self.assertEqual(len(self.ok(self.api('owner', 'GET', '/cms/api/hub/piezas?attr.con_coautor=true'))['items']), 1)
        self.assertEqual(len(self.ok(self.api('owner', 'GET', '/cms/api/hub/piezas?attr.gancho=Humor'))['items']), 0)
        self.assertEqual(len(self.ok(self.api('owner', 'GET', '/cms/api/hub/piezas?attr.presupuesto=250'))['items']), 1)
        self.assertEqual(self.api('owner', 'GET', '/cms/api/hub/piezas?attr.inexistente=1').status_code, 400)
        for malo in ({'gancho': 'Otro'}, {'presupuesto': 'mucho'}, {'con_coautor': 'quizás'}, {'nope': 1}):
            with self.subTest(malo):
                self.assertEqual(self.put_pieza(r1['id'], {'atributos': malo}).status_code, 400)
        csv = self.api('owner', 'GET', '/cms/api/hub/piezas.csv')
        self.assertEqual(csv.status_code, 200)
        self.assertIn('text/csv', csv.headers['Content-Type'])
        texto = csv.data.decode('utf-8-sig')
        cabecera = texto.splitlines()[0]
        for col in ('Tipo de gancho', 'Presupuesto de pauta', 'Con coautor', 'clave', 'seccion'):
            self.assertIn(col, cabecera)
        self.assertIn('Dato', texto)
        self.assertIn('2026-10-20-barril-r1', texto)
        # El tipo no cambia si ya hay valores; las opciones en uso no se pueden quitar.
        gancho = self.id('atributos', 'gancho')
        self.assertEqual(self.api('owner', 'PUT', f"/cms/api/hub/atributos/{attr['id']}", {'tipo': 'texto'}).status_code, 409)
        self.assertEqual(self.api('owner', 'PUT', f'/cms/api/hub/atributos/{gancho}', {'opciones': ['Humor']}).status_code, 409)
        self.assertEqual(self.api('owner', 'DELETE', f'/cms/api/hub/atributos/{gancho}?definitivo=1').status_code, 409)

    def test_csv_neutralizes_formulas(self):
        r1 = self.pieza('2026-10-20-barril-r1')
        self.ok(self.put_pieza(r1['id'], {'titulo': '=HYPERLINK("http://malo")'}))
        texto = self.api('owner', 'GET', '/cms/api/hub/piezas.csv').data.decode('utf-8-sig')
        self.assertIn("'=HYPERLINK", texto)

    def test_attributes_on_other_entities(self):
        self.ok(self.api('owner', 'POST', '/cms/api/hub/atributos',
                         {'clave': 'requiere_grabacion', 'entidad': 'seccion', 'nombre': 'Requiere grabación', 'tipo': 'booleano'}), 201)
        sid = self.id('secciones', 'barril-de-la-semana')
        item = self.ok(self.api('owner', 'PUT', f'/cms/api/hub/secciones/{sid}', {'atributos': {'requiere_grabacion': True}}))['item']
        self.assertEqual(item['atributos'], {'requiere_grabacion': True})
        self.ok(self.api('owner', 'POST', '/cms/api/hub/atributos',
                         {'clave': 'responsable_cuenta', 'entidad': 'aliado', 'nombre': 'Responsable', 'tipo': 'usuario'}), 201)
        aid = self.id('aliados', 'ilustrador-prueba')
        self.ok(self.api('owner', 'PUT', f'/cms/api/hub/aliados/{aid}', {'atributos': {'responsable_cuenta': 2}}))
        self.assertEqual(self.api('owner', 'PUT', f'/cms/api/hub/aliados/{aid}', {'atributos': {'responsable_cuenta': 99}}).status_code, 400)


class Pieces(HubBase):
    def test_crud_version_conflict_and_history(self):
        ig = self.id('canales', 'ig')
        alta = {'titulo': 'Maridaje del finde', 'seccion_id': self.id('secciones', 'barril-de-la-semana'), 'fecha': '2026-10-22',
                'hora': '16:00', 'responsable_id': 2, 'por_validar': ['Confirmar platillo'],
                'variantes': [{'canal_id': ig, 'formato_id': self.id('formatos', 'ig-carrusel'), 'copy': 'Hola', 'hashtags': ['#pachuca']}]}
        item = self.ok(self.api('editor', 'POST', '/cms/api/hub/piezas', alta), 201)['item']
        self.assertEqual((item['version'], item['estado'], item['responsable']), (1, 'borrador', 'Editor'))
        self.assertEqual(item['pilar'], 'El Barril')
        self.assertEqual(item['variantes'][0]['caracteres'], len('Hola #pachuca'))
        self.assertEqual(item['variantes'][0]['limites']['copy'], 2200)
        pid, vid = item['id'], item['variantes'][0]['id']
        v2 = self.ok(self.api('editor', 'PUT', f'/cms/api/hub/piezas/{pid}', {'version': 1, 'titulo': 'Maridaje v2',
                     'variantes': [{'id': vid, 'canal_id': ig, 'copy': 'Hola 2'},
                                   {'canal_id': self.id('canales', 'threads'), 'copy': 'Hilo'}]}))['item']
        self.assertEqual(v2['version'], 2)
        self.assertEqual([v['id'] == vid for v in v2['variantes']], [True, False])
        r = self.api('owner', 'PUT', f'/cms/api/hub/piezas/{pid}', {'version': 1, 'titulo': 'Pisando'})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json['version'], 2)
        self.assertEqual(self.api('owner', 'PUT', f'/cms/api/hub/piezas/{pid}', {'titulo': 'Sin versión'}).status_code, 400)
        d = self.detalle(pid)
        self.assertEqual([v['version'] for v in d['versiones']], [2, 1])
        v1 = self.ok(self.api('owner', 'GET', f'/cms/api/hub/piezas/{pid}/versiones/1'))
        self.assertEqual(v1['datos']['titulo'], 'Maridaje del finde')
        self.assertEqual(len(v1['datos']['variantes']), 1)
        self.assertEqual(self.api('owner', 'POST', '/cms/api/hub/piezas', {'titulo': ''}).status_code, 400)
        self.assertEqual(self.api('owner', 'POST', '/cms/api/hub/piezas', {'titulo': 'x', 'estado': 'aprobada'}).status_code, 400)
        self.assertEqual(self.api('owner', 'POST', '/cms/api/hub/piezas', {'titulo': 'x', 'hora': '25:00'}).status_code, 400)
        self.assertEqual(self.api('owner', 'POST', '/cms/api/hub/piezas', {'titulo': 'x', 'responsable_id': 99}).status_code, 400)
        self.assertEqual(self.api('owner', 'POST', '/cms/api/hub/piezas', {'titulo': 'x', 'variantes': [
            {'canal_id': ig, 'formato_id': self.id('formatos', 'threads-texto')}]}).status_code, 400)
        self.assertEqual(self.api('owner', 'POST', '/cms/api/hub/piezas', {'titulo': 'x', 'cumplimiento': {'datos_verificados': 'no_aplica'}}).status_code, 400)
        # Borrado suave, filtro y borrado definitivo (solo dueño).
        self.assertTrue(self.ok(self.api('editor', 'DELETE', f'/cms/api/hub/piezas/{pid}'))['archivado'])
        self.assertNotIn(pid, [p['id'] for p in self.ok(self.api('owner', 'GET', '/cms/api/hub/piezas'))['items']])
        self.assertIn(pid, [p['id'] for p in self.ok(self.api('owner', 'GET', '/cms/api/hub/piezas?archivados=1'))['items']])
        self.assertEqual(self.api('editor', 'DELETE', f'/cms/api/hub/piezas/{pid}?definitivo=1').status_code, 403)
        self.assertTrue(self.ok(self.api('owner', 'DELETE', f'/cms/api/hub/piezas/{pid}?definitivo=1'))['eliminado'])
        self.assertEqual(self.api('owner', 'GET', f'/cms/api/hub/piezas/{pid}').status_code, 404)

    def test_list_filters(self):
        lista = lambda q: [p['clave'] for p in self.ok(self.api('owner', 'GET', '/cms/api/hub/piezas' + q))['items']]
        self.assertEqual(len(lista('')), 3)
        self.assertEqual(lista('?desde=2026-10-21&hasta=2026-10-26'), ['2026-10-25-resena-r1'])
        self.assertEqual(lista('?canal=threads'), ['2026-10-20-barril-r1'])
        self.assertEqual(sorted(lista('?pilar=barril')), ['2026-10-20-barril-r1', '2026-10-27-barril-r2'])
        self.assertEqual(lista(f"?seccion={self.id('secciones', 'resena-en-voz-alta')}"), ['2026-10-25-resena-r1'])
        self.assertEqual(lista('?estado=idea'), ['2026-10-25-resena-r1'])
        self.assertEqual(lista('?q=R2'), ['2026-10-27-barril-r2'])
        self.assertEqual(self.api('owner', 'GET', '/cms/api/hub/piezas?estado=otro').status_code, 400)
        self.assertEqual(self.api('owner', 'GET', '/cms/api/hub/piezas?desde=ayer').status_code, 400)

    def test_move_and_duplicate(self):
        r1 = self.pieza('2026-10-20-barril-r1')
        movida = self.ok(self.api('editor', 'POST', f"/cms/api/hub/piezas/{r1['id']}/mover", {'fecha': '2026-10-21', 'hora': '13:00'}))['item']
        self.assertEqual((movida['fecha'], movida['hora'], movida['version']), ('2026-10-21', '13:00', 2))
        self.assertEqual({(v['fecha'], v['hora']) for v in movida['variantes']}, {('2026-10-21', '13:00')})
        self.assertEqual(self.api('editor', 'POST', f"/cms/api/hub/piezas/{r1['id']}/mover", {'fecha': '21/10'}).status_code, 400)
        self.assertEqual(self.api('editor', 'POST', f"/cms/api/hub/piezas/{r1['id']}/mover", {'fecha': '2026-10-22', 'version': 1}).status_code, 409)
        self.ok(self.put_pieza(r1['id'], {'cumplimiento': CHECK_OK}))
        copia = self.ok(self.api('editor', 'POST', f"/cms/api/hub/piezas/{r1['id']}/duplicar"), 201)['item']
        self.assertEqual(copia['clave'], '2026-10-20-barril-r1-copia')
        self.assertEqual((copia['estado'], copia['version'], copia['cumplimiento']), ('borrador', 1, {}))
        self.assertEqual(len(copia['variantes']), 2)
        self.assertTrue(all(v['estado_pub'] == 'pendiente' for v in copia['variantes']))
        self.assertEqual(copia['atributos'], {'gancho': 'Dato'})
        otra = self.ok(self.api('editor', 'POST', f"/cms/api/hub/piezas/{r1['id']}/duplicar"), 201)['item']
        self.assertEqual(otra['clave'], '2026-10-20-barril-r1-copia-2')

    def test_comments(self):
        pid = self.pieza('2026-10-20-barril-r1')['id']
        self.ok(self.api('editor', 'POST', f'/cms/api/hub/piezas/{pid}/comentarios', {'texto': 'Nota interna'}), 201)
        pub = self.ok(self.api('editor', 'POST', f'/cms/api/hub/piezas/{pid}/comentarios', {'texto': 'Para el dueño', 'interno': False}), 201)
        self.assertFalse(pub['item']['interno'])
        items = self.ok(self.api('owner', 'GET', f'/cms/api/hub/piezas/{pid}/comentarios'))['items']
        self.assertEqual([c['interno'] for c in items], [True, False])
        self.assertEqual(self.api('editor', 'POST', f'/cms/api/hub/piezas/{pid}/comentarios', {'texto': ''}).status_code, 400)
        self.assertEqual(self.api('editor', 'GET', '/cms/api/hub/piezas/9999/comentarios').status_code, 404)


class Workflow(HubBase):
    def test_transitions_permissions_and_checklist(self):
        pid = self.pieza('2026-10-20-barril-r1')['id']
        r = self.estado(pid, 'revision', 'editor')
        self.assertEqual(r.status_code, 400)
        self.assertIn('leyenda', r.json['faltantes'])
        self.assertEqual(self.estado(pid, 'aprobada', 'owner').status_code, 409)  # borrador → aprobada no existe
        self.ok(self.put_pieza(pid, {'cumplimiento': dict(CHECK_OK, leyenda=False)}, 'editor'))
        self.assertEqual(self.estado(pid, 'revision', 'editor').json['faltantes'], ['leyenda'])
        self.ok(self.put_pieza(pid, {'cumplimiento': CHECK_OK}, 'editor'))
        self.assertEqual(self.ok(self.estado(pid, 'revision', 'editor'))['estado'], 'revision')
        self.assertEqual(self.estado(pid, 'aprobada', 'editor').status_code, 403)
        self.assertEqual(self.estado(pid, 'observada', 'aprobador').status_code, 400)  # falta motivo
        self.ok(self.estado(pid, 'observada', 'aprobador', 'Cambia la foto'))
        self.assertIn('Cambios solicitados: Cambia la foto', [c['texto'] for c in self.detalle(pid)['comentarios']])
        self.assertEqual(self.estado(pid, 'programada', 'owner').status_code, 409)
        self.ok(self.estado(pid, 'borrador', 'editor'))
        self.ok(self.estado(pid, 'revision', 'editor'))
        self.ok(self.estado(pid, 'aprobada', 'aprobador'))
        self.assertEqual(self.estado(pid, 'revision', 'owner').status_code, 409)
        self.assertEqual(self.estado(pid, 'publicada', 'owner').status_code, 409)
        prog = self.ok(self.estado(pid, 'programada', 'editor'))
        self.assertTrue(all(v['estado_pub'] == 'programada' for v in prog['item']['variantes']))
        self.assertEqual(self.estado(pid, 'publicada', 'owner').status_code, 409)  # variantes sin publicar
        self.ok(self.estado(pid, 'error', 'editor', 'Falló la subida'))
        self.ok(self.estado(pid, 'programada', 'editor'))
        self.assertEqual(self.estado(pid, 'inventado', 'owner').status_code, 400)
        self.assertTrue(self.ok(self.estado(pid, 'archivada', 'editor'))['archivado'])

    def test_checklist_rules(self):
        self.assertEqual(faltantes_checklist({}), ['leyenda', 'sin_consumo_en_cuadro', 'personas_25_mas', 'sin_imperativo',
                                                   'sin_asociacion_prohibida', 'datos_verificados'])
        no_cerveza = {k: 'no_aplica' for k in CHECK_OK if k != 'datos_verificados'}
        self.assertEqual(faltantes_checklist(dict(no_cerveza, datos_verificados=True)), [])
        self.assertEqual(faltantes_checklist(no_cerveza), ['datos_verificados'])
        mezcla = dict(CHECK_OK, leyenda='no_aplica')
        self.assertEqual(faltantes_checklist(mezcla), ['leyenda'])
        pid = self.pieza('2026-10-25-resena-r1')['id']
        self.ok(self.estado(pid, 'borrador'))
        self.ok(self.put_pieza(pid, {'cumplimiento': dict(no_cerveza, datos_verificados=True)}))
        self.ok(self.estado(pid, 'revision'))

    def test_required_attribute_blocks_review(self):
        self.ok(self.api('owner', 'POST', '/cms/api/hub/atributos',
                         {'clave': 'personas', 'entidad': 'pieza', 'nombre': 'Personas en cuadro', 'tipo': 'lista',
                          'opciones': ['Ninguna', 'Staff 25+'], 'requerido': True}), 201)
        pid = self.pieza('2026-10-20-barril-r1')['id']
        self.ok(self.put_pieza(pid, {'cumplimiento': CHECK_OK}))
        r = self.estado(pid, 'revision')
        self.assertEqual((r.status_code, r.json['faltantes']), (400, ['personas']))
        self.ok(self.put_pieza(pid, {'atributos': {'personas': 'Ninguna'}}))
        self.ok(self.estado(pid, 'revision'))

    def test_character_limits(self):
        threads, ig = self.id('canales', 'threads'), self.id('canales', 'ig')
        base = {'titulo': 'Límites'}
        r = self.api('owner', 'POST', '/cms/api/hub/piezas', dict(base, variantes=[{'canal_id': threads, 'copy': 'x' * 501}]))
        self.assertEqual(r.status_code, 400)
        self.assertEqual((r.json['maximo'], r.json['caracteres'], r.json['canal']), (500, 501, 'threads'))
        r = self.api('owner', 'POST', '/cms/api/hub/piezas', dict(base, variantes=[{'canal_id': threads, 'copy': 'x' * 490,
                                                                                    'hashtags': ['#pachuca123']}]))
        self.assertEqual(r.status_code, 400)  # 490 + espacio + 10 = 501
        self.ok(self.api('owner', 'POST', '/cms/api/hub/piezas', dict(base, variantes=[{'canal_id': threads, 'copy': 'x' * 500}])), 201)
        self.assertEqual(self.api('owner', 'POST', '/cms/api/hub/piezas', dict(base, variantes=[{'canal_id': ig, 'copy': 'x' * 2201}])).status_code, 400)
        yt = self.ok(self.api('owner', 'POST', '/cms/api/hub/canales', {'clave': 'yt', 'nombre': 'YouTube Shorts'}), 201)['item']['id']
        self.assertEqual(self.api('owner', 'POST', '/cms/api/hub/piezas', dict(base, variantes=[{'canal_id': yt, 'titulo': 't' * 101}])).status_code, 400)
        self.ok(self.api('owner', 'POST', '/cms/api/hub/piezas', dict(base, variantes=[{'canal_id': yt, 'titulo': 't' * 100, 'copy': 'd' * 5000}])), 201)
        gbp = self.id('canales', 'gbp')
        self.assertEqual(self.api('owner', 'POST', '/cms/api/hub/piezas', dict(base, variantes=[{'canal_id': gbp, 'copy': 'x' * 1501}])).status_code, 400)

    def test_assisted_publication(self):
        pid = self.pieza('2026-10-20-barril-r1')['id']
        variantes = self.detalle(pid)['variantes']
        self.assertEqual(self.api('editor', 'POST', f"/cms/api/hub/variantes/{variantes[0]['id']}/publicada",
                                  {'url': 'https://instagram.com/p/1'}).status_code, 409)  # aún en borrador
        self.a_revision(pid)
        self.ok(self.estado(pid, 'aprobada'))
        self.ok(self.estado(pid, 'programada'))
        self.assertEqual(self.api('editor', 'POST', f"/cms/api/hub/variantes/{variantes[0]['id']}/publicada",
                                  {'url': 'javascript:alert(1)'}).status_code, 400)
        r = self.ok(self.api('editor', 'POST', f"/cms/api/hub/variantes/{variantes[0]['id']}/publicada",
                             {'url': 'https://instagram.com/p/1', 'publicado_at': '2026-10-20T18:30:00+00:00'}))
        self.assertEqual(r['estado_pieza'], 'programada')
        self.assertEqual(r['variante']['estado_pub'], 'publicada')
        d = self.detalle(pid)
        cuerpo = [{'id': v['id'], 'canal_id': v['canal_id'], 'formato_id': v['formato_id'], 'copy': v['copy'], 'hashtags': v['hashtags'],
                   'estado_pub': 'omitida' if v['canal_clave'] == 'threads' else v['estado_pub']} for v in d['variantes']]
        d2 = self.ok(self.api('editor', 'PUT', f'/cms/api/hub/piezas/{pid}', {'version': d['version'], 'variantes': cuerpo}))['item']
        self.assertEqual(d2['estado'], 'programada')
        self.ok(self.estado(pid, 'publicada', 'editor'))
        self.assertEqual(self.detalle(pid)['estado'], 'publicada')
        # Una variante publicada no se puede quitar ni "despublicar".
        cuerpo[0]['estado_pub'] = 'pendiente'
        self.assertEqual(self.api('editor', 'PUT', f'/cms/api/hub/piezas/{pid}', {'version': d2['version'], 'variantes': cuerpo}).status_code, 409)
        self.assertEqual(self.api('editor', 'PUT', f'/cms/api/hub/piezas/{pid}', {'version': d2['version'], 'variantes': []}).status_code, 409)
        self.assertEqual(self.api('editor', 'POST', f'/cms/api/hub/piezas/{pid}/mover', {'fecha': '2026-10-30'}).status_code, 409)
        self.assertEqual(self.api('owner', 'DELETE', f'/cms/api/hub/piezas/{pid}?definitivo=1').status_code, 409)

    def test_approved_piece_publishes_all_variants_directly(self):
        pid = self.nueva('barril-de-la-semana', None, '2026-10-29')
        self.a_revision(pid)
        self.ok(self.estado(pid, 'aprobada'))
        vid = self.detalle(pid)['variantes'][0]['id']
        r = self.ok(self.api('editor', 'POST', f'/cms/api/hub/variantes/{vid}/publicada', {'url': 'https://instagram.com/p/2'}))
        self.assertEqual(r['estado_pieza'], 'publicada')


class Approval(HubBase):
    def enlace(self, pid):
        r = self.ok(self.api('editor', 'POST', f'/cms/api/hub/piezas/{pid}/enlace-aprobacion'), 201)
        self.assertTrue(r['url'].startswith('http://localhost/cms/aprobar/'))
        return r['ruta'].rsplit('/', 1)[1]

    def test_public_link_flow(self):
        pid = self.pieza('2026-10-20-barril-r1')['id']
        self.assertEqual(self.api('editor', 'POST', f'/cms/api/hub/piezas/{pid}/enlace-aprobacion').status_code, 409)
        self.a_revision(pid)
        self.ok(self.api('editor', 'POST', f'/cms/api/hub/piezas/{pid}/comentarios', {'texto': 'SECRETO-INTERNO no mostrar'}), 201)
        self.ok(self.api('editor', 'POST', f'/cms/api/hub/piezas/{pid}/comentarios', {'texto': 'Hola jefe', 'interno': False}), 201)
        token = self.enlace(pid)
        anon = self.app.test_client()
        r = anon.get(f'/cms/hub/aprobacion/{token}')
        self.assertEqual(r.status_code, 200, r.json)
        texto = r.data.decode()
        self.assertNotIn('SECRETO-INTERNO', texto)
        self.assertNotIn('token_hash', texto)
        self.assertNotIn('Editor', texto.replace('"autor":"Editor"', ''))
        self.assertEqual([c['texto'] for c in r.json['pieza']['comentarios']], ['Hola jefe'])
        self.assertEqual(r.json['pieza']['titulo'], 'Barril de la semana · R1')
        self.assertEqual(len(r.json['pieza']['variantes']), 2)
        self.assertNotIn('responsable', r.json['pieza'])
        self.assertEqual(anon.post(f'/cms/hub/aprobacion/{token}', json={'decision': 'cambios', 'nombre': 'Dueño'}).status_code, 400)
        self.assertEqual(anon.post(f'/cms/hub/aprobacion/{token}', json={'decision': 'aprobada', 'nombre': ''}).status_code, 400)
        self.assertEqual(anon.post(f'/cms/hub/aprobacion/{token}', json={'decision': 'quizás', 'nombre': 'Dueño'}).status_code, 400)
        ok = anon.post(f'/cms/hub/aprobacion/{token}', json={'decision': 'aprobada', 'nombre': 'Dueño', 'motivo': 'Va'})
        self.assertEqual(ok.status_code, 200, ok.json)
        self.assertEqual(self.detalle(pid)['estado'], 'aprobada')
        apro = self.detalle(pid)['aprobaciones'][0]
        self.assertEqual((apro['decision'], apro['quien'], apro['vigente']), ('aprobada', 'Dueño', False))
        self.assertNotIn('token_hash', apro)
        self.assertEqual(anon.post(f'/cms/hub/aprobacion/{token}', json={'decision': 'aprobada', 'nombre': 'Otra vez'}).status_code, 410)
        self.assertEqual(anon.get(f'/cms/hub/aprobacion/{token}').status_code, 410)
        self.assertEqual(anon.get('/cms/hub/aprobacion/' + 'x' * 43).status_code, 404)
        self.assertEqual(anon.get('/cms/hub/aprobacion/corto').status_code, 404)
        actividad = [a['actor'] for a in self.ok(self.api('owner', 'GET', '/cms/api/hub/actividad'))['items']]
        self.assertIn('Dueño (enlace)', actividad)

    def test_changes_expired_and_superseded_links(self):
        pid = self.pieza('2026-10-20-barril-r1')['id']
        self.a_revision(pid)
        viejo, nuevo = self.enlace(pid), self.enlace(pid)
        with self.app.extensions['hub_db']() as con:
            con.execute('update aprobaciones set expira=1 where id=(select min(id) from aprobaciones)')
        anon = self.app.test_client()
        self.assertEqual(anon.get(f'/cms/hub/aprobacion/{viejo}').status_code, 410)
        r = anon.post(f'/cms/hub/aprobacion/{nuevo}', json={'decision': 'cambios', 'nombre': 'Dueño', 'motivo': 'Otra foto'})
        self.assertEqual(r.json['estado'], 'observada')
        self.assertEqual(self.detalle(pid)['estado'], 'observada')
        # Un enlace sin usar deja de servir si la pieza sale de revisión.
        self.ok(self.estado(pid, 'borrador'))
        self.ok(self.estado(pid, 'revision'))
        tercero = self.enlace(pid)
        self.ok(self.estado(pid, 'aprobada', 'aprobador'))
        self.assertEqual(anon.get(f'/cms/hub/aprobacion/{tercero}').status_code, 410)

    def test_rate_limit(self):
        self.app.config['HUB_APPROVAL_LIMIT'] = 3
        anon = self.app.test_client()
        codigos = [anon.get('/cms/hub/aprobacion/' + 'y' * 43).status_code for _ in range(4)]
        self.assertEqual(codigos, [404, 404, 404, 429])
        self.assertEqual(anon.post('/cms/hub/aprobacion/' + 'y' * 43, json={}).status_code, 429)

    def test_fallback_html_escapes_and_form_decides(self):
        sitio = Path(self.tmp.name) / 'sitio-sin-aprobar'
        (sitio / 'cms').mkdir(parents=True)
        self.app.config['CMS_SITE'] = str(sitio)
        pid = self.pieza('2026-10-20-barril-r1')['id']
        self.ok(self.put_pieza(pid, {'titulo': '<script>alert(1)</script> Barril'}))
        self.a_revision(pid)
        token = self.enlace(pid)
        anon = self.app.test_client()
        r = anon.get(f'/cms/aprobar/{token}')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/html', r.headers['Content-Type'])
        html_ = r.data.decode()
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html_)
        self.assertNotIn('<script>alert(1)', html_)
        self.assertIn('Content-Security-Policy', r.headers)
        self.assertEqual(anon.get('/cms/aprobar/' + 'z' * 43).status_code, 404)
        r = anon.post(f'/cms/aprobar/{token}', data={'decision': 'aprobada', 'nombre': '<b>Dueño</b>'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.detalle(pid)['estado'], 'aprobada')
        self.assertEqual(anon.post(f'/cms/aprobar/{token}', data={'decision': 'aprobada', 'nombre': 'x'}).status_code, 410)

    def test_static_approval_page_when_present(self):
        sitio = Path(self.tmp.name) / 'sitio-con-aprobar'
        (sitio / 'cms').mkdir(parents=True)
        (sitio / 'cms' / 'aprobar.html').write_text('<!doctype html><title>Aprobar</title>APROBAR-ESTATICO')
        self.app.config['CMS_SITE'] = str(sitio)
        r = self.app.test_client().get('/cms/aprobar/' + 'q' * 43)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'APROBAR-ESTATICO', r.data)

    def test_media_through_token_only_for_piece_media(self):
        client, csrf = self.session('owner')
        ids = []
        for color in ('#f2c97d', '#202020'):
            buf = io.BytesIO(); Image.new('RGB', (40, 50), color).save(buf, 'PNG'); buf.seek(0)
            r = client.post('/cms/api/media', data={'file': (buf, 'vaso.png'), 'metadata': json.dumps({'title': 'Vaso ' + color})},
                            headers={'X-CSRF-Token': csrf}, content_type='multipart/form-data')
            self.assertEqual(r.status_code, 201, r.json)
            ids.append(r.json['item']['id'])
        galeria = self.ok(self.api('editor', 'GET', '/cms/api/hub/media?q=Vaso&kind=image&limit=1'))
        self.assertEqual((len(galeria['items']), galeria['total']), (1, 2))
        self.assertEqual(self.api('editor', 'GET', '/cms/api/hub/media?kind=pdf').status_code, 400)
        pid = self.pieza('2026-10-20-barril-r1')['id']
        d = self.detalle(pid)
        variantes = [{'id': v['id'], 'canal_id': v['canal_id'], 'formato_id': v['formato_id'], 'copy': v['copy'],
                      'hashtags': v['hashtags'], 'media_ids': [ids[0]] if v['canal_clave'] == 'ig' else []} for v in d['variantes']]
        malo = [dict(variantes[0], media_ids=['f' * 32])] + variantes[1:]
        self.assertEqual(self.api('editor', 'PUT', f'/cms/api/hub/piezas/{pid}', {'version': d['version'], 'variantes': malo}).status_code, 400)
        self.ok(self.api('editor', 'PUT', f'/cms/api/hub/piezas/{pid}', {'version': d['version'], 'variantes': variantes,
                                                                          'cumplimiento': CHECK_OK}))
        self.ok(self.estado(pid, 'revision'))
        token = self.ok(self.api('editor', 'POST', f'/cms/api/hub/piezas/{pid}/enlace-aprobacion'), 201)['ruta'].rsplit('/', 1)[1]
        anon = self.app.test_client()
        vista = anon.get(f'/cms/hub/aprobacion/{token}').json
        medio = next(v for v in vista['pieza']['variantes'] if v['canal_clave'] == 'ig')['medios'][0]
        self.assertEqual(medio['id'], ids[0])
        self.assertEqual(anon.get(medio['url']).status_code, 200)
        self.assertEqual(anon.get(medio['thumbnail']).status_code, 200)
        self.assertEqual(anon.get(f'/cms/hub/aprobacion/{token}/media/{ids[1]}/file').status_code, 404)
        self.assertEqual(anon.get(f"/cms/media/{ids[0]}/file").status_code, 404)  # el CMS sigue privado


class Laboratory(HubBase):
    def test_vigente_saturada_and_dejo_de_funcionar(self):
        sec = 'barril-de-la-semana'
        r1, r2 = self.pieza('2026-10-20-barril-r1')['id'], self.pieza('2026-10-27-barril-r2')['id']
        r3 = self.nueva(sec, 'R3', '2026-11-03', hora='15:00')
        self.assertEqual(self.lab(sec)['estado_prueba_calculado'], 'no_empezada')
        for pid in (r1, r2, r3):
            self.publicar(pid)
        self.assertEqual(self.lab(sec)['estado_prueba_calculado'], 'empezada')
        vid = self.detalle(r1)['variantes'][0]['id']
        self.assertEqual(self.detalle(r1)['variantes'][0]['canal_clave'], 'ig')
        self.ok(self.api('editor', 'POST', f'/cms/api/hub/variantes/{vid}/metricas', {'likes': 5, 'horas_desde_pub': 2}), 201)
        res = self.medir(r1, 57, horas=25)  # la más cercana a 24 h gana
        self.assertEqual(res['seccion']['pruebas']['R1']['interaccion'], 57)
        self.assertEqual(res['seccion']['pruebas']['R1']['resultado'], 'cumplio')
        self.assertEqual(res['seccion']['estado_prueba'], 'empezada')
        res = self.medir(r2, 70)
        self.assertEqual(res['seccion']['pruebas']['R2']['resultado'], 'supero')  # 125 %
        self.assertEqual(res['seccion']['estado_prueba'], 'vigente')
        self.medir(r3, 20)
        s = self.lab(sec)
        self.assertEqual((s['estado_prueba'], s['estado_prueba_calculado']), ('vigente', 'vigente'))
        self.assertEqual(s['pruebas']['R3']['resultado'], 'no_cumplio')
        self.assertEqual(s['estado_seccion'], 'normal')  # 2 de 3 cumplen
        self.assertEqual(s['interaccion_ideal'], 56)
        p4, p5 = self.nueva(sec, None, '2026-11-10'), self.nueva(sec, None, '2026-11-17')
        for pid, likes in ((p4, 40), (p5, 45)):
            self.publicar(pid)
            self.medir(pid, likes)
        s = self.lab(sec)  # 101.8, 125, 35.7, 71.4, 80.4 → media 82.9 sin mayoría que cumpla
        self.assertEqual(s['estado_seccion'], 'saturada')
        self.assertEqual(len(s['ultimos']), 5)
        p6, p7 = self.nueva(sec, None, '2026-11-24'), self.nueva(sec, None, '2026-11-25')
        for pid in (p6, p7):
            self.publicar(pid)
            self.medir(pid, 5)
        s = self.lab(sec)
        self.assertEqual(s['estado_seccion'], 'dejo_de_funcionar')
        self.assertEqual(self.cat(True)['secciones'][0]['estado_seccion'], 'dejo_de_funcionar')

    def test_no_funciono_and_same_combination_warning(self):
        sec = 'barril-de-la-semana'
        r1, r2 = self.pieza('2026-10-20-barril-r1')['id'], self.pieza('2026-10-27-barril-r2')['id']
        self.publicar(r1)
        self.assertEqual(self.api('editor', 'POST', f"/cms/api/hub/variantes/{self.detalle(r2)['variantes'][0]['id']}/metricas",
                                  {'likes': 1}).status_code, 409)  # sin publicar
        self.medir(r1, 10)
        aviso = self.lab(sec)['avisos']
        self.assertEqual([(a['tipo'], a['prueba'], a['pieza_id']) for a in aviso], [('misma_combinacion', 'R2', r2)])
        self.assertEqual(self.detalle(r2)['avisos_laboratorio'][0]['prueba'], 'R2')
        self.ok(self.put_pieza(r2, {'hora': '15:30'}))
        self.assertEqual(self.lab(sec)['avisos'], [])
        self.ok(self.put_pieza(r2, {'hora': '12:30', 'plantilla_id': self.id('plantillas', 'volteo-etiqueta')}))
        self.assertEqual(self.lab(sec)['avisos'], [])
        self.ok(self.put_pieza(r2, {'plantilla_id': None}))
        self.assertEqual(len(self.lab(sec)['avisos']), 1)
        self.publicar(r2)
        res = self.medir(r2, 20)
        self.assertEqual(res['seccion']['estado_prueba'], 'no_funciono')
        self.assertIsNone(res['seccion']['estado_seccion'])
        self.assertEqual(self.api('editor', 'POST', f"/cms/api/hub/variantes/{self.detalle(r2)['variantes'][0]['id']}/metricas",
                                  {}).status_code, 400)

    def test_section_state_rules(self):
        m = lambda pct: {'pct': pct, 'resultado': 'supero' if pct > 120 else 'cumplio' if pct >= 100 else 'no_cumplio'}
        self.assertEqual(estado_seccion_calculado([m(130), m(140), m(90)]), 'buena')
        self.assertEqual(estado_seccion_calculado([m(105), m(110), m(50)]), 'normal')
        self.assertEqual(estado_seccion_calculado([m(70), m(90), m(80), m(200), m(30)]), 'saturada')
        self.assertEqual(estado_seccion_calculado([m(30), m(50), m(40)]), 'dejo_de_funcionar')
        self.assertIsNone(estado_seccion_calculado([]))


class SummaryPresentationSettings(HubBase):
    def test_summary(self):
        r1 = self.pieza('2026-10-20-barril-r1')['id']
        self.a_revision(r1)
        res = self.ok(self.api('editor', 'GET', '/cms/api/hub/resumen?desde=2026-10-19&hasta=2026-11-01'))
        self.assertEqual((res['desde'], res['hasta'], res['total']), ('2026-10-19', '2026-11-01', 3))
        self.assertEqual((res['conteos']['revision'], res['conteos']['borrador'], res['conteos']['idea']), (1, 1, 1))
        self.assertEqual([p['id'] for p in res['pendientes_aprobacion']], [r1])
        ig = next(c for c in res['kpis']['posts_semana'] if c['canal_clave'] == 'ig')
        self.assertEqual(ig['meta'], 3.5)
        self.assertEqual(ig['semanas'], [{'semana': '2026-10-19', 'planeadas': 1, 'publicadas': 0},
                                         {'semana': '2026-10-26', 'planeadas': 1, 'publicadas': 0}])
        eq = {e['clave']: e for e in res['kpis']['equilibrio_pilares']}
        self.assertEqual((eq['barril']['piezas'], eq['barril']['real_pct'], eq['barril']['objetivo_pct']), (2, 100.0, 60))
        self.assertEqual(res['laboratorio']['no_empezada'], 2)
        self.assertEqual(res['kpis']['kpi_estrella'], 'Visitas atribuidas por semana')
        self.assertEqual(self.api('editor', 'GET', '/cms/api/hub/resumen?desde=2026-11-01&hasta=2026-10-01').status_code, 400)
        self.assertIn('desde', self.ok(self.api('editor', 'GET', '/cms/api/hub/resumen')))

    def test_presentation_publish_and_public_get(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get('/cms/hub/presentacion.json').status_code, 404)
        r1 = self.pieza('2026-10-20-barril-r1')['id']
        self.ok(self.put_pieza(r1, {'responsable_id': 2}))
        self.ok(self.api('editor', 'POST', f'/cms/api/hub/piezas/{r1}/comentarios', {'texto': 'COMENTARIO-PRIVADO'}), 201)
        self.a_revision(r1)
        self.ok(self.api('editor', 'POST', f'/cms/api/hub/piezas/{r1}/enlace-aprobacion'), 201)
        self.assertEqual(self.api('editor', 'POST', '/cms/api/hub/presentacion/publicar').status_code, 403)
        pub = self.ok(self.api('owner', 'POST', '/cms/api/hub/presentacion/publicar'))
        self.assertEqual(pub['piezas'], 2)  # la idea no sale
        r = anon.get('/cms/hub/presentacion.json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('application/json', r.headers['Content-Type'])
        texto = r.data.decode()
        for prohibido in ('COMENTARIO-PRIVADO', 'token', 'responsable', 'Propietario', 'Editor', 'brief', 'sin personas bebiendo',
                          'Confirmar barril', 'aprobaciones', 'comentarios', '"id"', 'contacto', 'Solo pruebas'):
            self.assertNotIn(prohibido, texto, prohibido)
        data = r.json
        self.assertEqual(data['tipo'], 'hub-presentacion')
        self.assertEqual(data['piloto']['inicio'], '2026-10-19')
        self.assertEqual({p['clave'] for p in data['piezas']}, {'2026-10-20-barril-r1', '2026-10-27-barril-r2'})
        pieza = next(p for p in data['piezas'] if p['clave'] == '2026-10-20-barril-r1')
        self.assertEqual((pieza['seccion'], pieza['pilar'], pieza['pendientes_validar']), ('barril-de-la-semana', 'barril', 1))
        self.assertEqual(pieza['variantes'][0]['canal'], 'ig')
        self.assertEqual(data['formatos'][0]['canal'], 'ig')
        self.assertEqual(len(data['laboratorio']), 2)
        self.assertEqual(data['resumen']['desde'], '2026-10-19')
        self.assertTrue((Path(self.tmp.name) / 'hub-presentacion.json').is_file())

    def test_settings_never_return_secrets(self):
        aj = self.ok(self.api('editor', 'GET', '/cms/api/hub/ajustes'))
        self.assertFalse(aj['editable'])
        self.assertEqual(aj['integraciones'], {'meta_api': {'configurado': False}, 'postiz': {'configurado': False}})
        ig = self.id('canales', 'ig')
        self.assertEqual(self.api('editor', 'PUT', '/cms/api/hub/ajustes', {'leyenda': 'X'}).status_code, 403)
        with patch.dict(os.environ, {'HUB_META_TOKEN': 'SUPER-SECRETO-123', 'HUB_POSTIZ_URL': ''}):
            aj = self.ok(self.api('owner', 'PUT', '/cms/api/hub/ajustes', {
                'canales': [{'id': ig, 'metodo': 'meta_api'}], 'leyenda': 'EVITE EL EXCESO',
                'roles': [{'user_id': 2, 'roles': ['productor', 'community']}]}))
            raw = self.api('owner', 'GET', '/cms/api/hub/ajustes').data.decode()
        self.assertNotIn('SUPER-SECRETO-123', raw)
        canal = next(c for c in aj['canales'] if c['id'] == ig)
        self.assertEqual((canal['metodo'], canal['configurado']), ('meta_api', True))
        self.assertEqual(aj['integraciones']['postiz'], {'configurado': False})
        self.assertEqual(next(r for r in aj['roles'] if r['user_id'] == 2)['roles'], ['community', 'productor'])
        aj = self.ok(self.api('owner', 'GET', '/cms/api/hub/ajustes'))
        self.assertFalse(next(c for c in aj['canales'] if c['id'] == ig)['configurado'])
        for malo in ({'canales': [{'id': ig, 'metodo': 'fax'}]}, {'roles': [{'user_id': 99, 'roles': ['aprobador']}]},
                     {'roles': [{'user_id': 2, 'roles': ['jefe']}]}, {'zona': 'Marte/Base'}, {'leyenda': ''}):
            with self.subTest(malo):
                self.assertEqual(self.api('owner', 'PUT', '/cms/api/hub/ajustes', malo).status_code, 400)
        # El rol de aprobador del Hub habilita aprobar a un editor del CMS.
        self.ok(self.api('owner', 'PUT', '/cms/api/hub/ajustes', {'roles': [{'user_id': 2, 'roles': ['aprobador']}]}))
        pid = self.pieza('2026-10-20-barril-r1')['id']
        self.a_revision(pid)
        self.ok(self.estado(pid, 'aprobada', 'editor'))


class StaticAndSeed(HubBase):
    def test_hub_static_rules_win_over_cms_name_route(self):
        sitio = Path(self.tmp.name) / 'sitio-hub'
        (sitio / 'cms').mkdir(parents=True)
        anon = self.app.test_client()
        self.app.config['CMS_SITE'] = str(sitio)
        self.assertEqual(anon.get('/cms/hub.js').status_code, 404)
        (sitio / 'cms' / 'hub.js').write_text('window.CisneHub={};')
        (sitio / 'cms' / 'hub.css').write_text('.hub{}')
        r = anon.get('/cms/hub.js')
        self.assertEqual(r.status_code, 200)  # /cms/<name> solo sirve cms.css y cms.js
        self.assertIn(b'CisneHub', r.data)
        self.assertEqual(anon.get('/cms/hub.css').data, b'.hub{}')
        self.assertEqual(anon.get('/cms/cms.js').status_code, 200)  # el CMS sigue sirviendo lo suyo
        self.assertEqual(anon.get('/cms/otro.js').status_code, 404)
        dev = anon.get('/cms/hub-dev.html')
        self.assertEqual(dev.status_code, 200)
        self.assertIn(b'/cms/hub.js', dev.data)

    def test_hub_dev_page_only_in_dev(self):
        tmp = tempfile.TemporaryDirectory(prefix='cisne-hub-prod-')
        try:
            app = create_app({'CMS_ROOT': tmp.name, 'CMS_SITE': str(ROOT / 'sitio'), 'CMS_DEV': False,
                              'CMS_ORIGIN': 'http://localhost', 'TESTING': True})
            register_hub(app)
            self.assertEqual(app.test_client().get('/cms/hub-dev.html').status_code, 404)
            app.extensions['cms_media'].close()
        finally:
            tmp.cleanup()

    def test_seed_idempotent_and_preserves_hub_edits(self):
        data = json.loads(SEMILLA.read_text(encoding='utf-8'))
        stats = hub_seed.cargar(self.tmp.name, data)
        self.assertEqual(stats['creados'], {})
        self.assertEqual(stats['actualizados'], {})
        self.assertEqual(stats['sin_cambios']['piezas'], 3)
        with self.app.extensions['hub_db']() as con:
            conteo = {t: con.execute(f'select count(*) from {t}').fetchone()[0]
                      for t in ('canales', 'formatos', 'secciones', 'temas', 'piezas', 'variantes', 'valores', 'versiones')}
        self.assertEqual(conteo, {'canales': 3, 'formatos': 5, 'secciones': 2, 'temas': 2, 'piezas': 3, 'variantes': 4,
                                  'valores': 2, 'versiones': 3})
        # Cambio en la semilla: se actualiza la pieza que nadie tocó; la editada en el Hub se conserva.
        r1 = self.pieza('2026-10-20-barril-r1')['id']
        self.ok(self.put_pieza(r1, {'titulo': 'Editada en el Hub'}))
        data['piezas'][0]['titulo'] = 'Cambio de semilla R1'
        data['piezas'][1]['titulo'] = 'Cambio de semilla R2'
        data['canales'][0]['cadencia'] = '4 por semana'
        stats = hub_seed.cargar(self.tmp.name, data)
        self.assertEqual(stats['conservadas'], ['2026-10-20-barril-r1'])
        self.assertEqual(stats['actualizados'], {'canales': 1, 'piezas': 1})
        self.assertEqual(self.pieza('2026-10-20-barril-r1')['titulo'], 'Editada en el Hub')
        self.assertEqual(self.pieza('2026-10-27-barril-r2')['titulo'], 'Cambio de semilla R2')
        # Una semilla inválida no escribe nada.
        malo = json.loads(SEMILLA.read_text(encoding='utf-8'))
        malo['canales'][0]['nombre'] = 'Instagram cambiado'
        malo['piezas'][1]['variantes'][0]['canal'] = 'inexistente'
        with self.assertRaises(ValueError):
            hub_seed.cargar(self.tmp.name, malo)
        self.assertEqual(next(c for c in self.cat(True)['canales'] if c['clave'] == 'ig')['nombre'], 'Instagram')
        # --reset vacía y vuelve a cargar sin duplicar.
        stats = hub_seed.cargar(self.tmp.name, json.loads(SEMILLA.read_text(encoding='utf-8')), reset=True)
        self.assertEqual(stats['creados']['piezas'], 3)
        self.assertEqual(len(self.ok(self.api('owner', 'GET', '/cms/api/hub/piezas'))['items']), 3)

    def test_seed_cli(self):
        root = Path(self.tmp.name) / 'otro-root'
        out = io.StringIO()
        with patch('sys.stdout', out):
            self.assertEqual(hub_seed.main(['--root', str(root), '--seed', str(SEMILLA)]), 0)
        self.assertEqual(json.loads(out.getvalue())['creados']['piezas'], 3)
        with patch('sys.stdout', io.StringIO()):
            self.assertEqual(hub_seed.main(['--root', str(root), '--seed', str(SEMILLA)]), 0)
        with patch('sys.stderr', io.StringIO()):
            self.assertEqual(hub_seed.main(['--root', str(root), '--seed', str(root / 'no-existe.json')]), 1)

    @unittest.skipUnless(SEMILLA_REAL.is_file(), 'La semilla real aún no existe')
    def test_real_seed_loads_twice(self):
        data = json.loads(SEMILLA_REAL.read_text(encoding='utf-8'))
        root = Path(self.tmp.name) / 'real'
        primera = hub_seed.cargar(root, data)
        self.assertTrue(primera['creados'].get('piezas'))
        segunda = hub_seed.cargar(root, data)
        self.assertEqual(segunda['creados'], {})
        self.assertEqual(segunda['actualizados'], {})


if __name__ == '__main__':
    unittest.main()
