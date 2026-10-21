"""Content Hub de Cisne Negro: Blueprint de Flask montado sobre el CMS.

Uso: ``from cms_hub import register_hub; register_hub(app)`` al final de ``create_app``.

- Datos propios en ``<CMS_ROOT>/hub.sqlite`` (WAL, claves foráneas, migraciones por
  ``PRAGMA user_version``). De ``cms.sqlite`` solo se leen usuarios (id, name, role).
- MediaHub se consulta con ``app.extensions['cms_media']`` (``get`` y ``list``).
- La sesión, el CSRF y la comprobación de Origin los aplica el CMS en ``before_request``
  para todo ``/cms/api/*``. Las rutas públicas (``/cms/hub/*``, ``/cms/aprobar/*``) no
  requieren sesión; la aprobación usa un token de un solo uso cuyo sha256 se guarda.
- Este módulo no importa Flask al cargarse: ``hub_seed.py`` reutiliza el esquema y las
  validaciones sin levantar el servidor.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import html
import io
import json
import math
import os
import re
import secrets
import sqlite3
import time
import unicodedata
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes de dominio
# ---------------------------------------------------------------------------
METODOS = ('manual', 'meta_api', 'postiz')
ESTADOS = ('idea', 'borrador', 'revision', 'observada', 'aprobada', 'programada', 'publicada', 'error')
TRANSICIONES = {
    'idea': ('borrador',),
    'borrador': ('revision',),
    'revision': ('aprobada', 'observada'),
    'observada': ('borrador',),
    'aprobada': ('programada',),
    'programada': ('publicada', 'error'),
    'error': ('programada',),
    'publicada': (),
}
ESTADOS_PUB = ('pendiente', 'programada', 'publicada', 'error', 'omitida')
ESTADOS_PUB_EDITABLES = ('pendiente', 'programada', 'omitida')
PRUEBAS = ('R1', 'R2', 'R3')
ESTADOS_PRUEBA = ('no_empezada', 'empezada', 'vigente', 'no_funciono')
ESTADOS_SECCION = ('normal', 'buena', 'saturada', 'dejo_de_funcionar')
ROLES_HUB = ('aprobador', 'productor', 'community')
CHECKLIST_CERVEZA = ('leyenda', 'sin_consumo_en_cuadro', 'personas_25_mas', 'sin_imperativo', 'sin_asociacion_prohibida')
CHECKLIST = CHECKLIST_CERVEZA + ('datos_verificados',)
ENTIDADES = {'pieza': 'piezas', 'seccion': 'secciones', 'aliado': 'aliados', 'campana': 'campanas'}
TIPOS_ATRIBUTO = ('texto', 'numero', 'lista', 'fecha', 'booleano', 'usuario', 'cerveza')
LEYENDA = 'EVITE EL EXCESO'
ZONA = 'America/Mexico_City'
APROBACION_DIAS = 7
MAX_BODY = 1024 * 1024
LIMITE_PUBLICO = 30          # solicitudes públicas de aprobación por IP en la ventana
VENTANA_PUBLICA = 600        # segundos

# Límites de caracteres por red (§5). YouTube: título 100 y descripción 5,000.
LIMITES_RED = {
    'instagram': {'copy': 2200}, 'facebook': {'copy': 63206}, 'tiktok': {'copy': 2200},
    'threads': {'copy': 500}, 'youtube': {'copy': 5000, 'titulo': 100}, 'gbp': {'copy': 1500},
}
ALIAS_RED = {
    'ig': 'instagram', 'insta': 'instagram', 'instagram': 'instagram',
    'fb': 'facebook', 'facebook': 'facebook',
    'tiktok': 'tiktok', 'tt': 'tiktok',
    'threads': 'threads', 'th': 'threads',
    'yt': 'youtube', 'youtube': 'youtube', 'youtube-shorts': 'youtube', 'shorts': 'youtube', 'yt-shorts': 'youtube',
    'gbp': 'gbp', 'google': 'gbp', 'google-business': 'gbp', 'google-business-profile': 'gbp',
}

CLAVE_RE = re.compile(r'^[a-z0-9][a-z0-9_.-]{0,79}$')
HORA_RE = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
FECHA_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
COLOR_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')
URL_RE = re.compile(r'^https?://[^\s<>"\']{1,490}$')
MEDIA_ID_RE = re.compile(r'^[a-f0-9]{32}$')
TOKEN_RE = re.compile(r'^[A-Za-z0-9_-]{40,64}$')
SECRETO_RE = re.compile(r'token|secret|password|passwd|contrase|api[_-]?key|apikey|bearer|credencial|client[_-]?id', re.I)


class HubError(ValueError):
    """Error de validación o de regla de negocio. El CMS lo convierte en ``{error}``."""

    def __init__(self, message, status=400, **extra):
        super().__init__(message)
        self.status_code = status
        self.extra = extra


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def sha256(value):
    return hashlib.sha256(value.encode()).hexdigest()


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def loads(value, default):
    if value in (None, ''):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def slug(text):
    s = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:60].strip('-')
    return s or 'item'


def hoy(zona=ZONA):
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(zona)).date()
    except Exception:  # sin tzdata: UTC-6 fijo
        return (datetime.now(timezone.utc) - timedelta(hours=6)).date()


# ---------------------------------------------------------------------------
# Esquema y conexión
# ---------------------------------------------------------------------------
_COMUNES = 'creado_at text not null, actualizado_at text not null, archivado integer not null default 0'
MIGRACIONES = [
    f'''
    create table if not exists canales(id integer primary key, clave text unique not null, nombre text not null,
      handle text not null default '', color text not null default '', icono text not null default '',
      metodo text not null default 'manual' check(metodo in ('manual','meta_api','postiz')),
      rol text not null default '', cadencia text not null default '', config text not null default '{{}}',
      orden integer not null default 0, {_COMUNES});
    create table if not exists formatos(id integer primary key, clave text unique not null,
      canal_id integer not null references canales(id), nombre text not null, tipo text not null default '',
      proporcion text not null default '', max_caracteres integer, max_laminas integer, max_segundos integer,
      interaccion_ideal real, {_COMUNES});
    create table if not exists plantillas(id integer primary key, clave text unique not null, nombre text not null,
      que_es text not null default '', virtud text not null default '', que_se_necesita text not null default '',
      tiempo text not null default '', origen text not null default '', enlace text not null default '', {_COMUNES});
    create table if not exists pilares(id integer primary key, clave text unique not null, nombre text not null,
      color text not null default '', objetivo_pct real, descripcion text not null default '',
      orden integer not null default 0, {_COMUNES});
    create table if not exists topicos(id integer primary key, clave text unique not null,
      pilar_id integer not null references pilares(id), nombre text not null, orden integer not null default 0, {_COMUNES});
    create table if not exists secciones(id integer primary key, clave text unique not null,
      topico_id integer not null references topicos(id), nombre text not null, descripcion text not null default '',
      periodicidad text not null default '', formato_id integer references formatos(id),
      plantilla_id integer references plantillas(id), tiempo_produccion_min integer, interaccion_ideal real,
      estado_prueba text not null default 'no_empezada' check(estado_prueba in ('no_empezada','empezada','vigente','no_funciono')),
      estado_seccion text check(estado_seccion is null or estado_seccion in ('normal','buena','saturada','dejo_de_funcionar')),
      en_piloto integer not null default 0, {_COMUNES});
    create table if not exists aliados(id integer primary key, clave text unique not null, nombre text not null,
      tipo text not null default '', contacto text not null default '', nota text not null default '', {_COMUNES});
    create table if not exists campanas(id integer primary key, clave text unique not null, nombre text not null,
      inicio text, fin text, objetivo text not null default '', {_COMUNES});
    create table if not exists atributos(id integer primary key, clave text unique not null,
      entidad text not null check(entidad in ('pieza','seccion','aliado','campana')), nombre text not null,
      tipo text not null check(tipo in ('texto','numero','lista','fecha','booleano','usuario','cerveza')),
      opciones text not null default '[]', requerido integer not null default 0, filtrable integer not null default 0,
      columna integer not null default 0, orden integer not null default 0, {_COMUNES});
    create table if not exists valores(id integer primary key, atributo_id integer not null references atributos(id),
      entidad text not null, entidad_id integer not null, valor text not null,
      creado_at text not null, actualizado_at text not null, unique(atributo_id, entidad, entidad_id));
    create index if not exists valores_entidad on valores(entidad, entidad_id);
    create table if not exists piezas(id integer primary key, clave text unique not null, titulo text not null,
      seccion_id integer references secciones(id), campana_id integer references campanas(id),
      aliado_id integer references aliados(id), plantilla_id integer references plantillas(id),
      responsable_id integer, fecha text, hora text,
      estado text not null default 'borrador' check(estado in ('idea','borrador','revision','observada','aprobada','programada','publicada','error')),
      prueba text check(prueba is null or prueba in ('R1','R2','R3')), objetivo text not null default '',
      brief text not null default '', copy_base text not null default '', por_validar text not null default '[]',
      cumplimiento text not null default '{{}}', version integer not null default 1, {_COMUNES});
    create index if not exists piezas_fecha on piezas(archivado, fecha);
    create table if not exists temas(id integer primary key, seccion_id integer not null references secciones(id),
      titulo text not null, explicacion text not null default '',
      usado integer references piezas(id) on delete set null, {_COMUNES});
    create table if not exists variantes(id integer primary key,
      pieza_id integer not null references piezas(id) on delete cascade,
      canal_id integer not null references canales(id), formato_id integer references formatos(id),
      titulo text not null default '', copy text not null default '', hashtags text not null default '[]',
      media_ids text not null default '[]', fecha text, hora text,
      estado_pub text not null default 'pendiente' check(estado_pub in ('pendiente','programada','publicada','error','omitida')),
      url_publicada text not null default '', id_externo text not null default '', error text not null default '',
      publicado_at text, {_COMUNES});
    create index if not exists variantes_pieza on variantes(pieza_id);
    create table if not exists versiones(id integer primary key,
      pieza_id integer not null references piezas(id) on delete cascade, version integer not null,
      datos text not null, autor text not null, creado_at text not null);
    create index if not exists versiones_pieza on versiones(pieza_id, version);
    create table if not exists comentarios(id integer primary key,
      pieza_id integer not null references piezas(id) on delete cascade, autor text not null, texto text not null,
      interno integer not null default 1, creado_at text not null);
    create table if not exists aprobaciones(id integer primary key,
      pieza_id integer not null references piezas(id) on delete cascade, token_hash text unique not null,
      expira integer not null, decision text check(decision is null or decision in ('aprobada','cambios')),
      motivo text not null default '', quien text not null default '', decidido_at text,
      creado_por text not null default '', creado_at text not null);
    create table if not exists metricas(id integer primary key,
      variante_id integer not null references variantes(id) on delete cascade, medido_at text not null,
      horas_desde_pub real, likes integer, comentarios integer, compartidos integer, guardados integer,
      envios integer, alcance integer, vistas integer,
      fuente text not null default 'manual' check(fuente in ('manual','api')), creado_at text not null);
    create index if not exists metricas_variante on metricas(variante_id);
    create table if not exists roles_hub(id integer primary key, user_id integer not null,
      rol text not null check(rol in ('aprobador','productor','community')), creado_at text not null,
      unique(user_id, rol));
    create table if not exists actividad(id integer primary key, actor text not null, accion text not null,
      entidad text not null default '', entidad_id integer, creado_at text not null);
    create table if not exists ajustes(clave text primary key, valor text not null, actualizado_at text not null);
    create table if not exists intentos(clave text not null, at integer not null);
    create index if not exists intentos_clave on intentos(clave, at);
    ''',
]


@contextmanager
def connect(path):
    con = sqlite3.connect(str(path), timeout=20)
    con.row_factory = sqlite3.Row
    con.execute('pragma foreign_keys=on')
    con.execute('pragma busy_timeout=20000')
    try:
        with con:
            yield con
    finally:
        con.close()


def init_db(path):
    """Crea o migra ``hub.sqlite``. Idempotente: cada migración se aplica una vez."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=20)
    try:
        con.execute('pragma journal_mode=wal')
        con.execute('pragma foreign_keys=on')
        actual = con.execute('pragma user_version').fetchone()[0]
        for numero, script in enumerate(MIGRACIONES, start=1):
            if actual < numero:
                con.executescript(script)
                con.execute(f'pragma user_version={int(numero)}')
                con.commit()
    finally:
        con.close()
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def registrar(con, actor, accion, entidad='', entidad_id=None):
    con.execute('insert into actividad(actor,accion,entidad,entidad_id,creado_at) values(?,?,?,?,?)',
                (str(actor)[:120], str(accion)[:300], entidad, entidad_id, now()))


def ajuste(con, clave, default=None):
    row = con.execute('select valor from ajustes where clave=?', (clave,)).fetchone()
    return loads(row[0], default) if row else default


def guardar_ajuste(con, clave, valor):
    con.execute('insert into ajustes(clave,valor,actualizado_at) values(?,?,?) on conflict(clave) do update set '
                'valor=excluded.valor, actualizado_at=excluded.actualizado_at', (clave, dumps(valor), now()))


# ---------------------------------------------------------------------------
# Validadores
# ---------------------------------------------------------------------------
def v_text(value, label, limit, required=False, strip=True):
    if value is None:
        value = ''
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        raise HubError(f'{label}: se esperaba texto.')
    if strip:
        value = value.strip()
    if '\x00' in value:
        raise HubError(f'{label}: contiene caracteres no válidos.')
    if len(value) > limit:
        raise HubError(f'{label}: máximo {limit} caracteres.')
    if required and not value:
        raise HubError(f'{label} es obligatorio.')
    return value


def v_int(value, label, lo, hi, nullable=True):
    if value is None or value == '':
        if nullable:
            return None
        raise HubError(f'{label} es obligatorio.')
    if isinstance(value, bool):
        raise HubError(f'{label}: se esperaba un número entero.')
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, str) and re.fullmatch(r'-?\d{1,12}', value.strip()):
        value = int(value.strip())
    if not isinstance(value, int):
        raise HubError(f'{label}: se esperaba un número entero.')
    if not lo <= value <= hi:
        raise HubError(f'{label}: debe estar entre {lo} y {hi}.')
    return value


def v_float(value, label, lo, hi, nullable=True):
    if value is None or value == '':
        if nullable:
            return None
        raise HubError(f'{label} es obligatorio.')
    if isinstance(value, bool):
        raise HubError(f'{label}: se esperaba un número.')
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            raise HubError(f'{label}: se esperaba un número.') from None
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise HubError(f'{label}: se esperaba un número.')
    if not lo <= value <= hi:
        raise HubError(f'{label}: debe estar entre {lo} y {hi}.')
    return float(value)


def v_bool(value, label):
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    raise HubError(f'{label}: se esperaba verdadero o falso.')


def v_fecha(value, label, nullable=True):
    if value in (None, ''):
        if nullable:
            return None
        raise HubError(f'{label} es obligatoria.')
    if not isinstance(value, str) or not FECHA_RE.fullmatch(value):
        raise HubError(f'{label}: usa el formato AAAA-MM-DD.')
    try:
        date.fromisoformat(value)
    except ValueError:
        raise HubError(f'{label}: fecha no válida.') from None
    return value


def v_hora(value, label):
    if value in (None, ''):
        return None
    if not isinstance(value, str) or not HORA_RE.fullmatch(value):
        raise HubError(f'{label}: usa el formato HH:MM (24 h).')
    return value


