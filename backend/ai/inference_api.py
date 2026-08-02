import json

import requests

from django.conf import settings

_PROVIDERS = {
    'openrouter': {
        'api_key': 'OPENROUTER_API_KEY',
        'base_url': 'OPENROUTER_BASE_URL',
    },
    'groq': {
        'api_key': 'GROQ_API_KEY',
        'base_url': 'GROQ_BASE_URL',
    },
    'gemini': {
        'api_key': 'GEMINI_API_KEY',
        'base_url': 'GEMINI_BASE_URL',
    },
}


def provider_configured(provider):
    cfg = _PROVIDERS.get(provider)
    if not cfg:
        return False
    return bool(getattr(settings, cfg['api_key'], ''))


def provider_base_url(provider):
    cfg = _PROVIDERS.get(provider)
    if not cfg:
        return ''
    return getattr(settings, cfg['base_url'], '')


class IncompleteStreamError(RuntimeError):
    """The provider closed the stream before reporting a finish reason."""


class QuotaExhaustedError(IncompleteStreamError):
    """The provider's quota is exhausted; waiting locally is pointless."""


def generate_stream(prompt, model, max_tokens=None, temperature=0.6, provider='openrouter'):
    cfg = _PROVIDERS.get(provider)
    if not cfg:
        raise RuntimeError(f'Unknown provider: {provider}')
    api_key = getattr(settings, cfg['api_key'], '')
    base_url = getattr(settings, cfg['base_url'], '')
    if not api_key:
        raise RuntimeError(f'{cfg["api_key"]} is not configured')

    body = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': True,
        'temperature': temperature,
    }
    if max_tokens:
        body['max_tokens'] = max_tokens

    resp = requests.post(
        f'{base_url}/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json=body,
        stream=True,
        timeout=(30, 180),
    )
    resp.raise_for_status()

    finish_reason = None
    chars = 0
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith('data:'):
            continue
        payload = line[5:].strip()
        if payload == '[DONE]':
            break
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(chunk, dict) and chunk.get('error'):
            raise IncompleteStreamError(
                f'{provider} stream error: {json.dumps(chunk["error"])[:300]}'
            )
        choices = chunk.get('choices') or []
        if not choices:
            continue
        reason = choices[0].get('finish_reason')
        if isinstance(reason, str) and reason:
            finish_reason = reason
        delta = choices[0].get('delta') or {}
        content = delta.get('content')
        if content:
            chars += len(content)
            yield content

    print(
        f'[STREAM] provider={provider} model={model} chars={chars} finish={finish_reason!r} max_tokens={max_tokens}',
        flush=True,
    )
    if finish_reason not in ('stop', 'length'):
        raise IncompleteStreamError(
            f'{provider} stream ended before completion (finish_reason={finish_reason!r})'
        )
    if finish_reason == 'length' and max_tokens and chars < max_tokens * 2:
        raise IncompleteStreamError(
            f'{provider} ended with finish=length after only {chars} chars (budget {max_tokens} tokens)'
        )
