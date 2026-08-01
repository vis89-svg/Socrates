import json
import os
import re

from .feature_flags import FeatureFlags
from .observability import Observability

_GOLDEN_PATH = os.path.join(os.path.dirname(__file__), 'golden_facts.json')

_STATE_ABBR = {
    'alabama': 'al', 'alaska': 'ak', 'arizona': 'az', 'arkansas': 'ar',
    'california': 'ca', 'colorado': 'co', 'connecticut': 'ct', 'delaware': 'de',
    'florida': 'fl', 'georgia': 'ga', 'hawaii': 'hi', 'idaho': 'id',
    'illinois': 'il', 'indiana': 'in', 'iowa': 'ia', 'kansas': 'ks',
    'kentucky': 'ky', 'louisiana': 'la', 'maine': 'me', 'maryland': 'md',
    'massachusetts': 'ma', 'michigan': 'mi', 'minnesota': 'mn',
    'mississippi': 'ms', 'missouri': 'mo', 'montana': 'mt', 'nebraska': 'ne',
    'nevada': 'nv', 'new hampshire': 'nh', 'new jersey': 'nj', 'new mexico': 'nm',
    'new york': 'ny', 'north carolina': 'nc', 'north dakota': 'nd', 'ohio': 'oh',
    'oklahoma': 'ok', 'oregon': 'or', 'pennsylvania': 'pa', 'rhode island': 'ri',
    'south carolina': 'sc', 'south dakota': 'sd', 'tennessee': 'tn', 'texas': 'tx',
    'utah': 'ut', 'vermont': 'vt', 'virginia': 'va', 'washington': 'wa',
    'west virginia': 'wv', 'wisconsin': 'wi', 'wyoming': 'wy', 'district of columbia': 'dc',
}

_FIELD_MAP = {
    'founded': 'founded',
    'headquarters': 'headquarters',
    'ceo': 'ceo',
    'company_name': 'name',
    'official_website': 'website',
}


def _normalize(value):
    if value is None:
        return None
    text = str(value).lower().strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def _year_of(value):
    if value is None:
        return None
    match = re.search(r'(19|20)\d{2}', str(value))
    return match.group(0) if match else None


