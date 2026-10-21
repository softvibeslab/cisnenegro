"""Reprograma la parrilla del piloto de Cisne Negro: arranca el sábado 24 de octubre
(una semana antes de Halloween) y aprovecha las fechas de temporada.

Lee la v1 (historico/parrilla-piloto-v1-19oct.json) y escribe parrilla-piloto.json.
Uso: python3 historico/reprogramar-v2-24oct.py estrategia-contenido/datos
Es determinista: correrlo dos veces da el mismo resultado.
"""
import copy
import json
import sys
from datetime import date, timedelta
from pathlib import Path

DATOS = Path(sys.argv[1])
V1 = DATOS / 'historico' / 'parrilla-piloto-v1-19oct.json'
SALIDA = DATOS / 'parrilla-piloto.json'

d = json.loads(V1.read_text(encoding='utf-8'))
P = {p['clave']: p for p in d['piezas']}
SECC = {s['clave']: s for s in d['secciones']}

# Textos COFEPRIS estándar, tomados de piezas existentes.
COF_CERV = P['2026-10-19-produccion-r1']['brief'].split('COFEPRIS:', 1)[1]
COF_CERV = 'COFEPRIS:' + COF_CERV
COF_SIN = 'COFEPRIS:' + P['2026-10-22-gbp-pet-friendly']['brief'].split('COFEPRIS:', 1)[1]
HORARIO_GBP = ('Horario: martes a jueves 16–22 h, viernes y sábado 16–23:30 h, domingo 14–19 h; '
               'lunes cerrado por producción.')
GBP_ALCOHOL = ('Política de Google para publicaciones de alcohol en GBP (por verificar): '
               'mantener las publicaciones de GBP sin cerveza')


def iso(s):
    return date.fromisoformat(s)


def campos_texto(p):
    yield p, 'titulo'
    yield p, 'brief'
    yield p, 'copy_base'
    for v in p['variantes']:
        yield v, 'copy'
        if 'titulo' in v:
            yield v, 'titulo'


def rep(p, viejo, nuevo, obligatorio=True):
    """Reemplaza texto en título, brief, copy y variantes."""
    hits = 0
    for obj, k in campos_texto(p):
        if viejo in obj[k]:
            obj[k] = obj[k].replace(viejo, nuevo)
            hits += 1
    if obligatorio and not hits:
        raise SystemExit(f'{p["clave"]}: no se encontró «{viejo[:60]}»')


def rep_brief(p, viejo, nuevo):
    if viejo not in p['brief']:
        raise SystemExit(f'{p["clave"]}: brief sin «{viejo[:60]}»')
    p['brief'] = p['brief'].replace(viejo, nuevo)


def antes_de_cofepris(p, texto):
    """Inserta una frase en el brief justo antes del bloque COFEPRIS."""
    cuerpo, cof = p['brief'].split('COFEPRIS:', 1)
    p['brief'] = cuerpo.rstrip() + ' ' + texto + ' COFEPRIS:' + cof


def mover(clave, fecha, sufijo, prueba='igual', campana='igual'):
    """Cambia la fecha (variantes incluidas, conservando su desfase) y la clave."""
    p = P.pop(clave)
    delta = iso(fecha) - iso(p['fecha'])
    p['fecha'] = fecha
    for v in p['variantes']:
        v['fecha'] = (iso(v['fecha']) + delta).isoformat()
    if prueba != 'igual':
        p['prueba'] = prueba
    if campana != 'igual':
        p['campana'] = campana
    p['clave'] = f'{fecha}-{sufijo}'
    if p['clave'] in P:
        raise SystemExit(f'Clave duplicada: {p["clave"]}')
    P[p['clave']] = p
    return p


def a_banco(clave, seccion, tema):
    """Saca una pieza de la parrilla y deja su idea en el banco de temas de la sección."""
    P.pop(clave)
    temas = SECC[seccion].setdefault('temas', [])
    if tema not in temas:
        temas.append(tema)


