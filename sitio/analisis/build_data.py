#!/usr/bin/env python3
"""Genera data.json para el informe de presencia digital de Cervecería Cisne Negro.

Uso (desde cualquier carpeta):
    python3 sitio/analisis/build_data.py            # escribe data.json
    python3 sitio/analisis/build_data.py --embed    # además embebe data.json en index.html
    python3 sitio/analisis/build_data.py --thumbs   # además copia miniaturas del top 10 a img/

Fuentes: scraping/dataset.json y scraping/raw/*-20261006.json (scraping del 2026-10-06).
Todo número del informe sale de aquí o de un dato con fuente citada en FUENTES_EXTERNAS.
No se exporta ningún nombre de reseñador ni dato personal.
"""
import json
import re
import statistics as st
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]  # cisne-negro-cerveceria/
SCR = RAIZ / "scraping"
FECHA_CORTE = datetime(2026, 10, 6, tzinfo=timezone.utc)
CDMX = timezone(timedelta(hours=-6))  # México sin horario de verano desde oct 2022

ds = json.load(open(SCR / "dataset.json", encoding="utf-8"))
gm = json.load(open(SCR / "raw/gmaps-20261006.json", encoding="utf-8"))[0]
igp = json.load(open(SCR / "raw/ig-profile-20261006.json", encoding="utf-8"))
igp = igp[0] if isinstance(igp, list) else igp
ttraw = json.load(open(SCR / "raw/tiktok-20261006.json", encoding="utf-8"))


