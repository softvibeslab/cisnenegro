# Informe y manual de Cisne Negro

**Edición pública para GitHub, 21 de octubre de 2026.** HTML y PDF regenerados con las cinco capturas públicas o de acceso vacío. Las capturas de sesiones autenticadas y el anexo de accesos quedan fuera del repositorio. Se conservan los 20 capítulos y 50 enlaces. La descripción original de 34 páginas/20 capturas de abajo corresponde a la entrega privada inicial; esta edición pública tiene menos capturas y páginas. El PDF público está en `output/pdf/informe-y-manual-cisne-negro.pdf`.

Edición: 17 de octubre de 2026. Documentación de la instalación vigente en `https://cisnenegro.mx/`.

## Entregables

- `output/pdf/informe-y-manual-cisne-negro.pdf`: informe y guía de 34 páginas, con enlaces clicables e índice.
- `index.html`: versión autónoma con búsqueda, directorio filtrable, capturas ampliables e impresión. Abrir directamente en un navegador; no requiere servidor ni conexión para leer las capturas.
- `../PRIVADO/manual-usuario/accesos.html`: anexo privado, entregado por separado. Contiene usuarios y credenciales disponibles; identifica las no documentadas. No incluir en una publicación del sitio.

## Alcance

50 enlaces del sitio y sus módulos, dos proveedores, cinco perfiles, 20 capítulos y 20 capturas distintas (algunas se reutilizan). Incluye página, menú, Pasaporte, CMS, MediaHub, publicaciones, usuarios, Administración, Equipo, cobros, cortes y ayuda.

Las capturas corresponden a `cisne.softvibes.art`, alias temporal de la misma instalación y datos; la caché local todavía mostraba el sitio anterior en el dominio final. Algunas pantallas contienen datos importados de demostración. El dominio anterior `cisnenegro.softvibes.art` mantiene otra instalación.

## Fuentes y mantenimiento

- `contenido.json`: texto, directorio, roles y estado técnico.
- `fuentes.json`: evidencia de las consultas HTTPS, código, DNS, servicios y respaldos.
- `capturas/`: capturas reales, sin contraseñas, PIN ni códigos activos del día.
- `generar_html.py`: genera el HTML con imágenes incorporadas.
- `generar_pdf.py`: genera el PDF con ReportLab y las fuentes Arial/DIN de macOS.

Para actualizar, revisar primero el contenido y tomar nuevas capturas de la interfaz vigente. El generador PDF requiere Python con `reportlab` y `Pillow`. La revisión estructural utiliza `pypdf`; el renderizado visual utiliza `pdftoppm`. No son dependencias de la aplicación de producción.

## Verificación de esta entrega

- Las 34 páginas del PDF fueron renderizadas e inspeccionadas visualmente.
- Los 50 enlaces del directorio están presentes en ambas versiones.
- Se comprobó en Chrome la apertura local del HTML, búsqueda de MediaHub, navegación al capítulo, ampliación y cierre con Escape.
- Se compararon las credenciales conocidas contra el texto del PDF, HTML y JSON públicos: sin coincidencias.
- El anexo está en `PRIVADO`, excluido de Git, con permisos de archivo `0600`.
- Las sesiones empleadas para las capturas se cerraron. No se publicaron contenidos ni se ejecutaron altas, cobros, canjes o cortes para ilustrar el manual.

Los documentos se entregan localmente; no fueron publicados en el sitio.