def nueva(clave, **campos):
    base = {
        'clave': clave, 'campana': None, 'estado': 'borrador', 'prueba': None, 'aliado': None,
        'por_validar': [],
    }
    base.update(campos)
    if clave in P:
        raise SystemExit(f'Clave duplicada: {clave}')
    P[clave] = base
    return base


def attrs(**kw):
    a = {'gancho': 'Agenda', 'cerveza_destacada': None, 'personas_en_cuadro': 'Ninguna',
         'requiere_grabacion': False, 'con_coautor': False, 'objetivo_pauta': 'Sin pauta',
         'presupuesto_pauta': 0, 'locacion': 'Diseño (sin locación)', 'habla_de_cerveza': False}
    a.update(kw)
    return a


# ---------------------------------------------------------------- piloto y campañas
d['version'] = 2
d['generado'] = '2026-10-10'
d['piloto'] = {
    'inicio': '2026-10-24', 'fin': '2026-11-29', 'zona': 'America/Mexico_City',
    'nombre': 'Piloto de temporada: Halloween → Aniversario III', 'semanas': 5,
    'nota': ('Arranca el sábado 24 de octubre, una semana antes de Halloween (antes: lunes 19). '
             'Fechas de temporada: Halloween (sáb 31-oct), Día de Muertos (1 y 2-nov), Día Internacional '
             'de la Stout (jue 5-nov), Buen Fin y puente (13 al 16-nov, por confirmar), Aniversario Año III '
             '(supuesto sáb 21-nov). El 20 de noviembre no se asocia a la cerveza.'),
}
CAMP = {c['clave']: c for c in d['campanas']}
CAMP['halloween-2026'].update({
    'inicio': '2026-10-24', 'fin': '2026-10-31',
    'objetivo': ('Semana de cuenta regresiva (24 al 31 de octubre) hacia el sábado 31: concurso de disfraces si '
                 'el cliente lo confirma, etiquetas «disfrazadas», barril con calabaza y guiños de temporada en '
                 'comida y mascotas. La palabra Halloween nunca va en la misma frase que la cerveza.'),
})
CAMP['dia-de-muertos-2026'].update({
    'inicio': '2026-10-30', 'fin': '2026-11-02', 'por_confirmar': True,
    'objetivo': ('Ofrenda de los perrhijos en la terraza (sin cerveza; las fotos se reciben del 30 de octubre '
                 'al 1 de noviembre) y, solo con visto bueno legal, la ofrenda a las etiquetas que se fueron. '
                 'El Lunes de producción del 2 de noviembre no se relaciona con la festividad.'),
    'nota': ('La ofrenda de mascotas depende de que el cliente la acepte. La de etiquetas pasa por la consulta '
             'legal COFEPRIS antes de aprobarse.'),
})
d['campanas'].append({
    'clave': 'dia-de-la-stout-2026', 'nombre': 'Día Internacional de la Stout',
    'inicio': '2026-11-05', 'fin': '2026-11-05',
    'objetivo': ('Efeméride cervecera del primer jueves de noviembre: el Maridaje del finde se dedica a Agua Puerca '
                 '(Imperial Stout) con su pareja oficial, la Tlayuda de Picaña Adobada.'),
    'por_confirmar': False,
    'nota': ('Es una fecha del gremio cervecero, no una celebración cívica ni religiosa. Aun así, la mención va en '
             'su propia frase y se confirma con la consulta legal.'),
})
CAMP['buen-fin-2026']['nota'] = ('Fechas oficiales del Buen Fin 2026 por confirmar; las de esta campaña son '
                                 'tentativas e incluyen el puente del lunes 16 (feriado).')
CAMP['aniversario-iii-2026'].update({'inicio': '2026-11-06', 'fin': '2026-11-23'})
orden = ['halloween-2026', 'dia-de-muertos-2026', 'dia-de-la-stout-2026', 'buen-fin-2026', 'aniversario-iii-2026']
d['campanas'] = sorted(d['campanas'], key=lambda c: orden.index(c['clave']))

