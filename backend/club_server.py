"""Club Cisne Negro: Pasaporte (visitas y cortesías), NPS, miembros y ranking.

Servidor HTTP sin dependencias externas (Python 3.11+ y SQLite). Corre detrás de nginx:
  /api/*        → API pública del menú (socios, check-in, NPS, ranking)
  /api/admin/*  → panel del personal (sesión CMS + token interno del proxy)

Sesión del socio: cookie HttpOnly `cn_sesion` de 180 días que pone el servidor (Safari no la
borra a los 7 días como al localStorage). También acepta `Authorization: Bearer <token>`.

Variables de entorno:
  CLUB_DB      ruta de la base SQLite        (default ./club.db)
  CLUB_SECRET  secreto para el código del día (obligatorio en producción)
  CLUB_PORT    puerto local                  (default 8790)
  CLUB_REVIEW_URL  enlace de Google al que se invita después del NPS
  CLUB_COOKIE_SECURE  "0" para desarrollo sin HTTPS (default "1")
"""
import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DB_PATH = os.environ.get("CLUB_DB", "club.db")
SECRET = os.environ.get("CLUB_SECRET", "dev-secret")
PORT = int(os.environ.get("CLUB_PORT", "8790"))
REVIEW_URL = os.environ.get(
    "CLUB_REVIEW_URL",
    "https://www.google.com/maps/place/Cisne+Negro/data=!4m2!3m1!1s0x0:0x2d58b94ff33d7e6b")
COOKIE_SECURE = os.environ.get("CLUB_COOKIE_SECURE", "1") != "0"
COOKIE = "cn_sesion"
STAFF_TOKEN = os.environ.get("CLUB_ADMIN_TOKEN", "")
TZ = timezone(timedelta(hours=-6))  # America/Mexico_City (sin horario de verano desde 2022)

# Recompensas por número de visita. El ciclo se repite cada 10 visitas.
RECOMPENSAS = {5: "Cerveza de barril de 4 oz de cortesía", 10: "Cerveza de barril de 12 oz de cortesía"}
CICLO = 10
VIGENCIA_DIAS = 30
SESION_DIAS = 180
SEGUIMIENTOS = ("nuevo", "contactado", "resuelto", "cerrado")

SCHEMA = """
create table if not exists socios (
  id integer primary key,
  nombre text not null,
  telefono text not null unique,
  pin_hash text not null,
  acepta_privacidad_at text not null,
  acepta_whatsapp integer not null default 0,
  creado_at text not null
);
create table if not exists sesiones (
  token text primary key,
  socio_id integer not null references socios(id),
  creado_at text not null
);
create table if not exists visitas (
  id integer primary key,
  socio_id integer not null references socios(id),
  dia text not null,
  creado_at text not null,
  unique (socio_id, dia)
);
create table if not exists recompensas (
  id integer primary key,
  socio_id integer not null references socios(id),
  visita_id integer references visitas(id),
  codigo text not null unique,
  nombre text not null,
  estado text not null default 'emitida',
  emitida_at text not null,
  vence_at text not null,
  canjeada_at text
);
create table if not exists nps (
  id integer primary key,
  socio_id integer not null references socios(id),
  visita_id integer not null unique references visitas(id),
  score integer not null check (score between 0 and 10),
  comentario text,
  creado_at text not null,
  seguimiento text not null default 'nuevo',
  notas text,
  actualizado_at text
);
create table if not exists clicks_resena (
  id integer primary key,
  socio_id integer references socios(id),
  visita_id integer references visitas(id),
  creado_at text not null
);
create index if not exists visitas_socio_idx on visitas (socio_id, dia);
create index if not exists nps_creado_idx on nps (creado_at);
"""

# Columnas agregadas después de la v1 (migración automática y sin pérdida de datos).
MIGRACIONES = {
    "socios": [("mostrar_ranking", "integer not null default 1"), ("notas", "text"),
               ("actualizado_at", "text")],
    "visitas": [("origen", "text not null default 'menu'")],
    "nps": [("origen", "text not null default 'menu'")],
}

_lock = threading.Lock()
_intentos: dict[str, list[float]] = {}


def ahora():
    return datetime.now(TZ)


def hoy():
    return ahora().date().isoformat()


def iso(dt=None):
    return (dt or ahora()).isoformat(timespec="seconds")


def db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("pragma foreign_keys = on")
    return con


def init_db():
    with db() as con:
        con.executescript(SCHEMA)
        con.execute("pragma journal_mode = wal")
        for tabla, cols in MIGRACIONES.items():
            existentes = {r["name"] for r in con.execute(f"pragma table_info({tabla})")}
            for nombre, tipo in cols:
                if nombre not in existentes:
                    con.execute(f"alter table {tabla} add column {nombre} {tipo}")


def codigo_del_dia(dia=None):
    dia = dia or hoy()
    digest = hmac.new(SECRET.encode(), dia.encode(), hashlib.sha256).hexdigest()
    return f"{int(digest[:8], 16) % 10000:04d}"


def hash_pin(telefono, pin):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), f"cn:{telefono}".encode(), 200_000).hex()


def normaliza_tel(tel):
    digitos = re.sub(r"\D", "", tel or "")
    if len(digitos) == 12 and digitos.startswith("52"):
        digitos = digitos[2:]
    return digitos if len(digitos) == 10 else None


def limitar(clave, maximo=8, ventana=300):
    """Rate limit en memoria: máximo N intentos por clave en la ventana (segundos)."""
    t = time.time()
    with _lock:
        lista = [x for x in _intentos.get(clave, []) if t - x < ventana]
        lista.append(t)
        _intentos[clave] = lista
        return len(lista) <= maximo


