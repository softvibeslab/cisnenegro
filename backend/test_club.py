"""Prueba de humo del club v2: levanta el servidor con una DB temporal y recorre el flujo completo.

Uso: python3 backend/test_club.py
"""
import http.cookiejar
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
PORT = "8799"
BASE = f"http://127.0.0.1:{PORT}"
V1_SCHEMA = """
create table socios (id integer primary key, nombre text not null, telefono text not null unique,
  pin_hash text not null, acepta_privacidad_at text not null, acepta_whatsapp integer not null default 0,
  creado_at text not null);
create table visitas (id integer primary key, socio_id integer not null references socios(id), dia text not null,
  creado_at text not null, unique (socio_id, dia));
create table nps (id integer primary key, socio_id integer not null references socios(id),
  visita_id integer not null unique references visitas(id), score integer not null, comentario text,
  creado_at text not null, seguimiento text not null default 'nuevo', notas text, actualizado_at text);
"""


class Cliente:
    """Un navegador: guarda cookies como lo haría Safari/Chrome."""

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, path, data=None, token=None):
        req = urllib.request.Request(BASE + path, method=method,
                                     data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {token}"} if token else {})})
        try:
            with self.op.open(req) as r:
                body = r.read().decode("utf-8-sig")
                return r.status, (json.loads(body) if "json" in r.headers["Content-Type"] else body)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())


