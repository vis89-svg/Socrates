import re
from .source_weighter import SourceWeighter


class ConfidenceScorer:
    @staticmethod
    def analyze_response(response_text, search_results, verified=None):
        if not search_results:
            return response_text, [], []

        url_by_index = {}
        for i, r in enumerate(search_results, 1):
            url = r.get('url', '')
            title = r.get('title', '')
            if url:
                url_by_index[str(i)] = {'title': title, 'url': url, 'weight': SourceWeighter.weight(url)}

        source_refs = ConfidenceScorer._extract_source_refs(response_text)
        used_indices = source_refs['all_indices']

        citations = ConfidenceScorer._build_citations(used_indices, url_by_index)
        section_confidence = ConfidenceScorer._section_confidence(response_text, used_indices, url_by_index)
        summary_badge = ConfidenceScorer._overall_confidence(section_confidence)

        enriched = response_text
        if summary_badge:
            enriched += f'\n\n---\n**Report Confidence:** {summary_badge["label"]} ({summary_badge["score"]}% of claims supported by sources)'

        data_quality = ConfidenceScorer._data_quality(verified, url_by_index, summary_badge)
        if data_quality:
            enriched += '\n\n' + data_quality

        has_facts_section = '## Key Facts' in response_text or '### Facts' in response_text
        has_analysis_section = '## Analysis' in response_text or '### Analysis' in response_text

        notes = []
        if not has_facts_section:
            notes.append('Missing "Key Facts" section')
        if not has_analysis_section:
            notes.append('Missing "Analysis" section separate from facts')
        total_claims = len(used_indices)
        if total_claims < 3:
            notes.append('Very few source citations found — response may lack evidence')
        if source_refs['single_source_claims'] > 0:
            notes.append(f'{source_refs["single_source_claims"]} claim(s) rely on only one source')

        return enriched, citations, notes

    @staticmethod
    def _data_quality(verified, url_by_index, summary_badge):
        if not verified:
            return None

        lines = ['## Data Quality Report']
        verified_facts = {f: e for f, e in verified.items() if e and e.get('value') is not None}
        missing = [f for f, e in verified.items() if not e or e.get('value') is None]

        if summary_badge:
            lines.append(f'- Overall confidence: {summary_badge["label"]} ({summary_badge["score"]}% of claims supported by sources)')
        lines.append(f'- Verified facts: {len(verified_facts)} of {len(verified)} fields extracted')

        source_urls = set()
        low_confidence = 0
        for f, e in verified_facts.items():
            source_urls.update(e.get('sources', []))
            if e.get('confidence') == 'low':
                low_confidence += 1

        tiers = {'official': 0, 'medium': 0, 'general': 0}
        for url in source_urls:
            w = SourceWeighter.weight(url)
            if w >= 5:
                tiers['official'] += 1
            elif w >= 3:
                tiers['medium'] += 1
            else:
                tiers['general'] += 1

        lines.append(f'- Sources used: {len(source_urls)}')
        lines.append(f'- Official/government sources: {tiers["official"]}')
        lines.append(f'- High-authority news/profiles: {tiers["medium"]}')
        lines.append(f'- General sources: {tiers["general"]}')
        lines.append(f'- Fields with low confidence: {low_confidence}')
        if missing:
            lines.append(f'- Missing fields ({len(missing)}): {", ".join(f.replace("_", " ") for f in missing)}')

        return '\n'.join(lines)

    @staticmethod
    def _extract_source_refs(text):
        all_indices = set()
        single_source_claims = 0
        for match in re.finditer(r'\[Source\s+(\d+)\]', text, re.IGNORECASE):
            all_indices.add(match.group(1))
        for match in re.finditer(r'\[(\d+)\]', text):
            idx = match.group(1)
            if idx.isdigit():
                all_indices.add(idx)
        single_matches = re.findall(r'only\.?\]', text, re.IGNORECASE)
        single_source_claims = len(single_matches)
        return {
            'all_indices': all_indices,
            'single_source_claims': single_source_claims,
            'total': len(all_indices),
        }

    @staticmethod
    def _build_citations(used_indices, url_by_index):
        citations = []
        seen_urls = set()
        for idx in sorted(used_indices, key=int):
            entry = url_by_index.get(idx)
            if entry and entry['url'] not in seen_urls:
                citations.append({
                    'index': int(idx),
                    'title': entry['title'],
                    'url': entry['url'],
                    'authority': SourceWeighter.tier_label(entry['url']),
                })
                seen_urls.add(entry['url'])
        return citations

    @staticmethod
    def _section_confidence(text, used_indices, url_by_index):
        weights = []
        for idx in used_indices:
            entry = url_by_index.get(idx)
            if entry:
                weights.append(entry['weight'])
        if not weights:
            return {'average_weight': 0, 'high_count': 0, 'total': 0}
        return {
            'average_weight': sum(weights) / len(weights),
            'high_count': sum(1 for w in weights if w >= 3),
            'total': len(weights),
        }

    @staticmethod
    def _overall_confidence(section_conf):
        if not section_conf or section_conf['total'] == 0:
            return None
        total = section_conf['total']
        high = section_conf['high_count']
        avg = section_conf['average_weight']
        if total >= 5 and high >= 3 and avg >= 3:
            return {'label': 'High', 'score': 90}
        if total >= 3 and avg >= 2:
            return {'label': 'Medium', 'score': 70}
        if total >= 1:
            return {'label': 'Low', 'score': 40}
        return {'label': 'None', 'score': 0}
