from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from ai.model_router import ModelRouter


class FakeResponse:
    status_code = 429


class FakeHTTPError(requests.HTTPError):
    def __init__(self):
        super().__init__('429 Too Many Requests')
        self.response = FakeResponse()


class ModelRouterRetryTests(SimpleTestCase):
    @patch('ai.model_router._has_openrouter', return_value=True)
    def test_retries_once_on_rate_limit(self, _has_or):
        calls = {'n': 0}

        def flaky(prompt, model=None, max_tokens=None):
            calls['n'] += 1
            if calls['n'] == 1:
                raise FakeHTTPError()
            yield 'recovered'

        with patch('ai.inference_api.generate_stream', side_effect=flaky):
            out = ''.join(ModelRouter.generate_stream('x', model_key='planner', allow_fallback=False))
        self.assertEqual(out, 'recovered')
        self.assertEqual(calls['n'], 2)

    @patch('ai.model_router._has_openrouter', return_value=True)
    def test_non_rate_limit_error_is_not_retried(self, _has_or):
        calls = {'n': 0}

        def failing(prompt, model=None, max_tokens=None):
            calls['n'] += 1
            raise RuntimeError('network down')

        with patch('ai.inference_api.generate_stream', side_effect=failing):
            with self.assertRaises(RuntimeError):
                for _ in ModelRouter.generate_stream('x', model_key='planner', allow_fallback=False):
                    pass
        self.assertEqual(calls['n'], 1)
