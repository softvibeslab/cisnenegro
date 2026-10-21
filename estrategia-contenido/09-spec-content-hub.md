# Especificación: Content Hub (CMS) + Tablero de presentación

Fecha: 8 de octubre de 2026. Implementa el plan [08](08-plan-estrategia-contenido-y-content-hub.md) con las decisiones del usuario:

| Decisión | Valor |
|---|---|
| Piloto | **Del sábado 24 de octubre al domingo 29 de noviembre de 2026** (5 semanas; arranca una semana antes de Halloween; reprogramado el 10 de octubre, antes empezaba el lunes 19): Halloween (sábado 31 de octubre), Día de Muertos (1 y 2 de noviembre), Día Internacional de la Stout (jueves 5 de noviembre), Buen Fin y puente (13 al 16 de noviembre, por confirmar) y el Aniversario Año III (finales de noviembre; fecha por confirmar) |
| Ubicación | Edición dentro del CMS (`/cms/#hub`) + **tablero independiente de presentación** (`/estrategia/`, solo lectura) |
| Publicación | **Por configurar:** el MVP publica de forma asistida; en Ajustes cada canal queda en `manual`, `meta_api` o `postiz` con estado «no configurado» |
| Legal | Consulta legal aprobada. Mientras llega, el checklist COFEPRIS se mantiene obligatorio |
| Quién aprueba y produce | El equipo: roles dentro del Hub, independientes de los roles del CMS |
| Canales | Instagram, Facebook, TikTok, **Threads**, **YouTube Shorts**, Google Business Profile y Canal de WhatsApp |

## 1. Archivos (todos nuevos; no se modifican archivos del CMS existente)

| Archivo | Qué es |
|---|---|
| `estrategia-contenido/datos/parrilla-piloto.json` | **Semilla**: catálogos, estrategia y piezas del piloto (formato §2). Es la fuente única para el Hub y para el tablero |
| `backend/cms_hub.py` | Blueprint de Flask `hub` con `register_hub(app)`. Usa `app.extensions['cms_db']` solo para leer usuarios y `app.extensions['cms_media']` para MediaHub. Sus datos van en **`<CMS_ROOT>/hub.sqlite`** |
| `backend/hub_seed.py` | CLI: `python3 hub_seed.py --root <CMS_ROOT> --seed <json> [--reset]`. Es idempotente: actualiza por `clave` y no duplica |
| `tests/test_cms_hub.py` | Pruebas unittest con `create_app` del CMS + `register_hub(app)` en una carpeta temporal |
| `sitio/cms/hub.js`, `sitio/cms/hub.css` | Módulo del Hub. Se sirven en `/cms/hub.js` y `/cms/hub.css` desde el Blueprint, que tiene una regla estática más específica que `/cms/<name>` |
| `sitio/cms/aprobar.html` (+ el mismo `hub.css`) | Página pública para aprobar con un enlace firmado |
| `sitio/estrategia/index.html`, `estrategia.js`, `estrategia.css`, `data.json` | Tablero de presentación de solo lectura |
| `deploy/hub-integracion.patch` | Parche mínimo para el CMS (§6). **No se aplica** hasta que el CMS esté versionado en git |

## 2. Formato de la semilla (`parrilla-piloto.json`)

