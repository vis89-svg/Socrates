from django.conf import settings

_model = None


def get_model():
    global _model
    if _model is None:
        from llama_cpp import Llama
        _model = Llama(
            model_path=settings.MODEL_PATH,
            n_ctx=settings.MODEL_CONTEXT_SIZE,
            n_threads=settings.MODEL_N_THREADS,
            verbose=False,
        )
    return _model