def main():
    tmp = tempfile.mkdtemp()
    dbp = os.path.join(tmp, "t.db")
    # Base con el esquema v1 y un socio previo: la v2 debe migrarla sin perder datos.
    con = sqlite3.connect(dbp)
    con.executescript(V1_SCHEMA)
    con.execute("insert into socios values (1, 'Socio Viejo', '7719999999', 'x', '2026-10-01', 0, "
                "'2026-10-01T10:00:00-06:00')")
    con.commit()
    con.close()
    env = {**os.environ, "CLUB_DB": dbp, "CLUB_SECRET": "test", "CLUB_PORT": PORT, "CLUB_COOKIE_SECURE": "0"}
    srv = subprocess.Popen([sys.executable, os.path.join(AQUI, "club_server.py")], env=env)
    ok = 0
    try:
        nav, otro, admin = Cliente(), Cliente(), Cliente()
        for _ in range(50):
            try:
                admin.call("GET", "/api/salud")
                break
            except Exception:
                time.sleep(0.1)
        sys.path.insert(0, AQUI)
        import club_server
        club_server.SECRET = "test"
        codigo = club_server.codigo_del_dia()

        def check(cond, msg):
            nonlocal ok
            assert cond, msg
            ok += 1

        def sql(q, *p):
            c = sqlite3.connect(dbp)
            c.execute(q, p)
            c.commit()
            c.close()

        cols = {r[1] for r in sqlite3.connect(dbp).execute("pragma table_info(socios)")}
        check({"mostrar_ranking", "notas"} <= cols, "migración v1 → v2 agrega columnas")
        s, r = admin.call("GET", "/api/admin/socios?q=viejo")
        check(s == 200 and r["total"] == 1, "el socio de la v1 sigue ahí")

        # ── Registro y sesión persistente por cookie ──
        s, r = nav.call("POST", "/api/registro", {"nombre": "Ana Ruiz", "telefono": "771 123 0000", "pin": "1234"})
        check(s == 400, "rechaza registro sin aviso de privacidad")
        s, r = nav.call("POST", "/api/registro", {"nombre": "Ana Ruiz", "telefono": "+52 771 123 0000", "pin": "1234",
                                                  "acepta_privacidad": True})
        check(s == 201 and r["token"] and r["socio"]["alias"] == "Ana R.", "registro")
        tok = r["token"]
        galleta = [c for c in nav.jar if c.name == "cn_sesion"]
        check(galleta and galleta[0].value == tok and galleta[0].expires - time.time() > 170 * 86400,
              "cookie de sesión de 180 días")
        s, r = nav.call("GET", "/api/yo")
        check(s == 200 and r["socio"]["nombre"] == "Ana Ruiz", "sesión por cookie sin token (no vuelve a pedir login)")
        s, _ = otro.call("GET", "/api/yo")
        check(s == 401, "otro navegador sin cookie no entra")
        s, _ = otro.call("POST", "/api/registro", {"nombre": "Ana", "telefono": "7711230000", "pin": "1234",
                                                   "acepta_privacidad": True})
        check(s == 409, "teléfono duplicado")
        s, _ = otro.call("POST", "/api/login", {"telefono": "7711230000", "pin": "9999"})
        check(s == 401, "PIN incorrecto")
        s, r = otro.call("POST", "/api/login", {"telefono": "7711230000", "pin": "1234"})
        check(s == 200 and otro.call("GET", "/api/yo")[0] == 200, "login deja cookie")

        # ── Check-in y NPS: todos van a Google ──
        s, _ = nav.call("POST", "/api/checkin", {"codigo": "0000" if codigo != "0000" else "1111"})
        check(s == 400, "código del día incorrecto")
        s, r = nav.call("POST", "/api/checkin", {"codigo": codigo})
        check(s == 201 and r["socio"]["visitas"] == 1 and r["recompensa"] is None, "primer check-in")
        visita = r["visita_id"]
        s, r = nav.call("POST", "/api/checkin", {"codigo": codigo})
        check(s == 200 and r["ya_registrada"], "una visita por día")
        s, r = nav.call("POST", "/api/nps", {"visita_id": visita, "score": 4, "comentario": "Tardaron"})
        check(s == 201 and r["invitar_resena"] and "google.com/maps/place/Cisne+Negro" in r["resena_url"]
              and r["tono"] == "detractor", "detractor también recibe el enlace de Google")
        s, r = nav.call("POST", "/api/nps", {"visita_id": visita, "score": 10})
        check(s == 200 and r["ya_respondida"], "un NPS por visita")
        nav.call("POST", "/api/resena-click", {"visita_id": visita})
        nav.call("POST", "/api/resena-click", {"visita_id": visita})
        s, _ = nav.call("POST", "/api/resena-click", {"visita_id": 99999})
        check(s == 404, "clic a reseña con visita ajena")

        # 5ª visita con cortesía
        sql("update visitas set dia = '2020-01-01' where socio_id = 2")
        for d in ("2020-01-02", "2020-01-03", "2020-01-04"):
            sql("insert into visitas (socio_id, dia, creado_at) values (2, ?, ?)", d, d)
        s, r = nav.call("POST", "/api/checkin", {"codigo": codigo})
        check(s == 201 and r["socio"]["visitas"] == 5 and "4 oz" in r["recompensa"]["nombre"], "cortesía en la 5ª")
        cupon = r["recompensa"]["codigo"]
        s, r = admin.call("POST", "/api/admin/canjear", {"codigo": cupon[3:]})
        check(s == 200 and r["socio"] == "Ana Ruiz", "canje")
        s, _ = admin.call("POST", "/api/admin/canjear", {"codigo": cupon})
        check(s == 409, "no se canjea dos veces")

        # ── Ranking y preferencias ──
        s, r = nav.call("GET", "/api/ranking?periodo=mes")
        check(s == 200 and r["ranking"][0]["alias"] == "Ana R." and r["yo"]["posicion"] == 1
              and "telefono" not in json.dumps(r), "ranking público con alias y mi posición")
        s, r = nav.call("POST", "/api/yo/preferencias", {"mostrar_ranking": False})
        check(s == 200 and not r["socio"]["mostrar_ranking"], "salirse del ranking")
        s, r = otro.call("GET", "/api/ranking?periodo=mes")
        check(all(f["alias"] != "Ana R." for f in r["ranking"]), "oculto del ranking público")
        s, r = admin.call("GET", "/api/admin/ranking?periodo=total")
        check(s == 200 and r["ranking"][0]["nombre"] == "Ana Ruiz", "el panel ve el ranking completo")

        # ── CRUD de miembros ──
        s, r = admin.call("POST", "/api/admin/socios", {"nombre": "Beto", "telefono": "7712223333"})
        check(s == 400, "alta en barra exige aviso de privacidad")
        s, r = admin.call("POST", "/api/admin/socios", {"nombre": "Beto López", "telefono": "7712223333",
                                                        "acepta_privacidad": True})
        check(s == 201 and len(r["pin"]) == 4, "alta en barra genera PIN")
        beto, pin_beto = r["id"], r["pin"]
        s, r = Cliente().call("POST", "/api/login", {"telefono": "7712223333", "pin": pin_beto})
        check(s == 200, "el socio dado de alta en barra puede entrar")
        s, r = admin.call("PUT", f"/api/admin/socios/{beto}", {"nombre": "Alberto López", "notas": "cliente fiel"})
        check(s == 200, "editar socio")
        s, r = admin.call("PUT", f"/api/admin/socios/{beto}", {"telefono": "7714445555"})
        check(s == 200 and len(r["pin"]) == 4, "cambio de teléfono asigna PIN nuevo")
        s, _ = admin.call("PUT", f"/api/admin/socios/{beto}", {"telefono": "7711230000"})
        check(s == 409, "no permite teléfono duplicado")
        s, r = admin.call("POST", f"/api/admin/socios/{beto}/visitas", {})
        check(s == 201, "el equipo registra la visita")
        s, r = admin.call("GET", f"/api/admin/socios/{beto}")
        check(s == 200 and r["socio"]["nombre"] == "Alberto López" and r["socio"]["visitas"] == 1
              and r["visitas"][0]["origen"] == "panel", "detalle del socio")
        s, _ = admin.call("DELETE", f"/api/admin/visitas/{r['visitas'][0]['id']}")
        check(s == 200, "borrar visita")
        s, r = admin.call("GET", "/api/admin/socios?orden=visitas&q=771")
        check(s == 200 and r["socios"][0]["nombre"] == "Ana Ruiz", "lista ordenada y con búsqueda")

        # ── CRUD de NPS ──
        s, r = admin.call("POST", "/api/admin/nps", {"socio_id": beto, "score": 9, "comentario": "en papel"})
        check(s == 201, "captura manual de NPS")
        nid = r["id"]
        s, _ = admin.call("POST", "/api/admin/nps", {"socio_id": beto, "score": 8})
        check(s == 409, "un NPS por visita también en el panel")
        s, _ = admin.call("PUT", f"/api/admin/nps/{nid}", {"score": 11})
        check(s == 400, "score fuera de rango")
        s, _ = admin.call("PUT", f"/api/admin/nps/{nid}", {"score": 10, "seguimiento": "cerrado", "notas": "ok"})
        check(s == 200, "editar NPS")
        s, r = admin.call("GET", "/api/admin/nps?filtro=promotores&q=alberto")
        check(s == 200 and r["total"] == 1 and r["respuestas"][0]["score"] == 10, "filtrar y buscar NPS")
        s, r = admin.call("GET", "/api/admin/nps?filtro=pendientes")
        check(r["total"] == 1, "detractores pendientes")
        s, _ = admin.call("DELETE", f"/api/admin/nps/{nid}")
        check(s == 200, "borrar NPS")
        s, _ = admin.call("DELETE", f"/api/admin/nps/{nid}")
        check(s == 404, "borrar NPS inexistente")

        # ── KPIs ──
        s, r = admin.call("GET", "/api/admin/estadisticas?semanas=8")
        k = r["kpis"]
        check(s == 200 and len(r["semanal"]) == 8 and len(r["distribucion_nps"]) == 11
              and r["distribucion_nps"][4]["n"] == 1 and k["clicks_resena"] == 1 and k["tasa_canje_pct"] == 100,
              "estadísticas y KPIs")
        s, r = admin.call("GET", "/api/admin/resumen?dias=abc")
        check(s == 200 and r["dias"] == 30, "dias inválido usa 30")
        s, txt = admin.call("GET", "/api/admin/nps.csv")
        check(s == 200 and "Tardaron" in txt, "export NPS CSV")
        s, txt = admin.call("GET", "/api/admin/socios.csv")
        check(s == 200 and "7711230000" in txt, "export socios CSV")

        # ── Hallazgos del frontend v2 ──
        s, r = nav.call("POST", "/api/nps", {"visita_id": visita, "score": 9})
        check(r.get("tono") == "detractor", "tono también cuando el NPS ya estaba respondido")
        sql("update socios set mostrar_ranking = 0 where id = 2")  # Ana (1ª) oculta
        carlos = Cliente()
        carlos.call("POST", "/api/registro", {"nombre": "Carlos Díaz", "telefono": "7716667777", "pin": "1111",
                                              "acepta_privacidad": True})
        carlos.call("POST", "/api/checkin", {"codigo": codigo})
        s, r = carlos.call("GET", "/api/ranking?periodo=mes")
        mio = [f for f in r["ranking"] if f["alias"] == "Carlos D."][0]
        check(mio["posicion"] == r["yo"]["posicion"] and r["yo"]["participantes"] == len(r["ranking"])
              and all(f["alias"] != "Ana R." for f in r["ranking"]), "ranking público y 'yo' numeran igual con un socio oculto")
        s, r = nav.call("GET", "/api/yo")
        check(r["socio"]["ranking"]["oculto"] and r["socio"]["ranking"]["posicion"], "el oculto sabe dónde iría")
        v1 = Cliente()  # sesión de la v1: solo token, sin cookie
        s, r = v1.call("POST", "/api/login", {"telefono": "7716667777", "pin": "1111"})
        tok_v1 = r["token"]
        v1.jar.clear()
        s, _ = v1.call("GET", "/api/yo", token=tok_v1)
        check(s == 200 and any(c.name == "cn_sesion" for c in v1.jar), "sesión v1 por Bearer recibe cookie")
        s, _ = v1.call("GET", "/api/yo")
        check(s == 200, "y luego entra solo con la cookie")
        sql("insert into visitas (socio_id, dia, creado_at) select 4, d, d from (select '2020-02-01' d union "
            "select '2020-02-02' union select '2020-02-03' union select '2020-02-04')")
        sql("delete from visitas where socio_id = 4 and dia = ?", club_server.hoy())
        s, r = admin.call("POST", "/api/admin/nps", {"socio_id": 4, "score": 7})
        check(s == 201 and r["visita_nueva"] and r["recompensa"] and "4 oz" in r["recompensa"]["nombre"],
              "captura de NPS devuelve la cortesía que generó")
        s, r = admin.call("GET", "/api/admin/socios/4")
        check("notas" in r["nps"][0] and r["nps"][0]["origen"] == "panel", "ficha trae notas y origen del NPS")

        # ── Logout, borrado y vencimiento ──
        s, _ = otro.call("POST", "/api/logout", {})
        check(s == 200 and otro.call("GET", "/api/yo")[0] == 401, "logout borra la sesión")
        s, _ = admin.call("DELETE", f"/api/admin/socios/{beto}")
        check(s == 200 and admin.call("GET", f"/api/admin/socios/{beto}")[0] == 404, "borrar socio (ARCO)")
        sql("update sesiones set creado_at = '2020-01-01T00:00:00-06:00' where token = ?", tok)
        s, _ = nav.call("GET", "/api/yo")
        check(s == 401, "sesión vencida tras 180 días")
        print(f"OK — {ok} verificaciones")
    finally:
        srv.terminate()


if __name__ == "__main__":
    main()
