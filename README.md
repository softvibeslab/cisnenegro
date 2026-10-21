# Cervecería Cisne Negro — Pachuca, Hgo.

Repositorio independiente de [Cisne Negro](https://cisnenegro.mx/), exportado el 21 de octubre de 2026. La aplicación vigente está en **[hosting-independiente/](hosting-independiente/README.md)**: sitio, menú, CMS, MediaHub, administración y equipo. Los directorios raíz `sitio/`, `backend/` y `deploy/` conservan la primera versión como antecedente; usa `hosting-independiente/` para continuar el desarrollo actual.

```sh
git clone https://github.com/softvibeslab/cisnenegro.git
cd cisnenegro/hosting-independiente
./iniciar-local.sh
```

- [Alcance de la entrega y exclusiones](ENTREGA-GITHUB.md).
- [Skills y ecosistema de desarrollo](ecosistema/README.md), con fuentes y guías de instalación.
- [Paquete descargable del ecosistema](paquetes/cisnenegro-skills-ecosistema-20261021.zip).
- [Manual público](manual-usuario/README.md), HTML y PDF sin credenciales.
- [Últimos ajustes publicados](hosting-independiente/docs/actualizacion-menu-2026-10-17.md): imagen de Colchita, Wi-Fi/Pasaporte ocultos y pedido sin QR.

La semilla del menú de la aplicación vigente refleja el catálogo público de la revisión 8. Las imágenes de MediaHub que utiliza se incluyen como archivos estáticos para una instalación nueva. No se copian cuentas, contraseñas ni bases operativas; el arranque local crea sus propios accesos. El resto de esta página conserva la bitácora histórica del proyecto.

Proyecto de marca y presencia digital: investigación, análisis, landing, menú digital con maridaje, fidelización y NPS.

## Instalación v2 publicada — 2026-10-10

**https://cisne.softvibes.art/** sirve la copia v2 integrada al CMS, con menú/Pasaporte, MediaHub, Administración y Equipo. Aplicación, datos y respaldo separados en el VPS `31.220.63.211`, según autorización del usuario. Ver [despliegue, accesos y cambio al dominio definitivo](hosting-independiente/DESPLIEGUE.md). Usar esta nueva instancia para los próximos cambios; no sincroniza sus datos con la instalación anterior. El dominio final espera DNS y tiene activación HTTPS automatizada.

**17 de octubre:** dominio principal **https://cisnenegro.mx/** publicado con HTTPS y redirección de `www` al dominio sin prefijo. Se guardaron los dos registros A en Squarespace hacia `31.220.63.211`, TTL 300; las cuatro autoridades confirman el cambio y el correo permanece intacto. Acceso al CMS, administración y rutas públicas comprobados. Algunas cachés aún muestran el sitio anterior durante la propagación. El temporal sigue sirviendo esta misma instalación.

## Estado (2026-10-08) — publicado en https://cisnenegro.softvibes.art

| URL | Qué es |
|---|---|
| `/` | Landing nueva (barril de hoy, historia, maridajes, Pasaporte, galería, eventos, visítanos) |
| `/menu/` | Menú QR con maridaje, filtro por perfil, Vuelo del Cisne, Pasaporte Cisne y NPS |
| `/admin/` | Panel del equipo: código del día, canje, NPS y socios (credenciales en `PRIVADO/credenciales-panel.txt`, fuera de git) |
| `/cms/` | CMS con editor visual, catálogo, MediaHub, eventos, galería, datos del negocio, usuarios y publicaciones; acceso con las credenciales del panel |
| `/analisis/` | Informe de presencia digital (score global 37/100) |
| `/proyecto/` | Hub de artefactos: base de conocimientos, propuesta, plan, backlog, inventario y sistema visual |
| `/privacidad/` | Aviso de privacidad (preliminar, falta que lo apruebe el cliente) |
| `/propuesta/` | Propuesta económica con branding, PDF descargable y pestaña de Consultoría Beervibes (publicada con autorización el 2026-10-07) |
| `/propuesta/beervibes/` | Consultoría Beervibes de 90 días por USD 3,500, conectada a la propuesta mediante pestañas (publicada con autorización el 2026-10-07) |
| `/assets/qr/menu-qr.png` · `.svg` | QR del menú para portavasos y mesas |

- ✅ Fases 0–5 completas. Vista previa con `noindex`; el dominio del cliente sigue siendo cisnenegro.mx.
- 📋 Pendiente del cliente: ver [BACKLOG.md](BACKLOG.md) y las preguntas abiertas (§9 de la base de conocimientos), además de validar los maridajes, las notas de cata, la historia de cada nombre y el aviso de privacidad.
- ⚠️ Urgente para el cliente: corregir o retirar la landing de Abacus (teléfono falso y horario incorrecto) y quitar "temporalmente cerrado" en Tripadvisor.

## Operación

- **Publicar cambios:** `deploy/publicar.sh` (rsync de `sitio/` + backend y reinicio del servicio). El hub se regenera con `deploy/build_proyecto.py` (requiere el paquete `markdown`).
- **Editar la página y el menú:** desde `/cms/`. El borrador y las publicaciones viven en `/var/lib/cisnenegro-cms/cms.sqlite`; `/data/menu.json` es una representación de la revisión publicada. El JSON local se conserva como semilla de importación, no como fuente editorial activa. Ver [guía del CMS](07-guia-cms.md).
- **Actualizar el código del CMS:** `deploy/publicar-cms.sh`. No borra rutas remotas ni reemplaza borradores, medios o revisiones. Servicio `cisnenegro-cms`, Gunicorn en `127.0.0.1:8795`; `/v2` conserva su servicio separado.
- **MediaHub:** 477 medios únicos importados y 3 duplicados exactos detectados; 480 rutas de origen conservadas. Imágenes optimizadas, originales privados y videos procesados en segundo plano. El material importado queda pendiente de revisión editorial.
- **Respaldos CMS:** temporizador `cisnenegro-cms-backup.timer`, diario a las 03:40 de Ciudad de México, retención de 14 snapshots. Copias privadas en `/var/backups/cisnenegro-cms`; respaldan contenido, cuentas, revisiones y biblioteca. Cada ejecución verifica una restauración temporal sin tocar el Pasaporte. Primera ejecución y restauración verificadas el 2026-10-08.
- **Backend del club:** `backend/club_server.py` (Python + SQLite), servicio `cisnenegro-club` en el VPS rovicrm, base en `/var/lib/cisnenegro-club/club.db`, con respaldo diario a las 03:30 (CDMX) en `/var/backups/cisnenegro-club/`. Pruebas: `python3 backend/test_club.py` (26 verificaciones). Desarrollo local: `python3 backend/dev_server.py 8080`.
- **Auditoría responsiva:** `tests/responsive/audit.cjs` revisa 20 perfiles en 3 motores (Android, iPhone, iPad y tabletas Android, Mac, Windows, 2560 px) sobre 13 vistas: desbordes, objetivos táctiles, zoom de iOS, recortes y errores JS. Uso: `python3 backend/dev_server.py 8082 &` y luego `NODE_PATH=<carpeta con playwright>/node_modules node tests/responsive/audit.cjs`. Las capturas y `reporte.json` quedan en `sitio/qa/responsive/` (fuera de git).
- **Infra:** DNS A `cisnenegro.softvibes.art → 31.220.63.211` (Hostinger), SSL de Let's Encrypt y sesión individual para CMS y panel. `/api/admin/` verifica propietario y token interno; `/api/` conserva la autenticación independiente de socios. El include `deploy/cisnenegro-cms.conf` complementa el vhost vigente conservando TLS y `/v2`.

## Documentos

| Archivo | Contenido |
|---|---|
| [01-base-conocimientos.md](01-base-conocimientos.md) | Datos verificados con fuente, menú, huella digital y preguntas abiertas |
| [02-propuesta-marca-digital.md](02-propuesta-marca-digital.md) | Hallazgos, plataforma de marca, maridaje, lealtad, NPS, redes y KPIs |
| [03-plan-ejecucion.md](03-plan-ejecucion.md) | Fases: scraping → análisis → landing → menú → lealtad/NPS → lanzamiento |
| [05-consultoria-beervibes-90-dias.md](05-consultoria-beervibes-90-dias.md) | Plan de 90 días por USD 3,500 adaptado a contenido, embudo y Content Hub; revisión local del 2026-10-08 pendiente de publicación |
| [06-plan-cms-mediahub.md](06-plan-cms-mediahub.md) | Plan original del CMS y MediaHub; base de la implementación publicada el 2026-10-08 |
| [07-guia-cms.md](07-guia-cms.md) | Uso, límites, permisos, mantenimiento y recuperación del CMS publicado |
| [plan-hosting-independiente-v2.md](plan-hosting-independiente-v2.md) | Plan vigente para migrar a un hosting independiente, llevar v2 a cisnenegro.mx y conectar CMS, menú, admin y equipo; pendiente de ejecución |
| [hosting-independiente/README.md](hosting-independiente/README.md) | v2 integrada al CMS y publicada en cisne.softvibes.art; copia local, pruebas, paquete y registro del despliegue |
| [consultoria-beervibes/index.html](consultoria-beervibes/index.html) | Propuesta visual «Del primer vistazo al próximo brindis»: fotografías, embudo, flujo de trabajo y cronograma; plan completo en desplegables. Pendiente de publicación |
| [BACKLOG.md](BACKLOG.md) | Pendientes que dependen del cliente (B1–B4) |
| [sitio/DESIGN.md](sitio/DESIGN.md) | Sistema visual «Neón y tinta» |
| [scraping/README.md](scraping/README.md) | Inventario descargado, huecos, costo, cómo reproducir y hallazgos preliminares |
| [propuesta-economica/propuesta-economica.md](propuesta-economica/propuesta-economica.md) | Propuesta comercial: implementación, CMS, administración mensual, alcance y condiciones |
| [informe-roi/informe.md](informe-roi/informe.md) | Medición y umbral de retorno de CN-2026-01. La presentación local está en informe-roi/presentacion.html y no se publica |

## Propuestas y variantes

- **Tablero de contenido [`/estrategia/`](https://cisnenegro.softvibes.art/estrategia/)** (publicado el 2026-10-10 con autorización; `noindex`): dashboard de solo lectura del piloto con estructura de Meta Business Suite y estilo «Neón y tinta». Vistas: Inicio, Planner (mes, semana y lista), Parrilla (tabla y CSV), Matriz, Temporada, Laboratorio R1–R3, Estrategia, Canales y Cumplimiento. Cada pieza tiene una ficha con vista previa por red y un enlace directo. Incluye modo presentación con ←/→. Lee `/cms/hub/presentacion.json` cuando el Hub lo publique y, mientras tanto, `sitio/estrategia/data.json`.
  - Regenerar los datos tras cambiar la semilla: `<python con backend/requirements-cms.txt> deploy/build_estrategia.py`. Usa la misma función que publica el Hub, así que no lleva briefs, notas por validar ni contactos.
  - Verla: `python3 -m http.server 8099 --bind 127.0.0.1 --directory sitio` y abrir `http://127.0.0.1:8099/estrategia/`.
  - Prueba de navegador: `NODE_PATH=<carpeta con playwright>/node_modules node tests/estrategia.cjs` (58 verificaciones: las 9 vistas, la ficha, los filtros, el CSV, la presentación y el celular). Las capturas quedan en `sitio/qa/estrategia/`.
  - Publicar solo el tablero: `rsync -az -e "ssh -i ~/.ssh/rovi_vps_deploy" --exclude .DS_Store sitio/estrategia/ root@31.220.63.211:/var/www/cisnenegro/estrategia/` y `chmod 755` en la carpeta. No uses `deploy/publicar.sh` mientras haya cambios sin commit en `sitio/` o en `backend/club_server.py`, porque los publicaría y reiniciaría el club.
  - Pendiente: la parte de edición del Hub en el CMS (`hub.js`, `aprobar.html`) sigue sin construir, y `register_hub` no está conectado.
- **Hero con video:** `sitio/con-video/index.html` conserva el diseño de la portada y utiliza el montaje de cerveza y experiencia de [video-hero/](video-hero/README.md). Variante independiente; no sustituye `sitio/index.html` ni se ha publicado.
- Para verla: `python3 -m http.server 8098 --bind 127.0.0.1 --directory sitio` y abrir `http://127.0.0.1:8098/con-video/`.
- Video silencioso en bucle de 28 segundos, versión 1080p de 9.6 MB y versión móvil 720p de 3.3 MB. Incluye pausa, fotografía de respaldo y carga manual si se prefiere movimiento reducido o ahorro de datos.
- Verificación del controlador sin dependencias: `node tests/hero-video.cjs` (15 casos: preferencias, pausa, visibilidad, carga, errores y reproducción pendiente). Revisión visual realizada en Chrome de escritorio y vista móvil de 375 × 667.
- **Propuesta económica:** [PDF para los dueños](propuesta-economica/propuesta-economica-cisne-negro.pdf), con fuente editable en Markdown y descarga incluida en la propuesta HTML.
- **Propuesta HTML con branding:** [versión pública](https://cisnenegro.softvibes.art/propuesta/) · [archivo autónomo](propuesta-economica/index.html). Imágenes, tipografías y PDF incrustados; funciona sin conexión y tiene formato de impresión. Incluye la sección 05, Retorno medible, con una línea de tiempo de la transformación (hoy, cuatro semanas, apertura y lectura a 90 días). Publicada con autorización el 2026-10-07; la sección de retorno se publicó el 2026-10-07. HTTP redirige a HTTPS.
- Para actualizar la propuesta: `python3 propuesta-economica/generar_html.py` (requiere Pandoc). Genera la versión local y `sitio/propuesta/index.html`, con los enlaces de las pestañas adaptados a cada ubicación. No copiar manualmente la versión local sobre la pública, porque sus enlaces relativos son diferentes.
- **Consultoría Beervibes en HTML:** [versión pública](https://cisnenegro.softvibes.art/propuesta/beervibes/) · [archivo autónomo](consultoria-beervibes/index.html), con imágenes y fuentes incrustadas, versión móvil y botón para imprimir o guardar como PDF. Conserva el contenido de `05-consultoria-beervibes-90-dias.md`, incluida la inversión de USD 3,500 antes de impuestos. Publicada con autorización el 2026-10-07; las pestañas «Plataforma digital» y «Consultoría Beervibes» conectan ambas propuestas.
- **Adaptación del 2026-10-08, pendiente de publicación:** el Markdown y ambos HTML locales integran el embudo descubrir → considerar → visitar → regresar → recomendar, cuatro pilares y seis secciones editoriales. El piloto vigente de temporada (24 de octubre–29 de noviembre; reprogramado el 2026-10-10 para arrancar una semana antes de Halloween) procede de la especificación del Content Hub y su parrilla semilla. Se conservan 36 briefs, 12 desarrollos de texto, 90 días y USD 3,500; las 18 pruebas forman parte de esos briefs. El banco de 42 piezas y 131 variantes es material para priorizar, no producción incluida. Se distingue el CMS disponible del Hub en construcción y la intención digital de las visitas registradas. Fuentes: `estrategia-contenido/08-plan-estrategia-contenido-y-content-hub.md`, `estrategia-contenido/09-spec-content-hub.md` y `estrategia-contenido/datos/parrilla-piloto.json`. Verificación: contenido completo, anclas, estructura de entregables y revisión visual en escritorio y móvil de 375 px.
- **Versión visual del 2026-10-08, pendiente de publicación:** relato principal de 750 palabras, 15 imágenes del archivo de Cisne Negro, recorrido de cinco pasos, seis historias editoriales, flujo de responsables y línea de tiempo de cuatro etapas. Los 217 fragmentos del plan se conservan en 11 desplegables; al imprimir se incluyen completos y después se restablece su estado. Revisada en escritorio y móvil de 375 px, con apertura de condiciones y vista previa de impresión. No cambia precio, duración ni alcance.
- Para regenerar el plan: `python3 consultoria-beervibes/generar_html.py` (requiere Pandoc). Editar el relato en `consultoria-beervibes/plantilla.html`, su diseño en `consultoria-beervibes/estilo.css` y el detalle en `05-consultoria-beervibes-90-dias.md`. El HTML local es autónomo; `sitio/propuesta/beervibes/index.html` reutiliza las imágenes existentes en `/assets/img/` para evitar incrustarlas repetidamente. Ambos incluyen las fuentes de la propuesta económica. El generador verifica contenido completo, anclas, imágenes con alternativa y estructura de cinco pasos, seis historias y cuatro etapas. Verificación HTTP local: HTML y nueve recursos de imagen disponibles.
- La publicación de las pestañas transfirió únicamente los dos HTML de `sitio/propuesta/`, sin ejecutar el despliegue completo. Se respaldó la propuesta anterior fuera del directorio público. Verificación: navegación de ida y vuelta en móvil y escritorio, 90 y 151 fragmentos aprobados conservados, PDF original intacto, HTTP 200 y coincidencia exacta de los archivos publicados; rutas sin barra final redirigen correctamente.

## Bases reutilizadas

- Landing: `../malandra-cerveceria` (mismo nicho; solo la base técnica).
- Menú, lealtad y NPS: backend propio del club (MenuVibes/Supabase está apagado desde ago 2026; decisión del usuario el 2026-10-06).

## Reglas

No se inventan datos. No se publica, despliega ni contacta al cliente sin autorización explícita.
