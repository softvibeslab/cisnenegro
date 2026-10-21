"""Club Cisne Negro: Pasaporte (visitas y cortesías), NPS, miembros y ranking.

Servidor HTTP sin dependencias externas (Python 3.11+ y SQLite). Corre detrás del gateway:
  /api/*        → API pública del menú (socios, check-in, NPS, ranking)
  /api/admin/*  → propietario autenticado por CMS + token interno obligatorio

Sesión del socio: cookie HttpOnly `cn_sesion` de 180 días que pone el servidor (Safari no la
borra a los 7 días como al localStorage). También acepta `Authorization: Bearer <token>`.

Variables de entorno:
  CLUB_DB      ruta de la base SQLite        (default ./club.db)
  CLUB_SECRET  secreto para el código del día (obligatorio en producción)
  CLUB_PORT    puerto local                  (default 8790)
  CLUB_HOST    interfaz interna               (default 127.0.0.1)
  CLUB_ADMIN_TOKEN secreto compartido con el proxy CMS (obligatorio)
  CLUB_REVIEW_URL  enlace de Google al que se invita después del NPS
  CLUB_COOKIE_SECURE  "0" para desarrollo sin HTTPS (default "1")
  CLUB_MENU           ruta de menu.json (solo cuando no se conecta el CMS)
  CLUB_CMS_DB         SQLite del CMS; solo la revisión publicada fija los precios
  CLUB_COOKIE_PATH    ruta de la cookie de sesión (default "/api")
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
import sys
import threading
import time
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DB_PATH = os.environ.get("CLUB_DB", "club.db")
SECRET = os.environ.get("CLUB_SECRET", "dev-secret")
PORT = int(os.environ.get("CLUB_PORT", "8790"))
HOST = os.environ.get("CLUB_HOST", "127.0.0.1")
ADMIN_TOKEN = os.environ.get("CLUB_ADMIN_TOKEN", "")
REVIEW_URL = os.environ.get(
    "CLUB_REVIEW_URL",
    "https://www.google.com/maps/place/Cisne+Negro/data=!4m2!3m1!1s0x0:0x2d58b94ff33d7e6b")
COOKIE_SECURE = os.environ.get("CLUB_COOKIE_SECURE", "1") != "0"
COOKIE = "cn_sesion"
COOKIE_PATH = os.environ.get("CLUB_COOKIE_PATH", "/api")
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
create table if not exists ajustes (
  clave text primary key,
  valor text not null,
  actualizado_at text not null
);
create table if not exists staff (
  id integer primary key, usuario text not null unique, nombre text not null, rol text not null,
  pin_hash text not null, sal text not null, activo integer not null default 1, creado_at text not null, actualizado_at text
);
create table if not exists staff_sesiones (
  token text primary key, staff_id integer not null references staff(id), creado_at text not null, expira_at text not null
);
create table if not exists cuentas (
  id integer primary key, mesa text not null, estado text not null, mesero_id integer not null references staff(id),
  abierta_at text not null, cerrada_at text, cerrada_por integer, dia_operativo text not null,
  total_c integer not null default 0, propina_c integer not null default 0, pagos text not null default '[]',
  motivo text, corte_id integer
);
create table if not exists pedidos (
  id integer primary key, codigo text not null unique, estado text not null, mesa text, lineas text not null,
  total_c integer not null, socio_id integer, origen text not null default 'qr', creado_at text not null,
  expira_at text not null, tomado_por integer references staff(id), tomado_at text, cuenta_id integer references cuentas(id)
);
create table if not exists eventos (
  id integer primary key, tipo text not null, staff_id integer, cuenta_id integer, pedido_id integer,
  detalle text, creado_at text not null
);
create table if not exists cortes (
  id integer primary key, staff_id integer not null references staff(id), dia_operativo text not null,
  resumen text not null, hash text not null, creado_at text not null, unique (staff_id, dia_operativo)
);
create table if not exists cierres (
  id integer primary key, dia_operativo text not null unique, staff_id integer not null, resumen text not null,
  hash text not null, forzado integer not null default 0, motivo text, creado_at text not null,
  reabierto_at text, reabierto_por integer, reabierto_motivo text
);
create index if not exists cuentas_dia_idx on cuentas (dia_operativo, mesero_id);
create index if not exists cuentas_mesa_idx on cuentas (mesa, estado);
create index if not exists pedidos_estado_idx on pedidos (estado, expira_at);
create index if not exists visitas_socio_idx on visitas (socio_id, dia);
create index if not exists nps_creado_idx on nps (creado_at);
"""

# Columnas agregadas después de la v1 (migración automática y sin pérdida de datos).
MIGRACIONES = {
    "socios": [("mostrar_ranking", "integer not null default 1"), ("notas", "text"),
               ("actualizado_at", "text")],
    "visitas": [("origen", "text not null default 'menu'")],
    "nps": [("origen", "text not null default 'menu'")],
    "pedidos": [("huella", "text")],
}

_lock = threading.Lock()
_intentos: dict[str, list[float]] = {}


def ahora():
    return datetime.now(TZ)


def hoy():
    return ahora().date().isoformat()


def iso(dt=None):
    return (dt or ahora()).isoformat(timespec="seconds")


@contextmanager
def db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    try:
        con.row_factory = sqlite3.Row
        con.execute("pragma foreign_keys = on")
        with con:
            yield con
    finally:
        con.close()


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



# ── Ajustes del negocio (Wi-Fi) ────────────────────────────────────────────

WIFI_EJEMPLO = {"ssid": "CisneNegro-Invitados", "password": "CuentaloEnElCisne", "seguridad": "WPA",
                "visibilidad": "publica", "ejemplo": True, "actualizado_at": None}
WIFI_SEGURIDAD = ("WPA", "WEP", "nopass")
WIFI_VISIBILIDAD = ("publica", "socios", "oculta")


def leer_wifi(con):
    r = con.execute("select valor, actualizado_at from ajustes where clave = 'wifi'").fetchone()
    if not r:
        return dict(WIFI_EJEMPLO)
    w = {**WIFI_EJEMPLO, **json.loads(r["valor"])}
    w["actualizado_at"] = r["actualizado_at"]
    return w


def api_config(h, q):
    """Configuración pública del menú. El Wi-Fi respeta su visibilidad."""
    with db() as con:
        w = leer_wifi(con)
    wifi, requiere = None, False
    if w["visibilidad"] == "publica" or (w["visibilidad"] == "socios" and h.socio_id()):
        wifi = {k: w[k] for k in ("ssid", "password", "seguridad")}
    elif w["visibilidad"] == "socios":
        requiere = True
    return 200, {"wifi": wifi, "wifi_requiere_pasaporte": requiere}


def admin_ajustes(h, q):
    with db() as con:
        return 200, {"wifi": leer_wifi(con)}


def admin_ajustes_guardar(h, body):
    w = body.get("wifi")
    if not isinstance(w, dict):
        return 400, {"error": "Faltan los datos del Wi-Fi."}
    ssid = str(w.get("ssid") or "").strip()
    seguridad = w.get("seguridad") or "WPA"
    visibilidad = w.get("visibilidad") or "publica"
    password = str(w.get("password") or "")
    if not 1 <= len(ssid) <= 32:
        return 400, {"error": "El nombre de la red debe tener de 1 a 32 caracteres."}
    if seguridad not in WIFI_SEGURIDAD:
        return 400, {"error": "Tipo de seguridad inválido."}
    if visibilidad not in WIFI_VISIBILIDAD:
        return 400, {"error": "Visibilidad inválida."}
    if seguridad == "WPA" and not 8 <= len(password) <= 63:
        return 400, {"error": "La contraseña WPA debe tener de 8 a 63 caracteres."}
    if seguridad == "WEP" and len(password) not in (5, 10, 13, 26):
        return 400, {"error": "La contraseña WEP debe tener 5, 13 (texto) o 10, 26 (hex) caracteres."}
    if seguridad == "nopass":
        password = ""
    if any(ord(c) < 32 for c in ssid + password):
        return 400, {"error": "Hay caracteres no válidos."}
    valor = json.dumps({"ssid": ssid, "password": password, "seguridad": seguridad,
                        "visibilidad": visibilidad, "ejemplo": False}, ensure_ascii=False)
    with db() as con:
        con.execute("insert into ajustes (clave, valor, actualizado_at) values ('wifi', ?, ?) "
                    "on conflict(clave) do update set valor = excluded.valor, actualizado_at = excluded.actualizado_at",
                    (valor, iso()))
        return 200, {"ok": True, "wifi": leer_wifi(con)}


