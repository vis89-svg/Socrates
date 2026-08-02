from unittest.mock import patch

import os
import requests
from django.conf import settings
from django.test import SimpleTestCase, override_settings

from ai.model_router import (
    _STATE_PATH,
    ModelRouter,
    _api_stream_with_retry,
    _load_quota_state,
    _local_max_tokens,
    _mark_api_ok,
    _mark_quota_down,
    api_quota_down,
    reset_quota_state,
)
from ai.inference_api import IncompleteStreamError, QuotaExhaustedError


def setUpModule():
    reset_quota_state()
    if os.path.exists(_STATE_PATH):
        os.remove(_STATE_PATH)


def tearDownModule():
    reset_quota_state()
    if os.path.exists(_STATE_PATH):
        os.remove(_STATE_PATH)


class FakeResponse:
    status_code = 429
    headers = {}


class FakeHTTPError(requests.HTTPError):
    def __init__(self, headers=None):
        super().__init__('429 Too Many Requests')
        self.response = FakeResponse()
        self.response.headers = dict(headers or {})


class _QuotaResetMixin:
    def setUp(self):
        reset_quota_state()

    def tearDown(self):
        reset_quota_state()


class ModelRouterRetryTests(_QuotaResetMixin, SimpleTestCase):
    @patch('ai.model_router._has_openrouter', return_value=True)
    def test_retries_once_on_rate_limit(self, _has_or):
        calls = {'n': 0}

        def flaky(prompt, model=None, max_tokens=None, provider='openrouter'):
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

        def failing(prompt, model=None, max_tokens=None, provider='openrouter'):
            calls['n'] += 1
            raise RuntimeError('network down')

        with patch('ai.inference_api.generate_stream', side_effect=failing):
            with self.assertRaises(RuntimeError):
                for _ in ModelRouter.generate_stream('x', model_key='planner', allow_fallback=False):
                    pass
        self.assertEqual(calls['n'], 1)


class ModelRouterChainTests(_QuotaResetMixin, SimpleTestCase):
    @override_settings(GROQ_API_KEY='groq-key', GEMINI_API_KEY='gemini-key')
    @patch('ai.model_router._has_openrouter', return_value=True)
    def test_falls_to_groq_when_openrouter_rate_limited(self, _has_or):
        calls = []

        def api_stream(prompt, model=None, max_tokens=None, provider='openrouter'):
            calls.append(provider)
            if provider == 'openrouter':
                raise FakeHTTPError()
            yield f'{provider}-answer'

        with patch('ai.inference_api.generate_stream', side_effect=api_stream), \
             patch('ai.model_router._persist_state'):
            out = ''.join(ModelRouter.generate_stream('x', model_key='planner'))
        self.assertEqual(out, 'groq-answer')
        self.assertEqual(calls, ['openrouter', 'openrouter', 'groq'])

    @override_settings(GROQ_API_KEY='')
    @patch('ai.model_router._has_openrouter', return_value=True)
    def test_skips_unconfigured_rung(self, _has_or):
        calls = []

        def api_stream(prompt, model=None, max_tokens=None, provider='openrouter'):
            calls.append(provider)
            if provider == 'openrouter':
                raise FakeHTTPError()
            yield 'gemini-answer'

        with patch('ai.inference_api.generate_stream', side_effect=api_stream), \
             patch('ai.model_router._persist_state'):
            out = ''.join(ModelRouter.generate_stream('x', model_key='planner'))
        self.assertEqual(out, 'gemini-answer')
        self.assertEqual(calls, ['openrouter', 'openrouter', 'gemini'])

    @override_settings(GROQ_API_KEY='groq-key', GEMINI_API_KEY='gemini-key')
    @patch('ai.model_router._has_openrouter', return_value=True)
    @patch('ai.model_router.time.sleep')
    def test_local_as_last_resort(self, sleep, _has_or):
        def api_stream(prompt, model=None, max_tokens=None, provider='openrouter'):
            raise FakeHTTPError()

        def local_stream(prompt, max_tokens=None):
            yield 'local-answer'

        with patch('ai.inference_api.generate_stream', side_effect=api_stream), \
             patch('ai.model_router.local_stream', side_effect=local_stream), \
             patch('ai.model_router._persist_state'):
            out = ''.join(ModelRouter.generate_stream('x', model_key='planner'))
        self.assertEqual(out, 'local-answer')
        self.assertEqual(sleep.call_count, 3)
        self.assertTrue(api_quota_down())

    @override_settings(GROQ_API_KEY='groq-key')
    @patch('ai.model_router._has_openrouter', return_value=False)
    def test_fallback_key_starts_chain(self, _has_or):
        def api_stream(prompt, model=None, max_tokens=None, provider='openrouter'):
            yield 'groq-answer'

        with patch('ai.inference_api.generate_stream', side_effect=api_stream), \
             patch('ai.model_router._persist_state'):
            out = ''.join(ModelRouter.generate_stream('x', model_key='fallback'))
        self.assertEqual(out, 'groq-answer')

    @patch('ai.model_router._has_openrouter', return_value=False)
    def test_unconfigured_backend_raises_without_fallback(self, _has_or):
        with self.assertRaises(RuntimeError):
            for _ in ModelRouter.generate_stream('x', model_key='planner', allow_fallback=False):
                pass


