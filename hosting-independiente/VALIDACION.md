# Validación de la copia independiente

Fechas: 9–10 de octubre de 2026; adaptación al dominio sin `www` probada y desplegada el 17 de octubre. Entorno local: macOS, Python 3.14.7, SQLite, FFmpeg y Gunicorn. Dirección de revisión local: `http://127.0.0.1:8088/`.

## Resultado

**64 pruebas Python (48 de aplicación/importación y 16 de respaldo/activación DNS) y 11 pruebas JavaScript aprobadas.** Las pruebas automatizadas utilizan bases temporales. El despliegue autorizado y su validación en el VPS se documentan en [DESPLIEGUE.md](DESPLIEGUE.md).

| Área | Resultado |
|---|---|
| Archivos públicos | Portada y menú renderizados con imagen o video sin recursos locales faltantes |
| CMS | Borrador privado, publicación/restauración y precios de la revisión publicada comprobados |
| MediaHub | Subida de imagen, privacidad, video real procesado con FFmpeg y reproducción parcial HTTP 206 |
| Operación | Pedido, asignación a cuenta, registro de cobro/propina y corte; QR offline recalculado y sin duplicados |
| Pasaporte | Registro, privacidad, ingreso, visita diaria, NPS, quinta visita, recompensa y canje único |
| Autorización | Propietario/editor, personal administrador/mesero, token interno, origen y CSRF |
| Gateway | Cookies, límites, rutas privadas, protección de archivos, redirecciones y estado de salud |
| PWA | Paneles y APIs fuera de caché, menú offline y conservación de cachés ajenas |
| Transición de dominio | Tres orígenes explícitos, rechazo de externos y solicitudes entre dominios, CSRF y cookies por host |
| Indexación | Solo páginas públicas del dominio sin `www` HTTPS; temporal y paneles bloqueados; robots, sitemap y canonical coherentes |
| SEO guardado | HTML de publicaciones antiguas adapta metadatos propios al dominio final sin escribir en bases, borrador ni enlaces editoriales |
| Importación | Regenera plantillas v2, conserva borrador y publicación activa, respaldo previo y bloqueo del destino en uso |
| Copias | SQLite con WAL, medios, retención, reinicio ante fallos y restauración temporal comprobada por SHA-256 |

Comandos ejecutados:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m unittest discover -s deploy -p 'test_*.py' -v
node tests/frontend-security.cjs
```

## Comprobaciones sobre la instancia local

- HTTP 200 en portada, menú, CMS, equipo, privacidad, manifiesto y estado de salud.
- Inicio de sesión real por HTTP en CMS y Equipo; acceso autorizado a Administración, estadísticas y ajustes.
- Revisión visual en Safari de portada, CMS/editor, vista previa de celular, MediaHub, Administración y Equipo. En Chrome se comprobó la pantalla de pedido con QR.
- Equipo abrió el pedido creado en el menú local, mostrando el mismo producto y total; no se cobró ni canceló ese pedido manual.
- Biblioteca copiada: 420 imágenes y 57 videos, todos listos; originales, derivados y miniaturas comprobados sin faltantes.
- Reinicio completo del launcher: se conservaron cuentas, contenido publicado, borrador, los 477 medios y el pedido local existente.
- Recursos públicos independientes del VPS anterior; los aliases de dominios anteriores solo se conservan para reconocer y adaptar URLs propias. `/v2/` permanece como ruta de compatibilidad del gateway.

## Comprobación del entregable

- ZIP construido por lista explícita, sin `.venv`, bases SQLite, archivos privados ni credenciales locales.
- ZIP extraído en una carpeta temporal y arrancado con datos nuevos: salud, portada, menú, CMS, equipo, API de configuración y video disponibles.
- Los medios del MediaHub son datos privados separados; no se incorporan al ZIP de código.
- Adaptación comprobada sobre una copia temporal obtenida en lectura del CMS real: tres publicaciones regeneradas, revisión activa 3 y borrador conservado. La copia temporal se eliminó al terminar; ninguna base original se modificó.
- Configuración de Compose comprobada: una instancia, UID 10001, datos fuera del código, puerto web limitado a loopback y registros con rotación.
- Imagen Docker construida y ejecutada en Linux ARM64 mediante una VM local de Colima. Prueba en modo producción con datos nuevos: portada, menú, CMS, admin, equipo, video, autenticación en ambos dominios, rechazo de origen externo, indexación por host, UID 10001, herramientas FFmpeg/OpenSSL y sesión conservada después de reiniciar. Contenedores y volumen de ensayo retirados al terminar.
- Caddy validó su configuración real. Su servicio interno de autorización respondió 200 para los tres dominios previstos y 403 para dos dominios externos. No se solicitaron certificados públicos ni se modificó DNS durante esta prueba.

Para repetir la prueba de la imagen ya construida, usando exclusivamente datos efímeros:

```sh
python3 tests/docker_smoke.py --image cisne-independent:local
```

## Límites de esta validación

El 17 de octubre se reconstruyó la imagen AMD64 y se comprobó el contenedor saludable. Tras guardar los DNS en Squarespace, se emitió el certificado para apex y `www`. La verificación HTTPS pública desde el VPS devolvió 200 en portada, menú, CMS, equipo, privacidad, video, salud, robots y sitemap; las páginas públicas tienen canonical e indexación del dominio sin `www`. HTTP y `www` redirigen a apex conservando parámetros. Se verificaron acceso CMS y Administración/MediaHub autenticados con el certificado final y conexión a la IP nueva desde el equipo local. Las cuatro autoridades DNS confirman los registros nuevos y los MX/TXT/auxiliares intactos; algunas cachés públicas y el navegador local todavía muestran el sitio anterior. El temporal conserva HTTPS y `noindex`.

La imagen se probó localmente en ARM64 y se construyó en AMD64 en el VPS. `https://cisne.softvibes.art/` funciona con certificado público, acceso CMS/administración y equipo verificados; se comprobaron los 49 productos, las variantes de v2 y los 477 medios. La primera copia del servidor se restauró y verificó, y la aplicación volvió a estar saludable. Safari mostró portada, menú y acceso al CMS.

Quedan pendientes: caducidad de cachés DNS anteriores, réplica externa periódica de respaldos, prueba de cargas máximas bajo la carga real del VPS, cámara/QR y app instalable en teléfonos físicos. La nueva instancia conserva las cuentas y operaciones v2, que incluyen usuarios de demostración; no se añadieron las cuentas de la copia local. La indexación final está habilitada por host; el temporal permanece en `noindex`.
