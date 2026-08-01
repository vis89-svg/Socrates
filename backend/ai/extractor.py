import json
import os
import re
from .feature_flags import FeatureFlags
from .observability import Observability


def _load_prompt(name):
    path = os.path.join(os.path.dirname(__file__), 'prompts', name)
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''


def _parse_json(text):
    if not text:
        return None
    text = text.strip()
    text = re.sub(r'```(?:json)?', '', text, flags=re.IGNORECASE)
    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    in_str = False
    esc = False
    end = len(text)
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
    candidate = text[start:end]
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    try:
        cleaned = re.sub(r',(\s*[}\]])', r'\1', candidate)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    return None


_EXPECTED_FIELDS = [
    'company_name', 'founded', 'headquarters', 'leadership', 'ceo',
    'employees', 'revenue', 'budget', 'mission', 'vision',
    'description', 'products', 'technologies', 'research_domains',
    'major_projects', 'achievements', 'clients', 'locations',
    'partners', 'official_website', 'social_links', 'contact',
]

_HARDWARE_FIELDS = [
    'entity', 'vendor', 'product_family', 'architecture', 'process_node',
    'release_date', 'memory', 'memory_type', 'memory_bandwidth', 'power',
    'interconnect', 'compute_performance', 'price', 'availability',
    'status', 'previous_generation', 'comparison_notes',
]

_SCHEMA_PROMPTS = {
    'company': 'extract.md',
    'hardware': 'extract_hardware.md',
}

_MAX_TOKENS = {
    'company': 1200,
    'hardware': 2000,
}

_HARDWARE_KEYWORDS = [
    'gpu', 'cpu', 'processor', 'chip', 'accelerator', 'h100', 'h200', 'b100',
    'b200', 'b300', 'gb200', 'gb300', 'blackwell', 'hopper', 'rubin', 'a100',
    'v100', 't4', 'dgx', 'grace', 'rtx', 'gtx', 'tensor core', 'mi300',
    'mi325', 'mi350', 'cdna', 'instinct', 'rdna', 'gaudi', 'habana', 'xeon',
    'epyc', 'ryzen', 'core ultra', 'core i', 'snapdragon', 'tpu', 'trainium',
    'inferentia', 'neural engine', 'apple silicon', 'm4', 'm5', 'maia',
    'cobalt', 'hbm', 'gddr', 'nvidia', 'intel', 'amd', 'specs', 'specifications',
    'memory bandwidth', 'tflops', 'pflops', 'smartphone', 'laptop', 'phone',
    'benchmark', 'tdp', 'watt', 'graphics card', 'ssd', 'nvme', 'ram',
    'iphone', 'samsung', 'galaxy', 'pixel', 'oneplus', 'camera', 'battery',
    'screen', 'display', 'cores', 'clock speed', 'interconnect',
]

_COMPANY_KEYWORDS = [
    'company', 'revenue', 'funding', 'earnings', 'ceo', 'overview',
    'headquarters', 'employees', 'founded', 'market position', 'quarterly',
    'annual report', 'valuation', 'acquisition', 'ipo', 'leadership',
    'announcement', 'news', 'market share',
]


