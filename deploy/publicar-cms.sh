#!/bin/zsh
# Actualización del CMS ya provisionado; conserva el contenido y todas las rutas ajenas.
set -eu
cd "$(dirname "$0")/.."
KEY=~/.ssh/rovi_vps_deploy
HOST=root@31.220.63.211
rsync -az -e "ssh -i $KEY" backend/cms_server.py backend/cms_content.py backend/cms_media.py backend/import_cms_media.py backend/requirements-cms.txt $HOST:/opt/cisnenegro-cms/
rsync -az -e "ssh -i $KEY" sitio/cms/ $HOST:/var/www/cisnenegro/cms/
rsync -az -e "ssh -i $KEY" sitio/assets/js/admin.js sitio/assets/js/landing.js sitio/assets/js/menu.js sitio/assets/js/hero-video.js $HOST:/var/www/cisnenegro/assets/js/
rsync -az -e "ssh -i $KEY" sitio/assets/css/hero-video.css $HOST:/var/www/cisnenegro/assets/css/
ssh -i "$KEY" "$HOST" 'systemctl restart cisnenegro-cms && systemctl is-active --quiet cisnenegro-cms'
curl --fail --silent --retry 5 --retry-connrefused --retry-delay 1 --output /dev/null https://cisnenegro.softvibes.art/cms/
echo 'CMS publicado; contenido y medios conservados.'