class RetryDelayTests(SimpleTestCase):
    @patch('ai.model_router.time.sleep')
    def test_retry_after_is_honored(self, sleep):
        calls = {'n': 0}

        def flaky(prompt, model=None, max_tokens=None, provider='openrouter'):
            calls['n'] += 1
            if calls['n'] == 1:
                raise FakeHTTPError(headers={'Retry-After': '30'})
            yield 'recovered'

        with patch('ai.inference_api.generate_stream', side_effect=flaky):
            out = ''.join(_api_stream_with_retry('m', 'p', None, 'groq'))
        self.assertEqual(out, 'recovered')
        sleep.assert_called_once_with(30)

    @patch('ai.model_router.time.sleep')
    def test_long_retry_after_is_quota_exhausted_and_fails_fast(self, sleep):
        def flaky(prompt, model=None, max_tokens=None, provider='openrouter'):
            raise FakeHTTPError(headers={'Retry-After': '7400'})

        with patch('ai.inference_api.generate_stream', side_effect=flaky):
            with self.assertRaises(QuotaExhaustedError):
                for _ in _api_stream_with_retry('m', 'p', None, 'groq'):
                    pass
        sleep.assert_not_called()

    @patch('ai.model_router.time.sleep')
    def test_long_retry_after_sleep_is_capped(self, sleep):
        calls = {'n': 0}

        def flaky(prompt, model=None, max_tokens=None, provider='openrouter'):
            calls['n'] += 1
            raise FakeHTTPError(headers={'Retry-After': '149'})

        with patch('ai.inference_api.generate_stream', side_effect=flaky):
            with self.assertRaises(requests.HTTPError):
                for _ in _api_stream_with_retry('m', 'p', None, 'groq'):
                    pass
        sleep.assert_called_once_with(30)
        self.assertEqual(calls['n'], 2)

    @patch('ai.model_router.time.sleep')
    def test_plain_rate_limit_uses_two_seconds(self, sleep):
        def flaky(prompt, model=None, max_tokens=None, provider='openrouter'):
            raise FakeHTTPError()

        with patch('ai.inference_api.generate_stream', side_effect=flaky):
            with self.assertRaises(requests.HTTPError):
                for _ in _api_stream_with_retry('m', 'p', None, 'groq'):
                    pass
        sleep.assert_called_once_with(2)

    def test_local_max_tokens_capped(self):
        self.assertEqual(_local_max_tokens(1536), 600)
        self.assertEqual(_local_max_tokens(120), 120)
        self.assertIsNone(_local_max_tokens(None))