# ---------------------------------------------------------------- Lunes de producción (R1 26-oct)
p = mover('2026-10-19-produccion-r1', '2026-10-26', 'produccion-r1')
rep_brief(p, 'Grabar en lote las tomas de los lunes 19 y 26.',
          'Grabar en lote las tomas de los lunes 26 de octubre y 2 de noviembre.')
p = mover('2026-10-26-produccion-r2', '2026-11-02', 'produccion-r2')
antes_de_cofepris(p, 'Es lunes 2 de noviembre: cocción normal; no se relaciona con Día de Muertos en texto ni en imagen.')
p = mover('2026-11-02-produccion-r3', '2026-11-09', 'produccion-r3')
rep_brief(p, ' Cocción normal del lunes; no se relaciona con Día de Muertos en texto ni en imagen.',
          ' Ese mismo lunes se graba el reel de «Quién te sirve» (el 16 es feriado).')
a_banco('2026-11-09-produccion', 'lunes-de-produccion',
        '¿A dónde va el bagazo? El grano usado se dona como alimento para animales de granja')

# ---------------------------------------------------------------- Barril de la semana (R1 27-oct)
p = mover('2026-10-27-barril-r2', '2026-10-27', 'barril-r1', prueba='R1')
p = mover('2026-10-20-barril-r1', '2026-11-03', 'barril-r2', prueba='R2')
antes_de_cofepris(p, 'Plan B si R1 no cumplió: publicar a las 13:30 o cambiar la portada a la lata.')
p = mover('2026-11-10-barril', '2026-11-10', 'barril-r3', prueba='R3')
rep_brief(p, ' Sección vigente por confirmar.',
          ' Plan B si R2 no cumplió: publicar a las 13:30 o cambiar la portada a la lata.')
a_banco('2026-11-17-barril', 'barril-de-la-semana',
        'Henry IX: la única de la barra que se sirve en 14 oz (estilo por validar)')
p = mover('2026-11-03-barril-r3', '2026-11-17', 'barril', prueba=None)
rep_brief(p, ' Plan B si R2 no cumplió: publicar a las 13:30 o cambiar portada a la lata.',
          ' Semana del puente y del Buen Fin: en el aviso del Canal la lámina de la lata para llevar va primero. '
          'Sección vigente por confirmar.')

# ---------------------------------------------------------------- ¡Cuéntalo en el Cisne! (R1 28-oct)
p = mover('2026-10-28-cuentalo-r2', '2026-10-28', 'cuentalo-r1', prueba='R1', campana='halloween-2026')
rep_brief(p, ' Plan B del método: si R1 no cumplió, cambiar a plantilla «reel dibujado» con el video de cómo se hizo '
             'la ilustración (IG 2025-02-26).',
          ' Semana de Halloween: el gancho de miedo («Les tengo miedo a las stouts») va en su propia frase, '
          'separado del nombre de la cerveza.')
rep(p, '«No me gustan las stouts.» ¿A poco sí, pa\'? 🙂‍↕️', '«Les tengo miedo a las stouts.» 👻\n¿A poco sí, pa\'?',
    obligatorio=False)
rep(p, 'Así le decimos a quien jura que un estilo no es lo suyo.',
    'Así le decimos a quien jura que un estilo le da miedo.', obligatorio=False)
rep(p, 'jura que no le gustan las stouts', 'jura que les tiene miedo a las stouts', obligatorio=False)
p = mover('2026-10-21-cuentalo-r1', '2026-11-04', 'cuentalo-r2', prueba='R2')
antes_de_cofepris(p, 'Plan B si R1 no cumplió: cambiar a plantilla «reel dibujado» o publicar a las 13:00.')
p = mover('2026-11-04-cuentalo-r3', '2026-11-11', 'cuentalo-r3')

