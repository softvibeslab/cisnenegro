"""Genera sitio/estrategia/data.json: la instantánea pública del tablero de contenido.

Carga la semilla en un Hub temporal y usa la misma función que publica el Hub
(`construir_presentacion`), así que data.json tiene exactamente el formato de
/cms/hub/presentacion.json y tampoco lleva datos internos (briefs, notas por validar,
contactos de aliados, banco de temas).

Uso: <python con backend/requirements-cms.txt> deploy/build_estrategia.py [semilla.json]
"""
import json
import pathlib
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'backend'))
import cms_hub as hub  # noqa: E402
import hub_seed  # noqa: E402

SEMILLA = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / 'estrategia-contenido' / 'datos' / 'parrilla-piloto.json'
SALIDA = RAIZ / 'sitio' / 'estrategia' / 'data.json'


def main():
    data = json.loads(SEMILLA.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='cisne-tablero-') as tmp:
        hub_seed.cargar(tmp, data)
        with hub.connect(pathlib.Path(tmp) / 'hub.sqlite') as con:
            datos = hub.construir_presentacion(con)
    datos['tipo'] = 'semilla'  # el tablero indica que no es una instantánea publicada desde el Hub
    datos['publicado_at'] = None
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    texto = json.dumps(datos, ensure_ascii=False)
    for prohibido in ('"brief"', '"por_validar"', '"contacto"', '"temas"'):
        assert prohibido not in texto, f'data.json no debe llevar {prohibido}'
    print(f'{SALIDA.relative_to(RAIZ)}: {len(datos["piezas"])} piezas, {SALIDA.stat().st_size:,} bytes')


if __name__ == '__main__':
    main()
