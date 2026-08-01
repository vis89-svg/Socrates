from datetime import datetime, timezone, timedelta

from django.test import SimpleTestCase

from ai.query_expander import QueryExpander
from ai.retrieval_service import RetrievalService
from ai.retrieval_profiles import RetrievalProfile
from ai.query_planner import QueryPlanner
from ai.tests.test_regression import load_corpus, load_expected_intent


class IntentResolutionTests(SimpleTestCase):
    def test_corpus_intents_resolve_as_expected(self):
        expected = load_expected_intent()
        for p in load_corpus():
            if p['prompt'] not in expected:
                continue
            with self.subTest(prompt=p['prompt']):
                profile_id, _ = RetrievalProfile.resolve(p['prompt'])
                self.assertEqual(profile_id, expected[p['prompt']],
                                 f'{p["prompt"]} resolved to {profile_id}, expected {expected[p["prompt"]]}')

    def test_planner_intent_overrides_keywords(self):
        profile_id, _ = RetrievalProfile.resolve('NVIDIA H100 TDP and power consumption',
                                                 planner_intent='investment report')
        self.assertEqual(profile_id, 'investment')

    def test_invalid_planner_intent_falls_back_to_keywords(self):
        profile_id, _ = RetrievalProfile.resolve('NVIDIA H100 TDP and power consumption',
                                                 planner_intent='gibberish route x')
        self.assertEqual(profile_id, 'hardware')

    def test_generic_query_falls_back_to_general(self):
        profile_id, _ = RetrievalProfile.resolve('tell me something interesting')
        self.assertEqual(profile_id, 'general')


class ProfileQueryExpansionTests(SimpleTestCase):
    def test_investment_profile_adds_sec_and_ir_queries(self):
        expanded = QueryExpander.expand('OpenAI latest funding round',
                                        profile=RetrievalProfile.get('investment'))
        self.assertLessEqual(len(expanded), 15)
        for domain in ('sec.gov', 'reuters.com'):
            self.assertTrue(any(q.startswith(f'site:{domain}') for q in expanded),
                            f'investment expansion must contain site:{domain}')
        self.assertTrue(any('earnings' in q for q in expanded),
                        'investment expansion must contain earnings keyword query')
        self.assertTrue(any('10-K' in q for q in expanded))

    def test_investment_ir_domain_resolves_per_vendor(self):
        nvda = QueryExpander.expand('NVIDIA quarterly revenue 2026',
                                    profile=RetrievalProfile.get('investment'))
        self.assertTrue(any(q.startswith('site:investor.nvidia.com') for q in nvda),
                        'NVIDIA query must resolve site:investor.nvidia.com')
        openai = QueryExpander.expand('OpenAI latest funding round',
                                      profile=RetrievalProfile.get('investment'))
        self.assertFalse(any('investor.' in q.split(' ')[0] for q in openai),
                         'OpenAI has no known IR domain; no investor.* site query expected')

    def test_investment_profile_is_restrictive(self):
        profile = RetrievalProfile.get('investment')
        expanded = QueryExpander.expand('OpenAI latest funding round', profile=profile)
        self.assertEqual(expanded[0], 'OpenAI latest funding round')
        for q in expanded[1:]:
            self.assertTrue(q.startswith('site:') or any(kw in q for kw in profile['keywords']),
                            f'non-bare query should be site-scoped or keyword-bearing: {q}')

    def test_hardware_profile_adds_vendor_domains(self):
        expanded = QueryExpander.expand('B200 memory bandwidth vs H200',
                                        profile=RetrievalProfile.get('hardware'))
        for domain in ('nvidia.com', 'amd.com', 'intel.com'):
            self.assertTrue(any(q.startswith(f'site:{domain}') for q in expanded),
                            f'hardware expansion must contain site:{domain}')

    def test_technical_profile_matches_user_spec(self):
        expanded = QueryExpander.expand('python asyncio tutorial',
                                        profile=RetrievalProfile.get('technical'))
        for domain in ('docs.python.org', 'github.com', 'stackoverflow.com'):
            self.assertTrue(any(q.startswith(f'site:{domain}') for q in expanded),
                            f'technical expansion must contain site:{domain}')

    def test_medical_profile_domains(self):
        expanded = QueryExpander.expand('mRNA vaccine side effects',
                                        profile=RetrievalProfile.get('medical'))
        for domain in ('who.int', 'cdc.gov', 'nejm.org', 'thelancet.com'):
            self.assertTrue(any(q.startswith(f'site:{domain}') for q in expanded),
                            f'medical expansion must contain site:{domain}')

    def test_profile_does_not_break_plain_expansion(self):
        for p in load_corpus():
            profile = RetrievalProfile.get('general')
            expanded = QueryExpander.expand(p['prompt'], profile=profile)
            with self.subTest(prompt=p['prompt']):
                self.assertGreaterEqual(len(expanded), 2)


