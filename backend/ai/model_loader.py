import os
from django.conf import settings

_model = None


def _resolve_model_path():
    path = settings.MODEL_PATH
    if not path:
        return path
    if os.path.isabs(path) or os.path.exists(path):
        return path
    candidate = os.path.join(settings.BASE_DIR, path)
    if os.path.exists(candidate):
        return candidate
    return path


def get_model():
    global _model
    if _model is None:
        from llama_cpp import Llama
        _model = Llama(
            model_path=_resolve_model_path(),
            n_ctx=settings.MODEL_CONTEXT_SIZE,
            n_threads=settings.MODEL_N_THREADS,
            verbose=False,
        )
    return _model
