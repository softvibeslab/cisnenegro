# Marca, experiencia y desarrollo

## Identidad útil

Cisne Negro es una cervecería mexicana independiente con microcervecería, taproom y comedor en Pachuca. El lenguaje documentado es cercano, local, incluyente y sin pretensiones: «¡Cuéntalo en el Cisne!» y «Cervecería Independiente. Bebe Local.». Cerveza, cocina, oficio y convivencia forman una misma experiencia.

Hablar con claridad; explicar estilos sin elitismo. El humor puede acompañar los nombres y el ambiente, pero no sustituye información útil. No inventar anécdotas de fundadores o cervezas. Horarios, dirección, teléfonos, fechas y precios deben consultarse en el contenido vigente antes de responder o editar.

La estrategia propone cuatro pilares: **El Barril** (oficio y producto), **La Mesa** (cocina y maridaje), **La Parvada** (comunidad) y **La Agenda** (eventos y Pachuca). Cada pieza debe tener una intención dentro de descubrir → considerar → visitar → regresar → recomendar y un siguiente paso verificable. Son un marco de trabajo, no un calendario aprobado ni una promesa de resultados.

El plan distingue el CMS operativo de un Content Hub propuesto. No anunciar programación de redes, analítica completa o automatizaciones sociales sin comprobar que las herramientas del entorno las implementen.

## Sistema visual «Neón y tinta»

| Uso | Valor actual en CSS |
|---|---|
| Fondo tinta | `#0E0D0B` |
| Superficies carbón / bordes | `#191714` / `#2B2823` |
| Hueso / texto secundario | `#F3EDE2` / `#A39B8E` |
| Ámbar del neón | `#F2C97D` |
| Naranja de acciones y precios | `#FF5A1F` |
| Perfil lupulado | `#B7C46A` |
| Titulares | Big Shoulders Display 800/900 |
| Texto | Manrope |
| Datos técnicos | JetBrains Mono |

Conservar mascota, pluma y logotipo existentes; no redibujarlos o sustituirlos incidentalmente. Usar fotografías reales del negocio y sus productos. Las ilustraciones editoriales deben identificarse como tales y mantener la identidad específica de cada cerveza.

Diseñar primero para celular: nombre, estilo, precio y acción legibles; botones táctiles; foco visible; alternativas de texto; imágenes dimensionadas. En el hero conservar imagen de respaldo, pausa y preferencias de movimiento reducido. Revisar contraste y contenido real en vista móvil y escritorio. Los tokens exactos se consultan en el CSS vigente si cambian.

## Aplicación que se desarrolla

La versión activa del repositorio está en `hosting-independiente/`: interfaz HTML/CSS/JavaScript, CMS Flask/Python, SQLite, MediaHub con Pillow y FFmpeg, servidor Gunicorn y contenedor detrás del proxy. El README incluye arranque local y versiones fijadas. No asumir un framework de frontend distinto ni instalarlo para un ajuste editorial.

El contenido persistente y los medios no son el código desplegable. Los cambios de texto, catálogo, precios e imágenes pertenecen al CMS; los nuevos componentes, funciones y estilos pertenecen al repositorio. Mantener separados CMS y operación del club: una reversión editorial no revierte ventas, socios o pedidos.

Una tarea de desarrollo se cierra con diff revisable, comprobaciones pertinentes y resultado visual cuando cambia interfaz. Publicar código requiere autorización de despliegue para ese trabajo. El permiso del agente para guardar contenido no incluye shell remoto, DNS, usuarios administrativos o despliegues.

Fuentes: [base histórica](../../01-base-conocimientos.md), [estrategia](../../estrategia-contenido/08-plan-estrategia-contenido-y-content-hub.md), [consultoría](../../05-consultoria-beervibes-90-dias.md), [diseño](../../sitio/DESIGN.md), [CSS actual](../../hosting-independiente/sitio/assets/css/landing.css) y [aplicación](../../hosting-independiente/README.md).
