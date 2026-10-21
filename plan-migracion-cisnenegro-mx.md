# Plan para conectar cisnenegro.mx y transferirlo a Hostinger

> **Plan anterior, sustituido en alcance el 9 de octubre de 2026.** La solicitud vigente es un hosting nuevo independiente y usar v2 como sitio principal. Seguir [el nuevo plan de hosting independiente](plan-hosting-independiente-v2.md). No ejecutar las instrucciones de este documento para reutilizar el VPS o apuntar a su IP; se conserva como antecedente de las consultas DNS y del trámite de dominio.

Preparado el 9 de octubre de 2026. Estado: plan; no se han modificado dominio, DNS, servidor ni servicios.

## Resultado esperado

- Dominio administrado desde la cuenta Hostinger de Roger; titular y contactos del negocio documentados.
- Dirección principal propuesta: `https://www.cisnenegro.mx/`, conservando la variante pública actual.
- `https://cisnenegro.mx/` redirige a la dirección principal.
- Sitio, menú, CMS, MediaHub y Pasaporte usan el VPS existente y conservan sus datos.
- Correo continúa con el proveedor actual. Una migración de buzones sería otro trabajo.
- Enlaces y QR públicos antiguos siguen funcionando mediante redirecciones.

Secuencia recomendada: accesos → respaldo → preparar VPS → conectar web → comprobar → trasladar DNS → transferir registro → cerrar y monitorear. La publicación web no necesita esperar a que termine la transferencia del registro.

## Estado comprobado en consultas públicas

| Elemento | Observación del 9 de octubre |
|---|---|
| Registrador en WHOIS | Tucows.com Co. |
| Alta / vencimiento publicado por el registro | 5 de mayo de 2024 / 5 de mayo de 2027; confirmar fecha contractual en el panel |
| DNS autoritativo | ns-cloud-b1, b2, b3 y b4.googledomains.com |
| Web actual | A de raíz 198.49.23.145; www apunta a ext-sq.squarespace.com |
| Correo | Cinco registros MX hacia Google; confirmar buzones activos y quién factura Workspace |
| Nueva web | cisnenegro.softvibes.art resuelve a 31.220.63.211 |
| Indexación de la nueva web | Portada con meta noindex y cabecera X-Robots-Tag; robots.txt devuelve Disallow: / |
| DNSSEC | No se obtuvo un DS en la consulta; volver a comprobar antes de cambiar nameservers |

La web está conectada a Squarespace, pero estos datos no identifican por sí solos la cuenta donde se administra el dominio. Squarespace es un posible panel comercial sobre Tucows; debe confirmarse con el responsable. DNS público no sustituye una exportación completa de la zona: no permite descubrir todos los subdominios ni selectores DKIM.

## 1. Reunir accesos y responsables

Responsables: Roger y dueños/proveedor actual.

- Identificar la cuenta que administra cisnenegro.mx, su titular y el correo que recibe autorizaciones de transferencia.
- Confirmar acceso a Hostinger, al VPS existente y a quien administra Google Workspace.
- Obtener acceso delegado cuando esté disponible. Contraseñas, códigos de recuperación y Auth/EPP se manejan por un canal privado, fuera de este documento.
- Confirmar con el negocio la administración del dominio en la cuenta de Roger y conservar los datos del titular correspondientes al negocio.
- Verificar en Hostinger que cisnenegro.mx admite transferencia; revisar costo, bloqueos, requisitos específicos de .mx y qué sucede con su vencimiento. No asumir las reglas de renovación de .com.

Salida: proveedor identificado, acceso al DNS y correo de autorización disponible.

## 2. Guardar el estado actual

Responsable: equipo técnico, con acceso del proveedor actual.

- Exportar toda la zona DNS: A, AAAA, CNAME, MX, TXT, SPF, DKIM, DMARC, CAA, SRV y subdominios existentes, con sus TTL.
- Guardar los nameservers actuales y estado DNSSEC/DS.
- Respaldar la web antigua, sus URLs importantes y cualquier formulario o integración aún utilizada.
- Respaldar configuración Nginx/TLS real, CMS y MediaHub en `/var/lib/cisnenegro-cms`, y Pasaporte en `/var/lib/cisnenegro-club/club.db`. Verificar restauración temporal.
- Mantener activos Squarespace, dominio y correo durante la transición. Comprobar si Workspace se factura mediante Squarespace antes de cancelar cualquier suscripción.
- Si el proveedor lo permite, reducir el TTL de los registros web a 300 segundos con antelación suficiente para que caduque el TTL anterior, idealmente 24 horas antes.

Salida: DNS y servicios recuperables; buzones y registros de correo identificados.

## 3. Preparar el VPS para el dominio definitivo

Responsable: equipo técnico.

La aplicación usa Nginx y servicios Python con SQLite. Se reutiliza el VPS; no requiere copiarla a un hosting compartido ni reconstruirla en Website Builder.