def v_enum(value, choices, label, nullable=False):
    if value in (None, '') and nullable:
        return None
    if value not in choices:
        raise HubError(f'{label}: valor no admitido.')
    return value


def v_color(value, label):
    value = v_text(value, label, 9)
    if value and not COLOR_RE.fullmatch(value):
        raise HubError(f'{label}: usa un color hexadecimal (#RRGGBB).')
    return value


def v_url(value, label, required=False):
    value = v_text(value, label, 500, required=required)
    if value and not URL_RE.fullmatch(value):
        raise HubError(f'{label}: debe ser un enlace http(s) válido.')
    return value


def v_clave(value, label='Clave'):
    if not isinstance(value, str) or not CLAVE_RE.fullmatch(value):
        raise HubError(f'{label}: usa minúsculas, números, punto, guion o guion bajo (máx. 80).')
    return value


def _sin_secretos(value, label, depth=0):
    if depth > 5:
        raise HubError(f'{label}: demasiados niveles.')
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str) or len(k) > 60:
                raise HubError(f'{label}: clave no válida.')
            if SECRETO_RE.search(k):
                raise HubError(f'{label}: no guardes secretos aquí; usa variables de entorno del servidor.')
            _sin_secretos(v, label, depth + 1)
    elif isinstance(value, list):
        for v in value:
            _sin_secretos(v, label, depth + 1)
    elif isinstance(value, float) and not math.isfinite(value):
        raise HubError(f'{label}: número no válido.')


def v_obj(value, label, max_bytes=8000):
    if value in (None, ''):
        return {}
    if not isinstance(value, dict):
        raise HubError(f'{label}: se esperaba un objeto.')
    _sin_secretos(value, label)
    if len(dumps(value)) > max_bytes:
        raise HubError(f'{label}: demasiado grande.')
    return value


def v_lista_texto(value, label, max_items, item_limit):
    if value in (None, ''):
        return []
    if not isinstance(value, list) or len(value) > max_items:
        raise HubError(f'{label}: se esperaba una lista de hasta {max_items} elementos.')
    out = []
    for item in value:
        item = v_text(item, label, item_limit)
        if item:
            out.append(item)
    return out


def v_media_ids(value, label, media_get=None):
    if value in (None, ''):
        return []
    if not isinstance(value, list) or len(value) > 20:
        raise HubError(f'{label}: se esperaba una lista de hasta 20 archivos.')
    out = []
    for mid in value:
        if not isinstance(mid, str) or not MEDIA_ID_RE.fullmatch(mid):
            raise HubError(f'{label}: identificador de MediaHub no válido.')
        if media_get is not None and not media_get(mid):
            raise HubError(f'{label}: el archivo {mid[:8]}… no existe en MediaHub.')
        if mid not in out:
            out.append(mid)
    return out


def v_cumplimiento(value):
    if value in (None, ''):
        return {}
    if not isinstance(value, dict):
        raise HubError('Checklist de cumplimiento: se esperaba un objeto.')
    out = {}
    for k, v in value.items():
        if k == 'notas':
            out[k] = v_text(v, 'Notas de cumplimiento', 1000)
            continue
        if k not in CHECKLIST:
            raise HubError(f'Checklist de cumplimiento: punto desconocido «{k}».')
        if v is None:
            continue
        if v == 'no_aplica' and k == 'datos_verificados':
            raise HubError('Los datos siempre deben verificarse; «no aplica» no se admite aquí.')
        if not (isinstance(v, bool) or v == 'no_aplica'):
            raise HubError(f'Checklist de cumplimiento: «{k}» admite sí, no o no aplica.')
        out[k] = v
    return out


def faltantes_checklist(cumplimiento):
    """Puntos que impiden enviar a revisión. Los cinco puntos de cerveza van todos en
    ``True`` o todos en ``'no_aplica'`` (pieza que no trata de cerveza);
    ``datos_verificados`` siempre debe ser ``True``."""
    c = cumplimiento or {}
    faltan = []
    if not all(c.get(k) == 'no_aplica' for k in CHECKLIST_CERVEZA):
        faltan = [k for k in CHECKLIST_CERVEZA if c.get(k) is not True]
    if c.get('datos_verificados') is not True:
        faltan.append('datos_verificados')
    return faltan


def red_de_canal(clave, nombre=''):
    clave = (clave or '').lower()
    if clave in ALIAS_RED:
        return ALIAS_RED[clave]
    base = clave.split('-')[0]
    if base in ALIAS_RED:
        return ALIAS_RED[base]
    n = (nombre or '').lower()
    for palabra, red in (('instagram', 'instagram'), ('facebook', 'facebook'), ('tiktok', 'tiktok'),
                         ('threads', 'threads'), ('youtube', 'youtube'), ('google', 'gbp')):
        if palabra in n:
            return red
    return None


def limites_variante(canal_clave, canal_nombre, max_caracteres_formato):
    red = red_de_canal(canal_clave, canal_nombre)
    lim = dict(LIMITES_RED.get(red, {}))
    if max_caracteres_formato:
        lim['copy'] = min(lim.get('copy', max_caracteres_formato), max_caracteres_formato)
    return lim


def caracteres(copy, hashtags):
    texto = copy or ''
    if hashtags:
        texto = (texto + ' ' if texto else '') + ' '.join(hashtags)
    return len(texto)


# ---------------------------------------------------------------------------
# Catálogos (whitelist de tablas y columnas: nunca se interpola entrada del usuario)
# ---------------------------------------------------------------------------
def F(kind, **kw):
    kw['kind'] = kind
    return kw


CATALOGOS = {
    'canales': {'tabla': 'canales', 'clave': True, 'orden': 'orden, nombre', 'etiqueta': 'Canal', 'campos': {
        'nombre': F('text', limit=80, required=True, label='Nombre'), 'handle': F('text', limit=120, label='Cuenta'),
        'color': F('color', label='Color'), 'icono': F('text', limit=40, label='Ícono'),
        'metodo': F('enum', choices=METODOS, default='manual', label='Método de publicación'),
        'rol': F('text', limit=1000, label='Rol'), 'cadencia': F('text', limit=300, label='Cadencia'),
        'config': F('obj', label='Configuración'), 'orden': F('int', lo=-10000, hi=10000, default=0, label='Orden')},
        'deps': (('formatos', 'canal_id'), ('variantes', 'canal_id'))},
    'formatos': {'tabla': 'formatos', 'clave': True, 'orden': 'canal_id, nombre', 'etiqueta': 'Formato', 'campos': {
        'canal_id': F('ref', tabla='canales', required=True, label='Canal'),
        'nombre': F('text', limit=80, required=True, label='Nombre'), 'tipo': F('text', limit=40, label='Tipo'),
        'proporcion': F('text', limit=20, label='Proporción'),
        'max_caracteres': F('int', lo=1, hi=100000, label='Máximo de caracteres'),
        'max_laminas': F('int', lo=1, hi=100, label='Máximo de láminas'),
        'max_segundos': F('int', lo=1, hi=36000, label='Duración máxima'),
        'interaccion_ideal': F('float', lo=0, hi=1e9, label='Interacción ideal')},
        'deps': (('secciones', 'formato_id'), ('variantes', 'formato_id'))},
    'plantillas': {'tabla': 'plantillas', 'clave': True, 'orden': 'nombre', 'etiqueta': 'Plantilla', 'campos': {
        'nombre': F('text', limit=120, required=True, label='Nombre'), 'que_es': F('text', limit=2000, label='Qué es'),
        'virtud': F('text', limit=2000, label='Virtud'), 'que_se_necesita': F('text', limit=2000, label='Qué se necesita'),
        'tiempo': F('text', limit=80, label='Tiempo'), 'origen': F('text', limit=200, label='Origen'),
        'enlace': F('url', label='Enlace')},
        'deps': (('secciones', 'plantilla_id'), ('piezas', 'plantilla_id'))},
    'pilares': {'tabla': 'pilares', 'clave': True, 'orden': 'orden, nombre', 'etiqueta': 'Pilar', 'campos': {
        'nombre': F('text', limit=80, required=True, label='Nombre'), 'color': F('color', label='Color'),
        'objetivo_pct': F('float', lo=0, hi=100, label='Objetivo (%)'),
        'descripcion': F('text', limit=2000, label='Descripción'),
        'orden': F('int', lo=-10000, hi=10000, default=0, label='Orden')},
        'deps': (('topicos', 'pilar_id'),)},
    'topicos': {'tabla': 'topicos', 'clave': True, 'orden': 'pilar_id, orden, nombre', 'etiqueta': 'Tópico', 'campos': {
        'pilar_id': F('ref', tabla='pilares', required=True, label='Pilar'),
        'nombre': F('text', limit=120, required=True, label='Nombre'),
        'orden': F('int', lo=-10000, hi=10000, default=0, label='Orden')},
        'deps': (('secciones', 'topico_id'),)},
    'secciones': {'tabla': 'secciones', 'clave': True, 'orden': 'topico_id, nombre', 'etiqueta': 'Sección',
        'entidad': 'seccion', 'campos': {
        'topico_id': F('ref', tabla='topicos', required=True, label='Tópico'),
        'nombre': F('text', limit=120, required=True, label='Nombre'),
        'descripcion': F('text', limit=4000, label='Descripción'),
        'periodicidad': F('text', limit=200, label='Periodicidad'),
        'formato_id': F('ref', tabla='formatos', label='Formato'),
        'plantilla_id': F('ref', tabla='plantillas', label='Plantilla'),
        'tiempo_produccion_min': F('int', lo=0, hi=100000, label='Tiempo de producción'),
        'interaccion_ideal': F('float', lo=0, hi=1e9, label='Interacción ideal'),
        'estado_prueba': F('enum', choices=ESTADOS_PRUEBA, default='no_empezada', label='Estado de prueba'),
        'estado_seccion': F('enum', choices=ESTADOS_SECCION, nullable=True, label='Estado de sección'),
        'en_piloto': F('bool', default=False, label='En piloto')},
        'deps': (('temas', 'seccion_id'), ('piezas', 'seccion_id'))},
    'temas': {'tabla': 'temas', 'clave': False, 'orden': 'seccion_id, id', 'etiqueta': 'Tema', 'campos': {
        'seccion_id': F('ref', tabla='secciones', required=True, label='Sección'),
        'titulo': F('text', limit=300, required=True, label='Título'),
        'explicacion': F('text', limit=2000, label='Explicación'),
        'usado': F('ref', tabla='piezas', label='Pieza que lo usa')},
        'deps': ()},
    'aliados': {'tabla': 'aliados', 'clave': True, 'orden': 'nombre', 'etiqueta': 'Aliado', 'entidad': 'aliado', 'campos': {
        'nombre': F('text', limit=120, required=True, label='Nombre'), 'tipo': F('text', limit=80, label='Tipo'),
        'contacto': F('text', limit=300, label='Contacto'), 'nota': F('text', limit=2000, label='Nota')},
        'deps': (('piezas', 'aliado_id'),)},
    'campanas': {'tabla': 'campanas', 'clave': True, 'orden': 'inicio, nombre', 'etiqueta': 'Campaña', 'entidad': 'campana', 'campos': {
        'nombre': F('text', limit=120, required=True, label='Nombre'), 'inicio': F('date', label='Inicio'),
        'fin': F('date', label='Fin'), 'objetivo': F('text', limit=2000, label='Objetivo')},
        'deps': (('piezas', 'campana_id'),)},
    'atributos': {'tabla': 'atributos', 'clave': True, 'orden': 'entidad, orden, nombre', 'etiqueta': 'Atributo', 'campos': {
        'entidad': F('enum', choices=tuple(ENTIDADES), required=True, label='Entidad'),
        'nombre': F('text', limit=80, required=True, label='Nombre'),
        'tipo': F('enum', choices=TIPOS_ATRIBUTO, required=True, label='Tipo'),
        'opciones': F('list', max_items=50, item_limit=80, label='Opciones'),
        'requerido': F('bool', default=False, label='Requerido'), 'filtrable': F('bool', default=False, label='Filtrable'),
        'columna': F('bool', default=False, label='Columna'),
        'orden': F('int', lo=-10000, hi=10000, default=0, label='Orden')},
        'deps': (('valores', 'atributo_id'),)},
}
JSON_COLS = {'config': {}, 'opciones': [], 'hashtags': [], 'media_ids': [], 'por_validar': [], 'cumplimiento': {}}
BOOL_COLS = ('archivado', 'en_piloto', 'requerido', 'filtrable', 'columna', 'interno')


def catalogo(nombre):
    spec = CATALOGOS.get(nombre)
    if not spec:
        raise HubError('Catálogo no encontrado.', 404)
    return spec


def fila(row):
    if row is None:
        return None
    d = dict(row)
    for k, default in JSON_COLS.items():
        if k in d:
            d[k] = loads(d[k], default)
    for k in BOOL_COLS:
        if k in d and d[k] is not None:
            d[k] = bool(d[k])
    return d


def _limpiar_campo(con, f, value):
    kind, label = f['kind'], f.get('label', 'Campo')
    if kind == 'text':
        return v_text(value, label, f['limit'], required=f.get('required', False))
    if kind == 'color':
        return v_color(value, label)
    if kind == 'url':
        return v_url(value, label)
    if kind == 'enum':
        if f.get('required') and value in (None, ''):
            raise HubError(f'{label} es obligatorio.')
        return v_enum(value, f['choices'], label, nullable=f.get('nullable', False))
    if kind == 'int':
        return v_int(value, label, f['lo'], f['hi'], nullable='default' not in f)
    if kind == 'float':
        return v_float(value, label, f['lo'], f['hi'])
    if kind == 'bool':
        return int(v_bool(value, label))
    if kind == 'date':
        return v_fecha(value, label)
    if kind == 'obj':
        return dumps(v_obj(value, label))
    if kind == 'list':
        return dumps(v_lista_texto(value, label, f['max_items'], f['item_limit']))
    if kind == 'ref':
        if value in (None, ''):
            if f.get('required'):
                raise HubError(f'{label} es obligatorio.')
            return None
        rid = v_int(value, label, 1, 2 ** 62)
        if not con.execute(f"select 1 from {f['tabla']} where id=?", (rid,)).fetchone():
            raise HubError(f'{label}: no existe.')
        return rid
    raise HubError('Campo no admitido.')  # pragma: no cover


def clave_unica(con, tabla, base, excluir=None):
    base = base[:72] or 'item'
    clave, n = base, 2
    while con.execute(f'select 1 from {tabla} where clave=? and id is not ?', (clave, excluir)).fetchone():
        clave, n = f'{base}-{n}', n + 1
    return clave