```jsonc
{
  "version": 1,
  "generado": "2026-10-08",
  "piloto": { "inicio": "2026-10-24", "fin": "2026-11-29", "zona": "America/Mexico_City", "nombre": "Piloto Halloween + Aniversario III" },
  "estrategia": {
    "objetivo": "…", "kpi_estrella": "Visitas atribuidas por semana",
    "kpis": [{ "clave": "posts_ig_semana", "nombre": "…", "meta": "≥3.5", "fuente": "…" }],
    "leyenda_sanitaria": "EVITE EL EXCESO",
    "linea_base": { "ig": { "reel": 32, "carrusel": 56, "imagen": 43 }, "tiktok": { "video": 25 }, "corte": "2026-10-06", "nota": "likes+comentarios; recalibrar con Insights" },
    "diagnostico": { "insights": ["…"], "debilidades": ["…"] }
  },
  "canales":   [{ "clave": "ig", "nombre": "Instagram", "handle": "@cisnenegro.mx", "color": "#…", "icono": "instagram", "metodo": "manual", "rol": "…", "cadencia": "…" }],
  "formatos":  [{ "clave": "ig-carrusel", "canal": "ig", "nombre": "Carrusel", "tipo": "carrusel", "proporcion": "4:5", "max_caracteres": 2200, "max_laminas": 20, "max_segundos": null, "interaccion_ideal": 56 }],
  "plantillas":[{ "clave": "volteo-etiqueta", "nombre": "Volteo de etiqueta", "que_es": "…", "virtud": "…", "que_se_necesita": "…", "tiempo": "Rápido", "origen": "PDF 035 (adaptada)" }],
  "pilares":   [{ "clave": "barril", "nombre": "El Barril", "color": "#…", "objetivo_pct": 30, "descripcion": "…" }],
  "topicos":   [{ "clave": "barril-semana", "pilar": "barril", "nombre": "Barril de la semana" }],
  "secciones": [{ "clave": "barril-de-la-semana", "topico": "barril-semana", "nombre": "Barril de la semana", "descripcion": "…",
                  "periodicidad": "Semanal (martes 12–14 h)", "formato": "ig-carrusel", "plantilla": "ficha-barril",
                  "tiempo_produccion_min": 60, "estado_prueba": "no_empezada", "estado_seccion": null, "en_piloto": true,
                  "temas": ["10 títulos con gancho…"] }],
  "aliados":   [{ "clave": "amordeveranostd", "nombre": "@amordeveranostd", "tipo": "Ilustrador", "nota": "Ilustró ¡Alarma! y Matador" }],
  "campanas":  [{ "clave": "halloween-2026", "nombre": "Halloween 2026", "inicio": "2026-10-24", "fin": "2026-10-31", "objetivo": "…" }],
  "atributos": [{ "clave": "gancho", "entidad": "pieza", "nombre": "Tipo de gancho", "tipo": "lista", "opciones": ["Pregunta","Dato","Humor","Revelación"], "filtrable": true, "columna": true }],
  "piezas": [{
    "clave": "2026-10-20-barril-r1", "titulo": "…", "seccion": "barril-de-la-semana", "campana": null,
    "fecha": "2026-10-20", "hora": "12:30", "estado": "borrador", "prueba": "R1",
    "objetivo": "comunidad|alcance|visita", "brief": "qué se graba/diseña y cómo cumplir COFEPRIS",
    "copy_base": "texto base en voz Cisne", "por_validar": ["Confirmar barril en tap list"],
    "atributos": { "gancho": "Dato" }, "aliado": null,
    "variantes": [{ "canal": "ig", "formato": "ig-carrusel", "copy": "…", "hashtags": ["#pachuca"], "fecha": "2026-10-20", "hora": "12:30" }]
  }]
}
```

Reglas de la semilla:
- **Solo datos verificados** (base de conocimientos, `menu.json`, captions de IG). Lo que no está verificado va en `por_validar` de la pieza.
- **Voz Cisne:** pícara, local, de cuates; sin «Descubre» ni «Sumérgete».
- **COFEPRIS:** sin imperativos de consumo, sin personas bebiendo y sin asociar la cerveza con fiesta, éxito, música, arte o deporte. La leyenda va en cada pieza de cerveza.
- **Horarios:** martes de 12 a 14 h y jueves de 15 a 18 h para las piezas principales; sábado solo stories.

## 3. Base de datos `hub.sqlite`

Todas las tablas tienen `id integer primary key`, `clave text unique` (cuando aplica), `creado_at`, `actualizado_at` y `archivado integer default 0`. El borrado es suave (se archiva); el borrado definitivo es solo para el dueño y solo si nada depende del registro.

