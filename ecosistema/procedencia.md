# Procedencia y evidencia

Fecha de preparación: 2026-10-21. El alcance es Cisne Negro; no se incluyeron archivos de otros clientes ni toda la biblioteca de skills del equipo.

## Uso confirmado o documentado

| Elemento | Evidencia | Qué se entrega |
|---|---|---|
| `imagegen` integrada | [Registro de Colchita, referencias, prompt y publicación](../hosting-independiente/docs/colchita/README.md) | Skill instalada completa y sin modificaciones, incluyendo licencia Apache-2.0. El registro demuestra el uso de la herramienta; no establece que esta copia instalada sea idéntica a una versión histórica del día de la generación. |
| Revisión y creación de PDF | Contexto de trabajo de la carta adjunta; [generador de propuesta](../propuesta-economica/generar_pdf.py) y [manual](../manual-usuario/README.md) | Skill original portable `documentos-pdf`, escrita para este paquete. No se copia el plugin PDF de runtime. |
| Inventario antes de una landing | [Plan de ejecución, fase 3](../03-plan-ejecucion.md) | Skill original portable `sitios-inventario`. Se documentó el método; el archivo no demuestra la invocación exacta de `landing-inventory-first`. |
| Desarrollo y pruebas | [README de aplicación](../hosting-independiente/README.md), [validación](../hosting-independiente/VALIDACION.md), pruebas y código incluidos | Skill original `sitios-desarrollo-qa` y mapa de herramientas. |
| Apify, yt-dlp y curl | [Registro de scraping ejecutado](../scraping/README.md) y sus scripts | Guía de herramientas; no se copia una skill de Apify ni tokens de acceso. |
| Hostinger, SSH, Docker, Nginx y certificados | [Registro de despliegue](../hosting-independiente/DESPLIEGUE.md) y [guía operativa](../hosting-independiente/deploy/README.md) | Archivos operativos del propio proyecto y explicación del stack. No hay una skill Hostinger disponible en el inventario local inspeccionado. |
| Playwright | [Auditorías del proyecto](../README.md), archivos en `tests/` | Código de pruebas existente, no el navegador ni sesiones del desarrollador. La presencia de scripts no confirma que la skill `playwright-pro` se invocara. |

## Menciones que no prueban uso

El [plan de contenido](../estrategia-contenido/08-plan-estrategia-contenido-y-content-hub.md) propone `content-strategy`, `marketing-context`, `social-content`, `marketing-ideas`, `copywriting`, `content-humanizer`, `dataviz`, `weekly-review`, `schedule`, `statistical-analyst`, `ui-ux-pro-max`, `frontend-design`, `playwright-pro` y distintos agentes. Son un mapa de posibilidades del plan, no un registro de ejecución. No se empaquetan como si todas se hubieran utilizado.

El registro de scraping dice expresamente que `google-maps-scraper` fue sustituida por Apify porque Docker no estaba activo. No se presenta como una skill ejecutada. Envato fue una alternativa metodológica; no se incorpora ninguna plantilla comercial.

## Distribución de las skills

- **imagegen:** proveedor OpenAI, copia de la skill de sistema instalada al preparar el paquete. Sin número de versión declarado en `SKILL.md`; los hashes identifican exactamente los archivos exportados. Se conserva `LICENSE.txt` Apache-2.0 y todo el soporte de la carpeta. No se encontró un archivo `NOTICE` adicional dentro de ella.
- **sitios-inventario:** documento nuevo para este repositorio. Se inspira en el procedimiento de inventario documentado y sustituye rutas personales por el workspace que autorice el usuario. La skill local de referencia `landing-inventory-first` no incluía licencia de redistribución; por ello no se copió literalmente.
- **documentos-pdf:** documento nuevo que describe generación con ReportLab y revisión visual con Poppler. El plugin PDF local inspeccionado tenía versión de paquete `26.1017.22136`; no se encontró licencia de redistribución en la skill ni en sus niveles superiores inspeccionados. No se distribuye su `SKILL.md`, sus iconos ni sus herramientas vinculadas al runtime.
- **sitios-desarrollo-qa:** documento nuevo derivado de la arquitectura y las verificaciones documentadas en este proyecto. No se presenta como una skill histórica.

No se concede una licencia general nueva a materiales de terceros. Los servicios externos conservan sus condiciones, cuentas y costes. Los datos del negocio y los derechos de marca e imágenes no se transfieren mediante este paquete.