def guardar_catalogo(con, nombre, data, actor, item_id=None, usuarios=None, log=True):
    """Crea o actualiza un registro de catálogo. Devuelve ``(id, cambió)``."""
    spec = catalogo(nombre)
    tabla = spec['tabla']
    if not isinstance(data, dict):
        raise HubError('Se esperaba un objeto JSON.')
    actual = None
    if item_id is not None:
        actual = con.execute(f'select * from {tabla} where id=?', (item_id,)).fetchone()
        if not actual:
            raise HubError(f"{spec['etiqueta']} no encontrado.", 404)
    valores = {}
    for campo, f in spec['campos'].items():
        if campo in data:
            valores[campo] = _limpiar_campo(con, f, data[campo])
        elif actual is None:
            if f.get('required'):
                raise HubError(f"{f.get('label', campo)} es obligatorio.")
            if 'default' in f:
                d = f['default']
                valores[campo] = int(d) if isinstance(d, bool) else d
    if spec['clave']:
        if data.get('clave') not in (None, ''):
            valores['clave'] = v_clave(data['clave'])
            if con.execute(f'select 1 from {tabla} where clave=? and id is not ?', (valores['clave'], item_id)).fetchone():
                raise HubError('Ya existe un registro con esa clave.', 409)
        elif actual is None:
            valores['clave'] = clave_unica(con, tabla, slug(valores.get('nombre'))[:36 if nombre == 'atributos' else 72])
    if 'archivado' in data:
        valores['archivado'] = int(v_bool(data['archivado'], 'Archivado'))
    _validar_cruzado(con, nombre, valores, actual)
    atributos = data.get('atributos') if spec.get('entidad') else None
    if atributos is not None and not isinstance(atributos, dict):
        raise HubError('Atributos: se esperaba un objeto.')

    cambio = False
    ahora = now()
    if actual is None:
        valores.update(creado_at=ahora, actualizado_at=ahora)
        cols = list(valores)
        cur = con.execute(f"insert into {tabla}({','.join(cols)}) values({','.join('?' * len(cols))})",
                          [valores[c] for c in cols])
        item_id, cambio = cur.lastrowid, True
    else:
        diff = {k: v for k, v in valores.items() if actual[k] != v}
        if diff:
            diff['actualizado_at'] = ahora
            con.execute(f"update {tabla} set {','.join(k + '=?' for k in diff)} where id=?", [*diff.values(), item_id])
            cambio = True
    if spec.get('entidad'):
        if atributos:
            cambio = guardar_valores(con, spec['entidad'], item_id, atributos, usuarios) or cambio
        faltan = requeridos_faltantes(con, spec['entidad'], item_id)
        if faltan and (actual is None or atributos is not None):
            raise HubError('Faltan atributos requeridos: ' + ', '.join(faltan), faltantes=faltan)
    if cambio and log:
        accion = ('Alta' if actual is None else 'Edición') + f" de {spec['etiqueta'].lower()}"
        if 'archivado' in valores and actual is not None and actual['archivado'] != valores['archivado']:
            accion = ('Archivado' if valores['archivado'] else 'Recuperación') + f" de {spec['etiqueta'].lower()}"
        registrar(con, actor, accion, tabla, item_id)
    return item_id, cambio


def _validar_cruzado(con, nombre, v, actual):
    final = dict(actual) if actual is not None else {}
    final.update(v)
    if nombre == 'campanas' and final.get('inicio') and final.get('fin') and final['inicio'] > final['fin']:
        raise HubError('La campaña termina antes de empezar.')
    if nombre == 'atributos':
        opciones = loads(final.get('opciones'), [])
        if final.get('tipo') == 'lista' and not opciones:
            raise HubError('Un atributo de tipo lista necesita opciones.')
        if final.get('clave') and len(final['clave']) > 40:
            raise HubError('Clave del atributo: máximo 40 caracteres.')
        if actual is not None:
            usados = con.execute('select valor from valores where atributo_id=?', (actual['id'],)).fetchall()
            if usados and (final['tipo'] != actual['tipo'] or final['entidad'] != actual['entidad']):
                raise HubError('El atributo ya tiene valores: no se puede cambiar su tipo ni su entidad.', 409)
            if usados and final['tipo'] == 'lista':
                faltan = {loads(u[0], None) for u in usados} - set(opciones)
                if faltan:
                    raise HubError('Hay valores en uso que no están en las opciones: ' + ', '.join(map(str, faltan)), 409)


def validar_valor(attr, value, usuarios=None):
    tipo, label = attr['tipo'], attr['nombre']
    if tipo == 'texto':
        return v_text(value, label, 2000)
    if tipo == 'cerveza':
        return v_text(value, label, 200)
    if tipo == 'numero':
        return v_float(value, label, -1e12, 1e12, nullable=False)
    if tipo == 'lista':
        if value not in loads(attr['opciones'], []):
            raise HubError(f'{label}: elige una de las opciones.')
        return value
    if tipo == 'fecha':
        return v_fecha(value, label, nullable=False)
    if tipo == 'booleano':
        return v_bool(value, label)
    if tipo == 'usuario':
        uid = v_int(value, label, 1, 2 ** 62, nullable=False)
        if usuarios is not None and uid not in usuarios:
            raise HubError(f'{label}: usuario no encontrado.')
        return uid
    raise HubError('Tipo de atributo no admitido.')  # pragma: no cover


def guardar_valores(con, entidad, entidad_id, datos, usuarios=None):
    defs = {r['clave']: r for r in con.execute('select * from atributos where entidad=? and archivado=0', (entidad,))}
    cambio = False
    ahora = now()
    for clave, value in datos.items():
        attr = defs.get(clave)
        if attr is None:
            raise HubError(f'Atributo desconocido: {str(clave)[:40]}.')
        actual = con.execute('select valor from valores where atributo_id=? and entidad=? and entidad_id=?',
                             (attr['id'], entidad, entidad_id)).fetchone()
        if value is None or value == '':
            if actual:
                con.execute('delete from valores where atributo_id=? and entidad=? and entidad_id=?',
                            (attr['id'], entidad, entidad_id))
                cambio = True
            continue
        nuevo = dumps(validar_valor(attr, value, usuarios))
        if actual and actual[0] == nuevo:
            continue
        con.execute('insert into valores(atributo_id,entidad,entidad_id,valor,creado_at,actualizado_at) values(?,?,?,?,?,?) '
                    'on conflict(atributo_id,entidad,entidad_id) do update set valor=excluded.valor, actualizado_at=excluded.actualizado_at',
                    (attr['id'], entidad, entidad_id, nuevo, ahora, ahora))
        cambio = True
    return cambio


def requeridos_faltantes(con, entidad, entidad_id):
    rows = con.execute('''select a.clave from atributos a left join valores v on v.atributo_id=a.id and v.entidad=? and v.entidad_id=?
        where a.entidad=? and a.requerido=1 and a.archivado=0 and v.id is null order by a.orden, a.id''',
                       (entidad, entidad_id, entidad)).fetchall()
    return [r[0] for r in rows]


def valores_de(con, entidad, ids):
    out = {i: {} for i in ids}
    ids = list(ids)
    for i in range(0, len(ids), 500):
        parte = ids[i:i + 500]
        q = ','.join('?' * len(parte))
        for r in con.execute(f'''select v.entidad_id, a.clave, v.valor from valores v join atributos a on a.id=v.atributo_id
                where v.entidad=? and v.entidad_id in ({q}) and a.archivado=0''', [entidad, *parte]):
            out[r[0]][r[1]] = loads(r[2], None)
    return out


def dependencias(con, nombre, item_id):
    deps = {}
    for tabla, col in catalogo(nombre)['deps']:
        n = con.execute(f'select count(*) from {tabla} where {col}=?', (item_id,)).fetchone()[0]
        if n:
            deps[tabla] = n
    return deps


def borrar_catalogo(con, nombre, item_id, actor, definitivo=False):
    spec = catalogo(nombre)
    tabla = spec['tabla']
    row = con.execute(f'select * from {tabla} where id=?', (item_id,)).fetchone()
    if not row:
        raise HubError(f"{spec['etiqueta']} no encontrado.", 404)
    if not definitivo:
        con.execute(f'update {tabla} set archivado=1, actualizado_at=? where id=?', (now(), item_id))
        registrar(con, actor, f"Archivado de {spec['etiqueta'].lower()}", tabla, item_id)
        return {'ok': True, 'archivado': True}
    deps = dependencias(con, nombre, item_id)
    if deps:
        raise HubError('No se puede borrar: hay registros que dependen de este.', 409, dependencias=deps)
    if spec.get('entidad'):
        con.execute('delete from valores where entidad=? and entidad_id=?', (spec['entidad'], item_id))
    con.execute(f'delete from {tabla} where id=?', (item_id,))
    registrar(con, actor, f"Borrado definitivo de {spec['etiqueta'].lower()}", tabla, item_id)
    return {'ok': True, 'eliminado': True}


def listar_catalogo(con, nombre, archivados=False, filtros=None):
    spec = catalogo(nombre)
    tabla = spec['tabla']
    where, args = [], []
    if not archivados:
        where.append('archivado=0')
    for campo, valor in (filtros or {}).items():
        f = spec['campos'].get(campo)
        if f and f['kind'] == 'ref' and valor not in (None, ''):
            where.append(f'{campo}=?')
            args.append(v_int(valor, campo, 1, 2 ** 62))
    sql = f"select * from {tabla}" + (' where ' + ' and '.join(where) if where else '') + f" order by {spec['orden']}, id"
    items = [fila(r) for r in con.execute(sql, args)]
    if spec.get('entidad'):
        vals = valores_de(con, spec['entidad'], [i['id'] for i in items])
        for i in items:
            i['atributos'] = vals[i['id']]
    if nombre == 'secciones':
        ideales = {r[0]: r[1] for r in con.execute('select id, interaccion_ideal from formatos')}
        for i in items:
            i['interaccion_ideal_efectiva'] = i['interaccion_ideal'] if i['interaccion_ideal'] is not None else ideales.get(i['formato_id'])
    return items


# ---------------------------------------------------------------------------
# Piezas
# ---------------------------------------------------------------------------
class Contexto:
    """Dependencias externas de las validaciones: usuarios del CMS y MediaHub."""

    def __init__(self, actor='Sistema', usuarios=None, media_get=None):
        self.actor, self.usuarios, self.media_get = actor, usuarios, media_get


CAMPOS_PIEZA = {
    'titulo': F('text', limit=200, required=True, label='Título'),
    'seccion_id': F('ref', tabla='secciones', label='Sección'),
    'campana_id': F('ref', tabla='campanas', label='Campaña'),
    'aliado_id': F('ref', tabla='aliados', label='Aliado'),
    'plantilla_id': F('ref', tabla='plantillas', label='Plantilla'),
    'objetivo': F('text', limit=60, label='Objetivo'),
    'brief': F('text', limit=5000, label='Brief'),
    'copy_base': F('text', limit=10000, label='Texto base'),
}


def _limpiar_pieza(con, data, ctx, actual):
    v = {}
    for campo, f in CAMPOS_PIEZA.items():
        if campo in data:
            v[campo] = _limpiar_campo(con, f, data[campo])
        elif actual is None and f.get('required'):
            raise HubError(f"{f['label']} es obligatorio.")
    if 'fecha' in data:
        v['fecha'] = v_fecha(data['fecha'], 'Fecha')
    if 'hora' in data:
        v['hora'] = v_hora(data['hora'], 'Hora')
    if 'prueba' in data:
        v['prueba'] = v_enum(data['prueba'], PRUEBAS, 'Prueba', nullable=True)
    if 'responsable_id' in data:
        rid = v_int(data['responsable_id'], 'Responsable', 1, 2 ** 62)
        if rid is not None and ctx.usuarios is not None and rid not in ctx.usuarios:
            raise HubError('Responsable: usuario no encontrado.')
        v['responsable_id'] = rid
    if 'por_validar' in data:
        v['por_validar'] = dumps(v_lista_texto(data['por_validar'], 'Por validar', 30, 300))
    if 'cumplimiento' in data:
        v['cumplimiento'] = dumps(v_cumplimiento(data['cumplimiento']))
    if data.get('clave') not in (None, ''):
        v['clave'] = v_clave(data['clave'])
    return v


def _limpiar_variantes(con, lista, pieza_id, ctx):
    if not isinstance(lista, list) or len(lista) > 12:
        raise HubError('Variantes: se esperaba una lista de hasta 12.')
    existentes = {}
    if pieza_id is not None:
        existentes = {r['id']: r for r in con.execute('select * from variantes where pieza_id=? and archivado=0', (pieza_id,))}
    out = []
    for i, item in enumerate(lista, start=1):
        if not isinstance(item, dict):
            raise HubError('Variantes: cada variante debe ser un objeto.')
        etiqueta = f'Variante {i}'
        vid = item.get('id')
        actual = None
        if vid not in (None, ''):
            vid = v_int(vid, etiqueta, 1, 2 ** 62)
            actual = existentes.get(vid)
            if actual is None:
                raise HubError(f'{etiqueta}: no pertenece a esta pieza.')
        canal_id = _limpiar_campo(con, F('ref', tabla='canales', required=True, label=f'{etiqueta}: canal'), item.get('canal_id'))
        canal = con.execute('select clave, nombre from canales where id=?', (canal_id,)).fetchone()
        formato = None
        formato_id = _limpiar_campo(con, F('ref', tabla='formatos', label=f'{etiqueta}: formato'), item.get('formato_id'))
        if formato_id:
            formato = con.execute('select * from formatos where id=?', (formato_id,)).fetchone()
            if formato['canal_id'] != canal_id:
                raise HubError(f'{etiqueta}: el formato no pertenece al canal.')
        v = {
            'canal_id': canal_id, 'formato_id': formato_id,
            'titulo': v_text(item.get('titulo'), f'{etiqueta}: título', 300),
            'copy': v_text(item.get('copy'), f'{etiqueta}: texto', 70000),
            'hashtags': v_lista_texto(item.get('hashtags'), f'{etiqueta}: hashtags', 60, 100),
            'media_ids': v_media_ids(item.get('media_ids'), f'{etiqueta}: medios', ctx.media_get),
            'fecha': v_fecha(item.get('fecha'), f'{etiqueta}: fecha'),
            'hora': v_hora(item.get('hora'), f'{etiqueta}: hora'),
        }
        lim = limites_variante(canal['clave'], canal['nombre'], formato['max_caracteres'] if formato is not None else None)
        total = caracteres(v['copy'], v['hashtags'])
        if lim.get('copy') and total > lim['copy']:
            raise HubError(f"{canal['nombre']}: el texto tiene {total} caracteres y el máximo es {lim['copy']}.",
                           campo='copy', canal=canal['clave'], caracteres=total, maximo=lim['copy'])
        if lim.get('titulo') and len(v['titulo']) > lim['titulo']:
            raise HubError(f"{canal['nombre']}: el título tiene {len(v['titulo'])} caracteres y el máximo es {lim['titulo']}.",
                           campo='titulo', canal=canal['clave'], caracteres=len(v['titulo']), maximo=lim['titulo'])
        estado = item.get('estado_pub')
        if estado in (None, ''):
            v['estado_pub'] = actual['estado_pub'] if actual else 'pendiente'
        elif actual is not None and estado == actual['estado_pub']:
            v['estado_pub'] = estado
        else:
            v['estado_pub'] = v_enum(estado, ESTADOS_PUB_EDITABLES, f'{etiqueta}: estado de publicación')
        if actual is not None and actual['estado_pub'] == 'publicada' and v['estado_pub'] != 'publicada':
            raise HubError(f'{etiqueta}: ya está publicada.', 409)
        v['hashtags'] = dumps(v['hashtags'])
        v['media_ids'] = dumps(v['media_ids'])
        out.append((vid, v))
    ids = [vid for vid, _ in out if vid]
    if len(ids) != len(set(ids)):
        raise HubError('Variantes: hay una variante repetida.')
    quitar = [vid for vid in existentes if vid not in ids]
    for vid in quitar:
        if existentes[vid]['estado_pub'] == 'publicada' or con.execute('select 1 from metricas where variante_id=?', (vid,)).fetchone():
            raise HubError('No se puede quitar una variante publicada o con métricas.', 409)
    return out, quitar