- Confirmar en Hostinger que la IP del VPS sigue siendo `31.220.63.211`.
- Crear/adaptar el vhost para cisnenegro.mx y www.cisnenegro.mx preservando el CMS, Pasaporte, APIs, biblioteca y configuración vigente. No reemplazar a ciegas el vhost real por la plantilla HTTP antigua del repositorio.
- Proponer `https://www.cisnenegro.mx` como origen canónico. Preparar el cambio de `CMS_ORIGIN`, que actualmente admite un único origen. Coordinar su activación y la redirección del acceso administrativo antiguo para evitar errores 403.
- Preparar certificado TLS para ambos nombres y renovación automática. Se puede emitir previamente mediante validación DNS-01, probar el VPS con resolución local y cambiar después los registros web. Si se usa validación HTTP, coordinar emisión y cambio DNS en la misma ventana.
- Actualizar canonical, OpenGraph, Twitter, datos estructurados y enlaces que apuntan al dominio de pruebas.
- Retirar noindex únicamente de las páginas públicas aprobadas: meta HTML, cabeceras Nginx y cabecera global del CMS; actualizar robots.txt y crear sitemap.xml.
- El CMS sirve revisiones guardadas en SQLite. Regenerar los documentos públicos desde el contenido publicado vigente; no publicar borradores pendientes accidentalmente.
- Conservar exclusión de indexación y autenticación en CMS/admin. Separar de la web comercial las rutas de propuesta, análisis, proyecto y estrategia; noindex no equivale a control de acceso.
- Confirmar versión y contenido que se lanzarán: este plan conecta la web vigente; no implica publicar automáticamente las variantes de hero, propuestas o borradores locales.

Salida: HTTPS, rutas y aplicación probados antes del cambio público; copia de reversión disponible.

## 4. Conectar la web desde el DNS actual

Responsable: administrador actual del DNS, acompañado por el equipo técnico.

Modificar solo los registros de la web, después de confirmar la IP y preparar el VPS:

| Tipo | Nombre | Destino propuesto |
|---|---|---|
| A | @ | 31.220.63.211 |
| A | www | 31.220.63.211 |

- Reemplazar los A anteriores de raíz y el CNAME de www hacia Squarespace. No dejar simultáneamente CNAME y A en www.
- Revisar posibles AAAA incompatibles en esos dos nombres. Conservar registros de otros servicios.
- Mantener íntegros los MX de Google y demás registros de correo y verificación.
- Mantener ambos servidores disponibles mientras caduquen las cachés. Reservar hasta 24–48 horas de observación de propagación; no interpretar el TTL reducido como garantía de actualización inmediata para todos.

