from unittest.mock import patch

from django.test import SimpleTestCase

from ai.decision_loop import ANSWER_SENTINEL, DecisionLoop, MAX_ITERATIONS, _parse_action
from ai.model_router import _STATE_PATH, reset_quota_state
from ai.retrieval_profiles import matches_domain

import os


def setUpModule():
    reset_quota_state()
    if os.path.exists(_STATE_PATH):
        os.remove(_STATE_PATH)


def tearDownModule():
    reset_quota_state()
    if os.path.exists(_STATE_PATH):
        os.remove(_STATE_PATH)


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

    def test_answer_word_returns_sentinel(self):
        self.assertIs(_parse_action('ANSWER'), ANSWER_SENTINEL)

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

    def test_quota_down_caps_iterations_to_one(self):
        with patch('ai.decision_loop.api_quota_down', return_value=True):
            script = ['TOOL {"tool": "calculate", "expression": "0+1"}', 'Fast answer.']
            loop, _, events, _ = self._loop(script)
        tool_calls = [e for e in events if e['type'] == 'tool_use' and e['tool'] != 'answer']
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(loop.tool_count, 1)
        self.assertEqual(self._tokens(events), 'Fast answer.')

    def test_quota_down_caps_answer_tokens(self):
        with patch('ai.decision_loop.api_quota_down', return_value=True):
            loop, model, events, _ = self._loop(['ANSWER', 'Short answer.'])
        self.assertEqual(self._tokens(events), 'Short answer.')
        self.assertEqual(model.calls[-1]['max_tokens'], 300)

    def test_normal_mode_uses_full_answer_tokens(self):
        _, model, _, _ = self._loop(['ANSWER', 'Full answer.'])
        self.assertEqual(model.calls[-1]['max_tokens'], 1536)


class ContextTests(SimpleTestCase):
    def test_history_content_is_truncated(self):
        loop = DecisionLoop(
            'q', model_key='chat', generate_fn=lambda *a, **k: iter(['x']),
            history=[{'role': 'user', 'content': 'x' * 5000}],
        )
        text = loop._context_text()
        self.assertIn('...[truncated]', text)
        self.assertLess(len(text), 800)

    def test_history_limited_to_six_messages(self):
        loop = DecisionLoop(
            'q', model_key='chat', generate_fn=lambda *a, **k: iter(['x']),
            history=[{'role': 'user', 'content': 'm'} for _ in range(12)],
        )
        text = loop._context_text()
        self.assertEqual(text.count('user: m'), 6)


class SearchToolTests(SimpleTestCase):
    def _run(self, info, **kwargs):
        loop = DecisionLoop('q', model_key='chat', generate_fn=lambda *a, **k: iter(['x']), **kwargs)
        with patch('ai.decision_loop.RetrievalService') as svc:
            svc.return_value.execute.return_value = info
            result = loop._search('the query')
        return loop, result

    def test_required_sources_forwarded_to_retrieval(self):
        loop = DecisionLoop(
            'q', model_key='chat', generate_fn=lambda *a, **k: iter(['x']),
            intent='medical', required_sources=['who.int'],
        )
        with patch('ai.decision_loop.RetrievalService') as svc:
            loop._search('flu guidance')
        svc.return_value.execute.assert_called_once_with(
            'flu guidance', intent='medical', required_sources=['who.int'],
        )

    def test_coverage_report_included_in_result(self):
        _, result = self._run({
            'results': [],
            'coverage': {
                'required': ['who.int', 'cdc.gov'],
                'found': ['cdc.gov'],
                'missing': ['who.int'],
            },
        })
        self.assertIn('Required authorities: who.int, cdc.gov', result)
        self.assertIn('Found: cdc.gov', result)
        self.assertIn('Searched but no relevant results found: who.int', result)

    def test_required_domain_results_shown_first(self):
        results = [
            {'url': 'https://pubmed.ncbi.nlm.nih.gov/1', 'title': 'Pubmed one', 'snippet': 'a'},
            {'url': 'https://www.who.int/news/item/1', 'title': 'WHO page', 'snippet': 'b'},
            {'url': 'https://pubmed.ncbi.nlm.nih.gov/2', 'title': 'Pubmed two', 'snippet': 'c'},
        ]
        _, result = self._run({'results': results, 'coverage': {'required': ['who.int'], 'found': ['who.int']}})
        who_pos = result.index('URL: https://www.who.int/news/item/1')
        pubmed1_pos = result.index('URL: https://pubmed.ncbi.nlm.nih.gov/1')
        pubmed2_pos = result.index('URL: https://pubmed.ncbi.nlm.nih.gov/2')
        self.assertLess(who_pos, pubmed1_pos)
        self.assertLess(who_pos, pubmed2_pos)

    def test_prioritize_required_uses_effective_required(self):
        results = [
            {'url': 'https://www.who.int/news/item/1', 'title': 'WHO page'},
            {'url': 'https://nasa.gov/article', 'title': 'NASA page'},
        ]
        ordered = DecisionLoop._prioritize_required(results, {'required': ['who.int', 'cdc.gov']})
        self.assertEqual(ordered[0]['url'], 'https://www.who.int/news/item/1')
        self.assertTrue(matches_domain(ordered[0]['url'], 'who.int'))

    def test_no_coverage_leaves_order_unchanged(self):
        results = [{'url': 'https://a.com/1', 'title': 'A'}, {'url': 'https://b.com/2', 'title': 'B'}]
        self.assertEqual(DecisionLoop._prioritize_required(results, {}), results)

    def test_found_domain_always_visible_even_beyond_top_six(self):
        results = [
            {'url': f'https://cdc.gov/page/{i}', 'title': f'CDC {i}'} for i in range(8)
        ] + [{'url': 'https://www.who.int/news/item/1', 'title': 'WHO page', 'snippet': 'w'}]
        _, result = self._run({
            'results': results,
            'coverage': {'required': ['who.int', 'cdc.gov'], 'found': ['who.int', 'cdc.gov']},
        })
        self.assertIn('URL: https://www.who.int/news/item/1', result)