def entero(valor, defecto, minimo, maximo):
    try:
        return min(max(int(valor), minimo), maximo)
    except (TypeError, ValueError):
        return defecto


def score_valido(valor):
    """Score NPS estricto: entero de 0 a 10, o None si no es válido (no recorta)."""
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= 10 and str(valor).strip().lstrip("-").isdigit() else None


def alias_publico(nombre):
    """'Ana María Ruiz' → 'Ana R.' (lo que se ve en el ranking público)."""
    partes = (nombre or "").split()
    if not partes:
        return "Socio"
    return partes[0].capitalize() + (f" {partes[-1][0].upper()}." if len(partes) > 1 else "")


def nuevo_codigo(con):
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        codigo = "CN-" + "".join(secrets.choice(alfabeto) for _ in range(5))
        if not con.execute("select 1 from recompensas where codigo = ?", (codigo,)).fetchone():
            return codigo


def nueva_sesion(con, socio_id):
    token = secrets.token_urlsafe(32)
    con.execute("insert into sesiones values (?, ?, ?)", (token, socio_id, iso()))
    return token


def estado_socio(con, socio_id):
    s = con.execute("select id, nombre, telefono, mostrar_ranking from socios where id = ?",
                    (socio_id,)).fetchone()
    visitas = con.execute("select count(*) from visitas where socio_id = ?", (socio_id,)).fetchone()[0]
    visita_hoy = con.execute("select id from visitas where socio_id = ? and dia = ?", (socio_id, hoy())).fetchone()
    nps_hoy = bool(visita_hoy and con.execute(
        "select 1 from nps where visita_id = ?", (visita_hoy["id"],)).fetchone())
    recompensas = [dict(r) for r in con.execute(
        "select codigo, nombre, estado, vence_at from recompensas where socio_id = ? "
        "and estado = 'emitida' and vence_at >= ? order by emitida_at desc", (socio_id, iso()))]
    en_ciclo = visitas % CICLO
    siguiente = next((n for n in sorted(RECOMPENSAS) if n > en_ciclo), None)
    return {
        "nombre": s["nombre"], "alias": alias_publico(s["nombre"]), "telefono_final": s["telefono"][-4:],
        "visitas": visitas, "sellos_ciclo": en_ciclo if en_ciclo or not visitas else CICLO, "ciclo": CICLO,
        "proxima_recompensa": {"en_visita": siguiente, "faltan": siguiente - en_ciclo,
                               "nombre": RECOMPENSAS[siguiente]} if siguiente else None,
        "visita_hoy": visita_hoy["id"] if visita_hoy else None, "nps_hoy": nps_hoy,
        "recompensas": recompensas, "mostrar_ranking": bool(s["mostrar_ranking"]),
        "ranking": posicion_ranking(con, socio_id, "mes"),
    }


def registrar_visita(con, socio_id, origen="menu", dia=None):
    """Crea la visita del día (una por día) y emite la cortesía si toca. Devuelve (visita_id, nueva, recompensa)."""
    dia = dia or hoy()
    ya = con.execute("select id from visitas where socio_id = ? and dia = ?", (socio_id, dia)).fetchone()
    if ya:
        return ya["id"], False, None
    cur = con.execute("insert into visitas (socio_id, dia, creado_at, origen) values (?, ?, ?, ?)",
                      (socio_id, dia, iso(), origen))
    n = con.execute("select count(*) from visitas where socio_id = ?", (socio_id,)).fetchone()[0]
    recompensa = None
    nombre = RECOMPENSAS.get(((n - 1) % CICLO) + 1)
    if nombre:
        codigo = nuevo_codigo(con)
        vence = iso(ahora() + timedelta(days=VIGENCIA_DIAS))
        con.execute("insert into recompensas (socio_id, visita_id, codigo, nombre, emitida_at, vence_at) "
                    "values (?, ?, ?, ?, ?, ?)", (socio_id, cur.lastrowid, codigo, nombre, iso(), vence))
        recompensa = {"codigo": codigo, "nombre": nombre, "vence_at": vence}
    return cur.lastrowid, True, recompensa


def borrar_socio(con, socio_id):
    for tabla in ("clicks_resena", "nps", "recompensas", "sesiones", "visitas"):
        con.execute(f"delete from {tabla} where socio_id = ?", (socio_id,))
    return con.execute("delete from socios where id = ?", (socio_id,)).rowcount


# ── Ranking ────────────────────────────────────────────────────────────────

def _desde_periodo(periodo):
    hoy_d = ahora().date()
    if periodo == "mes":
        return hoy_d.replace(day=1).isoformat()
    if periodo == "semana":
        return (hoy_d - timedelta(days=hoy_d.weekday())).isoformat()
    return "0000-01-01"


def tabla_ranking(con, periodo="mes", limite=10, solo_publicos=True):
    """Ranking por visitas en el periodo. Desempate: llegó primero a ese número (última visita más antigua)."""
    filtro = "and s.mostrar_ranking = 1" if solo_publicos else ""
    rows = con.execute(
        f"select s.id, s.nombre, count(v.id) visitas, max(v.creado_at) ultima "
        f"from socios s join visitas v on v.socio_id = s.id and v.dia >= ? "
        f"where 1=1 {filtro} group by s.id order by visitas desc, ultima asc limit ?",
        (_desde_periodo(periodo), limite)).fetchall()
    return [{"posicion": i + 1, "socio_id": r["id"], "nombre": r["nombre"], "alias": alias_publico(r["nombre"]),
             "visitas": r["visitas"]} for i, r in enumerate(rows)]