class QuotaDownTests(SimpleTestCase):
    def setUp(self):
        reset_quota_state()

    def tearDown(self):
        reset_quota_state()

    @override_settings(GROQ_API_KEY='groq-key', GEMINI_API_KEY='gemini-key')
    @patch('ai.model_router._has_openrouter', return_value=True)
    @patch('ai.model_router.time.sleep')
    def test_quota_down_skips_chain_retries_and_goes_local(self, sleep, _has_or):
        def api_stream(prompt, model=None, max_tokens=None, provider='openrouter'):
            raise FakeHTTPError(headers={'Retry-After': '7400'})

        def local_stream(prompt, max_tokens=None):
            yield 'local-answer'

        with patch('ai.inference_api.generate_stream', side_effect=api_stream), \
             patch('ai.model_router.local_stream', side_effect=local_stream), \
             patch('ai.model_router._persist_state'):
            out = ''.join(ModelRouter.generate_stream('x', model_key='planner'))
        self.assertEqual(out, 'local-answer')
        sleep.assert_not_called()

    @override_settings(GROQ_API_KEY='groq-key', GEMINI_API_KEY='gemini-key')
    @patch('ai.model_router._has_openrouter', return_value=True)
    @patch('ai.model_router.time.sleep')
    def test_local_rung_receives_capped_tokens(self, sleep, _has_or):
        seen = {}

        def api_stream(prompt, model=None, max_tokens=None, provider='openrouter'):
            raise FakeHTTPError(headers={'Retry-After': '7400'})

        def local_stream(prompt, max_tokens=None):
            seen['max_tokens'] = max_tokens
            yield 'local-answer'

        with patch('ai.inference_api.generate_stream', side_effect=api_stream), \
             patch('ai.model_router.local_stream', side_effect=local_stream), \
             patch('ai.model_router._persist_state'):
            ''.join(ModelRouter.generate_stream('x', model_key='planner', max_tokens=1536))
        self.assertEqual(seen['max_tokens'], 600)

    def test_quota_state_marks_down_after_all_quota_failures(self):
        self.assertFalse(api_quota_down())
        self._run_quota_fail()
        self.assertTrue(api_quota_down())

    @override_settings(GROQ_API_KEY='groq-key', GEMINI_API_KEY='gemini-key')
    @patch('ai.model_router._has_openrouter', return_value=True)
    def test_all_plain_429_marks_quota_down_and_skips_chain_sleeps(self, _has_or):
        def api_stream(prompt, model=None, max_tokens=None, provider='openrouter'):
            raise FakeHTTPError()

        sleeps = []
        with patch('ai.inference_api.generate_stream', side_effect=api_stream), \
             patch('ai.model_router.local_stream', return_value=iter(['local'])), \
             patch('ai.model_router.time.sleep', side_effect=lambda s: sleeps.append(s)), \
             patch('ai.model_router._persist_state'):
            out = ''.join(ModelRouter.generate_stream('x', model_key='planner'))
        self.assertEqual(out, 'local')
        self.assertTrue(api_quota_down())
        self.assertFalse([s for s in sleeps if s >= 25], f'chain sleeps used: {sleeps}')

    @override_settings(GROQ_API_KEY='groq-key', GEMINI_API_KEY='gemini-key')
    @patch('ai.model_router._has_openrouter', return_value=True)
    def test_quota_down_skips_all_api_probing(self, _has_or):
        with patch('ai.model_router._persist_state'):
            _mark_quota_down()
        calls = {'api': 0, 'local': 0}

        def api_stream(prompt, model=None, max_tokens=None, provider='openrouter'):
            calls['api'] += 1
            raise AssertionError('API should not be probed while quota-down')

        def local_stream(prompt, max_tokens=None):
            calls['local'] += 1
            yield 'local-answer'

        with patch('ai.inference_api.generate_stream', side_effect=api_stream), \
             patch('ai.model_router.local_stream', side_effect=local_stream), \
             patch('ai.model_router.time.sleep', side_effect=AssertionError('should not sleep')):
            out = ''.join(ModelRouter.generate_stream('x', model_key='planner'))
        self.assertEqual(out, 'local-answer')
        self.assertEqual(calls['api'], 0)
        self.assertEqual(calls['local'], 1)

    @override_settings(GROQ_API_KEY='groq-key', GEMINI_API_KEY='gemini-key')
    @patch('ai.model_router._has_openrouter', return_value=True)
    def test_quota_state_clears_after_api_success(self, _has_or):
        self._run_quota_fail()
        self.assertTrue(api_quota_down())
        with patch('ai.model_router._persist_state'):
            _mark_api_ok()
        self.assertFalse(api_quota_down())

    def test_quota_state_expires(self):
        cases = [('301', False), ('299', True)]
        for now, expected in cases:
            with patch('ai.model_router._QUOTA_STATE', {'down': True, 'at': 0.0, 'ttl': 300}):
                with patch('ai.model_router.time.time', return_value=float(now)):
                    self.assertEqual(api_quota_down(), expected, now)

    def test_quota_state_persists_to_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            tmp_path = f.name
        try:
            with patch('ai.model_router._STATE_PATH', tmp_path), \
                 patch('ai.model_router.time.time', return_value=100.0):
                _mark_quota_down()
            reset_quota_state()
            with patch('ai.model_router._STATE_PATH', tmp_path), \
                 patch('ai.model_router.time.time', return_value=100.0):
                _load_quota_state()
                self.assertTrue(api_quota_down())
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    @override_settings(GROQ_API_KEY='groq-key', GEMINI_API_KEY='gemini-key')
    @patch('ai.model_router._has_openrouter', return_value=True)
    def _run_quota_fail(self, _has_or):
        def api_stream(prompt, model=None, max_tokens=None, provider='openrouter'):
            raise FakeHTTPError(headers={'Retry-After': '7400'})

        def local_stream(prompt, max_tokens=None):
            yield 'local'

        with patch('ai.inference_api.generate_stream', side_effect=api_stream), \
             patch('ai.model_router.local_stream', side_effect=local_stream), \
             patch('ai.model_router.time.sleep'), \
             patch('ai.model_router._persist_state'):
            ''.join(ModelRouter.generate_stream('x', model_key='planner'))


