#!/usr/bin/env python3
"""Render local y reproducible del loop; requiere ffmpeg y ffprobe en PATH."""
import concurrent.futures
import json
import math
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = HERE / 'revision' / 'planos-v2'
FPS = 24
TRANSITION = 9  # cuadros (375 ms)

SHOTS = [
    dict(name='El neón', source='sitio/assets/img/lugar/neon.jpg', frames=84,
         crop=[0, 40, 1600, 900], zoom=[1, 1.035]),
    dict(name='En los grifos', source='contenido/instagram/posts/2025-01-23_DFL_h-KxPsp/01.jpg',
         frames=60, crop=[0, 65, 1440, 810], zoom=[1.015, 1.045]),
    dict(name='Del barril al vaso', source='contenido/tiktok/20240727_7396425455320009989.mp4',
         frames=72, crop=[0, 340, 576, 324], start=25.65, speed=1),
    dict(name='Una degustación', source='contenido/google-maps/fotos/003.jpg',
         frames=66, crop=[0, 165, 1374, 772], zoom=[1, 1.035],
         source_collection='Fotos públicas del Perfil de Empresa de Cisne Negro en Google Maps, descargadas en contenido/'),
    dict(name='Una para cada gusto', source='contenido/instagram/posts/2025-11-15_DRGG0PMkqFT/01.jpg',
         frames=60, crop=[0, 180, 1052, 592], zoom=[1, 1.022]),
    dict(name='La plática y la cerveza', source='contenido/instagram/posts/2026-04-09_DW7L_1fDjE9/01.jpg',
         frames=66, crop=[0, 400, 1440, 810], zoom=[1.03, 1]),
    dict(name='Entre amigos', source='contenido/instagram/posts/2024-12-01_DDBCnhARpjm/01.jpg',
         frames=54, crop=[0, 55, 1068, 600], zoom=[1, 1.025]),
    dict(name='Cuatro pintas, un brindis', source='contenido/instagram/posts/2024-10-16_DBM4XOjxsZY/01.jpg',
         frames=60, crop=[0, 370, 1440, 810], zoom=[1.035, 1.005], saturation=.93),
    dict(name='El brindis', source='contenido/instagram/posts/2025-02-16_DGHi1ozxMd8/02.jpg',
         frames=66, crop=[0, 250, 1440, 810], zoom=[1.01, 1.04]),
    dict(name='El taproom se vive', source='contenido/instagram/posts/2025-11-23_DRacrleklrs/03.jpg',
         frames=84, crop=[0, 80, 1440, 810], zoom=[1.035, 1]),
    dict(name='Volver al neón', source='sitio/assets/img/lugar/neon.jpg',
         frames=90, crop=[0, 40, 1600, 900], zoom=[1.035, 1]),
]


def run(args):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:])
    return result.stdout


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))


def render_shot(item):
    index, shot = item
    source = ROOT / shot['source']
    info = probe(source)
    stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
    x, y, w, h = shot['crop']
    assert x >= 0 and y >= 0 and x + w <= stream['width'] and y + h <= stream['height'], shot['name']
    destination = CACHE / f'{index:02d}.mp4'
    n = shot['frames']
    duration = n / FPS
    args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-threads', '2']
    filters = [f'crop={w}:{h}:{x}:{y}']
    if 'start' in shot:
        source_duration = duration * shot['speed']
        assert shot['start'] + source_duration <= float(info['format']['duration']), shot['name']
        args += ['-ss', str(shot['start']), '-t', str(source_duration + .12), '-i', str(source)]
        filters += ['setpts=PTS-STARTPTS']
        if shot.get('interpolate'):
            filters += ['minterpolate=fps=80:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1']
        filters += [f'setpts=PTS/{shot["speed"]}', f'fps={FPS}', 'scale=1920:1080:flags=lanczos', 'tpad=stop_mode=clone:stop_duration=1']
    else:
        args += ['-i', str(source)]
        z0, z1 = shot['zoom']
        ease = f'(0.5-0.5*cos(PI*on/{n-1}))'
        zoom = f'{z0}+({z1-z0})*{ease}'
        filters += ['scale=3840:2160:flags=lanczos',
                    f"zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={n}:s=1920x1080:fps={FPS}"]
    filters += [f'eq=contrast=1.025:brightness=-0.008:saturation={shot.get("saturation", .97)}',
                'scale=in_range=auto:out_range=tv', 'setsar=1', 'format=yuv420p',
                f'settb=1/{FPS}', 'setpts=PTS-STARTPTS']
    args += ['-vf', ','.join(filters), '-frames:v', str(n), '-an', '-c:v', 'libx264',
             '-preset', 'fast', '-crf', '15', '-threads', '2', '-filter_threads', '1',
             '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-movflags', '+faststart', str(destination)]
    run(args)
    print(f'{index+1:02d}/{len(SHOTS)} {shot["name"]}', flush=True)
    return destination