# ══════════════════════════════════════════════════════════════════════════
# Pedidos por QR, cuentas por mesa, equipo (mesero / admin), cortes y cierre
# ══════════════════════════════════════════════════════════════════════════

MENU_PATH = os.environ.get("CLUB_MENU", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                     "..", "sitio", "data", "menu.json"))
CMS_DB_PATH = os.environ.get("CLUB_CMS_DB", "")
COOKIE_EQUIPO = "cn_equipo"
STAFF_SESION_H = 12
PEDIDO_TTL_H = 3
DIA_CORTE_HORA = 5            # el día operativo cambia a las 05:00 (el bar cierra 23:30)
ROLES = ("mesero", "admin")
METODOS_PAGO = {"efectivo": "Efectivo", "tarjeta_credito": "Tarjeta de crédito",
                "tarjeta_debito": "Tarjeta de débito"}
TIPOS_LINEA = ("barril", "lata", "comida", "bebida", "vuelo")
VUELO_N, MAX_CANT, MAX_LINEAS_PED, MAX_NOTA, MAX_MESA = 4, 20, 40, 40, 10
ALFABETO_COD = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_menu_cache = {"key": None, "data": None}
_menu_lock = threading.Lock()
_bloqueos: dict[str, list[float]] = {}


class MenuUnavailable(RuntimeError):
    """No se admite cobrar desde una copia obsoleta si falla el catálogo publicado."""


def menu_actual():
    """Catálogo publicado del CMS; nunca borradores ni precios enviados por el cliente.

    El ID de revisión invalida la caché al publicar/restaurar. Las líneas ya guardadas
    en pedidos conservan sus IDs y precios históricos aunque cambie la publicación.
    """
    with _menu_lock:
        try:
            if CMS_DB_PATH:
                source = Path(CMS_DB_PATH).resolve()
                stat = source.stat()
                with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=10)) as con:
                    # Una sola instantánea para el puntero y el contenido, incluso al publicar.
                    con.execute("begin")
                    row = con.execute("select value from settings where key='published'").fetchone()
                    if not row:
                        raise ValueError("Sin revisión publicada")
                    rid = int(row[0])
                    key = (str(source), stat.st_dev, stat.st_ino, rid)
                    if _menu_cache["key"] != key:
                        revision = con.execute("select output from revisions where id=?", (rid,)).fetchone()
                        if not revision:
                            raise ValueError("Revisión inexistente")
                        data = json.loads(json.loads(revision[0])["data/menu.json"])
                        if not isinstance(data, dict):
                            raise ValueError("Catálogo inválido")
                        _menu_cache.update(key=key, data=data)
            else:
                source = Path(MENU_PATH).resolve()
                stat = source.stat()
                key = (str(source), stat.st_ino, stat.st_mtime_ns, stat.st_size)
                if _menu_cache["key"] != key:
                    with source.open(encoding="utf-8") as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError("Catálogo inválido")
                    _menu_cache.update(key=key, data=data)
            return _menu_cache["data"]
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            raise MenuUnavailable("El menú está temporalmente fuera de servicio. Intenta de nuevo.") from exc


def nombre_platillo(item):
    n = item.get("nombre", "")
    img = item.get("img") or ""
    if n.startswith("De ") and img:
        resto = "de " + n[3:]
        if img.startswith("hambur"):
            return "Hamburguesa " + resto
        if img.startswith("san_"):
            return "Sándwich " + resto
    return n


def _buscar(menu, tipo, pid):
    if tipo == "barril":
        return next((b for b in menu.get("barril", []) if b.get("id") == pid), None)
    if tipo == "lata":
        return next((b for b in menu.get("latas", []) if b.get("id") == pid), None)
    if tipo == "bebida":
        return next((b for b in menu.get("sin_alcohol", []) if b.get("id") == pid), None)
    if tipo == "comida":
        for s in menu.get("comida", []):
            for it in s.get("items", []):
                if it.get("id") == pid:
                    return it
    return None


def resolver_linea(menu, tipo, pid, variante, cervezas):
    """Misma regla que sitio/assets/js/pedido.js. → (nombre, detalle, precio, variante, cervezas)."""
    if tipo == "vuelo":
        if (menu.get("vuelo") or {}).get("visible", True) is False:
            raise ValueError("El vuelo ya no está disponible en el menú.")
        if not isinstance(cervezas, list) or len(cervezas) != VUELO_N:
            raise ValueError(f"Elige {VUELO_N} cervezas de barril para el vuelo.")
        precio, nombres = 0, []
        for cid in cervezas:
            b = _buscar(menu, "barril", cid)
            if not b or b.get("disponible") is False:
                raise ValueError("Una cerveza del vuelo ya no está en barril.")
            p4 = next((p for p in b.get("precios", []) if re.fullmatch(r"4\s*oz", str(p.get("medida")), re.I)), None)
            if not p4:
                raise ValueError("Una cerveza del vuelo no tiene medida de 4 oz.")
            precio += int(p4["precio"])
            nombres.append(b["nombre"])
        nombre = (menu.get("vuelo") or {}).get("nombre") or "Vuelo del Cisne"
        return nombre, f"{VUELO_N} × 4 oz: " + " · ".join(nombres), precio, None, list(cervezas)
    prod = _buscar(menu, tipo, pid)
    if not prod:
        raise ValueError("Un producto ya no está en el menú.")
    if prod.get("disponible") is False:
        raise ValueError(f"{prod.get('nombre')} está agotado.")
    nombre = nombre_platillo(prod) if tipo == "comida" else prod["nombre"]
    if tipo == "barril":
        m = next((p for p in prod.get("precios", []) if p.get("medida") == variante), None)
        if not m:
            raise ValueError(f"Elige una medida disponible de {nombre}.")
        return nombre, m["medida"], int(m["precio"]), m["medida"], None
    variantes = prod.get("variantes") or []
    if variantes:
        v = next((x for x in variantes if x.get("id") == variante and x.get("disponible") is not False), None)
        if not v:
            raise ValueError(f"Elige una presentación disponible de {nombre}.")
        precio = int(v["precio"]) if isinstance(v.get("precio"), (int, float)) else int(prod["precio"]) + int(v.get("extra") or 0)
        return nombre, v.get("nombre", ""), precio, v["id"], None
    if variante not in (None, ""):
        raise ValueError(f"{nombre} no tiene esa presentación.")
    return nombre, "", int(prod["precio"]), None, None


def _texto(s, n):
    return re.sub(r"[\x00-\x1f\x7f]", "", s if isinstance(s, str) else "").strip()[:n]


