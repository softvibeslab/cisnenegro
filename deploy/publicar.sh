#!/bin/zsh
# Publica sitio/ y el backend en el VPS. Uso: deploy/publicar.sh
set -e
cd "$(dirname "$0")/.."
KEY=~/.ssh/rovi_vps_deploy; HOST=root@31.220.63.211
rsync -az -e "ssh -i $KEY" \
  --exclude 'qa/' --exclude 'DESIGN.md' --exclude '*.py' --exclude 'analisis/data.json' --exclude '.DS_Store' \
  sitio/ $HOST:/var/www/cisnenegro/
rsync -az -e "ssh -i $KEY" backend/club_server.py $HOST:/opt/cisnenegro-club/club_server.py
ssh -i $KEY $HOST 'find /var/www/cisnenegro -type d -exec chmod 755 {} + && find /var/www/cisnenegro -type f -exec chmod 644 {} + && systemctl restart cisnenegro-club && systemctl is-active cisnenegro-club'
echo "Publicado en https://cisnenegro.softvibes.art"
# No eliminar rutas remotas: /v2 y otras variantes pueden tener despliegue independiente.
# El contenido publicado del CMS vive en /var/lib/cisnenegro-cms, fuera de sitio/.
# Este comando actualiza plantillas y recursos; el contenido editorial se publica desde /cms/.