class Extractor:
    @staticmethod
    def select_schema(query):
        q = (query or '').lower()
        hw = sum(1 for kw in _HARDWARE_KEYWORDS if kw in q)
        comp = sum(1 for kw in _COMPANY_KEYWORDS if kw in q)
        return 'hardware' if hw > comp else 'company'

    @staticmethod
    def _prompt_for(schema):
        return _load_prompt(_SCHEMA_PROMPTS.get(schema, 'extract.md'))

    @staticmethod
    def extract(search_summary, generate_fn, tracer=None, schema='company'):
        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('extractor_start', {'summary_length': len(search_summary), 'schema': schema})

        prompt_template = Extractor._prompt_for(schema)
        if not prompt_template:
            return Extractor._empty_result(schema)

        prompt = f'{prompt_template}\n\nSearch results:\n{search_summary}'
        prompt += '\n\nJSON output:'

        raw_output = ''
        for token in generate_fn(prompt, max_tokens=_MAX_TOKENS.get(schema, 1200)):
            raw_output += token

        parsed = _parse_json(raw_output)
        if not parsed:
            if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
                tracer.log_timed_stage('extractor_failed', {'raw_output_length': len(raw_output), 'schema': schema})
            parsed = Extractor._repair_json(raw_output, generate_fn, tracer=tracer)
            if not parsed:
                return Extractor._empty_result(schema)

        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('extractor_parsed', {'fields_found': list(parsed.keys()), 'schema': schema})

        return Extractor._normalize(parsed, fields=Extractor._fields_for(schema))

    @staticmethod
    def _fields_for(schema):
        return _HARDWARE_FIELDS if schema == 'hardware' else _EXPECTED_FIELDS

    @staticmethod
    def _repair_json(raw_output, generate_fn, tracer=None):
        """Cheap targeted fix: ask the model to repair malformed JSON instead of re-extracting."""
        if not raw_output or len(raw_output) > 6000:
            return None
        repair_prompt = (
            'The text below is meant to be a single JSON object but is malformed. '
            'Fix it and output ONLY the corrected JSON, nothing else. '
            'Keep every non-null field and its sources. If there is no usable JSON, output {}\n\n'
            f'Malformed output:\n{raw_output[:4000]}\n\nCorrected JSON:'
        )
        try:
            repaired = ''
            for token in generate_fn(repair_prompt, max_tokens=2000):
                repaired += token
            parsed = _parse_json(repaired)
            if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
                tracer.log_timed_stage('extractor_repaired', {
                    'repaired_length': len(repaired),
                    'ok': parsed is not None,
                })
            return parsed
        except Exception:
            return None

    @staticmethod
    def extract_missing(search_summary, fields, generate_fn, tracer=None):
        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('extract_missing_start', {'fields': fields, 'summary_length': len(search_summary)})

        prompt_template = _load_prompt('extract_missing.md')
        if not prompt_template:
            return {}

        schema_lines = ',\n'.join(
            f'  "{f}": {{"value": "... or null", "sources": [{{"url": "url1", "published_date": "2026-01-01"}}]}}' for f in fields
        )
        prompt = prompt_template.replace('{{FIELDS}}', schema_lines)
        prompt += f'\n\nSearch results:\n{search_summary}'
        prompt += '\n\nJSON output:'

        raw_output = ''
        for token in generate_fn(prompt, max_tokens=800):
            raw_output += token

        parsed = _parse_json(raw_output)
        if not parsed:
            if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
                tracer.log_timed_stage('extract_missing_failed', {'raw_output_length': len(raw_output)})
            parsed = Extractor._repair_json(raw_output, generate_fn, tracer=tracer)
            if not parsed:
                return {}

        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('extract_missing_parsed', {'fields_found': list(parsed.keys())})

        return Extractor._normalize(parsed, fields=fields)

    @staticmethod
    def _normalize(data, fields=None):
        fields = fields or _EXPECTED_FIELDS
        result = {}
        for field in fields:
            entry = data.get(field, data.get(field.replace('_', ''), None))
            if entry is None or entry == {}:
                result[field] = None
                continue
            if isinstance(entry, dict):
                value = entry.get('value', entry.get('val', None))
                raw_sources = entry.get('sources', entry.get('source', []))
                sources = []
                for src in raw_sources:
                    if isinstance(src, str):
                        sources.append({'url': src, 'published_date': None})
                    elif isinstance(src, dict):
                        sources.append({
                            'url': src.get('url'),
                            'published_date': src.get('published_date')
                        })
                if value is not None and value != '' and value != 'null':
                    result[field] = {
                        'value': value,
                        'sources': sources,
                    }
                else:
                    result[field] = None
            else:
                result[field] = {
                    'value': entry,
                    'sources': [],
                }
        return result

    @staticmethod
    def _empty_result(schema='company'):
        return {f: None for f in Extractor._fields_for(schema)}
