# Ecosistema de creación de sitios · Cisne Negro

Paquete portable de instrucciones, herramientas y evidencia del trabajo de Cisne Negro. Se preparó el 21 de octubre de 2026 para acompañar el código del sitio. No contiene cuentas, claves, cookies, datos de clientes, configuración global del equipo ni ejecutables de terceros.

## Qué incluye

| Carpeta | Qué contiene | Procedencia |
|---|---|---|
| `skills/imagegen/` | Skill completa de generación de imágenes, referencias y scripts auxiliares | Copia exacta de la skill instalada de OpenAI, con Apache-2.0 |
| `skills/sitios-inventario/` | Elegir una base antes de crear un sitio; proteger datos de otros clientes | Instrucción nueva portable basada en el método documentado del proyecto; no es la copia de `landing-inventory-first` |
| `skills/sitios-desarrollo-qa/` | Construcción, CMS, medios, pruebas y entrega de un sitio | Instrucción nueva escrita a partir del código y verificaciones de Cisne Negro |
| `skills/documentos-pdf/` | Crear y revisar propuestas y manuales PDF | Instrucción nueva portable; no redistribuye el plugin PDF de Codex |
| `herramientas.md` | Stack, versiones, comandos y límites de portabilidad | Evidencia local del proyecto |
| `procedencia.md` | Qué se usó, qué solo se propuso y condiciones de los archivos | Registro verificable sin asumir un historial completo |
| `manifest.json` | Inventario, evidencias y SHA-256 de cada archivo del paquete | Generado al preparar esta versión |
| `scripts/install_skills.py` | Instalación opcional en una carpeta de skills | Python estándar; por defecto solo previsualiza y nunca sobrescribe |

Las tres skills nuevas facilitan repetir el proceso. **No son pruebas de que se invocaran con esos nombres durante el desarrollo.** El manifiesto separa las habilidades confirmadas de las herramientas verificadas y de las menciones en planes.

## Usarlo con un asistente

1. Mantener este paquete junto al repositorio para conservar los enlaces a las evidencias.
2. Leer `herramientas.md` y las instrucciones del proyecto antes de ejecutar comandos.
3. Pedir al asistente que use `sitios-inventario` al comenzar un proyecto nuevo, `sitios-desarrollo-qa` para implementarlo y `documentos-pdf` para documentos. La skill `imagegen` requiere un asistente con esa capacidad o su alternativa CLI expresamente elegida.
4. Mantener las credenciales en el gestor privado del entorno de destino. Las skills son instrucciones; no transfieren autorizaciones, sesiones ni acceso a conectores.

Instalación opcional para Codex, ejecutada desde esta carpeta:

```sh
# Muestra lo que copiaría; aún no modifica la carpeta de destino.
python3 scripts/install_skills.py --dest "$HOME/.codex/skills"

# Ejecutar deliberadamente para instalar. Falla si una skill ya existe.
python3 scripts/install_skills.py --dest "$HOME/.codex/skills" --install

# También se puede elegir solo una skill nueva.
python3 scripts/install_skills.py --dest "$HOME/.codex/skills" --skill sitios-desarrollo-qa --install
```

El instalador verifica los archivos contra `manifest.json` antes de copiarlos. Si `imagegen` ya viene con tu entorno, instala únicamente las skills nuevas con varias opciones `--skill`; no reemplaces la copia del sistema. Para otro asistente, configura su carpeta de skills conforme a sus propias instrucciones o lee los `SKILL.md` directamente.

## Ejecutar el sitio

Este paquete de skills no sustituye la aplicación. La versión desplegable está en [`../hosting-independiente/`](../hosting-independiente/README.md). Desde la raíz del repositorio:

```sh
cd hosting-independiente
./iniciar-local.sh
```

Los datos locales se generan fuera de esa carpeta; no se incluyen usuarios ni bases de producción. La configuración y los pasos de despliegue están en [`deploy/README.md`](../hosting-independiente/deploy/README.md). El código necesita Python, procesamiento de medios y almacenamiento persistente; no basta copiarlo como archivos estáticos a `public_html`.

## Licencias y alcance

La licencia Apache-2.0 incluida en `skills/imagegen/LICENSE.txt` corresponde a esa skill. No se asigna aquí una licencia pública general a la marca, fotografías, datos o código del proyecto, ni a los nuevos textos de Softvibes. La publicación en un repositorio no equivale por sí misma a una licencia de esos materiales. Ver el inventario de procedencia antes de reutilizar recursos de terceros.

El ZIP, si acompaña esta carpeta, es una distribución del paquete; el manifiesto corresponde a los archivos descomprimidos y no incluye su propio hash.
