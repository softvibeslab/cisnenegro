"""Servidor de desarrollo: replica en local lo que hace nginx en producción.

- Sirve ../sitio/ como estático.
- Redirige /api/* al club (club_server.py) que levanta en segundo plano con una DB de prueba.

Uso: python3 backend/dev_server.py [puerto=8080]
El código del día se imprime al arrancar (secreto de desarrollo "dev").
"""
import http.server
import os
import subprocess
import sys
import urllib.error
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
SITIO = os.path.join(AQUI, "..", "sitio")
PUERTO = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
CLUB_PORT = str(PUERTO + 1000)  # 8080 → 9080: cada servidor de desarrollo tiene su propio club
CLUB = f"http://127.0.0.1:{CLUB_PORT}"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITIO, **kw)

    def proxy(self):
        n = int(self.headers.get("Content-Length") or 0)
        req = urllib.request.Request(CLUB + self.path, data=self.rfile.read(n) if n else None,
                                     method=self.command,
                                     headers={k: v for k, v in self.headers.items()
                                              if k.lower() in ("content-type", "authorization", "cookie")})
        try:
            with urllib.request.urlopen(req) as r:
                status, headers, body = r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            status, headers, body = e.code, e.headers, e.read()
        self.send_response(status)
        self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
        for galleta in headers.get_all("Set-Cookie") or []:
            self.send_header("Set-Cookie", galleta)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        return self.proxy() if self.path.startswith("/api/") else super().do_GET()

    def do_POST(self):
        return self.proxy() if self.path.startswith("/api/") else self.send_error(405)

    do_PUT = do_POST
    do_DELETE = do_POST


if __name__ == "__main__":
    env = {**os.environ, "CLUB_DB": os.path.join(AQUI, f"dev-{PUERTO}.db"), "CLUB_SECRET": "dev", "CLUB_PORT": CLUB_PORT,
           "CLUB_COOKIE_SECURE": "0"}
    club = subprocess.Popen([sys.executable, os.path.join(AQUI, "club_server.py")], env=env)
    sys.path.insert(0, AQUI)
    import club_server
    club_server.SECRET = "dev"
    print(f"Sitio en http://127.0.0.1:{PUERTO}  ·  código del día (dev): {club_server.codigo_del_dia()}", flush=True)
    try:
        http.server.ThreadingHTTPServer(("127.0.0.1", PUERTO), Handler).serve_forever()
    finally:
        club.terminate()
