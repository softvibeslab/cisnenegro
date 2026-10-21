"""Entrada única: CMS/v2 y API operativa; nunca sirve el directorio de datos."""
import json
import os
import sqlite3
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

from flask import Response, jsonify, redirect, request, send_from_directory
from cms_server import create_app


def create_portable_app(config=None):
    app = create_app(config)
    site = Path(app.config['CMS_SITE']).resolve()
    club = app.config['CLUB_URL'].rstrip('/')

    @app.route('/api/<path:tail>', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def operations(tail):
        # La ruta más específica /api/admin/<tail> pertenece al CMS y exige owner+CSRF.
        if tail == 'admin' or tail.startswith('admin/'):
            return jsonify(error='Ruta no disponible.'), 404
        if '..' in tail or not all(c.isalnum() or c in '/._-' for c in tail):
            return jsonify(error='Ruta no válida.'), 404
        if request.content_length and request.content_length > 20000:
            return jsonify(error='Solicitud demasiado grande.'), 413
        body = request.get_data()
        if len(body) > 20000:
            return jsonify(error='Solicitud demasiado grande.'), 413
        headers = {k: request.headers[k] for k in ('Content-Type', 'Cookie', 'Authorization') if k in request.headers}
        headers['X-Real-IP'] = request.remote_addr or '127.0.0.1'
        query = '?' + request.query_string.decode('ascii') if request.query_string else ''
        req = urllib.request.Request(club + '/api/' + tail + query,
                                     data=body or None, headers=headers, method=request.method)
        try:
            result = urllib.request.urlopen(req, timeout=20)
        except urllib.error.HTTPError as exc:
            result = exc
        except (urllib.error.URLError, TimeoutError):
            return jsonify(error='El servicio de operación no está disponible. Intenta de nuevo.'), 503
        with result:
            response = Response(result.read(), status=result.code,
                                content_type=result.headers.get('Content-Type', 'application/json'))
            for value in result.headers.get_all('Set-Cookie', []):
                response.headers.add('Set-Cookie', value)
            if result.headers.get('Content-Disposition'):
                response.headers['Content-Disposition'] = result.headers['Content-Disposition']
            response.headers['Cache-Control'] = 'no-store'
            return response

    # Solo las rutas públicas inventariadas. Nada de rutas arbitrarias del filesystem.
    if not app.config['CMS_DEV']:
        app.add_url_rule('/assets/<path:filename>', 'public_assets',
                         lambda filename: send_from_directory(site / 'assets', filename))

    @app.get('/equipo')
    @app.get('/privacidad')
    def add_slash():
        return redirect(request.path + '/', 308)

    @app.get('/equipo/')
    @app.get('/equipo/index.html')
    def equipo():
        return send_from_directory(site / 'equipo', 'index.html')

    @app.get('/privacidad/')
    @app.get('/privacidad/index.html')
    def privacy():
        return send_from_directory(site / 'privacidad', 'index.html')

    @app.get('/equipo/equipo.webmanifest')
    def equipo_manifest():
        return send_from_directory(site / 'equipo', 'equipo.webmanifest', mimetype='application/manifest+json')

    @app.get('/manifest.webmanifest')
    def manifest():
        return send_from_directory(site, 'manifest.webmanifest', mimetype='application/manifest+json')

    @app.get('/sw.js')
    def service_worker():
        response = send_from_directory(site, 'sw.js', mimetype='application/javascript')
        response.headers['Service-Worker-Allowed'] = '/'
        return response

    @app.get('/offline.html')
    def offline():
        return send_from_directory(site, 'offline.html')

    @app.get('/robots.txt')
    def robots():
        public_host = app.config.get('PUBLIC_INDEX_HOST', '')
        if public_host and request.host == public_host and request.scheme == 'https':
            return Response('User-agent: *\nAllow: /\nDisallow: /cms\nDisallow: /admin\n'
                            'Disallow: /equipo\nDisallow: /api/\n'
                            f'Sitemap: https://{public_host}/sitemap.xml\n', mimetype='text/plain')
        return Response('User-agent: *\nDisallow: /\n', mimetype='text/plain')

    @app.get('/sitemap.xml')
    def sitemap():
        public_host = app.config.get('PUBLIC_INDEX_HOST', '')
        if not public_host or request.host != public_host or request.scheme != 'https':
            return Response('', status=404)
        urls = ''.join(f'<url><loc>https://{public_host}{path}</loc></url>'
                       for path in ('/', '/menu/', '/privacidad/'))
        return Response('<?xml version="1.0" encoding="UTF-8"?>'
                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                        + urls + '</urlset>', mimetype='application/xml')

    @app.route('/v2', defaults={'tail': ''}, methods=['GET', 'HEAD'])
    @app.route('/v2/<path:tail>', methods=['GET', 'HEAD'])
    def previous_path(tail):
        if tail.startswith('api/'):
            return jsonify(error='Abre nuevamente el menú en /menu/ para continuar.'), 410
        query = '?' + request.query_string.decode('ascii') if request.query_string else ''
        return redirect('/' + tail + query, 308)

    @app.get('/healthz')
    def health():
        try:
            db = Path(app.config['CMS_ROOT']) / 'cms.sqlite'
            with closing(sqlite3.connect(f'file:{db}?mode=ro', uri=True)) as con:
                revision = con.execute("select r.output from settings s join revisions r on r.id=cast(s.value as integer) where s.key='published'").fetchone()
                if not revision:
                    return jsonify(ok=False), 503
                catalogue = json.loads(json.loads(revision[0])['data/menu.json'])
                if not isinstance(catalogue, dict) or not all(k in catalogue for k in ('barril', 'comida')):
                    return jsonify(ok=False), 503
            with urllib.request.urlopen(club + '/api/config', timeout=3) as response:
                if response.status != 200:
                    return jsonify(ok=False), 503
            return jsonify(ok=True)
        except urllib.error.HTTPError as exc:
            exc.close()
            return jsonify(ok=False), 503
        except Exception:
            return jsonify(ok=False), 503

    @app.after_request
    def private_cache(response):
        if request.path.startswith(('/api/', '/admin', '/equipo', '/cms')) or request.path == '/healthz':
            response.headers['Cache-Control'] = 'no-store'
        return response

    return app
