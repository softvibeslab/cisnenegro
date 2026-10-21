#!/usr/bin/env python3
"""Build the offline, shareable Cisne Negro manual. Never reads private access files."""
from pathlib import Path
import base64
import html
import json
import re

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / "contenido.json").read_text())


def esc(value):
    return html.escape(str(value), quote=True)


def content_text(value):
    if isinstance(value, dict):
        return " ".join(content_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(content_text(v) for v in value)
    return str(value)


def paragraphs(values):
    return "".join(f"<p>{esc(v)}</p>" for v in values)


def safe_id(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def image_uri(name):
    path = ROOT / "capturas" / name
    if not path.is_file():
        raise FileNotFoundError(f"Falta captura: {name}")
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def figure(name, title, caption=None, extra=False):
    caption = caption or f"Captura real · {title}"
    return f'''<figure class="screen{' screen-detail' if extra else ''}">
      <button type="button" class="screen-button" data-lightbox aria-label="Ampliar captura: {esc(title)}">
        <img src="{image_uri(name)}" alt="{esc(caption)}" loading="lazy" decoding="async">
        <span class="zoom-label"><span aria-hidden="true">↗</span> Ampliar captura</span>
      </button><figcaption>{esc(caption)}</figcaption></figure>'''


chapter_nav = "".join(
    f'<a href="#{esc(p["id"])}" data-chapter-nav="{esc(p["id"])}"><span>{i:02}</span>{esc(p["title"])}</a>'
    for i, p in enumerate(data["pages"], 1)
)

roles = "".join(f'''<article class="role-card"><span class="eyebrow">PERFIL {i:02}</span>
  <h3>{esc(r['role'])}</h3><p class="role-area">{esc(r['access'])}</p>
  <dl><dt>Cómo entra</dt><dd>{esc(r['authentication'])}</dd><dt>Qué puede hacer</dt><dd>{esc(r['scope'])}</dd></dl></article>'''
  for i, r in enumerate(data["roles"], 1))

groups = list(dict.fromkeys(item["group"] for item in data["urls"]))
directory = []
for group in groups:
    cards = []
    for u in (u for u in data["urls"] if u["group"] == group):
        status = str(u.get("status", ""))
        status_text = "Acceso protegido" if status == "401" else "Enlace comprobado" if status == "200" else "Consulta de referencia"
        destination = ""
        if u.get("final_url") and u["final_url"] != u["url"].split("#")[0]:
            destination = f'<p class="redirect">Destino de la comprobación: <span>{esc(u["final_url"])}</span></p>'
        cards.append(f'''<article class="url-card" data-search-url="{esc(content_text(u))}" data-group="{esc(group)}">
          <div class="url-card-head"><span class="status-dot" aria-hidden="true"></span><span>{status_text}</span></div>
          <h4><a href="{esc(u['url'])}" target="_blank" rel="noopener noreferrer">{esc(u['label'])} <span aria-hidden="true">↗</span><span class="sr-only"> (abre en otra pestaña)</span></a></h4>
          <p class="url-address">{esc(u['url'])}</p><p>{esc(u['description'])}</p>
          <div class="access"><span>ACCESO</span>{esc(u['access'])}</div>{destination}
          <p class="verification">{esc(u.get('verification', ''))}</p></article>''')
    directory.append(f'<section class="url-group" data-url-group="{esc(group)}" aria-label="Enlaces: {esc(group)}"><div class="group-heading"><h3>{esc(group)}</h3><span>{len(cards):02} enlaces</span></div><div class="url-grid">{"".join(cards)}</div></section>')

chapters = []
for i, p in enumerate(data["pages"], 1):
    steps = "".join(f"<li>{esc(s)}</li>" for s in p.get("steps", []))
    tips = "".join(f"<li>{esc(t)}</li>" for t in p.get("tips", []))
    screenshot = figure(p["screenshot"], p["title"], p.get("screenshot_caption")) if p.get("screenshot") else ""
    extra = "".join(figure(name, "Ficha del producto" if name == "cms-producto.png" else "Ficha del archivo en MediaHub", extra=True) for name in p.get("extra_screenshots", []))
    chapters.append(f'''<article class="chapter" id="{esc(p['id'])}" data-search-chapter="{esc(content_text(p))}">
      <header class="chapter-heading"><span class="chapter-number">{i:02}</span><div><p class="eyebrow">{esc(p.get('subtitle', 'Manual de usuario'))}</p><h3>{esc(p['title'])}</h3></div></header>
      <div class="chapter-copy"><div class="explanation">{paragraphs(p.get('paragraphs', []))}<aside class="tip"><h4>Tenlo a la mano</h4><ul>{tips}</ul></aside></div>
        <div class="steps"><h4>Paso a paso</h4><ol>{steps}</ol></div></div>{screenshot}{extra}
      <a href="#guia" class="back-top">Volver al inicio de la guía <span aria-hidden="true">↑</span></a></article>''')


def readable_key(key):
    return key.replace("_", " ").capitalize()


def render_facts(value):
    """Accept both plain bullet lists and the structured technical summary."""
    if isinstance(value, dict):
        return "<dl class=\"facts\">" + "".join(
            f"<div><dt>{esc(readable_key(k))}</dt><dd>{render_facts(v) if isinstance(v, (dict, list)) else esc(v)}</dd></div>"
            for k, v in value.items()
        ) + "</dl>"
    if isinstance(value, list):
        return "<ul class=\"fact-list\">" + "".join(f"<li>{render_facts(v) if isinstance(v, (dict, list)) else esc(v)}</li>" for v in value) + "</ul>"
    return f"<p>{esc(value)}</p>"


technical = ""
if data.get("technical_summary"):
    summary = data["technical_summary"]
    status_cards = "".join(f'''<article class="status-card"><p class="eyebrow">{esc(item['label'])}</p><h4>{esc(item['value'])}</h4><p>{esc(item['detail'])}</p></article>''' for item in summary.get("items", []))
    dns_rows = "".join(f"<tr><td>{esc(record['type'])}</td><td>{esc(record['name'])}</td><td>{esc(record['value'])}</td><td>{esc(record['ttl'])}</td></tr>" for record in summary.get("dns_records", []))
    nameservers = "".join(f"<li>{esc(server)}</li>" for server in summary.get("nameservers", []))
    backup = summary.get("backup", {})
    backup_labels = {
        "timer_active": "Temporizador activo", "schedule": "Horario", "retention": "Retención de copias",
        "files_available": "Copias disponibles", "last_run_utc": "Último inicio · UTC", "last_completed_utc": "Última finalización · UTC",
        "last_result": "Resultado", "exit_code": "Código de salida", "restore_verified": "Restauración de prueba verificada",
        "files_verified": "Archivos verificados", "ready_media": "Medios preparados", "latest_archive": "Archivo más reciente",
        "latest_bytes": "Tamaño del respaldo · bytes", "external_initial_verified": "Copia externa inicial verificada",
    }
    backup_rows = "".join(f"<div><dt>{esc(backup_labels.get(key, readable_key(key)))}</dt><dd>{esc('Sí' if value is True else 'No' if value is False else 'Correcto' if value == 'success' else value)}</dd></div>" for key, value in backup.items())
    technical += f'''<div class="technical-card"><h3>{esc(summary.get('title', 'Estado de la instalación'))}</h3><div class="status-grid">{status_cards}</div>
      <details class="technical-detail"><summary>Detalle de DNS y respaldos</summary><div class="table-scroll"><table><caption>Registros de la página web</caption><thead><tr><th scope="col">Tipo</th><th scope="col">Nombre</th><th scope="col">Destino</th><th scope="col">TTL</th></tr></thead><tbody>{dns_rows}</tbody></table></div><h4>Servidores de nombres</h4><ul class="nameservers">{nameservers}</ul><h4>Última comprobación del respaldo</h4><dl class="facts">{backup_rows}</dl></details>
      <p class="technical-scope">{esc(summary.get('validation_scope', ''))}</p></div>'''
if data.get("providers"):
    provider_cards = "".join(f'''<article class="provider-card"><h4><a href="{esc(provider['url'])}" target="_blank" rel="noopener noreferrer">{esc(provider['name'])} <span aria-hidden="true">↗</span><span class="sr-only"> (otra pestaña)</span></a></h4><p class="url-address">{esc(provider['url'])}</p><p>{esc(provider['purpose'])}</p><dl><dt>Acceso</dt><dd>{esc(provider['authentication'])}</dd></dl><p class="verification">{esc(provider['verification'])}</p></article>''' for provider in data["providers"])
    technical += '<div class="technical-card"><h3>Proveedores y gestión</h3><div class="provider-grid">' + provider_cards + '</div></div>'
technical_section = f'''<section class="section" id="estado"><div class="section-heading"><p class="eyebrow">INFORME DE ENTREGA</p><h2>La instalación,<br>en orden.</h2><p>Referencia técnica y cuentas de gestión. Las credenciales se entregan por separado.</p></div><div class="technical-grid">{technical}</div></section>''' if technical else ""
tech_nav = '<a href="#estado"><span>03</span>Estado y proveedores</a>' if technical else ""

template = r'''<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="color-scheme" content="light"><title>Cisne Negro · Informe y manual de usuario</title>
<style>
:root{--ink:#171713;--muted:#626259;--paper:#f7f5ef;--white:#fffefb;--orange:#e94d17;--line:#dcd9cf;--soft:#eeebe2;--gold:#c7a15e;--sidebar:274px;--radius:15px}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:88px}body{margin:0;background:var(--paper);color:var(--ink);font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.6}button,input,select{font:inherit}button,a{-webkit-tap-highlight-color:transparent}a{color:inherit;text-underline-offset:4px}button{cursor:pointer}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid var(--orange);outline-offset:5px}button:focus-visible{outline-offset:3px}h1,h2,h3,h4,p{margin:0}h1,h2,h3{line-height:1.03;letter-spacing:-.045em}h4{line-height:1.25}img{max-width:100%;height:auto;display:block}.sr-only{position:absolute;clip:rect(0,0,0,0);clip-path:inset(50%);width:1px;height:1px;overflow:hidden;white-space:nowrap}.skip-link{position:fixed;top:8px;left:8px;transform:translateY(-200%);z-index:100;background:var(--white);padding:12px}.skip-link:focus{transform:none}[hidden]{display:none!important}.sidebar{position:fixed;inset:0 auto 0 0;width:var(--sidebar);background:var(--ink);color:#f9f6ed;padding:30px 23px 18px;z-index:20;display:flex;flex-direction:column}.brand{font-size:28px;line-height:.9;letter-spacing:-.065em;font-weight:900;text-decoration:none;display:inline-block;max-width:190px}.brand span{display:block;font-size:11px;letter-spacing:.25em;line-height:2.5;color:#d5b883;margin-top:8px}.edition{font-size:11px;color:#bab9af;margin:17px 0 21px;line-height:1.5;border-top:1px solid #393a31;padding-top:16px}.toc{min-height:0;overflow:auto;scrollbar-width:thin;scrollbar-color:#535348 transparent;flex:1}.toc summary{display:none}.toc nav>a{display:flex;gap:10px;text-decoration:none;line-height:1.45;font-size:12px;color:#cecec3;padding:9px 7px;border-radius:5px}.toc nav>a:hover,.toc nav>a:focus-visible,.toc nav>a.current{background:#34352c;color:#fff}.toc nav>a span{color:#d6af72;min-width:20px;font-variant-numeric:tabular-nums}.toc-label{font-size:10px;letter-spacing:.18em;color:#9c9e90;font-weight:700;margin:23px 7px 6px}.sidebar-foot{border-top:1px solid #393a31;margin-top:15px;padding-top:14px;font-size:10px;color:#c2c1b6}.sidebar-foot strong{font-size:11px;display:block;color:#f0ede3}.main{margin-left:var(--sidebar)}.toolbar{height:72px;display:flex;align-items:center;gap:15px;padding:0 5.3%;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:15;background:rgba(247,245,239,.97)}.search-wrap{position:relative;max-width:470px;flex:1}.search-icon{position:absolute;left:13px;top:9px;font-size:22px;color:var(--muted);pointer-events:none}.search-wrap input{width:100%;height:42px;border:1px solid var(--line);border-radius:8px;background:var(--white);padding:9px 36px 9px 41px;font-size:13px;color:var(--ink)}.print-button{margin-left:auto;border:1px solid var(--ink);border-radius:6px;padding:8px 14px;background:transparent;font-size:12px;font-weight:700;white-space:nowrap}.print-button:hover{background:var(--ink);color:white}.search-count{font-size:11px;color:var(--muted);margin-right:auto}.hero{padding:75px 5.3% 55px;position:relative;overflow:hidden}.eyebrow{font-size:10px;letter-spacing:.16em;font-weight:800;text-transform:uppercase;line-height:1.6;color:var(--muted);overflow-wrap:anywhere}.hero .eyebrow{color:#944620}.hero h1{font-size:clamp(48px,5.9vw,88px);max-width:860px;font-weight:900;margin:17px 0 24px;letter-spacing:-.067em}.hero h1 em{font-style:normal;color:var(--orange)}.hero-lead{max-width:620px;font-size:19px;line-height:1.5;color:#52544a}.hero-meta{display:flex;gap:24px;flex-wrap:wrap;margin-top:30px;font-size:12px;color:var(--muted)}.hero-meta strong{display:block;font-size:14px;color:var(--ink)}.quick-links{display:flex;gap:10px;flex-wrap:wrap;margin:28px 0 30px}.pill{display:inline-flex;gap:20px;align-items:center;padding:11px 17px;border:1px solid var(--ink);border-radius:6px;text-decoration:none;font-size:13px;font-weight:700;background:var(--white)}.pill-primary{background:var(--ink);color:var(--white)}.pill:hover{background:var(--orange);border-color:var(--orange);color:#fff}.journey{display:grid;grid-template-columns:repeat(3,1fr);background:var(--ink);color:var(--paper);border-radius:var(--radius);padding:26px 0;margin:42px 0 27px;overflow:hidden}.journey-item{padding:0 27px;border-right:1px solid #44453a;position:relative}.journey-item:last-child{border:0}.journey-item span{font-size:11px;letter-spacing:.15em;color:#d4b98a}.journey-item strong{font-size:clamp(21px,2.3vw,33px);display:block;letter-spacing:-.04em;margin:7px 0 4px}.journey-item p{font-size:12px;color:#d1d0c5;line-height:1.45;max-width:230px}.intro-note{border-left:3px solid var(--orange);padding:3px 0 3px 18px;max-width:940px;font-size:13px;color:var(--muted)}.intro-note strong{color:var(--ink);display:block;margin-bottom:5px}.section{padding:58px 5.3%;border-top:1px solid var(--line)}.section-heading{margin-bottom:30px;max-width:760px}.section-heading h2{font-size:clamp(33px,4vw,53px);margin:12px 0 18px}.section-heading>p:last-child{color:var(--muted);font-size:15px;max-width:660px}.directory-controls{display:flex;align-items:center;justify-content:space-between;gap:15px;margin:25px 0}.directory-controls label{font-size:12px;font-weight:700}.directory-controls select{background:var(--white);border:1px solid var(--line);border-radius:6px;margin-left:9px;padding:9px 28px 9px 10px;font-size:12px;max-width:100%}.directory-note{font-size:11px;color:var(--muted)}.group-heading{display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin:30px 0 14px}.group-heading h3{font-size:23px;letter-spacing:-.025em}.group-heading>span{font-size:11px;color:var(--muted)}.url-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.url-card{background:var(--white);border:1px solid var(--line);border-radius:10px;padding:21px 22px;min-width:0;transition:border-color .15s,transform .15s}.url-card:hover{border-color:#b1a083;transform:translateY(-1px)}.url-card-head{display:flex;align-items:center;gap:7px;font-size:9px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#58624e;margin-bottom:13px}.status-dot{height:5px;width:5px;border-radius:50%;background:#657647}.url-card h4{font-size:19px;letter-spacing:-.025em;margin-bottom:8px}.url-card h4 a{text-decoration:none;display:flex;gap:10px;justify-content:space-between}.url-card h4 a:hover{text-decoration:underline}.url-card h4 span{color:#9a5c31}.url-card p{font-size:12px;line-height:1.55;margin-top:8px;color:var(--muted)}.url-card .url-address{font-size:11px;overflow-wrap:anywhere;color:#805134;line-height:1.5}.access{border-top:1px solid #e8e5dc;margin-top:16px;padding-top:12px;font-size:11px;font-weight:700;line-height:1.6}.access>span{display:block;color:var(--muted);font-size:9px;letter-spacing:.12em;margin-bottom:3px}.redirect{overflow-wrap:anywhere;font-size:10px!important}.verification{font-size:9px!important;color:#737467!important}.empty-result{padding:25px;border:1px dashed var(--line);border-radius:10px;color:var(--muted);font-size:14px}.roles-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.role-card{padding:25px 22px;background:var(--white);border:1px solid var(--line);border-top:3px solid var(--orange);border-radius:9px}.role-card h3{font-size:24px;margin:13px 0;line-height:1.15}.role-area{font-size:12px;color:#805134}.role-card dl{margin:18px 0 0}.role-card dt{font-size:9px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:var(--muted);margin-top:13px}.role-card dd{margin:4px 0 0;font-size:12px;line-height:1.6}.private-note{background:var(--soft);border-radius:9px;padding:20px 24px;margin-top:20px;font-size:13px}.private-note strong{display:block;margin-bottom:3px}.technical-grid{display:grid;gap:17px}.technical-card{background:var(--white);border:1px solid var(--line);border-radius:12px;padding:25px}.technical-card h3{font-size:26px;margin-bottom:20px}.facts{margin:0}.facts>div{display:grid;grid-template-columns:minmax(130px,.3fr) 1fr;border-top:1px solid var(--line);gap:20px;padding:13px 0}.facts>div:first-child{border-top:0}.facts dt{font-weight:700;font-size:12px}.facts dd{margin:0;font-size:12px;overflow-wrap:anywhere}.fact-list{margin:0;padding-left:18px;font-size:13px}.fact-list>li{margin:9px 0}.chapter{padding:43px 0 38px;border-top:1px solid #cecabd;scroll-margin-top:90px}.chapter:first-of-type{border:0;padding-top:12px}.chapter-heading{display:flex;align-items:flex-start;gap:23px;margin-bottom:27px}.chapter-number{font-size:48px;line-height:1;color:var(--orange);letter-spacing:-.06em;font-weight:900;min-width:65px}.chapter-heading h3{font-size:clamp(27px,3.25vw,42px);margin-top:8px;max-width:820px}.chapter-copy{display:grid;grid-template-columns:1fr 1.25fr;gap:35px;margin-bottom:30px}.explanation>p{font-size:14px;line-height:1.75;margin:0 0 13px;color:#45483e}.tip{border-radius:10px;background:#ede8dc;padding:18px 19px;margin-top:22px}.tip h4{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:#7f4b2e;margin-bottom:10px}.tip ul{padding:0 0 0 15px;margin:0}.tip li{font-size:12px;line-height:1.65;margin:9px 0;color:#505244}.tip li:last-child{margin-bottom:0}.steps h4{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:17px}.steps ol{list-style:none;margin:0;padding:0;counter-reset:step}.steps li{position:relative;font-size:13px;line-height:1.7;padding:0 0 18px 38px;counter-increment:step}.steps li:last-child{padding-bottom:0}.steps li:before{content:counter(step);position:absolute;left:0;top:0;background:var(--ink);color:var(--paper);width:25px;height:25px;border-radius:50%;text-align:center;line-height:25px;font-size:11px;font-weight:700}.screen{margin:0 0 24px;min-width:0}.screen-button{padding:0;border:1px solid #cdcabf;border-radius:10px;overflow:hidden;display:block;width:100%;position:relative;background:#eae7df;box-shadow:0 7px 24px #2827190a}.screen-button img{width:100%;height:auto;max-height:650px;object-fit:contain}.zoom-label{position:absolute;right:14px;bottom:14px;background:var(--ink);color:#fff;border:1px solid #57574a;padding:7px 12px;border-radius:5px;font-size:11px;font-weight:700;opacity:.95}.zoom-label span{margin-right:7px}.screen-button:hover .zoom-label{background:#a73510}.screen figcaption{font-size:10px;line-height:1.55;color:var(--muted);margin-top:9px;padding:0 2px;max-width:800px}.screen-detail{max-width:85%;margin-left:auto;margin-right:auto}.screen-detail:before{content:'VISTA DE DETALLE';display:block;font-size:9px;font-weight:700;letter-spacing:.12em;color:#805134;margin:23px 0 10px}.back-top{display:inline-block;font-size:11px;font-weight:700;text-decoration:none;color:#656658;padding:4px 0}.back-top span{margin-left:8px}.footer{background:var(--ink);color:#e6e2d7;padding:40px 5.3%;font-size:12px}.footer .brand{font-size:28px;margin-bottom:22px}.footer p{max-width:700px;line-height:1.7;color:#bcbfb1;margin:8px 0}.footer a{color:#e5bd87}.image-dialog{padding:0;border:1px solid #5c5c50;border-radius:12px;background:#171713;color:white;width:min(96vw,1650px);max-width:96vw;max-height:96vh;overflow:auto}.image-dialog::backdrop{background:#090a08e8}.dialog-header{display:flex;align-items:center;justify-content:space-between;gap:15px;padding:15px 20px;position:sticky;top:0;background:#171713;z-index:1;border-bottom:1px solid #383a30}.dialog-header h2{font-size:15px;line-height:1.4;letter-spacing:0;max-width:85%}.dialog-header button{font-size:13px;border:1px solid #727567;background:#24271d;color:white;border-radius:5px;padding:7px 13px}.image-dialog img{width:100%;height:auto;max-height:calc(96vh - 125px);object-fit:contain}.dialog-note{padding:10px 20px;font-size:11px;color:#c7c8bc}
@media(min-width:1700px){.main>*{padding-left:max(5.3%,calc((100% - 1260px)/2));padding-right:max(5.3%,calc((100% - 1260px)/2))}.hero h1{font-size:90px}}
@media(max-width:1200px){:root{--sidebar:235px}.sidebar{padding:25px 15px}.chapter-copy{gap:24px}.roles-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.journey-item{padding:0 19px}.search-count{display:none}.screen-button img{max-height:none}}
@media(max-width:880px){html{scroll-padding-top:75px}.sidebar{position:static;width:auto;padding:21px 5.3% 0;display:block}.brand{font-size:25px}.brand span{font-size:9px}.sidebar .edition{position:absolute;right:5.3%;top:19px;border:0;margin:0;padding:0;text-align:right;max-width:190px;font-size:10px}.toc{margin-top:10px}.toc summary{display:block;font-size:12px;font-weight:700;padding:13px 0;cursor:pointer;border-top:1px solid #393a31}.toc summary:after{content:'＋';float:right}.toc[open] summary:after{content:'−'}.toc nav{padding-bottom:15px;columns:2;column-gap:20px}.toc nav>a,.toc-label{break-inside:avoid}.toc nav>a{font-size:12px}.sidebar-foot{display:none}.main{margin:0}.toolbar{height:65px}.hero{padding-top:45px}.hero h1{font-size:65px}.chapter-copy{grid-template-columns:1fr 1.1fr}.chapter-number{font-size:41px;min-width:52px}.chapter-heading{gap:17px}.chapter-heading h3{font-size:34px}.print-button{font-size:11px;padding:8px 10px}.screen-detail{max-width:92%}.section{padding-top:42px;padding-bottom:42px}}
@media(max-width:590px){.sidebar .edition{max-width:145px}.toc nav{columns:1}.toolbar{gap:8px}.search-wrap input{font-size:12px;padding-left:32px}.search-icon{left:9px;font-size:19px;top:10px}.print-button span{display:none}.print-button{width:39px;padding:8px}.hero h1{font-size:48px;margin-top:13px}.hero-lead{font-size:16px}.hero-meta{gap:15px}.hero-meta>div{flex:1;min-width:100px;font-size:10px}.hero-meta strong{font-size:12px}.hero{padding-top:35px}.eyebrow{font-size:9px}.quick-links{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:23px}.pill{font-size:12px;padding:10px 11px;justify-content:space-between;gap:5px}.journey{grid-template-columns:1fr;margin-top:29px;padding:7px 20px}.journey-item{padding:16px 0 18px;border-right:0;border-bottom:1px solid #44453a;display:grid;grid-template-columns:1fr 1.2fr;gap:0 18px}.journey-item span{font-size:9px;grid-column:1;align-self:end}.journey-item strong{font-size:24px;margin:4px 0;grid-column:1}.journey-item p{grid-column:2;grid-row:1 / span 2;align-self:center;font-size:11px}.intro-note{font-size:12px}.section-heading h2{font-size:37px}.section-heading>p:last-child{font-size:13px}.url-grid,.roles-grid{grid-template-columns:1fr}.directory-controls{display:block}.directory-controls label{display:flex;align-items:center;justify-content:space-between}.directory-note{margin-top:12px}.url-card{padding:20px}.role-card{padding:22px}.technical-card{padding:19px}.facts>div{grid-template-columns:1fr;gap:4px}.chapter{padding-top:32px}.chapter-heading{gap:14px}.chapter-number{font-size:37px;min-width:45px}.chapter-heading h3{font-size:29px;line-height:1.09}.chapter-copy{grid-template-columns:1fr;gap:22px}.explanation>p{font-size:13px}.tip{margin-top:17px}.steps li{font-size:13px;padding-bottom:17px}.screen-detail{max-width:100%}.zoom-label{font-size:9px;padding:5px 8px;right:7px;bottom:7px}.image-dialog{width:98vw;max-width:98vw;max-height:97vh}.dialog-header{padding:12px}.dialog-header h2{font-size:12px}.dialog-header button{font-size:11px}.footer{padding-top:30px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
@media print{@page{size:A4;margin:15mm}body{background:white;font-size:10pt}.sidebar,.toolbar,.quick-links,.directory-controls,.zoom-label,.back-top,dialog,.skip-link{display:none!important}.main{margin:0}.hero,.section,.footer{padding:20px 0}.hero h1{font-size:45pt}.hero-lead{font-size:14pt}.journey{print-color-adjust:exact;-webkit-print-color-adjust:exact}.section{break-before:page}.section-heading h2{font-size:30pt}.chapter{break-before:page;padding-top:12px}.chapter-heading h3{font-size:25pt}.chapter-number{font-size:35pt}.chapter-copy{grid-template-columns:1fr;gap:20px}.explanation>p,.steps li{font-size:10pt}.tip li{font-size:9pt}.tip{margin-top:12px;padding:12px}.chapter-heading,.screen,.url-card,.role-card{break-inside:avoid}.screen-button{box-shadow:none}.screen-button img{max-height:180mm}.screen-detail{max-width:100%}.url-grid{grid-template-columns:1fr 1fr}.url-card{padding:14px}.url-card h4{font-size:14pt}.url-card p{font-size:9pt}.roles-grid{grid-template-columns:1fr 1fr}.footer{background:white;color:black;border-top:1px solid #aaa}.footer p{color:#333}.footer .brand{color:black}.section-heading,.group-heading{break-after:avoid}.chapter[hidden],.url-card[hidden],.url-group[hidden]{display:block!important}}
</style></head>
<body><a class="skip-link" href="#contenido">Saltar al contenido</a>
<aside class="sidebar" aria-label="Índice del manual"><a class="brand" href="#portada">CISNE<br>NEGRO<span>CERVECERÍA · PACHUCA</span></a><p class="edition">INFORME + MANUAL<br>__DATE__</p>
<details class="toc" open><summary>Explorar el manual</summary><nav aria-label="Navegación principal"><a href="#portada"><span>↗</span>Comenzar</a><a href="#directorio"><span>01</span>Directorio de enlaces</a><a href="#roles"><span>02</span>Roles y accesos</a>__TECH_NAV__<p class="toc-label">GUÍA PASO A PASO</p>__CHAPTER_NAV__</nav></details><div class="sidebar-foot"><strong>cisnenegro.mx</strong>Documento autónomo · Sin contraseñas</div></aside>
<main class="main" id="contenido"><div class="toolbar"><div class="search-wrap"><label for="search" class="sr-only">Buscar enlaces y capítulos</label><span class="search-icon" aria-hidden="true">⌕</span><input id="search" type="search" placeholder="Buscar enlaces y capítulos…" autocomplete="off"></div><span id="search-count" class="search-count" aria-live="polite"></span><button class="print-button" id="print-button" type="button" aria-label="Imprimir el manual completo"><span aria-hidden="true">↗ </span><span>Imprimir</span><b class="print-mobile" aria-hidden="true">PDF</b></button></div>
<header class="hero" id="portada"><p class="eyebrow">INFORME DE ENTREGA · MANUAL DE USUARIO</p><h1>Detrás de cada<br><em>gran brindis.</em></h1><p class="hero-lead">Una guía para cuidar la página, contar la historia de Cisne Negro y acompañar cada visita.</p><div class="hero-meta"><div><strong>__PAGE_COUNT__ capítulos</strong>Paso a paso con capturas reales</div><div><strong>__URL_COUNT__ enlaces</strong>Producción y referencias</div><div><strong>__DATE__</strong>__EDITION__</div></div>
<div class="quick-links"><a class="pill pill-primary" href="https://cisnenegro.mx/" target="_blank" rel="noopener noreferrer">Página <span aria-hidden="true">↗</span><span class="sr-only">(otra pestaña)</span></a><a class="pill" href="https://cisnenegro.mx/menu/" target="_blank" rel="noopener noreferrer">Menú <span aria-hidden="true">↗</span><span class="sr-only">(otra pestaña)</span></a><a class="pill" href="https://cisnenegro.mx/cms/" target="_blank" rel="noopener noreferrer">CMS <span aria-hidden="true">↗</span><span class="sr-only">(otra pestaña)</span></a><a class="pill" href="https://cisnenegro.mx/equipo/" target="_blank" rel="noopener noreferrer">Equipo <span aria-hidden="true">↗</span><span class="sr-only">(otra pestaña)</span></a></div>
<div class="journey" aria-label="Tres partes de la experiencia"><div class="journey-item"><span>01 · DESCUBRIR</span><strong>La experiencia.</strong><p>Página, historias, cerveza, cocina y próximos encuentros.</p></div><div class="journey-item"><span>02 · DISFRUTAR</span><strong>El servicio.</strong><p>Menú, pedidos, cuentas y un equipo listo para atender.</p></div><div class="journey-item"><span>03 · VOLVER</span><strong>El vínculo.</strong><p>Pasaporte, visitas, cortesías y atención al cliente.</p></div></div>
<div class="intro-note"><strong>El punto de partida: cisnenegro.mx</strong><p>__INTRODUCTION__</p></div></header>
<section class="section" id="directorio"><div class="section-heading"><p class="eyebrow">01 · DIRECTORIO</p><h2>El enlace correcto.<br>Para cada tarea.</h2><p>Abre producción para el trabajo diario. El alias temporal comparte sus datos; las páginas anteriores se conservan como referencia y pertenecen a otra instalación.</p></div><div class="directory-controls"><label for="group-filter">Mostrar <select id="group-filter"><option value="">Todos los grupos</option>__GROUP_OPTIONS__</select></label><p class="directory-note">Comprobación: __DATE__ · Los enlaces abren en otra pestaña.</p></div><p class="empty-result" id="url-empty" hidden>No se encontraron enlaces. Cambia la búsqueda o el grupo.</p>__DIRECTORY__</section>
<section class="section" id="roles"><div class="section-heading"><p class="eyebrow">02 · ROLES Y ACCESOS</p><h2>Cada persona,<br>su espacio.</h2><p>CMS, Equipo y Pasaporte tienen accesos independientes. El permiso de un sistema no crea una cuenta en los demás.</p></div><div class="roles-grid">__ROLES__</div><div class="private-note"><strong>Anexo de accesos privados entregado por separado.</strong>Este manual no contiene contraseñas ni PIN. El propietario o administrador correspondiente debe asignar accesos individuales y revisar los permisos.</div></section>
__TECHNICAL_SECTION__
<section class="section guide" id="guia"><div class="section-heading"><p class="eyebrow">MANUAL DE USUARIO · __PAGE_COUNT__ CAPÍTULOS</p><h2>De la primera edición<br>al cierre del turno.</h2><p>Identifica tu tarea, sigue los pasos y compara con la pantalla. Pulsa cualquier captura para verla con detalle.</p></div><p class="empty-result" id="chapter-empty" hidden>No se encontraron capítulos. Prueba con «precios», «cobro», «imagen» o «Pasaporte».</p>__CHAPTERS__</section>
<footer class="footer"><div class="brand">CISNE NEGRO</div><p><strong>__SUBTITLE__</strong><br>Edición del __DATE__ · __EDITION__.</p><p>__CAPTURE_TYPE__. __CAPTURE_REASON__</p><p>__DEMO_NOTE__</p><p>Guía sin contraseñas. Anexo de accesos privados entregado por separado.</p><p><a href="#portada">Volver al inicio ↑</a></p></footer></main>
<dialog class="image-dialog" id="image-dialog" aria-labelledby="dialog-title"><div class="dialog-header"><h2 id="dialog-title">Captura de pantalla</h2><button type="button" id="close-dialog" autofocus>Cerrar ✕</button></div><img id="dialog-image" alt=""><p class="dialog-note">Captura real de la instalación vigente. Pulsa Escape para cerrar.</p></dialog>
<script>
(()=>{'use strict';
const search=document.getElementById('search'),groupFilter=document.getElementById('group-filter'),cards=[...document.querySelectorAll('[data-search-url]')],chapters=[...document.querySelectorAll('[data-search-chapter]')],groups=[...document.querySelectorAll('[data-url-group]')],navLinks=[...document.querySelectorAll('[data-chapter-nav]')],count=document.getElementById('search-count');
const normalize=v=>v.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const textCache=new WeakMap();[...cards,...chapters].forEach(el=>textCache.set(el,normalize(el.dataset.searchUrl||el.dataset.searchChapter||'')));
function applyFilters(){const terms=normalize(search.value.trim()).split(/\s+/).filter(Boolean),group=groupFilter.value;let urls=0,pages=0;cards.forEach(card=>{const show=(!group||card.dataset.group===group)&&terms.every(t=>textCache.get(card).includes(t));card.hidden=!show;if(show)urls++});groups.forEach(section=>section.hidden=![...section.querySelectorAll('[data-search-url]')].some(c=>!c.hidden));chapters.forEach(chapter=>{const show=terms.every(t=>textCache.get(chapter).includes(t));chapter.hidden=!show;if(show)pages++});navLinks.forEach(link=>link.hidden=document.getElementById(link.dataset.chapterNav).hidden);document.getElementById('url-empty').hidden=urls!==0;document.getElementById('chapter-empty').hidden=pages!==0;count.textContent=terms.length||group?`${urls} enlaces · ${pages} capítulos`:''}
search.addEventListener('input',applyFilters);groupFilter.addEventListener('change',applyFilters);
document.getElementById('print-button').addEventListener('click',()=>{search.value='';groupFilter.value='';applyFilters();window.print()});
const dialog=document.getElementById('image-dialog'),dialogImage=document.getElementById('dialog-image'),dialogTitle=document.getElementById('dialog-title');let opener=null;
document.querySelectorAll('[data-lightbox]').forEach(button=>button.addEventListener('click',()=>{opener=button;const img=button.querySelector('img');dialogImage.src=img.src;dialogImage.alt=img.alt;dialogTitle.textContent=img.alt;dialog.showModal();dialog.scrollTop=0}));
document.getElementById('close-dialog').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close()}});dialog.addEventListener('close',()=>{dialogImage.removeAttribute('src');if(opener)opener.focus()});
const toc=document.querySelector('.toc'),small=window.matchMedia('(max-width:880px)');toc.open=!small.matches;small.addEventListener('change',event=>{toc.open=!event.matches});document.querySelectorAll('.toc a').forEach(link=>link.addEventListener('click',()=>{if(small.matches)toc.open=false}));
if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting){navLinks.forEach(link=>link.classList.toggle('current',link.dataset.chapterNav===entry.target.id));break}}},{rootMargin:'-90px 0px -65% 0px',threshold:0});chapters.forEach(chapter=>observer.observe(chapter))}
})();
</script><style>.print-mobile{display:none}.status-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.status-card{padding:18px;background:var(--paper);border:1px solid var(--line);border-radius:9px}.status-card h4{font-size:17px;line-height:1.4;letter-spacing:-.025em;margin:10px 0;overflow-wrap:anywhere}.status-card>p:last-child{font-size:12px;color:var(--muted);line-height:1.65}.technical-detail{margin-top:22px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:14px 0;font-size:12px}.technical-detail summary{cursor:pointer;font-weight:700}.technical-detail h4{font-size:13px;margin:25px 0 12px}.table-scroll{overflow:auto}.technical-detail table{width:100%;border-collapse:collapse;font-size:12px;text-align:left;margin-top:15px}.technical-detail th,.technical-detail td{padding:9px 12px;border-bottom:1px solid var(--line)}.technical-detail caption{text-align:left;font-weight:700;margin:12px 0}.nameservers{padding-left:17px;overflow-wrap:anywhere}.technical-scope{font-size:11px;color:var(--muted);margin-top:20px}.provider-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:25px}.provider-card h4{font-size:20px;line-height:1.4;letter-spacing:-.03em}.provider-card a{text-decoration:none}.provider-card a:hover{text-decoration:underline}.provider-card p{font-size:12px;color:var(--muted);margin:13px 0}.provider-card .url-address{font-size:10px;color:#805134;overflow-wrap:anywhere}.provider-card dl{font-size:12px}.provider-card dt{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em}.provider-card dd{margin:4px 0 0}.technical-card .facts>div{grid-template-columns:1fr 1fr}@media(max-width:590px){.print-mobile{display:inline;font-size:10px}.status-grid,.provider-grid{grid-template-columns:1fr}.technical-card .facts>div{grid-template-columns:1fr;gap:4px}}@media print{.status-card,.provider-card{break-inside:avoid}}</style>
</body></html>'''

replacements = {
    "__DATE__": esc(data["date"]),
    "__EDITION__": esc(data["edition"]),
    "__PAGE_COUNT__": str(len(data["pages"])),
    "__URL_COUNT__": str(len(data["urls"])),
    "__INTRODUCTION__": esc(data["introduction"]),
    "__TECH_NAV__": tech_nav,
    "__CHAPTER_NAV__": chapter_nav,
    "__GROUP_OPTIONS__": "".join(f'<option value="{esc(g)}">{esc(g)}</option>' for g in groups),
    "__DIRECTORY__": "".join(directory),
    "__ROLES__": roles,
    "__TECHNICAL_SECTION__": technical_section,
    "__CHAPTERS__": "".join(chapters),
    "__SUBTITLE__": esc(data["subtitle"]),
    "__CAPTURE_TYPE__": esc(data["screenshots_note"]["type"]),
    "__CAPTURE_REASON__": esc(data["screenshots_note"]["reason"]),
    "__DEMO_NOTE__": esc(data["screenshots_note"]["demo_data"]),
}
for token, value in replacements.items():
    template = template.replace(token, value)
assert not re.search(r"__[A-Z_]+__", template), "Unresolved template tokens"
target = ROOT / "index.html"
target.write_text(template)
print(f"HTML listo: {len(data['pages'])} capítulos, {len(data['urls'])} enlaces, {len(data['roles'])} roles, {len(template.encode()) / 1024 / 1024:.1f} MB")
