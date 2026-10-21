#!/usr/bin/env python3
"""Línea base de contenido — Cervecería Cisne Negro (solo lectura del repo).
Lee scraping/raw/ig-posts-full-20261006.json, ig-profile, tiktok-20261006.json.
Escribe /tmp/cn/contenido-analisis/resumen-linea-base.json
Interacción IG = likes + comentarios (compartidos/guardados NO existen en datos públicos).
Interacción TikTok = likes + comentarios + compartidos + guardados.
Hora local: America/Mexico_City = UTC-6 fijo (sin horario de verano desde oct 2022; datos desde nov 2023).
"""
import json, re, statistics as st, unicodedata, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
RAW = RAIZ / "scraping/raw"
OUT = Path("/tmp/cn/contenido-analisis/resumen-linea-base.json")
CDMX = timezone(timedelta(hours=-6))
CORTE = datetime(2026, 10, 6, tzinfo=timezone.utc)

ig = json.load(open(RAW / "ig-posts-full-20261006.json", encoding="utf-8"))
prof = json.load(open(RAW / "ig-profile-20261006.json", encoding="utf-8"))
prof = prof[0] if isinstance(prof, list) else prof
tt = json.load(open(RAW / "tiktok-20261006.json", encoding="utf-8"))
FOLL = prof["followersCount"]
TT_FOLL = tt[0]["authorMeta"]["fans"]

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()

def r(x, n=1):
    return None if x is None else round(x, n)

def stats(v):
    v = [x for x in v if x is not None]
    if not v:
        return {"n": 0}
    return {"n": len(v), "media": r(st.mean(v)), "mediana": r(st.median(v)),
            "min": min(v), "max": max(v), "p75": r(sorted(v)[int(0.75 * (len(v) - 1))])}

FMT = {"Image": "imagen", "Video": "reel", "Sidecar": "carrusel"}
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
def franja(h):
    if h < 6: return "Madrugada 00-05"
    if h < 12: return "Mañana 06-11"
    if h < 15: return "Mediodía 12-14"
    if h < 19: return "Tarde 15-18"
    return "Noche 19-23"

# ---- categorías por palabras clave (multi-etiqueta; primaria por prioridad)
CATS = [
 ("eventos_colaboraciones", r"oktoberfest|pop ?up|takeover|kitchen|aniversario|anniversary|cumple|ano ii|noche de velas|pizza|yoga|circuito|expositor|documental|crudo|halloween|disfraz|posada|ride n|alttar|jabonera|evento|estreno|festej|cartelera|nos presentan|a cargo de|ft\.|feat"),
 ("promos", r"regalamos|promocion|gratis|2x1|descuento|nada o todo|cuenton|\$\d|precio|en la compra"),
 ("avisos_horarios", r"proximamente|ya abrimos|estamos abiertos|horario|a partir de las|de martes a domingo|martes a domingo|servicio de|los esperamos hoy de"),
 ("behind_the_scenes", r"dry ?hop|cebada|maltead|donde sucede la magia|produccion|lunes de|cocinamos|proceso|brewing|el lugar mas importante|hoy conectamos|conectar chelas|ya conectada|la parrilla"),
 ("producto_cerveza", r"\bipa\b|stout|lager|festbier|pils|hazy|sour|berliner|agua puerca|a poco si|henry|matador|barrilete|karnaval|carabela|joyas ayala|ejercicio|flight|vuelo|growler|lata|tap ?list|tap handle|barril|cerveza (independiente|artesanal)|nuestras? (ipa|cerveza)|abv|ibu|vacio ?barril|cheve|chela"),
 ("efemerides_temporada", r"navidad|christmas|reyes|ano nuevo|newyear|2025|2026|15 ?septiembre|independencia|viva ?mexico|dia de la (cerveza|hamburguesa)|burger day|cuaresma|san valentin|14 de febrero|valentines|papa|futbol|soccer|beis|mundial|gol\b|temporada"),
 ("comida", r"hamburguesa|burger|papas|dona|doughnut|ceviche|croqueta|costrit|tlayuda|tartar|sandwich|sándwich|suadero|philly|campechana|postre|aguachile|coliflor|taco|salchicha|platillo|menu|comida|camarones|burro|pollo|ensalada|pretzel|cocina"),
 ("comunidad_ambiente", r"amig|friends|petfriendly|pet friendly|patita|dog|resena|etiqueta a|compitas|juegos de mesa|terraza|lugar feliz|facade|todos son bienvenidos|cervezaparatodos|platica|conversacion|chisme|club social|gracias|ustedes|frankfurt|estuvo aqui"),
 ("humor_tendencia", r"\bpov\b|definicion|definition|si te aparecio|guia para|prioridades|caos|copy|paste|beerstateofmind|meme|si tu me quieres|merecemos|sobredosis"),
]
PRIO = [c for c, _ in CATS]