class ProfileRankingTests(SimpleTestCase):
    def setUp(self):
        self.svc = RetrievalService()
        self.results = [
            {'url': 'https://medium.com/whatever/nvidia-earnings', 'title': 'nvidia earnings analysis', 'snippet': 'nvidia revenue'},
            {'url': 'https://sec.gov/Archives/nvidia-10-k.htm', 'title': 'nvidia earnings filing', 'snippet': 'nvidia revenue'},
            {'url': 'https://reddit.com/r/nvidia/earnings-thread', 'title': 'nvidia earnings discussion', 'snippet': 'nvidia revenue'},
        ]

    def test_boosted_domains_rank_above_medium(self):
        ranked = self.svc._rank(self.results, 'nvidia earnings', profile=RetrievalProfile.get('investment'))
        self.assertEqual(ranked[0]['url'], 'https://sec.gov/Archives/nvidia-10-k.htm')

    def test_excluded_domains_rank_last(self):
        ranked = self.svc._rank(self.results, 'nvidia earnings', profile=RetrievalProfile.get('investment'))
        self.assertEqual(ranked[-1]['url'], 'https://reddit.com/r/nvidia/earnings-thread')

    def test_no_profile_keeps_original_behavior(self):
        ranked = self.svc._rank(list(self.results), 'nvidia earnings')
        self.assertEqual(len(ranked), 3)


class RecencyModeTests(SimpleTestCase):
    def test_fresh_mode_amplifies_new_docs(self):
        old = datetime.now(timezone.utc) - timedelta(days=400)
        fresh = datetime.now(timezone.utc) - timedelta(days=10)
        s_old = RetrievalProfile.recency_score(old, 'fresh')
        s_fresh = RetrievalProfile.recency_score(fresh, 'fresh')
        self.assertGreater(s_fresh, s_old)

    def test_none_mode_ignores_dates(self):
        old = datetime.now(timezone.utc) - timedelta(days=400)
        new = datetime.now(timezone.utc) - timedelta(days=1)
        self.assertEqual(RetrievalProfile.recency_score(old, 'none'), 0.5)
        self.assertEqual(RetrievalProfile.recency_score(new, 'none'), 0.5)

    def test_balanced_mode_matches_legacy_curve(self):
        new = datetime.now(timezone.utc) - timedelta(days=5)
        self.assertEqual(RetrievalProfile.recency_score(new, 'balanced'), 1.0)


