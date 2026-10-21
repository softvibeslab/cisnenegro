#!/usr/bin/env python3
"""Prepara un perfil Hermes dedicado; vista previa por defecto, sin gateway."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PROFILE = 'cisne-negro'
HERE = Path(__file__).resolve().parent


def profile_root(env):
    native = Path.home() / '.hermes'
    configured = Path(env.get('HERMES_HOME', native)).expanduser()
    try:
        configured.resolve().relative_to(native.resolve())
        return native
    except ValueError:
        return configured.parent.parent if configured.parent.name == 'profiles' else configured


def command(binary, arguments, env):
    result = subprocess.run([binary, *arguments], env=env, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError('Hermes no completó la preparación. Revisa el perfil con su CLI; no se inició ningún gateway.')


def install(env, apply=False, runner=command):
    root = profile_root(env)
    destination = root / 'profiles' / PROFILE
    binary = env.get('HERMES_BIN') or shutil.which('hermes')
    if not binary:
        raise RuntimeError('Instala Hermes o define HERMES_BIN con su ejecutable.')
    repo = None
    if env.get('CISNE_REPO_PATH'):
        repo = Path(env['CISNE_REPO_PATH']).expanduser().resolve()
        if not (repo / 'hosting-independiente').is_dir() or not (repo / 'agente-cisne' / 'instrucciones.md').is_file():
            raise RuntimeError('CISNE_REPO_PATH debe apuntar al repositorio independiente de Cisne Negro.')
    if destination.is_symlink():
        raise RuntimeError('El destino del perfil no puede ser un enlace simbólico.')
    fresh = not destination.exists()
    report = {'profile': PROFILE, 'destination': str(destination), 'apply': apply, 'create': fresh,
              'configure_cwd': bool(fresh and repo), 'gateway_started': False, 'copied': [], 'preserved': []}
    targets = [(HERE / 'SOUL.md', destination / 'SOUL.md'), (HERE / 'skills' / 'cisne-cms', destination / 'skills' / 'cisne-cms')]
    for _, target in targets:
        report['preserved' if target.exists() else 'copied'].append(str(target.relative_to(destination)))
    if not apply:
        return report
    run_env = dict(env)
    run_env['HERMES_HOME'] = str(root)
    if fresh:
        runner(binary, ['profile', 'create', PROFILE, '--no-skills', '--no-alias', '--description', 'Cisne Negro: contenido CMS, imágenes de cerveza, diseño y desarrollo.'], run_env)
        if not destination.is_dir():
            raise RuntimeError('Hermes no creó el perfil en la ubicación prevista; no se copiaron archivos.')
        # Solo la plantilla creada en ESTA ejecución se aparta. Nunca toca un SOUL preexistente.
        seeded = destination / 'SOUL.md'
        if seeded.exists():
            seeded.rename(destination / 'SOUL.hermes-default.md')
    for source, target in targets:
        if target.exists() or target.is_symlink():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            with target.open('x', encoding='utf-8') as stream:
                stream.write(source.read_text(encoding='utf-8'))
    if fresh and repo:
        runner(binary, ['--profile', PROFILE, 'config', 'set', 'terminal.cwd', str(repo)], run_env)
    report['next'] = 'Configura proveedor/modelo y accesos privados; después prueba la CLI antes de habilitar Telegram.'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Crear perfil y copiar solo archivos ausentes')
    args = parser.parse_args()
    try:
        print(json.dumps(install(os.environ, args.install), ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, OSError, subprocess.SubprocessError):
        print(json.dumps({'ok': False, 'error': 'No se pudo preparar el perfil. Comprueba Hermes, permisos y CISNE_REPO_PATH; no se sobrescribe configuración existente.'}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