class GoldenFacts:
    _data = None

    @classmethod
    def _load(cls):
        if cls._data is None:
            try:
                with open(_GOLDEN_PATH, encoding='utf-8') as f:
                    cls._data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                cls._data = {'entities': {}, 'products': {}}
        return cls._data

    @classmethod
    def entities(cls):
        return cls._load().get('entities', {})

    @classmethod
    def products(cls):
        return cls._load().get('products', {})

    @classmethod
    def find_entity(cls, text):
        if not text:
            return None
        low = text.lower()
        best = None
        best_len = 0
        for key, entity in cls.entities().items():
            for alias in [key] + entity.get('aliases', []):
                if alias.lower() in low:
                    if len(alias) > best_len:
                        best_len = len(alias)
                        best = key
        return best

    @classmethod
    def get(cls, entity_key):
        return cls.entities().get(entity_key)

    @classmethod
    def product_lookup(cls, product):
        if not product:
            return None
        low = _normalize(product)
        return cls.products().get(low)

    @classmethod
    def product_class(cls, product):
        entry = cls.product_lookup(product)
        return entry['class'] if entry else None

    @classmethod
    def vendor_of(cls, product):
        entry = cls.product_lookup(product)
        return entry['vendor'] if entry else None

    @classmethod
    def _extract_value(cls, entry):
        if entry is None:
            return None
        value = entry.get('value') if isinstance(entry, dict) else entry
        if isinstance(value, list):
            return value
        return value

    @classmethod
    def apply(cls, verified, query, tracer=None):
        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('golden_facts_start', {'query': query})

        entity_key = cls.find_entity(query)
        if entity_key is None:
            company_value = cls._extract_value(verified.get('company_name'))
            if isinstance(company_value, list):
                company_value = company_value[0] if company_value else None
            entity_key = cls.find_entity(company_value)
        entity = cls.get(entity_key) if entity_key else None
        if not entity:
            return verified

        checks = []
        for field, golden_field in _FIELD_MAP.items():
            golden_value = entity.get(golden_field)
            if golden_value is None:
                continue
            entry = verified.get(field)
            current = cls._extract_value(entry)
            current_flat = current[0] if isinstance(current, list) and current else current

            matches = cls._values_match(current_flat, golden_value, field)
            if entry is None or current is None or current_flat is None:
                verified[field] = {
                    'value': golden_value,
                    'sources': [entity['source']],
                    'published_dates': [],
                    'confidence': 'high',
                    'note': f'Golden fact (curated metadata, source: {entity["source"]})',
                    'checks': [{'rule': 'golden_fill', 'status': 'pass', 'detail': f'Filled from golden facts for {entity_key}', 'field': field}],
                }
            elif matches:
                value = current_flat if field == 'headquarters' else golden_value
                entry['value'] = value
                entry['sources'] = [entity['source']]
                entry['confidence'] = 'high'
                entry['note'] = 'Confirmed by golden facts (curated metadata)'
                if entry.get('checks') is None:
                    entry['checks'] = []
                entry['checks'].append({'rule': 'golden_conflict', 'status': 'pass',
                                        'detail': f'Matches golden fact for {entity_key}', 'field': field})
            else:
                entry['value'] = golden_value
                entry['sources'] = [entity['source']]
                entry['confidence'] = 'high'
                entry['note'] = f'Golden fact overrides extracted value "{current_flat}" (conflict with curated metadata for {entity_key})'
                if entry.get('checks') is None:
                    entry['checks'] = []
                entry['checks'].append({'rule': 'golden_conflict', 'status': 'fail',
                                        'detail': f'Extracted "{current_flat}" conflicts with golden fact "{golden_value}"', 'field': field})
            checks.extend(verified[field].get('checks') or [])

        products = verified.get('products')
        if products:
            product_values = cls._extract_value(products)
            if isinstance(product_values, list):
                check_details = cls._check_products(product_values, entity_key)
                if check_details:
                    if products.get('checks') is None:
                        products['checks'] = []
                    products['checks'].extend(check_details)
                checks.extend(check_details)

        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('golden_facts_applied', {
                'entity': entity_key,
                'checks': [c for c in checks if c['status'] != 'pass'],
            })
        return verified

    @classmethod
    def _check_products(cls, products, entity_key):
        checks = []
        classes = set()
        for product in products:
            if not isinstance(product, str):
                continue
            info = cls.product_lookup(product)
            if not info:
                continue
            classes.add(info['class'])
            if info['vendor'] != entity_key:
                checks.append({
                    'rule': 'wrong_vendor_attribution', 'status': 'fail',
                    'detail': f'"{product}" is a {info["vendor"]} product, not a {entity_key} product',
                    'field': 'products',
                })
        known_classes = {c for c in classes if c != 'software'}
        if len(known_classes) > 1:
            checks.append({
                'rule': 'product_class_mixing', 'status': 'warn',
                'detail': f'Products span multiple classes: {", ".join(sorted(known_classes))}. '
                          'Do not compare consumer and data-center products unless the user explicitly asks.',
                'field': 'products',
            })
        return checks

    @classmethod
    def _values_match(cls, extracted, golden, field):
        if extracted is None or golden is None:
            return False
        if field == 'founded':
            return _year_of(extracted) == _year_of(golden)
        if field in ('official_website',):
            e = _normalize(extracted)
            g = _normalize(golden)
            return (e.rstrip('/') == g.rstrip('/')) or (e in g or g in e)
        if field == 'company_name':
            e = _normalize(extracted)
            g = _normalize(golden)
            return e in g or g in e
        if field == 'headquarters':
            e = _normalize(extracted)
            g = _normalize(golden)
            parts = [p.strip() for p in g.split(',')]
            city = parts[0] if parts else g
            if city not in e:
                return False
            if len(parts) > 1:
                state = _normalize(parts[1])
                if state in e:
                    return True
                return _STATE_ABBR.get(state, '') in e
            return True
        return _normalize(extracted) == _normalize(golden)