def categorias(texto, collab):
    t = norm(texto)
    labs = [c for c, rx in CATS if re.search(rx, t)]
    if collab and "eventos_colaboraciones" not in labs:
        labs.insert(0, "eventos_colaboraciones")
    if not labs:
        labs = ["otros"]
    prim = next((c for c in PRIO if c in labs), "otros")
    return prim, labs

posts = []
for x in ig:
    dt = datetime.fromisoformat(x["timestamp"].replace("Z", "+00:00"))
    loc = dt.astimezone(CDMX)
    cap = x.get("caption") or ""
    collab = bool(x.get("coauthorProducers"))
    prim, labs = categorias(cap, collab)
    likes, com = x.get("likesCount") or 0, x.get("commentsCount") or 0
    posts.append({
        "id": x["shortCode"], "url": x["url"], "fecha_utc": x["timestamp"],
        "fecha_local": loc.strftime("%Y-%m-%d %H:%M"), "anio": loc.year,
        "dia": DIAS[loc.weekday()], "hora": loc.hour, "franja": franja(loc.hour),
        "formato": FMT[x["type"]], "likes": likes, "comentarios": com,
        "inter": likes + com, "er_pct": r(100 * (likes + com) / FOLL, 2),
        "vistas": x.get("videoViewCount"), "reproducciones": x.get("videoPlayCount"),
        "collab": collab, "hashtags": x.get("hashtags") or [],
        "menciones": x.get("mentions") or [], "categoria": prim, "etiquetas": labs,
        "caption": cap.replace("\n", " ")[:220], "dt": dt,
    })
posts.sort(key=lambda p: p["dt"])

# índice relativo a la mediana del año (la cuenta creció)
med_anio = {a: st.median([p["inter"] for p in posts if p["anio"] == a]) for a in {p["anio"] for p in posts}}
for p in posts:
    p["indice_anio"] = r(p["inter"] / med_anio[p["anio"]], 2)

def ventana(dias):
    return [p for p in posts if p["dt"] >= CORTE - timedelta(days=dias)]

def por_formato(ps):
    out = {}
    for f in ["reel", "carrusel", "imagen"]:
        sub = [p for p in ps if p["formato"] == f]
        d = {"interaccion": stats([p["inter"] for p in sub]),
             "likes": stats([p["likes"] for p in sub]),
             "comentarios": stats([p["comentarios"] for p in sub]),
             "er_pct_sobre_seguidores": stats([p["er_pct"] for p in sub]),
             "interaccion_sin_collab": stats([p["inter"] for p in sub if not p["collab"]])}
        if f == "reel":
            d["vistas_videoViewCount"] = stats([p["vistas"] for p in sub])
            d["reproducciones_videoPlayCount"] = stats([p["reproducciones"] for p in sub])
            d["interaccion_por_100_vistas"] = stats([100 * p["inter"] / p["vistas"] for p in sub if p["vistas"]])
        out[f] = d
    out["total"] = {"interaccion": stats([p["inter"] for p in ps]),
                    "er_pct_sobre_seguidores": stats([p["er_pct"] for p in ps]),
                    "interaccion_sin_collab": stats([p["inter"] for p in ps if not p["collab"]])}
    return out

def grupo(ps, key, orden=None, min_n=1):
    g = defaultdict(list)
    for p in ps:
        for k in (p[key] if isinstance(p[key], list) else [p[key]]):
            g[k].append(p)
    keys = orden or sorted(g)
    res = []
    for k in keys:
        sub = g.get(k, [])
        if not sub:
            res.append({"grupo": k, "n": 0}); continue
        res.append({"grupo": k, "n": len(sub),
                    "inter_media": r(st.mean(p["inter"] for p in sub)),
                    "inter_mediana": r(st.median(p["inter"] for p in sub)),
                    "indice_anio_mediano": r(st.median(p["indice_anio"] for p in sub), 2),
                    "muestra_suficiente": len(sub) >= min_n})
    return res

def resumen_post(p):
    return {k: p[k] for k in ["fecha_local", "dia", "formato", "likes", "comentarios", "inter",
                              "indice_anio", "collab", "categoria", "etiquetas", "url", "caption"]}

ult12 = ventana(365)
ult6 = ventana(183)
FRANJAS = ["Mañana 06-11", "Mediodía 12-14", "Tarde 15-18", "Noche 19-23", "Madrugada 00-05"]

