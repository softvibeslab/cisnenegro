#!/usr/bin/env python3
"""Audiencia de @oktoberfestjabonera → insumos para buyer personas de Cisne Negro.

Lee (crudos, fuera de git, con usernames → NO se copian a la salida):
  scraping/raw/jabonera-20261008/profile-jabonera.json     perfil (apify/instagram-profile-scraper)
  scraping/raw/jabonera-20261008/followers-jabonera.json   700 de 1,550 seguidores con bio
                                                           (scraping_solutions/instagram-scraper-followers-following, sin login)
  scraping/raw/jabonera-20261008/following-jabonera.json   225 de 258 seguidos con bio (mismo actor)
  scraping/raw/jabonera-20261008/posts-jabonera.json       50 de 66 posts (apify/instagram-post-scraper)
  scraping/raw/jabonera-20261008/comments-jabonera.json    comentarios completos de 3 posts (apify/instagram-comment-scraper)
  scraping/raw/jabonera-20261008/profiles-aliados.json     6 cuentas de aliados (apify/instagram-profile-scraper)
  scraping/raw/ig-posts-full-20261006.json                 200 posts de @cisnenegro.mx (comentaristas → solapamiento)
  contenido/google-maps/resenas.csv                        69 reseñas de Google de Cisne Negro

Escribe: estrategia-contenido/datos/audiencia-jabonera.json (SOLO agregados).
Privacidad (LFPDPPP): la salida no contiene usernames ni nombres de personas físicas.
Solo se nombran cuentas clasificadas como negocio/creador, públicas, o acreditadas
públicamente como participantes del evento (coautoría/etiqueta/mención en posts del festival).

Todas las clasificaciones son INFERENCIAS por palabras clave (bio, nombre, usuario);
cada bloque del JSON indica el método. Uso: python3 audiencia_jabonera.py
"""
import csv, json, re, statistics as st, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]          # cisne-negro-cerveceria/
RAW = BASE / "scraping/raw/jabonera-20261008"
OUT = BASE / "estrategia-contenido/datos/audiencia-jabonera.json"
SELF = "oktoberfestjabonera"


def load(p):
    return json.load(open(p, encoding="utf-8"))


