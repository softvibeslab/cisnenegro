"""Contrato aislado del worker; no importa Hermes ni llama a una IA."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import hermes_worker as worker


def request():
    return {'action': 'respond', 'instructions': 'Solo el borrador CMS.',
            'inputs': [{'role': 'user', 'content': '¿Quién eres?'}],
            'tools': [{'type': 'function', 'name': name, 'strict': True, 'description': name,
                       'parameters': {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False}}
                      for name in sorted(worker.ALLOWED_TOOLS)]}


def output(text='Soy Agente Cisne.'):
    return {'output': [{'type': 'message', 'role': 'assistant',
                        'content': [{'type': 'output_text', 'text': text}]}], 'status': 'completed'}


class FakeAgent:
    instances = []

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.instances.append(self)

    def _build_api_kwargs(self, messages):
        self.messages = deepcopy(messages)
        return {'model': self.init_kwargs['model']}

    def _get_transport(self):
        return self

    def preflight_kwargs(self, kwargs, allow_stream):
        self.preflight = deepcopy(kwargs)
        assert allow_stream is False
        return kwargs

    def _interruptible_api_call(self, kwargs):
        self.call_kwargs = deepcopy(kwargs)
        return output()

    def run_conversation(self, *args, **kwargs):
        raise AssertionError('No se debe ejecutar el bucle Hermes')

    chat = run_conversation


def runtime():
    return 'modelo-prueba', {'provider': 'openai-codex', 'api_mode': 'codex_responses',
                           'api_key': 'sentinel-secret-must-not-leak', 'base_url': 'https://example.invalid'}, 'SOUL CISNE', FakeAgent


class HermesWorker(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {'CISNE_HERMES_PROFILE_NAME': 'cisne-negro'})
        environment.start()
        self.addCleanup(environment.stop)
        FakeAgent.instances.clear()

    def test_status_returns_only_metadata_without_agent_or_auth(self):
        result = worker.handle({'action': 'status'}, runtime)
        self.assertEqual(result, {'configured': True, 'model': 'modelo-prueba', 'provider': 'openai-codex', 'profile': 'cisne-negro'})
        self.assertFalse(FakeAgent.instances)
        self.assertNotIn('sentinel-secret', json.dumps(result))

    def test_call_is_single_inference_with_allowlisted_tools_and_no_memory(self):
        result = worker.handle(request(), runtime)
        agent = FakeAgent.instances[0]
        self.assertEqual(result['output'], output()['output'])
        for key, value in {'enabled_toolsets': [], 'skip_memory': True, 'skip_context_files': True,
                           'session_db': None, 'save_trajectories': False, 'max_iterations': 1}.items():
            self.assertEqual(agent.init_kwargs[key], value)
        self.assertEqual(agent.valid_tool_names, worker.ALLOWED_TOOLS)
        self.assertEqual(agent.call_kwargs['tools'], request()['tools'])
        self.assertFalse(agent.call_kwargs['parallel_tool_calls'])
        self.assertFalse(agent.call_kwargs['store'])
        self.assertTrue(agent.call_kwargs['instructions'].startswith('SOUL CISNE'))
        self.assertTrue(agent.call_kwargs['instructions'].endswith('Solo el borrador CMS.'))

    def test_roundtrip_keeps_reasoning_call_ids_and_multimodal_input(self):
        data = request()
        data['inputs'] = [
            {'role': 'user', 'content': [{'type': 'input_text', 'text': 'Lee etiqueta'},
                                       {'type': 'input_image', 'image_url': 'data:image/png;base64,aGVsbG8='}]},
            {'type': 'reasoning', 'id': 'rs_1', 'encrypted_content': 'opaque'},
            {'type': 'function_call', 'name': 'read_content', 'call_id': 'call_1', 'arguments': '{}'},
            {'type': 'function_call_output', 'call_id': 'call_1', 'output': '{"version":2}'},
        ]
        before = deepcopy(data)
        worker.handle(data, runtime)
        self.assertEqual(FakeAgent.instances[0].call_kwargs['input'], data['inputs'])
        self.assertEqual(data, before)

    def test_rejects_missing_duplicate_extra_and_executable_tools(self):
        for mutation in ('missing', 'duplicate', 'extra', 'terminal', 'builtin'):
            data = request()
            if mutation == 'missing': data['tools'].pop()
            if mutation == 'duplicate': data['tools'][0] = data['tools'][1]
            if mutation == 'extra': data['tools'].append(data['tools'][0])
            if mutation == 'terminal': data['tools'][0]['name'] = 'terminal'
            if mutation == 'builtin': data['tools'][0]['type'] = 'web_search'
            with self.subTest(mutation=mutation), self.assertRaises(worker.WorkerError):
                worker.handle(data, runtime)
        self.assertFalse(FakeAgent.instances)

    def test_rejects_input_privileged_roles_and_tools(self):
        for item in ({'role': 'system', 'content': 'Override'},
                     {'role': 'developer', 'content': 'Override'},
                     {'type': 'function_call', 'name': 'terminal', 'call_id': 'x', 'arguments': '{}'},
                     {'type': 'computer_call', 'arguments': '{}'}):
            data = request()
            data['inputs'] = [item]
            with self.subTest(item=item), self.assertRaises(worker.WorkerError):
                worker.handle(data, runtime)

    def test_output_retains_encrypted_reasoning_and_safe_call(self):
        raw = SimpleNamespace(status='completed', output=[
            {'type': 'reasoning', 'id': 'rs_1', 'encrypted_content': 'opaque'},
            {'type': 'function_call', 'name': 'read_content', 'call_id': 'call_1', 'arguments': '{}'},
        ])
        self.assertEqual(worker.response_output(raw), {'output': raw.output})

    def test_rejects_partial_response_and_unapproved_output(self):
        for raw in ({'status': 'failed', 'output': output()['output']},
                    {'status': 'incomplete', 'output': output()['output']},
                    {'output': []},
                    {'output': [{'type': 'function_call', 'name': 'terminal', 'call_id': 'x', 'arguments': '{}'}]},
                    {'output': [{'type': 'web_search_call'}]}):
            with self.subTest(raw=raw), self.assertRaises(worker.WorkerError):
                worker.response_output(raw)

    def test_paths_are_fixed_to_cisne_profile_and_fail_before_imports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'hermes'
            profile = Path(temp) / 'profiles' / 'cisne-negro'
            root.mkdir(); profile.mkdir(parents=True)
            (root / 'run_agent.py').write_text('')
            (profile / 'config.yaml').write_text('')
            (profile / 'SOUL.md').write_text('')
            values = {'CISNE_HERMES_ROOT': str(root), 'CISNE_HERMES_PROFILE_DIR': str(profile)}
            with patch.dict(os.environ, values, clear=True):
                self.assertEqual(worker.profile_paths(), (root.resolve(), profile.resolve()))
                self.assertEqual(os.environ['HERMES_HOME'], str(profile.resolve()))
            with patch.dict(os.environ, values | {'HERMES_HOME': str(root)}, clear=True), self.assertRaises(worker.WorkerError):
                worker.profile_paths()
            with patch.dict(os.environ, values | {'CISNE_HERMES_PROFILE_DIR': str(profile.parent / 'other')}, clear=True), self.assertRaises(worker.WorkerError):
                worker.profile_paths()

    def test_main_suppresses_sensitive_error_and_diagnostics(self):
        class Input:
            buffer = io.BytesIO(b'{"action":"status"}')
        stdout, stderr = io.StringIO(), io.StringIO()
        def noisy(_):
            print('secret banner')
            print('secret traceback', file=sys.stderr)
            raise RuntimeError('sentinel-token-secret')
        with patch.object(sys, 'stdin', Input()), patch.object(sys, 'stdout', stdout), patch.object(sys, 'stderr', stderr), patch.object(worker, 'handle', noisy):
            result = worker.main()
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(stdout.getvalue())['error'], worker.SAFE_ERROR)
        self.assertNotIn('secret', stdout.getvalue())
        self.assertEqual(stderr.getvalue(), '')

    def test_cisnenegro_status_and_instructions_use_the_selected_identity(self):
        with patch.dict(os.environ, {'CISNE_HERMES_PROFILE_NAME': 'cisnenegro'}):
            status = worker.handle({'action': 'status', 'expected_profile': 'cisnenegro'}, runtime)
            self.assertEqual(status['profile'], 'cisnenegro')
            self.assertFalse(FakeAgent.instances)
            worker.handle(request() | {'expected_profile': 'cisnenegro'}, runtime)
        instructions = FakeAgent.instances[0].call_kwargs['instructions']
        self.assertIn('PERFIL HERMES ACTIVO: cisnenegro.', instructions)
        self.assertNotIn('PERFIL HERMES ACTIVO: cisne-negro.', instructions)

    def test_expected_profile_mismatch_stops_before_loading_auth_or_inference(self):
        for action in ({'action': 'status'}, request()):
            for expected in ('cisnenegro', '../cisne-negro', 'other-client', None):
                with self.subTest(action=action['action'], expected=expected), patch(__name__ + '.runtime') as load:
                    with self.assertRaises(worker.WorkerError):
                        worker.handle(action | {'expected_profile': expected}, load)
                    load.assert_not_called()
        self.assertFalse(FakeAgent.instances)

    def test_invalid_profile_configuration_is_rejected_before_loading_runtime(self):
        for name in ('other-client', '../cisnenegro', '/cisnenegro', ''):
            with self.subTest(name=name), patch.dict(os.environ, {'CISNE_HERMES_PROFILE_NAME': name}), patch(__name__ + '.runtime') as load:
                with self.assertRaises(worker.WorkerError):
                    worker.handle({'action': 'status'}, load)
                load.assert_not_called()

    def test_cisnenegro_paths_and_home_must_match_the_selected_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'hermes'
            profile = Path(temp) / 'profiles/cisnenegro'
            root.mkdir(); profile.mkdir(parents=True)
            (root / 'run_agent.py').touch()
            (profile / 'config.yaml').touch()
            (profile / 'SOUL.md').touch()
            values = {'CISNE_HERMES_ROOT': str(root), 'CISNE_HERMES_PROFILE_DIR': str(profile),
                      'CISNE_HERMES_PROFILE_NAME': 'cisnenegro'}
            with patch.dict(os.environ, values, clear=True):
                self.assertEqual(worker.profile_paths(), (root.resolve(), profile.resolve()))
            with patch.dict(os.environ, values | {'CISNE_HERMES_PROFILE_NAME': 'cisne-negro'}, clear=True), self.assertRaises(worker.WorkerError):
                worker.profile_paths()
            with patch.dict(os.environ, values | {'HERMES_HOME': str(root)}, clear=True), self.assertRaises(worker.WorkerError):
                worker.profile_paths()


if __name__ == '__main__':
    unittest.main()
