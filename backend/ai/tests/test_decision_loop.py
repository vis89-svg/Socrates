from unittest.mock import patch

from django.test import SimpleTestCase

from ai.decision_loop import DecisionLoop, MAX_ITERATIONS, _parse_action


class FakeModel:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def __call__(self, prompt, model_key='chat', max_tokens=None):
        self.calls.append({'model_key': model_key, 'max_tokens': max_tokens})
        text = self.outputs[min(len(self.outputs) - 1, len(self.calls) - 1)]
        return iter([text])


class ParseActionTests(SimpleTestCase):
    def test_plain_json_tool_call(self):
        self.assertEqual(_parse_action('{"tool": "search", "query": "x"}'), ('search', {'query': 'x'}))

    def test_tool_prefixed_call(self):
        self.assertEqual(
            _parse_action('TOOL {"tool": "calculate", "expression": "2+2"}'),
            ('calculate', {'expression': '2+2'}),
        )

    def test_fenced_json_call(self):
        text = '```json\n{"tool": "fetch_url", "url": "https://a.com"}\n```'
        self.assertEqual(_parse_action(text), ('fetch_url', {'url': 'https://a.com'}))

    def test_extra_reason_field_is_tolerated(self):
        self.assertEqual(
            _parse_action('{"tool": "search", "query": "q", "reason": "need fresh data"}'),
            ('search', {'query': 'q', 'reason': 'need fresh data'}),
        )

    def test_plain_answer_text_is_none(self):
        self.assertIsNone(_parse_action('The answer is 42.'))

    def test_answer_word_is_none(self):
        self.assertIsNone(_parse_action('ANSWER'))

    def test_malformed_json_is_none(self):
        self.assertIsNone(_parse_action('{"tool": "search"'))
        self.assertIsNone(_parse_action('TOOL {"tool": '))


class DecisionLoopTests(SimpleTestCase):
    def _loop(self, outputs, **kwargs):
        model = FakeModel(outputs)
        loop = DecisionLoop('What is 2+2?', model_key='chat', generate_fn=model, **kwargs)
        with patch.object(DecisionLoop, '_dispatch', return_value='canned result') as dispatch:
            events = list(loop.run())
        return loop, model, events, dispatch

    def _tokens(self, events):
        return ''.join(e['content'] for e in events if e['type'] == 'token')

    def test_tool_then_answer(self):
        loop, model, events, dispatch = self._loop([
            'TOOL {"tool": "calculate", "expression": "2+2"}',
            'ANSWER',
            'The result is 4.',
        ])
        dispatch.assert_called_once_with('calculate', {'expression': '2+2'})
        tools = [e for e in events if e['type'] == 'tool_use']
        self.assertEqual(tools[0]['tool'], 'calculate')
        self.assertEqual(tools[1]['tool'], 'answer')
        self.assertEqual(self._tokens(events), 'The result is 4.')
        self.assertEqual(loop.final_text, 'The result is 4.')
        self.assertEqual(len(loop.transcript), 2)
        self.assertEqual(model.calls[0]['model_key'], 'chat')

    def test_search_yields_search_results_event(self):
        _, _, events, _ = self._loop([
            'TOOL {"tool": "search", "query": "news"}',
            'ANSWER',
            'Here it is.',
        ])
        tools = [e for e in events if e['type'] == 'tool_use']
        self.assertEqual(tools[0]['tool'], 'search')
        search_events = [e for e in events if e['type'] == 'search_results']
        self.assertEqual(len(search_events), 1)

    def test_web_search_forces_initial_search(self):
        _, _, events, dispatch = self._loop(['ANSWER', 'Done.'], web_search=True)
        tools = [e['tool'] for e in events if e['type'] == 'tool_use']
        self.assertEqual(tools[0], 'search')
        self.assertEqual(tools[-1], 'answer')
        dispatch.assert_any_call('search', {'query': 'What is 2+2?'})

    def test_strikes_then_answer(self):
        loop, _, events, _ = self._loop(['garbage one', 'garbage two', 'Final text.'])
        self.assertEqual(loop.strikes, 2)
        self.assertEqual(self._tokens(events), 'Final text.')

    def test_iteration_cap(self):
        script = [f'TOOL {{"tool": "calculate", "expression": "{i}+1"}}' for i in range(MAX_ITERATIONS)]
        script.append('End.')
        loop, _, events, _ = self._loop(script)
        tool_calls = [e for e in events if e['type'] == 'tool_use' and e['tool'] != 'answer']
        self.assertEqual(len(tool_calls), MAX_ITERATIONS)
        self.assertEqual(loop.tool_count, MAX_ITERATIONS)
        self.assertEqual(self._tokens(events), 'End.')

    def test_duplicate_tool_call_is_skipped(self):
        loop, _, events, dispatch = self._loop([
            'TOOL {"tool": "search", "query": "news"}',
            'TOOL {"tool": "search", "query": "news"}',
            'TOOL {"tool": "search", "query": "news"}',
            'Final.',
        ])
        dispatch.assert_called_once_with('search', {'query': 'news'})
        self.assertEqual(self._tokens(events), 'Final.')
        tools = [e for e in events if e['type'] == 'tool_use' and e['tool'] != 'answer']
        self.assertEqual(len(tools), 1)

    def test_fallback_model_on_generation_error(self):
        def flaky(prompt, model_key='chat', max_tokens=None):
            if model_key == 'chat':
                raise RuntimeError('api down')
            return iter(['backup answer'])

        loop = DecisionLoop('hi', model_key='chat', generate_fn=flaky)
        events = list(loop.run())
        self.assertEqual(self._tokens(events), 'backup answer')
