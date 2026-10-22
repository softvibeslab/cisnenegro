"""Contrato de socket Unix y proceso aislado, sin proveedor ni datos reales."""
import json
import errno
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from agent_hermes import HermesError, HermesProvider
from hermes_socket_bridge import BridgeServer, WorkerRunner, SAFE_ERROR
from hermes_worker import ALLOWED_TOOLS, selected_profile


class SocketBridge(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {'CISNE_HERMES_PROFILE_NAME': 'cisne-negro'})
        environment.start()
        self.addCleanup(environment.stop)
        self.temp = tempfile.TemporaryDirectory(prefix='cisne-socket-', dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'run/bridge.sock'
        self.calls = []

    def start(self, runner=None):
        def fake(request):
            self.calls.append(request)
            return {'configured': True, 'model': 'fake-model', 'profile': selected_profile()}
        server = BridgeServer(self.path, runner or fake)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(2)))
        return server

    def raw(self, data):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(2)
            connection.connect(str(self.path))
            connection.sendall(data)
            try:
                connection.shutdown(socket.SHUT_WR)
            except OSError as exc:
                # A rejected complete request can close before this test sends EOF.
                if exc.errno not in (errno.ENOTCONN, errno.EPIPE):
                    raise
            result = bytearray()
            while b'\n' not in result:
                part = connection.recv(65536)
                if not part:
                    break
                result.extend(part)
        return json.loads(result)

    def test_provider_roundtrip_uses_socket_without_install_or_credentials(self):
        self.start()
        provider = HermesProvider({'AGENT_HERMES_SOCKET': str(self.path)}, [])
        with patch('agent_hermes.subprocess.run') as process:
            result = provider.status()
            process.assert_not_called()
        self.assertTrue(result['configured'])
        self.assertEqual(result['provider'], 'hermes')
        self.assertEqual(self.calls, [{'action': 'status', 'expected_profile': 'cisne-negro'}])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o660)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o750)

    def test_malformed_privileged_incomplete_and_multiple_requests_never_start_worker(self):
        self.start()
        for raw in (b'invalid\n', b'[]\n', b'{"action":"publish"}\n',
                    b'{"action":"status"}', b'{"action":"status"}\n{}\n'):
            with self.subTest(raw=raw):
                self.assertEqual(self.raw(raw), SAFE_ERROR)
        self.assertFalse(self.calls)

    def test_request_and_response_size_limits_return_generic_error(self):
        self.start(lambda request: {'configured': True, 'large': 'x' * 100})
        with patch('hermes_socket_bridge.MAX_REQUEST', 12):
            self.assertEqual(self.raw(b'{"action":"status"}\n'), SAFE_ERROR)
        with patch('hermes_socket_bridge.MAX_RESPONSE', 30):
            self.assertEqual(self.raw(b'{"action":"status"}\n'), SAFE_ERROR)

    def test_worker_failure_never_leaks_exception_to_client(self):
        def failed(_):
            raise RuntimeError('private-key-secret')
        self.start(failed)
        self.assertEqual(self.raw(b'{"action":"status"}\n'), SAFE_ERROR)

    def test_busy_limit_is_propagated_by_provider(self):
        server = self.start()
        server.slots.acquire()
        server.slots.acquire()
        try:
            provider = HermesProvider({'AGENT_HERMES_SOCKET': str(self.path)}, [])
            with self.assertRaises(HermesError) as caught:
                provider._call({'action': 'status'}, 2)
            self.assertEqual(caught.exception.status_code, 429)
            self.assertFalse(self.calls)
        finally:
            server.slots.release()
            server.slots.release()

    def test_existing_files_symlinks_and_live_socket_are_preserved(self):
        self.path.parent.mkdir()
        self.path.write_text('keep')
        with self.assertRaises(ValueError):
            BridgeServer(self.path, lambda x: x)
        self.assertEqual(self.path.read_text(), 'keep')
        self.path.unlink()
        target = Path(self.temp.name) / 'target'
        target.write_text('keep too')
        self.path.symlink_to(target)
        with self.assertRaises(ValueError):
            BridgeServer(self.path, lambda x: x)
        self.assertTrue(self.path.is_symlink())
        self.path.unlink()
        self.start()
        inode = self.path.stat().st_ino
        with self.assertRaises(ValueError):
            BridgeServer(self.path, lambda x: x)
        self.assertEqual(self.path.stat().st_ino, inode)

    def test_stale_socket_is_replaced_and_clean_shutdown_unlinks_it(self):
        self.path.parent.mkdir()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as old:
            old.bind(str(self.path))
        server = BridgeServer(self.path, lambda x: x)
        self.assertTrue(self.path.exists())
        server.server_close()
        self.assertFalse(self.path.exists())

    def test_worker_argv_timeouts_environment_and_output_are_fixed(self):
        root = Path(self.temp.name) / 'hermes'
        profile = Path(self.temp.name) / 'profiles/cisne-negro'
        (root / 'venv/bin').mkdir(parents=True)
        (root / 'venv/bin/python3').touch()
        (root / 'run_agent.py').touch()
        profile.mkdir(parents=True)
        (profile / 'config.yaml').write_text('model: {}')
        (profile / 'SOUL.md').write_text('Cisne')
        runner = WorkerRunner(root, profile)
        done = subprocess.CompletedProcess([], 0, '{"configured": true}', 'ignored-private-stderr')
        with patch.dict(os.environ, {'CISNE_CMS_PASSWORD': 'secret', 'PYTHONPATH': '/unsafe', 'TELEGRAM_BOT_TOKEN': 'secret'}), patch('hermes_socket_bridge.subprocess.run', return_value=done) as run:
            self.assertTrue(runner({'action': 'status'})['configured'])
        args, kwargs = run.call_args
        self.assertEqual(args[0], [str(root.resolve() / 'venv/bin/python3'), str(runner.worker)])
        self.assertNotIn('shell', kwargs)
        self.assertEqual(kwargs['timeout'], 18)
        self.assertEqual(kwargs['cwd'], str(profile.resolve()))
        self.assertEqual(kwargs['env']['HERMES_HOME'], str(profile.resolve()))
        self.assertEqual(kwargs['env']['CISNE_HERMES_PROFILE_NAME'], 'cisne-negro')
        self.assertTrue({'CISNE_CMS_PASSWORD', 'PYTHONPATH', 'TELEGRAM_BOT_TOKEN'}.isdisjoint(kwargs['env']))
        with patch('hermes_socket_bridge.subprocess.run') as run:
            with self.assertRaises(ValueError):
                runner({'action': 'terminal'})
            run.assert_not_called()

    def test_socket_roundtrip_supports_cisnenegro_when_both_ends_match(self):
        with patch.dict(os.environ, {'CISNE_HERMES_PROFILE_NAME': 'cisnenegro'}):
            self.start()
            provider = HermesProvider({'AGENT_HERMES_SOCKET': str(self.path)}, [])
            self.assertTrue(provider.status()['configured'])
            self.assertEqual(provider.status()['profile'], 'cisnenegro')
        self.assertEqual(self.calls, [{'action': 'status', 'expected_profile': 'cisnenegro'}])

    def test_cached_status_does_not_allow_inference_after_remote_profile_changes(self):
        self.start()
        tools = [{'type': 'function', 'name': name, 'strict': True,
                  'parameters': {'type': 'object', 'properties': {}}}
                 for name in ALLOWED_TOOLS]
        provider = HermesProvider({'AGENT_HERMES_SOCKET': str(self.path)}, tools)
        self.assertTrue(provider.status()['configured'])
        with patch.dict(os.environ, {'CISNE_HERMES_PROFILE_NAME': 'cisnenegro'}):
            self.assertTrue(provider.status()['configured'])  # Cached metadata, not permission to use another profile.
            with self.assertRaises(HermesError):
                provider.respond('Consulta de prueba', [{'role': 'user', 'content': 'Consulta'}])
        self.assertEqual(self.calls, [{'action': 'status', 'expected_profile': 'cisne-negro'}])

    def test_bridge_runner_requires_matching_profile_and_propagates_its_name(self):
        root = Path(self.temp.name) / 'hermes'
        profile = Path(self.temp.name) / 'profiles/cisnenegro'
        (root / 'venv/bin').mkdir(parents=True)
        (root / 'venv/bin/python3').touch()
        (root / 'run_agent.py').touch()
        profile.mkdir(parents=True)
        (profile / 'config.yaml').touch()
        (profile / 'SOUL.md').touch()
        with self.assertRaises(ValueError):
            WorkerRunner(root, profile)
        with patch.dict(os.environ, {'CISNE_HERMES_PROFILE_NAME': 'cisnenegro'}):
            runner = WorkerRunner(root, profile)
            done = subprocess.CompletedProcess([], 0, '{"configured":true,"profile":"cisnenegro"}', '')
            with patch('hermes_socket_bridge.subprocess.run', return_value=done) as run:
                self.assertEqual(runner({'action': 'status', 'expected_profile': 'cisnenegro'})['profile'], 'cisnenegro')
                self.assertEqual(run.call_args.kwargs['env']['CISNE_HERMES_PROFILE_NAME'], 'cisnenegro')
            with patch('hermes_socket_bridge.subprocess.run') as run:
                with self.assertRaises(ValueError):
                    runner({'action': 'status', 'expected_profile': 'cisne-negro'})
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
