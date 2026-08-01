from datetime import datetime, timezone

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


class FactVerifier:
    @staticmethod
    def verify(extracted_data, all_results, tracer=None, query=None):
        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('verifier_start', {'fields_count': len(extracted_data), 'results_count': len(all_results)})

        verified = {}
        for field, entry in extracted_data.items():
            if entry is None:
                verified[field] = {'value': None, 'sources': [], 'published_dates': [], 'confidence': 'none', 'note': 'Not found in available sources'}
                continue

            value = entry.get('value')
            raw_sources = entry.get('sources', [])

            weighted_sources = []
            published_dates = []
            total_weight = 0
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
                note = 'No supporting source URLs provided'
            elif source_count >= 3:
                confidence = 'high'
                note = f'Supported by {source_count} independent sources'
            elif source_count == 2:
                confidence = 'medium'
                note = f'Supported by {source_count} independent sources'
            else:
                confidence = 'low'
                note = f'Limited to {source_count} source(s)'

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
