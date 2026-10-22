"""Una inferencia de Hermes, sin bucle ni ejecución de herramientas.

Proceso privado iniciado por el CMS con el Python de Hermes. El perfil aporta
identidad, modelo y autenticación; el CMS conserva permisos y ejecuta las tres
herramientas editoriales. No llama a chat(), run_conversation() ni al terminal.
El protocolo stdin/stdout nunca devuelve credenciales ni excepciones internas.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
import logging
import os
from pathlib import Path
import sys


PROFILE = 'cisne-negro'
ALLOWED_PROFILES = frozenset({'cisne-negro', 'cisnenegro'})
ALLOWED_TOOLS = frozenset({'read_content', 'mutate_content', 'generate_beer_image'})
MAX_INPUT = 16 * 1024 * 1024
MAX_OUTPUT = 1024 * 1024
SAFE_ERROR = 'Hermes no pudo completar la solicitud. Revisa el perfil y su autenticación.'


class WorkerError(ValueError):
    """Fallo interno; su contenido no sale del proceso."""


def selected_profile(value=None):
    """Solo las dos identidades de Cisne autorizadas, nunca nombres del cliente."""
    name = os.environ.get('CISNE_HERMES_PROFILE_NAME', PROFILE) if value is None else value
    if not isinstance(name, str) or name not in ALLOWED_PROFILES:
        raise WorkerError('El perfil Hermes configurado no está permitido.')
    return name


def validate_request(request):
    if not isinstance(request, dict) or request.get('action') not in ('status', 'respond'):
        raise WorkerError('action')
    if 'expected_profile' in request and request['expected_profile'] != selected_profile():
        raise WorkerError('profile mismatch')
    if request['action'] == 'status':
        return
    instructions = request.get('instructions')
    inputs = request.get('inputs')
    definitions = request.get('tools')
    if not isinstance(instructions, str) or not instructions.strip() or len(instructions) > 60000:
        raise WorkerError('instructions')
    if not isinstance(inputs, list) or not inputs or len(inputs) > 80:
        raise WorkerError('inputs')
    for item in inputs:
        if not isinstance(item, dict):
            raise WorkerError('input item')
        kind = item.get('type')
        if kind in (None, 'message'):
            if item.get('role') not in ('user', 'assistant') or not isinstance(item.get('content'), (str, list)):
                raise WorkerError('input role')
        elif kind == 'function_call':
            if item.get('name') not in ALLOWED_TOOLS or not isinstance(item.get('arguments'), str):
                raise WorkerError('input function')
            if not isinstance(item.get('call_id'), str) or not item['call_id']:
                raise WorkerError('input call id')
        elif kind == 'function_call_output':
            if not isinstance(item.get('call_id'), str) or not isinstance(item.get('output'), str):
                raise WorkerError('input function output')
        elif kind != 'reasoning':
            raise WorkerError('input type')
    if not isinstance(definitions, list) or len(definitions) != len(ALLOWED_TOOLS):
        raise WorkerError('tools')
    names = []
    for definition in definitions:
        if (not isinstance(definition, dict) or definition.get('type') != 'function'
                or definition.get('strict') is not True
                or set(definition) - {'type', 'name', 'description', 'strict', 'parameters'}
                or not isinstance(definition.get('parameters'), dict)):
            raise WorkerError('tool definition')
        names.append(definition.get('name'))
    if set(names) != ALLOWED_TOOLS:
        raise WorkerError('tool names')


def profile_paths():
    root_value = os.environ.get('CISNE_HERMES_ROOT', '')
    profile_value = os.environ.get('CISNE_HERMES_PROFILE_DIR', '')
    if not root_value or not profile_value:
        raise WorkerError('missing paths')
    root, profile = Path(root_value).expanduser().resolve(), Path(profile_value).expanduser().resolve()
    if profile.name != selected_profile() or profile.parent.name != 'profiles':
        raise WorkerError('profile')
    if not (root / 'run_agent.py').is_file() or not (profile / 'config.yaml').is_file() or not (profile / 'SOUL.md').is_file():
        raise WorkerError('installation')
    configured_home = os.environ.get('HERMES_HOME')
    if configured_home and Path(configured_home).expanduser().resolve() != profile:
        raise WorkerError('home mismatch')
    # Set before importing Hermes: its configuration and auth paths are cached.
    os.environ['HERMES_HOME'] = str(profile)
    # No environment-based task/tool injection into an editorial request.
    for name in ('HERMES_KANBAN_TASK', 'HERMES_CONFIG', 'HERMES_ENV', 'HERMES_PROFILE',
                 'HERMES_INFERENCE_MODEL', 'HERMES_INFERENCE_PROVIDER'):
        os.environ.pop(name, None)
    return root, profile


def load_runtime():
    root, profile = profile_paths()
    sys.path.insert(0, str(root))
    from hermes_cli.config import load_config
    from hermes_cli.runtime_provider import resolve_runtime_provider
    from run_agent import AIAgent

    config = load_config()
    model_config = config.get('model') or {}
    if not isinstance(model_config, dict):
        raise WorkerError('model configuration')
    model, provider = model_config.get('default'), model_config.get('provider')
    if not isinstance(model, str) or not model or not isinstance(provider, str) or not provider:
        raise WorkerError('model configuration')
    # No auto-provider fallback: always use the provider explicitly in this profile.
    runtime = resolve_runtime_provider(requested=provider, target_model=model)
    # The checked-in adapter deliberately supports the Responses transport used
    # by this profile. Other modes need an explicit, tested message adapter.
    if runtime.get('api_mode') != 'codex_responses' or not runtime.get('api_key'):
        raise WorkerError('unsupported or unauthenticated runtime')
    soul = (profile / 'SOUL.md').read_text(encoding='utf-8')
    if not soul.strip() or len(soul) > 32000:
        raise WorkerError('identity')
    return model, runtime, soul, AIAgent


def _as_plain(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json', exclude_none=True)
    if isinstance(value, dict):
        return {key: _as_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_as_plain(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise WorkerError('unexpected response object')


def response_output(response):
    """Retain protocol reasoning for the next model turn, never execute a call."""
    status = response.get('status') if isinstance(response, dict) else getattr(response, 'status', None)
    if status in ('failed', 'cancelled', 'incomplete'):
        raise WorkerError('incomplete response')
    raw = response.get('output') if isinstance(response, dict) else getattr(response, 'output', None)
    if not isinstance(raw, list) or not raw:
        raise WorkerError('empty response')
    output = [_as_plain(item) for item in raw]
    for item in output:
        if not isinstance(item, dict):
            raise WorkerError('output item')
        kind = item.get('type')
        if kind == 'function_call':
            if item.get('name') not in ALLOWED_TOOLS or not isinstance(item.get('arguments'), str):
                raise WorkerError('output function')
            if not isinstance(item.get('call_id'), str) or not item['call_id']:
                raise WorkerError('output call id')
        elif kind == 'message':
            if item.get('role') != 'assistant' or not isinstance(item.get('content'), list):
                raise WorkerError('output message')
        elif kind != 'reasoning':
            raise WorkerError('output type')
    if len(json.dumps(output, ensure_ascii=False).encode()) > MAX_OUTPUT:
        raise WorkerError('output size')
    return {'output': output}


def handle(request, runtime_loader=load_runtime):
    validate_request(request)
    profile = selected_profile()
    model, runtime, soul, agent_class = runtime_loader()
    if request['action'] == 'status':
        return {'configured': True, 'model': model, 'provider': runtime['provider'], 'profile': profile}
    agent = agent_class(
        model=model, provider=runtime['provider'], api_key=runtime['api_key'],
        base_url=runtime.get('base_url'), api_mode=runtime['api_mode'],
        credential_pool=runtime.get('credential_pool'),
        enabled_toolsets=[], disabled_toolsets=[], skip_memory=True,
        skip_context_files=True, load_soul_identity=False, session_db=None,
        save_trajectories=False, verbose_logging=False, quiet_mode=True,
        max_iterations=1, max_tokens=2500, platform='cisne_cms',
        reasoning_config={'effort': 'low'}, checkpoints_enabled=False,
    )
    # These definitions are sent to the model only. No handler is registered.
    agent.tools = [{'type': 'function', 'function': {key: value for key, value in item.items() if key != 'type'}}
                   for item in deepcopy(request['tools'])]
    agent.valid_tool_names = set(ALLOWED_TOOLS)
    agent.request_overrides = {}
    agent.suppress_status_output = True
    agent.stream_delta_callback = None
    agent.tool_gen_callback = None
    instructions = (soul + '\n\nPERFIL HERMES ACTIVO: ' + profile + '. MODO CMS: las instrucciones de desarrollo del perfil '
                    'no conceden acceso a archivos, terminal, publicación ni cuentas en este canal. '
                    'Rigen los permisos y herramientas editoriales siguientes.\n\n' + request['instructions'])
    # Build authentication/provider-specific kwargs via Hermes. Retain the
    # original Responses input (including encrypted reasoning and image data).
    kwargs = agent._build_api_kwargs([
        {'role': 'system', 'content': instructions},
        {'role': 'user', 'content': 'Consulta editorial del CMS.'},
    ])
    kwargs.update(instructions=instructions, input=deepcopy(request['inputs']),
                  tools=deepcopy(request['tools']), parallel_tool_calls=False, store=False,
                  timeout=50)
    kwargs = agent._get_transport().preflight_kwargs(kwargs, allow_stream=False)
    response = agent._interruptible_api_call(kwargs)
    return response_output(response)


def main():
    # Hermes and optional SDKs can print banners or diagnostics during import.
    # Discard them rather than leaking paths, headers or credential failures.
    logging.disable(logging.CRITICAL)
    captured = io.StringIO()
    code = 0
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise WorkerError('input size')
        request = json.loads(raw)
        with redirect_stdout(captured), redirect_stderr(captured):
            result = handle(request)
    except Exception:
        code = 1
        try:
            profile = selected_profile()
        except WorkerError:
            profile = None
        result = {'configured': False, 'profile': profile, 'error': SAFE_ERROR}
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