def snapshot_pieza(con, pid):
    p = fila(con.execute('select * from piezas where id=?', (pid,)).fetchone())
    p['variantes'] = [fila(r) for r in con.execute('select * from variantes where pieza_id=? and archivado=0 order by id', (pid,))]
    p['atributos'] = valores_de(con, 'pieza', [pid])[pid]
    return p


def contenido_pieza(con, pid):
    """Instantánea sin campos volátiles, para detectar cambios reales."""
    p = snapshot_pieza(con, pid)
    for k in ('version', 'creado_at', 'actualizado_at'):
        p.pop(k, None)
    for v in p['variantes']:
        for k in ('creado_at', 'actualizado_at'):
            v.pop(k, None)
    return p


def guardar_version(con, pid, autor):
    p = snapshot_pieza(con, pid)
    con.execute('insert into versiones(pieza_id,version,datos,autor,creado_at) values(?,?,?,?,?)',
                (pid, p['version'], dumps(p), str(autor)[:120], now()))


def guardar_pieza(con, data, ctx, pieza_id=None, version=None, log=True):
    """Crea (``pieza_id=None``) o actualiza una pieza con bloqueo optimista. Devuelve el id."""
    if not isinstance(data, dict):
        raise HubError('Se esperaba un objeto JSON.')
    actual = None
    if pieza_id is not None:
        actual = con.execute('select * from piezas where id=?', (pieza_id,)).fetchone()
        if not actual:
            raise HubError('Pieza no encontrada.', 404)
        if version is None:
            raise HubError('Falta la versión de la pieza.', 400)
        if version != actual['version']:
            raise HubError('Otra persona guardó cambios en esta pieza. Recarga antes de continuar.', 409,
                           version=actual['version'])
    v = _limpiar_pieza(con, data, ctx, actual)
    if 'clave' in v and con.execute('select 1 from piezas where clave=? and id is not ?', (v['clave'], pieza_id)).fetchone():
        raise HubError('Ya existe una pieza con esa clave.', 409)
    variantes = quitar = None
    if 'variantes' in data:
        variantes, quitar = _limpiar_variantes(con, data['variantes'], pieza_id, ctx)
    atributos = data.get('atributos')
    if atributos is not None and not isinstance(atributos, dict):
        raise HubError('Atributos: se esperaba un objeto.')
    ahora = now()
    if actual is None:
        estado = data.get('estado') or 'borrador'
        v['estado'] = v_enum(estado, ('idea', 'borrador'), 'Estado inicial')
        if 'clave' not in v:
            v['clave'] = clave_unica(con, 'piezas', slug(f"{v.get('fecha') or ''} {v['titulo']}"))
        v.update(version=1, creado_at=ahora, actualizado_at=ahora)
        cols = list(v)
        pieza_id = con.execute(f"insert into piezas({','.join(cols)}) values({','.join('?' * len(cols))})",
                               [v[c] for c in cols]).lastrowid
    else:
        v.update(version=actual['version'] + 1, actualizado_at=ahora)
        con.execute(f"update piezas set {','.join(k + '=?' for k in v)} where id=?", [*v.values(), pieza_id])
    if variantes is not None:
        for vid in quitar:
            con.execute('delete from variantes where id=?', (vid,))
        for vid, campos in variantes:
            if vid:
                campos['actualizado_at'] = ahora
                con.execute(f"update variantes set {','.join(k + '=?' for k in campos)} where id=?", [*campos.values(), vid])
            else:
                campos.update(pieza_id=pieza_id, creado_at=ahora, actualizado_at=ahora)
                cols = list(campos)
                con.execute(f"insert into variantes({','.join(cols)}) values({','.join('?' * len(cols))})",
                            [campos[c] for c in cols])
    if atributos:
        guardar_valores(con, 'pieza', pieza_id, atributos, ctx.usuarios)
    guardar_version(con, pieza_id, ctx.actor)
    if log:
        registrar(con, ctx.actor, 'Alta de pieza' if actual is None else 'Edición de pieza', 'piezas', pieza_id)
    return pieza_id


SQL_PIEZAS = '''select p.*, s.nombre seccion, s.clave seccion_clave, t.id topico_id, t.nombre topico,
  pi.id pilar_id, pi.clave pilar_clave, pi.nombre pilar, pi.color pilar_color,
  c.nombre campana, c.clave campana_clave, a.nombre aliado, a.clave aliado_clave,
  coalesce(p.plantilla_id, s.plantilla_id) plantilla_efectiva_id, pl.nombre plantilla, pl.clave plantilla_clave
  from piezas p left join secciones s on s.id=p.seccion_id left join topicos t on t.id=s.topico_id
  left join pilares pi on pi.id=t.pilar_id left join campanas c on c.id=p.campana_id
  left join aliados a on a.id=p.aliado_id left join plantillas pl on pl.id=coalesce(p.plantilla_id, s.plantilla_id)'''

SQL_VARIANTES = '''select v.*, k.clave canal_clave, k.nombre canal, k.color canal_color, k.icono canal_icono,
  f.clave formato_clave, f.nombre formato, f.tipo formato_tipo, f.proporcion, f.max_caracteres, f.max_laminas,
  f.max_segundos from variantes v join canales k on k.id=v.canal_id left join formatos f on f.id=v.formato_id'''


def _variante_publica(r):
    d = fila(r)
    lim = limites_variante(d['canal_clave'], d['canal'], d.get('max_caracteres'))
    d['caracteres'] = caracteres(d['copy'], d['hashtags'])
    d['limites'] = lim
    avisos = []
    if d.get('max_laminas') and len(d['media_ids']) > d['max_laminas']:
        avisos.append(f"El formato admite {d['max_laminas']} láminas y hay {len(d['media_ids'])}.")
    if lim.get('copy') and d['caracteres'] > lim['copy'] * 0.9:
        avisos.append(f"El texto está cerca del límite ({d['caracteres']}/{lim['copy']}).")
    d['avisos'] = avisos
    return d


def serializar_piezas(con, rows, usuarios_map=None):
    items = [fila(r) for r in rows]
    ids = [p['id'] for p in items]
    variantes = {i: [] for i in ids}
    for i in range(0, len(ids), 500):
        parte = ids[i:i + 500]
        q = ','.join('?' * len(parte))
        for r in con.execute(SQL_VARIANTES + f' where v.pieza_id in ({q}) and v.archivado=0 order by v.id', parte):
            variantes[r['pieza_id']].append(_variante_publica(r))
    vals = valores_de(con, 'pieza', ids)
    for p in items:
        p['variantes'] = variantes[p['id']]
        p['atributos'] = vals[p['id']]
        faltan = faltantes_checklist(p['cumplimiento'])
        p['cumplimiento_ok'] = not faltan
        p['cumplimiento_faltantes'] = faltan
        p['responsable'] = (usuarios_map or {}).get(p['responsable_id'], {}).get('name') if p['responsable_id'] else None
        p['transiciones'] = list(TRANSICIONES.get(p['estado'], ()))
    return items


def filtrar_piezas(con, args, usuarios_map=None, limite=2000):
    where, params = [], []
    if args.get('archivados') not in ('1', 'true'):
        where.append('p.archivado=0')
    if args.get('desde'):
        where.append('p.fecha>=?'); params.append(v_fecha(args['desde'], 'Desde'))
    if args.get('hasta'):
        where.append('p.fecha<=?'); params.append(v_fecha(args['hasta'], 'Hasta'))
    if args.get('estado'):
        where.append('p.estado=?'); params.append(v_enum(args['estado'], ESTADOS, 'Estado'))
    for campo, alias in (('seccion', 's'), ('pilar', 'pi'), ('campana', 'c'), ('aliado', 'a')):
        valor = args.get(campo)
        if valor:
            valor = str(valor)[:80]
            if valor.isdigit():
                where.append(f'{alias}.id=?'); params.append(int(valor))
            else:
                where.append(f'{alias}.clave=?'); params.append(valor)
    if args.get('responsable'):
        where.append('p.responsable_id=?'); params.append(v_int(args['responsable'], 'Responsable', 1, 2 ** 62))
    if args.get('canal'):
        valor = str(args['canal'])[:80]
        where.append('exists(select 1 from variantes v join canales k on k.id=v.canal_id where v.pieza_id=p.id '
                     'and v.archivado=0 and ' + ('k.id=?)' if valor.isdigit() else 'k.clave=?)'))
        params.append(int(valor) if valor.isdigit() else valor)
    if args.get('q'):
        q = str(args['q'])[:120].replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        where.append("(p.titulo like ? escape '\\' or p.copy_base like ? escape '\\' or p.clave like ? escape '\\')")
        params += [f'%{q}%'] * 3
    sql = SQL_PIEZAS + (' where ' + ' and '.join(where) if where else '') + \
        ' order by p.fecha is null, p.fecha, p.hora is null, p.hora, p.id'
    rows = con.execute(sql, params).fetchall()
    filtros_attr = {k[5:]: v for k, v in args.items() if k.startswith('attr.') and v not in (None, '')}
    if filtros_attr:
        defs = {r['clave']: r for r in con.execute("select * from atributos where entidad='pieza' and archivado=0")}
        vals = valores_de(con, 'pieza', [r['id'] for r in rows])
        for clave, esperado in filtros_attr.items():
            attr = defs.get(clave)
            if attr is None:
                raise HubError(f'Atributo desconocido: {clave[:40]}.')
            rows = [r for r in rows if _coincide(attr, vals[r['id']].get(clave), str(esperado))]
    total = len(rows)
    return serializar_piezas(con, rows[:limite], usuarios_map), total


def _coincide(attr, valor, esperado):
    if valor is None:
        return esperado in ('', 'null', 'vacio')
    if attr['tipo'] == 'booleano':
        return bool(valor) == (esperado.lower() in ('1', 'true', 'si', 'sí'))
    if attr['tipo'] == 'numero':
        try:
            return float(valor) == float(esperado)
        except ValueError:
            return False
    if attr['tipo'] == 'usuario':
        return str(valor) == esperado
    return str(valor).casefold() == esperado.casefold()


def obtener_pieza(con, pid, usuarios_map=None, incluir_archivada=True):
    row = con.execute(SQL_PIEZAS + ' where p.id=?', (pid,)).fetchone()
    if not row or (row['archivado'] and not incluir_archivada):
        raise HubError('Pieza no encontrada.', 404)
    return serializar_piezas(con, [row], usuarios_map)[0]


def detalle_pieza(con, pid, usuarios_map=None):
    p = obtener_pieza(con, pid, usuarios_map)
    p['comentarios'] = [fila(r) for r in con.execute(
        'select id,autor,texto,interno,creado_at from comentarios where pieza_id=? order by id', (pid,))]
    p['versiones'] = [dict(r) for r in con.execute(
        'select version,autor,creado_at from versiones where pieza_id=? order by version desc, id desc limit 100', (pid,))]
    ahora = int(time.time())
    p['aprobaciones'] = [{
        'id': r['id'], 'expira': datetime.fromtimestamp(r['expira'], timezone.utc).isoformat(timespec='seconds'),
        'vigente': r['decision'] is None and r['expira'] > ahora, 'decision': r['decision'], 'motivo': r['motivo'],
        'quien': r['quien'], 'decidido_at': r['decidido_at'], 'creado_por': r['creado_por'], 'creado_at': r['creado_at'],
    } for r in con.execute('select * from aprobaciones where pieza_id=? order by id desc', (pid,))]
    p['avisos_laboratorio'] = []
    if p['seccion_id']:
        for s in laboratorio(con, [p['seccion_id']]):
            p['avisos_laboratorio'] = [a for a in s['avisos'] if a['pieza_id'] == pid]
    return p


def mover_pieza(con, pid, fecha, hora, actor, version=None):
    p = con.execute('select * from piezas where id=? and archivado=0', (pid,)).fetchone()
    if not p:
        raise HubError('Pieza no encontrada.', 404)
    if version is not None and version != p['version']:
        raise HubError('Otra persona guardó cambios en esta pieza. Recarga antes de continuar.', 409, version=p['version'])
    if p['estado'] == 'publicada':
        raise HubError('Una pieza publicada no se puede mover.', 409)
    fecha = v_fecha(fecha, 'Fecha', nullable=False)
    hora = v_hora(hora, 'Hora') if hora is not None else p['hora']
    ahora = now()
    for v in con.execute('select id, fecha, hora from variantes where pieza_id=? and estado_pub!=?', (pid, 'publicada')).fetchall():
        if v['fecha'] == p['fecha'] and v['fecha'] is not None:
            nueva_hora = hora if v['hora'] == p['hora'] else v['hora']
            con.execute('update variantes set fecha=?, hora=?, actualizado_at=? where id=?', (fecha, nueva_hora, ahora, v['id']))
    con.execute('update piezas set fecha=?, hora=?, version=version+1, actualizado_at=? where id=?', (fecha, hora, ahora, pid))
    guardar_version(con, pid, actor)
    registrar(con, actor, f"Pieza movida de {p['fecha'] or 'sin fecha'} a {fecha}", 'piezas', pid)


def duplicar_pieza(con, pid, actor):
    p = con.execute('select * from piezas where id=?', (pid,)).fetchone()
    if not p:
        raise HubError('Pieza no encontrada.', 404)
    ahora = now()
    clave = clave_unica(con, 'piezas', (p['clave'][:66] + '-copia'))
    nueva = con.execute('''insert into piezas(clave,titulo,seccion_id,campana_id,aliado_id,plantilla_id,responsable_id,
        fecha,hora,estado,prueba,objetivo,brief,copy_base,por_validar,cumplimiento,version,creado_at,actualizado_at)
        values(?,?,?,?,?,?,?,?,?,'borrador',?,?,?,?,?,'{}',1,?,?)''',
        (clave, (p['titulo'] + ' (copia)')[:200], p['seccion_id'], p['campana_id'], p['aliado_id'], p['plantilla_id'],
         p['responsable_id'], p['fecha'], p['hora'], p['prueba'], p['objetivo'], p['brief'], p['copy_base'],
         p['por_validar'], ahora, ahora)).lastrowid
    for v in con.execute('select * from variantes where pieza_id=? and archivado=0 order by id', (pid,)).fetchall():
        con.execute('''insert into variantes(pieza_id,canal_id,formato_id,titulo,copy,hashtags,media_ids,fecha,hora,
            estado_pub,creado_at,actualizado_at) values(?,?,?,?,?,?,?,?,?,'pendiente',?,?)''',
                    (nueva, v['canal_id'], v['formato_id'], v['titulo'], v['copy'], v['hashtags'], v['media_ids'],
                     v['fecha'], v['hora'], ahora, ahora))
    for r in con.execute("select atributo_id, valor from valores where entidad='pieza' and entidad_id=?", (pid,)).fetchall():
        con.execute("insert into valores(atributo_id,entidad,entidad_id,valor,creado_at,actualizado_at) values(?,'pieza',?,?,?,?)",
                    (r[0], nueva, r[1], ahora, ahora))
    guardar_version(con, nueva, actor)
    registrar(con, actor, f"Pieza duplicada desde {p['clave']}", 'piezas', nueva)
    return nueva


