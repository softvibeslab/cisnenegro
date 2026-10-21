#!/bin/sh
# Respaldo diario de la base del club (cron 03:30). Conserva 30 días.
set -e
D=/var/backups/cisnenegro-club
mkdir -p "$D"
python3 -c "import sqlite3,sys;s=sqlite3.connect('/var/lib/cisnenegro-club/club.db');d=sqlite3.connect(sys.argv[1]);s.backup(d);d.close()" "$D/club-$(date +%F).db"
find "$D" -name 'club-*.db' -mtime +30 -delete
