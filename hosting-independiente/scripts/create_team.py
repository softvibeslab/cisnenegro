#!/usr/bin/env python3
"""Crear personal en una instalación nueva; PIN leído sin mostrarlo en pantalla."""
import argparse
import getpass
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--data-dir', type=Path, required=True)
parser.add_argument('--usuario', required=True)
parser.add_argument('--nombre', required=True)
parser.add_argument('--rol', choices=('admin', 'mesero'), default='admin')
args = parser.parse_args()
data = args.data_dir.expanduser().resolve()
if not data.is_dir() or data == BASE or BASE in data.parents:
    parser.error('Usa la carpeta persistente existente fuera del paquete.')
os.environ['CLUB_DB'] = str(data / 'club.db')
sys.path.insert(0, str(BASE / 'backend'))
import club_server
pin = getpass.getpass('PIN de seis dígitos: ')
if pin != getpass.getpass('Repite el PIN: '):
    parser.error('Los PIN no coinciden.')
club_server.init_db()
with club_server.db() as con:
    club_server.crear_staff(con, args.nombre, args.usuario, args.rol, pin)
print('Cuenta de equipo creada. PIN no registrado en logs.')
