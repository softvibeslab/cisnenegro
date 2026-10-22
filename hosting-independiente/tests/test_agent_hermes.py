"""Contrato del puente Hermes: procesos simulados, sin IA ni credenciales reales."""
import json
import errno
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from agent_hermes import HermesProvider, HermesError


class HermesBridge(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {'CISNE_HERMES_PROFILE_NAME': 'cisne-negro'})
        environment.start()
        self.addCleanup(environment.stop)
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / 'profiles/cisne-negro'
        self.home.mkdir(parents=True)
        (self.home / 'config.yaml').write_text('model: {}')
        install = root / 'hermes-agent'
        (install / 'venv/bin').mkdir(parents=True)
        (install / 'venv/bin/python3').touch()
        self.provider = HermesProvider({'AGENT_HERMES_ROOT': str(install), 'AGENT_HERMES_PROFILE_DIR': str(self.home)}, [{'name': 'read_content'}])
        self.provider.worker = root / 'worker.py'
        self.provider.worker.touch()

    def tearDown(self):
        self.tmp.cleanup()

    def result(self, body=None, **kwargs):
        return subprocess.CompletedProcess([], kwargs.get('returncode', 0),
            kwargs.get('stdout', json.dumps(body or {'output': []})), kwargs.get('stderr', ''))

    def test_fixed_argv_stdin_and_environment_do_not_pass_cms_secrets(self):
        with patch.dict(os.environ, {'CLUB_SECRET': 'cms-secret', 'CISNE_CMS_PASSWORD': 'password-secret',
                                     'TELEGRAM_BOT_TOKEN': 'telegram-secret', 'PYTHONPATH': '/untrusted',
                                     'HERMES_HOME': '/other-profile'}), patch('agent_hermes.subprocess.run', side_effect=[self.result({'configured': True, 'profile': 'cisne-negro'}), self.result()]) as run:
            self.provider.respond('Instructions', [{'role': 'user', 'content': '$(touch bad);`echo bad`'}])
        args, kwargs = run.call_args
        self.assertEqual(args[0], [str(self.provider.python), str(self.provider.worker)])
        self.assertNotIn('shell', kwargs)
        self.assertEqual(kwargs['env']['HERMES_HOME'], str(self.home))
        self.assertEqual(kwargs['env']['CISNE_HERMES_PROFILE_NAME'], 'cisne-negro')
        self.assertEqual(json.loads(kwargs['input'])['expected_profile'], 'cisne-negro')
        self.assertTrue({'CLUB_SECRET','CISNE_CMS_PASSWORD','TELEGRAM_BOT_TOKEN','PYTHONPATH'}.isdisjoint(kwargs['env']))
        self.assertIn('$(touch bad)', kwargs['input'])
        self.assertEqual(kwargs['timeout'], 65)

    def test_status_cached_and_only_public_fields_returned(self):
        response = self.result({'configured': True, 'profile': 'cisne-negro', 'model': 'profile-model', 'api_key': 'hidden', 'extra': 'private'})
        with patch('agent_hermes.subprocess.run', return_value=response) as run:
            first = self.provider.status()
            first['configured'] = False
            second = self.provider.status()
        self.assertTrue(second['configured'])
        self.assertEqual(second, {'configured': True, 'model': 'profile-model', 'provider': 'hermes', 'profile': 'cisne-negro'})
        self.assertEqual(run.call_count, 1)

    def test_process_errors_are_sanitized(self):
        cases = [self.result(returncode=1, stderr='private-token-123'), self.result(stdout='private-token-123'),
                 self.result({'error':'private-token-123'}), self.result(stdout='x' * (2 * 1024 * 1024 + 1))]
        for result in cases:
            with self.subTest(case=len(result.stdout)), patch('agent_hermes.subprocess.run', return_value=result):
                with self.assertRaises(HermesError) as caught:
                    self.provider._call({'action': 'status'}, 20)
                self.assertNotIn('private-token', str(caught.exception))

    def test_timeout_and_full_capacity_fail_without_retry(self):
        with patch('agent_hermes.subprocess.run', side_effect=subprocess.TimeoutExpired([], 65)) as run:
            with self.assertRaises(HermesError): self.provider.respond('x', [])
            self.assertEqual(run.call_count, 1)
        self.provider._slots.acquire()
        self.provider._slots.acquire()
        try:
            with patch('agent_hermes.subprocess.run') as run:
                with self.assertRaises(HermesError) as caught: self.provider.respond('x', [])
                self.assertEqual(caught.exception.status_code, 429)
                run.assert_not_called()
        finally:
            self.provider._slots.release()
            self.provider._slots.release()

    def test_wrong_or_missing_profile_is_unavailable(self):
        self.provider.home = self.home.parent / 'another-client'
        with patch('agent_hermes.subprocess.run') as run:
            self.assertFalse(self.provider.status()['configured'])
            run.assert_not_called()

    def test_empty_optional_paths_use_defaults(self):
        with patch.dict(os.environ, {'CISNE_HERMES_ROOT':'', 'CISNE_HERMES_PROFILE_DIR':''}):
            provider = HermesProvider({}, [])
        self.assertEqual(provider.home.name, 'cisne-negro')
        self.assertEqual(provider.root.name, 'hermes-agent')

    def test_socket_path_is_private_configuration_and_needs_no_local_install(self):
        provider = HermesProvider({'AGENT_HERMES_SOCKET': '/run/cisne-hermes/bridge.sock'}, [])
        provider.home = Path('/missing/profile')
        with patch.object(provider, '_socket_call', return_value={'configured': True}) as call, patch('agent_hermes.subprocess.run') as process:
            self.assertTrue(provider._call({'action': 'status'}, 20)['configured'])
            call.assert_called_once_with({'action': 'status', 'expected_profile': 'cisne-negro'}, 20)
            process.assert_not_called()

    def test_socket_configuration_rejects_relative_and_nul_paths(self):
        for path in ('relative.sock', '/run/private\x00.sock'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                HermesProvider({'AGENT_HERMES_SOCKET': path}, [])

    def test_socket_connection_errors_do_not_disclose_internal_path(self):
        provider = HermesProvider({'AGENT_HERMES_SOCKET': '/missing/private-secret.sock'}, [])
        with self.assertRaises(HermesError) as caught:
            provider._call({'action': 'status'}, 0.1)
        self.assertNotIn('private-secret', str(caught.exception))

    def test_socket_request_size_is_limited_before_connect(self):
        provider = HermesProvider({'AGENT_HERMES_SOCKET': '/run/cisne-hermes/bridge.sock'}, [])
        with patch('agent_hermes.socket.socket') as connection:
            with self.assertRaises(HermesError):
                provider._call({'action': 'respond', 'large': 'x' * (16 * 1024 * 1024)}, 1)
            connection.assert_not_called()

    def test_only_the_two_cisne_profile_names_are_allowed(self):
        for name in ('other-client', '../cisnenegro', 'profiles/cisnenegro', '/cisnenegro', '', ['cisnenegro']):
            with self.subTest(name=name), self.assertRaises(ValueError):
                HermesProvider({'AGENT_HERMES_PROFILE_NAME': name}, [])
        with patch.dict(os.environ, {'CISNE_HERMES_PROFILE_NAME': 'cisnenegro'}):
            self.assertEqual(HermesProvider({}, []).profile, 'cisnenegro')
            self.assertEqual(HermesProvider({}, []).home.name, 'cisnenegro')
            self.assertEqual(HermesProvider({'AGENT_HERMES_PROFILE_NAME': 'cisne-negro'}, []).profile, 'cisne-negro')

    def test_subprocess_can_use_cisnenegro_and_rejects_wrong_parent(self):
        target = self.home.parent / 'cisnenegro'
        self.home.rename(target)
        provider = HermesProvider({'AGENT_HERMES_PROFILE_NAME': 'cisnenegro',
            'AGENT_HERMES_PROFILE_DIR': str(target), 'AGENT_HERMES_ROOT': str(self.provider.root)}, [])
        response = self.result({'configured': True, 'profile': 'cisnenegro', 'model': 'profile-model'})
        with patch('agent_hermes.subprocess.run', return_value=response) as run:
            self.assertEqual(provider.status()['profile'], 'cisnenegro')
            self.assertTrue(provider.status()['configured'])
            self.assertEqual(run.call_args.kwargs['env']['CISNE_HERMES_PROFILE_NAME'], 'cisnenegro')
        misplaced = target.parent.parent / 'cisnenegro'
        target.rename(misplaced)
        provider.home = misplaced
        provider._status = None
        with patch('agent_hermes.subprocess.run') as run:
            self.assertFalse(provider.status()['configured'])
            run.assert_not_called()

    def test_subprocess_status_requires_exact_profile_and_boolean_before_inference(self):
        cases = [{'configured': True, 'profile': 'cisnenegro'}, {'configured': True},
                 {'configured': 1, 'profile': 'cisne-negro'}, {'configured': 'true', 'profile': 'cisne-negro'}]
        for response in cases:
            self.provider._status = None
            with self.subTest(response=response), patch('agent_hermes.subprocess.run', return_value=self.result(response)) as run:
                self.assertFalse(self.provider.status()['configured'])
                with self.assertRaises(HermesError):
                    self.provider.respond('No debe llegar al modelo', [])
                self.assertEqual(run.call_count, 1)
                self.assertEqual(json.loads(run.call_args.kwargs['input'])['action'], 'status')

    def test_socket_status_does_not_trust_a_different_remote_profile(self):
        provider = HermesProvider({'AGENT_HERMES_SOCKET': '/run/cisne-hermes/bridge.sock',
                                  'AGENT_HERMES_PROFILE_NAME': 'cisnenegro'}, [])
        with patch.object(provider, '_socket_call', return_value={'configured': True, 'profile': 'cisne-negro', 'model': 'other'}) as call:
            self.assertFalse(provider.status()['configured'])
            with self.assertRaises(HermesError):
                provider.respond('No debe llegar al modelo', [])
            self.assertEqual(call.call_count, 1)

    def test_socket_preserves_early_busy_response_without_retrying_write(self):
        provider = HermesProvider({'AGENT_HERMES_SOCKET': '/run/cisne-hermes/bridge.sock'}, [])
        with patch('agent_hermes.socket.socket') as factory:
            connection = factory.return_value.__enter__.return_value
            connection.sendall.side_effect = BrokenPipeError(errno.EPIPE, 'closed')
            connection.recv.return_value = b'{"error":"busy","status":429}\n'
            with self.assertRaises(HermesError) as caught:
                provider._call({'action': 'status'}, 2)
            self.assertEqual(caught.exception.status_code, 429)
            connection.sendall.assert_called_once()
            connection.connect.assert_called_once()


if __name__ == '__main__': unittest.main()
