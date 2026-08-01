import json
import os

from django.test import SimpleTestCase

from ai.query_expander import QueryExpander
from ai.retrieval_service import RetrievalService
from ai.extractor import Extractor
from ai.verifier import FactVerifier
from ai.consistency import ConsistencyChecker

CORPUS_PATH = os.path.join(os.path.dirname(__file__), 'corpus.json')


def load_corpus():
    with open(CORPUS_PATH, encoding='utf-8') as f:
        data = json.load(f)
    prompts = []
    for category, items in data['categories'].items():
        for prompt in items:
            prompts.append({'category': category, 'prompt': prompt})
    return prompts


def load_expected_intent():
    with open(CORPUS_PATH, encoding='utf-8') as f:
        data = json.load(f)
    return data.get('expected_intent', {})


class CorpusSuiteTests(SimpleTestCase):
    def test_corpus_is_complete(self):
        prompts = load_corpus()
        self.assertGreaterEqual(len(prompts), 30, 'corpus must contain at least 30 prompts')
        categories = {}
        for p in prompts:
            categories[p['category']] = categories.get(p['category'], 0) + 1
        self.assertGreaterEqual(len(categories), 8, 'corpus must span at least 8 categories')
        for cat, count in categories.items():
            self.assertGreaterEqual(count, 3, f'category {cat} needs at least 3 prompts')


class QueryExpansionRegressionTests(SimpleTestCase):
    def test_hardware_prompts_produce_site_queries(self):
        for p in load_corpus():
            if p['category'] != 'ai_hardware':
                continue
            expanded = QueryExpander.expand(p['prompt'])
            with self.subTest(prompt=p['prompt']):
                self.assertGreaterEqual(len(expanded), 5)
                self.assertTrue(
                    any(q.startswith('site:') for q in expanded),
                    f'{p["prompt"]} should produce a site:-scoped query',
                )

    def test_non_hardware_prompts_do_not_require_site_queries(self):
        for p in load_corpus():
            if p['category'] in ('ai_hardware', 'cpu'):
                continue
            expanded = QueryExpander.expand(p['prompt'])
            with self.subTest(prompt=p['prompt']):
                self.assertGreaterEqual(len(expanded), 2)


class SchemaSelectionRegressionTests(SimpleTestCase):
    def test_hardware_queries_select_hardware_schema(self):
        for p in load_corpus():
            if p['category'] not in ('ai_hardware', 'cpu', 'phones'):
                continue
            with self.subTest(prompt=p['prompt']):
                self.assertEqual(Extractor.select_schema(p['prompt']), 'hardware',
                                 f'{p["prompt"]} should map to hardware schema')

    def test_company_queries_select_company_schema(self):
        for p in load_corpus():
            if p['category'] != 'companies':
                continue
            with self.subTest(prompt=p['prompt']):
                self.assertEqual(Extractor.select_schema(p['prompt']), 'company',
                                 f'{p["prompt"]} should map to company schema')


class DedupeRegressionTests(SimpleTestCase):
    def test_tracking_params_and_fragments_collapse(self):
        svc = RetrievalService()
        results = [
            {'url': 'https://nvidia.com/blackwell?utm_source=x&ref=abc', 'title': 'A', 'snippet': '1'},
            {'url': 'https://nvidia.com/blackwell', 'title': 'B', 'snippet': '2'},
            {'url': 'https://reuters.com/tech/nvidia-blackwell#top', 'title': 'C', 'snippet': '3'},
            {'url': 'https://reuters.com/tech/nvidia-blackwell', 'title': 'D', 'snippet': '4'},
            {'url': 'https://www.tomshardware.com/news/nvidia-blackwell', 'title': 'E', 'snippet': '5'},
        ]
        deduped = svc._dedupe(results)
        self.assertEqual(len(deduped), 3)
        urls = {r['url'] for r in deduped}
        self.assertNotIn('?utm_source=x', urls)
        self.assertNotIn('#top', urls)

    def test_canonical_url_normalized(self):
        svc = RetrievalService()
        out = svc._dedupe([{'url': 'https://NVIDIA.com/Blackwell/?utm_source=x', 'title': 'T', 'snippet': 'a'}])
        self.assertEqual(out[0]['url'], 'https://nvidia.com/blackwell')


