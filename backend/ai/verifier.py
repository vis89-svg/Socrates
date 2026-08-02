from datetime import datetime, timezone
import re

from .source_weighter import SourceWeighter
from .feature_flags import FeatureFlags
from .observability import Observability
from .consistency import ConsistencyChecker
from .golden_facts import GoldenFacts


def _parse_date(date_str):
    if not date_str:
        return None
    if isinstance(date_str, (int, float)):
        try:
            return datetime.fromtimestamp(date_str, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(date_str, str):
        return None
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ', '%Y/%m/%d', '%d %b %Y', '%b %d, %Y'):
        try:
            return datetime.strptime(date_str[:19], fmt[:19]).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


_FIELD_KEYWORDS = {
    'founded': ['founded', 'established', 'incorporated', 'started', 'launched', 'created', 'began', 'est.'],
    'founded_year': ['founded', 'established', 'incorporated', 'started', 'launched', 'created', 'began', 'est.'],
    'founder': ['founder', 'co-found', 'founded by'],
    'founders': ['founder', 'co-found', 'founded by'],
    'ceo': ['ceo', 'chief executive'],
    'chairman': ['chairman', 'chair'],
    'headquarters': ['headquarters', 'headquartered', 'based in', 'hq'],
    'hq': ['headquarters', 'headquartered', 'based in', 'hq'],
    'location': ['based in', 'located', 'headquarters'],
    'employees': ['employees', 'staff', 'workforce', 'headcount'],
    'revenue': ['revenue', 'income', 'earnings', 'sales', 'turnover'],
    'ticker': ['ticker', 'symbol', 'stock'],
    'website': ['website', 'site', 'web'],
    'market_cap': ['market cap', 'market capitalization', 'valuation'],
    'price': ['price', 'cost', 'priced', 'msrp'],
    'release_date': ['release', 'launch', 'shipped', 'announced', 'available'],
    'status': ['status', 'available', 'released', 'shipping', 'announced', 'unreleased'],
}


def _field_keywords(field):
    return _FIELD_KEYWORDS.get(str(field).lower().strip())


def _value_variants(value):
    if isinstance(value, list):
        return [str(v) for v in value if v is not None and str(v).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [] if text in ('', 'null') else [text]


def _source_content_by_url(all_results):
    lookup = {}
    for r in all_results or []:
        url = r.get('url', '')
        if not url:
            continue
        parts = [str(r.get('title') or ''), str(r.get('snippet') or ''), str(r.get('page_text') or '')]
        lookup[url] = '\n'.join(p for p in parts if p)
    return lookup


def _content_supports(content, variant, keywords=None):
    """True if the source text contains the value, False if it provably does not,
    None if there is no content to check against.

    With `keywords` (field-specific terms such as "founded" for the founded
    field), the value must appear in the SAME SENTENCE as at least one keyword;
    a page that merely mentions the value in an unrelated context is treated
    as not supporting the claim. If the page contains none of the keywords,
    the plain value check is used (the page does not discuss the topic at all,
    so it can neither confirm nor contradict the value's wording).
    """
    if not content:
        return None
    vlow = variant.lower()
    clow = content.lower()
    if vlow in clow:
        present = [k for k in (keywords or []) if k and k in clow]
        if not present:
            return True
        sentences = [s for s in re.split(r'(?<=[.!?])\s+|\n+', clow) if s.strip()]
        for sentence in sentences:
            if vlow in sentence and any(k in sentence for k in present):
                return True
        return False
    numbers = re.findall(r'\d[\d,.]*', vlow)
    if numbers:
        if not all(n.replace(',', '') in clow for n in numbers):
            return False
    v_tokens = set(re.findall(r"[a-z0-9']+", vlow))
    if len(v_tokens) <= 1:
        return False
    c_tokens = set(re.findall(r"[a-z0-9']+", clow))
    return len(v_tokens & c_tokens) / len(v_tokens) >= 0.5


class FactVerifier:
    @staticmethod
    def verify(extracted_data, all_results, tracer=None, query=None):
        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('verifier_start', {'fields_count': len(extracted_data), 'results_count': len(all_results)})

        source_texts = _source_content_by_url(all_results)
        verified = {}
        total_dropped = 0
        total_dropped_unrelated = 0
        for field, entry in extracted_data.items():
            if entry is None:
                verified[field] = {'value': None, 'sources': [], 'published_dates': [], 'confidence': 'none', 'note': 'Not found in available sources'}
                continue

            value = entry.get('value')
            raw_sources = entry.get('sources', [])
            variants = _value_variants(value)
            keywords = _field_keywords(field)

            weighted_sources = []
            published_dates = []
            total_weight = 0
            dropped = 0
            dropped_unrelated = 0
            for src in raw_sources:
                if isinstance(src, dict):
                    url = src.get('url')
                    pub_date = src.get('published_date')
                else:
                    url = src
                    pub_date = None
                if url:
                    w = SourceWeighter.weight(url)
                    if w > 0:
                        if url not in source_texts:
                            dropped += 1
                            continue
                        content = source_texts.get(url)
                        supported = None
                        if variants:
                            for variant in variants:
                                check = _content_supports(content, variant, keywords)
                                if check is True:
                                    supported = True
                                    break
                                if check is False:
                                    supported = False
                        if supported is False:
                            if keywords:
                                dropped_unrelated += 1
                            else:
                                dropped += 1
                            continue
                        weighted_sources.append({'url': url, 'weight': w})
                        if pub_date:
                            published_dates.append(pub_date)
                        total_weight += w

            source_count = len(weighted_sources)

            newest_date = None
            for d in published_dates:
                parsed = _parse_date(d)
                if parsed and (newest_date is None or parsed > newest_date):
                    newest_date = parsed

            if source_count == 0:
                confidence = 'none'
                if dropped_unrelated:
                    note = f'Value appears in claimed sources but not in a "{field.replace("_", " ")}" context'
                else:
                    note = 'No supporting source URLs provided' if not dropped else 'Value not found in its claimed sources'
            elif source_count >= 3:
                confidence = 'high'
                note = f'Supported by {source_count} independent sources'
            elif source_count == 2:
                confidence = 'medium'
                note = f'Supported by {source_count} independent sources'
            else:
                confidence = 'low'
                note = f'Limited to {source_count} source(s)'
            if dropped:
                note += f' ({dropped} claimed source(s) did not contain this value)'
            if dropped_unrelated:
                note += f' ({dropped_unrelated} claimed source(s) mentioned it in an unrelated context)'
            total_dropped += dropped
            total_dropped_unrelated += dropped_unrelated

            if newest_date:
                age_days = (datetime.now(timezone.utc) - newest_date).days
                if age_days > 730:
                    note += f' WARNING: newest supporting source is {age_days // 365} years old; evidence may be stale.'
                    if confidence == 'high':
                        confidence = 'medium'

            if isinstance(value, list) and len(value) > 1:
                dates_part = ''
                if published_dates:
                    dates_part = f' (source dates: {", ".join(sorted(set(published_dates)))})'
                note = 'Sources disagree between values: ' + '; '.join(str(v) for v in value[:3]) + dates_part

            if value == '' or value == 'null' or value is None:
                verified[field] = {'value': None, 'sources': [], 'published_dates': [], 'confidence': 'none', 'note': 'Not found in available sources'}
            else:
                verified[field] = {
                    'value': value,
                    'sources': [s['url'] for s in weighted_sources],
                    'published_dates': published_dates,
                    'confidence': confidence,
                    'note': note,
                }

        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('verifier_complete', {
                'fields_verified': len(verified),
                'high_confidence': sum(1 for v in verified.values() if v.get('confidence') == 'high'),
                'claimed_sources_dropped': total_dropped,
                'claimed_sources_unrelated_context': total_dropped_unrelated,
            })

        verified = GoldenFacts.apply(verified, query, tracer=tracer)

        checks = ConsistencyChecker.annotate(verified)
        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('consistency_checks', {
                'total': len(checks),
                'fail': sum(1 for c in checks if c['status'] == 'fail'),
                'warn': sum(1 for c in checks if c['status'] == 'warn'),
                'checks': checks,
            })

        return verified

    @staticmethod
    def build_dataset(verified, url_to_index=None):
        lines = ['Verified Fact Dataset:\n']
        for field, entry in verified.items():
            label = field.replace('_', ' ').title()
            if entry['value'] is None:
                lines.append(f'{label}: [Not found]')
            else:
                val = entry['value']
                if isinstance(val, list):
                    val = ', '.join(str(v) for v in val)
                elif isinstance(val, dict):
                    val = ', '.join(f'{k}: {v}' for k, v in val.items())
                if url_to_index:
                    indices = sorted({url_to_index[s] for s in entry['sources'] if s in url_to_index})
                    sources_str = ', '.join(f'[{i}]' for i in indices)
                else:
                    sources_str = ', '.join(f'[{i+1}]' for i in range(len(entry['sources'])))
                lines.append(f'{label}: {val}')
                if sources_str:
                    lines.append(f'  Sources: {sources_str}')
                if entry.get('published_dates'):
                    dates_str = ', '.join(set(entry['published_dates']))
                    lines.append(f'  Published: {dates_str}')
                lines.append(f'  Confidence: {entry["confidence"]}')
                if entry.get('note'):
                    lines.append(f'  Note: {entry["note"]}')
                for c in entry.get('checks') or []:
                    lines.append(f'  Check [{c["status"].upper()}]: {c["detail"]}')
            lines.append('')
        return '\n'.join(lines)
