"""Une los crudos de Instagram, TikTok y Google Maps en scraping/dataset.json.

Uso: python3 normalize.py [fecha]   (p. ej. 20261006)

Esquema:
  posts[]:   red, id, url, fecha, formato, texto, hashtags, likes, comentarios, vistas, carpeta
  resenas[]: red, fecha, estrellas, texto, respuesta_dueno
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "scraping" / "raw"
DATE = sys.argv[1] if len(sys.argv) > 1 else "20261006"
FORMATO_IG = {"Image": "foto", "Video": "reel", "Sidecar": "carrusel"}

posts = []
for p in json.load(open(RAW / f"ig-posts-{DATE}.json")):
    posts.append({
        "red": "instagram", "id": p["shortCode"], "url": p["url"], "fecha": p["timestamp"],
        "formato": FORMATO_IG.get(p["type"], p["type"]), "texto": p.get("caption") or "",
        "hashtags": p.get("hashtags") or [], "likes": p.get("likesCount") or 0,
        "comentarios": p.get("commentsCount") or 0,
        "vistas": p.get("videoViewCount") or p.get("videoPlayCount"),
        "carpeta": f"contenido/instagram/posts/{p['timestamp'][:10]}_{p['shortCode']}",
    })
for t in json.load(open(RAW / f"tiktok-{DATE}.json")):
    if "error" in t:
        continue
    posts.append({
        "red": "tiktok", "id": t["id"], "url": t.get("webVideoUrl"), "fecha": t.get("createTimeISO"),
        "formato": "carrusel" if t.get("isSlideshow") else "video", "texto": t.get("text") or "",
        "hashtags": [h.get("name") for h in t.get("hashtags") or []], "likes": t.get("diggCount") or 0,
        "comentarios": t.get("commentCount") or 0, "vistas": t.get("playCount"),
        "carpeta": "contenido/tiktok",
    })

g = json.load(open(RAW / f"gmaps-{DATE}.json"))[0]
resenas = [{
    "red": "google", "fecha": r.get("publishedAtDate"), "estrellas": r.get("stars"),
    "texto": r.get("text") or "", "respuesta_dueno": r.get("responseFromOwnerText"),
} for r in g.get("reviews") or []]

out = {"generado": DATE, "posts": sorted(posts, key=lambda x: x["fecha"] or ""), "resenas": resenas}
(ROOT / "scraping" / "dataset.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"dataset.json: {len(posts)} posts · {len(resenas)} reseñas")
