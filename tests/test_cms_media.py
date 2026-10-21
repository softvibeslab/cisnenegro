"""MediaHub integration tests; no network, production database or private credentials.

Run: python3 -m unittest discover -s tests -p 'test_cms_media.py' -v
Pillow is required. Real MP4 tests run when ffmpeg and ffprobe are available.
"""
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import cms_media as media
import import_cms_media as importer


def photo(color='orange', size=(96, 64), fmt='JPEG', exif=None):
    stream = io.BytesIO()
    im = Image.new('RGB', size, color)
    im.save(stream, format=fmt, **({'exif': exif} if exif else {}))
    return stream.getvalue()


class MediaTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cisne-media-test-')
        self.root = Path(self.temp.name)
        self.store = media.MediaStore(self.root / 'library')
        self.jpeg = photo()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def put(self, blob=None, name='cerveza.jpg', metadata=None):
        return self.store.ingest(io.BytesIO(self.jpeg if blob is None else blob), name, metadata)

    def test_persistent_derivatives_and_private_original(self):
        item = self.put(metadata={'title': 'Barrilete', 'alt': 'Pinta de cerveza'})
        self.assertEqual(item['hash'], hashlib.sha256(self.jpeg).hexdigest())
        self.assertEqual((item['width'], item['height']), (96, 64))
        self.assertEqual(item['status'], 'ready')
        self.assertFalse(item['reviewed'])
        self.assertEqual(self.store.path(item['id']).suffix, '.webp')
        with Image.open(self.store.path(item['id'])) as derivative:
            self.assertEqual(derivative.format, 'WEBP')
        with Image.open(self.store.path(item['id'], 'thumb')) as thumbnail:
            self.assertEqual(thumbnail.format, 'JPEG')
        self.assertNotIn('original_ext', item)
        self.assertEqual((self.store.originals / (item['id'] + '.jpg')).read_bytes(), self.jpeg)
        with self.assertRaises(media.MediaError):
            self.store.path(item['id'], 'original')
        self.store.close()
        self.store = media.MediaStore(self.root / 'library')
        self.assertEqual(self.store.get(item['id'])['title'], 'Barrilete')
        self.assertGreater(self.store.usage()['bytes'], len(self.jpeg))

    def test_exif_orientation_and_metadata_removed(self):
        exif = Image.Exif(); exif[274] = 6; exif[315] = 'private camera information'
        item = self.put(photo(exif=exif))
        self.assertEqual((item['width'], item['height']), (64, 96))
        with Image.open(self.store.path(item['id'])) as derivative:
            self.assertEqual(derivative.size, (64, 96))
            self.assertFalse(derivative.getexif())

    def test_png_transparency_and_webp_supported(self):
        buf = io.BytesIO(); Image.new('RGBA', (40, 30), (255, 100, 0, 120)).save(buf, 'PNG')
        item = self.put(buf.getvalue(), 'marca.png')
        with Image.open(self.store.path(item['id'])) as im:
            self.assertEqual(im.mode, 'RGBA')
        self.assertEqual(self.put(photo('red', fmt='WEBP'), 'foto.webp')['kind'], 'image')

    def test_exact_duplicate_keeps_id_metadata_and_storage(self):
        first = self.put(metadata={'title': 'Original aprobado', 'reviewed': True})
        before = self.store.usage()
        again = self.put(name='otro-nombre.jpeg', metadata={'title': 'No sobrescribir'})
        self.assertTrue(again['duplicate'])
        self.assertEqual(first['id'], again['id'])
        self.assertEqual(again['title'], 'Original aprobado')
        self.assertEqual(self.store.usage(), before)
        self.assertEqual(len(list(self.store.originals.iterdir())), 1)

    def test_concurrent_duplicate_is_atomic_and_cleans_files(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.put(), range(4)))
        self.assertEqual(len({r['id'] for r in results}), 1)
        self.assertEqual(sum(not r['duplicate'] for r in results), 1)
        self.assertEqual(len(list(self.store.derivatives.iterdir())), 1)
        self.assertFalse(list(self.store.incoming.iterdir()))

    def test_real_type_and_invalid_contents(self):
        for blob, name in [(self.jpeg, 'bad.png'), (b'<svg onload="alert(1)"></svg>', 'bad.jpg'),
                           (b'not an image', 'bad.webp'), (b'', 'empty.jpg'), (self.jpeg, 'bad.svg')]:
            with self.subTest(name=name), self.assertRaises(media.MediaError):
                self.put(blob, name)
        self.assertEqual(self.store.usage()['items'], 0)
        self.assertFalse(list(self.store.incoming.iterdir()))
        self.assertFalse(list(self.store.derivatives.iterdir()))

    def test_animated_png_rejected(self):
        buf = io.BytesIO()
        Image.new('RGB', (20, 20), 'red').save(buf, format='PNG', save_all=True,
                                              append_images=[Image.new('RGB', (20, 20), 'blue')], duration=100, loop=0)
        with self.assertRaisesRegex(media.MediaError, 'animadas'):
            self.put(buf.getvalue(), 'animated.png')

    def test_byte_pixel_and_storage_limits_leave_no_artifacts(self):
        for key, limit in [('PHOTO_LIMIT', 32), ('PIXEL_LIMIT', 100), ('STORAGE_LIMIT', 32)]:
            with self.subTest(limit=key), patch.object(media, key, limit), self.assertRaises(media.MediaError):
                self.put()
            self.assertEqual(self.store.usage()['items'], 0)
            self.assertFalse(list(self.store.incoming.iterdir()))
            self.assertFalse(list(self.store.derivatives.iterdir()))
            self.assertFalse(list(self.store.originals.iterdir()))

    def test_metadata_validation_and_no_mass_assignment(self):
        unsafe = [{'source_url': 'javascript:alert(1)'}, {'source_url': 'https://user:secret@host.test/a'},
                  {'source_url': 'https://host.test/\nheader'}, {'source_url': '//host.test/x'},
                  {'tags': 'string'}, {'tags': ['x'] * 31}, {'title': 'x' * 201},
                  {'date': '2026-99-99'}, {'hash': 'forged'}, {'status': 'ready'},
                  {'archived': True}, {'focal_x': float('nan')}, {'reviewed': 1}]
        for metadata in unsafe:
            with self.subTest(metadata=metadata), self.assertRaises(media.MediaError):
                self.put(metadata=metadata)
        item = self.put(metadata={'source_url': 'https://www.instagram.com/p/example/',
                                  'date': '2026-10-08', 'tags': ['Cerveza', 'Cerveza', ''], 'focal_x': 0.3})
        self.assertEqual(item['tags'], ['Cerveza'])
        self.assertEqual(item['focal_x'], 0.3)
        with self.assertRaises(media.MediaError):
            self.store.update(item['id'], {'id': 'forged'})

    def test_traversal_never_exposes_originals_or_arbitrary_files(self):
        for filename in ['../foto.jpg', '/tmp/foto.jpg', 'C:\\foto.jpg', 'x\nf.jpg']:
            with self.subTest(filename=filename), self.assertRaises(media.MediaError):
                self.put(name=filename)
        self.assertIsNone(self.store.get('../originals/private.jpg'))
        with self.assertRaises(FileNotFoundError):
            self.store.path('../media.sqlite')
        item = self.put()
        target = self.store.path(item['id'])
        target.unlink(); target.symlink_to(self.store.originals / (item['id'] + '.jpg'))
        with self.assertRaises(FileNotFoundError):
            self.store.path(item['id'])

    def test_archive_preserves_urls_and_restore_search(self):
        item = self.put(metadata={'title': 'Ámbar del Cisne', 'tags': ['barril'], 'category': 'Cervezas'})
        self.assertEqual(self.store.list(q='barril', category='Cervezas', kind='image')['total'], 1)
        self.store.archive(item['id'], True)
        self.assertEqual(self.store.list()['total'], 0)
        self.assertEqual(self.store.list(archived=True)['total'], 1)
        self.assertTrue(self.store.path(item['id']).is_file())
        self.store.archive(item['id'], False)
        updated = self.store.update(item['id'], {'title': 'Nueva ficha', 'reviewed': True})
        self.assertTrue(updated['reviewed'])
        self.assertEqual(self.store.list(q='Nueva')['total'], 1)
        self.assertEqual(self.store.list(q='%')['total'], 0)

    def test_pagination_latest_first_and_categories(self):
        ids = [self.put(photo((i * 5, 0, 0)), f'{i}.jpg')['id'] for i in range(38)]
        first = self.store.list()
        second = self.store.list(page=2)
        self.assertEqual((first['total'], first['pages'], len(first['items']), len(second['items'])), (38, 2, 36, 2))
        self.assertEqual(first['items'][0]['id'], ids[-1])
        self.assertEqual(second['items'][-1]['id'], ids[0])
        self.assertIn('Marca', first['categories'])

    def test_heic_is_explicitly_unavailable_without_optional_plugin(self):
        with patch.object(media, 'HEIF_AVAILABLE', False), self.assertRaisesRegex(media.MediaError, 'HEIC'):
            self.put(b'not heic', 'phone.heic')

    def test_import_is_repeatable_and_skips_private_folders(self):
        site = self.root / 'sitio'; image_dir = site / 'assets/img/marca'; image_dir.mkdir(parents=True)
        (image_dir / 'mascota.jpg').write_bytes(self.jpeg)
        (site / 'PRIVADO').mkdir(); (site / 'PRIVADO/secret.jpg').write_bytes(self.jpeg)
        archive = self.root / 'contenido'; post = archive / 'instagram/posts/2026-10-08_ABC'; post.mkdir(parents=True)
        (post / '01.jpg').write_bytes(self.jpeg)
        (post / 'caption.txt').write_text('Una pinta en el Cisne', encoding='utf-8')
        (post / 'meta.json').write_text(json.dumps({'url': 'https://www.instagram.com/p/ABC/'}))
        record = importer.metadata_for(post / '01.jpg', archive, 'Archivo propio')
        self.assertEqual(record['date'], '2026-10-08')
        self.assertEqual(record['title'], 'Una pinta en el Cisne')
        self.assertFalse(record['reviewed'])
        files = list(importer.candidates(site, 'Sitio', True)) + list(importer.candidates(archive, 'Archivo'))
        self.assertEqual(len(files), 2)
        imported = []
        for path, base, origin in files:
            with path.open('rb') as handle:
                imported.append(self.store.ingest(handle, path.name, importer.metadata_for(path, base, origin)))
        self.assertEqual(imported[0]['id'], imported[1]['id'])

    def test_local_import_detects_mislabeled_download_without_relaxing_uploads(self):
        path = self.root / 'download.jpg'
        content = photo(fmt='WEBP')
        path.write_bytes(content)
        self.assertEqual(importer.ingestion_filename(path), 'download.webp')
        with self.assertRaises(media.MediaError):
            self.put(content, path.name)
        with path.open('rb') as source:
            item = self.store.ingest(source, importer.ingestion_filename(path))
        self.assertEqual(item['name'], 'download.webp')
        self.assertEqual(item['kind'], 'image')
        self.assertEqual(path.read_bytes(), content)
        self.assertEqual(path.name, 'download.jpg')


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg no instalado')
class VideoTest(MediaTest):
    # Only run video-specific cases here; image tests are inherited and kept separate below.
    @classmethod
    def setUpClass(cls):
        cls.video_tmp = tempfile.TemporaryDirectory(prefix='cisne-video-fixture-')
        path = Path(cls.video_tmp.name) / 'tiny.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', 'color=c=orange:s=320x240:r=12',
                        '-f', 'lavfi', '-i', 'sine=frequency=440', '-t', '0.6',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(path)], check=True)
        cls.mp4 = path.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.video_tmp.cleanup()

    def test_video_processing_poster_and_silent_derivative(self):
        item = self.put(self.mp4, 'hero.mp4')
        self.assertIn(item['status'], ['processing', 'ready'])
        self.assertTrue(self.store.wait_for_idle(30))
        ready = self.store.get(item['id'])
        self.assertEqual(ready['status'], 'ready', ready['error'])
        self.assertTrue(self.store.path(item['id'], 'thumb').is_file())
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json',
                                 str(self.store.path(item['id']))], capture_output=True, check=True)
        streams = json.loads(result.stdout)['streams']
        self.assertEqual([s['codec_type'] for s in streams], ['video'])
        self.assertEqual(streams[0]['codec_name'], 'h264')
        self.assertEqual(self.store.usage()['reserved_bytes'], 0)

    def test_video_limits_and_fake_mp4(self):
        with self.assertRaises(media.MediaError):
            self.put(self.jpeg, 'not-video.mp4')
        with patch.object(media, 'DURATION_LIMIT', 0.1), self.assertRaises(media.MediaError):
            self.put(self.mp4, 'too-long.mp4')
        with patch.object(media, 'VIDEO_LIMIT', 32), self.assertRaises(media.MediaError):
            self.put(self.mp4, 'too-big.mp4')
        self.assertEqual(self.store.usage()['items'], 0)

    def test_pending_video_resumes_after_restart(self):
        self.store.close()
        item = self.put(self.mp4, 'pending.mp4')
        self.assertEqual(item['status'], 'processing')
        with self.assertRaises(FileNotFoundError):
            self.store.path(item['id'])
        self.store = media.MediaStore(self.root / 'library')
        self.assertTrue(self.store.wait_for_idle(30))
        self.assertEqual(self.store.get(item['id'])['status'], 'ready')

    def test_video_failure_is_visible_and_retryable(self):
        with patch.object(self.store, '_convert_video', side_effect=media.MediaError('Fallo de prueba')):
            item = self.put(self.mp4, 'retry.mp4')
            self.assertTrue(self.store.wait_for_idle(30))
            self.assertEqual(self.store.get(item['id'])['status'], 'error')
            with self.assertRaises(FileNotFoundError):
                self.store.path(item['id'])
        self.store.retry(item['id'])
        self.assertTrue(self.store.wait_for_idle(30))
        self.assertEqual(self.store.get(item['id'])['status'], 'ready')


# The helper setup is reused without running the image suite twice.
for inherited in [name for name in MediaTest.__dict__ if name.startswith('test_')]:
    setattr(VideoTest, inherited, None)


if __name__ == '__main__':
    unittest.main()