def normalizar_lineas(menu, lineas):
    """Valida y recalcula precios en el servidor (nunca se confía en los del navegador)."""
    if not isinstance(lineas, list) or not lineas:
        raise ValueError("El pedido está vacío.")
    out = []
    for l in lineas[:MAX_LINEAS_PED + 1]:
        if not isinstance(l, dict) or l.get("tipo") not in TIPOS_LINEA:
            raise ValueError("Hay un producto que no está en el menú.")
        cant = l.get("cantidad", 1)
        if not isinstance(cant, int) or isinstance(cant, bool) or not 1 <= cant <= MAX_CANT:
            raise ValueError(f"La cantidad debe ser de 1 a {MAX_CANT}.")
        tipo = l["tipo"]
        pid = "vuelo" if tipo == "vuelo" else str(l.get("id") or "")
        nombre, detalle, precio, variante, cervezas = resolver_linea(menu, tipo, pid, l.get("variante"), l.get("cervezas"))
        nota = _texto(l.get("nota"), MAX_NOTA)
        clave = (tipo, pid, variante or "", "+".join(cervezas or []), nota)
        igual = next((x for x in out if x["_clave"] == clave), None)
        if igual:
            igual["cantidad"] = min(MAX_CANT, igual["cantidad"] + cant)
            continue
        if len(out) >= MAX_LINEAS_PED:
            raise ValueError(f"El pedido admite hasta {MAX_LINEAS_PED} productos distintos.")
        out.append({"_clave": clave, "tipo": tipo, "id": pid, "variante": variante, "cervezas": cervezas,
                    "nombre": nombre, "detalle": detalle, "precio": precio, "cantidad": cant, "nota": nota})
    for x in out:
        del x["_clave"]
    return out


def total_lineas(lineas):
    return sum(l["precio"] * l["cantidad"] for l in lineas if l["cantidad"] > 0)


def dia_operativo(dt=None):
    dt = dt or ahora()
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return (dt.astimezone(TZ) - timedelta(hours=DIA_CORTE_HORA)).date().isoformat()


def nuevo_codigo_pedido(con):
    while True:
        c = "".join(secrets.choice(ALFABETO_COD) for _ in range(8))
        if not con.execute("select 1 from pedidos where codigo = ?", (c,)).fetchone():
            return c


def limpiar_codigo(c):
    return re.sub(r"[^A-Z0-9]", "", str(c or "").upper())[:12]


def evento(con, tipo, staff_id=None, cuenta_id=None, pedido_id=None, detalle=None):
    con.execute("insert into eventos (tipo, staff_id, cuenta_id, pedido_id, detalle, creado_at) values (?, ?, ?, ?, ?, ?)",
                (tipo, staff_id, cuenta_id, pedido_id, json.dumps(detalle or {}, ensure_ascii=False), iso()))


def caducar_pendientes(con):
    con.execute("update pedidos set estado = 'caducado' where estado = 'pendiente' and expira_at < ?", (iso(),))


def a_pesos(c):
    return round((c or 0) / 100, 2)


# ── API pública del cliente ──────────────────────────────────────────────

def api_pedido_crear(h, body):
    if not limitar("pedido:" + h.ip(), 120, 3600):
        return 429, {"error": "Demasiados pedidos seguidos. Pídele ayuda al equipo."}
    try:
        lineas = normalizar_lineas(menu_actual(), body.get("lineas"))
    except MenuUnavailable as e:
        return 503, {"error": str(e)}
    except ValueError as e:
        return 400, {"error": str(e)}
    mesa = _texto(body.get("mesa"), MAX_MESA)
    with db() as con:
        codigo = nuevo_codigo_pedido(con)
        expira = iso(ahora() + timedelta(hours=PEDIDO_TTL_H))
        con.execute("insert into pedidos (codigo, estado, mesa, lineas, total_c, socio_id, origen, creado_at, expira_at) "
                    "values (?, 'pendiente', ?, ?, ?, ?, 'qr', ?, ?)",
                    (codigo, mesa, json.dumps(lineas, ensure_ascii=False), total_lineas(lineas) * 100,
                     h.socio_id(), iso(), expira))
    return 201, {"codigo": codigo, "expira_at": expira, "total": total_lineas(lineas), "lineas": lineas}


def api_pedido_estado(h, codigo):
    with db() as con:
        caducar_pendientes(con)
        r = con.execute("select p.estado, p.tomado_at, s.nombre from pedidos p left join staff s on s.id = p.tomado_por "
                        "where p.codigo = ?", (limpiar_codigo(codigo),)).fetchone()
    if not r:
        return 404, {"error": "Pedido no encontrado."}
    mesero = (r["nombre"] or "").split(" ")[0] if r["nombre"] else None
    return 200, {"estado": r["estado"], "mesero": mesero, "tomado_at": r["tomado_at"]}


# ── Sesión del equipo ────────────────────────────────────────────────────

def hash_staff(pin, sal):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), sal.encode(), 200_000).hex()


def staff_publico(r):
    return {"id": r["id"], "nombre": r["nombre"], "usuario": r["usuario"], "rol": r["rol"], "activo": bool(r["activo"])}


def crear_staff(con, nombre, usuario, rol, pin=None):
    usuario = re.sub(r"[^a-z0-9._-]", "", str(usuario or "").lower())[:30]
    nombre = _texto(nombre, 60)
    if not nombre or len(usuario) < 3:
        raise ValueError("Nombre y usuario (mínimo 3 letras o números) son obligatorios.")
    if rol not in ROLES:
        raise ValueError("Rol inválido.")
    pin = str(pin or f"{secrets.randbelow(10**6):06d}")
    if not re.fullmatch(r"\d{6}", pin):
        raise ValueError("El PIN debe tener 6 números.")
    if con.execute("select 1 from staff where usuario = ?", (usuario,)).fetchone():
        raise ValueError("Ese usuario ya existe.")
    sal = secrets.token_hex(16)
    cur = con.execute("insert into staff (usuario, nombre, rol, pin_hash, sal, activo, creado_at) values (?, ?, ?, ?, ?, 1, ?)",
                      (usuario, nombre, rol, hash_staff(pin, sal), sal, iso()))
    return cur.lastrowid, pin


def equipo_login(h, body):
    usuario = re.sub(r"[^a-z0-9._-]", "", str(body.get("usuario") or "").lower())
    pin = str(body.get("pin") or "")
    if not limitar("eq-login:" + h.ip(), 40, 300):
        return 429, {"error": "Demasiados intentos. Espera unos minutos."}
    t = time.time()
    fallos = [x for x in _bloqueos.get(usuario, []) if t - x < 900]
    if len(fallos) >= 5:
        return 429, {"error": "Usuario bloqueado 15 minutos por intentos fallidos."}
    with db() as con:
        s = con.execute("select * from staff where usuario = ?", (usuario,)).fetchone()
        if not s or not s["activo"] or not hmac.compare_digest(s["pin_hash"], hash_staff(pin, s["sal"])):
            _bloqueos[usuario] = fallos + [t]
            return 401, {"error": "Usuario o PIN incorrectos."}
        _bloqueos.pop(usuario, None)
        token = secrets.token_urlsafe(32)
        con.execute("insert into staff_sesiones (token, staff_id, creado_at, expira_at) values (?, ?, ?, ?)",
                    (token, s["id"], iso(), iso(ahora() + timedelta(hours=STAFF_SESION_H))))
        evento(con, "login", s["id"])
    h.cookie_equipo = token
    return 200, {"staff": staff_publico(s), "dia_operativo": dia_operativo()}


def equipo_logout(h, body, staff):
    with db() as con:
        con.execute("delete from staff_sesiones where token = ?", (h.token_equipo(),))
    h.cookie_equipo = ""
    return 200, {"ok": True}


def equipo_yo(h, q, staff):
    return 200, {"staff": staff, "dia_operativo": dia_operativo(), "hora_corte": f"{DIA_CORTE_HORA:02d}:00",
                 "metodos_pago": METODOS_PAGO}


# ── Pedidos y cuentas ────────────────────────────────────────────────────

