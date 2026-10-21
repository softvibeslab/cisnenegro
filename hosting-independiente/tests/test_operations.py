"""Pruebas HTTP aisladas; solo datos ficticios, sin consultar producción.

Ejecutar desde hosting-independiente:
    python3 -m unittest discover -s tests -p test_operations.py -v
"""
import copy
from contextlib import closing, contextmanager
import http.client
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("portable_operations", ROOT / "backend/club_server.py")
club = importlib.util.module_from_spec(spec)
spec.loader.exec_module(club)

MENU = {
    "barril": [{"id": "cerveza-prueba", "nombre": "Cerveza de pruebas", "disponible": True,
                "precios": [{"medida": "12 oz", "precio": 95}, {"medida": "4 oz", "precio": 40}]}],
    "comida": [], "latas": [], "sin_alcohol": [],
}
LINES = [{"tipo": "barril", "id": "cerveza-prueba", "variante": "12 oz", "cantidad": 2,
          "precio": 1}]


@contextmanager
def cms_connection():
    with closing(sqlite3.connect(club.CMS_DB_PATH)) as con, con:
        yield con


class OperationsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals = {name: getattr(club, name) for name in
                         ("DB_PATH", "CMS_DB_PATH", "MENU_PATH", "ADMIN_TOKEN", "SECRET", "COOKIE_SECURE", "COOKIE_PATH")}
        cls.server = club.ThreadingHTTPServer(("127.0.0.1", 0), club.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        for name, value in cls.originals.items():
            setattr(club, name, value)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cisne-operations-test-")
        root = Path(self.tmp.name)
        club.DB_PATH = str(root / "club.sqlite")
        club.CMS_DB_PATH = str(root / "cms.sqlite")
        club.MENU_PATH = str(root / "menu.json")
        club.ADMIN_TOKEN = "token-interno-aislado-de-pruebas"
        club.SECRET = "secreto-aislado-para-pruebas-operativas"
        club.COOKIE_SECURE = False
        club.COOKIE_PATH = "/api"
        club._intentos.clear()
        club._bloqueos.clear()
        club._menu_cache.update(key=None, data=None)
        club.init_db()
        with club.db() as con:
            club.crear_staff(con, "Mesero de pruebas", "mesero", "mesero", "123456")
            club.crear_staff(con, "Otro mesero", "otro", "mesero", "654321")
            club.crear_staff(con, "Admin de pruebas", "admin", "admin", "234567")
        with cms_connection() as con:
            con.executescript("""
                create table settings (key text primary key, value text not null);
                create table revisions (id integer primary key, data text not null, output text not null);
                create table drafts (id integer primary key, data text not null);
                insert into settings values ('published', '1');
            """)
        self.add_revision(1, MENU)
        Path(club.MENU_PATH).write_text(json.dumps(MENU))

    def tearDown(self):
        self.tmp.cleanup()

    def add_revision(self, rid, menu, publish=False):
        with cms_connection() as con:
            con.execute("insert into revisions values (?,?,?)",
                        (rid, json.dumps({"menu": menu}), json.dumps({"data/menu.json": json.dumps(menu)})))
            if publish:
                con.execute("update settings set value=? where key='published'", (str(rid),))

    def request(self, method, path, body=None, cookie=None, headers=None):
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        if cookie:
            request_headers["Cookie"] = cookie
        con = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            con.request(method, path, json.dumps(body) if body is not None else None, request_headers)
            response = con.getresponse()
            raw = response.read().decode("utf-8-sig")
            payload = json.loads(raw) if "json" in response.getheader("Content-Type", "") else raw
            return response.status, payload, dict(response.getheaders())
        finally:
            con.close()

    def login(self, username="mesero", pin="123456"):
        status, data, headers = self.request("POST", "/api/equipo/login", {"usuario": username, "pin": pin})
        self.assertEqual(status, 200, data)
        return headers["Set-Cookie"].split(";", 1)[0]

    def create_order(self):
        status, data, _ = self.request("POST", "/api/pedidos", {"mesa": "T-1", "lineas": LINES})
        self.assertEqual(status, 201, data)
        return data

    def register_member(self):
        body = {"nombre": "Socio de ensayo", "telefono": "0000000000", "pin": "4321",
                "acepta_privacidad": True, "acepta_whatsapp": False}
        status, data, headers = self.request("POST", "/api/registro", body)
        self.assertEqual(status, 201, data)
        return headers["Set-Cookie"].split(";", 1)[0], data

    def test_passport_registration_login_checkin_and_nps(self):
        body = {"nombre": "Socio de ensayo", "telefono": "0000000000", "pin": "4321"}
        self.assertEqual(self.request("POST", "/api/registro", body)[0], 400)
        cookie, registered = self.register_member()
        self.assertEqual(registered["socio"]["visitas"], 0)
        self.assertEqual(self.request("POST", "/api/registro", body | {"acepta_privacidad": True})[0], 409)
        self.assertEqual(self.request("GET", "/api/yo")[0], 401)
        status, _, headers = self.request("POST", "/api/logout", {}, cookie)
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertEqual(self.request("GET", "/api/yo", cookie=cookie)[0], 401)
        self.assertEqual(self.request("POST", "/api/login", {"telefono": "0000000000", "pin": "9999"})[0], 401)
        status, signed_in, headers = self.request("POST", "/api/login", {"telefono": "0000000000", "pin": "4321"})
        self.assertEqual(status, 200, signed_in)
        self.assertIn("Path=/api;", headers["Set-Cookie"])
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        code = club.codigo_del_dia()
        wrong = f"{(int(code) + 1) % 10000:04d}"
        self.assertEqual(self.request("POST", "/api/checkin", {"codigo": wrong}, cookie)[0], 400)
        status, visit, _ = self.request("POST", "/api/checkin", {"codigo": code}, cookie)
        self.assertEqual(status, 201, visit)
        self.assertFalse(visit["ya_registrada"])
        self.assertEqual(visit["socio"]["visitas"], 1)
        status, duplicate, _ = self.request("POST", "/api/checkin", {"codigo": code}, cookie)
        self.assertEqual(status, 200, duplicate)
        self.assertTrue(duplicate["ya_registrada"])
        self.assertEqual(duplicate["visita_id"], visit["visita_id"])
        self.assertEqual(duplicate["socio"]["visitas"], 1)
        score = {"visita_id": visit["visita_id"], "score": 9, "comentario": "Prueba aislada"}
        status, nps, _ = self.request("POST", "/api/nps", score, cookie)
        self.assertEqual(status, 201, nps)
        status, nps, _ = self.request("POST", "/api/nps", score | {"score": 1}, cookie)
        self.assertEqual(status, 200, nps)
        self.assertTrue(nps["ya_respondida"])
        with club.db() as con:
            self.assertEqual(con.execute("select count(*) from visitas").fetchone()[0], 1)
            self.assertEqual(con.execute("select score from nps").fetchone()[0], 9)

    def test_passport_fifth_visit_emits_reward_and_redeems_once(self):
        cookie, _ = self.register_member()
        first_day = club.ahora()
        for day in range(5):
            # Cinco días simulados, sin esperas ni inserciones directas de visitas.
            with patch.object(club, "ahora", return_value=first_day + club.timedelta(days=day)):
                status, visit, _ = self.request("POST", "/api/checkin", {"codigo": club.codigo_del_dia()}, cookie)
                self.assertEqual(status, 201, visit)
                self.assertEqual(visit["socio"]["visitas"], day + 1)
                if day < 4:
                    self.assertIsNone(visit["recompensa"])
        reward = visit["recompensa"]
        self.assertIsNotNone(reward)
        self.assertEqual(reward["nombre"], club.RECOMPENSAS[5])
        with patch.object(club, "ahora", return_value=first_day + club.timedelta(days=4)):
            code = club.codigo_del_dia()
            status, duplicate, _ = self.request("POST", "/api/checkin", {"codigo": code}, cookie)
            self.assertEqual(status, 200, duplicate)
            self.assertIsNone(duplicate["recompensa"])
            self.assertEqual(len(duplicate["socio"]["recompensas"]), 1)
            redemption = {"codigo": reward["codigo"]}
            self.assertEqual(self.request("POST", "/api/admin/canjear", redemption, cookie)[0], 403)
            admin_headers = {"X-Cisne-Staff-Token": club.ADMIN_TOKEN}
            status, redeemed, _ = self.request("POST", "/api/admin/canjear", redemption, headers=admin_headers)
            self.assertEqual(status, 200, redeemed)
            self.assertTrue(redeemed["ok"])
            self.assertEqual(self.request("POST", "/api/admin/canjear", redemption, headers=admin_headers)[0], 409)
            status, member, _ = self.request("GET", "/api/yo", cookie=cookie)
            self.assertEqual(status, 200, member)
            self.assertEqual(member["socio"]["visitas"], 5)
            self.assertEqual(member["socio"]["recompensas"], [])
        with club.db() as con:
            self.assertEqual(con.execute("select count(*) from recompensas").fetchone()[0], 1)
            self.assertEqual(con.execute("select estado from recompensas").fetchone()[0], "canjeada")

    def test_admin_requires_internal_token_even_on_loopback(self):
        for headers in ({}, {"X-Cisne-Staff-Token": "incorrecto"}, {"X-Cisne-Staff": club.ADMIN_TOKEN}):
            status, _, _ = self.request("GET", "/api/admin/resumen", headers=headers)
            self.assertEqual(status, 403)
        status, data, _ = self.request("GET", "/api/admin/resumen",
                                       headers={"X-Cisne-Staff-Token": club.ADMIN_TOKEN})
        self.assertEqual(status, 200, data)
        club.ADMIN_TOKEN = ""
        status, _, _ = self.request("GET", "/api/admin/resumen", headers={"X-Cisne-Staff-Token": ""})
        self.assertEqual(status, 403)

    def test_team_roles_and_private_cookie(self):
        self.assertEqual(self.request("GET", "/api/equipo/staff")[0], 401)
        status, _, headers = self.request("POST", "/api/equipo/login", {"usuario": "mesero", "pin": "123456"})
        self.assertEqual(status, 200)
        self.assertIn("Path=/api;", headers["Set-Cookie"])
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        mesero = headers["Set-Cookie"].split(";", 1)[0]
        self.assertEqual(self.request("GET", "/api/equipo/staff", cookie=mesero)[0], 403)
        self.assertEqual(self.request("POST", "/api/equipo/cierre", {}, cookie=mesero)[0], 403)
        self.assertEqual(self.request("GET", "/api/admin/resumen", cookie=mesero)[0], 403)
        admin = self.login("admin", "234567")
        self.assertEqual(self.request("GET", "/api/equipo/staff", cookie=admin)[0], 200)

    def test_order_to_account_payment_and_cut(self):
        order = self.create_order()
        self.assertEqual(order["total"], 190)  # Cliente mandó precio=1: servidor calcula 95 × 2.
        path = "/api/equipo/pedidos/" + order["codigo"] + "/tomar"
        self.assertEqual(self.request("POST", path, {"mesa": "T-1"})[0], 401)
        cookie = self.login()
        status, result, _ = self.request("POST", path, {"mesa": "T-1"}, cookie)
        self.assertEqual(status, 200, result)
        account = result["cuenta"]
        self.assertEqual(account["total"], 190)
        self.assertEqual(self.request("POST", path, {"mesa": "T-1"}, cookie)[0], 409)
        account_path = f'/api/equipo/cuentas/{account["id"]}'
        other = self.login("otro", "654321")
        self.assertEqual(self.request("GET", account_path, cookie=other)[0], 404)
        payment = {"propina": 10, "pagos": [{"metodo": "efectivo", "monto": 199}]}
        self.assertEqual(self.request("POST", account_path + "/cerrar", payment, cookie)[0], 400)
        payment["pagos"][0]["monto"] = 200
        status, closed, _ = self.request("POST", account_path + "/cerrar", payment, cookie)
        self.assertEqual(status, 200, closed)
        self.assertEqual(closed["cuenta"]["estado"], "cerrada")
        self.assertEqual(closed["cuenta"]["total"], 190)
        self.assertEqual(closed["cuenta"]["propina"], 10)
        self.assertEqual(self.request("POST", account_path + "/cerrar", payment, cookie)[0], 409)
        status, cut, _ = self.request("POST", "/api/equipo/corte", {}, cookie)
        self.assertEqual(status, 201, cut)
        self.assertEqual(cut["corte"]["resumen"]["total"], 190)
        with club.db() as con:
            stored = con.execute("select * from cuentas where id=?", (account["id"],)).fetchone()
            self.assertEqual(stored["total_c"], 19000)
            self.assertIsNotNone(stored["corte_id"])

    def test_only_published_prices_change_and_history_survives(self):
        original = self.create_order()
        menu = copy.deepcopy(MENU)
        menu["barril"][0]["precios"][0]["precio"] = 120
        self.add_revision(2, menu)
        with cms_connection() as con:
            con.execute("insert into drafts values (1,?)", (json.dumps({"menu": menu}),))
        self.assertEqual(self.create_order()["total"], 190)  # Borrador/revisión no publicada no cobra.
        with cms_connection() as con:
            con.execute("update settings set value='2' where key='published'")
        self.assertEqual(self.create_order()["total"], 240)
        cookie = self.login()
        status, result, _ = self.request("POST", f'/api/equipo/pedidos/{original["codigo"]}/tomar', {}, cookie)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["cuenta"]["total"], 190)
        self.assertEqual(result["cuenta"]["pedidos"][0]["lineas"][0]["id"], "cerveza-prueba")
        with cms_connection() as con:
            con.execute("update settings set value='1' where key='published'")
        self.assertEqual(self.create_order()["total"], 190)  # Restauración también invalida caché.

    def test_missing_cms_never_falls_back_to_static_prices(self):
        self.create_order()  # Calienta la caché.
        club.CMS_DB_PATH = str(Path(self.tmp.name) / "no-existe.sqlite")
        status, data, _ = self.request("POST", "/api/pedidos", {"lineas": LINES})
        self.assertEqual(status, 503, data)
        self.assertFalse(Path(club.CMS_DB_PATH).exists())  # Apertura de lectura no crea una DB vacía.

    def test_unavailable_product_rejected_after_publication(self):
        self.create_order()
        menu = copy.deepcopy(MENU)
        menu["barril"][0]["disponible"] = False
        self.add_revision(2, menu, publish=True)
        status, data, _ = self.request("POST", "/api/pedidos", {"lineas": LINES})
        self.assertEqual(status, 400, data)
        self.assertIn("agotado", data["error"])

    def test_hidden_flight_rejects_new_orders_without_changing_history(self):
        body = {"mesa": "T-3", "lineas": [{"tipo": "vuelo", "cantidad": 1,
            "cervezas": ["cerveza-prueba"] * club.VUELO_N}]}
        # Catálogos existentes sin el campo visible siguen admitiendo vuelos.
        status, original, _ = self.request("POST", "/api/pedidos", body)
        self.assertEqual(status, 201, original)
        self.assertEqual(original["total"], 40 * club.VUELO_N)
        menu = copy.deepcopy(MENU)
        menu['vuelo'] = {'nombre': 'Vuelo de prueba', 'visible': False}
        self.add_revision(2, menu, publish=True)
        status, rejected, _ = self.request("POST", "/api/pedidos", body)
        self.assertEqual(status, 400, rejected)
        self.assertIn('ya no está disponible', rejected['error'])
        cookie = self.login()
        status, account, _ = self.request("POST",
            f'/api/equipo/pedidos/{original["codigo"]}/tomar', {}, cookie)
        self.assertEqual(status, 200, account)
        self.assertEqual(account['cuenta']['total'], 40 * club.VUELO_N)
        line = account['cuenta']['pedidos'][0]['lineas'][0]
        self.assertEqual(line['tipo'], 'vuelo')
        self.assertEqual(line['precio'], 40 * club.VUELO_N)
        # Rehabilitar la oferta vuelve a admitirla con el catálogo publicado.
        menu['vuelo']['visible'] = True
        self.add_revision(3, menu, publish=True)
        self.assertEqual(self.request("POST", "/api/pedidos", body)[0], 201)

    def test_offline_import_reprices_and_deduplicates(self):
        cookie = self.login()
        body = {"datos": {"mesa": "T-2", "t": "prueba-offline", "lineas": LINES}}
        status, created, _ = self.request("POST", "/api/equipo/pedidos/importar", body, cookie)
        self.assertEqual(status, 201, created)
        self.assertEqual(created["pedido"]["total"], 190)
        status, repeated, _ = self.request("POST", "/api/equipo/pedidos/importar", body, cookie)
        self.assertEqual(status, 200, repeated)
        self.assertTrue(repeated["repetido"])
        self.assertEqual(created["pedido"]["codigo"], repeated["pedido"]["codigo"])


if __name__ == "__main__":
    unittest.main()