def borrar_pieza(con, pid, actor, definitivo=False):
    p = con.execute('select * from piezas where id=?', (pid,)).fetchone()
    if not p:
        raise HubError('Pieza no encontrada.', 404)
    if not definitivo:
        con.execute('update piezas set archivado=1, actualizado_at=? where id=?', (now(), pid))
        _anular_enlaces(con, pid)
        registrar(con, actor, 'Pieza archivada', 'piezas', pid)
        return {'ok': True, 'archivado': True}
    publicadas = con.execute("select count(*) from variantes where pieza_id=? and estado_pub='publicada'", (pid,)).fetchone()[0]
    con_metricas = con.execute('select count(*) from metricas m join variantes v on v.id=m.variante_id where v.pieza_id=?',
                               (pid,)).fetchone()[0]
    if publicadas or con_metricas:
        raise HubError('No se puede borrar: la pieza tiene publicaciones o métricas. Archívala.', 409,
                       dependencias={'variantes_publicadas': publicadas, 'metricas': con_metricas})
    con.execute("delete from valores where entidad='pieza' and entidad_id=?", (pid,))
    con.execute('delete from piezas where id=?', (pid,))
    registrar(con, actor, f"Pieza borrada definitivamente ({p['clave']})", 'piezas', pid)
    return {'ok': True, 'eliminado': True}


def _anular_enlaces(con, pid):
    con.execute('update aprobaciones set expira=0 where pieza_id=? and decision is null', (pid,))


def cambiar_estado(con, pid, nuevo, actor, motivo='', puede_aprobar=False, por_enlace=False):
    p = con.execute('select * from piezas where id=?', (pid,)).fetchone()
    if not p or p['archivado']:
        raise HubError('Pieza no encontrada.', 404)
    motivo = v_text(motivo, 'Motivo', 1000)
    if nuevo == 'archivada':
        return borrar_pieza(con, pid, actor)
    v_enum(nuevo, ESTADOS, 'Estado')
    actual = p['estado']
    if nuevo not in TRANSICIONES.get(actual, ()):
        raise HubError(f'Transición no válida: {actual} → {nuevo}.', 409, permitidas=list(TRANSICIONES.get(actual, ())))
    if nuevo in ('aprobada', 'observada') and not (puede_aprobar or por_enlace):
        raise HubError('Solo el dueño o una persona con rol de aprobador puede aprobar u observar.', 403)
    if nuevo in ('revision', 'aprobada'):
        faltan = faltantes_checklist(loads(p['cumplimiento'], {}))
        if faltan:
            raise HubError('Completa el checklist de cumplimiento antes de continuar: ' + ', '.join(faltan), 400,
                           faltantes=faltan)
        req = requeridos_faltantes(con, 'pieza', pid)
        if req:
            raise HubError('Faltan atributos requeridos: ' + ', '.join(req), 400, faltantes=req)
    if nuevo == 'observada' and not motivo:
        raise HubError('Explica qué cambios se necesitan.')
    if nuevo == 'publicada':
        estados = [r[0] for r in con.execute('select estado_pub from variantes where pieza_id=? and archivado=0', (pid,))]
        if not estados or 'publicada' not in estados or any(e not in ('publicada', 'omitida') for e in estados):
            raise HubError('Todas las variantes deben estar publicadas u omitidas.', 409)
    ahora = now()
    con.execute('update piezas set estado=?, actualizado_at=? where id=?', (nuevo, ahora, pid))
    if nuevo == 'programada':
        con.execute("update variantes set estado_pub='programada', actualizado_at=? where pieza_id=? and estado_pub in ('pendiente','error')",
                    (ahora, pid))
    if actual == 'revision':
        _anular_enlaces(con, pid)
    if motivo:
        etiqueta = {'aprobada': 'Aprobada', 'observada': 'Cambios solicitados', 'error': 'Error'}.get(nuevo, nuevo.capitalize())
        con.execute('insert into comentarios(pieza_id,autor,texto,interno,creado_at) values(?,?,?,0,?)',
                    (pid, str(actor)[:120], f'{etiqueta}: {motivo}', ahora))
    registrar(con, actor, f'Estado de pieza: {actual} → {nuevo}', 'piezas', pid)
    return {'ok': True, 'estado': nuevo, 'anterior': actual}


def marcar_publicada(con, vid, url, publicado_at, actor, id_externo=''):
    v = con.execute('select v.*, p.estado, p.archivado parchivado from variantes v join piezas p on p.id=v.pieza_id where v.id=?',
                    (vid,)).fetchone()
    if not v or v['archivado'] or v['parchivado']:
        raise HubError('Variante no encontrada.', 404)
    if v['estado'] not in ('aprobada', 'programada', 'error', 'publicada'):
        raise HubError('Solo se publican piezas aprobadas.', 409)
    url = v_url(url, 'Enlace publicado', required=True)
    if publicado_at in (None, ''):
        publicado_at = now()
    else:
        publicado_at = v_text(publicado_at, 'Fecha de publicación', 40)
        try:
            datetime.fromisoformat(publicado_at.replace('Z', '+00:00'))
        except ValueError:
            raise HubError('Fecha de publicación: usa formato ISO 8601.') from None
    ahora = now()
    con.execute("update variantes set estado_pub='publicada', url_publicada=?, publicado_at=?, id_externo=?, error='', "
                'actualizado_at=? where id=?', (url, publicado_at, v_text(id_externo, 'Id externo', 200), ahora, vid))
    registrar(con, actor, 'Variante marcada como publicada', 'variantes', vid)
    pid = v['pieza_id']
    estados = [r[0] for r in con.execute('select estado_pub from variantes where pieza_id=? and archivado=0', (pid,))]
    estado = v['estado']
    if all(e in ('publicada', 'omitida') for e in estados) and estado != 'publicada':
        if estado == 'aprobada':
            cambiar_estado(con, pid, 'programada', actor)
        cambiar_estado(con, pid, 'publicada', actor)
        estado = 'publicada'
    return estado


METRICAS = ('likes', 'comentarios', 'compartidos', 'guardados', 'envios', 'alcance', 'vistas')


def guardar_metrica(con, vid, data, actor):
    v = con.execute('select * from variantes where id=?', (vid,)).fetchone()
    if not v or v['archivado']:
        raise HubError('Variante no encontrada.', 404)
    if v['estado_pub'] != 'publicada':
        raise HubError('Primero marca la variante como publicada.', 409)
    valores = {k: v_int(data.get(k), k.capitalize(), 0, 10 ** 10) for k in METRICAS}
    if all(x is None for x in valores.values()):
        raise HubError('Captura al menos una métrica.')
    medido_at = data.get('medido_at') or now()
    medido_at = v_text(medido_at, 'Momento de medición', 40)
    try:
        medido = datetime.fromisoformat(medido_at.replace('Z', '+00:00'))
    except ValueError:
        raise HubError('Momento de medición: usa formato ISO 8601.') from None
    horas = v_float(data.get('horas_desde_pub'), 'Horas desde la publicación', 0, 100000)
    if horas is None and v['publicado_at']:
        try:
            pub = datetime.fromisoformat(v['publicado_at'].replace('Z', '+00:00'))
            if (pub.tzinfo is None) == (medido.tzinfo is None):
                horas = round(max(0.0, (medido - pub).total_seconds() / 3600), 2)
        except ValueError:
            horas = None
    fuente = v_enum(data.get('fuente') or 'manual', ('manual', 'api'), 'Fuente')
    mid = con.execute(f"insert into metricas(variante_id,medido_at,horas_desde_pub,{','.join(METRICAS)},fuente,creado_at) "
                      f"values(?,?,?,{','.join('?' * len(METRICAS))},?,?)",
                      (vid, medido_at, horas, *valores.values(), fuente, now())).lastrowid
    registrar(con, actor, 'Métricas capturadas', 'variantes', vid)
    sid = con.execute('select seccion_id from piezas where id=?', (v['pieza_id'],)).fetchone()[0]
    seccion = recalcular_seccion(con, sid, actor) if sid else None
    return mid, seccion


# ---------------------------------------------------------------------------
# Laboratorio (método R1–R3)
# ---------------------------------------------------------------------------
def interaccion(m):
    return sum((m[k] or 0) for k in ('likes', 'comentarios', 'compartidos', 'guardados', 'envios'))


def resultado(pct):
    if pct is None:
        return None
    if pct > 120:
        return 'supero'
    if pct >= 100:
        return 'cumplio'
    return 'no_cumplio'


def _horas(m, publicado_at):
    if m['horas_desde_pub'] is not None:
        return m['horas_desde_pub']
    try:
        a = datetime.fromisoformat(m['medido_at'].replace('Z', '+00:00'))
        b = datetime.fromisoformat((publicado_at or '').replace('Z', '+00:00'))
        return (a - b).total_seconds() / 3600
    except (ValueError, TypeError, AttributeError):
        return None


def estado_prueba_calculado(pruebas):
    res = [m['resultado'] for m in pruebas.values() if m and m['resultado']]
    ok = sum(r in ('cumplio', 'supero') for r in res)
    malas = sum(r == 'no_cumplio' for r in res)
    if ok >= 2:
        return 'vigente'
    if malas >= 2:
        return 'no_funciono'
    if res or any(m and m['estado'] in ('programada', 'publicada', 'error') for m in pruebas.values()):
        return 'empezada'
    return 'no_empezada'


def estado_seccion_calculado(ultimos):
    medidos = [m for m in ultimos if m['pct'] is not None]
    n = len(medidos)
    if not n:
        return None
    if sum(m['resultado'] == 'supero' for m in medidos) > n / 2:
        return 'buena'
    if sum(m['resultado'] in ('cumplio', 'supero') for m in medidos) > n / 2:
        return 'normal'
    media = sum(m['pct'] for m in medidos) / n
    if media < 60:
        return 'dejo_de_funcionar'
    if media < 100:
        return 'saturada'
    return 'normal'


def laboratorio(con, seccion_ids=None):
    sql = '''select s.*, t.nombre topico, pi.id pilar_id, pi.clave pilar_clave, pi.nombre pilar, pi.color pilar_color,
        f.clave formato_clave, f.nombre formato, f.canal_id formato_canal_id, f.interaccion_ideal formato_ideal,
        pl.nombre plantilla, pl.clave plantilla_clave
        from secciones s left join topicos t on t.id=s.topico_id left join pilares pi on pi.id=t.pilar_id
        left join formatos f on f.id=s.formato_id left join plantillas pl on pl.id=s.plantilla_id where s.archivado=0'''
    args = []
    if seccion_ids:
        sql += f" and s.id in ({','.join('?' * len(seccion_ids))})"
        args = list(seccion_ids)
    secciones = con.execute(sql + ' order by pi.orden, t.orden, s.nombre, s.id', args).fetchall()
    if not secciones:
        return []
    sids = [s['id'] for s in secciones]
    q = ','.join('?' * len(sids))
    piezas = con.execute(f'''select id, clave, titulo, seccion_id, fecha, hora, prueba, estado, plantilla_id from piezas
        where archivado=0 and seccion_id in ({q}) order by fecha, hora, id''', sids).fetchall()
    pids = [p['id'] for p in piezas]
    variantes, metricas = {}, {}
    formatos = {r['id']: r for r in con.execute('select id, clave, nombre, canal_id, interaccion_ideal from formatos')}
    canales = {r['id']: r['clave'] for r in con.execute('select id, clave from canales')}
    for i in range(0, len(pids), 500):
        parte = pids[i:i + 500]
        qq = ','.join('?' * len(parte))
        for v in con.execute(f'select * from variantes where archivado=0 and pieza_id in ({qq}) order by id', parte):
            variantes.setdefault(v['pieza_id'], []).append(v)
        for m in con.execute(f'select m.* from metricas m join variantes v on v.id=m.variante_id where v.pieza_id in ({qq}) order by m.id', parte):
            metricas.setdefault(m['variante_id'], []).append(m)

    salida = []
    for s in secciones:
        ideal_seccion = s['interaccion_ideal'] if s['interaccion_ideal'] is not None else s['formato_ideal']
        medidas = []
        for p in (x for x in piezas if x['seccion_id'] == s['id']):
            vs = variantes.get(p['id'], [])
            principal = (next((v for v in vs if s['formato_id'] and v['formato_id'] == s['formato_id']), None)
                         or next((v for v in vs if s['formato_canal_id'] and v['canal_id'] == s['formato_canal_id']), None)
                         or next((v for v in vs if metricas.get(v['id'])), None)
                         or (vs[0] if vs else None))
            ideal, inter, pct, formato_id, medida_at, horas = ideal_seccion, None, None, None, None, None
            if principal is not None:
                formato_id = principal['formato_id'] or s['formato_id']
                if principal['formato_id'] and principal['formato_id'] != s['formato_id']:
                    f = formatos.get(principal['formato_id'])
                    if f is not None and f['interaccion_ideal'] is not None:
                        ideal = f['interaccion_ideal']
                ms = metricas.get(principal['id'], [])
                if ms:
                    elegida = min(ms, key=lambda m: (abs(h - 24) if (h := _horas(m, principal['publicado_at'])) is not None else 1e9, -m['id']))
                    inter = interaccion(elegida)
                    medida_at, horas = elegida['medido_at'], _horas(elegida, principal['publicado_at'])
                    if ideal:
                        pct = round(inter / ideal * 100, 1)
            hora = (principal['hora'] if principal is not None and principal['hora'] else None) or p['hora']
            f = formatos.get(formato_id) if formato_id else None
            medidas.append({
                'pieza_id': p['id'], 'clave': p['clave'], 'titulo': p['titulo'], 'fecha': p['fecha'], 'hora': hora,
                'prueba': p['prueba'], 'estado': p['estado'],
                'variante_id': principal['id'] if principal is not None else None,
                'canal_clave': canales.get(principal['canal_id']) if principal is not None else None,
                'formato_id': formato_id, 'formato_clave': f['clave'] if f is not None else None,
                'plantilla_id': p['plantilla_id'] or s['plantilla_id'],
                'interaccion': inter, 'ideal': ideal, 'pct': pct, 'resultado': resultado(pct),
                'medido_at': medida_at, 'horas_desde_pub': round(horas, 2) if horas is not None else None,
            })
        pruebas = {}
        for r in PRUEBAS:
            candidatas = [m for m in medidas if m['prueba'] == r]
            pruebas[r] = candidatas[-1] if candidatas else None
        calc = estado_prueba_calculado(pruebas)
        efectivo = calc if calc in ('vigente', 'no_funciono') else s['estado_prueba']
        if calc == 'empezada' and s['estado_prueba'] == 'no_empezada':
            efectivo = 'empezada'
        ultimos = sorted((m for m in medidas if m['pct'] is not None), key=lambda m: (m['fecha'] or '', m['pieza_id']))[-5:]
        sec_calc = estado_seccion_calculado(ultimos) if efectivo == 'vigente' else None
        avisos = []
        for a, b in (('R1', 'R2'), ('R2', 'R3')):
            pa, pb = pruebas[a], pruebas[b]
            if pa and pb and pa['resultado'] == 'no_cumplio' and \
                    (pa['hora'], pa['plantilla_id'], pa['formato_id']) == (pb['hora'], pb['plantilla_id'], pb['formato_id']):
                avisos.append({'tipo': 'misma_combinacion', 'prueba': b, 'pieza_id': pb['pieza_id'],
                               'mensaje': f'{a} no cumplió y {b} repite la misma hora, plantilla y formato: cambia al menos uno.'})
        media = round(sum(m['pct'] for m in ultimos) / len(ultimos), 1) if ultimos else None
        salida.append({
            'id': s['id'], 'clave': s['clave'], 'nombre': s['nombre'], 'periodicidad': s['periodicidad'],
            'pilar_id': s['pilar_id'], 'pilar_clave': s['pilar_clave'], 'pilar': s['pilar'], 'pilar_color': s['pilar_color'],
            'topico_id': s['topico_id'], 'topico': s['topico'],
            'formato_id': s['formato_id'], 'formato_clave': s['formato_clave'], 'formato': s['formato'],
            'plantilla_id': s['plantilla_id'], 'plantilla_clave': s['plantilla_clave'], 'plantilla': s['plantilla'],
            'en_piloto': bool(s['en_piloto']), 'interaccion_ideal': ideal_seccion,
            'estado_prueba': s['estado_prueba'], 'estado_prueba_calculado': calc,
            'estado_seccion': s['estado_seccion'], 'estado_seccion_calculado': sec_calc,
            'pruebas': pruebas, 'ultimos': ultimos, 'media_pct': media, 'avisos': avisos,
            'piezas': len(medidas),
        })
    return salida


