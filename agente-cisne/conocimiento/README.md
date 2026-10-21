# Conocimiento del agente

Paquete preparado el 21 de octubre de 2026 a partir del repositorio. Es contexto y procedimiento, no una conexión activa al negocio. La integración debe cargar [las instrucciones](../instrucciones.md) y seleccionar estas fichas según la tarea:

| Ficha | Consultar para |
|---|---|
| [Marca y diseño](marca-y-diseno.md) | Identidad, tono, estrategia, sistema visual y desarrollo |
| [Operación y ejemplos](operacion-y-ejemplos.md) | CRUD editorial, permisos, borradores, publicación y límites |
| [Etiqueta a imagen](etiqueta-a-imagen.md) | Alta de una cerveza y generación de la ilustración del menú |

## Jerarquía de fuentes

- **Contenido visible:** `published_document` y `published_version` del CMS conectado. La respuesta pública `/data/menu.json` permite comprobar el catálogo publicado, pero omite productos ocultos y no reemplaza el borrador completo.
- **Trabajo pendiente:** `document` y `version` del CMS. Leer antes de cualquier cambio; puede contener trabajo de otras personas.
- **Producto:** datos confirmados por el responsable y etiqueta original identificada. Registrar discrepancias frente al CMS antes de corregirlas.
- **Aplicación:** código de `hosting-independiente/` y sus pruebas. Las carpetas raíz `sitio/`, `backend/` y `deploy/` son antecedentes de la primera versión.
- **Historia y estrategia:** documentos fechados. Una propuesta no demuestra que una función esté activa ni que una campaña haya ocurrido.

La exportación del repositorio documenta la revisión 8 del CMS al 21 de octubre de 2026. **No debe asumirse que siga siendo la revisión actual.** Esa instantánea tiene Vuelo, Wi-Fi, Pasaporte y QR de compartir pedido ocultos según su alcance documentado; no reactivarlos como parte incidental de otra edición.

## Fuentes locales

| Fuente | Uso y límite |
|---|---|
| [AGENTS](https://github.com/softvibeslab/cisnenegro/blob/main/AGENTS.md) y [entrega](https://github.com/softvibeslab/cisnenegro/blob/main/ENTREGA-GITHUB.md) | Repositorio vigente, separación de datos privados y antecedentes |
| [Aplicación vigente](../../hosting-independiente/README.md) | Stack, arranque, rutas, operación y validación |
| [Código CMS](../../hosting-independiente/backend/cms_server.py) y [validación de contenido](../../hosting-independiente/backend/cms_content.py) | Contrato implementado de sesión, permisos, versiones, contenido y publicación |
| [MediaHub](../../hosting-independiente/backend/cms_media.py) | Ingesta, derivados, metadatos y estados de medios |
| [Base de conocimientos](../../01-base-conocimientos.md) | Investigación del 5 de octubre; sus precios, horarios y catálogo requieren contraste actual |
| [Cambios publicados](../../hosting-independiente/docs/actualizacion-menu-2026-10-17.md) y [exportación](../../hosting-independiente/docs/exportacion/README.md) | Estado documentado del menú y procedencia de la semilla, no estado en tiempo real |
| [Sistema visual](../../sitio/DESIGN.md) y [CSS vigente](../../hosting-independiente/sitio/assets/css/landing.css) | Identidad y tokens. Las instrucciones antiguas de dominio/noindex se subordinan a la aplicación vigente |
| [Colchita](../../hosting-independiente/docs/colchita/README.md) | Referencias, prompt, carácter editorial y revisión de una imagen publicada |
| [Estrategia](../../estrategia-contenido/08-plan-estrategia-contenido-y-content-hub.md) y [consultoría](../../05-consultoria-beervibes-90-dias.md) | Pilares y embudo propuestos; no pruebas de capacidades o resultados actuales |
| [Ecosistema](../../ecosistema/README.md) | Skills, procedencia y requisitos de herramientas. No transfiere cuentas ni permisos |

No cargar carpetas privadas ni el historial de conversaciones como una base indiscriminada. Citar el documento y la fecha cuando una respuesta dependa de antecedentes. Ante una fuente ilegible o ausente, declarar el límite.
