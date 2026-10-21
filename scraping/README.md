# Scraping — Cervecería Cisne Negro (Fase 1)

Ejecutado el 2026-10-06 (hora UTC). Cliente confirmado. Solo se usaron datos públicos.

## Inventario descargado → `../contenido/` (255 MB, fuera de git)

| Fuente | Qué se bajó | Cobertura | Herramienta |
|---|---|---|---|
| Instagram @cisnenegro.mx | **200 posts** (130 fotos, 44 reels, 26 carruseles) en una carpeta por post, con imágenes, video, `caption.txt` y `meta.json` (likes, comentarios, hashtags, menciones, últimos comentarios). Incluye perfil y avatar HD | 200 de 245 (de nov 2023 a sep 2026) | Apify `instagram-scraper` + `instagram-post-scraper` |
| TikTok @cisnenegro.mx | **14 publicaciones**: 11 videos MP4 y 3 carruseles (8 fotos + audio), con `.info.json` y descripción | 14 de 14 ✅ | `yt-dlp` + Apify `clockworks/tiktok-scraper` |
| Google Maps | Ficha completa (`ficha.json`), **69 reseñas** (`resenas.csv`) y **70 fotos** | 69 de 69 reseñas ✅, 70 de 74 fotos | Apify `compass/crawler-google-places` |
| cisnenegro.mx | HTML de Inicio, Menú y Contacto, y **46 imágenes** (incluye fotos de platillos) | Completo ✅ | curl |
| Facebook | ❌ Nada | 0 | Apify `facebook-posts-scraper` / `facebook-pages-scraper` → "Empty or private" |

Datos estructurados: `dataset.json` (214 posts de IG + TikTok y 69 reseñas, con un esquema común) y los crudos en `raw/`.

## Lo que falta y cómo conseguirlo

| Hueco | Por qué | Solución (requiere al cliente) |
|---|---|---|
| Facebook completo | La página bloquea el acceso sin sesión (probable restricción de edad por alcohol) | **Exportación oficial de Meta**: Centro de cuentas → Tu información → Descargar tu información (Página de FB + IG, formato JSON, calidad alta) |
| 45 posts de IG anteriores a nov 2023 | Instagram limita a 200 posts sin sesión | La misma exportación de Meta |
| Historias destacadas (Menú, Horario, #vacióbarril) | Requieren sesión | Exportación de Meta, o acceso de colaborador a la cuenta |
| Métricas reales (alcance, guardados, compartidos, demografía) | Solo existen en Insights | Acceso a **Meta Business Suite** como socio/colaborador, o capturas de Insights de 90 días |
| Rendimiento de Google (búsquedas, llamadas, rutas) | Es privado | Acceso de administrador al **Perfil de Empresa de Google** |
| Threads | Pide inicio de sesión; no se pudo verificar si existe | Preguntar al cliente |
| Untappd | No existe perfil de cervecería | Crearlo (propuesta §4.1) |

## Costo

Apify (plan FREE, 5 USD/mes): ≈ **1.25 USD** en total (IG 1.09 · Maps 0.08 · TikTok 0.05 · FB 0.02). Docker no estaba activo, así que la skill `google-maps-scraper` (Docker) se sustituyó por su equivalente en Apify.

## Reproducir

```bash
cd scraping
# 1) Actores (la CLI 1.9 no devuelve JSON: usar `apify runs ls <actor> --desc --json` para obtener el datasetId)
apify call apify/instagram-scraper -f inputs/ig-posts.json -s
apify datasets get-items <datasetId> --format json > raw/ig-posts-AAAAMMDD.json
# 2) Medios (los enlaces del CDN caducan en horas: correr enseguida)
python3 scripts/download_media.py AAAAMMDD
yt-dlp --write-info-json --write-thumbnail -o "../contenido/tiktok/%(upload_date)s_%(id)s.%(ext)s" https://www.tiktok.com/@cisnenegro.mx
# 3) Dataset normalizado
python3 scripts/normalize.py AAAAMMDD
```

## Hallazgos preliminares (sirven de insumo para la Fase 2)

**Instagram**
- Los carruseles tienen ~3.4× más interacción que las fotos (mediana de 70 vs. 20.5 likes+comentarios). Los reels quedan en 27, con una mediana de 279 vistas.
- La frecuencia cayó de 10–12 posts al mes (inicio de 2024) a 3–6 al mes desde mediados de 2024.
- **Los eventos y colaboraciones son el contenido ganador.** El top 10 es casi solo eventos: Oktoberfest La Jabonera (773 likes), 1er aniversario, Circuito Arte & Chela, Noche de Velas y Pizza con Pasado de Masa, yoga y cerveza, y la ilustración del 8M.
- Los hashtags son genéricos en inglés (#beer, #tap, #photo). Casi no usan hashtags locales.

**TikTok**
- Abandonado desde el 22 de agosto de 2024 (14 videos, 189 seguidores).
- Un video llegó a **50,900 vistas y 1,021 likes**: "somos el único taproom en Pachuca con cerveza independiente". El diferenciador funciona.

**Google**
- 4.5 ★ con 69 reseñas (51 de cinco estrellas, 9 de cuatro, 6 de tres y 3 de una).
- **0 respuestas del dueño.**
- La categoría es solo "Restaurante": falta "Cervecería" o "Brewpub".
- No tiene menú, enlace de reservas, publicaciones ni preguntas y respuestas.
- Quejas recurrentes en las reseñas de 3 estrellas o menos: actitud del servicio, precio de la cerveza de la casa y su frescura o calidad, y limpieza.

**Sitio web**
- Usa una foto de stock (Unsplash).
- La bio de IG sí enlaza WhatsApp: `wa.me/message/M766JUHYWQYYC1`.