def recalcular_seccion(con, sid, actor='Sistema'):
    lab = laboratorio(con, [sid])
    if not lab:
        return None
    s = lab[0]
    nuevo = s['estado_prueba']
    if s['estado_prueba_calculado'] in ('vigente', 'no_funciono'):
        nuevo = s['estado_prueba_calculado']
    elif s['estado_prueba_calculado'] == 'empezada' and nuevo == 'no_empezada':
        nuevo = 'empezada'
    sec = s['estado_seccion']
    if nuevo == 'vigente':
        sec = s['estado_seccion_calculado'] or sec
    elif nuevo == 'no_funciono':
        sec = None
    if (nuevo, sec) != (s['estado_prueba'], s['estado_seccion']):
        con.execute('update secciones set estado_prueba=?, estado_seccion=?, actualizado_at=? where id=?', (nuevo, sec, now(), sid))
        registrar(con, actor, f"Laboratorio: {s['nombre']} → {nuevo}" + (f' / {sec}' if sec else ''), 'secciones', sid)
        s = laboratorio(con, [sid])[0]
    return s


# ---------------------------------------------------------------------------
# Resumen y presentación
# ---------------------------------------------------------------------------
def _lunes(d):
    return d - timedelta(days=d.weekday())


def _fila_corta(r):
    return {'id': r['id'], 'clave': r['clave'], 'titulo': r['titulo'], 'fecha': r['fecha'], 'hora': r['hora'],
            'estado': r['estado'], 'prueba': r['prueba'], 'seccion': r['seccion'], 'pilar': r['pilar'],
            'pilar_color': r['pilar_color']}


def _meta_kpi(kpis, canal_clave):
    for k in kpis or []:
        if isinstance(k, dict) and k.get('clave') == f'posts_{canal_clave}_semana':
            m = re.search(r'\d+(?:[.,]\d+)?', str(k.get('meta', '')))
            if m:
                return float(m.group(0).replace(',', '.'))
    return None


def resumen(con, desde=None, hasta=None):
    zona = ajuste(con, 'zona', ZONA)
    hoy_ = hoy(zona)
    d = date.fromisoformat(v_fecha(desde, 'Desde')) if desde else _lunes(hoy_)
    h = date.fromisoformat(v_fecha(hasta, 'Hasta')) if hasta else d + timedelta(days=6)
    if h < d:
        raise HubError('El rango de fechas está invertido.')
    if (h - d).days > 400:
        raise HubError('El rango máximo es de 400 días.')
    rango = (d.isoformat(), h.isoformat())
    rows = con.execute(SQL_PIEZAS + ' where p.archivado=0 and p.fecha between ? and ?', rango).fetchall()
    conteos = {e: 0 for e in ESTADOS}
    for r in rows:
        conteos[r['estado']] += 1
    pendientes = [_fila_corta(r) for r in con.execute(
        SQL_PIEZAS + " where p.archivado=0 and p.estado='revision' order by p.fecha is null, p.fecha, p.hora limit 50")]
    proximas = [_fila_corta(r) for r in con.execute(
        SQL_PIEZAS + " where p.archivado=0 and p.fecha>=? and p.estado not in ('publicada','idea') "
        'order by p.fecha, p.hora is null, p.hora, p.id limit 10', (hoy_.isoformat(),))]
    errores = [_fila_corta(r) for r in con.execute(
        SQL_PIEZAS + " where p.archivado=0 and (p.estado='error' or exists(select 1 from variantes v where v.pieza_id=p.id "
        "and v.archivado=0 and v.estado_pub='error')) order by p.fecha limit 50")]
    estrategia = ajuste(con, 'estrategia', {}) or {}
    semanas = []
    s = _lunes(d)
    while s <= h:
        semanas.append(s.isoformat())
        s += timedelta(days=7)
    conteo = {}
    for r in con.execute('''select v.canal_id, coalesce(v.fecha, p.fecha) f, v.estado_pub from variantes v
            join piezas p on p.id=v.pieza_id left join formatos fo on fo.id=v.formato_id
            where p.archivado=0 and v.archivado=0 and p.estado!='idea' and v.estado_pub!='omitida'
            and coalesce(fo.tipo,'')!='story' and coalesce(v.fecha, p.fecha) between ? and ?''', rango):
        semana = _lunes(date.fromisoformat(r['f'])).isoformat()
        c = conteo.setdefault((r['canal_id'], semana), {'planeadas': 0, 'publicadas': 0})
        c['planeadas'] += 1
        c['publicadas'] += r['estado_pub'] == 'publicada'
    posts = []
    for c in con.execute('select * from canales where archivado=0 order by orden, nombre'):
        posts.append({'canal_id': c['id'], 'canal_clave': c['clave'], 'canal': c['nombre'], 'color': c['color'],
                      'meta': _meta_kpi(estrategia.get('kpis'), c['clave']),
                      'semanas': [{'semana': w, **conteo.get((c['id'], w), {'planeadas': 0, 'publicadas': 0})} for w in semanas]})
    por_pilar = {}
    total = 0
    for r in rows:
        if r['estado'] == 'idea':
            continue
        total += 1
        if r['pilar_id']:
            por_pilar[r['pilar_id']] = por_pilar.get(r['pilar_id'], 0) + 1
    equilibrio = [{'pilar_id': p['id'], 'clave': p['clave'], 'nombre': p['nombre'], 'color': p['color'],
                   'objetivo_pct': p['objetivo_pct'], 'piezas': por_pilar.get(p['id'], 0),
                   'real_pct': round(por_pilar.get(p['id'], 0) / total * 100, 1) if total else 0.0}
                  for p in con.execute('select * from pilares where archivado=0 order by orden, nombre')]
    lab = {e: 0 for e in ESTADOS_PRUEBA}
    for r in con.execute('select estado_prueba, count(*) n from secciones where archivado=0 and en_piloto=1 group by estado_prueba'):
        lab[r['estado_prueba']] = r['n']
    return {'desde': rango[0], 'hasta': rango[1], 'hoy': hoy_.isoformat(), 'total': len(rows), 'conteos': conteos,
            'pendientes_aprobacion': pendientes, 'proximas': proximas, 'errores': errores,
            'kpis': {'posts_semana': posts, 'equilibrio_pilares': equilibrio, 'estrategia': estrategia.get('kpis', []),
                     'kpi_estrella': estrategia.get('kpi_estrella')},
            'laboratorio': lab}


def construir_presentacion(con):
    """Instantánea pública con el mismo formato de la semilla (§2), referencias por clave.
    Excluye: ids internos, comentarios, aprobaciones/tokens, responsables, usuarios, brief,
    por_validar (solo su conteo), config de canales, contacto/nota de aliados, enlaces de
    plantillas, temas (banco de ideas), piezas en idea o archivadas y atributos de tipo usuario."""
    claves = {t: {r['id']: r['clave'] for r in con.execute(f'select id, clave from {t}')}
              for t in ('canales', 'formatos', 'plantillas', 'pilares', 'topicos', 'secciones', 'aliados', 'campanas')}

    def todos(tabla, orden):
        return [fila(r) for r in con.execute(f'select * from {tabla} where archivado=0 order by {orden}, id')]

    canales = [{k: c[k] for k in ('clave', 'nombre', 'handle', 'color', 'icono', 'metodo', 'rol', 'cadencia')}
               for c in todos('canales', 'orden, nombre')]
    formatos = [{'clave': f['clave'], 'canal': claves['canales'].get(f['canal_id']), **{k: f[k] for k in (
        'nombre', 'tipo', 'proporcion', 'max_caracteres', 'max_laminas', 'max_segundos', 'interaccion_ideal')}}
                for f in todos('formatos', 'canal_id, nombre')]
    plantillas = [{k: p[k] for k in ('clave', 'nombre', 'que_es', 'virtud', 'que_se_necesita', 'tiempo', 'origen')}
                  for p in todos('plantillas', 'nombre')]
    pilares = [{k: p[k] for k in ('clave', 'nombre', 'color', 'objetivo_pct', 'descripcion')} for p in todos('pilares', 'orden, nombre')]
    topicos = [{'clave': t['clave'], 'pilar': claves['pilares'].get(t['pilar_id']), 'nombre': t['nombre']}
               for t in todos('topicos', 'pilar_id, orden, nombre')]
    secciones = [{'clave': s['clave'], 'topico': claves['topicos'].get(s['topico_id']), 'nombre': s['nombre'],
                  'descripcion': s['descripcion'], 'periodicidad': s['periodicidad'],
                  'formato': claves['formatos'].get(s['formato_id']), 'plantilla': claves['plantillas'].get(s['plantilla_id']),
                  'tiempo_produccion_min': s['tiempo_produccion_min'], 'interaccion_ideal': s['interaccion_ideal'],
                  'estado_prueba': s['estado_prueba'], 'estado_seccion': s['estado_seccion'], 'en_piloto': s['en_piloto']}
                 for s in todos('secciones', 'topico_id, nombre')]
    aliados = [{k: a[k] for k in ('clave', 'nombre', 'tipo')} for a in todos('aliados', 'nombre')]
    campanas = [{k: c[k] for k in ('clave', 'nombre', 'inicio', 'fin', 'objetivo')} for c in todos('campanas', 'inicio, nombre')]
    attrs = [a for a in todos('atributos', 'entidad, orden, nombre') if a['tipo'] != 'usuario']
    atributos = [{k: a[k] for k in ('clave', 'entidad', 'nombre', 'tipo', 'opciones', 'filtrable', 'columna')} for a in attrs]
    visibles = {a['clave'] for a in attrs if a['entidad'] == 'pieza'}
    rows = con.execute(SQL_PIEZAS + " where p.archivado=0 and p.estado!='idea' order by p.fecha, p.hora, p.id").fetchall()
    piezas = []
    for p in serializar_piezas(con, rows):
        piezas.append({
            'clave': p['clave'], 'titulo': p['titulo'], 'seccion': p['seccion_clave'], 'campana': p['campana_clave'],
            'aliado': p['aliado_clave'], 'plantilla': p['plantilla_clave'], 'pilar': p['pilar_clave'],
            'fecha': p['fecha'], 'hora': p['hora'], 'estado': p['estado'], 'prueba': p['prueba'], 'objetivo': p['objetivo'],
            'copy_base': p['copy_base'], 'cumplimiento_ok': p['cumplimiento_ok'], 'pendientes_validar': len(p['por_validar']),
            'atributos': {k: v for k, v in p['atributos'].items() if k in visibles},
            'variantes': [{'canal': v['canal_clave'], 'formato': v['formato_clave'], 'titulo': v['titulo'], 'copy': v['copy'],
                           'hashtags': v['hashtags'], 'fecha': v['fecha'] or p['fecha'], 'hora': v['hora'] or p['hora'],
                           'estado_pub': v['estado_pub'], 'url_publicada': v['url_publicada'], 'medios': len(v['media_ids'])}
                          for v in p['variantes']],
        })
    lab = []
    for s in laboratorio(con):
        def limpia(m):
            if not m:
                return None
            return {'pieza': m['clave'], 'titulo': m['titulo'], 'fecha': m['fecha'], 'hora': m['hora'], 'prueba': m['prueba'],
                    'canal': m['canal_clave'], 'formato': m['formato_clave'], 'interaccion': m['interaccion'],
                    'ideal': m['ideal'], 'pct': m['pct'], 'resultado': m['resultado']}
        lab.append({'seccion': s['clave'], 'nombre': s['nombre'], 'pilar': s['pilar_clave'], 'en_piloto': s['en_piloto'],
                    'interaccion_ideal': s['interaccion_ideal'], 'estado_prueba': s['estado_prueba'],
                    'estado_seccion': s['estado_seccion'], 'pruebas': {r: limpia(m) for r, m in s['pruebas'].items()},
                    'media_pct': s['media_pct'], 'avisos': [a['mensaje'] for a in s['avisos']]})
    piloto = ajuste(con, 'piloto', {}) or {}
    res = resumen(con, piloto.get('inicio'), piloto.get('fin')) if piloto.get('inicio') and piloto.get('fin') else None
    resumen_publico = None
    if res:
        resumen_publico = {'desde': res['desde'], 'hasta': res['hasta'], 'conteos': res['conteos'],
                           'posts_semana': [{k: c[k] for k in ('canal_clave', 'canal', 'color', 'meta', 'semanas')}
                                            for c in res['kpis']['posts_semana']],
                           'equilibrio_pilares': [{k: e[k] for k in ('clave', 'nombre', 'color', 'objetivo_pct', 'piezas', 'real_pct')}
                                                  for e in res['kpis']['equilibrio_pilares']],
                           'laboratorio': res['laboratorio']}
    meta = ajuste(con, 'semilla', {}) or {}
    return {
        'version': 1, 'tipo': 'hub-presentacion', 'publicado_at': now(), 'generado': meta.get('generado'),
        'piloto': piloto, 'estrategia': ajuste(con, 'estrategia', {}) or {},
        'leyenda': ajuste(con, 'leyenda', LEYENDA),
        'canales': canales, 'formatos': formatos, 'plantillas': plantillas, 'pilares': pilares, 'topicos': topicos,
        'secciones': secciones, 'aliados': aliados, 'campanas': campanas, 'atributos': atributos, 'piezas': piezas,
        'laboratorio': lab, 'resumen': resumen_publico,
    }


# ---------------------------------------------------------------------------
# Aprobación pública
# ---------------------------------------------------------------------------
def crear_enlace(con, pid, actor):
    p = con.execute('select estado, archivado from piezas where id=?', (pid,)).fetchone()
    if not p or p['archivado']:
        raise HubError('Pieza no encontrada.', 404)
    if p['estado'] != 'revision':
        raise HubError('Solo se generan enlaces para piezas en revisión.', 409)
    token = secrets.token_urlsafe(32)
    expira = int(time.time()) + APROBACION_DIAS * 86400
    con.execute('insert into aprobaciones(pieza_id,token_hash,expira,creado_por,creado_at) values(?,?,?,?,?)',
                (pid, sha256(token), expira, str(actor)[:120], now()))
    registrar(con, actor, 'Enlace de aprobación generado', 'piezas', pid)
    return token, datetime.fromtimestamp(expira, timezone.utc).isoformat(timespec='seconds')


def buscar_aprobacion(con, token):
    if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
        raise HubError('Enlace no válido.', 404)
    h = sha256(token)
    row = con.execute('select * from aprobaciones where token_hash=?', (h,)).fetchone()
    if not row or not hmac.compare_digest(row['token_hash'], h):
        raise HubError('Enlace no válido.', 404)
    if row['decision']:
        raise HubError('Este enlace ya se usó para decidir.', 410, decision=row['decision'])
    if row['expira'] <= int(time.time()):
        raise HubError('El enlace caducó. Pide uno nuevo al equipo.', 410)
    p = con.execute('select estado, archivado from piezas where id=?', (row['pieza_id'],)).fetchone()
    if not p or p['archivado']:
        raise HubError('Enlace no válido.', 404)
    if p['estado'] != 'revision':
        raise HubError('La pieza ya no está en revisión.', 409)
    return row