def posicion_ranking(con, socio_id, periodo="mes"):
    """Posición con la misma numeración que el ranking público. Si el socio está oculto, se calcula
    como si apareciera (para que sepa dónde iría) y se marca `oculto`."""
    publico = con.execute("select mostrar_ranking from socios where id = ?", (socio_id,)).fetchone()
    oculto = bool(publico) and not publico["mostrar_ranking"]
    publicos = {r[0] for r in con.execute("select id from socios where mostrar_ranking = 1")}
    filas = [f for f in tabla_ranking(con, periodo, limite=100000, solo_publicos=False)
             if f["socio_id"] == socio_id or f["socio_id"] in publicos]
    for i, fila in enumerate(filas, 1):
        if fila["socio_id"] == socio_id:
            return {"periodo": periodo, "posicion": i, "visitas": fila["visitas"],
                    "participantes": len(filas), "oculto": oculto}
    return {"periodo": periodo, "posicion": None, "visitas": 0, "participantes": len(filas), "oculto": oculto}


# ── Handlers públicos ──────────────────────────────────────────────────────

def api_registro(h, body):
    nombre = (body.get("nombre") or "").strip()[:60]
    tel = normaliza_tel(body.get("telefono"))
    pin = str(body.get("pin") or "")
    if not nombre or not tel or not re.fullmatch(r"\d{4}", pin):
        return 400, {"error": "Escribe tu nombre, un teléfono de 10 dígitos y un PIN de 4 números."}
    if not body.get("acepta_privacidad"):
        return 400, {"error": "Necesitamos que aceptes el aviso de privacidad."}
    if not limitar("reg:" + h.ip(), 60, 3600):
        return 429, {"error": "Demasiados intentos. Prueba más tarde."}
    with db() as con:
        if con.execute("select 1 from socios where telefono = ?", (tel,)).fetchone():
            return 409, {"error": "Ese teléfono ya tiene Pasaporte. Entra con tu PIN."}
        cur = con.execute(
            "insert into socios (nombre, telefono, pin_hash, acepta_privacidad_at, acepta_whatsapp, creado_at) "
            "values (?, ?, ?, ?, ?, ?)",
            (nombre, tel, hash_pin(tel, pin), iso(), 1 if body.get("acepta_whatsapp") else 0, iso()))
        token = nueva_sesion(con, cur.lastrowid)
        h.cookie_sesion = token
        return 201, {"token": token, "socio": estado_socio(con, cur.lastrowid)}


def api_login(h, body):
    tel = normaliza_tel(body.get("telefono"))
    pin = str(body.get("pin") or "")
    if not limitar("login:" + h.ip(), 60, 300) or (tel and not limitar("login-tel:" + tel, 8, 300)):
        return 429, {"error": "Demasiados intentos. Espera 5 minutos."}
    with db() as con:
        s = con.execute("select id, pin_hash from socios where telefono = ?", (tel,)).fetchone() if tel else None
        if not s or not hmac.compare_digest(s["pin_hash"], hash_pin(tel, pin)):
            return 401, {"error": "Teléfono o PIN incorrectos."}
        token = nueva_sesion(con, s["id"])
        h.cookie_sesion = token
        return 200, {"token": token, "socio": estado_socio(con, s["id"])}


def api_yo(h, body, socio_id):
    with db() as con:
        return 200, {"socio": estado_socio(con, socio_id)}


def api_preferencias(h, body, socio_id):
    with db() as con:
        if "mostrar_ranking" in body:
            con.execute("update socios set mostrar_ranking = ?, actualizado_at = ? where id = ?",
                        (1 if body["mostrar_ranking"] else 0, iso(), socio_id))
        if "acepta_whatsapp" in body:
            con.execute("update socios set acepta_whatsapp = ?, actualizado_at = ? where id = ?",
                        (1 if body["acepta_whatsapp"] else 0, iso(), socio_id))
        return 200, {"socio": estado_socio(con, socio_id)}


def api_checkin(h, body, socio_id):
    if not limitar(f"checkin:{socio_id}", 6, 600):
        return 429, {"error": "Demasiados intentos. Pídele el código del día al equipo."}
    if str(body.get("codigo") or "").strip() != codigo_del_dia():
        return 400, {"error": "Ese no es el código de hoy. Pídeselo al equipo en la barra."}
    with db() as con:
        visita_id, nueva, recompensa = registrar_visita(con, socio_id)
        return (201 if nueva else 200), {"ya_registrada": not nueva, "visita_id": visita_id,
                                         "recompensa": recompensa, "socio": estado_socio(con, socio_id)}


def api_nps(h, body, socio_id):
    try:
        score = int(body.get("score"))
        visita_id = int(body.get("visita_id"))
    except (TypeError, ValueError):
        return 400, {"error": "Elige un número del 0 al 10."}
    if not 0 <= score <= 10:
        return 400, {"error": "Elige un número del 0 al 10."}
    comentario = (body.get("comentario") or "").strip()[:1000]
    with db() as con:
        if not con.execute("select 1 from visitas where id = ? and socio_id = ?", (visita_id, socio_id)).fetchone():
            return 404, {"error": "Primero registra tu visita de hoy."}
        previa = con.execute("select score from nps where visita_id = ?", (visita_id,)).fetchone()
        if previa:
            return 200, {"ya_respondida": True, "invitar_resena": True, "resena_url": REVIEW_URL,
                         "tono": tono_nps(previa["score"])}
        con.execute("insert into nps (socio_id, visita_id, score, comentario, creado_at) values (?, ?, ?, ?, ?)",
                    (socio_id, visita_id, score, comentario, iso()))
    # A todos se les invita a Google, sin premio: Google prohíbe pedir reseñas solo a quien califica alto.
    return 201, {"ya_respondida": False, "invitar_resena": True, "resena_url": REVIEW_URL, "tono": tono_nps(score)}


