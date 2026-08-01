from django.test import SimpleTestCase

from ai.golden_facts import GoldenFacts
from ai.extractor import Extractor
from ai.consistency import ConsistencyChecker
from ai.verifier import FactVerifier


def _entry(value, confidence='medium', sources=None, note=''):
    return {
        'value': value,
        'sources': sources or [{'url': 'https://example.com/a', 'published_date': '2026-07-01'}],
        'published_dates': ['2026-07-01'],
        'confidence': confidence,
        'note': note,
    }


class GoldenFactsLookupTests(SimpleTestCase):
    def test_find_entity_by_alias(self):
        self.assertEqual(GoldenFacts.find_entity('NVIDIA H100 TDP'), 'nvidia')
        self.assertEqual(GoldenFacts.find_entity('what about amd revenue'), 'amd')
        self.assertEqual(GoldenFacts.find_entity('OpenAI funding'), 'openai')
        self.assertIsNone(GoldenFacts.find_entity('pancake recipes'))

    def test_product_lookup(self):
        self.assertEqual(GoldenFacts.product_class('H100'), 'datacenter')
        self.assertEqual(GoldenFacts.product_class('RTX 5090'), 'consumer')
        self.assertEqual(GoldenFacts.vendor_of('DGX'), 'nvidia')
        self.assertIsNone(GoldenFacts.product_class('unknown thing'))


class GoldenFactsApplyTests(SimpleTestCase):
    def test_fills_missing_field(self):
        verified = {'company_name': _entry('NVIDIA Corporation'),
                    'founded': _entry(None, confidence='none')}
        out = GoldenFacts.apply(verified, 'NVIDIA company overview')
        self.assertEqual(out['founded']['value'], '1993')
        self.assertEqual(out['founded']['confidence'], 'high')
        self.assertIn('Golden fact', out['founded']['note'])
        self.assertEqual(out['founded']['sources'][0], 'https://www.nvidia.com/en-us/about-nvidia/')

    def test_rejects_conflicting_value(self):
        verified = {'company_name': _entry('NVIDIA Corporation'),
                    'founded': _entry('2008')}
        out = GoldenFacts.apply(verified, 'NVIDIA company overview')
        self.assertEqual(out['founded']['value'], '1993')
        fails = [c for c in out['founded']['checks'] if c['rule'] == 'golden_conflict']
        self.assertEqual(fails[0]['status'], 'fail')
        self.assertIn('2008', fails[0]['detail'])

    def test_matching_value_confirmed(self):
        verified = {'company_name': _entry('AMD'),
                    'headquarters': _entry('Santa Clara, California, USA')}
        out = GoldenFacts.apply(verified, 'AMD company overview')
        self.assertEqual(out['headquarters']['value'], 'Santa Clara, California, USA')
        passes = [c for c in out['headquarters']['checks'] if c['rule'] == 'golden_conflict']
        self.assertEqual(passes[0]['status'], 'pass')

    def test_street_address_hq_counts_as_match(self):
        verified = {'company_name': _entry('AMD'),
                    'headquarters': _entry('2485 Augustine Drive, Santa Clara, CA, 95054')}
        out = GoldenFacts.apply(verified, 'AMD company overview')
        self.assertEqual(out['headquarters']['value'], '2485 Augustine Drive, Santa Clara, CA, 95054')
        fails = [c for c in out['headquarters'].get('checks') or [] if c['status'] == 'fail']
        self.assertEqual(fails, [])

    def test_founded_year_matching_ignores_formatting(self):
        verified = {'company_name': _entry('Apple Inc.'),
                    'founded': _entry('Founded on April 1, 1976')}
        out = GoldenFacts.apply(verified, 'Apple company profile')
        self.assertEqual(out['founded']['value'], '1976')
        fails = [c for c in out['founded']['checks'] if c['status'] == 'fail']
        self.assertEqual(fails, [])

    def test_unknown_entity_untouched(self):
        verified = {'founded': _entry('1901')}
        out = GoldenFacts.apply(verified, 'Some obscure startup overview')
        self.assertEqual(out['founded']['value'], '1901')

    def test_wrong_vendor_attribution_flagged(self):
        verified = {'company_name': _entry('Intel Corporation'),
                    'products': _entry(['Xeon', 'DGX', 'Arc'])}
        out = GoldenFacts.apply(verified, 'Intel products overview')
        fails = [c for c in out['products']['checks'] if c['rule'] == 'wrong_vendor_attribution']
        self.assertEqual(len(fails), 1)
        self.assertIn('DGX', fails[0]['detail'])
        self.assertEqual(fails[0]['status'], 'fail')

    def test_product_class_mixing_warned(self):
        verified = {'company_name': _entry('NVIDIA Corporation'),
                    'products': _entry(['RTX 5090', 'H100', 'CUDA'])}
        out = GoldenFacts.apply(verified, 'NVIDIA products overview')
        warns = [c for c in out['products']['checks'] if c['rule'] == 'product_class_mixing']
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0]['status'], 'warn')

    def test_same_class_products_not_flagged(self):
        verified = {'company_name': _entry('NVIDIA Corporation'),
                    'products': _entry(['H100', 'B200'])}
        out = GoldenFacts.apply(verified, 'NVIDIA datacenter products')
        warns = [c for c in out['products'].get('checks') or [] if c['rule'] == 'product_class_mixing']
        self.assertEqual(warns, [])


class GoldenIntegrationTests(SimpleTestCase):
    def test_company_schema_has_golden_crosscheck_fields(self):
        fields = Extractor._fields_for('company')
        for field in ('founded', 'headquarters', 'ceo', 'company_name', 'official_website'):
            self.assertIn(field, fields)

    def test_verify_pipeline_applies_golden_facts(self):
        extracted = {
            'company_name': {'value': 'NVIDIA Corporation', 'sources': [{'url': 'https://example.com/a'}]},
            'founded': {'value': '2008', 'sources': [{'url': 'https://example.com/b'}]},
        }
        verified = FactVerifier.verify(extracted, [{'url': 'https://example.com/a'}], query='NVIDIA company overview')
        self.assertEqual(verified['founded']['value'], '1993')
        fail_checks = [c for c in verified['founded']['checks'] if c['status'] == 'fail']
        self.assertGreaterEqual(len(fail_checks), 1)

    def test_dataset_renders_golden_note_and_checks(self):
        verified = {'company_name': _entry('NVIDIA Corporation'),
                    'founded': _entry('2008')}
        out = GoldenFacts.apply(verified, 'NVIDIA overview')
        dataset = FactVerifier.build_dataset(out, url_to_index={})
        self.assertIn('Golden fact', dataset)
        self.assertIn('conflicts with golden fact', dataset)
