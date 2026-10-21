# Cisne Negro — Backlog

Tareas que dependen del cliente. No bloquean las fases actuales: se trabaja con los datos públicos (`scraping/dataset.json`) y se incorporan cuando lleguen.

| # | Tarea | Qué desbloquea | Cómo lo hace el cliente | Estado |
|---|---|---|---|---|
| B1 | **Exportación oficial de Meta** | Facebook completo, los 45 posts de IG anteriores a nov 2023 y las historias destacadas (Menú, Horario, #vacióbarril) | Instagram o Facebook → Centro de cuentas → Tu información → Descargar tu información → formato **JSON**, calidad **alta** | ⏳ Pendiente |
| B2 | **Acceso de socio en Meta Business Suite** | Alcance, guardados, compartidos y datos del público | Business Suite → Configuración → Socios → agregar a Softvibes | ⏳ Pendiente |
| B3 | **Acceso de administrador al Perfil de Empresa en Google** | Búsquedas, llamadas y rutas; responder reseñas (0 de 69 respondidas); cambiar la categoría a Cervecería/Brewpub | Perfil de Empresa → Configuración → Personas y acceso → agregar como administrador | ⏳ Pendiente |
| B4 | **Confirmar si tienen cuenta de Threads** | Saber si hay que incluirla en el inventario y el calendario | Preguntarle al cliente | ⏳ Pendiente |

## Al recibir cada tarea
- **B1:** guardar el ZIP en `scraping/raw/meta-export-AAAAMMDD/`, extraer los medios a `contenido/facebook/` y `contenido/instagram/`, y volver a correr `scripts/normalize.py` con el soporte para el export.
- **B2 y B3:** capturar las métricas de 90 días en `analisis/` y actualizar la línea base de KPIs en la propuesta (§5).