# ---------------------------------------------------------------- Maridaje del finde (R1 29-oct)
p = mover('2026-11-19-maridaje', '2026-10-29', 'maridaje-r1', prueba='R1', campana='halloween-2026')
rep(p, 'por eso salen negros.', 'por eso salen negros.\nSon los únicos de la carta que no necesitan disfraz esta semana. 🎃')
rep_brief(p, ' Sección vigente por confirmar.',
          ' Semana de Halloween: el guiño va en los camarones, nunca en la cerveza. Si la ficha de Tropkiller no '
          'queda validada a tiempo, se publica la pareja sin la lámina de ficha.')
p = mover('2026-10-22-maridaje-r1', '2026-11-05', 'maridaje-r2', prueba='R2', campana='dia-de-la-stout-2026')
rep(p, 'Maridaje del finde: Agua Puerca + Tlayuda de Picaña Adobada', 'Día de la Stout: Agua Puerca + Tlayuda de Picaña Adobada')
p['titulo'] = 'Maridaje del finde en el Día Internacional de la Stout: Agua Puerca + Tlayuda de Picaña Adobada'
p['copy_base'] = p['copy_base'].replace(
    'Día de la Stout: Agua Puerca + Tlayuda de Picaña Adobada. 🖤',
    'Hoy es el Día Internacional de la Stout. 🖤\nEl maridaje del finde es Agua Puerca + Tlayuda de Picaña Adobada.')
antes_de_cofepris(p, 'Jueves 5 de noviembre, Día Internacional de la Stout (primer jueves de noviembre): la efeméride '
                     'va en la primera frase y sola. Plan B si R1 no cumplió: publicar a las 17:00 o cambiar la '
                     'portada a foto del platillo.')
p['por_validar'].append('Consulta legal: mención del Día Internacional de la Stout junto a la marca')
for v in p['variantes']:
    if v['copy'].startswith('Día de la Stout: '):
        v['copy'] = v['copy'].replace('Día de la Stout: Agua Puerca + Tlayuda de Picaña Adobada. 🖤',
                                      'Hoy es el Día Internacional de la Stout. 🖤\nEl maridaje del finde es Agua Puerca + Tlayuda de Picaña Adobada.')
    elif 'Día Internacional de la Stout' not in v['copy']:
        v['copy'] = 'Hoy es el Día Internacional de la Stout. 🖤\n' + v['copy']
p = mover('2026-11-05-maridaje-r3', '2026-11-12', 'maridaje-r3')
rep_brief(p, '(Boca Negra + Sándwich de Suadero o Tropkiller + Camarones Piedra)',
          '(Boca Negra + Sándwich de Suadero o ¿A poco sí pa\'? + Palomitas de Coliflor)')
p = mover('2026-10-29-maridaje-r2', '2026-11-19', 'maridaje', prueba=None)
antes_de_cofepris(p, 'Semana del Año III: sección vigente por confirmar.')
a_banco('2026-11-26-maridaje', 'maridaje-del-finde',
        '¡Alarma! + Hamburguesa De Costilla de Res: lo tatemado contra el amargor (propuesta, por validar)')
p = mover('2026-11-12-maridaje', '2026-11-26', 'maridaje')

# ---------------------------------------------------------------- Reseña en voz alta (R1 25-oct)
p = mover('2026-11-01-resena-r2', '2026-11-08', 'resena-r2')
a_banco('2026-11-08-resena-r3', 'resena-en-voz-alta',
        '«Casi cada semana puedes encontrar algo nuevo» (validar cuántos barriles hay hoy)')
p = mover('2026-11-15-resena', '2026-11-15', 'resena-r3', prueba='R3')
rep_brief(p, ' Sección vigente por confirmar.',
          ' Plan B si R2 no cumplió: cambiar a carrusel con dos reseñas. Cae en el fin de semana del Buen Fin: '
          'no ligar la reseña a ninguna promoción.')

