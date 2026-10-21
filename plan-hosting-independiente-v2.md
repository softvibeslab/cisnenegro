# Cisne Negro — plan de migración a hosting independiente con v2

Fecha del plan: 9 de octubre de 2026. **Actualización del 10 de octubre:** el usuario eligió desplegar en `31.220.63.211`. La instalación con aplicación y datos separados ya está publicada en `https://cisne.softvibes.art/`; comparte el VPS existente. Ver [estado ejecutado y siguiente cambio DNS](hosting-independiente/DESPLIEGUE.md). El resto de este documento conserva la propuesta original de infraestructura físicamente independiente.

## 1. Resultado solicitado

Una instalación propia de Cisne Negro, independiente del VPS actual, con la versión v2 como sitio principal y el CMS conectado a esa versión.

| Módulo | Origen actual | Destino definitivo |
|---|---|---|
| Página principal | `https://cisnenegro.softvibes.art/v2/` | `https://www.cisnenegro.mx/` |
| Menú y Pasaporte | `https://cisnenegro.softvibes.art/v2/menu/` | `https://www.cisnenegro.mx/menu/` |
| CMS y MediaHub | `https://cisnenegro.softvibes.art/cms/#editor` | `https://www.cisnenegro.mx/cms/#editor` |
| Administración | `https://cisnenegro.softvibes.art/v2/admin/` | `https://www.cisnenegro.mx/admin/` |
| Operación del equipo | `https://cisnenegro.softvibes.art/v2/equipo/` | `https://www.cisnenegro.mx/equipo/` |

El dominio sin `www` redirigirá al dominio con `www`. El aviso de privacidad y los recursos necesarios acompañan a estos módulos. Las propuestas comerciales, análisis y borradores no se incorporan automáticamente al sitio público del negocio.

La independencia incluye aplicaciones, datos, fotos, videos, tareas y respaldos. La web nueva debe funcionar sin consultar el VPS anterior.

## 2. Lo comprobado y lo que falta

- En la comprobación pública, portada v2, menú, CMS y equipo respondieron HTTP 200; admin respondió 401, compatible con su protección de acceso. Esto verifica disponibilidad de las pantallas, no sus operaciones autenticadas.
- El README identifica `/v2` como servicio separado. Su fuente completa y su configuración no están en este subproyecto local. Antes de empaquetar hay que recuperar la versión realmente desplegada y localizar sus bases de datos.
- El CMS local utiliza Python, SQLite y un MediaHub que procesa video con FFmpeg. Publica las plantillas anteriores de `sitio/index.html` y `sitio/menu/index.html`; no está comprobada una conexión editorial con v2.
- El JavaScript público de v2 utiliza `/v2/data/menu.json`, `/v2/api/`, rutas de equipo y QR con el prefijo `/v2`. Los manifiestos y el service worker también dependen de ese prefijo.
- Equipo contempla pedidos QR, cuentas por mesa, registro de cobros, historial y cortes. Sus datos deben inventariarse junto con Pasaporte, usuarios y contenido.
- El código local del Content Hub existe, pero su registro en el CMS y su despliegue no están confirmados. Si está activo, se migra su base; terminar funciones pendientes del Hub es otro alcance.

Referencias locales: [README](README.md), [servidor CMS](backend/cms_server.py), [renderizado editorial](backend/cms_content.py), [MediaHub](backend/cms_media.py), [respaldo CMS](deploy/backup-cms.py) y [activación de rutas](deploy/activate-cms.py).

## 3. Elegir un hosting compatible

**Propuesta inicial:** alojamiento administrado de aplicaciones que permita Python o contenedores, procesos permanentes y almacenamiento persistente. Se puede mantener el dominio en Hostinger y alojar la aplicación con otro proveedor.

