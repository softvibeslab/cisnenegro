# Cisne Negro — Plan de ejecución

> Seis fases con checkpoints de aprobación (playbook Softvibes / `prospecta-mvp`). Nada se publica, despliega ni se envía al cliente sin autorización explícita.

## Estructura de la carpeta

```
cisne-negro-cerveceria/
├── README.md                    # estado y siguiente paso
├── 01-base-conocimientos.md     # fuente única de verdad (datos + fuentes)
├── 02-propuesta-marca-digital.md
├── 03-plan-ejecucion.md         # este archivo
├── scraping/
│   ├── raw/                     # JSON crudos por fuente y fecha (no se editan)
│   └── scripts/                 # scrapers reproducibles
├── analisis/                    # informe interactivo de presencia digital
├── landing/                     # sitio (fork de malandra-cerveceria)
├── menu-digital/                # data del tenant MenuVibes + maridaje
└── assets/                      # logo, fotos aprobadas, videos
```

---

## Fase 0 — Decisiones previas ✅
- [x] Definir si Cisne Negro es **cliente** (con acceso a sus cuentas) o **prospecto** (solo datos públicos y outreach). Esto cambia el alcance del scraping y del contacto.
- [ ] Corregir de inmediato la landing de Abacus (teléfono y horario) si es nuestra o del cliente.
- [ ] Llevar las preguntas abiertas de la base de conocimientos (§9) a la primera llamada.

**Checkpoint 0:** confirmar alcance y precio.

## Fase 1 — Scraping de redes y huella digital ✅

**Regla:** solo datos públicos, ritmo bajo y sin evadir logins ni bloqueos. Si es cliente, preferir la **exportación oficial** (Meta Business Suite e Insights de Google Business), que es más completa y no tiene riesgo de bloqueo.

| Fuente | Qué extraer | Herramienta |
|---|---|---|
| Instagram @cisnenegro.mx | Últimos 100–150 posts: fecha, tipo (reel/carrusel/foto), caption, hashtags, likes, comentarios, vistas de reel; highlights; bio | Playwright con sesión propia (precedente: hopepaoo) o Apify `instagram-scraper` |
| Facebook | Posts, eventos, recomendaciones, info de la página | Apify `facebook-pages-scraper` |
| Google Maps | Rating, reseñas completas (texto, estrellas, fecha, respuesta del dueño), fotos, horario, atributos | skill `google-maps-scraper` |
| Competencia | Mismos datos de 4–6 cervecerías y bares de Pachuca/Hidalgo (Hacienda, La Vizcaína, La Minera + taprooms de Pachuca) | Google Maps + IG |
| Sitios web | cisnenegro.mx y landing de Abacus: texto, meta, velocidad, enlaces | Playwright + Lighthouse |
| Agregadores | Tripadvisor, Restaurant Guru, Uber Eats, Untappd | Nimble / WebFetch |

**Salida:** `scraping/raw/<fuente>-<fecha>.json` y un `scraping/dataset.json` normalizado (un esquema común para posts y otro para reseñas).

**Checkpoint 1:** revisar la calidad del dataset antes de analizar.

## Fase 2 — Análisis interactivo de presencia digital ✅

Informe HTML en `analisis/index.html`, mismo formato que los análisis previos (Mystic Nails, Fabiola, Hopepaoo):
1. Resumen ejecutivo y score de presencia digital (0–100) por canal.
2. **Rendimiento de contenido:** qué formatos y temas generan más interacción; frecuencia y horarios.
3. **Voz del cliente:** análisis de temas y sentimiento de las reseñas (qué aman y qué les molesta).
4. **Consistencia NAP** (nombre, dirección, teléfono y horario en cada canal).
5. Benchmark contra la competencia.
6. SEO local: palabras clave ("cerveza artesanal Pachuca", "bar pet friendly Pachuca") y posición en Maps.
7. Recomendaciones priorizadas, alineadas con [02-propuesta](02-propuesta-marca-digital.md).

**Checkpoint 2:** aprobación del análisis, que se convierte en el material de venta y en el brief de la landing.

## Fase 3 — Landing ✅

- **Inventario primero** (regla del workspace): el nicho cervecero ya existe en **`malandra-cerveceria`** (Astro + CMS PHP/JSON, desplegado en Hostinger). Se usa como base técnica sin copiar contenido ni assets de Malandra. No hace falta buscar plantillas en Envato salvo que la dirección visual lo pida.
- **Dirección visual:** negro profundo + acento de la pluma, tipografía condensada de cartel cervecero y fotos reales del lugar. Presentar 2–3 opciones antes de construir.
- **Secciones:** Hero "¡Cuéntalo en el Cisne!" · Barril de hoy (editable desde el CMS) · Comedor · Maridajes destacados · Nuestra historia · Pasaporte Cisne · Eventos y catering (formulario a WhatsApp) · Visítanos (mapa, horario, pet friendly, Lunes de producción) · Footer con redes.
- **SEO:** schema `Brewery`/`BarOrPub` con `openingHours`, OG tags, sitemap y `noindex` mientras esté en revisión.
- **Datos:** solo los de la base de conocimientos; nada inventado (sin testimonios falsos ni teléfonos placeholder).
- **Deploy:** subdominio temporal de Hostinger, solo con autorización.

**Checkpoint 3:** aprobación del diseño y luego del contenido final.

