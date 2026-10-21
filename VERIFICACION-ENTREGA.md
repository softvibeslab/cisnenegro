# Verificación de entrega · 2026-10-21

- 51 pruebas Python de la aplicación vigente aprobadas sobre la copia exportada: CMS, assets, gateway, operación, importación y configuración.
- 16 pruebas Python de configuración y despliegue aprobadas.
- 11 verificaciones JavaScript de seguridad frontend y caché aprobadas.
- Verificación de disponibilidad: oferta de Vuelo oculta rechazada, carrito revalidado y productos individuales conservados. El caso de compatibilidad usa explícitamente una copia sin el indicador, independiente de la semilla actual.
- Instalador del ecosistema: ocho verificaciones en carpetas temporales, incluyendo previsualización, integridad, instalación, rechazo de sobrescritura y rutas inválidas.
- Manual público regenerado: HTML de 20 capítulos/50 enlaces, PDF de 32 páginas y cinco capturas públicas verificadas por hash. Sin capturas autenticadas.
- Exportación del catálogo público de revisión 8 e imágenes de MediaHub por HTTPS. Código de producción sin modificar.
- Auditoría de exclusiones, rutas personales, credenciales conocidas y archivos grandes antes del primer commit. No se incorpora historial de otros clientes.

Las pruebas operativas usan datos ficticios y bases temporales. No se crearon pedidos ni transacciones en producción.