def tono_nps(score):
    return "promotor" if score >= 9 else "pasivo" if score >= 7 else "detractor"


def api_click_resena(h, body, socio_id):
    with db() as con:
        v = con.execute("select id from visitas where id = ? and socio_id = ?",
                        (body.get("visita_id"), socio_id)).fetchone()
        if not v:
            return 404, {"error": "Visita no encontrada"}
        if not con.execute("select 1 from clicks_resena where visita_id = ?", (v["id"],)).fetchone():
            con.execute("insert into clicks_resena (socio_id, visita_id, creado_at) values (?, ?, ?)",
                        (socio_id, v["id"], iso()))
    return 201, {"ok": True}


def api_logout(h, body, socio_id):
    with db() as con:
        con.execute("delete from sesiones where token = ?", (h.token(),))
    h.cookie_sesion = ""
    return 200, {"ok": True}


def api_ranking(h, q):
    periodo = q.get("periodo", ["mes"])[0]
    periodo = periodo if periodo in ("semana", "mes", "total") else "mes"
    with db() as con:
        filas = [{k: f[k] for k in ("posicion", "alias", "visitas")} for f in tabla_ranking(con, periodo, 10)]
        sid = h.socio_id()
        return 200, {"periodo": periodo, "ranking": filas, "yo": posicion_ranking(con, sid, periodo) if sid else None}


# ── Admin: KPIs ────────────────────────────────────────────────────────────

def _nps_score(scores):
    if not scores:
        return None
    return round((sum(1 for s in scores if s >= 9) - sum(1 for s in scores if s <= 6)) * 100 / len(scores))


def admin_resumen(h, q):
    dias = entero(q.get("dias", ["30"])[0], 30, 1, 365)
    desde = iso(ahora() - timedelta(days=dias))
    with db() as con:
        scores = [r[0] for r in con.execute("select score from nps where creado_at >= ?", (desde,))]
        prom = sum(1 for s in scores if s >= 9)
        det = sum(1 for s in scores if s <= 6)
        return 200, {
            "codigo_del_dia": codigo_del_dia(), "fecha": hoy(), "dias": dias,
            "socios": con.execute("select count(*) from socios").fetchone()[0],
            "socios_nuevos": con.execute("select count(*) from socios where creado_at >= ?", (desde,)).fetchone()[0],
            "visitas": con.execute("select count(*) from visitas where creado_at >= ?", (desde,)).fetchone()[0],
            "visitas_hoy": con.execute("select count(*) from visitas where dia = ?", (hoy(),)).fetchone()[0],
            "nps": {"respuestas": len(scores), "promotores": prom, "detractores": det,
                    "pasivos": len(scores) - prom - det, "score": _nps_score(scores)},
            "clicks_resena": con.execute("select count(*) from clicks_resena where creado_at >= ?",
                                         (desde,)).fetchone()[0],
            "recompensas": {r["estado"]: r["n"] for r in con.execute(
                "select estado, count(*) n from recompensas where emitida_at >= ? group by estado", (desde,))},
            "por_recuperar": con.execute("select count(*) from nps where score <= 6 and seguimiento in "
                                         "('nuevo','contactado')").fetchone()[0],
        }


def admin_estadisticas(h, q):
    """KPIs y series para gráficas del panel."""
    semanas = entero(q.get("semanas", ["12"])[0], 12, 4, 52)
    hoy_d = ahora().date()
    lunes = hoy_d - timedelta(days=hoy_d.weekday())
    inicios = [lunes - timedelta(weeks=i) for i in range(semanas - 1, -1, -1)]
    desde = inicios[0].isoformat()
    with db() as con:
        def por_semana(sql):
            conteo = {}
            for fila in con.execute(sql, (desde,)):
                d = date.fromisoformat(fila[0][:10])
                clave = (d - timedelta(days=d.weekday())).isoformat()
                conteo.setdefault(clave, []).append(fila[1] if len(fila) > 1 else 1)
            return conteo
        v_sem = por_semana("select dia from visitas where dia >= ?")
        s_sem = por_semana("select creado_at from socios where substr(creado_at,1,10) >= ?")
        n_sem = por_semana("select creado_at, score from nps where substr(creado_at,1,10) >= ?")
        serie = []
        for ini in inicios:
            k = ini.isoformat()
            sc = n_sem.get(k, [])
            serie.append({"semana": k, "visitas": len(v_sem.get(k, [])), "socios_nuevos": len(s_sem.get(k, [])),
                          "nps_respuestas": len(sc), "nps": _nps_score(sc)})
        todos = [r[0] for r in con.execute("select score from nps")]
        distribucion = [{"score": i, "n": todos.count(i)} for i in range(11)]
        dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        por_dia = {d: 0 for d in dias_semana}
        for (dia,) in con.execute("select dia from visitas"):
            por_dia[dias_semana[date.fromisoformat(dia).weekday()]] += 1
        total_socios = con.execute("select count(*) from socios").fetchone()[0]
        recurrentes = con.execute("select count(*) from (select socio_id from visitas group by socio_id "
                                  "having count(*) >= 2)").fetchone()[0]
        con_visita = con.execute("select count(distinct socio_id) from visitas").fetchone()[0]
        total_visitas = con.execute("select count(*) from visitas").fetchone()[0]
        total_nps = len(todos)
        activos_30 = con.execute("select count(distinct socio_id) from visitas where dia >= ?",
                                 ((hoy_d - timedelta(days=30)).isoformat(),)).fetchone()[0]
        emitidas = con.execute("select count(*) from recompensas").fetchone()[0]
        canjeadas = con.execute("select count(*) from recompensas where estado = 'canjeada'").fetchone()[0]
        clicks = con.execute("select count(*) from clicks_resena").fetchone()[0]
        pct = lambda a, b: round(a * 100 / b) if b else None  # noqa: E731
        return 200, {
            "kpis": {
                "socios": total_socios, "socios_activos_30d": activos_30,
                "visitas_totales": total_visitas,
                "visitas_por_socio": round(total_visitas / con_visita, 1) if con_visita else None,
                "retencion_pct": pct(recurrentes, con_visita),
                "nps": _nps_score(todos), "nps_promedio": round(sum(todos) / total_nps, 1) if total_nps else None,
                "tasa_respuesta_nps_pct": pct(total_nps, total_visitas),
                "clicks_resena": clicks, "tasa_resena_pct": pct(clicks, total_nps),
                "cortesias_emitidas": emitidas, "cortesias_canjeadas": canjeadas,
                "tasa_canje_pct": pct(canjeadas, emitidas),
                "optin_whatsapp_pct": pct(con.execute("select count(*) from socios where acepta_whatsapp = 1")
                                          .fetchone()[0], total_socios),
            },
            "semanal": serie, "distribucion_nps": distribucion,
            "visitas_por_dia": [{"dia": d, "n": n} for d, n in por_dia.items()],
        }


