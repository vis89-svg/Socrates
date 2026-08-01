import json

import requests

from django.conf import settings


def generate_stream(prompt, model, max_tokens=None, temperature=0.6):
    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    base_url = getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    if not api_key:
        raise RuntimeError('OPENROUTER_API_KEY is not configured')

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
        choices = chunk.get('choices') or []
        if not choices:
            continue
        delta = choices[0].get('delta') or {}
        content = delta.get('content')
        if content:
            yield content
