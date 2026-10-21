"""Genera sitio/proyecto/: hub de artefactos + documentos .md renderizados con el sistema visual.

Uso: <python con el paquete markdown> deploy/build_proyecto.py
"""
import datetime
import html
import pathlib
import re

import markdown

RAIZ = pathlib.Path(__file__).resolve().parents[1]
OUT = RAIZ / "sitio" / "proyecto"

DOCS = [  # (archivo fuente, slug, título, descripción)
    ("01-base-conocimientos.md", "base-conocimientos", "Base de conocimientos",
     "Datos verificados con fuente: historia, operación, menú, huella digital y preguntas abiertas."),
    ("02-propuesta-marca-digital.md", "propuesta", "Propuesta de marca y presencia digital",
     "Diagnóstico, plataforma de marca «¡Cuéntalo en el Cisne!», maridaje, lealtad, NPS, redes y KPIs."),
    ("03-plan-ejecucion.md", "plan", "Plan de ejecución",
     "Las 6 fases, su estado, la arquitectura elegida y los riesgos."),
    ("04-gamificacion.md", "gamificacion", "Plan de gamificación del Pasaporte",
     "Plumas, combo «Cuéntalo» (publicación + calificación = 2 visitas), rachas, referidos, niveles e insignias."),
    ("BACKLOG.md", "backlog", "Backlog del cliente",
     "Lo que necesitamos de Cisne Negro: exportación de Meta, accesos y Threads."),
    ("scraping/README.md", "inventario", "Inventario de contenido (scraping)",
     "Qué se descargó de cada red, cobertura, costo y hallazgos preliminares."),
    ("sitio/DESIGN.md", "sistema-visual", "Sistema visual «Neón y tinta»",
     "Tokens, tipografías, componentes y reglas de la nueva identidad digital."),
]
LINKS = {src.split("/")[-1]: f"/proyecto/{slug}/" for src, slug, *_ in DOCS}
LINKS.update({"README.md": "/proyecto/", "scraping/README.md": "/proyecto/inventario/"})

CSS = """
:root{--tinta:#0E0D0B;--carbon:#191714;--borde:#2B2823;--hueso:#F3EDE2;--gris:#A39B8E;--neon:#F2C97D;--pico:#FF5A1F}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--tinta);color:var(--hueso);font:16px/1.65 Manrope,system-ui,sans-serif}
a{color:var(--pico)}a:focus-visible,button:focus-visible{outline:2px solid var(--pico);outline-offset:3px}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 72px}
.top{display:flex;align-items:center;gap:14px;justify-content:space-between;flex-wrap:wrap;border-bottom:1px solid var(--borde);padding-bottom:16px}
.marca{display:flex;align-items:center;gap:12px;color:var(--hueso);text-decoration:none}
.marca img{width:46px;height:46px;border-radius:50%;background:var(--hueso);border:3px solid var(--tinta);outline:2px solid var(--hueso);transform:rotate(-6deg)}
.marca b{font-family:"Big Shoulders Display",Impact,sans-serif;font-size:1.35rem;letter-spacing:.03em;text-transform:uppercase}
.chip{font:500 .78rem "JetBrains Mono",monospace;color:var(--gris);border:1px solid var(--borde);border-radius:999px;padding:4px 10px}
h1,h2,h3{font-family:"Big Shoulders Display",Impact,sans-serif;text-transform:uppercase;letter-spacing:.02em;line-height:1.05}
h1{font-size:clamp(2.2rem,6vw,3.6rem);margin:.6em 0 .2em}
.hero h1{color:var(--neon);text-shadow:0 0 18px rgba(242,201,125,.45)}
.lead{color:var(--gris);max-width:62ch;font-size:1.08rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;margin-top:18px}
.card{display:flex;flex-direction:column;gap:6px;background:var(--carbon);border:1px solid var(--borde);border-radius:14px;padding:18px;color:var(--hueso);text-decoration:none;transition:border-color .15s,transform .15s}
.card:hover{border-color:var(--pico);transform:translateY(-2px)}
.card h3{margin:0;font-size:1.35rem}.card p{margin:0;color:var(--gris);font-size:.94rem}
.card .tipo{font:500 .72rem "JetBrains Mono",monospace;color:var(--pico);text-transform:uppercase;letter-spacing:.06em}
.card.destacada{border-color:#3a352e;background:linear-gradient(160deg,#211d18,#191714)}
section{margin-top:44px}section>h2{font-size:1.6rem;margin:0;color:var(--hueso)}
.nota{background:var(--carbon);border:1px solid var(--borde);border-left:4px solid var(--pico);border-radius:8px;padding:12px 16px;color:var(--gris);font-size:.93rem;margin-top:16px}
.doc{max-width:820px}
.doc h1{color:var(--neon)}.doc h2{font-size:1.7rem;margin-top:1.8em;border-top:1px solid var(--borde);padding-top:.9em}
.doc h3{font-size:1.25rem;color:var(--neon);margin-top:1.4em}
.doc table{width:100%;border-collapse:collapse;font-size:.92rem;display:block;overflow-x:auto}
.doc th,.doc td{border:1px solid var(--borde);padding:8px 10px;text-align:left;vertical-align:top}
.doc th{background:var(--carbon);font-weight:700}
.doc code{font:500 .86em "JetBrains Mono",monospace;background:var(--carbon);border:1px solid var(--borde);border-radius:5px;padding:1px 5px}
.doc pre{background:var(--carbon);border:1px solid var(--borde);border-radius:10px;padding:14px;overflow-x:auto}
.doc pre code{border:0;padding:0;background:none}
.doc blockquote{margin:1em 0;border-left:3px solid var(--neon);padding:.2em 1em;color:var(--gris)}
.doc hr{border:0;border-top:1px solid var(--borde);margin:2em 0}
.doc a,.wrap>p>a{overflow-wrap:anywhere}
.wrap>p>a{display:inline-flex;align-items:center;min-height:44px}
@media (pointer:coarse){.marca{min-height:44px}}
@media (forced-colors:active){.card{border:1px solid CanvasText}}
footer{margin-top:56px;color:var(--gris);font-size:.85rem;border-top:1px solid var(--borde);padding-top:16px}
"""