# ---------------------------------------------------------------- Agenda Cisne
p = mover('2026-10-23-agenda-r1', '2026-10-25', 'agenda-r1')
p['hora'] = '19:00'
p = P['2026-10-30-agenda-r2']
OFRENDA_LINEA = 'Y del viernes 30 al domingo 1, la terraza tiene ofrenda para los perrhijos: trae la foto de tu mascota. 🐾'
p['copy_base'] = p['copy_base'] + '\n' + OFRENDA_LINEA
for v in p['variantes']:
    if v['formato'] in ('ig-imagen', 'fb-post'):
        v['copy'] = v['copy'] + '\n' + OFRENDA_LINEA
    elif v['formato'] == 'wa-aviso':
        v['copy'] = v['copy'] + ' Y ya está la ofrenda de los perrhijos en la terraza: trae la foto de tu mascota. 🐾'
antes_de_cofepris(p, 'Incluye la convocatoria a la ofrenda de los perrhijos (Día de Muertos, sin cerveza).')
p['por_validar'].append('Que el cliente acepte la ofrenda de mascotas en la terraza del 30 de octubre al 1 de noviembre')
p = P['2026-10-31-halloween-stories']
antes_de_cofepris(p, 'Una story recuerda la ofrenda de los perrhijos en la terraza (fotos hasta el domingo 1).')
p = P['2026-11-13-buen-fin']
p['por_validar'].append('Si el Cisne abre el lunes 16 (feriado): avisarlo aquí sin mencionar la Revolución')

# ---------------------------------------------------------------- GBP / Plato que manda
a_banco('2026-10-29-gbp-ceviche', 'el-plato-que-manda', 'Ceviche de Atún: «El ceviche es fenomenal» (reseña de Google)')
P.pop('2026-10-22-gbp-pet-friendly')

# ---------------------------------------------------------------- Si te gusta… (R1 18-nov)
p = mover('2026-11-11-si-te-gusta-r1', '2026-11-18', 'si-te-gusta-r1')
p = mover('2026-11-18-si-te-gusta-r2', '2026-11-25', 'si-te-gusta-r2')
a_banco('2026-11-25-si-te-gusta-r3', 'si-te-gusta',
        'Por fruta: una fruta por lámina y el barril que la trae (R3 en diciembre)')
SECC['si-te-gusta']['periodicidad'] = 'Semanal en prueba (miércoles 18 y 25 de noviembre; R3 en diciembre)'


# ---------------------------------------------------------------- Piezas nuevas
nueva('2026-10-24-halloween-arranque',
      titulo='Faltan 7 noches: arranca la semana de Halloween',
      seccion='agenda-cisne', plantilla='stories-en-vivo', campana='halloween-2026',
      fecha='2026-10-24', hora='17:00', objetivo='comunidad',
      brief=('Solo stories (sábado sin feed). Arranque del piloto: sticker de cuenta regresiva a «Halloween en el '
             'Cisne · sáb 31», foto de la pluma del Cisne con una calabaza sobre la barra (sin vasos ni latas '
             'abiertas) y encuesta «¿Vienes disfrazado?» (Obvio / Ya veremos). Aviso en el Canal de WhatsApp con '
             'la fecha. Mañana domingo sale el teaser de las etiquetas disfrazadas. ' + COF_CERV),
      copy_base=('Faltan 7 noches para Halloween en el Cisne. 🎃\n'
                 'Las etiquetas ya están escogiendo disfraz: mañana les enseñamos quién se disfrazó de qué.\n\n'
                 'EVITE EL EXCESO.'),
      por_validar=['Que el cliente confirme Halloween 2026 el sábado 31 de octubre y el concurso de disfraces'],
      atributos=attrs(gancho='Pregunta', locacion='Barra', habla_de_cerveza=True, requiere_grabacion=True),
      variantes=[
          {'canal': 'ig', 'formato': 'ig-story',
           'copy': 'Faltan 7 noches para Halloween en el Cisne 🎃 ¿Vienes disfrazado? EVITE EL EXCESO.',
           'hashtags': [], 'fecha': '2026-10-24', 'hora': '17:00'},
          {'canal': 'wa', 'formato': 'wa-aviso',
           'copy': ('🎃 Sábado 31 de octubre: Halloween en el Cisne. Faltan 7 noches; detalles del concurso de '
                    'disfraces el viernes 30. Rafael Vega Sánchez 110, Col. Periodistas.'),
           'hashtags': [], 'fecha': '2026-10-24', 'hora': '13:00'},
      ])

