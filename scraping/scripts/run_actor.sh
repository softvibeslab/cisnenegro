#!/bin/zsh
# Uso: run_actor.sh <actorId> <input.json> <salida.json>
# Ejecuta un actor de Apify y guarda todos los items del dataset en <salida.json>.
set -e
cd "$(dirname "$0")/.."
RUN=$(apify call "$1" -f "$2" --json 2>/dev/null)
DS=$(echo "$RUN" | python3 -c "import json,sys;print(json.load(sys.stdin)['defaultDatasetId'])")
apify datasets get-items "$DS" --format json > "$3"
python3 -c "import json;print('$1 ->', len(json.load(open('$3'))), 'items ->', '$3')"