def _socio_resumen(con, socio_id):
    if not socio_id:
        return None
    s = con.execute("select nombre from socios where id = ?", (socio_id,)).fetchone()
    if not s:
        return None
    n = con.execute("select count(*) from visitas where socio_id = ?", (socio_id,)).fetchone()[0]
    return {"alias": alias_publico(s["nombre"]), "visitas": n}


def _pedido_dict(con, r):
    d = {k: r[k] for k in ("id", "codigo", "estado", "mesa", "origen", "creado_at", "expira_at", "tomado_at", "cuenta_id")}
    d["lineas"] = json.loads(r["lineas"])
    d["total"] = a_pesos(r["total_c"])
    m = con.execute("select nombre from staff where id = ?", (r["tomado_por"],)).fetchone() if r["tomado_por"] else None
    d["tomado_por"] = m["nombre"] if m else None
    d["socio"] = _socio_resumen(con, r["socio_id"])
    return d


def _recalcular_cuenta(con, cuenta_id):
    tot = 0
    for r in con.execute("select lineas from pedidos where cuenta_id = ? and estado = 'tomado'", (cuenta_id,)):
        tot += total_lineas(json.loads(r["lineas"]))
    con.execute("update cuentas set total_c = ? where id = ?", (tot * 100, cuenta_id))
    return tot


def _cuenta_dict(con, c, detalle=False):
    m = con.execute("select nombre from staff where id = ?", (c["mesero_id"],)).fetchone()
    d = {k: c[k] for k in ("id", "mesa", "estado", "abierta_at", "cerrada_at", "dia_operativo", "corte_id", "motivo")}
    d.update(mesero_id=c["mesero_id"], mesero=m["nombre"] if m else None, total=a_pesos(c["total_c"]),
             propina=a_pesos(c["propina_c"]),
             pagos=[{"metodo": p["metodo"], "monto": a_pesos(p["monto_c"])} for p in json.loads(c["pagos"] or "[]")])
    rondas = con.execute("select * from pedidos where cuenta_id = ? order by tomado_at", (c["id"],)).fetchall()
    d["rondas"] = len(rondas)
    if detalle:
        d["pedidos"] = [_pedido_dict(con, r) for r in rondas]
        d["eventos"] = [dict(e) for e in con.execute(
            "select e.tipo, e.detalle, e.creado_at, s.nombre staff from eventos e left join staff s on s.id = e.staff_id "
            "where e.cuenta_id = ? order by e.creado_at", (c["id"],))]
    return d


def _puede(staff, cuenta):
    return staff["rol"] == "admin" or cuenta["mesero_id"] == staff["id"]


def _bloqueada(con, cuenta):
    if cuenta["corte_id"]:
        return "Esa cuenta ya entró en un corte."
    if con.execute("select 1 from cierres where dia_operativo = ? and reabierto_at is null",
                   (cuenta["dia_operativo"],)).fetchone():
        return "El día de esa cuenta ya está cerrado."
    return None


def equipo_pedido_ver(h, codigo, staff):
    with db() as con:
        caducar_pendientes(con)
        r = con.execute("select * from pedidos where codigo = ?", (limpiar_codigo(codigo),)).fetchone()
        if not r:
            return 404, {"error": "No encontramos ese pedido. Revisa el código."}
        d = _pedido_dict(con, r)
        if d["mesa"]:
            c = con.execute("select * from cuentas where mesa = ? and estado = 'abierta' order by abierta_at desc",
                            (d["mesa"],)).fetchone()
            d["cuenta_mesa"] = _cuenta_dict(con, c) if c else None
        return 200, {"pedido": d}


