"""Descarga el contenido multimedia de los datasets crudos a ../../contenido/.

Uso: python3 download_media.py [fecha]   (fecha del dataset, p. ej. 20261006)

- Instagram: una carpeta por post `AAAA-MM-DD_<shortCode>/` con imágenes, video,
  caption.txt y meta.json (likes, comentarios, hashtags, etc.).
- Google Maps: fotos del perfil y reseñas en CSV.
Es idempotente: no vuelve a bajar archivos que ya existen.
"""
import csv
import json
import pathlib
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "scraping" / "raw"
OUT = ROOT / "contenido"
DATE = sys.argv[1] if len(sys.argv) > 1 else "20261006"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36"}

jobs, errors = [], []


def queue(url, dest):
    if url and not dest.exists():
        jobs.append((url, dest))


def fetch(job):
    url, dest = job
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            dest.write_bytes(r.read())
    except Exception as e:  # registra y sigue; el reporte final lista los fallos
        errors.append({"url": url[:120], "dest": str(dest.relative_to(ROOT)), "error": str(e)})


def instagram():
    posts = []
    for f in sorted(RAW.glob("ig-posts*.json")):
        posts += json.load(open(f))
    seen = set()
    for p in posts:
        if p.get("shortCode") in seen or "error" in p:
            continue
        seen.add(p["shortCode"])
        d = OUT / "instagram" / "posts" / f"{p['timestamp'][:10]}_{p['shortCode']}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "caption.txt").write_text(p.get("caption") or "", encoding="utf-8")
        meta = {k: p.get(k) for k in ("url", "type", "productType", "timestamp", "likesCount",
                                       "commentsCount", "videoViewCount", "videoPlayCount", "hashtags",
                                       "mentions", "taggedUsers", "locationName", "alt",
                                       "latestComments", "coauthorProducers", "paidPartnership")}
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        children = p.get("childPosts") or []
        if children:
            for i, c in enumerate(children, 1):
                queue(c.get("displayUrl"), d / f"{i:02d}.jpg")
                queue(c.get("videoUrl"), d / f"{i:02d}.mp4")
        else:
            queue(p.get("displayUrl"), d / "01.jpg")
            queue(p.get("videoUrl"), d / "01.mp4")
    prof = json.load(open(RAW / f"ig-profile-{DATE}.json"))[0]
    queue(prof.get("profilePicUrlHD"), OUT / "instagram" / "perfil" / "avatar.jpg")
    (OUT / "instagram" / "perfil").mkdir(parents=True, exist_ok=True)
    (OUT / "instagram" / "perfil" / "perfil.json").write_text(
        json.dumps({k: v for k, v in prof.items() if k != "latestPosts"}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return len(seen)


def gmaps():
    g = json.load(open(RAW / f"gmaps-{DATE}.json"))[0]
    d = OUT / "google-maps"
    for i, u in enumerate(g.get("imageUrls") or [], 1):
        queue(u, d / "fotos" / f"{i:03d}.jpg")
    d.mkdir(parents=True, exist_ok=True)
    cols = ["publishedAtDate", "stars", "text", "textTranslated", "likesCount",
            "responseFromOwnerDate", "responseFromOwnerText", "reviewUrl"]
    with open(d / "resenas.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in g.get("reviews") or []:
            w.writerow(r)
    ficha = {k: v for k, v in g.items() if k not in ("reviews", "imageUrls")}
    (d / "ficha.json").write_text(json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(g.get("reviews") or [])


if __name__ == "__main__":
    n_ig = instagram()
    n_rev = gmaps()
    print(f"Instagram: {n_ig} posts · Google Maps: {n_rev} reseñas · archivos por bajar: {len(jobs)}")
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(fetch, jobs))
    (OUT / "errores-descarga.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2))
    print(f"Descargados: {len(jobs) - len(errors)} · Errores: {len(errors)}")