nueva('2026-10-29-gbp-halloween',
      titulo='GBP: Halloween en Cisne Negro (evento)',
      seccion='agenda-cisne', plantilla='agenda-evento', campana='halloween-2026',
      fecha='2026-10-29', hora='12:00', objetivo='visita',
      brief=('Publicación de GBP tipo evento para el sábado 31, con foto real de la terraza o la fachada decorada '
             '(sin vasos, barriles ni latas). Esa semana subir también 5–10 fotos reales a la ficha, incluida la '
             'decoración de temporada. Sustituye en este jueves al GBP del Ceviche de Atún, que pasa al banco de '
             'temas. ' + COF_SIN),
      copy_base=('Halloween en Cisne Negro: sábado 31 de octubre, con concurso de disfraces [por confirmar: hora y '
                 'premio] y cocina abierta con la carta de siempre. Mascotas bienvenidas, también disfrazadas. 🐶🎃 '
                 'Toca «Cómo llegar» para la ruta a Rafael Vega Sánchez 110, Col. Periodistas, Pachuca. ' + HORARIO_GBP),
      por_validar=['Que el cliente confirme Halloween 2026 el sábado 31 de octubre y el concurso de disfraces',
                   'Hora del concurso y premio sin alcohol', GBP_ALCOHOL],
      atributos=attrs(locacion='Fachada / calle'),
      variantes=[{'canal': 'gbp', 'formato': 'gbp-publicacion', 'copy': None, 'hashtags': [],
                  'fecha': '2026-10-29', 'hora': '12:00'}])
P['2026-10-29-gbp-halloween']['variantes'][0]['copy'] = P['2026-10-29-gbp-halloween']['copy_base']

nueva('2026-11-01-perrhijos-ofrenda',
      titulo='Perrhijos del Cisne: la ofrenda de la terraza',
      seccion='perrhijos-del-cisne', plantilla='recap-evento', campana='dia-de-muertos-2026',
      fecha='2026-11-01', hora='13:00', objetivo='comunidad',
      brief=('Carrusel de 6 láminas: la ofrenda armada en la terraza (papel picado, cempasúchil, veladoras LED, '
             'plato de agua y croquetas) con las fotos de mascotas que la comunidad dejó del viernes 30 al domingo 1; '
             'una lámina por historia (nombre de la mascota y una frase de su humano, con permiso). Sin vasos, '
             'latas ni barriles en cuadro y sin personas identificables. La convocatoria sale en la agenda del '
             'viernes 30 y en las stories del sábado 31. Es la pieza de Día de Muertos sin cerveza: no depende de '
             'la consulta legal de la ofrenda de etiquetas. Ocupa el domingo de Reseña en voz alta (la R2 pasa al '
             'domingo 8). También sale en GBP. ' + COF_SIN),
      copy_base=('En la terraza del Cisne pusimos una ofrenda para quienes nos acompañaron en cuatro patas. 🐾🕯️\n'
                 'Estas son las fotos que nos dejaron este fin de semana: [por confirmar: nombres de las mascotas, '
                 'con permiso de sus humanos].\n'
                 'Gracias por compartirlos con nosotros. Si el tuyo está aquí, etiquétanos en tu story.'),
      por_validar=['Que el cliente acepte la ofrenda de mascotas en la terraza del 30 de octubre al 1 de noviembre',
                   'Permiso de cada humano para publicar la foto y el nombre de su mascota',
                   'Quién arma la ofrenda y con qué presupuesto (cempasúchil, papel picado, veladoras LED)',
                   GBP_ALCOHOL],
      atributos=attrs(gancho='Revelación', personas_en_cuadro='Mascotas', requiere_grabacion=True,
                      locacion='Terraza'),
      variantes=[
          {'canal': 'ig', 'formato': 'ig-carrusel', 'copy': None,
           'hashtags': ['#perrhijosdelcisne', '#petfriendlypachuca', '#pachuca', '#cisnenegro'],
           'fecha': '2026-11-01', 'hora': '13:00'},
          {'canal': 'fb', 'formato': 'fb-album', 'copy': None, 'hashtags': ['#pachuca', '#cisnenegro'],
           'fecha': '2026-11-01', 'hora': '13:00'},
          {'canal': 'threads', 'formato': 'threads-imagen',
           'copy': 'Este fin de semana la terraza del Cisne tuvo ofrenda para los perrhijos que ya no están. 🐾🕯️',
           'hashtags': [], 'fecha': '2026-11-01', 'hora': '13:00'},
          {'canal': 'gbp', 'formato': 'gbp-publicacion',
           'copy': ('Este fin de semana la terraza de Cisne Negro tiene ofrenda para las mascotas de nuestra '
                    'comunidad. 🐾 Mascotas bienvenidas todo el año. Toca «Cómo llegar» para la ruta a Rafael Vega '
                    'Sánchez 110, Col. Periodistas, Pachuca. ' + HORARIO_GBP),
           'hashtags': [], 'fecha': '2026-11-01', 'hora': '12:00'},
      ])
