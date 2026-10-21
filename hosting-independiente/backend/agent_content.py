"""Operaciones editoriales acotadas, compartidas por el CMS y sus agentes.

Este módulo no publica contenido, modifica cuentas ni consulta datos operativos.
Las funciones puras trabajan sobre copias; el servicio conserva la transacción,
la versión y la identidad de la sesión del CMS.
"""
from copy import deepcopy
import json

from flask import g, jsonify

from cms_content import ID_RE, validate_document


COMMON_PRODUCT_FIELDS = frozenset({
    'nombre', 'nombre_completo', 'descripcion', 'detalle', 'img', 'etiqueta',
    'visible', 'disponible',
})
BEER_FIELDS = frozenset({
    'estilo', 'abv', 'ibu', 'perfil', 'cerveceria', 'origen', 'historia', 'notas',
})
FIELDS = {
    'barril': COMMON_PRODUCT_FIELDS | BEER_FIELDS | {'precios', 'marida_con', 'marida_oficial'},
    'latas': COMMON_PRODUCT_FIELDS | BEER_FIELDS | {'precio'},
    'sin_alcohol': COMMON_PRODUCT_FIELDS | {'precio', 'variantes'},
    'comida': COMMON_PRODUCT_FIELDS | {'precio', 'variantes'},
    'events': frozenset({'title', 'date', 'description', 'image', 'alt', 'url', 'visible', 'width', 'height'}),
    'gallery': frozenset({'image', 'alt', 'caption', 'width', 'height', 'wide'}),
}
BUSINESS_FIELDS = frozenset({
    'nombre', 'descriptor', 'eslogan', 'direccion', 'telefono', 'telefono_display',
    'email', 'horario', 'geo', 'facebook_url', 'instagram_url', 'tiktok_url',
    'google_maps_url', 'google_review_url', 'uber_eats_url', 'whatsapp_url',
})
COLLECTIONS = frozenset(FIELDS) | {'page', 'negocio'}
REQUIRED = {
    'barril': ['nombre', 'estilo', 'abv', 'perfil', 'precios'],
    'latas': ['nombre', 'estilo', 'abv', 'perfil', 'precio'],
    'sin_alcohol': ['nombre', 'precio'],
    'comida': ['nombre', 'precio'],
    'events': ['title', 'image'],
    'gallery': ['image'],
}


class ContentError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status_code = status


def _identity(value, label='ID'):
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ContentError(f'{label}: usa un identificador estable, sin rutas ni índices.')
    return value


def _collection(document, collection, category_id=None):
    if not isinstance(collection, str) or collection not in COLLECTIONS:
        raise ContentError('Colección editorial no permitida.')
    if collection == 'comida':
        _identity(category_id, 'ID de categoría')
        category = next((row for row in document['menu']['comida'] if row['id'] == category_id), None)
        if category is None:
            raise ContentError('Categoría no encontrada.', 404)
        return category['items']
    if category_id is not None:
        raise ContentError('category_id solo se admite para comida.')
    if collection == 'page':
        return document['page']
    if collection == 'negocio':
        return document['menu']['negocio']
    if collection in ('events', 'gallery'):
        return document[collection]
    return document['menu'][collection]


def _fields(document, collection):
    if collection == 'page':
        return frozenset(document['page'])
    if collection == 'negocio':
        return BUSINESS_FIELDS & document['menu']['negocio'].keys()
    return FIELDS[collection]


def content_schema(document):
    """Describe los campos permitidos sin convertir índices en identificadores."""
    return {
        'collections': {
            collection: {
                'actions': ['update'] if collection in ('page', 'negocio') else ['create', 'update', 'delete'],
                'fields': sorted(_fields(document, collection)),
                'required_on_create': REQUIRED.get(collection, []),
                'requires_id': collection not in ('page', 'negocio'),
                'requires_category_id': collection == 'comida',
            }
            for collection in sorted(COLLECTIONS)
        },
        'food_categories': [{'id': row['id'], 'name': row['seccion']} for row in document['menu']['comida']],
        'beer_profiles': deepcopy(document['menu']['perfiles']),
        'write_target': 'draft',
        'operation': {'action': 'create|update|delete', 'collection': 'collection name',
                      'id': 'stable ID for collection items', 'category_id': 'food category ID only',
                      'data': 'allowed fields; omitted for delete'},
    }


def read_content(document, collection, item_id=None, category_id=None):
    """Devuelve una copia de la colección o de un elemento por su ID estable."""
    target = _collection(document, collection, category_id)
    if collection in ('page', 'negocio'):
        if item_id is not None:
            raise ContentError('Esta colección es un objeto único y no admite ID.')
        return deepcopy(target)
    if item_id is None:
        return deepcopy(target)
    _identity(item_id)
    item = next((row for row in target if row['id'] == item_id), None)
    if item is None:
        raise ContentError('Contenido no encontrado.', 404)
    return deepcopy(item)