# heatmap día × franja (índice año)
heat = []
for d in DIAS:
    for f in FRANJAS:
        sub = [p for p in posts if p["dia"] == d and p["franja"] == f]
        if sub:
            heat.append({"dia": d, "franja": f, "n": len(sub),
                         "indice_anio_mediano": r(st.median(p["indice_anio"] for p in sub), 2),
                         "inter_mediana": r(st.median(p["inter"] for p in sub))})

ht = Counter(h.lower() for p in posts for h in p["hashtags"])
ht12 = Counter(h.lower() for p in ult12 for h in p["hashtags"])
mn = Counter(m.lower() for p in posts for m in p["menciones"])
# hashtags con desempeño (n>=5)
ht_perf = []
for h, n in ht.most_common():
    if n < 5: break
    sub = [p for p in posts if h in [x.lower() for x in p["hashtags"]]]
    ht_perf.append({"hashtag": h, "n": n, "indice_anio_mediano": r(st.median(p["indice_anio"] for p in sub), 2)})

# frecuencia
por_mes = Counter(p["dt"].astimezone(CDMX).strftime("%Y-%m") for p in posts)

# eras de voz: antes del hueco (hasta 2024-07-06) vs después
era1 = [p for p in posts if p["dt"] < datetime(2024, 9, 1, tzinfo=timezone.utc)]
era2 = [p for p in posts if p["dt"] >= datetime(2024, 9, 1, tzinfo=timezone.utc)]

# ---------- TikTok
tposts = []
for x in tt:
    tposts.append({
        "id": x["id"], "url": x["webVideoUrl"], "fecha_utc": x["createTimeISO"],
        "fecha_local": datetime.fromisoformat(x["createTimeISO"].replace("Z", "+00:00")).astimezone(CDMX).strftime("%Y-%m-%d %H:%M"),
        "formato": "slideshow" if x.get("isSlideshow") else "video",
        "vistas": x.get("playCount"), "likes": x.get("diggCount"), "comentarios": x.get("commentCount"),
        "compartidos": x.get("shareCount"), "guardados": x.get("collectCount"),
        "inter": sum((x.get(k) or 0) for k in ["diggCount", "commentCount", "shareCount", "collectCount"]),
        "duracion_s": (x.get("videoMeta") or {}).get("duration"),
        "texto": (x.get("text") or "")[:200], "hashtags": [h.get("name") for h in x.get("hashtags") or []],
    })
tposts.sort(key=lambda p: p["fecha_utc"])
def tt_fmt(ps):
    out = {}
    for f in ["video", "slideshow"]:
        sub = [p for p in ps if p["formato"] == f]
        out[f] = {k: stats([p[k] for p in sub]) for k in ["vistas", "likes", "comentarios", "compartidos", "guardados", "inter"]}
        out[f]["er_pct_sobre_vistas"] = stats([r(100 * p["inter"] / p["vistas"], 2) for p in sub if p["vistas"]])
    return out
viral = max(tposts, key=lambda p: p["vistas"] or 0)