Hostinger documenta que Python y Flask se admiten en sus VPS, no en Web Hosting ni Cloud Hosting. Por tanto, un plan compartido de esos productos exigiría adaptar el backend; copiar archivos a `public_html` no conserva el CMS actual. [Compatibilidad oficial de Hostinger](https://www.hostinger.com/support/which-programming-languages-and-frameworks-are-supported-at-hostinger/).

Render es un candidato para evaluar: admite Python y contenedores. Una propuesta técnica inicial sería un servicio de pago con un contenedor que reúna el enrutador, CMS, backend operativo y procesamiento de medios, sujeto a confirmar el runtime de v2. [Servicios web de Render](https://render.com/docs/web-services).

En esa opción, el disco persistente pertenece a una sola instancia y no se comparte con otros servicios; sus despliegues pueden causar una breve interrupción. Las bases, medios y tareas que acceden al mismo disco deben quedar en esa instancia. Si se necesitan varias instancias, habrá que adaptar almacenamiento y base de datos. [Discos persistentes de Render](https://render.com/docs/disks).

| Componente | Condición que debe cumplir el plan contratado |
|---|---|
| Aplicaciones | Python compatible con el backend actual; runtime de v2 por verificar; arranque y reinicio automáticos |
| Medios | FFmpeg/ffprobe, soporte H.264 y dependencias de imagen; CPU y RAM verificadas con una carga real de video |
| Persistencia | Volumen para SQLite, índices y medios, separado del código y del directorio público |
| Capacidad | Medir biblioteca y datos reales; reservar margen para crecimiento y temporales. La cuota local de biblioteca es 10 GB, no una medición del uso |
| Subidas | Compatibilidad de toda la cadena con fotos de hasta 20 MB y MP4 de hasta 100 MB; revisar límites del proveedor, proxy y tiempos de procesamiento |
| Acceso | HTTPS, dominio propio, secretos privados y rutas internas entre servicios |
| Operación | Logs, alertas, copias externas al hosting y restauración comprobada |

**Decisión pendiente:** proveedor y nombre exacto del plan. No contratarlo basándose únicamente en espacio o dominio incluido. Confirmar costo recurrente de cómputo, disco, transferencia y copias antes de elegir.

## 4. Ejecución por fases

### Fase 1 — Recuperar e inventariar la instalación real

Responsable: equipo técnico, con los accesos que facilite Roger.

1. Obtener fuentes y versión exacta de v2, CMS, admin y equipo, junto con dependencias, configuración de rutas, servicios y tareas programadas. Documentar cualquier diferencia con la carpeta local.
2. Localizar cada base de datos activa. No asumir que `backend/club_server.py` o el `club.db` del sistema anterior corresponden a los pedidos y socios de v2.
3. Inventariar contenido publicado y borradores; cuentas y roles; socios, visitas y canjes; pedidos, mesas, cobros e historial; originales y derivados de medios. Registrar conteos y tamaños sin poner datos personales en el informe público.
4. Respaldar SQLite mediante un mecanismo consistente y comprobar una restauración. Incluir archivos de medios y referencias; revisar tareas de video pendientes. Si existe `hub.sqlite` activo, añadirlo expresamente: el respaldador local actual no lo incluye.
5. Exportar DNS completo y registrar servicios del dominio, incluidas web y cuentas de correo actuales.

**Salida:** inventario verificable, respaldo restaurable y mapa de dependencias. Sin esa fuente completa no se declara preparado el paquete de v2.

### Fase 2 — Preparar una instalación portable

Responsable: equipo técnico.

1. Crear dentro del proyecto un paquete de despliegue reproducible: código de Cisne Negro, dependencias con versiones, configuración de arranque, rutas y ejemplo de variables sin secretos. No incluir el workspace completo de otros clientes.
2. Separar código, datos persistentes, respaldos y configuración privada. Transportar datos y secretos por separado del artefacto público.
3. Sustituir los servicios de systemd por el mecanismo de arranque y supervisión del hosting elegido. Configurar salud de servicios, límites de subidas y recuperación de tareas de medios.
4. Definir un único enrutamiento público para las cinco pantallas. Conservar el backend operativo real de v2 y resolver cualquier colisión entre sus APIs y las del CMS/Pasaporte anterior; documentar qué servicio atiende cada ruta.
5. Configurar copias consistentes automáticas, copia externa, retención y procedimiento de restauración. No dejar el respaldo exclusivamente en el VPS antiguo ni en el mismo disco de producción.

**Salida:** instalación que arranca y conserva sus datos después de reiniciarse o desplegar una nueva versión.

### Fase 3 — Llevar v2 a la raíz y conectarla con el CMS

Responsable: equipo técnico; Roger valida diseño y contenido.

1. Mantener el diseño de v2 y adaptar sus rutas a `/`, `/menu/`, `/admin/` y `/equipo/`. Revisar enlaces, assets, JSON, APIs, QR y redirecciones, evitando reemplazos de texto indiscriminados.
2. Integrar el contenido publicado del CMS en las plantillas de v2: hero, textos, negocio, catálogo, galería y demás campos que realmente use cada componente. Adaptar el editor y su vista previa a esas plantillas.
3. Definir una fuente única del catálogo. Conservar IDs y relaciones; coordinar precios y disponibilidad publicados con el backend de pedidos para que lo mostrado coincida con lo validado por el servidor. Los pedidos históricos conservan sus importes originales.
4. Hacer que publicar y restaurar una revisión actualicen v2 y sus cachés. Regenerar salidas desde la publicación vigente, sin promover borradores pendientes ni servir HTML de la plantilla anterior guardado en revisiones.
5. Ajustar `CMS_ORIGIN`, cookies y verificación de origen para `https://www.cisnenegro.mx`. Documentar las cuentas y permisos de CMS, admin y equipo; no asumir que comparten la misma autenticación. Los usuarios volverán a iniciar sesión en el nuevo dominio.
6. Actualizar manifiestos, identificadores, alcance y cachés de las apps instalables. Excluir APIs y respuestas privadas del almacenamiento público; evitar que el service worker de la raíz interfiera con CMS, admin o equipo. Explicar cómo abrir o reinstalar las apps del nuevo dominio.
7. Actualizar canonical, metadatos, sitemap y aviso de privacidad. Retirar `noindex` de páginas públicas definitivas, incluidas las cabeceras globales del CMS; conservar autenticación y exclusión de indexación de paneles, borradores y pruebas.

**Salida:** editar en el CMS modifica la versión v2 que verá el cliente en el dominio definitivo.

### Fase 4 — Probar en el nuevo hosting antes del cambio público

Responsables: equipo técnico y una persona de operación de Cisne Negro.

Usar una URL temporal con acceso restringido y una copia aislada de datos. Las pruebas no deben escribir en producción ni generar operaciones reales en servicios externos.

| Prueba | Criterio de aceptación |
|---|---|
| Sitio y menú | Diseño v2 correcto en móvil y escritorio; imágenes, video, filtros, enlaces y contacto funcionales |
| CMS | Borrador privado, vista previa v2, publicar y restaurar; cambios visibles en portada y menú correctos |
| MediaHub | Subir foto y video, generar derivados y reproducirlos; originales privados y biblioteca consistente |
| Pasaporte | Registro e ingreso, visitas, recompensas, canjes y NPS según funciones activas; sin duplicación de datos |
| Pedidos y equipo | Pedido QR online y offline, lectura, estados, cuenta por mesa, registro de cobro, historial y corte con cuentas de prueba |
| Roles | CMS, admin y equipo permiten únicamente las acciones del rol correspondiente; sesiones y cierre de sesión correctos |
| Persistencia | Reiniciar o volver a desplegar conserva contenido, usuarios, operaciones y medios; restaurar una copia en un entorno aislado |
| Independencia | Revisar llamadas de navegador y servidor: ninguna función depende del dominio o la IP del VPS anterior |
| Transición | Probar URLs antiguas, parámetros de QR y fragmentos offline, apps instaladas y mensajes a clientes con caché antigua |

**Salida:** acta de pruebas y versión concreta lista para cambiar el dominio. Abrir las pantallas sin errores no basta para aprobar la migración.

### Fase 5 — Conectar cisnenegro.mx y hacer el corte

Responsables: equipo técnico y administrador de DNS; operación coordina la ventana.

1. Reducir con antelación el TTL de los registros web cuando sea posible. Preparar en el hosting `www.cisnenegro.mx`, el dominio raíz y HTTPS. Usar los destinos DNS exactos que asigne el nuevo proveedor, nunca la IP del VPS antiguo.
2. Coordinar una ventana de baja actividad. Resolver o inventariar pedidos/cuentas abiertos; pausar temporalmente escrituras en CMS, Pasaporte y operación del sistema antiguo y completar una copia final consistente.
3. Restaurar los datos finales, comparar conteos y verificar integridad y medios. Habilitar un solo sistema para recibir nuevas operaciones; el antiguo queda sin escrituras para evitar dos bases divergentes.
4. Cambiar únicamente los registros web necesarios. Conservar MX, SPF, DKIM, DMARC y verificaciones del correo. Revisar A/AAAA/CNAME/CAA según las instrucciones del proveedor y verificar certificado de ambos nombres.
5. Probar las cinco URLs definitivas, login y una operación controlada de extremo a extremo. Verificar correo entrante y saliente con el responsable.
6. Mantener compatibilidad de URLs `/v2/*` y QR públicos antiguos mediante un mapa de redirecciones que conserve ruta y parámetros; comprobar también los fragmentos usados por QR offline. No redirigir a ciegas escrituras de APIs antiguas: los clientes desactualizados deben recibir una respuesta controlada que les permita reabrir el sistema nuevo.
7. Para conservar los enlaces de `cisnenegro.softvibes.art` sin depender permanentemente del VPS, alojar su capa de redirección en infraestructura independiente y ajustar ese subdominio cuando corresponda. No basta con dejar las redirecciones únicamente en el VPS que se quiere abandonar.

Si se elige Render, el proveedor permite dominio personalizado y gestiona emisión y renovación TLS; su activación debe comprobarse durante el corte. [Dominios personalizados de Render](https://render.com/docs/custom-domains).

**Salida:** negocio operativo en `.mx`, un solo origen de datos y correo preservado.

### Fase 6 — Observar, documentar y retirar la instalación anterior

1. Vigilar durante al menos 48–72 horas disponibilidad, errores, publicación, pedidos, canjes y copias. Comprobar persistencia después de un reinicio controlado.
2. Entregar accesos por canal privado, manual de despliegue, inventario, respaldo, guía de restauración y responsables de renovación/soporte.
3. Mantener la instalación anterior recuperable durante el periodo acordado, sin aceptar operaciones nuevas. Retirar únicamente los servicios de Cisne Negro que ya no sean necesarios; no apagar un VPS que aloje otros proyectos.
4. Si también se quiere transferir el registro del dominio a Hostinger, hacerlo como trámite separado después de estabilizar web y DNS, preservando la zona y el correo. Alojar la web no exige transferir primero el registro.

## 5. Reversión y condiciones para lanzar

Antes del corte debe existir una versión restaurable, una copia consistente y el DNS anterior documentado. Si falla la nueva web antes de recibir operaciones, restaurar servicio/configuración y registros web según el punto de fallo, teniendo en cuenta las cachés DNS.

Si el sistema nuevo ya recibió pedidos, cobros, socios o canjes, **no restaurar una base antigua ni devolver las escrituras al sistema anterior sin conciliar esos datos**. Pausar operaciones, conservar lo nuevo y resolver la recuperación. Volver a Squarespace solo recuperaría la web previa del dominio, no sustituye el sistema operativo v2.

Se considera listo cuando: las cinco rutas usan la versión solicitada, el CMS publica sobre v2, los datos y medios están completos, pedidos/Pasaporte/roles pasan pruebas, existe restauración verificada y no quedan dependencias de ejecución en el VPS.

## 6. Entregables y calendario

Entregables previstos: inventario real, paquete portable de código, configuración sin secretos, respaldo privado de datos/medios, CMS integrado con v2, entorno probado, mapa DNS/URLs, acta de pruebas y manual de operación/reversión.

La secuencia es **inventario → hosting compatible → paquete e integración → pruebas → corte → observación**. El calendario y costo técnico se cierran al recuperar la fuente de v2 y confirmar el hosting: la integración editorial aún no está comprobada y puede requerir desarrollo. La estimación de uno a dos días del plan anterior no aplica a este alcance. La propagación DNS y una eventual transferencia del registro se planifican aparte.

Para iniciar hacen falta: proveedor y plan de destino, acceso delegado a la instalación actual para exportarla, acceso al DNS y una persona del negocio para validar operación. Ninguna credencial debe guardarse en este documento.
