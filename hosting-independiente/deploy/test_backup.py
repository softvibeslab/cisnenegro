import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('cisne_backup', Path(__file__).with_name('backup.py'))
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / 'live'
        self.data.mkdir()
        (self.data / 'runtime.lock').touch()
        for relative in backup.DATABASES:
            path = self.data / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(path)
            if relative.endswith('media.sqlite'):
                con.execute('create table media(id text, kind text, original_ext text, status text)')
                con.execute("insert into media values('abc', 'image', '.jpg', 'ready')")
            else:
                con.execute('create table records(value text)')
                con.execute("insert into records values('persistente')")
            con.commit()
            con.close()
        for relative in ('cms/media/originals/abc.jpg', 'cms/media/derivatives/abc/file.webp',
                         'cms/media/derivatives/abc/thumb.jpg'):
            path = self.data / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'contenido de prueba')
        self.commands = []

    def tearDown(self):
        self.temp.cleanup()

    def command(self, args, **kwargs):
        self.commands.append(args)
        return subprocess.CompletedProcess(args, 0, stdout='app\n')

    def run_backup(self):
        return backup.run_backup(self.data, self.root / 'backups', self.root / 'compose.yaml',
                                 keep=1, command=self.command)

    def test_archive_restore_and_retention(self):
        first = self.run_backup()
        second = self.run_backup()
        self.assertFalse(Path(first['archive']).exists())
        self.assertTrue(Path(second['archive']).is_file())
        self.assertTrue(second['restore_verified'])
        self.assertEqual(second['ready_media'], 1)
        self.assertEqual(Path(second['archive']).stat().st_mode & 0o777, 0o600)
        self.assertEqual(sum('stop' in args for args in self.commands), 2)
        self.assertEqual(sum('start' in args for args in self.commands), 2)

    def test_failure_restarts_app_and_keeps_last_good_backup(self):
        first = self.run_backup()
        (self.data / 'outside-link').symlink_to(self.root / 'private.txt')
        with self.assertRaisesRegex(ValueError, 'simbólicos'):
            self.run_backup()
        self.assertIn('start', self.commands[-1])
        self.assertTrue(Path(first['archive']).is_file())

    def test_missing_media_rejects_backup_after_restart(self):
        (self.data / 'cms/media/originals/abc.jpg').unlink()
        with self.assertRaisesRegex(ValueError, 'original'):
            self.run_backup()
        self.assertIn('start', self.commands[-1])
        self.assertEqual(list((self.root / 'backups').glob('*.tar.gz')), [])

    def test_sqlite_backup_preserves_committed_wal_and_ignores_old_manifest(self):
        con = sqlite3.connect(self.data / 'club.db')
        try:
            con.execute('pragma journal_mode=wal')
            con.execute("insert into records values('todavía en WAL')")
            con.commit()
            (self.data / 'backup-manifest.json').write_text('manifiesto anterior')
            target = self.root / 'snapshot'
            backup.snapshot(self.data, target)
            restored = sqlite3.connect(target / 'club.db')
            try:
                self.assertEqual(restored.execute('select count(*) from records').fetchone()[0], 2)
            finally:
                restored.close()
            self.assertFalse((target / 'club.db-wal').exists())
            self.assertFalse((target / 'backup-manifest.json').exists())
            backup.archive_and_verify(target, self.root / 'verified.tar.gz')
        finally:
            con.close()


if __name__ == '__main__':
    unittest.main()