HEAD = """<!doctype html><html lang="es-MX"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#0E0D0B"><title>{titulo}</title>
<link rel="icon" href="/assets/img/marca/favicon-192.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@800;900&family=Manrope:wght@400;600;700&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>{css}</style></head><body><div class="wrap">
<header class="top"><a class="marca" href="/proyecto/"><img src="/assets/img/marca/cisne-mascota.jpg" alt="" width="46" height="46"><b>Cisne Negro · Proyecto</b></a>
<span class="chip">Vista previa · Softvibes</span></header>"""
FOOT = """<footer>Proyecto de marca y presencia digital de Cervecería Cisne Negro · Preparado por Softvibes · Actualizado el {fecha}.</footer></div></body></html>"""


def reescribe_links(md_text):
    """Convierte enlaces relativos a .md en rutas del hub; deja intactos los absolutos."""
    def rep(m):
        destino = m.group(1).split("#")[0]
        for clave, ruta in LINKS.items():
            if destino == clave or destino.endswith("/" + clave):
                return f"]({ruta})"
        return m.group(0)
    return re.sub(r"\]\((?!https?:|/|#|mailto:)([^)\s]+)\)", rep, md_text)


def main():
    fecha = datetime.date.today().isoformat()
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])
    for src, slug, titulo, _ in DOCS:
        texto = reescribe_links((RAIZ / src).read_text(encoding="utf-8"))
        cuerpo = md.reset().convert(texto)
        cuerpo = cuerpo.replace('<a href="http', '<a target="_blank" rel="noopener" href="http')
        for fuente, _, titulo_doc, _ in DOCS:
            nombre = fuente.split("/")[-1]
            cuerpo = cuerpo.replace(f">{nombre}</a>", f">{titulo_doc}</a>").replace(f"><code>{nombre}</code></a>", f">{titulo_doc}</a>")
        destino = OUT / slug
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "index.html").write_text(
            HEAD.format(titulo=html.escape(f"{titulo} · Cisne Negro"), css=CSS)
            + f'<p style="margin-top:20px"><a href="/proyecto/">← Todos los artefactos</a></p>'
            + f'<article class="doc">{cuerpo}</article>' + FOOT.format(fecha=fecha), encoding="utf-8")

    def card(href, tipo, titulo, desc, extra="", ident=""):
        idattr = f' id="{ident}"' if ident else ""
        return (f'<a class="card {extra}"{idattr} href="{href}"><span class="tipo">{tipo}</span>'
                f'<h3>{html.escape(titulo)}</h3><p>{html.escape(desc)}</p></a>')

    entregables = "".join([
        card("/", "Sitio", "Landing nueva", "El sitio de la cervecería: barril de hoy, historia, maridajes, Pasaporte, galería, eventos y cómo llegar.", "destacada"),
        card("/menu/", "Menú QR", "Menú digital con maridaje", "La cerveza primero: filtro por perfil, Vuelo del Cisne y «Pídelo con…». Incluye el Pasaporte y el NPS.", "destacada"),
        card("/analisis/", "Informe", "Análisis de presencia digital", "Score 0–100 por canal, contenido que funciona, voz del cliente, consistencia de datos, benchmark y prioridades.", "destacada"),
        card("/admin/", "Equipo", "Panel del personal", "Código del día, canje de cortesías, NPS, detractores por recuperar y socios. Pide usuario y contraseña."),
        card("/assets/qr/menu-qr.png", "Imprimible", "QR del menú", "Código QR al menú para portavasos y mesas (PNG; también en /assets/qr/menu-qr.svg para imprenta)."),
        card("/privacidad/", "Legal", "Aviso de privacidad", "Versión preliminar para el Pasaporte Cisne, pendiente de aprobación del cliente."),
    ])
    docs = "".join(card(f"/proyecto/{slug}/", "Documento", t, d, ident=slug if slug == "propuesta" else "")
                   for _, slug, t, d in DOCS)
    index = (HEAD.format(titulo="Proyecto Cisne Negro · Artefactos", css=CSS)
             + '<div class="hero"><h1>¡Cuéntalo en el Cisne!</h1>'
             + '<p class="lead">Todo el trabajo de marca y presencia digital de Cervecería Cisne Negro en un solo lugar: '
             + 'la investigación, el análisis, la propuesta y lo que ya está construido y funcionando.</p></div>'
             + f'<section><h2>Entregables</h2><div class="grid">{entregables}</div></section>'
             + f'<section><h2>Documentos</h2><div class="grid">{docs}</div>'
             + '<p class="nota">Este dominio es una vista previa de Softvibes y no se indexa en buscadores. '
             + 'El dominio del cliente sigue siendo cisnenegro.mx.</p></section>'
             + FOOT.format(fecha=fecha))
    (OUT / "index.html").write_text(index, encoding="utf-8")
    print(f"proyecto/: índice + {len(DOCS)} documentos")


if __name__ == "__main__":
    main()
