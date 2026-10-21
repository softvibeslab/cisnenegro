"""Contrato de gateway con un upstream HTTP exclusivamente local y datos aislados."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app import create_portable_app
from cms_server import now
from werkzeug.security import generate_password_hash


class LocalUpstream(BaseHTTPRequestHandler):
    """Dobla solo el transporte; test_operations valida la lógica operativa real."""
    def log_message(self, *args):
        pass

    def respond(self):
        data = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        record = {"path": self.path, "method": self.command,
                  "headers": {key.lower(): value for key, value in self.headers.items()},
                  "body": data.decode()}
        self.server.seen.append(record)
        status = 200 if self.server.healthy else 503
        if self.path.startswith("/api/admin/") and self.headers.get("X-Cisne-Staff-Token") != "internal-gateway-test-token":
            status = 403
        payload = json.dumps(record).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        if self.path.startswith("/api/echo"):
            self.send_header("Set-Cookie", "cn_sesion=sesion-ficticia; Path=/api; HttpOnly; SameSite=Lax")
            self.send_header("Set-Cookie", "cn_equipo=equipo-ficticio; Path=/api; HttpOnly; SameSite=Strict")
        self.end_headers()
        self.wfile.write(payload)

    do_GET = respond
    do_POST = respond
    do_PUT = respond
    do_DELETE = respond


class GatewayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = ThreadingHTTPServer(("127.0.0.1", 0), LocalUpstream)
        cls.thread = threading.Thread(target=cls.upstream.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.upstream.shutdown()
        cls.upstream.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cisne-gateway-test-")
        self.upstream.seen = []
        self.upstream.healthy = True
        self.app = create_portable_app({"CMS_ROOT": self.temp.name,
            "CMS_SITE": str(ROOT / "sitio"), "CMS_DEV": True,
            "CMS_ORIGIN": "http://localhost", "TESTING": True,
            "CLUB_URL": f"http://127.0.0.1:{self.upstream.server_port}",
            "STAFF_TOKEN": "internal-gateway-test-token"})
        self.client = self.app.test_client()
        with self.app.extensions["cms_db"]() as con:
            for user, role in (("owner", "owner"), ("editor", "editor")):
                con.execute("insert into users(username,name,password,role,created_at) values(?,?,?,?,?)",
                            (user, user, generate_password_hash("gateway-test-password"), role, now()))

    def tearDown(self):
        self.app.extensions["cms_media"].close()
        self.temp.cleanup()

    def login(self, user="owner"):
        response = self.client.post("/cms/api/login", json={"username": user, "password": "gateway-test-password"},
                                    headers={"Origin": "http://localhost"})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json["csrf"]

    def test_proxy_preserves_both_cookies_and_strips_privileged_headers(self):
        client = self.app.test_client(use_cookies=False)
        response = client.post("/api/echo?scope=local", json={"prueba": True}, headers={
            "Origin": "http://localhost", "X-Cisne-Staff-Token": "forged", "X-Cisne-Staff": "forged",
            "Cookie": "cn_sesion=sesion-local", "Authorization": "Bearer token-ficticio",
            "X-Real-IP": "203.0.113.90"})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        cookies = response.headers.getlist("Set-Cookie")
        self.assertEqual(len(cookies), 2)
        self.assertTrue(any(value.startswith("cn_sesion=") for value in cookies))
        self.assertTrue(any(value.startswith("cn_equipo=") for value in cookies))
        forwarded = response.json["headers"]
        self.assertNotIn("x-cisne-staff-token", forwarded)
        self.assertNotIn("x-cisne-staff", forwarded)
        self.assertEqual(forwarded["x-real-ip"], "127.0.0.1")
        self.assertEqual(forwarded["cookie"], "cn_sesion=sesion-local")
        self.assertEqual(forwarded["authorization"], "Bearer token-ficticio")
        self.assertEqual(response.json["path"], "/api/echo?scope=local")

    def test_admin_cannot_bypass_owner_or_csrf_through_generic_proxy(self):
        for path in ("/api/admin/resumen", "/api/%61dmin/resumen", "/api/admin%2fresumen"):
            response = self.client.get(path, headers={"X-Cisne-Staff-Token": "internal-gateway-test-token"})
            self.assertEqual(response.status_code, 401, path)
        self.assertEqual(self.upstream.seen, [])
        self.login("editor")
        self.assertEqual(self.client.get("/api/admin/resumen").status_code, 403)
        self.assertEqual(self.upstream.seen, [])
        csrf = self.login("owner")
        self.assertEqual(self.client.post("/api/admin/ajustes", json={}).status_code, 403)
        self.assertEqual(self.upstream.seen, [])
        response = self.client.put("/api/admin/ajustes", json={"prueba": True}, headers={
            "Origin": "http://localhost", "X-CSRF-Token": csrf, "X-Cisne-Staff-Token": "forged"})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["headers"]["x-cisne-staff-token"], "internal-gateway-test-token")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_untrusted_origin_and_oversized_body_never_reach_upstream(self):
        for path in ("/api/echo", "/api/equipo/login", "/cms/api/login"):
            response = self.client.post(path, json={}, headers={"Origin": "https://otro-sitio.invalid"})
            self.assertEqual(response.status_code, 403, path)
        response = self.client.post("/api/echo", data="x" * 20001, content_type="application/json")
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.upstream.seen, [])

    def test_private_routes_and_traversal_are_not_filesystem_access(self):
        for path in ("/.env", "/backend/app.py", "/scripts/start.py", "/cms.sqlite", "/club.db",
                     "/cms/media/media.sqlite", "/data/club.db", "/assets/../backend/app.py",
                     "/assets/%2e%2e/%2e%2e/backend/app.py", "/api/../admin/resumen"):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 404, path)
        self.assertEqual(self.upstream.seen, [])
        for path in ("/admin/", "/admin/index.html"):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(response.headers["Location"], "/cms/?next=/admin/")

    def test_private_pages_never_cache_and_public_routes_exist(self):
        for path in ("/cms/", "/equipo/", "/equipo/equipo.webmanifest"):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200, path)
                self.assertEqual(response.headers["Cache-Control"], "no-store", path)
        for path in ("/", "/menu/", "/data/menu.json", "/manifest.webmanifest", "/privacidad/", "/offline.html"):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200, path)
        with self.client.get("/sw.js") as response:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["Service-Worker-Allowed"], "/")

    def test_v2_redirect_preserves_query_but_old_api_does_not_replay(self):
        response = self.client.get("/v2/equipo/?p=PRUEBA")
        self.assertEqual(response.status_code, 308)
        self.assertEqual(response.headers["Location"], "/equipo/?p=PRUEBA")
        self.assertEqual(self.client.get("/v2/api/config").status_code, 410)
        self.assertEqual(self.client.post("/v2/api/pedidos", json={}).status_code, 405)
        self.assertEqual(self.upstream.seen, [])

    def test_health_requires_upstream_and_existing_publication(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json, {"ok": True})
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.upstream.healthy = False
        self.assertEqual(self.client.get("/healthz").status_code, 503)
        self.upstream.healthy = True
        with self.app.extensions["cms_db"]() as con:
            con.execute("update settings set value='999999' where key='published'")
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 503, response.json)
        self.assertEqual(response.json, {"ok": False})


if __name__ == "__main__":
    unittest.main()
