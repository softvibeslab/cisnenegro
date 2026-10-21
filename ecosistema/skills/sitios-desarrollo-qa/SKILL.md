---
name: sitios-desarrollo-qa
description: Construir y verificar un sitio con contenido editable, medios y despliegue documentado, usando la arquitectura de Cisne Negro como referencia técnica.
---

# Desarrollo, contenido y verificación

Skill nueva para este paquete, basada en el código de Cisne Negro. Los nombres de rutas y herramientas se adaptan al proyecto actual; no se traslada contenido de un cliente a otro.

## Entrada

Leer la petición, instrucciones locales, README, configuración de dependencias y estado Git. Identificar qué versión se sirve realmente y cuál es la fuente editable. Cuando sea un proyecto nuevo, completar primero `sitios-inventario` o un inventario equivalente autorizado.

## Trabajo

1. **Definir el recorrido.** Identificar audiencia, llamada a la acción, páginas, componentes y contenido confirmado. Mantener una lista de dudas editoriales; no inventar precios, reseñas, notas de producto o contactos.
2. **Implementar una primera versión completa.** Usar el stack existente salvo necesidad justificada. Conservar identidad visual, rutas coherentes, etiquetas accesibles, comportamiento móvil y recursos optimizados. Cambiar solo archivos pertinentes y respetar modificaciones previas del usuario.
3. **Separar contenido y operación.** En un CMS, un borrador no debe alterar la web ni los precios operativos hasta publicar. Conservar versiones y permitir restaurar. Mantener los importes históricos de pedidos aunque cambie el catálogo.
4. **Tratar medios como datos.** Guardar origen, autoría o permiso, título y texto alternativo. Distinguir fotografía real, ilustración generada y etiqueta oficial. Validar formato/tamaño, generar derivados, proteger borradores y servir públicamente solo lo publicado. No usar la imagen de otro producto como sustituto silencioso.
5. **Proteger los accesos.** Usar configuración externa para secretos, roles claros, sesiones y protección CSRF. Mantener bases y copias fuera del código público. Crear cuentas locales independientes para ensayar; no importar datos personales reales por comodidad.
6. **Verificar según el cambio.** Ejecutar pruebas existentes relevantes para lógica, precios, permisos, publicación o persistencia. Revisar el flujo afectado en navegador, en tamaños móvil y escritorio. En un cambio visual pequeño, comprobación de sintaxis y revisión visual pueden ser suficientes; no escribir pruebas que repitan la implementación.
7. **Preparar una entrega reproducible.** Documentar instalación, variables de ejemplo, almacenamiento, versión de dependencias, comprobación de salud y restauración. Eliminar rutas personales innecesarias de las instrucciones. No incluir entornos virtuales, cachés, tokens o sesiones en el paquete.
8. **Publicar dentro del alcance autorizado.** Revisar destino y diff, preparar respaldo pertinente y aplicar el cambio mínimo. Verificar la URL real y una acción principal después. Si la publicación no está autorizada, dejar el resultado concreto listo para revisión.

## Pruebas útiles para una aplicación como Cisne Negro

- Publicación: borrador independiente, salida renderizada, versión y restauración.
- Catálogo: visibilidad, disponibilidad, cantidades, total y precio histórico.
- Operación: pedido, cuenta, cobro y corte, con permisos por rol.
- MediaHub: imagen/video, procesamiento, acceso privado y público correcto.
- Despliegue: salud, orígenes, HTTPS, reinicio con persistencia y restauración ensayada.

Seleccionar solo las que correspondan; no ejecutar escrituras de prueba en producción si un entorno aislado resuelve la verificación.

## Entrega al usuario

Explicar qué quedó listo, dónde verlo, cómo se comprobó y los límites reales. Diferenciar local, preparado y publicado. Evitar afirmar que un despliegue o prueba se realizó sin evidencia de su ejecución.