- **Catálogos:**
  - `canales`: clave, nombre, handle, color, icono, metodo (`manual`|`meta_api`|`postiz`), rol, cadencia, config (JSON sin secretos), orden.
  - `formatos`: clave, canal_id, nombre, tipo, proporcion, max_caracteres, max_laminas, max_segundos, interaccion_ideal.
  - `plantillas`: clave, nombre, que_es, virtud, que_se_necesita, tiempo, origen, enlace.
  - `pilares`: clave, nombre, color, objetivo_pct, descripcion, orden.
  - `topicos`: clave, pilar_id, nombre, orden.
  - `secciones`: clave, topico_id, nombre, descripcion, periodicidad, formato_id, plantilla_id, tiempo_produccion_min, interaccion_ideal (si es null se hereda del formato), estado_prueba (`no_empezada`|`empezada`|`vigente`|`no_funciono`), estado_seccion (`normal`|`buena`|`saturada`|`dejo_de_funcionar`|null), en_piloto.
  - `temas`: seccion_id, titulo, explicacion, usado (pieza_id o null).
  - `aliados`: clave, nombre, tipo, contacto, nota.
  - `campanas`: clave, nombre, inicio, fin, objetivo.
- **Atributos personalizados:**
  - `atributos`: clave, entidad (`pieza`|`seccion`|`aliado`|`campana`), nombre, tipo (`texto`|`numero`|`lista`|`fecha`|`booleano`|`usuario`|`cerveza`), opciones (JSON), requerido, filtrable, columna, orden.
  - `valores`: atributo_id, entidad, entidad_id, valor (JSON), con unique(atributo_id, entidad, entidad_id).
- **Operación:**
  - `piezas`: clave, titulo, seccion_id, campana_id, aliado_id, responsable_id (usuario del CMS), fecha, hora, estado (`idea`|`borrador`|`revision`|`observada`|`aprobada`|`programada`|`publicada`|`error`), prueba (`R1`|`R2`|`R3`|null), objetivo, brief, copy_base, por_validar (JSON), cumplimiento (JSON del checklist), version.
  - `variantes`: pieza_id, canal_id, formato_id, copy, hashtags (JSON), media_ids (JSON de ids de MediaHub), fecha, hora, estado_pub (`pendiente`|`programada`|`publicada`|`error`|`omitida`), url_publicada, id_externo, error, publicado_at.
  - `versiones`: pieza_id, version, datos (JSON con la pieza y sus variantes), autor, creado_at.
  - `comentarios`: pieza_id, autor, texto, interno (1 = oculto en la vista de aprobación), creado_at.
  - `aprobaciones`: pieza_id, token_hash, expira, decision (`aprobada`|`cambios`|null), motivo, quien, decidido_at.
  - `metricas`: variante_id, medido_at, horas_desde_pub, likes, comentarios, compartidos, guardados, envios, alcance, vistas, fuente (`manual`|`api`).
  - `roles_hub`: user_id (de cms.sqlite), rol (`aprobador`|`productor`|`community`). El dueño del CMS siempre puede todo.
  - `actividad`: actor, accion, entidad, entidad_id, creado_at.

## 4. API (todo bajo `/cms/api/hub/`)

Hereda la sesión y el CSRF del CMS. Las respuestas son JSON y los errores van como `{error}`.