# ── Admin: CRUD NPS ────────────────────────────────────────────────────────

def admin_nps_lista(h, q):
    filtro = q.get("filtro", ["todos"])[0]
    buscar = (q.get("q", [""])[0] or "").strip().lower()
    limite = entero(q.get("limite", ["50"])[0], 50, 1, 500)
    pagina = entero(q.get("pagina", ["1"])[0], 1, 1, 10000)
    conds, params = [], []
    if filtro == "detractores":
        conds.append("n.score <= 6")
    elif filtro == "pasivos":
        conds.append("n.score between 7 and 8")
    elif filtro == "promotores":
        conds.append("n.score >= 9")
    elif filtro == "pendientes":
        conds.append("n.score <= 6 and n.seguimiento in ('nuevo','contactado')")
    if buscar:
        conds.append("(lower(s.nombre) like ? or s.telefono like ? or lower(coalesce(n.comentario,'')) like ?)")
        params += [f"%{buscar}%"] * 3
    where = ("where " + " and ".join(conds)) if conds else ""
    with db() as con:
        total = con.execute(f"select count(*) from nps n join socios s on s.id = n.socio_id {where}",
                            params).fetchone()[0]
        rows = con.execute(f"select n.id, n.score, n.comentario, n.creado_at, n.seguimiento, n.notas, n.origen, "
                           f"n.actualizado_at, s.id socio_id, s.nombre, s.telefono from nps n "
                           f"join socios s on s.id = n.socio_id {where} order by n.creado_at desc limit ? offset ?",
                           params + [limite, (pagina - 1) * limite]).fetchall()
        return 200, {"total": total, "pagina": pagina, "limite": limite, "respuestas": [dict(r) for r in rows]}


def admin_nps_crear(h, body):
    """Captura manual (encuesta en papel o de palabra). Se liga a la visita de hoy del socio."""
    sid = entero(body.get("socio_id"), 0, 0, 10**12)
    score = score_valido(body.get("score"))
    if score is None:
        return 400, {"error": "El score debe ser un número del 0 al 10."}
    with db() as con:
        if not con.execute("select 1 from socios where id = ?", (sid,)).fetchone():
            return 404, {"error": "Socio no encontrado."}
        visita_id, nueva, recompensa = registrar_visita(con, sid, origen="panel")
        if con.execute("select 1 from nps where visita_id = ?", (visita_id,)).fetchone():
            return 409, {"error": "Ese socio ya tiene NPS para su visita de hoy. Edítalo en lugar de crear otro."}
        cur = con.execute("insert into nps (socio_id, visita_id, score, comentario, creado_at, origen, seguimiento, "
                          "notas) values (?, ?, ?, ?, ?, 'panel', ?, ?)",
                          (sid, visita_id, score, (body.get("comentario") or "").strip()[:1000], iso(),
                           body.get("seguimiento") if body.get("seguimiento") in SEGUIMIENTOS else "nuevo",
                           (body.get("notas") or "")[:1000]))
        return 201, {"id": cur.lastrowid, "visita_nueva": nueva, "recompensa": recompensa}


def admin_nps_editar(h, body, nps_id):
    campos, params = [], []
    if "seguimiento" in body:
        if body["seguimiento"] not in SEGUIMIENTOS:
            return 400, {"error": "Estado inválido"}
        campos.append("seguimiento = ?"); params.append(body["seguimiento"])
    if "notas" in body:
        campos.append("notas = ?"); params.append((body.get("notas") or "")[:1000])
    if "comentario" in body:
        campos.append("comentario = ?"); params.append((body.get("comentario") or "")[:1000])
    if "score" in body:
        score = score_valido(body.get("score"))
        if score is None:
            return 400, {"error": "El score debe ser un número del 0 al 10."}
        campos.append("score = ?"); params.append(score)
    if not campos:
        return 400, {"error": "Nada que actualizar"}
    with db() as con:
        cur = con.execute(f"update nps set {', '.join(campos)}, actualizado_at = ? where id = ?",
                          params + [iso(), nps_id])
        if not cur.rowcount:
            return 404, {"error": "Respuesta no encontrada"}
    return 200, {"ok": True}


