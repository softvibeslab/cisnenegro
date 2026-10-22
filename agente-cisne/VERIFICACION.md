# Verificación · 21 de octubre de 2026

- **120 pruebas Python de la aplicación** aprobadas: CRUD editorial, chat/trabajos de imagen, puente Unix y worker Hermes, además de la regresión previa.
- **17 pruebas del cliente Hermes** aprobadas con servidor HTTP simulado: cookies privadas, CSRF, TLS/origen, bloqueos de redirección, conflictos, carga y descarga de imágenes, límites y permisos de archivos.
- **22 comprobaciones de interfaz** aprobadas en Playwright con API simulada: botón flotante, popup, foco/Escape, navegación, cierre/reapertura durante una consulta, chat, texto seguro, historial acotado, cambios locales, etiquetas, generación, recuperación de trabajos, aplicación al borrador, conflictos, móvil pequeño y horizontal.
- **11 comprobaciones JavaScript existentes** de seguridad/caché y prueba de disponibilidad del menú aprobadas.
- Integración HTTP contra el CMS local real: cliente Hermes autenticado como editor, crear → consultar → actualizar → eliminar producto ficticio. El catálogo publicado conserva exactamente su contenido anterior.
- Perfil `cisne-negro` creado; su modelo respondió correctamente en una prueba real de identidad y distinción borrador/publicación. No se inició el gateway de Telegram ni se enviaron mensajes a terceros.
- **Consulta real desde el popup** contra el perfil Hermes: leyó la carta de barril y devolvió productos correctos del borrador. Estado «Hermes conectado · Perfil cisne-negro» comprobado en Chrome.
- **Edición real con Hermes en base temporal aislada:** consultó una cerveza ficticia, cambió solo su nombre, conservó precio/visibilidad y dejó intacta la carta publicada. La base temporal se descartó al terminar; no se tocó el borrador de uso del usuario.
- Botón flotante y popup revisados en Chrome sobre el CMS local. Las capturas actuales de esta sesión se conservan fuera de Git. Las capturas de `capturas/` son evidencia histórica de la primera entrega, antes del popup.

## Despliegue y consulta real en producción

- Popup desplegado en [https://cisne.softvibes.art/cms/](https://cisne.softvibes.art/cms/). Configuración autenticada: `configured=true`, `provider=hermes`, `profile=cisne-negro`, modelo `gpt-6-astra`; `image_configured=false`.
- Consulta real mediante el perfil del servidor: Hermes utilizó `read_content` y respondió con datos del CMS. No se realizaron cambios editoriales: borrador **5** y publicación **8** permanecieron intactos.
- Revisión visual en Chrome sobre producción: el popup respondió con ¡Alarma! Red IPA, Agua Puerca Imperial Stout y Colchita Kölsch; identificó el borrador 5 y confirmó que no había cambios. La captura autenticada `popup-hermes-produccion.jpg` se conserva en el archivo privado, fuera de Git.
- Servicio host `cisne-hermes` activo y habilitado; Docker accede exclusivamente al socket privado. No se montaron credenciales ni el perfil en el contenedor.
- Respaldo consistente verificado: **1,448 archivos y 479 medios**, además de imagen anterior y copia privada de código/configuración. Rutas y reversión en el [registro del despliegue](../hosting-independiente/docs/agente-cisne-despliegue-2026-10-21.md).
- El temporal tiene TLS válido. `cisnenegro.mx` responde 200 al conectar directamente al servidor con SNI, pero su resolución pública devuelve `SERVFAIL`: las autoridades antiguas rechazan consultas y la delegación `.mx` sigue apuntando a ellas. No se modificaron DNS durante este despliegue.

## Preparación posterior del perfil remoto

- Selector de servidor `CISNE_HERMES_PROFILE_NAME`: admite únicamente `cisne-negro` y `cisnenegro`; conserva el predeterminado actual.
- Identidad remota comprobada antes de declarar conectado; cada solicitud lleva `expected_profile` y el worker actualizado rechaza una discrepancia antes de cargar autenticación o ejecutar inferencia, incluso con estado en caché.
- **120 pruebas Python** aprobadas, incluidas **39 del adaptador, bridge y worker**. Cubren el perfil `cisnenegro`, nombres y rutas incorrectos, rechazo de destino distinto y respuesta 429 temprana sin reenvíos. Sintaxis JavaScript y diff verificados.
- El servidor `169.58.107.205` rechazó el acceso SSH desde esta computadora. Su configuración y autenticación todavía no se han inspeccionado; no se ha probado una consulta real ni desplegado este selector en producción.
- [Guía de conexión del perfil existente](hermes/CONEXION-PERFIL-REMOTO.md). Túnel y activación pendientes; no se modificó el CMS operativo para esta preparación.

## Límites de la verificación

Las pruebas automatizadas sustituyen los proveedores externos por simulaciones; además se verificaron chat y edición real en local, y consulta real de contenido en producción. No se ha probado todavía una generación real de imagen desde el servidor: requiere su clave de API y acceso al modelo. La conexión Hermes utiliza `codex_responses`; un cambio de transporte exige adaptar y verificar el worker.

Falta conectar bot/operadores Telegram y su cuenta editorial del CMS, y ejecutar una prueba real etiqueta → imagen → vista previa con la IA configurada. El popup usa la cuenta CMS ya autenticada. El despliegue autorizado está completado; quedan la resolución del dominio con Hostinger y la conexión al perfil del usuario `cisnenegro` en `169.58.107.205`. El código se entrega en la rama `feat/agente-cisne-cms-hermes`, sin fusionarlo en `main`. La prueba de producción fue de consulta y no alteró contenido.

## Repetir comprobaciones

```sh
cd hosting-independiente
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
node tests/frontend-security.cjs
node tests/menu-availability.cjs
# En otra terminal: python3 -m http.server 8661 --bind 127.0.0.1 --directory sitio
# Requiere Chrome y Playwright instalado en un entorno de desarrollo:
NODE_PATH=/ruta/al/entorno/node_modules node tests/cms-agent.cjs
cd ..
python3 -m unittest discover -s agente-cisne/hermes/tests -p 'test_*.py'
```

El script de interfaz usa el servidor estático local indicado y simula la API. Las pruebas Python usan carpetas y bases temporales. Ninguna requiere credenciales de producción.