def fecha(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def med(v):
    return round(st.median(v), 1) if v else None


ig = [p for p in ds["posts"] if p["red"] == "instagram"]
tt = [p for p in ds["posts"] if p["red"] == "tiktok"]
for p in ig:
    p["inter"] = (p["likes"] or 0) + (p["comentarios"] or 0)
    p["dt"] = fecha(p["fecha"]).astimezone(CDMX)

# ---------------------------------------------------------------- Instagram
FORMATOS = ["carrusel", "reel", "foto"]
formato = []
for f in FORMATOS:
    v = [p["inter"] for p in ig if p["formato"] == f]
    item = {"formato": f, "n": len(v), "mediana": med(v), "promedio": round(sum(v) / len(v), 1)}
    if f == "reel":
        item["mediana_vistas"] = med([p["vistas"] for p in ig if p["formato"] == f and p["vistas"]])
    formato.append(item)

# Frecuencia mensual 2023-11 → 2026-09, incluidos los meses en cero
meses = []
y, m = 2023, 11
while (y, m) <= (2026, 9):
    meses.append(f"{y}-{m:02d}")
    m += 1
    if m == 13:
        y, m = y + 1, 1
cnt_mes = Counter(p["dt"].strftime("%Y-%m") for p in ig)
inter_mes = defaultdict(list)
for p in ig:
    inter_mes[p["dt"].strftime("%Y-%m")].append(p["inter"])
frecuencia = [{"mes": k, "posts": cnt_mes.get(k, 0), "mediana_inter": med(inter_mes.get(k, []))} for k in meses]
meses_cero = [k for k in meses if cnt_mes.get(k, 0) == 0]


def prom_mes(desde, hasta):
    sel = [cnt_mes.get(k, 0) for k in meses if desde <= k <= hasta]
    return round(sum(sel) / len(sel), 1)


ult90 = [p for p in ig if (FECHA_CORTE - p["dt"]).days <= 90]
frec_actual = {
    "posts_ult_90_dias": len(ult90),
    "posts_por_semana_ult_90": round(len(ult90) / (90 / 7), 1),
    "prom_mensual_2024_s1": prom_mes("2024-01", "2024-06"),
    "prom_mensual_2025": prom_mes("2025-01", "2025-12"),
    "prom_mensual_2026": prom_mes("2026-01", "2026-09"),
    "ultimo_post": max(p["fecha"] for p in ig)[:10],
}

# Mejor día y franja (hora CDMX). Para no confundir horario con crecimiento de la
# cuenta, cada post se mide contra la mediana de su año: índice 1.0 = post típico.
med_anio = {a: st.median([p["inter"] for p in ig if p["dt"].year == a]) for a in {p["dt"].year for p in ig}}
for p in ig:
    p["indice"] = p["inter"] / med_anio[p["dt"].year]
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
FRANJAS = [("Mañana", 6, 12), ("Mediodía", 12, 15), ("Tarde", 15, 19), ("Noche", 19, 24), ("Madrugada", 0, 6)]


def franja(h):
    for nombre, a, b in FRANJAS:
        if a <= h < b:
            return nombre


celdas = defaultdict(list)
por_dia = defaultdict(list)
por_franja = defaultdict(list)
for p in ig:
    d = DIAS[p["dt"].weekday()]
    fr = franja(p["dt"].hour)
    celdas[(d, fr)].append(p["indice"])
    por_dia[d].append(p["indice"])
    por_franja[fr].append(p["indice"])
MIN_N = 10
heatmap = [
    {"dia": d, "franja": fr, "n": len(celdas[(d, fr)]),
     "indice": round(st.median(celdas[(d, fr)]), 2) if celdas[(d, fr)] else None}
    for d in DIAS for fr, _, _ in FRANJAS
]
dia_stats = [{"dia": d, "n": len(por_dia[d]), "indice": round(st.median(por_dia[d]), 2)} for d in DIAS]
franja_stats = [{"franja": f, "n": len(por_franja[f]),
                 "indice": round(st.median(por_franja[f]), 2) if por_franja[f] else None} for f, _, _ in FRANJAS]
validas_dia = [x for x in dia_stats if x["n"] >= MIN_N]
validas_fr = [x for x in franja_stats if x["n"] >= MIN_N]
validas_celda = [x for x in heatmap if x["n"] >= MIN_N]
mejor = {
    "dia": max(validas_dia, key=lambda x: x["indice"]),
    "franja": max(validas_fr, key=lambda x: x["indice"]),
    "celda": max(validas_celda, key=lambda x: x["indice"]),
    "min_n": MIN_N,
    "mediana_por_anio": {str(k): v for k, v in sorted(med_anio.items())},
}

# Top 10 por interacción (likes + comentarios)
top = sorted(ig, key=lambda p: p["inter"], reverse=True)[:10]
top10 = [{
    "id": p["id"], "url": p["url"], "fecha": p["dt"].strftime("%Y-%m-%d"), "formato": p["formato"],
    "likes": p["likes"], "comentarios": p["comentarios"], "inter": p["inter"],
    "texto": re.sub(r"\s+", " ", p["texto"]).strip()[:140], "img": f"img/{p['id']}.jpg",
    "carpeta": p["carpeta"], "tema": None,
} for p in top]

# Temas: clasificación por reglas de palabras clave, con prioridad
# eventos > avisos > comida/cerveza > ambiente. Las reglas son explícitas y auditables.
TEMAS = {
    "Eventos y colaboraciones": [
        r"\bcolab", r"pop ?up", r"takeover", r"noche de velas", r"oktoberfest", r"aniversario",
        r"anniversary", r"\bcumple", r"halloween", r"posada", r"\byoga\b", r"circuito arte", r"estreno",
        r"documental", r"pizza ?& ?beer", r"pizza night", r"cartelera", r"rosca de reyes", r"\bdj\b",
        r"\bano ii\b", r"\b8m\b", r"vacioba", r"ride n chelas", r"\bevento", r"alttar",
    ],
    "Avisos y horarios": [
        r"proximamente", r"p r o x i m a", r"ya abrimos", r"estamos abiertos", r"estamos listos",
        r"te esperamos de", r"hoy de \d", r"de \d+:\d+ ?(a|pm)", r"servicio de", r"martes a domingo",
        r"cerrado", r"horario", r"a partir de las", r"valido durante",
    ],
    "Comida": [
        r"hamburgues", r"burger", r"\bpapas\b", r"ceviche", r"\bdona\b", r"doughnut", r"campechana",
        r"croqueta", r"costrita", r"chicharron", r"tlayuda", r"tartar", r"sandwich", r"sandwich",
        r"suadero", r"philly", r"poll(o|ito)", r"ensalada", r"salchicha", r"strudel", r"postre", r"palomitas",
        r"coliflor", r"\btaco", r"burro con alas", r"camarones", r"platillo", r"menu",
        r"parrilla", r"pizza", r"atun",
    ],
    "Cerveza": [
        r"\bipa\b", r"ipa's", r"stout", r"lager", r"festbier", r"tap ?list", r"\bbarril", r"\blata",
        r"growler", r"flight", r"agua puerca", r"henry", r"barrilete", r"karnaval", r"a poco si",
        r"joyas ayala", r"matador", r"carabela", r"alarma", r"guamaica", r"dry ?hop", r"conectamos",
        r"conectar", r"cebada", r"fermentador", r"produccion", r"tap handle", r"taphandle", r"cerveza por definicion",
        r"chela o cheve", r"dorada o negra", r"hecha por nosotros", r"producida en", r"estilos",
    ],
}
ORDEN_TEMAS = ["Eventos y colaboraciones", "Avisos y horarios", "Comida", "Cerveza", "Ambiente y comunidad"]


def clasifica(texto):
    t = norm(texto)
    hits = {k: sum(1 for rx in v if re.search(rx, t)) for k, v in TEMAS.items()}
    if hits["Eventos y colaboraciones"]:
        return "Eventos y colaboraciones"
    if "por la foto" in t:  # foto de un cliente (UGC) = comunidad
        return "Ambiente y comunidad"
    if re.search(r"@\w", t) and hits["Cerveza"] < 2:  # mención a otra cuenta = colaboración,
        return "Eventos y colaboraciones"            # salvo lanzamientos de cerveza con crédito de ilustración
    if hits["Avisos y horarios"] and not (hits["Comida"] or hits["Cerveza"]) or hits["Avisos y horarios"] >= 2:
        return "Avisos y horarios"
    if hits["Comida"] or hits["Cerveza"]:
        # gana el tema con más coincidencias; empate → comida (el platillo es lo que se ve en la foto)
        return "Cerveza" if hits["Cerveza"] > hits["Comida"] else "Comida"
    return "Ambiente y comunidad"


for p in ig:
    p["tema"] = clasifica(p["texto"])
for t, p in zip(top10, top):
    t["tema"] = p["tema"]
temas = []
for k in ORDEN_TEMAS:
    v = [p["inter"] for p in ig if p["tema"] == k]
    vi = [p["indice"] for p in ig if p["tema"] == k]
    temas.append({"tema": k, "n": len(v), "mediana": med(v), "indice": round(st.median(vi), 2) if vi else None})

# Hashtags
hts = Counter(h.lower() for p in ig for h in p["hashtags"])
con_pachuca = sum(1 for p in ig if any("pachuca" in h.lower() for h in p["hashtags"]) or "pachuca" in norm(p["texto"]))
con_ht_pachuca = sum(1 for p in ig if any("pachuca" in h.lower() for h in p["hashtags"]))
cuentalo = sum(1 for p in ig if re.search(r"cuent[ao]\w* (lo )?en el cisne|cuentaloenelcisne|te lo cuento en el cisne", norm(p["texto"])))
hashtags = {
    "top": hts.most_common(12),
    "posts_con_hashtag_pachuca": con_ht_pachuca,
    "posts_que_mencionan_pachuca": con_pachuca,
    "posts_con_cuentalo_en_el_cisne": cuentalo,
    "posts_sin_hashtags": sum(1 for p in ig if not p["hashtags"]),
}

# ---------------------------------------------------------------- TikTok
tt_sorted = sorted(tt, key=lambda p: p["fecha"])
viral = max(ttraw, key=lambda t: t["playCount"])
total_vistas = sum(t["playCount"] for t in ttraw)
otros = [t["playCount"] for t in ttraw if t["id"] != viral["id"]]
author = ttraw[0]["authorMeta"]
tiktok = {
    "seguidores": author["fans"], "likes_totales": author["heart"], "videos": author["video"],
    "bio_link": author.get("bioLink"),
    "primer_post": tt_sorted[0]["fecha"][:10], "ultimo_post": tt_sorted[-1]["fecha"][:10],
    "dias_sin_publicar": (FECHA_CORTE - fecha(tt_sorted[-1]["fecha"])).days,
    "vistas_totales": total_vistas, "mediana_vistas_resto": med(otros),
    "viral": {
        "fecha": viral["createTimeISO"][:10], "vistas": viral["playCount"], "likes": viral["diggCount"],
        "compartidos": viral["shareCount"], "guardados": viral["collectCount"], "comentarios": viral["commentCount"],
        "duracion_s": viral["videoMeta"].get("duration"), "url": viral["webVideoUrl"],
        "texto": viral["text"].split("#")[0].strip(),
        "pct_vistas_totales": round(100 * viral["playCount"] / total_vistas, 1),
        "veces_mediana_resto": round(viral["playCount"] / st.median(otros), 1),
        "dias_hasta_abandono": (fecha(tt_sorted[-1]["fecha"]) - fecha(viral["createTimeISO"])).days,
    },
    "posts": [{"fecha": p["fecha"][:10], "formato": p["formato"], "vistas": p["vistas"], "likes": p["likes"]} for p in tt_sorted],
}
# Hueco de IG que coincide con el empuje de TikTok
ig_fechas = sorted(p["dt"] for p in ig)
gaps = sorted(((b - a).days, a.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d")) for a, b in zip(ig_fechas, ig_fechas[1:]))
hueco_ig = {"dias": gaps[-1][0], "desde": gaps[-1][1], "hasta": gaps[-1][2]}

# ---------------------------------------------------------------- Google
res = ds["resenas"]
dist = gm["reviewsDistribution"]
estrellas = [{"estrellas": e, "n": dist[k]} for e, k in
             [(5, "fiveStar"), (4, "fourStar"), (3, "threeStar"), (2, "twoStar"), (1, "oneStar")]]
por_anio = defaultdict(list)
for r in res:
    por_anio[r["fecha"][:4]].append(r["estrellas"])
evol = [{"anio": a, "n": len(v), "promedio": round(sum(v) / len(v), 2),
         "pct_5": round(100 * sum(1 for x in v if x == 5) / len(v)),
         "bajas": sum(1 for x in v if x <= 3)} for a, v in sorted(por_anio.items())]
con_texto = [r for r in res if r["texto"].strip()]
respondidas = sum(1 for r in res if r["respuesta_dueno"])

# Subcalificaciones (Comida / Servicio / Ambiente) que Google pide al reseñador
sub = defaultdict(list)
precio = Counter()
for r in gm["reviews"]:
    for k, v in (r.get("reviewDetailedRating") or {}).items():
        sub[k].append(v)
    pp = (r.get("reviewContext") or {}).get("Precio por persona")
    if pp:
        precio[pp.replace("\xa0", " ")] += 1
subcal = [{"aspecto": k, "n": len(v), "promedio": round(sum(v) / len(v), 2)} for k, v in sub.items()]
precio_rangos = sorted(precio.items(), key=lambda kv: int(re.match(r"\d+", kv[0]).group()))

# Clasificación MANUAL de temas: leída reseña por reseña (clave = fecha ISO exacta de la reseña).
# P = temas positivos, N = temas negativos. Reseñas sin texto no se clasifican.
P_CERV, P_COM, P_SERV, P_AMB, P_CONC = "Cerveza", "Comida", "Servicio y atención", "Ambiente y lugar", "Concepto único en Pachuca"
N_SERV, N_PREC, N_CERV, N_COM, N_LIMP, N_MENU, N_INFO = ("Actitud del servicio", "Precio", "Calidad o frescura de la cerveza",
                                                         "Comida (grasa, pan, porción)", "Limpieza", "Carta o tap list limitados",
                                                         "Información y orden (precios, horario)")
MANUAL = {
    "2023-12-16": ([P_CERV, P_COM], []),
    "2023-12-24": ([P_CERV], []),
    "2024-01-07": ([P_AMB, P_SERV, P_COM], []),
    "2024-01-20": ([P_AMB], [N_SERV]),
    "2024-02-24": ([P_CERV, P_COM, P_AMB, P_SERV], []),
    "2024-02-25": ([P_CERV, P_COM, P_AMB], []),
    "2024-04-01": ([P_COM, P_CERV], []),
    "2024-04-17A": ([P_AMB], []),
    "2024-04-17B": ([P_SERV, P_AMB], []),
    "2024-05-03A": ([P_AMB], [N_SERV, N_INFO]),
    "2024-05-03B": ([P_CONC, P_CERV, P_COM, P_AMB, P_SERV], []),
    "2024-05-18": ([P_AMB, P_COM, P_CERV, P_SERV], []),
    "2024-05-22": ([P_COM], []),
    "2024-05-23": ([P_CERV], []),
    "2024-06-03": ([P_AMB], []),
    "2024-06-29": ([], [N_COM, N_MENU]),
    "2024-07-08": ([P_CONC, P_AMB, P_COM], [N_MENU]),
    "2024-07-14": ([P_CERV, P_COM, P_SERV], []),
    "2024-11-02": ([P_COM, P_CERV], [N_PREC]),
    "2024-11-17": ([P_CERV, P_AMB], []),
    "2024-12-03A": ([P_CONC, P_COM, P_SERV], [N_CERV, N_PREC, N_SERV]),
    "2024-12-03B": ([P_COM, P_CERV], [N_PREC]),
    "2024-12-04": ([], [N_MENU, N_CERV]),
    "2025-01-14": ([P_SERV], [N_PREC, N_INFO]),
    "2025-01-17": ([P_CERV, P_COM, P_AMB], []),
    "2025-02-28": ([P_COM, P_AMB, P_SERV], []),
    "2025-03-13": ([P_SERV, P_AMB], []),
    "2025-03-16": ([], [N_SERV]),
    "2025-03-21": ([P_COM, P_CERV], []),
    "2025-03-23": ([], [N_COM]),
    "2025-03-25": ([P_CERV, P_SERV, P_COM, P_AMB], []),
    "2025-04-10": ([P_CONC, P_SERV, P_COM], []),
    "2025-05-18": ([P_CERV, P_COM, P_SERV], []),
    "2025-06-10": ([], [N_SERV, N_CERV, N_COM, N_LIMP]),
    "2025-07-22": ([P_CERV, P_COM, P_SERV], []),
    "2025-11-12": ([P_COM, P_CERV], []),
    "2025-12-08": ([P_COM, P_CERV, P_AMB], []),
    "2026-01-04": ([P_SERV, P_CERV], []),
    "2026-01-06": ([P_COM, P_SERV], []),
    "2026-02-09": ([P_CERV, P_COM], []),
    "2026-05-06": ([P_CERV], []),
    "2026-05-11": ([P_COM], [N_SERV, N_COM]),
    "2026-07-16": ([P_AMB, P_SERV, P_CERV], []),
    "2026-08-01": ([P_CERV, P_COM, P_SERV], []),
    "2026-10-03": ([P_CONC, P_COM, P_CERV], []),
}
# Resolver claves: las fechas con dos reseñas el mismo día llevan sufijo A/B por orden de hora.
textos = sorted(con_texto, key=lambda r: r["fecha"])
claves = []
dia_cnt = Counter(r["fecha"][:10] for r in textos)
dia_vistos = Counter()
for r in textos:
    d = r["fecha"][:10]
    if dia_cnt[d] > 1:
        k = d + "AB"[dia_vistos[d]]
        dia_vistos[d] += 1
    else:
        k = d
    claves.append(k)
faltan = [k for k in claves if k not in MANUAL]
sobran = [k for k in MANUAL if k not in claves]
assert not faltan and not sobran, (faltan, sobran)
pos, neg = Counter(), Counter()
for k in claves:
    pos.update(MANUAL[k][0])
    neg.update(MANUAL[k][1])
n_bajas_texto = sum(1 for r in textos if r["estrellas"] <= 3)

CITAS = [  # fragmentos literales, anónimos (sin nombre del autor); se verifica que existan en el dataset
    ("Pocas veces en taprooms, la comida y la bebidas están tan espectacularmente equilibradas. Parada obligada en Pachuca", 5, "positiva"),
    ("el personal se toma el tiempo de explicar cada una de ellos; eso se agradece demasiado", 5, "positiva"),
    ("Me encantó es un concepto diferente en Pachuca", 5, "positiva"),
    ("casi cada semana puedes encontrar algo nuevo", 5, "positiva"),
    ("Los precios son un poco elevados", 4, "crítica"),
    ("cuando quieres ver el menú de cheves en la pared, te los dicen de memoria. Si pusieran el precio de cada una, mucho ayudaría", 3, "crítica"),
    ("Una mesera nos hablaba de manera hostíl, cero amable", 3, "crítica"),
    ("la cerveza no esta fresca", 3, "crítica"),
]
todo = " ".join(r["texto"] for r in res)
citas = []
for c, e, tono in CITAS:
    assert c in todo, c
    citas.append({"texto": c, "estrellas": e, "tono": tono})

google = {
    "titulo_ficha": gm["title"], "categorias": gm["categories"], "rating": gm["totalScore"],
    "resenas": gm["reviewsCount"], "fotos": gm["imagesCount"], "reclamada": not gm["claimThisBusiness"],
    "respondidas": respondidas, "con_texto": len(con_texto), "estrellas": estrellas, "por_anio": evol,
    "subcalificaciones": subcal, "precio_por_persona": precio_rangos,
    "positivos": pos.most_common(), "negativos": neg.most_common(), "n_clasificadas": len(textos),
    "n_bajas_con_texto": n_bajas_texto, "citas": citas,
    "horas_pico": gm.get("popularTimesHistogram") or {},
    "menu": gm.get("menu"), "reservas": gm.get("reserveTableUrl"), "publicaciones": len(gm.get("ownerUpdates") or []),
    "preguntas": len(gm.get("questionsAndAnswers") or []), "etiquetas_resenas": [(t["title"], t["count"]) for t in gm["reviewsTags"]],
    "horario": gm["openingHours"], "telefono": gm["phone"],
}

# ---------------------------------------------------------------- Scores por canal
# Rúbrica: 5 dimensiones × 20 pts. 20 = cumple, 10 = parcial, 0 = no cumple o no verificable
# públicamente (lo que un cliente sin sesión no ve, no cuenta).
ig_rate = med([p["inter"] for p in ig if (FECHA_CORTE - p["dt"]).days <= 365]) / igp["followersCount"] * 100
RUBRICA = {
    "Presencia": "Existe, está reclamado y completo (20) · existe con huecos (10) · no existe o no se puede ver (0)",
    "Exactitud": "Nombre, teléfono y horario correctos (20) · correctos pero incompletos (10) · erróneos o no verificables (0)",
    "Actividad": "Actualizado en los últimos 30 días y con ritmo ≥ 2 por semana (20) · actualizado en 90 días (10) · sin actividad (0)",
    "Tracción": "Audiencia o prueba social sobre el umbral del canal (20) · intermedia (10) · baja o nula (0)",
    "Conversión": "Lleva a visitar, llamar o escribir y responde (20) · parcial (10) · sin ruta (0)",
}
canales = [
    {"canal": "Sitio web", "detalle": "cisnenegro.mx", "puntos": {
        "Presencia": (20, "Dominio propio activo con Inicio, Menú y Contacto"),
        "Exactitud": (20, "Dirección, teléfono (771) 244-2025 y horario correctos"),
        "Actividad": (10, "Menú vigente, pero foto de stock y sin eventos ni novedades"),
        "Tracción": (0, "SEO básico ausente: título 'Cisne Negro' sin ciudad ni giro y meta description vacía"),
        "Conversión": (10, "Muestra teléfono y correo, pero no enlaza IG, FB ni WhatsApp y tiene un carrito vacío"),
    }},
    {"canal": "Instagram", "detalle": f"@{igp['username']}", "puntos": {
        "Presencia": (20, "Cuenta de empresa con bio, highlights (Menú, Horario) y enlace"),
        "Exactitud": (10, "Nombre correcto; la bio no dice dirección, horario ni 'lunes cerrado'"),
        "Actividad": (20 if frec_actual["posts_por_semana_ult_90"] >= 2 else 10,
                      f"{frec_actual['posts_ult_90_dias']} posts en 90 días ({frec_actual['posts_por_semana_ult_90']} por semana)"),
        "Tracción": (20 if ig_rate >= 3 else 10 if ig_rate >= 1 else 0,
                     f"{igp['followersCount']:,} seguidores; interacción mediana de {ig_rate:.2f}% por post (últimos 12 meses)"),
        "Conversión": (20, "La bio enlaza al sitio y a WhatsApp Business"),
    }},
    {"canal": "TikTok", "detalle": "@cisnenegro.mx", "puntos": {
        "Presencia": (10, "Perfil con bio, sin enlace en la bio"),
        "Exactitud": (10, "Nombre correcto; sin dirección ni horario"),
        "Actividad": (0, f"Último video: {tiktok['ultimo_post']} ({tiktok['dias_sin_publicar']} días sin publicar)"),
        "Tracción": (10, f"{tiktok['seguidores']} seguidores, pero un video llegó a {viral['playCount']:,} vistas"),
        "Conversión": (0, "Sin enlace ni llamada a la acción vigente"),
    }},
    {"canal": "Facebook", "detalle": "/cerveceriacisnenegro.mx", "puntos": {
        "Presencia": (10, "La página existe, pero no se puede ver sin iniciar sesión"),
        "Exactitud": (0, "No verificable sin sesión"),
        "Actividad": (0, "No verificable sin sesión"),
        "Tracción": (0, "Sin calificación pública ('Not yet rated', 2 reseñas)"),
        "Conversión": (0, "Un visitante sin cuenta no ve datos de contacto"),
    }},
    {"canal": "Google", "detalle": "Perfil de Empresa", "puntos": {
        "Presencia": (10, f"Ficha reclamada con {gm['imagesCount']} fotos, pero sin menú, reservas ni publicaciones"),
        "Exactitud": (10, "Teléfono y horario correctos; categoría solo 'Restaurante' y nombre 'Cisne Negro'"),
        "Actividad": (10, "Recibe reseñas cada mes, pero el dueño no publica nada"),
        "Tracción": (10, f"{gm['totalScore']} ★ es alto, pero {gm['reviewsCount']} reseñas es poco volumen (umbral: 100)"),
        "Conversión": (10, f"Enlaza web y teléfono, pero {respondidas} de {gm['reviewsCount']} reseñas tienen respuesta"),
    }},
    {"canal": "Tripadvisor / Untappd", "detalle": "fichas de terceros", "puntos": {
        "Presencia": (10, "Hay ficha en Tripadvisor; en Untappd no existe perfil"),
        "Exactitud": (0, "Tripadvisor la marca como 'temporalmente cerrado'"),
        "Actividad": (0, "0 reseñas en Tripadvisor y 0 check-ins en Untappd"),
        "Tracción": (0, "Sin prueba social en los canales del turista y del público cervecero"),
        "Conversión": (0, "Un turista que la encuentra la descarta por 'cerrado'"),
    }},
]
for c in canales:
    c["score"] = sum(v[0] for v in c["puntos"].values())
    c["puntos"] = [{"dimension": k, "pts": v[0], "motivo": v[1]} for k, v in c["puntos"].items()]
score_global = round(sum(c["score"] for c in canales) / len(canales))

# ---------------------------------------------------------------- KPIs
kpis = {
    "ig_seguidores": igp["followersCount"], "ig_posts": igp["postsCount"], "ig_analizados": len(ig),
    "google_rating": gm["totalScore"], "google_resenas": gm["reviewsCount"], "google_respondidas": respondidas,
    "tiktok_viral_vistas": viral["playCount"], "posts_por_semana": frec_actual["posts_por_semana_ult_90"],
    "score_global": score_global, "ig_tasa_interaccion": round(ig_rate, 2),
}

# ---------------------------------------------------------------- Datos externos (con fuente)
# Verificados a mano; cada fila lleva su fuente y fecha. "s/d" = sin dato verificable.
HOR_OK = "Mar–Jue 16–22 · Vie–Sáb 16–23:30 · Dom 14–19 · Lun cerrado"
nap = [
    {"canal": "Sitio cisnenegro.mx", "nombre": "Cisne Negro", "telefono": "(771) 244-2025", "horario": "Mar–Jue 16–22 · Vie–Sáb 16–23:30 · Dom 14–19 (lunes no aparece)",
     "estado": "Activo", "nivel": "ok", "nota": "Datos correctos; no enlaza redes ni WhatsApp",
     "fuente": "HTML descargado el 2026-10-06 (contenido/sitio-web/)"},
    {"canal": "Landing Abacus", "nombre": "Cisne Negro — Cervecería Mexicana Independiente", "telefono": "(771) 123-4567",
     "horario": "Lun–Jue 14–23 · Vie–Sáb 13–24 · Dom 13–21", "estado": "Publicada", "nivel": "error",
     "nota": "Teléfono falso; abre en lunes y los tres rangos de horario son incorrectos",
     "fuente": "cisne-negro-landing-a2w76y.abacusai.app, consultada el 2026-10-06"},
    {"canal": "Google", "nombre": gm["title"], "telefono": gm["phone"].replace("+52 ", "(").replace(" 244", ") 244-").replace("244- ", "244-"),
     "horario": "Mar–Jue 16–22 · Vie–Sáb 16–23:30 · Dom 14–19 · Lun cerrado", "estado": "Abierto", "nivel": "aviso",
     "nota": "Datos correctos, pero la categoría es solo 'Restaurante' y el nombre no dice 'Cervecería'",
     "fuente": "Ficha de Google Maps, scraping del 2026-10-06"},
    {"canal": "Instagram", "nombre": igp["fullName"], "telefono": "No visible (enlace a WhatsApp Business)",
     "horario": "Solo en la historia destacada 'Horario'", "estado": "Activo", "nivel": "aviso",
     "nota": "Ni la bio ni el perfil muestran dirección u horario", "fuente": "Perfil @cisnenegro.mx, scraping del 2026-10-06"},
    {"canal": "Facebook", "nombre": "s/d", "telefono": "s/d", "horario": "s/d", "estado": "Bloqueado sin sesión", "nivel": "aviso",
     "nota": "Sin calificación pública ('Not yet rated', 2 reseñas)", "fuente": "facebook.com/cerveceriacisnenegro.mx (2026-10-05/06)"},
    {"canal": "Tripadvisor", "nombre": "Cisne Negro", "telefono": "s/d", "horario": "s/d", "estado": "Temporalmente cerrado", "nivel": "error",
     "nota": "Clasificado como 'American, Brew Pub', con 0 reseñas", "fuente": "Tripadvisor, revisión del 2026-10-05 (el 2026-10-06 bloqueó la consulta automática)"},
    {"canal": "Uber Eats", "nombre": "Cisne Negro", "telefono": "s/d", "horario": "s/d", "estado": "Activo", "nivel": "aviso",
     "nota": "Tienda activa; revisar fotos y descripción", "fuente": "Uber Eats, revisión del 2026-10-05 (el 2026-10-06 bloqueó la consulta automática)"},
]
seo = {
    "busqueda_generica": {"consulta": "cisne negro", "fecha": "2026-10-06", "aparece_la_cerveceria": False,
                          "que_aparece": ["La película El cisne negro (2010)", "La teoría del cisne negro de Nassim Taleb", "Un libro titulado Cisne Negro", "El ave (Cygnus atratus)"]},
    "busqueda_local": {"consulta": "cerveza artesanal Pachuca taproom", "fecha": "2026-10-06", "aparece_sitio_propio": False,
                       "que_aparece": ["Perfil en Untappd de Cervecería Pachuca (primer resultado)", "Notas de prensa locales (La Silla Rota, El Universal Hidalgo, Criterio Hidalgo)",
                                       "Sitios propios de competidores en Pachuca (Buesjo Brewer Co., Cervecería Pamplona)", "Páginas de Facebook de otras cervecerías locales"]},
    "limitacion": "La herramienta de búsqueda usa resultados de EE. UU.; una búsqueda desde Pachuca con ubicación activa mostraría el mapa local. No hay datos de volumen de búsqueda: validar con Search Console.",
    "titulo_sitio": "Cisne Negro", "meta_description": "",
}
# Benchmark local: consulta del 2026-10-06. Google = búsqueda pública de Google Maps sin sesión;
# IG = meta og:description del perfil; "probable" = la cuenta no se pudo confirmar como oficial.
benchmark = {
    "fecha": "2026-10-06",
    "filas": [
        {"nombre": "Cervecería Cisne Negro", "ubicacion": "Pachuca", "google_rating": f"{gm['totalScore']}", "google_resenas": f"{gm['reviewsCount']}",
         "google_categoria": ", ".join(gm["categories"]), "google_fuente": "https://www.google.com/maps/search/?api=1&query=Cisne+Negro+Pachuca",
         "ig": f"{igp['followersCount']:,} (@{igp['username']})", "ig_fuente": "https://www.instagram.com/cisnenegro.mx/",
         "untappd": "Sin perfil", "untappd_fuente": None, "sitio": "Sí (cisnenegro.mx)", "otros": "Tripadvisor la marca como 'temporalmente cerrado'", "es_cliente": True},
        {"nombre": "La Vizcaína", "ubicacion": "Mineral del Monte (Real del Monte)", "google_rating": "4.8", "google_resenas": "458",
         "google_categoria": "Cervecería artesanal, Cervecería", "google_fuente": "https://www.google.com/maps/search/?api=1&query=La+Vizca%C3%ADna+Cervecer%C3%ADa+Artesanal+de+Real+del+Monte",
         "ig": "3,139 (@lavizcainabrew)", "ig_fuente": "https://www.instagram.com/lavizcainabrew/",
         "untappd": "3.58 · 154 calificaciones", "untappd_fuente": "https://untappd.com/w/la-vizcaina/331532", "sitio": "No (Facebook como sitio)",
         "otros": "Tripadvisor: 5.0 con 1 y 3 opiniones (solo visto en resultados de búsqueda)"},
        {"nombre": "Cervecería Hacienda", "ubicacion": "Zempoala", "google_rating": "5.0", "google_resenas": "3",
         "google_categoria": "Fábrica (el recinto, Hacienda San Juan Pueblilla, tiene 4.6 ★ con 219 reseñas)", "google_fuente": "https://www.google.com/maps/search/?api=1&query=Cerveceria+Hacienda+Zempoala",
         "ig": "2,107 (@cerveceriahacienda, probable)", "ig_fuente": "https://www.instagram.com/cerveceriahacienda/",
         "untappd": "3.08 · 1,427 calificaciones · 1,705 check-ins", "untappd_fuente": "https://untappd.com/w/cerveceria-hacienda/6143",
         "sitio": "Caído (cerveceriahacienda.com no resuelve)", "otros": "Sin ficha en Tripadvisor"},
        {"nombre": "La Minera", "ubicacion": "Zimapán", "google_rating": "4.8", "google_resenas": "5",
         "google_categoria": "Bar", "google_fuente": "https://www.google.com/maps/search/?api=1&query=Cerveceria+La+Minera+Zimapan",
         "ig": "833 (@cerveceriaartesanallaminera, probable)", "ig_fuente": "https://www.instagram.com/cerveceriaartesanallaminera/",
         "untappd": "Sin perfil", "untappd_fuente": None, "sitio": "No",
         "otros": "Facebook: 1,894 seguidores y 208 check-ins (la única página sin restricción de edad)"},
    ],
    "notas": [
        "La Vizcaína es la referencia: tiene 6.6 veces las reseñas de Google de Cisne Negro (458 contra 69), mejor calificación y su categoría de Google es 'Cervecería artesanal'. Cisne Negro le gana en seguidores de Instagram y es la única de las cuatro con un sitio propio funcionando.",
        "El caso de Cervecería Hacienda muestra el peso de Untappd: casi no tiene reseñas de Google, pero acumula 1,705 check-ins ahí. Cisne Negro no tiene perfil.",
        "Las cuentas marcadas 'probable' coinciden en nombre, pero no se pudo ver su bio por la restricción de edad. Los seguidores de Facebook de Hacienda y La Vizcaína quedan s/d por la misma razón.",
    ],
    "fuentes": [
        {"titulo": "La Silla Rota (jun 2026)", "url": "https://lasillarota.com/hidalgo/vida/2026/6/25/hidalgo-tambien-se-bebe-conoce-la-cerveza-artesanal-del-estado-517466.html"},
        {"titulo": "Google Maps: La Vizcaína", "url": "https://www.google.com/maps/search/?api=1&query=La+Vizca%C3%ADna+Cervecer%C3%ADa+Artesanal+de+Real+del+Monte"},
        {"titulo": "Google Maps: Cervecería Hacienda", "url": "https://www.google.com/maps/search/?api=1&query=Cerveceria+Hacienda+Zempoala"},
        {"titulo": "Google Maps: Hacienda San Juan Pueblilla", "url": "https://www.google.com/maps/search/?api=1&query=Hacienda+San+Juan+Pueblilla+Zempoala"},
        {"titulo": "Google Maps: La Minera", "url": "https://www.google.com/maps/search/?api=1&query=Cerveceria+La+Minera+Zimapan"},
        {"titulo": "Instagram @lavizcainabrew", "url": "https://www.instagram.com/lavizcainabrew/"},
        {"titulo": "Instagram @cerveceriahacienda", "url": "https://www.instagram.com/cerveceriahacienda/"},
        {"titulo": "Instagram @cerveceriaartesanallaminera", "url": "https://www.instagram.com/cerveceriaartesanallaminera/"},
        {"titulo": "Facebook La Minera", "url": "https://www.facebook.com/cerveceriaalaminera.zim/"},
        {"titulo": "Untappd Hacienda", "url": "https://untappd.com/w/cerveceria-hacienda/6143"},
        {"titulo": "Untappd La Vizcaína", "url": "https://untappd.com/w/la-vizcaina/331532"},
        {"titulo": "Wanderlog (La Vizcaína)", "url": "https://wanderlog.com/place/details/630878/la-vizca%C3%ADna-cervecer%C3%ADa-artesanal-de-real-del-monte"},
    ],
}
data = {
    "generado": "2026-10-06", "fuente_scraping": ds["generado"],
    "kpis": kpis, "rubrica": RUBRICA, "canales": canales,
    "instagram": {"formato": formato, "frecuencia": frecuencia, "meses_cero": meses_cero, "frec_actual": frec_actual,
                  "heatmap": heatmap, "dias": dia_stats, "franjas": franja_stats, "mejor": mejor, "top10": top10,
                  "temas": temas, "hashtags": hashtags, "hueco": hueco_ig,
                  "reglas_temas": {k: len(v) for k, v in TEMAS.items()}},
    "tiktok": tiktok, "google": google, "nap": nap, "seo": seo, "benchmark": benchmark,
}
out = AQUI / "data.json"
publico = json.loads(json.dumps(data, ensure_ascii=False, default=str))
for t in publico["instagram"]["top10"]:
    t.pop("carpeta")
out.write_text(json.dumps(publico, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"OK {out} · score global {score_global} · IG {len(ig)} posts · reseñas {len(res)}")

if "--thumbs" in sys.argv:
    (AQUI / "img").mkdir(exist_ok=True)
    for t in data["instagram"]["top10"]:
        src = RAIZ / t["carpeta"] / "01.jpg"
        dst = AQUI / t["img"]
        subprocess.run(["sips", "-Z", "480", "-s", "format", "jpeg", "-s", "formatOptions", "72", str(src), "--out", str(dst)],
                       check=True, capture_output=True)
    subprocess.run(["sips", "-Z", "320", "-s", "format", "jpeg", "-s", "formatOptions", "72",
                    str(AQUI.parent / "assets/img/marca/cisne-mascota.jpg"), "--out", str(AQUI / "img/mascota.jpg")],
                   check=True, capture_output=True)
    print("miniaturas y mascota copiadas")

if "--embed" in sys.argv:
    html = (AQUI / "index.html").read_text(encoding="utf-8")
    blob = json.dumps(publico, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    nuevo = re.sub(r'(<script id="datos" type="application/json">).*?(</script>)',
                   lambda m: m.group(1) + blob + m.group(2), html, count=1, flags=re.S)
    (AQUI / "index.html").write_text(nuevo, encoding="utf-8")
    print("data.json embebido en index.html")

if "--debug" in sys.argv:
    for p in sorted(ig, key=lambda p: p["fecha"]):
        print(p["tema"][:8], p["inter"], "|", p["texto"].replace("\n", " ")[:90])