class SourceCoverageTests(SimpleTestCase):
    def test_all_profiles_have_required_domains(self):
        for profile_id in RetrievalProfile.ids():
            with self.subTest(profile=profile_id):
                self.assertIsInstance(RetrievalProfile.get(profile_id).get('required_domains'), list,
                                      f'{profile_id} must declare required_domains')

    def test_required_domain_contracts(self):
        expected = {
            'medical': ['who.int', 'cdc.gov'],
            'investment': ['sec.gov', 'reuters.com'],
            'hardware': ['nvidia.com', 'amd.com'],
            'technical': ['stackoverflow.com', 'github.com'],
            'news': ['reuters.com'],
            'science': ['nature.com'],
            'regulatory': ['europa.eu', 'ftc.gov'],
            'historical': ['wikipedia.org'],
        }
        for profile_id, domains in expected.items():
            with self.subTest(profile=profile_id):
                self.assertEqual(RetrievalProfile.get(profile_id).get('required_domains'), domains)

    def test_required_domains_get_site_queries(self):
        medical = QueryExpander.expand('mRNA vaccine side effects', profile=RetrievalProfile.get('medical'))
        for domain in ('who.int', 'cdc.gov'):
            self.assertTrue(any(q.startswith(f'site:{domain}') for q in medical),
                            f'medical expansion must contain site:{domain}')
        investment = QueryExpander.expand('NVIDIA quarterly revenue 2026', profile=RetrievalProfile.get('investment'))
        for domain in ('sec.gov', 'reuters.com'):
            self.assertTrue(any(q.startswith(f'site:{domain}') for q in investment),
                            f'investment expansion must contain site:{domain}')
        hardware = QueryExpander.expand('B200 memory bandwidth vs H200', profile=RetrievalProfile.get('hardware'))
        for domain in ('nvidia.com', 'amd.com'):
            self.assertTrue(any(q.startswith(f'site:{domain}') for q in hardware),
                            f'hardware expansion must contain site:{domain}')

    def test_coverage_report_classification(self):
        results = [
            {'url': 'https://www.who.int/news-room/fact-sheets', 'title': 'WHO fact sheets'},
            {'url': 'https://cdc.gov/vaccines/', 'title': 'CDC vaccines'},
            {'url': 'https://random-blog.com/opinion', 'title': 'unrelated'},
        ]
        report = RetrievalService._coverage_report(results, ['who.int', 'cdc.gov', 'nih.gov'])
        self.assertEqual(report['found'], ['who.int', 'cdc.gov'])
        self.assertEqual(report['missing'], ['nih.gov'])
        self.assertEqual(report['required'], ['who.int', 'cdc.gov', 'nih.gov'])

    def test_coverage_empty_required(self):
        report = RetrievalService._coverage_report([], [])
        self.assertEqual(report, {'required': [], 'found': [], 'missing': []})

    def test_ensure_coverage_searches_missing_domains(self):
        initial = [
            {'url': 'https://cdc.gov/vaccines/covid', 'title': 'CDC page', 'snippet': 'vaccine'},
            {'url': 'https://random-blog.com/opinion', 'title': 'blog', 'snippet': 'vaccine'},
        ]
        fake_results = {
            'who.int': [{'url': 'https://www.who.int/news-room/questions-and-answers', 'title': 'WHO Q&A', 'snippet': 'vaccine guidance'}],
        }

        def fake_search(query, max_results=5):
            for domain, results in fake_results.items():
                if query.startswith(f'site:{domain}'):
                    return results, 'fake'
            return [], None

        merged, report = RetrievalService._ensure_coverage(initial, ['who.int', 'cdc.gov'],
                                                           'vaccine guidance', search_fn=fake_search)
        self.assertEqual(report['missing'], [])
        self.assertEqual(len(merged), 3)
        urls = {r['url'] for r in merged}
        self.assertIn('https://www.who.int/news-room/questions-and-answers', urls)

    def test_ensure_coverage_skips_wrong_domain_results(self):
        initial = [{'url': 'https://example.com/a', 'title': 'A', 'snippet': 'x'}]

        def fake_search(query, max_results=5):
            return [{'url': 'https://wrong-domain.org/not-who', 'title': 'not who', 'snippet': 'x'}], 'fake'

        merged, report = RetrievalService._ensure_coverage(initial, ['who.int'], 'guidance', search_fn=fake_search)
        self.assertEqual(report['missing'], ['who.int'])
        self.assertEqual(len(merged), 1)

    def test_ensure_coverage_no_required_is_noop(self):
        results = [{'url': 'https://example.com/a', 'title': 'A', 'snippet': 'x'}]
        merged, report = RetrievalService._ensure_coverage(results, [], 'x', search_fn=None)
        self.assertEqual(merged, results)
        self.assertEqual(report['missing'], [])

    def test_summary_includes_coverage_block(self):
        svc = RetrievalService()
        results = [{'url': 'https://www.who.int/x', 'title': 'WHO', 'snippet': 's'}]
        summary = svc._build_summary(results, coverage={'required': ['who.int', 'cdc.gov'], 'found': ['who.int'], 'missing': ['cdc.gov']})
        self.assertIn('Source coverage report', summary)
        self.assertIn('Searched but no relevant results found: cdc.gov', summary)


class PlannerRequiredSourcesTests(SimpleTestCase):
    def test_required_sources_normalized(self):
        plan = QueryPlanner._normalize({
            'rewritten_query': 'q', 'intent': 'medical',
            'required_sources': ['WHO.int', 'site:cdc.gov', 'https://www.nih.gov/', 'who.int'],
        }, 'original')
        self.assertEqual(plan['required_sources'], ['who.int', 'cdc.gov', 'nih.gov'])

    def test_required_sources_capped(self):
        plan = QueryPlanner._normalize({
            'rewritten_query': 'q', 'intent': 'research',
            'required_sources': ['a.com', 'b.com', 'c.com', 'd.com', 'e.com', 'f.com', 'g.com'],
        }, 'original')
        self.assertEqual(len(plan['required_sources']), 6)

    def test_required_sources_missing(self):
        plan = QueryPlanner._normalize({'rewritten_query': 'q', 'intent': 'chat'}, 'original')
        self.assertEqual(plan['required_sources'], [])

    def test_planner_required_sources_extend_profile(self):
        required = RetrievalProfile.effective_required('medical', extra=['fda.gov'], query='mRNA vaccine')
        self.assertEqual(required, ['who.int', 'cdc.gov', 'fda.gov'])