Hostinger documenta el uso de registros A para conectar un dominio externo a un VPS, sin transferir primero su registro: [guía oficial para VPS](https://www.hostinger.com/support/1583227-how-to-point-a-domain-to-your-vps-at-hostinger/).

## 5. Comprobar la web antes de transferir

Responsables: equipo técnico y un responsable de Cisne Negro.

- Abrir raíz y www con HTTP y HTTPS; terminar en la dirección canónica con certificado válido y sin bucles.
- Comprobar portada, menú, fotografías, videos y enlaces de contacto desde celular y escritorio.
- Probar registro/ingreso del Pasaporte, visitas, sellos/canjes y NPS con una cuenta de prueba controlada.
- Probar ingreso, edición, MediaHub y publicación del CMS, verificando persistencia de datos y permisos.
- Confirmar las cuentas existentes. Las sesiones/cookies pertenecen al host: los usuarios tendrán que volver a iniciar sesión; los datos deben conservarse en las mismas bases.
- El cliente prueba envío y recepción de su correo con cuentas externas.
- Verificar que las páginas públicas admitan indexación y las rutas internas sigan protegidas.

Salida: web y correo funcionan en .mx antes de mover la administración del registro.

## 6. Llevar la gestión DNS a Hostinger sin perder el correo

Responsable: equipo técnico y administrador del dominio.

- En hPanel: VPS → Administrar el VPS → DNS Manager → añadir cisnenegro.mx. Usar los nameservers exactos que asigne el panel, no valores genéricos de otra cuenta o producto.
- Reproducir la zona completa del paso 2 incorporando los nuevos registros A del paso 4; mantener Google como destino del correo.
- Comprobar que la zona de destino puede servir todos los registros antes de delegar. Si el panel exige primero verificar el dominio, resolver el procedimiento con soporte y preparar la carga; no cambiar a una zona vacía.
- Cambiar los nameservers en el proveedor actual solo cuando el DNS de destino esté listo. Si DNSSEC estuviera activo, coordinar DS y claves para evitar respuestas inválidas; no dejar un DS del proveedor anterior.
- Volver a probar web y correo y esperar estabilidad de la delegación antes del siguiente paso.

Esta etapa evita depender del DNS del proveedor anterior después de la transferencia. Ruta documentada en la [guía de DNS para VPS de Hostinger](https://www.hostinger.com/support/1583227-how-to-point-a-domain-to-your-vps-at-hostinger/).

## 7. Transferir el registro a la cuenta Hostinger de Roger

Responsables: titular/proveedor actual y Roger.

- Desbloquear la transferencia cuando corresponda y solicitar el código Auth/EPP en el panel que realmente administra el dominio.
- Si se confirma Squarespace: abrir el dominio, desactivar Domain Lock si aparece y solicitar Request transfer code; el código se envía al contacto registrado. [Procedimiento de Squarespace](https://support.squarespace.com/hc/en-us/articles/205812338-Transferring-a-domain-away-from-Squarespace).
- En Hostinger, entrar a Dominios → Transferencias → Transferir a Hostinger; introducir `cisnenegro.mx`, revisar elegibilidad y el importe específico antes de pagar.
- Introducir Auth/EPP y seleccionar conservar los nameservers ya validados del paso 6. No sustituirlos por una configuración automática que cambie los MX.
- El titular confirma los correos necesarios. Revisar el estado hasta completado y verificar dominio en la cuenta correcta, contactos, nameservers, fecha de vencimiento y renovación.
- Mantener web y DNS estables durante el trámite. Hostinger indica que la transferencia puede tardar hasta siete días y bloquear cambios de nameservers mientras está en curso. Su guía requiere confirmar el comportamiento de renovación de ccTLD no listados; .mx no aparece en esa tabla. [Guía de transferencia](https://www.hostinger.com/support/1583436-how-to-transfer-a-domain-to-hostinger/).
- Para planificación, reservar de una a dos semanas o hasta 15 días si aplica el flujo de Squarespace, sujeto a validaciones del proveedor y del registro. [Plazos de Squarespace](https://support.squarespace.com/hc/en-us/articles/115011719247-Domain-transfer-timing).

Si Hostinger rechaza temporalmente la transferencia .mx, la web puede seguir funcionando en el VPS con el DNS configurado. Se resuelve el registro por separado, sin deshacer una web ya validada.

## 8. Cerrar el lanzamiento y conservar continuidad

Responsables: equipo técnico, Roger y Cisne Negro.

- Redirigir permanentemente las URLs públicas de `cisnenegro.softvibes.art` a sus equivalentes canónicos, conservando ruta y parámetros. Resolver las rutas internas/comerciales de forma separada, sin una redirección indiscriminada.
- Mapear páginas antiguas de cisnenegro.mx a destinos pertinentes; evitar enviar todas las URLs antiguas a la portada.
- Regenerar QR del menú con `https://www.cisnenegro.mx/menu/`. Conservar la redirección del enlace anterior para que los impresos existentes funcionen.
- Verificar Search Console, enviar sitemap y actualizar enlaces en Google Business Profile/redes cuando se autorice su edición.
- Confirmar certificado y renovación, respaldos, logs, errores 404, correo y CMS durante al menos 48 horas después de cada cambio de infraestructura.
- Mantener la web anterior recuperable unos días. Cancelar únicamente el servicio que ya no se utiliza cuando dominio, DNS, web y correo estén confirmados; mantener Workspace si continúa prestando el correo.

## Reversión

- Si falla el sitio tras el paso 4, restaurar los A/CNAME web guardados, conservando MX y TXT; los cambios están sujetos a caché DNS. La web antigua debe seguir activa.
- Si falla el VPS o el acceso al CMS, restaurar su configuración/origen y artefactos anteriores. No sobrescribir las bases de datos con copias antiguas si hubo altas o visitas nuevas: evaluar y preservar esas operaciones primero.
- Si el cambio de nameservers del paso 6 falla, volver a los NS anteriores mientras la zona antigua siga activa y comprobar DNSSEC. No iniciar transferencia del registro hasta estabilizarlo.
- Durante una transferencia, el retorno de nameservers puede estar limitado; por eso el plan valida la zona antes de iniciarla.

## Estimación y costos

Preparación técnica: estimar uno a dos días de trabajo una vez obtenidos accesos y aprobada la versión pública, sujeto a los ajustes del CMS y SEO. Cambio web y verificación: una ventana coordinada más observación de propagación. Transferencia del registro: proceso independiente de varios días; no prometer fecha exacta hasta verificar .mx en el panel.

No se requiere otro hosting para esta arquitectura. Confirmar capacidad del VPS existente, costo de transferencia/renovación del dominio y mantenimiento de Google Workspace. El precio promocional de un dominio nuevo no es una cotización de transferencia.

Para TLS en este VPS: [opciones de SSL en Hostinger](https://www.hostinger.com/support/6360129-how-to-install-ssl-on-vps-at-hostinger/) y [validación DNS-01 de Let's Encrypt](https://letsencrypt.org/docs/challenge-types/).
