"""Carga la semilla del Content Hub en <CMS_ROOT>/hub.sqlite sin levantar Flask.

Uso: python3 hub_seed.py --root <CMS_ROOT> --seed <json> [--reset]

- Idempotente: hace upsert por ``clave`` y resuelve referencias por clave. Correrlo dos
  veces no duplica nada y la segunda vez no cambia ningún registro.
- Catálogos y atributos: la semilla manda (se actualizan los campos que trae).
- Piezas: se actualizan solo si nadie las editó en el Hub (todas sus versiones son de
  «Semilla») y siguen en idea o borrador; si no, se conservan y se reportan.
- Variantes: se identifican por (canal, formato) dentro de la pieza.
- Temas: por (sección, título).
- ``--reset`` borra el contenido del Hub (catálogos, piezas, métricas, aprobaciones)
  antes de cargar; conserva roles del Hub, ajustes y bitácora.
- Los ``media_ids`` se validan solo en formato (no se abre MediaHub).
Todo corre en una transacción: si algo falla, no se escribe nada.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cms_hub as hub  # noqa: E402

ACTOR = 'Semilla'
ORDEN_RESET = ('temas', 'metricas', 'aprobaciones', 'comentarios', 'versiones', 'variantes', 'valores', 'piezas',
               'secciones', 'atributos', 'topicos', 'pilares', 'formatos', 'canales', 'plantillas', 'aliados', 'campanas')
CAMPOS_SIMPLES = {
    'canales': ('nombre', 'handle', 'color', 'icono', 'metodo', 'rol', 'cadencia', 'config', 'orden'),
    'formatos': ('nombre', 'tipo', 'proporcion', 'max_caracteres', 'max_laminas', 'max_segundos', 'interaccion_ideal'),
    'plantillas': ('nombre', 'que_es', 'virtud', 'que_se_necesita', 'tiempo', 'origen', 'enlace'),
    'pilares': ('nombre', 'color', 'objetivo_pct', 'descripcion', 'orden'),
    'topicos': ('nombre', 'orden'),
    'secciones': ('nombre', 'descripcion', 'periodicidad', 'tiempo_produccion_min', 'interaccion_ideal',
                  'estado_prueba', 'estado_seccion', 'en_piloto'),
    'aliados': ('nombre', 'tipo', 'contacto', 'nota'),
    'campanas': ('nombre', 'inicio', 'fin', 'objetivo'),
    'atributos': ('entidad', 'nombre', 'tipo', 'opciones', 'requerido', 'filtrable', 'columna', 'orden'),
}
# referencia en la semilla -> (columna, tabla)
REFERENCIAS = {
    'formatos': {'canal': ('canal_id', 'canales')},
    'topicos': {'pilar': ('pilar_id', 'pilares')},
    'secciones': {'topico': ('topico_id', 'topicos'), 'formato': ('formato_id', 'formatos'),
                  'plantilla': ('plantilla_id', 'plantillas')},
}


def _usuarios(root):
    path = Path(root) / 'cms.sqlite'
    if not path.is_file():
        return None
    try:
        con = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        try:
            return {r[0] for r in con.execute('select id from users where active=1')}
        finally:
            con.close()
    except sqlite3.Error:
        return None


def _id_por_clave(con, tabla, clave, contexto):
    if clave in (None, ''):
        return None
    row = con.execute(f'select id from {tabla} where clave=?', (clave,)).fetchone()
    if not row:
        raise hub.HubError(f'{contexto}: no existe «{clave}» en {tabla}.')
    return row[0]


def _lista(data, nombre):
    valor = data.get(nombre) or []
    if not isinstance(valor, list):
        raise hub.HubError(f'«{nombre}» debe ser una lista.')
    for item in valor:
        if not isinstance(item, dict):
            raise hub.HubError(f'«{nombre}»: cada elemento debe ser un objeto.')
    return valor


def _upsert_catalogo(con, nombre, item, stats, usuarios):
    tabla = hub.CATALOGOS[nombre]['tabla']
    clave = hub.v_clave(item.get('clave'), f'{nombre}: clave')
    payload = {k: item[k] for k in CAMPOS_SIMPLES[nombre] if k in item}
    for ref, (col, destino) in REFERENCIAS.get(nombre, {}).items():
        if ref in item:
            payload[col] = _id_por_clave(con, destino, item[ref], f'{nombre} «{clave}»')
    if isinstance(item.get('atributos'), dict) and hub.CATALOGOS[nombre].get('entidad'):
        payload['atributos'] = item['atributos']
    row = con.execute(f'select id from {tabla} where clave=?', (clave,)).fetchone()
    if row:
        iid, cambio = hub.guardar_catalogo(con, nombre, payload, ACTOR, row[0], usuarios=usuarios, log=False)
        stats['actualizados' if cambio else 'sin_cambios'][nombre] = stats['actualizados' if cambio else 'sin_cambios'].get(nombre, 0) + 1
    else:
        payload['clave'] = clave
        iid, _ = hub.guardar_catalogo(con, nombre, payload, ACTOR, usuarios=usuarios, log=False)
        stats['creados'][nombre] = stats['creados'].get(nombre, 0) + 1
    return iid


def _temas(con, seccion_id, temas, stats):
    if not isinstance(temas, list):
        raise hub.HubError('«temas» debe ser una lista.')
    for t in temas:
        if isinstance(t, str):
            t = {'titulo': t}
        if not isinstance(t, dict):
            raise hub.HubError('Cada tema debe ser texto u objeto {titulo, explicacion}.')
        titulo = hub.v_text(t.get('titulo'), 'Tema', 300, required=True)
        row = con.execute('select id from temas where seccion_id=? and titulo=?', (seccion_id, titulo)).fetchone()
        payload = {'seccion_id': seccion_id, 'titulo': titulo}
        if 'explicacion' in t:
            payload['explicacion'] = t['explicacion']
        if row:
            _, cambio = hub.guardar_catalogo(con, 'temas', payload, ACTOR, row[0], log=False)
            clave = 'actualizados' if cambio else 'sin_cambios'
        else:
            hub.guardar_catalogo(con, 'temas', payload, ACTOR, log=False)
            clave = 'creados'
        stats[clave]['temas'] = stats[clave].get('temas', 0) + 1


def _pieza(con, item, stats, ctx):
    clave = hub.v_clave(item.get('clave'), 'pieza: clave')
    contexto = f'pieza «{clave}»'
    payload = {k: item[k] for k in ('titulo', 'fecha', 'hora', 'prueba', 'objetivo', 'brief', 'copy_base',
                                     'por_validar', 'cumplimiento') if k in item}
    for ref, (col, tabla) in {'seccion': ('seccion_id', 'secciones'), 'campana': ('campana_id', 'campanas'),
                              'aliado': ('aliado_id', 'aliados'), 'plantilla': ('plantilla_id', 'plantillas')}.items():
        if ref in item:
            payload[col] = _id_por_clave(con, tabla, item[ref], contexto)
    if isinstance(item.get('atributos'), dict):
        payload['atributos'] = item['atributos']
    actual = con.execute('select * from piezas where clave=?', (clave,)).fetchone()
    variantes = []
    vistos = set()
    for v in _lista(item, 'variantes'):
        canal_id = _id_por_clave(con, 'canales', v.get('canal'), contexto)
        formato_id = _id_por_clave(con, 'formatos', v.get('formato'), contexto)
        if (canal_id, formato_id) in vistos:
            raise hub.HubError(f'{contexto}: variante repetida ({v.get("canal")}, {v.get("formato")}).')
        vistos.add((canal_id, formato_id))
        dato = {k: v[k] for k in ('titulo', 'copy', 'hashtags', 'media_ids', 'fecha', 'hora') if k in v}
        dato.update(canal_id=canal_id, formato_id=formato_id)
        if actual is not None:
            existente = con.execute('select id from variantes where pieza_id=? and canal_id=? and formato_id is ? and archivado=0',
                                    (actual['id'], canal_id, formato_id)).fetchone()
            if existente:
                dato['id'] = existente[0]
        variantes.append(dato)
    payload['variantes'] = variantes
    estado = item.get('estado') or 'borrador'
    hub.v_enum(estado, hub.ESTADOS, f'{contexto}: estado')
    try:
        if actual is None:
            payload['clave'] = clave
            payload['estado'] = 'borrador' if estado not in ('idea', 'borrador') else estado
            pid = hub.guardar_pieza(con, payload, ctx, log=False)
            if estado not in ('idea', 'borrador'):
                con.execute('update piezas set estado=? where id=?', (estado, pid))
            stats['creados']['piezas'] = stats['creados'].get('piezas', 0) + 1
            return
        autores = {r[0] for r in con.execute('select distinct autor from versiones where pieza_id=?', (actual['id'],))}
        if autores - {ACTOR} or actual['estado'] not in ('idea', 'borrador'):
            stats['conservadas'].append(clave)
            return
        con.execute('savepoint pieza')
        antes = hub.contenido_pieza(con, actual['id'])
        hub.guardar_pieza(con, payload, ctx, actual['id'], actual['version'], log=False)
        if estado != actual['estado']:
            con.execute('update piezas set estado=? where id=?', (estado, actual['id']))
        if hub.contenido_pieza(con, actual['id']) == antes:
            con.execute('rollback to pieza')
            stats['sin_cambios']['piezas'] = stats['sin_cambios'].get('piezas', 0) + 1
        else:
            stats['actualizados']['piezas'] = stats['actualizados'].get('piezas', 0) + 1
        con.execute('release pieza')
    except hub.HubError as exc:
        raise hub.HubError(f'{contexto}: {exc}', exc.status_code) from None


def cargar(root, data, reset=False):
    """Carga ``data`` (dict con el formato §2) en ``<root>/hub.sqlite``. Devuelve estadísticas."""
    if not isinstance(data, dict):
        raise hub.HubError('La semilla debe ser un objeto JSON.')
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = hub.init_db(root / 'hub.sqlite')
    usuarios = _usuarios(root)
    ctx = hub.Contexto(ACTOR, usuarios, None)
    stats = {'creados': {}, 'actualizados': {}, 'sin_cambios': {}, 'conservadas': []}
    with hub.connect(path) as con:
        con.execute('begin immediate')
        if reset:
            for tabla in ORDEN_RESET:
                con.execute(f'delete from {tabla}')
        if 'piloto' in data:
            piloto = hub.v_obj(data['piloto'], 'piloto', 4000)
            for k in ('inicio', 'fin'):
                if k in piloto:
                    hub.v_fecha(piloto[k], f'piloto.{k}')
            if hub.ajuste(con, 'piloto') != piloto:
                hub.guardar_ajuste(con, 'piloto', piloto)
            if piloto.get('zona') and hub.ajuste(con, 'zona') != piloto['zona']:
                hub.guardar_ajuste(con, 'zona', hub.v_text(piloto['zona'], 'piloto.zona', 60))
        if 'estrategia' in data:
            estrategia = hub.v_obj(data['estrategia'], 'estrategia', 200000)
            if hub.ajuste(con, 'estrategia') != estrategia:
                hub.guardar_ajuste(con, 'estrategia', estrategia)
            if estrategia.get('leyenda_sanitaria'):
                leyenda = hub.v_text(estrategia['leyenda_sanitaria'], 'leyenda_sanitaria', 200)
                if hub.ajuste(con, 'leyenda') != leyenda:
                    hub.guardar_ajuste(con, 'leyenda', leyenda)
        meta = {'version': data.get('version'), 'generado': data.get('generado')}
        if hub.ajuste(con, 'semilla') != meta:
            hub.guardar_ajuste(con, 'semilla', meta)
        # Atributos primero: secciones, aliados y campañas pueden traer valores.
        for item in _lista(data, 'atributos'):
            _upsert_catalogo(con, 'atributos', item, stats, usuarios)
        for nombre in ('canales', 'formatos', 'plantillas', 'pilares', 'topicos', 'aliados', 'campanas'):
            for item in _lista(data, nombre):
                _upsert_catalogo(con, nombre, item, stats, usuarios)
        for item in _lista(data, 'secciones'):
            sid = _upsert_catalogo(con, 'secciones', item, stats, usuarios)
            if 'temas' in item:
                _temas(con, sid, item['temas'], stats)
        for item in _lista(data, 'piezas'):
            _pieza(con, item, stats, ctx)
        if stats['creados'] or stats['actualizados'] or reset:
            resumen = ', '.join(f'{k}: {v}' for k, v in sorted(stats['creados'].items())) or 'sin altas'
            hub.registrar(con, ACTOR, f'Semilla cargada ({resumen})' + (' con reinicio' if reset else ''), 'semilla')
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description='Carga la semilla del Content Hub en hub.sqlite.')
    parser.add_argument('--root', required=True, help='CMS_ROOT (carpeta privada con cms.sqlite)')
    parser.add_argument('--seed', required=True, help='JSON con el formato de la semilla (§2)')
    parser.add_argument('--reset', action='store_true', help='Borra el contenido del Hub antes de cargar')
    args = parser.parse_args(argv)
    try:
        data = json.loads(Path(args.seed).read_text(encoding='utf-8'))
        stats = cargar(args.root, data, reset=args.reset)
    except (OSError, json.JSONDecodeError) as exc:
        print(f'No se pudo leer la semilla: {exc}', file=sys.stderr)
        return 1
    except (hub.HubError, ValueError, sqlite3.Error) as exc:
        print(f'Semilla rechazada (no se escribió nada): {exc}', file=sys.stderr)
        return 1
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
