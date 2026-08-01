import json
import os
from django.conf import settings
from .inference import generate_stream as local_stream

_models = None


def _load_models():
    global _models
    if _models is not None:
        return _models
    path = os.path.join(os.path.dirname(__file__), 'models.json')
    with open(path) as f:
        _models = json.load(f)
    return _models


def _get_model_config(key):
    models = _load_models()
    cfg = models.get(key) or models.get('default')
    if isinstance(cfg, str):
        cfg = {'name': cfg, 'backend': 'local'}
    return {'name': cfg.get('name', ''), 'backend': cfg.get('backend', 'local')}


def _has_openrouter():
    return bool(getattr(settings, 'OPENROUTER_API_KEY', ''))


def _api_stream(model_name, prompt, max_tokens):
    from .inference_api import generate_stream as api_stream
    yield from api_stream(prompt, model=model_name, max_tokens=max_tokens)


class ModelRouter:
    @staticmethod
    def select(key):
        return _get_model_config(key)['name']

    @staticmethod
    def generate_stream(prompt, model_key='default', max_tokens=None, allow_fallback=True):
        cfg = _get_model_config(model_key)

        if cfg['backend'] == 'openrouter' and _has_openrouter():
            try:
                yield from _api_stream(cfg['name'], prompt, max_tokens)
                return
            except Exception:
                if not allow_fallback:
                    raise

        try:
            yield from local_stream(prompt, max_tokens=max_tokens)
            return
        except Exception:
            fallback = _get_model_config('fallback')
            if fallback['name'] != cfg['name'] or fallback['backend'] != cfg['backend']:
                if fallback['backend'] == 'openrouter' and _has_openrouter():
                    yield from _api_stream(fallback['name'], prompt, max_tokens)
                else:
                    yield from local_stream(prompt, max_tokens=max_tokens)
            else:
                raise