class IncompleteStreamRetryTests(_QuotaResetMixin, SimpleTestCase):
    def test_incomplete_stream_is_retried_once(self):
        calls = {'n': 0}

        def api_stream(prompt, model=None, max_tokens=None, provider='openrouter'):
            calls['n'] += 1
            if calls['n'] == 1:
                raise IncompleteStreamError('stream ended before completion')
            yield 'full-answer'

        with patch('ai.inference_api.generate_stream', side_effect=api_stream):
            out = ''.join(_api_stream_with_retry('m', 'p', None, 'groq'))
        self.assertEqual(out, 'full-answer')
        self.assertEqual(calls['n'], 2)

    def test_incomplete_stream_retry_failure_propagates(self):
        def api_stream(prompt, model=None, max_tokens=None, provider='openrouter'):
            raise IncompleteStreamError('stream ended before completion')

        with patch('ai.inference_api.generate_stream', side_effect=api_stream):
            with self.assertRaises(IncompleteStreamError):
                for _ in _api_stream_with_retry('m', 'p', None, 'groq'):
                    pass

    def test_incomplete_stream_advances_fallback_chain(self):
        calls = []

        def api_stream(prompt, model=None, max_tokens=None, provider='openrouter'):
            calls.append(provider)
            if provider == 'openrouter':
                raise IncompleteStreamError('stream ended before completion')
            yield 'groq-answer'

        with patch('ai.inference_api.generate_stream', side_effect=api_stream):
            out = ''.join(ModelRouter.generate_stream('x', model_key='planner'))
        self.assertEqual(out, 'groq-answer')
        self.assertEqual(calls, ['openrouter', 'openrouter', 'groq'])


class StreamParsingTests(SimpleTestCase):
    def _run(self, lines, provider='groq'):
        class FakeResp:
            def __init__(self, lines):
                self.lines = lines

            def raise_for_status(self):
                pass

            def iter_lines(self, decode_unicode=True):
                return iter(self.lines)

        with patch.object(settings, 'GROQ_API_KEY', 'test-key'), \
             patch.object(settings, 'GROQ_BASE_URL', 'https://api.groq.com/openai/v1'), \
             patch('ai.inference_api.requests.post', return_value=FakeResp(lines)):
            from ai.inference_api import generate_stream
            return ''.join(generate_stream('p', 'm', provider=provider))

    def test_normal_stop_is_complete(self):
        out = self._run([
            'data: {"choices":[{"delta":{"content":"hel"}}]}',
            'data: {"choices":[{"delta":{"content":"lo"},"finish_reason":"stop"}]}',
            'data: [DONE]',
        ])
        self.assertEqual(out, 'hello')

    def test_finish_reason_length_is_complete(self):
        out = self._run([
            'data: {"choices":[{"delta":{"content":"a"}}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"length"}]}',
            'data: [DONE]',
        ])
        self.assertEqual(out, 'a')

    def test_done_without_finish_reason_raises(self):
        with self.assertRaises(IncompleteStreamError):
            self._run([
                'data: {"choices":[{"delta":{"content":"partial answ"}}]}',
                'data: [DONE]',
            ])

    def test_connection_close_without_done_raises(self):
        with self.assertRaises(IncompleteStreamError):
            self._run([
                'data: {"choices":[{"delta":{"content":"partial"}}]}',
            ])

    def test_error_chunk_raises(self):
        with self.assertRaises(IncompleteStreamError):
            self._run([
                'data: {"choices":[{"delta":{"content":"partial"}}]}',
                'data: {"error":{"message":"generation aborted"}}',
            ])