def admin_nps_borrar(h, nps_id):
    with db() as con:
        if not con.execute("delete from nps where id = ?", (nps_id,)).rowcount:
            return 404, {"error": "Respuesta no encontrada"}
    return 200, {"ok": True}


# ── Admin: CRUD miembros ───────────────────────────────────────────────────

SOCIO_COLS = ("s.id, s.nombre, s.telefono, s.creado_at, s.acepta_whatsapp, s.mostrar_ranking, s.notas, "
              "(select count(*) from visitas v where v.socio_id = s.id) visitas, "
              "(select max(dia) from visitas v where v.socio_id = s.id) ultima_visita, "
              "(select round(avg(score),1) from nps n where n.socio_id = s.id) nps_promedio, "
              "(select count(*) from recompensas r where r.socio_id = s.id and r.estado = 'emitida' "
              " and r.vence_at >= ?) cortesias_vigentes")


def admin_socios_lista(h, q):
    buscar = (q.get("q", [""])[0] or "").strip().lower()
    orden = {"visitas": "visitas desc", "recientes": "s.creado_at desc", "ultima": "ultima_visita desc",
             "nombre": "lower(s.nombre) asc"}.get(q.get("orden", ["recientes"])[0], "s.creado_at desc")
    limite = entero(q.get("limite", ["50"])[0], 50, 1, 500)
    pagina = entero(q.get("pagina", ["1"])[0], 1, 1, 10000)
    where, params = "", []
    if buscar:
        where = "where lower(s.nombre) like ? or s.telefono like ?"
        solo_digitos = re.sub(r"\D", "", buscar) or buscar
        params = [f"%{buscar}%", f"%{solo_digitos}%"]
    with db() as con:
        total = con.execute(f"select count(*) from socios s {where}", params).fetchone()[0]
        rows = con.execute(f"select {SOCIO_COLS} from socios s {where} order by {orden} limit ? offset ?",
                           [iso()] + params + [limite, (pagina - 1) * limite]).fetchall()
        return 200, {"total": total, "pagina": pagina, "limite": limite, "socios": [dict(r) for r in rows]}


def admin_socio_detalle(h, socio_id):
    with db() as con:
        s = con.execute(f"select {SOCIO_COLS} from socios s where s.id = ?", (iso(), socio_id)).fetchone()
        if not s:
            return 404, {"error": "Socio no encontrado."}
        return 200, {
            "socio": dict(s),
            "visitas": [dict(r) for r in con.execute(
                "select id, dia, origen from visitas where socio_id = ? order by dia desc limit 100", (socio_id,))],
            "recompensas": [dict(r) for r in con.execute(
                "select codigo, nombre, estado, emitida_at, vence_at, canjeada_at from recompensas "
                "where socio_id = ? order by emitida_at desc", (socio_id,))],
            "nps": [dict(r) for r in con.execute(
                "select id, score, comentario, creado_at, seguimiento, notas, origen from nps where socio_id = ? "
                "order by creado_at desc", (socio_id,))],
            "ranking": posicion_ranking(con, socio_id, "mes"),
        }


def admin_socio_crear(h, body):
    """Alta en la barra. Si no se da PIN se genera uno y se devuelve una sola vez."""
    nombre = (body.get("nombre") or "").strip()[:60]
    tel = normaliza_tel(body.get("telefono"))
    pin = str(body.get("pin") or "") or f"{secrets.randbelow(10000):04d}"
    if not nombre or not tel or not re.fullmatch(r"\d{4}", pin):
        return 400, {"error": "Nombre, teléfono de 10 dígitos y PIN de 4 números (opcional)."}
    if not body.get("acepta_privacidad"):
        return 400, {"error": "El cliente debe aceptar el aviso de privacidad."}
    with db() as con:
        if con.execute("select 1 from socios where telefono = ?", (tel,)).fetchone():
            return 409, {"error": "Ese teléfono ya está registrado."}
        cur = con.execute(
            "insert into socios (nombre, telefono, pin_hash, acepta_privacidad_at, acepta_whatsapp, creado_at, "
            "notas, mostrar_ranking) values (?, ?, ?, ?, ?, ?, ?, ?)",
            (nombre, tel, hash_pin(tel, pin), iso(), 1 if body.get("acepta_whatsapp") else 0, iso(),
             (body.get("notas") or "")[:500], 0 if body.get("mostrar_ranking") is False else 1))
        return 201, {"id": cur.lastrowid, "pin": pin}