def assemble(clips):
    args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-threads', '2']
    for clip in clips:
        args += ['-i', str(clip)]
    graph = [f'[{i}:v]settb=1/{FPS},setpts=PTS-STARTPTS[v{i}]' for i in range(len(clips))]
    previous = 'v0'
    total_frames = SHOTS[0]['frames']
    for i in range(1, len(clips)):
        offset = (total_frames - TRANSITION) / FPS
        label = f'm{i}'
        graph.append(f'[{previous}][v{i}]xfade=transition=fade:duration={TRANSITION/FPS}:offset={offset}[{label}]')
        previous = label
        total_frames += SHOTS[i]['frames'] - TRANSITION
    destination = HERE / 'cisne-negro-hero-v2.mp4'
    args += ['-filter_complex_threads', '1', '-filter_complex', ';'.join(graph), '-map', f'[{previous}]',
             '-frames:v', str(total_frames), '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '22',
             '-profile:v', 'high', '-level:v', '4.1', '-pix_fmt', 'yuv420p', '-threads', '4',
             '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv',
             '-movflags', '+faststart', str(destination)]
    print('Uniendo planos y preparando MP4…', flush=True)
    run(args)
    info = probe(destination)
    stream = info['streams'][0]
    assert len(info['streams']) == 1 and stream['codec_type'] == 'video', 'El hero debe quedar sin pista de audio'
    assert (stream['width'], stream['height']) == (1920, 1080)
    assert stream['pix_fmt'] == 'yuv420p' and stream['codec_name'] == 'h264', stream
    assert int(stream['nb_frames']) == total_frames, (stream['nb_frames'], total_frames)
    assert math.isclose(float(info['format']['duration']), total_frames / FPS, abs_tol=.05)
    run(['ffmpeg', '-v', 'error', '-i', str(destination), '-f', 'null', '-'])
    cursor = 0
    manifest = []
    for index, shot in enumerate(SHOTS):
        item = dict(shot, timeline_start=cursor / FPS)
        path = ROOT / shot['source']
        meta = path.parent / 'meta.json'
        if meta.exists():
            item['source_url'] = json.loads(meta.read_text()).get('url')
        elif 'tiktok' in shot['source']:
            item['source_url'] = 'https://www.tiktok.com/@cisnenegro.mx/video/' + path.stem.split('_')[-1]
        manifest.append(item)
        cursor += shot['frames'] - (TRANSITION if index < len(SHOTS)-1 else 0)
    report = dict(duration=total_frames / FPS, width=1920, height=1080, fps=FPS,
                  codec='h264', audio=False, bytes=destination.stat().st_size,
                  transition_seconds=TRANSITION / FPS, shots=manifest,
                  verification='Dimensiones, cuadros, duración, ausencia de audio y decodificación completa: OK')
    (HERE / 'fuentes-y-montaje-v2.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Listo: {total_frames/FPS:.2f}s, {destination.stat().st_size/1e6:.2f} MB', flush=True)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        clips = list(executor.map(render_shot, enumerate(SHOTS)))
    assemble(clips)


if __name__ == '__main__':
    main()