def _nested_fields(data):
    """Rechaza claves opacas también en los campos estructurados editables."""
    nested = {
        'precios': {'medida', 'precio'},
        'variantes': {'id', 'nombre', 'precio', 'extra', 'visible', 'disponible'},
        'horario': {'dias', 'horas'},
    }
    for field, allowed in nested.items():
        if field not in data:
            continue
        rows = data[field]
        if not isinstance(rows, list) or any(not isinstance(row, dict) or set(row) - allowed for row in rows):
            raise ContentError(f'{field}: estructura o campos no permitidos.')
    if 'geo' in data and (not isinstance(data['geo'], dict) or set(data['geo']) - {'lat', 'lng'}):
        raise ContentError('geo: solo se admiten lat y lng.')


def apply_operation(document, operation):
    """Aplica UNA operación; devuelve (documento validado nuevo, cambio).

    No cambia el argumento original, ni siquiera si falla la validación. No
    repara referencias borradas automáticamente: el CMS exige resolverlas.
    """
    if not isinstance(operation, dict) or set(operation) - {'action', 'collection', 'id', 'category_id', 'data'}:
        raise ContentError('Operación editorial no válida o con campos no permitidos.')
    action, collection = operation.get('action'), operation.get('collection')
    if not isinstance(action, str) or action not in ('create', 'update', 'delete'):
        raise ContentError('Acción no permitida: usa create, update o delete.')
    result = deepcopy(document)
    target = _collection(result, collection, operation.get('category_id'))
    singleton = collection in ('page', 'negocio')
    if singleton and (action != 'update' or 'id' in operation):
        raise ContentError('Página y negocio solo admiten actualización parcial, sin ID.')
    item_id = None if singleton else _identity(operation.get('id'))
    if action == 'delete':
        if 'data' in operation:
            raise ContentError('Eliminar no admite data.')
        data = {}
    else:
        data = operation.get('data')
        if not isinstance(data, dict) or not data or any(not isinstance(key, str) for key in data):
            raise ContentError('Indica al menos un campo en data.')
        unknown = set(data) - _fields(result, collection)
        if unknown:
            raise ContentError('Campos no permitidos: ' + ', '.join(sorted(unknown)) + '.')
        _nested_fields(data)
    if singleton:
        before = {key: deepcopy(target.get(key)) for key in data}
        target.update(deepcopy(data))
        after = {key: deepcopy(target[key]) for key in data}
    else:
        item = next((row for row in target if row['id'] == item_id), None)
        if action == 'create':
            if item is not None:
                raise ContentError('Ya existe un elemento con ese ID.', 409)
            before = None
            after = {'id': item_id, **deepcopy(data)}
            target.append(after)
        else:
            if item is None:
                raise ContentError('Contenido no encontrado.', 404)
            before = deepcopy(item)
            if action == 'delete':
                target.remove(item)
                after = None
            else:
                item.update(deepcopy(data))
                after = deepcopy(item)
    validated = validate_document(result)
    if not singleton and after is not None:
        after = read_content(validated, collection, item_id, operation.get('category_id'))
    return validated, {'action': action, 'collection': collection, 'id': item_id,
                       'category_id': operation.get('category_id'), 'before': before, 'after': after}


class AgentContentService:
    def __init__(self, db, audit, now, encoded):
        self.db, self.audit, self.now, self.encoded = db, audit, now, encoded

    @staticmethod
    def _user():
        user = getattr(g, 'user', None)
        if not user:
            raise ContentError('Inicia sesión con tu cuenta del equipo.', 401)
        if user['role'] not in ('owner', 'editor'):
            raise ContentError('Tu cuenta no puede editar contenido.', 403)
        return user

    def read(self):
        self._user()
        with self.db() as con:
            row = con.execute('select version,data from draft where id=1').fetchone()
            published = int(con.execute("select value from settings where key='published'").fetchone()[0])
        document = json.loads(row['data'])
        return {'document': document, 'version': row['version'], 'published_version': published,
                'schema': content_schema(document)}

    def mutate(self, version, operation):
        user = self._user()
        if type(version) is not int or version < 1:
            raise ContentError('version debe ser un entero positivo.')
        with self.db() as con:
            con.execute('begin immediate')
            row = con.execute('select version,data from draft where id=1').fetchone()
            if version != row['version']:
                raise ContentError('Otra persona guardó cambios. Recarga antes de continuar.', 409)
            document, change = apply_operation(json.loads(row['data']), operation)
            next_version = version + 1
            con.execute('update draft set version=?,data=?,updated_at=?,author=? where id=1',
                        (next_version, self.encoded(document), self.now(), user['name']))
            entity = change['collection'] + (':' + change['id'] if change['id'] else '')
            self.audit(con, f'Agente: {change["action"]} {entity} · borrador {next_version}')
        return {'version': next_version, 'document': document, 'schema': content_schema(document),
                'change': change, 'preview_url': '/cms/preview/'}


def register_agent_content(app, db, body, audit, now, encoded):
    service = AgentContentService(db, audit, now, encoded)
    app.extensions['agent_content'] = service

    @app.get('/cms/api/agent/content')
    def agent_content_read():
        return jsonify(service.read())

    @app.post('/cms/api/agent/content')
    def agent_content_mutate():
        payload = body()
        if set(payload) - {'version', 'operation'}:
            raise ContentError('Solo se admiten version y operation.')
        return jsonify(service.mutate(payload.get('version'), payload.get('operation')))