def admin_socio_editar(h, body, socio_id):
    with db() as con:
        s = con.execute("select telefono from socios where id = ?", (socio_id,)).fetchone()
        if not s:
            return 404, {"error": "Socio no encontrado."}
        campos, params, pin_nuevo = [], [], None
        if "nombre" in body:
            nombre = (body.get("nombre") or "").strip()[:60]
            if not nombre:
                return 400, {"error": "El nombre no puede quedar vacío."}
            campos.append("nombre = ?"); params.append(nombre)
        for k in ("acepta_whatsapp", "mostrar_ranking"):
            if k in body:
                campos.append(f"{k} = ?"); params.append(1 if body[k] else 0)
        if "notas" in body:
            campos.append("notas = ?"); params.append((body.get("notas") or "")[:500])
        tel = s["telefono"]
        if "telefono" in body:
            tel = normaliza_tel(body.get("telefono"))
            if not tel:
                return 400, {"error": "Teléfono de 10 dígitos."}
            if tel != s["telefono"] and con.execute("select 1 from socios where telefono = ?", (tel,)).fetchone():
                return 409, {"error": "Ese teléfono ya está registrado."}
            campos.append("telefono = ?"); params.append(tel)
        # El PIN se cifra con el teléfono: si cambia el teléfono o se pide, se asigna un PIN nuevo.
        if body.get("reset_pin") or ("telefono" in body and tel != s["telefono"]) or body.get("pin"):
            pin_nuevo = str(body.get("pin") or f"{secrets.randbelow(10000):04d}")
            if not re.fullmatch(r"\d{4}", pin_nuevo):
                return 400, {"error": "El PIN debe tener 4 números."}
            campos.append("pin_hash = ?"); params.append(hash_pin(tel, pin_nuevo))
            con.execute("delete from sesiones where socio_id = ?", (socio_id,))
        if not campos:
            return 400, {"error": "Nada que actualizar"}
        con.execute(f"update socios set {', '.join(campos)}, actualizado_at = ? where id = ?",
                    params + [iso(), socio_id])
        return 200, {"ok": True, **({"pin": pin_nuevo} if pin_nuevo else {})}


def admin_socio_borrar(h, socio_id):
    with db() as con:
        if not borrar_socio(con, socio_id):
            return 404, {"error": "Socio no encontrado."}
    return 200, {"ok": True}


def admin_socio_visita(h, body, socio_id):
    """El equipo registra la visita de hoy (p. ej. si el cliente no trae batería)."""
    with db() as con:
        if not con.execute("select 1 from socios where id = ?", (socio_id,)).fetchone():
            return 404, {"error": "Socio no encontrado."}
        visita_id, nueva, recompensa = registrar_visita(con, socio_id, origen="panel")
        return (201 if nueva else 200), {"ya_registrada": not nueva, "visita_id": visita_id,
                                         "recompensa": recompensa}


def admin_visita_borrar(h, visita_id):
    with db() as con:
        if con.execute("select 1 from recompensas where visita_id = ? and estado = 'canjeada'",
                       (visita_id,)).fetchone():
            return 409, {"error": "Esa visita generó una cortesía ya canjeada; no se puede borrar."}
        for tabla in ("clicks_resena", "nps", "recompensas"):
            con.execute(f"delete from {tabla} where visita_id = ?", (visita_id,))
        if not con.execute("delete from visitas where id = ?", (visita_id,)).rowcount:
            return 404, {"error": "Visita no encontrada."}
    return 200, {"ok": True}


def admin_canjear(h, body):
    codigo = (body.get("codigo") or "").strip().upper()
    if codigo and not codigo.startswith("CN-"):
        codigo = "CN-" + codigo
    with db() as con:
        r = con.execute("select r.*, s.nombre as socio_nombre from recompensas r "
                        "join socios s on s.id = r.socio_id where r.codigo = ?", (codigo,)).fetchone()
        if not r:
            return 404, {"error": "Código no encontrado."}
        if r["estado"] == "canjeada":
            return 409, {"error": f"Ya se canjeó el {r['canjeada_at'][:16].replace('T', ' ')}."}
        if r["vence_at"] < iso():
            return 410, {"error": "El código venció."}
        con.execute("update recompensas set estado = 'canjeada', canjeada_at = ? where id = ?", (iso(), r["id"]))
        return 200, {"ok": True, "nombre": r["nombre"], "socio": r["socio_nombre"]}


def admin_ranking(h, q):
    periodo = q.get("periodo", ["mes"])[0]
    periodo = periodo if periodo in ("semana", "mes", "total") else "mes"
    with db() as con:
        return 200, {"periodo": periodo,
                     "ranking": tabla_ranking(con, periodo, entero(q.get("limite", ["50"])[0], 50, 1, 500), False)}


def admin_socios_csv(h, q):
    with db() as con:
        rows = con.execute("select s.nombre, s.telefono, s.creado_at, s.acepta_whatsapp, s.mostrar_ranking, "
                           "(select count(*) from visitas v where v.socio_id = s.id) visitas, "
                           "(select max(dia) from visitas v where v.socio_id = s.id) ultima_visita "
                           "from socios s order by s.creado_at").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["nombre", "telefono", "alta", "acepta_whatsapp", "aparece_en_ranking", "visitas", "ultima_visita"])
    for r in rows:
        w.writerow(list(r))
    return 200, buf.getvalue()


def admin_nps_csv(h, q):
    with db() as con:
        rows = con.execute("select n.creado_at, s.nombre, s.telefono, n.score, n.comentario, n.seguimiento, n.notas, "
                           "n.origen from nps n join socios s on s.id = n.socio_id order by n.creado_at desc").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["fecha", "nombre", "telefono", "score", "comentario", "seguimiento", "notas", "origen"])
    for r in rows:
        w.writerow(list(r))
    return 200, buf.getvalue()


# ── Servidor ────────────────────────────────────────────────────────────────

