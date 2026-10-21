#!/bin/sh
# Sólo recarga nginx al renovar certificados de esta instalación.
case " ${RENEWED_DOMAINS:-} " in
  *" cisne.softvibes.art "*|*" cisnenegro.mx "*|*" www.cisnenegro.mx "*)
    nginx -t && systemctl reload nginx
    ;;
esac