def vista_aprobacion(con, row, token, media_get=None):
    p = obtener_pieza(con, row['pieza_id'])
    base = f'/cms/hub/aprobacion/{token}/media/'
    variantes = []
    for v in p['variantes']:
        medios = []
        for mid in v['media_ids']:
            item = media_get(mid) if media_get else None
            medios.append({'id': mid, 'kind': item.get('kind') if item else None, 'title': item.get('title', '') if item else '',
                           'alt': item.get('alt', '') if item else '', 'width': item.get('width') if item else None,
                           'height': item.get('height') if item else None,
                           'url': base + mid + '/file', 'thumbnail': base + mid + '/thumb'})
        variantes.append({'id': v['id'], 'canal': v['canal'], 'canal_clave': v['canal_clave'], 'canal_color': v['canal_color'],
                          'canal_icono': v['canal_icono'], 'formato': v['formato'], 'formato_tipo': v['formato_tipo'],
                          'proporcion': v['proporcion'], 'titulo': v['titulo'], 'copy': v['copy'], 'hashtags': v['hashtags'],
                          'fecha': v['fecha'] or p['fecha'], 'hora': v['hora'] or p['hora'], 'caracteres': v['caracteres'],
                          'limites': v['limites'], 'medios': medios})
    comentarios = [dict(r) for r in con.execute(
        'select autor, texto, creado_at from comentarios where pieza_id=? and interno=0 order by id', (row['pieza_id'],))]
    return {'pieza': {'titulo': p['titulo'], 'fecha': p['fecha'], 'hora': p['hora'], 'estado': p['estado'], 'prueba': p['prueba'],
                      'objetivo': p['objetivo'], 'brief': p['brief'], 'copy_base': p['copy_base'], 'seccion': p['seccion'],
                      'pilar': p['pilar'], 'pilar_color': p['pilar_color'], 'campana': p['campana'], 'aliado': p['aliado'],
                      'cumplimiento': p['cumplimiento'], 'cumplimiento_ok': p['cumplimiento_ok'],
                      'por_validar': p['por_validar'], 'variantes': variantes, 'comentarios': comentarios},
            'expira': datetime.fromtimestamp(row['expira'], timezone.utc).isoformat(timespec='seconds'),
            'leyenda': ajuste(con, 'leyenda', LEYENDA)}


def decidir(con, token, data):
    row = buscar_aprobacion(con, token)
    decision = v_enum(data.get('decision'), ('aprobada', 'cambios'), 'Decisión')
    nombre = v_text(data.get('nombre'), 'Tu nombre', 80, required=True)
    motivo = v_text(data.get('motivo'), 'Motivo', 1000)
    if decision == 'cambios' and not motivo:
        raise HubError('Explica qué cambios se necesitan.')
    actor = f'{nombre} (enlace)'
    cambiar_estado(con, row['pieza_id'], 'aprobada' if decision == 'aprobada' else 'observada', actor,
                   motivo=motivo, por_enlace=True)
    con.execute('update aprobaciones set decision=?, motivo=?, quien=?, decidido_at=? where id=?',
                (decision, motivo, nombre, now(), row['id']))
    return {'ok': True, 'decision': decision, 'estado': 'aprobada' if decision == 'aprobada' else 'observada'}


def pagina_respaldo(titulo, cuerpo_html):
    return ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">'
            f'<title>{html.escape(titulo)} · Cisne Negro</title><link rel="stylesheet" href="/cms/cms.css">'
            '<link rel="stylesheet" href="/cms/hub.css"></head><body class="hub-aprobar"><main class="hub-aprobar__main">'
            f'{cuerpo_html}</main></body></html>')


def html_aprobacion(vista, token, mensaje=''):
    e = html.escape
    p = vista['pieza']
    partes = [f'<h1>{e(p["titulo"])}</h1>',
              f'<p>{e(p["fecha"] or "Sin fecha")} {e(p["hora"] or "")} · {e(p["seccion"] or "")} · {e(p["pilar"] or "")}</p>']
    if mensaje:
        partes.append(f'<p role="alert">{e(mensaje)}</p>')
    if p['copy_base']:
        partes.append(f'<h2>Texto base</h2><p style="white-space:pre-wrap">{e(p["copy_base"])}</p>')
    for v in p['variantes']:
        partes.append(f'<section><h2>{e(v["canal"])} · {e(v["formato"] or "")}</h2>'
                      + (f'<p><strong>{e(v["titulo"])}</strong></p>' if v['titulo'] else '')
                      + f'<p style="white-space:pre-wrap">{e(v["copy"])}</p><p>{e(" ".join(v["hashtags"]))}</p>'
                      + ''.join(f'<img src="{e(m["thumbnail"])}" alt="{e(m["alt"])}" width="160" loading="lazy">' for m in v['medios'])
                      + '</section>')
    if p['comentarios']:
        partes.append('<h2>Comentarios</h2><ul>' + ''.join(
            f'<li><strong>{e(c["autor"])}:</strong> {e(c["texto"])}</li>' for c in p['comentarios']) + '</ul>')
    partes.append(f'''<form method="post" action="/cms/aprobar/{e(token)}">
      <label>Tu nombre <input name="nombre" required maxlength="80" autocomplete="name"></label>
      <label>Comentario (obligatorio si pides cambios) <textarea name="motivo" maxlength="1000"></textarea></label>
      <button type="submit" name="decision" value="aprobada">Aprobar</button>
      <button type="submit" name="decision" value="cambios">Pedir cambios</button></form>
      <p><small>Enlace válido hasta {e(vista["expira"])}. {e(vista["leyenda"])}</small></p>''')
    return pagina_respaldo(p['titulo'], ''.join(partes))


# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------
def register_hub(app):
    """Registra el Blueprint ``hub`` en la app del CMS y prepara ``hub.sqlite``."""
    from flask import Blueprint, Response, g, jsonify, request, send_file, send_from_directory

    root = Path(app.config['CMS_ROOT']).resolve()
    dbpath = init_db(root / 'hub.sqlite')
    presentacion_path = root / 'hub-presentacion.json'
    bp = Blueprint('hub', __name__)

    @contextmanager
    def db():
        with connect(dbpath) as con:
            yield con

    app.extensions['hub_db'] = db
    app.extensions['hub_path'] = dbpath

    def site():
        return Path(app.config['CMS_SITE']).resolve()

    def media():
        return app.extensions.get('cms_media')

    def media_get(mid):
        m = media()
        return m.get(mid) if m else None

    def usuarios():
        cms_db = app.extensions.get('cms_db')
        if not cms_db:
            return {}
        with cms_db() as con:
            return {r['id']: {'id': r['id'], 'name': r['name'], 'role': r['role']}
                    for r in con.execute('select id, name, role from users where active=1 order by id')}

    def roles(con, uid):
        return {r[0] for r in con.execute('select rol from roles_hub where user_id=?', (uid,))}

    def es_dueno():
        return bool(g.user) and g.user.get('role') == 'owner'

    def puede_aprobar(con):
        return es_dueno() or 'aprobador' in roles(con, g.user['id'])

    def actor():
        return g.user['name'] if getattr(g, 'user', None) else 'Sistema'

    def ctx():
        return Contexto(actor(), set(usuarios()), media_get)

    def cuerpo():
        if request.content_length and request.content_length > MAX_BODY:
            raise HubError('Los datos superan el límite permitido.', 413)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise HubError('Se esperaba un objeto JSON.')
        return data

    def solo_dueno():
        if not es_dueno():
            raise HubError('Acceso reservado al dueño.', 403)

    def limite_publico(con):
        ventana = int(app.config.get('HUB_APPROVAL_WINDOW', VENTANA_PUBLICA))
        limite = int(app.config.get('HUB_APPROVAL_LIMIT', LIMITE_PUBLICO))
        clave, ahora = sha256('aprobar:' + (request.remote_addr or '')), int(time.time())
        con.execute('delete from intentos where at<?', (ahora - ventana,))
        if con.execute('select count(*) from intentos where clave=?', (clave,)).fetchone()[0] >= limite:
            raise HubError('Demasiados intentos. Espera unos minutos.', 429)
        con.execute('insert into intentos values(?,?)', (clave, ahora))

    @bp.errorhandler(HubError)
    def hub_error(exc):
        return jsonify(error=str(exc), **exc.extra), exc.status_code

    @bp.errorhandler(sqlite3.IntegrityError)
    def integrity(exc):
        return jsonify(error='Los datos chocan con otro registro o con una dependencia.'), 409

    # ---- Estáticos y páginas -------------------------------------------------
    def estatico(nombre):
        carpeta = site() / 'cms'
        if not (carpeta / nombre).is_file():
            return jsonify(error='No encontrado.'), 404
        return send_from_directory(carpeta, nombre)

    @bp.get('/cms/hub.js')
    def hub_js():
        return estatico('hub.js')

    @bp.get('/cms/hub.css')
    def hub_css():
        return estatico('hub.css')

    if app.config.get('CMS_DEV'):
        @bp.get('/cms/hub-dev.html')
        def hub_dev():
            if (site() / 'cms' / 'hub-dev.html').is_file():
                return send_from_directory(site() / 'cms', 'hub-dev.html')
            return Response('<!doctype html><html lang="es"><head><meta charset="utf-8">'
                            '<meta name="viewport" content="width=device-width,initial-scale=1">'
                            '<title>Content Hub · desarrollo</title><link rel="stylesheet" href="/cms/cms.css">'
                            '<link rel="stylesheet" href="/cms/hub.css"></head><body data-hub-dev="1">'
                            '<main id="hub-root"></main><script src="/cms/hub.js" defer></script></body></html>',
                            mimetype='text/html')

    @bp.get('/cms/hub/presentacion.json')
    def presentacion_publica():
        if not presentacion_path.is_file():
            return jsonify(error='Aún no hay una presentación publicada.'), 404
        return Response(presentacion_path.read_bytes(), mimetype='application/json')

    # ---- Aprobación pública ----------------------------------------------------
    @bp.get('/cms/aprobar/<token>')
    def aprobar_pagina(token):
        if (site() / 'cms' / 'aprobar.html').is_file():
            return send_from_directory(site() / 'cms', 'aprobar.html')
        try:
            with db() as con:
                limite_publico(con)
            with db() as con:
                vista = vista_aprobacion(con, buscar_aprobacion(con, token), token, media_get)
            return Response(html_aprobacion(vista, token), mimetype='text/html')
        except HubError as exc:
            return Response(pagina_respaldo('Aprobación', f'<h1>Aprobación</h1><p role="alert">{html.escape(str(exc))}</p>'),
                            status=exc.status_code, mimetype='text/html')

    @bp.post('/cms/aprobar/<token>')
    def aprobar_formulario(token):
        datos = {k: request.form.get(k, '') for k in ('decision', 'nombre', 'motivo')}
        try:
            with db() as con:
                limite_publico(con)
            with db() as con:
                con.execute('begin immediate')
                r = decidir(con, token, datos)
            texto = '¡Gracias! La pieza quedó aprobada.' if r['decision'] == 'aprobada' else 'Gracias. Enviamos tus cambios al equipo.'
            return Response(pagina_respaldo('Aprobación', f'<h1>Listo</h1><p role="status">{html.escape(texto)}</p>'), mimetype='text/html')
        except HubError as exc:
            return Response(pagina_respaldo('Aprobación', f'<h1>Aprobación</h1><p role="alert">{html.escape(str(exc))}</p>'),
                            status=exc.status_code, mimetype='text/html')

    @bp.get('/cms/hub/aprobacion/<token>')
    def aprobacion_ver(token):
        with db() as con:
            limite_publico(con)
        with db() as con:
            return jsonify(vista_aprobacion(con, buscar_aprobacion(con, token), token, media_get))

    @bp.post('/cms/hub/aprobacion/<token>')
    def aprobacion_decidir(token):
        with db() as con:
            limite_publico(con)
        data = cuerpo()
        with db() as con:
            con.execute('begin immediate')
            return jsonify(decidir(con, token, data))

    @bp.get('/cms/hub/aprobacion/<token>/media/<mid>/<variante>')
    def aprobacion_media(token, mid, variante):
        if variante not in ('file', 'thumb') or not MEDIA_ID_RE.fullmatch(mid):
            return jsonify(error='No encontrado.'), 404
        try:
            with db() as con:
                row = buscar_aprobacion(con, token)
                usados = set()
                for r in con.execute('select media_ids from variantes where pieza_id=? and archivado=0', (row['pieza_id'],)):
                    usados.update(loads(r[0], []))
        except HubError:
            with db() as con:
                limite_publico(con)
            return jsonify(error='No encontrado.'), 404
        if mid not in usados or not media():
            return jsonify(error='No encontrado.'), 404
        try:
            path = media().path(mid, variante)
        except (ValueError, OSError):
            return jsonify(error='No encontrado.'), 404
        resp = send_file(path, conditional=True, max_age=0)
        resp.headers['Content-Disposition'] = 'inline'
        return resp

    # ---- API interna ---------------------------------------------------------------
    @bp.get('/cms/api/hub/catalogos')
    def catalogos():
        us = usuarios()
        with db() as con:
            out = {nombre: listar_catalogo(con, nombre) for nombre in CATALOGOS}
            rh = {}
            for r in con.execute('select user_id, rol from roles_hub order by rol'):
                rh.setdefault(r[0], []).append(r[1])
            out['usuarios'] = [{'id': u['id'], 'name': u['name'], 'role': u['role'], 'roles_hub': rh.get(u['id'], [])}
                               for u in us.values()]
            out['ajustes'] = {'leyenda': ajuste(con, 'leyenda', LEYENDA), 'zona': ajuste(con, 'zona', ZONA),
                              'piloto': ajuste(con, 'piloto', {})}
            out['yo'] = {'id': g.user['id'], 'name': g.user['name'], 'role': g.user['role'],
                         'roles_hub': sorted(roles(con, g.user['id'])), 'puede_aprobar': puede_aprobar(con)}
        out['meta'] = {'estados': list(ESTADOS), 'transiciones': {k: list(v) for k, v in TRANSICIONES.items()},
                       'estados_pub': list(ESTADOS_PUB), 'pruebas': list(PRUEBAS), 'estados_prueba': list(ESTADOS_PRUEBA),
                       'estados_seccion': list(ESTADOS_SECCION), 'checklist': list(CHECKLIST),
                       'checklist_cerveza': list(CHECKLIST_CERVEZA), 'tipos_atributo': list(TIPOS_ATRIBUTO),
                       'entidades_atributo': list(ENTIDADES), 'metodos': list(METODOS), 'roles_hub': list(ROLES_HUB),
                       'limites_red': LIMITES_RED, 'alias_red': ALIAS_RED}
        return jsonify(out)

    @bp.get('/cms/api/hub/resumen')
    def ver_resumen():
        with db() as con:
            return jsonify(resumen(con, request.args.get('desde'), request.args.get('hasta')))

    @bp.get('/cms/api/hub/laboratorio')
    def ver_laboratorio():
        with db() as con:
            return jsonify(items=laboratorio(con))

    @bp.get('/cms/api/hub/actividad')
    def ver_actividad():
        with db() as con:
            return jsonify(items=[dict(r) for r in con.execute(
                'select actor, accion, entidad, entidad_id, creado_at from actividad order by id desc limit 200')])

    @bp.get('/cms/api/hub/media')
    def ver_media():
        m = media()
        if not m:
            return jsonify(items=[], total=0, page=1, pages=1)
        limite = v_int(request.args.get('limit') or 36, 'Límite', 1, 36)
        pagina = v_int(request.args.get('page') or 1, 'Página', 1, 100000)
        kind = request.args.get('kind', '')
        if kind not in ('', 'image', 'video'):
            raise HubError('Tipo de archivo no válido.')
        res = m.list(q=request.args.get('q', '')[:200], kind=kind, page=pagina)
        campos = ('id', 'title', 'alt', 'caption', 'category', 'kind', 'width', 'height', 'duration', 'status', 'url', 'thumbnail', 'tags')
        return jsonify(items=[{k: i.get(k) for k in campos} for i in res['items'][:limite]],
                       total=res['total'], page=res['page'], pages=res['pages'])

    # Piezas
    @bp.get('/cms/api/hub/piezas')
    def piezas_listar():
        us = usuarios()
        limite = v_int(request.args.get('limit') or 2000, 'Límite', 1, 5000)
        with db() as con:
            items, total = filtrar_piezas(con, request.args, us, limite)
        return jsonify(items=items, total=total)

    @bp.get('/cms/api/hub/piezas.csv')
    def piezas_csv():
        us = usuarios()
        with db() as con:
            items, _ = filtrar_piezas(con, request.args, us, 10000)
            attrs = [fila(r) for r in con.execute("select * from atributos where entidad='pieza' and archivado=0 order by orden, nombre")]
        buf = io.StringIO()
        w = csv.writer(buf)
        base = ['id', 'clave', 'fecha', 'hora', 'titulo', 'estado', 'prueba', 'pilar', 'topico', 'seccion', 'campana', 'aliado',
                'plantilla', 'responsable', 'objetivo', 'canales', 'copy_base', 'por_validar', 'cumplimiento_ok']
        w.writerow(base + [a['nombre'] for a in attrs])

        def celda(v):
            if v is None:
                return ''
            if isinstance(v, bool):
                v = 'sí' if v else 'no'
            v = str(v)
            return "'" + v if v[:1] in ('=', '+', '-', '@', '\t', '\r') else v

        for p in items:
            fila_csv = [p['id'], p['clave'], p['fecha'], p['hora'], p['titulo'], p['estado'], p['prueba'], p['pilar'], p['topico'],
                        p['seccion'], p['campana'], p['aliado'], p['plantilla'], p['responsable'], p['objetivo'],
                        ' '.join(v['canal_clave'] for v in p['variantes']), p['copy_base'], ' | '.join(p['por_validar']),
                        p['cumplimiento_ok']]
            fila_csv += [p['atributos'].get(a['clave']) for a in attrs]
            w.writerow([celda(v) for v in fila_csv])
        resp = Response('\ufeff' + buf.getvalue(), mimetype='text/csv; charset=utf-8')
        resp.headers['Content-Disposition'] = 'attachment; filename="parrilla-cisne-negro.csv"'
        return resp

    @bp.post('/cms/api/hub/piezas')
    def piezas_crear():
        data = cuerpo()
        c, us = ctx(), usuarios()
        with db() as con:
            con.execute('begin immediate')
            pid = guardar_pieza(con, data, c)
            item = detalle_pieza(con, pid, us)
        return jsonify(item=item), 201

    @bp.get('/cms/api/hub/piezas/<int:pid>')
    def piezas_ver(pid):
        us = usuarios()
        with db() as con:
            return jsonify(item=detalle_pieza(con, pid, us))

    @bp.get('/cms/api/hub/piezas/<int:pid>/versiones/<int:numero>')
    def piezas_version(pid, numero):
        with db() as con:
            r = con.execute('select version, autor, creado_at, datos from versiones where pieza_id=? and version=? order by id desc',
                            (pid, numero)).fetchone()
        if not r:
            raise HubError('Versión no encontrada.', 404)
        return jsonify(version=r['version'], autor=r['autor'], creado_at=r['creado_at'], datos=loads(r['datos'], {}))

    @bp.put('/cms/api/hub/piezas/<int:pid>')
    def piezas_editar(pid):
        data = cuerpo()
        version = data.get('version')
        if not isinstance(version, int) or isinstance(version, bool):
            raise HubError('Falta la versión de la pieza.')
        c, us = ctx(), usuarios()
        with db() as con:
            con.execute('begin immediate')
            guardar_pieza(con, data, c, pid, version)
            item = detalle_pieza(con, pid, us)
        return jsonify(item=item)

    @bp.delete('/cms/api/hub/piezas/<int:pid>')
    def piezas_borrar(pid):
        definitivo = request.args.get('definitivo') in ('1', 'true')
        if definitivo:
            solo_dueno()
        with db() as con:
            con.execute('begin immediate')
            return jsonify(borrar_pieza(con, pid, actor(), definitivo))

    @bp.post('/cms/api/hub/piezas/<int:pid>/mover')
    def piezas_mover(pid):
        data = cuerpo()
        version = data.get('version')
        if version is not None and (not isinstance(version, int) or isinstance(version, bool)):
            raise HubError('Versión no válida.')
        us = usuarios()
        with db() as con:
            con.execute('begin immediate')
            mover_pieza(con, pid, data.get('fecha'), data.get('hora'), actor(), version)
            return jsonify(item=detalle_pieza(con, pid, us))

    @bp.post('/cms/api/hub/piezas/<int:pid>/duplicar')
    def piezas_duplicar(pid):
        us = usuarios()
        with db() as con:
            con.execute('begin immediate')
            nueva = duplicar_pieza(con, pid, actor())
            return jsonify(item=detalle_pieza(con, nueva, us)), 201

    @bp.post('/cms/api/hub/piezas/<int:pid>/estado')
    def piezas_estado(pid):
        data = cuerpo()
        us = usuarios()
        with db() as con:
            con.execute('begin immediate')
            r = cambiar_estado(con, pid, data.get('estado'), actor(), data.get('motivo', ''), puede_aprobar(con))
            if r.get('archivado'):
                return jsonify(r)
            return jsonify(item=detalle_pieza(con, pid, us), **r)

    @bp.post('/cms/api/hub/piezas/<int:pid>/enlace-aprobacion')
    def piezas_enlace(pid):
        with db() as con:
            con.execute('begin immediate')
            token, expira = crear_enlace(con, pid, actor())
        ruta = f'/cms/aprobar/{token}'
        return jsonify(url=app.config.get('CMS_ORIGIN', '').rstrip('/') + ruta, ruta=ruta, expira=expira), 201

    @bp.get('/cms/api/hub/piezas/<int:pid>/comentarios')
    def comentarios_ver(pid):
        with db() as con:
            if not con.execute('select 1 from piezas where id=?', (pid,)).fetchone():
                raise HubError('Pieza no encontrada.', 404)
            return jsonify(items=[fila(r) for r in con.execute(
                'select id, autor, texto, interno, creado_at from comentarios where pieza_id=? order by id', (pid,))])

    @bp.post('/cms/api/hub/piezas/<int:pid>/comentarios')
    def comentarios_crear(pid):
        data = cuerpo()
        texto = v_text(data.get('texto'), 'Comentario', 2000, required=True)
        interno = v_bool(data.get('interno', True), 'Interno')
        with db() as con:
            con.execute('begin immediate')
            if not con.execute('select 1 from piezas where id=?', (pid,)).fetchone():
                raise HubError('Pieza no encontrada.', 404)
            cid = con.execute('insert into comentarios(pieza_id,autor,texto,interno,creado_at) values(?,?,?,?,?)',
                              (pid, actor(), texto, int(interno), now())).lastrowid
            registrar(con, actor(), 'Comentario ' + ('interno' if interno else 'visible para aprobación'), 'piezas', pid)
            item = fila(con.execute('select id, autor, texto, interno, creado_at from comentarios where id=?', (cid,)).fetchone())
        return jsonify(item=item), 201

    @bp.post('/cms/api/hub/variantes/<int:vid>/publicada')
    def variante_publicada(vid):
        data = cuerpo()
        with db() as con:
            con.execute('begin immediate')
            estado = marcar_publicada(con, vid, data.get('url'), data.get('publicado_at'), actor(), data.get('id_externo', ''))
            v = fila(con.execute('select * from variantes where id=?', (vid,)).fetchone())
        return jsonify(ok=True, variante=v, estado_pieza=estado)

    @bp.post('/cms/api/hub/variantes/<int:vid>/metricas')
    def variante_metricas(vid):
        data = cuerpo()
        with db() as con:
            con.execute('begin immediate')
            mid, seccion = guardar_metrica(con, vid, data, actor())
            m = dict(con.execute('select * from metricas where id=?', (mid,)).fetchone())
        m['interaccion'] = interaccion(m)
        return jsonify(metrica=m, seccion=seccion), 201

    @bp.get('/cms/api/hub/variantes/<int:vid>/metricas')
    def variante_metricas_ver(vid):
        with db() as con:
            items = [dict(r) for r in con.execute('select * from metricas where variante_id=? order by id', (vid,))]
        for m in items:
            m['interaccion'] = interaccion(m)
        return jsonify(items=items)

    # Ajustes
    @bp.get('/cms/api/hub/ajustes')
    def ajustes_ver():
        us = usuarios()
        meta_ok, postiz_ok = bool(os.environ.get('HUB_META_TOKEN')), bool(os.environ.get('HUB_POSTIZ_URL'))
        estado = {'manual': True, 'meta_api': meta_ok, 'postiz': postiz_ok}
        with db() as con:
            rh = {}
            for r in con.execute('select user_id, rol from roles_hub order by rol'):
                rh.setdefault(r[0], []).append(r[1])
            return jsonify(
                canales=[{'id': c['id'], 'clave': c['clave'], 'nombre': c['nombre'], 'metodo': c['metodo'],
                          'configurado': estado[c['metodo']]}
                         for c in con.execute('select id, clave, nombre, metodo from canales where archivado=0 order by orden, nombre')],
                integraciones={'meta_api': {'configurado': meta_ok}, 'postiz': {'configurado': postiz_ok}},
                metodos=list(METODOS), leyenda=ajuste(con, 'leyenda', LEYENDA), zona=ajuste(con, 'zona', ZONA),
                piloto=ajuste(con, 'piloto', {}),
                roles=[{'user_id': u['id'], 'name': u['name'], 'role': u['role'], 'roles': rh.get(u['id'], [])} for u in us.values()],
                roles_disponibles=list(ROLES_HUB), editable=es_dueno())

    @bp.put('/cms/api/hub/ajustes')
    def ajustes_editar():
        solo_dueno()
        data = cuerpo()
        us = usuarios()
        with db() as con:
            con.execute('begin immediate')
            if 'leyenda' in data:
                guardar_ajuste(con, 'leyenda', v_text(data['leyenda'], 'Leyenda', 200, required=True))
            if 'zona' in data:
                zona = v_text(data['zona'], 'Zona horaria', 60, required=True)
                try:
                    from zoneinfo import ZoneInfo
                    ZoneInfo(zona)
                except Exception:
                    raise HubError('Zona horaria no válida.') from None
                guardar_ajuste(con, 'zona', zona)
            if 'piloto' in data:
                p = v_obj(data['piloto'], 'Piloto', 4000)
                for k in ('inicio', 'fin'):
                    if k in p:
                        v_fecha(p[k], f'Piloto: {k}')
                guardar_ajuste(con, 'piloto', p)
            if 'canales' in data:
                if not isinstance(data['canales'], list):
                    raise HubError('Canales: se esperaba una lista.')
                for c in data['canales'][:50]:
                    if not isinstance(c, dict):
                        raise HubError('Canales: cada elemento debe ser un objeto.')
                    guardar_catalogo(con, 'canales', {'metodo': c.get('metodo')}, actor(), v_int(c.get('id'), 'Canal', 1, 2 ** 62, nullable=False))
            if 'roles' in data:
                if not isinstance(data['roles'], list):
                    raise HubError('Roles: se esperaba una lista.')
                for r in data['roles'][:50]:
                    if not isinstance(r, dict):
                        raise HubError('Roles: cada elemento debe ser un objeto.')
                    uid = v_int(r.get('user_id'), 'Usuario', 1, 2 ** 62, nullable=False)
                    if uid not in us:
                        raise HubError('Roles: usuario no encontrado.')
                    lista = r.get('roles') or []
                    if not isinstance(lista, list) or any(x not in ROLES_HUB for x in lista):
                        raise HubError('Roles: rol no admitido.')
                    con.execute('delete from roles_hub where user_id=?', (uid,))
                    for rol in set(lista):
                        con.execute('insert into roles_hub(user_id,rol,creado_at) values(?,?,?)', (uid, rol, now()))
            registrar(con, actor(), 'Ajustes del Hub actualizados', 'ajustes')
        return ajustes_ver()

    # Presentación
    @bp.post('/cms/api/hub/presentacion/publicar')
    def presentacion_publicar():
        solo_dueno()
        with db() as con:
            datos = construir_presentacion(con)
            registrar(con, actor(), 'Presentación publicada', 'presentacion')
        tmp = presentacion_path.with_suffix('.json.tmp')
        tmp.write_text(dumps(datos), encoding='utf-8')
        try:
            os.chmod(tmp, 0o640)
        except OSError:
            pass
        os.replace(tmp, presentacion_path)
        return jsonify(ok=True, publicado_at=datos['publicado_at'], piezas=len(datos['piezas']), url='/cms/hub/presentacion.json')

    # CRUD genérico de catálogos (después de las rutas fijas; las reglas estáticas ganan)
    @bp.get('/cms/api/hub/<catalogo_nombre>')
    def cat_listar(catalogo_nombre):
        catalogo(catalogo_nombre)
        filtros = {k: v for k, v in request.args.items() if k.endswith('_id')}
        with db() as con:
            return jsonify(items=listar_catalogo(con, catalogo_nombre, request.args.get('archivados') in ('1', 'true'), filtros))

    def _cat_item(con, nombre, item_id):
        spec = catalogo(nombre)
        items = [i for i in listar_catalogo(con, nombre, archivados=True) if i['id'] == item_id]
        if not items:
            raise HubError(f"{spec['etiqueta']} no encontrado.", 404)
        return items[0]

    @bp.post('/cms/api/hub/<catalogo_nombre>')
    def cat_crear(catalogo_nombre):
        catalogo(catalogo_nombre)
        data = cuerpo()
        us = set(usuarios())
        with db() as con:
            con.execute('begin immediate')
            iid, _ = guardar_catalogo(con, catalogo_nombre, data, actor(), usuarios=us)
            return jsonify(item=_cat_item(con, catalogo_nombre, iid)), 201

    @bp.put('/cms/api/hub/<catalogo_nombre>/<int:item_id>')
    def cat_editar(catalogo_nombre, item_id):
        catalogo(catalogo_nombre)
        data = cuerpo()
        us = set(usuarios())
        with db() as con:
            con.execute('begin immediate')
            guardar_catalogo(con, catalogo_nombre, data, actor(), item_id, usuarios=us)
            return jsonify(item=_cat_item(con, catalogo_nombre, item_id))

    @bp.delete('/cms/api/hub/<catalogo_nombre>/<int:item_id>')
    def cat_borrar(catalogo_nombre, item_id):
        catalogo(catalogo_nombre)
        definitivo = request.args.get('definitivo') in ('1', 'true')
        if definitivo:
            solo_dueno()
        with db() as con:
            con.execute('begin immediate')
            return jsonify(borrar_catalogo(con, catalogo_nombre, item_id, actor(), definitivo))

    app.register_blueprint(bp)
    return bp