RUTAS = [  # (método, patrón, handler, tipo) — tipo: publica | socio | admin
    ("GET", r"/api/salud", lambda h, q: (200, {"ok": True}), "publica"),
    ("GET", r"/api/ranking", api_ranking, "publica"),
    ("POST", r"/api/registro", api_registro, "publica"),
    ("POST", r"/api/login", api_login, "publica"),
    ("GET", r"/api/yo", api_yo, "socio"),
    ("POST", r"/api/yo/preferencias", api_preferencias, "socio"),
    ("POST", r"/api/checkin", api_checkin, "socio"),
    ("POST", r"/api/nps", api_nps, "socio"),
    ("POST", r"/api/resena-click", api_click_resena, "socio"),
    ("POST", r"/api/logout", api_logout, "socio"),
    ("GET", r"/api/admin/resumen", admin_resumen, "admin"),
    ("GET", r"/api/admin/estadisticas", admin_estadisticas, "admin"),
    ("GET", r"/api/admin/ranking", admin_ranking, "admin"),
    ("GET", r"/api/admin/nps", admin_nps_lista, "admin"),
    ("POST", r"/api/admin/nps", admin_nps_crear, "admin"),
    ("POST", r"/api/admin/nps/(\d+)", admin_nps_editar, "admin"),   # compatibilidad v1
    ("PUT", r"/api/admin/nps/(\d+)", admin_nps_editar, "admin"),
    ("DELETE", r"/api/admin/nps/(\d+)", admin_nps_borrar, "admin"),
    ("GET", r"/api/admin/nps\.csv", admin_nps_csv, "admin"),
    ("GET", r"/api/admin/socios", admin_socios_lista, "admin"),
    ("POST", r"/api/admin/socios", admin_socio_crear, "admin"),
    ("GET", r"/api/admin/socios\.csv", admin_socios_csv, "admin"),
    ("GET", r"/api/admin/socios/(\d+)", admin_socio_detalle, "admin"),
    ("PUT", r"/api/admin/socios/(\d+)", admin_socio_editar, "admin"),
    ("DELETE", r"/api/admin/socios/(\d+)", admin_socio_borrar, "admin"),
    ("POST", r"/api/admin/socios/(\d+)/visitas", admin_socio_visita, "admin"),
    ("DELETE", r"/api/admin/visitas/(\d+)", admin_visita_borrar, "admin"),
    ("POST", r"/api/admin/canjear", admin_canjear, "admin"),
]


class Handler(BaseHTTPRequestHandler):
    server_version = "ClubCisne/2.0"
    cookie_sesion = None  # None = no tocar; "" = borrar; token = poner

    def log_message(self, fmt, *args):  # sin datos personales en logs
        pass

    def ip(self):
        return self.headers.get("X-Real-IP") or self.client_address[0]

    def token(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and len(auth) > 7:
            return auth[7:]
        galleta = SimpleCookie(self.headers.get("Cookie", ""))
        return galleta[COOKIE].value if COOKIE in galleta else ""

    def socio_id(self):
        tok = self.token()
        if not tok:
            return None
        with db() as con:
            limite = iso(ahora() - timedelta(days=SESION_DIAS))
            con.execute("delete from sesiones where creado_at < ?", (limite,))
            r = con.execute("select socio_id from sesiones where token = ?", (tok,)).fetchone()
            if r and COOKIE not in SimpleCookie(self.headers.get("Cookie", "")):
                self.cookie_sesion = tok  # sesiones de la v1 (solo Bearer) pasan a cookie
            return r["socio_id"] if r else None

    def responder(self, status, data):
        if isinstance(data, str):
            payload, ctype = data.encode("utf-8-sig"), "text/csv; charset=utf-8"
        else:
            payload, ctype = json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if self.cookie_sesion is not None:
            vida = SESION_DIAS * 86400 if self.cookie_sesion else 0
            seguro = "; Secure" if COOKIE_SECURE else ""
            self.send_header("Set-Cookie", f"{COOKIE}={self.cookie_sesion}; Path=/api; Max-Age={vida}; "
                                           f"HttpOnly; SameSite=Lax{seguro}")
        self.end_headers()
        self.wfile.write(payload)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20_000:
            return None
        try:
            datos = json.loads(self.rfile.read(n) or b"{}")
            return datos if isinstance(datos, dict) else None
        except json.JSONDecodeError:
            return None

    def despachar(self, metodo):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        for m, patron, fn, tipo in RUTAS:
            coincide = re.fullmatch(patron, url.path)
            if m != metodo or not coincide:
                continue
            args = [int(g) for g in coincide.groups()]
            try:
                if tipo == "admin" and STAFF_TOKEN:
                    supplied = self.headers.get("X-Cisne-Staff", "")
                    if not hmac.compare_digest(supplied, STAFF_TOKEN):
                        return self.responder(403, {"error": "Acceso de personal requerido."})
                if metodo in ("POST", "PUT"):
                    body = self.body()
                    if body is None:
                        return self.responder(400, {"error": "JSON inválido"})
                    entrada = [body]
                else:
                    entrada = [] if args else [q]
                if tipo == "socio":
                    sid = self.socio_id()
                    if not sid:
                        self.cookie_sesion = "" if self.token() else None
                        return self.responder(401, {"error": "Sesión vencida. Vuelve a entrar."})
                    return self.responder(*fn(self, *(entrada or [{}]), sid))
                return self.responder(*fn(self, *entrada, *args))
            except Exception:  # noqa: BLE001 — nunca exponer trazas
                return self.responder(500, {"error": "Error interno"})
        self.responder(404, {"error": "No encontrado"})

    def do_GET(self):
        self.despachar("GET")

    def do_POST(self):
        self.despachar("POST")

    def do_PUT(self):
        self.despachar("PUT")

    def do_DELETE(self):
        self.despachar("DELETE")


def main():
    init_db()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Club Cisne Negro escuchando en 127.0.0.1:{PORT} (db={DB_PATH})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
