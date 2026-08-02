from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase

from ai.retrieval_service import RetrievalService
from ai.temporal_constraint import TemporalType, TemporalConstraintEngine


def _dated(url, title, days_old):
    dt = (datetime.now(timezone.utc) - timedelta(days=days_old)).strftime('%Y-%m-%d')
    return {'url': url, 'title': title, 'snippet': 'content', 'published_date': dt}


class TemporalExtractTests(SimpleTestCase):
    def test_today_phrases(self):
        for query in ('weather in kerala today', 'show me now', 'current price of nvidia'):
            with self.subTest(query=query):
                self.assertEqual(TemporalConstraintEngine.extract(query), TemporalType.TODAY)

    def test_week_phrases(self):
        for query in ('nvidia news this week', 'announcements last 7 days'):
            with self.subTest(query=query):
                self.assertEqual(TemporalConstraintEngine.extract(query), TemporalType.LAST_7_DAYS)

    def test_month_phrases(self):
        for query in ('sales figures this month', 'releases last 30 days'):
            with self.subTest(query=query):
                self.assertEqual(TemporalConstraintEngine.extract(query), TemporalType.LAST_30_DAYS)

    def test_year_phrases(self):
        for query in ('revenue this year', 'quarterly results last year'):
            with self.subTest(query=query):
                self.assertEqual(TemporalConstraintEngine.extract(query), TemporalType.LAST_YEAR)

    def test_seasonal(self):
        self.assertEqual(TemporalConstraintEngine.extract('seasonal rainfall forecast'),
                         TemporalType.SEASONAL)

    def test_historical(self):
        self.assertEqual(TemporalConstraintEngine.extract('the company in 1985'),
                         TemporalType.HISTORICAL)
        self.assertEqual(TemporalConstraintEngine.extract('historical overview of the firm'),
                         TemporalType.HISTORICAL)

    def test_no_constraint(self):
        self.assertEqual(TemporalConstraintEngine.extract('tell me about python'), 
                         TemporalType.NO_CONSTRAINT)


class TemporalEnforceTests(SimpleTestCase):
    def test_should_enforce(self):
        for t in (TemporalType.TODAY, TemporalType.LAST_7_DAYS, TemporalType.LAST_30_DAYS,
                  TemporalType.LAST_YEAR, TemporalType.HISTORICAL):
            self.assertTrue(TemporalConstraintEngine.should_enforce(t), t.value)
        for t in (TemporalType.NO_CONSTRAINT, TemporalType.SEASONAL):
            self.assertFalse(TemporalConstraintEngine.should_enforce(t), t.value)

    def test_filter_drops_stale_keeps_fresh(self):
        results = [
            _dated('https://example.com/fresh', 'fresh today', 0),
            _dated('https://example.com/week-old', 'week old', 6),
            _dated('https://example.com/stale', 'stale', 30),
        ]
        out = TemporalConstraintEngine.filter_results(results, TemporalType.TODAY)
        self.assertEqual([r['url'] for r in out], ['https://example.com/fresh'])

    def test_filter_last_30_days(self):
        results = [
            _dated('https://example.com/ten', 'ten days', 10),
            _dated('https://example.com/old', 'old', 400),
        ]
        out = TemporalConstraintEngine.filter_results(results, TemporalType.LAST_30_DAYS)
        self.assertEqual([r['url'] for r in out], ['https://example.com/ten'])

    def test_filter_keeps_undated_results(self):
        results = [
            _dated('https://example.com/stale', 'stale', 30),
            {'url': 'https://example.com/nodate', 'title': 'no date', 'snippet': 'x'},
        ]
        out = TemporalConstraintEngine.filter_results(results, TemporalType.TODAY)
        self.assertEqual([r['url'] for r in out], ['https://example.com/nodate'])

    def test_filter_no_constraint_is_identity(self):
        results = [_dated('https://example.com/a', 'a', 400)]
        out = TemporalConstraintEngine.filter_results(results, TemporalType.NO_CONSTRAINT)
        self.assertEqual(out, results)

    def test_expand_query_adds_modifiers(self):
        expanded = TemporalConstraintEngine.expand_query('nvidia', TemporalType.TODAY)
        self.assertGreater(len(expanded), 1)
        self.assertTrue(all('nvidia' in q for q in expanded))


class PipelineRankingTests(SimpleTestCase):
    def test_finance_profile_hits_finance_ranker(self):
        from ai.pipeline_ranking import PIPELINE_RANKERS
        from ai.retrieval_profiles import RetrievalProfile
        self.assertEqual(RetrievalProfile.get('finance')['schema_hint'], 'finance')
        self.assertIn('finance', PIPELINE_RANKERS)

    def test_rank_finance_boosts_fresh_results(self):
        from ai.pipeline_ranking import rank_finance
        results = [
            _dated('https://sec.gov/old', 'old filing', 400),
            _dated('https://sec.gov/fresh', 'fresh filing', 2),
        ]
        out = rank_finance(results)
        self.assertEqual(out[0]['url'], 'https://sec.gov/fresh')


class FakeFetcher:
    @staticmethod
    def is_fetchable(url):
        return False

    @staticmethod
    def fetch(url):
        return None


class TemporalExecuteTests(SimpleTestCase):
    def setUp(self):
        self.svc = RetrievalService()

    @patch('ai.retrieval_service.PageFetcher', FakeFetcher)
    @patch('ai.retrieval_service.search_service')
    def test_execute_filters_stale_results_for_today(self, mock_search):
        mock_search.search.return_value = (
            [
                _dated('https://example.com/fresh', 'news today', 0),
                _dated('https://example.com/stale', 'old news', 30),
            ],
            'fake',
        )
        info = self.svc.execute('latest news today', max_results=5)
        urls = [r['url'] for r in info['results']]
        self.assertIn('https://example.com/fresh', urls)
        self.assertNotIn('https://example.com/stale', urls)
        self.assertEqual(info['temporal_type'], 'today')

    @patch('ai.retrieval_service.PageFetcher', FakeFetcher)
    @patch('ai.retrieval_service.search_service')
    def test_execute_keeps_results_without_temporal_constraint(self, mock_search):
        mock_search.search.return_value = (
            [
                _dated('https://example.com/old', 'python history', 500),
                {'url': 'https://example.com/nodate', 'title': 'undated', 'snippet': 'x'},
            ],
            'fake',
        )
        info = self.svc.execute('history of python', max_results=5)
        urls = {r['url'] for r in info['results']}
        self.assertEqual(urls, {'https://example.com/old', 'https://example.com/nodate'})
        self.assertEqual(info['temporal_type'], 'no_constraint')