def equipo_pedido_importar(h, body, staff):
    """Pedido que llegó sin internet (los datos venían dentro del QR)."""
    datos = body.get("datos") if isinstance(body.get("datos"), dict) else {}
    try:
        lineas = normalizar_lineas(menu_actual(), datos.get("lineas"))
    except MenuUnavailable as e:
        return 503, {"error": str(e)}
    except ValueError as e:
        return 400, {"error": str(e)}
    # Huella del QR (incluye su marca de creación `t`): si dos meseros escanean el mismo QR, es el mismo pedido.
    huella = hashlib.sha256(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    with db() as con:
        previo = con.execute("select * from pedidos where origen = 'offline' and huella = ? and creado_at >= ? "
                             "order by id desc", (huella, iso(ahora() - timedelta(hours=PEDIDO_TTL_H)))).fetchone()
        if previo:
            return 200, {"pedido": _pedido_dict(con, previo), "repetido": True}
        codigo = nuevo_codigo_pedido(con)
        con.execute("insert into pedidos (codigo, estado, mesa, lineas, total_c, origen, creado_at, expira_at, huella) "
                    "values (?, 'pendiente', ?, ?, ?, 'offline', ?, ?, ?)",
                    (codigo, _texto(datos.get("mesa"), MAX_MESA), json.dumps(lineas, ensure_ascii=False),
                     total_lineas(lineas) * 100, iso(), iso(ahora() + timedelta(hours=PEDIDO_TTL_H)), huella))
        r = con.execute("select * from pedidos where codigo = ?", (codigo,)).fetchone()
        return 201, {"pedido": _pedido_dict(con, r)}


def equipo_pedido_tomar(h, body, codigo, staff):
    with db() as con:
        caducar_pendientes(con)
        r = con.execute("select * from pedidos where codigo = ?", (limpiar_codigo(codigo),)).fetchone()
        if not r:
            return 404, {"error": "No encontramos ese pedido."}
        if r["estado"] == "tomado":
            quien = con.execute("select nombre from staff where id = ?", (r["tomado_por"],)).fetchone()
            return 409, {"error": f"Ese pedido ya lo tomó {quien['nombre'] if quien else 'otra persona'}."}
        if r["estado"] != "pendiente":
            return 410, {"error": "Ese pedido ya no está vigente (caducó o se canceló)."}
        mesa = _texto(body.get("mesa") or r["mesa"], MAX_MESA)
        if not mesa:
            return 400, {"error": "Indica la mesa."}
        c = con.execute("select * from cuentas where mesa = ? and estado = 'abierta' order by abierta_at desc",
                        (mesa,)).fetchone()
        if c and _bloqueada(con, c):
            c = None
        if not c:
            cur = con.execute("insert into cuentas (mesa, estado, mesero_id, abierta_at, dia_operativo, total_c, propina_c, pagos) "
                              "values (?, 'abierta', ?, ?, ?, 0, 0, '[]')", (mesa, staff["id"], iso(), dia_operativo()))
            cuenta_id = cur.lastrowid
            evento(con, "cuenta_abierta", staff["id"], cuenta_id, detalle={"mesa": mesa})
        else:
            cuenta_id = c["id"]
        con.execute("update pedidos set estado = 'tomado', tomado_por = ?, tomado_at = ?, cuenta_id = ?, mesa = ? where id = ?",
                    (staff["id"], iso(), cuenta_id, mesa, r["id"]))
        evento(con, "pedido_tomado", staff["id"], cuenta_id, r["id"], {"codigo": r["codigo"], "total": a_pesos(r["total_c"])})
        _recalcular_cuenta(con, cuenta_id)
        c = con.execute("select * from cuentas where id = ?", (cuenta_id,)).fetchone()
        return 200, {"cuenta": _cuenta_dict(con, c, True)}


def equipo_pedido_cancelar(h, body, codigo, staff):
    motivo = _texto(body.get("motivo"), 200)
    if not motivo:
        return 400, {"error": "Escribe el motivo."}
    with db() as con:
        r = con.execute("select * from pedidos where codigo = ?", (limpiar_codigo(codigo),)).fetchone()
        if not r or r["estado"] != "pendiente":
            return 409, {"error": "Solo se cancelan pedidos pendientes."}
        con.execute("update pedidos set estado = 'cancelado' where id = ?", (r["id"],))
        evento(con, "pedido_cancelado", staff["id"], pedido_id=r["id"], detalle={"motivo": motivo})
    return 200, {"ok": True}


def equipo_cuentas(h, q, staff):
    estado = q.get("estado", ["abierta"])[0]
    conds, params = [], []
    if estado in ("abierta", "cerrada", "cancelada"):
        conds.append("estado = ?"); params.append(estado)
    if staff["rol"] != "admin" or q.get("mias", ["0"])[0] == "1":
        conds.append("mesero_id = ?"); params.append(staff["id"])
    where = ("where " + " and ".join(conds)) if conds else ""
    with db() as con:
        rows = con.execute(f"select * from cuentas {where} order by abierta_at desc limit 200", params).fetchall()
        return 200, {"cuentas": [_cuenta_dict(con, c) for c in rows]}


def equipo_cuenta_ver(h, cuenta_id, staff):
    with db() as con:
        c = con.execute("select * from cuentas where id = ?", (cuenta_id,)).fetchone()
        if not c or not _puede(staff, c):
            return 404, {"error": "Cuenta no encontrada."}
        return 200, {"cuenta": _cuenta_dict(con, c, True)}


def equipo_cuenta_linea(h, body, cuenta_id, staff):
    """Ajusta la cantidad de una línea (0 = «no hay»). El precio no se toca."""
    with db() as con:
        c = con.execute("select * from cuentas where id = ?", (cuenta_id,)).fetchone()
        if not c or not _puede(staff, c):
            return 404, {"error": "Cuenta no encontrada."}
        if c["estado"] != "abierta" or _bloqueada(con, c):
            return 409, {"error": _bloqueada(con, c) or "La cuenta ya no está abierta."}
        p = con.execute("select * from pedidos where id = ? and cuenta_id = ?", (body.get("pedido_id"), cuenta_id)).fetchone()
        if not p:
            return 404, {"error": "Ronda no encontrada."}
        lineas = json.loads(p["lineas"])
        i, cant = body.get("indice"), body.get("cantidad")
        if not isinstance(i, int) or not 0 <= i < len(lineas):
            return 400, {"error": "Producto no encontrado."}
        if not isinstance(cant, int) or isinstance(cant, bool) or not 0 <= cant <= MAX_CANT:
            return 400, {"error": f"La cantidad debe ser de 0 a {MAX_CANT}."}
        antes = lineas[i]["cantidad"]
        lineas[i]["cantidad"] = cant
        con.execute("update pedidos set lineas = ?, total_c = ? where id = ?",
                    (json.dumps(lineas, ensure_ascii=False), total_lineas(lineas) * 100, p["id"]))
        evento(con, "linea_ajustada", staff["id"], cuenta_id, p["id"],
               {"producto": lineas[i]["nombre"], "antes": antes, "despues": cant})
        _recalcular_cuenta(con, cuenta_id)
        c = con.execute("select * from cuentas where id = ?", (cuenta_id,)).fetchone()
        return 200, {"cuenta": _cuenta_dict(con, c, True)}


def _monto_c(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x < 0 or x > 1_000_000:
        return None
    return int(round(x * 100))


def equipo_cuenta_cerrar(h, body, cuenta_id, staff):
    with db() as con:
        c = con.execute("select * from cuentas where id = ?", (cuenta_id,)).fetchone()
        if not c or not _puede(staff, c):
            return 404, {"error": "Cuenta no encontrada."}
        if c["estado"] != "abierta" or _bloqueada(con, c):
            return 409, {"error": _bloqueada(con, c) or "La cuenta ya no está abierta."}
        total_c = _recalcular_cuenta(con, cuenta_id) * 100
        if total_c <= 0:
            return 400, {"error": "La cuenta está en $0. Cancélala en lugar de cerrarla."}
        propina_c = _monto_c(body.get("propina") or 0)
        if propina_c is None:
            return 400, {"error": "Propina inválida."}
        pagos = []
        for p in body.get("pagos") or []:
            m = _monto_c(p.get("monto")) if isinstance(p, dict) else None
            if not isinstance(p, dict) or p.get("metodo") not in METODOS_PAGO or not m:
                return 400, {"error": "Cada pago necesita forma de pago (efectivo, crédito o débito) y monto."}
            pagos.append({"metodo": p["metodo"], "monto_c": m})
        if not pagos:
            return 400, {"error": "Registra al menos un pago."}
        if sum(p["monto_c"] for p in pagos) != total_c + propina_c:
            return 400, {"error": f"Los pagos deben sumar ${a_pesos(total_c + propina_c):,.2f} (cuenta + propina)."}
        con.execute("update cuentas set estado = 'cerrada', cerrada_at = ?, propina_c = ?, pagos = ?, total_c = ?, "
                    "cerrada_por = ? where id = ?",
                    (iso(), propina_c, json.dumps(pagos), total_c, staff["id"], cuenta_id))
        evento(con, "cuenta_cerrada", staff["id"], cuenta_id, detalle={"total": a_pesos(total_c), "propina": a_pesos(propina_c),
                                                                       "pagos": [{"metodo": p["metodo"], "monto": a_pesos(p["monto_c"])} for p in pagos]})
        c = con.execute("select * from cuentas where id = ?", (cuenta_id,)).fetchone()
        return 200, {"cuenta": _cuenta_dict(con, c, True)}


def equipo_cuenta_cancelar(h, body, cuenta_id, staff):
    motivo = _texto(body.get("motivo"), 200)
    if not motivo:
        return 400, {"error": "Escribe el motivo de la cancelación."}
    with db() as con:
        c = con.execute("select * from cuentas where id = ?", (cuenta_id,)).fetchone()
        if not c or not _puede(staff, c):
            return 404, {"error": "Cuenta no encontrada."}
        if c["estado"] != "abierta" or _bloqueada(con, c):
            return 409, {"error": _bloqueada(con, c) or "La cuenta ya no está abierta."}
        con.execute("update cuentas set estado = 'cancelada', cerrada_at = ?, motivo = ?, cerrada_por = ? where id = ?",
                    (iso(), motivo, staff["id"], cuenta_id))
        evento(con, "cuenta_cancelada", staff["id"], cuenta_id, detalle={"motivo": motivo})
    return 200, {"ok": True}


def equipo_cuenta_transferir(h, body, cuenta_id, staff):
    with db() as con:
        c = con.execute("select * from cuentas where id = ?", (cuenta_id,)).fetchone()
        if not c or not _puede(staff, c):
            return 404, {"error": "Cuenta no encontrada."}
        if c["estado"] != "abierta":
            return 409, {"error": "Solo se transfieren cuentas abiertas."}
        dest = con.execute("select * from staff where id = ? and activo = 1", (body.get("staff_id"),)).fetchone()
        if not dest:
            return 400, {"error": "Elige un mesero activo."}
        con.execute("update cuentas set mesero_id = ? where id = ?", (dest["id"], cuenta_id))
        evento(con, "cuenta_transferida", staff["id"], cuenta_id, detalle={"a": dest["nombre"]})
        c = con.execute("select * from cuentas where id = ?", (cuenta_id,)).fetchone()
        return 200, {"cuenta": _cuenta_dict(con, c)}


def equipo_companeros(h, q, staff):
    with db() as con:
        rows = con.execute("select id, nombre, rol from staff where activo = 1 order by nombre").fetchall()
        return 200, {"staff": [dict(r) for r in rows]}


# ── Historial e indicadores ──────────────────────────────────────────────

def _rango(q):
    """rango=hoy|ayer|semana|mes, o desde/hasta (fecha = día operativo, o fecha y hora)."""
    hoy = date.fromisoformat(dia_operativo())
    r = q.get("rango", [""])[0]
    if r == "hoy":
        return hoy.isoformat(), hoy.isoformat(), None, None
    if r == "ayer":
        a = (hoy - timedelta(days=1)).isoformat()
        return a, a, None, None
    if r == "semana":
        return (hoy - timedelta(days=hoy.weekday())).isoformat(), hoy.isoformat(), None, None
    if r == "mes":
        return hoy.replace(day=1).isoformat(), hoy.isoformat(), None, None
    desde = q.get("desde", [""])[0] or hoy.isoformat()
    hasta = q.get("hasta", [""])[0] or desde
    if "T" in desde or "T" in hasta:  # intervalo exacto por fecha y hora
        try:
            d1 = datetime.fromisoformat(desde).replace(tzinfo=TZ) if "T" in desde else datetime.fromisoformat(desde + "T00:00").replace(tzinfo=TZ)
            d2 = datetime.fromisoformat(hasta).replace(tzinfo=TZ) if "T" in hasta else datetime.fromisoformat(hasta + "T23:59:59").replace(tzinfo=TZ)
        except ValueError:
            raise ValueError("Fechas inválidas.")
        return None, None, iso(d1), iso(d2)
    try:
        date.fromisoformat(desde); date.fromisoformat(hasta)
    except ValueError:
        raise ValueError("Fechas inválidas (usa AAAA-MM-DD).")
    return min(desde, hasta), max(desde, hasta), None, None


def _consulta_historial(con, q, staff):
    d1, d2, t1, t2 = _rango(q)
    conds, params = [], []
    if d1:
        conds.append("c.dia_operativo between ? and ?"); params += [d1, d2]
    else:
        conds.append("c.abierta_at between ? and ?"); params += [t1, t2]
    estado = q.get("estado", ["cerrada"])[0]
    if estado in ("abierta", "cerrada", "cancelada"):
        conds.append("c.estado = ?"); params.append(estado)
    mesero = q.get("mesero", [""])[0]
    if staff["rol"] != "admin":
        conds.append("c.mesero_id = ?"); params.append(staff["id"])
    elif mesero.isdigit():
        conds.append("c.mesero_id = ?"); params.append(int(mesero))
    mesa = _texto(q.get("mesa", [""])[0], MAX_MESA)
    if mesa:
        conds.append("c.mesa = ?"); params.append(mesa)
    metodo = q.get("metodo", [""])[0]
    rows = con.execute(f"select c.* from cuentas c where {' and '.join(conds)} order by c.abierta_at desc", params).fetchall()
    if metodo in METODOS_PAGO:
        rows = [r for r in rows if any(p["metodo"] == metodo for p in json.loads(r["pagos"] or "[]"))]
    return rows, {"desde": d1 or t1, "hasta": d2 or t2, "por_dia": bool(d1)}


def _indicadores(con, rows):
    cerradas = [r for r in rows if r["estado"] == "cerrada"]
    total = sum(r["total_c"] for r in cerradas)
    propinas = sum(r["propina_c"] for r in cerradas)
    por_metodo = {k: 0 for k in METODOS_PAGO}
    por_hora = {}
    productos = {}
    for r in cerradas:
        for p in json.loads(r["pagos"] or "[]"):
            por_metodo[p["metodo"]] = por_metodo.get(p["metodo"], 0) + p["monto_c"]
        hh = datetime.fromisoformat(r["abierta_at"]).astimezone(TZ).hour
        por_hora[hh] = por_hora.get(hh, 0) + 1
        for pe in con.execute("select lineas from pedidos where cuenta_id = ? and estado = 'tomado'", (r["id"],)):
            for l in json.loads(pe["lineas"]):
                if l["cantidad"] > 0:
                    k = l["nombre"] + (f" {l['detalle']}" if l.get("detalle") and l["tipo"] != "vuelo" else "")
                    productos[k] = productos.get(k, 0) + l["cantidad"]
    return {
        "cuentas": len(cerradas), "canceladas": sum(1 for r in rows if r["estado"] == "cancelada"),
        "abiertas": sum(1 for r in rows if r["estado"] == "abierta"),
        "total": a_pesos(total), "propinas": a_pesos(propinas),
        "ticket_promedio": a_pesos(total / len(cerradas)) if cerradas else 0,
        "por_metodo": {k: a_pesos(v) for k, v in por_metodo.items()},
        "por_hora": [{"hora": f"{k:02d}:00", "cuentas": v} for k, v in sorted(por_hora.items())],
        "top_productos": [{"producto": k, "cantidad": v} for k, v in sorted(productos.items(), key=lambda x: -x[1])[:10]],
    }


def equipo_historial(h, q, staff):
    try:
        with db() as con:
            rows, rango = _consulta_historial(con, q, staff)
            lim = entero(q.get("limite", ["50"])[0], 50, 1, 500)
            pag = entero(q.get("pagina", ["1"])[0], 1, 1, 10000)
            return 200, {"rango": rango, "indicadores": _indicadores(con, rows), "total_cuentas": len(rows),
                         "cuentas": [_cuenta_dict(con, c) for c in rows[(pag - 1) * lim: pag * lim]]}
    except ValueError as e:
        return 400, {"error": str(e)}


def equipo_historial_csv(h, q, staff):
    try:
        with db() as con:
            rows, _ = _consulta_historial(con, q, staff)
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["cuenta", "dia_operativo", "mesa", "mesero", "estado", "abierta", "cerrada", "total", "propina",
                        "efectivo", "tarjeta_credito", "tarjeta_debito", "motivo"])
            for c in rows:
                d = _cuenta_dict(con, c)
                pm = {k: 0 for k in METODOS_PAGO}
                for p in d["pagos"]:
                    pm[p["metodo"]] += p["monto"]
                w.writerow([d["id"], d["dia_operativo"], d["mesa"], d["mesero"], d["estado"], d["abierta_at"], d["cerrada_at"] or "",
                            d["total"], d["propina"], pm["efectivo"], pm["tarjeta_credito"], pm["tarjeta_debito"], d["motivo"] or ""])
            return 200, buf.getvalue()
    except ValueError as e:
        return 400, {"error": str(e)}


# ── Corte del mesero y cierre del día ────────────────────────────────────

def _resumen_corte(con, staff_id, dia):
    rows = con.execute("select * from cuentas where mesero_id = ? and dia_operativo = ?", (staff_id, dia)).fetchall()
    ind = _indicadores(con, rows)
    abiertas = [_cuenta_dict(con, c) for c in rows if c["estado"] == "abierta"]
    return rows, ind, abiertas


def equipo_corte_ver(h, q, staff):
    dia = q.get("dia", [dia_operativo()])[0]
    with db() as con:
        rows, ind, abiertas = _resumen_corte(con, staff["id"], dia)
        hecho = con.execute("select * from cortes where staff_id = ? and dia_operativo = ?", (staff["id"], dia)).fetchone()
        return 200, {"dia_operativo": dia, "indicadores": ind, "abiertas": abiertas,
                     "corte": {"id": hecho["id"], "creado_at": hecho["creado_at"], "resumen": json.loads(hecho["resumen"])} if hecho else None}


def equipo_corte_hacer(h, body, staff):
    dia = body.get("dia") or dia_operativo()
    with db() as con:
        if con.execute("select 1 from cortes where staff_id = ? and dia_operativo = ?", (staff["id"], dia)).fetchone():
            return 409, {"error": "Ya hiciste el corte de ese día."}
        rows, ind, abiertas = _resumen_corte(con, staff["id"], dia)
        if abiertas:
            return 409, {"error": f"Tienes {len(abiertas)} cuenta(s) abierta(s). Ciérralas, cancélalas o transfiérelas antes del corte.",
                         "abiertas": abiertas}
        resumen = {"staff": staff["nombre"], "dia_operativo": dia, **ind,
                   "cuentas_ids": [r["id"] for r in rows if r["estado"] in ("cerrada", "cancelada")]}
        texto = json.dumps(resumen, ensure_ascii=False, sort_keys=True)
        cur = con.execute("insert into cortes (staff_id, dia_operativo, resumen, hash, creado_at) values (?, ?, ?, ?, ?)",
                          (staff["id"], dia, texto, hashlib.sha256(texto.encode()).hexdigest(), iso()))
        con.execute("update cuentas set corte_id = ? where mesero_id = ? and dia_operativo = ? and estado in ('cerrada','cancelada')",
                    (cur.lastrowid, staff["id"], dia))
        evento(con, "corte", staff["id"], detalle={"dia": dia, "total": ind["total"]})
        return 201, {"corte": {"id": cur.lastrowid, "resumen": resumen}}


def _estado_dia(con, dia):
    # Quien tuvo cuentas ese día o hizo su corte (aunque haya quedado vacío por transferir todo).
    meseros = con.execute("select s.id as mesero_id, s.nombre from staff s where s.id in "
                          "(select mesero_id from cuentas where dia_operativo = ? union "
                          " select staff_id from cortes where dia_operativo = ?) order by s.nombre", (dia, dia)).fetchall()
    por_mesero = []
    for m in meseros:
        rows = con.execute("select * from cuentas where mesero_id = ? and dia_operativo = ?", (m["mesero_id"], dia)).fetchall()
        corte = con.execute("select id, creado_at from cortes where staff_id = ? and dia_operativo = ?", (m["mesero_id"], dia)).fetchone()
        por_mesero.append({"staff_id": m["mesero_id"], "nombre": m["nombre"], "corte": dict(corte) if corte else None,
                           **_indicadores(con, rows)})
    rows = con.execute("select * from cuentas where dia_operativo = ?", (dia,)).fetchall()
    ini = datetime.fromisoformat(dia + "T00:00").replace(tzinfo=TZ) + timedelta(hours=DIA_CORTE_HORA)
    fin = ini + timedelta(days=1)
    club = {
        "visitas": con.execute("select count(*) from visitas where creado_at >= ? and creado_at < ?", (iso(ini), iso(fin))).fetchone()[0],
        "nps": con.execute("select count(*) from nps where creado_at >= ? and creado_at < ?", (iso(ini), iso(fin))).fetchone()[0],
        "cortesias_canjeadas": con.execute("select count(*) from recompensas where canjeada_at >= ? and canjeada_at < ?",
                                           (iso(ini), iso(fin))).fetchone()[0],
    }
    pendientes = con.execute("select count(*) from pedidos where estado = 'pendiente' and creado_at >= ? and creado_at < ?",
                             (iso(ini), iso(fin))).fetchone()[0]
    cierre = con.execute("select * from cierres where dia_operativo = ?", (dia,)).fetchone()
    return {"dia_operativo": dia, "indicadores": _indicadores(con, rows), "por_mesero": por_mesero, "club": club,
            "pedidos_pendientes": pendientes,
            "cierre": {k: cierre[k] for k in ("id", "creado_at", "forzado", "motivo", "reabierto_at", "reabierto_motivo")} if cierre else None}


def equipo_cierre_ver(h, q, staff):
    with db() as con:
        caducar_pendientes(con)
        return 200, _estado_dia(con, q.get("dia", [dia_operativo()])[0])


def equipo_cierre_hacer(h, body, staff):
    dia = body.get("dia") or dia_operativo()
    forzar, motivo = bool(body.get("forzar")), _texto(body.get("motivo"), 200)
    with db() as con:
        previo = con.execute("select * from cierres where dia_operativo = ?", (dia,)).fetchone()
        if previo and not previo["reabierto_at"]:
            return 409, {"error": "Ese día ya está cerrado."}
        est = _estado_dia(con, dia)
        sin_corte = [m["nombre"] for m in est["por_mesero"] if not m["corte"]]
        abiertas = est["indicadores"]["abiertas"]
        if (sin_corte or abiertas) and not (forzar and motivo):
            return 409, {"error": "Faltan cortes o hay cuentas abiertas. Para cerrar de todos modos marca «forzar» y escribe el motivo.",
                         "sin_corte": sin_corte, "cuentas_abiertas": abiertas}
        con.execute("update pedidos set estado = 'caducado' where estado = 'pendiente'")
        texto = json.dumps(est, ensure_ascii=False, sort_keys=True)
        if previo:
            con.execute("update cierres set staff_id = ?, resumen = ?, hash = ?, forzado = ?, motivo = ?, creado_at = ?, "
                        "reabierto_at = null where id = ?",
                        (staff["id"], texto, hashlib.sha256(texto.encode()).hexdigest(), int(forzar), motivo, iso(), previo["id"]))
        else:
            con.execute("insert into cierres (dia_operativo, staff_id, resumen, hash, forzado, motivo, creado_at) values (?, ?, ?, ?, ?, ?, ?)",
                        (dia, staff["id"], texto, hashlib.sha256(texto.encode()).hexdigest(), int(forzar), motivo, iso()))
        evento(con, "cierre_dia", staff["id"], detalle={"dia": dia, "forzado": forzar, "motivo": motivo,
                                                        "total": est["indicadores"]["total"]})
        return 201, _estado_dia(con, dia)


def equipo_cierre_reabrir(h, body, staff):
    dia, motivo = body.get("dia") or dia_operativo(), _texto(body.get("motivo"), 200)
    if not motivo:
        return 400, {"error": "Escribe el motivo de la reapertura."}
    with db() as con:
        c = con.execute("select * from cierres where dia_operativo = ? and reabierto_at is null", (dia,)).fetchone()
        if not c:
            return 404, {"error": "Ese día no está cerrado."}
        con.execute("update cierres set reabierto_at = ?, reabierto_por = ?, reabierto_motivo = ? where id = ?",
                    (iso(), staff["id"], motivo, c["id"]))
        evento(con, "cierre_reabierto", staff["id"], detalle={"dia": dia, "motivo": motivo})
        return 200, _estado_dia(con, dia)


# ── Cuentas del equipo (solo admin) ──────────────────────────────────────

def equipo_staff_lista(h, q, staff):
    with db() as con:
        return 200, {"staff": [staff_publico(r) for r in con.execute("select * from staff order by activo desc, nombre")]}


def equipo_staff_crear(h, body, staff):
    with db() as con:
        try:
            sid, pin = crear_staff(con, body.get("nombre"), body.get("usuario"), body.get("rol") or "mesero", body.get("pin"))
        except ValueError as e:
            return 400, {"error": str(e)}
        evento(con, "staff_creado", staff["id"], detalle={"staff_id": sid})
        return 201, {"staff": staff_publico(con.execute("select * from staff where id = ?", (sid,)).fetchone()), "pin": pin}


def equipo_staff_editar(h, body, sid, staff):
    with db() as con:
        s = con.execute("select * from staff where id = ?", (sid,)).fetchone()
        if not s:
            return 404, {"error": "Usuario no encontrado."}
        campos, params, pin = [], [], None
        if "nombre" in body:
            n = _texto(body.get("nombre"), 60)
            if not n:
                return 400, {"error": "El nombre no puede quedar vacío."}
            campos.append("nombre = ?"); params.append(n)
        if "rol" in body:
            if body["rol"] not in ROLES:
                return 400, {"error": "Rol inválido."}
            campos.append("rol = ?"); params.append(body["rol"])
        if "activo" in body:
            if sid == staff["id"] and not body["activo"]:
                return 400, {"error": "No puedes desactivar tu propia cuenta."}
            campos.append("activo = ?"); params.append(1 if body["activo"] else 0)
        if body.get("reset_pin") or body.get("pin"):
            pin = str(body.get("pin") or f"{secrets.randbelow(10**6):06d}")
            if not re.fullmatch(r"\d{6}", pin):
                return 400, {"error": "El PIN debe tener 6 números."}
            campos.append("pin_hash = ?"); params.append(hash_staff(pin, s["sal"]))
        if not campos:
            return 400, {"error": "Nada que actualizar."}
        con.execute(f"update staff set {', '.join(campos)}, actualizado_at = ? where id = ?", params + [iso(), sid])
        if pin or body.get("activo") is False:
            con.execute("delete from staff_sesiones where staff_id = ?", (sid,))
        evento(con, "staff_editado", staff["id"], detalle={"staff_id": sid, "campos": [c.split(" ")[0] for c in campos]})
        return 200, {"staff": staff_publico(con.execute("select * from staff where id = ?", (sid,)).fetchone()),
                     **({"pin": pin} if pin else {})}


# ── Servidor ────────────────────────────────────────────────────────────────

RUTAS = [  # (método, patrón, handler, tipo) — tipo: publica | socio | admin
    ("GET", r"/api/salud", lambda h, q: (200, {"ok": True}), "publica"),
    ("GET", r"/api/ranking", api_ranking, "publica"),
    ("GET", r"/api/config", api_config, "publica"),
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
    ("POST", r"/api/pedidos", api_pedido_crear, "publica"),
    ("GET", r"/api/pedidos/([A-Za-z0-9-]{4,16})/estado", api_pedido_estado, "publica"),
    ("POST", r"/api/equipo/login", equipo_login, "publica"),
    ("POST", r"/api/equipo/logout", equipo_logout, "equipo"),
    ("GET", r"/api/equipo/yo", equipo_yo, "equipo"),
    ("GET", r"/api/equipo/companeros", equipo_companeros, "equipo"),
    ("POST", r"/api/equipo/pedidos/importar", equipo_pedido_importar, "equipo"),
    ("GET", r"/api/equipo/pedidos/([A-Za-z0-9-]{4,16})", equipo_pedido_ver, "equipo"),
    ("POST", r"/api/equipo/pedidos/([A-Za-z0-9-]{4,16})/tomar", equipo_pedido_tomar, "equipo"),
    ("POST", r"/api/equipo/pedidos/([A-Za-z0-9-]{4,16})/cancelar", equipo_pedido_cancelar, "equipo"),
    ("GET", r"/api/equipo/cuentas", equipo_cuentas, "equipo"),
    ("GET", r"/api/equipo/cuentas/(\d+)", equipo_cuenta_ver, "equipo"),
    ("POST", r"/api/equipo/cuentas/(\d+)/linea", equipo_cuenta_linea, "equipo"),
    ("POST", r"/api/equipo/cuentas/(\d+)/cerrar", equipo_cuenta_cerrar, "equipo"),
    ("POST", r"/api/equipo/cuentas/(\d+)/cancelar", equipo_cuenta_cancelar, "equipo"),
    ("POST", r"/api/equipo/cuentas/(\d+)/transferir", equipo_cuenta_transferir, "equipo"),
    ("GET", r"/api/equipo/historial", equipo_historial, "equipo"),
    ("GET", r"/api/equipo/historial\.csv", equipo_historial_csv, "equipo"),
    ("GET", r"/api/equipo/corte", equipo_corte_ver, "equipo"),
    ("POST", r"/api/equipo/corte", equipo_corte_hacer, "equipo"),
    ("GET", r"/api/equipo/cierre", equipo_cierre_ver, "equipo_admin"),
    ("POST", r"/api/equipo/cierre", equipo_cierre_hacer, "equipo_admin"),
    ("POST", r"/api/equipo/cierre/reabrir", equipo_cierre_reabrir, "equipo_admin"),
    ("GET", r"/api/equipo/staff", equipo_staff_lista, "equipo_admin"),
    ("POST", r"/api/equipo/staff", equipo_staff_crear, "equipo_admin"),
    ("PUT", r"/api/equipo/staff/(\d+)", equipo_staff_editar, "equipo_admin"),
    ("GET", r"/api/admin/ajustes", admin_ajustes, "admin"),
    ("PUT", r"/api/admin/ajustes", admin_ajustes_guardar, "admin"),
]


class Handler(BaseHTTPRequestHandler):
    server_version = "ClubCisne/2.0"
    cookie_sesion = None  # None = no tocar; "" = borrar; token = poner
    cookie_equipo = None

    def token_equipo(self):
        galleta = SimpleCookie(self.headers.get("Cookie", ""))
        return galleta[COOKIE_EQUIPO].value if COOKIE_EQUIPO in galleta else ""

    def staff_actual(self):
        tok = self.token_equipo()
        if not tok:
            return None
        with db() as con:
            con.execute("delete from staff_sesiones where expira_at < ?", (iso(),))
            r = con.execute("select s.* from staff_sesiones x join staff s on s.id = x.staff_id "
                            "where x.token = ? and s.activo = 1", (tok,)).fetchone()
            return staff_publico(r) if r else None

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
            self.send_header("Set-Cookie", f"{COOKIE}={self.cookie_sesion}; Path={COOKIE_PATH}; Max-Age={vida}; "
                                           f"HttpOnly; SameSite=Lax{seguro}")
        if self.cookie_equipo is not None:
            vida = STAFF_SESION_H * 3600 if self.cookie_equipo else 0
            seguro = "; Secure" if COOKIE_SECURE else ""
            self.send_header("Set-Cookie", f"{COOKIE_EQUIPO}={self.cookie_equipo}; Path={COOKIE_PATH}; Max-Age={vida}; "
                                           f"HttpOnly; SameSite=Strict{seguro}")
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
            args = [int(g) if g.isdigit() else g for g in coincide.groups()]
            try:
                if tipo == "admin":
                    supplied = self.headers.get("X-Cisne-Staff-Token", "")
                    if not ADMIN_TOKEN or not hmac.compare_digest(supplied.encode(), ADMIN_TOKEN.encode()):
                        return self.responder(403, {"error": "Acceso reservado al propietario."})
                if metodo in ("POST", "PUT"):
                    body = self.body()
                    if body is None:
                        return self.responder(400, {"error": "JSON inválido"})
                    entrada = [body]
                else:
                    entrada = [] if args else [q]
                if tipo in ("equipo", "equipo_admin"):
                    st = self.staff_actual()
                    if not st:
                        self.cookie_equipo = "" if self.token_equipo() else None
                        return self.responder(401, {"error": "Inicia sesión con tu usuario del equipo."})
                    if tipo == "equipo_admin" and st["rol"] != "admin":
                        return self.responder(403, {"error": "Solo un administrador puede hacer esto."})
                    return self.responder(*fn(self, *entrada, *args, st))
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
    if len(sys.argv) > 1 and sys.argv[1] == "crear-staff":
        # python3 club_server.py crear-staff <usuario> "<Nombre>" <mesero|admin> [pin6]
        _, _, usuario, nombre, rol, *resto = sys.argv
        with db() as con:
            sid, pin = crear_staff(con, nombre, usuario, rol, resto[0] if resto else None)
        print(json.dumps({"id": sid, "usuario": usuario, "rol": rol, "pin": pin}, ensure_ascii=False))
        return
    if not ADMIN_TOKEN:
        raise ValueError("Define CLUB_ADMIN_TOKEN antes de iniciar el servicio.")
    if SECRET == "dev-secret" or len(SECRET) < 32:
        raise ValueError("Define CLUB_SECRET con al menos 32 caracteres aleatorios.")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Club Cisne Negro escuchando en {HOST}:{PORT} (db={DB_PATH})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
