#!/usr/bin/env python3
"""Paquete de código por lista explícita; nunca incluye datos o contraseñas locales."""
import hashlib
from pathlib import Path
import zipfile

BASE = Path(__file__).resolve().parents[1]
OUTPUT = BASE / 'dist'
OUTPUT.mkdir(exist_ok=True)
archive = OUTPUT / 'cisne-negro-hosting.zip'
sources = [BASE / name for name in ('README.md', 'VALIDACION.md', 'DESPLIEGUE.md', 'Dockerfile', '.dockerignore', '.env.example', 'requirements.lock', 'iniciar-local.sh')]
for dirname in ('backend', 'sitio', 'scripts', 'tests', 'deploy'):
    sources.extend(p for p in (BASE / dirname).rglob('*') if p.is_file())
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as out:
    for path in sorted(sources):
        if not path.is_file() or '__pycache__' in path.parts or path.name.startswith('.') and path.name not in {'.env.example', '.dockerignore'}:
            continue
        if path.is_symlink() or path.suffix in {'.pyc', '.db', '.sqlite', '.log'} or path.name.endswith(('-wal', '-shm')):
            continue
        out.write(path, 'cisne-negro-hosting/' + str(path.relative_to(BASE)))
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
(OUTPUT / 'SHA256SUMS').write_text(f'{checksum}  {archive.name}\n')
print(f'{archive}\n{archive.stat().st_size / 1024 / 1024:.1f} MB · SHA256 {checksum}')