| Método y ruta | Uso |
|---|---|
| `GET /cms/api/hub/resumen?desde&hasta` | Inicio: conteos por estado, pendientes de aprobación, próximas piezas, errores, KPIs (posts por semana por canal contra la meta, equilibrio de pilares contra el objetivo) |
| `GET /cms/api/hub/catalogos` | Todos los catálogos, los atributos y los usuarios (id y nombre) en una sola llamada |
| `GET\|POST /cms/api/hub/<catalogo>`, `PUT\|DELETE /cms/api/hub/<catalogo>/<id>` | CRUD genérico de canales, formatos, plantillas, pilares, tópicos, secciones, temas, aliados, campañas y atributos. Validación por catálogo; `DELETE` archiva salvo que se mande `?definitivo=1` (solo dueño y sin dependencias) |
| `GET /cms/api/hub/piezas?desde&hasta&canal&pilar&seccion&estado&q&attr.<clave>=<valor>` | Lista con variantes, más los nombres resueltos y los valores de los atributos |
| `POST /cms/api/hub/piezas`, `GET\|PUT\|DELETE /cms/api/hub/piezas/<id>` | CRUD con `version` para bloqueo optimista (409 si hay conflicto); cada `PUT` guarda una versión |
| `POST /cms/api/hub/piezas/<id>/mover` | `{fecha, hora}` (arrastrar en el calendario); mueve también las variantes que comparten la fecha |
| `POST /cms/api/hub/piezas/<id>/duplicar` | Copia la pieza como borrador |
| `POST /cms/api/hub/piezas/<id>/estado` | `{estado, motivo?}`: transiciones válidas (§5) y permisos |
| `POST /cms/api/hub/piezas/<id>/enlace-aprobacion` | Genera un token de 32 bytes (se guarda su hash) con vigencia de 7 días → `{url}` |
| `GET\|POST /cms/api/hub/piezas/<id>/comentarios` | Comentarios |
| `POST /cms/api/hub/variantes/<id>/publicada` | `{url, publicado_at?}`: publicación asistida |
| `POST /cms/api/hub/variantes/<id>/metricas` | Captura de métricas; recalcula la prueba de la sección |
| `GET /cms/api/hub/laboratorio` | Secciones con sus R1–R3 (interacción contra la ideal) y su estado calculado |
| `GET /cms/api/hub/piezas.csv?…` | Exportación de la parrilla |
| `GET\|PUT /cms/api/hub/ajustes` | Método de publicación por canal, leyenda, roles del Hub (solo dueño); nunca devuelve secretos |
| `POST /cms/api/hub/presentacion/publicar` | El dueño publica la instantánea del tablero en `<CMS_ROOT>/hub-presentacion.json` |
| **Público:** `GET /cms/hub/presentacion.json` | Instantánea publicada (o 404). Sin datos internos: excluye comentarios internos, tokens, responsables y correos |
| **Público:** `GET /cms/aprobar/<token>` (HTML) y `GET\|POST /cms/hub/aprobacion/<token>` (JSON) | Ver la pieza y decidir `{decision, motivo, nombre}`. Límite de intentos por IP; el token caduca o se usa una sola vez por decisión |
| `GET /cms/hub.js`, `/cms/hub.css` | Archivos estáticos del módulo |

## 5. Reglas de negocio

- **Transiciones:** idea → borrador → revision → (aprobada | observada); observada → borrador; aprobada → programada → publicada | error; error → programada. Cualquier estado puede pasar a `archivada` (borrado suave).
- **Permisos:**
  - **Aprobar u observar:** el dueño del CMS o alguien con el rol `aprobador`.
  - **Programar:** solo piezas aprobadas.
  - **Publicada:** se marca cuando todas sus variantes están publicadas u omitidas.
- **Checklist de cumplimiento** (JSON en la pieza):
  - Obligatorios: `leyenda`, `sin_consumo_en_cuadro`, `personas_25_mas`, `sin_imperativo`, `sin_asociacion_prohibida`, `datos_verificados`.
  - **No se puede enviar a revisión** si falta alguno. Si la pieza no trata de cerveza, se marca `no_aplica` en todo salvo `datos_verificados`.
- **Validadores del composer:** caracteres por canal (IG 2,200; Threads 500; TikTok 2,200; YouTube: título 100 y descripción 5,000; GBP 1,500; FB 63,206), láminas máximas, proporción y duración del formato. Son avisos que el usuario ve; el servidor solo rechaza el exceso de caracteres.
- **Laboratorio (método):**
  - **Interacción** = likes + comentarios + compartidos + guardados (+ envíos si existen), medida lo más cerca posible de las 24 h.
  - **Prueba (R1–R3):** cada pieza `cumplió` si llega al 100% de la ideal, `superó` si pasa de 120% y `no cumplió` si queda por debajo.
  - **Estado de prueba:** `vigente` si al menos 2 de 3 cumplen; `no_funciono` si al menos 2 de 3 no cumplen.
  - **Estado de la sección** (ya vigente, con sus últimos 5 posts): `buena` si la mayoría supera; `normal` si la mayoría cumple; `saturada` si la media queda entre 60 y 100% de la ideal; `dejo_de_funcionar` si queda por debajo del 60%.
  - **Aviso automático** si R1 o R2 no cumplieron y la siguiente prueba tiene la misma hora, plantilla y formato.