## Fase 4 — Menú digital con maridaje ✅

- **Menú propio** en `/menu/` (HTML estático), alimentado por `sitio/data/menu.json`: barril primero, filtro por perfil, "Va perfecto con…" y "Pídelo con…" (maridaje en ambos sentidos), constructor del Vuelo del Cisne (4 × 4 oz) y fotos reales de los platillos.
- **Decisión de arquitectura (2026-10-06):** el backend de MenuVibes (Supabase en el VPS) está apagado desde el 1 de agosto. Por decisión del usuario se montó un **backend ligero propio** en lugar de reactivarlo.
- **Pendiente con el cliente:** validar los maridajes y las notas de cata, y contar la historia de cada nombre (campo `historia`).
- **QR:** imprimir el QR a `https://cisnenegro.softvibes.art/menu/` en portavasos y mesas (o al dominio final cuando migre).

## Fase 5 — Pasaporte Cisne y NPS ✅

- **Backend** `backend/club_server.py`: Python estándar + SQLite, servicio systemd `cisnenegro-club` detrás de nginx en `/api/`, con un respaldo diario a las 03:30 (CDMX). Prueba de humo: `python3 backend/test_club.py` (20 verificaciones).
- **Socios:** nombre, teléfono y PIN de 4 dígitos, con aceptación del aviso de privacidad (`/privacidad/`) y opt-in de WhatsApp.
- **Check-in** con el código del día (4 dígitos, cambia diario, lo da el equipo), una visita por día. Cortesías en la visita 5 (4 oz) y la 10 (12 oz) con código `CN-XXXXX` y vigencia de 30 días.
- **NPS** tras cada visita: **todos** reciben la invitación a Google, sin premio y con texto según el score; 0–6 → bandeja de recuperación.
- **v2 (2026-10-06):** sesión persistente por cookie HttpOnly de 180 días, CRUD de NPS y de miembros, estadísticas y KPIs, y ranking público (alias «Ana R.», con opción de ocultarse). Pruebas: 48 verificaciones.
- **Panel del equipo** `/admin/` (usuario y contraseña de nginx): código del día, canje de cortesías, métricas de 30 días, bandeja NPS con seguimiento y exportación de socios a CSV.
- **Pendiente:** reto "Vacía el barril" y Club del Barril (avisos de barril nuevo por WhatsApp), que se anuncian como "Próximamente". También falta validar el aviso de privacidad con el cliente (razón social y responsable).

## Fase 6 — Lanzamiento y operación ← SIGUIENTE

**Semana 1 (con el cliente)**
- [ ] Recorrido del sitio, el menú y el panel con los dueños; aprobar maridajes, notas de cata, historia de cada nombre y aviso de privacidad (razón social, casilla 18+).
- [ ] Capacitación del equipo (15 min): código del día, canje de cortesías, alta en barra, bandeja NPS y cómo recuperar a un detractor por WhatsApp.
- [ ] Imprimir el QR del menú (`/assets/qr/menu-qr.svg`) en portavasos y mesas, más un cartel "Pasaporte Cisne".
- [ ] Arreglos rápidos: retirar la landing de Abacus, corregir Tripadvisor, renombrar a "Cervecería Cisne Negro" y agregar la categoría "Cervecería/Brewpub" en Google, crear el perfil de Untappd y enlazar redes y WhatsApp en cisnenegro.mx.
- [ ] **Responder las 69 reseñas de Google** (empezando por las 9 críticas). Requiere el acceso B3 del backlog.

**Semana 2–4**
- [ ] Decidir el dominio final: `menu.cisnenegro.mx` / `club.cisnenegro.mx` apuntando al VPS, o migrar el sitio completo desde Squarespace. Al migrar, quitar `noindex` y regenerar el QR.
- [ ] Calendario editorial de 30 días con los formatos de la propuesta §4.6 (barril de la semana, lunes de producción, maridaje del finde, comunidad y eventos) y reactivar TikTok.
- [ ] Gamificación G1: plumas y combo «Cuéntalo» (ver [04-gamificacion.md](04-gamificacion.md)).
- [ ] Primera revisión mensual de KPIs en el panel (Estadísticas) contra las metas de la propuesta §5.

**Continuo:** backlog del cliente B1–B4 (exportación de Meta, Business Suite, Google admin, Threads).

## Cronograma resumido

| Semana | Entregables |
|---|---|
| 1 | Fase 0 + arreglos rápidos · Scraping · Inicio del análisis |
| 2 | Análisis aprobado · Diseño de landing · Carga del menú |
| 3 | Landing en revisión · Módulo de maridaje · Lealtad + NPS en piloto |
| 4 | Ajustes del piloto · Lanzamiento · Calendario de redes |

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Bloqueo o violación de ToS al scrapear IG/FB | Exportaciones oficiales si es cliente; ritmo bajo y solo datos públicos si es prospecto |
| Datos del menú desactualizados (los barriles rotan) | El switch "en barril" en el dashboard y un responsable del cliente |
| Supabase de MenuVibes apagado desde ago 2026 | Resuelto con un backend propio del club (decisión del 2026-10-06) |
| Maridajes sin validar | Revisión obligatoria por los cerveceros (checkpoint 4) |
| Confusión entre los dos sitios | Una sola URL canónica; redirigir o retirar la de Abacus |