def norm(s):
    """minúsculas, sin acentos y con letras 'decorativas' (𝐏𝐚𝐜𝐡𝐮𝐜𝐚) llevadas a ASCII."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def rx(*words):
    return re.compile("|".join(words))


def pct(n, d):
    return round(100 * n / d, 1) if d else None


# ---------------------------------------------------------------- diccionarios
# Señales de cuenta de NEGOCIO (establecimiento/marca)
NEG = rx(r"restaurante?s?\b", r"cerveceria", r"brew", r"taproom", r"biergarten", r"\bbar\b", r"\bcafe\b",
         r"cafeteria", r"coffee", r"panaderia", r"bakery", r"reposteria", r"pasteleria", r"\btienda\b", r"\bshop\b",
         r"\bstore\b", r"boutique", r"pedidos", r"envios", r"a domicilio", r"reserv", r"\bl-s\b", r"\bl-v\b",
         r"lun(es)? a ", r"mar(tes)? a ", r"sucursal", r"cotizacion", r"\bcitas\b", r"studio\b", r"\bestudio\b",
         r"salon", r"barberia", r"festival", r"banquet", r"catering", r"distribu", r"importadora", r"insumos",
         r"\bapp\b", r"oficial\b", r"official\b", r"\bcava\b", r"\bbodega\b", r"buffet", r"loncheria", r"poke",
         r"hamburguesas", r"tacos artesanales", r"espacio vecinal", r"sede de", r"agua purificada", r"agua natural",
         r"inventarios", r"english classes", r"cocina de", r"cocina mexicana", r"patio gastronomico", r"\bclub de\b",
         r"pulque", r"tattoo|tatuaje", r"nail ?art|manicura", r"ceramics|porcelana", r"zapatos", r"wine coolers",
         r"hybrid studio|crossfit\b.*pachuca", r"estudio floral", r"creadores de contenido", r"ordena dando",
         r"conciertos", r"lucha libre", r"recorridos guiados")
# Señales de CREADOR (persona-marca: foodie, DJ, artista, chef mediático, músico, fotógrafo)
CRE = rx(r"foodie", r"food ?blog", r"food writer", r"cronista", r"critica", r"periodismo", r"\bguia\b",
         r"resen(a|as|ando)", r"colabs?\b", r"colaboraciones", r"collabs?\b", r"booking", r"info agenda", r"\bdj\b",
         r"selector", r"producer", r"musician", r"\bmusico\b", r"cantante", r"\bbanda\b", r"band\b", r"brass",
         r"balkan", r"artista", r"\bartist\b", r"ilustrador", r"fotografo", r"photograph", r"filmmaker",
         r"cocinero", r"\bchef\b", r"sommelier", r"cicerone", r"beverage educator", r"creador de contenido",
         r"influencer", r"content creator", r"tatuador", r"bandcamp", r"youtube", r"podcast", r"coach",
         r"catadores", r"recomendaciones", r"donde comer")

# Categoría (para negocios/creadores)
CAT = [
    ("cerveza_vino_destilados", rx(r"cervec", r"brew", r"beer", r"taproom", r"biergarten", r"cerveza", r"\bvino",
                                  r"wine", r"\bcava\b", r"mezcal", r"pulque", r"cocktail", r"coctel", r"mixolog",
                                  r"sommelier", r"cicerone", r"bodega", r"winelover", r"lupul")),
    ("musica_dj", rx(r"\bdj\b", r"music", r"musica", r"selector", r"techno", r"(?<!thai )house", r"producer", r"band\b",
                     r"banda", r"brass", r"balkan", r"concierto", r"bandcamp", r"ritmo", r"vinyl", r"electro")),
    ("eventos_espacios_cultura", rx(r"festival", r"evento", r"event planner", r"espacio", r"experiencias",
                                    r"lucha libre", r"cultura", r"sede")),
    ("medio_foodie_creador", rx(r"foodie", r"food ?blog", r"food writer", r"cronista", r"critica", r"periodismo",
                                r"\bguia\b", r"resen", r"revista", r"cronicas? gastronom", r"comer\b", r"tragon", r"garnach",
                                r"taquivora", r"food & travel", r"documentando", r"comidilla", r"fooder")),
    ("cafe_panaderia_postres", rx(r"\bcafe", r"coffee", r"barista", r"panaderia", r"bakery", r"reposteria",
                                  r"pasteleria", r"postre", r"gelato", r"helado", r"brunch", r"\bpan\b")),
    ("restaurante_comida", rx(r"restaurant", r"cocina", r"taco", r"pizza", r"burger", r"hamburguesa", r"marisco",
                              r"paella", r"poke", r"sandwich", r"chapata", r"buffet", r"banquet", r"catering",
                              r"\bchef\b", r"cocinero", r"suadero", r"loncheria", r"salchicha", r"bistro",
                              r"patio gastronomico")),
    ("arte_diseno_foto", rx(r"\bart", r"artista", r"ilustr", r"disen", r"design", r"foto", r"photo", r"film",
                            r"tattoo", r"tatu", r"ceram", r"porcelana", r"vj")),
    ("bienestar_fitness", rx(r"gym", r"crossfit", r"pilates", r"yoga", r"fitness", r"nutri", r"wellness", r"trail",
                             r"running", r"hyrox", r"adelgaza")),
    ("belleza_moda", rx(r"nail", r"unas", r"salon", r"barber", r"zapato", r"moda", r"boutique", r"belleza")),
    ("servicios_otros", rx(r"agua", r"inventario", r"\bapp\b", r"consult", r"english", r"inmobili", r"abogad",
                           r"insumos", r"envios", r"medico", r"veterinari")),
]

# Intereses (todas las cuentas; multi-etiqueta) — palabras/emojis en bio + nombre
INT = {
    "cerveza_artesanal": rx(r"cerveza", r"\bbeer", r"cheve", r"chela", r"lupul", r"\bipa\b", r"stout", r"craft",
                            r"brew", r"cicerone", r"\bprost\b", r"🍺", r"🍻", r"taproom"),
    "vino_destilados_cocteleria": rx(r"\bvino", r"wine", r"mezcal", r"cocktail", r"coctel", r"sommelier", r"wset",
                                     r"whisk", r"tequila", r"🍷", r"🍸", r"mixolog", r"pulque"),
    "gastronomia_foodie": rx(r"foodie", r"\bfood", r"comida", r"cocina", r"cocinero", r"\bchef\b", r"gastronom",
                             r"\bcomer\b", r"\bnam\b", r"taco", r"pizza", r"tragon", r"garnach", r"🍔", r"🌮", r"🍕",
                             r"burger", r"🍽"),
    "cafe": rx(r"\bcafe\b", r"coffee", r"barista", r"cafeina", r"☕"),
    "musica_conciertos": rx(r"music", r"musica", r"\bdj\b", r"melomano", r"concierto", r"\brock", r"techno",
                            r"\bhouse\b", r"vinyl", r"vinilo", r"\bband\b", r"guitar", r"\bpunk", r"\bjazz",
                            r"metal", r"cantante", r"\bmusico", r"🎧", r"🎸", r"🎶", r"🎵", r"💿", r"🥁", r"ritmo",
                            r"riddim", r"selector", r"bandcamp"),
    "motos": rx(r"\bmoto", r"biker", r"rider", r"harley", r"motocicl", r"🏍"),
    "mascotas": rx(r"perr", r"\bdog", r"\bgato", r"\bgatos\b", r"\bcats?\b", r"mascota", r"animalista",
                   r"\bpet\b", r"veterinari", r"🐶", r"🐕", r"🐈", r"🐾", r"🐱", r"animal lover"),
    "futbol_deporte_espectaculo": rx(r"futbol", r"soccer", r"\btuzo", r"⚽", r"\bnfl\b", r"beisbol", r"⚾",
                                     r"lucha libre", r"\bf1\b"),
    "fitness_outdoor": rx(r"\bgym", r"crossfit", r"yoga", r"yogui", r"pilates", r"fitness", r"running", r"\btrail",
                          r"hyrox", r"ciclis", r"\bbici", r"🏋", r"🧘", r"jiu", r"\bbjj\b", r"senderismo", r"hiking",
                          r"🥾", r"🚴", r"🏊", r"triatl", r"marat", r"escalad", r"🧗", r"vinyasa"),
    "arte_diseno_creativos": rx(r"\barte\b", r"\bart\b", r"artista", r"\bartist", r"ilustr", r"disen", r"design",
                                r"pint", r"tattoo", r"tatu", r"ceram", r"fotograf", r"photo", r"escritor", r"poes",
                                r"\bcine", r"film", r"🎨", r"📷", r"📸", r"motion graphics", r"arquitect", r"architect"),
    "estudiantes_universidad": rx(r"\buaeh\b", r"\btec\b", r"itesm", r"tec de monterrey", r"\bprepa", r"universidad",
                                  r"\bunam\b", r"la salle", r"\bipn\b", r"politecnica", r"estudiante", r"student",
                                  r"\blic\.", r"\bing\.", r"\bupp\b", r"\buvm\b", r"anahuac", r"ibero", r"\bucc\b"),
    "familia_padres": rx(r"\bmama\b", r"mama de", r"\bmom\b", r"mom life", r"\bpapa\b", r"\bdad\b", r"padre de",
                         r"mis hijos", r"esposa", r"esposo", r"👶", r"👨‍👩", r"👩‍👧", r"👨‍👧", r"soccermom", r"soccer.?mom"),
    "emprendedor_negocios": rx(r"emprend", r"\bceo\b", r"founder", r"fundador", r"propietari", r"owner", r"duen[oa]",
                               r"negocio", r"business", r"marketing", r"consultor", r"empresari"),
    "viajes": rx(r"viaj", r"travel", r"\btrip", r"✈", r"🌎", r"🌍", r"nomad", r"mochil", r"🏝", r"wanderlust"),
    "eventos_fiesta": rx(r"fiesta", r"party", r"\bevento", r"\brave\b", r"festival", r"festivities", r"🪩", r"🎉"),
    "salud_profesiones": rx(r"medic", r"doctor", r"\bdra\b", r"\bdr\b", r"odont", r"nutri", r"psic", r"enfermer",
                            r"👩‍⚕", r"👨‍⚕", r"🦷"),
    "espiritualidad_bienestar": rx(r"\bdios\b", r"\bgod\b", r"\bfe\b", r"bendic", r"metta", r"bodhisattva",
                                   r"🙏", r"🕉", r"tarot", r"astrolog"),
}

LOC = [  # orden = prioridad (la primera que coincide gana)
    ("pachuca_zona_metro", rx(r"pachuca", r"pachuqu", r"pachucool", r"mineral de la reforma", r"zona plateada",
                              r"san javier", r"\bpzx\b")),
    ("hidalgo_otros_municipios", rx(r"hidalgo", r"\bhgo\b", r"hidalguense", r"tulancingo", r"tizayuca",
                                    r"real del monte", r"mineral del chico", r"actopan", r"ixmiquilpan", r"huasca",
                                    r"\btula\b", r"\bapan\b", r"zempoala", r"tepeji", r"huejutla", r"tlahuiltepa",
                                    r"tepeapulco", r"sahagun", r"progreso de obregon", r"tlaxcoapan")),
    ("cdmx", rx(r"cdmx", r"ciudad de mexico", r"mexico city", r"\bdf\b", r"chilang", r"roma norte", r"condesa",
                r"coyoacan", r"polanco", r"iztapalapa", r"del valle", r"tlalpan", r"\bcd\.? de mexico")),
    ("edomex", rx(r"edomex", r"estado de mexico", r"ecatepec", r"tecamac", r"naucalpan", r"toluca", r"texcoco",
                  r"satelite", r"neza")),
    ("otros_estados_mx", rx(r"queretaro", r"\bqro\b", r"puebla", r"monterrey", r"\bmty\b", r"guadalajara",
                            r"\bgdl\b", r"cancun", r"yucatan", r"merida", r"oaxaca", r"veracruz", r"tampico",
                            r"\bleon\b", r"\bslp\b", r"tijuana", r"villahermosa", r"tlaxcala", r"morelos",
                            r"cuernavaca", r"guanajuato", r"chiapas", r"baja", r"jalisco", r"sonora", r"colima")),
    ("extranjero", rx(r"spain", r"espana", r"madrid", r"\bbcn\b", r"barcelona", r"\busa\b", r"miami",
                      r"new jersey", r"austria", r"france|francia|paris", r"uruguay", r"canada", r"🇺🇸", r"🇪🇸",
                      r"🇫🇷", r"🇩🇪", r"🇨🇦", r"🇺🇾", r"🇦🇷", r"🇨🇴", r"🇧🇷")),
]

# Nombres de pila frecuentes en México (para género inferido, SOLO agregado)
FEM = set("""maria mariana ana andrea fernanda daniela gabriela alejandra paola valeria karla karen sofia
jessica diana laura monica claudia veronica adriana patricia leticia rosa guadalupe lupita alicia beatriz
carmen elena isabel itzel ximena regina natalia carolina caro lorena lore marisol nancy brenda araceli
liliana lili sandra silvia susana teresa tere yolanda viridiana wendy yesenia jazmin jasmin abril aranza
arantxa ariadna ariatna citlali citlalli dulce estefania fabiola frida gisela ivonne jimena joselyn jocelyn
julia julieta lucia luz marcela margarita martha melany melanie mercedes miriam nadia nayeli noemi
ofelia pamela perla rebeca rocio ruth samantha selene tania vanessa vanesa yazmin zaira abigail adela
alma angelica angeles anahi azucena barbara cecilia cristina denisse elizabeth erika esmeralda evelyn
evelyna fatima flor gloria graciela irma janet jennifer karina katia kimberly lizbeth maribel mayra
melissa michelle montserrat montse nora norma olga raquel renata rosario sara sarah sonia vianey yuridia
dianalaura marla irene ileana yoselin yosse deysi daysi dayana jacqueline jaqueline paulina mirna
emilia camila victoria valentina romina danna dana constanza ivanna ingrid sabrina sabina nathaly
nataly jaz jazz grecia esther susy alondra estrella carla nicole nicol astrid iris aide areli azul""".split())
MAS = set("""jose juan luis carlos jorge miguel francisco javier alejandro daniel david ricardo fernando
eduardo roberto antonio manuel sergio raul arturo enrique mario hector oscar alberto pedro rafael victor
alfredo armando ernesto ivan jesus gerardo guillermo hugo ignacio jaime julio leonardo leo marco marcos
martin mauricio omar pablo ramon ruben salvador santiago sebastian emilio diego gabriel andres angel
adrian abraham alan alonso axel bryan brayan cesar christian cristian edgar edson efrain emmanuel erick
eric esteban fabian felipe gilberto gustavo gus horacio humberto isaac israel jonathan josue kevin
lorenzo manolo mateo moises nicolas octavio orlando oswaldo osvaldo patricio rodolfo rodrigo samuel
saul tomas tom ulises uriel vicente alexis aldo benjamin dante elias emiliano gael hernan joel josh
luciano mariano maximiliano max nestor noe rene rogelio sam simon teodoro tilo yahir yakin charlie
fito pepe paco memo beto toño chucho lalo pancho rich gonzalo alex alexander joaquin agustin bruno
heriberto heri ismael jair jacobo julian kike luis_angel marcelo matias said""".split())
NAME_AMBIG = {"guadalupe", "lupe", "alex", "sam", "charlie", "jazz", "jaz", "cruz", "ari", "dani", "angeles"}


def first_name(full):
    t = re.findall(r"[a-z]+", norm(full))
    return t[0] if t else ""


def gender(full):
    fn = first_name(full)
    if not fn or fn in NAME_AMBIG:
        return None
    if fn in FEM:
        return "F"
    if fn in MAS:
        return "M"
    return None


BRAND = rx(r"cervec", r"brew", r"beer", r"taproom", r"\bcafe", r"coffee", r"food", r"restaurante?", r"cocina",
           r"studio", r"estudio", r"\bbar\b", r"panader", r"bakery", r"reposter", r"pasteler", r"\bvino", r"wine",
           r"tattoo", r"piercer", r"classes", r"zapatos", r"ceramic", r"\bagua\b", r"mexico", r"pachuca", r"\bmx\b",
           r"oficial", r"official", r"festival", r"\bpoke\b", r"taco", r"pizza", r"burger", r"rancho", r"\bcava\b",
           r"nail", r"fitness", r"\bclub\b", r"tienda", r"\bshop", r"insumos", r"foodie", r"blog", r"®")
STOP_BRAND = {"la", "el", "los", "las", "de", "del", "y", "the", "and"}


def person_like(full):
    """True si el nombre parece 'Nombre Apellido' de persona física (conservador: ante duda, excluye)."""
    name = (full or "").strip()
    if not name or BRAND.search(norm(name)):
        return False
    if gender(name):
        return True
    words = name.split()
    if not 2 <= len(words) <= 4 or any(norm(w) in STOP_BRAND for w in words):
        return False
    words = unicodedata.normalize("NFKC", name).split()
    return all(re.fullmatch(r"[A-ZÁÉÍÓÚÑ][a-záéíóúñü]+\.?", w) for w in words)


def text_of(a):
    return norm(" ".join([a.get("username") or "", a.get("full_name") or a.get("fullName") or "",
                          a.get("biography") or ""]))


def acct_type(a):
    """negocio / creador / personal (inferido). Bio y nombre; el username suma señal débil."""
    t = text_of(a)
    if NEG.search(t):
        return "negocio"
    if CRE.search(t):
        return "creador"
    if (a.get("follower_count") or 0) >= 10000 and not a.get("is_private"):
        return "creador"          # alcance alto sin señales → probable figura pública
    return "personal"


CAT_OVERRIDE = {  # cuentas de artistas/espacios cuya bio no trae palabras clave
    "juancirerolofficial": "musica_dj", "scorpio_seis_nueve": "musica_dj", "l.a.jabonera": "eventos_espacios_cultura",
}


def categoria(a):
    if a.get("username") in CAT_OVERRIDE:
        return CAT_OVERRIDE[a["username"]]
    t = text_of(a)
    for name, r in CAT:
        if r.search(t):
            return name
    return "otro"


LOC_OVERRIDE = {"lavizcainabrew": "hidalgo_otros_municipios"}  # Real del Monte (01-base-conocimientos §7)


def location(a):
    if a.get("username") in LOC_OVERRIDE:
        return LOC_OVERRIDE[a["username"]]
    t = norm((a.get("biography") or "") + " " + (a.get("full_name") or ""))
    for name, r in LOC:
        if r.search(t):
            return name
    return None


def tier(n):
    n = n or 0
    if n < 300: return "a_<300"
    if n < 1000: return "b_300-999"
    if n < 10000: return "c_nano_1k-9.9k"
    if n < 100000: return "d_micro_10k-99k"
    return "e_macro_100k+"


def likely_inactive(a):
    return (not (a.get("biography") or "").strip()) and (a.get("follower_count") or 0) < 50


def audience_block(accts, label):
    n = len(accts)
    types = Counter(acct_type(a) for a in accts)
    priv = sum(1 for a in accts if a.get("is_private"))
    with_bio = [a for a in accts if (a.get("biography") or "").strip()]
    pers = [a for a in accts if acct_type(a) == "personal"]
    locs = Counter(location(a) for a in with_bio)
    located = sum(v for k, v in locs.items() if k)
    ints = Counter()
    for a in with_bio:
        t = text_of(a)
        for k, r in INT.items():
            if r.search(t):
                ints[k] += 1
    g = Counter(gender(a.get("full_name")) for a in pers)
    g_cls = g["F"] + g["M"]
    biz = [a for a in accts if acct_type(a) != "personal"]
    cats = Counter(categoria(a) for a in biz)
    fc = [a.get("follower_count") or 0 for a in accts]
    fc_p = [a.get("follower_count") or 0 for a in pers]
    return {
        "muestra": n,
        "metodo": "clasificación por palabras clave en bio + nombre + usuario (inferido; ver 'notas_metodo')",
        "tipo_cuenta": {k: {"n": v, "pct": pct(v, n)} for k, v in types.most_common()},
        "privadas": {"n": priv, "pct": pct(priv, n)},
        "con_bio": {"n": len(with_bio), "pct": pct(len(with_bio), n)},
        "probables_inactivas_o_sin_contenido": sum(1 for a in accts if likely_inactive(a)),
        "seguidores_de_las_cuentas": {
            "mediana_todas": st.median(fc) if fc else None,
            "mediana_personales": st.median(fc_p) if fc_p else None,
            "tramos_todas": dict(sorted(Counter(tier(x) for x in fc).items())),
            "tramos_personales": dict(sorted(Counter(tier(x) for x in fc_p).items())),
            "nota": "nano = 1k–9.9k, micro = 10k–99k. Seguidores de cada cuenta, no de la Jabonera.",
        },
        "ubicacion_declarada_en_bio": {
            "base": f"{len(with_bio)} cuentas con bio",
            "con_ubicacion_detectable": {"n": located, "pct": pct(located, len(with_bio))},
            "reparto_sobre_detectables": {k: {"n": v, "pct": pct(v, located)} for k, v in locs.most_common() if k},
            "nota": "Solo cuenta a quien escribe su ciudad/estado en la bio o el nombre; el resto es desconocido, no 'fuera de Pachuca'.",
        },
        "intereses_en_bio": {
            "base": f"{len(with_bio)} cuentas con bio (multi-etiqueta)",
            **{k: {"n": v, "pct_sobre_con_bio": pct(v, len(with_bio))} for k, v in ints.most_common()},
        },
        "genero_inferido_personales": {
            "base_personales": len(pers),
            "clasificables": g_cls,
            "cobertura_pct": pct(g_cls, len(pers)),
            "F_pct_sobre_clasificables": pct(g["F"], g_cls),
            "M_pct_sobre_clasificables": pct(g["M"], g_cls),
            "metodo": "primer nombre del campo 'nombre' contra listas de nombres frecuentes en México; se excluyen ambiguos y apodos",
            "error_esperado": "±5–10 pp por sesgo de cobertura (quien usa apodo/emoji queda fuera) y nombres unisex; no capta identidades no binarias. Úsese solo como orden de magnitud.",
        },
        "categorias_negocio_creador": {k: {"n": v, "pct": pct(v, len(biz))} for k, v in cats.most_common()},
    }


# ---------------------------------------------------------------- carga
profile = load(RAW / "profile-jabonera.json")[0]
followers = load(RAW / "followers-jabonera.json")
following = load(RAW / "following-jabonera.json")
posts = load(RAW / "posts-jabonera.json")
comments_full = load(RAW / "comments-jabonera.json")
aliados_extra = {p["username"]: p for p in load(RAW / "profiles-aliados.json") if p.get("username")}
cn_posts = load(BASE / "scraping/raw/ig-posts-full-20261006.json")
reviews = list(csv.DictReader(open(BASE / "contenido/google-maps/resenas.csv", encoding="utf-8")))

_excl = RAW / "excluir-privacidad.json"   # revisión manual (crudo, gitignored: contiene usernames)
EXCLUIR = set(load(_excl)["excluir"]) if _excl.exists() else set()
fol_users = {a["username"] for a in followers}
fing_users = {a["username"] for a in following}

# ---------------------------------------------------------------- posts del festival
def post_kind(p):
    return {"Image": "imagen", "Sidecar": "carrusel", "Video": "video/reel"}.get(p.get("type"), p.get("type"))


def inter(p):
    return (p.get("likesCount") or 0) + (p.get("commentsCount") or 0)


def collab_names(p):
    return [c.get("username") for c in (p.get("coauthorProducers") or []) if c.get("username") and c.get("username") != SELF]


by_year = defaultdict(list)
for p in posts:
    by_year[(p.get("timestamp") or "")[:4]].append(p)
posts_block = {"posts_obtenidos": len(posts), "posts_totales_perfil": profile.get("postsCount"),
               "nota": "La cuenta se usó en jun-2025 para otro festival gastronómico/musical en La Jabonera (perfiles de cocineros, cervecerías, DJs) y desde jul-2026 para el Oktoberfest.",
               "por_anio": {}}
for y, ps in sorted(by_year.items()):
    col = [inter(p) for p in ps if collab_names(p)]
    nocol = [inter(p) for p in ps if not collab_names(p)]
    posts_block["por_anio"][y] = {
        "n": len(ps),
        "mediana_interaccion": st.median([inter(p) for p in ps]),
        "mediana_con_coautor": st.median(col) if col else None, "n_con_coautor": len(col),
        "mediana_sin_coautor": st.median(nocol) if nocol else None,
        "por_formato": {k: {"n": len(v), "mediana": st.median(v)} for k, v in
                        ((k, [inter(p) for p in ps if post_kind(p) == k]) for k in ("imagen", "carrusel", "video/reel")) if v},
    }
top = sorted(posts, key=inter, reverse=True)[:8]
posts_block["top_8"] = [{"fecha": (p.get("timestamp") or "")[:10], "formato": post_kind(p), "likes": p.get("likesCount"),
                         "comentarios": p.get("commentsCount"), "vistas_video": p.get("videoPlayCount") or p.get("videoViewCount"),
                         "coautores": collab_names(p), "tema": re.sub(r"\s+", " ", (p.get("caption") or ""))[:70]}
                        for p in top]

# ---------------------------------------------------------------- comentarios
cmts = {}
for p in posts:
    for c in p.get("latestComments") or []:
        cmts[c["id"]] = {"text": c.get("text") or "", "owner": c.get("ownerUsername"), "post": p.get("shortCode"),
                         "ts": c.get("timestamp") or ""}
for c in comments_full:
    sc = re.search(r"/p/([^/]+)", c.get("postUrl") or "")
    cmts[c["id"]] = {"text": c.get("text") or "", "owner": c.get("ownerUsername"),
                     "post": sc.group(1) if sc else None, "ts": c.get("timestamp") or ""}
post_year = {p.get("shortCode"): (p.get("timestamp") or "")[:4] for p in posts}
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐❤\U0001F1E6-\U0001F1FF]")
TOPIC = {
    "precio_boletos_preventa": rx(r"precio", r"cuanto", r"costo", r"cuesta", r"boleto", r"preventa", r"\$",
                                  r"entrada", r"day pass", r"incluye", r"cover", r"promo"),
    "horarios_fechas": rx(r"hora", r"horario", r"que dia", r"cuando", r"a que hora", r"fecha"),
    "artista_musica": rx(r"cirerol", r"\bjuan\b", r"\bdj\b", r"musica", r"rola", r"cancion", r"concierto",
                         r"toca", r"banda", r"escuby"),
    "cerveza_bebida": rx(r"cerveza", r"cheve", r"chela", r"beer", r"🍺", r"🍻", r"copa", r"tarro", r"litro",
                         r"barril", r"vino"),
    "comida": rx(r"comida", r"salchicha", r"pretzel", r"paella", r"taco", r"pizza", r"🥨", r"🌭", r"rico", r"sabroso"),
    "mascotas": rx(r"perr", r"mascota", r"pet", r"peludo", r"🐶", r"🐕"),
    "ninos_familia": rx(r"nin[oa]s", r"peque", r"familia", r"hijo", r"menor"),
    "estacionamiento_ubicacion": rx(r"estacion", r"donde", r"ubicacion", r"direccion", r"como llego", r"uber"),
    "fans_del_artista_piden_otras_ciudades": rx(r"guadalajara", r"\bmty\b", r"monterrey", r"\bqro\b",
                                                 r"queretaro", r"cdmx", r"cuautitlan", r"vienes a", r"solo diste",
                                                 r"otra fecha", r"\bgira\b", r"\btour\b"),
    "clima_lluvia": rx(r"lluvia", r"llov", r"clima", r"frio"),
    "elogio_entusiasmo": rx(r"genial", r"increible", r"chido", r"padre", r"buenis", r"excelente", r"vamos",
                            r"aqui estaremos", r"me encanta", r"🔥", r"🙌", r"😍", r"❤", r"👏", r"bravo", r"felicidades",
                            r"que bien", r"wow", r"jaja"),
    "queja_problema": rx(r"mal\b", r"pesimo", r"caro", r"no sirve", r"no funciona", r"queja", r"cancel", r"reembolso",
                         r"no llego", r"fila", r"tardan"),
}
cirerol_posts = {p.get("shortCode") for p in posts if "cirerol" in norm(p.get("caption"))}
own = [c for c in cmts.values() if c["owner"] == SELF]
aud = [c for c in cmts.values() if c["owner"] != SELF]
mention_only = 0
with_mention = 0
questions = []
topics = Counter()
emojis = Counter()
by_year_c = Counter()
for c in aud:
    t = c["text"]
    nt = norm(t)
    by_year_c[post_year.get(c["post"], "?")] += 1
    m = re.findall(r"@[\w.]+", t)
    if m:
        with_mention += 1
        rest = EMOJI.sub("", re.sub(r"@[\w.]+", "", t)).strip(" \n!.,")
        if not rest:
            mention_only += 1
    for k, r in TOPIC.items():
        if r.search(nt) or r.search(t):
            topics[k] += 1
    emojis.update(EMOJI.findall(t))
    if "?" in t or re.match(r"^(cuanto|a que hora|donde|cuando|hay|se puede|incluye)", nt):
        questions.append(re.sub(r"@[\w.]+", "@[usuario]", t).strip())
comment_block = {
    "comentarios_unicos": len(cmts),
    "de_la_cuenta_respondiendo": len(own),
    "de_audiencia": len(aud),
    "comentaristas_unicos": len({c["owner"] for c in aud}),
    "por_anio_del_post": dict(by_year_c),
    "con_mencion_a_otra_cuenta": {"n": with_mention, "pct": pct(with_mention, len(aud))},
    "solo_etiquetas_sin_texto": {"n": mention_only, "pct": pct(mention_only, len(aud)),
                                 "lectura": "señal de 'envío/etiquetado social': la persona invita a amigos al plan"},
    "temas": {k: {"n": v, "pct": pct(v, len(aud))} for k, v in topics.most_common()},
    "preguntas": {"n": len(questions), "pct": pct(len(questions), len(aud)),
                  "textos_anonimizados": questions[:15]},
    "emojis_top": emojis.most_common(12),
    "en_posts_con_juan_cirerol": {"n": sum(1 for c in aud if c["post"] in cirerol_posts),
                                  "pct": pct(sum(1 for c in aud if c["post"] in cirerol_posts), len(aud))},
    "cobertura": "98 comentarios de primer nivel visibles sin login (de 149 que reporta Instagram; la diferencia son respuestas anidadas, función de pago). El comment-scraper sobre los 3 posts con más conversación no añadió comentarios nuevos.",
}

# ---------------------------------------------------------------- solapamiento con Cisne Negro
cn_commenters = set()
cn_commenters_okt = set()
for p in cn_posts:
    is_okt = "oktober" in norm(p.get("caption")) or "jabonera" in norm(p.get("caption"))
    for c in p.get("latestComments") or []:
        u = c.get("ownerUsername")
        if u and u != "cisnenegro.mx":
            cn_commenters.add(u)
            if is_okt:
                cn_commenters_okt.add(u)
j_commenters = {c["owner"] for c in aud if c["owner"]}
overlap_block = {
    "metodo": "intersección de conjuntos de usernames calculada en local; solo se publican conteos",
    "comentaristas_cisne_negro_200_posts": len(cn_commenters),
    "de_ellos_en_muestra_seguidores_jabonera_700": len(cn_commenters & fol_users),
    "de_ellos_que_comentaron_en_jabonera": len(cn_commenters & j_commenters),
    "comentaristas_jabonera": len(j_commenters),
    "comentaristas_jabonera_en_muestra_seguidores": len(j_commenters & fol_users),
    "cisnenegro_mx_es_seguido_por_jabonera": "cisnenegro.mx" in fing_users,
    "cisnenegro_mx_en_muestra_seguidores_jabonera": "cisnenegro.mx" in fol_users,
    "seguidores_muestra_que_tambien_sigue_la_jabonera_(mutuos)": len(fol_users & fing_users),
    "lectura": "Con 1,550 seguidores (Jabonera) y 3,515 (Cisne), la muestra de 700 permite detectar solapamiento entre comentaristas, no estimar el solapamiento total de audiencias (requeriría la lista completa de seguidores de ambas cuentas).",
}

# ---------------------------------------------------------------- reseñas de Google (Cisne Negro)
RTOP = {
    "comida": rx(r"comida", r"hamburguesa", r"taco", r"tlayuda", r"papas", r"platillo", r"cocina", r"sabor", r"burger",
                 r"food", r"dona", r"ceviche", r"camarones", r"coliflor", r"sandwich", r"alitas"),
    "cerveza_producto": rx(r"cerveza", r"beer", r"ipa", r"stout", r"artesanal", r"barril", r"chela", r"variedad",
                           r"de la casa"),
    "servicio_atencion": rx(r"servicio", r"atencion", r"mesero", r"personal", r"amable", r"actitud", r"staff",
                            r"service", r"atienden"),
    "precio": rx(r"precio", r"caro", r"costoso", r"barato", r"\$", r"pesos", r"price", r"accesible"),
    "ambiente_lugar": rx(r"ambiente", r"lugar", r"musica", r"agradable", r"tranquilo", r"terraza", r"decor", r"vibe",
                         r"place", r"espacio"),
    "mascotas": rx(r"perr", r"mascota", r"pet", r"dog"),
    "maridaje_equilibrio": rx(r"marid", r"equilibr", r"combina", r"acompan"),
    "recomendacion_volver": rx(r"recomiend", r"volver", r"regresar", r"obligad", r"must", r"favorit"),
    "limpieza": rx(r"limpi", r"sucio", r"bano"),
    "estacionamiento": rx(r"estacion", r"parking"),
    "eventos_amigos": rx(r"amigos", r"evento", r"cumple", r"festej", r"reunion", r"friends", r"pareja", r"familia"),
}
rv = [r for r in reviews if (r.get("text") or "").strip()]
rt = defaultdict(list)
for r in rv:
    t = norm(r["text"])
    for k, r_ in RTOP.items():
        if r_.search(t):
            rt[k].append(int(float(r["stars"])))
review_block = {
    "resenas_total": len(reviews), "con_texto": len(rv),
    "estrellas": dict(sorted(Counter(int(float(r["stars"])) for r in reviews).items())),
    "temas": {k: {"n": len(v), "pct_con_texto": pct(len(v), len(rv)), "estrellas_promedio": round(st.mean(v), 2)}
              for k, v in sorted(rt.items(), key=lambda x: -len(x[1]))},
    "en_ingles": sum(1 for r in rv if re.search(r"\b(the|great|beer|place|good)\b", norm(r["text"]))),
    "metodo": "palabras clave sobre el texto de la reseña (multi-etiqueta)",
}

# ---------------------------------------------------------------- mapa de aliados
okt_credit = Counter()   # presencia acreditada en posts del Oktoberfest 2026
any_credit = Counter()
for p in posts:
    names = set(collab_names(p)) | {t.get("username") for t in (p.get("taggedUsers") or [])} | set(p.get("mentions") or [])
    names.discard(None); names.discard(SELF)
    for u in names:
        any_credit[u] += 1
        if (p.get("timestamp") or "") >= "2026-07":
            okt_credit[u] += 1
cn_collab = Counter()
for p in cn_posts:
    for c in p.get("coauthorProducers") or []:
        if c.get("username") and c.get("username") != "cisnenegro.mx":
            cn_collab[c["username"]] += 1

pool = {}
for a in following:
    pool[a["username"]] = {"src": "seguido_por_jabonera", **a}
for a in followers:
    if acct_type(a) != "personal" and not a.get("is_private"):
        pool.setdefault(a["username"], {"src": "seguidor_de_jabonera", **a})
for u, p in aliados_extra.items():
    if p.get("followersCount") is not None:
        pool.setdefault(u, {"src": "acreditado_en_posts", "username": u, "full_name": p.get("fullName"),
                            "biography": p.get("biography"), "follower_count": p.get("followersCount"),
                            "is_private": p.get("private"), "business_category": p.get("businessCategoryName")})

PRIOR_CAT = {"cerveza_vino_destilados": 3, "restaurante_comida": 2.5, "musica_dj": 2.5, "medio_foodie_creador": 2.5,
             "cafe_panaderia_postres": 2, "eventos_espacios_cultura": 2.5, "arte_diseno_foto": 1.5,
             "bienestar_fitness": 1.5, "belleza_moda": 0.5, "servicios_otros": 0.5, "otro": 0.5}
allies = []
for u, a in pool.items():
    if u == "cisnenegro.mx" or u in EXCLUIR:
        continue
    typ = acct_type(a)
    credited = okt_credit[u] + any_credit[u] > 0
    if a["src"] == "acreditado_en_posts" and typ == "personal":
        typ = "creador"   # página/colectivo acreditado públicamente en el line-up del festival
    if a.get("is_private"):
        continue
    if typ == "personal" and not credited:
        continue
    if typ == "personal" and credited:
        # acreditado en el evento pero sin señales de negocio/creador → no se nombra (persona física)
        continue
    fc0 = a.get("follower_count") or 0
    brand_name = bool(BRAND.search(norm((a.get("full_name") or "") + " " + u)))
    public_fig = fc0 >= 5000 or credited or cn_collab[u] > 0
    if not public_fig and person_like(a.get("full_name")):
        continue      # nombre con forma de persona física y sin notoriedad pública → no se nombra
    if typ == "creador" and not (public_fig or brand_name):
        continue      # creador pequeño no acreditado y sin nombre de marca → no se nombra
    if typ == "creador" and not (credited or cn_collab[u]) and not CRE.search(text_of(a)):
        continue      # 'creador' solo por alcance, sin señal de creador en la bio → no se nombra
    cat = categoria(a)
    loc = location(a)
    local = loc in ("pachuca_zona_metro", "hidalgo_otros_municipios")
    fc = a.get("follower_count") or 0
    reach = 0.5 if fc < 1000 else 1 if fc < 5000 else 1.5 if fc < 20000 else 2 if fc < 100000 else 1.0
    score = PRIOR_CAT.get(cat, 0.5) + (3 if local else 0) + reach + min(okt_credit[u], 5) * 0.6 \
        + (1.5 if cn_collab[u] else 0) + (0.5 if u in fol_users else 0)
    allies.append({
        "cuenta": "@" + u, "nombre": a.get("full_name"), "tipo": typ, "categoria": cat,
        "categoria_ig": a.get("business_category"), "seguidores": fc,
        "ubicacion_bio": loc, "local": local,
        "acreditado_en_oktoberfest_2026": okt_credit[u], "acreditado_en_posts_jabonera": any_credit[u],
        "collab_previa_con_cisne": cn_collab[u], "relacion_con_jabonera": a["src"],
        "bio": re.sub(r"\s+", " ", a.get("biography") or "")[:140], "score": round(score, 2),
    })
allies.sort(key=lambda x: -x["score"])
ally_types = Counter(x["categoria"] for x in allies)

# ---------------------------------------------------------------- tipología de lo que sigue la Jabonera
fing_block = audience_block(following, "seguidos")
fing_block["nota"] = "225 de 258 seguidos (33 no devueltos por el actor). Las cuentas personales se cuentan pero no se nombran."
fing_local = Counter(location(a) for a in following if acct_type(a) != "personal")

# ---------------------------------------------------------------- salida
out = {
    "generado": "2026-10-08",
    "fuente": "@oktoberfestjabonera (Instagram, datos públicos sin login) + @cisnenegro.mx + reseñas de Google",
    "privacidad": "Solo agregados. Usernames solo de cuentas de negocio/creador públicas o acreditadas en posts del festival. Crudos en scraping/raw/jabonera-20261008/ (gitignored).",
    "perfil_jabonera": {k: profile.get(k) for k in ("username", "fullName", "biography", "followersCount",
                                                     "followsCount", "postsCount", "businessCategoryName",
                                                     "externalUrl")},
    "extraccion": {
        "plan": "A (lista de seguidores/seguidos sin login) — viable; complementado con posts y comentarios (Plan B)",
        "seguidores_obtenidos": len(followers), "seguidores_totales": profile.get("followersCount"),
        "cobertura_seguidores_pct": pct(len(followers), profile.get("followersCount")),
        "seguidos_obtenidos": len(following), "seguidos_totales": profile.get("followsCount"),
        "posts_obtenidos": len(posts), "comentarios_unicos": len(cmts),
        "actores": {
            "apify/instagram-profile-scraper": "perfil Jabonera + 6 aliados",
            "scraping_solutions/instagram-scraper-followers-following": "seguidores (limite 750) y seguidos (limite 300) con enrichProfileDetails",
            "apify/instagram-post-scraper": "posts (limite 70)",
            "apify/instagram-comment-scraper": "3 posts, limite 35 c/u",
        },
    },
    "seguidores_muestra": audience_block(followers, "seguidores"),
    "seguidos_por_la_jabonera": fing_block,
    "seguidos_negocio_creador_por_ubicacion": dict(fing_local.most_common()),
    "posts": posts_block,
    "comentarios": comment_block,
    "solapamiento_cisne_negro": overlap_block,
    "resenas_google_cisne_negro": review_block,
    "aliados_potenciales": {"n": len(allies), "por_categoria": dict(ally_types.most_common()),
                            "criterio_privacidad": "más una lista de exclusión por revisión manual guardada en raw/ (no versionada); se excluyen privadas y personales; un negocio con nombre de persona solo entra si el nombre/usuario tiene señales de marca o es figura pública (≥5k, acreditado en el festival o collab previa con Cisne); un creador solo si es figura pública o su nombre es de marca",
                            "metodo_score": "categoría afín (cerveza 3 · restaurante/música/foodie/eventos 2.5 · café 2 …) + local Pachuca/Hidalgo 3 + alcance 0.5–2 + 0.6 por crédito en posts del Oktoberfest 2026 (máx 5) + 1.5 si ya hubo collab con Cisne + 0.5 si sigue a la Jabonera",
                            "top_40": allies[:40],
                            "resto": [{k: x[k] for k in ("cuenta", "categoria", "seguidores", "local", "score")} for x in allies[40:]]},
    "notas_metodo": [
        "Tipo de cuenta, categoría, ubicación, intereses y género son INFERENCIAS por palabras clave; no hay campo 'business' en los datos de seguidores.",
        "La muestra de seguidores (700/1,550) es el orden que devuelve Instagram (aprox. más recientes primero): sobrerrepresenta a quien siguió durante la promoción del Oktoberfest 2026.",
        "El 41% de la muestra es privada: su bio sí es visible, pero no sus posts.",
        "Los 'likers' no son obtenibles sin login; la audiencia comprometida se mide con comentaristas.",
        "Edad: no se infiere (no hay dato fiable). La comunicación asume 25+ por COFEPRIS.",
    ],
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("OK ->", OUT)