## 6. Integración con el CMS (`deploy/hub-integracion.patch`, se aplica después)

1. `backend/cms_server.py`, al final de `create_app` antes de `return app`: `from cms_hub import register_hub; register_hub(app)`.
2. `sitio/cms/index.html`: agregar `<link rel="stylesheet" href="/cms/hub.css">` y `<script src="/cms/hub.js" defer></script>` **antes** de `cms.js`.
3. `sitio/cms/cms.js`:
   - En `modules`, agregar `{id:'hub',label:'Contenido',icon:'calendar'}` después de `eventos`.
   - En `views`, agregar `hub:()=>window.CisneHub.render(ctx)`, donde `ctx` expone `api`, `dialog`, `toast`, `pageHeading`, `empty`, el usuario y el CSRF que ya existen en `cms.js`.
   - Si `cms.js` no expone esos helpers, `hub.js` trae los suyos (con el mismo look) y recibe solo `{api, user, csrf}`.
4. `deploy/publicar-cms.sh`: copiar `cms_hub.py`, `hub_seed.py`, `hub.js`, `hub.css` y `aprobar.html`. `backup-cms.py`: incluir `hub.sqlite`.

Mientras el parche no esté aplicado, `hub.js` también funciona solo, en `/cms/hub-dev.html` (únicamente en desarrollo, con `CMS_DEV=1`).

## 7. UX del módulo «Contenido»

Pestañas internas:
- **Planner:** calendario de mes o semana con arrastrar y soltar, más un panel lateral del composer.
- **Parrilla:** tabla editable con columnas configurables y CSV.
- **Matriz:** pilar × tópico × sección; pilar × canal × semana contra la cuota (mapa de calor); equilibrio.
- **Kanban.**
- **Laboratorio.**
- **Banco de ideas.**
- **Catálogos:** subnavegación con canales, formatos, plantillas, pilares, tópicos, secciones, aliados, campañas, atributos y roles.
- **Ajustes.**

El composer tiene:
- Texto base y una pestaña por canal con su vista previa (feed 4:5, reel o story 9:16, TikTok, Threads, YouTube Shorts, GBP, WhatsApp).
- Selector de MediaHub.
- Checklist de cumplimiento.
- Atributos personalizados.
- Comentarios.
- Historial de versiones.
- Botones Enviar a revisión, Generar enlace de aprobación y Marcar publicada.

Estilo «Neón y tinta» con los tokens de `cms.css`. Accesibilidad: foco visible, objetivos de 44 px, AA, estado con ícono y texto, y alternativa de teclado al arrastrar (menú «Mover a…»).

## 8. Tablero de presentación `/estrategia/`

Es de solo lectura, con `noindex`. Carga `/cms/hub/presentacion.json` y, si no existe, usa `/estrategia/data.json` (la semilla sin datos internos). Secciones:
1. **Portada:** objetivo, piloto y KPI estrella.
2. **Diagnóstico:** línea base por formato, mejores días y franjas, categorías (con `dataviz`).
3. **El método:** las 6 etapas y el workflow W0–W8.
4. **Pilares, tópicos y secciones:** cada pilar con sus tópicos y secciones, y un indicador de qué secciones se prueban en el piloto.
5. **Matriz:** pilar × canal × semana.
6. **Parrilla:** calendario de mes o semana más lista, con filtros por canal, pilar y sección, y una ficha de pieza con la vista previa por red.
7. **Canales:** rol y cadencia de cada uno.
8. **KPIs y laboratorio:** metas y, cuando existan, los resultados.
9. **Cumplimiento.**

Debe verse bien en celular y en proyector, con modo «presentación» (pantalla completa por secciones con teclas ←/→).
