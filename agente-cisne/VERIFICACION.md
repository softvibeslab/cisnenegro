# Verificación · 21 de octubre de 2026

- **80 pruebas Python de la aplicación** aprobadas: incluyen 10 del CRUD editorial y 19 del chat/trabajos de imagen, además de la regresión previa.
- **17 pruebas del cliente Hermes** aprobadas con servidor HTTP simulado: cookies privadas, CSRF, TLS/origen, bloqueos de redirección, conflictos, carga y descarga de imágenes, límites y permisos de archivos.
- **14 comprobaciones de interfaz** aprobadas en Playwright con API simulada: chat, texto seguro, historial acotado, cambios locales, cargas, generación, recuperación de trabajos, aplicación al borrador, conflictos y móvil.
- **11 comprobaciones JavaScript existentes** de seguridad/caché y prueba de disponibilidad del menú aprobadas.
- Integración HTTP contra el CMS local real: cliente Hermes autenticado como editor, crear → consultar → actualizar → eliminar producto ficticio. El catálogo publicado conserva exactamente su contenido anterior.
- Perfil `cisne-negro` creado; su modelo respondió correctamente en una prueba real de identidad y distinción borrador/publicación. No se inició el gateway de Telegram ni se enviaron mensajes a terceros.
- Login y pestaña del agente comprobados en Chrome sobre la aplicación local. Estado de configuración ausente visible; controles de IA deshabilitados. Revisión visual móvil de 390 px, sin desbordes.
- Capturas [escritorio](capturas/cms-agente-escritorio.png) y [móvil](capturas/cms-agente-movil.png): interfaz local con datos de revisión, sin credenciales ni conversaciones reales. Muestran el estado pendiente de proveedor, no una generación real.

## Límites de la verificación

Las pruebas de Responses API e imágenes sustituyen el proveedor por uno simulado. No se ha probado todavía una llamada real de generación desde el servidor: requiere su clave de API y acceso al modelo. La prueba real de Hermes usa su proveedor configurado, independiente de esa integración web.

Falta conectar bot/operadores Telegram, cuenta editorial del CMS y ejecutar una prueba real etiqueta → imagen → vista previa con la IA configurada. También falta el despliegue autorizado de esta versión. No se modificó el contenido ni la infraestructura de producción.

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