for v in P['2026-11-01-perrhijos-ofrenda']['variantes']:
    if v['copy'] is None:
        v['copy'] = P['2026-11-01-perrhijos-ofrenda']['copy_base']

# ---------------------------------------------------------------- Secciones y KPIs
if 'Ofrenda de los perrhijos (Día de Muertos)' not in SECC['perrhijos-del-cisne']['temas']:
    SECC['perrhijos-del-cisne']['temas'].append('Ofrenda de los perrhijos (Día de Muertos)')
efem = SECC['efemerides-cisne'].setdefault('temas', [])
for t in ('Día Internacional de la Stout (primer jueves de noviembre)',
          'Halloween: semana de cuenta regresiva (sin la palabra Halloween junto a la cerveza)'):
    if t not in efem:
        efem.append(t)

piezas = sorted(P.values(), key=lambda x: (x['fecha'], x['hora'] or '', x['clave']))
tiktoks = sum(1 for x in piezas for v in x['variantes'] if v['canal'] == 'tiktok')
for k in d['estrategia']['kpis']:
    if k['clave'] == 'tiktok_reactivado':
        k['meta'] = f'≥12 videos (el piloto programa {tiktoks}); mediana ≥900 vistas'
d['piezas'] = piezas

# ---------------------------------------------------------------- Validaciones
ini, fin = d['piloto']['inicio'], d['piloto']['fin']
claves_camp = {c['clave'] for c in d['campanas']}
for x in piezas:
    assert ini <= x['fecha'] <= fin, x['clave']
    assert x['clave'].startswith(x['fecha']), x['clave']
    assert x['campana'] in claves_camp | {None}, x['clave']
    for v in x['variantes']:
        assert v['copy'], x['clave']
        assert abs((iso(v['fecha']) - iso(x['fecha'])).days) <= 1, (x['clave'], v['fecha'])
    if x['atributos'].get('habla_de_cerveza'):
        assert 'EVITE EL EXCESO' in x['copy_base'], x['clave']
    if iso(x['fecha']).weekday() == 5:  # sábado: solo stories
        assert all(v['formato'] in ('ig-story', 'wa-aviso') for v in x['variantes']), x['clave']

SALIDA.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'{len(piezas)} piezas · {piezas[0]["fecha"]} → {piezas[-1]["fecha"]} · TikTok programados: {tiktoks}')