class VerifierRegressionTests(SimpleTestCase):
    def _verify(self, sources):
        return FactVerifier.verify({'field': {'value': 'X', 'sources': sources}}, [])

    def test_confidence_thresholds(self):
        one = self._verify([{'url': 'https://example.com/a', 'published_date': '2026-07-01'}])
        self.assertEqual(one['field']['confidence'], 'low')
        two = self._verify([{'url': 'https://example.com/a', 'published_date': '2026-07-01'},
                            {'url': 'https://example.com/b', 'published_date': '2026-07-02'}])
        self.assertEqual(two['field']['confidence'], 'medium')
        three = self._verify([{'url': 'https://example.com/a', 'published_date': '2026-07-01'},
                              {'url': 'https://example.com/b', 'published_date': '2026-07-02'},
                              {'url': 'https://example.com/c', 'published_date': '2026-07-03'}])
        self.assertEqual(three['field']['confidence'], 'high')

    def test_stale_sources_downgraded(self):
        stale = self._verify([{'url': 'https://example.com/a', 'published_date': '2020-01-01'},
                              {'url': 'https://example.com/b', 'published_date': '2020-01-02'},
                              {'url': 'https://example.com/c', 'published_date': '2020-01-03'}])
        self.assertEqual(stale['field']['confidence'], 'medium')
        self.assertIn('stale', stale['field']['note'])

    def test_blocked_sources_ignored(self):
        out = self._verify([{'url': 'https://youtube.com/x', 'published_date': '2026-07-01'}])
        self.assertEqual(out['field']['confidence'], 'none')


class ConsistencyRegressionTests(SimpleTestCase):
    def test_memory_type_contradiction_flagged(self):
        verified = {
            'memory_type': {'value': 'HBM3E and GDDR7', 'sources': [{'url': 'https://a.com'}],
                            'published_dates': ['2026-01-01'], 'confidence': 'medium', 'note': ''},
        }
        checks = ConsistencyChecker.check(verified)
        fails = [c for c in checks if c['rule'] == 'memory_type_contradiction']
        self.assertEqual(len(fails), 1)
        self.assertEqual(fails[0]['status'], 'fail')

    def test_future_release_flagged(self):
        verified = {
            'release_date': {'value': 'Q1 2027 (January 2027)', 'sources': [{'url': 'https://a.com'}],
                             'published_dates': ['2026-01-01'], 'confidence': 'medium', 'note': ''},
        }
        checks = ConsistencyChecker.check(verified)
        warns = [c for c in checks if c['rule'] == 'future_release']
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0]['status'], 'warn')

    def test_stale_latest_claim_flagged(self):
        verified = {
            'status': {'value': 'latest generation', 'sources': [{'url': 'https://a.com'}],
                       'published_dates': ['2020-06-01'], 'confidence': 'low', 'note': ''},
        }
        checks = ConsistencyChecker.check(verified)
        fails = [c for c in checks if c['rule'] == 'stale_latest_claim']
        self.assertEqual(len(fails), 1)
        self.assertEqual(fails[0]['status'], 'fail')

    def test_generation_order_inverted_flagged(self):
        verified = {
            'release_date': {'value': 'Released May 2024', 'sources': [{'url': 'https://a.com'}],
                             'published_dates': ['2026-01-01'], 'confidence': 'high', 'note': ''},
            'previous_generation': {'value': 'Predecessor released June 2026', 'sources': [{'url': 'https://b.com'}],
                                    'published_dates': ['2026-01-01'], 'confidence': 'medium', 'note': ''},
        }
        checks = ConsistencyChecker.check(verified)
        fails = [c for c in checks if c['rule'] == 'generation_order']
        self.assertEqual(len(fails), 1)
        self.assertEqual(fails[0]['status'], 'fail')
