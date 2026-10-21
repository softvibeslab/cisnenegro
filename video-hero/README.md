# Una vuelta por el Cisne — propuesta de hero V2

Vista previa local para revisión. La landing de `sitio/` no se ha modificado.

- Abrir `index.html` para reproducir el video o activar la simulación del texto del hero.
- Video: `cisne-negro-hero-v2.mp4`, 28 segundos, 1920×1080, 24 fps, H.264/YUV420P, sin pista de audio y con inicio rápido (`faststart`).
- Recorrido: neón original → grifos → cerveza servida → degustación → dos pintas a cámara → plática con cerveza → brindis entre amigos → cuatro pintas → brindis de noche → taproom lleno → neón original.
- Material real del archivo de esta cervecería: un clip de cerveza servida y fotografías con movimiento suave. Sin imágenes de stock, escenas generadas, voz, música ni rótulos incrustados.
- Los originales tienen distintas resoluciones; 1080p es el formato de entrega, no la resolución nativa de todos los planos. Los clips verticales se reencuadraron para 16:9.
- La apertura y el cierre regresan al mismo encuadre de `sitio/assets/img/lugar/neon.jpg`. Las uniones entre planos duran 9 cuadros (375 ms).

`fuentes-y-montaje-v2.json` documenta las rutas originales, enlaces públicos disponibles, recortes, tiempos y resultado de verificación.

## Reproducir el render

Requiere Python 3, FFmpeg y FFprobe instalados. No usa paquetes adicionales de Python.

```sh
python3 video-hero/render.py
```

Ejecutar desde la raíz de `cisne-negro-cerveceria`. Los originales de `contenido/` deben seguir disponibles localmente. El script valida los encuadres y el resultado (duración, dimensiones, cuadros, códec, ausencia de audio y decodificación completa). `revision/` guarda los planos intermedios y contactos de revisión, fuera de Git.

Para abrir la vista previa por HTTP local:

```sh
python3 -m http.server 8766 --bind 127.0.0.1
```

Abrir <http://127.0.0.1:8766/video-hero/>. La página también puede abrirse directamente como archivo local. El texto superpuesto es una simulación para evaluar legibilidad; la integración definitiva en la landing queda para después de revisar el video.

## Selección V2

La cerveza y la experiencia de compartirla son el centro de esta versión: producto, servicio, degustación, conversación y ambiente del taproom. `seleccion-v2.jpg` muestra los nueve encuadres fotográficos únicos. La V1 y sus fuentes se conservan para comparación (`cisne-negro-hero-v1.mp4`, `fuentes-y-montaje-v1.json`, `render-v1.py`).
