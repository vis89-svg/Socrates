from django.test import SimpleTestCase

from ai.verifier import FactVerifier, _content_supports


def _result(url, snippet=''):
    return {'url': url, 'title': '', 'snippet': snippet, 'page_text': ''}


class ContentSupportTests(SimpleTestCase):
    def test_substring_support(self):
        self.assertTrue(_content_supports('The company Acme Corp was founded in 1998.', 'Acme Corp'))
        self.assertFalse(_content_supports('The company Globex Inc was founded in 1998.', 'Acme Corp'))

    def test_numeric_value_requires_presence(self):
        self.assertTrue(_content_supports('Founded in 1998 by two engineers.', '1998'))
        self.assertFalse(_content_supports('Founded in the late nineties.', '1998'))

    def test_token_overlap_for_longer_values(self):
        self.assertTrue(_content_supports('OpenAI headquarters moved to San Francisco in 2023.', 'San Francisco'))
        self.assertFalse(_content_supports('The firm is based in New York.', 'San Francisco'))

    def test_url_domain_support(self):
        self.assertTrue(_content_supports('Visit the site at example.com for details.', 'https://example.com'))
        self.assertFalse(_content_supports('No website is listed in this article.', 'https://example.com'))

    def test_no_content_is_neutral(self):
        self.assertIsNone(_content_supports('', 'Acme Corp'))
        self.assertIsNone(_content_supports(None, 'Acme Corp'))

    def test_anchored_value_supported(self):
        self.assertTrue(_content_supports('NVIDIA was founded in 1993.', '1993', ['founded', 'established', 'incorporated']))
        self.assertTrue(_content_supports('NVIDIA Corporation was established in 1993.', '1993', ['founded', 'established', 'incorporated']))

    def test_value_in_unrelated_context_rejected(self):
        self.assertFalse(_content_supports(
            'In 1993 NVIDIA shipped its first GPU. The firm was founded in 1990.',
            '1993', ['founded', 'established', 'incorporated']))

    def test_keywords_on_other_sentence_do_not_anchor(self):
        self.assertFalse(_content_supports(
            'Acme released the 1998 catalog. The company was founded in 1990.',
            '1998', ['founded', 'established', 'incorporated']))

    def test_value_without_any_keyword_is_neutral_accept(self):
        self.assertTrue(_content_supports(
            'In 1993 NVIDIA shipped its first GPU.',
            '1993', ['founded', 'established', 'incorporated']))

    def test_multiline_sentence_anchor(self):
        self.assertTrue(_content_supports(
            'Overview\nNVIDIA was founded in 1993.\nDetails',
            '1993', ['founded', 'established']))


class VerifierContentTests(SimpleTestCase):
    def test_value_in_all_sources_is_high(self):
        results = [
            _result('https://example.com/a', 'Acme Corp was founded in 1998.'),
            _result('https://example.com/b', 'Acme Corp is a software company.'),
            _result('https://example.com/c', 'Acme Corp raised new funding.'),
        ]
        out = FactVerifier.verify(
            {'company_name': {'value': 'Acme Corp', 'sources': [{'url': r['url']} for r in results]}},
            results,
        )
        self.assertEqual(out['company_name']['confidence'], 'high')
        self.assertEqual(len(out['company_name']['sources']), 3)

    def test_value_in_none_of_the_sources_downgraded(self):
        results = [
            _result('https://example.com/a', 'Globex Inc was founded in 1998.'),
            _result('https://example.com/b', 'Globex Inc is a software company.'),
            _result('https://example.com/c', 'Globex Inc raised new funding.'),
        ]
        out = FactVerifier.verify(
            {'company_name': {'value': 'Acme Corp', 'sources': [{'url': r['url']} for r in results]}},
            results,
        )
        self.assertEqual(out['company_name']['confidence'], 'none')
        self.assertEqual(out['company_name']['sources'], [])
        self.assertIn('did not contain this value', out['company_name']['note'])

    def test_partial_support_keeps_only_matching_sources(self):
        results = [
            _result('https://example.com/a', 'Acme Corp was founded in 1998.'),
            _result('https://example.com/b', 'Some other company news.'),
            _result('https://example.com/c', 'Unrelated article about markets.'),
        ]
        out = FactVerifier.verify(
            {'founded': {'value': '1998', 'sources': [{'url': r['url']} for r in results]}},
            results,
        )
        self.assertEqual(out['founded']['confidence'], 'low')
        self.assertEqual(out['founded']['sources'], ['https://example.com/a'])

    def test_fabricated_url_is_dropped(self):
        results = [_result('https://example.com/a', 'Acme Corp details here.')]
        out = FactVerifier.verify(
            {'company_name': {'value': 'Acme Corp', 'sources': [{'url': 'https://invented.example/x'}]}},
            results,
        )
        self.assertEqual(out['company_name']['sources'], [])
        self.assertEqual(out['company_name']['confidence'], 'none')

    def test_source_without_content_is_neutral(self):
        results = [
            _result('https://example.com/a'),
            _result('https://example.com/b'),
            _result('https://example.com/c'),
        ]
        out = FactVerifier.verify(
            {'company_name': {'value': 'Acme Corp', 'sources': [{'url': r['url']} for r in results]}},
            results,
        )
        self.assertEqual(out['company_name']['confidence'], 'high')
        self.assertEqual(len(out['company_name']['sources']), 3)

    def test_claim_rejected_when_value_in_unrelated_context(self):
        results = [
            _result('https://example.com/a', 'In 1993 Acme shipped its first GPU. The firm was founded in 1990.'),
            _result('https://example.com/b', 'Acme was founded in 1993.'),
        ]
        out = FactVerifier.verify(
            {'founded': {'value': '1993', 'sources': [{'url': r['url']} for r in results]}},
            results,
        )
        self.assertEqual(out['founded']['sources'], ['https://example.com/b'])
        self.assertIn('unrelated context', out['founded']['note'])

    def test_claim_supported_only_when_sentence_anchored(self):
        results = [
            _result('https://example.com/a', 'Acme Corp was founded in 1993 by two engineers.'),
            _result('https://example.com/b', 'Acme raised funding in 1993. The company was founded in 1990.'),
        ]
        out = FactVerifier.verify(
            {'founded': {'value': '1993', 'sources': [{'url': r['url']} for r in results]}},
            results,
        )
        self.assertEqual(out['founded']['sources'], ['https://example.com/a'])
        self.assertEqual(out['founded']['confidence'], 'low')