res = {
    "generado": datetime.now(CDMX).strftime("%Y-%m-%d %H:%M"),
    "fuentes": ["scraping/raw/ig-posts-full-20261006.json", "scraping/raw/ig-profile-20261006.json",
                "scraping/raw/tiktok-20261006.json"],
    "notas": [
        "IG: interacción = likes + comentarios. Compartidos, guardados y alcance NO están en datos públicos (requiere Insights, backlog B2).",
        "IG: 200 de 245 posts (los 45 anteriores a 2023-11-18 no se pudieron obtener sin sesión).",
        "ER% = interacción / seguidores actuales (3,513 al 2026-10-06); no hay histórico de seguidores, así que el ER de posts antiguos está subestimado respecto a su momento.",
        "Reels: videoViewCount (vistas) y videoPlayCount (reproducciones) vienen del scraper; Instagram no aclara la diferencia públicamente.",
        "Categorías por reglas de palabras clave (multi-etiqueta; primaria por prioridad). Posts con coautor (collab) se cuentan como eventos/colaboraciones.",
        "indice_anio = interacción / mediana del año del post (normaliza el crecimiento de la cuenta).",
        "Hora local CDMX = UTC-6.",
    ],
    "instagram": {
        "perfil": {"usuario": prof["username"], "nombre": prof["fullName"], "seguidores": FOLL,
                   "siguiendo": prof["followsCount"], "posts_totales": prof["postsCount"],
                   "bio": prof["biography"], "enlaces": [u["url"] for u in prof.get("externalUrls") or []]},
        "posts_analizados": len(posts),
        "rango": [posts[0]["fecha_local"], posts[-1]["fecha_local"]],
        "conteo_formato": dict(Counter(p["formato"] for p in posts)),
        "posts_collab": sum(p["collab"] for p in posts),
        "por_formato_todo": por_formato(posts),
        "por_formato_ult_12_meses": por_formato(ult12),
        "por_formato_ult_6_meses": por_formato(ult6),
        "n_ult_12_meses": len(ult12), "n_ult_6_meses": len(ult6),
        "mediana_inter_por_anio": {str(k): v for k, v in sorted(med_anio.items())},
        "por_dia": grupo(posts, "dia", DIAS, 10),
        "por_franja": grupo(posts, "franja", FRANJAS, 10),
        "por_dia_ult_12m": grupo(ult12, "dia", DIAS, 5),
        "por_franja_ult_12m": grupo(ult12, "franja", FRANJAS, 5),
        "heatmap_dia_franja": heat,
        "por_categoria_primaria": grupo(posts, "categoria"),
        "por_etiqueta_multi": grupo(posts, "etiquetas"),
        "por_categoria_primaria_ult_12m": grupo(ult12, "categoria"),
        "collab_vs_propio": grupo(posts, "collab"),
        "eras_voz": {"hasta_2024_08 (copy genérico 'Descubre…')": {"n": len(era1), **stats([p["inter"] for p in era1])},
                     "desde_2024_09 (voz con humor/eventos)": {"n": len(era2), **stats([p["inter"] for p in era2])}},
        "top10": [resumen_post(p) for p in sorted(posts, key=lambda p: -p["inter"])[:10]],
        "bottom5": [resumen_post(p) for p in sorted(posts, key=lambda p: (p["inter"], p["dt"]))[:5]],
        "top5_indice_anio": [resumen_post(p) for p in sorted(posts, key=lambda p: -p["indice_anio"])[:5]],
        "bottom5_ult_12m": [resumen_post(p) for p in sorted(ult12, key=lambda p: p["inter"])[:5]],
        "hashtags_top": ht.most_common(25),
        "hashtags_top_ult_12m": ht12.most_common(15),
        "hashtags_desempeno_n5": ht_perf,
        "posts_sin_hashtags": sum(1 for p in posts if not p["hashtags"]),
        "hashtags_unicos": len(ht),
        "menciones_top": mn.most_common(15),
        "posts_por_mes": dict(sorted(por_mes.items())),
        "ultimo_post": posts[-1]["fecha_local"],
        "posts_ult_30_dias": len(ventana(30)), "posts_ult_90_dias": len(ventana(90)),
        "interaccion_ideal_propuesta": {
            "criterio": "Media de likes+comentarios de los últimos 12 meses por formato (método: interacción ideal = media). Sin compartidos/guardados hasta tener Insights.",
        },
    },
    "tiktok": {
        "seguidores": TT_FOLL, "likes_totales_perfil": tt[0]["authorMeta"]["heart"],
        "bio": tt[0]["authorMeta"]["signature"], "bio_link": tt[0]["authorMeta"].get("bioLink"),
        "n_posts": len(tposts), "rango": [tposts[0]["fecha_local"], tposts[-1]["fecha_local"]],
        "dias_sin_publicar_al_corte": (CORTE - datetime.fromisoformat(tposts[-1]["fecha_utc"].replace("Z", "+00:00"))).days,
        "por_formato": tt_fmt(tposts),
        "por_formato_sin_viral": tt_fmt([p for p in tposts if p["id"] != viral["id"]]),
        "viral": viral,
        "posts": tposts,
        "hashtags_top": Counter(h.lower() for p in tposts for h in p["hashtags"] if h).most_common(15),
    },
}
ii = res["instagram"]["interaccion_ideal_propuesta"]
for f in ["reel", "carrusel", "imagen"]:
    a = res["instagram"]["por_formato_ult_12_meses"][f]
    ii[f] = {"media_12m": a["interaccion"].get("media"), "mediana_12m": a["interaccion"].get("mediana"),
             "media_12m_sin_collab": a["interaccion_sin_collab"].get("media"), "n": a["interaccion"]["n"]}
    sub = [p["inter"] for p in ult12 if p["formato"] == f]
    out_ = [v for v in sub if v > 10 * st.median(sub)]
    ii[f]["media_12m_sin_atipicos_>10x_mediana"] = r(st.mean([v for v in sub if v not in out_]))
    ii[f]["atipicos_excluidos"] = out_

for p in posts:
    p.pop("dt")
res["instagram"]["posts"] = posts
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print("OK", OUT)
