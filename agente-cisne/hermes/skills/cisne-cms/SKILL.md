---
name: cisne-cms
description: Consulta y edición autorizada del CMS de Cisne Negro; altas de cerveza, MediaHub e imágenes desde etiquetas. Usar para contenido, menú y trabajo del negocio en su perfil privado.
---

# Cisne Negro · cliente editorial

Esta skill usa `scripts/cisne_cms.py`, Python 3.11+ sin dependencias externas. No es una API genérica: solo ofrece las operaciones editoriales descritas. El CMS debe tener desplegados los endpoints `/cms/api/agent/`; la existencia de esta skill no demuestra que ya estén disponibles.

## Preparación

El operador configura fuera del chat `CISNE_CMS_URL`, `CISNE_CMS_USER`, `CISNE_CMS_PASSWORD` y `HERMES_HOME`. Usa una cuenta editorial dedicada y un perfil privado. No pongas secretos en argumentos, ejemplos, archivos Git, memoria o mensajes. No leas ni imprimas `.env` para demostrar la configuración.

Localiza el script dentro de esta skill instalada; los ejemplos usan `$HERMES_HOME/skills/cisne-cms/scripts/cisne_cms.py`. La sesión se conserva en `$HERMES_HOME/.cisne-cms-session/` con permisos privados. El cliente valida TLS y no sigue redirecciones; configura el dominio canónico. HTTP solo se admite en loopback para pruebas locales.

Antes de desarrollar o redactar contenido consulta `agente-cisne/instrucciones.md` y las fichas de conocimiento del repositorio. Para cambios de software sigue AGENTS, usa pruebas y no publiques código por una autorización editorial.

## Consultar y editar

```sh
python3 "$HERMES_HOME/skills/cisne-cms/scripts/cisne_cms.py" state
python3 "$HERMES_HOME/skills/cisne-cms/scripts/cisne_cms.py" state --include-published
python3 "$HERMES_HOME/skills/cisne-cms/scripts/cisne_cms.py" mutate /ruta/privada/cambio.json
```

`cambio.json` es un objeto con `version` leída del CMS y `operation`. Ejemplo de estructura; no usar esta versión o ID sin leerlos:

```json
{"version":12,"operation":{"action":"update","collection":"barril","id":"colchita","data":{"disponible":false}}}
```

Acciones: `create`, `update`, `delete`. Colecciones: `barril`, `latas`, `sin_alcohol`, `comida`, `events`, `gallery`, `page`, `negocio`; la API valida los campos y restricciones. `category_id` identifica la categoría cuando corresponde. No usar borrado definitivo para una pausa de disponibilidad: ocultar o marcar agotado conserva referencias.

Si recibe `409`, relee y compara. Nunca reintentes una escritura a ciegas después de una desconexión. El estado publicado no equivale al borrador. Conserva IDs, referencias, otras modificaciones y opciones ocultas.

## Imagen de cerveza desde etiqueta

1. Inspecciona el adjunto y resuelve con el responsable los datos requeridos faltantes. Guarda una ficha válida con datos confirmados; no uses ceros o cifras inventadas. Guarda su versión e ID.
2. Sube la etiqueta original JPG/PNG/WebP (máximo 20 MB en este cliente) al MediaHub. No generes imágenes sin referencia de etiqueta identificada.
3. Solicita generación con el ID devuelto del medio y la versión del borrador. Consulta el trabajo hasta obtener resultado o error; no repitas el POST para sondear.
4. Cuando el trabajo esté `ready`, usa `image-download ID_DEL_TRABAJO`. Devuelve `filepath` privado y metadatos. Abre ese archivo con la herramienta de visión disponible y muéstralo/adjúntalo al operador en la misma conversación autorizada de Telegram; no envíes una URL privada que el operador no pueda abrir. Verifica texto e identidad. Una generación no significa que el producto esté publicado ni que su imagen ya se haya asociado. Relee el borrador y sigue el contrato de resultado de la API.
5. Solo después de aprobar la imagen, asóciala mediante `mutate` usando el campo `img` y la URL real devuelta por MediaHub. No inventes rutas. Si ya está asociada, no dupliques el cambio. Comprueba la vista previa privada.

```sh
python3 "$HERMES_HOME/skills/cisne-cms/scripts/cisne_cms.py" media-upload /ruta/privada/etiqueta.png --metadata /ruta/privada/medio.json
python3 "$HERMES_HOME/skills/cisne-cms/scripts/cisne_cms.py" generate-image /ruta/privada/imagen.json
python3 "$HERMES_HOME/skills/cisne-cms/scripts/cisne_cms.py" image-status ID_DEL_TRABAJO
python3 "$HERMES_HOME/skills/cisne-cms/scripts/cisne_cms.py" image-download ID_DEL_TRABAJO
```

`image-download` descarga únicamente el derivado `/cms/media/<media.id>/file` del trabajo listo, usando la sesión existente y sin seguir redirecciones. Acepta PNG/WebP hasta 20 MB y guarda un archivo nuevo en `$HERMES_HOME/.cisne-generated/` (directorio `700`, archivo `600`), sin sobrescribir archivos ni aceptar destinos arbitrarios. El JSON incluye `filepath`, tipo, tamaño, checksum e ID de medio. No adjuntes la carpeta de sesión; no publiques la imagen antes de revisarla. Si la plataforma no permite mostrar archivos, informa esa limitación y deja pendiente la aprobación visual.

Estructura de `imagen.json`: `{"collection":"barril","id":"ID_REAL","reference_media_id":"MEDIO_REAL","version":12}`. Metadatos de etiqueta: título identificable, categoría `cervezas`, descripción de procedencia y alternativa útil. Las claves aceptadas se validan en el CMS.

La imagen del menú es **ilustración editorial generada**, no etiqueta oficial. Conservar el original. No copiar datos de Colchita ni inventar premios, ingredientes o envases. Los precios permanecen editables en la ficha.

## Publicación separada

`state --include-published` permite comparar todo el borrador contra `published_document`. El CMS publica el borrador completo, no solo el cambio del agente. Si incluye trabajo ajeno no autorizado, no publiques.

Con instrucción explícita que cubra el resultado revisado y cuenta propietaria:

```sh
python3 "$HERMES_HOME/skills/cisne-cms/scripts/cisne_cms.py" publish --version VERSION_REVISADA --note 'Cambio autorizado de contenido' --confirm-publication
```

El flag expresa la decisión del operador; no sustituye la autorización humana ni el permiso validado por el servidor. La skill no publica automáticamente después de editar o generar. No usa funciones de usuarios, ventas, cobros, shell remoto o despliegue.

Al terminar comunica ID, campos cambiados, versión, estado y vista previa/URL comprobada. Los errores aparecen como JSON sin credenciales. No adjuntes cachés de sesión ni archivos de configuración privada.
