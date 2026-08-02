import json
import os
import time
from django.conf import settings

from .inference import generate_stream as local_stream
from .inference_api import QuotaExhaustedError

_models = None
_QUOTA_STATE = {'down': False, 'at': 0.0, 'ttl': 600}
_STATE_PATH = os.path.join(os.path.dirname(__file__), '.quota_state.json')


def _persist_state():
    try:
        with open(_STATE_PATH, 'w') as f:
            json.dump(_QUOTA_STATE, f)
    except Exception:
        pass


def _load_quota_state():
    try:
        with open(_STATE_PATH) as f:
            data = json.load(f)
        at = float(data.get('at', 0.0))
        if data.get('down') and time.time() - at <= _QUOTA_STATE['ttl']:
            _QUOTA_STATE.update(down=True, at=at)
    except Exception:
        pass


_load_quota_state()


def reset_quota_state():
    _QUOTA_STATE.update(down=False, at=0.0)


def api_quota_down():
    if not _QUOTA_STATE['down']:
        return False
    if time.time() - _QUOTA_STATE['at'] > _QUOTA_STATE['ttl']:
        _QUOTA_STATE['down'] = False
        return False
    return True


def _mark_api_ok():
    _QUOTA_STATE['down'] = False
    _persist_state()


def _mark_quota_down():
    _QUOTA_STATE.update(down=True, at=time.time())
    _persist_state()


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


def _backend_configured(backend):
    if backend == 'local':
        return True
    if backend == 'openrouter':
        return _has_openrouter()
    from .inference_api import provider_configured
    return provider_configured(backend)


def _retry_delay(exc):
    response = getattr(exc, 'response', None)
    retry_after = getattr(response, 'headers', None) and response.headers.get('Retry-After')
    if retry_after:
        try:
            return max(0, int(retry_after))
        except (TypeError, ValueError):
            pass
    return 2


def _local_max_tokens(max_tokens, cap=600):
    if not max_tokens:
        return max_tokens
    return min(max_tokens, cap)


_MAX_RETRY_SLEEP = 30


def _api_stream_with_retry(model_name, prompt, max_tokens, backend):
    from .inference_api import generate_stream as api_stream
    from .inference_api import IncompleteStreamError, QuotaExhaustedError
    try:
        yield from api_stream(prompt, model=model_name, max_tokens=max_tokens, provider=backend)
        return
    except Exception as exc:
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        if status not in (429, 500, 502, 503, 504) and not isinstance(exc, IncompleteStreamError):
            print(f'[ROUTER] backend={backend} not retryable: {type(exc).__name__}: {exc}', flush=True)
            raise
        delay = _retry_delay(exc)
        if status == 429 and delay > 300:
            print(
                f'[ROUTER] backend={backend} quota exhausted (retry-after={delay}s); skipping',
                flush=True,
            )
            raise QuotaExhaustedError(f'{backend} quota exhausted (retry in {delay}s)')
        sleep_delay = min(delay, _MAX_RETRY_SLEEP)
        print(
            f'[ROUTER] backend={backend} retrying in {sleep_delay}s after {type(exc).__name__} (status={status})',
            flush=True,
        )
        time.sleep(sleep_delay)
        yield from api_stream(prompt, model=model_name, max_tokens=max_tokens, provider=backend)


def _fallback_chain():
    return _load_models().get('fallback_chain') or []


class ModelRouter:
    @staticmethod
    def select(key):
        return _get_model_config(key)['name']

    @staticmethod
    def generate_stream(prompt, model_key='default', max_tokens=None, allow_fallback=True):
        cfg = _get_model_config(model_key)

        if cfg['backend'] != 'local':
            if api_quota_down():
                if not allow_fallback:
                    raise RuntimeError('all API providers are quota-exhausted')
                print('[ROUTER] quota-down active; skipping primary', flush=True)
            elif _backend_configured(cfg['backend']):
                try:
                    yield from _api_stream_with_retry(cfg['name'], prompt, max_tokens, cfg['backend'])
                    _mark_api_ok()
                    return
                except Exception as exc:
                    print(f'[ROUTER] primary {cfg["backend"]} failed: {type(exc).__name__}: {exc}', flush=True)
                    if not allow_fallback:
                        raise
            elif not allow_fallback:
                raise RuntimeError(f'{cfg["backend"]} API key not configured')

        if allow_fallback:
            rungs = _fallback_chain()
            api_rungs = [r for r in rungs if r.get('backend') != 'local']
            local_rung = next((r for r in rungs if r.get('backend') == 'local'), None)
            if not api_quota_down():
                for attempt in range(1, 4):
                    all_api_skipped = True
                    api_failed = False
                    quota_down = True
                    for rung in api_rungs:
                        backend = rung.get('backend')
                        if not _backend_configured(backend):
                            continue
                        all_api_skipped = False
                        try:
                            yield from _api_stream_with_retry(rung.get('name', ''), prompt, max_tokens, backend)
                            _mark_api_ok()
                            return
                        except QuotaExhaustedError as exc:
                            api_failed = True
                            print(f'[ROUTER] rung {backend} quota-exhausted: {exc}', flush=True)
                        except Exception as exc:
                            api_failed = True
                            status = getattr(getattr(exc, 'response', None), 'status_code', None)
                            if status == 429:
                                print(f'[ROUTER] rung {backend} 429 (quota): {exc}', flush=True)
                            else:
                                quota_down = False
                                print(f'[ROUTER] rung {backend} failed: {type(exc).__name__}: {exc}', flush=True)
                    if all_api_skipped or not api_failed:
                        break
                    if quota_down:
                        _mark_quota_down()
                        print('[ROUTER] all API rungs quota-down (429); going to local immediately', flush=True)
                        break
                    if attempt < 3:
                        delay = 30 * attempt
                        print(f'[ROUTER] all API rungs failed; retrying chain in {delay}s (attempt {attempt + 1}/3)', flush=True)
                        time.sleep(delay)
            if local_rung is not None:
                try:
                    print(f'[ROUTER] local last resort (max_tokens={_local_max_tokens(max_tokens)})', flush=True)
                    yield from local_stream(prompt, max_tokens=_local_max_tokens(max_tokens))
                    return
                except Exception:
                    pass

        try:
            yield from local_stream(prompt, max_tokens=_local_max_tokens(max_tokens))
            return
        except Exception:
            raise
